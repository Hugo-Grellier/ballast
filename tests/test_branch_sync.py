"""Branch synchronization before agent steps (#18), against real repositories.

A bare repository on disk stands in for GitHub: `branch_sync._url` is the
seam that points the check at it, so ls-remote, fetch, the lease and a
rejected push are real Git behavior (research R14). Operator state and the
operator's global Git configuration live in temporary files. "Unchanged"
means HEAD, `ls-files -s`, `diff-index --cached HEAD`, `status -z` and the
published branch equal their values before the check, with no operation in
progress.
"""

from __future__ import annotations

import ast
import json
import multiprocessing
import os
import shutil
import subprocess
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools/spec_workflow"
sys.path.insert(0, str(TOOLS))
try:
    import autonomy
    import branch_sync
    import draft_pr
    import launcher
    import ledger
finally:
    sys.path.pop(0)
sys.path.insert(0, str(ROOT / "tests"))
try:
    from test_autonomy import operator_state, trusted_directory
finally:
    sys.path.pop(0)

RUN = "run18"
FEATURE = "specs/18-x"
BRANCH = "feat/18-x"
PIN = '[github]\nrepository = "o/r"\n'


def _git_at_least(major: int, minor: int) -> bool:
    git = shutil.which("git")
    if git is None:
        return False
    found = branch_sync._git_version(git)  # noqa: SLF001
    return found is not None and found >= (major, minor)


GIT_OK = _git_at_least(*branch_sync.GIT_FLOOR)


class Killed(BaseException):
    """A process killed at a crash point: nothing catches it, no event."""


def crash_at(name: str, error: type[BaseException] = Killed, action=None):  # noqa: ANN001, ANN201
    """Return a `_crash` seam that acts, then raises, at one point."""

    def seam(point: str) -> None:
        if point == name:
            if action is not None:
                action()
            if error is not None:
                raise error

    return seam


class Scratch:
    """A checkout on feat/18-x with a bare stand-in for GitHub."""

    def __init__(self, case: unittest.TestCase, *, object_format: str = "sha1") -> None:
        """Build it in a temporary directory removed after the case."""
        self.case = case
        directory = TemporaryDirectory()
        case.addCleanup(directory.cleanup)
        self.base = Path(directory.name).resolve()
        self.root = self.base / "repo"
        self.remote = self.base / "remote.git"
        self.upstream = self.base / "upstream"
        self.received = self.base / "received.log"
        self.gitconfig = self.base / "gitconfig"
        self.gitconfig.write_text(
            "[user]\n\tname = Operator\n\temail = operator@example.test\n"
            "[init]\n\tdefaultBranch = main\n"
            '[protocol "file"]\n\tallow = always\n'
        )
        self.state = operator_state(case)
        env = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith("GIT_") and key not in {"SSH_ASKPASS", "DISPLAY"}
        }
        env |= {
            "GIT_CONFIG_GLOBAL": str(self.gitconfig),
            "GIT_CONFIG_NOSYSTEM": "1",
            "XDG_STATE_HOME": str(self.state),
        }
        case.enterContext(patch.dict(os.environ, env, clear=True))
        # The scratch checkout lives under /tmp, which program resolution
        # refuses in production (agents can write there); trust it here.
        case.enterContext(patch.object(ledger, "agent_temp_roots", tuple))
        self.url = self.remote.as_uri()
        case.enterContext(patch.object(branch_sync, "_url", lambda *_a, **_k: self.url))
        fmt = [f"--object-format={object_format}"]
        self.run("git", "init", "-q", "--bare", *fmt, str(self.remote), cwd=self.base)
        self.root.mkdir()
        self.git("init", "-q", *fmt)
        self.git("remote", "add", "origin", "https://github.com/o/r.git")
        self.write(
            {
                ".gitignore": ".agents/skills/ballast-*\n.env\n",
                "ballast.toml": PIN,
                ".specify/memory/constitution.md": "# Constitution\n",
                "README.md": "readme\n",
                "tools/a.py": "a = 1\n",
                f"{FEATURE}/spec.md": "# Spec\n",
            }
        )
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "base")
        self.git("push", "-q", str(self.remote), "main")
        self.run(
            "git", "clone", "-q", str(self.remote), str(self.upstream), cwd=self.base
        )
        self.git("checkout", "-q", "-b", BRANCH)
        self.commit({"feature.txt": "feature\n"}, "feature work")
        self.trust()
        self.pin()

    # --- plumbing -----------------------------------------------------------

    def run(self, *argv: str, cwd: Path, check: bool = True, **kwargs: object) -> str:
        result = subprocess.run(  # noqa: S603
            argv, cwd=cwd, capture_output=True, text=True, check=False, **kwargs
        )
        if check and result.returncode:
            message = f"{argv}: {result.stderr}"
            raise AssertionError(message)
        return result.stdout

    def git(self, *args: str, check: bool = True) -> str:
        return self.run("git", *args, cwd=self.root, check=check)

    def up(self, *args: str) -> str:
        return self.run("git", *args, cwd=self.upstream)

    def head(self, ref: str = "HEAD") -> str:
        return self.git("rev-parse", ref).strip()

    def write(self, files: dict[str, str], where: Path | None = None) -> None:
        for name, text in files.items():
            path = (where or self.root) / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)

    def commit(self, files: dict[str, str], message: str = "change") -> str:
        self.write(files)
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)
        return self.head()

    def trust(self) -> None:
        state = launcher.state_dir(self.root)
        state.mkdir(parents=True, exist_ok=True, mode=0o700)
        (state / launcher.TRUSTED).write_text(
            json.dumps(launcher.trusted_inputs(self.root))
        )

    def pin(self, run_id: str = RUN, **data: str) -> None:
        path = launcher.state_dir(self.root) / "draft-pr" / f"{run_id}.json"
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        path.write_text(json.dumps({"branch": BRANCH, "feature": FEATURE, **data}))

    def read_pin(self, run_id: str = RUN) -> dict:
        path = launcher.state_dir(self.root) / "draft-pr" / f"{run_id}.json"
        return json.loads(path.read_text()) if path.exists() else {}

    def record_path(self, branch: str = BRANCH) -> Path:
        key = branch_sync._key(branch)  # noqa: SLF001
        return launcher.state_dir(self.root) / "branch-sync" / f"{key}.json"

    # --- the stand-in GitHub ------------------------------------------------

    def advance_base(
        self, files: dict[str, str] | None = None, message: str = "base change"
    ) -> str:
        """Push a commit to main on the remote, never touching the checkout."""
        self.up("fetch", "-q", "origin")
        self.up("checkout", "-q", "-B", "main", "origin/main")
        if files is None:
            self.up("commit", "-q", "--allow-empty", "-m", message)
        else:
            self.write(files, self.upstream)
            self.up("add", "-A", "-f", "--", *files)
            self.up("commit", "-q", "-m", message)
        self.up("push", "-q", "origin", "main")
        return self.up("rev-parse", "HEAD").strip()

    def publish(self, branch: str = BRANCH) -> None:
        self.git("push", "-q", str(self.remote), f"{branch}:{branch}")

    def published(self, branch: str = BRANCH) -> str | None:
        if not self.remote.is_dir():
            return "unreachable"
        out = self.run(
            "git", "ls-remote", str(self.remote), f"refs/heads/{branch}", cwd=self.base
        )
        return out.split()[0] if out.strip() else None

    def push_as_someone_else(self, files: dict[str, str], branch: str = BRANCH) -> str:
        self.up("fetch", "-q", "origin")
        self.up("checkout", "-q", "-B", branch, f"origin/{branch}")
        self.write(files, self.upstream)
        self.up("add", "-A")
        self.up("commit", "-q", "-m", "someone else")
        self.up("push", "-q", "origin", f"{branch}:{branch}")
        return self.up("rev-parse", "HEAD").strip()

    def add_pre_receive(self, *, reject: bool = False) -> None:
        hook = self.remote / "hooks/pre-receive"
        hook.write_text(
            "#!/bin/sh\n"
            f"cat >> {self.received}\n"
            + ("echo 'protected branch' >&2\nexit 1\n" if reject else "exit 0\n")
        )
        hook.chmod(0o755)

    def pushes(self) -> list[str]:
        """Return what the remote received since the last `clear_pushes`."""
        return self.received.read_text().splitlines() if self.received.exists() else []

    def clear_pushes(self) -> None:
        self.received.unlink(missing_ok=True)

    def advance(self, branch: str, files: dict[str, str]) -> str:
        """Push a commit to another remote branch, from main."""
        self.up("fetch", "-q", "origin")
        self.up("checkout", "-q", "-B", branch, "origin/main")
        self.write(files, self.upstream)
        self.up("add", "-A")
        self.up("commit", "-q", "-m", f"{branch} change")
        self.up("push", "-q", "--force", "origin", f"{branch}:{branch}")
        return self.up("rev-parse", "HEAD").strip()

    # --- observation --------------------------------------------------------

    def snapshot(self, branch: str = BRANCH) -> dict[str, object]:
        markers = ["rebase-merge", "rebase-apply", "MERGE_HEAD"]
        return {
            "head": self.git("rev-parse", "HEAD", check=False).strip(),
            "ref": self.git("symbolic-ref", "-q", "HEAD", check=False).strip(),
            "index": self.git("ls-files", "-s"),
            "cached": self.git("diff-index", "--cached", "HEAD"),
            "status": self.git("status", "--porcelain=v1", "-z"),
            "published": self.published(branch),
            "markers": [m for m in markers if (self.root / ".git" / m).exists()],
        }

    def assert_unchanged(self, before: dict[str, object]) -> None:
        self.case.assertEqual(self.snapshot(), before)

    def events(self, run_id: str = RUN) -> list[dict]:
        events, problems = ledger.read(self.root, run_id)
        self.case.assertEqual(problems, [])
        return [e["data"] for e in events if e["kind"] == "branch_sync"]

    def global_config(self, text: str) -> None:
        with self.gitconfig.open("a") as handle:
            handle.write(text)

    def marker_program(self, name: str) -> tuple[Path, Path]:
        """Write a program that leaves a marker file when anything runs it."""
        marker = self.base / f"{name}.ran"
        program = trusted_directory(self.case) / name
        program.write_text(f"#!/bin/sh\ntouch {marker}\nexit 1\n")
        program.chmod(0o755)
        return program, marker

    def check(self, run_id: str = RUN, **kwargs: object) -> branch_sync.Outcome:
        kwargs.setdefault("feature", FEATURE)
        return branch_sync.synchronize(self.root, run_id, **kwargs)


@unittest.skipUnless(GIT_OK, "needs git 2.41 or later")
class SyncCase(unittest.TestCase):
    """A fresh Scratch per test; no tests of its own."""

    def setUp(self) -> None:
        self.s = Scratch(self)

    def assertBlocked(  # noqa: N802 - unittest style
        self, outcome: branch_sync.Outcome, cause: str, run_id: str = RUN
    ) -> list[tuple[str, str]]:
        """One block: cause, one recovery line, one recorded event."""
        self.assertEqual((outcome.outcome, outcome.cause), ("blocked", cause), outcome)
        lines = branch_sync.format_lines(outcome)
        self.assertEqual([stream for stream, _ in lines], ["stderr", "stderr"])
        self.assertTrue(lines[0][1].startswith(f"BLOCKED_UPSTREAM_SYNC ({cause})"))
        self.assertTrue(lines[1][1].startswith("Recovery: "))
        self.assertEqual(sum(line.startswith("Recovery:") for _, line in lines), 1)
        self.assertEqual(self.s.events(run_id)[-1]["cause"], cause)
        return lines

    def killed(self, point: str, action=None) -> None:  # noqa: ANN001
        """Run the check and kill it at `point`, after `action`."""
        with (
            patch.object(branch_sync, "_crash", crash_at(point, Killed, action)),
            self.assertRaises(Killed),
        ):
            self.s.check()


