"""Bring a run's feature branch onto its base before any agent step (#18).

`run.py` imports this module at startup, after the trusted launcher verified
the protected inputs and before any agent step, and calls `synchronize` once
per `ballast run start`, `resume` and `continue`. The trust boundary
(docs/adr/0005, FR-012):

- `git` is resolved outside every working tree and temp root, called by
  absolute path with a list argv, never through a shell;
- the repository comes from the protected `ballast.toml`, the base from the
  run's pin or that repository's default branch, never from `.git/config`;
- every network or merge command runs in a throwaway bare repository with an
  empty configuration, no prompts and no maintenance; it shares the
  checkout's object store, so nothing there may gc, repack or prune;
- the checkout sees only local plumbing with hooks, fsmonitor and every
  configured filter driver disabled, so no program it names ever runs;
- only the feature branch named for the Issue is rewritten or pushed, and
  only with a lease on the commit observed in the same invocation;
- every HEAD change is followed by the launcher's protected-input check;
- names and paths are data: shell-quoted in commands, escaped elsewhere, and
  Git's own output is never printed.

Every check records one `branch_sync` ledger event and returns one Outcome;
`run.py` starts no agent unless it is `up-to-date` or `synchronized`.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import shlex
import subprocess
import tempfile
import uuid
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, NoReturn

import autonomy
import draft_pr
import launcher
import ledger
import setup_trust
from artifacts import FEATURE_PATTERN, RUN_ID_PATTERN

GIT_FLOOR = (2, 41)
# Every throwaway command shares the checkout's object store: nothing it runs
# may start maintenance or gc, or write a commit-graph from its few refs.
NO_MAINTENANCE = (
    "-c",
    "maintenance.auto=false",
    "-c",
    "gc.auto=0",
    "-c",
    "fetch.writeCommitGraph=false",
    # Nor trust a commit-graph an agent can forge in the shared store (SEC-004).
    "-c",
    "core.commitGraph=false",
)
# The checkout's `submodule.recurse` would make `read-tree -u` run Git inside
# submodules, under their own agent-writable configuration. An agent-written
# commit-graph could answer ancestry questions falsely (SEC-004).
NO_RECURSION = ("-c", "submodule.recurse=false", "-c", "core.commitGraph=false")
LS_REMOTE_TIMEOUT = 30
NETWORK_TIMEOUT = 600
LOCAL_TIMEOUT = 600
REF = ledger.REF
COMMIT = ledger.OID
IN_PROGRESS_MARKERS = (
    ("rebase-merge", "rebase"),
    ("rebase-apply", "rebase"),
    ("MERGE_HEAD", "merge"),
    ("CHERRY_PICK_HEAD", "cherry-pick"),
    ("REVERT_HEAD", "revert"),
    ("BISECT_LOG", "bisect"),
)
# The only commands the throwaway repository runs (contract § External
# commands); none of them can garbage-collect the shared object store.
THROWAWAY_COMMANDS = frozenset(
    {
        "init",
        "update-ref",
        "cat-file",
        "rev-parse",
        "ls-remote",
        "fetch",
        "merge-tree",
        "var",
        "hash-object",
        "push",
    }
)
# One copy of the Git environment rules, shared with setup's observation of the
# pinned repository's default branch (ADR-0015; plan-review F-002).
DROPPED_ENV = setup_trust.DROPPED_ENV
DIRTY_PATHS = 10
CONFLICT_PATHS = 20
PROTECTED_NAMES = 10
OVERLAP_PATHS = 200
SHORT = 12
# old_base and new_base: the replay's bases, so a completion from the record
# can still report stale evidence (E-03); None for a fast-forward.
RECORD_FIELDS = frozenset(
    {
        "branch",
        "old_head",
        "new_head",
        "published_old",
        "old_base",
        "new_base",
        "run_id",
        "written_at",
    }
)
REMOTE = "origin"

# Recovery actions, one per cause and detail (SC-003). `{rerun}` is the same
# `ballast run` command in full; the policy section lists these verbatim.
RECOVERY = {
    "busy": "another ballast run is synchronizing {branch}; retry when it finishes",
    "git-old": "put a system git 2.41 or later on PATH ahead of any checkout directory",
    "shallow": "git fetch --unshallow, then {rerun}",
    "partial": "clone the repository again without --filter, then {rerun}",
    "alternates": "clone the repository again without alternates, then {rerun}",
    "in-progress": "finish or abort the {operation} yourself, then {rerun}",
    "index-lock": "if no git process is running, remove {path}, then {rerun}",
    "wrong-branch": "git switch {pinned}, then {rerun}",
    # #21 R11: a documented operator step; nothing writes the pin for it.
    "unpinned": (
        'after checking the feature in the run\'s record, add "feature": '
        '"specs/<N>-<slug>" (and "branch" when missing) to the run\'s pin in the '
        "launcher state directory (see Runs started before branch pinning), then "
        "{rerun}"
    ),
    "no-repository": "declare [github] repository and run ballast trust",
    "missing-base": "restore {base} on {repo}; Ballast never substitutes another base",
    "fetch-failed": (
        "check network access and credentials for {repo} (Ballast cannot answer "
        "a prompt), then {rerun}"
    ),
    "not-feature-branch": (
        "synchronize {branch} yourself, or run the feature on its own branch: "
        "git switch -c {feature_branch}"
    ),
    "diverged": "reconcile by hand: git pull --rebase {remote} {branch}, then {rerun}",
    "base-rewritten": "rebase by hand onto {base}, then {rerun}",
    "base-branch": "git switch -c {new_branch}",
    "dirty": (
        "commit or finish these changes (Ballast never stashes or discards them), "
        "then {rerun}"
    ),
    "dirty-files": "move or commit these files, then {rerun}",
    "dirty-pushed": (
        "move these changes aside without committing them (Ballast never stashes "
        "or discards them), then {rerun} to finish the synchronization"
    ),
    "dirty-files-pushed": (
        "move or commit these files, then {rerun} to finish the synchronization"
    ),
    "interrupted-update": (
        "git restore --source={new_head} --staged --worktree ., then {rerun} to "
        "finish the synchronization"
    ),
    "conflict": (
        "rebase by hand: git pull --rebase {remote} {base}, resolve, then {rerun}"
    ),
    "conflict-published": (
        "rebase by hand: git pull --rebase {remote} {base}, resolve, "
        "git push --force-with-lease={branch}:{published} {remote} {branch}, "
        "then {rerun}"
    ),
    "conflict-pushed": (
        "git rebase --onto {new_head} {old_head} {branch}, resolve, then {rerun}"
    ),
    "push-retry": "{rerun}",
    "push-rules": (
        "check {repo}'s branch rules for {branch} (protection, required "
        "signatures), then {rerun}"
    ),
    "protected-input": "review these changes, then run ballast trust (operator only)",
    "internal-error": "report it with the run ID, then {rerun}",
    "no-committer": (
        "set user.name and user.email in your global Git configuration, then {rerun}"
    ),
    "invalid-record": (
        "report it with the run ID; Ballast keeps {record} until you check {branch} "
        "and its published branch and delete it"
    ),
    "after-push": "{rerun} to finish the synchronization",
}
# Values shown as plain text; every other value is shell-quoted.
TEXT_VALUES = frozenset({"repo", "operation", "rerun"})

# Test seam: a list the throwaway and checkout runners append
# (where, argv) to, when not None.
ARGV_LOG: list[tuple[str, list[str]]] | None = None


@dataclass(frozen=True)
class Outcome:
    """One check result; names are validated data, wording is fixed."""

    outcome: str
    cause: str | None = None
    detail: str | None = None
    recovery: str | None = None
    branch: str | None = None
    base_ref: str | None = None
    base_before: str | None = None
    base_after: str | None = None
    head_before: str | None = None
    head_after: str | None = None
    pushed: bool | None = None
    fast_forwarded: bool | None = None
    retryable: bool | None = None
    recovered: bool | None = None
    recovered_from: str | None = None
    overlap: int | None = None
    stale_plan: bool | None = None
    stale_review: bool | None = None
    note: str | None = None
    interrupted: bool = False


@dataclass(frozen=True)
class Result:
    """What one Git command returned; never printed or stored."""

    returncode: int
    stdout: Any = ""
    stderr: str = ""
    timed_out: bool = False


class _Block(Exception):  # noqa: N818 - Control flow, not an error.
    def __init__(
        self,
        cause: str,
        detail: str | None,
        recovery: str,
        *,
        retryable: bool | None = None,
        interrupted: bool = False,
    ) -> None:
        super().__init__(cause)
        self.cause = cause
        self.detail = detail
        self.recovery = recovery
        self.retryable = retryable
        self.interrupted = interrupted


# --- test seams -------------------------------------------------------------


def _url(root: Path, owner: str, name: str, *, origin: str = "") -> str:
    """Return the pinned repository's URL, in the scheme `origin` uses.

    Only the scheme is read from `origin`; the repository never is.
    """
    return setup_trust.repository_url(root, owner, name, origin=origin)


def _crash(point: str) -> None:
    """No-op in production; tests raise here to simulate a crash at `point`."""


def _git_version(git: str) -> tuple[int, int] | None:
    """(major, minor) of `git version`, or None when it does not say."""
    env = {k: v for k, v in os.environ.items() if k not in DROPPED_ENV}
    try:
        result = subprocess.run(  # noqa: S603 - resolved program, fixed argv
            [git, "version"],
            env=env,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=LS_REMOTE_TIMEOUT,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    match = re.match(r"git version (\d+)\.(\d+)", result.stdout)
    return (int(match.group(1)), int(match.group(2))) if match else None


# --- text -------------------------------------------------------------------

_text = draft_pr.printable  # one escaping rule for the CLI and the PR body


def _short(commit: str | None) -> str:
    return commit[:SHORT] if commit else "unknown"


def _paths(paths: list[str], limit: int = DIRTY_PATHS) -> str:
    shown = ", ".join(_text(path) for path in paths[:limit])
    return shown + (" ..." if len(paths) > limit else "")


def _recovery(key: str, **fill: object) -> str:
    """Fill a fixed recovery action, quoting names as shell words."""
    values = {}
    for name, value in fill.items():
        text = str(value)
        if name in TEXT_VALUES:
            values[name] = _text(text)
        # A leading `-` reads as an option, a leading `+` as a forced refspec.
        elif not text.isprintable() or text.startswith(("-", "+")) or not text:
            values[name] = f"<{name.replace('_', '-')}>"
        else:
            values[name] = shlex.quote(text)
    return RECOVERY[key].format(**values)


def _stale_note(outcome: Outcome) -> str | None:
    if not outcome.overlap:
        return None
    kinds = [
        name
        for name, stale in (
            ("plan", outcome.stale_plan),
            ("review", outcome.stale_review),
        )
        if stale
    ]
    files = "file" if outcome.overlap == 1 else "files"
    return (
        f"{' and '.join(kinds)} evidence may be stale: {outcome.overlap} {files} "
        "changed on both sides (see the Draft PR)"
    )


def format_lines(outcome: Outcome) -> list[tuple[str, str]]:
    """(stream, line) pairs `run.py` prints: one line, or a block and recovery."""
    branch, base = (
        _text(outcome.branch or "HEAD"),
        _text(outcome.base_ref or "base"),
    )
    if outcome.outcome == "blocked":
        line = f"BLOCKED_UPSTREAM_SYNC ({outcome.cause})"
        if outcome.detail:
            line += f": {outcome.detail}"
        return [("stderr", line), ("stderr", f"Recovery: {outcome.recovery}")]
    if outcome.outcome == "up-to-date":
        line = (
            f"Branch sync: up-to-date {branch} with {base} "
            f"({_short(outcome.base_after)})"
        )
        if outcome.fast_forwarded:
            line += "; fast-forwarded to the published branch"
    else:
        line = (
            f"Branch sync: synchronized {branch} onto {base} "
            f"({_short(outcome.base_before)}..{_short(outcome.base_after)}), "
            f"HEAD {_short(outcome.head_before)} -> {_short(outcome.head_after)}"
        )
        if outcome.pushed:
            line += ", pushed"
        if outcome.recovered:
            line += (
                "; completed the interrupted synchronization from run "
                f"{outcome.recovered_from}"
            )
    for note in (outcome.note, _stale_note(outcome)):
        if note:
            line += f"; {note}"
    return [("stdout", line)]


# --- files --------------------------------------------------------------------


def _key(branch: str) -> str:
    return hashlib.sha256(branch.encode("utf-8", "surrogateescape")).hexdigest()[:16]


def _read_json(path: Path) -> object | None:
    """Return a JSON file's value, None when absent; a link or bad JSON raises."""
    try:
        handle = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    except FileNotFoundError:
        return None
    with os.fdopen(handle, encoding="utf-8") as stream:
        return json.loads(stream.read())


