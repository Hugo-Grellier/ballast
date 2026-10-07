"""Operator-driven Chat runs (#20): one `ballast run` invocation per action.

Trust boundary: this module is operator-side only. `run.py` imports it at
startup, inside the trust baseline the launcher verified, and calls it for
`start --mode chat`, `step`, `status`, `approve`, `reject`, `resolve`,
`checks`, `mode`, `continue --mode chat` and a Chat `publish`. No agent step
can run it: the launcher refuses every command while a step is active, and an
interactive step runs under bubblewrap, which hides operator state.

- The operator run record under `autonomy.run_dir` is the only source of
  truth: `run.json`, `steps.jsonl`, the hash-chained `events.jsonl` (E-NNNN)
  and `human-decisions.jsonl` (HD-NNNN), and content-addressed tree manifests.
  The ledger, the handoff summary and the PR section are projections of it.
- A phase starts only when its cumulative `artifacts.py` checks and its
  current human approvals pass when it is requested; each evaluation is
  recorded, so a failed check blocks until a later run of it passes, whatever
  the mode. Nothing stores a "blocked" flag.
- Gates open only through `approve` with a TTY and typed confirmation, bound
  to the artifact's digest; agent output never opens one.

See specs/20-chat-mode/contracts/ for the command, phase-graph, step-runner,
run-record and PR-evidence contracts. Standard library only; runs under
`python3 -I -S`.
"""

from __future__ import annotations

import sys

if __name__ == "__main__":
    sys.stderr.write(
        "chat.py is part of the trusted runner; use `ballast run` "
        "(see docs/policies/spec-kit-workflow.md)\n"
    )
    sys.exit(2)

import contextlib
import fcntl
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

# Never read or write checkout bytecode, including for the imports below.
sys.pycache_prefix = os.devnull

import agent  # noqa: E402
import artifacts  # noqa: E402
import autonomy  # noqa: E402
import branch_sync  # noqa: E402
import draft_pr  # noqa: E402
import launcher  # noqa: E402
import ledger  # noqa: E402

if TYPE_CHECKING:
    from collections.abc import Callable

HERE = Path(__file__).resolve().parent
EXIT_OK = 0
EXIT_BLOCKED = 1
EXIT_REFUSED = 2
EXIT_TAMPERED = 4
EXIT_INTERRUPTED = 130
ESCAPE = b"\x1d\x1d"
DETAIL_LIMIT = 2000
PATH_LIMIT = 500
WORKFLOW_ID = "ballast-feature"
NO_TERMINAL = (
    "Chat steps need a terminal; use `ballast run mode RUN human-gated` for "
    "headless steps"
)
# The separator of the summary's and the PR section's identity line.
SEP = f" {chr(0xB7)} "  # a middle dot

# Phase -> ballast-feature step ID, Spec Kit command, entry condition,
# postcondition checks and write scope (contracts/phase-graph.md). An entry
# requirement is ("check", name), ("approval", gate) or ("baseline", None).
PHASES: dict[str, dict[str, Any]] = {
    "specify": {
        "step_id": "specify",
        "command": "speckit-specify",
        "entry": [("approval", "scope")],
        "post": ["spec"],
        "scope": "feature",
    },
    "clarify": {
        "step_id": "clarify",
        "command": "speckit-clarify",
        "entry": [("check", "spec")],
        "post": ["clarified-spec"],
        "scope": "feature",
    },
    "plan": {
        "step_id": "plan",
        "command": "speckit-plan",
        # The registered block, and no later rejection of intent.
        "entry": [("check", "intent"), ("approval", "intent")],
        "post": ["plan"],
        "scope": "feature",
    },
    "tasks": {
        "step_id": "tasks",
        "command": "speckit-tasks",
        "entry": [("check", "plan"), ("approval", "plan")],
        "post": ["tasks"],
        "scope": "feature",
    },
    "analyze": {
        "step_id": "analyze",
        "command": "speckit-analyze",
        "entry": [("check", "tasks")],
        "post": ["tasks"],
        "scope": "feature",
    },
    "implement": {
        "step_id": "implement",
        "command": "speckit-intent-implement",
        "entry": [("check", "tasks"), ("approval", "tasks"), ("baseline", None)],
        "post": ["implementation"],
        "scope": "worktree",
    },
    "reconcile-intent": {
        "step_id": "reconcile-intent",
        "command": "speckit-intent-decisions",
        "entry": [("check", "implementation"), ("approval", "implementation")],
        "post": ["decision-structure"],
        "scope": "worktree",
    },
    "converge": {
        "step_id": "converge",
        "command": "speckit-converge",
        # Cumulative, as in ballast-feature: converge follows reconcile-intent.
        "entry": [
            ("check", "implementation"),
            ("approval", "implementation"),
            ("check", "decisions"),
        ],
        "post": ["plan", "tasks-done", "decisions"],
        "scope": "worktree",
    },
    "review": {
        "step_id": None,  # the review handoff of the kind's gate
        "command": None,  # the kind's shipped review skill
        "entry": None,  # the kind's artifact check
        "post": ["review-report"],
        "scope": "reviews",
    },
}
# Review kind -> entry, report, skill, verdicts and the gate it hands off to.
REVIEW_KINDS: dict[str, dict[str, Any]] = {
    "plan": {
        "entry": [("check", "plan")],
        "report": "reviews/plan-review.md",
        "skill": "ballast-engineering-review",
        "verdicts": ("approved", "changes-requested"),
        "step_id": "review-plan",
    },
    "implementation": {
        "entry": [("check", "implementation")],
        "report": "reviews/implementation-review.md",
        "skill": "ballast-engineering-review",
        "verdicts": ("approved", "changes-requested"),
        "step_id": "review-implementation",
    },
    "security": {
        "entry": [("check", "implementation")],
        "report": "reviews/security-review.md",
        "skill": "ballast-security-review",
        "verdicts": ("approved", "changes-requested"),
        "step_id": "review-implementation",
    },
    "test": {
        "entry": [("check", "implementation")],
        "report": "reviews/test-review.md",
        "skill": "ballast-test-review",
        "verdicts": ("approved", "changes-requested"),
        "step_id": "review-implementation",
    },
    "documentation": {
        "entry": [("check", "implementation")],
        "report": "reviews/documentation-review.md",
        "skill": "ballast-documentation-review",
        "verdicts": ("approved", "changes-requested"),
        "step_id": "review-implementation",
    },
    "spec-reconciliation": {
        "entry": [("check", "decisions"), ("check", "tasks-done")],
        "report": "reviews/convergence.md",
        "skill": "ballast-spec-reconciliation",
        "verdicts": ("CONVERGED", "PARTIAL", "FAILED"),
        "step_id": "spec-reconciliation",
    },
}
VERDICTS = ("approved", "changes-requested", "CONVERGED", "PARTIAL", "FAILED")
# artifacts.VERDICT_LINE, with the hyphen `changes-requested` needs.
VERDICT_LINE = re.compile(
    r"^\s*(?:[-*]\s+)?(?:\*\*)?Verdict(?:\*\*)?\s*:\s*(?:\*\*)?([A-Za-z_-]+)",
    re.MULTILINE,
)
# The ledger's review verdict enum for each Chat verdict.
LEDGER_VERDICTS = {
    "approved": "approved",
    "changes-requested": "changes-requested",
    "CONVERGED": "approved",
    "PARTIAL": "partial",
    "FAILED": "failed",
}
# Gate -> ballast-feature gate ID, the artifact shown, the precondition, the
# producer steps it covers (ledger report) and the Autonomous decision point a
# continued run's provisional decisions were taken at.
GATES: dict[str, dict[str, Any]] = {
    "scope": {
        "gate_id": "scope-gate",
        "pre": [("check", "scope")],
        "covers": [],
        "point": "scope",
    },
    "intent": {
        "gate_id": "approve-intent",
        "pre": [("check", "clarified-spec")],
        "covers": ["specify", "clarify"],
        "point": "intent",
    },
    "plan": {
        "gate_id": "review-plan",
        "pre": [("check", "plan")],
        "covers": ["plan"],
        "point": "plan",
    },
    "tasks": {
        "gate_id": "review-tasks",
        "pre": [("check", "tasks"), ("approval", "intent"), ("approval", "plan")],
        "covers": ["tasks", "analyze"],
        "point": "tasks",
    },
    "implementation": {
        "gate_id": "review-implementation",
        "pre": [("check", "implementation"), ("approval", "tasks")],
        "covers": ["implement"],
        "point": "implementation-review",
    },
    "spec-reconciliation": {
        "gate_id": "spec-reconciliation",
        "pre": [("check", "convergence")],
        "covers": ["reconcile-intent", "converge"],
        "point": "spec-reconciliation",
    },
    "final": {
        "gate_id": "final-acceptance",
        "pre": [
            ("check", "convergence"),
            ("approval", "spec-reconciliation"),
            ("checks", None),
            # DEC-0002: every earlier approval must still be current.
            ("approval", "scope"),
            ("approval", "intent"),
            ("approval", "plan"),
            ("approval", "tasks"),
            ("approval", "implementation"),
        ],
        "covers": [
            "specify",
            "clarify",
            "plan",
            "tasks",
            "analyze",
            "implement",
            "reconcile-intent",
            "converge",
        ],
        "point": "final-acceptance",
    },
}
OUTCOMES = ("completed", "failed", "interrupted", "tampered")
EVENT_KINDS = (
    "check",
    "project-checks",
    "review",
    "out-of-step-change",
    "refusal",
    "sync",
)
# Pseudo-checks that are approvals or records, never artifact checks.
RECORD_CHECKS = ("baseline", "project-checks", "scope")
# An entry check over earlier write-scope failures (DEC-0003).
OPEN_VIOLATIONS = "open-write-scope"


class Refused(Exception):  # noqa: N818 - a refusal, not an error
    """A Chat command stops here with an exit status and one reason."""

    def __init__(self, code: int, message: str) -> None:
        """Keep the exit status with the reason."""
        super().__init__(message)
        self.code = code


def _now() -> str:
    return autonomy.now()


def _stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")


def _out(text: str = "") -> None:
    sys.stdout.write(text + "\n")
    sys.stdout.flush()


def _err(text: str) -> None:
    sys.stderr.write(text + "\n")
    sys.stderr.flush()


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _text_digest(path: Path, *, tasks: bool = False) -> str | None:
    """Digest of an artifact's normalized text; None when it is absent.

    For tasks.md the checkboxes are left out: implementing marks tasks done,
    which must not make the tasks approval stale; a changed task does.
    """
    if path.is_symlink() or not path.is_file():
        return None
    text = path.read_text(encoding="utf-8", errors="replace")
    if tasks:
        text = TASK_BOX.sub(r"\1[ ]", text)
    return artifacts.spec_digest(text)


TASK_BOX = re.compile(r"(?m)^(\s*[-*] )\[[xX]\]")


# --- The operator run record ------------------------------------------------


class Run:
    """One Chat run's operator record, read and appended by trusted code only."""

    def __init__(self, root: Path, record: dict) -> None:
        """Wrap a validated `ballast-chat` record."""
        self.root = root
        self.record = record
        self.id: str = record["run_id"]
        self.dir = autonomy.run_dir(root, self.id)
        self.feature_dir: str = record["feature"]
        self._tree: str | None = None

    # files

    def save(self) -> None:
        """Validate and store run.json."""
        autonomy.write_run(self.root, self.record)

    def feature(self) -> artifacts.Feature:
        """Return the Chat feature: approvals and baseline from operator state."""
        return artifacts.Feature.from_operator_run(self.root, self.record)

    def events(self) -> list[dict]:
        """Every recorded event, the hash chain verified."""
        return autonomy.read_log(self.dir / "events.jsonl", "E")

    def humans(self) -> list[dict]:
        """Every human decision, chain and fields verified."""
        entries = autonomy.read_human_decisions(self.root, self.id)
        for entry in entries:
            autonomy.validate_human_decision(entry)
        return entries

    def steps(self) -> list[dict]:
        """Every step entry (start and close)."""
        return autonomy.read_steps(self.root, self.id)

    def event(self, kind: str, **fields: object) -> dict:
        """Append one event; never rewrite one."""
        if kind not in EVENT_KINDS:
            message = f"unknown event kind {kind!r}"
            raise autonomy.AutonomyError(message)
        return autonomy.append_log(
            self.dir / "events.jsonl", "E", {**fields, "kind": kind, "at": _now()}
        )

    def step_entry(self, entry: dict) -> None:
        """Append one step entry."""
        autonomy.append_step(self.root, self.id, entry)

    def human(self, kind: str, ref: str, **extra: object) -> dict:
        """Append one human decision with its kind's fields."""
        return autonomy.append_human_decision(
            self.root, self.id, kind, ref, resolves=None, extra=extra
        )

    # identity

    @property
    def mode(self) -> str:
        """The run's effective mode: chat or human-gated."""
        return autonomy.effective_mode(self.record)

    @property
    def issue(self) -> int:
        """The Issue number the run is for."""
        return int(self.record["issue"])

    def tree(self) -> str:
        """Tree digest of the worktree, the feature's reviews/ left out."""
        if self._tree is None:
            self._tree = autonomy.tree_digest(
                self.root, (f"{self.feature_dir}/reviews",)
            )
        return self._tree

    def changed(self) -> None:
        """Forget cached digests after a write to the worktree."""
        self._tree = None

    def file(self, name: str) -> Path:
        """Return a feature artifact path."""
        return self.root / self.feature_dir / name


