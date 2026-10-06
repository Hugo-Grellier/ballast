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
import re
import select
import shutil
import signal
import subprocess
import sys
import time
import tomllib
import unittest
from contextlib import nullcontext, redirect_stderr, redirect_stdout, suppress
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from typing import ClassVar
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


def setUpModule() -> None:  # noqa: D103
    isolate_operator_state()


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

    def test_gated_run_accepts_only_registered_approvals(self) -> None:
        # Issue #29: an agent step can write spec.md and a well-formed approval
        # block, but not the operator state record-intent registers it in.
        run = self.repo.root / ".specify/workflows/runs/abc123"
        run.mkdir(parents=True)
        (run / "inputs.json").write_text(
            json.dumps({"inputs": {"feature_directory": FEATURE}})
        )
        self.repo.write("spec.md", SPEC)
        self.repo.write("plan.md", PLAN)
        gated = ("--run", "abc123")
        self.assertEqual(self.repo.check("record-intent", *gated).returncode, 0)
        self.assertEqual(self.repo.check("plan", *gated).returncode, 0)
        intent = self.repo.root / FEATURE / "intent.md"
        approved = intent.read_text()

        # Forged: the agent changes the spec and runs record-intent with
        # operator state of its own choosing.
        self.repo.write("spec.md", SPEC + "\nMore scope.\n")
        forged = {**os.environ, "XDG_STATE_HOME": str(operator_state(self))}
        self.assertEqual(self.repo.check("record-intent", env=forged).returncode, 0)
        for check in ("intent", "plan"):
            result = self.repo.check(check, *gated)
            self.assertNotEqual(result.returncode, 0, check)
            self.assertIn("did not register", result.stderr)

        # Where operator state is unwritable (an agent sandbox), record-intent
        # fails and leaves intent.md alone.
        locked = operator_state(self)
        locked.chmod(0o500)
        self.addCleanup(locked.chmod, 0o700)
        sandboxed = {**os.environ, "XDG_STATE_HOME": f"{locked}/state"}
        before = intent.read_text()
        self.assertNotEqual(
            self.repo.check("record-intent", env=sandboxed).returncode, 0
        )
        self.assertEqual(intent.read_text(), before)
        # A temp directory is refused outright: agents can write it.
        with TemporaryDirectory() as temp:
            in_temp = {**os.environ, "XDG_STATE_HOME": temp}
            result = self.repo.check("record-intent", env=in_temp)
        self.assertIn("agents can write", result.stderr)
        self.assertEqual(intent.read_text(), before)

        # Upgrade path for an in-flight run approved before registration
        # existed: the operator re-approves with --feature, then resumes.
        self.repo.write("spec.md", SPEC)
        intent.write_text(approved)
        self.assertEqual(self.repo.check("intent").returncode, 0)
        self.assertEqual(self.repo.check("intent", *gated).returncode, 0)
        intent.write_text(approved.replace("Approved**: ", "Approved**: 0"))
        self.assertIn("did not register", self.repo.check("intent", *gated).stderr)
        self.repo.approve()
        self.assertEqual(self.repo.check("plan", *gated).returncode, 0)

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
sys.exit(int(os.environ.get("FAKE_EXIT", "0")))
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
        # systemd-run resolves only outside working trees and temp roots.
        trusted = trusted_directory(self)
        _fake_systemd(trusted)
        for name in ("claude", "codex"):
            (fake / name).write_text(FAKE_CLI)
            (fake / name).chmod(0o755)
        self.env = {
            **os.environ,
            "PATH": os.pathsep.join([str(trusted), str(fake), os.environ["PATH"]]),
            "FAKE_SYSTEMCTL_LOG": str(self.root / "systemctl.log"),
            "FAKE_ARGV": str(self.root / "argv.json"),
            "SPECKIT_WORKFLOW_RUN_ID": "run42",
            "XDG_STATE_HOME": str(operator_state(self)),
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
                "--config",
                "sandbox_workspace_write.writable_roots=[]",
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

    def test_login_failure_is_reported_as_an_authentication_block(self) -> None:
        """#65: the CLI's own login error becomes a distinct, explained exit."""
        for message in (
            (
                "Failed to authenticate: OAuth session expired and could not be "
                "refreshed"
            ),
            "Failed to authenticate. API Error: 401 OAuth access token is invalid.",
        ):
            with self.subTest(message=message):
                result = self.run_wrapper(
                    "claude",
                    "-p",
                    "/speckit-implement",
                    FAKE_STDOUT=message,
                    FAKE_EXIT="1",
                )
                self.assertEqual(result.returncode, 6)
                self.assertIn("claude /login", result.stderr)

    def test_login_text_from_a_successful_step_is_not_an_auth_failure(self) -> None:
        result = self.run_wrapper(
            "claude",
            "-p",
            "/speckit-implement",
            FAKE_STDOUT="Failed to authenticate",
            FAKE_EXIT="0",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        failed = self.run_wrapper(
            "claude", "-p", "/speckit-implement", FAKE_STDOUT="boom", FAKE_EXIT="1"
        )
        self.assertEqual(failed.returncode, 1)

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

    def plant_systemd_run(self) -> tuple[Path, Path]:
        planted = self.root / "planted-bin"  # In the checkout and a temp root.
        planted.mkdir()
        marker = self.root / "planted-ran"
        (planted / "systemd-run").write_text(f"#!/bin/sh\ntouch {marker}\nexit 1\n")
        (planted / "systemd-run").chmod(0o755)
        return planted, marker

    def test_planted_systemd_run_never_runs(self) -> None:
        """Fable-3: systemd-run resolves like gh and git (ADR-0003)."""
        planted, marker = self.plant_systemd_run()
        result = self.run_wrapper(
            "claude",
            "-p",
            "/speckit-plan",
            PATH=f"{planted}{os.pathsep}{self.env['PATH']}",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(marker.exists())

    def test_only_an_untrusted_systemd_run_refuses(self) -> None:
        planted, marker = self.plant_systemd_run()
        python = self.root / "python-only"
        python.mkdir()
        (python / "python3").symlink_to(sys.executable)
        result = self.run_wrapper(
            "claude",
            "-p",
            "/speckit-plan",
            PATH=os.pathsep.join(
                [str(planted), str(self.root / "fake-bin"), str(python)]
            ),
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("working tree or temp directory", result.stderr)
        self.assertFalse(marker.exists())

    def test_refuses_without_a_systemd_user_manager(self) -> None:
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
        (state,) = (Path(self.env["XDG_STATE_HOME"]) / "ballast").iterdir()
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

    def test_agent_git_refuses_writing_and_running_options(self) -> None:
        # Issue #34: the allowlist matches command text; `--out''put=` and
        # `git diff*` matching `difftool -x CMD` slipped past it.
        target = self.root / "written"
        (self.root / "fake-bin/claude").write_text(
            "#!/usr/bin/env python3\n"
            "import subprocess\n"
            f"for args in (['--version'], ['diff', '--output={target}'],"
            " ['difftool', '-y', '-x', 'true']):\n"
            "    r = subprocess.run(['git', *args], capture_output=True, text=True)\n"
            "    print(r.returncode, r.stdout.strip(), r.stderr.strip())\n"
        )
        result = self.run_wrapper("claude", "-p", "/speckit-plan")
        self.assertEqual(result.returncode, 0, result.stderr)
        version, output, difftool = result.stdout.splitlines()[:3]
        self.assertRegex(version, r"^0 git version ")
        self.assertRegex(output, r"^128 .*`git --output=.*` is not available")
        self.assertRegex(difftool, r"^128 .*`git difftool` is not available")
        self.assertFalse(target.exists())

    def test_git_guard_sees_arguments_after_shell_quoting(self) -> None:
        guard = ROOT / "tools/spec_workflow/guard/git"
        echo = shutil.which("echo")
        env = {"PATH": "/usr/bin:/bin", "BALLAST_GIT": str(echo)}
        refused = subprocess.run(  # noqa: S603
            ["/bin/sh", "-c", f"{guard} diff --out''put=x"],
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(refused.returncode, 128, refused.stdout)
        passed = subprocess.run(  # noqa: S603
            [guard, "log", "-p", "--stat"],
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(passed.stdout, "log -p --stat\n")
        unset = subprocess.run(  # noqa: S603
            [guard, "status"],
            env={"PATH": "/usr/bin:/bin"},
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(unset.returncode, 0)
        self.assertIn("no trusted git", unset.stderr)

    def test_claude_git_rules_match_whole_subcommands(self) -> None:
        settings = json.loads(
            (ROOT / "tools/spec_workflow/claude-settings.json").read_text()
        )
        rules = [
            rule[len("Bash(git ") : -1]
            for rule in settings["permissions"]["allow"]
            if rule.startswith("Bash(git ")
        ]
        self.assertTrue(rules)
        for rule in rules:
            self.assertRegex(rule, r"^[a-z-]+( \*)?$")
        self.assertIn("Edit(./.git/**)", settings["permissions"]["deny"])

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
        # systemd-run resolves only outside working trees and temp roots.
        trusted = trusted_directory(self)
        _fake_systemd(trusted)
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
            "XDG_STATE_HOME": str(operator_state(self)),
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
        fake = trusted_directory(self)
        _fake_systemd(fake)
        self.env = {
            **os.environ,
            "PATH": f"{fake}{os.pathsep}{os.environ['PATH']}",
            "XDG_STATE_HOME": str(operator_state(self)),
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
        (state_root := Path(self.env["XDG_STATE_HOME"]) / "ballast").mkdir(parents=True)
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
                "refusal": (
                    "no trusted baseline for this checkout; review its protected "
                    "inputs (.ballast/spec_workflow, .specify, .venv, .git), then run "
                    "`ballast trust`"
                ),
            },
        )
        self.assertEqual(list(state.iterdir()), [])
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

    def test_no_baseline_names_the_inputs_to_review(self) -> None:
        # #15 AC-002: only the protected inputs that exist are listed.
        self.assert_refused(
            "no trusted baseline for this checkout; review its protected inputs "
            "(.ballast/spec_workflow, .specify, .venv, .git), then run "
            "`ballast trust`"
        )
        shutil.rmtree(self.root / ".venv")
        (self.root / ".git").unlink()
        (self.root / "ballast.toml").write_text('[standard]\nref = "vA"\n')
        self.assert_refused(
            "review its protected inputs (ballast.toml, .ballast/spec_workflow, "
            ".specify), then run `ballast trust`"
        )

    def test_uninstalled_checkout_is_refused_without_writing(self) -> None:
        # #15 AC-005, plan review F-003: no state directory, no checkout.lock.
        (self.tools / "run.py").unlink()
        state_home = Path(self.env["XDG_STATE_HOME"])
        message = (
            "ballast: refusing: nothing is installed in this checkout; run "
            "`ballast setup`, or `ballast run`, `ledger` or `intake` to prepare it "
            "from a verified installation on this machine\n"
        )
        commands = (
            ("trust",),
            ("discard-runs",),
            ("run", "start"),
            ("ledger", "check", "r1"),
            ("intake", "--repo", "o/r"),
        )
        for args in commands:
            with self.subTest(args=args):
                result = self.launch(*args)
                self.assertEqual((result.returncode, result.stderr), (2, message))
                self.assertEqual(list(state_home.iterdir()), [])
        # An existing state directory gains no lock from trust or discard-runs.
        key = hashlib.sha256(str(self.root.resolve()).encode()).hexdigest()[:16]
        state = state_home / "ballast" / key
        state.mkdir(parents=True)
        for args in commands[:2]:
            with self.subTest(args=args, state="exists"):
                result = self.launch(*args)
                self.assertEqual((result.returncode, result.stderr), (2, message))
                self.assertEqual(list(state.iterdir()), [])
        self.assertFalse(self.ran.exists())
        self.assertTrue((self.root / ".specify/workflows/runs/r1").is_dir())

    def test_unfinished_step_is_discarded_on_an_uninstalled_checkout(self) -> None:
        # #15 review ENG-001: setup and preparation refuse while the marker
        # exists, so discard-runs must still clear it with nothing installed.
        (self.tools / "run.py").unlink()
        key = hashlib.sha256(str(self.root.resolve()).encode()).hexdigest()[:16]
        state = Path(self.env["XDG_STATE_HOME"]) / "ballast" / key
        state.mkdir(parents=True)
        (state / "in-progress").write_text("ballast-agent-r1-step.scope\n")
        result = self.launch("discard-runs")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((state / "in-progress").exists())
        self.assertFalse((self.root / ".specify/workflows/runs").exists())
        self.assertEqual(self.launch("trust").returncode, 2)

    def test_tamper_marker_and_unfinished_step_are_refused(self) -> None:
        self.assertEqual(self.launch("trust").returncode, 0)
        (self.root / "BALLAST_TAMPERED").write_text("x\n")
        self.assert_refused("BALLAST_TAMPERED")
        self.assertEqual(self.launch("trust").returncode, 2)
        (self.root / "BALLAST_TAMPERED").unlink()
        (state,) = (Path(self.env["XDG_STATE_HOME"]) / "ballast").iterdir()
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

    def test_unfinished_step_refusal_names_the_run_and_step(self) -> None:
        """#20 AC-013, FR-012: the marker's unit names the run and the step."""
        self.assertEqual(self.launch("trust").returncode, 0)
        (state,) = (Path(self.env["XDG_STATE_HOME"]) / "ballast").iterdir()
        marker = state / "in-progress"
        marker.write_text(
            "ballast-agent-ab12cd34-20261006T101010123456Z-plan-claude.scope\n"
        )
        self.assert_refused(
            "an agent step is active or did not finish: run ab12cd34, step "
            "20261006T101010123456Z-plan-claude; wait for it to end, or if no step "
            "is running, run `ballast discard-runs`"
        )
        self.assert_refused("did not finish")
        for content in ("ballast-agent-r1-step.scope\n", "garbage\n", ""):
            with self.subTest(content=content):
                marker.write_text(content)
                self.assert_refused(
                    "an agent step did not finish its protected-file check"
                )

    def trusted_state(self) -> Path:
        self.assertEqual(self.launch("trust").returncode, 0)
        (state,) = (Path(self.env["XDG_STATE_HOME"]) / "ballast").iterdir()
        return state

    def hold(self, state: Path, mode: str) -> subprocess.Popen[str]:
        holder = subprocess.Popen(  # noqa: S603
            [sys.executable, "-c", HOLD_LOCK, str(state / "checkout.lock"), mode],
            stdout=subprocess.PIPE,
            text=True,
        )
        self.addCleanup(holder.stdout.close)
        self.addCleanup(holder.wait)
        self.addCleanup(holder.kill)
        self.assertEqual(holder.stdout.readline(), "held\n")
        return holder

    def test_unfinished_setup_is_refused(self) -> None:
        # AC-005: every launcher command names `ballast setup` as the recovery.
        state = self.trusted_state()
        (state / "setup-attempt.json").write_text("{}\n")
        unfinished = "setup did not finish in this checkout; run `ballast setup`"
        for args in (
            ("run", "resume", "r1"),
            ("ledger", "check", "r1"),
            ("intake", "--repo", "o/r"),
            ("trust",),
            ("discard-runs",),
        ):
            with self.subTest(args=args):
                result = self.launch(*args)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn(unfinished, result.stderr)
        self.assertFalse(self.ran.exists())
        self.assertTrue((self.root / ".specify/workflows/runs/r1").is_dir())
        self.assertIn(unfinished, self.status()["refusal"])
        # A switch killed after moving the workflow tools out still names setup.
        (self.tools / "run.py").unlink()
        result = self.launch("run", "resume", "r1")
        self.assertEqual(result.returncode, 2)
        self.assertIn(unfinished, result.stderr)
        self.assertIn(unfinished, self.status()["refusal"])

    def test_running_setup_is_reported_as_running(self) -> None:
        # F-005, F-006: the lock is checked before the journal, also for trust.
        state = self.trusted_state()
        (state / "setup-attempt.json").write_text("{}\n")
        self.hold(state, "exclusive")
        for args in (("run", "resume", "r1"), ("trust",), ("discard-runs",)):
            with self.subTest(args=args):
                result = self.launch(*args)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn(
                    "ballast setup is running in this checkout", result.stderr
                )
        self.assertFalse(self.ran.exists())

    def test_workflow_tool_keeps_the_shared_lock(self) -> None:
        # FR-014: a setup started while `run` works must see the checkout held.
        state = self.trusted_state()
        (self.tools / "run.py").write_text(
            "import fcntl, os, sys\n"
            f"fd = os.open({str(state / 'checkout.lock')!r}, os.O_RDWR)\n"
            "try:\n    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)\n"
            "    held = 'free'\nexcept BlockingIOError:\n    held = 'held'\n"
            f"open({str(self.ran)!r}, 'w').write(held)\n"
        )
        self.assertEqual(self.launch("trust").returncode, 0)
        result = self.launch("run", "resume", "r1")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.ran.read_text(), "held")

    def test_pinned_and_installed_versions_differ(self) -> None:
        # AC-008, F-003: a valid record names both versions; a stale one is ignored.
        (self.root / "ballast.toml").write_text('[standard]\nref = "vB"\n')
        (self.root / ".ballast/.setup-version").write_text("fp A\n")
        state = self.trusted_state()
        record = {"schema": 1, "ref": "vA", "fingerprint": "fp A", "files": {}}
        (state / "installation.json").write_text(json.dumps(record))
        message = (
            'pinned vB, installed vA: restore ref = "vA" in ballast.toml, '
            "or fix the cause and rerun `ballast setup`"
        )
        self.assert_refused(message)
        self.assertEqual(self.status()["refusal"], message)
        (self.root / ".ballast/.setup-version").write_text("fp older\n")
        self.assertEqual(self.status(), {"installed": True, "refusal": None})


def _ids(node: object) -> list[str]:
    if isinstance(node, dict):
        own = [node["id"]] if isinstance(node.get("id"), str) else []
        return own + [i for value in node.values() for i in _ids(value)]
    if isinstance(node, list):
        return [i for value in node for i in _ids(value)]
    return []


class RunFormatTests(unittest.TestCase):
    """A version declares the run format it writes and the ones it resumes."""

    # What saved run state depends on, per format: the Spec Kit version and
    # every shipped workflow's step IDs. Record a new entry only together with
    # a new [runs] format (and a decision on [runs] resumes).
    BASIS: ClassVar[dict[str, str]] = {
        # ballast-autonomous 1.2.0 (#21) added fix steps; a run started under
        # 1.1.0 still resumes from its own workflow copy (#21 R19).
        "ballast-run/1": (
            "1aced2c4b3f9cef84956b39304132dcc0f096b909542420370e693ca922dabdc"
        ),
    }

    def manifest(self) -> dict:
        return tomllib.loads((ROOT / "tools/cli.toml").read_text())

    def test_run_format_matches_the_manifest(self) -> None:
        sys.path.insert(0, str(ROOT / "tools/spec_workflow"))
        try:
            import run  # noqa: PLC0415
        finally:
            sys.path.pop(0)
        manifest = self.manifest()
        self.assertEqual(run.RUN_FORMAT, manifest["runs"]["format"])
        self.assertIn(run.RUN_FORMAT, manifest["runs"]["resumes"])
        self.assertTrue(manifest["setup"]["recoverable"])

    def test_format_changes_with_what_runs_depend_on(self) -> None:
        version = re.search(
            r'^VERSION = "([^"]+)"', (ROOT / "tools/setup").read_text(), re.MULTILINE
        )
        digest = hashlib.sha256(version.group(1).encode())
        for path in sorted(
            (ROOT / "templates/spec-kit/workflows").glob("*/workflow.yml")
        ):
            steps = "\0".join(_ids(yaml.safe_load(path.read_text())))
            digest.update(path.parent.name.encode() + b"\0" + steps.encode() + b"\0")
        self.assertEqual(
            self.BASIS.get(self.manifest()["runs"]["format"]),
            digest.hexdigest(),
            "the Spec Kit version or a shipped workflow's step IDs changed: decide "
            "whether saved runs still resume, then bump [runs] format (and "
            "RUN_FORMAT in run.py) or record the new basis for the same format",
        )


HOLD_LOCK = """\
import fcntl, os, sys, time
fd = os.open(sys.argv[1], os.O_RDWR | os.O_CREAT, 0o600)
fcntl.flock(fd, fcntl.LOCK_EX if sys.argv[2] == "exclusive" else fcntl.LOCK_SH)
print("held", flush=True)
time.sleep(120)
"""


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

    def test_agent_writable_state_directory_is_refused(self) -> None:
        # Issue #34: the trust baseline and in-progress marker live there.
        with TemporaryDirectory() as directory:
            root = Path(directory) / "checkout"
            (root / ".ballast/spec_workflow").mkdir(parents=True)
            (root / ".ballast/spec_workflow/run.py").write_text("")
            for state in (str(root / "state"), str(Path(directory) / "s"), "rel"):
                for command in (["trust"], ["status", "--json"]):
                    result = subprocess.run(  # noqa: S603
                        [
                            sys.executable,
                            "-IS",
                            str(ROOT / "tools/spec_workflow/launcher.py"),
                            *command,
                        ],
                        cwd=root,
                        capture_output=True,
                        text=True,
                        check=False,
                        env={**os.environ, "XDG_STATE_HOME": state},
                    )
                    output = result.stdout + result.stderr
                    self.assertIn("agents can write", output, (state, command))
                    self.assertNotEqual(command == ["trust"], result.returncode == 0)
            self.assertEqual(
                sorted(p.name for p in Path(directory).rglob("*")),
                sorted(["checkout", ".ballast", "spec_workflow", "run.py"]),
            )


def _steps() -> list[dict[str, object]]:
    return yaml.safe_load(WORKFLOW.read_text())["steps"]


class WorkflowOrderTests(unittest.TestCase):
    """Every gate and consumer is reachable only after its contract check."""

    def test_producers_are_validated_before_the_next_step(self) -> None:
        ids = [step["id"] for step in _steps()]
        for producer, validator in (
            ("discover", "validate-discovery"),
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
            (root / ".ballast/feature_intake.py").write_text("")
            for command in ("run", "ledger", "intake"):
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
                if command == "intake":
                    # The pinned standard's helper acts with the operator's gh
                    # authority; a checkout copy is never executed (#38).
                    self.assertEqual(calls[0][2], str(ROOT / "tools/feature_intake.py"))
            with (
                patch.object(launcher.Path, "cwd", return_value=root),
                patch.dict(os.environ, {"XDG_STATE_HOME": str(operator_state(self))}),
                patch.object(launcher.os, "execv") as execv,
                patch("sys.stderr"),
            ):
                self.assertEqual(launcher.main(["intake", "x"]), 2)
            execv.assert_not_called()


FAKE_INTEGRATION = """#!/usr/bin/env python3
import os, shutil, sys
prompt = sys.argv[2]
if "speckit-ballast-discover" in prompt and os.environ.get("FAKE_BRIEF"):
    os.makedirs("specs/102-demo-import", exist_ok=True)
    shutil.copy(os.environ["FAKE_BRIEF"], "specs/102-demo-import/discovery.md")
if "speckit-specify" in prompt and os.environ.get("FAKE_SPEC"):
    os.makedirs("specs/102-demo-import", exist_ok=True)
    shutil.copy(os.environ["FAKE_SPEC"], "specs/102-demo-import/spec.md")
"""


def _gated_brief() -> str:
    """Write a settled human-gated brief citing only the Issue: nothing to ask."""
    issue = "Issue #102 body"
    return brief_text(
        {
            "Sources": f"- S-1: {issue}",
            "Non-goals": "- Audio import [I]",
            "Constraints": f"- Text only [S: {issue}]",
            "Decisions": decision(
                "D-01", "settled", sources=f"[S: {issue}]", resolution=f"[S: {issue}]"
            ),
        }
    )


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
        # Specs written after discovery are traced (#16).
        (root / "spec-fixture.md").write_text(TRACED_SPEC)
        (root / "brief-fixture.md").write_text(_gated_brief())
        self.env = {
            **os.environ,
            "BALLAST_SPEC_WORKFLOW": "1",
            "SPECKIT_INTEGRATION_CLAUDE_EXECUTABLE": str(agent),
            "FAKE_BRIEF": str(root / "brief-fixture.md"),
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
        self.assertEqual(results["validate-discovery"]["status"], "completed")
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
        # These tests cover archiving and import; the branch check has its own.
        self.enterContext(
            patch.object(
                _run_module().branch_sync, "synchronize", return_value=_sync_outcome()
            )
        )
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

    def test_launcher_records_the_run_format_at_start(self) -> None:
        # FR-016, AC-017: a later preview reads which format this run uses.
        sys.path.insert(0, str(ROOT / "tools/spec_workflow"))
        try:
            import run  # noqa: PLC0415
        finally:
            sys.path.pop(0)
        recorded: list[dict] = []

        def launch(*_args: object, **_kwargs: object) -> SimpleNamespace:
            target = run.archive_dir(self.repo.root, "run43xxx") / "run-format.json"
            recorded.append(json.loads(target.read_text()))
            return SimpleNamespace(returncode=0)

        with (
            patch.object(run, "ROOT", self.repo.root),
            patch.object(run.shutil, "which", return_value="/bin/specify"),
            patch.object(
                run.uuid, "uuid4", return_value=SimpleNamespace(hex="run43xxx")
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
        self.assertEqual(recorded, [{"schema": 1, "format": run.RUN_FORMAT}])

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
COMMANDS = ROOT / "templates/spec-kit/extensions/ballast/commands"
# SHA-256 of ballast-feature's workflow.yml (1.2.0, with #16's discovery):
# Autonomous work must not change it unnoticed.
FEATURE_WORKFLOW_DIGEST = (
    "f96ebfcce18e449e8b5aed949f16e85f0144bc611c6eeb953d7995996ec56c50"
)
# Both workflows' clarify step (#16): no decision of the brief is asked again.
CLARIFY_ARGS = (
    "Read {{ inputs.feature_directory }}/discovery.md first. Do not reopen or ask "
    "again a decision the brief settled, answered or assumed; ask only about a "
    "new contradiction it does not cover."
)
# contracts/workflow.md, ballast-autonomous: (step id, check or command, args).
AUTONOMOUS_STEPS = (
    ("preflight", "autonomous-preflight", None),
    ("decide-scope", "speckit.ballast.decide", "scope"),
    ("record-scope", "record-decision", "scope"),
    ("discover", "speckit.ballast.discover", "autonomous"),
    ("record-discovery", "record-decision", "clarification"),
    ("validate-discovery", "discovery", None),
    ("specify", "speckit.specify", None),
    ("validate-spec", "spec", None),
    ("clarify", "speckit.ballast.clarify", CLARIFY_ARGS),
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
    ("checks-implementation", "run-checks", "--feedback"),
    ("review-implementation", "speckit.ballast.review", "implementation"),
    ("review-specialists", "speckit.ballast.review", "specialists"),
    ("record-implementation-review", "record-decision", "implementation-review"),
    # #21: three fix cycles, each skipped while the fix state is idle.
    *(
        step
        for n in (1, 2, 3)
        for step in (
            (f"fix-{n}", "speckit.ballast.fix", None),
            (f"record-fix-{n}", "record-fix", None),
            (f"checks-fix-{n}", "run-checks", "--feedback"),
            (f"review-fix-{n}", "speckit.ballast.review", "implementation-recheck"),
            (
                f"review-specialists-fix-{n}",
                "speckit.ballast.review",
                "specialists-recheck",
            ),
            (f"record-fix-review-{n}", "record-decision", "implementation-review"),
        )
    ),
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
REVIEW_STEPS = (
    "review-plan",
    "review-implementation",
    "review-specialists",
    *(
        f"{kind}-{n}"
        for n in (1, 2, 3)
        for kind in ("review-fix", "review-specialists-fix")
    ),
)
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
                    (
                        step["id"],
                        step["command"],
                        args if "ballast" in step["command"] else None,
                    )
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
            ("discover", "record-discovery"),
            ("record-discovery", "validate-discovery"),
            ("validate-discovery", "specify"),
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
            ("validate-implementation", "checks-implementation"),
            *(
                pair
                for n in (1, 2, 3)
                for pair in (
                    (f"fix-{n}", f"record-fix-{n}"),
                    (f"record-fix-{n}", f"checks-fix-{n}"),
                    (f"review-specialists-fix-{n}", f"record-fix-review-{n}"),
                )
            ),
            ("resolve-decisions", "record-resolutions"),
            ("reconcile-spec", "record-reconciliation"),
            ("decide-final", "record-final"),
        ):
            self.assertEqual(ids[ids.index(producer) + 1], check, producer)

    def test_feature_workflow_is_unchanged(self) -> None:
        self.assertEqual(
            hashlib.sha256(WORKFLOW.read_bytes()).hexdigest(), FEATURE_WORKFLOW_DIGEST
        )

    def test_version_and_step_order(self) -> None:
        """#21 T014: 1.2.0, and the step order resume re-enters by."""
        self.assertEqual(self.doc["workflow"]["version"], "1.2.0")
        self.assertEqual(
            tuple(step["id"] for step in self.steps), autonomy.AUTONOMOUS_STEPS
        )
        shell = {s["id"] for s in self.steps if s.get("type") == "shell"}
        self.assertEqual(shell, set(autonomy.AUTONOMOUS_SHELL_STEPS))

    def test_every_human_gated_check_is_kept(self) -> None:
        """#21 T014 [AC-005, FR-006]: choosing Autonomous skips no check."""
        feature_checks = {
            _shell_check(step["run"])
            for step in _steps()
            if step.get("type") == "shell"
        }
        autonomous = {
            _shell_check(step["run"])
            for step in self.steps
            if step.get("type") == "shell"
        }
        # The human gates' recorders become provisional recorders; every
        # validator and postcondition of ballast-feature is still present.
        for check, _extra in feature_checks:
            if check in {"record-intent", "preflight"}:
                continue
            with self.subTest(check=check):
                self.assertIn(check, {c for c, _ in autonomous})
        commands = {s["command"] for s in self.steps if "command" in s}
        registered = set(
            re.findall(
                r'name: "([^"]+)"', (COMMANDS.parent / "extension.yml").read_text()
            )
        )
        for command in commands:
            if command.startswith("speckit.ballast."):
                self.assertIn(command, registered)


class DiscoveryWorkflowTests(unittest.TestCase):
    """#16 T010 [AC-001], T020 [AC-007], T033 [AC-014]: the discover steps."""

    def setUp(self) -> None:
        self.feature = yaml.safe_load(WORKFLOW.read_text())
        self.autonomous = yaml.safe_load(AUTONOMOUS_WORKFLOW.read_text())

    def steps(self, doc: dict) -> dict[str, dict]:
        return {step["id"]: step for step in doc["steps"]}

    def test_versions(self) -> None:
        self.assertEqual(self.feature["workflow"]["version"], "1.2.0")
        # 1.2.0 adds #21's fix loop after #16's discovery.
        self.assertEqual(self.autonomous["workflow"]["version"], "1.2.0")

    def test_feature_discovers_after_the_scope_gate(self) -> None:
        ids = [step["id"] for step in self.feature["steps"]]
        start = ids.index("scope-gate")
        self.assertEqual(
            ids[start : start + 4],
            ["scope-gate", "discover", "validate-discovery", "specify"],
        )
        steps = self.steps(self.feature)
        self.assertEqual(steps["discover"]["command"], "speckit.ballast.discover")
        self.assertEqual(steps["discover"]["input"]["args"], "human-gated")
        self.assertEqual(
            steps["validate-discovery"]["run"],
            SHELL_PREFIX + "discovery --run {{ context.run_id }}",
        )

    def test_autonomous_records_then_validates_discovery(self) -> None:
        steps = self.steps(self.autonomous)
        self.assertEqual(steps["discover"]["input"]["args"], "autonomous")
        self.assertEqual(
            _shell_check(steps["record-discovery"]["run"]),
            ("record-decision", "clarification"),
        )

    def test_clarify_does_not_ask_again(self) -> None:
        for doc in (self.feature, self.autonomous):
            with self.subTest(doc["workflow"]["id"]):
                self.assertEqual(
                    self.steps(doc)["clarify"]["input"]["args"], CLARIFY_ARGS
                )
        command = COMMANDS / "speckit.ballast.clarify.md"
        text = " ".join(command.read_text().split())
        self.assertIn(
            "do not reopen a decision the brief settled, answered or assumed", text
        )

    def test_specify_writes_a_traced_spec_from_the_brief(self) -> None:
        for doc in (self.feature, self.autonomous):
            with self.subTest(doc["workflow"]["id"]):
                args = self.steps(doc)["specify"]["input"]["args"]
                self.assertIn(
                    "Write spec.md from {{ inputs.feature_directory }}/discovery.md",
                    args,
                )
                for phrase in (
                    "every acceptance scenario an AC-NNN ID",
                    "every functional requirement and acceptance criterion",
                    "provenance marker",
                    "cite every IAC-n",
                    "Non-goals heading",
                ):
                    self.assertIn(phrase, args)


class ContinueWorkflowDefinitionTests(unittest.TestCase):
    """T037 [AC-009, AC-017]: ballast-continue has only validators and gates."""

    def setUp(self) -> None:
        self.doc = yaml.safe_load(CONTINUE_WORKFLOW.read_text())
        self.steps = self.doc["steps"]

    def test_no_command_step(self) -> None:
        self.assertEqual(self.doc["workflow"]["id"], "ballast-continue")
        self.assertEqual({step.get("type") for step in self.steps}, {"shell", "gate"})
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
        feature = {step["id"]: step for step in _steps() if step.get("type") == "gate"}
        for step in self.steps:
            if step["type"] == "gate":
                self.assertEqual(step, feature[step["id"]], step["id"])
                self.assertEqual(step["on_reject"], "retry")


sys.path.insert(0, str(ROOT / "tests"))
import discovery_fixtures  # noqa: E402
import test_branch_sync  # noqa: E402
from discovery_fixtures import brief_text, decision, metrics  # noqa: E402
from test_autonomy import (  # noqa: E402
    AutonomyCase,
    _bwrap_works,
    autonomy,
    isolate_operator_state,
    operator_state,
    trusted_directory,
)

sys.path.pop(0)
sys.path.insert(0, str(ROOT / "tools/spec_workflow"))
try:
    import run as run_module
finally:
    sys.path.pop(0)

AUTO_FEATURE = "specs/27-demo-run"
DONE_TASKS = TASKS.replace("- [ ]", "- [x]")
# Specs written after discovery are traced to the brief (#16).
TRACED_SPEC = discovery_fixtures.SPEC
# The engine's checkout has README.md but no policies: cite only what exists.
AUTO_BRIEF_SECTIONS = {
    "Sources": "- S-1: Issue #27 body\n- S-2: README.md",
    "Non-goals": "- Audio import [I]",
    "Constraints": "- Keep the demo small [S: README.md]",
    "Decisions": decision(
        "D-01",
        "settled",
        sources="[S: Issue #27 body]",
        resolution="Plain text, as [S: README.md] shows",
    ),
}
AUTO_BRIEF = brief_text(AUTO_BRIEF_SECTIONS, mode="autonomous")


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
    # The report names of speckit.ballast.review's table.
    report_name = "convergence" if kind == "spec-reconciliation" else kind
    report = f"{AUTO_FEATURE}/reviews/{report_name}.md"
    review = {
        "kind": kind,
        "verdict": "approved",
        "report": report,
        "findings": findings or [],
    }
    name = f"{point}-{kind}.json" if point == "specialist-review" else f"{point}.json"
    return {
        report: f"# {kind} review\n\nConsistent with the plan.\n"
        + ("\n- Verdict: CONVERGED\n" if report_name == "convergence" else ""),
        f"{AUTO_FEATURE}/autonomous/drafts/{name}": _draft(
            point, report, review=review
        ),
    }


def _autonomous_plan() -> dict[str, dict[str, str]]:
    """Return what each fake agent step writes, keyed by its plan directory."""
    feature, drafts = AUTO_FEATURE, f"{AUTO_FEATURE}/autonomous/drafts"
    spec, plan = f"{feature}/spec.md", f"{feature}/plan.md"

    def decide(point: str, artifact: str) -> dict[str, str]:
        return {f"{drafts}/{point}.json": _draft(point, artifact)}

    return {
        "speckit-ballast-decide-scope": decide("scope", "README.md"),
        "speckit-ballast-discover-autonomous": {f"{feature}/discovery.md": AUTO_BRIEF},
        "speckit-specify": {spec: TRACED_SPEC},
        # #21 FR-004: provisional intent cites the brief and the traced spec.
        "speckit-ballast-decide-intent": {
            f"{drafts}/intent.json": _draft(
                "intent", spec, evidence=[f"{feature}/discovery.md", spec]
            )
        },
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
        ),
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
    """Drive ballast-autonomous through run.py, Spec Kit and the agent wrapper.

    Real confinement and trusted recorders, with a fake agent, a fake gh and a
    bare origin.

    Shared by the engine test classes below; it has no tests of its own.
    """

    def setUp(self) -> None:
        super().setUp()
        # The ignore rules tools/setup installs, and the standard laid out the
        # way it places it in a project.
        (self.root / ".gitignore").write_text(
            ".ballast/\n.specify/*\n!.specify/memory/\n"
        )
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
        origin = (self.base / "origin.git").as_uri()
        self.enterContext(
            patch.object(run_module.branch_sync, "_url", lambda *_a, **_k: origin)
        )
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

    def start(
        self, *extra: str, integration: str = "claude"
    ) -> tuple[int, str, str, str]:
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
        """Return the commands of the agent steps that ran, in order."""
        return [
            step["command"].lstrip("/$")
            for step in autonomy.read_steps(self.root, run_id)
            if step.get("ran")
        ]

    def stopped(
        self, *extra: str, integration: str = "claude"
    ) -> tuple[str, dict, str]:
        """Start a run that must stop on a block; return run ID, block, output."""
        code, out, err, run_id = self.start(*extra, integration=integration)
        self.assertEqual(code, 1, out + err)
        record = autonomy.read_run(self.root, run_id)
        self.assertEqual(record["status"], "stopped")
        block = autonomy.read_block(self.root, run_id)
        self.assertIn(f"Next: {block['command']}", out)
        self.assertIn(
            f"Autonomous run blocked ({autonomy.block_class(block)}: "
            f"{block['category']})",
            out,
        )
        # DEC-0007: the #17 checkpoint line is printed, but no PR is published.
        self.assertNotRegex(out, r"Draft PR: (https://|created|reused)")
        if block["category"] not in autonomy.PUBLISH_RETRY:
            self.assertFalse([c for c in self.gh_calls() if c[:2] == ["pr", "create"]])
        return run_id, block, out


class AutonomousEngineTests(AutonomousEngineCase):
    """T033 [AC-001, AC-002, AC-003, SC-001, SC-002]: a full unattended run."""

    def test_r2_specialists_follow_the_required_reviews_hint(self) -> None:
        """Pilot: an R2 run missed the architecture review the recorder needs.

        The fake specialist reviewer does what speckit.ballast.review says:
        it writes one report and draft per kind listed in the hint file.
        """
        self.eligible_issue(risk="R2", extra="R2 boundaries: authentication")
        staged = self.root / ".git/fake-agent-kinds"
        for kind in autonomy.REVIEW_KINDS:
            for path, text in _review("specialist-review", kind).items():
                target = staged / kind / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(text)
        hint = (
            f".specify/workflow-state/required-reviews/{Path(AUTO_FEATURE).name}.json"
        )
        follow = (
            "import json, shutil, sys; "
            f"kinds = json.load(open({hint!r}))['required']; "
            "[shutil.copytree(f'{sys.argv[1]}/{k}', '.', dirs_exist_ok=True) "
            "for k in kinds if k != 'engineering']; "
            "print('kinds=' + ','.join(kinds))"
        )
        plan = _autonomous_plan()
        plan["speckit-ballast-review-specialists"] = {
            "exec": f'python3 -c "{follow}" {staged}'
        }
        self.layout(plan)
        code, out, err, run_id = self.start()
        self.assertEqual(code, 0, out + err)
        kinds = {
            e["review"]["kind"]
            for e in autonomy.current_decisions(
                autonomy.read_decisions(self.root, run_id)
            )
            if e.get("review")
        }
        self.assertLessEqual({"security", "architecture"}, kinds)

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


class AutonomousDiscoveryEngineTests(AutonomousEngineCase):
    """#16 T028 [AC-010, AC-011, AC-012]: discovery assumes or blocks, unasked."""

    def test_safe_gap_is_assumed_and_recorded(self) -> None:
        feature = AUTO_FEATURE
        sections = AUTO_BRIEF_SECTIONS | {
            "Inferred": "- Plain text is used [P: D-01]",
            "Decisions": decision(
                "D-01",
                "assumed",
                sources="[S: Issue #27 body] [S: README.md]",
                resolution="Plain text: reversible, no data loss",
            ),
            "Question metrics": metrics(0, 0, 1),
        }
        assumption = {
            "question": "D-01: Which output format?",
            "default": "Plain text",
            "reversible": True,
        }
        plan = _autonomous_plan()
        plan["speckit-ballast-discover-autonomous"] = {
            f"{feature}/discovery.md": brief_text(sections, mode="autonomous"),
            f"{feature}/autonomous/drafts/clarification-discovery-1.json": _draft(
                "clarification",
                f"{feature}/discovery.md",
                summary="D-01: assume plain text output",
                assumption=assumption,
            ),
        }
        self.layout(plan)
        code, out, err, run_id = self.start()
        self.assertEqual(code, 0, out + err)
        results = self.engine_state(run_id)["step_results"]
        for step in ("record-discovery", "validate-discovery"):
            self.assertEqual(results[step]["status"], "completed", step)
        record = (self.root / feature / "autonomous/record.md").read_text()
        self.assertIn("D-01: assume plain text output", record)
        self.assertIn("assume (agent-provisional)", record)
        body = (self.gh_dir / "pr-body.md").read_text()
        self.assertIn("D-01: assume plain text output", body)

    def test_unsafe_gap_blocks_with_options(self) -> None:
        plan = _autonomous_plan()
        plan["speckit-ballast-discover-autonomous"] = BLOCKED | _block_draft(
            "contradiction", "D-01: the Issue and the README disagree on the format"
        )
        self.layout(plan)
        run_id, block, out = self.stopped()
        self.assertEqual(block["category"], "contradiction")
        self.assertIn("D-01", block["condition"])
        self.assertEqual(len(block["options"]), 2)
        self.assertIn("option: Keep -> Imports stay visible", out)
        self.assertEqual(self.agent_commands(run_id)[-1], "speckit-ballast-discover")
        self.assertNotIn("specify", self.engine_state(run_id)["step_results"])
        points = [e["point"] for e in autonomy.read_decisions(self.root, run_id)]
        self.assertNotIn("clarification", points)


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
        self.assertEqual(
            results["validate-clarified-spec"]["status"], "completed", out + err
        )
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
    """T046, T046a [SC-004, AC-011, AC-012, AC-013, AC-024, FR-021]: blocks.

    Each block category stops the run before the next agent step, with its reason and
    recovery command.
    """

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
        self.assertTrue(
            (self.root / ".specify/workflow-state" / run_id / "agents").is_dir()
        )

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
        self.assertNotIn(
            "intent", [e["point"] for e in autonomy.read_decisions(self.root, run_id)]
        )

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
                    "intent",
                    f"{AUTO_FEATURE}/spec.md",
                    privileged_actions=["deploy"],
                    evidence=[
                        f"{AUTO_FEATURE}/discovery.md",
                        f"{AUTO_FEATURE}/spec.md",
                    ],
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
        self.blocked_at(
            "speckit-plan", {f"{AUTO_FEATURE}/plan.md": PLAN, "interrupt": ""}
        )
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
                    [
                        "run",
                        "continue",
                        run_id,
                        "--reason",
                        "block-resolved",
                        "--ref",
                        "x",
                    ]
                )
        finally:
            os.chdir(previous)
        self.assertEqual(code, 2)
        self.assertIn("ballast: refusing:", err.getvalue())
        self.assertEqual(self.run_ids(), [run_id])
        self.assertEqual(autonomy.read_run(self.root, run_id)["status"], "stopped")
        self.assertEqual(autonomy.read_block(self.root, run_id), block)


def _userns_restricted() -> bool:
    flag = Path("/proc/sys/kernel/apparmor_restrict_unprivileged_userns")
    try:
        return flag.read_text().strip() == "1"
    except OSError:
        return False


@unittest.skipUnless(
    shutil.which("codex") and _bwrap_works() and _userns_restricted(),
    "needs codex, bwrap and a host that restricts unprivileged user namespaces",
)
class CodexNestedSandboxTests(AutonomyCase):
    """DEC-0004: the probe sees that Codex's sandbox cannot nest here.

    On a host that restricts unprivileged user namespaces, Codex's own sandbox
    cannot start inside Ballast's bwrap.
    """

    def test_probe_reports_no_nested_sandbox(self) -> None:
        self.assertFalse(autonomy.codex_sandbox_nests(self.root))


class AutonomousConfinementEngineTests(AutonomousEngineCase):
    """T048 [AC-016, SC-005, FR-003]: agent writes change no operator state.

    Neither the mode, eligibility, limits, the decision log nor the committed
    projections change.
    """

    ATTEMPTS = (
        ("toml", "echo 'risk = [\"R3\"]' >> ballast.toml"),
        ("run", "echo '{}' > \"$RUN_DIR/run.json\""),
        ("log", "echo '{}' >> \"$RUN_DIR/decisions.jsonl\""),
        (
            "ballast",
            (
                "python3 -I -S .ballast/spec_workflow/run.py start --mode autonomous "
                "-i issue=27 -i idea=x -i feature_directory=specs/27-demo-run "
                "-i integration=claude"
            ),
        ),
        ("publish", 'python3 -I -S .ballast/spec_workflow/run.py publish "$RUN_ID"'),
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
        found = dict(line.split("=", 1) for line in text.splitlines() if "=" in line)
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
                self.assertEqual(record["limits"]["max_agent_steps"], 40)
                self.assertEqual(record["integration"], integration)
                self.assertEqual(self.run_ids(), [run_id])
                self.assertEqual(record["status"], "published")
                # Reset for the next integration: a fresh branch and state.
                shutil.rmtree(autonomy.state_dir(self.root))
                self.git("reset", "-q", "--hard", installed)
                self.git("clean", "-qfd", "--", "specs", "src", "tests")
                self.git("push", "-q", "origin", "--delete", "27-demo-run")

    def test_agents_read_the_issue_snapshot_but_cannot_write_it(self) -> None:
        """DEC-0008: the Issue body reaches confined agents, read-only."""
        snapshot = ".specify/workflow-state/issues/27.md"
        script = (
            f"grep -q '^- works$' {snapshot}; echo read=$?\n"
            f"(echo x >> {snapshot}) 2>/dev/null; echo write=$?\n"
        )
        plan = _autonomous_plan()
        for step in ("speckit-ballast-decide-scope", "speckit-specify"):
            plan[step] |= {"exec": script}
        self.layout(plan)
        code, out, err, run_id = self.start()
        self.assertEqual(code, 0, out + err)
        agents = self.root / ".specify/workflow-state" / run_id / "agents"
        for command in ("speckit-ballast-decide", "speckit-specify"):
            log = min(p for p in agents.iterdir() if f"-{command}-" in p.name)
            text = (log / "stdout.log").read_text()
            self.assertIn("read=0", text, command)
            self.assertNotIn("write=0", text, command)
        idea = json.loads(
            (self.root / ".specify/workflows/runs" / run_id / "inputs.json").read_text()
        )["inputs"]["idea"]
        self.assertIn(snapshot, idea)

    def test_custom_gh_config_dir_is_hidden_from_the_agent(self) -> None:
        """Review F1: the wrapper hides the operator's GH_CONFIG_DIR."""
        if not os.access("/var/tmp", os.W_OK):  # noqa: S108
            self.skipTest("needs a writable /var/tmp")
        outside = Path(self.enterContext(TemporaryDirectory(dir="/var/tmp")))
        (outside / "hosts.yml").write_text("oauth_token: secret\n")
        plan = _autonomous_plan()
        plan["speckit-ballast-decide-scope"] |= {
            "exec": f"cat {outside}/hosts.yml; echo gh=$?; "
            'echo "dir=${GH_CONFIG_DIR-unset}"\n'
        }
        self.layout(plan)
        with patch.dict(os.environ, {"GH_CONFIG_DIR": str(outside)}):
            code, out, err, run_id = self.start()
        self.assertEqual(code, 0, out + err)
        agents = self.root / ".specify/workflow-state" / run_id / "agents"
        log = min(p for p in agents.iterdir() if "-speckit-ballast-decide-" in p.name)
        text = (log / "stdout.log").read_text()
        self.assertNotIn("oauth_token", text)
        self.assertNotIn("gh=0", text)
        self.assertIn("dir=unset", text)

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


FAKE_SPECIFY = """#!/usr/bin/env python3
import json, os, sys
with open(os.environ["FAKE_ENV_DUMP"], "w") as handle:
    json.dump(dict(os.environ), handle)
sys.exit(int(os.environ["FAKE_EXIT"]))
"""
TOKENS = ("GH_TOKEN", "GITHUB_TOKEN", "GH_ENTERPRISE_TOKEN", "GITHUB_ENTERPRISE_TOKEN")


def _run_module() -> object:
    sys.path.insert(0, str(ROOT / "tools/spec_workflow"))
    try:
        import run  # noqa: PLC0415
    finally:
        sys.path.pop(0)
    return run


def _sync_outcome(outcome: str = "up-to-date", **values: object) -> object:
    """Return a branch check result, for tests that stand in for branch_sync."""
    fields = {
        "branch": "feat-x",
        "base_ref": "main",
        "base_after": "a" * 40,
        "head_before": "b" * 40,
        "head_after": "b" * 40,
    }
    if outcome == "blocked":
        fields = {"cause": "dirty", "detail": "uncommitted changes: x", "recovery": "r"}
    return _run_module().branch_sync.Outcome(outcome, **{**fields, **values})


class DraftPrRunTests(unittest.TestCase):
    """run.py reaches the Draft PR checkpoint once and never lets it change a run."""

    def setUp(self) -> None:
        RunHistoryTests.setUp(self)  # type: ignore[arg-type]
        RunHistoryTests._make_importable_run(self)  # type: ignore[arg-type]  # noqa: SLF001
        self.specify = self.repo.root / "fake-specify"
        self.specify.write_text(FAKE_SPECIFY)
        self.specify.chmod(0o755)
        self.dump = self.repo.root / "engine-env.json"
        self.run = _run_module()

    def tearDown(self) -> None:
        self.directory.cleanup()

    def main(self, code: int, *args: str, **env: str) -> tuple[int, str]:
        output = io.StringIO()
        with (
            patch.object(self.run, "ROOT", self.repo.root),
            patch.object(self.run.shutil, "which", return_value=str(self.specify)),
            patch.dict(
                os.environ,
                {"FAKE_EXIT": str(code), "FAKE_ENV_DUMP": str(self.dump), **env},
            ),
            redirect_stdout(output),
        ):
            status = self.run.main(list(args or ("resume", "run42")))
        return status, output.getvalue()

    def test_raising_checkpoint_never_changes_the_exit_status(self) -> None:
        for error in (RuntimeError("boom"), KeyboardInterrupt()):
            for code in (0, 1):
                with (
                    self.subTest(error=type(error).__name__, code=code),
                    patch.object(self.run.draft_pr, "checkpoint", side_effect=error),
                ):
                    status, output = self.main(code)
                    self.assertEqual(status, code)
                    self.assertIn(
                        "Draft PR: failed-retryable (internal-error) "
                        f"({type(error).__name__})",
                        output,
                    )
                    self.assertNotIn("boom", output)
            with (
                self.subTest(error=type(error).__name__, code=130),
                patch.object(self.run.draft_pr, "checkpoint", side_effect=error),
                patch.object(
                    self.run,
                    "subprocess",
                    SimpleNamespace(run=Mock(side_effect=KeyboardInterrupt)),
                ),
            ):
                status, output = self.main(0)
                self.assertEqual(status, 130)
                self.assertIn("Draft PR: failed-retryable (internal-error)", output)

    def test_acceptance_packet_line_follows_the_draft_pr_line(self) -> None:
        draft_pr = self.run.draft_pr
        outcome = draft_pr.Outcome(
            "reused",
            issue=102,
            pr_number=7,
            pr_url="https://github.com/o/r/pull/7",
            packet=draft_pr.packet.PacketOutcome(
                "published", pr_number=7, head="a" * 40
            ),
        )
        with patch.object(draft_pr, "checkpoint", return_value=outcome):
            status, output = self.main(0)
        self.assertEqual(status, 0)
        self.assertIn(
            "Draft PR: reused #7 https://github.com/o/r/pull/7\n"
            "Acceptance packet: published #7 head aaaaaaaaaaaa\n",
            output,
        )

    def test_raising_packet_step_never_changes_the_exit_status(self) -> None:
        draft_pr = self.run.draft_pr

        def execute(work: object) -> object:
            work.run.feature, work.run.issue = FEATURE, 102
            return draft_pr.Outcome(
                "created",
                issue=102,
                pr_number=7,
                pr_url="https://github.com/o/r/pull/7",
            )

        for code in (0, 1, 130):
            engine = (
                patch.object(
                    self.run,
                    "subprocess",
                    SimpleNamespace(run=Mock(side_effect=KeyboardInterrupt)),
                )
                if code == 130  # noqa: PLR2004
                else nullcontext()
            )
            with (
                self.subTest(code=code),
                engine,
                patch.object(draft_pr._Checkpoint, "execute", execute),  # noqa: SLF001
                patch.object(
                    draft_pr.packet, "publish", side_effect=RuntimeError("boom")
                ),
            ):
                status, output = self.main(0 if code == 130 else code)  # noqa: PLR2004
                self.assertEqual(status, code)
                self.assertIn(
                    "Draft PR: created #7 https://github.com/o/r/pull/7\n"
                    "Acceptance packet: failed-retryable (internal-error): report it "
                    "with the run ID; the next run retries (RuntimeError)\n",
                    output,
                )
                self.assertNotIn("boom", output)

    def test_engine_never_receives_github_tokens_but_checkpoint_does(self) -> None:
        seen: dict[str, str] = {}

        def checkpoint(root: Path, _run_id: str) -> object:
            result = self.run.draft_pr._command(  # noqa: SLF001
                [
                    sys.executable,
                    "-c",
                    "import json, os; print(json.dumps(dict(os.environ)))",
                ],
                cwd=root,
            )
            seen.update(json.loads(result.stdout))
            return self.run.draft_pr.Outcome("pending", "no-branch")

        tokens = {name: f"secret-{name}" for name in TOKENS}
        with patch.object(self.run.draft_pr, "checkpoint", side_effect=checkpoint):
            status, output = self.main(0, **tokens)
        self.assertEqual(status, 0)
        engine = json.loads(self.dump.read_text())
        self.assertEqual(engine["BALLAST_SPEC_WORKFLOW"], "1")
        for name in TOKENS:
            self.assertNotIn(name, engine)
            self.assertEqual(seen[name], tokens[name])
        self.assertEqual(self.run.draft_pr.TOKEN_VARIABLES, TOKENS)
        self.assertIn("Draft PR: pending (no-branch)", output)

    def test_checkpoint_runs_once_after_import_for_start_and_resume(self) -> None:
        for args, run_id in (
            (("start", "-i", f"feature_directory={FEATURE}"), "run42xxx"),
            (("resume", "run42"), "run42"),
        ):
            order: list[object] = []

            def importer(_root: Path, _rid: str, order: list[object] = order) -> int:
                order.append("import")
                return 0

            def checkpoint(root: Path, rid: str, order: list[object] = order) -> object:
                order.append((root, rid))
                return self.run.draft_pr.Outcome("pending", "no-branch")

            with (
                self.subTest(command=args[0]),
                patch.object(
                    self.run.uuid, "uuid4", return_value=SimpleNamespace(hex=run_id)
                ),
                patch.object(self.run, "archive_policy"),
                patch.object(self.run, "_summary"),
                patch.object(self.run, "_record"),
                patch.object(self.run, "import_run", side_effect=importer),
                patch.object(self.run.draft_pr, "checkpoint", side_effect=checkpoint),
            ):
                status, _ = self.main(0, *args)
                self.assertEqual(status, 0)
                self.assertEqual(order, ["import", (self.repo.root, run_id)])

    def test_paused_run_still_records_its_checkpoint(self) -> None:
        run_dir = self.repo.root / ".specify/workflows/runs/run42"
        (run_dir / "log.jsonl").write_text(
            '{"event":"step_started","step_id":"scope-gate","type":"gate"}\n'
            '{"event":"step_completed","step_id":"scope-gate","status":"paused"}\n'
            '{"event":"workflow_finished","status":"paused"}\n'
        )
        status, output = self.main(0)
        self.assertEqual(status, 0)
        self.assertIn("Draft PR: pending (not-published)", output)
        sys.path.insert(0, str(ROOT / "tools/spec_workflow"))
        try:
            import ledger  # noqa: PLC0415
        finally:
            sys.path.pop(0)
        events, problems = ledger.read(self.repo.root, "run42")
        self.assertEqual(problems, [])
        checkpoints = [event for event in events if event["kind"] == "pull_request"]
        self.assertEqual(len(checkpoints), 1)
        self.assertEqual(checkpoints[0]["data"]["outcome"], "pending")

    def test_agents_are_still_denied_push_and_gh(self) -> None:
        settings = json.loads(
            (ROOT / "tools/spec_workflow/claude-settings.json").read_text()
        )
        self.assertIn("Bash(git push*)", settings["permissions"]["deny"])
        self.assertIn("Bash(gh *)", settings["permissions"]["deny"])
        for rule in settings["permissions"]["allow"]:
            self.assertFalse(rule.startswith(("Bash(gh", "Bash(git push")), rule)


class BranchSyncCallTests(unittest.TestCase):
    """T015 [FR-001, FR-010, FR-014, SC-001, R12, R13]: where run.py calls the check."""

    def setUp(self) -> None:
        DraftPrRunTests.setUp(self)  # type: ignore[arg-type]
        self.calls: list[dict[str, object]] = []
        self.result = _sync_outcome()

        def recorder(root: Path, run_id: str, **kwargs: object) -> object:
            # Whether the fake engine (every agent step) had already run.
            self.calls.append(
                {"root": root, "run_id": run_id, "engine": self.dump.exists(), **kwargs}
            )
            return self.result

        self.enterContext(
            patch.object(self.run.branch_sync, "synchronize", side_effect=recorder)
        )
        self.checkpoint = self.enterContext(
            patch.object(
                self.run.draft_pr,
                "checkpoint",
                return_value=self.run.draft_pr.Outcome("pending", "no-branch"),
            )
        )

    def tearDown(self) -> None:
        self.directory.cleanup()

    def main(self, *args: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with (
            patch.object(self.run, "ROOT", self.repo.root),
            patch.object(self.run.shutil, "which", return_value=str(self.specify)),
            patch.object(
                self.run.uuid, "uuid4", return_value=SimpleNamespace(hex="new18xxx")
            ),
            patch.object(self.run, "_record"),
            patch.object(self.run, "import_run", return_value=0),
            patch.dict(os.environ, {"FAKE_EXIT": "0", "FAKE_ENV_DUMP": str(self.dump)}),
            redirect_stdout(out),
            redirect_stderr(err),
        ):
            status = self.run.main(list(args))
        return status, out.getvalue(), err.getvalue()

    def test_start_points_feature_json_at_the_run_before_the_engine(self) -> None:
        """Pilot finding (#16): discovery read a feature left by an earlier run."""
        pointer = self.repo.root / ".specify/feature.json"
        pointer.parent.mkdir(parents=True, exist_ok=True)
        pointer.write_text('{"feature_directory": "specs/4-admin-token"}\n')
        status, _, _ = self.main("start", "-i", f"feature_directory={FEATURE}")
        self.assertEqual(status, 0)
        self.assertEqual(json.loads(pointer.read_text())["feature_directory"], FEATURE)

    def test_resume_points_feature_json_at_the_pinned_feature(self) -> None:
        """SEC-002: resume takes the feature from the pin, never from inputs.json."""
        pins = autonomy.state_dir(self.repo.root) / "draft-pr"
        pins.mkdir(parents=True, exist_ok=True, mode=0o700)
        (pins / "run42.json").write_text(
            json.dumps({"branch": "feat-x", "feature": FEATURE})
        )
        inputs = self.repo.root / ".specify/workflows/runs/run42/inputs.json"
        inputs.write_text(json.dumps({"inputs": {"feature_directory": "specs/4-y"}}))
        status, _, _ = self.main("resume", "run42")
        self.assertEqual(status, 0)
        pointer = self.repo.root / ".specify/feature.json"
        self.assertEqual(json.loads(pointer.read_text())["feature_directory"], FEATURE)

    def test_called_once_before_the_engine_for_start_and_resume(self) -> None:
        for args, run_id, starting in (
            (("start", "-i", f"feature_directory={FEATURE}"), "new18xxx", True),
            (("resume", "run42"), "run42", False),
        ):
            with self.subTest(command=args[0]):
                self.calls.clear()
                self.dump.unlink(missing_ok=True)
                status, out, _ = self.main(*args)
                self.assertEqual(status, 0)
                self.assertEqual(
                    self.calls,
                    [
                        {
                            "root": self.repo.root,
                            "run_id": run_id,
                            "engine": False,
                            "feature": FEATURE,
                            "starting": starting,
                            "branch": None,
                            "base": None,
                            "source_run": None,
                        }
                    ],
                )
                self.assertTrue(self.dump.exists())
                self.assertIn("Branch sync: up-to-date feat-x with main", out)

    def test_start_needs_one_valid_feature_directory(self) -> None:
        """E-01 [FR-009]: refused before any check, pin or agent step."""
        for args in (
            ("start",),
            ("start", "-i", "integration=claude"),
            ("start", "-i", "feature_directory=nope"),
            (
                "start",
                "-i",
                f"feature_directory={FEATURE}",
                "--input",
                f"feature_directory={FEATURE}",
            ),
        ):
            with self.subTest(args=args):
                self.calls.clear()
                status, _, err = self.main(*args)
                self.assertEqual(status, 2)
                self.assertIn(
                    "start needs one -i feature_directory=specs/<issue>-<slug>", err
                )
                self.assertEqual(self.calls, [])
                self.assertFalse(self.dump.exists(), "an agent step started")
                pins = autonomy.state_dir(self.repo.root) / "draft-pr"
                self.assertEqual(list(pins.glob("*.json")) if pins.exists() else [], [])

    def test_publish_never_runs_the_check(self) -> None:
        self.main("publish", "run42")
        self.assertEqual(self.calls, [])

    def test_every_block_stops_before_any_agent_and_any_checkpoint(self) -> None:
        bs = self.run.branch_sync
        for cause in sorted(bs.ledger.SYNC_CAUSES):
            for interrupted in (False, True) if cause == "internal-error" else (False,):
                with self.subTest(cause=cause, interrupted=interrupted):
                    self.dump.unlink(missing_ok=True)
                    self.checkpoint.reset_mock()
                    self.result = bs.Outcome(
                        "blocked",
                        cause=cause,
                        detail="interrupted" if interrupted else "why",
                        recovery="the one action",
                        interrupted=interrupted,
                    )
                    for args in (
                        ("resume", "run42"),
                        ("start", "-i", f"feature_directory={FEATURE}"),
                    ):
                        status, out, err = self.main(*args)
                        self.assertEqual(status, 130 if interrupted else 1)
                        self.assertFalse(self.dump.exists(), "an agent step started")
                        self.checkpoint.assert_not_called()
                        self.assertEqual(
                            err.splitlines()[-2:],
                            [
                                f"BLOCKED_UPSTREAM_SYNC ({cause}): "
                                + ("interrupted" if interrupted else "why"),
                                "Recovery: the one action",
                            ],
                        )
                        self.assertNotIn("Draft PR:", out)

    def test_the_check_is_the_only_pin_writer(self) -> None:
        """R12: _launch no longer pins; draft_pr has no pin writer."""
        self.assertFalse(hasattr(self.run.draft_pr, "pin_branch"))
        status, _, _ = self.main("start", "-i", f"feature_directory={FEATURE}")
        self.assertEqual(status, 0)
        self.assertFalse(
            (autonomy.state_dir(self.repo.root) / "draft-pr" / "new18xxx.json").exists()
        )

    def test_help_describes_the_check(self) -> None:
        """FR-014."""
        result = subprocess.run(  # noqa: S603
            [
                sys.executable,
                "-I",
                "-S",
                str(ROOT / "tools/spec_workflow/run.py"),
                "--help",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 2)
        for text in ("Branch sync:", "BLOCKED_UPSTREAM_SYNC", "Branch synchronization"):
            self.assertIn(text, " ".join(result.stderr.split()))


HEAD_SPECIFY = """#!/usr/bin/env python3
import os
head = open(".git/HEAD").read().strip()
ref = head.removeprefix("ref: ")
commit = open(os.path.join(".git", ref)).read().strip() if ref != head else head
open(os.environ["FAKE_HEAD"], "w").write(commit)
"""


class BranchSyncEndToEndTests(unittest.TestCase):
    """T019 [AC-001, AC-004]: run.py with the real check against a scratch remote."""

    def setUp(self) -> None:
        if not test_branch_sync.GIT_OK:
            self.skipTest("needs git 2.41 or later")
        self.scratch = test_branch_sync.Scratch(self)
        self.branch = test_branch_sync.BRANCH
        self.feature = test_branch_sync.FEATURE
        self.run_id = test_branch_sync.RUN
        root = self.scratch.root
        (root / ".git/info/exclude").write_text(".specify/workflows/\n")
        inputs = root / ".specify/workflows/runs" / self.run_id / "inputs.json"
        inputs.parent.mkdir(parents=True)
        inputs.write_text(json.dumps({"inputs": {"feature_directory": self.feature}}))
        self.specify = self.scratch.base / "specify"
        self.specify.write_text(HEAD_SPECIFY)
        self.specify.chmod(0o755)
        self.head_file = self.scratch.base / "engine-head"
        self.run = _run_module()

    def main(self, *args: str) -> tuple[int, str]:
        out = io.StringIO()
        with (
            patch.object(self.run, "ROOT", self.scratch.root),
            patch.object(self.run.shutil, "which", return_value=str(self.specify)),
            patch.object(self.run, "_record"),
            patch.object(self.run, "import_run", return_value=0),
            patch.object(
                self.run.draft_pr,
                "checkpoint",
                return_value=self.run.draft_pr.Outcome("pending", "no-branch"),
            ),
            patch.dict(os.environ, {"FAKE_HEAD": str(self.head_file)}),
            redirect_stdout(out),
            redirect_stderr(io.StringIO()),
        ):
            status = self.run.main(list(args))
        return status, out.getvalue()

    def test_resume_runs_the_engine_on_the_new_base(self) -> None:
        new = self.scratch.advance_base({"base.txt": "b\n"})
        status, out = self.main("resume", self.run_id)
        self.assertEqual(status, 0, out)
        self.assertIn(f"Branch sync: synchronized {self.branch} onto main", out)
        engine_head = self.head_file.read_text()
        self.scratch.git("merge-base", "--is-ancestor", new, engine_head)

    def test_start_synchronizes_before_the_first_step(self) -> None:
        new = self.scratch.advance_base({"base.txt": "b\n"})
        status, out = self.main("start", "-i", f"feature_directory={self.feature}")
        self.assertEqual(status, 0, out)
        self.scratch.git("merge-base", "--is-ancestor", new, self.head_file.read_text())

    def test_resume_takes_the_issue_number_from_the_pin(self) -> None:
        """SEC-002: an agent-written inputs.json cannot widen the rewrite rule."""
        scratch = self.scratch
        scratch.git("checkout", "-q", "-b", "release/3")
        scratch.publish("release/3")
        scratch.pin(self.run_id, branch="release/3")
        inputs = scratch.root / ".specify/workflows/runs" / self.run_id / "inputs.json"
        inputs.write_text(json.dumps({"inputs": {"feature_directory": "specs/3-x"}}))
        scratch.advance_base({"base.txt": "b\n"})
        before = scratch.snapshot("release/3")
        status, _ = self.main("resume", self.run_id)
        self.assertEqual(status, 1)
        self.assertFalse(self.head_file.exists())
        self.assertEqual(scratch.snapshot("release/3"), before)
        (event,) = scratch.events(self.run_id)
        self.assertEqual(event["cause"], "not-feature-branch")

    def test_blocked_resume_starts_no_engine(self) -> None:
        self.scratch.advance_base({"base.txt": "b\n"})
        self.scratch.write({"README.md": "dirty\n"})
        status, _ = self.main("resume", self.run_id)
        self.assertEqual(status, 1)
        self.assertFalse(self.head_file.exists())


artifacts_module = run_module.chat.artifacts
PASS_THROUGH_BWRAP = """#!/usr/bin/env python3
import os, sys
args = sys.argv[1:]
command = args[args.index("--") + 1 :]
os.execvp(command[0], command)
"""  # noqa: S105 - a script body, not a password


class ChatArtifactTests(AutonomyCase):
    """#20 F-002, FR-003, AC-008, AC-009: Chat routes in artifacts.py."""

    def setUp(self) -> None:
        super().setUp()
        (self.root / AUTO_FEATURE).mkdir(parents=True)
        self.record = autonomy.new_run(
            run_id="chat42",
            feature=AUTO_FEATURE,
            issue=27,
            workflow="ballast-chat",
            mode="chat",
            integration="claude",
            start_head=self.git("rev-parse", "HEAD").strip(),
            last_manifest="a" * 64,
        )
        autonomy.write_run(self.root, self.record)
        self.feature = artifacts_module.Feature.from_operator_run(
            self.root, self.record
        )

    def write(self, name: str, text: str) -> Path:
        path = self.root / AUTO_FEATURE / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path

    def fails(self, check: object, reason: str) -> None:
        with self.assertRaisesRegex(artifacts_module.ContractError, reason):
            check(self.feature)  # type: ignore[operator]

    def test_feature_from_the_operator_record(self) -> None:
        self.assertEqual(self.feature.relative, AUTO_FEATURE)
        self.assertEqual(self.feature.run_id, "chat42")
        self.assertIs(self.feature.chat, self.record)
        self.assertIsNone(self.feature.run)
        self.assertIsNone(self.feature.continued)
        autonomous = dict(self.record, workflow="ballast-autonomous")
        with self.assertRaises(artifacts_module.ContractError):
            artifacts_module.Feature.from_operator_run(self.root, autonomous)

    def test_intent_needs_the_registered_human_block(self) -> None:
        self.write("spec.md", SPEC)
        self.fails(artifacts_module.check_intent, "intent.md is missing")
        digest = artifacts_module.spec_digest(SPEC)
        sections = "\n\n".join(
            f"## {name}\n\n- x"
            for name in ("Outcome", "Constraints", "Non-goals", "Success evidence")
        )
        provisional = (
            f"# Feature Intent: Demo\n\n{sections}\n\n## Authority\n\n"
            f"{artifacts_module.PROVISIONAL_START}\n"
            "- **Status**: agent-provisional, not human-approved\n"
            "- **Decision**: PD-0003\n"
            f"- **Spec**: {AUTO_FEATURE}/spec.md\n"
            f"- **Provisional spec digest**: {digest}\n"
            f"{artifacts_module.PROVISIONAL_END}\n"
        )
        self.write("intent.md", provisional)
        # Never the Autonomous route: a provisional block is not an approval.
        self.fails(artifacts_module.check_intent, "no single workflow approval record")
        forged = (
            f"# Feature Intent: Demo\n\n{sections}\n\n## Authority\n\n"
            + "\n".join(
                (
                    artifacts_module.APPROVAL_START,
                    "- **Approved by**: human user",
                    f"- **Spec**: {AUTO_FEATURE}/spec.md",
                    f"- **Approved spec digest**: {digest}",
                    artifacts_module.APPROVAL_END,
                )
            )
        )
        # An agent can write a well-formed human block, never its registration.
        self.write("intent.md", forged + "\n")
        self.fails(artifacts_module.check_intent, "did not register")
        self.write("intent.md", provisional)
        artifacts_module.record_intent(self.feature)
        text = (self.root / AUTO_FEATURE / "intent.md").read_text()
        self.assertNotIn(artifacts_module.PROVISIONAL_START, text)
        self.assertIn("ballast run approve intent (chat42)", text)
        artifacts_module.check_intent(self.feature)
        self.write("spec.md", SPEC + "\nMore scope.\n")
        self.fails(artifacts_module.check_intent, "approval is stale")

    def test_decisions_count_only_current_human_resolutions(self) -> None:
        self.write("spec.md", SPEC)
        artifacts_module.record_intent(self.feature)
        proposal = "# Ledger\n\n## DEC-0001 — Proposal\n\n- **Status**: proposed\n"
        resolution = "\n## DEC-0001 — Resolution\n\n- **Decision**: keep\n"
        self.write("decisions.md", proposal + resolution)
        # An agent-written resolution resolves nothing in a Chat run.
        self.fails(artifacts_module.check_decisions, "unresolved decisions: DEC-0001")
        body = artifacts_module.latest_resolutions(proposal + resolution)["DEC-0001"]
        autonomy.append_human_decision(
            self.root,
            "chat42",
            "decision-resolution",
            "resolve DEC-0001",
            resolves=None,
            extra={
                "decision": "DEC-0001",
                "digest": artifacts_module.resolution_digest(body),
            },
        )
        artifacts_module.check_decisions(self.feature)
        artifacts_module.check_decision_structure(self.feature)
        self.write("decisions.md", proposal + resolution.replace("keep", "drop"))
        self.fails(artifacts_module.check_decisions, "unresolved decisions: DEC-0001")
        self.write("decisions.md", proposal + "## DEC-0002\n")
        self.fails(artifacts_module.check_decision_structure, "malformed DEC headings")

    def test_implementation_baseline_comes_from_operator_state(self) -> None:
        self.write("spec.md", SPEC)
        artifacts_module.record_intent(self.feature)
        self.write("plan.md", PLAN)
        self.write("tasks.md", DONE_TASKS)
        self.fails(artifacts_module.check_implementation, "no implementation baseline")
        # A workspace baseline an agent could write is never read.
        state = self.root / ".specify/workflow-state/chat42"
        state.mkdir(parents=True)
        (state / "implementation-baseline.json").write_text(
            json.dumps({"feature": AUTO_FEATURE, "tree": "a" * 40})
        )
        self.fails(artifacts_module.check_implementation, "no implementation baseline")
        self.record["baseline"] = {
            "tree": artifacts_module.worktree_tree(self.root),
            "at": autonomy.now(),
            "approval": "HD-0003",
        }
        self.fails(artifacts_module.check_implementation, "changed nothing outside")
        (self.root / "src").mkdir()
        (self.root / "src/demo.py").write_text("print('demo')\n")
        artifacts_module.check_implementation(self.feature)

    def test_project_checks_core_is_mode_neutral(self) -> None:
        bwrap = self.bin / "bwrap"
        bwrap.write_text(PASS_THROUGH_BWRAP)
        bwrap.chmod(0o755)
        (self.root / "ballast.toml").write_text(
            '[checks]\ncommands = ["true", "exit 3"]\n'
            '[github]\nrepository = "acme/demo"\n'
        )
        # No limits, no frozen tree: a Chat record has neither.
        result = artifacts_module.project_checks(self.root, AUTO_FEATURE)
        self.assertFalse(result["unavailable"])
        self.assertEqual([r["exit"] for r in result["results"]], [0, 3])
        self.assertEqual({r["provenance"] for r in result["results"]}, {"runner"})
        self.assertEqual(
            result["tree"],
            autonomy.tree_digest(self.root, (f"{AUTO_FEATURE}/reviews",)),
        )
        self.assertEqual(result["protected_changes"], [])
        (self.root / "ballast.toml").write_text('[github]\nrepository = "acme/demo"\n')
        unavailable = artifacts_module.project_checks(self.root, AUTO_FEATURE)
        self.assertEqual(
            (unavailable["unavailable"], unavailable["results"]), (True, [])
        )


REPOSITION_WORKFLOW = """schema_version: "1.0"
workflow:
  id: reposition-demo
  name: Reposition demo
  version: 1.0.0
steps:
  - id: one
    type: shell
    run: echo one >> steps.log
  - id: two
    type: shell
    run: echo two >> steps.log
  - id: three
    type: shell
    run: echo three >> steps.log && test -f ok
"""


def _engine_run_dir(root: Path, run_id: str, steps: list[str], **state: object) -> Path:
    """Write an engine run directory: its workflow copy (as dumped) and state."""
    directory = root / ".specify/workflows/runs" / run_id
    directory.mkdir(parents=True)
    (directory / "workflow.yml").write_text(
        yaml.safe_dump(
            {"workflow": {"id": "demo"}, "steps": [{"id": s} for s in steps]},
            sort_keys=False,
        )
    )
    (directory / "state.json").write_text(json.dumps(state))
    (directory / "log.jsonl").write_text('{"event": "x"}\n')
    return directory


class EngineRepositionOfflineTests(unittest.TestCase):
    """#21 T001, R7: run.py repositions a failed engine run at an earlier step."""

    def setUp(self) -> None:
        self.directory = TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.enterContext(patch.object(run_module, "ROOT", self.root))

    def tearDown(self) -> None:
        self.directory.cleanup()

    def test_rewrites_index_results_and_status(self) -> None:
        directory = _engine_run_dir(
            self.root,
            "r1",
            ["one", "two", "three"],
            status="failed",
            current_step_index=2,
            current_step_id="three",
            step_results={"one": {"status": "completed"}, "two": {}, "three": {}},
            workflow_id="demo",
        )
        log = (directory / "log.jsonl").read_bytes()
        run_module._reposition_engine("r1", "two")  # noqa: SLF001
        state = json.loads((directory / "state.json").read_text())
        self.assertEqual(
            (state["current_step_index"], state["current_step_id"], state["status"]),
            (1, "two", "failed"),
        )
        self.assertEqual(state["step_results"], {"one": {"status": "completed"}})
        self.assertEqual(state["workflow_id"], "demo")
        self.assertEqual((directory / "log.jsonl").read_bytes(), log)

    def test_failed_step_itself_is_left_alone(self) -> None:
        directory = _engine_run_dir(
            self.root,
            "r1",
            ["one", "two"],
            status="failed",
            current_step_index=1,
            current_step_id="two",
            step_results={"two": {"status": "failed"}},
        )
        before = (directory / "state.json").read_bytes()
        run_module._reposition_engine("r1", "two")  # noqa: SLF001
        self.assertEqual((directory / "state.json").read_bytes(), before)

    def test_an_unfinished_run_becomes_resumable(self) -> None:
        directory = _engine_run_dir(
            self.root,
            "r1",
            ["one", "two"],
            status="running",
            current_step_index=1,
            current_step_id="two",
            step_results={"one": {}},
        )
        run_module._reposition_engine("r1", "two")  # noqa: SLF001
        state = json.loads((directory / "state.json").read_text())
        self.assertEqual((state["status"], state["current_step_index"]), ("failed", 1))

    def test_unknown_step_or_linked_state_refuses(self) -> None:
        _engine_run_dir(self.root, "r1", ["one"], status="failed", step_results={})
        with self.assertRaisesRegex(RuntimeError, "not a step"):
            run_module._reposition_engine("r1", "nope")  # noqa: SLF001
        other = _engine_run_dir(self.root, "r2", ["one"], status="failed")
        (self.root / ".specify/workflows/runs/r3").symlink_to(other)
        with self.assertRaisesRegex(RuntimeError, "symlink"):
            run_module._reposition_engine("r3", "one")  # noqa: SLF001


@unittest.skipUnless(shutil.which("specify"), "Spec Kit CLI (1.0.11 or later) missing")
class EngineRepositionTests(unittest.TestCase):
    """#21 T001, R7: the real engine resumes at a repositioned step."""

    def setUp(self) -> None:
        self.directory = TemporaryDirectory()
        self.root = Path(self.directory.name)
        (self.root / ".specify").mkdir()
        (self.root / "workflow.yml").write_text(REPOSITION_WORKFLOW)
        self.env = {**os.environ, "SPECKIT_WORKFLOW_RUN_ID": "repo1"}
        self.enterContext(patch.object(run_module, "ROOT", self.root))

    def tearDown(self) -> None:
        self.directory.cleanup()

    def specify(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(  # noqa: S603
            ["specify", "workflow", *args],  # noqa: S607 - resolved by the skip
            cwd=self.root,
            env=self.env,
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )

    def test_resume_runs_the_repositioned_step_next(self) -> None:
        self.specify("run", str(self.root / "workflow.yml"))
        log = self.root / "steps.log"
        self.assertEqual(log.read_text().split(), ["one", "two", "three"])
        state = run_module._engine_state("repo1")  # noqa: SLF001
        self.assertEqual(
            (state["status"], state["current_step_id"]), ("failed", "three")
        )
        run_module._reposition_engine("repo1", "one")  # noqa: SLF001
        (self.root / "ok").write_text("")
        result = self.specify("resume", "repo1")
        self.assertEqual(
            log.read_text().split(),
            ["one", "two", "three", "one", "two", "three"],
            result.stdout + result.stderr,
        )
        self.assertEqual(run_module._engine_state("repo1")["status"], "completed")  # noqa: SLF001


class EngineStepListTests(unittest.TestCase):
    """#21 R7: the step list is read whatever the dump's key order."""

    def setUp(self) -> None:
        self.directory = TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.enterContext(patch.object(run_module, "ROOT", self.root))

    def tearDown(self) -> None:
        self.directory.cleanup()

    def test_any_key_order_and_indentation(self) -> None:
        data = yaml.safe_load(AUTONOMOUS_WORKFLOW.read_text())
        directory = self.root / ".specify/workflows/runs/r1"
        directory.mkdir(parents=True)
        expected = [step["id"] for step in data["steps"]]
        for text in (
            yaml.safe_dump(data, sort_keys=False),
            yaml.safe_dump(data, sort_keys=True),
            AUTONOMOUS_WORKFLOW.read_text(),
        ):
            (directory / "workflow.yml").write_text(text)
            self.assertEqual(run_module._engine_steps("r1"), expected)  # noqa: SLF001
        (directory / "workflow.yml").write_text("steps:\n- type: shell\n")
        self.assertEqual(run_module._engine_steps("r1"), [])  # noqa: SLF001
