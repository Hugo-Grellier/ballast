---

description: "Task list for #19, source-linked acceptance packet on the Draft PR"
---

# Tasks: Source-linked acceptance packet on the Draft PR

**Input**: Design documents from `specs/19-acceptance-packet/` ([plan](plan.md), [spec](spec.md), [research](research.md), [data model](data-model.md), [contracts](contracts/), [quickstart](quickstart.md), [plan review](reviews/plan.md))

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Risk**: R1 (plan gate, research R18). **Mode**: Autonomous run `97858712`; every decision here is agent-provisional and merging is the only human approval.

**Acceptance evidence**: Every criterion AC-001 to AC-022 has a test task citing its ID. The test seams are the quickstart §1 scenarios: a real temporary Git repository, ledger events written with `ledger.append`, the scripted `FakeGitHub` `_command` fake from `tests/test_draft_pr.py`, and an injected clock. Only SC-002's "every link resolves on GitHub" and the live behavior of `gh pr edit` need a network, so they have a manual verification task (T052) with the reason.

**Organization**: Tasks are grouped by user story. US1, US2 and US3 are P1; US4 and US5 are P2.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel once its dependencies are done (different files, no dependency on an unfinished task)
- **[Story]**: The user story the task belongs to (US1 to US5)
- Test tasks cite the acceptance criteria they prove, e.g. `[AC-001]`.
- Many tasks edit `tools/spec_workflow/packet.py` or `tests/test_packet.py`. When tasks in the same wave edit the same file, apply them one at a time in ID order. Only tasks marked [P] are safe to run concurrently.

## Plan-review findings these tasks resolve

- **F-001** (manifest validation): T013 and T014 validate the manifest's **schema shape only**. A `spec_digest` that differs from the spec, an AC the spec lacks and an AC the manifest lacks are all **not** `manifest-malformed`. They give `stale`, the unknown-criteria line and `missing` (R4). T048 corrects the data-model wording.
- **F-002** (AC-010 / SC-003 wording): T048 clarifies both as edits *made by the packet*, matching R13.
- **F-003** (upgrade note): T047 extends the upgrade note to review and convergence snapshots.

## Analyze findings these tasks resolve

- **C1, C3** (evidence links, AC-002 and AC-009): [DEC-0001](decisions.md), agent-provisional. T019, T022, T025, T028 and T029 link each test's file at head and the head's check runs when present, and name only ledger-held evidence by run ID and event sequence.
- **C2** (OpenAPI read): unchanged. T036 keeps the contents-API read accepted at the plan gate (PD-0004, PD-0005); a local `git cat-file` read of the base would add a `base-not-local` failure, since Ballast never fetches (R10).
- **A1, I2, F3**: spec wording in T048. **I1, F2**: fixed in `research.md` R17 and R12. **F1**: T039 is no longer [P].
- **G1** (Autonomous runs show `not run` until the operator checks): kept deferred (R5); T045 documents it.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Test fixtures and the architecture record every later task relies on.

- [ ] T001 Create `tests/test_packet.py` with shared fixtures: a `_Repo` helper that builds a real temporary Git repository with a base commit and a head commit (feature artifacts under `specs/<feature>/`, implementation files, an optional OpenAPI JSON, an optional tracked file matched by `.gitignore`) and returns their object IDs; a helper that writes ledger events through `ledger.append` with `source` `operator-attested` or `runner`; a fixed-clock patch; and reuse of `FakeGitHub` from `tests/test_draft_pr.py` (import it, or move it to `tests/_github_fake.py` and import it from both files) to script `gh api` replies and record argv
- [ ] T002 [P] Write `docs/adr/0005-review-packet-reads.md` (status: proposed, agent-provisional in run `97858712`). It extends ADR-0003's fixed allowlist with the read calls in [checkpoint-integration.md](contracts/checkpoint-integration.md#commands-all-through-_command-the-17-environment-and-resolved-programs): `gh api` for PR, check-run and contents reads; `git` `cat-file`, `ls-tree`, `rev-parse` and `read-tree`/`rm --cached`/`write-tree` on a private index; and a second marked PR-body section written through the existing `gh pr edit --body-file -`. Record what it does not add: no new program, no fetch, push or commit, no write besides the PR body, and no agent authority. Copy the format of `docs/adr/0003-launcher-github-authority.md`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Ledger changes (R3, R6, R16), the `packet.py` skeleton with `inert()` and link builders, the collect core, and the checkpoint and `run.py` wiring. Every story needs them.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

### Ledger: criteria parser (R6 defect fix)

- [ ] T003 [P] In `tests/test_agent_run_ledger.py`, add tests for `ledger.spec_criteria`: it parses `- **AC-NNN**:` and `N. **AC-NNN**:` items in document order with title and 1-based line; it keeps only the first occurrence of a repeated ID; the title stops before `**When**` or at 120 characters; and a spec without IDs gives `[]`. Add a test that `ledger check` on a spec in the `1. **AC-NNN**:` form archives the manifest instead of failing with "approved spec has no AC IDs". Keep the existing `- **AC-` fixtures [R6]
- [ ] T004 Implement `spec_criteria(text) -> list[tuple[str, str, int]]` in `tools/spec_workflow/ledger.py` and make `_approved_spec_ids` (currently around line 992) use it (depends on T003)

