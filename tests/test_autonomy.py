"""Units of tools/spec_workflow/autonomy.py, the Autonomous operator records.

No test calls GitHub or a model: a fake `gh` serves canned JSON, Git runs on
temporary repositories with a bare `origin`, and operator state lives in a
temporary XDG_STATE_HOME. Real-bubblewrap cases are skipped where the host has
no usable `bwrap`.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import ClassVar
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools/spec_workflow"
FIXTURES = ROOT / "tests/fixtures/autonomy"
sys.path.insert(0, str(TOOLS))
try:
    import artifacts
    import autonomy
    import draft_pr
    import ledger
finally:
    sys.path.pop(0)

FEATURE = "specs/27-demo-run"
ISSUE = 27
SCOPE = """Scope gate: feature
Main outcome: Demo outcome
In scope: demo
Out of scope: everything else
Risk: {risk}
Privileged actions before merge: {actions}
{extra}
<!-- ballast-intake: issue=#27; scope=feature -->
"""
UPDATE_GOLDEN = os.environ.get("BALLAST_UPDATE_GOLDEN") == "1"
GITHUB_URL = "https://github.com/acme/demo.git"
GITHUB_PIN = '[github]\nrepository = "acme/demo"\n'


def listed_pr(number: int, body: str, **changes: object) -> dict:
    """One `gh pr list --json` entry for a PR from acme/demo's own branch."""
    return {
        "number": number,
        "url": f"https://github.com/acme/demo/pull/{number}",
        "body": body,
        "isCrossRepository": False,
        "headRepository": {"name": "demo"},
        "headRepositoryOwner": {"login": "acme"},
        **changes,
    }


def served_pr(number: int, body: str, **changes: object) -> dict:
    """`gh api repos/acme/demo/pulls/N`: an open draft from 27-demo-run to main."""
    return {
        "number": number,
        "html_url": f"https://github.com/acme/demo/pull/{number}",
        "state": "open",
        "merged_at": None,
        "draft": True,
        "body": body,
        "base": {"ref": "main"},
        "head": {
            "ref": "27-demo-run",
            "repo": {"full_name": "acme/demo", "owner": {"login": "acme"}},
        },
        **changes,
    }


# Beside the real default: bwrap gives ~/.cache a writable overlay, which the
# confinement self-test rightly treats as reachable state.
STATE_PARENT = Path.home() / ".local/state/ballast-tests"


def outside_temp() -> Path:
    """Return a parent for test directories that must not be agent-writable."""
    STATE_PARENT.mkdir(parents=True, exist_ok=True)
    return STATE_PARENT


def operator_state(case: unittest.TestCase | None = None) -> Path:
    """Return a fresh XDG_STATE_HOME, removed after the test (or module).

    Never under a temp root or a checkout: state_dir refuses those, because an
    agent could write them (#34).
    """
    state = TemporaryDirectory(dir=outside_temp())
    (case.addCleanup if case else unittest.addModuleCleanup)(state.cleanup)
    return Path(state.name)


def isolate_operator_state() -> None:
    """Point operator state at a module-scoped directory, never the real one.

    record-intent registers approvals there; call from setUpModule.
    """
    patcher = patch.dict(os.environ, {"XDG_STATE_HOME": str(operator_state())})
    patcher.start()
    unittest.addModuleCleanup(patcher.stop)


def trusted_directory(case: unittest.TestCase) -> Path:
    """Return a fresh directory outside every Git working tree and temp root.

    Operator-side programs (bwrap, systemd-run, gh, git) resolve only from
    such directories (ADR-0003), so their test fakes live here, not in /tmp.
    """
    base = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")
    base /= "ballast-tests"
    base.mkdir(parents=True, exist_ok=True)
    directory = TemporaryDirectory(dir=base)
    case.addCleanup(directory.cleanup)
    return Path(directory.name).resolve()


def _install(source: Path, target: Path) -> None:
    shutil.copyfile(source, target)
    target.chmod(0o755)


def _bwrap_works() -> bool:
    bwrap = shutil.which("bwrap")
    if bwrap is None:
        return False
    try:
        return (
            subprocess.run(  # noqa: S603
                [bwrap, "--ro-bind", "/", "/", "--unshare-pid", "--", "true"],
                capture_output=True,
                check=False,
                timeout=30,
            ).returncode
            == 0
        )
    except (OSError, subprocess.TimeoutExpired):
        return False


