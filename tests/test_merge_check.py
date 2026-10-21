"""R0 merge precondition: each refusal, the printed command and the merge."""

from __future__ import annotations

import json
import subprocess
import unittest
from unittest.mock import patch

from tools import admission, merge_check, worktree

HEAD = "a" * 40
BODY = "## Risk\n\n- [x] R0\n- [ ] R1\n- [ ] R2 — link explicit human approval\n"


class MergeCheckTests(unittest.TestCase):
    """A fake gh stands in for GitHub; no host call leaves the process."""

    def setUp(self) -> None:
        self.pr = {
            "number": 7,
            "state": "OPEN",
            "isDraft": False,
            "headRefOid": HEAD,
            "headRefName": "docs/7-typo",
            "author": {"login": "someone", "is_bot": False},
            "body": BODY,
            "changedFiles": 1,
            "files": [{"path": "docs/guide.md"}],
        }
        self.checks: object = [{"bucket": "pass"}, {"bucket": "pass"}]
        self.merge_code = 0
        self.calls: list[tuple[str, ...]] = []
        patcher = patch.object(merge_check, "gh", side_effect=self.fake)
        patcher.start()
        self.addCleanup(patcher.stop)
        # Tests may run inside an issue checkout; the refusal has its own test.
        outside = patch.object(worktree, "inside_checkout", return_value=False)
        outside.start()
        self.addCleanup(outside.stop)

    def fake(self, *args: str) -> subprocess.CompletedProcess:
        self.calls.append(args)
        output, code = "", 0
        if args[:2] == ("pr", "view"):
            output = json.dumps(self.pr)
        elif args[:2] == ("pr", "checks"):
            # gh exits 1 or 8 for failing or pending checks but still prints them.
            output = json.dumps(self.checks)
            code = (
                0
                if self.checks
                and all(item.get("bucket") == "pass" for item in self.checks)
                else 8
            )
        elif args[:2] == ("pr", "merge"):
            code = self.merge_code
        return subprocess.CompletedProcess(["gh", *args], code, output, "")

    def check(self, verdict: str = "approved", risk: str = "R0", *exclude: str) -> dict:
        arguments = ["--repo", "example/fixture", "--pr", "7"]
        arguments += ["--reviewed-head", HEAD, "--verdict", verdict, "--risk", risk]
        for pattern in exclude:
            arguments += ["--exclude", pattern]
        return merge_check.check(merge_check.parser().parse_args(arguments))

    def refuses(self, reason: str, **arguments: str) -> None:
        with self.assertRaises(admission.FixedReasonError) as raised:
            self.check(**arguments)
        self.assertIn(reason, str(raised.exception))
        self.assertFalse([call for call in self.calls if call[:2] == ("pr", "merge")])

    def test_prints_exact_squash_merge_pinned_to_reviewed_head(self) -> None:
        self.assertEqual(
            self.check()["merge"],
            [
                "gh",
                "pr",
                "merge",
                "7",
                "--repo",
                "github.com/example/fixture",
                "--squash",
                "--match-head-commit",
                HEAD,
            ],
        )

    def test_refuses_unapproved_verdict(self) -> None:
        self.refuses("did not approve", verdict="changes_required")

    def test_refuses_risk_the_reviewer_did_not_confirm_as_r0(self) -> None:
        self.refuses("did not confirm R0", risk="R1")

    def test_refuses_short_reviewed_head(self) -> None:
        with self.assertRaises(admission.FixedReasonError):
            merge_check.check(
                merge_check.parser().parse_args(
                    [
                        "--repo",
                        "example/fixture",
                        "--pr",
                        "7",
                        "--reviewed-head",
                        "abc",
                        "--verdict",
                        "approved",
                        "--risk",
                        "R0",
                    ]
                )
            )

    def test_refuses_head_changed_after_review(self) -> None:
        self.pr["headRefOid"] = "b" * 40
        self.refuses("differs from the reviewed head")

    def test_refuses_draft(self) -> None:
        self.pr["isDraft"] = True
        self.refuses("draft")

    def test_refuses_closed(self) -> None:
        self.pr["state"] = "MERGED"
        self.refuses("not open")

    def test_refuses_pr_body_without_only_r0_ticked(self) -> None:
        for body in ("- [ ] R0\n", BODY + "- [x] R2\n", ""):
            self.pr["body"] = body
            self.refuses("tick R0")

    def test_refuses_release_and_dependency_prs(self) -> None:
        self.pr["headRefName"] = "release-please--branches--main"
        self.refuses("Release and dependency")
        self.pr["headRefName"] = "docs/7-typo"
        self.pr["author"] = {"login": "dependabot", "is_bot": True}
        self.refuses("Release and dependency")

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
            self.pr["files"] = [{"path": "docs/guide.md"}, {"path": path}]
            self.pr["changedFiles"] = 2
            self.refuses("workflow, release or dependency")

    def test_refuses_project_excluded_paths(self) -> None:
        self.pr["files"] = [{"path": "deploy/values.yaml"}]
        self.assertIn("merge", self.check())
        with self.assertRaises(admission.FixedReasonError) as raised:
            self.check("approved", "R0", "deploy/*")
        self.assertIn("workflow, release or dependency", str(raised.exception))

    def test_refuses_malformed_file_entries(self) -> None:
        for entry in ({}, {"path": None}, {"path": ""}, {"path": 3}, "docs/x.md"):
            self.pr["files"] = [entry]
            self.refuses("malformed")

    def test_refuses_truncated_file_list(self) -> None:
        self.pr["changedFiles"] = 101
        self.refuses("incomplete")

    def test_refuses_missing_failing_or_pending_required_checks(self) -> None:
        self.checks = []
        self.refuses("No required checks")
        for bucket in ("fail", "pending", "skipping", "cancel"):
            self.checks = [{"bucket": "pass"}, {"bucket": bucket}]
            self.refuses("not green")

    def test_refuses_unreadable_github_response(self) -> None:
        self.pr = "not a pr"  # type: ignore[assignment]
        self.refuses("malformed")

    def test_merge_only_with_explicit_flag(self) -> None:
        args = merge_check.parser().parse_args(
            [
                "--repo",
                "example/fixture",
                "--pr",
                "7",
                "--reviewed-head",
                HEAD,
                "--verdict",
                "approved",
                "--risk",
                "R0",
            ]
        )
        self.assertNotIn("merged", merge_check.run(args))
        self.assertFalse([call for call in self.calls if call[:2] == ("pr", "merge")])
        args.merge = True
        self.assertTrue(merge_check.run(args)["merged"])
        self.assertEqual(
            self.calls[-1][:3] + self.calls[-1][-2:],
            ("pr", "merge", "7", "--match-head-commit", HEAD),
        )

    def test_refuses_to_run_inside_an_issue_checkout(self) -> None:
        args = merge_check.parser().parse_args(
            [
                "--repo",
                "example/fixture",
                "--pr",
                "7",
                "--reviewed-head",
                HEAD,
                "--verdict",
                "approved",
                "--risk",
                "R0",
                "--merge",
            ]
        )
        with (
            patch.object(worktree, "inside_checkout", return_value=True),
            self.assertRaises(admission.FixedReasonError),
        ):
            merge_check.run(args)
        self.assertEqual(self.calls, [])

    def test_merge_refused_by_github_is_reported(self) -> None:
        self.merge_code = 1
        args = merge_check.parser().parse_args(
            [
                "--repo",
                "example/fixture",
                "--pr",
                "7",
                "--reviewed-head",
                HEAD,
                "--verdict",
                "approved",
                "--risk",
                "R0",
                "--merge",
            ]
        )
        with self.assertRaises(admission.FixedReasonError):
            merge_check.run(args)


if __name__ == "__main__":
    unittest.main()
