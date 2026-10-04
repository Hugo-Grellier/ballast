#!/usr/bin/env python3
"""Deterministic postconditions for the ballast-feature Spec Kit workflow.

An agent exiting 0 does not prove it produced anything. Each check below
verifies an observable artifact contract and exits non-zero with a diagnostic
when the contract is not met. Checks are cumulative: a later check re-verifies
the artifacts it depends on, so a resumed run cannot trust stale step state.

Run from the repository root:

    artifacts.py <check> (--run RUN_ID | --feature specs/<number>-<slug>)
        [--point POINT] [--renew]

In an Autonomous run (operator run record with workflow ballast-autonomous),
every check first requires the run to be active and the committed
`autonomous/record.md` to equal its rendering from the operator logs. The
`record-*` checks validate agent drafts and append provisional decisions;
`check_intent` and `check_decisions` accept only agent-provisional records
there, and never count them as human approval in a human-gated run.
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
import time
from datetime import UTC, datetime
from pathlib import Path

# Never read or write checkout bytecode, including for the imports below. The
# trusted launcher runs this file under `-I`, which leaves its directory off
# sys.path.
sys.pycache_prefix = os.devnull
sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    import autonomy
    from launcher import digests, input_bases
except ImportError:  # pragma: no cover - only the ledger's isolated copy
    # ledger.py imports this file for its patterns alone. Every check that
    # names a workflow run fails closed below without the Autonomous module.
    autonomy = None

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
        # Set by load_run for a workflow run: the operator run record of an
        # Autonomous run, or of a human-gated continuation.
        self.run_id: str | None = None
        self.run: dict | None = None
        self.continued: dict | None = None
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
    if feature.run is not None:
        check_provisional_intent(feature)
        return
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
    block = "\n".join(
        (
            APPROVAL_START,
            "- **Approved by**: human user",
            f"- **Approved**: {datetime.now(UTC).replace(microsecond=0).isoformat()}",
            f"- **Source**: ballast-feature approve-intent gate ({feature.key})",
            f"- **Spec**: {feature.relative}/spec.md",
            f"- **Approved spec digest**: {spec_digest(spec)}",
            APPROVAL_END,
        )
    )
    if feature.continued is not None:
        # A human-gated continuation of an Autonomous run: this approval
        # supersedes the agent-provisional intent, which stays in the operator
        # log and autonomous/record.md.
        path = feature.file("intent.md")
        if path.exists():
            text = path.read_text(encoding="utf-8")
            path.write_text(PROVISIONAL_BLOCK.sub("", text), encoding="utf-8")
    _write_intent_block(feature, spec, block, APPROVAL_START, APPROVAL_END)
    check_intent(feature)


def _write_intent_block(
    feature: Feature, spec: str, block: str, start: str, end: str
) -> None:
    """Replace one machine-managed block in intent.md, keeping human sections."""
    path = feature.file("intent.md")
    if path.exists():
        text = path.read_text(encoding="utf-8")
        pattern = re.compile(re.escape(start) + r".*?" + re.escape(end), re.DOTALL)
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
    with tempfile.TemporaryDirectory(prefix="ballast-tree-") as directory:
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
    if feature.run is not None:
        resolved = _provisional_resolutions(feature, text)
    else:
        # An agent-provisional resolution is never a human resolution.
        resolved = {
            dec
            for dec, kind, body in decision_sections(text)
            if kind.lower() == "resolution" and "agent-provisional" not in body
        }
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
    """Require a run started through .ballast/spec_workflow/run.py."""
    if os.environ.get("BALLAST_SPEC_WORKFLOW") != "1":
        message = (
            "start ballast-feature with .ballast/spec_workflow/run so headless "
            "agents get the bounded permission model and run logs"
        )
        raise ContractError(message)
    del feature


# --- Autonomous runs ------------------------------------------------------

PROVISIONAL_START = "<!-- workflow-provisional: begin -->"
PROVISIONAL_END = "<!-- workflow-provisional: end -->"
PROVISIONAL_BLOCK = re.compile(
    re.escape(PROVISIONAL_START) + r"(.*?)" + re.escape(PROVISIONAL_END), re.DOTALL
)
PROVISIONAL_DIGEST = re.compile(
    r"^- \*\*Provisional spec digest\*\*: (sha256:[0-9a-f]{64})$", re.MULTILINE
)
PROVISIONAL_DECISION = re.compile(r"^- \*\*Decision\*\*: (PD-\d{4})$", re.MULTILINE)
FINDINGS_START = "<!-- ballast-findings: begin -->"
FINDINGS_END = "<!-- ballast-findings: end -->"
FINDINGS_BLOCK = re.compile(
    "\n*" + re.escape(FINDINGS_START) + r".*?" + re.escape(FINDINGS_END) + "\n*",
    re.DOTALL,
)
FINDINGS_HEADING = re.compile(r"(?im)^#{1,6}\s+.*\bfindings?\b")
SEVERITY = "(?:critical|high|medium|low)"
SEVERITY_TAG = re.compile(
    rf"(?im)(\[\s*{SEVERITY}\s*\]|\*\*\s*{SEVERITY}\s*\*\*|\bseverity\s*[:=]\s*\**\s*"
    rf"{SEVERITY}\b|^\s*(?:[-*]\s+)?\(?{SEVERITY}\)?\s*[:—–-]\s)"
)
PD_REF = re.compile(r"\bPD-\d{4}\b")
MODEL = re.compile(r"[A-Za-z0-9._:/@+-]{1,100}")
FINDING_ID = re.compile(r"F-\d{3}")
DRAFT_FIELDS = (
    "point",
    "decision",
    "summary",
    "basis",
    "evidence",
    "artifact",
    "model",
    "material",
    "supersedes",
    "risk",
    "boundaries",
    "privileged_actions",
    "review",
    "assumption",
)
RUNNER_FIELDS = ("id", "prev", "at", "provider", "step_id", "role", "agent")
# Review kinds each review point may record.
POINT_KINDS = {
    "plan-review": ("plan",),
    "implementation-review": ("engineering",),
    "specialist-review": (
        "test",
        "security",
        "documentation",
        "architecture",
        "dependency",
        "database-migration",
    ),
    "spec-reconciliation": ("spec-reconciliation",),
}
LOCKFILES = (
    "uv.lock",
    "poetry.lock",
    "Pipfile.lock",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "Cargo.lock",
    "Cargo.toml",
    "go.sum",
    "go.mod",
    "Gemfile.lock",
    "composer.lock",
    "pyproject.toml",
    "package.json",
)


class BlockedError(ContractError):
    """A contract failure that already recorded its block in operator state."""


def _workflow_id(root: Path, run_id: str) -> str | None:
    state = root / ".specify/workflows/runs" / run_id / "state.json"
    try:
        return json.loads(state.read_text(encoding="utf-8")).get("workflow_id")
    except (OSError, ValueError, AttributeError):
        return None


def load_run(feature: Feature) -> None:
    """Attach the operator run record of a workflow run, if any."""
    if feature.run_id is None:
        return
    if autonomy is None:
        message = "the Autonomous module autonomy.py is missing; reinstall Ballast"
        raise ContractError(message)
    try:
        record = autonomy.find_run(feature.root, feature.run_id)
    except autonomy.AutonomyError as error:
        message = f"run record unreadable: {error}"
        raise ContractError(message) from error
    workflow = _workflow_id(feature.root, feature.run_id)
    if record is None:
        if workflow == "ballast-autonomous":
            message = (
                "autonomous run has no operator run record; start it with "
                "ballast run start --mode autonomous"
            )
            raise ContractError(message)
        return
    if record["feature"] != feature.relative:
        message = "run record belongs to another feature"
        raise ContractError(message)
    if workflow is not None and workflow != record["workflow"]:
        message = f"run record is for {record['workflow']}, not {workflow}"
        raise ContractError(message)
    if record["workflow"] == "ballast-autonomous":
        feature.run = record
    elif record["workflow"] == "ballast-continue":
        feature.continued = record


def _require_run(feature: Feature) -> dict:
    if feature.run is None:
        message = "this check runs only in an autonomous run (ballast-autonomous)"
        raise ContractError(message)
    return feature.run


def _block(feature: Feature, category: str, condition: str, **fields: object) -> None:
    """Record a block for the run, then fail the step."""
    run = _require_run(feature)
    block = autonomy.make_block(category, condition, run_id=run["run_id"], **fields)
    autonomy.record_block(feature.root, run["run_id"], block)
    raise BlockedError(f"{category} block: {condition}")


def _rendered(feature: Feature) -> str:
    run = _require_run(feature)
    return autonomy.render_record(
        run,
        autonomy.read_decisions(feature.root, run["run_id"]),
        autonomy.read_checks(feature.root, run["run_id"]),
    )


def _record_file(feature: Feature) -> Path:
    directory = feature.path / "autonomous"
    if directory.is_symlink():
        message = f"{feature.relative}/autonomous must not be a symlink"
        raise ContractError(message)
    return feature.file("autonomous/record.md")


def write_record(feature: Feature) -> None:
    """Render the committed projection of the operator records."""
    path = _record_file(feature)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_rendered(feature), encoding="utf-8")


def autonomous_preamble(feature: Feature) -> None:
    """Every check of an Autonomous run: active run, untouched record."""
    run = _require_run(feature)
    if run["status"] != "active":
        message = f"autonomous run {run['run_id']} is {run['status']}, not active"
        raise ContractError(message)
    path = _record_file(feature)
    expected = _rendered(feature)
    if not path.exists():
        if autonomy.read_decisions(feature.root, run["run_id"]):
            message = "autonomous record was edited outside the recorder (missing)"
            raise ContractError(message)
        return
    if path.read_text(encoding="utf-8") != expected:
        message = "autonomous record was edited outside the recorder"
        raise ContractError(message)


def check_provisional_intent(feature: Feature) -> None:
    """In an Autonomous run, intent is one agent-provisional decision, never human."""
    run = _require_run(feature)
    spec = check_clarified_spec(feature)
    intent = feature.read("intent.md")
    missing = [section for section in INTENT_SECTIONS if section not in intent]
    if missing:
        message = f"{feature.relative}/intent.md lacks sections: {', '.join(missing)}"
        raise ContractError(message)
    if APPROVAL_START in intent or DIGEST_LINE.search(intent):
        message = (
            f"{feature.relative}/intent.md carries a human approval block; an "
            "autonomous run has no human gate before merge, so it accepts only its "
            "agent-provisional intent decision"
        )
        raise ContractError(message)
    blocks = PROVISIONAL_BLOCK.findall(intent)
    if len(blocks) != 1:
        message = f"{feature.relative}/intent.md has no single provisional intent block"
        raise ContractError(message)
    digests_found = PROVISIONAL_DIGEST.findall(blocks[0])
    decisions = PROVISIONAL_DECISION.findall(blocks[0])
    specs = SPEC_LINE.findall(blocks[0])
    if (
        len(digests_found) != 1
        or len(decisions) != 1
        or specs != [f"{feature.relative}/spec.md"]
    ):
        message = f"{feature.relative}/intent.md provisional block is malformed"
        raise ContractError(message)
    current = autonomy.current(
        autonomy.read_decisions(feature.root, run["run_id"]), "intent"
    )
    if len(current) != 1 or current[0]["id"] != decisions[0]:
        message = (
            f"{feature.relative}/intent.md provisional block does not name the current "
            "intent decision"
        )
        raise ContractError(message)
    if (
        digests_found[0] != spec_digest(spec)
        or current[0].get("spec_digest") != digests_found[0]
    ):
        message = (
            f"{feature.relative}/spec.md changed after the provisional intent "
            "decision; the decision is stale"
        )
        raise ContractError(message)


def decision_sections(text: str) -> list[tuple[str, str, str]]:
    """(DEC id, Proposal|Resolution, section body) for each DEC record."""
    matches = list(DECISION_RECORD.finditer(text))
    sections = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections.append((match.group(1), match.group(2), text[match.end() : end]))
    return sections


def _provisional_resolutions(feature: Feature, text: str) -> set[str]:
    """DEC ids whose resolution cites a logged decision-resolution PD."""
    run = _require_run(feature)
    logged = {
        entry["id"]
        for entry in autonomy.read_decisions(feature.root, run["run_id"])
        if entry.get("point") == "decision-resolution"
    }
    return {
        dec
        for dec, kind, body in decision_sections(text)
        if kind.lower() == "resolution"
        and any(ref in logged for ref in PD_REF.findall(body))
    }


def _repo_path(feature: Feature, value: object, name: str) -> str:
    """A repository-relative path that exists, inside the checkout, no links."""
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 300  # noqa: PLR2004
        or value.startswith("/")
        or "\\" in value
    ):
        message = f"{name} must be a repository-relative path"
        raise ContractError(message)
    parts = Path(value).parts
    if ".." in parts or "." in parts or value != Path(value).as_posix():
        message = f"{name} {value!r} must not contain '..'"
        raise ContractError(message)
    current = feature.root
    for part in parts:
        current = current / part
        if current.is_symlink():
            message = f"{name} {value!r} goes through a symlink"
            raise ContractError(message)
    if not current.exists():
        message = f"{name} {value!r} does not exist"
        raise ContractError(message)
    return value


def _evidence(feature: Feature, value: object) -> list[str]:
    if not isinstance(value, list) or not 1 <= len(value) <= 20:  # noqa: PLR2004
        message = "evidence must list 1-20 paths or https:// links"
        raise ContractError(message)
    out = []
    for item in value:
        if isinstance(item, str) and item.startswith("https://"):
            if len(item) > 500 or re.search(r"\s", item):  # noqa: PLR2004
                message = f"evidence link {item[:60]!r} is invalid"
                raise ContractError(message)
            out.append(item)
        else:
            out.append(_repo_path(feature, item, "evidence"))
    return out


def _text_field(value: object, name: str, limit: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        message = f"{name} must be 1-{limit} characters"
        raise ContractError(message)
    if autonomy.HUMAN_APPROVAL.search(value):
        message = f"{name} claims a human approval; agent decisions are provisional"
        raise ContractError(message)
    if autonomy.WORKFLOW_MARKER.search(value):
        message = f"{name} contains a workflow marker"
        raise ContractError(message)
    return value


def _string_list(value: object, name: str, limit: int = 20) -> list[str]:
    if not isinstance(value, list) or len(value) > limit:
        message = f"{name} must be a list of at most {limit} strings"
        raise ContractError(message)
    if not all(isinstance(v, str) and 0 < len(v.strip()) <= 100 for v in value):  # noqa: PLR2004
        message = f"{name} must contain short strings"
        raise ContractError(message)
    return sorted({" ".join(v.lower().split()) for v in value})


def _validate_review(feature: Feature, review: object, point: str, step: dict) -> dict:
    run = _require_run(feature)
    if not isinstance(review, dict):
        message = f"{point} draft needs a review entry"
        raise ContractError(message)
    kind = review.get("kind")
    if kind not in POINT_KINDS[point]:
        message = f"{point} review kind must be one of {', '.join(POINT_KINDS[point])}"
        raise ContractError(message)
    if review.get("verdict") not in autonomy.VERDICTS:
        message = f"{kind} review has an unknown verdict"
        raise ContractError(message)
    report = f"{feature.relative}/reviews/{kind}.md"
    if review.get("report") != report:
        message = f"{kind} review report must be {report}"
        raise ContractError(message)
    _repo_path(feature, report, "review report")
    findings = review.get("findings")
    if not isinstance(findings, list) or len(findings) > 100:  # noqa: PLR2004
        message = f"{kind} review findings must be a list"
        raise ContractError(message)
    checked = []
    for finding in findings:
        if not isinstance(finding, dict) or not FINDING_ID.fullmatch(
            str(finding.get("id"))
        ):
            message = f"{kind} review has a finding without an F-NNN id"
            raise ContractError(message)
        for field, allowed in (
            ("severity", autonomy.SEVERITIES),
            ("label", autonomy.FINDING_LABELS),
            ("disposition", autonomy.DISPOSITIONS),
        ):
            if finding.get(field) not in allowed:
                message = f"{kind} finding {finding['id']} has an invalid {field}"
                raise ContractError(message)
        reason = finding.get("reason")
        if reason is not None:
            reason = _text_field(reason, f"finding {finding['id']} reason", 1000)
        evidence = finding.get("evidence", [])
        checked.append(
            {
                "id": finding["id"],
                "severity": finding["severity"],
                "label": finding["label"],
                "disposition": finding["disposition"],
                "reason": reason,
                "evidence": _evidence(feature, evidence) if evidence else [],
            }
        )
    entry = {
        "kind": kind,
        "verdict": review["verdict"],
        "report": report,
        "cross_provider": step.get("integration") != run["integration"],
        "author_provider": run["integration"],
        "findings": checked,
    }
    required = review.get("required_kinds", [])
    if required:
        if not isinstance(required, list) or any(
            k not in autonomy.REVIEW_KINDS for k in required
        ):
            message = f"{kind} review declares unknown required kinds"
            raise ContractError(message)
        entry["required_kinds"] = sorted(set(required))
    if "privileged_actions" in review:
        entry["privileged_actions"] = _string_list(
            review["privileged_actions"], "review privileged_actions"
        )
    return entry


def _validate_draft(  # noqa: C901, PLR0912
    feature: Feature, data: object, point: str, step: dict
) -> dict:
    """Check one decision draft against the draft contract."""
    if not isinstance(data, dict):
        message = f"{point} draft must be a JSON object"
        raise ContractError(message)
    notes = [
        f"ignored runner-owned field {key}"
        for key in sorted(data)
        if key in RUNNER_FIELDS
    ] + [
        f"ignored unknown field {key}"
        for key in sorted(data)
        if key not in RUNNER_FIELDS and key not in DRAFT_FIELDS
    ]
    if data.get("point") != point:
        message = f"draft point {data.get('point')!r} does not match {point}"
        raise ContractError(message)
    if data.get("decision") != autonomy.POINT_DECISION[point]:
        message = f"{point} decision must be {autonomy.POINT_DECISION[point]}"
        raise ContractError(message)
    summary = _text_field(data.get("summary"), "summary", 500)
    if "\n" in summary or "\r" in summary:
        message = "summary must be one line"
        raise ContractError(message)
    basis = _text_field(data.get("basis"), "basis", 2000)
    artifact = _repo_path(feature, data.get("artifact"), "artifact")
    artifact_path = feature.root / artifact
    if not artifact_path.is_file():
        message = f"artifact {artifact!r} must be a regular file"
        raise ContractError(message)
    model = data.get("model")
    if model is None:
        model = "unreported"
    elif not isinstance(model, str) or not MODEL.fullmatch(model):
        message = "model must be a short model name"
        raise ContractError(message)
    material = data.get("material", False)
    supersedes = data.get("supersedes")
    if not isinstance(material, bool) or (
        supersedes is not None and not re.fullmatch(r"PD-\d{4}", str(supersedes))
    ):
        message = "material must be a boolean and supersedes a PD-NNNN id or null"
        raise ContractError(message)
    risk = data.get("risk")
    if risk is not None and risk not in autonomy.RISKS:
        message = "risk must be R0, R1 or R2"
        raise ContractError(message)
    if "privileged_actions" not in data:
        message = "draft must list privileged_actions (empty when none)"
        raise ContractError(message)
    entry = {
        "point": point,
        "decision": autonomy.POINT_DECISION[point],
        "summary": summary,
        "basis": basis,
        "evidence": _evidence(feature, data.get("evidence")),
        "artifact": {"path": artifact, "sha256": autonomy.sha256_file(artifact_path)},
        "agent": {
            "provider": step.get("integration", "runner"),
            "model": model,
            "role": step.get("role", "runner"),
            "step_id": step.get("step", "runner"),
        },
        "material": material,
        "supersedes": supersedes,
        "privileged_actions": _string_list(
            data["privileged_actions"], "privileged_actions"
        ),
        "risk": risk,
        "boundaries": _string_list(data.get("boundaries", []), "boundaries"),
        "at": autonomy.now(),
    }
    if point in autonomy.REVIEW_POINTS:
        entry["review"] = _validate_review(feature, data.get("review"), point, step)
        entry["privileged_actions"] = sorted(
            set(entry["privileged_actions"])
            | set(entry["review"].pop("privileged_actions", []))
        )
    elif data.get("review") is not None:
        message = f"{point} draft must not carry a review"
        raise ContractError(message)
    assumption = data.get("assumption")
    if point == "clarification":
        if not isinstance(assumption, dict):
            message = "clarification draft needs an assumption"
            raise ContractError(message)
        if assumption.get("reversible") is not True:
            message = (
                "clarification assumption must be reversible; a non-reversible "
                "choice must be a block"
            )
            raise ContractError(message)
        entry["assumption"] = {
            "question": _text_field(assumption.get("question"), "question", 1000),
            "default": _text_field(assumption.get("default"), "default", 1000),
            "reversible": True,
        }
    elif assumption is not None:
        message = f"{point} draft must not carry an assumption"
        raise ContractError(message)
    if notes:
        entry["notes"] = notes
    return entry


def _qualifying_steps(steps: list[dict], point: str) -> list[dict]:
    """Agent steps whose drafts a recorder for point may accept.

    The immediately preceding agent step, or, for a review point, the trailing
    run of reviewer steps (review-implementation then review-specialists).
    """
    if not steps or not steps[-1].get("ran"):
        return []
    if point not in autonomy.REVIEW_POINTS:
        return [steps[-1]] if steps[-1].get("role") == "author" else []
    found: list[dict] = []
    for step in reversed(steps):
        if not step.get("ran") or step.get("role") != "reviewer":
            break
        found.insert(0, step)
    return found


def _draft_point(name: str, points: list[str]) -> str | None:
    for point in points:
        if name == f"{point}.json" or (
            point in autonomy.MULTI_ENTRY
            and re.fullmatch(re.escape(point) + r"-[a-z0-9-]{1,40}\.json", name)
        ):
            return point
    return None


def _collect_drafts(
    feature: Feature, points: list[str]
) -> tuple[list[tuple[str, str, object, dict]], list[dict]]:
    """Drafts of the qualifying steps, read from their operator copies."""
    run = _require_run(feature)
    steps = autonomy.unconsumed_steps(feature.root, run["run_id"])
    qualifying = _qualifying_steps(steps, points[0])
    listed: dict[str, tuple[str, dict]] = {}
    for step in qualifying:
        for name, digest in (step.get("drafts") or {}).items():
            if digest == "invalid":
                message = f"draft {name} from step {step['step']} is not a regular file"
                raise ContractError(message)
            listed[name] = (digest, step)
    directory = autonomy.drafts_dir(feature.root, feature.relative)
    if directory.is_symlink():
        message = "the drafts directory must not be a symlink"
        raise ContractError(message)
    for path in sorted(directory.iterdir()) if directory.is_dir() else []:
        if (
            path.name not in listed
            or path.is_symlink()
            or not path.is_file()
            or autonomy.sha256_file(path) != listed[path.name][0]
        ):
            message = (
                f"draft {path.name} was not written by the immediately preceding "
                "agent step; refusing it"
            )
            raise ContractError(message)
    drafts = []
    for name, (digest, step) in sorted(listed.items()):
        point = _draft_point(name, points)
        if point is None:
            message = f"unexpected draft {name} for {points[0]}"
            raise ContractError(message)
        copy = autonomy.snapshot_draft(feature.root, run["run_id"], step["step"], name)
        data = copy.read_bytes()
        if hashlib.sha256(data).hexdigest() != digest:
            message = f"operator copy of draft {name} does not match its digest"
            raise ContractError(message)
        try:
            drafts.append((name, point, json.loads(data), step))
        except ValueError as error:
            message = f"draft {name} is not valid JSON"
            raise ContractError(message) from error
    return drafts, qualifying


def _consume(feature: Feature, names: list[str]) -> None:
    run = _require_run(feature)
    directory = autonomy.drafts_dir(feature.root, feature.relative)
    for name in names:
        path = directory / name
        if path.is_file() and not path.is_symlink():
            path.unlink()
    autonomy.consume_steps(feature.root, run["run_id"])


def _strip_findings(text: str) -> str:
    return FINDINGS_BLOCK.sub("\n", text)


def _render_findings(feature: Feature, review: dict) -> None:
    """Write the draft's findings into the report; the narrative holds none."""
    path = feature.root / review["report"]
    narrative = _strip_findings(path.read_text(encoding="utf-8")).rstrip("\n")
    lines = [FINDINGS_START, "## Findings (recorded from the review draft)", ""]
    lines += [
        f"- {f['id']} ({f['severity']}, {f['label']}, {f['disposition']}): "
        f"{autonomy.neutralize(f['reason'] or 'no reason given')}"
        for f in review["findings"]
    ] or ["None."]
    lines.append(FINDINGS_END)
    path.write_text(narrative + "\n\n" + "\n".join(lines) + "\n", encoding="utf-8")


