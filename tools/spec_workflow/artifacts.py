#!/usr/bin/env python3
"""Deterministic postconditions for the ballast-feature Spec Kit workflow.

An agent exiting 0 does not prove it produced anything. Each check below
verifies an observable artifact contract and exits non-zero with a diagnostic
when the contract is not met. Checks are cumulative: a later check re-verifies
the artifacts it depends on, so a resumed run cannot trust stale step state.

Run from the repository root:

    artifacts.py <check> (--run RUN_ID | --feature specs/<number>-<slug>)
        [--point POINT] [--renew] [--recheck] [--feedback]

In an Autonomous run (operator run record with workflow ballast-autonomous),
every check first requires the run to be active and the committed
`autonomous/record.md` to equal its rendering from the operator logs. The
`record-*` checks validate agent drafts and append provisional decisions;
`check_intent` and `check_decisions` accept only agent-provisional records
there, and never count them as human approval in a human-gated run.

The fix loop (#21): `run-checks --feedback` records the `[checks]` results
without blocking on a failure; the implementation-review recorder sets the
run's fix state instead of blocking while a fix cycle remains; `record-fix`
counts a cycle after the fix step; `record-decision --recheck` records the
review after it. `check_step_drafts` lets the agent wrapper run the recorders'
draft contract right after a step, so a DraftError retries the step.

`record-intent` registers each human approval block it writes in the
operator's state directory (launcher.state_dir), which no agent can write. A
check of a human-gated run (`--run`) refuses a block it did not register.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
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
    from launcher import digests, input_bases, state_dir
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
APPROVAL_BLOCK = re.compile(
    re.escape(APPROVAL_START) + r".*?" + re.escape(APPROVAL_END), re.DOTALL
)
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
# An operator-only task (#112): a browser or device check, a demo capture.
DEFERRED_TAG = "[DEFERRED-TO-PR]"
DEFERRED_TEXT = 300  # Characters of a deferred task the record shows.
DEFERRED = re.compile(r"^(?:[ \t]+\[[^\]\n]{1,40}\])*?[ \t]+\[DEFERRED-TO-PR\]")
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


class DraftError(ContractError):
    """A refusal the agent can correct by rewriting its own draft (#21 R4).

    The agent wrapper reruns an Autonomous agent step on it, within
    DRAFT_RETRIES; every other ContractError stays terminal.
    """


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
        # The operator record of a Ballast-driven Chat run (#20); never `run`,
        # so check_intent requires the registered human approval block.
        self.chat: dict | None = None
        specs = (root / "specs").resolve()
        if (
            not specs.is_relative_to(root.resolve())
            or self.path.is_symlink()
            or (self.path.exists() and self.path.resolve().parent != specs)
        ):
            message = f"{relative} must be a real directory directly under specs/"
            raise ContractError(message)

    @classmethod
    def from_operator_run(cls, root: Path, record: dict) -> Feature:
        """Return the feature of a `ballast-chat` operator record (#20).

        Its human approvals, implementation baseline and decision resolutions
        come from operator state, never from agent-writable run state.
        """
        if record.get("workflow") != "ballast-chat":
            message = "only a ballast-chat record builds a Chat feature"
            raise ContractError(message)
        feature = cls(root, record["feature"], record["run_id"])
        feature.run_id = record["run_id"]
        feature.chat = record
        return feature

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
    """spec.md exists in the requested feature and is not the template.

    Once discovery ran for the feature, every acceptance criterion is also
    traced to its source and every Issue criterion is covered (#16).
    """
    text = feature.read("spec.md")
    _reject_sentinels(f"{feature.relative}/spec.md", text, SPEC_SENTINELS)
    _spec_traceability(feature, text)
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
    blocks = APPROVAL_BLOCK.findall(intent)
    if feature.run_id is not None and (
        len(blocks) != 1 or not _approval_path(feature, blocks[0]).is_file()
    ):
        # An agent step can write a matching block into intent.md, but not the
        # operator state that record-intent registers it in (#29).
        message = (
            f"{feature.relative}/intent.md has an approval block that record-intent "
            "did not register in this checkout; review the spec, run "
            f"`python3 .ballast/spec_workflow/artifacts.py record-intent --feature "
            f"{feature.relative}`, then resume the run"
        )
        raise ContractError(message)


def _approval_path(feature: Feature, block: str) -> Path:
    """Operator-state registration of one recorded human approval block."""
    key = hashlib.sha256(f"{feature.relative}\n{block}".encode()).hexdigest()
    return state_dir(feature.root) / "approvals" / key


def record_intent(feature: Feature) -> None:
    """Record human intent approval bound to the current spec digest.

    Run only after the approve-intent gate. Human-written intent sections are
    preserved; only the machine-managed approval block is replaced.
    """
    spec = check_clarified_spec(feature)
    source = (
        f"ballast run approve intent ({feature.key})"
        if feature.chat is not None
        else f"ballast-feature approve-intent gate ({feature.key})"
    )
    block = "\n".join(
        (
            APPROVAL_START,
            "- **Approved by**: human user",
            f"- **Approved**: {datetime.now(UTC).replace(microsecond=0).isoformat()}",
            f"- **Source**: {source}",
            f"- **Spec**: {feature.relative}/spec.md",
            f"- **Approved spec digest**: {spec_digest(spec)}",
            APPROVAL_END,
        )
    )
    if feature.continued is not None or feature.chat is not None:
        # A human-gated or Chat continuation of an Autonomous run: this
        # approval supersedes the agent-provisional intent, which stays in the
        # operator log and autonomous/record.md.
        path = feature.file("intent.md")
        if path.exists():
            text = path.read_text(encoding="utf-8")
            path.write_text(PROVISIONAL_BLOCK.sub("", text), encoding="utf-8")
    # Registered first: where operator state is unwritable, as in an agent
    # sandbox, nothing is recorded.
    registration = _approval_path(feature, block)
    registration.parent.mkdir(parents=True, exist_ok=True)
    registration.write_text(
        json.dumps({"feature": feature.relative, "spec_digest": spec_digest(spec)})
        + "\n",
        encoding="utf-8",
    )
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


def deferred_tasks(text: str) -> dict[str, tuple[bool, str, int]]:
    """{task_id: (done, description, line)} of tasks tagged [DEFERRED-TO-PR].

    The description includes the task's indented continuation lines, so the
    digest the tasks decision binds covers the whole task.
    """
    found = {}
    for match in TASK_LINE.finditer(text):
        mark, task_id, rest = match.groups()
        if DEFERRED.match(rest):
            line = text.count("\n", 0, match.start(2)) + 1
            parts = [rest.strip()]
            for following in text[match.end() :].split("\n")[1:]:
                if (
                    not following[:1].isspace()
                    or not following.strip()
                    or TASK_LINE.match(following)
                ):
                    break
                parts.append(following.strip())
            found[task_id] = (mark != " ", "\n".join(parts), line)
    return found


def task_digest(description: str) -> str:
    """SHA-256 of a task's text: what the tasks decision binds a deferral to."""
    return hashlib.sha256(description.encode()).hexdigest()


def recorded_deferrals(feature: Feature) -> set[tuple[str, str]]:
    """(task ID, text digest) pairs the current tasks decision deferred to the PR."""
    if (
        feature.run is None
        or autonomy is None
        or autonomy.effective_mode(feature.run) != "autonomous"
    ):
        return set()
    entries = autonomy.read_decisions(feature.root, feature.run["run_id"])
    return {
        (item["task"], item["sha256"])
        for entry in autonomy.current(entries, "tasks")
        for item in entry.get("deferred") or []
        if isinstance(item, dict)
        and isinstance(item.get("task"), str)
        and isinstance(item.get("sha256"), str)
    }


def _require_tasks_done(feature: Feature) -> str:
    """Every task done; in an Autonomous run, recorded deferrals may stay open (#112).

    A task tagged [DEFERRED-TO-PR] stays open only when the tasks decision
    recorded it, with the same text, before implementation: the record, the
    Draft PR and its packet list it, and its criterion keeps no evidence.
    """
    text, tasks = parse_tasks(feature)
    pending = [task_id for task_id, done in tasks.items() if not done]
    if pending and feature.run is not None:
        recorded = recorded_deferrals(feature)
        allowed = {
            task_id
            for task_id, (_, description, _) in deferred_tasks(text).items()
            if (task_id, task_digest(description)) in recorded
        }
        pending = [task_id for task_id in pending if task_id not in allowed]
    if pending:
        message = f"{feature.relative}/tasks.md has pending tasks: {', '.join(pending)}"
        late = sorted(set(pending) & set(deferred_tasks(text)))
        if feature.run is not None and late:
            message += (
                f"; {', '.join(late)} {'is' if len(late) == 1 else 'are'} tagged "
                f"{DEFERRED_TAG} but the tasks decision did not record "
                f"{'it' if len(late) == 1 else 'them'} with this text: a task is "
                "deferred to the PR only as written when tasks are accepted"
            )
        raise ContractError(message)
    return text


def _git(root: Path, *args: str, env: dict[str, str] | None = None) -> str:
    git = shutil.which("git")
    if git is None:
        message = "git is required"
        raise ContractError(message)
    # No filter driver runs, whatever .gitattributes an agent added.
    filters = autonomy.filter_overrides(root, env)
    result = subprocess.run(  # noqa: S603 - fixed executable, argument list
        [git, *filters, *args],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
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
        try:
            base = _git(root, "rev-parse", "-q", "--verify", "HEAD^{commit}")
        except ContractError:
            base = None
        try:
            autonomy.refuse_embedded(
                root, base, lambda *args: _git(root, *args, env=env)
            )
        except autonomy.AutonomyError as error:
            raise ContractError(str(error)) from error
        return _git(root, "write-tree", env=env)


def _state_file(feature: Feature, name: str) -> Path:
    directory = feature.root / STATE_DIR / feature.key
    directory.mkdir(parents=True, exist_ok=True)
    return directory / name


def record_baseline(feature: Feature) -> None:
    """Snapshot the working tree immediately before implementation.

    An Autonomous run keeps the baseline it already took (#21 R6): after a
    resume the reviews still cover every change since the first one.
    """
    check_tasks(feature)
    path = _state_file(feature, "implementation-baseline.json")
    if feature.run is not None and path.is_file() and not path.is_symlink():
        try:
            kept = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            kept = None
        if (
            isinstance(kept, dict)
            and kept.get("feature") == feature.relative
            and isinstance(kept.get("tree"), str)
            and TREE_ID.fullmatch(kept["tree"])
        ):
            return
    payload = {"feature": feature.relative, "tree": worktree_tree(feature.root)}
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def _baseline_tree(feature: Feature) -> str:
    """Return the implementation baseline tree: operator state for a Chat run (#20)."""
    if feature.chat is not None:
        baseline = feature.chat.get("baseline") or {}
        tree = baseline.get("tree")
        if not isinstance(tree, str) or not TREE_ID.fullmatch(tree):
            message = (
                "no implementation baseline recorded before implementation; "
                "approve tasks with ballast run approve"
            )
            raise ContractError(message)
        return tree
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
    return tree


def check_implementation(feature: Feature) -> None:
    """Require every task done and a repository change since the baseline."""
    check_plan(feature)
    tasks_text = _require_tasks_done(feature)
    tree = _baseline_tree(feature)
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
    if feature.run is not None:
        write_required_reviews(feature)


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
    elif feature.chat is not None:
        resolved = human_resolutions(feature, text)
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


def latest_resolutions(text: str) -> dict[str, str]:
    """{DEC id: body of its last Resolution section} of decisions.md text."""
    return {
        dec: body
        for dec, kind, body in decision_sections(text)
        if kind.lower() == "resolution"
    }


def resolution_digest(body: str) -> str:
    """Digest of a Resolution section's normalized text (#20 `resolve`)."""
    return spec_digest(body)


def human_resolutions(feature: Feature, text: str) -> set[str]:
    """DEC ids whose last Resolution matches a current human resolution (#20).

    Only `ballast run resolve` records a `decision-resolution` human decision
    in operator state, bound to the resolution text: a resolution an agent
    writes, or an edited one, resolves nothing.
    """
    if autonomy is None or feature.chat is None:
        return set()
    try:
        entries = autonomy.read_human_decisions(feature.root, feature.chat["run_id"])
        for entry in entries:
            autonomy.validate_human_decision(entry)
    except autonomy.AutonomyError as error:
        message = f"human decisions are unreadable: {error}"
        raise ContractError(message) from error
    digests: dict[str, set[str]] = {}
    for entry in entries:
        if entry["kind"] == "decision-resolution":
            digests.setdefault(entry["decision"], set()).add(entry["digest"])
    return {
        dec
        for dec, body in latest_resolutions(text).items()
        if resolution_digest(body) in digests.get(dec, set())
    }


def check_decision_structure(feature: Feature) -> None:
    """decisions.md is well formed; resolutions may still be pending (#20)."""
    check_intent(feature)
    path = feature.file("decisions.md")
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    if len(DECISION_RECORD.findall(text)) != len(DECISION_HEADING.findall(text)):
        message = f"{feature.relative}/decisions.md has malformed DEC headings"
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


# --- Discovery brief (#16) ------------------------------------------------
#
# `discover` writes <f>/discovery.md, non-authoritative input evidence for
# spec.md (contracts/discovery-brief.md). `discovery` validates it; in a
# human-gated run it asks every open decision in one failed validation and
# attributes the answers through operator state, which no agent can write.
# `check_spec` traces the spec to the brief once discovery ran.

DISCOVERY = "discovery.md"
DISCOVERY_MARKER = "<!-- ballast-discovery: input evidence -->"
# Provenance markers (research R-04); [B: ...] cites a brief item from spec.md.
PROVENANCE = re.compile(r"\[(?:S: [^\]\n]+|I|O: D-\d{2}|P: D-\d{2}|B: [^\]\n]+)\]")
DISCOVERY_SECTIONS = (
    "Sources",
    "Need",
    "Examples",
    "Scope",
    "Non-goals",
    "Constraints",
    "Permissions and data authority",
    "Success evidence",
    "Issue acceptance criteria",
    "Edge, failure and permission cases",
    "Known",
    "Inferred",
    "Undecided",
    "Decisions",
    "Question metrics",
)
# Sections whose every list item carries a provenance marker. `## Changes`
# is the brief's own dated history, not requirements, so it needs none (#95).
MARKED_SECTIONS = (
    "Need",
    "Examples",
    "Scope",
    "Non-goals",
    "Constraints",
    "Permissions and data authority",
    "Success evidence",
    "Edge, failure and permission cases",
    "Known",
    "Inferred",
)
MARKER_KINDS = {"Known": ("S", "O"), "Inferred": ("I", "P")}
BRIEF_KINDS = ("S", "I", "O", "P")
# The decision status and the run mode an [O:] or [P:] marker requires.
MARKER_DECISION = {"O": ("answered", "human-gated"), "P": ("assumed", "autonomous")}
MIN_OPTIONS = 2
NEED_ITEMS = ("User", "Job to be done", "Current pain", "Intended outcome")
DECISION_STATUSES = ("settled", "open", "answered", "assumed", "blocking")
DECISION_FIELDS = {
    "Status": "status",
    "Question": "question",
    "Why it matters": "why",
    "Sources": "sources",
    "Options": "options",
    "Recommended default": "default",
    "Answer": "answer",
    "Resolution": "resolution",
}
DECISION_REQUIRED = ("Status", "Question", "Why it matters", "Sources")
METRICS = ("Rounds", "Questions asked", "Assumptions adopted")
SECTION = re.compile(r"^## +(\S.*?)\s*$")
LIST_ITEM = re.compile(r"^(?:[-*]|\d+\.)\s+(.*)$")
LABEL = re.compile(r"^\*\*([^*\n]+)\*\*:\s*(.*)$")
BRIEF_DECISION = re.compile(r"^###\s+(D-\d{2}):\s*(\S.*)$")
DECISION_ID = re.compile(r"\bD-\d{2}\b")
IAC_ITEM = re.compile(r"^(IAC-[1-9]\d*):\s*(\S.*)$")
IAC_TOKEN = re.compile(r"\bIAC-[1-9]\d*\b")
MODE_LINE = re.compile(r"^\*\*Mode\*\*:[ \t]*(.*?)[ \t]*$", re.MULTILINE)
CONSEQUENCE = re.compile(r"(?i)\bconsequence:\s*\S")
SOURCE_ENTRY = re.compile(r"^S-\d+:\s*(.*)$")
SOURCE_CITE = re.compile(r"\[S: ([^\]\n]+)\]")
PATH_TOKEN = re.compile(r"[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*/?")
# A file name: `AGENTS.md`, `artifacts.py`; not `e.g.` or `2.0`.
FILE_NAME = re.compile(r"[^./]+\.[A-Za-z][A-Za-z0-9]{0,7}")
DISCOVERY_ASSUMPTION = re.compile(r"(D-\d{2}):")
ANSWER_LINE = re.compile(r"^- \*\*Answer\*\*:.*$", re.MULTILINE)
HEADING_LINE = re.compile(r"^(#{1,6})\s+(.*)$")
CRITERIA_HEADING = re.compile(r"(?i)^#{1,6}\s+.*\bacceptance criteria\b")
CHECKBOX = re.compile(r"^\[[ xX]\]\s+")
AC_ID = re.compile(r"\*\*(AC-\d{3})\*\*")
SCENARIOS_LABEL = re.compile(r"(?i)^(?:#{1,6}\s+|\*\*)acceptance scenarios\b")
NON_GOALS = re.compile(r"(?i)\bnon-goals?\b|\bout of scope\b")


def _brief_error(feature: Feature, detail: str) -> ContractError:
    return ContractError(f"{feature.relative}/{DISCOVERY}: {detail}")


def _short(text: str, limit: int = 80) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 3] + "..."


def _markers(text: str) -> list[str]:
    """Provenance markers in text, in order; a Markdown link is none."""
    return PROVENANCE.findall(text)


def _marker_kind(marker: str) -> str:
    return marker[1]


def _list_items(body: str) -> list[str]:
    """Top-level list items of a body; indented lines continue the item."""
    items: list[str] = []
    open_item = False
    for line in body.splitlines():
        match = LIST_ITEM.match(line)
        if match:
            items.append(match.group(1).strip())
            open_item = True
        elif open_item and line[:1] in {" ", "\t"} and line.strip():
            items[-1] += " " + line.strip()
        elif line.strip():
            open_item = False
    return items


def _decision_line(ident: str, line: str) -> tuple[str, str]:
    """(field, value) of a decision's `- **Field**: value` line."""
    item = LIST_ITEM.match(line)
    label = LABEL.match(item.group(1)) if item else None
    if label is None or label.group(1) not in DECISION_FIELDS:
        message = f"decision {ident} has an unknown line {_short(line)!r}"
        raise ContractError(message)
    return DECISION_FIELDS[label.group(1)], label.group(2).strip()


def _continue_decision(found: dict, field: str | None, text: str) -> None:
    """Fold an indented line into the field above it; options are sub-items."""
    if field == "options":
        option = LIST_ITEM.match(text)
        if option:
            found["options"].append(option.group(1).strip())
        elif found["options"]:
            found["options"][-1] += " " + text
    elif field is not None:
        found[field] = f"{found[field]} {text}".strip()


def _parse_decision(ident: str, title: str, body: str) -> dict:
    """Parse one `### D-NN: <title>` block; a malformed block raises."""
    found: dict = {"id": ident, "title": title, "options": []}
    found |= {"default": "", "answer": "", "resolution": ""}
    seen: set[str] = set()
    field = None
    for line in body.splitlines():
        if not line.strip():
            continue
        if line[0] in {" ", "\t"}:
            _continue_decision(found, field, line.strip())
            continue
        field, value = _decision_line(ident, line)
        if field in seen:
            message = f"decision {ident} repeats its {field} line"
            raise ContractError(message)
        seen.add(field)
        if field != "options":
            found[field] = value
    missing = [name for name in DECISION_REQUIRED if DECISION_FIELDS[name] not in seen]
    if missing:
        message = f"decision {ident} lacks **{'**, **'.join(missing)}**"
        raise ContractError(message)
    found["status"] = found["status"].lower()
    if found["status"] not in DECISION_STATUSES:
        message = (
            f"decision {ident} has status {found['status']!r}; use one of "
            + ", ".join(DECISION_STATUSES)
        )
        raise ContractError(message)
    return found


def _split_sections(text: str) -> tuple[str, dict[str, str]]:
    """Split off the text before the first `## ` heading and each section's body."""
    preamble: list[str] = []
    sections: dict[str, list[str]] = {}
    current = preamble
    for line in text.splitlines():
        match = SECTION.match(line)
        if match is None:
            current.append(line)
        elif match.group(1) in sections:
            message = f"section {'## ' + match.group(1)!r} appears twice"
            raise ContractError(message)
        else:
            current = sections[match.group(1)] = []
    bodies = {name: "\n".join(lines).strip() for name, lines in sections.items()}
    return "\n".join(preamble), bodies


def _parse_decisions(body: str) -> dict[str, dict]:
    """Each `### D-NN: <title>` block of the `## Decisions` section."""
    decisions: dict[str, dict] = {}
    for block in re.split(r"(?m)^(?=###\s)", body):
        if not block.startswith("###"):
            continue
        heading, _, rest = block.partition("\n")
        match = BRIEF_DECISION.match(heading.strip())
        if match is None:
            message = f"decision heading {_short(heading)!r} is not '### D-NN: title'"
            raise ContractError(message)
        if match.group(1) in decisions:
            message = f"decision {match.group(1)} appears twice"
            raise ContractError(message)
        decisions[match.group(1)] = _parse_decision(*match.groups(), rest)
    return decisions


def _parse_discovery(text: str) -> dict:
    """Parse a brief's sections, list items, decisions and Issue criteria."""
    preamble, sections = _split_sections(text)
    iacs = []
    for item in _list_items(sections.get("Issue acceptance criteria", "")):
        match = IAC_ITEM.match(item)
        iacs.append((match.group(1), match.group(2).strip()) if match else ("", item))
    mode = MODE_LINE.search(preamble)
    return {
        "preamble": preamble,
        "mode": mode.group(1) if mode else None,
        "sections": sections,
        "items": {name: _list_items(body) for name, body in sections.items()},
        "decisions": _parse_decisions(sections.get("Decisions", "")),
        "iacs": iacs,
    }


def _cited_paths(value: str) -> list[str]:
    """Repository paths a citation names, as `path`, `path#part` or `path:12`."""
    paths = []
    for part in re.split(r"[;,]", value):
        words = part.split()
        if not words or "://" in part:
            continue
        token = re.split(r"[#:]", words[0].strip("`'\"()"), maxsplit=1)[0]
        if PATH_TOKEN.fullmatch(token) and (
            token.endswith("/") or FILE_NAME.fullmatch(token.rpartition("/")[2])
        ):
            paths.append(token.rstrip("/"))
    return paths


def _check_cited(feature: Feature, where: str, value: str) -> None:
    """Every repository path a citation names exists (AC-002)."""
    for path in _cited_paths(value):
        try:
            _repo_path(feature, path, "cited source")
        except ContractError as error:
            detail = f"{where}: {error}"
            raise _brief_error(feature, detail) from error


def _issue_criteria(feature: Feature) -> list[str] | None:
    """Return the Issue's acceptance criteria from the runner's snapshot (R-05).

    None when the snapshot is missing or its body has no acceptance-criteria
    heading; the brief's own IAC list is then what the spec must cover.
    """
    number = feature.relative.split("/")[1].split("-")[0]
    path = feature.root / STATE_DIR / "issues" / f"{number}.md"
    if path.is_symlink() or not path.is_file():
        return None
    lines = path.read_text(encoding="utf-8").splitlines()
    if "## Body" not in lines:
        return None
    start = lines.index("## Body") + 1
    # Comments follow the scope comment: a heading there is not the Issue's.
    scope = "## Intake scope comment"
    end = lines.index(scope, start) if scope in lines[start:] else len(lines)
    heading = next(
        (i for i in range(start, end) if CRITERIA_HEADING.match(lines[i])), None
    )
    if heading is None:
        return None
    region = []
    for line in lines[heading + 1 : end]:
        if HEADING_LINE.match(line):
            break
        region.append(line)
    return [
        " ".join(CHECKBOX.sub("", item).split())
        for item in _list_items("\n".join(region))
    ]


def _check_marked_items(feature: Feature, items: dict[str, list[str]]) -> None:
    """Each item of a marked section carries provenance of the allowed kinds."""
    for name in MARKED_SECTIONS:
        allowed = MARKER_KINDS.get(name, BRIEF_KINDS)
        for item in items.get(name, []):
            where = f"section '## {name}' item {_short(item)!r}"
            found = _markers(item)
            if not found:
                detail = f"{where} has no provenance marker ([S: ...] or [I])"
                raise _brief_error(feature, detail)
            if not {_marker_kind(marker) for marker in found} <= set(allowed):
                detail = f"{where} may carry only {', '.join(allowed)} markers"
                raise _brief_error(feature, detail)
            for marker in found:
                if _marker_kind(marker) == "S":
                    _check_cited(feature, where, marker[4:-1])


def _check_decision_markers(
    feature: Feature, text: str, decisions: dict, mode: str
) -> None:
    """[O: D-NN] names an answered decision, [P: D-NN] an assumed one."""
    for marker in _markers(text):
        kind = _marker_kind(marker)
        if kind not in MARKER_DECISION:
            continue
        ident, (status, wanted_mode) = marker[4:-1], MARKER_DECISION[kind]
        if mode != wanted_mode:
            detail = f"{marker} belongs only in {wanted_mode} briefs"
            raise _brief_error(feature, detail)
        if decisions.get(ident, {}).get("status") != status:
            detail = f"{marker} refers to {ident}, which is not {status}"
            raise _brief_error(feature, detail)


def _check_decision_status(feature: Feature, item: dict, mode: str) -> None:
    """Check a status the mode allows: an autonomous run never asks, nobody blocks."""
    where, status = f"decision {item['id']}", item["status"]
    if status == "blocking":
        detail = f"{where} is blocking: write the block draft and stop the run"
    elif status == "assumed" and mode != "autonomous":
        detail = f"{where} is assumed; only an autonomous run assumes a default"
    elif status in {"open", "answered"} and mode == "autonomous":
        detail = f"{where} is {status}; an autonomous run assumes a default or blocks"
    elif status == "answered" and not item["answer"]:
        detail = f"{where} is answered but its **Answer** is empty"
    elif item["answer"] and status != "answered":
        detail = (
            f"{where} has an **Answer** but status {status}; only an answered "
            "decision has one (set **Status** to answered)"
        )
    else:
        return
    raise _brief_error(feature, detail)


def _check_decision_fields(feature: Feature, item: dict) -> None:
    """Check cited sources, and options and a default unless settled."""
    where = f"decision {item['id']}"
    for field in ("question", "why", "sources"):
        if not item[field]:
            detail = f"{where} has an empty {field}"
            raise _brief_error(feature, detail)
    _check_cited(feature, where, " ; ".join(SOURCE_CITE.findall(item["sources"])))
    cited = SOURCE_CITE.findall(item["resolution"])
    if item["status"] == "settled":
        if not cited:
            detail = (
                f"{where} is settled, so its **Resolution** must cite the source "
                "that settles it as [S: ...]"
            )
            raise _brief_error(feature, detail)
        _check_cited(feature, where, " ; ".join(cited))
        return
    options = item["options"]
    if len(options) < MIN_OPTIONS or not all(CONSEQUENCE.search(o) for o in options):
        detail = f"{where} needs two **Options** or more, each with a Consequence"
        raise _brief_error(feature, detail)
    if not item["default"]:
        detail = f"{where} has no **Recommended default**"
        raise _brief_error(feature, detail)
    if item["status"] == "assumed" and not item["resolution"]:
        detail = f"{where} is assumed; its **Resolution** says why it is safe"
        raise _brief_error(feature, detail)


def _check_undecided(feature: Feature, items: list[str], decisions: dict) -> None:
    """Every `## Undecided` item names decisions of `## Decisions`."""
    for item in items:
        named = DECISION_ID.findall(item)
        unknown = [ident for ident in named if ident not in decisions]
        if not named or unknown:
            detail = (
                f"'## Undecided' item {_short(item)!r} must name decisions of "
                f"'## Decisions' (unknown: {', '.join(unknown) or 'none named'})"
            )
            raise _brief_error(feature, detail)


def _brief_metrics(feature: Feature, items: list[str]) -> dict[str, int]:
    """Parse the integer counts of `## Question metrics`."""
    values: dict[str, str] = {}
    for item in items:
        label = LABEL.match(item)
        if label and label.group(1) in METRICS:
            values[label.group(1)] = label.group(2).strip()
    for name in METRICS:
        if not values.get(name, "").isdigit():
            detail = f"'## Question metrics' needs an integer **{name}**"
            raise _brief_error(feature, detail)
    return {name: int(values[name]) for name in METRICS}


def _check_brief_header(
    feature: Feature, text: str, brief: dict, run_mode: str | None
) -> str:
    """Evidence marker, authority note and mode; return the brief's mode."""
    if text.partition("\n")[0].strip() != DISCOVERY_MARKER:
        detail = f"the first line must be {DISCOVERY_MARKER}"
        raise _brief_error(feature, detail)
    for name in ("spec.md", "intent.md"):
        if f"]({name})" not in brief["preamble"]:
            detail = (
                f"the authority note before the first section must link {name}: "
                "the brief is input evidence, spec.md and intent.md govern"
            )
            raise _brief_error(feature, detail)
    mode = brief["mode"]
    if mode not in autonomy.MODES:
        detail = "state **Mode**: human-gated or **Mode**: autonomous"
        raise _brief_error(feature, detail)
    if run_mode is not None and mode != run_mode:
        detail = f"**Mode** is {mode}, but this run is {run_mode}"
        raise _brief_error(feature, detail)
    return mode


def _check_brief_sections(feature: Feature, brief: dict) -> None:
    """Every section filled, the need spelled out, cited sources present."""
    for name in DISCOVERY_SECTIONS:
        if not brief["sections"].get(name):
            detail = f"section '## {name}' is missing or empty"
            raise _brief_error(feature, detail)
    need = brief["items"]["Need"]
    for label in NEED_ITEMS:
        if not any(item.startswith(f"**{label}**:") for item in need):
            detail = f"section '## Need' lacks the **{label}** item"
            raise _brief_error(feature, detail)
    if not brief["items"]["Examples"]:
        detail = "section '## Examples' needs one example or more"
        raise _brief_error(feature, detail)
    for item in brief["items"]["Sources"]:
        if not item.lower().startswith("unavailable:"):
            entry = SOURCE_ENTRY.match(item)
            _check_cited(feature, "'## Sources'", entry.group(1) if entry else item)


def _check_brief_iacs(feature: Feature, iacs: list[tuple[str, str]]) -> None:
    """IAC-n items, verbatim from the Issue snapshot when it lists criteria."""
    listed = [ident for ident, _ in iacs]
    if "" in listed or len(set(listed)) != len(listed):
        detail = "'## Issue acceptance criteria' needs unique 'IAC-n: <text>' items"
        raise _brief_error(feature, detail)
    criteria = _issue_criteria(feature)
    mine = [" ".join(text.split()) for _, text in iacs]
    if criteria is not None and mine != criteria:
        missing = [c for c in criteria if c not in mine]
        extra = [c for c in mine if c not in criteria]
        # Quoted: the retry note drops Issue and agent text (#95).
        detail = (
            "'## Issue acceptance criteria' must list the Issue's criteria verbatim "
            f"and in order (missing: {', '.join(map(repr, missing)) or 'none'}; "
            f"not in the Issue: {', '.join(map(repr, extra)) or 'none'})"
        )
        raise _brief_error(feature, detail)


def _check_brief(
    feature: Feature, text: str, brief: dict, run_mode: str | None
) -> None:
    """Structure, provenance and coverage of a brief (data-model.md)."""
    mode = _check_brief_header(feature, text, brief, run_mode)
    _check_brief_sections(feature, brief)
    _check_marked_items(feature, brief["items"])
    sections = "\n".join(brief["sections"].values())
    _check_decision_markers(feature, sections, brief["decisions"], mode)
    for item in brief["decisions"].values():
        _check_decision_status(feature, item, mode)
        _check_decision_fields(feature, item)
    _check_undecided(feature, brief["items"]["Undecided"], brief["decisions"])
    _check_brief_iacs(feature, brief["iacs"])
    # Only the operator's own answer may use approval wording (FR-010).
    checked = ANSWER_LINE.sub("", text) if mode == "human-gated" else text
    if autonomy.HUMAN_APPROVAL.search(checked):
        detail = (
            "claims a human approval; an agent's choice is an inference or "
            "agent-provisional, and only an operator **Answer** may say otherwise"
        )
        raise _brief_error(feature, detail)
    _brief_metrics(feature, brief["items"]["Question metrics"])


def _discovery_state_path(feature: Feature) -> Path:
    """Operator state of the feature's discovery, outside every checkout."""
    key = hashlib.sha256(feature.relative.encode()).hexdigest()
    try:
        base = state_dir(feature.root)
    except OSError as error:
        raise ContractError(str(error)) from error
    return base / "discovery" / f"{key}.json"


def _valid_discovery_state(data: object, feature: str) -> bool:
    if not isinstance(data, dict) or data.get("feature") != feature:
        return False
    rounds, answered = data.get("rounds"), data.get("answered")
    return (
        isinstance(data.get("ran"), bool)
        and isinstance(rounds, list)
        and all(
            isinstance(r, dict)
            and isinstance(r.get("asked"), list)
            and all(isinstance(i, str) for i in r["asked"])
            and isinstance(r.get("questions_digest"), str)
            for r in rounds
        )
        and isinstance(answered, dict)
        and all(isinstance(v, str) for v in answered.values())
    )


def _load_discovery_state(feature: Feature) -> dict:
    """Operator record of question rounds, accepted answers and `ran`."""
    path = _discovery_state_path(feature)
    if not os.path.lexists(path):
        return {"feature": feature.relative, "rounds": [], "answered": {}, "ran": False}
    message = f"operator discovery state {path} is malformed"
    if path.is_symlink() or not path.is_file():
        raise ContractError(message)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ContractError(message) from error
    if not _valid_discovery_state(data, feature.relative):
        raise ContractError(message)
    return data


def _save_discovery_state(feature: Feature, state: dict) -> None:
    """Write operator state by rename, never through a symlink."""
    path = _discovery_state_path(feature)
    path.parent.mkdir(parents=True, exist_ok=True)
    staged = path.with_name(path.name + ".tmp")
    staged.unlink(missing_ok=True)
    text = json.dumps(state, indent=2, sort_keys=True) + "\n"
    staged.write_text(text, encoding="utf-8")
    staged.replace(path)


def _discovery_ran(feature: Feature) -> bool:
    """Tell whether a brief exists or operator state says discovery validated (R-06)."""
    if feature.file(DISCOVERY).exists():
        return True
    try:
        return _load_discovery_state(feature)["ran"]
    except ContractError:
        if feature.run_id is not None:
            raise
        return False


def _text_digest(*parts: object) -> str:
    data = json.dumps(parts, ensure_ascii=False, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(data.encode()).hexdigest()


def _questions_digest(decisions: dict, asked: list[str]) -> str:
    """Digest of what a round asked: each question, reason, option and default."""
    fields = ("id", "question", "why", "options", "default")
    return _text_digest(*([decisions[i][f] for f in fields] for i in asked))


def _question_message(
    feature: Feature, decisions: dict, pending: list[str], number: int
) -> str:
    """Render the one bundled question round, with how to answer and resume (AC-006)."""
    lines = [
        (
            f"discovery needs your answers (question round {number}); the "
            "repository and the Issue do not settle these decisions:"
        ),
    ]
    for ident in pending:
        item = decisions[ident]
        lines += [
            "",
            f"{ident}: {item['question']}",
            f"  Why it matters: {item['why']}",
            "  Options:",
            *(f"    - {option}" for option in item["options"]),
            f"  Recommended default: {item['default']}",
        ]
    lines += [
        "",
        (
            f"For each decision above, edit {feature.relative}/{DISCOVERY}: set "
            "**Status** to answered and write your choice on its **Answer** line "
            "(the recommended default is fine). Leave the questions unchanged, "
            f"then run `ballast run resume {feature.run_id}`."
        ),
    ]
    return "\n".join(lines)


def _write_metrics(feature: Feature, text: str, values: tuple[int, ...]) -> None:
    """Rewrite only the `## Question metrics` section (FR-015)."""
    lines = text.split("\n")
    heads = {i: SECTION.match(line) for i, line in enumerate(lines)}
    starts = [i for i, match in heads.items() if match]
    start = next(i for i in starts if heads[i].group(1) == "Question metrics")
    end = next((i for i in starts if i > start), len(lines))
    pairs = zip(METRICS, values, strict=True)
    # Keeps the blank line before the next section, or the final newline.
    body = ["", *(f"- **{name}**: {value}" for name, value in pairs), ""]
    updated = "\n".join([*lines[: start + 1], *body, *lines[end:]])
    if updated != text:
        path = feature.file(DISCOVERY)
        staged = path.with_name(path.name + ".tmp")
        staged.unlink(missing_ok=True)
        staged.write_text(updated, encoding="utf-8")
        staged.replace(path)


def _asked(feature: Feature, state: dict, decisions: dict) -> set[str]:
    """Decisions of the recorded rounds, whose questions must be unchanged."""
    asked: set[str] = set()
    for number, round_ in enumerate(state["rounds"], 1):
        ids = round_["asked"]
        if any(i not in decisions for i in ids) or (
            _questions_digest(decisions, ids) != round_["questions_digest"]
        ):
            detail = (
                f"the questions asked in round {number} ({', '.join(ids)}) changed "
                "or were removed after they were asked; restore them as asked"
            )
            raise _brief_error(feature, detail)
        asked.update(ids)
    return asked


def _check_answers(
    feature: Feature, state: dict, decisions: dict, asked: set[str]
) -> None:
    """Accept answers only to asked questions; an accepted one never changes."""
    for ident, item in decisions.items():
        accepted = state["answered"].get(ident)
        if item["status"] == "answered" and ident not in asked:
            detail = (
                f"{ident} has an answer to a question that was not asked; only "
                "the operator answers, after validate-discovery asks"
            )
        elif accepted is not None and (
            item["status"] != "answered" or _text_digest(item["answer"]) != accepted
        ):
            detail = f"the accepted answer to {ident} changed after it was accepted"
        else:
            continue
        raise _brief_error(feature, detail)


def _check_gated_discovery(feature: Feature, text: str, brief: dict) -> None:
    """Ask every open decision once; accept only answers to asked questions.

    The round is recorded in operator state before the validation fails, so
    an answer an agent wrote before it was asked is never the operator's.
    """
    state = _load_discovery_state(feature)
    decisions = brief["decisions"]
    asked = _asked(feature, state, decisions)
    _check_answers(feature, state, decisions, asked)
    pending = [i for i, item in decisions.items() if item["status"] == "open"]
    new = [i for i in pending if i not in asked]
    if new:
        at = datetime.now(UTC).replace(microsecond=0).isoformat()
        digest = _questions_digest(decisions, new)
        state["rounds"].append({"asked": new, "questions_digest": digest, "at": at})
        _save_discovery_state(feature, state)
    if pending:
        number = len(state["rounds"])
        raise ContractError(_question_message(feature, decisions, pending, number))
    given = {i: d["answer"] for i, d in decisions.items() if d["status"] == "answered"}
    state["answered"].update({i: _text_digest(a) for i, a in given.items()})
    state["ran"] = True
    _save_discovery_state(feature, state)
    questions = sum(len(round_["asked"]) for round_ in state["rounds"])
    _write_metrics(feature, text, (len(state["rounds"]), questions, 0))


def _changed_paths(feature: Feature) -> list[str]:
    """Paths `git status` reports as changed, both sides of a rename."""
    status = autonomy.git(
        feature.root, "status", "--porcelain", "-z", "--untracked-files=all"
    ).stdout
    entries = status.split("\0")
    paths = []
    index = 0
    while index < len(entries):
        entry = entries[index]
        index += 1
        if len(entry) < 4:  # noqa: PLR2004 - "XY path"
            continue
        paths.append(entry[3:])
        if entry[0] in {"R", "C"} and index < len(entries):
            paths.append(entries[index])
            index += 1
    return paths


def _recorded_assumptions(feature: Feature) -> list[str]:
    """D-NN of each current clarification decision recorded from discovery."""
    run = _require_run(feature)
    entries = autonomy.current(
        autonomy.read_decisions(feature.root, run["run_id"]), "clarification"
    )
    questions = [(e.get("assumption") or {}).get("question", "") for e in entries]
    return [m.group(1) for q in questions if (m := DISCOVERY_ASSUMPTION.match(q))]


def _check_autonomous_discovery(feature: Feature, brief: dict) -> None:
    """Assumptions match the recorded decisions; nothing changed outside <f>."""
    recorded = _recorded_assumptions(feature)
    decisions = brief["decisions"]
    assumed = {i for i, d in decisions.items() if d["status"] == "assumed"}
    unmatched = sorted(assumed ^ set(recorded))
    if unmatched or len(set(recorded)) != len(recorded):
        detail = (
            "each assumed decision needs exactly one clarification-discovery-<n> "
            "draft whose assumption question starts with its 'D-NN:'; mismatched: "
            + (", ".join(unmatched) or "a decision recorded twice")
        )
        raise _brief_error(feature, detail)
    values = _brief_metrics(feature, brief["items"]["Question metrics"])
    for name, value in zip(METRICS, (0, 0, len(recorded)), strict=True):
        if values[name] != value:
            detail = (
                f"'## Question metrics' **{name}** is {values[name]}, but the run "
                f"recorded {value}"
            )
            raise _brief_error(feature, detail)
    prefix = feature.relative + "/"
    outside = sorted(p for p in _changed_paths(feature) if not p.startswith(prefix))
    if outside:
        listed = ", ".join(outside[:10])
        message = f"the discover step changed files outside {prefix}: {listed}"
        raise ContractError(message)
    state = _load_discovery_state(feature)
    state["ran"] = True
    _save_discovery_state(feature, state)


def check_discovery(feature: Feature) -> None:
    """Validate the discovery brief; in a run, attribute and count questions."""
    text = feature.read(DISCOVERY)
    try:
        brief = _parse_discovery(text)
    except ContractError as error:
        raise _brief_error(feature, str(error)) from error
    run_mode = None
    if feature.run is not None:
        run_mode = "autonomous"
    elif feature.run_id is not None:
        run_mode = "human-gated"
    _check_brief(feature, text, brief, run_mode)
    if run_mode == "autonomous":
        _check_autonomous_discovery(feature, brief)
    elif run_mode == "human-gated":
        _check_gated_discovery(feature, text, brief)


def _spec_items(spec: str) -> list[tuple[str, bool, str | None]]:
    """Each list item: (text, is an acceptance scenario, non-goal heading)."""
    items: list[tuple[str, bool, str | None]] = []
    scenarios = False
    non_goal: tuple[int, str] | None = None
    open_item = False
    for line in spec.splitlines():
        heading = HEADING_LINE.match(line)
        if heading:
            level = len(heading.group(1))
            if non_goal and level <= non_goal[0]:
                non_goal = None
            if NON_GOALS.search(heading.group(2)):
                non_goal = (level, heading.group(2))
        if heading or line.strip() == "---":
            scenarios = bool(heading and SCENARIOS_LABEL.match(line))
            open_item = False
            continue
        if SCENARIOS_LABEL.match(line):
            scenarios, open_item = True, False
            continue
        match = LIST_ITEM.match(line)
        if match:
            items.append((match.group(1).strip(), scenarios, non_goal and non_goal[1]))
            open_item = True
        elif open_item and line[:1] in {" ", "\t"} and line.strip():
            text, inside, goal = items[-1]
            items[-1] = (f"{text} {line.strip()}", inside, goal)
        elif line.strip():
            open_item = False
            scenarios = False
    return items


def _spec_brief(feature: Feature) -> dict | None:
    """Return the brief a spec traces to, or None when discovery never ran (R-06)."""
    if not _discovery_ran(feature):
        return None
    path = feature.file(DISCOVERY)
    if not path.exists():
        message = (
            f"discovery ran for {feature.relative}, but {feature.relative}/"
            f"{DISCOVERY} is missing; restore the brief"
        )
        raise ContractError(message)
    try:
        return _parse_discovery(path.read_text(encoding="utf-8"))
    except ContractError as error:
        raise _brief_error(feature, str(error)) from error


def _check_spec_criteria(where: str, items: list[tuple[str, bool, str | None]]) -> None:
    """Every scenario has an AC-NNN ID and every criterion a provenance marker."""
    for item, scenario, _ in items:
        found = AC_ID.search(item)
        if scenario and found is None:
            message = (
                f"{where}: acceptance scenario {_short(item)!r} has no **AC-NNN** "
                "ID; once discovery ran, every scenario is numbered and traced"
            )
            raise ContractError(message)
        if found and not _markers(item):
            message = (
                f"{where}: acceptance criterion {found.group(1)} has no provenance "
                "marker ([S: ...], [B: ...], [I], [O: D-NN] or [P: D-NN])"
            )
            raise ContractError(message)
    if not any(AC_ID.search(item) for item, _, _ in items):
        message = f"{where} has no acceptance scenario with an **AC-NNN** ID"
        raise ContractError(message)


def _check_spec_decisions(
    feature: Feature, where: str, spec: str, decisions: dict
) -> None:
    """[O: D-NN] and [P: D-NN] name answered and assumed brief decisions."""
    answered = None
    if feature.run is None and feature.run_id is not None:
        answered = _load_discovery_state(feature)["answered"]
    for marker in _markers(spec):
        kind = _marker_kind(marker)
        if kind not in MARKER_DECISION:
            continue
        ident, status = marker[4:-1], MARKER_DECISION[kind][0]
        if decisions.get(ident, {}).get("status") != status or (
            kind == "O" and answered is not None and ident not in answered
        ):
            message = f"{where}: {marker} refers to {ident}, which is not {status}"
            raise ContractError(message)


def _check_spec_coverage(
    where: str, items: list[tuple[str, bool, str | None]], iacs: list
) -> None:
    """Each IAC-n is cited by an acceptance criterion or listed as a non-goal."""
    covered: set[str] = set()
    for item, _, goal in items:
        if goal:
            covered.update(IAC_TOKEN.findall(item))
        elif AC_ID.search(item):
            covered.update(IAC_TOKEN.findall(" ".join(_markers(item))))
    for ident, text in iacs:
        if ident not in covered:
            message = (
                f"{where}: Issue acceptance criterion {ident} ({_short(text)}) is "
                "neither cited by an acceptance criterion's marker nor listed under "
                "a Non-goals heading"
            )
            raise ContractError(message)


def _spec_traceability(feature: Feature, spec: str) -> None:
    """Trace spec.md to the brief once discovery ran (FR-011, FR-012)."""
    brief = _spec_brief(feature)
    if brief is None:
        return
    where = f"{feature.relative}/spec.md"
    items = _spec_items(spec)
    _check_spec_criteria(where, items)
    _check_spec_decisions(feature, where, spec, brief["decisions"])
    _check_spec_coverage(where, items, brief["iacs"])


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
    rf"{SEVERITY}\b|^\s*(?:[-*]\s+)?\(?{SEVERITY}\)?\s*[:\u2014\u2013-]\s)"
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
RUNNER_FIELDS = ("id", "prev", "at", "provider", "step_id", "role", "agent", "deferred")
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
    message = f"{category} block: {condition}"
    raise BlockedError(message)


def _rendered(feature: Feature) -> str:
    return autonomy.render_run_record(feature.root, _require_run(feature))


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
    """Return a repository-relative path that exists, inside the checkout, no links."""
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 300  # noqa: PLR2004
        or value.startswith("/")
        or "\\" in value
    ):
        message = f"{name} must be a repository-relative path"
        raise DraftError(message)
    parts = Path(value).parts
    if ".." in parts or "." in parts or value != Path(value).as_posix():
        message = f"{name} {value!r} must not contain '..'"
        raise DraftError(message)
    current = feature.root
    for part in parts:
        current = current / part
        if current.is_symlink():
            message = f"{name} {value!r} goes through a symlink"
            raise DraftError(message)
    if not current.exists():
        message = f"{name} {value!r} does not exist"
        raise DraftError(message)
    return value


def _evidence(feature: Feature, value: object) -> list[str]:
    if not isinstance(value, list) or not 1 <= len(value) <= 20:  # noqa: PLR2004
        message = "evidence must list 1-20 paths or https:// links"
        raise DraftError(message)
    out = []
    for item in value:
        if isinstance(item, str) and item.startswith("https://"):
            if len(item) > 500 or re.search(r"\s", item):  # noqa: PLR2004
                message = f"evidence link {item[:60]!r} is invalid"
                raise DraftError(message)
            out.append(item)
        else:
            out.append(_repo_path(feature, item, "evidence"))
    return out


def _text_field(value: object, name: str, limit: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        message = f"{name} must be 1-{limit} characters"
        raise DraftError(message)
    if autonomy.HUMAN_APPROVAL.search(value):
        message = f"{name} claims a human approval; agent decisions are provisional"
        raise DraftError(message)
    if autonomy.WORKFLOW_MARKER.search(value):
        message = f"{name} contains a workflow marker"
        raise DraftError(message)
    return autonomy.printable(value)


def _string_list(value: object, name: str, limit: int = 20) -> list[str]:
    if not isinstance(value, list) or len(value) > limit:
        message = f"{name} must be a list of at most {limit} strings"
        raise DraftError(message)
    if not all(isinstance(v, str) and 0 < len(v.strip()) <= 100 for v in value):  # noqa: PLR2004
        message = f"{name} must contain short strings"
        raise DraftError(message)
    return sorted({" ".join(v.lower().split()) for v in value})


def _privileged_list(value: object, name: str) -> list[str]:
    """`KIND` or `KIND: description` entries, each kind from the vocabulary (#95)."""
    actions = _string_list(value, name)
    unknown = sorted(
        {a for a in actions if autonomy.action_kind(a) not in autonomy.ACTION_KINDS}
    )
    if unknown:
        message = (
            f"{name} entries must be KIND or 'KIND: description' with KIND one of "
            f"{', '.join(autonomy.ACTION_KINDS)}; {len(unknown)} entries name no kind"
        )
        raise DraftError(message)
    return actions


# speckit.ballast.review writes each kind's report here; spec reconciliation
# writes the convergence report that the `convergence` check reads.
REPORT_NAMES = {"spec-reconciliation": "convergence"}


def review_report(feature: str, kind: str) -> str:
    """Repository-relative path of a review kind's report."""
    return f"{feature}/reviews/{REPORT_NAMES.get(kind, kind)}.md"


def _validate_review(  # noqa: C901, PLR0912 - one field per rule
    feature: Feature, review: object, point: str, step: dict
) -> dict:
    run = _require_run(feature)
    if not isinstance(review, dict):
        message = f"{point} draft needs a review entry"
        raise DraftError(message)
    kind = review.get("kind")
    if kind not in POINT_KINDS[point]:
        message = f"{point} review kind must be one of {', '.join(POINT_KINDS[point])}"
        raise DraftError(message)
    if review.get("verdict") not in autonomy.VERDICTS:
        message = f"{kind} review has an unknown verdict"
        raise DraftError(message)
    report = review_report(feature.relative, kind)
    if review.get("report") != report:
        message = f"{kind} review report must be {report}"
        raise DraftError(message)
    _repo_path(feature, report, "review report")
    findings = review.get("findings")
    if not isinstance(findings, list) or len(findings) > 100:  # noqa: PLR2004
        message = f"{kind} review findings must be a list"
        raise DraftError(message)
    checked = []
    for finding in findings:
        if not isinstance(finding, dict) or not FINDING_ID.fullmatch(
            str(finding.get("id"))
        ):
            message = f"{kind} review has a finding without an F-NNN id"
            raise DraftError(message)
        for field, allowed in (
            ("severity", autonomy.SEVERITIES),
            ("label", autonomy.FINDING_LABELS),
            ("disposition", autonomy.DISPOSITIONS),
        ):
            if finding.get(field) not in allowed:
                message = f"{kind} finding {finding['id']} has an invalid {field}"
                raise DraftError(message)
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
        # A local fallback's review is never cross-provider (#23 AC-016).
        "cross_provider": step.get("route") != "fallback"
        and step.get("integration") != run["integration"],
        "author_provider": run["integration"],
        "findings": checked,
    }
    required = review.get("required_kinds", [])
    if required:
        if not isinstance(required, list) or any(
            k not in autonomy.REVIEW_KINDS for k in required
        ):
            message = f"{kind} review declares unknown required kinds"
            raise DraftError(message)
        entry["required_kinds"] = sorted(set(required))
    if "privileged_actions" in review:
        entry["privileged_actions"] = _privileged_list(
            review["privileged_actions"], "review privileged_actions"
        )
    return entry


def _validate_draft(  # noqa: C901, PLR0912, PLR0915 - one field per rule
    feature: Feature, data: object, point: str, step: dict
) -> dict:
    """Check one decision draft against the draft contract."""
    if not isinstance(data, dict):
        message = f"{point} draft must be a JSON object"
        raise DraftError(message)
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
        raise DraftError(message)
    if data.get("decision") != autonomy.POINT_DECISION[point]:
        message = f"{point} decision must be {autonomy.POINT_DECISION[point]}"
        raise DraftError(message)
    summary = _text_field(data.get("summary"), "summary", 500)
    if "\n" in summary or "\r" in summary:
        message = "summary must be one line"
        raise DraftError(message)
    basis = _text_field(data.get("basis"), "basis", 2000)
    artifact = _repo_path(feature, data.get("artifact"), "artifact")
    artifact_path = feature.root / artifact
    if not artifact_path.is_file():
        message = f"artifact {artifact!r} must be a regular file"
        raise DraftError(message)
    model = data.get("model")
    if model is None:
        model = "unreported"
    elif not isinstance(model, str) or not MODEL.fullmatch(model):
        message = "model must be a short model name"
        raise DraftError(message)
    provider = step.get("integration", "runner")
    if step.get("route") == "fallback":
        # The wrapper knows the local fallback's model; the agent's report
        # of its own model is ignored (#23 AC-016).
        provider, model = step.get("provider", "ollama"), step.get("model", model)
    material = data.get("material", False)
    supersedes = data.get("supersedes")
    if not isinstance(material, bool) or (
        supersedes is not None and not re.fullmatch(r"PD-\d{4}", str(supersedes))
    ):
        message = "material must be a boolean and supersedes a PD-NNNN id or null"
        raise DraftError(message)
    risk = data.get("risk")
    if risk is not None and risk not in autonomy.RISKS:
        message = "risk must be R0, R1 or R2"
        raise DraftError(message)
    if "privileged_actions" not in data:
        message = "draft must list privileged_actions (empty when none)"
        raise DraftError(message)
    entry = {
        "point": point,
        "decision": autonomy.POINT_DECISION[point],
        "summary": summary,
        "basis": basis,
        "evidence": _evidence(feature, data.get("evidence")),
        "artifact": {"path": artifact, "sha256": autonomy.sha256_file(artifact_path)},
        "agent": {
            "provider": provider,
            "model": model,
            "role": step.get("role", "runner"),
            "step_id": step.get("step", "runner"),
            # The wrapper's retries of this step (#21 R4), never the agent's.
            "attempts": step.get("attempt", 1),
            "refusals": list(step.get("refusals") or []),
        },
        "material": material,
        "supersedes": supersedes,
        "privileged_actions": _privileged_list(
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
        raise DraftError(message)
    assumption = data.get("assumption")
    if point == "clarification":
        if not isinstance(assumption, dict):
            message = "clarification draft needs an assumption"
            raise DraftError(message)
        if assumption.get("reversible") is not True:
            message = (
                "clarification assumption must be reversible; a non-reversible "
                "choice must be a block"
            )
            raise DraftError(message)
        entry["assumption"] = {
            "question": _text_field(assumption.get("question"), "question", 1000),
            "default": _text_field(assumption.get("default"), "default", 1000),
            "reversible": True,
        }
    elif assumption is not None:
        message = f"{point} draft must not carry an assumption"
        raise DraftError(message)
    if notes:
        entry["notes"] = notes
    return entry


def _qualifying_steps(steps: list[dict], point: str) -> list[dict]:
    """Agent steps whose drafts a recorder for point may accept.

    The immediately preceding agent step, or, for a review point, the trailing
    run of reviewer steps (review-implementation then review-specialists).
    Attempts whose drafts the wrapper refused and set aside never qualify.
    """
    steps = [step for step in steps if not step.get("refused")]
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


def _collect_drafts(  # noqa: C901 - every draft source is checked
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
            raise DraftError(message)
        copy = autonomy.snapshot_draft(feature.root, run["run_id"], step["step"], name)
        data = copy.read_bytes()
        if hashlib.sha256(data).hexdigest() != digest:
            message = f"operator copy of draft {name} does not match its digest"
            raise ContractError(message)
        try:
            drafts.append((name, point, json.loads(data), step))
        except ValueError as error:
            message = f"draft {name} is not valid JSON"
            raise DraftError(message) from error
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
        raise DraftError(message)


def _check_dispositions(review: dict, *, fixing: bool = False) -> None:
    """#27's rule; while a fix cycle remains, `open` means "fix this" (#21 R2)."""
    for finding in review["findings"]:
        severity, disposition = finding["severity"], finding["disposition"]
        if disposition == "open" and severity not in {"low", "info"} and not fixing:
            message = f"{finding['id']}: open is valid only for low and info findings"
            raise DraftError(message)
        if disposition == "accepted-provisionally" and not finding["reason"]:
            message = f"{finding['id']}: accepted-provisionally needs a reason"
            raise DraftError(message)


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


WORKFLOW_YAML = re.compile(
    r"(?:\.github|templates/github)/(?:workflows/.+|actions/.+/action)\.ya?ml"
)
ADDED_USES = re.compile(
    r"""^\+(?:\s*(?:-\s+)?|.*[{,]\s*)["']?uses["']?\s*:""", re.MULTILINE
)


def _adds_action_reference(feature: Feature, names: list[str]) -> bool:
    """Return whether a changed workflow file adds or edits a `uses:` line (#83)."""
    paths = [name for name in names if WORKFLOW_YAML.fullmatch(name)]
    if not paths:
        return False
    diff = _git(
        feature.root,
        "diff-tree",
        "-r",
        "-p",
        "-U0",
        "--end-of-options",
        _baseline_tree(feature),
        worktree_tree(feature.root),
        "--",
        *paths,
    )
    return bool(ADDED_USES.search(diff))


def required_kinds(feature: Feature, reviews: list[dict]) -> set[str]:
    """Review kinds an Autonomous implementation review must cover (R-08)."""
    run = _require_run(feature)
    required = {"engineering", "test", "security"}
    changed = _changed_since_baseline(feature)
    if _adds_action_reference(feature, changed):
        required.add("dependency")
    for name in changed:
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


REQUIRED_REVIEWS_DIR = ".specify/workflow-state/required-reviews"


def write_required_reviews(feature: Feature, reviews: list[dict] | None = None) -> Path:
    """Tell the specialists step which kinds the recorder will require.

    The same computation as `record-decision --point implementation-review`;
    `reviews` carries kinds a reviewer already declared. Under `.specify/`,
    which agent steps see read-only; the recorder still recomputes it.
    """
    required = sorted(required_kinds(feature, reviews or []))
    relative = f"{REQUIRED_REVIEWS_DIR}/{Path(feature.relative).name}.json"
    text = json.dumps({"feature": feature.relative, "required": required}) + "\n"
    return autonomy.replace_file(feature.root, relative, text)


def merge_requested_kinds(feature: Feature, step: dict) -> None:
    """Add the kinds the engineering review requests to the specialists hint (#83).

    Called by the wrapper once an implementation review step is accepted, before
    the specialists step starts. Anything but a list of known kinds is left to
    the recorder, which rejects it.
    """
    if "implementation-review.json" not in (step.get("drafts") or {}):
        return
    data = _step_draft(feature, step, "implementation-review.json")
    review = data.get("review") if isinstance(data, dict) else None
    kinds = review.get("required_kinds") if isinstance(review, dict) else None
    if (
        isinstance(kinds, list)
        and kinds
        and all(k in autonomy.REVIEW_KINDS for k in kinds)
    ):
        write_required_reviews(feature, [{"required_kinds": kinds}])


def _frozen_check(feature: Feature, *, required: bool = False) -> None:
    run = _require_run(feature)
    frozen = run.get("frozen_tree")
    if required and not frozen:
        _block(
            feature,
            "postcondition",
            "no tree was frozen after implementation review",
        )
    if frozen and autonomy.tree_digest(feature.root, (feature.relative,)) != frozen:
        _block(
            feature,
            "postcondition",
            "files outside the feature directory changed after the last "
            "implementation review froze the tree; after it only the spec, plan, "
            "tasks, decisions and drafts may change (code fixes belong in the fix "
            "loop, before the freeze)",
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
            note = (
                f"{current['id']} {current['point']}: {artifact['path']} "
                "no longer exists"
            )
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
        raise DraftError(message)


# --- Fix loop (#21 R1-R3) ----------------------------------------------------

FIX_INPUT_DIR = ".specify/workflow-state/fix-input"
# Characters of each failed check's output the fix input carries.
OUTPUT_TAIL = 4000


def _printable(text: str, limit: int) -> str:
    """Untrusted text made printable (newlines and tabs kept), last `limit` chars."""
    return "".join(c if c.isprintable() or c in "\n\t" else "?" for c in text[-limit:])


def fix_loop(feature: Feature) -> bool:
    """Whether the run's own workflow copy has the fix loop (#21 R19).

    The engine resumes a run from its own copy: a run started under
    ballast-autonomous 1.1.0 has no fix step, so its findings block as in #27.
    """
    path = feature.root / ".specify/workflows/runs" / feature.key / "workflow.yml"
    try:
        return "speckit.ballast.fix" in path.read_text(encoding="utf-8")
    except OSError:
        return False


def _failed_feedback(feature: Feature) -> list[dict]:
    """Failed commands of the latest `run-checks --feedback` run."""
    run = _require_run(feature)
    entries = autonomy.read_feedback(feature.root, run["run_id"])
    if not entries:
        return []
    return [r for r in entries[-1]["results"] if r.get("exit") != 0]


def _check_text(result: dict) -> str:
    outcome = "timed out" if result.get("timed_out") else f"exit {result.get('exit')}"
    return f"check {result.get('command')!r} ({outcome})"


def _blocking(reviews: list[dict]) -> list[str]:
    """High or critical findings and non-approved verdicts (#27's stop rule)."""
    found = [
        f"{review['kind']} {finding['id']} ({finding['severity']})"
        for review in reviews
        for finding in review["findings"]
        if finding["severity"] in autonomy.BLOCKING_SEVERITIES
    ]
    return found + [
        f"{review['kind']} verdict {review['verdict']}"
        for review in reviews
        if review["verdict"] != "approved"
    ]


def _open_to_fix(reviews: list[dict]) -> list[str]:
    """Medium findings left `open`: while a cycle remains, open means fix (R2)."""
    return [
        f"{review['kind']} {finding['id']} ({finding['severity']}, open)"
        for review in reviews
        for finding in review["findings"]
        if finding["disposition"] == "open"
        and finding["severity"] not in {"low", "info"}
        and finding["severity"] not in autonomy.BLOCKING_SEVERITIES
    ]


def review_rule(feature: Feature, point: str, reviews: list[dict]) -> tuple[str, list]:
    """How a review point's recorder treats these reviews.

    Returns ("block", reasons) for #27's review-finding stop, ("limit",
    reasons) when the fix cycles are spent, ("fixing", []) while a cycle
    remains (the relaxed disposition rule) or ("strict", []).
    """
    blocking = _blocking(reviews)
    if point not in {"implementation-review", "specialist-review"} or not fix_loop(
        feature
    ):
        return ("block", blocking) if blocking else ("strict", [])
    if autonomy.fix_state(_require_run(feature))["cycles"] < autonomy.FIX_CYCLES:
        return "fixing", []
    failed = [_check_text(r) for r in _failed_feedback(feature)]
    if blocking or failed:
        return "limit", blocking + failed
    return "strict", []


def _write_fix_input(feature: Feature, stored: list[dict], failed: list[dict]) -> None:
    """Write what the fix step reads: findings and failed checks, as data (R3).

    Under `.specify/`, which agent steps see read-only.
    """
    run = _require_run(feature)
    findings = []
    verdicts = []
    for entry in stored:
        review = entry.get("review")
        if not review:
            continue
        if review["verdict"] != "approved":
            verdicts.append(
                {
                    "decision": entry["id"],
                    "kind": review["kind"],
                    "verdict": review["verdict"],
                    "report": review["report"],
                }
            )
        findings += [
            {
                "decision": entry["id"],
                "kind": review["kind"],
                "id": finding["id"],
                "severity": finding["severity"],
                "label": finding["label"],
                "reason": finding["reason"],
                "report": review["report"],
            }
            for finding in review["findings"]
            if finding["severity"] in autonomy.BLOCKING_SEVERITIES
            or (
                finding["disposition"] == "open"
                and finding["severity"] not in {"low", "info"}
            )
        ]
    checks = [
        {
            "command": result.get("command"),
            "exit": result.get("exit"),
            "timed_out": bool(result.get("timed_out")),
            "output_tail": _printable(str(result.get("output_tail", "")), OUTPUT_TAIL),
        }
        for result in failed
    ]
    data = {
        "feature": feature.relative,
        "cycle": autonomy.fix_state(run)["cycles"] + 1,
        "findings": findings,
        "verdicts": verdicts,
        "checks": checks,
    }
    relative = f"{FIX_INPUT_DIR}/{Path(feature.relative).name}.json"
    autonomy.replace_file(
        feature.root, relative, json.dumps(data, indent=2, sort_keys=True) + "\n"
    )


def _check_recheck(feature: Feature, reviews: list[dict]) -> None:
    """Refuse a recheck that omits a finding the fix input listed (SEC2-003).

    Each listed finding of a kind rechecked here must appear again, by ID,
    with a disposition; a missing one is the reviewer's to correct.
    """
    if autonomy.fix_state(_require_run(feature))["state"] != "review-pending":
        return
    path = feature.root / FIX_INPUT_DIR / f"{Path(feature.relative).name}.json"
    if not path.is_file() or path.is_symlink():
        return
    try:
        listed = json.loads(path.read_text(encoding="utf-8")).get("findings") or []
    except (ValueError, AttributeError) as error:
        message = f"the fix input {path.name} is not valid JSON"
        raise ContractError(message) from error
    found = {(r["kind"], f["id"]) for r in reviews for f in r["findings"]}
    kinds = {r["kind"] for r in reviews}
    missing = sorted(
        f"{f.get('kind')} {f.get('id')}"
        for f in listed
        if isinstance(f, dict)
        and f.get("kind") in kinds
        and (f.get("kind"), f.get("id")) not in found
    )
    if missing:
        message = (
            "the recheck omits findings the fix cycle had to fix; list each with "
            f"its disposition: {', '.join(missing)}"
        )
        raise DraftError(message)


def _supersede(feature: Feature, point: str, entries: list[dict]) -> None:
    """Let a point recorded again replace its current decisions (#21 R6).

    A single point supersedes its one current decision, as intent always
    did; a review point supersedes every current entry of that point, and
    implementation-review also every current specialist review.
    """
    if point in {"clarification", "decision-resolution"} or not entries:
        return
    run = _require_run(feature)
    decisions = autonomy.read_decisions(feature.root, run["run_id"])
    if point not in autonomy.REVIEW_POINTS:
        found = autonomy.current(decisions, point)
        for entry in entries:
            if found and entry["supersedes"] is None:
                entry["supersedes"] = found[-1]["id"]
        return
    points = {point} | (
        {"specialist-review"} if point == "implementation-review" else set()
    )
    old = [
        e["id"] for e in autonomy.current_decisions(decisions) if e["point"] in points
    ]
    if not old:
        return
    for entry in entries:
        if entry["supersedes"] is not None:
            entry.setdefault("notes", []).append(
                f"ignored supersedes {entry['supersedes']}; the recorder replaces "
                "the earlier reviews"
            )
        entry["supersedes"] = None
    entries[0]["supersedes"] = old[0] if len(old) == 1 else old


def _check_intent_evidence(feature: Feature, entry: dict) -> None:
    """Provisional intent cites the discovery brief and the traced spec (#21 FR-004)."""
    if not feature.file(DISCOVERY).exists():
        return
    needed = [f"{feature.relative}/{DISCOVERY}", f"{feature.relative}/spec.md"]
    missing = [path for path in needed if path not in entry["evidence"]]
    if missing:
        message = (
            "intent evidence must cite the discovery brief and the spec traced to "
            f"it: add {', '.join(missing)}"
        )
        raise DraftError(message)


def record_decision(  # noqa: C901, PLR0912, PLR0915 - one guarded recorder
    feature: Feature, point: str, *, recheck: bool = False
) -> None:
    """Validate the preceding step's drafts and append provisional decisions.

    For implementation-review in a run with the fix loop, findings that need a
    fix set the fix state to `fix-pending` while a cycle remains, instead of
    blocking (#21 R2). `recheck` records the review after a fix cycle; it
    writes nothing unless the fix state is `review-pending`.
    """
    run = _require_run(feature)
    fix = autonomy.fix_state(run)
    if recheck:
        if point != "implementation-review":
            message = "--recheck applies only to implementation-review"
            raise ContractError(message)
        if fix["state"] != "review-pending":
            return
    elif point == "implementation-review" and fix["state"] != "idle":
        message = (
            f"the fix state is {fix['state']}; this review is recorded with --recheck"
        )
        raise ContractError(message)
    if point == "decision-resolution" and (
        fix["state"] != "idle" or not run.get("frozen_tree")
    ):
        _block(
            feature,
            "postcondition",
            f"decision resolution needs a finished fix loop and a frozen tree; the "
            f"fix state is {fix['state']}"
            + ("" if run.get("frozen_tree") else " and no tree was frozen"),
        )
    points = (
        [point, "specialist-review"] if point == "implementation-review" else [point]
    )
    drafts, steps = _collect_drafts(feature, points)
    _expected_drafts(point, drafts)
    entries = [
        _validate_draft(feature, data, draft_point, step)
        for _, draft_point, data, step in drafts
    ]
    if point == "intent":
        for entry in entries:
            _check_intent_evidence(feature, entry)
    if point in autonomy.REVIEW_POINTS:
        _reviewer_tree_check(feature, steps)
    if point in {"decision-resolution", "spec-reconciliation"}:
        _frozen_check(feature)
    reviews = [entry["review"] for entry in entries if "review" in entry]
    for review in reviews:
        _check_narrative(feature, review)
    if recheck:
        _check_recheck(feature, reviews)
    for review in reviews:
        _render_findings(feature, review)
    rule, reasons = review_rule(feature, point, reviews)
    evidence = sorted({review["report"] for review in reviews})
    if rule == "block":
        _block(
            feature,
            "review-finding",
            "reviews block the run (high or critical findings, or a verdict "
            "other than approved): " + ", ".join(reasons),
            evidence=evidence,
        )
    if rule == "limit":
        _block(
            feature,
            "limit",
            autonomy.limit_condition(
                "fix-cycles",
                "still open after the last fix cycle: " + ", ".join(reasons),
            ),
            evidence=evidence,
            limit="fix-cycles",
        )
    for review in reviews:
        _check_dispositions(review, fixing=rule == "fixing")
    if point == "implementation-review":
        missing = sorted(
            required_kinds(feature, reviews) - {r["kind"] for r in reviews}
        )
        if missing:
            message = f"required reviews missing: {', '.join(missing)}"
            raise ContractError(message)
    failed = _failed_feedback(feature) if rule == "fixing" else []
    needed = rule == "fixing" and bool(
        _blocking(reviews) or _open_to_fix(reviews) or failed
    )
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
    if point == "implementation-review" and fix_loop(feature):
        for entry in entries:
            entry["fix_cycle"] = fix["cycles"]
    _supersede(feature, point, entries)
    if point == "tasks":
        # No tasks.md defers nothing; the tasks check refuses it on its own.
        tasks_file = feature.file("tasks.md")
        tasks_text = feature.read("tasks.md") if tasks_file.is_file() else ""
        deferred = [
            {
                "task": task_id,
                "text": description[:DEFERRED_TEXT],
                "sha256": task_digest(description),
            }
            for task_id, (done, description, _) in deferred_tasks(tasks_text).items()
            if not done
        ]
        for entry in entries:
            if deferred:
                entry["deferred"] = deferred
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
        if needed:
            _write_fix_input(feature, [stored for _, stored in appended], failed)
            run["fix"] = {"cycles": fix["cycles"], "state": "fix-pending"}
        else:
            run["frozen_tree"] = autonomy.tree_digest(feature.root, (feature.relative,))
            if fix_loop(feature):
                run["fix"] = {"cycles": fix["cycles"], "state": "idle"}
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


def _step_command(command: object) -> str:
    """`/speckit-ballast-fix`, `$speckit-ballast-fix` -> `speckit-ballast-fix`."""
    return str(command or "").lstrip("/$").replace(".", "-")


def record_fix(feature: Feature) -> None:
    """After a fix step: count the cycle and ask for the recheck (#21 R1).

    Writes nothing unless the fix state is `fix-pending`. The fix step must
    be the last agent step, and the implementation contract must still hold.
    """
    run = _require_run(feature)
    fix = autonomy.fix_state(run)
    if fix["state"] != "fix-pending":
        return
    steps = [
        s
        for s in autonomy.unconsumed_steps(feature.root, run["run_id"])
        if not s.get("refused")
    ]
    last = steps[-1] if steps else {}
    if (
        not last.get("ran")
        or _step_command(last.get("command")) != "speckit-ballast-fix"
        or last.get("exit_code") != 0
    ):
        _block(
            feature,
            "postcondition",
            "record-fix needs the fix step that ran just before it",
        )
    if last.get("reviews_before") != autonomy.reviews_digest(
        feature.root, feature.relative
    ):
        _block(
            feature,
            "postcondition",
            "the fix step changed reviews/; only reviewer steps write the reports",
        )
    check_implementation(feature)
    run["fix"] = {"cycles": fix["cycles"] + 1, "state": "review-pending"}
    autonomy.write_run(feature.root, run)
    autonomy.consume_steps(feature.root, run["run_id"])
    write_record(feature)


# --- Draft checks inside the agent wrapper (#21 R4) --------------------------

DECIDE_POINTS = ("scope", "intent", "plan", "tasks", "final-acceptance")
REVIEW_ARGUMENTS = {
    "plan": ("plan-review",),
    "implementation": ("implementation-review", "specialist-review"),
    "implementation-recheck": ("implementation-review", "specialist-review"),
    "specialists": ("specialist-review",),
    "specialists-recheck": ("specialist-review",),
    "spec-reconciliation": ("spec-reconciliation",),
}
# Agent command (and its first argument) -> the draft points it writes.
STEP_POINTS = {
    "speckit-ballast-decide": {point: (point,) for point in DECIDE_POINTS},
    "speckit-ballast-discover": {None: ("clarification",)},
    "speckit-ballast-clarify": {None: ("clarification",)},
    "speckit-ballast-review": REVIEW_ARGUMENTS,
    "speckit-ballast-resolve": {None: ("decision-resolution",)},
}


def step_points(prompt: str) -> tuple[str, ...]:
    """Return the draft points an agent prompt's command writes; () for none."""
    words = prompt.split()
    if not words:
        return ()
    table = STEP_POINTS.get(_step_command(words[0]))
    if table is None:
        return ()
    if None in table:
        return table[None]
    return table.get(words[1] if len(words) > 1 else "", ())


def check_step_drafts(  # noqa: C901, PLR0912 - the recorder's checks, in its order
    feature: Feature, prompt: str, step: dict, *, blocked: bool = False
) -> None:
    """Check one agent step's drafts with the recorder's own draft contract.

    Raises DraftError for what the agent can correct in its draft; returns
    when the recorder will decide (including a terminal review block). The
    drafts are read from their operator copies; nothing is written.
    """
    _require_run(feature)
    created = step.get("drafts") or {}
    if blocked:
        if "block.json" not in created:
            return  # run.py records its fallback decision block.
        data = _step_draft(feature, step, "block.json")
        try:
            autonomy.validate_block_draft(data)
        except autonomy.AutonomyError as error:
            message = f"block.json: {error}"
            raise DraftError(message) from error
        return
    points = step_points(prompt)
    if not points:
        return
    drafts = []
    for name in sorted(created):
        point = _draft_point(name, list(points))
        if point is None:
            message = f"unexpected draft {name!r} for {points[0]}"
            raise DraftError(message)
        drafts.append((name, point, _step_draft(feature, step, name), step))
    if points[0] not in autonomy.MULTI_ENTRY:
        _expected_drafts(points[0], drafts)
    entries = [
        _validate_draft(feature, data, point, step) for _, point, data, _ in drafts
    ]
    for entry in entries:
        if entry["point"] == "intent":
            _check_intent_evidence(feature, entry)
    reviews = [entry["review"] for entry in entries if "review" in entry]
    for review in reviews:
        _check_narrative(feature, review)
    _check_recheck(feature, reviews)
    rule, _ = review_rule(feature, points[0], reviews)
    if rule in {"block", "limit"}:
        return
    for review in reviews:
        _check_dispositions(review, fixing=rule == "fixing")
    if _step_command(prompt.split(maxsplit=1)[0]) == "speckit-ballast-discover":
        _check_brief_draft(feature)


def _check_brief_draft(feature: Feature) -> None:
    """Check the discover step's brief as validate-discovery checks its form (#95).

    A format or provenance error is the agent's to correct, so the wrapper
    retries the step on it; what the recorded decisions and operator state
    must match stays with validate-discovery.
    """
    try:
        text = feature.read(DISCOVERY)
        _check_brief(feature, text, _parse_discovery(text), "autonomous")
    except DraftError:
        raise
    except ContractError as error:
        raise DraftError(str(error)) from error


def _step_draft(feature: Feature, step: dict, name: str) -> object:
    """Parse a draft's operator copy; a draft that is not JSON is the agent's."""
    run = _require_run(feature)
    digest = (step.get("drafts") or {}).get(name)
    if digest == "invalid":
        message = f"draft {name!r} is not a regular file"
        raise DraftError(message)
    try:
        data = autonomy.snapshot_draft(
            feature.root, run["run_id"], step["step"], name
        ).read_bytes()
    except (OSError, autonomy.AutonomyError) as error:
        message = f"draft {name} is unreadable"
        raise ContractError(message) from error
    if hashlib.sha256(data).hexdigest() != digest:
        message = f"operator copy of draft {name} does not match its digest"
        raise ContractError(message)
    try:
        return json.loads(data)
    except ValueError as error:
        message = f"draft {name} is not valid JSON"
        raise DraftError(message) from error


def renew_intent(feature: Feature) -> None:
    """Stop the run when a resolution changed the spec after the intent decision.

    A changed spec needs a new intent decision by a deciding agent or a human
    (FR-010, FR-012); the runner never decides one, so the run blocks as stale
    intent and continues human-gated, where `approve-intent` decides it.
    """
    run = _require_run(feature)
    spec = check_clarified_spec(feature)
    decisions = autonomy.read_decisions(feature.root, run["run_id"])
    current = autonomy.current(decisions, "intent")
    if len(current) != 1:
        message = "no single current intent decision to renew"
        raise ContractError(message)
    old = current[0]
    if old.get("spec_digest") == spec_digest(spec):
        return
    number = int(old["id"].split("-")[1])
    resolutions = [
        entry["id"]
        for entry in decisions
        if entry["point"] == "decision-resolution"
        and int(entry["id"].split("-")[1]) > number
    ]
    _block(
        feature,
        "postcondition",
        f"stale intent: {feature.relative}/spec.md changed after {old['id']}"
        + (f" through {', '.join(resolutions)}" if resolutions else "")
        + "; the changed spec needs a new intent decision by a deciding agent "
        "or a human (FR-010, FR-012)",
        evidence=[f"{feature.relative}/spec.md"],
    )


def record_provisional_intent(feature: Feature, *, renew: bool = False) -> None:
    """Record the intent decision, or (`--renew`) block when the spec changed."""
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


class ChecksExhaustedError(Exception):
    """The time left ran out before the next check command."""


def run_commands(  # noqa: PLR0913 - one confined run, every input explicit
    root: Path,
    feature: str,
    commands: list[str],
    timeout_minutes: int,
    *,
    remaining: object = None,
    keep_output: bool = False,
    read_only: bool = False,
) -> list[dict]:
    """Run trusted check commands, each confined; the mode-neutral core.

    `remaining`, when given, returns the seconds left before a deadline; an
    exhausted deadline raises ChecksExhaustedError before the next command,
    and no command may run past it. Without it (a Chat run, #20) only each
    command's own timeout applies. With `keep_output` (#21 R3) a failed
    command's result carries a bounded, printable `output_tail`. With
    `read_only` (#117) the whole checkout is read-only to the command.
    """
    env = autonomy.confined_env(dict(os.environ), None)
    results = []
    with tempfile.TemporaryDirectory(prefix="ballast-checks-") as private:
        for command in commands:
            argv = autonomy.confined_argv(
                root,
                ["sh", "-c", command],
                private=Path(private),
                feature=feature,
                env=dict(os.environ),
                integration=None,  # no agent CLI: neither login (#81)
                writable_checkout=not read_only,
            )
            # Measured after the sandbox is set up, just before the launch.
            left = remaining() if callable(remaining) else None
            if left is not None and left <= 0:
                raise ChecksExhaustedError
            timeout = timeout_minutes * 60
            started = time.monotonic()
            timed_out = False
            try:
                done = subprocess.run(  # noqa: S603 - resolved bwrap, argument list
                    argv,
                    cwd=root,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=timeout if left is None else min(timeout, left),
                    check=False,
                )
                code = done.returncode
                output = done.stdout + done.stderr
                sys.stdout.write(done.stdout[-4000:])
                sys.stderr.write(done.stderr[-4000:])
            except subprocess.TimeoutExpired as error:
                code, timed_out = 124, True
                output = "".join(
                    part.decode("utf-8", "replace") if isinstance(part, bytes) else part
                    for part in (error.stdout or "", error.stderr or "")
                )
            result = {
                "command": command,
                "exit": code,
                "seconds": round(time.monotonic() - started, 1),
                "timed_out": timed_out,
                "provenance": "runner",
            }
            if keep_output and code != 0:
                # Project output: kept in operator state, bounded and
                # printable, for the fix input only.
                result["output_tail"] = _printable(output, OUTPUT_TAIL)
            results.append(result)
    return results


def project_checks(root: Path, feature: str) -> dict:
    """Run `[checks] commands` for a Chat run, with no limit or freeze (#20).

    Returns {"results", "unavailable", "tree", "protected_changes"}: `tree`
    is the tree digest (feature reviews excluded) the commands ran against;
    no `[checks]` table is `unavailable`. A command that changed a protected
    input leaves the tamper marker.
    """
    config = autonomy.load_config(root)
    tree = autonomy.tree_digest(root, (f"{feature}/reviews",))
    if config.get("checks") is None:
        return {
            "results": [],
            "unavailable": True,
            "tree": tree,
            "protected_changes": [],
        }
    checks = autonomy.parse_checks(config)
    before = _protected_digests(root)
    results = run_commands(root, feature, checks["commands"], checks["timeout_minutes"])
    after = _protected_digests(root)
    changed = sorted(
        n for n in before.keys() | after.keys() if before.get(n) != after.get(n)
    )
    if changed:
        _mark_tampered(root, changed)
    return {
        "results": results,
        "unavailable": False,
        "tree": tree,
        "protected_changes": changed,
    }


def _feedback_due(run: dict) -> bool:
    """Whether a `run-checks --feedback` step has work (#21 R3).

    After implementation (no review recorded, so no frozen tree) and in a
    fix cycle under review; an idle cycle slot after the freeze has none.
    """
    state = autonomy.fix_state(run)["state"]
    return state == "review-pending" or (state == "idle" and not run.get("frozen_tree"))


def _acceptance_checks(  # noqa: C901, PLR0911, PLR0912 - every refusal is reported
    feature: Feature, run: dict, timeout_minutes: int
) -> tuple[dict, dict | None, list[tuple[str, str, str, int]]]:
    """Run each test the agent-proposed manifest maps (#117, ADR-0018).

    Each distinct test runs once, confined like the check commands but with
    the whole checkout read-only, under the check timeout and the run's wall
    time. Returns the record's summary, the snapshot the results bind to (None
    when nothing ran) and one `(ac, test, status, exit)` per mapped pair that
    ran. A missing, malformed, stale or oversized manifest runs nothing and
    says so; nothing here writes the ledger.
    """
    import ledger  # noqa: PLC0415 - ledger imports this module

    root, relative = feature.root, feature.relative
    path = root / relative / "acceptance-evidence.json"
    if not os.path.lexists(path):
        return {"status": "no-manifest"}, None, []
    # Bounded before it is read: the manifest is agent-written.
    if path.is_file() and path.stat().st_size > autonomy.MAX_PUBLISHED_FILE:
        return {"status": "too-many"}, None, []
    try:
        manifest = ledger.archive_manifest(root, run["run_id"], relative)
    except ledger.StaleManifestError:
        return {"status": "stale"}, None, []
    except (OSError, ValueError, KeyError, TypeError):
        return {"status": "malformed"}, None, []
    criteria = {
        ac: list(dict.fromkeys(tests)) for ac, tests in manifest["criteria"].items()
    }
    tests = sorted({test for mapped in criteria.values() for test in mapped})
    if sum(map(len, criteria.values())) > autonomy.ACCEPTANCE_TESTS:
        return {"status": "too-many"}, None, []
    results: list[dict] = [{"ac": ac} for ac in sorted(criteria) if not criteria[ac]]
    if not tests:
        return {"status": "recorded", "results": results}, None, []
    python = root / ".venv/bin/python"
    if not python.is_file():
        return {"status": "no-python", "results": results}, None, []
    try:
        snapshot = ledger.artifact_digests(root, relative)
        published = _published_tests(root, tests)
    except (OSError, ValueError):
        return {"status": "snapshot-unavailable", "results": results}, None, []
    ran: dict[str, dict] = {}
    exhausted = False
    for test in tests:
        if test not in published:
            continue
        try:
            ran[test] = run_commands(
                root,
                relative,
                [shlex.join([str(python), "-c", ledger.UNITTEST_CHECK, test])],
                timeout_minutes,
                remaining=lambda: autonomy.remaining_seconds(run),
                read_only=True,
            )[0]
        except ChecksExhaustedError:
            exhausted = True
            break
    recorded = []
    for ac in sorted(criteria):
        for test in criteria[ac]:
            done = ran.get(test)
            if done is None:
                status = "not run" if test in published else "not published"
                results.append({"ac": ac, "test": test, "status": status})
                continue
            status = "passed" if done["exit"] == 0 else "failed"
            results.append(
                {
                    "ac": ac,
                    "test": test,
                    "status": status,
                    "timed_out": done["timed_out"],
                }
            )
            recorded.append((ac, test, status, abs(done["exit"])))
    summary = {"status": "recorded", "results": results, "exhausted": exhausted}
    return summary, snapshot, recorded


def _published_tests(root: Path, tests: list[str]) -> set[str]:
    """Return the tests whose module file the run publishes (#117 review).

    `git add --all` publishes tracked and unignored files; a test in an
    ignored or missing file would pass here and be absent from the PR head.
    """
    import ledger  # noqa: PLC0415 - ledger imports this module

    modules: dict[str, str] = {}
    for test in tests:
        parts = test.split(".")
        for size in range(len(parts) - 1, 0, -1):
            path = "/".join(parts[:size]) + ".py"
            if (root / path).is_file() and not (root / path).is_symlink():
                modules[test] = path
                break
    if not modules:
        return set()
    listed = ledger._git(  # noqa: SLF001 - the ledger's hardened Git
        root,
        "--literal-pathspecs",
        "ls-files",
        "-z",
        "--cached",
        "--others",
        "--exclude-standard",
        "--",
        *sorted(set(modules.values())),
    ).split("\0")
    return {test for test, path in modules.items() if path in listed}


def _record_acceptance(
    feature: Feature,
    run: dict,
    acceptance: tuple[dict, dict | None, list] | None,
) -> None:
    """Write the acceptance checks to the ledger and the operator records.

    Called after the tamper and tree checks passed: the results bind to the
    snapshot taken before the tests ran, which must still be current.
    """
    import ledger  # noqa: PLC0415 - ledger imports this module

    path = autonomy.run_dir(feature.root, run["run_id"]) / "acceptance-checks.json"
    if acceptance is None:
        # Failed check commands: no acceptance check ran this time.
        path.unlink(missing_ok=True)
        return
    summary, snapshot, recorded = acceptance
    if recorded:
        try:
            if ledger.artifact_digests(feature.root, feature.relative) != snapshot:
                ledger.fail("the feature changed while the tests ran")
            ledger.record_runner_checks(
                feature.root, run["run_id"], feature.relative, snapshot, recorded
            )
        except (OSError, ValueError) as error:
            sys.stderr.write(f"acceptance checks not recorded: {error}\n")
            summary = {**summary, "status": "ledger-unavailable"}
    autonomy.write_json(path, summary)


def run_checks(feature: Feature, *, feedback: bool = False) -> None:  # noqa: C901 - one step
    """Run the trusted [checks] commands, confined, and record their results.

    With `feedback` (#21 R3) the results feed the fix loop: no frozen tree is
    needed, a failed command is recorded in checks-feedback.jsonl rather than
    blocking, and the tamper, tree-change and wall-time blocks still apply.
    """
    run = _require_run(feature)
    if feedback and not _feedback_due(run):
        return
    try:
        checks = autonomy.parse_checks(autonomy.load_config(feature.root))
    except autonomy.AutonomyError as error:
        _block(feature, "postcondition", str(error))
    # The review freeze holds across the final checks: the reviewed code is
    # what runs, and no check may change it (or anything else) on the way.
    if not feedback:
        _frozen_check(feature, required=True)
    checked = autonomy.checked_digest(feature.root, feature.relative)
    before = _protected_digests(feature.root)
    try:
        results = run_commands(
            feature.root,
            feature.relative,
            checks["commands"],
            checks["timeout_minutes"],
            remaining=lambda: autonomy.remaining_seconds(run),
            keep_output=feedback,
        )
    except ChecksExhaustedError:
        _block(feature, "limit", "wall-time limit exhausted before run-checks")
    acceptance = None
    if not feedback and all(r["exit"] == 0 for r in results):
        acceptance = _acceptance_checks(feature, run, checks["timeout_minutes"])
    if feedback:
        fix = autonomy.fix_state(run)
        autonomy.append_feedback(
            feature.root,
            run["run_id"],
            {
                "cycle": fix["cycles"] if fix["state"] == "review-pending" else 0,
                "at": autonomy.now(),
                "results": results,
            },
        )
    else:
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
    if autonomy.checked_digest(feature.root, feature.relative) != checked:
        _block(
            feature,
            "postcondition",
            "a check command changed the working tree; checks must leave the "
            "reviewed tree as it is (only git-ignored outputs may change)",
        )
    if not feedback:
        _record_acceptance(feature, run, acceptance)
    write_record(feature)
    if feedback:
        return
    failed = [r for r in results if r["exit"] != 0]
    if failed:
        _block(
            feature,
            "postcondition",
            "check commands failed: "
            + ", ".join(
                f"{r['command']!r} "
                f"({'timed out' if r['timed_out'] else 'exit ' + str(r['exit'])})"
                for r in failed
            ),
        )
    run["checked_tree"] = checked
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
    "record-fix": record_fix,
    "record-provisional-intent": record_provisional_intent,
    "run-checks": run_checks,
    "discovery": check_discovery,
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
        record_decision(feature, arguments.point, recheck=arguments.recheck)
    elif check == "record-provisional-intent":
        record_provisional_intent(feature, renew=arguments.renew)
    elif check == "run-checks":
        run_checks(feature, feedback=arguments.feedback)
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
    parser.add_argument("--recheck", action="store_true")
    parser.add_argument("--feedback", action="store_true")
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
