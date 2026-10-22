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
                        "body": "Fictional leaf acceptance\n\nRisk: R0",
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
            # The client's own instructions, outside the repository.
            "instructionSources": ["/fixture-codex-home/AGENTS.md"],
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

    def issue_response(self, payload: object) -> patch:
        """Answer the issue lookup with `payload`; Git and the rest run as set up."""
        previous = worktree.command

        def answer(argv: list[str], cwd: Path) -> str:
            return json.dumps(payload) if argv[0] == "gh" else previous(argv, cwd)

        return patch.object(worktree, "command", side_effect=answer)

    def test_prepare_refuses_targets_that_are_not_open_leaves(self) -> None:
        refused = {"number": 8, "state": "open"}
        for name, payload in {
            "closed": {**refused, "state": "closed"},
            "pull request": {**refused, "pull_request": {}},
            "sub-issues": {**refused, "sub_issues_summary": {"total": 2}},
            "other number": {**refused, "number": 9},
        }.items():
            with (
                self.subTest(name),
                self.issue_response(payload),
                self.assertRaisesRegex(RuntimeError, "open leaf"),
            ):
                worktree.prepare(self.repo, "example/fixture", 8, "main")
            self.assertFalse((self.claim.parent / "issue-8.json").exists())

    def test_prepare_refuses_bad_issue_number_and_base_name(self) -> None:
        calls = len(self.host_calls)
        for issue, base in (
            (0, "main"),
            (-1, "main"),
            (8, ""),
            (8, "-x"),
            (8, "a b"),
            (8, "a;b"),
            (8, "x" * 129),
        ):
            with (
                self.subTest(issue=issue, base=base),
                self.assertRaisesRegex(RuntimeError, "must be explicit"),
            ):
                worktree.prepare(self.repo, "example/fixture", issue, base)
        self.assertEqual(len(self.host_calls), calls)

    def test_prepare_refuses_malformed_issue_response_and_summary(self) -> None:
        for payload in ([], None, "x"):
            with (
                self.subTest(payload=payload),
                self.issue_response(payload),
                self.assertRaisesRegex(RuntimeError, "Issue response is malformed"),
            ):
                worktree.prepare(self.repo, "example/fixture", 8, "main")
        for summary in (None, [], "s", 1):
            body = {"number": 8, "state": "open", "sub_issues_summary": summary}
            with (
                self.subTest(summary=summary),
                self.issue_response(body),
                self.assertRaisesRegex(RuntimeError, "child summary is malformed"),
            ):
                worktree.prepare(self.repo, "example/fixture", 8, "main")

    def test_prepared_checkout_identity_must_match_claim(self) -> None:
        native = worktree.git
        for name, lie in (
            ("head", {("rev-parse", "HEAD"): "0" * 40}),
            ("branch", {("branch", "--show-current"): "other"}),
        ):

            def lying(cwd: Path, *argv: str, lie: dict = lie, **keywords: Path) -> str:
                result = native(cwd, *argv, **keywords)
                return lie.get(argv, result)

            with (
                self.subTest(name),
                patch.object(worktree, "git", side_effect=lying),
                self.assertRaisesRegex(RuntimeError, "identity differs"),
            ):
                worktree.prepare(self.repo, "example/fixture", 8, "main")
            claim = self.claim.parent / "issue-8.json"
            self.assertEqual(json.loads(claim.read_text())["status"], "setup_failed")
            claim.unlink()

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
            modes = []

            def inspect(thread: dict, found: list = modes) -> None:
                roots = thread["config"]["sandbox_workspace_write"]["writable_roots"]
                scratch = Path(roots[0] if roots else thread["cwd"])
                found.append(scratch.stat().st_mode & 0o777)

            with self.subTest(role=role):
                sent = self.threads(self.script(role=role), role, inspect)
                result, thread = sent["result"], sent["thread/start"]
                scratch = self.claim.parent / "scratch" / f"{role}-{result['worker']}"
                self.assertEqual(modes, [0o700])  # Private while the turn runs.
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
                    # No project root search up into the primary checkout.
                    self.assertEqual(thread["config"]["project_root_markers"], [])
                else:
                    self.assertEqual(thread["cwd"], str(self.cwd))
                    self.assertEqual(writes["writable_roots"], [str(scratch)])
                    self.assertNotIn("project_root_markers", thread["config"])
                self.assertEqual(sent["turn/start"]["cwd"], thread["cwd"])
                text = sent["turn/start"]["input"][0]["text"]
                self.assertIn(str(self.cwd), text)
                # Only a review needs telling: it loads no project instructions.
                reading = f"Read {self.cwd}/AGENTS.md and the instructions and skills"
                self.assertEqual(reading in text, role == "review")
                environment = thread["config"]["shell_environment_policy"]["set"]
                self.assertEqual(
                    environment,
                    {
                        "TMPDIR": str(scratch),
                        "UV_CACHE_DIR": str(scratch / "uv"),
                        "XDG_CACHE_HOME": str(scratch / "cache"),
                    },
                )
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
        # A review thread that works in the checkout could write it; one that
        # loaded instructions from above its scratch reads the primary checkout's.
        for change in (
            {"cwd": str(self.cwd)},
            {"instructionSources": [str(self.repo / "AGENTS.md")]},
            {"instructionSources": [f"{SCRATCH}/AGENTS.md"]},
            {"instructionSources": None},
            {"instructionSources": [None]},
        ):
            with (
                self.subTest(change=change),
                self.assertRaisesRegex(codex.QualificationError, "differs"),
            ):
                self.run_worker(self.script(role="review", **change), role="review")
            self.assertEqual(self.scratches(), [])
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

    def test_process_left_in_scratch_keeps_worker_unknown(self) -> None:
        def scan(root: Path) -> list[int]:
            return [4242] if root.parent.name == "scratch" else []

        with (
            patch.object(worker, "survivors", side_effect=scan),
            patch.object(worker, "QUIET_SECONDS", 0),
            self.assertRaisesRegex(codex.QualificationError, r"still run.*\b4242\b"),
        ):
            self.run_worker(self.script())
        self.assertTrue(self.claim.with_suffix(".worker").exists())
        self.assertEqual(len(self.scratches()), 1)

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
            env={
                **environment,
                "TMPDIR": str(scratch),
                "UV_CACHE_DIR": str(scratch / "uv"),
                "XDG_CACHE_HOME": str(scratch / "cache"),
            },
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

    def test_unapproved_r1_implement_never_reserves_or_launches(self) -> None:
        hosted = worktree.command

        def unapproved(argv: list[str], cwd: Path) -> str:
            if argv[0] != "gh":
                return hosted(argv, cwd)
            self.host_calls.append(argv)
            if argv[-1].endswith("/comments"):
                return ""
            return json.dumps({"number": 7, "body": "Risk: R1"})

        with (
            patch.object(worktree, "command", side_effect=unapproved),
            patch.object(worker, "WorkerServer") as process,
            patch.object(worker.shutil, "which", return_value="/fictional/codex"),
            self.assertRaisesRegex(RuntimeError, "No spec delta"),
        ):
            worker.execute(
                self.claim,
                self.task,
                route=("fixture-model", "low"),
                role="implement",
                timeout=2,
            )
        process.assert_not_called()
        self.assertFalse(self.claim.with_suffix(".worker").exists())
        self.assertEqual(
            self.host_calls[-1][-1], "repos/example/fixture/issues/7/comments"
        )

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

    def assert_never_launches(self, reason: str, **overrides: object) -> None:
        """Run the worker and check it refused with nothing reserved or started.

        Codex is present, so only the named validation can be the refusal.
        """
        arguments = {
            "route": ("fixture-model", "low"),
            "role": "implement",
            "timeout": 2,
        } | overrides
        with (
            patch.object(worker, "WorkerServer") as process,
            patch.object(worker.shutil, "which", return_value="/fictional/codex"),
            self.assertRaisesRegex(codex.QualificationError, reason),
        ):
            worker.execute(self.claim, self.task, **arguments)
        process.assert_not_called()
        self.assertFalse(self.claim.with_suffix(".worker").exists())
        self.assertFalse((self.claim.parent / "workers").exists())

    def test_task_input_outside_the_bounds_never_launches(self) -> None:
        for content in (b"", b"x" * 65537):
            with self.subTest(size=len(content)):
                self.task.write_bytes(content)
                with self.assertRaisesRegex(
                    codex.QualificationError, "between one and 65536"
                ):
                    worker.read_task(self.task)
                self.assert_never_launches("between one and 65536")
        self.task.write_bytes(b"x" * 65536)
        self.assertEqual(len(worker.read_task(self.task)), 65536)

    def test_timeout_outside_the_bounds_never_launches(self) -> None:
        for timeout in (float("nan"), float("inf"), 0, -1, 900.5):
            with self.subTest(timeout=timeout):
                self.assert_never_launches("timeout must be finite", timeout=timeout)
        worker.check_launch("fixture-model", "low", 900)

    def test_non_identifier_model_or_effort_never_launches(self) -> None:
        for bad in ("", "-x", "a b", "a/b", "a" * 129):
            for route in ((bad, "low"), ("fixture-model", bad)):
                with self.subTest(route=route):
                    self.assert_never_launches("explicit identifiers", route=route)
        for good in ("a" * 128, "m.1_x-2"):
            worker.check_launch(good, good, 2)

    def test_missing_codex_never_reserves_or_launches(self) -> None:
        with (
            patch.object(worker, "WorkerServer") as process,
            patch.object(worker.shutil, "which", return_value=None),
            self.assertRaisesRegex(codex.QualificationError, "not installed"),
        ):
            worker.execute(
                self.claim,
                self.task,
                route=("fixture-model", "low"),
                role="implement",
                timeout=2,
            )
        process.assert_not_called()
        self.assertFalse(self.claim.with_suffix(".worker").exists())
        self.assertFalse((self.claim.parent / "workers").exists())

    def results(self) -> list[dict]:
        found = (self.claim.parent / "workers").glob("*/result.json")
        return [json.loads(path.read_text()) for path in found]

    def assert_left_unknown(self) -> None:
        """Check the refused worker kept its lock and scratch as evidence."""
        self.assertTrue(self.claim.with_suffix(".worker").exists())
        self.assertEqual(len(self.scratches()), 1)
        (result,) = self.results()
        self.assertEqual(result["status"], "unknown")

    def test_review_that_moves_the_head_is_refused(self) -> None:
        def move(_thread: dict) -> None:
            worktree.git(self.cwd, "commit", "--allow-empty", "-m", "moved")

        with self.assertRaisesRegex(codex.QualificationError, "Reviewed checkout"):
            self.threads(self.script(role="review"), "review", move)
        self.assert_left_unknown()

    def test_review_that_dirties_the_checkout_is_refused(self) -> None:
        def dirty(_thread: dict) -> None:
            (self.cwd / "dirty.txt").write_text("untracked\n")

        with self.assertRaisesRegex(codex.QualificationError, "Reviewed checkout"):
            self.threads(self.script(role="review"), "review", dirty)
        self.assert_left_unknown()

    def test_final_output_over_the_cap_leaves_worker_unknown(self) -> None:
        messages = self.script()
        # 32769 characters but 65537 bytes: the cap counts bytes.
        messages[4]["params"]["item"]["text"] = "é" * 32768 + "x"
        with self.assertRaisesRegex(codex.QualificationError, "too large"):
            self.run_worker(messages)
        self.assert_left_unknown()

    def test_final_output_at_the_cap_is_kept(self) -> None:
        # 65536 bytes either way; the second is only 32768 characters.
        for text in ("x" * 65536, "é" * 32768):
            messages = self.script()
            messages[4]["params"]["item"]["text"] = text
            with self.subTest(characters=len(text)):
                result = self.run_worker(messages)
                self.assertEqual(result["status"], "completed")
                output = self.claim.parent / "workers" / result["worker"]
                self.assertEqual(len((output / "output.txt").read_bytes()), 65536)

    def stray_during_turn(self, stray: dict) -> None:
        """Deliver a message the worker never asked for before the turn ends."""
        messages = self.script()
        messages.insert(4, messages.pop(6))  # The turn/start response comes first.
        messages.insert(5, stray)
        with self.assertRaisesRegex(
            codex.QualificationError, "Unexpected worker response or approval"
        ):
            self.run_worker(messages)
        self.assert_left_unknown()

    def test_unexpected_response_during_a_turn_leaves_worker_unknown(self) -> None:
        self.stray_during_turn({"id": "stray-1", "result": {}})

    def test_approval_request_during_a_turn_leaves_worker_unknown(self) -> None:
        self.stray_during_turn(
            {
                "id": "approval-1",
                "method": "item/commandExecution/requestApproval",
                "params": {},
            }
        )

    def test_failed_scratch_removal_is_recorded_and_not_fatal(self) -> None:
        with patch.object(worker.shutil, "rmtree", side_effect=OSError):
            result = self.run_worker(self.script())
        self.assertEqual(result["status"], "completed")
        self.assertFalse(self.claim.with_suffix(".worker").exists())
        directory = self.claim.parent / "workers" / result["worker"]
        self.assertIn("scratch_left", (directory / "events.jsonl").read_text())
        self.assertEqual(len(self.scratches()), 1)


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
