"""Acceptance packet: a real temporary Git repository, a scripted gh, no network."""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import socket
import stat
import sys
import unittest
from contextlib import redirect_stdout
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools/spec_workflow"))

import autonomy  # noqa: E402
import draft_pr  # noqa: E402
import ledger  # noqa: E402
import packet  # noqa: E402

sys.path.insert(0, str(ROOT / "tests"))
from test_draft_pr import (  # noqa: E402
    FEATURE,
    FIXED,
    FORBIDDEN_EDIT_ARGS,
    REAL_GIT,
    RUN,
    TIMED_OUT,
    UNAUTHENTICATED,
    CheckpointCase,
    git,
    http,
    pull,
)

sys.path.pop(0)

T = "tests.test_demo.DemoTests.test_{}"
SPEC = (
    "# Feature Specification\n"
    "\n"
    "**Acceptance Scenarios**:\n"
    "\n"
    "1. **AC-001**: **Given** the first thing, **When** checked, **Then** shown.\n"
    "2. **AC-002**: **Given** the second thing, **When** checked, **Then** shown.\n"
    "3. **AC-003**: **Given** the third thing, **When** checked, **Then** shown.\n"
    "4. **AC-004**: **Given** the fourth thing, **When** checked, **Then** shown.\n"
    "5. **AC-005**: **Given** the fifth thing, **When** checked, **Then** shown.\n"
    "6. **AC-006**: **Given** the sixth thing, **When** checked, **Then** shown.\n"
)
MAPPING = {
    "AC-001": [T.format("one"), T.format("two")],
    "AC-002": [T.format("three"), T.format("four")],
    "AC-004": [T.format("five")],
    "AC-005": [T.format("six")],
    "AC-006": [T.format("seven")],
}
TESTS = "import unittest\n\n\nclass DemoTests(unittest.TestCase):\n    pass\n"
PR = 7
BEGIN = packet.BEGIN
END = packet.END
SECRET_TOKENS = (
    "ghp_" + "a" * 36,
    "github_pat_" + "b" * 40,
    "Bearer " + "c" * 30,
)


def sha(data: bytes | str) -> str:
    """SHA-256 of text or bytes."""
    return hashlib.sha256(data.encode() if isinstance(data, str) else data).hexdigest()


def cells(row: str) -> list[str]:
    """Split a Markdown table row on unescaped pipes."""
    return [cell.strip() for cell in re.split(r"(?<!\\)\|", row)[1:-1]]


def section_of(body: str) -> str:
    """Return the packet section of a PR body."""
    start, end = body.index(BEGIN), body.index(END) + len(END)
    return body[start:end]


def rows(text: str) -> dict[str, list[str]]:
    """Criterion rows of a packet, by ID."""
    found = {}
    for line in text.splitlines():
        match = re.match(r"\| \[(AC-[0-9]{3})\]\(", line)
        if match:
            found[match.group(1)] = cells(line)
    return found


class PacketCase(CheckpointCase):
    """A feature with base and head commits, an open Ballast Draft PR, fake GitHub."""

    def setUp(self) -> None:
        super().setUp()
        self.root = self.repo.root
        self.base_sha = git(self.root, "rev-parse", "main").strip()
        (self.root / ".gitignore").write_text(".specify/\n.venv/\n__pycache__/\n")
        self.feature = self.root / FEATURE
        self.write_feature()
        (self.root / "src").mkdir()
        (self.root / "src/app.py").write_text("VALUE = 1\n")
        (self.root / "tests").mkdir()
        (self.root / "tests/__init__.py").write_text("")
        (self.root / "tests/test_demo.py").write_text(TESTS)
        self.head = self.commit()
        self.open_pr("Human intro.")

    def write_feature(
        self,
        spec: str = SPEC,
        criteria: dict[str, list[str]] | None = MAPPING,
        spec_digest: str | None = None,
    ) -> None:
        self.feature.mkdir(parents=True, exist_ok=True)
        (self.feature / "spec.md").write_text(spec)
        (self.feature / "intent.md").write_text(f"sha256:{sha(spec)}\n")
        (self.feature / "tasks.md").write_text("- [x] T001\n")
        manifest = self.feature / "acceptance-evidence.json"
        if criteria is None:
            manifest.unlink(missing_ok=True)
            return
        manifest.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "spec_digest": spec_digest or sha(spec),
                    "criteria": criteria,
                },
                indent=2,
            )
        )

    def commit(self, message: str = "x") -> str:
        git(self.root, "add", "-A")
        git(
            self.root,
            "-c",
            "user.name=t",
            "-c",
            "user.email=t@example.test",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "-q",
            "--allow-empty",
            "-m",
            message,
        )
        return git(self.root, "rev-parse", "HEAD").strip()

    def open_pr(self, body: str = "", *, head: str | None = None) -> None:
        self.fake.prs[:] = [
            pull(
                PR,
                body=body,
                head_sha=head or self.head,
                base_sha=self.base_sha,
            )
        ]

    @property
    def body(self) -> str:
        return self.fake.prs[0]["body"]

    def binding(self) -> dict[str, str]:
        """Return the digests evidence must carry to bind to the current head."""
        manifest = self.feature / "acceptance-evidence.json"
        return {
            "snapshot": ledger.commit_tree(self.root, self.head),
            "spec_digest": sha((self.feature / "spec.md").read_bytes()),
            "manifest_digest": sha(manifest.read_bytes())
            if manifest.exists()
            else "0" * 64,
        }

    def verify(
        self,
        ac_id: str | None,
        test: str,
        status: str = "passed",
        source: str = "operator-attested",
        **override: str,
    ) -> int:
        """Append a `verification` event; return its sequence."""
        data: dict[str, Any] = {"check_id": test, "status": status}
        if ac_id is not None:
            data.update({"ac_id": ac_id, **self.binding(), **override})
        ledger.append(
            self.root, ledger.new_event(RUN, FEATURE, "verification", source, data)
        )
        events, _ = ledger.read(self.root, RUN)
        return events[-1]["sequence"]

    def collect(self) -> packet.Sources:
        """Collect directly, as the checkpoint would for PR #7."""
        work = draft_pr._Checkpoint(self.root, RUN)  # noqa: SLF001
        run = work.run
        run.feature, run.issue = FEATURE, 17
        run.git, run.gh = str(Path(REAL_GIT).resolve()), self.fake.gh
        run.owner, run.repo, run.published, run.base = "o", "r", "feat-x", "main"
        step = packet._Step(work, PR)  # noqa: SLF001
        step.head, step.base = self.head, self.base_sha
        return step.collect(self.head, self.base_sha)

    def packet(self) -> tuple[draft_pr.Outcome, str]:
        outcome = self.check()
        body = self.body
        return outcome, section_of(body) if BEGIN in body else ""

    def packet_events(self) -> list[dict[str, Any]]:
        events, problems = ledger.read(self.root, RUN)
        self.assertEqual(problems, [])
        return [e["data"] for e in events if e["kind"] == "acceptance_packet"]

    def blob(self, path: str, head: str | None = None) -> str:
        return f"https://github.com/o/r/blob/{head or self.head}/{path}"

    def assertPacket(  # noqa: N802
        self, outcome: draft_pr.Outcome, state: str, reason: str | None = None
    ) -> None:
        self.assertIsNotNone(outcome.packet)
        self.assertEqual(
            (outcome.packet.state, outcome.packet.reason), (state, reason), outcome
        )


