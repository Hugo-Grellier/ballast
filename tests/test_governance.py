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
        # Autonomous resume waits for #21; #18 added the synchronization.
        self.assertIn("#21", spec_kit)


class ChatGovernanceTests(unittest.TestCase):
    """#20 FR-023: the shipped guidance describes Chat mode."""

    DOCUMENTS = (
        "templates/policies/spec-kit-workflow.md",
        "templates/policies/workflow.md",
        "templates/AGENTS.md",
        "templates/skills/ballast-feature-intake/SKILL.md",
    )

    def text(self, name: str) -> str:
        return (ROOT / name).read_text(encoding="utf-8")

    def test_each_document_describes_starting_and_inspecting_a_chat_run(self) -> None:
        for name in self.DOCUMENTS:
            with self.subTest(document=name):
                text = self.text(name)
                self.assertIn("ballast run start --mode chat", text)  # start
                self.assertIn("ballast run status", text)  # inspect
                self.assertIn("ballast run step", text)  # continue
                self.assertIn("never", text)

    def test_policies_and_agents_describe_resume_switch_approvals_and_the_boundary(
        self,
    ) -> None:
        for name in self.DOCUMENTS[:3]:
            with self.subTest(document=name):
                text = self.text(name)
                self.assertIn("ballast run mode", text)  # switch
                self.assertIn("ballast run approve", text)  # approvals are human
                self.assertRegex(
                    text,
                    r"`ballast run resume`\s+refuses\s+a\s+Chat\s+run|never `resume`",
                )
                self.assertRegex(text, r"outside\s+`ballast run`")
                self.assertRegex(text, r"none\s+of")
        skill = self.text(self.DOCUMENTS[3])
        self.assertIn("Never approve a gate on the operator's behalf", skill)
        self.assertIn("never `resume`", skill)

    def test_spec_kit_policy_has_the_chat_section(self) -> None:
        spec_kit = self.text("templates/policies/spec-kit-workflow.md")
        self.assertIn("## Chat runs", spec_kit)
        self.assertIn("**Chat runs.**", spec_kit)  # runner-contract rows
        self.assertIn("ballast run continue RUN --reason", spec_kit)
        self.assertIn("Conversation logs stay", spec_kit)
        workflow = self.text("templates/policies/workflow.md")
        self.assertIn("- **Chat** (`ballast run start --mode chat`)", workflow)
        self.assertIn("never raised to Autonomous", workflow)


if __name__ == "__main__":
    unittest.main()
