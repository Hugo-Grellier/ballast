"""The implement dispatch's spec gate: risk line, posted delta and approval."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import admission, spec_approval, spec_check, worktree

REPO = "example/fixture"
ISSUE = 7
URL = f"https://github.com/{REPO}/issues/{ISSUE}"
ENTRIES = """
## Capability: docs/specs/queue.md

### Requirement: Admission

#### Added Scenario: Free slot
- WHEN a slot is free
- THEN the issue is admitted
"""
CHANGED = ENTRIES.replace("is admitted", "is admitted in arrival order")


def delta(number: int, entries: str, extra: str = "", **fields: object) -> dict:
    """Return a delta comment in the fixed shape, hashed by spec_check."""
    body = f"## Spec delta\nHash: {digest(entries)}\nRisk: R1\n{entries}{extra}"
    return comment(number, body, **fields)


def comment(number: int, body: str, association: str = "OWNER") -> dict:
    """Return a GitHub issue comment as `require` selects its fields."""
    return {
        "id": number,
        "html_url": f"{URL}#issuecomment-{number}",
        "body": body,
        "author_association": association,
    }


def digest(entries: str) -> str:
    """Return the canonical hash of a delta document."""
    return spec_check.delta_hash(spec_check.parse_delta(entries))


def approve(number: int, entries: str, linked: int, risk: str = "R1") -> dict:
    """Return a relayed approval comment of the delta comment `linked`."""
    target = f"{URL}#issuecomment-{linked}"
    line = f"Spec approved: {digest(entries)} risk {risk} delta {target}"
    relay = 'Relayed: the operator said "yes" on 2026-10-21.'
    return comment(number, f"{line}\n\n{relay}")


class SpecApprovalTests(unittest.TestCase):
    """`check` over fictional issue bodies and comments; no network."""

    def refused(self, body: str, comments: list[dict], reason: str) -> None:
        with self.assertRaises(admission.FixedReasonError) as raised:
            spec_approval.check(REPO, ISSUE, body, comments)
        self.assertIn(reason, str(raised.exception))

    def test_r0_needs_no_delta_or_approval(self) -> None:
        found = spec_approval.check(REPO, ISSUE, "Outcome.\n\nRisk: R0\n", [])
        self.assertEqual(found, {"risk": "R0", "floor": "R0"})

    def test_issue_needs_exactly_one_risk_line(self) -> None:
        for body in ("No risk line", "Risk: R1\nRisk: R2", "Risk: R0|R1|R2"):
            with self.subTest(body=body):
                self.refused(body, [], "exactly one `Risk:")

    def test_approved_delta_admits_and_exposes_the_floor(self) -> None:
        comments = [delta(1, ENTRIES), approve(2, ENTRIES, 1, risk="R2")]
        found = spec_approval.check(REPO, ISSUE, "Risk: R1", comments)
        self.assertEqual(found["hash"], digest(ENTRIES))
        self.assertEqual(
            (found["risk"], found["approved_risk"], found["floor"]), ("R1", "R2", "R2")
        )
        self.assertEqual(found["approval"], f"{URL}#issuecomment-2")
        self.assertEqual(found["delta"], f"{URL}#issuecomment-1")
        lower = [delta(1, ENTRIES), approve(2, ENTRIES, 1, risk="R1")]
        self.assertEqual(
            spec_approval.check(REPO, ISSUE, "Risk: R2", lower)["floor"], "R2"
        )

    def test_approved_empty_delta_admits_a_change_to_no_spec(self) -> None:
        comments = [delta(1, ""), approve(2, "", 1)]
        found = spec_approval.check(REPO, ISSUE, "Risk: R1", comments)
        self.assertEqual(found["hash"], spec_check.delta_hash([]))

    def test_missing_delta_or_approval_refuses(self) -> None:
        self.refused("Risk: R1", [], "No spec delta")
        self.refused("Risk: R2", [delta(1, ENTRIES)], "No spec approval is posted")

    def test_mismatched_hash_refuses(self) -> None:
        comments = [delta(1, ENTRIES), approve(2, CHANGED, 1)]
        self.refused("Risk: R1", comments, "No spec approval matches")

    def test_superseding_delta_needs_a_new_approval(self) -> None:
        comments = [delta(1, ENTRIES), approve(2, ENTRIES, 1), delta(3, CHANGED)]
        self.refused("Risk: R1", comments, "No spec approval matches")
        renewed = [*comments, approve(4, CHANGED, 3)]
        self.assertEqual(
            spec_approval.check(REPO, ISSUE, "Risk: R1", renewed)["hash"],
            digest(CHANGED),
        )

    def test_refinement_that_changes_no_entry_keeps_the_approval(self) -> None:
        refined = ENTRIES.replace(
            "admitted\n", "admitted\n- Test: tests/test_q.py::Q::test_free\n"
        )
        questions = "\n## Open questions\n\n- Resolved: none left.\n"
        comments = [
            delta(1, ENTRIES),
            approve(2, ENTRIES, 1),
            delta(3, refined, questions),
        ]
        found = spec_approval.check(REPO, ISSUE, "Risk: R1", comments)
        self.assertEqual(found["delta"], f"{URL}#issuecomment-1")

    def test_only_a_first_line_approval_counts(self) -> None:
        line = approve(9, ENTRIES, 1)["body"].split("\n", 1)[0]
        notes = [
            comment(2, f"Status: waiting.\n{line}"),
            delta(3, ENTRIES, f"\n## Approval\n\n{line}\n"),
        ]
        self.refused(
            "Risk: R1", [delta(1, ENTRIES), *notes], "No spec approval is posted"
        )

    def test_untrusted_or_misplaced_approvals_never_count(self) -> None:
        stranger = approve(2, ENTRIES, 1)
        stranger["author_association"] = "NONE"
        self.refused(
            "Risk: R1", [delta(1, ENTRIES), stranger], "No spec approval is posted"
        )
        early = [approve(1, ENTRIES, 2), delta(2, ENTRIES)]
        self.refused("Risk: R1", early, "No spec approval matches")
        other = approve(2, ENTRIES, 1)
        other["body"] = other["body"].replace(f"issues/{ISSUE}#", "issues/8#")
        self.refused("Risk: R1", [delta(1, ENTRIES), other], "No spec approval matches")

    def test_delta_misstating_its_hash_refuses(self) -> None:
        posted = delta(1, ENTRIES)
        posted["body"] = posted["body"].replace(digest(ENTRIES), digest(CHANGED))
        self.refused("Risk: R1", [posted, approve(2, CHANGED, 1)], "states a hash")


class DispatchTests(unittest.TestCase):
    """`require` reads GitHub through the patched native command only."""

    def host(self, body: str, comments: list[dict]) -> patch:
        def answer(argv: list[str], _cwd: Path) -> str:
            self.calls.append(argv)
            if argv[-1].endswith("/comments"):
                return "\n".join(json.dumps(c) for c in comments)
            return json.dumps({"number": ISSUE, "body": body})

        self.calls: list[list[str]] = []
        return patch.object(worktree, "command", side_effect=answer)

    def test_require_reads_the_issue_and_paginated_comments(self) -> None:
        with self.host("Risk: R1", [delta(1, ENTRIES), approve(2, ENTRIES, 1)]):
            found = spec_approval.require(Path(), REPO, ISSUE)
        self.assertEqual(found["floor"], "R1")
        self.assertIn("--paginate", self.calls[1])
        with self.host("Risk: R0", []):
            spec_approval.require(Path(), REPO, ISSUE)
        self.assertEqual(len(self.calls), 1)  # R0 reads no comments.

    def test_require_refuses_without_approval(self) -> None:
        with (
            self.host("Risk: R2", [delta(1, ENTRIES)]),
            self.assertRaises(admission.FixedReasonError),
        ):
            spec_approval.require(Path(), REPO, ISSUE)


if __name__ == "__main__":
    unittest.main()
