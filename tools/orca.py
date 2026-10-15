"""Inspect optional Orca execution support without launching or dispatching work.

Strict dispatch is blocked until a native pre-task session verification contract
is integrated and demonstrated. A requested/effective launch preference receipt
alone does not establish that contract.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools import codex

MAX_OUTPUT = 1024 * 1024
CAPABILITIES = frozenset(
    {
        "orchestration.contract.v1",
        "orchestration.worker-launch-preferences.v1",
        "orchestration.worker-stop-verdict.v1",
        "orchestration.federation-fleet-snapshot.v1",
        "terminal.prompt-delivery.v1",
        "worktree.create-idempotency.v1",
        "terminal.create-idempotency.v2",
        "agent-session.structured.hold.v1",
    }
)
READS = frozenset(
    {
        ("skills", "get", "orca-cli"),
        ("skills", "get", "orchestration"),
        ("status", "--json"),
        ("agent-context", "--json"),
    }
)
BLOCKER = (
    "Native same-session model/effort verification before task delivery "
    "is not integrated"
)


def read(executable: str, cwd: Path, args: tuple[str, ...]) -> str:
    """Call only fixed discovery operations; never expose raw backend output."""
    if args not in READS:
        codex.fail("Orca operation is outside the read-only qualification allowlist")
    result = subprocess.run(  # noqa: S603 -- resolved explicit executable, fixed argv, no shell
        [executable, *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if (
        result.returncode
        or not result.stdout.strip()
        or len(result.stdout) > MAX_OUTPUT
    ):
        codex.fail(
            "Selected Orca discovery command failed; no alternate executable tried"
        )
    return result.stdout


def inspect(executable: str, cwd: Path, model: str, effort: str) -> dict:
    """Project safe capability facts; never infer routing from advertised flags."""
    codex.check_environment(os.environ)
    if os.environ.get("ORCA_ENVIRONMENT") or os.environ.get("ORCA_PAIRING_CODE"):
        codex.fail("This Orca qualification supports only an explicit local target")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", model) or effort not in {
        "none",
        "minimal",
        "low",
        "medium",
        "high",
        "xhigh",
    }:
        codex.fail("Model and effort must be explicit concrete settings")
    selected = shutil.which(executable)
    if selected is None:
        codex.fail("Selected Orca executable is unavailable; no alternate tried")
    guides = {
        name: hashlib.sha256(
            read(selected, cwd, ("skills", "get", name)).encode()
        ).hexdigest()
        for name in ("orca-cli", "orchestration")
    }
    status = json.loads(read(selected, cwd, ("status", "--json")))
    if not isinstance(status, dict) or status.get("ok") is not True:
        codex.fail("Orca status is unavailable")
    result = status.get("result")
    if not isinstance(result, dict) or result.get("target") != {"kind": "local"}:
        codex.fail("Orca execution host is not proven local")
    runtime = result.get("runtime")
    if (
        not isinstance(runtime, dict)
        or runtime.get("state") != "ready"
        or runtime.get("reachable") is not True
        or not isinstance(runtime.get("capabilities"), list)
        or not all(isinstance(value, str) for value in runtime["capabilities"])
        or not isinstance(runtime.get("appVersion"), str)
        or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", runtime["appVersion"])
    ):
        codex.fail("Orca runtime readiness or capability response is malformed")
    schema = json.loads(read(selected, cwd, ("agent-context", "--json")))
    if (
        not isinstance(schema, dict)
        or schema.get("schemaVersion") != 1
        or not isinstance(schema.get("commands"), list)
        or not all(isinstance(command, dict) for command in schema["commands"])
    ):
        codex.fail("Orca public command schema is unsupported")
    starts = [
        c
        for c in schema["commands"]
        if c.get("command") == "orchestration worker-start"
    ]
    flags = starts[0].get("flags", []) if len(starts) == 1 else []
    if not isinstance(flags, list) or not all(isinstance(flag, str) for flag in flags):
        codex.fail("Orca launch command schema is malformed")
    return {
        "backend": "orca",
        "client_version": runtime["appVersion"],
        "guide_sha256": guides,
        "capabilities": sorted(CAPABILITIES.intersection(runtime["capabilities"])),
        "launch_options": {
            name: name in flags for name in ("agent", "model", "effort", "terminal")
        },
        "requested": {"provider": "openai", "model": model, "effort": effort},
        "observed": None,
        "verification": "unverified",
        "dispatch": "blocked",
        "reason": BLOCKER,
        "task_started": False,
        "resources_created": False,
    }


def main() -> int:
    """Emit a sanitized block, including on an otherwise capable future version."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--executable", required=True, help="Resolve using the installed Orca skill"
    )
    parser.add_argument("--cwd", type=Path, default=Path.cwd())
    parser.add_argument("--model", required=True)
    parser.add_argument("--effort", required=True)
    args = parser.parse_args()
    try:
        report = inspect(
            args.executable, args.cwd.resolve(strict=True), args.model, args.effort
        )
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError):
        # CLI diagnostics can contain paths, account identifiers or private text.
        report = {
            "backend": "orca",
            "dispatch": "blocked",
            "reason": "Orca qualification failed; inspect local installation",
            "task_started": False,
            "resources_created": False,
        }
    sys.stdout.write(json.dumps(report, indent=2) + "\n")
    return 1


if __name__ == "__main__":
    sys.exit(main())
