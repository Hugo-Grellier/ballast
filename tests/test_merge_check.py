"""Merge verdict: MERGE, HUMAN and BLOCK, each refusal, the command and the merge."""

from __future__ import annotations

import contextlib
import io
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import admission, merge_check, spec_check, worktree

FETCH = merge_check.fetch  # the real fetch; setUp replaces it with a fake

REPO = "example/fixture"
ISSUE = 5
URL = f"https://github.com/{REPO}/issues/{ISSUE}"
BALLAST = Path(__file__).resolve().parents[1]
WORKFLOW = "Human-only: tools/gate.py\nCoverage-exempt: docs/**\n"
SPEC = """# Capability

Covers: tools/a.py

### Requirement: One
The tool SHALL do one thing.

#### Scenario: First
- WHEN x happens
- THEN y follows
- Test: tests/test_a.py::A::test_first
"""
SECOND = """
#### Scenario: Second
- WHEN z happens
- THEN w follows
- Test: tests/test_a.py::A::test_second
"""
DELTA = """
## Capability: docs/specs/cap.md

### Requirement: One

#### Added Scenario: Second
- WHEN z happens
- THEN w follows
"""
EMPTY_DELTA = "\n"


def body(risk: str) -> str:
    """Return a PR body ticking one risk box."""
    boxes = "".join(
        f"- [{'x' if r == risk else ' '}] {r}\n" for r in ("R0", "R1", "R2")
    )
    return f"Closes #{ISSUE}\n\n## Risk\n\n{boxes}"


