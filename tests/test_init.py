"""Offline checks for tools/init (`ballast init`, #13).

tools/init runs in process with tests/test_setup.py's fakes patched onto the
setup module it loaded, so installation never touches the network.
"""

from __future__ import annotations

import ast
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tomllib
import unittest
from contextlib import ExitStack, redirect_stderr, redirect_stdout
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING
from unittest.mock import patch

if TYPE_CHECKING:
    from collections.abc import Iterator

ROOT = Path(__file__).resolve().parents[1]
_loader = SourceFileLoader("init_tool", str(ROOT / "tools/init"))
init = module_from_spec(spec_from_loader("init_tool", _loader))
_loader.exec_module(init)

sys.path.insert(0, str(ROOT / "tests"))
import test_setup as setup_tests  # noqa: E402
from test_autonomy import operator_state  # noqa: E402

sys.path.pop(0)

REF = "vA"
PATCH = ".ballast/init/proposed.patch"
NEXT_TRUST = "Next: review the files above, then run `ballast trust`"
PROTECTED = (
    "Review these protected inputs: ballast.toml, .specify/, .ballast/spec_workflow/"
)
READINESS = ("instructions", "ignored-paths", "pinned-version", "trust-boundary")
OWNED = (
    "ballast.toml",
    ".specify/memory/constitution.md",
    "AGENTS.md",
    "CLAUDE.md",
    ".gitignore",
)
CI = """\
name: ci
on: push
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pytest
      - name: lint
        run: |
          ruff check
          echo "${{ secrets.TOKEN }}"
      - run: make check && touch {marker}
"""
PYPROJECT = """\
[project]
name = "demo"
description = "Demo service"

[tool.pytest.ini_options]
addopts = "-q"
"""
AGENTS = "# Demo agents\n\nProject rules stay here.\n"

# Programs started while STARTED is a list (AC-015).
STARTED: list[str] | None = None


def _audit(event: str, args: tuple) -> None:
    if STARTED is None:
        return
    if event == "subprocess.Popen":
        executable, command = args[0], args[1]
        first = command if isinstance(command, (str, bytes)) else command[0]
        STARTED.append(Path(os.fsdecode(executable or first)).name)
    elif event in {"os.system", "os.exec", "os.posix_spawn", "os.spawn"}:
        STARTED.append(f"{event}:{args[0]!r}")


sys.addaudithook(_audit)


def fakes() -> ExitStack:
    """test_setup's fakes, patched onto the setup module init loaded."""
    stack = ExitStack()
    tool = init.setup
    stack.enter_context(patch.object(tool, "_fetch_source", setup_tests.fake_fetch))
    stack.enter_context(patch.object(tool.Setup, "run", setup_tests.fake_run))
    stack.enter_context(patch.object(tool.shutil, "which", lambda n: f"/usr/bin/{n}"))
    offline = AssertionError("unexpected network request")
    stack.enter_context(
        patch.object(tool.urllib.request, "urlretrieve", side_effect=offline)
    )
    return stack


class Terminal(io.StringIO):
    """A stream that claims to be a terminal, for init's prompts."""

    def isatty(self) -> bool:
        return True


def git(root: Path, *args: str) -> str:
    """Plain git for fixtures, with a fixed identity."""
    return setup_tests.git(root, *args)


def digest(path: Path) -> str:
    """Return a file's content digest, or a link's target."""
    if path.is_symlink():
        return "link:" + str(path.readlink())
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(root: Path, files: dict[str, str | bytes]) -> None:
    """Write fixture files, creating their parents."""
    for name, content in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content)


def section(report: str) -> dict[str, str]:
    """Return the lines of a report that must not change on a rerun (F-001)."""
    lines = report.splitlines()
    start = lines.index("Readiness:")
    block = [lines[start]]
    for line in lines[start + 1 :]:
        if not line.startswith("  "):
            break
        block.append(line)
    return {
        "readiness": "\n".join(block),
        "protected": next(line for line in lines if line.startswith("Review these")),
        "next": next(line for line in lines if line.startswith("Next:")),
    }


def readiness(report: str) -> dict[str, tuple[str, str]]:
    """`name -> (status, detail)` of the report's readiness block."""
    found = {}
    for line in section(report)["readiness"].splitlines()[1:]:
        name, status, detail = line.split(maxsplit=2)
        found[name] = (status, detail)
    return found


