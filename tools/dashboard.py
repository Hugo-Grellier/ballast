"""Foreground, capability-protected loopback projection of one explicit queue."""

from __future__ import annotations

import argparse
import contextlib
import hmac
import json
import math
import os
import re
import secrets
import signal
import subprocess
import sys
import time
from datetime import UTC, datetime
from http.cookies import CookieError, SimpleCookie
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools import admission, coordinate, progress, worktree

MAX_TIMESTAMP = 40
MAX_BODY = 1024
MAX_SESSIONS = 8
ASSETS = Path(__file__).with_name("dashboard_assets")
FILES = {
    "/": ("index.html", "text/html"),
    "/app.js": ("app.js", "text/javascript"),
    "/style.css": ("style.css", "text/css"),
}
MILESTONES = {
    "created",
    "route_verified",
    "task_dispatched",
    "task_accepted",
    "interrupt_requested",
} | coordinate.WORKER_STATUSES
TOKENS = {
    "totalTokens",
    "inputTokens",
    "cachedInputTokens",
    "cacheWriteInputTokens",
    "outputTokens",
    "reasoningOutputTokens",
}
ERRORS = (
    OSError,
    ValueError,
    KeyError,
    TypeError,
    RuntimeError,
    subprocess.SubprocessError,
)


def identifier(value: object) -> str | None:
    """Only bounded opaque receipt references enter the public projection."""
    return (
        value
        if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value)
        else None
    )


def stamp(value: object) -> str | None:
    """Validate timestamps without exposing arbitrary strings."""
    if not isinstance(value, str) or len(value) > MAX_TIMESTAMP:
        return None
    try:
        parsed = datetime.fromisoformat(value)
        return parsed.isoformat() if parsed.tzinfo is not None else None
    except ValueError:
        return None


def route(value: object) -> dict:
    """Whitelist concrete route keys; malformed observations remain unknown."""
    value = value if isinstance(value, dict) else {}
    return {
        key: item
        if isinstance(item := value.get(key), str)
        and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", item)
        else None
        for key in ("provider", "model", "effort")
    }


def number(value: object) -> float | None:
    """Accept only finite nonnegative supplied measurements."""
    return (
        value
        if type(value) in (float, int) and math.isfinite(value) and value >= 0
        else None
    )


def selection(cwd: Path) -> dict:
    """Bound dependency I/O including descendants, without a recurring worker."""
    with subprocess.Popen(  # noqa: S603 -- fixed helper, explicit checkout
        [
            sys.executable,
            "-I",
            "-S",
            str(Path(coordinate.__file__).resolve()),
            "--cwd",
            str(cwd),
            "select",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        start_new_session=True,
    ) as process:
        try:
            output, _ = process.communicate(timeout=2)
        except subprocess.TimeoutExpired:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGKILL)
            process.wait()
            raise
        if process.returncode:
            admission.fail("Dependency source unavailable")
        return json.loads(output)


