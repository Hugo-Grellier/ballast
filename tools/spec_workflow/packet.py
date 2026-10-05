"""Publish a source-linked acceptance packet into the feature's Draft PR.

`draft_pr.checkpoint` calls `publish` after recording its own outcome, and
only for a `created` or `reused` PR (docs/adr/0006). The packet is a derived
summary, never an approval: it lists every acceptance criterion of the spec at
the PR's head commit with one evidence state, the run's risk, decisions,
open findings and checks, optional API and UI sections, and links to every
canonical source pinned to that commit.

- `collect` reads: the PR (head and base commits), the feature artifacts from
  the local object store at head, the run ledger, the operator's Autonomous
  records, GitHub check runs at head, and an optional OpenAPI document.
  Every command goes through the checkpoint's `git`/`gh` and `_command`,
  except `ledger.commit_tree`, which needs a private `GIT_INDEX_FILE` that
  `_command` strips: it runs ledger's resolved Git with filters, hooks and
  fsmonitor off.
- `render` is pure: the same sources give the same text apart from the
  `Generated:` line. Every value from an agent-writable source goes through
  `inert`; every link is built here from validated parts.
- `publish` replaces or appends the one marked section, only when its text
  changed, after re-reading the PR; it writes the complete packet to the run
  archive and returns one `PacketOutcome`.

A packet failure is one fixed outcome, reason and remedy. It never changes the
#17 outcome or the run's exit status, and the next checkpoint retries.
"""

from __future__ import annotations

import base64
import hashlib
import html
import json
import os
import re
import tempfile
import tomllib
import urllib.parse
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Any, NoReturn

import autonomy
import draft_pr
import ledger

if TYPE_CHECKING:
    from datetime import datetime
    from pathlib import Path

BEGIN = "<!-- ballast:acceptance-packet:begin -->"
END = "<!-- ballast:acceptance-packet:end -->"
BODY_LIMIT = 65536
MARGIN = 1024
FILE_LIMIT = 1024 * 1024
LIST_LIMIT = 50
OPERATION_LIMIT = 2000
UI_LIMIT = 50
REF_DEPTH = 5
PATH_LIMIT = 300
LEVELS = (1, 2, 3, 4)
VERIFIED, FAILED, NOT_RUN, STALE, MISSING = STATES = (
    "verified",
    "failed",
    "not run",
    "stale",
    "missing",
)
COUNT_KEYS = dict(zip(STATES, ledger.PACKET_COUNTS, strict=True))
PATH_SEGMENT = re.compile(r"[A-Za-z0-9._-]{1,100}")
TEST_NAME = re.compile(r"tests\.test_[A-Za-z0-9_.]+\.test_[A-Za-z0-9_]+")
FINDING_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}")
DEC_HEADING = re.compile(r"#{1,6}[ \t]+(DEC-[0-9]{4})\b(.*)")
METHODS = ("get", "put", "post", "delete", "options", "head", "patch", "trace")
BREAKING = (
    "operation removed",
    "parameter removed",
    "parameter now required",
    "request body now required",
    "request field removed",
    "request field now required",
)
TOKEN = re.compile(r"(?:gh[pousr]_|github_pat_)[A-Za-z0-9_]+")
AUTHORIZATION = re.compile(
    r"(?i)\b(?:authorization\s*:\s*(?:(?:bearer|token|basic)\s+)?|bearer\s+)\S+"
)
# C0 controls, zero-width and bidirectional formatting characters.
CONTROL = re.compile(r"[\x00-\x1f\x7f\u200b-\u200f\u202a-\u202e\u2060-\u2069\ufeff]")
MARKDOWN = re.compile(r"([\\`*_\[\]()#|!~])")
WWW = re.compile(r"(?i)(www)\.")
SUMMARY = (
    "Derived summary for review. The linked sources are authoritative; this "
    "packet is not an approval and records none."
)
API_NOTE = (
    "This classification is automatic and needs human review; it is not an approval."
)
REMEDIES: dict[tuple[str, str], str] = {
    ("pending", "no-pr"): "see the Draft PR line; the next run retries",
    ("pending", "pr-blocked"): "see the Draft PR line",
    ("pending", "head-not-local"): "fetch the feature branch, then resume",
    ("failed-retryable", "body-changed"): "none: the next run retries",
    ("failed-retryable", "section-unmanaged"): (
        "keep at most one acceptance-packet section in the PR body"
    ),
    ("failed-retryable", "source-unreadable"): (
        "commit a readable spec.md; the next run retries"
    ),
    ("failed-retryable", "manifest-malformed"): (
        "fix the manifest; ballast ledger check validates it"
    ),
    ("failed-retryable", "ledger-invalid"): "run ballast ledger report --run {run}",
    ("failed-retryable", "too-large"): (
        "shorten the PR description outside Ballast's sections"
    ),
    ("failed-retryable", "internal-error"): (
        "report it with the run ID; the next run retries"
    ),
}


# --- data ---------------------------------------------------------------------


@dataclass(frozen=True)
class TestEvidence:
    """One mapped test and its own result."""

    __test__ = False  # Not a unittest case.

    test: str
    result: str  # passed, failed, stale, not run
    belongs_to: tuple[str, str] | None = None  # (commit|spec|manifest|snapshot, hex)
    file: str | None = None
    sequence: int | None = None


@dataclass(frozen=True)
class UiResult:
    """A configured UI state's result at head."""

    name: str
    criteria: tuple[str, ...]
    result: str  # present, passed, failed, not run (in progress), not run, missing
    path: str | None = None
    run: int | None = None


@dataclass(frozen=True)
class Criterion:
    """One spec criterion with its evidence state."""

    id: str
    title: str
    line: int
    state: str
    reason: str | None = None
    tests: tuple[TestEvidence, ...] = ()
    ui: tuple[UiResult, ...] = ()


@dataclass(frozen=True)
class Manifest:
    """`acceptance-evidence.json` at head, schema shape checked only."""

    spec_digest: str
    criteria: dict[str, list[str]]
    digest: str


@dataclass(frozen=True)
class ProvisionalDecision:
    """A current agent-provisional decision of an Autonomous run."""

    id: str
    point: str
    summary: str
    line: int | None


@dataclass(frozen=True)
class HumanDecision:
    """A human decision as a structured record states it."""

    label: str
    source: str
    sequence: int | None = None


@dataclass(frozen=True)
class FeatureDecision:
    """A `DEC-NNNN` record in the feature's decisions.md."""

    id: str
    resolved: bool
    line: int


@dataclass(frozen=True)
class Finding:
    """An open review finding."""

    id: str
    severity: str
    disposition: str
    reason: str | None
    report: str | None  # repository path


@dataclass(frozen=True)
class RunCheck:
    """One `run-checks` command result, recorded before publication."""

    command: str
    exit: int
    seconds: float
    timed_out: bool


@dataclass(frozen=True)
class CheckRun:
    """One GitHub check run at the head commit."""

    id: int
    name: str
    status: str
    conclusion: str | None


@dataclass(frozen=True)
class LedgerCheck:
    """A suite-wide `verification` event of the ledger."""

    check_id: str
    status: str
    source: str
    sequence: int


@dataclass(frozen=True)
class UiState:
    """A `[[review.ui_states]]` entry."""

    name: str
    criteria: tuple[str, ...]
    path: str | None = None
    check: str | None = None


