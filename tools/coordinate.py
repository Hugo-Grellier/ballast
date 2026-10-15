"""Configure, select, control, publish and observe one bounded local issue queue."""

from __future__ import annotations

import argparse
import contextlib
import itertools
import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

# Direct isolated invocation loads only this operator-selected source tree.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools import admission, progress, worktree

MAX_DEPENDENCIES = 50
# Bound regex work on untrusted issue bodies (GitHub caps bodies at 65536).
MAX_LINE = 1024
# Aliases per query keep the argument far below the per-argument exec limit.
BATCH = 100
ISSUE_FIELDS = """fragment F on Issue{
number state body subIssuesSummary{total}
blockedBy(first:50){pageInfo{hasNextPage} nodes{number state repository{nameWithOwner}}}
closedByPullRequestsReferences(first:20,includeClosedPrs:true){nodes{merged}}}"""
NAME = r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+"
# `#5`, `owner/repo#5` or `https://github.com/owner/repo/issues/5`.
REFERENCE = re.compile(rf"(?:https://github\.com/({NAME})/issues/|({NAME})?#)(\d+)")
BLOCKED_LINE = re.compile(r"(?im)^[ \t>*+-]*blocked by[*:]*[ \t]*(.+)$")
LOOKUP_ERRORS = (
    RuntimeError,
    KeyError,
    TypeError,
    ValueError,
    subprocess.SubprocessError,
)


def state_directory(cwd: Path) -> Path:
    """Shared local state for every linked worktree of this clone."""
    common = worktree.git(
        cwd, "rev-parse", "--path-format=absolute", "--git-common-dir"
    )
    return Path(common) / "ballast-v2"


def gh(cwd: Path, *args: str) -> object:
    """Call the verified GitHub.com host and parse its JSON response."""
    return json.loads(worktree.command(["gh", *args], cwd))


def check(value: object, number: int) -> dict:
    """Validate one issue node; anything malformed raises."""
    if (
        not isinstance(value, dict)
        or value["number"] != number
        or not isinstance(value["body"], str)
        or not isinstance(value["state"], str)
        or type(value["subIssuesSummary"]["total"]) is not int
        or not isinstance(value["closedByPullRequestsReferences"]["nodes"], list)
        or not isinstance(value["blockedBy"]["nodes"], list)
    ):
        raise TypeError
    return value


def issues(cwd: Path, repo: str, numbers: list[int]) -> dict[int, dict | None]:
    """Read issues in one aliased query; a missing, malformed or PR node is None.

    `issueOrPullRequest` resolves a PR number to `{}` instead of a NOT_FOUND error,
    so a PR-numbered prerequisite does not fail the whole call.
    """
    owner, name = repo.split("/")
    aliases = " ".join(
        f"i{n}:issueOrPullRequest(number:{int(n)}){{... on Issue{{...F}}}}"
        for n in numbers
    )
    query = (
        "query($owner:String!,$name:String!)"
        f"{{repository(owner:$owner,name:$name){{{aliases}}}}}\n{ISSUE_FIELDS}"
    )
    data = gh(
        cwd,
        "api",
        "graphql",
        "--hostname",
        "github.com",
        "-f",
        f"query={query}",
        "-f",
        f"owner={owner}",
        "-f",
        f"name={name}",
    )
    try:
        nodes = data["data"]["repository"]
    except (KeyError, TypeError):
        worktree.fail("Issue response is malformed")
    found: dict[int, dict | None] = {}
    for number in numbers:
        try:
            found[number] = check(nodes[f"i{number}"], number)
        except LOOKUP_ERRORS:
            found[number] = None
    return found


