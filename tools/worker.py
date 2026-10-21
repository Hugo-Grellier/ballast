"""Execute one explicit, verified Codex worker outside CI (foreground only)."""

from __future__ import annotations

import argparse
import contextlib
import ctypes
import json
import math
import os
import queue
import re
import select
import shutil
import signal
import subprocess
import sys
import threading
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

# Direct isolated invocation loads only this operator-selected source tree.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools import admission, codex, worktree

if TYPE_CHECKING:
    from collections.abc import Iterator

MAX_TEXT = 65536
MAX_RUNTIME = 900
POLL_SECONDS = 1.0
QUIET_GAP_SECONDS = 0.2
INTERRUPT_SECONDS = 30
QUIET_SECONDS = 30
# Extra quiet wait after a confirmed interrupt: a sandboxed tool command can
# outlive it (#242).
SURVIVOR_SECONDS = 120
MAX_NAMED = 10
STOP_SIGNALS = (signal.SIGTERM, signal.SIGINT)
PR_SET_PDEATHSIG = 1  # <linux/prctl.h>
# Set by SIGTERM/SIGINT; the worker settles through the interrupt path.
stopping = threading.Event()


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
        self.workdir = cwd
        self.interrupted = False
        self.finished: dict | None = None
        self.output = ""
        self.tokens: dict | None = None
        self.windows: dict = {}
        super().__init__(executable, cwd, timeout)

    @staticmethod
    def isolation() -> dict:
        """Keep the client out of group-wide signals, but never let it outlive us.

        In its own session, a signal to the worker's PID or process group (a
        terminal Ctrl-C) reaches only the worker, which then interrupts the turn;
        a recursive tree kill that signals each descendant still reaches the
        client. The kernel SIGKILLs the client if the worker dies first (Linux
        parent-death signal).
        """
        try:
            prctl = ctypes.CDLL(None, use_errno=True).prctl
        except (OSError, AttributeError):
            codex.fail("This worker requires Linux to bind its client's lifetime")
        parent = os.getpid()

        def die_with_worker() -> None:
            # Bound to the forking thread; execute() starts the client from main.
            if prctl(PR_SET_PDEATHSIG, signal.SIGKILL) != 0:
                raise OSError(ctypes.get_errno(), "prctl")
            if os.getppid() != parent:  # The worker died before prctl took effect.
                raise ProcessLookupError

        return {"start_new_session": True, "preexec_fn": die_with_worker}

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
            if self.interrupted:
                codex.fail("Worker timed out")
            return None  # The caller interrupts the turn at its deadline.
        try:
            message = self.messages.get(timeout=min(wait, remaining))
        except queue.Empty:
            return None
        if not isinstance(message, dict):
            codex.fail("Worker ended or returned malformed JSON")
        return message

    def interrupt(self, turn: str) -> None:
        """Request a stop; wait at most INTERRUPT_SECONDS more, even past timeout."""
        self.interrupted = True
        self.deadline = time.monotonic() + INTERRUPT_SECONDS
        self.send(
            {
                "id": "worker-interrupt",
                "method": "turn/interrupt",
                "params": {"threadId": self.thread_id, "turnId": turn},
            }
        )

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


def scratch_env(scratch: Path) -> dict[str, str]:
    """Point temp files and tool caches into the worker's scratch directory."""
    return {
        "TMPDIR": str(scratch),
        "UV_CACHE_DIR": str(scratch / "uv"),
        "XDG_CACHE_HOME": str(scratch / "cache"),
    }


def sandbox_roots(role: str, cwd: Path, scratch: Path) -> tuple[Path, list[str]]:
    """Return the thread's working directory and its exact extra write roots.

    Both roles write only the scratch directory outside the checkout. A review
    thread works in the scratch directory itself, so the checkout stays outside
    every write root: the client folds a root equal to its cwd away.
    """
    if role == "review":
        return scratch, []
    return cwd, [str(scratch)]


