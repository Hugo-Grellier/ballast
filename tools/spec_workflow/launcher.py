#!/usr/bin/python3 -IS
"""Trusted operator entry point for the ballast-feature workflow.

A headless agent can rewrite anything in the checkout, including run.py and
ledger.py, so they cannot check their own integrity. The global
`ballast` command (tools/ballast in the standard) runs this
file from the pinned standard version, outside the checkout, where no agent
can write. From the checkout root:

    ballast trust              # after reviewing the checkout
    ballast run start|resume ...
    ballast ledger snapshot|check|record ...
    ballast intake --repo OWNER/REPO ...   # the feature-intake helper
    ballast discard-runs       # after an unfinished agent step

`status --json` prints whether the workflow is installed and why `run` would
refuse, as `{"installed": bool, "refusal": null | "<reason>"}`, plus
`"baseline_source": "setup" | "trust"` once a trust baseline exists; it writes
nothing, so `ballast doctor` can call it before trust.

Every command except `status` takes the checkout lock shared, and refuses
while `ballast setup` holds it or left an unfinished attempt (its journal in
the state directory); `run`, `ledger` and `intake` keep the lock for as long
as the workflow tool runs, so setup never switches the installation under
them. They also refuse while the pin differs from the installed version.

`trust` records digests of every executable workflow input in your state
directory, and the repository `ballast.toml` pins as one you reviewed. `ballast
setup` and a worktree's first-command preparation record the same baseline when
the checkout holds exactly what they installed from reviewed configuration
(ADR-0014); the source is kept beside it and never affects the comparison.
`run`, `ledger` and `intake` refuse unless those inputs still match, no tamper
marker exists, and no agent step was left unfinished. This file uses only the
standard library and imports nothing from the checkout; agent.py imports its
digest helpers.
"""

from __future__ import annotations

import contextlib
import fcntl
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import tomllib
from datetime import UTC, datetime
from pathlib import Path

TAMPER_MARKER = "BALLAST_TAMPERED"
IN_PROGRESS = "in-progress"
TRUSTED = "trusted.json"
# Who recorded the baseline, bound to its exact bytes; display only (ADR-0014).
TRUSTED_SOURCE = "trusted-source.json"
# Machine-wide: the repositories `ballast trust` reviewed, identities only.
REVIEWED = "reviewed-repositories.json"
REVIEWED_LOCK = "reviewed-repositories.lock"
# Written by tools/setup in the state directory: its journal while an attempt
# is unfinished, its record of the installed content, and the checkout lock.
SETUP_ATTEMPT = "setup-attempt.json"
INSTALLATION = "installation.json"
CHECKOUT_LOCK = "checkout.lock"
CONFIG_LIMIT = 256 * 1024
STAMP = ".ballast/.setup-version"
UNFINISHED = "setup did not finish in this checkout; run `ballast setup` to recover"
SETUP_RUNNING = "ballast setup is running in this checkout; wait for it to finish"
NOT_INSTALLED = (
    "nothing is installed in this checkout; run `ballast setup`, or `ballast run`, "
    "`ledger` or `intake` to prepare it from a verified installation on this machine"
)
# Executable workflow inputs: the launcher's own tools, Spec Kit's engine
# configuration, extensions and scripts, and the environment validators and
# operator checks may run.
BASES = ("ballast.toml", ".ballast/spec_workflow", ".specify", ".venv")
# Written between steps by Spec Kit, the wrapper and validators, or holding no
# executable content; the wrapper checks run state around every agent step.
SKIPPED = (
    ".specify/feature.json",
    ".specify/extensions/.cache",
    ".specify/workflows/.cache",
    ".specify/workflows/runs",
    ".specify/workflow-state",
    ".specify/bugs",
)
# Agents run in a systemd user scope: a cgroup they cannot leave, because
# Codex's sandbox denies writes to /sys/fs/cgroup. Killing the scope stops every
# process the agent started, even after its wrapper was killed.
# A tag or commit of the standard; the same pattern as tools/ballast's REF.
REF = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}")
SCOPE = re.compile(r"ballast-agent-[A-Za-z0-9_.-]{1,200}\.scope")
# An agent step's unit is `ballast-agent-<run>-<step>.scope`, and every step
# name starts with its UTC stamp, so the stamp splits the run from the step.
STEP_SCOPE = re.compile(
    r"ballast-agent-(?P<run>[A-Za-z0-9_-]{1,64}?)-(?P<step>[0-9]{8}T[0-9]{6,12}Z-[A-Za-z0-9_.-]{1,120})\.scope"
)
SCOPE_SECONDS = 10.0
# `systemctl is-active` exit status for a stopped unit (3) or a collected one
# (4); a manager error exits 1 without a state.
UNIT_NOT_ACTIVE = frozenset({3, 4})
RUN_STATE = (".specify/workflows/runs", ".specify/workflow-state")
EXIT_REFUSED = 2
COMMANDS = {"run": ("-IS", "run.py"), "ledger": ("-IS", "ledger.py")}
# The intake helper acts with the operator's `gh` authority before any run, so
# it runs from this pinned standard, never from a checkout copy.
INTAKE = Path(__file__).resolve().parents[1] / "feature_intake.py"