def prerequisites(repo: str, value: dict) -> dict[str, dict]:
    """Native `blockedBy` plus explicit `Blocked by` lines; unknown stays visible."""
    native = value["blockedBy"]
    if native["pageInfo"]["hasNextPage"]:
        worktree.fail("Issue lists too many prerequisites to evaluate")
    found: dict[str, dict] = {}
    for node in native["nodes"]:
        found[f"{node['repository']['nameWithOwner']}#{node['number']}"] = node
    for line in BLOCKED_LINE.findall(value["body"]):
        if len(line) > MAX_LINE:
            worktree.fail("Prerequisite line is too long to evaluate")
        for url_owner, owner, number in REFERENCE.findall(line):
            found.setdefault(f"{url_owner or owner or repo}#{number}", {})
    if len(found) > MAX_DEPENDENCIES:
        worktree.fail("Issue lists too many prerequisites to evaluate")
    return found


def cycles(graph: dict[int, set[int]]) -> set[int]:
    """Return every queue issue on a dependency cycle."""
    found: set[int] = set()
    for start in graph:
        stack, seen = [start], set()
        while stack:
            node = stack.pop()
            for child in graph.get(node, ()):
                if child == start:
                    found.add(start)
                elif child not in seen:
                    seen.add(child)
                    stack.append(child)
    return found


def lookup(cwd: Path, repo: str, number: int, cache: dict) -> dict | None:
    """Fetch once; a failed or missing issue is unknown, never absent."""
    preload(cwd, repo, [number], cache)
    return cache[number]


def preload(cwd: Path, repo: str, numbers: list[int], cache: dict) -> None:
    """Fill the cache for uncached numbers, one GraphQL call per BATCH chunk."""
    wanted = [n for n in dict.fromkeys(numbers) if n not in cache]
    for start in range(0, len(wanted), BATCH):
        chunk = wanted[start : start + BATCH]
        try:
            cache.update(issues(cwd, repo, chunk))
        except LOOKUP_ERRORS:
            # GitHub exits non-zero on any unresolved alias; read the chunk's
            # issues alone so only the unreadable one is unknown.
            for number in chunk:
                try:
                    cache.update(issues(cwd, repo, [number]))
                except LOOKUP_ERRORS:
                    cache[number] = None


def preload_prerequisites(cwd: Path, queue: dict, cache: dict) -> None:
    """Second batch: same-repo prerequisites of the queue issues just read."""
    repo = queue["repository"]
    wanted: list[int] = []
    for number in queue["issues"]:
        if cache.get(number) is None:
            continue
        with contextlib.suppress(*LOOKUP_ERRORS):
            for key in prerequisites(repo, cache[number]):
                owner, dependency = key.rsplit("#", 1)
                if owner.lower() == repo.lower():
                    wanted.append(int(dependency))
    preload(cwd, repo, wanted, cache)


def merged(value: dict) -> bool:
    """Count a closed issue only when a closing PR merged."""
    return value["state"] == "CLOSED" and any(
        node.get("merged") is True
        for node in value["closedByPullRequestsReferences"]["nodes"]
    )


def blockers(cwd: Path, queue: dict, number: int, context: tuple) -> list[str]:
    """Reasons blocking one queue issue; lookups failing affect only it."""
    cache, graph = context
    repo = queue["repository"]
    current = lookup(cwd, repo, number, cache)
    if current is None:
        return ["issue could not be read"]
    reasons = []
    if current["state"] != "OPEN" or current["subIssuesSummary"]["total"]:
        reasons.append("not an open leaf issue")
    try:
        found = prerequisites(repo, current)
    except LOOKUP_ERRORS:
        return [*reasons, "prerequisites could not be evaluated"]
    for key in found:
        owner, dependency = key.rsplit("#", 1)
        if owner.lower() != repo.lower():
            reasons.append(f"unknown cross-repository prerequisite {key}")
            continue
        target = lookup(cwd, repo, int(dependency), cache)
        if int(dependency) in queue["issues"]:
            graph.setdefault(number, set()).add(int(dependency))
        if target is None:
            reasons.append(f"unknown prerequisite #{dependency}")
        elif not merged(target):
            reasons.append(f"prerequisite #{dependency} has no merged change")
    return reasons


