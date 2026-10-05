"""The discovery brief (#16): the `discovery` check and spec traceability.

Validators run as the workflow runs them (`python3 -I -S artifacts.py`)
against temporary repositories, with operator state in a fresh XDG_STATE_HOME
per test. Builders for briefs, snapshots and specs are in discovery_fixtures.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from discovery_fixtures import (
    AUTHORITY,
    POLICY,
    REQUIRED,
    SECTIONS,
    SETTLED,
    SNAPSHOT,
    SPEC,
    brief_text,
    decision,
    metrics,
    snapshot_text,
)
from test_autonomous_artifacts import RecorderCase
from test_autonomy import (
    FEATURE,
    ROOT,
    TOOLS,
    artifacts,
    isolate_operator_state,
    operator_state,
)

sys.path.pop(0)

ARTIFACTS = TOOLS / "artifacts.py"
RUN = "gated1"
COMMAND = ROOT / "templates/spec-kit/extensions/ballast/commands"
EXTENSION = ROOT / "templates/spec-kit/extensions/ballast/extension.yml"


def setUpModule() -> None:  # noqa: D103
    isolate_operator_state()


def asked(ident: str, status: str = "open", answer: str = "") -> str:
    """D-01 or D-02 as the round asks it, with the operator's status and answer."""
    default = "B, for tooling" if ident == "D-02" else "A, because it can change"
    return decision(ident, status, default=default, answer=answer)


def answered(ident: str, answer: str = "A") -> str:
    """Return the decision as asked, answered by the operator."""
    return asked(ident, "answered", answer)


def two_open(**changes: str) -> dict[str, str]:
    """Return sections with D-01 and D-02 open, and D-03 settled by a policy."""
    return {
        "Undecided": "- D-01 output format\n- D-02 second format",
        "Decisions": "\n\n".join(
            (
                changes.get("D-01", asked("D-01")),
                changes.get("D-02", asked("D-02")),
                decision(
                    "D-03",
                    "settled",
                    question="Which encoding?",
                    resolution=f"UTF-8, as [S: {POLICY}] requires",
                ),
            )
        ),
    }


