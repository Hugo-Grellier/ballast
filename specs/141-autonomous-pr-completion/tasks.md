---

description: "Task list for the Autonomous PR completion policy"
---

# Tasks: Autonomous PR completion policy

**Input**: Design documents from `specs/141-autonomous-pr-completion/`
**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md)

**Risk**: R2. Autonomous run `478cbe23`: every decision is agent-provisional, and merging the PR is the only human approval.

**Acceptance evidence**: Every behavior acceptance criterion (AC-001 to AC-018) has a test task below that cites it. T028 writes `acceptance-evidence.json`.

**Plan-review findings these tasks address** ([reviews/plan.md](reviews/plan.md), PD-0009, PD-0010):

- **F-001** (head race): the post-ready mismatch must not claim the PR is a Draft. T003 changes the design so the `forge-unverified` case prints `PR completion: unverified #<n> <url>: the forge did not report the PR ready at the published commit` and records `outcome: "unverified"` with `reasons: ["forge-unverified"]`. T022 names the race in ADR-0019.
- **F-005** (`cause` rule): follow the contract. `cause` is allowed with `forge-failed` or `pr-unreadable`. T003 updates research R9 to match.
- F-002, F-003 and F-004 are spec wording issues. Spec reconciliation handles them, so no task here touches them. F-006 is for the security and merge review.

**Verification commands**: Run one command per invocation, exactly in these forms, which `ballast.toml` `extra_allow` covers:

- `uv run --locked python -m unittest tests.test_completion`
- `uv run --locked python -m unittest tests.test_autonomy`
- `uv run --locked python -m unittest tests.test_agent_run_ledger`
- `uv run --locked python -m unittest tests.test_autonomous_run`
- `uv run --locked ruff format`
- `uv run --locked ruff check`

**Organization**: Tasks are grouped by user story so each story can be implemented and tested on its own. Every user story is P1. They are ordered US1 → US4 because US2 to US4 reuse the US1 harness.

## Format: `[ID] [P?] [Story?] Description [(depends on ...)]`

- **[P]**: Can run in parallel with other ready tasks once any listed dependencies are satisfied
- **[Story?]**: The user story the task belongs to (US1–US4)
- **(depends on ...)**: Explicit dependency on earlier task IDs

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Test harness and design-document fixes that later tasks build on.

