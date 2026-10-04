"""Operator records and trusted actions for Autonomous runs.

An Autonomous run replaces every human gate of ballast-feature with an agent
decision that is recorded as provisional; the human approves once, at merge.
Everything that grants or records authority lives here, in operator state that
no agent can write (`state_dir(root)/runs/<run-id>/`):

- the run record (`run.json`): mode history, risk, eligibility, limits;
- the hash-chained decision logs (`decisions.jsonl`, `human-decisions.jsonl`);
- the current block (`block.json`) and earlier blocks (`blocks.jsonl`).

The committed `specs/<f>/autonomous/record.md` and the Draft PR body are
deterministic projections of these records. This module also checks
eligibility, builds the bubblewrap confinement for agent steps, and publishes
the Draft PR as the operator. It uses only the standard library and runs under
`python3 -I -S`; see specs/27-autonomous-core/ for the contracts.
"""

from __future__ import annotations

import hashlib
import html
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import tomllib
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from types import ModuleType

# Never read or write checkout bytecode, including for the import below.
sys.pycache_prefix = os.devnull

from launcher import state_dir  # noqa: E402

VERSION = 1
RUN_ID = re.compile(r"[A-Za-z0-9_-]{1,64}")
FEATURE = re.compile(r"specs/([1-9][0-9]*)-[a-z0-9]+(?:-[a-z0-9]+)*")
MODES = ("human-gated", "autonomous")
WORKFLOWS = ("ballast-feature", "ballast-autonomous", "ballast-continue")
INTEGRATIONS = ("claude", "codex")
STATUSES = ("active", "stopped", "completed", "published", "continued")
# Only trusted code moves a run; `stopped` reaches `published` only through
# `ballast run publish` after a forge block.
TRANSITIONS = {
    "active": {"stopped", "completed"},
    "completed": {"published", "stopped", "continued"},
    "stopped": {"published", "continued"},
    "published": {"continued"},
    "continued": set(),
}

DECISION_POINTS = (
    "scope",
    "clarification",
    "intent",
    "plan",
    "plan-review",
    "tasks",
    "implementation-review",
    "specialist-review",
    "decision-resolution",
    "spec-reconciliation",
    "final-acceptance",
)
MULTI_ENTRY = ("clarification", "decision-resolution", "specialist-review")
# Points with exactly one current decision before final acceptance (SC-002).
SINGLE_POINTS = tuple(
    point
    for point in DECISION_POINTS
    if point not in MULTI_ENTRY and point != "final-acceptance"
)
REVIEW_POINTS = (
    "plan-review",
    "implementation-review",
    "specialist-review",
    "spec-reconciliation",
)
POINT_DECISION = {
    "scope": "accept",
    "intent": "accept",
    "plan": "accept",
    "tasks": "accept",
    "final-acceptance": "accept",
    "clarification": "assume",
    "decision-resolution": "resolve",
    **dict.fromkeys(REVIEW_POINTS, "accept-finding"),
}
DECISION_KINDS = ("accept", "assume", "resolve", "accept-finding")
BLOCK_CATEGORIES = (
    "decision",
    "contradiction",
    "review-finding",
    "limit",
    "postcondition",
    "tamper",
    "unfinished-step",
    "permission",
    "ineligible",
    "forge",
    "interrupted",
)
REVIEW_KINDS = (
    "plan",
    "engineering",
    "test",
    "security",
    "documentation",
    "architecture",
    "dependency",
    "database-migration",
    "spec-reconciliation",
)
VERDICTS = ("approved", "changes-requested", "partial", "failed")
SEVERITIES = ("critical", "high", "medium", "low", "info")
BLOCKING_SEVERITIES = ("critical", "high")
FINDING_LABELS = (
    "spec-violation",
    "implementation-bug",
    "architecture-issue",
    "missing-test",
    "spec-ambiguity",
    "proposed-product-change",
)
DISPOSITIONS = ("resolved", "accepted-provisionally", "open")
HUMAN_DECISION_KINDS = ("mode-change", "block-resolution", "merge-feedback")

REFUSAL = "not eligible for autonomous: "
CANNOT_CHECK = "cannot check autonomous eligibility: "
BRANCH_REFUSAL = "autonomous needs a feature branch without an open PR"
ORIGIN_REFUSAL = "origin is not the GitHub repository pinned in ballast.toml"
RESUME_REFUSAL = (
    "autonomous resume is not supported until safe resume (#18); continue "
    "human-gated: ballast run continue {run_id} --reason block-resolved --ref TEXT"
)
HUMAN_GATED_ALTERNATIVE = (
    "Run it human-gated instead: ballast run start -i idea=... -i feature_directory=..."
)
WIDENING = "ignored [autonomous] {key}: cannot widen eligibility"

WALL_TIME = (1, 1440, 240)
AGENT_STEPS = (1, 200, 30)
CHECK_TIMEOUT = (1, 240, 30)
RISKS = ("R0", "R1", "R2")
NEVER_AUTHORIZED = ("merge", "release", "deploy", "mark ready")
POLICY_KEYS = (
    "risk",
    "excluded_boundaries",
    "authorized_privileged_actions",
    "wall_time_minutes",
    "max_agent_steps",
)
# AC-007: no agent text or rendered record may claim a human approval.
HUMAN_APPROVAL = re.compile(
    r"(?i)\b(human[- ]approved|approved by (the )?(human|operator|user))\b"
)
WORKFLOW_MARKER = re.compile(r"<!--\s*workflow-", re.IGNORECASE)
GIT_HARDENING = ("-c", "core.hooksPath=/dev/null", "-c", "core.fsmonitor=false")
PROTECTED = ("ballast.toml", ".ballast", ".specify", ".venv")
# Spec Kit state that agent steps write; bound writable inside the sandbox.
SPECIFY_WRITABLE = ("feature.json", "extensions/.cache", "workflows/.cache")
SCOPE_COMMENT = "<!-- ballast-intake: issue=#{issue};"
SCOPE_AUTHORS = ("OWNER", "MEMBER", "COLLABORATOR")
MAX_PUBLISHED_FILE = 1024 * 1024
MAX_BODY = 60000
ZERO = "0" * 64

CREDENTIAL_DIRS = (
    ".config",
    ".ssh",
    ".gnupg",
    ".docker",
    ".aws",
    ".kube",
    ".local/share/keyrings",
)
CREDENTIAL_FILES = (".git-credentials", ".netrc", ".pypirc")
SECRET_NAME = re.compile(r"TOKEN|SECRET|PASSWORD|CREDENTIAL|API_KEY|AUTH")
SECRET_VARIABLES = ("SSH_AUTH_SOCK", "GPG_AGENT_INFO", "GIT_ASKPASS")
# Variables that relocate gh or Git credentials: cleared for the agent, and
# the directories they name are hidden like CREDENTIAL_DIRS.
CREDENTIAL_LOCATIONS = ("GH_CONFIG_DIR", "XDG_CONFIG_HOME")
INTEGRATION_KEYS = {
    "claude": ("ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN"),
    "codex": ("OPENAI_API_KEY", "CODEX_API_KEY"),
}
CREDENTIAL_URL = re.compile(r"https?://[^/\s@]+@", re.IGNORECASE)
PROGRAM_KEYS = (
    "gpg.program",
    "gpg.ssh.program",
    "gpg.x509.program",
    "core.sshcommand",
    "credential.helper",
    "core.askpass",
    "include.path",
)
INCLUDE_IF = re.compile(r"includeif\..+\.path")
EXTRA_HEADER = re.compile(r"http\.(?:.+\.)?extraheader")


class AutonomyError(Exception):
    """A refusal or block; `category` names the block category it maps to."""

    def __init__(self, message: str, category: str = "postcondition") -> None:
        """Keep the message and the block category."""
        super().__init__(message)
        self.category = category


def now() -> str:
    """Return the current UTC time, to the second."""
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _parse_time(value: str) -> datetime:
    try:
        moment = datetime.fromisoformat(value)
    except (TypeError, ValueError) as error:
        message = f"invalid timestamp {value!r}"
        raise AutonomyError(message) from error
    if moment.tzinfo is None:
        message = f"timestamp {value!r} has no time zone"
        raise AutonomyError(message)
    return moment


def sha256_file(path: Path) -> str:
    """SHA-256 of a regular file, never through a symlink."""
    return hashlib.sha256(_read_bytes(path)).hexdigest()


# --- Operator files -------------------------------------------------------


def run_dir(root: Path, run_id: str) -> Path:
    """Operator directory of one run, outside every agent's write authority."""
    if not RUN_ID.fullmatch(run_id or ""):
        message = f"invalid run id {run_id!r}"
        raise AutonomyError(message)
    return state_dir(root) / "runs" / run_id


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.is_symlink() or not path.is_dir():
        message = f"{path} must be a real directory"
        raise AutonomyError(message)


def _read_bytes(path: Path) -> bytes:
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as handle:
        return handle.read()


