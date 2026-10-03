# Bug Verification: Ledger reports on archived workflow YAML

- **Slug**: ledger-yaml-stdlib
- **Tested**: 2026-10-03T15:53:34+02:00
- **Assessment**: ./assessment.md
- **Fix**: ./fix.md
- **Result**: verified

## Summary

The assessed failure path no longer reproduces: an isolated Python subprocess reports a disposable archived run after its active workflow directory is removed. Under Python 3.13 with `-I -S`, the current ledger code also reported five real archived runs and produced a successful aggregate report. A review follow-up closed a malformed indentation case; the prescribed regression suite and lint passed afterward.

## Checks Performed

| Check | Command / Action | Result | Notes |
|-------|------------------|--------|-------|
| Reproduction (post-fix) | `python3 -m unittest tests.test_agent_run_ledger.LedgerTests.test_isolated_cli_reports_archived_run` | pass | Test creates an archived run, removes the active run, then invokes `ledger.py report --all --json` and `report --run run_1` under `python -I -S`; both return 0. |
| Real archived runs | `uv run --no-project --python 3.13 python -I -S -` with a read-only script calling `ledger.report(root, run_id)` for each archived workflow with events | pass | All 5 eligible LoreForge archives reported without exceptions: 3 workflow statuses were `failed`, 2 were `paused`. These are recorded run outcomes, not check failures. |
| Real aggregate report | `uv run --no-project --python 3.13 python -I -S -` with a read-only script calling `ledger.main(['report', '--all', '--json'])` against the LoreForge root | pass | Exit status 0; JSON contained 5 instrumented runs and 5 run reports. |
| New / updated tests | `python3 -m unittest tests.test_agent_run_ledger.LedgerTests.test_isolated_cli_reports_archived_run tests.test_agent_run_ledger.LedgerTests.test_isolated_cli_imports_run tests.test_agent_run_ledger.LedgerTests.test_isolated_cli_rejects_unsupported_workflow_yaml tests.test_agent_run_ledger.LedgerTests.test_imports_engine_normalized_workflow_yaml tests.test_agent_run_ledger.LedgerTests.test_workflow_reader_rejects_ambiguous_identity_and_steps tests.test_agent_run_ledger.LedgerTests.test_workflow_digest_check_remains_enforced tests.test_agent_run_ledger.LedgerTests.test_workflow_identity_check_remains_enforced` | pass | 7 tests passed, covering isolated import, unsupported YAML, normalized YAML, and digest and identity checks. |
| Review follow-up | `python3 -m unittest tests.test_agent_run_ledger.LedgerTests.test_workflow_reader_rejects_ambiguous_identity_and_steps tests.test_agent_run_ledger.LedgerTests.test_imports_engine_normalized_workflow_yaml tests.test_agent_run_ledger.LedgerTests.test_isolated_cli_reports_archived_run` | pass | 3 tests passed. The added malformed indentation case failed before the source change and passed afterward. |
| Regression suite | `python3 -m unittest tests/test_*.py` | pass | 143 tests passed; 2 environment-dependent tests skipped. Ran with Python 3.14.4 on 2026-10-02. |
| Prescribed Python 3.13 gate | `UV_CACHE_DIR=/tmp/ledger-bug-test-uv-cache uv run --no-project --python 3.13 --with pyyaml python -m unittest tests/test_*.py` | pass | 143 tests passed with no skips after the review follow-up on 2026-10-03. |
| Lint / format | `UV_CACHE_DIR=/tmp/ledger-bug-test-uv-cache uvx ruff check && UV_CACHE_DIR=/tmp/ledger-bug-test-uv-cache uvx ruff format --check` | pass | All checks passed; 58 files already formatted. |
| Diff whitespace | `git diff --check` | pass | Exit status 0, no output. |

## Output Excerpts

```text
Ran 7 tests in 0.898s
OK

Ran 143 tests in 59.880s
OK (skipped=2)

Ran 143 tests in 48.920s
OK

archived reports completed: 5
status counts: {'failed': 3, 'paused': 2}

exit status: 0
instrumented runs: 5
run count: 5

All checks passed!
58 files already formatted
```

## Residual Risks

- The real-archive checks called the current ledger code under `-I -S` with the LoreForge root supplied in a read-only script; they did not invoke LoreForge's installed launcher. The disposable archived-run test exercises the CLI subprocess boundary.
- Five of seven local archive directories had both an archived workflow and ledger events and were included in the real-archive check. The other two did not meet that selection condition.

## Recommendation

Close the bug based on the reproduced archived-report path, successful reports from five real archives, and the passing prescribed Python 3.13 gate.
