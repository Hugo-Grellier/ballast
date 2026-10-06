"""Decide whether setup or a worktree's preparation may record the trust baseline.

`ballast setup`, and the first `ballast run`, `ledger` or `intake` in a new
worktree, run this once their installation is complete (ADR-0014). They record
the baseline themselves only when the checkout holds exactly what they just
installed from configuration a human already reviewed and no agent has run
there; every other case records nothing and keeps needing `ballast trust`.

The conditions, in the order they are checked (the first failure is reported,
and nothing reaches the network before the last):

1. this standard is not inside the checkout (agents cannot write it);
2. no `BALLAST_TAMPERED` and no agent step's in-progress marker;
3. a baseline that already matches stays untouched;
4. no saved run state in the checkout and no unfinished operator-state run;
5. `ballast.toml` and the constitution are regular files read once;
6. every other protected input is what the installation record says;
7. a linked worktree's `.git` pointer names a worktree of its own repository;
8. both configuration files are committed and unchanged from `HEAD`;
9. both equal the checkout's earlier baseline recorded by `ballast trust`, or
   the pinned repository is one `ballast trust` reviewed and both equal its
   default branch, observed live in a throwaway repository with the operator's
   own Git authority and nothing from the checkout's Git configuration.

Standard library plus `launcher`, `ledger` and `autonomy` only; runs under
`python3 -I -S` from the pinned standard, never from a checkout copy.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import secrets
import shutil
import stat
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NoReturn

# Never read or write checkout bytecode; operator checks start under -I -S.
sys.pycache_prefix = os.devnull
sys.path.insert(0, str(Path(__file__).resolve().parent))

import autonomy  # noqa: E402
import launcher  # noqa: E402
import ledger  # noqa: E402

CONFIGS = ("ballast.toml", ".specify/memory/constitution.md")
READ_LIMIT = 256 * 1024
POINTER_LIMIT = 4096
GIT_FLOOR = (2, 41)
LOCAL_TIMEOUT = 30
LS_REMOTE_TIMEOUT = 30
FETCH_TIMEOUT = 120
MODES = ("setup", "prepare")
COMMIT = re.compile(r"[0-9a-f]{40}")
BLOB_MODES = frozenset({"100644", "100755"})
GIT_LOCATION = frozenset(
    {"GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR", "GIT_INDEX_FILE"}
)
# Variables that relocate Git's repository, objects or injected configuration.
DROPPED_ENV = frozenset(
    {
        *GIT_LOCATION,
        "GIT_OBJECT_DIRECTORY",
        "GIT_ALTERNATE_OBJECT_DIRECTORIES",
        "GIT_NAMESPACE",
        "GIT_CONFIG_PARAMETERS",
        "GIT_CONFIG_COUNT",
    }
)
NO_MAINTENANCE = (
    "-c",
    "maintenance.auto=false",
    "-c",
    "gc.auto=0",
    "-c",
    "core.commitGraph=false",
)
# `GIT_NO_LAZY_FETCH` only exists from Git 2.44. A local command must never
# lazy-fetch a missing object from a promisor remote the checkout's agent-writable
# configuration names, whatever the version: no transport is allowed.
NO_TRANSPORT = ("-c", "protocol.allow=never")
# Reasons are fixed phrases; checkout-derived values are filled in and escaped
# for display by the caller.
UNTRUSTED_STANDARD = (
    "setup runs from this checkout or a temp directory, which agents can write"
)
TAMPERED = (
    f"{launcher.TAMPER_MARKER} exists: an agent changed protected files; "
    "restore the checkout and delete it"
)
IN_PROGRESS = (
    "an agent step's marker exists; review the checkout, then run "
    "`ballast discard-runs`"
)
RUN_STATE = "saved run state shows agents ran here"
NO_RECORD = "the installation record is missing or does not match this setup"
POINTER = "the .git pointer does not name a worktree of this repository"
NOT_REVIEWED = "the pinned repository is not one you trusted on this machine"
NO_REPOSITORY = "ballast.toml names no valid [github] repository"
CHANGED = "protected inputs changed while setup checked them"
SETUP_REMEDY = (
    "Review the changed protected inputs, then run `ballast trust` "
    "before the next workflow run."
)
PREPARE_REMEDY = "Review this worktree's protected inputs, then run `ballast trust`."
# Test seam: a list every Git command appends (where, argv) to, when not None.
ARGV_LOG: list[tuple[str, list[str]]] | None = None


@dataclass(frozen=True)
class Verdict:
    """What setup tells the operator about the trust baseline."""

    kind: str  # "recorded", "kept" or "skipped"
    text: str  # the reference, the source or the reason
    count: int = 0
    mode: str = "setup"

    @property
    def reason_line(self) -> str:
        """The sentence for a skipped verdict."""
        return f"No trust baseline recorded: {self.text}."

    @property
    def remedy(self) -> str:
        """The operator's next step after a skipped verdict."""
        return PREPARE_REMEDY if self.mode == "prepare" else SETUP_REMEDY

    def lines(self) -> list[str]:
        """Return the verdict's lines for a recorded or kept baseline."""
        if self.kind == "recorded":
            return [
                (
                    f"Recorded the trust baseline for {self.count} protected "
                    f"inputs: ballast.toml and the constitution match {self.text}."
                ),
                "The next ballast run, ledger or intake needs no ballast trust.",
            ]
        if self.kind == "kept":
            who = (
                "you recorded with ballast trust"
                if self.text == "trust"
                else ("setup recorded")
            )
            return [f"The trust baseline {who} still matches; left unchanged."]
        return [self.reason_line, self.remedy]


