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
refuse, as `{"installed": bool, "refusal": null | "<reason>"}`; it writes
nothing, so `ballast doctor` can call it before trust.

Every command except `status` takes the checkout lock shared, and refuses
while `ballast setup` holds it or left an unfinished attempt (its journal in
the state directory); `run`, `ledger` and `intake` keep the lock for as long
as the workflow tool runs, so setup never switches the installation under
them. They also refuse while the pin differs from the installed version.

`trust` records digests of every executable workflow input in your state
directory. `run`, `ledger` and `intake` refuse unless those inputs still match, no
tamper marker exists, and no agent step was left unfinished. This file uses
only the standard library and imports nothing from the checkout; agent.py
imports its digest helpers.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import tomllib
from pathlib import Path

TAMPER_MARKER = "BALLAST_TAMPERED"
IN_PROGRESS = "in-progress"
TRUSTED = "trusted.json"
# Written by tools/setup in the state directory: its journal while an attempt
# is unfinished, its record of the installed content, and the checkout lock.
SETUP_ATTEMPT = "setup-attempt.json"
INSTALLATION = "installation.json"
CHECKOUT_LOCK = "checkout.lock"
STAMP = ".ballast/.setup-version"
UNFINISHED = "setup did not finish in this checkout; run `ballast setup` to recover"
SETUP_RUNNING = "ballast setup is running in this checkout; wait for it to finish"
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
SCOPE = re.compile(r"ballast-agent-[A-Za-z0-9_.-]{1,200}\.scope")
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


def state_dir(root: Path) -> Path:
    """Per-checkout operator state, outside every agent's write authority.

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
    key = hashlib.sha256(str(root.resolve()).encode()).hexdigest()[:16]
    return base / "ballast" / key


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


def pinned_ref(root: Path) -> str | None:
    """Return the `[standard] ref` of the checkout's ballast.toml, as data."""
    try:
        config = tomllib.loads((root / "ballast.toml").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    standard = config.get("standard")
    ref = standard.get("ref") if isinstance(standard, dict) else None
    return ref if isinstance(ref, str) else None


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
        return "an agent step did not finish its protected-file check"
    try:
        trusted = json.loads((state / TRUSTED).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "no trusted baseline; review the checkout, then run `trust`"
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
    (state / TRUSTED).write_text(json.dumps(inputs, indent=1), encoding="utf-8")
    sys.stdout.write(f"trusted {len(inputs)} workflow inputs for {root}\n")
    return 0


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


def main(argv: list[str]) -> int:  # noqa: PLR0911 - one exit per refusal
    """Verify the checkout, then run a workflow tool or record a baseline."""
    root = Path.cwd()
    installed = (root / ".ballast/spec_workflow/run.py").is_file()
    if argv == ["status", "--json"]:
        try:
            unfinished = os.path.lexists(state_dir(root) / SETUP_ATTEMPT)
        except OSError:
            unfinished = False
        refusal = _refusal(root) if installed or unfinished else None
        sys.stdout.write(
            json.dumps({"installed": installed, "refusal": refusal}) + "\n"
        )
        return 0
    if not argv or argv[0] not in {*COMMANDS, "intake", "trust", "discard-runs"}:
        sys.stderr.write(__doc__ or "")
        return EXIT_REFUSED
    held = _hold(root)
    if held:
        sys.stderr.write(f"ballast: refusing: {held}\n")
        return EXIT_REFUSED
    if not installed:
        sys.stderr.write(__doc__ or "")
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