class InertTests(unittest.TestCase):
    """R9: agent-written text is data (AC-020, AC-022, FR-013, FR-016)."""

    def test_one_line_collapsed_and_capped(self) -> None:
        self.assertEqual(packet.inert("a\n\n b\tc"), "a b c")
        self.assertEqual(packet.inert("x" * 50, 10), "x" * 9 + "…")
        self.assertEqual(packet.inert("a\x00b"), "a b")

    def test_markers_and_html_never_appear_raw(self) -> None:
        for text in (BEGIN, END, "<!-- workflow-step -->", "<b>x</b>"):
            out = packet.inert(text)
            self.assertNotIn("<", out)
            self.assertNotIn(">", out)
        self.assertEqual(packet.inert("a & b"), "a &amp; b")

    def test_markdown_punctuation_is_escaped(self) -> None:
        self.assertEqual(
            packet.inert("\\ ` * _ [ ] ( ) # | ! ~"),
            r"\\ \` \* \_ \[ \] \( \) \# \| \! \~",
        )
        self.assertNotIn("](", packet.inert("[x](https://evil)"))

    def test_autolinks_and_mentions_are_broken(self) -> None:
        for text in ("https://evil", "see www.evil.example", "HTTP://EVIL"):
            out = packet.inert(text)
            self.assertNotIn("://", out)
            self.assertNotRegex(out.lower(), r"www\.")
        self.assertEqual(packet.inert("@org/team"), "@\u200borg/team")

    def test_tokens_and_authorization_values_are_redacted(self) -> None:
        for token in (
            "ghp_" + "a" * 36,
            "gho_" + "b" * 36,
            "ghu_" + "c" * 36,
            "ghs_" + "d" * 36,
            "ghr_" + "e" * 36,
            "github_pat_" + "f" * 50,
        ):
            self.assertEqual(packet.inert(f"x {token} y"), r"x \[redacted\] y")
        for header in (
            "Authorization: token abc123",
            "authorization: Bearer abc123",
            "Bearer abc123",
        ):
            out = packet.inert(f"x {header} y")
            self.assertNotIn("abc123", out)
            self.assertIn(r"\[redacted\]", out)

    def test_approval_claims_never_match_the_guard(self) -> None:
        for text in ("approved by the human", "Human-approved", "approved by operator"):
            self.assertIsNone(autonomy.HUMAN_APPROVAL.search(packet.inert(text)))

    def test_link_builders_reject_invalid_parts(self) -> None:
        good = "a" * 40
        self.assertEqual(
            packet._blob("o/r", good, "tests/test_x.py"),  # noqa: SLF001
            f"https://github.com/o/r/blob/{good}/tests/test_x.py",
        )
        self.assertEqual(
            packet._line("o/r", good, "specs/1-x/spec.md", 3),  # noqa: SLF001
            f"https://github.com/o/r/blob/{good}/specs/1-x/spec.md?plain=1#L3",
        )
        self.assertEqual(
            packet._compare("o/r", good, "b" * 64),  # noqa: SLF001
            f"https://github.com/o/r/compare/{good}...{'b' * 64}",
        )
        self.assertEqual(
            packet._run_link("o/r", 12),  # noqa: SLF001
            "https://github.com/o/r/runs/12",
        )
        bad = (
            lambda: packet._blob("o/r", "HEAD", "x"),  # noqa: SLF001
            lambda: packet._blob("o/r", "A" * 40, "x"),  # noqa: SLF001
            lambda: packet._blob("o/r", good, "a/../b"),  # noqa: SLF001
            lambda: packet._blob("o/r", good, "/etc/passwd"),  # noqa: SLF001
            lambda: packet._blob("o/r", good, "a b"),  # noqa: SLF001
            lambda: packet._blob("o/../r", good, "x"),  # noqa: SLF001
            lambda: packet._line("o/r", good, "x", 0),  # noqa: SLF001
            lambda: packet._run_link("o/r", "12"),  # noqa: SLF001
            lambda: packet._run_link("o/r", True),  # noqa: SLF001, FBT003
        )
        for call in bad:
            with self.assertRaises(ValueError):
                call()


class CollectTests(PacketCase):
    """Collect core (AC-019, FR-002)."""

    def test_commits_versions_and_files_come_from_the_pr_and_head(self) -> None:
        (self.feature / "decisions.md").write_text("x" * (packet.FILE_LIMIT + 1))
        self.head = self.commit()
        sources = self.collect()
        self.assertEqual((sources.head, sources.base), (self.head, self.base_sha))
        self.assertEqual(
            sources.feature_version,
            git(self.root, "rev-parse", f"{self.head}:{FEATURE}").strip(),
        )
        self.assertEqual(
            sources.files,
            {
                "spec.md",
                "intent.md",
                "tasks.md",
                "decisions.md",
                "acceptance-evidence.json",
            },
        )
        self.assertEqual(sources.spec_version, sha(SPEC))
        self.assertEqual(sources.too_large, {"decisions.md"})
        self.assertIn("decisions: not present (too large)", packet.render(sources))
        self.assertEqual(sources.generated_at, FIXED)

    def test_git_commands_only_read_with_paths_after_double_dash(self) -> None:
        self.check()
        calls = [argv[1:] for argv in self.fake.calls if argv[0] == self.fake.git]
        subcommands = {argv[0] for argv in calls}
        self.assertLessEqual(
            subcommands,
            {
                "symbolic-ref",
                "for-each-ref",
                "remote",
                "rev-parse",
                "cat-file",
                "ls-tree",
            },
        )
        for argv in calls:
            if argv[0] == "ls-tree":
                self.assertEqual(argv[-2], "--")
            if argv[0] == "cat-file":
                self.assertRegex(argv[-1], r"^[0-9a-f]{40}(\^\{commit\}|:)")

    def test_invalid_commit_ids_from_github_are_refused(self) -> None:
        for head in ("HEAD", "a" * 12, "--output=x"):
            with self.subTest(head=head):
                self.open_pr(head=head)
                outcome, _ = self.packet()
                self.assertPacket(outcome, "failed-retryable", "github-error")

    def test_head_missing_locally_is_pending(self) -> None:
        self.open_pr(head="f" * 40)
        outcome, _ = self.packet()
        self.assertPacket(outcome, "pending", "head-not-local")
        self.assertIn("fetch the feature branch", outcome.packet.remedy)

    def test_spec_absent_or_too_large_is_unreadable(self) -> None:
        (self.feature / "spec.md").unlink()
        self.head = self.commit()
        self.open_pr()
        self.assertPacket(self.check(), "failed-retryable", "source-unreadable")
        (self.feature / "spec.md").write_text("x" * (packet.FILE_LIMIT + 1))
        self.head = self.commit()
        self.open_pr()
        self.assertPacket(self.check(), "failed-retryable", "source-unreadable")

    def test_manifest_shape_only_is_validated(self) -> None:
        malformed = (
            "{not json",
            json.dumps({"schema_version": 2, "spec_digest": sha(SPEC), "criteria": {}}),
            json.dumps(
                {
                    "schema_version": 1,
                    "spec_digest": sha(SPEC),
                    "criteria": {"AC-001": "t"},
                }
            ),
            json.dumps(
                {
                    "schema_version": 1,
                    "spec_digest": sha(SPEC),
                    "criteria": {"AC-001": ["tests.not_a_test"]},
                }
            ),
        )
        manifest = self.feature / "acceptance-evidence.json"
        for text in malformed:
            with self.subTest(text=text[:40]):
                manifest.write_text(text)
                self.head = self.commit()
                self.open_pr()
                outcome = self.check()
                self.assertPacket(outcome, "failed-retryable", "manifest-malformed")
                self.assertIn("ballast ledger check", outcome.packet.remedy)
        # A stale digest, an unknown ID and a missing ID all load normally.
        self.write_feature(
            criteria={"AC-031": [T.format("one")], "AC-001": [T.format("one")]},
            spec_digest="e" * 64,
        )
        self.head = self.commit()
        self.open_pr()
        sources = self.collect()
        self.assertEqual(sources.unknown, ("AC-031",))

    def test_corrupt_ledger_is_invalid(self) -> None:
        self.verify("AC-006", T.format("seven"))
        path = ledger.ledger_path(self.root, RUN)
        path.write_text(path.read_text() + "{broken\n")
        outcome = self.check()
        self.assertPacket(outcome, "failed-retryable", "ledger-invalid")
        self.assertIn(f"ballast ledger report --run {RUN}", outcome.packet.remedy)