def _write_bytes(path: Path, data: bytes) -> None:
    """Replace path atomically; a temporary file is never followed."""
    _ensure_dir(path.parent)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        Path(temporary).replace(path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


def write_json(path: Path, data: object) -> None:
    """Write operator JSON atomically."""
    text = json.dumps(data, indent=2, sort_keys=True) + "\n"
    _write_bytes(path, text.encode())


def read_json(path: Path, what: str) -> object:
    """Read operator JSON; missing, linked or malformed is a refusal."""
    try:
        data = _read_bytes(path)
    except FileNotFoundError as error:
        message = f"{what} is missing"
        raise AutonomyError(message) from error
    except OSError as error:
        message = f"{what} is unreadable: {error}"
        raise AutonomyError(message) from error
    try:
        return json.loads(data)
    except ValueError as error:
        message = f"{what} is malformed: {error}"
        raise AutonomyError(message) from error


# --- Run record -----------------------------------------------------------


def new_run(  # noqa: PLR0913 - one record, every field explicit
    *,
    run_id: str,
    feature: str,
    issue: int,
    workflow: str,
    mode: str,
    integration: str,
    review_integration: str | None = None,
    risk: dict | None = None,
    eligibility: dict | None = None,
    limits: dict | None = None,
    continues: str | None = None,
    reason: str | None = None,
) -> dict:
    """Build a fresh, validated run record with status `active`."""
    review = review_integration or integration
    record = {
        "version": VERSION,
        "run_id": run_id,
        "feature": feature,
        "issue": issue,
        "workflow": workflow,
        "mode_history": [
            {
                "mode": mode,
                "at": now(),
                "by": "operator",
                "action": "start",
                "reason": reason,
                "decision_id": None,
            }
        ],
        "status": "active",
        "agent_steps": 0,
        "integration": integration,
        "review_integration": review,
        "cross_provider": review != integration,
        "continues": continues,
        "started_at": now(),
    }
    if risk is not None:
        record["risk"] = risk
    if eligibility is not None:
        record["eligibility"] = eligibility
    if limits is not None:
        record["limits"] = limits
    return validate_run(record, run_id)


def _require(condition: bool, message: str) -> None:  # noqa: FBT001
    if not condition:
        raise AutonomyError(message)


def _validate_mode_history(history: object) -> None:
    _require(
        isinstance(history, list) and bool(history), "run record has no mode history"
    )
    assert isinstance(history, list)  # noqa: S101 - narrowed above
    for index, change in enumerate(history):
        _require(isinstance(change, dict), "mode change must be an object")
        _require(change.get("mode") in MODES, "mode change has an unknown mode")
        _require(change.get("by") == "operator", "only the operator changes a mode")
        _parse_time(change.get("at"))
        action = change.get("action")
        if index == 0:
            _require(action == "start", "the first mode change must be the start")
        else:
            _require(action == "lower", "a later mode change can only lower")
            _require(
                history[index - 1]["mode"] == "autonomous"
                and change["mode"] == "human-gated",
                "a mode can only be lowered from autonomous to human-gated",
            )


def validate_run(record: object, run_id: str) -> dict:
    """Check a run record strictly; any doubt is a refusal."""
    _require(isinstance(record, dict), "run record must be an object")
    assert isinstance(record, dict)  # noqa: S101 - narrowed above
    _require(record.get("version") == VERSION, "run record has an unknown version")
    _require(
        record.get("run_id") == run_id and bool(RUN_ID.fullmatch(run_id)),
        "run record does not belong to this run",
    )
    match = FEATURE.fullmatch(str(record.get("feature")))
    _require(match is not None, "run record has an invalid feature directory")
    assert match is not None  # noqa: S101 - narrowed above
    issue = record.get("issue")
    _require(
        isinstance(issue, int) and not isinstance(issue, bool),
        "run record has no issue number",
    )
    _require(issue == int(match.group(1)), "run record issue differs from feature")
    _require(record.get("workflow") in WORKFLOWS, "run record has an unknown workflow")
    _validate_mode_history(record.get("mode_history"))
    _require(record.get("status") in STATUSES, "run record has an unknown status")
    steps = record.get("agent_steps")
    _require(
        isinstance(steps, int) and not isinstance(steps, bool) and steps >= 0,
        "run record has an invalid step count",
    )
    _require(
        record.get("integration") in INTEGRATIONS
        and record.get("review_integration") in INTEGRATIONS,
        "run record has an unknown integration",
    )
    _require(
        isinstance(record.get("cross_provider"), bool),
        "run record has no cross-provider flag",
    )
    _require(
        record.get("integration_fallback") in {None, CODEX_FALLBACK},
        "run record has an unknown integration fallback",
    )
    continues = record.get("continues")
    _require(
        continues is None or bool(RUN_ID.fullmatch(str(continues))),
        "run record continues an invalid run",
    )
    if record["workflow"] == "ballast-autonomous":
        for key in ("risk", "eligibility", "limits"):
            _require(
                isinstance(record.get(key), dict), f"autonomous run record lacks {key}"
            )
        _require(record["risk"].get("level") in RISKS, "run record has an unknown risk")
        _parse_time(record["limits"].get("deadline"))
    return record


def run_file(root: Path, run_id: str) -> Path:
    """Path of a run's record."""
    return run_dir(root, run_id) / "run.json"


def write_run(root: Path, record: dict) -> None:
    """Validate and atomically store a run record."""
    validate_run(record, record.get("run_id", ""))
    write_json(run_file(root, record["run_id"]), record)


def read_run(root: Path, run_id: str) -> dict:
    """Read and validate a run record."""
    return validate_run(read_json(run_file(root, run_id), "run record"), run_id)


def find_run(root: Path, run_id: str) -> dict | None:
    """Return the run record when one exists; a broken one is still a refusal."""
    if not RUN_ID.fullmatch(run_id or ""):
        return None
    if not os.path.lexists(run_file(root, run_id)):
        return None
    return read_run(root, run_id)


def effective_mode(record: dict) -> str:
    """Return the mode of the last change."""
    return record["mode_history"][-1]["mode"]


def set_status(record: dict, status: str) -> dict:
    """Move a run along its legal transitions only."""
    if status not in TRANSITIONS.get(record["status"], set()):
        message = (
            f"run {record['run_id']} cannot go from {record['status']} to {status}"
        )
        raise AutonomyError(message)
    record["status"] = status
    return record


def change_mode(
    record: dict, mode: str, *, reason: str | None, decision_id: str | None
) -> dict:
    """Append a mode change; only lowering a paused Autonomous run exists."""
    if mode not in MODES:
        message = f"unknown mode {mode!r}"
        raise AutonomyError(message)
    if mode == "autonomous" or effective_mode(record) != "autonomous":
        message = "raising a run's autonomy after start is refused"
        raise AutonomyError(message, "ineligible")
    if record["status"] == "active":
        message = "only a paused autonomous run can be lowered"
        raise AutonomyError(message)
    record["mode_history"].append(
        {
            "mode": "human-gated",
            "at": now(),
            "by": "operator",
            "action": "lower",
            "reason": reason,
            "decision_id": decision_id,
        }
    )
    return validate_run(record, record["run_id"])


# --- Hash-chained logs ----------------------------------------------------


def read_log(path: Path, prefix: str) -> list[dict]:
    """Read an append-only log, verifying sequence and hash chain."""
    if not os.path.lexists(path):
        return []
    try:
        data = _read_bytes(path)
    except OSError as error:
        message = f"{path.name} is unreadable: {error}"
        raise AutonomyError(message) from error
    if data and not data.endswith(b"\n"):
        message = (
            f"{path.name} ends without a newline; a partly recorded entry is "
            "not complete"
        )
        raise AutonomyError(message)
    entries = []
    previous = ZERO
    for index, line in enumerate(data.splitlines(keepends=True), start=1):
        try:
            entry = json.loads(line)
        except ValueError as error:
            message = f"{path.name} line {index} is malformed"
            raise AutonomyError(message) from error
        if not isinstance(entry, dict) or entry.get("id") != f"{prefix}-{index:04d}":
            message = f"{path.name} line {index} is out of sequence"
            raise AutonomyError(message)
        if entry.get("prev") != previous:
            message = f"{path.name} line {index} breaks the hash chain"
            raise AutonomyError(message)
        previous = hashlib.sha256(line).hexdigest()
        entries.append(entry)
    return entries


def append_log(path: Path, prefix: str, entry: dict) -> dict:
    """Append one entry after the verified chain; never rewrite a line."""
    entries = read_log(path, prefix)
    previous = ZERO
    if entries:
        last = _read_bytes(path).splitlines(keepends=True)[-1]
        previous = hashlib.sha256(last).hexdigest()
    entry = {
        **{k: v for k, v in entry.items() if k not in {"id", "prev"}},
        "id": f"{prefix}-{len(entries) + 1:04d}",
        "prev": previous,
    }
    line = json.dumps(entry, sort_keys=True, separators=(",", ":")) + "\n"
    _ensure_dir(path.parent)
    flags = os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW
    fd = os.open(path, flags, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(line.encode())
        handle.flush()
        os.fsync(handle.fileno())
    return entry


def read_decisions(root: Path, run_id: str) -> list[dict]:
    """Every provisional decision of a run, in log order."""
    return read_log(run_dir(root, run_id) / "decisions.jsonl", "PD")


def read_human_decisions(root: Path, run_id: str) -> list[dict]:
    """Every human decision of a run, in log order."""
    return read_log(run_dir(root, run_id) / "human-decisions.jsonl", "HD")


def superseded(entries: list[dict]) -> dict[str, str]:
    """Map each superseded decision ID to the ID that replaced it."""
    return {e["supersedes"]: e["id"] for e in entries if e.get("supersedes")}


def current_decisions(entries: list[dict]) -> list[dict]:
    """Decisions not replaced by a later one."""
    replaced = superseded(entries)
    return [entry for entry in entries if entry["id"] not in replaced]


def current(entries: list[dict], point: str) -> list[dict]:
    """Return the current decisions for one point."""
    return [e for e in current_decisions(entries) if e.get("point") == point]


def append_decision(root: Path, run_id: str, entry: dict) -> dict:
    """Append a provisional decision; a replacement must name a current one."""
    path = run_dir(root, run_id) / "decisions.jsonl"
    entries = read_log(path, "PD")
    if entry.get("point") not in DECISION_POINTS:
        message = f"unknown decision point {entry.get('point')!r}"
        raise AutonomyError(message)
    if entry.get("decision") not in DECISION_KINDS:
        message = f"unknown decision {entry.get('decision')!r}"
        raise AutonomyError(message)
    replaces = entry.get("supersedes")
    if replaces is not None:
        if replaces not in {e["id"] for e in entries}:
            message = f"supersedes unknown decision {replaces}"
            raise AutonomyError(message)
        if replaces in superseded(entries):
            message = f"{replaces} is already superseded"
            raise AutonomyError(message)
    return append_log(path, "PD", entry)


def append_human_decision(
    root: Path, run_id: str, kind: str, ref: str, *, resolves: str | None
) -> dict:
    """Record an operator decision against a run."""
    if kind not in HUMAN_DECISION_KINDS:
        message = f"unknown human decision kind {kind!r}"
        raise AutonomyError(message)
    if not isinstance(ref, str) or not 1 <= len(ref.strip()) <= 500:  # noqa: PLR2004
        message = "--ref must be 1-500 characters"
        raise AutonomyError(message)
    entry = {
        "kind": kind,
        "ref": ref.strip(),
        "resolves": resolves,
        "at": now(),
        "by": "operator",
    }
    path = run_dir(root, run_id) / "human-decisions.jsonl"
    return append_log(path, "HD", entry)


# --- Agent steps and drafts -----------------------------------------------
#
# The wrapper appends one line per Autonomous agent step to `steps.jsonl` and
# keeps a copy of every draft the step created under `drafts/<step>/`. A
# recorder consumes the steps after its cursor, so a draft is attributed only
# to the step that wrote it (workflow contract, round 6 H-3).


def drafts_dir(root: Path, feature: str) -> Path:
    """Agent-writable directory for decision drafts."""
    return root / feature / "autonomous" / "drafts"


def append_step(root: Path, run_id: str, entry: dict) -> None:
    """Record one agent step (written by the wrapper only)."""
    path = run_dir(root, run_id) / "steps.jsonl"
    _ensure_dir(path.parent)
    line = json.dumps(entry, sort_keys=True, separators=(",", ":")) + "\n"
    flags = os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW
    with os.fdopen(os.open(path, flags, 0o600), "wb") as handle:
        handle.write(line.encode())


def read_steps(root: Path, run_id: str) -> list[dict]:
    """Every recorded agent step of a run."""
    path = run_dir(root, run_id) / "steps.jsonl"
    if not os.path.lexists(path):
        return []
    data = _read_bytes(path)
    if data and not data.endswith(b"\n"):
        message = "steps.jsonl ends without a newline; an agent step did not finish"
        raise AutonomyError(message, "unfinished-step")
    try:
        return [json.loads(line) for line in data.splitlines()]
    except ValueError as error:
        message = "steps.jsonl is malformed"
        raise AutonomyError(message) from error


def unconsumed_steps(root: Path, run_id: str) -> list[dict]:
    """Agent steps since the last recorder."""
    path = run_dir(root, run_id) / "cursor.json"
    cursor = read_json(path, "step cursor") if os.path.lexists(path) else 0
    if not isinstance(cursor, int):
        message = "step cursor is malformed"
        raise AutonomyError(message)
    return read_steps(root, run_id)[cursor:]


def consume_steps(root: Path, run_id: str) -> None:
    """Mark every recorded step as consumed by a recorder."""
    write_json(run_dir(root, run_id) / "cursor.json", len(read_steps(root, run_id)))


def snapshot_draft(root: Path, run_id: str, step: str, name: str) -> Path:
    """Operator copy of a draft a step created."""
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,200}", step) or not re.fullmatch(
        r"[a-z0-9-]{1,80}\.json", name
    ):
        message = f"invalid draft name {name!r}"
        raise AutonomyError(message)
    return run_dir(root, run_id) / "drafts" / step / name


