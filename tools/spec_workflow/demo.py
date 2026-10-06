"""Request an on-demand UI demo capture and show its outcome in the packet (#22).

`ballast run demo RUN_ID SCENARIO` (run.py) calls `request`; every packet step
(packet.py) calls `collect` and renders `lines`. `draft_pr` imports this
module, so `run.py` loads it before any agent step.

- The contract is the `[demo]` table of the protected `ballast.toml`
  (`demo_config`); a scenario's command never comes from a branch.
- The capture runs in the project's copy-once `ballast-demo.yml` workflow,
  dispatched on the feature branch's ref and never on the default branch, and
  only when the head commit's copy of the workflow is the default branch's
  blob (docs/adr/0012). A result is linked only when its run's `head_sha` is
  the requested commit.
- Every `gh` call goes through #17's checkpoint seam (resolved program, list
  argv, hardened environment, empty working directory, 30 s limit). `gh`
  output is parsed, never printed or stored; Ballast never downloads a log or
  an artifact and never runs the project's command locally.
- The ledger keeps one runner-only `demo_capture` event per dispatched
  request, written only after the dispatch succeeded, with no free text.
  GitHub Actions stays the source of truth for runs and media.

A video is never evidence for a criterion and never an approval.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import re
import secrets
import time
import tomllib
import urllib.parse
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any, NoReturn

import draft_pr
import ledger
import packet

if TYPE_CHECKING:
    from pathlib import Path

WORKFLOW = "ballast-demo.yml"
WORKFLOW_PATH = f".github/workflows/{WORKFLOW}"
TITLE = "Ballast demo {request}"
ARTIFACT = "ballast-demo-{request}"
# Step names of the template, in order; part of the workflow contract (R5).
STEP_VALIDATE = "Validate demo request"
STEP_RUN = "Run demo command"
STEP_TIMED_OUT = "Demo command timed out"
STEP_FAILED = "Demo command failed"
STEP_MISSING = "Demo video missing"
STEPS = (STEP_VALIDATE, STEP_RUN, STEP_TIMED_OUT, STEP_FAILED, STEP_MISSING)

CAPTURED, IN_PROGRESS, FAILED, MISSING = "captured", "in progress", "failed", "missing"
FAILED_STEPS = {
    STEP_VALIDATE: (FAILED, "request-invalid"),
    STEP_TIMED_OUT: (FAILED, "timed-out"),
    STEP_FAILED: (FAILED, "command-failed"),
    STEP_MISSING: (MISSING, "no-video"),
}
CONCLUSIONS = {"cancelled": "cancelled", "timed_out": "timed-out"}
REASONS = frozenset(
    {
        "queued",
        "running",
        "request-invalid",
        "timed-out",
        "command-failed",
        "cancelled",
        "job-failed",
        "run-not-found",
        "run-ambiguous",
        "run-list-truncated",
        "commit-mismatch",
        "no-video",
        "expired",
        "artifact-absent",
    }
)

# Contract limits (research R10): (lowest, highest, default).
RETENTION_DAYS = (1, 90, 14)
TIMEOUT_MINUTES = (1, 60, 15)
SCENARIO_LIMIT = 20
COMMAND_LIMIT = 1000
ENVIRONMENT_LIMIT = 80
DEMO_KEYS = frozenset({"retention_days", "timeout_minutes", "scenarios"})
SCENARIO_KEYS = frozenset({"name", "command", "video", "environment"})
NAME = re.compile(r"[A-Za-z0-9._-]{1,64}")
ERRORS = {
    "table": "demo is not a table",
    "key": "demo has an unknown key",
    "retention": "retention_days must be 1-90",
    "timeout": "timeout_minutes must be 1-60",
    "scenarios": "scenarios must be 1-20 tables",
    "scenario-key": "scenario has an unknown key",
    "name": "scenario name must match [A-Za-z0-9._-]{1,64}",
    "unique": "scenario names must be unique",
    "command": "scenario command must be 1-1000 printable characters on one line",
    "video": "scenario video is not a safe repository path",
    "environment": "scenario environment must be 1-80 printable characters",
}

# The bounded wait (R8) and the bounded run list (R6).
POLL_SECONDS = 10
WAIT_SECONDS = 120
PAGE_SIZE = 100
PAGE_LIMIT = 5
RUN_NOT_FOUND = timedelta(hours=24)
SHORT_LEVEL = 3  # #19 R14: at this size level the section is one count line.
GITHUB_ERROR = "github-error"  # An unreadable response is never "nothing found".

INTRO = (
    "A demo video helps a reviewer see behavior. It is not evidence for any "
    "criterion and not an approval. Reproduce a scenario by running its command "
    "at the captured commit."
)
REMEDIES: dict[tuple[str, str], str] = {
    ("refused", "not-configured"): (
        "declare [demo] with a scenario in ballast.toml, then run ballast trust"
    ),
    ("refused", "config-invalid"): "fix [demo] ({detail}), then run ballast trust",
    ("refused", "unknown-scenario"): "declared scenarios: {detail}",
    ("refused", "no-draft-pr"): (
        "ballast run publish {run} opens it once the run completes"
    ),
    ("refused", "pr-not-open"): (
        "the Draft PR line names the cause; a capture needs an open Ballast Draft PR"
    ),
    ("refused", "workflow-not-installed"): (
        f"copy templates/github/workflows/{WORKFLOW} of the pinned Ballast version "
        "to .github/workflows/ on the default branch"
    ),
    ("refused", "workflow-disabled"): (
        f"enable the {WORKFLOW} workflow in the repository's Actions settings"
    ),
    ("refused", "workflow-differs"): (
        f"the feature branch's {WORKFLOW_PATH} is missing or differs from the "
        "default branch's; sync the branch with the default branch, then request "
        "again"
    ),
    ("failed-retryable", "gh-forbidden"): (
        "grant your GitHub account write access to {repo}; dispatching a capture "
        "needs Actions write access"
    ),
}


@dataclass(frozen=True)
class DemoScenario:
    """One declared `[[demo.scenarios]]` entry."""

    name: str
    command: str
    video: str
    environment: str
    command_digest: str


@dataclass(frozen=True)
class DemoConfig:
    """The `[demo]` table; `error` is set, and `scenarios` empty, when invalid."""

    configured: bool = False
    retention_days: int = RETENTION_DAYS[2]
    timeout_minutes: int = TIMEOUT_MINUTES[2]
    scenarios: tuple[DemoScenario, ...] = ()
    error: str | None = None


@dataclass(frozen=True)
class DemoCapture:
    """A scenario's newest request, resolved at one checkpoint; never stored."""

    scenario: str
    commit: str
    outcome: str  # captured, in progress, failed, missing
    reason: str | None = None
    stale: bool = False
    run_id: int | None = None
    artifact_id: int | None = None
    command_changed: bool = False


