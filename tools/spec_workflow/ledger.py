#!/usr/bin/env python3
"""Local, append-only evidence and deterministic reports for Spec Kit runs."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import uuid
from collections import Counter, defaultdict
from contextlib import contextmanager, nullcontext, suppress
from datetime import UTC, datetime
from itertools import pairwise
from pathlib import Path
from typing import TYPE_CHECKING, Any, NoReturn

if TYPE_CHECKING:
    from collections.abc import Iterator

# Same name as agent.TAMPER_MARKER. Checked before importing any other checkout
# module, which a failed protected check means an agent may have rewritten.
TAMPER_MARKER = "BALLAST_TAMPERED"
if __name__ == "__main__" and os.path.lexists(
    Path(__file__).resolve().parents[2] / TAMPER_MARKER
):
    sys.stderr.write(f"agent ledger: {TAMPER_MARKER} exists; restore the checkout\n")
    sys.exit(2)
# Never read checkout bytecode: a headless agent may have planted it. Operator
# checks start under `python3 -I -S`, which leaves this directory off sys.path.
sys.pycache_prefix = os.devnull
sys.path.insert(0, str(Path(__file__).resolve().parent))

from artifacts import FEATURE_PATTERN, RUN_ID_PATTERN  # noqa: E402
from autonomy import AutonomyError, filter_flags, refuse_embedded  # noqa: E402
from launcher import agent_temp_roots  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
VERSION = 1
EXIT_INTERRUPTED = 130
ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}")
LABEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9_./:+-]{0,127}")
MODEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:/+-]{0,63}")
POLICY_ROW = re.compile(r"[A-Za-z0-9`][A-Za-z0-9`_./:+,() -]{0,127}")
AC = re.compile(r"AC-[0-9]{3}")
SHA = re.compile(r"[0-9a-f]{64}")
OID = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")
# Spec Kit writes `1. **AC-NNN**:`; older fixtures `- **AC-NNN**:`.
CRITERION = re.compile(r"(?:-|[0-9]+\.)[ \t]+\*\*(AC-[0-9]{3})\*\*:[ \t]*(.*)")
TITLE_LIMIT = 120
DROP_SPECS = ("rm", "-r", "--cached", "-q", "--ignore-unmatch", "--", "specs")
# Writing even a private index runs the agent-writable post-index-change hook.
NO_HOOKS = ("-c", f"core.hooksPath={os.devnull}", "-c", "core.fsmonitor=false")
PR_URL = re.compile(
    r"https://github\.com/[A-Za-z0-9._-]{1,100}/[A-Za-z0-9._-]{1,100}"
    r"/pull/[1-9][0-9]{0,9}"
)
# Draft PR checkpoint outcomes and the reasons each may carry (draft_pr.py).
PR_REASONS: dict[str, frozenset[str]] = {
    "pending": frozenset(
        {
            "no-branch",
            "not-published",
            "on-base-branch",
            "no-meaningful-change",
            "diff-unclassified",
        }
    ),
    "created": frozenset(),
    "reused": frozenset({"section-unmanaged", "body-changed"}),
    "failed-retryable": frozenset(
        {
            "gh-missing",
            "gh-unauthenticated",
            "gh-forbidden",
            "github-unreachable",
            "github-error",
            "lock-busy",
            "internal-error",
            "gh-untrusted",
            "git-untrusted",
        }
    ),
    "blocked-ambiguous": frozenset(
        {"several-open", "base-mismatch", "create-unverified"}
    ),
    "blocked-closed": frozenset({"closed", "merged"}),
    "blocked-unlinked": frozenset(
        {
            "no-issue-number",
            "issue-not-found",
            "not-github",
            "no-repository",
            "repository-mismatch",
            "branch-unpinned",
            "branch-mismatch",
        }
    ),
}
# Branch synchronization outcomes and causes (branch_sync.py, #18).
SYNC_OUTCOMES = frozenset({"up-to-date", "synchronized", "blocked"})
SYNC_CAUSES = frozenset(
    {
        "busy",
        "git-unavailable",
        "in-progress",
        "wrong-branch",
        "unknown-base",
        "fetch-failed",
        "not-feature-branch",
        "diverged",
        "dirty",
        "conflict",
        "push-failed",
        "protected-input",
        "internal-error",
    }
)
# A branch name Ballast records or passes to Git: never an option, a range, a
# reflog expression or a lock file.
REF = re.compile(
    r"(?![-/])(?!.*(?:\.\.|//|@\{))(?!.*(?:\.lock|/)$)[A-Za-z0-9._/-]{1,200}"
)
# Acceptance packet outcomes and the reasons each may carry (packet.py).
PACKET_REASONS: dict[str, frozenset[str]] = {
    "published": frozenset(),
    "updated": frozenset(),
    "unchanged": frozenset(),
    "pending": frozenset({"no-pr", "pr-blocked", "head-not-local"}),
    "failed-retryable": frozenset(
        {
            "gh-missing",
            "gh-unauthenticated",
            "gh-forbidden",
            "gh-untrusted",
            "github-unreachable",
            "github-error",
            "body-changed",
            "section-unmanaged",
            "source-unreadable",
            "manifest-malformed",
            "ledger-invalid",
            "too-large",
            "internal-error",
        }
    ),
}
PACKET_COUNTS = ("verified", "failed", "not_run", "stale", "missing")
SOURCES = {"runner", "client-counter", "operator-attested", "agent-reported"}
RANK = {"economy": 0, "standard": 1, "senior": 2, "critical": 3}
EFFORT_RANK = {"none": 0, "low": 1, "medium": 2, "high": 3, "xhigh": 4, "max": 5}
MIN_POLICY_COLUMNS = 2
REPEATED_FAILURES = 2
UNITTEST_CHECK = (
    "import sys,unittest;"
    "suite=unittest.defaultTestLoader.loadTestsFromName(sys.argv[1]);"
    "result=unittest.TestResult();suite.run(result);"
    "sys.exit(0 if result.testsRun==1 and result.wasSuccessful() "
    "and not result.skipped and not result.expectedFailures else 1)"
)
ENUM_FIELDS: dict[str, dict[str, set[str]]] = {
    "run": {
        "action": {"started", "ended"},
        "status": {
            "completed",
            "failed",
            "paused",
            "cancelled",
            "interrupted",
            "aborted",
            "mode-changed",
        },
        "mode": {"human-gated", "autonomous", "chat"},
    },
    "step": {
        "action": {"started", "completed", "failed"},
        "status": {"completed", "failed", "paused", "skipped", "running"},
    },
    "gate": {"choice": {"approve", "reject", "unobserved"}},
    "route": {
        "profile": set(RANK),
        "effort": set(EFFORT_RANK),
        "route_source": {
            "deterministic",
            "classifier",
            "human-override",
            "escalation",
            "operator-choice",
        },
        "outcome": {
            "success",
            "reasoning-failure",
            "mechanical-failure",
            "rejected",
            "incomplete",
        },
    },
    "escalation": {
        "from_profile": set(RANK),
        "to_profile": set(RANK),
        "reason": {
            "reasoning-failure",
            "verification-failure",
            "uncertainty",
            "human-choice",
            "boundary-risk",
            "other",
        },
    },
    "review": {
        "kind": {
            "plan",
            "implementation",
            "engineering",
            "test",
            "documentation",
            "security",
            "architecture",
            "convergence",
            "spec-reconciliation",
        },
        "verdict": {"approved", "changes-requested", "partial", "failed"},
    },
    "finding": {
        "severity": {"critical", "high", "medium", "low", "info"},
        "resolution": {"open", "resolved", "accepted-risk", "deferred"},
    },
    "verification": {"status": {"passed", "failed", "skipped", "unavailable"}},
    "convergence": {"verdict": {"CONVERGED", "PARTIAL", "FAILED"}},
    "usage": {"scope": {"invocation", "stage", "run"}, "profile": set(RANK)},
    "human_action": {
        "action": {
            "manual_recovery",
            "route_override",
            "product_decision",
            "final_acceptance",
        },
    },
    "pull_request": {
        "outcome": set(PR_REASONS),
        "reason": set().union(*PR_REASONS.values()),
    },
    "branch_sync": {"outcome": set(SYNC_OUTCOMES), "cause": set(SYNC_CAUSES)},
    "acceptance_packet": {
        "outcome": set(PACKET_REASONS),
        "reason": set().union(*PACKET_REASONS.values()),
    },
}

# No opaque payload, prose, argv, or output field is accepted. A question mark
# marks an optional field; every other field is required.
FIELDS: dict[str, dict[str, str]] = {
    "run": {
        "action": "label",
        "status?": "label",
        "workflow_id?": "label",
        "workflow_version?": "label",
        "workflow_digest?": "sha",
        "policy_digest?": "sha",
        "mode?": "label",
    },
    "step": {
        "action": "label",
        "step_id": "label",
        "step_type?": "label",
        "status?": "label",
        "exit_code?": "int",
        "log_line": "int",
    },
    "gate": {"step_id": "label", "choice": "label", "log_line": "int"},
    "route": {
        "stage": "label",
        "provider?": "label",
        "model?": "model",
        "profile?": "label",
        "effort?": "label",
        "policy_row?": "policy_row",
        "route_source": "label",
        "actor_id?": "id",
        "attempt?": "int",
        "cause_id?": "id",
        "outcome?": "label",
        "alternate_available?": "bool",
        "author_provider?": "label",
    },
    "classifier": {"stage": "label", "invocation_id": "id"},
    "escalation": {
        "stage": "label",
        "from_profile": "label",
        "to_profile": "label",
        "reason?": "label",
        "attempt?": "int",
    },
    "review": {
        "review_id": "id",
        "kind": "label",
        "verdict": "label",
        "reviewer_id?": "id",
        "reviewer_provider?": "label",
        "reviewer_model?": "model",
        "author_id?": "id",
        "author_provider?": "label",
        "snapshot?": "sha",
        "spec_digest?": "sha",
        "intent_digest?": "sha",
        "plan_digest?": "sha",
        "tasks_digest?": "sha",
        "manifest_digest?": "sha",
        "alternate_available?": "bool",
    },
    "finding": {
        "review_id": "id",
        "finding_id": "id",
        "severity": "label",
        "resolution": "label",
    },
    "verification": {
        "check_id": "id",
        "status": "label",
        "exit_code?": "int",
        "ac_id?": "ac",
        "snapshot?": "sha",
        "spec_digest?": "sha",
        "manifest_digest?": "sha",
        "commit?": "oid",
    },
    "convergence": {
        "verdict": "label",
        "snapshot?": "sha",
        "spec_digest?": "sha",
        "intent_digest?": "sha",
        "plan_digest?": "sha",
        "tasks_digest?": "sha",
        "manifest_digest?": "sha",
    },
    "usage": {
        "invocation_id": "id",
        "stage": "label",
        "scope": "label",
        "counter_source": "label",
        "counter_digest": "sha",
        "input_tokens": "int",
        "output_tokens": "int",
        "cached_tokens": "int",
        "complete": "bool",
        "provider?": "label",
        "model?": "model",
        "profile?": "label",
        "step_id?": "label",
        "attempt?": "int",
        "cause_id?": "id",
    },
    "human_action": {
        "action": "label",
        "gate_id?": "label",
        "decision_id?": "id",
        "stage?": "label",
    },
    "snapshot": {
        "tree": "sha",
        "spec_digest?": "sha",
        "intent_digest?": "sha",
        "plan_digest?": "sha",
        "tasks_digest?": "sha",
        "manifest_digest?": "sha",
    },
    "pull_request": {
        "outcome": "label",
        "reason?": "label",
        "issue?": "int",
        "pr_number?": "int",
        "pr_url?": "url",
        "matches?": "int",
    },
    "branch_sync": {
        "outcome": "label",
        "cause?": "label",
        "base_ref?": "ref",
        "base_before?": "oid",
        "base_after?": "oid",
        "head_before?": "oid",
        "head_after?": "oid",
        "pushed?": "bool",
        "fast_forwarded?": "bool",
        "recovered?": "bool",
        "recovered_from?": "run_id",
        "retryable?": "bool",
        "overlap?": "int",
        "stale_plan?": "bool",
        "stale_review?": "bool",
    },
    "acceptance_packet": {
        "outcome": "label",
        "reason?": "label",
        "pr_number?": "int",
        "head?": "oid",
        "base?": "oid",
        "feature_version?": "oid",
        "packet_digest?": "sha",
        "shortened?": "bool",
        **{f"{count}?": "int" for count in PACKET_COUNTS},
    },
    # One dispatched demo capture (#22); written only after the dispatch.
    "demo_capture": {
        "scenario": "scenario",
        "commit": "oid",
        "request": "request",
        "command_digest": "sha",
        "pr_number": "int",
    },
}
# Written only by the runner, its Draft PR checkpoint, its branch
# synchronization or `ballast run demo`, never by `record`.
RUNNER_ONLY = frozenset(
    {
        "run",
        "step",
        "gate",
        "snapshot",
        "pull_request",
        "branch_sync",
        "acceptance_packet",
        "demo_capture",
    }
)
DEMO_SCENARIO = re.compile(r"[A-Za-z0-9._-]{1,64}")
DEMO_REQUEST = re.compile(r"[0-9a-f]{16}")


class LedgerError(ValueError):
    """Invalid local evidence or storage."""


def fail(message: str) -> NoReturn:
    """Raise a user-facing ledger validation error."""
    raise LedgerError(message)


def in_working_tree(path: Path, roots: tuple[Path, ...] = ()) -> bool:
    """Whether a resolved path lies in one of roots or under a `.git` parent."""
    return any(path.is_relative_to(root) for root in roots) or any(
        os.path.lexists(parent / ".git") for parent in (path, *path.parents)
    )


def resolve_program(
    name: str, entries: list[str], excluded: tuple[Path, ...] = ()
) -> tuple[str | None, bool]:
    """Find a program outside every Git working tree, as `ballast doctor` does.

    Returns the resolved absolute path, or None and whether a copy was found
    only in a working tree or a relative PATH entry.
    """
    kept = trusted_entries(entries, excluded)
    dropped = [entry or "." for entry in entries if entry not in kept]
    shadowed = False
    for entry in kept:
        found = _executable(Path(entry) / name)
        if found is None:
            continue
        program = found.resolve()
        if not in_working_tree(program, excluded):
            return str(program), False
        shadowed = True
    return None, shadowed or any(_executable(Path(e) / name) for e in dropped)


def trusted_entries(entries: list[str], excluded: tuple[Path, ...] = ()) -> list[str]:
    """Return the absolute PATH entries that lie outside every Git working tree."""
    return [
        entry
        for entry in entries
        if entry
        and Path(entry).is_absolute()
        and not in_working_tree(Path(entry).resolve(), excluded)
    ]


def _executable(path: Path) -> Path | None:
    return path if path.is_file() and os.access(path, os.X_OK) else None


def _git(root: Path, *args: str, env: dict[str, str] | None = None) -> str:
    # Never a bare `git`: a checkout-local one could be agent-written.
    git, _ = resolve_program(
        "git",
        os.environ.get("PATH", "").split(os.pathsep),
        (root.resolve(), *agent_temp_roots()),
    )
    if git is None:
        fail("git not found outside working trees")
    # No filter driver runs, whatever .gitattributes an agent added.
    listed = subprocess.run(  # noqa: S603
        [git, "config", "--list", "--name-only", "-z"],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if listed.returncode:
        fail(listed.stderr.strip() or "git config failed")
    try:
        filters = filter_flags(listed.stdout)
    except AutonomyError as error:
        fail(str(error))
    result = subprocess.run(  # noqa: S603
        [git, *filters, *args],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        fail(result.stderr.strip() or f"git {args[0]} failed")
    return result.stdout.strip()


def common_dir(root: Path) -> Path:
    """Resolve the Git directory shared by this clone's worktrees."""
    path = Path(_git(root, "rev-parse", "--path-format=absolute", "--git-common-dir"))
    if not path.is_dir():
        fail("Git common directory is unavailable")
    return path.resolve()


