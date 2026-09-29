"""Offline checks for tools/setup; the Spec Kit install itself needs network."""

from __future__ import annotations

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


if __name__ == "__main__":
    unittest.main()