def _check_narrative(feature: Feature, review: dict) -> None:
    text = _strip_findings(
        (feature.root / review["report"]).read_text(encoding="utf-8")
    )
    if FINDINGS_HEADING.search(text) or SEVERITY_TAG.search(text):
        message = (
            f"{review['report']} carries findings or severity tags in its narrative; "
            "every finding belongs in the review draft"
        )
        raise ContractError(message)


def _check_dispositions(review: dict) -> None:
    for finding in review["findings"]:
        severity, disposition = finding["severity"], finding["disposition"]
        if disposition == "open" and severity not in {"low", "info"}:
            message = f"{finding['id']}: open is valid only for low and info findings"
            raise ContractError(message)
        if disposition == "accepted-provisionally" and not finding["reason"]:
            message = f"{finding['id']}: accepted-provisionally needs a reason"
            raise ContractError(message)


def _changed_since_baseline(feature: Feature) -> list[str]:
    path = feature.root / STATE_DIR / feature.key / "implementation-baseline.json"
    try:
        tree = json.loads(path.read_text(encoding="utf-8")).get("tree")
    except (OSError, ValueError, AttributeError) as error:
        message = "no implementation baseline recorded before implementation"
        raise ContractError(message) from error
    if not isinstance(tree, str) or not TREE_ID.fullmatch(tree):
        message = "implementation baseline has no valid tree id"
        raise ContractError(message)
    return _git(
        feature.root,
        "diff-tree",
        "-r",
        "--name-only",
        "--end-of-options",
        tree,
        worktree_tree(feature.root),
    ).splitlines()