class InitCase(unittest.TestCase):
    """A scratch project, isolated operator state, and init with fakes."""

    def setUp(self) -> None:
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.base = Path(directory.name).resolve()
        self.root = self.base / "project"
        self.root.mkdir()
        self.marker = self.base / "ran"
        environment = patch.dict(
            os.environ,
            {
                # Outside every temp root and working tree, as state_dir requires.
                "XDG_STATE_HOME": str(operator_state(self)),
                "GIT_CONFIG_GLOBAL": os.devnull,
                "GIT_CONFIG_NOSYSTEM": "1",
            },
        )
        environment.start()
        self.addCleanup(environment.stop)
        self.addCleanup(setup_tests.FAKE.clear)

    def init(
        self, *flags: str, root: Path | None = None, ref: str = REF
    ) -> tuple[int, str]:
        out, err = io.StringIO(), io.StringIO()
        arguments = ["--project", str(root or self.root), "--ref", ref, *flags]
        with fakes(), redirect_stdout(out), redirect_stderr(err):
            code = init.cli(arguments)
        return code, out.getvalue()

    def blank(self, *flags: str) -> tuple[int, str]:
        choices = ("--description", "Scratch service", "--stack", "python")
        return self.init(*choices, *flags)

    def established(self, **extra: str | bytes) -> None:
        """Write the Python fixture: manifest, CI, Makefile, AGENTS.md, policy."""
        git(self.root, "init", "-q")
        files: dict[str, str | bytes] = {
            "pyproject.toml": PYPROJECT,
            ".github/workflows/ci.yml": CI.format(marker=self.marker),
            "Makefile": f"check:\n\ttouch {self.marker}\n",
            "AGENTS.md": AGENTS,
            "docs/policies/project/security.md": "project rule\n",
            **extra,
        }
        write(self.root, {k: v for k, v in files.items() if v != ""})

    def state(self, root: Path | None = None) -> Path:
        return init.launcher.state_dir(root or self.root)

    def post_trust(self, root: Path | None = None) -> None:
        """Record the operator's trust, then the preflight must pass (AC-002)."""
        root = root or self.root
        with redirect_stdout(io.StringIO()):
            self.assertEqual(init.launcher._trust(root, self.state(root)), 0)  # noqa: SLF001
        self.assertIsNone(init.launcher._refusal(root))  # noqa: SLF001

    def ignored(self, *paths: str) -> list[str]:
        result = subprocess.run(  # noqa: S603
            ["git", "check-ignore", "--no-index", *paths],  # noqa: S607
            cwd=self.root,
            capture_output=True,
            text=True,
            check=False,
        )
        return result.stdout.split()

    def config(self) -> dict:
        return tomllib.loads((self.root / "ballast.toml").read_text())

    def project_files(self) -> dict[str, str]:
        """Digests of every tracked or trackable (not ignored) file."""
        listed = git(
            self.root, "ls-files", "-z", "--cached", "--others", "--exclude-standard"
        )
        return {
            name: digest(self.root / name)
            for name in sorted(set(listed.split("\0")) - {""})
        }

    def assert_installed(self) -> None:
        status = init.setup.Setup(self.root).status(self.state())
        self.assertEqual(status, "current")


# --- US1: a blank directory ---------------------------------------------------


class BlankRepositoryTests(InitCase):
    """AC-001 to AC-003, SC-002: one init and one trust adopt a blank directory."""

    def test_flags_adopt_an_empty_directory(self) -> None:
        code, report = self.blank()
        self.assertEqual(code, 0, report)
        self.assertTrue((self.root / ".git").is_dir())
        self.assertEqual((self.root / ".gitignore").read_text(), init.setup.GITIGNORE)
        self.assertEqual(self.config()["standard"]["ref"], REF)
        self.assertTrue((self.root / ".specify/memory/constitution.md").is_file())
        self.assertTrue((self.root / "AGENTS.md").is_file())
        self.assertEqual((self.root / "CLAUDE.md").readlink(), Path("AGENTS.md"))
        self.assert_installed()
        self.assertIn("ballast init: blank repository at", report)
        self.assertIn(NEXT_TRUST, report)

    def test_a_terminal_asks_exactly_two_questions(self) -> None:
        questions: list[str] = []

        def answer(question: str) -> str:
            questions.append(question)
            return "Scratch service" if len(questions) == 1 else "neutral"

        out = Terminal()
        with (
            fakes(),
            redirect_stdout(out),
            redirect_stderr(io.StringIO()),
            patch.object(sys, "stdin", Terminal()),
            patch("builtins.input", answer),
        ):
            code = init.cli(["--project", str(self.root), "--ref", REF])
        self.assertEqual(code, 0, out.getvalue())
        self.assertEqual(len(questions), 2)
        self.assertIn("description", questions[0].lower())
        self.assertIn("stack", questions[1].lower())
        constitution = (self.root / ".specify/memory/constitution.md").read_text()
        self.assertIn("Scratch service", constitution)
        self.assertIn("Stack: neutral (operator)", constitution)

    def test_preflight_passes_after_trust(self) -> None:
        for fixture in ("blank", "git-only"):
            with self.subTest(fixture=fixture):
                self.root = self.base / fixture
                self.root.mkdir()
                if fixture == "git-only":
                    git(self.root, "init", "-q")
                code, report = self.blank()
                self.assertEqual(code, 0, report)
                refusal = init.launcher._refusal(self.root)  # noqa: SLF001
                self.assertTrue(refusal.startswith("no trusted baseline"), refusal)
                self.post_trust()


