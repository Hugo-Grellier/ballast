---

description: "Task list for Make the [checks] test command pass inside an Autonomous run"
---

# Tasks: Make the [checks] test command pass inside an Autonomous run

**Input**: Design documents from `specs/146-checks-pass-in-run/`
**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/check-environment.md](contracts/check-environment.md), [contracts/timeout-block.md](contracts/timeout-block.md), [quickstart.md](quickstart.md)

**Risk**: R2, Autonomous run `a060b968`. Every decision in this file is agent-provisional; merging the PR is the only human approval.

**Acceptance evidence**: Every behavior criterion has a test or verification task that cites it. AC-001 to AC-006 map to `unittest` cases in `tests/test_autonomy.py`, `tests/test_autonomous_artifacts.py`, `tests/test_spec_workflow.py` and `tests/test_autonomous_run.py`. AC-007 to AC-009 map to `tests/test_agent_run_ledger.py`. AC-015 to AC-018 map to `tests/test_autonomous_artifacts.py` and `tests/test_autonomous_recovery.py`. AC-019 and AC-020 map to wording tests in `tests/test_governance.py`. AC-011 to AC-013 are verified by the suite profile in `suite-profile.md` and a diff check. AC-010 and AC-014 are deferred operator checks (see below). T030 writes `acceptance-evidence.json`.

