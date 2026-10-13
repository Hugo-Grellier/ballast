"""Mark an eligible Autonomous run's published PR ready for review (#141).

`run.py` imports this module at startup, before any agent step, and calls
`complete` once after an Autonomous publication's Draft PR checkpoint and
acceptance packet, in the invocation that published (ADR-0019):

- it acts only for an Autonomous run whose trusted `ballast.toml` snapshot
  set `[autonomous] completion = "ready"`; otherwise it prints and records
  nothing, so the run's output and ledger stay as before;
- `evaluate` is a pure function over operator records only: the run record,
  the decision log, the human decisions, `checks.json`, this invocation's
  packet outcome and one read-back of the PR. It lists every failed
  condition, in the order of the spec's FR-005;
- only when none fails does it run `gh pr ready` as the operator, against
  the repository pinned in `ballast.toml`, through draft_pr's resolved `gh`,
  hardened environment and empty working directory, then reads the PR back:
  `ready` is recorded only when GitHub shows it ready at the published
  commit (BL-INV-005); once the request is issued, a Draft is reported only
  when the read-back still shows one at that commit, else `unverified`;
- `gh` output, tokens and agent text are never printed or recorded: every
  reason is fixed wording filled with validated values;
- it never raises, and never changes the run's status or exit status.

Marking a PR ready is not an approval: merging stays the only human approval.
"""

from __future__ import annotations

import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import autonomy
import draft_pr
import ledger
from ledger import COMPLETION_REASONS

RISKS = ("R0", "R1")
PACKET_DONE = frozenset({"published", "updated", "unchanged"})
# The open findings each `completion_max_severity` allows (research R13).
ALLOWED = {"low": {"low", "info"}, "info": {"info"}, "none": set()}
OPEN = frozenset({"open", "accepted-provisionally"})
APPROVAL = "merging stays the only human approval"
UNVERIFIED = "the forge did not report the PR ready at the published commit"


@dataclass(frozen=True)
class Reason:
    """One failed condition: a code from COMPLETION_REASONS and its wording."""

    code: str
    text: str
    cause: str | None = None


@dataclass(frozen=True)
class Inputs:
    """Everything `evaluate` reads; collected from operator records only.

    `pr` is the PR read back once, or the fixed cause code of a failed read.
    `repo`, `number`, `base` and `branch` are the publication's own.
    """

    run: dict
    decisions: list[dict]
    human: list[dict]
    checks: list[dict] | None
    packet: Any  # packet.PacketOutcome or None
    commit: str
    pr: dict | str
    repo: str
    number: int
    base: str
    branch: str


def reported(policy: dict) -> bool:
    """Tell whether a run's outcome is printed and recorded (research R4)."""
    return policy.get("completion_configured") == "ready"


def _plural(count: int, word: str) -> str:
    return f"{count} {word}" + ("" if count == 1 else "s")


def _mode(inputs: Inputs) -> Reason | None:
    if inputs.run.get("workflow") != "ballast-autonomous":
        return Reason("mode", "the run is not an Autonomous run")
    mode = autonomy.effective_mode(inputs.run)
    if mode == "autonomous":
        return None
    shown = mode if mode in autonomy.MODES else "another"
    return Reason("mode", f"the run is in {shown} mode, not autonomous")


def _policy(inputs: Inputs) -> Reason | None:
    policy = inputs.run["eligibility"]["policy"]
    if policy.get("completion") == "ready":
        return None
    if policy.get("completion_flag") == "draft":
        return Reason("policy-draft", "the run's start flag chose draft")
    return Reason("policy-draft", "the completion policy is draft")


def _risk(inputs: Inputs) -> Reason | None:
    """Risk R0 or R1, and no R2 boundary declared (security review SEC-001)."""
    level = inputs.run["risk"].get("level")
    if level not in RISKS:
        return Reason("risk", f"risk {level if level in autonomy.RISKS else 'unknown'}")
    if inputs.run["risk"].get("boundaries"):
        return Reason("risk", "R2 boundaries declared")
    return None