@dataclass(frozen=True)
class DemoSection:
    """`packet.Sources.demo`: the contract and each scenario's newest capture."""

    repo: str
    head: str
    config: DemoConfig
    captures: tuple[DemoCapture, ...] = ()
    removed: tuple[str, ...] = ()  # requested scenarios no longer declared


@dataclass(frozen=True)
class DemoOutcome:
    """One `ballast run demo` result; fixed wording and validated IDs only."""

    state: str  # refused, failed-retryable, or a capture outcome
    reason: str | None = None
    scenario: str | None = None
    commit: str | None = None
    remedy: str | None = None
    link: str | None = None
    draft: draft_pr.Outcome | None = None
    refresh: draft_pr.Outcome | None = None


class ReadError(Exception):
    """A GitHub read failed; `cause` is #17's fixed classification."""

    def __init__(self, cause: str) -> None:
        """Keep the fixed cause only, never `gh` output."""
        super().__init__(cause)
        self.cause = cause


def _sleep(seconds: float) -> None:
    time.sleep(seconds)


def _monotonic() -> float:
    return time.monotonic()


# --- contract ---------------------------------------------------------------------


def _printable(value: object, limit: int) -> bool:
    return isinstance(value, str) and 0 < len(value) <= limit and value.isprintable()


def _bounded(value: object, bounds: tuple[int, int, int]) -> int | None:
    if value is None:
        return bounds[2]
    if type(value) is not int or not bounds[0] <= value <= bounds[1]:
        return None
    return value


