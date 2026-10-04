"""Regression tests for ballast-feature workflow postconditions.

No test calls a real model: validators run as subprocesses against temporary
repositories, the agent wrapper runs a fake CLI, and the optional engine test
drives Spec Kit with a fake integration executable.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import pty
import select
import shutil
import signal
import subprocess
import sys
import time
import unittest
from contextlib import redirect_stderr, redirect_stdout, suppress
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock, patch

import yaml

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "tools/spec_workflow/artifacts.py"
WORKFLOW = ROOT / "templates/spec-kit/workflows/feature/workflow.yml"
FEATURE = "specs/102-demo-import"

SPEC = """# Feature Specification: Demo import

**Created**: 2026-09-26

## User Scenarios

### User Story 1 - Import a fictional transcript (Priority: P1)

A GM imports the transcript of the fictional "Ashen Vale" session.

1. **Given** a text transcript, **When** it is imported, **Then** evidence is
   listed for review. [AC-001]
"""
PLAN = """# Implementation Plan: Demo import

**Spec**: [spec.md](spec.md)

## Summary

Store imported transcript evidence behind the session ingestion boundary.
"""
TASKS = """# Tasks: Demo import

- [ ] T001 Add import test for [AC-001] in tests/test_import.py
- [ ] T002 Implement import in src/demo/import.py (depends on T001)
"""


def _tree(root: Path) -> dict[str, str]:
    """Every path under root with its content, to prove a command wrote nothing."""
    return {
        str(path.relative_to(root)): "dir" if path.is_dir() else path.read_bytes().hex()
        for path in sorted(root.rglob("*"))
    }


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)  # noqa: S603, S607


class Repository:
    """A temporary Git repository shaped like a project checkout."""

    def __init__(self, directory: str) -> None:
        """Create the checkout with one empty feature directory."""
        self.root = Path(directory)
        (self.root / ".specify").mkdir()
        (self.root / ".gitignore").write_text(".specify/workflow-state/\n")
        (self.root / FEATURE).mkdir(parents=True)
        _git(self.root, "init", "-q")
        _git(
            self.root,
            "-c",
            "user.name=t",
            "-c",
            "user.email=t@example.test",
            "commit",
            "-q",
            "--allow-empty",
            "-m",
            "base",
        )

    def write(self, name: str, text: str) -> Path:
        path = self.root / FEATURE / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path

    def check(
        self, check: str, *target: str, env: dict[str, str] | None = None
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(  # noqa: S603
            [
                sys.executable,
                str(ARTIFACTS),
                check,
                *(target or ("--feature", FEATURE)),
            ],
            cwd=self.root,
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )

    def approve(self) -> None:
        self.write("spec.md", SPEC)
        result = self.check("record-intent")
        if result.returncode != 0:
            raise AssertionError(result.stderr)


class ArtifactContractTests(unittest.TestCase):
    """Each producer phase needs a valid artifact, not an exit code."""

    def setUp(self) -> None:
        self.directory = TemporaryDirectory()
        self.repo = Repository(self.directory.name)

    def tearDown(self) -> None:
        self.directory.cleanup()

    def assertFails(self, check: str, reason: str) -> None:  # noqa: N802
        result = self.repo.check(check)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn(reason, result.stderr)

    def assertPasses(self, check: str) -> None:  # noqa: N802
        result = self.repo.check(check)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_missing_artifact_fails_even_after_successful_command(self) -> None:
        self.assertFails("spec", "spec.md is missing")
        self.repo.write("spec.md", " \n")
        self.assertFails("spec", "spec.md is empty")

    def test_untouched_templates_fail(self) -> None:
        templates = ROOT / "templates/spec-kit/templates"
        self.repo.write("spec.md", (templates / "spec-template.md").read_text())
        self.assertFails("spec", "template placeholders")
        self.repo.approve()
        self.repo.write("plan.md", (templates / "plan-template.md").read_text())
        self.assertFails("plan", "# Implementation Plan: [FEATURE]")
        self.repo.write("plan.md", PLAN)
        self.repo.write("tasks.md", (templates / "tasks-template.md").read_text())
        self.assertFails("tasks", "template placeholders")

    def test_ordinary_brackets_are_allowed(self) -> None:
        self.repo.write(
            "spec.md", SPEC + "\nSee [the glossary](../../CONTEXT.md) [AC-002].\n"
        )
        self.assertPasses("spec")

    def test_unresolved_clarification_blocks_intent_approval(self) -> None:
        self.repo.write(
            "spec.md", SPEC + "\n- FR-001: [NEEDS CLARIFICATION: format?]\n"
        )
        self.assertPasses("spec")
        self.assertFails("clarified-spec", "NEEDS CLARIFICATION")
        self.assertFails("record-intent", "NEEDS CLARIFICATION")
        self.assertFalse((self.repo.root / FEATURE / "intent.md").exists())

    def test_missing_intent_approval_blocks_planning(self) -> None:
        self.repo.write("spec.md", SPEC)
        self.repo.write("plan.md", PLAN)
        self.assertFails("intent", "intent.md is missing")
        self.assertFails("plan", "intent.md is missing")
        self.repo.write(
            "intent.md", "# Feature Intent\n\n## Outcome\n\nDrafted by an agent.\n"
        )
        self.assertFails("plan", "lacks sections")

    def test_missing_tasks_blocks_task_review(self) -> None:
        self.repo.approve()
        self.repo.write("plan.md", PLAN)
        self.assertFails("tasks", "tasks.md is missing")
        self.repo.write("tasks.md", "# Tasks: Demo import\n\nNothing yet.\n")
        self.assertFails("tasks", "no task lines")

    def test_task_dependencies_must_exist(self) -> None:
        self.repo.approve()
        self.repo.write("plan.md", PLAN)
        self.repo.write("tasks.md", TASKS.replace("depends on T001", "depends on T009"))
        self.assertFails("tasks", "T002 depends on unknown task(s) T009")
        self.repo.write("tasks.md", TASKS + "- [ ] T001 Duplicate\n")
        self.assertFails("tasks", "defines T001 more than once")

    def test_valid_artifacts_pass(self) -> None:
        self.repo.approve()
        self.repo.write("plan.md", PLAN)
        self.repo.write("tasks.md", TASKS)
        for check in ("spec", "clarified-spec", "intent", "plan", "tasks"):
            self.assertPasses(check)
        intent = (self.repo.root / FEATURE / "intent.md").read_text()
        self.assertIn(f"- **Spec**: {FEATURE}/spec.md", intent)
        self.assertIn("## Authority", intent)

    def test_spec_change_after_approval_is_stale(self) -> None:
        self.repo.approve()
        self.repo.write("plan.md", PLAN)
        self.repo.write("spec.md", SPEC.replace("\n", "  \r\n"))
        self.assertPasses("plan")
        self.repo.write("spec.md", SPEC + "\n- FR-002: Import audio too.\n")
        self.assertFails("intent", "approval is stale")
        self.assertFails("plan", "approval is stale")
        self.repo.approve()
        self.assertPasses("intent")

    def test_record_intent_preserves_human_sections(self) -> None:
        self.repo.write("spec.md", SPEC)
        human = (
            "# Feature Intent: Demo\n\n## Outcome\n\nHuman words.\n\n"
            + "\n\n".join(
                f"## {name}\n\n- x"
                for name in (
                    "Constraints",
                    "Non-goals",
                    "Success evidence",
                    "Authority",
                )
            )
        )
        self.repo.write("intent.md", human)
        self.repo.approve()
        self.repo.approve()
        intent = (self.repo.root / FEATURE / "intent.md").read_text()
        self.assertIn("Human words.", intent)
        self.assertEqual(intent.count("workflow-approval: begin"), 1)

    def test_implementation_needs_completed_tasks_and_a_change(self) -> None:
        self.repo.approve()
        self.repo.write("plan.md", PLAN)
        self.repo.write("tasks.md", TASKS)
        self.assertPasses("implementation-baseline")
        self.assertFails("implementation", "pending tasks: T001, T002")
        self.repo.write("tasks.md", TASKS.replace("- [ ]", "- [X]"))
        self.assertFails("implementation", "changed nothing outside the feature")
        (self.repo.root / "docs").mkdir()
        (self.repo.root / "docs/import.md").write_text("Import guide.\n")
        self.assertPasses("implementation")
        state = self.repo.root / ".specify/workflow-state/feature-102-demo-import"
        (state / "implementation-baseline.json").unlink()
        self.assertFails("implementation", "no implementation baseline")

    def test_forged_baseline_cannot_inject_git_options(self) -> None:
        self.repo.approve()
        self.repo.write("plan.md", PLAN)
        self.repo.write("tasks.md", TASKS.replace("- [ ]", "- [X]"))
        target = self.repo.root / "outside.txt"
        state = self.repo.root / ".specify/workflow-state/feature-102-demo-import"
        state.mkdir(parents=True)
        for forged in (
            {"feature": FEATURE, "tree": f"--output={target}"},
            ["not", "an", "object"],
        ):
            (state / "implementation-baseline.json").write_text(json.dumps(forged))
            self.assertFails("implementation", "no valid tree id")
        (state / "implementation-baseline.json").write_text("{broken")
        self.assertFails("implementation", "not valid JSON")
        self.assertFalse(target.exists())

    def test_declared_no_code_change_is_explicit(self) -> None:
        self.repo.approve()
        self.repo.write("plan.md", PLAN)
        self.repo.write("tasks.md", TASKS)
        self.assertPasses("implementation-baseline")
        done = TASKS.replace("- [ ]", "- [x]")
        self.repo.write("tasks.md", done + "\n<!-- workflow: no-code-change -->\n")
        self.assertPasses("implementation")

    def test_unresolved_decisions_and_convergence(self) -> None:
        self.repo.approve()
        self.repo.write("plan.md", PLAN)
        self.repo.write("tasks.md", TASKS.replace("- [ ]", "- [X]"))
        proposal = "# Ledger\n\n## DEC-0001 — Proposal\n\n- **Status**: proposed\n"
        self.repo.write("decisions.md", proposal)
        self.assertFails("decisions", "unresolved decisions: DEC-0001")
        self.repo.write(
            "decisions.md",
            proposal + "\n## DEC-0001 - Resolution\n\n- **Decision**: accepted\n",
        )
        self.assertPasses("decisions")
        self.assertFails("convergence", "convergence.md is missing")
        self.repo.write("reviews/convergence.md", "# Review\n\n- Verdict: PARTIAL\n")
        self.assertFails("convergence", "latest verdict is PARTIAL")
        self.repo.write("reviews/convergence.md", "# Review\n\n- Verdict: CONVERGED\n")
        self.assertPasses("convergence")
        self.repo.write(
            "tasks.md", TASKS.replace("- [ ]", "- [X]") + "- [ ] T003 Converge gap\n"
        )
        self.assertFails("convergence", "pending tasks: T003")


class FeaturePathTests(unittest.TestCase):
    """Workflow inputs cannot point validators outside the feature."""

    def setUp(self) -> None:
        self.directory = TemporaryDirectory()
        self.repo = Repository(self.directory.name)

    def tearDown(self) -> None:
        self.directory.cleanup()

    def test_rejects_unsafe_feature_paths(self) -> None:
        for value in (
            "../outside",
            "/etc",
            "specs/../../x",
            "specs/-slug",
            "specs/102-a/b",
            "specs/102-A",
        ):
            result = self.repo.check("spec", "--feature", value)
            self.assertNotEqual(result.returncode, 0, value)
            self.assertIn("must match specs/<issue-number>-<slug>", result.stderr)

    def test_rejects_symlink_escape(self) -> None:
        with TemporaryDirectory() as outside:
            (Path(outside) / "spec.md").write_text(SPEC)
            (self.repo.root / "specs/103-link").symlink_to(outside)
            result = self.repo.check("spec", "--feature", "specs/103-link")
            self.assertIn("real directory directly under specs/", result.stderr)
            shutil.rmtree(self.repo.root / FEATURE)
            (self.repo.root / FEATURE).mkdir()
            (self.repo.root / FEATURE / "spec.md").symlink_to(Path(outside) / "spec.md")
            self.assertIn("must not be a symlink", self.repo.check("spec").stderr)

    def test_reads_feature_from_run_inputs(self) -> None:
        run = self.repo.root / ".specify/workflows/runs/abc123"
        run.mkdir(parents=True)
        (run / "inputs.json").write_text(
            json.dumps({"inputs": {"feature_directory": FEATURE}})
        )
        self.repo.write("spec.md", SPEC)
        self.assertEqual(self.repo.check("spec", "--run", "abc123").returncode, 0)
        self.assertIn("invalid run id", self.repo.check("spec", "--run", "a;b").stderr)
        (run / "inputs.json").write_text(
            json.dumps({"inputs": {"feature_directory": "$(id)"}})
        )
        self.assertIn("must match", self.repo.check("spec", "--run", "abc123").stderr)

    def test_preflight_requires_launcher(self) -> None:
        env = {
            key: value
            for key, value in os.environ.items()
            if key != "BALLAST_SPEC_WORKFLOW"
        }
        self.assertIn(
            ".ballast/spec_workflow/run", self.repo.check("preflight", env=env).stderr
        )
        passing = self.repo.check(
            "preflight", env={**env, "BALLAST_SPEC_WORKFLOW": "1"}
        )
        self.assertEqual(passing.returncode, 0)


FAKE_CLI = """#!/usr/bin/env python3
import json, os, sys
SURVIVOR = (
    "import os, sys, time; os.fork() and sys.exit(); os.setsid(); "
    "open(sys.argv[1], 'w').write(str(os.getpid())); time.sleep(120)"
)
LATE_WRITE = (
    "import os, sys, time; os.fork() and sys.exit(); "
    "time.sleep(1); open(sys.argv[1], 'w').write('late')"
)
with open(os.environ["FAKE_ARGV"], "w") as handle:
    json.dump(sys.argv[1:], handle)
