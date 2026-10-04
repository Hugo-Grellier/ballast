"""Make one Draft PR show an issue-linked feature run, and reuse it afterwards.

`run.py` imports this module at startup, before any agent step, and calls
`checkpoint` once after archiving and importing the run. The checkpoint is the
only place Ballast uses GitHub authority (docs/adr/0003):

- it refuses to act while `BALLAST_TAMPERED` or the launcher's `in-progress`
  marker exists;
- it runs only `git` and the operator's `gh`, each resolved outside every Git
  working tree and temp root and called by absolute path with a fixed list
  argv, no shell; `gh` starts outside the checkout;
- Git state is agent-writable, so the repository comes from the protected
  `ballast.toml` and the branch from the pin recorded at `ballast run start`;
  names from Git appear only shell-quoted in remedies;
- it never pushes, never changes readiness, never merges, closes or reopens;
- `gh` output is parsed, never printed or stored; every result is one fixed
  outcome, reason and remedy, printed as one line and recorded in the ledger.

Nothing here can change the workflow's exit status: `run.py` catches anything
that escapes.
"""

from __future__ import annotations

import base64
import fcntl
import json
import os
import re
import shlex
import stat
import subprocess
import tempfile
import time
import tomllib
import urllib.parse
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, NoReturn

import ledger
from artifacts import FEATURE_PATTERN, RUN_ID_PATTERN
from launcher import IN_PROGRESS, TAMPER_MARKER, state_dir

MARK_BEGIN = "<!-- ballast:draft-pr:begin -->"
MARK_END = "<!-- ballast:draft-pr:end -->"
INTAKE_MARK = "<!-- ballast-intake:"
# Withheld from the workflow engine and every agent step by run.py.
TOKEN_VARIABLES = (
    "GH_TOKEN",
    "GITHUB_TOKEN",
    "GH_ENTERPRISE_TOKEN",
    "GITHUB_ENTERPRISE_TOKEN",
)
GH_ENV = {
    "GH_PROMPT_DISABLED": "1",
    "GH_NO_UPDATE_NOTIFIER": "1",
    "GH_PAGER": "cat",
    "NO_COLOR": "1",
}
TIMEOUT = 30
LOCK_WAIT = 60
LOCK_NAME = "ballast-pr.lock"
TITLE_LIMIT = 256
SCOPE_LIMIT = 500
SCOPE_FIELDS = ("Main outcome:", "Risk:", "Scope gate:")
SCOPE_AUTHORS = frozenset({"OWNER", "MEMBER", "COLLABORATOR"})
COMPARE_FILE_CAP = 300  # GitHub lists at most 300 files, on the first page only.
NAME = re.compile(r"[A-Za-z0-9._-]{1,100}")
ISSUE = re.compile(r"specs/([1-9][0-9]{0,8})-")
HTTP_STATUS = re.compile(r"HTTP ([0-9]{3})")
GITHUB_REMOTE = re.compile(
    r"(?:https://(?:[^@/\s]+@)?github\.com/"
    r"|git@github\.com:"
    r"|ssh://git@github\.com(?::22)?/)"
    r"(?P<owner>[^/\s]+)/(?P<repo>[^/\s]+?)(?:\.git)?/?"
)
EXIT_UNAUTHENTICATED = 4
GIT_LOCATION = frozenset(
    {"GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR", "GIT_INDEX_FILE"}
)
GIT_OVERRIDES = (("core.fsmonitor", "false"), ("core.hooksPath", os.devnull))

