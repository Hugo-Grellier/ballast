# Architecture review: 146-checks-pass-in-run (specialists, after the run-checks block)

- Reviewer: claude-opus-5-5, independent context (agent-provisional)
- Scope: the change against the branch base `0bddeb8` (commits 752f88b, b72b578, 4491448 and the working tree). Since 4491448, the working tree touches only the run record and the engineering and test reports. The review compared the change with the accepted ADRs and architecture sections it touches: ADR-0004, ADR-0010, ADR-0018, ADR-0020, the constitution invariants the plan cites, and the runner contract in `templates/policies/spec-kit-workflow.md`. ADR-0021 was reviewed as the proposed decision.

## Why this review ran again

The final `run-checks` blocked as `postcondition`. The operator resolved that block as HD-0002, and the run resumed at `validate-implementation`. No architecture-bearing file changed during the block. That HD-0002 path blocked as `postcondition` and not as `check-timeout` confirms in practice that the final `run-checks` path is unchanged (AC-018, FR-010).

## Fit with accepted decisions

- **ADR-0018.** Acceptance checks still run through `run_commands` with a read-only checkout. ADR-0021 changes only the child environment, at that single call site, and `run_commands` is the only caller of `check_env`. ADR-0018 gains an "Extended by" line, and its status and decision text stay unchanged.
- **ADR-0010 and ADR-0020.** Limits are fixed at start, and resume cannot raise them. `check-timeout` is a resumable limit kind outside `FIXED_LIMITS`. Its recovery changes the trusted `[checks] timeout_minutes`, which every checks step re-reads, and does not change a run limit. ADR-0021's `Extends:` line names ADR-0020 as the amendment to ADR-0010. Its Consequences say that `check-timeout` becomes a Draft-PR limit outcome once #153 ships, which matches ADR-0020's Delivery section. The policy's Stop rule paragraph defers to ADR-0020, so the change adds no second source of truth.
- **ADR-0004 and BL-INV-006.** The new block and its recovery claim no approval. ADR-0021 is `proposed`, and the merge is its only acceptance.
- **BL-INV-002 and BL-INV-003.** Nothing the launcher executes moves into a writable checkout. A check loses environment entries and gains none, and it stays inside unchanged bwrap. Agent steps keep the guard and the run variables. The security report covers the `[checks]` command's move to `tests/parallel.py`: the command stays confined project code.
- **One source of truth.** `agent.GUARD` refers to `autonomy.GUARD`. `timeout_seconds` is an additive field on runner-owned results. `[checks]` and CI run the same modules through different entry points, which AC-013 requires, so this does not create a second authority.

## Observations

- ADR-0021 and the policy keep a timed-out final `run-checks` as a `postcondition` block. ADR-0020 makes a failed final `run-checks` a limit outcome once #153 ships. Both hold under ADR-0020's Delivery section, but ADR-0021's Consequences bullet names only the limits. #153 should apply ADR-0020 to the final `run-checks` case directly.
- `spec.md` (Assumptions) and `discovery.md` still number the new ADR 0020. The plan and the ADR use 0021. The plan review left this wording fix to spec reconciliation so that `spec_digest` stays valid.
- `specs/TECHNICAL-SPEC.md` has no status line for #146. ADR-0021 and the policy carry the decision.
- `[checks]` now differs from CI by running modules in parallel. HD-0002 is the first in-run failure under that runner, and the repository does not record its cause. If the cause turns out to be a parallel-only interaction, the per-module isolation that the D-001 choice assumed would need revisiting. Nothing in the reviewed code shows such an interaction.

## Verification

- Read ADR-0004, ADR-0010, ADR-0018, ADR-0020 and ADR-0021. Read the changed functions `check_env`, `run_commands`, `_timeout_only`, `_timeout_condition`, the `record_decision` insertion, `_check_timeout_step` and `_reentry`.
- Confirmed that `CHECK_TIMEOUT = (1, 240, 30)` matches the policy and the ADR, and that `timeout_minutes = 60` falls inside it. Confirmed with `git diff 4491448 --stat` that no architecture-bearing file changed since the last approved review.

<!-- ballast-findings: begin -->
## Findings (recorded from the review draft)

- F-001 (info, architecture-issue, open): ADR-0021 keeps a timed-out final run-checks as a postcondition block, while ADR-0020 makes a failed final run-checks a limit outcome. Both hold until #153 ships under ADR-0020's Delivery section, but ADR-0021's Consequences bullet names only the limits; #153 should cover the final run-checks case from ADR-0020 directly.
- F-002 (info, spec-ambiguity, open): spec.md (Assumptions) and discovery.md still number the new ADR 0020; the plan review left this wording clarification to spec reconciliation so the spec_digest stays valid.
- F-003 (info, spec-ambiguity, open): specs/TECHNICAL-SPEC.md has no status line for #146; ADR-0021 and the policy carry the decision, and spec reconciliation can decide whether one belongs there.
- F-004 (info, architecture-issue, open): HD-0002 is the first in-run failure under the parallel [checks] runner and its cause is not recorded in the repository. If it proves a parallel-only interaction, the per-module isolation D-001 assumed needs revisiting; the reviewed code shows none.
<!-- ballast-findings: end -->
