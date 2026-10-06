"""Offline checks for tools/setup; the Spec Kit install itself needs network."""

from __future__ import annotations

import errno
import hashlib
import io
import json
import os
import posixpath
import re
import shutil
import signal
import subprocess
import sys
import time
import unittest
from contextlib import ExitStack, redirect_stderr, redirect_stdout
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
import os, signal, sys
sys.path.insert(0, {tests!r})
import test_setup as t
s = t.setup
s._fetch_source = t.fake_fetch
s.Setup.run = t.fake_run
s.shutil.which = lambda name: "/usr/bin/" + name
point, count, calls = sys.argv[2], int(sys.argv[3]), []
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
sys.exit(s.cli(["--project", sys.argv[1]]))
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
        self, point: str = "none", count: int = 0, root: Path | None = None, **env: str
    ) -> subprocess.Popen[str]:
        process = subprocess.Popen(  # noqa: S603
            [sys.executable, "-c", WRAPPER, str(root or self.root), point, str(count)],
            env={**os.environ, **env},
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.addCleanup(process.wait)
        self.addCleanup(process.kill)
        return process

    def kill(self, point: str, count: int = 0, root: Path | None = None) -> None:
        process = self.child(point, count, root)
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


if __name__ == "__main__":
    unittest.main()