TEMP_ROOTS = ("/tmp", "/var/tmp", "/dev/shm")  # noqa: S108 - Refused, never used.


def agent_temp_roots() -> tuple[Path, ...]:
    """Directories an agent may write outside the checkout.

    Codex's workspace-write sandbox allows /tmp and $TMPDIR; a program found
    there is as untrusted as one in a working tree.
    """
    names = {*TEMP_ROOTS, os.environ.get("TMPDIR", "")} - {""}
    return tuple(Path(name).resolve() for name in sorted(names))


def state_base(root: Path) -> Path:
    """Return the operator state directory every checkout shares, validated.

    Raises OSError when XDG_STATE_HOME points where an agent can write: the
    trust baseline and the in-progress marker would then be the agent's (#34).
    """
    base = Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local/state")
    resolved = base.resolve()
    if not base.is_absolute() or any(
        resolved.is_relative_to(writable)
        for writable in (root.resolve(), *agent_temp_roots())
    ):
        message = (
            f"state directory {base} is inside the checkout or a temp directory, "
            "which agents can write; set XDG_STATE_HOME elsewhere"
        )
        raise OSError(message)
    return base / "ballast"


def state_dir(root: Path) -> Path:
    """Per-checkout operator state, outside every agent's write authority."""
    key = hashlib.sha256(str(root.resolve()).encode()).hexdigest()[:16]
    return state_base(root) / key