def _scenario(entry: dict[str, Any], seen: list[DemoScenario]) -> DemoScenario | str:
    """Return a validated scenario, or the key of its fixed error."""
    if set(entry) != SCENARIO_KEYS:
        return "scenario-key"
    name, command = entry["name"], entry["command"]
    video, environment = entry["video"], entry["environment"]
    error = None
    if not isinstance(name, str) or not NAME.fullmatch(name):
        error = "name"
    elif any(name == other.name for other in seen):
        error = "unique"
    elif not _printable(command, COMMAND_LIMIT):
        error = "command"
    elif not packet.safe_path(video):
        error = "video"
    elif not _printable(environment, ENVIRONMENT_LIMIT):
        error = "environment"
    if error is not None:
        return error
    digest = hashlib.sha256(command.encode("utf-8")).hexdigest()
    return DemoScenario(name, command, video, environment, digest)


def _table_error(table: object) -> str | None:
    """Return the key of the first fixed error outside the scenarios."""
    if not isinstance(table, dict):
        return "table"
    if not set(table) <= DEMO_KEYS:
        return "key"
    if _bounded(table.get("retention_days"), RETENTION_DAYS) is None:
        return "retention"
    if _bounded(table.get("timeout_minutes"), TIMEOUT_MINUTES) is None:
        return "timeout"
    entries = table.get("scenarios")
    if (
        not isinstance(entries, list)
        or not 0 < len(entries) <= SCENARIO_LIMIT
        or not all(isinstance(entry, dict) for entry in entries)
    ):
        return "scenarios"
    return None


def demo_config(root: Path) -> DemoConfig:
    """Parse `[demo]` of the protected ballast.toml; never raises."""
    try:
        config = tomllib.loads((root / "ballast.toml").read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError):
        return DemoConfig()
    table = config.get("demo")
    if table is None:
        return DemoConfig()
    error = _table_error(table)
    if error is not None:
        return DemoConfig(configured=True, error=ERRORS[error])
    entries = table["scenarios"]
    scenarios: list[DemoScenario] = []
    for entry in entries:
        found = _scenario(entry, scenarios)
        if isinstance(found, str):
            return DemoConfig(configured=True, error=ERRORS[found])
        scenarios.append(found)
    return DemoConfig(
        configured=True,
        retention_days=_bounded(table.get("retention_days"), RETENTION_DAYS),
        timeout_minutes=_bounded(table.get("timeout_minutes"), TIMEOUT_MINUTES),
        scenarios=tuple(scenarios),
    )


def scenario(config: DemoConfig, name: str) -> DemoScenario | None:
    """Return the declared scenario called `name`, if any."""
    return next((s for s in config.scenarios if s.name == name), None)


# --- GitHub reads ---------------------------------------------------------------------


def _get(work: draft_pr._Checkpoint, path: str, *, missing: bool = False) -> Any:  # noqa: ANN401 - Parsed JSON.
    """Parse one `gh api` read; None for a 404 that `missing` allows."""
    result = work.api(path)
    if result.returncode:
        if missing and draft_pr._status(result) == 404:  # noqa: SLF001, PLR2004
            return None
        raise ReadError(draft_pr._classify(result))  # noqa: SLF001
    data = draft_pr._json(result)  # noqa: SLF001
    if not isinstance(data, dict):
        raise ReadError(GITHUB_ERROR)
    return data


@dataclass(frozen=True)
class _WorkflowRun:
    id: int
    title: str
    status: str
    conclusion: str | None
    head_sha: str


def _workflow_run(entry: object) -> _WorkflowRun | None:
    if not isinstance(entry, dict):
        return None
    number, title = entry.get("id"), entry.get("display_title")
    status, conclusion = entry.get("status"), entry.get("conclusion")
    head = entry.get("head_sha")
    if (
        type(number) is not int
        or number < 1
        or not isinstance(title, str)
        or not isinstance(status, str)
        or not (conclusion is None or isinstance(conclusion, str))
        or not isinstance(head, str)
    ):
        return None
    return _WorkflowRun(number, title, status, conclusion, head)


