"""Offline checks for tools/setup; the Spec Kit install itself needs network."""

from __future__ import annotations

import ast
import errno
import hashlib
import io
import json
import os
import posixpath
import pty
import re
import shutil
import signal
import socket
import subprocess
import sys
import time
import unittest
from contextlib import ExitStack, redirect_stderr, redirect_stdout, suppress
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import ClassVar
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
_loader = SourceFileLoader("setup_tool", str(ROOT / "tools/setup"))
setup = module_from_spec(spec_from_loader("setup_tool", _loader))
_loader.exec_module(setup)

sys.path.insert(0, str(ROOT / "tests"))
from test_autonomy import operator_state  # noqa: E402

sys.path.pop(0)


class GitignoreTests(unittest.TestCase):
    """The documented block ignores installed paths and keeps project files."""

    def check(self, gitignore: str | None) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)  # noqa: S607
            if gitignore is not None:
                (root / ".gitignore").write_text(gitignore)
            setup.Setup(root).check_ignored()

    def test_block_passes(self) -> None:
        self.check(setup.GITIGNORE)

    def test_missing_block_fails(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "Add this block"):
            self.check(None)

    def test_ignoring_the_constitution_fails(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "constitution.md"):
            self.check(".ballast/\n.agents/\n.claude/\n.specify/\n")


class PermissionTests(unittest.TestCase):
    """Project rules extend the base list without duplicates."""

    def test_merge_appends_and_dedupes(self) -> None:
        base = {"permissions": {"allow": ["A"], "deny": ["D"]}}
        config = {"agents": {"permissions": {"extra_allow": ["A", "B"]}}}
        merged = setup.merge_permissions(base, config)["permissions"]
        self.assertEqual(merged, {"allow": ["A", "B"], "deny": ["D"]})

    def test_rejects_a_string(self) -> None:
        config = {"agents": {"permissions": {"extra_deny": "Edit(./x)"}}}
        with self.assertRaises(ValueError):
            setup.merge_permissions({"permissions": {"allow": [], "deny": []}}, config)


class LinkTests(unittest.TestCase):
    """Relative links in installed documents resolve in a project."""

    # Installed path prefix -> source in this repository.
    LAYOUT: ClassVar[dict[str, str]] = {
        "docs/policies/": "templates/policies/",
        ".agents/skills/": "templates/skills/",
        ".ballast/spec_workflow/": "tools/spec_workflow/",
    }
    # Owned by the project, so absent here.
    PROJECT_OWNED = ("docs/policies/project/", ".specify/memory/constitution.md")

    def source(self, installed: str) -> Path | None:
        for prefix, origin in self.LAYOUT.items():
            if installed.startswith(prefix):
                return ROOT / origin / installed.removeprefix(prefix)
        return None

    def test_links_resolve(self) -> None:
        documents = [
            *(ROOT / "templates/policies").glob("*.md"),
            *(ROOT / "templates/skills").glob("*/SKILL.md"),
            ROOT / "templates/AGENTS.md",
        ]
        for document in documents:
            relative = document.relative_to(ROOT).as_posix()
            relative = relative.replace("templates/AGENTS.md", "AGENTS.md")
            for prefix, origin in self.LAYOUT.items():
                relative = relative.replace(origin, prefix, 1)
            for target in re.findall(
                r"\]\(([^)#:]+)(?:#[^)]*)?\)", document.read_text()
            ):
                installed = posixpath.normpath(
                    posixpath.join(posixpath.dirname(relative), target)
                )
                if installed.startswith(self.PROJECT_OWNED):
                    continue
                source = self.source(installed)
                with self.subTest(document=relative, link=target):
                    self.assertIsNotNone(source, installed)
                    self.assertTrue(source.exists(), installed)


def snapshot(root: Path) -> dict[str, str]:
    """Every path under root with its content digest."""
    return {
        str(path.relative_to(root)): "dir"
        if path.is_dir()
        else hashlib.sha256(path.read_bytes()).hexdigest()
        for path in root.rglob("*")
    }


class CheckTests(unittest.TestCase):
    """`--check` reports the installation's freshness and writes nothing."""

    def setUp(self) -> None:
        self.directory = TemporaryDirectory()
        self.root = Path(self.directory.name)
        (self.root / "ballast.toml").write_text('[standard]\nref = "v1"\n')

    def tearDown(self) -> None:
        self.directory.cleanup()

    def check(self) -> tuple[bool, str]:
        before = snapshot(self.root)
        output = io.StringIO()
        offline = patch.object(
            setup.urllib.request, "urlretrieve", side_effect=AssertionError("network")
        )
        with offline, redirect_stdout(output):
            current = setup.Setup(self.root).check()
        self.assertEqual(snapshot(self.root), before)
        return current, output.getvalue().strip()

    def run_check(self) -> subprocess.CompletedProcess[str]:
        return subprocess.run(  # noqa: S603
            [
                *(sys.executable, "-I", "-S", str(ROOT / "tools/setup")),
                *("--project", str(self.root), "--check"),
            ],
            capture_output=True,
            text=True,
            check=False,
        )

    def install(self) -> None:
        for path in setup.PROMISED:
            (self.root / path).parent.mkdir(parents=True, exist_ok=True)
            (self.root / path).write_text("installed\n")
        stamp = self.root / ".ballast/.setup-version"
        stamp.write_text(setup.Setup(self.root).fingerprint() + "\n")

    def test_reports_each_state(self) -> None:
        self.assertEqual(self.check(), (False, "absent"))
        result = self.run_check()
        self.assertEqual((result.returncode, result.stdout), (1, "absent\n"))
        self.install()
        self.assertEqual(self.check(), (True, "current"))
        result = self.run_check()
        self.assertEqual((result.returncode, result.stdout), (0, "current\n"))
        (self.root / ".ballast/spec_workflow/run.py").unlink()
        self.assertEqual(
            self.check(), (False, "incomplete: .ballast/spec_workflow/run.py")
        )
        self.install()
        (self.root / "ballast.toml").write_text('[standard]\nref = "v2"\n')
        self.assertEqual(self.check(), (False, "stale"))
        self.assertEqual(self.run_check().returncode, 1)

    def test_missing_tool_points_to_doctor(self) -> None:
        with (
            patch.object(setup.shutil, "which", return_value=None),
            self.assertRaisesRegex(RuntimeError, "missing: uvx; run `ballast doctor`"),
        ):
            setup.Setup(self.root).install_spec_kit(self.root)


class AutonomousInstallTests(unittest.TestCase):
    """T032, T041: setup installs the Autonomous workflows and extension."""

    def setUp(self) -> None:
        self.directory = TemporaryDirectory()
        self.root = Path(self.directory.name)
        (self.root / ".specify/templates").mkdir(parents=True)
        self.calls: list[tuple[str, ...]] = []

    def tearDown(self) -> None:
        self.directory.cleanup()

    def setup(self, config: str = "") -> setup.Setup:
        (self.root / "ballast.toml").write_text(config)
        tool = setup.Setup(self.root)
        tool.specify = lambda *args: self.calls.append(args)  # type: ignore[method-assign]
        tool.run = lambda *args, **_: self.calls.append(args)  # type: ignore[method-assign]
        return tool

    def test_installs_every_workflow(self) -> None:
        self.setup().install_standard()
        added = [call[-1] for call in self.calls if call[:2] == ("workflow", "add")]
        self.assertEqual(
            added,
            [
                str(ROOT / "templates/spec-kit/workflows" / name)
                for name in ("feature", "autonomous", "continue")
            ],
        )
        for name in ("autonomous", "continue"):
            self.assertTrue(
                (
                    ROOT / "templates/spec-kit/workflows" / name / "workflow.yml"
                ).is_file()
            )

    def test_installs_the_ballast_extension_before_claude_skills(self) -> None:
        tool = self.setup()
        sources = {name: self.root / name for name in setup.SOURCES}
        for source in sources.values():
            (source / "bundles").mkdir(parents=True)
        with (
            patch.object(setup, "_fetch_source", side_effect=lambda n, _: sources[n]),
            patch.object(setup.shutil, "which", return_value="/usr/bin/x"),
            patch.object(tool, "complete_claude_extension_skills") as skills,
        ):
            skills.side_effect = lambda: self.calls.append(("claude-skills",))
            tool.install_spec_kit(self.root)
        extension = (
            "extension",
            "add",
            str(ROOT / "templates/spec-kit/extensions/ballast"),
            "--dev",
        )
        self.assertIn(extension, self.calls)
        self.assertLess(
            self.calls.index(extension), self.calls.index(("claude-skills",))
        )

    def test_autonomous_tables_leave_permissions_unchanged(self) -> None:
        config = (
            '[autonomous]\nrisk = ["R0"]\n[checks]\ncommands = ["true"]\n'
            '[agents.permissions]\nextra_allow = ["Bash(make:*)"]\n'
        )
        tool = self.setup(config)
        base = {"permissions": {"allow": ["A"], "deny": ["D"]}}
        merged = setup.merge_permissions(base, tool.config)["permissions"]
        self.assertEqual(merged, {"allow": ["A", "Bash(make:*)"], "deny": ["D"]})

    def test_new_installed_paths_are_ignored(self) -> None:
        probes = dict(setup.IGNORE_PROBES)
        for path in (
            ".specify/workflows/ballast-autonomous/workflow.yml",
            ".specify/workflows/ballast-continue/workflow.yml",
            ".specify/extensions/ballast/extension.yml",
        ):
            self.assertTrue(probes[path], path)


