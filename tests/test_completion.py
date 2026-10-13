"""Units of tools/spec_workflow/completion.py, the #141 PR completion step.

`evaluate` is pure, so each of the twelve conditions is tested alone on
built inputs. `complete` runs against the fake `gh` of test_autonomy, a
temporary Git repository and private operator state; no test calls GitHub.
"""

from __future__ import annotations

import io
import json
import os
import shutil
import sys
import unittest
from contextlib import redirect_stdout
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_autonomy import (
    FEATURE,
    GOLDEN_CHECKS,
    TOOLS,
    AutonomyCase,
    autonomy,
    fixed_decision,
    fixed_run,
    review,
    served_pr,
)

sys.path.pop(0)
sys.path.insert(0, str(TOOLS))
try:
    import completion
    import ledger
    import packet
finally:
    sys.path.pop(0)

COMMIT = "c" * 40
URL = "https://github.com/acme/demo/pull/7"
HEAD = {
    "ref": "27-demo-run",
    "repo": {"full_name": "acme/demo", "owner": {"login": "acme"}},
}
APPROVAL = "; merging stays the only human approval"


def counts(**changes: int) -> dict[str, int]:
    """Packet criterion counts: two verified, nothing else, unless changed."""
    return {**dict.fromkeys(ledger.PACKET_COUNTS, 0), "verified": 2, **changes}


def eligible_run() -> dict:
    """Return a run record that meets every condition read from the run."""
    record = fixed_run()
    record["eligibility"]["policy"].update(
        completion_configured="ready", completion="ready"
    )
    record["checked_tree"] = "d" * 64
    return record


def eligible_decisions() -> list[dict]:
    """Return an approved spec reconciliation and a final acceptance."""
    return [
        fixed_decision(
            1,
            "spec-reconciliation",
            review=review("spec-reconciliation"),
            provider="codex",
            role="reviewer",
        ),
        fixed_decision(2, "final-acceptance"),
    ]


def finding(severity: str, disposition: str = "open") -> dict:
    """One finding as the recorder writes it."""
    return {
        "id": "F-001",
        "severity": severity,
        "label": "implementation-bug",
        "disposition": disposition,
        "reason": "Known",
        "evidence": [],
    }


def with_findings(*findings: dict, number: int = 3) -> dict:
    """Return an implementation review decision carrying `findings`."""
    return fixed_decision(
        number,
        "implementation-review",
        review=review("engineering", findings=list(findings)),
        provider="codex",
        role="reviewer",
    )


def make_inputs(**overrides: object) -> completion.Inputs:
    """Return inputs meeting all twelve conditions, with `overrides` replaced."""
    inputs = completion.Inputs(
        run=eligible_run(),
        decisions=eligible_decisions(),
        human=[],
        checks=list(GOLDEN_CHECKS),
        packet=packet.PacketOutcome(
            "published", pr_number=7, head=COMMIT, counts=counts()
        ),
        commit=COMMIT,
        pr=served_pr(7, "", head={**HEAD, "sha": COMMIT}),
        repo="acme/demo",
        number=7,
        base="main",
        branch="27-demo-run",
    )
    return replace(inputs, **overrides)


def lowered(mode: str) -> dict:
    """Return the eligible run lowered to `mode` before publication."""
    record = eligible_run()
    record["mode_history"].append(
        {
            **record["mode_history"][0],
            "mode": mode,
            "action": "lower",
            "decision_id": "HD-0001",
        }
    )
    return record


def run_with(**changes: object) -> dict:
    """Return the eligible run with policy or top-level fields changed."""
    record = eligible_run()
    policy = record["eligibility"]["policy"]
    for key, value in changes.items():
        if key.startswith("completion"):
            policy[key] = value
        else:
            record[key] = value
    return record