- [X] T001 [P] Extend the stand-in `gh` in `tests/test_autonomous_run.py` (the fake that reads data files and `FAIL_<argv>` markers from its directory). (a) `pr ready <n> --repo <OWNER/NAME>` appends its argv to the fake's call log, sets the fake PR's `draft` to `false`, and fails with the marker's stderr and exit code when `FAIL_pr_ready` exists. (b) `api repos/<OWNER/NAME>/pulls/<n>` returns the fake PR JSON (`state`, `draft`, `base.ref`, `head.ref`, `head.sha`), where `head.sha` defaults to the commit publication pushed. A data file can override it (moved head), and another can keep `draft: true` after `pr ready` (unverified ready). Add a helper `pr_ready_calls()` that returns every logged `pr ready` argv. Existing fake behavior and existing tests must not change.
- [X] T002 Add a helper `_eligible_run(...)` in `tests/test_autonomous_run.py`. It drives an Autonomous run through the existing `RunCase` harness to publication with operator records that meet all 12 conditions (R1 scope risk, no privileged action, recorded `final-acceptance`, approved `spec-reconciliation` review verdict, no open finding above `low`, passing `checks.json` with `checked_tree` set, a packet whose criteria are all `verified`, no material decision, no `block-resolution`). Parameters let it write `[autonomous] completion` / `completion_max_severity` into the trusted `ballast.toml`, pass extra start flags, and override any single record. (depends on T001)
- [X] T003 [P] Align the design documents with the plan-review findings. In `specs/141-autonomous-pr-completion/research.md` R9, allow `cause` with `forge-failed` or `pr-unreadable` (F-005). In `specs/141-autonomous-pr-completion/data-model.md` and `specs/141-autonomous-pr-completion/contracts/output-and-ledger.md`, add the outcome `unverified` for the post-ready mismatch (F-001): line `PR completion: unverified #<n> <url>: the forge did not report the PR ready at the published commit`, event `outcome: "unverified"` with `reasons: ["forge-unverified"]` (required) and no `cause`. Keep `draft` for every other failure. Update research R8 so it no longer says the outcome is `draft`.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Policy parsing, the ledger kind and the pure eligibility core. Every story depends on them.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T004 [P] In `tools/spec_workflow/autonomy.py`: add `completion` and `completion_max_severity` to `POLICY_KEYS`. In `parse_policy`, store `completion_configured` (`draft`/`ready`) and `completion_max_severity` (`low`/`info`/`none`) only when the table sets the key. An unknown or non-string value is stored as `draft` / `low` and prints `ballast: ignored [autonomous] completion 'X': cannot widen eligibility` (or `completion_max_severity`) to stderr, using the existing `WIDENING` warning shape. Add `completion_policy(configured, flag)`: `ready` only when `configured == "ready"` and `flag in {None, "ready"}`, otherwise `draft`. Make `publish` also return `repo`, `number` and `commit` (`git rev-parse HEAD` after the push) without changing `ok`, `category`, `message` or `url`, and say in its docstring that publication itself never marks ready. With no key, every snapshot stays byte-identical to today's (FR-001, FR-002, FR-006, FR-013).
- [X] T005 [P] In `tools/spec_workflow/ledger.py`: add the `labels` value type (a list of 1–16 unique `label` strings, ENUM check per element) and `COMPLETION_REASONS` (`mode`, `policy-draft`, `risk`, `privileged-action`, `no-final-acceptance`, `not-converged`, `open-finding`, `checks`, `packet`, `material-change`, `block-resolved`, `head-moved`, `pr-changed`, `pr-unreadable`, `forge-failed`, `forge-unverified`, `internal-error`). Add the `pr_completion` kind to `FIELDS`, `ENUM_FIELDS`, `RUNNER_ONLY` and the required-source map (`runner`): `outcome` ∈ {`ready`, `draft`, `unverified`}, `pr_number` int, `commit` oid, `reasons?` labels (required for `draft` and `unverified`, forbidden for `ready`, exactly `["forge-unverified"]` for `unverified`), and `cause?` ∈ `PR_REASONS["failed-retryable"]`, allowed only when `reasons` contains `forge-failed` or `pr-unreadable`. Make `report` show the latest `pr_completion` beside `pull_request` and `acceptance_packet`. Document the kind, the `labels` type and the older-version incompatibility (as ADR-0018 records) in `tools/spec_workflow/ledger-schema.md`. (depends on T003)
- [X] T006 Create `tools/spec_workflow/completion.py` (standard library only, importable under `python3 -I -S`) with the pure core. `Reason(code, text)`. A frozen `Inputs(run, decisions, human, checks, packet, commit, pr)`. `reported(policy)` (true only when `completion_configured == "ready"`). `evaluate(inputs) -> tuple[Reason, ...]`, which checks conditions 1–12 in the order of research R5 and returns every failure, at most one per condition, with the fixed wording of data-model.md. The threshold uses `autonomy.SEVERITIES` with `low`/`info`/`none` as in research R13. Findings count when their disposition is `open` or `accepted-provisionally` in a current decision. Condition (12) maps a read failure to `pr-unreadable` (with cause), `autonomy._pr_problem` to `pr-changed`, and a `head.sha` mismatch to `head-moved`. Add `format_line(state, number, url, reasons)` for the `ready-for-review`, `draft` and `unverified` forms in contracts/output-and-ledger.md, leaving out `#<n> <url>` when the number is unknown, and `event_data(...)` building the `pr_completion` data. Import `COMPLETION_REASONS` from `ledger` rather than defining a second list. Text is filled only with validated values (risk level, mode, severity, action kinds via `autonomy.action_kind`, PD/HD IDs, counts, cause codes), never `gh` output or agent text. (depends on T003, T004, T005)
- [X] T007 [P] In `tests/test_autonomy.py`, add tests: `parse_policy` with each valid `completion` and `completion_max_severity`; unknown values such as `"Ready"`, `"merge"`, `"medium"`, `1` store `draft`/`low` and print the warning (FR-002, FR-006); no key leaves the snapshot without the new fields (FR-013); a `completion_policy` table covering every `(configured, flag)` pair; `publish` returns `repo`, `number` and `commit` and never runs `pr ready`; a decision draft declaring `mark-ready` is still refused as never authorizable (AC-017, keep the existing test and assert the kind is in `NEVER_AUTHORIZED`). Run `uv run --locked python -m unittest tests.test_autonomy`. (depends on T004)
- [X] T008 [P] In `tests/test_agent_run_ledger.py`, add `pr_completion` tests through `ledger.validate`: valid `ready`, `draft` and `unverified` events pass. Each of these is rejected: `ready` with `reasons`, `draft` without `reasons`, an unknown reason code, duplicate codes, more than 16 codes, `cause` without `forge-failed`/`pr-unreadable`, `unverified` with other reasons, a non-runner source, and `ballast ledger record pr_completion` (runner-only refusal). Also check the `report` line. Run `uv run --locked python -m unittest tests.test_agent_run_ledger`. (depends on T005)