def archive_dir(root: Path, run_id: str) -> Path:
    """Resolve local run storage outside the worktree."""
    if not RUN_ID_PATTERN.fullmatch(run_id):
        fail("invalid run ID")
    parent = common_dir(root) / "speckit-runs"
    archive = parent / run_id
    if parent.is_symlink() or archive.is_symlink():
        fail("symlinked run archive is unavailable")
    return archive


def ledger_path(root: Path, run_id: str) -> Path:
    """Return the append-only event file for a run."""
    return archive_dir(root, run_id) / "events.jsonl"


@contextmanager
def _lock(path: Path, *, exclusive: bool) -> Iterator[None]:
    if exclusive:
        path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.parent / "events.lock"
    if lock_path.is_symlink() or path.is_symlink():
        fail("symlinked ledger file is unavailable")
    with lock_path.open("a+b" if exclusive else "rb") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


@contextmanager
def archive_lock(root: Path, run_id: str, *, exclusive: bool) -> Iterator[None]:
    """Coordinate archive copies with readers of the archived run files."""
    with _lock(ledger_path(root, run_id), exclusive=exclusive):
        yield


def _valid_value(kind: str, value: object) -> bool:
    if kind == "int":
        return type(value) is int and value >= 0
    if kind == "bool":
        return type(value) is bool
    if not isinstance(value, str):
        return False
    pattern = {
        "label": LABEL,
        "model": MODEL,
        "policy_row": POLICY_ROW,
        "id": ID,
        "ac": AC,
        "sha": SHA,
        "oid": OID,
        "url": PR_URL,
        "ref": REF,
        "run_id": RUN_ID_PATTERN,
        "scenario": DEMO_SCENARIO,
        "request": DEMO_REQUEST,
    }[kind]
    return bool(pattern.fullmatch(value))


def validate(event: object) -> None:  # noqa: C901, PLR0912, PLR0915 - Explicit checks.
    """Reject event versions, fields, types, and unsafe values outside the schema."""
    if not isinstance(event, dict):
        fail("event must be an object")
    required = {
        "schema_version",
        "run_id",
        "feature",
        "sequence",
        "observed_at",
        "event_id",
        "kind",
        "source",
        "data",
    }
    if (
        set(event) != required
        or type(event["schema_version"]) is not int
        or event["schema_version"] != VERSION
    ):
        fail("unsupported schema or event fields")
    if not isinstance(event["run_id"], str) or not RUN_ID_PATTERN.fullmatch(
        event["run_id"]
    ):
        fail("invalid run ID")
    if not isinstance(event["feature"], str) or not FEATURE_PATTERN.fullmatch(
        event["feature"]
    ):
        fail("invalid feature path")
    if type(event["sequence"]) is not int or event["sequence"] < 1:
        fail("invalid sequence")
    if not isinstance(event["event_id"], str) or not ID.fullmatch(event["event_id"]):
        fail("invalid event ID")
    if (
        not isinstance(event["source"], str)
        or not isinstance(event["kind"], str)
        or event["source"] not in SOURCES
        or event["kind"] not in FIELDS
    ):
        fail("unknown source or event kind")
    try:
        observed_at = datetime.fromisoformat(event["observed_at"])
    except (TypeError, ValueError) as error:
        message = "invalid timestamp"
        raise LedgerError(message) from error
    if observed_at.tzinfo is None:
        fail("timestamp needs a timezone")
    data = event["data"]
    if not isinstance(data, dict):
        fail("data must be an object")
    fields = FIELDS[event["kind"]]
    allowed = {key.removesuffix("?") for key in fields}
    needed = {key for key in fields if not key.endswith("?")}
    if not needed <= set(data) or not set(data) <= allowed:
        fail("missing or prohibited data field")
    for key, value in data.items():
        field_type = fields.get(key, fields.get(key + "?"))
        if field_type is None or not _valid_value(field_type, value):
            fail(f"invalid {key}")
    for key, options in ENUM_FIELDS.get(event["kind"], {}).items():
        if key in data and data[key] not in options:
            fail(f"unknown {key}")
    if event["kind"] == "run" and data["action"] == "ended" and "status" not in data:
        fail("run end needs status")
    # A Chat run's mode switch or continuation (#20): the run goes on.
    if (
        event["kind"] == "run"
        and data.get("status") == "mode-changed"
        and ("mode" not in data or data["action"] != "ended")
    ):
        fail("mode-changed needs mode and action ended")
    if event["kind"] == "pull_request":
        if data["outcome"] in {"created", "reused"}:
            if "pr_number" not in data or "pr_url" not in data:
                fail(f"{data['outcome']} needs pr_number and pr_url")
        elif "reason" not in data:
            fail(f"{data['outcome']} needs reason")
        if "reason" in data and data["reason"] not in PR_REASONS[data["outcome"]]:
            fail(f"reason does not apply to {data['outcome']}")
    if event["kind"] == "branch_sync":
        _validate_branch_sync(data)
    if event["kind"] == "acceptance_packet":
        _validate_packet(data)
    if event["kind"] == "demo_capture" and data["pr_number"] < 1:
        fail("invalid pr_number")
    required_source = {
        "run": "runner",
        "step": "runner",
        "gate": "runner",
        "pull_request": "runner",
        "branch_sync": "runner",
        "acceptance_packet": "runner",
        "demo_capture": "runner",
        "usage": "client-counter",
        "human_action": "operator-attested",
    }.get(event["kind"])
    if required_source and event["source"] != required_source:
        fail(f"{event['kind']} requires {required_source} source")


def _validate_branch_sync(data: dict[str, Any]) -> None:
    """Apply the per-outcome rules of the branch_sync event (#18 contract)."""
    outcome = data["outcome"]
    if outcome == "blocked":
        if "cause" not in data:
            fail("blocked needs cause")
    else:
        if "cause" in data:
            fail(f"{outcome} has no cause")
        needed = {"base_ref", "base_after", "head_before", "head_after"}
        if outcome == "synchronized":
            needed.add("pushed")
        if not needed <= set(data):
            fail(f"{outcome} needs {', '.join(sorted(needed))}")
    if "retryable" in data and data.get("cause") != "push-failed":
        fail("retryable applies only to push-failed")
    if "recovered" in data and outcome != "synchronized":
        fail("recovered applies only to synchronized")
    if "recovered_from" in data and data.get("recovered") is not True:
        fail("recovered_from needs recovered")


def _validate_packet(data: dict[str, Any]) -> None:
    if data["outcome"] in {"pending", "failed-retryable"}:
        if "reason" not in data:
            fail(f"{data['outcome']} needs reason")
    elif not {
        "pr_number",
        "head",
        "base",
        "feature_version",
        "packet_digest",
        *PACKET_COUNTS,
    } <= set(data):
        fail(f"{data['outcome']} needs the PR, commits, digest and counts")
    if "reason" in data and data["reason"] not in PACKET_REASONS[data["outcome"]]:
        fail(f"reason does not apply to {data['outcome']}")


def new_event(  # noqa: PLR0913, PLR0917 - Event identity has six fixed fields.
    run_id: str,
    feature: str,
    kind: str,
    source: str,
    data: dict[str, Any],
    event_id: str | None = None,
) -> dict[str, Any]:
    """Construct one validated observation; append assigns its sequence."""
    event = {
        "schema_version": VERSION,
        "run_id": run_id,
        "feature": feature,
        "sequence": 1,
        "observed_at": datetime.now(UTC).isoformat(),
        "event_id": event_id or uuid.uuid4().hex,
        "kind": kind,
        "source": source,
        "data": data,
    }
    validate(event)
    return event