class MaterialChoiceRefusalTests(InitCase):
    """AC-004: without a terminal a missing choice refuses; nothing is written."""

    def test_each_missing_flag_is_named(self) -> None:
        for flags, named in (
            (("--stack", "python"), "--description TEXT"),
            (("--description", "Scratch"), "--stack python|node|rust|go|neutral"),
        ):
            with self.subTest(named=named):
                code, report = self.init(*flags)
                self.assertEqual(code, 2, report)
                self.assertIn("stopped at choose: missing the", report)
                self.assertIn(named, report)
                self.assertEqual(list(self.root.iterdir()), [])

    def test_invalid_values_are_refused(self) -> None:
        for flags, rule in (
            (("--stack", "cobol"), "the stack must be one of"),
            (("--description", "uses `rm`"), "without a backtick"),
            (("--description", "x" * 201), "1 to 200 printable characters"),
            (("--description", "two\nlines"), "1 to 200 printable characters"),
        ):
            with self.subTest(rule=rule, flags=flags):
                arguments = {"--description": "Scratch", "--stack": "python"}
                arguments[flags[0]] = flags[1]
                code, report = self.init(*[x for kv in arguments.items() for x in kv])
                self.assertEqual(code, 2, report)
                self.assertIn(rule, report)
                self.assertEqual(list(self.root.iterdir()), [])


# --- US2: an established repository ------------------------------------------


