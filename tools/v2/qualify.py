"""Qualify explicit Codex configuration without sending a model task."""

from __future__ import annotations

import argparse
import contextlib
import json
import math
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING, NoReturn

if TYPE_CHECKING:
    from collections.abc import Mapping

MAX_MESSAGE = 1024 * 1024
MAX_TIMEOUT = 300
CI_MARKERS = (
    "CI",
    "GITHUB_ACTIONS",
    "GITLAB_CI",
    "JENKINS_URL",
    "BUILD_BUILDID",
    "BUILDKITE",
    "CIRCLECI",
    "TF_BUILD",
)


class QualificationError(RuntimeError):
    """The backend did not establish the requested configuration."""


def fail(reason: str) -> NoReturn:
    """Raise a fixed diagnostic without exposing backend payloads."""
    raise QualificationError(reason)


class AppServer:
    """Bounded, task-free JSON-lines connection to an installed Codex client."""

    def __init__(self, executable: str, cwd: Path, timeout: float) -> None:
        """Start the client with pipes; never evaluate a shell command."""
        self.deadline = time.monotonic() + timeout
        self.messages: queue.Queue[object] = queue.Queue(maxsize=16)
        self.sequence = 0
        self.closed = threading.Event()
        self.process = subprocess.Popen(  # noqa: S603 -- caller's resolved CLI, fixed argv, no shell
            [executable, "app-server", "--listen", "stdio://"],
            cwd=cwd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        self.reader = threading.Thread(target=self._read, daemon=True)
        self.reader.start()

    def _read(self) -> None:
        stream = self.process.stdout
        if stream is None:
            return
        try:
            while not self.closed.is_set():
                line = stream.readline(MAX_MESSAGE + 1)
                if not line or len(line) > MAX_MESSAGE:
                    break
                try:
                    message = json.loads(line)
                except (ValueError, UnicodeError):
                    break
                while not self.closed.is_set():
                    try:
                        self.messages.put(message, timeout=0.1)
                        break
                    except queue.Full:
                        continue
        except OSError:
            # Report a fixed protocol failure on the receiving side.
            pass
        finally:
            # An absent message becomes a bounded timeout even if the queue is full.
            with contextlib.suppress(queue.Full):
                self.messages.put_nowait(None)

    def send(self, message: dict) -> None:
        """Write one protocol message; task input has no allowed method."""
        if message.get("method") not in {
            "initialize",
            "initialized",
            "model/list",
            "thread/start",
        }:
            fail("Method is outside the qualification allowlist")
        stream = self.process.stdin
        if stream is None:
            fail("App-server input is unavailable")
        try:
            stream.write(json.dumps(message).encode() + b"\n")
            stream.flush()
        except (BrokenPipeError, OSError):
            fail("App-server input closed")

    def request(self, method: str, params: dict) -> dict:
        """Read the matching response within the shared deadline."""
        self.sequence += 1
        request_id = f"qualify-{self.sequence}"
        self.send({"id": request_id, "method": method, "params": params})
        while True:
            remaining = self.deadline - time.monotonic()
            if remaining <= 0:
                fail("App-server qualification timed out")
            try:
                message = self.messages.get(timeout=remaining)
            except queue.Empty:
                fail("App-server qualification timed out")
            if not isinstance(message, dict):
                fail("App-server ended or returned malformed JSON")
            if "id" not in message and isinstance(message.get("method"), str):
                continue
            if message.get("id") != request_id or "method" in message:
                fail("Unexpected app-server response")
            if "error" in message or not isinstance(message.get("result"), dict):
                fail("App-server rejected qualification or returned a malformed result")
            return message["result"]

    def close(self) -> None:
        """Reap the client and close pipes on success, failure or interruption."""
        self.closed.set()
        return_code = self.process.poll()
        if return_code is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=2)
        self.reader.join(timeout=1)
        for stream in (self.process.stdin, self.process.stdout):
            if stream is not None:
                stream.close()
        if return_code not in (None, 0):
            fail("App-server exited unsuccessfully")