def digests(root: Path, bases: list[Path], skip: list[Path]) -> dict[str, str]:
    """Hash every file and link under bases, never following a link."""
    found: dict[str, str] = {}
    for base in bases:
        for path in sorted(base.rglob("*")) if base.is_dir() else [base]:
            if any(path.is_relative_to(s) for s in skip):
                continue
            name = str(path.relative_to(root))
            if path.is_symlink():
                found[name] = "link:" + str(path.readlink())
            elif path.is_file():
                found[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return found


def _systemctl(*args: str) -> subprocess.CompletedProcess[str] | None:
    systemctl = shutil.which("systemctl")
    if systemctl is None:
        return None
    return subprocess.run(  # noqa: S603 - fixed arguments
        [systemctl, "--user", *args], capture_output=True, text=True, check=False
    )


def scope_available() -> bool:
    """Whether a systemd user manager can hold agent scopes."""
    result = _systemctl("show", "--property=Version")
    return result is not None and result.returncode == 0


def stop_scope(unit: str) -> bool:
    """Kill every process in an agent scope; True once the scope is gone."""
    if (
        not SCOPE.fullmatch(unit)
        or _systemctl("kill", "--signal=SIGKILL", unit) is None
    ):
        return False
    deadline = time.monotonic() + SCOPE_SECONDS
    while time.monotonic() < deadline:
        result = _systemctl("is-active", unit)
        # A manager error must not read as a stopped scope.
        if (
            result
            and result.returncode in UNIT_NOT_ACTIVE
            and result.stdout.strip() in {"inactive", "failed"}
        ):
            return True
        time.sleep(0.05)
    return False


def input_bases(root: Path) -> list[Path]:
    """BASES, plus a linked worktree's `.git` pointer file.

    Workflow tools run Git as the operator; a redirected pointer could select a
    forged repository whose configuration runs commands. A primary checkout's
    `.git` directory changes with every Git command and is left to the agent
    sandbox, which keeps it read-only.
    """
    git = root / ".git"
    extra = [git] if git.is_symlink() or git.is_file() else []
    return [root / base for base in BASES] + extra


def trusted_inputs(root: Path) -> dict[str, str]:
    """Digests of the executable inputs; bytecode is never read, so skip it."""
    state = digests(root, input_bases(root), [root / s for s in SKIPPED])
    return {name: v for name, v in state.items() if "__pycache__" not in name}


def read_record(root: Path, state: Path) -> dict | None:
    """Return the installation record while it describes the live installation.

    Every setup version writes the stamp; an older one run after a rollback
    rewrites it but not this record, which is then stale and ignored.
    """
    try:
        record = json.loads((state / INSTALLATION).read_text(encoding="utf-8"))
        stamp = (root / STAMP).read_text(encoding="utf-8").strip()
    except (OSError, ValueError):
        return None
    valid = (
        isinstance(record, dict)
        and record.get("schema") == 1
        and isinstance(record.get("ref"), str)
        and isinstance(record.get("files"), dict)
        and record.get("fingerprint") == stamp
    )
    return record if valid else None


def claim_in_progress(state: Path, unit: str) -> None:
    """Create the in-progress marker exclusively; refuse while another holds it.

    Two runs (Chat or headless) in one checkout must not overwrite each
    other's marker: the first to finish would clear the other's (SEC-009, #66).
    """
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
    try:
        fd = os.open(state / IN_PROGRESS, flags, 0o600)
    except FileExistsError:
        try:
            other = (state / IN_PROGRESS).read_text(encoding="utf-8").strip()
        except OSError:
            other = ""
        found = STEP_SCOPE.fullmatch(other)
        who = (
            f"run {found['run']}, step {found['step']}" if found else "an unknown step"
        )
        message = (
            f"another agent step is in progress ({who}); wait for it, or run "
            "`ballast discard-runs` if it died"
        )
        raise StepInProgressError(message) from None
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(unit + "\n")


class StepInProgressError(OSError):
    """Another agent step holds the checkout's in-progress marker."""


def write_atomic(path: Path, data: bytes) -> None:
    """Replace path with data, durably: a private temporary file, then rename."""
    fd, name = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.rename(name, path)  # noqa: PTH104 - tests observe the write order
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(name)  # noqa: PTH108
        raise
    directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def record_baseline(
    state: Path,
    inputs: dict[str, str],
    *,
    source: str,
    reference: dict | None = None,
) -> None:
    """Write the trust baseline and, first, the record of who wrote it.

    The only writer of `trusted.json`. It decides nothing about eligibility:
    `ballast trust` (the operator) and `setup_trust` (setup and preparation,
    under ADR-0014's conditions) call it. The provenance is bound to the exact
    baseline bytes, so a crash between the two writes leaves a record bound to a
    baseline that was never written, which reads as the old baseline's `trust`.
    Raises OSError; the caller reports it.
    """
    data = json.dumps(inputs, indent=1).encode()
    provenance = {
        "schema": 1,
        "source": source,
        "baseline": "sha256:" + hashlib.sha256(data).hexdigest(),
        "recorded": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    if source == "setup":
        provenance["reference"] = reference
    write_atomic(
        state / TRUSTED_SOURCE, (json.dumps(provenance, indent=1) + "\n").encode()
    )
    write_atomic(state / TRUSTED, data)


def _provenance(state: Path) -> tuple[bytes | None, dict | None]:
    """Return the baseline's bytes and its provenance if readable and bound."""
    try:
        data = (state / TRUSTED).read_bytes()
    except OSError:
        return None, None
    try:
        record = json.loads((state / TRUSTED_SOURCE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return data, None
    bound = (
        isinstance(record, dict)
        and record.get("schema") == 1
        and record.get("baseline") == "sha256:" + hashlib.sha256(data).hexdigest()
    )
    return data, record if bound else None


def baseline_source(state: Path) -> str | None:
    """Who recorded the baseline: None without one, else `setup` or `trust`.

    Display only: a missing, unreadable or unbound record reads as `trust`
    (FR-013), and the comparison never reads it (FR-015).
    """
    data, record = _provenance(state)
    if data is None:
        return None
    return "setup" if record and record.get("source") == "setup" else "trust"


def operator_baseline(state: Path) -> dict | None:
    """Return the baseline's path-to-digest map when the operator recorded it.

    Legacy baselines carry no provenance and can only be the operator's;
    unreadable or unbound provenance is not the operator's, so eligibility fails
    closed (research R7).
    """
    data, record = _provenance(state)
    if data is None:
        return None
    if record is None and os.path.lexists(state / TRUSTED_SOURCE):
        return None
    if record is not None and record.get("source") != "trust":
        return None
    try:
        baseline = json.loads(data)
    except ValueError:
        return None
    ok = isinstance(baseline, dict) and all(
        isinstance(k, str) and isinstance(v, str) for k, v in baseline.items()
    )
    return baseline if ok else None


REPOSITORY_NAME = re.compile(r"[A-Za-z0-9._-]{1,100}")


def split_repository(value: object) -> tuple[str, str] | None:
    """Split a `[github] repository` value into owner and name, or None."""
    if not isinstance(value, str):
        return None
    owner, _, name = value.partition("/")
    valid = all(
        REPOSITORY_NAME.fullmatch(part) and part not in {".", ".."}
        for part in (owner, name)
    )
    return (owner, name) if valid else None


def reviewed_repositories(root: Path) -> frozenset[str]:
    """Return the repositories `ballast trust` reviewed here, case-folded.

    Missing, unreadable, unknown-schema or malformed reads as empty. Holds
    identities only, never digests (FR-005, FR-010).
    """
    try:
        path = state_base(root) / REVIEWED
        found = json.loads(path.read_text(encoding="utf-8"))
        names = found["repositories"] if found["schema"] == 1 else []
    except (OSError, ValueError, KeyError, TypeError):
        return frozenset()
    valid = isinstance(names, list) and all(
        isinstance(n, str) and split_repository(n) for n in names
    )
    return frozenset(names) if valid else frozenset()


def add_reviewed(root: Path, repository: str) -> None:
    """Add a repository to the reviewed record, under a lock; raises OSError."""
    base = state_base(root)
    base.mkdir(parents=True, exist_ok=True, mode=0o700)
    flags = os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC
    lock = os.open(base / REVIEWED_LOCK, flags, 0o600)
    try:
        fcntl.flock(lock, fcntl.LOCK_EX)
        names = reviewed_repositories(root) | {repository.casefold()}
        document = {"schema": 1, "repositories": sorted(names)}
        write_atomic(base / REVIEWED, (json.dumps(document, indent=1) + "\n").encode())
    finally:
        os.close(lock)


def checkout_lock(state: Path, *, shared: bool) -> int | None:
    """Take the checkout lock without waiting; None while another holds it.

    The kernel releases an flock when its holder dies, so a killed setup or
    run never blocks the next one.
    """
    flags = os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC
    fd = os.open(state / CHECKOUT_LOCK, flags, 0o600)
    try:
        fcntl.flock(fd, (fcntl.LOCK_SH if shared else fcntl.LOCK_EX) | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(fd)
        return None
    return fd


def read_config(root: Path) -> str:
    """Read ballast.toml: never through a link, a regular file, at most 256 KiB."""
    path = root / "ballast.toml"
    data, reason = b"", "a symbolic link" if path.is_symlink() else None
    if reason is None:
        flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC
        with os.fdopen(os.open(path, flags), "rb") as handle:
            if stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
                data = handle.read(CONFIG_LIMIT + 1)
            else:
                reason = "not a regular file"
    if len(data) > CONFIG_LIMIT:
        reason = "larger than 256 KiB"
    if reason is not None:
        raise OSError(reason)
    return data.decode("utf-8")


def pinned_ref(root: Path) -> str | None:
    """Return the checkout's `[standard] ref`, or None unless it is a valid ref."""
    try:
        config = tomllib.loads(read_config(root))
    except (OSError, ValueError):
        return None
    standard = config.get("standard")
    ref = standard.get("ref") if isinstance(standard, dict) else None
    valid = isinstance(ref, str) and REF.fullmatch(ref) and ".." not in ref
    return ref if valid else None


def _setup_refusal(root: Path, state: Path) -> str | None:
    """Name an unfinished setup attempt, or a pin that differs from the installation."""
    if os.path.lexists(state / SETUP_ATTEMPT):
        return UNFINISHED
    record = read_record(root, state)
    pin = pinned_ref(root)
    if record is not None and pin is not None and record["ref"] != pin:
        installed = record["ref"]
        return (
            f'pinned {pin}, installed {installed}: restore ref = "{installed}" in '
            "ballast.toml, or fix the cause and rerun `ballast setup`"
        )
    return None


def _unfinished(marker: Path) -> str:
    """Return the unfinished-step refusal, naming the run and step if marked."""
    try:
        unit = marker.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError):
        unit = ""
    named = STEP_SCOPE.fullmatch(unit) if SCOPE.fullmatch(unit) else None
    if named is None:
        return "an agent step did not finish its protected-file check"
    return (
        f"an agent step is active or did not finish: run {named['run']}, step "
        f"{named['step']}; wait for it to end, or if no step is running, run "
        "`ballast discard-runs`"
    )


def _refusal(root: Path) -> str | None:
    try:
        state = state_dir(root)
    except OSError as error:
        return str(error)
    return _setup_refusal(root, state) or _trust_refusal(root, state)


def _trust_refusal(root: Path, state: Path) -> str | None:
    if os.path.lexists(root / TAMPER_MARKER):
        return f"{TAMPER_MARKER} exists: an agent changed protected files"
    if os.path.lexists(state / IN_PROGRESS):
        return _unfinished(state / IN_PROGRESS)
    try:
        trusted = json.loads((state / TRUSTED).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        present = [
            str(path.relative_to(root))
            for path in input_bases(root)
            if os.path.lexists(path)
        ]
        return (
            "no trusted baseline for this checkout; review its protected inputs "
            f"({', '.join(present)}), then run `ballast trust`"
        )
    current = trusted_inputs(root)
    changed = sorted(
        name
        for name in trusted.keys() | current.keys()
        if trusted.get(name) != current.get(name)
    )
    if changed:
        shown = ", ".join(changed[:10]) + (" ..." if len(changed) > 10 else "")  # noqa: PLR2004
        return (
            f"workflow inputs changed since `trust`: {shown}; "
            "review them, then run `trust`"
        )
    return None


def _remove_tree(root: Path, name: str) -> None:
    """Delete root/name without following a link anywhere on its path.

    An agent may have left processes behind or replaced a parent such as
    `.specify/workflows` with a link to an operator directory. Each parent is
    opened relative to the previous handle with O_NOFOLLOW, and rmtree with
    dir_fd refuses a linked leaf and never follows links inside the tree.
    """
    *parents, leaf = Path(name).parts
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in parents:
            flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
            child = os.open(part, flags, dir_fd=fd)
            os.close(fd)
            fd = child
        shutil.rmtree(leaf, dir_fd=fd)
    except FileNotFoundError:
        return
    finally:
        os.close(fd)


def _discard(root: Path, state: Path) -> int:
    """Stop a dead wrapper's agent, then drop the unverifiable saved runs."""
    marker = state / IN_PROGRESS
    if os.path.lexists(marker) and not stop_scope(marker.read_text().strip()):
        sys.stderr.write(
            "refusing to discard run state: the unfinished agent step's processes "
            "could not be confirmed stopped; reboot, then retry\n"
        )
        return EXIT_REFUSED
    try:
        for name in RUN_STATE:
            _remove_tree(root, name)
    except OSError as error:
        sys.stderr.write(
            f"refusing to discard run state: {error}; a path component may be "
            "a link, so inspect the checkout\n"
        )
        return EXIT_REFUSED
    (state / IN_PROGRESS).unlink(missing_ok=True)
    sys.stdout.write("discarded local run state; start a fresh run\n")
    return 0


def _trust(root: Path, state: Path) -> int:
    """Record the reviewed checkout as the baseline for later commands."""
    if os.path.lexists(root / TAMPER_MARKER):
        sys.stderr.write(f"restore the checkout and delete {TAMPER_MARKER}\n")
        return EXIT_REFUSED
    if os.path.lexists(state / IN_PROGRESS):
        # Saved run state is outside the baseline, so it cannot be vouched for.
        sys.stderr.write(
            "an agent step did not finish; review the checkout, then run "
            "`discard-runs` before `trust`\n"
        )
        return EXIT_REFUSED
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    inputs = trusted_inputs(root)
    record_baseline(state, inputs, source="trust")
    sys.stdout.write(f"trusted {len(inputs)} workflow inputs for {root}\n")
    _review_repository(root, inputs)
    return 0


def _review_repository(root: Path, inputs: dict[str, str]) -> None:
    """Remember the repository the trusted `ballast.toml` pins as reviewed.

    It decides which default branch setup may later count as reviewed
    (ADR-0014). Failing to write it leaves the baseline recorded: warn only.
    """
    try:
        text = read_config(root)
        digest = hashlib.sha256(text.encode()).hexdigest()
        github = (
            tomllib.loads(text).get("github")
            if digest == inputs.get("ballast.toml")
            else None
        )
    except (OSError, ValueError):
        return
    value = github.get("repository") if isinstance(github, dict) else None
    if split_repository(value) is None:
        return
    try:
        add_reviewed(root, value)
    except OSError as error:
        sys.stderr.write(
            f"could not record {value} as reviewed: {error}; setup will not "
            "trust its fresh checkouts\n"
        )


def _marked(root: Path) -> bool:
    """Whether an agent step's in-progress marker is left in operator state."""
    try:
        return os.path.lexists(state_dir(root) / IN_PROGRESS)
    except OSError:
        return False


def _hold(root: Path) -> str | None:
    """Hold the checkout lock shared until exit, or say why not.

    Inheritable, so it lasts through `execv` for as long as the workflow tool
    runs. Without a state directory no setup has ever run here, and the trust
    check refuses anyway; nothing is created then.
    """
    try:
        state = state_dir(root)
        fd = checkout_lock(state, shared=True) if state.is_dir() else -1
    except OSError as error:
        return str(error)
    if fd is None:
        return SETUP_RUNNING
    if fd >= 0:
        os.set_inheritable(fd, True)  # noqa: FBT003 - positional-only
    if os.path.lexists(state / SETUP_ATTEMPT):
        return UNFINISHED
    return None


def _status(root: Path, *, installed: bool) -> dict:
    """Return what `status --json` prints; it writes nothing."""
    try:
        state = state_dir(root)
    except OSError:
        state = None
    unfinished = state is not None and os.path.lexists(state / SETUP_ATTEMPT)
    status = {
        "installed": installed,
        "refusal": _refusal(root) if installed or unfinished else None,
    }
    source = None if state is None else baseline_source(state)
    # Present only once a baseline exists; an older launcher never has it.
    return status if source is None else {**status, "baseline_source": source}


def main(argv: list[str]) -> int:  # noqa: PLR0911 - one exit per refusal
    """Verify the checkout, then run a workflow tool or record a baseline."""
    root = Path.cwd()
    installed = (root / ".ballast/spec_workflow/run.py").is_file()
    if argv == ["status", "--json"]:
        sys.stdout.write(json.dumps(_status(root, installed=installed)) + "\n")
        return 0
    if not argv or argv[0] not in {*COMMANDS, "intake", "trust", "discard-runs"}:
        sys.stderr.write(__doc__ or "")
        return EXIT_REFUSED
    # Before the lock: an uninstalled checkout gets no state file (#15),
    # except that an unfinished agent step can always be discarded: setup
    # and preparation refuse until it is.
    stranded = argv[0] == "discard-runs" and not installed and _marked(root)
    if argv[0] in {"trust", "discard-runs"} and not installed and not stranded:
        sys.stderr.write(f"ballast: refusing: {NOT_INSTALLED}\n")
        return EXIT_REFUSED
    held = _hold(root)
    if held:
        sys.stderr.write(f"ballast: refusing: {held}\n")
        return EXIT_REFUSED
    if not installed and not stranded:
        sys.stderr.write(f"ballast: refusing: {NOT_INSTALLED}\n")
        return EXIT_REFUSED
    if argv[0] in {"trust", "discard-runs"}:
        state = state_dir(root)
        return _trust(root, state) if argv[0] == "trust" else _discard(root, state)
    reason = _refusal(root)
    if reason:
        sys.stderr.write(f"ballast: refusing: {reason}\n")
        return EXIT_REFUSED
    if argv[0] == "intake":
        flags, tool = "-IS", str(INTAKE)
    else:
        flags, script = COMMANDS[argv[0]]
        tool = str(root / ".ballast/spec_workflow" / script)
    os.execv(sys.executable, [sys.executable, flags, tool, *argv[1:]])  # noqa: S606
    return EXIT_REFUSED  # unreachable


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
