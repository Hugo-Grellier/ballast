"""Autonomous behavior of run.py and the agent wrapper (agent.py).

The wrapper runs a fake agent CLI through fake systemd and a pass-through fake
bubblewrap (the real sandbox is covered in test_autonomy); run.py runs with a
fake `gh`, a temporary XDG_STATE_HOME and temporary Git repositories, and Spec
Kit replaced by a recording stub.
"""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import time
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_autonomy import (
    FEATURE,
    GOLDEN_CHECKS,
    ROOT,
    TOOLS,
    AutonomyCase,
    autonomy,
)

sys.path.pop(0)
sys.path.insert(0, str(TOOLS))
try:
    import run
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

EXIT_LIMIT = 5  # agent.EXIT_LIMIT


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

    def wrapper(
        self, name: str = "claude", prompt: str = "/speckit-plan", **env: str
    ) -> subprocess.CompletedProcess[str]:
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


class RunCase(WrapperCase):
    """run.py in process: real eligibility (fake gh, fake bwrap), fake engine."""

    def setUp(self) -> None:
        super().setUp()
        os.environ.pop("SPECKIT_WORKFLOW_RUN_ID")
        self.eligible_issue()
        (self.gh_dir / "auth.ok").write_text("")
        _write(self.bin / "specify", "#!/bin/sh\nexit 0\n")
        self.launched: list[tuple[list[str], str]] = []
        self.engine: dict[str, object] = {"status": "completed", "code": 0}
        self.enterContext(patch.object(run, "ROOT", self.root))
        self.enterContext(patch.object(run, "_launch", side_effect=self.fake_launch))

    def fake_launch(self, command: list[str], run_id: str, *, start: bool) -> int:
        """Stand in for Spec Kit: write the engine state, run a scenario."""
        del start
        self.launched.append((command, run_id))
        state = self.root / ".specify/workflows/runs" / run_id
        state.mkdir(parents=True, exist_ok=True)
        scenario = self.engine.get("scenario")
        if callable(scenario):
            scenario(run_id)
        (state / "state.json").write_text(
            json.dumps(
                {
                    "workflow_id": command[3],
                    "status": self.engine["status"],
                    "current_step_id": self.engine.get("step", "record-final"),
                    "step_results": {
                        self.engine.get("step", "record-final"): {
                            "status": "failed"
                            if self.engine["status"] == "failed"
                            else "completed",
                            "error": "boom",
                        }
                    },
                }
            )
        )
        return int(self.engine["code"])  # type: ignore[arg-type]

    def main(self, *argv: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = run.main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def start(self, *extra: str) -> tuple[int, str, str]:
        return self.main(
            "start",
            "--mode",
            "autonomous",
            *extra,
            "-i",
            "issue=27",
            "-i",
            "idea=Issue #27: demo",
            "-i",
            f"feature_directory={FEATURE}",
            "-i",
            "integration=claude",
        )

    def run_ids(self) -> list[str]:
        runs = autonomy.state_dir(self.root) / "runs"
        return sorted(p.name for p in runs.iterdir()) if runs.is_dir() else []

    def publishable(self, run_id: str) -> None:
        """Leave what preflight and run-checks leave behind, plus a change."""
        record = autonomy.read_run(self.root, run_id)
        record["head"] = self.git("rev-parse", "HEAD").strip()
        autonomy.write_json(
            autonomy.run_dir(self.root, run_id) / "git-config.json",
            autonomy.config_snapshot(self.root),
        )
        (self.root / FEATURE).mkdir(parents=True, exist_ok=True)
        (self.root / FEATURE / "spec.md").write_text("# Spec\n")
        (self.root / "src").mkdir(exist_ok=True)
        (self.root / "src/demo.py").write_text("print('demo')\n")
        autonomy.write_json(
            autonomy.run_dir(self.root, run_id) / "checks.json", GOLDEN_CHECKS
        )
        record["checked_tree"] = autonomy.checked_digest(self.root, FEATURE)
        autonomy.write_run(self.root, record)


class RunStartTests(RunCase):
    """T030, T031, T047: start, mode authority and end-of-run publication."""

    def test_autonomous_start_records_run_and_publishes(self) -> None:
        self.engine["scenario"] = self.publishable
        code, out, err = self.start("--wall-time", "60", "--max-agent-steps", "12")
        self.assertEqual(code, 0, err)
        ((command, run_id),) = self.launched
        self.assertEqual(command[1:4], ["workflow", "run", "ballast-autonomous"])
        inputs = [command[i + 1] for i, a in enumerate(command) if a == "-i"]
        self.assertEqual(
            [i.partition("=")[0] for i in inputs],
            ["idea", "feature_directory", "integration", "review_integration"],
        )
        self.assertIn("review_integration=codex", inputs)
        record = autonomy.read_run(self.root, run_id)
        self.assertEqual(record["status"], "published")
        self.assertEqual(autonomy.effective_mode(record), "autonomous")
        self.assertEqual(record["risk"]["level"], "R1")
        self.assertEqual(
            (
                record["limits"]["wall_time_minutes"],
                record["limits"]["max_agent_steps"],
            ),
            (60, 12),
        )
        self.assertEqual(record["limits"]["source"], "operator")
        self.assertTrue(record["cross_provider"])
        self.assertIn("Draft PR: https://github.com/acme/demo/pull/7", out)
        archive = self.root / ".git/speckit-runs" / run_id / "autonomous/run.json"
        self.assertTrue(archive.is_file())

    def test_single_provider_review(self) -> None:
        which = run.shutil.which
        self.engine["scenario"] = self.publishable
        with patch.object(
            run.shutil,
            "which",
            side_effect=lambda n: None if n == "codex" else which(n),
        ):
            code, out, _ = self.start()
        self.assertEqual(code, 0)
        record = autonomy.read_run(self.root, self.launched[0][1])
        self.assertEqual(record["review_integration"], "claude")
        self.assertFalse(record["cross_provider"])
        self.assertIn("reduced independence", out)

    def test_limits_need_autonomous_mode(self) -> None:
        for argv in (
            ("start", "--wall-time", "5", "-i", f"feature_directory={FEATURE}"),
            ("start", "--mode", "human-gated", "--max-agent-steps", "3"),
        ):
            with self.subTest(argv=argv):
                code, _, err = self.main(*argv)
                self.assertEqual(code, 2)
                self.assertIn("need --mode autonomous", err)
        self.assertEqual(self.launched, [])

    def test_default_mode_keeps_todays_argv(self) -> None:
        """AC-015, FR-001: no mode, or human-gated, is ballast-feature as today."""
        for extra in ((), ("--mode", "human-gated"), ("--mode=human-gated",)):
            with self.subTest(extra=extra):
                self.launched.clear()
                code, _, _ = self.main(
                    "start",
                    *extra,
                    "-i",
                    "idea=x",
                    "-i",
                    f"feature_directory={FEATURE}",
                )
                self.assertEqual(code, 0)
                ((command, _),) = self.launched
                self.assertEqual(
                    command[1:],
                    [
                        "workflow",
                        "run",
                        "ballast-feature",
                        "-i",
                        "idea=x",
                        "-i",
                        f"feature_directory={FEATURE}",
                    ],
                )
        self.assertEqual(self.run_ids(), [])
        self.assertEqual(self.gh_calls(), [])

    def test_mode_limits_and_eligibility_are_not_workflow_inputs(self) -> None:
        self.engine["scenario"] = self.publishable
        self.start()
        command, run_id = self.launched[0]
        joined = " ".join(command)
        for word in ("mode", "wall", "steps", "risk", "eligib", "issue="):
            self.assertNotIn(word, joined)
        self.assertTrue(autonomy.run_file(self.root, run_id).is_file())
        self.assertFalse(
            (self.root / ".specify/workflows/runs" / run_id / "run.json").exists()
        )

    def test_unknown_mode_and_input_refused(self) -> None:
        code, _, err = self.main("start", "--mode", "supervised")
        self.assertEqual(code, 2)
        self.assertIn("--mode must be", err)
        code, _, err = self.start("-i", "risk=R0")
        self.assertEqual(code, 2)
        self.assertIn("accept only", err)
        self.assertEqual(self.launched, [])

    def test_publication_failure_is_a_retryable_forge_block(self) -> None:
        self.engine["scenario"] = self.publishable
        (self.gh_dir / "FAIL_pr_create").write_text("")
        code, out, _ = self.start()
        self.assertEqual(code, 1)
        run_id = self.launched[0][1]
        record = autonomy.read_run(self.root, run_id)
        self.assertEqual(record["status"], "stopped")
        block = autonomy.read_block(self.root, run_id)
        self.assertEqual(block["category"], "forge")
        self.assertEqual(block["command"], f"ballast run publish {run_id}")
        self.assertIn(f"Next: ballast run publish {run_id}", out)
        (self.gh_dir / "FAIL_pr_create").unlink()
        code, out, err = self.main("publish", run_id)
        self.assertEqual(code, 0, err)
        self.assertEqual(autonomy.read_run(self.root, run_id)["status"], "published")
        self.assertEqual(len(self.launched), 1, "publish never runs the workflow")
        creates = [c for c in self.gh_calls() if c[:2] == ["pr", "create"]]
        self.assertEqual(len(creates), 2)

    def test_publish_refuses_other_runs(self) -> None:
        self.engine.update(status="failed", code=1, step="validate-plan")
        self.start()
        run_id = self.launched[0][1]
        code, _, err = self.main("publish", run_id)
        self.assertEqual(code, 2)
        self.assertIn("publish retries only", err)
        code, _, err = self.main("publish", "nope")
        self.assertEqual(code, 2)


class RunBlockTests(RunCase):
    """T043, T045: every stop is a categorized block with a recovery command."""

    def started(self) -> str:
        code, out, _ = self.start()
        self.assertEqual(code, 1, out)
        run_id = self.launched[0][1]
        self.assertEqual(autonomy.read_run(self.root, run_id)["status"], "stopped")
        self.out = out
        return run_id

    def agent_step(
        self, run_id: str, code: int, drafts: dict | None = None, **extra: object
    ) -> None:
        listed = {}
        for name, data in (drafts or {}).items():
            raw = json.dumps(data).encode()
            copy = autonomy.snapshot_draft(self.root, run_id, "step01", name)
            copy.parent.mkdir(parents=True, exist_ok=True)
            copy.write_bytes(raw)
            target = autonomy.drafts_dir(self.root, FEATURE) / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
            listed[name] = __import__("hashlib").sha256(raw).hexdigest()
        autonomy.append_step(
            self.root,
            run_id,
            {
                "step": "step01",
                "ran": True,
                "drafts": listed,
                "exit_code": code,
                **extra,
            },
        )

    def block_draft(self, **changes: object) -> dict:
        return {
            "category": "decision",
            "condition": "Archived items: keep or drop?",
            "no_safe_default": "Both change stored data",
            "options": [
                {"option": "Keep", "consequence": "More storage"},
                {"option": "Drop", "consequence": "Data loss"},
            ],
            "recovery": "Choose in spec.md, then continue human-gated",
            "evidence": [f"{FEATURE}/spec.md"],
            **changes,
        }

    def test_agent_block_draft_becomes_the_block(self) -> None:
        """AC-011: options and recovery come from the draft; no PD is written."""
        self.engine.update(status="failed", code=1, step="clarify")
        self.engine["scenario"] = lambda r: self.agent_step(
            r, 3, {"block.json": self.block_draft()}
        )
        run_id = self.started()
        block = autonomy.read_block(self.root, run_id)
        self.assertEqual(block["category"], "decision")
        self.assertIn("No safe, reversible default: Both change", block["condition"])
        self.assertEqual([o["option"] for o in block["options"]], ["Keep", "Drop"])
        self.assertEqual(
            block["command"],
            f"ballast run continue {run_id} --reason block-resolved --ref TEXT",
        )
        self.assertEqual(autonomy.read_decisions(self.root, run_id), [])
        self.assertFalse(
            (autonomy.drafts_dir(self.root, FEATURE) / "block.json").exists()
        )
        self.assertIn("option: Keep -> More storage", self.out)
        self.assertIn("Next: ballast run continue", self.out)

    def test_invalid_or_missing_draft_still_blocks_as_decision(self) -> None:
        for name, drafts in (
            (
                "one option",
                {
                    "block.json": self.block_draft(
                        options=[{"option": "a", "consequence": "b"}]
                    )
                },
            ),
            ("no reason", {"block.json": self.block_draft(no_safe_default=None)}),
            ("missing", None),
        ):
            with self.subTest(name=name):
                self.launched.clear()
                self.engine.update(status="failed", code=1, step="clarify")
                self.engine["scenario"] = lambda r, d=drafts: self.agent_step(r, 3, d)
                run_id = self.started()
                block = autonomy.read_block(self.root, run_id)
                self.assertEqual(block["category"], "decision")
                self.assertGreaterEqual(len(block["options"]), 2)

    def test_wrapper_exit_codes_map_to_categories(self) -> None:
        for code, category in ((4, "tamper"), (5, "limit"), (130, "interrupted")):
            with self.subTest(code=code):
                self.launched.clear()
                self.engine.update(status="failed", code=1, step="plan")
                self.engine["scenario"] = lambda r, c=code: self.agent_step(
                    r,
                    c,
                    reason="wall-time limit exhausted" if c == EXIT_LIMIT else None,
                )
                run_id = self.started()
                block = autonomy.read_block(self.root, run_id)
                self.assertEqual(block["category"], category)
                if category == "limit":
                    self.assertIn("wall-time limit exhausted", block["condition"])
                if category == "tamper":
                    self.assertEqual(block["command"], "ballast discard-runs")

    def test_tamper_keeps_its_category_despite_the_kept_marker(self) -> None:
        """The wrapper keeps the in-progress marker after tampering on purpose."""

        def tampered(run_id: str) -> None:
            self.agent_step(run_id, 4)
            marker = autonomy.state_dir(self.root) / "in-progress"
            marker.write_text("ballast-agent-x-step.scope\n")

        self.engine.update(status="failed", code=1, step="plan")
        self.engine["scenario"] = tampered
        run_id = self.started()
        self.assertEqual(autonomy.read_block(self.root, run_id)["category"], "tamper")

    def test_recorder_block_is_kept(self) -> None:
        def recorder(run_id: str) -> None:
            autonomy.record_block(
                self.root,
                run_id,
                autonomy.make_block(
                    "review-finding", "plan F-001 (high)", run_id=run_id
                ),
            )

        self.engine.update(status="failed", code=1, step="record-plan-review")
        self.engine["scenario"] = recorder
        run_id = self.started()
        self.assertEqual(
            autonomy.read_block(self.root, run_id)["category"], "review-finding"
        )
        self.assertIn("plan F-001 (high)", self.out)

    def test_failed_validator_without_block_is_postcondition(self) -> None:
        self.engine.update(status="failed", code=1, step="validate-plan")
        run_id = self.started()
        block = autonomy.read_block(self.root, run_id)
        self.assertEqual(block["category"], "postcondition")
        self.assertIn("validate-plan", block["condition"])

    def test_unfinished_step(self) -> None:
        def killed(run_id: str) -> None:
            self.agent_step(run_id, 1)
            marker = autonomy.state_dir(self.root) / "in-progress"
            marker.write_text("ballast-agent-x-step.scope\n")

        self.engine.update(status="failed", code=1, step="plan")
        self.engine["scenario"] = killed
        run_id = self.started()
        block = autonomy.read_block(self.root, run_id)
        self.assertEqual(block["category"], "unfinished-step")
        self.assertEqual(block["command"], "ballast discard-runs")

    def test_interrupted_run(self) -> None:
        self.engine.update(status="running", code=130, step="plan")
        code, _, _ = self.start()
        self.assertEqual(code, 130)
        run_id = self.launched[0][1]
        self.assertEqual(
            autonomy.read_block(self.root, run_id)["category"], "interrupted"
        )

    def test_publisher_permission_failure(self) -> None:
        self.engine["scenario"] = self.publishable
        with patch.object(
            autonomy,
            "_create_pr",
            side_effect=autonomy.AutonomyError(
                "gh pr create failed: auth", "permission"
            ),
        ):
            code, _, _ = self.start()
        self.assertEqual(code, 1)
        run_id = self.launched[0][1]
        block = autonomy.read_block(self.root, run_id)
        self.assertEqual(block["category"], "permission")
        self.assertEqual(block["command"], f"ballast run publish {run_id}")

    def test_resume_is_refused_for_autonomous_runs(self) -> None:
        """AC-014: names #18 and the human-gated continuation."""
        self.engine.update(status="failed", code=1, step="validate-plan")
        run_id = self.started()
        code, _, err = self.main("resume", run_id)
        self.assertEqual(code, 2)
        self.assertIn("autonomous resume is not supported until safe resume (#18)", err)
        self.assertIn(f"ballast run continue {run_id} --reason block-resolved", err)
        self.assertEqual(len(self.launched), 1)
        code, _, err = self.main("resume", run_id, "--mode", "autonomous")
        self.assertEqual(code, 2)

    def test_resume_of_human_gated_run_is_unchanged(self) -> None:
        code, _, _ = self.main("resume", "abc123")
        self.assertEqual(code, 0)
        ((command, run_id),) = self.launched
        self.assertEqual(
            (command[1:], run_id), (["workflow", "resume", "abc123"], "abc123")
        )


class RunContinueTests(RunCase):
    """T040, T049: continue lowers to human-gated and keeps every decision."""

    def stopped_run(self) -> str:
        def scenario(run_id: str) -> None:
            entry = {
                "point": "scope",
                "decision": "accept",
                "summary": "Scope accepted",
                "basis": "One outcome",
                "evidence": ["README.md"],
                "artifact": {"path": "README.md", "sha256": "0" * 64},
                "agent": {
                    "provider": "claude",
                    "model": "m",
                    "role": "author",
                    "step_id": "s",
                },
                "material": False,
                "supersedes": None,
                "privileged_actions": [],
                "at": autonomy.now(),
            }
            autonomy.append_decision(self.root, run_id, entry)
            baseline = self.root / ".specify/workflow-state" / run_id
            baseline.mkdir(parents=True)
            (baseline / "implementation-baseline.json").write_text('{"tree": "x"}')
            (self.root / FEATURE).mkdir(parents=True, exist_ok=True)

        self.engine.update(status="failed", code=1, step="validate-plan")
        self.engine["scenario"] = scenario
        code, _, _ = self.start()
        self.assertEqual(code, 1)
        self.engine.update(
            status="paused", code=0, step="approve-intent", scenario=None
        )
        return self.launched[0][1]

    def test_continue_records_human_decision_and_lowers(self) -> None:
        run_id = self.stopped_run()
        code, out, err = self.main(
            "continue", run_id, "--reason", "block-resolved", "--ref", "chose Keep"
        )
        self.assertEqual(code, 0, err)
        source = autonomy.read_run(self.root, run_id)
        self.assertEqual(source["status"], "continued")
        lower = source["mode_history"][-1]
        self.assertEqual(
            (lower["action"], lower["mode"], lower["by"], lower["decision_id"]),
            ("lower", "human-gated", "operator", "HD-0001"),
        )
        self.assertTrue(lower["at"])
        (hd,) = autonomy.read_human_decisions(self.root, run_id)
        self.assertEqual(
            (hd["kind"], hd["ref"], hd["resolves"]),
            ("block-resolution", "chose Keep", "block"),
        )
        command, new_id = self.launched[-1]
        self.assertEqual(command[1:4], ["workflow", "run", "ballast-continue"])
        new = autonomy.read_run(self.root, new_id)
        self.assertEqual(
            (new["workflow"], new["continues"], autonomy.effective_mode(new)),
            ("ballast-continue", run_id, "human-gated"),
        )
        copied = (
            self.root
            / ".specify/workflow-state"
            / new_id
            / "implementation-baseline.json"
        )
        self.assertTrue(copied.is_file())
        record = (self.root / FEATURE / "autonomous/record.md").read_text()
        self.assertIn("| PD-0001 | scope | accept (agent-provisional)", record)
        self.assertIn("Mode lower: human-gated", record)
        self.assertIn(f"continues as run {new_id}", out)
        self.assertEqual(len(autonomy.read_decisions(self.root, run_id)), 1)

    def test_changes_requested_after_publication(self) -> None:
        self.engine["scenario"] = self.publishable
        self.start()
        run_id = self.launched[0][1]
        self.engine.update(status="paused", scenario=None)
        code, _, err = self.main(
            "continue",
            run_id,
            "--reason",
            "changes-requested",
            "--ref",
            "https://github.com/acme/demo/pull/7#r1",
        )
        self.assertEqual(code, 0, err)
        (hd,) = autonomy.read_human_decisions(self.root, run_id)
        self.assertEqual((hd["kind"], hd["resolves"]), ("merge-feedback", None))

    def test_continue_refusals(self) -> None:
        run_id = self.stopped_run()
        for argv, text in (
            (
                (
                    "continue",
                    run_id,
                    "--reason",
                    "block-resolved",
                    "--ref",
                    "x",
                    "--mode",
                    "autonomous",
                ),
                "never raised",
            ),
            (("continue", run_id, "--mode", "autonomous"), "never raised"),
            (("continue", run_id, "--reason", "because", "--ref", "x"), "--reason"),
            (("continue", run_id, "--reason", "block-resolved"), "--reason"),
            (
                ("continue", "missing", "--reason", "block-resolved", "--ref", "x"),
                "not an autonomous run",
            ),
        ):
            with self.subTest(argv=argv):
                code, _, err = self.main(*argv)
                self.assertEqual(code, 2)
                self.assertIn(text, err)
        self.assertEqual(autonomy.read_run(self.root, run_id)["status"], "stopped")
        self.main("continue", run_id, "--reason", "block-resolved", "--ref", "x")
        code, _, err = self.main(
            "continue", run_id, "--reason", "block-resolved", "--ref", "x"
        )
        self.assertEqual(code, 2)
        self.assertIn("continued", err)
        code, _, err = self.main("resume", run_id)
        self.assertEqual(code, 2)
        self.assertIn("resume that run instead", err)

    def test_continuation_resumes_human_gated(self) -> None:
        run_id = self.stopped_run()
        self.main("continue", run_id, "--reason", "block-resolved", "--ref", "x")
        new_id = self.launched[-1][1]
        code, _, err = self.main("resume", new_id)
        self.assertEqual(code, 0, err)
        self.assertEqual(self.launched[-1][0][1:], ["workflow", "resume", new_id])

    def test_no_path_raises_a_human_gated_run(self) -> None:
        """AC-017, FR-003: a paused human-gated run is never altered."""
        human = autonomy.new_run(
            run_id="human1",
            feature=FEATURE,
            issue=27,
            workflow="ballast-continue",
            mode="human-gated",
            integration="claude",
            continues="other1",
        )
        with self.assertRaises(autonomy.AutonomyError):
            autonomy.change_mode(human, "autonomous", reason=None, decision_id=None)
        autonomy.write_run(self.root, human)
        before = autonomy.run_file(self.root, "human1").read_bytes()
        self.engine["scenario"] = self.publishable
        self.start()
        self.assertEqual(autonomy.run_file(self.root, "human1").read_bytes(), before)
        code, _, _ = self.main(
            "continue", "human1", "--reason", "block-resolved", "--ref", "x"
        )
        self.assertEqual(code, 2)


class RunRefusalTests(RunCase):
    """T050: every refusal exits 2 before any agent step, with its reason."""

    def refused(self, *text: str, extra: tuple[str, ...] = ()) -> str:
        code, _, err = self.start(*extra)
        self.assertEqual(code, 2, err)
        for item in text:
            self.assertIn(item, err)
        self.assertIn("Run it human-gated instead: ballast run start", err)
        self.assertEqual(self.launched, [])
        self.assertFalse((self.root / ".specify/workflow-state").exists())
        return err

    def test_scope_gate_refusals(self) -> None:
        self.eligible_issue(labels=("ready-for-agent", "epic"))
        self.refused("not eligible for autonomous: scope gate: issue is an Epic")
        self.eligible_issue(labels=())
        self.refused("not eligible for autonomous: issue has no recorded scope gate")

    def test_privileged_action_and_narrowed_risk(self) -> None:
        self.eligible_issue(actions="deploy")
        self.refused(
            "not eligible for autonomous: privileged action deploy before merge"
        )
        self.eligible_issue(risk="R2")
        (self.root / "ballast.toml").write_text(
            '[autonomous]\nrisk = ["R0", "R1"]\nallow_epics = true\n'
            '[checks]\ncommands = ["true"]\n'
        )
        self.git("commit", "-qam", "narrow")
        err = self.refused(
            "not eligible for autonomous: risk R2 excluded by ballast.toml [autonomous]"
        )
        self.assertIn("ignored [autonomous] allow_epics: cannot widen eligibility", err)

    def test_missing_scope_fields(self) -> None:
        self.gh_data(
            "repos_acme_demo_issues_27_comments.json",
            [
                {
                    "body": (
                        "Risk: R1\n<!-- ballast-intake: issue=#27; scope=feature -->"
                    ),
                    "author_association": "OWNER",
                }
            ],
        )
        self.refused("scope record lacks Privileged actions before merge:")

    def test_host_and_checkout_refusals(self) -> None:
        _write(self.bin / "bwrap", "#!/bin/sh\nexit 1\n")
        self.refused("confinement unavailable")
        _write(self.bin / "bwrap", FAKE_BWRAP)
        self.git("config", "remote.origin.url", "https://user:token@example.test/x.git")
        self.refused("git configuration carries a credential")
        self.git("config", "remote.origin.url", str(self.base / "origin.git"))
        (self.root / "dirty.txt").write_text("x")
        self.refused("clean worktree")
        (self.root / "dirty.txt").unlink()
        (self.root / "ballast.toml").write_text("")
        self.git("commit", "-qam", "no checks")
        self.refused("[checks]")

    def test_gh_failure_fails_closed(self) -> None:
        (self.gh_dir / "FAIL_api").write_text("")
        self.refused("cannot check autonomous eligibility")

    def test_issue_must_match_feature(self) -> None:
        code, _, err = self.main(
            "start",
            "--mode",
            "autonomous",
            "-i",
            "issue=28",
            "-i",
            "idea=x",
            "-i",
            f"feature_directory={FEATURE}",
        )
        self.assertEqual(code, 2)
        self.assertIn("is not for issue #28", err)
        code, _, err = self.main(
            "start",
            "--mode",
            "autonomous",
            "-i",
            "idea=x",
            "-i",
            f"feature_directory={FEATURE}",
        )
        self.assertEqual(code, 2)
        self.assertIn("-i issue", err)

    def test_out_of_range_limit(self) -> None:
        self.refused(
            "--wall-time must be an integer from 1 to 1440",
            extra=("--wall-time", "2000"),
        )

    def test_eligible_r0_starts_with_its_risk(self) -> None:
        self.eligible_issue(risk="R0")
        self.engine["scenario"] = self.publishable
        code, _, err = self.start()
        self.assertEqual(code, 0, err)
        record = autonomy.read_run(self.root, self.launched[0][1])
        self.assertEqual(record["risk"]["level"], "R0")
