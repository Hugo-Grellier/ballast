"""Deterministic queue admission, control and recovery checks without agents."""

from __future__ import annotations

import contextlib
import io
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

from tests import test_standalone_execution as standalone
from tests.test_standalone_execution import setUpModule  # noqa: F401 -- #233
from tools import admission, codex, coordinate, dashboard, progress, worker, worktree

REPO = "example/fixture"


def past_deadline():  # noqa: ANN201
    """Control check outlasting a one-second deadline once; fail, never hang, later."""
    calls = []

    def check(_: Path) -> bool:
        calls.append(None)
        if len(calls) > 3:  # noqa: PLR2004 -- bound a deadline that never fires
            message = "Worker kept polling past its deadline"
            raise AssertionError(message)
        if len(calls) == 1:
            time.sleep(1)
        return False

    return check


# Backend reply to an interrupted turn: receipt, interrupt ack, terminal turn.
INTERRUPTED = [
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
# A real client process: emit the transcript, then run until its input closes.
CLIENT = (
    "import sys; sys.stdout.write(sys.argv[1]); sys.stdout.flush(); sys.stdin.read()"
)
# A worker stand-in: launch a client the worker's way, report it, then idle.
STAND_IN = """
import subprocess, sys, time
from tools import worker
idle = [sys.executable, "-c", "import time; time.sleep(60)"]
client = subprocess.Popen(idle, **worker.WorkerServer.isolation())
print(client.pid, flush=True)
time.sleep(60)
"""
# Set in the child run that owns a fresh process group for group-wide signals.
GROUP_RUN = "BALLAST_TEST_GROUP_RUN"


def gone(pid: int) -> bool:
    """Report whether a process exited (a zombie has exited too)."""
    try:
        stat = (Path("/proc") / str(pid) / "stat").read_text()
    except FileNotFoundError:
        return True
    return stat.rsplit(")", 1)[1].split()[0] == "Z"


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
        self.pr_numbers: set[int] = set()
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
            return self.answer_graphql(argv)
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

    def answer_graphql(self, argv: list[str]) -> dict:
        """Answer one aliased issue query with only the fields it selects."""
        self.graphql.append(argv)
        query = next(a for a in argv if a.startswith("query="))
        numbers = [
            int(n)
            for n in re.findall(r"i\d+:issueOrPullRequest\(number:(\d+)\)", query)
        ]
        if self.missing.intersection(numbers):
            # The real gh exits non-zero when any alias is unresolved.
            worktree.fail("Fictional unresolved issue")
        nodes = {n: {} if n in self.pr_numbers else self.issue(n) for n in numbers}
        if not self.selects_native_prs(query):
            # Like GitHub, return only the fields the query selects.
            for value in nodes.values():
                if "blockedBy" in value:
                    native = value["blockedBy"]
                    value["blockedBy"] = {
                        **native,
                        "nodes": [
                            {
                                k: v
                                for k, v in node.items()
                                if k != "closedByPullRequestsReferences"
                            }
                            for node in native["nodes"]
                        ],
                    }
        return {"data": {"repository": {f"i{n}": v for n, v in nodes.items()}}}

    @staticmethod
    def selects_native_prs(query: str) -> bool:
        """Tell whether `blockedBy` nodes select closing PRs, fragments expanded."""
        fragments = dict(
            re.findall(
                r"fragment (\w+) on Issue\{(.*?)\}(?=\s*fragment|\s*$)",
                query,
                re.DOTALL,
            )
        )
        for _ in fragments:
            query = re.sub(r"\.\.\.(\w+)", lambda m: fragments.get(m[1], m[0]), query)
        start = query.find("{", query.index("blockedBy("))
        depth = 0
        for end in range(start, len(query)):
            depth += {"{": 1, "}": -1}.get(query[end], 0)
            if not depth:
                return "closedByPullRequestsReferences" in query[start:end]
        return False

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

    def worker_on(self, claim: Path, edit=None, timeout: float = 2) -> dict:  # noqa: ANN001
        """Run the scripted backend, optionally editing its transcript."""
        self.claim = claim
        self.cwd = Path(json.loads(claim.read_text())["checkout"])
        messages = self.script()
        return self.run_worker(edit(messages) if edit else messages, timeout=timeout)

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

    def outcome(self, claim: Path) -> tuple[dict, list[dict]]:
        """Return the claim's single worker's recorded result and events."""
        attempt = json.loads(claim.read_text())["attempt"]
        (directory,) = (
            path
            for path in (claim.parent / "workers").iterdir()
            if json.loads((path / "result.json").read_text())["attempt"] == attempt
        )
        events = (directory / "events.jsonl").read_text().splitlines()
        return (
            json.loads((directory / "result.json").read_text()),
            [json.loads(line) for line in events],
        )

    def quiet_signals(self) -> object:
        """Make the signals harmless here: a missing worker handler fails, not kills."""

        def ignore(*_: object) -> None:
            pass

        for number in (signal.SIGTERM, signal.SIGINT):
            self.addCleanup(signal.signal, number, signal.signal(number, ignore))
        return ignore

    def test_deadline_interrupts_and_settles_timeout(self) -> None:
        self.queue([84])
        claim = self.prepare(84)
        # The first control check outlasts the deadline, as a long turn would.
        with patch.object(admission, "cancelled", side_effect=past_deadline()):
            result = self.worker_on(claim, lambda m: m[:4] + INTERRUPTED, timeout=1)
        self.assertEqual(result["status"], "timeout")
        self.assertFalse(claim.with_suffix(".worker").exists())
        _, events = self.outcome(claim)
        self.assertIn("timeout", events[-2].values())
        self.assertEqual(events[-1]["event"], "timeout")
        # A settled worker stops counting running time.
        view = coordinate.worker_view(
            claim.parent / "workers" / result["worker"], "2999-01-01T00:00:00+00:00"
        )
        self.assertLess(view["running"], 60)

    def test_deadline_without_quiet_terminal_evidence_stays_unknown(self) -> None:
        self.queue([85, 86, 87], issues=3, workers=3)
        quiet = worker.await_quiet
        for issue, tail, check, reason in (
            # Backend ends after the interrupt ack (the silent backend's bound is
            # covered by test_interrupt_bound_ends_a_silent_backend).
            (85, INTERRUPTED[:2], quiet, "ended"),
            (
                86,
                [*INTERRUPTED[:1], {"id": "worker-interrupt", "error": {}}],
                quiet,
                "rejected the interrupt",
            ),
            (
                87,
                INTERRUPTED,
                Mock(side_effect=codex.QualificationError("Processes still run")),
                "still run",
            ),
        ):
            with self.subTest(issue=issue):
                claim = self.prepare(issue)
                with (
                    patch.object(admission, "cancelled", side_effect=past_deadline()),
                    patch.object(worker, "await_quiet", check),
                    self.assertRaisesRegex(codex.QualificationError, reason),
                ):
                    self.worker_on(claim, lambda m, t=tail: m[:4] + t, timeout=1)
                self.assertEqual(self.outcome(claim)[0]["status"], "unknown")
                self.assertTrue(claim.with_suffix(".worker").exists())

    def test_signal_before_reservation_starts_nothing(self) -> None:
        self.queue([92])
        claim = self.prepare(92)
        self.quiet_signals()
        with (
            worker.stop_on_signals(),
            patch.object(worker, "WorkerServer") as server,
            self.assertRaisesRegex(codex.QualificationError, "signal"),
        ):
            os.kill(os.getpid(), signal.SIGTERM)
            self.worker_on(claim)
        server.assert_not_called()
        self.assertFalse(claim.with_suffix(".worker").exists())
        self.assertFalse((claim.parent / "workers").exists())

    def test_signal_before_dispatch_settles_not_started(self) -> None:
        self.queue([88, 89], issues=2)
        ignore = self.quiet_signals()
        capability = codex.check_capability
        for issue, number in ((88, signal.SIGTERM), (89, signal.SIGINT)):
            with self.subTest(signal=number):
                claim = self.prepare(issue)

                def stop(*args: object, number: int = number) -> None:
                    os.kill(os.getpid(), number)
                    capability(*args)

                with (
                    worker.stop_on_signals(),
                    patch.object(codex, "check_capability", side_effect=stop),
                    patch.object(admission, "permit_turn") as permit,
                    self.assertRaisesRegex(codex.QualificationError, "signal"),
                ):
                    self.worker_on(claim)
                permit.assert_not_called()
                self.assertEqual(self.outcome(claim)[0]["status"], "not_started")
                self.assertFalse(claim.with_suffix(".worker").exists())
                self.assertIs(signal.getsignal(number), ignore)

    def test_signal_after_dispatch_interrupts_or_stays_unknown(self) -> None:
        self.queue([90, 91], issues=2)
        self.quiet_signals()

        def stop(_: Path) -> bool:
            os.kill(os.getpid(), signal.SIGTERM)
            return False

        claim = self.prepare(90)
        with (
            worker.stop_on_signals(),
            patch.object(admission, "cancelled", side_effect=stop),
        ):
            result = self.worker_on(claim, lambda m: m[:4] + INTERRUPTED)
        self.assertEqual(result["status"], "cancelled")
        self.assertFalse(claim.with_suffix(".worker").exists())
        claim = self.prepare(91)
        with (
            worker.stop_on_signals(),
            patch.object(admission, "cancelled", side_effect=stop),
            self.assertRaises(codex.QualificationError),
        ):
            self.worker_on(claim, lambda m: m[:4] + INTERRUPTED[:2])
        self.assertEqual(self.outcome(claim)[0]["status"], "unknown")
        self.assertTrue(claim.with_suffix(".worker").exists())

    def test_operator_cancelled_attempts_are_refunded(self) -> None:
        self.queue([96])
        claim = self.prepare(96)
        self.quiet_signals()

        def stop(_: Path) -> bool:
            os.kill(os.getpid(), signal.SIGTERM)
            return False

        for _ in range(3):
            with (
                worker.stop_on_signals(),
                patch.object(admission, "cancelled", side_effect=stop),
            ):
                result = self.worker_on(claim, lambda m: m[:4] + INTERRUPTED)
            self.assertEqual(result["status"], "cancelled")
        record = json.loads(claim.read_text())
        self.assertEqual(record["worker_attempts"], {"implement": 0})
        refunds = [h for h in record["history"] if h["event"] == "attempt_refunded"]
        self.assertEqual(len(refunds), 3)
        self.assertEqual(refunds[-1]["worker"], result["worker"])
        self.assertEqual(self.worker_on(claim)["status"], "completed")
        # A repeated settlement of the same worker never refunds twice.
        admission.release_worker(claim, result["worker"], "implement")
        record = json.loads(claim.read_text())
        self.assertEqual(record["worker_attempts"], {"implement": 1})
        self.assertEqual(
            [h["event"] for h in record["history"]].count("attempt_refunded"), 3
        )

    def test_timeout_and_unknown_attempts_keep_counting(self) -> None:
        self.queue([97, 98], issues=2)
        claim = self.prepare(97)
        for _ in range(3):
            with patch.object(admission, "cancelled", side_effect=past_deadline()):
                result = self.worker_on(claim, lambda m: m[:4] + INTERRUPTED, timeout=1)
            self.assertEqual(result["status"], "timeout")
        with self.assertRaisesRegex(admission.AdmissionError, "attempt limit"):
            self.worker_on(claim)
        self.assertEqual(
            json.loads(claim.read_text())["worker_attempts"], {"implement": 3}
        )
        # An interrupt without terminal evidence stays unknown and keeps its attempt.
        claim = self.prepare(98)
        with (
            patch.object(admission, "cancelled", return_value=True),
            self.assertRaises(codex.QualificationError),
        ):
            self.worker_on(claim, lambda m: m[:4] + INTERRUPTED[:2])
        held = claim.with_suffix(".worker").read_text()
        admission.release(claim, held, "backend thread shows the turn stopped")
        record = json.loads(claim.read_text())
        self.assertEqual(record["worker_attempts"], {"implement": 1})
        self.assertNotIn("attempt_refunded", [h["event"] for h in record["history"]])

    def client_on(self, claim: Path) -> dict:
        """Run the worker against a real client process that confirms an interrupt."""
        self.cwd = Path(json.loads(claim.read_text())["checkout"])
        lines = "".join(json.dumps(m) + "\n" for m in self.script()[:4] + INTERRUPTED)
        native = subprocess.Popen

        def launch(argv: list[str], **kwargs: object) -> object:
            if argv[0] == "/fictional/codex":
                argv = [sys.executable, "-I", "-S", "-c", CLIENT, lines]
            return native(argv, **kwargs)

        with (
            patch.object(codex.subprocess, "Popen", side_effect=launch),
            patch.object(worker.shutil, "which", return_value="/fictional/codex"),
        ):
            return worker.execute(
                claim,
                self.task,
                route=("fixture-model", "low"),
                role="implement",
                timeout=2,
            )

    def test_group_signal_after_dispatch_settles_cancelled(self) -> None:
        if GROUP_RUN not in os.environ:
            # A group-wide signal needs a process group of its own: rerun this
            # test as the leader of a new session, then signal that whole group.
            done = subprocess.run(  # noqa: S603 -- this interpreter, this test
                [
                    sys.executable,
                    "-m",
                    "unittest",
                    f"{__name__}.{self.id().split('.', 2)[2]}",
                ],
                cwd=Path(__file__).resolve().parents[1],
                env={**os.environ, GROUP_RUN: "1"},
                start_new_session=True,
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertRegex(done.stderr, r"Ran 1 test")
            return
        self.queue([93, 94], issues=2)
        self.quiet_signals()
        for issue, number in ((93, signal.SIGTERM), (94, signal.SIGINT)):
            with self.subTest(signal=number):
                claim = self.prepare(issue)

                def stop(_: Path, number: int = number) -> bool:
                    os.killpg(0, number)  # Ctrl-C or a harness stopping the tree.
                    return False

                with (
                    worker.stop_on_signals(),
                    patch.object(admission, "cancelled", side_effect=stop),
                ):
                    result = self.client_on(claim)
                self.assertEqual(result["status"], "cancelled")
                _, events = self.outcome(claim)
                self.assertIn("cancelled", events[-2].values())
                self.assertFalse(claim.with_suffix(".worker").exists())

    def test_client_dies_with_a_killed_worker(self) -> None:
        # A stand-in worker launches a client as the worker does, then is SIGKILLed.
        stand_in = subprocess.Popen(  # noqa: S603 -- this interpreter, fixed code
            [sys.executable, "-c", STAND_IN],
            cwd=Path(__file__).resolve().parents[1],
            stdout=subprocess.PIPE,
            text=True,
        )
        self.addCleanup(stand_in.wait)
        self.addCleanup(stand_in.kill)
        client = int(stand_in.stdout.readline())
        stand_in.stdout.close()
        self.assertNotEqual(os.getpgid(client), os.getpgid(stand_in.pid))
        stand_in.kill()
        deadline = time.monotonic() + 10
        while not gone(client):
            if time.monotonic() >= deadline:
                os.kill(client, signal.SIGKILL)
                self.fail("Client outlived its killed worker")
            time.sleep(0.05)

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
    def node(number: int, state: str, *, merged: bool = False) -> dict:
        """Build a native `blockedBy` node as the first query returns it."""
        return {
            "number": number,
            "state": state,
            "repository": {"nameWithOwner": REPO},
            "closedByPullRequestsReferences": {
                "nodes": [{"merged": True}] if merged else []
            },
        }

    def publish_ready(self, issue: int) -> Path:
        """Push the base head and run a completed independent review of it."""
        claim = self.prepare(issue)
        record = json.loads(claim.read_text())
        self.heads[record["branch"]] = self.base
        self.claim, self.cwd = claim, Path(record["checkout"])
        messages = self.script(sandbox={"type": "readOnly", "networkAccess": False})
        self.review = self.run_worker(messages, role="review")
        body = self.root / "body.md"
        body.write_text("Fictional PR body")
        return claim

    def test_publish_requires_a_completed_review_of_this_head_and_attempt(
        self,
    ) -> None:
        self.queue([45])
        claim = self.publish_ready(45)
        result = self.state / "workers" / self.review["worker"] / "result.json"
        reviewed = json.loads(result.read_text())
        self.assertEqual(reviewed["status"], "completed")
        branch = json.loads(claim.read_text())["branch"]
        # A refusal must come before the first GitHub call (the pushed-head read).
        self.heads[branch] = "advanced"
        refusals = {
            "no review": None,
            "implementer": {"role": "implement"},
            "older head": {"head_before": "older", "head_after": "older"},
            "changed checkout": {"head_after": "changed"},
            "moved during review": {"head_before": "older"},
            "another attempt": {"attempt": "another"},
            **{
                status: {"status": status}
                for status in ("cancelled", "unknown", "released", "quota")
            },
        }
        for name, change in refusals.items():
            with self.subTest(name):
                if change is None:
                    result.unlink()
                else:
                    result.write_text(json.dumps(reviewed | change))
                with self.assertRaisesRegex(RuntimeError, "completed independent"):
                    coordinate.publish(claim, "Fictional", self.root / "body.md")
        result.write_text(json.dumps(reviewed))
        # Any malformed worker record fails closed, even beside a valid review.
        other = self.state / "workers" / "other" / "result.json"
        other.parent.mkdir()
        other.write_text("{")
        native = Path.glob
        # Scan both orders: a valid review found first must not hide it.
        for reverse in (False, True):
            with (
                self.subTest(reverse=reverse),
                patch.object(
                    Path,
                    "glob",
                    lambda path, pattern, r=reverse: iter(
                        sorted(native(path, pattern), reverse=r)
                    ),
                ),
                self.assertRaisesRegex(RuntimeError, "malformed"),
            ):
                coordinate.publish(claim, "Fictional", self.root / "body.md")
        other.unlink()
        self.assertEqual(self.prs, [])
        self.heads[branch] = self.base
        record = coordinate.publish(claim, "Fictional", self.root / "body.md")
        self.assertEqual(record["pr"]["head"], self.base)

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
        record = json.loads(claim.read_text())
        # A claim recorded under another reference, e.g. before #200.
        claim.write_text(json.dumps({**record, "coordinator": "previous"}))
        with self.assertRaisesRegex(admission.AdmissionError, "stop evidence"):
            admission.settle(claim, "unknown", "taking over")
        self.assertEqual(json.loads(claim.read_text())["coordinator"], "previous")

    def test_queue_coordinator_stops_a_stranded_foreign_claim(self) -> None:
        self.queue([49])
        claim = self.prepare(49)
        record = json.loads(claim.read_text())
        for previous, activity in (("previous", "active"), ("", "unknown")):
            claim.write_text(
                json.dumps({**record, "coordinator": previous, "activity": activity})
            )
            stranded = claim.read_text()
            # A recorded writer lock blocks the stop; release or reconcile first.
            claim.with_suffix(".worker").write_text("fixture-worker")
            with self.assertRaisesRegex(admission.AdmissionError, "recorded worker"):
                admission.settle(claim, "stopped", "previous session gone")
            claim.with_suffix(".worker").unlink()
            # Neither the recorded owner nor another caller may stop it.
            for caller in (previous, "other"):
                with (
                    self.subTest(caller=caller),
                    patch.dict(os.environ, {"BALLAST_COORDINATOR": caller}),
                    self.assertRaisesRegex(
                        admission.AdmissionError, "queue's coordinator reference"
                    ),
                ):
                    admission.settle(claim, "stopped", "previous session gone")
            self.assertEqual(claim.read_text(), stranded)
            result = admission.settle(claim, "stopped", "previous session gone")
            self.assertEqual(
                (result["activity"], result["coordinator"]), ("stopped", "lead")
            )
            self.assertEqual(
                {
                    k: result["history"][-1][k]
                    for k in ("event", "previous_coordinator")
                },
                {"event": "stopped", "previous_coordinator": previous},
            )
        self.assertEqual(
            admission.settle(claim, "active", "resume")["activity"], "active"
        )
        claim.write_text(
            json.dumps({**record, "coordinator": "", "activity": "stopped"})
        )
        record = admission.settle(claim, "active", "accepted handoff")
        self.assertEqual(record["coordinator"], "lead")

    def test_queue_mutations_require_the_queue_coordinator(self) -> None:
        self.queue([47])
        claim = self.publish_ready(47)
        held = "fixture-worker"
        claim.with_suffix(".worker").write_text(held)
        body = self.root / "body.md"
        cli = coordinate.parser().parse_args(
            ["--cwd", str(self.repo), "control", "paused", "--reason", "x"]
        )
        mutations = {
            "control": lambda: coordinate.run(cli),
            "settle": lambda: admission.settle(claim, "stopped", "operator stop"),
            "release": lambda: admission.release(claim, held, "thread failed"),
            "publish": lambda: coordinate.publish(claim, "Fictional", body),
            "record_pr": lambda: admission.record_pr(claim, {"number": 1}),
            "close": lambda: admission.close(self.state, "run finished"),
        }

        def refused(mutations: dict, callers: tuple = (None, "", "other")) -> None:
            before = (claim.read_text(), (self.state / "queue.json").read_text())
            checkouts = worktree.git(self.repo, "worktree", "list", "--porcelain")
            for caller in callers:
                environment = {} if caller is None else {"BALLAST_COORDINATOR": caller}
                for name, mutate in mutations.items():
                    with (
                        self.subTest(caller=caller, operation=name),
                        patch.dict(os.environ, environment),
                    ):
                        if caller is None:
                            del os.environ["BALLAST_COORDINATOR"]
                        with self.assertRaisesRegex(
                            admission.AdmissionError, "queue's coordinator reference"
                        ):
                            mutate()
            self.assertEqual(
                (claim.read_text(), (self.state / "queue.json").read_text()), before
            )
            self.assertEqual(
                worktree.git(self.repo, "worktree", "list", "--porcelain"), checkouts
            )

        refused(mutations)
        self.assertTrue(claim.with_suffix(".worker").exists())
        self.assertEqual(self.prs, [])
        # The queue's coordinator succeeds on each operation.
        self.assertEqual(coordinate.run(cli)["mode"], "paused")
        self.assertEqual(
            coordinate.publish(claim, "Fictional", body)["pr"]["number"], 50
        )
        admission.release(claim, held, "thread failed")
        self.assertFalse(claim.with_suffix(".worker").exists())
        record = admission.settle(claim, "stopped", "operator stop")
        self.assertEqual(
            (record["activity"], record["coordinator"]), ("stopped", "lead")
        )
        admission.control(self.state, "running", "operator resume")
        refused({"recover": lambda: coordinate.recover(self.repo, claim, "seen")})
        self.assertEqual(
            coordinate.recover(self.repo, claim, "seen")["activity"], "active"
        )
        # A pre-#200 claim owned by another reference launches and records nothing.
        record = json.loads(claim.read_text())
        claim.write_text(json.dumps({**record, "coordinator": "successor"}))
        declaration = {"kind": "plan", "state": "accepted", "summary": "Fixture"}
        foreign = {
            "reserve_worker": lambda: admission.reserve_worker(claim, "w", "review"),
            "progress": lambda: progress.record(claim, declaration),
        }
        refused(foreign, ("successor",))
        self.assertFalse(claim.with_suffix(".worker").exists())

    def test_close_archives_a_finished_queue_for_a_new_one(self) -> None:
        first = self.queue([51, 52], issues=2)
        claim = self.prepare(51)
        # A live budget never closes: no reset by close-and-recreate.
        with self.assertRaisesRegex(admission.AdmissionError, "still has budget"):
            admission.close(self.state, "run finished")
        policy = json.loads((self.state / "queue.json").read_text())
        policy["deadline"] = time.time() - 1
        (self.state / "queue.json").write_text(json.dumps(policy))
        # Unsettled claims of this queue and any worker lock block closing.
        for activity in ("active", "unknown", "pr_wait"):
            record = json.loads(claim.read_text())
            claim.write_text(json.dumps({**record, "activity": activity}))
            with self.assertRaisesRegex(admission.AdmissionError, "awaiting merge"):
                admission.close(self.state, "run finished")
        admission.record_pr(claim, {"number": 1})
        admission.settle(claim, "stopped", "operator stop")
        lock = self.state / "issue-99.worker"
        lock.write_text("unknown")
        with self.assertRaisesRegex(admission.AdmissionError, "worker lock"):
            admission.close(self.state, "run finished")
        lock.unlink()
        with self.assertRaisesRegex(RuntimeError, "already exists"):
            self.queue([53])
        closed = admission.close(self.state, "run finished")
        self.assertEqual(closed["history"][-1]["event"], "closed")
        self.assertFalse((self.state / "queue.json").exists())
        second = self.queue([53])
        self.assertNotEqual(second["id"], first["id"])
        self.prepare(53)
        view = coordinate.observe(self.state)
        self.assertEqual([q["id"] for q in view["closed"]], [first["id"]])
        # The closed queue's published claim stays listed but its PR does not
        # count toward the new queue's throughput.
        self.assertEqual(json.loads(claim.read_text())["pr"]["number"], 1)
        self.assertIn(51, [item["issue"] for item in view["issues"]])
        self.assertEqual(view["summary"]["throughput"]["published"], 0)
        self.assertEqual(view["summary"]["throughput"]["published_per_hour"], 0)
        self.assertEqual(view["queue"]["id"], second["id"])
        with self.assertRaisesRegex(admission.AdmissionError, "No queue"):
            admission.close(self.state / "missing", "run finished")

    def test_close_accepts_a_cancelled_queue_before_its_deadline(self) -> None:
        self.queue([54])
        admission.control(self.state, "cancelled", "operator stop")
        admission.close(self.state, "cancelled run")
        self.assertFalse((self.state / "queue.json").exists())

    def test_pre_queue_claim_needs_no_coordinator(self) -> None:
        claim = self.prepare(48)
        claim.with_suffix(".worker").write_text("fixture-worker")
        with patch.dict(os.environ):
            del os.environ["BALLAST_COORDINATOR"]
            admission.release(claim, "fixture-worker", "thread failed")
            admission.record_pr(claim, {"number": 1})
            record = admission.settle(claim, "stopped", "operator stop")
        self.assertEqual(record["activity"], "stopped")
        self.assertNotIn("coordinator", record)

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

    def test_native_prerequisites_need_no_second_call(self) -> None:
        native = {"pageInfo": {"hasNextPage": False}}
        self.issues = {
            83: {"blockedBy": {**native, "nodes": [self.node(92, "CLOSED")]}},
            84: {
                "blockedBy": {**native, "nodes": [self.node(93, "CLOSED", merged=True)]}
            },
        }
        self.queue([83, 84])
        selected = coordinate.select(self.repo)
        self.assertEqual(len(self.graphql), 1)
        self.assertEqual(selected["eligible"], [84])
        self.assertIn("no merged change", selected["blocked"]["83"][0])

    def test_unreadable_native_prerequisite_is_looked_up_alone(self) -> None:
        self.missing = {94}
        partial = {**self.node(94, "CLOSED"), "closedByPullRequestsReferences": None}
        self.issues = {
            85: {"blockedBy": {"pageInfo": {"hasNextPage": False}, "nodes": [partial]}}
        }
        self.queue([85, 86])
        selected = coordinate.select(self.repo)
        # The partial node falls back to a lookup, which fails, then retries alone.
        self.assertEqual(len(self.graphql), 3)
        self.assertEqual(selected["eligible"], [86])
        self.assertEqual(selected["blocked"], {"85": ["unknown prerequisite #94"]})

    def test_pull_request_numbered_prerequisite_stays_batched(self) -> None:
        self.pr_numbers = {95}
        self.issues = {96: {"body": "Blocked by #95"}}
        self.queue([96])
        selected = coordinate.select(self.repo)
        self.assertEqual(len(self.graphql), 2)
        self.assertEqual(selected["blocked"], {"96": ["unknown prerequisite #95"]})

    def test_many_prerequisites_are_chunked(self) -> None:
        def body(start: int) -> dict:
            refs = ", ".join(f"#{n}" for n in range(start, start + 50))
            return {"body": f"Blocked by {refs}"}

        self.issues = {n: body(2000 + 50 * i) for i, n in enumerate((1, 2, 3))}
        self.queue([1, 2, 3])
        coordinate.select(self.repo)
        self.assertEqual(len(self.graphql), 3)  # queue, then 150 prerequisites in 2
        counts = [
            len(re.findall("issueOrPullRequest", next(a for a in c if "query=" in a)))
            for c in self.graphql
        ]
        self.assertEqual(counts, [3, coordinate.BATCH, 150 - coordinate.BATCH])

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
            patch.object(worker, "QUIET_SECONDS", 0),
            self.assertRaisesRegex(codex.QualificationError, "still run"),
        ):
            self.worker_on(claim)
        self.assertTrue(claim.with_suffix(".worker").exists())

    def tool_child(self, claim: Path) -> object:
        """Run a real tool command in the checkout; it exits once a scan sees it."""
        checkout = Path(json.loads(claim.read_text())["checkout"])
        child = subprocess.Popen(
            [sys.executable, "-c", "import sys; sys.stdin.read()"],
            cwd=checkout,
            stdin=subprocess.PIPE,
        )
        self.addCleanup(child.wait)
        self.addCleanup(child.kill)
        self.addCleanup(child.stdin.close)
        scan = worker.survivors

        def watch(cwd: Path) -> list[int]:
            child.poll()  # Reap it once it exited, as its real parent would.
            found = scan(cwd)
            if child.pid in found:
                child.stdin.close()  # Outlived the interrupt; now let it end.
            return found

        return watch

    @unittest.skipUnless(Path("/proc/self/cwd").exists(), "Linux /proc required")
    def test_interrupted_turn_settles_once_surviving_tool_command_exits(self) -> None:
        self.queue([95, 96], issues=2)
        for issue, control, timeout, status in (
            (95, Mock(return_value=True), 2, "cancelled"),
            (96, Mock(side_effect=past_deadline()), 1, "timeout"),
        ):
            with self.subTest(status=status):
                claim = self.prepare(issue)
                with (
                    patch.object(admission, "cancelled", control),
                    patch.object(worker, "survivors", self.tool_child(claim)),
                    patch.object(worker, "QUIET_SECONDS", 0),
                ):
                    result = self.worker_on(
                        claim, lambda m: m[:4] + INTERRUPTED, timeout=timeout
                    )
                self.assertEqual(result["status"], status)
                self.assertFalse(claim.with_suffix(".worker").exists())
                _, events = self.outcome(claim)
                self.assertEqual(events[-2]["event"], "survivors_exited")
                self.assertGreaterEqual(events[-2]["seconds"], 0)
                self.assertEqual(events[-1]["event"], status)

    def test_survivor_past_the_interrupt_bound_keeps_worker_unknown(self) -> None:
        self.queue([97])
        claim = self.prepare(97)
        scan = Mock(return_value=[4242])
        with (
            patch.object(admission, "cancelled", return_value=True),
            patch.object(worker, "survivors", scan),
            patch.object(worker, "QUIET_SECONDS", 0),
            patch.object(worker, "SURVIVOR_SECONDS", 0.1),
            self.assertRaisesRegex(codex.QualificationError, r"still run.*\b4242\b"),
        ):
            self.worker_on(claim, lambda m: m[:4] + INTERRUPTED)
        self.assertGreater(scan.call_count, 1)  # It kept watching past the bound.
        result, events = self.outcome(claim)
        self.assertEqual(result["status"], "unknown")
        self.assertNotIn("survivors_exited", [e["event"] for e in events])
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
            patch.object(worker, "QUIET_SECONDS", 0),
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
        # The child reports its rename on a pipe: no sleep races a loaded host.
        code = (
            "import sys, time; open('/proc/self/comm', 'wb').write(b'\\xffbad'); "
            "print('renamed', flush=True); time.sleep(30)"
        )
        process = subprocess.Popen(  # noqa: S603
            [sys.executable, "-c", code], stdout=subprocess.PIPE, text=True
        )
        self.addCleanup(process.stdout.close)
        self.addCleanup(process.wait)
        self.addCleanup(process.kill)
        self.assertEqual(process.stdout.readline(), "renamed\n")
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