class _Ineligible(Exception):  # noqa: N818 - control flow, not an error
    """A condition failed; the message is the reason."""


def _no(reason: str) -> NoReturn:
    """Stop: the checkout is not eligible, for this reason."""
    raise _Ineligible(reason)


@dataclass(frozen=True)
class Result:
    """One Git command's outcome; its output is parsed, never printed."""

    returncode: int
    stdout: bytes = b""
    stderr: str = ""
    timed_out: bool = False


# --- shared Git rules (branch synchronization uses the same ones) ------------


def repository_url(root: Path, owner: str, name: str, *, origin: str = "") -> str:  # noqa: ARG001
    """Return the pinned repository's URL, in the scheme `origin` uses.

    Only the scheme is read from `origin`; the repository never is.
    """
    if origin.startswith("https://"):
        return f"https://github.com/{owner}/{name}.git"
    return f"ssh://git@github.com/{owner}/{name}.git"


def child_path(root: Path, entries: list[str] | None = None) -> str:
    """PATH for Git and gh: gh runs git itself, so drop checkout entries too."""
    excluded = (root.resolve(), *ledger.agent_temp_roots())
    if entries is None:
        entries = os.environ.get("PATH", "").split(os.pathsep)
    return os.pathsep.join(ledger.trusted_entries(entries, excluded))


def base_environment(root: Path) -> dict[str, str]:
    """Return the environment of every operator Git command for a checkout."""
    env = {
        key: value
        for key, value in os.environ.items()
        if key not in DROPPED_ENV
        and not key.startswith(("GIT_CONFIG_KEY_", "GIT_CONFIG_VALUE_"))
    }
    env["PATH"] = child_path(root)
    # Replace refs and grafts in the agent-writable .git could make a branch
    # that lacks the base look up to date (SEC-004).
    env["GIT_NO_REPLACE_OBJECTS"] = "1"
    env["GIT_GRAFT_FILE"] = os.devnull
    return env


def throwaway_environment(root: Path) -> dict[str, str]:
    """Return the environment of a network command: it never prompts."""
    env = base_environment(root)
    for name in ("SSH_ASKPASS", "DISPLAY", "WAYLAND_DISPLAY"):
        env.pop(name, None)
    env |= {
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_NO_LAZY_FETCH": "1",
        # `push` failures are told apart by Git's English messages.
        "LC_ALL": "C",
        "GIT_ASKPASS": "",
        "SSH_ASKPASS_REQUIRE": "never",
    }
    return env


# --- reading the checkout ----------------------------------------------------


def _read_regular(path: Path, limit: int) -> bytes | None:
    """Read a regular file without following a link; None when absent."""
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC
    try:
        fd = os.open(path, flags)
    except FileNotFoundError:
        return None
    except OSError as error:
        message = "a symbolic link" if path.is_symlink() else str(error)
        raise OSError(message) from error
    with os.fdopen(fd, "rb") as handle:
        if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
            message = "not a regular file"
            raise OSError(message)
        data = handle.read(limit + 1)
    if len(data) > limit:
        message = f"larger than {limit // 1024} KiB"
        raise OSError(message)
    return data


def _skipped(name: str) -> bool:
    """Whether the launcher leaves this input out of its comparison."""
    path = Path(name)
    return "__pycache__" in path.parts or any(
        path.is_relative_to(skip) for skip in launcher.SKIPPED
    )


