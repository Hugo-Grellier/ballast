"""Atomic local admission and controls shared by Git worktrees and workers."""

from __future__ import annotations

import contextlib
import json
import math
import os
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, NoReturn

if os.name == "posix":
    import fcntl

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

MAX_ISSUES = 100
MAX_REFERENCE = 128
MAX_REASON = 256

DEFAULTS = {"issues": 1, "workers": 2, "backlog": 2, "attempts": 3, "seconds": 3600}
ACTIVE = {"active", "unknown"}
# Coordinator-recorded issue states; only GitHub-confirmed merge leaves backlog.
ACTIVITIES = {"active", "unknown", "pr_wait", "merged", "stopped"}
# Allowed coordinator transitions; None is a claim made before queue control.
TRANSITIONS = {
    None: {"unknown", "stopped"},
    "active": {"pr_wait", "stopped", "unknown"},
    "unknown": {"stopped", "active"},
    "pr_wait": {"active", "merged", "stopped"},
    "stopped": {"active"},
    "merged": set(),
}
QUOTA_ERRORS = {"usageLimitExceeded", "rateLimitExceeded"}


@dataclass(frozen=True)
class QueueSpec:
    """Explicit queue selection, fixed budgets and caller/instruction identity."""

    repository: str
    issues: list[int]
    limits: dict[str, int]
    coordinator: str
    revision: str


class AdmissionError(RuntimeError):
    """Work could not obtain an authorized local resource slot."""


def fail(reason: str) -> NoReturn:
    """Raise a fixed diagnostic without private payloads."""
    raise AdmissionError(reason)


def bounded(value: object, limit: int = MAX_REFERENCE) -> bool:
    """Accept a short explicit reference string."""
    return isinstance(value, str) and 0 < len(value) <= limit


@contextlib.contextmanager
def locked(state: Path) -> Iterator[None]:
    """Hold one short local mutex; never perform network or client work here."""
    if os.name != "posix":
        fail("Local admission requires POSIX file locks")
    state.mkdir(mode=0o700, parents=True, exist_ok=True)
    with (state / "admission.lock").open("a+") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def read(path: Path) -> dict:
    """Require an object record; partial/corrupt data is never absence."""
    try:
        value = json.loads(path.read_text())
    except ValueError:
        fail("Local execution record is malformed")
    if not isinstance(value, dict):
        fail("Local execution record is malformed")
    return value


def write(path: Path, value: dict) -> None:
    """Replace one record atomically while its caller holds the mutex."""
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.replace(path)


def valid_limits(limits: object) -> bool:
    """Every budget is explicit, positive and finite."""
    return (
        isinstance(limits, dict)
        and set(limits) == set(DEFAULTS)
        and all(type(item) is int and item > 0 for item in limits.values())
    )


def valid_quota(quota: object) -> bool:
    """Accept a quota pause with a finite retry time or an unknown window."""
    if not isinstance(quota, dict):
        return False
    retry = quota.get("retry_at")
    return retry is None or (type(retry) in (int, float) and math.isfinite(retry))


def policy(state: Path) -> dict | None:
    """Read the optional finite queue policy; malformed policy fails closed."""
    path = state / "queue.json"
    if not path.exists():
        return None
    value = read(path)
    quota = value.get("quota")
    if (
        value.get("schema") != 1
        or not valid_limits(value.get("limits"))
        or type(value.get("deadline")) not in (int, float)
        or not math.isfinite(value["deadline"])
        or value.get("mode") not in {"running", "paused", "cancelled"}
        or not isinstance(value.get("issues"), list)
        or not bounded(value.get("id"))
        or not bounded(value.get("repository"))
        or (quota is not None and not valid_quota(quota))
    ):
        fail("Queue policy is malformed")
    return value


def milestone(record: dict, kind: str, **values: object) -> None:
    """Keep control history separate from backend outcome evidence."""
    record.setdefault("history", []).append(
        {"at": datetime.now(UTC).isoformat(), "event": kind, **values}
    )


def runnable(value: dict | None) -> None:
    """Check queue controls before admission or a fresh turn permit."""
    if value is None:
        return
    if value["mode"] != "running":
        fail("Queue is paused or cancelled")
    if time.time() >= value["deadline"]:
        fail("Queue elapsed-time limit reached")
    quota = value.get("quota")
    if quota and (quota.get("retry_at") is None or time.time() < quota["retry_at"]):
        fail("Provider quota is paused; no eligible retry window")


def records(state: Path) -> list[dict]:
    """Inspect every durable issue claim, including work outside this queue."""
    return [read(path) for path in sorted(state.glob("issue-*.json"))]


def governing(state: Path, record: dict) -> dict | None:
    """Return the claim's policy; a vanished policy never means unbounded."""
    value = policy(state)
    if record.get("queue") and (value is None or value["id"] != record["queue"]):
        fail("Claim's queue policy is missing or replaced; recover explicitly")
    return value


def issue_room(state: Path, value: dict, record: dict) -> None:
    """Require issue-cap room before this claim moves into active work."""
    used = capacity(state)["issues"]
    if record.get("activity", "unknown") in ACTIVE:
        used -= 1
    if used >= value["limits"]["issues"]:
        fail("Queue issue limit reached")


