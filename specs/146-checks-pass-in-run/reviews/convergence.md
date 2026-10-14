# Spec reconciliation: 146-checks-pass-in-run

- Reviewer: claude/claude-opus-5-5 (independent context, same provider as the author; reduced independence)
- Scope: `spec.md` (digest `66574d89…`, unchanged and equal to `acceptance-evidence.json`'s `spec_digest`), `intent.md`, `plan.md`, `tasks.md`, `decisions.md`, `suite-profile.md`, `acceptance-evidence.json`, the run record, and the change since 617df9c: the two branch commits plus the uncommitted T031/T032 edits to ADR-0021 and `tests/test_governance.py`.
- Verdict: CONVERGED

## Method

I mapped each acceptance criterion to the code that implements it and to an executable test. I read the tests' bodies, not only their names, and grepped every test that `acceptance-evidence.json` names. All 29 exist in the class the manifest names. I checked the spec digest with `sha256sum`. I compared `tools/spec_workflow/*` against FR-001..FR-012, checked the policy template and ADR-0021 against FR-013/FR-014, and grepped `README.md`, `AGENTS.md`, `specs/TECHNICAL-SPEC.md` and `specs/PRODUCT-SPEC.md` for stale or missing statements. This session could not run unittest or a Python helper (no approval surface). The test results cited below therefore come from the run record's feedback checks (`tests/parallel.py` exited 0) and from reading the tests.

## Criterion-to-evidence map

| AC | Implementation | Evidence |
| --- | --- | --- |
| AC-001 | `autonomy.check_env` (secret filter, then drops `BALLAST_GIT`, `RUN_VARIABLES` and guard `PATH` entries); `run_commands` uses it; `confined_argv` still gets the operator env | `CheckEnvTests.test_guard_entries_and_run_variables_are_removed`, `CheckEnvironmentTests.test_run_commands` (env equals `check_env`, argv built from the operator env, `GITHUB_TOKEN` dropped) |
| AC-002 | `_acceptance_checks` → `run_commands(read_only=True)` | `CheckEnvironmentTests.test_acceptance_checks` (`writable_checkout=False`) |
| AC-003 | Every check path goes through `run_commands` | `test_feedback_checks`, `test_final_checks_then_acceptance_checks`, `test_project_checks` |
| AC-004 | `PATH` filter keeps order and empty entries; unset/empty kept as-is | `CheckEnvTests` (both methods) |
| AC-005 | Same code as AC-001 | `RealCheckEnvironmentTests` (bwrap-gated, not runnable nested); mapped `[]`, per the wording clarification in `decisions.md` |
| AC-006 | `agent.GUARD = autonomy.GUARD`; `_base_env`, `run._environment` unchanged | `AgentStepEnvironmentTests…guard`, `HumanGatedSnapshotTests.test_workflow_steps_keep_the_run_variables` |
| AC-007, AC-009 | `_clear_run_variables` in each ledger `setUp`; `ledger.py` absent from the diff | `IsolationTests` (in-process per class, plus a child process with both variables, including the self-patching forge test) |
| AC-008 | `_operator_step_guard` unchanged | `OperatorStepGuardTests.test_either_run_variable_refuses` (each variable alone and both, the guard and `_check`) |
| AC-010 | `ballast.toml` `timeout_minutes = 60`, done by the driving agent in bd80a3e with `ballast trust` (HD-0001) | Deferred operator task T020, done; mapped `[]` |
| AC-011, AC-013 | No skip added except the bwrap gate; no test removed; `uv.lock`, `pyproject.toml` and `ci.yml` unchanged; `tests/parallel.py` globs every `tests/test_*.py` | `suite-profile.md` diff checks and the before/after counts (1608 → 1643); mapped `[]` |
| AC-012 | `tests/parallel.py` (4 jobs) is now the `[checks]` command (D-001, accepted by the operator on 2026-10-13 per `decisions.md`) | Feedback checks passed under 60 min; no operator-machine duration recorded yet (gap 2) |
| AC-014 | Needs this checkout's runner | Deferred T021, open (gap 3) |
| AC-015 | `_timeout_only` / `_timeout_condition`; rule placed before `if rule == "block"`, gated on `implementation-review` and `fix_loop`; `check-timeout` in `LIMIT_KINDS` and not in `FIXED_LIMITS`; `_reentry` maps to the feedback checks step | `CheckTimeoutLimitTests`, `TimeoutSecondsTests`, `CheckTimeoutBlockTests` (a)–(d), with the fix state and cycle count asserted unchanged on first record, recheck and last cycle; `ResumeTests` (3 cases) |
| AC-016 | `_timeout_only` returns `[]` when any failure did not time out | `test_a_non_timeout_failure_starts_a_cycle` |
| AC-017 | `_blocking` / `_open_to_fix` short-circuit | `test_an_open_finding_starts_a_cycle`, `test_a_blocking_finding_keeps_the_existing_rules` (as clarified in `decisions.md`) |
| AC-018 | Final `run_checks` path untouched | `test_a_final_timeout_still_blocks_as_a_failed_check` (`postcondition`) |
| AC-019 | Policy template: "Check timeout" and "Check environment" paragraphs, runner-contract rows, resume note | `CheckEnvironmentDocumentTests` policy methods |
| AC-020 | ADR-0021 (extends ADR-0018 and ADR-0010 as amended by ADR-0020); "Extended by" note added to ADR-0018 | `test_adr_0021_records_the_boundary`, including the T032 `0020-autonomous-stop-rule.md` / `#153` assertions |

FR-012: `check_env`, the limit tables and `_check_timeout_step` use only `os`, `re`, `pathlib` and sibling modules. FR-011: `_timeout_condition` reads minutes only from `autonomy.parse_checks(load_config(...))`, and the per-result `timeout_seconds` comes from the runner's own feedback record. Out of scope and untouched, as the non-goals and the Notes in `tasks.md` require: the guard, `confined_argv`, `parse_checks`, `chat.py`, `ledger.py` and CI.

## Behavior beyond or against the spec

- `tests/parallel.py` and the `[checks]` command change go beyond the spec's literal text. The spec allows them conditionally (FR-007, "only if still needed"), T023/T024 showed the condition was met, and D-001 records the operator's choice. This is new knowledge, not a contradiction. `python -m unittest tests/test_*.py` remains CI's whole-suite command (FR-008).
- In the wall-time edge, `check-timeout` is recorded as resumable while the run's fixed wall-time limit then refuses at the next step. The condition text says the wall time ran out, so the operator is not misled. The test review already carries this, and it does not contradict AC-015.
- I found nothing else that exceeds or contradicts the spec.

## Gaps and diagnosis

1. Stale specification: the Assumptions in `spec.md` say the new ADR takes number 0020, and `discovery.md` says the same. After the rebase it is 0021. ADR-0021, the tests and `tasks.md` are right. Correcting `spec.md` changes its digest, so the change must also recompute `acceptance-evidence.json`'s `spec_digest` and renew provisional intent. Leaving the wording as is costs nothing in behavior.
2. Evidence not yet produced: AC-012 and SC-002 rely on the operator-machine `seconds` of this run's `run-checks`, which has not run yet. The PR must quote it next to 2848 s, or record it as unavailable, as the spec's assumption allows.
3. Deferred by design: AC-005, AC-014 and SC-001 rely on T021, which runs on this checkout's runner or a release. This run's v1.0.0 `run-checks` is not evidence of FR-001.
4. Documentation completeness: the block-category table in the policy template does not list `check-timeout`, although the new paragraph documents it. `specs/TECHNICAL-SPEC.md` has no runner-check content, so it needs no status line.

None of these is a wrong implementation, and none needs a new ADR beyond ADR-0021.

<!-- ballast-findings: begin -->
## Findings (recorded from the review draft)

- F-001 (low, spec-ambiguity, open): Stale specification: the Assumptions in spec.md (and discovery.md) still say the new ADR is 0020; after the rebase it is 0021. Correcting spec.md changes its digest, so acceptance-evidence.json's spec_digest must be recomputed and provisional intent renewed in the same change. Behavior is unaffected.
- F-002 (low, missing-test, open): AC-012 and SC-002 (under 45 min, lower than 2848 s) have no measured duration yet: run-checks has not run, and suite-profile.md's sandbox seconds are not comparable. The PR must quote the run-checks seconds or record them as unavailable.
- F-003 (info, missing-test, open): AC-005, AC-014 and SC-001 are deferred by design to T021 on this checkout's runner or a release; this run's v1.0.0 run-checks is not evidence of FR-001, and the PR must say so.
- F-004 (info, spec-ambiguity, open): New knowledge: the [checks] test command is now tests/parallel.py (D-001). spec.md allows this only conditionally, under FR-007, and does not name it. decisions.md records the decision, so the spec need not change. The PR should state both commands.
- F-005 (low, spec-ambiguity, open): The policy template's block-category table lists the limit forms without check-timeout, although the new Check timeout paragraph documents it. FR-013 is met; the table is incomplete.
<!-- ballast-findings: end -->
