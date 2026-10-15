"""Typed public coordinator declarations in the existing claim history."""

from __future__ import annotations

import os
import re
import unicodedata
from typing import TYPE_CHECKING

from tools import admission

if TYPE_CHECKING:
    from pathlib import Path

MAX_ROUNDS = 3
STATES = {
    "phase": {
        "understand",
        "decompose",
        "plan",
        "implement",
        "verify",
        "review",
        "publish",
        "blocked",
    },
    "plan": {"proposed", "accepted", "blocked"},
    "question": {"pending", "answered"},
    "decision": {"pending", "resolved"},
    "check": {"pending", "passed", "failed"},
    "review": {"pending", "accepted", "changes_required", "blocked"},
    "readiness": {"draft", "blocked", "ready"},
}
REVISION = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")
# Public summaries are coordinator-authored, never copied from private output.
# Match secret and path shapes, not common words.
SENSITIVE = re.compile(
    r"(?i)(?:(?<![a-z0-9])sk-[a-z0-9]|(?<![a-z0-9])gh[pousr]_[a-z0-9]|github_pat_|"
    r"xox[abpr]-|AKIA[0-9A-Z]{16}|glpat-|-----BEGIN [A-Z ]*PRIVATE KEY-----|"
    r"\bbearer\s+\S|authorization\s+(?:basic|digest|negotiate|token)\s+\S|"
    r"(?:password|passwd|secret|token|api[_ -]?key|authorization)(?:[_-]\w*)?\s*[=:]|"
    r"output\.txt|[a-z]:\\|"
    r"(?:^|[\s(`'\"=])(?:~|\\|/[^\s/]+/))"
)


def reference(value: object, repo: str) -> str | None:
    """Accept exact selected-repository GitHub evidence links only."""
    pattern = rf"https://github\.com/{re.escape(repo)}/(?:issues/[1-9]\d*(?:#issuecomment-\d+)?|pull/[1-9]\d*|actions/runs/[1-9]\d*)"
    return value if isinstance(value, str) and re.fullmatch(pattern, value) else None


def validate(value: dict, repo: str) -> dict:
    """Reject unknown fields, private text and unbound revision evidence."""
    if set(value) - {"kind", "state", "summary", "reference", "revision", "round"}:
        admission.fail("Unsupported public progress field")
    kind, state, summary = (value.get(k) for k in ("kind", "state", "summary"))
    if (
        not isinstance(kind, str)
        or kind not in STATES
        or not isinstance(state, str)
        or state not in STATES[kind]
        or not isinstance(summary, str)
        or not 0 < len(summary) <= admission.MAX_REASON
        or any(unicodedata.category(c).startswith("C") for c in summary)
        or SENSITIVE.search(summary)
    ):
        admission.fail("Invalid public progress declaration")
    if "reference" in value and reference(value["reference"], repo) is None:
        admission.fail("Progress reference must name selected repository evidence")
    if kind in {"question", "decision"} and "/issues/" not in value.get(
        "reference", ""
    ):
        admission.fail(
            "Questions and decisions require a main-conversation issue reference"
        )
    revision = value.get("revision")
    if (kind in {"check", "review", "readiness"} or revision is not None) and (
        not isinstance(revision, str) or not REVISION.fullmatch(revision)
    ):
        admission.fail("Evidence requires a full revision")
    if "round" in value and (
        kind != "review"
        or type(value["round"]) is not int
        or not 1 <= value["round"] <= MAX_ROUNDS
    ):
        admission.fail("Review round must be between one and three")
    return value.copy()


def record(claim: Path, declaration: dict) -> dict:
    """Append coordinator-only evidence under the shared admission lock."""
    with admission.locked(claim.parent):
        item = admission.read(claim)
        queue = admission.governing(claim.parent, item)
        if queue is None:
            admission.fail("Public progress requires a selected queue")
        if os.environ.get("BALLAST_COORDINATOR") != queue["coordinator"]:
            admission.fail("Queue context or coordinator changed")
        if (
            item.get("queue") != queue["id"]
            or item.get("repository") != queue["repository"]
            or item.get("issue") not in queue["issues"]
            or item.get("coordinator") != queue["coordinator"]
        ):
            admission.fail("Claim is outside coordinator's selected queue")
        public = validate(declaration, queue["repository"])
        admission.milestone(item, "progress", **public)
        admission.write(claim, item)
        return public