def create_files(directory: Path) -> None:
    """Return the record's logs and manifest directory, mode 0600 in a 0700 one."""
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    (directory / "manifests").mkdir(exist_ok=True, mode=0o700)
    for name in ("steps.jsonl", "events.jsonl", "human-decisions.jsonl"):
        flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW
        os.close(os.open(directory / name, flags, 0o600))


def load(root: Path, run_id: str) -> Run:
    """Return the Chat run `run_id`; anything else is refused."""
    if not autonomy.RUN_ID.fullmatch(run_id or ""):
        raise Refused(EXIT_REFUSED, "a valid RUN_ID is required")
    try:
        record = autonomy.find_run(root, run_id)
    except autonomy.AutonomyError as error:
        raise Refused(EXIT_REFUSED, f"run {run_id}: {error}") from error
    if record is None:
        raise Refused(EXIT_REFUSED, f"run {run_id} has no operator run record")
    if record["workflow"] != autonomy.CHAT:
        raise Refused(EXIT_REFUSED, f"run {run_id} is not a Chat run")
    return Run(root, record)


class Lock:
    """The run's lock: non-blocking, held for the whole invocation (R8)."""

    def __init__(self, run: Run, holder: str) -> None:
        """Name what this invocation does, for a refused second holder."""
        self.run = run
        self.holder = holder
        self.fd: int | None = None

    def __enter__(self) -> Lock:  # noqa: PYI034 - Lock is final; no subclass
        """Take the lock, or refuse and name who holds it."""
        path = self.run.dir / "lock"
        flags = os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW
        self.fd = os.open(path, flags, 0o600)
        try:
            fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            held = os.pread(self.fd, 200, 0).decode("utf-8", "replace").strip()
            os.close(self.fd)
            self.fd = None
            active = self.run.record.get("active_step") or {}
            named = held or (
                f"step {active.get('step')}" if active else "another invocation"
            )
            message = f"run {self.run.id} is busy: {named}"
            raise Refused(EXIT_REFUSED, message) from error
        os.ftruncate(self.fd, 0)
        os.pwrite(self.fd, f"{self.holder} (pid {os.getpid()})".encode(), 0)
        # Read again under the lock: another invocation may have changed it.
        self.run.record = autonomy.read_run(self.run.root, self.run.id)
        return self

    def describe(self, holder: str) -> None:
        """Update what the holder is doing (a step names itself once started)."""
        if self.fd is not None:
            os.ftruncate(self.fd, 0)
            os.pwrite(self.fd, f"{holder} (pid {os.getpid()})".encode(), 0)

    def __exit__(self, *_: object) -> None:
        """Release the lock."""
        if self.fd is not None:
            with contextlib.suppress(OSError):
                os.ftruncate(self.fd, 0)
            os.close(self.fd)
            self.fd = None


# --- Tree manifests and out-of-step changes ---------------------------------


def manifest(root: Path) -> dict[str, str]:
    """{path: sha256} of every tracked and unignored file outside `.git`.

    Listed by the operator's Git with hooks, fsmonitor and every filter driver
    disabled; content is hashed here, unfiltered, so no checkout-configured
    program runs. A symlink is recorded by its target.
    """
    listed = autonomy.git(
        root, "ls-files", "-z", "--cached", "--others", "--exclude-standard"
    ).stdout
    found: dict[str, str] = {}
    for name in sorted({item for item in listed.split("\0") if item}):
        path = root / name
        if path.is_symlink():
            found[name] = "link:" + str(path.readlink())
        elif path.is_file():
            with path.open("rb") as handle:
                found[name] = hashlib.file_digest(handle, "sha256").hexdigest()
    return found


def manifest_digest(mapping: dict[str, str]) -> str:
    """Content address of a manifest."""
    text = json.dumps(mapping, sort_keys=True, separators=(",", ":"))
    return _sha(text.encode())


def store_manifest(directory: Path, mapping: dict[str, str]) -> str:
    """Store a manifest once, under its digest; return the digest."""
    digest = manifest_digest(mapping)
    path = directory / "manifests" / f"{digest}.json"
    if not os.path.lexists(path):
        autonomy.write_json(path, mapping)
    return digest


def read_manifest(directory: Path, digest: str | None) -> dict[str, str]:
    """Return a stored manifest; an unknown or missing one reads as empty."""
    if not digest or not autonomy.MANIFEST_DIGEST.fullmatch(digest):
        return {}
    path = directory / "manifests" / f"{digest}.json"
    if not os.path.lexists(path):
        return {}
    data = autonomy.read_json(path, "tree manifest")
    if not isinstance(data, dict) or manifest_digest(data) != digest:
        message = f"tree manifest {digest[:12]} does not match its digest"
        raise autonomy.AutonomyError(message)
    return data


def changed_paths(before: dict[str, str], after: dict[str, str]) -> list[str]:
    """Paths added, removed or changed between two manifests, sorted."""
    return sorted(
        name
        for name in before.keys() | after.keys()
        if before.get(name) != after.get(name)
    )


def current_manifest(run: Run) -> str:
    """Store the current tree's manifest and return its digest."""
    return store_manifest(run.dir, manifest(run.root))


def _bounded(paths: list[str]) -> dict[str, object]:
    fields: dict[str, object] = {"paths": paths[:PATH_LIMIT]}
    if len(paths) > PATH_LIMIT:
        fields["more"] = len(paths) - PATH_LIMIT
    return fields


def out_of_step(run: Run, actor: str = "operator") -> dict | None:
    """Record changes made between steps, attributed to `actor` (FR-011).

    The actor is the operator, or `sync` for what a branch synchronization
    brought in (#66 ENG-010).

    Compares the tree with the last stored manifest; a difference is one
    `out-of-step-change` event with the changed paths and the human decisions
    whose bound digests no longer match.
    """
    current = current_manifest(run)
    previous = run.record.get("last_manifest")
    if current == previous:
        return None
    paths = changed_paths(
        read_manifest(run.dir, previous), read_manifest(run.dir, current)
    )
    run.changed()
    event = run.event(
        "out-of-step-change",
        actor=actor,
        from_manifest=previous,
        to_manifest=current,
        stale=_made_stale(run, paths),
        **_bounded(paths),
    )
    run.record["last_manifest"] = current
    run.save()
    _reactivate(run)
    return event


def _gate_paths(run: Run, gate: str) -> Callable[[str], bool]:
    feature = run.feature_dir
    names = {
        "intent": {f"{feature}/spec.md", f"{feature}/intent.md"},
        "plan": {f"{feature}/plan.md"},
        "tasks": {f"{feature}/tasks.md"},
        "spec-reconciliation": {f"{feature}/reviews/convergence.md"},
    }
    if gate == "final":
        return lambda _path: True
    if gate == "implementation":
        return lambda path: not path.startswith(f"{feature}/reviews/")
    if gate == "scope":
        return lambda _path: False
    return lambda path: path in names[gate]


def _made_stale(run: Run, paths: list[str]) -> list[str]:
    """HD IDs of current-looking decisions a change of `paths` made stale."""
    stale = []
    humans = run.humans()
    for gate in autonomy.CHAT_GATES:
        latest = _latest_gate_decision(humans, gate)
        if latest is None or latest["kind"] != "gate-approval":
            continue
        touches = _gate_paths(run, gate)
        if (
            any(touches(path) for path in paths)
            and gate_digest(run, gate) != latest["digest"]
        ):
            stale.append(latest["id"])
    if f"{run.feature_dir}/decisions.md" in paths:
        resolved = _resolution_digests(run)
        stale.extend(
            entry["id"]
            for entry in humans
            if entry["kind"] == "decision-resolution"
            and entry["digest"] != resolved.get(entry["decision"])
        )
    return sorted(set(stale))


# --- Gates and approvals ------------------------------------------------------


def gate_artifact(run: Run, gate: str) -> str:
    """Return what a gate's approval is bound to, as shown to the operator."""
    feature = run.feature_dir
    return {
        "scope": f"Issue #{run.issue} and {feature}",
        "intent": f"{feature}/spec.md",
        "plan": f"{feature}/plan.md",
        "tasks": f"{feature}/tasks.md",
        "implementation": "worktree",
        "spec-reconciliation": f"{feature}/reviews/convergence.md",
        "final": "worktree",
    }[gate]


def gate_digest(run: Run, gate: str) -> str | None:
    """Return the digest a gate's approval is bound to now (data-model binding)."""
    if gate == "scope":
        return "sha256:" + _sha(f"{run.issue}\n{run.feature_dir}".encode())
    if gate == "final":
        # DEC-0002: reviews/ included, so no review changes after final.
        return "tree:" + autonomy.tree_digest(run.root, ())
    if gate == "implementation":
        return "tree:" + run.tree()
    name = {
        "intent": "spec.md",
        "plan": "plan.md",
        "tasks": "tasks.md",
        "spec-reconciliation": "reviews/convergence.md",
    }[gate]
    return _text_digest(run.file(name), tasks=gate == "tasks")


def _latest_gate_decision(humans: list[dict], gate: str) -> dict | None:
    found = None
    for entry in humans:
        if (
            entry["kind"] in {"gate-approval", "gate-rejection"}
            and entry["gate"] == gate
        ):
            found = entry
    return found


def approval_state(  # noqa: PLR0911 - complexity inherent to one guarded flow
    run: Run, gate: str, humans: list[dict] | None = None
) -> tuple[str, dict | None]:
    """Return (`current`, `stale`, `rejected` or `pending`, the deciding HD) of a gate.

    The latest approval or rejection decides: a rejection keeps the gate
    closed until a later approval at a current digest. Intent is also current
    through a registered human approval block alone (a run continued from a
    `ballast-feature` run carries it), never through a provisional one.
    """
    humans = run.humans() if humans is None else humans
    latest = _latest_gate_decision(humans, gate)
    if gate == "intent":
        passed, _ = _check(run, "intent")
        if latest is None:
            return ("current" if passed else "pending"), None
        if latest["kind"] == "gate-rejection":
            return "rejected", latest
        current = latest["digest"] == gate_digest(run, gate) and passed
        return ("current" if current else "stale"), latest
    if latest is None:
        return "pending", None
    if latest["kind"] == "gate-rejection":
        return "rejected", latest
    if latest["digest"] == gate_digest(run, gate):
        return "current", latest
    return "stale", latest


def _resolution_digests(run: Run) -> dict[str, str]:
    path = run.file("decisions.md")
    if path.is_symlink() or not path.is_file():
        return {}
    text = path.read_text(encoding="utf-8", errors="replace")
    return {
        dec: artifacts.resolution_digest(body)
        for dec, body in artifacts.latest_resolutions(text).items()
    }


# --- Checks -------------------------------------------------------------------


def _tasks_done(feature: artifacts.Feature) -> None:
    artifacts.check_tasks(feature)
    artifacts._require_tasks_done(feature)  # noqa: SLF001 - the shared rule


CHECKS: dict[str, Callable[[artifacts.Feature], object]] = {
    "spec": artifacts.check_spec,
    "clarified-spec": artifacts.check_clarified_spec,
    "intent": artifacts.check_intent,
    "plan": artifacts.check_plan,
    "tasks": artifacts.check_tasks,
    "tasks-done": _tasks_done,
    "implementation": artifacts.check_implementation,
    "decisions": artifacts.check_decisions,
    "decision-structure": artifacts.check_decision_structure,
    "convergence": artifacts.check_convergence,
}


def _check(run: Run, name: str) -> tuple[bool, str]:  # noqa: PLR0911 - one branch per check kind
    """Run one check; (passed, detail). Nothing is recorded."""
    if name == "scope":
        return _scope_check(run)
    if name == OPEN_VIOLATIONS:
        return _violations_check(run)
    if name == "baseline":
        if run.record.get("baseline"):
            return True, "implementation baseline recorded at tasks approval"
        return False, "no implementation baseline; approve tasks first"
    if name == "project-checks":
        return _checks_result(run)
    try:
        CHECKS[name](run.feature())
    except (
        artifacts.ContractError,
        autonomy.AutonomyError,
        OSError,
        ValueError,
    ) as error:
        return False, str(error)[:DETAIL_LIMIT]
    return True, "passed"


def _violations_check(run: Run) -> tuple[bool, str]:
    """Pass unless a step's out-of-scope change is still in the tree (DEC-0003).

    A path a failed write-scope check named stays open while its content is
    what that step left; restoring or changing it closes it.
    """
    current: dict[str, str] | None = None
    still: list[str] = []
    for event in run.events():
        if event["kind"] != "check" or event.get("check") != "write-scope":
            continue
        if event.get("passed"):
            continue
        current = manifest(run.root) if current is None else current
        after = read_manifest(run.dir, event.get("tree"))
        paths = event.get("paths", [])
        if event.get("more"):
            paths = _all_violations(run, event, after)
        still += [p for p in paths if current.get(p) == after.get(p)]
    if still:
        paths = ", ".join(sorted(set(still))[:10])
        return False, (
            f"a step changed paths outside its write scope: {paths}; "
            "restore or change them before the next step"
        )
    return True, "no open write-scope violation"


