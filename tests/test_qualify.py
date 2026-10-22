"""Qualification flow: local mode end to end, live-mode refusals without GitHub."""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

from tools import codex, qualify

SCRIPT = Path(qualify.__file__)


class LocalModeTests(unittest.TestCase):
    """Every helper runs as a subprocess against the fake app-server and `gh`."""

    def local(
        self, fault: str = "", *args: str, **extra: str
    ) -> subprocess.CompletedProcess:
        environment = {**os.environ, **dict.fromkeys(codex.CI_MARKERS, "")}
        with tempfile.TemporaryDirectory() as cwd:
            return subprocess.run(  # noqa: S603 -- fixed argv
                [sys.executable, "-I", "-S", str(SCRIPT), "local", *args],
                cwd=cwd,
                env={**environment, "BALLAST_FAKE_FAULT": fault, **extra},
                capture_output=True,
                text=True,
                timeout=600,
                check=False,
            )

    def test_claim_worker_review_publish_end_to_end(self) -> None:
        result = self.local()
        self.assertEqual(result.returncode, 0, result.stderr)
        evidence = json.loads(result.stdout)
        self.assertEqual(evidence["selected"], [1])
        self.assertEqual(evidence["implement"]["status"], "completed")
        self.assertEqual(evidence["implement"]["sandbox"], "workspaceWrite")
        self.assertEqual(evidence["review"]["status"], "completed")
        self.assertEqual(evidence["review"]["sandbox"], "workspaceWrite")
        self.assertEqual(evidence["review"]["checkout_access"], "read-only")
        head = evidence["head"]
        self.assertNotEqual(head, evidence["base"])
        self.assertEqual(evidence["review"]["head_before"], head)
        self.assertEqual(evidence["review"]["head_after"], head)
        self.assertEqual(evidence["pr"]["head"], head)
        self.assertEqual(evidence["verdict"], "approve")
        self.assertEqual(evidence["activity"], "pr_wait")
        self.assertNotIn("No findings", result.stdout)
        # Evidence is meant for docs/evidence/: no local paths.
        self.assertNotIn(tempfile.gettempdir(), result.stdout)

    def test_entry_option_drives_helpers_through_the_named_command(self) -> None:
        cli = Path(qualify.__file__).with_name("cli.py")
        with tempfile.TemporaryDirectory() as tools:
            log = Path(tools) / "calls"
            wrapper = Path(tools) / "wrapper.py"
            wrapper.write_text(
                "import os, sys\n"
                f"open({str(log)!r}, 'a').write(sys.argv[1] + '\\n')\n"
                f"os.execv(sys.executable, [sys.executable, '-I', '-S', {str(cli)!r},"
                " *sys.argv[1:]])\n"
            )
            entry = shlex.join([sys.executable, "-I", "-S", str(wrapper)])
            result = self.local("", "--entry", entry)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["selected"], [1])
            called = log.read_text().split()
        # Every helper step goes through the named command, none around it.
        expected = ["coordinate", "coordinate", "worktree", "worker", "worker"]
        expected += ["coordinate"] * 3
        self.assertEqual(called, expected)

    def test_worker_written_gitfile_cannot_run_host_commands(self) -> None:
        # The implement worker points `.git` at a copy whose fsmonitor would run.
        with tempfile.TemporaryDirectory() as outside:
            marker = Path(outside) / "executed"
            result = self.local("hostile-gitfile", BALLAST_FAKE_MARKER=str(marker))
            self.assertFalse(marker.exists())
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_wrong_work_or_rejected_review_fails_before_publication(self) -> None:
        for fault, reason in (
            ("wrong-output", "must add only"),
            ("unrelated-edit", "must add only"),
            ("committed-edit", "must add only"),
            ("changes-required", "did not end with `Verdict: approve`"),
        ):
            with self.subTest(fault=fault):
                result = self.local(fault)
                self.assertEqual(result.returncode, 1)
                self.assertIn(reason, result.stderr)
                self.assertEqual(result.stdout, "")