class AutonomyCase(unittest.TestCase):
    """A feature-branch checkout with a bare origin, fake gh and private state.

    Shared by the Autonomous test modules; it has no tests of its own.
    """

    def setUp(self) -> None:
        self.directory = TemporaryDirectory()
        self.base = Path(self.directory.name).resolve()
        self.root = self.base / "repo"
        self.root.mkdir()
        # Fakes of operator-side programs: outside working trees and /tmp.
        self.bin = trusted_directory(self)
        self.gh_dir = self.base / "gh"
        self.gh_dir.mkdir()
        self.state = operator_state(self)
        gitconfig = self.base / "gitconfig"
        origin = self.base / "origin.git"
        # origin is the pinned GitHub repository by name; pushes reach the
        # bare repository through the operator's (global) pushInsteadOf.
        gitconfig.write_text(
            "[user]\n\tname = t\n\temail = t@example.test\n"
            "[init]\n\tdefaultBranch = main\n"
            f'[url "{self.base}/gh/"]\n\tpushInsteadOf = https://github.com/\n'
        )
        (self.base / "gh/acme").mkdir(parents=True)
        (self.base / "gh/acme/demo.git").symlink_to(origin)
        _install(FIXTURES / "fake_gh.py", self.bin / "gh")
        self.real_path = os.environ["PATH"]
        self.env = {
            **os.environ,
            "PATH": f"{self.bin}{os.pathsep}{self.real_path}",
            "XDG_STATE_HOME": str(self.state),
            "FAKE_GH_DIR": str(self.gh_dir),
            "FAKE_GH_LOG": str(self.base / "gh.log"),
            "GIT_CONFIG_GLOBAL": str(gitconfig),
            "GIT_CONFIG_NOSYSTEM": "1",
        }
        self.enterContext(patch.dict(os.environ, self.env, clear=True))
        # The fakes live under the temp root, which gh/git resolution refuses
        # in production (an agent can write there); trust it in tests.
        self.enterContext(patch.object(ledger, "agent_temp_roots", tuple))
        self.git("init", "-q")
        (self.root / ".gitignore").write_text(
            # What tools/setup ignores under .specify/ that runs write.
            ".specify/workflow-state/\n.specify/workflows/runs/\n"
            ".specify/feature.json\n"
        )
        (self.root / ".specify").mkdir()
        (self.root / ".specify/memory").mkdir()
        (self.root / ".specify/memory/constitution.md").write_text("# C\n")
        (self.root / "ballast.toml").write_text(
            '[checks]\ncommands = ["true"]\n' + GITHUB_PIN
        )
        (self.root / "README.md").write_text("demo\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "base")
        subprocess.run(  # noqa: S603
            ["git", "init", "-q", "--bare", str(origin)],  # noqa: S607
            check=True,
            capture_output=True,
        )
        self.git("remote", "add", "origin", GITHUB_URL)
        self.git("push", "-q", "-u", "origin", "main")
        self.git("checkout", "-q", "-b", "27-demo-run")

    def tearDown(self) -> None:
        self.directory.cleanup()

    def git(self, *args: str) -> str:
        return subprocess.run(  # noqa: S603
            ["git", *args],  # noqa: S607
            cwd=self.root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout

    def gh_data(self, name: str, data: object) -> None:
        (self.gh_dir / name).write_text(json.dumps(data))

    def gh_calls(self) -> list[list[str]]:
        log = self.base / "gh.log"
        if not log.exists():
            return []
        return [json.loads(line) for line in log.read_text().splitlines()]

    def eligible_issue(  # noqa: PLR0913 - fixture knobs
        self,
        *,
        risk: str = "R1",
        actions: str = "none",
        labels: tuple[str, ...] = ("ready-for-agent",),
        author: str = "OWNER",
        extra: str = "",
        state: str = "open",
    ) -> None:
        self.gh_data(
            "repo.json",
            {"nameWithOwner": "acme/demo", "defaultBranchRef": {"name": "main"}},
        )
        self.gh_data(
            f"repos_acme_demo_issues_{ISSUE}.json",
            {
                "number": ISSUE,
                "title": "Demo run",
                "state": state,
                "labels": [{"name": name} for name in labels],
                "body": "## Acceptance criteria\n\n- works\n",
            },
        )
        self.gh_data(f"repos_acme_demo_issues_{ISSUE}_sub_issues.json", [])
        self.gh_data(f"repos_acme_demo_issues_{ISSUE}_dependencies_blocked_by.json", [])
        self.gh_data(
            f"repos_acme_demo_issues_{ISSUE}_comments.json",
            [
                {
                    "body": SCOPE.format(risk=risk, actions=actions, extra=extra),
                    "author_association": author,
                }
            ],
        )

    def policy(self, table: str = "") -> tuple[dict, dict, list[str]]:
        import tomllib  # noqa: PLC0415

        return autonomy.parse_policy(tomllib.loads(table))

    def make_run(self, run_id: str = "run42", **changes: object) -> dict:
        policy, _, _ = self.policy()
        record = autonomy.new_run(
            run_id=run_id,
            feature=FEATURE,
            issue=ISSUE,
            workflow="ballast-autonomous",
            mode="autonomous",
            integration="claude",
            review_integration="codex",
            risk={
                "level": "R1",
                "source": "scope-record",
                "history": [{"level": "R1", "at": autonomy.now(), "decision_id": None}],
                "boundaries": [],
            },
            eligibility={
                "eligible": True,
                "checked_at": autonomy.now(),
                "reasons": [],
                "privileged_actions": [],
                "policy": policy,
                "ignored_policy": [],
            },
            limits=autonomy.resolve_limits({}),
        )
        record.update(changes)
        autonomy.write_run(self.root, record)
        return record


def fixed_run(*, risk: str = "R1", cross: bool = True) -> dict:
    """Return a run record with fixed timestamps, for golden rendering."""
    at = "2026-10-03T12:00:00+00:00"
    return {
        "version": 1,
        "run_id": "gold01",
        "feature": FEATURE,
        "issue": ISSUE,
        "workflow": "ballast-autonomous",
        "mode_history": [
            {
                "mode": "autonomous",
                "at": at,
                "by": "operator",
                "action": "start",
                "reason": None,
                "decision_id": None,
            }
        ],
        "status": "completed",
        "agent_steps": 12,
        "integration": "claude",
        "review_integration": "codex" if cross else "claude",
        "cross_provider": cross,
        "continues": None,
        "started_at": at,
        "risk": {
            "level": risk,
            "source": "scope-record",
            "history": [{"level": risk, "at": at, "decision_id": None}],
            "boundaries": ["agent authority", "trust model"] if risk == "R2" else [],
        },
        "eligibility": {
            "eligible": True,
            "checked_at": at,
            "reasons": [],
            "privileged_actions": [],
            "policy": {
                "risk": ["R0", "R1", "R2"],
                "excluded_boundaries": [],
                "authorized_privileged_actions": [],
            },
            "ignored_policy": [],
        },
        "limits": {
            "wall_time_minutes": 240,
            "deadline": "2026-10-03T16:00:00+00:00",
            "max_agent_steps": 30,
            "source": "default",
        },
    }


def fixed_decision(  # noqa: PLR0913, D103 - fixture knobs
    number: int,
    point: str,
    *,
    summary: str = "Accepted",
    material: bool = False,
    supersedes: str | None = None,
    review: dict | None = None,
    provider: str = "claude",
    role: str = "author",
) -> dict:
    entry = {
        "id": f"PD-{number:04d}",
        "prev": "0" * 64,
        "point": point,
        "decision": autonomy.POINT_DECISION[point],
        "summary": summary,
        "basis": f"Basis for {point}.\nSecond line @someone <!-- x -->",
        "evidence": [f"{FEATURE}/spec.md"],
        "artifact": {"path": f"{FEATURE}/spec.md", "sha256": "ab" * 32},
        "agent": {
            "provider": provider,
            "model": "model-x",
            "role": role,
            "step_id": f"step-{number}",
        },
        "material": material,
        "supersedes": supersedes,
        "privileged_actions": [],
        "at": "2026-10-03T12:00:00+00:00",
    }
    if review is not None:
        entry["review"] = review
    return entry


def review(kind: str, *, cross: bool = True, findings: list | None = None) -> dict:
    """Return a review entry as the recorder writes it."""
    return {
        "kind": kind,
        "verdict": "approved",
        "report": f"{FEATURE}/reviews/{kind}.md",
        "cross_provider": cross,
        "author_provider": "claude",
        "findings": findings or [],
    }


def golden_decisions(*, cross: bool = True) -> list[dict]:
    """Return the decision log the golden files render."""
    reviewer = "codex" if cross else "claude"
    return [
        fixed_decision(1, "scope"),
        fixed_decision(2, "intent", summary="Intent | accepted @team"),
        fixed_decision(
            3,
            "plan-review",
            review=review("plan", cross=cross),
            provider=reviewer,
            role="reviewer",
        ),
        fixed_decision(4, "plan"),
        fixed_decision(5, "tasks"),
        fixed_decision(
            6,
            "implementation-review",
            review=review(
                "engineering",
                cross=cross,
                findings=[
                    {
                        "id": "F-001",
                        "severity": "medium",
                        "label": "missing-test",
                        "disposition": "accepted-provisionally",
                        "reason": "Covered by the pilot",
                        "evidence": [],
                    }
                ],
            ),
            provider=reviewer,
            role="reviewer",
        ),
        fixed_decision(
            7,
            "decision-resolution",
            summary="DEC-0001 resolved: keep scope",
            material=True,
        ),
        fixed_decision(8, "intent", summary="Renewed intent", supersedes="PD-0002"),
        fixed_decision(
            9,
            "spec-reconciliation",
            review=review("spec-reconciliation", cross=cross),
            provider=reviewer,
            role="reviewer",
        ),
        fixed_decision(10, "final-acceptance"),
    ]


GOLDEN_CHECKS = [
    {"command": "true", "exit": 0, "seconds": 0.25, "provenance": "runner"}
]


class RunRecordTests(AutonomyCase):
    """FR-002, FR-003: the run record is strict and only lowers."""

    def test_round_trip_and_private_directory(self) -> None:
        record = self.make_run()
        self.assertEqual(autonomy.read_run(self.root, "run42"), record)
        directory = autonomy.run_dir(self.root, "run42")
        self.assertEqual(directory.stat().st_mode & 0o777, 0o700)
        self.assertTrue(str(directory).startswith(str(self.state)))

    def test_missing_malformed_symlinked_and_unknown_version_refuse(self) -> None:
        with self.assertRaisesRegex(autonomy.AutonomyError, "missing"):
            autonomy.read_run(self.root, "nope")
        self.make_run()
        path = autonomy.run_file(self.root, "run42")
        path.write_text("{not json")
        with self.assertRaisesRegex(autonomy.AutonomyError, "malformed"):
            autonomy.read_run(self.root, "run42")
        record = self.make_run()
        record["version"] = 2
        path.write_text(json.dumps(record))
        with self.assertRaisesRegex(autonomy.AutonomyError, "version"):
            autonomy.read_run(self.root, "run42")
        target = self.base / "elsewhere.json"
        target.write_text(json.dumps(self.make_run()))
        path.unlink()
        path.symlink_to(target)
        with self.assertRaisesRegex(autonomy.AutonomyError, "unreadable"):
            autonomy.read_run(self.root, "run42")

    def test_run_id_must_match_directory(self) -> None:
        record = self.make_run()
        autonomy.write_json(autonomy.run_file(self.root, "other"), record)
        with self.assertRaisesRegex(autonomy.AutonomyError, "belong"):
            autonomy.read_run(self.root, "other")
        with self.assertRaises(autonomy.AutonomyError):
            autonomy.run_dir(self.root, "../escape")

    def test_status_transitions(self) -> None:
        record = self.make_run()
        autonomy.set_status(record, "completed")
        autonomy.set_status(record, "published")
        autonomy.set_status(record, "continued")
        with self.assertRaises(autonomy.AutonomyError):
            autonomy.set_status(record, "active")
        with self.assertRaises(autonomy.AutonomyError):
            autonomy.set_status(self.make_run(), "published")

    def test_lower_only_from_paused_autonomous_and_raise_refused(self) -> None:
        record = self.make_run()
        with self.assertRaisesRegex(autonomy.AutonomyError, "paused"):
            autonomy.change_mode(record, "human-gated", reason="x", decision_id=None)
        autonomy.set_status(record, "stopped")
        before = json.dumps(record)
        with self.assertRaisesRegex(autonomy.AutonomyError, "raising"):
            autonomy.change_mode(record, "autonomous", reason="x", decision_id=None)
        self.assertEqual(json.dumps(record), before)
        autonomy.change_mode(record, "human-gated", reason="x", decision_id="HD-0001")
        self.assertEqual(autonomy.effective_mode(record), "human-gated")
        self.assertEqual(record["mode_history"][-1]["action"], "lower")
        with self.assertRaisesRegex(autonomy.AutonomyError, "raising"):
            autonomy.change_mode(record, "human-gated", reason="x", decision_id=None)

    def test_forged_history_is_refused(self) -> None:
        record = self.make_run()
        record["mode_history"].append(dict(record["mode_history"][0]))
        with self.assertRaisesRegex(autonomy.AutonomyError, "lower"):
            autonomy.validate_run(record, "run42")
        record = self.make_run()
        record["mode_history"][0]["mode"] = "human-gated"
        record["mode_history"].append(
            {**record["mode_history"][0], "mode": "autonomous", "action": "lower"}
        )
        with self.assertRaises(autonomy.AutonomyError):
            autonomy.validate_run(record, "run42")


class HashChainTests(AutonomyCase):
    """FR-013: logs are append-only and tamper-evident."""

    def entry(self, point: str = "scope", **extra: object) -> dict:
        return {"point": point, "decision": "accept", "summary": "s", **extra}

    def test_sequential_ids_and_chain(self) -> None:
        first = autonomy.append_decision(self.root, "run42", self.entry())
        second = autonomy.append_decision(self.root, "run42", self.entry("plan"))
        self.assertEqual((first["id"], second["id"]), ("PD-0001", "PD-0002"))
        self.assertEqual(first["prev"], "0" * 64)
        path = autonomy.run_dir(self.root, "run42") / "decisions.jsonl"
        line = path.read_bytes().splitlines(keepends=True)[0]
        self.assertEqual(second["prev"], hashlib.sha256(line).hexdigest())
        self.assertEqual(len(autonomy.read_decisions(self.root, "run42")), 2)

    def test_runner_owned_ids_are_ignored(self) -> None:
        entry = autonomy.append_decision(
            self.root, "run42", self.entry(id="PD-0099", prev="f" * 64)
        )
        self.assertEqual(entry["id"], "PD-0001")
        self.assertEqual(entry["prev"], "0" * 64)

    def test_edited_or_truncated_log_is_unreadable(self) -> None:
        autonomy.append_decision(self.root, "run42", self.entry())
        autonomy.append_decision(self.root, "run42", self.entry("plan"))
        path = autonomy.run_dir(self.root, "run42") / "decisions.jsonl"
        original = path.read_bytes()
        path.write_bytes(original.replace(b'"summary":"s"', b'"summary":"t"', 1))
        with self.assertRaisesRegex(autonomy.AutonomyError, "chain"):
            autonomy.read_decisions(self.root, "run42")
        path.write_bytes(original[:-1])
        with self.assertRaisesRegex(autonomy.AutonomyError, "newline"):
            autonomy.read_decisions(self.root, "run42")
        path.write_bytes(original.splitlines(keepends=True)[1])
        with self.assertRaisesRegex(autonomy.AutonomyError, "sequence"):
            autonomy.read_decisions(self.root, "run42")

    def test_supersedes_must_name_a_current_decision(self) -> None:
        autonomy.append_decision(self.root, "run42", self.entry("intent"))
        with self.assertRaisesRegex(autonomy.AutonomyError, "unknown"):
            autonomy.append_decision(
                self.root, "run42", self.entry("intent", supersedes="PD-0009")
            )
        autonomy.append_decision(
            self.root, "run42", self.entry("intent", supersedes="PD-0001")
        )
        with self.assertRaisesRegex(autonomy.AutonomyError, "already superseded"):
            autonomy.append_decision(
                self.root, "run42", self.entry("intent", supersedes="PD-0001")
            )
        entries = autonomy.read_decisions(self.root, "run42")
        self.assertEqual(
            [e["id"] for e in autonomy.current(entries, "intent")], ["PD-0002"]
        )

    def test_human_decisions_chain(self) -> None:
        entry = autonomy.append_human_decision(
            self.root, "run42", "merge-feedback", "https://x/review", resolves=None
        )
        self.assertEqual((entry["id"], entry["by"]), ("HD-0001", "operator"))
        with self.assertRaises(autonomy.AutonomyError):
            autonomy.append_human_decision(
                self.root, "run42", "approval", "x", resolves=None
            )
        with self.assertRaises(autonomy.AutonomyError):
            autonomy.append_human_decision(
                self.root, "run42", "merge-feedback", "", resolves=None
            )


class BlockRecordTests(AutonomyCase):
    """FR-022: one current block, earlier blocks kept, recovery commands only."""

    def test_block_replaces_and_keeps_history(self) -> None:
        first = autonomy.make_block("limit", "wall time exhausted", run_id="run42")
        autonomy.record_block(self.root, "run42", first)
        second = autonomy.make_block("forge", "push failed", run_id="run42")
        autonomy.record_block(self.root, "run42", second)
        self.assertEqual(autonomy.read_block(self.root, "run42")["category"], "forge")
        kept = (autonomy.run_dir(self.root, "run42") / "blocks.jsonl").read_text()
        self.assertEqual(json.loads(kept)["category"], "limit")
        self.assertEqual(second["command"], "ballast run publish run42")
        self.assertIn("ballast run continue run42", first["command"])

    def test_command_restricted_to_recovery(self) -> None:
        block = autonomy.make_block("limit", "x", run_id="run42")
        block["command"] = "rm -rf /"
        with self.assertRaisesRegex(autonomy.AutonomyError, "recovery command"):
            autonomy.validate_block(block)

    def test_no_trust_block(self) -> None:
        """DEC-0002: a changed trusted input is a launcher refusal, not a block."""
        self.assertNotIn("trust", autonomy.BLOCK_CATEGORIES)
        block = autonomy.make_block("limit", "x", run_id="run42")
        block["category"] = "trust"
        with self.assertRaisesRegex(autonomy.AutonomyError, "category"):
            autonomy.validate_block(block)

    def test_agent_block_draft_rules(self) -> None:
        good = {
            "category": "decision",
            "condition": "X or not X",
            "no_safe_default": "Both outcomes are irreversible",
            "options": [
                {"option": "Keep X", "consequence": "a"},
                {"option": "Drop X", "consequence": "b"},
            ],
            "recovery": "Pick one",
            "evidence": [f"{FEATURE}/spec.md"],
        }
        cleaned = autonomy.validate_block_draft(good)
        self.assertIn("No safe, reversible default", cleaned["condition"])
        for broken, reason in (
            ({**good, "options": good["options"][:1]}, "two options"),
            ({**good, "no_safe_default": ""}, "no_safe_default"),
            ({**good, "category": "limit"}, "category"),
            # DEC-0005: only the publisher reports a permission block.
            ({**good, "category": "permission"}, "category"),
            ({**good, "recovery": "approved by the human"}, "human approval"),
        ):
            with (
                self.subTest(reason=reason),
                self.assertRaisesRegex(autonomy.AutonomyError, reason),
            ):
                autonomy.validate_block_draft(broken)
        contradiction = {**good, "category": "contradiction"}
        del contradiction["no_safe_default"]
        autonomy.validate_block_draft(contradiction)


class PolicyTests(AutonomyCase):
    """FR-007, FR-020: the project table only narrows; limits are bounded."""

    def test_defaults_without_table(self) -> None:
        policy, defaults, warnings = self.policy()
        self.assertEqual(policy["risk"], ["R0", "R1", "R2"])
        self.assertEqual(policy["authorized_privileged_actions"], [])
        self.assertEqual((defaults, warnings), ({}, []))
        limits = autonomy.resolve_limits(defaults)
        self.assertEqual(
            (limits["wall_time_minutes"], limits["max_agent_steps"], limits["source"]),
            (240, 30, "default"),
        )

    def test_narrowing_and_ignored_widening(self) -> None:
        policy, _, warnings = self.policy(
            "[autonomous]\n"
            'risk = ["R0", "R1", "R3"]\n'
            'excluded_boundaries = ["Agent Authority"]\n'
            "authorized_privileged_actions = "
            '["secret provisioning", "deploy", "merge"]\n'
            "allow_epics = true\n"
        )
        self.assertEqual(policy["risk"], ["R0", "R1"])
        self.assertEqual(policy["excluded_boundaries"], ["agent authority"])
        self.assertEqual(
            policy["authorized_privileged_actions"], ["secret provisioning"]
        )
        self.assertIn(
            "ignored [autonomous] allow_epics: cannot widen eligibility", warnings
        )
        self.assertTrue(any("'R3'" in w for w in warnings))
        self.assertTrue(any("'deploy'" in w for w in warnings))
        self.assertTrue(any("'merge'" in w for w in warnings))

    def test_limit_precedence_and_ranges(self) -> None:
        _, defaults, _ = self.policy(
            "[autonomous]\nwall_time_minutes = 120\nmax_agent_steps = 24\n"
        )
        project = autonomy.resolve_limits(defaults)
        self.assertEqual(
            (project["wall_time_minutes"], project["source"]), (120, "project")
        )
        operator = autonomy.resolve_limits(defaults, wall_time=5)
        self.assertEqual(
            (
                operator["wall_time_minutes"],
                operator["max_agent_steps"],
                operator["source"],
            ),
            (5, 24, "operator"),
        )
        start = datetime(2026, 10, 3, 12, tzinfo=UTC)
        limits = autonomy.resolve_limits({}, wall_time=1, start=start)
        self.assertEqual(
            datetime.fromisoformat(limits["deadline"]), start + timedelta(minutes=1)
        )
        for table in (
            "wall_time_minutes = 0",
            "max_agent_steps = 201",
            "max_agent_steps = true",
        ):
            with self.subTest(table=table), self.assertRaises(autonomy.AutonomyError):
                self.policy(f"[autonomous]\n{table}\n")
        for bad in ((0, None), (1441, None), (None, 0), (None, 201)):
            with self.subTest(bad=bad), self.assertRaises(autonomy.AutonomyError):
                autonomy.resolve_limits({}, *bad)

    def test_checks_table(self) -> None:
        import tomllib  # noqa: PLC0415

        checks = autonomy.parse_checks(
            tomllib.loads('[checks]\ncommands = ["a", "b"]\n')
        )
        self.assertEqual(checks, {"commands": ["a", "b"], "timeout_minutes": 30})
        for table in ("", "[checks]\n", "[checks]\ncommands = []\n"):
            with (
                self.subTest(table=table),
                self.assertRaisesRegex(autonomy.AutonomyError, r"\[checks\]"),
            ):
                autonomy.parse_checks(tomllib.loads(table))
        with self.assertRaises(autonomy.AutonomyError):
            autonomy.parse_checks(
                tomllib.loads('[checks]\ncommands = ["a"]\ntimeout_minutes = 241\n')
            )


class GitHelperTests(AutonomyCase):
    """Hardened Git, tree digests and the configuration scans."""

    def test_digest_ignores_protected_inputs_and_exclusions(self) -> None:
        before = autonomy.tree_digest(self.root)
        (self.root / "ballast.toml").write_text("changed = true\n")
        (self.root / ".specify/new.txt").write_text("x")
        self.assertEqual(autonomy.tree_digest(self.root), before)
        (self.root / FEATURE).mkdir(parents=True)
        (self.root / FEATURE / "spec.md").write_text("spec")
        self.assertNotEqual(autonomy.tree_digest(self.root), before)
        self.assertEqual(autonomy.tree_digest(self.root, (FEATURE,)), before)
        self.assertEqual(self.git("status", "--porcelain", "--", "README.md"), "")
        self.assertNotIn("spec.md", self.git("diff", "--cached", "--name-only"))

    def test_digest_with_git_ignored_protected_inputs(self) -> None:
        """An installed project ignores .ballast/ and most of .specify/."""
        before = autonomy.tree_digest(self.root)
        (self.root / ".gitignore").write_text(".ballast/\n.specify/*\n.venv/\n")
        (self.root / ".ballast/spec_workflow").mkdir(parents=True)
        (self.root / ".ballast/spec_workflow/run.py").write_text("x")
        (self.root / ".venv").mkdir()
        self.git("add", ".gitignore")
        self.git("commit", "-q", "-m", "ignore installed paths")
        digest = autonomy.tree_digest(self.root, (f"{FEATURE}/reviews",))
        self.assertNotEqual(digest, before)
        (self.root / ".ballast/spec_workflow/run.py").write_text("y")
        self.assertEqual(
            autonomy.tree_digest(self.root, (f"{FEATURE}/reviews",)), digest
        )

    def test_no_filter_runs_in_operator_git(self) -> None:
        """Review F2: an agent-added .gitattributes never runs a filter driver."""
        marker = self.base / "filter-ran"
        with Path(os.environ["GIT_CONFIG_GLOBAL"]).open("a") as config:
            config.write(
                f'[filter "Evil"]\n\tclean = "touch {marker}; cat"\n'
                f"\tsmudge = cat\n\trequired = true\n"
                f'[filter "proc"]\n\tprocess = "touch {marker}"\n'
            )
        before = autonomy.tree_digest(self.root)
        for driver in ("Evil", "proc"):
            with self.subTest(driver=driver):
                (self.root / ".gitattributes").write_text(f"* filter={driver}\n")
                (self.root / "new.txt").write_text(driver)
                self.assertNotEqual(autonomy.tree_digest(self.root), before)
                autonomy.checked_digest(self.root, FEATURE)
                autonomy.git(self.root, "add", "--all")
                autonomy.git(self.root, "status", "--porcelain")
                autonomy.git(self.root, "reset", "-q")
                artifacts.worktree_tree(self.root)
                ledger.implementation_tree(self.root)
                self.assertFalse(marker.exists())

    def test_hooks_never_run(self) -> None:
        marker = self.base / "hook-ran"
        hook = self.root / ".git/hooks/pre-commit"
        hook.write_text(f"#!/bin/sh\ntouch {marker}\n")
        hook.chmod(0o755)
        (self.root / "x.txt").write_text("x")
        autonomy.git(self.root, "add", "x.txt")
        autonomy.git(self.root, "commit", "-q", "-m", "x")
        self.assertFalse(marker.exists())

    def test_credential_findings(self) -> None:
        self.assertEqual(autonomy.credential_findings(self.root), [])
        self.git(
            "remote", "set-url", "origin", "https://user:secret@example.test/r.git"
        )
        self.git("config", "http.https://example.test/.extraheader", "AUTH: x")
        findings = autonomy.credential_findings(self.root)
        self.assertTrue(any("remote.origin.url" in f for f in findings))
        self.assertTrue(any("extraheader" in f for f in findings))
        self.assertFalse(any("secret" in f for f in findings))

    def test_program_findings_inside_checkout(self) -> None:
        self.assertEqual(autonomy.program_findings(self.root), [])
        self.git("config", "core.sshCommand", str(self.root / "evil.sh"))
        self.git("config", "credential.helper", "store")
        self.git("config", "include.path", "../extra.cfg")
        findings = autonomy.program_findings(self.root)
        self.assertTrue(any("core.sshcommand" in f for f in findings))
        self.assertFalse(any("credential.helper" in f for f in findings))
        self.assertTrue(any("include.path" in f for f in findings))

    def test_attribute_drivers_only_when_configured(self) -> None:
        (self.root / ".gitattributes").write_text("*.bin filter=lfs diff=lfs\n")
        self.assertEqual(autonomy.attribute_drivers(self.root), [])
        self.git("config", "filter.lfs.clean", "git-lfs clean -- %f")
        self.assertEqual(autonomy.attribute_drivers(self.root), ["filter=lfs"])

    def test_config_snapshot_tracks_local_config_and_hooks(self) -> None:
        before = autonomy.config_snapshot(self.root)
        self.assertEqual(autonomy.config_snapshot(self.root), before)
        self.git("config", "gpg.program", "/usr/bin/gpg")
        self.assertNotEqual(autonomy.config_snapshot(self.root), before)
        after = autonomy.config_snapshot(self.root)
        (self.root / ".git/hooks/post-checkout").write_text("#!/bin/sh\n")
        self.assertNotEqual(autonomy.config_snapshot(self.root), after)


class ConfinementTests(AutonomyCase):
    """AC-016, SC-005: agent steps run under a read-only host."""

    def setUp(self) -> None:
        super().setUp()
        # These tests inspect the argv and never run bwrap; CI has none, so
        # give the trusted resolver a stand-in when no real copy exists.
        if autonomy.trusted_program("bwrap", self.root)[0] is None:
            _install(Path("/bin/true"), self.bin / "bwrap")

    def argv(self, home: Path | None = None) -> list[str]:
        private = self.base / "private"
        private.mkdir(exist_ok=True)
        return autonomy.confined_argv(
            self.root,
            ["true"],
            private=private,
            feature=FEATURE,
            home=home or self.base / "home",
            env={"XDG_RUNTIME_DIR": "/run/user/1000"},
        )

    def test_resolver_files_hidden_by_a_tmpfs_are_bound_back(self) -> None:
        """systemd-resolved: /etc/resolv.conf links into the hidden /run."""
        hidden = self.base / "run"
        (hidden / "systemd/resolve").mkdir(parents=True)
        stub = hidden / "systemd/resolve/stub-resolv.conf"
        stub.write_text("nameserver 127.0.0.53\n")
        etc = self.base / "etc"
        etc.mkdir()
        (etc / "resolv.conf").symlink_to(stub)
        (etc / "hosts").write_text("127.0.0.1 localhost\n")
        (etc / "nsswitch.conf").symlink_to(hidden)  # a directory: never bound
        files = tuple(etc / name for name in ("resolv.conf", "hosts", "nsswitch.conf"))
        with (
            patch.object(autonomy, "RESOLVER_FILES", files),
            patch.object(autonomy, "TMPFS_HIDDEN", (hidden,)),
        ):
            argv = self.argv()
        triples = list(zip(argv, argv[1:], argv[2:], strict=False))
        bind = ("--ro-bind", str(stub), str(stub))
        self.assertIn(bind, triples)
        # After the tmpfs that hides it, and nothing else of the hidden tree.
        self.assertGreater(triples.index(bind), argv.index("/run"))
        sources = [argv[i + 1] for i, a in enumerate(argv) if a == "--ro-bind"]
        self.assertNotIn(str(hidden), sources)
        self.assertNotIn(str(etc / "hosts"), sources)
        self.assertEqual([s for s in sources if s.startswith(str(hidden))], [str(stub)])

    def test_argv_shape(self) -> None:
        home = self.base / "home"
        for name in (".claude", ".codex", ".cache", ".config", ".ssh"):
            (home / name).mkdir(parents=True)
        (home / ".claude.json").write_text("{}")
        (home / ".netrc").write_text("machine x")
        (self.root / ".ballast").mkdir()
        argv = self.argv(home)
        joined = " ".join(argv)
        self.assertEqual(argv[1:4], ["--ro-bind", "/", "/"])
        self.assertIn(f"--bind {self.root} {self.root}", joined)
        for name in ("ballast.toml", ".ballast", ".specify", ".git"):
            path = self.root / name
            self.assertIn(f"--ro-bind {path} {path}", joined)
        feature_json = self.root / ".specify/feature.json"
        self.assertIn(f"--bind {feature_json} {feature_json}", joined)
        self.assertEqual(
            json.loads(feature_json.read_text()), {"feature_directory": FEATURE}
        )
        self.assertLess(
            joined.index(f"--ro-bind {self.root / '.specify'}"),
            joined.index(f"--bind {feature_json}"),
        )
        for flag in (
            "--unshare-pid",
            "--unshare-ipc",
            "--new-session",
            "--die-with-parent",
        ):
            self.assertIn(flag, argv)
        self.assertIn("--tmpfs /run/user/1000", joined)
        self.assertIn(f"--tmp-overlay {home / '.claude'}", joined)
        self.assertIn(f"--tmpfs {home / '.config'}", joined)
        self.assertGreater(
            joined.index(f"--remount-ro {home / '.config'}"),
            joined.index(f"--tmp-overlay {home / '.codex'}"),
        )
        self.assertIn(f"--ro-bind /dev/null {home / '.netrc'}", joined)
        self.assertIn(
            f"{self.base / 'private/claude.json'} {home / '.claude.json'}", joined
        )
        self.assertEqual(argv[-2:], ["--", "true"])

    def test_secret_variables_removed_except_integration_key(self) -> None:
        env = {
            "GH_TOKEN": "t",
            "GITHUB_TOKEN": "t",
            "AWS_SECRET_ACCESS_KEY": "s",
            "SSH_AUTH_SOCK": "/s",
            "ANTHROPIC_API_KEY": "a",
            "OPENAI_API_KEY": "o",
            "HOME": "/h",
            "PATH": "/p",
        }
        self.assertEqual(
            autonomy.confined_env(env, "claude"),
            {"ANTHROPIC_API_KEY": "a", "HOME": "/h", "PATH": "/p"},
        )
        self.assertEqual(
            autonomy.confined_env(env, "codex"),
            {"OPENAI_API_KEY": "o", "HOME": "/h", "PATH": "/p"},
        )

    def test_custom_gh_and_xdg_config_locations_are_hidden(self) -> None:
        """Review F1: GH_CONFIG_DIR and XDG_CONFIG_HOME are cleared and hidden."""
        gh = self.base / "elsewhere/gh"
        xdg = self.base / "elsewhere/xdg"
        for path in (gh, xdg / "gh"):
            path.mkdir(parents=True)
            (path / "hosts.yml").write_text("oauth_token: secret\n")
        env = {"GH_CONFIG_DIR": str(gh), "XDG_CONFIG_HOME": str(xdg), "PATH": "/p"}
        self.assertEqual(autonomy.confined_env(env, "claude"), {"PATH": "/p"})
        private = self.base / "private"
        private.mkdir()
        joined = " ".join(
            autonomy.confined_argv(
                self.root, ["true"], private=private, env=env, home=self.base / "h"
            )
        )
        for path in (gh, xdg):
            self.assertIn(f"--tmpfs {path}", joined)
            self.assertIn(f"--remount-ro {path}", joined)

    def plant_bwrap(self, directory: Path) -> Path:
        marker = self.base / "planted-ran"
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "bwrap").write_text(f"#!/bin/sh\ntouch {marker}\nexit 0\n")
        (directory / "bwrap").chmod(0o755)
        return marker

    def test_planted_bwrap_is_never_used(self) -> None:
        """Fable-3: bwrap resolves like gh and git (ADR-0003)."""
        _install(Path("/bin/true"), self.bin / "bwrap")
        for planted, roots in (
            (self.root / ".git/planted-bin", ()),
            (self.base / "temp-root/bin", (self.base / "temp-root",)),
        ):
            with self.subTest(planted=planted):
                self.plant_bwrap(planted)
                os.environ["PATH"] = f"{planted}{os.pathsep}{self.env['PATH']}"
                with patch.object(ledger, "agent_temp_roots", lambda r=roots: r):
                    self.assertEqual(self.argv()[0], str(self.bin / "bwrap"))

    def test_only_an_untrusted_bwrap_refuses_and_never_runs(self) -> None:
        planted = self.root / ".git/planted-bin"
        marker = self.plant_bwrap(planted)
        system = self.base / "system-bin"  # git and python3, never a bwrap
        system.mkdir()
        for name in ("git", "python3"):
            (system / name).symlink_to(shutil.which(name, path=self.real_path) or "")
        os.environ["PATH"] = f"{planted}{os.pathsep}{system}"
        with (
            patch.object(autonomy.shutil, "which", return_value=None),
            self.assertRaisesRegex(autonomy.AutonomyError, "outside working trees"),
        ):
            autonomy.confinement_self_test(self.root)
        self.assertFalse(marker.exists())

    def test_missing_bwrap_fails_closed(self) -> None:
        which = shutil.which

        def no_bwrap(name: str, *args: object, **kwargs: object) -> str | None:
            return None if name == "bwrap" else which(name, *args, **kwargs)

        trusted = autonomy.trusted_program

        def no_trusted_bwrap(name: str, root: Path) -> tuple[str | None, bool]:
            return (None, False) if name == "bwrap" else trusted(name, root)

        with (
            patch.object(autonomy.shutil, "which", side_effect=no_bwrap),
            patch.object(autonomy, "trusted_program", side_effect=no_trusted_bwrap),
            self.assertRaisesRegex(autonomy.AutonomyError, "bwrap not found") as raised,
        ):
            autonomy.confinement_self_test(self.root)
        self.assertEqual(raised.exception.category, "ineligible")

    def test_escaping_probe_fails_closed(self) -> None:
        fake = self.bin / "bwrap"
        fake.write_text(
            "#!/usr/bin/env python3\nimport os, sys\n"
            "args = sys.argv[1:]\ncommand = args[args.index('--') + 1:]\n"
            "os.execvp(command[0], command)\n"
        )
        fake.chmod(0o755)
        with self.assertRaisesRegex(autonomy.AutonomyError, "self-test reached"):
            autonomy.confinement_self_test(self.root)


@unittest.skipUnless(_bwrap_works(), "needs bwrap with user namespaces")
class RealConfinementTests(AutonomyCase):
    """Probes from inside a real bubblewrap sandbox."""

    def confined(
        self, *command: str, root: Path | None = None
    ) -> subprocess.CompletedProcess[str]:
        root = root or self.root
        private = self.base / "private"
        private.mkdir(exist_ok=True)
        env = autonomy.confined_env(dict(os.environ), None)
        env["PATH"] = self.real_path
        argv = autonomy.confined_argv(
            root, list(command), private=private, feature=FEATURE, env=env
        )
        return subprocess.run(  # noqa: S603
            argv, capture_output=True, text=True, check=False, env=env, timeout=60
        )

    def write(self, target: Path, root: Path | None = None) -> int:
        code = f"open({str(target)!r}, 'w').write('x')"
        return self.confined("python3", "-I", "-S", "-c", code, root=root).returncode

    def test_self_test_passes(self) -> None:
        autonomy.confinement_self_test(self.root)

    def test_dns_resolves_inside_when_it_does_outside(self) -> None:
        """Agent steps keep the host network and its resolver configuration."""
        host = "api.anthropic.com"
        try:
            socket.getaddrinfo(host, 443)
        except OSError:
            self.skipTest("no DNS resolution on this host")
        code = f"import socket; socket.getaddrinfo({host!r}, 443)"
        result = self.confined("python3", "-I", "-S", "-c", code)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_protected_and_operator_paths_are_read_only(self) -> None:
        (self.root / ".specify/workflows").mkdir()
        self.assertEqual(self.write(self.root / "notes.txt"), 0)
        self.assertEqual(self.write(self.root / ".specify/feature.json"), 0)
        for target in (
            self.root / ".specify/workflows/x.yml",
            self.root / "ballast.toml",
            self.root / ".git/config",
            self.root / ".git/hooks/pre-commit",
            Path.home() / ".ballast-probe",
        ):
            with self.subTest(target=target):
                self.assertNotEqual(self.write(target), 0)
        self.assertEqual((self.root / ".specify/feature.json").read_text(), "x")
        self.assertFalse((self.root / ".specify/workflows/x.yml").exists())

    def test_linked_worktree_git_directory_is_read_only(self) -> None:
        linked = self.base / "linked"
        self.git("worktree", "add", "-q", str(linked), "-b", "27-linked")
        self.assertEqual(self.write(linked / "ok.txt", root=linked), 0)
        self.assertNotEqual(self.write(self.root / ".git/probe", root=linked), 0)
        result = self.confined("git", "status", "--porcelain", root=linked)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_agent_home_writes_do_not_persist(self) -> None:
        claude = autonomy.agent_homes(Path.home(), dict(os.environ))[0]
        if not claude.is_dir():
            self.skipTest("no ~/.claude on this host")
        probe = claude / ".ballast-persist-probe"
        self.assertEqual(self.write(probe), 0)
        self.assertFalse(probe.exists())

    def test_operator_processes_bus_and_credentials_unreachable(self) -> None:
        code = (
            "import json, os, subprocess, sys\n"
            "home = os.path.expanduser('~')\n"
            "out = {}\n"
            "runtime = os.environ.get('XDG_RUNTIME_DIR')\n"
            "out['runtime'] = (\n"
            "    os.listdir(runtime) if runtime and os.path.isdir(runtime) else []\n"
            ")\n"
            f"out['environ'] = os.path.exists('/proc/{os.getpid()}/environ')\n"
            "readable = []\n"
            "names = ('.git-credentials', '.netrc', '.ssh', '.config/gh/hosts.yml')\n"
            "for name in names:\n"
            "    path = os.path.join(home, name)\n"
            "    try:\n"
            "        if os.path.isdir(path):\n"
            "            if os.listdir(path): readable.append(name)\n"
            "        elif open(path).read(): readable.append(name)\n"
            "    except OSError: pass\n"
            "out['readable'] = readable\n"
            "out['secrets'] = sorted(\n"
            "    k for k in os.environ if 'TOKEN' in k or 'SECRET' in k\n"
            ")\n"
            "print(json.dumps(out))\n"
        )
        result = self.confined("python3", "-I", "-S", "-c", code)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["runtime"], [])
        self.assertFalse(report["environ"])
        self.assertEqual(report["readable"], [])
        self.assertEqual(report["secrets"], [])
        if shutil.which("systemd-run", path=self.real_path):
            self.assertNotEqual(
                self.confined("systemd-run", "--user", "--quiet", "true").returncode, 0
            )
        real_gh = shutil.which("gh", path=self.real_path)
        if real_gh:
            self.assertNotEqual(self.confined(real_gh, "auth", "status").returncode, 0)
        fill = self.confined(
            "sh",
            "-c",
            "printf 'protocol=https\\nhost=github.com\\n\\n' | "
            "GIT_TERMINAL_PROMPT=0 git credential fill",
        )
        self.assertNotIn("password=", fill.stdout)

    def test_custom_gh_and_xdg_config_locations_unreadable(self) -> None:
        """Review F1, under real bwrap: custom credential locations stay hidden.

        /var/tmp, unlike /tmp, is not emptied by the sandbox, so only the
        hiding of the configured directories keeps the files out of reach.
        """
        if not os.access("/var/tmp", os.W_OK):  # noqa: S108
            self.skipTest("needs a writable /var/tmp")
        outside = Path(self.enterContext(TemporaryDirectory(dir="/var/tmp")))
        gh = outside / "gh"
        xdg = outside / "xdg"
        for path in (gh, xdg / "gh"):
            path.mkdir(parents=True)
            (path / "hosts.yml").write_text("oauth_token: secret\n")
        env = {
            **os.environ,
            "PATH": self.real_path,
            "GH_CONFIG_DIR": str(gh),
            "XDG_CONFIG_HOME": str(xdg),
        }
        private = self.base / "private"
        private.mkdir(exist_ok=True)
        script = 'echo "${GH_CONFIG_DIR-unset} ${XDG_CONFIG_HOME-unset}"; cat "$0" "$1"'
        files = [str(gh / "hosts.yml"), str(xdg / "gh/hosts.yml")]
        argv = autonomy.confined_argv(
            self.root,
            ["sh", "-c", script, *files],
            private=private,
            feature=FEATURE,
            env=env,
        )
        result = subprocess.run(  # noqa: S603
            argv,
            capture_output=True,
            text=True,
            check=False,
            env=autonomy.confined_env(env, None),
            timeout=60,
        )
        self.assertEqual(result.stdout.splitlines()[0], "unset unset")
        self.assertNotIn("oauth_token", result.stdout)
        self.assertNotEqual(result.returncode, 0)


