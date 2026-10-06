---

description: "Task list for reaching a reviewed PR with provisional Autonomous decisions (Issue #21)"
---

# Tasks: Reach a reviewed PR with provisional Autonomous decisions

**Input**: Design documents from `specs/21-autonomous-reviewed-pr/`: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md)

**Prerequisites**: plan.md, spec.md (intent agent-provisional, see [intent.md](intent.md)), research.md, data-model.md, contracts/

**Risk**: R2. This is Autonomous run `fcba2ba4`, so every decision in these tasks is agent-provisional. Merging the PR is the only human approval.

**Acceptance evidence**: Every behavior acceptance criterion (`AC-001`–`AC-033`) is cited by at least one test or verification task below. Each implementation task writes its failing unit tests in the named test file first. The end-to-end scenarios of [quickstart.md](quickstart.md) are their own test tasks. Real-engine and real-confinement cases are skipped where the host lacks the Spec Kit CLI, bubblewrap or a systemd user session, as the existing suites do. SC-001 needs a live pilot after merge, which the operator runs ([quickstart](quickstart.md#live-pilot-operator-after-merge)). It is not a task here.

**Workflow-owned steps (D-07)**: no task below runs the full gate, the quickstart, reviews, converge or spec reconciliation. The workflow runs them after `validate-implementation`. That includes the `specs/TECHNICAL-SPEC.md` §61/§91 update, which spec reconciliation decides.

**Organization**: Tasks are grouped by user story. Most code sits in a few shared files (`autonomy.py`, `artifacts.py`, `run.py`, `agent.py`) and test files. Tasks that touch the same file are chained by explicit dependencies even across stories, and `[P]` marks only tasks whose files no other ready task edits.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel with other ready tasks (different files, dependencies satisfied)
- **[Story]**: User story the task belongs to (US1–US6)
- Test and verification tasks cite the criteria they prove, e.g. `[AC-001]`

## Path Conventions

Tools in `tools/spec_workflow/`, shipped templates in `templates/`, tests in `tests/` (unittest, standard library only under `python3 -I -S` for the tools). New test module: `tests/test_autonomous_recovery.py` (fix loop, resume, retry, checkpoint, block classes, active time, provisional guard). Existing modules get new cases. Expectations that this feature changes on purpose (`RESUME_REFUSAL` for Autonomous runs, the `unpinned` recovery text, the default agent-step limit, the `_frozen_check` message) are updated in the task that changes them. No assertion is weakened.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Verify the one unproven engine assumption (R7) and create the shared test scaffolding.

- [x] T001 Write `EngineRepositionTests` in `tests/test_spec_workflow.py` (real engine, skipped without `specify` ≥ 1.0.11 with the reason), then implement `_reposition_engine(run_id, step_id)` in `tools/spec_workflow/run.py` per [research R7](research.md#r7-repositioning-the-engine-verify-first): read the step order from the top-level `- id:` lines of the run's own `.specify/workflows/runs/<id>/workflow.yml` copy (no YAML library), rewrite `state.json` atomically with `current_step_id` = the re-entry step, `current_step_index` = its position, `step_results` of that step and every later one removed and `status` = `failed`, leave `log.jsonl` untouched, and do nothing when the re-entry step is the failed step. Test case: a fixture run fails at a recorder, is repositioned two steps back, and `specify workflow resume` runs the earlier step next. Add offline unit cases for the rewrite itself. If the real engine rejects a repositioned state, stop and record the R7 fallback as a proposal in `specs/21-autonomous-reviewed-pr/decisions.md` before T018 and T021 continue; if the CLI is unavailable in the implementing environment, record that the R7 check is still pending for the full local gate in the same file
- [x] T002 [P] Create `tests/test_autonomous_recovery.py` with a base class that reuses the fixtures and helpers of `tests/test_autonomous_run.py` (fake agent, fake `specify`, fake `gh` with argv log, temporary `XDG_STATE_HOME`, temporary Git repository on a feature branch with a bare `origin`, injected clock), plus helpers to: write a 1.2.0 engine run directory and `state.json`, write implementation-review and specialist-review drafts with given findings and verdicts, put a run into a given block, and advance `origin`'s base branch

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Record-model groundwork every story needs: constants, active time, block fields and classes, the `stopped → active` transition, the invocation lock and the `DraftError` split.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [x] T003 Write tests in `tests/test_autonomy.py`, then add to `tools/spec_workflow/autonomy.py` the constants of [data-model.md](data-model.md#constants): `FIX_CYCLES = 3`, `DRAFT_RETRIES = 2`, `AGENT_STEPS = (1, 200, 40)` (R9), `WALL_TIME` documented as active minutes, and `AUTONOMOUS_STEPS`, the ordered step IDs of `ballast-autonomous` 1.2.0 from [contracts/workflow-steps.md](contracts/workflow-steps.md) (`checks-implementation` after `validate-implementation`; `fix-N`, `record-fix-N`, `checks-fix-N`, `review-fix-N`, `review-specialists-fix-N`, `record-fix-review-N` for N = 1..3 after `record-implementation-review`). Update the existing default-limit expectations from 30 to 40 [FR-022]
- [x] T004 Write `RunRecordTests` and `ActiveTimeTests` unit cases in `tests/test_autonomy.py`, then extend the run record in `tools/spec_workflow/autonomy.py` per [data-model.md](data-model.md#run-record-runjson): optional `active_seconds` (never decreases), `invocation_started_at`, `fix` (absent means `{"cycles": 0, "state": "idle"}`, cycles 0–3, states `idle`/`fix-pending`/`review-pending`) and `resumes` (append-only entries per [resume entry](data-model.md#resume-entry)); `validate_run` accepts either legacy `limits.deadline` or `active_seconds`; `remaining_seconds(record, now)` = limit − `active_seconds` − open invocation time, with the legacy deadline path unchanged while active; `open_invocation`/`close_invocation` helpers; `close_crashed_invocation` at the latest recorded time (last `steps.jsonl` `at`, block `at`, or `invocation_started_at`); legacy seeding `active_seconds = min(limit, latest − started_at)` that drops `deadline` [FR-021] (depends on T003)
- [x] T005 Write `BlockRecordTests` cases in `tests/test_autonomy.py`, then extend the block model in `tools/spec_workflow/autonomy.py` per [data-model.md](data-model.md#block-blockjson) and [research R15](research.md#r15-block-classes-fr-023): optional `limit` (`agent-steps`, `wall-time`, `fix-cycles`, `retries`, only for category `limit`) and `inputs` (`{path: sha256}` plus `outside`); `BLOCK_CLASSES` mapping every category to `conflict`, `missing authority`, `exhausted limits` or `unsafe uncertainty`, with new category `interrupted`; `recovery_command` returning `ballast run resume RUN_ID` for every resumable category and `BLOCK_COMMAND` accepting it; `RECOVERY` texts saying "then resume, or continue human-gated" where both apply; `resume_run(record, decision_id, entry)` implementing the `stopped → active` transition, legal only with an existing `block-resolution` human decision ID, never touching `mode_history`, `risk`, `limits`, `integration`, `review_integration`, `cross_provider`, `integration_fallback` or `eligibility` (R18) (depends on T004)
- [x] T006 Write lock unit cases in `tests/test_autonomous_run.py`, then add the per-run invocation lock to `tools/spec_workflow/run.py` per [research R13](research.md#r13-per-run-invocation-lock): an exclusive non-blocking `fcntl.flock` on `<operator run dir>/invocation.lock` as a context manager, a held lock refused with "run RUN_ID has an active invocation", and a probe that tells a held lock from a free one; take it for the whole of `start --mode autonomous` and `publish` (depends on T001)
- [x] T007 [P] Write classification tests in `tests/test_autonomous_artifacts.py`, then add `DraftError(ContractError)` to `tools/spec_workflow/artifacts.py` and raise it, with unchanged messages and conditions, from exactly the correctable checks listed in [research R4](research.md#r4-correctable-refusals-retried-inside-the-agent-wrapper) (non-object draft, wrong `point`/`decision`, missing expected draft, text length and format limits, approval wording or workflow marker in agent text, invalid evidence or artifact path, missing review report, invalid finding fields, `accepted-provisionally` without a reason, narrative with findings or severity tags, invalid `block.json` behind exit 3). Every other refusal stays a plain `ContractError`. The recorder's behavior and exit codes are unchanged [FR-017]

**Checkpoint**: Record model, block classes, lock and refusal classes are tested; story work can begin.

---

## Phase 3: User Story 1 - A bounded feature reaches a reviewed Draft PR without prompts (Priority: P1) 🎯 MVP

**Goal**: After implementation, the run gets feedback checks, independent reviews and up to three fix cycles, then publishes a Draft PR whose record and packet show the loop.

**Independent Test**: A fixture R1 feature whose implementation review returns a medium `open` finding runs one fix cycle, passes `run-checks` and publishes a Draft PR with no prompt and a complete record and packet (quickstart scenario 2).

- [x] T008 [US1] Write `FeedbackChecksTests` in `tests/test_autonomous_artifacts.py`, then add `run-checks --feedback` to `tools/spec_workflow/artifacts.py` per [research R3](research.md#r3-check-results-reach-the-fix-loop-only-through-trusted-steps): same confined `[checks]` commands, no frozen-tree requirement, a failed command recorded and not blocked, one line per run appended to `checks-feedback.jsonl` (`cycle`, `at`, `results` with `provenance: runner`), and the tamper, tree-change and wall-time blocks kept; `checks.json` stays the final `run-checks` result; a `checks-fix-N` invocation exits 0 and writes nothing unless the fix state is `review-pending` [AC-006, FR-003] (depends on T004, T007)
- [x] T009 [US1] Write `FixStateTests` in `tests/test_autonomous_artifacts.py`, then extend the implementation-review recorder in `tools/spec_workflow/artifacts.py` per [research R2](research.md#r2-what-triggers-a-fix-and-what-happens-when-the-cycles-run-out) and the [fix state table](data-model.md#fix-state): compute "fix needed" (non-approved verdict, a `critical`/`high` finding, a `medium`+ `open` finding, or a failed command in the latest feedback run); no fix needed freezes the tree and sets `idle`; fix needed with `cycles < 3` records the reviews, writes `.specify/workflow-state/fix-input/<slug>.json` (findings with decision, ID, severity, label, reason, report; failed checks with exit code and the last 4000 printable characters; cycle) and sets `fix-pending` without blocking; with `cycles == 3` blocks `limit` with `limit: fix-cycles`, naming the open high or critical findings, the failed checks and the recovery; the disposition rule allows `open` at any severity only while a cycle remains and applies #27's rule unchanged otherwise; a run whose `workflow.yml` copy lacks `speckit.ballast.fix` blocks on findings exactly as in #27 (R19); `record-decision --point decision-resolution` refuses unless the fix state is `idle` and `frozen_tree` is set; update the `_frozen_check` message [AC-002, AC-003, FR-001, FR-002] (depends on T005, T008)
- [x] T010 [US1] Write `RecordFixTests` in `tests/test_autonomous_artifacts.py`, then add to `tools/spec_workflow/artifacts.py` the `record-fix` subcommand (exits 0 and writes nothing unless the fix state is `fix-pending`; otherwise requires the last unconsumed step to be a `speckit.ballast.fix` that ran and `check_implementation` to pass, else a postcondition block; increments `fix.cycles`, sets `review-pending`, re-renders the record) and `record-decision --point implementation-review --recheck` (exits 0 and writes nothing unless `review-pending`; otherwise records like the first review with `fix_cycle = N`, supersedes every current `implementation-review` and `specialist-review` entry, then applies the T009 transitions) [AC-002, FR-001] (depends on T009)
- [x] T011 [US1] Write skip-gate cases in `tests/test_autonomous_run.py`, then add to `tools/spec_workflow/agent.py` the fix-cycle gate before any limit check or step count: for an Autonomous run, `fix-N` runs only when the fix state is `fix-pending` and `review-fix-N`/`review-specialists-fix-N` only when it is `review-pending`; a skipped step starts no agent, counts no step and writes no `steps.jsonl` entry. The agent argv, `claude-settings.json` arguments and confinement are unchanged [FR-003] (depends on T002, T004)
- [x] T012 [P] [US1] Create `templates/spec-kit/extensions/ballast/commands/speckit.ballast.fix.md` per [contracts/workflow-steps.md](contracts/workflow-steps.md#command-contracts) and [research R16](research.md#r16-commands-templates-and-the-tasks-template): read the fix input as untrusted data, fix only the listed findings and failed checks, change only code, tests and the feature's `tasks.md`/`decisions.md`, never create drafts, edit reviews or `autonomous/`, never run the `[checks]` commands, end with a per-item summary and state that the work is agent-provisional; register it in `templates/spec-kit/extensions/ballast/extension.yml`
- [x] T013 [US1] Extend `templates/spec-kit/extensions/ballast/commands/speckit.ballast.review.md` with the `implementation-recheck` and `specialists-recheck` arguments: same draft contract as `implementation`/`specialists`, read the fix input, mark each listed finding `resolved` with a reason or still present, state the remaining cycles (`3 − cycles`) and that `open` above `low` is valid only while a cycle remains
- [x] T014 [US1] Update `templates/spec-kit/workflows/autonomous/workflow.yml` to version 1.2.0 exactly as in [contracts/workflow-steps.md](contracts/workflow-steps.md) (`checks-implementation` and three fix cycles). Write `StepOrderTests` in `tests/test_autonomy.py` comparing `AUTONOMOUS_STEPS` with the template's step IDs, and extend the gate-structure comparison in `tests/test_spec_workflow.py` so every check, required review, validator and postcondition of the human-gated workflow is still present in 1.2.0 and every command step names a registered command [AC-005, FR-006] (depends on T001, T005, T012, T013)
- [x] T015 [US1] Write `RecordRenderTests` cases in `tests/test_autonomy.py`, then extend `render_record` in `tools/spec_workflow/autonomy.py` per [research R14](research.md#r14-record-and-packet-additions): in "Mode and risk" the line `- Spend: bounded by the agent-step limit; every agent step, retry and fix cycle counts; monetary spend is not measured`; a "Fix loop" section with cycles used out of 3 and, per cycle, the review decisions and feedback check results; deterministic bytes and agent text neutralized as today [AC-004, AC-028, FR-005, FR-022] (depends on T005, T014)
- [x] T016 [US1] Write `FixLoopTests` in `tests/test_autonomous_recovery.py` for quickstart scenarios 2–5 and 27: `test_medium_finding_one_cycle_then_publish` (one cycle, recheck approves, `run-checks` passes, Draft PR published, no approval prompt, record and packet list every provisional decision, review, disposition and the `run-checks` result) [AC-001, AC-002, AC-004]; `test_high_finding_after_three_cycles_blocks_limit` (blocks `limit`/`fix-cycles`, the finding is never published as provisionally passed) [AC-003]; `test_check_failure_reaches_fix_input_only` (failed feedback check appears only in the fix input; agent settings and allowed tools unchanged) [AC-006]; `test_idle_cycles_skip` and `test_old_workflow_copy_blocks` (R1, R19); argv-log assertions that no `gh pr merge`, `gh pr ready` or other new `git`/`gh` write command ran and the PR stays Draft [AC-033] (depends on T002, T010, T011, T014, T015)
- [x] T017 [US1] Extend the existing #16 and #27 intent tests in `tests/test_autonomous_artifacts.py` to assert that an Autonomous run's provisional intent cites the discovery brief and the traced spec and is recorded as agent-provisional; if the intent recorder in `tools/spec_workflow/artifacts.py` does not already refuse an intent without the brief citation, add that refusal as a `DraftError` [AC-007, FR-004] (depends on T010)

**Checkpoint**: The fix loop works end to end offline; an R1 fixture run reaches a reviewed Draft PR.

---

## Phase 4: User Story 2 - A paused or blocked Autonomous run resumes safely (Priority: P1)

**Goal**: `ballast run resume RUN_ID` continues a blocked or interrupted Autonomous run in Autonomous, after branch synchronization, with a recorded `block-resolution` and re-entry at the earliest changed input.

**Independent Test**: Block one fixture run at `decide-tasks` and another after implementation, advance the base, resume each; both sync, record a block resolution and reach their next step in Autonomous (quickstart scenarios 6–7).

- [x] T018 [US2] Write `ReentryTests` in `tests/test_autonomous_run.py`, then add to `tools/spec_workflow/run.py` per [research R6](research.md#r6-re-entry-step-fr-009): when `_stop` records an Autonomous block, store `block.inputs` (digests of `discovery.md`, `spec.md`, `intent.md`, the plan files and `contracts/`, `tasks.md`, `decisions.md`, and `outside`, the tree digest outside the feature directory once an implementation baseline exists); `_reentry_step(record, block, current)` returning the earliest of the block step (the failed agent step; for a failed recorder the agent step whose drafts it records, the first reviewer step for `record-implementation-review` and `record-fix-review-N`; for a failed validator the validator) and the mapped validator of each changed input that comes before it, using `autonomy.AUTONOMOUS_STEPS` order (depends on T005, T006)
- [x] T019 [US2] Write unit cases in `tests/test_autonomy.py`, then extend `resume_run` in `tools/spec_workflow/autonomy.py` with the runner-state reset of [research R6](research.md#r6-re-entry-step-fr-009): when re-entry is at or before `record-implementation-review`, clear `frozen_tree`, `checked_tree` and the fix state to `idle` while keeping `fix.cycles`; consume pending steps; append the `resumes` entry; open the invocation clock [FR-001, FR-012] (depends on T015)
- [x] T020 [US2] Write tests in `tests/test_autonomous_artifacts.py`, then change `tools/spec_workflow/artifacts.py` so a single decision point recorded again after a resume or fix cycle supersedes its current decision automatically (as `intent` does), a review point supersedes every current entry of that point (and of `specialist-review` for `implementation-review`), and `record_baseline` keeps an existing baseline for the run [FR-008, FR-009] (depends on T017)
- [x] T021 [US2] Implement the Autonomous `resume` flow in `tools/spec_workflow/run.py` per [research R5](research.md#r5-autonomous-resume-flow) and [contracts/cli-commands.md](contracts/cli-commands.md#ballast-run-resume), replacing `RESUME_REFUSAL` for `ballast-autonomous` runs: argument check (only `RUN_ID` and `--ref` of 1–500 characters not matching `HUMAN_APPROVAL`; `-i`, `--mode`, `--wall-time`, `--max-agent-steps` refused); tamper marker check; the [resume eligibility](data-model.md#resume-eligibility) table, with an `active` run whose lock is free closed at its latest recorded time and blocked `interrupted`; the invocation lock; `_sync(run_id, feature=<pinned feature>)` before any agent step, a sync block recorded as the current block with command `ballast run resume RUN_ID` and no human decision; re-entry (T018); the `block-resolution` human decision; `autonomy.resume_run`; record re-render; `.specify/feature.json` pointed at the pinned feature; `_reposition_engine` (T001) and `specify workflow resume RUN_ID`; `_finish` with the invocation clock closed in `finally`. Open and close the active-time clock around `start` too, and apply legacy deadline seeding on resume. Print `Recorded HD-NNNN (block-resolution); run RUN_ID resumes in Autonomous at <step>` and the changed inputs. Human-gated `resume` is unchanged; update the `RESUME_REFUSAL` expectations in `tests/test_autonomous_run.py` for Autonomous runs only [FR-007, FR-008, FR-010, FR-012, FR-013, FR-021] (depends on T018, T019, T020)
- [x] T022 [US2] Write `ContinueTests.test_pre_implementation_continue_points_to_resume` in `tests/test_autonomous_run.py`, then add to `_continue_refusal` in `tools/spec_workflow/run.py`, after the existing `upstream-sync` refusal, the refusal "run RUN_ID stopped before implementation; resume it in Autonomous: ballast run resume RUN_ID" for a source run without an implementation baseline; existing post-implementation `continue` tests pass unchanged [AC-011, FR-011] (depends on T021)
- [x] T023 [P] [US2] Change the `unpinned` recovery text in `tools/spec_workflow/branch_sync.py` to name the manual operator step of [research R11](research.md#r11-runs-started-before-branch-pinning-d-12) (add `"feature": "specs/<N>-<slug>"`, taken from the run record, to the run's pin file under the launcher state directory, then rerun), and update its expectation in `tests/test_branch_sync.py`; nothing writes the pin [FR-014]
- [x] T024 [US2] Write `RecordRenderTests` cases in `tests/test_autonomy.py`, then extend `render_record` in `tools/spec_workflow/autonomy.py` with `human_decisions` and a "Block resolutions" section: each `block-resolution` with the block it resolved, its re-entry step and time, its reference text neutralized [AC-010, FR-005] (depends on T019)
- [x] T025 [US2] Write `ResumeTests` in `tests/test_autonomous_recovery.py` for quickstart scenarios 6–12: `test_pre_implementation_block_resumes` (block at `decide-tasks`, base advances, resume syncs, records `block-resolution`, re-enters at `decide-tasks`, completes; the record shows the resolution) [AC-008, AC-010]; `test_post_implementation_block_syncs_first` (sync runs before any agent step, argv-log order) [AC-009]; `test_changed_spec_reenters_at_validate_spec` [AC-012]; `test_protected_input_fails_closed` (during the pause and during sync; no agent; recovery names `ballast trust`) [AC-013]; `test_unpinned_run_blocks_with_manual_step` (`wrong-branch`, nothing writes the pin) [AC-014]; keep and run `test_resume_of_continued_run_refused` [AC-015]; `test_resume_keeps_mode_and_limits` (`-i integration=codex`, `--mode`, `--wall-time`, `--max-agent-steps` refused with no record written; `mode_history`, `risk`, `limits`, integrations and `eligibility` byte-identical after a resume) [AC-016, AC-029]; `--ref` with approval wording refused; one case per non-resumable row of the eligibility table naming its command; `fix.cycles` unchanged across a resume [FR-001] (depends on T002, T016, T021, T022, T023, T024)

**Checkpoint**: Pre- and post-implementation blocks resume in Autonomous; US1 and US2 together unblock the pilot.

---

## Phase 5: User Story 3 - A correctable agent-output error does not end the run (Priority: P2)

**Goal**: A `DraftError` reruns the agent step with the validator's message, at most twice, each attempt counted; state refusals stay terminal.

**Independent Test**: A review draft with a 1001-character finding reason is retried and the second, valid draft recorded; a draft that keeps failing blocks as exhausted limits (quickstart scenarios 14–15).

- [x] T026 [US3] Write tests in `tests/test_autonomous_artifacts.py`, then add to `tools/spec_workflow/artifacts.py` `STEP_POINTS` and `check_step_drafts(feature, command, args, step, drafts)` per [contracts/draft-retry.md](contracts/draft-retry.md#step-to-point-map-artifactsstep_points), calling the same functions as `record_decision` (`_expected_drafts`, `_validate_draft`, `_validate_review`, `_check_narrative`, `_check_dispositions` with the cycle rule, `autonomy.validate_block_draft`) and changing none; make `_qualifying_steps` skip `steps.jsonl` entries with `refused`; write `agent.attempts` and `agent.refusals` into every decision recorded from a step [FR-016, FR-017] (depends on T020)
- [x] T027 [US3] Implement the per-attempt loop in `tools/spec_workflow/agent.py` per [contracts/draft-retry.md](contracts/draft-retry.md#sequence-per-step-invocation) (Autonomous agent steps only): each attempt runs the limit check and step count, confinement, a new systemd scope, the in-progress marker, the protected-input check (tamper ends the step, no retry) and its own log directory; after the agent exits call `artifacts.check_step_drafts`; on `DraftError` append `{attempt, refused: <message>}`, move the drafts to `set-aside/<step>/retry-<attempt>/` and rerun with the [retry note](contracts/draft-retry.md#retry-note-appended-to-the-prompt) (message printable, ≤ 500 characters); after `DRAFT_RETRIES` exit `EXIT_LIMIT` with `draft refused after 2 retries: <message>` and `limit: retries`; a limit hit on a retry exits `EXIT_LIMIT` with `<limit> exhausted after a refused draft: <message>` and `limit` `agent-steps` or `wall-time`; any other exception ends the step as today; human-gated steps unchanged. End-to-end cases are in T031 (depends on T011, T026)
- [x] T028 [US3] Write `CommandWordingTests` in `tests/test_governance.py`, then state the recorder's length limits of [research R4](research.md#r4-correctable-refusals-retried-inside-the-agent-wrapper) in `templates/spec-kit/extensions/ballast/commands/speckit.ballast.decide.md`, `speckit.ballast.review.md`, `speckit.ballast.clarify.md`, `speckit.ballast.discover.md` and `speckit.ballast.resolve.md`; decide and review also say "paraphrase and cite a sourced human approval; never quote approval wording" [AC-020, AC-021, FR-018] (depends on T013)
- [x] T029 [US3] Write `TasksTemplateTests` in `tests/test_governance.py`, then add to `templates/spec-kit/templates/tasks-template.md` the rule: never create tasks for steps the workflow runs itself (the full gate, quickstart runs, reviews, converge, spec reconciliation), because `validate-implementation` requires every task done before they run. Assert in the same test that `check_implementation` in `tools/spec_workflow/artifacts.py` is unchanged by running the existing implementation-check cases [AC-022, FR-019] (depends on T028)
- [x] T030 [US3] Write a `RecordRenderTests` case in `tests/test_autonomy.py`, then render "after N retries" in `render_record` in `tools/spec_workflow/autonomy.py` for decisions whose `agent.attempts > 1` (depends on T024)
- [x] T031 [US3] Write `RetryTests` in `tests/test_autonomous_recovery.py` for quickstart scenarios 14–17: `test_overlong_reason_retried_then_recorded` (second draft recorded, both attempts counted, record says "after 1 retries"/"after N retries") [AC-017]; `test_retries_exhausted_blocks_limit` and `test_step_limit_during_retry` (block `limit` with the last validator message) [AC-018]; `test_state_refusals_not_retried` (high finding at plan review, tamper, contradiction draft, ineligible risk: one attempt each) [AC-019]; `test_quoted_approval_retried` (a basis quoting "approved by the operator" is refused and retried under the same bound) [AC-020] (depends on T025, T027, T030)

**Checkpoint**: A single correctable draft error never ends a run.

---

## Phase 6: User Story 4 - The operator refreshes a finished run's packet (Priority: P2)

**Goal**: `ballast run checkpoint RUN_ID` refreshes the Draft PR checkpoint and acceptance packet without an agent and without touching run records.

**Independent Test**: Publish a fixture run, add a ledger check, run `checkpoint`; the PR section and packet update, no agent ran, the decision log is byte-identical (quickstart scenario 19).

- [x] T032 [P] [US4] Write a test in `tests/test_draft_pr.py`, then add `create=True` to `checkpoint(root, run_id, *, create=True)` in `tools/spec_workflow/draft_pr.py`: with `create=False`, `settle()` returning no PR ends as `skipped` with reason `no-draft-pr`, records no ledger event and publishes no packet; existing calls are unchanged
- [x] T033 [US4] Add the `checkpoint` subcommand to `tools/spec_workflow/run.py` per [contracts/cli-commands.md](contracts/cli-commands.md#ballast-run-checkpoint), dispatched before the `specify` lookup like `publish`: refuse extra arguments, an invalid ID, a run without an operator record or not `ballast-autonomous`, and a held invocation lock; call `draft_pr.checkpoint(root, run_id, create=False)`; `skipped`/`no-draft-pr` refuses with exit 2 and the actionable reason; otherwise print the `Draft PR:` and packet lines and exit 0, or 1 on `failed-retryable`; never read or write `run.json`, `decisions.jsonl`, `human-decisions.jsonl`, `block.json` or `record.md`; update the module docstring and usage for `resume` and `checkpoint` [FR-020] (depends on T022, T032)
- [x] T034 [US4] Write `CheckpointTests` in `tests/test_autonomous_recovery.py`: `test_refresh_published_run` (after a new ledger check the PR section and packet are updated; `run.json`, `decisions.jsonl` and `human-decisions.jsonl` byte-identical; mode and status unchanged; no agent ran; argv log shows no merge or ready command) [AC-023, AC-024, AC-033]; `test_refusals_write_nothing` (no Draft PR, a human-gated run, the lock held: exit 2, no ledger event, no packet, no archive write) [AC-025] (depends on T031, T033)

**Checkpoint**: Evidence recorded after publication reaches the PR.

---

## Phase 7: User Story 5 - Limits and blocks are bounded and actionable (Priority: P2)

**Goal**: Every stop names its class, cause and next command; wall time counts active time only; every attempt counts against the step limit.

**Independent Test**: Drive fixture runs into each block class and check the printed reason and `Next:` command; pause a run for a simulated 10 hours and resume within budget (quickstart scenarios 21–23).

- [x] T035 [US5] Change the printed block in `tools/spec_workflow/run.py` to the format of [contracts/cli-commands.md](contracts/cli-commands.md#printed-block): `Autonomous run blocked (<class>: <category>): <condition>`, options, `Recovery:` and `Next:`; for `limit`, the condition starts with `agent-step limit`, `wall-time limit`, `fix-cycle limit (3)` or `draft retries (2)` [FR-023] (depends on T033)
- [x] T036 [US5] Write in `tests/test_autonomous_recovery.py`: `BlockClassTests` (one block per class, each printing its class, a reason naming the cause and a `Next:` command) [AC-026]; `ActiveTimeTests` (10-hour simulated pause then resume within budget; a step still stops at the limit; a crashed invocation does not count its downtime; a v0.6.x record with `limits.deadline` is seeded) [AC-027]; `test_every_attempt_counts` (steps, retries and fix cycles all increment `agent_steps`; skipped cycle steps do not; the record states monetary spend is not measured) [AC-028]; a test that `resume`, `checkpoint`, `publish`, `continue` and every recorder refuse or ignore any attempt to raise a run to Autonomous or change its mode [AC-029] (depends on T027, T034, T035)

**Checkpoint**: Every Autonomous stop is bounded and actionable.

---

## Phase 8: User Story 6 - Provisional stays distinguishable from accepted (Priority: P3)

**Goal**: New paths keep provisional decisions visibly provisional; policies, ADR and README describe them; the human-gated workflow and agent permissions are unchanged.

**Independent Test**: Validators refuse artifacts from the new paths that present a provisional decision as accepted; the human-gated tests and permission settings are unchanged (quickstart scenarios 24–26).

- [x] T037 [US6] Write `ProvisionalGuardTests` in `tests/test_autonomous_artifacts.py`: a fix-step change, a retried draft, a `--ref` on resume and a refreshed packet that present a provisional decision as accepted or as a human approval are each refused by the existing guards, with the guard unchanged [AC-030, FR-024] (depends on T021, T026, T033)
- [x] T038 [P] [US6] Update `templates/policies/spec-kit-workflow.md` with Autonomous sections for resume (re-entry, block resolution, what refuses), the fix loop, retries, `checkpoint`, active wall time and the spend bound, block classes, and "Runs started before branch pinning" (where the pin file is, how to read the feature from the run record); and in `templates/policies/workflow.md` replace "blocked Autonomous runs continue only human-gated until #18" with resume plus the fix-loop bound, keeping the three-cycle escalation rule. Every section says the path is agent-provisional and merging the PR is the single human approval [FR-014, FR-024]
- [x] T039 [P] [US6] Write `docs/adr/0010-autonomous-resume-and-bounded-recovery.md` per [research R17](research.md#r17-adr-0010) (status Proposed, agent-provisional; context, decision, consequences including the R7 engine reposition and the step-default change R9) and add an "Amended by ADR-0010" line to the continuation rule in `docs/adr/0004-autonomous-provisional-decisions.md` [FR-015]
- [x] T040 [P] [US6] Add one sentence on `ballast run resume` and `ballast run checkpoint` for Autonomous runs to the workflow section of `README.md`
- [x] T041 [US6] Write `PolicyWordingTests` in `tests/test_governance.py`: the installed policy templates and README describe resume, the fix loop, retries and refresh as agent-provisional and state that merging the PR is the single human approval; ADR-0010 exists and ADR-0004 carries the amendment line [AC-031] (depends on T029, T038, T039, T040)
- [x] T042 [US6] Write `PermissionsUnchangedTests` in `tests/test_governance.py` (the `claude-settings.json` template, `CONFINED_ALLOW`/`CONFINED_DENY` and the Codex sandbox arguments equal their pre-feature values) and `HumanGatedUnchangedTests` in `tests/test_autonomous_run.py` (a human-gated `resume` and `continue` produce the same argv and records as before, and the human-gated workflow definition is unchanged) [AC-032, FR-025] (depends on T022, T027, T041)

**Checkpoint**: All user stories are complete and independently tested.

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Security bounds on untrusted text that crosses the new paths.

- [x] T043 Write `UntrustedTextTests` in `tests/test_autonomous_recovery.py`, then fix any gap in `tools/spec_workflow/artifacts.py`, `agent.py` or `autonomy.py`: check output in the fix input is printable and cut to 4000 characters per command; validator messages in the retry note are printable, ≤ 500 characters and carry no draft content; `--ref` text and changed-input paths in the record and PR text are neutralized (`<!-- workflow-* -->` markers, `@mentions`, HTML comments) [FR-003, FR-018, FR-026] (depends on T036, T037)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies. T001 must report on the engine reposition before T018 and T021 build on it.
- **Foundational (Phase 2)**: T003–T007; blocks every story.
- **US1 (Phase 3)** and **US2 (Phase 4)**: both P1. US2's resume needs US1's step list and fix state (T014, T015), because re-entry and the runner-state reset must know the fix-cycle steps.
- **US3 (Phase 5)**: needs the artifacts chain through T020 and the wrapper gate T011.
- **US4 (Phase 6)**: independent apart from the shared `run.py` chain (after T022).
- **US5 (Phase 7)**: needs the printed block on top of US4's `run.py` changes and the retry loop.
- **US6 (Phase 8)**: documentation tasks start at once; the guard and unchanged-behavior tests come last.
- **Polish (Phase 9)**: after US5 and US6.

### Shared-file chains

- `tools/spec_workflow/autonomy.py`: T003 → T004 → T005 → T015 → T019 → T024 → T030
- `tools/spec_workflow/artifacts.py`: T007 → T008 → T009 → T010 → T017 → T020 → T026
- `tools/spec_workflow/run.py`: T001 → T006 → T018 → T021 → T022 → T033 → T035
- `tools/spec_workflow/agent.py`: T011 → T027
- `tests/test_autonomous_recovery.py`: T002 → T016 → T025 → T031 → T034 → T036 → T043
- `tests/test_governance.py`: T028 → T029 → T041 → T042
- `speckit.ballast.review.md`: T013 → T028

### Execution Wave DAG

| Wave | Tasks | Starts after |
| --- | --- | --- |
| 1 | T001, T002, T003, T007, T012, T013, T023, T032, T038, T039, T040 | — |
| 2 | T004, T006, T028 | T003; T001; T013 |
| 3 | T005, T008, T011, T029 | T004; T004, T007; T002, T004; T028 |
| 4 | T009, T014, T018, T041 | T005, T008; T001, T005, T012, T013; T005, T006; T029, T038, T039, T040 |
| 5 | T010, T015 | T009; T005, T014 |
| 6 | T016, T017, T019 | T002, T010, T011, T014, T015; T010; T015 |
| 7 | T020, T024 | T017; T019 |
| 8 | T021, T026, T030 | T018, T019, T020; T020; T024 |
| 9 | T022, T027 | T021; T011, T026 |
| 10 | T025, T033, T042 | T002, T016, T021, T022, T023, T024; T022, T032; T022, T027, T041 |
| 11 | T031, T035, T037 | T025, T027, T030; T033; T021, T026, T033 |
| 12 | T034 | T031, T033 |
| 13 | T036 | T027, T034, T035 |
| 14 | T043 | T036, T037 |

### Acceptance coverage

| Criterion | Task(s) |
| --- | --- |
| AC-001, AC-002, AC-003, AC-004, AC-006 | T016 (units T008–T010, T015) |
| AC-005 | T014 |
| AC-007 | T017 |
| AC-008, AC-009, AC-010, AC-012, AC-013, AC-014, AC-015, AC-016 | T025 (units T018–T024) |
| AC-011 | T022 |
| AC-017, AC-018, AC-019, AC-020 | T031 (units T007, T026) |
| AC-020, AC-021 | T028 |
| AC-022 | T029 |
| AC-023, AC-024, AC-025 | T034 |
| AC-026, AC-027, AC-028, AC-029 | T036 (AC-029 also T025) |
| AC-030 | T037 |
| AC-031 | T041 |
| AC-032 | T042 |
| AC-033 | T016, T034 |

### Parallel Opportunities

- Wave 1 runs eleven tasks across different files: the engine spike, scaffolding, constants, the `DraftError` split, the fix and review commands, the branch-sync text, the `draft_pr` switch, and all three documentation tasks.
- Within later waves, tasks touch different files: for example wave 4 runs the recorder fix state (`artifacts.py`), workflow 1.2.0 (`workflow.yml`), re-entry (`run.py`) and governance wording tests in parallel.

---

## Parallel Example: Wave 1

```text
Task: "T001 Engine reposition spike in tools/spec_workflow/run.py + tests/test_spec_workflow.py"
Task: "T003 Constants in tools/spec_workflow/autonomy.py"
Task: "T007 DraftError in tools/spec_workflow/artifacts.py"
Task: "T012 speckit.ballast.fix command"
Task: "T032 draft_pr create=False"
Task: "T039 ADR-0010"
```

---

## Implementation Strategy

### MVP first

1. Phase 1 and Phase 2. Read T001's result first: if the engine rejects a repositioned state, the R7 fallback is a proposal in `decisions.md`, not a silent change.
2. Phase 3 (US1): the fix loop, so an Autonomous PR is reviewed.
3. Phase 4 (US2): resume, which unblocks the pilot. US1 and US2 together are the MVP.
4. Stop and validate both stories with their test tasks.

### Incremental delivery

1. US3 retries keep correctable draft errors from ending runs.
2. US4 checkpoint brings post-publication evidence to the PR.
3. US5 block classes and active time make every stop actionable.
4. US6 policies, ADR-0010, README and the unchanged-behavior tests.
5. Polish: untrusted-text bounds.

The plan suggested resume and retries before the fix loop. The wave DAG follows that where it can: resume (T018–T021) and the `DraftError` split (T007) start before the fix-loop end-to-end tests, but resume needs the 1.2.0 step list and fix state, so T014 and T015 come first.

---

## Notes

- Commit after each task or logical group, with Conventional Commit messages.
- Any implementation discovery that conflicts with the spec, plan or an accepted ADR goes to `decisions.md` as a proposal; do not silently change behavior.
- The live pilot (SC-001) and the full local gate (SC-008) are recorded in the PR by the workflow and the operator, not by tasks here.

## Implementation evidence

Implemented by hand by the driving agent after `speckit.implement` of run `fcba2ba4` stopped (agent usage limit); commits `22bc044`..`2b79b8a` on `feat/21-autonomous-reviewed-pr`. Every task is done; its evidence is a test that fails without the behavior.

| Tasks | Evidence |
| --- | --- |
| T001 | `test_spec_workflow.EngineRepositionTests` (real Spec Kit 1.0.11: `specify workflow resume` runs the repositioned step next), `EngineRepositionOfflineTests`, `EngineStepListTests`. R7 holds; no fallback was needed. |
| T002 | `tests/test_autonomous_recovery.py` (`RecoveryEngineCase`, `StubCase`) |
| T003–T005 | `test_autonomy.RecoveryConstantsTests`, `ActiveRecordTests`, `RecoveryBlockTests`, `ResumeRunTests` |
| T006 | `test_autonomous_run.InvocationLockTests`; lock refusals in `test_autonomous_recovery.ResumeTests`, `CheckpointTests` |
| T007, T026 | `test_autonomous_artifacts.StepDraftTests` |
| T008 | `test_autonomous_artifacts.FeedbackChecksTests` |
| T009 | `test_autonomous_artifacts.FixStateTests` |
| T010 | `test_autonomous_artifacts.RecordFixTests` |
| T011 | `test_autonomous_recovery.AttemptCountTests` (skip and pending cases) |
| T012, T013, T028 | `test_governance.CommandWordingTests` |
| T014 | `test_spec_workflow.AutonomousWorkflowDefinitionTests` (`test_version_and_step_order`, `test_every_human_gated_check_is_kept`) |
| T015, T024, T030 | `test_autonomy.RecoveryRenderTests` and the updated goldens |
| T016 | `test_autonomous_recovery.FixLoopTests` (real engine) |
| T017 | `test_autonomous_artifacts.IntentEvidenceTests`; engine fixture cites the brief |
| T018 | `test_autonomous_run.ReentryTests`, `test_autonomous_recovery.ResumeTests.test_changed_inputs_send_the_resume_back` |
| T019 | `test_autonomy.ResumeRunTests` |
| T020 | `test_autonomous_artifacts.SupersessionTests` |
| T021, T025 | `test_autonomous_recovery.ResumeTests` (offline) and `ResumeEngineTests` (real engine); `test_autonomous_run.RunBlockTests.test_autonomous_resume_refuses_mode_limits_and_inputs` |
| T022 | `test_autonomous_run.ContinueRefusalTests` |
| T023 | `test_branch_sync` (`test_unpinned_resume_is_refused`, `DocumentationTests`) |
| T027, T031 | `test_autonomous_recovery.RetryEngineTests` (real engine), `AttemptCountTests` |
| T029 | `test_governance.TasksTemplateTests` |
| T032 | `test_draft_pr.RefreshOnlyTests` |
| T033, T034 | `test_autonomous_recovery.CheckpointTests` |
| T035, T036 | `test_autonomous_recovery.BlockClassTests`, `AttemptCountTests`, `ResumeTests.test_active_time_after_a_long_pause`, `ModeAuthorityTests` |
| T037 | `test_autonomous_recovery.ProvisionalGuardTests` |
| T038–T041 | `test_governance.PolicyWordingTests` |
| T042 | `test_governance.PermissionsUnchangedTests`, `test_autonomous_run.HumanGatedUnchangedTests`, the unchanged human-gated resume and continue tests |
| T043 | `test_autonomous_recovery.UntrustedTextTests`, `ResumeTests.test_reference_is_neutralized_in_the_record`, `FeedbackChecksTests.test_output_tail_is_bounded_and_printable` |

Discovery during implementation: [DEC-0001](decisions.md) (a resume after the base advanced first blocks as `dirty`, per #18).

