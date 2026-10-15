"""Execute one explicit, verified Codex worker outside CI (foreground only)."""

from __future__ import annotations

import argparse
import contextlib
import json
import math
import os
import queue
import re
import select
import shutil
import subprocess
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

# Direct isolated invocation loads only this operator-selected source tree.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools import admission, codex, worktree

MAX_TEXT = 65536
MAX_RUNTIME = 900
POLL_SECONDS = 1.0
QUIET_GAP_SECONDS = 0.2
INTERRUPT_SECONDS = 30
MAX_NAMED = 10


class WorkerServer(codex.AppServer):
    """Task-capable transport; the qualification probe stays task-free."""

    methods = codex.AppServer.methods | {
        "account/read",
        "turn/start",
        "turn/interrupt",
    }
    options = ("-c", 'forced_login_method="chatgpt"', "--disable", "multi_agent")

    def __init__(self, executable: str, cwd: Path, timeout: float) -> None:
        """Retain only bounded final output and completion metadata."""
        if os.name != "posix":
            codex.fail("This worker requires POSIX bounded pipe writes")
        self.thread_id = ""
        self.finished: dict | None = None
        self.output = ""
        self.tokens: dict | None = None
        self.windows: dict = {}
        super().__init__(executable, cwd, timeout)

    def send(self, message: dict) -> None:
        """Bound pipe writes too, including a backend that stops reading input."""
        if message.get("method") not in self.methods:
            codex.fail("Method is outside the worker allowlist")
        stream = self.process.stdin
        if stream is None:
            codex.fail("Worker input is unavailable")
        descriptor = stream.fileno()
        os.set_blocking(descriptor, False)
        pending = memoryview(json.dumps(message).encode() + b"\n")
        while pending:
            remaining = self.deadline - time.monotonic()
            if remaining <= 0 or not select.select([], [descriptor], [], remaining)[1]:
                codex.fail("Worker input timed out")
            try:
                written = os.write(descriptor, pending)
            except BlockingIOError:
                continue
            if written <= 0:
                codex.fail("Worker input closed")
            pending = pending[written:]

    def poll(self, wait: float) -> dict | None:
        """Read one message or return None so the caller can observe controls."""
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            codex.fail("Worker timed out")
        try:
            message = self.messages.get(timeout=min(wait, remaining))
        except queue.Empty:
            return None
        if not isinstance(message, dict):
            codex.fail("Worker ended or returned malformed JSON")
        return message

    def interrupt(self, turn: str) -> None:
        """Request a stop and bound the wait for terminal evidence."""
        self.send(
            {
                "id": "worker-interrupt",
                "method": "turn/interrupt",
                "params": {"threadId": self.thread_id, "turnId": turn},
            }
        )
        self.deadline = min(self.deadline, time.monotonic() + INTERRUPT_SECONDS)

    def retry_at(self) -> float | None:
        """Use only a backend-provided reset time for an exhausted window."""
        times = [
            window["resetsAt"]
            for window in self.windows.values()
            if isinstance(window, dict)
            and type(window.get("usedPercent")) is int
            and window["usedPercent"] >= 100  # noqa: PLR2004 -- exhausted window
            and type(window.get("resetsAt")) is int
        ]
        return max(times, default=None)

    def usage(self, method: object, params: dict) -> None:
        """Keep only quota window timing and token totals, never account data."""
        if method == "account/rateLimits/updated":
            limits = params.get("rateLimits")
            if isinstance(limits, dict):
                self.windows.update(
                    (key, limits[key])
                    for key in ("primary", "secondary")
                    if isinstance(limits.get(key), dict)
                )
        elif method == "thread/tokenUsage/updated" and (
            params.get("threadId") == self.thread_id
        ):
            usage = params.get("tokenUsage")
            if isinstance(usage, dict) and isinstance(usage.get("total"), dict):
                self.tokens = {
                    key: value
                    for key, value in usage["total"].items()
                    if type(value) is int
                }

    def notification(self, message: dict) -> None:
        """Keep final messages, never reasoning, account data or raw tool output."""
        method = message.get("method")
        params = message.get("params", {})
        if not isinstance(params, dict):
            return
        self.usage(method, params)
        if params.get("threadId") != self.thread_id:
            return
        if method == "item/completed":
            item = params.get("item", {})
            if not isinstance(item, dict):
                codex.fail("Worker item notification is malformed")
            if item.get("type") == "agentMessage":
                output = item.get("text")
                if not isinstance(output, str) or len(output.encode()) > MAX_TEXT:
                    codex.fail("Worker final output is malformed or too large")
                self.output = output
        elif method == "turn/completed":
            final = params.get("turn")
            if not isinstance(final, dict):
                codex.fail("Worker completion notification is malformed")
            self.finished = final