def git(root: Path, *args: str) -> str:
    """Run git in the fixture repository."""
    return subprocess.run(  # noqa: S603 -- fixed git argv
        ["git", "-C", str(root), *args],  # noqa: S607
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def digest(entries: str) -> str:
    """Return the canonical hash of a delta document."""
    return spec_check.delta_hash(spec_check.parse_delta(entries))


def comment(number: int, text: str, at: str, updated: str | None = None) -> dict:
    """Return an issue comment as the REST API lists it."""
    return {
        "id": number,
        "html_url": f"{URL}#issuecomment-{number}",
        "body": text,
        "author_association": "OWNER",
        "created_at": at,
        "updated_at": updated or at,
    }


def delta(entries: str, updated: str | None = None) -> dict:
    """Return the posted delta comment, created at T1."""
    text = f"## Spec delta\nHash: {digest(entries)}\n{entries}"
    return comment(101, text, "2026-10-21T10:00:00Z", updated)


def approval(entries: str, risk: str = "R1", updated: str | None = None) -> dict:
    """Return a relayed approval of the delta comment, created at T2."""
    line = f"Spec approved: {digest(entries)} risk {risk} delta {URL}#issuecomment-101"
    text = f'{line}\n\nRelayed: the operator said "yes" on 2026-10-21.'
    return comment(102, text, "2026-10-21T11:00:00Z", updated)


class MergeVerdictTests(unittest.TestCase):
    """A fake gh stands in for GitHub; a throwaway Git repository for the PR."""

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        git(self.root, "init", "-q", "-b", "main")
        git(self.root, "config", "user.email", "t@example.invalid")
        git(self.root, "config", "user.name", "t")
        git(self.root, "config", "commit.gpgsign", "false")
        self.write(
            {
                "project/workflow.md": WORKFLOW,
                "docs/specs/cap.md": SPEC,
                "tools/a.py": "",
                "tools/gate.py": "",
                "docs/guide.md": "",
            }
        )
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "base")
        self.base = self.tip = git(self.root, "rev-parse", "HEAD")
        self.pr = {
            "number": 7,
            "state": "OPEN",
            "isDraft": False,
            "headRefName": "docs/7-typo",
            "baseRefName": "main",
            "author": {"login": "someone", "is_bot": False},
            "body": body("R0"),
            "closingIssuesReferences": [
                {
                    "number": ISSUE,
                    "repository": {"name": "fixture", "owner": {"login": "example"}},
                }
            ],
        }
        self.issue: object = {"body": "Outcome.\n\nRisk: R0\n"}
        self.comments: list = []
        self.change({"docs/guide.md": "Fixed a typo.\n"})
        self.rules: object = [
            [
                {"type": "deletion"},
                {
                    "type": "required_status_checks",
                    "parameters": {
                        "required_status_checks": [
                            {"context": "lint"},
                            {"context": "test"},
                        ]
                    },
                },
            ]
        ]
        self.branch: object = {"name": "main", "protection": {"enabled": False}}
        self.checks: object = [
            {"name": "lint", "bucket": "pass"},
            {"name": "test", "bucket": "pass"},
            {"name": "advisory", "bucket": "fail"},
        ]
        self.merge_code = 0
        self.queue = False
        self.failing: dict[str, int] = {}
        self.calls: list[tuple[str, ...]] = []
        for target, name, fake in (
            (merge_check, "gh", self.fake),
            (merge_check, "fetch", lambda *_: self.tip),
            # Tests may run inside an issue checkout; the refusal has its own test.
            (worktree, "inside_checkout", lambda: False),
        ):
            patcher = patch.object(target, name, side_effect=fake)
            patcher.start()
            self.addCleanup(patcher.stop)

    def write(self, files: dict[str, str | None]) -> None:
        for path, text in files.items():
            target = self.root / path
            if text is None:
                target.unlink()
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")

    def change(self, files: dict[str, str | None]) -> str:
        """Make the PR head one commit on the base changing files."""
        git(self.root, "checkout", "-q", "-B", "pr", self.base)
        self.write(files)
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "--allow-empty", "-m", "pr")
        self.head = git(self.root, "rev-parse", "HEAD")
        git(self.root, "checkout", "-q", "main")
        self.pr["headRefOid"] = self.head
        self.files: list = [{"filename": path} for path in files]
        self.pr["changedFiles"] = len(self.files)
        return self.head

    def advance_target(self, files: dict[str, str | None]) -> None:
        """Land a concurrent change on the target branch after the PR forked."""
        self.write(files)
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "concurrent")
        self.tip = git(self.root, "rev-parse", "HEAD")

    def r1(self, entries: str = DELTA, **approval_fields: str) -> None:
        """Make an R1 PR adding scenario Second, its delta posted and approved."""
        self.change({"docs/specs/cap.md": SPEC + SECOND, "tools/a.py": "x = 1\n"})
        self.pr["body"] = body("R1")
        self.pr["headRefName"] = f"issue-{ISSUE}-abcdef12"
        self.issue = {"body": "Risk: R1"}
        self.comments = [delta(entries), approval(entries, **approval_fields)]

    def issued(self) -> object:
        """Return the issue, open and by a trusted author unless set otherwise."""
        if not isinstance(self.issue, dict):
            return self.issue
        return {"state": "open", "author_association": "OWNER", **self.issue}

    def merged(self) -> int:
        """Return the merge exit code; without a queue a merge is immediate."""
        if not self.merge_code and not self.queue:
            self.pr["state"] = "MERGED"
        return self.merge_code

    def fake(self, *args: str) -> subprocess.CompletedProcess:
        self.calls.append(args)
        output, code = "", 0
        if args[:2] == ("pr", "view"):
            output = json.dumps(self.pr)
        elif args[0] == "api" and "/rules/branches/" in args[1]:
            output = json.dumps(self.rules)
        elif args[0] == "api" and "/branches/" in args[1]:
            output = json.dumps(self.branch)
        elif args[0] == "api" and "/issues/" in args[1]:
            comments = args[1].endswith("/comments?per_page=100")
            output = json.dumps([self.comments] if comments else self.issued())
        elif args[0] == "api":
            # --paginate --slurp: one array per page of up to 100 files.
            pages = [self.files[i : i + 100] for i in range(0, len(self.files), 100)]
            output = json.dumps(pages)
        elif args[:2] == ("pr", "checks"):
            # gh exits 1 or 8 for failing or pending checks but still prints them.
            output = json.dumps(self.checks)
            code = 8 if any(c.get("bucket") != "pass" for c in self.checks) else 0
        elif args[:2] == ("pr", "merge"):
            code = self.merged()
        for marker, failure in self.failing.items():
            if marker in " ".join(args):
                code = failure
        return subprocess.CompletedProcess(["gh", *args], code, output, "")

    def arguments(self, verdict: str, risk: str, *extra: str) -> list[str]:
        arguments = ["--repo", REPO, "--pr", "7", "--root", str(self.root)]
        arguments += ["--reviewed-head", self.head, "--verdict", verdict]
        return [*arguments, "--risk", risk, *extra]

    def check(self, verdict: str = "approved", risk: str = "R0", *extra: str) -> dict:
        args = merge_check.parser().parse_args(self.arguments(verdict, risk, *extra))
        return merge_check.check(args)

    def verdict(self, expected: str, reason: str, *args: str) -> dict:
        result = self.check(*args) if args else self.check()
        self.assertEqual(result["verdict"], expected, result)
        level = result.get(expected.lower(), [])
        self.assertTrue(any(reason in item["reason"] for item in level), result)
        self.assertNotIn("merge", result)
        self.assertFalse([call for call in self.calls if call[:2] == ("pr", "merge")])
        return result

    def blocks(self, reason: str, *args: str) -> dict:
        return self.verdict("BLOCK", reason, *args)

    def human(self, reason: str, *args: str) -> dict:
        return self.verdict("HUMAN", reason, *args)

    def merges(self, *args: str) -> dict:
        result = self.check(*args) if args else self.check()
        self.assertEqual(result["verdict"], "MERGE", result)
        return result

    # MERGE

    def test_prints_exact_squash_merge_pinned_to_reviewed_head(self) -> None:
        self.assertEqual(
            self.merges()["merge"],
            [
                "gh",
                "pr",
                "merge",
                "7",
                "--repo",
                f"github.com/{REPO}",
                "--squash",
                "--match-head-commit",
                self.head,
            ],
        )

    def test_r1_with_approved_conformant_covered_spec_merges(self) -> None:
        self.r1()
        result = self.merges("approved", "R1")
        self.assertEqual(result["spec"]["hash"], digest(DELTA))
        self.assertEqual(result["spec"]["approval"], f"{URL}#issuecomment-102")

    def test_r0_adding_spec_entries_only_merges(self) -> None:
        self.change({"docs/specs/cap.md": SPEC + SECOND})
        self.merges()

    # BLOCK

    def test_refuses_unapproved_verdict(self) -> None:
        self.blocks("did not approve", "changes_required")

    def test_refuses_short_reviewed_head(self) -> None:
        self.head = "abc"
        self.blocks("full commit SHA")

    def test_refuses_head_changed_after_review(self) -> None:
        self.pr["headRefOid"] = "b" * 40
        self.blocks("review is stale")

    def test_refuses_draft(self) -> None:
        self.pr["isDraft"] = True
        self.blocks("draft")

    def test_refuses_closed(self) -> None:
        self.pr["state"] = "MERGED"
        self.blocks("not open")

    def test_refuses_pr_body_without_exactly_one_risk_ticked(self) -> None:
        for text in ("- [ ] R0\n", body("R0") + "- [x] R2\n", ""):
            self.pr["body"] = text
            self.blocks("exactly one risk")

    def test_refuses_missing_failing_or_pending_required_checks(self) -> None:
        # One required check passed, the other never started.
        self.checks = [{"name": "lint", "bucket": "pass"}]
        self.blocks("has not reported")
        for bucket in ("fail", "pending", "skipping", "cancel"):
            self.checks = [
                {"name": "lint", "bucket": "pass"},
                {"name": "test", "bucket": bucket},
            ]
            self.blocks("not green")
        # A rerun that is still pending blocks even if an earlier run passed.
        self.checks = [
            {"name": "lint", "bucket": "pass"},
            {"name": "test", "bucket": "pass"},
            {"name": "test", "bucket": "pending"},
        ]
        self.blocks("not green")

    def test_reads_required_checks_from_rulesets_and_protection(self) -> None:
        self.branch = {
            "name": "main",
            "protection": {"required_status_checks": {"contexts": ["legacy"]}},
        }
        self.blocks("has not reported")
        self.checks.append({"name": "legacy", "bucket": "pass"})
        self.merges()
        self.rules, self.branch = [[]], {"name": "main"}
        self.blocks("No required checks are configured")

    def test_refuses_failed_github_reads_even_with_parseable_output(self) -> None:
        # A failed paginated rules read printed only its first page: "test" is
        # missing from the required set, but the exit code refuses it.
        self.rules = [
            [
                {
                    "type": "required_status_checks",
                    "parameters": {"required_status_checks": [{"context": "lint"}]},
                }
            ]
        ]
        self.checks = [{"name": "lint", "bucket": "pass"}]
        for marker in ("/rules/branches/", "/branches/main", "/files", "pr view"):
            self.failing = {marker: 1}
            self.blocks("GitHub read failed")
        for marker in ("/issues/5", "/comments"):
            self.failing = {marker: 1}
            self.blocks("GitHub read failed")
        # gh pr checks reports failures and pending checks with 1 and 8.
        self.failing = {"pr checks": 4}
        self.blocks("GitHub read failed")

    def test_refuses_unreadable_base_rules(self) -> None:
        for rules in (
            {"message": "Not Found"},
            [[3]],
            [[{"type": "required_status_checks"}]],
        ):
            self.rules = rules
            self.blocks("unreadable")
        self.rules = [[]]
        self.branch = {"message": "Branch not found"}
        self.blocks("unreadable")
        self.branch = {"name": "main"}
        self.pr["baseRefName"] = "../x"
        self.blocks("base branch is malformed")

    def test_refuses_unreadable_github_response(self) -> None:
        self.pr["closingIssuesReferences"] = "#5"
        self.blocks("malformed")
        self.pr["closingIssuesReferences"] = ["#5"]
        self.blocks("malformed")
        self.pr = "not a pr"  # type: ignore[assignment]
        self.blocks("malformed")

    def test_unexpected_errors_and_git_timeouts_block(self) -> None:
        with patch.object(spec_check, "git_delta", side_effect=ValueError):
            self.blocks("Unexpected ValueError")
        timeout = subprocess.TimeoutExpired("git", 120)
        with patch.object(spec_check.subprocess, "run", side_effect=timeout):
            self.blocks("timed out")

    def test_refuses_malformed_file_entries(self) -> None:
        for entry in (
            {},
            {"filename": None},
            {"filename": ""},
            {"filename": 3},
            {"filename": "docs/x.md", "previous_filename": None},
            "docs/x.md",
        ):
            self.files = [entry]
            self.blocks("malformed")

    def test_refuses_truncated_file_list(self) -> None:
        self.pr["changedFiles"] = 101
        self.blocks("incomplete")

    def test_r1_without_approval_blocks(self) -> None:
        self.r1()
        self.comments = [delta(DELTA)]
        self.blocks("needs an approved spec delta", "approved", "R1")

    def test_r1_changing_no_spec_needs_an_approved_empty_delta(self) -> None:
        self.r1()
        self.change({"tools/a.py": "x = 1\n"})
        self.blocks("Spec hash mismatch", "approved", "R1")
        self.comments = [delta(EMPTY_DELTA), approval(EMPTY_DELTA)]
        self.merges("approved", "R1")

    def test_hash_mismatch_blocks(self) -> None:
        self.r1()
        self.change(
            {
                "docs/specs/cap.md": SPEC + SECOND.replace("w follows", "v follows"),
                "tools/a.py": "x = 1\n",
            }
        )
        self.blocks("Spec hash mismatch", "approved", "R1")

    def test_edited_approval_or_delta_after_approval_blocks(self) -> None:
        self.r1(updated="2026-10-21T12:00:00Z")
        self.blocks("edited after the approval", "approved", "R1")
        self.r1()
        self.comments[0] = delta(DELTA, updated="2026-10-21T11:30:00Z")
        self.blocks("edited after the approval", "approved", "R1")
        # A delta edited before the approval was approved as it stood.
        self.comments[0] = delta(DELTA, updated="2026-10-21T10:30:00Z")
        self.merges("approved", "R1")

    def test_stale_delta_blocks(self) -> None:
        # The target branch changed the base text of a modified scenario.
        changed = SPEC.replace("y follows", "y follows quickly")
        self.change({"docs/specs/cap.md": changed})
        self.advance_target({"docs/specs/cap.md": SPEC.replace("y follows", "y ends")})
        self.blocks("delta is stale")
        # Or already has an entry this PR adds.
        self.setUp()
        self.r1()
        self.advance_target({"docs/specs/cap.md": SPEC + SECOND})
        self.blocks("delta is stale", "approved", "R1")

    def test_merge_refused_by_github_is_reported(self) -> None:
        self.merge_code = 1
        args = merge_check.parser().parse_args(
            self.arguments("approved", "R0", "--merge")
        )
        result = merge_check.run(args)
        self.assertEqual(result["verdict"], "BLOCK")
        self.assertNotIn("merged", result)

    # HUMAN

    def test_r2_needs_a_human(self) -> None:
        self.pr["body"] = body("R2")
        self.issue = {"body": "Risk: R2"}
        self.human("R2 PR needs a human merge", "approved", "R2")

    def test_disputed_risk_needs_a_human(self) -> None:
        self.r1()
        self.pr["body"] = body("R0")
        self.human("risk is disputed", "approved", "R1")
        self.setUp()
        self.pr["body"] = body("R1")
        self.human("risk is disputed", "approved", "R0")

    def test_refuses_release_and_dependency_prs(self) -> None:
        self.pr["headRefName"] = "release-please--branches--main"
        self.human("Release and dependency")
        self.pr["headRefName"] = "docs/7-typo"
        self.pr["author"] = {"login": "dependabot", "is_bot": True}
        self.human("Release and dependency")

    def test_dependency_branch_from_a_human_author_needs_a_human(self) -> None:
        self.pr["author"] = {"login": "someone", "is_bot": False}
        for branch in ("dependabot/pip/x", "renovate/x"):
            with self.subTest(branch=branch):
                self.pr["headRefName"] = branch
                self.human("Release and dependency")

    def test_author_without_is_bot_needs_a_human(self) -> None:
        for author in ({"login": "someone"}, {"login": "someone", "is_bot": None}):
            with self.subTest(author=author):
                self.pr["author"] = author
                self.human("Release and dependency")

    def test_refuses_excluded_paths(self) -> None:
        for path in (
            ".github/workflows/ci.yml",
            ".github/CODEOWNERS",
            "CHANGELOG.md",
            "uv.lock",
            "sub/package.json",
            "requirements-dev.txt",
            "Pipfile.lock",
            "Pipfile",
            "poetry.lock",
            "web/pnpm-lock.yaml",
            "Gemfile.lock",
            "build.gradle.kts",
        ):
            self.files = [{"filename": "docs/guide.md"}, {"filename": path}]
            self.pr["changedFiles"] = 2
            result = self.human("workflow, release, dependency or human-only")
            self.assertIn(path, result["handoff"]["risky_paths"])

    def test_refuses_project_excluded_paths(self) -> None:
        self.files = [{"filename": "docs/deploy/values.yaml"}]
        self.merges()
        self.human("human-only", "approved", "R0", "--exclude", "docs/deploy/*")

    def test_human_only_globs_come_from_the_target_branch(self) -> None:
        self.change({"tools/gate.py": "x = 1\n"})
        self.human("human-only")
        # Removing the glob in the PR changes nothing: the base globs judge it.
        self.change({"project/workflow.md": "", "tools/gate.py": "x = 1\n"})
        result = self.human("human-only")
        self.assertIn("tools/gate.py", result["handoff"]["risky_paths"])

    def test_human_only_matching_ignores_case(self) -> None:
        self.change({"Tools/Gate.PY": "x\n"})
        self.human("human-only")

    def test_refuses_renames_from_excluded_paths(self) -> None:
        for old in (".github/workflows/ci.yml", "requirements.txt", "tools/gate.py"):
            self.files = [{"filename": "docs/archived", "previous_filename": old}]
            self.human("human-only")
        self.files = [{"filename": "docs/b.md", "previous_filename": "docs/a.md"}]
        self.merges()

    def test_reads_every_page_of_files(self) -> None:
        self.files = [{"filename": f"docs/{n}.md"} for n in range(150)]
        self.files.append({"filename": "uv.lock"})
        self.pr["changedFiles"] = 151
        self.human("workflow, release, dependency")

    def test_closing_issue_and_its_risk_set_the_floor(self) -> None:
        self.pr["closingIssuesReferences"] = []
        self.human("closes no issue")
        self.setUp()
        self.issue = {"body": "No risk line"}
        self.assertEqual(self.human("no single parseable")["floor"], "unknown")
        self.issue = {"body": "Risk: R0\nRisk: R1"}
        self.human("no single parseable `Risk:` line")
        self.setUp()
        self.pr["closingIssuesReferences"][0]["repository"]["name"] = "other"
        self.human("outside this repository")
        self.setUp()
        self.issue = {"body": "Risk: R1"}
        self.human("below the closing issue's R1")

    def test_closed_or_untrusted_closing_issue_needs_a_human(self) -> None:
        # A later PR cannot replay the approval of an issue already closed.
        self.r1()
        self.merges("approved", "R1")
        self.issue = {"body": "Risk: R1", "state": "closed"}
        self.human("is not open", "approved", "R1")
        # A `Risk:` line counts only in a body a trusted author wrote.
        self.issue = {"body": "Risk: R1", "author_association": "NONE"}
        self.human("no single parseable `Risk:` line", "approved", "R1")

    def test_coverage_comes_from_the_target_branch(self) -> None:
        self.r1()
        covered = SPEC.replace(
            "Covers: tools/a.py", "Covers: tools/a.py\nCovers: tools/b.py"
        )
        self.change({"docs/specs/cap.md": covered + SECOND, "tools/b.py": "x = 1\n"})
        result = self.human("no spec covers", "approved", "R1")
        self.assertIn("tools/b.py", result["handoff"]["risky_paths"])
        self.assertIn("no spec covers", str(result["human"]))

    def test_target_moved_before_merge_blocks(self) -> None:
        args = merge_check.parser().parse_args(
            self.arguments("approved", "R0", "--merge")
        )
        with patch.object(merge_check, "fetch", side_effect=[self.tip, "c" * 40]):
            result = merge_check.run(args)
        self.assertEqual(result["verdict"], "BLOCK")
        self.assertIn("moved since the verdict", result["block"][0]["reason"])
        self.assertFalse([call for call in self.calls if call[:2] == ("pr", "merge")])

    def test_r1_closes_exactly_one_issue_its_branch_names(self) -> None:
        # One approved issue cannot carry a second, unapproved R1 issue.
        self.r1()
        second = {
            "number": 6,
            "repository": {"name": "fixture", "owner": {"login": "example"}},
        }
        self.pr["closingIssuesReferences"].append(second)
        self.human("closes more than one issue", "approved", "R1")
        # An approved empty delta of another issue cannot authorize this PR.
        self.setUp()
        self.r1()
        self.change({"tools/a.py": "x = 1\n"})
        self.comments = [delta(EMPTY_DELTA), approval(EMPTY_DELTA)]
        self.pr["headRefName"] = "issue-9-abcdef12"
        self.human("claim branch names issue #9", "approved", "R1")
        for branch in ("feat-x", "Issue-5-x"):
            self.pr["headRefName"] = branch
            self.human("needs a claim branch", "approved", "R1")
        self.pr["headRefName"] = f"issue-{ISSUE}-abcdef12"
        self.merges("approved", "R1")

    def test_approved_risk_raises_the_floor(self) -> None:
        self.r1(risk="R2")
        self.human("below the closing issue's R2", "approved", "R1")

    def test_uncovered_changed_path_needs_a_human(self) -> None:
        self.r1()
        self.change({"docs/specs/cap.md": SPEC + SECOND, "tools/b.py": ""})
        result = self.human("no spec covers", "approved", "R1")
        self.assertEqual(result["handoff"]["risky_paths"], ["tools/b.py"])

    def test_r0_changing_a_covered_path_needs_a_human(self) -> None:
        self.change({"tools/a.py": "x = 1\n"})
        self.human("R0 PR changes paths a spec covers")

    def test_r0_modifying_or_removing_a_spec_entry_needs_a_human(self) -> None:
        self.change({"docs/specs/cap.md": SPEC.replace("y follows", "y ends")})
        self.human("R0 PR modifies or removes a spec entry")
        self.change({"docs/specs/cap.md": SPEC.split("#### Scenario", maxsplit=1)[0]})
        self.human("R0 PR modifies or removes a spec entry")

    def test_missing_or_malformed_workflow_on_target_needs_a_human(self) -> None:
        for text in (
            None,
            "- Human-only: tools/gate.py\n",
            "Human-only:\n",
            "Human-only: tools/gate.py\n```\nCoverage-exempt: docs/**\n",
            "",
            "No keys here.\n",
            "```\nHuman-only: tools/gate.py\n```\n",
        ):
            self.setUp()
            self.advance_target({"project/workflow.md": text})
            self.human("missing or malformed")

    def test_workflow_key_lines_in_code_fences_are_ignored(self) -> None:
        fenced = WORKFLOW + "```\n- Human-only: example, malformed\n```\n"
        self.advance_target({"project/workflow.md": fenced})
        self.base = self.tip
        self.change({"docs/guide.md": "x\n"})
        self.merges()

    def test_docs_specs_is_always_coverage_exempt(self) -> None:
        self.advance_target({"project/workflow.md": "Human-only: tools/gate.py\n"})
        self.base = self.tip
        self.change({"docs/specs/cap.md": SPEC + SECOND})
        self.merges()

    def test_r0_covered_check_uses_target_and_head_covers(self) -> None:
        # A PR adding a Covers: line for the path it changes still touches
        # specified behavior; so does one dropping the target's Covers: line.
        moved = SPEC.replace(
            "Covers: tools/a.py", "Covers: tools/a.py\nCovers: tools/b.py"
        )
        self.change({"docs/specs/cap.md": moved, "tools/b.py": ""})
        self.human("R0 PR changes paths a spec covers")
        dropped = SPEC.replace("Covers: tools/a.py", "Covers: tools/z.py")
        self.change({"docs/specs/cap.md": dropped, "tools/a.py": "x = 1\n"})
        self.human("R0 PR changes paths a spec covers")

    def test_changing_covers_lines_needs_a_human_at_any_risk(self) -> None:
        widened = SPEC.replace("Covers: tools/a.py", "Covers: tools/a.py\nCovers: x.py")
        # R0: a spec file is coverage-exempt, but its Covers: lines are not.
        self.change({"docs/specs/cap.md": widened})
        result = self.human("changes `Covers:` lines")
        self.assertIn("docs/specs/cap.md", result["handoff"]["risky_paths"])
        # R1 with an approved delta: Covers: lines are outside the delta hash.
        self.r1()
        self.change({"docs/specs/cap.md": widened + SECOND, "tools/a.py": "x = 1\n"})
        self.human("changes `Covers:` lines", "approved", "R1")
        # Unchanged Covers: lines still merge.
        self.r1()
        self.merges("approved", "R1")

    def test_real_fetch_returns_the_target_tip(self) -> None:
        git(self.root, "config", "uploadpack.allowReachableSHA1InWant", "true")
        with tempfile.TemporaryDirectory() as clone:
            local = Path(clone)
            git(local, "init", "-q")
            url = f"https://github.com/{REPO}.git"
            git(local, "config", f"url.{self.root}.insteadOf", url)
            self.assertEqual(FETCH(local, REPO, "main", self.head), self.tip)
            self.assertNotEqual(self.tip, self.head)
            git(local, "cat-file", "-e", f"{self.head}^{{commit}}")

    def test_handoff_lists_paths_spec_and_findings(self) -> None:
        self.r1()
        self.pr["body"] = body("R2")
        self.issue = {"body": "Risk: R2"}
        self.comments = [delta(DELTA), approval(DELTA, risk="R2")]
        self.change({"docs/specs/cap.md": SPEC + SECOND, "tools/gate.py": "x\n"})
        result = self.human("R2", "approved", "R2", "--finding", "minor: naming")
        handoff = result["handoff"]
        self.assertEqual(handoff["risky_paths"], ["tools/gate.py"])
        self.assertEqual(handoff["approved_spec"]["hash"], digest(DELTA))
        self.assertEqual(handoff["approved_spec"]["delta"], f"{URL}#issuecomment-101")
        self.assertEqual(handoff["review_findings"], ["minor: naming"])

    # Precedence

    def test_block_takes_precedence_over_human_and_human_over_merge(self) -> None:
        self.pr["body"] = body("R2")
        self.issue = {"body": "Risk: R2"}
        result = self.human("R2", "approved", "R2")
        self.assertNotIn("block", result)
        self.pr["isDraft"] = True
        result = self.blocks("draft", "approved", "R2")
        self.assertTrue(result["human"])

    # Ballast's own project/workflow.md

    def ballast(self) -> None:
        """Use Ballast's own project/workflow.md on the target branch."""
        text = (BALLAST / "project/workflow.md").read_text(encoding="utf-8")
        self.advance_target(
            {
                "project/workflow.md": text,
                "docs/specs/cap.md": SPEC.replace(
                    "tools/a.py", "templates/github/pull_request_template.md"
                ),
            }
        )
        self.base = self.tip

    def test_ballast_gate_surfaces_need_a_human(self) -> None:
        text = (BALLAST / "project/workflow.md").read_text(encoding="utf-8")
        globs = re.findall(r"(?m)^Human-only: (\S+)$", text)
        # Every file CI executes or imports, and the gate's own code and text.
        for required in (
            "tools/merge_check.py",
            "tools/spec_check.py",
            "tools/pr_body.py",
            "tools/admission.py",
            "tools/coordinate.py",
            "tools/worker.py",
            "tools/worktree.py",
            "tools/codex.py",
            "tools/spec_approval.py",
            "tools/cli.py",
            "tools/progress.py",
            "tools/qualify.py",
            "tools/dashboard.py",
            "tools/dashboard_assets/app.js",
            "tests/parallel.py",
            ".github/workflows/ci.yml",
            "project/workflow.md",
            "AGENTS.md",
            "CLAUDE.md",
            "docs/issue-workflow.md",
            "docs/pair-review.md",
            "docs/standalone.md",
            "docs/execution.md",
            "docs/model-routing.md",
            "docs/adr/0027-x.md",
            "templates/policies/workflow.md",
            "templates/skills/ballast-test-review/SKILL.md",
        ):
            self.assertTrue(spec_check.matches(required, globs), required)
        self.ballast()
        # One sample path per glob, so deleting any glob from the file fails.
        samples = [g.replace("**", "x/y.md").replace("*", "x") for g in globs]
        extra = ["tests/test_zz.py", "tests/__init__.py", "tools/dashboard.py"]
        for path in [*samples, *extra]:
            with self.subTest(path=path):
                self.change({path: "changed\n"})
                self.human("human-only")

    def test_covered_ballast_r1_pr_merges(self) -> None:
        self.ballast()
        self.change(
            {
                "docs/specs/cap.md": SPEC.replace(
                    "tools/a.py", "templates/github/pull_request_template.md"
                )
                + SECOND,
                "templates/github/pull_request_template.md": "## Summary\n",
            }
        )
        self.pr["body"] = body("R1")
        self.pr["headRefName"] = f"issue-{ISSUE}-abcdef12"
        self.issue = {"body": "Risk: R1"}
        self.comments = [delta(DELTA), approval(DELTA)]
        self.merges("approved", "R1")

    # Merge

    def test_merge_only_on_merge_and_with_explicit_flag(self) -> None:
        args = merge_check.parser().parse_args(self.arguments("approved", "R0"))
        self.assertNotIn("merged", merge_check.run(args))
        self.assertFalse([call for call in self.calls if call[:2] == ("pr", "merge")])
        args.merge = True
        result = merge_check.run(args)
        self.assertTrue(result["merged"])
        merge = next(call for call in self.calls if call[:2] == ("pr", "merge"))
        self.assertEqual(merge[-2:], ("--match-head-commit", self.head))
        note = self.calls[-1]
        self.assertEqual(note[:3], ("pr", "comment", "7"))
        self.assertIn("under ADR-0027", note[-1])
        self.assertIn("not a human approval", note[-1])
        self.assertTrue(result["noted"])
        # A HUMAN verdict never merges, even with --merge.
        self.calls.clear()
        self.pr["state"] = "OPEN"
        self.pr["body"] = body("R2")
        self.assertEqual(merge_check.run(args)["verdict"], "HUMAN")
        self.assertFalse([call for call in self.calls if call[:2] == ("pr", "merge")])

    def test_merge_queue_is_reported_queued_not_merged(self) -> None:
        self.queue = True
        args = merge_check.parser().parse_args(
            self.arguments("approved", "R0", "--merge")
        )
        result = merge_check.run(args)
        self.assertEqual((result["merged"], result["state"]), (False, "queued"))
        self.assertFalse([call for call in self.calls if call[:2] == ("pr", "comment")])
        # A state GitHub does not report is unknown, not queued.
        self.failing = {"--json state": 1}
        result = merge_check.run(args)
        self.assertEqual((result["merged"], result["state"]), (False, "unknown"))

    def test_failing_fetch_blocks_without_reading_fetch_head(self) -> None:
        failed = subprocess.CompletedProcess(["git"], 1, "", "")
        with (
            patch.object(merge_check.subprocess, "run", return_value=failed),
            patch.object(spec_check, "git") as git_call,
            self.assertRaises(admission.FixedReasonError),
        ):
            FETCH(self.root, REPO, "main", self.head)
        git_call.assert_not_called()

    def test_main_reports_spec_errors_as_block(self) -> None:
        argv = ["merge_check", *self.arguments("approved", "R0")]
        out = io.StringIO()
        with (
            patch.object(merge_check, "run", side_effect=spec_check.SpecError("x")),
            patch.object(sys, "argv", argv),
            contextlib.redirect_stdout(out),
        ):
            self.assertEqual(merge_check.main(), 1)
        self.assertEqual(json.loads(out.getvalue())["verdict"], "BLOCK")

    def run_main(self, error: BaseException) -> tuple[int, dict, str]:
        argv = ["merge_check", *self.arguments("approved", "R0")]
        out = io.StringIO()
        with (
            patch.object(merge_check, "run", side_effect=error),
            patch.object(sys, "argv", argv),
            contextlib.redirect_stdout(out),
        ):
            code = merge_check.main()
        return code, json.loads(out.getvalue()), out.getvalue()

    def test_main_prints_a_fixed_reason(self) -> None:
        code, result, _ = self.run_main(admission.FixedReasonError("fixed text"))
        self.assertEqual(code, 1)
        self.assertEqual(
            result, {"verdict": "BLOCK", "block": [{"reason": "fixed text"}]}
        )

    def test_main_prints_only_the_exception_type(self) -> None:
        for error in (
            OSError("/secret/path"),
            AttributeError("/secret/path"),
            TypeError("/secret/path"),
            subprocess.TimeoutExpired("/secret/path", 1),
        ):
            with self.subTest(error=type(error).__name__):
                code, result, text = self.run_main(error)
                self.assertEqual(code, 1)
                self.assertEqual(result["verdict"], "BLOCK")
                self.assertEqual(result["block"], [{"reason": type(error).__name__}])
                self.assertNotIn("/secret/path", text)

    def test_refuses_to_run_inside_an_issue_checkout(self) -> None:
        args = merge_check.parser().parse_args(
            self.arguments("approved", "R0", "--merge")
        )
        with (
            patch.object(worktree, "inside_checkout", return_value=True),
            self.assertRaises(admission.FixedReasonError),
        ):
            merge_check.run(args)
        self.assertEqual(self.calls, [])


if __name__ == "__main__":
    unittest.main()
