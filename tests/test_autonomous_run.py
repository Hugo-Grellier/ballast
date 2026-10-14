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
import re
import subprocess
import sys
import time
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import ClassVar
from unittest.mock import patch

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_autonomy import (
    FEATURE,
    GITHUB_PIN,
    GOLDEN_CHECKS,
    ROOT,
    TOOLS,
    AutonomyCase,
    autonomy,
    fixed_decision,
    listed_pr,
    review,
)

sys.path.pop(0)
sys.path.insert(0, str(TOOLS))
try:
    import run
finally:
    sys.path.pop(0)


class TerminalText(io.StringIO):
    """A text stream that says it is a terminal: the operator's, in process."""

    def isatty(self) -> bool:
        return True


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
                handle.write(os.environ.get("FAKE_DRAFT_BODY", '{"point": "plan"}'))
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
        # Never read the operator's real login through a custom home.
        for name in ("CLAUDE_CONFIG_DIR", "CODEX_HOME"):
            os.environ.pop(name, None)
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
        self.assertNotIn("--allowedTools", self.ran()["argv"])
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
                # #21: only the trusted resume makes a stopped run active again.
                self.assertIn(f"{status}, not active", result.stderr)
                self.assertIn("ballast run resume run42", result.stderr)
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
        # Read-only shell commands only where bubblewrap bounds them (#37).
        argv = self.ran()["argv"]
        allowed = argv[
            argv.index("--allowedTools") + 1 : argv.index("--disallowedTools")
        ]
        self.assertIn("Bash(ls *)", allowed)
        self.assertIn("Bash(find *-exec*)", argv[argv.index("--disallowedTools") + 1 :])
        env = self.ran()["env"]
        self.assertNotIn("GH_TOKEN", env)
        self.assertIn("ANTHROPIC_API_KEY", env)
        (step,) = self.steps()
        self.assertEqual(
            (step["role"], step["exit_code"], step["ran"]), ("author", 0, True)
        )
        self.assertRegex(step["tree_before"], r"^[0-9a-f]{40}$")

    def test_each_wrapper_step_gets_only_its_own_cli_credentials(self) -> None:
        """#81: a Claude step never sees Codex's login or key, nor the reverse."""
        home = self.base / "home"
        for name in (".claude", ".codex"):
            (home / name).mkdir(parents=True)
        (home / ".claude/.credentials.json").write_text('{"claudeAiOauth": {}}')
        (home / ".codex/auth.json").write_text('{"OPENAI_API_KEY": "synthetic"}')
        keys = {"claude": "ANTHROPIC_API_KEY", "codex": "OPENAI_API_KEY"}
        for name, other in (("claude", "codex"), ("codex", "claude")):
            with self.subTest(name=name):
                (self.base / "bwrap.log").unlink(missing_ok=True)
                self.make_run()
                result = self.wrapper(name, HOME=str(home), OPENAI_API_KEY="o")
                self.assertEqual(result.returncode, 0, result.stderr)
                bwrap = json.loads(
                    (self.base / "bwrap.log").read_text().splitlines()[-1]
                )
                joined = " ".join(bwrap)
                self.assertIn(f"--tmp-overlay {home / f'.{name}'}", joined)
                self.assertIn(f"--tmpfs {home / f'.{other}'}", joined)
                env = self.ran()["env"]
                self.assertIn(keys[name], env)
                self.assertNotIn(keys[other], env)

    def test_reviewer_role(self) -> None:
        self.make_run()
        # An argument with no draft contract: the fake writes no valid draft,
        # and the draft retries (#21) are covered in test_autonomous_recovery.
        self.assertEqual(
            self.wrapper(prompt="/speckit-ballast-review audit").returncode, 0
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
            prompt="/speckit-ballast-review audit",
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


class RequestedKindsHookTests(WrapperCase):
    """#83: the wrapper shares the review's required_kinds with the specialists."""

    def setUp(self) -> None:
        super().setUp()
        feature = self.root / FEATURE
        (feature / "reviews").mkdir(parents=True)
        (feature / "spec.md").write_text("# Feature Specification: Demo\n")
        runs = self.root / ".specify/workflows/runs/run42"
        runs.mkdir(parents=True)
        (runs / "inputs.json").write_text(
            json.dumps({"inputs": {"feature_directory": FEATURE}})
        )
        (runs / "state.json").write_text(
            json.dumps({"workflow_id": "ballast-autonomous"})
        )
        self.make_run()
        tree = subprocess.run(
            ["git", "write-tree"],  # noqa: S607
            cwd=self.root,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        state = self.root / ".specify/workflow-state/run42"
        state.mkdir(parents=True)
        (state / "implementation-baseline.json").write_text(
            json.dumps({"feature": FEATURE, "tree": tree})
        )
        self.hint = (
            self.root
            / f".specify/workflow-state/required-reviews/{Path(FEATURE).name}.json"
        )

    def review(self, point: str, kind: str, *, required: list[str]) -> str:
        report = self.root / FEATURE / "reviews" / f"{kind}.md"
        report.write_text(f"# {kind} review\n\nLooks consistent.\n")
        return json.dumps(
            {
                "point": point,
                "decision": autonomy.POINT_DECISION[point],
                "summary": f"{point} accepted",
                "basis": "Matches the spec.",
                "evidence": [f"{FEATURE}/spec.md"],
                "artifact": f"{FEATURE}/spec.md",
                "model": "model-x",
                "material": False,
                "supersedes": None,
                "privileged_actions": [],
                "review": {
                    "kind": kind,
                    "verdict": "approved",
                    "report": f"{FEATURE}/reviews/{kind}.md",
                    "findings": [],
                    "required_kinds": required,
                },
                "assumption": None,
            }
        )

    def review_step(self, scope: str, point: str, kind: str) -> str:
        drafts = autonomy.drafts_dir(self.root, FEATURE)
        result = self.wrapper(
            prompt=f"/speckit-ballast-review {scope}",
            FAKE_DRAFTS=str(drafts),
            FAKE_DRAFT_NAMES=f"{point}.json",
            FAKE_DRAFT_BODY=self.review(point, kind, required=["dependency"]),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stderr

    def test_implementation_review_requests_reach_the_hint(self) -> None:
        self.review_step("implementation", "implementation-review", "engineering")
        self.assertIn("dependency", json.loads(self.hint.read_text())["required"])

    def test_a_failed_hint_write_names_its_cause_on_stderr(self) -> None:
        directory = self.hint.parent
        directory.parent.mkdir(parents=True, exist_ok=True)
        directory.symlink_to(self.base)
        stderr = self.review_step(
            "implementation", "implementation-review", "engineering"
        )
        self.assertIn("required-reviews hint not updated:", stderr)

    def test_a_plan_review_leaves_the_hint_alone(self) -> None:
        self.review_step("plan", "plan-review", "plan")
        self.assertFalse(self.hint.exists())


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
        # The real branch check, against the bare origin standing in for GitHub.
        origin = (self.base / "origin.git").as_uri()
        self.enterContext(
            patch.object(run.branch_sync, "_url", lambda *_a, **_k: origin)
        )

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

    def main(self, *argv: str, tty: bool = True) -> tuple[int, str, str]:
        """run.main in process; by default at the operator's terminal (#147 T028)."""
        out = TerminalText() if tty else io.StringIO()
        err = io.StringIO()
        stdin = TerminalText() if tty else io.StringIO()
        with (
            patch.object(sys, "stdin", stdin),
            redirect_stdout(out),
            redirect_stderr(err),
        ):
            code = run.main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def start(
        self, *extra: str, integration: str = "claude", tty: bool = True
    ) -> tuple[int, str, str]:
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
            f"integration={integration}",
            tty=tty,
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
        # What implementation-baseline leaves: implementation happened.
        baseline = (
            self.root
            / ".specify/workflow-state"
            / run_id
            / "implementation-baseline.json"
        )
        baseline.parent.mkdir(parents=True, exist_ok=True)
        baseline.write_text(json.dumps({"feature": FEATURE, "tree": "0" * 40}))


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

    def test_start_writes_the_issue_snapshot_for_agents(self) -> None:
        """DEC-0008: the Issue body and scope reach the agents' prompts."""
        self.engine["scenario"] = self.publishable
        code, _, err = self.start()
        self.assertEqual(code, 0, err)
        ((command, _),) = self.launched
        path = self.root / ".specify/workflow-state/issues/27.md"
        text = path.read_text()
        self.assertIn("untrusted", text.lower())
        self.assertIn("# Issue #27: Demo run", text)
        self.assertIn("## Acceptance criteria\n\n- works", text)
        self.assertIn("Labels: ready-for-agent", text)
        self.assertIn("Main outcome: Demo outcome", text)
        idea = next(a for a in command if a.startswith("idea="))
        self.assertTrue(idea.startswith("idea=Issue #27: demo"), idea)
        self.assertIn(".specify/workflow-state/issues/27.md", idea)
        self.assertIn("acceptance criteria", idea)

    def test_start_replaces_a_stale_feature_json(self) -> None:
        """Pilot: feature.json from an earlier feature broke Spec Kit scripts."""
        path = self.root / ".specify/feature.json"
        path.write_text('{"feature_directory": "specs/1-titlecase"}\n')
        self.engine["scenario"] = self.publishable
        code, _, err = self.start()
        self.assertEqual(code, 0, err)
        self.assertEqual(json.loads(path.read_text()), {"feature_directory": FEATURE})

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

    def codex_sandbox(self, *, nests: bool) -> None:
        """Install a codex whose own sandbox does (or does not) start inside bwrap."""
        refusal = "echo 'bwrap: No permissions to create a new namespace' >&2; exit 1"
        _write(
            self.bin / "codex",
            f'#!/bin/sh\n[ "$1" = sandbox ] && {{ {"exit 0" if nests else refusal}; }}'
            "\nexit 0\n",
        )

    def probes(self) -> list[list[str]]:
        log = self.base / "bwrap.log"
        lines = log.read_text().splitlines() if log.exists() else []
        return [a for a in map(json.loads, lines) if "sandbox" in a]

    def test_nested_codex_sandbox_keeps_cross_provider_review(self) -> None:
        """DEC-0004: the probe runs once, confined and offline, and passes."""
        self.codex_sandbox(nests=True)
        self.engine["scenario"] = self.publishable
        code, out, err = self.start()
        self.assertEqual(code, 0, err)
        record = autonomy.read_run(self.root, self.launched[0][1])
        self.assertEqual(
            (record["integration"], record["review_integration"]), ("claude", "codex")
        )
        self.assertNotIn("integration_fallback", record)
        (probe,) = self.probes()
        self.assertIn("--unshare-net", probe)
        self.assertNotIn(autonomy.CODEX_FALLBACK, out)

    def test_codex_without_nested_sandbox_falls_back_to_claude(self) -> None:
        """DEC-0004: Claude takes both roles; the fallback is recorded and shown."""
        self.codex_sandbox(nests=False)
        for requested in ("claude", "codex", "auto"):
            with self.subTest(integration=requested):
                self.launched.clear()
                self.engine["scenario"] = self.publishable
                code, out, err = self.start(integration=requested)
                self.assertEqual(code, 0, err)
                ((command, run_id),) = self.launched
                self.assertIn("integration=claude", command)
                self.assertIn("review_integration=claude", command)
                record = autonomy.read_run(self.root, run_id)
                self.assertEqual(
                    (record["integration"], record["review_integration"]),
                    ("claude", "claude"),
                )
                self.assertFalse(record["cross_provider"])
                self.assertEqual(
                    record["integration_fallback"], autonomy.CODEX_FALLBACK
                )
                self.assertIn(autonomy.CODEX_FALLBACK, out)
                self.assertIn("reduced independence", out)
                rendered = autonomy.render_record(record, [], None)
                self.assertIn(autonomy.CODEX_FALLBACK, rendered)

    def test_codex_only_host_without_nested_sandbox_is_refused(self) -> None:
        self.codex_sandbox(nests=False)
        which = run.shutil.which
        with patch.object(
            run.shutil,
            "which",
            side_effect=lambda n: None if n == "claude" else which(n),
        ):
            code, _, err = self.start(integration="codex")
        self.assertEqual(code, run.EXIT_REFUSED)
        self.assertIn(autonomy.CODEX_FALLBACK, err)
        self.assertEqual(self.launched, [])
        self.assertEqual(self.run_ids(), [])

    def test_no_probe_without_codex(self) -> None:
        self.codex_sandbox(nests=False)
        which = run.shutil.which
        self.engine["scenario"] = self.publishable
        with patch.object(
            run.shutil,
            "which",
            side_effect=lambda n: None if n == "codex" else which(n),
        ):
            code, out, _ = self.start()
        self.assertEqual(code, 0)
        self.assertEqual(self.probes(), [])
        self.assertNotIn(autonomy.CODEX_FALLBACK, out)

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
        # #16: the only GitHub access is the read of the run's Issue.
        self.assertTrue(self.gh_calls())
        for call in self.gh_calls():
            self.assertEqual(call[0], "api", call)
            self.assertTrue(call[1].startswith("repos/acme/demo/issues/27"), call)

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


class HumanGatedSnapshotTests(RunCase):
    """#16 T009 [AC-003]: a human-gated start writes the Issue snapshot."""

    def gated_start(self) -> tuple[int, str, str]:
        return self.main(
            "start",
            "-i",
            "idea=Issue #27: demo",
            "-i",
            f"feature_directory={FEATURE}",
        )

    def snapshot(self) -> str:
        return (self.root / ".specify/workflow-state/issues/27.md").read_text()

    def test_snapshot_with_comments_is_written_before_the_engine(self) -> None:
        comments = json.loads(
            (self.gh_dir / "repos_acme_demo_issues_27_comments.json").read_text()
        )
        comments.append(
            {
                "body": "Please also import notes.",
                "author_association": "CONTRIBUTOR",
                "user": {"login": "alice"},
                "created_at": "2026-10-01T10:00:00Z",
            }
        )
        self.gh_data("repos_acme_demo_issues_27_comments.json", comments)
        seen: list[str] = []
        self.engine["scenario"] = lambda _: seen.append(self.snapshot())
        code, out, err = self.gated_start()
        self.assertEqual(code, 0, err)
        ((command, _),) = self.launched
        self.assertEqual(command[1:4], ["workflow", "run", "ballast-feature"])
        (text,) = seen
        self.assertIn("untrusted", text.lower())
        self.assertIn("## Acceptance criteria\n\n- works", text)
        self.assertIn("Main outcome: Demo outcome", text)
        self.assertIn("### alice (CONTRIBUTOR), 2026-10-01T10:00:00Z", text)
        self.assertIn("Please also import notes.", text)
        self.assertIn("Issue snapshot: .specify/workflow-state/issues/27.md", out)
        self.assertIn(["api", "repos/acme/demo/issues/27"], self.gh_calls())

    def test_unreadable_issue_is_recorded_and_the_start_goes_on(self) -> None:
        (self.gh_dir / "FAIL_api").write_text("HTTP 503: unavailable\n")
        code, out, err = self.gated_start()
        self.assertEqual(code, 0, err)
        self.assertEqual(len(self.launched), 1)
        self.assertIn("Issue #27 could not be read: ", self.snapshot())
        self.assertIn("HTTP 503", self.snapshot())
        self.assertIn("the run lists it as unavailable", out)

    def test_missing_gh_is_recorded_and_the_start_goes_on(self) -> None:
        missing = autonomy.AutonomyError("gh not found outside working trees")
        with patch.object(run.autonomy, "read_issue", side_effect=missing):
            code, _, err = self.gated_start()
        self.assertEqual(code, 0, err)
        self.assertIn("could not be read: gh not found", self.snapshot())

    def test_engine_never_receives_a_token(self) -> None:
        self.assertIn("GH_TOKEN", os.environ)
        environment = run._environment("run1")  # noqa: SLF001
        self.assertFalse(set(environment) & set(run.draft_pr.TOKEN_VARIABLES))

    def test_autonomous_start_still_fails_closed(self) -> None:
        (self.gh_dir / "FAIL_api").write_text("")
        code, _, err = self.start()
        self.assertEqual(code, run.EXIT_REFUSED)
        self.assertIn("cannot check autonomous eligibility", err)
        self.assertEqual(self.launched, [])


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
        # #21: the operator answers the decision, then resumes in Autonomous.
        self.assertEqual(block["command"], f"ballast run resume {run_id}")
        self.assertEqual(autonomy.read_decisions(self.root, run_id), [])
        self.assertFalse(
            (autonomy.drafts_dir(self.root, FEATURE) / "block.json").exists()
        )
        self.assertIn("option: Keep -> More storage", self.out)
        self.assertIn(f"Next: ballast run resume {run_id}", self.out)

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

    def test_agent_login_failure_is_a_credential_block(self) -> None:
        """#65: an agent CLI that cannot authenticate is no failed contract."""
        reason = "the claude CLI could not authenticate"
        self.engine.update(status="failed", code=1, step="implement")
        self.engine["scenario"] = lambda r: self.agent_step(r, 6, reason=reason)
        run_id = self.started()
        block = autonomy.read_block(self.root, run_id)
        self.assertEqual(block["category"], "credential")
        self.assertIn(reason, block["condition"])
        self.assertIn("claude /login", block["recovery"])
        self.assertIn("codex login", block["recovery"])  # #76
        self.assertIn("then resume", block["recovery"])
        # #65 SEC-006: resume re-enters at the failed step (#21).
        self.assertEqual(block["command"], f"ballast run resume {run_id}")
        self.assertEqual(autonomy.block_class(block), "missing authority")

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

    def test_autonomous_resume_refuses_mode_limits_and_inputs(self) -> None:
        """#21 AC-016, AC-029 (was #18 AC-014): resume never changes the mode."""
        self.engine.update(status="failed", code=1, step="validate-plan")
        run_id = self.started()
        before = autonomy.read_run(self.root, run_id)
        for extra in (
            ("--mode", "autonomous"),
            ("--mode", "human-gated"),
            ("--wall-time", "999"),
            ("--max-agent-steps", "200"),
            ("-i", "integration=codex"),
        ):
            with self.subTest(extra=extra):
                code, _, err = self.main("resume", run_id, *extra)
                self.assertEqual(code, 2)
                self.assertIn("keeps the mode, risk, limits and integrations", err)
        self.assertEqual(autonomy.read_run(self.root, run_id), before)
        self.assertEqual(autonomy.read_human_decisions(self.root, run_id), [])
        self.assertEqual(len(self.launched), 1)

    def test_resume_of_human_gated_run_is_unchanged(self) -> None:
        # What `ballast run start` leaves: the engine inputs and the pin (SEC-002).
        inputs = self.root / ".specify/workflows/runs/abc123/inputs.json"
        inputs.parent.mkdir(parents=True)
        inputs.write_text(json.dumps({"inputs": {"feature_directory": FEATURE}}))
        run.branch_sync._write_json(  # noqa: SLF001
            run.branch_sync._pin_path(self.root, "abc123"),  # noqa: SLF001
            {"branch": "27-demo-run", "feature": FEATURE},
        )
        code, out, err = self.main("resume", "abc123")
        self.assertEqual(code, 0, out + err)
        self.assertIn("Branch sync: up-to-date 27-demo-run with main", out)
        ((command, run_id),) = self.launched
        self.assertEqual(
            (command[1:], run_id), (["workflow", "resume", "abc123"], "abc123")
        )


class UpstreamSyncRunTests(RunCase):
    """T026, T015, T019 [AC-005, AC-011, AC-021, FR-011, F-06, N-05, N-07, DEC-0006].

    run.py's Autonomous start and continue with the real branch check, against
    the bare origin.
    """

    def advance_origin(self, files: dict[str, str]) -> str:
        """Push a commit to origin's main without touching the checkout."""
        up = self.base / "up"
        if not up.exists():
            subprocess.run(  # noqa: S603
                ["git", "clone", "-q", str(self.base / "origin.git"), str(up)],  # noqa: S607
                check=True,
                capture_output=True,
            )

        def git(*args: str) -> str:
            return subprocess.run(  # noqa: S603
                ["git", *args],  # noqa: S607
                cwd=up,
                check=True,
                capture_output=True,
                text=True,
            ).stdout

        git("fetch", "-q", "origin")
        git("checkout", "-q", "-B", "main", "origin/main")
        for name, text in files.items():
            (up / name).write_text(text)
        git("add", "-A")
        git("commit", "-q", "-m", "base change")
        git("push", "-q", "origin", "main")
        return git("rev-parse", "HEAD").strip()

    def conflict(self) -> None:
        (self.root / "README.md").write_text("mine\n")
        self.git("commit", "-q", "-am", "feature edits README")
        self.advance_origin({"README.md": "theirs\n"})

    def sync_events(self, run_id: str) -> list[dict]:
        events, problems = run.draft_pr.ledger.read(self.root, run_id)
        self.assertEqual(problems, [])
        return [e["data"] for e in events if e["kind"] == "branch_sync"]

    def stopped_run(self) -> str:
        """Start an Autonomous run that stops on a decision block."""
        return RunContinueTests.stopped_run(self)  # type: ignore[arg-type]

    def test_blocked_autonomous_start_is_an_upstream_sync_block(self) -> None:
        """Q13 [AC-011, FR-011, F-06]."""
        self.conflict()
        code, out, err = self.start()
        self.assertEqual(code, 1, out + err)
        self.assertEqual(self.launched, [])
        (run_id,) = self.run_ids()
        self.assertEqual(autonomy.read_run(self.root, run_id)["status"], "stopped")
        block = autonomy.read_block(self.root, run_id)
        self.assertEqual(block["category"], "upstream-sync")
        self.assertEqual(block["command"], autonomy.RESTART_COMMAND)
        self.assertEqual(block["recovery"], autonomy.RECOVERY["upstream-sync"])
        self.assertTrue(
            block["condition"].startswith("BLOCKED_UPSTREAM_SYNC (conflict): ")
        )
        self.assertIn(". Recovery: rebase by hand", block["condition"])
        self.assertEqual(autonomy.read_decisions(self.root, run_id), [])
        self.assertIn("BLOCKED_UPSTREAM_SYNC (conflict)", err)
        self.assertIn("Autonomous run blocked (unsafe uncertainty: upstream-sync)", out)
        self.assertEqual([e["cause"] for e in self.sync_events(run_id)], ["conflict"])
        code, _, err = self.main(
            "continue", run_id, "--reason", "block-resolved", "--ref", "x"
        )
        self.assertEqual(code, 2)
        self.assertIn("there is nothing to continue", err)
        self.assertEqual(autonomy.read_human_decisions(self.root, run_id), [])

    def test_eligibility_uses_the_feature_branch_rule(self) -> None:
        """Q44 [AC-021, N-05]."""
        for name in ("develop", "feat/270-x"):
            with self.subTest(name=name):
                self.git("checkout", "-q", "-B", name, "27-demo-run")
                code, _, err = self.start()
                self.assertEqual(code, 2)
                self.assertIn("a feature branch named for the Issue", err)
                self.assertEqual(self.run_ids(), [])

    def test_recovery_command_and_resume_refusal(self) -> None:
        command = autonomy.recovery_command("r1", "upstream-sync")
        self.assertEqual(command, autonomy.RESTART_COMMAND)
        self.assertTrue(autonomy.BLOCK_COMMAND.fullmatch(command))
        self.assertIn("upstream-sync", autonomy.BLOCK_CATEGORIES)
        # #21: every other resumable block names resume.
        resume = autonomy.recovery_command("r1", "decision")
        self.assertEqual(resume, "ballast run resume r1")
        self.assertTrue(autonomy.BLOCK_COMMAND.fullmatch(resume))

    def test_continue_checks_then_pins_the_continuation(self) -> None:
        """Q4, second variant [AC-005, R12]."""
        run_id = self.stopped_run()
        new_base = self.advance_origin({"base.txt": "b\n"})
        # What `ballast trust` recorded: the recheck after the HEAD change uses it.
        trusted = autonomy.state_dir(self.root) / "trusted.json"
        trusted.write_text(
            json.dumps(run.branch_sync.launcher.trusted_inputs(self.root))
        )
        code, out, err = self.main(
            "continue", run_id, "--reason", "block-resolved", "--ref", "x"
        )
        self.assertEqual(code, 0, out + err)
        new_id = self.launched[-1][1]
        self.assertIn("Branch sync: synchronized 27-demo-run onto main", out)
        self.assertEqual(
            run.branch_sync.read_pin(self.root, new_id),
            {
                "branch": "27-demo-run",
                "feature": FEATURE,
                "base": "main",
                "base_commit": new_base,
            },
        )
        self.assertEqual(len(autonomy.read_human_decisions(self.root, run_id)), 1)
        self.assertEqual(
            [e["outcome"] for e in self.sync_events(new_id)], ["synchronized"]
        )

    def test_blocked_continue_changes_no_record(self) -> None:
        """Q4, third variant [N-07]."""
        run_id = self.stopped_run()
        self.conflict()
        before = autonomy.run_file(self.root, run_id).read_bytes()
        for _ in range(2):
            code, _, err = self.main(
                "continue", run_id, "--reason", "block-resolved", "--ref", "x"
            )
            self.assertEqual(code, 1)
            self.assertIn("BLOCKED_UPSTREAM_SYNC (conflict)", err)
        self.assertEqual(len(self.launched), 1)
        self.assertEqual(autonomy.read_human_decisions(self.root, run_id), [])
        self.assertEqual(autonomy.run_file(self.root, run_id).read_bytes(), before)
        self.assertEqual(
            [e["cause"] for e in self.sync_events(run_id) if e["outcome"] == "blocked"],
            ["conflict", "conflict"],
        )
        archives = run.draft_pr.ledger.common_dir(self.root) / "speckit-runs"
        self.assertEqual([p.name for p in archives.iterdir()], [run_id])
        pins = autonomy.state_dir(self.root) / "draft-pr"
        self.assertEqual([p.stem for p in pins.glob("*.json")], [run_id])

    def test_continue_needs_the_source_branch(self) -> None:
        """Q4, first and fourth variants [DEC-0006]."""
        run_id = self.stopped_run()
        self.git("checkout", "-q", "main")
        code, _, err = self.main(
            "continue", run_id, "--reason", "block-resolved", "--ref", "x"
        )
        self.assertEqual(code, 1)
        self.assertIn(
            "BLOCKED_UPSTREAM_SYNC (wrong-branch): on main, run started on 27-demo-run",
            err,
        )
        self.git("checkout", "-q", "27-demo-run")
        (autonomy.state_dir(self.root) / "draft-pr" / f"{run_id}.json").unlink()
        code, _, err = self.main(
            "continue", run_id, "--reason", "block-resolved", "--ref", "x"
        )
        self.assertEqual(code, 1)
        self.assertIn(f"run {run_id} has no branch or feature pin", err)
        self.assertIn("Recovery: after checking the feature in the run's record", err)
        self.assertEqual(autonomy.read_human_decisions(self.root, run_id), [])


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
            '[checks]\ncommands = ["true"]\n' + GITHUB_PIN
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

    def test_earlier_runs_record_refuses_the_start(self) -> None:
        """#95: the recovery names how to retire an earlier run's record."""
        record = self.root / FEATURE / "autonomous/record.md"
        record.parent.mkdir(parents=True)
        record.write_text("# Autonomous run record\n")
        self.git("add", "-A")
        self.git("commit", "-qm", "earlier run")
        code, _, err = self.start()
        self.assertEqual(code, 2, err)
        self.assertIn(f"git rm {FEATURE}/autonomous/record.md", err)
        self.assertIn("Git history keeps it", err)
        self.assertEqual(self.launched, [])
        self.assertEqual(self.run_ids(), [])

    def test_eligible_r0_starts_with_its_risk(self) -> None:
        self.eligible_issue(risk="R0")
        self.engine["scenario"] = self.publishable
        code, _, err = self.start()
        self.assertEqual(code, 0, err)
        record = autonomy.read_run(self.root, self.launched[0][1])
        self.assertEqual(record["risk"]["level"], "R0")


class PublisherCheckpointTests(RunCase):
    """DEC-0007: the #27 publisher and the #17 checkpoint leave one Draft PR."""

    PR: ClassVar[dict] = {
        "number": 7,
        "html_url": "https://github.com/acme/demo/pull/7",
        "state": "open",
        "draft": True,
        "merged_at": None,
        "closed_at": None,
        "head": {
            "ref": "27-demo-run",
            "repo": {"full_name": "acme/demo", "owner": {"login": "acme"}},
        },
        "base": {"ref": "main"},
    }

    def setUp(self) -> None:
        super().setUp()
        # The checkpoint's GitHub reads; `pr create` lists the PR it opened.
        self.gh_data("repos_acme_demo.json", {"default_branch": "main"})
        self.gh_data("created-pr.json", self.PR)

    def started_run(self, run_id: str) -> None:
        """Leave what the real _launch would: the run's inputs.

        The branch check pinned the branch before _launch (#18).
        """
        self.assertEqual(
            run.branch_sync.read_pin(self.root, run_id)["branch"], "27-demo-run"
        )
        inputs = self.root / ".specify/workflows/runs" / run_id / "inputs.json"
        inputs.write_text(json.dumps({"inputs": {"feature_directory": FEATURE}}))
        self.publishable(run_id)

    def test_publication_then_checkpoint_leaves_one_pr(self) -> None:
        self.engine["scenario"] = self.started_run
        code, out, err = self.start()
        self.assertEqual(code, 0, out + err)
        ((_, run_id),) = self.launched
        lines = [line for line in out.splitlines() if line.startswith("Draft PR:")]
        # The publisher opens the PR; the checkpoint runs once, after it.
        self.assertEqual(
            lines,
            [
                "Draft PR: https://github.com/acme/demo/pull/7",
                "Draft PR: reused #7 https://github.com/acme/demo/pull/7",
            ],
        )
        calls = [c[:2] for c in self.gh_calls()]
        self.assertEqual(calls.count(["pr", "create"]), 1)
        self.assertNotIn(["pr", "edit"], calls)
        # The checkpoint left the publisher's merge-review summary untouched.
        body = (self.gh_dir / "pr-body.md").read_text()
        self.assertNotIn(run.draft_pr.MARK_BEGIN, body)
        self.assertIn("Refs #27", body)
        events, _ = run.draft_pr.ledger.read(self.root, run_id)
        outcomes = [
            (e["data"]["outcome"], e["data"].get("pr_number"))
            for e in events
            if e["kind"] == "pull_request"
        ]
        self.assertEqual(outcomes, [("reused", 7)])
        # A later checkpoint keeps reusing it.
        again = run.draft_pr.checkpoint(self.root, run_id)
        self.assertEqual((again.state, again.pr_number), ("reused", 7))
        self.assertEqual([c[:2] for c in self.gh_calls()].count(["pr", "create"]), 1)

    def test_publish_retry_adopts_the_checkpoints_pr(self) -> None:
        """A PR the checkpoint opened after a failed publication is reused."""
        self.engine["scenario"] = self.started_run
        (self.gh_dir / "FAIL_pr_create").write_text("HTTP 502: Bad Gateway\n")
        code, _, _ = self.start()
        self.assertEqual(code, 1)
        ((_, run_id),) = self.launched
        self.assertEqual(autonomy.read_block(self.root, run_id)["category"], "forge")
        # The push succeeded, so a later checkpoint opens the PR itself.
        (self.gh_dir / "FAIL_pr_create").unlink()
        self.gh_data(
            "repos_acme_demo_compare_main...27-demo-run.json",
            {"files": [{"filename": "src/demo.py"}]},
        )
        self.gh_data("repos_acme_demo_pulls.json", [])
        opened = run.draft_pr.checkpoint(self.root, run_id)
        self.assertEqual((opened.state, opened.pr_number), ("created", 7), opened)
        section = (self.gh_dir / "pr-body.md").read_text()
        self.gh_data(
            "pr-list.json",
            [listed_pr(7, "Intro\n" + section)],
        )
        before = len(self.gh_calls())
        code, out, err = self.main("publish", run_id)
        self.assertEqual(code, 0, out + err)
        self.assertIn("Draft PR: https://github.com/acme/demo/pull/7", out)
        calls = [c[:2] for c in self.gh_calls()[before:]]
        self.assertNotIn(["pr", "create"], calls)
        self.assertEqual(calls.count(["pr", "edit"]), 1)
        body = (self.gh_dir / "pr-body.md").read_text()
        # The checkpoint's body, with the publisher's own section added.
        self.assertTrue(body.startswith(autonomy.SUMMARY_BEGIN), body)
        self.assertIn(f"Autonomous run {run_id} for #27", body)
        self.assertEqual(body.count(run.draft_pr.MARK_BEGIN), 1)
        self.assertTrue(body.rstrip().endswith(run.draft_pr.MARK_END))


class InvocationLockTests(RunCase):
    """#21 T006, R13: one invocation per run; the lock tells live from dead."""

    def test_lock_is_exclusive_and_released(self) -> None:
        autonomy.run_dir(self.root, "run42").mkdir(parents=True, exist_ok=True)
        with (
            run._invocation_lock("run42"),  # noqa: SLF001
            self.assertRaisesRegex(run.LockHeld, "run run42 has an active"),
            run._invocation_lock("run42"),  # noqa: SLF001
        ):
            pass
        with run._invocation_lock("run42"):  # noqa: SLF001 - free again
            pass
        lock = autonomy.run_dir(self.root, "run42") / "invocation.lock"
        self.assertEqual(lock.stat().st_mode & 0o777, 0o600)

    def test_publish_refuses_while_held(self) -> None:
        self.engine.update(status="failed", code=1, step="record-final")
        self.start()
        run_id = self.launched[0][1]
        autonomy.record_block(
            self.root,
            run_id,
            autonomy.make_block("forge", "push failed", run_id=run_id),
        )
        with run._invocation_lock(run_id):  # noqa: SLF001
            code, _, err = self.main("publish", run_id)
        self.assertEqual(code, 2)
        self.assertIn("has an active invocation", err)


class ReentryTests(unittest.TestCase):
    """#21 T018, R6: the block step and the inputs that send a resume back."""

    STEPS: ClassVar[list[str]] = list(autonomy.AUTONOMOUS_STEPS)

    def test_block_step(self) -> None:
        for failed, expected in (
            ("decide-tasks", "decide-tasks"),
            ("record-tasks", "decide-tasks"),
            ("record-scope", "decide-scope"),
            ("record-provisional-intent", "decide-intent"),
            ("record-implementation-review", "review-implementation"),
            ("record-fix-review-2", "review-fix-2"),
            ("record-fix-3", "fix-3"),
            ("record-reconciliation", "reconcile-spec"),
            ("validate-plan", "validate-plan"),
            ("checks-fix-1", "checks-fix-1"),
            ("renew-intent", "renew-intent"),
            (None, None),
            ("unknown", None),
        ):
            with self.subTest(failed=failed):
                self.assertEqual(run._block_step(failed, self.STEPS), expected)  # noqa: SLF001

    def test_every_input_maps_to_a_validator(self) -> None:
        for step in run.REENTRY_INPUTS.values():
            self.assertIn(step, self.STEPS)
            self.assertTrue(step.startswith("validate-"))


class ContinueRefusalTests(RunCase):
    """#21 T022 [AC-011, FR-011]: continue before implementation points to resume."""

    def test_pre_implementation_continue_points_to_resume(self) -> None:
        self.engine.update(status="failed", code=1, step="decide-tasks")
        self.start()
        run_id = self.launched[0][1]
        code, _, err = self.main(
            "continue", run_id, "--reason", "block-resolved", "--ref", "x"
        )
        self.assertEqual(code, 2)
        self.assertIn(
            f"run {run_id} stopped before implementation; resume it in Autonomous: "
            f"ballast run resume {run_id}",
            err,
        )
        self.assertEqual(autonomy.read_human_decisions(self.root, run_id), [])
        self.assertEqual(len(self.launched), 1)

    def test_pre_implementation_fixed_limit_names_the_restart(self) -> None:
        """SEC2-002: before implementation only a new run lifts a fixed limit."""
        self.engine.update(status="failed", code=1, step="decide-tasks")
        self.engine["scenario"] = lambda r: RunBlockTests.agent_step(
            self,  # type: ignore[arg-type]
            r,
            EXIT_LIMIT,
            reason="agent-step limit reached",
            limit="agent-steps",
        )
        _, out, _ = self.start()
        run_id = self.launched[0][1]
        block = autonomy.read_block(self.root, run_id)
        self.assertEqual((block["category"], block["limit"]), ("limit", "agent-steps"))
        self.assertEqual(block["command"], autonomy.RESTART_COMMAND)
        self.assertIn(f"Next: {autonomy.RESTART_COMMAND}", out)
        self.assertNotIn("continue human-gated", block["recovery"])
        for argv in (
            ("resume", run_id),
            ("continue", run_id, "--reason", "block-resolved", "--ref", "x"),
        ):
            with self.subTest(command=argv[0]):
                code, _, err = self.main(*argv)
                self.assertEqual(code, 2)
                self.assertIn(autonomy.RESTART_COMMAND, err)
                self.assertNotIn("ballast run continue", err)
                self.assertNotIn("ballast run resume", err)
        self.assertEqual(autonomy.read_human_decisions(self.root, run_id), [])
        self.assertEqual(len(self.launched), 1)


class HumanGatedUnchangedTests(WrapperCase):
    """#21 T042 [AC-032, FR-025]: human-gated steps get no gate and no retry."""

    def test_no_skip_and_no_retry_without_an_autonomous_record(self) -> None:
        drafts = self.root / FEATURE / "autonomous/drafts"
        result = self.wrapper(
            prompt="/speckit-ballast-decide plan",
            FAKE_DRAFTS=str(drafts),
            FAKE_DRAFT_NAMES="plan.json",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.ran()["argv"][:2], ["-p", "/speckit-ballast-decide plan"])
        self.assertNotIn("Ballast retry", " ".join(self.ran()["argv"]))
        result = self.wrapper(prompt="/speckit-ballast-fix")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("skipped", result.stdout)


class LocalFallbackRecordTests(WrapperCase):
    """#23 T025 [AC-003, AC-020]: record.md shows the local fallback setting."""

    def mode_section(self, text: str) -> str:
        return text.split("## Mode and risk\n", 1)[1].split("\n## ", 1)[0]

    def test_record_shows_the_setting(self) -> None:
        record = self.make_run()
        plain = autonomy.render_run_record(self.root, record)
        self.assertNotIn("Local fallback", plain)
        # Without a setting the record is exactly what it was before #23.
        self.assertEqual(
            plain,
            autonomy.render_record(
                record,
                autonomy.read_decisions(self.root, "run42"),
                autonomy.read_checks(self.root, "run42"),
                human=autonomy.read_human_decisions(self.root, "run42"),
                feedback=autonomy.read_feedback(self.root, "run42"),
            ),
        )
        run.fallback.write_setting(self.root, "run42", "qwen3:4b-16k")
        section = self.mode_section(autonomy.render_run_record(self.root, record))
        self.assertTrue(
            section.rstrip().endswith("- Local fallback: on (ollama qwen3:4b-16k)")
        )
        run.fallback.write_setting(self.root, "run42", None)
        section = self.mode_section(autonomy.render_run_record(self.root, record))
        self.assertIn("- Local fallback: off\n", section)
        run.fallback.setting_path(self.root, "run42").write_text("{")
        section = self.mode_section(autonomy.render_run_record(self.root, record))
        self.assertIn("- Local fallback: off\n", section)


SESSION = "claude-code:t1"
NO_SESSION = (
    "ballast: refusing: without a terminal, name the relaying agent session with "
    "--relayed-by SESSION; nothing was recorded"
)


class RelayedStartTests(RunCase):
    """#147 T021 [AC-012, AC-013]: a relayed Autonomous start, and what it refuses."""

    def test_a_relayed_start_is_recorded_as_relayed(self) -> None:
        self.engine["scenario"] = self.publishable
        code, out, err = self.start("--relayed-by", SESSION, tty=False)
        self.assertEqual(code, 0, out + err)
        ((_, run_id),) = self.launched
        record = autonomy.read_run(self.root, run_id)
        start = record["mode_history"][0]
        self.assertEqual((start["by"], start["relayed_by"]), ("relayed", SESSION))
        text = autonomy.render_run_record(self.root, record)
        self.assertIn(f"by agent session {SESSION} (relayed)", text)
        self.assertNotIn("by operator", text)

    def test_a_terminal_less_start_without_a_session_is_refused(self) -> None:
        code, _, err = self.start(tty=False)
        self.assertEqual(code, 2)
        self.assertEqual(err, NO_SESSION + "\n")
        self.assertEqual(self.run_ids(), [])
        self.assertEqual(self.launched, [])

    def test_a_relayed_approval_on_an_autonomous_run_is_refused(self) -> None:
        """AC-012."""
        self.engine["scenario"] = self.publishable
        code, _, err = self.start()
        self.assertEqual(code, 0, err)
        ((_, run_id),) = self.launched
        path = autonomy.run_dir(self.root, run_id) / "human-decisions.jsonl"
        before = path.read_bytes() if path.exists() else None
        code, _, err = self.main(
            "approve", run_id, "final", "--relayed-by", SESSION, tty=False
        )
        self.assertEqual(code, 2)
        self.assertEqual(
            err,
            "ballast: refusing: an Autonomous run has no human gate before merge; "
            "nothing was recorded\n",
        )
        self.assertEqual(path.read_bytes() if path.exists() else None, before)

    def test_invalid_sessions_and_commands_that_take_none(self) -> None:
        for session in ("a b", "human-approved", "-x", "a" * 81):
            with self.subTest(session=session):
                code, _, err = self.start("--relayed-by", session, tty=False)
                self.assertEqual(code, 2)
                self.assertIn("--relayed-by SESSION must match", err)
        for command in ("status", "publish", "checkpoint"):
            with self.subTest(command=command):
                code, _, err = self.main(
                    command, "run42", "--relayed-by", SESSION, tty=False
                )
                self.assertEqual(code, 2)
                self.assertIn(f"--relayed-by is not accepted by {command}", err)
        self.assertEqual(self.run_ids(), [])


class IssueBranchOfferTests(RunCase):
    """#147 T036 [AC-027, D-06]: the Issue branch is offered, never switched quietly."""

    def on_develop(self) -> str:
        self.git("checkout", "-q", "-b", "develop")
        self.git("branch", "-D", "27-demo-run")
        return self.git("rev-parse", "HEAD").strip()

    def start_typing(self, typed: str) -> tuple[int, str, str]:
        out, err = TerminalText(), io.StringIO()
        with (
            patch.object(sys, "stdin", TerminalText(typed)),
            redirect_stdout(out),
            redirect_stderr(err),
        ):
            code = run.main(
                [
                    "start",
                    "--mode",
                    "autonomous",
                    "-i",
                    "issue=27",
                    "-i",
                    "idea=Issue #27: demo",
                    "-i",
                    f"feature_directory={FEATURE}",
                    "-i",
                    "integration=claude",
                ]
            )
        return code, out.getvalue(), err.getvalue()

    def test_typing_switch_creates_the_branch_and_starts(self) -> None:
        self.on_develop()
        self.engine["scenario"] = self.publishable
        code, out, err = self.start_typing("switch feat-27-demo-run\n")
        self.assertEqual(code, 0, out + err)
        self.assertIn(
            "autonomous needs a feature branch named for Issue #27; this checkout "
            "is on develop.",
            out,
        )
        self.assertIn(
            "Type `switch feat-27-demo-run` to run `git switch -c feat-27-demo-run` "
            "and continue",
            out,
        )
        self.assertEqual(
            self.git("rev-parse", "--abbrev-ref", "HEAD").strip(), "feat-27-demo-run"
        )
        self.assertEqual(len(self.launched), 1)

    def test_the_one_local_issue_branch_is_proposed(self) -> None:
        self.git("checkout", "-q", "-b", "develop")
        code, out, err = self.start_typing("no\n")
        self.assertEqual(code, 2)
        self.assertIn("Type `switch 27-demo-run` to run `git switch 27-demo-run`", out)
        self.assertIn("Switch first: git switch 27-demo-run", err)

    def test_any_other_answer_stops_with_head_unchanged(self) -> None:
        head = self.on_develop()
        code, _, err = self.start_typing("yes\n")
        self.assertEqual(code, 2)
        self.assertIn(autonomy.BRANCH_REFUSAL, err)
        self.assertEqual(
            self.git("rev-parse", "--abbrev-ref", "HEAD").strip(), "develop"
        )
        self.assertEqual(self.git("rev-parse", "HEAD").strip(), head)
        self.assertEqual(self.run_ids(), [])

    def test_without_a_terminal_or_relayed_it_prints_the_commands(self) -> None:
        self.on_develop()
        for extra in ((), ("--relayed-by", SESSION)):
            with self.subTest(extra=extra):
                code, _, err = self.main(
                    "start",
                    "--mode",
                    "autonomous",
                    *extra,
                    "-i",
                    "issue=27",
                    "-i",
                    f"feature_directory={FEATURE}",
                    "-i",
                    "idea=Issue #27: demo",
                    tty=not extra,
                )
                if not extra:
                    # At a terminal with nothing typed: the same refusal.
                    pass
                self.assertEqual(code, 2)
                self.assertIn(
                    "ballast: refusing: not eligible for autonomous: autonomous "
                    "needs a feature branch named for the Issue without an open PR",
                    err,
                )
                self.assertIn("Switch first: git switch -c feat-27-demo-run", err)
                self.assertIn(
                    "Then rerun: ballast run start --mode autonomous -i issue=27 -i "
                    f"feature_directory={FEATURE}",
                    err,
                )
                self.assertEqual(
                    self.git("rev-parse", "--abbrev-ref", "HEAD").strip(), "develop"
                )
        self.assertEqual(self.run_ids(), [])


BASE_TOML = '[checks]\ncommands = ["true"]\n' + GITHUB_PIN
READY = '[autonomous]\ncompletion = "ready"\n'
DRAFT = '[autonomous]\ncompletion = "draft"\n'
PR_URL = "https://github.com/acme/demo/pull/7"
READY_LINE = (
    f"PR completion: ready-for-review #7 {PR_URL}; merging stays the only human "
    "approval"
)
TEMPLATE = ROOT / "templates/spec-kit/workflows/autonomous/workflow.yml"
HEX = re.compile(r"\b[0-9a-f]{7,64}\b")


class CompletionCase(RunCase):
    """#141: an Autonomous run whose operator records meet every condition.

    The real publisher, checkpoint and completion step run against the fake
    `gh`; only the packet is a stand-in (packet.py's own tests build it).
    The engine stub also stands in for `specify workflow resume`.
    """

    def setUp(self) -> None:
        super().setUp()
        self.gh_data("repos_acme_demo.json", {"default_branch": "main"})
        self.gh_data("created-pr.json", PublisherCheckpointTests.PR)
        # A served PR's head is what publication pushed.
        (self.gh_dir / "head-sha").write_text("auto")
        self.counts = {
            **dict.fromkeys(run.draft_pr.ledger.PACKET_COUNTS, 0),
            "verified": 2,
        }
        self.final = True
        self.verdict = "approved"
        self.before: list = []
        self.changes: list = []
        self.enterContext(
            patch.object(run.draft_pr.packet, "publish", side_effect=self.fake_packet)
        )

    def fake_packet(self, work: object, outcome: run.draft_pr.Outcome) -> object:
        """Stand in for packet.publish: published at HEAD with `self.counts`."""
        del work
        packet = run.draft_pr.packet
        if outcome.state not in {"created", "reused"}:
            return packet.make_outcome("pending", "no-pr")
        head = self.git("rev-parse", "HEAD").strip()
        return packet.PacketOutcome(
            "published",
            pr_number=outcome.pr_number,
            head=head,
            base=self.git("rev-parse", "main").strip(),
            feature_version=head,
            packet_digest="0" * 64,
            shortened=False,
            counts=dict(self.counts),
        )

    def fake_launch(self, command: list[str], run_id: str, *, start: bool) -> int:
        """Stand in for the engine; `resume` continues the run's own state."""
        directory = self.root / ".specify/workflows/runs" / run_id
        if command[2] != "resume":
            code = super().fake_launch(command, run_id, start=start)
            workflow = yaml.safe_load(TEMPLATE.read_text())
            (directory / "workflow.yml").write_text(
                yaml.safe_dump(workflow, sort_keys=False)
            )
            (directory / "inputs.json").write_text(
                json.dumps({"inputs": {"feature_directory": FEATURE}})
            )
            return code
        self.launched.append((command, run_id))
        scenario = self.engine.get("scenario")
        if callable(scenario):
            scenario(run_id)
        state = json.loads((directory / "state.json").read_text())
        state.update(
            status=self.engine["status"],
            current_step_id=self.engine.get("step", "record-final"),
        )
        (directory / "state.json").write_text(json.dumps(state))
        return int(self.engine["code"])  # type: ignore[arg-type]

    def configure(self, table: str) -> None:
        """Set ballast.toml's `[autonomous]` table, as the operator commits it."""
        (self.root / "ballast.toml").write_text(BASE_TOML + table)
        if self.git("status", "--porcelain").strip():
            self.git("commit", "-qam", "configure [autonomous]")

    def trust(self) -> None:
        """Record the checkout's inputs as `ballast trust` would."""
        launcher = run.branch_sync.launcher
        state = autonomy.state_dir(self.root)
        state.mkdir(parents=True, exist_ok=True)
        for name in (launcher.TRUSTED, launcher.TRUSTED_SOURCE):
            (state / name).unlink(missing_ok=True)
        launcher.record_baseline(
            state, launcher.trusted_inputs(self.root), source="trust"
        )

    def eligible(self, run_id: str) -> None:
        """Leave what a converged R1 run leaves: checks, reviews, acceptance."""
        for change in self.before:
            change(run_id)
        self.publishable(run_id)
        entries = [
            fixed_decision(
                1,
                "spec-reconciliation",
                review={**review("spec-reconciliation"), "verdict": self.verdict},
                provider="codex",
                role="reviewer",
            )
        ]
        if self.final:
            entries.append(fixed_decision(2, "final-acceptance"))
        for entry in entries:
            autonomy.append_decision(self.root, run_id, entry)
        for change in self.changes:
            change(run_id)

    def _eligible_run(
        self, table: str | None = READY, *extra: str
    ) -> tuple[int, str, str, str]:
        """Configure, then start an Autonomous run that reaches publication."""
        if table is not None:
            self.configure(table)
        self.engine["scenario"] = self.eligible
        code, out, err = self.start(*extra)
        return code, out, err, self.launched[-1][1] if self.launched else ""

    def blocked_run(self, *extra: str) -> str:
        """Start a run that stops at record-tasks, before publication."""
        self.engine.update(status="failed", code=1, step="record-tasks")
        code, out, err = self.start(*extra)
        self.assertEqual(code, 1, out + err)
        self.assertNotIn("PR completion:", out)
        self.engine.update(status="completed", code=0, scenario=self.eligible)
        self.engine.pop("step")
        return self.launched[-1][1]

    def pr_ready_calls(self) -> list[list[str]]:
        return [c for c in self.gh_calls() if c[:2] == ["pr", "ready"]]

    def completions(self, run_id: str) -> list[dict]:
        events, problems = run.draft_pr.ledger.read(self.root, run_id)
        self.assertEqual(problems, [])
        return [e["data"] for e in events if e["kind"] == "pr_completion"]

    def snapshot(self, run_id: str) -> dict:
        return autonomy.read_run(self.root, run_id)["eligibility"]["policy"]

    def served(self) -> dict:
        return json.loads((self.gh_dir / "repos_acme_demo_pulls_7.json").read_text())

    def draft(self, run_id: str, *reasons: tuple[str, str], cause: str = "") -> None:
        """Assert the run's last line and only event: a Draft, for `reasons`."""
        self.assertEqual(self.pr_ready_calls(), [])
        events = self.completions(run_id)
        self.assertEqual(len(events), 1, events)
        expected = {
            "outcome": "draft",
            "pr_number": 7,
            "commit": self.git("rev-parse", "HEAD").strip(),
            "reasons": [code for code, _ in reasons],
        }
        if cause:
            expected["cause"] = cause
        self.assertEqual(events[0], expected)
        self.assertTrue(self.served()["draft"])

    def last_line(self, out: str) -> str:
        return out.splitlines()[-1]


class CompletionReadyTests(CompletionCase):
    """T011, T012 [AC-001, AC-002, AC-003, FR-007, FR-012]: the ready path."""

    def test_start_marks_an_eligible_run_ready_once(self) -> None:
        code, out, err, run_id = self._eligible_run()
        self.assertEqual(code, 0, out + err)
        self.assertEqual(
            self.pr_ready_calls(), [["pr", "ready", "7", "--repo", "acme/demo"]]
        )
        lines = out.splitlines()
        self.assertEqual(lines[-1], READY_LINE)
        self.assertTrue(lines[-2].startswith("Acceptance packet: published #7"))
        self.assertEqual(lines[-3], f"Draft PR: reused #7 {PR_URL}")
        self.assertEqual(autonomy.read_run(self.root, run_id)["status"], "published")
        self.assertIsNone(autonomy.read_block(self.root, run_id))
        self.assertFalse(self.served()["draft"])
        pushed = self.git("rev-parse", "HEAD").strip()
        origin = str(self.base / "origin.git")
        self.assertEqual(
            self.git("--git-dir", origin, "rev-parse", "refs/heads/27-demo-run"),
            pushed + "\n",
        )
        self.assertEqual(
            self.completions(run_id),
            [{"outcome": "ready", "pr_number": 7, "commit": pushed}],
        )

    def test_resume_publication_evaluates_and_names_the_resolved_block(self) -> None:
        """FR-007: a resume publication evaluates; condition (11) always fails."""
        self.configure(READY)
        run_id = self.blocked_run()
        code, out, err = self.main("resume", run_id)
        self.assertEqual(code, 0, out + err)
        self.assertEqual(
            self.last_line(out),
            f"PR completion: draft #7 {PR_URL}: a block was resolved during the "
            "run (HD-0001)",
        )
        self.draft(run_id, ("block-resolved", ""))
        api = [c for c in self.gh_calls() if c == ["api", "repos/acme/demo/pulls/7"]]
        self.assertGreaterEqual(len(api), 1)

    def test_checkpoint_after_ready_reuses_the_pr(self) -> None:
        """AC-003: no second `pr ready`, and the PR stays ready for review."""
        code, out, err, run_id = self._eligible_run()
        self.assertEqual(code, 0, out + err)
        code, out, err = self.main("checkpoint", run_id)
        self.assertEqual(code, 0, out + err)
        self.assertEqual(out.splitlines()[0], f"Draft PR: reused #7 {PR_URL}")
        self.assertNotIn("PR completion:", out)
        self.assertEqual(len(self.pr_ready_calls()), 1)
        self.assertFalse(self.served()["draft"])
        self.assertEqual(len(self.completions(run_id)), 1)

    def test_publish_of_the_published_run_refuses_without_a_forge_call(self) -> None:
        """AC-003, research R11: a published run has no publish retry."""
        code, out, err, run_id = self._eligible_run()
        self.assertEqual(code, 0, out + err)
        before = len(self.gh_calls())
        code, _, err = self.main("publish", run_id)
        self.assertEqual(code, 2, err)
        self.assertIn(f"run {run_id} is published", err)
        self.assertEqual(len(self.gh_calls()), before)

    def failed_publication(self) -> str:
        """Start an eligible run whose `gh pr create` fails, then allow it."""
        (self.gh_dir / "FAIL_pr_create").write_text("HTTP 502: Bad Gateway\n")
        code, out, err, run_id = self._eligible_run(None)
        self.assertEqual(code, 1, out + err)
        self.assertEqual(autonomy.read_block(self.root, run_id)["category"], "forge")
        self.assertNotIn("PR completion:", out)
        (self.gh_dir / "FAIL_pr_create").unlink()
        return run_id

    def test_publish_retry_of_a_reported_run_runs_the_packet_then_completes(
        self,
    ) -> None:
        """FR-007, research R2: the retry is a publication that evaluates."""
        self.configure(READY)
        run_id = self.failed_publication()
        code, out, err = self.main("publish", run_id)
        self.assertEqual(code, 0, out + err)
        lines = out.splitlines()
        self.assertEqual(lines[0], f"Draft PR: {PR_URL}")
        self.assertEqual(lines[2], f"Draft PR: reused #7 {PR_URL}")
        self.assertTrue(lines[3].startswith("Acceptance packet: published #7"))
        self.assertEqual(lines[4:], [READY_LINE])
        self.assertEqual(len(self.pr_ready_calls()), 1)
        self.assertEqual(self.completions(run_id)[0]["outcome"], "ready")

    def test_publish_retry_without_the_opt_in_is_unchanged(self) -> None:
        """FR-013: no checkpoint, no packet and no completion on the retry."""
        run_id = self.failed_publication()
        code, out, err = self.main("publish", run_id)
        self.assertEqual(code, 0, out + err)
        self.assertEqual(
            out.splitlines(),
            [
                f"Draft PR: {PR_URL}",
                (
                    "Every intermediate decision is agent-provisional; merging the "
                    "PR is the only human approval."
                ),
            ],
        )
        self.assertEqual(self.pr_ready_calls(), [])
        self.assertEqual(self.completions(run_id), [])


class CompletionDraftTests(CompletionCase):
    """T015 [AC-004, AC-005, AC-007, AC-008]: ineligible runs stay a Draft."""

    def test_r2_stays_a_draft(self) -> None:
        def raised(run_id: str) -> None:
            record = autonomy.read_run(self.root, run_id)
            autonomy.raise_risk(record, "R2", ["trust model"], "PD-0001")
            autonomy.write_run(self.root, record)

        self.changes.append(raised)
        code, out, err, run_id = self._eligible_run()
        self.assertEqual(code, 0, out + err)
        line = f"PR completion: draft #7 {PR_URL}: risk R2"
        self.assertEqual(self.last_line(out), line)
        self.draft(run_id, ("risk", "risk R2"))

    def test_no_final_acceptance_stays_a_draft(self) -> None:
        self.final = False
        code, out, err, run_id = self._eligible_run()
        self.assertEqual(code, 0, out + err)
        self.assertEqual(
            self.last_line(out),
            f"PR completion: draft #7 {PR_URL}: no final acceptance recorded",
        )
        self.draft(run_id, ("no-final-acceptance", ""))

    def test_moved_head_stays_a_draft(self) -> None:
        (self.gh_dir / "head-sha").write_text("1" * 40)
        code, out, err, run_id = self._eligible_run()
        self.assertEqual(code, 0, out + err)
        self.assertEqual(
            self.last_line(out),
            f"PR completion: draft #7 {PR_URL}: the PR head is not the published "
            "commit",
        )
        self.draft(run_id, ("head-moved", ""))

    def test_forge_refusal_keeps_the_runs_result(self) -> None:
        """AC-008, FR-011: same exit, status and no block as a ready run."""
        (self.gh_dir / "FAIL_pr_ready").write_text("HTTP 403: Forbidden\n")
        code, out, err, run_id = self._eligible_run()
        self.assertEqual(code, 0, out + err)
        self.assertEqual(
            self.last_line(out),
            f"PR completion: draft #7 {PR_URL}: marking ready failed (gh-forbidden)",
        )
        self.assertNotIn("Forbidden", out)
        self.assertEqual(
            self.pr_ready_calls(), [["pr", "ready", "7", "--repo", "acme/demo"]]
        )
        (event,) = self.completions(run_id)
        self.assertEqual(
            (event["outcome"], event["reasons"], event["cause"]),
            ("draft", ["forge-failed"], "gh-forbidden"),
        )
        self.assertEqual(autonomy.read_run(self.root, run_id)["status"], "published")
        self.assertIsNone(autonomy.read_block(self.root, run_id))
        self.assertTrue(self.served()["draft"])

    def test_forge_applied_a_failed_request_is_ready(self) -> None:
        """F-02: a failed `pr ready` the read-back shows applied is `ready`."""
        (self.gh_dir / "ready-then-fail").write_text("")
        code, out, err, run_id = self._eligible_run()
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.last_line(out), READY_LINE)
        (event,) = self.completions(run_id)
        self.assertEqual(event["outcome"], "ready")
        self.assertEqual(autonomy.read_run(self.root, run_id)["status"], "published")
        self.assertFalse(self.served()["draft"])

    def test_skipped_checkpoint_reports_the_missing_packet(self) -> None:
        """F-03, FR-009: a skipped checkpoint leaves no packet; the Draft says so."""
        skipped = run.draft_pr.Outcome("skipped", remedy="marker exists; restore it")
        with patch.object(run.draft_pr, "checkpoint", return_value=skipped):
            code, out, err, run_id = self._eligible_run()
        self.assertEqual(code, 0, out + err)
        self.assertEqual(
            self.last_line(out),
            f"PR completion: draft #7 {PR_URL}: acceptance packet not published",
        )
        self.draft(run_id, ("packet", ""))


class CompletionUnconfiguredTests(CompletionCase):
    """T016, T017 [AC-010, AC-011, AC-012, SC-003, FR-014]: no opt-in, no change."""

    def observed(self, table: str | None) -> tuple[list[str], list[tuple], dict]:
        """Return one eligible run's normalized stdout and ledger, and its policy."""
        code, out, err, run_id = self._eligible_run(table)
        self.assertEqual(code, 0, out + err)
        events, _ = run.draft_pr.ledger.read(self.root, run_id)

        def normal(text: str) -> str:
            return HEX.sub("X", text.replace(run_id, "RUN"))

        lines = [normal(line) for line in out.splitlines()]
        kinds = [
            (e["kind"], normal(json.dumps(e["data"], sort_keys=True))) for e in events
        ]
        return lines, kinds, self.snapshot(run_id)

    def elsewhere(self, table: str | None) -> tuple[list[str], list[tuple], dict]:
        """Run `observed` in a fresh checkout, operator state and fake GitHub."""
        case = type(self)(self._testMethodName)
        case.setUp()
        try:
            return case.observed(table)
        finally:
            case.tearDown()
            case.doCleanups()

    def nothing_new(self, lines: list[str], kinds: list[tuple]) -> None:
        self.assertFalse([line for line in lines if line.startswith("PR completion")])
        self.assertNotIn("pr_completion", [kind for kind, _ in kinds])
        self.assertEqual(self.pr_ready_calls(), [])

    def test_no_table_or_no_key_adds_nothing(self) -> None:
        """AC-010, SC-003: the same output and ledger with or without a table."""
        lines, kinds, policy = self.observed(None)
        self.nothing_new(lines, kinds)
        other = self.elsewhere('[autonomous]\nrisk = ["R0", "R1", "R2"]\n')
        self.assertEqual((lines, kinds), other[:2])
        new = {
            "completion_configured",
            "completion_max_severity",
            "completion_flag",
            "completion",
        }
        for snapshot in (policy, other[2]):
            self.assertFalse(new & set(snapshot), snapshot)

    def test_draft_is_the_same_as_no_configuration(self) -> None:
        """AC-011: `completion = "draft"` prints and records what none does."""
        lines, kinds, policy = self.observed(DRAFT)
        self.nothing_new(lines, kinds)
        self.assertEqual((lines, kinds), self.elsewhere(None)[:2])
        self.assertEqual(
            (policy["completion_configured"], policy["completion"]), ("draft", "draft")
        )

    def test_unknown_completion_value_is_no_configuration(self) -> None:
        """FR-002: a warning at start, then the run behaves as `draft`."""
        self.configure('[autonomous]\ncompletion = "Ready"\n')
        self.engine["scenario"] = self.eligible
        code, out, err = self.start()
        self.assertEqual(code, 0, out + err)
        self.assertIn(
            "ballast: ignored [autonomous] completion 'Ready': cannot widen "
            "eligibility",
            err,
        )
        run_id = self.launched[-1][1]
        self.nothing_new(out.splitlines(), [])
        self.assertEqual(self.completions(run_id), [])
        self.assertEqual(self.snapshot(run_id)["completion"], "draft")

    def test_unknown_severity_keeps_the_low_threshold(self) -> None:
        """FR-006: a warning, and the threshold stays `low`."""
        code, out, err, run_id = self._eligible_run(
            READY + 'completion_max_severity = "medium"\n'
        )
        self.assertEqual(code, 0, out + err)
        self.assertIn(
            "ignored [autonomous] completion_max_severity 'medium': cannot widen "
            "eligibility",
            err,
        )
        self.assertEqual(self.snapshot(run_id)["completion_max_severity"], "low")
        self.assertEqual(self.last_line(out), READY_LINE)

    def test_chat_publication_never_marks_ready(self) -> None:
        """AC-012: a Chat run's publish never reaches the completion step."""
        self.configure(READY)
        with (
            patch.object(run, "_chat_run", return_value=True),
            patch.object(run.chat, "publish", return_value=0) as publish,
            patch.object(run.completion, "complete") as complete,
        ):
            code, out, err = self.main("publish", "chat01")
        self.assertEqual(code, 0, out + err)
        publish.assert_called_once()
        complete.assert_not_called()
        self.assertNotIn("PR completion:", out)
        self.assertEqual(self.pr_ready_calls(), [])

    def test_human_gated_run_never_marks_ready(self) -> None:
        """AC-012, FR-014: the checkpoint runs; nothing marks the PR ready."""
        self.configure(READY)
        with patch.object(run.completion, "complete") as complete:
            code, out, err = self.main(
                "start",
                "-i",
                "idea=Issue #27: demo",
                "-i",
                f"feature_directory={FEATURE}",
            )
        self.assertEqual(code, 0, out + err)
        complete.assert_not_called()
        self.assertIn("Draft PR:", out)
        self.assertNotIn("PR completion:", out)
        self.assertEqual(self.pr_ready_calls(), [])

    def test_lowered_run_never_marks_ready(self) -> None:
        """AC-012: an Autonomous run continued human-gated before publication."""
        self.configure(READY)
        run_id = RunContinueTests.stopped_run(self)
        with patch.object(run.completion, "complete") as complete:
            code, out, err = self.main(
                "continue", run_id, "--reason", "block-resolved", "--ref", "chose Keep"
            )
        self.assertEqual(code, 0, out + err)
        complete.assert_not_called()
        self.assertNotIn("PR completion:", out)
        self.assertEqual(self.pr_ready_calls(), [])

    def test_checkpoint_never_marks_ready(self) -> None:
        """FR-007: a checkpoint of an eligible, reported run leaves the Draft."""
        (self.gh_dir / "FAIL_pr_ready").write_text("HTTP 502: Bad Gateway\n")
        code, out, err, run_id = self._eligible_run()
        self.assertEqual(code, 0, out + err)
        (self.gh_dir / "FAIL_pr_ready").unlink()
        attempts = len(self.pr_ready_calls())
        code, out, err = self.main("checkpoint", run_id)
        self.assertEqual(code, 0, out + err)
        self.assertNotIn("PR completion:", out)
        self.assertEqual(len(self.pr_ready_calls()), attempts)
        self.assertTrue(self.served()["draft"])
        self.assertEqual(len(self.completions(run_id)), 1)


class CompletionFlagTests(CompletionCase):
    """T019, T020, T021 [AC-013 to AC-018, SC-004]: only the operator decides."""

    def test_flag_cannot_widen_ballast_toml(self) -> None:
        """AC-015: refused before any record, Issue read or agent step."""
        for table, configured in (("", "draft"), (DRAFT, "draft")):
            with self.subTest(table=table):
                self.configure(table)
                code, _, err = self.start("--completion", "ready")
                self.assertEqual(code, 2, err)
                self.assertIn(
                    "--completion ready cannot widen ballast.toml [autonomous] "
                    f"completion ({configured})",
                    err,
                )
                self.assertEqual(self.run_ids(), [])
                self.assertEqual(self.launched, [])
                self.assertEqual(self.gh_calls(), [])

    def test_flag_narrows_a_ready_policy(self) -> None:
        """AC-016: the snapshot records it, and the reason names the flag."""
        code, out, err, run_id = self._eligible_run(READY, "--completion", "draft")
        self.assertEqual(code, 0, out + err)
        policy = self.snapshot(run_id)
        self.assertEqual(
            (
                policy["completion_configured"],
                policy["completion_flag"],
                policy["completion"],
            ),
            ("ready", "draft", "draft"),
        )
        self.assertEqual(
            self.last_line(out),
            f"PR completion: draft #7 {PR_URL}: the run's start flag chose draft",
        )
        self.draft(run_id, ("policy-draft", ""))

    def test_flag_refusals(self) -> None:
        feature = f"feature_directory={FEATURE}"
        for argv, text in (
            (
                ("start", "--mode", "chat", "--completion", "draft", "-i", feature),
                "--completion needs --mode autonomous",
            ),
            (
                ("start", "--completion", "ready", "-i", "idea=x", "-i", feature),
                "--completion needs --mode autonomous",
            ),
            (
                ("start", "--mode", "autonomous", "--completion", "merge"),
                "--completion must be draft or ready",
            ),
            (
                (
                    "start",
                    "--mode",
                    "autonomous",
                    "--completion",
                    "draft",
                    "--completion=draft",
                ),
                "--completion given twice",
            ),
        ):
            with self.subTest(argv=argv):
                code, _, err = self.main(*argv)
                self.assertEqual(code, 2, err)
                self.assertIn(text, err)
        self.assertEqual(self.launched, [])

    def test_resume_and_continue_refuse_the_flag(self) -> None:
        run_id = self.blocked_run()
        code, _, err = self.main("resume", run_id, "--completion", "draft")
        self.assertEqual(code, 2, err)
        self.assertIn("recorded at start; it accepts only --ref TEXT", err)
        code, _, err = self.main(
            "continue",
            run_id,
            "--reason",
            "block-resolved",
            "--ref",
            "x",
            "--completion",
            "draft",
        )
        self.assertEqual(code, 2, err)
        self.assertIn("continue accepts only", err)
        self.assertEqual(len(self.launched), 1)

    def refreshed(self, *extra: str) -> tuple[str, str]:
        """Block under `draft`, then opt in, trust and resume with a refresh."""
        self.configure(DRAFT)
        run_id = self.blocked_run(*extra)
        self.configure(READY)
        self.trust()
        code, out, err = self.main("resume", run_id, "--refresh-policy")
        self.assertEqual(code, 0, out + err)
        return run_id, out

    def test_refresh_keeps_the_start_flag(self) -> None:
        """AC-018: a flag-narrowed run stays `draft` after the refresh."""
        run_id, out = self.refreshed("--completion", "draft")
        policy = self.snapshot(run_id)
        self.assertEqual(
            (
                policy["completion_configured"],
                policy["completion_flag"],
                policy["completion"],
            ),
            ("ready", "draft", "draft"),
        )
        self.assertEqual(
            self.last_line(out),
            f"PR completion: draft #7 {PR_URL}: the run's start flag chose draft; "
            "a block was resolved during the run (HD-0001)",
        )
        self.draft(run_id, ("policy-draft", ""), ("block-resolved", ""))

    def test_refresh_applies_the_new_opt_in_without_a_flag(self) -> None:
        """AC-018: the refreshed value applies; condition (11) keeps the Draft."""
        run_id, out = self.refreshed()
        policy = self.snapshot(run_id)
        self.assertNotIn("completion_flag", policy)
        self.assertEqual(
            (policy["completion_configured"], policy["completion"]), ("ready", "ready")
        )
        self.assertEqual(
            self.last_line(out),
            f"PR completion: draft #7 {PR_URL}: a block was resolved during the "
            "run (HD-0001)",
        )
        self.draft(run_id, ("block-resolved", ""))

    def test_checkout_ballast_toml_never_changes_the_policy(self) -> None:
        """AC-013, SC-004: an agent's `ready` copy is not the start snapshot."""

        def rewrite(_: str) -> None:
            (self.root / "ballast.toml").write_text(BASE_TOML + READY)

        self.changes.append(rewrite)
        code, out, err, run_id = self._eligible_run(DRAFT)
        # The changed protected input stops the run before publication.
        self.assertEqual(code, 1, out + err)
        block = autonomy.read_block(self.root, run_id)
        self.assertEqual(block["category"], "postcondition")
        self.assertIn("ballast.toml", block["condition"])
        self.assertEqual(self.snapshot(run_id)["completion_configured"], "draft")
        self.assertEqual(self.snapshot(run_id)["completion"], "draft")
        self.assertNotIn("PR completion:", out)
        self.assertEqual(self.pr_ready_calls(), [])
        self.assertEqual(self.completions(run_id), [])

    def test_agent_claims_never_change_the_result(self) -> None:
        """AC-014, SC-004: only operator records count, never agent artifacts."""

        def raised(run_id: str) -> None:
            record = autonomy.read_run(self.root, run_id)
            autonomy.raise_risk(record, "R2", ["trust model"], "PD-0001")
            autonomy.write_run(self.root, record)

        def claims(run_id: str) -> None:
            # A step's decision drafts, as the wrapper keeps them, never recorded.
            for point in ("spec-reconciliation", "final-acceptance"):
                draft = autonomy.snapshot_draft(
                    self.root, run_id, "step01", f"{point}.json"
                )
                draft.parent.mkdir(parents=True, exist_ok=True)
                draft.write_text(
                    json.dumps(
                        {
                            "point": point,
                            "decision": "accept",
                            "summary": "Converged; every criterion verified.",
                            "review": {"verdict": "approved", "findings": []},
                        }
                    )
                )
            reviews = self.root / FEATURE / "reviews"
            reviews.mkdir(parents=True, exist_ok=True)
            (reviews / "convergence.md").write_text("- Verdict: CONVERGED\n")
            (self.root / FEATURE / "decisions.md").write_text(
                "Final acceptance: accepted. Risk: R0. All checks passed.\n"
            )
            (self.root / FEATURE / "acceptance-evidence.json").write_text(
                json.dumps({"verified": ["AC-001"], "checks": "passed"})
            )

        self.final = False
        self.verdict = "changes-requested"
        self.before.append(claims)
        self.changes.append(raised)
        code, out, err, run_id = self._eligible_run()
        self.assertEqual(code, 0, out + err)
        self.assertEqual(
            self.last_line(out),
            f"PR completion: draft #7 {PR_URL}: risk R2; no final acceptance "
            "recorded; spec reconciliation is not recorded as approved and converged",
        )
        # The same reasons as the run without any agent write.
        self.draft(
            run_id, ("risk", ""), ("no-final-acceptance", ""), ("not-converged", "")
        )


if __name__ == "__main__":
    unittest.main()