def _privileged(inputs: Inputs) -> Reason | None:
    actions = autonomy.privileged_union(inputs.run, inputs.decisions)
    if not actions:
        return None
    # A kind outside the fixed list is shown as `other`, never as its text.
    kinds = sorted(
        {
            kind if kind in autonomy.ACTION_KINDS else autonomy.OTHER_ACTION
            for kind in map(autonomy.action_kind, actions)
        }
    )
    text = f"privileged actions declared: {', '.join(kinds)}"
    return Reason("privileged-action", text)


def _final(inputs: Inputs) -> Reason | None:
    if autonomy.current(inputs.decisions, "final-acceptance"):
        return None
    return Reason("no-final-acceptance", "no final acceptance recorded")


def _converged(inputs: Inputs) -> Reason | None:
    """Read the recorded review verdict, never `reviews/convergence.md` (R6)."""
    entries = autonomy.current(inputs.decisions, "spec-reconciliation")
    if entries and all(
        (entry.get("review") or {}).get("verdict") == "approved" for entry in entries
    ):
        return None
    return Reason(
        "not-converged",
        "spec reconciliation is not recorded as approved and converged",
    )


def _findings(inputs: Inputs) -> Reason | None:
    threshold = inputs.run["eligibility"]["policy"].get("completion_max_severity")
    if threshold not in ALLOWED:
        threshold = "low"
    above = [
        finding.get("severity")
        for entry in autonomy.current_decisions(inputs.decisions)
        for finding in (entry.get("review") or {}).get("findings") or []
        if finding.get("disposition") in OPEN
        and finding.get("severity") not in ALLOWED[threshold]
    ]
    if not above:
        return None
    # An unknown severity counts as the highest: any doubt keeps the Draft.
    known = [severity for severity in autonomy.SEVERITIES if severity in above]
    highest = known[0] if len(known) == len(set(above)) else "unknown"
    return Reason(
        "open-finding",
        f"{_plural(len(above), 'open finding')} above the {threshold} threshold, "
        f"highest {highest}",
    )


def _checks(inputs: Inputs) -> Reason | None:
    checks = inputs.checks
    if checks is None:
        return Reason("checks", "run-checks not run")
    passed = (
        bool(checks)
        and all(
            isinstance(c, dict) and c.get("exit") == 0 and not c.get("timed_out")
            for c in checks
        )
        and bool(inputs.run.get("checked_tree"))
    )
    if passed:
        return None
    return Reason("checks", "run-checks did not pass on the published tree")


def _packet(inputs: Inputs) -> Reason | None:
    packet = inputs.packet
    if packet is None:
        return Reason("packet", "acceptance packet not published")
    if packet.state not in PACKET_DONE:
        state = packet.state if packet.state in ledger.PACKET_REASONS else "unknown"
        reasons = ledger.PACKET_REASONS.get(packet.state, frozenset())
        why = f" ({packet.reason})" if packet.reason in reasons else ""
        return Reason("packet", f"acceptance packet {state}{why}")
    if packet.head != inputs.commit:
        return Reason("packet", "acceptance packet head is not the published commit")
    return _criteria(packet.counts or {})


def _criteria(given: dict) -> Reason | None:
    """Every criterion in the packet is verified, and there is at least one."""
    counts = {key: given.get(key) for key in ledger.PACKET_COUNTS}
    if not all(type(value) is int for value in counts.values()):
        return Reason("packet", "acceptance packet counts are unavailable")
    others = [counts[key] for key in ledger.PACKET_COUNTS if key != "verified"]
    if counts["verified"] >= 1 and not any(others):
        return None
    if not any(counts.values()):
        return Reason("packet", "the acceptance packet lists no criterion")
    return Reason(
        "packet",
        f"criteria not all verified: {counts['failed']} failed, "
        f"{counts['not_run']} not run, {counts['stale']} stale, "
        f"{counts['missing']} missing",
    )


def _material(inputs: Inputs) -> Reason | None:
    ids = [
        entry["id"]
        for entry in autonomy.current_decisions(inputs.decisions)
        if entry.get("material") is True
    ]
    if not ids:
        return None
    shown = [i if autonomy.PD_ID.fullmatch(str(i)) else "PD-????" for i in ids]
    return Reason("material-change", f"material provisional change {', '.join(shown)}")