def establish(
    server: WorkerServer, cwd: Path, scratch: Path, route: tuple[str, str], role: str
) -> dict:
    """Validate subscription access and executing thread before task input."""
    model, effort = route
    initialized = server.request(
        "initialize", {"clientInfo": {"name": "ballast_v2_worker", "version": "0.1.0"}}
    )
    server.send({"method": "initialized", "params": {}})
    account = server.request("account/read", {"refreshToken": False}).get("account")
    if not isinstance(account, dict) or account.get("type") != "chatgpt":
        codex.fail("Authorized subscription access could not be established")
    codex.check_capability(server, model, effort)
    workdir, roots = sandbox_roots(role, cwd, scratch)
    receipt = server.request(
        "thread/start",
        {
            "model": model,
            "modelProvider": "openai",
            "cwd": str(workdir),
            "sandbox": "workspace-write",
            "approvalPolicy": "never",
            "ephemeral": True,
            "config": {
                "model_reasoning_effort": effort,
                "sandbox_workspace_write": {
                    "writable_roots": roots,
                    "exclude_tmpdir_env_var": True,
                    "exclude_slash_tmp": True,
                    "network_access": False,
                },
                # Tool commands only: the unsandboxed client keeps its own temp.
                "shell_environment_policy": {"set": scratch_env(scratch)},
            },
        },
    )
    policy = receipt.get("sandbox", {})
    if (
        not isinstance(policy, dict)
        or receipt.get("model") != model
        or receipt.get("reasoningEffort") != effort
        or receipt.get("modelProvider") != "openai"
        or receipt.get("approvalPolicy") != "never"
        or receipt.get("cwd") != str(workdir)
        or policy.get("type") != "workspaceWrite"
        or policy.get("networkAccess") is not False
        or policy.get("writableRoots") != roots
        or policy.get("excludeTmpdirEnvVar") is not True
        or policy.get("excludeSlashTmp") is not True
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
    server.workdir = workdir
    version = re.search(r"/(\d+\.\d+\.\d+)", str(initialized.get("userAgent", "")))
    route = {"provider": "openai", "model": model, "effort": effort}
    return {
        "requested": route,
        "observed": route.copy(),
        "source": "codex-app-server:thread/start",
        "client_version": version[1] if version else "unknown",
        "session": thread,
        "role": role,
        "sandbox": "workspaceWrite",
        "checkout_access": "read-only" if role == "review" else "writable",
        "task_started": False,
    }


def run_turn(
    server: WorkerServer, cwd: Path, text: str, directory: Path, result: dict
) -> tuple[str, str | None]:
    """Wait for a correlated terminal turn; observe cancellation meanwhile."""
    workdir = server.workdir
    boundary = (
        f"Work only on the assigned task in the checkout {cwd}. "
        + (
            "It is read-only and your working directory is a private scratch "
            "directory: cd into the checkout or use git -C to inspect it. "
            if workdir != cwd
            else ""
        )
        + "Temporary files and caches belong in $TMPDIR, never the checkout. "
        "Do not invoke ballast, spawn agents, change model/provider, access "
        "credentials, publish, merge, or release. "
        "Do not use clone-wide Git state (git stash, git worktree, switching "
        "branches): other checkouts share it. Compare with git diff BASE. "
        "Report consequential ambiguity as blocked. "
    )
    turn = server.request(
        "turn/start",
        {
            "threadId": server.thread_id,
            "model": result["requested"]["model"],
            "effort": result["requested"]["effort"],
            "cwd": str(workdir),
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


def await_terminal(server: WorkerServer, turn_id: str, directory: Path) -> str | None:
    """Wait for the turn's terminal notification; return why we interrupted it."""
    state = directory.parents[1]
    reason = None
    while server.finished is None:
        if not server.interrupted:
            if admission.cancelled(state) or stopping.is_set():
                reason = "cancelled"
            elif time.monotonic() >= server.deadline:
                reason = "timeout"
            if reason:
                server.interrupt(turn_id)
                event(directory, "interrupt_requested", reason=reason)
        message = server.poll(POLL_SECONDS)
        if message is None:
            continue
        if message.get("id") == "worker-interrupt" and server.interrupted:
            if "error" in message:
                codex.fail("Backend rejected the interrupt; outcome unknown")
            continue
        if "id" in message or not isinstance(message.get("method"), str):
            codex.fail("Unexpected worker response or approval request")
        server.notification(message)
    return reason


def settle_turn(
    server: WorkerServer, turn_id: str, directory: Path
) -> tuple[str, str | None]:
    """Classify only backend-confirmed terminal states; others stay unknown."""
    reason = await_terminal(server, turn_id, directory)
    final = server.finished
    if not isinstance(final, dict) or final.get("id") != turn_id:
        codex.fail("Worker did not report a matching turn completion")
    error = final.get("error")
    kind = error.get("codexErrorInfo") if isinstance(error, dict) else None
    if reason and final.get("status") == "interrupted":
        return reason, None
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


def await_quiet(roots: tuple[Path, ...], bound: float) -> float | None:
    """Settle only when nothing runs in the checkout or scratch; else unknown.

    Return the seconds spent waiting on survivors, or None if none was seen.
    """
    start = time.monotonic()
    deadline = start + bound
    seen = None
    # ponytail: two empty scans a short gap apart narrow, but cannot close, a race
    # with a process forking mid-scan; a cgroup per worker would close it.
    empty = 0
    while empty < 2:  # noqa: PLR2004 -- consecutive empty scans
        if found := sorted({pid for root in roots for pid in survivors(root)}):
            empty = 0
            seen = True
            if time.monotonic() >= deadline:
                codex.fail(
                    "Processes still run in the checkout; outcome unknown: "
                    + describe(found)
                )
            time.sleep(POLL_SECONDS)
        else:
            empty += 1
            time.sleep(QUIET_GAP_SECONDS)
    return time.monotonic() - start if seen else None


def settle_quiet(roots: tuple[Path, ...], directory: Path, outcome: str) -> None:
    """Wait longer after a confirmed interrupt; its tool command may still run."""
    interrupted = outcome in {"cancelled", "timeout"}
    waited = await_quiet(roots, QUIET_SECONDS + SURVIVOR_SECONDS * interrupted)
    if interrupted and waited is not None:
        event(directory, "survivors_exited", seconds=round(waited, 1))


def remove_scratch(scratch: Path, directory: Path) -> None:
    """Remove a settled worker's scratch; an `unknown` one stays as evidence.

    A leftover is recorded, never fatal: each worker has its own directory.
    """
    try:
        shutil.rmtree(scratch)  # Symlink-safe on Linux: never leaves the tree.
    except OSError:
        event(directory, "scratch_left")


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


def request_stop(*_: object) -> None:
    """Signal handler: only flag the stop; the worker settles it."""
    stopping.set()


@contextlib.contextmanager
def stop_on_signals() -> Iterator[None]:
    """Turn SIGTERM/SIGINT into a stop request, then restore prior handlers."""
    stopping.clear()
    previous = {number: signal.signal(number, request_stop) for number in STOP_SIGNALS}
    try:
        yield
    finally:
        for number, handler in previous.items():
            signal.signal(number, handler)
        stopping.clear()


def check_stop() -> None:
    """Refuse to reserve or dispatch work after a stop signal."""
    if stopping.is_set():
        codex.fail("Worker stopped by a signal before dispatch")


def permit(claim: Path, identifier: str, role: str) -> None:
    """Refuse dispatch after a stop signal; else take the queue's turn permit."""
    check_stop()
    admission.permit_turn(claim, identifier, role)


def reserve(claim: Path, identifier: str, role: str) -> tuple[Path, Path]:
    """Reserve capacity, the private worker directory and its scratch, or none.

    One scratch per worker, so an `unknown` worker's kept scratch never collides.
    """
    check_stop()  # A stop before reservation never starts a client.
    admission.reserve_worker(claim, identifier, role)
    directory = claim.parent / "workers" / identifier
    scratch = claim.parent / "scratch" / f"{role}-{identifier}"
    try:
        directory.mkdir(parents=True, mode=0o700)
        scratch.mkdir(parents=True, mode=0o700)
    except OSError:
        admission.release_worker(claim, identifier)  # Nothing was started.
        raise
    return directory, scratch


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
    directory, scratch = reserve(claim, identifier, role)
    dispatched = settled = False
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
            receipt = establish(server, cwd, scratch, route, role)
            result.update(receipt)
            admission.write(directory / "result.json", result)
            event(directory, "route_verified", **receipt)
            # Pause/cancel after this permit treats the turn as already active.
            permit(claim, identifier, role)
            # Persist possible delivery BEFORE writing; a lost response is unknown.
            dispatched = True
            result.update(status="unknown", task_started="unknown")
            admission.write(directory / "result.json", result)
            event(directory, "task_dispatched")
            outcome, kind = run_turn(server, cwd, text, directory, result)
            keep_output(server, directory, result, outcome)
        # Close/reap must succeed before calling the worker settled. Sandboxed
        # tool commands run in their own session and can outlive the client.
        settle_quiet((cwd, scratch), directory, outcome)
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
            result["status"] = "unknown" if dispatched else "not_started"
        admission.write(directory / "result.json", result)
        event(directory, result["status"])
        if settled or not dispatched:  # Not `unknown`: nothing keeps the scratch.
            remove_scratch(scratch, directory)
            refund = role if settled and result["status"] == "cancelled" else None
            admission.release_worker(claim, identifier, refund)
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
        with stop_on_signals():
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
