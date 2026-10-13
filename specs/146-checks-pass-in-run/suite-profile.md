# Suite profile: #146

The before-measurement for AC-011 and AC-012 (T001), then the after-measurement (T023).

## Where it was measured

**Reference baseline (from #146):** 1666 tests in 2848 s on the operator's machine. This is the figure AC-012 and SC-002 compare against, and the PR quotes it next to the `seconds` that this run's own `run-checks` records.

**This profile:** measured inside the implementing agent step of Autonomous run `a060b968` on 2026-10-13. Each module ran as `uv run --locked python -m unittest --durations 15 tests/test_<module>.py`, before any edit under `tests/` or `tools/`. That step is a guarded caller: the git guard is first on `PATH`, `BALLAST_GIT` is set, both run variables are set, and there is no systemd user session, Spec Kit CLI or nested bwrap. As a result:

- Modules that run `git` through the launcher's trusted resolution fail fast with `git-untrusted`, or `git not found outside working trees`, instead of doing their work: `test_demo`, `test_draft_pr`, `test_packet`, `test_completion` and part of `test_ballast`. Their seconds here understate the operator's.
- `test_agent_run_ledger` fails 22 tests on the run variables (the #142 attestation cause).
- The engine, real-systemd and real-bwrap tests are skipped (`skipped=` below), so their time is missing here.
- `test_chat_mode` drives `ballast run` on ptys. Here each of its tests took 30–60 s, and the first attempt stopped making progress after 34 of its 128 tests (a `fork()` from a multi-threaded process warning was printed). A second, solo attempt had reached about 20 tests after several minutes, so it was stopped. It is not measured here.
- `test_demo`, `test_discovery`, `test_doctor` and `test_chat_mode` (first attempt) overlapped for part of their run, as did `test_setup`, `test_setup_trust` and `test_spec_workflow`. Their seconds include some contention.

This profile therefore ranks the slow tests that do run here. It is not a substitute for the operator-machine total.

## Before (unchanged tree)

| Module | Tests | Seconds | Result here | Slowest tests (s) |
| --- | ---: | ---: | --- | --- |
| `test_agent_run_ledger` | 103 | 16.8 | 3 failures, 19 errors (run variables) | all < 1 |
| `test_autonomous_artifacts` | 126 | 208.7 | OK, 1 skipped | `RecordDecisionTests.test_field_rules` 8.9; `FinalAcceptanceTests.test_stale_intent_is_rejected` 7.0; `FinalAcceptanceTests.test_edit_after_run_checks_blocks` 6.6 |
| `test_autonomous_recovery` | 46 | 94.6 | OK, 12 skipped | `CheckpointTests.test_refresh_published_run` 6.1; `ResumeTests.test_active_time_after_a_long_pause` 5.9 |
| `test_autonomous_run` | 103 | 279.4 | OK | `RunStartTests.test_codex_without_nested_sandbox_falls_back_to_claude` 8.7; `CompletionReadyTests.test_publish_retry_of_a_reported_run_runs_the_packet_then_completes` 8.4 |
| `test_autonomy` | 188 | 131.8 | OK, 18 skipped | `EligibilityTests.test_uv_checks_without_venv_are_refused` 12.2; `EligibilityTests.test_branch_feature_and_credentials` 9.4; `PublisherTests.test_argv_never_merges_or_forces` 7.1 |
| `test_ballast` | 46 | 40.3 | 4 failures (`git not found outside working trees`) | `CacheTests.test_concurrent_fetches_download_once` 17.1 |
| `test_branch_sync` | 81 | 52.0 | OK | `RecoveryTests.test_failure_after_the_push_is_completed_by_any_next_invocation` 2.7 |
| `test_chat_mode` | (128 methods) | not measured | see above | 30–60 s per pty test here |
| `test_completion` | 30 | 6.2 | 2 failures (`LedgerError` under the guard) | `CompleteTests.test_forge_failure_keeps_the_draft_with_its_cause` 2.0 |
| `test_demo` | 33 | 9.5 | 44 subtest failures (`git-untrusted`) | all < 1.3 |
| `test_discovery` | 71 | 37.9 | OK | `BriefStructureTests.test_each_required_section_is_required` 6.8 |
| `test_doctor` | 42 | 21.1 | OK | `MachineTests.test_hung_resolver_is_bounded` 5.3; `MachineTests.test_hung_probe_is_bounded` 3.0 |
| `test_draft_pr` | 94 | 5.5 | 135 failures, 5 errors (`git-untrusted`) | all < 1 |
| `test_fallback` | 84 | 153.3 | OK | `WrapperFallbackTests.test_failed_fallback_timeout_is_incomplete` 10.0; `LedgerFallbackTests.test_refusal_recorded_with_reason` 9.4 |
| `test_feature_intake` | 10 | 41.6 | OK | `FeatureIntakeTests.test_retries_after_each_partial_write_without_duplicate_child` 27.4 |
| `test_governance` | 23 | 34.8 | OK | `TasksTemplateTests.test_implementation_check_is_unchanged` 34.5 |
| `test_init` | 51 | 21.6 | OK | `GeneratedContentTests.test_github_origin` 2.4 |
| `test_packet` | 78 | 16.7 | 83 failures, 27 errors (`git-untrusted`) | — |
| `test_preview` | 6 | 2.1 | OK | all < 1 |
| `test_release_workflow` | 4 | 0.0 | OK | — |
| `test_setup` | 79 | 214.1 | OK | `SetupLockTests.test_concurrent_setups_never_interleave` 34.9; `PrepareConcurrencyTests.test_one_preparation_per_worktree` 24.2; `RecoverableSetupTests.test_killed_setup_is_recovered` 12.1 |
| `test_setup_trust` | 108 | 130.7 | OK | `EveryRefusalTests.test_every_skipped_case_reports_and_keeps_the_baseline` 4.8 |
| `test_spec_workflow` | 202 | 181.4 | OK, 28 skipped | `TrustedLauncherTests.test_tamper_marker_and_unfinished_step_are_refused` 11.0; `AgentWrapperTests.test_unconfirmed_scope_stop_fails_the_step` 10.9 |
| **Total measured here** | **1608** (+ `test_chat_mode`) | **1700.2** (+ `test_chat_mode`) | | |

Without `test_chat_mode`, 1608 tests ran in about 1700 s here, while the operator's whole suite took 2848 s. The difference (about 1150 s) is `test_chat_mode`, the engine and systemd tests skipped here, and the fast failures above. `test_chat_mode` is the largest single cost that this sandbox cannot measure.

## Shared host state (research R9)

- Operator-side fakes and operator state live under fixed parents, `~/.cache/ballast-tests` and `~/.local/state/ballast-tests` (`test_autonomy.trusted_directory`, `operator_state`). Each test uses its own temporary directory beneath them.
- The real-bwrap tests in `test_autonomous_artifacts` and `test_autonomy` use `/var/tmp` for a fake home.
- `test_chat_mode`, `test_spec_workflow` and `test_autonomous_recovery` (engine classes) start transient systemd user scopes with per-run unit names.
- `test_setup` (`SetupLockTests`, `PrepareConcurrencyTests`) runs concurrent children against one temporary project each. It shares no lock outside that directory.

No module uses a fixed port. No module shares a fixed file outside its own temporary directory, apart from the parents above.

## Speed-ups (T022)

| Change | Effect here | Kept |
| --- | --- | --- |
| `test_governance.TasksTemplateTests.test_implementation_check_is_unchanged` ran all of `tests.test_spec_workflow.ArtifactContractTests` in a child process. It now runs only `test_implementation_needs_completed_tasks_and_a_change`, the contract test that asserts "pending tasks", and also asserts that the child ran exactly 1 test. | 34.5 s → about 4 s; `test_governance` 34.8 s → 5.6 s | Same test name and purpose (D-07). The rest of `ArtifactContractTests` still runs in the suite on its own. |

No other speed-up was safe. The remaining slow tests spend their time on what they assert: 20 concurrent-setup races (`test_setup`), killed and recovered processes, real child-process lifetimes, the real intake tool against a fake `gh`, and pty-driven Chat steps that must stay in progress while other commands are refused (`test_chat_mode`'s 6 s step). Shortening them would weaken them. See [decisions.md D-001](decisions.md) for the parallel runner that follows from this (T024).

## After (T023)

Measured the same way, in the same sandbox, after every change. Modules ran one per invocation, up to three at a time, so seconds include contention. `test_demo`, `test_draft_pr` and `test_packet` ran in one invocation, and their counts and failures are summed.

| Module | Tests before → after | Seconds before → after | Result after |
| --- | ---: | ---: | --- |
| `test_agent_run_ledger` | 103 → 106 | 16.8 → 46.4 | **OK** (before: 22 failures/errors on the run variables, which also made it fast) |
| `test_autonomous_artifacts` | 126 → 141 | 208.7 → 255.1 | 1 failure, 2 skipped: the pre-existing 1-in-240 flake D-002 (passes on rerun); the new real-bwrap test is skipped here |
| `test_autonomous_recovery` | 46 → 49 | 94.6 → 94.8 | OK, 12 skipped |
| `test_autonomous_run` | 103 → 104 | 279.4 → 303.9 | OK |
| `test_autonomy` | 188 → 193 | 131.8 → 123.0 | OK, 18 skipped |
| `test_ballast` | 46 → 46 | 40.3 → 36.6 | 4 failures, unchanged (`git not found outside working trees`) |
| `test_branch_sync` | 81 → 81 | 52.0 → 52.2 | OK |
| `test_chat_mode` | (128 methods) | not measured | not measured (see above) |
| `test_completion` | 30 → 30 | 6.2 → 9.7 | 2 failures, unchanged |
| `test_demo` + `test_draft_pr` + `test_packet` | 205 → 205 | 31.7 → 25.9 | 262 failures and 32 errors, unchanged (`git-untrusted`) |
| `test_discovery` | 71 → 71 | 37.9 → 27.1 | OK |
| `test_doctor` | 42 → 42 | 21.1 → 19.7 | OK |
| `test_fallback` | 84 → 84 | 153.3 → 122.1 | OK |
| `test_feature_intake` | 10 → 10 | 41.6 → 33.1 | OK |
| `test_governance` | 23 → 26 | 34.8 → 5.6 | OK |
| `test_init` | 51 → 51 | 21.6 → 14.3 | OK |
| `test_parallel` (new) | 0 → 4 | 0 → 0.5 | OK |
| `test_preview` | 6 → 6 | 2.1 → 1.2 | OK |
| `test_release_workflow` | 4 → 4 | 0.0 → 0.0 | OK |
| `test_setup` | 79 → 79 | 214.1 → 180.4 | OK |
| `test_setup_trust` | 108 → 108 | 130.7 → 76.5 | OK |
| `test_spec_workflow` | 202 → 203 | 181.4 → 126.9 | OK, 28 skipped |
| **Total measured here** | **1608 → 1643** | **1700.2 → 1555.0** | |

Every module has the same number of tests or more. The 35 new tests are this feature's (ledger 3, artifacts 15, recovery 3, autonomous run 1, autonomy 5, governance 3, spec workflow 1, parallel runner 4). The failures that remain are the ones the baseline had, caused by this guarded caller (`git-untrusted`, `git not found outside working trees`). The runner's check environment removes that cause for `run-checks` (AC-005), but a direct agent-step invocation like this one keeps the guard. The seconds here are not comparable run to run (contention, fast failures), so they are not evidence for AC-012.

**Diff checks (AC-011, AC-013):**

- `git diff HEAD -- tests/`: the only added skip is `@unittest.skipUnless(_bwrap_works(), ...)` on the new `RealCheckEnvironmentTests` (T008). No `skip`, `skipIf`, `expectedFailure` or test method was removed. The only removed lines are the governance test's docstring and its child-process target, narrowed by T022. Reviewed: `tests/test_agent_run_ledger.py`, `tests/test_autonomous_artifacts.py`, `tests/test_autonomous_recovery.py`, `tests/test_autonomous_run.py`, `tests/test_autonomy.py`, `tests/test_governance.py`, `tests/test_spec_workflow.py`, plus the new `tests/parallel.py` and `tests/test_parallel.py`.
- `git diff HEAD -- uv.lock pyproject.toml .github/workflows/ci.yml ballast.toml`: empty. `python -m unittest tests/test_*.py` still runs the whole suite, including `tests/test_parallel.py`. No dependency is added.

**Authoritative duration (AC-012, SC-002):** the operator-machine `seconds` of this run's own `run-checks`, quoted in the PR next to 2848 s. This run's `run-checks` uses the pinned v1.0.0 runner (research R11), so it proves the ledger isolation and the narrowed governance test, not the check environment.

## Parallel runner decision (T024)

The only safe speed-up saves about 30 s, so the operator-machine suite is projected at about 2848 − 30 ≈ 2818 s. That is above the 2700 s bar. `tests/parallel.py` (standard library) and `tests/test_parallel.py` were added. Switching the `[checks]` test command to `uv run --locked python tests/parallel.py` is a `ballast.toml` change, so it is proposed in [decisions.md D-001](decisions.md) for the driving agent, with `ballast trust`, alongside T020. CI keeps the sequential command.
