#!/usr/bin/env python3
"""Start or resume ballast-feature with bounded headless agents.

    ballast run start -i idea="Issue #N: ..." \
        -i feature_directory=specs/N-slug [-i integration=claude|codex]
    ballast run resume RUN_ID [-i integration=claude|codex]

`ballast` is the installed copy of launcher.py, which verifies the
checkout before executing this file; see docs/policies/spec-kit-workflow.md.

Routes Spec Kit's Claude/Codex dispatch through `bin/` (see agent.py), assigns
the run ID up front so agent logs land in `.specify/workflow-state/<run>/`, and
prints the failing contract after a stop because Spec Kit keeps shell step
output only in run state.

After every start or resume it archives the run under
`<git common dir>/speckit-runs/<run>/`, local to the clone and shared by its
worktrees. The full run state and agent logs stay outside Git tracking.

Then it runs the Draft PR checkpoint (draft_pr.py, imported here before any
agent step) and prints its one-line outcome; nothing the checkpoint does
changes the exit status. The workflow engine, and so every agent step, never
receives the GitHub token variables in draft_pr.TOKEN_VARIABLES.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
# Same name as agent.TAMPER_MARKER. Checked before importing any other checkout
# module, which a failed protected check means an agent may have rewritten.
TAMPER_MARKER = "BALLAST_TAMPERED"
TAMPER_MESSAGE = (
    f"{TAMPER_MARKER} exists: an agent changed protected workflow files. "
    "Restore them and recreate .venv, then delete the marker.\n"
)
if __name__ == "__main__" and os.path.lexists(ROOT / TAMPER_MARKER):
    sys.stderr.write(TAMPER_MESSAGE)
    sys.exit(2)
# Never read checkout bytecode: a headless agent may have planted it. The
# trusted launcher starts this file under `-I -S`, which leaves this directory
# off sys.path and runs no site-packages startup code.
sys.pycache_prefix = os.devnull
sys.path.insert(0, str(Path(__file__).resolve().parent))

import draft_pr  # noqa: E402
from ledger import archive_dir, archive_lock, archive_policy, import_run  # noqa: E402

BIN = ROOT / ".ballast/spec_workflow/bin"
EXIT_INTERRUPTED = 130
WORKFLOW = "ballast-feature"
RESUMABLE_INPUTS = {"integration"}
RUN_ID = re.compile(r"[A-Za-z0-9_-]{1,64}")


def _summary(run_id: str) -> None:
    state_path = ROOT / ".specify/workflows/runs" / run_id / "state.json"
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    step = state.get("current_step_id")
    sys.stdout.write(f"\nRun {run_id}: {state.get('status')} at step {step}\n")
    result = state.get("step_results", {}).get(step) or {}
    if result.get("status") == "failed":
        output = result.get("output") or {}
        for stream in ("stdout", "stderr"):
            text = (output.get(stream) or "").strip()
            if text:
                sys.stdout.write(f"{stream}: {text}\n")
        sys.stdout.write(f"error: {result.get('error')}\n")
    sys.stdout.write(f"Agent logs: .specify/workflow-state/{run_id}/agents/\n")


def _record(root: Path, run_id: str, exit_status: int | None = None) -> None:
    """Keep the full run state outside worktrees in the Git common directory."""
    run_dir = root / ".specify/workflows/runs" / run_id
    if run_dir.is_symlink() or run_dir.parent.is_symlink():
        message = "symlinked run state is unavailable for archive"
        raise RuntimeError(message)
    try:
        lines = (run_dir / "log.jsonl").read_text(encoding="utf-8").splitlines()
    except OSError as error:
        message = "run state is unavailable for archive"
        raise RuntimeError(message) from error
    archive = archive_dir(root, run_id)
    state_dir = root / ".specify/workflow-state" / run_id
    if state_dir.is_symlink() or state_dir.parent.is_symlink():
        message = "symlinked agent state is unavailable for archive"
        raise RuntimeError(message)
    with archive_lock(root, run_id, exclusive=True):
        shutil.copytree(run_dir, archive / "run", dirs_exist_ok=True)
        if state_dir.is_dir():
            shutil.copytree(state_dir, archive / "state", dirs_exist_ok=True)
        if exit_status is not None:
            pending = archive / "invocation.json.tmp"
            pending.write_text(
                json.dumps({"log_lines": len(lines), "exit_status": exit_status})
                + "\n",
                encoding="utf-8",
            )
            pending.replace(archive / "invocation.json")


def main(argv: list[str]) -> int:  # noqa: C901, PLR0912, PLR0915 - Preserve runner exit.
    """Launch Spec Kit with the wrapper environment."""
    if len(argv) < 1 or argv[0] not in {"start", "resume"}:
        sys.stderr.write(__doc__ or "")
        return 2
    options = argv[1:]
    if argv[0] == "resume":
        rest = options[1:]
        if not options or not RUN_ID.fullmatch(options[0]):
            sys.stderr.write("resume needs a valid RUN_ID\n")
            return 2
        # Only the integration may change; the feature directory is fixed.
        if len(rest) % 2 or any(
            flag not in {"-i", "--input"}
            or value.partition("=")[0] not in RESUMABLE_INPUTS
            for flag, value in zip(rest[::2], rest[1::2], strict=True)
        ):
            sys.stderr.write("resume accepts only: -i integration=claude|codex|auto\n")
            return 2
    if os.path.lexists(ROOT / TAMPER_MARKER):
        sys.stderr.write(TAMPER_MESSAGE)
        return 2
    specify = shutil.which("specify")
    if specify is None:
        sys.stderr.write(
            "specify CLI not found; see docs/policies/spec-kit-workflow.md\n"
        )
        return 2
    if argv[0] == "start":
        run_id = uuid.uuid4().hex[:8]
        command = [specify, "workflow", "run", WORKFLOW, *options]
    else:
        run_id = options[0]
        command = [specify, "workflow", "resume", *options]
    env = {
        **{
            key: value
            for key, value in os.environ.items()
            if key not in draft_pr.TOKEN_VARIABLES
        },
        "BALLAST_SPEC_WORKFLOW": "1",
        "SPECKIT_WORKFLOW_RUN_ID": run_id,
        "SPECKIT_INTEGRATION_CLAUDE_EXECUTABLE": str(BIN / "claude"),
        "SPECKIT_INTEGRATION_CODEX_EXECUTABLE": str(BIN / "codex"),
    }
    if argv[0] == "start":
        archive_policy(ROOT, run_id)
    status = EXIT_INTERRUPTED
    try:
        result = subprocess.run(command, cwd=ROOT, env=env, check=False)  # noqa: S603
        status = result.returncode
    except KeyboardInterrupt:
        status = EXIT_INTERRUPTED
    finally:
        try:
            _summary(run_id)
        except (
            OSError,
            ValueError,
            RuntimeError,
            KeyError,
            TypeError,
            AttributeError,
        ) as error:
            sys.stderr.write(f"workflow summary failed: {error}\n")
            if status == 0:
                status = 1
        try:
            _record(ROOT, run_id, status)
        except (
            OSError,
            ValueError,
            RuntimeError,
            KeyError,
            TypeError,
            AttributeError,
        ) as error:
            sys.stderr.write(f"workflow archive failed: {error}\n")
            if status == 0:
                status = 1
        try:
            import_run(ROOT, run_id)
        except (
            OSError,
            ValueError,
            RuntimeError,
            KeyError,
            TypeError,
            AttributeError,
        ) as error:
            sys.stderr.write(f"workflow ledger import failed: {error}\n")
            if status == 0:
                status = 1
        # Never assigns status: a PR failure must not change the run's result.
        try:
            line = draft_pr.format_line(draft_pr.checkpoint(ROOT, run_id))
        except (Exception, KeyboardInterrupt) as error:  # noqa: BLE001
            line = (
                f"Draft PR: failed-retryable (internal-error) ({type(error).__name__})"
            )
        sys.stdout.write(line + "\n")
    return status


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