def required_kinds(feature: Feature, reviews: list[dict]) -> set[str]:
    """Review kinds an Autonomous implementation review must cover (R-08)."""
    run = _require_run(feature)
    required = {"engineering", "test", "security"}
    for name in _changed_since_baseline(feature):
        base = name.rsplit("/", 1)[-1]
        parts = name.split("/")
        if name.startswith(".github/"):
            required.add("security")
        if base in LOCKFILES or re.fullmatch(r"requirements.*\.txt", base):
            required.add("dependency")
        if any(part in {"migrations", "migration"} for part in parts[:-1]):
            required.add("database-migration")
        if (
            name.startswith("docs/")
            or base.startswith("README")
            or (len(parts) == 1 and base.endswith((".toml", ".yml", ".yaml")))
        ):
            required.add("documentation")
    if run["risk"]["level"] == "R2" or run["risk"].get("boundaries"):
        required |= {"security", "architecture"}
    for review in reviews:
        required.update(review.get("required_kinds", []))
    return required


def _frozen_check(feature: Feature) -> None:
    run = _require_run(feature)
    frozen = run.get("frozen_tree")
    if frozen and autonomy.tree_digest(feature.root, (feature.relative,)) != frozen:
        _block(
            feature,
            "postcondition",
            "files outside the feature directory changed after implementation "
            "review; after the reviews only the spec, plan, tasks, decisions and "
            "drafts may change (no fix loop in #27)",
        )