**Checkpoint**: Policy parsing, the ledger kind and `evaluate` exist. User stories can begin.

---

## Phase 3: User Story 1 - A converged low-risk run ends with a PR ready for review (Priority: P1) 🎯 MVP

**Goal**: An opted-in, eligible Autonomous publication marks its PR ready for review exactly once, prints that it did, and records it in the ledger.

**Independent Test**: With `completion = "ready"` and `_eligible_run`, there is exactly one `pr ready 7 --repo acme/demo` call, the last line is `PR completion: ready-for-review #7 …; merging stays the only human approval`, there is one `pr_completion` event `ready`, and the exit status is 0.

### Implementation for User Story 1

- [X] T009 [US1] In `tools/spec_workflow/completion.py`, add `complete(root, run_id, publication, packet)`. It returns at once, printing and recording nothing, unless the run is `ballast-autonomous` and `reported(policy)`. Otherwise it collects `Inputs` from `autonomy.read_run`, `read_decisions`, `read_human_decisions` and `read_checks`, the in-process packet outcome and the publication's commit. It makes one read-back `gh api repos/<repo>/pulls/<n>` and calls `evaluate`. When nothing fails, it runs `gh pr ready <n> --repo <repo>` through `draft_pr._resolve` / `draft_pr._command` (resolved outside working trees, empty working directory, hardened environment) and classifies failures with `draft_pr._classify` into a `forge-failed` reason with its cause code. It then makes one verification read-back requiring `draft: false` and the same `head.sha`, which gives `ready`, or `unverified` on a mismatch (F-001). It prints exactly one `PR completion:` line and appends exactly one runner `pr_completion` event. It turns any exception into `internal-error` (`completion check failed (<ExceptionName>)`) and never raises. It never prints `gh` output or tokens. (depends on T006)
- [X] T010 [US1] In `tools/spec_workflow/run.py`: make `_publish` keep the successful publication (`repo`, `pr_number`, `url`, `commit` from `autonomy.publish`) in an in-process holder keyed by run ID, never persisted (research R1). Make `_checkpoint` return its outcome (skipped or the packet outcome), still swallowing exceptions as today. In `_run_autonomous` and `_resume_engine`, call a new `_complete(run_id, checkpoint_outcome)` right after `_checkpoint` in the same `finally`. It does nothing when this invocation did not publish or the checkpoint skipped (for example on `BALLAST_TAMPERED` or an unfinished-step marker), and it never changes the exit status or run state (FR-007, FR-011). In `_publish_command`, after a successful Autonomous `_publish`, run `_checkpoint` then `_complete` only when the snapshot has `completion_configured == "ready"`, so the output stays unchanged otherwise (research R2). Keep this inside the existing `_invocation_lock` without taking a second lock. Import `completion` at module start. (depends on T004, T009)

### Acceptance tests for User Story 1

