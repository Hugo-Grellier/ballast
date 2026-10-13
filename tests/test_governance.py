"""Governance text for Autonomous runs (FR-029, FR-030)."""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONSTITUTION = ROOT / ".specify/memory/constitution.md"
AMENDMENT = ROOT / "specs/27-autonomous-core/constitution-amendment.md"
VERSION = "**Version**: 1.2.0"


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

    def test_constitution_allows_setup_recorded_baselines(self) -> None:
        # #55, ADR-0015: BL-INV-002 also accepts a baseline setup recorded.
        text = CONSTITUTION.read_text(encoding="utf-8")
        self.assertIn("or until the operator's `ballast setup` or worktree", text)
        self.assertIn("**1.2.0** (2026-10-06, #55)", text)

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

    def test_template_names_allowed_verification_commands(self) -> None:
        """#124: verification tasks use commands the step allowlist covers."""
        text = (ROOT / "templates/spec-kit/templates/tasks-template.md").read_text()
        self.assertIn("**Verification commands**:", text)
        self.assertIn("`[checks] commands`", text)
        self.assertIn("`[agents.permissions] extra_allow`", text)

    def test_installed_template_carries_the_task_guidance(self) -> None:
        """#112: the preset's tasks template replaces Ballast's copy at runtime.

        Spec Kit resolves a preset template before `.specify/templates/`, so the
        guidance must reach the preset's template through preset.patch.
        """
        template = (ROOT / "templates/spec-kit/templates/tasks-template.md").read_text()
        self.assertIn("[DEFERRED-TO-PR]", template)
        self.assertIn("`ballast run demo`", template)
        self.assertIn('"AC-002": []', template)
        program = shutil.which("patch")
        if program is None:
            self.skipTest("patch is not installed")
        with tempfile.TemporaryDirectory() as temp:
            # The pinned preset's own files, before Ballast's patch.
            preset = Path(temp) / "preset"
            shutil.copytree(ROOT / "tests/fixtures/spec-kit/preset", preset)
            subprocess.run(  # noqa: S603 - fixed program and arguments
                [program, "-p1", "-s", "-i", str(ROOT / "tools/spec-kit/preset.patch")],
                cwd=preset,
                check=True,
            )
            installed = (preset / "templates/tasks-template.md").read_text()
        for name in (
            "Acceptance evidence",
            "Operator-only checks",
            "Workflow-owned steps",
            "Verification commands",
        ):
            start = template.index(f"**{name}**:")
            self.assertIn(template[start : template.index("\n", start)], installed)

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
            (
                "An Autonomous run's refreshed packet still lists every decision as "
                "agent-provisional"
            ),
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

    def test_adr_0010_amends_adr_0004(self) -> None:
        adr = ROOT / "docs/adr/0010-autonomous-resume-and-bounded-recovery.md"
        text = adr.read_text()
        self.assertIn("- Status: accepted", text)
        self.assertIn("Agent-provisional", text)
        old = (ROOT / "docs/adr/0004-autonomous-provisional-decisions.md").read_text()
        self.assertIn("Amended by [ADR-0010]", old)