class EvaluateTests(unittest.TestCase):
    """T013 [AC-004 to AC-007, AC-009, SC-002, FR-017]: the pure evaluation."""

    def reasons(self, inputs: completion.Inputs) -> list[tuple[str, str]]:
        return [(r.code, r.text) for r in completion.evaluate(inputs)]

    def only(self, inputs: completion.Inputs, code: str, text: str) -> None:
        self.assertEqual(self.reasons(inputs), [(code, text)])

    def test_every_condition_met_is_eligible(self) -> None:
        self.assertEqual(completion.evaluate(make_inputs()), ())

    def test_mode(self) -> None:
        """(1) Autonomous at publication [AC-012]."""
        for mode in ("human-gated", "chat"):
            with self.subTest(mode=mode):
                self.only(
                    make_inputs(run=lowered(mode)),
                    "mode",
                    f"the run is in {mode} mode, not autonomous",
                )
        self.only(
            make_inputs(run=run_with(workflow="ballast-continue")),
            "mode",
            "the run is not an Autonomous run",
        )

    def test_policy_draft(self) -> None:
        """(2) The effective policy is `ready` [AC-016]."""
        self.only(
            make_inputs(run=run_with(completion="draft", completion_flag="draft")),
            "policy-draft",
            "the run's start flag chose draft",
        )
        self.only(
            make_inputs(run=run_with(completion="draft")),
            "policy-draft",
            "the completion policy is draft",
        )

    def test_risk(self) -> None:
        """(3) Risk R0 or R1, no R2 boundary declared [AC-004, SEC-001]."""
        self.only(make_inputs(run=fixed_run_ready(risk="R2")), "risk", "risk R2")
        self.assertEqual(self.reasons(make_inputs(run=fixed_run_ready(risk="R0"))), [])
        record = eligible_run()
        record["risk"]["boundaries"] = ["launcher trust model"]
        self.only(make_inputs(run=record), "risk", "R2 boundaries declared")

    def test_privileged_action(self) -> None:
        """(4) No privileged action, authorized or not; kinds, never text."""
        record = eligible_run()
        record["eligibility"]["privileged_actions"] = ["external-write: post"]
        decisions = [
            *eligible_decisions(),
            {**fixed_decision(3, "tasks"), "privileged_actions": ["deploy prod <b>"]},
        ]
        self.only(
            make_inputs(run=record, decisions=decisions),
            "privileged-action",
            "privileged actions declared: external-write, other",
        )

    def test_no_final_acceptance(self) -> None:
        """(5) Final acceptance is recorded."""
        self.only(
            make_inputs(decisions=eligible_decisions()[:1]),
            "no-final-acceptance",
            "no final acceptance recorded",
        )

    def test_not_converged(self) -> None:
        """FR-005(6): the recorded spec reconciliation is approved [AC-014]."""
        rejected = fixed_decision(
            1,
            "spec-reconciliation",
            review={**review("spec-reconciliation"), "verdict": "changes-requested"},
        )
        text = "spec reconciliation is not recorded as approved and converged"
        for decisions in (
            [rejected, fixed_decision(2, "final-acceptance")],
            [fixed_decision(2, "final-acceptance")],
        ):
            with self.subTest(decisions=[d["point"] for d in decisions]):
                self.only(make_inputs(decisions=decisions), "not-converged", text)

    def test_open_finding(self) -> None:
        """(7) No open finding above the threshold [AC-009]."""
        decisions = [*eligible_decisions(), with_findings(finding("high"))]
        self.only(
            make_inputs(decisions=decisions),
            "open-finding",
            "1 open finding above the low threshold, highest high",
        )

    def test_checks(self) -> None:
        """(8) `[checks]` passed on the published tree."""
        failed = "run-checks did not pass on the published tree"
        for name, overrides, text in (
            ("not run", {"checks": None}, "run-checks not run"),
            ("empty", {"checks": []}, failed),
            ("failure", {"checks": [{**GOLDEN_CHECKS[0], "exit": 1}]}, failed),
            (
                "timeout",
                {"checks": [{**GOLDEN_CHECKS[0], "timed_out": True}]},
                failed,
            ),
            ("unchecked tree", {"run": run_with(checked_tree=None)}, failed),
        ):
            with self.subTest(name=name):
                self.only(make_inputs(**overrides), "checks", text)

    def test_packet(self) -> None:
        """(9) The packet was published at the commit, every criterion verified."""
        published = make_inputs().packet
        for name, value, text in (
            ("none", None, "acceptance packet not published"),
            (
                "failed",
                packet.PacketOutcome("failed-retryable", "too-large"),
                "acceptance packet failed-retryable (too-large)",
            ),
            (
                "pending",
                packet.PacketOutcome("pending", "no-pr"),
                "acceptance packet pending (no-pr)",
            ),
            (
                "other head",
                replace(published, head="e" * 40),
                "acceptance packet head is not the published commit",
            ),
            (
                "not verified",
                replace(published, counts=counts(failed=1, not_run=2, missing=1)),
                "criteria not all verified: 1 failed, 2 not run, 0 stale, 1 missing",
            ),
            (
                "no criterion",
                replace(published, counts=counts(verified=0)),
                "the acceptance packet lists no criterion",
            ),
            (
                "no counts",
                replace(published, counts=None),
                "acceptance packet counts are unavailable",
            ),
        ):
            with self.subTest(name=name):
                self.only(make_inputs(packet=value), "packet", text)
        for key in ("failed", "not_run", "stale", "missing"):
            with self.subTest(count=key):
                changed = replace(published, counts=counts(**{key: 1}))
                self.assertEqual(
                    [r.code for r in completion.evaluate(make_inputs(packet=changed))],
                    ["packet"],
                )
        for state in ("updated", "unchanged"):
            with self.subTest(state=state):
                done = make_inputs(packet=replace(published, state=state))
                self.assertEqual(completion.evaluate(done), ())

    def test_material_change(self) -> None:
        """(10) No material provisional change."""
        material = fixed_decision(3, "decision-resolution", material=True)
        self.only(
            make_inputs(decisions=[*eligible_decisions(), material]),
            "material-change",
            "material provisional change PD-0003",
        )

    def test_block_resolved(self) -> None:
        """FR-005(11): no block was resolved during the run [AC-018]."""
        human = [{"id": "HD-0001", "kind": "block-resolution", "by": "operator"}]
        self.only(
            make_inputs(human=human),
            "block-resolved",
            "a block was resolved during the run (HD-0001)",
        )
        other = [{"id": "HD-0001", "kind": "merge-feedback", "by": "operator"}]
        self.assertEqual(completion.evaluate(make_inputs(human=other)), ())

    def test_pr_read_back(self) -> None:
        """(12) The PR read back is the open draft at the pushed commit [AC-007]."""
        moved = served_pr(7, "", head={**HEAD, "sha": "e" * 40})
        text = "the PR head is not the published commit"
        self.only(make_inputs(pr=moved), "head-moved", text)
        changed = "PR #7 is not an open draft from the run's branch"
        head = {**HEAD, "sha": COMMIT}
        for name, pr in (
            ("not a draft", served_pr(7, "", draft=False, head=head)),
            ("closed", served_pr(7, "", state="closed", head=head)),
            ("other number", served_pr(8, "", head=head)),
            ("other base", served_pr(7, "", base={"ref": "dev"}, head=head)),
        ):
            with self.subTest(name=name):
                self.only(make_inputs(pr=pr), "pr-changed", changed)
        for cause, shown in (
            ("github-unreachable", "github-unreachable"),
            ("gh-missing", "gh-missing"),
            ("HTTP 500 boom", "github-error"),
        ):
            with self.subTest(cause=cause):
                (reason,) = completion.evaluate(make_inputs(pr=cause))
                self.assertEqual(
                    (reason.code, reason.text, reason.cause),
                    (
                        "pr-unreadable",
                        f"the PR could not be read back ({shown})",
                        shown,
                    ),
                )

    def test_several_failures_in_condition_order(self) -> None:
        """AC-006: every failed condition, in FR-005 order."""
        published = make_inputs().packet
        inputs = make_inputs(
            run=fixed_run_ready(risk="R2"),
            packet=replace(published, counts=counts(not_run=1)),
            decisions=[
                fixed_decision(3, "decision-resolution", material=True),
                *eligible_decisions(),
            ],
        )
        self.assertEqual(
            [r.code for r in completion.evaluate(inputs)],
            ["risk", "packet", "material-change"],
        )

    def test_severity_thresholds(self) -> None:
        """AC-009, research R13: the default never allows more than `low`."""
        for name, threshold, found, expected in (
            ("default allows low", None, finding("low"), None),
            ("default allows info", None, finding("info"), None),
            ("none refuses info", "none", finding("info"), "info"),
            ("info refuses low", "info", finding("low"), "low"),
            ("info allows info", "info", finding("info"), None),
            (
                "accepted medium",
                None,
                finding("medium", "accepted-provisionally"),
                "medium",
            ),
            ("resolved high", None, finding("high", "resolved"), None),
        ):
            with self.subTest(name=name):
                changes = {"completion_max_severity": threshold} if threshold else {}
                inputs = make_inputs(
                    run=run_with(**changes),
                    decisions=[*eligible_decisions(), with_findings(found)],
                )
                if expected is None:
                    self.assertEqual(completion.evaluate(inputs), ())
                else:
                    shown = threshold or "low"
                    self.only(
                        inputs,
                        "open-finding",
                        f"1 open finding above the {shown} threshold, highest "
                        f"{expected}",
                    )

    def test_superseded_and_unknown_findings(self) -> None:
        """A superseded finding is ignored; an unknown severity is the highest."""
        old = with_findings(finding("high"), number=3)
        new = {
            **with_findings(finding("high", "resolved"), number=4),
            "supersedes": "PD-0003",
        }
        self.assertEqual(
            completion.evaluate(
                make_inputs(decisions=[*eligible_decisions(), old, new])
            ),
            (),
        )
        self.only(
            make_inputs(
                decisions=[
                    *eligible_decisions(),
                    with_findings(finding("low"), finding("urgent"), finding("high")),
                ]
            ),
            "open-finding",
            "2 open findings above the low threshold, highest unknown",
        )

    def test_no_wording_claims_an_approval(self) -> None:
        """FR-017: no reason or line presents marking ready as an approval."""
        published = make_inputs().packet
        failing = make_inputs(
            run=fixed_run_ready(risk="R2", mode="human-gated", flag="draft"),
            decisions=[
                fixed_decision(1, "tasks", material=True),
                with_findings(finding("high")),
                {**fixed_decision(4, "plan"), "privileged_actions": ["merge"]},
            ],
            human=[{"id": "HD-0001", "kind": "block-resolution"}],
            checks=None,
            packet=replace(published, counts=counts(failed=1)),
            pr="github-error",
        )
        reasons = completion.evaluate(failing)
        self.assertEqual(
            [r.code for r in reasons],
            [
                "mode",
                "policy-draft",
                "risk",
                "privileged-action",
                "no-final-acceptance",
                "not-converged",
                "open-finding",
                "checks",
                "packet",
                "material-change",
                "block-resolved",
                "pr-unreadable",
            ],
        )
        reasons = (
            *reasons,
            completion.Reason("forge-failed", "marking ready failed (gh-forbidden)"),
            completion.Reason("forge-unverified", completion.UNVERIFIED),
            completion.Reason("internal-error", "completion check failed (OSError)"),
        )
        lines = [
            completion.format_line("ready-for-review", 7, URL, ()),
            completion.format_line("draft", 7, URL, reasons),
            completion.format_line("unverified", 7, URL, reasons[-2:-1]),
        ]
        for text in [r.text for r in reasons] + lines:
            self.assertIsNone(autonomy.HUMAN_APPROVAL.search(text), text)

    def test_line_forms(self) -> None:
        """contracts/output-and-ledger.md: the three line forms."""
        unverified = completion.Reason("forge-unverified", completion.UNVERIFIED)
        self.assertEqual(
            completion.format_line("ready-for-review", 7, URL, ()),
            f"PR completion: ready-for-review #7 {URL}{APPROVAL}",
        )
        self.assertEqual(
            completion.format_line(
                "draft",
                7,
                URL,
                (completion.Reason("risk", "risk R2"), completion.Reason("x", "y")),
            ),
            f"PR completion: draft #7 {URL}: risk R2; y",
        )
        self.assertEqual(
            completion.format_line("unverified", 7, URL, (unverified,)),
            f"PR completion: unverified #7 {URL}: {completion.UNVERIFIED}",
        )
        self.assertEqual(
            completion.format_line(
                "draft",
                None,
                None,
                (completion.Reason("internal-error", "completion check failed (E)"),),
            ),
            "PR completion: draft: completion check failed (E)",
        )


