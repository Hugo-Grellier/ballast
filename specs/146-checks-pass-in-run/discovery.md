<!-- ballast-discovery: input evidence -->
# Discovery brief: make the [checks] test command pass inside an Autonomous run

This brief is input evidence for [spec.md](spec.md). It is not the feature's
authority: once intent is recorded, [spec.md](spec.md) and [intent.md](intent.md)
govern, and later steps do not read requirements from this file.

**Mode**: autonomous
**Issue**: #146 (snapshot `.specify/workflow-state/issues/146.md`, untrusted requirements data)

## Sources

- S-1: Issue #146 body
- S-2: Issue #146 intake scope comment (operator decisions of 2026-10-13; verified by the trusted runner, recorded as PD-0001 in specs/146-checks-pass-in-run/autonomous/record.md)
- S-3: Issue #146 comments: none
- S-4: AGENTS.md (commands, invariants, risk classes, "write a new ADR for an accepted architecture change")
- S-5: .specify/memory/constitution.md#BL-INV-003 and #BL-INV-006
- S-6: docs/policies/project/workflow.md#r2-boundaries
- S-7: docs/policies/spec-kit-workflow.md#workflow-runner-contract (`checks-implementation`, `checks-fix-N`, `run-checks` rows) and #autonomous-runs (fix loop; `[checks]` commands see neither CLI's credentials; `.venv` protected input)
- S-8: templates/policies/spec-kit-workflow.md (the tracked source of the installed, git-ignored docs/policies/spec-kit-workflow.md)
- S-9: docs/adr/0018-runner-recorded-acceptance-checks.md (acceptance checks run through the same confined argv as check commands)
- S-10: docs/adr/0004-autonomous-provisional-decisions.md
- S-11: specs/142-feature-ui-states/decisions.md (D-001, D-002)
- S-12: tools/spec_workflow/ledger.py (`_operator_step_guard`)
- S-13: tools/spec_workflow/artifacts.py (`run_commands`, `_failed_feedback`, `_check_text`, the `fix-cycles` limit block in the decision recorder)
- S-14: tools/spec_workflow/autonomy.py (`confined_env`, `CHECK_TIMEOUT = (1, 240, 30)`, `parse_checks`, `BLOCK_CATEGORIES`, `RECOVERY`, `LIMIT_RECOVERY`)
- S-15: tools/spec_workflow/agent.py (`_base_env`: guard directory prepended to `PATH`, `BALLAST_GIT` set)
- S-16: tools/spec_workflow/run.py (`_environment`: sets `BALLAST_SPEC_WORKFLOW`, `SPECKIT_WORKFLOW_RUN_ID`) and tools/spec_workflow/chat.py (same variables for Chat steps)
- S-17: templates/spec-kit/workflows/autonomous/workflow.yml (`checks-implementation`, `checks-fix-N`, `run-checks` shell steps)
- S-18: ballast.toml (`[checks]` commands, `timeout_minutes = 30`, `[autonomous] authorized_privileged_actions`)
- S-19: .github/workflows/ci.yml (CI runs `uv run --locked python -m unittest tests/test_*.py`)
- S-20: docs/policies/testing.md and docs/policies/dependencies.md
- S-21: tests/test_agent_run_ledger.py, tests/test_packet.py, tests/test_governance.py

## Need

