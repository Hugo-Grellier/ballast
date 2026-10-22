"""PR title workflow: its shell check runs under bash, and the adopter copy matches."""

from __future__ import annotations

import os
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / ".github/workflows/pr-title.yml"
TEMPLATE = ROOT / "templates/github/workflows/pr-title.yml"

ACCEPTED = (
    "feat: x",
    "fix(scope): x",
    "refactor(a_b.c/d-e)!: x",
    "revert: x",
    "docs: x",
    "test: x",
    "build: x",
    "ci: x",
    "chore: x",
    "perf: x",
    "feat(1): two words here",
)
REFUSED = (
    "",
    "feature: x",
    "feat x",
    "feat:",
    "feat:   ",
    "feat(): x",
    "feat(-a): x",
    "feat (a): x",
    "feat : x",
    "fix(scope) : x",
    "feat! : x",
    "Feat: x",
    "feat:x",
    "x feat: y",
)


def script() -> str:
    """Return the `run: |` block of the workflow, de-indented as bash sees it."""
    lines = WORKFLOW.read_text().splitlines()
    start = next(i for i, line in enumerate(lines) if line.strip() == "run: |")
    indent = len(lines[start + 1]) - len(lines[start + 1].lstrip())
    block = [line[indent:] for line in lines[start + 1 :] if line.startswith(" ")]
    return "\n".join(block)


class PrTitleWorkflowTests(unittest.TestCase):
    """bash is the regex engine of the workflow, so the tests run its step."""

    def check(self, title: str) -> subprocess.CompletedProcess:
        return subprocess.run(  # noqa: S603 -- fixed argv, title only in the env
            ["bash", "-c", script()],  # noqa: S607 -- the runner's bash
            env={**os.environ, "PR_TITLE": title},
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )

    def test_accepts_conventional_titles(self) -> None:
        for title in ACCEPTED:
            with self.subTest(title=title):
                result = self.check(title)
                self.assertEqual(result.returncode, 0, result.stdout)

    def test_refuses_other_titles(self) -> None:
        for title in REFUSED:
            with self.subTest(title=title):
                result = self.check(title)
                self.assertEqual(result.returncode, 1)
                self.assertIn(f"Invalid PR title: {title}\n", result.stdout)
                self.assertIn("<type>(optional-scope)[!]: <description>", result.stdout)

    def test_adopter_copy_equals_repository_copy(self) -> None:
        self.assertEqual(WORKFLOW.read_bytes(), TEMPLATE.read_bytes())


if __name__ == "__main__":
    unittest.main()
