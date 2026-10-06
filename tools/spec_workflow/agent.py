#!/usr/bin/env python3
"""Headless agent wrapper for the ballast-feature and ballast-autonomous workflows.

Spec Kit 1.0.11 runs `claude -p ...` or `codex exec ...` for command steps and
only records the exit code. The launcher points SPECKIT_INTEGRATION_<KEY>_
EXECUTABLE at `bin/claude` / `bin/codex` (symlinks to this file), which:

- add the bounded permission model (never a permission or sandbox bypass);
- tee stdout/stderr to the terminal and to ignored run state;
- fail the step when the agent reports `RECONCILE_STATUS: BLOCKED_*`;
- exit EXIT_AUTH, with the remedy, when the agent CLI cannot authenticate;
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
import fcntl
import hashlib
import json
import os
import re
import select
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import termios
import threading
import time
import tty
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import BinaryIO

# Never read or write checkout bytecode, including for the import below.
sys.pycache_prefix = os.devnull

import artifacts  # noqa: E402
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
# Each agent CLI's own login errors: its token expired or was refused (#65,
# #76). Codex prints `ERROR: ` before a failed refresh or a refused request.
AUTH_FAILURES = {
    "claude": re.compile(
        rb"^(?:Failed to authenticate|Not logged in|Invalid API key)\b", re.MULTILINE
    ),
    "codex": re.compile(
        rb"^ERROR: (?:Failed to refresh token|Your (?:access token|authentication "
        rb"session) could not be refreshed|unexpected status 401 Unauthorized)",
        re.MULTILINE,
    ),
}
AUTH_REASONS = {
    "claude": "the claude CLI could not authenticate: its login expired or was "
    "refused. Sign in again outside the sandbox (run `claude` once, or "
    "`claude /login`)",
    "codex": "the codex CLI could not authenticate: its login expired or was "
    "refused. Sign in again outside the sandbox (run `codex login`)",
}
SETTINGS = HERE / "claude-settings.json"
# The Chat-only additions to the headless rules (#20 contracts/step-runner.md).
CHAT_SETTINGS = HERE / "claude-chat-settings.json"
GUARD = HERE / "guard"
# Read-only commands a confined Claude step may also run (#37). Bubblewrap,
# not these rules, bounds what they can reach; the denials only keep `find`
# from running or deleting anything, as `ls` and `cat` cannot.
CONFINED_ALLOW = tuple(
    f"Bash({command}{rest})"
    for command in ("ls", "cat", "head", "tail", "wc", "find")
    for rest in ("", " *")
)
CONFINED_DENY = tuple(
    f"Bash(find *{action}*)"
    for action in ("-exec", "-ok", "-delete", "-fprint", "-fls")
)
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
EXIT_AUTH = 6
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
# The operator ends an interactive step with Ctrl-] twice within a second.
ESCAPE_BYTE = 0x1D
ESCAPE_SECONDS = 1.0
HANGUP_GRACE_SECONDS = 2.0
# Leave the alternate screen; mouse, focus and bracketed-paste reports off;
# cursor shown; normal keypad; default colors (#20 SEC-006).
TERMINAL_RESET = (
    b"\x1b[?1049l\x1b[?1000l\x1b[?1002l\x1b[?1003l\x1b[?1004l\x1b[?1006l"
    b"\x1b[?2004l\x1b[?25h\x1b>\x1b[0m"
)


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
    # Pin network off and the writable roots to the checkout and temp roots: a
    # user config could otherwise widen workspace-write (#34).
    return [
        "exec",
        "--sandbox",
        "workspace-write",
        "--config",
        "sandbox_workspace_write.network_access=false",
        "--config",
        "sandbox_workspace_write.writable_roots=[]",
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


def _containment(root: Path) -> tuple[str, list[str]]:
    """Prepare both process guards; return the systemd-run path and options.

    systemd 254 expands `$VAR` in the command line by default, which blanks a
    Codex prompt such as `$speckit-plan`. Turn that off where the option
    exists; an older or unreadable systemd-run keeps the scope, without it.
    """
    _become_subreaper()
    # Like gh and git: never a copy an agent could have written (ADR-0003).
    systemd_run, shadowed = autonomy.trusted_program("systemd-run", root)
    if systemd_run is None and shadowed:
        message = (
            "process containment refuses systemd-run found only in a working "
            "tree or temp directory; put the system one on PATH"
        )
        raise OSError(message)
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


class Refusal(Exception):  # noqa: N818 - a refusal, not an error
    """An Autonomous agent step refused before the agent started."""

    def __init__(self, code: int, message: str, limit: str | None = None) -> None:
        """Keep the wrapper exit code and, for a limit, its kind with the reason."""
        super().__init__(message)
        self.code = code
        self.limit = limit


def _workflow_id(root: Path, key: str) -> str | None:
    state = root / ".specify/workflows/runs" / key / "state.json"
    try:
        return json.loads(state.read_text(encoding="utf-8")).get("workflow_id")
    except (OSError, ValueError, AttributeError):
        return None


def _autonomous_record(root: Path, key: str) -> dict | None:
    """Return the active Autonomous run record, or None if the run is human-gated.

    Refuses (before any agent starts) an Autonomous run without a record and
    one that is not active.
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
            f"run {key} is {record['status']}, not active; only the operator's "
            f"ballast run resume {key} makes a stopped Autonomous run active again"
        )
        raise Refusal(EXIT_USAGE, message)
    return record


