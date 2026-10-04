"""Recorders and mode-aware checks of artifacts.py in Autonomous runs.

Each test fakes the agent wrapper's operator records directly (a step entry
in steps.jsonl and the operator copy of each draft), then runs artifacts.py as
the workflow does: `python3 -I -S artifacts.py <check> --run run42`.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_autonomy import FEATURE, TOOLS, AutonomyCase, autonomy

sys.path.pop(0)

ARTIFACTS = TOOLS / "artifacts.py"
SPEC = """# Feature Specification: Demo run

**Created**: 2026-10-03

## User Scenarios

### User Story 1 - Demo (Priority: P1)

1. **Given** a demo, **When** it runs, **Then** it works. [AC-001]
"""
PLAN = "# Implementation Plan: Demo run\n\n**Spec**: [spec.md](spec.md)\n"
TASKS = "# Tasks: Demo run\n\n- [x] T001 Implement demo in src/demo.py\n"
PASS_BWRAP = """#!/usr/bin/env python3
import os, sys
args = sys.argv[1:]
command = args[args.index("--") + 1 :]
os.execvp(command[0], command)
"""  # noqa: S105 - a script, not a secret


class RecorderCase(AutonomyCase):
    """An active Autonomous run on a feature with a spec."""

    def setUp(self) -> None:
        super().setUp()
        bwrap = self.bin / "bwrap"
        bwrap.write_text(PASS_BWRAP)
        bwrap.chmod(0o755)
        runs = self.root / ".specify/workflows/runs/run42"
        runs.mkdir(parents=True)
        (runs / "inputs.json").write_text(
            json.dumps({"inputs": {"feature_directory": FEATURE}})
        )
        (runs / "state.json").write_text(
            json.dumps({"workflow_id": "ballast-autonomous"})
        )
        self.feature = self.root / FEATURE
        (self.feature / "reviews").mkdir(parents=True)
        (self.feature / "spec.md").write_text(SPEC)
        self.make_run()
        self.count = 0

    # -- helpers --------------------------------------------------------

    def step(
        self,
        drafts: dict[str, object] | None = None,
        *,
        role: str = "author",
        integration: str = "claude",
    ) -> str:
        """Fake one wrapped agent step that wrote drafts."""
        self.count += 1
        name = f"step{self.count:02d}"
        exclusions = (f"{FEATURE}/reviews", f"{FEATURE}/autonomous/drafts")
        tree_before = autonomy.tree_digest(self.root, exclusions)
        directory = autonomy.drafts_dir(self.root, FEATURE)
        listed = {}
        for file_name, content in (drafts or {}).items():
            data = (
                content if isinstance(content, bytes) else json.dumps(content).encode()
            )
            directory.mkdir(parents=True, exist_ok=True)
            (directory / file_name).write_bytes(data)
            copy = autonomy.snapshot_draft(self.root, "run42", name, file_name)
            copy.parent.mkdir(parents=True, exist_ok=True)
            copy.write_bytes(data)
            listed[file_name] = hashlib.sha256(data).hexdigest()
        autonomy.append_step(
            self.root,
            "run42",
            {
                "step": name,
                "ran": True,
                "command": "/speckit-x",
                "integration": integration,
                "role": role,
                "set_aside": [],
                "tree_before": tree_before,
                "drafts": listed,
                "exit_code": 0,
                "at": autonomy.now(),
            },
        )
        return name

    def draft(self, point: str, /, **changes: object) -> dict:
        data = {
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
            "review": None,
            "assumption": None,
        }
        data.update(changes)
        return data

    def review_draft(
        self, point: str, kind: str, findings: list | None = None, **changes: object
    ) -> dict:
        # The report names of speckit.ballast.review's table.
        name = "convergence" if kind == "spec-reconciliation" else kind
        report = self.feature / "reviews" / f"{name}.md"
        if not report.exists():
            report.write_text(f"# {kind} review\n\nLooks consistent.\n")
        return self.draft(
            point,
            review={
                "kind": kind,
                "verdict": "approved",
                "report": f"{FEATURE}/reviews/{name}.md",
                "findings": findings or [],
                **changes,
            },
        )

    def check(self, check: str, *extra: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(  # noqa: S603
            [
                sys.executable,
                "-I",
                "-S",
                str(ARTIFACTS),
                check,
                "--run",
                "run42",
                *extra,
            ],
            cwd=self.root,
            capture_output=True,
            text=True,
            check=False,
            env={**os.environ, "BALLAST_SPEC_WORKFLOW": "1"},
        )

    def record(self, point: str) -> subprocess.CompletedProcess[str]:
        return self.check("record-decision", "--point", point)

    def ok(self, result: subprocess.CompletedProcess[str]) -> None:
        self.assertEqual(result.returncode, 0, result.stderr)

    def failed(self, result: subprocess.CompletedProcess[str], text: str) -> None:
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn(text, result.stderr)

    def decisions(self) -> list[dict]:
        return autonomy.read_decisions(self.root, "run42")

    def block(self) -> dict | None:
        return autonomy.read_block(self.root, "run42")

    def intent(self) -> None:
        self.step({"intent.json": self.draft("intent")})
        self.ok(self.check("record-provisional-intent"))


class RecordDecisionTests(RecorderCase):
    """AC-002, AC-003, AC-007, FR-010, FR-011, FR-013: the generic recorder."""

    def test_records_one_provisional_decision(self) -> None:
        step = self.step({"plan.json": self.draft("plan")})
        self.ok(self.record("plan"))
        (entry,) = self.decisions()
        self.assertEqual(
            (entry["id"], entry["point"], entry["decision"]),
            ("PD-0001", "plan", "accept"),
        )
        self.assertEqual(
            entry["agent"],
            {
                "provider": "claude",
                "model": "model-x",
                "role": "author",
                "step_id": step,
            },
        )
        self.assertEqual(
            entry["artifact"]["sha256"],
            hashlib.sha256((self.feature / "spec.md").read_bytes()).hexdigest(),
        )
        record = (self.feature / "autonomous/record.md").read_text()
        self.assertIn("| PD-0001 | plan | accept (agent-provisional)", record)
        self.assertFalse((self.feature / "autonomous/drafts/plan.json").exists())
        self.assertEqual(autonomy.unconsumed_steps(self.root, "run42"), [])

    def test_planted_draft_is_refused(self) -> None:
        self.step({"plan.json": self.draft("plan")})
        (self.feature / "autonomous/drafts/tasks.json").write_text("{}")
        self.failed(self.record("plan"), "not written by the immediately preceding")
        self.assertEqual(self.decisions(), [])

    def test_draft_from_an_earlier_step_is_not_accepted(self) -> None:
        self.step({"plan.json": self.draft("plan")})
        (self.feature / "autonomous/drafts/plan.json").unlink()
        self.step()
        self.failed(self.record("plan"), "wrote no plan.json")

    def test_edited_draft_is_refused(self) -> None:
        self.step({"plan.json": self.draft("plan")})
        (self.feature / "autonomous/drafts/plan.json").write_text(
            json.dumps(self.draft("plan", summary="changed"))
        )
        self.failed(self.record("plan"), "not written by the immediately preceding")

    def test_field_rules(self) -> None:
        cases = {
            "forged approval": (
                {"summary": "Plan approved by the human"},
                "human approval",
            ),
            "forged phrase": ({"basis": "This is human-approved"}, "human approval"),
            "marker": (
                {"basis": "<!-- workflow-approval: begin -->"},
                "workflow marker",
            ),
            "multi-line": ({"summary": "a\nb"}, "one line"),
            "point": ({"point": "tasks"}, "does not match"),
            "parent path": ({"evidence": ["../outside"]}, "'..'"),
            "missing": ({"artifact": f"{FEATURE}/nope.md"}, "does not exist"),
            "no actions": ({"privileged_actions": None}, "privileged_actions"),
            "long": ({"summary": "x" * 501}, "1-500"),
        }
        for name, (changes, text) in cases.items():
            with self.subTest(name=name):
                data = self.draft("plan", **changes)
                if changes.get("privileged_actions", 0) is None:
                    del data["privileged_actions"]
                self.step({"plan.json": data})
                self.failed(self.record("plan"), text)
                for path in (self.feature / "autonomous/drafts").iterdir():
                    path.unlink()
                autonomy.consume_steps(self.root, "run42")
                (autonomy.run_dir(self.root, "run42") / "block.json").unlink(
                    missing_ok=True
                )
        self.assertEqual(self.decisions(), [])

    def test_symlinked_evidence_is_refused(self) -> None:
        (self.feature / "link.md").symlink_to(self.feature / "spec.md")
        self.step({"plan.json": self.draft("plan", evidence=[f"{FEATURE}/link.md"])})
        self.failed(self.record("plan"), "symlink")

    def test_runner_owned_fields_are_ignored_with_a_note(self) -> None:
        self.step({"plan.json": self.draft("plan", id="PD-0042", provider="codex")})
        self.ok(self.record("plan"))
        (entry,) = self.decisions()
        self.assertEqual(
            (entry["id"], entry["agent"]["provider"]), ("PD-0001", "claude")
        )
        self.assertIn("ignored runner-owned field id", entry["notes"])

    def test_edited_record_fails_the_next_check(self) -> None:
        self.step({"plan.json": self.draft("plan")})
        self.ok(self.record("plan"))
        record = self.feature / "autonomous/record.md"
        record.write_text(record.read_text().replace("plan accepted", "approved"))
        self.failed(
            self.check("spec"), "autonomous record was edited outside the recorder"
        )
        record.unlink()
        self.failed(self.check("spec"), "edited outside the recorder")

    def test_failed_check_records_a_postcondition_block(self) -> None:
        (self.feature / "spec.md").unlink()
        self.failed(self.check("spec"), "spec.md is missing")
        block = self.block()
        self.assertEqual(block["category"], "postcondition")
        self.assertEqual(block["step_id"], "spec")
        self.assertEqual(
            block["command"],
            "ballast run continue run42 --reason block-resolved --ref TEXT",
        )

    def test_inactive_run_refuses_every_check(self) -> None:
        record = autonomy.read_run(self.root, "run42")
        autonomy.set_status(record, "stopped")
        autonomy.write_run(self.root, record)
        self.failed(self.check("spec"), "not active")

    def test_autonomous_workflow_without_record_refuses(self) -> None:
        (autonomy.run_file(self.root, "run42")).unlink()
        self.failed(self.check("spec"), "no operator run record")

    def test_human_gated_checks_are_unchanged_without_a_record(self) -> None:
        (autonomy.run_file(self.root, "run42")).unlink()
        state = self.root / ".specify/workflows/runs/run42/state.json"
        state.write_text(json.dumps({"workflow_id": "ballast-feature"}))
        self.ok(self.check("spec"))


class ClarificationTests(RecorderCase):
    """AC-005, FR-017: only safe, reversible defaults are adopted."""

    def assumption(self, *, reversible: object = True) -> dict:
        return {
            "question": "Which format?",
            "default": "Plain text",
            "reversible": reversible,
        }

    def test_zero_drafts_allowed(self) -> None:
        self.step()
        self.ok(self.record("clarification"))
        self.assertEqual(self.decisions(), [])

    def test_one_decision_per_assumption(self) -> None:
        self.step(
            {
                f"clarification-{n}.json": self.draft(
                    "clarification", assumption=self.assumption()
                )
                for n in (1, 2)
            }
        )
        self.ok(self.record("clarification"))
        self.assertEqual([e["point"] for e in self.decisions()], ["clarification"] * 2)
        self.assertEqual(self.decisions()[0]["assumption"]["reversible"], True)

    def test_irreversible_assumption_is_refused(self) -> None:
        self.step(
            {
                "clarification-1.json": self.draft(
                    "clarification", assumption=self.assumption(reversible=False)
                )
            }
        )
        self.failed(self.record("clarification"), "must be a block")

    def test_unresolved_marker_still_fails(self) -> None:
        (self.feature / "spec.md").write_text(
            SPEC + "\n[NEEDS CLARIFICATION: format]\n"
        )
        self.failed(self.check("clarified-spec"), "NEEDS CLARIFICATION")


class ProvisionalIntentTests(RecorderCase):
    """FR-011, FR-012, AC-008: intent is provisional and bound to the spec."""

    def test_records_provisional_block(self) -> None:
        self.intent()
        intent = (self.feature / "intent.md").read_text()
        self.assertIn("<!-- workflow-provisional: begin -->", intent)
        self.assertIn("- **Decision**: PD-0001", intent)
        self.assertIn("- **Status**: agent-provisional, not human-approved", intent)
        self.assertNotIn("workflow-approval", intent)
        self.assertNotIn("Approved by", intent)
        self.ok(self.check("intent"))

    def test_spec_change_makes_it_stale(self) -> None:
        self.intent()
        (self.feature / "spec.md").write_text(SPEC + "\nMore.\n")
        self.failed(self.check("intent"), "stale")

    def test_forged_human_approval_is_refused(self) -> None:
        self.intent()
        intent = self.feature / "intent.md"
        digest = (
            "sha256:"
            + hashlib.sha256(
                (
                    "\n".join(line.rstrip() for line in SPEC.split("\n")).strip("\n")
                    + "\n"
                ).encode()
            ).hexdigest()
        )
        intent.write_text(
            intent.read_text()
            + "\n<!-- workflow-approval: begin -->\n- **Approved by**: human user\n"
            f"- **Spec**: {FEATURE}/spec.md\n- **Approved spec digest**: {digest}\n"
            "<!-- workflow-approval: end -->\n"
        )
        self.failed(self.check("intent"), "carries a human approval block")

    def test_provisional_block_is_not_human_approval(self) -> None:
        self.intent()
        result = subprocess.run(  # noqa: S603
            [
                sys.executable,
                "-I",
                "-S",
                str(ARTIFACTS),
                "intent",
                "--feature",
                FEATURE,
            ],
            cwd=self.root,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("no single workflow approval record", result.stderr)

    def test_renew_blocks_stale_intent_after_a_spec_change(self) -> None:
        """Review F4, FR-010, FR-012: no runner-attributed intent decision.

        A spec changed by a resolution needs a new intent decision by a
        deciding agent or a human, so the run stops as stale intent.
        """
        self.intent()
        self.ok(self.check("record-provisional-intent", "--renew"))
        self.assertEqual(len(self.decisions()), 1)
        self.step({"decision-resolution-1.json": self.draft("decision-resolution")})
        (self.feature / "decisions.md").write_text(
            "## DEC-0001 — Proposal\n\nx\n\n## DEC-0001 — Resolution\n\n"
            "- **Status**: agent-provisional\n- **Resolution**: keep\n"
        )
        self.ok(self.record("decision-resolution"))
        (self.feature / "spec.md").write_text(SPEC + "\nResolved.\n")
        self.failed(self.check("intent"), "stale")
        self.failed(
            self.check("record-provisional-intent", "--renew"), "postcondition block"
        )
        block = self.block()
        self.assertEqual(block["category"], "postcondition")
        self.assertIn("PD-0002", block["condition"])
        self.assertIn("new intent decision", block["condition"])
        self.assertEqual(
            [e["point"] for e in self.decisions()], ["intent", "decision-resolution"]
        )
        self.assertNotIn("runner", {e["agent"]["provider"] for e in self.decisions()})
        self.failed(self.check("intent"), "stale")

    def test_plain_human_gated_record_intent_keeps_a_provisional_block(self) -> None:
        """Only a continuation replaces the provisional block (SC-007)."""
        self.intent()
        result = subprocess.run(  # noqa: S603
            [
                sys.executable,
                "-I",
                "-S",
                str(ARTIFACTS),
                "record-intent",
                "--feature",
                FEATURE,
            ],
            cwd=self.root,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("workflow-provisional", (self.feature / "intent.md").read_text())


class ReviewRecorderTests(RecorderCase):
    """AC-004, AC-024, FR-016, FR-019: reviews are independent and severity blocks."""

    def test_same_provider_review_is_flagged(self) -> None:
        self.step(
            {"plan-review.json": self.review_draft("plan-review", "plan")},
            role="reviewer",
        )
        self.ok(self.record("plan-review"))
        (entry,) = self.decisions()
        self.assertFalse(entry["review"]["cross_provider"])
        self.assertEqual(entry["review"]["author_provider"], "claude")
        self.assertIn(
            "Reduced independence", (self.feature / "autonomous/record.md").read_text()
        )
        report = (self.feature / "reviews/plan.md").read_text()
        self.assertIn("<!-- ballast-findings: begin -->", report)

    def test_cross_provider_review(self) -> None:
        self.step(
            {"plan-review.json": self.review_draft("plan-review", "plan")},
            role="reviewer",
            integration="codex",
        )
        self.ok(self.record("plan-review"))
        self.assertTrue(self.decisions()[0]["review"]["cross_provider"])

    def test_author_step_cannot_supply_a_review(self) -> None:
        self.step({"plan-review.json": self.review_draft("plan-review", "plan")})
        self.failed(
            self.record("plan-review"), "not written by the immediately preceding"
        )

    def finding(
        self, severity: str, disposition: str, reason: str | None = "why"
    ) -> dict:
        return {
            "id": "F-001",
            "severity": severity,
            "label": "implementation-bug",
            "disposition": disposition,
            "reason": reason,
            "evidence": [],
        }

    def test_high_or_critical_finding_blocks_whatever_its_disposition(self) -> None:
        for severity in ("high", "critical"):
            for disposition in ("resolved", "accepted-provisionally", "open"):
                with self.subTest(severity=severity, disposition=disposition):
                    self.step(
                        {
                            "plan-review.json": self.review_draft(
                                "plan-review",
                                "plan",
                                [self.finding(severity, disposition)],
                            )
                        },
                        role="reviewer",
                    )
                    self.failed(self.record("plan-review"), "review-finding block")
                    self.assertEqual(self.block()["category"], "review-finding")
                    self.assertEqual(self.decisions(), [])
                    self.assertIn(
                        f"F-001 ({severity}",
                        (self.feature / "reviews/plan.md").read_text(),
                    )
                    for path in (self.feature / "autonomous/drafts").iterdir():
                        path.unlink()
                    autonomy.consume_steps(self.root, "run42")

    def test_only_an_approved_verdict_proceeds(self) -> None:
        """Review F5: a failed or partial review blocks, even with no finding."""
        for verdict in ("failed", "changes-requested", "partial"):
            with self.subTest(verdict=verdict):
                self.step(
                    {
                        "plan-review.json": self.review_draft(
                            "plan-review", "plan", verdict=verdict
                        )
                    },
                    role="reviewer",
                )
                result = self.record("plan-review")
                self.failed(result, "review-finding block")
                self.assertIn(f"plan verdict {verdict}", result.stderr)
                self.assertEqual(self.block()["category"], "review-finding")
                self.assertEqual(self.decisions(), [])
                for path in (self.feature / "autonomous/drafts").iterdir():
                    path.unlink()
                autonomy.consume_steps(self.root, "run42")

    def test_medium_rules(self) -> None:
        for finding, text in (
            (self.finding("medium", "accepted-provisionally", None), "needs a reason"),
            (self.finding("medium", "open"), "open is valid only"),
        ):
            with self.subTest(finding=finding):
                self.step(
                    {
                        "plan-review.json": self.review_draft(
                            "plan-review", "plan", [finding]
                        )
                    },
                    role="reviewer",
                )
                self.failed(self.record("plan-review"), text)
                for path in (self.feature / "autonomous/drafts").iterdir():
                    path.unlink()
                autonomy.consume_steps(self.root, "run42")
        self.step(
            {
                "plan-review.json": self.review_draft(
                    "plan-review",
                    "plan",
                    [self.finding("medium", "accepted-provisionally")],
                )
            },
            role="reviewer",
        )
        self.ok(self.record("plan-review"))
        self.assertIn(
            "## Open findings", (self.feature / "autonomous/record.md").read_text()
        )

    def test_finding_only_in_narrative_is_refused(self) -> None:
        (self.feature / "reviews/plan.md").write_text(
            "# Plan review\n\n- **High**: data loss\n"
        )
        self.step(
            {"plan-review.json": self.review_draft("plan-review", "plan")},
            role="reviewer",
        )
        self.failed(self.record("plan-review"), "severity tags in its narrative")
        (self.feature / "reviews/plan.md").write_text(
            "# Plan review\n\n## Findings\n\nnone\n"
        )
        for path in (self.feature / "autonomous/drafts").iterdir():
            path.unlink()
        autonomy.consume_steps(self.root, "run42")
        self.step(
            {"plan-review.json": self.review_draft("plan-review", "plan")},
            role="reviewer",
        )
        self.failed(self.record("plan-review"), "findings or severity")

    def test_reviewer_source_edit_blocks(self) -> None:
        drafts = {"plan-review.json": self.review_draft("plan-review", "plan")}
        self.step(drafts, role="reviewer")
        (self.root / "src.py").write_text("edited by the reviewer\n")
        self.failed(self.record("plan-review"), "reviewer step changed files")
        self.assertEqual(self.block()["category"], "postcondition")


class ImplementationReviewTests(RecorderCase):
    """AC-023, FR-016: required review kinds; the code is frozen afterwards."""

    def setUp(self) -> None:
        super().setUp()
        state = self.root / ".specify/workflow-state/run42"
        state.mkdir(parents=True)
        tree = subprocess.run(
            ["git", "write-tree"],  # noqa: S607
            cwd=self.root,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        (state / "implementation-baseline.json").write_text(
            json.dumps({"feature": FEATURE, "tree": tree})
        )
        (self.root / "src").mkdir()
        (self.root / "src/demo.py").write_text("print('demo')\n")

    def reviews(self, *kinds: str) -> dict:
        drafts = {
            "implementation-review.json": self.review_draft(
                "implementation-review", "engineering"
            )
        }
        for kind in kinds:
            drafts[f"specialist-review-{kind}.json"] = self.review_draft(
                "specialist-review", kind
            )
        return drafts

    def test_security_and_test_always_required(self) -> None:
        self.step(self.reviews("test"), role="reviewer", integration="codex")
        self.failed(
            self.record("implementation-review"), "required reviews missing: security"
        )
        self.assertEqual(self.decisions(), [])

    def test_complete_coverage_freezes_the_code(self) -> None:
        self.step(self.reviews("test"), role="reviewer", integration="codex")
        self.step(self.reviews("security") | {}, role="reviewer", integration="codex")
        # Two reviewer steps: drafts of the first were moved aside by the
        # wrapper; the recorder reads them from operator state.
        self.ok(self.record("implementation-review"))
        kinds = sorted(e["review"]["kind"] for e in self.decisions())
        self.assertIn("security", kinds)
        self.assertIn("test", kinds)
        self.assertTrue(autonomy.read_run(self.root, "run42")["frozen_tree"])
        (self.root / "src/demo.py").write_text("changed after review\n")
        self.step({"decision-resolution-1.json": self.draft("decision-resolution")})
        (self.feature / "decisions.md").write_text("## DEC-0001 — Resolution\n\n- x\n")
        self.failed(
            self.record("decision-resolution"), "changed after implementation review"
        )

    def test_r2_and_path_triggers_add_kinds(self) -> None:
        record = autonomy.read_run(self.root, "run42")
        record["risk"]["boundaries"] = ["agent authority"]
        autonomy.write_run(self.root, record)
        (self.root / "docs").mkdir()
        (self.root / "docs/guide.md").write_text("guide\n")
        self.step(self.reviews("test", "security"), role="reviewer")
        result = self.record("implementation-review")
        self.failed(result, "architecture")
        self.assertIn("documentation", result.stderr)

    def test_reviewer_declared_kind(self) -> None:
        drafts = self.reviews("test", "security")
        drafts["implementation-review.json"]["review"]["required_kinds"] = [
            "dependency"
        ]
        self.step(drafts, role="reviewer")
        self.failed(self.record("implementation-review"), "dependency")


class DecisionsTests(RecorderCase):
    """FR-018: provisional resolutions count only in an Autonomous run."""

    def write_decisions(self, status: str) -> None:
        (self.feature / "decisions.md").write_text(
            "## DEC-0001 — Proposal\n\nScope question.\n\n## DEC-0001 — Resolution\n\n"
            f"- **Status**: {status}\n- **Resolution**: keep\n"
        )

    def test_resolution_needs_a_logged_decision(self) -> None:
        self.intent()
        self.write_decisions("agent-provisional")
        self.failed(self.check("decisions"), "unresolved decisions: DEC-0001")
        self.step(
            {
                "decision-resolution-1.json": self.draft(
                    "decision-resolution", material=True
                )
            }
        )
        self.ok(self.record("decision-resolution"))
        text = (self.feature / "decisions.md").read_text()
        self.assertIn(
            "- **Status**: agent-provisional (PD-0002), not human-approved", text
        )
        self.assertIn("- **Material**: yes", text)
        self.ok(self.check("decisions"))
        self.assertIn(
            "PD-0002 (decision-resolution",
            (self.feature / "autonomous/record.md").read_text(),
        )

    def test_draft_must_name_a_resolution(self) -> None:
        self.write_decisions("agent-provisional")
        self.step({"decision-resolution-7.json": self.draft("decision-resolution")})
        self.failed(self.record("decision-resolution"), "match a resolution record")

    def test_human_gated_ignores_provisional_resolutions(self) -> None:
        self.write_decisions("agent-provisional (PD-0001), not human-approved")
        intent = subprocess.run(  # noqa: S603
            [
                sys.executable,
                "-I",
                "-S",
                str(ARTIFACTS),
                "record-intent",
                "--feature",
                FEATURE,
            ],
            cwd=self.root,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(intent.returncode, 0, intent.stderr)
        result = subprocess.run(  # noqa: S603
            [
                sys.executable,
                "-I",
                "-S",
                str(ARTIFACTS),
                "decisions",
                "--feature",
                FEATURE,
            ],
            cwd=self.root,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertIn("unresolved decisions: DEC-0001", result.stderr)
        self.write_decisions("resolved by the team")
        result = subprocess.run(  # noqa: S603
            [
                sys.executable,
                "-I",
                "-S",
                str(ARTIFACTS),
                "decisions",
                "--feature",
                FEATURE,
            ],
            cwd=self.root,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)


class PreflightTests(RecorderCase):
    """Start of an Autonomous run: clean tree, HEAD and Git snapshot recorded."""

    def setUp(self) -> None:
        super().setUp()
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "feature")

    def test_records_head_and_snapshot(self) -> None:
        self.ok(self.check("autonomous-preflight"))
        record = autonomy.read_run(self.root, "run42")
        self.assertEqual(record["head"], self.git("rev-parse", "HEAD").strip())
        snapshot = autonomy.run_dir(self.root, "run42") / "git-config.json"
        self.assertEqual(
            json.loads(snapshot.read_text()), autonomy.config_snapshot(self.root)
        )

    def test_refusals(self) -> None:
        result = subprocess.run(  # noqa: S603
            [
                sys.executable,
                "-I",
                "-S",
                str(ARTIFACTS),
                "autonomous-preflight",
                "--run",
                "run42",
            ],
            cwd=self.root,
            capture_output=True,
            text=True,
            check=False,
            env={k: v for k, v in os.environ.items() if k != "BALLAST_SPEC_WORKFLOW"},
        )
        self.assertIn("start ballast-feature with", result.stderr)
        (self.root / "dirty.txt").write_text("x")
        self.failed(self.check("autonomous-preflight"), "clean worktree")
        (self.root / "dirty.txt").unlink()
        (self.root / ".gitattributes").write_text("*.py filter=evil\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "attributes")
        self.git("config", "filter.evil.clean", "cat")
        self.failed(self.check("autonomous-preflight"), "filter=evil")


class RunChecksTests(RecorderCase):
    """FR-015: trusted checks, confined, with runner provenance."""

    def setUp(self) -> None:
        super().setUp()
        record = autonomy.read_run(self.root, "run42")
        record["frozen_tree"] = autonomy.tree_digest(self.root, (FEATURE,))
        autonomy.write_run(self.root, record)

    def set_checks(self, commands: str) -> None:
        (self.root / "ballast.toml").write_text(f"[checks]\ncommands = {commands}\n")

    def test_check_that_changes_reviewed_code_blocks(self) -> None:
        """Review F3: a check may not change the tree that passed review."""
        self.set_checks('["echo changed by a check >> README.md"]')
        self.failed(self.check("run-checks"), "changed the working tree")
        self.assertEqual(self.block()["category"], "postcondition")
        self.assertNotIn("checked_tree", autonomy.read_run(self.root, "run42"))

    def test_code_changed_after_review_blocks_before_checks(self) -> None:
        marker = self.base / "check-ran"
        self.set_checks(f'["touch {marker}"]')
        (self.root / "README.md").write_text("changed after review\n")
        self.failed(self.check("run-checks"), "after implementation review")
        self.assertFalse(marker.exists())
        record = autonomy.read_run(self.root, "run42")
        del record["frozen_tree"]
        autonomy.write_run(self.root, record)
        self.failed(self.check("run-checks"), "after implementation review")
        self.assertFalse(marker.exists())

    def test_passing_checks_record_results_and_tree(self) -> None:
        self.set_checks('["true", "echo checked"]')
        self.ok(self.check("run-checks"))
        results = autonomy.read_checks(self.root, "run42")
        self.assertEqual([r["exit"] for r in results], [0, 0])
        self.assertEqual({r["provenance"] for r in results}, {"runner"})
        record = autonomy.read_run(self.root, "run42")
        self.assertEqual(
            record["checked_tree"], autonomy.checked_digest(self.root, FEATURE)
        )
        self.assertIn(
            "- runner: `true` exited 0",
            (self.feature / "autonomous/record.md").read_text(),
        )

    def test_failing_check_blocks(self) -> None:
        self.set_checks('["true", "exit 3"]')
        self.failed(self.check("run-checks"), "check commands failed")
        self.assertEqual(self.block()["category"], "postcondition")
        self.assertNotIn("checked_tree", autonomy.read_run(self.root, "run42"))

    def test_missing_table_blocks(self) -> None:
        (self.root / "ballast.toml").write_text("")
        self.failed(self.check("run-checks"), "[checks]")

    def test_protected_change_is_tamper(self) -> None:
        self.set_checks('["echo x >> ballast.toml"]')
        self.failed(self.check("run-checks"), "tamper block")
        self.assertEqual(self.block()["category"], "tamper")
        self.assertTrue((self.root / "BALLAST_TAMPERED").exists())


class FinalAcceptanceTests(RecorderCase):
    """SC-002, FR-009: one current decision per point before final acceptance."""

    def all_points(self) -> None:
        self.step({"scope.json": self.draft("scope")})
        self.ok(self.record("scope"))
        self.intent()
        for point, kind in (("plan-review", "plan"),):
            self.step(
                {f"{point}.json": self.review_draft(point, kind)}, role="reviewer"
            )
            self.ok(self.record(point))
        for point in ("plan", "tasks"):
            self.step({f"{point}.json": self.draft(point)})
            self.ok(self.record(point))
        state = self.root / ".specify/workflow-state/run42"
        state.mkdir(parents=True)
        tree = subprocess.run(
            ["git", "write-tree"],  # noqa: S607
            cwd=self.root,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        (state / "implementation-baseline.json").write_text(
            json.dumps({"feature": FEATURE, "tree": tree})
        )
        drafts = {
            "implementation-review.json": self.review_draft(
                "implementation-review", "engineering"
            ),
            "specialist-review-test.json": self.review_draft(
                "specialist-review", "test"
            ),
            "specialist-review-security.json": self.review_draft(
                "specialist-review", "security"
            ),
        }
        self.step(drafts, role="reviewer")
        self.ok(self.record("implementation-review"))
        self.step()
        self.ok(self.record("decision-resolution"))
        self.ok(self.check("record-provisional-intent", "--renew"))
        self.step(
            {
                "spec-reconciliation.json": self.review_draft(
                    "spec-reconciliation", "spec-reconciliation"
                )
            },
            role="reviewer",
        )
        self.ok(self.record("spec-reconciliation"))
        (self.root / "ballast.toml").write_text('[checks]\ncommands = ["true"]\n')
        self.ok(self.check("run-checks"))

    def test_review_reports_follow_the_review_command_table(self) -> None:
        """Every kind's report path matches speckit.ballast.review.md."""
        table = (
            TOOLS.parents[1]
            / "templates/spec-kit/extensions/ballast/commands/speckit.ballast.review.md"
        ).read_text()
        self.assertIn(
            "`<f>/reviews/convergence.md` (kind `spec-reconciliation`)", table
        )
        sys.path.insert(0, str(TOOLS))
        try:
            import artifacts  # noqa: PLC0415
        finally:
            sys.path.pop(0)
        for kind in autonomy.REVIEW_KINDS:
            name = "convergence" if kind == "spec-reconciliation" else kind
            self.assertEqual(
                artifacts.review_report("specs/1-x", kind),
                f"specs/1-x/reviews/{name}.md",
            )

    def test_spec_reconciliation_report_is_convergence(self) -> None:
        """Pilot: the recorder refused the report the review command names."""
        self.all_points()  # Records spec-reconciliation with reviews/convergence.md.
        self.assertFalse((self.feature / "reviews/spec-reconciliation.md").exists())
        current = autonomy.current_decisions(self.decisions())
        (entry,) = [e for e in current if e["point"] == "spec-reconciliation"]
        self.assertEqual(entry["review"]["report"], f"{FEATURE}/reviews/convergence.md")

    def test_final_acceptance(self) -> None:
        self.all_points()
        self.step({"final-acceptance.json": self.draft("final-acceptance")})
        self.ok(self.record("final-acceptance"))
        points = [e["point"] for e in autonomy.current_decisions(self.decisions())]
        for point in autonomy.SINGLE_POINTS:
            self.assertEqual(points.count(point), 1, point)
        self.assertEqual(points.count("final-acceptance"), 1)

    def test_missing_point_is_refused(self) -> None:
        self.intent()
        self.step({"final-acceptance.json": self.draft("final-acceptance")})
        self.failed(
            self.record("final-acceptance"), "exactly one current scope decision"
        )

    def test_edit_after_run_checks_blocks(self) -> None:
        self.all_points()
        (self.root / "late.py").write_text("x\n")
        self.step({"final-acceptance.json": self.draft("final-acceptance")})
        self.failed(self.record("final-acceptance"), "changed after run-checks")

    def test_stale_intent_is_rejected(self) -> None:
        self.all_points()
        (self.feature / "spec.md").write_text(SPEC + "\nlate\n")
        self.step({"final-acceptance.json": self.draft("final-acceptance")})
        self.failed(self.record("final-acceptance"), "stale")

    def test_changed_artifacts_are_noted(self) -> None:
        self.all_points()
        self.step({"final-acceptance.json": self.draft("final-acceptance")})
        self.ok(self.record("final-acceptance"))
        final = self.decisions()[-1]
        self.assertEqual(final.get("notes", []), [])