def select(cwd: Path) -> dict:
    """Report blocked issues and eligible work within the remaining budgets."""
    state = state_directory(cwd)
    with admission.locked(state):
        value = admission.policy(state)
        used = admission.capacity(state)
        claimed = {item.get("issue") for item in admission.records(state)}
    if value is None:
        worktree.fail("No queue is configured")
    worktree.repository(cwd, value["repository"])
    context: tuple = ({}, {})
    preload(cwd, value["repository"], list(value["issues"]), context[0])
    preload_prerequisites(cwd, value, context[0])
    blocked = {n: blockers(cwd, value, n, context) for n in value["issues"]}
    for number in cycles(context[1]):
        blocked[number].append("dependency cycle")
    # Mutating admission rechecks these budgets under the lock at prepare time.
    room = max(
        min(
            value["limits"]["issues"] - used["issues"],
            value["limits"]["backlog"] - used["backlog"],
        ),
        0,
    )
    try:
        admission.runnable(value)
        halted = None
    except admission.AdmissionError as error:
        halted, room = str(error), 0
    ready = [n for n in value["issues"] if not blocked[n] and n not in claimed]
    return {
        "mode": value["mode"],
        "halted": halted,
        "used": used,
        "eligible": ready[:room],
        "waiting_for_capacity": ready[room:],
        "claimed": sorted(n for n in value["issues"] if n in claimed),
        "blocked": {str(n): r for n, r in blocked.items() if r},
    }


def pulls(cwd: Path, record: dict) -> list[dict]:
    """Every PR, any state, from the claim's stable issue branch."""
    owner = record["repository"].split("/")[0]
    data = gh(
        cwd,
        "api",
        "--hostname",
        "github.com",
        f"repos/{record['repository']}/pulls?state=all&head={owner}:{record['branch']}",
    )
    if not isinstance(data, list):
        worktree.fail("Pull request response is malformed")
    return data


def matching(cwd: Path, record: dict, head: str) -> dict | None:
    """Reuse one exact PR; foreign, multiple or stale candidates block."""
    candidates = pulls(cwd, record)
    if not candidates:
        return None
    if len(candidates) > 1:
        worktree.fail("Several PRs use this issue branch; reconcile them first")
    found = candidates[0]
    if not isinstance(found, dict):
        worktree.fail("Pull request response is malformed")
    base, branch = found.get("base") or {}, found.get("head") or {}
    source = (branch.get("repo") or {}).get("full_name") or ""
    if (
        base.get("ref") != record["base"]
        or source.lower() != record["repository"].lower()
    ):
        worktree.fail("Existing PR targets another base or repository")
    if found.get("state") == "closed" and not found.get("merged_at"):
        worktree.fail("A closed PR uses this branch; reopen or reconcile it first")
    if branch.get("sha") != head:
        worktree.fail("Existing PR head differs from the reviewed head")
    return found


def publish(claim: Path, title: str, body: Path) -> dict:
    """Create or reuse one draft PR; re-query after an uncertain response."""
    # Refuse before any GitHub write; record_pr rechecks under the lock.
    admission.require_coordinator(admission.policy(claim.parent))
    record = worktree.validate(claim)
    cwd = Path(record["checkout"])
    # Pinned admin directory: never follow the worker-writable gitfile.
    head = worktree.git(cwd, "rev-parse", "HEAD", git_dir=Path(record["git_dir"]))
    remote = worktree.integration_revision(cwd, record["repository"], record["branch"])
    if remote != head:
        worktree.fail("Push the reviewed head before publication")
    found = matching(cwd, record, head)
    if found is None:
        # A lost response may follow creation; the re-query decides.
        with contextlib.suppress(RuntimeError, subprocess.SubprocessError):
            worktree.command(
                [
                    "gh",
                    "pr",
                    "create",
                    "--repo",
                    record["repository"],
                    "--head",
                    record["branch"],
                    "--base",
                    record["base"],
                    "--title",
                    title,
                    "--body-file",
                    str(body),
                    "--draft",
                ],
                cwd,
            )
        found = matching(cwd, record, head)
        if found is None:
            worktree.fail("PR creation failed; nothing was published")
    pr = {"number": found["number"], "url": found["html_url"], "head": head}
    return admission.record_pr(claim, pr)