def _autonomous_run(root: Path, key: str) -> dict | None:
    """Return the active Autonomous run record for this step, or None if human-gated.

    Refuses (before any agent starts) an Autonomous run without a record, one
    that is not active, an exhausted limit, and a failed confinement
    self-test; otherwise counts the step. Every attempt counts (#21 R4).
    """
    record = _autonomous_record(root, key)
    if record is None:
        return None
    if autonomy.remaining_seconds(record) <= 0:
        raise Refusal(EXIT_LIMIT, "wall-time limit exhausted", "wall-time")
    if record["agent_steps"] >= record["limits"]["max_agent_steps"]:
        raise Refusal(EXIT_LIMIT, "agent step limit exhausted", "agent-steps")
    try:
        autonomy.confinement_self_test(root)
    except autonomy.AutonomyError as error:
        raise Refusal(EXIT_USAGE, str(error)) from error
    record["agent_steps"] += 1
    autonomy.write_run(root, record)
    return record


def _command(prompt: str) -> tuple[str, str | None]:
    """(command, first argument) of a prompt: `/speckit-x a` -> (speckit-x, a)."""
    words = prompt.split()
    name = words[0].lstrip("/$").replace(".", "-") if words else ""
    return name, words[1] if len(words) > 1 else None


# Fix-cycle agent steps and the fix state each one needs (#21 R1).
FIX_CYCLE_GATES = {
    ("speckit-ballast-fix", None): "fix-pending",
    ("speckit-ballast-review", "implementation-recheck"): "review-pending",
    ("speckit-ballast-review", "specialists-recheck"): "review-pending",
}


def _skip(record: dict, prompt: str) -> str | None:
    """Why a fix-cycle step has nothing to do, or None when it runs.

    Read from the operator record before any limit check: a skipped step
    starts no agent, counts no step and records nothing.
    """
    name, argument = _command(prompt)
    needed = FIX_CYCLE_GATES.get((name, None if name.endswith("-fix") else argument))
    state = autonomy.fix_state(record)["state"]
    if needed is None or state == needed:
        return None
    return f"{name} {argument or ''}".strip() + f" skipped: the fix state is {state}"


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


# --- Interactive Chat steps (#20) ---------------------------------------------
#
# `chat.run_step` is the only caller. The agent runs with the headless rules,
# denied anything that would prompt, under bubblewrap and a systemd scope,
# behind a pty this wrapper owns: the agent's controlling terminal is that
# pty, and it holds no descriptor to the operator's terminal, which this
# wrapper relays (contracts/step-runner.md, D-3).


