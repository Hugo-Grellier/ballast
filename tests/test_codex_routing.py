"""Deterministic routing-protocol checks; never start a real agent in CI."""

from __future__ import annotations

import io
import json
import queue
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import codex as routing


class MemoryProcess:
    """A subprocess-shaped byte stream with observable shutdown."""

    def __init__(self, messages: list[dict] | None = None, raw: bytes = b"") -> None:
        """Provide scripted output without spawning an executable."""
        self.stdin = io.BytesIO()
        self.stdout = io.BytesIO(
            raw
            or b"".join(json.dumps(value).encode() + b"\n" for value in messages or [])
        )
        self.stopped = False

    def poll(self) -> int | None:
        """Report running until explicitly terminated."""
        return 0 if self.stopped else None

    def terminate(self) -> None:
        """Record shutdown."""
        self.stopped = True

    def kill(self) -> None:
        """Record forced shutdown."""
        self.stopped = True

    def wait(self, timeout: float) -> int:
        """Require an explicit shutdown before reaping."""
        if not self.stopped:
            command = "fake"
            raise subprocess.TimeoutExpired(command, timeout)
        return 0


def response(number: int, result: dict) -> dict:
    """Construct a correlated fake backend receipt."""
    return {"id": f"qualify-{number}", "result": result}


def transcript(workdir: Path, **overrides: object) -> list[dict]:
    """Return expected startup, capability and fresh-thread results."""
    receipt = {
        "model": "test-model",
        "modelProvider": "openai",
        "reasoningEffort": "medium",
        "cwd": str(workdir),
        "approvalPolicy": "never",
        "sandbox": {"type": "readOnly", "networkAccess": False},
        "thread": {"id": "test-thread"},
    }
    receipt.update(overrides)
    return [
        response(1, {"userAgent": "probe/1.2.3 (private-machine-data)"}),
        {"method": "thread/started", "params": {"private": "not-public"}},
        response(
            2,
            {
                "data": [
                    {
                        "model": "test-model",
                        "supportedReasoningEfforts": [
                            {"reasoningEffort": "medium"},
                        ],
                    }
                ],
                "nextCursor": None,
            },
        ),
        response(3, receipt),
    ]


