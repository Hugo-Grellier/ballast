# Plan review: Reach a reviewed PR with provisional Autonomous decisions

- Review: plan (engineering)
- Reviewer: claude/claude-opus-5-5, fresh context, independent of the plan author
- Status: agent-provisional; merging the PR is the only human approval

## What was reviewed

The plan and its Phase 1 artifacts, checked against the approved spec (`spec.md`, provisional intent PD-0013) and the governing policies:

- `plan.md`, `research.md` (R1–R20), `data-model.md`, `contracts/workflow-steps.md`, `contracts/cli-commands.md`, `contracts/draft-retry.md`, `quickstart.md`.
- `spec.md` (AC-001 to AC-033, FR-001 to FR-027, edge cases, assumptions) and `intent.md`.
- `AGENTS.md`, `docs/policies/workflow.md` (review matrix, three-cycle rule, supervision modes), `docs/policies/project/workflow.md` (R2 boundaries), the engineering review skill.
- `docs/adr/0004-autonomous-provisional-decisions.md` (the continuation rule the plan amends).
- `tasks.md` and `decisions.md` do not exist yet; this review precedes task generation.

## How the plan was checked

Claims in the plan were compared against the current code rather than taken on trust:

- **Step budget (R9).** `templates/spec-kit/workflows/autonomous/workflow.yml` 1.1.0 has 18 `command:` steps, matching the plan. Three fix cycles add 9 agent steps, so 27 on the designed path; the 30 → 40 default change follows from the spec's assumption that the plan checks the default. No installed doc states the old default, so nothing goes stale.
- **Fix-input confidentiality (R3).** `agent.py` `_protected_state` hashes all of `.specify/` except `feature.json` and two caches (`SPECIFY_WRITABLE`), so `.specify/workflow-state/fix-input/` is read-only to agents, as with the existing required-reviews file. The claim holds.
- **Baseline scope (R6, R10).** `record_baseline` writes under `.specify/workflow-state/<key>/` and `Feature` is keyed by the run ID, so "keep an existing baseline" is per run and cannot pick up another run's baseline.
- **Dispositions (R2).** `autonomy.DISPOSITIONS` already includes `resolved`, which the recheck contract relies on. `_check_dispositions` today allows `open` only for `low`/`info`. The plan permits `open` at any severity while a cycle remains. That is a conditional exception, not a pass-through: any open medium-or-higher finding forces a fix, and the strict rule applies again on the last review. The security specialist should confirm this reading of FR-017.
- **Checkpoint (R12).** `draft_pr.checkpoint` records a ledger event and publishes a packet only when the outcome is not `skipped`, and `_Checkpoint.settle()` returns `None` when no PR exists. A `create=False` switch that ends `skipped`/`no-draft-pr` therefore writes nothing, which is what AC-025 needs.
- **Human decision kind (FR-010).** `block-resolution` is already in `autonomy.HUMAN_DECISION_KINDS`, so the schema needs no change.
- **Continuation rule.** ADR-0004 states that a blocked run cannot resume autonomously until #18. The plan does not edit that decision in place. It proposes ADR-0007, adds an "Amended by" line and updates the workflow policy template, which matches FR-015 and the requirement to write a new ADR for an accepted architecture change.
- **Authority.** The plan changes no `claude-settings.json`, `CONFINED_ALLOW`/`CONFINED_DENY` or sandbox flags. Resume refuses mode, limit and integration flags, never writes mode or limits, and refuses `agent-steps`/`wall-time` limit blocks. The new `stopped → active` transition requires a `block-resolution` decision. Refusals write nothing. These hold FR-003, FR-012, FR-013, FR-026 and BL-INV-003/006.
- **Engine assumption (R7).** Repositioning the engine's `state.json` is unverified. The plan makes T001 verify it with the real CLI first and names a fallback, which goes to `decisions.md` as a proposal rather than being adopted silently. That is the right way to handle the risk.
- **Coverage.** Every AC maps to a quickstart scenario. Scenario 30 covers AC-005/FR-006, and scenario 26 checks that permissions are unchanged. The R2 risk class and the required reviews (engineering, security, test, documentation, architecture) match the review matrix and the project's R2 boundaries.

## Gaps noted for tasks and implementation

Three issues remain open. None blocks the plan decision, and the draft records each with a provisional disposition:

1. AC-007/FR-004 require the provisional intent to cite the discovery brief. Nothing in `artifacts.py` or `autonomy.py` enforces this today; it holds in this run only because the agent chose to cite `discovery.md` in PD-0013's evidence. The Repository Impact table lists no recorder change. Quickstart scenario 29 says it will "extend existing tests to assert the brief citation", but without a code change those tests would only exercise agent wording.
2. The workflow contract sets `fix_cycle = N` from the slot number of `record-fix-review-N`. R1 states that the bound is the persisted counter `fix.cycles`, never the slot. After a resume that re-enters at or before `record-implementation-review` with cycles already spent, slot 1 can carry cycle 2 or 3, so the record's "Fix loop" section (AC-004) would label the cycle wrongly.
3. R13 takes a non-blocking `flock` in `start`, Autonomous `resume`, `publish` and `checkpoint`, and `resume`/`start` publish through `_finish`. `flock` locks belong to the open file description, so a second open-and-lock in the same process fails. The lock must be taken once at CLI entry and not again on the internal publish path.

Smaller observations that need no action: `contracts/draft-retry.md` promises that validator messages carry no draft content, but some current messages (for example on evidence paths) echo agent-supplied values. Since the text only returns to the same agent, the 500-character, printable-only bound is enough. A run started under v0.6.x has no lock file, so resume treats a live old invocation as interrupted. That is acceptable for an upgrade edge case.

<!-- ballast-findings: begin -->
## Findings (recorded from the review draft)

- F-001 (medium, missing-test, accepted-provisionally): AC-007/FR-004 require the provisional intent to cite the discovery brief, but no recorder enforces it today; it holds in this run only because the agent cited discovery.md in PD-0013. The Repository Impact table lists no recorder change, and quickstart scenario 29 only extends tests. Acceptable for now because tasks can add a check in the intent recorder that the discovery brief appears in the intent evidence, with a negative test, before implementation review.
- F-002 (medium, spec-ambiguity, accepted-provisionally): The workflow-steps contract sets fix_cycle = N from the slot of record-fix-review-N, while R1 says the bound is the persisted fix.cycles counter, never the slot. After a resume that resets the fix state but keeps the cycles spent, slot 1 can hold cycle 2 or 3, so the record's Fix loop section (AC-004) would mislabel the cycle. Acceptable for now because tasks can define fix_cycle as fix.cycles at record time and test it on a resumed run; the bound itself is unaffected.
- F-003 (low, implementation-bug, open): R13 takes a non-blocking flock in start, resume, publish and checkpoint, and start and resume publish through _finish. A second open-and-lock in the same process fails, so the lock must be taken once at CLI entry and not again on the internal publish path. A test should cover resume reaching publish.
<!-- ballast-findings: end -->
