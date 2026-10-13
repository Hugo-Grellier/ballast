---

description: "Task list for Declare UI states per feature"
---

# Tasks: Declare UI states per feature

**Input**: Design documents from `specs/142-feature-ui-states/`
**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/ui-states-file.md](contracts/ui-states-file.md), [contracts/packet-ui-section.md](contracts/packet-ui-section.md), [quickstart.md](quickstart.md)

**Risk**: R2, Autonomous run `864d9151`. Every decision in this file is agent-provisional; merging the PR is the only human approval.

**Acceptance evidence**: Every behavior criterion AC-001 to AC-016 maps to a `unittest` case in `tests/test_packet.py`; the documentation criteria AC-017 to AC-019 map to wording tests in `tests/test_governance.py`, following that file's existing `DemoPolicyTests` and `LocalFallbackDocumentTests` pattern. T020 writes `acceptance-evidence.json`. The mapping is a proposal; only `ballast ledger check` records evidence.

**Operator-only checks**: None. The packet is plain text, so every criterion has an automated test seam (`PacketCase`'s temporary Git repository and the scripted `gh` fake). No task is `[DEFERRED-TO-PR]`.

**Workflow-owned steps**: The full gate, quickstart runs, reviews, converge and spec reconciliation are not tasks. What they must check is in [quickstart.md](quickstart.md) and [plan.md](plan.md).

**Verification commands**: Each command matches an `[agents.permissions] extra_allow` rule in `ballast.toml`. Run one command per invocation:

- `uv run --no-project --python 3.13 --with pyyaml python -m unittest tests/test_packet.py`
- `uv run --no-project --python 3.13 --with pyyaml python -m unittest tests/test_governance.py`
- `uvx ruff check`
- `uvx ruff format --check`

**Plan review findings settled here** ([reviews/plan.md](reviews/plan.md)):

- F-001: T008 keeps `Step.blob` unchanged and accepts the conflation explicitly. A listed `ui-states.toml` whose text is `None` and which is not too large reads `ui-states.toml: not UTF-8 text`, also when `git cat-file` failed. The UI section is derived, never evidence, and a retry on the next checkpoint reads the file again. Agent data can therefore never fail the packet step. T008 states this in a one-line comment.
- F-002: T007 carries `openapi` and `api_error` over in `merge_ui_states`; T014 asserts that the API section is unchanged when a feature file is present.
- F-003: T001 reorders the fixed-reasons table in `contracts/ui-states-file.md` to the validation order: `ui_states is not a list of tables` before `more than 50 UI states` for each source.
- F-004: no edit to `docs/policies/`. This repository's installed copy follows the pinned release, not this PR.

**Organization**: `tools/spec_workflow/packet.py` holds all the behavior, so the shared validator, the two new functions, the collection change and the rendering are foundational or US1 tasks. US2, US3 and US4 are delivered by that code and add the tests that prove their guarantees.

## Format: `[ID] [P?] [Story?] Description [(depends on ...)]`

- **[P]**: Can run in parallel with other ready tasks once any listed dependencies are satisfied. Tasks that edit the same file are never marked `[P]`: `tools/spec_workflow/packet.py` and `tests/test_packet.py` take one writer at a time.
- **[Story?]**: The user story a task belongs to (US1 to US5).
- **(depends on ...)**: Explicit dependency on earlier task IDs.
- Test and verification tasks cite the acceptance criterion IDs they prove.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Align the contract with the validation order before any test asserts it.

- [X] T001 Reorder the "Fixed reasons" table in `specs/142-feature-ui-states/contracts/ui-states-file.md` so each source lists `ui_states is not a list of tables` before `more than 50 UI states`, matching the order `_ui_states` checks today (plan review F-003). Do not change any reason text.

No other setup: the tools are standard-library-only, and no dependency, directory or configuration is added.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The source-aware validator and the `agent` flag that every story needs.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T002 In `tools/spec_workflow/packet.py`, add `agent: bool = False` as the last field of the frozen dataclasses `UiState` and `UiResult`, make `_Step.ui_result` copy `state.agent` into the `UiResult` it returns, and update the docstrings of `UiState` (repository entries carry no criteria; `agent` marks entries from `ui-states.toml`) and `ReviewConfig` (holds the merged view after `collect`; reasons carry a source prefix). No behavior change yet. (depends on T001)
- [X] T003 In `tools/spec_workflow/packet.py`, make the validator source-aware (research R2, R3). Add the module constants `REPOSITORY = "ballast.toml"` and `FEATURE = "ui-states.toml"`. Change `_ui_states(value, spec_ids)` to `_ui_states(value, source, spec_ids=None)`:
  - Keep the rule order and rule texts. Prefix every returned reason with `f"{source}: "`, except `more than 50 UI states`, which stays unprefixed.
  - For `REPOSITORY`: before any other entry rule, an entry that has a `criteria` key, even `[]`, returns `ballast.toml: UI state criteria belong in the feature's ui-states.toml`. The allowed keys become `name`, `path`, `check`, and a valid entry gets `criteria=()`. Skip the criteria rules.
  - For `FEATURE`: keep today's allowed keys and criteria rules, always apply the undefined-criterion rule against `spec_ids` (an empty or `None` set means every criterion is undefined), and build each `UiState` with `agent=True`.
  - Change `review_config(root, spec_ids=None)` to `review_config(root)`, validating with `_ui_states(value, REPOSITORY)`. Update its one caller in `_Step.collect` to drop `spec_ids`. `review is not a table` stays unprefixed.

  (depends on T002)
- [X] T004 In `tests/test_packet.py` `ReviewConfigTests`, rewrite every UI states case that uses a repository entry with `criteria` as a criterion-less repository entry so that each repository rule stays covered (`ui_states` not a list of tables, more than 50 entries, unknown key, name outside 1-80 characters, neither or both of `path` and `check`, unsafe `path`, `check` outside 1-100 characters), and expect the `ballast.toml: ` prefix. The criteria rules (missing, empty, non-`AC-NNN`, undefined criterion) are not repository rules any more and are covered on the feature file by T005. Keep every non-UI case of the class unchanged. Run `uv run --no-project --python 3.13 --with pyyaml python -m unittest tests/test_packet.py`; only the `UiStateTests` cases that still declare criteria in `ballast.toml` may fail, and T011 moves them [AC-013] (depends on T003)

**Checkpoint**: Repository entries validate without criteria and every reason names its source.

---

## Phase 3: User Story 1 - A feature's UI states appear beside its own criteria (Priority: P1) 🎯 MVP

**Goal**: The packet reads `<feature>/ui-states.toml` at the head commit, checks it against that feature's spec only, and shows its entries beside their criteria with the agent-declared label.

**Independent Test**: In a fixture with two features, give the run's feature a `ui-states.toml` with a valid entry for `AC-003`: the link appears beside its `AC-003`. Make the entry cite a criterion its spec does not define: the UI section reads `configuration invalid (ui-states.toml: UI state names a criterion the spec does not define).` and every other section is published.

### Acceptance tests for User Story 1

> Write these first in a new `FeatureUiStateTests(PacketCase)` class in `tests/test_packet.py` and confirm they fail before T006-T010. Each test writes `<feature>/ui-states.toml` with the fixture's helpers, commits the head and publishes the packet, as quickstart scenarios 1-6 describe.

- [X] T005 [US1] In `tests/test_packet.py` `FeatureUiStateTests`, add:
  - `test_valid_entries_appear_beside_their_criteria` (quickstart 1): a `path` entry for AC-001 with the file committed, a `check` entry for AC-002 with a passed check run in the `gh` fake, and a `path` entry for AC-006 with the file absent. The section lists three labelled lines; the AC-001 row contains `UI <name> (agent-declared in ui-states.toml): [present at head](<blob>)`, AC-002 `[passed](<run>)`, AC-006 `missing` [AC-001].
  - `test_undefined_criterion_invalidates_only_the_ui_section` (quickstart 2): an entry citing `AC-099` gives `UI states: configuration invalid (ui-states.toml: UI state names a criterion the spec does not define).`; `### Criteria` and every other section are present and the packet result is `published` [AC-002].
  - `test_each_entry_rule_names_the_feature_file` (quickstart 3): one `subTest` per rule (unknown key, 81-character name, `criteria = ["AC-1"]`, missing `criteria`, `criteria = []`, both `path` and `check`, neither, `path = "../x"`, 101-character `check`, `ui_states = "x"`, an extra top-level key) asserting the matching `ui-states.toml:` reason from `contracts/ui-states-file.md` and a published packet [AC-003].
  - `test_unreadable_file_names_the_feature_file` (quickstart 4): invalid TOML, non-UTF-8 bytes, and a file larger than `packet.FILE_LIMIT` give `ui-states.toml: not valid TOML`, `ui-states.toml: not UTF-8 text` and `ui-states.toml: larger than 1 MiB`, with the rest of the packet published [AC-004].

  (depends on T004)
- [X] T006 [US1] In `tests/test_packet.py` `FeatureUiStateTests`, add:
  - `test_other_features_files_never_reach_this_packet` (quickstart 5): commit a second feature directory with its own `spec.md` and a `ui-states.toml` naming `AC-003` for a different screen and `AC-099`. The run's packet shows only its own `AC-003` screen beside its `AC-003` and contains no `configuration invalid` [AC-005, AC-009].
  - `test_file_is_read_at_the_head_commit` (quickstart 6): commit a valid file, then overwrite it in the working tree without committing; the packet shows the committed entry's name and not the working-tree one [AC-006].

  (depends on T005)

### Implementation for User Story 1

- [X] T007 [US1] In `tools/spec_workflow/packet.py`, add two pure functions (research R4, R5; data-model "Functions"):
  - `feature_ui_states(text, spec_ids, *, present, too_large) -> tuple[tuple[UiState, ...] | None, str | None]`. Absent file → `(None, None)`. Then, in order: too large → `ui-states.toml: larger than 1 MiB`; `text is None` → `ui-states.toml: not UTF-8 text`; `tomllib.TOMLDecodeError` → `ui-states.toml: not valid TOML`; any top-level key other than `ui_states` → `ui-states.toml: has a top-level key other than ui_states`; no `ui_states` key → `(None, None)`; otherwise `_ui_states(data["ui_states"], FEATURE, spec_ids)`.
  - `merge_ui_states(config: ReviewConfig, states, error) -> ReviewConfig`. Keep `config.openapi` and `config.api_error` unchanged (plan review F-002). If `config.ui_error` is set, return it unchanged (repository first). Otherwise, if `error` is set, return it as `ui_error` with `ui_states=None`. Otherwise, if both `config.ui_states` and `states` are `None`, return `ui_states=None` (`not configured`). Otherwise merge repository entries then feature entries in file order, treating a `None` side as empty; more than `UI_LIMIT` in total → `ui_error="more than 50 UI states"`.

  (depends on T003)
- [X] T008 [US1] In `tools/spec_workflow/packet.py` `_Step.collect`, after `spec.md` is read and its criteria are known, read the feature file with the existing `read("ui-states.toml")` helper (head commit only, so no new program or GitHub call, FR-014), call `feature_ui_states(text, "ui-states.toml" in files, "ui-states.toml" in too_large, spec_ids)`, and pass the result with `review_config(root)` to `merge_ui_states` before `ui_result` is resolved for each state. Store the merged `ReviewConfig` in `Sources.config`. Leave the `Criterion.ui` attachment as is, so it only replaces `ui` and repository entries, which have no criteria, never attach. Add a one-line comment that a `None` text which is not too large reads `not UTF-8 text` even after a `git cat-file` failure, because the UI section is derived and a later checkpoint reads it again (plan review F-001). (depends on T007)
- [X] T009 [US1] In `tools/spec_workflow/packet.py`, render the label (contracts/packet-ui-section.md, research R6). Add the constant `AGENT_LABEL = "agent-declared in ui-states.toml"`. In `_ui_lines`, render a feature entry as `- <inert name> (<AC IDs>, agent-declared in ui-states.toml): <result>` and a repository entry as `- <inert name>: <result>`, with no empty parentheses. In `_detail` (through `_ui_text` if that is where the criterion text is built), render ` · UI <inert name> (agent-declared in ui-states.toml): <result>` for an `agent` result. Names keep `inert(name, 80)`. The shortened count line at level 3 and above is unchanged. (depends on T002, T008)
- [X] T010 [US1] In `tests/test_packet.py` `UiStateTests`, move the four criterion-linked entries from `ballast.toml` to `<feature>/ui-states.toml` committed at the head, keep every expected result, and add the label to the expected section and criterion lines (quickstart 17). Run `uv run --no-project --python 3.13 --with pyyaml python -m unittest tests/test_packet.py` until it passes with T005 and T006 (depends on T005, T006, T008, T009)

**Checkpoint**: A feature's own UI states appear beside its criteria, and an invalid feature file fails only the UI section.

---

## Phase 4: User Story 2 - One feature never invalidates another feature's packet (Priority: P1)

**Goal**: A feature without `ui-states.toml` sees `not configured` or only the repository-wide screens, never an error from another feature.

**Independent Test**: Publish the packet of a feature without `ui-states.toml` while another feature has one and `ballast.toml` has no UI states: `UI states: not configured.`. Add a criterion-less repository entry: the section lists only that entry.

### Acceptance tests for User Story 2

- [X] T011 [US2] In `tests/test_packet.py`, add `FeatureIsolationTests(PacketCase)` with:
  - `test_no_file_and_no_table_is_not_configured` (quickstart 7): no feature file, no `[review]`, another feature directory with a `ui-states.toml` committed → `UI states: not configured.`. Subtests: a feature file with no `ui_states` key and no other key → `not configured`; `ui_states = []` → `None (0).` (research R5) [AC-007].
  - `test_repository_entries_alone_are_listed_without_criteria` (quickstart 8): no feature file, one criterion-less repository `check` entry → the section has `- <name>: <result>` without label or parentheses and no `### Criteria` row contains `UI ` [AC-008].
  - `test_repository_table_is_valid_for_every_feature` : a valid criterion-less repository table gives the same UI section for the run's feature and for a second feature fixture whose spec defines other criteria, and `packet.review_config(root)` takes no spec argument [AC-009].

  (depends on T010)

**Checkpoint**: No packet reads `configuration invalid` because of another feature (SC-001).

---

## Phase 5: User Story 3 - Repository-wide screens stay operator-owned and merge with the feature's (Priority: P2)

**Goal**: Criterion-less repository entries merge with the feature's; a repository entry with criteria gives the move reason.

**Independent Test**: One repository entry and one feature entry are both listed and only the feature entry appears beside its criterion; adding `criteria` to the repository entry gives the move reason.

### Acceptance tests for User Story 3

- [X] T012 [US3] In `tests/test_packet.py`, add `MergedUiStateTests(PacketCase)` with:
  - `test_repository_then_feature_entries` (quickstart 9): one repository entry and one feature entry → repository line first, then the labelled feature line; only the feature entry appears in a `### Criteria` row [AC-010].
  - `test_repository_criteria_give_the_move_reason` (quickstart 10): subtests with `criteria = ["AC-001"]` and `criteria = []` → `UI states: configuration invalid (ballast.toml: UI state criteria belong in the feature's ui-states.toml).` [AC-011].

  (depends on T011)
- [X] T013 [US3] In `tests/test_packet.py` `MergedUiStateTests`, add `test_more_than_fifty_in_total` (quickstart 11): subtests with 30 repository and 21 feature entries, 51 repository entries, and 51 feature entries → `UI states: configuration invalid (more than 50 UI states).` with the rest of the packet published; 30 and 20 lists all 50 [AC-012]. Add `test_repository_reason_wins_when_both_are_invalid` (quickstart 13, research R4): an invalid repository entry and an invalid feature file → the `ballast.toml:` reason [AC-013]. (depends on T012)
- [X] T014 [US3] In `tests/test_packet.py` `MergedUiStateTests`, add `test_api_section_unchanged_by_feature_file`: with `[review] openapi` configured as in `OpenApiTests`, the `### API` section text is identical with no feature file and with a valid one, and `merge_ui_states` keeps `openapi` and `api_error` (plan review F-002) [AC-010]. (depends on T013)

**Checkpoint**: Repository-wide screens appear on every packet, and stale criterion-linked configuration says where to move it.

---

## Phase 6: User Story 4 - Agent-declared entries are marked and inert (Priority: P2)

**Goal**: The reviewer can tell which links an agent declared, and nothing in the feature file changes a structure, label or evidence state.

**Independent Test**: A hostile feature entry name renders as plain text with the label, and every criterion's state is identical without the file.

### Acceptance tests for User Story 4

- [X] T015 [US4] In `tests/test_packet.py`, add `AgentDeclaredTests(PacketCase)` with `test_label_only_on_feature_entries` (quickstart 14): with one repository entry and one feature entry naming two criteria, `agent-declared in ui-states.toml` appears exactly once on the feature section line and once in each named criterion's row, and never on the repository line; assert `autonomy.HUMAN_APPROVAL.search(packet.AGENT_LABEL)` is `None` [AC-014]. (depends on T014)
- [X] T016 [US4] In `tests/test_packet.py` `AgentDeclaredTests`, add `test_hostile_name_is_inert` (quickstart 15): name a feature entry with the hostile text `HostileTextTests` uses (packet markers, a Markdown link, an `@` mention, a backtick, `|`, HTML). Assert no packet marker or raw link or mention appears, the section and criteria table keep their structure, and the row's state is unchanged [AC-015]. Add `test_evidence_states_ignore_the_file` (quickstart 16): publish the same fixture without the file, with a valid file and with an invalid file, and assert every criterion's state cell and reason are identical across the three [AC-016]. (depends on T015)

**Checkpoint**: Every UI link's origin is visible (SC-005) and no criterion state depends on the file (SC-004).

---

## Phase 7: User Story 5 - Adopters know where UI states live and why it changed (Priority: P3)

**Goal**: The policy template and a new ADR describe the feature file, the repository table and the change of authority.

**Independent Test**: The wording tests in `tests/test_governance.py` pass against the policy section and the ADRs.

### Implementation for User Story 5

- [X] T017 [P] [US5] Rewrite the UI states part of the acceptance packet section of `templates/policies/spec-kit-workflow.md` (around the current `[[review.ui_states]]` example). State that criterion-linked UI states live in `specs/<feature>/ui-states.toml`, with the entry schema and the TOML example from `contracts/ui-states-file.md`. State that `[[review.ui_states]]` in `ballast.toml` holds only criterion-less repository-wide entries, merged with the feature's and listed first, and that a `criteria` key there reads `configuration invalid` with the move reason. Cover the 50-entry total limit, that reasons name the failing source, and that feature entries carry the `agent-declared in ui-states.toml` label and never change a criterion's state. Explain how screenshots are kept current: a `path` screenshot is committed with the change that alters the screen and is linked at the head commit, a `check` result is read for the head commit, and a state without a head-commit result shows `missing`. Use neutral example names. Do not edit `docs/policies/` (plan review F-004).
- [X] T018 [P] [US5] Write `docs/adr/0019-feature-local-ui-states.md` in the format of `docs/adr/0018-runner-recorded-acceptance-checks.md`, status proposed and agent-provisional until merge. Record that criterion-linked UI states move from the protected `ballast.toml` to the agent-writable `specs/<feature>/ui-states.toml`, read at the head commit and checked against that feature's spec only. `[[review.ui_states]]` keeps only criterion-less operator-owned entries merged with the feature's. Feature entries are labelled agent-declared, inert, and never change a criterion's state. The ADR amends ADR-0006's statement that the packet's configuration lives in the protected `ballast.toml`, and the packet gains no new program, GitHub call, fetch or authority. Link Issue #142, the operator decisions 1b and 2b, and `specs/142-feature-ui-states/`.
- [X] T019 [US5] Add one italic amendment note to the configuration line of "What it does not add" in `docs/adr/0006-review-packet-reads.md`, pointing to ADR-0019, in the style ADR-0007 uses for ADR-0015. Leave its status and decision unchanged. (depends on T018)

### Acceptance tests for User Story 5

- [X] T020 [US5] In `tests/test_governance.py`, add `FeatureUiStatesDocumentTests(unittest.TestCase)` following `DemoPolicyTests`:
  - `test_policy_describes_where_ui_states_live`: the acceptance packet section of `templates/policies/spec-kit-workflow.md` contains `specs/<feature>/ui-states.toml`, `[[ui_states]]`, `criteria`, `[[review.ui_states]]` with criterion-less wording, `50`, `agent-declared in ui-states.toml`, and a statement that entries never change a criterion's state [AC-017].
  - `test_policy_explains_keeping_screenshots_current`: the same section states that a `path` screenshot is committed with the change and linked at the head commit, that a `check` is read for the head commit, and `missing` [AC-018].
  - `test_adr_0019_amends_adr_0006`: `docs/adr/0019-feature-local-ui-states.md` exists, names `ballast.toml`, `ui-states.toml` and ADR-0006, and states no new program, GitHub call, fetch or authority; `docs/adr/0006-review-packet-reads.md` links `0019-feature-local-ui-states.md` [AC-019].

  Run `uv run --no-project --python 3.13 --with pyyaml python -m unittest tests/test_governance.py` (depends on T017, T019)

**Checkpoint**: Adopters can declare UI states from the policy alone, and the authority change is recorded.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Evidence mapping and the fast checks the implementation must leave clean.

- [X] T021 Run `uvx ruff check` and `uvx ruff format --check` and fix any finding in `tools/spec_workflow/packet.py`, `tests/test_packet.py` and `tests/test_governance.py` without adding a `noqa` beyond the per-function ones `_ui_states` and `collect` already carry. Confirm no test outside `ReviewConfigTests` and `UiStateTests` changed its expectations (FR-018) with `git diff -- tests/test_packet.py`. (depends on T016, T020)
- [X] T022 Write `specs/142-feature-ui-states/acceptance-evidence.json` as `{"schema_version": 1, "spec_digest": "<sha256 of spec.md>", "criteria": {...}}`, computing the digest of the committed `spec.md` at implementation time. Map each criterion to the dotted test IDs that prove it: AC-001 to AC-006 to `tests.test_packet.FeatureUiStateTests.*` (T005, T006); AC-007 to AC-009 to `tests.test_packet.FeatureIsolationTests.*` (T011), with AC-009 also `test_other_features_files_never_reach_this_packet`; AC-010 to AC-013 to `tests.test_packet.MergedUiStateTests.*` (T012-T014) and the rewritten `tests.test_packet.ReviewConfigTests` cases for AC-013 (T004); AC-014 to AC-016 to `tests.test_packet.AgentDeclaredTests.*` (T015, T016); AC-017 to AC-019 to `tests.test_governance.FeatureUiStatesDocumentTests.*` (T020). Every criterion maps to at least one test; none is `[]`. (depends on T021)
- [X] T023 Fix cycle 1: in `ReviewConfigTests.test_invalid_configuration_names_a_fixed_reason`, order the cases so no two adjacent cases share a reason. Two adjacent cases rendered the same body, so the second packet read `unchanged` and failed the `published`/`updated` assertion. The assertions are unchanged. (depends on T004)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: none.
- **Foundational (Phase 2)**: depends on Setup; blocks every user story.
- **US1 (Phase 3)**: depends on Foundational. It delivers all the packet code.
- **US2, US3, US4 (Phases 4-6)**: tests only. They depend on US1's code (T008, T009) and are chained through T010 → T011 → … → T016 only because they all edit `tests/test_packet.py`.
- **US5 (Phase 7)**: T017 and T018 depend on nothing and can start at once; the wording tests T020 need T017 and T019.
- **Polish (Phase 8)**: depends on all stories.

### User Story Dependencies

- **US1 (P1)**: after Foundational. MVP.
- **US2 (P1)**: needs US1's merge and rendering; its tests are independent of US3 and US4 in content.
- **US3 (P2)**: needs US1's merge; independent of US2 and US4 in content.
- **US4 (P2)**: needs US1's rendering; independent of US2 and US3 in content.
- **US5 (P3)**: documentation; independent of the code, so it can run alongside every other phase.

### Within Each User Story

- Tests are written first and fail before the implementation (T005, T006 before T007-T009).
- Validator before parser, parser before collection, collection before the moved `UiStateTests`.

### Parallel Opportunities

- T017 and T018 (policy template, new ADR) run in parallel with each other and with all code work.
- T007 (pure functions) and T009 (rendering) are independent in content but both edit `packet.py`, so they run one after the other.
- All test tasks in `tests/test_packet.py` are serialized by file.

---

## Execution Wave DAG

Tasks grouped by dependency resolution. Tasks within a wave have no dependency on each other; tasks that edit the same file are chained explicitly, so a wave never holds two writers of one file.

```text
Wave 1 (no dependencies):
  T001      Reorder the contract's fixed-reasons table
  T017 [P] [US5] Policy template UI states section
  T018 [P] [US5] ADR-0019

Wave 2 (T001, T018 done):
  T002      agent flag on UiState and UiResult (depends on T001)
  T019 [US5] ADR-0006 amendment note (depends on T018)

Wave 3 (T002, T017, T019 done):
  T003      Source-aware _ui_states and review_config(root) (depends on T002)
  T020 [US5] Documentation wording tests (depends on T017, T019)

Wave 4 (T003 done):
  T004      Rewrite ReviewConfigTests as criterion-less entries (depends on T003)
  T007 [US1] feature_ui_states and merge_ui_states (depends on T003)

Wave 5:
  T005 [US1] Tests AC-001 to AC-004 (depends on T004)
  T008 [US1] Read and merge in collect (depends on T007)

Wave 6:
  T006 [US1] Tests AC-005, AC-006, AC-009 (depends on T005)
  T009 [US1] Render the agent-declared label (depends on T002, T008)

Wave 7:
  T010 [US1] Move UiStateTests entries to the feature file (depends on T005, T006, T008, T009)

Wave 8:
  T011 [US2] Isolation tests AC-007 to AC-009 (depends on T010)

Wave 9:
  T012 [US3] Merge and move-reason tests AC-010, AC-011 (depends on T011)

Wave 10:
  T013 [US3] Limit and failure-order tests AC-012, AC-013 (depends on T012)

Wave 11:
  T014 [US3] API section unchanged test (depends on T013)

Wave 12:
  T015 [US4] Label tests AC-014 (depends on T014)

Wave 13:
  T016 [US4] Inert name and unchanged states tests AC-015, AC-016 (depends on T015)

Wave 14:
  T021      Lint, format and FR-018 diff check (depends on T016, T020)

Wave 15:
  T022      acceptance-evidence.json (depends on T021)
```

---

## Implementation Strategy

### MVP First (User Story 1)

1. T001-T004: contract order, `agent` flag, source-aware validator, rewritten repository tests.
2. T005-T010: feature file tests, parser and merge, collection, label, moved `UiStateTests`.
3. **Stop and validate**: `uv run --no-project --python 3.13 --with pyyaml python -m unittest tests/test_packet.py` passes. At this point a feature's UI states work end to end.

### Incremental Delivery

1. Foundational + US1 → criterion-linked UI states per feature (MVP).
2. US2 → cross-feature isolation proven.
3. US3 → merge, move reason, limit and failure order proven.
4. US4 → label and inertness proven.
5. US5 → policy and ADR, written in parallel from the start.
6. Polish → lint, evidence mapping.

---

## Notes

- Every reason is fixed Ballast text from `contracts/ui-states-file.md`; no value from either file or the feature path appears in one.
- Do not touch `draft_pr.py`, `run.py`, `launcher.py`, the protected-input list, the trust baseline or `specs/19-acceptance-packet/` (plan "Repository Impact").
- Do not edit `docs/policies/`; it follows the pinned release.