# --- Recoverable setup (#14) -------------------------------------------------

PIN = '[standard]\nref = "{}"\n'
# What the fake Spec Kit writes into the project root it builds (the stage).
FAKE_SPEC_KIT = {
    ".specify/scripts/python/common.py": "common {ref}\n",
    ".specify/templates/plan-template.md": "plan\n",
    ".specify/integration.json": "{{}}\n",
    ".specify/init-options.json": "{{}}\n",
    ".specify/.gitignore": "*.tmp\n",
    ".specify/extensions.yml": "installed: []\n",
    ".specify/extensions/ballast/extension.yml": "id: ballast\n",
    ".specify/integrations/codex.json": "{{}}\n",
    ".specify/presets/explicit-task-dependencies/preset.yml": "id: x\n",
    ".specify/workflows/workflow-registry.json": "{{}}\n",
    ".specify/memory/constitution.md": "template constitution\n",
    ".specify/memory/.constitution-template.json": "{{}}\n",
    ".specify/.workflow-install.lock": "",
    ".agents/skills/speckit-tasks/SKILL.md": "tasks {ref}\n",
    ".claude/skills/speckit-tasks/SKILL.md": "tasks {ref}\n",
}
# Version B drops a skill A installed and adds one (plan review F-001).
FAKE_ONLY = {
    "vA": {".agents/skills/speckit-old/SKILL.md": "old\n"},
    "vB": {".agents/skills/speckit-new/SKILL.md": "new\n"},
}
# Switches the fakes read: a command substring to fail, a workflow to skip,
# an extra output, or the stage path written into a staged file.
FAKE: dict[str, str] = {}


def fake_fetch(name: str, temporary: Path) -> Path:
    """Stand in for a Spec Kit source download, never touching the network."""
    if os.environ.get("FAKE_NETWORK") == "deny" or FAKE.get("fail") == f"fetch {name}":
        message = f"cannot download {name}"
        raise OSError(message)
    source = temporary / name
    (source / "bundles").mkdir(parents=True, exist_ok=True)
    return source


def fake_run(self: setup.Setup, *args: str, cwd: Path | None = None) -> None:
    """Emulate Spec Kit and patch.

    `init` writes FAKE_SPEC_KIT and `workflow add` installs the workflow;
    nothing else has an effect.
    """
    del cwd
    command = " ".join(args)
    if os.environ.get("FAKE_NETWORK") == "deny":
        raise AssertionError("unexpected command: " + command)
    time.sleep(float(os.environ.get("FAKE_SLEEP", "0")))
    if FAKE.get("fail") and FAKE["fail"] in command:
        raise subprocess.CalledProcessError(1, args)
    spec = args[4:] if args[:1] == ("uvx",) else ()
    if spec[:1] == ("init",):
        outputs = {**FAKE_SPEC_KIT, **FAKE_ONLY.get(self.ref, {})}
        for name, text in outputs.items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text.format(ref=self.ref))
        if FAKE.get("embed"):
            (self.root / ".specify/init-options.json").write_text(str(self.root))
        if FAKE.get("extra"):
            (self.root / FAKE["extra"]).write_text("extra\n")
    elif spec[:2] == ("workflow", "add") and FAKE.get("skip") != Path(spec[-1]).name:
        target = self.root / ".specify/workflows" / f"ballast-{Path(spec[-1]).name}"
        target.mkdir(parents=True, exist_ok=True)
        shutil.copy(Path(spec[-1]) / "workflow.yml", target / "workflow.yml")


def fakes() -> ExitStack:
    """Patch every network and Spec Kit call with the fakes above."""
    stack = ExitStack()
    stack.enter_context(patch.object(setup, "_fetch_source", fake_fetch))
    stack.enter_context(patch.object(setup.Setup, "run", fake_run))
    stack.enter_context(patch.object(setup.shutil, "which", lambda n: f"/usr/bin/{n}"))
    return stack


# Runs tools/setup with the fakes in a child process, killing it with SIGKILL
# at a named point (research R12: no fault hook in production code).
WRAPPER = """\
import os, signal, sys, time
sys.path.insert(0, {tests!r})
import test_setup as t
s = t.setup
s._fetch_source = t.fake_fetch
s.Setup.run = t.fake_run
s.shutil.which = lambda name: "/usr/bin/" + name
def offline(*_args, **_kwargs):
    raise AssertionError("unexpected network request")
s.urllib.request.urlretrieve = offline
t.socket.socket.connect = offline
point, count, calls = sys.argv[2], int(sys.argv[3]), []
barrier = os.environ.get("BARRIER")
while barrier and not os.path.exists(barrier):
    time.sleep(0.005)
def die(*_):
    os.kill(os.getpid(), signal.SIGKILL)
if point == "staging":
    s.Setup.install_standard = die
elif point in ("switching", "committed"):
    write = s._write_journal
    def journal(state, data):
        write(state, data)
        if data["phase"] == point:
            die()
    s._write_journal = journal
elif point == "rename":
    rename = s._rename
    def renamed(source, target):
        rename(source, target)
        calls.append(source)
        if len(calls) == count:
            die()
    s._rename = renamed
elif point == "copytree":
    copytree = s.shutil.copytree
    def copied(*args, **kwargs):
        result = copytree(*args, **kwargs)
        calls.append(args[0])
        if len(calls) == count:
            die()
        return result
    s.shutil.copytree = copied
elif point == "validate":
    s.Setup.validate = die
elif point == "sleep":
    fill = s.Setup.fill_from_candidates
    def slow(self, stage, state):
        time.sleep(count)
        return fill(self, stage, state)
    s.Setup.fill_from_candidates = slow
sys.exit(s.cli(["--project", sys.argv[1], *sys.argv[4:]]))
""".format(tests=str(ROOT / "tests"))
HOLD_LOCK = """\
import fcntl, os, sys, time
fd = os.open(sys.argv[1], os.O_RDWR | os.O_CREAT, 0o600)
fcntl.flock(fd, fcntl.LOCK_EX if sys.argv[2] == "exclusive" else fcntl.LOCK_SH)
print("held", flush=True)
time.sleep(120)
"""
LAUNCHER = ROOT / "tools/spec_workflow/launcher.py"
SUCCESS = f"Spec Kit {setup.VERSION} and the standard are set up."


