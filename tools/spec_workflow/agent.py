#!/usr/bin/env python3
"""Headless agent wrapper for the agentic-feature workflow.

Spec Kit 1.0.11 runs `claude -p ...` or `codex exec ...` for command steps and
only records the exit code. The launcher points SPECKIT_INTEGRATION_<KEY>_
EXECUTABLE at `bin/claude` / `bin/codex` (symlinks to this file), which:

- add the bounded permission model (never a permission or sandbox bypass);
- tee stdout/stderr to the terminal and to ignored run state;
- fail the step when the agent reports `RECONCILE_STATUS: BLOCKED_*`;
- fail the step when the agent changed run state or workflow machinery.

Artifact validation steps remain the primary postcondition; this wrapper only
adds evidence and an early stop.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import BinaryIO

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
EXIT_USAGE = 2
EXIT_INTERRUPTED = 130


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


def _tee(source: BinaryIO, sink: BinaryIO, log: Path, captured: list[bytes]) -> None:
    with log.open("wb") as handle:
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


def _protected_state(root: Path, key: str, own_log: Path) -> dict[str, str]:
    """Hash workflow machinery and run state that no agent may change.

    Codex's workspace-write sandbox cannot deny paths, and run state is
    gitignored, so edits here would be invisible in the diff yet could skip
    gates on resume or neuter the validators. Spec Kit writes none of these
    while a command step runs.
    """
    bases = [
        root / ".agentic/spec_workflow",
        root / ".specify/workflows/agentic-feature",
    ]
    if key != "no-run":
        bases += [
            root / ".specify/workflows/runs" / key,
            root / ".specify/workflow-state" / key,
        ]
    digests: dict[str, str] = {}
    for base in bases:
        for path in sorted(base.rglob("*")) if base.is_dir() else []:
            if "__pycache__" in path.parts or path.is_relative_to(own_log):
                continue
            name = str(path.relative_to(root))
            if path.is_symlink():
                digests[name] = "link:" + str(path.readlink())
            elif path.is_file():
                digests[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return digests


def main() -> int:
    """Run the real agent CLI with bounded permissions and persistent logs."""
    integration = Path(sys.argv[0]).name
    if integration not in {"claude", "codex"}:
        sys.stderr.write("invoke through .agentic/spec_workflow/bin/{claude,codex}\n")
        return EXIT_USAGE
    try:
        argv = [
            _real_executable(integration),
            *permission_args(integration, sys.argv[1:]),
        ]
    except (ValueError, FileNotFoundError) as error:
        sys.stderr.write(f"spec workflow agent wrapper: {error}\n")
        return EXIT_USAGE

    root = Path.cwd()
    log_dir, key = _log_dir(root, integration, sys.argv[2])
    meta = {
        "run_id": key,
        "feature_directory": _feature_directory(root, key),
        "integration": integration,
        "command": sys.argv[2].split(maxsplit=1)[0],
        "argv": [Path(argv[0]).name, *argv[1:]],
        "started_at": datetime.now(UTC).isoformat(),
    }
    protected = _protected_state(root, key, log_dir)
    stdout: list[bytes] = []
    process = subprocess.Popen(  # noqa: S603 - resolved CLI, argument list
        argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    assert process.stdout is not None  # noqa: S101 - set by PIPE above
    assert process.stderr is not None  # noqa: S101 - set by PIPE above
    threads = [
        threading.Thread(
            target=_tee,
            args=(process.stdout, sys.stdout.buffer, log_dir / "stdout.log", stdout),
        ),
        threading.Thread(
            target=_tee,
            args=(process.stderr, sys.stderr.buffer, log_dir / "stderr.log", []),
        ),
    ]
    for thread in threads:
        thread.start()
    try:
        exit_code = process.wait()
    except KeyboardInterrupt:
        exit_code = process.wait()
        exit_code = exit_code or EXIT_INTERRUPTED
    for thread in threads:
        thread.join()

    blocked = BLOCKING.findall(b"".join(stdout).decode("utf-8", "replace"))
    if exit_code == 0 and blocked:
        sys.stderr.write(
            f"spec workflow agent wrapper: agent reported {blocked[0]}; "
            "failing this step\n"
        )
        exit_code = EXIT_BLOCKED
    after = _protected_state(root, key, log_dir)
    tampered = sorted(
        name
        for name in protected.keys() | after.keys()
        if protected.get(name) != after.get(name)
    )
    if tampered:
        sys.stderr.write(
            "spec workflow agent wrapper: agent changed protected workflow files; "
            f"failing this step: {', '.join(tampered)}\n"
        )
        exit_code = EXIT_TAMPERED
    meta |= {
        "finished_at": datetime.now(UTC).isoformat(),
        "exit_code": exit_code,
        "blocking_status": blocked,
        "protected_changes": tampered,
    }
    (log_dir / "meta.json").write_text(
        json.dumps(meta, indent=2) + "\n", encoding="utf-8"
    )
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
