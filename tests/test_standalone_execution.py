"""Deterministic standalone execution checks; no real agent process or host calls."""

from __future__ import annotations

import contextlib
import json
import os
import queue
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tests.test_codex_routing import MemoryProcess, response
from tools import admission, codex, coordinate, worker, worktree

ROOT = Path(__file__).resolve().parents[1]
# The worker's scratch path holds its fresh identifier; run_worker fills it in.
SCRATCH = "/fixture-scratch"


def setUpModule() -> None:
    """Run from a neutral directory, never from an issue checkout (#233).

    The helpers refuse to start inside one (`worktree.inside_checkout`), and the
    gate itself may run from a `worktree.py` checkout. Modules that launch
    helpers import this.
    """
    directory = tempfile.TemporaryDirectory()
    unittest.addModuleCleanup(directory.cleanup)
    unittest.enterModuleContext(contextlib.chdir(directory.name))


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

    def script(
        self, *, account: str = "chatgpt", role: str = "implement", **overrides: object
    ) -> list[dict]:
        review = role == "review"
        receipt = {
            "model": "fixture-model",
            "reasoningEffort": "low",
            "modelProvider": "openai",
            # A review thread works in its scratch; the checkout is in no root.
            "cwd": SCRATCH if review else str(self.cwd),
            "approvalPolicy": "never",
            "thread": {"id": "fixture-thread"},
            "sandbox": {
                "type": "workspaceWrite",
                "networkAccess": False,
                "writableRoots": [] if review else [SCRATCH],
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

    def bind_scratch(self, messages: list[dict], role: str) -> tuple[list, object]:
        """Fill the next worker's scratch path in; return a patch fixing its id."""
        identifier = uuid.uuid4().hex
        scratch = self.claim.parent / "scratch" / f"{role}-{identifier}"
        bound = json.loads(json.dumps(messages).replace(SCRATCH, str(scratch)))
        fixed = SimpleNamespace(hex=identifier)
        return bound, patch.object(worker.uuid, "uuid4", return_value=fixed)

    def run_worker(
        self, messages: list[dict], *, role: str = "implement", timeout: float = 2
    ) -> dict:
        messages, identity = self.bind_scratch(messages, role)
        process = MemoryProcess(messages)
        process.stdin = self.enterContext(tempfile.TemporaryFile(mode="w+b"))
        native_popen = subprocess.Popen

        def launch(argv: list[str], **kwargs: object) -> object:
            if argv[0] == "/fictional/codex":
                return process
            return native_popen(argv, **kwargs)

        with (
            identity,
            patch.object(codex.subprocess, "Popen", side_effect=launch),
            patch.object(worker.shutil, "which", return_value="/fictional/codex"),
        ):
            return worker.execute(
                self.claim,
                self.task,
                route=("fixture-model", "low"),
                role=role,
                timeout=timeout,
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

    def test_inherited_git_variables_cannot_redirect_helper_git(self) -> None:
        # Hostile caller environment: another index and an empty object store.
        before = worktree.validate(self.claim)
        status = worktree.git(self.cwd, "status", "--porcelain")
        objects = self.root / "empty-objects"
        objects.mkdir()
        hostile = {
            "GIT_INDEX_FILE": str(self.root / "hostile-index"),
            "GIT_OBJECT_DIRECTORY": str(objects),
            "GIT_CONFIG_COUNT": "1",
            "GIT_CONFIG_KEY_0": "core.hooksPath",
            "GIT_CONFIG_VALUE_0": str(self.root),
        }
        with patch.dict(os.environ, hostile):
            self.assertEqual(worktree.validate(self.claim), before)
            self.assertEqual(worktree.git(self.cwd, "status", "--porcelain"), status)
        self.assertFalse((self.root / "hostile-index").exists())

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

    def test_handoff_forbids_clone_wide_git_state(self) -> None:
        # Worktrees of one clone share the stash and branch refs (#235).
        request = worker.WorkerServer.request
        with patch.object(
            worker.WorkerServer, "request", autospec=True, side_effect=request
        ) as sent:
            self.assertEqual(self.run_worker(self.script())["status"], "completed")
        (turn,) = [c.args[2] for c in sent.call_args_list if c.args[1] == "turn/start"]
        text = turn["input"][0]["text"]
        for rule in ("git stash", "git worktree", "switching branches", "git diff"):
            self.assertIn(rule, text)

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

    def scratches(self) -> list[Path]:
        return list((self.claim.parent / "scratch").glob("*"))

    def threads(self, messages: list[dict], role: str, turn=None) -> dict:  # noqa: ANN001
        """Run one worker; return what it asked thread/start for, and its result."""
        request = worker.WorkerServer.request
        sent = {}

        def record(server: worker.WorkerServer, method: str, params: dict) -> dict:
            sent[method] = params
            if method == "turn/start" and turn:
                turn(sent["thread/start"])
            return request(server, method, params)

        with patch.object(worker.WorkerServer, "request", autospec=True) as wrapped:
            wrapped.side_effect = record
            sent["result"] = self.run_worker(messages, role=role)
        return sent

    def test_each_role_writes_only_its_private_scratch(self) -> None:
        for role in ("implement", "review"):
            with self.subTest(role=role):
                sent = self.threads(self.script(role=role), role)
                result, thread = sent["result"], sent["thread/start"]
                scratch = self.claim.parent / "scratch" / f"{role}-{result['worker']}"
                self.assertEqual(result["status"], "completed")
                self.assertEqual(thread["sandbox"], "workspace-write")
                writes = thread["config"]["sandbox_workspace_write"]
                excluded = (
                    writes["exclude_tmpdir_env_var"],
                    writes["exclude_slash_tmp"],
                )
                self.assertEqual(excluded, (True, True))
                if role == "review":  # The checkout is in no write root.
                    self.assertEqual(thread["cwd"], str(scratch))
                    self.assertEqual(writes["writable_roots"], [])
                    self.assertEqual(result["checkout_access"], "read-only")
                else:
                    self.assertEqual(thread["cwd"], str(self.cwd))
                    self.assertEqual(writes["writable_roots"], [str(scratch)])
                self.assertEqual(sent["turn/start"]["cwd"], thread["cwd"])
                self.assertIn(str(self.cwd), sent["turn/start"]["input"][0]["text"])
                environment = thread["config"]["shell_environment_policy"]["set"]
                self.assertEqual(environment, worker.scratch_env(scratch))
                for value in environment.values():
                    self.assertTrue(Path(value).is_relative_to(scratch))
                self.assertEqual(self.scratches(), [])  # Removed once settled.

    def test_receipt_must_show_exactly_the_scratch_root(self) -> None:
        roots = (
            ("implement", {"writableRoots": []}),
            ("implement", {"writableRoots": [SCRATCH, "/elsewhere"]}),
            ("implement", {"writableRoots": ["/elsewhere"]}),
            ("review", {"writableRoots": [SCRATCH]}),
            ("review", {"writableRoots": [str(self.cwd)]}),
            ("implement", {"excludeTmpdirEnvVar": False}),
            ("review", {"excludeSlashTmp": False}),
            ("review", {"type": "readOnly"}),
        )
        for role, change in roots:
            receipt = self.script(role=role)[3]["result"]
            sandbox = {**receipt["sandbox"], **change}
            with (
                self.subTest(role=role, change=change),
                self.assertRaisesRegex(codex.QualificationError, "differs"),
            ):
                self.run_worker(self.script(role=role, sandbox=sandbox), role=role)
            self.assertFalse(self.claim.with_suffix(".worker").exists())
            self.assertEqual(self.scratches(), [])
        # A review thread that works in the checkout could write it.
        with self.assertRaisesRegex(codex.QualificationError, "differs"):
            self.run_worker(
                self.script(role="review", cwd=str(self.cwd)), role="review"
            )
        for record in (self.claim.parent / "workers").glob("*/events.jsonl"):
            self.assertNotIn("task_dispatched", record.read_text())

    def test_review_test_with_temp_files_leaves_checkout_clean(self) -> None:
        created = []

        def focused_test(thread: dict) -> None:
            # A tool command as the client runs it: thread cwd and environment.
            code = (
                "import tempfile; print(tempfile.NamedTemporaryFile(delete=False).name)"
            )
            ran = subprocess.run(  # noqa: S603 -- this interpreter, fixed code
                [sys.executable, "-I", "-c", code],
                cwd=thread["cwd"],
                env={
                    **os.environ,
                    **thread["config"]["shell_environment_policy"]["set"],
                },
                capture_output=True,
                text=True,
                check=True,
            )
            created.append(Path(ran.stdout.strip()))

        sent = self.threads(self.script(role="review"), "review", focused_test)
        self.assertEqual(sent["result"]["status"], "completed")
        (path,) = created
        self.assertTrue(path.is_relative_to(self.claim.parent / "scratch"))
        self.assertFalse(path.exists())
        self.assertEqual(
            worktree.git(self.cwd, "status", "--porcelain", "--ignored"), ""
        )

    @unittest.skipUnless(shutil.which("uv"), "uv required")
    def test_uv_run_with_scratch_environment_leaves_checkout_untouched(self) -> None:
        scratch = self.root / "scratch"
        scratch.mkdir()
        environment = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith(("UV_", "VIRTUAL_ENV", "XDG_CACHE"))
        }
        subprocess.run(  # noqa: S603 -- resolved uv, fixed argv
            [
                *(shutil.which("uv"), "run", "--no-project", "--offline"),
                *("python", "-c", "import tempfile; tempfile.mkstemp()"),
            ],
            cwd=self.cwd,
            env={**environment, **worker.scratch_env(scratch)},
            capture_output=True,
            check=True,
        )
        self.assertEqual(
            worktree.git(self.cwd, "status", "--porcelain", "--ignored"), ""
        )
        self.assertTrue((scratch / "uv").is_dir())

    def test_unconfirmed_completion_retains_lock(self) -> None:
        messages = self.script()
        messages[5]["params"]["turn"]["status"] = "failed"
        with self.assertRaises(codex.QualificationError):
            self.run_worker(messages)
        self.assertTrue(self.claim.with_suffix(".worker").exists())
        self.assertEqual(len(self.scratches()), 1)  # Kept as `unknown` evidence.
        with self.assertRaisesRegex(
            admission.AdmissionError, "Another worker holds this issue"
        ):
            self.run_worker(self.script())
        results = list((self.claim.parent / "workers").glob("*/result.json"))
        self.assertEqual(json.loads(results[0].read_text())["status"], "unknown")

    def test_unbound_client_lifetime_never_starts_client(self) -> None:
        # The refusal comes from launch options, before any client process exists.
        with (
            patch.object(worker.ctypes, "CDLL", side_effect=OSError),
            self.assertRaisesRegex(codex.QualificationError, "Linux"),
        ):
            self.run_worker(self.script())
        self.assertFalse(self.claim.with_suffix(".worker").exists())
        results = list((self.claim.parent / "workers").glob("*/result.json"))
        self.assertEqual(json.loads(results[0].read_text())["status"], "not_started")

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

    def test_interrupt_bound_ends_a_silent_backend(self) -> None:
        server = worker.WorkerServer.__new__(worker.WorkerServer)
        server.messages = queue.Queue()
        server.deadline = time.monotonic() - 1
        server.interrupted = False
        # At the deadline the caller still has to interrupt the turn.
        self.assertIsNone(server.poll(worker.POLL_SECONDS))
        server.interrupted = True
        with self.assertRaisesRegex(codex.QualificationError, "timed out"):
            server.poll(worker.POLL_SECONDS)

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
        handlers = []

        def run(*_: object, **__: object) -> dict:
            handlers.append(signal.getsignal(signal.SIGTERM))
            handlers.append(signal.getsignal(signal.SIGINT))
            return {"status": "completed"}

        before = signal.getsignal(signal.SIGTERM)
        with (
            patch("sys.argv", args),
            patch.object(worker, "execute", side_effect=run) as execute,
            patch.object(codex, "emit"),
        ):
            self.assertEqual(worker.main(), 0)
            self.assertEqual(
                execute.call_args.kwargs["route"], ("fixture-model", "low")
            )
        # Stop signals settle through the worker while it runs, then are restored.
        self.assertEqual(handlers, [worker.request_stop] * 2)
        self.assertIs(signal.getsignal(signal.SIGTERM), before)

    def test_main_reports_fixed_reasons_and_stays_generic_otherwise(self) -> None:
        args = ["worker.py", "--claim", str(self.claim), "--task", str(self.task)]
        args += ["--model", "m", "--effort", "low", "--role", "implement"]
        for error, reason in (
            (worktree_error("Fictional fixed reason"), "Fictional fixed reason"),
            (RuntimeError("private payload"), "Worker failed; inspect local"),
        ):
            with (
                patch("sys.argv", args),
                patch.object(worker, "execute", side_effect=error),
                patch.object(codex, "emit") as emit,
            ):
                self.assertEqual(worker.main(), 1)
                shown = emit.call_args.args[0]["reason"]
                self.assertTrue(shown.startswith(reason), shown)
                self.assertNotIn("private", shown)
        with (
            patch(
                "sys.argv",
                ["worktree.py", "--repo", "r", "--issue", "1", "--base", "b"],
            ),
            patch.object(worktree, "prepare", side_effect=worktree_error("Fixed.")),
            patch("sys.stderr") as stderr,
        ):
            self.assertEqual(worktree.main(), 1)
            self.assertIn("Fixed.", stderr.write.call_args.args[0])

    def worker_reason(self) -> str:
        args = ["worker.py", "--claim", str(self.claim), "--task", str(self.task)]
        args += ["--model", "m", "--effort", "low", "--role", "implement"]
        with (
            patch("sys.argv", args),
            patch.object(worker.shutil, "which", return_value="/fictional/codex"),
            patch.object(codex, "emit") as emit,
        ):
            self.assertEqual(worker.main(), 1)
        return emit.call_args.args[0]["reason"]

    def test_worker_main_reports_claim_and_lock_reasons(self) -> None:
        self.claim.with_suffix(".worker").write_text("{}")
        self.assertEqual(self.worker_reason(), "Another worker holds this issue")
        self.claim.with_suffix(".worker").unlink()
        worktree.mark(self.claim, "preparing")
        self.assertEqual(
            self.worker_reason(),
            "Claim is not ready or belongs to another Git repository",
        )

    def test_coordinate_main_reports_fixed_reasons_only(self) -> None:
        for error, shown in (
            (worktree_error("Fixed reason."), "Fixed reason."),
            (RuntimeError("private payload"), "RuntimeError"),
        ):
            with (
                patch("sys.argv", ["coordinate.py", "status"]),
                patch.object(coordinate, "run", side_effect=error),
                patch("sys.stderr") as stderr,
            ):
                self.assertEqual(coordinate.main(), 1)
                text = stderr.write.call_args.args[0]
                self.assertIn(shown, text)
                self.assertNotIn("private", text)


def worktree_error(reason: str) -> Exception:
    """Capture the exception worktree.fail raises."""
    try:
        worktree.fail(reason)
    except admission.FixedReasonError as error:
        return error
    raise AssertionError


class CheckoutCwdTests(unittest.TestCase):
    """The gate passes when started from a worktree.py issue checkout (#233)."""

    def test_helper_launching_test_passes_from_a_ballast_v2_cwd(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            checkout = Path(temporary, "ballast-v2", "worktrees", "issue-1-x")
            checkout.mkdir(parents=True)
            name = "test_completed_worker_records_receipt_before_dispatch"
            result = subprocess.run(  # noqa: S603 -- fixed argv
                [
                    *(sys.executable, "-m", "unittest"),
                    f"tests.test_standalone_execution.ExecutionTests.{name}",
                ],
                cwd=checkout,
                env={**os.environ, "PYTHONPATH": str(ROOT)},
                capture_output=True,
                text=True,
                timeout=300,
                check=False,
            )
        self.assertEqual(result.returncode, 0, result.stderr)


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

    def check(self, origin: str, expected: str = "example/fixture") -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            worktree.git(repo, "init", "-b", "main")
            worktree.git(repo, "remote", "add", "origin", origin)
            worktree.repository(repo, expected)

    def test_dot_segments_refused(self) -> None:
        forms = (
            "https://github.com/{}",
            "git@github.com:{}.git",
            "ssh://git@github.com/{}.git",
        )
        for expected in ("../example", "example/..", "./example", "example/."):
            for form in forms:
                with (
                    self.subTest(expected=expected, form=form),
                    self.assertRaisesRegex(RuntimeError, "Repository|Origin"),
                ):
                    self.check(form.format(expected), expected)
        # The origin alone is refused even when the request is a valid name.
        for origin in (
            "https://github.com/../example",
            "ssh://git@github.com/example/..git",
        ):
            with (
                self.subTest(origin=origin),
                self.assertRaisesRegex(RuntimeError, "Origin"),
            ):
                self.check(origin, "example/fixture")

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