@dataclass(frozen=True)
class ReviewConfig:
    """The optional `[review]` table of the protected ballast.toml."""

    openapi: str | None = None
    ui_states: tuple[UiState, ...] | None = None
    api_error: str | None = None
    ui_error: str | None = None


@dataclass(frozen=True)
class ApiComparison:
    """The OpenAPI document at base and head, compared."""

    state: str  # no API change, changed, added in this PR, removed..., could not...
    reason: str | None = None
    added: tuple[tuple[str, str], ...] = ()
    removed: tuple[tuple[str, str], ...] = ()
    changed: tuple[tuple[str, str, tuple[str, ...], bool], ...] = ()


@dataclass(frozen=True)
class Sources:
    """Everything `render` needs, read at one checkpoint."""

    repo: str
    run_id: str
    feature: str
    mode: str
    head: str
    base: str
    feature_version: str
    spec_version: str
    generated_at: datetime
    risk: str
    risk_source: str
    files: frozenset[str]
    too_large: frozenset[str] = frozenset()
    criteria: tuple[Criterion, ...] = ()
    unknown: tuple[str, ...] = ()
    decisions: tuple[ProvisionalDecision, ...] = ()
    human: tuple[HumanDecision, ...] = ()
    feature_decisions: tuple[FeatureDecision, ...] = ()
    findings: tuple[Finding, ...] = ()
    run_checks: tuple[RunCheck, ...] | None = None
    check_runs: tuple[CheckRun, ...] = ()
    ledger_checks: tuple[LedgerCheck, ...] = ()
    config: ReviewConfig = field(default_factory=ReviewConfig)
    api: ApiComparison | None = None
    ui: tuple[UiResult, ...] = ()


@dataclass(frozen=True)
class Packet:
    """A rendered packet and what the ledger records about it."""

    text: str
    full_text: str
    masked_digest: str
    shortened: bool
    counts: dict[str, int]


@dataclass(frozen=True)
class PacketOutcome:
    """One packet step result; every field is fixed wording or validated data."""

    state: str
    reason: str | None = None
    remedy: str | None = None
    detail: str | None = None
    pr_number: int | None = None
    head: str | None = None
    base: str | None = None
    feature_version: str | None = None
    packet_digest: str | None = None
    shortened: bool | None = None
    counts: dict[str, int] | None = None


class _Fail(Exception):  # noqa: N818 - Control flow, not an error.
    def __init__(self, outcome: PacketOutcome) -> None:
        super().__init__(outcome.state)
        self.outcome = outcome


class MalformedError(ValueError):
    """A source is not in the shape its schema requires."""


# --- inert text and links ---------------------------------------------------------


def inert(text: object, limit: int = 200) -> str:
    """Render agent-written text as data: one line, no markup, link or token.

    It cannot end or forge a marked section, form a link, autolink or mention,
    break a table cell, or read as a human approval.
    """
    text = AUTHORIZATION.sub("[redacted]", TOKEN.sub("[redacted]", str(text)))
    text = " ".join(CONTROL.sub(" ", text).split())
    if len(text) > limit:
        text = text[: limit - 1] + "…"
    text = autonomy.HUMAN_APPROVAL.sub(
        lambda match: match.group(0)[0] + "\u200b" + match.group(0)[1:], text
    )
    text = html.escape(text, quote=False)
    # `$` as an entity: GitHub renders `$...$` as LaTeX, which can restyle text.
    text = MARKDOWN.sub(r"\\\1", text).replace("://", ":\u200b//").replace("$", "&#36;")
    return autonomy.MENTION.sub("@\u200b", WWW.sub("\\1\u200b.", text))


def safe_path(path: object) -> bool:
    """Tell whether a path is relative, `/`-separated and of plain segments."""
    return (
        isinstance(path, str)
        and 0 < len(path) <= PATH_LIMIT
        and all(
            PATH_SEGMENT.fullmatch(part) and part not in {".", ".."}
            for part in path.split("/")
        )
    )


def _oid(value: object) -> str:
    if not isinstance(value, str) or not ledger.OID.fullmatch(value):
        message = "invalid commit"
        raise ValueError(message)
    return value


def _path(path: str) -> str:
    if not safe_path(path):
        message = "unsafe repository path"
        raise ValueError(message)
    return path


def _repo(repo: str) -> str:
    owner, _, name = repo.partition("/")
    if not all(
        draft_pr.NAME.fullmatch(part) and part not in {".", ".."}
        for part in (owner, name)
    ):
        message = "invalid repository"
        raise ValueError(message)
    return f"https://github.com/{repo}"


def _blob(repo: str, head: str, path: str) -> str:
    return f"{_repo(repo)}/blob/{_oid(head)}/{_path(path)}"


def _line(repo: str, head: str, path: str, number: int) -> str:
    if type(number) is not int or number < 1:
        message = "invalid line"
        raise ValueError(message)
    return f"{_blob(repo, head, path)}?plain=1#L{number}"


def _compare(repo: str, base: str, head: str) -> str:
    return f"{_repo(repo)}/compare/{_oid(base)}...{_oid(head)}"


def _run_link(repo: str, run: int) -> str:
    if type(run) is not int or run < 1:
        message = "invalid check run"
        raise ValueError(message)
    return f"{_repo(repo)}/runs/{run}"


def _checks(repo: str, head: str) -> str:
    return f"{_repo(repo)}/commit/{_oid(head)}/checks"


def _mask(text: str) -> str:
    return "\n".join(
        line
        for line in text.replace("\r\n", "\n").split("\n")
        if not line.startswith("- Generated: ")
    )


def _digest(text: str) -> str:
    return hashlib.sha256(_mask(text).encode("utf-8")).hexdigest()


# --- outcomes -------------------------------------------------------------------


def make_outcome(
    state: str,
    reason: str | None = None,
    *,
    run: Any = None,  # noqa: ANN401 - draft_pr._Run
    **values: Any,  # noqa: ANN401
) -> PacketOutcome:
    """Build an outcome with its fixed remedy (R17), filled from validated IDs."""
    template = REMEDIES.get((state, reason or ""))
    if template is None:
        template = draft_pr.REMEDIES.get((state, reason))
    remedy = None
    if template is not None:
        fill = {"run": "RUN_ID", "repo": "OWNER/NAME"}
        if run is not None:
            fill = {"run": run.run_id, "repo": f"{run.owner}/{run.repo}"}
        remedy = template.format(**fill)
    return PacketOutcome(state, reason, remedy=remedy, **values)


def format_line(outcome: PacketOutcome) -> str:
    """Print `Acceptance packet: <state>[ (<reason>)][ #<pr> head <12>][: <remedy>]`."""
    line = f"Acceptance packet: {outcome.state}"
    if outcome.reason:
        line += f" ({outcome.reason})"
    if outcome.pr_number is not None and outcome.head:
        line += f" #{outcome.pr_number} head {outcome.head[:12]}"
    if outcome.remedy:
        line += f": {outcome.remedy}"
    if outcome.detail:
        line += f" ({outcome.detail})"
    return line