REASONS = ledger.PR_REASONS
REMEDIES: dict[tuple[str, str | None], str] = {
    ("pending", "no-branch"): "check out the feature branch, then resume",
    ("pending", "not-published"): (
        "publish the branch, e.g. git push -u {remote} {branch}"
    ),
    ("pending", "on-base-branch"): "run the feature on its own branch",
    ("pending", "no-meaningful-change"): (
        "none: a Draft PR opens once implementation changes are pushed"
    ),
    ("pending", "diff-unclassified"): "open the PR by hand; Ballast will adopt it",
    ("reused", "section-unmanaged"): "keep one Ballast section in the PR body",
    ("reused", "body-changed"): (
        "none: the PR body changed during the check; the next run refreshes the section"
    ),
    ("failed-retryable", "gh-missing"): (
        "install the GitHub CLI; ballast doctor checks it"
    ),
    ("failed-retryable", "gh-unauthenticated"): "run gh auth login",
    ("failed-retryable", "gh-forbidden"): (
        "grant your GitHub account write access to {repo}"
    ),
    ("failed-retryable", "github-unreachable"): (
        "check the network; the next run retries"
    ),
    ("failed-retryable", "github-error"): (
        "the next run retries; check GitHub status, or upgrade gh to 2.48 or "
        "later, if it persists"
    ),
    ("failed-retryable", "lock-busy"): (
        "another checkpoint is running; the next run retries"
    ),
    ("failed-retryable", "internal-error"): (
        "report it with the run ID; the next run retries"
    ),
    ("failed-retryable", "gh-untrusted"): (
        "gh not found outside working trees: install it in a directory outside "
        "any Git working tree and put that directory on PATH"
    ),
    ("failed-retryable", "git-untrusted"): (
        "git not found outside working trees: put a system git on PATH ahead of "
        "any checkout directory"
    ),
    ("blocked-ambiguous", "several-open"): "close all but one of the listed PRs",
    ("blocked-ambiguous", "base-mismatch"): (
        "PR #{number} targets {actual}, expected {expected}: change its base on "
        "GitHub, or close it"
    ),
    ("blocked-ambiguous", "create-unverified"): (
        "check the listed PR on GitHub: its base, head or draft state is not what "
        "Ballast requested"
    ),
    ("blocked-closed", "closed"): (
        "reopen the PR, or open a new one by hand from this branch; Ballast will "
        "adopt it"
    ),
    ("blocked-closed", "merged"): (
        "reopen the PR, or open a new one by hand from this branch; Ballast will "
        "adopt it"
    ),
    ("blocked-unlinked", "no-issue-number"): (
        "name the feature directory specs/<issue>-<slug>/"
    ),
    ("blocked-unlinked", "issue-not-found"): (
        "create the Issue, or fix the number in the feature directory"
    ),
    ("blocked-unlinked", "not-github"): "none: Draft PRs need a GitHub upstream",
    ("blocked-unlinked", "branch-unpinned"): (
        "start a new run with ballast run start on the feature branch"
    ),
    ("blocked-unlinked", "branch-mismatch"): (
        "check out {branch}, the branch this run started on, with its upstream, "
        "then resume"
    ),
    ("blocked-unlinked", "no-repository"): (
        'declare [github] repository = "OWNER/NAME" in ballast.toml, then run '
        "ballast trust"
    ),
    ("blocked-unlinked", "repository-mismatch"): (
        "the branch's upstream is not {repo}, the repository pinned in "
        "ballast.toml: push the branch there, or fix the pin and run ballast trust"
    ),
}


@dataclass(frozen=True)
class Outcome:
    """One checkpoint result; every field is fixed wording or validated data."""

    state: str
    reason: str | None = None
    issue: int | None = None
    pr_number: int | None = None
    pr_url: str | None = None
    addresses: tuple[str, ...] = ()
    remedy: str | None = None
    matches: int | None = None
    detail: str | None = None


@dataclass(frozen=True)
class Result:
    """What one external command returned; never printed or stored."""

    returncode: int
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False


@dataclass(frozen=True)
class _PullRequest:
    number: int
    url: str
    state: str
    draft: bool
    base: str
    body: str
    closed_at: str


@dataclass
class _Run:
    """Identity resolved so far; read by the recorder even after a failure."""

    root: Path
    run_id: str
    feature: str | None = None
    issue: int | None = None
    git: str = ""
    gh: str = ""
    remote: str = ""
    published: str = ""
    owner: str = ""
    repo: str = ""
    base: str = ""
    title: str = ""
    scope: list[str] = field(default_factory=list)


class _Stop(Exception):  # noqa: N818 - Control flow, not an error.
    def __init__(self, outcome: Outcome) -> None:
        super().__init__(outcome.state)
        self.outcome = outcome


class LockUnavailableError(OSError):
    """The PR lock is a link or not a regular file."""