class EstablishedRepositoryTests(InitCase):
    """AC-006 to AC-012: existing files stay byte-identical; changes are a patch."""

    KEPT = (
        "pyproject.toml",
        ".github/workflows/ci.yml",
        "Makefile",
        "AGENTS.md",
        "docs/policies/project/security.md",
    )

    def test_existing_files_are_kept_and_the_section_is_a_patch(self) -> None:
        self.established()
        before = {name: digest(self.root / name) for name in self.KEPT}
        github = setup_tests.tree(self.root / ".github")
        code, report = self.init()
        self.assertEqual(code, 0, report)
        self.assertEqual({n: digest(self.root / n) for n in self.KEPT}, before)
        patch_text = (self.root / PATCH).read_text()
        self.assertIn("+++ b/AGENTS.md", patch_text)
        self.assertIn("+## Ballast workflow", patch_text)
        applied = subprocess.run(
            ["git", "apply", "--check", ".ballast/init/proposed.patch"],  # noqa: S607
            cwd=self.root,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(applied.returncode, 0, applied.stderr)
        self.assertIn(f"Proposed patch: {PATCH} (AGENTS.md: Ballast section)", report)
        self.assertFalse(os.path.lexists(self.root / "CLAUDE.md"))
        self.assertEqual(setup_tests.tree(self.root / ".github"), github)
        optional = "Not written (optional): .github/pull_request_template.md"
        self.assertIn(optional, report)
        self.assertIn("README: Using the copy-once templates", report)
        self.assertEqual(readiness(report)["instructions"][0], "warning")
        self.post_trust()  # AC-010: the patch is not applied

    def test_only_claude_md_gets_the_patch(self) -> None:
        self.established(**{"AGENTS.md": "", "CLAUDE.md": AGENTS})
        code, report = self.init()
        self.assertEqual(code, 0, report)
        self.assertFalse(os.path.lexists(self.root / "AGENTS.md"))
        self.assertEqual((self.root / "CLAUDE.md").read_text(), AGENTS)
        self.assertIn("+++ b/CLAUDE.md", (self.root / PATCH).read_text())

    def test_the_block_is_appended_once(self) -> None:
        for old in ("node_modules/\n", "node_modules/"):
            with self.subTest(old=old):
                self.root = self.base / f"append-{len(old)}"
                self.root.mkdir()
                self.established(**{".gitignore": old})
                code, report = self.init()
                self.assertEqual(code, 0, report)
                expected = old + ("" if old.endswith("\n") else "\n")
                expected += init.setup.GITIGNORE
                self.assertEqual((self.root / ".gitignore").read_text(), expected)
                self.assertIn("Appended the Ballast ignore block to .gitignore", report)
                code, _ = self.init()
                self.assertEqual((self.root / ".gitignore").read_text(), expected)


class IgnoreConflictTests(InitCase):
    """AC-009, AC-013: a conflicting rule stops before installing, with a patch."""

    def test_an_un_ignoring_rule_stops_before_install(self) -> None:
        # A nested rule outranks the root block; `!.ballast/spec_workflow/`
        # cannot conflict, since git never re-includes below an ignored `.ballast/`.
        self.established(**{"docs/.gitignore": "# keep\n!policies/*.md\n"})
        code, report = self.init()
        self.assertEqual(code, 1, report)
        self.assertIn("stopped at ignore: installed paths are not ignored", report)
        self.assertIn("(rule docs/.gitignore:2:!policies/*.md)", report)
        patch_text = (self.root / PATCH).read_text()
        explained = "+# ballast init: un-ignores docs/policies/model-routing.md:"
        self.assertIn(explained, patch_text)
        self.assertIn("+# !policies/*.md", patch_text)
        self.assertFalse(os.path.lexists(self.root / ".ballast/spec_workflow"))
        self.assertFalse(os.path.lexists(self.root / "ballast.toml"))
        self.assertFalse((self.state() / "setup-attempt.json").exists())
        self.assertIn("Not written: ballast.toml", report)
        self.assertEqual(
            (self.root / "docs/.gitignore").read_text(), "# keep\n!policies/*.md\n"
        )

    def test_a_rule_outside_the_repository_files_is_named_without_a_patch(self) -> None:
        self.established()
        write(self.root, {".git/info/exclude": "docs/policies/project/\n"})
        code, report = self.init()
        self.assertEqual(code, 1, report)
        self.assertIn(
            "project files are ignored: docs/policies/project/security.md "
            "(rule .git/info/exclude:1:docs/policies/project/)",
            report,
        )
        # Only the AGENTS.md section is proposed; the rule is named, not edited.
        self.assertNotIn("# ballast init:", (self.root / PATCH).read_text())
        self.assertEqual(
            (self.root / ".git/info/exclude").read_text(), "docs/policies/project/\n"
        )

    def test_an_ignored_project_file_is_not_ready(self) -> None:
        # F-006: a rule ignoring ballast.toml is proposed, never rewritten.
        self.established(**{".gitignore": "ballast.toml\n"})
        code, report = self.init()
        self.assertEqual(code, 1, report)
        self.assertEqual(readiness(report)["ignored-paths"][0], "not-ready")
        patch_text = (self.root / PATCH).read_text()
        self.assertIn("+# ballast init: ignores ballast.toml:", patch_text)
        first = (self.root / ".gitignore").read_text().splitlines()[0]
        self.assertEqual(first, "ballast.toml")


# --- US3: the trust boundary and the tracked/ignored split -------------------


class BoundaryTests(InitCase):
    """AC-013, AC-014, AC-018, AC-019, AC-020."""

    def fixtures(self) -> Iterator[str]:
        for fixture in ("blank", "git-only", "established"):
            self.root = self.base / fixture
            self.root.mkdir()
            if fixture == "git-only":
                git(self.root, "init", "-q")
            if fixture == "established":
                self.established()
            yield fixture

    def test_split_trust_and_git_state(self) -> None:
        for fixture in self.fixtures():
            with self.subTest(fixture=fixture):
                config = self.root / ".git/config"
                inode = config.stat().st_ino if config.exists() else None
                code, report = self.blank()
                self.assertEqual(code, 0, report)
                probes = [path for path, _ in init.setup.IGNORE_PROBES]
                wanted = {path for path, ignored in init.setup.IGNORE_PROBES if ignored}
                self.assertEqual(set(self.ignored(*probes)), wanted)
                owned = [n for n in OWNED if os.path.lexists(self.root / n)]
                self.assertEqual(self.ignored(*owned), [])
                self.assertFalse((self.state() / "trusted.json").exists())
                self.assertIsNotNone(init.launcher._refusal(self.root))  # noqa: SLF001
                self.assertIn(PROTECTED, report)
                self.assertIn(NEXT_TRUST, report)
                self.assertEqual(git(self.root, "rev-list", "--all"), "")
                self.assertEqual(git(self.root, "remote"), "")
                if inode is not None:
                    self.assertEqual(config.stat().st_ino, inode)

    def test_no_active_permission(self) -> None:
        self.established()
        code, report = self.init()
        self.assertEqual(code, 0, report)
        self.assertNotIn("agents", self.config())
        rules = [
            line
            for line in (self.root / "ballast.toml").read_text().splitlines()
            if "Bash(" in line
        ]
        self.assertTrue(rules)
        for line in rules:
            self.assertTrue(line.startswith("#"), line)
            self.assertTrue(line.endswith("# inferred"), line)

    def test_a_failed_install_names_the_stage(self) -> None:
        self.established()
        setup_tests.FAKE["fail"] = "specify init"
        code, report = self.init()
        self.assertEqual(code, 1, report)
        self.assertIn("stopped at install: install: spec-kit init failed", report)
        self.assertFalse(os.path.lexists(self.root / ".ballast/spec_workflow"))
        self.assertIn("Written: .gitignore, ballast.toml", report)
        setup_tests.FAKE.clear()
        with patch.object(init.setup.Setup, "main", side_effect=OSError("disk full")):
            code, report = self.init()
        self.assertEqual(code, 1, report)
        self.assertIn("stopped at install: install: disk full", report)


class NoExecutionTests(InitCase):
    """AC-015 to AC-017: nothing detected runs; git config runs nothing; no link."""

    def test_only_git_starts_and_no_detected_command_runs(self) -> None:
        global STARTED  # noqa: PLW0603 - the audit hook's switch
        self.established(
            **{
                "package.json": json.dumps(
                    {"scripts": {"test": f"touch {self.marker}"}}
                ),
            }
        )
        STARTED = []
        try:
            code, report = self.init()
        finally:
            started, STARTED = STARTED, None
        self.assertEqual(code, 0, report)
        self.assertEqual(set(started), {"git"})
        self.assertFalse(self.marker.exists())

    def test_git_config_runs_nothing(self) -> None:
        self.established()
        program = self.base / "program"
        program.write_text(f"#!/bin/sh\ntouch {self.marker}\n")
        program.chmod(0o755)
        hooks = self.base / "hooks"
        hooks.mkdir()
        for hook in ("post-checkout", "pre-commit", "post-index-change"):
            (hooks / hook).symlink_to(program)
        for key, value in (
            ("core.hooksPath", str(hooks)),
            ("core.pager", str(program)),
            ("core.fsmonitor", str(program)),
            ("pager.check-ignore", str(program)),
        ):
            git(self.root, "config", key, value)
        code, report = self.init()
        self.assertEqual(code, 0, report)
        self.assertFalse(self.marker.exists())

    def test_a_linked_github_is_never_read(self) -> None:
        outside = self.base / "outside"
        write(outside, {"workflows/ci.yml": CI.format(marker=self.marker)})
        self.established(**{".github/workflows/ci.yml": ""})
        (self.root / ".github").symlink_to(outside)
        outside.chmod(0)
        self.addCleanup(outside.chmod, 0o755)
        code, report = self.init()
        self.assertEqual(code, 0, report)
        self.assertIn("Skipped evidence: .github (symbolic link)", report)
        self.assertNotIn("evidence: .github", (self.root / "ballast.toml").read_text())

    def test_a_linked_policies_parent_refuses(self) -> None:
        outside = self.base / "outside"
        outside.mkdir()
        self.established()
        (self.root / "docs/policies").rename(outside / "policies")
        (self.root / "docs/policies").symlink_to(outside / "policies")
        before = setup_tests.tree(self.root, (".git",)), setup_tests.tree(outside)
        code, report = self.init()
        self.assertEqual(code, 2, report)
        self.assertIn("stopped at check: docs/policies is a symbolic link", report)
        after = setup_tests.tree(self.root, (".git",)), setup_tests.tree(outside)
        self.assertEqual(after, before)


# --- US4: evidence ------------------------------------------------------------


class EvidenceTests(InitCase):
    """AC-021, AC-022, AC-024, AC-025, SC-006."""

    def entries(self) -> list[str]:
        text = (self.root / "ballast.toml").read_text()
        block = text.split("commands = [\n", 1)[1].split("\n]", 1)[0]
        return block.splitlines()

    def test_direct_checks_are_active_and_inferred_ones_commented(self) -> None:
        self.established(
            **{
                "package.json": '{\n  "name": "x",\n  "scripts": {\n'
                '    "build": "tsc",\n    "test": "vitest"\n  }\n}\n',
                "pnpm-lock.yaml": "lockfileVersion: 9\n",
            }
        )
        code, report = self.init()
        self.assertEqual(code, 0, report)
        entries = self.entries()
        ci = ".github/workflows/ci.yml"
        self.assertEqual(
            entries[:3],
            [
                f'  "pytest",  # evidence: {ci}:8',
                f'  "ruff check",  # evidence: {ci}:11',
                '  "pnpm run test",  # evidence: package.json:5',
            ],
        )
        self.assertIn(
            '  # "make check",  # inferred from Makefile:1; confirm, then uncomment',
            entries,
        )
        self.assertNotIn("secrets", "\n".join(entries))
        self.assertNotIn("&&", "\n".join(entries))
        for entry in entries:
            active = not entry.lstrip().startswith("#")
            self.assertTrue(
                ("# evidence: " in entry) if active else ("inferred" in entry), entry
            )
        commands = self.config()["checks"]["commands"]
        self.assertEqual(commands, ["pytest", "ruff check", "pnpm run test"])
        self.assertIn('check "make check" (Makefile:1)', report)

    def test_an_unknown_stack_is_neutral_and_inferred(self) -> None:
        git(self.root, "init", "-q")
        write(self.root, {"src/main.zig": "pub fn main() void {}\n"})
        code, report = self.init()
        self.assertEqual(code, 0, report)
        constitution = (self.root / ".specify/memory/constitution.md").read_text()
        self.assertIn("Stack: neutral (inferred: no recognised manifest)", constitution)
        self.assertIn("stack neutral (no recognised manifest)", report)
        self.assertNotIn("checks", self.config())

    def test_unusable_evidence_is_skipped_with_its_reason(self) -> None:
        self.established(
            **{
                "pyproject.toml": "[project\n",
                "package.json": "{" + " " * (256 * 1024) + "}",
                ".github/workflows/ci.yml": b"run: pytest \xff\n",
            }
        )
        code, report = self.init()
        self.assertEqual(code, 0, report)
        self.assertIn("pyproject.toml (parse error: ", report)
        self.assertIn("package.json (larger than 256 KiB)", report)
        self.assertIn(".github/workflows/ci.yml (not UTF-8)", report)

    def test_checkout_text_is_escaped_in_the_report(self) -> None:
        self.established(**{".github/workflows/x\x1b[2J.yml": "run: pytest\n"})
        code, report = self.init()
        self.assertEqual(code, 0, report)
        self.assertNotIn("\x1b", report)
        self.assertIn(".github/workflows/x\\x1b[2J.yml (unusual file name)", report)


class GeneratedContentTests(InitCase):
    """AC-023, AC-026, AC-027."""

    def test_values_cite_their_source_and_no_placeholder_remains(self) -> None:
        self.established(**{"AGENTS.md": ""})
        code, report = self.init()
        self.assertEqual(code, 0, report)
        agents = (self.root / "AGENTS.md").read_text()
        constitution = (self.root / ".specify/memory/constitution.md").read_text()
        self.assertIn("Demo service (source: pyproject.toml)", agents)
        self.assertIn("Source: pyproject.toml", constitution)
        self.assertIn("`pytest` (evidence: .github/workflows/ci.yml:8)", agents)
        self.assertNotIn("starting point", agents)
        for text in (agents, constitution):
            self.assertIsNone(init.PLACEHOLDER.search(text))
            self.assertIsNone(init.MUSTACHE.search(text))
        self.assertEqual(readiness(report)["instructions"][0], "ready")

    def test_an_unknown_description_is_to_confirm(self) -> None:
        self.established(**{"pyproject.toml": "", "AGENTS.md": ""})
        code, report = self.init()
        self.assertEqual(code, 0, report)
        agents = (self.root / "AGENTS.md").read_text()
        self.assertIn("TO CONFIRM: what this project does", agents)
        self.assertIn("To confirm (inferred): description", report)

    def test_the_table_covers_every_template_placeholder(self) -> None:
        template = (ROOT / "templates/AGENTS.md").read_text()
        tool = init.Init(self.root, REF, None, None)
        found = set(init.PLACEHOLDER.findall(template))
        self.assertTrue(found)
        self.assertEqual(found - set(tool.agents_values()), set())

    def test_github_origin(self) -> None:
        for url, repository in (
            ("https://github.com/acme/demo.git", "acme/demo"),
            ("https://github.com/acme/demo", "acme/demo"),
            ("git@github.com:acme/demo.git", "acme/demo"),
            ("ssh://git@github.com/acme/demo.git", "acme/demo"),
            ("https://gitlab.com/acme/demo.git", None),
            (None, None),
        ):
            with self.subTest(url=url):
                self.root = self.base / f"origin-{len(list(self.base.iterdir()))}"
                self.root.mkdir()
                git(self.root, "init", "-q")
                write(self.root, {"README.md": "demo\n"})
                if url:
                    git(self.root, "remote", "add", "origin", url)
                code, report = self.init()
                self.assertEqual(code, 0, report)
                if repository:
                    self.assertEqual(self.config()["github"]["repository"], repository)
                    self.assertNotIn("GitHub repository: not set", report)
                else:
                    self.assertNotIn("github", self.config())
                    config = (self.root / "ballast.toml").read_text()
                    self.assertIn('# [github] repository = "OWNER/REPO"', config)
                    self.assertIn("GitHub repository: not set", report)

    def test_testing_addendum_only_with_direct_evidence(self) -> None:
        git(self.root, "init", "-q")
        write(self.root, {"Makefile": "test:\n\ttrue\n"})
        code, report = self.init()
        self.assertEqual(code, 0, report)
        self.assertFalse((self.root / "docs/policies/project/testing.md").exists())
        self.root = self.base / "with-ci"
        self.root.mkdir()
        self.established()
        code, report = self.init()
        self.assertEqual(code, 0, report)
        testing = (self.root / "docs/policies/project/testing.md").read_text()
        self.assertIn("- `pytest` (evidence: .github/workflows/ci.yml:8)", testing)
        self.root = self.base / "kept"
        self.root.mkdir()
        self.established(**{"docs/policies/project/testing.md": "ours\n"})
        code, report = self.init()
        self.assertEqual(code, 0, report)
        testing = self.root / "docs/policies/project/testing.md"
        self.assertEqual(testing.read_text(), "ours\n")


# --- US5: reruns --------------------------------------------------------------


class RerunTests(InitCase):
    """AC-028 to AC-031, SC-004, F-001."""

    def twice(self) -> tuple[str, str]:
        code, first = self.blank()
        self.assertEqual(code, 0, first)
        status, files = git(self.root, "status", "--porcelain"), self.project_files()
        code, second = self.init()
        self.assertEqual(code, 0, second)
        self.assertEqual(git(self.root, "status", "--porcelain"), status)
        self.assertEqual(self.project_files(), files)
        return first, second

    def test_a_rerun_changes_nothing_and_reports_the_same(self) -> None:
        for fixture in ("blank", "git-only", "established"):
            with self.subTest(fixture=fixture):
                self.root = self.base / fixture
                self.root.mkdir()
                if fixture == "git-only":
                    git(self.root, "init", "-q")
                if fixture == "established":
                    self.established()
                first, second = self.twice()
                self.assertEqual(section(second), section(first))
                self.assertIn("Written: none", second)

    def test_drift_is_a_patch(self) -> None:
        self.established()
        code, report = self.init()
        self.assertEqual(code, 0, report)
        config = (self.root / "ballast.toml").read_bytes()
        workflow = self.root / ".github/workflows/ci.yml"
        workflow.write_text(workflow.read_text() + "      - run: mypy .\n")
        code, report = self.init()
        self.assertEqual(code, 0, report)
        self.assertEqual((self.root / "ballast.toml").read_bytes(), config)
        self.assertIn(
            '+# ballast init found: "mypy ." (evidence: .github/workflows/ci.yml:14)',
            (self.root / PATCH).read_text(),
        )
        self.assertIn("ballast.toml: new evidence", report)

    def test_a_missing_github_table_is_proposed(self) -> None:
        git(self.root, "init", "-q")
        git(self.root, "remote", "add", "origin", "git@github.com:acme/demo.git")
        write(self.root, {"ballast.toml": setup_tests.PIN.format(REF)})
        code, report = self.init()
        self.assertEqual(code, 0, report)
        patch_text = (self.root / PATCH).read_text()
        self.assertIn("+[github]", patch_text)
        table = '+repository = "acme/demo"  # evidence: git remote origin'
        self.assertIn(table, patch_text)

    def test_an_oversized_pin_file_stops_without_writing(self) -> None:
        git(self.root, "init", "-q")
        pin = setup_tests.PIN.format(REF) + "#" * (256 * 1024) + "\n"
        write(self.root, {"ballast.toml": pin})
        before = setup_tests.tree(self.root, (".git",))
        code, report = self.init()
        self.assertEqual(code, 1, report)
        self.assertIn("stopped at plan: ballast.toml is unusable (larger", report)
        self.assertEqual(setup_tests.tree(self.root, (".git",)), before)

    def test_a_partial_adoption_is_completed(self) -> None:
        git(self.root, "init", "-q")
        write(self.root, {"ballast.toml": setup_tests.PIN.format(REF)})
        before = digest(self.root / "ballast.toml")
        code, report = self.init()
        self.assertEqual(code, 0, report)
        self.assertEqual(digest(self.root / "ballast.toml"), before)
        self.assertEqual((self.root / ".gitignore").read_text(), init.setup.GITIGNORE)
        self.assertTrue((self.root / ".specify/memory/constitution.md").is_file())
        self.assertIn("Written: .gitignore, .specify/memory/constitution.md", report)

    def test_ballast_own_repository(self) -> None:
        listed = git(ROOT, "ls-files", "-z").split("\0")
        for name in filter(None, listed):
            source, target = ROOT / name, self.root / name
            if not os.path.lexists(source):
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            if source.is_symlink():
                target.symlink_to(source.readlink())
            else:
                shutil.copy2(source, target)
        git(self.root, "init", "-q")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "copy")
        pin = tomllib.loads((self.root / "ballast.toml").read_text())["standard"]["ref"]
        code, report = self.init(ref=pin)
        self.assertNotEqual(code, 2, report)
        self.assertEqual(git(self.root, "status", "--porcelain", "-uno"), "", report)