def _semantic_problems(  # noqa: C901, PLR0912, PLR0915 - Transition cases mirror event kinds.
    events: list[dict[str, Any]],
) -> list[str]:
    """Find contradictory runner transitions without treating a pause as failure."""
    problems = []
    started_run = False
    completed_run = False
    open_steps: set[str] = set()
    completed_steps: set[tuple[str, int]] = set()
    failed_completions: set[tuple[str, int]] = set()
    gate_occurrences: set[tuple[str, int]] = set()
    route_attempts: set[tuple[str, str, int]] = set()
    review_ids: set[str] = set()
    for event in events:
        kind = event["kind"]
        data = event["data"]
        line = event["sequence"]
        if kind == "run":
            if data["action"] == "started":
                if started_run:
                    problems.append(f"line {line}: duplicate run start")
                started_run = True
            elif data["action"] == "ended":
                if not started_run or completed_run:
                    problems.append(f"line {line}: contradictory run end")
                completed_run = data.get("status") == "completed"
        elif kind == "step":
            step_id = data["step_id"]
            if not started_run or completed_run:
                problems.append(f"line {line}: step outside active run")
            if data["action"] == "started":
                open_steps.add(step_id)
            elif data["action"] in {"completed", "failed"}:
                repeated_failure = (
                    data["action"] == "failed"
                    and (step_id, data["log_line"] - 1) in failed_completions
                )
                if step_id not in open_steps and not repeated_failure:
                    problems.append(f"line {line}: step ended without start")
                open_steps.discard(step_id)
                completed_steps.add((step_id, data["log_line"]))
                if data["action"] == "completed" and data.get("status") == "failed":
                    failed_completions.add((step_id, data["log_line"]))
        elif kind == "gate":
            occurrence = (data["step_id"], data["log_line"])
            if occurrence not in completed_steps or occurrence in gate_occurrences:
                problems.append(f"line {line}: contradictory gate occurrence")
            gate_occurrences.add(occurrence)
        elif kind == "route" and data.get("cause_id") and "attempt" in data:
            attempt = (data["stage"], data["cause_id"], data["attempt"])
            if attempt in route_attempts:
                problems.append(f"line {line}: duplicate route attempt")
            route_attempts.add(attempt)
        elif kind == "review":
            review_id = data["review_id"]
            if review_id in review_ids:
                problems.append(f"line {line}: duplicate review ID")
            review_ids.add(review_id)
        elif kind == "finding" and data["review_id"] not in review_ids:
            problems.append(f"line {line}: finding references unknown review")
    return problems


def _read_unlocked(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    if not path.exists():
        return [], []
    events: list[dict[str, Any]] = []
    problems: list[str] = []
    ids: set[str] = set()
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        try:
            event = json.loads(line)
            validate(event)
            if event["sequence"] != number:
                fail("out-of-order or duplicate sequence")
            if event["event_id"] in ids:
                fail("duplicate event ID")
            ids.add(event["event_id"])
            events.append(event)
        except (ValueError, UnicodeError) as error:
            problems.append(f"line {number}: {error}")
    if not problems:
        problems.extend(_semantic_problems(events))
    return events, problems


def read(root: Path, run_id: str) -> tuple[list[dict[str, Any]], list[str]]:
    """Read all valid records and return line-numbered validation errors."""
    path = ledger_path(root, run_id)
    if not path.exists():
        return [], []
    with _lock(path, exclusive=False):
        return _read_unlocked(path)


def append(root: Path, event: dict[str, Any]) -> bool:
    """Append a new event under a file lock, retaining any invalid history."""
    validate(event)
    path = ledger_path(root, event["run_id"])
    with _lock(path, exclusive=True):
        events, problems = _read_unlocked(path)
        if problems:
            fail("invalid existing ledger: " + "; ".join(problems))
        for prior in events:
            if prior["event_id"] == event["event_id"]:
                same = {
                    k: v
                    for k, v in prior.items()
                    if k not in {"sequence", "observed_at"}
                } == {
                    k: v
                    for k, v in event.items()
                    if k not in {"sequence", "observed_at"}
                }
                if same:
                    return False
                fail("conflicting event ID")
        event = {**event, "sequence": len(events) + 1}
        semantic = _semantic_problems([*events, event])
        if semantic:
            fail("invalid event transition: " + "; ".join(semantic))
        with path.open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n"
            )
            handle.flush()
            os.fsync(handle.fileno())
    return True


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _has_head(root: Path, git: Any = None) -> bool:  # noqa: ANN401
    try:
        (git or _git)(root, "rev-parse", "--verify", "--quiet", "HEAD^{commit}")
    except LedgerError:
        return False
    return True


def implementation_tree(root: Path) -> str:
    """Fingerprint dirty implementation files without touching the user's index.

    The private index starts from HEAD, so tracked files matched by an ignore
    rule count as they do in a commit: a clean checkout's fingerprint equals
    `commit_tree(root, "HEAD")`.
    """
    with tempfile.TemporaryDirectory() as directory:
        env = {**os.environ, "GIT_INDEX_FILE": str(Path(directory) / "index")}
        if _has_head(root):
            _git(root, *NO_HOOKS, "read-tree", "HEAD", env=env)
        # Fixed pathspecs avoid interpreting untrusted filenames as Git magic.
        _git(root, *NO_HOOKS, "add", "-A", "--", ".", ":!specs", env=env)
        _git(root, *NO_HOOKS, *DROP_SPECS, env=env)
        try:
            refuse_embedded(
                root,
                "HEAD" if _has_head(root) else None,
                lambda *args: _git(root, *NO_HOOKS, *args, env=env),
            )
        except AutonomyError as error:
            fail(str(error))
        tree_oid = _git(root, *NO_HOOKS, "write-tree", env=env)
        return hashlib.sha256(tree_oid.encode("ascii")).hexdigest()


def commit_tree(root: Path, commit: str, git: Any = None) -> str:  # noqa: ANN401
    """Fingerprint a commit's implementation files as `implementation_tree` does.

    Reads only the object store into a private index: the worktree and the
    user's index are untouched, and no hook or filter runs.
    """
    run = git or _git
    if commit != "HEAD" and not OID.fullmatch(commit):
        fail("invalid commit")
    with tempfile.TemporaryDirectory() as directory:
        env = {**os.environ, "GIT_INDEX_FILE": str(Path(directory) / "index")}
        run(root, *NO_HOOKS, "read-tree", commit, env=env)
        run(root, *NO_HOOKS, *DROP_SPECS, env=env)
        tree_oid = run(root, *NO_HOOKS, "write-tree", env=env)
        return hashlib.sha256(tree_oid.encode("ascii")).hexdigest()


def spec_criteria(text: str) -> list[tuple[str, str, int]]:
    """`(AC-NNN, title, line)` for each criterion item, first occurrence, in order.

    The title is the text before `**When**`, without bold markers, at most
    TITLE_LIMIT characters.
    """
    found: list[tuple[str, str, int]] = []
    seen: set[str] = set()
    for number, line in enumerate(text.splitlines(), 1):
        match = CRITERION.fullmatch(line.rstrip())
        if match is None or match.group(1) in seen:
            continue
        seen.add(match.group(1))
        title = match.group(2).split("**When**", 1)[0].replace("**", "")
        title = " ".join(title.split()).rstrip(" ,;")[:TITLE_LIMIT]
        found.append((match.group(1), title, number))
    return found


def _run_files(root: Path, run_id: str) -> Path:
    active = root / ".specify/workflows/runs" / run_id
    if active.is_symlink() or active.parent.is_symlink():
        fail("symlinked active run is unavailable")
    if active.is_dir():
        return active
    archived = archive_dir(root, run_id) / "run"
    if archived.is_symlink():
        fail("symlinked archived run is unavailable")
    if archived.is_dir():
        return archived
    fail("run state is unavailable")


def _policy_rows(text: str) -> dict[str, str]:
    rows: dict[str, str] = {}
    in_table = False
    for line in text.splitlines():
        if line.startswith("| Work | Default profile / effort |"):
            in_table = True
            continue
        if in_table and not line.startswith("|"):
            break
        if in_table and line.startswith("|"):
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            if len(cells) >= MIN_POLICY_COLUMNS and not cells[0].startswith("---"):
                rows[cells[0]] = cells[1]
    return rows