def _all_violations(run: Run, event: dict, after: dict[str, str]) -> list[str]:
    """Every out-of-scope path of a failed check that stored only the first few.

    Recomputed from the step's start manifest; when that step is not found,
    every path of the after manifest stays open (fail closed, #66 SEC-002).
    """
    start = next(
        (
            entry
            for entry in run.steps()
            if entry.get("step") == event.get("step") and entry["entry"] == "start"
        ),
        None,
    )
    if start is None:
        return sorted(after)
    before = read_manifest(run.dir, start.get("tree_before"))
    return [
        path
        for path in changed_paths(before, after)
        if not _in_scope(run, start["phase"], path)
    ]


def _scope_check(run: Run) -> tuple[bool, str]:
    pin = branch_sync.read_pin(run.root, run.id)
    match = autonomy.FEATURE.fullmatch(run.feature_dir)
    if match is None or int(match.group(1)) != run.issue:
        return False, f"{run.feature_dir} is not for Issue #{run.issue}"
    if pin.get("feature") not in {None, run.feature_dir}:
        return (
            False,
            f"the pinned feature is {pin.get('feature')}, not {run.feature_dir}",
        )
    if run.record["status"] not in {"active", "completed"}:
        return False, f"run {run.id} is {run.record['status']}"
    return True, f"Issue #{run.issue} matches {run.feature_dir}"


def _checks_result(run: Run) -> tuple[bool, str]:
    latest = None
    for event in run.events():
        if event["kind"] == "project-checks":
            latest = event
    if latest is None:
        return False, "no project checks recorded; run `ballast run checks`"
    if latest["tree"] != run.tree():
        return False, f"the project checks ({latest['id']}) ran on another tree"
    if latest.get("protected_changes"):
        # A check that changed protected inputs proves nothing (#66 ENG-012).
        return False, f"the project checks ({latest['id']}) changed protected inputs"
    if latest.get("unavailable"):
        return True, f"no [checks] table: checks unavailable ({latest['id']})"
    failed = [r["command"] for r in latest["results"] if r["exit"] != 0]
    if failed:
        return False, f"project checks failed ({latest['id']}): {', '.join(failed)}"
    return True, f"project checks passed ({latest['id']})"


def artifact_digests(run: Run) -> dict[str, str]:
    """sha256 of the feature artifacts a check may read."""
    found = {}
    for name in (
        "spec.md",
        "intent.md",
        "plan.md",
        "tasks.md",
        "decisions.md",
        "reviews/convergence.md",
    ):
        path = run.file(name)
        if path.is_file() and not path.is_symlink():
            found[name] = _sha(path.read_bytes())
    return found


def evaluate(
    run: Run, name: str, purpose: str, step: str | None = None, *, record: bool = True
) -> tuple[bool, str, str | None]:
    """Run one check and (by default) record it; (passed, detail, E-id)."""
    passed, detail = _check(run, name)
    if not record:
        return passed, detail, None
    event = run.event(
        "check",
        check=name,
        purpose=purpose,
        passed=passed,
        detail=detail[:DETAIL_LIMIT],
        digests=artifact_digests(run),
        tree=run.record.get("last_manifest"),
        step=step,
    )
    return passed, detail, event["id"]


def _requirement(  # noqa: PLR0913 - complexity inherent to one guarded flow
    run: Run,
    item: tuple[str, str | None],
    purpose: str,
    humans: list[dict],
    *,
    record: bool,
    memo: dict | None = None,
) -> tuple[bool, str, str | None, str]:
    """Evaluate one entry or gate requirement; (passed, detail, E-id, name)."""
    kind, value = item
    if kind == "approval":
        name = f"{value}-approval"
        state, decision = approval_state(run, str(value), humans)
        passed = state == "current"
        detail = f"{value} approval is {state}" + (
            f" ({decision['id']})" if decision else ""
        )
    elif kind == "baseline":
        name = "baseline"
        passed, detail = _check(run, name)
    elif kind == "checks":
        name = "project-checks"
        passed, detail = _check(run, name)
    else:
        name = str(value)
        if memo is not None and name in memo:
            passed, detail = memo[name]
        else:
            passed, detail = _check(run, name)
            if memo is not None:
                memo[name] = (passed, detail)
    if not record:
        return passed, detail, None, name
    event = run.event(
        "check",
        check=name,
        purpose=purpose,
        passed=passed,
        detail=detail[:DETAIL_LIMIT],
        digests=artifact_digests(run),
        tree=run.record.get("last_manifest"),
        step=None,
    )
    return passed, detail, event["id"], name


def _requirements(phase: str, kind: str | None) -> list[tuple[str, str | None]]:
    # DEC-0003: an open write-scope violation blocks every step.
    if phase == "review":
        return [*REVIEW_KINDS[str(kind)]["entry"], ("check", OPEN_VIOLATIONS)]
    return [*PHASES[phase]["entry"], ("check", OPEN_VIOLATIONS)]


def entry(
    run: Run,
    phase: str,
    kind: str | None = None,
    *,
    record: bool = True,
    memo: dict | None = None,
) -> tuple[bool, str | None, str | None, str | None]:
    """Return a phase's entry condition now; (passed, failing check, E-id, detail).

    Requirements run in order and stop at the first failure; each one run
    is recorded (purpose `entry`) unless `record` is False.
    """
    humans = run.humans()
    for item in _requirements(phase, kind):
        passed, detail, event_id, name = _requirement(
            run, item, "entry", humans, record=record, memo=memo
        )
        if not passed:
            return False, name, event_id, detail
    return True, None, None, None


def gate_precondition(
    run: Run, gate: str, *, record: bool = True, memo: dict | None = None
) -> tuple[bool, str | None, str | None, str | None]:
    """Return a gate's precondition now; (passed, failing check, E-id, detail)."""
    humans = run.humans()
    extra = [("check", OPEN_VIOLATIONS)] if gate in {"implementation", "final"} else []
    for item in [*GATES[gate]["pre"], *extra]:
        passed, detail, event_id, name = _requirement(
            run, item, "gate", humans, record=record, memo=memo
        )
        if not passed:
            return False, name, event_id, detail
    return True, None, None, None


def allowed_actions(run: Run) -> list[str]:
    """Return the actions allowed now, in the contract's order; nothing is recorded."""
    memo: dict = {}
    actions = []
    for phase in PHASES:
        if phase == "review":
            actions.extend(
                f"ballast run step {run.id} review --kind {kind}"
                for kind in REVIEW_KINDS
                if entry(run, phase, kind, record=False, memo=memo)[0]
            )
        elif entry(run, phase, record=False, memo=memo)[0]:
            actions.append(f"ballast run step {run.id} {phase}")
    humans = run.humans()
    for gate in GATES:
        if approval_state(run, gate, humans)[0] == "current":
            continue
        if gate_precondition(run, gate, record=False, memo=memo)[0]:
            actions.append(f"ballast run approve {run.id} {gate}")
    implementation = memo.get("implementation") or _check(run, "implementation")
    if implementation[0]:
        actions.append(f"ballast run checks {run.id}")
    if approval_state(run, "final", humans)[0] == "current":
        actions.append(f"ballast run publish {run.id}")
    actions.append(f"ballast run mode {run.id} chat|human-gated --reason TEXT")
    return actions


def _reactivate(run: Run) -> None:
    """Return a completed or published run goes back to active once final is stale."""
    if run.record["status"] in {"completed", "published"}:
        state, _ = approval_state(run, "final")
        if state != "current":
            autonomy.set_status(run.record, "active")
            run.save()


# --- Ledger and archive ---------------------------------------------------------


def _ledger(
    run: Run, kind: str, data: dict[str, Any], event_id: str | None = None
) -> None:
    """Append one runner event to the shared ledger; a failure is reported only."""
    try:
        ledger.append(
            run.root,
            ledger.new_event(run.id, run.feature_dir, kind, "runner", data, event_id),
        )
    except (ledger.LedgerError, OSError, ValueError) as error:
        _err(f"ballast: ledger {kind} not recorded: {error}")


def _log_line(run: Run) -> int:
    """Return the Chat run's own monotonic counter for a ledger step occurrence."""
    try:
        events, _ = ledger.read(run.root, run.id)
    except (ledger.LedgerError, OSError, ValueError):
        events = []
    return 1 + sum(
        1
        for event in events
        if event["kind"] == "step" and event["data"]["action"] == "started"
    )


def _ledger_snapshot(run: Run) -> None:
    try:
        data = ledger.artifact_digests(run.root, run.feature_dir)
    except (ledger.LedgerError, OSError, ValueError) as error:
        _err(f"ballast: ledger snapshot not recorded: {error}")
        return
    _ledger(run, "snapshot", data, f"runner:snapshot:{uuid.uuid4().hex}")


def _ledger_gate(run: Run, gate: str, choice: str) -> None:
    gate_id = GATES[gate]["gate_id"]
    line = _log_line(run)
    _ledger(
        run,
        "step",
        {
            "action": "started",
            "step_id": gate_id,
            "step_type": "gate",
            "log_line": line,
        },
    )
    _ledger(
        run,
        "step",
        {
            "action": "completed",
            "step_id": gate_id,
            "step_type": "gate",
            "status": "completed",
            "log_line": line,
        },
    )
    _ledger(run, "gate", {"step_id": gate_id, "choice": choice, "log_line": line})


def phase_graph() -> dict:
    """Return the phase graph projection archived at start (`run/chat.json`)."""
    return {
        "workflow_id": WORKFLOW_ID,
        "phases": {
            name: {
                "step_id": spec["step_id"],
                "command": spec["command"],
                "post": spec["post"],
                "scope": spec["scope"],
            }
            for name, spec in PHASES.items()
        },
        "review_kinds": {
            kind: {
                "report": spec["report"],
                "skill": spec["skill"],
                "step_id": spec["step_id"],
            }
            for kind, spec in REVIEW_KINDS.items()
        },
        "gates": {
            gate: {"gate_id": spec["gate_id"], "covers": spec["covers"]}
            for gate, spec in GATES.items()
        },
    }


