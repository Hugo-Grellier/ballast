#!/usr/bin/env python3
"""Start or resume loreforge-feature with bounded headless agents.

    scripts/spec_workflow/run.py start -i idea="Issue #N: ..." \
        -i feature_directory=specs/N-slug [-i integration=claude|codex]
    scripts/spec_workflow/run.py resume RUN_ID [-i integration=claude|codex]

Routes Spec Kit's Claude/Codex dispatch through `bin/` (see agent.py), assigns
the run ID up front so agent logs land in `.specify/workflow-state/<run>/`, and
prints the failing contract after a stop because Spec Kit keeps shell step
output only in run state.

After every start or resume it keeps the run's history in two places, because
run state is ignored and dies with the worktree:
- `<feature>/workflow-runs/<run>.json`, committed with the feature: inputs,
  step events and gate choices. It holds no agent output or absolute paths.
- `<git common dir>/speckit-runs/<run>/`, local to the clone and shared by
  its worktrees: the full run state and agent logs.
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

from artifacts import FEATURE_PATTERN

ROOT = Path(__file__).resolve().parents[2]
BIN = ROOT / "scripts/spec_workflow/bin"
WORKFLOW = "loreforge-feature"
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


def _record(root: Path, run_id: str) -> None:
    """Commit-safe run history in the feature, full copy beside the Git dir."""
    run_dir = root / ".specify/workflows/runs" / run_id
    try:
        state = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
        inputs = json.loads((run_dir / "inputs.json").read_text(encoding="utf-8"))
        lines = (run_dir / "log.jsonl").read_text(encoding="utf-8").splitlines()
    except (OSError, ValueError):
        return
    inputs = inputs.get("inputs", {})
    feature = inputs.get("feature_directory")
    if isinstance(feature, str) and FEATURE_PATTERN.fullmatch(feature):
        gates = {
            step: (result.get("output") or {}).get("choice")
            for step, result in state.get("step_results", {}).items()
            if result.get("type") == "gate"
        }
        record = {
            "run_id": run_id,
            "workflow_id": state.get("workflow_id"),
            "status": state.get("status"),
            "current_step_id": state.get("current_step_id"),
            "created_at": state.get("created_at"),
            "updated_at": state.get("updated_at"),
            "inputs": inputs,
            "gates": gates,
            "events": [json.loads(line) for line in lines if line.strip()],
        }
        target = root / feature / "workflow-runs" / f"{run_id}.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    common = subprocess.run(
        ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],  # noqa: S607
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()
    if not common:
        return
    archive = Path(common) / "speckit-runs" / run_id
    shutil.copytree(run_dir, archive / "run", dirs_exist_ok=True)
    state_dir = root / ".specify/workflow-state" / run_id
    if state_dir.is_dir():
        shutil.copytree(state_dir, archive / "state", dirs_exist_ok=True)


def main(argv: list[str]) -> int:
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
    specify = shutil.which("specify")
    if specify is None:
        sys.stderr.write("specify CLI not found; see docs/spec-kit-workflow.md\n")
        return 2
    if argv[0] == "start":
        run_id = uuid.uuid4().hex[:8]
        command = [specify, "workflow", "run", WORKFLOW, *options]
    else:
        run_id = options[0]
        command = [specify, "workflow", "resume", *options]
    env = {
        **os.environ,
        "LOREFORGE_SPEC_WORKFLOW": "1",
        "SPECKIT_WORKFLOW_RUN_ID": run_id,
        "SPECKIT_INTEGRATION_CLAUDE_EXECUTABLE": str(BIN / "claude"),
        "SPECKIT_INTEGRATION_CODEX_EXECUTABLE": str(BIN / "codex"),
    }
    result = subprocess.run(command, cwd=ROOT, env=env, check=False)  # noqa: S603
    _summary(run_id)
    _record(ROOT, run_id)
    return result.returncode


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
