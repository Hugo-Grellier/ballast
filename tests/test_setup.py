"""Offline checks for tools/setup; the Spec Kit install itself needs network."""

from __future__ import annotations

import hashlib
import io
import posixpath
import re
import subprocess
import sys
import unittest
from contextlib import redirect_stdout
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


if __name__ == "__main__":
    unittest.main()