def _runs(
    work: draft_pr._Checkpoint, repo: str, branch: str, since: str, pages: int
) -> tuple[list[_WorkflowRun], bool]:
    """Demo runs on the feature branch since a date; False when the list is cut."""
    found: list[_WorkflowRun] = []
    for page in range(1, pages + 1):
        query = urllib.parse.urlencode(
            {
                "event": "workflow_dispatch",
                "branch": branch,
                "created": f">={since}",
                "per_page": PAGE_SIZE,
                "page": page,
            }
        )
        data = _get(work, f"repos/{repo}/actions/workflows/{WORKFLOW}/runs?{query}")
        entries = data.get("workflow_runs")
        if not isinstance(entries, list):
            raise ReadError(GITHUB_ERROR)
        found.extend(run for entry in entries if (run := _workflow_run(entry)))
        if len(entries) < PAGE_SIZE:
            return found, True
    return found, False


def _failed_step(work: draft_pr._Checkpoint, repo: str, run: int) -> str | None:
    """Name of the first failed step of a run's jobs, from structured fields only."""
    data = _get(work, f"repos/{repo}/actions/runs/{run}/jobs?per_page=100")
    jobs = data.get("jobs")
    if not isinstance(jobs, list):
        raise ReadError(GITHUB_ERROR)
    for job in jobs:
        steps = job.get("steps") if isinstance(job, dict) else None
        if not isinstance(steps, list):
            continue
        numbered = [
            step
            for step in steps
            if isinstance(step, dict) and type(step.get("number")) is int
        ]
        for step in sorted(numbered, key=lambda step: step["number"]):
            name = step.get("name")
            if step.get("conclusion") == "failure" and isinstance(name, str):
                return name
    return None


def _artifact(
    work: draft_pr._Checkpoint, repo: str, run: int, request_id: str
) -> tuple[int | None, bool]:
    """(ID, expired) of the request's artifact in its run; (None, False) if absent."""
    name = ARTIFACT.format(request=request_id)
    data = _get(work, f"repos/{repo}/actions/runs/{run}/artifacts?name={name}")
    entries = data.get("artifacts")
    if not isinstance(entries, list):
        raise ReadError(GITHUB_ERROR)
    for entry in entries:
        if not isinstance(entry, dict) or entry.get("name") != name:
            continue
        number = entry.get("id")
        if type(number) is int and number > 0:
            return number, entry.get("expired") is not False
    return None, False


# --- resolution (research R5, R6) -----------------------------------------------------


def _observed(event: dict[str, Any]) -> datetime:
    return datetime.fromisoformat(event["observed_at"]).astimezone(UTC)


def resolve(  # noqa: PLR0911, PLR0913 - The R6 order and inputs, explicit.
    work: draft_pr._Checkpoint,
    repo: str,
    event: dict[str, Any],
    runs: list[_WorkflowRun],
    *,
    complete: bool,
    now: datetime,
) -> DemoCapture:
    """Resolve one `demo_capture` event against the listed runs, in R6 order."""
    data = event["data"]
    request_id, commit = data["request"], data["commit"]
    capture = DemoCapture(data["scenario"], commit, IN_PROGRESS, "queued")
    title = TITLE.format(request=request_id)
    matches = [run for run in runs if run.title == title]
    if len(matches) > 1:
        return replace(capture, outcome=FAILED, reason="run-ambiguous")
    if not matches:
        if not complete:
            return replace(capture, outcome=FAILED, reason="run-list-truncated")
        if now - _observed(event) > RUN_NOT_FOUND:
            return replace(capture, outcome=FAILED, reason="run-not-found")
        return capture
    run = matches[0]
    capture = replace(capture, run_id=run.id)
    if run.head_sha != commit:
        return replace(capture, outcome=FAILED, reason="commit-mismatch")
    if run.status != "completed":
        return replace(capture, reason="running")
    if run.conclusion == "success":
        artifact, expired = _artifact(work, repo, run.id, request_id)
        if artifact is None:
            return replace(capture, outcome=MISSING, reason="artifact-absent")
        if expired:
            return replace(capture, outcome=MISSING, reason="expired")
        return replace(capture, outcome=CAPTURED, reason=None, artifact_id=artifact)
    fallback = (FAILED, CONCLUSIONS.get(run.conclusion or "", "job-failed"))
    step = _failed_step(work, repo, run.id) or ""
    outcome, reason = FAILED_STEPS.get(step, fallback)
    return replace(capture, outcome=outcome, reason=reason)


