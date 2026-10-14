# Test review: 146-checks-pass-in-run (implementation, after the run-checks block)

- Reviewer: claude/claude-opus-5-5, independent context (agent-provisional)
- Scope: every test change against the branch base `0bddeb8`. That covers `tests/test_autonomy.py`, `test_autonomous_artifacts.py`, `test_autonomous_recovery.py`, `test_autonomous_run.py`, `test_agent_run_ledger.py`, `test_governance.py` and `test_spec_workflow.py`, plus the new `tests/parallel.py` and `tests/test_parallel.py`, `acceptance-evidence.json`, `suite-profile.md` and the run record's Checks and Block resolutions. Judged against the testing policy and AC-001 to AC-020.

## Traceability

- AC-001 to AC-004: `CheckEnvTests` covers guard entries (this install's guard, another checkout's guard, a trailing slash), the three variables plus a secret, order, empty and unset `PATH`, and no mutation. `CheckEnvironmentTests` covers `run_commands` and the acceptance, feedback, final and project checks.
- AC-005: the bwrap-gated `RealCheckEnvironmentTests`, mapped to `[]` because a nested bwrap cannot run inside acceptance checks. Deferred to T021.
- AC-006: `AgentStepEnvironmentTests` and `test_workflow_steps_keep_the_run_variables`.
- AC-007 to AC-009: `IsolationTests` checks each class's setUp clearing and restoring. It also runs the named tests in a child process with both variables set. `OperatorStepGuardTests` checks refusal with either variable and with both, through the guard and through `_check`.
- AC-015 to AC-018: `CheckTimeoutBlockTests` covers the first record, the recheck, the last cycle, wall-time wording and older results. Its counter-cases are a non-timeout failure, an open finding, a blocking finding and a final timeout that stays `postcondition`. `ResumeTests` covers re-entry at the feedback checks, an earlier changed input winning, and unchanged `fix-cycles` re-entry. `CheckTimeoutLimitTests` and `TimeoutSecondsTests` cover the limit kind and `timeout_seconds`.
- AC-019, AC-020: `CheckEnvironmentDocumentTests`.
- AC-010 to AC-014 map to `[]` and rest on `ballast.toml`, `suite-profile.md`, the PR and the deferred T021.

## Suite not weakened (AC-011, AC-013)

No test, assertion or skip was removed. The one added skip is the bwrap gate, which mirrors the file's existing gate. The narrowed child-process test in `test_governance.py` asserts `Ran 1 test`, and its full class still runs. `tests/parallel.py` globs every `tests/test_*.py`. CI keeps the sequential command. `test_parallel.py` covers a passing run, a failing module, output order, default selection and `--jobs` validation.

## New evidence since the last test review

- The final `run-checks` exited 1 after 1064.2 s. The operator called this a flake (HD-0002) and reported the full parallel suite green outside the run in 1483 s.
- 1483 s is the first suite duration recorded for SC-002 and AC-012: under the 2700 s bar and below 2848 s. It is operator-reported in a block reference, not runner-recorded, and it was measured outside the run. The PR should quote it as such, together with the next `run-checks` seconds.
- Which module failed in-run is not recorded in the repository. D-002's known 1-in-240 flake is a plausible cause. A parallel-only interaction is another: `suite-profile.md` found no shared host state, but this is the first in-run failure under the parallel command. The PR should name the failing test from the operator-state output tail. If it is not D-002, it needs its own Issue.

## Commands

- `uv run --locked python -m unittest` on the feature's test classes (`tests.test_parallel`, `CheckEnvTests`, `CheckTimeoutLimitTests`, `CheckTimeoutBlockTests`, `CheckEnvironmentTests`, `OperatorStepGuardTests`, `IsolationTests`, `CheckEnvironmentDocumentTests`): 28 tests, OK.
- `uv run --locked ruff check` and `ruff format --check`: clean.
- The full suite was not run here. The runner's next `run-checks` is the evidence.

<!-- ballast-findings: begin -->
## Findings (recorded from the review draft)

- F-001 (low, missing-test, open): AC-012 and SC-002 have only the operator-reported 1483 s from HD-0002, measured outside the run, with no runner-recorded duration. The PR must quote it as such with the next run-checks seconds, or record those as unavailable.
- F-002 (low, missing-test, open): AC-005 maps to [] in acceptance-evidence.json because its bwrap-gated test cannot run nested in the runner's acceptance checks. The guarded real-sandbox case is verified only on a host with user namespaces and by the deferred T021.
- F-003 (info, implementation-bug, open): Pre-existing 1-in-240 flake (D-002): AcceptanceChecksTests fakes a timeout with exit 124, which can equal the drawn pass code. This diff did not cause it; a separate change fixes it.
- F-004 (low, missing-test, open): The final run-checks failed in-run under the parallel command (exit 1, 1064 s) with its failing module unrecorded in the repository. The PR should name it from the operator-state output tail, and open an Issue if it is not D-002.
<!-- ballast-findings: end -->