def capacity(state: Path) -> dict:
    """Unknown ownership consumes capacity until positive reconciliation."""
    claims = records(state)
    return {
        # A claim without a recorded activity predates queue control: unknown.
        "issues": sum(item.get("activity", "unknown") in ACTIVE for item in claims),
        "workers": len(list(state.glob("issue-*.worker"))),
        # Blocked/unverified drafts count too; only a confirmed merge releases.
        "backlog": sum(
            "pr" in item and item.get("activity") != "merged" for item in claims
        ),
    }


def create(state: Path, spec: QueueSpec) -> dict:
    """Create one selected finite queue; never silently replace existing limits."""
    issues, limits = spec.issues, spec.limits
    if (
        not issues
        or len(issues) > MAX_ISSUES
        or len(set(issues)) != len(issues)
        or any(type(item) is not int or item < 1 for item in issues)
    ):
        fail("Select one to 100 distinct positive issue numbers")
    if not valid_limits(limits):
        fail("Every queue limit must be an explicit positive integer")
    if not all(
        bounded(item) for item in (spec.repository, spec.coordinator, spec.revision)
    ):
        fail("Repository, coordinator and revision must be bounded references")
    with locked(state):
        if (state / "queue.json").exists():
            fail("Queue already exists; recover it instead of resetting its budget")
        value = {
            "schema": 1,
            "id": uuid.uuid4().hex,
            "repository": spec.repository,
            "issues": issues,
            "limits": limits,
            "coordinator": spec.coordinator,
            "instruction_revision": spec.revision,
            "started_at": datetime.now(UTC).isoformat(),
            "deadline": time.time() + limits["seconds"],
            "mode": "running",
        }
        milestone(value, "configured")
        write(state / "queue.json", value)
        return value


def admit_issue(state: Path, record: dict) -> None:
    """Reserve a fresh issue claim; caller holds the shared mutex."""
    value = policy(state)
    runnable(value)
    if value is None:
        return
    coordinator = os.environ.get("BALLAST_COORDINATOR", "")
    if coordinator != value["coordinator"]:
        fail("Queue operations require the queue's explicit coordinator reference")
    if (
        record["repository"].lower() != value["repository"].lower()
        or record["issue"] not in value["issues"]
    ):
        fail("Issue is outside the selected queue")
    used = capacity(state)
    if (
        used["issues"] >= value["limits"]["issues"]
        or used["backlog"] >= value["limits"]["backlog"]
    ):
        fail("Queue issue or human-review backlog limit reached")
    record.update(queue=value["id"], coordinator=coordinator, activity="active")
    milestone(record, "admitted")


def reserve_worker(claim: Path, identifier: str, role: str) -> Path:
    """Reserve all-worker capacity and the per-issue writer lock together."""
    state = claim.parent
    lock = claim.with_suffix(".worker")
    with locked(state):
        value = policy(state)
        runnable(value)
        if lock.exists():
            raise FileExistsError(lock.name)
        record = read(claim)
        value = governing(state, record)
        if value:
            if record.get("queue") != value["id"] or record.get(
                "coordinator"
            ) != os.environ.get("BALLAST_COORDINATOR"):
                fail("Claim needs explicit coordinator/queue reconciliation")
            if record.get("activity") != "active":
                fail("Issue is not admitted for active work")
            if capacity(state)["workers"] >= value["limits"]["workers"]:
                fail("Total worker limit reached, including unknown workers")
            if (
                record.get("worker_attempts", {}).get(role, 0)
                >= (value["limits"]["attempts"])
            ):
                fail("Worker attempt limit reached; budget cannot reset on resume")
            milestone(record, "worker_reserved", worker=identifier, role=role)
            write(claim, record)
        with lock.open("x") as stream:
            stream.write(identifier)
    return lock


def permit_turn(claim: Path, identifier: str, role: str) -> None:
    """Spend one attempt on a logical turn, before delivery or its receipt.

    Environment and qualification failures happen earlier and spend nothing.
    """
    with locked(claim.parent):
        record = read(claim)
        value = governing(claim.parent, record)
        runnable(value)
        if claim.with_suffix(".worker").read_text() != identifier:
            fail("Worker reservation changed before turn admission")
        if value:
            attempts = record.setdefault("worker_attempts", {})
            if attempts.get(role, 0) >= value["limits"]["attempts"]:
                fail("Worker attempt limit reached; budget cannot reset on resume")
            attempts[role] = attempts.get(role, 0) + 1
            milestone(record, "turn_permitted", worker=identifier, role=role)
            write(claim, record)


def release_worker(claim: Path, identifier: str) -> None:
    """Release only this settled reservation; never delete a replacement lock."""
    with locked(claim.parent):
        lock = claim.with_suffix(".worker")
        if lock.exists() and lock.read_text() == identifier:
            lock.unlink()


