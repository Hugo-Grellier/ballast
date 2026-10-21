"""The `ballast` command and what an adopting repository's AGENTS.md cites."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

from tools import cli

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "tools" / "cli.py"
LINK = re.compile(r"\]\(([^)\s]+)\)")
WORKFLOW_COPIES = ("issue-workflow.md", "pair-review.md", "model-routing.md")


def ballast(*args: str, **env: str) -> subprocess.CompletedProcess:
    """Run the entry point's module the way its console script calls `main`."""
    return subprocess.run(  # noqa: S603 -- fixed interpreter and script
        [sys.executable, str(CLI), *args],
        capture_output=True,
        text=True,
        env={**os.environ, **env},
        check=False,
        timeout=60,
    )


class CommandTests(unittest.TestCase):
    """`ballast COMMAND` runs the shipped helper isolated, nothing else."""

    def test_entry_point_names_the_dispatcher(self) -> None:
        project = tomllib.loads((ROOT / "pyproject.toml").read_text())
        self.assertEqual(project["project"]["scripts"], {"ballast": "tools.cli:main"})
        self.assertEqual(project["project"]["dependencies"], [])
        self.assertEqual(project["tool"]["uv"]["build-backend"]["module-name"], "tools")

    def test_documented_commands_map_to_shipped_helpers(self) -> None:
        for command in ("worker", "coordinate", "worktree", "dashboard"):
            self.assertIn(command, cli.COMMANDS)
        for script in cli.COMMANDS.values():
            self.assertTrue((ROOT / "tools" / script).is_file(), script)

    def test_unknown_or_missing_command_is_refused(self) -> None:
        for args in ((), ("qualify",), ("../worker",), ("--help",)):
            with self.subTest(args=args):
                result = ballast(*args)
                self.assertEqual(result.returncode, 2)
                self.assertIn("usage: ballast", result.stderr)
                self.assertEqual(result.stdout, "")

    def test_helper_runs_isolated_with_its_arguments(self) -> None:
        with tempfile.TemporaryDirectory() as planted:
            marker = Path(planted) / "imported"
            # The helper imports argparse; the dispatcher does not.
            (Path(planted) / "argparse.py").write_text(
                f"open({str(marker)!r}, 'w').close()\nraise SystemExit(9)\n"
            )
            result = ballast("worktree", "--help", PYTHONPATH=planted)
            self.assertFalse(marker.exists(), "helper ran without -I")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("usage: worktree.py", result.stdout)


class AdopterLinkTests(unittest.TestCase):
    """Every link in the template AGENTS.md resolves in the adopted layout."""

    def adopt(self, root: Path) -> None:
        """Copy as docs/migration.md describes: policies, workflow, skills."""
        shutil.copy(ROOT / "templates" / "AGENTS.md", root / "AGENTS.md")
        shutil.copytree(ROOT / "templates" / "policies", root / "docs" / "policies")
        for name in WORKFLOW_COPIES:
            shutil.copy(ROOT / "docs" / name, root / "docs" / "policies" / name)
        shutil.copytree(ROOT / "templates" / "skills", root / ".agents" / "skills")

    def test_template_links_resolve_inside_the_repository(self) -> None:
        text = (ROOT / "templates" / "AGENTS.md").read_text()
        self.assertNotIn("BALLAST_SOURCE", text)
        links = [link for link in LINK.findall(text) if "://" not in link]
        for name in WORKFLOW_COPIES:
            self.assertIn(f"docs/policies/{name}", links)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.adopt(root)
            for link in links:
                with self.subTest(link=link):
                    target = (root / link.split("#")[0]).resolve()
                    self.assertTrue(target.is_relative_to(root.resolve()), link)
                    self.assertTrue(target.exists(), link)

    def test_template_has_no_absolute_links(self) -> None:
        text = (ROOT / "templates" / "AGENTS.md").read_text()
        self.assertEqual([link for link in LINK.findall(text) if "://" in link], [])


if __name__ == "__main__":
    unittest.main()