def check_capability(server: AppServer, model: str, effort: str) -> None:
    """Validate a concrete pair against every catalog page."""
    cursor = None
    seen = set()
    supported = False
    while True:
        catalog = server.request("model/list", {"limit": 100, "cursor": cursor})
        entries = catalog.get("data")
        if not isinstance(entries, list):
            fail("Model catalog is malformed")
        for entry in entries:
            if not isinstance(entry, dict):
                fail("Model catalog is malformed")
            if entry.get("model") == model:
                choices = entry.get("supportedReasoningEfforts")
                if not isinstance(choices, list):
                    fail("Model effort capabilities are unavailable")
                supported = any(
                    isinstance(choice, dict) and choice.get("reasoningEffort") == effort
                    for choice in choices
                )
        cursor = catalog.get("nextCursor")
        if cursor is None:
            break
        if not isinstance(cursor, str) or cursor in seen:
            fail("Model catalog pagination is malformed")
        seen.add(cursor)
    if not supported:
        fail("Requested model and effort are not in the supported catalog")


def qualify(server: AppServer, model: str, effort: str, cwd: Path) -> dict:
    """Check the model catalog and resolved thread receipt before any turn."""
    initialized = server.request(
        "initialize",
        {
            "clientInfo": {"name": "ballast_v2_probe", "version": "0.1.0"},
        },
    )
    server.send({"method": "initialized", "params": {}})
    check_capability(server, model, effort)
    receipt = server.request(
        "thread/start",
        {
            "model": model,
            "modelProvider": "openai",
            "cwd": str(cwd),
            "sandbox": "read-only",
            "approvalPolicy": "never",
            "ephemeral": True,
            "config": {"model_reasoning_effort": effort},
        },
    )
    if (
        receipt.get("model") != model
        or receipt.get("reasoningEffort") != effort
        or receipt.get("modelProvider") != "openai"
        or receipt.get("approvalPolicy") != "never"
        or receipt.get("sandbox") != {"type": "readOnly", "networkAccess": False}
        or receipt.get("cwd") != str(cwd)
        or not isinstance(receipt.get("thread"), dict)
        or not isinstance(receipt["thread"].get("id"), str)
        or not receipt["thread"]["id"]
    ):
        fail("Resolved thread configuration is missing or differs from the request")
    user_agent = initialized.get("userAgent")
    version = (
        re.search(r"/(\d+\.\d+\.\d+)", user_agent)
        if isinstance(user_agent, str)
        else None
    )
    return {
        "status": "qualified",
        "scope": "resolved-client-configuration",
        "requested": {"provider": "openai", "model": model, "effort": effort},
        "observed": {"provider": "openai", "model": model, "effort": effort},
        "source": "codex-app-server:thread/start",
        "client_version": version.group(1) if version else "unknown",
        "task_started": False,
    }


def check_environment(environment: Mapping[str, str]) -> None:
    """Refuse agent startup in CI before creating any subprocess."""
    if any(environment.get(marker) for marker in CI_MARKERS):
        fail("Agent configuration qualification is disabled in CI")


def main() -> int:
    """Emit a minimal JSON receipt or a fixed failure diagnostic."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True)
    parser.add_argument("--effort", required=True)
    parser.add_argument("--cwd", type=Path, default=Path.cwd())
    parser.add_argument("--timeout", type=float, default=30)
    args = parser.parse_args()
    try:
        check_environment(os.environ)
        if not math.isfinite(args.timeout) or not 0 < args.timeout <= MAX_TIMEOUT:
            fail("Timeout must be finite and between zero and 300 seconds")
        if not all(
            re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", value)
            for value in (args.model, args.effort)
        ):
            fail("Model and effort must be explicit identifiers")
        executable = shutil.which("codex")
        if executable is None:
            fail("Codex is not installed on PATH")
        cwd = args.cwd.resolve(strict=True)
        if not cwd.is_dir():
            fail("Working directory must be a directory")
        with contextlib.closing(
            AppServer(str(Path(executable).resolve()), cwd, args.timeout)
        ) as server:
            result = qualify(server, args.model, args.effort, cwd)
    except QualificationError as error:
        emit({"status": "blocked", "reason": str(error), "task_started": False})
        return 1
    except (OSError, subprocess.SubprocessError):
        emit(
            {
                "status": "blocked",
                "reason": "Client, directory or confirmed shutdown unavailable",
                "task_started": False,
            }
        )
        return 1
    emit(result)
    return 0


def emit(result: dict) -> None:
    """Write the public JSON result only."""
    sys.stdout.write(json.dumps(result) + "\n")


if __name__ == "__main__":
    sys.exit(main())