# --- US6: the report ----------------------------------------------------------


class ReportTests(InitCase):
    """AC-032, AC-034."""

    def test_readiness_lines_and_next(self) -> None:
        self.established()
        code, report = self.init()
        self.assertEqual(code, 0, report)
        found = readiness(report)
        self.assertEqual(list(found), [*READINESS, "checks"])
        for status, _ in found.values():
            self.assertIn(status, {"ready", "warning", "not-ready"})
        self.assertEqual(found["ignored-paths"][0], "ready")
        current = ("ready", f"{REF} installed and current")
        self.assertEqual(found["pinned-version"], current)
        self.assertIn(NEXT_TRUST, report)

    def test_a_missing_program_is_a_warning(self) -> None:
        self.established()
        out = io.StringIO()

        def which(name: str) -> str | None:
            return None if name == "pytest" else f"/usr/bin/{name}"

        with (
            fakes(),
            patch.object(init.shutil, "which", which),
            redirect_stdout(out),
            redirect_stderr(io.StringIO()),
        ):
            code = init.cli(["--project", str(self.root), "--ref", REF])
        report = out.getvalue()
        self.assertEqual(code, 0, report)
        status, detail = readiness(report)["checks"]
        self.assertEqual(status, "warning")
        self.assertIn("pytest: not found", detail)
        self.assertIn('extra_allow does not cover "pytest"', detail)

    def test_a_matching_baseline_names_ballast_run(self) -> None:
        code, report = self.blank()
        self.assertEqual(code, 0, report)
        self.post_trust()
        code, report = self.init()
        self.assertEqual(code, 0, report)
        self.assertEqual(readiness(report)["trust-boundary"][0], "ready")
        self.assertIn("Next: run `ballast run`", report)

    def test_every_stop_names_stage_writes_and_next(self) -> None:
        cases = {
            "choose": lambda: self.init("--stack", "python"),
            "ignore": lambda: (
                self.established(**{"docs/.gitignore": "!policies/*.md\n"}),
                self.init(),
            )[1],
            "install": lambda: (
                self.established(),
                setup_tests.FAKE.update(fail="specify init"),
                self.init(),
            )[2],
        }
        for stage, run in cases.items():
            with self.subTest(stage=stage):
                self.root = self.base / stage
                self.root.mkdir()
                code, report = run()
                self.assertNotEqual(code, 0, report)
                lines = report.splitlines()
                stop = next(i for i, line in enumerate(lines) if "stopped at" in line)
                header = f"ballast init: stopped at {stage}: "
                self.assertTrue(lines[stop].startswith(header))
                self.assertTrue(lines[stop + 1].startswith("Written: "))
                self.assertTrue(lines[stop + 2].startswith("Not written: "))
                self.assertTrue(lines[-1].startswith("Next: "))
                self.assertTrue(lines[-1].endswith(", then rerun `ballast init`"))
                setup_tests.FAKE.clear()