def _blocks(inputs: Inputs) -> Reason | None:
    ids = [e["id"] for e in inputs.human if e.get("kind") == "block-resolution"]
    if not ids:
        return None
    shown = [i if autonomy.HD_ID.fullmatch(str(i)) else "HD-????" for i in ids]
    text = f"a block was resolved during the run ({', '.join(shown)})"
    return Reason("block-resolved", text)


def _cause(cause: str) -> str:
    """Return a Draft PR `failed-retryable` code; anything else is `github-error`."""
    return cause if cause in ledger.PR_REASONS["failed-retryable"] else "github-error"


def _head(inputs: Inputs) -> Reason | None:
    pr = inputs.pr
    if isinstance(pr, str):
        cause = _cause(pr)
        text = f"the PR could not be read back ({cause})"
        return Reason("pr-unreadable", text, cause)
    problem = autonomy._pr_problem(pr, inputs.repo, inputs.base, inputs.branch)  # noqa: SLF001
    if problem or pr.get("number") != inputs.number:
        text = f"PR #{inputs.number} is not an open draft from the run's branch"
        return Reason("pr-changed", text)
    head = pr.get("head") if isinstance(pr.get("head"), dict) else {}
    if head.get("sha") != inputs.commit:
        return Reason("head-moved", "the PR head is not the published commit")
    return None


# FR-005's twelve conditions, in order.
CONDITIONS = (
    _mode,
    _policy,
    _risk,
    _privileged,
    _final,
    _converged,
    _findings,
    _checks,
    _packet,
    _material,
    _blocks,
    _head,
)


def evaluate(inputs: Inputs) -> tuple[Reason, ...]:
    """Return every failed condition, in FR-005 order, at most one per condition.

    Pure: it reads only `inputs`. An empty result means the run is eligible.
    """
    found = tuple(r for r in (check(inputs) for check in CONDITIONS) if r)
    if any(reason.code not in COMPLETION_REASONS for reason in found):
        message = "unknown completion reason"
        raise ValueError(message)
    return found


def format_line(
    state: str, number: int | None, url: str | None, reasons: tuple[Reason, ...]
) -> str:
    """Return `PR completion: <state>[ #<n> <url>][: <reason>[; <reason>]...]`.

    A ready line ends with the reminder that merging is the only approval.
    """
    line = f"PR completion: {state}"
    if number is not None and url:
        line += f" #{number} {url}"
    if state == "ready-for-review":
        return f"{line}; {APPROVAL}"
    return f"{line}: {'; '.join(reason.text for reason in reasons)}"


def event_data(
    outcome: str, number: int | None, commit: object, reasons: tuple[Reason, ...]
) -> dict[str, Any]:
    """Return the `pr_completion` ledger data: codes, IDs and the commit only."""
    data: dict[str, Any] = {"outcome": outcome, "pr_number": number, "commit": commit}
    if reasons:
        data["reasons"] = [reason.code for reason in reasons]
    causes = [reason.cause for reason in reasons if reason.cause]
    if causes:
        data["cause"] = causes[0]
    return data


class _Gh:
    """The operator's `gh`, resolved and run as the Draft PR checkpoint does.

    It is found outside every working tree and agent temp root, and starts
    in an empty directory with the hardened environment; every call names
    the pinned repository.
    """

    def __init__(self, root: Path) -> None:
        self.root = root
        self.path, shadowed = draft_pr._resolve("gh", root)  # noqa: SLF001
        self.missing = "gh-untrusted" if shadowed else "gh-missing"

    def run(self, *args: str) -> draft_pr.Result | str:
        """Return the call's result, or the cause code when no trusted gh exists."""
        if self.path is None:
            return self.missing
        with tempfile.TemporaryDirectory(prefix="ballast-gh-") as away:
            return draft_pr._command(  # noqa: SLF001
                [self.path, *args], cwd=Path(away), root=self.root
            )

    def read(self, repo: str, number: int) -> dict | str:
        """Return the PR read back, or the fixed cause code of a failed read."""
        result = self.run("api", f"repos/{repo}/pulls/{number}")
        if isinstance(result, str):
            return result
        if result.returncode:
            return draft_pr._classify(result)  # noqa: SLF001
        data = draft_pr._json(result)  # noqa: SLF001
        return data if isinstance(data, dict) else "github-error"