def git(root: Path, *args: str) -> str:
    """Run git in root with a fixed identity."""
    return subprocess.run(  # noqa: S603
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", *args],  # noqa: S607
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def tree(root: Path, skip: tuple[str, ...] = ()) -> dict[str, str]:
    """Every file and link under root, never following a link."""
    found = {}
    if not root.is_dir():
        return found
    for path in sorted(root.rglob("*")):
        name = path.relative_to(root).as_posix()
        if name in skip or name.split("/")[0] in skip:
            continue
        if path.is_symlink():
            found[name] = "link:" + str(path.readlink())
        elif path.is_file():
            found[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return found


class ProjectCase(unittest.TestCase):
    """A disposable Git project with a paused run, an archive and a constitution."""

    def setUp(self) -> None:
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.base = Path(directory.name)
        self.state_home = operator_state(self)
        environment = patch.dict(os.environ, {"XDG_STATE_HOME": str(self.state_home)})
        environment.start()
        self.addCleanup(environment.stop)
        self.root = self.new_project("project")

    def new_project(self, name: str, *, constitution: bool = True) -> Path:
        root = self.base / name
        root.mkdir()
        git(root, "init", "-q")
        (root / ".gitignore").write_text(setup.GITIGNORE)
        (root / "ballast.toml").write_text(PIN.format("vA"))
        files = {
            "docs/policies/project/security.md": "project rule\n",
            ".specify/workflows/runs/r1/state.json": '{"status": "paused"}\n',
            ".specify/workflow-state/r1/agents/log": "evidence\n",
            ".git/speckit-runs/r1/events.jsonl": "{}\n",
        }
        if constitution:
            files[".specify/memory/constitution.md"] = "project constitution\n"
        for name_, text in files.items():
            (root / name_).parent.mkdir(parents=True, exist_ok=True)
            (root / name_).write_text(text)
        return root

    def pin(self, ref: str, root: Path | None = None) -> None:
        ((root or self.root) / "ballast.toml").write_text(PIN.format(ref))

    def state(self, root: Path | None = None) -> Path:
        return setup.launcher.state_dir(root or self.root)

    def setup(self, root: Path | None = None) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with fakes(), redirect_stdout(out), redirect_stderr(err):
            code = setup.cli(["--project", str(root or self.root)])
        return code, out.getvalue(), err.getvalue()

    def installed(self, root: Path | None = None) -> None:
        code, out, err = self.setup(root)
        self.assertEqual(code, 0, err)
        self.assertIn(SUCCESS, out)

    def child(
        self,
        point: str = "none",
        count: int = 0,
        root: Path | None = None,
        args: tuple[str, ...] = (),
        **env: str,
    ) -> subprocess.Popen[str]:
        process = subprocess.Popen(  # noqa: S603
            [
                *(sys.executable, "-c", WRAPPER, str(root or self.root)),
                *(point, str(count), *args),
            ],
            env={**os.environ, **env},
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.addCleanup(process.wait)
        self.addCleanup(process.kill)
        return process

    def kill(
        self,
        point: str,
        count: int = 0,
        root: Path | None = None,
        args: tuple[str, ...] = (),
    ) -> None:
        process = self.child(point, count, root, args)
        process.communicate(timeout=60)
        self.assertEqual(process.returncode, -signal.SIGKILL)

    def launcher(
        self, *args: str, root: Path | None = None
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(  # noqa: S603
            [sys.executable, "-I", "-S", str(LAUNCHER), *args],
            cwd=root or self.root,
            capture_output=True,
            text=True,
            check=False,
        )

    def refusal(self, root: Path | None = None) -> str | None:
        result = self.launcher("status", "--json", root=root)
        return json.loads(result.stdout)["refusal"]

    def trust(self, root: Path | None = None) -> None:
        result = self.launcher("trust", root=root)
        self.assertEqual(result.returncode, 0, result.stderr)

    def check(self, root: Path | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run(  # noqa: S603
            [
                *(sys.executable, "-I", "-S", str(ROOT / "tools/setup")),
                *("--project", str(root or self.root), "--check"),
            ],
            capture_output=True,
            text=True,
            check=False,
        )

    def snapshot(self, root: Path | None = None) -> dict[str, dict[str, str]]:
        root = root or self.root
        return {
            "checkout": tree(root, (".git",)),
            "archives": tree(root / ".git/speckit-runs"),
            "state": tree(self.state(root), ("checkout.lock", "setup-holder.json")),
        }

    def record(self, root: Path | None = None) -> dict:
        return json.loads((self.state(root) / "installation.json").read_text())


class RecoverableSetupTests(ProjectCase):
    """A failed or killed setup leaves the previous installation (US1)."""

    def setUp(self) -> None:
        super().setUp()
        self.installed()
        self.trust()

    def test_first_installation_records_its_content(self) -> None:
        record = self.record()
        self.assertEqual(record["ref"], "vA")
        self.assertIn(".ballast/spec_workflow/run.py", record["files"])
        self.assertIn(".agents/skills/speckit-old/SKILL.md", record["files"])
        self.assertNotIn(".specify/.workflow-install.lock", record["files"])
        self.assertFalse((self.root / ".specify/.workflow-install.lock").exists())
        constitution = self.root / ".specify/memory/constitution.md"
        self.assertEqual(constitution.read_text(), "project constitution\n")
        self.assertTrue((self.root / ".specify/workflows/runs/r1/state.json").is_file())
        self.assertFalse((self.root / ".ballast/setup").exists())
        self.assertEqual(self.check().stdout, "current\n")
        self.assertIsNone(self.refusal())
        # A first installation creates the constitution only when absent.
        fresh = self.new_project("fresh", constitution=False)
        self.installed(fresh)
        created = fresh / ".specify/memory/constitution.md"
        self.assertEqual(created.read_text(), "template constitution\n")

    def test_failed_stages_keep_the_previous_installation(self) -> None:
        # AC-001, AC-002, AC-006
        self.pin("vB")
        before = self.snapshot()
        for fail, stage in (
            ("fetch core", "fetch core"),
            ("fetch intent", "fetch intent"),
            ("specify init", "spec-kit init"),
            ("integration install", "spec-kit integration install claude"),
            ("bundle install", "spec-kit bundle install"),
            ("extension add", "spec-kit extension add"),
            ("workflow add", "spec-kit workflow add"),
            ("preset add", "spec-kit preset add"),
            ("skills.patch", "patch skills.patch"),
            ("preset.patch", "patch preset.patch"),
        ):
            with self.subTest(stage=stage), patch.dict(FAKE, fail=fail):
                code, _, err = self.setup()
                self.assertEqual(code, 1, err)
                self.assertIn(f"setup: {stage} failed: ", err)
                self.assertIn("The previous installation was kept. Next: ", err)
                self.assertEqual(self.snapshot(), before)
                self.assertFalse((self.root / ".ballast/setup").exists())

    def test_switch_and_stage_failures_keep_the_previous_installation(self) -> None:
        # SC-001: a failing rename mid-switch, and a stage that cannot be prepared.
        self.pin("vB")
        before = self.snapshot()
        rename, calls = setup._rename, []  # noqa: SLF001 - fault injection

        def failing(source: Path, target: Path) -> None:
            calls.append(source)
            if len(calls) == 7:  # noqa: PLR2004 - mid-switch
                raise OSError(errno.EIO, "I/O error")
            rename(source, target)

        broken = OSError(errno.EACCES, "Permission denied")
        for stage, failure in (
            ("switch", patch.object(setup, "_rename", failing)),
            ("stage", patch.object(setup.shutil, "copyfile", side_effect=broken)),
        ):
            with self.subTest(stage=stage), failure:
                code, _, err = self.setup()
                self.assertEqual(code, 1, err)
                self.assertIn(f"setup: {stage} failed: ", err)
                self.assertIn("The previous installation was kept.", err)
                self.assertEqual(self.snapshot(), before)

    def test_invalid_stage_is_never_switched(self) -> None:
        # AC-003, F-002
        self.pin("vB")
        before = self.snapshot()
        enospc = OSError(errno.ENOSPC, "No space left on device")
        cases = (
            (
                {"skip": "continue"},
                None,
                (
                    "validate required outputs failed: "
                    ".specify/workflows/ballast-continue/workflow.yml is missing"
                ),
            ),
            ({"embed": "1"}, None, "validate stage paths failed: "),
            (
                {"extra": ".specify/unexpected.txt"},
                None,
                (
                    "validate stage paths failed: unexpected output "
                    ".specify/unexpected.txt"
                ),
            ),
            (
                {},
                patch.object(setup.shutil, "copy2", side_effect=enospc),
                "install standard failed: ",
            ),
        )
        for switches, failure, message in cases:
            with (
                self.subTest(message=message),
                patch.dict(FAKE, switches),
                ExitStack() as stack,
            ):
                if failure is not None:
                    stack.enter_context(failure)
                code, _, err = self.setup()
                self.assertEqual(code, 1, err)
                self.assertIn(message, err)
                self.assertIn("The previous installation was kept.", err)
                self.assertEqual(self.snapshot(), before)
        with (self.root / ".gitignore").open("a") as gitignore:
            gitignore.write("!docs/policies/workflow.md\n")
        before = self.snapshot()
        code, _, err = self.setup()
        self.assertEqual(code, 1, err)
        self.assertIn("validate ignore rules failed: docs/policies/workflow.md", err)
        self.assertEqual(self.snapshot(), before)

    def test_linked_work_area_is_refused(self) -> None:
        # F-007: setup never moves or deletes through a link.
        outside = self.base / "outside"
        outside.mkdir()
        (self.root / ".ballast/setup").symlink_to(outside)
        self.pin("vB")
        before = self.snapshot()
        code, _, err = self.setup()
        self.assertEqual(code, 2, err)
        self.assertIn("setup: refusing: .ballast/setup is a symbolic link", err)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(list(outside.iterdir()), [])

    def reference(self) -> dict[str, str]:
        """Return the checkout after an uninterrupted update from vA to vB."""
        root = self.new_project("reference")
        self.installed(root)
        self.pin("vB", root)
        self.installed(root)
        return self.snapshot(root)["checkout"]

    def test_killed_setup_is_recovered(self) -> None:
        # AC-004, AC-005, AC-006, AC-011, SC-001, F-001: five kill points.
        new = self.reference()
        for index, (point, count) in enumerate(
            (
                ("staging", 0),
                ("switching", 0),
                ("rename", 1),
                ("rename", 9),
                ("committed", 0),
            )
        ):
            with self.subTest(point=point, count=count):
                root = self.new_project(f"killed-{index}")
                self.installed(root)
                self.trust(root)
                self.pin("vB", root)
                before = self.snapshot(root)
                self.kill(point, count, root)
                self.assertTrue((self.state(root) / "setup-attempt.json").is_file())
                refused = self.launcher("run", "resume", "r1", root=root)
                self.assertEqual(refused.returncode, 2)
                self.assertIn("setup did not finish", refused.stderr)
                if point == "committed":
                    code, out, err = self.setup(root)
                    self.assertEqual(code, 0, err)
                    self.assertIn(
                        "recovered an interrupted setup: the new installation (vB) "
                        "is complete",
                        out,
                    )
                    self.assertIn("nothing changed", out)
                    self.assertEqual(self.snapshot(root)["checkout"], new)
                    continue
                with patch.dict(FAKE, fail="specify init"):
                    code, out, err = self.setup(root)
                self.assertEqual(code, 1, err)
                self.assertIn(
                    "recovered an interrupted setup: the previous installation (vA) "
                    "is in place",
                    out,
                )
                self.assertEqual(self.snapshot(root), before)

    def test_kill_during_rollback_is_recovered(self) -> None:
        self.pin("vB")
        before = self.snapshot()
        self.kill("rename", 9)
        self.kill("rename", 2)
        with patch.dict(FAKE, fail="specify init"):
            code, out, _ = self.setup()
        self.assertEqual(code, 1)
        self.assertIn("the previous installation (vA) is in place", out)
        self.assertEqual(self.snapshot(), before)

    def test_failure_at_an_unchanged_pin_keeps_trust(self) -> None:
        # AC-007, SC-002: an installation an older setup made is rebuilt.
        (self.state() / "installation.json").unlink()
        with patch.dict(FAKE, fail="specify init"):
            self.assertEqual(self.setup()[0], 1)
        self.assertIsNone(self.refusal())
        self.kill("rename", 3)
        with patch.dict(FAKE, fail="specify init"):
            self.assertEqual(self.setup()[0], 1)
        self.assertIsNone(self.refusal())

    def test_changed_pin_names_both_versions(self) -> None:
        # AC-008
        self.pin("vB")
        with patch.dict(FAKE, fail="specify init"):
            self.assertEqual(self.setup()[0], 1)
        detail = (
            'pinned vB, installed vA; restore ref = "vA" in ballast.toml, '
            "or fix the cause and rerun `ballast setup`"
        )
        result = self.check()
        self.assertEqual((result.returncode, result.stdout), (1, f"stale: {detail}\n"))
        self.assertTrue(self.refusal().startswith("pinned vB, installed vA: "))

    def test_stale_record_is_ignored(self) -> None:
        # F-003: B, then a setup older than this feature for A, then B again.
        self.pin("vB")
        self.installed()
        (self.root / ".ballast/.setup-version").write_text("pre-feature\n")
        (self.root / "docs/policies/legacy.md").write_text("old policy\n")
        self.pin("vA")
        self.assertEqual(self.check().stdout, "stale\n")
        self.assertNotIn("pinned", self.refusal())
        self.pin("vB")
        self.installed()
        self.assertFalse((self.root / "docs/policies/legacy.md").exists())
        self.assertEqual(self.record()["ref"], "vB")
        self.assertEqual(self.check().stdout, "current\n")

    def test_rollback_reuses_the_previous_installation(self) -> None:
        # AC-022, AC-023, SC-007: no download, project files and runs intact.
        self.pin("vB")
        self.installed()
        self.trust()
        trusted = (self.state() / "trusted.json").read_bytes()
        self.pin("vA")
        with patch.dict(os.environ, {"FAKE_NETWORK": "deny"}):
            code, out, err = self.setup()
        self.assertEqual(code, 0, err)
        self.assertIn("Reused the previous installation (vA)", out)
        after = self.snapshot()
        installed = {
            name: digest
            for name, digest in after["checkout"].items()
            if not name.startswith(".ballast/setup/")
        }
        self.assertEqual(installed, self.a_checkout)
        self.assertEqual(after["archives"], self.a_archives)
        self.assertEqual((self.state() / "trusted.json").read_bytes(), trusted)
        self.assertIn("workflow inputs changed", self.refusal())

    def test_damaged_kept_copy_is_not_reused(self) -> None:
        # SEC2-002, SEC2-003: an altered, added, linked or unreadable kept file.
        planted = self.base / "planted"
        planted.write_text("planted\n")
        digest = hashlib.sha256(b"planted\n").hexdigest()
        policy = "docs/policies/workflow.md"
        fresh = self.a_checkout

        def plant(kept: Path, name: str) -> None:
            (kept / name).write_text("planted\n")

        def link(kept: Path) -> None:
            (kept / policy).unlink()
            (kept / policy).symlink_to(planted)

        def fifo(kept: Path) -> None:
            plant(kept, ".specify/scripts/planted.py")
            (kept / policy).unlink()
            os.mkfifo(kept / policy)

        for case, damage in (
            ("altered", lambda k: plant(k, ".specify/scripts/python/common.py")),
            ("added", lambda k: plant(k, ".specify/scripts/planted.py")),
            ("linked", link),
            ("unreadable", fifo),
        ):
            with self.subTest(case=case):
                self.pin("vB")
                self.installed()
                self.pin("vA")
                damage(self.root / setup.KEPT)
                code, out, err = self.setup()
                self.assertEqual(code, 0, err)
                self.assertNotIn("Reused the previous installation", out)
                if case == "unreadable":
                    self.assertIn(
                        "full installation: the kept installation is unreadable: ", out
                    )
                checkout = self.snapshot()["checkout"]
                installed = {
                    n: d for n, d in checkout.items() if not n.startswith(setup.WORK)
                }
                self.assertEqual(installed, fresh)
                self.assertNotIn(digest, installed.values())
                self.assertNotIn(f"link:{planted}", installed.values())

    def test_tracked_files_are_never_removed_or_replaced(self) -> None:
        # SEC2-004, FR-005: a project file force-added under an installed path.
        custom = self.root / "docs/policies/custom.md"
        custom.write_text("project policy\n")
        git(self.root, "add", "-f", "docs/policies/custom.md")
        self.pin("vB")
        self.installed()
        self.assertEqual(custom.read_text(), "project policy\n")
        self.assertNotIn("docs/policies/custom.md", self.record()["entries"])
        self.assertFalse((self.root / setup.KEPT / "docs/policies/custom.md").exists())
        self.assertEqual(
            self.setup()[1], "nothing changed: vB is set up and verified\n"
        )
        git(self.root, "add", "-f", "docs/policies/workflow.md")
        before = self.snapshot()["checkout"]
        self.pin("vA")
        code, _, err = self.setup()
        self.assertEqual(code, 1)
        self.assertIn(
            "validate stage paths failed: docs/policies/workflow.md is tracked by git",
            err,
        )
        self.pin("vB")
        self.assertEqual(self.snapshot()["checkout"], before)

    def test_check_without_operator_state_is_unverified(self) -> None:
        # SEC2-007: doctor must not show current where the launcher refuses.
        inside = str(self.root / ".state")
        with patch.dict(os.environ, {"XDG_STATE_HOME": inside}):
            result = self.check()
        self.assertEqual(result.returncode, 1)
        self.assertTrue(result.stdout.startswith("unverified: state directory "))

    def test_invalid_pin_is_never_printed(self) -> None:
        # SEC2-009: in developer mode nothing validates the pin before setup.
        self.pin("v\\u001b]0;x\\u0007")
        for _ in range(2):
            code, out, err = self.setup()
            self.assertEqual(code, 0, err)
            self.assertNotIn("\x1b", out + err)
        self.assertIsNone(setup.launcher.pinned_ref(self.root))

    @property
    def a_checkout(self) -> dict[str, str]:
        root = self.new_project("fresh-a")
        self.installed(root)
        return self.snapshot(root)["checkout"]

    @property
    def a_archives(self) -> dict[str, str]:
        return tree(self.new_project("fresh-archives") / ".git/speckit-runs")


class SetupLockTests(ProjectCase):
    """One setup per checkout, never while a workflow command runs (US2)."""

    def setUp(self) -> None:
        super().setUp()
        self.installed()

    def hold(self, mode: str) -> subprocess.Popen[str]:
        holder = subprocess.Popen(  # noqa: S603
            [
                sys.executable,
                "-c",
                HOLD_LOCK,
                str(self.state() / "checkout.lock"),
                mode,
            ],
            stdout=subprocess.PIPE,
            text=True,
        )
        self.addCleanup(holder.stdout.close)
        self.addCleanup(holder.wait)
        self.addCleanup(holder.kill)
        self.assertEqual(holder.stdout.readline(), "held\n")
        return holder

    def test_second_setup_is_refused_and_a_dead_holder_is_recovered(self) -> None:
        # AC-009, AC-011
        self.pin("vB")
        running = self.child(FAKE_SLEEP="60")
        journal = self.state() / "setup-attempt.json"
        deadline = time.monotonic() + 30
        while not journal.exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        time.sleep(0.5)
        before = self.snapshot()
        code, _, err = self.setup()
        self.assertEqual(code, 2, err)
        self.assertIn(f"another ballast setup (PID {running.pid}, started ", err)
        self.assertIn("ref vB) holds this checkout", err)
        self.assertEqual(self.snapshot(), before)
        running.kill()
        running.communicate()
        code, out, err = self.setup()
        self.assertEqual(code, 0, err)
        self.assertIn("recovered an interrupted setup: the previous installation", out)
        self.assertEqual(self.record()["ref"], "vB")

    def test_running_workflow_command_is_named(self) -> None:
        # AC-015
        self.pin("vB")
        holder = self.hold("shared")
        before = self.snapshot()
        code, _, err = self.setup()
        self.assertEqual(code, 2, err)
        self.assertIn(
            "a `ballast run`, `ledger` or `intake` command is running in this checkout",
            err,
        )
        self.assertEqual(self.snapshot(), before)
        holder.kill()
        holder.wait()
        self.installed()

    def test_unfinished_agent_step_is_refused(self) -> None:
        # AC-015, PD-0004: setup never clears the marker.
        marker = self.state() / "in-progress"
        marker.write_text("ballast-agent-r1-step.scope\n")
        self.pin("vB")
        before = self.snapshot()
        code, _, err = self.setup()
        self.assertEqual(code, 2, err)
        self.assertIn("an agent step did not finish", err)
        self.assertIn("ballast discard-runs", err)
        self.assertEqual(self.snapshot(), before)
        self.assertTrue(marker.exists())

    def test_concurrent_setups_never_interleave(self) -> None:
        # AC-009, SC-004: 20 races in one checkout.
        for race in range(20):
            ref = "vB" if race % 2 == 0 else "vA"
            self.pin(ref)
            first, second = self.child(FAKE_SLEEP="0.05"), self.child(FAKE_SLEEP="0.05")
            results = [(p.wait(timeout=120), *p.communicate()) for p in (first, second)]
            installs = [r for r in results if r[0] == 0 and "are set up" in r[1]]
            self.assertEqual(len(installs), 1, results)
            for code, out, err in results:
                self.assertTrue(
                    (code == 0 and ("are set up" in out or "nothing changed" in out))
                    or (code == setup.EXIT_REFUSED and "holds this checkout" in err),
                    (code, out, err),
                )
            self.assertEqual(self.check().stdout, "current\n")
            self.assertEqual(self.record()["ref"], ref)


class NoOpTests(ProjectCase):
    """A rerun at a current pin changes nothing and downloads nothing (AC-012)."""

    def test_rerun_changes_nothing(self) -> None:
        # AC-012, SC-003
        self.installed()
        before = self.snapshot()
        started = time.monotonic()
        with patch.dict(os.environ, {"FAKE_NETWORK": "deny"}):
            code, out, err = self.setup()
        self.assertLess(time.monotonic() - started, 5)
        self.assertEqual(code, 0, err)
        self.assertEqual(out, "nothing changed: vA is set up and verified\n")
        self.assertEqual(self.snapshot(), before)

    def test_modified_installation_is_not_current(self) -> None:
        self.installed()
        (self.root / ".specify/scripts/python/common.py").write_text("edited\n")
        result = self.check()
        self.assertEqual(
            (result.returncode, result.stdout),
            (1, "modified: .specify/scripts/python/common.py\n"),
        )
        with patch.dict(os.environ, {"FAKE_NETWORK": "deny"}):
            code, _, err = self.setup()
        self.assertEqual(code, 1)
        self.assertIn("setup: fetch core failed: ", err)


class WorktreeCopyTests(ProjectCase):
    """A worktree copies only a verified primary installation (AC-014)."""

    def setUp(self) -> None:
        super().setUp()
        self.installed()
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "project")
        self.count = 0

    def worktree(self) -> Path:
        self.count += 1
        path = self.base / f"worktree-{self.count}"
        git(self.root, "worktree", "add", "-q", str(path))
        return path

    def test_verified_primary_is_copied(self) -> None:
        worktree = self.worktree()
        with patch.dict(os.environ, {"FAKE_NETWORK": "deny"}):
            code, out, err = self.setup(worktree)
        self.assertEqual(code, 0, err)
        self.assertIn("Copied the installation from the primary checkout", out)
        self.assertEqual(self.record(worktree)["files"], self.record()["files"])
        self.assertEqual(self.check(worktree).stdout, "current\n")

    def test_damaged_primary_is_not_copied(self) -> None:
        # SC-005: a missing, added or altered file in the primary installation.
        for path, damage in (
            (".specify/scripts/python/common.py", lambda p: p.write_text("edited\n")),
            (".specify/scripts/extra.py", lambda p: p.write_text("added\n")),
            ("docs/policies/workflow.md", Path.unlink),
        ):
            with self.subTest(path=path):
                target = self.root / path
                original = target.read_bytes() if target.exists() else None
                damage(target)
                worktree = self.worktree()
                code, out, err = self.setup(worktree)
                self.assertEqual(code, 0, err)
                self.assertIn(
                    "full installation: the primary installation differs from its "
                    f"record at {path}",
                    out,
                )
                self.assertEqual(self.check(worktree).stdout, "current\n")
                if original is None:
                    target.unlink()
                else:
                    target.write_bytes(original)

    def test_unusable_primary_falls_back(self) -> None:
        worktree = self.worktree()
        self.pin("vB", worktree)
        code, out, _ = self.setup(worktree)
        self.assertEqual(code, 0)
        self.assertIn(
            "full installation: the primary installation is for another version "
            "or configuration",
            out,
        )
        holder = subprocess.Popen(  # noqa: S603
            [
                sys.executable,
                "-c",
                HOLD_LOCK,
                str(self.state() / "checkout.lock"),
                "exclusive",
            ],
            stdout=subprocess.PIPE,
            text=True,
        )
        self.addCleanup(holder.stdout.close)
        self.addCleanup(holder.wait)
        self.addCleanup(holder.kill)
        self.assertEqual(holder.stdout.readline(), "held\n")
        code, out, _ = self.setup(self.worktree())
        self.assertEqual(code, 0)
        self.assertIn("full installation: the primary checkout is being set up", out)
        holder.kill()
        (self.state() / "installation.json").unlink()
        code, out, _ = self.setup(self.worktree())
        self.assertEqual(code, 0)
        self.assertIn(
            "full installation: the primary checkout has no installation record", out
        )

    def test_primary_record_is_read_under_its_lock(self) -> None:
        # #15 T023: the lock comes first, so a setup holding the primary is
        # named even when its record is momentarily absent.
        (self.state() / "installation.json").unlink()
        holder = subprocess.Popen(  # noqa: S603
            [
                *(sys.executable, "-c", HOLD_LOCK),
                *(str(self.state() / "checkout.lock"), "exclusive"),
            ],
            stdout=subprocess.PIPE,
            text=True,
        )
        self.addCleanup(holder.stdout.close)
        self.addCleanup(holder.wait)
        self.addCleanup(holder.kill)
        self.assertEqual(holder.stdout.readline(), "held\n")
        code, out, _ = self.setup(self.worktree())
        self.assertEqual(code, 0)
        self.assertIn("full installation: the primary checkout is being set up", out)

    def test_record_lists_executable_files(self) -> None:
        # #15 AC-010: the record carries the execute bits a copy must keep.
        record = self.record()
        listed = record["executable"]
        self.assertEqual(listed, sorted(listed))
        self.assertIn(".ballast/spec_workflow/run.py", listed)
        for name in listed:
            self.assertFalse(record["files"][name].startswith("link:"), name)
            self.assertNotIn("__pycache__", name)
            self.assertFalse(
                any(name.startswith(p + "/") for p in setup.LOCAL_STATE), name
            )
        self.assertNotIn(".specify/scripts/python/common.py", listed)

    def test_changed_file_mode_is_not_copied(self) -> None:
        # #15 AC-010: content digests do not cover modes; the record does.
        for path, mode in (
            ("docs/policies/workflow.md", 0o755),
            (".ballast/spec_workflow/run.py", 0o644),
        ):
            with self.subTest(path=path):
                target = self.root / path
                original = target.stat().st_mode
                target.chmod(mode)
                worktree = self.worktree()
                code, out, err = self.setup(worktree)
                self.assertEqual(code, 0, err)
                self.assertIn(
                    "full installation: the primary installation's file modes "
                    f"differ from its record at {path}",
                    out,
                )
                self.assertEqual(self.check(worktree).stdout, "current\n")
                target.chmod(original)

    def test_record_without_modes_is_still_copied(self) -> None:
        # A record an earlier version wrote has no `executable`; setup's own
        # primary copy keeps accepting it on content (#14 behavior).
        record = self.record()
        del record["executable"]
        (self.state() / "installation.json").write_text(json.dumps(record))
        worktree = self.worktree()
        with patch.dict(os.environ, {"FAKE_NETWORK": "deny"}):
            code, out, err = self.setup(worktree)
        self.assertEqual(code, 0, err)
        self.assertIn("Copied the installation from the primary checkout", out)


# --- Preparing a new worktree (#15) ------------------------------------------

# Every file a preparation opens while AUDIT is a list (AC-012).
AUDIT: list[str] | None = None


def _audit(event: str, args: tuple) -> None:
    if AUDIT is not None and event == "open" and args and args[0] is not None:
        AUDIT.append(os.fsdecode(args[0]) if not isinstance(args[0], int) else "")


sys.addaudithook(_audit)
PREPARED = (
    "Prepared the {ref} installation from {source} (verified, nothing downloaded).\n"
    "Review this worktree's protected inputs, then run `ballast trust`.\n"
)
NO_SOURCE = (
    "setup: refusing: no verified installation of {ref} with this ballast.toml on "
    "this machine ({checked} checked). Next: run `ballast setup` once here (it may "
    "download); later worktrees at this pin are then prepared from it\n"
)
PROJECT_OWNED = (
    "ballast.toml",
    ".specify/memory/constitution.md",
    "docs/policies/project",
)


class WorktreeCase(ProjectCase):
    """A committed project with a verified installation and linked worktrees."""

    def setUp(self) -> None:
        super().setUp()
        self.installed()
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "project")
        self.count = 0
        for target in (
            patch.object(setup, "_fetch_source", self.network),
            patch.object(setup.urllib.request, "urlretrieve", self.network),
            patch.object(socket.socket, "connect", self.network),
        ):
            target.start()
            self.addCleanup(target.stop)

    def network(self, *_args: object, **_kwargs: object) -> None:
        self.fail("a preparation made a network request")

    def worktree(self, ref: str | None = None, config: str = "") -> Path:
        self.count += 1
        path = self.base / f"worktree-{self.count}"
        git(self.root, "worktree", "add", "-q", "--detach", str(path))
        if ref or config:
            (path / "ballast.toml").write_text(PIN.format(ref or "vA") + config)
        return path

    def checkouts(self) -> list[Path]:
        listing = git(self.root, "worktree", "list", "--porcelain", "-z")
        return [
            Path(f.removeprefix("worktree "))
            for f in listing.split("\0")
            if f.startswith("worktree ")
        ]

    def owned(self, root: Path) -> dict[str, str]:
        """Return the worktree's project-owned files (AC-014)."""
        return {
            name: digest
            for name, digest in tree(root, (".git",)).items()
            if any(name == o or name.startswith(o + "/") for o in PROJECT_OWNED)
        }

    def prepare(
        self, root: Path, opened: list[str] | None = None
    ) -> tuple[int, str, str]:
        """Prepare root in-process; every other checkout and root's own files stay.

        With `opened`, every file the preparation opens is appended to it.
        """
        global AUDIT  # noqa: PLW0603
        others = {p: self.snapshot(p) for p in self.checkouts() if p != root}
        owned = self.owned(root)
        out, err = io.StringIO(), io.StringIO()
        AUDIT = opened
        try:
            with redirect_stdout(out), redirect_stderr(err):
                code = setup.cli(["--project", str(root), "--prepare"])
        finally:
            AUDIT = None
        self.assertEqual(self.owned(root), owned)
        for path, before in others.items():
            self.assertEqual(self.snapshot(path), before, path)
        return code, out.getvalue(), err.getvalue()

    def prepared(self, root: Path, source: Path, ref: str = "vA") -> str:
        code, out, err = self.prepare(root)
        self.assertEqual(code, 0, err)
        self.assertTrue(out.endswith(PREPARED.format(ref=ref, source=source)), out)
        return out

    def assert_uninstalled(self, root: Path) -> None:
        self.assertEqual(setup.entries(root), [])
        self.assertFalse((root / ".ballast").exists())
        self.assertFalse((self.state(root) / "setup-attempt.json").exists())
        self.assertFalse((self.state(root) / "installation.json").exists())


class PrepareTests(WorktreeCase):
    """The first command in a new worktree installs a verified local copy (#15)."""

    def test_new_worktree_is_prepared_offline(self) -> None:
        # AC-001, SC-005
        worktree = self.worktree()
        started = time.monotonic()
        code, out, err = self.prepare(worktree)
        self.assertLess(time.monotonic() - started, 10)
        self.assertEqual(
            (code, out, err), (0, PREPARED.format(ref="vA", source=self.root), "")
        )
        record, source = self.record(worktree), self.record()
        self.assertEqual(record["files"], source["files"])
        self.assertEqual(record["executable"], source["executable"])
        self.assertEqual(
            (record["ref"], record["fingerprint"]), ("vA", source["fingerprint"])
        )
        self.assertEqual(self.check(worktree).stdout, "current\n")
        self.assertFalse((worktree / ".ballast/setup").exists())
        self.assertFalse((worktree / ".specify/workflows/runs").exists())
        self.assertFalse((self.state(worktree) / "trusted.json").exists())
        self.assertTrue(
            self.refusal(worktree).startswith("no trusted baseline for this checkout")
        )
        # A preparation never creates the project's constitution.
        bare = self.worktree()
        (bare / ".specify/memory/constitution.md").unlink()
        self.prepared(bare, self.root)
        self.assertFalse((bare / ".specify/memory/constitution.md").exists())

    def test_sibling_and_kept_sources(self) -> None:
        # AC-003: the primary is at another pin; a sibling, then a kept copy.
        sibling = self.worktree("vB")
        self.installed(sibling)
        worktree = self.worktree("vB")
        out = self.prepared(worktree, sibling, "vB")
        self.assertIn(f"skipped {self.root}: it is for vA, not vB\n", out)
        self.assertEqual(self.record(worktree)["files"], self.record(sibling)["files"])
        self.pin("vB")
        self.installed()
        kept = self.root / ".ballast/setup/kept"
        self.assertTrue(kept.is_dir())
        worktree = self.worktree()
        out = self.prepared(worktree, kept)
        self.assertIn(f"skipped {self.root}: it is for vB, not vA\n", out)
        self.assertEqual(self.check(worktree).stdout, "current\n")

    def test_existing_installation_is_never_replaced(self) -> None:
        # AC-006: stale, modified, other-pin or partial installations stand.
        stale = self.worktree()
        self.installed(stale)
        self.pin("vB", stale)
        modified = self.worktree()
        self.installed(modified)
        (modified / ".specify/scripts/python/common.py").write_text("edited\n")
        partial = self.worktree()
        (partial / ".specify/scripts").mkdir(parents=True)
        (partial / ".specify/scripts/x.py").write_text("x\n")
        for root, status in (
            (stale, "stale: pinned vB, installed vA"),
            (modified, "modified: .specify/scripts/python/common.py"),
            (partial, "absent"),
        ):
            with self.subTest(status=status):
                before = self.snapshot(root)
                code, out, err = self.prepare(root)
                self.assertEqual((code, out), (2, ""), err)
                self.assertIn(
                    "setup: refusing: this checkout already holds an installation "
                    f"({status}",
                    err,
                )
                self.assertTrue(err.endswith("Next: run `ballast setup`\n"), err)
                self.assertEqual(self.snapshot(root), before)

    def test_tracked_policy_is_not_an_installation(self) -> None:
        # Plan review F-002: a project file under docs/policies/ is its own.
        (self.root / "docs/policies/team.md").write_text("team rule\n")
        git(self.root, "add", "-f", "docs/policies/team.md")
        git(self.root, "commit", "-q", "-m", "team policy")
        worktree = self.worktree()
        self.prepared(worktree, self.root)
        self.assertEqual(
            (worktree / "docs/policies/team.md").read_text(), "team rule\n"
        )
        self.assertEqual(self.check(worktree).stdout, "current\n")

    def test_other_pin_is_never_used(self) -> None:
        # AC-008
        worktree = self.worktree("vB")
        code, out, err = self.prepare(worktree)
        self.assertEqual(code, 2)
        self.assertEqual(out, f"skipped {self.root}: it is for vA, not vB\n")
        self.assertEqual(err, NO_SOURCE.format(ref="vB", checked=1))
        self.assert_uninstalled(worktree)

    def test_other_configuration_is_never_used(self) -> None:
        # AC-009: only [agents.permissions] differs.
        config = '[agents.permissions]\nextra_allow = ["Bash(make test)"]\n'
        worktree = self.worktree(config=config)
        code, out, err = self.prepare(worktree)
        self.assertEqual(code, 2)
        self.assertEqual(
            out, f"skipped {self.root}: it was built for another configuration\n"
        )
        self.assertEqual(err, NO_SOURCE.format(ref="vA", checked=1))
        self.assert_uninstalled(worktree)
        self.assertFalse(
            (worktree / ".ballast/spec_workflow/claude-settings.json").exists()
        )

    def test_mismatched_content_is_rejected(self) -> None:
        # AC-010, SC-003: added, missing, altered, mode-changed, or unrecorded modes.
        record_file = self.state() / "installation.json"
        record = record_file.read_text()

        def without_modes(_: Path) -> None:
            data = json.loads(record)
            del data["executable"]
            record_file.write_text(json.dumps(data))

        cases = (
            (
                ".specify/scripts/extra.py",
                lambda p: p.write_text("added\n"),
                "its content differs from its record at .specify/scripts/extra.py",
            ),
            (
                "docs/policies/workflow.md",
                Path.unlink,
                "its content differs from its record at docs/policies/workflow.md",
            ),
            (
                ".specify/scripts/python/common.py",
                lambda p: p.write_text("edited\n"),
                (
                    "its content differs from its record at "
                    ".specify/scripts/python/common.py"
                ),
            ),
            (
                "docs/policies/workflow.md",
                lambda p: p.chmod(0o755),
                "its file modes differ from its record at docs/policies/workflow.md",
            ),
            (
                ".ballast/spec_workflow/run.py",
                lambda p: p.chmod(0o644),
                (
                    "its file modes differ from its record at "
                    ".ballast/spec_workflow/run.py"
                ),
            ),
            (
                ".ballast/spec_workflow/run.py",
                without_modes,
                "its record predates file-mode checks",
            ),
        )
        for path, damage, reason in cases:
            with self.subTest(reason=reason):
                target = self.root / path
                original = target.read_bytes() if target.exists() else None
                mode = target.stat().st_mode if target.exists() else None
                damage(target)
                try:
                    worktree = self.worktree()
                    code, out, err = self.prepare(worktree)
                    self.assertEqual(code, 2, err)
                    self.assertEqual(out, f"skipped {self.root}: {reason}\n")
                    self.assertEqual(err, NO_SOURCE.format(ref="vA", checked=1))
                    self.assert_uninstalled(worktree)
                finally:
                    if original is None:
                        target.unlink()
                    else:
                        target.write_bytes(original)
                        target.chmod(mode)
                    record_file.write_text(record)

    def test_source_reached_through_a_link_is_rejected(self) -> None:
        # Security review: a parent link in a source could make the copy read
        # files outside it into this worktree, even if the copy then fails.
        moved = self.base / "elsewhere"
        (self.root / ".specify").rename(moved)
        (self.root / ".specify").symlink_to(moved)
        kept = self.root / ".ballast/setup/kept"
        kept.mkdir(parents=True)
        (kept / ".specify").symlink_to(moved)
        record = json.loads((self.state() / "installation.json").read_text())
        (self.state() / "kept-installation.json").write_text(json.dumps(record))
        worktree = self.worktree()
        code, out, _ = self.prepare(worktree)
        self.assertEqual(code, 2)
        self.assertEqual(
            out,
            f"skipped {self.root}: it reaches its installation through a symbolic "
            "link at .specify\n"
            f"skipped {kept}: it reaches its installation through a symbolic link "
            "at .ballast/setup/kept/.specify\n",
        )
        self.assert_uninstalled(worktree)

    def test_unfinished_or_busy_source_is_rejected(self) -> None:
        # AC-011, plan review F-004
        journal = self.state() / "setup-attempt.json"
        journal.write_text("{}\n")
        worktree = self.worktree()
        code, out, _ = self.prepare(worktree)
        self.assertEqual(code, 2)
        self.assertEqual(out, f"skipped {self.root}: its setup did not finish\n")
        self.assert_uninstalled(worktree)
        journal.unlink()
        holder = subprocess.Popen(  # noqa: S603
            [
                sys.executable,
                "-c",
                HOLD_LOCK,
                str(self.state() / "checkout.lock"),
                "exclusive",
            ],
            stdout=subprocess.PIPE,
            text=True,
        )
        self.addCleanup(holder.stdout.close)
        self.addCleanup(holder.wait)
        self.addCleanup(holder.kill)
        self.assertEqual(holder.stdout.readline(), "held\n")
        code, out, _ = self.prepare(worktree)
        self.assertEqual(code, 2)
        self.assertEqual(out, f"skipped {self.root}: it is being set up\n")
        self.assert_uninstalled(worktree)
        holder.kill()
        holder.wait()
        lock = self.state() / "checkout.lock"
        lock.unlink()
        code, out, _ = self.prepare(worktree)
        self.assertEqual(code, 2)
        self.assertEqual(out, f"skipped {self.root}: it has no checkout lock\n")
        self.assertFalse(lock.exists())
        self.assert_uninstalled(worktree)

    def test_no_baseline_is_inherited(self) -> None:
        # AC-012, SC-003: byte-identical inputs, a trusted primary.
        self.trust()
        worktree = self.worktree()
        opened: list[str] = []
        code, out, err = self.prepare(worktree, opened)
        self.assertEqual(
            (code, out), (0, PREPARED.format(ref="vA", source=self.root)), err
        )
        self.assertIn(str(self.state() / "installation.json"), opened)
        self.assertEqual([p for p in opened if p.endswith("trusted.json")], [])
        self.assertFalse((self.state(worktree) / "trusted.json").exists())
        self.assertTrue(
            self.refusal(worktree).startswith("no trusted baseline for this checkout")
        )
        # A baseline left at a reused path predates this worktree.
        reused = self.worktree()
        self.state(reused).mkdir(parents=True)
        (self.state(reused) / "trusted.json").write_text("{}\n")
        out = self.prepared(reused, self.root)
        self.assertTrue(
            out.startswith(
                "removed a trust baseline left by an earlier checkout at this path\n"
            ),
            out,
        )
        self.assertFalse((self.state(reused) / "trusted.json").exists())
        self.assertTrue(self.refusal(reused).startswith("no trusted baseline"))

    def test_missing_source_then_setup(self) -> None:
        # AC-017, AC-019
        worktree = self.worktree("vB")
        code, _, err = self.prepare(worktree)
        self.assertEqual((code, err), (2, NO_SOURCE.format(ref="vB", checked=1)))
        self.assert_uninstalled(worktree)
        self.installed(worktree)
        later = self.worktree("vB")
        self.prepared(later, worktree, "vB")
        self.assertEqual(self.record(later)["files"], self.record(worktree)["files"])

    def test_killed_preparation_is_recovered(self) -> None:
        # AC-018, AC-019, SC-004: five kill points, then a retry.
        reference = self.worktree()
        self.prepared(reference, self.root)
        expected = tree(reference, (".git",))
        for point, count in (
            ("copytree", 2),
            ("validate", 0),
            ("switching", 0),
            ("rename", 3),
            ("committed", 0),
        ):
            with self.subTest(point=point, count=count):
                worktree = self.worktree()
                self.kill(point, count, worktree, ("--prepare",))
                self.assertTrue((self.state(worktree) / "setup-attempt.json").is_file())
                code, out, err = self.prepare(worktree)
                self.assertEqual(code, 0, err)
                if point == "committed":
                    self.assertEqual(
                        out,
                        "recovered an interrupted preparation: the new installation "
                        "(vA) is complete\n",
                    )
                else:
                    self.assertEqual(
                        out,
                        "recovered an interrupted preparation: no installation was "
                        "in place before it; none is now\n"
                        + PREPARED.format(ref="vA", source=self.root),
                    )
                self.assertEqual(tree(worktree, (".git",)), expected)
                self.assertEqual(self.record(worktree)["files"], self.record()["files"])
                self.assertEqual(self.check(worktree).stdout, "current\n")

    def test_committed_preparation_at_a_changed_pin_is_rolled_back(self) -> None:
        # AC-018 edge case: the pin changed before the next command.
        sibling = self.worktree("vB")
        self.installed(sibling)
        worktree = self.worktree()
        self.kill("committed", 0, worktree, ("--prepare",))
        self.pin("vB", worktree)
        code, out, err = self.prepare(worktree)
        self.assertEqual(code, 0, err)
        self.assertTrue(
            out.startswith(
                "recovered an interrupted preparation: the installation it prepared "
                "(vA) no longer matches this checkout's pin and ballast.toml and was "
                "removed; none is in place now\n"
            ),
            out,
        )
        self.assertTrue(out.endswith(PREPARED.format(ref="vB", source=sibling)), out)
        self.assertEqual(self.record(worktree)["files"], self.record(sibling)["files"])
        self.assertEqual(self.check(worktree).stdout, "current\n")

    def test_setup_recovers_a_preparation(self) -> None:
        # AC-018: `ballast setup` finishes the same journal, then sets up.
        worktree = self.worktree()
        self.kill("switching", 0, worktree, ("--prepare",))
        refused = self.launcher("run", "start", root=worktree)
        self.assertEqual(refused.returncode, 2)
        code, out, err = self.setup(worktree)
        self.assertEqual(code, 0, err)
        self.assertIn(
            "recovered an interrupted preparation: no installation was in place "
            "before it; none is now\n",
            out,
        )
        self.assertIn(SUCCESS, out)
        self.assertEqual(self.check(worktree).stdout, "current\n")

    def test_unfinished_setup_is_not_recovered_by_preparation(self) -> None:
        # A setup journal belongs to `ballast setup` (research R6).
        worktree = self.worktree()
        self.state(worktree).mkdir(parents=True)
        journal = self.state(worktree) / "setup-attempt.json"
        journal.write_text('{"schema": 1, "phase": "staging"}\n')
        code, out, err = self.prepare(worktree)
        self.assertEqual((code, out), (2, ""))
        self.assertEqual(
            err,
            "setup: refusing: setup did not finish in this checkout. Next: run "
            "`ballast setup` to recover\n",
        )
        self.assertTrue(journal.exists())


class PrepareConcurrencyTests(WorktreeCase):
    """Worktrees prepared together stay complete and independent (US3)."""

    def setUp(self) -> None:
        super().setUp()
        self.sibling = self.worktree("vB")
        self.installed(self.sibling)

    def race(self, roots: list[Path]) -> list[tuple[int, str, str]]:
        """Start one preparation per root at the same moment."""
        barrier = self.base / f"barrier-{self.count}"
        children = [
            self.child(
                root=r, args=("--prepare",), BARRIER=str(barrier), FAKE_NETWORK="deny"
            )
            for r in roots
        ]
        barrier.touch()
        return [(c.wait(timeout=120), *c.communicate()) for c in children]

    def test_ten_worktrees_two_pins(self) -> None:
        # AC-015, SC-002: 20 repetitions of ten concurrent first commands.
        sources = {"vA": self.root, "vB": self.sibling}
        for repetition in range(20):
            pins = ["vA", "vB"] * 5
            roots = [self.worktree(ref) for ref in pins]
            results = self.race(roots)
            for root, ref, (code, out, err) in zip(roots, pins, results, strict=True):
                with self.subTest(repetition=repetition, root=root.name):
                    self.assertEqual(code, 0, err)
                    self.assertTrue(
                        out.endswith(PREPARED.format(ref=ref, source=sources[ref])), out
                    )
                    record, source = self.record(root), self.record(sources[ref])
                    self.assertEqual(
                        (record["ref"], record["fingerprint"], record["files"]),
                        (ref, source["fingerprint"], source["files"]),
                    )
                    live = setup.installed_digests(root, record["entries"])
                    self.assertEqual(live, record["files"])
                    refusal = setup.launcher._refusal(root)  # noqa: SLF001
                    self.assertTrue(
                        refusal.startswith("no trusted baseline for this checkout"),
                        refusal,
                    )

    def test_state_stays_per_worktree(self) -> None:
        # AC-016: a run in one worktree changes nobody else's state.
        roots = [self.worktree(ref) for ref in ["vA", "vB"] * 5]
        for code, _, err in self.race(roots):
            self.assertEqual(code, 0, err)
        for root in roots:
            self.assertFalse((root / ".specify/workflows/runs").exists(), root)
            self.assertFalse((root / ".specify/workflow-state").exists(), root)
            self.trust(root)
        self.trust()

        def everything(path: Path) -> dict[str, dict[str, str]]:
            return {"checkout": tree(path, (".git",)), "state": tree(self.state(path))}

        active, others = roots[0], [*roots[1:], self.root, self.sibling]
        before = {p: everything(p) for p in others}
        run = active / ".specify/workflows/runs/r9/state.json"
        run.parent.mkdir(parents=True)
        run.write_text('{"status": "paused"}\n')
        self.assertIsNone(self.refusal(active))
        discarded = self.launcher("discard-runs", root=active)
        self.assertEqual(discarded.returncode, 0, discarded.stderr)
        self.assertFalse(run.exists())
        self.assertEqual({p: everything(p) for p in others}, before)

    def test_one_preparation_per_worktree(self) -> None:
        # AC-020, plan review F-001
        worktree = self.worktree()
        first = self.child("sleep", 6, worktree, ("--prepare",), FAKE_NETWORK="deny")
        holder = self.state(worktree) / "setup-holder.json"
        deadline = time.monotonic() + 30
        while not (self.state(worktree) / "setup-attempt.json").exists():
            self.assertLess(time.monotonic(), deadline)
            time.sleep(0.02)
        self.assertEqual(json.loads(holder.read_text())["mode"], "prepare")
        code, out, err = self.prepare(worktree)
        self.assertEqual((code, out), (2, ""))
        self.assertRegex(
            err,
            rf"^setup: refusing: another ballast preparation \(PID {first.pid}, "
            r"started [^,]+, ref vA\) holds this checkout\. Next: wait for it to "
            r"finish, then rerun the command\n$",
        )
        _, err = first.communicate(timeout=60)
        self.assertEqual(first.returncode, 0, err)
        self.assertEqual(self.record(worktree)["files"], self.record()["files"])
        code, out, err = self.prepare(worktree)
        self.assertEqual(
            (code, out, err),
            (0, "nothing to prepare: this checkout is already installed for vA\n", ""),
        )
        # The first command already runs its launcher, holding the lock shared.
        running = subprocess.Popen(  # noqa: S603
            [
                *(sys.executable, "-c", HOLD_LOCK),
                *(str(self.state(worktree) / "checkout.lock"), "shared"),
            ],
            stdout=subprocess.PIPE,
            text=True,
        )
        self.addCleanup(running.stdout.close)
        self.addCleanup(running.wait)
        self.addCleanup(running.kill)
        self.assertEqual(running.stdout.readline(), "held\n")
        code, out, err = self.prepare(worktree)
        self.assertEqual(
            (code, out, err),
            (0, "nothing to prepare: this checkout is already installed for vA\n", ""),
        )
        running.kill()
        # Unsequenced: one prepares, the other refuses or finds nothing to do.
        for _ in range(10):
            root = self.worktree()
            results = self.race([root, root])
            prepared = [r for r in results if r[0] == 0 and "Prepared the" in r[1]]
            self.assertEqual(len(prepared), 1, results)
            for result in results:
                if result not in prepared:
                    self.assertTrue(
                        (result[0] == 0 and result[1].startswith("nothing to prepare"))
                        or (
                            result[0] == setup.EXIT_REFUSED
                            and "holds this checkout" in result[2]
                        ),
                        result,
                    )
            self.assertEqual(self.check(root).stdout, "current\n")


class ChatInstallTests(unittest.TestCase):
    """#20 T071, BL-INV-001: setup installs Chat mode with the standard."""

    setUp = AutonomousInstallTests.setUp
    tearDown = AutonomousInstallTests.tearDown
    setup = AutonomousInstallTests.setup

    def test_installs_chat_and_keeps_project_rules_for_chat_steps(self) -> None:
        config = '[agents.permissions]\nextra_deny = ["Edit(./secrets/**)"]\n'
        self.setup(config).install_standard()
        tools = self.root / ".ballast/spec_workflow"
        for name in ("chat.py", "claude-chat-settings.json", "agent.py", "run.py"):
            self.assertTrue((tools / name).is_file(), name)
        for policy in (ROOT / "templates/policies").glob("*.md"):
            installed = self.root / "docs/policies" / policy.name
            self.assertEqual(installed.read_text(), policy.read_text(), policy.name)
        sys.path.insert(0, str(ROOT / "tools/spec_workflow"))
        try:
            import agent  # noqa: PLC0415
        finally:
            sys.path.pop(0)
        with (
            patch.object(agent, "SETTINGS", tools / "claude-settings.json"),
            patch.object(agent, "CHAT_SETTINGS", tools / "claude-chat-settings.json"),
        ):
            merged = agent.chat_settings()["permissions"]
        self.assertIn("Edit(./secrets/**)", merged["deny"])
        self.assertIn("Edit(./**)", merged["allow"])


class CheckoutGitConfigTests(unittest.TestCase):
    """Checkout git config an agent can write never runs a program before trust."""

    def setUp(self) -> None:
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name) / "project"
        self.marker = Path(directory.name) / "ran"
        program = Path(directory.name) / "program"
        program.write_text(f"#!/bin/sh\ntouch {self.marker}\n")
        program.chmod(0o755)
        self.program = str(program)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)  # noqa: S603, S607
        (self.root / "ballast.toml").write_text("")
        subprocess.run(["git", "add", "ballast.toml"], cwd=self.root, check=True)  # noqa: S607

    def configure(self, key: str, value: str) -> None:
        subprocess.run(  # noqa: S603
            ["git", "config", key, value],  # noqa: S607
            cwd=self.root,
            check=True,
        )

    def test_fsmonitor_never_runs(self) -> None:
        self.configure("core.fsmonitor", self.program)
        self.assertEqual(setup.tracked(self.root, ["ballast.toml"]), {"ballast.toml"})
        builder = setup.Setup(self.root)
        builder.ignored(["ballast.toml"])
        builder.primary()
        with suppress(RuntimeError):
            builder.check_ignored()
        self.assertFalse(self.marker.exists(), "core.fsmonitor ran a program")

    def test_pager_never_runs_on_a_terminal(self) -> None:
        self.configure("pager.check-ignore", self.program)
        code = (
            "import sys; from contextlib import suppress\n"
            "from importlib.machinery import SourceFileLoader\n"
            "from importlib.util import module_from_spec, spec_from_loader\n"
            "from pathlib import Path\n"
            "loader = SourceFileLoader('setup_tool', sys.argv[1])\n"
            "tool = module_from_spec(spec_from_loader('setup_tool', loader))\n"
            "loader.exec_module(tool)\n"
            "with suppress(RuntimeError):\n"
            "    tool.Setup(Path(sys.argv[2])).check_ignored()\n"
        )
        env = {k: v for k, v in os.environ.items() if k not in {"GIT_PAGER", "PAGER"}}
        main, terminal = pty.openpty()
        try:
            subprocess.run(  # noqa: S603
                [sys.executable, "-c", code, str(ROOT / "tools/setup"), str(self.root)],
                stdin=terminal,
                stdout=terminal,
                stderr=subprocess.DEVNULL,
                env=env,
                check=False,
                timeout=60,
            )
        finally:
            os.close(terminal)
            os.close(main)
        self.assertFalse(self.marker.exists(), "pager.check-ignore ran a program")

    def test_every_git_call_is_hardened(self) -> None:
        source = (ROOT / "tools/setup").read_text()
        for flag in ("--no-pager", "core.fsmonitor=false", "core.hooksPath=/dev/null"):
            self.assertIn(flag, setup.GIT)
        bare = [
            node.lineno
            for node in ast.walk(ast.parse(source))
            if isinstance(node, ast.List)
            and node.elts
            and isinstance(node.elts[0], ast.Constant)
            and node.elts[0].value == "git"
        ]
        self.assertEqual(bare, [], "git calls must start with *GIT")


if __name__ == "__main__":
    unittest.main()