class EligibilityTests(AutonomyCase):
    """AC-018 to AC-021, FR-005, FR-006, FR-008: refusals before any agent step."""

    def check(self, table: str = "", **kwargs: object) -> dict:
        policy, _, warnings = self.policy(table)
        return autonomy.check_eligibility(
            self.root,
            issue=ISSUE,
            feature=kwargs.pop("feature", FEATURE),
            policy=policy,
            warnings=warnings,
            self_test=False,
        )

    def reasons(self, table: str = "", **kwargs: object) -> list[str]:
        return self.check(table, **kwargs)["eligibility"]["reasons"]

    def test_eligible_risk_levels_are_recorded(self) -> None:
        for level in ("R0", "R1", "R2"):
            with self.subTest(level=level):
                self.eligible_issue(risk=level, extra="R2 boundaries: Agent Authority")
                result = self.check()
                self.assertTrue(result["eligibility"]["eligible"], result)
                self.assertEqual(result["risk"]["level"], level)
                self.assertEqual(result["risk"]["boundaries"], ["agent authority"])
                self.assertEqual(result["repo"], "acme/demo")

    def test_scope_gate_refusals(self) -> None:
        cases = {
            "epic": {"labels": ("ready-for-agent", "epic")},
            "closed": {"state": "closed"},
        }
        for name, kwargs in cases.items():
            with self.subTest(name=name):
                self.eligible_issue(**kwargs)
                reasons = self.reasons()
                self.assertTrue(
                    any(
                        r.startswith(autonomy.REFUSAL + "scope gate:") for r in reasons
                    ),
                    reasons,
                )
        self.eligible_issue()
        self.gh_data(
            f"repos_acme_demo_issues_{ISSUE}_sub_issues.json", [{"number": 30}]
        )
        self.assertTrue(any("Epic or has sub-issues" in r for r in self.reasons()))
        self.eligible_issue()
        self.gh_data(
            f"repos_acme_demo_issues_{ISSUE}_dependencies_blocked_by.json",
            [{"number": 12, "state": "open"}],
        )
        self.assertTrue(any("blocked by #12" in r for r in self.reasons()))

    def test_missing_scope_record(self) -> None:
        for kwargs in ({"labels": ()}, {"author": "NONE"}):
            with self.subTest(kwargs=kwargs):
                self.eligible_issue(**kwargs)
                self.assertIn(
                    autonomy.REFUSAL + "issue has no recorded scope gate",
                    self.reasons(),
                )
        self.eligible_issue()
        self.gh_data(f"repos_acme_demo_issues_{ISSUE}_comments.json", [])
        self.assertIn(
            autonomy.REFUSAL + "issue has no recorded scope gate", self.reasons()
        )

    def test_missing_privileged_actions_line(self) -> None:
        self.eligible_issue()
        comment = SCOPE.format(risk="R1", actions="none", extra="").replace(
            "Privileged actions before merge: none\n", ""
        )
        self.gh_data(
            f"repos_acme_demo_issues_{ISSUE}_comments.json",
            [{"body": comment, "author_association": "OWNER"}],
        )
        self.assertIn(
            autonomy.REFUSAL + "scope record lacks Privileged actions before merge:",
            self.reasons(),
        )

    def test_privileged_actions(self) -> None:
        self.eligible_issue(actions="secret provisioning")
        self.assertIn(
            autonomy.REFUSAL + "privileged action secret provisioning before merge",
            self.reasons(),
        )
        table = (
            '[autonomous]\nauthorized_privileged_actions = ["secret provisioning"]\n'
        )
        self.assertEqual(self.reasons(table), [])
        self.eligible_issue(actions="deploy")
        self.assertIn(
            autonomy.REFUSAL + "privileged action deploy before merge",
            self.reasons('[autonomous]\nauthorized_privileged_actions = ["deploy"]\n'),
        )

    def test_narrowed_risk_and_boundary(self) -> None:
        self.eligible_issue(risk="R2", extra="R2 boundaries: agent authority")
        self.assertIn(
            autonomy.REFUSAL + "risk R2 excluded by ballast.toml [autonomous]",
            self.reasons('[autonomous]\nrisk = ["R0", "R1"]\n'),
        )
        self.assertIn(
            autonomy.REFUSAL + "boundary agent authority excluded by ballast.toml "
            "[autonomous]",
            self.reasons('[autonomous]\nexcluded_boundaries = ["agent authority"]\n'),
        )

    def test_widening_key_is_ignored_with_warning(self) -> None:
        self.eligible_issue()
        result = self.check("[autonomous]\nallow_epics = true\n")
        self.assertTrue(result["eligibility"]["eligible"])
        self.assertEqual(
            result["eligibility"]["ignored_policy"],
            ["ignored [autonomous] allow_epics: cannot widen eligibility"],
        )

    def test_branch_feature_and_credentials(self) -> None:
        self.eligible_issue()
        self.assertTrue(
            any(
                "other issue" in r or "is not for issue" in r
                for r in self.reasons(feature="specs/28-other")
            )
        )
        self.gh_data("pr-list.json", [{"number": 3}])
        self.assertIn(autonomy.REFUSAL + autonomy.BRANCH_REFUSAL, self.reasons())
        (self.gh_dir / "pr-list.json").unlink()
        self.git("checkout", "-q", "main")
        self.assertIn(autonomy.REFUSAL + autonomy.BRANCH_REFUSAL, self.reasons())
        # N-05: the same predicate as branch synchronization (Q44).
        for name in ("develop", "feat/270-x"):
            self.git("checkout", "-q", "-b", name, "27-demo-run")
            self.assertIn(autonomy.REFUSAL + autonomy.BRANCH_REFUSAL, self.reasons())
        self.assertIn("named for the Issue", autonomy.BRANCH_REFUSAL)
        self.git("checkout", "-q", "27-demo-run")
        self.git("remote", "set-url", "origin", "https://u:token@example.test/r.git")
        self.assertTrue(any("carries a credential" in r for r in self.reasons()))

    def test_gh_failure_fails_closed(self) -> None:
        self.eligible_issue()
        (self.gh_dir / "FAIL_api").write_text("")
        with self.assertRaisesRegex(
            autonomy.AutonomyError, "^cannot check autonomous eligibility: "
        ):
            self.check()

    def test_confinement_failure_refuses(self) -> None:
        self.eligible_issue()
        policy, _, warnings = self.policy()
        with patch.object(
            autonomy,
            "confinement_self_test",
            side_effect=autonomy.AutonomyError("confinement unavailable: x"),
        ):
            result = autonomy.check_eligibility(
                self.root,
                issue=ISSUE,
                feature=FEATURE,
                policy=policy,
                warnings=warnings,
            )
        self.assertIn(
            autonomy.REFUSAL + "confinement unavailable: x",
            result["eligibility"]["reasons"],
        )