def _unfinished_runs(state: Path) -> bool:
    """Whether an operator-state run is not finished (research R11)."""
    runs = state / "runs"
    try:
        children = sorted(runs.iterdir()) if runs.is_dir() else []
    except OSError:
        return True
    for child in children:
        try:
            if not child.is_dir():
                return True
            entries = list(child.iterdir())
            if not entries:
                continue
            record = json.loads(_read_regular(child / "run.json", READ_LIMIT) or b"")
            if record.get("status") not in {"completed", "published", "continued"}:
                return True
        except (OSError, ValueError, AttributeError):
            return True
    return False


def _saved_runs(root: Path) -> bool:
    """Whether the checkout holds saved run state: any entry, even a link."""
    for name in launcher.RUN_STATE:
        path = root / name
        if path.is_symlink() or (path.exists() and not path.is_dir()):
            return True
        if path.is_dir() and any(path.iterdir()):
            return True
    return False


def _check_parents(root: Path, snapshot: dict[str, str]) -> None:
    """No directory above a protected input is a link (a copy outside the checkout).

    Setup's install path refuses linked parents; the launcher's digests follow
    them, so a `.specify` linked to an identical outside copy would otherwise be
    recorded and then edited from outside the checkout.
    """
    checked: set[str] = set()
    for name in sorted(snapshot):
        parts = Path(name).parts[:-1]
        for count in range(1, len(parts) + 1):
            parent = "/".join(parts[:count])
            if parent not in checked and (root / parent).is_symlink():
                _no(f"{parent} is a link, not a directory setup installed")
            checked.add(parent)


def _check_installation(
    root: Path, snapshot: dict[str, str], record: dict | None
) -> None:
    """Every other protected input is what the installation record lists."""
    if record is None:
        _no(NO_RECORD)
    _check_parents(root, snapshot)
    files = record["files"]
    for name in sorted(snapshot):
        if name in CONFIGS or name == ".git":
            continue
        if files.get(name) != snapshot[name]:
            _no(f"{name} was not written by setup")
    for name in sorted(files):
        under = name.startswith((".ballast/spec_workflow/", ".specify/"))
        differs = snapshot.get(name) != files[name]
        if under and differs and not _skipped(name) and name not in CONFIGS:
            _no(f"{name} was not written by setup")


def _check_pointer(root: Path, snapshot: dict[str, str]) -> None:
    """Require a linked worktree's `.git` pointer to name a worktree of its repo."""
    git = root / ".git"
    if git.is_symlink():
        _no(POINTER)
    if not git.is_file():
        return  # a primary checkout's `.git` directory is not a protected input
    try:
        data = _read_regular(git, POINTER_LIMIT) or b""
        if hashlib.sha256(data).hexdigest() != snapshot.get(".git"):
            _no(CHANGED)
        text = data.decode()
        match = re.fullmatch(r"gitdir: (/[^\n\0]+)\n?", text)
        if match is None:
            _no(POINTER)
        admin = Path(match[1]).resolve(strict=True)
        common = (
            admin / (_read_regular(admin / "commondir", 4096) or b"").decode().strip()
        ).resolve(strict=True)
        back = (_read_regular(admin / "gitdir", 4096) or b"").decode().strip()
    except (OSError, UnicodeDecodeError):
        _no(POINTER)
    outside = not any(
        common.is_relative_to(path)
        for path in (root.resolve(), *ledger.agent_temp_roots())
    )
    here = (root.resolve() / ".git") == Path(back).resolve()
    if not (admin == common / "worktrees" / admin.name and here and outside):
        _no(POINTER)


# --- local Git plumbing ------------------------------------------------------