def recover(cwd: Path, claim: Path, evidence: str) -> dict:
    """Adopt an existing attempt after verifying its checkout.

    A preparation interrupted before its checkout existed gets that checkout
    created at the recorded branch and base; nothing is deleted or replaced.
    """
    record = admission.read(claim)
    # Never pass recorded strings to Git unchecked: they must be the exact shapes
    # prepare() writes, and the checkout path is recomputed, not trusted.
    branch, base = record.get("branch"), record.get("base_sha")
    if (
        claim.parent != state_directory(cwd)
        or not isinstance(branch, str)
        or not re.fullmatch(rf"issue-{record.get('issue')}-[0-9a-f]{{8}}", branch)
        or not isinstance(base, str)
        or not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", base)
        or record.get("checkout") != str(claim.parent / "worktrees" / branch)
    ):
        worktree.fail("Claim identity is malformed; inspect it before recovery")
    checkout = claim.parent / "worktrees" / branch
    if not checkout.exists() and record.get("status") in {"preparing", "setup_failed"}:
        worktree.repository(cwd, record["repository"])
        try:
            worktree.git(
                cwd, "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}"
            )
            worktree.git(cwd, "worktree", "add", str(checkout), branch)
        except RuntimeError:
            worktree.git(cwd, "worktree", "add", "-b", branch, str(checkout), base)
    worktree.validate(claim, ready=False)
    return admission.adopt(claim, evidence)


def settle(claim: Path, activity: str, evidence: str) -> dict:
    """Coordinator reconciliation; merge removes backlog only when GitHub says so."""
    record = admission.read(claim)
    if activity == "merged":
        pr = record.get("pr")
        if not isinstance(pr, dict):
            worktree.fail("No recorded PR to confirm")
        data = gh(
            Path(record["checkout"]),
            "api",
            "--hostname",
            "github.com",
            f"repos/{record['repository']}/pulls/{pr['number']}",
        )
        if not isinstance(data, dict) or data.get("merged") is not True:
            worktree.fail("GitHub does not report this PR merged")
    return admission.settle(claim, activity, evidence)