### Ledger: commit fingerprint (R3)

- [ ] T005 In `tests/test_agent_run_ledger.py`, add tests showing that `commit_tree(root, HEAD)` equals `implementation_tree(root)` on a clean checkout that tracks a file matched by `.gitignore`, and differs once the checkout is dirty. Show that `commit_tree` leaves the worktree and the user's index unchanged and runs no hook or filter (a hook that would fail is present). Show that `ledger check` records `verification.commit` = `HEAD` on a clean checkout and omits it on a dirty one, and that `verification` events without `commit` stay valid [R3, ledger contract] (depends on T003)
- [ ] T006 In `tools/spec_workflow/ledger.py`: add the `oid` value type (`[0-9a-f]{40}` or `[0-9a-f]{64}`); add `commit_tree(root, commit, git=_git)` (private temporary `GIT_INDEX_FILE`, `read-tree <commit>`, `rm -r --cached -q --ignore-unmatch -- specs`, `write-tree`, SHA-256 of the tree ID); seed `implementation_tree`'s private index with `read-tree HEAD` when `HEAD` exists, before `add -A -- . :!specs` and the `specs` removal; add the optional `commit` (`oid`) to `verification`, set by `ledger check` only when `implementation_tree(root) == commit_tree(root, HEAD)` (depends on T004, T005)

### Ledger: `acceptance_packet` event (R16)