def _command(
    argv: list[str], *, stdin: str | None = None, cwd: Path, root: Path | None = None
) -> Result:
    """Run one fixed command: list argv, no shell, bounded, output kept local.

    `root` is the checkout, when `cwd` is not. Its PATH entries are dropped,
    Git stops searching for a repository above `cwd`, and the repository
    settings that run commands (fsmonitor, hooks) are overridden.
    """
    env = {
        **{k: v for k, v in os.environ.items() if k not in GIT_LOCATION},
        **GH_ENV,
        "PATH": _child_path(root or cwd),
        "GIT_CEILING_DIRECTORIES": str(cwd.resolve().parent),
        "GIT_CONFIG_COUNT": str(len(GIT_OVERRIDES)),
    }
    for index, (key, value) in enumerate(GIT_OVERRIDES):
        env[f"GIT_CONFIG_KEY_{index}"] = key
        env[f"GIT_CONFIG_VALUE_{index}"] = value
    try:
        result = subprocess.run(  # noqa: S603 - Absolute program, fixed argv.
            argv,
            cwd=cwd,
            env=env,
            input=stdin,
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return Result(-1, timed_out=True)
    except OSError:
        return Result(-1)
    return Result(result.returncode, result.stdout, result.stderr)


def _path_entries() -> list[str]:
    return os.environ.get("PATH", "").split(os.pathsep)


def _child_path(root: Path) -> str:
    """PATH for gh and git: gh runs git itself, so drop checkout entries too."""
    excluded = (root.resolve(), *ledger.agent_temp_roots())
    return os.pathsep.join(ledger.trusted_entries(_path_entries(), excluded))


def _pin_path(root: Path, run_id: str) -> Path | None:
    """Return the pin's path, or None when an agent could write it.

    That is state under the checkout or a temp root, e.g. XDG_STATE_HOME=/tmp/x.
    """
    path = state_dir(root) / "draft-pr" / f"{run_id}.json"
    resolved = path.resolve()
    writable = (root.resolve(), *ledger.agent_temp_roots())
    if any(resolved.is_relative_to(base) for base in writable):
        return None
    return path


def pin_branch(root: Path, run_id: str) -> str | None:
    """Record the run's branch when the operator starts it.

    HEAD lives in agent-writable Git state; every later checkpoint must still
    be on this branch, published under the same name (DEC-0006, DEC-0010).
    """
    path = _pin_path(root, run_id) if RUN_ID_PATTERN.fullmatch(run_id) else None
    if path is None:
        return None
    git, _ = _resolve("git", root)
    if git is None:
        return None
    head = _command([git, "symbolic-ref", "--quiet", "--short", "HEAD"], cwd=root)
    branch = head.stdout.strip()
    if head.returncode or not branch or branch.startswith("-"):
        return None
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.write_text(json.dumps({"branch": branch}), encoding="utf-8")
    return branch


def _branch_pin(root: Path, run_id: str) -> str | None:
    path = _pin_path(root, run_id)
    if path is None:
        return None
    try:
        pin = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    branch = pin.get("branch") if isinstance(pin, dict) else None
    return branch if isinstance(branch, str) and branch else None


def _pinned_repository(root: Path) -> tuple[str, str] | None:
    """Return `[github] repository` from the protected ballast.toml.

    The upstream remote lives in agent-writable `.git/config`; this pin is
    what keeps an agent from steering the operator's credentials elsewhere.
    """
    try:
        config = tomllib.loads((root / "ballast.toml").read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError):
        return None
    github = config.get("github")
    value = github.get("repository") if isinstance(github, dict) else None
    if not isinstance(value, str):
        return None
    owner, _, repo = value.partition("/")
    if not all(
        NAME.fullmatch(part) and part not in {".", ".."} for part in (owner, repo)
    ):
        return None
    return owner, repo


def _now() -> datetime:
    return datetime.now(UTC)


def _untrusted_marker(root: Path) -> str | None:
    if os.path.lexists(root / TAMPER_MARKER):
        return TAMPER_MARKER
    if os.path.lexists(state_dir(root) / IN_PROGRESS):
        return IN_PROGRESS
    return None


def _resolve(name: str, root: Path) -> tuple[str | None, bool]:
    excluded = (root.resolve(), *ledger.agent_temp_roots())
    return ledger.resolve_program(name, _path_entries(), excluded)


def _outcome(state: str, reason: str | None = None, **values: Any) -> Outcome:  # noqa: ANN401
    """Build an outcome with its fixed remedy, formatted from validated values."""
    fill = values.pop("fill", {})
    template = REMEDIES.get((state, reason))
    # Names come from agent-writable Git state; a remedy may be pasted.
    quoted = {key: shlex.quote(str(value)) for key, value in fill.items()}
    remedy = template.format(**quoted) if template else None
    return Outcome(state, reason, remedy=remedy, **values)


def _status(result: Result) -> int | None:
    match = HTTP_STATUS.search(result.stderr)
    return int(match.group(1)) if match else None


def _classify(result: Result, *, repository: bool = False) -> str:
    """Map a failed `gh` call to a fixed cause without keeping its output."""
    if result.timed_out:
        return "github-unreachable"
    if result.returncode == EXIT_UNAUTHENTICATED:
        return "gh-unauthenticated"
    status = _status(result)
    if status == 401:  # noqa: PLR2004
        return "gh-unauthenticated"
    if status == 403 or (status == 404 and repository):  # noqa: PLR2004
        return "gh-forbidden"
    if status is None and "unknown flag" not in result.stderr:
        return "github-unreachable"
    # Any other status, or a gh older than 2.48 refusing --slurp.
    return "github-error"


def _quote(name: str) -> str:
    return urllib.parse.quote(name, safe="")


def _json(result: Result) -> Any:  # noqa: ANN401
    try:
        return json.loads(result.stdout)
    except ValueError:
        return None


def format_line(outcome: Outcome) -> str:
    """`Draft PR: <state>[ (<reason>)][ #<number> <url>][: <remedy>]`."""
    line = f"Draft PR: {outcome.state}"
    if outcome.reason:
        line += f" ({outcome.reason})"
    if outcome.addresses:
        line += " " + " ".join(outcome.addresses)
    elif outcome.pr_number is not None and outcome.pr_url:
        line += f" #{outcome.pr_number} {outcome.pr_url}"
    if outcome.remedy:
        line += f": {outcome.remedy}"
    if outcome.detail:
        line += f" ({outcome.detail})"
    return line


def _escape(text: str) -> str:
    return text.replace("<", "&lt;").replace(">", "&gt;").replace("@", "&#64;")


def _after(text: str, addition: str) -> str:
    """Text, a blank line, then addition; every byte of text is kept."""
    if not text:
        return addition
    return text + ("\n" if text.endswith("\n") else "\n\n") + addition


def _section(run: _Run, checked_at: datetime) -> str:
    lines = [
        MARK_BEGIN,
        "## Ballast",
        "",
        f"Related to #{run.issue}",
        "",
        f"- Feature: `{run.feature}/`",
        f"- Run: `{run.run_id}`",
        f"- Last checkpoint: {checked_at.strftime('%Y-%m-%dT%H:%M:%SZ')}",
    ]
    if run.scope:
        lines.append("- Scope:")
        lines.extend(f"  - {line}" for line in run.scope)
    else:
        lines.append("- Scope: no intake scope comment")
    lines.append(MARK_END)
    return "\n".join(lines)


class _Checkpoint:
    def __init__(self, root: Path, run_id: str) -> None:
        self.run = _Run(root, run_id)

    # --- commands ---------------------------------------------------------

    def git(self, *args: str) -> Result:
        return _command([self.run.git, *args], cwd=self.run.root)

    def gh(self, *args: str, stdin: str | None = None) -> Result:
        # gh runs git itself; from an empty directory it never reads the
        # agent-writable .git/config. Every call names --repo explicitly.
        with tempfile.TemporaryDirectory(prefix="ballast-gh-") as away:
            return _command(
                [self.run.gh, *args], stdin=stdin, cwd=Path(away), root=self.run.root
            )

    def api(self, path: str, *, paginate: bool = False) -> Result:
        flags = ("--paginate", "--slurp") if paginate else ()
        return self.gh("api", *flags, path)

    def stop(self, state: str, reason: str | None = None, **values: Any) -> NoReturn:  # noqa: ANN401
        """End the checkpoint with this outcome."""
        raise _Stop(_outcome(state, reason, issue=self.run.issue, **values))

    def failed(self, result: Result, *, repository: bool = False) -> NoReturn:
        """End the checkpoint with the fixed cause of a failed `gh` call."""
        self.stop(
            "failed-retryable",
            _classify(result, repository=repository),
            fill={"repo": f"{self.run.owner}/{self.run.repo}"},
        )

    # --- decision order ---------------------------------------------------

    def execute(self) -> Outcome:
        run = self.run
        marker = _untrusted_marker(run.root)
        if marker:
            return Outcome("skipped", remedy=f"{marker} exists; restore the checkout")
        self.identify()
        self.lookup_issue()
        settled = self.settle()
        if settled is not None:
            return settled
        self.compare()
        body = _after(self.template(), _section(run, _now()))
        return self.create(body)

    def settle(self) -> Outcome | None:
        """Apply the PR identity rules to a fresh list; None when no PR exists."""
        found = self.decide(self.list_prs())
        if isinstance(found, _PullRequest):
            return self.reuse(found)
        return found

    def identify(self) -> None:  # noqa: C901 - One check per identity field.
        run = self.run
        if not RUN_ID_PATTERN.fullmatch(run.run_id):
            message = "invalid run ID"
            raise ValueError(message)
        inputs = run.root / ".specify/workflows/runs" / run.run_id / "inputs.json"
        feature = json.loads(inputs.read_text(encoding="utf-8"))["inputs"].get(
            "feature_directory"
        )
        if not isinstance(feature, str) or not FEATURE_PATTERN.fullmatch(feature):
            self.stop("blocked-unlinked", "no-issue-number")
        run.feature = feature
        match = ISSUE.match(feature)
        if match is None:
            self.stop("blocked-unlinked", "no-issue-number")
        run.issue = int(match.group(1))
        git, _ = _resolve("git", run.root)
        if git is None:
            self.stop("failed-retryable", "git-untrusted")
        run.git = git
        result = self.git("symbolic-ref", "--quiet", "--short", "HEAD")
        branch = result.stdout.strip()
        if result.returncode or not branch or branch.startswith("-"):
            self.stop("pending", "no-branch")
        result = self.git(
            "for-each-ref",
            "--format=%(upstream:remotename)%00%(upstream:remoteref)",
            f"refs/heads/{branch}",
        )
        remote, _, ref = result.stdout.strip("\n").partition("\0")
        published = ref.removeprefix("refs/heads/")
        if (
            result.returncode
            or not remote
            or remote == "."
            or remote.startswith("-")
            or not ref.startswith("refs/heads/")
            or not published
            or published.startswith("-")
        ):
            self.stop(
                "pending",
                "not-published",
                fill={"remote": remote or "origin", "branch": branch},
            )
        self.pinned_branch(branch, published, remote)
        run.remote, run.published = remote, published
        result = self.git("remote", "get-url", remote)
        match = GITHUB_REMOTE.fullmatch(result.stdout.strip())
        if (
            result.returncode
            or match is None
            or not all(
                NAME.fullmatch(part) and part not in {".", ".."}
                for part in match.group("owner", "repo")
            )
        ):
            self.stop("blocked-unlinked", "not-github")
        run.owner, run.repo = self.pinned(*match.group("owner", "repo"))
        gh, shadowed = _resolve("gh", run.root)
        if gh is None:
            self.stop("failed-retryable", "gh-untrusted" if shadowed else "gh-missing")
        run.gh = gh
        result = self.api(f"repos/{run.owner}/{run.repo}")
        if result.returncode:
            self.failed(result, repository=True)
        data = _json(result)
        base = data.get("default_branch") if isinstance(data, dict) else None
        if not isinstance(base, str) or not base:
            self.stop("failed-retryable", "github-error")
        run.base = base
        if base == published:
            self.stop("pending", "on-base-branch")

    def pinned_branch(self, branch: str, published: str, remote: str) -> None:
        """Accept only the branch and upstream recorded at `ballast run start`."""
        pin = _branch_pin(self.run.root, self.run.run_id)
        if pin is None:
            self.stop("blocked-unlinked", "branch-unpinned")
        if branch != pin:
            self.stop("blocked-unlinked", "branch-mismatch", fill={"branch": pin})
        if published != pin:
            # Published elsewhere, or tracking another branch such as main.
            self.stop(
                "pending", "not-published", fill={"remote": remote, "branch": pin}
            )

    def pinned(self, owner: str, repo: str) -> tuple[str, str]:
        """Accept the upstream only when it is the repository pinned in ballast.toml."""
        pinned = _pinned_repository(self.run.root)
        if pinned is None:
            self.stop("blocked-unlinked", "no-repository")
        if (owner.lower(), repo.lower()) != tuple(part.lower() for part in pinned):
            self.stop(
                "blocked-unlinked",
                "repository-mismatch",
                fill={"repo": "/".join(pinned)},
            )
        return pinned

    def lookup_issue(self) -> None:
        run = self.run
        result = self.api(f"repos/{run.owner}/{run.repo}/issues/{run.issue}")
        if result.returncode:
            if _status(result) in {404, 410}:
                self.stop("blocked-unlinked", "issue-not-found")
            self.failed(result)
        data = _json(result)
        if not isinstance(data, dict) or "pull_request" in data:
            self.stop("blocked-unlinked", "issue-not-found")
        title = data.get("title")
        run.title = (title if isinstance(title, str) else "")[:TITLE_LIMIT]
        result = self.api(
            f"repos/{run.owner}/{run.repo}/issues/{run.issue}/comments?per_page=100",
            paginate=True,
        )
        if result.returncode:
            self.failed(result)
        run.scope = _scope(self.pages(result))

    def pages(self, result: Result) -> list[dict[str, Any]]:
        """Entries of a `--paginate --slurp` list; unreadable is never empty."""
        data = _json(result)
        if not isinstance(data, list) or not all(isinstance(p, list) for p in data):
            self.stop("failed-retryable", "github-error")
        return _pages(data)

    def list_prs(self) -> list[_PullRequest]:
        run = self.run
        result = self.api(
            f"repos/{run.owner}/{run.repo}/pulls?head={run.owner}:"
            f"{_quote(run.published)}&state=all&per_page=100",
            paginate=True,
        )
        if result.returncode:
            self.failed(result)
        prs = []
        for entry in self.pages(result):
            pr = _pull_request(entry, run)
            if pr is not None:
                prs.append(pr)
        return prs

    def decide(self, prs: list[_PullRequest]) -> Outcome | _PullRequest | None:
        run = self.run
        opened = [pr for pr in prs if pr.state == "open"]
        if len(opened) > 1:
            return _outcome(
                "blocked-ambiguous",
                "several-open",
                issue=run.issue,
                matches=len(opened),
                addresses=tuple(pr.url for pr in opened),
            )
        if opened:
            pr = opened[0]
            if pr.base != run.base:
                return _outcome(
                    "blocked-ambiguous",
                    "base-mismatch",
                    issue=run.issue,
                    pr_number=pr.number,
                    pr_url=pr.url,
                    matches=1,
                    fill={
                        "number": pr.number,
                        "actual": pr.base,
                        "expected": run.base,
                    },
                )
            return pr
        if prs:
            latest = max(prs, key=lambda pr: (pr.closed_at, pr.number))
            merged = any(pr.state == "merged" for pr in prs)
            return _outcome(
                "blocked-closed",
                "merged" if merged else "closed",
                issue=run.issue,
                pr_number=latest.number,
                pr_url=latest.url,
                matches=len(prs),
                addresses=tuple(pr.url for pr in prs),
            )
        return None

    def reuse(self, pr: _PullRequest) -> Outcome:
        run = self.run
        reused = _outcome("reused", issue=run.issue, pr_number=pr.number, pr_url=pr.url)
        body = pr.body
        begins, ends = body.count(MARK_BEGIN), body.count(MARK_END)
        if begins == ends == 0:
            if _references(body, run):
                return reused
            updated = _after(body, _section(run, _now()))
        else:
            start, end = body.find(MARK_BEGIN), body.find(MARK_END)
            if begins != 1 or ends != 1 or end < start:
                return replace(
                    reused,
                    reason="section-unmanaged",
                    remedy=REMEDIES["reused", "section-unmanaged"],
                )
            section = _section(run, _now())
            end += len(MARK_END)
            if body[start:end] == section:
                return reused
            updated = body[:start] + section + body[end:]
        # GitHub has no conditional update for a PR body (DEC-0007): re-read it
        # just before writing and leave a body a human changed meanwhile.
        result = self.api(f"repos/{run.owner}/{run.repo}/pulls/{pr.number}")
        if result.returncode:
            self.failed(result)
        current = _json(result)
        if not isinstance(current, dict) or (current.get("body") or "") != pr.body:
            return replace(
                reused, reason="body-changed", remedy=REMEDIES["reused", "body-changed"]
            )
        result = self.gh(
            "pr",
            "edit",
            str(pr.number),
            "--repo",
            f"{run.owner}/{run.repo}",
            "--body-file",
            "-",
            stdin=updated,
        )
        if result.returncode:
            self.failed(result)
        return reused

    def compare(self) -> None:
        run = self.run
        result = self.api(
            f"repos/{run.owner}/{run.repo}/compare/"
            f"{_quote(run.base)}...{_quote(run.published)}"
        )
        if result.returncode:
            if _status(result) == 404:  # noqa: PLR2004
                self.stop(
                    "pending",
                    "not-published",
                    fill={"remote": run.remote, "branch": run.published},
                )
            self.failed(result)
        data = _json(result)
        files = data.get("files") if isinstance(data, dict) else None
        if not isinstance(files, list):
            # Unreadable is never "no change" (R2 round 3).
            self.stop("failed-retryable", "github-error")
        files = [item for item in files if isinstance(item, dict)]
        prefix = f"{run.feature}/"
        for item in files:
            for key in ("filename", "previous_filename"):
                name = item.get(key)
                if isinstance(name, str) and name and not name.startswith(prefix):
                    return
        reason = (
            "diff-unclassified"
            if len(files) >= COMPARE_FILE_CAP
            else "no-meaningful-change"
        )
        self.stop("pending", reason)

    def template(self) -> str:
        run = self.run
        result = self.api(
            f"repos/{run.owner}/{run.repo}/contents/.github/"
            f"pull_request_template.md?ref={_quote(run.base)}"
        )
        if result.returncode:
            if _status(result) == 404:  # noqa: PLR2004
                return ""
            self.failed(result)
        data = _json(result)
        content = data.get("content") if isinstance(data, dict) else None
        if not isinstance(content, str):
            return ""
        try:
            return base64.b64decode(content).decode("utf-8", "replace")
        except ValueError:
            return ""

    def create(self, body: str) -> Outcome:
        """List again, create and verify, all under the clone-wide lock."""
        run = self.run
        with _locked(ledger.common_dir(run.root) / LOCK_NAME) as held:
            if not held:
                self.stop("failed-retryable", "lock-busy")
            settled = self.settle()
            if settled is not None:
                return settled
            result = self.gh(
                "pr",
                "create",
                "--repo",
                f"{run.owner}/{run.repo}",
                "--draft",
                "--base",
                run.base,
                "--head",
                run.published,
                "--title",
                run.title,
                "--body-file",
                "-",
                stdin=body,
            )
            if result.returncode:
                if "already exists" not in result.stderr:
                    self.failed(result)
                # Another clone opened it first: GitHub allows only one.
                return self.settle() or self.failed(result)
            prs = self.list_prs()
        return self.verify(prs)

    def verify(self, prs: list[_PullRequest]) -> Outcome:
        """Report `created` only when the list shows exactly the requested PR."""
        run = self.run
        opened = [pr for pr in prs if pr.state == "open"]
        if len(opened) > 1:
            found = self.decide(prs)
            if isinstance(found, Outcome):
                return found
        if len(opened) == 1 and opened[0].base == run.base and opened[0].draft:
            pr = opened[0]
            return _outcome(
                "created", issue=run.issue, pr_number=pr.number, pr_url=pr.url
            )
        pr = opened[0] if len(opened) == 1 else None
        return _outcome(
            "blocked-ambiguous",
            "create-unverified",
            issue=run.issue,
            pr_number=pr.number if pr else None,
            pr_url=pr.url if pr else None,
            matches=len(opened),
        )


def _pages(data: object) -> list[dict[str, Any]]:
    """Flatten a `--paginate --slurp` array of pages into its entries."""
    if not isinstance(data, list):
        return []
    entries: list[dict[str, Any]] = []
    for page in data:
        items = page if isinstance(page, list) else [page]
        entries.extend(item for item in items if isinstance(item, dict))
    return entries


def _scope(comments: list[dict[str, Any]]) -> list[str]:
    """Scope lines of the newest intake comment written by a repository member."""
    eligible = [
        comment
        for comment in comments
        if isinstance(comment.get("body"), str)
        and INTAKE_MARK in comment["body"]
        and comment.get("author_association") in SCOPE_AUTHORS
    ]
    if not eligible:
        return []
    newest = max(
        enumerate(eligible), key=lambda item: (str(item[1].get("created_at")), item[0])
    )[1]
    lines = []
    for label in SCOPE_FIELDS:
        for line in newest["body"].splitlines():
            text = line.strip()
            if text.startswith(label):
                lines.append(_escape(text[:SCOPE_LIMIT]))
                break
    return lines


def _pull_request(entry: dict[str, Any], run: _Run) -> _PullRequest | None:
    """Keep a list entry only when it is this repository's PR for the head."""
    head = entry.get("head") if isinstance(entry.get("head"), dict) else {}
    repository = head.get("repo") if isinstance(head.get("repo"), dict) else {}
    owner = repository.get("owner") if isinstance(repository.get("owner"), dict) else {}
    base = entry.get("base") if isinstance(entry.get("base"), dict) else {}
    number = entry.get("number")
    full_name = f"{run.owner}/{run.repo}"
    if (
        type(number) is not int
        or not 0 < number < 10**10
        or head.get("ref") != run.published
        or str(owner.get("login")).lower() != run.owner.lower()
        or str(repository.get("full_name")).lower() != full_name.lower()
        or not isinstance(entry.get("html_url"), str)
        or entry["html_url"].lower()
        != f"https://github.com/{full_name}/pull/{number}".lower()
        or not isinstance(base.get("ref"), str)
    ):
        return None
    state = "merged" if entry.get("merged_at") else str(entry.get("state"))
    if state not in {"open", "closed", "merged"}:
        return None
    body = entry.get("body")
    return _PullRequest(
        number=number,
        url=entry["html_url"],
        state=state,
        draft=entry.get("draft") is True,
        base=base["ref"],
        body=body if isinstance(body, str) else "",
        closed_at=str(entry.get("closed_at") or ""),
    )


def _references(body: str, run: _Run) -> bool:
    """Whether a body already names the Issue as `#N` or its address."""
    token = rf"(?<![\w/#&])#{run.issue}(?!\w)"
    address = (
        rf"github\.com/{re.escape(run.owner)}/{re.escape(run.repo)}"
        rf"/issues/{run.issue}(?![0-9])"
    )
    return bool(re.search(token, body) or re.search(address, body, re.IGNORECASE))


class _Locked:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.handle: int | None = None

    def __enter__(self) -> bool:
        flags = os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC
        try:
            handle = os.open(self.path, flags, 0o600)
        except OSError as error:
            message = "the PR lock is unavailable"
            raise LockUnavailableError(message) from error
        if not stat.S_ISREG(os.fstat(handle).st_mode):
            os.close(handle)
            message = "the PR lock is not a regular file"
            raise LockUnavailableError(message)
        deadline = time.monotonic() + LOCK_WAIT
        while True:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    os.close(handle)
                    return False
                time.sleep(0.05)
                continue
            self.handle = handle
            return True

    def __exit__(self, *_: object) -> None:
        if self.handle is not None:
            fcntl.flock(self.handle, fcntl.LOCK_UN)
            os.close(self.handle)
            self.handle = None


def _locked(path: Path) -> _Locked:
    """Hold the clone-wide PR lock, waiting at most LOCK_WAIT seconds."""
    return _Locked(path)


def _record(run: _Run, outcome: Outcome) -> None:
    data: dict[str, Any] = {"outcome": outcome.state}
    for key in ("reason", "issue", "pr_number", "pr_url", "matches"):
        value = getattr(outcome, key)
        if value is not None:
            data[key] = value
    ledger.append(
        run.root,
        ledger.new_event(run.run_id, run.feature, "pull_request", "runner", data),
    )


def checkpoint(root: Path, run_id: str) -> Outcome:
    """Create or reuse the feature's Draft PR; record and return the outcome."""
    work = _Checkpoint(root, run_id)
    try:
        outcome = work.execute()
    except _Stop as stop:
        outcome = stop.outcome
    except Exception as error:  # noqa: BLE001 - Any failure is one outcome.
        outcome = replace(
            _outcome("failed-retryable", "internal-error", issue=work.run.issue),
            detail=type(error).__name__,
        )
    if outcome.state != "skipped" and work.run.feature is not None:
        try:
            _record(work.run, outcome)
        except Exception as error:  # noqa: BLE001 - The line is still printed.
            outcome = replace(outcome, detail=f"not recorded: {type(error).__name__}")
    return outcome
