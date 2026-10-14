# Engineering review: 146-checks-pass-in-run (implementation, after the run-checks block)

- Reviewer: claude/claude-opus-5-5, independent context (agent-provisional)
- Scope: the whole change against the branch base `0bddeb8` (commits 752f88b, b72b578, 4491448 and the working tree, whose only change is the regenerated `autonomous/record.md`). Files: `tools/spec_workflow/{autonomy,artifacts,run,agent}.py`, `ballast.toml`, `templates/policies/spec-kit-workflow.md`, ADR-0018's back-link, ADR-0021, `tests/parallel.py` and the test changes. Judged against `spec.md`, `intent.md`, `plan.md`, `tasks.md`, `decisions.md` (D-001 to D-003), both contracts, the engineering policy and the run record (HD-0001, HD-0002, PD-0014 to PD-0022).

## Why this review ran again

The final `run-checks` ran `uv run --locked python tests/parallel.py` and exited 1 after 1064.2 s, which recorded a `postcondition` block. The operator resolved it as HD-0002, calling it a flake. The operator's reference states that the full parallel suite was green outside the run (24 modules, 1483 s). The run then resumed at `validate-implementation`. No code changed during the block: the record lists only `outside`, and the diff since 4491448 touches only the record. This review covers the whole change again.

## What was checked

**Check environment (FR-001 to FR-005).** `autonomy.check_env` applies the unchanged secret filter `confined_env(env, None)`. It then removes `BALLAST_GIT` and both `RUN_VARIABLES` and drops every `PATH` entry that equals `GUARD` or ends in `spec_workflow/guard`. Order and empty entries are kept, nothing is added, and the argument is not mutated. `run_commands` is the single call site, so feedback, fix, final, acceptance, Chat and human-gated checks all get the same environment. The bwrap argv is still built from the operator environment. `agent.GUARD` now aliases `autonomy.GUARD` with the same value. `run._environment`, the agent step environment and `ledger._operator_step_guard` are unchanged: `git diff 0bddeb8 -- tools/spec_workflow/ledger.py .github` is empty.

**Timeout block (FR-009, FR-010, AC-015 to AC-018).** `_timeout_only` returns the latest feedback failures only when every one has `timed_out` and `_blocking` and `_open_to_fix` are both empty. In `record_decision`, it runs only for `implementation-review` with the fix loop. It runs after `review_rule` and before the block or limit branches and before any fix-state write. `_block` raises `BlockedError`, so no cycle is consumed. `check-timeout` is a resumable limit. `_reentry` sends it back to `checks-implementation` or `checks-fix-N`, which re-reads `[checks]` from the trusted `ballast.toml`. `_timeout_condition` takes minutes only from the trusted config, falls back to the default, separates a wall-time cut from the configured timeout, and bounds the text. The final `run-checks` path is untouched: HD-0002 shows that path still records a `postcondition` block (AC-018).

**`ballast.toml`.** `timeout_minutes = 60`, and the test command is `tests/parallel.py` (T020, D-001). Both were applied outside any step, with trust re-recorded (HD-0001, HD-0002). CI, `AGENTS.md` and `CLAUDE.md` keep the sequential command (AC-013).

**`tests/parallel.py`.** It uses only the standard library and globs every `tests/test_*.py`. It runs a bounded pool of `python -m unittest <module>` child processes and exits 1 on any failed module. The ordered `pool.map` output (earlier F-003) is unchanged. The HD-0002 failure shows why it matters: the committed record keeps only the exit code and duration of the failed final check, so the repository cannot say which module failed. Without that, the reader cannot tell whether the failure was the known D-002 flake or a race that the parallel runner introduced. The operator's green rerun outside the run, and the two green parallel feedback runs, make a systematic race unlikely. But the cause is not recorded anywhere this reviewer can read.

## Verification

- `uv run --locked ruff check`: all checks passed. `uv run --locked ruff format --check`: 540 files already formatted.
- `uv run --locked python -m unittest tests.test_parallel tests.test_autonomy.CheckEnvTests tests.test_autonomy.CheckTimeoutLimitTests tests.test_autonomous_artifacts.CheckTimeoutBlockTests tests.test_autonomous_artifacts.CheckEnvironmentTests tests.test_agent_run_ledger.OperatorStepGuardTests tests.test_agent_run_ledger.IsolationTests tests.test_governance.CheckEnvironmentDocumentTests`: 28 tests OK in 18.4 s.
- The full suite was not run in this session; the trusted runner's final `run-checks` reruns it after the reviews.
- `sha256sum spec.md` equals the `spec_digest` in `acceptance-evidence.json`.
- Operator state, which holds the failed final check's output tail, could not be read: the command needed an approval that this session cannot give.

## Assessment

The implementation still matches the approved spec, plan and ADR-0021. Nothing changed since the previous approved reviews (PD-0017 to PD-0021). The only new evidence is the in-run final check failure, which the operator classified as a flake. It is recorded below as a diagnostic gap for the PR. It is not a defect that a fix step could address without the failure output. The earlier low notes stand.

<!-- ballast-findings: begin -->
## Findings (recorded from the review draft)

- F-001 (low, missing-test, open): SC-002/AC-012 now has one duration, 1483 s for the parallel suite outside the run, but only as the operator's HD-0002 reference, not runner-recorded. The PR must quote it as such with the next run-checks seconds. A fix step cannot produce either number.
- F-002 (low, implementation-bug, open): When the run's wall time cuts a feedback check, the recorder records a resumable check-timeout block, but resuming meets the fixed wall-time limit at the next step. The condition says the wall time ran out, so the operator is not misled. Note only.
- F-003 (low, implementation-bug, open): tests/parallel.py prints module output through pool.map in module order, so on a [checks] timeout the kept output_tail names finished modules, not the one that hung. Printing as modules complete or a start line would fix it.
- F-004 (info, spec-ambiguity, open): AC-005, AC-014 and SC-001 have no runner-recorded evidence and rest on the deferred T021. The PR must not cite this run's v1.0.0 run-checks as FR-001 evidence.
- F-005 (low, missing-test, open): The final run-checks under tests/parallel.py exited 1 after 1064 s, and HD-0002 calls it a flake. The repository does not record which module failed, so a parallel-only race cannot be told apart from the known D-002 flake. The PR should name the failing test from the operator-state output tail and open an Issue if it is not D-002.
<!-- ballast-findings: end -->