class FeatureBranchTests(unittest.TestCase):
    """T009 [FR-005, AC-021, DEC-0004, N-05]: the one feature-branch predicate."""

    def test_issue_number_as_a_whole_segment(self) -> None:
        for name in ("feat/18-branch-sync", "18-branch-sync", "fix_18.x", "a/b/18"):
            with self.subTest(name=name):
                self.assertTrue(autonomy.is_feature_branch(name, 18, "main", "main"))

    def test_everything_else_is_not_a_feature_branch(self) -> None:
        cases = {
            "feat/180-x": (18, "main", "main"),
            "v18": (18, "main", "main"),
            "feat/018-x": (18, "main", "main"),
            "develop": (18, "main", "main"),
            "18-base": (18, "18-base", "main"),
            "18-default": (18, "release", "18-default"),
            "feat/18-x": (None, "main", "main"),
            "": (18, "main", "main"),
        }
        for name, (issue, base, default) in cases.items():
            with self.subTest(name=name):
                self.assertFalse(autonomy.is_feature_branch(name, issue, base, default))


class IssueSnapshotTests(AutonomyCase):
    """DEC-0008: the runner's Issue snapshot for agents."""

    ISSUE: ClassVar[dict] = {
        "number": 27,
        "title": "Demo run",
        "body": "## Acceptance criteria\n\n- works\n",
        "labels": [{"name": "ready-for-agent"}],
    }

    def test_renders_body_labels_and_scope_as_untrusted_data(self) -> None:
        text = autonomy.render_issue_snapshot(self.ISSUE, "Risk: R1\n")
        self.assertIn("Untrusted Issue data", text)
        self.assertIn("# Issue #27: Demo run", text)
        self.assertIn("Labels: ready-for-agent", text)
        self.assertIn("## Acceptance criteria\n\n- works", text)
        self.assertIn("Risk: R1", text)

    def test_long_body_is_capped_with_a_marker(self) -> None:
        issue = self.ISSUE | {"body": "x" * (autonomy.ISSUE_SNAPSHOT_LIMIT * 2)}
        text = autonomy.render_issue_snapshot(issue, "y" * 100_000)
        self.assertLessEqual(len(text), autonomy.ISSUE_SNAPSHOT_LIMIT)
        self.assertIn("[truncated by Ballast]", text)

    def test_snapshot_never_writes_through_a_symlinked_directory(self) -> None:
        elsewhere = self.base / "elsewhere"
        elsewhere.mkdir()
        state = self.root / ".specify/workflow-state"
        state.symlink_to(elsewhere)
        with self.assertRaisesRegex(autonomy.AutonomyError, "symlink"):
            autonomy.write_issue_snapshot(self.root, self.ISSUE, "")
        self.assertEqual(list(elsewhere.iterdir()), [])

    def test_snapshot_never_follows_a_symlink(self) -> None:
        target = self.base / "elsewhere.md"
        issues = self.root / ".specify/workflow-state/issues"
        issues.mkdir(parents=True)
        (issues / "27.md").symlink_to(target)
        path = autonomy.write_issue_snapshot(self.root, self.ISSUE, "")
        self.assertFalse(target.exists())
        self.assertFalse(path.is_symlink())
        self.assertIn("- works", path.read_text())