def archive_policy(root: Path, run_id: str) -> dict[str, Any] | None:
    """Freeze the policy used by a new run before its first agent step."""
    target = archive_dir(root, run_id) / "policy.json"
    if target.is_symlink():
        fail("symlinked policy snapshot is unavailable")
    if target.is_file():
        return json.loads(target.read_text(encoding="utf-8"))
    policy = root / "docs/policies/model-routing.md"
    if not policy.is_file():
        return None
    data = {
        "digest": _sha(policy),
        "rows": _policy_rows(policy.read_text(encoding="utf-8")),
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return data


def import_run(  # noqa: C901, PLR0912, PLR0915 - One pass preserves log order.
    root: Path,
    run_id: str,
    *,
    at_invocation_end: bool = True,
) -> int:
    """Import new Spec Kit log lines, using only this invocation's final state."""
    run = _run_files(root, run_id)
    archived = run != root / ".specify/workflows/runs" / run_id
    guard = (
        archive_lock(
            root,
            run_id,
            exclusive=not (archive_dir(root, run_id) / "events.lock").exists(),
        )
        if archived
        else nullcontext()
    )
    with guard:
        inputs = json.loads((run / "inputs.json").read_text(encoding="utf-8"))["inputs"]
        state = json.loads((run / "state.json").read_text(encoding="utf-8"))
        lines = (run / "log.jsonl").read_text(encoding="utf-8").splitlines()
        invocation_file = archive_dir(root, run_id) / "invocation.json"
        if invocation_file.is_symlink():
            fail("symlinked invocation status is unavailable")
        invocation = (
            json.loads(invocation_file.read_text(encoding="utf-8"))
            if invocation_file.is_file()
            else {}
        )
        if (
            not isinstance(invocation, dict)
            or (invocation and set(invocation) != {"log_lines", "exit_status"})
            or any(type(value) is not int for value in invocation.values())
        ):
            fail("invalid invocation status")
        interrupted = (
            invocation.get("log_lines") == len(lines)
            and invocation.get("exit_status") == EXIT_INTERRUPTED
        )
        workflow = run / "workflow.yml"
        if not workflow.is_file():
            fail("archived workflow definition is missing")
        workflow_digest = _sha(workflow)
        gate_steps = {name for name, is_gate in _workflow_steps(run) if is_gate}
        _, workflow_version = _workflow_identity(run)
    feature = inputs["feature_directory"]
    if not FEATURE_PATTERN.fullmatch(feature):
        fail("invalid run feature")
    current, problems = read(root, run_id)
    if problems:
        fail("invalid existing ledger: " + "; ".join(problems))
    known = {event["event_id"] for event in current}
    count = 0
    if "runner:run" not in known:
        data = {
            "action": "started",
            "workflow_id": state.get("workflow_id", "unknown"),
            "workflow_version": workflow_version,
            "workflow_digest": workflow_digest,
        }
        policy_data = archive_policy(root, run_id)
        if policy_data is not None:
            data["policy_digest"] = policy_data["digest"]
        count += append(
            root, new_event(run_id, feature, "run", "runner", data, "runner:run")
        )
    all_lines: list[tuple[int, dict[str, Any]]] = []
    for number, raw in enumerate(lines, 1):
        item = json.loads(raw)
        if not isinstance(item, dict):
            fail(f"invalid run log line {number}")
        all_lines.append((number, item))
    new_lines = [
        (number, item)
        for number, item in all_lines
        if f"runner:log:{number}" not in known
    ]
    finishes = [
        number for number, item in all_lines if item.get("event") == "workflow_finished"
    ]
    current_start = 0
    if finishes:
        current_start = finishes[-1]
        if all_lines[-1][1].get("event") == "workflow_finished":
            current_start = finishes[-2] if len(finishes) > 1 else 0
    last_completed: dict[str, int] = {}
    last_gate_end: dict[str, int] = {}
    missed_invocation = (
        sum(item.get("event") == "workflow_finished" for _, item in new_lines) > 1
    )
    for number, item in all_lines:
        if item.get("event") == "step_completed" and isinstance(
            item.get("step_id"), str
        ):
            last_completed[item["step_id"]] = number
        if (
            item.get("event") in {"step_completed", "step_failed"}
            and item.get("step_id") in gate_steps
        ):
            last_gate_end[item["step_id"]] = number
    results = state.get("step_results", {})
    for number, item in all_lines:
        name = item.get("event")
        if f"runner:log:{number}" not in known:
            if name == "workflow_finished":
                kind = "run"
                data = {"action": "ended", "status": item.get("status", "unknown")}
            elif name in {"step_started", "step_completed", "step_failed"}:
                kind = "step"
                step_id = item.get("step_id")
                if not isinstance(step_id, str) or not LABEL.fullmatch(step_id):
                    fail(f"invalid step ID at run log line {number}")
                data = {
                    "action": name.removeprefix("step_"),
                    "step_id": step_id,
                    "log_line": number,
                }
                if isinstance(item.get("type"), str):
                    data["step_type"] = item["type"]
                if isinstance(item.get("status"), str):
                    data["status"] = item["status"]
                if last_completed.get(step_id) == number:
                    result = results.get(step_id, {})
                    output = result.get("output") or {}
                    if (
                        type(output.get("exit_code")) is int
                        and output["exit_code"] >= 0
                    ):
                        data["exit_code"] = output["exit_code"]
            else:
                fail(f"unknown run log event at line {number}")
            count += append(
                root,
                new_event(
                    run_id, feature, kind, "runner", data, f"runner:log:{number}"
                ),
            )
        if (
            name in {"step_completed", "step_failed"}
            and item.get("step_id") in gate_steps
            and f"runner:gate:{number}" not in known
        ):
            result = results.get(item["step_id"], {})
            choice = (result.get("output") or {}).get("choice")
            if (
                missed_invocation
                or number <= current_start
                or last_gate_end.get(item["step_id"]) != number
                or result.get("type") != "gate"
                or choice not in {"approve", "reject"}
                or (interrupted and choice == "reject")
            ):
                choice = "unobserved"
            count += append(
                root,
                new_event(
                    run_id,
                    feature,
                    "gate",
                    "runner",
                    {"step_id": item["step_id"], "choice": choice, "log_line": number},
                    f"runner:gate:{number}",
                ),
            )
    if (
        at_invocation_end
        and (root / feature).is_dir()
        and (root / ".specify/workflows/runs" / run_id).is_dir()
    ):
        # This captures the checkout at the end of the runner invocation, even
        # when no operator explicitly requested a snapshot.
        snapshot = artifact_digests(root, feature)
        identity = hashlib.sha256(
            json.dumps(
                {"state": state, "log_lines": len(lines), "snapshot": snapshot},
                sort_keys=True,
            ).encode()
        ).hexdigest()
        count += append(
            root,
            new_event(
                run_id,
                feature,
                "snapshot",
                "runner",
                snapshot,
                f"runner:snapshot:{identity}",
            ),
        )
        # In-progress spec revisions must not erase runner observations.
        # The missing validated version stays unavailable in the report.
        with suppress(OSError, ValueError, KeyError, TypeError):
            _archive_manifest_if_present(root, run_id, feature)
    return count


def artifact_digests(root: Path, feature: str) -> dict[str, str]:
    """Capture implementation and feature-artifact identities separately."""
    directory = root / feature
    result = {"tree": implementation_tree(root)}
    for name, key in (
        ("spec.md", "spec_digest"),
        ("intent.md", "intent_digest"),
        ("plan.md", "plan_digest"),
        ("tasks.md", "tasks_digest"),
        ("acceptance-evidence.json", "manifest_digest"),
    ):
        path = directory / name
        if path.is_file() and not path.is_symlink():
            result[key] = _sha(path)
    return result


def _approved_spec_ids(root: Path, feature: str) -> tuple[str, set[str]]:
    spec = root / feature / "spec.md"
    intent = root / feature / "intent.md"
    if spec.is_symlink() or intent.is_symlink():
        fail("symlinked feature approval artifact is unavailable")
    digest = _sha(spec)
    if f"sha256:{digest}" not in intent.read_text(encoding="utf-8"):
        fail("spec intent approval is missing or stale")
    ids = {ac for ac, _, _ in spec_criteria(spec.read_text(encoding="utf-8"))}
    if not ids:
        fail("approved spec has no AC IDs")
    return digest, ids


def archive_manifest(root: Path, run_id: str, feature: str) -> dict[str, Any]:
    """Validate and copy the approved AC to unittest mapping into the archive."""
    digest, ids = _approved_spec_ids(root, feature)
    path = root / feature / "acceptance-evidence.json"
    if path.is_symlink():
        fail("symlinked acceptance manifest is unavailable")
    source_bytes = path.read_bytes()
    data = json.loads(source_bytes)
    if (
        set(data) != {"schema_version", "spec_digest", "criteria"}
        or data["schema_version"] != 1
        or data["spec_digest"] != digest
    ):
        fail("acceptance manifest does not match approved spec")
    criteria = data["criteria"]
    if not isinstance(criteria, dict) or set(criteria) != ids:
        fail("acceptance manifest AC set differs from approved spec")
    for tests in criteria.values():
        if not isinstance(tests, list) or not tests:
            fail("each AC needs a named test")
        for test in tests:
            if not isinstance(test, str) or not re.fullmatch(
                r"tests\.test_[A-Za-z0-9_.]+\.test_[A-Za-z0-9_]+", test
            ):
                fail("acceptance evidence must name a unittest case")
    _store_manifest_bytes(root, run_id, source_bytes)
    return data


def _store_manifest_bytes(root: Path, run_id: str, source_bytes: bytes) -> None:
    version = hashlib.sha256(source_bytes).hexdigest()
    target = archive_dir(root, run_id) / "manifests" / f"{version}.json"
    if target.parent.is_symlink() or target.is_symlink():
        fail("symlinked archived acceptance manifest is unavailable")
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and target.read_bytes() != source_bytes:
        fail("archived acceptance manifest version was modified")
    if not target.exists():
        with tempfile.NamedTemporaryFile(
            dir=target.parent, prefix=".manifest-", delete=False
        ) as temp:
            temp.write(source_bytes)
            temp.flush()
            os.fsync(temp.fileno())
            staging = Path(temp.name)
        try:
            try:
                os.link(staging, target)
            except FileExistsError:
                if target.is_symlink() or target.read_bytes() != source_bytes:
                    fail("archived acceptance manifest version was modified")
        finally:
            staging.unlink()


def _archive_manifest_if_present(root: Path, run_id: str, feature: str) -> None:
    path = root / feature / "acceptance-evidence.json"
    if path.exists() or path.is_symlink():
        archive_manifest(root, run_id, feature)


def _workflow_steps(run: Path) -> list[tuple[str, bool]]:
    document = _workflow_document(run)
    raw = document.get("steps")
    if not isinstance(raw, list) or any(not isinstance(item, dict) for item in raw):
        fail("archived workflow steps are invalid")
    steps = [(item.get("id"), item.get("type") == "gate") for item in raw]
    names = [name for name, _ in steps]
    if (
        not names
        or any(not isinstance(name, str) or not LABEL.fullmatch(name) for name in names)
        or len(set(names)) != len(names)
    ):
        fail("archived workflow steps are invalid")
    return steps


def _workflow_identity(run: Path) -> tuple[str, str]:
    """Extract the archived workflow's ID and version."""
    workflow = _workflow_document(run).get("workflow")
    if not isinstance(workflow, dict):
        fail("archived workflow identity is unavailable")
    identity, version = workflow.get("id"), workflow.get("version")
    if not isinstance(identity, str) or not isinstance(version, str):
        fail("archived workflow identity is unavailable")
    return identity, version


def _workflow_document(  # noqa: C901, PLR0912, PLR0915 - Strict YAML projection.
    run: Path,
) -> dict[str, Any]:
    """Read identity and steps from the engine's block-style safe_dump output."""
    workflow: dict[str, str] = {}
    steps: list[dict[str, str]] = []
    section = None
    step_indent = None
    nested = False
    seen: set[str] = set()
    for line in (run / "workflow.yml").read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if not line.startswith(" ") and not line.startswith("-"):
            match = re.fullmatch(r"([a-z_][a-z_0-9]*):(?: (.*))?", line)
            if match is None:
                fail("archived workflow YAML is invalid")
            key, value = match.groups()
            if key in {"workflow", "steps"}:
                if key in seen or value is not None:
                    fail("archived workflow YAML is invalid")
                seen.add(key)
            section = key
            continue
        if section == "workflow":
            if line.startswith("  ") and not line.startswith("   "):
                match = re.fullmatch(r"  ([a-z_][a-z_0-9]*):(?: (.*))?", line)
                if match is None:
                    fail("archived workflow YAML is invalid")
                key, value = match.groups()
                if key in {"id", "version"}:
                    if key in workflow:
                        fail("archived workflow YAML is invalid")
                    workflow[key] = _workflow_scalar(value)
            elif not line.startswith("    "):
                fail("archived workflow YAML is invalid")
        elif section == "steps":
            match = re.fullmatch(r"( *)- ([a-z_][a-z_0-9]*):(?: (.*))?", line)
            if match is not None:
                indent, key, value = match.groups()
                if len(indent) not in {0, 2} or (
                    step_indent is not None and len(indent) != step_indent
                ):
                    fail("archived workflow YAML is invalid")
                step_indent = len(indent)
                steps.append({})
                nested = False
            else:
                if step_indent is None:
                    fail("archived workflow YAML is invalid")
                indent = step_indent + 2
                if nested and line.startswith(" " * indent + "- "):
                    continue
                if line.startswith(" " * indent) and not line.startswith(
                    " " * (indent + 1)
                ):
                    match = re.fullmatch(
                        rf" {{{indent}}}([a-z_][a-z_0-9]*):(?: (.*))?", line
                    )
                    if match is None:
                        fail("archived workflow YAML is invalid")
                    key, value = match.groups()
                elif line.startswith(" " * (indent + 2)):
                    if not nested and re.match(
                        r"(?:- |[A-Za-z_][A-Za-z_0-9-]*:)", line.lstrip()
                    ):
                        fail("archived workflow YAML is invalid")
                    continue
                else:
                    fail("archived workflow YAML is invalid")
            nested = value is None
            if key in {"id", "type"}:
                if key in steps[-1]:
                    fail("archived workflow YAML is invalid")
                steps[-1][key] = _workflow_scalar(value)
        elif not line.startswith(" "):
            fail("archived workflow YAML is invalid")
    if "workflow" not in seen or "steps" not in seen:
        fail("archived workflow YAML is invalid")
    return {"workflow": workflow, "steps": steps}


def _workflow_scalar(value: str | None) -> str:
    """Accept only unambiguous strings emitted for workflow identity fields."""
    if value is None:
        fail("archived workflow YAML is invalid")
    if re.fullmatch(r"'(?:[^']|'')*'", value):
        return value[1:-1].replace("''", "'")
    if value.startswith('"'):
        try:
            decoded = json.loads(value)
        except ValueError as error:
            message = "archived workflow YAML is invalid"
            raise LedgerError(message) from error
        if isinstance(decoded, str):
            return decoded
    elif re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:/+-]*", value) and not (
        value.lower() in {"true", "false", "yes", "no", "on", "off", "null"}
        or re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", value)
        or re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value)
    ):
        return value
    fail("archived workflow YAML is invalid")


def _availability(value: object = None, reason: str | None = None) -> dict[str, object]:
    return (
        {"status": "available", "value": value}
        if reason is None
        else {"status": "unavailable", "reason": reason}
    )


def _independent(review: dict[str, Any]) -> bool:
    data = review["data"]
    return (
        review["source"] == "operator-attested"
        and bool(data.get("author_id"))
        and bool(data.get("reviewer_id"))
        and data["author_id"] != data["reviewer_id"]
    )


