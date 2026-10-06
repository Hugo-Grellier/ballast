# Review: implementation (tests and acceptance evidence)

- Role: test reviewer
- Agent/model: claude/claude-opus-5-5, the driving agent; reduced independence (see the security review)
- Base: `1176309..bf5359c`
- Artifacts: [spec.md](../spec.md), [quickstart.md](../quickstart.md), [tasks.md](../tasks.md), `tests/test_setup.py`, `tests/test_ballast.py`, `tests/test_preview.py`, `tests/test_spec_workflow.py`, `tests/test_doctor.py`, `docs/policies/testing.md`, `docs/policies/project/testing.md`
- Verdict: approved

## Criterion to evidence

| Criterion | Evidence |
|---|---|
| AC-001 | `test_failed_stages_keep_the_previous_installation` (fetch core/intent); `CacheTests.test_failed_download_leaves_nothing` (missing and truncated archive) |
| AC-002 | same test: every Spec Kit step (init, integration install, bundle install, extension add, preset add, workflow add) and both patches; T028 live patch failure |
| AC-003 | `test_invalid_stage_is_never_switched` (required output, stage path, unexpected output, ENOSPC, un-ignored path); `test_linked_work_area_is_refused` |
| AC-004, SC-001 | `test_killed_setup_is_recovered` (5 points incl. a dropped entry), `test_kill_during_rollback_is_recovered`, `test_switch_and_stage_failures_keep_the_previous_installation`; T028 live `kill -9` |
| AC-005 | `TrustedLauncherTests.test_unfinished_setup_is_refused`, `test_running_setup_is_reported_as_running`; kill test asserts `run` refuses |
| AC-006 | every failure/kill test compares checkout (incl. constitution, `docs/policies/project/`, run state), run archives and operator state snapshots |
| AC-007, SC-002 | `test_failure_at_an_unchanged_pin_keeps_trust`; T028 live |
| AC-008 | `test_changed_pin_names_both_versions`, `TrustedLauncherTests.test_pinned_and_installed_versions_differ`, `NotFetchedTests`, `ProjectTests.test_pinned_and_installed_versions_are_named` |
| AC-009, SC-004 | `SetupLockTests.test_second_setup_is_refused_and_a_dead_holder_is_recovered`, `test_concurrent_setups_never_interleave` (20) |
| AC-010, SC-004 | `CacheTests.test_concurrent_fetches_download_once` (20 races, one download each) |
| AC-011 | `SetupLockTests` (killed setup holder), `CacheTests.test_dead_fetch_holder_does_not_block` |
| AC-012, SC-003 | `NoOpTests.test_rerun_changes_nothing` (< 5 s, downloads denied); `CacheTests.test_fetch_publishes_the_tree_with_its_record` (verified copy, no download) |
| AC-013, SC-005 | `CacheTests.test_damage_is_detected_and_refetched` (missing, added, altered, mode, no record; refusal when refetch fails) |
| AC-014, SC-005 | `WorktreeCopyTests` (verified copy; altered, added, removed file; three fallbacks) |
| AC-015 | `SetupLockTests.test_running_workflow_command_is_named`, `test_unfinished_agent_step_is_refused`; `test_workflow_tool_keeps_the_shared_lock` |
| AC-016 to AC-021, SC-006 | `tests/test_preview.py` (report/JSON, runs, paths against an actual update of a copy, ignore impact, steps, snapshots for successful/failed/refused previews, older target); `RunFormatTests`, `test_launcher_records_the_run_format_at_start`; T028 live preview |
| AC-022, AC-023, SC-007 | `test_rollback_reuses_the_previous_installation` (downloads and Spec Kit denied) |
| AC-024 | `ReadmeUpdateTests` |

Tests written before their implementation were seen failing first; the three Spec Kit step cases added in this review passed at once, because the stage naming already covered them, while the switch and stage cases failed until ENG-001's fix. A mutation of the rollback rule to presence-only (the F-001 bug) makes `test_killed_setup_is_recovered` fail.

## Findings

| ID | Class | Severity | Location | Evidence | Required action |
|---|---|---|---|---|---|
| TST-001 | missing test | medium | `tests/test_setup.py` | SC-001 names every Spec Kit step and the switch; integration install, bundle install, preset add and a failing (not killed) switch had no test. | Add them. |
| TST-002 | missing test | low | `tests/test_setup.py` | Setup tests fake Spec Kit and downloads, so real Spec Kit output (stray files, embedded paths) is not covered offline. | Covered by the T028 live run with Spec Kit 1.0.11; accept. |
| TST-003 | missing test | low | `tests/test_preview.py` | SC-006 compares the preview with an update performed by fixture setups, which is partly by construction. | The live `ballast preview v0.4.2` (T028) exercised real builds; accept. |

## Resolution

- TST-001: added in `bf5359c`; the switch and stage cases failed before ENG-001's fix.
- TST-002, TST-003: accepted with the live evidence above.