if os.environ.get("FAKE_TAMPER"):
    with open(os.environ["FAKE_TAMPER"], "w") as handle:
        handle.write('{"current_step_index": 99}')
if os.environ.get("FAKE_IGNORE_INTERRUPT"):
    import signal, time
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    open(os.environ["FAKE_IGNORE_INTERRUPT"], "w").close()
    time.sleep(60)
if os.environ.get("FAKE_SURVIVOR"):
    import subprocess
    subprocess.Popen(
        [sys.executable, "-c", SURVIVOR, os.environ["FAKE_SURVIVOR"]],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
if os.environ.get("FAKE_KILL_WRAPPER"):
    import signal
    os.kill(os.getppid(), signal.SIGKILL)
if os.environ.get("FAKE_SWAP_LOG"):
    import glob
    (log,) = glob.glob(".specify/workflow-state/*/agents/*")
    os.rename(log, log + ".moved")
    os.symlink(os.environ["FAKE_SWAP_LOG"], log)
if os.environ.get("FAKE_IMPORT"):
    sys.path.insert(0, os.environ["FAKE_IMPORT"])
    import fake_module
    print("imported fake_module", fake_module.VALUE)
if os.environ.get("FAKE_LATE_WRITE"):
    import subprocess
    # Detached from the session and the wrapper's pipes, then double-forked
    # so the writer is an orphan: nothing waits for it.
    subprocess.Popen(
        [sys.executable, "-c", LATE_WRITE, os.environ["FAKE_LATE_WRITE"]],
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
print(os.environ.get("FAKE_STDOUT", "done"))
print("progress", file=sys.stderr)
"""


FAKE_SYSTEMD_RUN = """#!/usr/bin/env python3
# systemd >= 254 by default; FAKE_SYSTEMD_PRE_254 models an older one.
import os, sys
old = os.environ.get("FAKE_SYSTEMD_PRE_254")
args = sys.argv[1:]
if args == ["--help"]:
    print("--scope" if old else "--scope\\n--expand-environment=BOOL")
    sys.exit(0)
options = args[: args.index("--")]
command = args[args.index("--") + 1 :]
if old and any(o.startswith("--expand-environment") for o in options):
    sys.exit("systemd-run: unrecognized option")
if not old and "--expand-environment=no" not in options:
    command = ["" if "$" in word else word for word in command]
os.execvp(command[0], command)
"""
FAKE_SYSTEMCTL = """#!/usr/bin/env python3
import os, sys
if os.environ.get("FAKE_SYSTEMCTL_LOG"):
    with open(os.environ["FAKE_SYSTEMCTL_LOG"], "a") as log:
        log.write(" ".join(sys.argv[1:]) + "\\n")
if "is-active" in sys.argv:
    state = os.environ.get("FAKE_SCOPE_STATE", "inactive")
    print(state)
    sys.exit(0 if state == "active" else 3)
"""


def _fake_systemd(directory: Path) -> None:
    """Stand-ins that run the agent directly and report scopes as stopped."""
    for name, source in (
        ("systemd-run", FAKE_SYSTEMD_RUN),
        ("systemctl", FAKE_SYSTEMCTL),
    ):
        (directory / name).write_text(source)
        (directory / name).chmod(0o755)


def _user_systemd() -> bool:
    try:
        return (
            subprocess.run(
                ["systemctl", "--user", "show", "--property=Version"],  # noqa: S607
                capture_output=True,
                check=False,
            ).returncode
            == 0
        )
    except OSError:
        return False


class AgentWrapperTests(unittest.TestCase):
    """The wrapper bounds permissions, keeps logs, and surfaces blocking status."""

    def setUp(self) -> None:
        self.directory = TemporaryDirectory()
        self.root = Path(self.directory.name)
        fake = self.root / "fake-bin"
        fake.mkdir()
        for name in ("claude", "codex"):
            (fake / name).write_text(FAKE_CLI)
            (fake / name).chmod(0o755)
        _fake_systemd(fake)
        self.env = {
            **os.environ,
            "PATH": f"{fake}{os.pathsep}{os.environ['PATH']}",
            "FAKE_SYSTEMCTL_LOG": str(self.root / "systemctl.log"),
            "FAKE_ARGV": str(self.root / "argv.json"),
            "SPECKIT_WORKFLOW_RUN_ID": "run42",
            "XDG_STATE_HOME": str(self.root / "operator-state"),
        }

    def tearDown(self) -> None:
        self.directory.cleanup()

    def run_wrapper(
        self, name: str, *args: str, **env: str
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(  # noqa: S603
            [str(ROOT / "tools/spec_workflow/bin" / name), *args],
            cwd=self.root,
            env={**self.env, **env},
            capture_output=True,
            text=True,
            check=False,
        )

    def argv(self) -> list[str]:
        return json.loads((self.root / "argv.json").read_text())

    def test_claude_gets_bounded_permissions_and_tee_logs(self) -> None:
        result = self.run_wrapper("claude", "-p", "/speckit-plan")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "done")
        argv = self.argv()
        self.assertEqual(argv[:2], ["-p", "/speckit-plan"])
        self.assertIn("acceptEdits", argv)
        self.assertIn("--strict-mcp-config", argv)
        self.assertEqual(argv[argv.index("--setting-sources") + 1], "project")
        (log,) = (self.root / ".specify/workflow-state/run42/agents").iterdir()
        self.assertEqual((log / "stdout.log").read_text().strip(), "done")
        self.assertEqual((log / "stderr.log").read_text().strip(), "progress")
        meta = json.loads((log / "meta.json").read_text())
        self.assertEqual((meta["integration"], meta["exit_code"]), ("claude", 0))

    def test_codex_gets_workspace_write_sandbox(self) -> None:
        self.assertEqual(
            self.run_wrapper("codex", "exec", "$speckit-tasks").returncode, 0
        )
        self.assertEqual(
            self.argv(),
            [
                "exec",
                "--sandbox",
                "workspace-write",
                "--config",
                "sandbox_workspace_write.network_access=false",
                "$speckit-tasks",
            ],
        )

    def test_dollar_prompt_survives_systemd_without_expand_option(self) -> None:
        result = self.run_wrapper(
            "codex", "exec", "$speckit-tasks", FAKE_SYSTEMD_PRE_254="1"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.argv()[-1], "$speckit-tasks")

    def test_blocking_status_fails_the_step(self) -> None:
        result = self.run_wrapper(
            "claude",
            "-p",
            "/speckit-intent-implement",
            FAKE_STDOUT="RECONCILE_STATUS: BLOCKED_INTENT",
        )
        self.assertEqual(result.returncode, 3)
        self.assertIn("BLOCKED_INTENT", result.stderr)

    def test_tampering_with_run_state_fails_the_step(self) -> None:
        run = self.root / ".specify/workflows/runs/run42"
        run.mkdir(parents=True)
        (run / "state.json").write_text('{"current_step_index": 3}')
        result = self.run_wrapper(
            "claude", "-p", "/speckit-plan", FAKE_TAMPER=str(run / "state.json")
        )
        self.assertEqual(result.returncode, 4)
        self.assertIn(".specify/workflows/runs/run42/state.json", result.stderr)
        untouched = self.run_wrapper("claude", "-p", "/speckit-plan")
        self.assertEqual(untouched.returncode, 0, untouched.stderr)

    def test_editing_ballast_config_fails_the_step(self) -> None:
        config = self.root / "ballast.toml"
        config.write_text("[agents.permissions]\n")
        result = self.run_wrapper(
            "codex", "exec", "/speckit-plan", FAKE_TAMPER=str(config)
        )
        self.assertEqual(result.returncode, 4)
        self.assertIn("ballast.toml", result.stderr)

    def test_planted_bytecode_fails_the_step(self) -> None:
        cache = self.root / ".ballast/spec_workflow/__pycache__"
        cache.mkdir(parents=True)
        result = self.run_wrapper(
            "codex",
            "exec",
            "$speckit-plan",
            FAKE_TAMPER=str(cache / "artifacts.cpython-314.pyc"),
        )
        self.assertEqual(result.returncode, 4)
        self.assertIn("__pycache__/artifacts.cpython-314.pyc", result.stderr)
        marker = self.root / "BALLAST_TAMPERED"
        self.assertIn("artifacts.cpython-314.pyc", marker.read_text())

    def test_worktree_git_pointer_is_protected(self) -> None:
        (self.root / ".git").write_text("gitdir: /repo/.git/worktrees/x\n")
        result = self.run_wrapper(
            "codex", "exec", "$speckit-plan", FAKE_TAMPER=str(self.root / ".git")
        )
        self.assertEqual(result.returncode, 4)
        self.assertIn(".git", result.stderr)

    def test_another_runs_saved_workflow_is_protected(self) -> None:
        other = self.root / ".specify/workflows/runs/run7"
        other.mkdir(parents=True)
        (other / "workflow.yml").write_text("steps: []\n")
        result = self.run_wrapper(
            "codex",
            "exec",
            "$speckit-plan",
            FAKE_TAMPER=str(other / "workflow.yml"),
        )
        self.assertEqual(result.returncode, 4)
        self.assertIn(".specify/workflows/runs/run7/workflow.yml", result.stderr)

    def test_planted_marker_link_is_never_followed(self) -> None:
        state = self.root / ".specify/workflow-state"
        state.mkdir(parents=True)
        (self.root / ".venv").mkdir()
        outside = self.root / "outside.txt"
        outside.write_text("keep\n")
        (self.root / "BALLAST_TAMPERED").symlink_to(outside)
        result = self.run_wrapper(
            "codex",
            "exec",
            "$speckit-plan",
            FAKE_TAMPER=str(self.root / ".venv/hook.pth"),
        )
        self.assertEqual(result.returncode, 4)
        self.assertEqual(outside.read_text(), "keep\n")

    def test_agent_runs_in_a_scope_that_is_stopped_afterwards(self) -> None:
        result = self.run_wrapper("claude", "-p", "/speckit-plan")
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = (self.root / "systemctl.log").read_text()
        self.assertIn("--user kill --signal=SIGKILL ballast-agent-run42-", calls)
        self.assertIn("--user is-active ballast-agent-run42-", calls)

    def test_unconfirmed_scope_stop_fails_the_step(self) -> None:
        result = self.run_wrapper(
            "claude", "-p", "/speckit-plan", FAKE_SCOPE_STATE="active"
        )
        self.assertEqual(result.returncode, 4)
        self.assertIn("could not be stopped", result.stderr)

    def test_refuses_without_a_systemd_user_manager(self) -> None:
        (self.root / "fake-bin/systemd-run").unlink()
        python = self.root / "python-only"
        python.mkdir()
        (python / "python3").symlink_to(sys.executable)
        result = self.run_wrapper(
            "claude",
            "-p",
            "/speckit-plan",
            PATH=f"{self.root / 'fake-bin'}{os.pathsep}{python}",
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("systemd", result.stderr)

    def test_killed_wrapper_leaves_an_unfinished_step_behind(self) -> None:
        result = self.run_wrapper(
            "codex", "exec", "$speckit-plan", FAKE_KILL_WRAPPER="1"
        )
        self.assertEqual(result.returncode, -signal.SIGKILL)
        (state,) = (self.root / "operator-state/ballast").iterdir()
        self.assertTrue((state / "in-progress").exists())
        clean = self.run_wrapper("codex", "exec", "$speckit-plan")
        self.assertEqual(clean.returncode, 0, clean.stderr)
        self.assertFalse((state / "in-progress").exists())

    def test_swapped_log_directory_is_never_followed(self) -> None:
        outside = self.root / "outside"
        outside.mkdir()
        result = self.run_wrapper(
            "claude", "-p", "/speckit-plan", FAKE_SWAP_LOG=str(outside)
        )
        self.assertEqual(result.returncode, 4)
        self.assertEqual(list(outside.iterdir()), [])
        (moved,) = (self.root / ".specify/workflow-state/run42/agents").glob("*.moved")
        self.assertEqual((moved / "stdout.log").read_text().strip(), "done")
        self.assertIn('"exit_code": 4', (moved / "meta.json").read_text())

    def test_interrupt_still_stops_the_agent_and_checks(self) -> None:
        ready = self.root / "ready"
        state = self.root / ".specify/workflow-state"
        state.mkdir(parents=True)
        wrapper = subprocess.Popen(  # noqa: S603
            [str(ROOT / "tools/spec_workflow/bin/claude"), "-p", "/speckit-plan"],
            cwd=self.root,
            env={**self.env, "FAKE_IGNORE_INTERRUPT": str(ready)},
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        deadline = time.monotonic() + 10
        while not ready.exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        wrapper.send_signal(signal.SIGINT)
        wrapper.send_signal(signal.SIGINT)
        self.assertEqual(wrapper.wait(timeout=30), 130)
        (log,) = (state / "run42/agents").iterdir()
        meta = json.loads((log / "meta.json").read_text())
        self.assertEqual(meta["protected_changes"], [])

    def test_spec_kit_configuration_is_protected(self) -> None:
        specify = self.root / ".specify"
        (specify / "workflow-state").mkdir(parents=True)
        (specify / "extensions.yml").write_text("hooks: {}\n")
        result = self.run_wrapper(
            "codex",
            "exec",
            "$speckit-plan",
            FAKE_TAMPER=str(specify / "extensions.yml"),
        )
        self.assertEqual(result.returncode, 4)
        self.assertIn(".specify/extensions.yml", result.stderr)
        (self.root / "BALLAST_TAMPERED").unlink()
        feature = self.run_wrapper(
            "codex",
            "exec",
            "$speckit-specify",
            FAKE_TAMPER=str(specify / "feature.json"),
        )
        self.assertEqual(feature.returncode, 0, feature.stderr)

    def test_venv_startup_hook_fails_the_step(self) -> None:
        site = self.root / ".venv/lib/python3.14/site-packages"
        site.mkdir(parents=True)
        result = self.run_wrapper(
            "codex", "exec", "$speckit-plan", FAKE_TAMPER=str(site / "hook.pth")
        )
        self.assertEqual(result.returncode, 4)
        self.assertIn("site-packages/hook.pth", result.stderr)

    def test_agent_python_caches_stay_out_of_the_checkout(self) -> None:
        modules = self.root / ".ballast/spec_workflow"
        modules.mkdir(parents=True)
        (modules / "fake_module.py").write_text("VALUE = 1\n")
        result = self.run_wrapper(
            "claude", "-p", "/speckit-plan", FAKE_IMPORT=str(modules)
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((modules / "__pycache__").exists())
        self.assertIn("fake_module", result.stdout)

    def test_detached_child_cannot_write_after_the_agent_exits(self) -> None:
        run = self.root / ".specify/workflows/runs/run42"
        run.mkdir(parents=True)
        state = run / "state.json"
        state.write_text('{"current_step_index": 3}')
        result = subprocess.run(  # noqa: S603
            [str(ROOT / "tools/spec_workflow/bin/claude"), "-p", "/speckit-plan"],
            cwd=self.root,
            env={**self.env, "FAKE_LATE_WRITE": str(state)},
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        time.sleep(1.5)
        self.assertEqual(state.read_text(), '{"current_step_index": 3}')
        (log,) = (self.root / ".specify/workflow-state/run42/agents").iterdir()
        meta = json.loads((log / "meta.json").read_text())
        self.assertGreaterEqual(meta["stopped_descendants"], 1)

    def test_refuses_permission_bypass(self) -> None:
        for name, args in (
            ("claude", ("-p", "/speckit-plan", "--dangerously-skip-permissions")),
            (
                "claude",
                ("-p", "/speckit-plan", "--permission-mode", "bypassPermissions"),
            ),
            ("codex", ("exec", "$speckit-plan", "--sandbox=danger-full-access")),
            (
                "codex",
                (
                    "exec",
                    "$speckit-plan",
                    "-c",
                    "sandbox_workspace_write.network_access=true",
                ),
            ),
        ):
            result = self.run_wrapper(name, *args)
            self.assertEqual(result.returncode, 2, args)
            self.assertFalse((self.root / "argv.json").exists())


@unittest.skipUnless(_user_systemd(), "needs a systemd user manager")
class ScopeContainmentTests(unittest.TestCase):
    """With real systemd, agents get their arguments and recovery stops leftovers."""

    def setUp(self) -> None:
        self.directory = TemporaryDirectory()
        self.root = Path(self.directory.name)
        fake = self.root / "fake-bin"
        fake.mkdir()
        for name in ("claude", "codex"):
            (fake / name).write_text(FAKE_CLI)
            (fake / name).chmod(0o755)
        (self.root / ".ballast/spec_workflow").mkdir(parents=True)
        (self.root / ".ballast/spec_workflow/run.py").write_text("")
        self.pid_file = self.root / "survivor.pid"
        self.env = {
            **os.environ,
            "PATH": f"{fake}{os.pathsep}{os.environ['PATH']}",
            "FAKE_ARGV": str(self.root / "argv.json"),
            "FAKE_SURVIVOR": str(self.pid_file),
            "FAKE_KILL_WRAPPER": "1",
            "SPECKIT_WORKFLOW_RUN_ID": "run42",
            "XDG_STATE_HOME": str(self.root / "operator-state"),
        }

    def tearDown(self) -> None:
        if self.pid_file.exists():
            with suppress(ProcessLookupError):
                os.kill(int(self.pid_file.read_text()), signal.SIGKILL)
        self.directory.cleanup()

    def test_discard_stops_a_survivor_of_a_killed_wrapper(self) -> None:
        wrapper = subprocess.run(  # noqa: S603
            [str(ROOT / "tools/spec_workflow/bin/claude"), "-p", "/speckit-plan"],
            cwd=self.root,
            env=self.env,
            capture_output=True,
            check=False,
        )
        self.assertEqual(wrapper.returncode, -signal.SIGKILL)
        deadline = time.monotonic() + 10
        while not self.pid_file.exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        survivor = int(self.pid_file.read_text())
        self.assertTrue(Path(f"/proc/{survivor}").exists())
        result = subprocess.run(  # noqa: S603
            [
                sys.executable,
                "-IS",
                str(ROOT / "tools/spec_workflow/launcher.py"),
                "discard-runs",
            ],
            cwd=self.root,
            env=self.env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        deadline = time.monotonic() + 10
        while Path(f"/proc/{survivor}").exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        self.assertFalse(Path(f"/proc/{survivor}").exists())

    def test_real_scope_passes_a_dollar_prompt_unchanged(self) -> None:
        wrapper = subprocess.run(  # noqa: S603
            [str(ROOT / "tools/spec_workflow/bin/codex"), "exec", "$speckit-plan"],
            cwd=self.root,
            env={**self.env, "FAKE_SURVIVOR": "", "FAKE_KILL_WRAPPER": ""},
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(wrapper.returncode, 0, wrapper.stderr)
        argv = json.loads((self.root / "argv.json").read_text())
        self.assertEqual(argv[-1], "$speckit-plan")


@unittest.skipUnless(
    shutil.which("codex") and _user_systemd(), "needs codex and a systemd user manager"
)
class CodexSandboxTests(unittest.TestCase):
    """The agent's sandbox cannot ask the user manager for a unit of its own.

    Scope containment assumes this: a unit started through the manager would
    sit outside the agent's scope and survive `stop_scope`.
    """

    def test_workspace_write_sandbox_cannot_start_a_unit(self) -> None:
        unit = f"ballast-escape-probe-{os.getpid()}"
        with TemporaryDirectory() as directory:
            result = subprocess.run(  # noqa: S603
                [
                    shutil.which("codex") or "codex",
                    "sandbox",
                    "-c",
                    'sandbox_mode="workspace-write"',
                    "-c",
                    "sandbox_workspace_write.network_access=false",
                    "--",
                    "systemd-run",
                    "--user",
                    "--quiet",
                    f"--unit={unit}",
                    "sleep",
                    "30",
                ],
                cwd=directory,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                check=False,
                timeout=60,
            )
        listed = subprocess.run(  # noqa: S603
            ["systemctl", "--user", "list-units", "--all", f"{unit}*", "--no-legend"],  # noqa: S607
            capture_output=True,
            text=True,
            check=False,
        )
        if listed.stdout.strip():
            subprocess.run(["systemctl", "--user", "stop", unit], check=False)  # noqa: S603, S607
        self.assertNotEqual(result.returncode, 0, result.stdout)
        # Denied at the bus, not failing for some unrelated reason.
        self.assertIn("Operation not permitted", result.stderr + result.stdout)
        self.assertEqual(listed.stdout.strip(), "")


class TrustedLauncherTests(unittest.TestCase):
    """The operator launcher refuses changed inputs before running any of them."""

    def setUp(self) -> None:
        self.directory = TemporaryDirectory()
        self.root = Path(self.directory.name) / "checkout"
        self.tools = self.root / ".ballast/spec_workflow"
        self.tools.mkdir(parents=True)
        self.ran = self.root / "ran"
        for name in ("run.py", "ledger.py"):
            (self.tools / name).write_text(
                f"import sys; open({str(self.ran)!r}, 'w').write(' '.join(sys.argv))\n"
            )
        (self.root / ".specify/workflows/runs/r1").mkdir(parents=True)
        (self.root / ".specify/extensions.yml").write_text("hooks: {}\n")
        (self.root / ".venv/lib").mkdir(parents=True)
        (self.root / ".git").write_text("gitdir: /repo/.git/worktrees/checkout\n")
        fake = Path(self.directory.name) / "fake-bin"
        fake.mkdir()
        _fake_systemd(fake)
        self.env = {
            **os.environ,
            "PATH": f"{fake}{os.pathsep}{os.environ['PATH']}",
            "XDG_STATE_HOME": str(Path(self.directory.name) / "state"),
        }

    def tearDown(self) -> None:
        self.directory.cleanup()

    def launch(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(  # noqa: S603
            [
                sys.executable,
                "-IS",
                str(ROOT / "tools/spec_workflow/launcher.py"),
                *args,
            ],
            cwd=self.root,
            env=self.env,
            capture_output=True,
            text=True,
            check=False,
        )

    def launch_with(self, **env: str) -> subprocess.CompletedProcess[str]:
        saved = self.env
        self.env = {**saved, **env}
        try:
            return self.launch("discard-runs")
        finally:
            self.env = saved

    def assert_refused(self, reason: str) -> None:
        result = self.launch("run", "resume", "r1")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn(reason, result.stderr)
        self.assertFalse(self.ran.exists())

    def test_runs_only_after_trust_and_while_unchanged(self) -> None:
        self.assert_refused("no trusted baseline")
        self.assertEqual(self.launch("trust").returncode, 0)
        # Run state, and bytecode that no workflow tool reads, may change.
        (self.root / ".specify/workflows/runs/r1/state.json").write_text("{}")
        (self.tools / "__pycache__").mkdir()
        (self.tools / "__pycache__/x.pyc").write_bytes(b"x")
        result = self.launch("ledger", "check", "r1")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(self.ran.read_text().endswith("ledger.py check r1"))

    def test_changed_entry_point_or_environment_is_refused(self) -> None:
        for path, content in (
            (self.tools / "run.py", "print('rewritten')\n"),
            (self.tools / "yaml.py", "print('shadow')\n"),
            (self.root / ".venv/lib/hook.pth", "import os\n"),
            (self.root / ".specify/extensions.yml", "hooks: {x: y}\n"),
            (self.root / ".git", "gitdir: /tmp/forged\n"),
        ):
            with self.subTest(path=path.name):
                original = path.read_bytes() if path.exists() else None
                self.assertEqual(self.launch("trust").returncode, 0)
                path.write_text(content)
                self.assert_refused(path.name)
                if original is None:
                    path.unlink()
                else:
                    path.write_bytes(original)

    def test_discard_never_follows_a_linked_parent(self) -> None:
        operator = Path(self.directory.name) / "operator-data"
        (operator / "runs").mkdir(parents=True)
        (operator / "runs/keep.txt").write_text("keep\n")
        workflows = self.root / ".specify/workflows"
        shutil.rmtree(workflows)
        workflows.symlink_to(operator)
        (state_root := Path(self.directory.name) / "state/ballast").mkdir(parents=True)
        result = self.launch("discard-runs")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual((operator / "runs/keep.txt").read_text(), "keep\n")
        self.assertEqual(list(state_root.iterdir()), [])

    def status(self) -> dict:
        state = Path(self.env["XDG_STATE_HOME"])
        before = _tree(self.root), _tree(state) if state.exists() else None
        result = self.launch("status", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        after = _tree(self.root), _tree(state) if state.exists() else None
        self.assertEqual(after, before)
        return json.loads(result.stdout)

    def test_status_reports_the_refusal_without_writing(self) -> None:
        state = Path(self.env["XDG_STATE_HOME"])
        self.assertEqual(
            self.status(),
            {
                "installed": True,
                "refusal": "no trusted baseline; review the checkout, then run `trust`",
            },
        )
        self.assertFalse(state.exists())
        self.assertEqual(self.launch("trust").returncode, 0)
        self.assertEqual(self.status(), {"installed": True, "refusal": None})
        (self.root / ".specify/extensions.yml").write_text("hooks: {x: y}\n")
        self.assertIn("workflow inputs changed", self.status()["refusal"])
        self.assertEqual(self.launch("trust").returncode, 0)
        (self.root / "BALLAST_TAMPERED").write_text("x\n")
        self.assertIn("BALLAST_TAMPERED exists", self.status()["refusal"])
        (self.root / "BALLAST_TAMPERED").unlink()
        (marker_dir,) = (state / "ballast").iterdir()
        (marker_dir / "in-progress").write_text("ballast-agent-r1-step.scope\n")
        self.assertIn("did not finish", self.status()["refusal"])
        (self.tools / "run.py").unlink()
        self.assertEqual(self.status(), {"installed": False, "refusal": None})

    def test_tamper_marker_and_unfinished_step_are_refused(self) -> None:
        self.assertEqual(self.launch("trust").returncode, 0)
        (self.root / "BALLAST_TAMPERED").write_text("x\n")
        self.assert_refused("BALLAST_TAMPERED")
        self.assertEqual(self.launch("trust").returncode, 2)
        (self.root / "BALLAST_TAMPERED").unlink()
        (state,) = (Path(self.directory.name) / "state/ballast").iterdir()
        (state / "in-progress").write_text("ballast-agent-r1-step.scope\n")
        self.assert_refused("did not finish")
        # Saved runs are outside the baseline: trust alone must not clear this.
        self.assertEqual(self.launch("trust").returncode, 2)
        self.assert_refused("did not finish")
        # A scope that cannot be confirmed stopped keeps recovery closed.
        alive = self.launch_with(FAKE_SCOPE_STATE="active")
        self.assertEqual(alive.returncode, 2, alive.stderr)
        self.assertTrue((self.root / ".specify/workflows/runs").exists())
        self.assertEqual(self.launch("discard-runs").returncode, 0)
        self.assertFalse((self.root / ".specify/workflows/runs").exists())
        self.assertEqual(self.launch("trust").returncode, 0)
        self.assertEqual(self.launch("run", "start").returncode, 0)


class LauncherTests(unittest.TestCase):
    """The launcher validates resume input before touching run state."""

    def test_resume_rejects_unsafe_run_id_and_inputs(self) -> None:
        launcher = ROOT / "tools/spec_workflow/run.py"
        for args in (
            ["resume", "../../outside"],
            ["resume"],
            ["resume", "abc123", "-i", "feature_directory=specs/1-x"],
        ):
            result = subprocess.run(  # noqa: S603
                [sys.executable, "-I", str(launcher), *args],
                capture_output=True,
                text=True,
                check=False,
                env={**os.environ, "PATH": os.defpath},
            )
            self.assertEqual(result.returncode, 2, args)
            self.assertIn("resume", result.stderr)


def _steps() -> list[dict[str, object]]:
    return yaml.safe_load(WORKFLOW.read_text())["steps"]


class WorkflowOrderTests(unittest.TestCase):
    """Every gate and consumer is reachable only after its contract check."""

    def test_producers_are_validated_before_the_next_step(self) -> None:
        ids = [step["id"] for step in _steps()]
        for producer, validator in (
            ("specify", "validate-spec"),
            ("clarify", "validate-clarified-spec"),
            ("approve-intent", "record-intent"),
            ("record-intent", "validate-intent"),
            ("plan", "validate-plan"),
            ("tasks", "validate-tasks"),
            ("implement", "validate-implementation"),
            ("reconcile-intent", "validate-decisions"),
        ):
            self.assertEqual(ids[ids.index(producer) + 1], validator, producer)
        for before, after in (
            ("validate-intent", "plan"),
            ("validate-plan", "review-plan"),
            ("validate-tasks", "review-tasks"),
            ("implementation-baseline", "implement"),
            ("validate-convergence", "final-acceptance"),
        ):
            self.assertLess(ids.index(before), ids.index(after), before)
        self.assertNotIn("confirm-intent", ids)

    def test_gates_show_their_artifact(self) -> None:
        shown = {
            step["id"]: step.get("show_file")
            for step in _steps()
            if step.get("type") == "gate"
        }
        self.assertTrue(str(shown["approve-intent"]).endswith("/spec.md"))
        self.assertTrue(str(shown["review-plan"]).endswith("/plan.md"))
        self.assertTrue(str(shown["review-tasks"]).endswith("/tasks.md"))

    def test_shell_steps_never_interpolate_inputs(self) -> None:
        for step in _steps():
            if step.get("type") == "shell":
                self.assertNotIn("inputs.", str(step["run"]), step["id"])

    def test_operator_ledger_commands_start_without_site(self) -> None:
        result = subprocess.run(  # noqa: S603
            [
                sys.executable,
                "-I",
                "-S",
                str(ROOT / "tools/spec_workflow/ledger.py"),
                "--help",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        docs = (ROOT / "templates/policies/spec-kit-workflow.md").read_text()
        self.assertNotIn("python3 .ballast/spec_workflow/ledger.py", docs)

    def test_validators_run_without_checkout_startup_code(self) -> None:
        for step in _steps():
            if step.get("type") == "shell":
                run = str(step["run"])
                self.assertNotIn(".venv", run, step["id"])
                self.assertTrue(run.startswith("python3 -I -S "), step["id"])


PURELIB = "import sysconfig; print(sysconfig.get_path('purelib'))"


class InterpreterStartupTests(unittest.TestCase):
    """Why validators use `-I -S`: `-I -B` still runs site-packages `.pth` code."""

    def test_only_no_site_skips_pth_startup_hooks(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(  # noqa: S603
                [sys.executable, "-m", "venv", "--without-pip", str(root / "venv")],
                check=True,
            )
            python = str(root / "venv/bin/python")
            purelib = subprocess.run(  # noqa: S603
                [python, "-c", PURELIB],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            marker = root / "marker"
            (Path(purelib) / "hook.pth").write_text(
                f"import pathlib; pathlib.Path({str(marker)!r}).touch()\n"
            )
            subprocess.run([python, "-I", "-B", "-c", "pass"], check=True)  # noqa: S603
            self.assertTrue(marker.exists())
            marker.unlink()
            subprocess.run([python, "-I", "-S", "-c", "pass"], check=True)  # noqa: S603
            self.assertFalse(marker.exists())

    def test_launcher_starts_every_tool_with_isolation_and_no_site(self) -> None:
        # run.py holds the operator's GitHub credentials; site-packages .pth
        # code must never run before it (constitution: python3 -I -S).
        sys.path.insert(0, str(ROOT / "tools/spec_workflow"))
        try:
            import launcher  # noqa: PLC0415
        finally:
            sys.path.pop(0)
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".ballast/spec_workflow").mkdir(parents=True)
            (root / ".ballast/spec_workflow/run.py").write_text("")
            for command in ("run", "ledger"):
                calls: list[list[str]] = []
                with (
                    self.subTest(command=command),
                    patch.object(launcher.Path, "cwd", return_value=root),
                    patch.object(launcher, "_refusal", return_value=None),
                    patch.object(
                        launcher.os,
                        "execv",
                        side_effect=lambda _p, a, calls=calls: calls.append(a),
                    ),
                ):
                    launcher.main([command, "x"])
                self.assertEqual(calls[0][1], "-IS", calls)


FAKE_INTEGRATION = """#!/usr/bin/env python3
import os, shutil, sys
prompt = sys.argv[2]
if "speckit-specify" in prompt and os.environ.get("FAKE_SPEC"):
    os.makedirs("specs/102-demo-import", exist_ok=True)
    shutil.copy(os.environ["FAKE_SPEC"], "specs/102-demo-import/spec.md")
"""


@unittest.skipUnless(shutil.which("specify"), "Spec Kit CLI not installed")
class EngineRunTests(unittest.TestCase):
    """Drive the real workflow file through Spec Kit with a fake agent."""

    def setUp(self) -> None:
        self.directory = TemporaryDirectory()
        self.repo = Repository(self.directory.name)
        root = self.repo.root
        shutil.rmtree(root / FEATURE)
        # Lay the standard out the way the installer places it in a project.
        (root / ".ballast").mkdir()
        (root / ".ballast/spec_workflow").symlink_to(ROOT / "tools/spec_workflow")
        agent = root / "fake-agent"
        agent.write_text(FAKE_INTEGRATION)
        agent.chmod(0o755)
        (root / "spec-fixture.md").write_text(SPEC)
        self.env = {
            **os.environ,
            "BALLAST_SPEC_WORKFLOW": "1",
            "SPECKIT_INTEGRATION_CLAUDE_EXECUTABLE": str(agent),
        }

    def tearDown(self) -> None:
        self.directory.cleanup()

    def run_workflow(self, answers: list[str], **env: str) -> dict[str, object]:
        """Run with a TTY so gates prompt; answer each gate in order."""
        primary, secondary = pty.openpty()
        process = subprocess.Popen(  # noqa: S603
            [  # noqa: S607 - resolved by the skip condition
                "specify",
                "workflow",
                "run",
                str(WORKFLOW),
                "-i",
                "idea=Issue #102: demo",
                "-i",
                f"feature_directory={FEATURE}",
                "-i",
                "integration=claude",
            ],
            cwd=self.repo.root,
            env={**self.env, **env},
            stdin=secondary,
            stdout=secondary,
            stderr=secondary,
        )
        os.close(secondary)
        output, pending, deadline = b"", list(answers), time.monotonic() + 120
        while process.poll() is None and time.monotonic() < deadline:
            if select.select([primary], [], [], 0.2)[0]:
                try:
                    output += os.read(primary, 4096)
                except OSError:
                    break
                if pending and output.count(b"Choose [") > len(answers) - len(pending):
                    os.write(primary, pending.pop(0).encode() + b"\n")
        process.wait(timeout=30)
        os.close(primary)
        (run,) = (self.repo.root / ".specify/workflows/runs").iterdir()
        return json.loads((run / "state.json").read_text())

    def test_exit_zero_without_artifact_stops_before_any_gate(self) -> None:
        state = self.run_workflow(["approve"])
        results = state["step_results"]
        self.assertEqual(state["status"], "failed")
        self.assertEqual(results["specify"]["status"], "completed")
        self.assertEqual(results["validate-spec"]["status"], "failed")
        self.assertNotIn("clarify", results)
        self.assertNotIn("approve-intent", results)

    def test_rejected_intent_cannot_reach_planning(self) -> None:
        state = self.run_workflow(
            ["approve", "reject"], FAKE_SPEC=str(self.repo.root / "spec-fixture.md")
        )
        results = state["step_results"]
        self.assertEqual(state["status"], "paused")
        self.assertEqual(results["validate-clarified-spec"]["status"], "completed")
        self.assertNotIn("record-intent", results)
        self.assertNotIn("plan", results)

    def test_approved_intent_then_missing_plan_stops_before_review(self) -> None:
        state = self.run_workflow(
            ["approve", "approve"], FAKE_SPEC=str(self.repo.root / "spec-fixture.md")
        )
        results = state["step_results"]
        self.assertEqual(results["record-intent"]["status"], "completed")
        self.assertEqual(results["plan"]["status"], "completed")
        self.assertEqual(results["validate-plan"]["status"], "failed")
        self.assertNotIn("review-plan", results)


if __name__ == "__main__":
    unittest.main()


class RunHistoryTests(unittest.TestCase):
    """run.py keeps run data only in the local Git common directory."""

    def setUp(self) -> None:
        self.directory = TemporaryDirectory()
        self.repo = Repository(self.directory.name)
        run_dir = self.repo.root / ".specify/workflows/runs/run42"
        run_dir.mkdir(parents=True)
        (run_dir / "inputs.json").write_text(
            json.dumps({"inputs": {"feature_directory": FEATURE}})
        )
        (run_dir / "state.json").write_text(
            json.dumps(
                {
                    "workflow_id": "ballast-feature",
                    "status": "paused",
                    "workflow_dir": str(self.repo.root / "secret-path"),
                    "step_results": {
                        "scope-gate": {"type": "gate", "output": {"choice": "approve"}},
                        "specify": {"type": "command", "output": {"stdout": "noisy"}},
                    },
                }
            )
        )
        (run_dir / "log.jsonl").write_text('{"event": "step_started"}\n')
        agents = self.repo.root / ".specify/workflow-state/run42/agents"
        agents.mkdir(parents=True)
        (agents / "log.txt").write_text("agent output\n")

    def tearDown(self) -> None:
        self.directory.cleanup()

    def _make_importable_run(self) -> None:
        run_dir = self.repo.root / ".specify/workflows/runs/run42"
        (run_dir / "workflow.yml").write_text(
            "workflow:\n  id: ballast-feature\n  version: 1.1.0\n"
            "steps:\n  - id: scope-gate\n    type: gate\n"
        )
        (run_dir / "log.jsonl").write_text(
            '{"event":"step_started","step_id":"scope-gate","type":"gate"}\n'
            '{"event":"step_completed","step_id":"scope-gate","status":"completed"}\n'
        )

    def test_archives_run_without_feature_record(self) -> None:
        sys.path.insert(0, str(ROOT / "tools/spec_workflow"))
        try:
            import run  # noqa: PLC0415
        finally:
            sys.path.pop(0)
        run._record(self.repo.root, "run42")  # noqa: SLF001

        archive = self.repo.root / ".git/speckit-runs/run42"
        self.assertTrue((archive / "run/state.json").is_file())
        self.assertTrue((archive / "state/agents/log.txt").is_file())
        self.assertFalse((self.repo.root / FEATURE / "workflow-runs").exists())

    def test_launcher_imports_after_workflow_failure_and_preserves_exit(self) -> None:
        sys.path.insert(0, str(ROOT / "tools/spec_workflow"))
        try:
            import run  # noqa: PLC0415
        finally:
            sys.path.pop(0)
        with (
            patch.object(run, "ROOT", self.repo.root),
            patch.object(run.shutil, "which", return_value="/bin/specify"),
            patch.object(
                run.subprocess, "run", return_value=SimpleNamespace(returncode=7)
            ),
            patch.object(run, "_record") as archive,
            patch.object(
                run, "import_run", side_effect=ValueError("bad ledger")
            ) as importer,
        ):
            self.assertEqual(run.main(["resume", "run42"]), 7)
        archive.assert_called_once_with(self.repo.root, "run42", 7)
        importer.assert_called_once_with(self.repo.root, "run42")

    def test_launcher_refuses_to_run_after_tampering(self) -> None:
        sys.path.insert(0, str(ROOT / "tools/spec_workflow"))
        try:
            import run  # noqa: PLC0415
        finally:
            sys.path.pop(0)
        (self.repo.root / "BALLAST_TAMPERED").write_text("x\n")
        with (
            patch.object(run, "ROOT", self.repo.root),
            patch.object(run.subprocess, "run") as specify,
        ):
            for args in (["resume", "run42"], ["start", "-i", "idea=x"]):
                self.assertEqual(run.main(args), 2)
        specify.assert_not_called()

    def test_entry_points_stop_before_importing_checkout_code(self) -> None:
        tools = self.repo.root / ".ballast/spec_workflow"
        tools.mkdir(parents=True)
        for name in ("run.py", "ledger.py"):
            shutil.copy(ROOT / "tools/spec_workflow" / name, tools)
        ran = self.repo.root / "ran"
        for name in ("agent.py", "artifacts.py"):
            (tools / name).write_text(f"open({str(ran)!r}, 'w').close()\n")
        (self.repo.root / "BALLAST_TAMPERED").write_text("x\n")
        for script, args in (
            ("run.py", ["resume", "run42"]),
            ("ledger.py", ["check", "run42", "AC-001", "tests.x"]),
        ):
            result = subprocess.run(  # noqa: S603
                [sys.executable, "-I", "-S", str(tools / script), *args],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertIn("BALLAST_TAMPERED", result.stderr)
        self.assertFalse(ran.exists())

    def test_marker_name_matches_across_entry_points(self) -> None:
        sys.path.insert(0, str(ROOT / "tools/spec_workflow"))
        try:
            import agent  # noqa: PLC0415
            import ledger  # noqa: PLC0415
            import run  # noqa: PLC0415
        finally:
            sys.path.pop(0)
        self.assertEqual(
            {agent.TAMPER_MARKER, ledger.TAMPER_MARKER, run.TAMPER_MARKER},
            {"BALLAST_TAMPERED"},
        )

    def test_launcher_freezes_policy_before_start(self) -> None:
        sys.path.insert(0, str(ROOT / "tools/spec_workflow"))
        try:
            import run  # noqa: PLC0415
        finally:
            sys.path.pop(0)
        order: list[str] = []

        def launch(*_args: object, **_kwargs: object) -> SimpleNamespace:
            self.assertEqual(order, ["policy"])
            return SimpleNamespace(returncode=0)

        with (
            patch.object(run, "ROOT", self.repo.root),
            patch.object(run.shutil, "which", return_value="/bin/specify"),
            patch.object(
                run.uuid, "uuid4", return_value=SimpleNamespace(hex="run42xxx")
            ),
            patch.object(
                run, "archive_policy", side_effect=lambda *_: order.append("policy")
            ),
            patch.object(
                run, "subprocess", SimpleNamespace(run=Mock(side_effect=launch))
            ),
            patch.object(run, "_summary"),
            patch.object(run, "_record"),
            patch.object(run, "import_run"),
        ):
            self.assertEqual(
                run.main(
                    ["start", "-i", "feature_directory=specs/93-agent-run-ledger"]
                ),
                0,
            )

    def test_launcher_import_failure_fails_successful_workflow(self) -> None:
        sys.path.insert(0, str(ROOT / "tools/spec_workflow"))
        try:
            import run  # noqa: PLC0415
        finally:
            sys.path.pop(0)
        with (
            patch.object(run, "ROOT", self.repo.root),
            patch.object(run.shutil, "which", return_value="/bin/specify"),
            patch.object(
                run,
                "subprocess",
                SimpleNamespace(run=Mock(return_value=SimpleNamespace(returncode=0))),
            ),
            patch.object(run, "_record"),
            patch.object(run, "import_run", side_effect=ValueError("bad ledger")),
        ):
            self.assertEqual(run.main(["resume", "run42"]), 1)

    def test_malformed_import_preserves_workflow_failure_code(self) -> None:
        sys.path.insert(0, str(ROOT / "tools/spec_workflow"))
        try:
            import run  # noqa: PLC0415
        finally:
            sys.path.pop(0)
        with (
            patch.object(run, "ROOT", self.repo.root),
            patch.object(run.shutil, "which", return_value="/bin/specify"),
            patch.object(
                run,
                "subprocess",
                SimpleNamespace(run=Mock(return_value=SimpleNamespace(returncode=7))),
            ),
            patch.object(run, "_record"),
            patch.object(run, "import_run", side_effect=KeyError("inputs")),
        ):
            self.assertEqual(run.main(["resume", "run42"]), 7)

    def test_malformed_summary_still_attempts_import(self) -> None:
        sys.path.insert(0, str(ROOT / "tools/spec_workflow"))
        try:
            import run  # noqa: PLC0415
        finally:
            sys.path.pop(0)
        with (
            patch.object(run, "ROOT", self.repo.root),
            patch.object(run.shutil, "which", return_value="/bin/specify"),
            patch.object(
                run,
                "subprocess",
                SimpleNamespace(run=Mock(return_value=SimpleNamespace(returncode=7))),
            ),
            patch.object(run, "_summary", side_effect=AttributeError("bad state")),
            patch.object(run, "_record"),
            patch.object(run, "import_run", return_value=1) as importer,
        ):
            self.assertEqual(run.main(["resume", "run42"]), 7)
        importer.assert_called_once_with(self.repo.root, "run42")

    def test_archive_failure_still_attempts_ledger_import(self) -> None:
        sys.path.insert(0, str(ROOT / "tools/spec_workflow"))
        try:
            import run  # noqa: PLC0415
        finally:
            sys.path.pop(0)
        with (
            patch.object(run, "ROOT", self.repo.root),
            patch.object(run.shutil, "which", return_value="/bin/specify"),
            patch.object(
                run.subprocess, "run", return_value=SimpleNamespace(returncode=0)
            ),
            patch.object(run, "_record", side_effect=ValueError("archive failed")),
            patch.object(run, "import_run", return_value=1) as importer,
        ):
            self.assertEqual(run.main(["resume", "run42"]), 1)
        importer.assert_called_once_with(self.repo.root, "run42")

    def test_malformed_archive_shape_still_attempts_import(self) -> None:
        sys.path.insert(0, str(ROOT / "tools/spec_workflow"))
        try:
            import run  # noqa: PLC0415
        finally:
            sys.path.pop(0)
        with (
            patch.object(run, "ROOT", self.repo.root),
            patch.object(run.shutil, "which", return_value="/bin/specify"),
            patch.object(
                run,
                "subprocess",
                SimpleNamespace(run=Mock(return_value=SimpleNamespace(returncode=7))),
            ),
            patch.object(run, "_record", side_effect=AttributeError("bad state")),
            patch.object(run, "import_run", return_value=1) as importer,
        ):
            self.assertEqual(run.main(["resume", "run42"]), 7)
        importer.assert_called_once_with(self.repo.root, "run42")

    def test_launcher_archives_and_imports_real_fixture(self) -> None:
        self._make_importable_run()
        sys.path.insert(0, str(ROOT / "tools/spec_workflow"))
        try:
            import ledger  # noqa: PLC0415
            import run  # noqa: PLC0415
        finally:
            sys.path.pop(0)
        with (
            patch.object(run, "ROOT", self.repo.root),
            patch.object(run.shutil, "which", return_value="/bin/specify"),
            patch.object(
                run,
                "subprocess",
                SimpleNamespace(run=Mock(return_value=SimpleNamespace(returncode=0))),
            ),
        ):
            self.assertEqual(run.main(["resume", "run42"]), 0)
        events, problems = ledger.read(self.repo.root, "run42")
        self.assertEqual(problems, [])
        self.assertEqual(
            [item["data"]["choice"] for item in events if item["kind"] == "gate"],
            ["approve"],
        )
        self.assertTrue(
            (ledger.archive_dir(self.repo.root, "run42") / "run/state.json").is_file()
        )

    def test_keyboard_interrupt_still_imports_partial_run(self) -> None:
        self._make_importable_run()
        run_dir = self.repo.root / ".specify/workflows/runs/run42"
        state = json.loads((run_dir / "state.json").read_text())
        state["step_results"]["scope-gate"]["output"]["choice"] = "reject"
        (run_dir / "state.json").write_text(json.dumps(state))
        (run_dir / "log.jsonl").write_text(
            '{"event":"step_started","step_id":"scope-gate","type":"gate"}\n'
            '{"event":"step_completed","step_id":"scope-gate","status":"paused"}\n'
        )
        sys.path.insert(0, str(ROOT / "tools/spec_workflow"))
        try:
            import ledger  # noqa: PLC0415
            import run  # noqa: PLC0415
        finally:
            sys.path.pop(0)
        with (
            patch.object(run, "ROOT", self.repo.root),
            patch.object(run.shutil, "which", return_value="/bin/specify"),
            patch.object(
                run,
                "subprocess",
                SimpleNamespace(run=Mock(side_effect=KeyboardInterrupt)),
            ),
        ):
            self.assertEqual(run.main(["resume", "run42"]), 130)
        events, problems = ledger.read(self.repo.root, "run42")
        self.assertEqual(problems, [])
        self.assertEqual(
            [event["data"]["choice"] for event in events if event["kind"] == "gate"],
            ["unobserved"],
        )


AUTONOMOUS_WORKFLOW = ROOT / "templates/spec-kit/workflows/autonomous/workflow.yml"
CONTINUE_WORKFLOW = ROOT / "templates/spec-kit/workflows/continue/workflow.yml"
# SHA-256 of ballast-feature's workflow.yml on main before Autonomous runs.
FEATURE_WORKFLOW_DIGEST = (
    "af141e8475e3934493ef143baa485744c30fcde0503e0b8c3ebf36622d1ab3ed"
)
# contracts/workflow.md, ballast-autonomous: (step id, check or command, args).
AUTONOMOUS_STEPS = (
    ("preflight", "autonomous-preflight", None),
    ("decide-scope", "speckit.ballast.decide", "scope"),
    ("record-scope", "record-decision", "scope"),
    ("specify", "speckit.specify", None),
    ("validate-spec", "spec", None),
    ("clarify", "speckit.ballast.clarify", None),
    ("record-clarifications", "record-decision", "clarification"),
    ("validate-clarified-spec", "clarified-spec", None),
    ("decide-intent", "speckit.ballast.decide", "intent"),
    ("record-provisional-intent", "record-provisional-intent", None),
    ("validate-intent", "intent", None),
    ("plan", "speckit.plan", None),
    ("validate-plan", "plan", None),
    ("review-plan", "speckit.ballast.review", "plan"),
    ("record-plan-review", "record-decision", "plan-review"),
    ("decide-plan", "speckit.ballast.decide", "plan"),
    ("record-plan", "record-decision", "plan"),
    ("tasks", "speckit.tasks", None),
    ("validate-tasks", "tasks", None),
    ("analyze", "speckit.analyze", None),
    ("decide-tasks", "speckit.ballast.decide", "tasks"),
    ("record-tasks", "record-decision", "tasks"),
    ("implementation-baseline", "implementation-baseline", None),
    ("implement", "speckit.implement", None),
    ("validate-implementation", "implementation", None),
    ("review-implementation", "speckit.ballast.review", "implementation"),
    ("review-specialists", "speckit.ballast.review", "specialists"),
    ("record-implementation-review", "record-decision", "implementation-review"),
    ("resolve-decisions", "speckit.ballast.resolve", None),
    ("record-resolutions", "record-decision", "decision-resolution"),
    ("renew-intent", "record-provisional-intent", "--renew"),
    ("validate-decisions", "decisions", None),
    ("converge", "speckit.converge", None),
    ("reconcile-spec", "speckit.ballast.review", "spec-reconciliation"),
    ("record-reconciliation", "record-decision", "spec-reconciliation"),
    ("validate-convergence", "convergence", None),
    ("run-checks", "run-checks", None),
    ("decide-final", "speckit.ballast.decide", "final-acceptance"),
    ("record-final", "record-decision", "final-acceptance"),
)
REVIEW_STEPS = ("review-plan", "review-implementation", "review-specialists")
SHELL_PREFIX = "python3 -I -S .ballast/spec_workflow/artifacts.py "


def _shell_check(run: str) -> tuple[str, str | None]:
    """(check, --point value or --renew) of a validator command line."""
    rest = run.removeprefix(SHELL_PREFIX).split()
    check, extra = rest[0], rest[1:]
    assert extra[:2] == ["--run", "{{"], run  # noqa: S101
    tail = extra[4:]
    if tail[:1] == ["--point"]:
        return check, tail[1]
    return check, tail[0] if tail else None


class AutonomousWorkflowDefinitionTests(unittest.TestCase):
    """T015 [AC-001, SC-007]: ballast-autonomous has no gate and every check."""

    def setUp(self) -> None:
        self.doc = yaml.safe_load(AUTONOMOUS_WORKFLOW.read_text())
        self.steps = self.doc["steps"]

    def test_parses_with_no_gate(self) -> None:
        self.assertEqual(self.doc["workflow"]["id"], "ballast-autonomous")
        self.assertNotIn("gate", {step.get("type") for step in self.steps})
        self.assertEqual(
            set(self.doc["inputs"]),
            {"idea", "feature_directory", "integration", "review_integration"},
        )

    def test_steps_match_the_contract(self) -> None:
        found = []
        for step in self.steps:
            if step.get("type") == "shell":
                check, extra = _shell_check(step["run"])
                found.append((step["id"], check, extra))
            else:
                args = (step.get("input") or {}).get("args")
                found.append(
                    (step["id"], step["command"], args if "ballast" in step["command"] else None)
                )
        self.assertEqual(tuple(found), AUTONOMOUS_STEPS)

    def test_shell_steps_never_interpolate_inputs(self) -> None:
        for step in self.steps:
            if step.get("type") == "shell":
                self.assertTrue(step["run"].startswith(SHELL_PREFIX), step["id"])
                self.assertIn("--run {{ context.run_id }}", step["run"], step["id"])
                self.assertNotIn("inputs.", step["run"], step["id"])

    def test_review_steps_use_the_review_integration(self) -> None:
        for step in self.steps:
            if step.get("type") == "shell":
                continue
            expected = (
                "{{ inputs.review_integration }}"
                if step["id"] in (*REVIEW_STEPS, "reconcile-spec")
                else "{{ inputs.integration }}"
            )
            self.assertEqual(step["integration"], expected, step["id"])

    def test_every_producer_is_followed_by_its_check(self) -> None:
        ids = [step["id"] for step in self.steps]
        for producer, check in (
            ("decide-scope", "record-scope"),
            ("specify", "validate-spec"),
            ("clarify", "record-clarifications"),
            ("decide-intent", "record-provisional-intent"),
            ("plan", "validate-plan"),
            ("review-plan", "record-plan-review"),
            ("decide-plan", "record-plan"),
            ("tasks", "validate-tasks"),
            ("decide-tasks", "record-tasks"),
            ("implement", "validate-implementation"),
            ("review-specialists", "record-implementation-review"),
            ("resolve-decisions", "record-resolutions"),
            ("reconcile-spec", "record-reconciliation"),
            ("decide-final", "record-final"),
        ):
            self.assertEqual(ids[ids.index(producer) + 1], check, producer)

    def test_feature_workflow_is_unchanged(self) -> None:
        self.assertEqual(
            hashlib.sha256(WORKFLOW.read_bytes()).hexdigest(), FEATURE_WORKFLOW_DIGEST
        )


class ContinueWorkflowDefinitionTests(unittest.TestCase):
    """T037 [AC-009, AC-017]: ballast-continue has only validators and gates."""

    def setUp(self) -> None:
        self.doc = yaml.safe_load(CONTINUE_WORKFLOW.read_text())
        self.steps = self.doc["steps"]

    def test_no_command_step(self) -> None:
        self.assertEqual(self.doc["workflow"]["id"], "ballast-continue")
        self.assertEqual(
            {step.get("type") for step in self.steps}, {"shell", "gate"}
        )
        self.assertFalse(any("command" in step for step in self.steps))

    def test_steps_match_the_contract(self) -> None:
        found = []
        for step in self.steps:
            if step["type"] == "shell":
                found.append(_shell_check(step["run"])[0])
            else:
                found.append("gate " + step["id"])
        self.assertEqual(
            found,
            [
                "continue-preflight",
                "clarified-spec",
                "gate approve-intent",
                "record-intent",
                "intent",
                "plan",
                "gate review-plan",
                "tasks",
                "gate review-tasks",
                "implementation",
                "gate review-implementation",
                "decisions",
                "gate spec-reconciliation",
                "convergence",
                "gate final-acceptance",
            ],
        )

    def test_gates_equal_ballast_feature(self) -> None:
        feature = {
            step["id"]: step for step in _steps() if step.get("type") == "gate"
        }
        for step in self.steps:
            if step["type"] == "gate":
                self.assertEqual(step, feature[step["id"]], step["id"])
                self.assertEqual(step["on_reject"], "retry")


sys.path.insert(0, str(ROOT / "tests"))
from test_autonomy import AutonomyCase, _bwrap_works, autonomy  # noqa: E402

sys.path.pop(0)
sys.path.insert(0, str(ROOT / "tools/spec_workflow"))
try:
    import run as run_module  # noqa: E402
finally:
    sys.path.pop(0)

AUTO_FEATURE = "specs/27-demo-run"
DONE_TASKS = TASKS.replace("- [ ]", "- [x]")


def _draft(point: str, artifact: str, **changes: object) -> str:
    data = {
        "point": point,
        "decision": autonomy.POINT_DECISION[point],
        "summary": f"{point} is acceptable",
        "basis": "Consistent with the spec and the Issue.",
        "evidence": [artifact],
        "artifact": artifact,
        "model": "fake-model",
        "material": False,
        "supersedes": None,
        "privileged_actions": [],
        "review": None,
        "assumption": None,
    }
    return json.dumps(data | changes)


def _review(point: str, kind: str, findings: list | None = None) -> dict[str, str]:
    report = f"{AUTO_FEATURE}/reviews/{kind}.md"
    review = {
        "kind": kind,
        "verdict": "approved",
        "report": report,
        "findings": findings or [],
    }
    name = f"{point}-{kind}.json" if point == "specialist-review" else f"{point}.json"
    return {
        report: f"# {kind} review\n\nConsistent with the plan.\n",
        f"{AUTO_FEATURE}/autonomous/drafts/{name}": _draft(
            point, report, review=review
        ),
    }


def _autonomous_plan() -> dict[str, dict[str, str]]:
    """What each fake agent step writes, keyed by the fake agent's directory."""
    feature, drafts = AUTO_FEATURE, f"{AUTO_FEATURE}/autonomous/drafts"
    spec, plan = f"{feature}/spec.md", f"{feature}/plan.md"

    def decide(point: str, artifact: str) -> dict[str, str]:
        return {f"{drafts}/{point}.json": _draft(point, artifact)}

    return {
        "speckit-ballast-decide-scope": decide("scope", "README.md"),
        "speckit-specify": {spec: SPEC},
        "speckit-ballast-decide-intent": decide("intent", spec),
        "speckit-plan": {plan: PLAN},
        "speckit-ballast-review-plan": _review("plan-review", "plan"),
        "speckit-ballast-decide-plan": decide("plan", plan),
        "speckit-tasks": {f"{feature}/tasks.md": TASKS},
        "speckit-ballast-decide-tasks": decide("tasks", f"{feature}/tasks.md"),
        "speckit-implement": {
            f"{feature}/tasks.md": DONE_TASKS,
            "src/demo/import.py": "print('import')\n",
            "tests/test_import.py": "assert True\n",
        },
        "speckit-ballast-review-implementation": _review(
            "implementation-review", "engineering"
        ),
        "speckit-ballast-review-specialists": _review("specialist-review", "test")
        | _review("specialist-review", "security"),
        "speckit-ballast-review-spec-reconciliation": _review(
            "spec-reconciliation", "spec-reconciliation"
        )
        | {f"{feature}/reviews/convergence.md": "# Convergence\n\n- Verdict: CONVERGED\n"},
        "speckit-ballast-decide-final-acceptance": decide(
            "final-acceptance", f"{feature}/tasks.md"
        ),
    }


BLOCKED = {"stdout.txt": "RECONCILE_STATUS: BLOCKED_DECISION\n"}
# A bwrap that skips confinement but answers the self-test as confined: it
# stands for a confinement hole, behind which the wrapper's protected-file
# check and the run's block mapping must still hold.
UNCONFINED_BWRAP = """#!/usr/bin/env python3
import json, os, sys
args = sys.argv[1:]
command = args[args.index("--") + 1 :]
if len(command) > 4 and command[3] == "-c" and "targets, persist" in command[4]:
    targets = json.loads(command[5])[0]
    print(json.dumps({**{t: "ok" for t in targets}, "operator environ": "ok"}))
    sys.exit(0)
os.execvp(command[0], command)
"""


def _block_draft(category: str, condition: str) -> dict[str, str]:
    draft = {
        "category": category,
        "condition": condition,
        "no_safe_default": "Each option changes what users see",
        "options": [
            {"option": "Keep", "consequence": "Imports stay visible"},
            {"option": "Hide", "consequence": "Imports need a review first"},
        ],
        "recovery": "Choose an option in spec.md, then continue human-gated",
        "evidence": [f"{AUTO_FEATURE}/spec.md"],
    }
    return {f"{AUTO_FEATURE}/autonomous/drafts/block.json": json.dumps(draft)}


@unittest.skipUnless(
    shutil.which("specify") and _user_systemd() and _bwrap_works(),
    "needs Spec Kit, a systemd user manager and a working bwrap",
)
class AutonomousEngineCase(AutonomyCase):
    """ballast-autonomous through run.py, Spec Kit, the confined agent wrapper
    and the trusted recorders, with a fake agent, a fake gh and a bare origin.

    Shared by the engine test classes below; it has no tests of its own.
    """

    def setUp(self) -> None:
        super().setUp()
        # The ignore rules tools/setup installs, and the standard laid out the
        # way it places it in a project.
        (self.root / ".gitignore").write_text(".ballast/\n.specify/*\n!.specify/memory/\n")
        shutil.copytree(
            ROOT / "tools/spec_workflow",
            self.root / ".ballast/spec_workflow",
            symlinks=True,
            ignore=shutil.ignore_patterns("__pycache__"),
        )
        for name in ("autonomous", "continue"):
            subprocess.run(  # noqa: S603
                [  # noqa: S607 - resolved by the skip condition
                    "specify",
                    "workflow",
                    "add",
                    "--dev",
                    str(ROOT / "templates/spec-kit/workflows" / name),
                ],
                cwd=self.root,
                check=True,
                capture_output=True,
            )
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "install")
        self.eligible_issue()
        (self.gh_dir / "auth.ok").write_text("")
        for name in ("claude", "codex"):
            target = self.bin / name
            shutil.copyfile(ROOT / "tests/fixtures/autonomy/fake_agent.py", target)
            target.chmod(0o755)
        # Inside .git: readable from the agent sandbox, whose /tmp is private,
        # and outside the worktree the run must keep clean.
        self.plan_dir = self.root / ".git/fake-agent-plan"
        self.layout(_autonomous_plan())
        os.environ["FAKE_AGENT_PLAN"] = str(self.plan_dir)
        self.enterContext(patch.object(run_module, "ROOT", self.root))
        self.enterContext(
            patch.object(run_module, "BIN", self.root / ".ballast/spec_workflow/bin")
        )

    def layout(self, plan: dict[str, dict[str, str]]) -> None:
        """(Re)write the fake agent's per-step output tree."""
        shutil.rmtree(self.plan_dir, ignore_errors=True)
        for step, files in plan.items():
            for path, text in files.items():
                target = self.plan_dir / step / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(text)

    def unconfined(self) -> None:
        """Put the self-test-passing, non-confining bwrap first on PATH."""
        target = self.bin / "bwrap"
        target.write_text(UNCONFINED_BWRAP)
        target.chmod(0o755)

    def main(self, *argv: str) -> tuple[int, str, str]:
        """run.main in process, with stdin that cannot answer a gate."""
        out, err = io.StringIO(), io.StringIO()
        saved = os.dup(0)
        with Path(os.devnull).open() as null:
            os.dup2(null.fileno(), 0)
        try:
            with redirect_stdout(out), redirect_stderr(err):
                code = run_module.main(list(argv))
        finally:
            os.dup2(saved, 0)
            os.close(saved)
        return code, out.getvalue(), err.getvalue()

    def run_ids(self) -> list[str]:
        runs = autonomy.state_dir(self.root) / "runs"
        return sorted(p.name for p in runs.iterdir()) if runs.is_dir() else []

    def start(self, *extra: str, integration: str = "claude") -> tuple[int, str, str, str]:
        """Run `ballast run start --mode autonomous`; return code, out, err, run."""
        code, out, err = self.main(
            "start",
            "--mode",
            "autonomous",
            *extra,
            "-i",
            "issue=27",
            "-i",
            "idea=Issue #27: demo",
            "-i",
            f"feature_directory={AUTO_FEATURE}",
            "-i",
            f"integration={integration}",
        )
        ids = self.run_ids()
        return code, out, err, ids[0] if ids else ""

    def engine_state(self, run_id: str) -> dict:
        path = self.root / ".specify/workflows/runs" / run_id / "state.json"
        return json.loads(path.read_text())

    def agent_commands(self, run_id: str) -> list[str]:
        """The agent steps that ran, as `<command> <first arg>`."""
        return [
            step["command"].lstrip("/$")
            for step in autonomy.read_steps(self.root, run_id)
            if step.get("ran")
        ]

    def stopped(self, *extra: str, integration: str = "claude") -> tuple[str, dict, str]:
        """Start a run that must stop on a block; return run ID, block, output."""
        code, out, err, run_id = self.start(*extra, integration=integration)
        self.assertEqual(code, 1, out + err)
        record = autonomy.read_run(self.root, run_id)
        self.assertEqual(record["status"], "stopped")
        block = autonomy.read_block(self.root, run_id)
        self.assertIn(f"Next: {block['command']}", out)
        self.assertIn(f"Autonomous run blocked ({block['category']})", out)
        self.assertNotIn("Draft PR", out)
        if block["category"] not in autonomy.PUBLISH_RETRY:
            self.assertFalse([c for c in self.gh_calls() if c[:2] == ["pr", "create"]])
        return run_id, block, out


class AutonomousEngineTests(AutonomousEngineCase):
    """T033 [AC-001, AC-002, AC-003, SC-001, SC-002]: a full unattended run."""

    def test_runs_to_a_draft_pr_without_a_prompt(self) -> None:
        code, out, err, run_id = self.start()
        self.assertEqual(code, 0, out + err)
        state = self.engine_state(run_id)
        self.assertEqual(state["status"], "completed")
        results = state["step_results"]
        # Every step ran, and ballast-autonomous has no gate to prompt at.
        self.assertEqual(set(results), {step[0] for step in AUTONOMOUS_STEPS})
        record = autonomy.read_run(self.root, run_id)
        self.assertEqual(record["status"], "published")
        current = autonomy.current_decisions(autonomy.read_decisions(self.root, run_id))
        points = [entry["point"] for entry in current]
        for point in autonomy.SINGLE_POINTS:
            self.assertEqual(points.count(point), 1, point)
        rendered = (self.root / AUTO_FEATURE / "autonomous/record.md").read_text()
        for entry in current:
            self.assertIn(entry["id"], rendered)
            self.assertIsNotNone(entry["agent"]["provider"])
        self.assertIn("Draft PR:", out)
        self.assertIn(["pr", "create", "--draft"], [c[:3] for c in self.gh_calls()])
        body = (self.gh_dir / "pr-body.md").read_text()
        for entry in current:
            self.assertIn(entry["id"], body)
        # Every agent step ran under the confined wrapper; reviews on codex.
        reviewers = {
            step["integration"]
            for step in autonomy.read_steps(self.root, run_id)
            if step.get("role") == "reviewer"
        }
        self.assertEqual(reviewers, {"codex"})
        self.assertEqual(record["agent_steps"], len(self.agent_commands(run_id)))

    def test_failed_validator_stops_the_run(self) -> None:
        plan = _autonomous_plan()
        del plan["speckit-plan"]
        self.layout(plan)
        run_id, block, _ = self.stopped()
        results = self.engine_state(run_id)["step_results"]
        self.assertEqual(results["validate-plan"]["status"], "failed")
        self.assertNotIn("review-plan", results)
        self.assertEqual(block["category"], "postcondition")
        self.assertEqual(self.agent_commands(run_id)[-1], "speckit-plan")


class AutonomousContinueEngineTests(AutonomousEngineCase):
    """T042 [AC-009, AC-017]: merge feedback continues human-gated."""

    def test_changes_requested_starts_ballast_continue(self) -> None:
        code, out, err, run_id = self.start()
        self.assertEqual(code, 0, out + err)
        before = autonomy.read_decisions(self.root, run_id)
        url = "https://github.com/acme/demo/pull/7#pullrequestreview-1"
        code, out, err = self.main(
            "continue", run_id, "--reason", "changes-requested", "--ref", url
        )
        (new_id,) = set(self.run_ids()) - {run_id}
        state = self.engine_state(new_id)
        self.assertEqual(state["workflow_id"], "ballast-continue", out + err)
        results = state["step_results"]
        self.assertEqual(results["preflight"]["status"], "completed", out + err)
        self.assertEqual(results["validate-clarified-spec"]["status"], "completed", out + err)
        # The first gate is the first thing that waits for a human.
        self.assertEqual(state["status"], "paused")
        self.assertEqual(state["current_step_id"], "approve-intent")
        self.assertEqual(results["approve-intent"]["type"], "gate")
        self.assertNotIn("record-intent", results)
        (decision,) = autonomy.read_human_decisions(self.root, run_id)
        self.assertEqual((decision["kind"], decision["ref"]), ("merge-feedback", url))
        source = autonomy.read_run(self.root, run_id)
        self.assertEqual(source["status"], "continued")
        self.assertEqual(autonomy.effective_mode(source), "human-gated")
        self.assertEqual(autonomy.read_decisions(self.root, run_id), before)
        rendered = (self.root / AUTO_FEATURE / "autonomous/record.md").read_text()
        for entry in before:
            self.assertIn(entry["id"], rendered)
        self.assertIn("agent-provisional", rendered)
        self.assertIn("human-gated", rendered)


class AutonomousBlockEngineTests(AutonomousEngineCase):
    """T046, T046a [SC-004, AC-011, AC-012, AC-013, AC-024, FR-021]: each block
    category stops the run before the next agent step, with its reason and
    recovery command."""

    def blocked_at(self, step: str, files: dict[str, str]) -> None:
        plan = _autonomous_plan()
        plan[step] = files
        self.layout(plan)

    def test_decision(self) -> None:
        self.blocked_at(
            "speckit-ballast-decide-plan",
            _block_draft("decision", "Should imports be visible before review?")
            | BLOCKED,
        )
        run_id, block, out = self.stopped()
        self.assertEqual(block["category"], "decision")
        self.assertIn("No safe, reversible default", block["condition"])
        self.assertIn("option: Keep -> Imports stay visible", out)
        points = [e["point"] for e in autonomy.read_decisions(self.root, run_id)]
        self.assertNotIn("plan", points)
        self.assertEqual(self.agent_commands(run_id)[-1], "speckit-ballast-decide")

    def test_contradiction(self) -> None:
        self.blocked_at(
            "speckit-ballast-clarify",
            _block_draft("contradiction", "The Issue requires both X and not-X")
            | BLOCKED,
        )
        run_id, block, _ = self.stopped()
        self.assertEqual(block["category"], "contradiction")
        self.assertIn("both X and not-X", block["condition"])
        self.assertEqual(self.agent_commands(run_id)[-1], "speckit-ballast-clarify")

    def test_several_outcomes_recommend_decomposition(self) -> None:
        """T046a: no provisional split, no Issue created."""
        self.blocked_at(
            "speckit-ballast-clarify",
            _block_draft(
                "decision",
                "The Issue holds three independent outcomes; decompose it into "
                "separate Issues before running it",
            )
            | BLOCKED,
        )
        run_id, block, _ = self.stopped()
        self.assertEqual(block["category"], "decision")
        self.assertIn("decompose", block["condition"])
        self.assertNotIn(
            "clarification",
            [e["point"] for e in autonomy.read_decisions(self.root, run_id)],
        )
        self.assertFalse([c for c in self.gh_calls() if c[:2] == ["issue", "create"]])
        self.assertFalse([c for c in self.gh_calls() if "POST" in c])
        self.assertEqual(self.agent_commands(run_id)[-1], "speckit-ballast-clarify")

    def test_review_finding(self) -> None:
        finding = {
            "id": "F-001",
            "severity": "high",
            "label": "spec-violation",
            "disposition": "resolved",
            "reason": "Fixed in the plan",
            "evidence": [],
        }
        self.blocked_at(
            "speckit-ballast-review-plan", _review("plan-review", "plan", [finding])
        )
        run_id, block, _ = self.stopped()
        self.assertEqual(block["category"], "review-finding")
        self.assertIn("F-001", block["condition"])
        self.assertEqual(self.agent_commands(run_id)[-1], "speckit-ballast-review")

    def test_limit(self) -> None:
        run_id, block, _ = self.stopped("--max-agent-steps", "3")
        self.assertEqual(block["category"], "limit")
        self.assertIn("agent step limit exhausted", block["condition"])
        self.assertEqual(len(self.agent_commands(run_id)), 3)
        refused = autonomy.read_steps(self.root, run_id)[-1]
        self.assertEqual((refused["ran"], refused["exit_code"]), (False, 5))
        self.assertTrue((self.root / ".specify/workflow-state" / run_id / "agents").is_dir())

    def test_tamper(self) -> None:
        self.unconfined()
        self.blocked_at("speckit-ballast-decide-intent", {"tamper": "ballast.toml"})
        run_id, block, _ = self.stopped()
        self.assertEqual(block["category"], "tamper")
        self.assertEqual(block["command"], "ballast discard-runs")
        self.assertTrue((self.root / "BALLAST_TAMPERED").exists())
        self.assertEqual(self.agent_commands(run_id)[-1], "speckit-ballast-decide")

    def test_unfinished_step(self) -> None:
        self.unconfined()
        self.blocked_at("speckit-ballast-decide-intent", {"kill-parent": ""})
        run_id, block, _ = self.stopped()
        self.assertEqual(block["category"], "unfinished-step")
        self.assertEqual(block["command"], "ballast discard-runs")
        # The killed step recorded nothing; nothing ran after it.
        self.assertEqual(self.agent_commands(run_id)[-1], "speckit-ballast-clarify")
        self.assertNotIn("intent", [e["point"] for e in autonomy.read_decisions(self.root, run_id)])

    def test_postcondition(self) -> None:
        plan = _autonomous_plan()
        del plan["speckit-tasks"]
        self.layout(plan)
        run_id, block, _ = self.stopped()
        self.assertEqual(block["category"], "postcondition")
        self.assertIn("tasks.md is missing", block["condition"])
        self.assertEqual(self.agent_commands(run_id)[-1], "speckit-tasks")

    def test_ineligible(self) -> None:
        self.blocked_at(
            "speckit-ballast-decide-intent",
            {
                f"{AUTO_FEATURE}/autonomous/drafts/intent.json": _draft(
                    "intent", f"{AUTO_FEATURE}/spec.md", privileged_actions=["deploy"]
                )
            },
        )
        run_id, block, _ = self.stopped()
        self.assertEqual(block["category"], "ineligible")
        self.assertIn("deploy", block["condition"])
        self.assertEqual(self.agent_commands(run_id)[-1], "speckit-ballast-decide")

    def test_forge(self) -> None:
        (self.gh_dir / "FAIL_pr_create").write_text("HTTP 422: Validation Failed\n")
        run_id, block, _ = self.stopped()
        self.assertEqual(block["category"], "forge")
        self.assertEqual(block["command"], f"ballast run publish {run_id}")

    def test_permission(self) -> None:
        (self.gh_dir / "FAIL_pr_create").write_text(
            "gh: To use GitHub CLI, authenticate with gh auth login\n"
        )
        run_id, block, _ = self.stopped()
        self.assertEqual(block["category"], "permission")
        self.assertEqual(block["command"], f"ballast run publish {run_id}")

    def test_interrupted(self) -> None:
        self.unconfined()
        os.environ["FAKE_INTERRUPT_PID"] = str(os.getpid())
        self.blocked_at("speckit-plan", {f"{AUTO_FEATURE}/plan.md": PLAN, "interrupt": ""})
        code, out, err, run_id = self.start()
        self.assertEqual(code, 130, out + err)
        # The wrapper outlives the killed engine briefly; let its check finish.
        marker = autonomy.state_dir(self.root) / "in-progress"
        deadline = time.monotonic() + 30
        while marker.exists() and time.monotonic() < deadline:
            time.sleep(0.2)
        block = autonomy.read_block(self.root, run_id)
        self.assertEqual(block["category"], "interrupted")
        self.assertEqual(autonomy.read_run(self.root, run_id)["status"], "stopped")
        self.assertIn(f"Next: {block['command']}", out)
        self.assertNotIn("speckit-ballast-review", self.agent_commands(run_id))

    def test_trust(self) -> None:
        """A changed trusted input stops recovery before any run code executes.

        No `trust` block is written: the launcher refuses before run.py, so the
        stopped run keeps its block (DEC-0002).
        """
        plan = _autonomous_plan()
        del plan["speckit-plan"]
        self.layout(plan)
        run_id, block, _ = self.stopped()
        sys.path.insert(0, str(ROOT / "tools/spec_workflow"))
        try:
            import launcher  # noqa: PLC0415
        finally:
            sys.path.pop(0)
        previous = Path.cwd()
        os.chdir(self.root)
        try:
            with redirect_stdout(io.StringIO()):
                self.assertEqual(launcher.main(["trust"]), 0)
            workflow = self.root / ".specify/workflows/ballast-continue/workflow.yml"
            workflow.write_text(workflow.read_text() + "# changed\n")
            err = io.StringIO()
            with redirect_stderr(err):
                code = launcher.main(
                    ["run", "continue", run_id, "--reason", "block-resolved", "--ref", "x"]
                )
        finally:
            os.chdir(previous)
        self.assertEqual(code, 2)
        self.assertIn("ballast: refusing:", err.getvalue())
        self.assertEqual(self.run_ids(), [run_id])
        self.assertEqual(autonomy.read_run(self.root, run_id)["status"], "stopped")
        self.assertEqual(autonomy.read_block(self.root, run_id), block)


class AutonomousConfinementEngineTests(AutonomousEngineCase):
    """T048 [AC-016, SC-005, FR-003]: agent writes cannot change the mode,
    eligibility, limits, the decision log or the committed projections."""

    ATTEMPTS = (
        ("toml", "echo 'risk = [\"R3\"]' >> ballast.toml"),
        ("run", "echo '{}' > \"$RUN_DIR/run.json\""),
        ("log", "echo '{}' >> \"$RUN_DIR/decisions.jsonl\""),
        (
            "ballast",
            "python3 -I -S .ballast/spec_workflow/run.py start --mode autonomous "
            "-i issue=27 -i idea=x -i feature_directory=specs/27-demo-run "
            "-i integration=claude",
        ),
        ("publish", "python3 -I -S .ballast/spec_workflow/run.py publish \"$RUN_ID\""),
    )

    def attempt_script(self) -> str:
        state = autonomy.state_dir(self.root)
        lines = [f'RUN_ID="$SPECKIT_WORKFLOW_RUN_ID"; RUN_DIR="{state}/runs/$RUN_ID"']
        for name, command in self.ATTEMPTS:
            lines.append(f"({command}) >/dev/null 2>&1; echo {name}=$?")
        return "\n".join(lines) + "\n"

    def attempts(self, run_id: str, command: str) -> dict[str, str]:
        agents = self.root / ".specify/workflow-state" / run_id / "agents"
        log = min(p for p in agents.iterdir() if f"-{command}-" in p.name)
        text = (log / "stdout.log").read_text()
        found = dict(
            line.split("=", 1) for line in text.splitlines() if "=" in line
        )
        return {name: found.get(name, "missing") for name, _ in self.ATTEMPTS}

    def test_agent_writes_change_nothing_operator_side(self) -> None:
        installed = self.git("rev-parse", "HEAD").strip()
        for integration in ("claude", "codex"):
            with self.subTest(integration=integration):
                plan = _autonomous_plan()
                plan["speckit-ballast-decide-scope"] |= {"exec": self.attempt_script()}
                self.layout(plan)
                toml = (self.root / "ballast.toml").read_bytes()
                code, out, err, run_id = self.start(integration=integration)
                self.assertEqual(code, 0, out + err)
                results = self.attempts(run_id, "speckit-ballast-decide")
                self.assertNotIn("0", results.values(), results)
                self.assertNotIn("missing", results.values(), results)
                self.assertEqual((self.root / "ballast.toml").read_bytes(), toml)
                record = autonomy.read_run(self.root, run_id)
                self.assertEqual(autonomy.effective_mode(record), "autonomous")
                self.assertTrue(record["eligibility"]["eligible"])
                self.assertEqual(record["limits"]["max_agent_steps"], 30)
                self.assertEqual(record["integration"], integration)
                self.assertEqual(self.run_ids(), [run_id])
                self.assertEqual(record["status"], "published")
                # Reset for the next integration: a fresh branch and state.
                shutil.rmtree(autonomy.state_dir(self.root))
                self.git("reset", "-q", "--hard", installed)
                self.git("clean", "-qfd", "--", "specs", "src", "tests")
                self.git("push", "-q", "origin", "--delete", "27-demo-run")

    def test_edited_record_fails_the_next_recorder(self) -> None:
        plan = _autonomous_plan()
        plan["speckit-ballast-decide-plan"] |= {
            "tamper": f"{AUTO_FEATURE}/autonomous/record.md"
        }
        self.layout(plan)
        run_id, block, _ = self.stopped()
        self.assertEqual(block["category"], "postcondition")
        self.assertIn("edited outside the recorder", block["condition"])
        self.assertNotIn(
            "plan", [e["point"] for e in autonomy.read_decisions(self.root, run_id)]
        )

    def test_edited_provisional_intent_fails_the_next_validator(self) -> None:
        plan = _autonomous_plan()
        # Rebind the provisional block to another spec version.
        forge = (
            "import re; p = '" + AUTO_FEATURE + "/intent.md'; t = open(p).read(); "
            "open(p, 'w').write(re.sub('sha256:[0-9a-f]{64}', 'sha256:' + '0' * 64, t))"
        )
        plan["speckit-plan"] |= {"exec": f'python3 -c "{forge}"'}
        self.layout(plan)
        run_id, block, _ = self.stopped()
        self.assertEqual(block["category"], "postcondition")
        self.assertIn("intent", block["condition"])
        self.assertEqual(self.agent_commands(run_id)[-1], "speckit-plan")