def chat_settings() -> dict:
    """Return an interactive Claude step's settings: every headless rule, plus Chat's.

    The installed `claude-settings.json` already holds the project's
    `[agents.permissions]` rules (tools/setup merges them), so its allow and
    deny lists come first; `claude-chat-settings.json` adds `Edit`/`Write`
    for `dontAsk` and disables the bypass and auto modes. A deny list is
    therefore always a superset of the headless one.
    """
    headless = json.loads(SETTINGS.read_text(encoding="utf-8"))
    chat = json.loads(CHAT_SETTINGS.read_text(encoding="utf-8"))
    merged = {**chat, "permissions": dict(chat["permissions"])}
    for key in ("allow", "deny"):
        merged["permissions"][key] = list(
            dict.fromkeys(
                [
                    *headless["permissions"].get(key, []),
                    *chat["permissions"].get(key, []),
                ]
            )
        )
    # The hook runs this trusted interpreter by absolute path: a `python3`
    # shadowed on PATH, or one that cannot start, would not block (SEC-003).
    for group in merged.get("hooks", {}).get("PreToolUse", []):
        for hook in group["hooks"]:
            hook["command"] = hook["command"].replace(
                "python3 ", f"{shlex.quote(sys.executable)} ", 1
            )
    return merged


def interactive_argv(
    integration: str,
    executable: str,
    prompt: str,
    model: str | None = None,
    *,
    settings: str = ".ballast/spec_workflow/claude-chat-settings.json",
) -> list[str]:
    """Return the interactive agent argv: deny without prompting, never a bypass.

    `settings` is the step's generated settings file (`chat_settings`),
    relative to the checkout root the agent runs in.
    """
    for token in (prompt, model or ""):
        if any(marker in token for marker in FORBIDDEN):
            message = f"refusing permission bypass flag {token!r}"
            raise ValueError(message)
    chosen = ["--model", model] if model else []
    if integration == "claude":
        # The prompt precedes the variadic tool lists, which would take it.
        return [
            executable,
            "--permission-mode",
            "dontAsk",
            "--setting-sources",
            "project",
            "--strict-mcp-config",
            "--settings",
            settings,
            *chosen,
            prompt,
            "--allowedTools",
            *CONFINED_ALLOW,
            "--disallowedTools",
            *CONFINED_DENY,
        ]
    if integration == "codex":
        return [
            executable,
            "--sandbox",
            "workspace-write",
            "--ask-for-approval",
            "never",
            "--config",
            "sandbox_workspace_write.network_access=false",
            "--config",
            "sandbox_workspace_write.writable_roots=[]",
            *chosen,
            prompt,
        ]
    message = f"unknown integration {integration!r}"
    raise ValueError(message)


def _copy_size(source: int, target: int) -> None:
    """Give the step's pty the operator terminal's window size."""
    with suppress(OSError):
        size = fcntl.ioctl(source, termios.TIOCGWINSZ, b"\0" * 8)
        fcntl.ioctl(target, termios.TIOCSWINSZ, size)


def _take_terminal() -> None:
    """In the agent's child, after setsid: the pty slave on fd 0 is its terminal."""
    fcntl.ioctl(0, termios.TIOCSCTTY, 0)


def _write_all(fd: int, data: bytes) -> None:
    while data:
        try:
            written = os.write(fd, data)
        except BlockingIOError:
            select.select([], [fd], [], 1.0)
            continue
        data = data[written:]


class _Escape:
    """Ctrl-] twice within a second ends the step; a lone Ctrl-] is forwarded."""

    def __init__(self) -> None:
        self.held_at: float | None = None

    def feed(self, data: bytes) -> tuple[bytes, bool]:
        """Return the bytes to forward and whether the escape was typed."""
        forward = bytearray()
        for byte in data:
            now = time.monotonic()
            if self.held_at is not None and now - self.held_at > ESCAPE_SECONDS:
                forward.append(ESCAPE_BYTE)
                self.held_at = None
            if byte == ESCAPE_BYTE:
                if self.held_at is not None:
                    return bytes(forward), True
                self.held_at = now
                continue
            if self.held_at is not None:
                forward.append(ESCAPE_BYTE)
                self.held_at = None
            forward.append(byte)
        return bytes(forward), False

    def expired(self) -> bytes:
        """Return a held Ctrl-] whose second press never came, to forward now."""
        if (
            self.held_at is not None
            and time.monotonic() - self.held_at > ESCAPE_SECONDS
        ):
            self.held_at = None
            return bytes([ESCAPE_BYTE])
        return b""


