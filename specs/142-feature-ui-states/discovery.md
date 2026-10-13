<!-- ballast-discovery: input evidence -->
# Discovery brief: Declare UI states per feature

This brief is input evidence for [spec.md](spec.md). It is not the feature's
authority: once intent is recorded, [spec.md](spec.md) and [intent.md](intent.md)
govern, and later steps do not read requirements from this file.

**Mode**: autonomous
**Issue**: #142 (snapshot `.specify/workflow-state/issues/142.md`, untrusted requirements data)

## Sources

- S-1: Issue #142 body
- S-2: Issue #142 intake scope comment (part of the snapshot; operator decisions 1b, 2b and Autonomous, 2026-10-12)
- S-3: specs/142-feature-ui-states/autonomous/record.md#Provisional decisions (PD-0001, agent-provisional scope accept)
- S-4: tools/spec_workflow/packet.py:521 (`review_config`, `_ui_states`), :834 (`collect`, feature files read at head), :1027 (UI results beside criteria), :1597 (`_ui_lines`)
- S-5: docs/adr/0006-review-packet-reads.md#What it does not add ("the packet's configuration lives in the protected `ballast.toml`")
- S-6: specs/19-acceptance-packet/research.md#R11 and #R12 (UI states schema, `[review]` in protected `ballast.toml`, invalid configuration never stops the packet)
- S-7: specs/19-acceptance-packet/spec.md (FR-011, AC-015, AC-018)
- S-8: specs/19-acceptance-packet/contracts/packet-format.md#UI states
- S-9: templates/policies/spec-kit-workflow.md#Acceptance packet (`[review]` table documentation; `docs/policies/*.md` is the git-ignored installed copy)
- S-10: docs/policies/project/workflow.md#R2 boundaries (launcher trust model: trusted inputs)
- S-11: .specify/memory/constitution.md (BL-INV-003, protected inputs)
- S-12: tests/test_packet.py (`ReviewConfigTests`, `UiStateTests`)
- S-13: AGENTS.md#Invariants
- S-14: .gitignore (`docs/policies/*.md` installed and ignored)
- unavailable: Issue comments — the snapshot records none

## Need

- **User**: the operator reviewing a feature's Draft PR in a repository that has UI screens, and the agent authoring that feature [S: Issue #142 body]
- **Job to be done**: see each UI state's screenshot or check result beside the acceptance criterion it shows, for the PR's own feature [S: specs/19-acceptance-packet/spec.md]
- **Current pain**: `[[review.ui_states]]` is repository-wide but its `criteria` are feature-local `AC-NNN` IDs, so any table that fits one feature makes every other feature's packet `configuration invalid`, and adopters leave it unset [S: Issue #142 body]
- **Intended outcome**: a feature declares its own UI states in `specs/<feature>/ui-states.toml`, validated against that feature's spec only, merged with criterion-less repository entries [S: Issue #142 body] [S: .specify/workflow-state/issues/142.md]

## Examples

- Feature A's `specs/A/ui-states.toml` lists `name = "Login error"`, `criteria = ["AC-003"]`, `path = "docs/screens/login-error.png"`; feature A's packet shows that link beside AC-003, and feature B's packet is unaffected [S: Issue #142 body]
- Feature B has no `ui-states.toml` and the repository has no `[[review.ui_states]]`; B's packet reads `UI states: not configured.` [S: IAC-2]
- `ballast.toml` keeps `[[review.ui_states]]` with `name = "Home"`, `check = "ui / home"` and no `criteria`; every feature's packet lists it in the UI section, merged with that feature's entries [S: .specify/workflow-state/issues/142.md]
- `ballast.toml` holds an entry with `criteria = ["AC-003"]`; the packet reports a configuration error that names moving the entry to the feature file [S: .specify/workflow-state/issues/142.md]
- A feature file cites `AC-009`, which its spec does not define; the UI section reads `configuration invalid (UI state names a criterion the spec does not define)` [S: tools/spec_workflow/packet.py:575]

## Scope

