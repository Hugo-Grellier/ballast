#!/usr/bin/env python3
"""Headless agent wrapper for the ballast-feature and ballast-autonomous workflows.

Spec Kit 1.0.11 runs `claude -p ...` or `codex exec ...` for command steps and
only records the exit code. The launcher points SPECKIT_INTEGRATION_<KEY>_
EXECUTABLE at `bin/claude` / `bin/codex` (symlinks to this file), which:

- add the bounded permission model (never a permission or sandbox bypass);
- tee stdout/stderr to the terminal and to ignored run state;
- fail the step when the agent reports `RECONCILE_STATUS: BLOCKED_*`;
- fail the step when the agent changed run state, workflow machinery, their
  bytecode, or the checkout's virtual environment;
- stop every process the agent left behind before that check (Linux child
  subreaper), so a detached child cannot write after it;
- on a protected change, leave TAMPER_MARKER so the launcher refuses every
  later start or resume until the operator restores the checkout.

For an Autonomous run (operator run record with workflow ballast-autonomous)
it also refuses a run that is not active, enforces the wall-time and step
limits (EXIT_LIMIT), runs the agent under bubblewrap (autonomy.confined_argv),
and records which drafts the step created, so a recorder attributes each draft
to the step that wrote it. Human-gated runs keep the argv above unchanged.

Artifact validation steps remain the primary postcondition; this wrapper only
adds evidence and an early stop.
"""

from __future__ import annotations

import ctypes
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import BinaryIO

# Never read or write checkout bytecode, including for the import below.
sys.pycache_prefix = os.devnull

import autonomy  # noqa: E402
from launcher import (  # noqa: E402
    IN_PROGRESS,
    SCOPE,
    TAMPER_MARKER,
    digests,
    input_bases,
    scope_available,
    state_dir,
    stop_scope,
)

NOFOLLOW_WRITE = os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW

HERE = Path(__file__).resolve().parent
SETTINGS = HERE / "claude-settings.json"
RUN_ID = re.compile(r"[A-Za-z0-9_-]{1,64}")
BLOCKING = re.compile(r"^RECONCILE_STATUS: (BLOCKED_[A-Z_]+)\s*$", re.MULTILINE)
FORBIDDEN = (
    "dangerously",
    "bypassPermissions",
    "danger-full-access",
    "network_access",
)
EXIT_BLOCKED = 3
EXIT_TAMPERED = 4
EXIT_LIMIT = 5
EXIT_USAGE = 2
EXIT_INTERRUPTED = 130
PR_SET_CHILD_SUBREAPER = 36
# Python cannot read or write bytecode under a file, so this prefix makes every
# import compile from source and never touch a checkout __pycache__.
NO_BYTECODE = os.devnull
# Installed Spec Kit state that agents write. Everything else under .specify is
# engine configuration, extensions, scripts, templates, or the saved state of a
# run (any of which a later resume executes), so it is protected.
SPECIFY_WRITABLE = ("feature.json", "extensions/.cache", "workflows/.cache")
LOG_FILES = ("stdout.log", "stderr.log", "meta.json")
REAP_SECONDS = 10.0
INTERRUPT_GRACE_SECONDS = 5.0


def permission_args(integration: str, args: list[str]) -> list[str]:
    """Return argv with the bounded headless permission model."""
    if len(args) < 2 or args[0] not in {"-p", "exec"}:  # noqa: PLR2004
        message = f"unexpected {integration} invocation: {args[:1]}"
        raise ValueError(message)
    # args[1] is the prompt; any other token may come from EXTRA_ARGS.
    for token in (args[0], *args[2:]):
        if any(marker in token for marker in FORBIDDEN):
            message = f"refusing permission bypass flag {token!r}"
            raise ValueError(message)
    if integration == "claude":
        return [
            *args,
            "--permission-mode",
            "acceptEdits",
            "--permission-prompts",
            "none",
            "--setting-sources",
            "project",
            "--strict-mcp-config",
            "--settings",
            str(SETTINGS),
        ]
    # Pin network off: a user config could otherwise enable it for workspace-write.
    return [
        "exec",
        "--sandbox",
        "workspace-write",
        "--config",
        "sandbox_workspace_write.network_access=false",
        *args[1:],
    ]