def _reviewer_tree_check(feature: Feature, steps: list[dict]) -> None:
    before = steps[0].get("tree_before") if steps else None
    exclusions = (
        f"{feature.relative}/reviews",
        f"{feature.relative}/autonomous/drafts",
    )
    if before and autonomy.tree_digest(feature.root, exclusions) != before:
        _block(
            feature,
            "postcondition",
            "a reviewer step changed files outside reviews/ and drafts/",
        )


def _eligibility_recheck(feature: Feature, entries: list[dict]) -> tuple[str, list]:
    """Raise risk or grow privileged actions; block when no longer eligible."""
    run = _require_run(feature)
    policy = run["eligibility"]["policy"]
    level = run["risk"]["level"]
    for entry in entries:
        declared = entry.get("risk")
        if declared and autonomy.RISKS.index(declared) > autonomy.RISKS.index(level):
            level = declared
        elif declared and declared != level:
            entry.setdefault("notes", []).append(
                f"ignored lower declared risk {declared}; risk stays {level}"
            )
    boundaries = sorted(
        set(run["risk"].get("boundaries", []))
        | {b for e in entries for b in e.get("boundaries", [])}
    )
    decisions = autonomy.read_decisions(feature.root, run["run_id"])
    actions = autonomy.privileged_union(run, [*decisions, *entries])
    reasons = autonomy.risk_reasons(level, boundaries, policy) + [
        f"{autonomy.REFUSAL}privileged action {action} before merge"
        for action in autonomy.unauthorized_actions(actions, policy)
    ]
    if reasons:
        autonomy.raise_risk(run, level, boundaries, None)
        autonomy.write_run(feature.root, run)
        _block(feature, "ineligible", "; ".join(reasons))
    return level, boundaries