# --- Blocks ---------------------------------------------------------------

BLOCK_COMMAND = re.compile(
    r"ballast (?:run continue [A-Za-z0-9_-]{1,64} \S.*|run publish [A-Za-z0-9_-]{1,64}"
    r"|discard-runs|run start \S.*)"
)


# Blocks that `ballast run publish` retries: the forge refused or the operator's
# forge credential was unavailable; nothing in the run itself needs changing.
PUBLISH_RETRY = ("forge", "permission")


def recovery_command(run_id: str, category: str) -> str:
    """Return the one command that recovers from a block of this category."""
    if category in PUBLISH_RETRY:
        return f"ballast run publish {run_id}"
    if category in {"tamper", "unfinished-step"}:
        return "ballast discard-runs"
    return f"ballast run continue {run_id} --reason block-resolved --ref TEXT"


RECOVERY = {
    "decision": "Choose an option and record it in the spec, then continue "
    "human-gated.",
    "contradiction": "Resolve the contradiction in the spec, then continue "
    "human-gated.",
    "review-finding": "Fix or reject the finding, then continue human-gated.",
    "limit": "Review the evidence so far, then continue human-gated or start a "
    "new run with a larger limit.",
    "postcondition": "Fix the failed contract, then continue human-gated.",
    "tamper": "Restore the protected files and recreate .venv, delete the "
    "marker, review the checkout, then discard the run state and trust again.",
    "unfinished-step": "Review the checkout, discard the run state, then start again.",
    "permission": "Restore the missing permission or credential, then retry.",
    "ineligible": "Run the feature human-gated instead.",
    "forge": "Fix forge access, then retry publication.",
    "interrupted": "Review the checkout, then continue human-gated.",
}


def _text(value: object, name: str, limit: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        message = f"{name} must be 1-{limit} characters"
        raise AutonomyError(message)
    return value


def _guard_wording(name: str, value: str) -> None:
    if HUMAN_APPROVAL.search(value):
        message = f"{name} claims a human approval; agent decisions are provisional"
        raise AutonomyError(message)
    if WORKFLOW_MARKER.search(value):
        message = f"{name} contains a workflow marker"
        raise AutonomyError(message)


def _options(value: object) -> list[dict]:
    if not isinstance(value, list):
        message = "block options must be a list"
        raise AutonomyError(message)
    options = []
    for item in value:
        if not isinstance(item, dict):
            message = "each block option needs option and consequence"
            raise AutonomyError(message)
        options.append(
            {
                "option": _text(item.get("option"), "option", 500),
                "consequence": _text(item.get("consequence"), "consequence", 1000),
            }
        )
    return options


def validate_block(block: object) -> dict:
    """Check a block before it becomes the run's current block."""
    if not isinstance(block, dict):
        message = "block must be an object"
        raise AutonomyError(message)
    if block.get("category") not in BLOCK_CATEGORIES:
        message = f"unknown block category {block.get('category')!r}"
        raise AutonomyError(message)
    _text(block.get("condition"), "block condition", 4000)
    options = _options(block.get("options", []))
    if block["category"] in {"decision", "contradiction"} and len(options) < 2:  # noqa: PLR2004
        message = "a decision or contradiction block needs at least two options"
        raise AutonomyError(message)
    _text(block.get("recovery"), "block recovery", 1000)
    if not BLOCK_COMMAND.fullmatch(str(block.get("command"))):
        message = "block command is not a ballast recovery command"
        raise AutonomyError(message)
    evidence = block.get("evidence", [])
    if not isinstance(evidence, list) or not all(isinstance(e, str) for e in evidence):
        message = "block evidence must be a list of paths"
        raise AutonomyError(message)
    _parse_time(block.get("at"))
    return block


def make_block(  # noqa: PLR0913 - one record, every field explicit
    category: str,
    condition: str,
    *,
    run_id: str,
    step_id: str | None = None,
    options: list[dict] | None = None,
    recovery: str | None = None,
    evidence: list[str] | None = None,
) -> dict:
    """Build a validated block with its recovery command."""
    return validate_block(
        {
            "category": category,
            "step_id": step_id,
            "condition": condition,
            "options": options or [],
            "recovery": recovery or RECOVERY[category],
            "command": recovery_command(run_id, category),
            "evidence": evidence or [],
            "at": now(),
        }
    )


def validate_block_draft(draft: object) -> dict:
    """Validate an agent's `drafts/block.json` (decision or contradiction)."""
    if not isinstance(draft, dict):
        message = "block draft must be a JSON object"
        raise AutonomyError(message)
    category = draft.get("category")
    if category not in {"decision", "contradiction"}:
        message = "block draft category must be decision or contradiction"
        raise AutonomyError(message)
    condition = _text(draft.get("condition"), "block draft condition", 2000)
    options = _options(draft.get("options"))
    if len(options) < 2:  # noqa: PLR2004
        message = "block draft needs at least two options"
        raise AutonomyError(message)
    no_default = draft.get("no_safe_default")
    if category == "decision":
        no_default = _text(no_default, "block draft no_safe_default", 2000)
        condition = f"{condition} No safe, reversible default: {no_default}"
    recovery = _text(draft.get("recovery"), "block draft recovery", 1000)
    for name, value in (("condition", condition), ("recovery", recovery)):
        _guard_wording(f"block draft {name}", value)
    evidence = draft.get("evidence", [])
    if not isinstance(evidence, list) or not all(isinstance(e, str) for e in evidence):
        message = "block draft evidence must be a list of paths"
        raise AutonomyError(message)
    return {
        "category": category,
        "condition": condition,
        "options": options,
        "recovery": recovery,
        "evidence": evidence[:20],
    }


def record_block(root: Path, run_id: str, block: dict) -> dict:
    """Make block current; the previous current block moves to blocks.jsonl."""
    validate_block(block)
    directory = run_dir(root, run_id)
    path = directory / "block.json"
    if os.path.lexists(path):
        previous = read_json(path, "current block")
        line = json.dumps(previous, sort_keys=True, separators=(",", ":")) + "\n"
        _ensure_dir(directory)
        flags = os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW
        with os.fdopen(os.open(directory / "blocks.jsonl", flags, 0o600), "wb") as h:
            h.write(line.encode())
    write_json(path, block)
    return block


def read_block(root: Path, run_id: str) -> dict | None:
    """Return the run's current block, if any."""
    path = run_dir(root, run_id) / "block.json"
    if not os.path.lexists(path):
        return None
    return validate_block(read_json(path, "current block"))


# --- Policy ---------------------------------------------------------------


def load_config(root: Path) -> dict:
    """Parse ballast.toml, the trusted project configuration."""
    path = root / "ballast.toml"
    if not os.path.lexists(path):
        return {}
    try:
        return tomllib.loads(_read_bytes(path).decode())
    except (OSError, ValueError) as error:
        message = f"ballast.toml is unreadable: {error}"
        raise AutonomyError(message, "ineligible") from error


def _bounded(value: object, name: str, bounds: tuple[int, int, int]) -> int:
    low, high, _ = bounds
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or not low <= value <= high
    ):
        message = f"{name} must be an integer from {low} to {high}"
        raise AutonomyError(message, "ineligible")
    return value