def _real_executable(integration: str) -> str:
    own = HERE / "bin"
    path = os.pathsep.join(
        entry
        for entry in os.environ.get("PATH", "").split(os.pathsep)
        if entry and Path(entry).resolve() != own
    )
    found = shutil.which(integration, path=path)
    if found is None or Path(found).resolve() == Path(__file__).resolve():
        message = f"{integration} CLI not found on PATH"
        raise FileNotFoundError(message)
    return found


def _log_dir(root: Path, integration: str, prompt: str) -> tuple[Path, str]:
    run_id = os.environ.get("SPECKIT_WORKFLOW_RUN_ID", "")
    key = run_id if RUN_ID.fullmatch(run_id) else "no-run"
    command = re.sub(r"[^a-z0-9.-]", "", prompt.split(maxsplit=1)[0].lower()) or "agent"
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    path = (
        root
        / ".specify/workflow-state"
        / key
        / "agents"
        / f"{stamp}-{command}-{integration}"
    )
    path.mkdir(parents=True, exist_ok=True)
    return path, key


def _open_log(log_fd: int, name: str) -> BinaryIO:
    """Open a log file relative to a directory handle taken before the agent ran.

    The agent may later replace the directory path with a link; writes through
    this handle still land in the original directory.
    """
    return os.fdopen(os.open(name, NOFOLLOW_WRITE, 0o644, dir_fd=log_fd), "wb")


def _tee(
    source: BinaryIO, sink: BinaryIO, handle: BinaryIO, captured: list[bytes]
) -> None:
    with handle:
        for chunk in iter(lambda: source.read1(65536), b""):
            sink.write(chunk)
            sink.flush()
            handle.write(chunk)
            handle.flush()
            captured.append(chunk)


def _feature_directory(root: Path, key: str) -> str | None:
    inputs = root / ".specify/workflows/runs" / key / "inputs.json"
    try:
        return json.loads(inputs.read_text(encoding="utf-8"))["inputs"][
            "feature_directory"
        ]
    except (OSError, ValueError, KeyError, TypeError):
        return None


def _protected_state(root: Path, own_log: Path) -> dict[str, str]:
    """Hash workflow machinery and run state that no agent may change.

    Codex's workspace-write sandbox cannot deny paths, and run state is
    gitignored, so edits here would be invisible in the diff yet could skip
    gates on resume or neuter the validators. Spec Kit writes none of these
    while a command step runs. Bytecode is included because Python can load an
    unchecked-hash `.pyc` over changed source; the agent's Python never writes
    bytecode (PYTHONPYCACHEPREFIX). `.venv` is included because a `.pth` or
    module there runs in the operator's later unsandboxed commands, and
    `.specify` because the engine loads its configuration and extensions.
    """
    skip = [root / ".specify" / name for name in SPECIFY_WRITABLE]
    # The log files are written through handles (see _open_log); the directory
    # itself stays checked, so a swap for a link is caught.
    skip += [own_log / name for name in LOG_FILES]
    return digests(root, input_bases(root), skip)


def _become_subreaper() -> None:
    """Adopt the agent's orphans so none can outlive the wrapper's check."""
    if sys.platform != "linux":
        message = "process containment needs Linux (PR_SET_CHILD_SUBREAPER)"
        raise OSError(message)
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(PR_SET_CHILD_SUBREAPER, 1, 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), "prctl(PR_SET_CHILD_SUBREAPER) failed")


def _children() -> list[int]:
    own = str(os.getpid())
    found = []
    for stat in Path("/proc").glob("[0-9]*/stat"):
        try:
            fields = stat.read_text().rpartition(")")[2].split()
        except OSError:
            continue
        if fields[1] == own:
            found.append(int(stat.parent.name))
    return found


