"""Who recorded a decision: the operator at a terminal, or a relaying agent session.

ADR-0020 (#147). Every operator-state record that says who acted (human
decisions `HD-NNNN` and mode-history entries) takes its actor from
`resolve`, and every command an agent session may run is in `MATRIX`:

- `--relayed-by SESSION` given: the actor is `relayed`, naming the session.
  The launcher cannot verify that the operator said yes in chat, so the
  record says who claims it and is never rendered as operator-typed.
- Otherwise, stdin and stdout both terminals: the actor is the `operator`.
- Otherwise the command is refused before anything is written.

A terminal is not proof of a human: an agent session can allocate a
pseudo-terminal. The boundary that keeps an agent *inside* a workflow step
from running any `ballast` command is the `in-progress` marker and the
step's sandbox, not this module and not `BALLAST_AGENT_STEP`.

Standard library only; imported by the trusted `run.py`, `chat.py` and
`autonomy.py` under `python3 -I -S`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import TextIO

SESSION = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,79}")
# Block categories that carry no decision: a relayed resume or continue of
# them needs no --ref (operator decision D-08). Every other category, and
# any category added later, carries a decision until classified here.
DECISION_FREE = frozenset({"upstream-sync", "interrupted", "postcondition"})
# The commands that accept --relayed-by; every other one refuses it.
RELAY_ACCEPTING = ("start", "resume", "continue", "approve")

NO_TERMINAL = (
    "without a terminal, name the relaying agent session with --relayed-by "
    "SESSION; nothing was recorded"
)
HUMAN_GATED = (
    "a human-gated run takes approvals only from the operator at a terminal; "
    "nothing was recorded"
)
AUTONOMOUS = "an Autonomous run has no human gate before merge; nothing was recorded"
DECISION_BLOCK = (
    "the {category} block carries a decision; relay it only with --ref naming "
    "the operator's answer; nothing was recorded"
)
NOT_ACCEPTED = "--relayed-by is not accepted by {command}"
INVALID_SESSION = (
    "--relayed-by SESSION must match [A-Za-z0-9][A-Za-z0-9._:-]{0,79} and "
    "claim no approval; nothing was recorded"
)


class Refused(Exception):  # noqa: N818 - a refusal, not an error
    """The actor rule refuses the command; nothing was recorded."""


@dataclass(frozen=True)
class Actor:
    """Who acted: `operator` at a terminal, or `relayed` by a named session."""

    by: str
    relayed_by: str | None = None

    def fields(self) -> dict[str, str]:
        """Return the record fields: `by`, and `relayed_by` for a relay."""
        if self.by == "relayed":
            return {"by": "relayed", "relayed_by": str(self.relayed_by)}
        return {"by": "operator"}


OPERATOR = Actor("operator")


@dataclass(frozen=True)
class Row:
    """One row of the agent command matrix (contracts/cli.md)."""

    command: str
    session: str  # "may run", "relays" or "refused"
    recorded: str
    modes: dict[str, str]


# The agent command matrix (ADR-0020). The policy table and the ADR name
# exactly these commands; tests/test_governance.py keeps them equal.
MATRIX = (
    Row(
        "ballast setup",
        "may run",
        "none",
        {"human-gated": "yes", "chat": "yes", "autonomous": "yes"},
    ),
    Row(
        "ballast intake",
        "may run",
        "none",
        {"human-gated": "yes", "chat": "yes", "autonomous": "yes"},
    ),
    Row(
        "ballast run status",
        "may run",
        "none",
        {"human-gated": "yes", "chat": "yes", "autonomous": "yes"},
    ),
    Row(
        "ballast run start",
        "may run",
        "none",
        {"human-gated": "yes", "chat": "n/a", "autonomous": "n/a"},
    ),
    Row(
        "ballast run start --mode chat",
        "may run",
        "relayed mode start",
        {"human-gated": "n/a", "chat": "yes", "autonomous": "n/a"},
    ),
    Row(
        "ballast run start --mode autonomous",
        "relays",
        "relayed mode start",
        {"human-gated": "n/a", "chat": "n/a", "autonomous": "yes"},
    ),
    Row(
        "ballast run resume",
        "relays",
        "relayed block resolution",
        {"human-gated": "yes", "chat": "n/a", "autonomous": "yes"},
    ),
    Row(
        "ballast run continue",
        "relays",
        "relayed block resolution or mode change",
        {"human-gated": "n/a", "chat": "n/a", "autonomous": "yes"},
    ),
    Row(
        "ballast run step --headless",
        "may run",
        "none",
        {"human-gated": "n/a", "chat": "yes", "autonomous": "n/a"},
    ),
    Row(
        "ballast run step",
        "refused",
        "none",
        {"human-gated": "n/a", "chat": "operator", "autonomous": "n/a"},
    ),
    Row(
        "ballast run publish",
        "may run",
        "none",
        {"human-gated": "n/a", "chat": "yes", "autonomous": "runner"},
    ),
    Row(
        "ballast run approve",
        "relays",
        "relayed gate approval",
        {"human-gated": "refused", "chat": "yes", "autonomous": "refused"},
    ),
    Row(
        "ballast run reject",
        "refused",
        "operator",
        {"human-gated": "operator", "chat": "operator", "autonomous": "n/a"},
    ),
    Row(
        "ballast run resolve",
        "refused",
        "operator",
        {"human-gated": "operator", "chat": "operator", "autonomous": "n/a"},
    ),
    Row(
        "ballast run mode",
        "refused",
        "operator",
        {"human-gated": "operator", "chat": "operator", "autonomous": "n/a"},
    ),
    # D-09: outside a step only; the in-progress marker refuses it inside one.
    Row("ballast trust", "may run", "none", {}),
    Row("ballast discard-runs", "may run", "none", {}),
    Row("ballast ledger", "may run", "none", {}),
)


def agent_runnable() -> set[str]:
    """Commands an agent session may run or relay."""
    return {row.command for row in MATRIX if row.session != "refused"}


def operator_only() -> set[str]:
    """Commands only the operator runs, at a terminal."""
    return {row.command for row in MATRIX if row.session == "refused"}


def session_refusal(session: str) -> str | None:
    """Why SESSION is not a valid relaying agent session, or None."""
    import autonomy  # noqa: PLC0415 - autonomy imports this module

    if not SESSION.fullmatch(session) or autonomy.HUMAN_APPROVAL.search(session):
        return INVALID_SESSION
    return None


def resolve(relayed_by: str | None, *, stdin: TextIO, stdout: TextIO) -> Actor:
    """Return the actor of a decision-recording command, or raise `Refused`."""
    if relayed_by is not None:
        refusal = session_refusal(relayed_by)
        if refusal is not None:
            raise Refused(refusal)
        return Actor("relayed", relayed_by)
    if _isatty(stdin) and _isatty(stdout):
        return OPERATOR
    raise Refused(NO_TERMINAL)


def _isatty(stream: object) -> bool:
    try:
        return bool(stream.isatty())  # type: ignore[attr-defined]
    except (AttributeError, OSError, ValueError):
        return False


def allowed(
    command: str,
    mode: str | None,
    actor: Actor,
    block_category: str | None = None,
    ref: str | None = None,
) -> str | None:
    """Return the refusal the matrix gives COMMAND, or None when it is allowed.

    `mode` is the run's effective mode; `block_category` the category of the
    block a `resume` or `continue` resolves; `ref` its `--ref`, if any.
    """
    if actor.by != "relayed":
        return None
    if command not in RELAY_ACCEPTING:
        return NOT_ACCEPTED.format(command=command)
    if command == "approve":
        return {"chat": None, "autonomous": AUTONOMOUS}.get(str(mode), HUMAN_GATED)
    if (
        command in {"resume", "continue"}
        and block_category is not None
        and block_category not in DECISION_FREE
        and not (ref and ref.strip())
    ):
        return DECISION_BLOCK.format(category=block_category)
    return None


def label(entry: dict) -> str:
    """Return who recorded ENTRY, as every renderer shows it (FR-011)."""
    if entry.get("by") == "relayed":
        return f"agent session {entry.get('relayed_by')} (relayed)"
    return str(entry.get("by"))