def _write_json(path: Path, data: object) -> None:
    """Replace path atomically, mode 0600 in a 0700 directory."""
    directory = path.parent
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    if directory.is_symlink() or not directory.is_dir():
        message = f"{directory} is not a directory"
        raise OSError(message)
    directory.chmod(0o700)
    handle, temporary = tempfile.mkstemp(dir=directory, prefix=".", suffix=".tmp")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write(json.dumps(data, sort_keys=True))
            stream.flush()
            os.fsync(stream.fileno())
        Path(temporary).replace(path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


def _pin_path(root: Path, run_id: str) -> Path:
    if not RUN_ID_PATTERN.fullmatch(run_id):
        message = "invalid run ID"
        raise ValueError(message)
    return launcher.state_dir(root) / "draft-pr" / f"{run_id}.json"


def read_pin(root: Path, run_id: str) -> dict[str, str]:
    """Return a run's pin (#17 branch, #18 base, base_commit, feature); {} if absent.

    Fields that are not valid are left out; `continue` passes the source run's
    `branch` and `base` back into `synchronize`.
    """
    try:
        data = _read_json(_pin_path(root, run_id))
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    pin: dict[str, str] = {}
    branch = data.get("branch")
    if isinstance(branch, str) and branch and not branch.startswith("-"):
        pin["branch"] = branch
    if isinstance(data.get("base"), str):
        pin["base"] = data["base"]
    commit = data.get("base_commit")
    if isinstance(commit, str) and COMMIT.fullmatch(commit):
        pin["base_commit"] = commit
    feature = data.get("feature")
    if isinstance(feature, str) and FEATURE_PATTERN.fullmatch(feature):
        pin["feature"] = feature
    return pin


def _issue(feature: str | None) -> int | None:
    match = draft_pr.ISSUE.match(feature) if feature else None
    return int(match.group(1)) if match else None


def _status_entries(output: str) -> list[tuple[str, str]]:
    """(XY, path) of `status --porcelain=v1 -z`; a rename's source is skipped."""
    items = output.split("\0")
    entries = []
    index = 0
    while index < len(items):
        item = items[index]
        index += 1
        if len(item) < 4:  # noqa: PLR2004 - "XY path"
            continue
        entries.append((item[:2], item[3:]))
        if item[0] in "RC":
            index += 1
    return entries


def _split(output: str) -> list[str]:
    return [item for item in output.split("\0") if item]


def _rewrite(raw: bytes, tree: str, parent: str, committer: bytes) -> bytes:
    """Rewrite a commit for replay: new tree, parent and committer; no signature.

    Author, encoding, other headers and the message are kept byte for byte.
    """
    head, separator, message = raw.partition(b"\n\n")
    lines: list[bytes] = []
    skipping = False
    for line in head.split(b"\n"):
        if line.startswith(b" "):
            if not skipping:
                lines.append(line)
            continue
        skipping = False
        name = line.split(b" ", 1)[0]
        if name == b"tree":
            lines += [b"tree " + tree.encode(), b"parent " + parent.encode()]
        elif name == b"parent":
            continue
        elif name in {b"gpgsig", b"gpgsig-sha256"}:
            skipping = True
        elif name == b"committer":
            lines.append(b"committer " + committer)
        else:
            lines.append(line)
    return b"\n".join(lines) + (separator or b"\n\n") + message


def _headers(raw: bytes) -> dict[str, list[str]]:
    """Single-line commit headers (tree, parent) of a raw commit."""
    found: dict[str, list[str]] = {}
    for line in raw.partition(b"\n\n")[0].split(b"\n"):
        name, _, value = line.partition(b" ")
        if name in {b"tree", b"parent"}:
            found.setdefault(name.decode(), []).append(value.decode())
    return found


# --- the check ----------------------------------------------------------------


class _Sync:
    def __init__(  # noqa: PLR0913 - The entry point's arguments.
        self,
        root: Path,
        run_id: str,
        *,
        feature: str | None,
        starting: bool,
        branch: str | None,
        base: str | None,
        source_run: str | None,
        rerun: str | None = None,
    ) -> None:
        self.root = root
        self.run_id = run_id
        self.feature = (
            feature
            if isinstance(feature, str) and FEATURE_PATTERN.fullmatch(feature)
            else None
        )
        # The Issue number decides what may be rewritten: from the operator's
        # command at start, from the operator's pin afterwards (SEC-002).
        self.issue = _issue(self.feature) if starting else None
        self.starting = starting
        self.given_branch = branch
        self.given_base = base
        self.source_run = source_run
        self.continuing = source_run is not None and not starting
        if rerun is not None:
            # A Chat step names its own rerun command (#20 R5).
            self.rerun = rerun
        elif starting:
            self.rerun = "your ballast run start command"
        elif self.continuing:
            self.rerun = f"your ballast run continue {source_run} command"
        else:
            self.rerun = f"ballast run resume {run_id}"
        self.event_id = uuid.uuid4().hex
        self.git = ""
        self.filters: list[str] | None = None
        self.state: Path | None = None
        self.bare: Path | None = None
        self.objects: Path | None = None
        self.pin: dict[str, str] = {}
        self.branch: str | None = None
        self.head_before: str | None = None
        self.head: str | None = None
        self.repo = ""
        self.url = ""
        self.base: str | None = None
        self.base_before: str | None = None
        self.base_after: str | None = None
        self.default: str | None = None
        self.published: str | None = None
        self.pushed = False
        self.holds: str | None = None  # the published branch holds this sync
        self.fast_forwarded = False
        self.recovered = False
        self.recovered_from: str | None = None
        self.protected: list[str] = []
        self.protected_source = "base"
        self.committer: bytes | None = None
        self.note: str | None = None
        self.overlap: list[str] = []
        self.stale: list[str] = []
        # The bases of the replay being written, for the write-ahead record.
        self.sync_bases: tuple[str, str] | None = None

    # --- runners --------------------------------------------------------------

    def _env(self) -> dict[str, str]:
        return setup_trust.base_environment(self.root)

    def _run(  # noqa: PLR0913 - One bounded command.
        self,
        argv: list[str],
        *,
        cwd: Path,
        env: dict[str, str],
        timeout: float,
        stdin: bytes | None = None,
        binary: bool = False,
        network: bool = False,
    ) -> Result:
        try:
            result = subprocess.run(  # noqa: S603 - absolute git, list argv
                argv,
                cwd=cwd,
                env=env,
                input=stdin,
                stdin=subprocess.DEVNULL if stdin is None else None,
                capture_output=True,
                timeout=timeout,
                start_new_session=network,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return Result(-1, b"" if binary else "", timed_out=True)
        except OSError:
            return Result(-1, b"" if binary else "")
        stderr = result.stderr.decode("utf-8", "replace")
        if binary:
            return Result(result.returncode, result.stdout, stderr)
        stdout = result.stdout.decode("utf-8", "surrogateescape")
        return Result(result.returncode, stdout, stderr)

    def checkout(
        self, *args: str, binary: bool = False, timeout: float = LOCAL_TIMEOUT
    ) -> Result:
        """Local plumbing in the checkout: no hooks, fsmonitor or filter."""
        filters = [] if args[0] == "config" else self.filter_flags()
        argv = [self.git, *autonomy.GIT_HARDENING, *NO_RECURSION, *filters, *args]
        if ARGV_LOG is not None:
            ARGV_LOG.append(("checkout", argv))
        env = self._env() | {
            "GIT_NO_LAZY_FETCH": "1",
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_CEILING_DIRECTORIES": str(self.root.resolve().parent),
        }
        return self._run(argv, cwd=self.root, env=env, timeout=timeout, binary=binary)

    def throwaway(
        self,
        *args: str,
        attr_source: str | None = None,
        network: bool = False,
        stdin: bytes | None = None,
        binary: bool = False,
        timeout: float = LOCAL_TIMEOUT,
    ) -> Result:
        """Run one command in the throwaway repository, never with maintenance."""
        if args[0] not in THROWAWAY_COMMANDS or self.bare is None:
            # Not an assert: it must hold under python -O too (SEC-006).
            message = f"git {args[0]} is not allowed in the throwaway"
            raise RuntimeError(message)
        prefix = [f"--attr-source={attr_source}"] if attr_source else []
        argv = [self.git, *prefix, *autonomy.GIT_HARDENING, *NO_MAINTENANCE, *args]
        if ARGV_LOG is not None:
            ARGV_LOG.append(("throwaway", argv))
        env = setup_trust.throwaway_environment(self.root)
        env["GIT_CEILING_DIRECTORIES"] = str(self.bare.parent)
        if args[0] != "init":
            env |= {
                "GIT_DIR": str(self.bare),
                "GIT_OBJECT_DIRECTORY": str(self.objects),
            }
        return self._run(
            argv,
            cwd=self.bare.parent,
            env=env,
            timeout=timeout,
            stdin=stdin,
            binary=binary,
            network=network,
        )

    def filter_flags(self) -> list[str]:
        if self.filters is None:
            listed = self.checkout("config", "--list", "--name-only", "-z")
            if listed.returncode:
                message = "git config failed"
                raise RuntimeError(message)
            self.filters = autonomy.filter_flags(listed.stdout)
        return self.filters

    def value(self, *args: str) -> str:
        """Stdout of a checkout command that must succeed."""
        result = self.checkout(*args)
        if result.returncode:
            message = f"git {args[0]} failed"
            raise RuntimeError(message)
        return result.stdout.strip()

    # --- blocks ---------------------------------------------------------------

    def stop(
        self, cause: str, detail: str | None, key: str, **fill: object
    ) -> NoReturn:
        raise _Block(cause, detail, _recovery(key, rerun=self.rerun, **fill))

    def blocked(self, block: _Block) -> Outcome:
        detail, recovery = block.detail, block.recovery
        if self.holds and block.cause in {"busy", "internal-error"}:
            # DEC-0005: the next invocation completes it from the record.
            suffix = f"the published branch already holds {_short(self.holds)}"
            detail = f"{detail}; {suffix}" if detail else suffix
            recovery = _recovery("after-push", rerun=self.rerun)
        return Outcome(
            "blocked",
            cause=block.cause,
            detail=detail,
            recovery=recovery,
            branch=self.branch,
            base_ref=self.base,
            base_before=self.base_before,
            base_after=self.base_after,
            head_before=self.head_before,
            head_after=self.head,
            pushed=self.pushed or None,
            retryable=block.retryable,
            interrupted=block.interrupted,
            # E-03: a protected-input block keeps the synchronization.
            **(self.stale_fields() if block.cause == "protected-input" else {}),
        )

    def stale_fields(self) -> dict[str, Any]:
        if not self.overlap:
            return {}
        return {
            "overlap": len(self.overlap),
            "stale_plan": "plan" in self.stale,
            "stale_review": "review" in self.stale,
        }

    # --- the R4 steps ---------------------------------------------------------

    def execute(self) -> Outcome:
        self.resolve_git()
        # Refuses operator state an agent could write (#34): internal-error.
        self.state = launcher.state_dir(self.root)
        intended = self.intended_branch()
        lock = self.state / "branch-sync" / f"{_key(intended)}.lock"
        lock.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            with draft_pr._Locked(lock, wait=0) as held:  # noqa: SLF001
                if not held:
                    self.stop("busy", None, "busy", branch=intended)
                _crash("locked")
                self.shape()
                self.in_progress()
                self.identity(intended)
                with tempfile.TemporaryDirectory(
                    prefix="ballast-sync-", dir=self.state
                ) as away:
                    self.create_throwaway(Path(away))
                    self.observe()
                    self.recover()
                    return self.classify()
        except draft_pr.LockUnavailableError as error:
            raise RuntimeError(str(error)) from error

    def resolve_git(self) -> None:
        git, _ = draft_pr._resolve("git", self.root)  # noqa: SLF001
        if git is None:
            self.stop(
                "git-unavailable", "git not found outside working trees", "git-old"
            )
        self.git = git
        version = _git_version(git)
        if version is None:
            self.stop("git-unavailable", "git version unknown", "git-old")
        if version < GIT_FLOOR:
            shown = f"{version[0]}.{version[1]}"
            self.stop("git-unavailable", f"git {shown} is older than 2.41", "git-old")

    def current_branch(self) -> str | None:
        result = self.checkout("symbolic-ref", "--quiet", "HEAD")
        name = result.stdout.strip()
        if result.returncode or not name.startswith("refs/heads/"):
            return None
        branch = name.removeprefix("refs/heads/")
        return branch if branch and not branch.startswith("-") else None

    def intended_branch(self) -> str:
        """Return the run's branch (R12): pinned at start only (DEC-0006)."""
        if self.starting:
            current = self.current_branch()
            if current is None:
                # R4: an operation in progress is reported before identity (E-02).
                self.in_progress()
                self.stop(
                    "wrong-branch",
                    "HEAD is detached",
                    "wrong-branch",
                    pinned=self.feature_branch(),
                )
            self.pin = read_pin(self.root, self.run_id)
            if "branch" not in self.pin:
                self.pin = {"branch": current}
                if self.feature:
                    self.pin["feature"] = self.feature
                self.save_pin()
            return self.pin["branch"]
        run = self.source_run if self.continuing else self.run_id
        pinned = read_pin(self.root, str(run))
        if self.continuing:
            self.pin = {
                key: value
                for key, value in (
                    ("branch", self.given_branch),
                    ("base", self.given_base),
                    ("feature", pinned.get("feature")),
                )
                if value
            }
        else:
            self.pin = pinned
        missing = [name for name in ("branch", "feature") if name not in self.pin]
        if missing:
            # DEC-0006: never trust what an agent step could have changed.
            self.stop(
                "wrong-branch",
                f"run {run} has no {' or '.join(missing)} pin "
                "(started before branch pinning)",
                "unpinned",
            )
        self.feature = self.pin["feature"]
        self.issue = _issue(self.feature)
        return self.pin["branch"]

    def save_pin(self, *, final: bool = False) -> None:
        """Write the pin; a continuation's waits for a non-blocked outcome (N-07)."""
        if self.continuing and not final:
            return
        _write_json(_pin_path(self.root, self.run_id), self.pin)

    def shape(self) -> None:
        """Shallow checkouts and partial clones are refused (N-12, DEC-0007)."""
        if self.value("rev-parse", "--is-shallow-repository") == "true":
            self.stop("git-unavailable", "shallow checkout", "shallow")
        partial = self.checkout("config", "--get", "extensions.partialClone")
        promisor = self.checkout(
            "config",
            "--get-regexp",
            r"^remote\..*\.(promisor|partialclonefilter)$",
        )
        if partial.returncode == 0 or (promisor.returncode == 0 and promisor.stdout):
            self.stop("git-unavailable", "partial clone", "partial")
        # The throwaway shares the object store: alternates would let it read
        # and push objects of any store the operator can read (SEC-005).
        alternates = self.value(
            "rev-parse",
            "--path-format=absolute",
            "--git-path",
            "objects/info/alternates",
        )
        if os.path.lexists(alternates):
            self.stop("git-unavailable", "alternate object store", "alternates")

    def in_progress(self) -> None:
        names = [name for name, _ in IN_PROGRESS_MARKERS] + ["index.lock"]
        args = [arg for name in names for arg in ("--git-path", name)]
        paths = self.value("rev-parse", "--path-format=absolute", *args).split("\n")
        if len(paths) != len(names):
            message = "git rev-parse --git-path failed"
            raise RuntimeError(message)
        for (_, operation), path in zip(IN_PROGRESS_MARKERS, paths, strict=False):
            if os.path.lexists(path):
                self.stop(
                    "in-progress",
                    f"a {operation} is in progress",
                    "in-progress",
                    operation=operation,
                )
        if os.path.lexists(paths[-1]):
            self.stop(
                "in-progress",
                f"another git process may hold the index ({_text(paths[-1])} exists)",
                "index-lock",
                path=paths[-1],
            )

    def identity(self, intended: str) -> None:
        current = self.current_branch()
        if current is None:
            self.stop(
                "wrong-branch", "HEAD is detached", "wrong-branch", pinned=intended
            )
        if current != intended:
            self.stop(
                "wrong-branch",
                f"on {_text(current)}, run started on {_text(intended)}",
                "wrong-branch",
                pinned=intended,
            )
        self.branch = intended
        self.head_before = self.head = self.branch_head()
        commit = self.pin.get("base_commit")
        self.base_before = commit

    def branch_head(self) -> str:
        return self.value(
            "rev-parse", "--verify", f"refs/heads/{self.branch}^{{commit}}"
        )

    def create_throwaway(self, away: Path) -> None:
        object_format = self.value("rev-parse", "--show-object-format")
        if object_format not in {"sha1", "sha256"}:
            message = "unknown object format"
            raise RuntimeError(message)
        common = Path(
            self.value("rev-parse", "--path-format=absolute", "--git-common-dir")
        )
        self.objects = common / "objects"
        self.bare = away / "sync.git"
        made = self.throwaway(
            "init",
            "--quiet",
            "--bare",
            "--template=",
            f"--object-format={object_format}",
            str(self.bare),
        )
        if made.returncode:
            message = "git init failed"
            raise RuntimeError(message)

    def has(self, commit: str) -> bool:
        """Probe the shared store from the throwaway: it can never lazy-fetch."""
        return self.throwaway("cat-file", "-e", f"{commit}^{{commit}}").returncode == 0

    def observe(self) -> None:  # noqa: C901, PLR0912 - One advertisement, read once.
        """R3: the base, default and published branch from the pinned repository."""
        pinned = draft_pr._pinned_repository(self.root)  # noqa: SLF001
        if pinned is None:
            self.stop(
                "unknown-base",
                "no [github] repository in ballast.toml",
                "no-repository",
            )
        owner, name = pinned
        self.repo = f"{owner}/{name}"
        origin = self.checkout("remote", "get-url", REMOTE)
        self.url = _url(
            self.root,
            owner,
            name,
            origin=origin.stdout.strip() if origin.returncode == 0 else "",
        )
        base = self.pin.get("base")
        if base is not None and not REF.fullmatch(base):
            self.stop(
                "unknown-base",
                f"{_text(base)} does not exist on {self.repo}",
                "missing-base",
                base=base,
                repo=self.repo,
            )
        refs = ["HEAD", f"refs/heads/{self.branch}"]
        if base is not None and base != self.branch:
            refs.insert(1, f"refs/heads/{base}")
        listed = self.throwaway(
            "ls-remote",
            "--symref",
            self.url,
            *refs,
            network=True,
            timeout=LS_REMOTE_TIMEOUT,
        )
        if listed.returncode:
            self.fetch_failed(base)
        default, commits = None, {}
        for line in listed.stdout.splitlines():
            value, _, ref = line.partition("\t")
            if value.startswith("ref: ") and ref == "HEAD":
                target = value.removeprefix("ref: ").removeprefix("refs/heads/")
                default = target if REF.fullmatch(target) else None
            elif COMMIT.fullmatch(value):
                commits[ref] = value
        self.default = default
        if base is None and default is not None and "HEAD" in commits:
            # The HEAD line of the same advertisement is the default's commit.
            commits.setdefault(f"refs/heads/{default}", commits["HEAD"])
        if base is None:
            if default is None or "HEAD" not in commits:
                self.stop(
                    "unknown-base",
                    f"{self.repo} has no default branch",
                    "missing-base",
                    base="",
                    repo=self.repo,
                )
            base = default
            self.pin["base"] = base
            self.save_pin()  # N-06: only after the ls-remote that provides it.
        self.base = base
        base_commit = commits.get(f"refs/heads/{base}")
        if base_commit is None:
            self.stop(
                "unknown-base",
                f"{_text(base)} does not exist on {self.repo}",
                "missing-base",
                base=base,
                repo=self.repo,
            )
        published = commits.get(f"refs/heads/{self.branch}")
        missing = [c for c in {base_commit, published} - {None} if not self.has(c)]
        if missing:
            self.fetch(base, published is not None)
            base_commit = self.throwaway_value(
                "rev-parse", "--verify", "refs/sync/base"
            )
            if published is not None and self.branch != base:
                published = self.throwaway_value(
                    "rev-parse", "--verify", "refs/sync/published"
                )
            elif published is not None:
                published = base_commit
        self.base_after = base_commit
        self.published = published

    def throwaway_value(self, *args: str) -> str:
        result = self.throwaway(*args)
        value = result.stdout.strip()
        if result.returncode or not COMMIT.fullmatch(value):
            message = f"git {args[0]} failed"
            raise RuntimeError(message)
        return value

    def fetch(self, base: str, published: bool) -> None:  # noqa: FBT001
        """Fetch only what is missing; local commits are negotiation hints."""
        haves = [("head", self.head)]
        if self.base_before and self.has(self.base_before):
            haves.append(("base", self.base_before))
        for name, commit in haves:
            self.throwaway("update-ref", f"refs/haves/{name}", str(commit))
        specs = [f"+refs/heads/{base}:refs/sync/base"]
        if published and self.branch != base:
            specs.append(f"+refs/heads/{self.branch}:refs/sync/published")
        fetched = self.throwaway(
            "fetch",
            "--quiet",
            "--no-tags",
            "--no-write-fetch-head",
            self.url,
            *specs,
            network=True,
            timeout=NETWORK_TIMEOUT,
        )
        if fetched.returncode:
            self.fetch_failed(base)

    def fetch_failed(self, base: str | None) -> NoReturn:
        self.stop(
            "fetch-failed",
            f"could not fetch {_text(base or 'the default branch')} from {self.repo}",
            "fetch-failed",
            repo=self.repo,
        )

    # --- Git helpers ----------------------------------------------------------

    def is_ancestor(self, ancestor: str, descendant: str) -> bool:
        result = self.checkout("merge-base", "--is-ancestor", ancestor, descendant)
        if result.returncode not in {0, 1}:
            message = "git merge-base failed"
            raise RuntimeError(message)
        return result.returncode == 0

    def merge_base(self, one: str, other: str) -> str | None:
        result = self.checkout("merge-base", one, other)
        if result.returncode == 1:
            return None
        if result.returncode:
            message = "git merge-base failed"
            raise RuntimeError(message)
        return result.stdout.strip()

    def diff_tree(self, old: str, new: str, *paths: str) -> list[str]:
        args = ["diff-tree", "-r", "--name-only", "--no-renames", "-z", old, new]
        if paths:
            args += ["--", *paths]
        result = self.checkout(*args)
        if result.returncode:
            message = "git diff-tree failed"
            raise RuntimeError(message)
        return _split(result.stdout)

    def status(self, *flags: str) -> list[tuple[str, str]]:
        result = self.checkout(
            "status",
            "--porcelain=v1",
            "-z",
            # `none` would run `git status` inside each submodule, under its
            # own configuration's filters (SEC-001); `dirty` still reports a
            # changed gitlink.
            "--ignore-submodules=dirty",
            *flags,
        )
        if result.returncode:
            message = "git status failed"
            raise RuntimeError(message)
        return _status_entries(result.stdout)

    def dirty(self) -> list[str]:
        return [path for _, path in self.status("--untracked-files=normal")]

    def index_matches(self, commit: str) -> bool:
        result = self.checkout("diff-index", "--cached", "--quiet", commit, "--")
        if result.returncode not in {0, 1}:
            message = "git diff-index failed"
            raise RuntimeError(message)
        return result.returncode == 0

    def raw_commit(self, commit: str) -> bytes:
        result = self.throwaway("cat-file", "commit", commit, binary=True)
        if result.returncode:
            message = "git cat-file failed"
            raise RuntimeError(message)
        return result.stdout

    def tree_of(self, commit: str) -> str:
        return _headers(self.raw_commit(commit))["tree"][0]

    def identity_line(self) -> bytes:
        """Return the operator's committer, never the checkout's (F-12)."""
        if self.committer is None:
            result = self.throwaway("var", "GIT_COMMITTER_IDENT")
            line = result.stdout.strip()
            if result.returncode or not line or "\n" in line:
                self.stop("internal-error", "no committer identity", "no-committer")
            self.committer = line.encode("utf-8", "surrogateescape")
        return self.committer

    # --- recovery (R5 table) --------------------------------------------------

    def record_path(self) -> Path:
        assert self.state is not None  # noqa: S101
        return self.state / "branch-sync" / f"{_key(str(self.branch))}.json"

    def read_record(self) -> dict | None:
        path = self.record_path()
        try:
            data = _read_json(path)
        except (OSError, ValueError):
            data = False
        if data is None:
            return None
        if not self.valid_record(data):
            self.stop(
                "internal-error",
                "invalid write-ahead record",
                "invalid-record",
                record=path,
                branch=self.branch,
            )
        return data

    def valid_record(self, data: object) -> bool:
        if not isinstance(data, dict) or set(data) != RECORD_FIELDS:
            return False
        try:
            datetime.fromisoformat(str(data["written_at"]))
        except ValueError:
            return False
        return (
            data["branch"] == self.branch
            and all(
                isinstance(data[key], str) and COMMIT.fullmatch(data[key])
                for key in ("old_head", "new_head")
            )
            and all(
                data[key] is None
                or (isinstance(data[key], str) and COMMIT.fullmatch(data[key]))
                for key in ("published_old", "old_base", "new_base")
            )
            and (data["old_base"] is None) == (data["new_base"] is None)
            and isinstance(data["run_id"], str)
            and RUN_ID_PATTERN.fullmatch(data["run_id"]) is not None
            and isinstance(data["written_at"], str)
        )

    def write_record(self, old: str, new: str, published_old: str | None) -> None:
        _write_json(
            self.record_path(),
            {
                "branch": self.branch,
                "old_head": old,
                "new_head": new,
                "published_old": published_old,
                "old_base": self.sync_bases[0] if self.sync_bases else None,
                "new_base": self.sync_bases[1] if self.sync_bases else None,
                "run_id": self.run_id,
                "written_at": datetime.now(UTC).isoformat(),
            },
        )

    def clear_record(self) -> None:
        self.record_path().unlink(missing_ok=True)

    def recover(self) -> None:
        """Complete or clear a half-done sync on this branch, whatever run wrote it."""
        record = self.read_record()
        if record is None:
            return
        old, new = record["old_head"], record["new_head"]
        published_old = record["published_old"]
        records_push = published_old is not None and published_old != new
        for _ in range(3):
            local, published = self.branch_head(), self.published
            if not self.has(new) and published != new:
                break  # row 7: gone before it was referenced
            if local == new and (published == new or published_old is None):
                break  # row 1
            if local == new and published == published_old and records_push:
                self.completed(record)  # row 2: local moved, push missing
                self.holds = None
                self.push(new, lease=published_old)
                self.pushed = True
                self.published = new
                break
            if local == old and self.index_matches(new):
                self.completed(record)  # row 3: read-tree done, update-ref not
                self.update_ref(new, old)
                continue
            if local == old and self.index_matches(old):
                self.interrupted_update(old, new)  # row 3b blocks when it matches
            if local == old and published == new:
                self.completed(record)  # row 4: push done, local not
                self.holds = new
                self.overlap_from(record, old)
                self.mutate(old, new, observed=new, push=False, onto_base=False)
                return
            if (
                local != old
                and published == new
                and records_push
                and self.is_ancestor(old, local)
            ):
                self.completed(record)  # row 5: commits after the pushed sync
                self.holds = new
                self.overlap_from(record, old)
                # Attributes from the fetched base, never the feature (E-04).
                replayed = self.replay(
                    old, new, local, pushed=new, attributes=self.base_after
                )
                self.mutate(
                    local, replayed, observed=new, push=replayed != new, onto_base=False
                )
                return
            break  # rows 6 and 7: nothing landed, or someone else moved a branch
        self.clear_record()

    def completed(self, record: dict) -> None:
        self.recovered = True
        self.recovered_from = record["run_id"]

    def overlap_from(self, record: dict, old_head: str) -> None:
        """E-03: a completed replay still reports stale evidence."""
        old_base, new_base = record["old_base"], record["new_base"]
        if old_base is None or not (self.has(old_base) and self.has(new_base)):
            return
        self.sync_bases = (old_base, new_base)
        self.find_overlap(old_base, new_base, old_head)

    def interrupted_update(self, old: str, new: str) -> None:
        """Row 3b: `read-tree -m -u` died after writing part of the worktree."""
        entries = self.status("--untracked-files=all")
        if not entries:
            return
        changed = set(self.diff_tree(old, new))
        paths = []
        for _, path in entries:
            if path not in changed or not self.at_new_content(new, path):
                return
            paths.append(path)
        self.stop(
            "dirty",
            "an interrupted update left these files at the synchronized content: "
            + _paths(paths),
            "interrupted-update",
            new_head=new,
        )

    def at_new_content(self, new: str, path: str) -> bool:
        listed = self.checkout("ls-tree", "-z", new, "--", path)
        if listed.returncode:
            return False
        entry = listed.stdout.split("\0")[0]
        target = self.root / path
        if not entry:
            return not os.path.lexists(target)
        meta, _, name = entry.partition("\t")
        parts = meta.split()
        if name != path or len(parts) != 3 or parts[1] != "blob":  # noqa: PLR2004
            return False
        if not target.is_file() or target.is_symlink():
            return False
        hashed = self.checkout("hash-object", "--no-filters", "--", path)
        return hashed.returncode == 0 and hashed.stdout.strip() == parts[2]

    # --- classification (R4 steps 7-15) --------------------------------------

    def kind(self) -> str:
        if self.branch == self.base:
            return "base"
        if autonomy.is_feature_branch(
            str(self.branch), self.issue, self.base, self.default
        ):
            return "feature"
        return "other"

    def classify(self) -> Outcome:
        """R4 steps 7 to 15, after any pending record was completed or cleared."""
        assert self.head is not None  # noqa: S101
        assert self.base_after is not None  # noqa: S101
        kind = self.kind()
        if kind != "base":
            # On the base branch the published branch is the base: step 10.
            self.follow_published()
        if self.is_ancestor(self.base_after, self.head):
            return self.finish("synchronized" if self.recovered else "up-to-date")
        if kind == "base":
            return self.fast_forward_base()
        if kind == "other":
            detail = (
                f"{_text(self.branch)} is not the feature branch of #{self.issue}; "
                "Ballast rewrites only a branch named for the Issue"
                if self.issue is not None
                else "the run has no feature directory, so no Issue number"
            )
            self.stop(
                "not-feature-branch",
                detail,
                "not-feature-branch",
                branch=self.branch,
                feature_branch=self.feature_branch(),
            )
        return self.rebase_feature()

    def follow_published(self) -> None:
        """R4 step 8: fast-forward to the published branch (AC-015), or diverged."""
        assert self.head is not None  # noqa: S101
        published = self.published
        if published is None or published == self.head:
            return
        if self.is_ancestor(self.head, published):
            if self.dirty():
                self.note = (
                    "published branch is ahead; not fast-forwarded: uncommitted changes"
                )
                return
            # AC-015 never pushes: its record has published_old == new_head (P-01).
            self.mutate(
                self.head,
                published,
                observed=published,
                push=False,
                onto_base=False,
                source="published",
            )
            self.fast_forwarded = True
        elif not self.is_ancestor(published, self.head):
            self.stop(
                "diverged",
                f"{_text(self.branch)} and the published branch both have commits "
                f"the other lacks ({_short(self.head)} vs {_short(published)})",
                "diverged",
                remote=REMOTE,
                branch=self.branch,
            )

    def fast_forward_base(self) -> Outcome:
        """R4 step 10, DEC-0003: only fast-forward the base branch, never push it."""
        assert self.head is not None  # noqa: S101
        assert self.base_after is not None  # noqa: S101
        if not self.is_ancestor(self.head, self.base_after):
            self.stop(
                "diverged",
                f"{_text(self.branch)} is the base branch and has local commits",
                "base-branch",
                new_branch=self.feature_branch(),
            )
        if self.base_before is None:
            self.base_before = self.head
        self.mutate(
            self.head, self.base_after, observed=None, push=False, onto_base=True
        )
        self.fast_forwarded = True
        return self.finish("synchronized")

    def rebase_feature(self) -> Outcome:
        """R4 steps 11 to 15 for a feature branch behind its base."""
        assert self.head is not None  # noqa: S101
        assert self.base_after is not None  # noqa: S101
        paths = self.dirty()
        if paths:
            self.stop("dirty", f"uncommitted changes: {_paths(paths)}", "dirty")
        old_head = self.head
        old_base = self.old_base(old_head)
        new = self.replay(old_base, self.base_after, old_head)
        if new == self.base_after:
            self.fast_forwarded = True
        _crash("after-replay")
        self.sync_bases = (old_base, self.base_after)
        self.mutate(
            old_head,
            new,
            observed=self.published,
            push=self.published is not None,
            onto_base=True,
        )
        if self.base_before is None:
            self.base_before = old_base
        self.find_overlap(old_base, self.base_after, old_head)
        return self.finish("synchronized")

    def feature_branch(self) -> str:
        return Path(self.feature).name if self.feature else ""

    def old_base(self, head: str) -> str:
        """R8: the base the feature's commits were made on."""
        assert self.base_after is not None  # noqa: S101
        recorded = self.base_before
        if recorded and self.has(recorded):
            if self.is_ancestor(recorded, self.base_after):
                found = self.merge_base(head, self.base_after)
                if found:
                    return found
            elif self.is_ancestor(recorded, head):
                return recorded  # the base was force-pushed
        elif not recorded:  # A recorded base that is gone is unknown (R8, E-06).
            found = self.merge_base(head, self.base_after)
            if found:
                return found
        return self.stop(
            "diverged",
            "the base was rewritten and the old base is unknown",
            "base-rewritten",
            base=self.base,
        )

    def replay(
        self,
        old_base: str,
        new_base: str,
        head: str,
        *,
        pushed: str | None = None,
        attributes: str | None = None,
    ) -> str:
        """R2: replay old_base..head onto new_base without touching the checkout.

        `.gitattributes` come from `attributes`, by default new_base: always a
        fetched base, never the feature branch.
        """
        listed = self.checkout(
            "rev-list",
            "--reverse",
            "--topo-order",
            "--no-merges",
            f"{old_base}..{head}",
        )
        if listed.returncode:
            message = "git rev-list failed"
            raise RuntimeError(message)
        parent = new_base
        parent_tree = self.tree_of(parent)
        for commit in listed.stdout.split():
            if not COMMIT.fullmatch(commit):  # SEC-004: names are validated data.
                message = "git rev-list failed"
                raise RuntimeError(message)
            raw = self.raw_commit(commit)
            headers = _headers(raw)
            if not headers.get("parent"):
                self.stop(
                    "diverged",
                    "the base was rewritten and the old base is unknown",
                    "base-rewritten",
                    base=self.base,
                )
            original = headers["parent"][0]
            if not COMMIT.fullmatch(original):
                message = "malformed commit"
                raise RuntimeError(message)
            was_empty = headers["tree"][0] == self.tree_of(original)
            merged = self.throwaway(
                "merge-tree",
                "--write-tree",
                f"--merge-base={original}",
                "--name-only",
                "-z",
                parent,
                commit,
                attr_source=attributes or new_base,
            )
            parts = merged.stdout.split("\0")
            if merged.returncode == 1:
                self.conflict(commit, parts[1:], old_base, pushed)
            tree = parts[0].strip()
            if merged.returncode or not COMMIT.fullmatch(tree):
                message = "git merge-tree failed"
                raise RuntimeError(message)
            if tree == parent_tree and not was_empty:
                continue  # already upstream, as git rebase drops it
            text = _rewrite(raw, tree, parent, self.identity_line())
            written = self.throwaway(
                "hash-object", "-t", "commit", "-w", "--stdin", stdin=text
            )
            new = written.stdout.strip()
            if written.returncode or not COMMIT.fullmatch(new):
                message = "git hash-object failed"
                raise RuntimeError(message)
            parent, parent_tree = new, tree
        return parent

    def conflict(
        self, commit: str, names: list[str], old_base: str, pushed: str | None
    ) -> NoReturn:
        """Block on a replay conflict, naming the commit and its paths."""
        conflicts: list[str] = []
        for name in names:  # `--name-only -z` paths, then an empty separator
            if not name:
                break
            if name not in conflicts:
                conflicts.append(name)
        shown = _paths(conflicts, CONFLICT_PATHS)
        if pushed:  # Recovery row 5: commits made after a pushed sync.
            self.stop(
                "conflict",
                f"replaying {_short(commit)} onto the already pushed "
                f"{_short(pushed)} conflicts in {shown}",
                "conflict-pushed",
                new_head=pushed,
                old_head=old_base,
                branch=self.branch,
            )
        if self.published:  # The by-hand rebase rewrites a published branch.
            self.stop(
                "conflict",
                f"replaying {_short(commit)} conflicts in {shown}",
                "conflict-published",
                remote=REMOTE,
                base=self.base,
                branch=self.branch,
                published=self.published,
            )
        self.stop(
            "conflict",
            f"replaying {_short(commit)} conflicts in {shown}",
            "conflict",
            remote=REMOTE,
            base=self.base,
        )

    # --- R5: every mutation ---------------------------------------------------

    def mutate(  # noqa: PLR0913 - The R5 inputs, each explicit.
        self,
        old: str,
        new: str,
        *,
        observed: str | None,
        push: bool,
        onto_base: bool,
        source: str = "base",
    ) -> None:
        """Check, record, push, then move the checkout; never the other order."""
        # 1. Pre-mutation checks: nothing has changed yet when these block.
        if self.current_branch() != self.branch or self.branch_head() != old:
            self.stop("busy", None, "busy", branch=self.branch)
        paths = self.dirty()
        if paths:
            self.dirty_block("uncommitted changes", paths, files=False)
        changed = self.diff_tree(old, new)
        ignored = [
            path
            for code, path in self.status("--ignored=matching", "--untracked-files=all")
            if code == "!!"
        ]
        clobbered = [
            path
            for path in changed
            if any(
                path == entry or (entry.endswith("/") and path.startswith(entry))
                for entry in ignored
            )
        ]
        if clobbered:
            self.dirty_block(
                "ignored files would be overwritten", clobbered, files=True
            )
        dry = self.checkout("read-tree", "-m", "-u", "--dry-run", old, new)
        if dry.returncode:
            self.in_progress()
            refused = [
                line.strip()
                for line in dry.stderr.splitlines()
                if line.startswith("\t")
            ]
            self.dirty_block("untracked files are in the way", refused, files=True)
        names = [
            path
            for path in self.diff_tree(old, new, *launcher.BASES)
            if not any(
                path == skipped or path.startswith(skipped + "/")
                for skipped in launcher.SKIPPED
            )
            and path not in self.protected
        ]
        if names and not self.protected:
            self.protected_source = source
        self.protected += names
        # 2. Write-ahead record: published_old != new_head marks a push (P-01).
        self.write_record(old, new, observed)
        _crash("after-record")
        # 3. Push, published feature branch only, under a lease.
        if push and observed is not None and new != observed:
            _crash("before-push")
            self.push(new, lease=observed)
            self.pushed = True
            self.holds = new
            self.published = new
            _crash("after-push")
        # 4. Local update: index and worktree, then a compare-and-swap.
        moved = self.checkout("read-tree", "-m", "-u", old, new)
        if moved.returncode:
            self.in_progress()
            paths = self.dirty()
            if paths:
                self.dirty_block("uncommitted changes", paths, files=False)
            self.stop("busy", None, "busy", branch=self.branch)
        _crash("after-read-tree")
        self.update_ref(new, old)
        _crash("after-update-ref")
        # 5. Completion.
        if onto_base:
            self.pin["base_commit"] = str(self.base_after)
            self.save_pin()
        self.clear_record()
        self.holds = None
        self.sync_bases = None

    def dirty_block(self, what: str, paths: list[str], *, files: bool) -> NoReturn:
        detail = f"{what}: {_paths(paths)}" if paths else what
        if self.holds:
            # P-06, N-03: the next invocation completes the pushed sync.
            self.stop(
                "dirty",
                f"a previous synchronization already pushed {_short(self.holds)}; "
                + detail,
                "dirty-files-pushed" if files else "dirty-pushed",
            )
        self.stop("dirty", detail, "dirty-files" if files else "dirty")

    def update_ref(self, new: str, old: str) -> None:
        message = f"ballast: sync onto {self.base}"
        result = self.checkout(
            "update-ref", "-m", message, f"refs/heads/{self.branch}", new, old
        )
        if result.returncode:
            # P-04: someone moved the branch; drop only the sync's own output.
            if self.index_matches(new) and (
                self.checkout("diff-files", "--quiet").returncode == 0
            ):
                self.checkout("read-tree", "-m", "-u", new, "HEAD")
            self.stop("busy", None, "busy", branch=self.branch)
        self.head = new

    def push(self, new: str, *, lease: str) -> None:
        ref = f"refs/heads/{self.branch}"
        result = self.throwaway(
            "push",
            "--quiet",
            f"--force-with-lease={ref}:{lease}",
            self.url,
            f"{new}:{ref}",
            network=True,
            timeout=NETWORK_TIMEOUT,
        )
        if result.returncode == 0:
            return
        if "stale info" in result.stderr:
            self.stop(
                "diverged",
                "the published branch moved during the check",
                "diverged",
                remote=REMOTE,
                branch=self.branch,
            )
        rejected = not result.timed_out and (
            "[remote rejected]" in result.stderr
            or "hook declined" in result.stderr
            or "! [rejected]" in result.stderr
        )
        raise _Block(
            "push-failed",  # noqa: EM101 - The cause, not a message.
            f"pushing {_text(self.branch)} failed; a retry "
            f"{'cannot' if rejected else 'can'} succeed alone",
            _recovery(
                "push-rules" if rejected else "push-retry",
                rerun=self.rerun,
                repo=self.repo,
                branch=self.branch,
            ),
            retryable=not rejected,
        )

    # --- R4 steps 14 and 15 ---------------------------------------------------

    def recheck(self) -> None:
        """R9: the launcher's own protected-input comparison, after any HEAD move."""
        if self.head == self.head_before:
            return
        assert self.state is not None  # noqa: S101
        try:
            trusted = json.loads((self.state / launcher.TRUSTED).read_text("utf-8"))
        except (OSError, ValueError):
            trusted = {}
        current = launcher.trusted_inputs(self.root)
        changed = sorted(
            name
            for name in trusted.keys() | current.keys()
            if trusted.get(name) != current.get(name)
        )
        if not changed:
            return
        names = self.protected or changed
        source = "published branch" if self.protected_source == "published" else "base"
        self.stop(
            "protected-input",
            f"the {source} changed protected inputs: {_paths(names, PROTECTED_NAMES)}",
            "protected-input",
        )

    def find_overlap(self, old_base: str, new_base: str, old_head: str) -> None:
        """R11: files both the base and the feature changed, when evidence exists.

        Adds to what an earlier completion in the same check found.
        """
        if self.feature is None:
            return
        both = set(self.diff_tree(old_base, new_base)) & set(
            self.diff_tree(old_base, old_head)
        )
        if not both:
            return
        plan = bool(self.listing(old_head, f"{self.feature}/plan.md"))
        review = bool(self.listing(old_head, f"{self.feature}/reviews/"))
        if not review:
            try:
                events, _ = ledger.read(self.root, self.source_run or self.run_id)
            except (ledger.LedgerError, OSError, ValueError):
                events = []
            review = any(e["kind"] in {"review", "convergence"} for e in events)
        stale = {name for name, found in (("plan", plan), ("review", review)) if found}
        if stale:
            self.stale = sorted(stale | set(self.stale))
            self.overlap = sorted(both | set(self.overlap))

    def listing(self, commit: str, path: str) -> str:
        result = self.checkout("ls-tree", "-r", "--name-only", "-z", commit, "--", path)
        return result.stdout if result.returncode == 0 else ""

    def finish(self, outcome: str) -> Outcome:
        self.recheck()
        self.pin["base_commit"] = str(self.base_after)
        self.save_pin(final=True)
        synchronized = outcome == "synchronized"
        return Outcome(
            outcome,
            branch=self.branch,
            base_ref=self.base,
            base_before=self.base_before
            or (self.base_after if not synchronized else None),
            base_after=self.base_after,
            head_before=self.head_before,
            head_after=self.head,
            pushed=self.pushed if synchronized else None,
            fast_forwarded=self.fast_forwarded or None,
            recovered=True if synchronized and self.recovered else None,
            recovered_from=self.recovered_from
            if synchronized and self.recovered
            else None,
            note=self.note,
            **self.stale_fields(),
        )

    # --- recording ------------------------------------------------------------

    def event_run(self, outcome: Outcome) -> str:
        if outcome.outcome == "blocked" and self.source_run:
            return self.source_run  # N-07: a blocked continuation has no archive
        return self.run_id

    def record(self, outcome: Outcome) -> None:
        """Append the one `branch_sync` event, and the stale-evidence file."""
        if self.feature is None:
            message = "no feature directory"
            raise ValueError(message)
        data: dict[str, Any] = {"outcome": outcome.outcome}
        if outcome.cause:
            data["cause"] = outcome.cause
        if outcome.base_ref and REF.fullmatch(outcome.base_ref):
            data["base_ref"] = outcome.base_ref
        for key in ("base_before", "base_after", "head_before", "head_after"):
            value = getattr(outcome, key)
            if value and COMMIT.fullmatch(value):
                data[key] = value
        for key in (
            "pushed",
            "fast_forwarded",
            "recovered",
            "recovered_from",
            "retryable",
            "overlap",
            "stale_plan",
            "stale_review",
        ):
            value = getattr(outcome, key)
            if value is not None:
                data[key] = value
        run = self.event_run(outcome)
        event = ledger.new_event(
            run, self.feature, "branch_sync", "runner", data, self.event_id
        )
        if outcome.overlap:  # synchronized, or a kept protected-input sync
            # Operator state: an agent can neither plant nor hide it (SEC-003).
            _write_json(
                draft_pr.stale_dir(self.root, self.feature) / f"{self.event_id}.json",
                {
                    "event_id": self.event_id,
                    "run_id": run,
                    "feature": self.feature,
                    "observed_at": event["observed_at"],
                    "base_ref": self.base,
                    "base_before": self.base_before,
                    "base_after": self.base_after,
                    "stale": self.stale,
                    "paths": self.overlap[:OVERLAP_PATHS],
                    "truncated": len(self.overlap) > OVERLAP_PATHS,
                },
            )
        ledger.append(self.root, event)


def synchronize(  # noqa: PLR0913 - The contract's entry point.
    root: Path,
    run_id: str,
    *,
    feature: str | None,
    starting: bool = False,
    branch: str | None = None,
    base: str | None = None,
    source_run: str | None = None,
    rerun: str | None = None,
) -> Outcome:
    """Check, and when safe update, the run's branch; never raises (contract).

    Records exactly one `branch_sync` event. An unexpected failure, Ctrl-C or
    a failed record is `blocked` with cause `internal-error`. `rerun` replaces
    the command a recovery line ends with (a Chat step's `ballast run step`).
    """
    work = _Sync(
        root,
        run_id,
        feature=feature,
        starting=starting,
        branch=branch,
        base=base,
        source_run=source_run,
        rerun=rerun,
    )
    try:
        outcome = work.execute()
    except _Block as block:
        outcome = work.blocked(block)
    except KeyboardInterrupt:
        outcome = work.blocked(
            _Block(
                "internal-error",
                "interrupted",
                _recovery("internal-error", rerun=work.rerun),
                interrupted=True,
            )
        )
    except Exception as error:  # noqa: BLE001 - Any failure is one outcome.
        outcome = work.blocked(
            _Block(
                "internal-error",
                type(error).__name__,
                _recovery("internal-error", rerun=work.rerun),
            )
        )
    try:
        work.record(outcome)
    except (Exception, KeyboardInterrupt):  # noqa: BLE001 - No agent on an unrecorded check.
        if outcome.outcome != "blocked":
            if work.continuing:
                # N-07: a continuation that does not proceed leaves no pin.
                with contextlib.suppress(OSError, ValueError):
                    _pin_path(root, run_id).unlink(missing_ok=True)
            outcome = replace(
                outcome,
                outcome="blocked",
                cause="internal-error",
                detail="not recorded",
                recovery=_recovery("internal-error", rerun=work.rerun),
                pushed=None,
                fast_forwarded=None,
                recovered=None,
                recovered_from=None,
                overlap=None,
                stale_plan=None,
                stale_review=None,
                note=None,
            )
    return outcome
