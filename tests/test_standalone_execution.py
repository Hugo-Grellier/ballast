"""Deterministic standalone execution checks; no real agent process or host calls."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tests.test_codex_routing import MemoryProcess, response
from tools import codex, worker, worktree


class ExecutionTests(unittest.TestCase):
    """Exercise native Git identity and scripted app-server boundaries together."""

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        worktree.git(self.repo, "init", "-b", "main")
        worktree.git(self.repo, "config", "user.name", "Fictional Author")
        worktree.git(self.repo, "config", "user.email", "fictional@example.invalid")
        worktree.git(
            self.repo,
            "remote",
            "add",
            "origin",
            "https://github.com/example/fixture.git",
        )
        (self.repo / "example.txt").write_text("fictional\n")
        worktree.git(self.repo, "add", ".")
        worktree.git(self.repo, "commit", "-m", "fixture")
        self.base = worktree.git(self.repo, "rev-parse", "HEAD")
        worktree.git(self.repo, "update-ref", "refs/remotes/origin/main", self.base)
        self.host_calls: list[list[str]] = []
        native = worktree.command

        def hosting(argv: list[str], cwd: Path) -> str:
            if argv[0] != "gh":
                return native(argv, cwd)
            self.host_calls.append(argv)
            if "/issues/" in argv[-1]:
                return json.dumps(
                    {
                        "number": int(argv[-1].rsplit("/", 1)[-1]),
                        "state": "open",
                        "body": "Fictional leaf acceptance",
                    }
                )
            return json.dumps({"object": {"sha": self.base}})

        self.patcher = patch.object(worktree, "command", side_effect=hosting)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        self.claim = worktree.prepare(self.repo, "example/fixture", 7, "main")
        self.record = json.loads(self.claim.read_text())
        self.cwd = Path(self.record["checkout"])
        self.task = self.root / "task.txt"
        self.task.write_text("Inspect the fictional fixture and report.")
        self.environment = patch.dict(os.environ, dict.fromkeys(codex.CI_MARKERS, ""))
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def script(self, *, account: str = "chatgpt", **overrides: object) -> list[dict]:
        receipt = {
            "model": "fixture-model",
            "reasoningEffort": "low",
            "modelProvider": "openai",
            "cwd": str(self.cwd),
            "approvalPolicy": "never",
            "thread": {"id": "fixture-thread"},
            "sandbox": {
                "type": "workspaceWrite",
                "networkAccess": False,
                "writableRoots": [],
                "excludeTmpdirEnvVar": True,
                "excludeSlashTmp": True,
            },
        }
        receipt.update(overrides)
        return [
            response(1, {"userAgent": "fixture/1.2.3"}),
            response(2, {"account": {"type": account}}),
            response(
                3,
                {
                    "data": [
                        {
                            "model": "fixture-model",
                            "supportedReasoningEfforts": [{"reasoningEffort": "low"}],
                        }
                    ]
                },
            ),
            response(4, receipt),
            # Notifications may precede the turn/start response.
            {
                "method": "item/completed",
                "params": {
                    "threadId": "fixture-thread",
                    "item": {"type": "agentMessage", "text": "Fictional result"},
                },
            },
            {
                "method": "turn/completed",
                "params": {
                    "threadId": "fixture-thread",
                    "turn": {
                        "id": "fixture-turn",
                        "status": "completed",
                        "error": None,
                    },
                },
            },
            response(5, {"turn": {"id": "fixture-turn"}}),
        ]

    def run_worker(self, messages: list[dict], *, role: str = "implement") -> dict:
        process = MemoryProcess(messages)
        process.stdin = self.enterContext(tempfile.TemporaryFile(mode="w+b"))
        native_popen = subprocess.Popen

        def launch(argv: list[str], **kwargs: object) -> object:
            if argv[0] == "/fictional/codex":
                return process
            return native_popen(argv, **kwargs)

        with (
            patch.object(codex.subprocess, "Popen", side_effect=launch),
            patch.object(worker.shutil, "which", return_value="/fictional/codex"),
        ):
            return worker.execute(
                self.claim,
                self.task,
                route=("fixture-model", "low"),
                role=role,
                timeout=2,
            )

    def test_linked_worktree_and_duplicate_claim(self) -> None:
        self.assertEqual(worktree.validate(self.claim)["base_sha"], self.base)
        with self.assertRaisesRegex(RuntimeError, "already claimed"):
            worktree.prepare(self.cwd, "example/fixture", 7, "main")
        for argv in self.host_calls:
            self.assertEqual(argv[2:4], ["--hostname", "github.com"])

    def test_wrong_repository_and_branch_block(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "Origin"):
            worktree.repository(self.repo, "example/other")
        worktree.git(self.cwd, "switch", "-c", "unassigned")
        with self.assertRaisesRegex(RuntimeError, "branch"):
            worktree.validate(self.claim)

    def test_worker_written_gitfile_cannot_run_host_commands(self) -> None:
        # A writing worker controls its checkout, including the `.git` gitfile.
        evil = self.root / "evil.git"
        shutil.copytree(self.repo / ".git", evil)
        marker = self.root / "executed"
        with (evil / "config").open("a") as stream:
            stream.write(f'[filter "fixture"]\n\tclean = touch {marker}; cat\n')
        (self.cwd / ".git").write_text(f"gitdir: {evil}\n")
        (self.cwd / ".gitattributes").write_text("* filter=fixture\n")
        time.sleep(0.01)
        (self.cwd / "example.txt").write_text("changed\n")
        result = self.run_worker(self.script())
        self.assertFalse(marker.exists())
        self.assertEqual(result["head_after"], self.base)

    def test_stale_base_and_setup_failure_preserve_state(self) -> None:
        self.base = "different"
        with self.assertRaisesRegex(RuntimeError, "stale"):
            worktree.prepare(self.repo, "example/fixture", 8, "main")
        self.base = self.record["base_sha"]
        # Failure after exclusive claim keeps evidence and prevents blind retries.
        self.claim.unlink()
        native = worktree.git

        def broken(cwd: Path, *args: str, **kwargs: object) -> str:
            if args[0] == "worktree":
                worktree.fail("Fictional setup failure")
            return native(cwd, *args, **kwargs)

        with (
            patch.object(worktree, "git", side_effect=broken),
            self.assertRaisesRegex(RuntimeError, "setup failure"),
        ):
            worktree.prepare(self.repo, "example/fixture", 7, "main")
        self.assertEqual(json.loads(self.claim.read_text())["status"], "setup_failed")

    def test_malformed_host_responses_fail_closed(self) -> None:
        for payload in (None, [], {"sub_issues_summary": None}):
            with (
                self.subTest(payload=payload),
                patch.object(worktree, "command", return_value=json.dumps(payload)),
                self.assertRaises(RuntimeError),
            ):
                worktree.integration_revision(self.repo, "example/fixture", "main")

    def test_completed_worker_records_receipt_before_dispatch(self) -> None:
        result = self.run_worker(self.script())
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["requested"], result["observed"])
        directory = self.claim.parent / "workers" / result["worker"]
        events = [
            json.loads(line)
            for line in (directory / "events.jsonl").read_text().splitlines()
        ]
        names = [event["event"] for event in events]
        self.assertLess(names.index("route_verified"), names.index("task_dispatched"))
        self.assertFalse(self.claim.with_suffix(".worker").exists())
        self.assertEqual((directory / "output.txt").read_text(), "Fictional result")

    def test_invalid_routes_and_access_never_dispatch(self) -> None:
        for changes in (
            {"account": "apiKey"},
            {"account": "unknown"},
            {"reasoningEffort": "medium"},
            {"model": "other"},
            {"sandbox": None},
            {"thread": None},
            {"cwd": "/unassigned"},
        ):
            with (
                self.subTest(changes=changes),
                self.assertRaises(codex.QualificationError),
            ):
                self.run_worker(self.script(**changes))
            self.assertFalse(self.claim.with_suffix(".worker").exists())
        for record in (self.claim.parent / "workers").glob("*/events.jsonl"):
            self.assertNotIn("task_dispatched", record.read_text())

    def test_unconfirmed_completion_retains_lock(self) -> None:
        messages = self.script()
        messages[5]["params"]["turn"]["status"] = "failed"
        with self.assertRaises(codex.QualificationError):
            self.run_worker(messages)
        self.assertTrue(self.claim.with_suffix(".worker").exists())
        with self.assertRaises(FileExistsError):
            self.run_worker(self.script())
        results = list((self.claim.parent / "workers").glob("*/result.json"))
        self.assertEqual(json.loads(results[0].read_text())["status"], "unknown")

    def test_malformed_notification_preserves_unknown(self) -> None:
        messages = self.script()
        messages[4]["params"]["item"] = None
        with self.assertRaises(codex.QualificationError):
            self.run_worker(messages)
        self.assertTrue(self.claim.with_suffix(".worker").exists())

    def test_missing_write_roots_blocks_before_dispatch(self) -> None:
        messages = self.script()
        del messages[3]["result"]["sandbox"]["writableRoots"]
        with self.assertRaises(codex.QualificationError):
            self.run_worker(messages)
        self.assertFalse(self.claim.with_suffix(".worker").exists())

    def test_dirty_review_and_ci_block_without_process(self) -> None:
        (self.cwd / "example.txt").write_text("changed\n")
        with (
            patch.object(worker, "WorkerServer") as process,
            self.assertRaises(codex.QualificationError),
        ):
            worker.execute(
                self.claim,
                self.task,
                route=("fixture-model", "low"),
                role="review",
                timeout=2,
            )
        process.assert_not_called()
        with (
            patch.dict(os.environ, {"CI": "true"}),
            patch.object(worker, "WorkerServer") as process,
            self.assertRaises(codex.QualificationError),
        ):
            worker.execute(
                self.claim,
                self.task,
                route=("fixture-model", "low"),
                role="implement",
                timeout=2,
            )
        process.assert_not_called()

    def test_stopped_reader_cannot_block_task_write(self) -> None:
        read_descriptor, write_descriptor = os.pipe()
        self.addCleanup(os.close, read_descriptor)
        stream = self.enterContext(os.fdopen(write_descriptor, "wb"))
        os.set_blocking(write_descriptor, False)
        while True:
            try:
                os.write(write_descriptor, b"x" * 4096)
            except BlockingIOError:
                break
        server = worker.WorkerServer.__new__(worker.WorkerServer)
        server.process = SimpleNamespace(stdin=stream)
        server.deadline = time.monotonic() + 0.01
        with self.assertRaisesRegex(codex.QualificationError, "timed out"):
            server.send({"method": "turn/start", "params": {"private": "fictional"}})

    def test_corrupt_claim_blocks_before_process(self) -> None:
        self.claim.write_text("null")
        with self.assertRaisesRegex(RuntimeError, "malformed"):
            worktree.validate(self.claim)

    def test_main_uses_explicit_pair_and_sanitizes_errors(self) -> None:
        args = [
            "worker.py",
            "--claim",
            str(self.claim),
            "--task",
            str(self.task),
            "--model",
            "fixture-model",
            "--effort",
            "low",
            "--role",
            "implement",
        ]
        with (
            patch("sys.argv", args),
            patch.object(
                worker, "execute", return_value={"status": "completed"}
            ) as execute,
            patch.object(codex, "emit"),
        ):
            self.assertEqual(worker.main(), 0)
            self.assertEqual(
                execute.call_args.kwargs["route"], ("fixture-model", "low")
            )


if __name__ == "__main__":
    unittest.main()


class OriginFormTests(unittest.TestCase):
    """The origin must name github.com verifiably and carry no credentials."""

    ACCEPTED = (
        "https://github.com/example/fixture",
        "https://github.com/example/fixture.git/",
        "git@github.com:example/fixture.git",
        "ssh://git@github.com/example/fixture",
        "ssh://git@github.com/example/fixture.git",
        "ssh://git@github.com/example/fixture.git/",
        "ssh://git@github.com/Example/Fixture.git",
    )
    REFUSED = (
        "ssh://git@github-work/example/fixture.git",
        "git@github-work:example/fixture.git",
        "ssh://git@github.com.evil.example/example/fixture.git",
        "ssh://user:secret@github.com/example/fixture.git",
        "ssh://other@github.com/example/fixture.git",
        "ssh://github.com/example/fixture.git",
        "ssh://git@github.com:2222/example/fixture.git",
        "ssh://git@github.com/example/other.git",
        "https://token@github.com/example/fixture",
        "https://user:secret@github.com/example/fixture",
        "https://example.com/example/fixture",
    )

    def check(self, origin: str) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            worktree.git(repo, "init", "-b", "main")
            worktree.git(repo, "remote", "add", "origin", origin)
            worktree.repository(repo, "example/fixture")

    def test_accepted_origins(self) -> None:
        for origin in self.ACCEPTED:
            with self.subTest(origin=origin):
                self.check(origin)

    def test_refused_origins(self) -> None:
        for origin in self.REFUSED:
            with (
                self.subTest(origin=origin),
                self.assertRaisesRegex(RuntimeError, "Origin"),
            ):
                self.check(origin)
