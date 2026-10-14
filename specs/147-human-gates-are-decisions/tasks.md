---

description: "Task list for Human gates are decisions, not command relays"
---

# Tasks: Human gates are decisions, not command relays

**Input**: Design documents from `specs/147-human-gates-are-decisions/`
**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/trust-refresh.md](contracts/trust-refresh.md), [contracts/cli.md](contracts/cli.md), [quickstart.md](quickstart.md), [constitution-amendment.md](constitution-amendment.md)

**Risk**: R2, Autonomous run `2e651132`. Every decision in this file is agent-provisional. Merging the PR is the only human approval (BL-INV-006).

**Acceptance evidence**: Every behavior criterion AC-001 to AC-028 maps to a `unittest` case in the module [quickstart.md](quickstart.md) names. AC-007 and AC-009 (documents) map to wording tests in `tests/test_governance.py`. AC-008 maps to an automated end-to-end Chat run with fake agents (T029), and the networked scratch run in quickstart.md (workflow-owned) adds the operator-action count. T050 writes `acceptance-evidence.json`. The mapping is a proposal; only `ballast ledger check` records evidence.

**Operator-only checks**: one task is `[DEFERRED-TO-PR]`: T043, applying the constitution amendment, which the confined implement step cannot do because the constitution is a protected input (as in #55). Before merge, the operator applies [constitution-amendment.md](constitution-amendment.md) and `ballast trust` is run for the changed protected inputs (`operator-trust`) and the end-to-end scratch run (`scratch-repository`). Both are workflow and merge steps, described in plan.md and quickstart.md.

**Workflow-owned steps**: The full gate, the quickstart end-to-end run, the reviews (engineering, security, test, documentation), converge and spec reconciliation are not tasks.

**Verification commands**: Each command matches an `[agents.permissions] extra_allow` rule in `ballast.toml`. Run one command per invocation:

- `uv run --locked python -m unittest tests.test_<module>` (for example `tests.test_setup_trust`)
- `uv run --locked python -m unittest tests/test_*.py`
- `uv run --locked ruff check`
- `uv run --locked ruff format --check`

Inside a confined agent step, `tests.test_agent_run_ledger` cases that pass through the ledger's operator-attestation guard refuse by design (see `specs/23-free-fallback/tasks.md` T036). Record which ones, and leave them to the full gate.

**Plan review findings settled here** ([reviews/plan.md](reviews/plan.md)):

- F-001: T023 adds a test showing that a terminal-less, relayed human-gated `start` or `resume` with piped stdin pauses at a Spec Kit engine gate and records no approval. T041 names ADR-0020's dependency on engine gates prompting only at a terminal (ADR-0004 context).
- F-002: a human-gated `start` or `resume` writes no operator run record today and gains none. `--relayed-by` is accepted and validated there, so only the actor rule's refusal applies, and the gate decisions themselves stay terminal-only at the engine gate. The contract matrix's "Recorded actor" cell for those rows says so (T001, already applied). FR-011 is met because nothing in a human-gated run records a decision as relayed.
- F-003: the contract marks `continue` as Autonomous-source only (stopped, completed or published Autonomous runs) and notes that `continue` already requires `--ref` (T001, already applied). T022 asserts which refusal fires: the D-08 message for `resume`, and today's argument refusal for `continue` without `--ref`.

**Third plan review findings settled here** (PD-0010, after D-09):

- F-001: `ballast trust` keeps today's terminal-free behavior outside a step and is refused inside one (D-09). No task adds a terminal check to `_trust`: T024 adds only the `BALLAST_AGENT_STEP` refusal. T045, the Phase 4 goal and the Wave 3 label no longer call `trust` terminal-only. T023 fails if a terminal check comes back.
- F-002: T041 lists the D-09 residual risk (`trust` has no terminal test, so only the step boundary keeps a confined agent from vouching for its own changes) and cites the pseudo-terminal risk to the first plan review. T049 checks both risks.
- F-003: installed `docs/policies/*.md` outside `project/` are git-ignored copies and are not edited (Phase 7). T001 is marked done because `contracts/cli.md` already carries its edits. Parallel Opportunities no longer lists the dropped `ballast.toml` comment.

**Organization**: `actor.py` and the record schemas in `autonomy.py` are foundational. The refresh (US1) needs neither and can start at once. Tasks that edit the same file are never in the same wave: `launcher.py`, `run.py`, `chat.py`, `agent.py`, `tools/setup` and each test module take one writer at a time, through explicit dependencies.

## Format: `[ID] [P?] [Story?] Description [(depends on ...)]`

- **[P]**: Can run in parallel with other ready tasks once any listed dependencies are satisfied. No two `[P]` tasks in a wave edit the same file.
- **[Story?]**: The user story a task belongs to (US1 to US4).
- **(depends on ...)**: Explicit dependency on earlier task IDs.
- Test and verification tasks cite the acceptance criterion IDs they prove.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Align the contract with plan-review F-002 and F-003 before any test asserts it.

- [x] T001 (Done: `contracts/cli.md` already carries these edits, as checked in the third plan review.) In `specs/147-human-gates-are-decisions/contracts/cli.md`, agent command matrix: (a) for `ballast run start` (human-gated) and for human-gated `resume`, set "Recorded actor" to "none: no operator run record; `--relayed-by` is validated, and engine gates stay terminal-only" (F-002); (b) mark `ballast run continue` as applying only to a stopped, completed or published Autonomous run, setting the Human-gated and Chat columns of the `continue` rows to "n/a", and add one line under "Relayed `resume` and `continue` by block category" saying `continue` already requires `--ref` for every category, so D-08 adds a requirement to `resume` only (F-003). Change no other row.

No other setup: the tools stay standard-library-only, and no dependency or directory is added.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The actor rule and the record schemas every relay and batch path writes through.

**⚠️ CRITICAL**: US2, US3 and US4 depend on this phase. US1 does not.

- [x] T002 Create `tools/spec_workflow/actor.py` (standard library only, importable under `python3 -I -S` from the installed tools like `chat.py`):
  - an `Actor` frozen dataclass (`by`: `"operator" | "relayed"`, `relayed_by`: `str | None`);
  - `SESSION = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,79}")` with full-match validation, refusing any session that matches `autonomy.HUMAN_APPROVAL`;
  - `resolve(relayed_by, *, stdin, stdout)`, which returns `Actor("relayed", S)` when a session is given, `Actor("operator")` when both streams are terminals, and otherwise raises a refusal whose text is `without a terminal, name the relaying agent session with --relayed-by SESSION; nothing was recorded`;
  - `DECISION_FREE = frozenset({"upstream-sync", "interrupted", "postcondition"})`;
  - `RELAY_ACCEPTING = ("start", "resume", "continue", "approve")`;
  - the agent command matrix as data (command name, agent session rule, recorded actor, per-mode allowance) matching `contracts/cli.md` after T001;
  - `allowed(command, mode, actor, block_category=None, ref=None)`, which returns `None` or the exact refusal text from `contracts/cli.md`: human-gated approve, Autonomous approve, a decision-carrying block without `--ref`, and `--relayed-by is not accepted by COMMAND` for every command outside `RELAY_ACCEPTING`.

  Add a module docstring stating that the `in-progress` marker, not this module, is the step boundary.
- [x] T003 In `tools/spec_workflow/autonomy.py`, following [data-model.md](data-model.md):
  - extend `validate_human_decision` to accept `by` in `{"operator", "relayed"}`. `relayed_by` is required and must pass `actor.SESSION` when `by == "relayed"`, and is forbidden otherwise. A relayed `gate-approval` must have `ref == f"relayed approve {gate}"`. `gate-rejection` and `decision-resolution` are refused when relayed. A relayed `block-resolution` whose category is outside `actor.DECISION_FREE` needs a non-empty `ref` that passes the `HUMAN_APPROVAL` guard;
  - extend `_validate_mode_history` the same way. A `switch` entry must be `operator`;
  - add `append_human_decisions(run_dir, decisions)`, which assigns consecutive `HD-NNNN` IDs, chains each line's hash to the previous one, and rewrites `human-decisions.jsonl` once through `write_atomic` (all lines or none). Make the existing single append call it with a list of one;
  - add `actor=` to `new_run` so `mode_history[0]` carries `by` and `relayed_by`;
  - make `_mode_lines` and `_resolution_lines` render a relayed entry as `by agent session S (relayed)` and never `by operator`.

  Existing `by: "operator"` records stay valid. (depends on T002)
- [x] T004 [P] Add `ActorTests` to `tests/test_autonomy.py`:
  - `resolve` with a session, with both streams terminals, and with neither, where it refuses with the exact text;
  - invalid sessions (empty, 81 characters, a leading `-`, a space, a session matching `HUMAN_APPROVAL`);
  - `allowed` for every row of the matrix;
  - `DECISION_FREE` pinned to exactly the three categories, so widening it fails until the test changes (AC-028). (depends on T002)
- [x] T005 Add `RelayedRecordSchemaTests` to `tests/test_autonomy.py`:
  - valid and invalid relayed HDs and mode-history entries for every rule in T003;
  - legacy `operator` records still validate;
  - `append_human_decisions` writes N chained lines, and with a crash injected before `write_atomic` (patched to raise) the file is byte-identical (AC-019);
  - `_mode_lines` and `_resolution_lines` render "relayed" and never "by operator" for relayed entries (AC-010, AC-013). (depends on T003, T004)

**Checkpoint**: The actor rule and the schemas are ready. US2 to US4 can begin.

---

## Phase 3: User Story 1 - Changes merged on the default branch need no trust or setup (Priority: P1) 🎯 MVP

**Goal**: A protected-input change merged on the pinned repository's default branch refreshes the baseline and regenerates the installation by itself, and says so. Anything unattributable still blocks for `ballast trust`.

**Independent Test**: In a stand-in bare repository with a reviewed baseline, merge a `ballast.toml` change on the default branch and run `setup --refresh`. It records a `default-branch` baseline naming the commit, and the launcher passes. A local edit, a branch-only commit, a `.venv` change, a repointed repository or an unobservable branch each leave every record byte-identical, and the launcher still names `ballast trust`.

### Acceptance tests for User Story 1

> Write these first and confirm they fail before implementing.

- [x] T006 [P] [US1] Add `RefreshEligibilityTests` to `tests/test_setup_trust.py`, using stand-in bare repositories through the `setup_trust.repository_url` seam and the Git argv log. Each case asserts that `trusted.json`, `trusted-source.json`, `reviewed-repositories.json` and the installation are byte-identical afterwards, that the result is `not refreshed: <reason>`, and that the launcher still refuses naming `ballast trust`. Cases:
  - an uncommitted `ballast.toml` edit; a commit on a branch absent on the default branch; a changed `.venv` (AC-002);
  - `[github] repository` repointed to an unreviewed repository and to another reviewed repository; legacy provenance without `repository` (AC-005);
  - offline; a timeout; an `insteadOf` rewrite; a `BALLAST_TAMPERED` marker; the `in-progress` marker. For the local conditions, the argv log shows no network Git command ran (AC-006);
  - a default-branch path that is a symlink or a submodule (R2).
- [x] T007 [US1] Add `RefreshRecordTests` to `tests/test_setup_trust.py`:
  - success: the default branch carries a new `ballast.toml` with one more `extra_allow` rule. `setup --refresh` regenerates `.ballast/spec_workflow/claude-settings.json` with the rule, records `source: "default-branch"` with `reference {repository, branch, commit}` and `repository`, adds the new (`ballast.toml`, constitution) pair under the same repository key in the reviewed record, prints `refreshed the trust baseline from OWNER/NAME BRANCH at COMMIT12 (N workflow inputs); regenerated the installation for ballast.toml`, and the launcher passes (AC-001);
  - a regeneration whose generated settings differ (patched producer) records nothing and restores the previous baseline and provenance (AC-004);
  - a regeneration failure (the standard fetch fails) records nothing and the launcher reports the unfinished setup;
  - the default branch moves between observation and record: only the observed commit is named, or nothing is recorded when a blob no longer matches (spec edge case);
  - `refresh_eligible` turns an injected exception into `not refreshed: internal error: <type>`. (depends on T006)
- [x] T008 [P] [US1] Add `TrustSettingsTests` and `RefreshStatusTests` to `tests/test_spec_workflow.py`:
  - `ballast trust` with a stale `claude-settings.json` (an `extra_allow` missing) refuses with the contract text, writes no baseline, and leaves the reviewed record byte-identical. A malformed `[agents.permissions]` also refuses (AC-003);
  - `trust` writes `repository` into `trusted-source.json`;
  - `status --json` reports `refusal_kind` (`inputs-changed`, `pin-mismatch`, `tamper`, `unfinished-step`, `no-baseline`, `setup-unfinished`) and `baseline_commit` when the source is `default-branch`;
  - the first `ballast run` after a `default-branch` refresh prints `trust baseline refreshed from OWNER/NAME BRANCH at COMMIT12` once and appends it to the ledger, and the next invocation does not repeat it (AC-001).
- [x] T009 [P] [US1] Add `RefreshTriggerTests` to `tests/test_ballast.py`:
  - for `run`, `ledger` and `intake`, `tools/ballast` runs `ensure_standard` and `setup --project ROOT --refresh` only when `refusal_kind` is `inputs-changed` or `pin-mismatch` and the pinned standard declares `[setup] refresh = true` (AC-001);
  - it never refreshes for other kinds, for other subcommands, for a launcher without `refusal_kind`, or for a standard without the declaration;
  - the subprocess's exit status is ignored and the launcher is executed afterwards;
  - `setup --refresh` is executed only from the standard's verified cache, never from the agent-writable checkout, even when the checkout contains a `tools/setup` (FR-020, analyze C1).
- [x] T010 [P] [US1] Add `RefreshSetupTests` to `tests/test_setup.py`:
  - `setup --refresh` refuses and changes nothing while another command holds the lock, after an unfinished attempt (saying "run `ballast setup`"), and with either marker present;
  - plain `ballast setup` runs `record_refresh` when `settle` skips and a baseline with a named repository exists (FR-001, second alternative);
  - `tools/setup` writes `claude-settings.json` through `launcher.merge_permissions` (one producer);
  - a test enumerating the installed files asserts `claude-settings.json` is the only one whose bytes depend on `ballast.toml` beyond the pin (R6, AC-004).
- [x] T011 [P] [US1] In `tests/test_branch_sync.py`, assert that `RECOVERY["protected-input"]` matches the [trust-refresh contract](contracts/trust-refresh.md#branch-synchronization) text, names the rerun command and `ballast trust`, and no longer says to run `ballast setup` first (FR-002, AC-001).

### Implementation for User Story 1

- [x] T012 [US1] In `tools/spec_workflow/launcher.py`:
  - move `merge_permissions` from `tools/setup` and add `generated_settings(standard_dir, config) -> bytes`, returning `json.dumps(..., indent=2) + "\n"` of the standard's `claude-settings.json` merged with `[agents.permissions]`;
  - give `record_baseline(state, inputs, *, source, reference=None, repository=None)` the `default-branch` source and the `repository` field. It stays the only writer of `trusted.json`;
  - make `baseline_source` return `default-branch`, and add `refresh_repository()`, which returns `repository` only from a bound record;
  - make `_trust` read `ballast.toml` once with `read_config`, refuse before writing when the generated settings differ or `[agents.permissions]` is malformed (contract text), and write `repository`;
  - add `refusal_kind` and `baseline_commit` to `status --json`;
  - export `BALLAST_REFRESHED` to `run.py` when the provenance is `default-branch` and was recorded after the run's last invocation;
  - update the module docstring.

  Leave the comparison, the refusals and the markers unchanged. (depends on T008)
- [x] T013 [US1] In `tools/setup`, delete the local `merge_permissions` (around `:1566`) and import it from the standard's `launcher.py`, keeping the written bytes identical. (depends on T010, T012)
- [x] T014 [US1] In `tools/spec_workflow/setup_trust.py`:
  - add `refresh_eligible(root, state, *, standard)`, which checks the [research R2](research.md#r2-refresh-eligibility-fr-001-fr-003-ac-002-ac-005-ac-006) conditions in order, reaches the network last, returns the first failing reason, and never raises;
  - classify the changed set into installed, tracked-unchanged-from-`HEAD` (the hardened plumbing of `_check_committed`) and unattributable;
  - observe every tracked changed path with one multi-path `ls-tree` reusing `_observe_in` on ADR-0015's throwaway path. Each must be a regular blob whose ID equals the local bytes;
  - add `record_refresh(root, state, verdict, record)`, which checks the recordable terms of [data-model.md](data-model.md#refresh-eligibility-transient-not-stored), calls `launcher.record_baseline(source="default-branch", ...)`, re-snapshots, restores the previous baseline and provenance on any difference, then calls `launcher.add_reviewed`. (depends on T007, T012)
- [x] T015 [US1] In `tools/setup`:
  - add `--refresh`, which takes the exclusive lock and refuses on a held lock, an unfinished attempt or a marker;
  - run `refresh_eligible`, printing `not refreshed: <reason>; the operator reviews and runs ballast trust` and exiting 0 when it is not eligible;
  - otherwise run `attempt(state, build)`, then `record_refresh`, and print the refreshed line;
  - make plain setup call `record_refresh` when `settle` skips and a named-repository baseline exists;
  - update the docstring. (depends on T013, T014)
- [x] T016 [US1] In `tools/ballast`:
  - for `run`, `ledger` and `intake`, after worktree preparation, read the launcher's `status --json`;
  - on `inputs-changed` or `pin-mismatch` with `Declarations.refresh`, call `ensure_standard(pin)` and run `python3 -IS <standard>/tools/setup --project ROOT --refresh` as a subprocess with stdout and stderr passed through, ignore its exit status, then `execv` the launcher as today;
  - add `refresh` to `Declarations`.

  In `tools/cli.toml`, add `refresh = true` under `[setup]`. (depends on T009, T015)
- [x] T017 [US1] In `tools/spec_workflow/run.py`, read `BALLAST_REFRESHED` and append its line once to the invocation output and the ledger (AC-001). (depends on T012)
- [x] T018 [P] [US1] In `tools/spec_workflow/branch_sync.py`, replace `RECOVERY["protected-input"]` with the contract text, keeping the `{rerun}` placeholder. (depends on T011)

**Checkpoint**: A default-branch change refreshes without `trust` or `setup` (SC-001). Every FR-019 trust refusal path has a test.

---

## Phase 4: User Story 2 - The agent runs mechanical commands and relays decisions within the run's autonomy (Priority: P1)

**Goal**: An agent session runs every decision-free command, relays `start --mode autonomous` and Chat approvals after an in-chat yes, and every relayed action is labeled. `reject`, `resolve` and `mode` stay at the operator's terminal. `trust` keeps working without a terminal outside a step and is refused inside one (D-09).

**Independent Test**: Start a Chat run terminal-less with `--relayed-by`, run a headless step, relay one approval, and check that status, `record.md` and the PR section say "relayed by agent session S". The same relay in a human-gated or Autonomous run is refused with the HD file unchanged.

### Acceptance tests for User Story 2

- [x] T019 [P] [US2] Add `RelayedApprovalTests` to `tests/test_chat_mode.py`:
  - a relayed `approve RUN GATE --relayed-by claude-code:t1` in a Chat run writes an HD with `by: "relayed"`, `relayed_by` and `ref == "relayed approve GATE"`. `ballast run status`, `record.md`, `allowed_actions`, the PR "Human approvals" section and the ledger gate log line show "relayed by agent session claude-code:t1" and never "by operator" (AC-010, SC-004);
  - a relayed approve in a human-gated run, and in a Chat run switched to human-gated, is refused with the AC-011 text and `human-decisions.jsonl` byte-identical (AC-011);
  - a terminal-less approve without `--relayed-by` is refused before writing;
  - `reject --relayed-by x`, and terminal-less `reject`, are refused with nothing recorded (AC-016);
  - `mode RUN chat` without a terminal is refused, `mode --relayed-by` is refused, and at a fake terminal `mode` needs the typed text `mode RUN TARGET`. (depends on T005)
- [x] T020 [US2] In `tests/test_chat_mode.py`:
  - extend `ForgeryTests`: a fake agent inside a step runs `ballast run approve RUN GATE --relayed-by x` and `ballast run start --mode autonomous --relayed-by x`, and both are refused by the `in-progress` marker with nothing recorded (AC-014);
  - add `HeadlessStepTests`. `step RUN PHASE --headless` builds the confined argv (bwrap, systemd scope, `CONFINED_ALLOW` and `CONFINED_DENY`, `--confined`), stops at the next pending gate, and prints `ballast run approve RUN --through GATE` (AC-015). A missing `bwrap` refuses. A terminal-less step without `--headless` refuses with the contract text naming `--headless`. `test_headless_step_keeps_todays_argv` still passes unedited. (depends on T019)
- [x] T021 [P] [US2] Add `RelayedStartTests` to `tests/test_autonomous_run.py`:
  - a terminal-less, eligible `start --mode autonomous --relayed-by claude-code:t1` writes `mode_history[0]` with `by: "relayed"` and `relayed_by`, and `record.md` renders "by agent session claude-code:t1 (relayed)" (AC-013);
  - the same start terminal-less without the flag is refused with the actor text and no run directory;
  - a relayed approve on an Autonomous run is refused with the AC-012 text and no HD file change (AC-012);
  - an invalid session, a session matching `HUMAN_APPROVAL`, and `--relayed-by` on `status` or `publish` are refused. (depends on T005)
- [x] T022 [P] [US2] Add `RelayedResumeTests` to `tests/test_autonomous_recovery.py`, iterating over `autonomy.BLOCK_CATEGORIES`:
  - for each category outside `actor.DECISION_FREE`, a relayed `resume` without `--ref` is refused with the D-08 text, and `human-decisions.jsonl` and `run.json` are byte-identical. A relayed `continue` without `--ref` is refused by today's argument rule, and the test asserts that text (F-003). With `--ref` both record a relayed `block-resolution` or `mode-change` carrying the ref. A `--ref` matching `HUMAN_APPROVAL` is refused;
  - for `upstream-sync`, `interrupted` and `postcondition`, a relayed `resume` without `--ref` succeeds and is recorded as relayed;
  - today's preconditions still fire first: `tamper` and `unfinished-step` cannot resume in Autonomous (AC-028). (depends on T005)
- [x] T023 [US2] Add `AgentStepEnvironmentTests` and `RelayedHumanGatedTests` to `tests/test_spec_workflow.py`:
  - with `BALLAST_AGENT_STEP=1`, every launcher command except `status` is refused (AC-014);
  - terminal-less `ballast trust` outside a step still records a baseline, and with `BALLAST_AGENT_STEP=1` it is refused with no baseline written (AC-016, D-09);
  - plan-review F-001: a terminal-less human-gated `start --relayed-by claude-code:t1` (and a relayed `resume`) with piped stdin (`approve\n`) pauses at the Spec Kit engine gate and records no approval. Use the existing human-gated run fixtures, skipping only where they already skip without the Spec Kit CLI. (depends on T008)

### Implementation for User Story 2

- [x] T024 [US2] In `tools/spec_workflow/launcher.py`:
  - make `main` refuse every command except `status` when `BALLAST_AGENT_STEP` is set, with a message saying it is defence in depth and the marker is the boundary. This covers `ballast trust` inside a step (D-09);
  - add no terminal check to `_trust`: outside a step it keeps today's terminal-free behavior and its existing marker refusals (D-09, AC-016);
  - accept no `--relayed-by` on any launcher command. (depends on T012, T023)
- [x] T025 [US2] In `tools/spec_workflow/agent.py`:
  - add `--confined`, which applies the Autonomous confinement (bwrap, scope, confined lists, self-test) without an Autonomous record;
  - set `BALLAST_AGENT_STEP=1` in every step environment (headless, confined and interactive). (depends on T020)
- [x] T026 [US2] In `tools/spec_workflow/run.py`:
  - parse `--relayed-by SESSION` on `start`, `resume`, `continue` and `approve`, and refuse it elsewhere through `actor.allowed`;
  - call `actor.resolve` before anything is written for every decision-recording command: `start` in every mode, `resume`, `continue`, and `approve` in Chat;
  - add early refusals in `_chat_command` for relayed approvals in human-gated and Autonomous runs;
  - apply the D-08 `--ref` rule to a relayed `resume` and `continue` through `actor.allowed` with the stopped run's `block.category`;
  - pass the actor to `autonomy.new_run(actor=)` and to the `block-resolution` and `mode-change` records;
  - for human-gated `start` and `resume`, validate `--relayed-by` and write no new record (F-002). (depends on T001, T003, T017, T021, T022)
- [x] T027 [US2] In `tools/spec_workflow/chat.py`:
  - record a relayed single-gate approval (no prompt, the same validation, `ref = "relayed approve GATE"`);
  - make `mode` require terminals and the typed text `mode RUN TARGET`, refusing `--relayed-by`;
  - keep `reject` and `resolve` terminal-only;
  - add `step RUN PHASE --headless` through a confined `_headless`, which passes `--confined` to `agent.py`, then prints the next pending gates and `ballast run approve RUN --through GATE`;
  - change the terminal-less non-headless refusal to the contract text;
  - make the status "Gates:" lines append `, relayed by agent session S`, and do the same in `allowed_actions` and `publish_section`.

  In `tools/spec_workflow/ledger.py`, make the gate `log_line` render relayed actors the same way. (depends on T019, T020, T025, T026)
- [x] T028 [US2] Adapt the existing tests that run terminal-less `start`, `resume`, `continue` or Chat `approve` in-process. They now pass `--relayed-by` or use the `TTY` stand-in, in `tests/test_autonomous_run.py`, `tests/test_autonomous_recovery.py`, `tests/test_chat_mode.py`, `tests/test_spec_workflow.py`, `tests/test_agent_run_ledger.py` and `tests/test_autonomy.py`. Where a terminal-less call asserted `by: "operator"` (for example `tests/test_autonomy.py:1993`, `tests/test_autonomous_run.py:1290`, `tests/test_chat_mode.py:2494` and `:4063`), choose the TTY stand-in when the test is about operator behavior, and otherwise change the expectation to `relayed` by design (FR-011). List every changed assertion in the PR description. Do not weaken or delete any refusal, tamper or validation test. (depends on T026, T027)
- [x] T029 [US2] Add `AgentSessionEndToEndTests` to `tests/test_chat_mode.py`. Drive a Chat run for a fixture R1 feature with fake agents from `start --mode chat --relayed-by claude-code:e2e` through headless steps, relayed approvals and `publish`, with every command terminal-less. Assert that no command needed a terminal, that every HD is `relayed` with the session, and that no record or output says "by operator". The only remaining operator action is the merge (AC-008, SC-002). (depends on T027, T028)

**Checkpoint**: Every decision-free command runs from an agent session, and every relayed action is labeled (SC-004).

---

## Phase 5: User Story 3 - Approve several pending gates at once (Priority: P2)

**Goal**: One command, one listing, one typed confirmation, all-or-nothing.

**Independent Test**: With scope, intent, plan and tasks pending, `approve RUN scope intent plan tasks` at a fake terminal shows four artifacts and digests, takes one line and writes four chained HDs. A not-pending gate or a mismatched line records nothing.

### Acceptance tests for User Story 3

- [x] T030 [US3] Add `BatchApprovalTests` to `tests/test_chat_mode.py`:
  - four pending gates at a fake terminal show one block listing each gate, artifact path and `sha256:` digest, then `Type \`approve scope intent plan tasks\` to confirm:`; one typed line writes four HDs in one hash chain, and the ledger gets four gate events (AC-017);
  - `--through tasks` selects the same pending and stale set, and a stale gate is included (AC-018);
  - each of the following leaves `human-decisions.jsonl`, the ledger and the intent and tasks baselines byte-identical, with the reason printed (AC-019): a not-pending gate, a mismatched typed line, a failing precondition on the third gate, an active agent step, a digest changed between display and record, gates out of order or duplicated, `--through` combined with explicit gates, and a crash injected before the atomic write;
  - a terminal-less batch in a human-gated run is refused, and a relayed batch in Chat writes one relayed `gate-approval` per gate (AC-020);
  - a single-gate `approve RUN GATE` keeps the prompt `approve GATE`. (depends on T029)

### Implementation for User Story 3

- [x] T031 [US3] In `tools/spec_workflow/chat.py`, add `approve_many(run, gates, actor)`:
  - under one run lock, validate every gate as pending or stale, run `_require_no_step`, and evaluate each `gate_precondition` with the batch's earlier gates treated as approved at their current digests;
  - display the block and read one line at a terminal; skip the prompt for a relayed actor;
  - re-read every digest, then write all HDs through `autonomy.append_human_decisions`;
  - run the per-gate side effects in gate order (`record_intent`, the tasks baseline, the ledger events).

  Route the single-gate approve through it with today's prompt text. (depends on T027, T030)
- [x] T032 [US3] In `tools/spec_workflow/run.py` `_chat_command`, parse `approve RUN GATE [GATE ...]` and `--through GATE` (mutually exclusive, `GATES` order, no duplicates), pass the resolved actor, and call `chat.approve_many`. (depends on T026, T031)

**Checkpoint**: Four gates take one command and one confirmation (SC-003).

---

## Phase 6: User Story 4 - Recover without extra commands (Priority: P2)

**Goal**: `discard-runs`, postcondition resume, usage-limit stops and the Autonomous branch rule recover through commands the agent may already run.

**Independent Test**: Each recovery path in its test module ends resumable with no `trust`, `setup` or `discard-runs` beyond what the contract names.

### Acceptance tests for User Story 4

- [x] T033 [P] [US4] Add `DiscardRunsArgumentTests` to `tests/test_spec_workflow.py`:
  - `discard-runs --help` and `-h` print usage to stdout, exit 0, and leave run state and lock files byte-identical (AC-021);
  - `discard-runs --bogus` exits 2 with `ballast: refusing: discard-runs takes no arguments (see --help)` and the same state (AC-022);
  - after a discard with unchanged inputs, the `Next:` line names no `ballast trust` and the next launcher check passes; with changed inputs it names `ballast trust`; with a tamper marker it prints the tamper recovery (AC-023). (depends on T028)
- [x] T034 [P] [US4] Add `PostconditionReentryTests` to `tests/test_autonomous_recovery.py`. After a `postcondition` block at `validate-implementation`, `resume` rewrites the engine state to re-enter at `implement`, keeps the implementation baseline, counts the agent step against the limit, and `validate-implementation` runs after it (AC-024). (depends on T028)
- [x] T035 [P] [US4] Add `UsageLimitStopTests` to `tests/test_agent_run_ledger.py`:
  - a fake agent CLI prints a usage-limit signature from `fallback.SIGNATURES` and exits 1 with no fallback configured, and the wrapper confirms the scope stopped. The result is `EXIT_USAGE_LIMIT`, a block of category `interrupted` with the detail "the agent CLI hit its provider usage limit", the marker removed, and the run resumable without `discard-runs` or `trust` (AC-025);
  - a killed wrapper leaves the marker, and the next start refuses with `unfinished-step` (AC-026);
  - with a fallback configured, today's behavior is unchanged. (depends on T028)
- [x] T036 [P] [US4] Add `IssueBranchOfferTests` to `tests/test_autonomous_run.py`:
  - at a fake terminal on a branch without the Issue number, typing `switch feat-N-slug` runs `git switch -c feat-N-slug` through the hardened Git, eligibility is rechecked, and the start proceeds. When exactly one local branch carries the Issue number, the proposal is that branch with `git switch`;
  - any other answer stops with HEAD unchanged;
  - without a terminal, and with `--relayed-by`, it exits 2 printing the refusal, `Switch first: git switch -c feat-N-slug` and the rerun command, with HEAD unchanged (AC-027). (depends on T028)

### Implementation for User Story 4

- [x] T037 [US4] In `tools/spec_workflow/launcher.py`:
  - make `main` handle `discard-runs` arguments first (`--help` and `-h` print usage and exit 0 with no lock; anything else exits 2), before the uninstalled-checkout refusal;
  - after a discard, make `_discard` run `_trust_refusal` without the removed marker and print the conditional `Next:` line from the contract;
  - update `RECOVER` to say "then `ballast trust` if `ballast run status` still reports changed inputs". (depends on T024, T033)
- [x] T038 [US4] In `tools/spec_workflow/autonomy.py`, update `RECOVERY`:
  - `unfinished-step` and `tamper` say "then `ballast trust` if `ballast run status` still reports changed inputs". Tamper keeps its review-then-trust step;
  - add the `interrupted` usage-limit text `wait for the usage limit to reset, then ballast run resume RUN` (Chat: `ballast run step RUN PHASE`). (depends on T003, T035)
- [x] T039 [US4] In `tools/spec_workflow/agent.py`, classify every failed agent exit with `fallback.classify` against `fallback.SIGNATURES`, whether or not a fallback is configured. When a usage-limit signature is found and `stop_scope` and `_stop_descendants` confirmed the stop, remove the marker and exit with a new `EXIT_USAGE_LIMIT`. Leave the local-fallback path unchanged. (depends on T025, T035)
- [x] T040 [US4] In `tools/spec_workflow/run.py`:
  - make `_block_step` map a failed `validate-implementation` with category `postcondition` to `implement`;
  - map `EXIT_USAGE_LIMIT` to `interrupted` in `WRAPPER_CATEGORIES`, with the detail text;
  - in `_start_autonomous`, when `check_eligibility` fails only on `BRANCH_REFUSAL`, propose the branch as in [research R14](research.md#r14-issue-named-branch-at-autonomous-start-fr-017-ac-027-d-06) (validated by `git check-ref-format --branch`), prompt only at a terminal without `--relayed-by`, switch through `draft_pr._resolve`'s Git, and otherwise print the contract refusal. (depends on T032, T034, T036, T039)

**Checkpoint**: Each #141 recovery needs no operator command without a decision.

---

## Phase 7: Governing documents (FR-013, FR-014, FR-018)

**Purpose**: The ADR, the constitution amendment and the operator-facing documents, consistent with `actor.py`. Edit policies only at `templates/policies/`. `docs/policies/*.md` outside `project/` are git-ignored installed copies that follow the pinned release, so do not edit them.

- [x] T041 [P] Write `docs/adr/0020-agent-sessions-relay-decisions.md` (status: proposed, agent-provisional until merge), following the format of `docs/adr/0019-feature-local-ui-states.md`. Cover:
  - the agent command matrix, as the same command names as `actor.py`'s matrix, with the decision-free block categories;
  - the actor rule (R7);
  - the default-branch refresh and its conditions (R1 to R5), including both narrowings for merge review;
  - the trust settings check (R6);
  - batch approval (R9), headless Chat steps (R10) and the recovery changes (R11 to R14);
  - the dependency on Spec Kit engine gates prompting only at a terminal (F-001);
  - residual risks: branch protection on the pinned default branch is the review of configuration changes; a relayed approval or `--ref` is an unverifiable labeled claim; the terminal test is not proof of a human, since an agent session can allocate a pseudo-terminal (first plan review); `ballast trust` has no terminal test (D-09), so on a checkout the operator's agent session set up, that session can vouch for its own protected-input changes outside a step, and only the step boundary (the `in-progress` marker, the sandbox hiding operator state) keeps a confined agent from doing so; `.venv` changes still need trust; `BALLAST_AGENT_STEP` is not a boundary.

  Add "Supersedes in part: ADR-0004, ADR-0009" and "Amends: ADR-0010, ADR-0015" lines. (depends on T002)
- [x] T042 Add a one-line "superseded in part by ADR-0020" or "amended by ADR-0020" note beside the affected clauses:
  - in `docs/adr/0004-autonomous-provisional-decisions.md`, at the rejected alternative "piping approvals";
  - in `docs/adr/0009-chat-mode-operator-driven-steps.md`, at D-1 and D-4;
  - in `docs/adr/0010-autonomous-resume-and-bounded-recovery.md`, at the re-entry rule;
  - in `docs/adr/0015-setup-recorded-trust-baseline.md`, at provenance, the reviewed record and the refresh. (depends on T041)
- [x] T043 [DEFERRED-TO-PR] The operator applies [constitution-amendment.md](constitution-amendment.md) to `.specify/memory/constitution.md` before merge; the implement step only keeps `constitution-amendment.md` complete and exact: the BL-INV-002 text, version 1.3.0, and the amendment-history entry with its reason and compatibility (FR-014).
- [x] T044 In `templates/policies/spec-kit-workflow.md` (runner contract table, Chat runs, Autonomous runs, branch synchronization, trust) and `templates/policies/workflow.md` (supervision modes), add the agent command matrix with the same command names as `actor.py` (`trust` agent-runnable outside a step, D-09), relayed decisions and the D-08 `--ref` rule, batch approval, the headless Chat step, the automatic refresh and the recovery texts (AC-007, FR-008, FR-018). (depends on T041)
- [x] T045 [P] In `AGENTS.md` (`CLAUDE.md` links to it), `templates/AGENTS.md` and `templates/init/agents-section.md`, replace "an agent never runs `ballast run`" with the distinction between agent sessions and steps, the relay rules per mode, the terminal-only `reject`, `resolve` and `mode`, and `ballast trust` as agent-runnable outside a step on a checkout the session set up, never inside one (D-09, FR-018). (depends on T041)
- [x] T046 [P] In `templates/skills/ballast-feature-intake/SKILL.md`, change the handoff: the session runs mechanical commands with `--relayed-by`, relays approvals only in Chat after an in-chat yes, relays a decision-carrying `resume` only with `--ref`, and may run `ballast trust` outside a step but never `ballast run reject` (D-09, FR-018). (depends on T041)
- [x] T047 [P] Update `README.md` and `specs/TECHNICAL-SPEC.md` §37 and §9.1 with the same content in user and architecture form: the refresh, the actor rule, batch approval, headless Chat steps, and that an older global CLI never refreshes (`ballast self-install`) (FR-018). (depends on T041)
- ~~T048~~ Dropped (D-09): `ballast.toml` is unchanged because `trust` keeps working without a terminal.
- [x] T049 Add `AgentCommandMatrixDocumentTests` to `tests/test_governance.py`, following its `LocalFallbackDocumentTests` pattern:
  - the policy table in `templates/policies/spec-kit-workflow.md` and ADR-0020 name exactly the commands of `actor.py`'s matrix, with agent-runnable and operator-reserved sets compared as sets, and the decision-free categories (AC-007);
  - ADR-0020 carries its supersedes and amends lines, each autonomy level's commands, the pseudo-terminal residual risk and the D-09 residual risk that `trust` has no terminal test (AC-009);
  - the policy table, ADR-0020, `AGENTS.md` and its templates never call `ballast trust` terminal-only or operator-reserved (D-09);
  - `constitution-amendment.md` states version 1.3.0, the new BL-INV-002 text and an amendment-history entry with reason and compatibility (FR-014); the live constitution is checked at merge (T043);
  - `AGENTS.md`, `templates/AGENTS.md`, `templates/init/agents-section.md` and the intake skill no longer say an agent never runs `ballast run` (FR-018);
  - the existing link checks pass for the new ADR. (depends on T042, T044, T045, T046, T047)

---

## Phase 8: Polish & Cross-Cutting Concerns

- [x] T050 Write `specs/147-human-gates-are-decisions/acceptance-evidence.json` as `{"schema_version": 1, "spec_digest": "<sha256 of spec.md>", "criteria": {...}}`, computing the digest of the committed `spec.md` at implementation time. Map every criterion to the dotted test IDs that prove it:
  - AC-001: `RefreshRecordTests` (T007), `RefreshTriggerTests` (T009), `RefreshStatusTests` (T008), `RefreshSetupTests` (T010), and the T011 case;
  - AC-002, AC-005, AC-006: `RefreshEligibilityTests` (T006);
  - AC-003: `TrustSettingsTests` (T008);
  - AC-004: `RefreshRecordTests` and `RefreshSetupTests`;
  - AC-007, AC-009: `AgentCommandMatrixDocumentTests` (T049);
  - AC-008: `AgentSessionEndToEndTests` (T029);
  - AC-010, AC-011, AC-016: `RelayedApprovalTests` (T019), plus T023 for AC-016;
  - AC-012, AC-013: `RelayedStartTests` (T021);
  - AC-014: `ForgeryTests` (T020) and `AgentStepEnvironmentTests` (T023);
  - AC-015: `HeadlessStepTests` (T020);
  - AC-017 to AC-020: `BatchApprovalTests` (T030), plus the crash case of `RelayedRecordSchemaTests` (T005) for AC-019;
  - AC-021 to AC-023: `DiscardRunsArgumentTests` (T033);
  - AC-024: `PostconditionReentryTests` (T034);
  - AC-025, AC-026: `UsageLimitStopTests` (T035);
  - AC-027: `IssueBranchOfferTests` (T036);
  - AC-028: `RelayedResumeTests` (T022) and `ActorTests` (T004).

  No criterion is `[]`. (depends on T007, T010, T016, T018, T024, T029, T032, T037, T038, T040, T049)
- [x] T051 Run `uv run --locked ruff check`, `uv run --locked ruff format --check`, and `uv run --locked python -m unittest` on each changed test module (one invocation each). Fix findings in the changed files. Record in the implement step's output which tests could not run inside the confined step and why, for the full gate. (depends on T050)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: none. T001 only edits the contract and is already done.
- **Foundational (Phase 2)**: none. It blocks US2, US3 and US4, but not US1.
- **US1 (Phase 3)**: none. It can start in Wave 1 alongside the foundation.
- **US2 (Phase 4)**: needs the foundation, and US1's `launcher.py` (T012) and `run.py` (T017) edits first, because those files take one writer at a time.
- **US3 (Phase 5)**: needs US2's relayed approval and actor plumbing (T026, T027, T029).
- **US4 (Phase 6)**: needs the foundation. Its tests wait for T028's test adaptations, and its implementation waits for the US2 and US3 edits of the same files.
- **Governing documents (Phase 7)**: need only `actor.py` (T002) for the matrix names.
- **Polish (Phase 8)**: needs every story and the documents.

### User Story Dependencies

- **US1 (P1)**: independent.
- **US2 (P1)**: logically independent of US1. It depends on US1 only through shared files.
- **US3 (P2)**: builds on US2's relayed single-gate approval.
- **US4 (P2)**: logically independent. It shares `launcher.py`, `run.py`, `agent.py` and the test modules with US1 to US3.

### Within Each User Story

- Tests are written first and fail before implementation.
- `actor.py` and the schemas come before `run.py` and `chat.py`.
- `launcher.py` comes before `tools/setup`, `tools/setup` before `tools/ballast`.

### Parallel Opportunities

- Wave 1 runs six independent tasks: `actor.py` and five US1 test modules. T001 is already done, and T043 is deferred to the PR.
- The US1 implementation, the foundation tests and the documents run side by side in Waves 2 to 4.
- The US4 test modules (T033 to T036) run in parallel in Wave 9.

---

## Execution Wave DAG

Tasks grouped by dependency resolution. Tasks within the same wave can run in parallel, and no two tasks in a wave edit the same file.

```text
Wave 1 (no dependencies):
  T001      contracts/cli.md F-002, F-003 (done)
  T002      actor.py
  T006 [P]  [US1] RefreshEligibilityTests (test_setup_trust)
  T008 [P]  [US1] TrustSettingsTests, RefreshStatusTests (test_spec_workflow)
  T009 [P]  [US1] RefreshTriggerTests (test_ballast)
  T010 [P]  [US1] RefreshSetupTests (test_setup)
  T011 [P]  [US1] branch-sync recovery test
  T043      constitution 1.3.0 [DEFERRED-TO-PR, operator]

Wave 2:
  T003      autonomy.py schemas (depends on T002)
  T004 [P]  ActorTests (depends on T002)
  T007      [US1] RefreshRecordTests (depends on T006)
  T012      [US1] launcher.py provenance, settings, status (depends on T008)
  T018 [P]  [US1] branch_sync.py text (depends on T011)
  T023      [US2] AgentStepEnvironmentTests, RelayedHumanGatedTests (depends on T008)
  T041 [P]  ADR-0020 (depends on T002)

Wave 3:
  T005      RelayedRecordSchemaTests (depends on T003, T004)
  T013      [US1] tools/setup imports merge_permissions (depends on T010, T012)
  T014      [US1] setup_trust.py refresh (depends on T007, T012)
  T017      [US1] run.py refresh line (depends on T012)
  T024      [US2] launcher.py BALLAST_AGENT_STEP refusal (depends on T012, T023)
  T042      ADR notes 0004/0009/0010/0015 (depends on T041)
  T044      templates/policies (depends on T041)
  T045 [P]  AGENTS.md and templates (depends on T041)
  T046 [P]  feature-intake skill (depends on T041)
  T047 [P]  README, TECHNICAL-SPEC (depends on T041)

Wave 4:
  T015      [US1] tools/setup --refresh (depends on T013, T014)
  T019 [P]  [US2] RelayedApprovalTests (depends on T005)
  T021 [P]  [US2] RelayedStartTests (depends on T005)
  T022 [P]  [US2] RelayedResumeTests (depends on T005)
  T049      AgentCommandMatrixDocumentTests (depends on T042-T047)

Wave 5:
  T016      [US1] tools/ballast trigger, cli.toml (depends on T009, T015)
  T020      [US2] ForgeryTests, HeadlessStepTests (depends on T019)
  T026      [US2] run.py relays (depends on T001, T003, T017, T021, T022)

Wave 6:
  T025      [US2] agent.py --confined, BALLAST_AGENT_STEP (depends on T020)

Wave 7:
  T027      [US2] chat.py relays, mode, headless step, rendering; ledger.py (depends on T019, T020, T025, T026)

Wave 8:
  T028      [US2] adapt terminal-less tests (depends on T026, T027)

Wave 9:
  T029      [US2] AgentSessionEndToEndTests (depends on T027, T028)
  T033 [P]  [US4] DiscardRunsArgumentTests (depends on T028)
  T034 [P]  [US4] PostconditionReentryTests (depends on T028)
  T035 [P]  [US4] UsageLimitStopTests (depends on T028)
  T036 [P]  [US4] IssueBranchOfferTests (depends on T028)

Wave 10:
  T030      [US3] BatchApprovalTests (depends on T029)
  T037      [US4] launcher.py discard-runs (depends on T024, T033)
  T038      [US4] autonomy.py RECOVERY (depends on T003, T035)
  T039      [US4] agent.py usage limit (depends on T025, T035)

Wave 11:
  T031      [US3] chat.approve_many (depends on T027, T030)

Wave 12:
  T032      [US3] run.py batch parsing (depends on T026, T031)

Wave 13:
  T040      [US4] run.py re-entry, usage-limit category, branch offer (depends on T032, T034, T036, T039)

Wave 14:
  T050      acceptance-evidence.json (depends on T007, T010, T016, T018, T024, T029, T032, T037, T038, T040, T049)

Wave 15:
  T051      lint, format, changed test modules (depends on T050)
```

---

## Implementation Strategy

### MVP First (User Story 1)

1. Wave 1 to Wave 5 for US1 (T006 to T018). The refresh works and every trust refusal path is tested.
2. **Stop and validate**: `uv run --locked python -m unittest tests.test_setup_trust`, then the same for `tests.test_setup`, `tests.test_ballast`, `tests.test_spec_workflow` and `tests.test_branch_sync`.

### Incremental Delivery

1. Foundation and US1: the refresh (SC-001).
2. US2: relays and labeled records (SC-002, SC-004).
3. US3: batch approval (SC-003).
4. US4: recovery paths.
5. The governing documents and the evidence map. Everything ships in one PR, since ADR-0020 and the constitution amendment govern all four stories.

---

## Notes

- Never weaken a refusal, tamper or validation test. Assertions that change by design are only those in T028, and each is listed in the PR.
- `.specify/memory/constitution.md` and `ballast.toml` are protected inputs. The implement step edits neither: the operator applies the constitution amendment (T043) before merge and `ballast trust` is then run, and `ballast.toml` is unchanged (D-09).
- Commit after each wave or logical group with a Conventional Commit message.