class HarnessTests(SyncCase):
    """T003: the module imports and the scratch repository is consistent."""

    def test_scratch_is_a_published_capable_feature_checkout(self) -> None:
        self.assertEqual(
            self.s.git("symbolic-ref", "HEAD").strip(), f"refs/heads/{BRANCH}"
        )
        self.assertEqual(self.s.published("main"), self.s.head("main"))
        self.assertIsNone(self.s.published())
        self.assertIsNone(launcher._refusal(self.s.root))  # noqa: SLF001
        self.assertEqual(self.s.read_pin(), {"branch": BRANCH, "feature": FEATURE})


class FoundationTests(SyncCase):
    """T011 [FR-009, FR-012, FR-013, DEC-0001, N-02, N-11, C1]."""

    def test_standard_library_and_sibling_imports_only(self) -> None:
        tree = ast.parse((TOOLS / "branch_sync.py").read_text())
        names = {
            alias.name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        } | {
            node.module.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        }
        siblings = {path.stem for path in TOOLS.glob("*.py")}
        self.assertLessEqual(names - siblings - {"__future__"}, sys.stdlib_module_names)
        result = subprocess.run(  # noqa: S603
            [
                sys.executable,
                "-I",
                "-S",
                "-c",
                f"import sys; sys.path.insert(0, {str(TOOLS)!r}); import branch_sync",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_runners_harden_every_command(self) -> None:
        self.s.advance_base({"base.txt": "b\n"})
        log: list = []
        environments: list[dict] = []
        real_run = subprocess.run

        every: list[dict] = []

        def spy(argv, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003, ANN202
            if kwargs.get("env") and "GIT_DIR" in kwargs["env"]:
                environments.append(kwargs["env"])
            if kwargs.get("env") and argv[1:] != ["version"]:
                every.append(kwargs["env"])
            return real_run(argv, *args, **kwargs)

        with (
            patch.object(branch_sync, "ARGV_LOG", log),
            patch.object(branch_sync.subprocess, "run", spy),
            patch.dict(
                os.environ,
                {
                    "SSH_ASKPASS": "/x",
                    "DISPLAY": ":0",
                    "WAYLAND_DISPLAY": "w",
                    "GIT_CONFIG_PARAMETERS": "'core.hookspath'='/x'",
                },
            ),
        ):
            outcome = self.s.check()
        self.assertEqual(outcome.outcome, "synchronized", outcome)
        git, _ = draft_pr._resolve("git", self.s.root)  # noqa: SLF001
        hardening, maintenance = (
            list(autonomy.GIT_HARDENING),
            list(branch_sync.NO_MAINTENANCE),
        )
        throwaway = [argv for where, argv in log if where == "throwaway"]
        self.assertTrue(throwaway)
        for where, argv in log:
            self.assertEqual(Path(argv[0]), Path(git).resolve(), argv)
            start = argv.index(hardening[0])
            self.assertEqual(argv[start : start + len(hardening)], hardening)
            # SEC-004: a forged commit-graph never answers ancestry.
            self.assertIn("core.commitGraph=false", argv)
            if where == "checkout":
                self.assertIn("submodule.recurse=false", argv)
            if where == "throwaway":
                after = start + len(hardening)
                self.assertEqual(argv[after : after + len(maintenance)], maintenance)
                self.assertNotIn(
                    argv[after + len(maintenance)], {"gc", "repack", "prune"}
                )
        self.assertTrue(every)
        for env in every:
            self.assertEqual(env["GIT_NO_REPLACE_OBJECTS"], "1")
            self.assertEqual(env["GIT_GRAFT_FILE"], os.devnull)
        init = next(argv for argv in throwaway if "init" in argv)
        self.assertIn("--template=", init)
        self.assertIn("--object-format=sha1", init)
        self.assertTrue(environments)
        for env in environments:
            self.assertEqual(env["GIT_TERMINAL_PROMPT"], "0")
            self.assertEqual(env["GIT_NO_LAZY_FETCH"], "1")
            self.assertEqual(env["GIT_ASKPASS"], "")
            self.assertEqual(env["SSH_ASKPASS_REQUIRE"], "never")
            self.assertEqual(env["LC_ALL"], "C")
            for name in ("SSH_ASKPASS", "DISPLAY", "WAYLAND_DISPLAY"):
                self.assertNotIn(name, env)
            self.assertFalse(
                [
                    k
                    for k in env
                    if k in {"GIT_CONFIG_PARAMETERS", "GIT_CONFIG_COUNT"}
                    or k.startswith(("GIT_CONFIG_KEY_", "GIT_CONFIG_VALUE_"))
                ]
            )
        # The throwaway repository is deleted afterwards.
        state = launcher.state_dir(self.s.root)
        self.assertEqual(list(state.glob("ballast-sync-*")), [])

    def test_throwaway_allow_list_holds_without_assert(self) -> None:
        """SEC-006, E-05: a refusal, not an assert that python -O removes."""
        work = branch_sync._Sync(  # noqa: SLF001
            self.s.root,
            RUN,
            feature=FEATURE,
            starting=False,
            branch=None,
            base=None,
            source_run=None,
        )
        work.bare = self.s.base / "away.git"
        with self.assertRaisesRegex(RuntimeError, "git gc is not allowed"):
            work.throwaway("gc")
        work.bare = None
        with self.assertRaises(RuntimeError):
            work.throwaway("cat-file", "-e", "HEAD")

    def test_checkout_git_is_never_executed(self) -> None:
        local = self.s.root / "bin"
        program, marker = self.s.marker_program("git")
        local.mkdir()
        shutil.copy(program, local / "git")
        with patch.dict(
            os.environ, {"PATH": f"{local}{os.pathsep}{os.environ['PATH']}"}
        ):
            outcome = self.s.check()
        self.assertEqual(outcome.outcome, "up-to-date", outcome)
        self.assertFalse(marker.exists())

    def test_old_git_is_refused(self) -> None:
        before = self.s.snapshot()
        with patch.object(branch_sync, "_git_version", return_value=(2, 40)):
            outcome = self.s.check()
        self.assertBlocked(outcome, "git-unavailable")
        self.assertEqual(outcome.detail, "git 2.40 is older than 2.41")
        self.assertIn("2.41 or later", outcome.recovery)
        self.s.assert_unchanged(before)

    def test_records_are_private_and_atomic(self) -> None:
        self.s.advance_base({"base.txt": "b\n"})
        seen: dict[str, int] = {}

        def look() -> None:
            path = self.s.record_path()
            seen["file"] = path.stat().st_mode & 0o777
            seen["directory"] = path.parent.stat().st_mode & 0o777

        with patch.object(branch_sync, "_crash", crash_at("after-record", None, look)):
            self.assertEqual(self.s.check().outcome, "synchronized")
        self.assertEqual(seen, {"file": 0o600, "directory": 0o700})
        pin = launcher.state_dir(self.s.root) / "draft-pr" / f"{RUN}.json"
        self.assertEqual(pin.stat().st_mode & 0o777, 0o600)
        self.assertEqual(pin.parent.stat().st_mode & 0o777, 0o700)
        self.assertEqual(list(pin.parent.glob(".*.tmp")), [])
        with (
            patch.dict(os.environ, {"XDG_STATE_HOME": str(self.s.root / "state")}),
        ):
            self.assertBlocked(self.s.check(), "internal-error")

    def test_invalid_record_is_reported_not_ignored(self) -> None:
        path = self.s.record_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{not json")
        before = self.s.snapshot()
        outcome = self.s.check()
        self.assertBlocked(outcome, "internal-error")
        self.assertEqual(outcome.detail, "invalid write-ahead record")
        self.assertIn(str(path), outcome.recovery)
        self.assertTrue(path.exists())
        self.s.assert_unchanged(before)

    def test_names_are_quoted_and_escaped(self) -> None:
        outcome = branch_sync.Outcome(
            "blocked",
            cause="wrong-branch",
            detail=draft_pr.printable("on a\nb\x1b[31m"),
            recovery=branch_sync._recovery(  # noqa: SLF001
                "wrong-branch", pinned="feat/18-$(id);x", rerun="r"
            ),
        )
        lines = [line for _, line in branch_sync.format_lines(outcome)]
        self.assertNotIn("\n", "".join(lines))
        self.assertNotIn("\x1b", "".join(lines))
        self.assertIn("git switch 'feat/18-$(id);x', then r", lines[1])
        option = branch_sync._recovery("wrong-branch", pinned="-x", rerun="r")  # noqa: SLF001
        self.assertIn("<pinned>", option)
        # PFR-01: `+x-18` as a push refspec would force-push without the lease.
        forced = branch_sync._recovery(  # noqa: SLF001
            "conflict-published",
            remote="origin",
            base="main",
            branch="+x-18",
            published="a" * 40,
            rerun="r",
        )
        self.assertNotIn("+x-18", forced)
        self.assertIn("<branch>", forced)

    def test_never_raises(self) -> None:
        with patch.object(branch_sync._Sync, "classify", side_effect=RuntimeError("x")):  # noqa: SLF001
            outcome = self.s.check()
        self.assertBlocked(outcome, "internal-error")
        self.assertEqual(outcome.detail, "RuntimeError")
        with patch.object(branch_sync._Sync, "classify", side_effect=KeyboardInterrupt):  # noqa: SLF001
            outcome = self.s.check()
        self.assertBlocked(outcome, "internal-error")
        self.assertEqual(outcome.detail, "interrupted")
        self.assertTrue(outcome.interrupted)

    def test_failed_record_blocks_an_otherwise_good_outcome(self) -> None:
        self.s.advance_base({"base.txt": "b\n"})
        with patch.object(ledger, "append", side_effect=OSError("disk full")):
            outcome = self.s.check()
        self.assertEqual(
            (outcome.outcome, outcome.cause), ("blocked", "internal-error")
        )
        self.assertEqual(outcome.detail, "not recorded")
        # Q35: the branch stays synchronized; the next invocation says so.
        self.s.git("merge-base", "--is-ancestor", str(self.s.published("main")), "HEAD")
        again = self.s.check()
        self.assertEqual(again.outcome, "up-to-date", again)
        self.assertEqual(self.s.events()[-1]["outcome"], "up-to-date")


class ResumeOnCurrentBaseTests(SyncCase):
    """T017 [AC-001..AC-004, FR-002, FR-004, FR-005, FR-009, SC-005, N-06]."""

    def test_behind_clean_unpublished_is_synchronized(self) -> None:
        """Q1."""
        base_before = self.s.head("main")
        base_after = self.s.advance_base({"base.txt": "b\n"})
        head_before = self.s.head()
        outcome = self.s.check()
        self.assertEqual(outcome.outcome, "synchronized", outcome)
        head_after = self.s.head()
        self.assertEqual(outcome.head_after, head_after)
        self.assertNotEqual(head_after, head_before)
        self.s.git("merge-base", "--is-ancestor", base_after, "HEAD")
        self.assertEqual((self.s.root / "feature.txt").read_text(), "feature\n")
        self.assertEqual(self.s.git("status", "--porcelain"), "")
        (event,) = self.s.events()
        self.assertEqual(
            {k: event[k] for k in ("outcome", "base_ref", "base_before", "base_after")},
            {
                "outcome": "synchronized",
                "base_ref": "main",
                "base_before": base_before,
                "base_after": base_after,
            },
        )
        self.assertEqual(
            (event["head_before"], event["head_after"]), (head_before, head_after)
        )
        self.assertFalse(event["pushed"])
        ((stream, line),) = branch_sync.format_lines(outcome)
        self.assertEqual(stream, "stdout")
        self.assertEqual(
            line,
            f"Branch sync: synchronized {BRANCH} onto main ({base_before[:12]}.."
            f"{base_after[:12]}), HEAD {head_before[:12]} -> {head_after[:12]}",
        )
        self.assertEqual(self.s.read_pin()["base_commit"], base_after)
        self.assertFalse(self.s.record_path().exists())

    def test_up_to_date_needs_no_fetch_and_repeats(self) -> None:
        """Q2 [AC-002, SC-005]."""
        self.s.git("fetch", "-q", str(self.s.remote), "main")
        log: list = []
        before = self.s.snapshot()
        with patch.object(branch_sync, "ARGV_LOG", log):
            outcome = self.s.check()
        self.assertEqual(outcome.outcome, "up-to-date", outcome)
        self.s.assert_unchanged(before)
        commands = [argv for where, argv in log if where == "throwaway"]
        self.assertFalse([argv for argv in commands if "fetch" in argv])
        self.assertEqual(sum("ls-remote" in argv for argv in commands), 1)
        self.assertEqual(self.s.check().outcome, "up-to-date")
        self.assertEqual([e["outcome"] for e in self.s.events()], ["up-to-date"] * 2)
        ((_, line),) = branch_sync.format_lines(outcome)
        self.assertEqual(
            line,
            f"Branch sync: up-to-date {BRANCH} with main ({self.s.head('main')[:12]})",
        )

    def test_start_pins_branch_then_base_after_ls_remote(self) -> None:
        """Q3 [AC-004, FR-002, N-06]."""
        new = self.s.advance_base({"base.txt": "b\n"})
        outcome = self.s.check("start1", starting=True)
        self.assertEqual(outcome.outcome, "synchronized", outcome)
        self.assertEqual(
            self.s.read_pin("start1"),
            {"branch": BRANCH, "feature": FEATURE, "base": "main", "base_commit": new},
        )
        self.s.advance_base({"base2.txt": "c\n"})
        with patch.object(
            branch_sync, "_url", lambda *_a, **_k: "file:///nowhere/x.git"
        ):
            outcome = self.s.check("start2", starting=True)
        self.assertBlocked(outcome, "fetch-failed", "start2")
        self.assertEqual(
            self.s.read_pin("start2"), {"branch": BRANCH, "feature": FEATURE}
        )
        log: list = []
        with patch.object(branch_sync, "ARGV_LOG", log):
            outcome = self.s.check("start2")
        self.assertEqual(outcome.outcome, "synchronized", outcome)
        self.assertEqual(self.s.read_pin("start2")["base"], "main")
        self.assertEqual(sum("ls-remote" in argv for _, argv in log), 1)

    def test_a_17_pin_gets_its_base(self) -> None:
        """Q11, second variant."""
        self.assertEqual(self.s.check().outcome, "up-to-date")
        self.assertEqual(self.s.read_pin()["base"], "main")

    def test_no_commits_beyond_the_base_fast_forwards(self) -> None:
        """Q30 [edge "no commits beyond the base"]."""
        self.s.git("reset", "-q", "--hard", "main")
        new = self.s.advance_base({"base.txt": "b\n"})
        self.s.add_pre_receive()
        outcome = self.s.check()
        self.assertEqual(outcome.outcome, "synchronized", outcome)
        self.assertTrue(outcome.fast_forwarded)
        self.assertEqual(self.s.head(), new)
        self.assertEqual(self.s.pushes(), [])

    def test_empty_and_spec_only_base_commits_count_as_behind(self) -> None:
        """Q31 [FR-004]."""
        for files in (None, {f"{FEATURE}/notes.md": "n\n"}):
            with self.subTest(files=files):
                new = self.s.advance_base(files)
                outcome = self.s.check()
                self.assertEqual(outcome.outcome, "synchronized", outcome)
                self.s.git("merge-base", "--is-ancestor", new, "HEAD")

    def test_rewritten_base(self) -> None:
        """Q32 [edge "base rewritten"]."""
        self.assertEqual(self.s.check().outcome, "up-to-date")
        old_base = self.s.read_pin()["base_commit"]
        # Rewrite main on the remote: the old base commit is replaced.
        self.s.up("fetch", "-q", "origin")
        self.s.up("checkout", "-q", "-B", "main", "origin/main")
        self.s.up("commit", "-q", "--amend", "-m", "rewritten base")
        self.s.up("push", "-q", "--force", "origin", "main")
        outcome = self.s.check()
        self.assertEqual(outcome.outcome, "synchronized", outcome)
        replayed = self.s.git("log", "--format=%s", f"{outcome.base_after}..HEAD")
        self.assertEqual(replayed.split(), ["feature", "work"])
        self.assertNotEqual(old_base, outcome.base_after)
        # With no recorded base and no common history, the old base is unknown.
        scratch = Scratch(self)
        scratch.up("checkout", "-q", "--orphan", "fresh")
        scratch.up("commit", "-q", "--allow-empty", "-m", "unrelated base")
        scratch.up("push", "-q", "--force", "origin", "fresh:main")
        before = scratch.snapshot()
        outcome = scratch.check()
        self.assertEqual((outcome.outcome, outcome.cause), ("blocked", "diverged"))
        self.assertEqual(
            outcome.detail, "the base was rewritten and the old base is unknown"
        )
        scratch.assert_unchanged(before)


class ReplayFidelityTests(SyncCase):
    """T018 [FR-005, FR-006, FR-012, F-01, F-05, F-09, N-02]."""

    def test_union_attributes_come_from_the_base(self) -> None:
        """Q8."""
        self.s.git("checkout", "-q", "main")
        self.s.commit({"CHANGELOG.md": "start\n"}, "changelog")
        self.s.git("push", "-q", str(self.s.remote), "main")
        self.s.git("checkout", "-q", BRANCH)
        self.s.git("rebase", "-q", "main")
        self.s.commit({"CHANGELOG.md": "feature line\nstart\n"}, "feature changelog")
        new = self.s.advance_base(
            {
                ".gitattributes": "CHANGELOG.md merge=union\n",
                "CHANGELOG.md": "base line\nstart\n",
            }
        )
        log: list = []
        with patch.object(branch_sync, "ARGV_LOG", log):
            outcome = self.s.check()
        self.assertEqual(outcome.outcome, "synchronized", outcome)
        text = (self.s.root / "CHANGELOG.md").read_text()
        self.assertIn("base line", text)
        self.assertIn("feature line", text)
        merge = next(argv for _, argv in log if "merge-tree" in argv)
        self.assertEqual(merge[1], f"--attr-source={new}")
        self.assertLess(merge.index(f"--attr-source={new}"), merge.index("merge-tree"))

    def test_feature_attributes_are_not_honoured(self) -> None:
        self.s.commit(
            {
                ".gitattributes": "CHANGELOG.md merge=union\n",
                "CHANGELOG.md": "feature\n",
            },
            "feature attributes",
        )
        self.s.advance_base({"CHANGELOG.md": "base\n"})
        before = self.s.snapshot()
        outcome = self.s.check()
        self.assertBlocked(outcome, "conflict")
        self.s.assert_unchanged(before)

    def test_replayed_commits_keep_author_and_message(self) -> None:
        self.s.git(
            "-c",
            "user.name=Agent Author",
            "-c",
            "user.email=agent@example.test",
            "commit",
            "-q",
            "--allow-empty",
            "-m",
            "subject\n\nbody line\n",
        )
        self.s.advance_base({"base.txt": "b\n"})
        outcome = self.s.check()
        self.assertEqual(outcome.outcome, "synchronized", outcome)
        self.assertEqual(
            self.s.git("log", "-1", "--format=%an <%ae>|%B").strip(),
            "Agent Author <agent@example.test>|subject\n\nbody line",
        )
        self.assertEqual(
            self.s.git("log", "-1", "--format=%cn <%ce>").strip(),
            "Operator <operator@example.test>",
        )
        self.assertNotIn("gpgsig", self.s.git("cat-file", "commit", "HEAD"))

    def test_signature_is_dropped(self) -> None:
        raw = (
            b"tree " + b"a" * 40 + b"\nparent " + b"b" * 40 + b"\n"
            b"author A <a@x> 1 +0000\ncommitter C <c@x> 1 +0000\n"
            b"gpgsig -----BEGIN PGP SIGNATURE-----\n \n abc\n"
            b" -----END PGP SIGNATURE-----\n"
            b"encoding ISO-8859-1\n\nmessage \xe9\n"
        )
        rewritten = branch_sync._rewrite(raw, "c" * 40, "d" * 40, b"Op <o@x> 2 +0000")  # noqa: SLF001
        self.assertEqual(
            rewritten,
            b"tree " + b"c" * 40 + b"\nparent " + b"d" * 40 + b"\n"
            b"author A <a@x> 1 +0000\ncommitter Op <o@x> 2 +0000\n"
            b"encoding ISO-8859-1\n\nmessage \xe9\n",
        )

    def test_change_already_upstream_is_dropped(self) -> None:
        self.s.commit({"shared.txt": "same\n"}, "shared change")
        self.s.advance_base({"shared.txt": "same\n"})
        outcome = self.s.check()
        self.assertEqual(outcome.outcome, "synchronized", outcome)
        subjects = self.s.git("log", "--format=%s", f"{outcome.base_after}..HEAD")
        self.assertEqual(subjects.splitlines(), ["feature work"])

    def test_operator_gc_never_prunes_the_checkout(self) -> None:
        """Q37 [F-01]."""
        self.s.global_config(
            "[gc]\n\tauto = 1\n\tpruneExpire = now\n[maintenance]\n\tauto = true\n"
        )
        self.s.git("checkout", "-q", "-b", "side", "main")
        for number in range(5):
            self.s.commit({f"side{number}.txt": f"{number}\n"}, f"side {number}")
        self.s.git("checkout", "-q", BRANCH)
        self.s.advance_base({"base.txt": "b\n"})
        outcome = self.s.check()
        self.assertEqual(outcome.outcome, "synchronized", outcome)
        self.s.git("fsck", "--no-progress")
        self.assertEqual(len(self.s.git("log", "--format=%H", "side").split()), 6)


class BlockedCauseTests(SyncCase):
    """T023 [AC-006..AC-010, AC-021, FR-002, FR-003, FR-005, FR-006, FR-013]."""

    def test_dirty_checkouts_are_never_touched(self) -> None:
        """Q5 and Q12 [AC-006, AC-010, A-8]."""
        self.s.advance_base({"base.txt": "b\n"})
        for change in ({"README.md": "edited\n"}, {"new.txt": "untracked\n"}):
            with self.subTest(change=change):
                self.s.write(change)
                before = self.s.snapshot()
                outcome = self.s.check()
                self.assertBlocked(outcome, "dirty")
                self.assertIn(next(iter(change)), outcome.detail)
                self.assertIn("never stashes or discards", outcome.recovery)
                self.assertIn(f"ballast run resume {RUN}", outcome.recovery)
                self.s.assert_unchanged(before)
                self.s.git("stash", "-q", "-u")  # the test removes the cause
                self.s.git("stash", "drop", "-q")
        self.s.write({".agents/skills/ballast-x/SKILL.md": "installed\n"})
        outcome = self.s.check()
        self.assertEqual(outcome.outcome, "synchronized", outcome)

    def test_ignored_file_the_base_tracks_is_not_overwritten(self) -> None:
        """Q6 [F-07]."""
        self.s.write({".env": "secret=local\n"})
        self.s.advance_base({".env": "secret=base\n"})
        before = self.s.snapshot()
        outcome = self.s.check()
        self.assertBlocked(outcome, "dirty")
        self.assertEqual(outcome.detail, "ignored files would be overwritten: .env")
        self.assertTrue(outcome.recovery.startswith("move or commit these files"))
        self.assertEqual((self.s.root / ".env").read_text(), "secret=local\n")
        self.s.assert_unchanged(before)
        self.assertFalse(self.s.record_path().exists())

    def test_conflict_changes_nothing(self) -> None:
        """Q7, Q12 [AC-007, AC-010]."""
        mine = self.s.commit({"tools/a.py": "a = 2\n"}, "feature edits a")
        self.s.advance_base({"tools/a.py": "a = 3\n"})
        before = self.s.snapshot()
        outcome = self.s.check()
        self.assertBlocked(outcome, "conflict")
        self.assertEqual(
            outcome.detail, f"replaying {mine[:12]} conflicts in tools/a.py"
        )
        self.assertEqual(
            outcome.recovery,
            "rebase by hand: git pull --rebase origin main, resolve, then ballast run "
            f"resume {RUN}",
        )
        self.s.assert_unchanged(before)
        self.s.git("reset", "-q", "--hard", "HEAD~1")
        self.assertEqual(self.s.check().outcome, "synchronized")

    def test_base_that_cannot_be_fetched_is_never_guessed(self) -> None:
        """Q9 [AC-008, FR-002, FR-003, A-6]."""
        self.assertEqual(self.s.check().outcome, "up-to-date")
        self.s.advance_base({"base.txt": "b\n"})
        moved = self.s.base / "moved.git"
        self.s.remote.rename(moved)
        before = self.s.snapshot()
        outcome = self.s.check()
        self.assertBlocked(outcome, "fetch-failed")
        self.assertEqual(outcome.detail, "could not fetch main from o/r")
        self.assertIn("Ballast cannot answer a prompt", outcome.recovery)
        self.s.assert_unchanged(before)
        moved.rename(self.s.remote)
        # Q12 [AC-010]: once the base is reachable again, a rerun proceeds.
        self.assertEqual(self.s.check().outcome, "synchronized")
        self.s.up("push", "-q", "origin", "main:develop")
        self.s.pin(base="develop")
        self.s.run("git", "branch", "-D", "develop", cwd=self.s.remote)
        outcome = self.s.check()
        self.assertBlocked(outcome, "unknown-base")
        self.assertEqual(outcome.detail, "develop does not exist on o/r")
        self.assertIn("never substitutes another base", outcome.recovery)
        self.s.pin()
        (self.s.root / "ballast.toml").write_text("[checks]\n")
        outcome = self.s.check()
        self.assertBlocked(outcome, "unknown-base")
        self.assertEqual(outcome.detail, "no [github] repository in ballast.toml")

    def test_operations_and_branches(self) -> None:
        """Q10, Q12 [AC-009, AC-010]."""
        self.s.advance_base({"base.txt": "b\n"})
        merge_head = self.s.root / ".git/MERGE_HEAD"
        merge_head.write_text(self.s.head() + "\n")
        before = self.s.snapshot()
        outcome = self.s.check()
        self.assertBlocked(outcome, "in-progress")
        self.assertEqual(outcome.detail, "a merge is in progress")
        self.s.assert_unchanged(before)
        merge_head.unlink()
        self.s.git("checkout", "-q", "--detach")
        outcome = self.s.check()
        self.assertBlocked(outcome, "wrong-branch")
        self.assertEqual(outcome.detail, "HEAD is detached")
        self.assertEqual(
            outcome.recovery, f"git switch {BRANCH}, then ballast run resume {RUN}"
        )
        self.s.git("checkout", "-q", "main")
        outcome = self.s.check()
        self.assertBlocked(outcome, "wrong-branch")
        self.assertEqual(outcome.detail, f"on main, run started on {BRANCH}")
        self.s.git("checkout", "-q", BRANCH)
        self.assertEqual(self.s.check().outcome, "synchronized")

    def test_every_operation_in_progress_blocks(self) -> None:
        """AC-009: rebase, merge, cherry-pick, revert and bisect markers."""
        self.s.advance_base({"base.txt": "b\n"})
        before = self.s.snapshot()
        for name, operation in branch_sync.IN_PROGRESS_MARKERS:
            with self.subTest(marker=name):
                marker = self.s.root / ".git" / name
                marker.write_text(self.s.head() + "\n")
                try:
                    outcome = self.s.check()
                finally:
                    marker.unlink()
                self.assertBlocked(outcome, "in-progress")
                self.assertEqual(outcome.detail, f"a {operation} is in progress")
                self.assertEqual(
                    outcome.recovery,
                    f"finish or abort the {operation} yourself, then ballast run "
                    f"resume {RUN}",
                )
                self.assertEqual(self.s.snapshot(), before)

    def test_start_during_a_rebase_reports_the_rebase(self) -> None:
        """E-02 [AC-009, R4]: in-progress comes before the detached-HEAD stop."""
        self.s.git("checkout", "-q", "main")
        self.s.commit({"feature.txt": "base version\n"}, "conflicting")
        self.s.git("checkout", "-q", BRANCH)
        self.s.git("rebase", "-q", "main", check=False)
        self.assertTrue((self.s.root / ".git/rebase-merge").exists())
        outcome = self.s.check("st1", starting=True)
        self.assertBlocked(outcome, "in-progress", "st1")
        self.assertEqual(outcome.detail, "a rebase is in progress")
        self.s.git("rebase", "--abort")
        self.s.git("checkout", "-q", "--detach")
        outcome = self.s.check("st2", starting=True)
        self.assertBlocked(outcome, "wrong-branch", "st2")
        self.assertEqual(
            outcome.recovery, "git switch 18-x, then your ballast run start command"
        )

    def test_recorded_base_missing_locally_blocks(self) -> None:
        """E-06 [R8]: a recorded base the store lost is unknown, not guessed."""
        self.s.advance_base({"base.txt": "b\n"})
        self.s.pin(base="main", base_commit="1" * 40)
        before = self.s.snapshot()
        outcome = self.s.check()
        self.assertBlocked(outcome, "diverged")
        self.assertEqual(
            outcome.detail, "the base was rewritten and the old base is unknown"
        )
        self.assertEqual(
            outcome.recovery,
            f"rebase by hand onto main, then ballast run resume {RUN}",
        )
        self.s.assert_unchanged(before)

    def test_no_committer_identity_changes_nothing(self) -> None:
        """R2, F-12: the replay never borrows the checkout's identity."""
        self.s.advance_base({"base.txt": "b\n"})
        self.s.gitconfig.write_text(
            '[protocol "file"]\n\tallow = always\n[user]\n\tuseConfigOnly = true\n'
        )
        self.s.git("config", "user.name", "Agent")
        self.s.git("config", "user.email", "agent@example.test")
        before = self.s.snapshot()
        with patch.dict(os.environ):
            for name in ("GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL", "EMAIL"):
                os.environ.pop(name, None)
            outcome = self.s.check()
        self.assertBlocked(outcome, "internal-error")
        self.assertEqual(outcome.detail, "no committer identity")
        self.assertEqual(
            outcome.recovery,
            "set user.name and user.email in your global Git configuration, then "
            f"ballast run resume {RUN}",
        )
        self.s.assert_unchanged(before)

    def test_unpinned_resume_is_refused(self) -> None:
        """Q11, first variant [DEC-0006, SEC-002]: no branch, or no feature, pinned."""
        before = self.s.snapshot()
        outcome = self.s.check("old1")
        self.assertBlocked(outcome, "wrong-branch", "old1")
        self.assertEqual(
            outcome.detail,
            "run old1 has no branch or feature pin (started before branch pinning)",
        )
        # #21 R11: the documented manual operator step, never a re-pin.
        self.assertEqual(
            outcome.recovery,
            'after checking the feature in the run\'s record, add "feature": '
            '"specs/<N>-<slug>" (and "branch" when missing) to the run\'s pin in the '
            "launcher state directory (see Runs started before branch pinning), "
            "then ballast run resume old1",
        )
        self.assertEqual(self.s.read_pin("old1"), {})
        # A #17 pin has the branch but not the feature whose Issue number
        # decides what may be rewritten; inputs.json is never asked.
        path = launcher.state_dir(self.s.root) / "draft-pr" / "old2.json"
        path.write_text(json.dumps({"branch": BRANCH}))
        outcome = self.s.check("old2")
        self.assertBlocked(outcome, "wrong-branch", "old2")
        self.assertEqual(
            outcome.detail,
            "run old2 has no feature pin (started before branch pinning)",
        )
        self.s.assert_unchanged(before)

    def test_issue_number_comes_from_the_pin(self) -> None:
        """SEC-002: an agent-written feature directory cannot widen the rule."""
        self.s.add_pre_receive()
        self.s.git("checkout", "-q", "-b", "release/3")
        self.s.publish("release/3")
        self.s.pin(branch="release/3")
        self.s.advance_base({"base.txt": "b\n"})
        self.s.clear_pushes()
        before = self.s.snapshot("release/3")
        # What run.py would read from agent-writable inputs.json.
        outcome = self.s.check(feature="specs/3-x")
        self.assertBlocked(outcome, "not-feature-branch")
        self.assertIn("is not the feature branch of #18", outcome.detail)
        self.assertEqual(self.s.snapshot("release/3"), before)
        self.assertEqual(self.s.pushes(), [])

    def test_only_feature_branches_are_rewritten(self) -> None:
        """Q28 [AC-021, FR-005, DEC-0004]."""
        self.s.add_pre_receive()
        self.s.git("checkout", "-q", "-b", "develop", "main")
        self.s.publish("develop")
        self.s.pin(branch="develop")
        self.assertEqual(self.s.check().outcome, "up-to-date")
        self.s.advance_base({"base.txt": "b\n"})
        self.s.clear_pushes()
        before = self.s.snapshot("develop")
        outcome = self.s.check()
        self.assertBlocked(outcome, "not-feature-branch")
        self.assertEqual(
            outcome.detail,
            "develop is not the feature branch of #18; Ballast rewrites only a "
            "branch named for the Issue",
        )
        self.assertEqual(
            outcome.recovery,
            "synchronize develop yourself, or run the feature on its own branch: "
            "git switch -c 18-x",
        )
        self.assertEqual(self.s.snapshot("develop"), before)
        self.s.git("checkout", "-q", "-b", "feat/180-x")
        self.s.pin(branch="feat/180-x")
        self.assertBlocked(self.s.check(), "not-feature-branch")
        self.s.git("checkout", "-q", "main")
        self.s.git("reset", "-q", "--hard", str(self.s.published("main")))
        self.s.advance("release", {"release.txt": "r\n"})
        self.s.pin(branch="main", base="release")
        self.s.clear_pushes()
        self.assertBlocked(self.s.check(), "not-feature-branch")
        self.s.git("checkout", "-q", BRANCH)
        # Defense only: run.py refuses a start without a feature directory.
        outcome = self.s.check("start9", starting=True, feature=None)
        self.assertEqual(outcome.cause, "not-feature-branch")
        self.assertEqual(
            outcome.detail, "the run has no feature directory, so no Issue number"
        )
        self.assertEqual(self.s.pushes(), [])

    def test_run_on_the_base_branch_only_fast_forwards(self) -> None:
        """Q29 [FR-005, FR-006, DEC-0003, N-10]."""
        self.s.git("checkout", "-q", "main")
        self.s.pin(branch="main")
        self.s.add_pre_receive()
        new = self.s.advance_base({"base.txt": "b\n"})
        self.s.clear_pushes()
        outcome = self.s.check()
        self.assertEqual(outcome.outcome, "synchronized", outcome)
        self.assertTrue(outcome.fast_forwarded)
        self.assertEqual(self.s.head(), new)
        self.assertEqual(self.s.pushes(), [])
        self.s.commit({"local.txt": "l\n"}, "local on main")
        self.s.advance_base({"base2.txt": "c\n"})
        self.s.clear_pushes()
        before = self.s.snapshot("main")
        outcome = self.s.check()
        self.assertBlocked(outcome, "diverged")
        self.assertEqual(
            outcome.detail, "main is the base branch and has local commits"
        )
        self.assertEqual(outcome.recovery, "git switch -c 18-x")
        self.assertEqual(self.s.snapshot("main"), before)
        self.s.git("reset", "-q", "--hard", "HEAD~1")
        self.s.write({"README.md": "dirty\n"})
        log: list = []
        with patch.object(branch_sync, "ARGV_LOG", log):
            outcome = self.s.check()
        self.assertBlocked(outcome, "dirty")
        self.assertFalse([argv for _, argv in log if "read-tree" in argv])
        self.assertEqual(self.s.pushes(), [])

    def test_untrusted_names_are_printed_as_data(self) -> None:
        """Q33 [FR-013]."""
        weird = "feat/18-$(touch${IFS}pwned);x"
        self.s.git("checkout", "-q", "-b", weird)
        self.s.pin(branch=weird)
        path = "we\nird $(id).txt"
        self.s.commit({path: "mine\n"}, "weird path")
        self.s.advance_base({path: "theirs\n"})
        outcome = self.s.check()
        self.assertBlocked(outcome, "conflict")
        text = "\n".join(line for _, line in branch_sync.format_lines(outcome))
        self.assertIn("we\\nird $(id).txt", text)
        self.assertEqual(text.count("\n"), 1)
        self.s.git("checkout", "-q", "main")
        self.s.git("checkout", "-q", "--detach")
        outcome = self.s.check()
        self.assertIn("git switch 'feat/18-$(touch${IFS}pwned);x'", outcome.recovery)
        self.assertFalse((self.s.root / "pwned").exists())

    def test_ctrl_c_during_the_replay(self) -> None:
        """Q34 [DEC-0001]."""
        self.s.advance_base({"base.txt": "b\n"})
        before = self.s.snapshot()
        with patch.object(
            branch_sync, "_crash", crash_at("after-replay", KeyboardInterrupt)
        ):
            outcome = self.s.check()
        self.assertBlocked(outcome, "internal-error")
        self.assertEqual(outcome.detail, "interrupted")
        self.assertTrue(outcome.interrupted)
        self.s.assert_unchanged(before)
        self.assertEqual(self.s.check().outcome, "synchronized")


class EnvironmentRefusalTests(SyncCase):
    """T024 [FR-010, FR-012, AC-017, DEC-0001, DEC-0007, N-09, N-12]."""

    def test_git_only_in_the_checkout(self) -> None:
        """Q36."""
        local = self.s.root / "bin"
        local.mkdir()
        (local / "git").symlink_to(shutil.which("git") or "/usr/bin/git")
        (self.s.root / ".git/info/exclude").write_text("bin/\n")
        before = self.s.snapshot()
        with patch.dict(os.environ, {"PATH": str(local)}):
            outcome = self.s.check()
        self.assertEqual(outcome.cause, "git-unavailable")
        self.assertEqual(outcome.detail, "git not found outside working trees")
        (local / "git").unlink()
        local.rmdir()
        self.s.assert_unchanged(before)

    def test_no_prompt_ever_runs(self) -> None:
        """Q39 [F-11, N-09]: a credential is needed and nothing can supply it."""

        class Deny(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                self.send_response(401)
                self.send_header("WWW-Authenticate", 'Basic realm="r"')
                self.send_header("Content-Length", "0")
                self.end_headers()

            def log_message(self, *_: object) -> None:
                pass

        server = HTTPServer(("127.0.0.1", 0), Deny)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        askpass, marker = self.s.marker_program("askpass")
        self.s.global_config(f"[core]\n\taskPass = {askpass}\n")
        url = f"http://127.0.0.1:{server.server_port}/o/r.git"
        before = self.s.snapshot()
        with (
            patch.object(branch_sync, "_url", lambda *_a, **_k: url),
            patch.dict(
                os.environ,
                {
                    "GIT_ASKPASS": str(askpass),
                    "SSH_ASKPASS": str(askpass),
                    "DISPLAY": ":0",
                },
            ),
        ):
            started = __import__("time").monotonic()
            outcome = self.s.check()
            elapsed = __import__("time").monotonic() - started
        self.assertBlocked(outcome, "fetch-failed")
        self.assertLess(elapsed, branch_sync.LS_REMOTE_TIMEOUT / 2)
        self.assertFalse(marker.exists())
        self.s.assert_unchanged(before)

    def test_partial_clones_are_refused(self) -> None:
        """Q41 [DEC-0007]."""
        for key, value in (
            ("remote.origin.promisor", "true"),
            ("extensions.partialClone", "origin"),
        ):
            with self.subTest(key=key):
                self.s.git("config", key, value)
                before = self.s.snapshot()
                outcome = self.s.check()
                self.assertBlocked(outcome, "git-unavailable")
                self.assertEqual(outcome.detail, "partial clone")
                self.assertEqual(
                    outcome.recovery,
                    "clone the repository again without --filter, then ballast run "
                    f"resume {RUN}",
                )
                self.s.assert_unchanged(before)
                self.s.git("config", "--unset", key)
        # A real blobless clone, whose origin names a marker upload-pack.
        self.s.run("git", "config", "uploadpack.allowFilter", "true", cwd=self.s.remote)
        self.s.publish()
        clone = self.s.base / "partial"
        self.s.run(
            "git",
            "clone",
            "-q",
            "--filter=blob:none",
            "--no-local",
            "-b",
            BRANCH,
            self.s.url,
            str(clone),
            cwd=self.s.base,
        )
        program, marker = self.s.marker_program("uploadpack")
        self.s.run("git", "config", "remote.origin.uploadpack", str(program), cwd=clone)
        self.s.advance_base({"base.txt": "b\n"})
        outcome = branch_sync.synchronize(
            clone, "part1", feature=FEATURE, starting=True
        )
        self.assertEqual(
            (outcome.cause, outcome.detail), ("git-unavailable", "partial clone")
        )
        self.assertFalse(marker.exists())

    def test_alternates_are_refused(self) -> None:
        """SEC-005: the shared store never borrows another store's objects."""
        other = self.s.base / "other.git"
        self.s.run("git", "init", "-q", "--bare", str(other), cwd=self.s.base)
        alternates = self.s.root / ".git/objects/info/alternates"
        alternates.parent.mkdir(parents=True, exist_ok=True)
        alternates.write_text(f"{other / 'objects'}\n")
        self.s.advance_base({"base.txt": "b\n"})
        before = self.s.snapshot()
        log: list = []
        with patch.object(branch_sync, "ARGV_LOG", log):
            outcome = self.s.check()
        self.assertBlocked(outcome, "git-unavailable")
        self.assertEqual(outcome.detail, "alternate object store")
        self.assertEqual(
            outcome.recovery,
            "clone the repository again without alternates, then ballast run "
            f"resume {RUN}",
        )
        self.assertFalse(
            [argv for _, argv in log if {"ls-remote", "fetch"} & set(argv)]
        )
        self.s.assert_unchanged(before)

    def test_shallow_checkouts_are_refused(self) -> None:
        """Q42 [N-12]."""
        self.s.publish()
        clone = self.s.base / "shallow"
        self.s.run(
            "git",
            "clone",
            "-q",
            "--depth",
            "1",
            "-b",
            BRANCH,
            self.s.url,
            str(clone),
            cwd=self.s.base,
        )
        self.s.advance_base({"base.txt": "b\n"})
        head = self.s.run("git", "rev-parse", "HEAD", cwd=clone)
        outcome = branch_sync.synchronize(
            clone, "shal1", feature=FEATURE, starting=True
        )
        self.assertEqual(
            (outcome.cause, outcome.detail), ("git-unavailable", "shallow checkout")
        )
        self.assertEqual(
            outcome.recovery,
            "git fetch --unshallow, then your ballast run start command",
        )
        self.assertEqual(self.s.run("git", "rev-parse", "HEAD", cwd=clone), head)


def _hold_lock(path: str, ready, release) -> None:  # noqa: ANN001
    import fcntl  # noqa: PLC0415

    with Path(path).open("a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        ready.set()
        release.wait(30)


class ConcurrencyTests(SyncCase):
    """T025 [AC-019, AC-020, FR-007, FR-016, F-03]."""

    def lock_path(self) -> Path:
        key = branch_sync._key(BRANCH)  # noqa: SLF001
        path = launcher.state_dir(self.s.root) / "branch-sync" / f"{key}.lock"
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def test_lock_held_by_another_process(self) -> None:
        """Q26."""
        self.s.advance_base({"base.txt": "b\n"})
        context = multiprocessing.get_context("fork")
        ready, release = context.Event(), context.Event()
        holder = context.Process(
            target=_hold_lock, args=(str(self.lock_path()), ready, release)
        )
        holder.start()
        self.addCleanup(holder.join)
        self.addCleanup(release.set)
        self.assertTrue(ready.wait(10))
        before = self.s.snapshot()
        outcome = self.s.check()
        self.assertBlocked(outcome, "busy")
        self.assertEqual(
            outcome.recovery,
            f"another ballast run is synchronizing {BRANCH}; retry when it finishes",
        )
        self.s.assert_unchanged(before)

    def test_two_checks_race(self) -> None:
        """Q27: at most one mutates; the other is busy."""
        self.s.advance_base({"base.txt": "b\n"})
        holding, finish = threading.Event(), threading.Event()
        results: dict[str, branch_sync.Outcome] = {}

        def wait_inside(point: str) -> None:
            if point == "locked" and threading.current_thread().name == "first":
                holding.set()
                finish.wait(30)

        with patch.object(branch_sync, "_crash", wait_inside):
            first = threading.Thread(
                name="first", target=lambda: results.update(first=self.s.check())
            )
            first.start()
            self.assertTrue(holding.wait(30))
            results["second"] = self.s.check()
            finish.set()
            first.join(60)
        self.assertEqual(results["first"].outcome, "synchronized", results)
        self.assertEqual(results["second"].cause, "busy", results)
        self.assertEqual(self.s.head(), results["first"].head_after)

    def test_commit_after_the_replay_is_busy_then_kept(self) -> None:
        """Q19 [F-03]."""
        self.s.publish()
        self.s.advance_base({"base.txt": "b\n"})
        published = self.s.published()
        late: dict[str, str] = {}

        def commit() -> None:
            late["commit"] = self.s.commit({"late.txt": "late\n"}, "late commit")

        with patch.object(
            branch_sync, "_crash", crash_at("after-replay", None, commit)
        ):
            outcome = self.s.check()
        self.assertBlocked(outcome, "busy")
        self.assertEqual(self.s.published(), published)
        self.assertEqual(self.s.head(), late["commit"])
        self.assertFalse(self.s.record_path().exists())
        outcome = self.s.check()
        self.assertEqual(outcome.outcome, "synchronized", outcome)
        self.assertIn("late commit", self.s.git("log", "--format=%s", "-3"))
        self.assertEqual(self.s.published(), self.s.head())


class TrustBoundaryTests(SyncCase):
    """T033 [AC-016, AC-017, FR-008, FR-012, DEC-0002, F-08, F-12, P-05]."""

    def test_protected_input_from_the_base_fails_closed(self) -> None:
        """Q23."""
        self.s.advance_base({"ballast.toml": PIN + "# a new pin\n"})
        outcome = self.s.check()
        self.assertBlocked(outcome, "protected-input")
        self.assertEqual(
            outcome.detail, "the base changed protected inputs: ballast.toml"
        )
        self.assertEqual(
            outcome.recovery,
            "review these changes, then run ballast trust (operator only)",
        )
        # AC-016: the synchronization is kept, and the launcher now refuses.
        self.assertEqual(self.s.head(), outcome.head_after)
        self.assertIn("# a new pin", (self.s.root / "ballast.toml").read_text())
        self.assertIn("ballast.toml", launcher._refusal(self.s.root) or "")  # noqa: SLF001

    def test_checkout_configuration_never_runs(self) -> None:
        """Q24 [AC-017, FR-012, F-12]."""
        self.s.commit(
            {".gitattributes": "*.txt filter=evil\nCHANGELOG.md merge=evil\n"},
            "agent attributes",
        )
        self.s.publish()
        self.s.advance_base({"base.txt": "b\n"})
        markers = []
        programs = {}
        for name in (
            "origin",
            "ssh",
            "include",
            "credential",
            "filter",
            "merge",
            "hook",
        ):
            program, marker = self.s.marker_program(name)
            programs[name] = program
            markers.append(marker)
        include = self.s.base / "included.config"
        include.write_text(f"[core]\n\tsshCommand = {programs['include']}\n")
        hooks = self.s.root / ".git/hooks"
        for hook in ("reference-transaction", "pre-push", "post-checkout"):
            shutil.copy(programs["hook"], hooks / hook)
        config = self.s.root / ".git/config"
        with config.open("a") as handle:
            handle.write(
                f'[remote "origin"]\n\turl = {programs["origin"]}\n'
                f'[url "{programs["origin"]}"]\n\tinsteadOf = https://\n'
                "\tinsteadOf = ssh://\n\tinsteadOf = file://\n"
                f"[core]\n\tsshCommand = {programs['ssh']}\n"
                f"[include]\n\tpath = {include}\n"
                f"[credential]\n\thelper = {programs['credential']}\n"
                f'[filter "evil"]\n\tclean = {programs["filter"]}\n'
                f"\tsmudge = {programs['filter']}\n\trequired = true\n"
                f'[merge "evil"]\n\tdriver = {programs["merge"]}\n'
                "[user]\n\tname = Agent\n\temail = agent@example.test\n"
                "[submodule]\n\trecurse = true\n"
            )
        outcome = self.s.check()
        self.assertEqual([m.name for m in markers if m.exists()], [])
        self.assertEqual(outcome.outcome, "synchronized", outcome)
        self.assertTrue(outcome.pushed)
        self.assertEqual(self.s.published(), outcome.head_after)
        committer = self.s.run(
            "git",
            "log",
            "-1",
            "--format=%cn <%ce>",
            str(outcome.head_after),
            cwd=self.s.remote,
        ).strip()
        self.assertEqual(committer, "Operator <operator@example.test>")

    def test_nested_repository_configuration_never_runs(self) -> None:
        """SEC-001: no `git status` runs inside a gitlink, under its own config."""
        nested = self.s.root / "sub"
        nested.mkdir()
        self.s.run("git", "init", "-q", cwd=nested)
        self.s.write({"x.txt": "x\n"}, nested)
        self.s.run("git", "add", "x.txt", cwd=nested)
        self.s.run("git", "commit", "-q", "-m", "nested", cwd=nested)
        self.s.git("add", "sub")  # a gitlink, as an agent can stage one
        self.s.git("commit", "-q", "-m", "gitlink")
        program, marker = self.s.marker_program("nested")
        with (nested / ".git/config").open("a") as handle:
            handle.write(f'[filter "evil"]\n\tclean = {program}\n')
        self.s.write({".gitattributes": "*.txt filter=evil\n", "x.txt": "y\n"}, nested)
        self.s.advance_base({"base.txt": "b\n"})
        outcome = self.s.check()
        self.assertFalse(marker.exists(), "a nested repository's filter ran")
        self.assertEqual(outcome.outcome, "synchronized", outcome)
        # A changed gitlink is still a change Ballast never touches.
        (nested / ".gitattributes").unlink()
        self.s.run("git", "commit", "-q", "-am", "nested 2", cwd=nested)
        self.s.git("add", "sub")
        self.s.advance_base({"base2.txt": "c\n"})
        before = self.s.snapshot()
        outcome = self.s.check()
        self.assertBlocked(outcome, "dirty")
        self.assertIn("sub", outcome.detail)
        self.s.assert_unchanged(before)
        self.assertFalse(marker.exists())

    def test_replace_refs_and_grafts_do_not_hide_the_base(self) -> None:
        """SEC-004: ancestry is answered from the real commits."""
        for how in ("replace", "grafts"):
            with self.subTest(how=how):
                self.s = Scratch(self)
                new = self.s.advance_base({"base.txt": "b\n"})
                # An agent fetches the new base and grafts the branch onto it.
                self.s.git("fetch", "-q", str(self.s.remote), "main")
                head = self.s.head()
                if how == "replace":
                    self.s.git("replace", "--graft", head, new)
                else:
                    (self.s.root / ".git/info/grafts").write_text(f"{head} {new}\n")
                # Plain git is fooled: the branch looks up to date.
                self.s.git("merge-base", "--is-ancestor", new, head)
                outcome = self.s.check()
                self.assertEqual(outcome.outcome, "synchronized", outcome)
                self.s.run(
                    "git",
                    "merge-base",
                    "--is-ancestor",
                    new,
                    str(outcome.head_after),
                    cwd=self.s.root,
                    env=os.environ | {"GIT_NO_REPLACE_OBJECTS": "1"},
                )

    def test_crash_after_a_protected_update_is_caught_by_the_launcher(self) -> None:
        """Q47 [P-05]."""
        self.s.publish()
        self.s.advance_base({".specify/memory/constitution.md": "# Changed\n"})
        with (
            patch.object(branch_sync, "_crash", crash_at("after-update-ref")),
            self.assertRaises(Killed),
        ):
            self.s.check()
        self.assertTrue(self.s.record_path().exists())
        self.assertEqual(self.s.events(), [])  # killed: nothing was recorded
        self.assertIn(
            ".specify/memory/constitution.md",
            launcher._refusal(self.s.root) or "",  # noqa: SLF001
        )
        self.s.trust()
        outcome = self.s.check()
        self.assertEqual(outcome.outcome, "up-to-date", outcome)
        # Row 1 clears the record without a HEAD change: P-05 is the launcher's.
        self.assertIsNone(outcome.recovered)
        self.assertFalse(self.s.record_path().exists())


class StaleEvidenceTests(SyncCase):
    """T034 [AC-018, FR-015]."""

    def overlap_setup(self, evidence: bool = True, overlap: bool = True) -> None:  # noqa: FBT001, FBT002
        self.s.git("checkout", "-q", "main")
        self.s.commit({"tools/a.py": "a = 1\n\n\n\nb = 1\n"}, "two lines")
        self.s.git("push", "-q", str(self.s.remote), "main")
        self.s.git("checkout", "-q", BRANCH)
        self.s.git("rebase", "-q", "main")
        files = (
            {"tools/a.py": "a = 1\n\n\n\nb = 2\n"} if overlap else {"tools/b.py": "x\n"}
        )
        if evidence:
            files |= {
                f"{FEATURE}/plan.md": "# Plan\n",
                f"{FEATURE}/reviews/r.md": "ok\n",
            }
        self.s.commit(files, "feature edits")
        self.s.trust()
        self.s.advance_base({"tools/a.py": "a = 2\n\n\n\nb = 1\n"})

    def stale_files(self) -> list[Path]:
        directory = draft_pr.stale_dir(self.s.root, FEATURE)
        old = ledger.archive_dir(self.s.root, RUN) / "branch-sync"
        self.assertFalse(old.exists(), "a record in agent-writable Git state")
        return sorted(directory.glob("*.json"))

    def test_overlap_marks_plan_and_review_stale(self) -> None:
        """Q25."""
        self.overlap_setup()
        outcome = self.s.check()
        self.assertEqual(outcome.outcome, "synchronized", outcome)
        self.assertEqual(
            (outcome.overlap, outcome.stale_plan, outcome.stale_review), (1, True, True)
        )
        (event,) = self.s.events()
        self.assertEqual(
            (event["overlap"], event["stale_plan"], event["stale_review"]),
            (1, True, True),
        )
        (path,) = self.stale_files()
        record = json.loads(path.read_text())
        self.assertEqual(record["paths"], ["tools/a.py"])
        self.assertEqual((record["feature"], record["truncated"]), (FEATURE, False))
        self.assertEqual(record["stale"], ["plan", "review"])
        ((_, line),) = branch_sync.format_lines(outcome)
        self.assertIn(
            "plan and review evidence may be stale: 1 file changed on both sides "
            "(see the Draft PR)",
            line,
        )

    def test_no_evidence_or_no_overlap_writes_nothing(self) -> None:
        for evidence, overlap in ((False, True), (True, False)):
            with self.subTest(evidence=evidence, overlap=overlap):
                self.s = Scratch(self)
                self.overlap_setup(evidence, overlap)
                outcome = self.s.check()
                self.assertEqual(outcome.outcome, "synchronized", outcome)
                self.assertIsNone(outcome.overlap)
                self.assertEqual(self.stale_files(), [])

    def test_kept_protected_input_sync_keeps_its_stale_record(self) -> None:
        """E-03 [AC-016, AC-018]: the sync is kept, so is its staleness."""
        self.overlap_setup()
        self.s.advance_base({".specify/memory/constitution.md": "# Changed\n"})
        outcome = self.s.check()
        self.assertBlocked(outcome, "protected-input")
        self.assertEqual(
            (outcome.overlap, outcome.stale_plan, outcome.stale_review), (1, True, True)
        )
        event = self.s.events()[-1]
        self.assertEqual(
            (event["overlap"], event["stale_plan"], event["stale_review"]),
            (1, True, True),
        )
        (path,) = self.stale_files()
        self.assertEqual(json.loads(path.read_text())["paths"], ["tools/a.py"])

    def test_completion_from_the_record_keeps_its_stale_record(self) -> None:
        """E-03: recovery rows 4 and 5 report the overlap of the pushed sync."""
        for later in (False, True):
            with self.subTest(row=5 if later else 4):
                self.s = Scratch(self)
                self.overlap_setup()
                self.s.publish()
                self.killed("after-push")
                record = json.loads(self.s.record_path().read_text())
                self.assertIsNotNone(record["old_base"])
                if later:
                    self.s.commit({"later.txt": "l\n"}, "after the pushed sync")
                outcome = self.s.check()
                self.assertEqual(outcome.outcome, "synchronized", outcome)
                self.assertTrue(outcome.recovered)
                self.assertEqual(
                    (outcome.overlap, outcome.stale_plan, outcome.stale_review),
                    (1, True, True),
                )
                (path,) = self.stale_files()
                self.assertEqual(json.loads(path.read_text())["paths"], ["tools/a.py"])


class PublishedBranchTests(SyncCase):
    """T039 [AC-012..AC-016, AC-021, FR-007, DEC-0003, DEC-0004, F-02, F-13, P-01]."""

    def test_published_branch_moves_under_a_lease(self) -> None:
        """Q14 [AC-012]."""
        self.s.publish()
        self.s.advance_base({"base.txt": "b\n"})
        outcome = self.s.check()
        self.assertEqual(outcome.outcome, "synchronized", outcome)
        self.assertTrue(outcome.pushed)
        self.assertEqual(self.s.published(), self.s.head())
        self.assertTrue(branch_sync.format_lines(outcome)[0][1].endswith(", pushed"))

    def test_conflict_recovery_works_as_printed(self) -> None:
        """Pilot finding [SC-003]: local `main` is stale; the branch is published."""
        self.s.commit({"tools/a.py": "a = 2\n"}, "feature edits a")
        self.s.publish()
        published = self.s.published()
        self.s.advance_base({"tools/a.py": "a = 3\n"})
        outcome = self.s.check()
        self.assertBlocked(outcome, "conflict")
        self.assertEqual(
            outcome.recovery,
            "rebase by hand: git pull --rebase origin main, resolve, git push "
            f"--force-with-lease={BRANCH}:{published} origin {BRANCH}, then ballast "
            f"run resume {RUN}",
        )
        # Follow it literally: the pull conflicts, the operator resolves, pushes.
        # `origin` names the pinned repository; point it at the scratch remote.
        origin = f"url.{self.s.url}.insteadOf=https://github.com/o/r.git"
        self.s.git(
            "-c", origin, "pull", "-q", "--rebase", "origin", "main", check=False
        )
        self.assertTrue(self.s.git("diff", "--name-only", "--diff-filter=U"))
        (self.s.root / "tools/a.py").write_text("a = 4\n")
        self.s.git("add", "tools/a.py")
        self.s.git("-c", "core.editor=true", "rebase", "--continue")
        self.s.git(
            "-c",
            origin,
            "push",
            "-q",
            f"--force-with-lease={BRANCH}:{published}",
            "origin",
            BRANCH,
        )
        self.assertEqual(self.s.check().outcome, "up-to-date")

    def test_both_sides_have_commits(self) -> None:
        """Q15 [AC-013]."""
        self.s.publish()
        theirs = self.s.push_as_someone_else({"theirs.txt": "t\n"})
        mine = self.s.commit({"mine.txt": "m\n"}, "mine")
        self.s.advance_base({"base.txt": "b\n"})
        before = self.s.snapshot()
        outcome = self.s.check()
        self.assertBlocked(outcome, "diverged")
        self.assertEqual(
            outcome.detail,
            f"{BRANCH} and the published branch both have commits the other lacks "
            f"({mine[:12]} vs {theirs[:12]})",
        )
        self.assertEqual(
            outcome.recovery,
            f"reconcile by hand: git pull --rebase origin {BRANCH}, then ballast run "
            f"resume {RUN}",
        )
        self.s.assert_unchanged(before)

    def test_published_branch_moves_during_the_check(self) -> None:
        """Q16 [AC-013, FR-007]."""
        self.s.publish()
        self.s.advance_base({"base.txt": "b\n"})
        before = self.s.snapshot()
        pushed: dict[str, str] = {}

        def race() -> None:
            pushed["theirs"] = self.s.push_as_someone_else({"race.txt": "r\n"})

        with patch.object(branch_sync, "_crash", crash_at("before-push", None, race)):
            outcome = self.s.check()
        self.assertBlocked(outcome, "diverged")
        self.assertEqual(outcome.detail, "the published branch moved during the check")
        self.assertEqual(self.s.published(), pushed["theirs"])
        self.assertEqual(self.s.snapshot()["head"], before["head"])
        self.assertEqual(self.s.snapshot()["status"], before["status"])

    def test_failed_push_restores_nothing_because_nothing_moved(self) -> None:
        """Q17 [AC-014]."""
        self.s.publish()
        self.s.advance_base({"base.txt": "b\n"})
        self.s.add_pre_receive(reject=True)
        before = self.s.snapshot()
        outcome = self.s.check()
        self.assertBlocked(outcome, "push-failed")
        self.assertFalse(outcome.retryable)
        self.assertEqual(
            outcome.detail, f"pushing {BRANCH} failed; a retry cannot succeed alone"
        )
        self.assertEqual(
            outcome.recovery,
            f"check o/r's branch rules for {BRANCH} (protection, required signatures), "
            f"then ballast run resume {RUN}",
        )
        self.assertFalse(self.s.events()[-1]["retryable"])
        self.s.assert_unchanged(before)
        (self.s.remote / "hooks/pre-receive").unlink()
        moved = self.s.base / "away.git"

        def unplug() -> None:
            self.s.remote.rename(moved)

        with patch.object(branch_sync, "_crash", crash_at("before-push", None, unplug)):
            outcome = self.s.check()
        moved.rename(self.s.remote)
        self.assertBlocked(outcome, "push-failed")
        self.assertTrue(outcome.retryable)
        self.assertEqual(outcome.recovery, f"ballast run resume {RUN}")
        self.s.assert_unchanged(before)
        self.assertEqual(self.s.check().outcome, "synchronized")

    def test_behind_its_published_branch_fast_forwards(self) -> None:
        """Q20 [AC-015]."""
        self.s.publish()
        theirs = self.s.push_as_someone_else({"theirs.txt": "t\n"})
        outcome = self.s.check()
        self.assertEqual(outcome.outcome, "up-to-date", outcome)
        self.assertTrue(outcome.fast_forwarded)
        self.assertEqual((self.s.head(), outcome.head_after), (theirs, theirs))
        self.assertTrue(self.s.events()[-1]["fast_forwarded"])

    def test_fast_forward_brings_protected_inputs_to_the_recheck(self) -> None:
        """Q21 [AC-015, AC-016, F-02]."""
        self.s.publish()
        self.s.push_as_someone_else({".specify/memory/extra.md": "x\n"})
        outcome = self.s.check()
        self.assertBlocked(outcome, "protected-input")
        self.assertEqual(
            outcome.detail,
            "the published branch changed protected inputs: .specify/memory/extra.md",
        )

    def test_dirty_tree_is_not_fast_forwarded(self) -> None:
        """Q22 [AC-015, AC-006, F-13]."""
        self.s.publish()
        self.s.push_as_someone_else({"theirs.txt": "t\n"})
        self.s.write({"README.md": "dirty\n"})
        before = self.s.snapshot()
        outcome = self.s.check()
        self.assertEqual(outcome.outcome, "up-to-date", outcome)
        self.assertEqual(
            outcome.note,
            "published branch is ahead; not fast-forwarded: uncommitted changes",
        )
        self.assertTrue(branch_sync.format_lines(outcome)[0][1].endswith(outcome.note))
        self.s.assert_unchanged(before)
        self.s.advance_base({"base.txt": "b\n"})
        outcome = self.s.check()
        self.assertBlocked(outcome, "dirty")
        self.s.assert_unchanged(before)

    def test_published_branch_without_feature_commits(self) -> None:
        """Q30, published variant."""
        self.s.git("reset", "-q", "--hard", "main")
        self.s.publish()
        new = self.s.advance_base({"base.txt": "b\n"})
        outcome = self.s.check()
        self.assertEqual(outcome.outcome, "synchronized", outcome)
        self.assertTrue(outcome.pushed)
        self.assertEqual((self.s.head(), self.s.published()), (new, new))

    def test_fast_forward_record_never_pushes(self) -> None:
        """Q45 [P-01, DEC-0003, DEC-0004]."""
        for branch in ("main", "develop"):
            with self.subTest(branch=branch):
                self.s = Scratch(self)
                if branch == "develop":
                    self.s.git("checkout", "-q", "-b", "develop", "main")
                    self.s.publish("develop")
                    self.s.push_as_someone_else({"theirs.txt": "t\n"}, "develop")
                else:
                    self.s.git("checkout", "-q", "main")
                    self.s.advance_base({"theirs.txt": "t\n"})
                self.s.pin(branch=branch)
                self.s.add_pre_receive()
                with (
                    patch.object(branch_sync, "_crash", crash_at("after-record")),
                    self.assertRaises(Killed),
                ):
                    self.s.check()
                record = json.loads(self.s.record_path(branch).read_text())
                # The record does not record a push (P-01).
                self.assertIn(record["published_old"], {None, record["new_head"]})
                self.s.commit({"local.txt": "l\n"}, "on the old local branch")
                self.s.clear_pushes()
                outcome = self.s.check()
                self.assertBlocked(outcome, "diverged")
                self.assertEqual(
                    outcome.recovery,
                    "git switch -c 18-x"
                    if branch == "main"
                    else "reconcile by hand: git pull --rebase origin develop, then "
                    f"ballast run resume {RUN}",
                )
                self.assertEqual(self.s.pushes(), [])
                self.assertFalse(self.s.record_path(branch).exists())


class RecoveryTests(SyncCase):
    """T040: the R5 recovery table.

    [AC-005, AC-014, FR-006, FR-007, SC-002, DEC-0005, N-01, N-03, N-11, P-02..P-04]
    """

    def reruns(self) -> dict[str, dict[str, object]]:
        return {
            "resume": {},
            "restart": {"run_id": "restart1", "starting": True},
            "start": {"run_id": "start2", "starting": True},
            "continue": {
                "run_id": "cont1",
                "branch": BRANCH,
                "base": "main",
                "source_run": RUN,
            },
        }

    def assertRecovered(self, outcome: branch_sync.Outcome) -> None:  # noqa: N802
        self.assertEqual(outcome.outcome, "synchronized", outcome)
        self.assertTrue(outcome.recovered)
        self.assertEqual(outcome.recovered_from, RUN)
        self.assertEqual(self.s.head(), outcome.head_after)
        self.assertFalse(self.s.record_path().exists())
        self.assertIn(
            f"completed the interrupted synchronization from run {RUN}",
            branch_sync.format_lines(outcome)[0][1],
        )

    def rerun(self, how: str) -> branch_sync.Outcome:
        kwargs = dict(self.reruns()[how])
        run_id = str(kwargs.pop("run_id", RUN))
        return self.s.check(run_id, **kwargs)

    def test_failure_after_the_push_is_completed_by_any_next_invocation(self) -> None:
        """Q18, first and second variants [DEC-0005, N-01]."""
        for how in self.reruns():
            with self.subTest(how=how):
                self.s = Scratch(self)
                self.s.publish()
                self.s.advance_base({"base.txt": "b\n"})
                with patch.object(
                    branch_sync, "_crash", crash_at("after-push", RuntimeError)
                ):
                    outcome = self.s.check()
                self.assertBlocked(outcome, "internal-error")
                pushed = self.s.published()
                self.assertEqual(
                    outcome.detail,
                    f"RuntimeError; the published branch already holds {pushed[:12]}",
                )
                self.assertEqual(
                    outcome.recovery,
                    f"ballast run resume {RUN} to finish the synchronization",
                )
                self.assertTrue(self.s.record_path().exists())
                outcome = self.rerun(how)
                self.assertRecovered(outcome)
                self.assertEqual(self.s.head(), pushed)

    def test_kill_after_the_push(self) -> None:
        """Q18, process killed after the push."""
        self.s.publish()
        self.s.advance_base({"base.txt": "b\n"})
        self.killed("after-push")
        pushed = self.s.published()
        self.assertNotEqual(self.s.head(), pushed)
        self.assertRecovered(self.s.check())
        self.assertEqual(self.s.head(), pushed)

    def test_kill_between_read_tree_and_update_ref(self) -> None:
        """Q18, third to fifth variants [P-02]."""
        for published in (False, True):
            with self.subTest(published=published):
                self.s = Scratch(self)
                if published:
                    self.s.publish()
                self.s.advance_base({"base.txt": "b\n"})
                self.killed("after-read-tree")
                self.s.write({"README.md": "operator edit\n", "scratch.txt": "new\n"})
                outcome = self.s.check()
                self.assertRecovered(outcome)
                self.assertEqual(
                    sorted(self.s.git("status", "--porcelain").splitlines()),
                    [" M README.md", "?? scratch.txt"],
                )
                if published:
                    self.assertEqual(self.s.published(), self.s.head())

    def test_completion_blocked_dirty_then_committed(self) -> None:
        """Q40, first variant [N-03]."""
        self.s.git("checkout", "-q", "main")
        self.s.commit({"notes.txt": "a\n\n\n\nb\n"}, "notes")
        self.s.git("push", "-q", str(self.s.remote), "main")
        self.s.git("checkout", "-q", BRANCH)
        self.s.git("rebase", "-q", "main")
        self.s.publish()
        self.s.advance_base({"notes.txt": "A\n\n\n\nb\n"})

        def dirty() -> None:
            # Edits a file the sync changes, so read-tree refuses to move it.
            self.s.write({"notes.txt": "a\n\n\n\nB\n"})

        with patch.object(branch_sync, "_crash", crash_at("after-push", None, dirty)):
            outcome = self.s.check()
        pushed = self.s.published()
        self.assertBlocked(outcome, "dirty")
        self.assertEqual(
            outcome.detail,
            f"a previous synchronization already pushed {pushed[:12]}; uncommitted "
            "changes: notes.txt",
        )
        self.assertTrue(
            outcome.recovery.startswith("move these changes aside without committing")
        )
        self.assertTrue(self.s.record_path().exists())
        outcome = self.s.check()
        self.assertBlocked(outcome, "dirty")
        self.assertIn("a previous synchronization already pushed", outcome.detail)
        self.s.git("commit", "-q", "-am", "operator commit")
        outcome = self.s.check()
        self.assertRecovered(outcome)
        self.assertTrue(outcome.pushed)
        self.assertEqual(self.s.published(), self.s.head())
        self.assertEqual(self.s.head("HEAD~1"), pushed)
        self.assertIn("operator commit", self.s.git("log", "-1", "--format=%s"))
        self.assertEqual((self.s.root / "notes.txt").read_text(), "A\n\n\n\nB\n")

    def test_conflicting_commit_after_a_pushed_sync(self) -> None:
        """Q40, conflict variant."""
        self.s.publish()
        self.s.advance_base({"base.txt": "b\n"})

        def dirty() -> None:
            self.s.write({"base.txt": "operator\n"})

        with patch.object(branch_sync, "_crash", crash_at("after-push", None, dirty)):
            self.s.check()
        pushed = self.s.published()
        old = json.loads(self.s.record_path().read_text())["old_head"]
        self.s.git("add", "base.txt")
        self.s.git("commit", "-q", "-m", "operator base.txt")
        outcome = self.s.check()
        self.assertBlocked(outcome, "conflict")
        self.assertTrue(
            outcome.detail.startswith("replaying ")
            and f"onto the already pushed {pushed[:12]} conflicts in base.txt"
            in outcome.detail
        )
        self.assertEqual(
            outcome.recovery,
            f"git rebase --onto {pushed} {old} {BRANCH}, resolve, then ballast run "
            f"resume {RUN}",
        )
        self.assertTrue(self.s.record_path().exists())

    def test_commit_between_the_push_and_the_compare_and_swap(self) -> None:
        """Q40, second and third variants [P-04]."""
        for bare_commit in (False, True):
            with self.subTest(bare_commit=bare_commit):
                self.s = Scratch(self)
                self.s.publish()
                self.s.advance_base({"base.txt": "b\n"})
                landed: dict[str, str] = {}

                def land(
                    bare: bool = bare_commit,  # noqa: FBT001
                    landed: dict[str, str] = landed,
                ) -> None:
                    if bare:
                        self.s.git(
                            "commit", "-q", "-m", "bare commit of the staged tree"
                        )
                        landed["x"] = self.s.head()
                        return
                    # Another actor's commit on the old branch, made without
                    # the index: an empty change on top of OLD.
                    old = self.s.head()
                    commit = self.s.git(
                        "commit-tree",
                        f"{old}^{{tree}}",
                        "-p",
                        old,
                        "-m",
                        "landed elsewhere",
                    ).strip()
                    self.s.git("update-ref", f"refs/heads/{BRANCH}", commit)
                    landed["x"] = commit

                with patch.object(
                    branch_sync, "_crash", crash_at("after-read-tree", None, land)
                ):
                    outcome = self.s.check()
                self.assertBlocked(outcome, "busy")
                self.assertTrue(
                    outcome.detail.startswith("the published branch already holds")
                )
                self.assertEqual(
                    outcome.recovery,
                    f"ballast run resume {RUN} to finish the synchronization",
                )
                self.assertEqual(self.s.head(), landed["x"])
                self.assertEqual(self.s.git("status", "--porcelain"), "")
                pushed = self.s.published()
                self.s.clear_pushes()
                self.s.add_pre_receive()
                outcome = self.s.check()
                self.assertRecovered(outcome)
                if bare_commit:
                    self.assertEqual(self.s.head(), pushed)
                    self.assertEqual(self.s.pushes(), [])
                else:
                    self.assertEqual(self.s.head("HEAD~1"), pushed)
                    self.assertEqual(self.s.published(), self.s.head())

    def test_local_moved_but_push_missing(self) -> None:
        """T-01, R5 row 2: the one row that pushes from a record."""
        for records_push in (True, False):
            with self.subTest(records_push=records_push):
                self.s = Scratch(self)
                self.s.publish()
                published_old = self.s.published()
                self.s.advance_base({"base.txt": "b\n"})
                self.killed("after-record")
                path = self.s.record_path()
                record = json.loads(path.read_text())
                new = record["new_head"]
                self.assertEqual(record["published_old"], published_old)
                if not records_push:
                    record["published_old"] = new  # a fast-forward record (P-01)
                    path.write_text(json.dumps(record))
                self.s.git("reset", "-q", "--hard", new)
                self.s.add_pre_receive()
                self.s.clear_pushes()
                outcome = self.s.check()
                self.assertFalse(path.exists())
                if records_push:
                    self.assertRecovered(outcome)
                    self.assertTrue(outcome.pushed)
                    self.assertEqual(self.s.published(), new)
                    self.assertTrue(self.s.pushes())
                else:  # row 7: never pushed from a record that records no push
                    self.assertBlocked(outcome, "diverged")
                    self.assertEqual(self.s.pushes(), [])
                    self.assertEqual(self.s.published(), published_old)

    def test_row_5_reads_attributes_from_the_fetched_base(self) -> None:
        """E-04 [R2, ADR-0005]: never from the pushed feature commit."""
        self.s.publish()
        base = self.s.advance_base({"base.txt": "b\n"})
        self.killed("after-push")
        pushed = self.s.published()
        self.s.commit({"later.txt": "l\n"}, "after the pushed sync")
        log: list = []
        with patch.object(branch_sync, "ARGV_LOG", log):
            outcome = self.s.check()
        self.assertRecovered(outcome)
        merges = [argv for _, argv in log if "merge-tree" in argv]
        self.assertTrue(merges)
        for argv in merges:
            self.assertIn(f"--attr-source={base}", argv)
            self.assertNotIn(f"--attr-source={pushed}", argv)

    def test_pruned_new_head_and_the_record_is_cleared(self) -> None:
        """Q43, first variant [N-11]."""
        self.s.advance_base({"base.txt": "b\n"})
        self.killed("after-read-tree")
        new = json.loads(self.s.record_path().read_text())["new_head"]
        self.s.git("reflog", "expire", "--expire=now", "--all")
        self.s.git("gc", "-q", "--prune=now")
        result = subprocess.run(  # noqa: S603
            ["git", "cat-file", "-e", new],  # noqa: S607
            cwd=self.s.root,
            check=False,
            capture_output=True,
        )
        self.assertNotEqual(result.returncode, 0)
        outcome = self.s.check()
        self.assertBlocked(outcome, "dirty")
        self.assertTrue(outcome.recovery.startswith("commit or finish these changes"))
        self.assertFalse(self.s.record_path().exists())

    def test_crash_during_read_tree(self) -> None:
        """Q46 [P-03]."""
        for lock in (True, False):
            with self.subTest(lock=lock):
                self.s = Scratch(self)
                self.s.advance_base({"base.txt": "b\n", "README.md": "readme v2\n"})

                def half(locked: bool = lock) -> None:  # noqa: FBT001
                    self.s.write({"base.txt": "b\n"})
                    if locked:
                        (self.s.root / ".git/index.lock").write_text("")

                self.killed("after-record", half)
                record = json.loads(self.s.record_path().read_text())
                if lock:
                    outcome = self.s.check()
                    self.assertBlocked(outcome, "in-progress")
                    self.assertTrue(
                        outcome.detail.startswith(
                            "another git process may hold the index"
                        )
                    )
                    (self.s.root / ".git/index.lock").unlink()
                outcome = self.s.check()
                self.assertBlocked(outcome, "dirty")
                self.assertEqual(
                    outcome.detail,
                    "an interrupted update left these files at the synchronized "
                    "content: base.txt",
                )
                command = (
                    f"git restore --source={record['new_head']} --staged --worktree ."
                )
                self.assertTrue(outcome.recovery.startswith(command))
                self.assertTrue(self.s.record_path().exists())
                self.s.git(*command.split()[1:])
                self.assertRecovered(self.s.check())
        # One path that differs from new_head is the operator's: normal advice.
        self.s = Scratch(self)
        self.s.advance_base({"base.txt": "b\n"})

        def other() -> None:
            self.s.write({"base.txt": "not the synchronized content\n"})

        self.killed("after-record", other)
        outcome = self.s.check()
        self.assertBlocked(outcome, "dirty")
        self.assertTrue(outcome.detail.startswith("uncommitted changes"))


class DocumentationTests(unittest.TestCase):
    """T048 [FR-014, SC-003]: every cause and recovery is in the operator policy."""

    def section(self) -> str:
        text = (ROOT / "templates/policies/spec-kit-workflow.md").read_text()
        start = text.index("## Branch synchronization")
        return text[start : text.index("\n## ", start + 1)]

    def test_every_cause_and_recovery_is_documented(self) -> None:
        section = self.section()
        for cause in sorted(ledger.SYNC_CAUSES):
            self.assertIn(f"`{cause}`", section)
        for key, template in branch_sync.RECOVERY.items():
            with self.subTest(key=key):
                self.assertIn(template.replace("{rerun}", "rerun"), section)
        for text in (
            "2.41",
            "Shallow checkouts and partial",
            "not synchronized",
            "`protected-input` keeps the completed",
            "Differences from `git rebase`",
            "unsigned",
            "Draft PR",
        ):
            self.assertIn(text, " ".join(section.split()))

    def test_run_help_mentions_the_check(self) -> None:
        result = subprocess.run(  # noqa: S603
            [sys.executable, "-I", "-S", str(TOOLS / "run.py"), "--help"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertIn("BLOCKED_UPSTREAM_SYNC", result.stderr)
        self.assertIn("Branch synchronization", " ".join(result.stderr.split()))

    def test_ballast_run_help_mentions_the_check(self) -> None:
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        project = Path(directory.name)
        shutil.copytree(
            TOOLS,
            project / ".ballast/spec_workflow",
            ignore=shutil.ignore_patterns("__pycache__"),
        )
        env = {
            **os.environ,
            "XDG_STATE_HOME": str(operator_state(self)),
            "BALLAST_STANDARD_DIR": str(ROOT),
        }
        for args in (["trust"], ["run", "--help"]):
            result = subprocess.run(  # noqa: S603
                [sys.executable, "-I", "-S", str(ROOT / "tools/ballast"), *args],
                cwd=project,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertIn(
            "BLOCKED_UPSTREAM_SYNC", result.stderr, result.stdout + result.stderr
        )


@unittest.skipUnless(GIT_OK, "needs git 2.41 or later")
class Sha256Tests(unittest.TestCase):
    """Q38 [F-09]."""

    def test_sha256_repository(self) -> None:
        scratch = Scratch(self, object_format="sha256")
        scratch.advance_base({"base.txt": "b\n"})
        log: list = []
        with patch.object(branch_sync, "ARGV_LOG", log):
            outcome = scratch.check()
        self.assertEqual(outcome.outcome, "synchronized", outcome)
        self.assertEqual(len(outcome.head_after), 64)
        init = next(argv for _, argv in log if "init" in argv)
        self.assertIn("--object-format=sha256", init)


class ChatRerunTests(SyncCase):
    """#20 R5: a Chat step names its own rerun command; nothing else changes."""

    def test_default_recovery_is_unchanged_and_chat_names_its_step(self) -> None:
        self.s.advance_base({"base.txt": "b\n"})
        self.s.write({"README.md": "edited\n"})
        default = self.s.check()
        self.assertBlocked(default, "dirty")
        chat = self.s.check(rerun=f"ballast run step {RUN} plan")
        lines = self.assertBlocked(chat, "dirty")
        self.assertEqual(
            default.recovery.replace(f"ballast run resume {RUN}", "X"),
            chat.recovery.replace(f"ballast run step {RUN} plan", "X"),
        )
        self.assertIn(f"ballast run resume {RUN}", default.recovery)
        self.assertNotIn("resume", chat.recovery)
        self.assertTrue(lines[1][1].endswith(f"then ballast run step {RUN} plan"))


if __name__ == "__main__":
    unittest.main()