def _end_session(process: subprocess.Popen, unit: str) -> None:
    """Hang up the agent's session, then kill what is left of it and its scope."""
    for number, wait in ((signal.SIGHUP, HANGUP_GRACE_SECONDS), (signal.SIGKILL, 5.0)):
        with suppress(ProcessLookupError, PermissionError):
            os.killpg(process.pid, number)
        try:
            process.wait(wait)
        except subprocess.TimeoutExpired:
            continue
        else:
            return
    stop_scope(unit)


def run_interactive(  # noqa: C901, PLR0912, PLR0913, PLR0915 - one session, every input explicit
    root: Path,
    *,
    integration: str,
    prompt: str,
    model: str | None,
    feature: str,
    unit: str,
    stdout_log: BinaryIO,
    settings: str,
) -> dict:
    """Run one interactive, confined agent session behind a wrapper-owned pty.

    The session ends when the agent exits, when the operator types Ctrl-]
    twice, or on SIGHUP, SIGTERM or SIGINT; then the scope is stopped and
    every descendant reaped before this returns, and later signals are
    ignored. The operator's terminal attributes are restored on every path.
    Returns exit_code (None when interrupted), interrupted, scope_stopped,
    stopped_descendants and argv (program names only).
    """
    if not SCOPE.fullmatch(unit):
        message = f"invalid agent scope name {unit!r}"
        raise ValueError(message)
    argv = interactive_argv(
        integration, _real_executable(integration), prompt, model, settings=settings
    )
    systemd_run, scope_options = _containment(root)
    env = {**os.environ, "PYTHONPYCACHEPREFIX": NO_BYTECODE}
    git, _ = autonomy.trusted_program("git", root)
    if git is not None:
        env["BALLAST_GIT"] = git
        env["PATH"] = os.pathsep.join((str(GUARD), env.get("PATH", "")))
    private = Path(tempfile.mkdtemp(prefix="ballast-agent-"))
    stdin_fd, stdout_fd = sys.stdin.fileno(), sys.stdout.fileno()
    saved = termios.tcgetattr(stdin_fd) if os.isatty(stdin_fd) else None
    ending: dict[str, int | None] = {"signal": None}

    def on_signal(number: int, _frame: object) -> None:
        ending["signal"] = number
        if saved is not None:
            with suppress(termios.error):
                termios.tcsetattr(stdin_fd, termios.TCSADRAIN, saved)

    handlers = {
        number: signal.signal(number, on_signal)
        for number in (signal.SIGHUP, signal.SIGTERM, signal.SIGINT)
    }
    master = slave = -1
    process = None
    interrupted = False
    try:
        confined = autonomy.confined_argv(
            root,
            argv,
            private=private,
            feature=feature,
            env=env,
            interactive_pty=True,
            readonly_extra=(".claude", ".codex"),
        )
        env = autonomy.confined_env(env, integration)
        command = [
            systemd_run,
            "--user",
            "--scope",
            "--quiet",
            "--collect",
            f"--unit={unit.removesuffix('.scope')}",
            *scope_options,
            "--",
            *confined,
        ]
        master, slave = os.openpty()
        if saved is not None:
            _copy_size(stdin_fd, slave)
        process = subprocess.Popen(  # noqa: S603 - resolved CLI, argument list
            command,
            stdin=slave,
            stdout=slave,
            stderr=slave,
            env=env,
            start_new_session=True,
            preexec_fn=_take_terminal,  # noqa: PLW1509 - no threads in this wrapper
            close_fds=True,
        )
        os.close(slave)
        slave = -1
        signal.signal(signal.SIGWINCH, lambda *_: _copy_size(stdin_fd, master))
        if saved is not None:
            tty.setraw(stdin_fd)
        escape = _Escape()
        reading = True
        while True:
            if ending["signal"] is not None:
                interrupted = True
                break
            sources = [master, stdin_fd] if reading else [master]
            try:
                ready, _, _ = select.select(sources, [], [], 0.2)
            except InterruptedError:
                continue
            if master in ready:
                try:
                    data = os.read(master, 65536)
                except OSError:
                    data = b""
                if not data:
                    break
                _write_all(stdout_fd, data)
                stdout_log.write(data)
                stdout_log.flush()
            if stdin_fd in ready:
                try:
                    data = os.read(stdin_fd, 4096)
                except OSError:
                    data = b""
                if not data:
                    reading = False
                else:
                    forward, typed = escape.feed(data)
                    if forward:
                        _write_all(master, forward)
                    if typed:
                        interrupted = True
                        break
            held = escape.expired()
            if held:
                _write_all(master, held)
            if process.poll() is not None and master not in ready:
                break
    finally:
        if saved is not None:
            # Undo modes the agent may have left on, and drop pending input
            # (late answers to its terminal queries) before the shell reads.
            with suppress(OSError):
                _write_all(stdout_fd, TERMINAL_RESET)
            with suppress(termios.error):
                termios.tcsetattr(stdin_fd, termios.TCSAFLUSH, saved)
        for number in handlers:
            signal.signal(number, signal.SIG_IGN)
        signal.signal(signal.SIGWINCH, signal.SIG_DFL)
        if slave >= 0:
            os.close(slave)
        if process is not None and process.poll() is None:
            interrupted = True
            _end_session(process, unit)
        scoped = stop_scope(unit) if process is not None else True
        survivors, contained = _stop_descendants()
        if master >= 0:
            with suppress(OSError):
                while select.select([master], [], [], 0)[0]:
                    data = os.read(master, 65536)
                    if not data:
                        break
                    stdout_log.write(data)
            os.close(master)
        shutil.rmtree(private, ignore_errors=True)
    stdout_log.flush()
    return {
        "exit_code": None if interrupted else process.returncode,
        "interrupted": interrupted,
        "scope_stopped": scoped and contained,
        "stopped_descendants": survivors,
        "argv": [Path(command[0]).name, *command[1:]],
    }