def _policy_comparison(  # noqa: PLR0911 - Missing reasons are distinct.
    root: Path, run_id: str, route: dict[str, Any], events: list[dict[str, Any]]
) -> dict[str, Any]:
    data = route["data"]
    row = data.get("policy_row")
    profile = data.get("profile")
    if not row or not profile:
        return _availability(reason="policy row or actual profile missing")
    path = archive_dir(root, run_id) / "policy.json"
    if path.is_symlink():
        return _availability(reason="symlinked policy snapshot")
    if not path.is_file():
        return _availability(reason="policy snapshot missing")
    rows = json.loads(path.read_text(encoding="utf-8"))["rows"]
    cell = rows.get(row)
    if cell is None:
        return _availability(reason="policy row unknown")
    allowed = re.findall(
        r"`(economy|standard|senior|critical)`\s+(low|medium|high|xhigh|max)",
        cell,
    )
    effort = data.get("effort")
    if effort is None:
        return _availability(reason="actual effort missing")
    if not allowed or profile not in RANK or effort not in EFFORT_RANK:
        return _availability(reason="policy cell is not machine-readable")
    if "Other provider" in cell and (
        not data.get("author_provider") or not data.get("provider")
    ):
        return _availability(reason="author or reviewer provider missing")
    allowed_rank = max(RANK[item] for item, _ in allowed)
    profile_above = RANK[profile] > allowed_rank
    effort_above = RANK[profile] == allowed_rank and EFFORT_RANK[effort] > max(
        EFFORT_RANK[item_effort]
        for item_profile, item_effort in allowed
        if RANK[item_profile] == allowed_rank
    )
    trigger = any(
        event["kind"] == "escalation"
        and event["source"] != "agent-reported"
        and event["data"]["stage"] == data["stage"]
        and event["data"].get("reason")
        and (
            "attempt" not in data
            or "attempt" not in event["data"]
            or event["data"]["attempt"] < data["attempt"]
        )
        and event["sequence"] < route["sequence"]
        for event in events
    )
    override = any(
        event["kind"] == "human_action"
        and event["data"]["action"] == "route_override"
        and event["data"].get("stage") == data["stage"]
        and event["sequence"] < route["sequence"]
        for event in events
    )
    other_provider_deviation = (
        "Other provider" in cell and data["author_provider"] == data["provider"]
    )
    return _availability(
        {
            "row": row,
            "matches_default": (profile, effort) in allowed
            and not other_provider_deviation,
            "profile_or_effort_above_default": profile_above or effort_above,
            "other_provider_deviation": other_provider_deviation,
            "above_default_without_reason": (profile_above or effort_above)
            and not trigger
            and not override,
        }
    )


def _attempt_measures(  # noqa: C901, PLR0911, PLR0912 - Missingness has distinct causes.
    events: list[dict[str, Any]], usage: list[dict[str, Any]], total_tokens: int
) -> dict[str, object]:
    """Account only for attempt spans linked to complete client counters."""
    routes = [
        event["data"]
        for event in events
        if event["kind"] == "route" and event["source"] != "agent-reported"
    ]
    if not routes or any(
        not route.get("cause_id")
        or "attempt" not in route
        or route.get("outcome")
        not in {"success", "reasoning-failure", "mechanical-failure", "rejected"}
        for route in routes
    ):
        return {
            "rework": _availability(reason="attempt outcomes are incomplete"),
            "before_after_escalation": _availability(
                reason="attempt linkage is incomplete"
            ),
        }
    by_attempt: dict[tuple[str, str, int], int] = defaultdict(int)
    for event in usage:
        data = event["data"]
        if "attempt" in data and "cause_id" in data:
            by_attempt[(data["stage"], data["cause_id"], data["attempt"])] += (
                data["input_tokens"] + data["output_tokens"]
            )
    if any(
        (route["stage"], route["cause_id"], route["attempt"]) not in by_attempt
        for route in routes
    ):
        return {
            "rework": _availability(reason="route attempt counter missing"),
            "before_after_escalation": _availability(
                reason="route attempt counter missing"
            ),
        }
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for route in routes:
        if route.get("cause_id") and "attempt" in route:
            groups[(route["stage"], route["cause_id"])].append(route)
    spans: list[tuple[str, str, int, int]] = []
    for (stage, cause), attempts in groups.items():
        attempts.sort(key=lambda item: item["attempt"])
        failed_at: int | None = None
        for item in attempts:
            if item.get("outcome") in {
                "reasoning-failure",
                "mechanical-failure",
                "rejected",
            }:
                if failed_at is None:
                    failed_at = item["attempt"]
            elif item.get("outcome") == "success" and failed_at is not None:
                spans.append((stage, cause, failed_at, item["attempt"]))
                failed_at = None
        if failed_at is not None:
            return {
                "rework": _availability(
                    reason="failed attempt has no observed correction"
                ),
                "before_after_escalation": _availability(
                    reason="attempt span incomplete"
                ),
            }
    rework = 0
    rework_by_stage: Counter[str] = Counter()
    for stage, cause, start, end in spans:
        for attempt in range(start, end + 1):
            key = (stage, cause, attempt)
            if key not in by_attempt:
                return {
                    "rework": _availability(reason="counter missing from rework span"),
                    "before_after_escalation": _availability(
                        reason="attempt span incomplete"
                    ),
                }
            rework += by_attempt[key]
            rework_by_stage[stage] += by_attempt[key]
    rework_value = {
        "tokens": rework,
        "ratio": rework / total_tokens if total_tokens else None,
        "by_stage": dict(rework_by_stage),
    }
    escalations = [event["data"] for event in events if event["kind"] == "escalation"]
    comparisons = []
    for escalation in escalations:
        stage = escalation["stage"]
        pivot = escalation.get("attempt")
        if pivot is None:
            return {
                "rework": _availability(rework_value),
                "before_after_escalation": _availability(
                    reason="escalation attempt missing"
                ),
            }
        before = sum(
            value
            for (item_stage, _, attempt), value in by_attempt.items()
            if item_stage == stage and attempt <= pivot
        )
        after = sum(
            value
            for (item_stage, _, attempt), value in by_attempt.items()
            if item_stage == stage and attempt > pivot
        )
        if not before or not after:
            return {
                "rework": _availability(rework_value),
                "before_after_escalation": _availability(
                    reason="escalation counters missing"
                ),
            }
        comparisons.append(
            {"stage": stage, "before_tokens": before, "after_tokens": after}
        )
    return {
        "rework": _availability(rework_value),
        "before_after_escalation": _availability(comparisons),
    }


def _underpowered(routes: list[dict[str, Any]]) -> list[str]:
    """Signal repeated same-cause failures resolved at a higher route."""
    by_cause: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for event in routes:
        data = event["data"]
        if data.get("cause_id") and "attempt" in data:
            by_cause[(data["stage"], data["cause_id"])].append(data)
    signals = []
    for (stage, cause), attempts in by_cause.items():
        if len({item["attempt"] for item in attempts}) != len(attempts):
            continue
        ordered = sorted(attempts, key=lambda item: item["attempt"])
        failures: list[dict[str, Any]] = []
        for attempt in ordered:
            if attempt.get("outcome") == "reasoning-failure":
                failures.append(attempt)
            elif (
                attempt.get("outcome") == "success"
                and len(failures) >= REPEATED_FAILURES
            ):
                first = failures[0]
                old_profile = first.get("profile")
                new_profile = attempt.get("profile")
                old_effort = first.get("effort")
                new_effort = attempt.get("effort")
                higher = (
                    old_profile in RANK
                    and new_profile in RANK
                    and RANK[new_profile] > RANK[old_profile]
                ) or (
                    old_profile == new_profile
                    and old_effort in EFFORT_RANK
                    and new_effort in EFFORT_RANK
                    and EFFORT_RANK[new_effort] > EFFORT_RANK[old_effort]
                )
                if higher:
                    signals.append(f"{stage}:{cause}")
                break
    return signals


def _missing_usage_reason(
    events: list[dict[str, Any]], usage: list[dict[str, Any]]
) -> str | None:
    """Find recorded attempts or classifiers without a complete counter."""
    routes = [
        event["data"]
        for event in events
        if event["kind"] == "route" and event["source"] != "agent-reported"
    ]
    if any("cause_id" not in route or "attempt" not in route for route in routes):
        return "attempt linkage is incomplete"
    recorded_attempts = {
        (route["stage"], route["cause_id"], route["attempt"]) for route in routes
    }
    counted_attempts = {
        (
            event["data"]["stage"],
            event["data"].get("cause_id"),
            event["data"].get("attempt"),
        )
        for event in usage
    }
    if not recorded_attempts <= counted_attempts:
        return "attempt counter missing"
    classifier_ids = {
        event["data"]["invocation_id"]
        for event in events
        if event["kind"] == "classifier"
    }
    if not classifier_ids <= {event["data"]["invocation_id"] for event in usage}:
        return "classifier counter missing"
    return None


def _usage(events: list[dict[str, Any]], passed_ac: int | None) -> dict[str, Any]:
    usage = [event for event in events if event["kind"] == "usage"]
    if not usage:
        return _availability(reason="client usage unavailable")
    if any(event["data"]["scope"] != "invocation" for event in usage):
        return _availability(reason="usage scope is not a disjoint invocation")
    if any(not event["data"]["complete"] for event in usage):
        return _availability(reason="partial client usage scope")
    ids = [event["data"]["invocation_id"] for event in usage]
    if len(set(ids)) != len(ids):
        return _availability(reason="overlapping invocation counters")
    missing = _missing_usage_reason(events, usage)
    if missing:
        return _availability(reason=missing)
    total = {
        key: sum(event["data"][key] for event in usage)
        for key in ("input_tokens", "output_tokens", "cached_tokens")
    }
    by_stage: dict[str, dict[str, int]] = defaultdict(lambda: dict.fromkeys(total, 0))
    by_profile: dict[str, dict[str, int]] = defaultdict(lambda: dict.fromkeys(total, 0))
    by_model: dict[str, dict[str, int]] = defaultdict(lambda: dict.fromkeys(total, 0))
    for event in usage:
        data = event["data"]
        for grouping, value in (
            (by_stage, data["stage"]),
            (by_profile, data.get("profile", "unavailable")),
            (by_model, data.get("model", "unavailable")),
        ):
            for key in total:
                grouping[value][key] += data[key]
    classifier_ids = {
        event["data"]["invocation_id"]
        for event in events
        if event["kind"] == "classifier"
    }
    classifier = sum(
        event["data"]["input_tokens"] + event["data"]["output_tokens"]
        for event in usage
        if event["data"]["invocation_id"] in classifier_ids
    )
    observed_usage_ids = {event["data"]["invocation_id"] for event in usage}
    classifier_overhead = (
        _availability(classifier)
        if classifier_ids <= observed_usage_ids
        else _availability(reason="classifier counter missing")
    )
    token_total = total["input_tokens"] + total["output_tokens"]
    attempts = _attempt_measures(events, usage, token_total)
    return _availability(
        {
            "total": total,
            "by_stage": dict(by_stage),
            "by_profile": dict(by_profile),
            "by_model": dict(by_model),
            "tokens_per_passed_ac": _availability(token_total / passed_ac)
            if passed_ac
            else _availability(
                reason="historical snapshot"
                if passed_ac is None
                else "no accepted criterion"
            ),
            "classifier_tokens": classifier_overhead,
            "rework": attempts["rework"],
            "before_after_escalation": attempts["before_after_escalation"],
        }
    )


def _intent_recovery_valid(
    events: list[dict[str, Any]],
    approval: dict[str, Any],
    rejected_snapshot: dict[str, str] | None,
    latest_snapshot: dict[str, str] | None,
) -> bool:
    """Bind intent creation and validation after the accepted spec revision."""
    if rejected_snapshot is None or latest_snapshot is None:
        return False
    recorded = [
        event["sequence"]
        for event in events
        if event["kind"] == "step"
        and event["data"]["step_id"] == "record-intent"
        and event["data"]["action"] == "completed"
        and event["data"].get("status") == "completed"
        and event["sequence"] > approval["sequence"]
    ]
    validated = [
        event["sequence"]
        for event in events
        if event["kind"] == "step"
        and event["data"]["step_id"] == "validate-intent"
        and event["data"]["action"] == "completed"
        and event["data"].get("status") == "completed"
        and event["data"].get("exit_code") == 0
        and any(sequence < event["sequence"] for sequence in recorded)
    ]
    return any(
        event["kind"] == "snapshot"
        and event["source"] == "runner"
        and any(sequence < event["sequence"] for sequence in validated)
        and event["data"].get("spec_digest") == latest_snapshot.get("spec_digest")
        and bool(event["data"].get("intent_digest"))
        and event["data"].get("intent_digest") != rejected_snapshot.get("intent_digest")
        for event in events
    )