class QualificationTests(unittest.TestCase):
    """Exercise receipts and failure paths through the actual pipe reader."""

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.cwd = Path(self.temporary.name).resolve()

    def open_server(self, process: MemoryProcess) -> routing.AppServer:
        """Replace process creation, preserving the real JSON-lines transport."""
        # A generous bound: these tests expect a receipt or a protocol error, so a
        # loaded host must not turn them into a timeout (#241). Timeout behavior
        # is tested by setting the deadline explicitly.
        with patch.object(routing.subprocess, "Popen", return_value=process):
            server = routing.AppServer("fake-codex", self.cwd, 30)
        self.addCleanup(server.close)
        return server

    def test_success_checks_receipt_without_task_input_or_sensitive_output(
        self,
    ) -> None:
        process = MemoryProcess(transcript(self.cwd))
        server = self.open_server(process)
        result = routing.qualify(server, "test-model", "medium", self.cwd)
        self.assertEqual(result["requested"], result["observed"])
        self.assertEqual(result["client_version"], "1.2.3")
        self.assertFalse(result["task_started"])
        encoded = json.dumps(result)
        self.assertNotIn(str(self.cwd), encoded)
        self.assertNotIn("private", encoded)
        requests = [json.loads(line) for line in process.stdin.getvalue().splitlines()]
        self.assertEqual(
            [value["method"] for value in requests],
            [
                "initialize",
                "initialized",
                "model/list",
                "thread/start",
            ],
        )
        self.assertEqual(
            requests[-1]["params"]["config"],
            {
                "model_reasoning_effort": "medium",
            },
        )
        self.assertTrue(requests[-1]["params"]["ephemeral"])
        server.close()
        self.assertTrue(process.stopped)

    def test_mismatched_or_missing_receipt_never_qualifies(self) -> None:
        variants = [
            {"model": "parent-model"},
            {"reasoningEffort": "high"},
            {"reasoningEffort": None},
            {"modelProvider": "other"},
            {"cwd": "elsewhere"},
            {"approvalPolicy": "on-request"},
            {"sandbox": {"type": "dangerFullAccess"}},
            {"thread": None},
            {"thread": {"id": ""}},
        ]
        for override in variants:
            with self.subTest(override=override):
                server = self.open_server(
                    MemoryProcess(transcript(self.cwd, **override))
                )
                with self.assertRaises(routing.QualificationError):
                    routing.qualify(server, "test-model", "medium", self.cwd)

    def test_unsupported_effort_stops_before_thread_creation(self) -> None:
        process = MemoryProcess(transcript(self.cwd))
        server = self.open_server(process)
        with self.assertRaisesRegex(routing.QualificationError, "supported catalog"):
            routing.qualify(server, "test-model", "ultra", self.cwd)
        self.assertNotIn(b"thread/start", process.stdin.getvalue())

    def test_catalog_pages_are_followed_and_repeated_cursor_is_rejected(self) -> None:
        messages = transcript(self.cwd)
        catalog = messages[2]["result"]
        messages[2] = response(2, {"data": [], "nextCursor": "next-page"})
        messages.insert(3, response(3, catalog))
        messages[-1]["id"] = "qualify-4"
        process = MemoryProcess(messages)
        server = self.open_server(process)
        self.assertEqual(
            routing.qualify(server, "test-model", "medium", self.cwd)["status"],
            "qualified",
        )
        broken = [
            response(1, {}),
            response(2, {"data": [], "nextCursor": "same"}),
            response(3, {"data": [], "nextCursor": "same"}),
        ]
        with self.assertRaisesRegex(routing.QualificationError, "pagination"):
            routing.qualify(
                self.open_server(MemoryProcess(broken)),
                "test-model",
                "medium",
                self.cwd,
            )

    def test_protocol_errors_eof_and_malformed_json_are_not_receipts(self) -> None:
        cases = [
            MemoryProcess(raw=b"invalid-json\n"),
            MemoryProcess(),
            MemoryProcess([{"id": "qualify-1", "error": {"message": "private"}}]),
            MemoryProcess([response(99, {})]),
            MemoryProcess([response(1, {}), response(2, {"data": None})]),
            MemoryProcess(raw=b"x" * (routing.MAX_MESSAGE + 1)),
        ]
        for process in cases:
            with self.subTest(process=process):
                with self.assertRaises(routing.QualificationError) as caught:
                    routing.qualify(
                        self.open_server(process), "test-model", "medium", self.cwd
                    )
                self.assertNotIn("private", str(caught.exception))

    def test_shared_deadline_and_request_allowlist(self) -> None:
        server = self.open_server(MemoryProcess())
        server.messages = queue.Queue()
        server.deadline = 0
        with self.assertRaisesRegex(routing.QualificationError, "timed out"):
            server.request("model/list", {})
        with self.assertRaisesRegex(routing.QualificationError, "allowlist"):
            server.send({"method": "turn/start", "params": {}})

    def test_hung_process_is_killed_and_reaped(self) -> None:
        process = MemoryProcess()
        server = self.open_server(process)
        with (
            patch.object(
                process,
                "wait",
                side_effect=[
                    subprocess.TimeoutExpired("fake", 2),
                    subprocess.TimeoutExpired("fake", 2),
                    0,
                ],
            ),
            patch.object(process, "kill", wraps=process.kill) as kill,
        ):
            server.close()
        kill.assert_called_once()

    def test_ci_refuses_before_process_creation(self) -> None:
        for marker in routing.CI_MARKERS:
            with (
                self.subTest(marker=marker),
                patch.dict(routing.os.environ, {marker: "true"}, clear=True),
                patch.object(routing, "AppServer") as start,
                patch.object(
                    routing.sys,
                    "argv",
                    ["qualify", "--model", "test-model", "--effort", "medium"],
                ),
                patch("sys.stdout", new_callable=io.StringIO) as output,
            ):
                self.assertEqual(routing.main(), 1)
                start.assert_not_called()
                self.assertEqual(json.loads(output.getvalue())["status"], "blocked")

    def test_invalid_arguments_never_launch_a_process(self) -> None:
        for extra in (["--timeout", "nan"], ["--timeout", "0"], ["--model", ""]):
            with (
                self.subTest(extra=extra),
                patch.dict(routing.os.environ, {}, clear=True),
                patch.object(routing, "AppServer") as start,
                patch.object(
                    routing.sys,
                    "argv",
                    [
                        "qualify",
                        "--model",
                        "test-model",
                        "--effort",
                        "medium",
                        *extra,
                    ],
                ),
                patch("sys.stdout", new_callable=io.StringIO) as output,
            ):
                self.assertEqual(routing.main(), 1)
                start.assert_not_called()
                self.assertFalse(json.loads(output.getvalue())["task_started"])

    def probe(self, which: str | None, *extra: str) -> dict:
        """Run the probe with a fictional `codex` lookup; it must never launch."""
        with (
            patch.dict(routing.os.environ, {}, clear=True),
            patch.object(routing.shutil, "which", return_value=which),
            patch.object(routing, "AppServer") as start,
            patch.object(
                routing.sys,
                "argv",
                ["qualify", "--model", "m", "--effort", "low", *extra],
            ),
            patch("sys.stdout", new_callable=io.StringIO) as output,
        ):
            self.assertEqual(routing.main(), 1)
        start.assert_not_called()
        receipt = json.loads(output.getvalue())
        self.assertFalse(receipt["task_started"])
        return receipt

    def test_probe_refuses_a_missing_codex(self) -> None:
        receipt = self.probe(None)
        self.assertEqual(receipt["reason"], "Codex is not installed on PATH")

    def test_probe_refuses_a_cwd_that_is_not_a_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "file"
            file.write_text("fictional")
            receipt = self.probe("/fictional/codex", "--cwd", str(file))
            self.assertEqual(receipt["reason"], "Working directory must be a directory")
            self.probe("/fictional/codex", "--cwd", str(Path(directory) / "missing"))

    def test_nonzero_process_exit_is_not_qualified(self) -> None:
        process = MemoryProcess()
        server = self.open_server(process)
        with (
            patch.object(process, "poll", return_value=1),
            self.assertRaisesRegex(routing.QualificationError, "unsuccessfully"),
        ):
            server.close()

    def test_exit_failure_racing_with_shutdown_is_not_qualified(self) -> None:
        server = self.open_server(MemoryProcess())
        with (
            patch.object(server.process, "poll", return_value=None),
            patch.object(server.process, "wait", return_value=1),
            self.assertRaisesRegex(routing.QualificationError, "unsuccessfully"),
        ):
            server.close()


if __name__ == "__main__":
    unittest.main()