def event(directory: Path, kind: str, **values: object) -> None:
    """Append a scrubbed milestone to private local state."""
    with (directory / "events.jsonl").open("a") as stream:
        stream.write(
            json.dumps({"at": datetime.now(UTC).isoformat(), "event": kind, **values})
            + "\n"
        )


def establish(
    server: WorkerServer, cwd: Path, model: str, effort: str, role: str
) -> dict:
    """Validate subscription access and executing thread before task input."""
    initialized = server.request(
        "initialize", {"clientInfo": {"name": "ballast_v2_worker", "version": "0.1.0"}}
    )
    server.send({"method": "initialized", "params": {}})
    account = server.request("account/read", {"refreshToken": False}).get("account")
    if not isinstance(account, dict) or account.get("type") != "chatgpt":
        codex.fail("Authorized subscription access could not be established")
    codex.check_capability(server, model, effort)
    sandbox = "read-only" if role == "review" else "workspace-write"
    receipt = server.request(
        "thread/start",
        {
            "model": model,
            "modelProvider": "openai",
            "cwd": str(cwd),
            "sandbox": sandbox,
            "approvalPolicy": "never",
            "ephemeral": True,
            "config": {
                "model_reasoning_effort": effort,
                "sandbox_workspace_write": {
                    "exclude_tmpdir_env_var": True,
                    "exclude_slash_tmp": True,
                    "network_access": False,
                },
            },
        },
    )
    policy = receipt.get("sandbox", {})
    expected = "readOnly" if role == "review" else "workspaceWrite"
    if (
        not isinstance(policy, dict)
        or receipt.get("model") != model
        or receipt.get("reasoningEffort") != effort
        or receipt.get("modelProvider") != "openai"
        or receipt.get("approvalPolicy") != "never"
        or receipt.get("cwd") != str(cwd)
        or policy.get("type") != expected
        or policy.get("networkAccess") is not False
        or policy.get("writableRoots", [])
        or (
            expected == "workspaceWrite"
            and (
                policy.get("writableRoots") != []
                or policy.get("excludeTmpdirEnvVar") is not True
                or policy.get("excludeSlashTmp") is not True
            )
        )
    ):
        codex.fail(
            "Executing session configuration differs from the authorized request"
        )
    thread_record = receipt.get("thread")
    if not isinstance(thread_record, dict):
        codex.fail("Executing session identity is unavailable")
    thread = thread_record.get("id")
    if not isinstance(thread, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", thread):
        codex.fail("Executing session identity is unavailable")
    server.thread_id = thread
    version = re.search(r"/(\d+\.\d+\.\d+)", str(initialized.get("userAgent", "")))
    route = {"provider": "openai", "model": model, "effort": effort}
    return {
        "requested": route,
        "observed": route.copy(),
        "source": "codex-app-server:thread/start",
        "client_version": version[1] if version else "unknown",
        "session": thread,
        "role": role,
        "sandbox": expected,
        "task_started": False,
    }


def run_turn(
    server: WorkerServer, cwd: Path, text: str, directory: Path, result: dict
) -> tuple[str, str | None]:
    """Wait for a correlated terminal turn; observe cancellation meanwhile."""
    boundary = (
        "Work only on the assigned task in this checkout. "
        "Do not invoke ballast, spawn agents, change model/provider, access "
        "credentials, publish, merge, or release. "
        "Report consequential ambiguity as blocked. "
    )
    turn = server.request(
        "turn/start",
        {
            "threadId": server.thread_id,
            "model": result["requested"]["model"],
            "effort": result["requested"]["effort"],
            "cwd": str(cwd),
            "approvalPolicy": "never",
            "input": [{"type": "text", "text": boundary + text}],
        },
    )
    turn_record = turn.get("turn")
    if not isinstance(turn_record, dict):
        codex.fail("Worker turn receipt is malformed")
    turn_id = turn_record.get("id")
    if not isinstance(turn_id, str) or not turn_id:
        codex.fail("Worker turn identity is missing")
    result["task_started"] = True
    event(directory, "task_accepted", turn=turn_id)
    return settle_turn(server, turn_id, directory)


def await_terminal(server: WorkerServer, turn_id: str, directory: Path) -> bool:
    """Wait for the turn's terminal notification; return whether we interrupted."""
    state = directory.parents[1]
    interrupted = False
    while server.finished is None:
        if not interrupted and admission.cancelled(state):
            server.interrupt(turn_id)
            interrupted = True
            event(directory, "interrupt_requested")
        message = server.poll(POLL_SECONDS)
        if message is None:
            continue
        if message.get("id") == "worker-interrupt" and interrupted:
            if "error" in message:
                codex.fail("Backend rejected the interrupt; outcome unknown")
            continue
        if "id" in message or not isinstance(message.get("method"), str):
            codex.fail("Unexpected worker response or approval request")
        server.notification(message)
    return interrupted


def settle_turn(
    server: WorkerServer, turn_id: str, directory: Path
) -> tuple[str, str | None]:
    """Classify only backend-confirmed terminal states; others stay unknown."""
    interrupted = await_terminal(server, turn_id, directory)
    final = server.finished
    if not isinstance(final, dict) or final.get("id") != turn_id:
        codex.fail("Worker did not report a matching turn completion")
    error = final.get("error")
    kind = error.get("codexErrorInfo") if isinstance(error, dict) else None
    if interrupted and final.get("status") == "interrupted":
        return "cancelled", None
    if final.get("status") == "failed" and kind in admission.QUOTA_ERRORS:
        return "quota", kind
    if final.get("status") != "completed" or error:
        codex.fail("Worker did not report a successful matching turn completion")
    if not server.output:
        codex.fail("Worker did not return final output")
    return "completed", None


def read_task(task: Path) -> str:
    """Bound task input before starting a client."""
    with task.open("rb") as stream:
        content = stream.read(MAX_TEXT + 1)
    if not content or len(content) > MAX_TEXT:
        codex.fail("Task input must contain between one and 65536 bytes")
    return content.decode()


def check_launch(model: str, effort: str, timeout: float) -> None:
    """Reject CI, implicit routes and unbounded runtime before native work."""
    codex.check_environment(os.environ)
    if worktree.inside_checkout():
        codex.fail("Start the worker outside issue checkouts")
    if not math.isfinite(timeout) or not 0 < timeout <= MAX_RUNTIME:
        codex.fail("Worker timeout must be finite and between zero and 900 seconds")
    if not all(
        re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", value)
        for value in (model, effort)
    ):
        codex.fail("Worker model and effort must be explicit identifiers")


def started(entry: Path) -> int:
    """Return a process's start time in clock ticks since boot (stat field 22)."""
    return int((entry / "stat").read_text().rsplit(")", 1)[1].split()[19])


def describe(pids: list[int]) -> str:
    """Name survivors by PID and command name; arguments may hold secrets."""
    names = []
    for pid in pids[:MAX_NAMED]:
        try:
            comm = (
                (Path("/proc") / str(pid) / "comm").read_text(errors="replace").strip()
            )
        except OSError:
            comm = "?"
        names.append(f"{pid} ({''.join(c if c.isprintable() else '?' for c in comm)})")
    more = len(pids) - MAX_NAMED
    return ", ".join(names) + (f", and {more} more" if more > 0 else "")


def survivors(cwd: Path) -> list[int]:
    """List processes still running inside the checkout; Linux /proc only.

    A same-user process started after this worker whose working directory
    cannot be read counts as a survivor: unreadable is unknown, never stopped.
    Older ones (session managers, agents) cannot belong to this worker.
    """
    proc = Path("/proc")
    if not (proc / "self" / "cwd").exists():
        codex.fail("Cannot confirm worker processes stopped on this host")
    birth = started(proc / "self")
    found = []
    for entry in proc.iterdir():
        if not entry.name.isdigit():
            continue
        try:
            where = (entry / "cwd").readlink()
        except (FileNotFoundError, ProcessLookupError):
            continue
        except OSError:
            with contextlib.suppress(OSError, ValueError, IndexError):
                if entry.stat().st_uid == os.getuid() and started(entry) >= birth:
                    found.append(int(entry.name))
            continue
        if where == cwd or cwd in where.parents:
            found.append(int(entry.name))
    return found


def await_quiet(cwd: Path) -> None:
    """Settle only when nothing still runs in the checkout; else stay unknown."""
    deadline = time.monotonic() + INTERRUPT_SECONDS
    # ponytail: two empty scans a short gap apart narrow, but cannot close, a race
    # with a process forking mid-scan; a cgroup per worker would close it.
    empty = 0
    while empty < 2:  # noqa: PLR2004 -- consecutive empty scans
        if found := survivors(cwd):
            empty = 0
            if time.monotonic() >= deadline:
                codex.fail(
                    "Processes still run in the checkout; outcome unknown: "
                    + describe(found)
                )
            time.sleep(POLL_SECONDS)
        else:
            empty += 1
            time.sleep(QUIET_GAP_SECONDS)


def keep_output(
    server: WorkerServer, directory: Path, result: dict, outcome: str
) -> None:
    """Keep a completed turn's output even if settlement later stays unknown."""
    if outcome == "completed":
        (directory / "output.txt").write_text(server.output)
        result["turn"] = "completed"


def record_outcome(
    server: WorkerServer,
    claim: Path,
    result: dict,
    terminal: tuple[str, str | None],
) -> None:
    """Persist a confirmed terminal turn and any structured quota pause."""
    outcome, kind = terminal
    result.update(status=outcome, tokens=server.tokens or "unavailable")
    if outcome == "quota":
        result["retry_at"] = server.retry_at()
        admission.quota(claim.parent, kind or "unknown", result["retry_at"])


def reserve(claim: Path, identifier: str, role: str) -> Path:
    """Reserve capacity and the private worker directory, or neither."""
    admission.reserve_worker(claim, identifier, role)
    directory = claim.parent / "workers" / identifier
    try:
        directory.mkdir(parents=True, mode=0o700)
    except OSError:
        admission.release_worker(claim, identifier)  # Nothing was started.
        raise
    return directory


def execute(
    claim: Path, task: Path, *, route: tuple[str, str], role: str, timeout: float
) -> dict:
    """Own one foreground worker; uncertain attempts retain their exclusive lock."""
    model, effort = route
    check_launch(model, effort, timeout)
    record = worktree.validate(claim)
    cwd = Path(record["checkout"])
    git_dir = Path(record["git_dir"])
    text = read_task(task)
    executable = shutil.which("codex")
    if executable is None:
        codex.fail("Codex is not installed on PATH")
    identifier = uuid.uuid4().hex
    directory = reserve(claim, identifier, role)
    started = False
    settled = False
    result = {
        "worker": identifier,
        "attempt": record["attempt"],
        "role": role,
        "status": "not_started",
        "task_started": False,
    }
    try:
        event(directory, "created", role=role, model=model, effort=effort)
        head = worktree.git(cwd, "rev-parse", "HEAD", git_dir=git_dir)
        if role == "review" and worktree.git(
            cwd, "status", "--porcelain", git_dir=git_dir
        ):
            codex.fail("Independent review requires a clean, committed head")
        with contextlib.closing(
            WorkerServer(str(Path(executable).resolve()), cwd, timeout)
        ) as server:
            receipt = establish(server, cwd, model, effort, role)
            result.update(receipt)
            worktree.write_record(directory / "result.json", result)
            event(directory, "route_verified", **receipt)
            # Pause/cancel after this permit treats the turn as already active.
            admission.permit_turn(claim, identifier, role)
            # Persist possible delivery BEFORE writing; a lost response is unknown.
            started = True
            result.update(status="unknown", task_started="unknown")
            worktree.write_record(directory / "result.json", result)
            event(directory, "task_dispatched")
            outcome, kind = run_turn(server, cwd, text, directory, result)
            keep_output(server, directory, result, outcome)
        # Close/reap must succeed before calling the worker settled. Sandboxed
        # tool commands run in their own session and can outlive the client.
        await_quiet(cwd)
        result.update(
            head_before=head,
            head_after=worktree.git(cwd, "rev-parse", "HEAD", git_dir=git_dir),
        )
        record_outcome(server, claim, result, (outcome, kind))
        if role == "review" and (
            result["head_after"] != head
            or worktree.git(cwd, "status", "--porcelain", git_dir=git_dir)
        ):
            codex.fail("Reviewed checkout changed; review evidence is invalid")
        settled = True
    except admission.FixedReasonError as error:
        result["reason"] = str(error)
        raise
    finally:
        if not settled:
            result["status"] = "unknown" if started else "not_started"
        worktree.write_record(directory / "result.json", result)
        event(directory, result["status"])
        if settled or not started:
            admission.release_worker(claim, identifier)
    return result


def main() -> int:
    """Emit a receipt; worker output remains private for coordinator inspection."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--claim", type=Path, required=True)
    parser.add_argument("--task", type=Path, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--effort", required=True)
    parser.add_argument("--role", choices=("implement", "review"), required=True)
    parser.add_argument("--timeout", type=float, default=300)
    args = parser.parse_args()
    try:
        result = execute(
            args.claim.resolve(strict=True),
            args.task,
            route=(args.model, args.effort),
            role=args.role,
            timeout=args.timeout,
        )
    except admission.FixedReasonError as error:
        codex.emit({"status": "blocked", "reason": str(error)})
        return 1
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.SubprocessError):
        codex.emit(
            {
                "status": "blocked",
                "reason": "Worker failed; inspect local attempt state before retrying",
            }
        )
        return 1
    codex.emit(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