class DiscoveryCase(unittest.TestCase):
    """A checkout with a feature, a policy, an Issue snapshot and a gated run."""

    def setUp(self) -> None:
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name).resolve()
        (self.root / ".specify").mkdir()
        (self.root / POLICY).parent.mkdir(parents=True)
        (self.root / POLICY).write_text("# Demo policy\n")
        self.feature = self.root / FEATURE
        self.feature.mkdir(parents=True)
        self.state = operator_state(self)
        self.enterContext(patch.dict(os.environ, {"XDG_STATE_HOME": str(self.state)}))
        runs = self.root / ".specify/workflows/runs" / RUN
        runs.mkdir(parents=True)
        (runs / "inputs.json").write_text(
            json.dumps({"inputs": {"feature_directory": FEATURE}})
        )
        self.write_snapshot()

    def write_brief(self, sections: dict[str, str] | None = None, **kwargs) -> str:  # noqa: ANN003
        text = brief_text(sections, **kwargs)
        (self.feature / "discovery.md").write_text(text)
        return text

    def write_snapshot(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        path = self.root / SNAPSHOT
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(snapshot_text(*args, **kwargs))

    def run_check(self, name: str, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(  # noqa: S603
            [
                sys.executable,
                "-I",
                "-S",
                str(ARTIFACTS),
                name,
                *(args or ("--feature", FEATURE)),
            ],
            cwd=self.root,
            capture_output=True,
            text=True,
            check=False,
        )

    def gated(self, name: str = "discovery") -> subprocess.CompletedProcess[str]:
        return self.run_check(name, "--run", RUN)

    def ok(self, result: subprocess.CompletedProcess[str]) -> None:
        self.assertEqual(result.returncode, 0, result.stderr)

    def failed(self, result: subprocess.CompletedProcess[str], *texts: str) -> None:
        self.assertNotEqual(result.returncode, 0, result.stdout)
        for text in texts:
            self.assertIn(text, result.stderr)

    def state_file(self) -> Path:
        key = hashlib.sha256(FEATURE.encode()).hexdigest()
        return artifacts.state_dir(self.root) / "discovery" / f"{key}.json"

    def discovery_state(self) -> dict:
        return json.loads(self.state_file().read_text())

    def feature_object(self) -> artifacts.Feature:
        return artifacts.Feature(self.root, FEATURE, "key")


class ParserTests(unittest.TestCase):
    """T002: sections, items, markers, decisions and Issue criteria."""

    def test_sections_and_items(self) -> None:
        brief = artifacts._parse_discovery(brief_text())  # noqa: SLF001
        self.assertLessEqual(set(REQUIRED), set(brief["sections"]))
        self.assertEqual(brief["mode"], "human-gated")
        self.assertEqual(len(brief["items"]["Need"]), 4)
        self.assertTrue(brief["items"]["Need"][0].startswith("**User**: A GM"))
        self.assertEqual(brief["iacs"], [("IAC-1", "works")])
        self.assertIn("[spec.md](spec.md)", brief["preamble"])

    def test_marker_shapes(self) -> None:
        markers = artifacts._markers  # noqa: SLF001
        valid = ("[S: Issue #27 body]", "[I]", "[O: D-01]", "[P: D-12]", "[B: Scope]")
        for marker in valid:
            self.assertEqual(markers(f"text {marker}."), [marker])
        for invalid in ("[O: D-1]", "[i]", "[S:x]", "[P: D-001]"):
            self.assertEqual(markers(f"text {invalid}"), [], invalid)
        # A Markdown link is not provenance.
        self.assertEqual(markers(f"see [the policy]({POLICY})"), [])

    def test_decision_blocks(self) -> None:
        text = brief_text({"Decisions": decision("D-02", answer="")})
        (found,) = artifacts._parse_discovery(text)["decisions"].values()  # noqa: SLF001
        self.assertEqual(found["id"], "D-02")
        self.assertEqual(found["status"], "open")
        self.assertEqual(found["question"], "Which output format for D-02?")
        self.assertEqual(found["why"], "It changes what the import writes.")
        self.assertIn("[S: Issue #27 body]", found["sources"])
        self.assertEqual(len(found["options"]), 2)
        self.assertIn("Consequence: needs a viewer", found["options"][1])
        self.assertTrue(found["default"].startswith("A, because"))
        self.assertEqual((found["answer"], found["resolution"]), ("", ""))

    def test_malformed_decisions_raise(self) -> None:
        cases = {
            "heading": SETTLED.replace("### D-01:", "### D-1:"),
            "status": SETTLED.replace("settled", "maybe"),
            "missing field": SETTLED.replace("- **Question**: ", "- Question: "),
            "unknown field": SETTLED + "\n- **Approval**: yes",
            "duplicate": SETTLED + "\n\n" + SETTLED,
        }
        for name, block in cases.items():
            with self.subTest(name), self.assertRaises(artifacts.ContractError):
                artifacts._parse_discovery(brief_text({"Decisions": block}))  # noqa: SLF001


class OperatorStateTests(DiscoveryCase):
    """T002: discovery state lives in operator state, never in the checkout."""

    def test_round_trip_outside_the_checkout(self) -> None:
        feature = self.feature_object()
        path = artifacts._discovery_state_path(feature)  # noqa: SLF001
        self.assertEqual(path, self.state_file())
        self.assertFalse(path.resolve().is_relative_to(self.root))
        state = artifacts._load_discovery_state(feature)  # noqa: SLF001
        self.assertEqual(
            state, {"feature": FEATURE, "rounds": [], "answered": {}, "ran": False}
        )
        state["rounds"].append(
            {"asked": ["D-01"], "questions_digest": "sha256:" + "0" * 64, "at": "now"}
        )
        state["answered"]["D-01"] = "sha256:" + "1" * 64
        state["ran"] = True
        artifacts._save_discovery_state(feature, state)  # noqa: SLF001
        self.assertEqual(artifacts._load_discovery_state(feature), state)  # noqa: SLF001

    def test_ran_means_brief_or_state(self) -> None:
        feature = self.feature_object()
        self.assertFalse(artifacts._discovery_ran(feature))  # noqa: SLF001
        self.write_brief()
        self.assertTrue(artifacts._discovery_ran(feature))  # noqa: SLF001
        (self.feature / "discovery.md").unlink()
        state = artifacts._load_discovery_state(feature)  # noqa: SLF001
        artifacts._save_discovery_state(feature, state | {"ran": True})  # noqa: SLF001
        self.assertTrue(artifacts._discovery_ran(feature))  # noqa: SLF001

    def test_save_never_writes_through_a_symlink(self) -> None:
        feature = self.feature_object()
        path = self.state_file()
        path.parent.mkdir(parents=True)
        target = self.state / "elsewhere.json"
        path.symlink_to(target)
        state = {"feature": FEATURE, "rounds": [], "answered": {}, "ran": True}
        artifacts._save_discovery_state(feature, state)  # noqa: SLF001
        self.assertFalse(target.exists())
        self.assertFalse(path.is_symlink())

    def test_malformed_state_fails_closed(self) -> None:
        self.state_file().parent.mkdir(parents=True)
        self.state_file().write_text('{"feature": "specs/1-other"}')
        with self.assertRaises(artifacts.ContractError):
            artifacts._load_discovery_state(self.feature_object())  # noqa: SLF001


class BriefStructureTests(DiscoveryCase):
    """T005 [AC-001], T032 [AC-018]: every section, the authority note."""

    def test_valid_brief_passes(self) -> None:
        self.write_brief()
        self.ok(self.run_check("discovery"))

    def test_each_required_section_is_required(self) -> None:
        for name in REQUIRED:
            with self.subTest(name):
                self.write_brief(drop=(name,))
                self.failed(self.run_check("discovery"), f"## {name}")
                self.write_brief({name: ""})
                self.failed(self.run_check("discovery"), f"## {name}")

    def test_each_need_item_is_required(self) -> None:
        for label in ("User", "Job to be done", "Current pain", "Intended outcome"):
            with self.subTest(label):
                need = "\n".join(
                    line
                    for line in SECTIONS["Need"].splitlines()
                    if not line.startswith(f"- **{label}**")
                )
                self.write_brief({"Need": need})
                self.failed(self.run_check("discovery"), label)

    def test_changes_section_is_optional(self) -> None:
        change = "- 2026-10-05: a new comment [S: Issue comment bob 2026-10-05]"
        self.write_brief({"Changes": change})
        self.ok(self.run_check("discovery"))

    def test_evidence_marker_and_authority_note(self) -> None:
        self.write_brief(marker="# Discovery brief")
        self.failed(self.run_check("discovery"), "ballast-discovery: input evidence")
        no_intent = AUTHORITY.replace("[intent.md](intent.md)", "intent")
        self.write_brief(authority=no_intent)
        self.failed(self.run_check("discovery"), "intent.md")
        self.write_brief(authority=AUTHORITY.replace("[spec.md](spec.md)", "the spec"))
        self.failed(self.run_check("discovery"), "spec.md")

    def test_unknown_mode_fails(self) -> None:
        self.write_brief(mode="sometimes")
        self.failed(self.run_check("discovery"), "Mode")


class ProvenanceTests(DiscoveryCase):
    """T006 [AC-002]: every item cites an existing source or is an inference."""

    def test_unmarked_item_fails_naming_section_and_item(self) -> None:
        self.write_brief({"Constraints": "- Standard library only"})
        self.failed(
            self.run_check("discovery"), "## Constraints", "Standard library only"
        )

    def test_cited_path_must_exist(self) -> None:
        self.write_brief({"Constraints": "- Stdlib [S: docs/policies/missing.md]"})
        self.failed(self.run_check("discovery"), "docs/policies/missing.md")
        sources = SECTIONS["Sources"] + "\n- S-4: docs/policies/gone.md#rules"
        self.write_brief({"Sources": sources})
        self.failed(self.run_check("discovery"), "docs/policies/gone.md")

    def test_cited_path_with_section_or_line_passes(self) -> None:
        self.write_brief(
            {"Constraints": f"- Stdlib [S: {POLICY}#rules; {POLICY}:1 rule]"}
        )
        self.ok(self.run_check("discovery"))

    def test_unavailable_source_passes(self) -> None:
        self.assertIn("unavailable: docs/adr/", SECTIONS["Sources"])
        self.write_brief()
        self.ok(self.run_check("discovery"))

    def test_link_is_not_a_marker(self) -> None:
        self.write_brief({"Scope": f"- Text transcripts, see [policy]({POLICY})"})
        self.failed(self.run_check("discovery"), "## Scope")

    def test_known_and_inferred_use_their_markers(self) -> None:
        self.write_brief({"Known": "- Transcripts are text [I]"})
        self.failed(self.run_check("discovery"), "## Known")
        self.write_brief({"Inferred": "- Imports are rare [S: Issue #27 body]"})
        self.failed(self.run_check("discovery"), "## Inferred")

    def test_brief_item_marker_is_spec_only(self) -> None:
        self.write_brief({"Scope": "- Text transcripts [B: Scope]"})
        self.failed(self.run_check("discovery"), "[B:")


class DecisionRuleTests(DiscoveryCase):
    """T007 [AC-004]: decisions carry options, consequences and a default."""

    def test_open_contradiction_naming_both_sources_passes(self) -> None:
        self.write_brief(
            {"Undecided": "- D-01 output format", "Decisions": decision("D-01")}
        )
        self.ok(self.run_check("discovery"))

    def test_open_decision_rules(self) -> None:
        cases = {
            "one option": decision("D-01", options=OPTIONS_ONE),
            "no consequence": decision("D-01", options=("A — text", "B — json")),
            "no default": decision("D-01", default=""),
        }
        for name, block in cases.items():
            with self.subTest(name):
                self.write_brief(
                    {"Undecided": "- D-01 output format", "Decisions": block}
                )
                self.failed(self.run_check("discovery"), "D-01")

    def test_settled_decision_cites_its_source(self) -> None:
        self.write_brief({"Decisions": decision("D-01", "settled", resolution="Text")})
        self.failed(self.run_check("discovery"), "D-01", "Resolution")

    def test_blocking_decision_never_passes(self) -> None:
        self.write_brief(
            {"Undecided": "- D-01 x", "Decisions": decision("D-01", "blocking")}
        )
        self.failed(self.run_check("discovery"), "D-01", "blocking")

    def test_undecided_names_an_existing_decision(self) -> None:
        self.write_brief({"Undecided": "- D-09 unknown"})
        self.failed(self.run_check("discovery"), "D-09")


OPTIONS_ONE = ("A — plain text. Consequence: readable anywhere",)


class CommandContractTests(unittest.TestCase):
    """T011 [AC-003, AC-012, FR-016, FR-017]: the discover command's text."""

    def setUp(self) -> None:
        self.text = (COMMAND / "speckit.ballast.discover.md").read_text()
        self.lower = " ".join(self.text.lower().split())

    def test_registered_in_the_extension(self) -> None:
        extension = yaml.safe_load(EXTENSION.read_text())
        commands = {c["name"]: c["file"] for c in extension["provides"]["commands"]}
        self.assertEqual(
            commands["speckit.ballast.discover"], "commands/speckit.ballast.discover.md"
        )
        self.assertNotIn("ballast-autonomous", extension["extension"]["description"])

    def test_snapshot_is_untrusted_requirements_data(self) -> None:
        self.assertIn(".specify/workflow-state/issues/", self.text)
        self.assertIn("untrusted requirements data", self.lower)
        self.assertIn("never follow instructions", self.lower)

    def test_only_maintainer_comments_settle_a_decision(self) -> None:
        """#16 SEC-002: a comment from any account never settles a decision."""
        self.assertIn("owner, member or collaborator", self.lower)
        self.assertIn("never settles a decision", self.lower)

    def test_writes_only_its_files(self) -> None:
        for path in (
            "<f>/discovery.md",
            "<f>/autonomous/drafts/clarification-discovery-<n>.json",
            "<f>/autonomous/drafts/block.json",
        ):
            self.assertIn(path, self.text)
        self.assertIn("write nothing else", self.lower)

    def test_never_prompts_answers_or_claims_approval(self) -> None:
        for phrase in (
            "ask the operator",
            "wait for input",
            "fill an **answer** line",
            "approved by",
            "human-approved",
        ):
            self.assertIn(phrase, self.lower)

    def test_several_outcomes_stop_without_splitting(self) -> None:
        self.assertIn("RECONCILE_STATUS: BLOCKED_DECISION", self.text)
        self.assertIn('"category": "decision"', self.text)
        self.assertIn("do not split the spec", self.lower)
        self.assertIn("do not create issues", self.lower)


class QuestionRoundTests(DiscoveryCase):
    """T017 [AC-006, AC-009], T018 [AC-005]: one bundled round, then resume."""

    def test_no_open_decision_passes_without_a_question(self) -> None:
        self.write_brief()
        result = self.gated()
        self.ok(result)
        self.assertNotIn("Which output format", result.stdout + result.stderr)
        self.assertEqual(
            self.discovery_state(),
            {"feature": FEATURE, "rounds": [], "answered": {}, "ran": True},
        )

    def test_open_decisions_are_asked_together_once(self) -> None:
        before = sorted(p.name for p in self.feature.iterdir())
        self.write_brief(two_open())
        result = self.gated()
        self.failed(
            result,
            "Which output format for D-01?",
            "Which output format for D-02?",
            "Consequence: readable anywhere",
            "Consequence: needs a viewer",
            "A, because it can change",
            "B, for tooling",
            f"{FEATURE}/discovery.md",
            f"ballast run resume {RUN}",
        )
        # D-03 is settled by a policy: never asked (AC-005).
        self.assertNotIn("Which encoding?", result.stderr)
        (round_,) = self.discovery_state()["rounds"]
        self.assertEqual(round_["asked"], ["D-01", "D-02"])
        self.assertRegex(round_["questions_digest"], r"^sha256:[0-9a-f]{64}$")
        self.assertTrue(round_["at"])
        # Recorded in operator state only, never in the checkout.
        self.assertEqual(
            sorted(p.name for p in self.feature.iterdir()), [*before, "discovery.md"]
        )

    def test_rerun_before_answering_asks_the_same_round(self) -> None:
        self.write_brief(two_open())
        first = self.gated()
        second = self.gated()
        self.failed(second, "Which output format for D-01?")
        self.assertEqual(
            first.stderr.split("]: ", 1)[1], second.stderr.split("]: ", 1)[1]
        )
        self.assertEqual(len(self.discovery_state()["rounds"]), 1)


class AttributionTests(DiscoveryCase):
    """T019 [AC-008, AC-013], T020: answers come from the operator, once asked."""

    def ask(self) -> None:
        self.write_brief(two_open())
        self.failed(self.gated(), "Which output format")

    def test_answer_before_any_round_is_refused(self) -> None:
        self.write_brief(two_open(**{"D-01": answered("D-01")}))
        self.failed(self.gated(), "D-01", "not asked")
        self.assertFalse(self.state_file().exists())

    def test_answer_to_a_decision_outside_the_round_is_refused(self) -> None:
        self.write_brief({"Undecided": "- D-01 x", "Decisions": asked("D-01")})
        self.failed(self.gated(), "Which output format for D-01?")
        sections = two_open(**{"D-01": answered("D-01"), "D-02": answered("D-02")})
        self.write_brief(sections)
        self.failed(self.gated(), "D-02", "not asked")

    def test_changed_question_is_refused(self) -> None:
        self.ask()
        changed = decision("D-01", "answered", question="Another question?", answer="A")
        self.write_brief(two_open(**{"D-01": changed, "D-02": answered("D-02")}))
        self.failed(self.gated(), "changed")

    def test_empty_answer_keeps_the_decision_open(self) -> None:
        self.ask()
        self.write_brief(two_open(**{"D-02": answered("D-02")}))
        result = self.gated()
        self.failed(result, "Which output format for D-01?")
        self.assertNotIn("Which output format for D-02?", result.stderr)
        self.write_brief(two_open(**{"D-01": asked("D-01", "answered")}))
        self.failed(self.gated(), "D-01")

    def test_answer_without_answered_status_is_refused(self) -> None:
        self.ask()
        sections = two_open(**{"D-01": asked("D-01", answer="A")})
        self.write_brief(sections)
        self.failed(self.gated(), "D-01", "answered")

    def test_accepted_answers_are_recorded_as_digests(self) -> None:
        self.ask()
        wording = "B, my own wording"
        self.write_brief(
            two_open(**{"D-01": answered("D-01", wording), "D-02": answered("D-02")})
        )
        self.ok(self.gated())
        state = self.discovery_state()
        self.assertEqual(set(state["answered"]), {"D-01", "D-02"})
        for digest in state["answered"].values():
            self.assertRegex(digest, r"^sha256:[0-9a-f]{64}$")
        self.assertNotIn(wording, self.state_file().read_text())
        self.assertTrue(state["ran"])

    def test_accepted_answer_cannot_change(self) -> None:
        self.ask()
        sections = two_open(**{"D-01": answered("D-01"), "D-02": answered("D-02")})
        self.write_brief(sections)
        self.ok(self.gated())
        self.write_brief(
            two_open(**{"D-01": answered("D-01", "B"), "D-02": answered("D-02")})
        )
        self.failed(self.gated(), "D-01", "changed")

    def test_answer_contradiction_asks_a_second_round(self) -> None:
        self.ask()
        sections = two_open(**{"D-01": answered("D-01"), "D-02": answered("D-02")})
        self.write_brief(sections)
        self.ok(self.gated())
        sections["Undecided"] = "- D-04 answers contradict"
        sections["Decisions"] += "\n\n" + decision("D-04", question="Which wins?")
        self.write_brief(sections)
        result = self.gated()
        self.failed(result, "Which wins?")
        self.assertNotIn("Which output format for D-01?", result.stderr)
        rounds = self.discovery_state()["rounds"]
        self.assertEqual([r["asked"] for r in rounds], [["D-01", "D-02"], ["D-04"]])

    def test_operator_marker_needs_an_answered_decision(self) -> None:
        self.write_brief(two_open() | {"Known": "- Plain text is chosen [O: D-01]"})
        self.failed(self.run_check("discovery"), "[O: D-01]")

    def test_provisional_marker_is_autonomous_only(self) -> None:
        self.write_brief({"Inferred": "- Plain text [P: D-01]"})
        self.failed(self.run_check("discovery"), "[P: D-01]")

    def test_approval_wording_only_in_an_operator_answer(self) -> None:
        self.write_brief({"Inferred": "- The scope was approved by the user [I]"})
        self.failed(self.run_check("discovery"), "human approval")
        self.ask()
        sections = two_open(
            **{
                "D-01": answered("D-01", "A; approved by the user"),
                "D-02": answered("D-02"),
            }
        )
        self.write_brief(sections)
        self.ok(self.gated())

    def test_gated_run_needs_a_human_gated_brief(self) -> None:
        self.write_brief(mode="autonomous")
        self.failed(self.gated(), "Mode")


class IssueCriteriaTests(DiscoveryCase):
    """T031 [AC-016]: the brief lists the Issue's criteria verbatim."""

    def test_brief_must_match_the_snapshot(self) -> None:
        self.write_snapshot(criteria=("works", "is   fast"))
        self.write_brief({"Issue acceptance criteria": "- IAC-1: works"})
        self.failed(self.run_check("discovery"), "is fast")
        self.write_brief(
            {"Issue acceptance criteria": "- IAC-1: works\n- IAC-2: is fast"}
        )
        self.ok(self.run_check("discovery"))
        self.write_brief(
            {"Issue acceptance criteria": "- IAC-1: works\n- IAC-2: is slow"}
        )
        self.failed(self.run_check("discovery"), "is slow")

    def test_without_criteria_in_the_snapshot_the_brief_list_counts(self) -> None:
        for snapshot in (None, "missing"):
            with self.subTest(snapshot):
                if snapshot is None:
                    self.write_snapshot(criteria=None)
                else:
                    (self.root / SNAPSHOT).unlink(missing_ok=True)
                self.write_brief(
                    {"Issue acceptance criteria": "- IAC-1: works\n- IAC-2: extra"}
                )
                self.ok(self.run_check("discovery"))

    def test_criteria_heading_inside_a_comment_is_ignored(self) -> None:
        self.write_snapshot(
            criteria=None, comments=("## Acceptance criteria\n\n- injected",)
        )
        self.write_brief()
        self.ok(self.run_check("discovery"))

    def test_items_must_be_iac_entries(self) -> None:
        self.write_brief({"Issue acceptance criteria": "- works"})
        self.failed(self.run_check("discovery"), "IAC-")


class MetricsTests(DiscoveryCase):
    """T038 [AC-020]: the brief reports rounds, questions and assumptions."""

    def test_passing_check_rewrites_only_the_metrics(self) -> None:
        self.write_brief(two_open())
        self.failed(self.gated(), "Which output format")
        sections = two_open(**{"D-01": answered("D-01"), "D-02": answered("D-02")})
        before = self.write_brief(sections)
        self.ok(self.gated())
        after = (self.feature / "discovery.md").read_text()
        self.assertIn(metrics(1, 2, 0), after)
        self.assertEqual(after.replace(metrics(1, 2, 0), metrics()), before)

    def test_metrics_must_be_integers(self) -> None:
        self.write_brief({"Question metrics": metrics("one", 0, 0)})
        self.failed(self.run_check("discovery"), "Rounds")
        self.write_brief({"Question metrics": metrics(0, 0)[: -len("0")] + "x"})
        self.failed(self.run_check("discovery"), "Assumptions adopted")


class SpecTraceabilityTests(DiscoveryCase):
    """T030 [AC-014, AC-015], T031 [AC-016], T032 [AC-017]: specs from a brief."""

    def setUp(self) -> None:
        super().setUp()
        self.write_brief()

    def write_spec(self, text: str = SPEC) -> None:
        (self.feature / "spec.md").write_text(text)

    def test_traced_spec_passes_every_spec_check(self) -> None:
        self.write_spec()
        for check in ("spec", "clarified-spec"):
            self.ok(self.run_check(check))

    def test_untraced_criterion_fails_naming_it(self) -> None:
        self.write_spec(SPEC.replace(" [B: Edge, failure and permission cases]", ""))
        for check in ("spec", "clarified-spec", "record-intent", "intent", "plan"):
            with self.subTest(check):
                self.failed(self.run_check(check), "AC-002")

    def test_scenario_without_an_id_fails(self) -> None:
        self.write_spec(SPEC.replace("2. **AC-002**: **Given**", "2. **Given**"))
        self.failed(self.run_check("spec"), "AC-NNN", "empty transcript")

    def test_spec_without_scenarios_fails(self) -> None:
        self.write_spec("# Feature Specification: Demo run\n\nNothing yet.\n")
        self.failed(self.run_check("spec"), "acceptance scenario")

    def test_markers_must_match_decision_status(self) -> None:
        for marker in ("[O: D-01]", "[P: D-01]", "[O: D-07]"):
            with self.subTest(marker):
                self.write_spec(SPEC.replace("[S: IAC-1]", f"[S: IAC-1] {marker}"))
                self.failed(self.run_check("spec"), marker)

    def test_issue_criteria_are_cited_or_non_goals(self) -> None:
        self.write_snapshot(criteria=("works", "is fast"))
        self.write_brief(
            {"Issue acceptance criteria": "- IAC-1: works\n- IAC-2: is fast"}
        )
        self.write_spec()
        self.failed(self.run_check("spec"), "IAC-2", "is fast")
        self.write_spec(SPEC.replace("[S: IAC-1]", "[S: IAC-1; IAC-2]"))
        self.ok(self.run_check("spec"))
        self.write_spec(SPEC + "\n## Non-goals\n\n- IAC-2: speed is out of scope.\n")
        self.ok(self.run_check("spec"))
        prose = SPEC.replace("[S: IAC-1]", "[S: IAC-1] (Issue #27 AC 2)")
        self.write_spec(prose)
        self.failed(self.run_check("spec"), "IAC-2")
        self.write_spec(SPEC + "\nIAC-2 is in the overview.\n")
        self.failed(self.run_check("spec"), "IAC-2")

    def test_feature_without_discovery_is_unchanged(self) -> None:
        (self.feature / "discovery.md").unlink()
        self.write_spec("# Feature Specification: Old\n\n1. **Given** x [AC-001]\n")
        self.ok(self.run_check("spec"))
        self.ok(self.gated("spec"))

    def test_deleted_brief_after_discovery_ran_fails(self) -> None:
        self.ok(self.gated())
        (self.feature / "discovery.md").unlink()
        self.write_spec()
        self.failed(self.gated("spec"), "discovery.md")
        self.failed(self.run_check("spec"), "discovery.md")

    def test_brief_edit_after_intent_leaves_intent_valid(self) -> None:
        self.write_spec()
        self.ok(self.run_check("record-intent"))
        intent = (self.feature / "intent.md").read_text()
        self.write_brief({"Inferred": "- Imports are frequent after all [I]"})
        self.ok(self.run_check("intent"))
        self.assertEqual((self.feature / "intent.md").read_text(), intent)


class AutonomousBriefTests(RecorderCase):
    """T025 [AC-012, AC-013], T024 [AC-010], T026 [FR-016], T038 [AC-020]."""

    def setUp(self) -> None:
        super().setUp()
        (self.root / POLICY).parent.mkdir(parents=True)
        (self.root / POLICY).write_text("# Demo policy\n")
        (self.root / SNAPSHOT).parent.mkdir(parents=True, exist_ok=True)
        (self.root / SNAPSHOT).write_text(snapshot_text())
        self.git("add", "-A", "docs")
        self.git("commit", "-q", "-m", "policy")

    def write_brief(self, sections: dict[str, str] | None = None, **kwargs) -> None:  # noqa: ANN003
        kwargs.setdefault("mode", "autonomous")
        (self.feature / "discovery.md").write_text(brief_text(sections, **kwargs))

    def assumed(self, ident: str = "D-01") -> str:
        return decision(ident, "assumed", resolution="A: reversible, plain text")

    def record_assumptions(self, *idents: str) -> None:
        self.step(
            {
                f"clarification-discovery-{n}.json": self.draft(
                    "clarification",
                    summary=f"{ident}: assume plain text output",
                    artifact=f"{FEATURE}/discovery.md",
                    evidence=[f"{FEATURE}/discovery.md"],
                    assumption={
                        "question": f"{ident}: Which output format?",
                        "default": "Plain text",
                        "reversible": True,
                    },
                )
                for n, ident in enumerate(idents, 1)
            }
        )
        self.ok(self.record("clarification"))

    def test_settled_brief_passes_and_sets_ran(self) -> None:
        self.write_brief()
        self.ok(self.check("discovery"))
        feature = artifacts.Feature(self.root, FEATURE, "run42")
        self.assertTrue(artifacts._load_discovery_state(feature)["ran"])  # noqa: SLF001

    def test_open_answered_and_operator_markers_fail(self) -> None:
        cases = {
            "open": {"Undecided": "- D-01 x", "Decisions": decision("D-01")},
            "answered": {"Decisions": answered("D-01")},
            "operator marker": {"Known": "- Text [O: D-01]"},
        }
        for name, sections in cases.items():
            with self.subTest(name):
                self.write_brief(sections)
                self.failed(self.check("discovery"), "D-01")

    def test_human_gated_brief_fails(self) -> None:
        self.write_brief(mode="human-gated")
        self.failed(self.check("discovery"), "Mode")

    def test_approval_wording_fails_even_in_an_answer(self) -> None:
        self.write_brief({"Inferred": "- Human-approved scope [I]"})
        self.failed(self.check("discovery"), "human approval")

    def test_assumed_decision_needs_a_recorded_assumption(self) -> None:
        sections = {
            "Inferred": "- Plain text is used [P: D-01]",
            "Decisions": self.assumed("D-01"),
            "Question metrics": metrics(0, 0, 1),
        }
        self.write_brief(sections)
        self.record_assumptions("D-01")
        self.ok(self.check("discovery"))
        record = (self.feature / "autonomous/record.md").read_text()
        self.assertIn("D-01: assume plain text output", record)
        self.assertIn("assume (agent-provisional)", record)
        sections["Decisions"] += "\n\n" + self.assumed("D-02")
        sections["Question metrics"] = metrics(0, 0, 2)
        self.write_brief(sections)
        self.failed(self.check("discovery"), "D-02")

    def test_metrics_must_equal_the_recorded_assumptions(self) -> None:
        self.write_brief({"Question metrics": metrics(0, 0, 1)})
        self.failed(self.check("discovery"), "Assumptions adopted")
        self.write_brief({"Question metrics": metrics(1, 0, 0)})
        self.failed(self.check("discovery"), "Rounds")
        before = brief_text(mode="autonomous")
        self.write_brief()
        self.ok(self.check("discovery"))
        self.assertEqual((self.feature / "discovery.md").read_text(), before)

    def test_write_outside_the_feature_fails(self) -> None:
        self.write_brief()
        (self.root / "src.py").write_text("print('x')\n")
        self.failed(self.check("discovery"), "src.py")
        (self.root / "src.py").unlink()
        drafts = self.feature / "autonomous/drafts"
        drafts.mkdir(parents=True, exist_ok=True)
        (drafts / "note.json").write_text("{}")
        self.ok(self.check("discovery"))


if __name__ == "__main__":
    unittest.main()