- [ ] T007 In `tests/test_agent_run_ledger.py`, add validation tests for the `acceptance_packet` kind. Accepted: every outcome with its required fields. Rejected: `published`/`updated`/`unchanged` missing any of `pr_number`, `head`, `base`, `feature_version`, `packet_digest` or the five counts; `pending`/`failed-retryable` without `reason`; a reason outside `PACKET_REASONS[outcome]`; a non-`runner` source; a non-`oid` `head`. Also test that `ledger.py record` does not offer the kind, and that `report --run` (JSON and text) shows the latest packet event with `observed_at`, or `{"available": false, "reason": "no packet recorded"}` [ledger contract] (depends on T005)
- [ ] T008 In `tools/spec_workflow/ledger.py`: add `acceptance_packet` to `FIELDS`, `ENUM_FIELDS` and `RUNNER_ONLY`; add `PACKET_REASONS` with the R17 codes (`no-pr`, `pr-blocked`, `head-not-local`, #17's `github-*`/`gh-*` codes, `body-changed`, `section-unmanaged`, `source-unreadable`, `manifest-malformed`, `ledger-invalid`, `too-large`, `internal-error`) and the per-outcome required fields; extend `report` and `_text_report` with the latest `acceptance_packet` (depends on T006, T007)
- [ ] T009 Document in `tools/spec_workflow/ledger-schema.md` the `oid` type, the `acceptance_packet` kind and its validation, `verification.commit`, `commit_tree`, the seeded `implementation_tree`, `spec_criteria`, and the fact that an older pinned Ballast rejects a stream that contains the new kind (depends on T008)

### Packet module core

- [ ] T010 [P] Create `tools/spec_workflow/packet.py` (stdlib only, runnable under `python3 -I -S`) with a module docstring and the frozen dataclasses from [data-model.md](data-model.md): `Sources`, `Criterion`, `TestEvidence`, `Manifest`, `ProvisionalDecision`, `HumanDecision`, `FeatureDecision`, `Finding`, `RunCheck`, `CheckRun`, `ReviewConfig`, `UiState`, `ApiComparison`, `UiResult`, `Packet`, `PacketOutcome`. Add the `EvidenceState` constants, the markers `<!-- ballast:acceptance-packet:begin -->`/`end -->`, `BODY_LIMIT = 65536`, `MARGIN = 1024`, and link builders `_blob(head, path)`, `_line(head, path, n)`, `_compare(base, head)` and `_run_link(id)`. The builders validate `oid`, `PATH_SEGMENT` and an integer ID and raise on anything else. Add a `publish(work, outcome)` stub that returns `failed-retryable/internal-error`, and `format_line(outcome)` per the checkpoint contract's output line
- [ ] T011 In `tests/test_packet.py`, add unit tests for `inert(text, limit)`: one line, whitespace collapsed, capped with `…`; `&<>` escaped, so both packet markers and `<!-- workflow-` markers never appear raw; `` \ ` * _ [ ] ( ) # | ! ~ `` backslash-escaped; `://` and `www.` broken so no autolink forms; `@word` broken; `ghp_…`, `gho_…`, `ghu_…`, `ghs_…`, `ghr_…`, `github_pat_…`, `Authorization: …` and `Bearer …` replaced with `[redacted]`. Add tests that the link builders reject non-hex commits, `..` segments and non-integer IDs [AC-020, AC-022, FR-013, FR-016] (depends on T001, T010)
- [ ] T012 Implement `inert()` in `tools/spec_workflow/packet.py` per research R9 (depends on T011)
- [ ] T013 In `tests/test_packet.py`, add collect-core tests on `_Repo` with `FakeGitHub`. `head` and `base` come from the `pulls/<n>` read, validated as `oid`. A head missing from the object store gives `pending/head-not-local`. `feature_version` is `rev-parse <head>:<feature>`. `files` come from `ls-tree -r -z`. File bytes over 1 MB give `source-unreadable` for `spec.md` and `not present (too large)` for any other artifact. `spec_version` is the SHA-256 of `spec.md` at head. `head_fingerprint` equals `ledger.commit_tree(root, head)`. **Manifest validation checks schema shape only (F-001)**: invalid JSON, a wrong `schema_version`, a non-list criterion entry or a test name that fails the pattern gives `manifest-malformed`, while a stale `spec_digest`, IDs missing from the spec and spec IDs missing from the manifest load normally. A corrupt ledger stream gives `ledger-invalid`. Assert that every Git command runs with `--` before paths and that none of them fetches, pushes or commits [AC-019, FR-002] (depends on T006, T011)
- [ ] T014 Implement the collect core in `tools/spec_workflow/packet.py`: PR read, head presence, feature version, file list, file reads with size caps, `spec_criteria`, shape-only `Manifest` loading with `digest` = SHA-256 of the bytes, `head_fingerprint` through `ledger.commit_tree(..., git=work.git)`, `ledger.read` with problems mapped to `ledger-invalid`, and the `generated_at` clock. All I/O goes through `work.git`/`work.gh` and `_command` (depends on T004, T006, T012, T013)

### Checkpoint and `run.py` wiring

- [ ] T015 In `tests/test_draft_pr.py`, add tests for the checkpoint wiring. `packet.publish` is called only after `created` or `reused`, and only after the `pull_request` event is recorded. #17 `pending`/`failed-retryable` gives packet `pending/no-pr`, and `blocked-*` (closed, merged, ambiguous, unlinked) gives `pending/pr-blocked`, both with no packet `gh` call. `skipped` attempts no packet and records no `acceptance_packet` event. A raising `publish` gives `failed-retryable/internal-error` with the exception type as detail. The #17 `Outcome` state, reason and remedy are unchanged in every case. Update the existing argv-sequence test to expect the packet calls [AC-019, FR-015, FR-001] (depends on T008, T010)
- [ ] T016 In `tools/spec_workflow/draft_pr.py`: import `packet` at module load; add `Outcome.packet: packet.PacketOutcome | None`; after `_record`, call `packet.publish` inside its own `try/except Exception`, then append the `acceptance_packet` event (outcome, reason, counts, oids, digest, never free text); let `packet` reach the resolved `git`/`gh` and the hardened environment through `_Checkpoint`; extend the module docstring (depends on T008, T010, T015)
- [ ] T017 In `tests/test_spec_workflow.py`, add tests that `run.py` prints `Acceptance packet: …` after `Draft PR: …`, and that a packet step that raises keeps `run.py`'s exit statuses 0, 1 and 130 and its step state [AC-019, FR-015, SC-005] (depends on T016)
- [ ] T018 In `tools/spec_workflow/run.py`, make `_checkpoint` print `packet.format_line(outcome.packet)` after the Draft PR line when it is set, inside the existing `except (Exception, KeyboardInterrupt)` guard and without assigning the exit status. Update the module docstring (depends on T017)

**Checkpoint**: Ledger, collect core and wiring are ready. `publish` is still a stub.

---

## Phase 3: User Story 1 - See each criterion's evidence, or its absence, in the PR (Priority: P1) 🎯 MVP

**Goal**: The packet lists every spec criterion with one evidence state, together with risk, mode, decisions, open findings and checks, and is published into the Draft PR.

**Independent Test**: For a spec with several criteria (some with passing evidence, one with a failing test, one unmapped, one with evidence from an older commit), reach a checkpoint. Each criterion appears once with the right state and a link.

### Acceptance tests for User Story 1

- [ ] T019 [US1] In `tests/test_packet.py`, add criteria tests driving `collect` and `render` with the quickstart rows. A spec with AC-001…AC-006 as `1. **AC-NNN**:` items gives six rows in spec order, each with its title and a `blob/<head>/<feature>/spec.md?plain=1#L<n>` link [AC-001]. All mapped tests passed at head's fingerprint, spec and manifest gives `verified`: each test is a `blob/<head>/tests/<module>.py` link resolved from its dotted name, followed by `ledger event <seq> of run <id>`, and the row links `commit/<head>/checks` when the fake check-runs read returns at least one run, or reads `no CI result at head` when it returns none; a mapped test whose module file is absent at head is named unlinked with `file not found at head` and the state is unchanged [AC-002, DEC-0001]. An unmapped AC gives `missing` with "no test named in acceptance-evidence.json", and no manifest gives `missing` with "no acceptance-evidence.json" [AC-003]. One test failed gives `failed` with both per-test results. Evidence only on an earlier commit gives `stale (commit <12>)`. Evidence for an earlier spec digest gives `stale (spec <12>)`. A mapped test with no events gives `not run` plus the `ballast ledger check` hint [AC-004]. A manifest whose `spec_digest` differs gives every mapped AC `stale` with that spec version. A dirty-checkout event (fingerprint ≠ head) is never `verified` [FR-003]. A manifest naming AC-031 adds the "Evidence for unknown criteria" line. A spec without IDs gives "No acceptance criteria found" with a spec link. A base that advanced while head did not keeps head-bound evidence `verified` and shows the new base [edge cases] (depends on T014)
- [ ] T020 [US1] In `tests/test_packet.py`, add decision and risk tests. Autonomous records (one superseded PD, one open medium finding, risk R1) give `Risk: R1 (run record)`, each current PD labeled `agent-provisional` with a `autonomous/record.md` line link, the superseded PD omitted, and the finding with severity and report link [AC-005, AC-006]. A human-gated run with ledger gate `approve` events, a `human_action` event and an intake `Risk:` line gives `human; observed by runner`, risk from the intake comment, `human-gated` mode and no `agent-provisional` label [AC-006]. `decisions.md` with one resolved and one unresolved `DEC-NNNN` gives `see record` lines. With no decisions, findings or checks, each section reads `None (0).` and the header counts read 0 [AC-005, FR-004]. The fixed "not an approval" sentence is present, and the rendered text matches `HUMAN_APPROVAL` nowhere outside inert data [AC-006, FR-005] (depends on T019)
- [ ] T021 [US1] In `tests/test_packet.py`, add checks-section tests. `checks.json` gives `run-checks (runner, before publication, not bound to the head commit)` lines, and its absence gives `run-checks: not run`. Paginated check runs at head are listed with Ballast-built `runs/<id>` links, with one `completed/success` and one `in progress`. An empty response gives `none reported`. A response `html_url` pointing elsewhere is never used. Ledger `verification` events without `ac_id` are listed with `skipped` and `unavailable` statuses [FR-004, AC-009] (depends on T020)

### Implementation for User Story 1

- [ ] T022 [US1] Implement criterion evaluation per research R4 and the data-model state diagram in `tools/spec_workflow/packet.py`: newest operator-attested `verification` event per `(ac_id, check_id)`, preferring events bound to `(head_fingerprint, spec_version, manifest_digest)`; `TestEvidence.belongs_to` (`commit`, else `spec`, else `manifest`, else `snapshot`, 12 hex characters); state order `failed`, `stale`, `not run`; `TestEvidence.file` resolved as the longest dotted prefix of the test name whose `.py` file exists at head (`git cat-file -e <head>:<path>`, with `--` before paths), else `None`; the unknown-criteria list (depends on T019)
- [ ] T023 [US1] Collect decisions, approvals, findings, risk and mode per research R7 in `tools/spec_workflow/packet.py`. Use `autonomy.read_run`, `read_decisions`, `current_decisions`, `superseded` and `read_human_decisions` only when `run.json` exists, the ledger `gate`, `human_action` and `finding` events, `DEC-NNNN` headings in `decisions.md` (unresolved = has a Proposal and no Resolution), and #17's intake `Risk:` scope. Report links go to the recorded report path, else `reviews/<review_id>.md` when present, else `reviews/`. Never take a label from prose (depends on T020, T022)
- [ ] T024 [US1] Collect checks per research R8 in `tools/spec_workflow/packet.py`: `gh api --paginate --slurp "repos/<o>/<r>/commits/<head>/check-runs?per_page=100"`, integer `id` validation, inert names, and `checks.json` run-check lines (depends on T021, T023)
- [ ] T025 [US1] Implement `render(sources, level=1)` in `tools/spec_workflow/packet.py` per [packet-format.md](contracts/packet-format.md): the header (feature version, spec `sha256:<12>`, base, head, diff link, run and mode, `Generated:`, risk, criteria counts, finding and decision counts), the derived-summary sentence, the criteria table with the hint line (a `verified` row links each test's file at head as `blob/<head>/<path>` from `TestEvidence.file`, names its `ledger event <seq> of run <id>`, and links `commit/<head>/checks` when `check_runs` is not empty or says `no CI result at head`; DEC-0001), decisions, open findings and checks. Every value from a source goes through `inert`. After rendering, assert exactly one begin and one end marker and no `HUMAN_APPROVAL` match outside inert data, raising otherwise (depends on T022, T023, T024)
- [ ] T026 [US1] Implement the first-pass `publish` in `tools/spec_workflow/packet.py`: guard on the #17 outcome; `collect`; `render`; on the first-read body, append the section with `draft_pr._after` when no marker exists, or replace the single marker pair; `gh pr edit <n> --repo <o>/<r> --body-file -` with the body on stdin; `PacketOutcome` `published` or `updated` with `pr_number`, oids, the masked digest and counts (depends on T016, T025)
- [ ] T027 [US1] In `tests/test_packet.py`, add an end-to-end test through `draft_pr.checkpoint` on `_Repo` with `FakeGitHub`, covering both a `created` and a `reused` PR. The packet appears in the body passed to `pr edit`, `Acceptance packet: published #N head <12>` is printed, and the `acceptance_packet` event validates with the expected counts [AC-001, AC-002, AC-003] (depends on T018, T026)

**Checkpoint**: The MVP works. A Draft PR shows every criterion and its evidence state.

---

## Phase 4: User Story 2 - Locate every canonical source from the packet (Priority: P1)

**Goal**: A sources section, plus a source link on every summary line, all pinned to the head commit.

**Independent Test**: Publish packets for a feature with every artifact and for one missing some. Every link is pinned to head, and every absent artifact reads `not present`.

### Acceptance tests for User Story 2

- [ ] T028 [US2] In `tests/test_packet.py`, add tests: with intent, spec, plan, tasks, decisions, the manifest, two `reviews/*.md` and `autonomous/record.md` present at head, the sources section has one `blob/<head SHA>/…` link each, plus `compare/<base>...<head>` [AC-007]. With `plan.md`, `decisions.md` and `reviews/` absent, each reads `not present` with no link, and the packet is still published [AC-008]. Parse the rendered packet: every criterion row, decision, finding and check line carries a Ballast-built link; a `ledger event <seq> of run <id>` reference appears only for a record held solely in the ledger (a `verification` event or a gate approval), never in place of a link to a record that has one (a spec line, `record.md`, `decisions.md`, a review report, a check run); a `verified` row has a test-file link for each test whose file exists at head, and every URL starts with `https://github.com/<o>/<r>/` and contains the head or base SHA, or a `runs/<id>` [AC-009, SC-002, DEC-0001] (depends on T027)

### Implementation for User Story 2

- [ ] T029 [US2] Render the sources section in `tools/spec_workflow/packet.py` from `Sources.files`: intent, spec, plan, tasks, decisions, acceptance evidence, each review report in sorted order, the run record and the diff, with `not present` for any that is absent. Make the ledger-only decision and check lines name the run ID and event sequence (depends on T028)

**Checkpoint**: Every summary line traces to its source.

---

## Phase 5: User Story 3 - The packet stays current and honest about which commits it describes (Priority: P1)

**Goal**: One packet per PR, updated in place, never edited when nothing changed, never touching other PR text.

**Independent Test**: Repeat checkpoints with no change, after a new commit, after a spec change, and after a human edit. One packet exists, it is unchanged when nothing changed, and the human's text is kept.

### Acceptance tests for User Story 3

- [ ] T030 [US3] In `tests/test_packet.py`, add these tests:
  - A second checkpoint with the same sources and a different clock makes no `pr edit` call and records `unchanged` with the same `packet_digest`. With a fixed clock, the whole checkpoint makes no edit call [AC-010, SC-003].
  - A new head SHA, a new base SHA, a changed spec or a new verification event each replace the section in place, leave one marker pair and record `updated` [AC-011].
  - The header shows the feature version, base, head and a `Generated:` UTC time [AC-012].
  - A body with human text before and after, the #17 section and the #27 summary changes only inside the packet span, byte for byte, and the argv has no `--title`, `--base`, label, reviewer, `--ready` or `--draft` [AC-013].
  - When a human deletes the markers, the packet is appended once at the end, everything else stays identical, and the outcome is `published`. The same holds on an adopted (`reused`) PR [AC-014].
  - Two begin markers, or an end before a begin, give `failed-retryable/section-unmanaged` with no edit [FR-008].
  - A body that changed between the first read and the re-read gives `failed-retryable/body-changed` with no edit [FR-008].

  (depends on T027)

### Implementation for User Story 3

- [ ] T031 [US3] Complete the body edit rule from [checkpoint-integration.md](contracts/checkpoint-integration.md#body-edit-rule) in `tools/spec_workflow/packet.py`: count markers (0 → append, 1 ordered pair → replace, otherwise `section-unmanaged`); compute the masked digest with the `Generated:` line removed and return `unchanged` with no call when it matches the current section; assert that every byte outside the span is unchanged; re-read `pulls/<n>` and refuse with `body-changed` on any difference; only then edit (depends on T026, T030)

**Checkpoint**: Republishing is idempotent and never touches content outside the packet.

---

## Phase 6: User Story 4 - API contract changes and UI states appear when the project provides them (Priority: P2)

**Goal**: An optional `[review]` table in `ballast.toml` drives a JSON OpenAPI comparison and UI-state links, and the packet stays useful without it.

**Independent Test**: Projects with neither configured, with a changed OpenAPI JSON, and with UI states (some with results, one without). Check the API and UI sections.

### Acceptance tests for User Story 4

- [ ] T032 [US4] In `tests/test_packet.py`, add `ReviewConfig` tests. With no `[review]` table, the packet has `API: not configured.` and `UI states: not configured.` and nothing else in those sections [AC-015]. An `openapi` path with `../x`, a UI state with `criteria = ["AC-1"]`, a UI state with both `path` and `check`, more than 50 UI states, a name over 80 characters and a criterion the spec does not define each give `configuration invalid (<fixed reason>)`, and the rest of the packet is published [R12] (depends on T027)
- [ ] T033 [US4] In `tests/test_packet.py`, add OpenAPI tests with `FakeGitHub` contents replies (base64 `content`) at base and head. One added operation, one removed, one with a changed response and one request field newly required are listed by method and path; the removal and the newly required field are flagged `potentially breaking` with their fixed causes; the review sentence is present [AC-016]. Also cover a removed parameter, a parameter newly required, a request body newly required, a removed request field resolved through a local `$ref`, and a `$ref` cycle that terminates. An unchanged document gives `no API change`, a 404 at base gives `added in this PR`, a 404 at head gives `removed in this PR`, YAML gives `could not compare (not JSON)`, a 502 gives `could not compare (github-error)`, a response with no inline content or more than 2,000 operations gives `could not compare (too large)`, and a document without `openapi`/`paths` gives `could not compare (not an OpenAPI document)`. The rest of the packet is published in every case, and no contents call is made when nothing is configured [AC-017, FR-010, FR-012] (depends on T032)
- [ ] T034 [US4] In `tests/test_packet.py`, add UI-state tests. A `path` present at head links to the blob at head. A `check` with a success conclusion gives `passed` with a run link. A `check` in progress gives `not run (in progress)` with a run link (the CI edge case, R8). A `path` absent at head gives `missing`. Each result appears beside its criterion's row and never changes the criterion's evidence state [AC-018] (depends on T033)

### Implementation for User Story 4

- [ ] T035 [US4] Parse `[review]` from the protected `ballast.toml` with `tomllib` in `tools/spec_workflow/packet.py` into `ReviewConfig`. Path rules: relative, `/`-separated segments matching `[A-Za-z0-9._-]{1,100}`, no `.` or `..`, at most 300 characters. Also validate `AC-NNN` criteria, 1–80 character names, 1–100 character check names, exactly one of `path`/`check`, and at most 50 states. Every failure gives a fixed reason (depends on T032)
- [ ] T036 [US4] Implement the OpenAPI read and comparison from research R10 in `tools/spec_workflow/packet.py`: a `gh api "repos/<o>/<r>/contents/<quoted path>?ref=<sha>"` read for base and head, JSON-only decoding, operations as `(METHOD, path)` over the eight methods with path-level parameters merged, canonical-JSON comparison, the breaking causes (local `$ref` resolved to depth 5, cycle-safe) and the operation limit. Map failures to the fixed `could not compare` reasons through `draft_pr._classify` (depends on T033, T035)
- [ ] T037 [US4] Implement UI-state results (R11: `git cat-file -e <head>:<path>` for `path`, the R8 response for `check`) and render the API and UI sections in `tools/spec_workflow/packet.py`. Keep at most 50 lines per list in the PR text and every line in the level-1 text (depends on T034, T036)

**Checkpoint**: API and UI sections appear when the project configures them, and the packet is unaffected when it does not.

---

## Phase 7: User Story 5 - A packet failure never blocks the work or leaks a secret (Priority: P2)

**Goal**: Every failure is visible, harmless and retried. Hostile text stays inert, oversize packets shrink, and no credential leaks.

**Independent Test**: Simulate an unreadable source, a malformed manifest, GitHub unavailable, an oversize body and hostile agent-written text. Check the outcome, the ledger and the PR text.

### Acceptance tests for User Story 5

- [ ] T038 [US5] In `tests/test_packet.py`, add failure tests through `draft_pr.checkpoint`. `spec.md` absent at head gives `source-unreadable`. Invalid manifest JSON gives `manifest-malformed`. A corrupt ledger stream gives `ledger-invalid`. A head missing locally gives `pending/head-not-local`. `gh` 401, 403 and unreachable on the check-runs read give `gh-unauthenticated`, `gh-forbidden` and `github-unreachable`. Each prints its R17 remedy, records the reason, leaves the existing packet section and the #17 outcome untouched, and a following checkpoint with the cause removed publishes [AC-019, FR-015] (depends on T027)
- [ ] T039 [US5] In `tests/test_packet.py`, add hostile-text tests. Spec titles, PD summaries, finding reasons, `DEC` headings and check and UI-state names contain both packet markers, `<!-- workflow-` markers, `[x](https://evil)`, a bare `https://evil`, `@org/team`, `` ` ``, `|`, "approved by the human" and "verified". The published body has exactly one packet marker pair and no link or autolink to `evil`, the table columns are intact, every state and label equals the clean-fixture result, and the body passes the `HUMAN_APPROVAL` guard outside inert data [AC-020, FR-013] (depends on T027)
- [ ] T040 [US5] In `tests/test_packet.py`, add size tests. A PR body with 60,000 characters of human text gives a shortened packet that keeps the header, risk, counts, every non-`verified` criterion, every open finding and every provisional decision, plus the `Shortened to fit…` note naming `speckit-runs/<run_id>/acceptance-packet.md`. The complete level-1 text is in `<git common dir>/speckit-runs/<run>/acceptance-packet.md` with mode 0600, and the archive holds no absolute path or host. Human text that leaves no room even at level 4 gives `failed-retryable/too-large` with the section unchanged [AC-021, FR-014] (depends on T027)
- [ ] T041 [US5] In `tests/test_packet.py`, add credential tests. Set `GH_TOKEN=ghp_…`, put `github_pat_…` and `Authorization: Bearer …` in a source, and have the fake return a token on `gh` stderr and in a raised exception's message. Assert no token appears in stdout, any ledger event, the archive file or the PR body, for a published outcome and for a `failed-retryable` one [AC-022, FR-016] (depends on T027)

### Implementation for User Story 5

- [ ] T042 [US5] Map every failure to the R17 outcome, reason and remedy in `tools/spec_workflow/packet.py`. Reuse `draft_pr._classify` for `gh` results. `detail` is the exception type only. `format_line` prints the remedy and never prints `gh` output, environment values or paths outside the repository (depends on T026, T038)
- [ ] T043 [US5] Implement the size budget and levels 2–4 from research R14 in `tools/spec_workflow/packet.py`: the budget is 65,536 minus the body outside the span minus 1,024; take the first level that fits; level 4 failing gives `too-large`. Add the R15 archive copy, written atomically with mode 0600 to `ledger.archive_dir(root, run_id) / "acceptance-packet.md"` after every successful build, whether or not the edit succeeds (depends on T031, T040)
- [ ] T044 [US5] Close every gap T039 and T041 expose in `tools/spec_workflow/packet.py`: route every source-derived value through `inert`, check the marker count on the final body before the edit, and redact `detail`. Do not weaken any assertion in those tests (depends on T039, T041, T042)

**Checkpoint**: Every FR-017 situation has a passing deterministic test.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, review-finding follow-ups, the feature's own evidence manifest, gates and reviews.

- [ ] T045 [P] Add an "Acceptance packet" subsection under "Draft PR" in `templates/policies/spec-kit-workflow.md` [FR-018]. Cover:
  - what the packet shows and its five evidence states;
  - recording per-criterion evidence with `ballast ledger check RUN_ID AC-NNN TEST`, and why Autonomous runs show `not run` until then (R5);
  - the `[review]` configuration: a JSON-only OpenAPI document, UI states, and invalid-configuration messages;
  - the outcomes and remedies from R17;
  - the archive copy;
  - that the packet is a derived summary, not an approval.

  Do not edit the installed `docs/policies/` copy, which `ballast setup` refreshes. (depends on T029, T037, T044)
- [ ] T046 [P] In `README.md`, add one sentence in the workflow section pointing to the new subsection (depends on T045)
- [ ] T047 [P] Extend the upgrade note for the seeded `implementation_tree` (F-003). Snapshots recorded before the upgrade read `stale` once, for per-criterion checks and for review and convergence events alike, so re-run `ballast ledger check` and the affected reviews or convergence. Put it in `specs/19-acceptance-packet/quickstart.md` §3, in the Compatibility section of `specs/19-acceptance-packet/contracts/ledger-acceptance-packet-event.md`, and in `tools/spec_workflow/ledger-schema.md` (depends on T009)
- [ ] T048 [P] Fix the wording in `specs/19-acceptance-packet/` without changing behavior. In `spec.md`, AC-010 and SC-003 refer to PR-description edits *made by the packet* (F-002, R13). In `data-model.md`, the Manifest section validates schema shape only, and a stale `spec_digest` or a differing AC set is not malformed (F-001). In `spec.md`, AC-021 keeps every open finding and provisional decision, matching FR-014 (analyze I2), and names the complete packet's path in the run archive instead of linking it, since the archive is local (R15, analyze A1); FR-009 records the commits *when known*, since `pending` and `failed-retryable` may have none (R16, analyze F3) (depends on T030)
- [ ] T049 Check the docstrings of `tools/spec_workflow/packet.py`, `draft_pr.py` and `run.py` against the final behavior. Check that `packet.py` imports only the standard library and sibling `spec_workflow` modules, and that `python3 -I -S tools/spec_workflow/run.py --help` still loads (depends on T044)
- [ ] T050 Write `specs/19-acceptance-packet/acceptance-evidence.json` (schema 1, `spec_digest` of the final `spec.md`), mapping AC-001…AC-022 to the test methods added in T011–T041 (fully qualified `tests.test_….Class.test_…`). Validate it by running `ballast ledger check` for one criterion on the clean checkout (depends on T029, T031, T037, T044, T048)
- [ ] T051 Run the fast gate and record the exact commands and results for the PR: `uvx ruff check && uvx ruff format --check` and `uv run --no-project --python 3.13 --with pyyaml python -m unittest tests/test_*.py`. Name the four tests CI skips and say whether the full local gate ran (depends on T045, T046, T047, T049, T050)
- [ ] T052 Manual verification, which needs a network and a disposable GitHub repository so has no offline seam: the operator runs [quickstart §2](quickstart.md#2-live-check-operator-disposable-repository) steps 1–7, including following every Sources link (SC-002) and confirming that the PR edit history shows no packet edit on the unchanged run (AC-010). Record the outcome in the PR, or record that it is pending for the operator (depends on T051)
- [ ] T053 Run the required reviews and record each under `specs/19-acceptance-packet/reviews/`: engineering, security (GitHub authority, inert rendering, token leakage), test, documentation (policy subsection, ADR-0005) and architecture (ADR-0005 extends ADR-0003). Then run Spec Kit converge and spec reconciliation. Put the PR-description follow-up proposal from plan §Review notes (`run-checks` records per-criterion evidence; R2) in the PR (depends on T051)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: none.
- **Foundational (Phase 2)**: T010 and T003 start at once. T011 and T013 need T001. Every story depends on T014 and T018.
- **US1 (Phase 3)**: depends on Foundational. It delivers the first real `publish` (T026), which US2–US5 build on.
- **US2, US3, US4, US5 (Phases 4–7)**: each needs only US1's end-to-end test (T027), so they can proceed in parallel. Within US5, T043 also needs US3's body edit rule (T031), because the size budget is computed from the body outside the span.
- **Polish (Phase 8)**: after the stories it documents or verifies.

### User Story Dependencies

```text
Foundational ──► US1 (MVP) ──┬──► US2
                             ├──► US3 ──► (T043 in US5)
                             ├──► US4
                             └──► US5
```

### Within Each User Story

Tests come first and must fail before their implementation task. Collect comes before render, and render before publish.

## Execution Wave DAG

Each wave starts when every task it depends on is done. Tasks in one wave that edit the same file run one at a time in ID order; [P] marks the ones that can run concurrently.

| Wave | Tasks | Unblocked by |
| --- | --- | --- |
| 1 | T001, T002, T003, T010 | — |
| 2 | T004, T005, T011 | T003; T001 + T010 |
| 3 | T006, T007, T012 | T004 + T005; T005; T011 |
| 4 | T008, T013 | T006 + T007; T006 + T011 |
| 5 | T009, T014, T015 | T008; T004 + T006 + T012 + T013; T008 + T010 |
| 6 | T016, T019, T047 | T015; T014; T009 |
| 7 | T017, T020, T022 | T016; T019; T019 |
| 8 | T018, T021, T023 | T017; T020; T020 + T022 |
| 9 | T024 | T021 + T023 |
| 10 | T025 | T022 + T023 + T024 |
| 11 | T026 | T016 + T025 |
| 12 | T027 | T018 + T026 |
| 13 | T028, T030, T032, T038, T039, T040, T041 | T027 |
| 14 | T029, T031, T033, T035, T042, T048 | T028; T026 + T030; T032; T032; T026 + T038; T030 |
| 15 | T034, T036, T043, T044 | T033; T033 + T035; T031 + T040; T039 + T041 + T042 |
| 16 | T037, T049 | T034 + T036; T044 |
| 17 | T045, T050 | T029 + T037 + T044; T029 + T031 + T037 + T044 + T048 |
| 18 | T046 | T045 |
| 19 | T051 | T045 + T046 + T047 + T049 + T050 |
| 20 | T052, T053 | T051 |

Critical path (20 waves): T003 → T005 → T006 → T013 → T014 → T019 → T020 → T021 → T024 → T025 → T026 → T027 → T032 → T033 → T036 → T037 → T045 → T046 → T051 → T053.

## Parallel Example: after T027 (wave 13)

```text
Task: "T028 [US2] sources and link tests in tests/test_packet.py"
Task: "T030 [US3] idempotency and body-edit tests in tests/test_packet.py"
Task: "T032 [US4] ReviewConfig tests in tests/test_packet.py"
Task: "T039 [US5] hostile-text tests in tests/test_packet.py"
```

They share one file, so each adds its own `TestCase` class. One agent should apply them in ID order, or several agents should each work on a separate copy and merge the classes.

## Implementation Strategy

### MVP first (US1)

1. Phases 1–2: ledger fixes (R6 makes `ledger check` usable on real specs), collect core and wiring. `publish` is still a stub.
2. Phase 3: criteria, decisions, findings, checks, render, and a first publish.
3. **Stop and validate**: run T027 and `tests/test_packet.py`. A real Draft PR checkpoint now shows the packet.

### Incremental delivery

1. US2 makes every line traceable (P1).
2. US3 makes republishing safe and idempotent (P1). Without it every checkpoint edits the PR, so it is part of the minimum releasable scope.
3. US4 adds the optional API and UI sections (P2).
4. US5 hardens failure, size and secrets (P2). The feature is not releasable until the inert-text and redaction tests (T039, T041) pass. This run's own checkpoints use the pinned Ballast in `.ballast/`, not this checkout, so intermediate states never publish a packet.
5. Phase 8: documentation, the feature's own evidence manifest, gates and reviews.

## Notes

- `[P]` marks tasks in a different file with no unfinished dependency. Most work is in `packet.py` and `test_packet.py`, so parallelism is mostly across files (ADR, ledger, documentation) and across waves.
- Never weaken a failing test to pass. If implementation evidence conflicts with the spec or the contracts, stop and record it in `specs/19-acceptance-packet/decisions.md`.
- Commit after each task or logical group, with Conventional Commit messages.
