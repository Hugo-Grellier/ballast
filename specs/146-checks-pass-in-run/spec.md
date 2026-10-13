# Feature Specification: Make the [checks] test command pass inside an Autonomous run

**Feature Branch**: `fix-146-checks-pass-in-run`

**Created**: 2026-10-13

**Status**: Draft

**Input**: User description: "Issue #146: the [checks] commands run by an Autonomous run pass on an unchanged main within the configured timeout, with a faster suite, a CI-like check environment and immediate block on an unaddressable timeout."

**Tracking**: [Ballast #146](https://github.com/Hugo-Grellier/ballast/issues/146). Follows proposals D-001 and D-002 of [#142](../142-feature-ui-states/decisions.md) and extends [ADR-0018](../../docs/adr/0018-runner-recorded-acceptance-checks.md). Written from the [discovery brief](discovery.md).

**Risk**: R2. The runner's environment for `[checks]` commands and runner acceptance checks changes, which is part of the headless-agent permission model ([`docs/policies/project/workflow.md`](../../docs/policies/project/workflow.md#r2-boundaries)). The `ballast.toml` timeout edit needs `ballast trust` re-recorded before merge (privileged action `operator-trust`).

**Mode**: Autonomous run `a060b968`. Every gate decision on this feature, including the pre-change approval for the R2 boundary, is agent-provisional; merging its PR is the only human approval.

## Context

Autonomous run `864d9151` for #142 ended at `fix-cycle limit (3)` with every review approved and no finding open. The `[checks]` test command could not pass inside the run for three reasons: the run variables `BALLAST_SPEC_WORKFLOW` and `SPECKIT_WORKFLOW_RUN_ID` leaked into the tests, so the ledger's operator-attestation guard failed ledger tests; the agent git guard came first on `PATH`, so packet and governance tests stopped with `git-untrusted`; and the suite (1666 tests in 2848 s on the operator's machine) exceeded the 30-minute timeout. The fix agent cannot edit `ballast.toml`, so it spent its three fix cycles changing nothing.

The operator chose, on 2026-10-13, to run checks in an environment like CI, to make the ledger tests independent of the caller, to raise the timeout to 60 minutes, to make the suite faster without weakening it, and to block at once on a timeout that no fix step can address.

## User Scenarios & Testing *(mandatory)*

Give each acceptance scenario a stable ID (`AC-001`, `AC-002`, ...). Task and test descriptions cite the IDs they satisfy, so review can trace each criterion to evidence.

### User Story 1 - Check commands run in an environment like CI (Priority: P1)

The operator starts an Autonomous run. When the runner runs the `[checks]` commands or a runner acceptance check, the tests see the same environment they see in CI: the real git and no run variables, while confinement and secret filtering stay as they are. Tests that pass in CI pass in the run.

**Why this priority**: Two of the three recorded causes come from the check environment; without this the test command cannot pass in any run.

**Independent Test**: Build the environment for a check command from a caller environment that has the guard directory on `PATH`, `BALLAST_GIT`, both run variables and a secret-named variable: none of them reaches the check, and every other variable and `PATH` entry does, in order.

**Acceptance Scenarios**:

1. **AC-001**: **Given** a caller environment with the agent git guard directory on `PATH` and `BALLAST_GIT`, `BALLAST_SPEC_WORKFLOW` and `SPECKIT_WORKFLOW_RUN_ID` set, **When** the runner runs a `[checks]` command, **Then** the command's environment has no guard directory on `PATH` and none of those three variables, secret-named variables are still dropped, and the command still runs under the same bwrap confinement with a read-only host and hidden credential paths. [S: IAC-2] [B: D-01] [S: tools/spec_workflow/autonomy.py]
2. **AC-002**: **Given** the same caller environment, **When** the runner runs a runner acceptance check, **Then** the check gets the same environment as a `[checks]` command and keeps its read-only checkout. [B: D-01] [B: D-02] [S: docs/adr/0018-runner-recorded-acceptance-checks.md]
3. **AC-003**: **Given** a `[checks]` run from an Autonomous feedback, fix or final check step, a Chat run or a human-gated `ballast run checks`, **When** each runs its commands, **Then** every one gets the same check environment. [B: D-02] [S: tools/spec_workflow/artifacts.py]
4. **AC-004**: **Given** a caller `PATH` that holds the guard directory more than once or after other entries, **When** the check environment is built, **Then** every guard entry is removed and the remaining entries keep their order. [I]
5. **AC-005**: **Given** a `[checks]` test command that runs `tests/test_packet.py` and `tests/test_governance.py` from a guarded caller, **When** the runner runs it, **Then** those tests find the host git as in CI and no test stops with `git-untrusted`. [S: IAC-2] [B: D-01]
6. **AC-006**: **Given** an agent step of any run, **When** it starts, **Then** it still has the guard directory first on `PATH`, `BALLAST_GIT` and both run variables, exactly as before. [S: .specify/workflow-state/issues/146.md] [B: D-01]

---

### User Story 2 - Ledger tests pass under any caller without weakening the attestation guard (Priority: P1)

A maintainer or the runner runs the ledger tests from any environment, including one where the run variables are set. The tests pass, and the guard that refuses an operator attestation inside an agent step is unchanged.

**Why this priority**: It removes the first recorded cause at its source, so the tests stay correct even outside the runner's check environment, and it protects a security check from being relaxed to make tests pass.

**Independent Test**: Run `tests/test_agent_run_ledger.py` with both run variables set: it passes. Call the attestation guard with either variable set: it refuses.

**Acceptance Scenarios**:

1. **AC-007**: **Given** `BALLAST_SPEC_WORKFLOW` and `SPECKIT_WORKFLOW_RUN_ID` set in the caller's environment, **When** `tests/test_agent_run_ledger.py` runs, **Then** every test in it passes, including `test_criterion_mapped_to_no_test_stays_missing` and `test_stale_manifest_does_not_block_runner_snapshot`. [S: IAC-1] [B: D-04]
2. **AC-008**: **Given** either `BALLAST_SPEC_WORKFLOW` or `SPECKIT_WORKFLOW_RUN_ID` set, **When** an operator attestation is attempted, **Then** `_operator_step_guard` refuses it with `operator attestation is unavailable inside an agent step`, and its code is unchanged. [S: IAC-3] [B: D-04] [S: tools/spec_workflow/ledger.py]
3. **AC-009**: **Given** a ledger test that sets a run variable inside its own patch, such as `test_explicit_record_cannot_forge_snapshot_or_ac_check`, **When** it runs, **Then** it sees that variable and still asserts the refusal. [S: specs/142-feature-ui-states/decisions.md] [B: D-04]

---

### User Story 3 - The test command finishes inside the configured timeout (Priority: P1)

The operator's Autonomous run on an unchanged `main` runs the full test suite as its `[checks]` test command and gets a pass well within the timeout, so a correct feature reaches its Draft PR.

**Why this priority**: The third recorded cause; even with a clean environment the suite exceeded the timeout, which alone ends a correct run at the fix-cycle limit.

**Independent Test**: Measure the suite on the operator's machine before and after; confirm the same tests run, the duration is lower and the run's `run-checks` result passes within `timeout_minutes = 60`.

**Acceptance Scenarios**:

1. **AC-010**: **Given** this repository's `ballast.toml`, **When** the runner reads `[checks]`, **Then** `timeout_minutes` is `60`, within the 1-240 bound, and the edit was made outside an agent step with operator trust re-recorded. [B: D-05] [S: tools/spec_workflow/autonomy.py] [S: ballast.toml]
2. **AC-011**: **Given** the suite before this feature, **When** it is compared with the suite after, **Then** no test is skipped, deleted or weakened, every test keeps its isolation, and the after run reports at least as many tests as the before run. [S: .specify/workflow-state/issues/146.md] [P: D-07]
3. **AC-012**: **Given** the operator's machine, **When** the suite is measured before and after, **Then** its wall-clock duration after is lower than before and well under 60 minutes, and both durations are recorded in the PR. [S: .specify/workflow-state/issues/146.md] [P: D-07] [I]
4. **AC-013**: **Given** the faster suite, **When** `uv run --locked python -m unittest tests/test_*.py` runs, **Then** it still runs the whole suite, and no dependency beyond the pinned `ruff` and `pyyaml` is added unless it passes the dependency policy. [P: D-07] [S: docs/policies/dependencies.md] [S: .github/workflows/ci.yml]
5. **AC-014**: **Given** an Autonomous run on an unchanged `main`, **When** its `run-checks` step runs the `[checks]` test command, **Then** the command passes within the configured timeout with no `git-untrusted` and no attestation error. [S: IAC-2] [B: D-01] [B: D-05]

---

### User Story 4 - An unaddressable timeout blocks at once (Priority: P2)

When a feedback check times out and nothing a fix step can address is open, the operator sees the run block immediately with the timed-out command and what to do, instead of watching three fix cycles change nothing.

**Why this priority**: It stops the waste and the misleading limit block, but the run already ends safely without it; stories 1-3 remove the timeouts this feature knows about.

**Independent Test**: Record a feedback check result in which every failed check timed out and no finding is open: the run blocks at once and the fix-cycle count is unchanged. Add one non-timeout failure: the run enters a fix cycle.

**Acceptance Scenarios**:

1. **AC-015**: **Given** a feedback check run in which every failed check timed out and no review finding is blocking or open to fix, **When** the runner records the fix state, **Then** the run blocks at once without consuming a fix cycle, and the block names each timed-out command and its timeout and tells the operator to raise `[checks] timeout_minutes` or speed up the command, run `ballast trust`, then resume or continue human-gated. [S: .specify/workflow-state/issues/146.md] [P: D-06]
2. **AC-016**: **Given** a feedback check run with a timed-out check and another check that failed with a non-zero exit, **When** the runner records the fix state, **Then** the run enters a fix cycle as before. [P: D-06]
3. **AC-017**: **Given** a timed-out feedback check together with a blocking or open review finding, **When** the runner records the fix state, **Then** the existing fix-loop and blocking rules apply unchanged. [P: D-06]
4. **AC-018**: **Given** a final `run-checks` step whose command times out, **When** the runner records it, **Then** the run blocks exactly as it does today. [S: docs/policies/spec-kit-workflow.md#workflow-runner-contract]

---

### User Story 5 - The check environment and timeout are documented (Priority: P2)

An adopter or reviewer reads the workflow policy and an ADR to learn what environment check commands get, why it differs from an agent step, and how the timeout and the timeout block work.

**Why this priority**: Required by the Issue and by the rule that an accepted architecture change gets an ADR, but it delivers no behavior on its own.

**Independent Test**: Read the installed policy built from `templates/policies/spec-kit-workflow.md` and the new ADR: both state the removed entries, the kept confinement, the timeout source and bound, and the immediate timeout block.

**Acceptance Scenarios**:

1. **AC-019**: **Given** the spec-kit workflow policy template, **When** it is installed as `docs/policies/spec-kit-workflow.md`, **Then** it describes the check environment (no guard on `PATH`, no `BALLAST_GIT` or run variables; bwrap and secret filtering kept), that it applies to every `[checks]` command and runner acceptance check, the `timeout_minutes` setting with its bounds and trusted source, and the immediate block on an unaddressable timeout. [S: IAC-4] [S: templates/policies/spec-kit-workflow.md]
2. **AC-020**: **Given** the ADR directory, **When** this feature merges, **Then** a new ADR records the check-environment boundary, why removing the guard and run variables gives checks no new authority, and that agent steps keep both; it extends ADR-0018. [S: IAC-4] [B: D-03] [I]

### Edge Cases

- No trusted git exists on the host: the check sees the host `PATH` without guard entries and nothing is added; a test that needs git fails as it would in CI. [I]
- `PATH` is unset or empty in the caller's environment: the check environment is built without error and adds no guard entry. [I]
- A timed-out final `run-checks` already blocks; only the feedback path changes. [S: docs/policies/spec-kit-workflow.md#workflow-runner-contract]
- A timed-out feedback check while a finding is open: the fix loop runs and may still end at the `fix-cycles` limit, as today. [P: D-06]
- Removing the run variables gives a check no runner authority: results are recorded in operator state, which a check cannot write. [S: docs/policies/spec-kit-workflow.md#workflow-runner-contract]
- Shared fixtures introduced for speed must not leak state between tests; a test that passes alone must pass in the full run, in any order. [I]

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The runner MUST give every `[checks]` command and every runner acceptance check an environment from which every agent git guard directory is removed from `PATH` (other entries keeping their order) and `BALLAST_GIT`, `BALLAST_SPEC_WORKFLOW` and `SPECKIT_WORKFLOW_RUN_ID` are removed. [S: IAC-2] [B: D-01] [B: D-02]
- **FR-002**: The check environment MUST keep dropping secret-named variables, and check commands MUST keep the existing bwrap confinement, read-only host and hidden credential paths. [B: D-01] [S: tools/spec_workflow/autonomy.py]
- **FR-003**: The same check environment MUST apply to Autonomous feedback, fix and final checks, runner acceptance checks, Chat runs and human-gated `ballast run checks`. [B: D-02] [S: tools/spec_workflow/artifacts.py]
- **FR-004**: Agent steps MUST keep the guard directory first on `PATH`, `BALLAST_GIT` and both run variables; the git guard itself MUST NOT change. [S: .specify/workflow-state/issues/146.md] [B: D-01]
- **FR-005**: The ledger tests MUST pass whatever run variables the caller sets, by clearing them for each test; `_operator_step_guard` MUST NOT change and MUST still refuse an attestation while either run variable is set. [S: IAC-1] [S: IAC-3] [B: D-04]
- **FR-006**: This repository's `[checks] timeout_minutes` MUST be `60`, edited outside an agent step, with operator trust re-recorded before merge. [B: D-05] [S: ballast.toml]
- **FR-007**: The suite's wall-clock time MUST be reduced without skipping, deleting or weakening any test; slow tests are fixed and expensive fixtures shared first, and a standard-library parallel per-module runner is added only if still needed. [S: .specify/workflow-state/issues/146.md] [P: D-07]
- **FR-008**: `python -m unittest tests/test_*.py` MUST keep running the whole suite; any new dependency MUST follow the dependency policy. [P: D-07] [S: docs/policies/dependencies.md]
- **FR-009**: When every failed feedback check timed out and no review finding is blocking or open to fix, the run MUST block at once without consuming a fix cycle, naming each timed-out command and its timeout and the recovery (raise the timeout or speed up the command, `ballast trust`, then resume or continue human-gated). [S: .specify/workflow-state/issues/146.md] [P: D-06]
- **FR-010**: Any non-timeout check failure or open finding MUST keep the existing fix loop; a timed-out final `run-checks` MUST keep blocking as today; no other `[checks]` semantics (pass/fail rules, tree freeze, protected-input checks) may change. [P: D-06] [S: .specify/workflow-state/issues/146.md]
- **FR-011**: The timeout MUST come only from the trusted `ballast.toml`, never from agent output. [S: tools/spec_workflow/autonomy.py] [S: ballast.toml]
- **FR-012**: The workflow tools changed by this feature MUST stay standard-library-only and run under `python3 -I -S`. [S: AGENTS.md]
- **FR-013**: `templates/policies/spec-kit-workflow.md` MUST describe the check environment, its scope, the timeout setting and the immediate timeout block. [S: IAC-4] [S: templates/policies/spec-kit-workflow.md]
- **FR-014**: A new ADR under `docs/adr/` MUST record the check-environment boundary and extend ADR-0018. [S: IAC-4] [B: D-03] [I]
- **FR-015**: Automated tests MUST cover the check environment (guard entries and the three variables removed, secret-named variables dropped, other entries kept in order) for a check command and an acceptance check, the ledger tests with both run variables set, the guard's refusal with either variable set, and the timeout block with its non-timeout and open-finding counter-cases. [S: AGENTS.md] [S: docs/policies/testing.md]

### Key Entities

- **Check environment**: the environment the runner gives a `[checks]` command or runner acceptance check; the caller's environment minus guard `PATH` entries, `BALLAST_GIT`, the two run variables and secret-named variables.
- **Run variables**: `BALLAST_SPEC_WORKFLOW` and `SPECKIT_WORKFLOW_RUN_ID`, set for workflow steps; their presence makes the attestation guard refuse.
- **Check timeout**: `[checks] timeout_minutes` in the protected `ballast.toml`, bounded 1-240, applied to each check command.
- **Unaddressable timeout block**: a block recorded when every failed feedback check timed out and no finding needs a fix; names the commands, their timeout and the recovery.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An Autonomous run on an unchanged `main` reaches a passing `run-checks` with 0 fix cycles spent on check failures.
- **SC-002**: The full suite on the operator's machine finishes in under 45 minutes, against 2848 s (about 47 minutes) before, with at least the same number of tests.
- **SC-003**: 0 tests fail with `git-untrusted` or an attestation error when run as a check command from a guarded caller.
- **SC-004**: A run whose only failure is a timeout blocks after 0 fix cycles instead of 3.
- **SC-005**: An operator attestation attempted with either run variable set is refused in 100% of tested cases.

## Non-goals

- Changing the git guard itself or the agent step environment. [S: .specify/workflow-state/issues/146.md]
- Changing other `[checks]` semantics: pass/fail rules, tree freeze, protected-input checks. [S: .specify/workflow-state/issues/146.md]
- CI workflow changes beyond what the faster suite needs. [S: .specify/workflow-state/issues/146.md]
- Weakening `_operator_step_guard`. [S: .specify/workflow-state/issues/146.md]
- Skipping, deleting or weakening tests to make the suite faster. [S: .specify/workflow-state/issues/146.md]
- Splitting the check into a run subset and leaving the full suite to CI; the operator did not choose it. [S: .specify/workflow-state/issues/146.md]

Every Issue acceptance criterion (IAC-1, IAC-2, IAC-3, IAC-4) is covered by an acceptance criterion above; none is a non-goal.

## Assumptions

- The immediate block fires where the runner computes the fix state, only when every failed feedback check timed out and no finding is blocking or open to fix (D-06, agent-provisional). [P: D-06]
- The suite is sped up by profiling and fixing the slowest tests and sharing expensive fixtures first; a standard-library parallel per-module runner is added only if still needed (D-07, agent-provisional). [P: D-07]
- "Well under 60 minutes" means under 45 minutes on the operator's machine, a 25% margin below the timeout; this threshold is an agent-provisional clarification, not an operator choice, and only sets the acceptance bar for AC-012 and SC-002. [I]
- The guard can reach a check through the caller's `PATH` (for example a run started from a guarded session); the check environment removes it whatever its origin. [I]
- The new ADR takes the next free number, 0020, since 0019 is used twice. [I]
- The suite's duration is measured on the operator's machine; a run outside it records the measurement as unavailable in the PR. [I]