QUOTED = re.compile(r"'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\"")
MESSAGE_LIMIT = 500
RETRY_NOTE = (
    "\n\nBallast retry {n} of {total}: the trusted recorder refused the draft you "
    "wrote:\n{message}\nWrite a corrected draft. Keep within the stated limits. "
    "Paraphrase and cite any human approval you rely on; never quote approval "
    "wording."
)


def _retry_message(error: Exception) -> str:
    """Make a validator message fit for a prompt and the record (#21 R4, T043).

    Quoted draft values are dropped, approval wording and workflow markers
    replaced, and the text made printable and cut to MESSAGE_LIMIT
    characters: field names, IDs and limits remain, never draft content.
    """
    text = QUOTED.sub(
        lambda match: match.group(0) if match.group(0) == "'..'" else "<value>",
        str(error),
    )
    text = autonomy.HUMAN_APPROVAL.sub("<approval wording>", text)
    text = autonomy.WORKFLOW_MARKER.sub("<marker>", text)
    text = "".join(c if c.isprintable() else "?" for c in text)
    return text[:MESSAGE_LIMIT]


def _check_drafts(root: Path, record: dict, prompt: str, entry: dict) -> str | None:
    """Run the recorders' draft contract; the refusal to retry on, or None.

    Only a DraftError is retried. Any other refusal is left to the recorder,
    which decides as it always did.
    """
    try:
        feature = artifacts.Feature(root, record["feature"], record["run_id"])
        feature.run_id = record["run_id"]
        feature.run = record
        artifacts.check_step_drafts(
            feature, prompt, entry, blocked=entry["exit_code"] == EXIT_BLOCKED
        )
    except artifacts.DraftError as error:
        return _retry_message(error)
    except (
        artifacts.ContractError,
        autonomy.AutonomyError,
        OSError,
        ValueError,
        KeyError,
        TypeError,
    ):
        return None
    return None