def _strings(value: object, name: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        message = f"[autonomous] {name} must be a list of strings"
        raise AutonomyError(message, "ineligible")
    return [" ".join(v.lower().split()) for v in value if v.strip()]


def parse_policy(config: dict) -> tuple[dict, dict, list[str]]:
    """Return (policy snapshot, project limit defaults, warnings).

    The table can only narrow the standard: R0-R2, no privileged action.
    """
    table = config.get("autonomous", {})
    if not isinstance(table, dict):
        message = "[autonomous] must be a table"
        raise AutonomyError(message, "ineligible")
    warnings = [
        WIDENING.format(key=key) for key in sorted(table) if key not in POLICY_KEYS
    ]
    risk = list(RISKS)
    if "risk" in table:
        values = table["risk"]
        if not isinstance(values, list):
            message = "[autonomous] risk must be a list"
            raise AutonomyError(message, "ineligible")
        warnings.extend(
            WIDENING.format(key=f"risk {value!r}")
            for value in values
            if value not in RISKS
        )
        risk = [level for level in RISKS if level in values]
    authorized = []
    for action in _strings(table.get("authorized_privileged_actions", []), "actions"):
        if action in NEVER_AUTHORIZED:
            warnings.append(
                WIDENING.format(key=f"authorized_privileged_actions {action!r}")
            )
        elif action not in authorized:
            authorized.append(action)
    policy = {
        "risk": risk,
        "excluded_boundaries": sorted(
            set(_strings(table.get("excluded_boundaries", []), "excluded_boundaries"))
        ),
        "authorized_privileged_actions": sorted(authorized),
    }
    defaults = {}
    if "wall_time_minutes" in table:
        defaults["wall_time_minutes"] = _bounded(
            table["wall_time_minutes"], "[autonomous] wall_time_minutes", WALL_TIME
        )
    if "max_agent_steps" in table:
        defaults["max_agent_steps"] = _bounded(
            table["max_agent_steps"], "[autonomous] max_agent_steps", AGENT_STEPS
        )
    return policy, defaults, warnings


def parse_checks(config: dict) -> dict:
    """Return the trusted `[checks]` commands an Autonomous run must pass."""
    table = config.get("checks")
    commands = table.get("commands") if isinstance(table, dict) else None
    if (
        not isinstance(commands, list)
        or not commands
        or not all(isinstance(c, str) and c.strip() for c in commands)
    ):
        message = (
            "ballast.toml has no [checks] commands; add a [checks] table with the "
            "project's check commands, then run `ballast trust`"
        )
        raise AutonomyError(message, "ineligible")
    timeout = table.get("timeout_minutes", CHECK_TIMEOUT[2])
    return {
        "commands": list(commands),
        "timeout_minutes": _bounded(timeout, "[checks] timeout_minutes", CHECK_TIMEOUT),
    }


def resolve_limits(
    defaults: dict,
    wall_time: int | None = None,
    max_steps: int | None = None,
    start: datetime | None = None,
) -> dict:
    """Limits by precedence operator > project > built-in default."""
    minutes = WALL_TIME[2]
    steps = AGENT_STEPS[2]
    source = "default"
    if defaults:
        minutes = defaults.get("wall_time_minutes", minutes)
        steps = defaults.get("max_agent_steps", steps)
        source = "project"
    if wall_time is not None or max_steps is not None:
        source = "operator"
    if wall_time is not None:
        minutes = _bounded(wall_time, "--wall-time", WALL_TIME)
    if max_steps is not None:
        steps = _bounded(max_steps, "--max-agent-steps", AGENT_STEPS)
    begin = (start or datetime.now(UTC)).replace(microsecond=0)
    return {
        "wall_time_minutes": minutes,
        "deadline": (begin + timedelta(minutes=minutes)).isoformat(),
        "max_agent_steps": steps,
        "source": source,
    }


def remaining_seconds(record: dict) -> float:
    """Seconds left before the run's deadline (negative once passed)."""
    deadline = _parse_time(record["limits"]["deadline"])
    return (deadline - datetime.now(UTC)).total_seconds()


# --- Git ------------------------------------------------------------------


def git(
    root: Path,
    *args: str,
    env: dict[str, str] | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Run git as the operator with hooks, fsmonitor and filters disabled.

    Never a bare `git`: like draft_pr, only one found outside every working
    tree and agent temp root (DEC-0007).
    """
    executable, _ = _trusted()._resolve("git", root)  # noqa: SLF001
    if executable is None:
        message = "git not found outside working trees"
        raise AutonomyError(message)
    overrides = [] if args[:1] == ("config",) else filter_overrides(root, env)
    result = subprocess.run(  # noqa: S603 - resolved executable, argument list
        [executable, *GIT_HARDENING, *overrides, *args],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if check and result.returncode != 0:
        message = f"git {args[0]} failed: {result.stderr.strip()}"
        raise AutonomyError(message)
    return result


def filter_overrides(root: Path, env: dict[str, str] | None = None) -> list[str]:
    """`-c` flags that empty every configured filter driver.

    A filter runs only when the configuration defines its command, and an
    agent can add a `.gitattributes` that selects one; emptying each defined
    driver means no `clean`, `smudge` or `process` program ever runs.
    """
    listed = git(root, "config", "--list", "--name-only", "-z", env=env).stdout
    return filter_flags(listed)


def filter_flags(listed: str) -> list[str]:
    """`-c` flags for `filter_overrides`, from `git config --list --name-only -z`."""
    names = {
        key[len("filter.") :].rpartition(".")[0]
        for key in listed.split("\0")
        if key.lower().startswith("filter.") and key.count(".") >= 2  # noqa: PLR2004
    }
    flags = []
    for name in sorted(names):
        if "=" in name or "\n" in name:
            message = f"refusing a filter driver name Git cannot override: {name!r}"
            raise AutonomyError(message)
        for key, value in FILTER_OFF:
            flags += ["-c", f"filter.{name}.{key}={value}"]
    return flags


FILTER_OFF = (("clean", ""), ("smudge", ""), ("process", ""), ("required", "false"))


def git_path(root: Path, *args: str) -> Path:
    """Return an absolute path reported by `git rev-parse`."""
    out = git(root, "rev-parse", "--path-format=absolute", *args).stdout.strip()
    return Path(out)


def tree_digest(root: Path, exclude: tuple[str, ...] = ()) -> str:
    """Hash the working tree (minus ignored files) in a private index.

    Protected inputs and the given extra paths are left out, so the digest
    covers exactly what an agent or a check may change.
    """
    index = git_path(root, "--git-path", "index")
    excluded = [*PROTECTED, *exclude]
    with tempfile.TemporaryDirectory(prefix="ballast-tree-") as directory:
        private = Path(directory) / "index"
        if index.is_file():
            shutil.copyfile(index, private)
        env = {**os.environ, "GIT_INDEX_FILE": str(private)}
        # Exclusions are removed below rather than as `add` pathspecs: git
        # refuses an exclude pathspec that names an ignored path, and installed
        # projects ignore .ballast/ and most of .specify/.
        git(root, "add", "--all", "--", ":/", env=env)
        git(
            root,
            "rm",
            "-r",
            "-q",
            "--cached",
            "--ignore-unmatch",
            "--",
            *(f":(top){path}" for path in excluded),
            env=env,
        )
        return git(root, "write-tree", env=env).stdout.strip()


def checked_digest(root: Path, feature: str) -> str:
    """Tree digest recorded at run-checks and compared until publication.

    It leaves out `specs/<f>/autonomous/`: the recorders re-render record.md
    there (every check compares it with the logs) and drafts are transient.
    """
    return tree_digest(root, (f"{feature}/autonomous",))


def effective_config(root: Path) -> list[tuple[str, str, str, str]]:
    """Every effective Git setting as (scope, origin, key, value)."""
    result = git(
        root, "config", "--list", "--show-scope", "--show-origin", "-z", check=False
    )
    if result.returncode != 0:
        return []
    tokens = result.stdout.split("\0")
    entries = []
    for scope, origin, pair in zip(
        tokens[::3], tokens[1::3], tokens[2::3], strict=False
    ):
        key, _, value = pair.partition("\n")
        entries.append((scope, origin, key.lower(), value))
    return entries


def _inside(root: Path, base: Path, token: str) -> bool:
    """Whether a path-like config token names a file in the writable checkout."""
    token = token.lstrip("!").partition("=")[2] or token.lstrip("!")
    if not token or not ("/" in token or token.startswith(("~", "."))):
        return False
    path = Path(token).expanduser()
    if not path.is_absolute():
        path = base / path
    resolved = Path(os.path.normpath(path))
    checkout = Path(os.path.normpath(root.resolve()))
    git_dir = checkout / ".git"
    return resolved.is_relative_to(checkout) and not resolved.is_relative_to(git_dir)


def _tokens(value: str) -> list[str]:
    try:
        return shlex.split(value)
    except ValueError:
        return [value]


def credential_findings(root: Path) -> list[str]:
    """Git settings that carry a credential an agent could read.

    Messages name the key only, never the value.
    """
    found = set()
    for _, _, key, value in effective_config(root):
        if CREDENTIAL_URL.search(value):
            found.add(f"{key} carries a URL with embedded credentials")
        if EXTRA_HEADER.fullmatch(key):
            found.add(f"{key} sets an HTTP header")
        elif "authorization" in value.lower():
            found.add(f"{key} carries an Authorization value")
        if key == "credential.helper" and any(
            _inside(root, root, token) for token in _tokens(value)
        ):
            found.add(f"{key} stores credentials inside the checkout")
    return sorted(found)


def program_findings(root: Path) -> list[str]:
    """Git settings that run a program or include a file an agent could write."""
    found = set()
    for _, origin, key, value in effective_config(root):
        if key not in PROGRAM_KEYS and not INCLUDE_IF.fullmatch(key):
            continue
        base = root
        if key.endswith(".path") and origin.startswith("file:"):
            base = Path(origin.removeprefix("file:")).parent
            if not base.is_absolute():
                base = root / base
        if any(_inside(root, base, token) for token in _tokens(value)):
            found.add(f"{key} names a program or file inside the checkout")
    return sorted(found)


DRIVER_KEYS = {
    "filter": ("clean", "smudge", "process"),
    "diff": ("command", "textconv"),
    "merge": ("driver",),
}
ATTRIBUTE = re.compile(r"(?:^|\s)(filter|diff|merge)=([^\s]+)")


def attribute_drivers(root: Path) -> list[str]:
    """Filter, diff or merge drivers that `.gitattributes` uses and config defines."""
    files = git(
        root,
        "ls-files",
        "-z",
        "--cached",
        "--others",
        "--exclude-standard",
        "--",
        ":(top,glob)**/.gitattributes",
    ).stdout.split("\0")
    paths = [root / name for name in files if name]
    paths.append(git_path(root, "--git-path", "info/attributes"))
    used = set()
    for path in paths:
        if path.is_file() and not path.is_symlink():
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                if not line.lstrip().startswith("#"):
                    used.update(ATTRIBUTE.findall(line))
    defined = {key for _, _, key, _ in effective_config(root)}
    return sorted(
        f"{kind}={name}"
        for kind, name in used
        if any(f"{kind}.{name.lower()}.{part}" in defined for part in DRIVER_KEYS[kind])
    )


def config_snapshot(root: Path) -> dict:
    """Repository-local Git configuration, its includes and the hooks listing."""

    def listed(scope: str) -> list[str]:
        out = git(root, "config", scope, "--list", "-z", check=False).stdout
        # Branch tracking runs no program; the publisher's own `push -u` sets it.
        return [item for item in out.split("\0") if not item.startswith("branch.")]

    local = listed("--local")
    worktree = listed("--worktree")
    includes = {}
    for scope, origin, key, value in effective_config(root):
        if scope in {"local", "worktree"} and (
            key == "include.path" or INCLUDE_IF.fullmatch(key)
        ):
            base = Path(origin.removeprefix("file:")).parent
            path = Path(value).expanduser()
            path = path if path.is_absolute() else root / base / path
            includes[str(path)] = (
                sha256_file(path) if path.is_file() and not path.is_symlink() else None
            )
    hooks = {}
    # Not `--git-path hooks`: the hardening points core.hooksPath at /dev/null.
    # A configured core.hooksPath is part of the local configuration above.
    directory = git_path(root, "--git-common-dir") / "hooks"
    if directory.is_dir():
        for path in sorted(directory.iterdir()):
            hooks[path.name] = (
                "link:" + str(path.readlink())
                if path.is_symlink()
                else sha256_file(path)
                if path.is_file()
                else "dir"
            )
    return {"local": local, "worktree": worktree, "includes": includes, "hooks": hooks}


# --- Confinement ----------------------------------------------------------


def confined_env(env: dict[str, str], integration: str | None) -> dict[str, str]:
    """Drop every secret-named variable except the integration's own key."""
    keep = set(INTEGRATION_KEYS.get(integration or "", ()))
    return {
        name: value
        for name, value in env.items()
        if name in keep
        or (
            not SECRET_NAME.search(name.upper())
            and name not in SECRET_VARIABLES
            and name not in CREDENTIAL_LOCATIONS
        )
    }


def agent_homes(home: Path, env: dict[str, str]) -> list[Path]:
    """Agent CLI homes and caches that get a throwaway overlay."""
    claude = Path(env.get("CLAUDE_CONFIG_DIR") or home / ".claude")
    codex = Path(env.get("CODEX_HOME") or home / ".codex")
    return [claude, codex, home / ".cache"]


def _binds_for_worktree(root: Path, feature: str | None) -> list[str]:
    args = ["--bind", str(root), str(root)]
    for name in PROTECTED:
        path = root / name
        if os.path.lexists(path):
            args += ["--ro-bind", str(path), str(path)]
    specify = root / ".specify"
    if specify.is_dir() and not specify.is_symlink():
        for name in SPECIFY_WRITABLE:
            path = specify / name
            if name == "feature.json":
                if not os.path.lexists(path) and feature:
                    path.write_text(
                        json.dumps({"feature_directory": feature}) + "\n",
                        encoding="utf-8",
                    )
                if not path.is_file() or path.is_symlink():
                    continue
            else:
                path.mkdir(parents=True, exist_ok=True)
                if path.is_symlink():
                    continue
            args += ["--bind", str(path), str(path)]
    git = root / ".git"
    if git.is_dir() and not git.is_symlink():
        args += ["--ro-bind", str(git), str(git)]
    return args


TMPFS_HIDDEN = (Path("/tmp"), Path("/run"))  # noqa: S108 - emptied in the sandbox
# Name resolution the agent CLIs need; systemd-resolved links resolv.conf into /run.
RESOLVER_FILES = (
    Path("/etc/resolv.conf"),
    Path("/etc/hosts"),
    Path("/etc/nsswitch.conf"),
    Path("/etc/gai.conf"),
)


def _hidden_by_tmpfs(path: Path) -> bool:
    return any(path.is_relative_to(base) for base in TMPFS_HIDDEN)


def _resolver_binds() -> list[str]:
    """Bind back each resolver file a tmpfs hides, and nothing else under it.

    Only the resolved regular file: never its directory, the user bus or a
    runtime socket. Agent steps keep the host network, so a stub resolver on
    127.0.0.53 stays reachable.
    """
    args: list[str] = []
    for name in RESOLVER_FILES:
        target = name.resolve()
        if target != name and _hidden_by_tmpfs(target) and target.is_file():
            args += ["--ro-bind", str(target), str(target)]
    return args


def _visible_binds(root: Path, command: list[str]) -> list[str]:
    """Read-only binds for what the tmpfs mounts would hide but a step needs.

    A linked worktree's common Git directory and the executable's directory
    stay visible, read-only, when they live under /tmp or /run.
    """
    paths = []
    common = git(
        root, "rev-parse", "--path-format=absolute", "--git-common-dir", check=False
    )
    if common.returncode == 0:
        paths.append(Path(common.stdout.strip()))
    executable = shutil.which(command[0]) if command else None
    if executable:
        paths.append(Path(executable).resolve().parent)
    args = []
    for path in paths:
        resolved = path.resolve()
        if (
            _hidden_by_tmpfs(resolved)
            and resolved.is_dir()
            and not Path(root).resolve().is_relative_to(resolved)
            and not resolved.is_relative_to(Path(root).resolve())
        ):
            args += ["--ro-bind", str(resolved), str(resolved)]
    return args


def confined_argv(  # noqa: C901, PLR0913 - every input is explicit
    root: Path,
    command: list[str],
    *,
    private: Path,
    feature: str | None = None,
    env: dict[str, str] | None = None,
    home: Path | None = None,
) -> list[str]:
    """Bwrap argv: read-only host, writable worktree minus protected inputs.

    `private` is a wrapper-owned temporary directory for the per-step copy of
    `~/.claude.json`. Agent homes and caches get throwaway overlays,
    credential paths are hidden, and the agent cannot reach the operator's
    processes, user bus or runtime sockets. Pass the operator's environment,
    not `confined_env()`'s: it names the credential locations to hide.
    """
    bwrap = shutil.which("bwrap")
    if bwrap is None:
        message = "confinement unavailable: bwrap not found"
        raise AutonomyError(message, "ineligible")
    env = dict(os.environ if env is None else env)
    home = home or Path.home()
    args = [
        bwrap,
        "--ro-bind",
        "/",
        "/",
        "--dev",
        "/dev",
        "--proc",
        "/proc",
        "--tmpfs",
        "/tmp",  # noqa: S108 - private tmpfs inside the sandbox
        "--tmpfs",
        "/run",
    ]
    if Path("/var/run").is_dir() and not Path("/var/run").is_symlink():
        args += ["--tmpfs", "/var/run"]
    runtime = env.get("XDG_RUNTIME_DIR")
    if runtime:
        args += ["--tmpfs", runtime]
    args += _resolver_binds()
    # Credential directories are emptied first and made read-only last, so an
    # agent home inside one (CODEX_HOME under ~/.config) can still be overlaid.
    hidden = [home / name for name in CREDENTIAL_DIRS if (home / name).is_dir()]
    hidden += [
        Path(env[name]).resolve()
        for name in CREDENTIAL_LOCATIONS
        if env.get(name) and Path(env[name]).is_dir()
    ]
    for path in hidden:
        args += ["--tmpfs", str(path)]
    for name in CREDENTIAL_FILES:
        path = home / name
        if os.path.lexists(path):
            args += ["--ro-bind", "/dev/null", str(path)]
    for path in agent_homes(home, env):
        if path.is_dir() and not path.is_symlink():
            args += ["--overlay-src", str(path), "--tmp-overlay", str(path)]
    settings = home / ".claude.json"
    if settings.is_file() and not settings.is_symlink():
        copy = private / "claude.json"
        shutil.copyfile(settings, copy)
        args += ["--bind", str(copy), str(settings)]
    args += _visible_binds(root, command)
    args += _binds_for_worktree(root, feature)
    for path in hidden:
        args += ["--remount-ro", str(path)]
    args += [
        "--unshare-pid",
        "--unshare-ipc",
        "--new-session",
        "--die-with-parent",
        "--chdir",
        str(root),
        "--",
        *command,
    ]
    return args


PROBE = r"""
import json, os, subprocess, sys
targets, persist, runtime, parent = json.loads(sys.argv[1])
result = {}
for target in targets:
    try:
        with open(target, "x") as handle:
            handle.write("probe")
        os.unlink(target)
        result[target] = "escaped"
    except OSError:
        result[target] = "ok"
try:
    with open(persist, "w") as handle:
        handle.write("probe")
except OSError:
    pass
try:
    done = subprocess.run(
        ["systemd-run", "--user", "--quiet", "true"],
        capture_output=True, timeout=20,
    ).returncode
    result["systemd-run --user"] = "escaped" if done == 0 else "ok"
except (OSError, subprocess.TimeoutExpired):
    result["systemd-run --user"] = "ok"
if runtime:
    try:
        result["XDG_RUNTIME_DIR"] = "escaped" if os.listdir(runtime) else "ok"
    except OSError:
        result["XDG_RUNTIME_DIR"] = "ok"
try:
    with open(f"/proc/{parent}/environ", "rb") as handle:
        handle.read(1)
    result["operator environ"] = "escaped"
except OSError:
    result["operator environ"] = "ok"
print(json.dumps(result))
"""


def confinement_self_test(root: Path, *, env: dict[str, str] | None = None) -> None:
    """Fail closed unless a confined process cannot reach operator authority."""
    env = dict(os.environ if env is None else env)
    home = Path.home()
    python = shutil.which("python3") or sys.executable
    common = git_path(root, "--git-common-dir")
    targets = [
        str(state_dir(root) / ".ballast-probe"),
        str(common / ".ballast-probe"),
        str(home / ".ballast-probe"),
    ]
    if (home / ".config").is_dir():
        targets.append(str(home / ".config/.ballast-probe"))
    if (root / ".specify").is_dir():
        targets.append(str(root / ".specify/.ballast-probe"))
    claude = agent_homes(home, env)[0]
    persist = claude / ".ballast-probe"
    payload = json.dumps(
        [targets, str(persist), env.get("XDG_RUNTIME_DIR", ""), os.getpid()]
    )
    state_dir(root).mkdir(parents=True, exist_ok=True, mode=0o700)
    with tempfile.TemporaryDirectory(prefix="ballast-confine-") as private:
        argv = confined_argv(
            root,
            [python, "-I", "-S", "-c", PROBE, payload],
            private=Path(private),
            env=env,
            home=home,
        )
        try:
            result = subprocess.run(  # noqa: S603 - resolved bwrap, argument list
                argv,
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
                env=confined_env(env, None),
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            message = f"confinement unavailable: {error}"
            raise AutonomyError(message, "ineligible") from error
    try:
        report = json.loads(result.stdout.strip().splitlines()[-1])
    except (IndexError, ValueError) as error:
        detail = result.stderr.strip().splitlines()[-1:] or ["no output"]
        message = f"confinement unavailable: self-test failed ({detail[0]})"
        raise AutonomyError(message, "ineligible") from error
    escaped = sorted(name for name, state in report.items() if state != "ok")
    if claude.is_dir() and os.path.lexists(persist):
        persist.unlink(missing_ok=True)
        escaped.append("agent home write persisted")
    if escaped:
        message = f"confinement unavailable: self-test reached {', '.join(escaped)}"
        raise AutonomyError(message, "ineligible")


CODEX_FALLBACK = (
    "codex cannot start its own sandbox inside Ballast's confinement; "
    "claude takes both roles (DEC-0004)"
)


def codex_sandbox_nests(root: Path, *, env: dict[str, str] | None = None) -> bool:
    """Whether Codex's workspace-write sandbox starts inside Ballast's bwrap.

    Runs `true` under `codex sandbox` in a confined, network-less step, once
    per run start. Any failure, including a missing codex, is False.
    """
    codex = shutil.which("codex")
    if codex is None:
        return False
    env = dict(os.environ if env is None else env)
    command = [
        codex,
        "sandbox",
        "-c",
        'sandbox_mode="workspace-write"',
        "-c",
        "sandbox_workspace_write.network_access=false",
        "--",
        "true",
    ]
    with tempfile.TemporaryDirectory(prefix="ballast-confine-") as private:
        try:
            argv = confined_argv(root, command, private=Path(private), env=env)
            argv.insert(argv.index("--"), "--unshare-net")
            result = subprocess.run(  # noqa: S603 - resolved bwrap, argument list
                argv,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                timeout=60,
                check=False,
                env=confined_env(env, None),
            )
        except (AutonomyError, OSError, subprocess.TimeoutExpired):
            return False
    return result.returncode == 0


# --- Eligibility ----------------------------------------------------------


def _gh(
    root: Path, *args: str, stdin: str | None = None, category: str = "ineligible"
) -> object:
    """Run the operator's gh as draft_pr does (DEC-0007); return its JSON.

    gh is found outside every working tree and agent temp root and starts in
    an empty directory, so it never reads the agent-writable `.git/config`;
    every caller names the repository pinned in ballast.toml. A failure raises
    `category`; at publication an authentication failure is `permission`.
    """
    prefix = CANNOT_CHECK if category == "ineligible" else ""
    draft_pr = _trusted()
    gh, _ = draft_pr._resolve("gh", root)  # noqa: SLF001
    if gh is None:
        message = f"{prefix}gh not found outside working trees"
        raise AutonomyError(message, category if prefix else "permission")
    with tempfile.TemporaryDirectory(prefix="ballast-gh-") as away:
        result = draft_pr._command(  # noqa: SLF001
            [gh, *args], stdin=stdin, cwd=Path(away), root=root
        )
    if result.returncode != 0:
        cause = draft_pr._classify(result)  # noqa: SLF001
        detail = (result.stderr.strip().splitlines() or [cause])[0][:500]
        message = f"{prefix}gh {' '.join(args[:2])} failed: {detail}"
        # draft_pr's causes, plus #27's earlier rule for a gh login prompt.
        if not prefix and (
            cause in {"gh-unauthenticated", "gh-forbidden"}
            or "auth" in result.stderr.lower()
        ):
            category = "permission"
        raise AutonomyError(message, category)
    if args[:2] == ("pr", "create"):
        return result.stdout
    try:
        return json.loads(result.stdout or "null")
    except ValueError as error:
        message = f"{prefix}gh returned invalid JSON"
        raise AutonomyError(message, category) from error


def _gh_list(root: Path, path: str) -> list[dict]:
    items: list[dict] = []
    for page in range(1, 11):
        separator = "&" if "?" in path else "?"
        result = _gh(root, "api", f"{path}{separator}per_page=100&page={page}")
        if not isinstance(result, list):
            message = f"{CANNOT_CHECK}GitHub returned a non-list page"
            raise AutonomyError(message, "ineligible")
        items.extend(item for item in result if isinstance(item, dict))
        if len(result) < 100:  # noqa: PLR2004
            return items
    message = f"{CANNOT_CHECK}GitHub pagination exceeded 10 pages"
    raise AutonomyError(message, "ineligible")


def repository(root: Path, category: str = "ineligible") -> tuple[str, str]:
    """(OWNER/NAME, default branch) of the repository pinned in ballast.toml.

    Never the agent-writable remote (#17 DEC-0005, DEC-0007 here).
    """
    prefix = CANNOT_CHECK if category == "ineligible" else ""
    pinned = _trusted()._pinned_repository(root)  # noqa: SLF001
    if pinned is None:
        message = (
            f'{prefix}declare [github] repository = "OWNER/NAME" in ballast.toml, '
            "then run ballast trust"
        )
        raise AutonomyError(message, category)
    repo = "/".join(pinned)
    data = _gh(
        root,
        "repo",
        "view",
        repo,
        "--json",
        "nameWithOwner,defaultBranchRef",
        category=category,
    )
    name = data.get("nameWithOwner") if isinstance(data, dict) else None
    if not isinstance(name, str) or name.lower() != repo.lower():
        message = f"{prefix}gh repo view did not return {repo}"
        raise AutonomyError(message, category)
    branch = (data.get("defaultBranchRef") or {}).get("name")
    return repo, branch if isinstance(branch, str) else ""


def _label_names(issue: dict) -> set[str]:
    return {str(label.get("name")) for label in issue.get("labels") or []}


def parse_scope(text: str) -> dict:
    """Risk, privileged actions, boundaries and Autonomous marker of a scope record."""
    risk = re.search(r"(?m)^Risk:[ \t]*(R[012])\b", text)
    actions = re.search(r"(?mi)^Privileged actions before merge:[ \t]*(.+)$", text)
    boundaries = re.search(r"(?mi)^R2 boundaries:[ \t]*(.+)$", text)

    def items(match: re.Match[str] | None) -> list[str] | None:
        if match is None:
            return None
        value = match.group(1).strip().rstrip(".")
        if value.lower() in {"none", "-", "n/a"}:
            return []
        return [" ".join(v.lower().split()) for v in value.split(",") if v.strip()]

    return {
        "risk": risk.group(1) if risk else None,
        "privileged_actions": items(actions),
        "boundaries": items(boundaries) or [],
    }


def _scope_problems(issue: dict, children: list, blockers: list) -> list[str]:
    problems = []
    if issue.get("state") != "open":
        problems.append("issue is not open")
    if "epic" in _label_names(issue) or children:
        problems.append("issue is an Epic or has sub-issues")
    open_blockers = sorted(
        b.get("number") for b in blockers if b.get("state") == "open"
    )
    if open_blockers:
        problems.append("blocked by " + ", ".join(f"#{n}" for n in open_blockers))
    return [f"{REFUSAL}scope gate: {problem}" for problem in problems]


def unauthorized_actions(actions: list[str], policy: dict) -> list[str]:
    """Return declared privileged actions the narrowed policy does not authorize."""
    allowed = set(policy.get("authorized_privileged_actions", []))
    return sorted({a for a in actions if a in NEVER_AUTHORIZED or a not in allowed})


def risk_reasons(level: str, boundaries: list[str], policy: dict) -> list[str]:
    """Refusals for a risk level and boundaries under the policy snapshot."""
    reasons = []
    if level not in policy.get("risk", []):
        reasons.append(f"{REFUSAL}risk {level} excluded by ballast.toml [autonomous]")
    excluded = sorted(set(boundaries) & set(policy.get("excluded_boundaries", [])))
    reasons.extend(
        f"{REFUSAL}boundary {name} excluded by ballast.toml [autonomous]"
        for name in excluded
    )
    return reasons


def check_eligibility(  # noqa: C901, PLR0913 - one list of independent rules
    root: Path,
    *,
    issue: int,
    feature: str,
    policy: dict,
    warnings: list[str],
    self_test: bool = True,
) -> dict:
    """Check every Autonomous eligibility rule before any agent step.

    Returns {"eligibility", "risk", "repo", "branch", "issue_title"}; a gh
    failure raises (fails closed).
    """
    reasons: list[str] = []
    repo, default_branch = repository(root)
    base = f"repos/{repo}"
    data = _gh(root, "api", f"{base}/issues/{issue}")
    if not isinstance(data, dict) or data.get("number") != issue:
        message = f"{CANNOT_CHECK}issue #{issue} could not be read"
        raise AutonomyError(message, "ineligible")
    children = _gh_list(root, f"{base}/issues/{issue}/sub_issues")
    blockers = _gh_list(root, f"{base}/issues/{issue}/dependencies/blocked_by")
    reasons += _scope_problems(data, children, blockers)
    comments = [
        c
        for c in _gh_list(root, f"{base}/issues/{issue}/comments")
        if SCOPE_COMMENT.format(issue=issue) in (c.get("body") or "")
    ]
    scope = {"risk": None, "privileged_actions": None, "boundaries": []}
    if (
        "ready-for-agent" not in _label_names(data)
        or len(comments) != 1
        or comments[0].get("author_association") not in SCOPE_AUTHORS
    ):
        reasons.append(f"{REFUSAL}issue has no recorded scope gate")
    else:
        scope = parse_scope(comments[0].get("body") or "")
        if scope["risk"] is None:
            reasons.append(f"{REFUSAL}scope record lacks Risk:")
        if scope["privileged_actions"] is None:
            reasons.append(
                f"{REFUSAL}scope record lacks Privileged actions before merge:"
            )
    actions = scope["privileged_actions"] or []
    if scope["risk"]:
        reasons += risk_reasons(scope["risk"], scope["boundaries"], policy)
    reasons += [
        f"{REFUSAL}privileged action {action} before merge"
        for action in unauthorized_actions(actions, policy)
    ]
    match = FEATURE.fullmatch(feature)
    if match is None or int(match.group(1)) != issue:
        reasons.append(
            f"{REFUSAL}feature directory {feature} is not for issue #{issue}"
        )
    branch = git(root, "rev-parse", "--abbrev-ref", "HEAD", check=False).stdout.strip()
    if not branch or branch in {"HEAD", default_branch}:
        reasons.append(f"{REFUSAL}{BRANCH_REFUSAL}")
    else:
        prs = _gh(
            root,
            "pr",
            "list",
            "--repo",
            repo,
            "--head",
            branch,
            "--state",
            "open",
            "--json",
            "number",
        )
        if prs:
            reasons.append(f"{REFUSAL}{BRANCH_REFUSAL}")
    reasons += [
        f"{REFUSAL}git configuration carries a credential: {finding}"
        for finding in credential_findings(root)
    ]
    if self_test:
        try:
            confinement_self_test(root)
        except AutonomyError as error:
            reasons.append(f"{REFUSAL}{error}")
    level = scope["risk"] or "R2"
    return {
        "eligibility": {
            "eligible": not reasons,
            "checked_at": now(),
            "reasons": reasons,
            "privileged_actions": actions,
            "policy": policy,
            "ignored_policy": list(warnings),
        },
        "risk": {
            "level": level,
            "source": "scope-record",
            "history": [{"level": level, "at": now(), "decision_id": None}],
            "boundaries": sorted(set(scope["boundaries"])),
        },
        "repo": repo,
        "branch": branch,
        "issue_title": str(data.get("title") or f"Issue #{issue}")[:200],
    }


def raise_risk(record: dict, level: str | None, boundaries: list[str], pd: str) -> bool:
    """Raise the recorded risk, never lower it.

    Return True when eligibility must be checked again.
    """
    risk = record["risk"]
    merged = sorted(set(risk.get("boundaries", [])) | set(boundaries))
    grew = merged != risk.get("boundaries", [])
    risk["boundaries"] = merged
    if level in RISKS and RISKS.index(level) > RISKS.index(risk["level"]):
        risk["level"] = level
        risk["source"] = "raised"
        risk["history"].append({"level": level, "at": now(), "decision_id": pd})
        return True
    return grew


# --- Rendering ------------------------------------------------------------

MENTION = re.compile(r"@(?=[A-Za-z0-9_-])")


def neutralize(text: str) -> str:
    """Escape agent text for Markdown: no HTML, markers or mentions."""
    text = html.escape(" ".join(str(text).split()), quote=False)
    return MENTION.sub("@\u200b", text).replace("|", "\\|")


def _quote_block(text: str) -> list[str]:
    lines = str(text).replace("\r\n", "\n").split("\n")
    return [
        "> " + MENTION.sub("@\u200b", html.escape(line, quote=False)) for line in lines
    ]


def _code(value: str) -> str:
    return "`" + str(value).replace("`", "'") + "`"


def _intent_pd(decisions: list[dict]) -> str:
    for point in ("tasks", "intent"):
        found = current(decisions, point)
        if found:
            return found[-1]["id"]
    return "none recorded yet"


def _mode_lines(run: dict) -> list[str]:
    lines = ["## Mode and risk", ""]
    for change in run["mode_history"]:
        extra = ""
        if change.get("decision_id"):
            extra += f", decision {change['decision_id']}"
        if change.get("reason"):
            extra += f": {neutralize(change['reason'])}"
        lines.append(
            f"- Mode {change['action']}: {change['mode']} at {change['at']} "
            f"by {change['by']}{extra}"
        )
    risk = run.get("risk")
    if risk:
        history = "; ".join(
            f"{h['level']} at {h['at']}"
            + (f" ({h['decision_id']})" if h.get("decision_id") else "")
            for h in risk["history"]
        )
        lines.append(f"- Risk: {risk['level']} ({risk['source']}); history: {history}")
    limits = run.get("limits")
    if limits:
        lines.append(
            f"- Limits ({limits['source']}): {limits['wall_time_minutes']} minutes "
            f"wall time, {limits['max_agent_steps']} agent steps"
        )
    lines.append(
        f"- Authoring integration: {run['integration']}; review integration: "
        f"{run['review_integration']}"
    )
    if run.get("integration_fallback"):
        lines.append(f"- Integration fallback: {run['integration_fallback']}")
    return [*lines, ""]


def _r2_lines(run: dict, decisions: list[dict]) -> list[str]:
    risk = run.get("risk") or {}
    if risk.get("level") != "R2":
        return []
    lines = [
        "## R2 notice",
        "",
        (
            "This is an R2 change. It was made without any prior human approval; "
            f"the pre-change approval was agent-provisional ({_intent_pd(decisions)})."
        ),
        "",
        "R2 boundaries touched:",
        "",
    ]
    boundaries = risk.get("boundaries") or []
    lines += [f"- {neutralize(b)}" for b in boundaries] or ["- None declared"]
    return [*lines, ""]


def _decided_by(entry: dict) -> str:
    agent = entry.get("agent") or {}
    return neutralize(
        f"{agent.get('provider', 'runner')}/{agent.get('model', 'unreported')} "
        f"({agent.get('role', 'runner')})"
    )


def _decision_rows(decisions: list[dict], link: object, *, short: bool) -> list[str]:
    replaced = superseded(decisions)
    if short:
        lines = ["| ID | Point | Summary |", "| --- | --- | --- |"]
        lines += [
            f"| {e['id']} | {e['point']} | agent-provisional: "
            f"{neutralize(e['summary'])} |"
            for e in decisions
        ]
        return lines
    lines = [
        (
            "| ID | Point | Decision | Summary | Decided by | Artifact | Evidence "
            "| Superseded by |"
        ),
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for entry in decisions:
        artifact = entry.get("artifact") or {}
        evidence = ", ".join(link(item) for item in entry.get("evidence", []))
        lines.append(
            f"| {entry['id']} | {entry['point']} | {entry['decision']} "
            f"(agent-provisional) | {neutralize(entry['summary'])} | "
            f"{_decided_by(entry)} | {link(artifact.get('path', ''))} "
            f"{_code(str(artifact.get('sha256', ''))[:12])} | {evidence} | "
            f"{replaced.get(entry['id'], '')} |"
        )
    return lines


def _review_lines(run: dict, decisions: list[dict], link: object) -> list[str]:
    reviews = [e for e in decisions if e.get("review")]
    lines = ["## Reviews", ""]
    if not reviews:
        return [*lines, "No review recorded yet.", ""]
    for entry in reviews:
        review = entry["review"]
        agent = entry.get("agent") or {}
        lines.append(
            f"- {entry['id']} {review['kind']}: {review['verdict']}; reviewer "
            f"{neutralize(agent.get('provider', ''))}/"
            f"{neutralize(agent.get('model', 'unreported'))}; cross-provider: "
            f"{'yes' if review.get('cross_provider') else 'no'}; report "
            f"{link(review.get('report', ''))}"
        )
    if not run.get("cross_provider") or any(
        not e["review"].get("cross_provider") for e in reviews
    ):
        lines += ["", "Reduced independence: reviews used the authoring provider."]
    return [*lines, ""]


def _open_findings(decisions: list[dict]) -> list[str]:
    lines = ["## Open findings", ""]
    found = []
    for entry in current_decisions(decisions):
        for finding in (entry.get("review") or {}).get("findings", []):
            if finding.get("disposition") in {"accepted-provisionally", "open"}:
                reason = finding.get("reason") or "no reason given"
                found.append(
                    f"- {entry['id']} {finding['id']} ({finding['severity']}, "
                    f"{finding['label']}, {finding['disposition']}): "
                    f"{neutralize(reason)}"
                )
    return [*lines, *(found or ["None."]), ""]


IGNORED_FILES_NOTE = (
    "- run-checks ran in the run's worktree, so git-ignored files there were "
    "visible to them and are not part of this PR"
)


def _check_lines(checks: list[dict] | None) -> list[str]:
    lines = ["## Checks", ""]
    if checks is None:
        lines.append("- run-checks: not run yet")
    else:
        lines += [
            f"- runner: {_code(c['command'])} exited {c['exit']} in "
            f"{c['seconds']:.1f}s" + (" (timed out)" if c.get("timed_out") else "")
            for c in checks
        ]
    lines += [
        IGNORED_FILES_NOTE,
        "- agent-reported: none; agent claims never satisfy run-checks",
        "",
        "CI results appear on this PR.",
        "",
    ]
    return lines


def _relative_link(record_dir: str) -> object:
    depth = len(Path(record_dir).parts)

    def link(path: str) -> str:
        if not path:
            return ""
        if path.startswith("https://"):
            return f"<{neutralize(path)}>"
        target = "../" * depth + path
        return f"[{neutralize(path)}]({target})"

    return link


def _sections(
    run: dict,
    decisions: list[dict],
    checks: list[dict] | None,
    link: object,
    *,
    short: bool = False,
) -> list[str]:
    material = [e for e in current_decisions(decisions) if e.get("material")]
    lines = [*_mode_lines(run), *_r2_lines(run, decisions)]
    lines += ["## Material provisional changes", ""]
    lines += [
        f"- {e['id']} ({e['point']}, agent-provisional): {neutralize(e['summary'])}"
        for e in material
    ] or ["None."]
    lines += ["", "## Provisional decisions", ""]
    lines += _decision_rows(decisions, link, short=short) if decisions else ["None."]
    lines.append("")
    if not short:
        for entry in decisions:
            lines += [f"### {entry['id']} basis", "", *_quote_block(entry["basis"]), ""]
            notes = entry.get("notes") or []
            if notes:
                lines += ["Runner notes:", "", *(f"- {neutralize(n)}" for n in notes)]
                lines.append("")
    lines += _review_lines(run, decisions, link)
    lines += _open_findings(decisions)
    lines += _check_lines(checks)
    return lines


def record_path(feature: str) -> str:
    """Repository-relative path of the committed record."""
    return f"{feature}/autonomous/record.md"


def render_record(run: dict, decisions: list[dict], checks: list[dict] | None) -> str:
    """Deterministic bytes of specs/<f>/autonomous/record.md."""
    record_dir = str(Path(record_path(run["feature"])).parent)
    lines = [
        "# Autonomous run record",
        "",
        (
            f"Run {_code(run['run_id'])} for #{run['issue']} "
            f"({_code(run['feature'])}). Generated from the operator records; every "
            "check re-renders it, so an edit fails the next check. Every decision "
            "below is agent-provisional; merging the PR that contains this record "
            "is the only human approval."
        ),
        "",
        *_sections(run, decisions, checks, _relative_link(record_dir)),
    ]
    return "\n".join(lines).rstrip("\n") + "\n"


def render_pr_body(  # noqa: PLR0913 - one rendering, every input explicit
    run: dict,
    decisions: list[dict],
    checks: list[dict] | None,
    staged: list[str],
    *,
    repo: str,
    branch: str,
) -> str:
    """Render the Draft PR body; short decision rows over 60,000 characters."""

    def link(path: str) -> str:
        if not path:
            return ""
        if path.startswith("https://"):
            return f"<{neutralize(path)}>"
        return f"[{neutralize(path)}](https://github.com/{repo}/blob/{branch}/{path})"

    header = [
        (
            f"Autonomous run {run['run_id']} for #{run['issue']} — all intermediate "
            "decisions are agent-provisional. Merging this PR is the only human "
            "approval."
        ),
        "",
    ]
    footer = [
        "## Changed paths",
        "",
        *(f"- {_code(p)}" for p in staged),
        "",
        f"Refs #{run['issue']}",
    ]
    for short in (False, True):
        sections = _sections(run, decisions, checks, link, short=short)
        if short:
            sections.insert(
                0, f"Full decision rows: {link(record_path(run['feature']))}"
            )
            sections.insert(1, "")
        body = "\n".join([*header, *sections, *footer]) + "\n"
        if len(body) <= MAX_BODY:
            return body
    return body


# --- Publication ----------------------------------------------------------


def privileged_union(run: dict, decisions: list[dict]) -> list[str]:
    """Every privileged action declared at start or during the run."""
    actions = set(run["eligibility"].get("privileged_actions", []))
    for entry in decisions:
        actions.update(entry.get("privileged_actions") or [])
    return sorted(actions)


def _protected_path(path: str) -> bool:
    return any(path == p or path.startswith(p + "/") for p in PROTECTED)


def publish(root: Path, run_id: str) -> dict:  # noqa: C901, PLR0911, PLR0912
    """Commit, push and open one Draft PR as the operator.

    Returns {"ok": bool, "category": str|None, "message": str, "url": str|None}.
    Never merges, marks ready, releases, deploys or force-pushes.
    """

    def refuse(category: str, message: str) -> dict:
        return {"ok": False, "category": category, "message": message, "url": None}

    try:
        run = read_run(root, run_id)
        decisions = read_decisions(root, run_id)
        policy = run["eligibility"]["policy"]
        unauthorized = unauthorized_actions(privileged_union(run, decisions), policy)
        if unauthorized:
            return refuse(
                "ineligible",
                f"{REFUSAL}privileged action {', '.join(unauthorized)} before merge",
            )
        reasons = risk_reasons(run["risk"]["level"], run["risk"]["boundaries"], policy)
        if reasons:
            return refuse("ineligible", reasons[0])
        repo, default_branch = repository(root, "forge")
        branch = git(root, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
        if branch in {"", "HEAD", default_branch}:
            return refuse("postcondition", BRANCH_REFUSAL)
        if not _origin_is(root, repo):
            return refuse("postcondition", ORIGIN_REFUSAL)
        push_url = _push_url(root, repo)
        prs = _gh(
            root,
            "pr",
            "list",
            "--repo",
            repo,
            "--head",
            branch,
            "--state",
            "open",
            "--json",
            "number,url,body,isCrossRepository,headRepository,headRepositoryOwner",
            category="forge",
        )
        adopted = _adoptable(prs, run["feature"], repo)
        if prs and adopted is None:
            return refuse("postcondition", f"{BRANCH_REFUSAL}; reuse is #17")
        checked = run.get("checked_tree")
        if not checked or checked_digest(root, run["feature"]) != checked:
            return refuse(
                "postcondition",
                "the working tree differs from the tree that passed run-checks",
            )
        snapshot = read_json(run_dir(root, run_id) / "git-config.json", "Git snapshot")
        if snapshot != config_snapshot(root):
            return refuse(
                "postcondition",
                "repository Git configuration or hooks changed during the run",
            )
        findings = program_findings(root) + [
            f"attribute driver {d} is configured" for d in attribute_drivers(root)
        ]
        if findings:
            return refuse("postcondition", "; ".join(findings))
        head = run.get("head")
        allowed = set(
            git(
                root, "diff-tree", "-r", "--name-only", "--no-renames", head, checked
            ).stdout.split()
        )
        # The record is rendered by trusted recorders, so it is always publishable.
        allowed.add(record_path(run["feature"]))
        git(root, "add", "--all")
        staged = git(
            root, "diff", "--cached", "--name-only", "--no-renames", head
        ).stdout.split()
        problems = [p for p in staged if _protected_path(p) or (p not in allowed)] + [
            p
            for p in staged
            if (root / p).is_file() and (root / p).stat().st_size > MAX_PUBLISHED_FILE
        ]
        if problems:
            git(root, "reset", "-q", check=False)
            return refuse(
                "postcondition",
                "refusing to publish unexpected, protected or oversized paths: "
                + ", ".join(sorted(set(problems))[:10]),
            )
        if git(root, "diff", "--cached", "--quiet", check=False).returncode != 0:
            title = f"feat: {run.get('issue_title') or 'autonomous change'}"
            git(
                root,
                "commit",
                "--no-verify",
                "-q",
                "-m",
                title[:100],
                "-m",
                f"Refs #{run['issue']}",
                "-m",
                f"Autonomous-Run: {run_id}",
            )
        pushed = _push(root, push_url, branch)
        if pushed.returncode != 0:
            return refuse("forge", f"git push failed: {pushed.stderr.strip()[:500]}")
        body = render_pr_body(
            run,
            decisions,
            read_checks(root, run_id),
            staged,
            repo=repo,
            branch=branch,
        )
        _guard_body(body)
        title = f"feat: {run.get('issue_title') or 'autonomous change'}"[:100]
        if adopted is not None:
            url = _adopt_pr(root, repo, adopted, body)
        else:
            url = _create_pr(
                root, repo, base=default_branch, head=branch, title=title, body=body
            )
    except AutonomyError as error:
        return refuse(error.category, str(error))
    return {"ok": True, "category": None, "message": "published", "url": url}


def _guard_body(body: str) -> None:
    if HUMAN_APPROVAL.search(body):
        message = "PR body would claim a human approval"
        raise AutonomyError(message)


def _trusted() -> ModuleType:
    """draft_pr, imported late: it imports ledger, which imports this module."""
    import draft_pr  # noqa: PLC0415

    return draft_pr


def _origin_is(root: Path, repo: str) -> bool:
    """Whether `origin` is the pinned GitHub repository; it receives the push."""
    url = git(root, "remote", "get-url", "origin", check=False).stdout.strip()
    match = _trusted().GITHUB_REMOTE.fullmatch(url)
    return match is not None and "/".join(match.group("owner", "repo")).lower() == (
        repo.lower()
    )


def _push_url(root: Path, repo: str) -> str:
    """Return the pinned repository's URL, in the scheme `origin` uses.

    Pushing to it, not to `origin`, keeps `remote.origin.pushurl` out of play.
    """
    origin = git(root, "remote", "get-url", "origin").stdout.strip()
    if origin.startswith("https://"):
        return f"https://github.com/{repo}.git"
    return f"ssh://git@github.com/{repo}.git"


def _push(root: Path, url: str, branch: str) -> subprocess.CompletedProcess[str]:
    """Push HEAD to the pinned URL without reading the checkout's configuration.

    The checkout's config is agent-writable: `core.sshCommand`,
    `credential.helper`, includes, URL rewrites and hooks could run commands
    with the operator's credentials or redirect the push, and no list of them
    is complete. So the push runs from a throwaway bare repository with an
    empty config that borrows the checkout's objects; only the operator's
    global and system configuration apply. On success it records `origin`
    as the branch's upstream, which the #17 checkpoint reads.
    """
    draft_pr = _trusted()
    head = git(root, "rev-parse", "--verify", "HEAD^{commit}").stdout.strip()
    objects = git_path(root, "--git-common-dir") / "objects"
    executable, _ = draft_pr._resolve("git", root)  # noqa: SLF001
    if executable is None:
        message = "git not found outside working trees"
        raise AutonomyError(message)
    env = {
        key: value
        for key, value in os.environ.items()
        if key not in draft_pr.GIT_LOCATION
        and not key.startswith(("GIT_CONFIG_PARAMETERS", "GIT_CONFIG_COUNT"))
        and not key.startswith(("GIT_CONFIG_KEY_", "GIT_CONFIG_VALUE_"))
    }
    env["PATH"] = draft_pr._child_path(root)  # noqa: SLF001
    state = state_dir(root)
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    with tempfile.TemporaryDirectory(prefix="ballast-push-", dir=state) as away:
        bare = Path(away) / "push.git"

        def run(*args: str) -> subprocess.CompletedProcess[str]:
            return subprocess.run(  # noqa: S603 - trusted git, argument list
                [executable, *GIT_HARDENING, *args],
                cwd=away,
                env=env,
                capture_output=True,
                text=True,
                timeout=600,
                check=False,
            )

        made = run("init", "-q", "--bare", str(bare))
        if made.returncode != 0:
            return made
        alternates = bare / "objects/info/alternates"
        alternates.write_text(f"{objects}\n", encoding="utf-8")
        pushed = run(f"--git-dir={bare}", "push", url, f"{head}:refs/heads/{branch}")
    if pushed.returncode == 0:
        git(root, "config", f"branch.{branch}.remote", "origin")
        git(root, "config", f"branch.{branch}.merge", f"refs/heads/{branch}")
    return pushed


def _own_head(pr: dict, repo: str) -> bool:
    """Whether a `gh pr list` entry's head is a branch of repo itself.

    The rule of draft_pr._pull_request, on `gh pr list --json` fields.
    """
    owner, _, name = repo.lower().partition("/")
    head = pr.get("headRepository")
    login = pr.get("headRepositoryOwner")
    return (
        pr.get("isCrossRepository") is False
        and isinstance(head, dict)
        and str(head.get("name")).lower() == name
        and isinstance(login, dict)
        and str(login.get("login")).lower() == owner
        and str(pr.get("url")).lower()
        == f"https://github.com/{repo}/pull/{pr.get('number')}".lower()
    )


def _adoptable(prs: object, feature: str, repo: str) -> tuple[int, str, str] | None:
    """Return the one open PR the #17 checkpoint opened for this feature.

    That is (number, url, managed section), or None: any other open PR, or
    more than one, is refused.
    """
    draft_pr = _trusted()
    if not isinstance(prs, list) or len(prs) != 1 or not isinstance(prs[0], dict):
        return None
    if not _own_head(prs[0], repo):
        return None
    number, url, body = (prs[0].get(key) for key in ("number", "url", "body"))
    if type(number) is not int or not isinstance(url, str) or not isinstance(body, str):
        return None
    begin, end = draft_pr.MARK_BEGIN, draft_pr.MARK_END
    if body.count(begin) != 1 or body.count(end) != 1:
        return None
    start, stop = body.find(begin), body.find(end)
    section = body[start : stop + len(end)]
    if stop < start or f"- Feature: `{feature}/`" not in section:
        return None
    return number, url, section


def _adopt_pr(root: Path, repo: str, adopted: tuple[int, str, str], body: str) -> str:
    """Put the summary on the checkpoint's PR, keeping its managed section."""
    number, url, section = adopted
    _gh(
        root,
        "pr",
        "edit",
        str(number),
        "--repo",
        repo,
        "--body-file",
        "-",
        stdin=body + "\n" + section + "\n",
        category="forge",
    )
    return url


def _create_pr(  # noqa: PLR0913 - every input explicit
    root: Path, repo: str, *, base: str, head: str, title: str, body: str
) -> str:
    argv = ["pr", "create", "--draft", "--repo", repo, "--head", head]
    if base:
        argv += ["--base", base]
    created = _gh(
        root, *argv, "--title", title, "--body-file", "-", stdin=body, category="forge"
    )
    return (str(created).strip().splitlines() or [""])[-1]


def read_checks(root: Path, run_id: str) -> list[dict] | None:
    """run-checks results, when the step ran."""
    path = run_dir(root, run_id) / "checks.json"
    if not os.path.lexists(path):
        return None
    data = read_json(path, "check results")
    if not isinstance(data, list):
        message = "check results are malformed"
        raise AutonomyError(message)
    return data
