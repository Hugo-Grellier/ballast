# Test review: 146-checks-pass-in-run (implementation, after the resume)

- Reviewer: claude/claude-opus-5-5, independent context (agent-provisional)
- Scope: every test change against the rebased base `617df9c` (`tests/test_autonomy.py`, `test_autonomous_artifacts.py`, `test_autonomous_recovery.py`, `test_autonomous_run.py`, `test_agent_run_ledger.py`, `test_governance.py`, `test_spec_workflow.py`, the new `tests/parallel.py` and `tests/test_parallel.py`), plus `acceptance-evidence.json` and `suite-profile.md`. Judged against the testing policy and AC-001 to AC-020.

## Traceability

- AC-001 to AC-004: `CheckEnvTests` (guard entries, a second checkout's guard, the three variables plus a secret, order, empty and unset `PATH`, no mutation). `CheckEnvironmentTests` shows the same environment and an unchanged argv on `run_commands`, acceptance, feedback, final and project checks.
- AC-005: the bwrap-gated `RealCheckEnvironmentTests`. `acceptance-evidence.json` maps AC-005 to `[]`, because a nested bwrap cannot run inside the runner's acceptance checks (`decisions.md` wording clarification). T021 is deferred.
- AC-006: `AgentStepEnvironmentTests` and `test_workflow_steps_keep_the_run_variables`.
- AC-007 to AC-009: `IsolationTests` (per-class clearing and restoring, and the named tests in a child process with both variables set) and `OperatorStepGuardTests` (refusal with either variable).
- AC-015 to AC-018: `CheckTimeoutBlockTests`. They cover the first record, the recheck and the last cycle with no cycle consumed, and the wall-time and older-result wording. They cover the counter-cases: a non-timeout failure, an open finding, and a blocking finding. A final timeout stays `postcondition`. They also check re-entry at the feedback checks, that an earlier changed input wins, and that `fix-cycles` re-entry is unchanged. `CheckTimeoutLimitTests` and `TimeoutSecondsTests` cover the limit kind and `timeout_seconds`.
- AC-019, AC-020: `CheckEnvironmentDocumentTests`. After T032, `test_adr_0021_records_the_boundary` also asserts the ADR-0020 link and `#153`, under the same method name. The evidence mapping therefore still resolves, and `spec_digest` still matches `spec.md`.
- AC-010 to AC-014 are mapped to `[]` and rest on `suite-profile.md`, bd80a3e (T020 and D-001) and the deferred T021.

## Suite not weakened (AC-011, AC-013)

The diff adds one skip, the bwrap gate, which mirrors the file's existing gate. No test, assertion or skip was removed. The one narrowed child-process test asserts `Ran 1 test`, so it cannot pass vacuously, and its full class still runs in the suite. `tests/parallel.py` globs every `tests/test_*.py`, so the `[checks]` command runs the same modules as CI's sequential command. CI keeps `python -m unittest tests/test_*.py`. `test_parallel.py` covers passing, a failing module, default selection and `--jobs` validation.

## Evidence state after the resume

The run record's fix loop shows the feedback checks passed with the parallel runner under the 60-minute timeout (exit 0). The record does not show the run's duration. The 45-minute bar of AC-012 and SC-002 therefore still needs the measured `run-checks` seconds in the PR. A fix step cannot produce that number. The pre-existing 1-in-240 flake (D-002) is out of scope and tracked separately.

## Commands

This session could not run `unittest` or `ruff`: commands that need approval were refused, and no approval is possible here. The reviewer relied on the trusted runner's feedback checks in the run record and on reading the tests. `sha256sum specs/146-checks-pass-in-run/spec.md` matched the `spec_digest` in `acceptance-evidence.json`.

<!-- ballast-findings: begin -->
## Findings (recorded from the review draft)

- F-001 (low, missing-test, open): AC-012 and SC-002 have no recorded duration: the record shows the parallel feedback checks passed under 60 minutes, not how long they took, and test_chat_mode was never measured in the agent sandbox. The PR must state the measured run-checks seconds, or record them as unavailable.
- F-002 (low, missing-test, open): AC-005 is mapped to [] in acceptance-evidence.json because its bwrap-gated test cannot run nested in the runner's acceptance checks; the guarded real-sandbox case is verified only on a host with user namespaces and by the deferred T021.
- F-003 (info, implementation-bug, open): Pre-existing 1-in-240 flake (decisions.md D-002): AcceptanceChecksTests fakes a timeout with exit 124, which can equal the drawn pass code. Not caused by this diff; a separate change fixes it.
<!-- ballast-findings: end -->
