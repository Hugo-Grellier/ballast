"""Loopback contracts with isolated repositories and scripted native transport."""

from __future__ import annotations

import http.client
import json
import shutil
import subprocess
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from tests import test_queue_admission as queue_tests
from tools import admission, dashboard, progress, worktree

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
        data["observed"].update(private="PRIVATE_SENTINEL")
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