def event_data(outcome: PacketOutcome) -> dict[str, Any]:
    """Return the `acceptance_packet` ledger data: codes, IDs and counts only."""
    data: dict[str, Any] = {"outcome": outcome.state}
    for key in (
        "reason",
        "pr_number",
        "head",
        "base",
        "feature_version",
        "packet_digest",
        "shortened",
    ):
        value = getattr(outcome, key)
        if value is not None:
            data[key] = value
    data.update(outcome.counts or {})
    return data


# --- collect --------------------------------------------------------------------


def review_config(root: Path, spec_ids: set[str] | None = None) -> ReviewConfig:
    """Parse `[review]`; any problem is a fixed reason, never a stop."""
    try:
        config = tomllib.loads((root / "ballast.toml").read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError):
        return ReviewConfig()
    review = config.get("review")
    if review is None:
        return ReviewConfig()
    if not isinstance(review, dict):
        reason = "review is not a table"
        return ReviewConfig(api_error=reason, ui_error=reason)
    openapi = review.get("openapi")
    api_error = None
    if openapi is not None and not safe_path(openapi):
        openapi, api_error = None, "openapi is not a safe repository path"
    states, ui_error = _ui_states(review.get("ui_states"), spec_ids)
    return ReviewConfig(openapi, states, api_error, ui_error)


def _ui_states(  # noqa: C901, PLR0911 - One fixed reason per rule.
    value: object, spec_ids: set[str] | None
) -> tuple[tuple[UiState, ...] | None, str | None]:
    if value is None:
        return None, None
    if not isinstance(value, list) or not all(isinstance(v, dict) for v in value):
        return None, "ui_states is not a list of tables"
    if len(value) > UI_LIMIT:
        return None, "more than 50 UI states"
    states = []
    for entry in value:
        name, criteria = entry.get("name"), entry.get("criteria")
        path, check = entry.get("path"), entry.get("check")
        if set(entry) - {"name", "criteria", "path", "check"}:
            return None, "UI state has an unknown key"
        if not isinstance(name, str) or not 1 <= len(name) <= 80:  # noqa: PLR2004
            return None, "UI state name must be 1-80 characters"
        if (
            not isinstance(criteria, list)
            or not criteria
            or not all(isinstance(c, str) and ledger.AC.fullmatch(c) for c in criteria)
        ):
            return None, "UI state criteria must be AC-NNN IDs"
        if (path is None) == (check is None):
            return None, "UI state needs exactly one of path or check"
        if path is not None and not safe_path(path):
            return None, "UI state path is not a safe repository path"
        if check is not None and (
            not isinstance(check, str)
            or not 1 <= len(check) <= 100  # noqa: PLR2004
            or not check.isprintable()
        ):
            return None, "UI state check must be 1-100 characters"
        if spec_ids is not None and not set(criteria) <= spec_ids:
            return None, "UI state names a criterion the spec does not define"
        states.append(UiState(name, tuple(criteria), path, check))
    return tuple(states), None


def _manifest(text: str | None, raw: bytes | None) -> Manifest | None:
    """Shape only: a stale digest or a different AC set is not malformed."""
    if text is None or raw is None:
        return None
    try:
        data = json.loads(text)
    except ValueError as error:
        raise MalformedError(str(error)) from None
    if (
        not isinstance(data, dict)
        or set(data) != {"schema_version", "spec_digest", "criteria"}
        or data["schema_version"] != 1
        or type(data["schema_version"]) is not int
        or not isinstance(data["spec_digest"], str)
        or not ledger.SHA.fullmatch(data["spec_digest"])
        or not isinstance(data["criteria"], dict)
    ):
        raise MalformedError
    for ac_id, tests in data["criteria"].items():
        if (
            not ledger.AC.fullmatch(ac_id)
            or not isinstance(tests, list)
            or not tests
            or not all(isinstance(t, str) and TEST_NAME.fullmatch(t) for t in tests)
        ):
            raise MalformedError
    return Manifest(
        data["spec_digest"], data["criteria"], hashlib.sha256(raw).hexdigest()
    )


def evaluate(  # noqa: PLR0913, PLR0917 - The R4 inputs, explicit.
    criteria: list[tuple[str, str, int]],
    manifest: Manifest | None,
    spec_version: str,
    head: str,
    head_fingerprint: str,
    events: list[dict[str, Any]],
    file_of: Any,  # noqa: ANN401 - Callable[[str], str | None]
) -> tuple[list[Criterion], list[str]]:
    """Each criterion's evidence state (research R4) and unknown manifest IDs."""
    checks: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for event in events:
        data = event["data"]
        if (
            event["kind"] == "verification"
            and event["source"] == "operator-attested"
            and data.get("ac_id")
        ):
            checks.setdefault((data["ac_id"], data["check_id"]), []).append(event)
    result = []
    for ac_id, title, line in criteria:
        if manifest is None:
            result.append(
                Criterion(ac_id, title, line, MISSING, "no acceptance-evidence.json")
            )
            continue
        tests = manifest.criteria.get(ac_id)
        if not tests:
            result.append(
                Criterion(
                    ac_id,
                    title,
                    line,
                    MISSING,
                    "no test named in acceptance-evidence.json",
                )
            )
            continue
        if manifest.spec_digest != spec_version:
            belongs = ("spec", manifest.spec_digest[:12])
            evidence = tuple(TestEvidence(t, STALE, belongs, file_of(t)) for t in tests)
            result.append(
                Criterion(ac_id, title, line, STALE, _belongs(belongs), evidence)
            )
            continue
        evidence = tuple(
            _test(
                test,
                checks.get((ac_id, test), []),
                (head_fingerprint, spec_version, manifest.digest),
                head,
                file_of(test),
            )
            for test in tests
        )
        result.append(_criterion(ac_id, title, line, evidence))
    spec_ids = {ac_id for ac_id, _, _ in criteria}
    unknown = sorted(set(manifest.criteria) - spec_ids) if manifest else []
    return result, unknown


def _belongs(belongs: tuple[str, str]) -> str:
    return f"evidence belongs to {belongs[0]} {belongs[1]}"


def _test(
    test: str,
    events: list[dict[str, Any]],
    binding: tuple[str, str, str],
    head: str,
    file: str | None,
) -> TestEvidence:
    bound = [
        e
        for e in events
        if (
            e["data"].get("snapshot"),
            e["data"].get("spec_digest"),
            e["data"].get("manifest_digest"),
        )
        == binding
    ]
    if bound:
        latest = bound[-1]
        result = "passed" if latest["data"]["status"] == "passed" else FAILED
        return TestEvidence(test, result, None, file, latest["sequence"])
    if not events:
        return TestEvidence(test, NOT_RUN, None, file)
    latest = events[-1]
    data = latest["data"]
    if data.get("commit") and data["commit"] != head:
        belongs = ("commit", data["commit"][:12])
    elif data.get("spec_digest") != binding[1]:
        belongs = ("spec", str(data.get("spec_digest") or "none")[:12])
    elif data.get("manifest_digest") != binding[2]:
        belongs = ("manifest", str(data.get("manifest_digest") or "none")[:12])
    else:
        belongs = ("snapshot", str(data.get("snapshot") or "none")[:12])
    return TestEvidence(test, STALE, belongs, file, latest["sequence"])