def _run(  # noqa: PLR0913 - one bounded command
    argv: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    timeout: float,
    where: str,
    network: bool = False,
) -> Result:
    if ARGV_LOG is not None:
        ARGV_LOG.append((where, argv))
    try:
        done = subprocess.run(  # noqa: S603 - absolute Git, list argv
            argv,
            cwd=cwd,
            env=env,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=timeout,
            start_new_session=network,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return Result(-1, timed_out=True)
    except OSError:
        return Result(-1)
    return Result(done.returncode, done.stdout, done.stderr.decode("utf-8", "replace"))


def _git_program(root: Path) -> str:
    excluded = (root.resolve(), *ledger.agent_temp_roots())
    entries = os.environ.get("PATH", "").split(os.pathsep)
    git, _ = ledger.resolve_program("git", entries, excluded)
    if git is None:
        message = "git was not found outside working trees"
        _no(message)
    probe = _run(
        [git, "version"],
        cwd=root,
        env=base_environment(root),
        timeout=LOCAL_TIMEOUT,
        where="checkout",
    )
    found = re.match(rb"git version (\d+)\.(\d+)", probe.stdout)
    if found is None or (int(found[1]), int(found[2])) < GIT_FLOOR:
        message = "git 2.41 or later is required"
        _no(message)
    return git


class _Checkout:
    """Local, read-only Git plumbing in the checkout."""

    def __init__(self, root: Path, git: str) -> None:
        self.root = root
        self.git = git
        self.env = base_environment(root) | {
            "GIT_NO_LAZY_FETCH": "1",
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_CEILING_DIRECTORIES": str(root.resolve().parent),
        }

    def run(self, *args: str) -> Result:
        argv = [
            self.git,
            *autonomy.GIT_HARDENING,
            "-c",
            "core.commitGraph=false",
            *NO_TRANSPORT,
            *args,
        ]
        return _run(
            argv,
            cwd=self.root,
            env=self.env,
            timeout=LOCAL_TIMEOUT,
            where="checkout",
        )

    def object_format(self) -> str:
        result = self.run("rev-parse", "--show-object-format")
        found = result.stdout.decode().strip()
        if result.returncode or found not in {"sha1", "sha256"}:
            _no("the repository's object format is not readable")
        return found

    def head(self, path: str) -> str | None:
        """Return the blob ID `HEAD:<path>` names, or None when it names nothing."""
        result = self.run("rev-parse", "--verify", "--quiet", f"HEAD:{path}")
        found = result.stdout.decode().strip()
        return found if result.returncode == 0 and found else None


def _blob_id(data: bytes, algorithm: str) -> str:
    return hashlib.new(algorithm, b"blob %d\0" % len(data) + data).hexdigest()


def _check_committed(root: Path, git: str, configs: dict[str, bytes | None]) -> None:
    """Both configuration files are committed and unchanged from `HEAD`.

    `HEAD` lives in the agent-writable `.git`, so this is an early, precise
    refusal of uncommitted edits, not the authority: eligibility still needs a
    reviewed reference, which nothing in the checkout can supply.
    """
    checkout = _Checkout(root, git)
    algorithm = checkout.object_format()
    unborn = checkout.run("rev-parse", "--verify", "--quiet", "HEAD^{commit}")
    if unborn.returncode:
        _no("the checkout has no commit")
    for path, data in configs.items():
        committed = checkout.head(path)
        expected = None if data is None else _blob_id(data, algorithm)
        if committed != expected:
            _no(f"{path} has uncommitted changes")


# --- the default branch of the pinned repository ----------------------------


class _Unobservable(Exception):  # noqa: N818 - control flow, not an error
    """The default branch could not be read; the message is the cause."""


def _unseen(cause: str) -> NoReturn:
    """Stop: the default branch could not be observed, for this cause."""
    raise _Unobservable(cause)


def _observe(
    root: Path,
    state: Path,
    git: str,
    pinned: tuple[str, str],
    configs: dict[str, bytes | None],
) -> dict[str, Any]:
    """Return the default-branch reference both configuration files equal.

    Raises `_Unobservable` with a cause when it cannot be read, and
    `_Ineligible` when it differs. Only these commands run, all in a throwaway
    bare repository with its own object store, never the checkout's.
    """
    owner, name = pinned
    origin = _Checkout(root, git).run("remote", "get-url", "origin")
    url = repository_url(
        root,
        owner,
        name,
        origin=origin.stdout.decode().strip() if origin.returncode == 0 else "",
    )
    away = state / "setup-trust" / secrets.token_hex(8)
    # The checkout lock is ours: a scratch directory a killed setup left is stale.
    shutil.rmtree(away.parent, ignore_errors=True)
    away.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    bare = away / "reviewed.git"
    away.mkdir(mode=0o700)
    try:
        return _observe_in(root, git, bare, (url, f"{owner}/{name}"), configs)
    finally:
        shutil.rmtree(away, ignore_errors=True)


def _observe_in(  # noqa: C901 - one advertisement, read once
    root: Path,
    git: str,
    bare: Path,
    target: tuple[str, str],
    configs: dict[str, bytes | None],
) -> dict[str, Any]:
    url, repository = target
    base_env = throwaway_environment(root) | {
        "GIT_CEILING_DIRECTORIES": str(bare.parent)
    }
    prefix = [git, *autonomy.GIT_HARDENING, *NO_MAINTENANCE]

    def run(
        *args: str,
        timeout: float = LOCAL_TIMEOUT,
        network: bool = False,
        config: tuple[str, ...] = (),
    ) -> Result:
        env = dict(base_env)
        if args[0] != "init":
            env["GIT_DIR"] = str(bare)
        return _run(
            [*prefix, *(() if network else NO_TRANSPORT), *config, *args],
            cwd=bare.parent,
            env=env,
            timeout=timeout,
            where="throwaway",
            network=network,
        )

    made = run(
        "init", "--quiet", "--bare", "--template=", "--object-format=sha1", str(bare)
    )
    if made.returncode:
        _unseen("could not create a scratch repository")
    listed = run(
        "ls-remote", "--symref", url, "HEAD", timeout=LS_REMOTE_TIMEOUT, network=True
    )
    _failure(listed)
    branch, tip = None, None
    for line in listed.stdout.decode("utf-8", "replace").splitlines():
        value, _, ref = line.partition("\t")
        if value.startswith("ref: ") and ref == "HEAD":
            target = value.removeprefix("ref: ").removeprefix("refs/heads/")
            branch = target if ledger.REF.fullmatch(target) else None
        elif ref == "HEAD" and COMMIT.fullmatch(value):
            tip = value
    if branch is None or tip is None:
        _unseen("no default branch")
    fetched = run(
        "fetch",
        "--depth=1",
        "--no-tags",
        "--no-write-fetch-head",
        "--filter=blob:none",
        "reviewed",
        f"+refs/heads/{branch}:refs/reviewed/default",
        timeout=FETCH_TIMEOUT,
        network=True,
        config=(
            "-c",
            f"remote.reviewed.url={url}",
            "-c",
            "remote.reviewed.promisor=true",
            "-c",
            "remote.reviewed.partialclonefilter=blob:none",
        ),
    )
    _failure(fetched)
    found = run("rev-parse", "--verify", "refs/reviewed/default^{commit}")
    commit = found.stdout.decode().strip()
    if found.returncode or not COMMIT.fullmatch(commit):
        _unseen("no default branch")
    tree = run("ls-tree", "-z", commit, "--", *configs)
    if tree.returncode:
        _unseen("the default branch is unreadable")
    blobs: dict[str, str] = {}
    for entry in tree.stdout.decode("utf-8", "surrogateescape").split("\0"):
        meta, _, path = entry.partition("\t")
        fields = meta.split(" ")
        # A symbolic link or submodule is not the file (plan-review F-006).
        if len(fields) == 3 and fields[0] in BLOB_MODES and fields[1] == "blob":  # noqa: PLR2004
            blobs[path] = fields[2]
    same = all(
        blobs.get(path) == (None if data is None else _blob_id(data, "sha1"))
        for path, data in configs.items()
    )
    if not same:
        message = (
            f"differs from {repository}'s default branch and from your last "
            "trusted baseline"
        )
        _no(message)
    return {
        "kind": "default-branch",
        "repository": repository,
        "branch": branch,
        "commit": commit,
    }


def _failure(result: Result) -> None:
    """Raise `_Unobservable` with a short cause for a failed network command."""
    if result.timed_out:
        _unseen("timed out")
    if result.returncode:
        denied = re.search(
            r"Authentication failed|Permission denied|terminal prompts disabled"
            r"|could not read Username|Repository not found|access denied",
            result.stderr,
            re.IGNORECASE,
        )
        _unseen(
            "no access with your Git credentials"
            if denied
            else "offline or unreachable"
        )


# --- the decision ------------------------------------------------------------


def _default_branch(
    root: Path, state: Path, configs: dict[str, bytes | None], git: str
) -> dict[str, Any]:
    """Return the default-branch reference both configuration files equal, or raise.

    Counts only for a repository `ballast trust` reviewed on this machine.
    """
    pinned = None
    if configs["ballast.toml"] is not None:
        with contextlib.suppress(ValueError, UnicodeDecodeError):
            text = tomllib.loads(configs["ballast.toml"].decode())
            github = text.get("github")
            pinned = launcher.split_repository(
                github.get("repository") if isinstance(github, dict) else None
            )
    if pinned is None:
        _no(NO_REPOSITORY)
    repository = "/".join(pinned)
    if repository.casefold() not in launcher.reviewed_repositories(root):
        _no(NOT_REVIEWED)
    try:
        return _observe(root, state, git, pinned, configs)
    except _Unobservable as cause:
        message = f"could not read {repository}'s default branch: {cause}"
        _no(message)


def _precheck(root: Path, state: Path, standard: Path) -> None:
    """Refuse a standard an agent can write and any agent step's marker."""
    unsafe = (root.resolve(), *ledger.agent_temp_roots())
    if any(standard.resolve().is_relative_to(path) for path in unsafe):
        _no(UNTRUSTED_STANDARD)
    if os.path.lexists(root / launcher.TAMPER_MARKER):
        _no(TAMPERED)
    if os.path.lexists(state / launcher.IN_PROGRESS):
        _no(IN_PROGRESS)


def _read_configs(root: Path, snapshot: dict[str, str]) -> dict[str, bytes | None]:
    """Read both configuration files once; they must be the bytes snapshotted."""
    configs: dict[str, bytes | None] = {}
    for path in CONFIGS:
        try:
            data = _read_regular(root / path, READ_LIMIT)
        except OSError as error:
            message = f"{path} is not a regular file under 256 KiB ({error})"
            _no(message)
        digest = None if data is None else hashlib.sha256(data).hexdigest()
        if digest != snapshot.get(path):
            _no(CHANGED)
        configs[path] = data
    return configs


def _evaluate(
    root: Path, state: Path, record: dict | None, standard: Path, mode: str
) -> tuple[dict[str, str], dict[str, Any]] | Verdict:
    _precheck(root, state, standard)
    snapshot = launcher.trusted_inputs(root)
    held = None
    if mode == "setup":
        with contextlib.suppress(OSError, ValueError):
            held = json.loads((state / launcher.TRUSTED).read_text("utf-8"))
    if held == snapshot:
        return Verdict(
            "kept", launcher.baseline_source(state) or "trust", len(snapshot)
        )
    if _saved_runs(root) or _unfinished_runs(state):
        _no(RUN_STATE)
    configs = _read_configs(root, snapshot)
    _check_installation(root, snapshot, record)
    _check_pointer(root, snapshot)
    git = _git_program(root)
    _check_committed(root, git, configs)
    # A preparation installs a checkout that held nothing, so it never opens a
    # baseline in its state: one there predates it (ADR-0011, AC-008).
    earlier = launcher.operator_baseline(state) if mode == "setup" else None
    if earlier is not None and all(
        earlier.get(path) == snapshot.get(path) for path in CONFIGS
    ):
        return snapshot, {"kind": "operator-baseline"}
    return snapshot, _default_branch(root, state, configs, git)


def _describe(reference: dict[str, Any]) -> str:
    if reference["kind"] == "operator-baseline":
        return "the baseline you recorded with ballast trust"
    return (
        f"{reference['repository']}'s default branch {reference['branch']} at "
        f"{reference['commit'][:12]}"
    )


def _record(
    root: Path, state: Path, snapshot: dict[str, str], reference: dict[str, Any]
) -> None:
    """Write the baseline; undo it, restoring the previous one, on any doubt."""
    paths = [state / launcher.TRUSTED, state / launcher.TRUSTED_SOURCE]
    previous = [path.read_bytes() if path.exists() else None for path in paths]
    try:
        launcher.record_baseline(state, snapshot, source="setup", reference=reference)
        if launcher.trusted_inputs(root) != snapshot:
            _no(CHANGED)
    except BaseException:
        for path, data in zip(paths, previous, strict=True):
            if data is None:
                path.unlink(missing_ok=True)
            else:
                launcher.write_atomic(path, data)
        raise


def settle(
    root: Path, state: Path, record: dict | None, *, standard: Path, mode: str
) -> Verdict:
    """Record the baseline when eligible and say what happened; never raises.

    `record` is the installation record just written or verified, `standard`
    the directory this setup runs from. An ineligible checkout, an unreadable
    reference or a failed write returns `skipped` and leaves any earlier
    baseline untouched.
    """
    try:
        decided = _evaluate(root, state, record, standard, mode)
        if isinstance(decided, Verdict):
            return Verdict(decided.kind, decided.text, decided.count, mode)
        snapshot, reference = decided
        _record(root, state, snapshot, reference)
    except _Ineligible as reason:
        return Verdict("skipped", str(reason), mode=mode)
    except Exception as error:  # noqa: BLE001 - the installation is already committed
        return Verdict("skipped", f"could not record it ({error})", mode=mode)
    return Verdict("recorded", _describe(reference), len(snapshot), mode)
