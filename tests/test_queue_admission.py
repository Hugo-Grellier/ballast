"""Deterministic queue admission, control and recovery checks without agents."""

from __future__ import annotations

import contextlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from tests import test_standalone_execution as standalone
from tools import admission, codex, coordinate, dashboard, worker, worktree

REPO = "example/fixture"


class QueueTests(unittest.TestCase):
    """Exercise the shared lock through the real prepare/worker primitives."""

    # Reuse the scripted backend without re-running the standalone suite here.
    script = standalone.ExecutionTests.script
    run_worker = standalone.ExecutionTests.run_worker

    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        worktree.git(self.repo, "init", "-b", "main")
        worktree.git(self.repo, "config", "user.name", "Fictional Author")
        worktree.git(self.repo, "config", "user.email", "fictional@example.invalid")
        worktree.git(
            self.repo, "remote", "add", "origin", f"https://github.com/{REPO}.git"
        )
        (self.repo / "example.txt").write_text("fictional\n")
        worktree.git(self.repo, "add", ".")
        worktree.git(self.repo, "commit", "-m", "fixture")
        self.base = worktree.git(self.repo, "rev-parse", "HEAD")
        worktree.git(self.repo, "update-ref", "refs/remotes/origin/main", self.base)
        self.state = coordinate.state_directory(self.repo)
        # Fictional GitHub: issues, branch heads and PRs keyed like the API.
        self.issues: dict[int, dict] = {}
        self.heads: dict[str, str] = {}
        self.prs: list[dict] = []
        self.merged: set[int] = set()
        self.missing: set[int] = set()
        self.graphql: list[list[str]] = []
        self.lose_create_response = False
        native = worktree.command

        def hosting(argv: list[str], cwd: Path) -> str:
            if argv[0] != "gh":
                return native(argv, cwd)
            return json.dumps(self.host(argv))

        patcher = patch.object(worktree, "command", side_effect=hosting)
        patcher.start()
        self.addCleanup(patcher.stop)
        environment = patch.dict(
            os.environ,
            {**dict.fromkeys(codex.CI_MARKERS, ""), "BALLAST_COORDINATOR": "lead"},
        )
        environment.start()
        self.addCleanup(environment.stop)
        self.task = self.root / "task.txt"
        self.task.write_text("Inspect the fictional fixture and report.")

    def host(self, argv: list[str]) -> object:
        """Answer the few GitHub calls the helpers make."""
        if argv[1:3] == ["pr", "create"]:
            branch = argv[argv.index("--head") + 1]
            self.prs.append(
                {
                    "number": 50 + len(self.prs),
                    "html_url": f"https://github.com/{REPO}/pull/{50 + len(self.prs)}",
                    "base": {"ref": argv[argv.index("--base") + 1]},
                    "head": {
                        "ref": branch,
                        "sha": self.heads[branch],
                        "repo": {"full_name": REPO},
                    },
                }
            )
            if self.lose_create_response:
                worktree.fail("Fictional lost response")
            return {}
        if "graphql" in argv:
            self.graphql.append(argv)
            query = next(a for a in argv if a.startswith("query="))
            numbers = [int(n) for n in re.findall(r"i\d+:issue\(number:(\d+)\)", query)]
            if self.missing.intersection(numbers):
                # The real gh exits non-zero when any alias is unresolved.
                worktree.fail("Fictional unresolved issue")
            return {"data": {"repository": {f"i{n}": self.issue(n) for n in numbers}}}
        path = argv[-1]
        if "/git/ref/heads/" in path:
            return {
                "object": {"sha": self.heads.get(path.rsplit("/", 1)[1], self.base)}
            }
        if "/pulls?" in path:
            branch = path.rsplit(":", 1)[1]
            return [pr for pr in self.prs if pr["head"]["ref"] == branch]
        if "/pulls/" in path:
            return {"merged": int(path.rsplit("/", 1)[1]) in self.merged}
        number = int(path.rsplit("/", 1)[1])
        return {"number": number, "state": "open", "body": "Fictional leaf"}

    def issue(self, number: int) -> dict:
        """Default: an open leaf with no prerequisites."""
        value = {
            "number": number,
            "state": "OPEN",
            "body": "Fictional acceptance",
            "subIssuesSummary": {"total": 0},
            "blockedBy": {"pageInfo": {"hasNextPage": False}, "nodes": []},
            "closedByPullRequestsReferences": {"nodes": []},
        }
        value.update(self.issues.get(number, {}))
        return value

    def queue(self, selected: list[int], **limits: int) -> dict:
        spec = admission.QueueSpec(
            REPO, selected, {**admission.DEFAULTS, **limits}, "lead", "rev-1"
        )
        return admission.create(self.state, spec)

    def prepare(self, issue: int) -> Path:
        return worktree.prepare(self.repo, REPO, issue, "main")

    def worker_on(self, claim: Path, edit=None) -> dict:  # noqa: ANN001
        """Run the scripted backend, optionally editing its transcript."""
        self.claim = claim
        self.cwd = Path(json.loads(claim.read_text())["checkout"])
        messages = self.script()
        return self.run_worker(edit(messages) if edit else messages)

    def test_independent_issues_get_separate_worktrees_within_issue_cap(self) -> None:
        self.queue([1, 2, 3], issues=2)
        first, second = self.prepare(1), self.prepare(2)
        checkouts = {json.loads(p.read_text())["checkout"] for p in (first, second)}
        self.assertEqual(len(checkouts), 2)
        with self.assertRaisesRegex(admission.AdmissionError, "issue or human-review"):
            self.prepare(3)
        self.assertFalse((self.state / "issue-3.json").exists())

    def test_two_coordinators_racing_get_one_claim(self) -> None:
        self.queue([4], issues=2)
        outcomes: list[str] = []

        def contend() -> None:
            try:
                self.prepare(4)
                outcomes.append("claimed")
            except RuntimeError:
                outcomes.append("blocked")

        threads = [threading.Thread(target=contend) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(sorted(outcomes), ["blocked", "claimed"])

    def test_foreign_coordinator_and_outside_issue_are_rejected(self) -> None:
        self.queue([5])
        with self.assertRaisesRegex(admission.AdmissionError, "outside"):
            self.prepare(6)
        with (
            patch.dict(os.environ, {"BALLAST_COORDINATOR": "other"}),
            self.assertRaisesRegex(admission.AdmissionError, "coordinator"),
        ):
            self.prepare(5)

    def test_unknown_claim_and_worker_consume_capacity(self) -> None:
        legacy = self.prepare(7)  # Created before queue control: unknown owner.
        self.queue([7, 8], issues=1)
        with self.assertRaisesRegex(admission.AdmissionError, "issue or human"):
            self.prepare(8)
        legacy.with_suffix(".worker").write_text("unreconciled")
        self.assertEqual(admission.capacity(self.state)["workers"], 1)

    def test_review_counts_in_worker_budget_and_attempts_do_not_reset(self) -> None:
        self.queue([9], workers=2, attempts=1)
        claim = self.prepare(9)
        result = self.worker_on(claim)
        self.assertEqual(result["status"], "completed")
        with self.assertRaisesRegex(admission.AdmissionError, "attempt limit"):
            self.worker_on(claim)
        record = json.loads(claim.read_text())
        self.assertEqual(record["worker_attempts"], {"implement": 1})
        # An unknown worker elsewhere plus this one fill the shared budget.
        (self.state / "issue-99.worker").write_text("unknown")
        (self.state / "issue-98.worker").write_text("unknown")
        with self.assertRaisesRegex(admission.AdmissionError, "Total worker"):
            admission.reserve_worker(claim, "review-1", "review")

    def test_pause_blocks_admission_and_turns_without_inferring_stop(self) -> None:
        self.queue([10, 11], issues=2)
        claim = self.prepare(10)
        admission.control(self.state, "paused", "operator pause")
        with self.assertRaisesRegex(admission.AdmissionError, "paused"):
            self.prepare(11)
        with self.assertRaisesRegex(admission.AdmissionError, "paused"):
            self.worker_on(claim)
        self.assertFalse(claim.with_suffix(".worker").exists())
        admission.control(self.state, "running", "operator resume")
        self.assertEqual(self.worker_on(claim)["status"], "completed")

    def test_cancel_interrupts_live_worker_and_releases_on_terminal(self) -> None:
        self.queue([12])
        claim = self.prepare(12)
        tail = [
            {"id": "qualify-5", "result": {"turn": {"id": "fixture-turn"}}},
            {"id": "worker-interrupt", "result": {}},
            {
                "method": "turn/completed",
                "params": {
                    "threadId": "fixture-thread",
                    "turn": {"id": "fixture-turn", "status": "interrupted"},
                },
            },
        ]
        with patch.object(admission, "cancelled", return_value=True):
            result = self.worker_on(claim, lambda m: m[:4] + tail)
        self.assertEqual(result["status"], "cancelled")
        self.assertFalse(claim.with_suffix(".worker").exists())

    def test_cancel_without_terminal_evidence_stays_unknown(self) -> None:
        self.queue([13])
        claim = self.prepare(13)
        tail = [
            {"id": "qualify-5", "result": {"turn": {"id": "fixture-turn"}}},
            {"id": "worker-interrupt", "result": {}},
        ]
        with (
            patch.object(admission, "cancelled", return_value=True),
            self.assertRaises(codex.QualificationError),
        ):
            self.worker_on(claim, lambda m: m[:4] + tail)
        self.assertTrue(claim.with_suffix(".worker").exists())

    @staticmethod
    def quota(resets: int | None):  # noqa: ANN205
        window = {"usedPercent": 100, "resetsAt": resets}
        return lambda m: (
            [
                *m[:4],
                {"method": "account/rateLimits/updated", "params": {"rateLimits": {}}},
                {
                    "method": "account/rateLimits/updated",
                    "params": {"rateLimits": {"primary": window, "planType": "plus"}},
                },
                {
                    "method": "turn/completed",
                    "params": {
                        "threadId": "fixture-thread",
                        "turn": {
                            "id": "fixture-turn",
                            "status": "failed",
                            "error": {
                                "message": "fictional",
                                "codexErrorInfo": "usageLimitExceeded",
                            },
                        },
                    },
                },
                {"id": "qualify-5", "result": {"turn": {"id": "fixture-turn"}}},
            ]
        )

    def test_quota_with_known_window_pauses_until_reset(self) -> None:
        self.queue([14, 15], issues=2)
        claim = self.prepare(14)
        resets = int(time.time()) + 600
        result = self.worker_on(claim, self.quota(resets))
        self.assertEqual((result["status"], result["retry_at"]), ("quota", resets))
        self.assertFalse(claim.with_suffix(".worker").exists())
        self.assertNotIn("plus", (self.state / "queue.json").read_text())
        with self.assertRaisesRegex(admission.AdmissionError, "quota"):
            self.prepare(15)
        with patch.object(admission.time, "time", return_value=resets + 1):
            self.prepare(15)

    def test_quota_without_window_needs_explicit_resume(self) -> None:
        self.queue([16, 17], issues=2)
        self.worker_on(self.prepare(16), self.quota(None))
        with patch.object(admission.time, "time", return_value=time.time() + 10**6):
            policy = admission.policy(self.state)
            self.assertIsNone(policy["quota"]["retry_at"])
        admission.control(self.state, "running", "operator checked quota")
        self.prepare(17)

    def test_selection_reports_blockers_and_bounds_eligible_work(self) -> None:
        self.issues = {
            20: {"body": "Blocked by: #21"},
            21: {"body": "Blocked by: #20"},
            22: {"body": "Blocked by: other/repo#1"},
            23: {
                "blockedBy": {
                    "pageInfo": {"hasNextPage": False},
                    "nodes": [self.node(30, "CLOSED")],
                }
            },
            30: {"state": "CLOSED"},  # Closed without a merged change.
            24: {"body": "Blocked by: #31"},
            31: {
                "state": "CLOSED",
                "closedByPullRequestsReferences": {"nodes": [{"merged": True}]},
            },
        }
        self.queue([20, 21, 22, 23, 24, 25], issues=1)
        selected = coordinate.select(self.repo)
        self.assertEqual(selected["eligible"], [24])
        self.assertEqual(selected["waiting_for_capacity"], [25])
        blocked = selected["blocked"]
        self.assertIn("dependency cycle", blocked["20"])
        self.assertIn("dependency cycle", blocked["21"])
        self.assertIn("unknown cross-repository", blocked["22"][0])
        self.assertIn("no merged change", blocked["23"][0])

    @staticmethod
    def node(number: int, state: str) -> dict:
        return {"number": number, "state": state, "repository": {"nameWithOwner": REPO}}

    def publish_ready(self, issue: int) -> Path:
        claim = self.prepare(issue)
        record = json.loads(claim.read_text())
        self.heads[record["branch"]] = self.base
        body = self.root / "body.md"
        body.write_text("Fictional PR body")
        return claim

    def test_lost_publication_response_recovers_one_pr(self) -> None:
        self.queue([40], issues=1, backlog=1)
        claim = self.publish_ready(40)
        self.lose_create_response = True
        record = coordinate.publish(claim, "Fictional", self.root / "body.md")
        self.assertEqual(len(self.prs), 1)
        self.assertEqual(record["pr"]["number"], 50)
        # Restart: publication reuses the existing PR instead of creating another.
        coordinate.publish(claim, "Fictional", self.root / "body.md")
        self.assertEqual(len(self.prs), 1)

    def test_stale_or_duplicate_prs_block_publication(self) -> None:
        self.queue([41])
        claim = self.publish_ready(41)
        branch = json.loads(claim.read_text())["branch"]
        self.heads[branch] = "advanced"
        with self.assertRaisesRegex(RuntimeError, "Push the reviewed head"):
            coordinate.publish(claim, "Fictional", self.root / "body.md")
        self.heads[branch] = self.base
        coordinate.publish(claim, "Fictional", self.root / "body.md")
        self.prs.append(dict(self.prs[0], number=99))
        with self.assertRaisesRegex(RuntimeError, "Several PRs"):
            coordinate.publish(claim, "Fictional", self.root / "body.md")

    def test_backlog_holds_until_github_confirms_merge(self) -> None:
        self.queue([42, 43], issues=2, backlog=1)
        claim = self.publish_ready(42)
        coordinate.publish(claim, "Fictional", self.root / "body.md")
        # A still-active draft already occupies human-review backlog.
        self.assertEqual(admission.capacity(self.state)["backlog"], 1)
        coordinate.settle(claim, "pr_wait", "ready for human review")
        with self.assertRaisesRegex(admission.AdmissionError, "backlog"):
            self.prepare(43)
        with self.assertRaisesRegex(RuntimeError, "merged"):
            coordinate.settle(claim, "merged", "operator says merged")
        self.merged.add(50)
        coordinate.settle(claim, "merged", "GitHub merge confirmed")
        self.prepare(43)
        self.assertTrue(worktree.validate(claim))  # No checkout cleanup.

    def test_active_transfer_needs_stop_evidence(self) -> None:
        self.queue([44])
        claim = self.prepare(44)
        with (
            patch.dict(os.environ, {"BALLAST_COORDINATOR": "successor"}),
            self.assertRaisesRegex(admission.AdmissionError, "stop evidence"),
        ):
            admission.settle(claim, "active", "taking over")
        admission.settle(claim, "stopped", "lead handed off")
        with patch.dict(os.environ, {"BALLAST_COORDINATOR": "successor"}):
            record = admission.settle(claim, "active", "accepted handoff")
        self.assertEqual(record["coordinator"], "successor")

    def test_observation_derives_history_and_reports_unavailable(self) -> None:
        self.queue([45], issues=1, attempts=2)
        claim = self.prepare(45)

        def tokens(messages: list[dict]) -> list[dict]:
            messages.insert(
                4,
                {
                    "method": "thread/tokenUsage/updated",
                    "params": {
                        "threadId": "fixture-thread",
                        "turnId": "fixture-turn",
                        "tokenUsage": {"total": {"totalTokens": 12}, "last": {}},
                    },
                },
            )
            return messages

        self.worker_on(claim, tokens)
        self.worker_on(claim)
        view = coordinate.observe(self.state)
        (item,) = view["issues"]
        self.assertEqual(item["rework"], 1)
        tokens = [worker["tokens"] for worker in item["workers"]]
        self.assertCountEqual(tokens, [{"totalTokens": 12}, "unavailable"])
        self.assertIn("admitted", [h["event"] for h in item["history"]])
        self.assertEqual(
            set(item["phases"]),
            {"implement", "review", "worker_setup", "human_review_wait", "coordinator"},
        )
        self.assertEqual(view["summary"]["throughput"]["published"], 0)

    def test_phase_waiting_and_regressions_from_fixed_history(self) -> None:
        def at(offset: int) -> str:
            return f"2026-01-01T00:{offset // 60:02d}:{offset % 60:02d}+00:00"

        history = [
            {"at": at(0), "event": "admitted"},
            {"at": at(100), "event": "pr_wait", "evidence": "review approved"},
            {"at": at(160), "event": "active", "evidence": "human asked rework"},
            {"at": at(200), "event": "pr_wait", "evidence": "re-review approved"},
            {"at": at(260), "event": "merged", "evidence": "GitHub merged"},
        ]
        workers = [
            {"attempt": "a", "role": "implement", "setup": 2.0, "running": 30.0},
            {"attempt": "a", "role": "review", "setup": 1.0, "running": 10.0},
            {"attempt": "other", "role": "implement", "setup": 9.0, "running": 99.0},
        ]
        view = coordinate.issue_view(
            {"attempt": "a", "activity": "merged", "history": history},
            workers,
            at(3000),
        )
        self.assertEqual(view["elapsed"], 260)
        self.assertEqual(
            view["phases"],
            {
                "implement": 30.0,
                "review": 10.0,
                "worker_setup": 3.0,
                "human_review_wait": 120.0,
                "coordinator": 97.0,
            },
        )
        self.assertEqual(view["reopened"], 1)
        self.assertEqual(len(view["evidence"]), 4)
        opened = datetime.fromisoformat(at(50)).timestamp()
        controls = [
            {"at": at(10), "event": "paused"},
            {"at": at(40), "event": "running"},
            {"at": at(50), "event": "quota_paused", "retry_at": opened + 20},
        ]
        paused = {"paused", "cancelled", "quota_paused"}
        self.assertEqual(coordinate.waited(controls, paused, {"running"}, at(900)), 50)

    def test_corrupt_policy_fails_closed(self) -> None:
        self.queue([46])
        (self.state / "queue.json").write_text('{"schema": 1}')
        with self.assertRaisesRegex(admission.AdmissionError, "malformed"):
            self.prepare(46)

    def test_unknown_worker_is_released_only_with_evidence(self) -> None:
        self.queue([60])
        claim = self.prepare(60)

        def failed(messages: list[dict]) -> list[dict]:
            messages[5]["params"]["turn"]["status"] = "failed"
            return messages

        with self.assertRaises(codex.QualificationError):
            self.worker_on(claim, failed)
        held = claim.with_suffix(".worker").read_text()
        with self.assertRaisesRegex(admission.AdmissionError, "No such worker"):
            admission.release(claim, "other", "checked process table")
        admission.release(claim, held, "backend thread shows failed turn")
        self.assertFalse(claim.with_suffix(".worker").exists())
        released = self.state / "workers" / held / "result.json"
        self.assertEqual(json.loads(released.read_text())["status"], "released")
        self.assertEqual(self.worker_on(claim)["status"], "completed")

    def test_interrupted_preparation_and_legacy_claim_are_recovered(self) -> None:
        legacy = self.prepare(61)
        worktree.mark(legacy, "preparing")  # Killed around `git worktree add`.
        with self.assertRaisesRegex(RuntimeError, "not ready"):
            worktree.validate(legacy)
        self.queue([61])
        with self.assertRaisesRegex(admission.AdmissionError, "reconciliation"):
            admission.reserve_worker(legacy, "fictional", "implement")
        legacy.with_suffix(".worker").write_text("residual")
        with self.assertRaisesRegex(admission.AdmissionError, "Release"):
            coordinate.recover(self.repo, legacy, "checkout inspected")
        legacy.with_suffix(".worker").unlink()
        record = coordinate.recover(self.repo, legacy, "checkout inspected")
        self.assertEqual((record["status"], record["activity"]), ("ready", "active"))
        self.assertEqual(self.worker_on(legacy)["status"], "completed")

    def test_bound_claim_fails_closed_without_its_policy(self) -> None:
        self.queue([62])
        claim = self.prepare(62)
        (self.state / "queue.json").unlink()
        with self.assertRaisesRegex(admission.AdmissionError, "policy is missing"):
            self.worker_on(claim)
        with self.assertRaisesRegex(admission.AdmissionError, "policy is missing"):
            admission.settle(claim, "stopped", "operator stop")

    def test_transitions_recheck_issue_cap(self) -> None:
        self.queue([63, 64], issues=1, backlog=2)
        first = self.prepare(63)
        admission.settle(first, "pr_wait", "awaiting review")
        self.prepare(64)
        with self.assertRaisesRegex(admission.AdmissionError, "issue limit"):
            admission.settle(first, "active", "review asked for rework")
        with self.assertRaisesRegex(admission.AdmissionError, "transition"):
            admission.settle(first, "unknown", "not a valid move")

    def test_qualification_failure_spends_no_attempt(self) -> None:
        self.queue([65], attempts=1)
        claim = self.prepare(65)
        with self.assertRaises(codex.QualificationError):
            self.worker_on(claim, lambda m: [m[0], response_account("apiKey"), *m[2:]])
        self.assertNotIn("worker_attempts", json.loads(claim.read_text()))
        self.assertEqual(self.worker_on(claim)["status"], "completed")

    def test_selection_isolates_unreadable_and_written_prerequisites(self) -> None:
        self.missing = {9999}
        self.issues = {
            70: {"body": "Blocked by #9999"},
            71: {
                "body": "- **Blocked by** https://github.com/example/fixture/issues/72"
            },
            72: {"state": "CLOSED"},
            73: {"blockedBy": {"pageInfo": {"hasNextPage": True}, "nodes": []}},
            # Oversized untrusted input blocks instead of costing regex time.
            75: {"body": "Blocked by " + "a" * 5000},
        }
        self.queue([70, 71, 73, 74, 75], issues=2)
        selected = coordinate.select(self.repo)
        self.assertEqual(selected["eligible"], [74])
        self.assertEqual(selected["blocked"]["70"], ["unknown prerequisite #9999"])
        self.assertIn("no merged change", selected["blocked"]["71"][0])
        self.assertIn("could not be evaluated", selected["blocked"]["73"][0])
        self.assertIn("could not be evaluated", selected["blocked"]["75"][0])
        admission.control(self.state, "paused", "operator pause")
        paused = coordinate.select(self.repo)
        self.assertEqual(
            (paused["eligible"], paused["waiting_for_capacity"]), ([], [74])
        )

    def test_selection_batches_queue_and_prerequisite_reads(self) -> None:
        self.issues = {81: {"body": "Blocked by #90"}, 82: {"body": "Blocked by #91"}}
        self.queue([80, 81, 82])
        coordinate.select(self.repo)
        self.assertEqual(len(self.graphql), 2)  # queue issues, then prerequisites

    def test_malformed_node_isolates_only_that_issue(self) -> None:
        self.issues = {91: {"number": 0}}
        self.queue([90, 91])
        selected = coordinate.select(self.repo)
        self.assertEqual(selected["eligible"], [90])
        self.assertEqual(selected["blocked"], {"91": ["issue could not be read"]})

    def test_closed_or_forkless_prs_block_cleanly(self) -> None:
        self.queue([75])
        claim = self.publish_ready(75)
        coordinate.publish(claim, "Fictional", self.root / "body.md")
        self.prs[0]["state"] = "closed"
        with self.assertRaisesRegex(RuntimeError, "closed PR"):
            coordinate.publish(claim, "Fictional", self.root / "body.md")
        self.prs[0]["head"]["repo"] = None  # Source fork deleted.
        with self.assertRaisesRegex(RuntimeError, "another base"):
            coordinate.publish(claim, "Fictional", self.root / "body.md")

    def test_preparation_killed_before_checkout_is_recreated(self) -> None:
        self.queue([66])
        native = worktree.git

        def killed(cwd: Path, *args: str, **kwargs: object) -> str:
            if args[0] == "worktree":
                raise KeyboardInterrupt  # Process died before the checkout.
            return native(cwd, *args, **kwargs)

        with (
            patch.object(worktree, "git", side_effect=killed),
            self.assertRaises(KeyboardInterrupt),
        ):
            self.prepare(66)
        claim = self.state / "issue-66.json"
        self.assertEqual(json.loads(claim.read_text())["status"], "preparing")
        record = coordinate.recover(self.repo, claim, "process confirmed gone")
        self.assertEqual(record["status"], "ready")
        self.assertEqual(self.worker_on(claim)["status"], "completed")

    def test_legacy_claim_cannot_be_taken_over_without_stop(self) -> None:
        legacy = self.prepare(67)
        self.queue([67])
        with self.assertRaisesRegex(admission.AdmissionError, "transition"):
            admission.settle(legacy, "active", "taking it")
        admission.settle(legacy, "stopped", "original session confirmed stopped")

    def test_publish_ignores_worker_written_gitfile(self) -> None:
        self.queue([77])
        claim = self.publish_ready(77)
        checkout = Path(json.loads(claim.read_text())["checkout"])
        # A worker-written gitfile points at a repository with another HEAD.
        evil = self.root / "evil.git"
        worktree.git(self.repo, "commit", "--allow-empty", "-m", "elsewhere")
        shutil.copytree(self.repo / ".git", evil)
        worktree.git(self.repo, "reset", "--hard", self.base)
        (checkout / ".git").write_text(f"gitdir: {evil}\n")
        record = coordinate.publish(claim, "Fictional", self.root / "body.md")
        self.assertEqual(record["pr"]["head"], self.base)

    def test_recovery_and_cli_refuse_untrusted_git_inputs(self) -> None:
        self.queue([78])
        claim = self.prepare(78)
        worktree.mark(claim, "preparing")
        record = json.loads(claim.read_text())
        record["branch"] = "--upload-pack=touch /tmp/fictional"
        claim.write_text(json.dumps(record))
        with self.assertRaisesRegex(RuntimeError, "malformed"):
            coordinate.recover(self.repo, claim, "inspected")
        issue_checkout = Path(record["checkout"])
        args = coordinate.parser().parse_args(["--cwd", str(issue_checkout), "status"])
        with self.assertRaisesRegex(RuntimeError, "project checkout"):
            coordinate.run(args)

    def test_surviving_sandbox_process_keeps_worker_unknown(self) -> None:
        self.queue([79])
        claim = self.prepare(79)
        with (
            patch.object(worker, "survivors", return_value=[4242]),
            patch.object(worker, "INTERRUPT_SECONDS", 0),
            self.assertRaisesRegex(codex.QualificationError, "still run"),
        ):
            self.worker_on(claim)
        self.assertTrue(claim.with_suffix(".worker").exists())

    @unittest.skipUnless(Path("/proc/self/cwd").exists(), "Linux /proc required")
    def test_survivors_finds_a_process_inside_the_checkout(self) -> None:
        checkout = Path(json.loads(self.prepare(80).read_text())["checkout"])
        process = subprocess.Popen(["sleep", "30"], cwd=checkout / "")  # noqa: S607
        self.addCleanup(process.wait)
        self.addCleanup(process.kill)
        time.sleep(0.1)
        self.assertIn(process.pid, worker.survivors(checkout))
        self.assertNotIn(process.pid, worker.survivors(self.root / "elsewhere"))

    @unittest.skipUnless(Path("/proc/self/cwd").exists(), "Linux /proc required")
    def test_unrelated_process_in_checkout_is_named_and_output_kept(self) -> None:
        # The #193 case: a coordinator process, not the worker, sits in the checkout.
        claim = self.prepare(81)
        checkout = Path(json.loads(claim.read_text())["checkout"])
        process = subprocess.Popen(["sleep", "30"], cwd=checkout)  # noqa: S607
        self.addCleanup(process.wait)
        self.addCleanup(process.kill)
        with (
            patch.object(worker, "INTERRUPT_SECONDS", 0),
            self.assertRaisesRegex(
                codex.QualificationError, rf"unknown: .*\b{process.pid} \(sleep\)"
            ),
        ):
            self.worker_on(claim)
        (directory,) = (claim.parent / "workers").iterdir()
        result = json.loads((directory / "result.json").read_text())
        self.assertEqual((result["status"], result["turn"]), ("unknown", "completed"))
        self.assertIn(str(process.pid), result["reason"])
        self.assertTrue((directory / "output.txt").read_text())
        self.assertTrue(claim.with_suffix(".worker").exists())

    def test_client_shutdown_failure_keeps_completed_output(self) -> None:
        claim = self.prepare(83)
        with (
            patch.object(
                worker.WorkerServer,
                "close",
                side_effect=codex.QualificationError("Fictional shutdown failure"),
            ),
            self.assertRaisesRegex(codex.QualificationError, "shutdown"),
        ):
            self.worker_on(claim)
        (directory,) = (claim.parent / "workers").iterdir()
        result = json.loads((directory / "result.json").read_text())
        self.assertEqual((result["status"], result["turn"]), ("unknown", "completed"))
        self.assertTrue((directory / "output.txt").read_text())
        self.assertTrue(claim.with_suffix(".worker").exists())

    @unittest.skipUnless(Path("/proc/self/comm").exists(), "Linux /proc required")
    def test_non_utf8_process_name_is_still_named(self) -> None:
        code = "import time; open('/proc/self/comm', 'wb').write(b'\\xffbad')"
        process = subprocess.Popen([sys.executable, "-c", f"{code}; time.sleep(30)"])  # noqa: S603
        self.addCleanup(process.wait)
        self.addCleanup(process.kill)
        time.sleep(0.3)
        self.assertRegex(worker.describe([process.pid]), rf"^{process.pid} \(.bad\)$")

    def test_survivor_names_are_bounded(self) -> None:
        self.assertEqual(worker.describe([2**31]), f"{2**31} (?)")
        many = worker.describe([2**31] * (worker.MAX_NAMED + 2))
        self.assertTrue(many.endswith(", and 2 more"))

    def test_helpers_refuse_to_start_inside_an_issue_checkout(self) -> None:
        self.queue([82])
        checkout = Path(json.loads(self.prepare(82).read_text())["checkout"])
        args = coordinate.parser().parse_args(["--cwd", str(self.repo), "status"])
        argv = ["dashboard", "--cwd", str(self.repo), "--repo", REPO]
        with contextlib.chdir(checkout):
            with self.assertRaisesRegex(RuntimeError, "project checkout"):
                coordinate.run(args)
            with self.assertRaisesRegex(codex.QualificationError, "outside issue"):
                worker.check_launch("fixture-model", "low", 2)
            with (
                patch.object(sys, "argv", [*argv, "--coordinator", "lead"]),
                patch.object(dashboard.Server, "serve_forever") as serve,
                contextlib.redirect_stderr(io.StringIO()) as error,
            ):
                self.assertEqual(dashboard.main(), 1)
            serve.assert_not_called()
            self.assertIn("outside issue checkouts", error.getvalue())
        coordinate.run(args)  # The project checkout itself is fine.

    def test_timing_edge_cases_from_review(self) -> None:
        def at(offset: int) -> str:
            return f"2026-01-01T00:{offset // 60:02d}:{offset % 60:02d}+00:00"

        changes = coordinate.CHANGES
        # A re-publish inside review waiting does not end the wait.
        history = [
            {"at": at(10), "event": "pr_wait"},
            {"at": at(20), "event": "published"},
            {"at": at(100), "event": "merged"},
        ]
        self.assertEqual(coordinate.waited(history, {"pr_wait"}, changes, at(500)), 90)
        # Repeated pause controls count once.
        pauses = [
            {"at": at(10), "event": "paused"},
            {"at": at(20), "event": "paused"},
            {"at": at(100), "event": "running"},
        ]
        self.assertEqual(
            coordinate.waited(pauses, {"paused"}, {"running"}, at(500)), 90
        )
        # A stopped then recovered issue keeps its clock; recovery and an
        # intervening milestone still count as a reopening.
        history = [
            {"at": at(0), "event": "admitted"},
            {"at": at(10), "event": "pr_wait"},
            {"at": at(15), "event": "published"},
            {"at": at(20), "event": "recovered"},
            {"at": at(30), "event": "stopped"},
            {"at": at(40), "event": "active"},
            {"at": at(100), "event": "merged"},
            {"at": at(300), "event": "published"},
        ]
        view = coordinate.issue_view(
            {"attempt": "a", "activity": "merged", "history": history}, [], at(900)
        )
        self.assertEqual((view["elapsed"], view["reopened"]), (100, 1))

    def test_live_worker_runtime_counts_until_now(self) -> None:
        directory = self.root / "workers" / "live"
        directory.mkdir(parents=True)
        (directory / "events.jsonl").write_text(
            '{"at": "2026-01-01T00:00:00+00:00", "event": "created"}\n'
            '{"at": "2026-01-01T00:00:01+00:00", "event": "task_accepted"}\n'
        )
        view = coordinate.worker_view(directory, "2026-01-01T00:10:01+00:00")
        self.assertEqual((view["setup"], view["running"]), (1, 600))
        self.assertEqual(view["status"], "unrecorded")
        # A worker that ended unknown may still run: count until now.
        (directory / "events.jsonl").write_text(
            '{"at": "2026-01-01T00:00:00+00:00", "event": "created"}\n'
            '{"at": "2026-01-01T00:00:01+00:00", "event": "task_accepted"}\n'
            '{"at": "2026-01-01T00:00:31+00:00", "event": "unknown"}\n'
        )
        view = coordinate.worker_view(directory, "2026-01-01T00:10:01+00:00")
        self.assertEqual(view["running"], 600)

    def test_unreadable_same_user_process_is_a_survivor(self) -> None:
        native = Path.readlink

        def hidden(path: Path) -> Path:
            if path.parent.name == str(os.getpid()):
                raise PermissionError(path)
            return native(path)

        with patch.object(Path, "readlink", hidden):
            self.assertIn(os.getpid(), worker.survivors(self.root / "elsewhere"))


def response_account(kind: str) -> dict:
    """Account receipt in the scripted transcript's second position."""
    return {"id": "qualify-2", "result": {"account": {"type": kind}}}


if __name__ == "__main__":
    unittest.main()
