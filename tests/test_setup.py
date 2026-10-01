"""Offline checks for tools/setup; the Spec Kit install itself needs network."""

from __future__ import annotations

import posixpath
import re
import subprocess
import unittest
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path
from tempfile import TemporaryDirectory

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
            self.check(".agentic/\n.agents/\n.claude/\n.specify/\n")


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
    LAYOUT = {
        "docs/policies/": "templates/policies/",
        ".agents/skills/": "templates/skills/",
        ".agentic/spec_workflow/": "tools/spec_workflow/",
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
            for target in re.findall(r"\]\(([^)#:]+)(?:#[^)]*)?\)", document.read_text()):
                installed = posixpath.normpath(
                    posixpath.join(posixpath.dirname(relative), target)
                )
                if installed.startswith(self.PROJECT_OWNED):
                    continue
                source = self.source(installed)
                with self.subTest(document=relative, link=target):
                    self.assertIsNotNone(source, installed)
                    self.assertTrue(source.exists(), installed)


if __name__ == "__main__":
    unittest.main()
