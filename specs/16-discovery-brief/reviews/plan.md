# Plan review: Source-backed discovery brief

- Review kind: plan
- Reviewer: claude/claude-opus-5-5, independent reviewer context; agent-provisional
- Artifacts reviewed: `plan.md`, `research.md` (R-01 to R-09), `data-model.md`, `contracts/discovery-brief.md`, `contracts/discover-command.md`, `contracts/workflow-and-validator.md` (`quickstart.md` was not read; nothing in the verdict depends on it), against `spec.md`, `intent.md` (PD-0003) and `autonomous/record.md` (PD-0001 to PD-0003)
- Policies read: `AGENTS.md`, `docs/policies/workflow.md`, `docs/policies/engineering.md`, `docs/policies/project/workflow.md`, `docs/policies/spec-kit-workflow.md`; skill `ballast-engineering-review`
- `tasks.md` and `decisions.md` do not exist yet; this review covers the plan only

## Method

Each requirement-coverage row in the plan was traced to a concrete mechanism in the contracts and data model. The plan's claims about existing code were then checked against the source:

- `artifacts.py`: the `clarification` point needs a reversible assumption (`_validate_draft`). `_expected_drafts` accepts zero drafts for `clarification`. `_draft_point` accepts `clarification-<suffix>.json` for multi-entry points, so `clarification-discovery-<n>.json` is valid. `_collect_drafts` accepts only drafts from the immediately preceding agent step, so `record-discovery` straight after `discover` fits. `_approval_path` and `state_dir` are the precedent for operator-only state.
- `autonomy.py`: `render_issue_snapshot(issue, scope_comment)` currently renders only the body and the intake scope comment under a 60,000-character cap. The eligibility check already lists `issues/<N>/comments`. `_gh` resolves `gh` through `draft_pr._resolve`, outside working trees, in an empty directory, against the repository pinned in `ballast.toml` (`repository()` → `_pinned_repository`). `validate_block_draft` already enforces the block contract (category, at least two options, `no_safe_default`, recovery, wording guard).
- `run.py`: today only the Autonomous start writes the snapshot. Agent blocks reach the run through `_agent_block` (exit 3 plus the `block.json` draft). Human-gated `resume` delegates to `specify workflow resume`. The engine environment drops `draft_pr.TOKEN_VARIABLES`.
- `agent.py`: `RECONCILE_STATUS: BLOCKED_*` fails the step in both modes, so the human-gated decomposition stop in the command contract works.
- Both workflow files: the step positions the plan proposes (`scope-gate` → `discover`; `record-scope` → `discover`) exist, and so do the current versions (1.1.0 and 1.0.0).

## Assessment

**Requirement coverage.** Every FR and AC in the spec has a mechanism in the plan. Deterministic checks cover the brief structure and markers, the question round (`open` → recorded round → `answered`), the separation of operator answers from agent assumptions, and AC/IAC traceability. FR markers and edge-case coverage (AC-014 for FRs, AC-019) go to review, which matches the spec's Assumptions.

**Reuse over new machinery.** Recording Autonomous assumptions at the existing `clarification` point (R-03) requires no change to the decision log, record renderer or Draft PR body. The code supports this: zero drafts are allowed, the draft name fits, and reversibility is already enforced. Using a failed validation plus resume for the question round (R-02) follows the documented runner contract. Keeping the answer attribution in operator state follows the `record-intent` defence.

**Authority.** `check_intent` binds only the `spec.md` digest, so the brief cannot invalidate or change intent (AC-017, SC-006). The plan correctly needs no new code for this. The brief declares itself input evidence (AC-018).

**Risk re-check (R-01).** I confirm the R1 reading. The new human-gated read uses the same `gh` resolution, pinned repository and token stripping as the Autonomous start and the Draft PR checkpoint. It reads Issue data and executes or downloads nothing from the standard's fetch path. It changes no agent permission, protected input, launcher trust input or ignore rule. What it does add is untrusted comment text from any GitHub account in the agents' context, in both modes. The snapshot header and FR-005 handle that text as data, and the always-required security review should look at it.

**Fail-closed behavior.** The Autonomous write-boundary check, the operator-state `ran` flag that stops an agent from skipping the spec check by deleting the brief, and the refusal of pre-filled answers all fail closed. One gap is in the AC traceability rule: it only checks lines that already carry an `AC-NNN` ID. See the recorded findings.

**Scope and complexity.** The plan changes one new command, one new check, one extended check, two workflow edits and one runner change. That matches the outcome, with no unrelated refactor. The documentation targets (`templates/policies/spec-kit-workflow.md`, `specs/TECHNICAL-SPEC.md`) are named, so a documentation review will be required at implementation.

<!-- ballast-findings: begin -->
## Findings (recorded from the review draft)

- F-001 (medium, implementation-bug, accepted-provisionally): data-model.md 'Spec traceability' checks only lines with a **AC-NNN** ID. The validator does not require AC IDs today: spec-template.md asks for them only in a comment, and the scenarios are '1. **Given** ...'. So a brief-backed spec whose scenarios have no IDs passes with nothing checked, which fails open against AC-015 and BL-INV-005. Fix while writing tasks, with no design change: once discovery has run, require every acceptance scenario (each Given/When/Then item under 'Acceptance Scenarios') to carry an AC-NNN ID and a marker, and add a failing-when-broken test for a spec with unnumbered scenarios.
- F-002 (low, spec-ambiguity, open): The contract table sets operator-state 'ran' only in the human-gated row, while data-model.md says it is set whenever discovery validates. If an Autonomous validate-discovery does not set it, a later Autonomous agent step could delete discovery.md and skip the spec traceability rule (R-06). Tasks should state that both modes set 'ran'.
- F-003 (low, spec-ambiguity, open): render_issue_snapshot's header says the snapshot was 'written by the Ballast runner at the start of an Autonomous run'. Once human-gated starts also write it, that wording is wrong, and the plan does not list the change. It is a small edit when the renderer gains the comments section.
- F-004 (info, architecture-issue, open): R-01 holds as R1. Adding all Issue comments, including ones from accounts with no repository association, puts more untrusted text in front of agents in both modes. FR-005, the snapshot header and the recorded author_association handle it as data. The always-required security review should confirm that nothing downstream gives that text authority.
<!-- ballast-findings: end -->