def _move_refused(root: Path, record: dict, step: str, attempt: int) -> None:
    """Keep a refused attempt's drafts in operator state, out of the agent's reach."""
    directory = autonomy.drafts_dir(root, record["feature"])
    if directory.is_symlink() or not directory.is_dir():
        return
    target = (
        autonomy.run_dir(root, record["run_id"])
        / "set-aside"
        / step
        / f"retry-{attempt}"
    )
    for path in sorted(directory.iterdir()):
        target.mkdir(parents=True, exist_ok=True, mode=0o700)
        shutil.move(str(path), str(target / path.name))


def _refuse_step(root: Path, run_id: str, refusal: Refusal) -> int:
    """Report a refusal before any agent started, with a step entry when possible."""
    sys.stderr.write(f"spec workflow agent wrapper: refusing: {refusal}\n")
    with suppress(autonomy.AutonomyError, OSError):
        if autonomy.find_run(root, run_id):
            entry = {
                "step": None,
                "ran": False,
                "exit_code": refusal.code,
                "reason": str(refusal),
                "at": autonomy.now(),
            }
            if refusal.limit:
                entry["limit"] = refusal.limit
            autonomy.append_step(root, run_id, entry)
    return refusal.code


def main() -> int:  # noqa: C901, PLR0911 - one guarded step, its attempts
    """Run the real agent CLI with bounded permissions and persistent logs."""
    integration = Path(sys.argv[0]).name
    if integration not in {"claude", "codex"}:
        sys.stderr.write("invoke through .ballast/spec_workflow/bin/{claude,codex}\n")
        return EXIT_USAGE
    args = sys.argv[1:]
    try:
        real = _real_executable(integration)
        permission_args(integration, args)
        systemd_run, scope_options = _containment(Path.cwd())
    except (ValueError, OSError) as error:
        sys.stderr.write(f"spec workflow agent wrapper: {error}\n")
        return EXIT_USAGE

    root = Path.cwd()
    run_id = os.environ.get("SPECKIT_WORKFLOW_RUN_ID", "")
    prompt = args[1]
    try:
        found = _autonomous_record(root, run_id) if RUN_ID.fullmatch(run_id) else None
    except Refusal as refusal:
        return _refuse_step(root, run_id, refusal)
    if found is not None:
        # Before any limit check or step count (#21 T011).
        skipped = _skip(found, prompt)
        if skipped is not None:
            sys.stdout.write(f"spec workflow agent wrapper: {skipped}\n")
            return 0
    refusals: list[str] = []
    attempt = 1
    while True:
        try:
            record = _autonomous_run(root, run_id) if found is not None else None
        except Refusal as refusal:
            if refusals and refusal.code == EXIT_LIMIT:
                label = autonomy.LIMIT_LABELS[refusal.limit or "agent-steps"]
                refusal = Refusal(
                    EXIT_LIMIT,
                    f"{label} exhausted after a refused draft: {refusals[-1]}",
                    refusal.limit,
                )
            return _refuse_step(root, run_id, refusal)
        argv = [real, *permission_args(integration, [args[0], prompt, *args[2:]])]
        exit_code, entry = _attempt(
            root,
            integration=integration,
            argv=argv,
            scope=(systemd_run, scope_options),
            record=record,
            prompt=prompt,
        )
        if record is None:
            return exit_code
        refused = (
            _check_drafts(root, record, prompt, entry)
            if exit_code in {0, EXIT_BLOCKED}
            else None
        )
        entry |= {"attempt": attempt, "refusals": list(refusals)}
        if refused is None:
            autonomy.append_step(root, record["run_id"], entry)
            return exit_code
        refusals.append(refused)
        entry["refused"] = refused
        sys.stderr.write(
            f"spec workflow agent wrapper: the recorder would refuse this draft: "
            f"{refused}\n"
        )
        if attempt > autonomy.DRAFT_RETRIES:
            reason = autonomy.limit_condition(
                "retries",
                f"draft refused after {autonomy.DRAFT_RETRIES} retries: {refused}",
            )
            entry |= {"exit_code": EXIT_LIMIT, "reason": reason, "limit": "retries"}
            autonomy.append_step(root, record["run_id"], entry)
            sys.stderr.write(f"spec workflow agent wrapper: {reason}\n")
            return EXIT_LIMIT
        autonomy.append_step(root, record["run_id"], entry)
        _move_refused(root, record, entry["step"], attempt)
        prompt = args[1] + RETRY_NOTE.format(
            n=attempt, total=autonomy.DRAFT_RETRIES, message=refused
        )
        attempt += 1