- [X] T011 [US1] In `tests/test_autonomous_run.py`, add end-to-end tests for the ready path from `ballast run start` and from `ballast run resume`, using `_eligible_run` with `completion = "ready"`. Assert one `pr ready <n> --repo <pinned>` argv as the operator, the `PR completion: ready-for-review #<n> <url>; merging stays the only human approval` line after the `Acceptance packet:` line, exit 0, and run status `published` [AC-001]. Assert exactly one ledger `pr_completion` event with `outcome: "ready"`, the PR number and the pushed commit, and no `reasons` [AC-002]. Run `uv run --locked python -m unittest tests.test_autonomous_run`. (depends on T002, T010)
- [X] T012 [US1] In `tests/test_autonomous_run.py`, add tests. (a) After the ready run, `ballast run checkpoint RUN` prints `Draft PR: reused #<n>`, makes no `pr ready` call and leaves the fake PR non-draft [AC-003]. (b) `ballast run publish RUN` on the published run is refused as today, with no forge call [AC-003]. (c) A `ballast run publish` retry of a run whose first publication failed, with `completion = "ready"`, runs the checkpoint and packet and then reports the completion line. With no key, the same retry prints today's lines only (FR-007, research R2). Run `uv run --locked python -m unittest tests.test_autonomous_run`. (depends on T011)

**Checkpoint**: US1 is fully functional and testable on its own.

---

## Phase 4: User Story 2 - An ineligible run stays a Draft and says why (Priority: P1)

**Goal**: Each failed condition keeps the PR a Draft, the forge is never asked to mark it ready, and the line and the ledger name every failed condition in order.

**Independent Test**: For each of the 12 conditions, inputs that meet every other condition and fail that one give exactly that reason code, no `pr ready` call, and a `draft` line and event.

### Acceptance tests for User Story 2

- [X] T013 [P] [US2] Create `tests/test_completion.py` with a `make_inputs(**overrides)` builder that meets all 12 conditions, and tests on `completion.evaluate`. One test per condition fails only that condition and asserts the single expected code and wording: `mode` (human-gated, chat, lowered), `policy-draft`, `risk` (R2) [AC-004], `privileged-action`, `no-final-acceptance`, `not-converged`, `open-finding`, `checks` (not run, a failure, a timeout), `packet` (not published, failed-retryable, head mismatch, each non-verified count), `material-change`, `block-resolved`, and `head-moved` / `pr-changed` / `pr-unreadable` [AC-005, AC-007, SC-002]. R2 plus a `not run` criterion plus a material change gives `("risk", "packet", "material-change")` in that order [AC-006]. Severity thresholds: an open `low` with the default is eligible; `none` with an open `info` gives `open-finding`; `info` with an open `low` gives `open-finding`; an `accepted-provisionally` `medium` with the default gives `open-finding` naming `medium`; a superseded finding is ignored [AC-009]. Every reason text and the `ready-for-review`, `draft` and `unverified` line forms have no `autonomy.HUMAN_APPROVAL` match (FR-017). Run `uv run --locked python -m unittest tests.test_completion`. (depends on T006)
- [X] T014 [US2] In `tests/test_completion.py`, add tests for `completion.complete` with a stand-in `gh` on `PATH` like the one in `tests/test_autonomy.py`. An ineligible run makes only the first read-back and no `pr ready` call [AC-005]. A `pr ready` failure for each cause code (`gh-forbidden`, `gh-unauthenticated`, `github-unreachable`, `github-error`) gives a `draft` line `marking ready failed (<cause>)` and an event with `reasons: ["forge-failed"]` and that `cause` [AC-008]. A missing trusted `gh` gives `pr-unreadable` with `gh-missing`. A successful `pr ready` whose read-back is still `draft: true` or shows a different head gives the `unverified` line and event, and the line does not say `draft` (F-001). An exception raised inside collection gives `internal-error` and no exception escapes. A run without `completion_configured == "ready"` prints and records nothing. No line contains `gh` stderr text. Run `uv run --locked python -m unittest tests.test_completion`. (depends on T009, T013)
- [X] T015 [US2] In `tests/test_autonomous_run.py`, add end-to-end tests with `_eligible_run` and `completion = "ready"`. (a) An R2 scope record keeps the PR a Draft, the `PR completion: draft …: risk R2` line and the event `reasons` give `["risk"]`, and no `pr ready` is called [AC-004]. (b) A run with no final acceptance makes no `pr ready` call and names `no-final-acceptance` in both the line and the event [AC-005]. (c) A fake read-back `head.sha` that is not the pushed commit gives `head-moved` and no `pr ready` call [AC-007]. (d) `FAIL_pr_ready` with an `HTTP 403` stderr gives `marking ready failed (gh-forbidden)`, `reasons == ["forge-failed"]` and `cause == "gh-forbidden"`, and the exit status, run status (`published`) and the absence of a block equal those of a successful ready run [AC-008]. Run `uv run --locked python -m unittest tests.test_autonomous_run`. (depends on T011)