def _criterion(
    ac_id: str, title: str, line: int, tests: tuple[TestEvidence, ...]
) -> Criterion:
    results = [t.result for t in tests]
    if all(r == "passed" for r in results):
        return Criterion(ac_id, title, line, VERIFIED, None, tests)
    if FAILED in results:
        count = results.count(FAILED)
        reason = f"{count} of {len(tests)} tests failed at head"
        return Criterion(ac_id, title, line, FAILED, reason, tests)
    if STALE in results:
        belongs = next(t.belongs_to for t in tests if t.result == STALE)
        return Criterion(ac_id, title, line, STALE, _belongs(belongs), tests)
    return Criterion(ac_id, title, line, NOT_RUN, "no check recorded at head", tests)


def _feature_decisions(text: str | None) -> list[FeatureDecision]:
    """`DEC-NNNN` headings; resolved once any heading says Resolution."""
    if text is None:
        return []
    first: dict[str, int] = {}
    resolved: set[str] = set()
    for number, line in enumerate(text.splitlines(), 1):
        match = DEC_HEADING.fullmatch(line.rstrip())
        if match is None:
            continue
        first.setdefault(match.group(1), number)
        if "resolution" in match.group(2).lower():
            resolved.add(match.group(1))
    return [FeatureDecision(d, d in resolved, n) for d, n in first.items()]


def _record_line(text: str | None, decision: str) -> int | None:
    if text is None:
        return None
    for number, line in enumerate(text.splitlines(), 1):
        if line.startswith(f"| {decision} |"):
            return number
    return None


