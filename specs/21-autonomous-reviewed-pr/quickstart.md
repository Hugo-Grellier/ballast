# Quickstart: validating Autonomous review, fix, resume, retry and refresh

How to prove the feature works end to end. Test names are the planned ones. The interfaces are in [contracts/](contracts/) and the records in [data-model.md](data-model.md).

## Prerequisites

- Fast gate: Python 3.13 via `uv`, and `pyyaml` for the workflow-file tests.
- Full local gate: Linux with a systemd user session, bubblewrap, the Spec Kit CLI (`specify` ≥ 1.0.11) and the Codex CLI. Only these tests exercise the real engine (R7, T001) and real confinement.

```bash
uvx ruff check && uvx ruff format --check
uv run --no-project --python 3.13 --with pyyaml python -m unittest tests/test_*.py
```

Expected: every test passes. On a host without the full-gate tools, only the existing skips plus the new real-engine scenarios are skipped, each with its reason.

## Scenarios

Unless marked *real engine*, every scenario runs offline with the fake agent and fake `specify` fixtures already used by `tests/test_autonomous_run.py`, a temporary Git repository and a bare `origin`.

| # | Scenario | Planned test | Proves |
| --- | --- | --- | --- |
| 1 | *Real engine*: a fixture run fails at a recorder; `state.json` is repositioned two steps back; `specify workflow resume` runs the earlier step next | `test_spec_workflow.EngineRepositionTests` | R7 holds (T001) |
| 2 | R1 fixture feature; implementation review returns a medium `open` finding; one fix cycle runs; recheck approves; `run-checks` passes; Draft PR published; no prompt; record and packet list the cycle | `test_autonomous_recovery.FixLoopTests.test_medium_finding_one_cycle_then_publish` | AC-001, AC-002, AC-004, SC-001 (offline part) |
| 3 | A high finding persists through three cycles | `…test_high_finding_after_three_cycles_blocks_limit` | AC-003, FR-002 |
| 4 | Feedback checks fail after implement; the fix input lists the failure; the fix step runs; agent settings and allowed tools unchanged | `…test_check_failure_reaches_fix_input_only` | AC-006, FR-003 |
| 5 | Clean review: every cycle step skips without counting a step; a 1.1.0 workflow copy with findings blocks as before | `…test_idle_cycles_skip`, `…test_old_workflow_copy_blocks` | R1, R19 |
| 6 | Block at `decide-tasks`; base advances; `resume` syncs, records HD `block-resolution`, re-enters at `decide-tasks`, completes | `ResumeTests.test_pre_implementation_block_resumes` | AC-008, AC-010, SC-004 |
| 7 | Block after implementation; base advances; sync runs before any agent step; the run continues | `…test_post_implementation_block_syncs_first` | AC-009, SC-004 |
| 8 | Spec edited and committed during a block at `record-tasks` | `…test_changed_spec_reenters_at_validate_spec` | AC-012, FR-009 |
| 9 | Protected input changed during the pause, and during sync | `…test_protected_input_fails_closed` | AC-013 |
| 10 | Pin without `feature` | `…test_unpinned_run_blocks_with_manual_step` | AC-014 |
| 11 | `resume` of a lowered run | existing `test_resume_of_continued_run_refused` | AC-015 |
| 12 | `resume -i integration=codex`, `--mode`, `--wall-time`; mode, risk, limits and integrations byte-identical after a resume | `…test_resume_keeps_mode_and_limits` | AC-016, AC-029, SC-003 |
| 13 | `continue` of a pre-implementation block refused; post-implementation `continue` unchanged | `ContinueTests.test_pre_implementation_continue_points_to_resume` + existing continue tests | AC-011 |
| 14 | Finding reason of 1001 characters, then a valid draft | `RetryTests.test_overlong_reason_retried_then_recorded` | AC-017, SC-005 |
| 15 | Draft keeps failing; also a draft refused when the step limit is reached | `…test_retries_exhausted_blocks_limit`, `…test_step_limit_during_retry` | AC-018 |
| 16 | High finding at plan review, tamper, contradiction draft, ineligible risk: no retry | `…test_state_refusals_not_retried` | AC-019 |
| 17 | Basis quoting "approved by the operator" is refused and retried; the command files state the limits and the paraphrase rule | `…test_quoted_approval_retried`, `test_governance.CommandWordingTests` | AC-020, AC-021 |
| 18 | Installed tasks template forbids workflow-owned tasks; `check_implementation` unchanged | `test_governance.TasksTemplateTests` + existing implementation tests | AC-022 |
| 19 | `checkpoint` of a published run after a new ledger check: PR section and packet updated; `run.json`, `decisions.jsonl` and `human-decisions.jsonl` byte-identical; no agent ran | `CheckpointTests.test_refresh_published_run` | AC-023, AC-024, SC-007 |
| 20 | `checkpoint` with no Draft PR, with a human-gated run, and with the lock held | `…test_refusals_write_nothing` | AC-025 |
| 21 | One block per class, each with a class, a reason and a `Next:` command | `BlockClassTests` | AC-026, FR-023, SC-003 |
| 22 | Run paused for a simulated 10 hours, resumed within budget; a step still stops at the limit; a crashed invocation does not count its downtime | `ActiveTimeTests` | AC-027 |
| 23 | Steps, retries and fix cycles all increment `agent_steps`; the record states that monetary spend is not measured | `…test_every_attempt_counts`, record render test | AC-028, FR-022 |
| 24 | Fix, retry, resume and refresh artifacts presenting a provisional decision as accepted are refused | `ProvisionalGuardTests` | AC-030 |
| 25 | Policies and README describe resume, fix loop, retries and refresh as agent-provisional, with merge as the single human approval | `test_governance.PolicyWordingTests` | AC-031 |
| 26 | Human-gated workflow tests unchanged; `claude-settings.json` and `CONFINED_ALLOW` unchanged | existing suites + `test_governance.PermissionsUnchangedTests` | AC-032, SC-006 |
| 27 | No new `gh`/`git` write commands; the PR stays Draft | argv-log assertions in scenarios 2 and 19 | AC-033 |
| 28 | `AUTONOMOUS_STEPS` equals the template's step IDs | `test_autonomy.StepOrderTests` | R6 |
| 29 | Provisional intent cites the discovery brief and the spec | existing #16 and #27 intent tests, extended to assert the brief citation | AC-007, FR-004 |
| 30 | Every check, required review, validator and postcondition of the human-gated workflow is present in `ballast-autonomous` | existing gate-structure comparison, extended for 1.2.0 | AC-005, FR-006 |

## Live pilot (operator, after merge)

SC-001 also needs a live run. Pin a scratch project to the merge commit (or the next release). Start a bounded R1 Issue with `ballast run start --mode autonomous -i issue=N …` and let it run without intervention. Then check that:

1. no approval prompt appeared;
2. the Draft PR's record shows the reviews, any fix cycles, `run-checks` and every provisional decision;
3. `ballast run checkpoint RUN_ID` after `ballast ledger check` updates only the PR section and packet.

The PR records this pilot as pending until it is done. The fast gate and full local gate results are recorded in the PR (SC-008).