def _final_check(feature: Feature, entry: dict) -> None:
    run = _require_run(feature)
    decisions = autonomy.read_decisions(feature.root, run["run_id"])
    for point in autonomy.SINGLE_POINTS:
        found = autonomy.current(decisions, point)
        if len(found) != 1:
            message = (
                f"final acceptance needs exactly one current {point} decision, "
                f"found {len(found)}"
            )
            raise ContractError(message)
    check_intent(feature)
    checked = run.get("checked_tree")
    if (
        not checked
        or autonomy.checked_digest(feature.root, feature.relative) != checked
    ):
        _block(
            feature,
            "postcondition",
            "the tree changed after run-checks; decide-final may write only its draft",
        )
    for current in autonomy.current_decisions(decisions):
        artifact = current.get("artifact") or {}
        path = feature.root / artifact.get("path", "")
        if not artifact.get("path"):
            continue
        if not path.is_file() or path.is_symlink():
            note = f"{current['id']} {current['point']}: {artifact['path']} no longer exists"
        elif autonomy.sha256_file(path) != artifact.get("sha256"):
            note = (
                f"{current['id']} {current['point']}: {artifact['path']} changed after "
                "the decision"
            )
        else:
            continue
        entry.setdefault("notes", []).append(note)


def _resolution_targets(feature: Feature, drafts: list[tuple]) -> dict[str, str]:
    """Map each decision-resolution draft name to its DEC record."""
    path = feature.file("decisions.md")
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    resolutions = {
        int(dec.split("-")[1]): dec
        for dec, kind, _ in decision_sections(text)
        if kind.lower() == "resolution"
    }
    targets = {}
    for name, *_ in drafts:
        match = re.fullmatch(r"decision-resolution-(\d{1,6})\.json", name)
        if match is None or int(match.group(1)) not in resolutions:
            message = (
                f"{name} must be named decision-resolution-<DEC number>.json and "
                "match a resolution record in decisions.md"
            )
            raise ContractError(message)
        targets[name] = resolutions[int(match.group(1))]
    return targets