def _archive_definition(run: Run) -> dict[str, Any]:
    """Archive the trusted ballast-feature definition and the phase graph."""
    source = run.root / ".specify/workflows" / WORKFLOW_ID / "workflow.yml"
    archive = ledger.archive_dir(run.root, run.id) / "run"
    data: dict[str, Any] = {
        "action": "started",
        "workflow_id": WORKFLOW_ID,
        "mode": "chat",
    }
    with ledger.archive_lock(run.root, run.id, exclusive=True):
        archive.mkdir(parents=True, exist_ok=True)
        if source.is_file() and not source.is_symlink():
            shutil.copyfile(source, archive / "workflow.yml")
            data["workflow_digest"] = _sha((archive / "workflow.yml").read_bytes())
            with contextlib.suppress(ledger.LedgerError, ValueError):
                data["workflow_version"] = ledger._workflow_identity(archive)[1]  # noqa: SLF001
        (archive / "chat.json").write_text(
            json.dumps(phase_graph(), indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    policy = ledger.archive_policy(run.root, run.id)
    if policy is not None:
        data["policy_digest"] = policy["digest"]
    return data


def archive(run: Run) -> None:
    """Copy the operator record and the run's agent logs into the archive."""
    try:
        target = ledger.archive_dir(run.root, run.id)
        logs = run.root / ".specify/workflow-state" / run.id
        with ledger.archive_lock(run.root, run.id, exclusive=True):
            shutil.copytree(run.dir, target / "operator", dirs_exist_ok=True)
            if logs.is_dir() and not logs.is_symlink() and not logs.parent.is_symlink():
                shutil.copytree(
                    logs, target / "state", dirs_exist_ok=True, symlinks=True
                )
    except (OSError, ValueError, ledger.LedgerError) as error:
        _err(f"ballast: Chat archive failed: {error}")


def checkpoint(run: Run, *, create: bool = True) -> None:
    """Run the Draft PR checkpoint (#17) and its packet (#19); assign no status."""
    try:
        outcome = draft_pr.checkpoint(run.root, run.id, create=create)
        line = draft_pr.format_line(outcome)
        if outcome.packet is not None:
            line += "\n" + draft_pr.packet.format_line(outcome.packet)
    except (Exception, KeyboardInterrupt) as error:  # noqa: BLE001
        line = f"Draft PR: failed-retryable (internal-error) ({type(error).__name__})"
    _out(line)


# --- Synchronization ----------------------------------------------------------


def synchronize(
    run: Run, *, rerun: str | None = None, starting: bool = False, **pin: str | None
) -> branch_sync.Outcome:
    """Run the branch check, print its lines and record a `sync` pointer.

    `rerun` is a Chat step's recovery command; a start or a continuation
    keeps branch_sync's own wording.
    """
    outcome = branch_sync.synchronize(
        run.root,
        run.id,
        feature=run.feature_dir,
        starting=starting,
        rerun=rerun,
        **pin,
    )
    for stream, line in branch_sync.format_lines(outcome):
        (_out if stream == "stdout" else _err)(line)
    pointer = None
    with contextlib.suppress(ledger.LedgerError, OSError, ValueError):
        events, _ = ledger.read(run.root, run.id)
        pointer = next(
            (e["event_id"] for e in reversed(events) if e["kind"] == "branch_sync"),
            None,
        )
    run.event(
        "sync", outcome=outcome.outcome, cause=outcome.cause, ledger_event=pointer
    )
    return outcome


def _inherited_pin(run: Run) -> dict[str, str | None]:
    """Return the source's pin for a continuation that has no pin of its own.

    A continuation whose first synchronization was blocked saved no pin; its
    next step synchronizes as the continuation did, from the source's pin.
    """
    source = run.record.get("continues")
    if not source or branch_sync.read_pin(run.root, run.id):
        return {}
    pin = branch_sync.read_pin(run.root, source)
    return {"branch": pin.get("branch"), "base": pin.get("base"), "source_run": source}


# --- start --mode chat -----------------------------------------------------------


START_INPUTS = ("feature_directory", "idea", "integration", "model")


def _start_inputs(options: list[str]) -> dict[str, str]:
    if len(options) % 2:
        raise Refused(EXIT_REFUSED, "inputs must be given as -i NAME=VALUE")
    inputs: dict[str, str] = {}
    for flag, pair in zip(options[::2], options[1::2], strict=True):
        name, equals, value = pair.partition("=")
        if flag not in {"-i", "--input"} or not equals:
            raise Refused(EXIT_REFUSED, "inputs must be given as -i NAME=VALUE")
        if name not in START_INPUTS:
            message = f"Chat runs accept only -i {', '.join(START_INPUTS)}"
            raise Refused(EXIT_REFUSED, message)
        if name in inputs:
            raise Refused(EXIT_REFUSED, f"input {name} given twice")
        inputs[name] = value
    return inputs


def _model(value: str | None) -> str | None:
    if value is None:
        return None
    if not artifacts.MODEL.fullmatch(value):
        raise Refused(EXIT_REFUSED, "-i model must be a short model name")
    return value


def _confinable(root: Path, integration: str) -> str | None:
    """Why `integration` cannot run an interactive step confined, or None."""
    try:
        autonomy.confinement_self_test(root)
    except autonomy.AutonomyError as error:
        return str(error)
    if integration == "codex" and not autonomy.codex_sandbox_nests(root):
        return "codex cannot start its own sandbox inside Ballast's confinement"
    return None


def _other(integration: str) -> str:
    return next(name for name in autonomy.INTEGRATIONS if name != integration)


def _integration_refusal(root: Path, integration: str, reason: str) -> Refused:
    other = _other(integration)
    hint = ""
    if shutil.which(other) and _confinable(root, other) is None:
        hint = f"; choose another integration: -i integration={other}"
    return Refused(EXIT_REFUSED, f"{integration} cannot run confined: {reason}{hint}")


def _choose_integrations(root: Path, requested: str) -> tuple[str, str]:
    if requested == "auto":
        found = [name for name in autonomy.INTEGRATIONS if shutil.which(name)]
        if not found:
            raise Refused(EXIT_REFUSED, "no agent CLI (claude or codex) found on PATH")
        requested = found[0]
    if requested not in autonomy.INTEGRATIONS:
        raise Refused(EXIT_REFUSED, "integration must be auto, claude or codex")
    if not shutil.which(requested):
        raise Refused(EXIT_REFUSED, f"{requested} CLI not found on PATH")
    reason = _confinable(root, requested)
    if reason is not None:
        raise _integration_refusal(root, requested, reason)
    other = _other(requested)
    review = (
        other if shutil.which(other) and _confinable(root, other) is None else requested
    )
    return requested, review


def _active_chat_runs(root: Path) -> list[str]:
    """Chat runs in this checkout with an active step."""
    runs = launcher.state_dir(root) / "runs"
    found = []
    for path in sorted(runs.iterdir()) if runs.is_dir() else []:
        try:
            record = autonomy.find_run(root, path.name)
        except autonomy.AutonomyError:
            continue
        if record and record["workflow"] == autonomy.CHAT and record.get("active_step"):
            found.append(
                f"run {record['run_id']}, step {record['active_step']['step']}"
            )
    return found


def continued_by(root: Path, run_id: str) -> str | None:
    """Return the Chat run that continues `run_id`, if one does."""
    runs = launcher.state_dir(root) / "runs"
    for path in sorted(runs.iterdir()) if runs.is_dir() else []:
        try:
            record = autonomy.find_run(root, path.name)
        except autonomy.AutonomyError:
            continue
        if (
            record
            and record["workflow"] == autonomy.CHAT
            and record.get("continues") == run_id
        ):
            return record["run_id"]
    return None


def _head(root: Path) -> str:
    result = autonomy.git(root, "rev-parse", "--verify", "HEAD^{commit}", check=False)
    head = result.stdout.strip()
    if result.returncode != 0 or not head:
        raise Refused(EXIT_REFUSED, "the checkout has no commit to start from")
    return head


def _new_run(  # noqa: PLR0913 - one record, every field explicit
    root: Path,
    *,
    feature: str,
    integration: str,
    review: str,
    continues: str | None = None,
    reason: str | None = None,
    decision_id: str | None = None,
    idea: str | None = None,
    model: str | None = None,
) -> Run:
    match = autonomy.FEATURE.fullmatch(feature)
    if match is None:
        raise Refused(EXIT_REFUSED, f"invalid feature directory {feature}")
    run_id = uuid.uuid4().hex[:8]
    directory = autonomy.run_dir(root, run_id)
    create_files(directory)
    digest = store_manifest(directory, manifest(root))
    record = autonomy.new_run(
        run_id=run_id,
        feature=feature,
        issue=int(match.group(1)),
        workflow=autonomy.CHAT,
        mode="chat",
        integration=integration,
        review_integration=review,
        continues=continues,
        reason=reason,
        start_head=_head(root),
        last_manifest=digest,
        decision_id=decision_id,
    )
    record["idea"] = idea
    record["model"] = model
    autonomy.write_run(root, record)
    return Run(root, record)


def start(root: Path, options: list[str]) -> int:
    """`ballast run start --mode chat`: record, synchronize, summarize; no agent."""
    inputs = _start_inputs(options)
    feature = inputs.get("feature_directory", "")
    if not autonomy.FEATURE.fullmatch(feature):
        raise Refused(
            EXIT_REFUSED, "start needs one -i feature_directory=specs/<issue>-<slug>"
        )
    model = _model(inputs.get("model"))
    active = _active_chat_runs(root)
    if active:
        raise Refused(EXIT_REFUSED, f"another Chat run has an active step: {active[0]}")
    integration, review = _choose_integrations(root, inputs.get("integration", "auto"))
    try:
        autonomy.write_feature_json(root, feature)
    except (autonomy.AutonomyError, OSError) as error:
        raise Refused(
            EXIT_REFUSED, f"cannot point .specify/feature.json at {feature}: {error}"
        ) from error
    run = _new_run(
        root,
        feature=feature,
        integration=integration,
        review=review,
        idea=inputs.get("idea"),
        model=model,
    )
    _out(
        f"Chat run {run.id}: {feature}, authoring {integration}, review by {review}"
        + ("" if review != integration else " (same provider: reduced independence)")
    )
    # Recorded before synchronization: a blocked start still has a ledger
    # run, so its later steps are recorded in a valid ledger.
    _ledger(run, "run", _archive_definition(run), "runner:run")
    outcome = synchronize(run, starting=True)
    if outcome.outcome == "blocked":
        archive(run)
        return EXIT_INTERRUPTED if outcome.interrupted else EXIT_BLOCKED
    run.record["last_manifest"] = current_manifest(run)
    run.save()
    _out(summary(run))
    archive(run)
    checkpoint(run)
    return EXIT_OK


# --- Late close, step close and the step runner -------------------------------------


def _start_entry(run: Run, step: str) -> dict | None:
    for item in run.steps():
        if item.get("entry") == "start" and item.get("step") == step:
            return item
    return None


def _closed(run: Run, step: str) -> bool:
    return any(
        item.get("entry") == "close" and item.get("step") == step
        for item in run.steps()
    )


def late_close(run: Run) -> None:
    """Close a step whose wrapper died, before anything else (R10, F-003, F-004).

    The launcher only lets this invocation run once no `in-progress` marker
    exists, so the step's processes were confirmed stopped by its wrapper or
    by `ballast discard-runs`; its scope is checked again. Every change since
    the step's `tree_before` is attributed to it, with uncertain attribution,
    and no protected-state comparison was possible.
    """
    active = run.record.get("active_step")
    if not active:
        return
    step = active["step"]
    if _closed(run, step):
        run.record["active_step"] = None
        run.save()
        return
    unit = active.get("unit")
    stopped = launcher.stop_scope(unit) if unit else True
    if not stopped:
        # Exclusive: another run's marker also blocks, so keep it as it is.
        with contextlib.suppress(launcher.StepInProgressError):
            launcher.claim_in_progress(launcher.state_dir(run.root), str(unit))
        message = (
            f"the processes of step {step} of run {run.id} could not be confirmed "
            "stopped; run `ballast discard-runs`"
        )
        raise Refused(EXIT_REFUSED, message)
    start_entry = _start_entry(run, step) or {}
    phase = active["phase"]
    kind = start_entry.get("review_kind")
    tree_after = current_manifest(run)
    run.changed()
    post, failures, violations = _postconditions(
        run, phase, kind, step, start_entry.get("tree_before"), tree_after
    )
    _close(
        run,
        step=step,
        phase=phase,
        kind=kind,
        start=start_entry,
        outcome="interrupted",
        exit_code=None,
        scope_stopped=True,
        protected=[],
        violations=violations,
        post=post,
        tree_after=tree_after,
        late=True,
    )
    _out(f"Step {step}: interrupted (closed after its wrapper ended)")
    if failures:
        name, event_id, detail = failures[0]
        _out(f"Failed check: {name} ({event_id}): {_first_line(detail)}")


def _first_line(text: str) -> str:
    return draft_pr.printable((text.strip().splitlines() or [""])[0][:300])


def _safe(text: object) -> str:
    """Return agent-derived text for the operator's terminal: no control bytes."""
    return draft_pr.printable(autonomy.neutralize(str(text)))


def _postconditions(  # noqa: PLR0913, PLR0917 - one close, every input explicit
    run: Run,
    phase: str,
    kind: str | None,
    step: str,
    tree_before: str | None,
    tree_after: str,
) -> tuple[list[str], list[tuple[str, str, str]], list[str]]:
    """Run the phase's postcondition, then its write-scope check; record each.

    Returns (E-ids, failures as (check, E-id, detail), write-scope violations).
    """
    ids: list[str] = []
    failures: list[tuple[str, str, str]] = []
    before = read_manifest(run.dir, tree_before)
    after = read_manifest(run.dir, tree_after)
    paths = changed_paths(before, after)
    for name in PHASES[phase]["post"]:
        if name == "review-report":
            passed, detail = _review_report(run, str(kind), before, after)
            event = run.event(
                "check",
                check="review-report",
                purpose="postcondition",
                passed=passed,
                detail=detail[:DETAIL_LIMIT],
                digests=artifact_digests(run),
                tree=tree_after,
                step=step,
            )
            event_id = event["id"]
        else:
            passed, detail = _check(run, name)
            event_id = run.event(
                "check",
                check=name,
                purpose="postcondition",
                passed=passed,
                detail=detail[:DETAIL_LIMIT],
                digests=artifact_digests(run),
                tree=tree_after,
                step=step,
            )["id"]
        ids.append(event_id)
        if not passed:
            failures.append((name, event_id, detail))
    violations = [path for path in paths if not _in_scope(run, phase, path)]
    detail = (
        "every change is inside the write scope"
        if not violations
        else "changed outside the write scope: " + ", ".join(violations[:50])
    )
    event = run.event(
        "check",
        check="write-scope",
        purpose="postcondition",
        passed=not violations,
        detail=detail[:DETAIL_LIMIT],
        digests=artifact_digests(run),
        tree=tree_after,
        step=step,
        **_bounded(violations),
    )
    ids.append(event["id"])
    if violations:
        failures.append(("write-scope", event["id"], detail))
    return ids, failures, violations


def _in_scope(run: Run, phase: str, path: str) -> bool:
    scope = PHASES[phase]["scope"]
    if scope == "feature":
        return path.startswith(f"{run.feature_dir}/")
    if scope == "reviews":
        return path.startswith(f"{run.feature_dir}/reviews/")
    return not autonomy._protected_path(path)  # noqa: SLF001 - the shared rule


def _review_report(
    run: Run, kind: str, before: dict[str, str], after: dict[str, str]
) -> tuple[bool, str]:
    report = f"{run.feature_dir}/{REVIEW_KINDS[kind]['report']}"
    path = run.root / report
    if path.is_symlink() or not path.is_file():
        return False, f"{report} is missing"
    if before.get(report) == after.get(report):
        return False, f"{report} did not change in this step"
    verdicts = VERDICT_LINE.findall(path.read_text(encoding="utf-8", errors="replace"))
    allowed = REVIEW_KINDS[kind]["verdicts"]
    if not verdicts or verdicts[-1] not in allowed:
        latest = verdicts[-1] if verdicts else "none"
        return (
            False,
            (
                f"{report} latest verdict is {latest}; "
                f"expected one of {', '.join(allowed)}"
            ),
        )
    return True, f"verdict {verdicts[-1]}"


def _close(  # noqa: PLR0913 - one close entry, every field explicit
    run: Run,
    *,
    step: str,
    phase: str,
    kind: str | None,
    start: dict,
    outcome: str,
    exit_code: int | None,
    scope_stopped: bool,
    protected: list[str],
    violations: list[str],
    post: list[str],
    tree_after: str,
    late: bool = False,
    protected_compared: bool = True,
    block: str | None = None,
) -> None:
    """Write the close entry, clear the active step, then the ledger events."""
    run.step_entry(
        {
            **({"block": block} if block else {}),
            "step": step,
            "entry": "close",
            "phase": phase,
            "review_kind": kind,
            "ended_at": _now(),
            "outcome": outcome,
            "exit_code": exit_code,
            "scope_stopped": scope_stopped,
            "protected_changes": protected,
            "write_scope_violations": violations[:PATH_LIMIT],
            "postcondition": post,
            "tree_after": tree_after,
            "log": f".specify/workflow-state/{run.id}/agents/{step}/",
            "late_close": late,
            "attribution": "uncertain" if late else "step",
            "protected_compared": protected_compared and not late,
        }
    )
    run.record["active_step"] = None
    run.record["last_manifest"] = tree_after
    run.save()
    review = None
    if phase == "review" and outcome == "completed":
        review = _review_event(run, str(kind), step, start)
    step_id = (
        REVIEW_KINDS[str(kind)]["step_id"]
        if phase == "review"
        else PHASES[phase]["step_id"]
    )
    line = int(start.get("log_line") or _log_line(run))
    ok = outcome == "completed"
    data: dict[str, Any] = {
        "action": "completed" if ok else "failed",
        "step_id": step_id,
        "status": "completed" if ok else "failed",
        "log_line": line,
    }
    if exit_code is not None:
        data["exit_code"] = abs(exit_code)
    _ledger(run, "step", data)
    _ledger_snapshot(run)
    if review is not None:
        _ledger_review(run, review, start)
    _reactivate(run)


def _review_event(run: Run, kind: str, step: str, start: dict) -> dict:
    report = f"{run.feature_dir}/{REVIEW_KINDS[kind]['report']}"
    text = (run.root / report).read_text(encoding="utf-8", errors="replace")
    verdict = VERDICT_LINE.findall(text)[-1]
    authors = {
        item.get("integration")
        for item in run.steps()
        if item.get("entry") == "start" and item.get("role") == "author"
    } | {run.record["integration"]}
    return run.event(
        "review",
        review_kind=kind,
        step=step,
        reviewer={
            "provider": start.get("integration"),
            "model": start.get("model", "unreported"),
            "role": "reviewer",
        },
        cross_provider=start.get("integration") not in authors,
        report=report,
        report_digest=_sha((run.root / report).read_bytes()),
        verdict=verdict,
    )


def _ledger_review(run: Run, review: dict, start: dict) -> None:
    kind = review["review_kind"]
    data: dict[str, Any] = {
        "review_id": f"chat-{review['id']}",
        "kind": {"spec-reconciliation": "spec-reconciliation"}.get(kind, kind),
        "verdict": LEDGER_VERDICTS[review["verdict"]],
        "reviewer_provider": review["reviewer"]["provider"],
        # The ledger compares the two providers: pick the author provider that
        # makes it agree with the run record's cross_provider (#66 ENG-008).
        "author_provider": run.record["integration"]
        if review["cross_provider"]
        else review["reviewer"]["provider"],
    }
    model = start.get("model")
    if isinstance(model, str) and ledger.MODEL.fullmatch(model):
        data["reviewer_model"] = model
    _ledger(run, "review", data)


def _prompt(run: Run, phase: str, kind: str | None, integration: str) -> str:
    sigil = "/" if integration == "claude" else "$"
    feature = run.feature_dir
    if phase == "review":
        spec = REVIEW_KINDS[str(kind)]
        return (
            f"{sigil}{spec['skill']} Review {feature} ({kind} review) in a fresh "
            f"context. Write the report to {feature}/{spec['report']} and end it with "
            f"one line `- Verdict: {'|'.join(spec['verdicts'])}`."
        )
    command = PHASES[phase]["command"]
    if phase == "specify":
        idea = run.record.get("idea") or f"Issue #{run.issue}"
        return (
            f"{sigil}{command} {idea}. Set SPECIFY_FEATURE_DIRECTORY={feature} before "
            "creating spec.md; keep this path for the feature's later artifacts."
        )
    return f"{sigil}{command} {feature}"


def _step_inputs(options: list[str]) -> dict[str, str]:
    if len(options) % 2:
        raise Refused(EXIT_REFUSED, "step accepts only -i integration=... -i model=...")
    inputs: dict[str, str] = {}
    for flag, pair in zip(options[::2], options[1::2], strict=True):
        name, equals, value = pair.partition("=")
        if (
            flag not in {"-i", "--input"}
            or not equals
            or name not in {"integration", "model"}
        ):
            raise Refused(
                EXIT_REFUSED, "step accepts only -i integration=... -i model=..."
            )
        if name in inputs:
            raise Refused(EXIT_REFUSED, f"input {name} given twice")
        inputs[name] = value
    return inputs


def _refuse(
    run: Run, command: str, reason: str, code: int, **fields: object
) -> Refused:
    """Record a refusal for a run that exists, and return the exception to raise."""
    run.event("refusal", command=command, reason=reason[:DETAIL_LIMIT], **fields)
    return Refused(code, reason)


def run_step(  # noqa: C901, PLR0912, PLR0915 - the lifecycle, in order
    root: Path, run_id: str, phase: str, kind: str | None, options: list[str]
) -> int:
    """`ballast run step RUN PHASE`: the step-runner lifecycle (contracts)."""
    if phase not in PHASES:
        raise Refused(
            EXIT_REFUSED, f"unknown phase {phase!r}; phases: {', '.join(PHASES)}"
        )
    if phase == "review" and kind not in REVIEW_KINDS:
        raise Refused(EXIT_REFUSED, f"review needs --kind {'|'.join(REVIEW_KINDS)}")
    if phase != "review" and kind is not None:
        raise Refused(EXIT_REFUSED, "--kind applies only to the review phase")
    inputs = _step_inputs(options)
    run = load(root, run_id)
    with Lock(run, f"step {phase}") as lock:
        late_close(run)
        out_of_step(run)
        if run.record["status"] == "published":
            raise _refuse(
                run, "step", f"run {run.id} is published", EXIT_REFUSED, phase=phase
            )
        interactive = run.mode == "chat"
        if interactive and not (sys.stdin.isatty() and sys.stdout.isatty()):
            raise _refuse(run, "step", NO_TERMINAL, EXIT_REFUSED, phase=phase)
        rerun = f"ballast run step {run.id} {phase}" + (
            f" --kind {kind}" if kind else ""
        )
        outcome = synchronize(run, rerun=rerun, **_inherited_pin(run))
        if outcome.outcome == "blocked":
            raise _refuse(
                run,
                "step",
                f"branch synchronization blocked ({outcome.cause})",
                EXIT_INTERRUPTED if outcome.interrupted else EXIT_BLOCKED,
                phase=phase,
            )
        out_of_step(run, actor="sync")
        run.changed()
        passed, failing, event_id, detail = entry(run, phase, kind)
        if not passed:
            raise _refuse(
                run,
                "step",
                f"{phase} is not allowed yet: {failing} failed ({event_id}): "
                f"{_first_line(str(detail))}",
                EXIT_BLOCKED,
                phase=phase,
                failed_check=event_id,
            )
        role = "reviewer" if phase == "review" else "author"
        integration = (
            run.record["review_integration"]
            if phase == "review"
            else inputs.get("integration", run.record["integration"])
        )
        if integration not in autonomy.INTEGRATIONS:
            raise _refuse(
                run,
                "step",
                "integration must be claude or codex",
                EXIT_REFUSED,
                phase=phase,
            )
        model = _model(inputs.get("model")) or run.record.get("model")
        prompt = _prompt(run, phase, kind, integration)
        if any(
            marker in token
            for token in (prompt, model or "")
            for marker in agent.FORBIDDEN
        ):
            raise _refuse(
                run,
                "step",
                "refusing a permission bypass marker in the step's input",
                EXIT_REFUSED,
                phase=phase,
            )
        if interactive:
            reason = (
                None
                if shutil.which(integration)
                else f"{integration} CLI not found on PATH"
            )
            reason = reason or _confinable(root, integration)
            if reason is not None:
                refusal = _integration_refusal(root, integration, reason)
                raise _refuse(run, "step", str(refusal), EXIT_REFUSED, phase=phase)
        with contextlib.suppress(autonomy.AutonomyError, OSError):
            autonomy.write_feature_json(root, run.feature_dir)
        name = f"{_stamp()}-{phase}-{integration}"
        unit = f"ballast-agent-{run.id}-{name}.scope"
        if not launcher.SCOPE.fullmatch(unit):
            raise Refused(EXIT_REFUSED, f"invalid agent scope name {unit!r}")
        log_dir = root / ".specify/workflow-state" / run.id / "agents" / name
        log_dir.mkdir(parents=True, exist_ok=True)
        settings = (
            f".specify/workflow-state/{run.id}/agents/{name}/claude-settings.json"
        )
        if interactive:
            try:
                launcher.claim_in_progress(launcher.state_dir(root), unit)
            except launcher.StepInProgressError as error:
                raise _refuse(
                    run, "step", str(error), EXIT_REFUSED, phase=phase
                ) from None
        try:
            if interactive and integration == "claude":
                # Before the protected snapshot: the agent sees it read-only.
                _write_settings(log_dir)
            tree_before = current_manifest(run)
            run.record["last_manifest"] = tree_before
            protected = agent._protected_state(root, log_dir)  # noqa: SLF001
            started_at = _now()
            run.record["active_step"] = {
                "step": name,
                "phase": phase,
                "unit": unit if interactive else None,
                "started_at": started_at,
            }
            run.save()
            line = _log_line(run)
            start_entry = {
                "step": name,
                "entry": "start",
                "phase": phase,
                "review_kind": kind,
                "driver": "interactive" if interactive else "headless",
                "integration": integration,
                "model": model or "unreported",
                "role": role,
                "tree_before": tree_before,
                "started_at": started_at,
                "log_line": line,
            }
            run.step_entry(start_entry)
            step_id = (
                REVIEW_KINDS[str(kind)]["step_id"]
                if phase == "review"
                else PHASES[phase]["step_id"]
            )
            _ledger(
                run,
                "step",
                {
                    "action": "started",
                    "step_id": step_id,
                    "step_type": "command",
                    "log_line": line,
                },
            )
            lock.describe(f"step {name}")
        except BaseException:
            # The agent has not started: nothing is left to be unsure about.
            if interactive:
                marker = launcher.state_dir(root) / launcher.IN_PROGRESS
                marker.unlink(missing_ok=True)
            raise
        if interactive:
            result = _interactive(
                run,
                name,
                unit,
                integration,
                prompt,
                model,
                phase,
                role,
                log_dir,
                started_at,
                settings,
            )
        else:
            result = _headless(run, integration, prompt, name)
        # Steps 9 to 12 run to the end: a second signal is ignored.
        numbers = (signal.SIGHUP, signal.SIGTERM, signal.SIGINT)
        previous = {number: signal.signal(number, signal.SIG_IGN) for number in numbers}
        try:
            return _finish(
                run, name, phase, kind, start_entry, result, protected, log_dir
            )
        finally:
            for number, handler in previous.items():
                signal.signal(number, handler)


def _interactive(  # noqa: PLR0913, PLR0917 - one session, every input explicit
    run: Run,
    name: str,  # noqa: ARG001 - kept for the call-site signature
    unit: str,
    integration: str,
    prompt: str,
    model: str | None,
    phase: str,
    role: str,
    log_dir: Path,
    started_at: str,
    settings: str,
) -> dict:
    """Run the interactive session behind a wrapper-owned pty (agent.py)."""
    log_fd = os.open(log_dir, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        stdout_log = agent._open_log(log_fd, "stdout.log")  # noqa: SLF001
        meta_file = agent._open_log(log_fd, "meta.json")  # noqa: SLF001
    finally:
        os.close(log_fd)
    result: dict[str, Any] = {
        "exit_code": None,
        "interrupted": True,
        "scope_stopped": False,
        "stopped_descendants": 0,
        "argv": [],
        "error": None,
    }
    try:
        with stdout_log:
            result |= agent.run_interactive(
                run.root,
                integration=integration,
                prompt=prompt,
                model=model,
                feature=run.feature_dir,
                unit=unit,
                stdout_log=stdout_log,
                settings=settings,
            )
    except (OSError, ValueError, agent.LaunchError, autonomy.AutonomyError) as error:
        result["error"] = str(error)
        # A launch failure started no agent: the step failed, it was not
        # interrupted (#66 ENG-013).
        result["launch_failed"] = isinstance(error, agent.LaunchError)
        result["scope_stopped"] = launcher.stop_scope(unit)
        _err(f"ballast: the interactive step could not run: {error}")
    result["meta"] = {
        "run_id": run.id,
        "feature_directory": run.feature_dir,
        "integration": integration,
        "model": model or "unreported",
        "role": role,
        "phase": phase,
        "driver": "interactive",
        "argv": result["argv"],
        "started_at": started_at,
    }
    result["meta_file"] = meta_file
    return result


def _write_settings(log_dir: Path) -> None:
    """Return the step's Claude settings: every installed headless rule, plus Chat's."""
    log_fd = os.open(log_dir, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        with agent._open_log(log_fd, "claude-settings.json") as handle:  # noqa: SLF001
            handle.write((json.dumps(agent.chat_settings(), indent=2) + "\n").encode())
    finally:
        os.close(log_fd)


def _headless(run: Run, integration: str, prompt: str, name: str) -> dict:
    """Run the phase headless through agent.py (human-gated mode).

    agent.py writes its logs to the step's own directory, `name`.
    """
    program = HERE / "bin" / integration
    args = ["-p", prompt] if integration == "claude" else ["exec", prompt]
    env = {
        **{k: v for k, v in os.environ.items() if k not in draft_pr.TOKEN_VARIABLES},
        "BALLAST_SPEC_WORKFLOW": "1",
        "SPECKIT_WORKFLOW_RUN_ID": run.id,
        "BALLAST_STEP_LOG": name,
    }
    interrupted = False

    def interrupt(*_: object) -> None:
        raise KeyboardInterrupt

    previous = {
        number: signal.signal(number, interrupt)
        for number in (signal.SIGHUP, signal.SIGTERM)
    }
    process = subprocess.Popen([str(program), *args], cwd=run.root, env=env)  # noqa: S603
    try:
        code = process.wait()
    except KeyboardInterrupt:
        interrupted = True
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        try:
            code = process.wait(agent.INTERRUPT_GRACE_SECONDS * 4)
        except subprocess.TimeoutExpired:
            process.kill()
            code = process.wait()
    finally:
        for number, handler in previous.items():
            signal.signal(number, handler)
    if code == agent.EXIT_INTERRUPTED:
        interrupted = True
    marker = launcher.state_dir(run.root) / launcher.IN_PROGRESS
    return {
        "exit_code": None if interrupted else code,
        "interrupted": interrupted,
        "scope_stopped": not marker.exists(),
        "stopped_descendants": 0,
        "argv": [integration, *args[:1]],
        "error": None,
        "headless_code": code,
    }


def _finish(  # noqa: C901, PLR0912, PLR0913, PLR0915, PLR0917 - steps 9 to 12, in order
    run: Run,
    name: str,
    phase: str,
    kind: str | None,
    start: dict,
    result: dict,
    protected: dict[str, str],
    log_dir: Path,
) -> int:
    """Close a step: scope, protected inputs, postconditions, records."""
    root = run.root
    interactive = start["driver"] == "interactive"
    marker = launcher.state_dir(root) / launcher.IN_PROGRESS
    meta = result.get("meta") or {}
    meta_file = result.get("meta_file")

    def write_meta(**fields: object) -> None:
        if meta_file is None:
            return
        with meta_file:
            meta_file.write(
                (
                    json.dumps({**meta, "finished_at": _now(), **fields}, indent=2)
                    + "\n"
                ).encode()
            )

    if not result["scope_stopped"]:  # SEC-007: headless too
        run.record["active_step"] = {
            **run.record["active_step"],
            "scope_stopped": False,
        }
        run.save()
        write_meta(
            exit_code=result["exit_code"],
            protected_changes=[],
            stopped_descendants=result["stopped_descendants"],
            scope_stopped=False,
        )
        _out(f"Step {name}: interrupted")
        _err(
            "ballast: the step's agent processes could not be confirmed stopped; "
            "its changes were not checked. The launcher refuses every command until "
            "`ballast discard-runs` confirms them stopped."
        )
        return EXIT_TAMPERED
    tampered: list[str] = []
    if interactive:
        after = agent._protected_after(root, log_dir)  # noqa: SLF001
        tampered = sorted(
            path
            for path in protected.keys() | after.keys()
            if protected.get(path) != after.get(path)
        )
    elif result.get("headless_code") == agent.EXIT_TAMPERED:
        tampered = ["(see the agent wrapper's protected-file report)"]
    tree_after = current_manifest(run)
    run.changed()
    if tampered:
        if interactive:
            agent._mark_tampered(root, tampered)  # noqa: SLF001
        write_meta(
            exit_code=result["exit_code"],
            protected_changes=tampered,
            stopped_descendants=result["stopped_descendants"],
            scope_stopped=True,
        )
        _close(
            run,
            step=name,
            phase=phase,
            kind=kind,
            start=start,
            outcome="tampered",
            exit_code=result["exit_code"],
            scope_stopped=True,
            protected=tampered,
            violations=[],
            post=[],
            tree_after=tree_after,
        )
        _out(f"Step {name}: tampered")
        _err(
            "ballast: the step changed protected workflow files: "
            f"{', '.join(tampered[:10])}. Restore them, recreate .venv, and delete "
            f"{launcher.TAMPER_MARKER} before any other workflow command."
        )
        archive(run)
        return EXIT_TAMPERED
    if interactive:
        marker.unlink(missing_ok=True)
    post, failures, violations = _postconditions(
        run, phase, kind, name, start["tree_before"], tree_after
    )
    credential = result.get("headless_code") == agent.EXIT_AUTH
    if result.get("launch_failed"):
        outcome = "failed"
    elif result["interrupted"]:
        outcome = "interrupted"
    elif failures or result["exit_code"] != 0:
        outcome = "failed"
    else:
        outcome = "completed"
    write_meta(
        exit_code=result["exit_code"],
        protected_changes=[],
        stopped_descendants=result["stopped_descendants"],
        scope_stopped=True,
    )
    _close(
        run,
        step=name,
        phase=phase,
        kind=kind,
        start=start,
        outcome=outcome,
        exit_code=result["exit_code"],
        scope_stopped=True,
        protected=[],
        violations=violations,
        post=post,
        tree_after=tree_after,
        # The wrapper's own classification, never agent text (#65 SEC-003).
        block="credential" if credential else None,
    )
    archive(run)
    checkpoint(run)
    _out(f"Step {name}: {outcome}")
    if credential:  # the cause of any failed check, so it comes first
        _out(f"Blocked (credential): {agent.AUTH_REASONS[result['argv'][0]]}.")
    elif result.get("launch_failed"):  # likewise the cause of any failed check
        _out(f"The agent did not start: {_first_line(str(result['error']))}")
    elif failures:
        check, event_id, detail = failures[0]
        _out(f"Failed check: {check} ({event_id}): {_first_line(detail)}")
    elif outcome == "failed":
        _out(f"The agent exited with status {result['exit_code']}.")
    _out("Next:")
    for action in allowed_actions(run):
        _out(f"  {action}")
    return {
        "completed": EXIT_OK,
        "failed": EXIT_BLOCKED,
        "interrupted": EXIT_INTERRUPTED,
    }[outcome]


# --- status and the handoff summary --------------------------------------------------


def _mode_history(record: dict) -> str:
    parts = []
    for change in record["mode_history"]:
        extra = f" ({change['decision_id']})" if change.get("decision_id") else ""
        reason = f": {_safe(change['reason'])}" if change.get("reason") else ""
        parts.append(
            f"{change['action']} {change['mode']} at {change['at']} "
            f"by {change['by']}{extra}{reason}"
        )
    return "; ".join(parts)


def _source_decisions(run: Run) -> list[dict]:
    """Provisional decisions of a continued Autonomous source, if any."""
    source = run.record.get("continues")
    if not source:
        return []
    try:
        record = autonomy.find_run(run.root, source)
        decisions = (
            autonomy.read_decisions(run.root, source)
            if record is not None and record["workflow"] == "ballast-autonomous"
            else []
        )
    except autonomy.AutonomyError:
        decisions = []
    return decisions


def superseding(run: Run, humans: list[dict]) -> dict[str, str]:  # noqa: ARG001 - kept for the call-site signature
    """{PD id: the HD that superseded it} for a continued Autonomous source."""
    found = {}
    for entry in humans:
        if entry["kind"] == "gate-approval":
            for pd in entry.get("supersedes_provisional", []):
                found.setdefault(pd, entry["id"])
    return found


def summary(run: Run) -> str:  # noqa: C901, PLR0912, PLR0915 - seven fixed sections
    """Return the handoff summary, built from the operator record only (FR-019)."""
    record = run.record
    humans = run.humans()
    events = run.events()
    steps = run.steps()
    pin = branch_sync.read_pin(run.root, run.id)
    lines = [
        f"Chat run {run.id} ({record['status']})",
        f"Mode: {run.mode}; history: {_mode_history(record)}",
        f"Issue #{run.issue}{SEP}feature {run.feature_dir}{SEP}branch "
        f"{draft_pr.printable(pin.get('branch', 'not pinned'))}{SEP}run {run.id}"
        + (f"{SEP}continues {record['continues']}" if record.get("continues") else ""),
        "",
        "Completed steps:",
    ]
    starts = {item["step"]: item for item in steps if item.get("entry") == "start"}
    closes = [item for item in steps if item.get("entry") == "close"]
    for close in closes:
        begin = starts.get(close["step"], {})
        phase = close["phase"] + (
            f" ({close['review_kind']})" if close.get("review_kind") else ""
        )
        lines.append(
            f"  - {phase}: {begin.get('integration')}/"
            f"{begin.get('model', 'unreported')} "
            f"({begin.get('role')}), {begin.get('started_at')} "
            f"to {close['ended_at']}: "
            f"{close['outcome']}"
            + (" (closed late)" if close.get("late_close") else "")
        )
    if not closes:
        lines.append("  none")
    lines += ["", "Failed checks:"]
    latest: dict[str, dict] = {}
    for event in events:
        if (
            event["kind"] == "check"
            and not event["check"].endswith("-approval")
            and event["check"] not in RECORD_CHECKS
        ):
            latest[event["check"]] = event
    failed = [event for event in latest.values() if not event["passed"]]
    lines += [
        f"  - {event['check']} ({event['id']}): {_first_line(event['detail'])}"
        for event in failed
    ] or ["  none"]
    lines += ["", "Gates:"]
    for gate in GATES:
        state, decision = approval_state(run, gate, humans)
        if state == "current":
            text = "approved, current" + (
                f" ({decision['id']})" if decision else " (registered intent block)"
            )
        elif state == "stale":
            change = next(
                (
                    event["id"]
                    for event in reversed(events)
                    if event["kind"] == "out-of-step-change"
                    and decision
                    and decision["id"] in event.get("stale", [])
                ),
                None,
            )
            text = f"approved, stale ({decision['id'] if decision else 'none'}" + (
                f"; made stale by {change})"
                if change
                else "; the artifact changed since)"
            )
        elif state == "rejected":
            text = f"rejected ({decision['id']}: {_safe(decision['ref'])})"
        else:
            text = "pending"
        lines.append(f"  - {gate}: {text}")
    lines += ["", "Open decisions:"]
    open_lines = []
    path = run.file("decisions.md")
    if path.is_file() and not path.is_symlink():
        text = path.read_text(encoding="utf-8", errors="replace")
        proposals = [
            dec
            for dec, kind, _ in artifacts.decision_sections(text)
            if kind.lower() == "proposal"
        ]
        resolved = artifacts.human_resolutions(run.feature(), text)
        open_lines += [
            f"  - {dec}: proposal without a current human resolution"
            for dec in dict.fromkeys(proposals)
            if dec not in resolved
        ]
    replaced = superseding(run, humans)
    for decision in autonomy.current_decisions(_source_decisions(run)):
        state = (
            f"superseded by {replaced[decision['id']]}"
            if decision["id"] in replaced
            else "not yet superseded"
        )
        open_lines.append(
            f"  - {decision['id']} ({decision['point']}, agent-provisional, {state}): "
            f"{_safe(decision['summary'])}"
        )
    lines += open_lines or ["  none"]
    lines += ["", "Changes made outside agent steps since the last step:"]
    last_close = None
    if closes:
        last_close = closes[-1]["step"]
    since = 0
    for index, event in enumerate(events):
        if last_close and event.get("step") == last_close:
            since = index + 1
    changes = [
        event for event in events[since:] if event["kind"] == "out-of-step-change"
    ]
    lines += [
        f"  - {event['id']}: {len(event['paths']) + event.get('more', 0)} path(s): "
        + ", ".join(draft_pr.printable(p) for p in event["paths"][:10])
        + (" ..." if len(event["paths"]) > 10 or event.get("more") else "")  # noqa: PLR2004 - preview cap
        for event in changes
    ] or ["  none"]
    lines += ["", "Allowed next actions:"]
    lines += [f"  - {action}" for action in allowed_actions(run)]
    lines.append("  - stop: the run waits, unchanged, for your next command")
    return "\n".join(lines)


def status(root: Path, run_id: str) -> int:
    """`ballast run status RUN`: the handoff summary; no agent, no sync."""
    if not autonomy.RUN_ID.fullmatch(run_id or ""):
        raise Refused(EXIT_REFUSED, "a valid RUN_ID is required")
    try:
        record = autonomy.find_run(root, run_id)
    except autonomy.AutonomyError as error:
        raise Refused(EXIT_REFUSED, f"run {run_id}: {error}") from error
    if record is not None and record["workflow"] == "ballast-autonomous":
        _out(_autonomous_status(root, record))
        return EXIT_OK
    run = load(root, run_id)
    with Lock(run, "status"):
        late_close(run)
        out_of_step(run)
        _out(summary(run))
    return EXIT_OK


def _autonomous_status(root: Path, record: dict) -> str:
    try:
        block = autonomy.read_block(root, record["run_id"])
    except autonomy.AutonomyError:
        block = None
    lines = [
        (
            f"Autonomous run {record['run_id']} ({record['status']}) "
            f"for #{record['issue']} "
            f"({record['feature']})"
        ),
        f"Mode: {autonomy.effective_mode(record)}; history: {_mode_history(record)}",
    ]
    if block:
        lines.append(f"Block ({block['category']}): {_safe(block['condition'])}")
    lines += [
        (
            "Provisional decisions: "
            f"{len(autonomy.read_decisions(root, record['run_id']))}, "
            "all agent-provisional"
        ),
        (
            "To continue it in Chat: ballast run continue "
            f"{record['run_id']} --reason block-resolved|changes-requested "
            "--ref TEXT --mode chat"
        ),
    ]
    return "\n".join(lines)


# --- Human decisions: approve, reject, resolve ---------------------------------------


def _terminal(command: str) -> None:
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        message = (
            f"{command} needs a terminal for its typed confirmation; "
            "nothing was recorded"
        )
        raise Refused(EXIT_REFUSED, message)


def _confirm(expected: str) -> bool:
    _out(f"Type `{expected}` to confirm, anything else to cancel:")
    try:
        typed = sys.stdin.readline()
    except (OSError, KeyboardInterrupt):
        return False
    return typed.strip() == expected


def _require_no_step(run: Run, command: str) -> None:
    active = run.record.get("active_step")
    if active:
        raise _refuse(
            run,
            command,
            f"run {run.id} has an active step: {active['step']}",
            EXIT_REFUSED,
        )


def _gate_decision(  # noqa: C901, PLR0912 - complexity inherent to one guarded flow
    root: Path, run_id: str, gate: str, choice: str, reason: str | None
) -> int:
    command = "approve" if choice == "approve" else "reject"
    if gate not in GATES:
        raise Refused(EXIT_REFUSED, f"unknown gate {gate!r}; gates: {', '.join(GATES)}")
    if choice == "reject" and not (reason and reason.strip()):
        raise Refused(EXIT_REFUSED, "reject needs --reason TEXT")
    _terminal(command)
    run = load(root, run_id)
    with Lock(run, f"{command} {gate}"):
        late_close(run)
        out_of_step(run)
        _require_no_step(run, command)
        passed, failing, _, detail = gate_precondition(run, gate, record=False)
        if not passed:
            _, _, event_id, _ = _requirement_event(run, failing, detail, gate)
            raise _refuse(
                run,
                command,
                f"the {gate} gate's precondition fails: {failing} ({event_id}): "
                f"{_first_line(str(detail))}",
                EXIT_BLOCKED,
                gate=gate,
                failed_check=event_id,
            )
        digest = gate_digest(run, gate)
        if digest is None:
            raise _refuse(
                run,
                command,
                f"{gate_artifact(run, gate)} is missing",
                EXIT_BLOCKED,
                gate=gate,
            )
        humans = run.humans()
        point = GATES[gate]["point"]
        replaced = superseding(run, humans)
        supersedes = (
            [
                entry["id"]
                for entry in autonomy.current(_source_decisions(run), point)
                if entry["id"] not in replaced
            ]
            if choice == "approve"
            else []
        )
        _out(f"Gate: {gate}")
        _out(f"Artifact: {gate_artifact(run, gate)}")
        _out(f"Digest: {digest}")
        if supersedes:
            _out(
                f"Supersedes agent-provisional decisions: {', '.join(supersedes)} "
                "(they stay labeled agent-provisional)"
            )
        if not _confirm(f"{command} {gate}"):
            _out(
                f"Not {'approved' if choice == 'approve' else 'rejected'}; "
                "nothing was recorded."
            )
            return EXIT_REFUSED
        run.changed()
        if gate_digest(run, gate) != digest:
            raise _refuse(
                run,
                command,
                f"{gate_artifact(run, gate)} changed while you confirmed",
                EXIT_REFUSED,
                gate=gate,
            )
        for item in GATES[gate]["pre"]:
            _requirement(run, item, "gate", humans, record=True)
        if choice == "approve" and gate == "intent":
            artifacts.record_intent(run.feature())
            run.changed()
        if choice == "approve":
            decision = run.human(
                "gate-approval",
                f"approve {gate}",
                gate=gate,
                artifact=gate_artifact(run, gate),
                digest=digest,
                supersedes_provisional=supersedes,
            )
        else:
            decision = run.human(
                "gate-rejection",
                str(reason),
                gate=gate,
                artifact=gate_artifact(run, gate),
                digest=digest,
            )
        if choice == "approve" and gate == "tasks":
            run.record["baseline"] = {
                "tree": artifacts.worktree_tree(root),
                "at": _now(),
                "approval": decision["id"],
            }
        if choice == "approve" and gate == "final" and run.record["status"] == "active":
            autonomy.set_status(run.record, "completed")
        run.record["last_manifest"] = current_manifest(run)
        run.save()
        _ledger_gate(run, gate, choice)
        archive(run)
        verb = "approved" if choice == "approve" else "rejected"
        _out(f"Recorded {decision['id']}: {gate} {verb} at {digest}")
    return EXIT_OK


def _requirement_event(
    run: Run, name: str | None, detail: str | None, gate: str
) -> tuple[bool, str, str, str]:
    event = run.event(
        "check",
        check=str(name),
        purpose="gate",
        passed=False,
        detail=str(detail)[:DETAIL_LIMIT],
        digests=artifact_digests(run),
        tree=run.record.get("last_manifest"),
        step=None,
        gate=gate,
    )
    return False, str(detail), event["id"], str(name)


def approve(root: Path, run_id: str, gate: str) -> int:
    """`ballast run approve RUN GATE`: a human approval bound to a digest."""
    return _gate_decision(root, run_id, gate, "approve", None)


def reject(root: Path, run_id: str, gate: str, reason: str | None) -> int:
    """`ballast run reject RUN GATE --reason TEXT`: a human rejection."""
    return _gate_decision(root, run_id, gate, "reject", reason)


def resolve(root: Path, run_id: str, decision: str) -> int:
    """`ballast run resolve RUN DEC-NNNN`: confirm a human resolution."""
    if not autonomy.DECISION_ID.fullmatch(decision or ""):
        raise Refused(EXIT_REFUSED, "resolve needs a DEC-NNNN decision")
    _terminal("resolve")
    run = load(root, run_id)
    with Lock(run, f"resolve {decision}"):
        late_close(run)
        out_of_step(run)
        _require_no_step(run, "resolve")
        path = run.file("decisions.md")
        text = (
            path.read_text(encoding="utf-8")
            if path.is_file() and not path.is_symlink()
            else ""
        )
        sections = artifacts.decision_sections(text)
        if not any(
            dec == decision and kind.lower() == "proposal" for dec, kind, _ in sections
        ):
            raise _refuse(
                run,
                "resolve",
                f"decisions.md has no {decision} — Proposal",
                EXIT_REFUSED,
            )
        body = artifacts.latest_resolutions(text).get(decision)
        if body is None:
            raise _refuse(
                run,
                "resolve",
                f"decisions.md has no {decision} — Resolution",
                EXIT_REFUSED,
            )
        digest = artifacts.resolution_digest(body)
        _out(f"{decision} — Resolution:")
        # Agent-written: escape control bytes so the screen shows what is bound.
        _out("\n".join(draft_pr.printable(line) for line in body.strip().splitlines()))
        _out(f"Digest: {digest}")
        if not _confirm(f"resolve {decision}"):
            _out("Not resolved; nothing was recorded.")
            return EXIT_REFUSED
        current = artifacts.latest_resolutions(path.read_text(encoding="utf-8")).get(
            decision
        )
        if current is None or artifacts.resolution_digest(current) != digest:
            raise _refuse(
                run,
                "resolve",
                f"the resolution of {decision} changed while you confirmed",
                EXIT_REFUSED,
            )
        entry = run.human(
            "decision-resolution",
            f"resolve {decision}",
            decision=decision,
            digest=digest,
        )
        archive(run)
        _out(f"Recorded {entry['id']}: {decision} resolved at {digest}")
    return EXIT_OK


# --- checks ------------------------------------------------------------------------


def checks(root: Path, run_id: str) -> int:
    """`ballast run checks RUN`: the project's checks, confined; no agent."""
    run = load(root, run_id)
    with Lock(run, "checks"):
        late_close(run)
        out_of_step(run)
        _require_no_step(run, "checks")
        try:
            result = artifacts.project_checks(root, run.feature_dir)
        except autonomy.AutonomyError as error:
            raise _refuse(run, "checks", str(error), EXIT_REFUSED) from error
        event = run.event(
            "project-checks",
            results=result["results"],
            unavailable=result["unavailable"],
            tree=result["tree"],
            protected_changes=result["protected_changes"][:PATH_LIMIT],
        )
        try:
            snapshot = ledger.artifact_digests(root, run.feature_dir)
        except (ledger.LedgerError, OSError, ValueError):
            snapshot = {}
        bound = {key: snapshot[key] for key in ("spec_digest",) if key in snapshot}
        if "tree" in snapshot:
            bound["snapshot"] = snapshot["tree"]
        if result["unavailable"]:
            _ledger(
                run,
                "verification",
                {"check_id": "project-checks", "status": "unavailable", **bound},
            )
            _out(f"No [checks] table: checks unavailable ({event['id']})")
        for index, item in enumerate(result["results"], start=1):
            passed = item["exit"] == 0
            _ledger(
                run,
                "verification",
                {
                    "check_id": f"project-check-{index}",
                    "status": "passed" if passed else "failed",
                    "exit_code": abs(item["exit"]),
                    **bound,
                },
            )
            _out(
                f"Check {draft_pr.printable(item['command'])}: exit {item['exit']} in "
                f"{item['seconds']:.1f}s"
                + (" (timed out)" if item["timed_out"] else "")
            )
        archive(run)
        if result["protected_changes"]:
            _err(
                "ballast: a check command changed protected inputs: "
                + ", ".join(result["protected_changes"][:10])
            )
            return EXIT_TAMPERED
        failed = [item for item in result["results"] if item["exit"] != 0]
        _out(f"Project checks recorded as {event['id']}")
        return EXIT_BLOCKED if failed else EXIT_OK


# --- mode and continue --------------------------------------------------------------


def change_mode(root: Path, run_id: str, target: str, reason: str | None) -> int:
    """`ballast run mode RUN chat|human-gated --reason TEXT` (R12)."""
    if target == "autonomous":
        with contextlib.suppress(Refused, autonomy.AutonomyError, OSError):
            run = load(root, run_id)
            run.event("refusal", command="mode", reason=autonomy.NEVER_RAISED)
        raise Refused(EXIT_REFUSED, autonomy.NEVER_RAISED)
    if target not in {"chat", "human-gated"}:
        raise Refused(EXIT_REFUSED, "mode must be chat or human-gated")
    if not (reason and reason.strip()):
        raise Refused(EXIT_REFUSED, "mode needs --reason TEXT")
    if not autonomy.RUN_ID.fullmatch(run_id or ""):
        raise Refused(EXIT_REFUSED, "a valid RUN_ID is required")
    try:
        record = autonomy.find_run(root, run_id)
    except autonomy.AutonomyError as error:
        raise Refused(EXIT_REFUSED, f"run {run_id}: {error}") from error
    if record is None:
        return _link_engine_run(root, run_id, target, reason)
    if record["workflow"] != autonomy.CHAT:
        message = f"run {run_id} is a {record['workflow']} run; " + (
            f"continue it in Chat with ballast run continue {run_id} --reason "
            "block-resolved|changes-requested --ref TEXT --mode chat"
            if record["workflow"] == "ballast-autonomous"
            else "only a Chat run or a paused ballast-feature run changes mode here"
        )
        raise Refused(EXIT_REFUSED, message)
    run = Run(root, record)
    with Lock(run, f"mode {target}"):
        late_close(run)
        out_of_step(run)
        _require_no_step(run, "mode")
        current = run.mode
        if current == target:
            raise _refuse(
                run, "mode", f"run {run.id} is already in {target} mode", EXIT_REFUSED
            )
        decision = autonomy.append_human_decision(
            root,
            run.id,
            "mode-change",
            reason,
            resolves=None,
            extra={"from": current, "to": target},
        )
        autonomy.change_mode(
            run.record, target, reason=reason, decision_id=decision["id"]
        )
        run.save()
        _ledger(
            run, "run", {"action": "ended", "status": "mode-changed", "mode": target}
        )
        archive(run)
        _out(
            f"Recorded {decision['id']}: run {run.id} switched from {current} "
            f"to {target}."
        )
        if target == "human-gated":
            _out(
                "Steps now run headless through the agent wrapper; "
                "gates still need `ballast run approve`."
            )
    return EXIT_OK


def _engine_state(root: Path, run_id: str) -> dict:
    path = root / ".specify/workflows/runs" / run_id / "state.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _link_engine_run(root: Path, run_id: str, target: str, reason: str) -> int:
    """Continue a paused `ballast-feature` engine run as a linked Chat run."""
    state = _engine_state(root, run_id)
    if state.get("workflow_id") != WORKFLOW_ID:
        raise Refused(
            EXIT_REFUSED, f"run {run_id} is not a Chat run or a ballast-feature run"
        )
    if target != "chat":
        raise Refused(
            EXIT_REFUSED,
            f"run {run_id} is a ballast-feature run; it can only continue in chat",
        )
    if state.get("status") not in {
        "paused",
        "failed",
        "interrupted",
        "cancelled",
        "aborted",
    }:
        raise Refused(
            EXIT_REFUSED,
            f"run {run_id} is {state.get('status')}; "
            "only a paused or stopped run continues in Chat",
        )
    existing = continued_by(root, run_id)
    if existing:
        raise Refused(
            EXIT_REFUSED, f"run {run_id} already continues as Chat run {existing}"
        )
    pin = branch_sync.read_pin(root, run_id)
    if "branch" not in pin or "feature" not in pin:
        raise Refused(
            EXIT_REFUSED, f"run {run_id} has no branch pin; start a Chat run instead"
        )
    feature = pin["feature"]
    integrations = [name for name in autonomy.INTEGRATIONS if shutil.which(name)]
    if not integrations:
        raise Refused(EXIT_REFUSED, "no agent CLI (claude or codex) found on PATH")
    integration, review = _choose_integrations(root, "auto")
    run = _new_run(
        root,
        feature=feature,
        integration=integration,
        review=review,
        continues=run_id,
        reason=reason,
    )
    decision = run.human("mode-change", reason, **{"from": "human-gated", "to": "chat"})
    run.record["mode_history"][0]["decision_id"] = decision["id"]
    run.save()
    branch_sync._write_json(  # noqa: SLF001 - the continuation inherits the pin
        branch_sync._pin_path(root, run.id),  # noqa: SLF001
        {
            key: value
            for key, value in pin.items()
            if key in {"branch", "base", "base_commit", "feature"}
        },
    )
    data = _archive_definition(run)
    _ledger(run, "run", data, "runner:run")
    _ledger(run, "run", {"action": "ended", "status": "mode-changed", "mode": "chat"})
    _out(
        f"Recorded {decision['id']}: ballast-feature run {run_id} continues as "
        f"Chat run {run.id}. Its engine state is untouched; "
        "plan and tasks approvals are asked again."
    )
    _out(summary(run))
    archive(run)
    return EXIT_OK


def continue_run(root: Path, source: dict, decision: dict) -> int:
    """Run steps 4 to 6 of `continue --mode chat`: the linked Chat run (AC-022).

    `run.py` has already recorded the human decision, lowered the source to
    chat, set it to `continued` and re-rendered its committed record.
    """
    run = _new_run(
        root,
        feature=source["feature"],
        integration=source["integration"],
        review=source["review_integration"],
        continues=source["run_id"],
        reason=decision["kind"],
        decision_id=decision["id"],
    )
    _ledger(run, "run", _archive_definition(run), "runner:run")
    outcome = synchronize(run, **_inherited_pin(run))
    _out(
        f"Recorded {decision['id']} ({decision['kind']}); "
        f"run {source['run_id']} is lowered "
        f"to chat and continues as Chat run {run.id}. "
        "Every gate asks for your approval; "
        "its provisional decisions stay agent-provisional."
    )
    if outcome.outcome == "blocked":
        archive(run)
        return EXIT_INTERRUPTED if outcome.interrupted else EXIT_BLOCKED
    run.record["last_manifest"] = current_manifest(run)
    run.save()
    _out(summary(run))
    archive(run)
    return EXIT_OK


# --- publish -------------------------------------------------------------------------


CHAT_BEGIN = autonomy.CHAT_BEGIN
CHAT_END = autonomy.CHAT_END
LOGS_LOCAL = (
    "Conversation logs and agent logs stay on the operator's machine and are not "
    "part of this PR."
)


def _agent_value(value: object) -> str:
    """Return an agent-derived value for the PR: neutralized, no approval claim."""
    text = autonomy.neutralize(str(value))
    if autonomy.HUMAN_APPROVAL.search(text) or autonomy.WORKFLOW_MARKER.search(
        str(value)
    ):
        message = (
            "an agent-derived value claims an approval or carries a marker: "
            f"{text[:60]}"
        )
        raise autonomy.AutonomyError(message, "postcondition")
    return text


def publish_section(root: Path, record: dict, *, short: bool = False) -> str:  # noqa: C901, PLR0912, PLR0915 - fixed sections
    """Return the Chat section of the Draft PR, rendered from operator records only."""
    run = Run(root, record)
    humans = run.humans()
    events = run.events()
    steps = run.steps()
    pin = branch_sync.read_pin(root, run.id)
    source = ""
    if record.get("continues"):
        try:
            found = autonomy.find_run(root, record["continues"])
        except autonomy.AutonomyError:
            found = None
        kind = autonomy.effective_mode(found) if found else "ballast-feature"
        source = f"{SEP}continues {record['continues']} ({kind})"
    lines = [
        CHAT_BEGIN,
        f"## Chat run {run.id}",
        "",
        (
            f"Mode: {run.mode} (driven by the operator; every gate decision "
            "below was made by the operator through `ballast run approve` or "
            "`reject`, and publishing needs every gate's latest approval "
            "current). "
            f"History: {_mode_history(record)}."
        ),
        (
            f"Feature: {run.feature_dir}{SEP}Issue #{run.issue}{SEP}branch "
            f"{_agent_value(pin.get('branch', 'not pinned'))}{SEP}run {run.id}{source}"
        ),
        "",
        "### Steps",
        "",
    ]
    starts = {item["step"]: item for item in steps if item.get("entry") == "start"}
    closes = [item for item in steps if item.get("entry") == "close"]
    if short:
        failed = [item for item in closes if item["outcome"] != "completed"]
        lines.append(f"{len(closes)} steps recorded; {len(failed)} did not complete.")
        if failed:
            lines.append(
                f"Latest failure: {failed[-1]['phase']} {failed[-1]['outcome']}."
            )
    else:
        lines += [
            (
                "| Phase | Agent (provider/model, role) | Started | Ended | "
                "Outcome | Postcondition |"
            ),
            "| --- | --- | --- | --- | --- | --- |",
        ]
        for close in closes:
            begin = starts.get(close["step"], {})
            phase = close["phase"] + (
                f" ({close['review_kind']})" if close.get("review_kind") else ""
            )
            lines.append(
                f"| {phase} | {_agent_value(begin.get('integration'))}/"
                f"{_agent_value(begin.get('model', 'unreported'))}, "
                f"{begin.get('role')} | "
                f"{begin.get('started_at')} | {close['ended_at']} | "
                f"{close['outcome']} | "
                f"{', '.join(close.get('postcondition', [])) or 'none'} |"
            )
        if not closes:
            lines.append("| none | | | | | |")
    lines += [
        "",
        "### Human approvals",
        "",
        "| Gate | Artifact | Digest | Decision | Approved at |",
        "| --- | --- | --- | --- | --- |",
    ]
    states = {gate: approval_state(run, gate, humans) for gate in GATES}
    for entry in humans:
        if entry["kind"] == "gate-approval":
            # ENG-003: say whether this approval is the gate's current one.
            state, latest = states[entry["gate"]]
            currency = state if latest and latest["id"] == entry["id"] else "superseded"
            decision = f"{entry['id']} approved by the operator ({currency})"
        elif entry["kind"] == "gate-rejection":
            decision = f"{entry['id']} rejected: {autonomy.neutralize(entry['ref'])}"
        else:
            continue
        lines.append(
            f"| {entry['gate']} | {_agent_value(entry['artifact'])} | "
            f"`{entry['digest'][:19]}` | {decision} | {entry['at']} |"
        )
    lines += [
        "",
        "### Decisions",
        "",
        "| DEC | Status | Human resolution |",
        "| --- | --- | --- |",
    ]
    path = run.file("decisions.md")
    if path.is_file() and not path.is_symlink():
        text = path.read_text(encoding="utf-8", errors="replace")
        resolved = artifacts.human_resolutions(run.feature(), text)
        by_decision = {
            entry["decision"]: entry["id"]
            for entry in humans
            if entry["kind"] == "decision-resolution"
        }
        for dec in dict.fromkeys(
            dec
            for dec, kind, _ in artifacts.decision_sections(text)
            if kind.lower() == "proposal"
        ):
            status_text = "resolved" if dec in resolved else "open"
            lines.append(
                f"| {_agent_value(dec)} | {status_text} | "
                f"{by_decision.get(dec, 'none') if dec in resolved else 'none'} |"
            )
    carried = autonomy.current_decisions(_source_decisions(run))
    replaced = superseding(run, humans)
    if carried:
        lines += ["", f"Carried decisions from run {record['continues']}:"]
        lines += [
            f"- {entry['id']} ({entry['point']}, agent-provisional): "
            + (
                f"superseded by {replaced[entry['id']]}"
                if entry["id"] in replaced
                else "still provisional"
            )
            for entry in carried
        ]
    lines += [
        "",
        "### Reviews",
        "",
        "| Kind | Reviewer (provider/model) | Cross-provider | Verdict | Report |",
        "| --- | --- | --- | --- | --- |",
    ]
    lines.extend(
        f"| {event['review_kind']} | {_agent_value(event['reviewer']['provider'])}/"
        f"{_agent_value(event['reviewer']['model'])} | "
        f"{'yes' if event['cross_provider'] else 'no'} | "
        f"{_agent_value(event['verdict'])} | {_agent_value(event['report'])} |"
        for event in events
        if event["kind"] == "review"
    )
    lines += ["", "### Checks", ""]
    latest = None
    for event in events:
        if event["kind"] == "project-checks":
            latest = event
    if latest is None:
        lines.append("No project checks recorded.")
    elif latest.get("unavailable"):
        lines.append("No [checks] table: checks unavailable")
    elif short:
        failed_checks = [r for r in latest["results"] if r["exit"] != 0]
        lines.append(
            f"{len(latest['results'])} check commands; {len(failed_checks)} failed."
        )
    else:
        lines += [
            "| Command | Exit | Seconds | Provenance |",
            "| --- | --- | --- | --- |",
        ]
        lines += [
            f"| `{str(r['command']).replace('`', chr(39))}` | {r['exit']} | "
            f"{r['seconds']:.1f} | {r['provenance']} |"
            for r in latest["results"]
        ]
    lines += ["", "### Changes made outside agent steps", ""]
    changes = [event for event in events if event["kind"] == "out-of-step-change"]
    paths = sorted({p for event in changes for p in event["paths"]})
    if paths:
        shown = ", ".join(f"`{_agent_value(p)}`" for p in paths[:50])
        lines.append(
            f"{len(changes)} recorded; paths: {shown}"
            + (" ..." if len(paths) > 50 else "")  # noqa: PLR2004 - preview cap
        )
    else:
        lines.append("None.")
    lines += ["", LOGS_LOCAL, CHAT_END]
    section = "\n".join(lines)
    if not short and len(section) > autonomy.MAX_BODY:
        return publish_section(root, record, short=True)
    return section


def publish(root: Path, run_id: str) -> int:
    """`ballast run publish RUN` for a Chat run: the mode-aware publisher."""
    run = load(root, run_id)
    with Lock(run, "publish"):
        late_close(run)
        out_of_step(run)
        _require_no_step(run, "publish")
        state, _ = approval_state(run, "final")
        if state != "current":
            raise _refuse(
                run,
                "publish",
                f"the final approval is {state}; approve final first",
                EXIT_REFUSED,
            )
        passed, failing, event_id, detail = gate_precondition(run, "final")
        if not passed:
            reason = f"final precondition failed: {failing} ({event_id}): {detail}"
            raise _refuse(run, "publish", reason, EXIT_REFUSED)
        result = autonomy.publish(root, run.id)
        if not result["ok"]:
            _err(f"ballast: publish failed ({result['category']}): {result['message']}")
            archive(run)
            return (
                EXIT_REFUSED if result["category"] == "postcondition" else EXIT_BLOCKED
            )
        run.record = autonomy.read_run(root, run.id)
        if run.record["status"] == "completed":
            autonomy.set_status(run.record, "published")
        run.record["last_manifest"] = current_manifest(run)
        run.save()
        archive(run)
        _out(
            f"Draft PR: {result['url']}\nThe PR's Chat section lists every human "
            "approval; merging stays your decision."
        )
        # The acceptance packet (#19, #111) for the PR just verified; never a
        # second PR, even while GitHub's list lags.
        checkpoint(run, create=False)
    return EXIT_OK