def _newest(events: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Return the newest `demo_capture` event per scenario, by sequence."""
    newest: dict[str, dict[str, Any]] = {}
    for event in sorted(events, key=lambda event: event["sequence"]):
        if event["kind"] == "demo_capture":
            newest[event["data"]["scenario"]] = event
    return newest


def collect(step: Any, head: str, events: list[dict[str, Any]]) -> DemoSection:  # noqa: ANN401 - packet._Step
    """Resolve each declared scenario's newest capture for the packet.

    A GitHub read failure raises ReadError; the packet step fails retryable.
    """
    run = step.run
    config = demo_config(run.root)
    section = DemoSection(step.repo, head, config)
    if not config.configured or config.error is not None:
        return section
    newest = _newest(events)
    if not newest:
        return section
    since = min(_observed(event) for event in newest.values()).date().isoformat()
    runs, complete = _runs(step.work, step.repo, run.published, since, PAGE_LIMIT)
    now = draft_pr._now()  # noqa: SLF001
    declared = {item.name: item for item in config.scenarios}
    captures = []
    for name, event in newest.items():
        if name not in declared:
            continue
        capture = resolve(step.work, step.repo, event, runs, complete=complete, now=now)
        changed = event["data"]["command_digest"] != declared[name].command_digest
        captures.append(
            replace(capture, stale=capture.commit != head, command_changed=changed)
        )
    removed = tuple(name for name in newest if name not in declared)
    return replace(section, captures=tuple(captures), removed=removed)


# --- rendering (contracts/packet-demo-section.md) ---------------------------------


def _job_link(repo: str, run: int | None) -> str:
    if type(run) is not int or run < 1:
        message = "invalid workflow run"
        raise ValueError(message)
    return f"{packet._repo(repo)}/actions/runs/{run}"  # noqa: SLF001


def _artifact_link(repo: str, run: int | None, artifact: int | None) -> str:
    if type(artifact) is not int or artifact < 1:
        message = "invalid artifact"
        raise ValueError(message)
    return f"{_job_link(repo, run)}/artifacts/{artifact}"


def _code(text: str) -> str:
    return "`" + packet.inert(text, COMMAND_LIMIT).replace("`", "") + "`"


def _state(capture: DemoCapture) -> str:
    return capture.outcome + (f" ({capture.reason})" if capture.reason else "")


def format_line(section: DemoSection, item: DemoScenario) -> str:
    """One scenario's packet line; `[video]` only for a captured, current commit."""
    label = f"- {packet.inert(item.name, 80)} ({packet.inert(item.environment, 80)})"
    reproduce = f"reproduce: {_code(item.command)}"
    capture = next((c for c in section.captures if c.scenario == item.name), None)
    if capture is None:
        return f"{label}: not yet requested · {reproduce}"
    commit, head = capture.commit[:12], section.head[:12]
    state = _state(capture)
    if capture.stale:
        state = f"stale ({state} at `{commit}`; head is `{head}`)"
    else:
        state += f" at `{commit}`"
    parts = [state]
    if capture.outcome == CAPTURED and not capture.stale:
        link = _artifact_link(section.repo, capture.run_id, capture.artifact_id)
        parts.append(f"[video]({link})")
    elif capture.run_id is not None:
        parts.append(f"[job]({_job_link(section.repo, capture.run_id)})")
    parts.append(reproduce)
    line = f"{label}: " + " · ".join(parts)
    if capture.command_changed:
        line += " (declared command changed since this capture)"
    return line


def lines(section: DemoSection | None, level: int) -> list[str]:
    """Render the packet's `### Demo captures` section at a size level."""
    heading = ["### Demo captures", ""]
    removed = section.removed if section is not None else ()
    if section is None or not section.config.configured:
        return [*heading, "Demo captures: not configured.", ""]
    config = section.config
    if config.error is not None:
        return [*heading, f"Demo captures: configuration invalid ({config.error}).", ""]
    if level >= SHORT_LEVEL:
        done = sum(c.outcome == CAPTURED and not c.stale for c in section.captures)
        count = f"{len(config.scenarios)} scenarios, {done} captured at head"
        return [*heading, f"Demo captures: {count}.", ""]
    items = [format_line(section, item) for item in config.scenarios]
    # A removed scenario never shows a working link (SC-002).
    items += [f"- {packet.inert(name, 80)}: no longer declared" for name in removed]
    return [*heading, INTRO, "", *items, ""]


# --- request (contracts/demo-command.md) ------------------------------------------


def format_outcome(outcome: DemoOutcome) -> str:
    """`Demo capture: <state>[ (<reason>)][ <scenario> at <commit12>][: <detail>]`."""
    line = f"Demo capture: {outcome.state}"
    if outcome.reason:
        line += f" ({outcome.reason})"
    if outcome.scenario and outcome.commit:
        line += f" {outcome.scenario} at {outcome.commit[:12]}"
    detail = outcome.remedy or outcome.link
    if detail:
        line += f": {detail}"
    return line


def event_data(
    item: DemoScenario, commit: str, request_id: str, pr_number: int
) -> dict[str, Any]:
    """Build the `demo_capture` ledger data: codes and IDs, never the command."""
    return {
        "scenario": item.name,
        "commit": commit,
        "request": request_id,
        "command_digest": item.command_digest,
        "pr_number": pr_number,
    }


class _Refused(Exception):  # noqa: N818 - Control flow, not an error.
    def __init__(self, outcome: DemoOutcome) -> None:
        super().__init__(outcome.state)
        self.outcome = outcome


class _Request:
    """One `ballast run demo` invocation, after run.py's own refusals (R9)."""

    def __init__(self, root: Path, run_id: str, name: str) -> None:
        self.root = root
        self.run_id = run_id
        self.name = name
        self.repo = "OWNER/NAME"
        self.draft: draft_pr.Outcome | None = None

    def stop(self, state: str, reason: str, detail: str = "") -> NoReturn:
        """End the request with this outcome; nothing more is dispatched."""
        template = REMEDIES.get((state, reason)) or draft_pr.REMEDIES.get(
            (state, reason)
        )
        remedy = None
        if template is not None:
            remedy = template.format(run=self.run_id, repo=self.repo, detail=detail)
        raise _Refused(DemoOutcome(state, reason, remedy=remedy, draft=self.draft))

    def contract(self) -> tuple[DemoConfig, DemoScenario]:
        config = demo_config(self.root)
        if not config.configured:
            self.stop("refused", "not-configured")
        if config.error is not None:
            self.stop("refused", "config-invalid", config.error)
        found = scenario(config, self.name)
        if found is None:
            names = ", ".join(item.name for item in config.scenarios)
            self.stop("refused", "unknown-scenario", names)
        return config, found

    def settle(self) -> tuple[draft_pr._Checkpoint, int]:
        """#17's checkpoint without creation; go on only for `reused`."""
        outcome, work = draft_pr.checkpoint_work(self.root, self.run_id, create=False)
        self.draft = outcome
        if work.run.owner and work.run.repo:
            self.repo = f"{work.run.owner}/{work.run.repo}"
        if outcome.state == "skipped" and outcome.reason is None:
            # A marker appeared since run.py checked: #17's own remedy.
            raise _Refused(DemoOutcome("refused", "untrusted", remedy=outcome.remedy))
        if outcome.state == "skipped":
            self.stop("refused", "no-draft-pr")
        if outcome.state == "failed-retryable":
            self.stop("failed-retryable", outcome.reason or "internal-error")
        if outcome.state != "reused" or outcome.pr_number is None:
            self.stop("refused", "pr-not-open")
        return work, outcome.pr_number

    def head(self, work: draft_pr._Checkpoint, number: int) -> str:
        pull = draft_pr.pull_head(work, number)
        if pull.cause is not None:
            raise ReadError(pull.cause)
        if pull.state != "open" or pull.head is None:
            self.stop("refused", "pr-not-open")
        return pull.head

    def check_workflow(self, work: draft_pr._Checkpoint, head: str) -> None:
        """Installed, active, and the same blob at head as on the default branch."""
        default = _get(work, f"repos/{self.repo}").get("default_branch")
        if not isinstance(default, str) or not default:
            raise ReadError(GITHUB_ERROR)
        path = f"repos/{self.repo}/actions/workflows/{WORKFLOW}"
        workflow = _get(work, path, missing=True)
        if workflow is None:
            self.stop("refused", "workflow-not-installed")
        if workflow.get("state") != "active":
            self.stop("refused", "workflow-disabled")
        blobs = []
        for ref in (head, default):
            path = f"repos/{self.repo}/contents/{WORKFLOW_PATH}?ref={_quote(ref)}"
            data = _get(work, path, missing=True)
            blob = data.get("sha") if data is not None else None
            blobs.append(blob if isinstance(blob, str) and blob else None)
        if blobs[1] is None:
            self.stop("refused", "workflow-not-installed")
        if blobs[0] != blobs[1]:
            self.stop("refused", "workflow-differs")

    def dispatch(
        self,
        work: draft_pr._Checkpoint,
        config: DemoConfig,
        item: DemoScenario,
        head: str,
    ) -> str:
        """Dispatch the workflow on the feature branch; return the request ID."""
        request_id = secrets.token_hex(8)
        branch = work.run.published
        if not branch or branch == work.run.base:
            # Never the default branch: PR-head code must not run under its ref.
            self.stop("failed-retryable", "internal-error")
        body = {
            "ref": branch,
            "inputs": {
                "request": request_id,
                "scenario": item.name,
                "commit": head,
                "command": item.command,
                "video": item.video,
                "timeout_minutes": str(config.timeout_minutes),
                "retention_days": str(config.retention_days),
            },
        }
        result = work.gh(
            "api",
            "--method",
            "POST",
            f"repos/{self.repo}/actions/workflows/{WORKFLOW}/dispatches",
            "--input",
            "-",
            stdin=json.dumps(body),
        )
        if result.returncode:
            raise ReadError(draft_pr._classify(result))  # noqa: SLF001
        return request_id

    def wait(self, work: draft_pr._Checkpoint, event: dict[str, Any]) -> DemoCapture:
        """Poll page 1 every 10 s for at most 120 s, until the run completes."""
        data = event["data"]
        capture = DemoCapture(data["scenario"], data["commit"], IN_PROGRESS, "queued")
        since = _observed(event).date().isoformat()
        title = TITLE.format(request=data["request"])
        started = _monotonic()
        while _monotonic() - started < WAIT_SECONDS:
            _sleep(POLL_SECONDS)
            runs, _ = _runs(work, self.repo, work.run.published, since, 1)
            if not any(run.title == title for run in runs):
                continue
            now = draft_pr._now()  # noqa: SLF001
            capture = resolve(work, self.repo, event, runs, complete=True, now=now)
            if capture.reason != "running":
                break
        return capture

    def execute(self, *, wait: bool) -> DemoOutcome:
        config, item = self.contract()
        work, number = self.settle()
        try:
            head = self.head(work, number)
            self.check_workflow(work, head)
            request_id = self.dispatch(work, config, item, head)
        except ReadError as error:
            self.stop("failed-retryable", error.cause)
        data = event_data(item, head, request_id, number)
        event = ledger.new_event(
            self.run_id, work.run.feature, "demo_capture", "runner", data
        )
        ledger.append(self.root, event)
        capture = DemoCapture(item.name, head, IN_PROGRESS, "queued")
        if wait:
            # A failed read leaves `queued`; the packet refresh reports it.
            with contextlib.suppress(ReadError):
                capture = self.wait(work, event)
        refresh = draft_pr.checkpoint(self.root, self.run_id, create=False)
        link = None
        if capture.outcome == CAPTURED:
            link = _artifact_link(self.repo, capture.run_id, capture.artifact_id)
        elif capture.run_id is not None:
            link = _job_link(self.repo, capture.run_id)
        return DemoOutcome(
            capture.outcome,
            capture.reason,
            scenario=item.name,
            commit=head,
            link=link,
            draft=self.draft,
            refresh=refresh,
        )


def _quote(ref: str) -> str:
    return urllib.parse.quote(ref, safe="")


def request(root: Path, run_id: str, name: str, *, wait: bool = True) -> DemoOutcome:
    """Dispatch one capture of a declared scenario for the run's open Draft PR.

    Refusals and GitHub failures dispatch nothing and write no event. A
    dispatched request returns the capture's state after the bounded wait.
    """
    try:
        return _Request(root, run_id, name).execute(wait=wait)
    except _Refused as refused:
        return refused.outcome