def _stamp_resolution(feature: Feature, dec: str, entry: dict) -> None:
    """Point a DEC resolution at its provisional decision."""
    path = feature.file("decisions.md")
    text = path.read_text(encoding="utf-8")
    for found, kind, body in decision_sections(text):
        if found != dec or kind.lower() != "resolution":
            continue
        status = f"- **Status**: agent-provisional ({entry['id']}), not human-approved"
        material = f"- **Material**: {'yes' if entry['material'] else 'no'}"
        updated = re.sub(r"(?m)^- \*\*Status\*\*:.*$", status, body, count=1)
        if updated == body:
            updated = "\n\n" + status + updated
        if re.search(r"(?m)^- \*\*Material\*\*:", updated):
            updated = re.sub(r"(?m)^- \*\*Material\*\*:.*$", material, updated, count=1)
        else:
            updated = updated.replace(status, status + "\n" + material, 1)
        text = text.replace(body, updated, 1)
        break
    path.write_text(text, encoding="utf-8")


def _intent_block(feature: Feature, entry: dict) -> str:
    run = _require_run(feature)
    agent = entry["agent"]
    return "\n".join(
        (
            PROVISIONAL_START,
            "- **Status**: agent-provisional, not human-approved",
            f"- **Decision**: {entry['id']}",
            f"- **Decided by**: {agent['provider']}/{agent['model']} ({agent['role']})",
            f"- **Recorded**: {entry['at']}",
            f"- **Source**: ballast-autonomous run ({run['run_id']})",
            f"- **Spec**: {feature.relative}/spec.md",
            f"- **Provisional spec digest**: {entry['spec_digest']}",
            PROVISIONAL_END,
        )
    )


def _expected_drafts(point: str, drafts: list[tuple]) -> None:
    names = [name for name, *_ in drafts]
    if point in {"clarification", "decision-resolution"}:
        return
    main = f"{point}.json"
    if names.count(main) != 1:
        message = f"the preceding agent step wrote no {main} draft"
        raise ContractError(message)


