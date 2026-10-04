"""Autonomous behavior of run.py and the agent wrapper (agent.py).

The wrapper runs a fake agent CLI through fake systemd and a pass-through fake
bubblewrap (the real sandbox is covered in test_autonomy); run.py runs with a
fake `gh`, a temporary XDG_STATE_HOME and temporary Git repositories, and Spec
Kit replaced by a recording stub.
"""

from __future__ import annotations

import json
import os
import sys
import time
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_autonomy import (
    FEATURE,
    ROOT,
    TOOLS,
    AutonomyCase,
    autonomy,
)

sys.path.pop(0)
sys.path.insert(0, str(TOOLS))
try:
    pass
finally:
    sys.path.pop(0)

FAKE_SYSTEMD_RUN = """#!/usr/bin/env python3
import os, sys
args = sys.argv[1:]
command = args[args.index("--") + 1 :]
os.execvp(command[0], command)
"""
FAKE_SYSTEMCTL = """#!/usr/bin/env python3
import sys
if "is-active" in sys.argv:
    print("inactive")
    sys.exit(3)
"""
# Pass-through bwrap: answers the confinement probe as fully confined and
# records the argv of every other command.
FAKE_BWRAP = """#!/usr/bin/env python3
import json, os, sys
args = sys.argv[1:]
command = args[args.index("--") + 1 :]
if len(command) > 4 and command[3] == "-c" and "targets, persist" in command[4]:
    targets = json.loads(command[5])[0]
    print(json.dumps({**{t: "ok" for t in targets}, "operator environ": "ok"}))
    sys.exit(0)
with open(os.environ["FAKE_BWRAP_LOG"], "a") as log:
    log.write(json.dumps(args) + "\\n")
os.execvp(command[0], command)
"""
FAKE_CLI = """#!/usr/bin/env python3
import json, os, sys, time
with open(os.environ["FAKE_ARGV"], "w") as handle:
    json.dump({"argv": sys.argv[1:], "env": sorted(os.environ)}, handle)
drafts = os.environ.get("FAKE_DRAFTS")
if drafts:
    os.makedirs(drafts, exist_ok=True)
    for name in os.environ.get("FAKE_DRAFT_NAMES", "").split(","):
        if name:
            with open(os.path.join(drafts, name), "w") as handle:
                handle.write('{"point": "plan"}')
if os.environ.get("FAKE_SLEEP"):
    time.sleep(float(os.environ["FAKE_SLEEP"]))
print(os.environ.get("FAKE_STDOUT", "done"))
"""


def _write(path: Path, text: str) -> None:
    path.write_text(text)
    path.chmod(0o755)


class WrapperCase(AutonomyCase):
    """An Autonomous run record and the fakes the wrapper needs."""

    def setUp(self) -> None:
        super().setUp()
        for name, source in (
            ("systemd-run", FAKE_SYSTEMD_RUN),
            ("systemctl", FAKE_SYSTEMCTL),
            ("bwrap", FAKE_BWRAP),
            ("claude", FAKE_CLI),
            ("codex", FAKE_CLI),
        ):
            _write(self.bin / name, source)
        os.environ.update(
            {
                "FAKE_ARGV": str(self.base / "argv.json"),
                "FAKE_BWRAP_LOG": str(self.base / "bwrap.log"),
                "SPECKIT_WORKFLOW_RUN_ID": "run42",
                "GH_TOKEN": "secret-token",
                "ANTHROPIC_API_KEY": "key",
            }
        )

    def wrapper(self, name: str = "claude", prompt: str = "/speckit-plan", **env: str):
        import subprocess  # noqa: PLC0415

        return subprocess.run(  # noqa: S603
            [str(ROOT / "tools/spec_workflow/bin" / name), "-p", prompt],
            cwd=self.root,
            env={**os.environ, **env},
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )

    def ran(self) -> dict | None:
        path = self.base / "argv.json"
        return json.loads(path.read_text()) if path.exists() else None

    def steps(self) -> list[dict]:
        return autonomy.read_steps(self.root, "run42")