def _containment() -> tuple[str, list[str]]:
    """Prepare both process guards; return the systemd-run path and options.

    systemd 254 expands `$VAR` in the command line by default, which blanks a
    Codex prompt such as `$speckit-plan`. Turn that off where the option
    exists; an older or unreadable systemd-run keeps the scope, without it.
    """
    _become_subreaper()
    systemd_run = shutil.which("systemd-run")
    if systemd_run is None or not scope_available():
        message = "process containment needs a systemd user manager"
        raise OSError(message)
    try:
        usage = subprocess.run(  # noqa: S603 - resolved CLI, argument list
            [systemd_run, "--help"], capture_output=True, timeout=5, check=False
        ).stdout
    except (OSError, subprocess.TimeoutExpired):
        usage = b""
    if b"--expand-environment" in usage:
        return systemd_run, ["--expand-environment=no"]
    return systemd_run, []


def _stop_descendants() -> tuple[int, bool]:
    """Kill and reap every remaining descendant within REAP_SECONDS.

    Killing a process re-parents its children to this subreaper, so repeat
    until no child is left. Returns (reaped, complete); an unreapable process
    (for example one stuck in uninterruptible sleep) makes it incomplete.
    """
    reaped = 0
    deadline = time.monotonic() + REAP_SECONDS
    while time.monotonic() < deadline:
        for pid in _children():
            with suppress(ProcessLookupError):
                os.kill(pid, signal.SIGKILL)
        try:
            pid, _ = os.waitpid(-1, os.WNOHANG)
        except ChildProcessError:
            return reaped, True
        if pid:
            reaped += 1
        else:
            time.sleep(0.02)
    return reaped, False


def _mark_tampered(root: Path, reasons: list[str]) -> None:
    """Leave the launcher's stop marker without following a planted link.

    Any existing entry, even a dangling symlink, already blocks the launcher,
    so a failed exclusive create still fails closed.
    """
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
    with suppress(FileExistsError):
        handle = os.open(root / TAMPER_MARKER, flags, 0o600)
        with os.fdopen(handle, "w") as marker:
            marker.write("\n".join(reasons) + "\n")


class Refusal(Exception):
    """An Autonomous agent step refused before the agent started."""

    def __init__(self, code: int, message: str) -> None:
        """Keep the wrapper exit code with the reason."""
        super().__init__(message)
        self.code = code


def _workflow_id(root: Path, key: str) -> str | None:
    state = root / ".specify/workflows/runs" / key / "state.json"
    try:
        return json.loads(state.read_text(encoding="utf-8")).get("workflow_id")
    except (OSError, ValueError, AttributeError):
        return None


def _autonomous_run(root: Path, key: str) -> dict | None:
    """The active Autonomous run record for this step, or None if human-gated.

    Refuses (before any agent starts) an Autonomous run without a record, one
    that is not active, an exhausted limit, and a failed confinement
    self-test; otherwise counts the step.
    """
    try:
        record = autonomy.find_run(root, key)
    except autonomy.AutonomyError as error:
        raise Refusal(EXIT_USAGE, f"run record unreadable: {error}") from error
    if record is None:
        if _workflow_id(root, key) == "ballast-autonomous":
            message = (
                "autonomous run has no operator run record; start it with "
                "ballast run start --mode autonomous"
            )
            raise Refusal(EXIT_USAGE, message)
        return None
    if record["workflow"] != "ballast-autonomous":
        return None
    if record["status"] != "active":
        message = (
            f"run {key} is {record['status']}, not active; "
            + autonomy.RESUME_REFUSAL.format(run_id=key)
        )
        raise Refusal(EXIT_USAGE, message)
    if autonomy.remaining_seconds(record) <= 0:
        raise Refusal(EXIT_LIMIT, "wall-time limit exhausted")
    if record["agent_steps"] >= record["limits"]["max_agent_steps"]:
        raise Refusal(EXIT_LIMIT, "agent step limit exhausted")
    try:
        autonomy.confinement_self_test(root)
    except autonomy.AutonomyError as error:
        raise Refusal(EXIT_USAGE, str(error)) from error
    record["agent_steps"] += 1
    autonomy.write_run(root, record)
    return record


def _set_aside(root: Path, record: dict, step: str) -> list[str]:
    """Move drafts left by earlier steps out of the agent's reach."""
    directory = autonomy.drafts_dir(root, record["feature"])
    if directory.is_symlink() or not directory.is_dir():
        return []
    target = autonomy.run_dir(root, record["run_id"]) / "set-aside" / step
    moved = []
    for path in sorted(directory.iterdir()):
        target.mkdir(parents=True, exist_ok=True, mode=0o700)
        shutil.move(str(path), str(target / path.name))
        moved.append(path.name)
    return moved