class CriteriaTests(PacketCase):
    """US1 criteria (AC-001 to AC-004, FR-003, DEC-0001)."""

    def setUp(self) -> None:
        super().setUp()
        self.fake.check_pages = [
            [{"id": 11, "name": "ci", "status": "completed", "conclusion": "success"}]
        ]

    def quickstart_evidence(self) -> dict[str, int]:
        seq = {
            "one": self.verify("AC-001", T.format("one")),
            "two": self.verify("AC-001", T.format("two")),
            "three": self.verify("AC-002", T.format("three"), "failed"),
            "four": self.verify("AC-002", T.format("four")),
        }
        self.verify(
            "AC-004",
            T.format("five"),
            snapshot="d" * 64,
            commit=self.base_sha,
        )
        self.verify("AC-005", T.format("six"), spec_digest="e" * 64)
        return seq

    def test_every_criterion_once_in_spec_order_with_title_and_link(self) -> None:
        self.quickstart_evidence()
        _, text = self.packet()
        found = rows(text)
        self.assertEqual(list(found), [f"AC-00{n}" for n in range(1, 7)])
        for number, (ac_id, row) in enumerate(found.items(), 5):
            self.assertEqual(
                row[0],
                f"[{ac_id}]({self.blob(f'{FEATURE}/spec.md')}?plain=1#L{number})",
            )
        self.assertEqual(found["AC-001"][1], "Given the first thing")
        self.assertEqual(text.count("| [AC-001]("), 1)

    def test_states_follow_the_quickstart_rows(self) -> None:
        seq = self.quickstart_evidence()
        _, text = self.packet()
        found = rows(text)
        self.assertEqual(
            {ac: row[2] for ac, row in found.items()},
            {
                "AC-001": "verified",
                "AC-002": "failed",
                "AC-003": "missing",
                "AC-004": "stale",
                "AC-005": "stale",
                "AC-006": "not run",
            },
        )
        link = self.blob("tests/test_demo.py")
        self.assertEqual(
            found["AC-001"][3],
            f"2/2 tests passed at head: [`{T.format('one')}`]({link}) (ledger event "
            f"{seq['one']} of run {RUN}), [`{T.format('two')}`]({link}) (ledger event "
            f"{seq['two']} of run {RUN}) · CI at head: [check runs]"
            f"(https://github.com/o/r/commit/{self.head}/checks)",
        )
        self.assertIn(f"`{T.format('three')}`]({link})", found["AC-002"][3])
        self.assertIn(": failed", found["AC-002"][3])
        self.assertIn(": passed", found["AC-002"][3])
        self.assertIn("1 of 2 tests failed at head", found["AC-002"][3])
        self.assertEqual(
            found["AC-003"][3], "no test named in acceptance-evidence.json"
        )
        self.assertIn(f"stale (commit `{self.base_sha[:12]}`)", found["AC-004"][3])
        self.assertIn(f"stale (spec `{'e' * 12}`)", found["AC-005"][3])
        self.assertIn("no check recorded at head", found["AC-006"][3])
        self.assertIn(f"`ballast ledger check {RUN} AC-NNN TEST`", text)
        self.assertIn(
            "- Criteria: 6 · verified 1 · failed 1 · not run 1 · stale 2 · missing 1",
            text,
        )

    def test_no_ci_at_head_and_test_file_not_found(self) -> None:
        self.fake.check_pages = [[]]
        self.write_feature(criteria={"AC-001": ["tests.test_gone.Gone.test_x"]})
        self.head = self.commit()
        self.open_pr()
        self.verify("AC-001", "tests.test_gone.Gone.test_x")
        _, text = self.packet()
        detail = rows(text)["AC-001"]
        self.assertEqual(detail[2], "verified")
        self.assertIn(
            "`tests.test_gone.Gone.test_x` (file not found at head)", detail[3]
        )
        self.assertIn("CI at head: no CI result at head", detail[3])

    def test_no_manifest_is_missing(self) -> None:
        self.write_feature(criteria=None)
        self.head = self.commit()
        self.open_pr()
        _, text = self.packet()
        self.assertEqual({row[2] for row in rows(text).values()}, {"missing"})
        self.assertEqual(rows(text)["AC-001"][3], "no acceptance-evidence.json")

    def test_manifest_for_another_spec_makes_every_mapped_criterion_stale(self) -> None:
        self.write_feature(spec_digest="e" * 64)
        self.head = self.commit()
        self.open_pr()
        self.verify("AC-001", T.format("one"))
        _, text = self.packet()
        found = rows(text)
        for ac_id in MAPPING:
            self.assertEqual(found[ac_id][2], "stale")
            self.assertIn(f"spec {'e' * 12}", found[ac_id][3])
        self.assertEqual(found["AC-003"][2], "missing")

    def test_dirty_checkout_evidence_is_never_verified(self) -> None:
        self.verify("AC-006", T.format("seven"), snapshot="d" * 64)
        _, text = self.packet()
        self.assertEqual(rows(text)["AC-006"][2], "stale")
        self.assertIn(f"snapshot `{'d' * 12}`", rows(text)["AC-006"][3])

    def test_unknown_criteria_and_spec_without_ids(self) -> None:
        self.write_feature(criteria={**MAPPING, "AC-031": [T.format("one")]})
        self.head = self.commit()
        self.open_pr()
        _, text = self.packet()
        self.assertIn(
            "Evidence for unknown criteria: AC-031 (in [acceptance-evidence.json]("
            f"{self.blob(f'{FEATURE}/acceptance-evidence.json')}), not in the spec)",
            text,
        )
        self.write_feature(spec="# Spec\n\nNo criteria here.\n", criteria=None)
        self.head = self.commit()
        self.open_pr(self.body)
        _, text = self.packet()
        self.assertIn(
            "No acceptance criteria found in "
            f"[spec.md]({self.blob(f'{FEATURE}/spec.md')}).",
            text,
        )
        self.assertNotIn("| ID |", text)

    def test_advanced_base_keeps_head_bound_evidence(self) -> None:
        self.verify("AC-006", T.format("seven"))
        self.base_sha = git(
            self.root,
            "-c",
            "user.name=t",
            "-c",
            "user.email=t@example.test",
            "commit-tree",
            "main^{tree}",
            "-p",
            "main",
            "-m",
            "base moved",
        ).strip()
        self.open_pr()
        _, text = self.packet()
        self.assertEqual(rows(text)["AC-006"][2], "verified")
        self.assertIn(f"- Base: `{self.base_sha[:12]}`", text)