class AgentWrapperAutonomousTests(WrapperCase):
    """T014, T044: run-record checks, confinement, limits, draft ownership."""

    def test_human_gated_run_keeps_todays_argv(self) -> None:
        result = self.wrapper()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.ran()["argv"][:2], ["-p", "/speckit-plan"])
        self.assertFalse((self.base / "bwrap.log").exists())
        self.assertIn("GH_TOKEN", self.ran()["env"])

    def test_autonomous_workflow_without_record_refuses(self) -> None:
        state = self.root / ".specify/workflows/runs/run42"
        state.mkdir(parents=True)
        (state / "state.json").write_text('{"workflow_id": "ballast-autonomous"}')
        result = self.wrapper()
        self.assertEqual(result.returncode, 2)
        self.assertIn("no operator run record", result.stderr)
        self.assertIsNone(self.ran())

    def test_inactive_run_refuses(self) -> None:
        for status in ("stopped", "completed"):
            with self.subTest(status=status):
                record = self.make_run()
                autonomy.set_status(record, status)
                autonomy.write_run(self.root, record)
                result = self.wrapper()
                self.assertEqual(result.returncode, 2)
                self.assertIn("#18", result.stderr)
                self.assertIsNone(self.ran())

    def test_confined_step_counts_and_hides_secrets(self) -> None:
        self.make_run()
        result = self.wrapper()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(autonomy.read_run(self.root, "run42")["agent_steps"], 1)
        (bwrap,) = [
            json.loads(line)
            for line in (self.base / "bwrap.log").read_text().splitlines()
        ]
        self.assertEqual(bwrap[:3], ["--ro-bind", "/", "/"])
        self.assertIn("--unshare-pid", bwrap)
        env = self.ran()["env"]
        self.assertNotIn("GH_TOKEN", env)
        self.assertIn("ANTHROPIC_API_KEY", env)
        (step,) = self.steps()
        self.assertEqual(
            (step["role"], step["exit_code"], step["ran"]), ("author", 0, True)
        )
        self.assertRegex(step["tree_before"], r"^[0-9a-f]{40}$")

    def test_reviewer_role(self) -> None:
        self.make_run()
        self.assertEqual(
            self.wrapper(prompt="/speckit-ballast-review plan").returncode, 0
        )
        self.assertEqual(self.steps()[0]["role"], "reviewer")

    def test_expired_deadline_refuses_before_spawn(self) -> None:
        past = (datetime.now(UTC) - timedelta(minutes=1)).replace(microsecond=0)
        record = self.make_run()
        record["limits"]["deadline"] = past.isoformat()
        autonomy.write_run(self.root, record)
        result = self.wrapper()
        self.assertEqual(result.returncode, 5)
        self.assertIn("wall-time limit exhausted", result.stderr)
        self.assertIsNone(self.ran())
        (step,) = self.steps()
        self.assertEqual((step["ran"], step["exit_code"]), (False, 5))

    def test_step_limit_refuses_before_spawn(self) -> None:
        record = self.make_run()
        record["limits"]["max_agent_steps"] = 1
        autonomy.write_run(self.root, record)
        self.assertEqual(self.wrapper().returncode, 0)
        (self.base / "argv.json").unlink()
        result = self.wrapper()
        self.assertEqual(result.returncode, 5)
        self.assertIn("agent step limit exhausted", result.stderr)
        self.assertIsNone(self.ran())
        self.assertEqual(autonomy.read_run(self.root, "run42")["agent_steps"], 1)

    def test_agent_outliving_the_deadline_is_stopped(self) -> None:
        record = self.make_run()
        soon = datetime.now(UTC).replace(microsecond=0) + timedelta(seconds=3)
        record["limits"]["deadline"] = soon.isoformat()
        autonomy.write_run(self.root, record)
        started = time.monotonic()
        result = self.wrapper(FAKE_SLEEP="60")
        self.assertEqual(result.returncode, 5, result.stderr)
        self.assertLess(time.monotonic() - started, 40)
        self.assertEqual(
            self.steps()[-1]["reason"], "wall-time limit exhausted during the step"
        )
        logs = list((self.root / ".specify/workflow-state/run42/agents").iterdir())
        self.assertEqual(len(logs), 1)
        self.assertTrue((logs[0] / "meta.json").exists())

    def test_drafts_belong_to_the_step_that_wrote_them(self) -> None:
        self.make_run()
        drafts = autonomy.drafts_dir(self.root, FEATURE)
        drafts.mkdir(parents=True)
        (drafts / "plan-review.json").write_text('{"planted": true}')
        result = self.wrapper(
            prompt="/speckit-ballast-review plan",
            FAKE_DRAFTS=str(drafts),
            FAKE_DRAFT_NAMES="plan-review.json",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        (step,) = self.steps()
        self.assertEqual(step["set_aside"], ["plan-review.json"])
        content = (drafts / "plan-review.json").read_bytes()
        self.assertEqual(
            step["drafts"],
            {"plan-review.json": __import__("hashlib").sha256(content).hexdigest()},
        )
        copy = autonomy.snapshot_draft(
            self.root, "run42", step["step"], "plan-review.json"
        )
        self.assertEqual(copy.read_bytes(), content)
        aside = autonomy.run_dir(self.root, "run42") / "set-aside" / step["step"]
        self.assertEqual(
            json.loads((aside / "plan-review.json").read_text()), {"planted": True}
        )
        meta = json.loads(
            next((self.root / ".specify/workflow-state/run42/agents").iterdir())
            .joinpath("meta.json")
            .read_text()
        )
        self.assertEqual(meta["drafts"], step["drafts"])

    def test_failed_confinement_refuses(self) -> None:
        self.make_run()
        _write(self.bin / "bwrap", "#!/bin/sh\nexit 1\n")
        result = self.wrapper()
        self.assertEqual(result.returncode, 2)
        self.assertIn("confinement unavailable", result.stderr)
        self.assertIsNone(self.ran())


if __name__ == "__main__":
    unittest.main()