def _recovery(
    events: list[dict[str, Any]], gates: list[dict[str, Any]]
) -> list[dict[str, str]]:
    """Require gate-specific evidence between rejection and later approval."""
    review_gate = {
        "review-plan": "plan",
        "review-implementation": "implementation",
        "final-acceptance": "implementation",
    }
    result = []
    for rejected in (gate for gate in gates if gate["data"]["choice"] == "reject"):
        gate_id = rejected["data"]["step_id"]
        approval = next(
            (
                gate
                for gate in gates
                if gate["sequence"] > rejected["sequence"]
                and gate["data"]["step_id"] == gate_id
                and gate["data"]["choice"] == "approve"
            ),
            None,
        )
        if approval is None:
            result.append({"gate": gate_id, "status": "incomplete"})
            continue
        between = [
            event
            for event in events
            if rejected["sequence"] < event["sequence"] < approval["sequence"]
        ]
        latest_snapshot = next(
            (
                event["data"]
                for event in reversed(events)
                if event["kind"] == "snapshot"
                and event["sequence"] < approval["sequence"]
            ),
            None,
        )
        rejected_snapshot = next(
            (
                event["data"]
                for event in events
                if event["kind"] == "snapshot"
                and event["source"] == "runner"
                and rejected["sequence"] < event["sequence"] < approval["sequence"]
            ),
            None,
        )
        latest_tree = latest_snapshot.get("tree") if latest_snapshot else None
        manual = any(
            event["kind"] == "human_action"
            and event["data"]["action"] == "manual_recovery"
            and event["data"].get("gate_id") == gate_id
            for event in between
        )
        verification = any(
            event["kind"] == "verification"
            and event["source"] == "operator-attested"
            and event["data"]["status"] == "passed"
            and latest_snapshot is not None
            and event["data"].get("snapshot") == latest_tree
            and (
                gate_id != "approve-intent"
                or event["data"].get("spec_digest")
                == latest_snapshot.get("spec_digest")
            )
            and (
                gate_id not in {"review-tasks", "approve-intent"}
                or event["data"]["check_id"]
                == (
                    "speckit-analyze"
                    if gate_id == "review-tasks"
                    else "validate-clarified-spec"
                )
            )
            for event in between
        )
        review_kind = review_gate.get(gate_id)
        review = review_kind is None or any(
            event["kind"] == "review"
            and event["data"]["kind"] == review_kind
            and event["data"]["verdict"] == "approved"
            and _independent(event)
            and event["data"].get("snapshot") == latest_tree
            and latest_snapshot is not None
            and all(
                event["data"].get(key) == latest_snapshot.get(key)
                for key in (
                    "spec_digest",
                    "intent_digest",
                    "plan_digest",
                    "tasks_digest",
                    "manifest_digest",
                )
            )
            for event in between
        )
        changed_keys = {
            "approve-intent": ("spec_digest",),
            "review-plan": ("spec_digest", "plan_digest"),
            "review-tasks": ("tasks_digest",),
        }.get(gate_id)
        revised = changed_keys is None or (
            rejected_snapshot is not None
            and latest_snapshot is not None
            and any(
                rejected_snapshot.get(key) is not None
                and latest_snapshot.get(key) is not None
                and rejected_snapshot[key] != latest_snapshot[key]
                for key in changed_keys
            )
        )
        convergence = gate_id not in {"spec-reconciliation", "final-acceptance"} or any(
            event["kind"] == "convergence"
            and event["source"] == "operator-attested"
            and event["data"]["verdict"] == "CONVERGED"
            and event["data"].get("snapshot") == latest_tree
            and latest_snapshot is not None
            and all(
                event["data"].get(key) == latest_snapshot.get(key)
                for key in (
                    "spec_digest",
                    "intent_digest",
                    "plan_digest",
                    "tasks_digest",
                    "manifest_digest",
                )
            )
            for event in between
        )
        intent_validated = gate_id != "approve-intent" or _intent_recovery_valid(
            events, approval, rejected_snapshot, latest_snapshot
        )
        result.append(
            {
                "gate": gate_id,
                "status": "compliant"
                if gate_id != "scope-gate"
                and manual
                and verification
                and review
                and revised
                and convergence
                and intent_validated
                else "unproven",
            }
        )
    return result


def _snapshot_status(
    root: Path, run_id: str, feature: str, events: list[dict[str, Any]]
) -> tuple[dict[str, str] | None, str]:
    """Compare with live files only while this checkout owns the active run."""
    snapshot = next(
        (event["data"] for event in reversed(events) if event["kind"] == "snapshot"),
        None,
    )
    if snapshot is None:
        return None, "unavailable"
    active = root / ".specify/workflows/runs" / run_id
    if not active.is_dir() or not (root / feature).is_dir():
        return snapshot, "historical"
    return (
        snapshot,
        "current" if artifact_digests(root, feature) == snapshot else "stale",
    )