class DecisionTests(PacketCase):
    """US1 decisions, approvals, findings and risk (AC-005, AC-006, FR-004, FR-005)."""

    def autonomous(self) -> None:
        record = autonomy.new_run(
            run_id=RUN,
            feature=FEATURE,
            issue=17,
            workflow="ballast-autonomous",
            mode="autonomous",
            integration="claude",
            risk={"level": "R1", "source": "intake", "history": []},
            eligibility={},
            limits={"deadline": "2026-10-05T00:00:00+00:00"},
        )
        autonomy.write_run(self.root, record)
        directory = autonomy.run_dir(self.root, RUN)
        for entry in (
            {"point": "clarification", "decision": "assume", "summary": "Old guess."},
            {
                "point": "clarification",
                "decision": "assume",
                "summary": "Use numbered criteria.",
                "supersedes": "PD-0001",
            },
            {
                "point": "plan-review",
                "decision": "accept-finding",
                "summary": "Plan reviewed.",
                "review": {
                    "kind": "plan",
                    "verdict": "approved",
                    "report": f"{FEATURE}/reviews/plan.md",
                    "findings": [
                        {
                            "id": "F-003",
                            "severity": "medium",
                            "label": "missing test",
                            "disposition": "open",
                            "reason": "Cover the oversize case.",
                        },
                        {
                            "id": "F-004",
                            "severity": "low",
                            "label": "missing test",
                            "disposition": "resolved",
                        },
                    ],
                },
            },
        ):
            autonomy.append_log(directory / "decisions.jsonl", "PD", entry)
        (self.feature / "autonomous").mkdir()
        (self.feature / "autonomous/record.md").write_text(
            "# Autonomous run record\n\n| ID | Point |\n| --- | --- |\n"
            "| PD-0002 | clarification |\n| PD-0003 | plan-review |\n"
        )
        (self.feature / "reviews").mkdir()
        (self.feature / "reviews/plan.md").write_text("# Plan review\n")
        self.head = self.commit()
        self.open_pr()

    def test_autonomous_records_are_labeled_provisional_with_links(self) -> None:
        self.autonomous()
        _, text = self.packet()
        record = self.blob(f"{FEATURE}/autonomous/record.md")
        self.assertIn("- Risk: R1 (run record)", text)
        self.assertIn(f"- Run: `{RUN}` (autonomous)", text)
        self.assertIn(
            "- PD-0002 (clarification, agent-provisional): Use numbered criteria. — "
            f"[record]({record}?plain=1#L5)",
            text,
        )
        self.assertIn("PD-0003 (plan-review, agent-provisional)", text)
        self.assertNotIn("PD-0001", text)
        self.assertNotIn("Old guess", text)
        self.assertIn(
            "- PD-0003 F-003 (medium, open): Cover the oversize case. — "
            f"[report]({self.blob(f'{FEATURE}/reviews/plan.md')})",
            text,
        )
        self.assertNotIn("F-004", text)
        self.assertIn("- Open findings: 1 · Provisional decisions: 2", text)
        self.assertNotIn("(human;", text)

    def test_human_gated_approvals_are_labeled_human(self) -> None:
        self.fake.comment_pages = [
            [
                {
                    "body": "<!-- ballast-intake: issue=#17; scope=feature -->\n"
                    "Risk: R1 (normal feature)\n",
                    "created_at": "2026-10-01T00:00:00Z",
                    "author_association": "MEMBER",
                }
            ]
        ]
        for event in (
            ledger.new_event(
                RUN, FEATURE, "run", "runner", {"action": "started"}, "r1"
            ),
            ledger.new_event(
                RUN,
                FEATURE,
                "step",
                "runner",
                {"action": "started", "step_id": "approve-plan", "log_line": 2},
                "s0",
            ),
            ledger.new_event(
                RUN,
                FEATURE,
                "step",
                "runner",
                {"action": "completed", "step_id": "approve-plan", "log_line": 3},
                "s1",
            ),
            ledger.new_event(
                RUN,
                FEATURE,
                "gate",
                "runner",
                {"step_id": "approve-plan", "choice": "approve", "log_line": 3},
                "g1",
            ),
            ledger.new_event(
                RUN,
                FEATURE,
                "human_action",
                "operator-attested",
                {"action": "manual_recovery", "gate_id": "approve-plan"},
                "h1",
            ),
            ledger.new_event(
                RUN,
                FEATURE,
                "review",
                "agent-reported",
                {"review_id": "rev-1", "kind": "plan", "verdict": "partial"},
                "v1",
            ),
            ledger.new_event(
                RUN,
                FEATURE,
                "finding",
                "agent-reported",
                {
                    "review_id": "rev-1",
                    "finding_id": "F-1",
                    "severity": "high",
                    "resolution": "open",
                },
                "f1",
            ),
        ):
            ledger.append(self.root, event)
        (self.feature / "decisions.md").write_text(
            "# Decisions\n\n## DEC-0001 — Proposal\n\nx\n\n## DEC-0001 — Resolution\n"
            "\ny\n\n## DEC-0002 — Proposal\n\nz\n"
        )
        self.head = self.commit()
        self.open_pr()
        _, text = self.packet()
        self.assertIn("- Risk: R1 \\(normal feature\\) (intake comment)", text)
        self.assertIn(f"- Run: `{RUN}` (human-gated)", text)
        self.assertIn(
            "- gate approve-plan: approve (human; observed by runner) — ledger event 4 "
            f"of run {RUN}",
            text,
        )
        self.assertIn(
            "- manual\\_recovery approve-plan (human; operator-attested) — ledger "
            f"event 5 of run {RUN}",
            text,
        )
        decisions = self.blob(f"{FEATURE}/decisions.md")
        self.assertIn(
            "- DEC-0001 (resolved; see record) — "
            f"[decisions.md]({decisions}?plain=1#L3)",
            text,
        )
        self.assertIn(
            "- DEC-0002 (unresolved; see record) — "
            f"[decisions.md]({decisions}?plain=1#L11)",
            text,
        )
        self.assertIn("- F-1 (high, open) — report not present", text)
        self.assertNotIn("agent-provisional", text)

    def test_zero_counts_are_explicit_and_the_packet_is_no_approval(self) -> None:
        _, text = self.packet()
        self.assertIn("- Risk: not recorded (no record)", text)
        self.assertIn(
            "- Open findings: 0 · Provisional decisions: 0 · Human decisions: 0", text
        )
        self.assertIn("### Decisions\n\nNone (0).", text)
        self.assertIn("### Open findings\n\nNone (0).", text)
        self.assertIn(packet.SUMMARY, text)
        self.assertIsNone(autonomy.HUMAN_APPROVAL.search(text))


class CheckTests(PacketCase):
    """US1 checks (FR-004, AC-009)."""

    def test_run_checks_check_runs_and_ledger_checks(self) -> None:
        record = autonomy.new_run(
            run_id=RUN,
            feature=FEATURE,
            issue=17,
            workflow="ballast-feature",
            mode="human-gated",
            integration="claude",
        )
        autonomy.write_run(self.root, record)
        autonomy.write_json(
            autonomy.run_dir(self.root, RUN) / "checks.json",
            [{"command": "./scripts/check", "exit": 0, "seconds": 12.34}],
        )
        self.fake.check_pages = [
            [
                {
                    "id": 21,
                    "name": "ci / test",
                    "status": "completed",
                    "conclusion": "success",
                    "html_url": "https://evil.example/runs/21",
                }
            ],
            [{"id": 22, "name": "lint", "status": "in_progress", "conclusion": None}],
        ]
        skipped = self.verify(None, "suite-a", "skipped", "agent-reported")
        unavailable = self.verify(None, "suite-b", "unavailable", "agent-reported")
        _, text = self.packet()
        self.assertIn(
            "- run-checks (runner, before publication, not bound to the head commit): "
            "./scripts/check exited 0 in 12.3s",
            text,
        )
        self.assertIn(
            "- GitHub check runs at head: [ci / test](https://github.com/o/r/runs/21) "
            "completed/success · [lint](https://github.com/o/r/runs/22) in progress",
            text,
        )
        self.assertNotIn("evil", text)
        self.assertIn(
            f"- suite-a: skipped (agent-reported) — ledger event {skipped} "
            f"of run {RUN}",
            text,
        )
        self.assertIn(
            f"- suite-b: unavailable (agent-reported) — ledger event {unavailable}",
            text,
        )
        (call,) = self.fake.gh_calls("checks")
        self.assertEqual(
            call[-1], f"repos/o/r/commits/{self.head}/check-runs?per_page=100"
        )

    def test_nothing_recorded_reads_not_run_and_none_reported(self) -> None:
        _, text = self.packet()
        self.assertIn("- run-checks: not run", text)
        self.assertIn("- GitHub check runs at head: none reported", text)