class _Step:
    """One packet attempt on an open Ballast Draft PR."""

    def __init__(self, work: draft_pr._Checkpoint, number: int) -> None:
        self.work = work
        self.run = work.run
        self.number = number
        self.repo = f"{self.run.owner}/{self.run.repo}"
        self.head: str | None = None
        self.base: str | None = None

    def fail(self, state: str, reason: str) -> NoReturn:
        raise _Fail(
            make_outcome(
                state,
                reason,
                run=self.run,
                pr_number=self.number,
                head=self.head,
                base=self.base,
            )
        )

    def gh_failed(self, result: draft_pr.Result) -> NoReturn:
        self.fail("failed-retryable", draft_pr._classify(result))  # noqa: SLF001

    # --- reads ------------------------------------------------------------

    def read_pr(self) -> tuple[str, str, str]:
        """Body, head and base of the PR, re-validated as #17 does."""
        result = self.work.api(f"repos/{self.repo}/pulls/{self.number}")
        if result.returncode:
            self.gh_failed(result)
        data = draft_pr._json(result)  # noqa: SLF001
        if not isinstance(data, dict):
            self.fail("failed-retryable", "github-error")
        pr = draft_pr._pull_request(data, self.run)  # noqa: SLF001
        head, base = (
            data[key].get("sha") if isinstance(data.get(key), dict) else None
            for key in ("head", "base")
        )
        if (
            pr is None
            or pr.number != self.number
            or pr.state != "open"
            or not isinstance(head, str)
            or not isinstance(base, str)
            or not ledger.OID.fullmatch(head)
            or not ledger.OID.fullmatch(base)
        ):
            self.fail("failed-retryable", "github-error")
        return pr.body, head, base

    def ok(self, *args: str) -> str | None:
        result = self.work.git(*args)
        return None if result.returncode else result.stdout

    def exists(self, commit: str, path: str) -> bool:
        return self.ok("cat-file", "-e", f"{commit}:{_path(path)}") is not None

    def blob(self, path: str) -> tuple[str | None, bytes | None, bool]:
        """Text and bytes of a file at head; the flag says it was too large."""
        spec = f"{self.head}:{_path(path)}"
        size = self.ok("cat-file", "-s", spec)
        if size is None or not size.strip().isdigit():
            return None, None, False
        if int(size) > FILE_LIMIT:
            return None, None, True
        try:
            text = self.ok("cat-file", "blob", spec)
        except ValueError:  # Not UTF-8.
            return None, None, False
        if text is None:
            return None, None, False
        # ponytail: the seam decodes text, so a CRLF file's digest differs from
        # the ledger's byte digest and reads stale; commit LF specs.
        return text, text.encode("utf-8"), False

    def collect(self, head: str, base: str) -> Sources:  # noqa: C901, PLR0912, PLR0915 - One read per source.
        """Read every source for this head and base (all I/O is here)."""
        run, root, feature = self.run, self.run.root, self.run.feature
        if self.ok("cat-file", "-e", f"{head}^{{commit}}") is None:
            self.fail("pending", "head-not-local")
        version = (self.ok("rev-parse", "--verify", f"{head}:{feature}") or "").strip()
        if not ledger.OID.fullmatch(version):
            self.fail("failed-retryable", "source-unreadable")
        listed = self.ok(
            "ls-tree", "-r", "-z", "--name-only", head, "--", f"{feature}/"
        )
        if listed is None:
            self.fail("failed-retryable", "source-unreadable")
        prefix = f"{feature}/"
        files = frozenset(
            name.removeprefix(prefix)
            for name in listed.split("\0")
            if name.startswith(prefix)
        )
        too_large: set[str] = set()

        def read(name: str) -> tuple[str | None, bytes | None]:
            if name not in files:
                return None, None
            text, raw, large = self.blob(f"{prefix}{name}")
            if large:
                too_large.add(name)
            return text, raw

        spec_text, spec_raw = read("spec.md")
        if spec_text is None or spec_raw is None:
            self.fail("failed-retryable", "source-unreadable")
        spec_version = hashlib.sha256(spec_raw).hexdigest()
        criteria = ledger.spec_criteria(spec_text)
        try:
            manifest = _manifest(*read("acceptance-evidence.json"))
        except MalformedError:
            self.fail("failed-retryable", "manifest-malformed")
        decisions_text, _ = read("decisions.md")
        record_text, _ = read("autonomous/record.md")
        fingerprint = ledger.commit_tree(root, head)
        try:
            events, problems = ledger.read(root, run.run_id)
        except (ledger.LedgerError, OSError):
            problems = ["unreadable"]
        if problems:
            self.fail("failed-retryable", "ledger-invalid")

        test_files: dict[str, str | None] = {}

        def file_of(test: str) -> str | None:
            if test not in test_files:
                parts = test.split(".")
                test_files[test] = next(
                    (
                        path
                        for size in range(len(parts), 0, -1)
                        if safe_path(path := "/".join(parts[:size]) + ".py")
                        and self.exists(head, path)
                    ),
                    None,
                )
            return test_files[test]

        evaluated, unknown = evaluate(
            criteria, manifest, spec_version, head, fingerprint, events, file_of
        )
        record = autonomy.find_run(root, run.run_id)
        decisions: list[ProvisionalDecision] = []
        human: list[HumanDecision] = []
        findings: list[Finding] = []
        run_checks = None
        if record is not None:
            mode = autonomy.effective_mode(record)
            risk = (record.get("risk") or {}).get("level")
            risk_source = "run record"
            entries = autonomy.read_decisions(root, run.run_id)
            for entry in autonomy.current_decisions(entries):
                decisions.append(
                    ProvisionalDecision(
                        str(entry.get("id")),
                        str(entry.get("point")),
                        str(entry.get("summary", "")),
                        _record_line(record_text, str(entry.get("id"))),
                    )
                )
                review = entry.get("review") or {}
                for item in review.get("findings") or []:
                    if item.get("disposition") in {"open", "accepted-provisionally"}:
                        report = review.get("report")
                        findings.append(
                            Finding(
                                f"{entry.get('id')} {item.get('id')}",
                                str(item.get("severity")),
                                str(item.get("disposition")),
                                item.get("reason"),
                                report if safe_path(report) else None,
                            )
                        )
            human.extend(
                HumanDecision(f"{e.get('id')} {e.get('kind')}", "operator record")
                for e in autonomy.read_human_decisions(root, run.run_id)
            )
            recorded = autonomy.read_checks(root, run.run_id)
            if recorded is not None:
                run_checks = tuple(
                    RunCheck(
                        str(c.get("command", "")),
                        int(c.get("exit", -1)),
                        float(c.get("seconds", 0)),
                        bool(c.get("timed_out")),
                    )
                    for c in recorded
                    if isinstance(c, dict)
                )
        else:
            mode = "human-gated"
            risk = next(
                (
                    html.unescape(line).removeprefix("Risk:").strip()
                    for line in run.scope
                    if line.startswith("Risk:")
                ),
                None,
            )
            risk_source = "intake comment"
        if not risk:
            risk, risk_source = "not recorded", "no record"
        latest: dict[tuple[str, str], dict[str, Any]] = {}
        ledger_checks = []
        for event in events:
            data = event["data"]
            if event["kind"] == "gate" and data["choice"] in {"approve", "reject"}:
                human.append(
                    HumanDecision(
                        f"gate {data['step_id']}: {data['choice']}",
                        "observed by runner",
                        event["sequence"],
                    )
                )
            elif event["kind"] == "human_action":
                target = data.get("gate_id") or data.get("decision_id") or ""
                human.append(
                    HumanDecision(
                        f"{data['action']} {target}".strip(),
                        event["source"],
                        event["sequence"],
                    )
                )
            elif event["kind"] == "finding":
                latest[data["review_id"], data["finding_id"]] = event
            elif event["kind"] == "verification" and not data.get("ac_id"):
                ledger_checks.append(
                    LedgerCheck(
                        data["check_id"],
                        data["status"],
                        event["source"],
                        event["sequence"],
                    )
                )
        for (review_id, finding_id), event in latest.items():
            if event["data"]["resolution"] != "open":
                continue
            report = f"{prefix}reviews/{review_id}.md"
            if f"reviews/{review_id}.md" not in files or not safe_path(report):
                report = None
            findings.append(
                Finding(finding_id, event["data"]["severity"], "open", None, report)
            )
        check_runs = self.check_runs(head)
        spec_ids = {ac_id for ac_id, _, _ in criteria}
        config = review_config(root, spec_ids)
        api = None
        if config.openapi is not None:
            api = self.compare_api(config.openapi, base, head)
        ui: tuple[UiResult, ...] = ()
        if config.ui_states is not None:
            ui = tuple(
                self.ui_result(state, head, check_runs) for state in config.ui_states
            )
            evaluated = [
                replace(c, ui=tuple(u for u in ui if c.id in u.criteria))
                for c in evaluated
            ]
        return Sources(
            repo=self.repo,
            run_id=run.run_id,
            feature=feature,
            mode=mode,
            head=head,
            base=base,
            feature_version=version,
            spec_version=spec_version,
            generated_at=draft_pr._now(),  # noqa: SLF001
            risk=risk,
            risk_source=risk_source,
            files=files,
            too_large=frozenset(too_large),
            criteria=tuple(evaluated),
            unknown=tuple(unknown),
            decisions=tuple(decisions),
            human=tuple(human),
            feature_decisions=tuple(_feature_decisions(decisions_text)),
            findings=tuple(findings),
            run_checks=run_checks,
            check_runs=check_runs,
            ledger_checks=tuple(ledger_checks),
            config=config,
            api=api,
            ui=ui,
        )

    def check_runs(self, head: str) -> tuple[CheckRun, ...]:
        """GitHub check runs at head (R8); links are built from the ID only."""
        result = self.work.api(
            f"repos/{self.repo}/commits/{head}/check-runs?per_page=100", paginate=True
        )
        if result.returncode:
            self.gh_failed(result)
        pages = draft_pr._json(result)  # noqa: SLF001
        if not isinstance(pages, list) or not all(isinstance(p, dict) for p in pages):
            self.fail("failed-retryable", "github-error")
        runs = []
        for page in pages:
            entries = page.get("check_runs")
            if not isinstance(entries, list):
                self.fail("failed-retryable", "github-error")
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                number = entry.get("id")
                name, status = entry.get("name"), entry.get("status")
                conclusion = entry.get("conclusion")
                if (
                    type(number) is not int
                    or number < 1
                    or not isinstance(name, str)
                    or not isinstance(status, str)
                    or not (conclusion is None or isinstance(conclusion, str))
                ):
                    continue
                runs.append(CheckRun(number, name, status, conclusion))
        return tuple(sorted(runs, key=lambda r: r.id))

    def ui_result(
        self, state: UiState, head: str, runs: tuple[CheckRun, ...]
    ) -> UiResult:
        """Return a configured UI state's result at head (R11)."""
        if state.path is not None:
            found = self.exists(head, state.path)
            return UiResult(
                state.name,
                state.criteria,
                "present" if found else MISSING,
                state.path if found else None,
            )
        named = [r for r in runs if r.name == state.check]
        if not named:
            return UiResult(state.name, state.criteria, MISSING)
        latest = named[-1]
        if latest.status != "completed":
            result = "not run (in progress)"
        elif latest.conclusion == "success":
            result = "passed"
        elif latest.conclusion in {"neutral", "skipped"}:
            result = NOT_RUN
        else:
            result = FAILED
        return UiResult(state.name, state.criteria, result, None, latest.id)

    # --- OpenAPI (R10) ----------------------------------------------------

    def document(  # noqa: PLR0911 - One fixed reason per failure.
        self, path: str, commit: str
    ) -> tuple[dict | None, str | None]:
        """Return the OpenAPI document at a commit, or None and a reason."""
        result = self.work.api(
            f"repos/{self.repo}/contents/{urllib.parse.quote(path, safe='/')}"
            f"?ref={commit}"
        )
        if result.returncode:
            absent = draft_pr._status(result) == 404  # noqa: SLF001, PLR2004
            return None, "absent" if absent else "github-error"
        data = draft_pr._json(result)  # noqa: SLF001
        if not isinstance(data, dict) or data.get("type", "file") != "file":
            return None, "unreadable"
        content = data.get("content")
        if data.get("encoding") == "none" or not isinstance(content, str):
            return None, "too large"
        try:
            raw = base64.b64decode(content)
        except ValueError:
            return None, "unreadable"
        if len(raw) > FILE_LIMIT:
            return None, "too large"
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            return None, "unreadable"
        try:
            document = json.loads(text)
        except ValueError:
            return None, "not JSON"
        if (
            not isinstance(document, dict)
            or "openapi" not in document
            or not isinstance(document.get("paths"), dict)
        ):
            return None, "not an OpenAPI document"
        if len(_operations(document)) > OPERATION_LIMIT:
            return None, "too large"
        return document, None

    def compare_api(self, path: str, base: str, head: str) -> ApiComparison:
        old, old_reason = self.document(path, base)
        new, new_reason = self.document(path, head)
        for reason in (new_reason, old_reason):
            if reason not in {None, "absent"}:
                return ApiComparison("could not compare", reason)
        if old is None and new is None:
            return ApiComparison("could not compare", "unreadable")
        if old is None:
            return ApiComparison("added in this PR")
        if new is None:
            return ApiComparison("removed in this PR")
        return compare_documents(old, new)


