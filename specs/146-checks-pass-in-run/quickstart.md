# Quickstart: validate the feature

Validation scenarios mapped to the acceptance criteria. Contracts: [check environment](contracts/check-environment.md), [timeout block](contracts/timeout-block.md).

## Prerequisites

- `uv sync --locked`
- Linux with `bwrap` for the confined-check scenarios (CI skips them without it).
- The operator's machine for the suite timing (AC-012, SC-002).

## Fast gate

```sh
uv run --locked ruff check && uv run --locked ruff format --check
uv run --locked python -m unittest tests/test_*.py
```

## Scenarios

| ID | Scenario | How | Expected |
| --- | --- | --- | --- |
| AC-001, AC-004 | `check_env` from a caller with the guard on `PATH` twice and in a later position, `BALLAST_GIT`, both run variables and `GITHUB_TOKEN` | unit test in `tests/test_autonomy.py` | none of them in the result; other `PATH` entries in order; other variables kept |
| AC-001 | `run_commands` passes `check_env` to the process and the bwrap argv is unchanged | unit test in `tests/test_autonomous_artifacts.py` with a recorded `subprocess.run` | the recorded `env` has none of the removed entries; argv equals the one built before |
| AC-002 | an acceptance check from the same caller | unit test through `_acceptance_checks` | same environment; `writable_checkout=False` |
| AC-003 | feedback, final, Chat `project_checks` and acceptance paths | unit test per path | each calls `run_commands`, so each gets `check_env` |
| AC-005 | a check command running `env` and `command -v git` under real bwrap from a guarded caller | bwrap-gated test | no guard directory, the host git found |
| AC-006 | agent step environment | existing `_base_env` tests plus one asserting the guard is first on `PATH` and `BALLAST_GIT` set | unchanged |
| AC-007, AC-009 | `BALLAST_SPEC_WORKFLOW=1 SPECKIT_WORKFLOW_RUN_ID=x uv run --locked python -m unittest tests/test_agent_run_ledger.py` | command | all pass |
| AC-008 | guard with each variable alone | unit test | `operator attestation is unavailable inside an agent step`; `git diff` shows `_operator_step_guard` unchanged |
| AC-010 | `ballast.toml` | `grep timeout_minutes ballast.toml`; `ballast trust` recorded by the driving agent | `60` |
| AC-011 | test count before and after | `python -m unittest` summary on `main` and on the branch | after ≥ before; no new `skip`; `git diff tests/` reviewed for weakened assertions |
| AC-012, SC-002 | suite duration | `time uv run --locked python -m unittest tests/test_*.py` on `main` and the branch, operator's machine | after < before and < 45 min; both in the PR |
| AC-013 | command and dependencies | `git diff uv.lock pyproject.toml .github/workflows/ci.yml` | unchanged, or justified per the dependency policy |
| AC-014, SC-001, SC-003 | Autonomous run on unchanged `main` using this checkout's runner | `BALLAST_STANDARD_DIR=<checkout>` run, or deferred operator task after release ([research R11](research.md#r11-what-this-runs-own-checks-prove)) | `run-checks` passes, 0 fix cycles, no `git-untrusted`, no attestation error |
| AC-015, SC-004 | feedback with only timed-out checks, no open finding | recorder unit test in `tests/test_autonomous_artifacts.py` | `limit`/`check-timeout` block naming each command and timeout; cycles 0 |
| AC-015 | resume after a `check-timeout` block | `_reentry` test in `tests/test_autonomous_recovery.py` | re-enters at `checks-implementation` or `checks-fix-N` |
| AC-016 | timeout plus a non-zero exit | recorder unit test | `fix-pending`, cycle starts |
| AC-017 | timeout plus an open or blocking finding | recorder unit test | existing fix or block rule |
| AC-018 | final `run-checks` timeout | existing test, kept | `postcondition` block as before |
| AC-019 | policy | read `templates/policies/spec-kit-workflow.md` | check environment, scope, timeout bounds and source, timeout block |
| AC-020 | ADR | read `docs/adr/0021-check-command-environment.md` | boundary, no new authority, agent steps keep both, extends ADR-0018 |