def report(  # noqa: C901, PLR0911, PLR0912, PLR0915 - Five evidence dimensions share this read.
    root: Path, run_id: str
) -> dict[str, Any]:
    """Derive separate evidence-backed dimensions from one archived run."""
    events, problems = read(root, run_id)
    result: dict[str, Any] = {
        "run_id": run_id,
        "status": "incomplete",
        "problems": problems,
    }
    if problems:
        return {**result, "status": "invalid"}
    if not events:
        return {**result, "status": "uninstrumented"}
    feature = events[0]["feature"]
    result["feature"] = feature
    if any(
        event["run_id"] != run_id or event["feature"] != feature for event in events
    ):
        problems.append("mixed run or feature identity")
    if problems:
        result["status"] = "invalid"
        return result
    checkpoints = [event for event in events if event["kind"] == "pull_request"]
    result["pull_request"] = (
        {**checkpoints[-1]["data"], "observed_at": checkpoints[-1]["observed_at"]}
        if checkpoints
        else {"available": False, "reason": "no checkpoint recorded"}
    )
    packets = [event for event in events if event["kind"] == "acceptance_packet"]
    result["acceptance_packet"] = (
        {**packets[-1]["data"], "observed_at": packets[-1]["observed_at"]}
        if packets
        else {"available": False, "reason": "no packet recorded"}
    )
    demos: dict[str, dict[str, Any]] = {}
    for event in events:
        if event["kind"] == "demo_capture":
            demos[event["data"]["scenario"]] = {
                **event["data"],
                "observed_at": event["observed_at"],
            }
    if demos:
        result["demo_capture"] = demos
    syncs = [event for event in events if event["kind"] == "branch_sync"]
    result["branch_sync"] = (
        {**syncs[-1]["data"], "observed_at": syncs[-1]["observed_at"]}
        if syncs
        else {"available": False, "reason": "no check recorded"}
    )
    if len(syncs) == len(events):
        # A start blocked by branch synchronization never ran a workflow.
        return result
    runs = [event for event in events if event["kind"] == "run"]
    if runs and runs[0]["data"].get("mode") == "chat":
        try:
            return _chat_report(root, run_id, events, result)
        except (OSError, ValueError, KeyError, TypeError) as error:
            result["problems"].append(str(error))
            result["status"] = "invalid"
            return result
    result["status"] = (
        runs[-1]["data"].get("status", "incomplete") if runs else "incomplete"
    )
    try:
        archive = archive_dir(root, run_id)
        run = _run_files(root, run_id)
        archived = run != root / ".specify/workflows/runs" / run_id
        guard = (
            archive_lock(root, run_id, exclusive=False) if archived else nullcontext()
        )
        with guard:
            steps = _workflow_steps(run)
            workflow_digest = _sha(run / "workflow.yml")
            workflow_id, workflow_version = _workflow_identity(run)
        first_run = runs[0]["data"]
        if workflow_digest != first_run.get("workflow_digest"):
            fail("workflow definition digest mismatch")
        if (
            first_run.get("workflow_id") != workflow_id
            or first_run.get("workflow_version") != workflow_version
        ):
            fail("archived workflow identity mismatch")
        step_events = [event for event in events if event["kind"] == "step"]
        started = [
            event["data"]["step_id"]
            for event in step_events
            if event["data"]["action"] == "started"
        ]
        expected = [name for name, _ in steps]
        order = {name: index for index, name in enumerate(expected)}
        unknown_steps = sorted(set(started) - set(expected))
        out_of_order = [
            name
            for previous, name in pairwise(started)
            if name in order
            and previous in order
            and order[name] < order[previous]
            and name != previous
        ]
        completed = {
            event["data"]["step_id"]
            for event in step_events
            if event["data"]["action"] == "completed"
            and event["data"].get("status") == "completed"
        }
        missing = [name for name in expected if name not in completed]
        disagreements = []
        for index, validator_name in enumerate(expected):
            if not validator_name.startswith("validate-"):
                continue
            producer = index - 1
            while producer >= 0 and steps[producer][1]:
                producer -= 1
            if producer < 0:
                continue
            command_name = expected[producer]
            command_ok = any(
                event["data"]["step_id"] == command_name
                and event["data"]["action"] == "completed"
                and event["data"].get("exit_code") == 0
                for event in step_events
            )
            validator_failed = any(
                event["data"]["step_id"] == validator_name
                and (
                    event["data"]["action"] == "failed"
                    or event["data"].get("status") == "failed"
                )
                for event in step_events
            )
            if command_ok and validator_failed:
                disagreements.append(
                    {"command": command_name, "validator": validator_name}
                )
        gates = [event for event in events if event["kind"] == "gate"]
        choices = Counter(event["data"]["choice"] for event in gates)
        choices_unobserved = choices.get("unobserved", 0)
        required_gates = [name for name, gate in steps if gate]
        approved_gates = {
            event["data"]["step_id"]
            for event in gates
            if event["data"]["choice"] == "approve"
        }
        gate_missing = [name for name in required_gates if name not in approved_gates]
        recovery = _recovery(events, gates)
        final = result["status"] == "completed"
        result["workflow"] = {
            "required_steps_completed": [
                name for name in expected if name in completed
            ],
            "missing_steps": missing,
            "unknown_steps": unknown_steps,
            "out_of_order": out_of_order,
            "command_validator_disagreements": disagreements,
            "gate_choices": dict(choices),
            "missing_gate_approvals": gate_missing,
            "rejection_recovery": recovery,
            "compliance": "unavailable"
            if choices_unobserved
            else (
                "compliant"
                if final
                and not missing
                and not unknown_steps
                and not gate_missing
                and not out_of_order
                and all(item["status"] == "compliant" for item in recovery)
                else "incomplete_or_noncompliant"
            ),
        }
        reviews = [event for event in events if event["kind"] == "review"]
        independent = [event for event in reviews if _independent(event)]
        findings = [event for event in events if event["kind"] == "finding"]
        latest_findings = {
            (event["data"]["review_id"], event["data"]["finding_id"]): event
            for event in findings
        }
        checks = [event for event in events if event["kind"] == "verification"]
        convergence = [event for event in events if event["kind"] == "convergence"]
        snapshot, freshness = _snapshot_status(root, run_id, feature, events)
        snapshot_tree = snapshot.get("tree") if snapshot else None
        manifest_digest = snapshot.get("manifest_digest") if snapshot else None
        fresh_independent = [
            event
            for event in independent
            if snapshot is not None
            and event["data"].get("snapshot") == snapshot_tree
            and event["data"].get("manifest_digest") == manifest_digest
            and all(
                event["data"].get(key) == snapshot.get(key)
                for key in (
                    "spec_digest",
                    "intent_digest",
                    "plan_digest",
                    "tasks_digest",
                )
            )
        ]
        fresh_convergence = [
            event
            for event in convergence
            if event["source"] == "operator-attested"
            and event["data"].get("snapshot") == snapshot_tree
            and event["data"].get("manifest_digest") == manifest_digest
            and snapshot_tree is not None
            and all(
                event["data"].get(key) == snapshot.get(key)
                for key in (
                    "spec_digest",
                    "intent_digest",
                    "plan_digest",
                    "tasks_digest",
                )
            )
        ]
        manifest_file = (
            archive / "manifests" / f"{manifest_digest}.json"
            if manifest_digest
            else None
        )
        if manifest_file is not None and (
            manifest_file.parent.is_symlink() or manifest_file.is_symlink()
        ):
            fail("symlinked archived acceptance manifest is unavailable")
        manifest_available = manifest_file is not None and manifest_file.is_file()
        manifest_stale = False
        ac: dict[str, str] = {}
        if manifest_available:
            manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
            if (
                not isinstance(manifest, dict)
                or set(manifest) != {"schema_version", "spec_digest", "criteria"}
                or manifest["schema_version"] != 1
            ):
                fail("archived acceptance manifest is invalid")
            if not SHA.fullmatch(manifest["spec_digest"]):
                fail("archived acceptance spec digest is invalid")
            if not isinstance(manifest["criteria"], dict) or not manifest["criteria"]:
                fail("archived acceptance criteria are invalid")
            if manifest_digest != _sha(manifest_file):
                fail("acceptance manifest digest mismatch")
            for ac_id, tests in manifest["criteria"].items():
                if not AC.fullmatch(ac_id) or not isinstance(tests, list) or not tests:
                    fail("archived acceptance mapping is invalid")
                if any(
                    not isinstance(test, str)
                    or not re.fullmatch(
                        r"tests\.test_[A-Za-z0-9_.]+\.test_[A-Za-z0-9_]+", test
                    )
                    for test in tests
                ):
                    fail("archived acceptance test identity is invalid")
                matches = [
                    check
                    for check in checks
                    if check["source"] == "operator-attested"
                    and check["data"].get("ac_id") == ac_id
                    and check["data"]["check_id"] in tests
                    and check["data"].get("snapshot") == snapshot_tree
                    and check["data"].get("spec_digest")
                    == (snapshot or {}).get("spec_digest")
                    and check["data"].get("manifest_digest") == manifest_digest
                ]
                latest = {
                    check["data"]["check_id"]: check["data"]["status"]
                    for check in matches
                }
                older_checks = {
                    check["data"]["check_id"]
                    for check in checks
                    if check["source"] == "operator-attested"
                    and check["data"].get("ac_id") == ac_id
                    and check["data"]["check_id"] in tests
                    and (
                        check["data"].get("manifest_digest") != manifest_digest
                        or check["data"].get("snapshot") != snapshot_tree
                        or check["data"].get("spec_digest")
                        != (snapshot or {}).get("spec_digest")
                    )
                }
                older_mapping = any(
                    check["source"] == "operator-attested"
                    and check["data"].get("ac_id") == ac_id
                    and check["data"].get("manifest_digest") != manifest_digest
                    for check in checks
                )
                ac[ac_id] = (
                    "unavailable"
                    if freshness == "historical"
                    else "stale"
                    if freshness == "stale"
                    else (
                        "passed"
                        if all(latest.get(test) == "passed" for test in tests)
                        else (
                            "failed"
                            if any(latest.get(test) == "failed" for test in tests)
                            else "stale"
                            if any(
                                test not in latest and test in older_checks
                                for test in tests
                            )
                            or (older_mapping and len(latest) < len(tests))
                            else "missing"
                        )
                    )
                )
            if manifest["spec_digest"] != (snapshot or {}).get("spec_digest"):
                ac.clear()
                manifest_available = False
                manifest_stale = True
        passed_ac = sum(value == "passed" for value in ac.values())
        result["outcome"] = {
            "manifest_status": (
                "stale"
                if manifest_stale
                else "archived"
                if manifest_available
                else "unavailable"
            ),
            "ac_total": len(ac) if manifest_available else None,
            "ac_passed": (
                passed_ac if manifest_available and freshness != "historical" else None
            ),
            "ac_status": ac,
            "ac_executable_coverage": (
                f"{passed_ac}/{len(ac)}" if ac and freshness != "historical" else None
            ),
            "first_independent_review": independent[0]["data"]["verdict"]
            if independent
            else None,
            "final_independent_review": independent[-1]["data"]["verdict"]
            if independent
            else None,
            "review_cycles": len(reviews),
            "fresh_independent_review": fresh_independent[-1]["data"]["verdict"]
            if fresh_independent and freshness == "current"
            else None,
            "snapshot_freshness": freshness,
            "material_findings": dict(
                Counter(event["data"]["severity"] for event in latest_findings.values())
            ),
            "finding_resolutions": dict(
                Counter(
                    event["data"]["resolution"] for event in latest_findings.values()
                )
            ),
            "verification": dict(Counter(event["data"]["status"] for event in checks)),
            "final_convergence": convergence[-1]["data"]["verdict"]
            if convergence
            else None,
            "fresh_convergence": fresh_convergence[-1]["data"]["verdict"]
            if fresh_convergence and freshness == "current"
            else None,
        }
        final_acceptance = max(
            (
                event["sequence"]
                for event in gates
                if event["data"]["step_id"] == "final-acceptance"
                and event["data"]["choice"] == "approve"
            ),
            default=0,
        )
        accepted_snapshot = next(
            (
                event["data"]
                for event in reversed(events)
                if event["kind"] == "snapshot" and event["sequence"] < final_acceptance
            ),
            None,
        )
        before_findings = {
            (event["data"]["review_id"], event["data"]["finding_id"]): event
            for event in findings
            if event["sequence"] < final_acceptance
        }
        result["outcome"]["material_findings_before_final_acceptance"] = (
            sum(
                event["data"]["severity"] in {"critical", "high", "medium"}
                for event in before_findings.values()
            )
            if final_acceptance
            else None
        )
        fresh_implementation_review = any(
            event["data"]["kind"] == "implementation"
            and event["data"]["verdict"] == "approved"
            and event["sequence"] < final_acceptance
            for event in fresh_independent
        )
        fresh_convergence_ok = any(
            event["data"]["verdict"] == "CONVERGED"
            and event["sequence"] < final_acceptance
            for event in fresh_convergence
        )
        ac_checks_before_acceptance = all(
            event["sequence"] < final_acceptance
            for event in checks
            if event["data"].get("ac_id") in ac
            and event["data"].get("snapshot") == snapshot_tree
            and event["data"].get("manifest_digest") == manifest_digest
        )
        unresolved_material = any(
            event["data"]["severity"] in {"critical", "high", "medium"}
            and event["data"]["resolution"] != "resolved"
            for event in latest_findings.values()
        )
        if result["workflow"]["compliance"] == "compliant" and (
            freshness == "stale"
            or not fresh_implementation_review
            or not fresh_convergence_ok
            or accepted_snapshot != snapshot
            or not ac_checks_before_acceptance
            or unresolved_material
            or not ac
            or (passed_ac != len(ac) and freshness != "historical")
        ):
            result["workflow"]["compliance"] = "incomplete_or_noncompliant"
        if (
            freshness == "historical"
            and result["workflow"]["compliance"] == "compliant"
        ):
            result["workflow"]["compliance"] = "unavailable"
        cross = [
            event
            for event in independent
            if event["data"].get("author_provider")
            and event["data"].get("reviewer_provider")
            and event["data"]["author_provider"] != event["data"]["reviewer_provider"]
        ]
        routes = [
            event
            for event in events
            if event["kind"] == "route" and event["source"] != "agent-reported"
        ]
        comparisons = [
            _policy_comparison(root, run_id, event, events) for event in routes
        ]
        underpowered = _underpowered(routes)
        result["routing"] = {
            "actual_routes": [event["data"] for event in routes],
            "agent_reported_routes": sum(
                event["kind"] == "route" and event["source"] == "agent-reported"
                for event in events
            ),
            "route_sources": dict(
                Counter(event["data"]["route_source"] for event in routes)
            ),
            "escalations": [
                event["data"] for event in events if event["kind"] == "escalation"
            ],
            "policy_comparisons": comparisons,
            "policy_overpowered_signals": sum(
                item.get("value", {}).get("above_default_without_reason", False)
                for item in comparisons
            ),
            "underpowered_signals": underpowered,
            "independent_reviews": len(independent),
            "cross_provider_reviews": len(cross),
            "review_provider_availability": [
                {
                    "review_id": event["data"]["review_id"],
                    "alternate_available": event["data"].get("alternate_available"),
                    "independent": _independent(event),
                    "cross_provider": event in cross,
                }
                for event in reviews
            ],
        }
        result["efficiency"] = _usage(
            events, None if freshness == "historical" else passed_ac
        )
        human = [
            event
            for event in events
            if event["kind"] == "human_action" and event["source"] != "agent-reported"
        ]
        result["human_effort"] = {
            "gate_approvals": choices.get("approve", 0),
            "gate_rejections": choices.get("reject", 0),
            "manual_recovery": sum(
                event["data"]["action"] == "manual_recovery" for event in human
            ),
            "route_overrides": sum(
                event["data"]["action"] == "route_override" for event in human
            ),
            "product_decisions_requested": sum(
                event["data"]["action"] == "product_decision"
                and event["data"].get("gate_id") in required_gates
                for event in human
            ),
        }
    except (OSError, ValueError, KeyError, TypeError) as error:
        result["problems"].append(str(error))
        result["status"] = "invalid"
    return result


def _chat_report(
    root: Path, run_id: str, events: list[dict[str, Any]], result: dict[str, Any]
) -> dict[str, Any]:
    """Report a Chat run (#20) against its archived definition and phase graph.

    Reads `run/workflow.yml` and `run/chat.json`, never engine state: every
    producer step's latest entry completed, and every gate's latest choice
    `approve`, made after the latest completion of the steps it covers.
    """
    archive = archive_dir(root, run_id) / "run"
    if archive.is_symlink():
        fail("symlinked archived run is unavailable")
    with archive_lock(root, run_id, exclusive=False):
        graph = json.loads((archive / "chat.json").read_text(encoding="utf-8"))
        definition = archive / "workflow.yml"
        digest = _sha(definition) if definition.is_file() else None
    runs = [event for event in events if event["kind"] == "run"]
    if digest != runs[0]["data"].get("workflow_digest"):
        fail("workflow definition digest mismatch")
    producers = [
        phase["step_id"] for phase in graph["phases"].values() if phase.get("step_id")
    ]
    gate_ids = {gate["gate_id"]: gate["covers"] for gate in graph["gates"].values()}
    latest: dict[str, str] = {}
    completed_at: dict[str, int] = {}
    choice: dict[str, tuple[str, int]] = {}
    for event in events:
        data = event["data"]
        if event["kind"] == "step" and data["step_id"] not in gate_ids:
            if data["action"] == "started":
                continue
            ok = data["action"] == "completed" and data.get("status") == "completed"
            latest[data["step_id"]] = "completed" if ok else "failed"
            if ok:
                completed_at[data["step_id"]] = event["sequence"]
        elif event["kind"] == "gate":
            choice[data["step_id"]] = (data["choice"], event["sequence"])
    missing = [step for step in producers if latest.get(step) != "completed"]
    missing_gates = [
        gate for gate in gate_ids if choice.get(gate, ("", 0))[0] != "approve"
    ]
    stale_gates = [
        gate
        for gate, covers in gate_ids.items()
        if choice.get(gate, ("", 0))[0] == "approve"
        and any(completed_at.get(step, 0) > choice[gate][1] for step in covers)
    ]
    final = choice.get("final-acceptance", ("", 0))[0] == "approve"
    gates = [event for event in events if event["kind"] == "gate"]
    choices = Counter(event["data"]["choice"] for event in gates)
    reviews = [event for event in events if event["kind"] == "review"]
    checks = [event for event in events if event["kind"] == "verification"]
    result["status"] = "completed" if final and not stale_gates else "incomplete"
    result["mode"] = "chat"
    result["workflow"] = {
        "mode": "chat",
        "mode_history": [
            {
                "mode": event["data"].get("mode"),
                "change": event["data"].get("status", "started"),
                "sequence": event["sequence"],
            }
            for event in runs
        ],
        "required_steps_completed": [s for s in producers if s not in missing],
        "missing_steps": missing,
        "gate_choices": dict(choices),
        "missing_gate_approvals": missing_gates,
        "stale_gate_approvals": stale_gates,
        "compliance": "compliant"
        if final and not missing and not missing_gates and not stale_gates
        else "incomplete_or_noncompliant",
    }
    result["outcome"] = {
        "reviews": [
            {
                "kind": event["data"]["kind"],
                "verdict": event["data"]["verdict"],
                "reviewer_provider": event["data"].get("reviewer_provider"),
                "cross_provider": event["data"].get("reviewer_provider")
                != event["data"].get("author_provider"),
            }
            for event in reviews
        ],
        "verification": dict(Counter(event["data"]["status"] for event in checks)),
    }
    result["human_effort"] = {
        "gate_approvals": choices.get("approve", 0),
        "gate_rejections": choices.get("reject", 0),
    }
    return result