def _operations(document: dict) -> dict[tuple[str, str], tuple[dict, dict]]:
    found = {}
    for path, item in sorted(document.get("paths", {}).items()):
        if not isinstance(item, dict):
            continue
        for method in METHODS:
            if isinstance(item.get(method), dict):
                found[method.upper(), str(path)] = (item[method], item)
    return found


def _resolve(document: dict, node: object) -> dict:
    """Follow local `$ref`s, at most REF_DEPTH, never round a cycle."""
    seen: list[str] = []
    while isinstance(node, dict) and isinstance(node.get("$ref"), str):
        ref = node["$ref"]
        if not ref.startswith("#/") or ref in seen or len(seen) >= REF_DEPTH:
            return {}
        seen.append(ref)
        node = document
        for part in ref[2:].split("/"):
            key = part.replace("~1", "/").replace("~0", "~")
            node = node.get(key) if isinstance(node, dict) else None
    return node if isinstance(node, dict) else {}


def _parameters(document: dict, operation: dict, item: dict) -> dict[tuple, bool]:
    found: dict[tuple, bool] = {}
    for source in (item.get("parameters"), operation.get("parameters")):
        for raw in source if isinstance(source, list) else []:
            parameter = _resolve(document, raw)
            name, where = parameter.get("name"), parameter.get("in")
            if isinstance(name, str) and isinstance(where, str):
                found[name, where] = parameter.get("required") is True
    return found


def _request(document: dict, operation: dict) -> tuple[bool, set[str], set[str]]:
    body = _resolve(document, operation.get("requestBody"))
    content = body.get("content") if isinstance(body.get("content"), dict) else {}
    media = "application/json" if "application/json" in content else None
    if media is None and content:
        media = min(content)
    schema = {}
    if media is not None and isinstance(content[media], dict):
        schema = _resolve(document, content[media].get("schema"))
    properties = schema.get("properties")
    required = schema.get("required")
    return (
        body.get("required") is True,
        set(properties) if isinstance(properties, dict) else set(),
        {r for r in required if isinstance(r, str)}
        if isinstance(required, list)
        else set(),
    )


def _causes(
    old: dict, new: dict, before: tuple[dict, dict], after: tuple[dict, dict]
) -> tuple[str, ...]:
    (old_op, old_item), (new_op, new_item) = before, after
    causes = set()
    old_params = _parameters(old, old_op, old_item)
    new_params = _parameters(new, new_op, new_item)
    if set(old_params) - set(new_params):
        causes.add("parameter removed")
    if any(
        required and not old_params.get(name, False)
        for name, required in new_params.items()
    ):
        causes.add("parameter now required")
    old_body, old_fields, old_required = _request(old, old_op)
    new_body, new_fields, new_required = _request(new, new_op)
    if new_body and not old_body:
        causes.add("request body now required")
    if old_fields - new_fields:
        causes.add("request field removed")
    if new_required - old_required:
        causes.add("request field now required")
    return tuple(cause for cause in BREAKING if cause in causes)


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def compare_documents(old: dict, new: dict) -> ApiComparison:
    """Operations added, removed and changed, with potentially breaking causes."""
    before, after = _operations(old), _operations(new)
    added = tuple(sorted(set(after) - set(before)))
    removed = tuple(sorted(set(before) - set(after)))
    changed = []
    for key in sorted(set(before) & set(after)):
        (old_op, old_item), (new_op, new_item) = before[key], after[key]
        causes = _causes(old, new, before[key], after[key])
        # ponytail: a response change made only inside a `$ref`'d component
        # is not seen; request-side changes are resolved through `_causes`.
        if not causes and _canonical([old_op, old_item.get("parameters")]) == (
            _canonical([new_op, new_item.get("parameters")])
        ):
            continue
        responses = _canonical(old_op.get("responses")) != _canonical(
            new_op.get("responses")
        )
        changed.append((*key, causes, responses))
    if not (added or removed or changed):
        return ApiComparison("no API change")
    return ApiComparison("changed", None, added, removed, tuple(changed))


# --- render ---------------------------------------------------------------------


def counts(sources: Sources) -> dict[str, int]:
    """Criterion counts per state, keyed as the ledger records them."""
    return {
        COUNT_KEYS[state]: sum(c.state == state for c in sources.criteria)
        for state in STATES
    }


def _ledger_ref(sources: Sources, sequence: int) -> str:
    return f"ledger event {sequence} of run {sources.run_id}"


def _test_ref(sources: Sources, test: TestEvidence) -> str:
    if test.file is not None:
        text = f"[`{test.test}`]({_blob(sources.repo, sources.head, test.file)})"
    else:
        text = f"`{test.test}` (file not found at head)"
    if test.sequence is not None:
        text += f" ({_ledger_ref(sources, test.sequence)})"
    return text


def _ui_text(sources: Sources, result: UiResult) -> str:
    if result.path is not None:
        return f"[present at head]({_blob(sources.repo, sources.head, result.path)})"
    if result.run is not None:
        return f"[{result.result}]({_run_link(sources.repo, result.run)})"
    return result.result


def _detail(sources: Sources, criterion: Criterion, level: int) -> str:
    tests = criterion.tests
    if criterion.state == VERIFIED:
        ci = (
            f"[check runs]({_checks(sources.repo, sources.head)})"
            if sources.check_runs
            else "no CI result at head"
        )
        detail = (
            f"{len(tests)}/{len(tests)} tests passed at head: "
            + ", ".join(_test_ref(sources, t) for t in tests)
            + f" · CI at head: {ci}"
        )
    elif level >= 4 or not tests:  # noqa: PLR2004
        detail = str(criterion.reason)
    else:
        lines = []
        for test in tests:
            line = f"{_test_ref(sources, test)}: {test.result}"
            if test.belongs_to is not None:
                line += f" ({test.belongs_to[0]} `{test.belongs_to[1]}`)"
            lines.append(line)
        detail = f"{criterion.reason}: " + "; ".join(lines)
    for result in criterion.ui:
        detail += f" · UI {inert(result.name, 80)}: {_ui_text(sources, result)}"
    return detail


