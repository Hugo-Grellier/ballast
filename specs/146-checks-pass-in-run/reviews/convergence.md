# Spec reconciliation: 146-checks-pass-in-run

- Reviewer: claude/claude-opus-5-5 (independent context, same provider as the author; reduced independence)
- Scope: `spec.md` (digest `66574d89…`, equal to `acceptance-evidence.json`'s `spec_digest`), `intent.md`, `plan.md`, `tasks.md`, `decisions.md`, `acceptance-evidence.json`, the run record, and the change since 0bddeb8 (752f88b, b72b578, 4491448), plus the working tree, which changes only the run record and five review reports. This is the re-run after the HD-0002 resume.
- Verdict: CONVERGED

## Method

I read the tool and `ballast.toml` diff against 0bddeb8 and compared it with FR-001..FR-012. I checked that each of the 29 tests named in `acceptance-evidence.json` exists as a method in the named module. I checked the spec digest with `sha256sum`. I compared the policy template and ADR-0021 with FR-013/FR-014. I also read the run record's HD-0002 resolution and its final `run-checks` result. This session could not run unittest or a multi-step shell check (no approval surface). Test results therefore come from the run record and the PD-0023/PD-0027 reviews, which ran ruff and 28 targeted tests.

## What changed since the previous reconciliation (PD-0022)

The implementation did not change. The branch was rewritten into three commits after the operator's HD-0002 resume. The final `run-checks` ran `tests/parallel.py` in-run and exited 1 after 1064 s. The operator classified that as a flake and reported a full parallel run outside the run: 24 modules in 1483 s. That is the first duration for SC-002 and AC-012, but the operator reported it and the runner did not record it.

## Criterion-to-evidence map

| AC | Implementation | Evidence |
| --- | --- | --- |
| AC-001, AC-004 | `autonomy.check_env`: secret filter first, then it drops `BALLAST_GIT`, `RUN_VARIABLES` and guard `PATH` entries (own guard or any `spec_workflow/guard`), keeping order and empty entries | `CheckEnvTests` (both methods), `CheckEnvironmentTests.test_run_commands` |
| AC-002 | `run_commands` is the single caller of `check_env`; acceptance checks stay `read_only` | `CheckEnvironmentTests.test_acceptance_checks` |
| AC-003 | Every check path goes through `run_commands` | `test_feedback_checks`, `test_final_checks_then_acceptance_checks`, `test_project_checks` |
| AC-005 | Same code as AC-001 | bwrap-gated `RealCheckEnvironmentTests` and deferred T021; mapped `[]` per the `decisions.md` wording clarification |
| AC-006 | `agent.GUARD = autonomy.GUARD`; the agent step environment is unchanged | `AgentStepEnvironmentTests…guard`, `HumanGatedSnapshotTests.test_workflow_steps_keep_the_run_variables` |
| AC-007, AC-009 | Each ledger class clears the run variables; `ledger.py` is not in the diff | `IsolationTests` (two methods) |
| AC-008 | `_operator_step_guard` is unchanged | `OperatorStepGuardTests.test_either_run_variable_refuses` |
| AC-010 | `ballast.toml` `timeout_minutes = 60`, applied outside a step with trust re-recorded (HD-0001) | Config diff; mapped `[]` |
| AC-011, AC-013 | No test removed; `tests/parallel.py` globs every module; CI and `AGENTS.md` keep `python -m unittest tests/test_*.py` | `suite-profile.md`, `tests/test_parallel.py`; mapped `[]` |
| AC-012 | `[checks]` runs `tests/parallel.py` (D-001) | Operator-reported 1483 s against 2848 s before (HD-0002); no runner-recorded passing duration (gap 1) |
| AC-014 | Needs this checkout's runner | Deferred T021, still open; this run's v1.0.0 `run-checks` failed once in-run (gap 2) |
| AC-015 | `_timeout_only` and `_timeout_condition` run before the block, limit and fix-state code; `check-timeout` is in `LIMIT_KINDS` with its label and recovery; `_check_timeout_step` re-enters at the feedback checks | `CheckTimeoutLimitTests`, `TimeoutSecondsTests`, `CheckTimeoutBlockTests` (first record, recheck, last cycle, wall-time cut), `ResumeTests` (3) |
| AC-016, AC-017 | `_timeout_only` returns `[]` on a non-timeout failure, a blocking finding or a finding open to fix | `test_a_non_timeout_failure_starts_a_cycle`, `test_an_open_finding_starts_a_cycle`, `test_a_blocking_finding_keeps_the_existing_rules` |
| AC-018 | Final `run_checks` path unchanged | `test_a_final_timeout_still_blocks_as_a_failed_check`. HD-0002's in-run `postcondition` block also shows it. |
| AC-019 | Policy template: runner-contract row, "Check timeout" and "Check environment" paragraphs, resume note | `CheckEnvironmentDocumentTests` policy methods |
| AC-020 | ADR-0021 extends ADR-0018 and ADR-0010 as amended by ADR-0020; ADR-0018 has an "Extended by" note | `test_adr_0021_records_the_boundary` |

FR-011: the minutes come only from `autonomy.parse_checks(load_config(...))` and from the runner's own `timeout_seconds`. FR-012: the new code uses only `os`, `re`, `pathlib` and sibling modules. The non-goals still hold. The diff does not touch the git guard, `confined_argv`, `ledger.py`, `chat.py` or `.github/`.

## Behavior beyond or against the spec

- `tests/parallel.py` as the `[checks]` command follows FR-007's conditional path. The operator accepted it on 2026-10-13, as `decisions.md` D-001 records. This is new knowledge, not a contradiction, and FR-008 holds.
- When the wall time cuts a check, the run records a resumable `check-timeout` block, but the fixed wall-time limit then refuses the resume. The condition says the wall time ran out, so the operator is not misled.
- I found nothing else that exceeds or contradicts the spec.

## Gaps and diagnosis

1. Evidence not yet produced (AC-012, SC-002). The only duration is the operator-reported 1483 s from HD-0002. The PR must present it as operator-reported, or record the runner duration as unavailable, as the spec's assumption allows.
2. Evidence not yet produced (AC-014, SC-001, AC-005). These rest on the deferred T021. The in-run final `run-checks` under the parallel command exited 1, and the repository does not record the failing module. Nothing in the repository shows whether it was the D-002 flake or a parallel-only interaction. The PR should name the failing test from the operator-state output tail.
3. Stale specification. The Assumptions in `spec.md` and `discovery.md` still give the ADR number as 0020; the ADR is 0021. Fixing it changes the spec digest, so the same change must recompute `spec_digest`. Behavior is unaffected.
4. Documentation completeness. The policy's block-category table omits `check-timeout`, although the Check timeout paragraph covers it. The README does not describe the check environment or the timeout bounds. FR-013 is still met.

None of these is a wrong implementation, and none needs an ADR beyond ADR-0021.

<!-- ballast-findings: begin -->
## Findings (recorded from the review draft)

- F-001 (low, missing-test, open): AC-012 and SC-002 have only the operator-reported 1483 s from HD-0002, measured outside the run, against 2848 s before. The PR must present it as operator-reported or record the runner duration as unavailable.
- F-002 (low, missing-test, open): AC-014, SC-001 and AC-005 rest on the deferred T021. The in-run final run-checks under tests/parallel.py exited 1 after 1064 s, and the repository does not record the failing module, so the D-002 flake and a parallel-only interaction cannot be told apart. The PR should name it from the operator-state output tail.
- F-003 (low, spec-ambiguity, open): Stale specification: the Assumptions in spec.md, and discovery.md, still give the new ADR number as 0020; it is 0021. A correction changes the spec digest, so acceptance-evidence.json's spec_digest must be recomputed in the same change. Behavior is unaffected.
- F-004 (info, spec-ambiguity, open): The [checks] test command is tests/parallel.py under FR-007's conditional path and D-001, while CI and AGENTS.md keep the sequential command (FR-008). decisions.md records the choice, so spec.md need not change. The PR should state both commands.
- F-005 (low, spec-ambiguity, open): The policy template's block-category table omits check-timeout, although the Check timeout paragraph documents it, and README.md does not describe the check environment or the timeout bounds. FR-013 is met.
<!-- ballast-findings: end -->