- **User**: the operator of this repository who runs Autonomous feature runs and expects a correct feature to reach a Draft PR. [S: Issue #146 body]
- **Job to be done**: have the run's `[checks]` test command pass on a correct tree, inside the run, within the configured timeout. [S: Issue #146 body]
- **Current pain**: run `864d9151` for #142 ended at `fix-cycle limit (3)` with every review approved, because the test check failed from leaked run variables and the agent git guard, then timed out; the fix agent spent three cycles changing nothing. [S: Issue #146 body] [S: specs/142-feature-ui-states/decisions.md]
- **Intended outcome**: the `[checks]` commands of an Autonomous run pass on an unchanged `main` within the configured timeout, and an unaddressable timeout no longer consumes fix cycles. [S: Issue #146 intake scope comment]

## Examples

- `test_criterion_mapped_to_no_test_stays_missing` in `tests/test_agent_run_ledger.py` fails with `operator attestation is unavailable inside an agent step` when `BALLAST_SPEC_WORKFLOW` is set; after the change it passes with both run variables set. [S: IAC-1]
- `tests/test_packet.py` and `tests/test_governance.py` stop with `git-untrusted` when `.ballast/spec_workflow/guard/git` is first on `PATH`; run as a `[checks]` command they find the real git, as in CI. [S: Issue #146 body] [S: tools/spec_workflow/agent.py]
- The suite took 2848 s for 1666 tests on the operator's machine, over the 30-minute timeout; with `timeout_minutes = 60` and a faster suite it finishes well inside the limit. [S: Issue #146 body] [S: Issue #146 intake scope comment]
- A feedback check times out and no review finding is open: the run blocks at once, naming the timed-out command, instead of running fix cycles 1-3. [S: Issue #146 intake scope comment]

## Scope

- The runner gives `[checks]` commands and runner acceptance checks an environment without the agent git guard on `PATH` and without `BALLAST_GIT`, `BALLAST_SPEC_WORKFLOW` and `SPECKIT_WORKFLOW_RUN_ID`; bwrap confinement and secret filtering stay. [S: Issue #146 intake scope comment]
- A new ADR recording that check-environment boundary. [S: Issue #146 intake scope comment]
- Ledger tests independent of the caller's environment (clear the run variables in `setUp`), with `_operator_step_guard` unchanged. [S: Issue #146 intake scope comment]
- `[checks] timeout_minutes = 60` in `ballast.toml`, with operator trust re-recorded by the driving agent. [S: Issue #146 intake scope comment]
- Reduce the suite's wall-clock time, target well under 60 minutes on the operator's machine, without skipping, weakening or deleting tests. [S: Issue #146 intake scope comment]
- A timed-out check with no open finding blocks immediately instead of consuming fix cycles. [S: Issue #146 intake scope comment]
- Document the check environment and timeout in the spec-kit workflow policy; its tracked source is `templates/policies/spec-kit-workflow.md`. [S: Issue #146 intake scope comment] [S: templates/policies/spec-kit-workflow.md]

## Non-goals

- Changing the git guard itself or the agent step environment. [S: Issue #146 intake scope comment]
- Changing other `[checks]` semantics (pass/fail rules, tree freeze, protected-input checks). [S: Issue #146 intake scope comment]
- CI workflow changes beyond what the faster suite needs. [S: Issue #146 intake scope comment]
- Weakening `_operator_step_guard`. [S: Issue #146 body]
- Skipping, deleting or weakening tests to make the suite faster. [S: Issue #146 intake scope comment]
- Splitting the check into a run subset and leaving the full suite to CI (an Issue proposal the operator did not choose). [S: Issue #146 intake scope comment]

## Constraints

- An agent step cannot edit `ballast.toml`; the timeout edit is made outside an agent step and needs `ballast trust` (privileged action `operator-trust`, authorized in `[autonomous]`). [S: .specify/memory/constitution.md#BL-INV-003] [S: ballast.toml]
- `timeout_minutes` must stay within `CHECK_TIMEOUT` bounds 1-240. [S: tools/spec_workflow/autonomy.py]
- Workflow tools stay standard-library-only and run under `python3 -I -S`. [S: AGENTS.md]
- Any new test dependency follows the dependency policy; the gate's only pinned dependencies are `ruff` and `pyyaml`. [S: Issue #146 intake scope comment] [S: docs/policies/dependencies.md] [S: AGENTS.md]
- Changing the runner's check environment is R2 (headless-agent permission model); merging the PR is the single human approval. [S: docs/policies/project/workflow.md#r2-boundaries] [S: .specify/memory/constitution.md#BL-INV-006]
- `docs/policies/*.md` is git-ignored and installed; documentation changes go to `templates/policies/spec-kit-workflow.md`. [S: .gitignore] [S: templates/policies/spec-kit-workflow.md]
- The runner acceptance checks use the same confined argv as the `[checks]` commands, with a read-only checkout. [S: docs/adr/0018-runner-recorded-acceptance-checks.md]
- No test failure, validation or error result is silently weakened. [S: AGENTS.md]

## Permissions and data authority

- Check commands keep bwrap confinement, the read-only host, hidden credential paths and the secret-named-variable filter of `confined_env`. [S: Issue #146 intake scope comment] [S: tools/spec_workflow/autonomy.py]
- Removing the run variables from check commands removes no runner authority: the runner records results in operator state, which checks cannot write. [S: docs/policies/spec-kit-workflow.md#workflow-runner-contract]
- Agent steps keep the git guard and the run variables; only the runner's check commands lose them. [S: Issue #146 intake scope comment]
- `_operator_step_guard` keeps refusing an operator attestation while a run variable is set. [S: IAC-3]
- The timeout value comes only from the trusted `ballast.toml`, never from agent output. [S: tools/spec_workflow/autonomy.py] [S: ballast.toml]

## Success evidence

- A test that `tests/test_agent_run_ledger.py` passes with both run variables set in the environment. [S: IAC-1]
- A test that `_operator_step_guard` still fails with either run variable set. [S: IAC-3]
- Unit tests that the environment of a check command and of a runner acceptance check has no guard directory on `PATH` and none of `BALLAST_GIT`, `BALLAST_SPEC_WORKFLOW`, `SPECKIT_WORKFLOW_RUN_ID`, while secret-named variables are still dropped. [S: Issue #146 intake scope comment]
- A test that a timed-out feedback check with no open finding blocks at once, and that a non-timeout failure still enters a fix cycle. [S: Issue #146 intake scope comment]
- The run's own `run-checks` result: the test command passes within the configured timeout, with no `git-untrusted` and no attestation error. [S: IAC-2]
- Measured suite durations before and after on the operator's machine, recorded in the PR. [I]
- The fast gate passes; the full gate is recorded or listed as unavailable. [S: AGENTS.md]
- The policy section and a new ADR describe the check environment and timeout. [S: IAC-4]

## Edge, failure and permission cases

- The caller's `PATH` carries the guard directory more than once or in a later position: every guard entry is removed, other entries keep their order. [I]
- No trusted git on the host: the check command sees the host `PATH` as is; no guard is added. [I]
- A check command that times out and another that fails with a non-zero exit in the same feedback run: the fixable failure still enters a fix cycle. [P: D-06]
- A timed-out check together with an open or blocking review finding: the existing fix-loop and blocking rules apply. [P: D-06]
- A timed-out final `run-checks` (not feedback) already blocks; that behavior is unchanged. [S: docs/policies/spec-kit-workflow.md#workflow-runner-contract]
- A test that itself sets a run variable (`test_explicit_record_cannot_forge_snapshot_or_ac_check`) still sees it inside its own patch. [S: specs/142-feature-ui-states/decisions.md]
- Chat and human-gated `[checks]` runs go through the same `run_commands` core and get the same environment. [S: tools/spec_workflow/artifacts.py]
- A faster suite must keep each test's isolation; shared fixtures must not leak state between tests. [I]

## Issue acceptance criteria

- IAC-1: `tests/test_agent_run_ledger.py` passes with `BALLAST_SPEC_WORKFLOW` and `SPECKIT_WORKFLOW_RUN_ID` set in the environment.
- IAC-2: The `[checks]` test command run by an Autonomous run on an unchanged `main` passes (no `git-untrusted`, no attestation error) within the configured timeout.
- IAC-3: `_operator_step_guard` still refuses an operator attestation from an agent step.
- IAC-4: The chosen check environment and timeout are documented in `docs/policies/spec-kit-workflow.md` (and an ADR if the guard or runner environment changes).

## Known

- `_operator_step_guard` fails when `BALLAST_SPEC_WORKFLOW` or `SPECKIT_WORKFLOW_RUN_ID` is set. [S: tools/spec_workflow/ledger.py]
- `run.py` and `chat.py` set both run variables in the environment of workflow steps. [S: tools/spec_workflow/run.py] [S: tools/spec_workflow/chat.py]
- Agent steps prepend the guard directory to `PATH` and set `BALLAST_GIT`. [S: tools/spec_workflow/agent.py]
- `run_commands` passes `confined_env(dict(os.environ), None)` to each check, which only drops secret-named variables. [S: tools/spec_workflow/artifacts.py] [S: tools/spec_workflow/autonomy.py]
- The feedback, fix and final check steps all call `artifacts.py run-checks`. [S: templates/spec-kit/workflows/autonomous/workflow.yml]
- A failed feedback check, including a timeout, keeps the run in its fix loop until the `fix-cycles` limit. [S: tools/spec_workflow/artifacts.py] [S: docs/policies/spec-kit-workflow.md#autonomous-runs]
- `[checks] timeout_minutes` defaults to 30, bounded 1-240. [S: tools/spec_workflow/autonomy.py] [S: ballast.toml]
- CI runs the same unittest command with no guard or run variables. [S: .github/workflows/ci.yml]
- The operator chose decision A (check environment like CI), timeout 60, a faster suite and an immediate block. [S: Issue #146 intake scope comment]
- The run is R2 with privileged action `operator-trust` before merge. [S: Issue #146 intake scope comment] [S: ballast.toml]

## Inferred

- The guard reaches a `run-checks` command when it is on the caller's `PATH` (for example a run started from a guarded session); the check environment removes it whatever its origin. [I]
- The new ADR is numbered 0020, since 0019 is already used twice. [I]
- The block for an unaddressable timeout fires at the point where the recorder computes the fix state, when every failed feedback check timed out and no finding needs a fix. [P: D-06]
- The suite is sped up first by profiling and fixing the slowest tests and sharing expensive fixtures; a parallel per-module runner is standard-library-only and added only if still needed. [P: D-07]
- The ADR extends ADR-0018 and the runner-contract rows rather than ADR-0004. [I]

## Undecided

None.

## Decisions

### D-01: Which environment the runner gives `[checks]` commands
- **Status**: settled
- **Question**: Do check commands run without the git guard and run variables, or keep them with tests made independent?
- **Why it matters**: decides whether the change touches the runner (R2, ADR) or only tests.
- **Sources**: [S: Issue #146 body] [S: Issue #146 intake scope comment] [S: tools/spec_workflow/artifacts.py]
- **Options**:
  - A — no guard on `PATH`, no `BALLAST_GIT`, `BALLAST_SPEC_WORKFLOW`, `SPECKIT_WORKFLOW_RUN_ID`; bwrap and secret filtering stay. Consequence: checks run as in CI; R2 runner change with an ADR.
  - B — keep the guard and make each affected test independent of it. Consequence: every future git-using test must work around the guard.
- **Recommended default**: A, because the operator chose it.
- **Answer**:
- **Resolution**: A, for `[checks]` commands and runner acceptance checks [S: Issue #146 intake scope comment].

### D-02: Which runner check paths get that environment
- **Status**: settled
- **Question**: Does the environment apply to Autonomous `run-checks` only, or to every runner check path?
- **Why it matters**: decides whether the change lives in the shared `run_commands` core.
- **Sources**: [S: Issue #146 intake scope comment] [S: tools/spec_workflow/artifacts.py] [S: docs/adr/0018-runner-recorded-acceptance-checks.md]
- **Options**:
  - A — the shared core: Autonomous feedback and final checks, acceptance checks, Chat and `ballast run checks`. Consequence: one environment for every `[checks]` command.
  - B — Autonomous only. Consequence: Chat checks keep failing the same tests.
- **Recommended default**: A, because the operator's decision covers "the runner gives `[checks]` commands", which all run through `run_commands`.
- **Answer**:
- **Resolution**: A; the intake decision names every `[checks]` command and runner acceptance check, and both use `run_commands`/`confined_argv` [S: Issue #146 intake scope comment] [S: tools/spec_workflow/artifacts.py].

### D-03: Whether a new ADR is needed
- **Status**: settled
- **Question**: Is the check-environment boundary recorded in a new ADR?
- **Why it matters**: decides the documentation deliverables (IAC-4).
- **Sources**: [S: Issue #146 intake scope comment] [S: AGENTS.md] [S: IAC-4]
- **Options**:
  - A — a new ADR. Consequence: the R2 boundary is recorded where design is governed.
  - B — policy text only. Consequence: an accepted runner-contract change without an ADR.
- **Recommended default**: A.
- **Answer**:
- **Resolution**: A; the intake scope comment asks to "record the boundary in a new ADR" [S: Issue #146 intake scope comment].

### D-04: How the ledger tests are isolated
- **Status**: settled
- **Question**: Are the ledger tests isolated, or is `_operator_step_guard` relaxed?
- **Why it matters**: relaxing the guard would weaken a security check.
- **Sources**: [S: Issue #146 body] [S: Issue #146 intake scope comment] [S: tools/spec_workflow/ledger.py]
- **Options**:
  - A — clear both variables in the tests' `setUp`; guard unchanged. Consequence: tests pass under any caller.
  - B — relax the guard. Consequence: contradicts IAC-3.
- **Recommended default**: A.
- **Answer**:
- **Resolution**: A [S: Issue #146 intake scope comment].

### D-05: The `[checks]` timeout for this repository
- **Status**: settled
- **Question**: What `timeout_minutes` does this repository use, and who edits it?
- **Why it matters**: decides whether IAC-2 is reachable and which privileged action the PR needs.
- **Sources**: [S: Issue #146 intake scope comment] [S: ballast.toml] [S: tools/spec_workflow/autonomy.py]
- **Options**:
  - A — 60, edited outside an agent step, operator trust re-recorded by the driving agent. Consequence: `operator-trust` before merge.
  - B — keep 30 and rely only on a faster suite. Consequence: little margin.
- **Recommended default**: A.
- **Answer**:
- **Resolution**: A [S: Issue #146 intake scope comment].

### D-06: When a timed-out check blocks immediately
- **Status**: assumed
- **Question**: Under which exact condition, and with which block, does a timed-out feedback check stop the run instead of starting a fix cycle?
- **Why it matters**: decides the recorder logic, the block text and which cases still get fix cycles.
- **Sources**: [S: Issue #146 intake scope comment] [S: tools/spec_workflow/artifacts.py] [S: tools/spec_workflow/autonomy.py]
- **Options**:
  - A — block at once when every failed feedback check timed out and no review finding is blocking or open to fix; any non-timeout failure or open finding keeps the fix loop. The block names the timed-out command and its timeout and tells the operator to raise `timeout_minutes` or speed up the command, `ballast trust`, then resume or continue human-gated. Consequence: fix cycles are used only when a fix could help.
  - B — block on any timed-out check, even alongside fixable failures. Consequence: a fixable failure in the same run is not fixed.
- **Recommended default**: A, because it follows "with no open finding" literally and keeps the fix loop for anything a fix step can address.
- **Answer**:
- **Resolution**: A assumed. It only stops a run earlier in a case where fix cycles cannot help, changes no approval or authority, and the condition and message are reversible before merge.

### D-07: How to reduce the suite's wall-clock time
- **Status**: assumed
- **Question**: Which approach reduces the suite's duration without weakening tests?
- **Why it matters**: decides whether the `[checks]` and CI commands, or the dependencies, change.
- **Sources**: [S: Issue #146 intake scope comment] [S: docs/policies/dependencies.md] [S: .github/workflows/ci.yml] [S: ballast.toml]
- **Options**:
  - A — profile, fix the slowest tests and share expensive fixtures first; add a standard-library parallel per-module runner only if still needed, keeping `python -m unittest tests/test_*.py` working. Consequence: no new dependency; command changes only if parallelism is needed.
  - B — add a third-party parallel runner. Consequence: a dependency evaluation and a lock change.
- **Recommended default**: A, because it needs no dependency and leaves the commands unchanged when possible.
- **Answer**:
- **Resolution**: A assumed. It keeps every test, adds no dependency and is reversible; any command change follows the same `ballast.toml` and trust path as D-05.

## Question metrics

- **Rounds**: 0
- **Questions asked**: 0
- **Assumptions adopted**: 2