class Binding:
    """One immutable execution context, with no scheduler or worker ownership."""

    def __init__(self, cwd: Path, repo: str, queue_id: str, coordinator: str) -> None:
        """Verify explicit identity before serving any browser request."""
        if "ballast-v2" in cwd.parts:
            admission.fail("Bind from the project checkout")
        worktree.repository(cwd, repo)
        self.cwd = cwd
        self.state = coordinate.state_directory(cwd)
        with admission.locked(self.state):
            queue = admission.policy(self.state)
            if queue is None or (
                queue["repository"],
                queue["id"],
                queue["coordinator"],
            ) != (repo, queue_id, coordinator):
                admission.fail("Explicit dashboard context does not match queue")
            self.expected = admission.context(queue)
            admission.require_context(queue, self.expected)
        self.dependencies: dict = {"status": "unknown", "at": None}
        self.next_refresh = 0.0

    def refresh_dependencies(self) -> None:
        """Bound the entire existing selection operation, at most once a minute."""
        if time.monotonic() < self.next_refresh:
            return
        self.next_refresh = time.monotonic() + 60
        try:
            data = selection(self.cwd)
            self.dependencies = {
                "status": "observed",
                "at": datetime.now(UTC).isoformat(),
                "reasons": {
                    str(n): [
                        reason
                        for reason in data["blocked"].get(str(n), [])
                        if re.fullmatch(
                            r"not an open leaf issue|issue could not be read|"
                            r"prerequisites could not be evaluated|dependency cycle|"
                            r"unknown prerequisite #[0-9]{1,10}|"
                            r"prerequisite #[0-9]{1,10} has no merged change",
                            reason,
                        )
                    ]
                    for n in self.expected["issues"]
                },
                "issues": {
                    str(n): "unknown"
                    if any(
                        "unknown" in reason or "could not" in reason
                        for reason in data["blocked"].get(str(n), [])
                    )
                    else "blocked"
                    if str(n) in data["blocked"]
                    else "admission_wait"
                    if data.get("halted") and n not in data["claimed"]
                    else "capacity_wait"
                    if n in data["waiting_for_capacity"]
                    else "eligible"
                    if n in data["eligible"]
                    else "claimed"
                    for n in self.expected["issues"]
                },
            }
        except ERRORS:
            self.dependencies = {"status": "unknown", "at": None}

    def worker(self, reservation: dict, attempt: str) -> dict:
        """Read only workers joined through a selected claim's reservation."""
        worker_id = reservation["worker"]
        directory = self.state / "workers" / worker_id
        result, events = {}, []
        try:
            if (directory / "result.json").exists():
                result = admission.read(directory / "result.json")
                if (
                    result.get("worker") != worker_id
                    or result.get("attempt") != attempt
                ):
                    result = {}
            log = directory / "events.jsonl"
            if log.exists():
                events = [json.loads(line) for line in log.read_text().splitlines()]
        except ERRORS:
            result, events = {}, []
        events = [e for e in events if isinstance(e, dict)]
        created = next((e for e in events if e.get("event") == "created"), {})
        requested = result.get("requested") or {
            key: created.get(key) for key in ("model", "effort")
        }
        timings = {}
        with contextlib.suppress(*ERRORS):
            view = coordinate.worker_view(directory, datetime.now(UTC).isoformat())
            timings = {key: number(view.get(key)) for key in ("setup", "running")}
        tokens = result.get("tokens")
        return {
            "worker": worker_id,
            "attempt": attempt,
            "role": reservation.get("role")
            if reservation.get("role") in {"implement", "review"}
            else "unknown",
            "status": result.get("status")
            if result.get("status") in coordinate.WORKER_STATUSES
            else "unknown",
            "requested": route(requested),
            "observed": route(result.get("observed")),
            "source": result.get("source")
            if result.get("source") == "codex-app-server:thread/start"
            else None,
            "session": identifier(result.get("session")),
            "milestones": [
                {"event": e["event"], "at": stamp(e.get("at"))}
                for e in events
                if e.get("event") in MILESTONES
            ],
            "timing": timings,
            "tokens": {
                key: number(tokens.get(key))
                for key in TOKENS
                if number(tokens.get(key)) is not None
            }
            if isinstance(tokens, dict)
            else {},
        }

    def issue(self, item: dict) -> dict:
        """Project selected public evidence; completion implies no approval."""
        attempt = identifier(item.get("attempt"))
        history = item.get("history", [])
        workers = [
            self.worker(h, attempt)
            for h in history
            if h.get("event") == "worker_reserved"
            and identifier(h.get("worker"))
            and attempt
        ]
        head = None
        with contextlib.suppress(*ERRORS):
            claim = self.state / f"issue-{item['issue']}.json"
            pinned = worktree.validate(claim, ready=False)
            head = worktree.git(
                Path(pinned["checkout"]),
                "rev-parse",
                "HEAD",
                git_dir=Path(pinned["git_dir"]),
            )
        evidence = []
        for entry in history:
            if entry.get("event") != "progress":
                continue
            with contextlib.suppress(*ERRORS):
                public = progress.validate(
                    {k: v for k, v in entry.items() if k not in {"at", "event"}},
                    self.expected["repository"],
                )
                evidence.append(
                    public
                    | {
                        "at": stamp(entry.get("at")),
                        "source": "coordinator-recorded",
                        "freshness": "current"
                        if head and public.get("revision") == head
                        else "stale"
                        if head and public.get("revision")
                        else "unknown",
                    }
                )
        timing = {}
        with contextlib.suppress(*ERRORS):
            timed_workers = [w | w["timing"] for w in workers]
            derived = coordinate.issue_view(
                item, timed_workers, datetime.now(UTC).isoformat()
            )
            timing = {
                "elapsed": number(derived.get("elapsed")),
                "phases": {
                    key: number(derived["phases"].get(key))
                    for key in (
                        "implement",
                        "review",
                        "worker_setup",
                        "human_review_wait",
                        "coordinator",
                    )
                },
            }
        pr = item.get("pr") or {}
        return {
            "issue": item["issue"],
            "attempt": attempt,
            "activity": item.get("activity")
            if item.get("activity") in admission.ACTIVITIES
            else "unknown",
            "workers": workers,
            "timing": timing,
            "evidence": evidence,
            "pr": progress.reference(pr.get("url"), self.expected["repository"]),
            **coordinate.rounds([w["role"] for w in workers]),
            "readiness": next(
                (
                    e["state"]
                    for e in reversed(evidence)
                    if e["kind"] == "readiness" and e["freshness"] == "current"
                ),
                "unknown",
            ),
        }

    def snapshot(self) -> dict:
        """Revalidate and filter full claims before deriving any selected rows."""
        with admission.locked(self.state):
            admission.require_context(admission.policy(self.state), self.expected)
        self.refresh_dependencies()
        with admission.locked(self.state):
            queue = admission.policy(self.state)
            admission.require_context(queue, self.expected)
            claims = [
                item
                for item in admission.records(self.state)
                if item.get("repository") == queue["repository"]
                and item.get("queue") == queue["id"]
                and type(item.get("issue")) is int
                and item.get("issue") in queue["issues"]
            ]
            used = admission.capacity(self.state)
        selected = {item["issue"]: self.issue(item) for item in claims}
        with admission.locked(self.state):
            admission.require_context(admission.policy(self.state), self.expected)
        return {
            "at": datetime.now(UTC).isoformat(),
            "repository": queue["repository"],
            "queue": identifier(queue["id"]),
            "mode": queue["mode"],
            "coordinator_liveness": "unknown",
            "limits": queue["limits"],
            "clone_wide_used": used,
            "quota": {
                "state": "paused"
                if queue.get("quota")
                and (
                    queue["quota"].get("retry_at") is None
                    or queue["quota"]["retry_at"] > time.time()
                )
                else "window_elapsed"
                if queue.get("quota")
                else "unknown",
                "retry_at": number((queue.get("quota") or {}).get("retry_at")),
            },
            "controls": [
                {"event": h["event"], "at": stamp(h.get("at"))}
                for h in queue.get("history", [])
                if h.get("event") in {"running", "paused", "cancelled", "quota_paused"}
            ],
            "dependencies": self.dependencies,
            "issues": [
                selected.get(
                    n,
                    {
                        "issue": n,
                        "activity": "unclaimed",
                        "readiness": "unknown",
                        "workers": [],
                        "evidence": [],
                    },
                )
                for n in queue["issues"]
            ],
        }