**Checkpoint**: US1 and US2 work on their own.

---

## Phase 5: User Story 3 - No configuration, no change (Priority: P1)

**Goal**: Without the opt-in, an Autonomous run, and every human-gated or Chat run, behaves exactly as before.

**Independent Test**: An eligible run without the `completion` key gives the same stdout, `run.json` and ledger events as the same run with `completion = "draft"`. Neither has a completion line, a `pr_completion` event, new snapshot fields or a `pr ready` call.

### Acceptance tests for User Story 3

- [X] T016 [US3] In `tests/test_autonomous_run.py`, add tests with `_eligible_run`. (a) No `[autonomous]` table, and a table without `completion`: no `pr ready` argv, no `PR completion:` line, no `pr_completion` event, and none of `completion_configured`, `completion_max_severity`, `completion_flag` or `completion` in the policy snapshot. The stdout lines, after normalizing run IDs, timestamps and temporary paths in the existing harness way, and the ledger event kinds and data, match a run of the same records, so the feature adds nothing [AC-010, SC-003]. (b) `completion = "draft"`: the same assertions, and stdout and ledger equal the no-configuration run [AC-011]. (c) `completion = "Ready"`: the start prints the `cannot widen eligibility` warning, and the run then behaves as no configuration (FR-002). (d) `completion_max_severity = "medium"` prints the warning and keeps the threshold `low` (FR-006). Run `uv run --locked python -m unittest tests.test_autonomous_run`. (depends on T011)
- [X] T017 [US3] In `tests/test_autonomous_run.py`, add tests with `completion = "ready"` in the trusted `ballast.toml`. A Chat run's publish, a human-gated run's publication and Draft PR checkpoint, and an Autonomous run lowered to human-gated or Chat (via `ballast run mode` or `continue`) before publication: none of them has a `pr ready` argv, and none prints a `PR completion:` line or records a `pr_completion` event [AC-012, FR-014]. `ballast run checkpoint` on an eligible Autonomous run never calls `pr ready` (FR-007). Run `uv run --locked python -m unittest tests.test_autonomous_run`. (depends on T011)

**Checkpoint**: US1 to US3 work on their own.

---

## Phase 6: User Story 4 - Only the operator controls the policy and the result (Priority: P1)

**Goal**: The start flag can only narrow the policy. A refresh keeps the flag. No agent-writable input changes the policy or the result.

**Independent Test**: `--completion ready` without a configured `ready` is refused before any run record or agent step. Agent-written changes to the checkout's `ballast.toml`, drafts or artifacts leave the effective policy and the reasons unchanged.

### Implementation for User Story 4

- [X] T018 [US4] In `tools/spec_workflow/run.py`: make `_split_mode` take `--completion`. Refuse `--completion needs --mode autonomous`, `--completion must be draft or ready`, and the existing given-twice refusal. In `_start_autonomous`, after `parse_policy` and before `check_eligibility` writes anything, refuse `--completion ready cannot widen ballast.toml [autonomous] completion (<configured>)` when the configured value is not `ready`. Otherwise record `completion_flag` and `completion = completion_policy(configured, flag)` in the policy snapshot (only when the key or the flag is present). Add `--completion` to `RESUME_FLAGS`. In `_resume_locked`, on `--refresh-policy`, replace `completion_configured` and `completion_max_severity` from the `ballast trust` baseline (removing them when they are unset), keep `completion_flag`, and recompute `completion`. Leave the existing `Re-read [autonomous]…` line and the `block-resolution` record unchanged. Update the module docstring and the usage line. (depends on T004, T010)