**Operator-only checks**: Two tasks are `[DEFERRED-TO-PR]`. An agent step cannot do them: `ballast.toml` is a protected input, and the pinned v1.0.0 runner cannot prove the new check environment ([research R10, R11](research.md#r11-what-this-runs-own-checks-prove)).
- T020: the driving agent edits `timeout_minutes` outside any step and runs `ballast trust` (AC-010).
- T021: a run on this checkout's runner, or a run after the release, proves AC-014 and SC-001 (plan review F-003).

No implementing step edits `ballast.toml`.

**Workflow-owned steps**: The full gate, quickstart runs, reviews, converge and spec reconciliation are not tasks. The authoritative full-suite duration after this change is the `seconds` that the run's own `run-checks` records on the operator's machine. The PR quotes it next to the 2848 s baseline (AC-012, SC-002). What the workflow-owned steps must check is in [quickstart.md](quickstart.md) and [plan.md](plan.md).

**Verification commands**: Each command matches an `[agents.permissions] extra_allow` rule in `ballast.toml`. Run one command per invocation, without `&&`, pipes or a leading `VAR=value`:

- `uv run --locked python -m unittest tests/test_autonomy.py` (and likewise any single `tests/test_*.py` module, or a dotted `tests.test_module.Class.test_method`)
- `uv run --locked ruff check`
- `uv run --locked ruff format --check`

Read-only `git status`, `git diff`, `git log` and `git show` are also allowed. A test that needs the run variables set sets them inside the test (`patch.dict` or a child process `env=`), never on the command line.

**After the resume at `validate-plan`** (HD-0001 in the [run record](autonomous/record.md)): the branch was rebased on `main` at 617df9c. `main` now holds `docs/adr/0020-autonomous-stop-rule.md`, so this feature's ADR is 0021. Outside any step, the driving agent applied T020 and [D-001](decisions.md) in commit bd80a3e: `[checks]` now runs `uv run --locked python tests/parallel.py` with `timeout_minutes = 60`. It then ran `ballast trust`. T001 to T030 stay done. Only T031 to T033 are new, and they settle the second plan review.

**Second plan review findings settled here** ([reviews/plan.md](reviews/plan.md), PD-0014):

- F-001: ADR-0021 extends ADR-0010 but does not cite ADR-0020, which amends ADR-0010. T031 adds the citation and T032 tests it.
- F-002: `spec.md` and `discovery.md` still name the ADR 0020. That is a wording clarification for spec reconciliation, a workflow-owned step. No task edits `spec.md`, so the `spec_digest` in `acceptance-evidence.json` stays valid.
- F-003: the PR states both commands: `[checks]` runs `tests/parallel.py`, while CI and `AGENTS.md` keep `python -m unittest tests/test_*.py`. It also states the measured `run-checks` seconds for SC-002 and keeps AC-014 and SC-001 deferred to T021. The PR is workflow-owned, so this is not a task.

**First plan review findings settled here** (PD-0006):

- F-001: the wall-time case keeps the resumable `check-timeout` kind from the contract. Its condition says that the run's wall time ran out instead of naming a `timeout_minutes` value. T017 implements that wording and T019 tests it.
- F-002: the timeout-only rule goes in `record_decision` right after `review_rule(...)` and `evidence` are computed. It comes before `if rule == "block":`, the `limit` block, `_check_dispositions` and the required-kinds check. It applies only when `point == "implementation-review"` and `fix_loop(feature)`. T019 asserts that the fix state and the cycle count are unchanged on both the first record and `--recheck`.
- F-003: T021 defers AC-014 and SC-001. The PR must not cite this run's v1.0.0 `run-checks` as evidence of FR-001.

**Organization**: `tools/spec_workflow/autonomy.py` holds the shared constants and `check_env`, so it is foundational. The other files are edited as follows:

- `tools/spec_workflow/artifacts.py`: `run_commands` for US1, then `timeout_seconds` and the recorder rule for US4.
- `tools/spec_workflow/run.py`: `_reentry` for US4.
- Test files: tasks that edit the same file are never `[P]` with each other.

US3's speed-ups run after the new tests exist, so the after-profile includes them.

## Format: `[ID] [P?] [Story?] Description [(depends on ...)]`

- **[P]**: Can run in parallel with other ready tasks once any listed dependencies are satisfied. Tasks that edit the same file never run in parallel.
- **[Story?]**: The user story a task belongs to (US1 to US5).
- **(depends on ...)**: Explicit dependency on earlier task IDs.
- Test and verification tasks cite the acceptance criterion IDs they prove.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Record the suite baseline before any test file changes.

- [X] T001 Profile the unchanged suite and write `specs/146-checks-pass-in-run/suite-profile.md`. Do this before any edit under `tests/`.
  - Run `uv run --locked python -m unittest tests/test_<module>.py` once for each `tests/test_*.py` module, one invocation each, and record the module's `Ran N tests in X s` line. Add `--durations 15` when the interpreter supports it (Python ≥ 3.12) to list the slowest tests. A module that runs longer than the tool's foreground limit runs in the background.
  - Record a table with module, test count, seconds and the slowest tests, plus the totals.
  - Record the reference baseline from #146: 1666 tests in 2848 s on the operator's machine.
  - Record any module that shares host state (systemd units, fixed ports, fixed paths), per research R9.
  - This is the before-measurement for AC-011 and AC-012.

No other setup: the tools stay standard-library-only, and no dependency, directory or configuration is added.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The shared constants, `check_env` and the new limit kind that every story uses.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T002 In `tools/spec_workflow/autonomy.py`, add the following per [contracts/check-environment.md](contracts/check-environment.md):
  - `GUARD`: the same path `agent.GUARD` has today, `tools/spec_workflow/guard` next to `autonomy.py`, built the way `agent.py` builds `HERE / "guard"`.
  - `RUN_VARIABLES = ("BALLAST_SPEC_WORKFLOW", "SPECKIT_WORKFLOW_RUN_ID")`.
  - A pure `check_env(env: dict[str, str]) -> dict[str, str]`:
    - Start from `confined_env(env, None)`, then drop `BALLAST_GIT` and each name in `RUN_VARIABLES`.
    - When `PATH` is present, split it on `os.pathsep` and drop each entry whose `os.path.normpath` equals `os.path.normpath(GUARD)` or whose last two components are `spec_workflow` and `guard`. Rejoin the rest in order, keeping empty entries.
    - An empty `PATH` stays empty and an absent one stays absent.
    - Never read `os.environ` or the filesystem, and never mutate the argument.
  - A docstring that names the boundary (ADR-0021).

  In `tools/spec_workflow/agent.py`, replace `GUARD = HERE / "guard"` with `GUARD = autonomy.GUARD`; its value and every use stay the same. (depends on T001)
- [X] T003 In `tools/spec_workflow/autonomy.py`, add the `check-timeout` limit per [contracts/timeout-block.md](contracts/timeout-block.md):
  - Append `"check-timeout"` to `LIMIT_KINDS`, and not to `FIXED_LIMITS`, so `resumable()` accepts it.
  - Add `LIMIT_LABELS["check-timeout"] = "check timeout"`.
  - Add `LIMIT_RECOVERY["check-timeout"]` with the contract's text: "Raise [checks] timeout_minutes in ballast.toml or speed up the named commands, run ballast trust, then resume, or continue human-gated."
  - Check that every other table keyed by limit kind in `autonomy.py`, `agent.py` and `run.py` either lists the kind or falls back safely, and add it where a table must list every kind. (depends on T002)

**Checkpoint**: The foundation is ready. US1, US2 and US4 can begin.

---

## Phase 3: User Story 1 - Check commands run in an environment like CI (Priority: P1) 🎯 MVP

**Goal**: Every `[checks]` command and runner acceptance check runs without the git guard on `PATH`, `BALLAST_GIT` or the run variables, inside unchanged confinement. Agent steps keep all three.

**Independent Test**: Build a check environment from a guarded caller with both run variables and a secret-named variable. None of them reaches the check, and every other variable and `PATH` entry does, in order.

### Acceptance tests for User Story 1

- [X] T004 [P] [US1] In `tests/test_autonomy.py`, add a `CheckEnvTests` class covering `autonomy.check_env`:
  - The caller has `GUARD` on `PATH` twice: first and after other entries.
  - A second checkout's `/x/.ballast/spec_workflow/guard` is on `PATH`.
  - `BALLAST_GIT`, `BALLAST_SPEC_WORKFLOW`, `SPECKIT_WORKFLOW_RUN_ID` and `GITHUB_TOKEN` are set.
  - Assert that every guard entry and those four variables are gone, the other `PATH` entries (including an empty one) keep their order, and every other variable is kept with its value. [AC-001, AC-004]
  - Also assert that an unset `PATH` stays unset, an empty `PATH` stays empty, the argument dict is not mutated, and no key is added. [AC-004, edge cases]

  Run `uv run --locked python -m unittest tests/test_autonomy.py`. (depends on T002)
- [X] T005 [P] [US1] Add a test for AC-006 in `tests/test_spec_workflow.py`, next to the guard-script tests, or in the module that already imports `agent`.
  - The environment `agent._base_env` builds still has `str(agent.GUARD)` as the first `PATH` entry and `BALLAST_GIT` set.
  - `agent.GUARD == autonomy.GUARD`.

  In `tests/test_autonomous_run.py`, assert that `run._environment` still sets `BALLAST_SPEC_WORKFLOW` and `SPECKIT_WORKFLOW_RUN_ID`. Do not change `agent._base_env`, `run._environment` or `chat.py`. Run each module with `uv run --locked python -m unittest tests/<module>.py`. [AC-006] (depends on T002)

### Implementation for User Story 1

- [X] T006 [US1] In `tools/spec_workflow/artifacts.py` `run_commands`, replace `env = autonomy.confined_env(dict(os.environ), None)` with `env = autonomy.check_env(dict(os.environ))`. Keep passing `env=dict(os.environ)` to `autonomy.confined_argv`, so the bwrap argv, the read-only host and the hidden credential paths do not change. Update the docstring: commands get the check environment (ADR-0021). (depends on T002)

### Tests through the check paths for User Story 1

- [X] T007 [US1] In `tests/test_autonomous_artifacts.py`, patch `os.environ` with a guarded caller: `GUARD` first on `PATH`, `BALLAST_GIT`, both run variables and `GITHUB_TOKEN`. Record `subprocess.run` and assert:
  - `run_commands` passes an `env` without the guard entry, the three variables or the token. Its argv equals `autonomy.confined_argv(..., env=dict(os.environ), ...)` built from the same inputs. [AC-001]
  - A runner acceptance check through `_acceptance_checks` gets the same `env` and a read-only checkout (`writable_checkout=False` in the argv). [AC-002]
  - `run_checks(feedback=True)`, the final `run_checks` and `project_checks` each reach `subprocess.run` with that same `env`. [AC-003]

  Reuse the file's existing fakes and `PASS_BWRAP` stub. Run `uv run --locked python -m unittest tests/test_autonomous_artifacts.py`. (depends on T006)
- [X] T008 [US1] In `tests/test_autonomous_artifacts.py`, add a test gated by `@unittest.skipUnless(_bwrap_works(), "needs bwrap with user namespaces")`, as the file's existing real-bwrap test is.
  - From a guarded caller (`autonomy.GUARD` first on `PATH`, `BALLAST_GIT` and both run variables), run `run_commands` with the command `env; command -v git` and `keep_output=True`, or capture stdout.
  - Assert that the output has no `spec_workflow/guard` entry, no `BALLAST_GIT=`, `BALLAST_SPEC_WORKFLOW=` or `SPECKIT_WORKFLOW_RUN_ID=`, and that `command -v git` names a host git outside the guard directory.

  This is the `tests/test_packet.py` and `tests/test_governance.py` case from #142 reduced to its cause. Run `uv run --locked python -m unittest tests/test_autonomous_artifacts.py`. [AC-005] (depends on T007)

**Checkpoint**: US1 is complete. Every check path builds the CI-like environment, and agent steps are unchanged.

---

## Phase 4: User Story 2 - Ledger tests pass under any caller without weakening the attestation guard (Priority: P1)

**Goal**: `tests/test_agent_run_ledger.py` passes whatever run variables the caller sets, and `_operator_step_guard` is unchanged.

**Independent Test**: Run the ledger tests with both run variables set and they pass. Call the guard with either variable set and it refuses.

### Implementation for User Story 2

- [X] T009 [P] [US2] In `tests/test_agent_run_ledger.py`, add one module-level helper, for example `_clear_run_variables(test: unittest.TestCase) -> None`:
  - It starts `patch.dict(os.environ)`, deletes `BALLAST_SPEC_WORKFLOW` and `SPECKIT_WORKFLOW_RUN_ID` when present, and registers `test.addCleanup(patcher.stop)`.
  - Call it first in `setUp` of every `TestCase` class in the file: `LedgerTests`, `SpecCriteriaTests`, `CommitFingerprintTests`, `AcceptancePacketEventTests`, `DemoCaptureEventTests`, `ChatModeLedgerTests` and any other. Add a `setUp` that calls `super().setUp()` where a class has none.
  - Tests that set a variable in their own `patch.dict` keep working unchanged, because their patch nests inside this one.
  - Do not touch `tools/spec_workflow/ledger.py`. (research R5) (depends on T002)

### Acceptance tests for User Story 2

- [X] T010 [US2] In `tests/test_agent_run_ledger.py`, add an `OperatorStepGuardTests` class that calls the ledger's operator attestation path, through `_operator_step_guard` or its public caller. Use a `subTest` for each case: `BALLAST_SPEC_WORKFLOW` alone, `SPECKIT_WORKFLOW_RUN_ID` alone and both, each set with `patch.dict(os.environ, ...)`. Assert that it refuses with `operator attestation is unavailable inside an agent step`. Confirm with `git diff main -- tools/spec_workflow/ledger.py` that the guard is unchanged. [AC-008] (depends on T009)
- [X] T011 [US2] In `tests/test_agent_run_ledger.py`, add an `IsolationTests` class:
  - (a) With both run variables set by an outer `patch.dict`, construct each other `TestCase` class in the module for one of its test methods, call `setUp()`, assert that neither variable is in `os.environ`, then call `doCleanups()` and assert that both are restored.
  - (b) Run `test_criterion_mapped_to_no_test_stays_missing` and `test_stale_manifest_does_not_block_runner_snapshot` in a child process with `subprocess.run([sys.executable, "-m", "unittest", "tests.test_agent_run_ledger.LedgerTests.<name>"], env={**os.environ, "BALLAST_SPEC_WORKFLOW": "1", "SPECKIT_WORKFLOW_RUN_ID": "x"}, cwd=<repo root>)` and assert exit 0. Use the class that actually holds each test.
  - (c) Assert that `test_explicit_record_cannot_forge_snapshot_or_ac_check` still sees its own variable and still asserts the refusal: run it the same way and check it passes and keeps its assertion.

  Run `uv run --locked python -m unittest tests/test_agent_run_ledger.py`. [AC-007, AC-009] (depends on T010)

**Checkpoint**: US2 is complete. The ledger tests are independent of the caller, and the guard is unchanged.

---

## Phase 5: User Story 4 - An unaddressable timeout blocks at once (Priority: P2)

US4 comes before US3 in execution because it adds tests that US3's after-profile must include. Its priority stays P2.

**Goal**: When every failed feedback check timed out and no finding is blocking or open to fix, the run blocks at once with a resumable `check-timeout` limit, without consuming a fix cycle. Resume reruns the feedback checks.

**Independent Test**: Record a feedback result where every failure timed out and no finding is open: the run blocks and the cycle count is unchanged. Add a non-timeout failure: a fix cycle starts.

### Implementation for User Story 4

- [X] T012 [US4] In `tools/spec_workflow/artifacts.py` `run_commands`, add `"timeout_seconds"` to each result: the applied timeout as an int, `timeout` when `left is None` or `timeout <= left`, else `int(left)`. Leave every existing field unchanged ([data-model](data-model.md#check-result-additive-field), research R8). (depends on T006)
- [X] T013 [US4] In `tools/spec_workflow/artifacts.py`, add `_timeout_only(feature, reviews) -> list[dict]`.
  - It returns the latest feedback failures (`_failed_feedback(feature)`) when there is at least one, all have `timed_out` true, and `_blocking(reviews)` and `_open_to_fix(reviews)` are both empty. Otherwise it returns `[]`.
  - Add `_timeout_condition(feature, failed) -> str`, which builds `check timeout reached: check 'CMD' timed out after M min[, ...]; no review finding is open, so a fix step cannot address it` with commands shown with `repr`, as `_check_text` does.
    - `M` is `timeout_seconds // 60`.
    - When a result's `timeout_seconds` is below the trusted `[checks] timeout_minutes * 60` from `autonomy.parse_checks`, that entry reads `check 'CMD' timed out when the run's wall time ran out (S s)` instead (plan review F-001).
    - A result without `timeout_seconds`, from an older run, uses the configured timeout.
    - Truncate the text to the 4000-character block limit. (depends on T012)
- [X] T014 [US4] In `tools/spec_workflow/artifacts.py` `record_decision`, insert the rule right after `rule, reasons = review_rule(feature, point, reviews)` and `evidence = ...`, before `if rule == "block":` (plan review F-002).
  - The rule runs when `point == "implementation-review"` and `fix_loop(feature)`, for the first record and for `--recheck`.
  - When `_timeout_only(feature, reviews)` is not empty, call `_block(feature, "limit", autonomy.limit_condition("check-timeout", _timeout_condition(feature, failed)), evidence=evidence, limit="check-timeout")`.
  - Leave every later rule unchanged, and leave the final `run-checks` path unchanged. (depends on T003, T013)
- [X] T015 [US4] In `tools/spec_workflow/run.py` `_reentry`, when `block.get("category") == "limit"` and `block.get("limit") == "check-timeout"`, map the blocked step to its feedback checks step: `record-implementation-review` → `checks-implementation`, and `record-fix-review-N` → `checks-fix-N`.
  - Use the mapped step only when it is in `steps`.
  - The changed-input loop keeps picking the earliest step.
  - Add one line to the docstring. (depends on T003)

### Acceptance tests for User Story 4

- [X] T016 [P] [US4] In `tests/test_autonomy.py`, assert the following. Run `uv run --locked python -m unittest tests/test_autonomy.py`. [AC-015] (depends on T003, T004)
  - `"check-timeout"` is in `LIMIT_KINDS` and not in `FIXED_LIMITS`.
  - `resumable()` accepts a `limit`/`check-timeout` block.
  - Block validation accepts it.
  - `LIMIT_LABELS` and `LIMIT_RECOVERY` carry the contract text.
- [X] T017 [US4] In `tests/test_autonomous_artifacts.py`, assert that a `run_commands` result has `timeout_seconds == timeout_minutes * 60` without `remaining`. With a `remaining` smaller than the timeout, it has that smaller value, and the result is `timed_out` when the fake `subprocess.run` raises `TimeoutExpired`. [AC-015] (depends on T008, T012)
- [X] T018 [US4] In `tests/test_autonomous_artifacts.py`, add recorder tests on the existing fix-loop recorder harness (`recorders.FixLoopCase` or the file's equivalent). Each test writes a feedback entry and approved reviews:
  - (a) Two timed-out failures and no blocking or open finding, first record:
    - It blocks with `category == "limit"` and `limit == "check-timeout"`.
    - The condition names both commands and `60 min`.
    - The recovery is the contract text.
    - The fix state and `fix["cycles"]` are unchanged. [AC-015]
  - (b) The same on `--recheck` after one fix cycle: it blocks, and the cycle count is unchanged (F-002). [AC-015]
  - (c) The same at the last fix cycle: it blocks as `check-timeout`, not `fix-cycles`. [AC-015]
  - (d) One timed-out result whose `timeout_seconds` is below the configured timeout: the condition says `the run's wall time ran out` and gives no minutes (F-001). [AC-015]
  - (e) A timeout plus a non-zero exit: the existing `fixing` path, with `fix-pending` set and the cycle started. [AC-016]
  - (f) A timeout plus an open medium finding: the existing fixing path. [AC-017]
  - (g) A timeout plus a high finding or a non-approved verdict: the existing `review-finding` block. [AC-017]
  - (h) A final `run_checks` whose command times out: the same `postcondition` block as before. Keep the existing test and add a timeout case if none exists. [AC-018]

  Run `uv run --locked python -m unittest tests/test_autonomous_artifacts.py`. (depends on T014, T017)
- [X] T019 [P] [US4] In `tests/test_autonomous_recovery.py`, add `ResumeTests` cases on the existing `StubCase` harness.
  - A `limit`/`check-timeout` block at `record-implementation-review` resumes at `checks-implementation`.
  - At `record-fix-review-1`, it resumes at `checks-fix-1`.
  - When a changed input maps to an earlier step, that earlier step wins.
  - A `fix-cycles` limit block still re-enters as before.

  Run `uv run --locked python -m unittest tests/test_autonomous_recovery.py`. [AC-015] (depends on T015)

**Checkpoint**: US4 is complete. A timeout that only the operator can address blocks at once, and resume reruns the checks.

---

## Phase 6: User Story 3 - The test command finishes inside the configured timeout (Priority: P1)

**Goal**: The timeout is 60 minutes, and the suite runs faster with no test lost or weakened.

**Independent Test**: Compare the before and after profiles: same or more tests, lower total, under 2700 s. The run's `run-checks` passes within 60 minutes.

- [X] T020 [US3] [DEFERRED-TO-PR] The driving agent, outside any agent step, sets `[checks] timeout_minutes = 60` in `ballast.toml` and runs `ballast trust`, the authorized privileged action `operator-trust`. The PR records both. An implementing step never edits `ballast.toml`. [AC-010]
  - Done by the driving agent in commit bd80a3e, together with D-001, then `ballast trust` (HD-0001). No agent step made it.
- [ ] T021 [US3] [DEFERRED-TO-PR] Operator verification of AC-014 and SC-001.
  - Run an Autonomous run on an unchanged `main` with this checkout's runner (`BALLAST_STANDARD_DIR` set to the checkout), or with the first release that ships this change. Its `run-checks` passes within the timeout, with 0 fix cycles, no `git-untrusted` and no attestation error.
  - The PR states that this run's own v1.0.0 `run-checks` is not evidence of FR-001 (plan review F-003, research R11). [AC-014]
- [X] T022 [US3] Speed up the slowest tests named in `suite-profile.md`, without skipping, deleting or weakening any test (research R9).
  - Replace avoidable sleeps and real-timeout waits with an injected clock or a shorter injected bound, keeping each assertion.
  - Move expensive read-only fixtures (repeated `git init`, installs, template copies) to `setUpClass` only where no test modifies them.
  - Keep every test name, every assertion and each test's isolation.
  - After each module's change, run that module alone with `uv run --locked python -m unittest tests/test_<module>.py` and confirm its count is unchanged and it passes.
  - Record each change and its measured effect in `suite-profile.md`.
  - Do not edit `tools/`, `uv.lock`, `pyproject.toml` or `.github/workflows/ci.yml`. (depends on T001, T005, T008, T011, T016, T018, T019, T027)
- [X] T023 [US3] Re-profile every module as in T001 and add the after-table to `specs/146-checks-pass-in-run/suite-profile.md`.
  - Show that each module's test count is equal or higher, that the total is at least 1666 and at least the before total, and that the total seconds are lower than before and below 2700 s.
  - Use `git diff main -- tests/` to confirm that no `skip`, `skipIf`, `skipUnless` or `expectedFailure` was added outside the new bwrap-gated test from T008, and that no test method or assertion was removed. List the reviewed files.
  - Use `git diff main -- uv.lock pyproject.toml .github/workflows/ci.yml` to confirm they are unchanged, so `python -m unittest tests/test_*.py` still runs the whole suite. [AC-011, AC-012, AC-013] (depends on T022)
- [X] T024 [US3] Decide on the parallel runner from T023's total.
  - If the total is at or below 2700 s, record in `suite-profile.md` that no parallel runner is needed and that the `[checks]` and CI commands stay unchanged.
  - If it is above, add `tests/parallel.py`: a standard-library runner that runs `python -m unittest <module>` per module in a bounded process pool, prints each module's output and exits non-zero when any module fails. Add a test for it in `tests/test_parallel.py`. Record in `specs/146-checks-pass-in-run/decisions.md` that the `[checks]` command change needs the driving agent and `ballast trust`, as T020 does.
  - Run `uv run --locked python -m unittest tests/test_parallel.py` when the runner was added. [AC-012, AC-013] (depends on T023)
  - Outcome: the total stayed above 2700 s, so `tests/parallel.py` and `tests/test_parallel.py` were added. D-001 was accepted and applied by the driving agent in bd80a3e. `.github/workflows/ci.yml` is unchanged.

**Checkpoint**: US3 is complete, except for the deferred operator checks T020 and T021.

---

## Phase 7: User Story 5 - The check environment and timeout are documented (Priority: P2)

**Goal**: The policy and a new ADR explain the check environment, the timeout setting and the timeout block.

**Independent Test**: Read the policy template and ADR-0021; both state the removed entries, the kept confinement, the timeout source and bounds, and the immediate block.

- [X] T025 [P] [US5] Write `docs/adr/0021-check-command-environment.md`, following the format of the neighboring ADRs (status, context, decision, consequences). It records:
  - Every `[checks]` command and runner acceptance check runs without the agent git guard on `PATH` and without `BALLAST_GIT`, `BALLAST_SPEC_WORKFLOW` and `SPECKIT_WORKFLOW_RUN_ID`.
  - Bwrap, the read-only host, hidden credential paths, the secret filter and the read-only checkout for acceptance checks are unchanged.
  - Why this grants no authority (research R4).
  - Agent steps keep the guard and the run variables.
  - The `check-timeout` limit and its resume re-entry.
  - It extends ADR-0018.

  In `docs/adr/0018-runner-recorded-acceptance-checks.md`, add an "Extended by ADR-0021" note. If `docs/adr/` has an index or README listing ADRs, add the entry. (depends on T006, T014)
- [X] T026 [P] [US5] In `templates/policies/spec-kit-workflow.md`, in the Autonomous runs section and the workflow runner contract rows, describe:
  - The check environment: no guard on `PATH`, no `BALLAST_GIT` and no run variables; bwrap and secret filtering kept.
  - Its scope: every `[checks]` command and runner acceptance check, in Autonomous, Chat and human-gated runs.
  - `[checks] timeout_minutes`: default 30, bound 1-240, read only from the trusted `ballast.toml`.
  - The immediate `check-timeout` block when every failed feedback check timed out and no finding is open, with its recovery and resume at the feedback checks step, next to the fix-loop and limit text.

  Do not edit `docs/policies/`; the installed copy follows the pinned release. (depends on T006, T014)
- [X] T027 [US5] In `tests/test_governance.py`, add a `CheckEnvironmentDocumentTests` class that follows the `FeatureUiStatesDocumentTests` pattern.
  - Policy assertions [AC-019]: `templates/policies/spec-kit-workflow.md` names `BALLAST_GIT`, `BALLAST_SPEC_WORKFLOW`, `SPECKIT_WORKFLOW_RUN_ID`, the guard on `PATH`, `timeout_minutes` with `1` and `240`, `ballast.toml` as the source, and `check-timeout`.
  - ADR assertions [AC-020]: `docs/adr/0021-check-command-environment.md` exists, names ADR-0018, states that agent steps keep the guard, and names bwrap.

  Run `uv run --locked python -m unittest tests/test_governance.py`. (depends on T025, T026)

**Checkpoint**: All stories are complete.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [X] T028 Check that `tools/spec_workflow/autonomy.py`, `artifacts.py`, `run.py` and `agent.py` still import only the standard library and their sibling modules. Run the changed tool modules' existing `python3 -I -S` tests in `tests/test_spec_workflow.py`. [FR-012] (depends on T006, T014, T015)
- [X] T029 Run `uv run --locked ruff check`, then `uv run --locked ruff format --check`, and fix any finding in the changed files without disabling a rule. (depends on T024, T027, T028)
- [X] T030 Write `specs/146-checks-pass-in-run/acceptance-evidence.json` as `{"schema_version": 1, "spec_digest": "<sha256 of spec.md>", "criteria": {...}}`, computing the digest of the committed `spec.md` at implementation time. The mapping is a proposal; only `ballast ledger check` records evidence. (depends on T029)
  - Map AC-001 and AC-004 to the `tests.test_autonomy.CheckEnvTests.*` cases (T004), and AC-001 also to the `run_commands` env case (T007).
  - Map AC-002 and AC-003 to the T007 cases.
  - Map AC-005 to the bwrap-gated T008 case.
  - Map AC-006 to the T005 cases.
  - Map AC-007 and AC-009 to `tests.test_agent_run_ledger.IsolationTests.*` (T011).
  - Map AC-008 to `tests.test_agent_run_ledger.OperatorStepGuardTests.*` (T010).
  - Map AC-015 to the T016, T017, T018 (a)-(d) and T019 cases.
  - Map AC-016 to T018 (e), AC-017 to T018 (f) and (g), and AC-018 to T018 (h).
  - Map AC-019 and AC-020 to `tests.test_governance.CheckEnvironmentDocumentTests.*` (T027).
  - Map AC-010, AC-011, AC-012, AC-013 and AC-014 to `[]`. They are verified by `suite-profile.md`, the diff checks of T023 and the deferred T020 and T021, and stay missing in the acceptance packet.

---

## Phase 9: Rebase follow-up (second plan review)

**Purpose**: Settle PD-0014 F-001. ADR-0021 must name the accepted ADR-0020 amendment, so that #153 treats `check-timeout` like every other limit.

- [X] T031 [US5] In `docs/adr/0021-check-command-environment.md`, cite [ADR-0020](0020-autonomous-stop-rule.md) as the record that amends ADR-0010. Make two edits:
  - In the `Extends:` line, after the ADR-0010 link, add that ADR-0020 amends ADR-0010.
  - In `## Consequences`, add one bullet. Under ADR-0020's stop rule, every limit, `check-timeout` included, becomes a Draft-PR limit outcome once #153 ships. Until then, the resumable block described here applies, as ADR-0020's Delivery section keeps ADR-0010's limits as written.

  Do not change ADR-0020, ADR-0018 or the Decision section of ADR-0021. Do not edit `templates/policies/spec-kit-workflow.md`, because its Stop rule paragraph already covers this. (depends on T025)
- [X] T032 [US5] In `tests/test_governance.py`, extend `CheckEnvironmentDocumentTests.test_adr_0021_records_the_boundary`:
  - Assert that the ADR text contains `0020-autonomous-stop-rule.md` and `#153`.
  - Keep every existing assertion, and keep the method name so the `acceptance-evidence.json` mapping for AC-020 is still valid.

  Run `uv run --locked python -m unittest tests.test_governance.CheckEnvironmentDocumentTests`. [AC-020] (depends on T027, T031)
- [X] T033 Run `uv run --locked ruff check`, then `uv run --locked ruff format --check`, and fix any finding in the changed files without disabling a rule. Then confirm that `acceptance-evidence.json` needs no change:
  - `git diff bd80a3e -- specs/146-checks-pass-in-run/spec.md` must be empty, so the `spec_digest` still matches.
  - Every test it names for AC-019 and AC-020 still exists.

  (depends on T030, T032)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: T001 must finish before any edit under `tests/`, because it is the before-measurement.
- **Foundational (Phase 2)**: T001 → T002 → T003. These block every story.
- **US1 (Phase 3)** and **US2 (Phase 4)**: start after T002.
- **US4 (Phase 5)**: starts after T003 and T006. It shares `artifacts.py` with US1 and test files with US1.
- **US3 (Phase 6)**: speed-ups wait for every new test (US1, US2, US4, US5), so the after-profile is complete. T020 and T021 are deferred and block nothing.
- **US5 (Phase 7)**: after the behavior it documents (T006, T014).
- **Polish (Phase 8)**: after every story.
- **Rebase follow-up (Phase 9)**: after T025, T027 and T030. It is the only open work after the resume.

### User Story Dependencies

- **US1 (P1)**: needs Foundational only.
- **US2 (P1)**: independent of US1 (test-only change).
- **US4 (P2)**: needs T006 because `run_commands` changes in both stories, so the edits are serialized.
- **US3 (P1)**: its timeout edit (T020) is independent. Its speed-up and measurement tasks run last so they cover the whole suite.
- **US5 (P2)**: documents US1 and US4.

### Same-file serialization

- `tools/spec_workflow/autonomy.py`: T002 → T003
- `tools/spec_workflow/artifacts.py`: T006 → T012 → T013 → T014
- `tests/test_autonomy.py`: T004 → T016
- `tests/test_autonomous_artifacts.py`: T007 → T008 → T017 → T018
- `tests/test_agent_run_ledger.py`: T009 → T010 → T011
- `tests/*` speed-ups: T022 after every test-writing task, including T027
- `docs/adr/0021-check-command-environment.md`: T025 → T031
- `tests/test_governance.py`: T027 → T032

---

## Execution Wave DAG

Tasks grouped by dependency resolution. Tasks within the same wave can run in parallel.

```text
Wave 1 (no dependencies):
  T001      Baseline suite profile → suite-profile.md
  T020 [US3] [DEFERRED-TO-PR] timeout_minutes = 60 + ballast trust (driving agent)
  T021 [US3] [DEFERRED-TO-PR] AC-014/SC-001 run on this checkout's runner

Wave 2 (T001 done, so code and test edits may start):
  T002      autonomy.GUARD, RUN_VARIABLES, check_env; agent.GUARD (depends on T001)

Wave 3 (T002 done):
  T003      check-timeout limit kind (depends on T002)
  T004 [P] [US1] check_env tests (depends on T002)
  T005 [P] [US1] agent step env unchanged tests (depends on T002)
  T006 [US1] run_commands uses check_env (depends on T002)
  T009 [P] [US2] per-test run-variable clearing (depends on T002)

Wave 4:
  T007 [US1] run_commands / acceptance / project_checks env tests (depends on T006)
  T010 [US2] guard refusal tests (depends on T009)
  T012 [US4] timeout_seconds in results (depends on T006)
  T015 [US4] _reentry check-timeout mapping (depends on T003)
  T016 [P] [US4] limit-kind tests (depends on T003, T004)

Wave 5:
  T008 [US1] bwrap-gated guarded-caller test (depends on T007)
  T011 [US2] isolation tests (depends on T010)
  T013 [US4] _timeout_only and condition text (depends on T012)
  T019 [P] [US4] resume re-entry tests (depends on T015)

Wave 6:
  T014 [US4] recorder rule in record_decision (depends on T003, T013)
  T017 [US4] timeout_seconds tests (depends on T008, T012)

Wave 7:
  T018 [US4] recorder block and counter-case tests (depends on T014, T017)
  T025 [P] [US5] ADR-0021 + ADR-0018 note (depends on T006, T014)
  T026 [P] [US5] policy template (depends on T006, T014)
  T028      stdlib-only / -I -S check (depends on T006, T014, T015)

Wave 8:
  T027 [US5] governance wording tests (depends on T025, T026)

Wave 9:
  T022 [US3] speed up slowest tests (depends on T001, T005, T008, T011, T016, T018, T019, T027)

Wave 10:
  T023 [US3] after-profile, count and diff checks (depends on T022)

Wave 11:
  T024 [US3] parallel runner decision (depends on T023)

Wave 12:
  T029      ruff check and format (depends on T024, T027, T028)

Wave 13:
  T030      acceptance-evidence.json (depends on T029)

Wave 14 (after the resume at validate-plan):
  T031 [US5] ADR-0021 cites the ADR-0020 amendment (depends on T025)

Wave 15:
  T032 [US5] governance test asserts the ADR-0020 citation (depends on T027, T031)

Wave 16:
  T033      ruff and acceptance-evidence.json still valid (depends on T030, T032)
```

Every task after T001 depends on it, directly or through T002, because T001 measures the unchanged tree.

---

## Implementation Strategy

### MVP First (User Story 1 + User Story 2)

1. T001 baseline, then Foundational (T002, T003).
2. US1 (T004 to T008) removes the `git-untrusted` cause for every check path.
3. US2 (T009 to T011) removes the attestation cause at its source. This also helps this run's own v1.0.0 `run-checks`.
4. **Stop and validate**: run the touched modules alone.

### Incremental Delivery

1. US4 adds the immediate timeout block and its resume.
2. US3 speeds up the suite and measures it after every new test exists. The driving agent applies the 60-minute timeout (T020) outside a step before the run's `run-checks`.
3. US5 documents the boundary in ADR-0021 and the policy template.
4. Polish, then `acceptance-evidence.json`.
5. After the resume, do T031 to T033 only. Every other task is done or deferred.

---

## Notes

- `[P]` tasks touch different files from every other task in their wave.
- No implementing step edits `ballast.toml`, `tools/spec_workflow/ledger.py`, `tools/spec_workflow/guard/`, `confined_argv`, `parse_checks`, `chat.py`, `run._environment`, `uv.lock`, `pyproject.toml` or `.github/workflows/ci.yml`. T024 is the one conditional exception: it adds `tests/parallel.py`, and only the driving agent can change the `[checks]` command.
- A discovery that conflicts with the spec or plan goes to `decisions.md`; do not resolve it silently.