# --- invariants -----------------------------------------------------------------


class InvariantTests(unittest.TestCase):
    """FR-022, FR-023, F-005."""

    def test_standard_library_only(self) -> None:
        tree = ast.parse((ROOT / "tools/init").read_text())
        modules = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules |= {alias.name.split(".")[0] for alias in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules.add(node.module.split(".")[0])
        self.assertEqual(modules - set(sys.stdlib_module_names) - {"__future__"}, set())

    def test_templates_are_generic(self) -> None:
        allowed = {
            "{{description}}",
            "{{description_source}}",
            "{{stack}}",
            "{{stack_source}}",
            "{{gates}}",
            "{{date}}",
        }
        for template in sorted((ROOT / "templates/init").glob("*.md")):
            text = template.read_text()
            with self.subTest(template=template.name):
                for name in ("Hugo-Grellier", "Grellier", "agentic-repo-standard"):
                    self.assertNotIn(name, text)
                self.assertEqual(set(init.MUSTACHE.findall(text)) - allowed, set())

    def test_loading_leaves_no_bytecode(self) -> None:
        with TemporaryDirectory() as directory:
            copy = Path(directory)
            for part in ("tools", "templates"):
                shutil.copytree(
                    ROOT / part,
                    copy / part,
                    ignore=shutil.ignore_patterns("__pycache__"),
                )
            result = subprocess.run(  # noqa: S603
                [sys.executable, "-I", "-S", str(copy / "tools/init"), "--help"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(list(copy.rglob("__pycache__")), [])


if __name__ == "__main__":
    unittest.main()
