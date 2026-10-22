"""Loopback contracts with isolated repositories and scripted native transport."""

from __future__ import annotations

import contextlib
import fcntl
import http.client
import io
import json
import os
import select
import shutil
import signal
import subprocess
import sys
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from tests import test_queue_admission as queue_tests
from tests.test_standalone_execution import setUpModule  # noqa: F401 -- #233
from tools import admission, codex, coordinate, dashboard, progress, worker, worktree

REPO = queue_tests.REPO


class DashboardTests(unittest.TestCase):
    """Reuse only fixture helpers, without inheriting the queue test cases."""

    setUp = queue_tests.QueueTests.setUp
    host = queue_tests.QueueTests.host
    issue = queue_tests.QueueTests.issue
    queue = queue_tests.QueueTests.queue
    prepare = queue_tests.QueueTests.prepare
    worker_on = queue_tests.QueueTests.worker_on
    script = queue_tests.QueueTests.script
    run_worker = queue_tests.QueueTests.run_worker
    bind_scratch = queue_tests.QueueTests.bind_scratch

    def start(self) -> None:
        """Start the actual foreground server in a joined fixture thread."""
        binding = dashboard.Binding(self.repo, REPO, self.policy["id"], "lead")
        binding.next_refresh = float("inf")
        self.server = dashboard.Server(binding)
        thread = threading.Thread(target=self.server.serve_forever)
        thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(thread.join)
        self.addCleanup(self.server.shutdown)
        self.cookie = ""
        self.csrf = ""

    def request(self, path: str, data: dict | None = None, **headers: str) -> tuple:
        """Make real HTTP requests; never call handler methods directly."""
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port)
        self.addCleanup(connection.close)
        supplied = {
            "Origin": self.server.origin,
            "Cookie": self.cookie,
            "X-Ballast-CSRF": self.csrf,
            **headers,
        }
        body = json.dumps(data) if data is not None else None
        if body is not None:
            supplied.setdefault("Content-Type", "application/json")
        connection.request("POST" if data is not None else "GET", path, body, supplied)
        response = connection.getresponse()
        content = response.read()
        return response.status, dict(response.getheaders()), content

    def login(self) -> None:
        """Exchange the fragment capability for a private browser session."""
        status, headers, body = self.request(
            "/api/session", {"capability": self.server.capability}
        )
        self.assertEqual(status, 200)
        self.cookie = headers["Set-Cookie"].split(";", 1)[0]
        self.csrf = json.loads(body)["csrf"]

    def snapshot(self) -> dict:
        """Read the authenticated projection through loopback."""
        status, _, body = self.request("/api/snapshot")
        self.assertEqual(status, 200, body)
        return json.loads(body)

    def test_http_boundary_and_controls(self) -> None:
        self.policy = self.queue([1])
        self.start()
        self.assertEqual(self.request("/api/snapshot")[0], 403)
        self.assertEqual(self.request("/", Host="evil.invalid")[0], 403)
        self.assertEqual(self.request("/../output.txt")[0], 403)
        self.assertEqual(
            self.request(
                "/api/session",
                {"capability": self.server.capability},
                Origin="https://evil.invalid",
            )[0],
            403,
        )
        self.login()
        _, headers, _ = self.request("/")
        self.assertNotIn("unsafe-inline", headers["Content-Security-Policy"])
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])
        self.assertEqual(
            self.request(
                "/api/control", {"action": "paused"}, **{"X-Ballast-CSRF": "wrong"}
            )[0],
            403,
        )
        self.assertEqual(
            self.request(
                "/api/control", {"action": "paused"}, **{"Content-Type": "text/plain"}
            )[0],
            400,
        )
        self.assertEqual(
            self.request(
                "/api/control", {"action": "paused"}, **{"Content-Length": "4096"}
            )[0],
            400,
        )
        self.assertEqual(self.request("/api/control", {"action": "release"})[0], 400)
        for action in ("paused", "running", "cancelled"):
            self.assertEqual(self.request("/api/control", {"action": action})[0], 200)
            self.assertEqual(self.snapshot()["mode"], action)
        for action in ("paused", "running"):
            self.assertEqual(self.request("/api/control", {"action": action})[0], 409)
        self.assertEqual(admission.policy(self.state)["mode"], "cancelled")

    def test_independent_bounded_sessions_and_malformed_cookies(self) -> None:
        self.policy = self.queue([1])
        self.start()
        self.login()
        first_server, first_cookie, first_csrf = self.server, self.cookie, self.csrf
        self.assertTrue(
            first_cookie.startswith(f"ballast_session_{self.server.server_port}=")
        )
        self.login()
        second_cookie, second_csrf = self.cookie, self.csrf
        self.assertEqual(self.request("/api/snapshot", Cookie=first_cookie)[0], 200)
        self.assertEqual(
            self.request(
                "/api/control",
                {"action": "paused"},
                Cookie=first_cookie,
                **{"X-Ballast-CSRF": first_csrf},
            )[0],
            200,
        )
        self.assertEqual(
            self.request(
                "/api/control",
                {"action": "running"},
                Cookie=second_cookie,
                **{"X-Ballast-CSRF": second_csrf},
            )[0],
            200,
        )
        for malformed in (
            "bad[key]=value",
            "$bad=value",
            first_cookie + "; $bad=value",
        ):
            self.assertEqual(self.request("/api/snapshot", Cookie=malformed)[0], 403)
        for _ in range(7):
            self.login()
        self.assertEqual(len(self.server.sessions), 8)
        self.assertEqual(self.request("/api/snapshot", Cookie=first_cookie)[0], 403)
        self.assertEqual(self.request("/api/snapshot", Cookie=second_cookie)[0], 200)
        _, headers, _ = self.request(
            "/api/session", {"capability": self.server.capability}
        )
        for attribute in ("HttpOnly", "SameSite=Strict", "Path=/api"):
            self.assertIn(attribute, headers["Set-Cookie"])
        retained_cookie = headers["Set-Cookie"].split(";", 1)[0]
        # Same host, different ports: a browser may send both cookies together.
        self.start()
        self.login()
        self.assertNotEqual(self.server.cookie_name, first_server.cookie_name)
        combined = self.cookie + "; " + retained_cookie
        self.assertEqual(self.request("/api/snapshot", Cookie=combined)[0], 200)
        self.assertEqual(self.request("/api/snapshot", Cookie=retained_cookie)[0], 403)
        self.server = first_server
        self.assertEqual(self.request("/api/snapshot", Cookie=combined)[0], 200)

    def test_replacement_is_checked_inside_control_lock(self) -> None:
        self.policy = self.queue([2])
        self.start()
        self.login()
        native = admission.locked

        def replaced(state: Path):  # noqa: ANN202 -- context manager fixture
            value = admission.policy(state)
            value["issues"] = [3]
            admission.write(state / "queue.json", value)
            return native(state)

        with patch.object(admission, "locked", side_effect=replaced):
            self.assertEqual(self.request("/api/control", {"action": "paused"})[0], 409)
        self.assertEqual(admission.policy(self.state)["mode"], "running")
        self.assertEqual(self.request("/api/snapshot")[0], 409)
        (self.state / "queue.json").write_text("{")
        self.assertEqual(self.request("/api/snapshot")[0], 409)
        self.assertEqual(self.request("/api/control", {"action": "cancelled"})[0], 409)

    def test_scripted_transport_projection_evidence_and_reconnect(self) -> None:
        self.policy = self.queue([4, 5])
        claim = self.prepare(4)
        result = self.worker_on(claim)
        self.assertEqual(result["status"], "completed")
        for declaration in (
            {"kind": "plan", "state": "accepted", "summary": "Bounded plan accepted"},
            {
                "kind": "question",
                "state": "pending",
                "summary": "Confirm intended acceptance",
                "reference": f"https://github.com/{REPO}/issues/4#issuecomment-12",
            },
            {
                "kind": "check",
                "state": "passed",
                "summary": "Fixture checks passed",
                "revision": self.base,
            },
            {
                "kind": "review",
                "state": "accepted",
                "summary": "Independent fixture review",
                "revision": self.base,
                "round": 1,
            },
        ):
            progress.record(claim, declaration)
        other = admission.read(claim)
        other.update(issue=99, attempt="foreign", queue="foreign")
        other["history"] = [{"event": "worker_reserved", "worker": "private-worker"}]
        admission.write(self.state / "issue-99.json", other)
        private = self.state / "workers" / "private-worker"
        private.mkdir()
        (private / "result.json").write_text('{"reason":"PRIVATE_SENTINEL"}')
        worker_dir = self.state / "workers" / result["worker"]
        record = admission.read(worker_dir / "result.json")
        record.update(
            reason="PRIVATE_SENTINEL",
            tokens={"totalTokens": 12, "account": "PRIVATE_SENTINEL"},
        )
        record["observed"]["private"] = "PRIVATE_SENTINEL"
        admission.write(worker_dir / "result.json", record)
        self.start()
        self.login()
        first = self.snapshot()
        encoded = json.dumps(first)
        for forbidden in (
            "PRIVATE_SENTINEL",
            "private-worker",
            str(self.root),
            "output.txt",
        ):
            self.assertNotIn(forbidden, encoded)
        item = first["issues"][0]
        self.assertEqual(item["readiness"], "unknown")
        self.assertEqual(first["coordinator_liveness"], "unknown")
        self.assertEqual(
            item["workers"][0]["requested"], item["workers"][0]["observed"]
        )
        self.assertEqual(item["workers"][0]["tokens"], {"totalTokens": 12})
        self.assertEqual(item["evidence"][-1]["freshness"], "current")
        self.assertEqual(first["issues"][1]["activity"], "unclaimed")
        # New browser session and refresh observes the same attempts, no dispatch.
        self.login()
        reconnected = self.snapshot()["issues"]
        for original, current in zip(first["issues"], reconnected, strict=True):
            before = json.loads(json.dumps(original))
            after = json.loads(json.dumps(current))
            # Only elapsed and coordinator time advance on observation; every
            # identity, receipt, evidence entry and settled duration must match.
            if "timing" in before:
                self.assertGreaterEqual(
                    after["timing"]["elapsed"], before["timing"]["elapsed"]
                )
                self.assertGreaterEqual(
                    after["timing"]["phases"]["coordinator"],
                    before["timing"]["phases"]["coordinator"],
                )
                for item in (before, after):
                    del item["timing"]["elapsed"]
                    del item["timing"]["phases"]["coordinator"]
            self.assertEqual(after, before)
        checkout = Path(admission.read(claim)["checkout"])
        worktree.git(checkout, "commit", "--allow-empty", "-m", "later")
        self.assertEqual(
            self.snapshot()["issues"][0]["evidence"][-1]["freshness"], "stale"
        )
        self.assertEqual(self.request("/api/control", {"action": "cancelled"})[0], 200)
        self.assertEqual(
            self.snapshot()["issues"][0]["workers"][0]["status"], "completed"
        )

    def test_progress_validation_unknown_worker_and_dependency_budget(self) -> None:
        self.policy = self.queue([6])
        claim = self.prepare(6)
        for changes in (
            {"summary": "api_key=private"},
            {"summary": "/private/path"},
            {"summary": "bad\ntext"},
            {"secret": "x"},
            {"reference": "https://github.com/other/repo/issues/6"},
        ):
            with self.assertRaises(admission.AdmissionError):
                progress.record(
                    claim,
                    {
                        "kind": "plan",
                        "state": "accepted",
                        "summary": "Safe public summary",
                        **changes,
                    },
                )
        with self.assertRaises(admission.AdmissionError):
            progress.record(
                claim,
                {"kind": "check", "state": "passed", "summary": "Missing revision"},
            )
        admission.reserve_worker(claim, "a" * 32, "implement")
        self.start()
        self.login()
        self.assertEqual(
            self.snapshot()["issues"][0]["workers"][0]["status"], "unknown"
        )
        binding = self.server.binding
        binding.next_refresh = 0
        with patch.object(
            dashboard, "selection", side_effect=subprocess.TimeoutExpired("fixture", 2)
        ) as run:
            binding.refresh_dependencies()
            binding.refresh_dependencies()
            self.assertEqual(run.call_count, 1)
        self.assertEqual(binding.dependencies["status"], "unknown")
        with patch.dict("os.environ", {"BALLAST_COORDINATOR": "other"}):
            self.assertEqual(self.request("/api/control", {"action": "paused"})[0], 409)
            with self.assertRaises(admission.AdmissionError):
                progress.record(
                    claim, {"kind": "plan", "state": "accepted", "summary": "Safe"}
                )

    def test_durable_projection_without_http(self) -> None:
        self.policy = self.queue([7, 8])
        claim = self.prepare(7)
        result = self.worker_on(claim)
        progress.record(
            claim,
            {
                "kind": "review",
                "state": "accepted",
                "summary": "Fixture review accepted",
                "revision": self.base,
                "round": 1,
            },
        )
        binding = dashboard.Binding(self.repo, REPO, self.policy["id"], "lead")
        binding.next_refresh = float("inf")
        snapshot = binding.snapshot()
        self.assertEqual(
            snapshot["issues"][0]["workers"][0]["worker"], result["worker"]
        )
        self.assertEqual(snapshot["issues"][0]["evidence"][0]["freshness"], "current")
        self.assertEqual(snapshot["issues"][0]["readiness"], "unknown")
        self.assertEqual(snapshot["issues"][1]["activity"], "unclaimed")
        for action in ("paused", "running", "cancelled"):
            admission.control(self.state, action, "fixture", expected=binding.expected)
        with self.assertRaises(admission.AdmissionError):
            admission.control(
                self.state, "paused", "fixture", expected=binding.expected
            )
        value = admission.policy(self.state)
        value["id"] = "replacement"
        admission.write(self.state / "queue.json", value)
        with self.assertRaises(admission.AdmissionError):
            binding.snapshot()
        with self.assertRaises(admission.AdmissionError):
            admission.control(
                self.state, "paused", "fixture", expected=binding.expected
            )

    def test_retired_attempt_stays_in_projection_until_replaced(self) -> None:
        self.policy = self.queue([7])
        claim = self.prepare(7)
        coordinate.settle(claim, "stopped", "fixture stop")
        coordinate.retire(claim, "fixture retire")
        binding = dashboard.Binding(self.repo, REPO, self.policy["id"], "lead")
        binding.next_refresh = float("inf")
        self.assertEqual(binding.snapshot()["issues"][0]["activity"], "stopped")
        attempt = json.loads(self.prepare(7).read_text())["attempt"]
        row = binding.snapshot()["issues"][0]
        self.assertEqual((row["activity"], row["attempt"]), ("active", attempt))

    def test_snapshot_derives_outside_lock_and_refuses_replacement(self) -> None:
        self.policy = self.queue([7])
        self.prepare(7)
        binding = dashboard.Binding(self.repo, REPO, self.policy["id"], "lead")
        binding.next_refresh = float("inf")
        native = binding.issue
        derived = []

        def probe(item: dict) -> dict:
            with (self.state / "admission.lock").open("a+") as stream:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            derived.append(item["issue"])
            return native(item)

        with patch.object(binding, "issue", side_effect=probe):
            binding.snapshot()
        self.assertEqual(derived, [7])

        def replace(item: dict) -> dict:
            value = admission.policy(self.state)
            value["id"] = "replacement"
            admission.write(self.state / "queue.json", value)
            return native(item)

        with (
            patch.object(binding, "issue", side_effect=replace),
            self.assertRaises(admission.AdmissionError),
        ):
            binding.snapshot()

    def test_projection_isolation_and_unknown_without_http(self) -> None:
        self.policy = self.queue([9, 10], issues=3)
        claim = self.prepare(9)
        result = self.worker_on(claim)
        directory = self.state / "workers" / result["worker"]
        data = admission.read(directory / "result.json")
        data.update(
            reason="PRIVATE_SENTINEL",
            tokens={"totalTokens": 20, "private": "PRIVATE_SENTINEL"},
        )
        data["requested"].update(model="fixture-model.1")
        data["observed"].update(model="fixture-model.2", private="PRIVATE_SENTINEL")
        data["session"] = "invalid.session"
        admission.write(directory / "result.json", data)
        other = admission.read(claim)
        other.update(queue="foreign", issue=99, attempt="PRIVATE_SENTINEL")
        admission.write(self.state / "issue-99.json", other)
        unknown = self.prepare(10)
        admission.reserve_worker(unknown, "f" * 32, "review")
        binding = dashboard.Binding(self.repo, REPO, self.policy["id"], "lead")
        binding.next_refresh = float("inf")
        view = binding.snapshot()
        self.assertNotIn("PRIVATE_SENTINEL", json.dumps(view))
        self.assertNotIn(str(self.root), json.dumps(view))
        projected = view["issues"][0]["workers"][0]
        self.assertEqual(projected["requested"]["model"], "fixture-model.1")
        self.assertEqual(projected["observed"]["model"], "fixture-model.2")
        self.assertNotEqual(projected["requested"], projected["observed"])
        self.assertIsNone(projected["session"])
        self.assertEqual(view["issues"][0]["workers"][0]["tokens"], {"totalTokens": 20})
        self.assertEqual(view["issues"][1]["workers"][0]["status"], "unknown")
        self.assertEqual(
            view["issues"][1]["workers"][0]["observed"],
            dict.fromkeys(("provider", "model", "effort")),
        )
        binding.next_refresh = 0
        with patch.object(
            dashboard, "selection", side_effect=subprocess.TimeoutExpired("fixture", 2)
        ) as selected:
            binding.refresh_dependencies()
            binding.refresh_dependencies()
            self.assertEqual(selected.call_count, 1)
        self.assertEqual(binding.dependencies["status"], "unknown")
        binding.next_refresh = 0
        with patch.object(
            dashboard,
            "selection",
            return_value={
                "blocked": {
                    "9": ["prerequisite #10 has no merged change", "PRIVATE_SENTINEL"],
                    "10": ["unknown prerequisite #11"],
                    "99": ["dependency cycle"],
                },
                "claimed": [],
                "waiting_for_capacity": [],
                "eligible": [],
            },
        ):
            binding.refresh_dependencies()
        self.assertEqual(
            binding.dependencies["reasons"],
            {
                "9": ["prerequisite #10 has no merged change"],
                "10": ["unknown prerequisite #11"],
            },
        )
        self.assertEqual(
            binding.dependencies["issues"], {"9": "blocked", "10": "unknown"}
        )
        self.assertNotIn("PRIVATE_SENTINEL", json.dumps(binding.dependencies))

    def test_route_validation_in_projection(self) -> None:
        self.policy = self.queue([11])
        claim = self.prepare(11)
        result = self.worker_on(claim)
        path = self.state / "workers" / result["worker"] / "result.json"
        binding = dashboard.Binding(self.repo, REPO, self.policy["id"], "lead")
        binding.next_refresh = float("inf")
        for value, expected in (
            ("a" + "._-9" * 31 + "xyz", "a" + "._-9" * 31 + "xyz"),
            ("a" * 129, None),
            (".model", None),
            ("../private", None),
            ("bad value", None),
            (12, None),
        ):
            with self.subTest(value=value):
                result["observed"] = dict.fromkeys(
                    ("provider", "model", "effort"), value
                )
                result["observed"]["private"] = "PRIVATE_SENTINEL"
                admission.write(path, result)
                projected = binding.snapshot()["issues"][0]["workers"][0]
                self.assertEqual(
                    projected["observed"],
                    dict.fromkeys(("provider", "model", "effort"), expected),
                )
                self.assertNotIn("PRIVATE_SENTINEL", json.dumps(projected))
        record = admission.read(claim)
        record["history"].append(
            {"event": "worker_reserved", "worker": "invalid.worker", "role": "review"}
        )
        admission.write(claim, record)
        self.assertEqual(len(binding.snapshot()["issues"][0]["workers"]), 1)

    def test_scripted_cancellation_projection_without_http(self) -> None:
        self.policy = self.queue([12, 13, 14], issues=3)
        completed = self.prepare(12)
        self.worker_on(completed)
        cancelled = self.prepare(13)
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
            result = self.worker_on(cancelled, lambda m: m[:4] + tail)
        self.assertEqual(result["status"], "cancelled")
        directory = self.state / "workers" / result["worker"]
        events = [
            json.loads(line)
            for line in (directory / "events.jsonl").read_text().splitlines()
        ]
        terminal = next(e for e in events if e["event"] == "cancelled")
        unknown = self.prepare(14)
        with (
            patch.object(admission, "cancelled", return_value=True),
            self.assertRaises(codex.QualificationError),
        ):
            self.worker_on(unknown, lambda m: m[:4] + tail[:2])
        binding = dashboard.Binding(self.repo, REPO, self.policy["id"], "lead")
        binding.next_refresh = float("inf")
        admission.control(self.state, "cancelled", "fixture", expected=binding.expected)
        workers = [item["workers"][0] for item in binding.snapshot()["issues"]]
        self.assertEqual(
            [w["status"] for w in workers], ["completed", "cancelled", "unknown"]
        )
        self.assertIn(
            {"event": "cancelled", "at": terminal["at"]}, workers[1]["milestones"]
        )
        self.assertIn(
            "interrupt_requested", [e["event"] for e in workers[2]["milestones"]]
        )
        self.assertNotIn("cancelled", [e["event"] for e in workers[2]["milestones"]])
        self.assertTrue(unknown.with_suffix(".worker").exists())

    def test_timed_out_worker_is_projected_settled(self) -> None:
        self.policy = self.queue([15])
        claim = self.prepare(15)
        # One survivor, then quiet: the worker records survivors_exited. Each
        # scan covers the checkout, then the scratch directory.
        scan = Mock(side_effect=[[4242], [], [], [], [], []])
        with (
            patch.object(
                admission, "cancelled", side_effect=queue_tests.past_deadline()
            ),
            patch.object(worker, "survivors", scan),
        ):
            self.worker_on(claim, lambda m: m[:4] + queue_tests.INTERRUPTED, timeout=1)
        binding = dashboard.Binding(self.repo, REPO, self.policy["id"], "lead")
        binding.next_refresh = float("inf")
        (projected,) = binding.snapshot()["issues"][0]["workers"]
        self.assertEqual(projected["status"], "timeout")
        milestones = [e["event"] for e in projected["milestones"]]
        self.assertIn("timeout", milestones)
        self.assertIn("survivors_exited", milestones)

    @unittest.skipUnless(os.name == "posix", "process groups require POSIX")
    def test_selection_timeout_kills_and_reaps_own_group(self) -> None:
        helper = self.root / "selection_helper.py"
        read_fd, write_fd = os.pipe()
        self.addCleanup(os.close, read_fd)
        write_pipe = os.fdopen(write_fd, "wb")
        self.addCleanup(write_pipe.close)
        # The child signals readiness, then keeps the pipe open until killed.
        # EOF proves no live fixture descendant retains it; alarms bound failures.
        child = (
            "import os, signal; signal.alarm(10); "
            f"os.write({write_fd}, b'ready'); signal.pause()"
        )
        helper.write_text(
            "import signal, subprocess, sys\n"
            "signal.alarm(10)\n"
            f"subprocess.Popen([sys.executable, '-I', '-S', '-c', {child!r}], "
            f"pass_fds=({write_fd},))\n"
            "signal.pause()\n"
        )
        native = subprocess.Popen
        processes = []

        def launch(argv: list[str], **kwargs: object) -> subprocess.Popen:
            process = native(argv, pass_fds=(write_fd,), **kwargs)
            processes.append(process)
            return process

        try:
            with (
                patch.object(dashboard.coordinate, "__file__", str(helper)),
                patch.object(dashboard.subprocess, "Popen", side_effect=launch),
                self.assertRaises(subprocess.TimeoutExpired),
            ):
                dashboard.selection(self.repo)
            write_pipe.close()
            self.assertEqual(len(processes), 1)
            process = processes[0]
            self.assertEqual(process.returncode, -signal.SIGKILL)
            with self.assertRaises(ChildProcessError):
                os.waitpid(process.pid, os.WNOHANG)
            self.assertTrue(select.select([read_fd], [], [], 1)[0])
            self.assertEqual(os.read(read_fd, 5), b"ready")
            self.assertTrue(select.select([read_fd], [], [], 1)[0])
            self.assertEqual(os.read(read_fd, 1), b"")
        finally:
            for process in processes:
                with contextlib.suppress(ProcessLookupError):
                    os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=2)

    def enter(self, *argv: str, coordinator: str = "lead") -> tuple:
        """Run main() with serving stubbed; return (code, stdout, stderr, serve)."""
        out, err = io.StringIO(), io.StringIO()
        with (
            patch.object(
                sys,
                "argv",
                [
                    "dashboard",
                    "--cwd",
                    str(self.repo),
                    "--repo",
                    REPO,
                    "--coordinator",
                    "lead",
                    *argv,
                ],
            ),
            patch.dict(os.environ, {"BALLAST_COORDINATOR": coordinator}),
            patch.object(dashboard.Server, "serve_forever") as serve,
            contextlib.redirect_stdout(out),
            contextlib.redirect_stderr(err),
        ):
            code = dashboard.main()
        return code, out.getvalue(), err.getvalue(), serve

    def test_main_refuses_foreign_coordinator(self) -> None:
        code, out, err, serve = self.enter(
            "--create", "--issue", "5", "--revision", "rev-1", coordinator="other"
        )
        self.assertEqual(code, 1)
        self.assertIn("Dashboard blocked", err)
        self.assertEqual(out, "")
        serve.assert_not_called()
        self.assertIsNone(admission.policy(self.state))

    def test_main_enforces_create_and_queue_arguments(self) -> None:
        refused = (
            ("--create", "--queue", "q", "--issue", "1", "--revision", "r"),
            ("--create", "--revision", "r"),
            ("--create", "--issue", "1"),
            (),
            ("--queue", "q", "--issue", "1"),
            ("--queue", "q", "--revision", "r"),
        )
        for argv in refused:
            with self.subTest(argv=argv), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as raised:
                    self.enter(*argv)
                self.assertEqual(raised.exception.code, 2)
                self.assertIsNone(admission.policy(self.state))

    def test_main_create_makes_and_binds_a_queue(self) -> None:
        code, out, err, serve = self.enter(
            "--create", "--issue", "5", "--issue", "6", "--revision", "rev-1"
        )
        self.assertEqual((code, err), (0, ""))
        self.assertRegex(out, r"\Ahttp://127\.0\.0\.1:[0-9]+/#[^\s]+\n\Z")
        serve.assert_called_once()
        created = admission.policy(self.state)
        self.assertEqual(created["issues"], [5, 6])
        self.assertEqual(
            (created["repository"], created["coordinator"]), (REPO, "lead")
        )
        self.assertEqual(created["instruction_revision"], "rev-1")

    def test_binding_refuses_checkout_and_mismatched_context(self) -> None:
        self.policy = self.queue([1])
        queue_id = self.policy["id"]
        dashboard.Binding(self.repo, REPO, queue_id, "lead")
        with self.assertRaisesRegex(admission.AdmissionError, "project checkout"):
            dashboard.Binding(self.root / "ballast-v2" / "x", REPO, queue_id, "lead")
        for queue, coordinator in (("other-id", "lead"), (queue_id, "other")):
            with (
                self.subTest(queue=queue, coordinator=coordinator),
                self.assertRaisesRegex(
                    admission.AdmissionError, "does not match queue"
                ),
            ):
                dashboard.Binding(self.repo, REPO, queue, coordinator)
        # The checkout's origin check fires first, so edit the queue's repository.
        admission.write(
            self.state / "queue.json", {**self.policy, "repository": "owner/other"}
        )
        with self.assertRaisesRegex(admission.AdmissionError, "does not match queue"):
            dashboard.Binding(self.repo, REPO, queue_id, "lead")

    def test_quota_projection(self) -> None:
        self.policy = self.queue([1])
        binding = dashboard.Binding(self.repo, REPO, self.policy["id"], "lead")
        binding.next_refresh = float("inf")
        self.assertEqual(
            binding.snapshot()["quota"], {"state": "unknown", "retry_at": None}
        )
        future, past = time.time() + 3600, time.time() - 60
        for retry, state in (
            (future, "paused"),
            (None, "paused"),
            (past, "window_elapsed"),
        ):
            admission.quota(self.state, "fixture", retry)
            self.assertEqual(
                binding.snapshot()["quota"], {"state": state, "retry_at": retry}
            )

    def test_dependency_states_in_projection(self) -> None:
        self.policy = self.queue([2, 3, 4])
        binding = dashboard.Binding(self.repo, REPO, self.policy["id"], "lead")
        for halted, waiting, expected in (
            (False, [2], {"2": "capacity_wait", "3": "eligible", "4": "claimed"}),
            (True, [], {"2": "admission_wait", "3": "admission_wait", "4": "claimed"}),
        ):
            binding.next_refresh = 0.0
            observed = {
                "blocked": {},
                "claimed": [4],
                "waiting_for_capacity": waiting,
                "eligible": [] if halted else [3],
                "halted": halted,
            }
            with patch.object(dashboard, "selection", return_value=observed):
                projected = binding.snapshot()["dependencies"]
            self.assertEqual(projected["status"], "observed")
            self.assertEqual(projected["issues"], expected)

    def test_native_ui_contract(self) -> None:
        node = shutil.which("node")
        self.assertIsNotNone(node, "CI requires its existing Node runtime")
        result = subprocess.run(  # noqa: S603 -- fixed local test
            [node, str(Path(__file__).with_name("dashboard_ui.cjs"))],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
