---

description: "Task list for on-demand UI demo capture linked to the PR"
---

# Tasks: On-demand UI demo capture linked to the PR

**Input**: Design documents from `specs/22-ui-demo/`: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md), [decisions.md](decisions.md) (DEC-0001).

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Acceptance evidence**: Each behavior acceptance criterion has a test task citing its `AC-NNN` ID. All tests are offline `unittest`. `gh` is #17's scripted `_command` fake, Git is a real temporary repository, and the clock and sleep are injected. No test dispatches a real workflow. SC-001 (live pilot) and SC-004 (local reproduction of a real journey) are post-merge operator evidence ([research R13](research.md#r13-pilot-evidence-sc-001), [quickstart](quickstart.md#post-merge-pilot-sc-001-operator)). They are listed in the PR as open items, not as tasks here.

**Workflow-owned steps**: The fast and full gates, quickstart runs, the engineering, security, test and documentation reviews, the dependency evaluation of `actions/checkout` and `actions/upload-artifact`, converge and spec reconciliation are run by the workflow after implementation. They are deliberately not tasks here.

**Organization**: Tasks are grouped by user story. Tests are written first and must fail before the implementation they cover.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel with the other ready tasks of its wave (it touches a file no other task in that wave touches)
- **[Story]**: Which user story this task belongs to (US1–US4)
- Test and verification tasks cite the acceptance criterion IDs they prove, e.g. `[AC-001]`; quickstart scenario numbers are given as `Q<n>`

## Path Conventions

Single project: workflow tools in `tools/spec_workflow/`, the copy-once template in `templates/github/workflows/`, the policy template in `templates/policies/`, tests in `tests/`. Tools are standard-library-only and must import under `python3 -I -S` (FR-020). pyyaml is test-only.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: The new module and its test harness