def _criteria_lines(sources: Sources, level: int) -> list[str]:
    spec = f"{sources.feature}/spec.md"
    lines = ["### Criteria", ""]
    if not sources.criteria:
        link = _blob(sources.repo, sources.head, spec)
        return [*lines, f"No acceptance criteria found in [spec.md]({link}).", ""]
    rows = list(sources.criteria)
    if level >= 2:  # noqa: PLR2004
        verified = [c for c in rows if c.state == VERIFIED]
        rows = [c for c in rows if c.state != VERIFIED]
        if verified:
            ids = ", ".join(
                f"[{c.id}]({_line(sources.repo, sources.head, spec, c.line)})"
                for c in verified
            )
            lines += [f"Verified at head: {ids}.", ""]
    if rows:
        lines += ["| ID | Criterion | Evidence | Detail |", "| --- | --- | --- | --- |"]
        lines += [
            f"| [{c.id}]({_line(sources.repo, sources.head, spec, c.line)}) | "
            f"{inert(c.title, 120)} | {c.state} | {_detail(sources, c, level)} |"
            for c in rows
        ]
        lines.append("")
    if sources.unknown:
        manifest = _blob(
            sources.repo, sources.head, f"{sources.feature}/acceptance-evidence.json"
        )
        lines += [
            (
                f"Evidence for unknown criteria: {', '.join(sources.unknown)} (in "
                f"[acceptance-evidence.json]({manifest}), not in the spec)"
            ),
            "",
        ]
    lines += [
        (
            "To record evidence for one criterion at the current commit: "
            f"`ballast ledger check {sources.run_id} AC-NNN TEST`."
        ),
        "",
    ]
    return lines


def _record_link(sources: Sources, line: int | None) -> str:
    path = f"{sources.feature}/autonomous/record.md"
    if "autonomous/record.md" not in sources.files:
        return "record not present"
    if line is None:
        return f"[record]({_blob(sources.repo, sources.head, path)})"
    return f"[record]({_line(sources.repo, sources.head, path, line)})"


def _decision_lines(sources: Sources) -> list[str]:
    lines = [
        f"- {d.id} ({inert(d.point, 40)}, agent-provisional): "
        f"{inert(d.summary)} — {_record_link(sources, d.line)}"
        for d in sources.decisions
    ]
    for decision in sources.human:
        label = f"- {inert(decision.label, 120)} (human; {decision.source})"
        if decision.sequence is not None:
            label += f" — {_ledger_ref(sources, decision.sequence)}"
        else:
            label += f" — operator record of run {sources.run_id}"
        lines.append(label)
    path = f"{sources.feature}/decisions.md"
    for decision in sources.feature_decisions:
        state = "resolved" if decision.resolved else "unresolved"
        link = _line(sources.repo, sources.head, path, decision.line)
        lines.append(f"- {decision.id} ({state}; see record) — [decisions.md]({link})")
    return ["### Decisions", "", *(lines or ["None (0)."]), ""]


def _finding_lines(sources: Sources) -> list[str]:
    lines = []
    reviews = f"{sources.feature}/reviews"
    for finding in sources.findings:
        line = (
            f"- {inert(finding.id, 80)} ({inert(finding.severity, 20)}, "
            f"{finding.disposition})"
        )
        if finding.reason:
            line += f": {inert(finding.reason)}"
        if finding.report is not None:
            line += f" — [report]({_blob(sources.repo, sources.head, finding.report)})"
        elif any(f.startswith("reviews/") for f in sources.files):
            line += f" — [reviews]({_blob(sources.repo, sources.head, reviews)})"
        else:
            line += " — report not present"
        lines.append(line)
    return ["### Open findings", "", *(lines or ["None (0)."]), ""]


def _check_lines(sources: Sources) -> list[str]:
    lines = ["### Checks", ""]
    if sources.run_checks is None:
        lines.append("- run-checks: not run")
    record = (
        f" — {_record_link(sources, None)}"
        if "autonomous/record.md" in sources.files
        else ""
    )
    lines.extend(
        "- run-checks (runner, before publication, not bound to the head "
        f"commit): {inert(check.command)} exited {check.exit} in "
        f"{check.seconds:.1f}s" + (" (timed out)" if check.timed_out else "") + record
        for check in sources.run_checks or ()
    )
    if sources.check_runs:
        runs = []
        for run in sources.check_runs:
            status = (
                f"completed/{inert(run.conclusion or 'none', 30)}"
                if run.status == "completed"
                else inert(run.status.replace("_", " "), 30)
            )
            runs.append(
                f"[{inert(run.name, 100)}]({_run_link(sources.repo, run.id)}) {status}"
            )
        lines.append("- GitHub check runs at head: " + " · ".join(runs))
    else:
        lines.append("- GitHub check runs at head: none reported")
    lines += [
        f"- {inert(check.check_id, 128)}: {check.status} ({check.source}) — "
        f"{_ledger_ref(sources, check.sequence)}"
        for check in sources.ledger_checks
    ]
    return [*lines, ""]


def _capped(sources: Sources, items: list[str], archive: bool) -> list[str]:  # noqa: FBT001
    if archive or len(items) <= LIST_LIMIT:
        return items
    more = len(items) - LIST_LIMIT
    return [
        *items[:LIST_LIMIT],
        f"- … {more} more in the complete packet ({_archive_path(sources)})",
    ]


def _api_lines(sources: Sources, level: int, archive: bool) -> list[str]:  # noqa: FBT001
    config, api = sources.config, sources.api
    lines = ["### API changes", ""]
    if config.api_error is not None:
        return [*lines, f"API: configuration invalid ({config.api_error}).", ""]
    if api is None or config.openapi is None:
        return [*lines, "API: not configured.", ""]
    where = f"`{config.openapi}`"
    if api.state != "changed":
        state = api.state + (f" ({api.reason})" if api.reason else "")
        return [*lines, f"API ({where}): {state}.", ""]
    breaking = len(api.removed) + sum(1 for c in api.changed if c[2])
    lines += [
        (
            f"API ({where}, base → head): {len(api.added)} added, {len(api.removed)} "
            f"removed, {len(api.changed)} changed; {breaking} potentially breaking."
        ),
        API_NOTE,
    ]
    short = level >= 3  # noqa: PLR2004
    added = [] if short else [f"- added: {m} {inert(p)}" for m, p in api.added]
    removed = [
        f"- removed: {m} {inert(p)} — potentially breaking (operation removed)"
        for m, p in api.removed
    ]
    changed = []
    for method, path, causes, responses in api.changed:
        if causes:
            note = f" — potentially breaking ({', '.join(causes)})"
        elif short:
            continue
        else:
            note = " — response changed" if responses else ""
        changed.append(f"- changed: {method} {inert(path)}{note}")
    lines += [
        *_capped(sources, added, archive),
        *_capped(sources, removed, archive),
        *_capped(sources, changed, archive),
    ]
    return [*lines, ""]


def _ui_lines(sources: Sources, level: int, archive: bool) -> list[str]:  # noqa: FBT001
    config = sources.config
    lines = ["### UI states", ""]
    if config.ui_error is not None:
        return [*lines, f"UI states: configuration invalid ({config.ui_error}).", ""]
    if config.ui_states is None:
        return [*lines, "UI states: not configured.", ""]
    if level >= 3:  # noqa: PLR2004
        done = sum(u.result in {"present", "passed"} for u in sources.ui)
        return [*lines, f"UI states: {len(sources.ui)}, {done} with a result.", ""]
    items = [
        f"- {inert(u.name, 80)} ({', '.join(u.criteria)}): {_ui_text(sources, u)}"
        for u in sources.ui
    ]
    return [*lines, *(_capped(sources, items, archive) or ["None (0)."]), ""]


def _archive_path(sources: Sources) -> str:
    return f"speckit-runs/{sources.run_id}/acceptance-packet.md in the operator's clone"


def _source(sources: Sources, name: str, label: str) -> str:
    if name in sources.too_large:
        return f"{label}: not present (too large)"
    if name not in sources.files:
        return f"{label}: not present"
    link = _blob(sources.repo, sources.head, f"{sources.feature}/{name}")
    return f"{label}: [{name}]({link})"


