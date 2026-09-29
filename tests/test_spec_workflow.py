"""Regression tests for agentic-feature workflow postconditions.

No test calls a real model: validators run as subprocesses against temporary
repositories, the agent wrapper runs a fake CLI, and the optional engine test
drives Spec Kit with a fake integration executable.
"""

from __future__ import annotations

import json
import os
import pty
import select
import shutil
import subprocess
import sys
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

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
            if key != "AGENTIC_SPEC_WORKFLOW"
        }
        self.assertIn(
            ".agentic/spec_workflow/run", self.repo.check("preflight", env=env).stderr
        )
        passing = self.repo.check(
            "preflight", env={**env, "AGENTIC_SPEC_WORKFLOW": "1"}
        )
        self.assertEqual(passing.returncode, 0)


FAKE_CLI = """#!/usr/bin/env python3
import json, os, sys
with open(os.environ["FAKE_ARGV"], "w") as handle:
    json.dump(sys.argv[1:], handle)
if os.environ.get("FAKE_TAMPER"):
    with open(os.environ["FAKE_TAMPER"], "w") as handle:
        handle.write('{"current_step_index": 99}')
print(os.environ.get("FAKE_STDOUT", "done"))
print("progress", file=sys.stderr)
"""


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
        self.env = {
            **os.environ,
            "PATH": f"{fake}{os.pathsep}{os.environ['PATH']}",
            "FAKE_ARGV": str(self.root / "argv.json"),
            "SPECKIT_WORKFLOW_RUN_ID": "run42",
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
                [sys.executable, str(launcher), *args],
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
        (root / ".agentic").mkdir()
        (root / ".agentic/spec_workflow").symlink_to(ROOT / "tools/spec_workflow")
        agent = root / "fake-agent"
        agent.write_text(FAKE_INTEGRATION)
        agent.chmod(0o755)
        (root / "spec-fixture.md").write_text(SPEC)
        self.env = {
            **os.environ,
            "AGENTIC_SPEC_WORKFLOW": "1",
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
    """run.py keeps a commit-safe record in the feature and a full local copy."""

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
                    "workflow_id": "agentic-feature",
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

    def test_records_run_in_feature_and_archive(self) -> None:
        sys.path.insert(0, str(ROOT / "tools/spec_workflow"))
        try:
            import run  # noqa: PLC0415
        finally:
            sys.path.pop(0)
        run._record(self.repo.root, "run42")  # noqa: SLF001

        record_path = self.repo.root / FEATURE / "workflow-runs/run42.json"
        text = record_path.read_text()
        record = json.loads(text)
        self.assertEqual(record["gates"], {"scope-gate": "approve"})
        self.assertEqual(record["events"], [{"event": "step_started"}])
        self.assertNotIn("secret-path", text)
        self.assertNotIn("noisy", text)

        archive = self.repo.root / ".git/speckit-runs/run42"
        self.assertTrue((archive / "run/state.json").is_file())
        self.assertTrue((archive / "state/agents/log.txt").is_file())