### Acceptance tests for User Story 4

- [X] T019 [US4] In `tests/test_autonomous_run.py`, add start-flag tests. (a) With no key and with `completion = "draft"`, `--completion ready` is refused with the widening message, leaving no run record, no ledger event and no engine launch [AC-015]. (b) With `completion = "ready"` and `--completion draft`, the snapshot has `completion: "draft"` and `completion_flag: "draft"`, no `pr ready` is called, the line reads `PR completion: draft …: the run's start flag chose draft`, and the event has `reasons == ["policy-draft"]` [AC-016]. (c) `--completion` with `--mode chat` or `human-gated`, a value such as `merge`, and the flag given twice are each refused. (d) `ballast run resume` and `continue` refuse `--completion`. Run `uv run --locked python -m unittest tests.test_autonomous_run`. (depends on T011, T018)
- [X] T020 [US4] In `tests/test_autonomous_run.py`, add refresh tests. A run started with `--completion draft` under configured `draft`, then a trusted `ballast.toml` changed to `ready` and a `ballast trust` baseline, then `resume --refresh-policy`: the snapshot keeps `completion: "draft"` and `completion_flag: "draft"`. The same sequence without the flag gives `completion_configured: "ready"` and `completion: "ready"` in the snapshot, and the publication reports `block-resolved` (condition 11) [AC-018]. Run `uv run --locked python -m unittest tests.test_autonomous_run`. (depends on T019)
- [X] T021 [US4] In `tests/test_autonomous_run.py`, add tamper tests. (a) The trusted `ballast.toml` has `completion = "draft"`, and an agent step's scenario rewrites the checkout's `ballast.toml` copy to `completion = "ready"` before publication. The effective policy stays `draft`, nothing is reported, and no `pr ready` is called [AC-013, SC-004]. If the protected-input check refuses the run first, assert that refusal and that no `pr ready` happens. (b) An ineligible run (no final acceptance) where agent steps write decision drafts, a `reviews/convergence.md` with `- Verdict: CONVERGED`, packet and record edits claiming verified criteria, low risk and passing checks: the reported reasons equal those of the same run without the writes [AC-014, SC-004]. (c) An agent decision draft declaring `mark-ready` inside a run is refused as never authorizable [AC-017]. Run `uv run --locked python -m unittest tests.test_autonomous_run`. (depends on T011)

**Checkpoint**: All user stories work on their own.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Architecture record, operator documentation, formatting and the acceptance-evidence mapping.

