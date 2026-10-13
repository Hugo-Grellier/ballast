# Research: Make the [checks] test command pass inside an Autonomous run

Phase 0 decisions for [plan.md](plan.md). Every decision here is agent-provisional (Autonomous run `a060b968`); merging the PR is the only human approval.

## R1: Where the check environment is built

- **Decision**: One function, `autonomy.check_env(env)`, builds the check environment. `artifacts.run_commands` passes the process environment through it in place of the bare `confined_env(dict(os.environ), None)`. `check_env` first applies `confined_env(env, None)` (secret-named variables dropped, unchanged), then drops `BALLAST_GIT`, `BALLAST_SPEC_WORKFLOW` and `SPECKIT_WORKFLOW_RUN_ID` and removes every guard entry from `PATH`.
- **Rationale**: every check path already goes through `run_commands`: Autonomous feedback, fix and final checks (`run_checks`), runner acceptance checks (`_acceptance_checks`, `read_only=True`) and Chat or human-gated `ballast run checks` (`project_checks`). One change there covers FR-003 and keeps one source of truth. `confined_argv` keeps receiving the operator's environment, because it reads `HOME`, `XDG_RUNTIME_DIR` and the credential locations to hide; the bwrap argv, and so the confinement, does not change (FR-002).
- **Alternatives considered**: filtering in each caller (three copies of the rule; a missed caller re-opens the bug); clearing the variables in the workflow YAML shell steps (misses Chat and human-gated checks and the acceptance checks, and the YAML is not where the runner's trust rules live).

## R2: How a guard entry on `PATH` is recognized

- **Decision**: An entry is a guard entry when its path, normalized, equals this install's guard directory (`tools/spec_workflow/guard`, installed as `.ballast/spec_workflow/guard`), or when its last two components are `spec_workflow/guard`. Every match is removed; the others keep their order. Empty entries are kept as they are, and an unset or empty `PATH` stays unset or empty. The guard directory constant moves to `autonomy.GUARD` and `agent.GUARD` refers to it, so the agent step and the check filter read one value.
- **Rationale**: the guard can reach a check from any caller (the spec's Assumptions), including a session guarded by another checkout's `.ballast/spec_workflow/guard`. Matching the fixed `spec_workflow/guard` suffix catches those without resolving links in a writable checkout. Removing a non-guard directory that happens to end in `spec_workflow/guard` costs nothing a CI run would have.
- **Alternatives considered**: matching only this install's exact path (misses a guard from another checkout, the case recorded in #142); probing each entry for a `git` that execs `BALLAST_GIT` (reads agent-writable files at check time).

## R3: The agent step environment is untouched

- **Decision**: `agent._base_env` and the interactive Chat launch keep prepending the guard and setting `BALLAST_GIT`; `run._environment` and `chat.py` keep setting both run variables. Only the `GUARD` constant's home moves (R2); its value is the same.
- **Rationale**: FR-004 and the Non-goals. The check filter is applied by the runner after the step environment is built, so nothing an agent step sees changes (AC-006).

## R4: Why removing the guard and run variables gives a check no authority

- **Decision**: Record in ADR-0021 that a check command keeps bwrap confinement with a read-only host, a writable checkout minus protected inputs (read-only for acceptance checks), hidden credential paths and the secret filter. The run variables grant nothing: run state, the decision log and the ledger's runner events are written by the runner in operator state, which a check cannot write. The git guard limits an agent's `git` options because Claude's allowlist matches command text; a check runs trusted commands from protected `ballast.toml`, under the same bwrap that bounds a guarded agent, so the host git reaches nothing the guarded git could not.
- **Rationale**: AC-020 and the R2 boundary. The removed variables also stop `ledger._operator_step_guard` from refusing inside a check, but a check still cannot write operator state, so an attestation from a check has nowhere to land.
- **Alternatives considered**: keeping the guard and changing each git-using test (D-01 option B, not chosen by the operator).

## R5: Ledger test isolation

- **Decision**: `tests/test_agent_run_ledger.py` clears `BALLAST_SPEC_WORKFLOW` and `SPECKIT_WORKFLOW_RUN_ID` for every test, with a `patch.dict(os.environ)` started in each test class's `setUp` and stopped by `addCleanup`, through one shared helper. Tests that set a variable inside their own `patch.dict` (such as `test_explicit_record_cannot_forge_snapshot_or_ac_check`) keep working, because their patch nests inside the per-test one. `_operator_step_guard` does not change. A new test asserts the guard refuses with each variable set alone.
- **Rationale**: FR-005 and D-04. Per-test patching keeps every test independent of the caller, and `patch.dict` restores the environment even when a test fails. Python 3.11 is the floor (`pyproject.toml`), so `enterContext` (3.11) is also available; `addCleanup` matches the surrounding tests.
- **Alternatives considered**: `setUpModule` patching (leaks into a module run alongside other modules if stopping fails, and is not "for each test"); relaxing the guard (D-04 option B, contradicts IAC-3).

## R6: Recognizing an unaddressable timeout

- **Decision**: In `artifacts.record_decision`, for `implementation-review` (first record and `--recheck`) in a run with the fix loop, when the latest feedback run has failed checks, every failed check has `timed_out` true, and `_blocking(reviews)` and `_open_to_fix(reviews)` are both empty, the recorder blocks before it sets `fix-pending` or the limit. The check runs before the existing `limit` rule, so a timeout-only failure at the last cycle also gets this block instead of the fix-cycle limit. Any non-timeout failure or any blocking or open finding leaves today's rules in place (AC-016, AC-017). The final `run-checks` path does not change (AC-018).
- **Rationale**: D-06. The recorder is the only point that knows both the feedback checks and the reviews. Blocking before the state change means no fix cycle is consumed (AC-015, SC-004).
- **Alternatives considered**: blocking in `run-checks --feedback` (runs before the reviews, so it cannot know whether a finding is open); blocking on any timeout (D-06 option B).

## R7: How the timeout block is represented and resumed

- **Decision**: A new limit kind `check-timeout` in `autonomy.LIMIT_KINDS`, with label `check timeout` and a `LIMIT_RECOVERY` entry: "Raise [checks] timeout_minutes in ballast.toml or speed up the named commands, run ballast trust, then resume, or continue human-gated." It is not in `FIXED_LIMITS`, so `ballast run resume` accepts it. The condition names each timed-out command and the timeout applied to it. On resume, `run._reentry` maps a `check-timeout` block to the feedback checks step before the blocked recorder: `checks-implementation` for `record-implementation-review`, `checks-fix-N` for `record-fix-review-N`. Resume already re-reads `[checks]` from the trusted `ballast.toml` each time `run-checks` runs, and the launcher refuses an untrusted `ballast.toml` before any step.
- **Rationale**: a timeout is an exhausted limit (class "exhausted limits"), so the existing limit vocabulary, validation and status output apply without a new category. Without the re-entry mapping, resume would re-enter at the recorder, re-read the stale feedback result and block again; `ballast.toml` is a protected input, so the tree-digest re-entry rule (#21 R6) does not see a timeout change. Re-entering at the checks step reruns the checks with the new timeout and then the reviews, as the workflow already does after `validate-implementation`. For `checks-implementation`, the existing `reset` (re-entry at or before `record-implementation-review`) applies; for `checks-fix-N` the fix state stays `review-pending`, so the feedback step has work.
- **Alternatives considered**: a new block category (more vocabulary, a new `BLOCK_CLASSES` row and status wording for the same meaning); a `postcondition` block with recovery in the condition (resume would re-enter at the recorder and block again).

## R8: The timeout each result records

- **Decision**: Each `run_commands` result gains `timeout_seconds`, the timeout applied to that command (the `[checks]` timeout, or the run's remaining wall time when smaller). The block condition names it, and adds "the run's remaining wall time" when that was the smaller bound.
- **Rationale**: FR-009 asks for each command's timeout; a timeout cut short by the wall-time remainder is also unaddressable by a fix step, but raising `timeout_minutes` alone would not help, and the operator needs to see that. The field is additive: `read_feedback` and `checks.json` readers ignore unknown keys.
- **Alternatives considered**: reading `parse_checks` again at block time (misreports a wall-time cut, and could differ from what ran).

## R9: Speeding up the suite

- **Decision**: Profile per test and per module with a throwaway standard-library timing runner kept outside the repository, on the operator's machine. Fix the slowest tests first (avoidable sleeps, waits on real timeouts that a stand-in clock or a shorter injected bound can replace without changing what is asserted, repeated `git init` or install fixtures). Then share expensive read-only fixtures per class (`setUpClass`) where a test does not modify them. Add a standard-library parallel per-module runner only if the sequential suite still exceeds the 45-minute bar (SC-002). Every change keeps the test count, the assertions and each test's isolation; a test that passes alone passes in the full run.
- **Rationale**: D-07. The suite has 23 modules and 1666 tests (#146); the 2848 s baseline is only about 5% over the 45-minute bar, so targeted fixes are expected to be enough. Without a parallel runner, `[checks]` and CI commands stay as they are.
- **If the parallel runner is needed**: a `tests/parallel.py` that runs `python -m unittest <module>` per module in a bounded process pool, prints each module's output and fails when any module fails. `python -m unittest tests/test_*.py` keeps working and is still what CI runs unless CI also needs it. Changing the `[checks]` command follows the same `ballast.toml` and `ballast trust` path as the timeout (R10). Modules must not share host state (systemd units, fixed ports, fixed paths); the profile step lists any that do.
- **Alternatives considered**: a third-party runner such as `pytest-xdist` (D-07 option B; a dependency evaluation and a lock change for a gain the targeted fixes should give).

## R10: The timeout edit and trust

- **Decision**: `ballast.toml` `[checks] timeout_minutes = 60` is edited by the driving agent outside any agent step, followed by `ballast trust` (privileged action `operator-trust`, authorized in `[autonomous]`). An agent step never edits `ballast.toml`; it would fail as a protected-input change.
- **Rationale**: D-05 and FR-006, FR-011. The value stays in the 1-240 bound of `CHECK_TIMEOUT`.

## R11: What this run's own checks prove

- **Decision**: This repository pins `ref = "v1.0.0"`, so this run's own `run-checks` uses the pinned v1.0.0 runner, not the runner changed here. The ledger isolation (R5), the faster suite (R9) and the 60-minute timeout (R10) apply to this run; the check environment (R1) does not until a release is pinned. AC-014 and SC-001 are verified by an Autonomous run that uses this checkout's runner (`BALLAST_STANDARD_DIR` set to the checkout, per `ballast.toml`'s comment) when the host allows it; otherwise they are recorded as a deferred operator task after the release that ships this change (ADR-0017), and the PR says so.
- **Rationale**: report what the evidence proves; a v1.0.0 run passing would not prove FR-001.
- **Risk**: if this run's own guarded `run-checks` hits `git-untrusted` under v1.0.0, the new timeout block does not exist yet either; the run would end at the fix-cycle limit as #142 did. The PR records that case as evidence of the old runner, not of this change.

## R12: ADR number

- **Decision**: ADR-0021 `docs/adr/0021-check-command-environment.md`, extending ADR-0018. 0019 is used twice already.

## R13: Risk recheck

- **Decision**: R2 stands. The change narrows what reaches a check (fewer variables, fewer `PATH` entries) inside unchanged confinement; it changes no download, no executed program from the checkout, no ignore rule and no agent permission. The required reviews are engineering, security (runner trust model, agent tool boundary), test (environment, ledger, timeout block, suite speed) and documentation (policy, ADR).