def record_decision(feature: Feature, point: str) -> None:  # noqa: C901, PLR0912
    """Validate the preceding step's drafts and append provisional decisions."""
    run = _require_run(feature)
    points = (
        [point, "specialist-review"] if point == "implementation-review" else [point]
    )
    drafts, steps = _collect_drafts(feature, points)
    _expected_drafts(point, drafts)
    entries = [
        _validate_draft(feature, data, draft_point, step)
        for _, draft_point, data, step in drafts
    ]
    if point in autonomy.REVIEW_POINTS:
        _reviewer_tree_check(feature, steps)
    if point in {"decision-resolution", "spec-reconciliation"}:
        _frozen_check(feature)
    reviews = [entry["review"] for entry in entries if "review" in entry]
    for review in reviews:
        _check_narrative(feature, review)
    for review in reviews:
        _render_findings(feature, review)
    blocking = [
        f"{review['kind']} {finding['id']} ({finding['severity']})"
        for review in reviews
        for finding in review["findings"]
        if finding["severity"] in autonomy.BLOCKING_SEVERITIES
    ]
    if blocking:
        _block(
            feature,
            "review-finding",
            "unresolved high or critical review findings: " + ", ".join(blocking),
            evidence=sorted({review["report"] for review in reviews}),
        )
    for review in reviews:
        _check_dispositions(review)
    if point == "implementation-review":
        missing = sorted(
            required_kinds(feature, reviews) - {r["kind"] for r in reviews}
        )
        if missing:
            message = f"required reviews missing: {', '.join(missing)}"
            raise ContractError(message)
    targets = (
        _resolution_targets(feature, drafts) if point == "decision-resolution" else {}
    )
    level, boundaries = _eligibility_recheck(feature, entries)
    if point == "intent":
        intent = feature.file("intent.md")
        if intent.exists() and (
            APPROVAL_START in intent.read_text(encoding="utf-8")
            or DIGEST_LINE.search(intent.read_text(encoding="utf-8"))
        ):
            message = (
                f"{feature.relative}/intent.md carries a human approval block; an "
                "autonomous run accepts only its agent-provisional intent decision"
            )
            raise ContractError(message)
        spec = check_clarified_spec(feature)
        for entry in entries:
            entry["spec_digest"] = spec_digest(spec)
            current = autonomy.current(
                autonomy.read_decisions(feature.root, run["run_id"]), "intent"
            )
            if current and entry["supersedes"] is None:
                entry["supersedes"] = current[-1]["id"]
    if point == "final-acceptance":
        for entry in entries:
            _final_check(feature, entry)
    appended = []
    for (name, *_), entry in zip(drafts, entries, strict=True):
        risk_raised = entry["risk"] and entry["risk"] == level
        for key in ("risk", "boundaries"):
            if not entry[key]:
                entry.pop(key)
        stored = autonomy.append_decision(feature.root, run["run_id"], entry)
        appended.append((name, stored))
        if risk_raised:
            autonomy.raise_risk(run, level, boundaries, stored["id"])
    autonomy.raise_risk(run, None, boundaries, None)
    if point == "implementation-review":
        run["frozen_tree"] = autonomy.tree_digest(feature.root, (feature.relative,))
    autonomy.write_run(feature.root, run)
    for name, stored in appended:
        if name in targets:
            _stamp_resolution(feature, targets[name], stored)
        if point == "intent":
            spec = check_clarified_spec(feature)
            _write_intent_block(
                feature,
                spec,
                _intent_block(feature, stored),
                PROVISIONAL_START,
                PROVISIONAL_END,
            )
    write_record(feature)
    _consume(feature, [name for name, *_ in drafts])
    if point == "intent":
        check_intent(feature)


def renew_intent(feature: Feature) -> None:
    """Supersede a stale provisional intent after a spec-changing resolution."""
    run = _require_run(feature)
    spec = check_clarified_spec(feature)
    decisions = autonomy.read_decisions(feature.root, run["run_id"])
    current = autonomy.current(decisions, "intent")
    if len(current) != 1:
        message = "no single current intent decision to renew"
        raise ContractError(message)
    old = current[0]
    digest = spec_digest(spec)
    if old.get("spec_digest") == digest:
        return
    number = int(old["id"].split("-")[1])
    resolutions = [
        entry["id"]
        for entry in decisions
        if entry["point"] == "decision-resolution"
        and int(entry["id"].split("-")[1]) > number
    ]
    spec_path = f"{feature.relative}/spec.md"
    entry = {
        "point": "intent",
        "decision": "accept",
        "summary": "Spec changed after the provisional intent; renewed by the runner "
        "without re-review",
        "basis": (
            f"spec.md changed after {old['id']}"
            + (f" through {', '.join(resolutions)}" if resolutions else "")
            + ". The runner rebinds the provisional intent to the changed spec; no "
            "agent re-reviewed the renewed spec. The merge reviewer must review it."
        ),
        "evidence": [spec_path],
        "artifact": {
            "path": spec_path,
            "sha256": autonomy.sha256_file(feature.root / spec_path),
        },
        "agent": {
            "provider": "runner",
            "model": "none",
            "role": "runner",
            "step_id": "renew-intent",
        },
        "material": True,
        "supersedes": old["id"],
        "privileged_actions": [],
        "spec_digest": digest,
        "at": autonomy.now(),
    }
    stored = autonomy.append_decision(feature.root, run["run_id"], entry)
    _write_intent_block(
        feature,
        spec,
        _intent_block(feature, stored),
        PROVISIONAL_START,
        PROVISIONAL_END,
    )
    write_record(feature)
    check_intent(feature)


def record_provisional_intent(feature: Feature, *, renew: bool = False) -> None:
    """Record the intent decision, or renew it (`--renew`) after a spec change."""
    if renew:
        renew_intent(feature)
    else:
        record_decision(feature, "intent")


def _protected_digests(root: Path) -> dict[str, str]:
    skip = [root / ".specify" / name for name in autonomy.SPECIFY_WRITABLE]
    return digests(root, input_bases(root), skip)


def _mark_tampered(root: Path, reasons: list[str]) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
    try:
        handle = os.open(root / "BALLAST_TAMPERED", flags, 0o600)
    except FileExistsError:
        return
    with os.fdopen(handle, "w") as marker:
        marker.write("\n".join(reasons) + "\n")