def release(claim: Path, identifier: str, evidence: str) -> dict:
    """Free an unknown worker only on recorded positive stop evidence."""
    if not bounded(evidence, MAX_REASON):
        fail("Release requires bounded stop evidence")
    with locked(claim.parent):
        lock = claim.with_suffix(".worker")
        if not lock.exists() or lock.read_text() != identifier:
            fail("No such worker reservation on this claim")
        record = read(claim)
        milestone(record, "worker_released", worker=identifier, evidence=evidence)
        write(claim, record)
        result = claim.parent / "workers" / identifier / "result.json"
        if result.exists():
            outcome = read(result)
            outcome.update(status="released", release_evidence=evidence)
            write(result, outcome)
        lock.unlink()
        return record


def adopt(claim: Path, evidence: str) -> dict:
    """Resume a verified existing attempt instead of creating a duplicate.

    The caller has already verified checkout, branch and base outside the lock.
    """
    if not bounded(evidence, MAX_REASON):
        fail("Recovery requires bounded evidence")
    state = claim.parent
    with locked(state):
        if claim.with_suffix(".worker").exists():
            fail("Release or reconcile the recorded worker before recovery")
        record = read(claim)
        value = governing(state, record) if record.get("queue") else policy(state)
        coordinator = os.environ.get("BALLAST_COORDINATOR", "")
        if record.get("coordinator") not in (None, coordinator) and (
            record.get("activity", "unknown") in ACTIVE
        ):
            fail("Active issue transfer needs recorded stop evidence first")
        if value:
            runnable(value)
            if record["repository"].lower() != value["repository"].lower() or (
                record["issue"] not in value["issues"]
            ):
                fail("Issue is outside the selected queue")
            if coordinator != value["coordinator"]:
                fail("Queue operations require the queue's coordinator reference")
            if record.get("activity") == "merged":
                fail("Merged work is complete; nothing to recover")
            issue_room(state, value, record)
            record.update(queue=value["id"], coordinator=coordinator, activity="active")
        record["status"] = "ready"
        milestone(record, "recovered", evidence=evidence)
        write(claim, record)
        return record


def record_pr(claim: Path, pr: dict) -> dict:
    """Attach publication evidence without changing the issue's activity."""
    with locked(claim.parent):
        record = read(claim)
        record["pr"] = pr
        milestone(record, "published", pr=pr["number"])
        write(claim, record)
        return record


def cancelled(state: Path) -> bool:
    """Live workers poll this between backend messages."""
    value = policy(state)
    return value is not None and value["mode"] == "cancelled"


def quota(state: Path, kind: str, retry_at: float | None) -> None:
    """Pause dispatch on a structured quota error; unknown window stays blocked."""
    with locked(state):
        value = policy(state)
        if value is None:
            return
        value["quota"] = {"error": kind, "retry_at": retry_at}
        milestone(value, "quota_paused", error=kind, retry_at=retry_at)
        write(state / "queue.json", value)


def control(state: Path, action: str, reason: str) -> dict:
    """Record an explicit control without inferring active workers stopped."""
    if action not in {"running", "paused", "cancelled"} or not bounded(
        reason, MAX_REASON
    ):
        fail("Control requires a supported action and bounded reason reference")
    with locked(state):
        value = policy(state)
        if value is None:
            fail("No queue to control")
        if value["mode"] == "cancelled" and action == "running":
            fail("Cancelled queue needs explicit recovery, not a control reset")
        value["mode"] = action
        if action == "running":
            # An explicit operator resume is the only way out of an unknown window.
            value.pop("quota", None)
        milestone(value, action, reason=reason)
        write(state / "queue.json", value)
        return value


def settle(claim: Path, activity: str, evidence: str) -> dict:
    """Record positive coordinator evidence; never infer it from age or PID."""
    if activity not in ACTIVITIES or not bounded(evidence, MAX_REASON):
        fail("Settlement requires a supported activity and bounded evidence")
    with locked(claim.parent):
        record = read(claim)
        value = governing(claim.parent, record)
        coordinator = os.environ.get("BALLAST_COORDINATOR", "")
        # An owner-less pre-queue claim may only move to unknown/stopped (TRANSITIONS).
        if value and record.get("coordinator") not in (None, coordinator):
            # Transfer needs the prior owner's recorded stop/handoff evidence.
            if record.get("activity", "unknown") in ACTIVE:
                fail("Active issue transfer needs recorded stop evidence first")
            record["coordinator"] = coordinator
        if activity not in TRANSITIONS.get(record.get("activity"), set()):
            fail("Unsupported activity transition; recover or stop explicitly")
        if activity == "active" and value:
            runnable(value)
            issue_room(claim.parent, value, record)
        record["activity"] = activity
        milestone(record, activity, evidence=evidence)
        write(claim, record)
        return record


def status(state: Path) -> dict:
    """Project queue, capacity and per-issue history from durable records."""
    keys = (
        "issue",
        "attempt",
        "branch",
        "status",
        "activity",
        "coordinator",
        "worker_attempts",
        "pr",
        "history",
    )
    with locked(state):
        return {
            "queue": policy(state),
            "used": capacity(state),
            "issues": [{key: item.get(key) for key in keys} for item in records(state)],
        }