- Read `<feature>/ui-states.toml` for the PR's feature directory with the existing entry schema (`name`, `criteria`, exactly one of `path` or `check`) and validate its criteria against that feature's spec [S: IAC-1]
- At most 50 UI states in total across repository and feature entries [S: .specify/workflow-state/issues/142.md]
- Keep `[[review.ui_states]]` in `ballast.toml`, restricted to entries without `criteria`, merged with the feature entries; a repository entry with `criteria` is a configuration error naming the move to the feature file [S: .specify/workflow-state/issues/142.md]
- The feature file stays agent-writable like `spec.md`; the packet renders its entries as agent-declared, inert data [S: .specify/workflow-state/issues/142.md]
- A new ADR recording that criterion-linked UI states move out of the protected `ballast.toml`, amending ADR-0006's configuration statement [S: .specify/workflow-state/issues/142.md] [S: docs/adr/0006-review-packet-reads.md]
- Policy docs (acceptance packet section) describe where UI states live and how screenshots are kept current [S: IAC-3]
- Tests: valid feature file, criterion missing from the spec, feature without the file, repository entry with criteria, merge of repository and feature entries [S: IAC-4] [S: .specify/workflow-state/issues/142.md]

## Non-goals

- Adding the feature file to the protected inputs or the trust baseline (operator decision 2b) [S: .specify/workflow-state/issues/142.md]
- Removing `[[review.ui_states]]` from `ballast.toml` (operator decision 1b) [S: .specify/workflow-state/issues/142.md]
- Capturing screenshots, the `[demo]` table, OpenAPI comparison [S: .specify/workflow-state/issues/142.md]
- Changing a criterion's evidence state from a UI state; a UI state never changes it [S: specs/19-acceptance-packet/research.md#R11]

## Constraints