class Server(HTTPServer):
    """Single foreground service with private in-memory browser sessions."""

    def __init__(self, binding: Binding, port: int = 0) -> None:
        """Bind IPv4 loopback only; no wildcard or remote bind option."""
        self.binding = binding
        self.capability = secrets.token_urlsafe(32)
        self.sessions: dict[str, str] = {}
        super().__init__(("127.0.0.1", port), Handler)
        self.origin = f"http://127.0.0.1:{self.server_port}"
        self.cookie_name = f"ballast_session_{self.server_port}"

    @property
    def url(self) -> str:
        """Return a fragment capability, never a query credential."""
        return f"{self.origin}/#{self.capability}"


class Handler(BaseHTTPRequestHandler):
    """Fixed assets and authenticated JSON only; never serve arbitrary files."""

    server: Server

    def setup(self) -> None:
        """Bound slow or incomplete requests."""
        super().setup()
        self.connection.settimeout(3)

    def log_message(self, *_args: object) -> None:
        """Keep URLs, capabilities and backend diagnostics out of logs."""

    def reply(
        self,
        status: int,
        value: object,
        content_type: str = "application/json",
        cookie: str | None = None,
    ) -> None:
        """Apply the same restrictive headers to success and errors."""
        body = value if isinstance(value, bytes) else json.dumps(value).encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type + "; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'none'; script-src 'self'; style-src 'self'; "
            "connect-src 'self'; base-uri 'none'; form-action 'none'; "
            "frame-ancestors 'none'",
        )
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Connection", "close")
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()
        self.wfile.write(body)
        self.close_connection = True

    def send_error(
        self, code: int, _message: str | None = None, _explain: str | None = None
    ) -> None:
        """Use fixed protected errors even for unsupported HTTP methods."""
        self.reply(code, {"error": "Request denied"})

    def host_ok(self) -> bool:
        """Reject rebinding and ambiguous Host headers."""
        return self.headers.get_all("Host") == [
            self.server.origin.removeprefix("http://")
        ]

    def session(self) -> str | None:
        """Accept only a previously exchanged private browser cookie."""
        cookie = SimpleCookie()
        try:
            cookie.load(self.headers.get("Cookie", ""))
        except (CookieError, ValueError):
            return None
        item = cookie.get(self.server.cookie_name)
        return self.server.sessions.get(item.value) if item else None

    def do_GET(self) -> None:
        """Read fixed assets or the explicitly bound, authorized snapshot."""
        if not self.host_ok():
            self.reply(403, {"error": "Host denied"})
        elif self.path in FILES:
            name, mime = FILES[self.path]
            self.reply(200, (ASSETS / name).read_bytes(), mime)
        elif self.path == "/api/snapshot" and self.session():
            try:
                self.reply(200, self.server.binding.snapshot())
            except ERRORS:
                self.reply(
                    409, {"error": "Context unavailable; return to main conversation"}
                )
        else:
            self.reply(403, {"error": "Request denied"})

    def do_POST(self) -> None:
        """Exchange a capability or request one existing bounded control."""
        if not self.host_ok() or self.headers.get_all("Origin") != [self.server.origin]:
            self.reply(403, {"error": "Origin denied"})
            return
        lengths = self.headers.get_all("Content-Length", [])
        if (
            self.headers.get("Content-Type") != "application/json"
            or len(lengths) != 1
            or len(lengths[0]) > len(str(MAX_BODY))
            or not lengths[0].isdigit()
            or not 0 < int(lengths[0]) <= MAX_BODY
            or self.headers.get("Transfer-Encoding")
        ):
            self.reply(400, {"error": "Bounded JSON required"})
            return
        try:
            data = json.loads(self.rfile.read(int(lengths[0])))
            if not isinstance(data, dict):
                raise TypeError
            if (
                self.path == "/api/session"
                and set(data) == {"capability"}
                and isinstance(data["capability"], str)
                and hmac.compare_digest(data["capability"], self.server.capability)
            ):
                token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
                if len(self.server.sessions) >= MAX_SESSIONS:
                    del self.server.sessions[next(iter(self.server.sessions))]
                self.server.sessions[token] = csrf
                self.reply(
                    200,
                    {"csrf": csrf},
                    cookie=(
                        f"{self.server.cookie_name}={token}; "
                        "HttpOnly; SameSite=Strict; Path=/api"
                    ),
                )
                return
            csrf = self.session()
            if not csrf or not hmac.compare_digest(
                self.headers.get("X-Ballast-CSRF", ""), csrf
            ):
                self.reply(403, {"error": "Authorization denied"})
                return
            if (
                self.path == "/api/control"
                and set(data) == {"action"}
                and data["action"] in {"paused", "running", "cancelled"}
            ):
                admission.control(
                    self.server.binding.state,
                    data["action"],
                    "dashboard-request",
                    expected=self.server.binding.expected,
                )
                self.reply(200, {"requested": data["action"]})
                return
            self.reply(400, {"error": "Unsupported request"})
        except ERRORS:
            self.reply(
                409,
                {"error": "Control outcome unknown; observe before acting"},
            )