class EndToEndTests(PacketCase):
    """A real checkpoint publishes the packet (AC-001, AC-002, AC-003)."""

    def test_reused_pr_gets_the_packet_and_an_event(self) -> None:
        self.verify("AC-006", T.format("seven"))
        outcome, text = self.packet()
        self.assertEqual(outcome.state, "reused")
        self.assertPacket(outcome, "published")
        self.assertEqual(
            packet.format_line(outcome.packet),
            f"Acceptance packet: published #{PR} head {self.head[:12]}",
        )
        self.assertTrue(self.fake.body_of("edit").endswith(text))
        self.assertTrue(self.body.startswith("Human intro."))
        (event,) = self.packet_events()
        self.assertEqual(
            {k: event[k] for k in ("outcome", "pr_number", "head", "base")},
            {
                "outcome": "published",
                "pr_number": PR,
                "head": self.head,
                "base": self.base_sha,
            },
        )
        self.assertEqual([event[k] for k in ledger.PACKET_COUNTS], [1, 0, 4, 0, 1])
        self.assertEqual(event["packet_digest"], sha(packet._mask(text)))  # noqa: SLF001

    def test_created_pr_gets_the_packet(self) -> None:
        self.fake.prs.clear()
        self.fake.shas = (self.head, self.base_sha)
        outcome, text = self.packet()
        self.assertEqual(outcome.state, "created")
        self.assertPacket(outcome, "published")
        self.assertIn("## Acceptance packet", text)
        self.assertEqual(self.packet_events()[0]["outcome"], "published")


class SourceTests(PacketCase):
    """US2: every source linked at head, absent ones named (AC-007 to AC-009)."""

    def test_every_artifact_is_linked_at_head(self) -> None:
        for name in ("plan.md", "decisions.md", "reviews/plan.md", "reviews/tasks.md"):
            (self.feature / name).parent.mkdir(parents=True, exist_ok=True)
            (self.feature / name).write_text("# x\n")
        (self.feature / "autonomous").mkdir()
        (self.feature / "autonomous/record.md").write_text("# record\n")
        self.head = self.commit()
        self.open_pr()
        _, text = self.packet()
        sources = text.split("### Sources", 1)[1]
        for name in (
            "intent.md",
            "spec.md",
            "plan.md",
            "tasks.md",
            "decisions.md",
            "acceptance-evidence.json",
            "reviews/plan.md",
            "reviews/tasks.md",
            "autonomous/record.md",
        ):
            self.assertEqual(
                sources.count(f"({self.blob(f'{FEATURE}/{name}')})"), 1, name
            )
        self.assertIn(
            f"- diff: [{self.base_sha[:12]}...{self.head[:12]}]"
            f"(https://github.com/o/r/compare/{self.base_sha}...{self.head})",
            sources,
        )

    def test_absent_artifacts_read_not_present(self) -> None:
        _, text = self.packet()
        sources = text.split("### Sources", 1)[1]
        self.assertIn("plan: not present", sources)
        self.assertIn("- decisions: not present", sources)
        self.assertIn("- reviews: not present", sources)
        self.assertIn("- run record: not present", sources)
        self.assertIn("- acceptance evidence: [acceptance-evidence.json](", sources)

    def test_every_summary_line_carries_a_link_or_a_ledger_reference(self) -> None:
        DecisionTests.autonomous(self)  # type: ignore[arg-type]
        self.fake.check_pages = [
            [{"id": 5, "name": "ci", "status": "completed", "conclusion": "success"}]
        ]
        self.verify("AC-001", T.format("one"))
        self.verify("AC-001", T.format("two"))
        _, text = self.packet()
        for url in re.findall(r"\]\(([^)]*)\)", text):
            self.assertTrue(url.startswith("https://github.com/o/r/"), url)
            self.assertTrue(
                self.head in url or self.base_sha in url or "/runs/" in url, url
            )
        for row in rows(text).values():
            self.assertIn("](https://github.com/o/r/blob/", row[0])
        verified = rows(text)["AC-001"][3]
        self.assertEqual(verified.count(f"]({self.blob('tests/test_demo.py')})"), 2)
        body = text.split("### Decisions", 1)[1].split("### API changes", 1)[0]
        for line in body.splitlines():
            if (
                line.startswith("- ")
                and "not run" not in line
                and "none reported" not in line
            ):
                self.assertTrue(
                    "](https://github.com/o/r/" in line or "ledger event" in line, line
                )
        # A ledger reference only stands in for records with no URL.
        for line in text.splitlines():
            if "ledger event" in line and line.startswith("- PD-"):
                self.fail(line)