def _ready_at(pr: dict | str, number: int, commit: str) -> bool:
    """Tell whether a read-back shows PR `number` ready for review at `commit`."""
    if not isinstance(pr, dict):
        return False
    head = pr.get("head") if isinstance(pr.get("head"), dict) else {}
    return (
        pr.get("number") == number
        and pr.get("state") == "open"
        and pr.get("draft") is False
        and head.get("sha") == commit
    )


def _decide(
    root: Path, run_id: str, run: dict, publication: dict, packet: object
) -> tuple[str, tuple[Reason, ...]]:
    """Collect the inputs, evaluate them, and mark ready when all conditions hold."""
    repo, number, commit = (publication[k] for k in ("repo", "number", "commit"))
    gh = _Gh(root)
    inputs = Inputs(
        run=run,
        decisions=autonomy.read_decisions(root, run_id),
        human=autonomy.read_human_decisions(root, run_id),
        checks=autonomy.read_checks(root, run_id),
        packet=packet,
        commit=commit,
        pr=gh.read(repo, number),
        repo=repo,
        number=number,
        base=publication["base"],
        branch=publication["branch"],
    )
    failed = evaluate(inputs)
    if failed:
        return "draft", failed
    try:
        return _mark(gh, repo, number, commit)
    except (Exception, KeyboardInterrupt):  # noqa: BLE001 - the request may be applied
        return "unverified", (Reason("forge-unverified", UNVERIFIED),)


def _mark(
    gh: _Gh, repo: str, number: int, commit: str
) -> tuple[str, tuple[Reason, ...]]:
    """Run `gh pr ready` and read the PR back once; never report a Draft blindly.

    Once the request is issued, a failed or timed-out call may still have
    been applied: only a read-back showing the PR still a Draft at the
    published commit reports the forge failure; any doubt is `unverified`.
    """
    marked = gh.run("pr", "ready", str(number), "--repo", repo)
    if isinstance(marked, str):
        cause = _cause(marked)
        return "draft", (
            Reason("forge-failed", f"marking ready failed ({cause})", cause),
        )
    pr = gh.read(repo, number)
    if _ready_at(pr, number, commit):
        return "ready", ()
    if marked.returncode and isinstance(pr, dict) and pr.get("draft") is True:
        head = pr.get("head") if isinstance(pr.get("head"), dict) else {}
        if head.get("sha") == commit:
            cause = _cause(draft_pr._classify(marked))  # noqa: SLF001
            text = f"marking ready failed ({cause})"
            return "draft", (Reason("forge-failed", text, cause),)
    return "unverified", (Reason("forge-unverified", UNVERIFIED),)


def complete(root: Path, run_id: str, publication: dict, packet: object) -> str | None:
    """Evaluate a reported run once; print one line and record one event.

    Returns the printed line, or None when the run is not reported (then
    nothing is printed or recorded). Never raises.
    """
    try:
        run = autonomy.read_run(root, run_id)
        policy = run["eligibility"]["policy"]
        if run["workflow"] != "ballast-autonomous" or not reported(policy):
            return None
    except Exception:  # noqa: BLE001 - unknown policy: report nothing (FR-013)
        return None
    number, url = publication.get("number"), publication.get("url")
    number = number if type(number) is int else None
    url = url if isinstance(url, str) and ledger.PR_URL.fullmatch(url) else None
    try:
        outcome, reasons = _decide(root, run_id, run, publication, packet)
    except (Exception, KeyboardInterrupt) as error:  # noqa: BLE001 - keeps the Draft
        outcome = "draft"
        text = f"completion check failed ({type(error).__name__})"
        reasons = (Reason("internal-error", text),)
    state = "ready-for-review" if outcome == "ready" else outcome
    line = format_line(state, number, url, reasons)
    data = event_data(outcome, number, publication.get("commit"), reasons)
    try:
        event = ledger.new_event(
            run_id, run["feature"], "pr_completion", "runner", data
        )
        ledger.append(root, event)
    except Exception as error:  # noqa: BLE001 - the line is still printed
        line += f" (not recorded: {type(error).__name__})"
    sys.stdout.write(line + "\n")
    return line
