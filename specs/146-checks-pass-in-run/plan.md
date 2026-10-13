# Implementation Plan: Make the [checks] test command pass inside an Autonomous run

**Branch**: `fix-146-checks-pass-in-run` | **Date**: 2026-10-13 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/146-checks-pass-in-run/spec.md` (intent agent-provisional, PD-0005, digest in [intent.md](intent.md))

**Risk**: R2. The runner's environment for `[checks]` commands and acceptance checks is part of the headless-agent permission model ([research R13](research.md#r13-risk-recheck)). **Mode**: Autonomous run `a060b968`. Every decision here is agent-provisional. Merging the PR is the only human approval, including for R2.

## Summary

A new pure `autonomy.check_env` builds the environment of every check process. It starts from today's secret filter, then drops `BALLAST_GIT` and both run variables and removes every git guard entry from `PATH`. `artifacts.run_commands` uses it, and every check path runs through `run_commands`: Autonomous feedback, fix and final checks, runner acceptance checks, Chat and human-gated `ballast run checks`. The bwrap argv does not change, and agent steps keep the guard and the run variables.

The ledger tests clear both run variables for each test. `_operator_step_guard` does not change, and a new test proves it refuses with either variable set.

The implementation-review recorder gains one rule. When every failed feedback check timed out and no finding is blocking or open to fix, it records a resumable `limit` block of the new kind `check-timeout`. The block names each command and its applied timeout, and no fix cycle is consumed. Resume re-enters at the feedback checks step, so the checks rerun under the trusted `ballast.toml`'s new timeout.

`[checks] timeout_minutes` becomes 60, set by the driving agent outside a step and followed by `ballast trust`. The suite is profiled and its slowest tests fixed without losing a test. A standard-library parallel runner is added only if the suite stays over 45 minutes. ADR-0021 and the workflow policy document the boundary.

## Technical Context

**Language/Version**: Python ≥ 3.11, standard library only. The changed tools run under `python3 -I -S`.

**Primary Dependencies**: none new. `ruff` and `pyyaml` stay the only pinned gate dependencies ([R9](research.md#r9-speeding-up-the-suite)).

**Storage**: operator state only. The check results in `checks.json` and `checks-feedback.jsonl` gain the additive `timeout_seconds` field ([data-model](data-model.md#check-result-additive-field)). Blocks use the existing record with a new limit kind. No new file.

**Testing**: `unittest`. `check_env` is tested as a pure function. `run_commands` is tested with a recorded `subprocess.run`, and the recorder and resume through the existing artifacts and recovery harnesses. One bwrap-gated test runs a real check from a guarded caller.

**Target Platform**: the qualified 1.0 host (Linux, bwrap, systemd user session).

**Project Type**: workflow tools inside the installed standard (`tools/spec_workflow/`).

**Performance Goals**: the full suite under 45 minutes on the operator's machine (SC-002), down from 2848 s, with at least 1666 tests.

**Constraints**: the confinement is unchanged, and agent steps are unchanged. `_operator_step_guard` is unchanged. No test is skipped, deleted or weakened. The timeout comes only from the trusted `ballast.toml`.

**Scale/Scope**: about 40 lines in `autonomy.py`, 40 in `artifacts.py`, 15 in `run.py` and 2 in `agent.py`. Tests go in four existing files. Suite speed-ups touch whichever test modules the profile names. Documentation and ADR-0021.

No NEEDS CLARIFICATION remains.

## Constitution Check

*Gate before Phase 0, re-checked after Phase 1. Result: **PASS** both times, no violations.*

| Principle | How the design holds it |
| --- | --- |
| 1. Projects own only their files (BL-INV-001) | Changes are in installed tools, templates, tests and docs. The only project file touched is this repository's `ballast.toml`, which it owns. |
| 2. Nothing executes from a writable checkout (BL-INV-002) | Unchanged. The launcher still runs the pinned standard. The check commands come from trusted `ballast.toml`, and the launcher still refuses an untrusted `ballast.toml` after the timeout edit until `ballast trust` runs. |
| 3. Delegated authority (BL-INV-003) | A check loses variables and `PATH` entries and gains nothing. It keeps bwrap, the read-only host and hidden credentials, and it cannot write operator state ([R4](research.md#r4-why-removing-the-guard-and-run-variables-gives-a-check-no-authority)). Agent steps keep the guard. The `ballast.toml` edit happens outside a step. |
| 4. A project picks a version, never a source (BL-INV-004) | Not touched. |
| 5. Postconditions over exit codes (BL-INV-005) | The timeout block is decided from recorded check results and validated reviews. The protected-input and tree checks around checks are unchanged. |
| 6. Portable, dependency-free tools | Standard library only. Any parallel runner is standard library too. |
| 7. Generic by default | `check_env`, the limit kind and the policy text are generic. The 60-minute value is this repository's own setting. |
| 8. Executable evidence | Each AC has a scenario in [quickstart.md](quickstart.md). The guard refusal, the counter-cases of the timeout block and the guarded real-bwrap case are tested. |
| 9. A provisional decision is never human approval (BL-INV-006) | The new block and its recovery claim no approval. `ballast trust` here is an authorized privileged action, not an approval of the feature. |

## Architecture Boundaries

- **Affected areas**: confinement and limits in `tools/spec_workflow/autonomy.py` (`GUARD`, `RUN_VARIABLES`, `check_env`, `LIMIT_KINDS`, `LIMIT_LABELS`, `LIMIT_RECOVERY`); the checks core and the recorder in `tools/spec_workflow/artifacts.py` (`run_commands`, `record_decision`, a `_timeout_only` helper); resume re-entry in `tools/spec_workflow/run.py` (`_reentry`); `tools/spec_workflow/agent.py` (`GUARD` refers to `autonomy.GUARD`); and the tests and docs.
- **Contracts and data flow**: `run_checks` / `_acceptance_checks` / `project_checks` → `run_commands` → `check_env(os.environ)` → `subprocess.run(confined_argv(..., env=os.environ), env=check_env)` → results with `timeout_seconds` → `checks-feedback.jsonl` → recorder → existing rules, or the `check-timeout` block → `ballast run resume` → `_reentry` → the feedback checks step. The run record and feedback log in operator state stay the source of truth for check results, and `ballast.toml` stays the only source of the timeout. See [contracts/check-environment.md](contracts/check-environment.md), [contracts/timeout-block.md](contracts/timeout-block.md) and [data-model.md](data-model.md).
- **Architecture references**: [constitution](../../.specify/memory/constitution.md) BL-INV-002, BL-INV-003 and BL-INV-006; [ADR-0018](../../docs/adr/0018-runner-recorded-acceptance-checks.md) (acceptance checks use the check confinement); [ADR-0010](../../docs/adr/0010-autonomous-resume-and-bounded-recovery.md) (resume and limits); [ADR-0004](../../docs/adr/0004-autonomous-provisional-decisions.md); [workflow runner contract](../../templates/policies/spec-kit-workflow.md#workflow-runner-contract); [R2 boundaries](../../docs/policies/project/workflow.md#r2-boundaries).
- **Proposed architecture decisions** (agent-provisional; the merge accepts them):
  1. **ADR-0021 Check commands run in an environment like CI.** It extends ADR-0018. Every `[checks]` command and runner acceptance check runs without the agent git guard on `PATH` and without `BALLAST_GIT`, `BALLAST_SPEC_WORKFLOW` and `SPECKIT_WORKFLOW_RUN_ID`, inside unchanged confinement. It explains why that grants no authority, records that agent steps keep both, and records the `check-timeout` limit with its resume re-entry.

## Repository Impact

| Path | Change |
| --- | --- |
| `tools/spec_workflow/autonomy.py` | `GUARD`, `RUN_VARIABLES` and `check_env` ([contract](contracts/check-environment.md)). The `check-timeout` limit kind, its label and its recovery ([contract](contracts/timeout-block.md)). |
| `tools/spec_workflow/artifacts.py` | `run_commands` passes `check_env(dict(os.environ))` to `subprocess.run` and records `timeout_seconds`. `record_decision` applies the timeout-only rule before the limit and fixing rules. A helper builds the condition. |
| `tools/spec_workflow/run.py` | `_reentry` maps a `check-timeout` block to its feedback checks step. |
| `tools/spec_workflow/agent.py` | `GUARD = autonomy.GUARD`; behavior unchanged. |
| `tests/test_autonomy.py` | `check_env` cases: guard entries, the three variables, the secret filter, order kept, `PATH` unset or empty. The `check-timeout` block validates and is resumable. |
| `tests/test_autonomous_artifacts.py` | `run_commands` env and unchanged argv; acceptance-check env; the timeout-only block and its counter-cases (non-timeout failure, open finding, blocking finding, last cycle, recheck); `timeout_seconds`; the final timeout still blocks as `postcondition`. A bwrap-gated real check from a guarded caller. |
| `tests/test_autonomous_recovery.py` | Resume re-entry for a `check-timeout` block at both recorder steps. |
| `tests/test_agent_run_ledger.py` | Per-test clearing of the run variables. A guard refusal test with each variable alone. |
| `tests/test_*.py` (as the profile names) | Speed-ups that keep each test and its assertions ([R9](research.md#r9-speeding-up-the-suite)). |
| `ballast.toml` | `timeout_minutes = 60`, edited by the driving agent outside a step, then `ballast trust` ([R10](research.md#r10-the-timeout-edit-and-trust)). |
| `templates/policies/spec-kit-workflow.md` | Autonomous runs and the runner contract rows: the check environment and its scope, `[checks] timeout_minutes` (default 30, 1-240, trusted `ballast.toml` only; the policy does not describe it today), the `check-timeout` block and its resume, next to the fix-loop and limit text. |
| `docs/adr/0021-check-command-environment.md` | New ADR-0021. |
| `docs/adr/0018-runner-recorded-acceptance-checks.md` | "Extended by ADR-0021" note. |
| `tests/parallel.py` (only if needed) | Standard-library per-module runner. A `[checks]` command change follows the same trust path ([R9](research.md#r9-speeding-up-the-suite)). |

Unchanged: the `guard/git` script, `ledger._operator_step_guard`, `chat.py`, `run._environment`, `confined_argv`, `parse_checks` and its bounds, the workflow YAML, `uv.lock`, `pyproject.toml`, and `.github/workflows/ci.yml` unless the parallel runner is needed.

## Feature Artifacts

```text
specs/146-checks-pass-in-run/
├── discovery.md
├── intent.md
├── spec.md
├── plan.md            # this file
├── research.md        # Phase 0 decisions R1-R13
├── data-model.md
├── contracts/
│   ├── check-environment.md
│   └── timeout-block.md
├── quickstart.md      # validation scenarios mapped to ACs
├── checklists/
├── autonomous/        # run record (rendered by the runner)
├── tasks.md           # next: speckit-tasks
├── decisions.md       # only if implementation discovers one
└── reviews/
```

## Review notes

- **Required reviews** (R2, [review matrix](../../templates/policies/workflow.md#review-triggers)):
  - engineering;
  - security, because the runner's check environment and the agent tool boundary change;
  - test, covering the environment, the ledger isolation, the timeout block's counter-cases and proof that the suite was not weakened;
  - documentation, covering the policy and ADR-0021.
- **For the plan decision** (agent-provisional): accept the guard match rule ([R2](research.md#r2-how-a-guard-entry-on-path-is-recognized)). Accept `check-timeout` as a limit kind with a re-entry mapping rather than a new category ([R7](research.md#r7-how-the-timeout-block-is-represented-and-resumed)). Accept the additive `timeout_seconds` field ([R8](research.md#r8-the-timeout-each-result-records)).
- **For the merge reviewer**: this run's own `run-checks` uses the pinned v1.0.0 runner, so it proves the ledger isolation, the faster suite and the new timeout, but not the check environment. AC-014 and SC-001 need a run on this checkout's runner, or a deferred operator task after release ([R11](research.md#r11-what-this-runs-own-checks-prove)).
- **Not in scope**: the git guard itself, the agent step environment, other `[checks]` semantics, and a run subset of the suite.

## Complexity Tracking

No constitution violations.