class RepublishTests(PacketCase):
    """US3: one packet, updated in place, never without a change (AC-010 to AC-014)."""

    def test_same_sources_make_no_edit_and_record_unchanged(self) -> None:
        self.packet()
        first = self.packet_events()[-1]
        # With a fixed clock the whole checkpoint makes no edit call (R13).
        edits = len(self.fake.gh_calls("edit"))
        self.assertPacket(self.check(), "unchanged")
        self.assertEqual(len(self.fake.gh_calls("edit")), edits)
        later = datetime(2026, 10, 5, 9, 0, tzinfo=UTC)
        with patch.object(draft_pr, "_now", lambda: later):
            outcome = self.check()
        self.assertPacket(outcome, "unchanged")
        # #17 refreshes its own Last checkpoint line; the packet made no edit.
        self.assertEqual(len(self.fake.gh_calls("edit")), edits + 1)
        self.assertNotIn("2026-10-05T09:00:00Z", section_of(self.body))
        last = self.packet_events()[-1]
        self.assertEqual(last["outcome"], "unchanged")
        self.assertEqual(last["packet_digest"], first["packet_digest"])

    def test_any_source_change_replaces_the_section_in_place(self) -> None:
        self.packet()

        def new_head() -> None:
            (self.root / "src/app.py").write_text("VALUE = 2\n")
            self.head = self.commit()
            self.open_pr(self.body)

        def new_base() -> None:
            self.base_sha = git(self.root, "rev-parse", "HEAD~1").strip()
            self.open_pr(self.body)

        def new_spec() -> None:
            self.write_feature(SPEC + "\nMore context.\n")
            self.head = self.commit()
            self.open_pr(self.body)

        def new_evidence() -> None:
            self.verify("AC-006", T.format("seven"))

        for change in (new_head, new_base, new_spec, new_evidence):
            with self.subTest(change=change.__name__):
                change()
                outcome = self.check()
                self.assertPacket(outcome, "updated")
                self.assertEqual(self.body.count(BEGIN), 1)
                self.assertEqual(self.body.count(END), 1)
                self.assertIn(f"Head: `{self.head[:12]}`", section_of(self.body))
                self.assertEqual(self.packet_events()[-1]["outcome"], "updated")

    def test_header_states_versions_and_time(self) -> None:
        _, text = self.packet()
        version = git(self.root, "rev-parse", f"{self.head}:{FEATURE}").strip()
        self.assertIn(
            f"- Feature: `{FEATURE}/` version `{version[:12]}` "
            f"(spec `sha256:{sha(SPEC)[:12]}`)",
            text,
        )
        self.assertIn(
            f"- Base: `{self.base_sha[:12]}` · Head: `{self.head[:12]}`", text
        )
        self.assertIn("- Generated: 2026-10-04T12:34:56Z", text)

    def test_only_the_packet_span_changes(self) -> None:
        summary = f"{autonomy.SUMMARY_BEGIN}\nsummary\n{autonomy.SUMMARY_END}"
        self.packet()
        body = self.body
        before = "Human before.\n\n" + summary + "\n\n"
        after = "\n\nHuman after.\r\n"
        start, end = body.index(BEGIN), body.index(END) + len(END)
        old = (
            body[:start]
            + body[start:end].replace("version", "old version")
            + body[end:]
        )
        self.open_pr(before + old + after)
        outcome = self.check()
        self.assertPacket(outcome, "updated")
        new = self.body
        start = new.index(BEGIN)
        self.assertEqual(new[:start], (before + old)[: (before + old).index(BEGIN)])
        self.assertTrue(new.endswith(body[end:] + after))
        for argv in self.fake.gh_calls():
            for token in FORBIDDEN_EDIT_ARGS:
                self.assertNotIn(token, argv[1:])

    def test_deleted_section_is_appended_once(self) -> None:
        for adopted in (False, True):
            with self.subTest(adopted=adopted):
                if adopted:  # Opened by a human, with text of its own.
                    self.open_pr("Opened by hand.")
                else:  # Created by Ballast.
                    self.fake.prs.clear()
                    self.fake.shas = (self.head, self.base_sha)
                self.assertEqual(self.check().state, "reused" if adopted else "created")
                body = self.body
                cut = body[: body.index(BEGIN)].rstrip("\n") + "\n\nMy own line."
                self.open_pr(cut)
                outcome = self.check()
                self.assertPacket(outcome, "published")
                self.assertTrue(self.body.startswith(cut + "\n\n" + BEGIN))
                self.assertEqual(self.body.count(BEGIN), 1)

    def test_unmanaged_sections_are_left_alone(self) -> None:
        for body in (
            f"{BEGIN}\nx\n{END}\n{BEGIN}\ny\n{END}",
            f"{END}\nx\n{BEGIN}",
            f"{BEGIN}\nno end",
        ):
            with self.subTest(body=body[:30]):
                self.open_pr(f"Related to #17\n\n{body}")
                edits = len(self.fake.gh_calls("edit"))
                outcome = self.check()
                self.assertPacket(outcome, "failed-retryable", "section-unmanaged")
                self.assertEqual(len(self.fake.gh_calls("edit")), edits)

    def test_body_changed_before_the_edit_is_left_alone(self) -> None:
        self.open_pr("Related to #17")
        reads = []

        def human_edit(_number: int) -> None:
            reads.append(1)
            if len(reads) == 2:  # noqa: PLR2004 - The packet's re-read.
                self.fake.prs[0]["body"] = "Edited meanwhile."

        self.fake.on_pull = human_edit
        outcome = self.check()
        self.assertPacket(outcome, "failed-retryable", "body-changed")
        self.assertEqual(self.fake.gh_calls("edit"), [])
        self.assertEqual(self.body, "Edited meanwhile.")


class ReviewConfigTests(PacketCase):
    """US4 configuration (AC-015, R12)."""

    def configure(self, text: str) -> None:
        (self.root / "ballast.toml").write_text(
            '[github]\nrepository = "o/r"\n\n' + text
        )

    def test_not_configured_is_one_line_each(self) -> None:
        _, text = self.packet()
        self.assertIn("### API changes\n\nAPI: not configured.\n\n### UI states", text)
        self.assertIn(
            "### UI states\n\nUI states: not configured.\n\n### Sources", text
        )
        self.assertEqual(self.fake.gh_calls("contents"), [])

    def test_invalid_configuration_names_a_fixed_reason(self) -> None:
        state = (
            '[[review.ui_states]]\nname = "x"\ncriteria = ["AC-001"]\npath = "a.png"\n'
        )
        cases = {
            '[review]\nopenapi = "../x"\n': (
                "API: configuration invalid (openapi is not a safe repository path)."
            ),
            '[[review.ui_states]]\nname = "x"\ncriteria = ["AC-1"]\npath = "a.png"\n': (
                "UI states: configuration invalid (UI state criteria must be "
                "AC-NNN IDs)."
            ),
            state + 'check = "c"\n': (
                "UI states: configuration invalid (UI state needs exactly one of path "
                "or check)."
            ),
            state * 51: "UI states: configuration invalid (more than 50 UI states).",
            state.replace('"x"', '"' + "n" * 81 + '"'): (
                "UI states: configuration invalid (UI state name must be 1-80 "
                "characters)."
            ),
            state.replace("AC-001", "AC-099"): (
                "UI states: configuration invalid (UI state names a criterion the spec "
                "does not define)."
            ),
        }
        for config, expected in cases.items():
            with self.subTest(config=config[:50]):
                self.configure(config)
                outcome, text = self.packet()
                self.assertIn(outcome.packet.state, {"published", "updated"})
                self.assertIn(expected, text)
                self.assertIn("### Criteria", text)


OPENAPI_BASE = {
    "openapi": "3.0.0",
    "paths": {
        "/orders": {
            "get": {"responses": {"200": {"description": "old"}}},
            "post": {
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/Order"}
                        }
                    }
                },
                "responses": {},
            },
        },
        "/orders/{id}": {"delete": {"responses": {}}},
        "/items": {
            "get": {
                "parameters": [
                    {"name": "q", "in": "query"},
                    {"name": "page", "in": "query"},
                    {"$ref": "#/components/parameters/Size"},
                ],
                "responses": {},
            },
            "put": {"requestBody": {"content": {}}, "responses": {}},
        },
    },
    "components": {
        "schemas": {
            "Order": {"properties": {"id": {}, "note": {}}, "required": ["id"]},
            "Loop": {"$ref": "#/components/schemas/Loop"},
        },
        "parameters": {"Size": {"name": "size", "in": "query"}},
    },
}


def openapi_head() -> dict[str, Any]:
    """Return the base document with one of each kind of change."""
    head = json.loads(json.dumps(OPENAPI_BASE))
    paths = head["paths"]
    paths["/orders"]["get"]["responses"]["200"]["description"] = "new"
    head["components"]["schemas"]["Order"] = {
        "properties": {"id": {}, "note": {}},
        "required": ["id", "note"],
    }
    del paths["/orders/{id}"]
    paths["/payments"] = {"post": {"responses": {}}}
    paths["/items"]["get"]["parameters"] = [
        {"name": "q", "in": "query", "required": True},
        {"$ref": "#/components/parameters/Size"},
    ]
    paths["/items"]["put"]["requestBody"]["required"] = True
    return head