- [X] T001 [P] Create `tools/spec_workflow/demo.py` with a module docstring and only standard-library imports, so it loads under `python3 -I -S`. Add these constants: the workflow file name `ballast-demo.yml` and its path `.github/workflows/ballast-demo.yml`; the fixed step names from [capture-workflow.md](contracts/capture-workflow.md#steps-in-order-names-are-part-of-the-contract-research-r5); the fixed reason strings from [data-model.md](data-model.md#democapture-resolved-at-each-checkpoint-derived-never-stored) and [demo-command.md](contracts/demo-command.md#output); the contract limits of [research R10](research.md#r10-contract-limits); the wait constants (10 s poll, 120 s cap); the run-list bounds (100 per page, 5 pages); and the 24 h `run-not-found` window. Add frozen dataclasses `DemoScenario`, `DemoConfig`, `DemoCapture`, `DemoSection` and `DemoOutcome` with the fields in data-model.md.
- [X] T002 [P] Create `tests/test_demo.py` with a shared harness. Reuse the scripted `gh` `_command` fake and temporary Git repository helpers from `tests/test_draft_pr.py` by importing them, not copying them. Add an injected clock and monotonic sleep seam, a helper that writes a `[demo]` table into the fixture `ballast.toml`, a helper that appends `demo_capture` events through `ledger.append`, and fake-response builders for the runs list (paged), jobs, artifacts, the workflow read, the contents blob read and the repository read (depends on T001)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The ledger event, the contract parser and the `gh` seam that every story uses

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T003 [P] Add the runner-only `demo_capture` kind to `tools/spec_workflow/ledger.py`: add it to `FIELDS`, `RUNNER_ONLY` and the source map, with field patterns `scenario` `[A-Za-z0-9._-]{1,64}`, `commit` oid (40 or 64 hex), `request` `[0-9a-f]{16}`, `command_digest` `[0-9a-f]{64}` and `pr_number` int ≥ 1, and no free-text field. Make `report` show the latest capture per scenario. Document the kind in `tools/spec_workflow/ledger-schema.md` ([research R7](research.md#r7-ledger-event-demo_capture))
- [X] T004 [P] Test the `demo_capture` event in `tests/test_agent_run_ledger.py`. A valid runner event is accepted. An agent-sourced event is rejected, as are a scenario with a space or markup, a non-16-hex `request`, a short `command_digest`, `pr_number` 0 and an extra free-text field. `report` shows only the newest event per scenario. Supports AC-006 and FR-018 (depends on T003)
- [X] T005 [P] Implement `demo_config(root)` in `tools/spec_workflow/demo.py` per [demo-config.md](contracts/demo-config.md):
  - read `[demo]` from `ballast.toml` with `tomllib` and never raise;
  - an unreadable file or an absent table gives `configured=False`, as `packet.review_config` does;
  - every rule violation gives exactly one of data-model.md's fixed `error` strings, with empty `scenarios`;
  - `retention_days` defaults to 14 and `timeout_minutes` to 15;
  - `video` is validated with `packet.safe_path`;
  - each scenario's `command_digest` is the sha256 hex of its UTF-8 command;
  - add `scenario(config, name)` lookup.
  (depends on T001)
- [X] T006 [P] In `tools/spec_workflow/draft_pr.py`, import `demo` so `run.py` loads it before any agent step. Expose the existing `_Checkpoint` `gh`/`api` seam (resolved program, argument list, hardened environment, empty working directory, 30 s limit, `_classify`) and a PR-head read for `demo.request` and `demo.collect` to use, with no behavior change. The existing `tests/test_draft_pr.py` must pass unchanged (depends on T001)

**Checkpoint**: Foundation ready. User story tests and implementation can begin.

---

## Phase 3: User Story 1 - Request a demo video and see it on the same PR (Priority: P1) 🎯 MVP

**Goal**: `ballast run demo RUN_ID SCENARIO` dispatches the capture on the feature branch, records it, waits a bounded time and refreshes the packet, which shows one line per scenario with the newest capture's outcome.

**Independent Test**: With one declared scenario and a `reused` Draft PR, request a capture and refresh the packet. The packet shows one demo line with a video link, the head commit, scenario, environment and `captured`. No `pr create` call is made.

### Acceptance tests for User Story 1

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T007 [US1] Test the successful request (Q1) in `tests/test_demo.py`. The argv sequence is exactly ADR-0012's:
  - checkpoint, PR read, repository read and workflow read;
  - two contents reads that return the same blob `sha`;
  - a `--method POST … /dispatches --input -` whose stdin JSON has `ref` = the feature branch (asserted never to be the default branch), `commit` = PR head, the declared `command`, and every input value a string.

  Exactly one `demo_capture` event is written, after the dispatch. The output starts `Demo capture: in progress (queued)`. No `pr create` appears. [AC-001, AC-010, AC-019] (depends on T002)
- [X] T008 [US1] Test the captured line (Q2) in `tests/test_demo.py`. A runs list with the matching `display_title` `Ballast demo <request>`, `completed/success`, `head_sha` = commit and an unexpired artifact `ballast-demo-<request>` renders `captured at <head12>` · `[video](https://github.com/o/r/actions/runs/R/artifacts/A)` · environment · `reproduce: \`<command>\``. [AC-002, AC-007] (depends on T002)
- [X] T009 [US1] Test stale captures (Q3) in `tests/test_demo.py`. With the event commit ≠ PR head, a capture that resolved to `captured`, `failed` or `missing` renders `stale (<outcome>[ (<reason>)] at <commit12>; head is <head12>)` with a job link and never a `[video]` link. [AC-003] (depends on T002)
- [X] T010 [US1] Test in-progress captures and pagination (Q4, Q23) in `tests/test_demo.py`:
  - a run `in_progress` renders `in progress (running)` with a job link;
  - no run within 24 h renders `in progress (queued)`, and no run after 24 h renders `failed (run-not-found)`;
  - a second collect with the run completed shows the final outcome;
  - a match on page 3 after two full pages stops at page 3;
  - five full pages with no match give `failed (run-list-truncated)` even within 24 h, with no sixth read;
  - the `created=>=` filter is the older UTC date of two scenarios' newest events;
  - every list argv has `branch=<feature branch>` and `event=workflow_dispatch` and no `--paginate`.

  [AC-004] (depends on T002)
- [X] T011 [P] [US1] Test demo isolation (Q5) in `tests/test_packet.py`. For each demo state, the criteria lines, counts, header and digest of everything outside `### Demo captures` are identical with and without demo data. The rendered section passes #19's marker and `HUMAN_APPROVAL` guard, and contains no `approved` or approval wording. [AC-005] (depends on T001)
- [X] T012 [US1] Test a repeated request (Q6) in `tests/test_demo.py`. Two requests for the same commit and scenario show the newer request's run. The PR body edited through `gh pr edit` has exactly one packet marker pair and one `### Demo captures` heading. No `pr create` call is made. [AC-006, SC-003] (depends on T002)
- [X] T013 [US1] Test the bounded wait (Q20) in `tests/test_demo.py`. A run that completes on the third poll stops polling there. A run that never completes stops at 120 s of the injected clock with ≤ 12 page-1 list reads, followed by exactly one checkpoint refresh. `--no-wait` makes no list read before the refresh. [FR-009] (depends on T002)
- [X] T014 [US1] Test hostile project text (Q18) in `tests/test_demo.py`. A scenario environment and command containing packet section markers, `[x](javascript:…)`, `@user`, `#12`, backticks and `$…$` are rendered inert through `packet.inert`. The output keeps exactly one packet marker pair and has no link other than Ballast's run and artifact links. [FR-018, edge case] (depends on T002)

### Implementation for User Story 1

- [X] T015 [P] [US1] Implement `collect(step, head, events)` and `resolve` in `tools/spec_workflow/demo.py` per [research R6](research.md#r6-outcome-resolution-at-a-checkpoint) and [capture-workflow.md](contracts/capture-workflow.md#github-reads-that-interpret-the-run-adr-0012).
  - Take the newest `demo_capture` event per scenario.
  - Read runs-list pages of 100 for `branch=<feature branch>`, `event=workflow_dispatch` and `created=>=<oldest newest-event date>`, until a short page, at most 5 pages, through the T006 seam.
  - Match `display_title` exactly. Several matches give `run-ambiguous`.
  - Apply R6 in order: queued, `run-not-found` after 24 h, `run-list-truncated`, `commit-mismatch` when `head_sha` ≠ commit, `running`, and for `success` the artifacts read (`artifacts?name=ballast-demo-<request>`) giving `captured` with `artifact_id`.
  - Set `stale` when commit ≠ head, and `command_changed` when the digests differ.
  - Let GitHub read failures propagate as the classified cause.

  (depends on T003, T005, T006)
- [X] T016 [US1] Implement `lines(section, level)` and `format_line` in `tools/spec_workflow/demo.py` per [packet-demo-section.md](contracts/packet-demo-section.md).
  - Write the fixed intro sentence, then one line per declared scenario in declaration order.
  - Show `[video]` only for a non-stale `captured`, and `[job]` otherwise when a run is known.
  - Put `stale` first.
  - Pass scenario, environment and command through `packet.inert`, and show the command in a code span with backticks removed.
  - Add `(declared command changed since this capture)` when `command_changed` is set.
  - Render `not yet requested` for a scenario with no event, and `<name>: no longer declared` with no link for an event whose scenario was removed.
  - Build links only from the validated repository and integer IDs.
  - At level ≥ 3, render the count line `Demo captures: N scenarios, K captured at head.`

  (depends on T015)
- [X] T017 [P] [US1] Integrate the demo section into `tools/spec_workflow/packet.py`. Add `Sources.demo`, and have `_Step.collect` call `demo.collect` with the run's events and the PR head. A GitHub read failure there makes the packet step `failed-retryable` with the classified cause, as a check-run read failure does. `render` places `### Demo captures` after `### UI states` and before `### Sources`, using `demo.lines`. Criteria, counts and evidence states never read `Sources.demo` (FR-014) (depends on T016)
- [X] T018 [P] [US1] Implement `request(root, run_id, scenario, wait=True)` and `event_data` in `tools/spec_workflow/demo.py` per [demo-command.md](contracts/demo-command.md#sequence).
  - Apply refusals 3–10 of [research R9](research.md#r9-refusals-before-dispatch) in order: `not-configured`, `config-invalid`, `unknown-scenario`, `no-draft-pr`, `pr-not-open`, `workflow-not-installed` (404), `workflow-disabled` and `workflow-differs` (head blob absent or ≠ default-branch blob).
  - Run `draft_pr.checkpoint(create=False)` and continue only on `reused`.
  - Do the PR, repository and workflow reads and the two contents blob reads.
  - Dispatch with a `secrets.token_hex(8)` request ID and the JSON body on stdin through `--input -`. The `ref` is the pinned feature branch and never the default branch.
  - Append `demo_capture` only after the dispatch succeeds.
  - Poll page 1 every 10 s for at most 120 s with the injected clock and sleep, unless `wait=False`.
  - Run `draft_pr.checkpoint(create=False)` again.
  - Return a `DemoOutcome` whose reasons, remedies and links are fixed strings or validated IDs only.

  (depends on T016)
- [X] T019 [US1] Add the `demo` subcommand to `tools/spec_workflow/run.py`:
  - `ballast run demo RUN_ID SCENARIO [--no-wait]` in `COMMANDS`;
  - `_demo_command(options)` under `_invocation_lock`, with the launcher's `untrusted` refusal (tamper or `in-progress` marker) and `lock-held` refusal before any `gh` call;
  - it prints the `Demo capture:`, `Draft PR:` and `Acceptance packet:` lines;
  - it exits 1 for `refused`/`failed-retryable` and 0 for any dispatched outcome;
  - update the usage text and module docstring.

  (depends on T017, T018)

**Checkpoint**: User Story 1 is functional and testable on its own (T007–T014 pass).

---

## Phase 4: User Story 2 - Reproduce the journey locally without private data (Priority: P1)

**Goal**: A secret-free, read-only capture workflow template; the reproduce command shown verbatim; the documentation of local reproduction and seeded data; the feature-branch execution scope of DEC-0001.

**Independent Test**: The static test of the template passes, the packet line names the declared command exactly, and the policy text names the reproduce command and the data warning.

### Acceptance tests for User Story 2

- [X] T020 [US2] Add a static test of the template (Q7) with pyyaml in `tests/test_demo.py`. It asserts:
  - triggers: `workflow_dispatch` is the only trigger, with the seven required string inputs, and `run-name` is `Ballast demo ${{ inputs.request }}`;
  - permissions and secrets: `permissions == {"contents": "read"}`, there are no job-level permissions, and no `secrets.` or `environment:` appears;
  - job shape: there is exactly one job, and its `timeout-minutes` is the integer `65`;
  - shell steps: no `${{` appears inside any `run:`; the command step runs `timeout --kill-after=30s "${TIMEOUT}m"` with `TIMEOUT` from `inputs.timeout_minutes` via `env:`; the validate step compares `GITHUB_SHA` with the commit input;
  - actions: the only `uses:` are `actions/checkout` and `actions/upload-artifact`, pinned to 40-hex SHAs, with no `actions/cache` and no `cache:` input; checkout has `ref: ${{ inputs.commit }}`, `persist-credentials: false` and `fetch-depth: 1`;
  - step names: the fixed names appear in the contract's order.

  [AC-008, AC-017, SC-005] (depends on T002)
- [X] T021 [US2] Test the workflow identity check (Q21) in `tests/test_demo.py`. A head-commit blob `sha` that differs from the default branch's, or a 404 on the head contents read, gives `refused (workflow-differs)` with the sync remedy and exit 1. There is no dispatch call and no ledger event. [AC-010] (depends on T002)
- [X] T022 [US2] Test `commit-mismatch` (Q22) in `tests/test_demo.py`. A matched `completed/success` run whose `head_sha` ≠ the event's commit, with an unexpired artifact, renders `failed (commit-mismatch)` with a job link. The artifacts endpoint is never read, and no `[video]` link appears. [AC-010, SC-002] (depends on T002)
- [X] T023 [US2] Test the reproduce command in `tests/test_demo.py`. Every non-`not configured` line names the scenario's command exactly as declared, inert. When the event's `command_digest` differs from the current command's, the line adds `(declared command changed since this capture)`. [AC-007] (depends on T002)
- [X] T024 [P] [US2] Add a policy-text check (Q8) to `tests/test_governance.py`, beside its existing policy checks. `templates/policies/spec-kit-workflow.md` must name:
  - `ballast run demo`;
  - every packet demo state (`captured`, `in progress`, `failed`, `missing`, `stale`, `not yet requested`, `not configured`, `configuration invalid`);
  - running the scenario's command at the captured commit to reproduce it;
  - seeded nonsensitive data and fake accounts;
  - that the video is readable by anyone with repository read access;
  - that a command exiting 124 or 137 itself is reported `timed-out`;
  - that a feature branch must carry the default branch's `ballast-demo.yml`.

  [AC-007, AC-009]

### Implementation for User Story 2

- [X] T025 [P] [US2] Create the copy-once template `templates/github/workflows/ballast-demo.yml` per [capture-workflow.md](contracts/capture-workflow.md).
  - Trigger, permissions and job: `workflow_dispatch` with the seven required string inputs; `run-name: Ballast demo ${{ inputs.request }}`; workflow-level `permissions: contents: read`; one `ubuntu-latest` job with `timeout-minutes: 65`.
  - Steps, in this order:
    1. `Validate demo request`, which checks every input pattern and `GITHUB_SHA == commit`, with inputs through `env:` only;
    2. checkout at `inputs.commit` with `persist-credentials: false` and `fetch-depth: 1`, then a `HEAD` check;
    3. `Run demo command` with `set +e` and `timeout --kill-after=30s "${TIMEOUT}m" bash -c "$DEMO_COMMAND"`, writing `exit=` to `$GITHUB_OUTPUT`;
    4. `Demo command timed out` (exit 124/137);
    5. `Demo command failed`;
    6. `Demo video missing`, with a `realpath` check against `$GITHUB_WORKSPACE`;
    7. `actions/upload-artifact` with `name: ballast-demo-${{ inputs.request }}`, `retention-days` from the input, `if-no-files-found: error` and `compression-level: 0`.
  - Pin `actions/checkout` and `actions/upload-artifact` to the full commit SHA of their current release tag, with a `# vX.Y.Z` comment.
  - Do not add secrets, `environment:` or a cache step.
- [X] T026 [P] [US2] Add a "Demo capture" subsection after "Acceptance packet" in `templates/policies/spec-kit-workflow.md`. It covers:
  - setup: the `[demo]` table and its limits, and copying the template to `.github/workflows/` on the default branch;
  - the feature-branch requirement: a feature branch must carry the same file, because the capture runs on the feature branch's ref so PR code cannot write default-branch caches, and a differing copy is refused;
  - requesting: `ballast run demo RUN_ID SCENARIO [--no-wait]`;
  - reading results: each packet state and reason, including that a command that itself exits 124 or 137 is reported `timed-out`;
  - reproduction and data: local reproduction by running the scenario's command at the captured commit without credentials, the seeded nonsensitive data and fake accounts requirement, and that the artifact is readable by anyone with repository read access;
  - the meaning of a video: it is never evidence or approval.

**Checkpoint**: User Stories 1 and 2 pass (T007–T014, T020–T024).

---

## Phase 5: User Story 3 - A failed capture shows as missing evidence (Priority: P1)

**Goal**: Failed, timed-out, video-less and expired captures read as `failed` or `missing` with a fixed reason, published in place, and never with a video link.

**Independent Test**: Scripted failed, timed-out and video-less runs each render `failed` or `missing` with a reason and no video link. The PR is edited in place and never created.

### Acceptance tests for User Story 3

- [X] T027 [US3] Test failure causes (Q9) in `tests/test_demo.py`. The first failed step `Demo command failed`, `Demo command timed out`, conclusion `cancelled`, conclusion `timed_out` and an unknown failed step render `failed (command-failed|timed-out|cancelled|timed-out|job-failed)` respectively, with a job link and no `[video]` link. A `Validate demo request` failure renders `failed (request-invalid)`. No log or artifact download argv appears. [AC-011] (depends on T002)
- [X] T028 [US3] Test missing videos (Q10) in `tests/test_demo.py`. Failed step `Demo video missing`, success with an artifact `expired: true`, and success with no artifact render `missing (no-video|expired|artifact-absent)` with no `[video]` link. [AC-012, SC-002] (depends on T002)
- [X] T029 [US3] Test in-place publication of failures (Q11) in `tests/test_demo.py`. For a failed and a missing capture, the packet is published with `updated` through `gh pr edit`, and the recorded argv contains no `pr create`. [AC-013] (depends on T002)
- [X] T030 [US3] Test PR-state refusals (Q12) in `tests/test_demo.py`. A checkpoint `skipped no-draft-pr` gives `refused (no-draft-pr)`. A `blocked-*` outcome, a closed PR and a merged PR give `refused (pr-not-open)`. Each exits 1, with no dispatch call, no `demo_capture` event and no `pr create`. [AC-014] (depends on T002)

### Implementation for User Story 3

- [X] T031 [P] [US3] Extend `resolve` in `tools/spec_workflow/demo.py` with the failure mapping of [research R5](research.md#r5-failure-causes-without-downloading-logs):
  - for a completed, non-successful run only, read `actions/runs/<id>/jobs?per_page=100` and map the first failed step's `name` to `request-invalid`, `timed-out`, `command-failed` or `no-video` (as `missing`);
  - otherwise use the conclusion `cancelled`/`timed_out` or `job-failed`;
  - for `success`, map an expired or absent artifact to `missing (expired|artifact-absent)`;
  - set `artifact_id` only for `captured`.

  (depends on T018)

**Checkpoint**: User Stories 1–3 pass.

---

## Phase 6: User Story 4 - Declare the demo contract once and get clear refusals (Priority: P2)

**Goal**: An absent or invalid contract, an unknown scenario, a forge failure and an agent attempt each give a fixed refusal or packet state, and the rest of the packet still publishes.

**Independent Test**: With no contract, an unknown key, an escaping video path and an undeclared scenario, each request refuses with a fixed reason and the packet still publishes with a single demo state line.

### Acceptance tests for User Story 4

- [X] T032 [US4] Test the absent contract (Q13) in `tests/test_demo.py`. With no `[demo]` table, the request gives `refused (not-configured)` with the remedy to declare `[demo]` and run `ballast trust`, and makes no `gh` dispatch. The packet shows `Demo captures: not configured.`, and the rest publishes. [AC-015] (depends on T002)
- [X] T033 [US4] Test the invalid contract (Q14) in `tests/test_demo.py`. An unknown key, `video = "../x"`, `video = "/etc/x"`, duplicate names and each limit at its bound and one past it (`retention_days` 1/90/0/91, `timeout_minutes` 1/60/0/61, 20/21 scenarios, a 64/65-character name, a 1000/1001-character command, an 80/81-character environment) give `refused (config-invalid)` with the fixed reason, or are accepted at the bound. An undeclared scenario gives `refused (unknown-scenario)` naming the declared scenarios. There is no dispatch in any case, and the packet shows `configuration invalid (<reason>)` while the rest publishes. [AC-016] (depends on T002)
- [X] T034 [US4] Test defaults and overrides (Q15) in `tests/test_demo.py`. A contract without `retention_days`/`timeout_minutes` dispatches inputs `"14"`/`"15"`, and one with 30/45 dispatches `"30"`/`"45"`. [AC-017] (depends on T002)
- [X] T035 [US4] Test forge failures and token leakage (Q16) in `tests/test_demo.py`. The cases are a `gh` timeout, exit 4, HTTP 401, 403, 500 on any read or the dispatch, and 404 on the workflow read; the fake writes a `ghp_…` token to stderr in each. Each gives `failed-retryable (github-unreachable|gh-unauthenticated|gh-forbidden|github-error)`, and the `gh-forbidden` remedy names Actions write access. The 404 gives `refused (workflow-not-installed)`, and a disabled workflow gives `refused (workflow-disabled)`. No `demo_capture` event is written, and `packet.TOKEN` matches nothing in stdout, stderr, the ledger or the packet. [AC-018, SC-006] (depends on T002)
- [X] T036 [P] [US4] Test `run demo` authority (Q17) in `tests/test_spec_workflow.py`. With the tamper marker, with an agent step's `in-progress` marker, and with the run's invocation lock held, `ballast run demo RUN_ID SCENARIO` gives `refused (untrusted|lock-held)` with exit 1 and makes no `gh` call. [AC-019]
- [X] T037 [US4] Test the remaining packet states (Q19) in `tests/test_demo.py`. An event for a removed scenario renders `<name>: no longer declared` with no link. A declared scenario with no event renders `not yet requested`, distinct from `not configured`. Two runs matching one request render `failed (run-ambiguous)`. [FR-010, edge cases] (depends on T002)

### Implementation for User Story 4

- [X] T038 [US4] Complete the refusal and failure paths in `tools/spec_workflow/demo.py`.
  - `collect` returns a `DemoSection` in the `not configured` or `configuration invalid (<reason>)` state, without any GitHub read, and `lines` renders each as its single line.
  - `request` maps `gh` failures through `draft_pr._classify` to `failed-retryable (<cause>)` with #17's remedies, with the `gh-forbidden` remedy naming Actions write access.
  - `gh` stdout and stderr are parsed only, never printed, stored or rendered.
  - Every refusal and failure leaves the ledger without a `demo_capture` event.

  (depends on T031)

**Checkpoint**: All user stories pass.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: The architecture decision and the documentation outside the policy

- [X] T039 [P] Write `docs/adr/0012-demo-capture-dispatch.md` (ADR-0012, agent-provisional until merge), extending ADR-0003 and ADR-0006. It records:
  - the reads and the one dispatch write of [research R12](research.md#r12-new-github-calls-adr-0012);
  - the execution scope (the feature-branch ref and never the default branch, the blob identity check before dispatch, `head_sha` = requested commit before linking, and the bound on the race), per [R15](research.md#r15-execution-scope-of-the-capture-run-plan-review-f-001) and DEC-0001;
  - that the command comes only from trusted `ballast.toml`;
  - the job's constraints: no secrets, `contents: read`, no cache and the fixed `timeout-minutes` backstop;
  - that Ballast does no log or artifact download and no new local execution.
- [X] T040 [P] Name the demo capture workflow (`templates/github/workflows/ballast-demo.yml`) in the copy-once template list of `README.md`
- [X] T041 [P] Update §91 of `specs/TECHNICAL-SPEC.md`: on-demand demo capture is in 1.0, and automatic capture is later

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: T001 has no dependencies. T002 needs T001.
- **Foundational (Phase 2)**: needs T001 (T003 needs nothing). It blocks the user-story implementation tasks.
- **User stories (Phases 3–6)**: their test tasks need only the harness (T002), or nothing for T024 and T036, so they are written first and fail. Their implementation tasks change `demo.py` in sequence T005 → T015 → T016 → T018 → T031 → T038, because they share the file.
- **Polish (Phase 7)**: independent documents, with no task dependency.

### User Story Dependencies

- **US1 (P1)**: needs Foundational only. It delivers the request, resolution, rendering, packet integration and the `run demo` subcommand that every other story's tests exercise.
- **US2 (P1)**: the template (T025) and the policy (T026) are independent of US1. Its tests T021–T023 exercise the identity check and `commit-mismatch`, which are implemented in US1's T015/T018.
- **US3 (P1)**: T031 extends US1's `resolve`. The PR-state refusals tested by T030 are implemented in T018.
- **US4 (P2)**: T038 completes the refusal paths after T031. The contract parser it relies on is foundational (T005), and the `run.py` authority refusals tested by T036 are implemented in T019.

### Within Each User Story

- Tests are written first and must fail before their implementation.
- Parser and seam → resolve → render → packet integration and request → `run.py` subcommand.
- `tests/test_demo.py` tasks in the same wave are applied one after another in ID order, because they share the file.

## Execution Wave DAG

Tasks in a wave can run together once the previous waves are complete. Tasks marked [P] touch a file no other task in their wave touches. Unmarked tasks in a wave share `tests/test_demo.py` and run in ID order.

| Wave | Tasks | Waits for |
| --- | --- | --- |
| 1 | T001, T003, T024, T025, T026, T036, T039, T040, T041 | — |
| 2 | T002 (T001), T004 (T003), T005 (T001), T006 (T001), T011 (T001) | wave 1 |
| 3 | T015 (T003, T005, T006); `tests/test_demo.py` in order: T007, T008, T009, T010, T012, T013, T014, T020, T021, T022, T023, T027, T028, T029, T030, T032, T033, T034, T035, T037 (all T002) | wave 2 |
| 4 | T016 (T015) | wave 3 |
| 5 | T017 (T016), T018 (T016) | wave 4 |
| 6 | T019 (T017, T018), T031 (T018) | wave 5 |
| 7 | T038 (T031) | wave 6 |

```text
T001 ─┬─ T002 ─── [test_demo.py tests T007…T037]
      ├─ T005 ─┐
      ├─ T006 ─┼─ T015 ─ T016 ─┬─ T017 ─┐
      └─ T011  │               └─ T018 ─┼─ T019
T003 ─┬────────┘                        └─ T031 ─ T038
      └─ T004
T024, T025, T026, T036, T039, T040, T041 (independent)
```

## Acceptance Criteria Coverage

| AC | Evidence task(s) | Quickstart |
| --- | --- | --- |
| AC-001 | T007 | Q1 |
| AC-002 | T008 | Q2 |
| AC-003 | T009 | Q3 |
| AC-004 | T010 | Q4, Q23 |
| AC-005 | T011 | Q5 |
| AC-006 | T012, T004 | Q6 |
| AC-007 | T008, T023, T024 | Q2, Q8 |
| AC-008 | T020 | Q7 |
| AC-009 | T024 | Q8 |
| AC-010 | T007, T021, T022 | Q1, Q21, Q22 |
| AC-011 | T027 | Q9 |
| AC-012 | T028 | Q10 |
| AC-013 | T029 | Q11 |
| AC-014 | T030 | Q12 |
| AC-015 | T032 | Q13 |
| AC-016 | T033 | Q14 |
| AC-017 | T034, T020 | Q15, Q7 |
| AC-018 | T035 | Q16 |
| AC-019 | T036, T007 | Q17, Q1 |

FR-009: T013. FR-010 and the edge cases: T037. FR-018: T014. SC-001 and SC-004 are post-merge operator evidence (pilot), recorded as open in the PR.

---

## Parallel Example: Wave 1

```bash
Task: "Create tools/spec_workflow/demo.py skeleton (T001)"
Task: "Add demo_capture to tools/spec_workflow/ledger.py and ledger-schema.md (T003)"
Task: "Create templates/github/workflows/ballast-demo.yml (T025)"
Task: "Add the Demo capture subsection to templates/policies/spec-kit-workflow.md (T026)"
Task: "Policy-text check in tests/test_governance.py (T024)"
Task: "run demo authority test in tests/test_spec_workflow.py (T036)"
Task: "Write docs/adr/0012-demo-capture-dispatch.md (T039)"
```

---

## Implementation Strategy

### MVP First (User Story 1)

1. Phases 1 and 2 (T001–T006).
2. Phase 3 (T007–T019). Request, resolve, render and the `run demo` subcommand.
3. **Validate**: T007–T014 pass. A capture is dispatched on the feature branch and shows on the same PR.

### Incremental Delivery

1. US1: capture and link (MVP).
2. US2: the template, the reproduce command and the documentation. Without the template no project can capture, so US2 ships with US1 in the same PR.
3. US3: failure causes and missing videos.
4. US4: refusal paths and forge failures.
5. Polish: ADR-0012, README and the technical spec.

All phases ship in one PR. The increments order the work and keep each story's tests green as it lands.

---

## Notes

- `demo.py` is edited by T005, T015, T016, T018, T031 and T038 strictly in that order.
- No task runs the project's command locally or downloads a browser, a recorder, logs or media (FR-016, D-05).
- The two action SHAs in T025 are looked up at implementation time from the actions' release tags. Their dependency evaluation is a workflow-owned review.
- The installed `docs/policies/spec-kit-workflow.md` refreshes from the template through `ballast setup`. It is not edited by hand.
