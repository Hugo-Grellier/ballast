# Decisions

## DEC-0001 — Proposal

- **Found during**: implementation of T025 (`ResumeEngineTests`, real engine), 2026-10-06, after the Autonomous run `fcba2ba4` stopped and the driving agent implemented the tasks by hand.
- **Conflict**: SC-004 asks for tests that resume a pre-implementation and a post-implementation block "after the base advances, each reaching its next step without a prompt", and AC-009 says such a resume "continues Autonomous or blocks with an actionable reason". An Autonomous run keeps its artifacts (spec, plan, tasks, code) uncommitted until the trusted runner publishes them. When the base advanced during the pause, branch synchronization must rebase the feature branch, and #18 (FR-006, ADR-0005) never stashes, commits or discards uncommitted changes: it blocks with cause `dirty` and the recovery "commit or finish these changes (Ballast never stashes or discards them), then ballast run resume RUN_ID". So a resume after the base advanced always blocks once, actionably, before it can continue.
- **Label**: spec ambiguity (SC-004 does not say whether the operator's documented `dirty` recovery may come between the base advancing and the resume that reaches the next step).
- **Options**:
  1. Keep #18's rule. The first resume blocks as `upstream-sync` (`dirty`) with its recovery and records no human decision; the operator commits the paused run's work on the feature branch and resumes again, and the run continues in Autonomous. Document it in the policy.
  2. Let the trusted runner commit the paused run's work before synchronizing. This changes #18's FR-006 and ADR-0005 (an accepted architecture decision), so it needs its own ADR and is out of this feature's scope.
- **Needs**: a resolution before the resume tests are final.

## DEC-0001 — Resolution

- **Status**: resolved by the driving agent (claude/claude-opus-5-5) under the operator's standing authority for v1.0 issues (2026-10-05); listed in the PR for merge review. The operator has not reviewed this option individually. Option 1.
- **Resolution**: #18's rule holds. A resume after the base advanced first blocks as `upstream-sync` with cause `dirty`, the block names `ballast run resume RUN_ID`, keeps the block-time input snapshot of the block it replaced, and records no human decision. After the operator commits the paused run's work on the feature branch, the next resume synchronizes, records the `block-resolution` and continues in Autonomous. Publication still commits whatever remains, and every tree digest the run compares (frozen tree, checked tree, re-entry inputs) is taken from the working tree, so the operator's commit changes none of them.
- **Rationale**: AC-009 allows an actionable block; option 2 would weaken an accepted safety rule of ADR-0005 without an ADR.
- **Changed now**: the "Resume" section of `templates/policies/spec-kit-workflow.md` states the `dirty` case and its recovery; `ResumeEngineTests.test_pre_implementation_block_resumes` and `test_post_implementation_block_syncs_first` follow the recovery (`commit_work`) and assert the first, blocked attempt. No spec requirement changes; SC-004 is met after the documented recovery.
- **Tests**: `tests/test_autonomous_recovery.py` `ResumeEngineTests` (both base-advance cases) and `ResumeTests.test_unpinned_run_blocks_with_manual_step` (a resume of the resume's own synchronization block).