def _created_drafts(root: Path, record: dict, step: str) -> dict[str, str]:
    """{name: sha256} of the drafts this step created, copied to operator state."""
    directory = autonomy.drafts_dir(root, record["feature"])
    if directory.is_symlink():
        return {"(drafts directory)": "invalid"}
    if not directory.is_dir():
        return {}
    created = {}
    for path in sorted(directory.iterdir()):
        if path.is_symlink() or not path.is_file():
            created[path.name] = "invalid"
            continue
        try:
            copy = autonomy.snapshot_draft(root, record["run_id"], step, path.name)
        except autonomy.AutonomyError:
            created[path.name] = "invalid"
            continue
        data = path.read_bytes()
        copy.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        copy.write_bytes(data)
        created[path.name] = hashlib.sha256(data).hexdigest()
    return created


def _role(prompt: str) -> str:
    return "reviewer" if "ballast-review" in prompt.split(maxsplit=1)[0] else "author"


def _review_exclusions(feature: str) -> tuple[str, ...]:
    return (f"{feature}/reviews", f"{feature}/autonomous/drafts")


def main() -> int:  # noqa: C901, PLR0912, PLR0915 - one guarded, linear agent step
    """Run the real agent CLI with bounded permissions and persistent logs."""
    integration = Path(sys.argv[0]).name
    if integration not in {"claude", "codex"}:
        sys.stderr.write("invoke through .ballast/spec_workflow/bin/{claude,codex}\n")
        return EXIT_USAGE
    try:
        argv = [
            _real_executable(integration),
            *permission_args(integration, sys.argv[1:]),
        ]
        systemd_run, scope_options = _containment()
    except (ValueError, OSError) as error:
        sys.stderr.write(f"spec workflow agent wrapper: {error}\n")
        return EXIT_USAGE

    root = Path.cwd()
    run_id = os.environ.get("SPECKIT_WORKFLOW_RUN_ID", "")
    try:
        record = _autonomous_run(root, run_id) if RUN_ID.fullmatch(run_id) else None
    except Refusal as refusal:
        sys.stderr.write(f"spec workflow agent wrapper: refusing: {refusal}\n")
        with suppress(autonomy.AutonomyError, OSError):
            if autonomy.find_run(root, run_id):
                autonomy.append_step(
                    root,
                    run_id,
                    {
                        "step": None,
                        "ran": False,
                        "exit_code": refusal.code,
                        "reason": str(refusal),
                        "at": autonomy.now(),
                    },
                )
        return refusal.code
    log_dir, key = _log_dir(root, integration, sys.argv[2])
    env = {**os.environ, "PYTHONPYCACHEPREFIX": NO_BYTECODE}
    private = None
    step_record: dict = {}
    if record is not None:
        feature = record["feature"]
        step_record = {
            "step": log_dir.name,
            "ran": True,
            "command": sys.argv[2].split(maxsplit=1)[0],
            "integration": integration,
            "role": _role(sys.argv[2]),
            "set_aside": _set_aside(root, record, log_dir.name),
            "tree_before": autonomy.tree_digest(root, _review_exclusions(feature)),
        }
        private = Path(tempfile.mkdtemp(prefix="ballast-agent-"))
        env = autonomy.confined_env(env, integration)
        argv = autonomy.confined_argv(
            root, argv, private=private, feature=feature, env=env
        )
    meta = {
        "run_id": key,
        "feature_directory": _feature_directory(root, key),
        "integration": integration,
        "command": sys.argv[2].split(maxsplit=1)[0],
        "argv": [Path(argv[0]).name, *argv[1:]],
        "started_at": datetime.now(UTC).isoformat(),
    }
    protected = _protected_state(root, log_dir)
    log_fd = os.open(log_dir, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    logs = {name: _open_log(log_fd, name) for name in LOG_FILES}
    meta_file = logs["meta.json"]
    os.close(log_fd)
    # Outside every agent's write authority: if the agent kills this wrapper
    # before the check below, the trusted launcher still refuses to continue.
    in_progress = state_dir(root) / IN_PROGRESS
    in_progress.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    unit = f"ballast-agent-{key}-{log_dir.name}.scope"
    if not SCOPE.fullmatch(unit):
        message = f"invalid agent scope name {unit!r}"
        raise ValueError(message)
    in_progress.write_text(unit + "\n")
    argv = [
        systemd_run,
        "--user",
        "--scope",
        "--quiet",
        "--collect",
        f"--unit={unit.removesuffix('.scope')}",
        *scope_options,
        "--",
        *argv,
    ]
    stdout: list[bytes] = []
    process = subprocess.Popen(  # noqa: S603 - resolved CLI, argument list
        argv,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    assert process.stdout is not None  # noqa: S101 - set by PIPE above
    assert process.stderr is not None  # noqa: S101 - set by PIPE above
    threads = [
        threading.Thread(
            target=_tee,
            args=(process.stdout, sys.stdout.buffer, logs["stdout.log"], stdout),
            daemon=True,
        ),
        threading.Thread(
            target=_tee,
            args=(process.stderr, sys.stderr.buffer, logs["stderr.log"], []),
            daemon=True,
        ),
    ]
    for thread in threads:
        thread.start()
    # An Autonomous step may only run until the run's deadline.
    timeout = (
        max(autonomy.remaining_seconds(record), 0.0) if record is not None else None
    )
    limit_hit = False
    try:
        exit_code = process.wait(timeout)
    except subprocess.TimeoutExpired:
        sys.stderr.write(
            "spec workflow agent wrapper: wall-time limit exhausted during the "
            "step; stopping the agent\n"
        )
        limit_hit = True
        exit_code = EXIT_LIMIT
    except KeyboardInterrupt:
        # The check below must run: ignore further interrupts, and stop an agent
        # that does not exit on its own.
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        try:
            process.wait(INTERRUPT_GRACE_SECONDS)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        exit_code = EXIT_INTERRUPTED
    # Before joining: a survivor holding the pipes would block the tee threads.
    scoped = stop_scope(unit)
    survivors, contained = _stop_descendants()
    contained = contained and scoped
    for thread in threads:
        # An unreapable survivor may hold a pipe open forever; do not wait on it.
        thread.join(None if contained else 1.0)

    blocked = BLOCKING.findall(b"".join(stdout).decode("utf-8", "replace"))
    if exit_code == 0 and blocked:
        sys.stderr.write(
            f"spec workflow agent wrapper: agent reported {blocked[0]}; "
            "failing this step\n"
        )
        exit_code = EXIT_BLOCKED
    after = _protected_state(root, log_dir)
    tampered = sorted(
        name
        for name in protected.keys() | after.keys()
        if protected.get(name) != after.get(name)
    )
    if not contained:
        tampered.append("(agent processes could not be stopped)")
    if tampered:
        sys.stderr.write(
            "spec workflow agent wrapper: agent changed protected workflow files; "
            f"failing this step: {', '.join(tampered)}\n"
            "Restore them, recreate .venv, and delete "
            f"{TAMPER_MARKER} before any other workflow command.\n"
        )
        _mark_tampered(root, tampered)
        exit_code = EXIT_TAMPERED
    else:
        in_progress.unlink(missing_ok=True)
    meta |= {
        "finished_at": datetime.now(UTC).isoformat(),
        "exit_code": exit_code,
        "blocking_status": blocked,
        "protected_changes": tampered,
        "stopped_descendants": survivors,
    }
    if record is not None:
        drafts = _created_drafts(root, record, log_dir.name)
        meta["drafts"] = drafts
        reason = "wall-time limit exhausted during the step" if limit_hit else None
        autonomy.append_step(
            root,
            record["run_id"],
            {
                **step_record,
                "drafts": drafts,
                "exit_code": exit_code,
                "blocking_status": blocked,
                "reason": reason,
                "at": autonomy.now(),
            },
        )
    if private is not None:
        shutil.rmtree(private, ignore_errors=True)
    with meta_file:
        meta_file.write((json.dumps(meta, indent=2) + "\n").encode())
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