def run_checks(feature: Feature) -> None:
    """Run the trusted [checks] commands, confined, and record their results."""
    run = _require_run(feature)
    try:
        checks = autonomy.parse_checks(autonomy.load_config(feature.root))
    except autonomy.AutonomyError as error:
        _block(feature, "postcondition", str(error))
    env = autonomy.confined_env(dict(os.environ), None)
    before = _protected_digests(feature.root)
    results = []
    with tempfile.TemporaryDirectory(prefix="ballast-checks-") as private:
        for command in checks["commands"]:
            remaining = autonomy.remaining_seconds(run)
            if remaining <= 0:
                _block(feature, "limit", "wall-time limit exhausted before run-checks")
            argv = autonomy.confined_argv(
                feature.root,
                ["sh", "-c", command],
                private=Path(private),
                feature=feature.relative,
                env=env,
            )
            started = time.monotonic()
            timed_out = False
            try:
                done = subprocess.run(  # noqa: S603 - resolved bwrap, argument list
                    argv,
                    cwd=feature.root,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=min(checks["timeout_minutes"] * 60, remaining),
                    check=False,
                )
                code = done.returncode
                sys.stdout.write(done.stdout[-4000:])
                sys.stderr.write(done.stderr[-4000:])
            except subprocess.TimeoutExpired:
                code, timed_out = 124, True
            results.append(
                {
                    "command": command,
                    "exit": code,
                    "seconds": round(time.monotonic() - started, 1),
                    "timed_out": timed_out,
                    "provenance": "runner",
                }
            )
    autonomy.write_json(
        autonomy.run_dir(feature.root, run["run_id"]) / "checks.json", results
    )
    after = _protected_digests(feature.root)
    changed = sorted(
        n for n in before.keys() | after.keys() if before.get(n) != after.get(n)
    )
    if changed:
        _mark_tampered(feature.root, changed)
        _block(
            feature,
            "tamper",
            "a check command changed protected inputs: " + ", ".join(changed[:10]),
        )
    write_record(feature)
    failed = [r for r in results if r["exit"] != 0]
    if failed:
        _block(
            feature,
            "postcondition",
            "check commands failed: "
            + ", ".join(
                f"{r['command']!r} ({'timed out' if r['timed_out'] else 'exit ' + str(r['exit'])})"
                for r in failed
            ),
        )
    run["checked_tree"] = autonomy.checked_digest(feature.root, feature.relative)
    autonomy.write_run(feature.root, run)


def check_autonomous_preflight(feature: Feature) -> None:
    """Start of an Autonomous run: launcher env, eligible record, clean tree."""
    check_preflight(feature)
    run = _require_run(feature)
    if not run["eligibility"].get("eligible"):
        message = "autonomous run record is not eligible"
        raise ContractError(message)
    try:
        status = autonomy.git(feature.root, "status", "--porcelain").stdout
        findings = [
            f"attribute driver {d} is configured"
            for d in autonomy.attribute_drivers(feature.root)
        ] + autonomy.program_findings(feature.root)
        if status.strip():
            message = (
                "an autonomous run needs a clean worktree; commit or stash local "
                "changes first"
            )
            raise ContractError(message)
        if findings:
            raise ContractError("; ".join(findings))
        run["head"] = autonomy.git(feature.root, "rev-parse", "HEAD").stdout.strip()
        autonomy.write_json(
            autonomy.run_dir(feature.root, run["run_id"]) / "git-config.json",
            autonomy.config_snapshot(feature.root),
        )
    except autonomy.AutonomyError as error:
        raise ContractError(str(error)) from error
    autonomy.write_run(feature.root, run)


def check_continue_preflight(feature: Feature) -> None:
    """Start of a human-gated continuation of an Autonomous run."""
    check_preflight(feature)
    record = feature.continued
    if record is None or record["workflow"] != "ballast-continue":
        message = "start ballast-continue with ballast run continue RUN_ID"
        raise ContractError(message)
    if autonomy.effective_mode(record) != "human-gated":
        message = "a continuation must be human-gated"
        raise ContractError(message)
    try:
        source = autonomy.read_run(feature.root, str(record.get("continues")))
    except autonomy.AutonomyError as error:
        message = f"continued run is unreadable: {error}"
        raise ContractError(message) from error
    if (
        source["workflow"] != "ballast-autonomous"
        or source["status"] != "continued"
        or source["feature"] != feature.relative
    ):
        message = f"run {source['run_id']} is not a continued autonomous run"
        raise ContractError(message)
    baseline = feature.root / STATE_DIR / feature.key / "implementation-baseline.json"
    if not baseline.is_file():
        message = "the continued run's implementation baseline was not copied"
        raise ContractError(message)


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
    "autonomous-preflight": check_autonomous_preflight,
    "continue-preflight": check_continue_preflight,
    "record-decision": record_decision,
    "record-provisional-intent": record_provisional_intent,
    "run-checks": run_checks,
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
    feature = Feature(root, value, run_id)
    feature.run_id = run_id
    return feature


def _run_check(feature: Feature, arguments: argparse.Namespace) -> None:
    check = arguments.check
    if check == "record-decision":
        if arguments.point is None:
            message = "record-decision needs --point"
            raise ContractError(message)
        record_decision(feature, arguments.point)
    elif check == "record-provisional-intent":
        record_provisional_intent(feature, renew=arguments.renew)
    else:
        CHECKS[check](feature)


def main(argv: list[str] | None = None) -> int:
    """Run one check and report the result."""
    if autonomy is None:
        sys.stderr.write("workflow contract failed: autonomy.py is missing\n")
        return 1
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("check", choices=sorted(CHECKS))
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--run", help="workflow run id; reads its feature_directory")
    target.add_argument("--feature", help="specs/<issue-number>-<slug>")
    parser.add_argument("--point", choices=autonomy.DECISION_POINTS)
    parser.add_argument("--renew", action="store_true")
    arguments = parser.parse_args(argv)
    feature = None
    try:
        feature = resolve_feature(Path.cwd(), arguments.run, arguments.feature)
        load_run(feature)
        if feature.run is not None:
            autonomous_preamble(feature)
        _run_check(feature, arguments)
    except (ContractError, autonomy.AutonomyError) as error:
        sys.stderr.write(f"workflow contract failed [{arguments.check}]: {error}\n")
        if (
            feature is not None
            and feature.run is not None
            and not isinstance(error, BlockedError)
        ):
            # The run stops here; the block tells run.py and the operator why.
            category = (
                error.category
                if isinstance(error, autonomy.AutonomyError)
                else "postcondition"
            )
            step = arguments.check + (
                f" --point {arguments.point}" if arguments.point else ""
            )
            try:
                autonomy.record_block(
                    feature.root,
                    feature.run["run_id"],
                    autonomy.make_block(
                        category,
                        f"{step}: {error}",
                        run_id=feature.run["run_id"],
                        step_id=step,
                    ),
                )
            except (autonomy.AutonomyError, OSError) as failure:
                sys.stderr.write(f"could not record the block: {failure}\n")
        return 1
    sys.stdout.write(f"workflow contract ok [{arguments.check}]: {feature.relative}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
