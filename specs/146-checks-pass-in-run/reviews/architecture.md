# Architecture review: 146-checks-pass-in-run (specialists)

- Reviewer: claude-opus-5-5, independent context (agent-provisional)
- Scope: the change since the branch start `617df9c` (commits `fa1eefe` and `bd80a3e` and the uncommitted T031–T033 edits), compared with the accepted ADRs and architecture sections it touches: ADR-0004, ADR-0010, ADR-0018, ADR-0020 (now on `main` after the rebase), the constitution invariants the plan cites, and the runner contract in `templates/policies/spec-kit-workflow.md`. ADR-0021 is reviewed as the proposed decision.

## Fit with accepted decisions

- **ADR-0018.** Acceptance checks already ran through `run_commands` with a read-only checkout. ADR-0021 keeps that confinement and changes only the child environment at the single call site, `run_commands`, which is the only caller of `check_env`. ADR-0018 gains an "Extended by" line, and its status and decision text are unchanged.
- **ADR-0010.** Limits are fixed at start and resume cannot raise them. `check-timeout` is a new resumable limit kind outside `FIXED_LIMITS`. Its recovery raises `[checks] timeout_minutes`, a trusted `ballast.toml` setting that every checks step re-reads, not a run limit. So "raise it, `ballast trust`, resume" fits "resume refuses limit flags". The `_reentry` override applies only to a `limit` block of kind `check-timeout`, and an earlier changed input still wins.
- **ADR-0020.** The rebase brought in ADR-0020, which amends ADR-0010 and turns every limit into a Draft-PR limit outcome once #153 ships. Its Delivery section keeps ADR-0010's limits as written until then. ADR-0021 now names ADR-0020 in its `Extends:` line and adds a Consequences bullet saying that `check-timeout` becomes a limit outcome too, which settles the second plan review's F-001 (T031, asserted by T032). The policy's Stop rule paragraph already defers to ADR-0020, so no second source of truth is added.
- **ADR-0004 and BL-INV-006.** The new block and its recovery claim no approval, and ADR-0021 is `proposed` with the merge as its only acceptance.
- **BL-INV-002 and BL-INV-003.** Nothing the launcher executes moves into a writable checkout. A check loses environment entries and gains none, inside unchanged bwrap, and agent steps keep the guard and the run variables. The `[checks]` command change to `tests/parallel.py` keeps checks as confined project code, as before. See the security report.
- **One source of truth.** `agent.GUARD` refers to `autonomy.GUARD`. `timeout_seconds` is an additive field on runner-owned results. `[checks]` and CI now run the same modules through different entry points (parallel per module versus one process). AC-013 requires CI to keep the sequential command, so this is intended, not a second authority.

## Observations

- ADR-0021 and the policy keep a timed-out final `run-checks` as a `postcondition` block. ADR-0020 says a failed `[checks]` command is not a `postcondition` and makes a failed final `run-checks` a limit outcome. Both hold, because ADR-0020's Delivery keeps today's behavior until #153 ships. But ADR-0021's new Consequences bullet names only the limits. When #153 lands it should treat the final `run-checks` case as ADR-0020 says, without needing ADR-0021 changed.
- `spec.md` line 173 and `discovery.md` line 132 still say the new ADR is 0020. The second plan review (F-002) left that wording to spec reconciliation, so `spec_digest` stays valid. The plan and ADR use 0021 correctly.
- `specs/TECHNICAL-SPEC.md` has status lines for earlier runner changes but none for #146. ADR-0021 and the policy carry the decision, and spec reconciliation can decide whether a status line belongs there.
- The repository still has two ADRs numbered 0019. That predates this change.

## Verification

- Read ADR-0004, ADR-0010, ADR-0018, ADR-0020 and ADR-0021, and the changed functions `check_env`, `run_commands`, `_timeout_only`, `_timeout_condition`, the `record_decision` insertion, `_check_timeout_step` and `_reentry`, plus `resumable` and `FIXED_LIMITS` in `autonomy.py`.
- Confirmed that `CHECK_TIMEOUT = (1, 240, 30)` matches the bounds in the policy and ADR, and that `timeout_minutes = 60` is within them.

<!-- ballast-findings: begin -->
## Findings (recorded from the review draft)

- F-001 (info, architecture-issue, open): ADR-0021 keeps a timed-out final run-checks as a postcondition block, while ADR-0020 makes a failed final run-checks a limit outcome. Both hold until #153 ships under ADR-0020's Delivery section, but ADR-0021's new Consequences bullet names only the limits; #153 should cover the final run-checks case from ADR-0020 directly.
- F-002 (info, spec-ambiguity, open): spec.md line 173 and discovery.md line 132 still number the new ADR 0020; the second plan review left this wording clarification to spec reconciliation so the spec_digest stays valid.
- F-003 (info, spec-ambiguity, open): specs/TECHNICAL-SPEC.md has status lines for earlier runner changes but none for #146; ADR-0021 and the policy carry the decision, and spec reconciliation can decide whether a status line belongs there.
<!-- ballast-findings: end -->
