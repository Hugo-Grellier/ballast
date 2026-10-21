"""Coordinator-executed records: lifecycle, refusals, projection and publication."""

from __future__ import annotations

import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from tests import test_queue_admission as queue_tests
from tools import admission, coordinate, dashboard, worktree

REPO = queue_tests.REPO
ROUTE = ("anthropic", "fixture-model", "high")


class CoordinatorExecutionTests(unittest.TestCase):
    """Reuse only fixture helpers, without inheriting the queue test cases."""

    setUp = queue_tests.QueueTests.setUp
    host = queue_tests.QueueTests.host
    issue = queue_tests.QueueTests.issue
    queue = queue_tests.QueueTests.queue
    prepare = queue_tests.QueueTests.prepare
    worker_on = queue_tests.QueueTests.worker_on
    script = queue_tests.QueueTests.script
    run_worker = queue_tests.QueueTests.run_worker
    publish_ready = queue_tests.QueueTests.publish_ready

    def claimed(self, issue: int) -> Path:
        self.policy = self.queue([issue])
        claim = self.prepare(issue)
        self.checkout = Path(admission.read(claim)["checkout"])
        return claim

    def commit(self, text: str) -> None:
        (self.checkout / "example.txt").write_text(text)
        worktree.git(self.checkout, "commit", "-am", text)

    def events(self, record: dict) -> list[str]:
        log = self.state / "workers" / record["worker"] / "events.jsonl"
        return [json.loads(line)["event"] for line in log.read_text().splitlines()]

    def test_implementation_lifecycle_takes_no_worker_capacity_or_lock(self) -> None:
        claim = self.claimed(5)
        started = coordinate.start_execution(claim, "implement", ROUTE)
        self.assertEqual(
            {k: started[k] for k in ("executor", "route_verified", "status", "role")},
            {
                "executor": "coordinator",
                "route_verified": False,
                "status": "running",
                "role": "implement",
            },
        )
        self.assertEqual(
            started["requested"],
            dict(zip(("provider", "model", "effort"), ROUTE, strict=True)),
        )
        self.assertNotIn("observed", started)
        self.assertFalse(claim.with_suffix(".worker").exists())
        self.assertEqual(admission.capacity(self.state)["workers"], 0)
        self.assertNotIn("worker_attempts", admission.read(claim))
        # One writer: neither a second execution nor a worker may start meanwhile.
        with self.assertRaisesRegex(RuntimeError, "Another execution"):
            coordinate.start_execution(claim, "review", ROUTE)
        with self.assertRaisesRegex(RuntimeError, "coordinator execution holds"):
            admission.reserve_worker(claim, "f" * 32, "implement")
        (item,) = coordinate.observe(self.state)["issues"]
        (view,) = item["workers"]
        self.assertEqual(view["status"], "running")
        self.assertEqual(
            coordinate.observe(self.state)["summary"]["unknown_workers"], 0
        )
        self.commit("implemented\n")
        finished = coordinate.finish_execution(claim, started["worker"], "completed")
        self.assertNotEqual(finished["head_after"], finished["head_before"])
        self.assertEqual(
            self.events(finished), ["created", "task_accepted", "completed"]
        )
        with self.assertRaisesRegex(RuntimeError, "No open coordinator execution"):
            coordinate.finish_execution(claim, started["worker"], "completed")
        (item,) = coordinate.observe(self.state)["issues"]
        (view,) = item["workers"]
        self.assertEqual(
            {k: view[k] for k in ("executor", "route_verified", "status", "setup")},
            {
                "executor": "coordinator",
                "route_verified": False,
                "status": "completed",
                "setup": view["setup"],
            },
        )
        self.assertLess(view["setup"], 1)
        self.assertIsInstance(view["running"], float)
        self.assertEqual(item["phases"]["implement"], view["running"])
        # Closed: the issue is free for a real worker again.
        admission.reserve_worker(claim, "f" * 32, "implement")
        with self.assertRaisesRegex(RuntimeError, "Another execution"):
            coordinate.start_execution(claim, "implement", ROUTE)

    def test_review_records_verdict_round_and_an_unchanged_clean_head(self) -> None:
        claim = self.claimed(6)
        (self.checkout / "example.txt").write_text("dirty\n")
        with self.assertRaisesRegex(RuntimeError, "clean, committed head"):
            coordinate.start_execution(claim, "review", ROUTE)
        worktree.git(self.checkout, "checkout", "--", "example.txt")
        review = coordinate.start_execution(claim, "review", ROUTE)
        identifier = review["worker"]
        malformed = {
            "no verdict": (None, 1),
            "no round": ("approved", None),
            "unknown verdict": ("accepted", 1),
            "round too high": ("approved", 4),
            "round zero": ("approved", 0),
        }
        for name, judgement in malformed.items():
            with (
                self.subTest(name),
                self.assertRaisesRegex(RuntimeError, "verdict and round"),
            ):
                coordinate.finish_execution(claim, identifier, "completed", judgement)
        with self.assertRaisesRegex(RuntimeError, "verdict and round"):
            coordinate.finish_execution(claim, identifier, "cancelled", ("approved", 1))
        self.commit("moved during review\n")
        with self.assertRaisesRegex(RuntimeError, "Reviewed checkout changed"):
            coordinate.finish_execution(claim, identifier, "completed", ("approved", 1))
        cancelled = coordinate.finish_execution(claim, identifier, "cancelled")
        self.assertNotIn("verdict", cancelled)
        review = coordinate.start_execution(claim, "review", ROUTE)
        done = coordinate.finish_execution(
            claim, review["worker"], "completed", ("changes_required", 2)
        )
        head = worktree.git(self.checkout, "rev-parse", "HEAD")
        self.assertEqual(
            {k: done[k] for k in ("reviewed_head", "verdict", "round", "head_after")},
            {
                "reviewed_head": head,
                "verdict": "changes_required",
                "round": 2,
                "head_after": head,
            },
        )
        views = coordinate.observe(self.state)["issues"][0]["workers"]
        self.assertEqual(
            [
                (v["status"], v.get("verdict"))
                for v in views
                if v["worker"] == done["worker"]
            ],
            [("completed", "changes_required")],
        )
        implement = coordinate.start_execution(claim, "implement", ROUTE)
        with self.assertRaisesRegex(RuntimeError, "verdict and round"):
            coordinate.finish_execution(
                claim, implement["worker"], "completed", ("approved", 1)
            )

    def test_malformed_foreign_and_worker_records_are_refused(self) -> None:
        claim = self.claimed(7)
        for name, (role, route) in {
            "role": ("plan", ROUTE),
            "missing model": ("implement", ("anthropic", None, "high")),
            "spaced effort": ("implement", ("anthropic", "model", "high x")),
            "empty provider": ("implement", ("", "model", "high")),
        }.items():
            with (
                self.subTest(name),
                self.assertRaisesRegex(RuntimeError, "explicit provider"),
            ):
                coordinate.start_execution(claim, role, route)
        for caller in (None, "other"):
            environment = {
                k: v for k, v in os.environ.items() if k != "BALLAST_COORDINATOR"
            }
            if caller:
                environment["BALLAST_COORDINATOR"] = caller
            with (
                self.subTest(caller=caller),
                patch.dict(os.environ, environment, clear=True),
                self.assertRaisesRegex(RuntimeError, "coordinator reference"),
            ):
                coordinate.start_execution(claim, "implement", ROUTE)
        self.assertEqual(list((self.state / "workers").glob("*")), [])
        # A real worker's lock blocks a coordinator execution.
        admission.reserve_worker(claim, "f" * 32, "implement")
        with self.assertRaisesRegex(RuntimeError, "Another execution"):
            coordinate.start_execution(claim, "implement", ROUTE)
        admission.release_worker(claim, "f" * 32)
        # A worker.py record is never finished as a coordinator execution, even
        # if the claim history names it.
        real = self.worker_on(claim)
        for status in ("completed", "cancelled"):
            with self.assertRaisesRegex(RuntimeError, "No open coordinator"):
                coordinate.finish_execution(claim, real["worker"], status)
        item = admission.read(claim)
        admission.milestone(item, "execution_started", worker=real["worker"])
        admission.write(claim, item)
        with self.assertRaisesRegex(RuntimeError, "not an open coordinator"):
            coordinate.finish_execution(claim, real["worker"], "cancelled")
        for bad in ("../x", "F" * 32, ""):
            with self.assertRaisesRegex(RuntimeError, "execution ID"):
                coordinate.finish_execution(claim, bad, "completed")

    def test_route_cannot_be_marked_verified(self) -> None:
        claim = self.claimed(8)
        started = coordinate.start_execution(claim, "review", ROUTE)
        path = self.state / "workers" / started["worker"] / "result.json"
        record = admission.read(path)
        forged = record | {"route_verified": True, "source": coordinate.RECEIPT}
        admission.write(path, forged)
        view = coordinate.worker_view(path.parent, "2026-01-01T00:00:00+00:00")
        self.assertFalse(view["route_verified"])
        binding = dashboard.Binding(self.repo, REPO, self.policy["id"], "lead")
        binding.next_refresh = float("inf")
        (projected,) = binding.snapshot()["issues"][0]["workers"]
        self.assertFalse(projected["route_verified"])
        with self.assertRaisesRegex(RuntimeError, "not an open coordinator"):
            coordinate.finish_execution(claim, started["worker"], "cancelled")
        # No option sets the route verified.
        with self.assertRaises(SystemExit), patch("sys.stderr"):
            coordinate.parser().parse_args(
                ["execution", "start", "--claim", str(claim), "--route-verified"]
            )
        admission.write(path, record)
        coordinate.finish_execution(claim, started["worker"], "cancelled")

    def test_status_and_dashboard_project_executor_and_marker(self) -> None:
        claim = self.claimed(9)
        review = coordinate.start_execution(claim, "review", ROUTE)
        coordinate.finish_execution(
            claim, review["worker"], "completed", ("approved", 1)
        )
        binding = dashboard.Binding(self.repo, REPO, self.policy["id"], "lead")
        binding.next_refresh = float("inf")
        issue = binding.snapshot()["issues"][0]
        (projected,) = issue["workers"]
        self.assertEqual(
            {
                k: projected[k]
                for k in ("executor", "route_verified", "source", "verdict", "round")
            },
            {
                "executor": "coordinator",
                "route_verified": False,
                "source": "coordinator-reported",
                "verdict": "approved",
                "round": 1,
            },
        )
        self.assertEqual(projected["requested"]["provider"], "anthropic")
        self.assertIsNone(projected["observed"]["model"])
        self.assertIsNotNone(projected["timing"]["running"])
        self.assertEqual(issue["review_rounds"], 1)
        self.assertEqual(
            [m["event"] for m in projected["milestones"]],
            ["created", "task_accepted", "completed"],
        )

    def test_cli_names_the_executor_and_separates_actions(self) -> None:
        claim = self.claimed(10)

        def run(*argv: str) -> dict:
            arguments = ["--cwd", str(self.repo), "execution", *argv]
            return coordinate.run(coordinate.parser().parse_args(arguments))

        route = ["--provider", "anthropic", "--model", "m", "--effort", "high"]
        start = ["start", "--claim", str(claim), "--role", "implement", *route]
        with self.assertRaisesRegex(RuntimeError, "executor, role and route"):
            run(*start)
        with self.assertRaisesRegex(RuntimeError, "executor, role and route"):
            run(*start, "--executor", "coordinator", "--status", "completed")
        started = run(*start, "--executor", "coordinator")
        finish = ["finish", "--claim", str(claim), "--worker", started["worker"]]
        with self.assertRaisesRegex(RuntimeError, "worker, status, verdict"):
            run(*finish, "--status", "completed", "--model", "m")
        done = run(*finish, "--status", "completed")
        self.assertEqual(done["status"], "completed")

    def test_publish_never_counts_a_coordinator_review(self) -> None:
        self.policy = self.queue([11])
        claim = self.prepare(11)
        record = admission.read(claim)
        self.heads[record["branch"]] = self.base
        (self.root / "body.md").write_text("Fictional PR body")
        review = coordinate.start_execution(claim, "review", ROUTE)
        coordinate.finish_execution(
            claim, review["worker"], "completed", ("approved", 1)
        )
        with self.assertRaisesRegex(RuntimeError, "completed independent"):
            coordinate.publish(claim, "Fictional", self.root / "body.md")
        self.assertEqual(self.prs, [])
        with self.assertRaises(SystemExit), patch("sys.stderr"):
            coordinate.parser().parse_args(
                [
                    "publish",
                    "--claim",
                    str(claim),
                    "--title",
                    "Fictional",
                    "--body-file",
                    str(self.root / "body.md"),
                    "--accept-unverified-review",
                ]
            )

    def test_interrupted_finish_resumes_with_the_same_outcome(self) -> None:
        claim = self.claimed(12)
        native_write, native_event = admission.write, coordinate.worker.event

        def fail_on(target: str) -> object:
            def write(path: Path, value: dict) -> None:
                if path == claim and target == "claim":
                    raise OSError
                native_write(path, value)

            def event(directory: Path, kind: str, **values: object) -> None:
                if target == "event" and kind != "created":
                    raise OSError
                native_event(directory, kind, **values)

            return (
                patch.object(admission, "write", write),
                patch.object(coordinate.worker, "event", event),
            )

        for target in ("event", "claim"):
            with self.subTest(target):
                review = coordinate.start_execution(claim, "review", ROUTE)
                identifier = review["worker"]
                write, event = fail_on(target)
                with write, event, self.assertRaises(OSError):
                    coordinate.finish_execution(
                        claim, identifier, "completed", ("approved", 1)
                    )
                self.assertIn(
                    identifier, admission.open_executions(admission.read(claim))
                )
                # A retry may not change the recorded outcome.
                for status, judgement in (
                    ("cancelled", (None, None)),
                    ("completed", ("changes_required", 1)),
                    ("completed", ("approved", 2)),
                ):
                    with self.assertRaisesRegex(RuntimeError, "not an open"):
                        coordinate.finish_execution(
                            claim, identifier, status, judgement
                        )
                # The head may move after the recorded review; the retry still closes.
                self.commit(f"after {target}\n")
                done = coordinate.finish_execution(
                    claim, identifier, "completed", ("approved", 1)
                )
                self.assertEqual(done["verdict"], "approved")
                self.assertEqual(done["head_after"], review["head_before"])
                self.assertEqual(
                    self.events(done), ["created", "task_accepted", "completed"]
                )
                self.assertEqual(
                    admission.open_executions(admission.read(claim)), set()
                )
                with self.assertRaisesRegex(RuntimeError, "No open coordinator"):
                    coordinate.finish_execution(
                        claim, identifier, "completed", ("approved", 1)
                    )
        admission.reserve_worker(claim, "f" * 32, "implement")


if __name__ == "__main__":
    unittest.main()