def _source_lines(sources: Sources) -> list[str]:
    reviews = sorted(
        name
        for name in sources.files
        if name.startswith("reviews/")
        and name.endswith(".md")
        and safe_path(f"{sources.feature}/{name}")
    )
    review_links = ", ".join(
        f"[{name.removeprefix('reviews/')}]"
        f"({_blob(sources.repo, sources.head, f'{sources.feature}/{name}')})"
        for name in reviews
    )
    diff = _compare(sources.repo, sources.base, sources.head)
    return [
        "### Sources",
        "",
        "- "
        + " · ".join(
            _source(sources, name, label)
            for name, label in (
                ("intent.md", "intent"),
                ("spec.md", "spec"),
                ("plan.md", "plan"),
                ("tasks.md", "tasks"),
            )
        ),
        "- " + _source(sources, "decisions.md", "decisions"),
        "- " + _source(sources, "acceptance-evidence.json", "acceptance evidence"),
        "- reviews: " + (review_links or "not present"),
        "- " + _source(sources, "autonomous/record.md", "run record"),
        f"- diff: [{sources.base[:12]}...{sources.head[:12]}]({diff})",
    ]


def render(sources: Sources, level: int = 1, *, archive: bool = False) -> str:
    """Render the packet section at a size level (R14).

    Deterministic apart from the `Generated:` line.

    `archive` keeps every list line, for the run archive's complete copy.
    """
    total = counts(sources)
    generated = sources.generated_at.strftime("%Y-%m-%dT%H:%M:%SZ")
    header = [
        BEGIN,
        "## Acceptance packet",
        "",
        SUMMARY,
        "",
    ]
    if level > 1:
        header += [
            (
                "Shortened to fit the PR description. Complete packet: "
                f"{_archive_path(sources)}."
            ),
            "",
        ]
    diff = _compare(sources.repo, sources.base, sources.head)
    header += [
        (
            f"- Feature: `{sources.feature}/` version `{sources.feature_version[:12]}` "
            f"(spec `sha256:{sources.spec_version[:12]}`)"
        ),
        f"- Base: `{sources.base[:12]}` · Head: `{sources.head[:12]}` · [diff]({diff})",
        f"- Run: `{sources.run_id}` ({sources.mode})",
        f"- Generated: {generated}",
        f"- Risk: {inert(sources.risk, 80)} ({sources.risk_source})",
        (
            f"- Criteria: {len(sources.criteria)} · verified {total['verified']} · "
            f"failed {total['failed']} · not run {total['not_run']} · stale "
            f"{total['stale']} · missing {total['missing']}"
        ),
        (
            f"- Open findings: {len(sources.findings)} · Provisional decisions: "
            f"{len(sources.decisions)} · Human decisions: {len(sources.human)}"
        ),
        "",
    ]
    lines = [
        *header,
        *_criteria_lines(sources, level),
        *_decision_lines(sources),
        *_finding_lines(sources),
        *_check_lines(sources),
        *_api_lines(sources, level, archive),
        *_ui_lines(sources, level, archive),
        *_source_lines(sources),
        END,
    ]
    text = "\n".join(lines)
    if (
        text.count(BEGIN) != 1
        or text.count(END) != 1
        or autonomy.HUMAN_APPROVAL.search(text)
        or autonomy.WORKFLOW_MARKER.search(text)
    ):
        message = "packet text failed its marker or approval guard"
        raise ValueError(message)
    return text


# --- publish --------------------------------------------------------------------


def _write_archive(root: Path, run_id: str, text: str) -> None:
    """Keep the complete packet in the run archive, atomically, mode 0600."""
    directory = ledger.archive_dir(root, run_id)
    directory.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=directory, prefix=".packet-", delete=False
    ) as handle:
        handle.write(text + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.chmod(handle.name, 0o600)  # noqa: PTH101
    os.replace(handle.name, directory / "acceptance-packet.md")  # noqa: PTH105


def _span(body: str) -> tuple[int, int] | None:
    """Return the one packet section's span, or None; raise when unmanaged."""
    begins, ends = body.count(BEGIN), body.count(END)
    if begins == ends == 0:
        return None
    start, end = body.find(BEGIN), body.find(END)
    if begins != 1 or ends != 1 or end < start:
        raise MalformedError
    return start, end + len(END)


def build(step: _Step, body: str, head: str, base: str) -> tuple[Sources, Packet]:
    """Collect, archive the complete packet, and fit the section to the body."""
    sources = step.collect(head, base)
    full = render(sources, 1, archive=True)
    _write_archive(step.run.root, step.run.run_id, full)
    try:
        span = _span(body)
    except MalformedError:
        step.fail("failed-retryable", "section-unmanaged")
    outside = len(body) - (span[1] - span[0] if span else 0)
    budget = BODY_LIMIT - outside - MARGIN - (2 if span is None else 0)
    for level in LEVELS:
        text = render(sources, level)
        if len(text) <= budget:
            # Level 1 is shortened too when a list was capped.
            return sources, Packet(
                text, full, _digest(text), text != full, counts(sources)
            )
    return step.fail("failed-retryable", "too-large")


def _publish(work: draft_pr._Checkpoint, number: int) -> PacketOutcome:
    step = _Step(work, number)
    body, head, base = step.read_pr()
    step.head, step.base = head, base
    sources, packet = build(step, body, head, base)
    span = _span(body)
    published = {
        "run": step.run,
        "pr_number": number,
        "head": head,
        "base": base,
        "feature_version": sources.feature_version,
        "packet_digest": packet.masked_digest,
        "shortened": packet.shortened,
        "counts": packet.counts,
    }
    if span is not None and _mask(body[span[0] : span[1]]) == _mask(packet.text):
        return make_outcome("unchanged", **published)
    if span is None:
        updated = draft_pr._after(body, packet.text)  # noqa: SLF001
        kept = updated.startswith(body) and updated.endswith(packet.text)
    else:
        start, end = span
        updated = body[:start] + packet.text + body[end:]
        kept = (
            updated[:start] == body[:start]
            and updated[start + len(packet.text) :] == body[end:]
        )
    if not kept or updated.count(BEGIN) != 1 or updated.count(END) != 1:
        step.fail("failed-retryable", "internal-error")
    # GitHub has no conditional update for a PR body (#17 DEC-0007).
    current, _, _ = step.read_pr()
    if current != body:
        step.fail("failed-retryable", "body-changed")
    result = work.gh(
        "pr",
        "edit",
        str(number),
        "--repo",
        step.repo,
        "--body-file",
        "-",
        stdin=updated,
    )
    if result.returncode:
        step.gh_failed(result)
    return make_outcome("published" if span is None else "updated", **published)


def publish(work: draft_pr._Checkpoint, outcome: draft_pr.Outcome) -> PacketOutcome:
    """Publish the packet into the open Draft PR of a #17 `created`/`reused` outcome."""
    if outcome.state not in {"created", "reused"} or outcome.pr_number is None:
        reason = "pr-blocked" if outcome.state.startswith("blocked-") else "no-pr"
        return make_outcome("pending", reason, run=work.run)
    try:
        return _publish(work, outcome.pr_number)
    except _Fail as failure:
        return failure.outcome
