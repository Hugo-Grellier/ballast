# Test review: 146-checks-pass-in-run (implementation)

- Reviewer: claude-opus-5-5, independent context (agent-provisional)
- Scope: test changes in `tests/test_autonomy.py`, `tests/test_autonomous_artifacts.py`, `tests/test_autonomous_recovery.py`, `tests/test_autonomous_run.py`, `tests/test_agent_run_ledger.py`, `tests/test_governance.py`, `tests/test_spec_workflow.py`, the new `tests/parallel.py` and `tests/test_parallel.py`, `acceptance-evidence.json` and `suite-profile.md`, judged against the testing policy and AC-001 to AC-020.

## Traceability

- AC-001/AC-004: `CheckEnvTests` cover the guard on `PATH` twice, a second checkout's guard, the three variables plus a secret, kept order including an empty entry, unset or empty `PATH` and no mutation. AC-001 to AC-003 through `CheckEnvironmentTests`: a recorded `subprocess.run` shows the same environment on `run_commands`, the acceptance checks (with a read-only checkout), feedback, final and project checks, and an argv equal to the one built from the operator environment.
- AC-005: the bwrap-gated `RealCheckEnvironmentTests` runs `env; command -v git` from a guarded caller. It was skipped in this sandbox. `acceptance-evidence.json` maps AC-005 to `[]`, with the reason recorded in `decisions.md` (nested bwrap inside the runner's acceptance checks), and the deferred T021 covers it.
- AC-006: `AgentStepEnvironmentTests` asserts that the guard is first, `BALLAST_GIT` and both run variables are kept, and `agent.GUARD == autonomy.GUARD`. `test_workflow_steps_keep_the_run_variables` covers `run._environment`.
- AC-007 to AC-009: per-class clearing in `setUp`. `IsolationTests` (a) checks clearing and restoring for every class, and (b)/(c) run the named tests in a child process with both variables set. `OperatorStepGuardTests` checks the refusal with either variable or both. `ledger.py` is unchanged.
- AC-015 to AC-018: `CheckTimeoutBlockTests` on the real recorder harness assert the exact condition text, the recovery, the resume command and an unchanged fix state and cycle count on the first record, the recheck and the last cycle. They also cover the wall-time and older-result wording, and the counter-cases (non-timeout failure starts a cycle with both checks in the fix input; open medium finding; blocking finding keeps existing rules). The final timeout still blocks as `postcondition`. `CheckTimeoutLimitTests` and `ResumeTests` cover the limit kind, validation, resumability and re-entry, including an earlier changed input winning and `fix-cycles` re-entry unchanged.
- AC-019/AC-020: `CheckEnvironmentDocumentTests` assert the policy wording, ADR-0021's content, the ADR-0018 back-link and ADR-0021's relative links.
- AC-010 to AC-014 are mapped to `[]` and left to `suite-profile.md` and the deferred T020/T021, as the tasks state.

## Suite not weakened (AC-011, AC-013)

The diff adds exactly one skip decorator, the bwrap gate on the new real-sandbox test, which mirrors the file's existing gate. No test method, assertion or skip was removed. The one narrowed test (`TasksTemplateTests.test_implementation_check_is_unchanged`) now runs the single contract test that asserts its stated purpose and adds an `assertIn("Ran 1 test", ...)` so a renamed target cannot pass vacuously. The full `ArtifactContractTests` class still runs in the suite. Per-module counts rose from 1608 to 1643 where measured. `test_parallel.py` covers the runner's exit status and module selection.

## Gaps

The operator-machine duration (AC-012, SC-002) is not measured: `test_chat_mode` could not run in the agent sandbox, and the projection exceeds the 2700 s bar without the D-001 parallel command. `decisions.md` D-002 records a pre-existing 1-in-240 flake in `AcceptanceChecksTests.test_timeout_and_exhausted_wall_time_are_explicit`, which this feature did not cause but which can fail a run's `[checks]` command.

## Commands run

- `uv run --locked python -m unittest tests/test_autonomy.py tests/test_autonomous_recovery.py tests/test_agent_run_ledger.py tests/test_parallel.py`: 352 OK.
- `uv run --locked python -m unittest tests/test_autonomous_artifacts.py tests/test_governance.py tests/test_autonomous_run.py`: 271 OK, 2 skipped.

<!-- ballast-findings: begin -->
## Findings (recorded from the review draft)

- F-001 (medium, missing-test, accepted-provisionally): AC-012 and SC-002 have no measurement on the operator's machine: test_chat_mode could not run in the agent sandbox, and the sequential projection exceeds 2700 s. Only the operator can produce this evidence, after D-001 and T020, so a fix cycle cannot add it. The PR must record both durations, or record them as unavailable.
- F-002 (low, missing-test, open): AC-005 is mapped to [] in acceptance-evidence.json. Its bwrap-gated test was skipped in this reviewer sandbox, so the guarded real-sandbox case is verified only on a host with user namespaces and by the deferred T021.
- F-003 (info, implementation-bug, open): Pre-existing 1-in-240 flake, recorded in decisions.md D-002: AcceptanceChecksTests fakes a timeout with exit 124, which can equal the drawn pass code. Not caused by this diff, but it can fail any run's [checks] command; a separate change should fix it.
<!-- ballast-findings: end -->