class OpenApiTests(PacketCase):
    """US4 OpenAPI (AC-016, AC-017, FR-010, FR-012)."""

    PATH = "docs/api/openapi.json"

    def setUp(self) -> None:
        super().setUp()
        (self.root / "ballast.toml").write_text(
            f'[github]\nrepository = "o/r"\n\n[review]\nopenapi = "{self.PATH}"\n'
        )

    def serve(self, base: object, head: object) -> None:
        for ref, value in ((self.base_sha, base), (self.head, head)):
            if value is None:
                self.fake.contents.pop((self.PATH, ref), None)
            else:
                self.fake.contents[self.PATH, ref] = (
                    value
                    if isinstance(value, (str, draft_pr.Result))
                    else json.dumps(value)
                )

    def api(self) -> str:
        _, text = self.packet()
        return text.split("### API changes\n\n", 1)[1].split("\n\n### UI states", 1)[0]

    def test_changes_are_listed_and_breaking_ones_flagged(self) -> None:
        self.serve(OPENAPI_BASE, openapi_head())
        self.assertEqual(
            self.api().splitlines(),
            [
                (
                    f"API (`{self.PATH}`, base → head): 1 added, 1 removed, 4 changed; "
                    "4 potentially breaking."
                ),
                packet.API_NOTE,
                "- added: POST /payments",
                (
                    "- removed: DELETE /orders/{id} — potentially breaking (operation "
                    "removed)"
                ),
                (
                    "- changed: GET /items — potentially breaking (parameter removed, "
                    "parameter now required)"
                ),
                "- changed: GET /orders — response changed",
                (
                    "- changed: POST /orders — potentially breaking (request field now "
                    "required)"
                ),
                (
                    "- changed: PUT /items — potentially breaking (request body now "
                    "required)"
                ),
            ],
        )
        calls = self.fake.gh_calls("contents")
        self.assertEqual(
            [argv[-1] for argv in calls],
            [
                f"repos/o/r/contents/{self.PATH}?ref={self.base_sha}",
                f"repos/o/r/contents/{self.PATH}?ref={self.head}",
            ],
        )

    def test_request_field_removed_through_a_ref_and_cycles_end(self) -> None:
        head = json.loads(json.dumps(OPENAPI_BASE))
        head["components"]["schemas"]["Order"] = {"properties": {"id": {}}}
        head["paths"]["/loop"] = {
            "post": {
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/Loop"}
                        }
                    }
                },
                "responses": {},
            }
        }
        base = json.loads(json.dumps(head))
        base["components"]["schemas"]["Order"] = OPENAPI_BASE["components"]["schemas"][
            "Order"
        ]
        base["paths"]["/loop"]["post"]["responses"] = {"200": {}}
        self.serve(base, head)
        api = self.api()
        self.assertIn(
            "- changed: POST /orders — potentially breaking (request field removed)",
            api,
        )
        self.assertIn("- changed: POST /loop — response changed", api)
        self.assertEqual(
            packet.compare_documents(OPENAPI_BASE, openapi_head()).state, "changed"
        )

    def test_states_without_a_comparison(self) -> None:
        cases = (
            (OPENAPI_BASE, OPENAPI_BASE, "no API change"),
            (None, OPENAPI_BASE, "added in this PR"),
            (OPENAPI_BASE, None, "removed in this PR"),
            (OPENAPI_BASE, "openapi: 3.0.0\n", "could not compare (not JSON)"),
            (OPENAPI_BASE, http(502), "could not compare (github-error)"),
            (
                OPENAPI_BASE,
                {"swagger": "2.0"},
                "could not compare (not an OpenAPI document)",
            ),
            (
                OPENAPI_BASE,
                {
                    "openapi": "3",
                    "paths": {f"/p{n}": {"get": {}} for n in range(2001)},
                },
                "could not compare (too large)",
            ),
        )
        for base, head, expected in cases:
            with self.subTest(expected=expected):
                self.serve(base, head)
                outcome, text = self.packet()
                self.assertIn(f"API (`{self.PATH}`): {expected}.", text)
                self.assertIn(outcome.packet.state, {"published", "updated"})

    def test_long_lists_are_capped_in_the_pr_but_whole_in_the_archive(self) -> None:
        head = json.loads(json.dumps(OPENAPI_BASE))
        head["paths"].update({f"/new{n:02d}": {"get": {}} for n in range(60)})
        self.serve(OPENAPI_BASE, head)
        api = self.api()
        self.assertEqual(api.count("- added: GET /new"), 50)
        self.assertIn("- … 10 more in the complete packet", api)
        archive = ledger.archive_dir(self.root, RUN) / "acceptance-packet.md"
        self.assertEqual(archive.read_text().count("- added: GET /new"), 60)

    def test_response_without_inline_content_is_too_large(self) -> None:
        self.serve(OPENAPI_BASE, OPENAPI_BASE)
        large = draft_pr.Result(
            0, json.dumps({"type": "file", "encoding": "none", "content": ""})
        )
        self.fake.contents[self.PATH, self.head] = large
        self.assertIn("could not compare (too large)", self.api())


class UiStateTests(PacketCase):
    """US4 UI states (AC-018)."""

    def test_results_appear_beside_their_criteria(self) -> None:
        (self.root / "docs").mkdir()
        (self.root / "docs/login.png").write_bytes(b"\x89PNG")
        self.head = self.commit()
        self.open_pr()
        (self.root / "ballast.toml").write_text(
            '[github]\nrepository = "o/r"\n\n'
            '[[review.ui_states]]\nname = "Login"\ncriteria = ["AC-001"]\n'
            'path = "docs/login.png"\n\n'
            '[[review.ui_states]]\nname = "Checkout"\ncriteria = ["AC-002"]\n'
            'check = "ui / checkout"\n\n'
            '[[review.ui_states]]\nname = "Cart"\ncriteria = ["AC-003"]\n'
            'check = "ui / cart"\n\n'
            '[[review.ui_states]]\nname = "Gone"\ncriteria = ["AC-006"]\n'
            'path = "docs/gone.png"\n'
        )
        self.fake.check_pages = [
            [
                {
                    "id": 31,
                    "name": "ui / checkout",
                    "status": "completed",
                    "conclusion": "success",
                },
                {
                    "id": 32,
                    "name": "ui / cart",
                    "status": "in_progress",
                    "conclusion": None,
                },
            ]
        ]
        _, text = self.packet()
        found = rows(text)
        self.assertIn(
            f"UI Login: [present at head]({self.blob('docs/login.png')})",
            found["AC-001"][3],
        )
        self.assertIn(
            "UI Checkout: [passed](https://github.com/o/r/runs/31)", found["AC-002"][3]
        )
        self.assertIn(
            "UI Cart: [not run (in progress)](https://github.com/o/r/runs/32)",
            found["AC-003"][3],
        )
        self.assertIn("UI Gone: missing", found["AC-006"][3])
        self.assertEqual(found["AC-003"][2], "missing")
        self.assertEqual(found["AC-002"][2], "not run")
        self.assertIn("- Login (AC-001): [present at head](", text)