- Workflow tools stay standard-library-only (`tomllib`) and run under `python3 -I -S` [S: AGENTS.md#Invariants]
- No new program, GitHub call, fetch or download: the feature file is read at the head commit from the local object store with the same `git cat-file` reads ADR-0006 already allows for feature artifacts [S: docs/adr/0006-review-packet-reads.md] [S: tools/spec_workflow/packet.py:834]
- An invalid configuration never stops the packet; the UI section says `configuration invalid (<fixed reason>)` and the rest is published [S: specs/19-acceptance-packet/research.md#R12]
- Agent-written text is rendered inert: it cannot end the section, form a link or mention, or change a state or label [S: templates/policies/spec-kit-workflow.md] [S: tools/spec_workflow/packet.py:1597]
- The edit goes to `templates/policies/spec-kit-workflow.md`; `docs/policies/*.md` is the ignored installed copy [S: .gitignore]
- Risk R2: the change touches the launcher's trust model (what the packet trusts from `ballast.toml` versus agent-written files) [S: docs/policies/project/workflow.md] [S: specs/142-feature-ui-states/autonomous/record.md]

## Permissions and data authority

- `ballast.toml` stays the protected, operator-owned source for repository-wide, criterion-less UI states; agents cannot change it [S: .specify/memory/constitution.md] [S: specs/19-acceptance-packet/research.md#R12]
- `<feature>/ui-states.toml` is agent-writable feature data, same authority as `spec.md`; it can only add links beside its own feature's criteria and never changes a criterion's state [S: .specify/workflow-state/issues/142.md] [S: specs/19-acceptance-packet/research.md#R11]
- The packet gains no GitHub authority and no new read beyond the existing local Git object reads [S: docs/adr/0006-review-packet-reads.md]

## Success evidence

- Unit tests in `tests/test_packet.py` for each IAC-4 case plus the repository-entry-with-criteria error and the merge [S: IAC-4] [S: tests/test_packet.py]
- Existing `ReviewConfigTests` and `UiStateTests` keep passing or are updated only where a repository entry with criteria now gives the new error [S: tests/test_packet.py]
- The acceptance packet section of the policy template documents the feature file, the repository table's restriction and how screenshots are kept current [S: IAC-3]
- A new ADR under `docs/adr/` amending ADR-0006 [S: .specify/workflow-state/issues/142.md]

## Edge, failure and permission cases

- Feature file absent and no repository table: `not configured` [S: IAC-2]
- Feature file absent, repository criterion-less entries present: only those entries, never an error caused by another feature [S: IAC-2]
- Feature file not valid TOML, not UTF-8 or over the 1 MiB file limit: UI section `configuration invalid (<fixed reason>)`, rest published [I]
- Feature entry cites a criterion the spec does not define: `configuration invalid` [S: tools/spec_workflow/packet.py:575]
- More than 50 entries after merging: `configuration invalid (more than 50 UI states)` [S: .specify/workflow-state/issues/142.md]
- A feature entry's `path` or `check` points at an unrelated or misleading result: shown as an agent-declared link only; the criterion's state is unchanged [I]
- Agent-written names in the feature file contain markup, mentions or packet markers: rendered inert [S: tools/spec_workflow/packet.py:1597]
- A repository entry with `criteria`: configuration error naming the move to the feature file [S: .specify/workflow-state/issues/142.md]

## Issue acceptance criteria

- IAC-1: A feature-local UI states file is read for the PR's feature directory, validated with the existing rules, and its criteria are checked against that feature's spec only.
- IAC-2: A PR for a feature without the file reports `not configured` (or the repository entries, if kept), never `configuration invalid` because of another feature's criteria.
- IAC-3: Policy docs (`spec-kit-workflow.md`, acceptance packet section) describe where UI states live and how screenshots are kept current.
- IAC-4: Tests cover a valid feature file, a criterion missing from the spec, and a feature without the file.

## Known

- Today `_ui_states` rejects the whole table when any entry cites a criterion the spec does not define [S: tools/spec_workflow/packet.py:575]
- The packet already lists every file under the feature directory at the head commit and reads them with `git cat-file` [S: tools/spec_workflow/packet.py:834]
- `ballast.toml` is read from the run's root, a protected input [S: tools/spec_workflow/packet.py:521] [S: .specify/memory/constitution.md]
- The repository table is kept, criterion-less only (decision 1b) [S: .specify/workflow-state/issues/142.md]
- The feature file is not protected (decision 2b) [S: .specify/workflow-state/issues/142.md]
- The 50-entry limit applies to the total [S: .specify/workflow-state/issues/142.md]
- Feature entries use the existing schema, so `path` is a repository-relative safe path as today [S: Issue #142 body] [S: specs/19-acceptance-packet/research.md#R11]
- A new ADR amends ADR-0006 [S: .specify/workflow-state/issues/142.md]

## Inferred

- The feature file is read at the head commit like `spec.md`, so the spec and its UI states come from the same commit [I]
- Criterion-less repository entries appear only in the UI states section, not beside any criterion [I]
- The feature file holds a top-level `[[ui_states]]` array of tables and no other key [P: D-01]
- A repository entry is criterion-less when it omits the `criteria` key; any `criteria` key in `ballast.toml`, even an empty list, is the move-to-feature-file error; feature entries still need a non-empty `criteria` list [P: D-02]
- Any invalid entry from either source makes the whole UI section `configuration invalid`, with a fixed reason that says which source (repository table or feature file) failed [P: D-03]
- The UI section marks feature-file entries as agent-declared (one fixed label naming `ui-states.toml`), while repository entries stay unlabelled [P: D-04]

## Undecided

None.

## Decisions

### D-01: Layout of the feature file
- **Status**: assumed
- **Question**: Which TOML layout does `<feature>/ui-states.toml` use?
- **Why it matters**: the parser, the docs example and the tests depend on the key name.
- **Sources**: [S: Issue #142 body] [S: tools/spec_workflow/packet.py:521]
- **Options**:
  - A — top-level `[[ui_states]]` array of tables; any other top-level key is a configuration error. Consequence: the file reads like the repository table without the `review.` prefix and `_ui_states` validates entries unchanged.
  - B — `[[review.ui_states]]`, copying `ballast.toml`. Consequence: an identical snippet, but a redundant `review` table in a file that holds only UI states.
- **Recommended default**: A, because the file has one purpose and the entry schema is reused as is.
- **Answer**:
- **Resolution**: assumed A. It is a file format detail of a new, unreleased file; renaming the key later is a mechanical change to the parser, docs and tests, and no data or authority depends on it.

### D-02: How a repository entry is criterion-less
- **Status**: assumed
- **Question**: What makes a `ballast.toml` entry "without criteria", and do feature entries still require criteria?
- **Why it matters**: decides which repository entries trigger the move-to-feature-file error and the validation of each source.
- **Sources**: [S: .specify/workflow-state/issues/142.md] [S: tools/spec_workflow/packet.py:541]
- **Options**:
  - A — repository entries omit `criteria`; any `criteria` key (even `[]`) is the move error; feature entries keep the existing non-empty `AC-NNN` list rule. Consequence: one clear rule per source, existing feature validation unchanged.
  - B — repository entries may write `criteria = []`. Consequence: two spellings of the same thing and a weaker error signal.
- **Recommended default**: A, because it keeps one spelling and the existing rule for criterion-linked entries.
- **Answer**:
- **Resolution**: assumed A. Decision 1b fixes that repository entries carry no criteria; this only picks the spelling. Accepting `[]` later is a relaxation that breaks no configuration.

### D-03: Failure isolation between the two sources
- **Status**: assumed
- **Question**: When one source is invalid, does the UI section fail whole or show the valid source?
- **Why it matters**: the rendered section and the invalid-configuration tests.
- **Sources**: [S: specs/19-acceptance-packet/research.md#R12] [S: tools/spec_workflow/packet.py:1597]
- **Options**:
  - A — the whole UI section is `configuration invalid (<fixed reason>)`, the reason naming the failing source; the rest of the packet is published. Consequence: matches today's one-reason section and keeps the 50 total limit simple.
  - B — show the valid source's entries and an invalid line for the other. Consequence: more output states to render and test.
- **Recommended default**: A, because it keeps the existing section contract and still never blames another feature.
- **Answer**:
- **Resolution**: assumed A. It extends the existing R12 behavior; showing partial results later is additive. IAC-2 holds either way because a feature only reads its own file.

### D-04: How agent-declared entries are shown
- **Status**: assumed
- **Question**: How does the packet show that feature-file entries are agent-declared?
- **Why it matters**: the rendered UI lines and the inert-rendering tests.
- **Sources**: [S: .specify/workflow-state/issues/142.md] [S: tools/spec_workflow/packet.py:1597]
- **Options**:
  - A — a fixed label on feature entries naming `ui-states.toml` as agent-declared; names stay rendered through `inert`; repository entries unlabelled. Consequence: the reviewer sees which links the operator configured and which an agent declared.
  - B — no label, inert rendering only. Consequence: the reviewer cannot tell the trust level of a link.
- **Recommended default**: A, because the intake asks for agent-declared rendering and the label is Ballast-built text.
- **Answer**:
- **Resolution**: assumed A. The label is fixed Ballast text that adds no authority; its wording can change later without affecting data or permissions.

### D-05: Repository table kept or dropped
- **Status**: settled
- **Question**: Drop `[[review.ui_states]]` or keep it for criterion-less entries?
- **Why it matters**: parser, migration of existing configs and docs.
- **Sources**: [S: Issue #142 body] [S: .specify/workflow-state/issues/142.md]
- **Options**:
  - A — keep, criterion-less only, merged. Consequence: repository-wide screens stay operator-controlled.
  - B — drop. Consequence: every UI state is agent-declared.
- **Recommended default**: A
- **Answer**:
- **Resolution**: A, operator decision 1b in the Issue intake scope comment [S: .specify/workflow-state/issues/142.md]

### D-06: Protect the feature file
- **Status**: settled
- **Question**: Is `<feature>/ui-states.toml` a protected input?
- **Why it matters**: trust baseline and tamper handling.
- **Sources**: [S: Issue #142 body] [S: .specify/workflow-state/issues/142.md]
- **Options**:
  - A — agent-writable like `spec.md`, rendered as agent-declared inert data. Consequence: no trust-baseline change.
  - B — protected input. Consequence: agents cannot declare their feature's UI states.
- **Recommended default**: A
- **Answer**:
- **Resolution**: A, operator decision 2b in the Issue intake scope comment, which overrides the Issue body's suggestion [S: .specify/workflow-state/issues/142.md]

### D-07: Where the 50-entry limit applies
- **Status**: settled
- **Question**: Is the limit per source or in total?
- **Why it matters**: validation and tests.
- **Sources**: [S: .specify/workflow-state/issues/142.md]
- **Options**:
  - A — 50 in total after merging. Consequence: the packet section stays bounded.
  - B — 50 per source. Consequence: up to 100 lines.
- **Recommended default**: A
- **Answer**:
- **Resolution**: A, "at most 50 in total" in the Issue intake scope comment [S: .specify/workflow-state/issues/142.md]

## Question metrics

- **Rounds**: 0
- **Questions asked**: 0
- **Assumptions adopted**: 4