def fixed_run_ready(
    *, risk: str = "R1", mode: str | None = None, flag: str | None = None
) -> dict:
    """Return the eligible run at another risk, mode or start flag."""
    record = eligible_run() if mode is None else lowered(mode)
    record["risk"] = fixed_run(risk=risk)["risk"]
    if flag is not None:
        record["eligibility"]["policy"].update(completion=flag, completion_flag=flag)
    return record


class CompleteTests(AutonomyCase):
    """T014 [AC-005, AC-008, F-001]: the I/O step against the fake `gh`."""

    PUBLICATION = {  # noqa: RUF012 - read-only fixture
        "repo": "acme/demo",
        "number": 7,
        "url": URL,
        "commit": COMMIT,
        "base": "main",
        "branch": "27-demo-run",
    }

    def setUp(self) -> None:
        super().setUp()
        record = self.make_run(checked_tree="d" * 64)
        record["eligibility"]["policy"].update(
            completion_configured="ready", completion="ready"
        )
        autonomy.write_run(self.root, record)
        autonomy.write_json(
            autonomy.run_dir(self.root, "run42") / "checks.json", GOLDEN_CHECKS
        )
        for entry in eligible_decisions():
            autonomy.append_decision(self.root, "run42", entry)
        self.serve(draft=True)
        self.packet = packet.PacketOutcome(
            "published", pr_number=7, head=COMMIT, counts=counts()
        )

    def serve(
        self, *, sha: str = COMMIT, then: str | None = None, **changes: object
    ) -> None:
        """Serve PR #7; `then` is the head GitHub shows after the first read."""
        pr = served_pr(7, "", head={**HEAD, "sha": sha}, **changes)
        self.gh_data("repos_acme_demo_pulls_7.json", pr)
        if then is not None:
            self.gh_data(
                "repos_acme_demo_pulls_7.then.json",
                served_pr(7, "", head={**HEAD, "sha": then}, **changes),
            )

    def complete(self) -> tuple[str | None, str]:
        out = io.StringIO()
        publication, outcome = self.PUBLICATION, self.packet
        with redirect_stdout(out):
            line = completion.complete(self.root, "run42", publication, outcome)
        return line, out.getvalue()

    def events(self) -> list[dict]:
        events, problems = ledger.read(self.root, "run42")
        self.assertEqual(problems, [])
        return [e["data"] for e in events if e["kind"] == "pr_completion"]

    def ready_calls(self) -> list[list[str]]:
        return [c for c in self.gh_calls() if c[:2] == ["pr", "ready"]]

    def test_eligible_run_is_marked_ready_once_and_verified(self) -> None:
        line, out = self.complete()
        self.assertEqual(line, f"PR completion: ready-for-review #7 {URL}{APPROVAL}")
        self.assertEqual(out, line + "\n")
        self.assertEqual(
            self.gh_calls(),
            [
                ["api", "repos/acme/demo/pulls/7"],
                ["pr", "ready", "7", "--repo", "acme/demo"],
                ["api", "repos/acme/demo/pulls/7"],
            ],
        )
        self.assertEqual(
            self.events(), [{"outcome": "ready", "pr_number": 7, "commit": COMMIT}]
        )

    def test_ineligible_run_reads_once_and_never_marks_ready(self) -> None:
        """AC-005: only the condition (12) read; the reason in line and ledger."""
        path = autonomy.run_dir(self.root, "run42") / "decisions.jsonl"
        path.unlink()
        autonomy.append_decision(self.root, "run42", eligible_decisions()[0])
        line, _ = self.complete()
        self.assertEqual(
            line, f"PR completion: draft #7 {URL}: no final acceptance recorded"
        )
        self.assertEqual(self.gh_calls(), [["api", "repos/acme/demo/pulls/7"]])
        self.assertEqual(
            self.events(),
            [
                {
                    "outcome": "draft",
                    "pr_number": 7,
                    "commit": COMMIT,
                    "reasons": ["no-final-acceptance"],
                }
            ],
        )

    def test_forge_failure_keeps_the_draft_with_its_cause(self) -> None:
        """AC-008: one fixed cause code, never gh's text."""
        for stderr, cause in (
            ("HTTP 403: Resource not accessible by integration\n", "gh-forbidden"),
            ("HTTP 401: Bad credentials secret-token\n", "gh-unauthenticated"),
            ("error connecting to api.github.com\n", "github-unreachable"),
            ("HTTP 500: Internal Server Error\n", "github-error"),
        ):
            with self.subTest(cause=cause):
                (self.gh_dir / "FAIL_pr_ready").write_text(stderr)
                self.addCleanup((self.gh_dir / "FAIL_pr_ready").unlink, missing_ok=True)
                line, _ = self.complete()
                reason = f"marking ready failed ({cause})"
                self.assertEqual(line, f"PR completion: draft #7 {URL}: {reason}")
                for word in stderr.split():
                    if word not in {"HTTP", "error"}:
                        self.assertNotIn(word, line)
                self.assertEqual(
                    self.events()[-1],
                    {
                        "outcome": "draft",
                        "pr_number": 7,
                        "commit": COMMIT,
                        "reasons": ["forge-failed"],
                        "cause": cause,
                    },
                )
                (self.gh_dir / "FAIL_pr_ready").unlink()
                served = json.loads(
                    (self.gh_dir / "repos_acme_demo_pulls_7.json").read_text()
                )
                self.assertTrue(served["draft"])

    def test_missing_trusted_gh_is_an_unreadable_pr(self) -> None:
        with patch.object(completion.draft_pr, "_resolve", return_value=(None, False)):
            line, _ = self.complete()
        reason = "the PR could not be read back (gh-missing)"
        self.assertEqual(line, f"PR completion: draft #7 {URL}: {reason}")
        self.assertEqual(self.gh_calls(), [])
        self.assertEqual(
            self.events()[-1],
            {
                "outcome": "draft",
                "pr_number": 7,
                "commit": COMMIT,
                "reasons": ["pr-unreadable"],
                "cause": "gh-missing",
            },
        )

    def test_untrusted_gh_never_runs(self) -> None:
        """SEC-004: a gh first on PATH in the checkout or a temp root never runs."""
        marker = self.base / "planted-ran"
        planted = self.root / ".git/planted-bin"  # In the checkout, not in status.
        planted.mkdir()
        (planted / "gh").write_text(f"#!/bin/sh\ntouch {marker}\nexit 0\n")
        (planted / "gh").chmod(0o755)
        system = self.base / "system-bin"  # git only, never a real gh
        system.mkdir()
        (system / "git").symlink_to(shutil.which("git", path=self.real_path) or "")
        for name, first, roots in (
            ("checkout", planted, ()),
            ("agent temp root", self.bin, (self.bin,)),
        ):
            path = f"{first}{os.pathsep}{system}"
            with (
                self.subTest(name=name),
                patch.dict(os.environ, {"PATH": path}),
                patch.object(ledger, "agent_temp_roots", lambda roots=roots: roots),
            ):
                line, _ = self.complete()
                reason = "the PR could not be read back (gh-untrusted)"
                self.assertEqual(line, f"PR completion: draft #7 {URL}: {reason}")
                self.assertEqual(self.gh_calls(), [])
                self.assertFalse(marker.exists())
                self.assertEqual(
                    (self.events()[-1]["reasons"], self.events()[-1]["cause"]),
                    (["pr-unreadable"], "gh-untrusted"),
                )

    def test_unverified_ready_never_claims_a_draft(self) -> None:
        """F-001: the forge accepted, but the read-back does not show it ready."""
        expected = f"PR completion: unverified #7 {URL}: {completion.UNVERIFIED}"
        for name in ("still a draft", "head moved"):
            with self.subTest(name=name):
                if name == "still a draft":
                    (self.gh_dir / "ready-keeps-draft").write_text("")
                    self.serve(draft=True)
                else:
                    (self.gh_dir / "ready-keeps-draft").unlink()
                    self.serve(draft=True, then="e" * 40)
                line, _ = self.complete()
                self.assertEqual(line, expected)
                self.assertNotIn("draft", line)
                self.assertEqual(
                    self.events()[-1],
                    {
                        "outcome": "unverified",
                        "pr_number": 7,
                        "commit": COMMIT,
                        "reasons": ["forge-unverified"],
                    },
                )

    def unverified(self) -> None:
        line, _ = self.complete()
        self.assertEqual(
            line, f"PR completion: unverified #7 {URL}: {completion.UNVERIFIED}"
        )
        self.assertEqual(
            self.events()[-1],
            {
                "outcome": "unverified",
                "pr_number": 7,
                "commit": COMMIT,
                "reasons": ["forge-unverified"],
            },
        )

    def test_a_failed_request_the_forge_applied_is_unverified(self) -> None:
        """AC-019, AC-008, F-02: ready at another head after a failed request."""
        (self.gh_dir / "ready-then-fail").write_text("")
        self.serve(draft=True, then="e" * 40)
        self.unverified()
        self.assertEqual(len(self.ready_calls()), 1)

    def test_a_failed_read_after_the_request_is_unverified(self) -> None:
        """AC-019, F-02, SEC-003: once requested, any doubt is `unverified`."""
        (self.gh_dir / "FAIL_pr_ready").write_text("HTTP 502: Bad Gateway\n")
        served = completion._Gh(self.root).read("acme/demo", 7)  # noqa: SLF001
        for second in (KeyboardInterrupt(), RuntimeError("boom"), "github-error"):
            with (
                self.subTest(second=repr(second)),
                patch.object(
                    completion._Gh,  # noqa: SLF001
                    "read",
                    side_effect=[served, second],
                ) as read,
            ):
                self.unverified()
                self.assertEqual(read.call_count, 2)

    def test_an_internal_error_keeps_the_draft_and_never_raises(self) -> None:
        with patch.object(
            completion.autonomy, "read_checks", side_effect=RuntimeError("boom")
        ):
            line, _ = self.complete()
        reason = "completion check failed (RuntimeError)"
        self.assertEqual(line, f"PR completion: draft #7 {URL}: {reason}")
        self.assertNotIn("boom", line)
        self.assertEqual(self.ready_calls(), [])
        self.assertEqual(self.events()[-1]["reasons"], ["internal-error"])
        with patch.object(
            completion.autonomy, "read_checks", side_effect=KeyboardInterrupt
        ):
            line, _ = self.complete()
        self.assertEqual(
            line,
            f"PR completion: draft #7 {URL}: completion check failed "
            "(KeyboardInterrupt)",
        )

    def test_unreported_run_prints_and_records_nothing(self) -> None:
        """FR-013, research R4: without `completion = "ready"`, nothing."""
        for policy in (
            {},
            {"completion_configured": "draft", "completion": "draft"},
            {"completion_flag": "ready", "completion": "draft"},
        ):
            with self.subTest(policy=policy):
                record = self.make_run(checked_tree="d" * 64)
                record["eligibility"]["policy"].update(policy)
                autonomy.write_run(self.root, record)
                line, out = self.complete()
                self.assertIsNone(line)
                self.assertEqual(out, "")
                self.assertEqual(self.gh_calls(), [])
        self.assertEqual(self.events(), [])

    def test_checkout_ballast_toml_is_never_the_policy(self) -> None:
        """AC-013: only the trusted snapshot counts, never the checkout copy."""
        path = self.root / "ballast.toml"
        path.write_text(path.read_text() + '[autonomous]\ncompletion = "ready"\n')
        record = self.make_run(checked_tree="d" * 64)
        record["eligibility"]["policy"].update(
            completion_configured="draft", completion="draft"
        )
        autonomy.write_run(self.root, record)
        line, out = self.complete()
        self.assertIsNone(line)
        self.assertEqual(out, "")
        self.assertEqual(self.gh_calls(), [])
        self.assertEqual(self.events(), [])

    def test_feature_of_the_event_is_the_runs(self) -> None:
        self.complete()
        events, _ = ledger.read(self.root, "run42")
        self.assertEqual({e["feature"] for e in events}, {FEATURE})
        self.assertEqual({e["source"] for e in events}, {"runner"})


if __name__ == "__main__":
    unittest.main()