class FailureTests(PacketCase):
    """US5 failures never block (AC-019, FR-015)."""

    def test_each_failure_is_recorded_and_retried(self) -> None:
        self.packet()
        published = section_of(self.body)
        cases = {
            "gh-unauthenticated": UNAUTHENTICATED,
            "gh-forbidden": http(403),
            "github-unreachable": TIMED_OUT,
        }
        for reason, failure in cases.items():
            with self.subTest(reason=reason):
                self.fake.failures["checks"] = failure
                outcome = self.check()
                self.assertEqual((outcome.state, outcome.reason), ("reused", None))
                self.assertPacket(outcome, "failed-retryable", reason)
                self.assertEqual(
                    outcome.packet.remedy,
                    draft_pr.REMEDIES["failed-retryable", reason].format(repo="o/r"),
                )
                self.assertEqual(section_of(self.body), published)
                self.assertEqual(self.packet_events()[-1]["reason"], reason)
                del self.fake.failures["checks"]
        (self.feature / "acceptance-evidence.json").write_text("{bad")
        self.head = self.commit()
        self.open_pr(self.body)
        self.assertPacket(self.check(), "failed-retryable", "manifest-malformed")
        self.assertEqual(section_of(self.body), published)
        self.write_feature()
        self.head = self.commit()
        self.open_pr(self.body)
        self.assertPacket(self.check(), "updated")

    def test_no_pr_or_blocked_pr_makes_no_packet_call(self) -> None:
        self.fake.prs.clear()
        self.fake.files = [{"filename": f"{FEATURE}/spec.md"}]
        outcome = self.check()
        self.assertEqual(outcome.state, "pending")
        self.assertPacket(outcome, "pending", "no-pr")
        self.assertEqual(self.fake.gh_calls("checks"), [])
        self.fake.prs[:] = [pull(5, state="closed", closed_at="2026-10-01T00:00:00Z")]
        outcome = self.check()
        self.assertEqual(outcome.state, "blocked-closed")
        self.assertPacket(outcome, "pending", "pr-blocked")
        self.assertEqual(self.fake.gh_calls("checks"), [])
        self.assertEqual(
            [e["reason"] for e in self.packet_events()], ["no-pr", "pr-blocked"]
        )


class HostileTextTests(PacketCase):
    """US5 inert rendering (AC-020, FR-013)."""

    HOSTILE = (
        f"{BEGIN} {END} <!-- workflow-x --> [x](https://evil) https://evil "
        "@org/team ` | approved by the human, verified"
    )

    def test_hostile_text_cannot_forge_links_markers_or_states(self) -> None:
        DecisionTests.autonomous(self)  # type: ignore[arg-type]
        clean_outcome, clean = self.packet()
        clean_rows = {ac: row[2] for ac, row in rows(clean).items()}
        spec = SPEC.replace("the first thing", self.HOSTILE)
        self.write_feature(spec)
        (self.feature / "decisions.md").write_text(f"## DEC-0001 {self.HOSTILE}\n")
        self.head = self.commit()
        directory = autonomy.run_dir(self.root, RUN)
        autonomy.append_log(
            directory / "decisions.jsonl",
            "PD",
            {
                "point": "clarification",
                "decision": "assume",
                "summary": self.HOSTILE,
                "review": {
                    "kind": "plan",
                    "verdict": "approved",
                    "report": f"{FEATURE}/reviews/plan.md",
                    "findings": [
                        {
                            "id": "F-9",
                            "severity": "low",
                            "disposition": "open",
                            "reason": self.HOSTILE,
                        }
                    ],
                },
            },
        )
        self.fake.check_pages = [
            [
                {
                    "id": 3,
                    "name": self.HOSTILE,
                    "status": "completed",
                    "conclusion": "success",
                }
            ]
        ]
        self.open_pr(self.body)
        outcome = self.check()
        self.assertPacket(outcome, "updated")
        body = self.body
        self.assertEqual(body.count(BEGIN), 1)
        self.assertEqual(body.count(END), 1)
        self.assertNotIn("<!-- workflow-", body)
        self.assertNotIn("https://evil", body)
        self.assertNotIn("](https:\u200b//evil", body)
        self.assertNotIn("@org", body)
        self.assertIsNone(autonomy.HUMAN_APPROVAL.search(body))
        found = rows(section_of(body))
        self.assertEqual({ac: row[2] for ac, row in found.items()}, clean_rows)
        for row in found.values():
            self.assertEqual(len(row), 4)
        self.assertIn("agent-provisional", section_of(body))
        self.assertEqual(clean_outcome.packet.state, "published")


class SizeTests(PacketCase):
    """US5 size (AC-021, FR-014)."""

    def test_long_body_shortens_the_packet_and_archives_it_whole(self) -> None:
        DecisionTests.autonomous(self)  # type: ignore[arg-type]
        self.verify("AC-001", T.format("one"))
        self.verify("AC-001", T.format("two"))
        full = len(packet.render(self.collect()))
        # Human text that leaves room for a shortened packet but not this one.
        human = "h" * max(60000, packet.BODY_LIMIT - packet.MARGIN - full + 10)
        self.open_pr(human)
        outcome, text = self.packet()
        self.assertPacket(outcome, "published")
        self.assertTrue(outcome.packet.shortened)
        self.assertIn(
            f"Shortened to fit the PR description. Complete packet: speckit-runs/{RUN}/"
            "acceptance-packet.md in the operator's clone.",
            text,
        )
        self.assertIn("Verified at head: [AC-001](", text)
        self.assertNotIn("| [AC-001](", text)
        for ac_id in ("AC-002", "AC-003", "AC-004", "AC-005", "AC-006"):
            self.assertIn(f"| [{ac_id}](", text)
        self.assertIn("PD-0003 F-003 (medium, open)", text)
        self.assertIn("PD-0002 (clarification, agent-provisional)", text)
        self.assertLessEqual(len(self.body), packet.BODY_LIMIT)
        archive = ledger.archive_dir(self.root, RUN) / "acceptance-packet.md"
        self.assertEqual(stat.S_IMODE(archive.stat().st_mode), 0o600)
        stored = archive.read_text()
        self.assertIn("| [AC-001](", stored)
        self.assertNotIn(str(self.root), stored)
        self.assertNotIn(socket.gethostname(), stored)

    def test_no_room_even_shortened_is_too_large(self) -> None:
        self.packet()
        published = section_of(self.body)
        self.open_pr("h" * (packet.BODY_LIMIT - 500) + "\n\n" + published)
        outcome = self.check()
        self.assertPacket(outcome, "failed-retryable", "too-large")
        self.assertIn(published, self.body)


class CredentialTests(PacketCase):
    """US5 no credential leaks (AC-022, FR-016)."""

    def test_no_token_reaches_output_ledger_archive_or_body(self) -> None:
        secrets = " ".join(SECRET_TOKENS) + " Authorization: token zzzsecretzzz"
        self.write_feature(SPEC.replace("the first thing", secrets))
        self.head = self.commit()
        self.open_pr()
        stderr_token = draft_pr.Result(1, "", f"HTTP 502 token {SECRET_TOKENS[0]}")

        def leaky(*_args: object, **_kwargs: object) -> None:
            raise RuntimeError(SECRET_TOKENS[1])

        values = (*SECRET_TOKENS, "zzzsecretzzz", "c" * 30)
        with patch.dict(os.environ, {"GH_TOKEN": SECRET_TOKENS[0]}):
            output = io.StringIO()
            with redirect_stdout(output):
                outcome = self.check()
                print(packet.format_line(outcome.packet))  # noqa: T201
                self.fake.failures["checks"] = stderr_token
                failed = self.check()
                print(packet.format_line(failed.packet))  # noqa: T201
                del self.fake.failures["checks"]
                with patch.object(packet, "publish", leaky):
                    crashed = self.check()
                print(packet.format_line(crashed.packet))  # noqa: T201
        self.assertPacket(outcome, "published")
        self.assertPacket(failed, "failed-retryable", "github-error")
        self.assertPacket(crashed, "failed-retryable", "internal-error")
        self.assertEqual(crashed.packet.detail, "RuntimeError")
        archive = (
            ledger.archive_dir(self.root, RUN) / "acceptance-packet.md"
        ).read_text()
        events = ledger.ledger_path(self.root, RUN).read_text()
        for value in values:
            for name, text in (
                ("stdout", output.getvalue()),
                ("ledger", events),
                ("archive", archive),
                ("body", self.body),
            ):
                self.assertNotIn(value, text, name)
        self.assertIn(r"\[redacted\]", section_of(self.body))


if __name__ == "__main__":
    unittest.main()