class FeatureJsonTests(AutonomyCase):
    """The run's feature directory for Spec Kit's scripts."""

    def test_replaces_another_feature(self) -> None:
        path = self.root / ".specify/feature.json"
        path.write_text('{"feature_directory": "specs/1-other"}\n')
        autonomy.write_feature_json(self.root, FEATURE)
        self.assertEqual(json.loads(path.read_text()), {"feature_directory": FEATURE})

    def test_never_writes_through_a_symlink(self) -> None:
        target = self.base / "elsewhere.json"
        target.write_text("{}\n")
        path = self.root / ".specify/feature.json"
        path.symlink_to(target)
        autonomy.write_feature_json(self.root, FEATURE)
        self.assertEqual(target.read_text(), "{}\n")
        self.assertFalse(path.is_symlink())
        self.assertEqual(json.loads(path.read_text()), {"feature_directory": FEATURE})


class EffectiveConfigTests(AutonomyCase):
    """Implementation review fable-3: a failed listing is never an empty one."""

    def test_failed_listing_raises(self) -> None:
        (self.root / ".git/config").write_text("[broken\n")
        with self.assertRaises(autonomy.AutonomyError):
            autonomy.effective_config(self.root)


class RecordRenderTests(unittest.TestCase):
    """FR-014, FR-025, AC-006, AC-007, SC-003, SC-006: deterministic projections."""

    def assertGolden(self, name: str, text: str) -> None:  # noqa: N802
        path = FIXTURES / name
        if UPDATE_GOLDEN or not path.exists():
            # First generation or a deliberate update: review the diff.
            path.write_text(text)
        self.assertEqual(text, path.read_text(), name)

    def body(self, run: dict, decisions: list[dict]) -> str:
        return autonomy.render_pr_body(
            run,
            decisions,
            GOLDEN_CHECKS,
            [f"{FEATURE}/spec.md", "src/demo.py"],
            repo="acme/demo",
            branch="27-demo-run",
        )

    def check_wording(self, text: str, decisions: list[dict]) -> None:
        self.assertIsNone(autonomy.HUMAN_APPROVAL.search(text))
        self.assertNotIn("<!--", text)
        self.assertNotIn("@someone", text)
        self.assertNotIn("@team", text)
        rows = [line for line in text.splitlines() if line.startswith("| PD-")]
        self.assertEqual(len(rows), len(decisions))
        for row in rows:
            self.assertIn("agent-provisional", row)

    def test_goldens(self) -> None:
        for name, run, decisions in (
            ("cross-provider-r1", fixed_run(), golden_decisions()),
            (
                "single-provider-r1",
                fixed_run(cross=False),
                golden_decisions(cross=False),
            ),
            ("r2", fixed_run(risk="R2"), golden_decisions()),
        ):
            with self.subTest(name=name):
                record = autonomy.render_record(run, decisions, GOLDEN_CHECKS)
                self.assertEqual(
                    record, autonomy.render_record(run, decisions, GOLDEN_CHECKS)
                )
                self.assertGolden(f"record-{name}.md", record)
                body = self.body(run, decisions)
                self.assertGolden(f"pr-body-{name}.md", body)
                self.check_wording(record, decisions)
                self.check_wording(body, decisions)
                self.assertIn("Refs #27", body)
                self.assertNotIn("Closes", body)
                self.assertTrue(body.startswith("Autonomous run gold01 for #27"))

    def test_sections_and_markers(self) -> None:
        decisions = golden_decisions()
        record = autonomy.render_record(fixed_run(), decisions, None)
        self.assertIn("- run-checks: not run yet", record)
        # Plan review: checks see git-ignored files that the PR does not carry.
        self.assertIn(autonomy.IGNORED_FILES_NOTE, record)
        self.assertIn("- PD-0007 (decision-resolution, agent-provisional)", record)
        self.assertIn("| PD-0002 | intent |", record)
        self.assertIn("| PD-0008 |", record)
        self.assertRegex(record, r"\| PD-0002 .*\| PD-0008 \|")
        self.assertIn("Intent \\| accepted @\u200bteam", record)
        self.assertIn("F-001 (medium, missing-test, accepted-provisionally)", record)
        self.assertNotIn("Reduced independence", record)
        single = autonomy.render_record(
            fixed_run(cross=False), golden_decisions(cross=False), None
        )
        self.assertIn(
            "Reduced independence: reviews used the authoring provider.", single
        )

    def test_r2_notice_only_for_r2(self) -> None:
        notice = "This is an R2 change. It was made without any prior human approval"
        r2 = autonomy.render_record(fixed_run(risk="R2"), golden_decisions(), None)
        self.assertIn(notice, r2)
        self.assertIn("pre-change approval was agent-provisional (PD-0005)", r2)
        self.assertIn("- agent authority\n- trust model", r2)
        for level in ("R0", "R1"):
            run = fixed_run(risk=level)
            self.assertNotIn(
                notice, autonomy.render_record(run, golden_decisions(), None)
            )
            self.assertNotIn(notice, self.body(run, golden_decisions()))
        self.assertIn(notice, self.body(fixed_run(risk="R2"), golden_decisions()))

    def test_long_body_falls_back_to_short_rows(self) -> None:
        decisions = [
            fixed_decision(n, "clarification", summary="s" * 400) for n in range(1, 120)
        ]
        for entry in decisions:
            entry["basis"] = "b" * 1800
        body = self.body(fixed_run(), decisions)
        self.assertLessEqual(len(body), autonomy.MAX_BODY)
        self.assertIn("Full decision rows:", body)
        self.assertEqual(
            len([row for row in body.splitlines() if row.startswith("| PD-")]), 119
        )


