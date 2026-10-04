"""Behavioral checks for the local, uncommitted agent run ledger."""

from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools/spec_workflow"))

import ledger  # noqa: E402

FEATURE = "specs/93-agent-run-ledger"


def git(root: Path, *args: str) -> str:
    """Run local Git setup in a disposable test repository."""
    result = subprocess.run(  # noqa: S603
        ["git", *args],  # noqa: S607 - Local Git test fixture.
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


class LedgerTests(unittest.TestCase):
    """Exercise ledger storage and deterministic import with fictional runs."""

    def setUp(self) -> None:
        self.temp = TemporaryDirectory()
        self.root = Path(self.temp.name)
        git(self.root, "init", "-q")
        (self.root / FEATURE).mkdir(parents=True)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def event(
        self,
        kind: str,
        data: dict[str, object],
        event_id: str = "e1",
        source: str = "runner",
    ) -> dict[str, object]:
        return ledger.new_event("run_1", FEATURE, kind, source, data, event_id)

    def test_append_is_ordered_idempotent_and_outside_worktree(self) -> None:
        event = self.event("run", {"action": "started"})
        self.assertTrue(ledger.append(self.root, event))
        self.assertFalse(ledger.append(self.root, event))
        self.assertTrue(
            str(ledger.ledger_path(self.root, "run_1")).startswith(
                str(self.root / ".git")
            )
        )
        events, problems = ledger.read(self.root, "run_1")
        self.assertEqual(problems, [])
        self.assertEqual([item["sequence"] for item in events], [1])

    def test_rejects_prohibited_fields_and_bad_paths(self) -> None:
        with self.assertRaisesRegex(ledger.LedgerError, "prohibited"):
            ledger.new_event(
                "run_1",
                FEATURE,
                "review",
                "agent-reported",
                {
                    "review_id": "r1",
                    "kind": "code",
                    "verdict": "approved",
                    "prompt": "private",
                },
            )
        with self.assertRaisesRegex(ledger.LedgerError, "run ID"):
            ledger.new_event(
                "../escape", FEATURE, "run", "runner", {"action": "started"}
            )
        with self.assertRaisesRegex(ledger.LedgerError, "invalid reason"):
            ledger.new_event(
                "run_1",
                FEATURE,
                "escalation",
                "operator-attested",
                {
                    "stage": "implement",
                    "from_profile": "standard",
                    "to_profile": "senior",
                    "reason": "a long private explanation",
                },
            )
        with self.assertRaisesRegex(ledger.LedgerError, "unknown severity"):
            ledger.new_event(
                "run_1",
                FEATURE,
                "finding",
                "operator-attested",
                {
                    "review_id": "peer",
                    "finding_id": "f1",
                    "severity": "High",
                    "resolution": "open",
                },
            )

    def test_concurrent_append_and_read(self) -> None:
        ledger.append(self.root, self.event("run", {"action": "started"}, "e0"))

        def write(number: int) -> None:
            ledger.append(
                self.root,
                self.event(
                    "snapshot",
                    {"tree": f"{number:064x}"},
                    f"e{number + 1}",
                    "operator-attested",
                ),
            )

        with ThreadPoolExecutor(max_workers=5) as pool:
            list(pool.map(write, range(20)))
            events, problems = ledger.read(self.root, "run_1")
        self.assertEqual(problems, [])
        self.assertEqual(len(events), 21)
        self.assertEqual([event["sequence"] for event in events], list(range(1, 22)))

    def test_invalid_line_withholds_report(self) -> None:
        ledger.append(self.root, self.event("run", {"action": "started"}))
        with ledger.ledger_path(self.root, "run_1").open(
            "a", encoding="utf-8"
        ) as handle:
            handle.write('{"secret":"not an event"}\n')
        result = ledger.report(self.root, "run_1")
        self.assertEqual(result["status"], "invalid")
        self.assertIn("line 2", result["problems"][0])
        output = io.StringIO()
        with patch.object(ledger, "ROOT", self.root), redirect_stdout(output):
            self.assertEqual(ledger.main(["report", "--run", "run_1", "--json"]), 1)
        self.assertEqual(json.loads(output.getvalue())["status"], "invalid")

    def test_wholly_invalid_stream_is_not_uninstrumented(self) -> None:
        path = ledger.ledger_path(self.root, "run_1")
        path.parent.mkdir(parents=True)
        (path.parent / "events.lock").touch()
        for raw in ('{"bad":true}\n', '{"schema_version":99}\n'):
            with self.subTest(raw=raw):
                path.write_text(raw)
                self.assertEqual(ledger.report(self.root, "run_1")["status"], "invalid")
                for args in (
                    ["report", "--run", "run_1", "--json"],
                    ["report", "--all", "--json"],
                ):
                    output = io.StringIO()
                    with (
                        patch.object(ledger, "ROOT", self.root),
                        redirect_stdout(output),
                    ):
                        self.assertEqual(ledger.main(args), 1)
                    self.assertIn("invalid", output.getvalue())

    def test_contradictory_transition_is_not_appended(self) -> None:
        ledger.append(self.root, self.event("run", {"action": "started"}))
        before = ledger.ledger_path(self.root, "run_1").read_bytes()
        with self.assertRaisesRegex(ledger.LedgerError, "step ended without start"):
            ledger.append(
                self.root,
                self.event(
                    "step",
                    {"action": "completed", "step_id": "implement", "log_line": 1},
                    "e2",
                ),
            )
        self.assertEqual(ledger.ledger_path(self.root, "run_1").read_bytes(), before)

    def test_pull_request_events_accept_every_outcome_and_reason(self) -> None:
        pr = {"pr_number": 7, "pr_url": "https://github.com/o/r/pull/7"}
        for outcome, reasons in ledger.PR_REASONS.items():
            needs_pr = outcome in {"created", "reused"}
            for reason in sorted(reasons) or [None]:
                data: dict[str, object] = {"outcome": outcome, "issue": 17}
                if reason:
                    data["reason"] = reason
                if needs_pr:
                    data.update(pr)
                if outcome.startswith("blocked-") and reason != "no-issue-number":
                    data["matches"] = 1
                with self.subTest(outcome=outcome, reason=reason):
                    self.assertEqual(
                        ledger.new_event(
                            "run_1", FEATURE, "pull_request", "runner", data
                        )["data"],
                        data,
                    )

    def test_pull_request_events_reject_values_outside_the_schema(self) -> None:
        pr = {"pr_number": 7, "pr_url": "https://github.com/o/r/pull/7"}
        cases = {
            "unknown outcome": {"outcome": "merged", "reason": "closed"},
            "unknown reason": {"outcome": "pending", "reason": "later"},
            "reason of another outcome": {"outcome": "pending", "reason": "merged"},
            "created without url": {"outcome": "created", "pr_number": 7},
            "reused without number": {"outcome": "reused", "pr_url": pr["pr_url"]},
            "pending without reason": {"outcome": "pending", "issue": 17},
            "created with reason": {"outcome": "created", "reason": "closed", **pr},
            "non-GitHub url": {
                "outcome": "created",
                "pr_number": 7,
                "pr_url": "https://example.com/o/r/pull/7",
            },
            "issue url": {
                "outcome": "created",
                "pr_number": 7,
                "pr_url": "https://github.com/o/r/issues/7",
            },
            "free text": {"outcome": "pending", "reason": "no-branch", "note": "x"},
        }
        for name, data in cases.items():
            with (
                self.subTest(name=name),
                self.assertRaises(ledger.LedgerError),
            ):
                ledger.new_event("run_1", FEATURE, "pull_request", "runner", data)
        with self.assertRaisesRegex(ledger.LedgerError, "requires runner"):
            ledger.new_event(
                "run_1",
                FEATURE,
                "pull_request",
                "operator-attested",
                {"outcome": "pending", "reason": "no-branch"},
            )

    def test_pull_request_is_runner_only_and_may_follow_any_event(self) -> None:
        output = io.StringIO()
        with (
            redirect_stdout(output),
            redirect_stderr(output),
            self.assertRaises(SystemExit),
        ):
            ledger.main(
                [
                    "record",
                    "run_1",
                    "pull_request",
                    "--source",
                    "agent-reported",
                    "--data",
                    '{"outcome": "pending", "reason": "no-branch"}',
                ]
            )
        self.assertIn("invalid choice", output.getvalue())
        with self.assertRaisesRegex(ledger.LedgerError, "runner or snapshot"):
            ledger._record(  # noqa: SLF001
                self.root,
                "run_1",
                FEATURE,
                "pull_request",
                "agent-reported",
                {"outcome": "pending", "reason": "no-branch"},
            )
        ledger.append(
            self.root,
            self.event("pull_request", {"outcome": "pending", "reason": "no-branch"}),
        )
        ledger.append(self.root, self.event("run", {"action": "started"}, "e2"))
        ledger.append(
            self.root,
            self.event("run", {"action": "ended", "status": "completed"}, "e3"),
        )
        ledger.append(
            self.root,
            self.event(
                "pull_request",
                {
                    "outcome": "created",
                    "pr_number": 7,
                    "pr_url": "https://github.com/o/r/pull/7",
                },
                "e4",
            ),
        )
        self.assertEqual(ledger.read(self.root, "run_1")[1], [])

    def test_report_shows_latest_pull_request_or_its_absence(self) -> None:
        self.write_run([], None)
        ledger.import_run(self.root, "run_1")
        report = ledger.report(self.root, "run_1")
        self.assertEqual(
            report["pull_request"],
            {"available": False, "reason": "no checkpoint recorded"},
        )
        for event_id, data in (
            ("pr1", {"outcome": "pending", "reason": "not-published", "issue": 93}),
            (
                "pr2",
                {
                    "outcome": "created",
                    "issue": 93,
                    "pr_number": 7,
                    "pr_url": "https://github.com/o/r/pull/7",
                },
            ),
        ):
            ledger.append(self.root, self.event("pull_request", data, event_id))
        events, _ = ledger.read(self.root, "run_1")
        report = ledger.report(self.root, "run_1")
        self.assertEqual(
            report["pull_request"],
            {**events[-1]["data"], "observed_at": events[-1]["observed_at"]},
        )
        text = ledger._text_report(report)  # noqa: SLF001
        self.assertEqual(
            [line for line in text.splitlines() if line.startswith("pull_request:")],
            [f"pull_request: {json.dumps(report['pull_request'], sort_keys=True)}"],
        )
        self.assertNotIn("pull_request", ledger.aggregate(self.root))

    def test_checkout_local_git_is_never_executed(self) -> None:
        sentinel = self.root / "git-ran"
        local = self.root / "bin"
        local.mkdir()
        fake = local / "git"
        fake.write_text(f"#!/bin/sh\ntouch {sentinel}\nexit 1\n")
        fake.chmod(0o755)
        system = os.environ.get("PATH", "")
        with patch.dict(os.environ, {"PATH": f"{local}{os.pathsep}{system}"}):
            ledger.append(self.root, self.event("run", {"action": "started"}))
            self.assertTrue(ledger.common_dir(self.root).is_dir())
        self.assertFalse(sentinel.exists())
        with (
            patch.dict(os.environ, {"PATH": str(local)}),
            self.assertRaisesRegex(ledger.LedgerError, "git not found outside"),
        ):
            ledger.common_dir(self.root)
        self.assertFalse(sentinel.exists())

    def test_unsupported_version_and_source_are_rejected(self) -> None:
        event = self.event("run", {"action": "started"})
        event["schema_version"] = True
        with self.assertRaisesRegex(ledger.LedgerError, "unsupported schema"):
            ledger.validate(event)
        with self.assertRaisesRegex(ledger.LedgerError, "requires runner"):
            ledger.new_event(
                "run_1",
                FEATURE,
                "gate",
                "operator-attested",
                {"step_id": "scope-gate", "choice": "approve", "log_line": 2},
            )

    def write_run(
        self, entries: list[dict[str, object]], choice: str | None = None
    ) -> None:
        run = self.root / ".specify/workflows/runs/run_1"
        run.mkdir(parents=True)
        (run / "inputs.json").write_text(
            json.dumps({"inputs": {"feature_directory": FEATURE}})
        )
        (run / "workflow.yml").write_text(
            "workflow:\n  id: ballast-feature\n  version: 1.1.0\n"
            "steps:\n  - id: scope-gate\n    type: gate\n"
            "  - id: implement\n    command: speckit.intent.implement\n"
            "  - id: validate-implement\n    type: shell\n"
            "  - id: review-implementation\n    type: gate\n"
        )
        (run / "state.json").write_text(
            json.dumps(
                {
                    "workflow_id": "ballast-feature",
                    "step_results": {
                        "scope-gate": {"type": "gate", "output": {"choice": choice}}
                    },
                }
            )
        )
        (run / "log.jsonl").write_text(
            "".join(json.dumps(item) + "\n" for item in entries)
        )

    def isolated_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        cli_dir = self.root / "tools/spec_workflow"
        cli_dir.mkdir(parents=True, exist_ok=True)
        for name in ("ledger.py", "artifacts.py"):
            shutil.copy2(ROOT / "tools/spec_workflow" / name, cli_dir / name)
        return subprocess.run(  # noqa: S603
            [sys.executable, "-I", "-S", str(cli_dir / "ledger.py"), *args],
            cwd=self.root,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_skipped_import_does_not_invent_old_gate_rejection(self) -> None:
        entries = [
            {"event": "step_started", "step_id": "scope-gate", "type": "gate"},
            {"event": "step_completed", "step_id": "scope-gate", "status": "paused"},
            {"event": "workflow_finished", "status": "paused"},
            {"event": "step_started", "step_id": "scope-gate", "type": "gate"},
            {"event": "step_completed", "step_id": "scope-gate", "status": "completed"},
            {"event": "workflow_finished", "status": "completed"},
        ]
        self.write_run(entries, "approve")
        ledger.import_run(self.root, "run_1")
        events, problems = ledger.read(self.root, "run_1")
        self.assertEqual(problems, [])
        gates = [item for item in events if item["kind"] == "gate"]
        self.assertEqual(
            [item["data"]["choice"] for item in gates], ["unobserved", "unobserved"]
        )
        self.assertEqual(
            ledger.report(self.root, "run_1")["workflow"]["compliance"], "unavailable"
        )
        self.assertEqual(ledger.import_run(self.root, "run_1"), 0)

    def test_imports_engine_normalized_workflow_yaml(self) -> None:
        self.write_run([], None)
        run = self.root / ".specify/workflows/runs/run_1"
        (run / "workflow.yml").write_text(
            "schema_version: '1.0'\nworkflow:\n  id: ballast-feature\n"
            "  version: 1.1.0\n  description: A wrapped workflow description\n"
            "    from an archived engine run.\nrequires:\n  integrations:\n"
            "    any:\n    - claude\n    - codex\nsteps:\n"
            "- id: scope-gate\n  type: gate\n  message: A wrapped gate message\n"
            "    from an archived engine run.\n  options:\n  - approve\n"
            "  - reject\n- id: implement\n  command: speckit.intent.implement\n"
            "  input:\n    args: '{{ inputs.idea }}'\n"
        )
        self.assertGreater(ledger.import_run(self.root, "run_1"), 0)
        report = ledger.report(self.root, "run_1")
        self.assertNotEqual(report["status"], "invalid")
        self.assertEqual(
            report["workflow"]["missing_steps"], ["scope-gate", "implement"]
        )

    def test_isolated_cli_reports_archived_run(self) -> None:
        self.write_run([], None)
        run = self.root / ".specify/workflows/runs/run_1"
        (run / "workflow.yml").write_text(
            "schema_version: '1.0'\nworkflow:\n  id: ballast-feature\n"
            "  version: 1.1.0\nsteps:\n- id: scope-gate\n  type: gate\n"
            "  options:\n  - approve\n  - reject\n- id: implement\n"
            "  command: speckit.intent.implement\n"
        )
        ledger.import_run(self.root, "run_1")
        shutil.copytree(run, ledger.archive_dir(self.root, "run_1") / "run")
        shutil.rmtree(run)
        for args in (("report", "--all", "--json"), ("report", "--run", "run_1")):
            with self.subTest(args=args):
                result = self.isolated_cli(*args)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertNotIn("ModuleNotFoundError", result.stderr)
                if "--all" in args:
                    self.assertEqual(json.loads(result.stdout)["instrumented_runs"], 1)
                else:
                    self.assertIn("run_1", result.stdout)

    def test_isolated_cli_imports_run(self) -> None:
        self.write_run([], None)
        result = self.isolated_cli("import", "run_1")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("imported 1 event", result.stdout)

    def test_isolated_cli_rejects_unsupported_workflow_yaml(self) -> None:
        self.write_run([], None)
        run = self.root / ".specify/workflows/runs/run_1"
        (run / "workflow.yml").write_text(
            "workflow: {id: ballast-feature, version: 1.1.0}\nsteps: []\n"
        )
        result = self.isolated_cli("import", "run_1")
        self.assertEqual(result.returncode, 2)
        self.assertIn("agent ledger: archived workflow YAML is invalid", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_workflow_reader_rejects_ambiguous_identity_and_steps(self) -> None:
        self.write_run([], None)
        run = self.root / ".specify/workflows/runs/run_1"
        for raw in (
            "workflow: {id: ballast-feature, version: 1.1.0}\nsteps: []\n",
            (
                "workflow:\n  id: &name ballast-feature\n  version: 1.1.0\n"
                "steps:\n- id: scope-gate\n"
            ),
            (
                "workflow:\n  id: ballast-feature\n  version: 1.1.0\n"
                "steps:\n- id: scope-gate\n  id: implement\n"
            ),
            (
                "workflow:\n  id: ballast-feature\n  version: 1.1.0\n"
                "steps:\n- id: scope-gate\nsteps:\n- id: implement\n"
            ),
            (
                "workflow:\n  id: ballast-feature\n  version: 1.1.0\n"
                "steps:\n- id: scope-gate\n id: implement\n"
            ),
            (
                "workflow:\n  id: ballast-feature\n  version: 1.1.0\n"
                "steps:\n- id: scope-gate\n  type: gate\n    id: hidden\n"
            ),
            (
                "workflow:\n  id: ballast-feature\n  version: 1\n"
                "steps:\n- id: scope-gate\n"
            ),
            "workflow:\n  id: 2026-10-02\n  version: 1.1.0\nsteps:\n- id: scope-gate\n",
        ):
            with self.subTest(raw=raw):
                (run / "workflow.yml").write_text(raw)
                with self.assertRaisesRegex(ledger.LedgerError, "workflow YAML"):
                    ledger._workflow_document(run)  # noqa: SLF001

    def test_workflow_digest_check_remains_enforced(self) -> None:
        self.write_run([], None)
        ledger.import_run(self.root, "run_1")
        run = self.root / ".specify/workflows/runs/run_1"
        workflow = run / "workflow.yml"
        original = workflow.read_text()
        workflow.write_text(original + "name: changed\n")
        self.assertIn(
            "workflow definition digest mismatch",
            ledger.report(self.root, "run_1")["problems"],
        )

    def test_workflow_identity_check_remains_enforced(self) -> None:
        self.write_run([], None)
        run = self.root / ".specify/workflows/runs/run_1"
        state = json.loads((run / "state.json").read_text())
        state["workflow_id"] = "different-workflow"
        (run / "state.json").write_text(json.dumps(state))
        ledger.import_run(self.root, "run_1")
        self.assertIn(
            "archived workflow identity mismatch",
            ledger.report(self.root, "run_1")["problems"],
        )

    def test_imports_engine_failed_completion_followed_by_step_failed(self) -> None:
        self.write_run(
            [
                {"event": "step_started", "step_id": "implement", "type": "command"},
                {"event": "step_completed", "step_id": "implement", "status": "failed"},
                {"event": "step_failed", "step_id": "implement"},
                {"event": "workflow_finished", "status": "failed"},
            ]
        )
        ledger.import_run(self.root, "run_1")
        report = ledger.report(self.root, "run_1")
        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["problems"], [])

    def test_manual_import_uses_archived_interruption_status(self) -> None:
        self.write_run(
            [
                {"event": "step_started", "step_id": "scope-gate", "type": "gate"},
                {
                    "event": "step_completed",
                    "step_id": "scope-gate",
                    "status": "paused",
                },
                {"event": "workflow_finished", "status": "paused"},
            ],
            "reject",
        )
        archive = ledger.archive_dir(self.root, "run_1")
        archive.mkdir(parents=True)
        (archive / "invocation.json").write_text(
            json.dumps({"log_lines": 3, "exit_status": 130})
        )
        ledger.import_run(self.root, "run_1", at_invocation_end=False)
        events, problems = ledger.read(self.root, "run_1")
        self.assertEqual(problems, [])
        self.assertEqual(
            [event["data"]["choice"] for event in events if event["kind"] == "gate"],
            ["unobserved"],
        )
        self.assertEqual(
            ledger.import_run(self.root, "run_1", at_invocation_end=False), 0
        )

    def test_import_retry_recovers_gate_after_step_append_crash(self) -> None:
        self.write_run(
            [
                {"event": "step_started", "step_id": "scope-gate", "type": "gate"},
                {
                    "event": "step_completed",
                    "step_id": "scope-gate",
                    "status": "paused",
                },
                {"event": "workflow_finished", "status": "paused"},
            ],
            "reject",
        )
        original_append = ledger.append

        def crash_before_gate(root: Path, event: dict[str, object]) -> bool:
            if event["kind"] == "gate":
                raise KeyboardInterrupt
            return original_append(root, event)

        with (
            patch.object(ledger, "append", side_effect=crash_before_gate),
            self.assertRaises(KeyboardInterrupt),
        ):
            ledger.import_run(self.root, "run_1", at_invocation_end=False)
        self.assertGreater(
            ledger.import_run(self.root, "run_1", at_invocation_end=False), 0
        )
        events, problems = ledger.read(self.root, "run_1")
        self.assertEqual(problems, [])
        self.assertEqual(
            [event["data"]["choice"] for event in events if event["kind"] == "gate"],
            ["reject"],
        )
        self.assertEqual(
            ledger.import_run(self.root, "run_1", at_invocation_end=False), 0
        )

    def test_rejection_requires_linked_recovery_evidence(self) -> None:
        entries = [
            {
                "event": "step_started",
                "step_id": "review-implementation",
                "type": "gate",
            },
            {
                "event": "step_completed",
                "step_id": "review-implementation",
                "status": "paused",
            },
        ]
        self.write_run(entries)
        run = self.root / ".specify/workflows/runs/run_1"
        state = json.loads((run / "state.json").read_text())
        state["step_results"]["review-implementation"] = {
            "type": "gate",
            "output": {"choice": "reject"},
        }
        (run / "state.json").write_text(json.dumps(state))
        ledger.import_run(self.root, "run_1")
        entries.extend(
            [
                {
                    "event": "step_started",
                    "step_id": "review-implementation",
                    "type": "gate",
                },
                {
                    "event": "step_completed",
                    "step_id": "review-implementation",
                    "status": "completed",
                },
            ]
        )
        (run / "log.jsonl").write_text(
            "\n".join(json.dumps(item) for item in entries) + "\n"
        )
        state["step_results"]["review-implementation"]["output"]["choice"] = "approve"
        (run / "state.json").write_text(json.dumps(state))
        ledger.import_run(self.root, "run_1")
        self.assertEqual(
            ledger.report(self.root, "run_1")["workflow"]["rejection_recovery"],
            [{"gate": "review-implementation", "status": "unproven"}],
        )
        self.assertEqual(
            ledger.aggregate(self.root)["rejection_recovery"], {"unproven": 1}
        )

    def test_plan_recovery_needs_changed_plan_and_bound_peer_review(self) -> None:
        old = {
            "tree": "a" * 64,
            "spec_digest": "b" * 64,
            "plan_digest": "c" * 64,
            "manifest_digest": "e" * 64,
        }
        revised = {**old, "plan_digest": "d" * 64}

        def evidence(
            snapshot: dict[str, str], include: str | None = None
        ) -> list[dict]:
            items = [
                ("gate", {"step_id": "review-plan", "choice": "reject", "log_line": 1}),
                ("snapshot", old),
                ("snapshot", snapshot),
                (
                    "human_action",
                    {"action": "manual_recovery", "gate_id": "review-plan"},
                ),
                (
                    "verification",
                    {
                        "check_id": "plan-check",
                        "status": "passed",
                        "snapshot": snapshot["tree"],
                    },
                ),
                (
                    "review",
                    {
                        "review_id": "peer",
                        "kind": "plan",
                        "verdict": "approved",
                        "reviewer_id": "peer",
                        "author_id": "author",
                        "snapshot": snapshot["tree"],
                        "spec_digest": snapshot["spec_digest"],
                        "plan_digest": snapshot["plan_digest"],
                        "manifest_digest": snapshot["manifest_digest"],
                    },
                ),
                (
                    "gate",
                    {"step_id": "review-plan", "choice": "approve", "log_line": 2},
                ),
            ]
            if include:
                items = [item for item in items if item[0] != include]
            result = []
            for number, (kind, data) in enumerate(items, 1):
                source = (
                    "runner"
                    if kind == "gate" or (kind == "snapshot" and data is old)
                    else "operator-attested"
                )
                event = ledger.new_event("run_1", FEATURE, kind, source, data)
                event["sequence"] = number
                result.append(event)
            return result

        complete = evidence(revised)
        self.assertEqual(
            ledger._recovery(complete, [e for e in complete if e["kind"] == "gate"]),  # noqa: SLF001
            [{"gate": "review-plan", "status": "compliant"}],
        )
        stale_manifest = evidence(revised)
        stale_manifest.insert(
            -1,
            ledger.new_event(
                "run_1",
                FEATURE,
                "snapshot",
                "operator-attested",
                {**revised, "manifest_digest": "f" * 64},
            ),
        )
        for number, event in enumerate(stale_manifest, 1):
            event["sequence"] = number
        self.assertEqual(
            ledger._recovery(  # noqa: SLF001 - Pure recovery rule.
                stale_manifest, [e for e in stale_manifest if e["kind"] == "gate"]
            ),
            [{"gate": "review-plan", "status": "unproven"}],
        )
        for events in (
            evidence(old),
            *(
                evidence(revised, missing)
                for missing in ("human_action", "verification", "review")
            ),
        ):
            recovery = ledger._recovery(  # noqa: SLF001 - Pure rule seam.
                events, [e for e in events if e["kind"] == "gate"]
            )
            self.assertEqual(recovery[0]["status"], "unproven")

    def test_imported_plan_rejection_cannot_recover_without_revision(self) -> None:
        (self.root / FEATURE / "plan.md").write_text("Original plan.\n")
        entries = [
            {"event": "step_started", "step_id": "review-plan", "type": "gate"},
            {"event": "step_completed", "step_id": "review-plan", "status": "paused"},
            {"event": "workflow_finished", "status": "paused"},
        ]
        self.write_run(entries)
        run = self.root / ".specify/workflows/runs/run_1"
        (run / "workflow.yml").write_text(
            "workflow:\n  id: ballast-feature\n  version: 1.1.0\n"
            "steps:\n  - id: review-plan\n    type: gate\n"
        )
        state = json.loads((run / "state.json").read_text())
        state["step_results"] = {
            "review-plan": {
                "type": "gate",
                "output": {"choice": "reject"},
            }
        }
        (run / "state.json").write_text(json.dumps(state))
        ledger.import_run(self.root, "run_1")
        digests = ledger.artifact_digests(self.root, FEATURE)
        ledger.append(
            self.root,
            ledger.new_event(
                "run_1",
                FEATURE,
                "human_action",
                "operator-attested",
                {"action": "manual_recovery", "gate_id": "review-plan"},
            ),
        )
        ledger.append(
            self.root,
            ledger.new_event(
                "run_1",
                FEATURE,
                "verification",
                "operator-attested",
                {
                    "check_id": "plan-check",
                    "status": "passed",
                    "snapshot": digests["tree"],
                },
            ),
        )
        ledger.append(
            self.root,
            ledger.new_event(
                "run_1",
                FEATURE,
                "review",
                "operator-attested",
                {
                    "review_id": "peer",
                    "kind": "plan",
                    "verdict": "approved",
                    "author_id": "author",
                    "reviewer_id": "peer",
                    "snapshot": digests["tree"],
                    "plan_digest": digests["plan_digest"],
                },
            ),
        )
        entries.extend(
            [
                {"event": "step_started", "step_id": "review-plan", "type": "gate"},
                {
                    "event": "step_completed",
                    "step_id": "review-plan",
                    "status": "completed",
                },
                {"event": "workflow_finished", "status": "completed"},
            ]
        )
        (run / "log.jsonl").write_text("".join(json.dumps(e) + "\n" for e in entries))
        state["step_results"]["review-plan"]["output"]["choice"] = "approve"
        (run / "state.json").write_text(json.dumps(state))
        ledger.import_run(self.root, "run_1")
        self.assertEqual(
            ledger.report(self.root, "run_1")["workflow"]["rejection_recovery"],
            [{"gate": "review-plan", "status": "unproven"}],
        )

    def test_tasks_recovery_needs_revised_tasks_and_analyze(self) -> None:
        old = {"tree": "a" * 64, "tasks_digest": "b" * 64}
        revised = {**old, "tasks_digest": "c" * 64}

        def recovery(snapshot: dict[str, str], check: str) -> str:
            records = [
                (
                    "gate",
                    "runner",
                    {"step_id": "review-tasks", "choice": "reject", "log_line": 1},
                ),
                ("snapshot", "runner", old),
                ("snapshot", "operator-attested", snapshot),
                (
                    "human_action",
                    "operator-attested",
                    {"action": "manual_recovery", "gate_id": "review-tasks"},
                ),
                (
                    "verification",
                    "operator-attested",
                    {
                        "check_id": check,
                        "status": "passed",
                        "snapshot": snapshot["tree"],
                    },
                ),
                (
                    "gate",
                    "runner",
                    {"step_id": "review-tasks", "choice": "approve", "log_line": 2},
                ),
            ]
            events = []
            for sequence, (kind, source, data) in enumerate(records, 1):
                event = ledger.new_event("run_1", FEATURE, kind, source, data)
                event["sequence"] = sequence
                events.append(event)
            return ledger._recovery(  # noqa: SLF001 - Pure recovery rule.
                events, [e for e in events if e["kind"] == "gate"]
            )[0]["status"]

        self.assertEqual(recovery(revised, "speckit-analyze"), "compliant")
        self.assertEqual(recovery(old, "speckit-analyze"), "unproven")
        self.assertEqual(recovery(revised, "unrelated"), "unproven")

    def test_reconciliation_recovery_needs_attested_convergence(self) -> None:
        tree = "a" * 64

        def recovery(source: str) -> str:
            records = [
                (
                    "gate",
                    "runner",
                    {
                        "step_id": "spec-reconciliation",
                        "choice": "reject",
                        "log_line": 1,
                    },
                ),
                ("snapshot", "runner", {"tree": tree}),
                (
                    "human_action",
                    "operator-attested",
                    {"action": "manual_recovery", "gate_id": "spec-reconciliation"},
                ),
                (
                    "verification",
                    "operator-attested",
                    {"check_id": "reconcile", "status": "passed", "snapshot": tree},
                ),
                ("convergence", source, {"verdict": "CONVERGED", "snapshot": tree}),
                (
                    "gate",
                    "runner",
                    {
                        "step_id": "spec-reconciliation",
                        "choice": "approve",
                        "log_line": 2,
                    },
                ),
            ]
            events = []
            for sequence, (kind, event_source, data) in enumerate(records, 1):
                event = ledger.new_event("run_1", FEATURE, kind, event_source, data)
                event["sequence"] = sequence
                events.append(event)
            return ledger._recovery(  # noqa: SLF001 - Pure recovery rule.
                events, [e for e in events if e["kind"] == "gate"]
            )[0]["status"]

        self.assertEqual(recovery("operator-attested"), "compliant")
        self.assertEqual(recovery("agent-reported"), "unproven")

    def test_intent_recovery_follows_gate_then_intent_validation(self) -> None:
        def recovery(
            *,
            revised: bool = True,
            check: bool = True,
            check_on_revised_spec: bool = True,
            validated: bool = True,
            matching: bool = True,
        ) -> str:
            old = "a" * 64
            new = "b" * 64 if revised else old
            tree = "c" * 64
            records = [
                (
                    "gate",
                    "runner",
                    {"step_id": "approve-intent", "choice": "reject", "log_line": 1},
                ),
                ("snapshot", "runner", {"tree": tree, "spec_digest": old}),
                ("snapshot", "operator-attested", {"tree": tree, "spec_digest": new}),
                (
                    "human_action",
                    "operator-attested",
                    {"action": "manual_recovery", "gate_id": "approve-intent"},
                ),
                (
                    "verification",
                    "operator-attested",
                    {
                        "check_id": "validate-clarified-spec" if check else "unrelated",
                        "status": "passed",
                        "snapshot": tree,
                        "spec_digest": new if check_on_revised_spec else old,
                    },
                ),
                (
                    "gate",
                    "runner",
                    {"step_id": "approve-intent", "choice": "approve", "log_line": 2},
                ),
                (
                    "step",
                    "runner",
                    {
                        "step_id": "record-intent",
                        "action": "completed",
                        "status": "completed",
                        "log_line": 3,
                    },
                ),
                (
                    "step",
                    "runner",
                    {
                        "step_id": "validate-intent",
                        "action": "completed",
                        "status": "completed",
                        "exit_code": 0 if validated else 1,
                        "log_line": 4,
                    },
                ),
                (
                    "snapshot",
                    "runner",
                    {
                        "tree": tree,
                        "spec_digest": new if matching else "d" * 64,
                        "intent_digest": "e" * 64,
                    },
                ),
            ]
            events = []
            for sequence, (kind, source, data) in enumerate(records, 1):
                event = ledger.new_event("run_1", FEATURE, kind, source, data)
                event["sequence"] = sequence
                events.append(event)
            return ledger._recovery(  # noqa: SLF001 - Pure recovery rule.
                events, [e for e in events if e["kind"] == "gate"]
            )[0]["status"]

        self.assertEqual(recovery(), "compliant")
        for options in (
            {"revised": False},
            {"check": False},
            {"check_on_revised_spec": False},
            {"validated": False},
            {"matching": False},
        ):
            self.assertEqual(recovery(**options), "unproven")

    def _complete_evidence_run(
        self,
        *,
        review: bool = True,
        convergence: bool = True,
        check_source: str = "operator-attested",
        convergence_source: str = "operator-attested",
    ) -> None:
        (self.root / ".gitignore").write_text(
            "__pycache__/\n.venv/\n.specify/workflows/runs/\n"
        )
        feature = self.root / FEATURE
        (feature / "spec.md").write_text("- **AC-001**: A fictional check.\n")
        spec_digest = hashlib.sha256((feature / "spec.md").read_bytes()).hexdigest()
        (feature / "intent.md").write_text(f"Approved spec sha256:{spec_digest}\n")
        (feature / "plan.md").write_text("One bounded step.\n")
        (feature / "tasks.md").write_text("- [x] Check it.\n")
        check_id = "tests.test_demo.DemoTests.test_one"
        (feature / "acceptance-evidence.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "spec_digest": spec_digest,
                    "criteria": {"AC-001": [check_id]},
                }
            )
        )
        test_dir = self.root / "tests"
        test_dir.mkdir()
        (test_dir / "__init__.py").write_text("")
        (test_dir / "test_demo.py").write_text(
            "import unittest\nclass DemoTests(unittest.TestCase):\n"
            "    def test_one(self): self.assertEqual(1, 1)\n"
        )
        interpreter = self.root / ".venv/bin/python"
        interpreter.parent.mkdir(parents=True)
        interpreter.symlink_to(Path(sys.executable).resolve())
        self.write_run(
            [
                {"event": "step_started", "step_id": "implement", "type": "command"},
                {
                    "event": "step_completed",
                    "step_id": "implement",
                    "status": "completed",
                },
            ]
        )
        run = self.root / ".specify/workflows/runs/run_1"
        (run / "workflow.yml").write_text(
            "workflow:\n  id: ballast-feature\n  version: 1.1.0\n"
            "steps:\n  - id: implement\n    type: command\n"
            "  - id: review-implementation\n    type: gate\n"
            "  - id: final-acceptance\n    type: gate\n"
        )
        ledger.import_run(self.root, "run_1")
        ledger.archive_manifest(self.root, "run_1", FEATURE)
        if check_source == "operator-attested":
            self.assertEqual(ledger._check(self.root, "run_1", "AC-001", check_id), 0)  # noqa: SLF001
        else:
            digests = ledger.artifact_digests(self.root, FEATURE)
            ledger.append(
                self.root,
                ledger.new_event(
                    "run_1",
                    FEATURE,
                    "snapshot",
                    "operator-attested",
                    digests,
                ),
            )
            ledger.append(
                self.root,
                ledger.new_event(
                    "run_1",
                    FEATURE,
                    "verification",
                    check_source,
                    {
                        "check_id": check_id,
                        "ac_id": "AC-001",
                        "status": "passed",
                        "snapshot": digests["tree"],
                        "manifest_digest": digests["manifest_digest"],
                    },
                ),
            )
        digests = ledger.artifact_digests(self.root, FEATURE)
        if review:
            ledger._record(  # noqa: SLF001 - Exercise binding at CLI seam.
                self.root,
                "run_1",
                FEATURE,
                "review",
                "operator-attested",
                {
                    "review_id": "peer",
                    "kind": "implementation",
                    "verdict": "approved",
                    "author_id": "author",
                    "reviewer_id": "peer",
                    "snapshot": digests["tree"],
                    **{
                        key: value
                        for key, value in digests.items()
                        if key.endswith("_digest")
                    },
                },
            )
        if convergence:
            data = {
                "verdict": "CONVERGED",
                "snapshot": digests["tree"],
                **{
                    key: value
                    for key, value in digests.items()
                    if key.endswith("_digest")
                },
            }
            if convergence_source == "operator-attested":
                ledger._record(  # noqa: SLF001 - Exercise binding at CLI seam.
                    self.root,
                    "run_1",
                    FEATURE,
                    "convergence",
                    convergence_source,
                    data,
                )
            else:
                ledger.append(
                    self.root,
                    ledger.new_event(
                        "run_1",
                        FEATURE,
                        "convergence",
                        convergence_source,
                        data,
                    ),
                )
        entries = [
            json.loads(line) for line in (run / "log.jsonl").read_text().splitlines()
        ]
        for step in ("review-implementation", "final-acceptance"):
            entries.extend(
                [
                    {"event": "step_started", "step_id": step, "type": "gate"},
                    {"event": "step_completed", "step_id": step, "status": "completed"},
                ]
            )
        entries.append({"event": "workflow_finished", "status": "completed"})
        (run / "log.jsonl").write_text("".join(json.dumps(e) + "\n" for e in entries))
        state = json.loads((run / "state.json").read_text())
        state["step_results"] = {
            step: {"type": "gate", "output": {"choice": "approve"}}
            for step in ("review-implementation", "final-acceptance")
        }
        (run / "state.json").write_text(json.dumps(state))
        ledger.import_run(self.root, "run_1")

    def test_complete_run_is_compliant_with_runner_end_snapshot(self) -> None:
        self._complete_evidence_run()
        report = ledger.report(self.root, "run_1")
        self.assertEqual(report["workflow"]["compliance"], "compliant")
        self.assertEqual(report["outcome"]["ac_status"], {"AC-001": "passed"})
        events, _ = ledger.read(self.root, "run_1")
        self.assertEqual(events[-1]["kind"], "snapshot")
        self.assertEqual(events[-1]["source"], "runner")

    def test_complete_run_needs_fresh_review_and_convergence(self) -> None:
        self._complete_evidence_run(review=False)
        self.assertEqual(
            ledger.report(self.root, "run_1")["workflow"]["compliance"],
            "incomplete_or_noncompliant",
        )

    def test_complete_run_needs_convergence(self) -> None:
        self._complete_evidence_run(convergence=False)
        self.assertEqual(
            ledger.report(self.root, "run_1")["workflow"]["compliance"],
            "incomplete_or_noncompliant",
        )

    def test_feature_artifact_change_stales_convergence(self) -> None:
        self._complete_evidence_run()
        self.assertTrue(
            ledger.report(self.root, "run_1")["outcome"]["fresh_convergence"]
        )
        (self.root / FEATURE / "plan.md").write_text("A revised bounded step.\n")
        ledger.append(
            self.root,
            ledger.new_event(
                "run_1",
                FEATURE,
                "snapshot",
                "operator-attested",
                ledger.artifact_digests(self.root, FEATURE),
            ),
        )
        self.assertFalse(
            ledger.report(self.root, "run_1")["outcome"]["fresh_convergence"]
        )

    def test_agent_reported_checks_and_convergence_cannot_prove_compliance(
        self,
    ) -> None:
        self._complete_evidence_run(
            check_source="agent-reported", convergence_source="agent-reported"
        )
        report = ledger.report(self.root, "run_1")
        self.assertEqual(report["outcome"]["ac_status"], {"AC-001": "missing"})
        self.assertEqual(report["workflow"]["compliance"], "incomplete_or_noncompliant")

    def test_removed_worktree_labels_prior_evidence_unavailable(self) -> None:
        self._complete_evidence_run()
        active = self.root / ".specify/workflows/runs/run_1"
        shutil.copytree(active, ledger.archive_dir(self.root, "run_1") / "run")
        shutil.rmtree(active)
        report = ledger.report(self.root, "run_1")
        self.assertEqual(report["workflow"]["compliance"], "unavailable")
        self.assertEqual(report["outcome"]["ac_status"], {"AC-001": "unavailable"})
        self.assertIsNone(report["outcome"]["ac_passed"])
        self.assertIsNone(report["outcome"]["ac_executable_coverage"])
        self.assertEqual(report["outcome"]["snapshot_freshness"], "historical")
        self.assertIn("routing", report)
        self.assertIn("efficiency", report)
        self.assertIn("human_effort", report)

    def test_manifest_revision_makes_prior_checks_stale_without_invalid_run(
        self,
    ) -> None:
        self._complete_evidence_run()
        feature = self.root / FEATURE
        path = feature / "acceptance-evidence.json"
        original_digest = hashlib.sha256(path.read_bytes()).hexdigest()
        path.write_text(path.read_text().replace("test_one", "test_two"))
        ledger.archive_manifest(self.root, "run_1", FEATURE)
        revised_digest = hashlib.sha256(path.read_bytes()).hexdigest()
        ledger.append(
            self.root,
            ledger.new_event(
                "run_1",
                FEATURE,
                "snapshot",
                "operator-attested",
                ledger.artifact_digests(self.root, FEATURE),
            ),
        )
        report = ledger.report(self.root, "run_1")
        self.assertEqual(report["status"], "completed")
        self.assertEqual(report["outcome"]["ac_status"], {"AC-001": "stale"})
        self.assertEqual(report["workflow"]["compliance"], "incomplete_or_noncompliant")
        archive = ledger.archive_dir(self.root, "run_1") / "manifests"
        self.assertTrue((archive / f"{original_digest}.json").is_file())
        self.assertTrue((archive / f"{revised_digest}.json").is_file())

    def test_review_record_rejects_stale_plan_digest(self) -> None:
        self._complete_evidence_run()
        old = ledger.artifact_digests(self.root, FEATURE)
        (self.root / FEATURE / "plan.md").write_text("Revised plan.\n")
        with self.assertRaisesRegex(ledger.LedgerError, "current artifact digests"):
            ledger._record(  # noqa: SLF001 - Check binding at CLI seam.
                self.root,
                "run_1",
                FEATURE,
                "review",
                "operator-attested",
                {
                    "review_id": "stale",
                    "kind": "plan",
                    "verdict": "approved",
                    "author_id": "author",
                    "reviewer_id": "peer",
                    "snapshot": old["tree"],
                    **{
                        key: value
                        for key, value in old.items()
                        if key.endswith("_digest")
                    },
                },
            )

    def test_passed_verification_rejects_stale_spec_digest(self) -> None:
        self._complete_evidence_run()
        digests = ledger.artifact_digests(self.root, FEATURE)
        with self.assertRaisesRegex(ledger.LedgerError, "current artifact digests"):
            ledger._record(  # noqa: SLF001 - Check binding at CLI seam.
                self.root,
                "run_1",
                FEATURE,
                "verification",
                "operator-attested",
                {
                    "check_id": "validate-clarified-spec",
                    "status": "passed",
                    "snapshot": digests["tree"],
                    "spec_digest": "f" * 64,
                },
            )

    def test_runner_detects_change_after_final_acceptance(self) -> None:
        self._complete_evidence_run()
        (self.root / "changed.py").write_text("answer = 42\n")
        self.assertEqual(ledger.import_run(self.root, "run_1"), 1)
        self.assertEqual(
            ledger.report(self.root, "run_1")["workflow"]["compliance"],
            "incomplete_or_noncompliant",
        )
        active = self.root / ".specify/workflows/runs/run_1"
        shutil.copytree(active, ledger.archive_dir(self.root, "run_1") / "run")
        shutil.rmtree(active)
        self.assertEqual(
            ledger.report(self.root, "run_1")["workflow"]["compliance"],
            "incomplete_or_noncompliant",
        )

    def test_new_snapshot_marks_old_check_stale(self) -> None:
        self._complete_evidence_run()
        (self.root / "changed.py").write_text("answer = 42\n")
        ledger.append(
            self.root,
            ledger.new_event(
                "run_1",
                FEATURE,
                "snapshot",
                "operator-attested",
                ledger.artifact_digests(self.root, FEATURE),
            ),
        )
        self.assertEqual(
            ledger.report(self.root, "run_1")["outcome"]["ac_status"],
            {"AC-001": "stale"},
        )

    def test_partly_rerun_ac_is_stale(self) -> None:
        self.write_run([], None)
        ledger.import_run(self.root, "run_1")
        feature = self.root / FEATURE
        spec = feature / "spec.md"
        spec.write_text("- **AC-001**: Fictional checks.\n")
        spec_digest = hashlib.sha256(spec.read_bytes()).hexdigest()
        (feature / "intent.md").write_text(f"Approved spec sha256:{spec_digest}\n")
        checks = [f"tests.test_demo.DemoTests.test_{name}" for name in ("one", "two")]
        (feature / "acceptance-evidence.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "spec_digest": spec_digest,
                    "criteria": {"AC-001": checks},
                }
            )
        )
        ledger.archive_manifest(self.root, "run_1", FEATURE)
        first = ledger.artifact_digests(self.root, FEATURE)
        ledger.append(
            self.root,
            ledger.new_event(
                "run_1",
                FEATURE,
                "snapshot",
                "operator-attested",
                first,
            ),
        )
        for check in checks:
            ledger.append(
                self.root,
                ledger.new_event(
                    "run_1",
                    FEATURE,
                    "verification",
                    "operator-attested",
                    {
                        "check_id": check,
                        "ac_id": "AC-001",
                        "status": "passed",
                        "snapshot": first["tree"],
                        "spec_digest": spec_digest,
                        "manifest_digest": first["manifest_digest"],
                    },
                ),
            )
        (self.root / "changed.py").write_text("answer = 42\n")
        second = ledger.artifact_digests(self.root, FEATURE)
        ledger.append(
            self.root,
            ledger.new_event(
                "run_1",
                FEATURE,
                "snapshot",
                "operator-attested",
                second,
            ),
        )
        ledger.append(
            self.root,
            ledger.new_event(
                "run_1",
                FEATURE,
                "verification",
                "operator-attested",
                {
                    "check_id": checks[0],
                    "ac_id": "AC-001",
                    "status": "passed",
                    "snapshot": second["tree"],
                    "spec_digest": spec_digest,
                    "manifest_digest": second["manifest_digest"],
                },
            ),
        )
        self.assertEqual(
            ledger.report(self.root, "run_1")["outcome"]["ac_status"],
            {"AC-001": "stale"},
        )

    def test_aborted_scope_gate_records_rejection(self) -> None:
        self.write_run(
            [
                {"event": "step_started", "step_id": "scope-gate", "type": "gate"},
                {"event": "step_failed", "step_id": "scope-gate", "status": "failed"},
                {"event": "workflow_finished", "status": "failed"},
            ],
            "reject",
        )
        ledger.import_run(self.root, "run_1")
        result = ledger.report(self.root, "run_1")
        self.assertEqual(result["human_effort"]["gate_rejections"], 1)
        self.assertEqual(result["workflow"]["gate_choices"], {"reject": 1})

    def test_command_success_does_not_hide_validator_failure_or_unknown_step(
        self,
    ) -> None:
        entries = [
            {"event": "step_started", "step_id": "implement", "type": "command"},
            {"event": "step_completed", "step_id": "implement", "status": "completed"},
            {"event": "step_started", "step_id": "validate-implement", "type": "shell"},
            {
                "event": "step_failed",
                "step_id": "validate-implement",
                "status": "failed",
            },
            {"event": "step_started", "step_id": "unexpected", "type": "shell"},
            {"event": "step_completed", "step_id": "unexpected", "status": "completed"},
        ]
        self.write_run(entries)
        run = self.root / ".specify/workflows/runs/run_1"
        state = json.loads((run / "state.json").read_text())
        state["step_results"]["implement"] = {
            "type": "command",
            "output": {"exit_code": 0},
        }
        (run / "state.json").write_text(json.dumps(state))
        ledger.import_run(self.root, "run_1")
        workflow = ledger.report(self.root, "run_1")["workflow"]
        self.assertEqual(workflow["unknown_steps"], ["unexpected"])
        self.assertEqual(
            workflow["command_validator_disagreements"],
            [{"command": "implement", "validator": "validate-implement"}],
        )
        self.assertEqual(workflow["compliance"], "incomplete_or_noncompliant")

    def test_validator_detects_command_failure_across_gate(self) -> None:
        entries = [
            {"event": "step_started", "step_id": "converge", "type": "command"},
            {"event": "step_completed", "step_id": "converge", "status": "completed"},
            {
                "event": "step_started",
                "step_id": "validate-convergence",
                "type": "shell",
            },
            {
                "event": "step_failed",
                "step_id": "validate-convergence",
                "status": "failed",
            },
        ]
        self.write_run(entries)
        run = self.root / ".specify/workflows/runs/run_1"
        (run / "workflow.yml").write_text(
            "workflow:\n  id: ballast-feature\n  version: 1.1.0\n"
            "steps:\n  - id: converge\n    type: command\n"
            "  - id: spec-reconciliation\n    type: gate\n"
            "  - id: validate-convergence\n    type: shell\n"
        )
        state = json.loads((run / "state.json").read_text())
        state["step_results"]["converge"] = {
            "type": "command",
            "output": {"exit_code": 0},
        }
        (run / "state.json").write_text(json.dumps(state))
        ledger.import_run(self.root, "run_1")
        self.assertEqual(
            ledger.report(self.root, "run_1")["workflow"][
                "command_validator_disagreements"
            ],
            [{"command": "converge", "validator": "validate-convergence"}],
        )

    def test_report_marks_missing_usage_unavailable_and_counts_ac_evidence(
        self,
    ) -> None:
        self.write_run(
            [{"event": "step_started", "step_id": "scope-gate", "type": "gate"}], None
        )
        ledger.import_run(self.root, "run_1")
        feature = self.root / FEATURE
        spec = feature / "spec.md"
        spec.write_text("- **AC-001**: Fictional behavior.\n")
        spec_digest = hashlib.sha256(spec.read_bytes()).hexdigest()
        (feature / "intent.md").write_text(f"Approved spec sha256:{spec_digest}\n")
        manifest = {
            "schema_version": 1,
            "spec_digest": spec_digest,
            "criteria": {"AC-001": ["tests.test_demo.DemoTests.test_one"]},
        }
        manifest_file = feature / "acceptance-evidence.json"
        manifest_file.write_text(json.dumps(manifest))
        ledger.archive_manifest(self.root, "run_1", FEATURE)
        manifest_digest = hashlib.sha256(manifest_file.read_bytes()).hexdigest()
        digests = ledger.artifact_digests(self.root, FEATURE)
        tree = digests["tree"]
        ledger.append(
            self.root,
            ledger.new_event(
                "run_1",
                FEATURE,
                "snapshot",
                "operator-attested",
                digests,
            ),
        )
        ledger.append(
            self.root,
            ledger.new_event(
                "run_1",
                FEATURE,
                "verification",
                "operator-attested",
                {
                    "check_id": "tests.test_demo.DemoTests.test_one",
                    "status": "passed",
                    "ac_id": "AC-001",
                    "snapshot": tree,
                    "spec_digest": spec_digest,
                    "manifest_digest": manifest_digest,
                },
            ),
        )
        result = ledger.report(self.root, "run_1")
        self.assertEqual(result["outcome"]["ac_executable_coverage"], "1/1")
        self.assertEqual(result["efficiency"]["status"], "unavailable")
        ledger.append(
            self.root,
            ledger.new_event(
                "run_1",
                FEATURE,
                "verification",
                "operator-attested",
                {
                    "check_id": "tests.test_demo.DemoTests.test_one",
                    "status": "failed",
                    "ac_id": "AC-001",
                    "snapshot": tree,
                    "spec_digest": spec_digest,
                    "manifest_digest": manifest_digest,
                },
            ),
        )
        self.assertEqual(
            ledger.report(self.root, "run_1")["outcome"]["ac_status"],
            {"AC-001": "failed"},
        )
        (self.root / "changed.py").write_text("answer = 42\n")
        self.assertEqual(
            ledger.report(self.root, "run_1")["outcome"]["ac_status"],
            {"AC-001": "stale"},
        )

    def test_live_snapshot_becomes_stale_after_code_change(self) -> None:
        self.write_run([], None)
        ledger.import_run(self.root, "run_1")
        digests = ledger.artifact_digests(self.root, FEATURE)
        ledger.append(
            self.root,
            ledger.new_event(
                "run_1", FEATURE, "snapshot", "operator-attested", digests
            ),
        )
        self.assertEqual(
            ledger.report(self.root, "run_1")["outcome"]["snapshot_freshness"],
            "current",
        )
        (self.root / "changed.py").write_text("answer = 42\n")
        self.assertEqual(
            ledger.report(self.root, "run_1")["outcome"]["snapshot_freshness"],
            "stale",
        )

    def test_partial_usage_and_missing_attempts_remain_unavailable(self) -> None:
        usage = ledger.new_event(
            "run_1",
            FEATURE,
            "usage",
            "client-counter",
            {
                "invocation_id": "i1",
                "stage": "implement",
                "scope": "invocation",
                "counter_source": "client-report",
                "counter_digest": "a" * 64,
                "input_tokens": 10,
                "output_tokens": 5,
                "cached_tokens": 0,
                "complete": False,
            },
        )
        incomplete_counter = dict(usage["data"])
        incomplete_counter.pop("counter_digest")
        with self.assertRaisesRegex(ledger.LedgerError, "missing"):
            ledger.new_event(
                "run_1", FEATURE, "usage", "client-counter", incomplete_counter
            )
        self.assertEqual(
            ledger._usage([usage], 1)["reason"],  # noqa: SLF001 - Pure metric seam.
            "partial client usage scope",
        )
        usage["data"]["complete"] = True
        result = ledger._usage([usage], 1)  # noqa: SLF001 - Pure metric seam.
        self.assertEqual(result["value"]["rework"]["status"], "unavailable")
        self.assertEqual(result["value"]["total"]["input_tokens"], 10)
        overlapping = ledger.new_event(
            "run_1", FEATURE, "usage", "client-counter", dict(usage["data"])
        )
        self.assertEqual(
            ledger._usage([usage, overlapping], 1)["reason"],  # noqa: SLF001
            "overlapping invocation counters",
        )
        counted = ledger.new_event(
            "run_1",
            FEATURE,
            "usage",
            "client-counter",
            {**usage["data"], "cause_id": "same-cause", "attempt": 1},
        )
        attempts = [
            ledger.new_event(
                "run_1",
                FEATURE,
                "route",
                "operator-attested",
                {
                    "stage": "implement",
                    "route_source": "deterministic",
                    "cause_id": "same-cause",
                    "attempt": attempt,
                    "outcome": "mechanical-failure" if attempt == 1 else "success",
                },
            )
            for attempt in (1, 2)
        ]
        self.assertEqual(
            ledger._usage([*attempts, counted], 1)["reason"],  # noqa: SLF001
            "attempt counter missing",
        )

    def test_mechanical_and_rejected_attempts_count_as_rework(self) -> None:
        for failure in ("mechanical-failure", "rejected"):
            with self.subTest(failure=failure):
                events = []
                for attempt, outcome in ((1, failure), (2, "success")):
                    events.append(
                        ledger.new_event(
                            "run_1",
                            FEATURE,
                            "route",
                            "operator-attested",
                            {
                                "stage": "implement",
                                "route_source": "deterministic",
                                "cause_id": "same-cause",
                                "attempt": attempt,
                                "outcome": outcome,
                            },
                        )
                    )
                    events.append(
                        ledger.new_event(
                            "run_1",
                            FEATURE,
                            "usage",
                            "client-counter",
                            {
                                "invocation_id": f"try-{attempt}",
                                "stage": "implement",
                                "scope": "invocation",
                                "counter_source": "client-report",
                                "counter_digest": f"{attempt:064x}",
                                "input_tokens": 10,
                                "output_tokens": 5,
                                "cached_tokens": 0,
                                "complete": True,
                                "cause_id": "same-cause",
                                "attempt": attempt,
                            },
                        )
                    )
                result = ledger._usage(events, 1)  # noqa: SLF001 - Metric seam.
                self.assertEqual(result["status"], "available")
                self.assertEqual(result["value"]["rework"]["value"]["tokens"], 30)
                self.assertEqual(ledger._underpowered([events[0], events[2]]), [])  # noqa: SLF001

    def test_rework_counts_each_cycle_and_withholds_unresolved_failure(self) -> None:
        events = []
        for attempt, outcome in enumerate(
            ("mechanical-failure", "success", "rejected", "success"), 1
        ):
            events.extend(
                [
                    ledger.new_event(
                        "run_1",
                        FEATURE,
                        "route",
                        "operator-attested",
                        {
                            "stage": "implement",
                            "route_source": "deterministic",
                            "cause_id": "same-cause",
                            "attempt": attempt,
                            "outcome": outcome,
                        },
                    ),
                    ledger.new_event(
                        "run_1",
                        FEATURE,
                        "usage",
                        "client-counter",
                        {
                            "invocation_id": f"try-{attempt}",
                            "stage": "implement",
                            "scope": "invocation",
                            "counter_source": "client-report",
                            "counter_digest": f"{attempt:064x}",
                            "input_tokens": 10,
                            "output_tokens": 5,
                            "cached_tokens": 0,
                            "complete": True,
                            "cause_id": "same-cause",
                            "attempt": attempt,
                        },
                    ),
                ]
            )
        complete = ledger._usage(events, 1)  # noqa: SLF001 - Metric seam.
        self.assertEqual(complete["value"]["rework"]["value"]["tokens"], 60)
        incomplete = ledger._usage(events[:-2], 1)  # noqa: SLF001 - Metric seam.
        self.assertEqual(incomplete["value"]["rework"]["status"], "unavailable")

    def test_review_identity_and_actual_route_policy_signal(self) -> None:
        policy = self.root / "docs/policies/model-routing.md"
        policy.parent.mkdir(parents=True)
        policy.write_text(
            "| Work | Default profile / effort | Escalate when |\n"
            "| --- | --- | --- |\n"
            "| Normal R1 implementation | `standard` medium | Uncertainty |\n"
        )
        self.write_run([], None)
        ledger.import_run(self.root, "run_1")
        ledger.append(
            self.root,
            ledger.new_event(
                "run_1",
                FEATURE,
                "route",
                "operator-attested",
                {
                    "stage": "implement",
                    "provider": "OpenAI",
                    "profile": "senior",
                    "effort": "high",
                    "policy_row": "Normal R1 implementation",
                    "route_source": "deterministic",
                    "alternate_available": True,
                },
            ),
        )
        ledger.append(
            self.root,
            ledger.new_event(
                "run_1",
                FEATURE,
                "route",
                "operator-attested",
                {
                    "stage": "implement",
                    "provider": "OpenAI",
                    "profile": "standard",
                    "effort": "medium",
                    "policy_row": "Normal R1 implementation",
                    "route_source": "deterministic",
                },
            ),
        )
        ledger.append(
            self.root,
            ledger.new_event(
                "run_1",
                FEATURE,
                "review",
                "agent-reported",
                {
                    "review_id": "self",
                    "kind": "implementation",
                    "verdict": "approved",
                    "author_id": "same",
                    "reviewer_id": "same",
                },
            ),
        )
        ledger.append(
            self.root,
            ledger.new_event(
                "run_1",
                FEATURE,
                "review",
                "operator-attested",
                {
                    "review_id": "peer",
                    "kind": "implementation",
                    "verdict": "approved",
                    "author_id": "author",
                    "reviewer_id": "reviewer",
                    "author_provider": "OpenAI",
                    "reviewer_provider": "Anthropic",
                    "alternate_available": True,
                },
            ),
        )
        routing = ledger.report(self.root, "run_1")["routing"]
        self.assertEqual(routing["policy_overpowered_signals"], 1)
        self.assertEqual(
            routing["policy_comparisons"][1]["value"]["matches_default"], True
        )
        self.assertEqual(ledger.aggregate(self.root)["policy_overpowered_signals"], 1)
        self.assertEqual(routing["independent_reviews"], 1)
        self.assertEqual(routing["cross_provider_reviews"], 1)
        self.assertEqual(
            routing["review_provider_availability"][1],
            {
                "review_id": "peer",
                "alternate_available": True,
                "independent": True,
                "cross_provider": True,
            },
        )
        self.assertIsNone(
            routing["review_provider_availability"][0]["alternate_available"]
        )
        self.assertNotIn("model", routing["actual_routes"][0])

    def test_policy_snapshot_is_frozen_before_import(self) -> None:
        policy = self.root / "docs/policies/model-routing.md"
        policy.parent.mkdir(parents=True)
        policy.write_text(
            "| Work | Default profile / effort | Escalate when |\n"
            "| --- | --- | --- |\n"
            "| Normal R1 implementation | `standard` medium | Uncertainty |\n"
        )
        self.write_run([], None)
        frozen = ledger.archive_policy(self.root, "run_1")
        policy.write_text(policy.read_text().replace("standard", "senior"))
        ledger.import_run(self.root, "run_1")
        events, problems = ledger.read(self.root, "run_1")
        self.assertEqual(problems, [])
        self.assertEqual(events[0]["data"]["policy_digest"], frozen["digest"])
        self.assertEqual(
            json.loads(
                (ledger.archive_dir(self.root, "run_1") / "policy.json").read_text()
            )["rows"]["Normal R1 implementation"],
            "`standard` medium",
        )

    def test_policy_signal_respects_escalation_and_human_override(self) -> None:
        policy = self.root / "docs/policies/model-routing.md"
        policy.parent.mkdir(parents=True)
        policy.write_text(
            "| Work | Default profile / effort | Escalate when |\n"
            "| --- | --- | --- |\n"
            "| Normal R1 implementation | `standard` medium | Uncertainty |\n"
        )
        self.write_run([], None)
        ledger.import_run(self.root, "run_1")
        ledger.append(
            self.root,
            ledger.new_event(
                "run_1",
                FEATURE,
                "escalation",
                "operator-attested",
                {
                    "stage": "implement",
                    "from_profile": "standard",
                    "to_profile": "senior",
                    "reason": "reasoning-failure",
                    "attempt": 1,
                },
            ),
        )
        route = {
            "stage": "implement",
            "profile": "senior",
            "effort": "high",
            "policy_row": "Normal R1 implementation",
            "route_source": "escalation",
            "attempt": 2,
        }
        ledger.append(
            self.root,
            ledger.new_event(
                "run_1",
                FEATURE,
                "route",
                "operator-attested",
                route,
            ),
        )
        ledger.append(
            self.root,
            ledger.new_event(
                "run_1",
                FEATURE,
                "human_action",
                "operator-attested",
                {"action": "route_override", "stage": "review"},
            ),
        )
        ledger.append(
            self.root,
            ledger.new_event(
                "run_1",
                FEATURE,
                "route",
                "operator-attested",
                {**route, "stage": "review", "route_source": "human-override"},
            ),
        )
        comparisons = ledger.report(self.root, "run_1")["routing"]["policy_comparisons"]
        self.assertEqual(
            [item["value"]["above_default_without_reason"] for item in comparisons],
            [False, False],
        )

    def test_real_policy_row_punctuation_is_recordable(self) -> None:
        policy = self.root / "docs/policies/model-routing.md"
        policy.parent.mkdir(parents=True)
        shutil.copyfile(ROOT / "templates/policies/model-routing.md", policy)
        self.write_run([], None)
        ledger.archive_policy(self.root, "run_1")
        ledger.import_run(self.root, "run_1")
        for row, stage, profile in (
            ("`speckit-plan`", "planning", "standard"),
            ("Security, architecture, migration review", "security-review", "senior"),
        ):
            ledger._record(  # noqa: SLF001 - Exercise CLI's archived-row validation.
                self.root,
                "run_1",
                FEATURE,
                "route",
                "operator-attested",
                {
                    "stage": stage,
                    "profile": profile,
                    "effort": "medium",
                    "route_source": "deterministic",
                    "policy_row": row,
                },
            )
        comparisons = ledger.report(self.root, "run_1")["routing"]["policy_comparisons"]
        self.assertEqual(
            [item["value"]["matches_default"] for item in comparisons], [True, True]
        )
        with self.assertRaisesRegex(ledger.LedgerError, "archived policy"):
            ledger._record(  # noqa: SLF001 - Exercise CLI's archived-row validation.
                self.root,
                "run_1",
                FEATURE,
                "route",
                "operator-attested",
                {
                    "stage": "planning",
                    "profile": "standard",
                    "effort": "medium",
                    "route_source": "deterministic",
                    "policy_row": "Invented work",
                },
            )

    def test_explicit_record_cannot_forge_snapshot_or_ac_check(self) -> None:
        self.write_run([], None)
        ledger.import_run(self.root, "run_1")
        before = ledger.ledger_path(self.root, "run_1").read_bytes()
        with self.assertRaisesRegex(ledger.LedgerError, "snapshot command"):
            ledger._record(  # noqa: SLF001 - CLI validation boundary.
                self.root,
                "run_1",
                FEATURE,
                "snapshot",
                "operator-attested",
                {"tree": "a" * 64},
            )
        with self.assertRaisesRegex(ledger.LedgerError, "check command"):
            ledger._record(  # noqa: SLF001 - CLI validation boundary.
                self.root,
                "run_1",
                FEATURE,
                "verification",
                "operator-attested",
                {
                    "check_id": "tests.test_demo.DemoTests.test_one",
                    "status": "passed",
                    "ac_id": "AC-001",
                },
            )
        with self.assertRaisesRegex(ledger.LedgerError, "current artifact digests"):
            ledger._record(  # noqa: SLF001 - CLI validation boundary.
                self.root,
                "run_1",
                FEATURE,
                "review",
                "operator-attested",
                {
                    "review_id": "peer",
                    "kind": "implementation",
                    "verdict": "approved",
                    "snapshot": "a" * 64,
                },
            )
        self.assertEqual(ledger.ledger_path(self.root, "run_1").read_bytes(), before)
        with patch.dict(os.environ, {"BALLAST_SPEC_WORKFLOW": "1"}):
            with self.assertRaisesRegex(ledger.LedgerError, "agent step"):
                ledger._check(  # noqa: SLF001 - Operator boundary regression.
                    self.root, "run_1", "AC-001", "tests.test_demo.DemoTests.test_one"
                )
            with patch.object(ledger, "ROOT", self.root):
                self.assertEqual(ledger.main(["snapshot", "run_1"]), 2)

    def test_skipped_mapped_unittest_cannot_pass_ac(self) -> None:
        self.write_run([], None)
        ledger.import_run(self.root, "run_1")
        feature = self.root / FEATURE
        spec = feature / "spec.md"
        spec.write_text("- **AC-001**: A fictional check.\n")
        digest = hashlib.sha256(spec.read_bytes()).hexdigest()
        (feature / "intent.md").write_text(f"Approved spec sha256:{digest}\n")
        test_id = "tests.test_demo.DemoTests.test_skipped"
        (feature / "acceptance-evidence.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "spec_digest": digest,
                    "criteria": {"AC-001": [test_id]},
                }
            )
        )
        test_dir = self.root / "tests"
        test_dir.mkdir()
        (test_dir / "__init__.py").write_text("")
        (test_dir / "test_demo.py").write_text(
            "import unittest\n"
            "class DemoTests(unittest.TestCase):\n"
            "    @unittest.skip('fixture')\n"
            "    def test_skipped(self):\n"
            "        pass\n"
        )
        interpreter = self.root / ".venv/bin/python"
        interpreter.parent.mkdir(parents=True)
        interpreter.symlink_to(Path(sys.executable).resolve())
        self.assertEqual(ledger._check(self.root, "run_1", "AC-001", test_id), 1)  # noqa: SLF001
        events, problems = ledger.read(self.root, "run_1")
        self.assertEqual(problems, [])
        self.assertEqual(
            [
                event["data"]["status"]
                for event in events
                if event["kind"] == "verification"
            ],
            ["failed"],
        )

    def test_manifest_versions_preserve_approved_mappings(self) -> None:
        feature = self.root / FEATURE
        spec = feature / "spec.md"
        spec.write_text("- **AC-001**: Fictional behavior.\n")
        digest = hashlib.sha256(spec.read_bytes()).hexdigest()
        (feature / "intent.md").write_text(f"Approved spec: sha256:{digest}\n")
        manifest = feature / "acceptance-evidence.json"
        manifest.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "spec_digest": digest,
                    "criteria": {"AC-001": ["tests.test_demo.DemoTests.test_one"]},
                }
            )
        )
        archived = ledger.archive_manifest(self.root, "run_1", FEATURE)
        self.assertEqual(set(archived["criteria"]), {"AC-001"})
        first_digest = hashlib.sha256(manifest.read_bytes()).hexdigest()
        manifest.write_text(manifest.read_text().replace("test_one", "test_two"))
        second = ledger.archive_manifest(self.root, "run_1", FEATURE)
        second_digest = hashlib.sha256(manifest.read_bytes()).hexdigest()
        self.assertNotEqual(first_digest, second_digest)
        self.assertEqual(
            second["criteria"]["AC-001"], ["tests.test_demo.DemoTests.test_two"]
        )
        archive = ledger.archive_dir(self.root, "run_1") / "manifests"
        self.assertTrue((archive / f"{first_digest}.json").is_file())
        self.assertTrue((archive / f"{second_digest}.json").is_file())
        manifest.write_text(manifest.read_text().replace(digest, "f" * 64))
        with self.assertRaisesRegex(ledger.LedgerError, "approved spec"):
            ledger.archive_manifest(self.root, "run_1", FEATURE)

    def test_stale_manifest_does_not_block_runner_snapshot(self) -> None:
        feature = self.root / FEATURE
        spec = feature / "spec.md"
        spec.write_text("- **AC-001**: Original fictional behavior.\n")
        approved = hashlib.sha256(spec.read_bytes()).hexdigest()
        (feature / "intent.md").write_text(f"Approved spec sha256:{approved}\n")
        (feature / "acceptance-evidence.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "spec_digest": approved,
                    "criteria": {"AC-001": ["tests.test_demo.DemoTests.test_one"]},
                }
            )
        )
        self.write_run(
            [
                {"event": "step_started", "step_id": "approve-intent", "type": "gate"},
                {
                    "event": "step_completed",
                    "step_id": "approve-intent",
                    "status": "paused",
                },
                {"event": "workflow_finished", "status": "paused"},
            ]
        )
        run = self.root / ".specify/workflows/runs/run_1"
        (run / "workflow.yml").write_text(
            "workflow:\n  id: ballast-feature\n  version: 1.1.0\n"
            "steps:\n  - id: approve-intent\n    type: gate\n"
        )
        state = json.loads((run / "state.json").read_text())
        state["step_results"] = {
            "approve-intent": {
                "type": "gate",
                "output": {"choice": "reject"},
            }
        }
        (run / "state.json").write_text(json.dumps(state))
        ledger.import_run(self.root, "run_1")
        spec.write_text("- **AC-001**: Revised fictional behavior.\n")
        self.assertEqual(ledger.import_run(self.root, "run_1"), 1)
        events, problems = ledger.read(self.root, "run_1")
        self.assertEqual(problems, [])
        self.assertEqual(events[-1]["kind"], "snapshot")
        self.assertEqual(events[-1]["source"], "runner")
        self.assertEqual(
            ledger.report(self.root, "run_1")["outcome"]["manifest_status"], "stale"
        )
        with patch.object(ledger, "ROOT", self.root):
            self.assertEqual(ledger.main(["snapshot", "run_1"]), 0)
        self.assertEqual(
            ledger.read(self.root, "run_1")[0][-1]["source"], "operator-attested"
        )

    def test_structured_finding_updates_count_once(self) -> None:
        self.write_run([], None)
        ledger.import_run(self.root, "run_1")
        ledger.append(
            self.root,
            ledger.new_event(
                "run_1",
                FEATURE,
                "review",
                "operator-attested",
                {
                    "review_id": "peer",
                    "kind": "implementation",
                    "verdict": "changes-requested",
                    "author_id": "author",
                    "reviewer_id": "reviewer",
                },
            ),
        )
        for resolution in ("open", "resolved"):
            ledger.append(
                self.root,
                ledger.new_event(
                    "run_1",
                    FEATURE,
                    "finding",
                    "operator-attested",
                    {
                        "review_id": "peer",
                        "finding_id": "f1",
                        "severity": "high",
                        "resolution": resolution,
                    },
                ),
            )
        outcome = ledger.report(self.root, "run_1")["outcome"]
        self.assertEqual(outcome["material_findings"], {"high": 1})
        self.assertEqual(outcome["finding_resolutions"], {"resolved": 1})

    def test_underpowered_and_rework_require_ordered_attempts(self) -> None:
        self.write_run([], None)
        ledger.import_run(self.root, "run_1")
        for attempt, profile, outcome in (
            (1, "standard", "reasoning-failure"),
            (2, "standard", "reasoning-failure"),
            (3, "senior", "success"),
        ):
            ledger.append(
                self.root,
                ledger.new_event(
                    "run_1",
                    FEATURE,
                    "route",
                    "operator-attested",
                    {
                        "stage": "implement",
                        "profile": profile,
                        "effort": "medium",
                        "route_source": "escalation"
                        if profile == "senior"
                        else "deterministic",
                        "cause_id": "same-cause",
                        "attempt": attempt,
                        "outcome": outcome,
                    },
                ),
            )
            ledger.append(
                self.root,
                ledger.new_event(
                    "run_1",
                    FEATURE,
                    "usage",
                    "client-counter",
                    {
                        "invocation_id": f"call-{attempt}",
                        "stage": "implement",
                        "scope": "invocation",
                        "counter_source": "client-report",
                        "counter_digest": f"{attempt:064x}",
                        "input_tokens": 10,
                        "output_tokens": 5,
                        "cached_tokens": 0,
                        "complete": True,
                        "cause_id": "same-cause",
                        "attempt": attempt,
                    },
                ),
            )
        result = ledger.report(self.root, "run_1")
        self.assertEqual(
            result["routing"]["underpowered_signals"], ["implement:same-cause"]
        )
        rework = result["efficiency"]["value"]["rework"]
        self.assertEqual(rework["status"], "available")
        self.assertEqual(
            rework["value"], {"tokens": 45, "ratio": 1.0, "by_stage": {"implement": 45}}
        )

    def test_duplicate_route_attempt_cannot_create_underpowered_signal(self) -> None:
        ledger.append(self.root, self.event("run", {"action": "started"}, "start"))
        failed = {
            "stage": "implement",
            "route_source": "deterministic",
            "cause_id": "same-cause",
            "attempt": 1,
            "outcome": "reasoning-failure",
            "profile": "standard",
        }
        first = ledger.new_event(
            "run_1", FEATURE, "route", "operator-attested", failed, "attempt-1"
        )
        ledger.append(self.root, first)
        success = ledger.new_event(
            "run_1",
            FEATURE,
            "route",
            "operator-attested",
            {**failed, "attempt": 2, "outcome": "success", "profile": "senior"},
            "attempt-2",
        )
        for duplicate in (failed, {**failed, "outcome": "mechanical-failure"}):
            with self.subTest(duplicate=duplicate["outcome"]):
                second = ledger.new_event(
                    "run_1",
                    FEATURE,
                    "route",
                    "operator-attested",
                    duplicate,
                    f"duplicate-{duplicate['outcome']}",
                )
                with self.assertRaisesRegex(
                    ledger.LedgerError, "duplicate route attempt"
                ):
                    ledger.append(self.root, second)
                self.assertEqual(ledger._underpowered([first, second, success]), [])  # noqa: SLF001

    def test_classifier_and_escalation_accounting(self) -> None:
        self.write_run([], None)
        ledger.import_run(self.root, "run_1")
        for attempt, outcome in ((1, "reasoning-failure"), (2, "success")):
            if outcome == "success":
                ledger.append(
                    self.root,
                    ledger.new_event(
                        "run_1",
                        FEATURE,
                        "escalation",
                        "operator-attested",
                        {
                            "stage": "implement",
                            "from_profile": "standard",
                            "to_profile": "senior",
                            "attempt": 1,
                        },
                    ),
                )
            ledger.append(
                self.root,
                ledger.new_event(
                    "run_1",
                    FEATURE,
                    "route",
                    "operator-attested",
                    {
                        "stage": "implement",
                        "profile": "senior" if outcome == "success" else "standard",
                        "effort": "medium",
                        "route_source": "escalation"
                        if outcome == "success"
                        else "deterministic",
                        "cause_id": "reason",
                        "attempt": attempt,
                        "outcome": outcome,
                    },
                ),
            )
            ledger.append(
                self.root,
                ledger.new_event(
                    "run_1",
                    FEATURE,
                    "usage",
                    "client-counter",
                    {
                        "invocation_id": f"try-{attempt}",
                        "stage": "implement",
                        "scope": "invocation",
                        "counter_source": "client-report",
                        "counter_digest": f"{attempt:064x}",
                        "input_tokens": 10,
                        "output_tokens": 5,
                        "cached_tokens": 0,
                        "complete": True,
                        "profile": "senior" if outcome == "success" else "standard",
                        "model": "model-b" if outcome == "success" else "model-a",
                        "cause_id": "reason",
                        "attempt": attempt,
                    },
                ),
            )
        ledger.append(
            self.root,
            ledger.new_event(
                "run_1",
                FEATURE,
                "classifier",
                "operator-attested",
                {"stage": "triage", "invocation_id": "classifier-1"},
            ),
        )
        ledger.append(
            self.root,
            ledger.new_event(
                "run_1",
                FEATURE,
                "usage",
                "client-counter",
                {
                    "invocation_id": "classifier-1",
                    "stage": "triage",
                    "scope": "invocation",
                    "counter_source": "client-report",
                    "counter_digest": "f" * 64,
                    "input_tokens": 4,
                    "output_tokens": 2,
                    "cached_tokens": 0,
                    "complete": True,
                    "profile": "economy",
                    "model": "classifier-model",
                },
            ),
        )
        value = ledger.report(self.root, "run_1")["efficiency"]["value"]
        self.assertEqual(value["classifier_tokens"]["value"], 6)
        self.assertEqual(value["by_stage"]["implement"]["input_tokens"], 20)
        self.assertEqual(value["by_profile"]["senior"]["output_tokens"], 5)
        self.assertEqual(value["by_model"]["classifier-model"]["input_tokens"], 4)
        self.assertEqual(value["rework"]["value"]["tokens"], 30)
        self.assertEqual(
            value["before_after_escalation"]["value"],
            [{"stage": "implement", "before_tokens": 15, "after_tokens": 15}],
        )
        aggregate = ledger.aggregate(self.root)
        self.assertEqual(
            aggregate["rework_by_stage"],
            {
                "tokens": {"implement": 30},
                "runs_with_evidence": 1,
            },
        )
        self.assertEqual(aggregate["escalations_by_stage"], {"implement": 1})
        self.assertEqual(
            aggregate["classifier_overhead"],
            {
                "tokens": 6,
                "runs_with_evidence": 1,
            },
        )

    def test_human_actions_and_aggregate_are_observed_only(self) -> None:
        self.write_run([], None)
        ledger.import_run(self.root, "run_1")
        for action in ("manual_recovery", "route_override", "product_decision"):
            data = {"action": action}
            if action == "product_decision":
                data["gate_id"] = "scope-gate"
            ledger.append(
                self.root,
                ledger.new_event(
                    "run_1",
                    FEATURE,
                    "human_action",
                    "operator-attested",
                    data,
                ),
            )
        path = ledger.ledger_path(self.root, "run_1")
        before = path.read_bytes()
        single = ledger.report(self.root, "run_1")
        aggregate = ledger.aggregate(self.root)
        self.assertEqual(single["human_effort"]["manual_recovery"], 1)
        self.assertEqual(single["human_effort"]["route_overrides"], 1)
        self.assertEqual(single["human_effort"]["product_decisions_requested"], 1)
        self.assertEqual(aggregate["instrumented_runs"], 1)
        self.assertEqual(aggregate["classifier_overhead"]["runs_with_evidence"], 0)
        (ledger.archive_dir(self.root, "uninstrumented") / "run").mkdir(parents=True)
        self.assertEqual(ledger.aggregate(self.root)["instrumented_runs"], 1)
        self.assertEqual(path.read_bytes(), before)
        output = io.StringIO()
        with patch.object(ledger, "ROOT", self.root), redirect_stdout(output):
            self.assertEqual(ledger.main(["report", "--all", "--json"]), 0)
        self.assertEqual(json.loads(output.getvalue())["instrumented_runs"], 1)
        output = io.StringIO()
        with patch.object(ledger, "ROOT", self.root), redirect_stdout(output):
            self.assertEqual(ledger.main(["report", "--run", "run_1"]), 0)
        self.assertIn("human_effort", output.getvalue())
        output = io.StringIO()
        with patch.object(ledger, "ROOT", self.root), redirect_stdout(output):
            self.assertEqual(ledger.main(["report", FEATURE]), 0)
        self.assertIn("Instrumented runs: 1", output.getvalue())
        output = io.StringIO()
        with patch.object(ledger, "ROOT", self.root), redirect_stdout(output):
            self.assertEqual(ledger.main(["report", FEATURE, "--json"]), 0)
        self.assertEqual(json.loads(output.getvalue())["instrumented_runs"], 1)
        self.assertEqual(path.read_bytes(), before)

    def test_worktree_removal_keeps_archive(self) -> None:
        self.write_run([], None)
        git(
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
        child = self.root / "child"
        git(self.root, "worktree", "add", "-q", "--detach", str(child))
        child_run = child / ".specify/workflows/runs/run_1"
        shutil.copytree(self.root / ".specify/workflows/runs/run_1", child_run)
        ledger.import_run(child, "run_1")
        archive = ledger.archive_dir(child, "run_1")
        shutil.copytree(child_run, archive / "run")
        git(self.root, "worktree", "remove", "--force", str(child))
        shutil.rmtree(self.root / ".specify/workflows/runs/run_1")
        self.assertEqual(len(ledger.read(self.root, "run_1")[0]), 1)
        result = ledger.report(self.root, "run_1")
        self.assertEqual(result["status"], "incomplete")
        self.assertEqual(result["feature"], FEATURE)


if __name__ == "__main__":
    unittest.main()
