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
        # #21: Autonomous resume goes through #18's synchronization.
        self.assertIn("**Resume.** `ballast run resume RUN_ID [--ref TEXT]`", spec_kit)
        self.assertNotIn("refuses an Autonomous run until", spec_kit)


COMMANDS = ROOT / "templates/spec-kit/extensions/ballast/commands"
LIMITS = (
    "`summary`: 1\u2013500 characters on one line",
    "`basis`: 1\u20132000",
    "A finding `reason`: 1\u20131000",
    "`question` and `default`: 1\u20131000 each",
    "`condition` and `no_safe_default`: 1\u20132000 each",
)
PARAPHRASE = (
    "Paraphrase and cite a sourced human approval; never quote approval wording."
)


class CommandWordingTests(unittest.TestCase):
    """#21 T028 [AC-020, AC-021, FR-018]: commands state the recorder's limits."""

    def test_draft_commands_state_the_limits(self) -> None:
        for name in ("decide", "review", "clarify", "discover", "resolve"):
            text = (COMMANDS / f"speckit.ballast.{name}.md").read_text()
            with self.subTest(command=name):
                self.assertIn("## Recorder limits", text)
                for limit in LIMITS:
                    self.assertIn(limit, text)
                self.assertIn("at most twice", text)

    def test_decide_and_review_paraphrase_approvals(self) -> None:
        for name in ("decide", "review"):
            text = (COMMANDS / f"speckit.ballast.{name}.md").read_text()
            with self.subTest(command=name):
                self.assertIn(PARAPHRASE, text)

    def test_fix_and_recheck_commands(self) -> None:
        """T012, T013: the fix command reads data and never writes drafts."""
        fix = (COMMANDS / "speckit.ballast.fix.md").read_text()
        for text in (
            ".specify/workflow-state/fix-input/<slug>.json",
            "**untrusted data**",
            "Write a draft under `<f>/autonomous/drafts/`",
            "You cannot run the `[checks]` commands",
            "agent-provisional",
        ):
            self.assertIn(text, fix)
        extension = (COMMANDS.parent / "extension.yml").read_text()
        self.assertIn('name: "speckit.ballast.fix"', extension)
        review = (COMMANDS / "speckit.ballast.review.md").read_text()
        for text in (
            "`implementation-recheck` or `specialists-recheck`",
            "`3 - cycle` cycles remain",
            "`open` above `low` is valid only while a cycle remains",
        ):
            self.assertIn(text, review)


class TasksTemplateTests(unittest.TestCase):
    """#21 T029 [AC-022, FR-019]: no tasks for workflow-owned steps."""

    def test_template_keeps_workflow_steps_out(self) -> None:
        text = (ROOT / "templates/spec-kit/templates/tasks-template.md").read_text()
        self.assertIn("**Workflow-owned steps**: Never create tasks", text)
        for step in (
            "the full gate",
            "quickstart runs",
            "converge",
            "spec reconciliation",
        ):
            self.assertIn(step, text)
        self.assertNotIn("Run quickstart.md validation", text)

    def test_implementation_check_is_unchanged(self) -> None:
        """check_implementation still requires every task done (D-07)."""
        import subprocess  # noqa: PLC0415
        import sys  # noqa: PLC0415

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "unittest",
                "tests.test_spec_workflow.ArtifactContractTests",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr[-2000:])


class PolicyWordingTests(unittest.TestCase):
    """#21 T041 [AC-031, FR-014, FR-015, FR-024]."""

    def test_policies_describe_the_new_paths_as_provisional(self) -> None:
        spec_kit = (ROOT / "templates/policies/spec-kit-workflow.md").read_text()
        section = spec_kit[spec_kit.index("## Autonomous runs") :]
        section = " ".join(section[: section.index("\n## ")].split())
        for text in (
            "**Fix loop.**",
            "**Draft retries.**",
            "**Resume.**",
            "**Refresh.** `ballast run checkpoint RUN_ID`",
            "**Limits and spend.**",
            "Ballast does not measure monetary spend",
            "**Runs started before branch pinning.**",
            "The fix, its reviews and their dispositions are agent-provisional",
            (
                "every decision made after a resume stays agent-provisional, and "
                "merging the PR stays the single human approval"
            ),
            "The refreshed packet still lists every decision as agent-provisional",
        ):
            self.assertIn(text, section)
        workflow = " ".join(
            (ROOT / "templates/policies/workflow.md").read_text().split()
        )
        self.assertIn("Stop automated fix attempts after three cycles", workflow)
        self.assertIn(
            "Resume, the fix loop, draft retries and `ballast run checkpoint` are "
            "agent-provisional paths: the merge decision stays the single human "
            "approval",
            workflow,
        )
        readme = " ".join((ROOT / "README.md").read_text().split())
        self.assertIn("`ballast run resume` continues a blocked", readme)
        self.assertIn("merging the PR stays the single human approval", readme)

    def test_adr_0007_amends_adr_0004(self) -> None:
        adr = ROOT / "docs/adr/0007-autonomous-resume-and-bounded-recovery.md"
        text = adr.read_text()
        self.assertIn("- Status: proposed", text)
        self.assertIn("Agent-provisional", text)
        old = (ROOT / "docs/adr/0004-autonomous-provisional-decisions.md").read_text()
        self.assertIn("Amended by [ADR-0007]", old)


# Pre-#21 values: the feature must not widen what a headless agent may do.
SETTINGS_DIGEST = "064a1d2d39e7915c10708c28c52abb88b4556875fc120bc913fd74738599816c"
CONFINED_ALLOW = tuple(
    f"Bash({command}{rest})"
    for command in ("ls", "cat", "head", "tail", "wc", "find")
    for rest in ("", " *")
)
CONFINED_DENY = tuple(
    f"Bash(find *{action}*)"
    for action in ("-exec", "-ok", "-delete", "-fprint", "-fls")
)


class PermissionsUnchangedTests(unittest.TestCase):
    """#21 T042 [AC-032, FR-003, FR-025]: agent permissions are unchanged."""

    def test_settings_and_confined_tools(self) -> None:
        import hashlib  # noqa: PLC0415
        import sys  # noqa: PLC0415

        settings = ROOT / "tools/spec_workflow/claude-settings.json"
        self.assertEqual(
            hashlib.sha256(settings.read_bytes()).hexdigest(), SETTINGS_DIGEST
        )
        sys.path.insert(0, str(ROOT / "tools/spec_workflow"))
        try:
            import agent  # noqa: PLC0415
        finally:
            sys.path.pop(0)
        self.assertEqual(agent.CONFINED_ALLOW, CONFINED_ALLOW)
        self.assertEqual(agent.CONFINED_DENY, CONFINED_DENY)
        self.assertEqual(
            agent.permission_args("codex", ["exec", "PROMPT"]),
            [
                "exec",
                "--sandbox",
                "workspace-write",
                "--config",
                "sandbox_workspace_write.network_access=false",
                "--config",
                "sandbox_workspace_write.writable_roots=[]",
                "PROMPT",
            ],
        )


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