class PublisherTests(AutonomyCase):
    """FR-024, FR-025, FR-027, AC-010: the trusted runner opens one Draft PR."""

    def setUp(self) -> None:
        super().setUp()
        self.eligible_issue()
        (self.gh_dir / "auth.ok").write_text("")
        head = self.git("rev-parse", "HEAD").strip()
        self.run_record = self.make_run(
            head=head, issue_title="Demo run", status="completed"
        )
        autonomy.write_json(
            autonomy.run_dir(self.root, "run42") / "git-config.json",
            autonomy.config_snapshot(self.root),
        )
        (self.root / FEATURE).mkdir(parents=True)
        (self.root / FEATURE / "spec.md").write_text("# Spec\n")
        (self.root / "src").mkdir()
        (self.root / "src/demo.py").write_text("print('demo')\n")
        autonomy.write_json(
            autonomy.run_dir(self.root, "run42") / "checks.json", GOLDEN_CHECKS
        )
        self.checked()

    def checked(self) -> None:
        record = autonomy.read_run(self.root, "run42")
        record["checked_tree"] = autonomy.checked_digest(self.root, FEATURE)
        autonomy.write_run(self.root, record)

    def test_publishes_draft_pr(self) -> None:
        result = autonomy.publish(self.root, "run42")
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["url"], "https://github.com/acme/demo/pull/7")
        message = self.git("log", "-1", "--format=%B")
        self.assertIn("Autonomous-Run: run42", message)
        self.assertIn("Refs #27", message)
        remote = subprocess.run(  # noqa: S603
            ["git", "--git-dir", str(self.base / "origin.git"), "branch", "--list"],  # noqa: S607
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        self.assertIn("27-demo-run", remote)
        body = (self.gh_dir / "pr-body.md").read_text()
        self.assertIn("src/demo.py", body)
        self.assertIn("Refs #27", body)
        create = [c for c in self.gh_calls() if c[:2] == ["pr", "create"]]
        self.assertEqual(len(create), 1)
        self.assertIn("--draft", create[0])

    def test_argv_never_merges_or_forces(self) -> None:
        _install(FIXTURES / "fake_git.py", self.bin / "git")
        os.environ["FAKE_GIT_LOG"] = str(self.base / "git.log")
        os.environ["FAKE_REAL_GIT"] = shutil.which("git", path=self.real_path) or "git"
        self.assertTrue(autonomy.publish(self.root, "run42")["ok"])
        git_calls = [
            json.loads(line)
            for line in (self.base / "git.log").read_text().splitlines()
        ]
        commands = [
            next(word for word in call[4:] if not word.startswith("--git-dir="))
            for call in git_calls
            if call[:4] == list(autonomy.GIT_HARDENING)
        ]
        self.assertEqual(len(commands), len(git_calls), "every git call is hardened")
        # DEC-0007: HEAD's commit to the pinned URL, from a bare repository
        # with an empty config, never through origin or the checkout's config.
        head = self.git("rev-parse", "HEAD").strip()
        ((push,),) = [[c[4:]] for c in git_calls if "push" in c[4:6]]
        self.assertTrue(push[0].startswith("--git-dir="), push)
        self.assertFalse(Path(push[0][10:]).is_relative_to(self.root))
        self.assertEqual(
            push[1:], ["push", GITHUB_URL, f"{head}:refs/heads/27-demo-run"]
        )
        self.assertTrue({"add", "commit", "push"} <= set(commands))
        forbidden = ("merge", "ready", "--force", "-f", "release", "deploy", "rebase")
        for call in [*git_calls, *self.gh_calls()]:
            for word in forbidden:
                self.assertNotIn(word, call, call)
        # Reads back through `gh api` are GETs: no method or field flags.
        for call in self.gh_calls():
            if call[0] == "api":
                self.assertFalse({"-X", "--method", "-f", "-F"} & set(call), call)
        gh_commands = {tuple(c[:2]) for c in self.gh_calls() if c[0] != "api"}
        self.assertLessEqual(
            gh_commands,
            {("repo", "view"), ("pr", "list"), ("pr", "create")},
        )

    def test_planted_hook_does_not_run(self) -> None:
        marker = self.base / "hook-ran"
        for name in ("pre-commit", "commit-msg", "pre-push", "post-commit"):
            hook = self.root / ".git/hooks" / name
            hook.write_text(f"#!/bin/sh\ntouch {marker}\n")
            hook.chmod(0o755)
        autonomy.write_json(
            autonomy.run_dir(self.root, "run42") / "git-config.json",
            autonomy.config_snapshot(self.root),
        )
        self.assertTrue(autonomy.publish(self.root, "run42")["ok"])
        self.assertFalse(marker.exists())

    def refused(self, category: str, text: str) -> None:
        result = autonomy.publish(self.root, "run42")
        self.assertFalse(result["ok"])
        self.assertEqual(result["category"], category, result)
        self.assertIn(text, result["message"])
        self.assertFalse((self.gh_dir / "pr-body.md").exists())

    def test_changed_tree_is_refused(self) -> None:
        (self.root / "src/late.py").write_text("x")
        self.refused("postcondition", "differs from the tree that passed run-checks")

    def test_changed_local_config_is_refused(self) -> None:
        self.git("config", "credential.helper", "store")
        self.refused("postcondition", "Git configuration or hooks changed")

    def test_program_inside_checkout_is_refused(self) -> None:
        self.git("config", "gpg.program", str(self.root / "gpg.sh"))
        autonomy.write_json(
            autonomy.run_dir(self.root, "run42") / "git-config.json",
            autonomy.config_snapshot(self.root),
        )
        self.refused("postcondition", "gpg.program")

    def test_configured_filter_is_refused(self) -> None:
        (self.root / ".gitattributes").write_text("*.py filter=evil\n")
        self.git("config", "filter.evil.clean", "cat")
        autonomy.write_json(
            autonomy.run_dir(self.root, "run42") / "git-config.json",
            autonomy.config_snapshot(self.root),
        )
        self.checked()
        self.refused("postcondition", "filter=evil")

    def test_protected_and_large_paths_are_refused(self) -> None:
        (self.root / "ballast.toml").write_text(
            '[checks]\ncommands = ["false"]\n' + GITHUB_PIN
        )
        self.refused("postcondition", "ballast.toml")
        self.assertEqual(self.git("diff", "--cached", "--name-only"), "")
        self.git("checkout", "--", "ballast.toml")
        (self.root / "big.bin").write_bytes(b"0" * (autonomy.MAX_PUBLISHED_FILE + 1))
        self.checked()
        self.refused("postcondition", "big.bin")

    def test_default_branch_and_existing_pr_are_refused(self) -> None:
        self.gh_data("pr-list.json", [{"url": "https://x"}])
        self.refused("postcondition", "reuse is #17")
        (self.gh_dir / "pr-list.json").unlink()
        self.gh_data(
            "repo.json",
            {"nameWithOwner": "acme/demo", "defaultBranchRef": {"name": "27-demo-run"}},
        )
        self.refused("postcondition", autonomy.BRANCH_REFUSAL)

    def test_body_claiming_human_approval_is_never_posted(self) -> None:
        """AC-007, SC-003: the last guard before the PR body leaves the host."""
        render = autonomy.render_pr_body
        with patch.object(
            autonomy,
            "render_pr_body",
            side_effect=lambda *a, **k: (
                render(*a, **k) + "\nPlan approved by the operator.\n"
            ),
        ):
            result = autonomy.publish(self.root, "run42")
        self.assertFalse(result["ok"])
        self.assertIn("human approval", result["message"])
        self.assertFalse([c for c in self.gh_calls() if c[:2] == ["pr", "create"]])

    def test_forge_failure_is_retryable(self) -> None:
        (self.gh_dir / "FAIL_pr_create").write_text("")
        result = autonomy.publish(self.root, "run42")
        self.assertEqual(result["category"], "forge")
        (self.gh_dir / "FAIL_pr_create").unlink()
        commits = self.git("rev-list", "--count", "HEAD")
        self.assertEqual(commits, "2\n")
        retry = autonomy.publish(self.root, "run42")
        self.assertTrue(retry["ok"], retry)
        self.assertEqual(self.git("rev-list", "--count", "HEAD"), commits)

    def test_run_created_artifacts_before_baseline_are_staged(self) -> None:
        self.assertTrue(autonomy.publish(self.root, "run42")["ok"])
        files = self.git("show", "--name-only", "--format=", "HEAD").split()
        self.assertIn(f"{FEATURE}/spec.md", files)
        self.assertIn("src/demo.py", files)

    def test_unauthorized_privileged_action_blocks_publication(self) -> None:
        autonomy.append_decision(
            self.root,
            "run42",
            {
                "point": "implementation-review",
                "decision": "accept-finding",
                "summary": "s",
                "privileged_actions": ["secret provisioning"],
            },
        )
        self.refused("ineligible", "privileged action secret provisioning before merge")

    def test_raised_excluded_risk_blocks_publication(self) -> None:
        record = autonomy.read_run(self.root, "run42")
        record["eligibility"]["policy"]["risk"] = ["R0", "R1"]
        autonomy.raise_risk(record, "R2", [], "PD-0001")
        autonomy.write_run(self.root, record)
        self.refused("ineligible", "risk R2 excluded")

    # DEC-0007: the publisher uses draft_pr's gh and git hardening (#17).

    def test_gh_starts_outside_the_checkout_and_names_the_pinned_repo(self) -> None:
        with patch.object(draft_pr, "_command", wraps=draft_pr._command) as command:  # noqa: SLF001
            self.assertTrue(autonomy.publish(self.root, "run42")["ok"])
        gh_calls = [c for c in command.call_args_list if c.args[0][1] != "api"]
        self.assertTrue(gh_calls)
        for call in gh_calls:
            self.assertFalse(call.kwargs["cwd"].resolve().is_relative_to(self.root))
            argv = call.args[0]
            self.assertIn("acme/demo", argv)
            if argv[1] == "pr":
                self.assertEqual(argv[argv.index("--repo") + 1], "acme/demo")
        create = next(c for c in self.gh_calls() if c[:2] == ["pr", "create"])
        self.assertEqual(create[create.index("--base") + 1], "main")
        self.assertEqual(create[create.index("--head") + 1], "27-demo-run")

    def test_checkout_local_gh_and_git_never_run(self) -> None:
        planted = self.root / ".git/planted-bin"  # In the checkout, not in status.
        planted.mkdir()
        marker = self.base / "planted-ran"
        for name in ("gh", "git"):
            (planted / name).write_text(f"#!/bin/sh\ntouch {marker}\nexit 1\n")
            (planted / name).chmod(0o755)
        os.environ["PATH"] = f"{planted}{os.pathsep}{os.environ['PATH']}"
        self.assertTrue(autonomy.publish(self.root, "run42")["ok"])
        self.assertFalse(marker.exists())

    def test_gh_only_in_a_temp_root_is_refused(self) -> None:
        system = self.base / "system-bin"  # git only, never a real gh
        system.mkdir()
        (system / "git").symlink_to(shutil.which("git", path=self.real_path) or "")
        os.environ["PATH"] = f"{self.bin}{os.pathsep}{system}"
        with patch.object(ledger, "agent_temp_roots", lambda: (self.bin,)):
            result = autonomy.publish(self.root, "run42")
        self.assertEqual(self.gh_calls(), [])
        self.assertEqual(result["category"], "permission")
        self.assertIn("gh not found outside working trees", result["message"])

    def test_missing_pin_is_a_retryable_forge_refusal(self) -> None:
        (self.root / "ballast.toml").write_text('[checks]\ncommands = ["true"]\n')
        self.refused("forge", "[github] repository")
        self.assertIn("forge", autonomy.PUBLISH_RETRY)

    def test_origin_other_than_the_pinned_repository_is_refused(self) -> None:
        self.git("remote", "set-url", "origin", "https://github.com/evil/demo.git")
        self.refused("postcondition", autonomy.ORIGIN_REFUSAL)
        self.assertFalse([c for c in self.gh_calls() if c[:2] == ["pr", "list"]])

    def test_open_pr_of_another_feature_is_still_refused(self) -> None:
        section = (
            f"{draft_pr.MARK_BEGIN}\n- Feature: `specs/28-other/`\n{draft_pr.MARK_END}"
        )
        self.gh_data(
            "pr-list.json",
            [
                {
                    "number": 9,
                    "url": "https://github.com/acme/demo/pull/9",
                    "body": section,
                }
            ],
        )
        self.refused("postcondition", "reuse is #17")

    def test_adopts_the_checkpoints_pr_and_keeps_its_section(self) -> None:
        section = f"{draft_pr.MARK_BEGIN}\n- Feature: `{FEATURE}/`\n{draft_pr.MARK_END}"
        body = f"Template\n\n{section}\n"
        self.gh_data("pr-list.json", [listed_pr(9, body)])
        self.gh_data("repos_acme_demo_pulls_9.json", served_pr(9, body))
        result = autonomy.publish(self.root, "run42")
        self.assertEqual(result["url"], "https://github.com/acme/demo/pull/9", result)
        calls = [c[:2] for c in self.gh_calls()]
        self.assertNotIn(["pr", "create"], calls)
        self.assertIn(["pr", "edit"], calls)
        body = (self.gh_dir / "pr-body.md").read_text()
        # Only the publisher's own section is added; all other text is kept.
        self.assertTrue(body.startswith("Template\n\n"), body)
        self.assertEqual(body.count(autonomy.SUMMARY_BEGIN), 1)
        self.assertIn("Refs #27", body)
        self.assertEqual(body.count(draft_pr.MARK_BEGIN), 1)
        self.assertTrue(body.endswith(section + "\n"))

    def test_republish_replaces_only_its_own_section(self) -> None:
        section = f"{draft_pr.MARK_BEGIN}\n- Feature: `{FEATURE}/`\n{draft_pr.MARK_END}"
        old = f"{autonomy.SUMMARY_BEGIN}\nold summary\n{autonomy.SUMMARY_END}"
        body = f"Human note\n\n{old}\n\n{section}\nTrailer\n"
        self.gh_data("pr-list.json", [listed_pr(9, body)])
        self.gh_data("repos_acme_demo_pulls_9.json", served_pr(9, body))
        self.assertTrue(autonomy.publish(self.root, "run42")["ok"])
        edited = (self.gh_dir / "pr-body.md").read_text()
        self.assertNotIn("old summary", edited)
        self.assertTrue(edited.startswith("Human note\n\n" + autonomy.SUMMARY_BEGIN))
        self.assertTrue(edited.endswith(f"{section}\nTrailer\n"))
        self.assertIn("Refs #27", edited)

    def test_ready_or_retargeted_pr_is_never_adopted(self) -> None:
        section = f"{draft_pr.MARK_BEGIN}\n- Feature: `{FEATURE}/`\n{draft_pr.MARK_END}"
        self.gh_data("pr-list.json", [listed_pr(9, section)])
        for changes, problem in (
            ({"draft": False}, "is not a draft"),
            ({"base": {"ref": "develop"}}, "targets develop"),
            ({"state": "closed"}, "is not open"),
        ):
            with self.subTest(changes=changes):
                self.gh_data(
                    "repos_acme_demo_pulls_9.json", served_pr(9, section, **changes)
                )
                self.refused("postcondition", problem)
                self.assertNotIn(["pr", "edit"], [c[:2] for c in self.gh_calls()])

    def test_concurrent_body_edit_is_never_overwritten(self) -> None:
        section = f"{draft_pr.MARK_BEGIN}\n- Feature: `{FEATURE}/`\n{draft_pr.MARK_END}"
        self.gh_data("pr-list.json", [listed_pr(9, section)])
        self.gh_data("repos_acme_demo_pulls_9.json", served_pr(9, section))
        edited = f"Reviewer: please keep this.\n\n{section}"
        # GitHub changes the body after the publisher first read it.
        self.gh_data("repos_acme_demo_pulls_9.then.json", served_pr(9, edited))
        result = autonomy.publish(self.root, "run42")
        self.assertEqual(result["category"], "forge", result)
        self.assertIn("changed", result["message"])
        self.assertNotIn(["pr", "edit"], [c[:2] for c in self.gh_calls()])
        self.assertIn("forge", autonomy.PUBLISH_RETRY)
        # The retry keeps the human's text.
        retry = autonomy.publish(self.root, "run42")
        self.assertTrue(retry["ok"], retry)
        body = (self.gh_dir / "pr-body.md").read_text()
        self.assertTrue(body.startswith("Reviewer: please keep this."), body)

    def test_created_pr_is_read_back_and_verified(self) -> None:
        for changes, problem in (
            ({"draft": False}, "is not a draft"),
            ({"base": {"ref": "develop"}}, "targets develop"),
            (
                {"head": {"ref": "x", "repo": {"full_name": "acme/demo"}}},
                "head is not",
            ),
        ):
            with self.subTest(changes=changes):
                self.gh_data("create-override.json", changes)
                result = autonomy.publish(self.root, "run42")
                self.assertFalse(result["ok"])
                self.assertEqual(result["category"], "postcondition", result)
                self.assertIn(problem, result["message"])
        reads = [
            c for c in self.gh_calls() if c[:2] == ["api", "repos/acme/demo/pulls/7"]
        ]
        self.assertEqual(len(reads), 3)

    def test_pr_from_another_head_repository_is_never_adopted(self) -> None:
        """Same branch name and section, but not acme/demo's own branch."""
        section = f"{draft_pr.MARK_BEGIN}\n- Feature: `{FEATURE}/`\n{draft_pr.MARK_END}"
        for changes in (
            {"isCrossRepository": True},
            {"headRepository": {"name": "demo-fork"}, "isCrossRepository": True},
            {"headRepositoryOwner": {"login": "evil"}},
            {"headRepository": {"name": "other"}},
            {"url": "https://github.com/evil/demo/pull/9"},
        ):
            with self.subTest(changes=changes):
                self.gh_data("pr-list.json", [listed_pr(9, section, **changes)])
                self.refused("postcondition", "reuse is #17")
                calls = [c[:2] for c in self.gh_calls()]
                self.assertNotIn(["pr", "edit"], calls)

    def test_head_repository_matches_case_insensitively(self) -> None:
        section = f"{draft_pr.MARK_BEGIN}\n- Feature: `{FEATURE}/`\n{draft_pr.MARK_END}"
        pr = listed_pr(
            9,
            section,
            headRepository={"name": "Demo"},
            headRepositoryOwner={"login": "ACME"},
            url="https://github.com/ACME/Demo/pull/9",
        )
        self.gh_data("pr-list.json", [pr])
        self.gh_data("repos_acme_demo_pulls_9.json", served_pr(9, section))
        self.assertTrue(autonomy.publish(self.root, "run42")["ok"])

    def bare(self, name: str) -> Path:
        path = self.base / name
        subprocess.run(  # noqa: S603
            ["git", "init", "-q", "--bare", str(path)],  # noqa: S607
            check=True,
            capture_output=True,
        )
        return path

    def branches(self, bare: Path) -> str:
        return subprocess.run(  # noqa: S603
            ["git", "--git-dir", str(bare), "branch", "--list"],  # noqa: S607
            capture_output=True,
            text=True,
            check=True,
        ).stdout

    def snapshot(self) -> None:
        """Treat the current local Git configuration as the run's start state."""
        autonomy.write_json(
            autonomy.run_dir(self.root, "run42") / "git-config.json",
            autonomy.config_snapshot(self.root),
        )

    def test_pushurl_never_redirects_the_push(self) -> None:
        evil = self.bare("evil.git")
        self.git("config", "remote.origin.pushurl", str(evil))
        self.snapshot()
        self.assertTrue(autonomy.publish(self.root, "run42")["ok"])
        self.assertEqual(self.branches(evil), "")
        self.assertIn("27-demo-run", self.branches(self.base / "origin.git"))

    def assert_pushed_to_origin_only(self, evil: Path) -> None:
        self.assertEqual(self.branches(evil), "")
        head = self.git("rev-parse", "HEAD").strip()
        origin = str(self.base / "origin.git")
        pushed = subprocess.run(  # noqa: S603
            ["git", "--git-dir", origin, "rev-parse", "refs/heads/27-demo-run"],  # noqa: S607
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        self.assertEqual(pushed, head)

    def test_local_push_rewrite_never_redirects_the_push(self) -> None:
        evil = self.bare("evil.git")
        self.git("config", f"url.{evil}.pushInsteadOf", "https://github.com/acme/")
        self.snapshot()
        self.assertTrue(autonomy.publish(self.root, "run42")["ok"])
        self.assert_pushed_to_origin_only(evil)

    def test_local_fetch_rewrite_is_refused_and_never_pushed_to(self) -> None:
        evil = self.bare("evil.git")
        self.git("config", f"url.{evil}.insteadOf", "https://github.com/acme/")
        self.snapshot()
        self.refused("postcondition", autonomy.ORIGIN_REFUSAL)
        self.assertEqual(self.branches(evil), "")

    def test_rewrite_key_with_spaces_never_redirects_the_push(self) -> None:
        spaced = self.base / "e v"
        spaced.mkdir()
        evil = self.bare("e v/demo.git")
        # As long as the operator's own rewrite, and later: it would win.
        self.git("config", f"url.{spaced}/.pushInsteadOf", "https://github.com/acme/")
        self.snapshot()
        self.assertTrue(autonomy.publish(self.root, "run42")["ok"])
        self.assert_pushed_to_origin_only(evil)

    def test_included_config_never_redirects_the_push(self) -> None:
        evil = self.bare("evil.git")
        included = self.root / ".git/evil.inc"
        included.write_text(
            f'[url "{evil}"]\n\tpushInsteadOf = https://github.com/acme/\n'
        )
        self.git("config", "include.path", str(included))
        self.snapshot()
        self.assertTrue(autonomy.publish(self.root, "run42")["ok"])
        self.assert_pushed_to_origin_only(evil)

    def test_local_ssh_command_and_credential_helper_never_run(self) -> None:
        """The push reads none of the checkout's configuration."""
        marker = self.base / "local-ran"
        script = self.root / ".git/evil.sh"
        script.write_text(f"#!/bin/sh\ntouch {marker}\nexit 1\n")
        script.chmod(0o755)
        # Over ssh, with the operator's own (failing) ssh: only the local
        # core.sshCommand could run the sentinel.
        self.git("remote", "set-url", "origin", "ssh://git@github.com/acme/demo.git")
        operator = self.base / "gitconfig"
        for key, value in (("core.sshCommand", "false"),):
            subprocess.run(  # noqa: S603
                ["git", "config", "--file", str(operator), key, value],  # noqa: S607
                check=True,
            )
        self.git("config", "core.sshCommand", str(script))
        self.git("config", "credential.helper", f"!{script}")
        self.snapshot()
        result = autonomy.publish(self.root, "run42")
        self.assertEqual(result["category"], "forge", result)
        self.assertFalse(marker.exists())

    def test_hooks_path_pre_push_never_runs(self) -> None:
        marker = self.base / "hook-ran"
        hooks = self.base / "hooks"
        hooks.mkdir()
        (hooks / "pre-push").write_text(f"#!/bin/sh\ntouch {marker}\n")
        (hooks / "pre-push").chmod(0o755)
        self.git("config", "core.hooksPath", str(hooks))
        self.snapshot()
        self.assertTrue(autonomy.publish(self.root, "run42")["ok"])
        self.assertFalse(marker.exists())

    # Implementation review fable-3, Low findings.

    def test_body_without_the_checkpoint_section_is_never_reshuffled(self) -> None:
        section = f"{draft_pr.MARK_BEGIN}\n- Feature: `{FEATURE}/`\n{draft_pr.MARK_END}"
        self.gh_data("pr-list.json", [listed_pr(9, section)])
        # The PR as read back no longer carries the #17 section.
        self.gh_data("repos_acme_demo_pulls_9.json", served_pr(9, "Human text."))
        result = autonomy.publish(self.root, "run42")
        self.assertEqual(result["category"], "forge", result)
        self.assertNotIn(["pr", "edit"], [c[:2] for c in self.gh_calls()])

    def test_pr_marked_ready_before_the_edit_is_not_edited(self) -> None:
        section = f"{draft_pr.MARK_BEGIN}\n- Feature: `{FEATURE}/`\n{draft_pr.MARK_END}"
        self.gh_data("pr-list.json", [listed_pr(9, section)])
        self.gh_data("repos_acme_demo_pulls_9.json", served_pr(9, section))
        self.gh_data(
            "repos_acme_demo_pulls_9.then.json", served_pr(9, section, draft=False)
        )
        result = autonomy.publish(self.root, "run42")
        self.assertEqual(result["category"], "postcondition", result)
        self.assertIn("is not a draft", result["message"])
        self.assertNotIn(["pr", "edit"], [c[:2] for c in self.gh_calls()])

    def test_unknown_default_branch_refuses_before_any_write(self) -> None:
        self.gh_data("repo.json", {"nameWithOwner": "acme/demo"})
        self.refused("forge", "no default branch")
        calls = [c[:2] for c in self.gh_calls()]
        self.assertNotIn(["pr", "create"], calls)
        self.assertNotIn("27-demo-run", self.branches(self.base / "origin.git"))
        policy, _, warnings = self.policy()
        with self.assertRaisesRegex(autonomy.AutonomyError, "no default branch"):
            autonomy.check_eligibility(
                self.root,
                issue=ISSUE,
                feature=FEATURE,
                policy=policy,
                warnings=warnings,
                self_test=False,
            )

    def test_eligibility_needs_the_pin(self) -> None:
        (self.root / "ballast.toml").write_text('[checks]\ncommands = ["true"]\n')
        policy, _, warnings = self.policy()
        with self.assertRaisesRegex(autonomy.AutonomyError, r"\[github\] repository"):
            autonomy.check_eligibility(
                self.root,
                issue=ISSUE,
                feature=FEATURE,
                policy=policy,
                warnings=warnings,
                self_test=False,
            )


if __name__ == "__main__":
    unittest.main()