def aggregate(root: Path, feature: str | None = None) -> dict[str, Any]:
    """Compare only instrumented runs in the shared local archive."""
    parent = common_dir(root) / "speckit-runs"
    runs = []
    if parent.is_dir():
        for path in sorted(parent.iterdir()):
            if (
                path.is_dir()
                and not path.is_symlink()
                and RUN_ID_PATTERN.fullmatch(path.name)
                and (path / "events.jsonl").is_file()
            ):
                item = report(root, path.name)
                if feature is None or item.get("feature") == feature:
                    runs.append(item)
    rework_by_stage: Counter[str] = Counter()
    escalation_by_stage: Counter[str] = Counter()
    recovery: Counter[str] = Counter()
    classifier_tokens = 0
    classifier_runs = 0
    pre_acceptance_findings = 0
    pre_acceptance_runs = 0
    rework_runs = 0
    for item in runs:
        routing = item.get("routing", {})
        escalation_by_stage.update(
            event["stage"] for event in routing.get("escalations", [])
        )
        recovery.update(
            event["status"]
            for event in item.get("workflow", {}).get("rejection_recovery", [])
        )
        outcome = item.get("outcome", {})
        pre_acceptance = outcome.get("material_findings_before_final_acceptance")
        if pre_acceptance is not None:
            pre_acceptance_findings += pre_acceptance
            pre_acceptance_runs += 1
        efficiency = item.get("efficiency", {})
        if efficiency.get("status") != "available":
            continue
        value = efficiency["value"]
        rework = value.get("rework", {})
        if rework.get("status") == "available":
            rework_runs += 1
            rework_by_stage.update(rework["value"].get("by_stage", {}))
        classifier = value.get("classifier_tokens", {})
        if classifier.get("status") == "available":
            classifier_runs += 1
            classifier_tokens += classifier["value"]
    return {
        "instrumented_runs": len(runs),
        "runs": runs,
        "statuses": dict(Counter(item["status"] for item in runs)),
        "workflow_compliance": dict(
            Counter(
                item.get("workflow", {}).get("compliance", "unavailable")
                for item in runs
            )
        ),
        "policy_overpowered_signals": sum(
            item.get("routing", {}).get("policy_overpowered_signals", 0)
            for item in runs
        ),
        "underpowered_signals": sum(
            len(item.get("routing", {}).get("underpowered_signals", []))
            for item in runs
        ),
        "material_findings": sum(
            sum(item.get("outcome", {}).get("material_findings", {}).values())
            for item in runs
        ),
        "material_findings_before_final_acceptance": {
            "count": pre_acceptance_findings,
            "runs_with_evidence": pre_acceptance_runs,
        },
        "rework_by_stage": {
            "tokens": dict(rework_by_stage),
            "runs_with_evidence": rework_runs,
        },
        "escalations_by_stage": dict(escalation_by_stage),
        "rejection_recovery": dict(recovery),
        "classifier_overhead": {
            "tokens": classifier_tokens,
            "runs_with_evidence": classifier_runs,
        },
        "dimension_unavailable": {
            name: sum(name not in item for item in runs)
            for name in ("outcome", "workflow", "routing", "efficiency", "human_effort")
        },
    }


def _text_report(data: dict[str, Any]) -> str:
    if "runs" in data:
        lines = [f"Instrumented runs: {data['instrumented_runs']}"]
        for run in data["runs"]:
            workflow = run.get("workflow", {}).get("compliance", "unavailable")
            coverage = run.get("outcome", {}).get("ac_executable_coverage")
            lines.append(
                f"{run['run_id']}: {run['status']} | workflow {workflow} | "
                f"AC {coverage or 'unavailable'}"
            )
        lines.append(
            f"Policy-overpowered signals: {data['policy_overpowered_signals']}"
        )
        lines.append(f"Underpowered signals: {data['underpowered_signals']}")
        lines.append(f"Rework by stage: {json.dumps(data['rework_by_stage'])}")
        lines.append(
            f"Escalations by stage: {json.dumps(data['escalations_by_stage'])}"
        )
        lines.append(f"Rejection recovery: {json.dumps(data['rejection_recovery'])}")
        lines.append(f"Classifier overhead: {json.dumps(data['classifier_overhead'])}")
        lines.append(
            "Material findings before final acceptance: "
            + json.dumps(data["material_findings_before_final_acceptance"])
        )
        return "\n".join(lines)
    lines = [f"Run {data['run_id']}: {data['status']}"]
    if data.get("problems"):
        lines.extend(f"Problem: {problem}" for problem in data["problems"])
    for name in (
        "outcome",
        "workflow",
        "routing",
        "efficiency",
        "human_effort",
        "pull_request",
        "branch_sync",
        "acceptance_packet",
        "demo_capture",
    ):
        if name in data:
            lines.append(f"{name}: {json.dumps(data[name], sort_keys=True)}")
    return "\n".join(lines)


def _feature_for_run(root: Path, run_id: str) -> str:
    events, problems = read(root, run_id)
    if problems:
        fail("invalid ledger: " + "; ".join(problems))
    if events:
        return events[0]["feature"]
    return json.loads(
        (_run_files(root, run_id) / "inputs.json").read_text(encoding="utf-8")
    )["inputs"]["feature_directory"]


def _operator_step_guard() -> None:
    """Catch accidental operator attestations from a normal agent step."""
    if os.environ.get("BALLAST_SPEC_WORKFLOW") or os.environ.get(
        "SPECKIT_WORKFLOW_RUN_ID"
    ):
        fail("operator attestation is unavailable inside an agent step")


def _record(  # noqa: C901, PLR0913, PLR0917 - Validate fixed observation fields.
    root: Path, run_id: str, feature: str, kind: str, source: str, data: dict[str, Any]
) -> None:
    if not isinstance(data, dict):
        fail("observation data must be an object")
    if kind in RUNNER_ONLY:
        fail("this observation must come from the runner or snapshot command")
    if kind == "verification" and data.get("ac_id"):
        fail("AC verification must use the check command")
    if source == "operator-attested":
        _operator_step_guard()
    if not FEATURE_PATTERN.fullmatch(feature) or feature != _feature_for_run(
        root, run_id
    ):
        fail("feature does not match the run")
    if kind == "route" and data.get("policy_row"):
        policy = archive_policy(root, run_id)
        if policy is None or data["policy_row"] not in policy["rows"]:
            fail("policy row is not in the archived policy")
    if kind in {"review", "convergence"} or (
        kind == "verification" and data.get("status") == "passed"
    ):
        current = artifact_digests(root, feature)
        bound = (
            ("snapshot", "manifest_digest")
            if kind != "verification"
            else ("snapshot", "spec_digest")
        )
        if kind in {"review", "convergence"}:
            bound += ("spec_digest", "intent_digest", "plan_digest", "tasks_digest")
        if any(
            data.get(key) != current.get("tree" if key == "snapshot" else key)
            for key in bound
        ):
            fail("successful evidence must bind to current artifact digests")
    append(root, new_event(run_id, feature, kind, source, data))


def _check(root: Path, run_id: str, ac_id: str, test_id: str) -> int:
    _operator_step_guard()
    if os.path.lexists(root / TAMPER_MARKER):
        fail(f"{TAMPER_MARKER} exists; restore the checkout and recreate .venv")
    feature = _feature_for_run(root, run_id)
    snapshot = artifact_digests(root, feature)
    append(root, new_event(run_id, feature, "snapshot", "operator-attested", snapshot))
    manifest = archive_manifest(root, run_id, feature)
    if ac_id not in manifest["criteria"] or test_id not in manifest["criteria"][ac_id]:
        fail("test is not mapped to this AC")
    python = root / ".venv/bin/python"
    result = subprocess.run(  # noqa: S603
        [str(python), "-c", UNITTEST_CHECK, test_id], cwd=root, check=False
    )
    unchanged = artifact_digests(root, feature) == snapshot
    status = "passed" if result.returncode == 0 and unchanged else "failed"
    # The checked code is exactly HEAD's only when the checkout is clean.
    commit = (
        {"commit": _git(root, "rev-parse", "--verify", "HEAD^{commit}")}
        if _has_head(root) and commit_tree(root, "HEAD") == snapshot["tree"]
        else {}
    )
    append(
        root,
        new_event(
            run_id,
            feature,
            "verification",
            "operator-attested",
            {
                "check_id": test_id,
                "ac_id": ac_id,
                "status": status,
                "exit_code": abs(result.returncode),
                "snapshot": snapshot["tree"],
                "spec_digest": snapshot["spec_digest"],
                "manifest_digest": snapshot["manifest_digest"],
                **commit,
            },
        ),
    )
    return result.returncode or (0 if unchanged else 1)


def main(argv: list[str] | None = None) -> int:  # noqa: C901, PLR0915 - CLI branches.
    """Handle local import, observation, verification, and report commands."""
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    importer = sub.add_parser("import", help="Import new runner events")
    importer.add_argument("run_id")
    recorder = sub.add_parser("record", help="Append bounded explicit evidence")
    recorder.add_argument("run_id")
    recorder.add_argument("kind", choices=sorted(FIELDS.keys() - RUNNER_ONLY))
    recorder.add_argument(
        "--source", required=True, choices=sorted(SOURCES - {"runner"})
    )
    recorder.add_argument(
        "--data", required=True, help="A JSON object using only schema fields"
    )
    snapshot = sub.add_parser(
        "snapshot", help="Record current implementation and artifact digests"
    )
    snapshot.add_argument("run_id")
    checker = sub.add_parser(
        "check", help="Run one mapped unittest case and record its result"
    )
    checker.add_argument("run_id")
    checker.add_argument("ac_id")
    checker.add_argument("test_id")
    reporter = sub.add_parser("report", help="Report one run/feature or all local runs")
    reporter.add_argument("target", nargs="?")
    reporter.add_argument("--run")
    reporter.add_argument("--all", action="store_true")
    reporter.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "import":
            count = import_run(ROOT, args.run_id, at_invocation_end=False)
            sys.stdout.write(f"imported {count} event(s)\n")
            return 0
        if args.command == "record":
            _record(
                ROOT,
                args.run_id,
                _feature_for_run(ROOT, args.run_id),
                args.kind,
                args.source,
                json.loads(args.data),
            )
            return 0
        if args.command == "snapshot":
            _operator_step_guard()
            feature = _feature_for_run(ROOT, args.run_id)
            append(
                ROOT,
                new_event(
                    args.run_id,
                    feature,
                    "snapshot",
                    "operator-attested",
                    artifact_digests(ROOT, feature),
                ),
            )
            try:
                _archive_manifest_if_present(ROOT, args.run_id, feature)
            except (OSError, ValueError, KeyError, TypeError) as error:
                sys.stderr.write(f"acceptance manifest unavailable: {error}\n")
            return 0
        if args.command == "check":
            return _check(ROOT, args.run_id, args.ac_id, args.test_id)
        if args.all:
            data = aggregate(ROOT)
        elif args.run:
            data = report(ROOT, args.run)
        elif args.target:
            if not FEATURE_PATTERN.fullmatch(args.target):
                fail("target must be specs/<issue>-<slug>")
            data = aggregate(ROOT, args.target)
        else:
            fail("report needs --run, --all, or a feature directory")
        sys.stdout.write(
            json.dumps(data, indent=2, sort_keys=True)
            if args.json
            else _text_report(data)
        )
        sys.stdout.write("\n")
        return (
            0
            if not any(
                item.get("status") == "invalid" for item in data.get("runs", [data])
            )
            else 1
        )
    except (LedgerError, OSError, ValueError, KeyError, TypeError) as error:
        sys.stderr.write(f"agent ledger: {error}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
