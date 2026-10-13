# Architecture review: 146-checks-pass-in-run (specialists)

- Reviewer: claude-opus-5-5, independent context (agent-provisional)
- Scope: the diff against `d215a63`, compared with the accepted ADRs and architecture sections it touches: ADR-0018 (runner-recorded acceptance checks), ADR-0010 (resume and bounded recovery), ADR-0004 (provisional decisions), the constitution invariants BL-INV-002, BL-INV-003 and BL-INV-006, and the workflow runner contract in `templates/policies/spec-kit-workflow.md`. New ADR-0021 is reviewed as the proposed decision.

## Fit with accepted decisions

- **ADR-0018.** Acceptance checks already ran through `run_commands` with a read-only checkout. ADR-0021 keeps that confinement and changes only the child environment at the single call site. ADR-0018 gains an "Extended by" line, and its status and decision text are untouched. One rule in one place is the design ADR-0021 picks over per-caller filtering, and it is visible in the code: `run_commands` is the only caller of `check_env`.
- **ADR-0010.** Limits are fixed at start, and resume cannot raise them. `check-timeout` is a new resumable limit kind that is not in `FIXED_LIMITS`. Its recovery is to raise `[checks] timeout_minutes`, which is not a run limit under ADR-0010: it is a `[checks]` setting, which `run_checks` reads live from the protected `ballast.toml` on every checks step (`artifacts.py` reads `parse_checks(load_config(...))` at each call). So "raise it, `ballast trust`, resume" is consistent with "resume refuses limit flags": the operator changes a trusted input through trust, not a run limit through resume. The re-entry override in `_reentry` applies only to a `limit` block of kind `check-timeout` and still lets an earlier changed input win.
- **ADR-0004 / BL-INV-006.** The new block and its recovery claim no approval, and the ADR is `proposed` with the merge as its only acceptance. That matches how ADR-0019 was handled.
- **BL-INV-002 / BL-INV-003.** Nothing the launcher executes moves into a writable checkout. A check loses environment entries and gains none, inside unchanged bwrap. Agent steps keep the guard and run variables. See the security report for the authority argument.
- **Second source of truth.** `agent.GUARD` now refers to `autonomy.GUARD`, so the agent environment and the check filter read one value. `timeout_seconds` is an additive field on runner-owned results, and the run record and feedback log remain the source of check outcomes.

## Observations

- The fix-loop text in the policy and ADR-0010 says that after the third cycle a failed check blocks as `fix-cycles`. A timeout-only failure now blocks earlier as `check-timeout`. The policy's new **Check timeout** paragraph and ADR-0021 record that refinement, so no conflict with an accepted decision is left unrecorded.
- The repository has two ADRs numbered 0019. ADR-0021 takes the next free number. That duplicate predates this change and is out of scope.
- `specs/TECHNICAL-SPEC.md` carries status lines for earlier runner changes (#20, #55) but none for #146. The ADR and the policy are the authority for this boundary, and spec reconciliation can decide whether a status line belongs there.

## Verification

- Read ADR-0004, ADR-0010, ADR-0018, ADR-0021, the constitution references in `plan.md`, and the changed functions `check_env`, `run_commands`, `_timeout_only`, `_timeout_condition`, the `record_decision` insertion and `_reentry`/`_check_timeout_step`.
- Confirmed that `CHECK_TIMEOUT = (1, 240, 30)` matches the bounds the policy and ADR state.

<!-- ballast-findings: begin -->
## Findings (recorded from the review draft)

- F-001 (info, spec-ambiguity, open): specs/TECHNICAL-SPEC.md has status lines for earlier runner changes (#20, #55) but none for #146; ADR-0021 and the policy carry the decision, and spec reconciliation can decide whether a status line belongs there.
<!-- ballast-findings: end -->
