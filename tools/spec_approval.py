"""Read an issue's risk and its approved spec delta from GitHub (ADR-0027).

The implement dispatch calls `require`: an R1 or R2 leaf needs an approval
comment whose quoted hash equals the hash recomputed from the posted delta
comment, with `tools/spec_check.py`. GitHub is authoritative; nothing is cached.
The comment shapes are in docs/issue-workflow.md (Spec approval).
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# Direct isolated invocation loads only this operator-selected source tree.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools import admission, spec_check, worktree

RISK = re.compile(r"^Risk:[ \t]*(R[012])[ \t]*$", re.MULTILINE)
HASH = re.compile(r"^Hash:[ \t]*([0-9a-f]{64})[ \t]*$", re.MULTILINE)
DELTA_MARK = "## Spec delta"
APPROVAL = re.compile(r"Spec approved: ([0-9a-f]{64}) risk (R[012]) delta (\S+)")
# Comments from anyone else (a public repository's passers-by) never count.
TRUSTED = {"OWNER", "MEMBER", "COLLABORATOR"}


def first_line(comment: dict) -> str:
    """Return the comment's first line without surrounding whitespace."""
    return comment["body"].replace("\r\n", "\n").split("\n", 1)[0].strip()


def issue_risk(body: str) -> str:
    """Return the one `Risk: R0|R1|R2` line of an issue body, or refuse."""
    found = RISK.findall(body.replace("\r\n", "\n"))
    if len(found) != 1:
        worktree.fail("Issue body needs exactly one `Risk: R0|R1|R2` line")
    return found[0]


def delta_hash(comment: dict) -> str:
    """Recompute a delta comment's hash; refuse one that misstates it."""
    try:
        computed = spec_check.delta_hash(spec_check.parse_delta(comment["body"]))
    except spec_check.SpecError:
        worktree.fail("Posted spec delta is malformed")
    stated = HASH.findall(comment["body"])
    if stated != [computed]:
        worktree.fail("Posted spec delta states a hash its content does not have")
    return computed


def approval(repo: str, issue: int, comments: list[dict]) -> dict:
    """Return the approval of the latest posted delta, or refuse.

    The latest delta is current: a later delta with another hash supersedes an
    approval, one with the same hash (a refinement that changes no requirement
    or scenario) keeps it. An approval links a delta comment of this issue that
    precedes it and has the hash it quotes; only its first line counts.
    """
    trusted = list(
        enumerate(c for c in comments if c.get("author_association") in TRUSTED)
    )
    deltas = [(i, c) for i, c in trusted if first_line(c) == DELTA_MARK]
    if not deltas:
        worktree.fail("No spec delta is posted on the issue")
    current = delta_hash(deltas[-1][1])
    prefix = f"https://github.com/{repo}/issues/{issue}#issuecomment-".lower()
    approvals = [(i, c) for i, c in trusted if APPROVAL.fullmatch(first_line(c))]
    for index, comment in reversed(approvals):
        quoted, risk, url = APPROVAL.fullmatch(first_line(comment)).groups()
        linked = [
            d for i, d in deltas if i < index and url.lower() == prefix + str(d["id"])
        ]
        if quoted == current and linked and delta_hash(linked[0]) == quoted:
            return {
                "hash": quoted,
                "approved_risk": risk,
                "approval": comment["html_url"],
                "delta": url,
            }
    if approvals:
        reason = "No spec approval matches the current delta hash"
    else:
        reason = "No spec approval is posted on the issue"
    raise admission.FixedReasonError(reason)


def check(repo: str, issue: int, body: str, comments: list[dict]) -> dict:
    """Return the risk floor and, for R1/R2, the approval; refuse without one.

    The approved risk is stored in the approval line; the floor is the higher of
    it and the issue's `Risk:` line, for the merge verdict (#269).
    """
    risk = issue_risk(body)
    if risk == "R0":
        return {"risk": risk, "floor": risk}
    found = approval(repo, issue, comments)
    return {"risk": risk, "floor": max(risk, found["approved_risk"]), **found}


def require(cwd: Path, repo: str, issue: int) -> dict:
    """Read the issue and its comments from GitHub and apply `check`."""
    host = ("gh", "api", "--hostname", "github.com")
    path = f"repos/{repo}/issues/{issue}"
    data = json.loads(worktree.command([*host, path], cwd))
    body = (data.get("body") if isinstance(data, dict) else None) or ""
    if not isinstance(body, str):
        worktree.fail("Issue response is malformed")
    if issue_risk(body) == "R0":
        return check(repo, issue, body, [])
    fields = "{id, html_url, body, author_association}"
    lines = worktree.command(
        [*host, "--paginate", "--jq", f".[] | {fields}", f"{path}/comments"], cwd
    )
    comments = [json.loads(line) for line in lines.splitlines() if line]
    if not all(
        isinstance(c, dict) and isinstance(c.get("body"), str) for c in comments
    ):
        worktree.fail("Issue comments response is malformed")
    return check(repo, issue, body, comments)
