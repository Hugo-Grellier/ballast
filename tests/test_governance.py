"""Governance text for Autonomous runs (FR-029, FR-030)."""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONSTITUTION = ROOT / ".specify/memory/constitution.md"
AMENDMENT = ROOT / "specs/27-autonomous-core/constitution-amendment.md"
VERSION = "**Version**: 1.1.0"


class GovernanceTests(unittest.TestCase):
    """The amended constitution and shipped policies describe Autonomous."""

    def test_constitution_has_bl_inv_006(self) -> None:
        # The operator applies the amendment (T071a); until then it is checked.
        text = CONSTITUTION.read_text(encoding="utf-8")
        if VERSION not in text:
            text = AMENDMENT.read_text(encoding="utf-8")
        self.assertIn(VERSION, text)
        self.assertIn("(BL-INV-006)", text)
        self.assertIn("only merging the PR that contains it accepts it", text)

    def test_policies_have_the_autonomous_section(self) -> None:
        workflow = (ROOT / "templates/policies/workflow.md").read_text()
        self.assertIn("## Supervision modes", workflow)
        self.assertIn("the merge decision is the single human approval", workflow)
        spec_kit = (ROOT / "templates/policies/spec-kit-workflow.md").read_text()
        self.assertIn("## Autonomous runs", spec_kit)
        self.assertIn("#18", spec_kit)


if __name__ == "__main__":
    unittest.main()