class RiskRecheckTests(RecorderCase):
    """AC-022, FR-005, FR-006: risk only rises; privileged actions re-check."""

    def test_raise_is_recorded(self) -> None:
        self.step(
            {"plan.json": self.draft("plan", risk="R2", boundaries=["Trust Model"])}
        )
        self.ok(self.record("plan"))
        risk = autonomy.read_run(self.root, "run42")["risk"]
        self.assertEqual((risk["level"], risk["source"]), ("R2", "raised"))
        self.assertEqual(risk["history"][-1]["decision_id"], "PD-0001")
        self.assertEqual(risk["boundaries"], ["trust model"])
        self.assertIn(
            "## R2 notice", (self.feature / "autonomous/record.md").read_text()
        )

    def test_raise_to_excluded_level_blocks(self) -> None:
        record = autonomy.read_run(self.root, "run42")
        record["eligibility"]["policy"]["risk"] = ["R0", "R1"]
        autonomy.write_run(self.root, record)
        self.step({"plan.json": self.draft("plan", risk="R2")})
        self.failed(self.record("plan"), "ineligible block")
        self.assertEqual(self.block()["category"], "ineligible")
        self.assertEqual(self.decisions(), [])
        self.assertEqual(autonomy.read_run(self.root, "run42")["risk"]["level"], "R2")

    def test_lower_level_is_ignored_and_noted(self) -> None:
        self.step({"plan.json": self.draft("plan", risk="R0")})
        self.ok(self.record("plan"))
        self.assertEqual(autonomy.read_run(self.root, "run42")["risk"]["level"], "R1")
        self.assertIn(
            "ignored lower declared risk R0; risk stays R1",
            self.decisions()[0]["notes"],
        )

    def test_unauthorized_privileged_action_blocks(self) -> None:
        self.step(
            {
                "plan.json": self.draft(
                    "plan", privileged_actions=["secret provisioning"]
                )
            }
        )
        self.failed(
            self.record("plan"), "privileged action secret provisioning before merge"
        )
        self.assertEqual(self.block()["category"], "ineligible")

    def test_review_declared_action_blocks(self) -> None:
        draft = self.review_draft("plan-review", "plan", privileged_actions=["deploy"])
        self.step({"plan-review.json": draft}, role="reviewer")
        self.failed(self.record("plan-review"), "privileged action deploy")