# Pre-#21 values: the feature must not widen what a headless agent may do.
# #79 added chmod, deliberately: bwrap confines it to the worktree.
SETTINGS_DIGEST = "064a1d2d39e7915c10708c28c52abb88b4556875fc120bc913fd74738599816c"
CONFINED_ALLOW = tuple(
    f"Bash({command}{rest})"
    for command in ("ls", "cat", "head", "tail", "wc", "find", "chmod")
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


class DemoPolicyTests(unittest.TestCase):
    """#22 T024 [AC-007, AC-009]: the policy documents demo capture."""

    def test_demo_capture_subsection(self) -> None:
        spec_kit = (ROOT / "templates/policies/spec-kit-workflow.md").read_text()
        section = spec_kit[spec_kit.index("### Demo capture") :]
        section = " ".join(section[: section.index("\n## ")].split())
        for text in (
            "`ballast run demo RUN_ID SCENARIO [--no-wait]`",
            "Check out the captured commit in a clean checkout and run that command",
            "only seeded, nonsensitive data and fake accounts",
            "the video and the job log are readable by anyone with repository read",
            "A command that itself exits 124 or 137",
            "reported `timed-out`",
            "Every feature branch must carry the default branch's `ballast-demo.yml`",
            "It is never evidence for a criterion",
        ):
            self.assertIn(text, section)
        for state in (
            "captured",
            "in progress",
            "failed",
            "missing",
            "stale",
            "not yet requested",
            "not configured",
            "configuration invalid",
        ):
            with self.subTest(state=state):
                self.assertIn(f"| `{state}` |", section)


class LocalFallbackDocumentTests(unittest.TestCase):
    """#23 T028 to T033 [AC-018, AC-019]: the fallback's evidence and documents."""

    DOCUMENTS = (
        "specs/23-free-fallback/evaluation.md",
        "docs/adr/0014-local-zero-cost-fallback.md",
        "templates/policies/spec-kit-workflow.md",
        "templates/policies/model-routing.md",
        "README.md",
        "specs/TECHNICAL-SPEC.md",
    )

    def test_policy_subsection(self) -> None:
        spec_kit = (ROOT / "templates/policies/spec-kit-workflow.md").read_text()
        section = spec_kit[spec_kit.index("## Local fallback") :]
        section = " ".join(section[: section.index("\n## ")].split())
        for text in (
            "--local-fallback MODEL",
            "ballast run resume RUN_ID --local-fallback MODEL|off",
            "127.0.0.1:11434",
            "at least 16384 tokens",
            "0.13.4 or newer",
            "Spec Kit's Codex integration",
            "Only after the step's first attempt",
            "`changed-state`",
            "`privacy-exclusion`",
            "`unknown-free-status`",
            "`incompatible-capability`",
            "`permission-mismatch`",
            "`~/.agents/skills` is not empty",
            "never available in Chat runs",
            "never loosens a sandbox",
            "ballast run status RUN_ID",
            "ballast ledger report --run RUN_ID",
            "closed local port",
            "not a network boundary",
        ):
            with self.subTest(text=text):
                self.assertIn(text, section)

    def test_evaluation_and_adr(self) -> None:
        evaluation = (ROOT / self.DOCUMENTS[0]).read_text()
        for heading in ("## Summary", "### Alternatives", "## Pilot", "## Workflow"):
            self.assertIn(heading, evaluation)
        adr = (ROOT / self.DOCUMENTS[1]).read_text()
        self.assertIn("- Status: accepted", adr)
        for text in ("first** primary attempt", "200,000", "16384", "exact allowlist"):
            self.assertIn(text, adr)

    def test_links_resolve(self) -> None:
        link = re.compile(r"\]\(([^)#\s]+)(?:#[^)]*)?\)")
        # Policy templates link from where setup installs them, docs/policies/.
        for name in (n for n in self.DOCUMENTS if not n.startswith("templates/")):
            path = ROOT / name
            for target in link.findall(path.read_text()):
                if "://" in target or target.startswith("mailto:"):
                    continue
                with self.subTest(document=name, target=target):
                    self.assertTrue((path.parent / target).exists())


class FeatureUiStatesDocumentTests(unittest.TestCase):
    """#142 T020 [AC-017 to AC-019]: where UI states live and why it changed."""

    ADR = "docs/adr/0019-feature-local-ui-states.md"

    def packet_section(self) -> str:
        spec_kit = (ROOT / "templates/policies/spec-kit-workflow.md").read_text()
        section = spec_kit[spec_kit.index("### Acceptance packet") :]
        return " ".join(section[: section.index("\n### ")].split())

    def test_policy_describes_where_ui_states_live(self) -> None:
        section = self.packet_section()
        for text in (
            "`specs/<feature>/ui-states.toml`",
            "[[ui_states]]",
            'criteria = ["AC-003"]',
            "a non-empty `criteria` list and exactly one of `path` or `check`",
            (
                "`[[review.ui_states]]` in `ballast.toml` holds only criterion-less,"
                " repository-wide entries"
            ),
            "at most 50 in total",
            "criteria belong in the feature's ui-states.toml",
            "labeled `agent-declared in ui-states.toml`",
            "A UI state never changes a criterion's state",
            "names the failing source",
        ):
            with self.subTest(text=text):
                self.assertIn(text, section)

    def test_policy_explains_keeping_screenshots_current(self) -> None:
        section = self.packet_section()
        for text in (
            "commit the new `path` file with the change that alters the screen",
            "the packet links it at the head commit",
            "A `check` result is read for the head commit only",
            "shows `missing`",
        ):
            with self.subTest(text=text):
                self.assertIn(text, section)

    def test_adr_0019_amends_adr_0006(self) -> None:
        adr = " ".join((ROOT / self.ADR).read_text().split())
        self.assertIn("- Status: proposed", adr)
        for text in (
            "`ballast.toml`",
            "`specs/<feature>/ui-states.toml`",
            "Amends: [ADR-0006](0006-review-packet-reads.md)",
            "No new program, GitHub call, fetch or download",
            "No agent authority beyond",
        ):
            with self.subTest(text=text):
                self.assertIn(text, adr)
        adr_0006 = (ROOT / "docs/adr/0006-review-packet-reads.md").read_text()
        self.assertIn("(0019-feature-local-ui-states.md)", adr_0006)
        link = re.compile(r"\]\(([^)#\s]+)(?:#[^)]*)?\)")
        for target in link.findall((ROOT / self.ADR).read_text()):
            if "://" not in target:
                with self.subTest(target=target):
                    self.assertTrue((ROOT / self.ADR).parent.joinpath(target).exists())


class AutonomousStopRuleDocumentTests(unittest.TestCase):
    """#150 [AC-001 to AC-011, FR-008, FR-009, FR-012]: the Autonomous stop rule.

    ADR-0020 states the rule, ADR-0004 and ADR-0010 point to it, and the policy
    template and technical spec reference it without restating it.
    """

    ADR = "docs/adr/0020-autonomous-stop-rule.md"
    ADR_0004 = "docs/adr/0004-autonomous-provisional-decisions.md"
    ADR_0010 = "docs/adr/0010-autonomous-resume-and-bounded-recovery.md"
    POLICY = "templates/policies/spec-kit-workflow.md"
    TECHNICAL_SPEC = "specs/TECHNICAL-SPEC.md"
    NOTE = "*Amended by [ADR-0020](0020-autonomous-stop-rule.md):"
    STATUS = "**Status (#150, Autonomous stop rule):**"

    def folded(self, name: str) -> str:
        return " ".join((ROOT / name).read_text(encoding="utf-8").split())

    def decision_bullet(self, lead: str) -> str:
        text = (ROOT / self.ADR).read_text(encoding="utf-8")
        decision = text[text.index("\n## Decision\n") :]
        decision = decision[: decision.index("\n## ", 1)]
        start = decision.index(f"\n- **{lead}.**")
        end = decision.find("\n- ", start + 1)
        return " ".join(decision[start : end if end != -1 else None].split())

    def adr_bullet(self, name: str, lead: str) -> str:
        text = (ROOT / name).read_text(encoding="utf-8")
        start = text.index(f"\n- **{lead}**")
        end = min(
            i
            for i in (text.find("\n- ", start + 1), text.find("\n\n", start))
            if i >= 0
        )
        return " ".join(text[start:end].split())

    def paragraph(self, name: str, opening: str) -> str:
        text = (ROOT / name).read_text(encoding="utf-8")
        start = text.index(f"\n{opening}") + 1
        end = text.find("\n\n", start)
        return " ".join(text[start : end if end != -1 else None].split())

    def assert_phrases(self, text: str, phrases: tuple[str, ...]) -> None:
        for phrase in phrases:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_adr_0020_header_and_sections(self) -> None:
        text = (ROOT / self.ADR).read_text(encoding="utf-8")
        lines = text.splitlines()
        self.assertEqual(
            lines[0],
            "# ADR-0020: Autonomous runs stop only for authority that takes effect "
            "before merge",
        )
        status = next(line for line in lines if line.startswith("- Status:"))
        self.assert_phrases(
            status,
            (
                "- Status: accepted (2026-10-13",
                "agent-provisional",
                "until the operator merges the PR",
            ),
        )
        self.assertTrue(any(line.startswith("- Risk: R2") for line in lines))
        self.assertIn(
            "- Feature: [150-autonomous-stop-rule]"
            "(../../specs/150-autonomous-stop-rule/spec.md)",
            text,
        )
        amends = [line for line in lines if line.startswith("- Amends:")]
        self.assertEqual(len(amends), 1)
        self.assert_phrases(
            amends[0],
            (
                "[ADR-0004](0004-autonomous-provisional-decisions.md)",
                "[ADR-0010](0010-autonomous-resume-and-bounded-recovery.md)",
            ),
        )
        headings = [
            "## Context",
            "## Decision",
            "## Consequences",
            "## Rejected alternatives",
        ]
        self.assertEqual([line for line in lines if line in headings], headings)

    def test_stop_rule(self) -> None:
        self.assert_phrases(
            self.decision_bullet("Stop rule"),
            (
                "takes effect before merge",
                "run authority",
                "launcher execution",
                "external writes",
                "credentials",
                "an invariant the runner enforces",
                "material provisional decision",
                "top of the PR",
            ),
        )

    def test_what_still_blocks(self) -> None:
        bullet = self.decision_bullet("What still blocks")
        self.assert_phrases(
            bullet,
            tuple(
                f"`{category}`"
                for category in (
                    "credential",
                    "permission",
                    "forge",
                    "ineligible",
                    "secret-provisioning",
                    "external-write",
                    "tamper",
                    "unfinished-step",
                    "postcondition",
                    "decision",
                    "contradiction",
                    "limit",
                    "review-finding",
                    "interrupted",
                    "upstream-sync",
                )
            ),
        )
        limit = bullet[bullet.index("*Limit outcome instead of a block:*") :]
        limit = limit[: limit.index("*Not a decision")]
        self.assert_phrases(
            limit,
            ("plan review or spec reconciliation", "failed final `run-checks`"),
        )
        self.assertIn("A failed `[checks]` command is not a `postcondition`", bullet)

    def test_trusted_author(self) -> None:
        self.assert_phrases(
            self.decision_bullet("Trusted author"),
            (
                "`ready-for-agent`",
                "operator-controlled",
                "never from the Issue or an agent-writable file",
                "#152",
            ),
        )

    def test_limit_outcome(self) -> None:
        self.assert_phrases(
            self.decision_bullet("Limit outcome"),
            (
                "agent steps",
                "wall time",
                "fix cycles",
                "draft retries",
                "in any phase",
                "Draft PR",
                "open findings",
                "failed checks",
                "`unverified`",
                "#153",
            ),
        )

    def test_self_resume(self) -> None:
        self.assert_phrases(
            self.decision_bullet("Self-resume"),
            (
                "provider usage limit",
                "without an operator `block-resolution` record",
                "runner event",
                "never a human decision",
                "mode, risk, limits and integrations",
                "condition (11)",
                "stays a Draft",
                "#154",
            ),
        )

    def test_residual_risk(self) -> None:
        self.assert_phrases(
            self.decision_bullet("Residual risk"),
            (
                "decisions concentrated at the merge",
                "material-decision cap",
                "cap was reached",
                "#151",
                "#153",
            ),
        )

    def test_invariants_and_delivery(self) -> None:
        self.assert_phrases(
            self.decision_bullet("Invariants"),
            ("BL-INV-003 and BL-INV-006", "no constitution amendment"),
        )
        self.assertIn("#151, #152, #153 and #154", self.decision_bullet("Delivery"))

    def test_adr_0020_links_resolve(self) -> None:
        link = re.compile(r"\]\(([^)#\s]+)(?:#[^)]*)?\)")
        path = ROOT / self.ADR
        for target in link.findall(path.read_text(encoding="utf-8")):
            if "://" not in target:
                with self.subTest(target=target):
                    self.assertTrue((path.parent / target).exists())

    def test_adr_0004_note(self) -> None:
        bullet = self.adr_bullet(self.ADR_0004, "Continuation as a gate-only workflow")
        self.assertIn(self.NOTE, bullet)
        note = bullet[bullet.index(self.NOTE) :]
        self.assert_phrases(note, ("Autonomous run blocks only for",))

    def test_adr_0010_notes(self) -> None:
        text = self.folded(self.ADR_0010)
        self.assertEqual(text.count(self.NOTE), 3)
        resume = self.adr_bullet(self.ADR_0010, "Autonomous resume")
        self.assertIn(self.NOTE, resume)
        self.assert_phrases(
            resume[resume.index(self.NOTE) :],
            ("provider usage limit", "`block-resolution`"),
        )
        fix_loop = self.adr_bullet(self.ADR_0010, "Bounded fix loop")
        self.assertIn(self.NOTE, fix_loop)
        self.assertIn("Draft PR", fix_loop[fix_loop.index(self.NOTE) :])
        consequences = text[text.index("## Consequences") :]
        consequences = consequences[: consequences.index("## Rejected alternatives")]
        runs_out = consequences[consequences.index("a run that runs out blocks") :]
        runs_out = runs_out[: runs_out.index(" - ")]
        self.assertIn(self.NOTE, runs_out)
        self.assertIn("Draft PR", runs_out[runs_out.index(self.NOTE) :])

    def test_chat_runs_unaffected(self) -> None:
        self.assert_phrases(
            self.decision_bullet("Chat runs"),
            ("Chat runs are unaffected", "every Chat gate needs the operator"),
        )
        adr_0009 = (
            ROOT / "docs/adr/0009-chat-mode-operator-driven-steps.md"
        ).read_text(encoding="utf-8")
        self.assertNotIn("0020", adr_0009)

    def test_policy_cites_adr_0020(self) -> None:
        text = (ROOT / self.POLICY).read_text(encoding="utf-8")
        section = text[text.index("\n## Autonomous runs\n") :]
        section = section[: section.index("\n## ", 1)]
        table = section.index("| unsafe uncertainty |")
        stop_rule = section.index("\n**Stop rule.**")
        self.assertLess(table, stop_rule)
        paragraph = self.paragraph(self.POLICY, "**Stop rule.**")
        self.assert_phrases(
            paragraph, ("ADR-0020 in the Ballast repository", "later Ballast releases")
        )
        self.assertNotIn("](", paragraph)
        self.assertNotIn("takes effect before merge", " ".join(section.split()))
        for issue in range(150, 155):
            with self.subTest(issue=issue):
                self.assertNotIn(f"#{issue}", text)

    def test_technical_spec_links_adr_0020(self) -> None:
        text = (ROOT / self.TECHNICAL_SPEC).read_text(encoding="utf-8")
        self.assertLess(
            text.index("may still block a run."), text.index(f"\n{self.STATUS}")
        )
        paragraph = self.paragraph(self.TECHNICAL_SPEC, self.STATUS)
        self.assert_phrases(
            paragraph, ("(../docs/adr/0020-autonomous-stop-rule.md)", "#151", "#154")
        )
        self.assertNotIn("takes effect before merge", paragraph)

    def test_no_human_approval_wording(self) -> None:
        import sys  # noqa: PLC0415

        sys.path.insert(0, str(ROOT / "tools/spec_workflow"))
        try:
            import autonomy  # noqa: PLC0415
        finally:
            sys.path.pop(0)
        resume = self.adr_bullet(self.ADR_0010, "Autonomous resume")
        fix_loop = self.adr_bullet(self.ADR_0010, "Bounded fix loop")
        continuation = self.adr_bullet(
            self.ADR_0004, "Continuation as a gate-only workflow"
        )
        for name, value in (
            ("ADR-0020", self.folded(self.ADR)),
            ("ADR-0004 note", continuation[continuation.index(self.NOTE) :]),
            ("ADR-0010 resume note", resume[resume.index(self.NOTE) :]),
            ("ADR-0010 fix-loop note", fix_loop[fix_loop.index(self.NOTE) :]),
            ("policy", self.paragraph(self.POLICY, "**Stop rule.**")),
            ("technical spec", self.paragraph(self.TECHNICAL_SPEC, self.STATUS)),
        ):
            with self.subTest(document=name):
                self.assertIsNone(autonomy.HUMAN_APPROVAL.search(value))


if __name__ == "__main__":
    unittest.main()