def _attempt(root: Path, **kwargs: object) -> tuple[int, dict]:
    """Run `_attempt_in` with a private directory that never outlives it.

    The directory holds the step's copies of the agent logins (access tokens),
    so it is removed however the attempt ends (#65 SEC-002).
    """
    with tempfile.TemporaryDirectory(
        prefix="ballast-agent-", ignore_cleanup_errors=True
    ) as private:
        return _attempt_in(root, private=Path(private), **kwargs)  # type: ignore[arg-type]


def _attempt_in(  # noqa: C901, PLR0912, PLR0913, PLR0915 - one guarded, linear agent run
    root: Path,
    *,
    private: Path,
    integration: str,
    argv: list[str],
    scope: tuple[str, list[str]],
    record: dict | None,
    prompt: str,
) -> tuple[int, dict]:
    """Run the agent once; return its exit code and, for Autonomous, its step entry.

    The entry is not appended here: the caller first checks the drafts.
    """
    systemd_run, scope_options = scope
    log_dir, key = _log_dir(root, integration, prompt)
    env = {**os.environ, "PYTHONPYCACHEPREFIX": NO_BYTECODE}
    # Every `git` the agent runs goes through guard/git first (#34).
    git, _ = autonomy.trusted_program("git", root)
    if git is not None:
        env["BALLAST_GIT"] = git
        env["PATH"] = os.pathsep.join((str(GUARD), env.get("PATH", "")))
    step_record: dict = {}
    if record is not None:
        feature = record["feature"]
        step_record = {
            "step": log_dir.name,
            "ran": True,
            "command": prompt.split(maxsplit=1)[0],
            "integration": integration,
            "role": _role(prompt),
            "set_aside": _set_aside(root, record, log_dir.name),
            "tree_before": autonomy.tree_digest(root, _review_exclusions(feature)),
            "reviews_before": autonomy.reviews_digest(root, feature),
        }
        if integration == "claude":
            argv += [
                "--allowedTools",
                *CONFINED_ALLOW,
                "--disallowedTools",
                *CONFINED_DENY,
            ]
        # The operator's environment names the credential locations to hide.
        argv = autonomy.confined_argv(
            root, argv, private=private, feature=feature, env=env
        )
        env = autonomy.confined_env(env, integration)
    meta = {
        "run_id": key,
        "feature_directory": _feature_directory(root, key),
        "integration": integration,
        "command": prompt.split(maxsplit=1)[0],
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
    stderr: list[bytes] = []
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
            args=(process.stderr, sys.stderr.buffer, logs["stderr.log"], stderr),
            daemon=True,
        ),
    ]
    for thread in threads:
        thread.start()
    # An Autonomous step may only run while the run has wall time left.
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

    reason = "wall-time limit exhausted during the step" if limit_hit else None
    if exit_code not in {0, EXIT_LIMIT, EXIT_INTERRUPTED} and AUTH_FAILURES[
        integration
    ].search(b"".join(stdout + stderr)):
        reason = AUTH_REASONS[integration]
        sys.stderr.write(f"spec workflow agent wrapper: {reason}\n")
        exit_code = EXIT_AUTH
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
        # A tampering step is never retried: EXIT_TAMPERED is not checked.
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
    entry: dict = {}
    if record is not None:
        drafts = _created_drafts(root, record, log_dir.name)
        meta["drafts"] = drafts
        entry = {
            **step_record,
            "drafts": drafts,
            "exit_code": exit_code,
            "blocking_status": blocked,
            "reason": reason,
            "at": autonomy.now(),
        }
        if limit_hit:
            entry["limit"] = "wall-time"
    with meta_file:
        meta_file.write((json.dumps(meta, indent=2) + "\n").encode())
    return exit_code, entry


if __name__ == "__main__":
    sys.exit(main())