class ContinuePreflightTests(RecorderCase):
    """A human-gated continuation needs its lowered source run and baseline."""

    def setUp(self) -> None:
        super().setUp()
        source = autonomy.read_run(self.root, "run42")
        autonomy.set_status(source, "stopped")
        autonomy.change_mode(source, "human-gated", reason="x", decision_id="HD-0001")
        autonomy.set_status(source, "continued")
        autonomy.write_run(self.root, source)
        record = autonomy.new_run(
            run_id="cont01",
            feature=FEATURE,
            issue=27,
            workflow="ballast-continue",
            mode="human-gated",
            integration="claude",
            continues="run42",
        )
        autonomy.write_run(self.root, record)
        runs = self.root / ".specify/workflows/runs/cont01"
        runs.mkdir(parents=True)
        (runs / "inputs.json").write_text(
            json.dumps({"inputs": {"feature_directory": FEATURE}})
        )
        (runs / "state.json").write_text(
            json.dumps({"workflow_id": "ballast-continue"})
        )

    def preflight(self) -> subprocess.CompletedProcess[str]:
        return subprocess.run(  # noqa: S603
            [
                sys.executable,
                "-I",
                "-S",
                str(ARTIFACTS),
                "continue-preflight",
                "--run",
                "cont01",
            ],
            cwd=self.root,
            capture_output=True,
            text=True,
            check=False,
            env={**os.environ, "BALLAST_SPEC_WORKFLOW": "1"},
        )

    def test_needs_baseline(self) -> None:
        result = self.preflight()
        self.assertIn("implementation baseline was not copied", result.stderr)
        state = self.root / ".specify/workflow-state/cont01"
        state.mkdir(parents=True)
        (state / "implementation-baseline.json").write_text("{}")
        self.assertEqual(self.preflight().returncode, 0, self.preflight().stderr)

    def gated(self, check: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(  # noqa: S603
            [sys.executable, "-I", "-S", str(ARTIFACTS), check, "--run", "cont01"],
            cwd=self.root,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_human_approval_supersedes_the_provisional_intent(self) -> None:
        """AC-009, AC-017: a continuation's human intent approval wins.

        The provisional block leaves intent.md; the PD stays logged.
        """
        record = autonomy.read_run(self.root, "run42")
        record["status"] = "active"
        record["mode_history"] = record["mode_history"][:1]
        autonomy.write_run(self.root, record)
        self.intent()
        record["status"] = "continued"
        autonomy.write_run(self.root, record)
        self.assertNotEqual(self.gated("intent").returncode, 0)
        result = self.gated("record-intent")
        self.assertEqual(result.returncode, 0, result.stderr)
        intent = (self.feature / "intent.md").read_text()
        self.assertNotIn("workflow-provisional", intent)
        self.assertIn("- **Approved by**: human user", intent)
        self.assertEqual(self.gated("intent").returncode, 0)
        self.assertEqual([e["point"] for e in self.decisions()], ["intent"])


if __name__ == "__main__":
    unittest.main()
