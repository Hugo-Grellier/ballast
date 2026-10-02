#!/usr/bin/env python3
"""Deterministic postconditions for the agentic-feature Spec Kit workflow.

An agent exiting 0 does not prove it produced anything. Each check below
verifies an observable artifact contract and exits non-zero with a diagnostic
when the contract is not met. Checks are cumulative: a later check re-verifies
the artifacts it depends on, so a resumed run cannot trust stale step state.

Run from the repository root:

    artifacts.py <check> (--run RUN_ID | --feature specs/<number>-<slug>)
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
import tempfile
from datetime import UTC, datetime
from pathlib import Path

FEATURE_PATTERN = re.compile(r"specs/[1-9][0-9]*-[a-z0-9]+(?:-[a-z0-9]+)*")
RUN_ID_PATTERN = re.compile(r"[A-Za-z0-9_-]{1,64}")
TREE_ID = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")
STATE_DIR = Path(".specify/workflow-state")
NO_CODE_CHANGE = "<!-- workflow: no-code-change -->"
APPROVAL_START = "<!-- workflow-approval: begin -->"
APPROVAL_END = "<!-- workflow-approval: end -->"
INTENT_SECTIONS = (
    "## Outcome",
    "## Constraints",
    "## Non-goals",
    "## Success evidence",
    "## Authority",
)

# Exact text from the committed templates; ordinary bracketed prose is allowed.
SPEC_SENTINELS = (
    "# Feature Specification: [FEATURE NAME]",
    "[###-feature-name]",
    "**Created**: [DATE]",
    "[Brief Title]",
    "[Describe this user journey in plain language]",
    "[Explain the value and why it has this priority level]",
    "**Given** [initial state]",
    "[Entity 1]",
    "[Add more user stories as needed",
)
PLAN_SENTINELS = (
    "# Implementation Plan: [FEATURE]",
    "[###-feature-name]",
    "**Date**: [DATE]",
    "**Spec**: [link]",
    "[Extract from feature spec",
    "[Gates determined based on constitution file]",
    "[Select only areas this feature touches",
    "[e.g., ",
)
TASKS_SENTINELS = (
    "# Tasks: [FEATURE NAME]",
    "[###-feature-name]",
    "SAMPLE TASKS for illustration",
)
UNRESOLVED_CLARIFICATION = re.compile(
    r"\[NEEDS CLARIFICATION|^\*\*[^*\n]+\*\*:\s*NEEDS CLARIFICATION", re.MULTILINE
)
TASK_LINE = re.compile(r"^\s*[-*] \[( |x|X)\] (T\d{3,})\b(.*)$", re.MULTILINE)
DEPENDS_ON = re.compile(r"\(depends on ([^)]*)\)")
TASK_ID = re.compile(r"T\d{3,}")
DECISION_HEADING = re.compile(r"^##\s+DEC-", re.MULTILINE)
DECISION_RECORD = re.compile(
    # Em dash per the intent extension; en dash and hyphen are tolerated.
    "^##\\s+(DEC-\\d+)\\s+[\u2014\u2013-]+\\s+(Proposal|Resolution)\\s*$",
    re.MULTILINE | re.IGNORECASE,
)
VERDICT_LINE = re.compile(
    r"^\s*(?:[-*]\s+)?(?:\*\*)?Verdict(?:\*\*)?\s*:\s*(?:\*\*)?([A-Za-z_]+)",
    re.MULTILINE,
)
DIGEST_LINE = re.compile(
    r"^- \*\*Approved spec digest\*\*: (sha256:[0-9a-f]{64})$", re.MULTILINE
)
SPEC_LINE = re.compile(r"^- \*\*Spec\*\*: (\S+)$", re.MULTILINE)


class ContractError(Exception):
    """An artifact does not satisfy its workflow postcondition."""


class Feature:
    """A validated feature directory inside the repository."""

    def __init__(self, root: Path, relative: str, key: str) -> None:
        """Validate *relative* as specs/<number>-<slug> without escaping *root*."""
        if not FEATURE_PATTERN.fullmatch(relative):
            message = (
                f"feature directory {relative!r} must match "
                "specs/<issue-number>-<slug> (lowercase slug, no absolute or parent "
                "paths)"
            )
            raise ContractError(message)
        self.root = root
        self.relative = relative
        self.key = key
        self.path = root / relative
        specs = (root / "specs").resolve()
        if (
            not specs.is_relative_to(root.resolve())
            or self.path.is_symlink()
            or (self.path.exists() and self.path.resolve().parent != specs)
        ):
            message = f"{relative} must be a real directory directly under specs/"
            raise ContractError(message)

    def file(self, name: str) -> Path:
        """Return a regular, non-symlink artifact path inside the feature."""
        path = self.path / name
        if path.is_symlink() or not path.resolve().is_relative_to(self.path.resolve()):
            message = (
                f"{self.relative}/{name} must not be a symlink or escape the feature"
            )
            raise ContractError(message)
        if path.exists() and not path.is_file():
            message = f"{self.relative}/{name} must be a regular file"
            raise ContractError(message)
        return path

    def read(self, name: str) -> str:
        """Read a required, non-empty artifact."""
        path = self.file(name)
        if not path.exists():
            message = f"{self.relative}/{name} is missing"
            raise ContractError(message)
        text = path.read_text(encoding="utf-8")
        if not text.strip():
            message = f"{self.relative}/{name} is empty"
            raise ContractError(message)
        return text


def _reject_sentinels(name: str, text: str, sentinels: tuple[str, ...]) -> None:
    found = [sentinel for sentinel in sentinels if sentinel in text]
    if found:
        listed = ", ".join(repr(sentinel) for sentinel in found)
        message = f"{name} still contains template placeholders: {listed}"
        raise ContractError(message)


def spec_digest(text: str) -> str:
    """Hash spec content, ignoring line-ending and trailing-space noise."""
    lines = [line.rstrip() for line in text.replace("\r\n", "\n").split("\n")]
    normalized = "\n".join(lines).strip("\n") + "\n"
    return "sha256:" + hashlib.sha256(normalized.encode()).hexdigest()


def check_spec(feature: Feature) -> str:
    """spec.md exists in the requested feature and is not the template."""
    text = feature.read("spec.md")
    _reject_sentinels(f"{feature.relative}/spec.md", text, SPEC_SENTINELS)
    return text


def check_clarified_spec(feature: Feature) -> str:
    """Require a spec with no unresolved clarification markers."""
    text = check_spec(feature)
    if UNRESOLVED_CLARIFICATION.search(text):
        message = (
            f"{feature.relative}/spec.md still has NEEDS CLARIFICATION markers; "
            "resolve them interactively (speckit-clarify) before intent approval"
        )
        raise ContractError(message)
    return text


def check_intent(feature: Feature) -> None:
    """intent.md records approval of the current spec.md version."""
    spec = check_clarified_spec(feature)
    intent = feature.read("intent.md")
    missing = [section for section in INTENT_SECTIONS if section not in intent]
    if missing:
        message = f"{feature.relative}/intent.md lacks sections: {', '.join(missing)}"
        raise ContractError(message)
    digests = DIGEST_LINE.findall(intent)
    specs = SPEC_LINE.findall(intent)
    if len(digests) != 1 or specs != [f"{feature.relative}/spec.md"]:
        message = (
            f"{feature.relative}/intent.md has no single workflow approval record for "
            f"{feature.relative}/spec.md; approve intent at the workflow gate"
        )
        raise ContractError(message)
    if digests[0] != spec_digest(spec):
        message = (
            f"{feature.relative}/spec.md changed after intent approval; the approval "
            "is stale. Review the spec and re-approve (record-intent)"
        )
        raise ContractError(message)


def record_intent(feature: Feature) -> None:
    """Record human intent approval bound to the current spec digest.

    Run only after the approve-intent gate. Human-written intent sections are
    preserved; only the machine-managed approval block is replaced.
    """
    spec = check_clarified_spec(feature)
    path = feature.file("intent.md")
    block = "\n".join(
        (
            APPROVAL_START,
            "- **Approved by**: human user",
            f"- **Approved**: {datetime.now(UTC).replace(microsecond=0).isoformat()}",
            f"- **Source**: agentic-feature approve-intent gate ({feature.key})",
            f"- **Spec**: {feature.relative}/spec.md",
            f"- **Approved spec digest**: {spec_digest(spec)}",
            APPROVAL_END,
        )
    )
    if path.exists():
        text = path.read_text(encoding="utf-8")
        pattern = re.compile(
            re.escape(APPROVAL_START) + r".*?" + re.escape(APPROVAL_END), re.DOTALL
        )
        if pattern.search(text):
            text = pattern.sub(lambda _: block, text, count=1)
        else:
            text = text.rstrip("\n") + "\n\n" + block + "\n"
    else:
        title = re.search(r"^# Feature Specification:\s*(.+)$", spec, re.MULTILINE)
        name = title.group(1).strip() if title else feature.relative
        pointer = (
            "As approved in [`spec.md`](spec.md) at the digest recorded under "
            "Authority. The spec is the source of this feature's"
        )
        text = "\n".join(
            (
                f"# Feature Intent: {name}",
                "",
                "## Outcome",
                "",
                f"{pointer} outcome.",
                "",
                "## Constraints",
                "",
                f"- {pointer} constraints and requirements.",
                "",
                "## Non-goals",
                "",
                f"- {pointer} out-of-scope boundary.",
                "",
                "## Success evidence",
                "",
                f"- {pointer} acceptance criteria and success criteria.",
                "",
                "## Authority",
                "",
                block,
                "",
            )
        )
    path.write_text(text, encoding="utf-8")
    check_intent(feature)


def check_plan(feature: Feature) -> None:
    """plan.md is filled in, on top of a still-valid intent approval."""
    check_intent(feature)
    text = feature.read("plan.md")
    _reject_sentinels(f"{feature.relative}/plan.md", text, PLAN_SENTINELS)
    if UNRESOLVED_CLARIFICATION.search(text):
        message = f"{feature.relative}/plan.md has unresolved NEEDS CLARIFICATION"
        raise ContractError(message)


def parse_tasks(feature: Feature) -> tuple[str, dict[str, bool]]:
    """Return tasks.md text and {task_id: done}, validating structure."""
    text = feature.read("tasks.md")
    name = f"{feature.relative}/tasks.md"
    _reject_sentinels(name, text, TASKS_SENTINELS)
    tasks: dict[str, bool] = {}
    dependencies: dict[str, list[str]] = {}
    for mark, task_id, rest in TASK_LINE.findall(text):
        if task_id in tasks:
            message = f"{name} defines {task_id} more than once"
            raise ContractError(message)
        tasks[task_id] = mark != " "
        dependencies[task_id] = [
            dep for group in DEPENDS_ON.findall(rest) for dep in TASK_ID.findall(group)
        ]
    if not tasks:
        message = f"{name} has no task lines like '- [ ] T001 ...'"
        raise ContractError(message)
    for task_id, deps in dependencies.items():
        unknown = sorted({dep for dep in deps if dep not in tasks or dep == task_id})
        if unknown:
            message = (
                f"{name}: {task_id} depends on unknown task(s) {', '.join(unknown)}"
            )
            raise ContractError(message)
    return text, tasks


def check_tasks(feature: Feature) -> None:
    """tasks.md has real, well-formed tasks on top of a valid plan."""
    check_plan(feature)
    parse_tasks(feature)


def _require_tasks_done(feature: Feature) -> str:
    text, tasks = parse_tasks(feature)
    pending = [task_id for task_id, done in tasks.items() if not done]
    if pending:
        message = f"{feature.relative}/tasks.md has pending tasks: {', '.join(pending)}"
        raise ContractError(message)
    return text


def _git(root: Path, *args: str, env: dict[str, str] | None = None) -> str:
    git = shutil.which("git")
    if git is None:
        message = "git is required"
        raise ContractError(message)
    result = subprocess.run(  # noqa: S603 - fixed executable, argument list
        [git, *args], cwd=root, env=env, capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        message = f"git {args[0]} failed: {result.stderr.strip()}"
        raise ContractError(message)
    return result.stdout.strip()


def worktree_tree(root: Path) -> str:
    """Hash the whole working tree (tracked + untracked, minus ignored files).

    Uses a throwaway index so the user's staging area is untouched.
    """
    index = Path(
        _git(root, "rev-parse", "--path-format=absolute", "--git-path", "index")
    )
    with tempfile.TemporaryDirectory(prefix="agentic-tree-") as directory:
        temporary = Path(directory) / "index"
        if index.exists():
            shutil.copyfile(index, temporary)
        env = {**os.environ, "GIT_INDEX_FILE": str(temporary)}
        _git(root, "add", "--all", "--", ".", env=env)
        return _git(root, "write-tree", env=env)


def _state_file(feature: Feature, name: str) -> Path:
    directory = feature.root / STATE_DIR / feature.key
    directory.mkdir(parents=True, exist_ok=True)
    return directory / name


def record_baseline(feature: Feature) -> None:
    """Snapshot the working tree immediately before implementation."""
    check_tasks(feature)
    path = _state_file(feature, "implementation-baseline.json")
    payload = {"feature": feature.relative, "tree": worktree_tree(feature.root)}
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def check_implementation(feature: Feature) -> None:
    """Require every task done and a repository change since the baseline."""
    check_plan(feature)
    tasks_text = _require_tasks_done(feature)
    path = _state_file(feature, "implementation-baseline.json")
    if not path.exists():
        message = "no implementation baseline recorded before implementation"
        raise ContractError(message)
    # The baseline lives in the agent's writable workspace: never trust it as argv.
    try:
        baseline = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as error:
        message = f"implementation baseline is not valid JSON: {error}"
        raise ContractError(message) from error
    tree = baseline.get("tree") if isinstance(baseline, dict) else None
    if not isinstance(tree, str) or not TREE_ID.fullmatch(tree):
        message = "implementation baseline has no valid tree id"
        raise ContractError(message)
    if baseline.get("feature") != feature.relative:
        message = "implementation baseline belongs to another feature"
        raise ContractError(message)
    changed = _git(
        feature.root,
        "diff-tree",
        "-r",
        "--name-only",
        "--end-of-options",
        tree,
        worktree_tree(feature.root),
    ).splitlines()
    outside = [name for name in changed if not name.startswith(feature.relative + "/")]
    if not outside and NO_CODE_CHANGE not in tasks_text:
        message = (
            "implementation changed nothing outside the feature directory; if the "
            f"feature needs no code change, add {NO_CODE_CHANGE} to tasks.md"
        )
        raise ContractError(message)


def check_decisions(feature: Feature) -> None:
    """Every decision proposal has a human resolution."""
    check_intent(feature)
    path = feature.file("decisions.md")
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    records = DECISION_RECORD.findall(text)
    if len(records) != len(DECISION_HEADING.findall(text)):
        message = f"{feature.relative}/decisions.md has malformed DEC headings"
        raise ContractError(message)
    proposals = {dec for dec, kind in records if kind.lower() == "proposal"}
    resolved = {dec for dec, kind in records if kind.lower() == "resolution"}
    pending = sorted(proposals - resolved)
    if pending:
        message = (
            f"unresolved decisions: {', '.join(pending)}; resolve them interactively "
            "with speckit-intent-decisions"
        )
        raise ContractError(message)


def check_convergence(feature: Feature) -> None:
    """Converged: tasks done, decisions resolved, CONVERGED verdict recorded."""
    check_plan(feature)
    _require_tasks_done(feature)
    check_decisions(feature)
    verdicts = VERDICT_LINE.findall(feature.read("reviews/convergence.md"))
    if not verdicts or verdicts[-1] != "CONVERGED":
        latest = verdicts[-1] if verdicts else "none"
        message = (
            f"{feature.relative}/reviews/convergence.md latest verdict is {latest}; "
            "expected '- Verdict: CONVERGED'"
        )
        raise ContractError(message)


def check_preflight(feature: Feature) -> None:
    """Require a run started through .agentic/spec_workflow/run.py."""
    if os.environ.get("AGENTIC_SPEC_WORKFLOW") != "1":
        message = (
            "start agentic-feature with .agentic/spec_workflow/run so headless "
            "agents get the bounded permission model and run logs"
        )
        raise ContractError(message)
    del feature


CHECKS = {
    "preflight": check_preflight,
    "spec": check_spec,
    "clarified-spec": check_clarified_spec,
    "record-intent": record_intent,
    "intent": check_intent,
    "plan": check_plan,
    "tasks": check_tasks,
    "implementation-baseline": record_baseline,
    "implementation": check_implementation,
    "decisions": check_decisions,
    "convergence": check_convergence,
}


def resolve_feature(root: Path, run_id: str | None, relative: str | None) -> Feature:
    """Resolve the feature from explicit input or a run's persisted inputs."""
    if not (root / ".specify").is_dir():
        message = "run from the repository root"
        raise ContractError(message)
    if run_id is None:
        return Feature(
            root, relative or "", "feature-" + (relative or "").rpartition("/")[2]
        )
    if not RUN_ID_PATTERN.fullmatch(run_id):
        message = f"invalid run id {run_id!r}"
        raise ContractError(message)
    inputs = root / ".specify/workflows/runs" / run_id / "inputs.json"
    try:
        data = json.loads(inputs.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        message = f"cannot read inputs for run {run_id}: {error}"
        raise ContractError(message) from error
    value = data.get("inputs", {}).get("feature_directory")
    if not isinstance(value, str):
        message = f"run {run_id} has no feature_directory input"
        raise ContractError(message)
    return Feature(root, value, run_id)


def main(argv: list[str] | None = None) -> int:
    """Run one check and report the result."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("check", choices=sorted(CHECKS))
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--run", help="workflow run id; reads its feature_directory")
    target.add_argument("--feature", help="specs/<issue-number>-<slug>")
    arguments = parser.parse_args(argv)
    try:
        feature = resolve_feature(Path.cwd(), arguments.run, arguments.feature)
        CHECKS[arguments.check](feature)
    except ContractError as error:
        sys.stderr.write(f"workflow contract failed [{arguments.check}]: {error}\n")
        return 1
    sys.stdout.write(f"workflow contract ok [{arguments.check}]: {feature.relative}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