class LiveModeTests(unittest.TestCase):
    """Live safety rules, with every native command replaced by a recorder."""

    def setUp(self) -> None:
        self.calls: list[list[str]] = []
        self.failing: set[str] = set()
        self.exists = True

        def recorder(argv: list[str], _: Path) -> str:
            self.calls.append(argv)
            if argv[:3] == ["gh", "repo", "view"] and argv[-1] == "id":
                if "id" in self.failing:
                    message = "fictional lost response"
                    raise qualify.QualificationError(message)
                return json.dumps({"id": "R_fictional1"})
            if argv[:3] == ["gh", "repo", "view"] and not self.exists:
                message = "fictional missing repository"
                raise qualify.QualificationError(message)
            if " ".join(argv[:3]) in self.failing:
                message = "fictional failure"
                raise qualify.QualificationError(message)
            if argv[:3] == ["gh", "issue", "create"]:
                return "https://github.com/owner/ballast-qualification-x/issues/7"
            return ""

        def scenario(*args: object) -> dict:
            created = args[-1]
            created("branches", {"name": "issue-7-a", "sha": "b" * 40})  # type: ignore[operator]
            return {"pr": {"number": 8}}

        for name, fake in (("run", recorder), ("scenario", scenario)):
            patcher = patch.object(qualify, name, side_effect=fake)
            patcher.start()
            self.addCleanup(patcher.stop)
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.ledger = Path(temporary.name) / "ledger.json"

    def args(self, repo: str, **overrides: object) -> Namespace:
        values = {
            "repo": repo,
            "confirm_disposable": True,
            "model": "fixture-model",
            "effort": "low",
            "ledger": self.ledger,
        }
        return Namespace(**(values | overrides))

    def deletes(self) -> list[list[str]]:
        return [argv for argv in self.calls if "delete" in argv or "DELETE" in argv]

    def test_refuses_without_confirmation_or_prefix(self) -> None:
        refused = [
            self.args("owner/ballast-qualification-x", confirm_disposable=False),
            self.args("owner/production"),
            self.args("owner/production-ballast-qualification-x"),
            self.args("owner/ballast-qualification-x/../production"),
        ]
        for args in refused:
            with self.subTest(args=args), self.assertRaises(qualify.QualificationError):
                qualify.live(args)
        self.assertEqual(self.calls, [])
        with self.assertRaises(SystemExit):
            qualify.parser().parse_args(
                [
                    *("live", "--repo", "owner/ballast-qualification-x"),
                    *("--confirm-disposable", "--model", "m", "--effort", "low"),
                ]
            )

    def test_created_repository_is_listed_never_deleted(self) -> None:
        repo = "owner/ballast-qualification-x"
        self.exists = False
        result = qualify.live(self.args(repo))
        self.assertIn(
            ["gh", "repo", "create", repo, "--private", "--add-readme"], self.calls
        )
        self.assertEqual(result["leftovers"], [f"gh repo delete {repo}"])
        self.assertEqual(self.deletes(), [])
        ledger = json.loads(self.ledger.read_text())
        self.assertEqual((ledger["created"], ledger["id"]), (True, "R_fictional1"))

    def test_reused_repository_lists_its_branch_and_issue(self) -> None:
        repo = "owner/ballast-qualification-x"
        result = qualify.live(self.args(repo))
        self.assertEqual(
            result["leftovers"],
            [
                f"gh api -X DELETE repos/{repo}/git/refs/heads/issue-7-a",
                f"gh issue close 7 --repo {repo}",
            ],
        )
        self.assertEqual(self.deletes(), [])

    def test_existing_ledger_is_never_overwritten(self) -> None:
        self.ledger.write_text('{"repository": "earlier run"}\n')
        with self.assertRaisesRegex(qualify.QualificationError, "already exists"):
            qualify.live(self.args("owner/ballast-qualification-x"))
        self.assertEqual(self.calls, [])
        self.assertEqual(self.ledger.read_text(), '{"repository": "earlier run"}\n')

    def test_concurrent_run_cannot_take_a_reserved_ledger(self) -> None:
        # Another run reserved the ledger between our checks: refused, untouched.
        real_open = Path.open

        def reserved(path: Path, mode: str = "r", *args: object) -> object:
            if path == self.ledger and mode == "x":
                raise FileExistsError(path)
            return real_open(path, mode, *args)

        with (
            patch.object(Path, "open", reserved),
            self.assertRaisesRegex(qualify.QualificationError, "already exists"),
        ):
            qualify.live(self.args("owner/ballast-qualification-x"))
        self.assertEqual(self.calls, [])

    def test_lost_issue_response_leaves_a_findable_title(self) -> None:
        self.failing = {"gh issue create"}
        with self.assertRaises(qualify.QualificationError):
            qualify.live(self.args("owner/ballast-qualification-x"))
        ledger = json.loads(self.ledger.read_text())
        self.assertEqual(ledger["issues"], [])
        created = [a for a in self.calls if a[:3] == ["gh", "issue", "create"]]
        self.assertIn(ledger["issue_title"], created[0])
        commands = qualify.leftovers(ledger)
        self.assertIn("--search", commands[-1])
        self.assertIn(ledger["issue_title"], commands[-1])

    def test_creation_is_recorded_before_the_id_lookup(self) -> None:
        self.exists = False
        self.failing = {"id"}  # The id lookup fails after creation.
        with self.assertRaises(qualify.QualificationError):
            qualify.live(self.args("owner/ballast-qualification-x"))
        ledger = json.loads(self.ledger.read_text())
        self.assertEqual((ledger["created"], ledger["id"]), (True, None))
        self.assertEqual(self.deletes(), [])

    def test_unconfirmed_creation_lists_a_check_never_a_delete(self) -> None:
        # The lookup failed transiently and the create failed: maybe not ours.
        repo = "owner/ballast-qualification-x"
        self.exists = False
        self.failing = {"gh repo create"}
        with self.assertRaises(qualify.QualificationError):
            qualify.live(self.args(repo))
        ledger = json.loads(self.ledger.read_text())
        self.assertEqual((ledger["create_attempted"], ledger["created"]), (True, False))
        self.assertEqual(
            qualify.leftovers(ledger), [f"gh repo view {repo} --json id,createdAt"]
        )
        self.assertEqual(self.deletes(), [])

    def test_failed_run_deletes_nothing_and_keeps_its_ledger(self) -> None:
        self.exists = False
        self.failing = {"gh issue create"}
        with self.assertRaises(qualify.QualificationError):
            qualify.live(self.args("owner/ballast-qualification-x"))
        self.assertEqual(self.deletes(), [])
        self.assertTrue(json.loads(self.ledger.read_text())["created"])


if __name__ == "__main__":
    unittest.main()