def seconds(start: str, end: str) -> float:
    """Elapsed time between two recorded UTC milestones."""
    return (datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds()


def waited(history: list[dict], starts: set[str], stop: set[str], now: str) -> float:
    """Length of the union of spans opened by `starts` until a `stop` event.

    Overlapping spans (repeated pauses, a quota window inside a pause) count once.
    """
    spans = []
    for index, entry in enumerate(history):
        if entry["event"] not in starts:
            continue
        end = next(
            (later["at"] for later in history[index + 1 :] if later["event"] in stop),
            now,
        )
        opened = datetime.fromisoformat(entry["at"]).timestamp()
        closed = datetime.fromisoformat(end).timestamp()
        if isinstance(entry.get("retry_at"), (int, float)):
            # A known quota window ends on its own, without a control event.
            closed = min(closed, max(entry["retry_at"], opened))
        spans.append((opened, closed))
    total, reach = 0.0, float("-inf")
    for opened, closed in sorted(spans):
        if closed > reach:
            total += closed - max(opened, reach)
            reach = closed
    return total


# Worker terminal events (worker.py writes its final status as the last event).
# `unknown` is not among them: such a worker may still run until released.
SETTLED = {"completed", "cancelled", "quota", "not_started"}
# Every status a worker result can record.
WORKER_STATUSES = SETTLED | {"unknown", "released"}
# Claim events that change an issue's activity; `recovered` re-enters active work.
CHANGES = admission.ACTIVITIES | {"recovered"}


def worker_view(directory: Path, now: str) -> dict:
    """Split one worker's time into setup (until task accepted) and running."""
    # A worker that died before its first result write is never "settled".
    result = (
        admission.read(directory / "result.json")
        if (directory / "result.json").exists()
        else {"worker": directory.name, "status": "unrecorded"}
    )
    log = directory / "events.jsonl"
    events = (
        [json.loads(line) for line in log.read_text().splitlines()]
        if log.exists()
        else []
    )
    view = {key: result.get(key) for key in ("worker", "attempt", "role", "status")} | {
        "tokens": result.get("tokens", "unavailable")
    }
    if not events:
        return view | {"setup": "unavailable", "running": "unavailable"}
    accepted = next((e["at"] for e in events if e["event"] == "task_accepted"), None)
    # Still running (or died without a final event): count up to now.
    ended = events[-1]["event"] in SETTLED or result.get("status") == "released"
    last = events[-1]["at"] if ended else now
    return view | {
        "setup": seconds(events[0]["at"], accepted or last),
        "running": seconds(accepted, last) if accepted else 0.0,
    }


def rounds(roles: list[str]) -> dict:
    """Rework and review rounds counted from worker roles."""
    return {
        "review_rounds": roles.count("review"),
        "rework": max(roles.count("implement") - 1, 0),
    }


def issue_view(item: dict, workers: list[dict], now: str) -> dict:
    """Phase times, reopenings and the evidence trail for one issue."""
    history = item.get("history") or []
    mine = [w for w in workers if w["attempt"] == item["attempt"]]
    roles = [w["role"] for w in mine]
    timed = [w for w in mine if isinstance(w["running"], float)]
    phases = {
        role: sum(w["running"] for w in timed if w["role"] == role)
        for role in ("implement", "review")
    }
    phases["worker_setup"] = sum(w["setup"] for w in timed)
    phases["human_review_wait"] = waited(history, {"pr_wait"}, CHANGES, now)
    # Only a current terminal activity ends the clock; a resumed issue runs on.
    # Later milestones (a re-publish after merge) do not move the endpoint.
    finished = (
        next(h["at"] for h in reversed(history) if h["event"] in {"merged", "stopped"})
        if item.get("activity") in {"merged", "stopped"}
        else now
    )
    elapsed = seconds(history[0]["at"], finished) if history else 0.0
    # The rest is coordinator time: checks, decisions and publication.
    phases["coordinator"] = max(elapsed - sum(phases.values()), 0.0)
    activities = [
        "active" if h["event"] == "recovered" else h["event"]
        for h in history
        if h["event"] in CHANGES
    ]
    return {
        "workers": mine,
        "elapsed": elapsed if history else "unavailable",
        "phases": phases,
        **rounds(roles),
        # A PR sent back to active work after review is a regression signal.
        "reopened": sum(
            a == "pr_wait" and b == "active" for a, b in itertools.pairwise(activities)
        ),
        "evidence": [
            {"at": h["at"], "event": h["event"], "evidence": h["evidence"]}
            for h in history
            if "evidence" in h
        ],
    }


def observe(state: Path) -> dict:
    """Derive throughput, waiting and rework from records; never invent values."""
    view = admission.status(state)
    now = datetime.now(UTC).isoformat()
    workers = [
        worker_view(directory, now)
        for directory in sorted((state / "workers").glob("*"))
    ]
    for item in view["issues"]:
        item.update(issue_view(item, workers, now))
    queue = view["queue"] or {}
    history = queue.get("history") or []
    hours = seconds(history[0]["at"], now) / 3600 if history else 0.0
    published = sum(item.get("pr") is not None for item in view["issues"])
    merged = sum(i["activity"] == "merged" for i in view["issues"])
    view["summary"] = {
        "merged": merged,
        "awaiting_review": sum(i["activity"] == "pr_wait" for i in view["issues"]),
        "unknown_workers": sum(w["status"] == "unknown" for w in workers),
        "reopened": sum(i["reopened"] for i in view["issues"]),
        "queue_paused": waited(
            history, {"paused", "cancelled", "quota_paused"}, {"running"}, now
        ),
        "throughput": {
            "hours": hours,
            "published": published,
            "merged": merged,
            "published_per_hour": published / hours if hours else "unavailable",
        },
    }
    return view


def limits(args: argparse.Namespace) -> dict[str, int]:
    """Explicit overrides on top of the documented solo-pilot defaults."""
    return {
        key: value if getattr(args, key) is None else getattr(args, key)
        for key, value in admission.DEFAULTS.items()
    }


def parser() -> argparse.ArgumentParser:
    """Subcommands mirror the queue contract in docs/execution.md."""
    root = argparse.ArgumentParser(description=__doc__)
    root.add_argument("--cwd", type=Path, default=Path.cwd())
    commands = root.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create")
    create.add_argument("--repo", required=True)
    create.add_argument("--issue", type=int, action="append", required=True)
    create.add_argument("--coordinator", required=True)
    create.add_argument("--revision", required=True)
    for key in admission.DEFAULTS:
        create.add_argument(f"--{key}", type=int)
    commands.add_parser("select")
    commands.add_parser("status")
    record = commands.add_parser("record")
    record.add_argument("--claim", type=Path, required=True)
    record.add_argument("--kind", choices=sorted(progress.STATES), required=True)
    record.add_argument("--state", required=True)
    record.add_argument("--summary", required=True)
    record.add_argument("--reference")
    record.add_argument("--revision")
    record.add_argument("--round", type=int)
    control = commands.add_parser("control")
    control.add_argument("action", choices=("running", "paused", "cancelled"))
    control.add_argument("--reason", required=True)
    for name in ("settle", "publish", "recover", "release"):
        command = commands.add_parser(name)
        command.add_argument("--claim", type=Path, required=True)
        if name != "publish":
            command.add_argument("--evidence", required=True)
    commands.choices["settle"].add_argument(
        "activity", choices=sorted(admission.ACTIVITIES)
    )
    commands.choices["release"].add_argument("--worker", required=True)
    commands.choices["publish"].add_argument("--title", required=True)
    commands.choices["publish"].add_argument("--body-file", type=Path, required=True)
    return root


def run(args: argparse.Namespace) -> dict:
    """Dispatch one subcommand."""
    cwd = args.cwd.resolve(strict=True)
    # Refuse before any Git call follows a worker-writable gitfile.
    if "ballast-v2" in cwd.parts or worktree.inside_checkout():
        worktree.fail("Run queue commands from the project checkout, not an issue")
    state = state_directory(cwd)
    if cwd.is_relative_to(state):
        # Issue checkouts are worker-writable, including their `.git` gitfile.
        worktree.fail("Run queue commands from the project checkout, not an issue")
    if args.command == "create":
        worktree.repository(cwd, args.repo)
        spec = admission.QueueSpec(
            args.repo, args.issue, limits(args), args.coordinator, args.revision
        )
        return admission.create(state, spec)
    if args.command == "select":
        return select(cwd)
    if args.command == "status":
        return observe(state)
    if args.command == "control":
        return admission.control(state, args.action, args.reason)
    claim = args.claim.resolve(strict=True)
    if args.command == "record":
        declaration = {
            key: getattr(args, key)
            for key in ("kind", "state", "summary", "reference", "revision", "round")
            if getattr(args, key) is not None
        }
        return progress.record(claim, declaration)
    operations = {
        "settle": lambda: settle(claim, args.activity, args.evidence),
        "recover": lambda: recover(cwd, claim, args.evidence),
        "release": lambda: admission.release(claim, args.worker, args.evidence),
        "publish": lambda: publish(claim, args.title, args.body_file),
    }
    return operations[args.command]()


def main() -> int:
    """Print a local-only JSON projection; it may contain machine paths."""
    args = parser().parse_args()
    try:
        result = run(args)
    except (
        OSError,
        ValueError,
        KeyError,
        RuntimeError,
        subprocess.SubprocessError,
    ) as error:
        reason = (
            str(error)
            if isinstance(error, admission.FixedReasonError)
            else type(error).__name__
        )
        sys.stderr.write(f"Queue operation blocked: {reason}\n")
        return 1
    sys.stdout.write(json.dumps(result, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