def main() -> int:
    """Bind or explicitly create a queue; print URL and serve in foreground."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cwd", type=Path, required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--queue")
    parser.add_argument("--coordinator", required=True)
    parser.add_argument("--create", action="store_true")
    parser.add_argument("--issue", type=int, action="append")
    parser.add_argument("--revision")
    parser.add_argument("--port", type=int, default=0)
    args = parser.parse_args()
    if worktree.inside_checkout():
        # A server running in a checkout would block a worker's quiet check.
        sys.stderr.write("Dashboard blocked: start it outside issue checkouts\n")
        return 1
    try:
        cwd = args.cwd.resolve(strict=True)
        if os.environ.get("BALLAST_COORDINATOR") != args.coordinator:
            admission.fail("Explicit coordinator ownership required")
        if args.create:
            if args.queue or not args.issue or not args.revision:
                parser.error("create requires issues and revision, without queue")
            worktree.repository(cwd, args.repo)
            queue = admission.create(
                coordinate.state_directory(cwd),
                admission.QueueSpec(
                    args.repo,
                    args.issue,
                    admission.DEFAULTS.copy(),
                    args.coordinator,
                    args.revision,
                ),
            )
            args.queue = queue["id"]
        elif not args.queue or args.issue or args.revision:
            parser.error(
                "observation requires explicit queue; creation inputs need --create"
            )
        binding = Binding(cwd, args.repo, args.queue, args.coordinator)
        with Server(binding, args.port) as server:
            sys.stdout.write(server.url + "\n")
            sys.stdout.flush()
            server.serve_forever()
    except KeyboardInterrupt:
        return 0
    except ERRORS:
        sys.stderr.write(
            "Dashboard blocked: verify explicit context in main conversation\n"
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