- [X] T022 [P] Write `docs/adr/0019-autonomous-pr-completion.md` (ADR-0019, status Proposed). Context: ADR-0004 publication. Decision: the trusted runner marks an eligible, opted-in Autonomous PR ready for review. It amends ADR-0004's Draft-only publication and its narrowing-only `[autonomous]` rule, and extends ADR-0003's command list with `gh pr ready <n> --repo <pinned>`. Record the 12 conditions, the pure evaluation over operator records, the verification read-back, the residual head race and its `unverified` outcome (F-001), the `pr_completion` kind and its older-version incompatibility, and that merge and auto-merge stay out (#143). Say that marking ready is not an approval and that merging stays the only human approval (FR-017). In `docs/adr/0004-autonomous-provisional-decisions.md`, add "Amended by ADR-0019" notes on the publication decision and the narrowing-only consequence. Add ADR-0019 to the ADR index if `docs/adr/` has one. (depends on T003)
- [X] T023 [P] Update `templates/policies/spec-kit-workflow.md`. Publication row: the publisher still opens a Draft PR, and for a run whose operator set `completion = "ready"` the runner marks it ready after the checkpoint and packet when every condition holds. Add a **PR completion** paragraph under Autonomous runs: keys, `--completion`, the 12 conditions, the `PR completion:` line forms, the `pr_completion` event, and that it is not an approval. Draft PR section: the checkpoint still never marks ready, with a pointer to PR completion. Resume: `--refresh-policy` also re-reads `completion` and keeps the start flag. (depends on T003)
- [X] T024 [P] Update the Autonomous bullet in `templates/policies/workflow.md` to: "It never merges, releases or deploys. It marks its PR ready for review only when the operator opted in and every completion condition holds, and that is not an approval."
- [X] T025 [P] Update `README.md`. Add `completion` and `completion_max_severity` to the `[autonomous]` configuration example. Add one paragraph on `--completion` and the `PR completion:` line. Scope the existing "never marks a PR ready" sentences to the Draft PR checkpoint and to runs without the opt-in.
- [X] T026 [P] Update `specs/TECHNICAL-SPEC.md`: in the §36 Autonomous paragraph and the v1.0 status paragraph, say that an eligible, opted-in Autonomous run ends with a PR ready for review and that the merge stays the single human approval. Link ADR-0019 and `specs/141-autonomous-pr-completion/spec.md`. (depends on T022)
- [X] T027 Run `uv run --locked ruff format`, then `uv run --locked ruff check`, and fix any finding in `tools/spec_workflow/completion.py`, `tools/spec_workflow/run.py`, `tools/spec_workflow/autonomy.py`, `tools/spec_workflow/ledger.py` and the changed `tests/test_*.py` files without weakening a rule. (depends on T007, T008, T012, T014, T015, T016, T017, T020, T021)
- [X] T028 Write `specs/141-autonomous-pr-completion/acceptance-evidence.json`: `{"schema_version": 1, "spec_digest": "<sha256 of spec.md>", "criteria": {...}}`. Map AC-001 to AC-018 to the dotted `unittest` IDs (`tests.test_module.Class.test_method`) of the tests from T007, T008 and T011 to T021 that prove each one. The mapping is a proposal; only `ballast ledger check` records evidence. (depends on T027)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies. T002 needs T001.
- **Foundational (Phase 2)**: T005 and T006 need T003. T006 also needs T004 and T005. T007 and T008 test T004 and T005. This phase blocks every story.
- **US1 (Phase 3)**: needs T006 (via T009) and T002. It provides `complete`, the run wiring and the ready-path tests that the other stories build on.
- **US2 (Phase 4)**: T013 needs only T006 and can start alongside US1. T014 needs T009. T015 needs T011.
- **US3 (Phase 5)**: needs T011.
- **US4 (Phase 6)**: T018 needs T010, because it edits the same `run.py`. T019 and T020 need T018. T021 needs only T011.
- **Polish (Phase 7)**: the documentation tasks are independent of code. T027 and T028 come last.

### User Story Dependencies

- **US1 (P1)**: after Foundational. No dependency on other stories.
- **US2 (P1)**: the pure tests (T013) need only Foundational. The I/O and end-to-end tests reuse US1's `complete` and harness.
- **US3 (P1)**: reuses the US1 harness and does not depend on US2 or US4.
- **US4 (P1)**: reuses the US1 harness and `run.py` wiring and does not depend on US2 or US3.

### Within Each User Story

- Shared code first (`completion.py` before `run.py` wiring), then the end-to-end tests that exercise it.
- `run.py` is edited by T010 and then T018, never in parallel. `tests/test_autonomous_run.py` is edited by T001, T002, T011, T012, T015, T016, T017, T019, T020 and T021. Run those tasks one at a time even when the DAG lets them start together.

### Parallel Opportunities

- T001 and T003. Then T004 and T005 (different files). Then T007 and T008.
- T013 (`tests/test_completion.py`) alongside T009 and T010.
- The documentation tasks T022 to T025 alongside any code work.

---

## Execution Wave DAG

Tasks grouped by dependency resolution. Tasks in the same wave can run in parallel, except that tasks editing the same file run one after another.

```text
Wave 1 (no dependencies):
  T001 [P] Stand-in gh: pr ready and PR read-back (tests/test_autonomous_run.py)
  T003 [P] Design-doc fixes F-001, F-005 (research, data-model, output contract)
  T004 [P] autonomy.py policy keys, completion_policy, publish return keys
  T024 [P] templates/policies/workflow.md Autonomous bullet
  T025 [P] README.md

Wave 2:
  T002     _eligible_run helper (depends on T001)
  T005 [P] ledger.py pr_completion kind and labels type (depends on T003)
  T007 [P] tests/test_autonomy.py (depends on T004)
  T022 [P] ADR-0019 and ADR-0004 notes (depends on T003)
  T023 [P] templates/policies/spec-kit-workflow.md (depends on T003)

Wave 3:
  T006     completion.py pure core (depends on T003, T004, T005)
  T008 [P] tests/test_agent_run_ledger.py (depends on T005)
  T026 [P] specs/TECHNICAL-SPEC.md (depends on T022)

Wave 4:
  T009 [US1] completion.complete I/O (depends on T006)
  T013 [P] [US2] tests/test_completion.py evaluate tests (depends on T006)

Wave 5:
  T010 [US1] run.py wiring (depends on T004, T009)
  T014 [US2] tests/test_completion.py complete tests (depends on T009, T013)

Wave 6:
  T011 [US1] ready path end-to-end (depends on T002, T010)
  T018 [US4] run.py start flag and refresh (depends on T004, T010)

Wave 7 (same test file: run one at a time):
  T012 [US1] checkpoint and publish retry after ready (depends on T011)
  T015 [US2] ineligible end-to-end paths (depends on T011)
  T016 [US3] no-configuration identity (depends on T011)
  T017 [US3] Chat, human-gated, lowered (depends on T011)
  T019 [US4] start-flag tests (depends on T011, T018)
  T021 [US4] tamper tests (depends on T011)

Wave 8:
  T020 [US4] refresh tests (depends on T019)

Wave 9:
  T027     ruff format and check (depends on T007, T008, T012, T014, T015, T016, T017, T020, T021)

Wave 10:
  T028     acceptance-evidence.json (depends on T027)
```

---

## Acceptance criteria coverage

| AC | Test task(s) |
| --- | --- |
| AC-001 | T011 |
| AC-002 | T011 |
| AC-003 | T012 |
| AC-004 | T013, T015 |
| AC-005 | T013, T014, T015 |
| AC-006 | T013 |
| AC-007 | T013, T015 |
| AC-008 | T014, T015 |
| AC-009 | T013 |
| AC-010 | T016 |
| AC-011 | T016 |
| AC-012 | T017 |
| AC-013 | T021 |
| AC-014 | T021 |
| AC-015 | T019 |
| AC-016 | T019 |
| AC-017 | T007, T021 |
| AC-018 | T020 |
| AC-019 | T014, T008 (DEC-0001) |

FR-002 and FR-006 are covered by T007 and T016. FR-010's validation is covered by T008, and FR-017 by T013. SC-005 (the fast and full gate) is a workflow-owned step, not a task.

---

## Implementation Strategy

### MVP First (User Story 1)

1. Phase 1 and Phase 2.
2. Phase 3 (US1): an opted-in eligible run is marked ready, verified and recorded.
3. **Stop and validate**: run `uv run --locked python -m unittest tests.test_autonomous_run` and `uv run --locked python -m unittest tests.test_completion`.

US1 alone is not safe to ship: US2's fallbacks, US3's no-configuration identity and US4's narrowing guarantees are all part of the R2 contract. Merge only with all four stories done.

### Incremental Delivery

1. Setup + Foundational → policy, ledger kind and pure evaluation.
2. US1 → ready path.
3. US2 → every fallback reason.
4. US3 → unchanged behavior without the opt-in.
5. US4 → operator-only control.
6. Polish → ADR-0019, documentation, formatting, evidence mapping.

---

## Notes

- Marking ready is never an approval. Every line, event, document and ADR says that merging stays the only human approval.
- With no `completion` key, nothing new runs, prints or records (FR-013). Any doubt keeps the Draft.
- No task here covers reviews, the full gate, quickstart runs, converge or spec reconciliation. The workflow runs them after implementation. Spec reconciliation should reword AC-003, FR-009/AC-004 and AC-018 as findings F-002 to F-004 ask.
