# Feature Specification: Declare UI states per feature

**Feature Branch**: `feat-142-review-declare-ui-states-per-feature`

**Created**: 2026-10-12

**Status**: Draft

**Input**: User description: "Issue #142: a feature declares its own UI states in specs/<feature>/ui-states.toml, validated against that feature's spec only."

**Tracking**: [Ballast #142](https://github.com/Hugo-Grellier/ballast/issues/142). Builds on the acceptance packet ([#19](../19-acceptance-packet/spec.md), FR-011, AC-015, AC-018) and amends [ADR-0006](../../docs/adr/0006-review-packet-reads.md). Written from the [discovery brief](discovery.md).

**Risk**: R2. Criterion-linked UI states move from the protected `ballast.toml` to an agent-writable feature file, which changes what the packet trusts from operator-owned configuration versus agent-written files ([`docs/policies/project/workflow.md`](../../docs/policies/project/workflow.md#r2-boundaries)).

**Mode**: Autonomous run `864d9151`. Every gate decision on this feature, including the pre-change approval for the R2 boundary, is agent-provisional; merging its PR is the only human approval.

## Context

The acceptance packet on a feature's Draft PR can show UI states (a screenshot path or a check result) beside the acceptance criteria they illustrate. Today those states are declared only in the repository-wide `[[review.ui_states]]` table of `ballast.toml`, but each entry's `criteria` are feature-local `AC-NNN` IDs. The packet rejects the whole table when any entry names a criterion the PR's spec does not define, so a table that fits one feature makes every other feature's packet read `configuration invalid`, and an `AC-003` reused across specs would link the wrong screenshot. Adopting repositories leave the table unset.

This feature lets each feature declare its own UI states next to its spec, in `specs/<feature>/ui-states.toml`, validated against that feature's spec only. The repository table stays for criterion-less, repository-wide screens and is merged with the feature's entries. The feature file is agent-writable like `spec.md`; the packet shows its entries as agent-declared, inert data that never changes a criterion's evidence state.

## User Scenarios & Testing *(mandatory)*

Give each acceptance scenario a stable ID (`AC-001`, `AC-002`, ...). Task and test descriptions cite the IDs they satisfy, so review can trace each criterion to evidence.

### User Story 1 - A feature's UI states appear beside its own criteria (Priority: P1)

The agent authoring a feature with visible UI declares that feature's screens in `specs/<feature>/ui-states.toml`, each naming the criteria it shows and where its screenshot or check result is found. The operator reviewing the Draft PR sees each screen beside the criterion it illustrates, checked against that feature's spec only.

**Why this priority**: This is the Issue's main outcome; without it criterion-linked UI states cannot be used in a repository with more than one feature.

**Independent Test**: In a repository with two features, give feature A a `ui-states.toml` with one valid entry for `AC-003` and publish A's packet: the link appears beside A's `AC-003`. Give the file an entry for a criterion A's spec does not define: A's UI section reads `configuration invalid` with the fixed reason and the rest of the packet is published.

**Acceptance Scenarios**:

1. **AC-001**: **Given** a feature whose `ui-states.toml` holds a `[[ui_states]]` entry with `name`, a non-empty `criteria` list of `AC-NNN` IDs its spec defines, and exactly one of `path` or `check`, **When** the packet for that feature's PR is published, **Then** the entry appears in the UI states section and beside each criterion it names, with its screenshot link or check result for the head commit, or `missing` when there is none. [S: IAC-1] [S: specs/19-acceptance-packet/spec.md] [P: D-01]
2. **AC-002**: **Given** a feature file entry that names a criterion its own spec does not define, **When** the packet is published, **Then** the UI section reads `configuration invalid` with a fixed reason that names the feature file and the undefined criterion rule, and every other packet section is published unchanged. [S: IAC-1] [S: IAC-4] [S: specs/19-acceptance-packet/research.md] [P: D-03]
3. **AC-003**: **Given** a feature file entry that breaks any existing entry rule (unknown key, name outside 1-80 characters, missing or non-`AC-NNN` criteria, both or neither of `path` and `check`, an unsafe `path`, a `check` outside 1-100 printable characters) or a file with a top-level key other than `ui_states`, **When** the packet is published, **Then** the UI section reads `configuration invalid` with the fixed reason for that rule, naming the feature file as the failing source. [S: IAC-1] [S: tools/spec_workflow/packet.py] [P: D-01] [P: D-03]
4. **AC-004**: **Given** a feature file that is not valid TOML, not UTF-8 or larger than the packet's per-file read limit, **When** the packet is published, **Then** the UI section reads `configuration invalid` with a fixed reason naming the feature file, and the rest of the packet is published. [S: specs/19-acceptance-packet/research.md] [I]
5. **AC-005**: **Given** two features whose files both name `AC-003` for different screens, **When** each feature's packet is published, **Then** each packet shows only its own feature's screen beside its `AC-003`. [S: IAC-1] [S: Issue #142 body]
6. **AC-006**: **Given** the feature file at the PR's head commit differs from a copy in the working tree, **When** the packet is published, **Then** the packet uses the head commit's file, the same commit its spec is read from. [S: tools/spec_workflow/packet.py] [I]

---

### User Story 2 - One feature never invalidates another feature's packet (Priority: P1)

The operator reviewing a feature that declares no UI states sees `not configured`, or only the repository-wide screens, never an error caused by another feature's criteria.

**Why this priority**: The Issue's pain is cross-feature invalidation; this story is the guarantee that removes it.

**Independent Test**: Publish the packet of a feature without `ui-states.toml` in a repository where another feature has one and `ballast.toml` has no UI states: the UI section reads `UI states: not configured.`. Add a criterion-less repository entry: the section lists only that entry.

**Acceptance Scenarios**:

1. **AC-007**: **Given** a feature without `ui-states.toml` and a `ballast.toml` without `[[review.ui_states]]`, **When** its packet is published, **Then** the UI section reads `UI states: not configured.`, whatever other features' files declare. [S: IAC-2] [S: IAC-4]
2. **AC-008**: **Given** a feature without `ui-states.toml` and a `ballast.toml` with valid criterion-less `[[review.ui_states]]` entries, **When** its packet is published, **Then** the UI section lists exactly those repository entries with their results and none appears beside a criterion. [S: IAC-2] [S: IAC-4] [B: D-05] [I]
3. **AC-009**: **Given** any feature's packet, **When** it is published, **Then** its UI section never reads `configuration invalid` because of a criterion defined or cited by another feature's spec or file. [S: IAC-2]

---

### User Story 3 - Repository-wide screens stay operator-owned and merge with the feature's (Priority: P2)

The operator keeps repository-wide screens (for example a home page check) in the protected `ballast.toml`, without criteria. Every feature's packet lists them together with that feature's own entries. A repository entry that still names criteria is reported with the fix: move it to the feature file.

**Why this priority**: It keeps existing operator-owned configuration useful and gives a clear migration path, but the feature-local file already delivers the main outcome.

**Independent Test**: Configure one criterion-less repository entry and one feature-file entry, publish the packet: the section lists both, and only the feature entry appears beside its criterion. Add `criteria` to the repository entry: the UI section reads `configuration invalid` with a reason that names moving the entry to the feature file.

**Acceptance Scenarios**:

1. **AC-010**: **Given** a `ballast.toml` with criterion-less `[[review.ui_states]]` entries and a feature file with valid entries, **When** that feature's packet is published, **Then** the UI section lists the repository entries and the feature entries together, and only the feature entries appear beside criteria. [S: IAC-1] [S: IAC-2] [B: D-05]
2. **AC-011**: **Given** a `ballast.toml` `[[review.ui_states]]` entry that has a `criteria` key, even an empty list, **When** any feature's packet is published, **Then** the UI section reads `configuration invalid` with a fixed reason that names moving the entry to `specs/<feature>/ui-states.toml`. [S: .specify/workflow-state/issues/142.md] [B: D-05] [P: D-02]
3. **AC-012**: **Given** more than 50 UI states across the repository table and the feature file together, **When** the packet is published, **Then** the UI section reads `configuration invalid (more than 50 UI states)` and the rest of the packet is published. [S: .specify/workflow-state/issues/142.md] [B: D-07]
4. **AC-013**: **Given** a repository entry that breaks an existing entry rule other than criteria, **When** the packet is published, **Then** the UI section reads `configuration invalid` with the fixed reason for that rule, naming the repository table as the failing source. [S: tools/spec_workflow/packet.py] [P: D-03]

---

### User Story 4 - Agent-declared entries are marked and inert (Priority: P2)

The operator can tell which UI links the protected configuration supplies and which an agent declared, and nothing an agent writes in the feature file can change the packet's structure, a criterion's state or its labels.

**Why this priority**: The feature file is agent-writable by operator decision; this story keeps that authority bounded.

**Independent Test**: Put markup, a mention, a link and a packet marker in a feature entry's `name`, publish the packet: the name shows as plain text, the entry carries the fixed agent-declared label, and every criterion's evidence state matches the packet without the file.

**Acceptance Scenarios**:

1. **AC-014**: **Given** a valid feature file entry, **When** the packet is published, **Then** the entry carries one fixed Ballast-written label stating it is agent-declared in `ui-states.toml`, and repository entries carry no such label. [S: .specify/workflow-state/issues/142.md] [P: D-04]
2. **AC-015**: **Given** a feature entry whose name contains Markdown, HTML, a link, an `@` mention or a packet marker, **When** the packet is published, **Then** the name is rendered as inert text that cannot end the section, form a link or mention, or change a state or label. [S: templates/policies/spec-kit-workflow.md] [S: tools/spec_workflow/packet.py]
3. **AC-016**: **Given** any feature file, valid or invalid, **When** the packet is published, **Then** no acceptance criterion's evidence state differs from the state it has without the file. [S: specs/19-acceptance-packet/research.md] [I]

---

### User Story 5 - Adopters know where UI states live and why it changed (Priority: P3)

A project author reads the acceptance packet section of the workflow policy to learn where to declare UI states and how to keep screenshots current; a maintainer reads the new ADR to see why criterion-linked UI states left the protected configuration.

**Why this priority**: Required for adoption and for the R2 record, but it describes behavior delivered by the stories above.

**Independent Test**: Read the policy's acceptance packet section and the new ADR: each statement below is present.

**Acceptance Scenarios**:

1. **AC-017**: **Given** the acceptance packet section of the workflow policy template, **When** a project author reads it, **Then** it states that criterion-linked UI states live in `specs/<feature>/ui-states.toml` with the entry schema and an example, that `[[review.ui_states]]` in `ballast.toml` holds only criterion-less repository-wide entries merged with the feature's, the 50-entry total limit, and that feature entries are agent-declared and never change a criterion's state. [S: IAC-3] [S: templates/policies/spec-kit-workflow.md]
2. **AC-018**: **Given** the same policy section, **When** a project author reads it, **Then** it explains how screenshots are kept current: a `path` screenshot is committed with the change that alters the screen and is linked at the head commit, a `check` result is read for the head commit, and a state without a head-commit result shows `missing`. [S: IAC-3] [S: specs/19-acceptance-packet/spec.md]
3. **AC-019**: **Given** the repository's ADRs, **When** a maintainer reads them, **Then** a new ADR records that criterion-linked UI states move from the protected `ballast.toml` to the agent-writable feature file, amends ADR-0006's statement that the packet's configuration lives in `ballast.toml`, and states that the packet gains no new program, GitHub call, fetch or authority. [S: .specify/workflow-state/issues/142.md] [S: docs/adr/0006-review-packet-reads.md]

### Edge Cases

- A feature file that exists but declares no `ui_states` key and no other key adds no entries; with no repository entries the section reads `not configured`. [I]
- A feature file whose `ui_states` is not a list of tables reads `configuration invalid` naming the feature file. [S: tools/spec_workflow/packet.py] [P: D-01]
- When both sources are invalid, the section shows one fixed reason; which source is reported first is a plan detail, and the section never shows partial results. [P: D-03]
- A feature entry's `path` or `check` may point at an unrelated or misleading result; it is shown only as an agent-declared link and never changes the criterion's state. [I]
- The PR's spec cannot be read or has no criteria: feature entries cannot be validated against it, so any feature entry is reported as naming a criterion the spec does not define. [S: tools/spec_workflow/packet.py] [I]
- Agents cannot change the repository table: `ballast.toml` stays a protected input, read from the run's root as today. [S: .specify/memory/constitution.md] [S: AGENTS.md]

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The packet MUST read UI states for a PR from two sources: the criterion-less `[[review.ui_states]]` entries of the protected `ballast.toml`, and the `[[ui_states]]` entries of `ui-states.toml` in the PR's feature directory at the head commit. [S: IAC-1] [B: D-05] [P: D-01]
- **FR-002**: Feature file entries MUST use the existing entry schema and rules (`name` 1-80 characters; a non-empty `criteria` list of `AC-NNN` IDs; exactly one of a safe repository-relative `path` or a 1-100 printable-character `check`; no other key), and the feature file MUST hold no top-level key other than `ui_states`. [S: IAC-1] [S: tools/spec_workflow/packet.py] [P: D-01] [P: D-02]
- **FR-003**: Each feature entry's criteria MUST be checked against the acceptance criteria of the PR's own feature spec only; another feature's spec or file MUST NOT affect the result. [S: IAC-1] [S: IAC-2]
- **FR-004**: A `[[review.ui_states]]` entry in `ballast.toml` MUST have no `criteria` key; an entry with one, even empty, MUST make the UI section `configuration invalid` with a fixed reason naming the move to `specs/<feature>/ui-states.toml`. Repository entries otherwise keep the existing rules. [S: .specify/workflow-state/issues/142.md] [B: D-05] [P: D-02]
- **FR-005**: The packet MUST merge valid repository and feature entries into one UI states section; at most 50 entries MUST be allowed in total, and more MUST read `configuration invalid (more than 50 UI states)`. [S: .specify/workflow-state/issues/142.md] [B: D-07]
- **FR-006**: Only feature entries MUST appear beside the criteria they name; repository entries MUST appear only in the UI states section. [S: IAC-1] [I]
- **FR-007**: With no feature file and no repository entries the UI section MUST read `UI states: not configured.`; with no feature file and valid repository entries it MUST list those entries only. [S: IAC-2] [B: D-05]
- **FR-008**: Any invalid source MUST make the whole UI section `configuration invalid (<fixed reason>)`, with the reason naming the failing source (repository table or feature file); the rest of the packet MUST be published and the packet MUST NOT stop. [S: specs/19-acceptance-packet/research.md] [P: D-03]
- **FR-009**: A feature file that is not valid TOML, not UTF-8 or larger than the packet's per-file read limit MUST be treated as an invalid source with a fixed reason. [S: specs/19-acceptance-packet/research.md] [I]
- **FR-010**: Feature entries MUST carry one fixed Ballast-written label marking them agent-declared from `ui-states.toml`; repository entries MUST NOT carry it. [S: .specify/workflow-state/issues/142.md] [P: D-04]
- **FR-011**: Every agent-written value from the feature file MUST be rendered inert, and every link MUST be built by Ballast from validated parts as today. [S: docs/adr/0006-review-packet-reads.md] [S: tools/spec_workflow/packet.py]
- **FR-012**: A UI state from either source MUST NOT change any acceptance criterion's evidence state. [S: specs/19-acceptance-packet/research.md]
- **FR-013**: The feature file MUST remain agent-writable and MUST NOT be added to the protected inputs or the trust baseline. [S: .specify/workflow-state/issues/142.md] [B: D-06]
- **FR-014**: The packet MUST read the feature file only from the local Git object store at the head commit, with the reads ADR-0006 already allows for feature artifacts; it MUST add no new program, GitHub call, fetch, download or execution. [S: docs/adr/0006-review-packet-reads.md] [S: tools/spec_workflow/packet.py]
- **FR-015**: The workflow tools changed by this feature MUST stay standard-library-only and run under `python3 -I -S`. [S: AGENTS.md]
- **FR-016**: The acceptance packet section of `templates/policies/spec-kit-workflow.md` MUST describe where UI states live (feature file and criterion-less repository table), the entry schema with an example, the merge and 50-entry total limit, the move-to-feature-file error, the agent-declared label, and how screenshots are kept current. [S: IAC-3] [S: templates/policies/spec-kit-workflow.md]
- **FR-017**: A new ADR under `docs/adr/` MUST record the move of criterion-linked UI states out of the protected `ballast.toml` and amend ADR-0006's configuration statement. [S: .specify/workflow-state/issues/142.md] [S: docs/adr/0006-review-packet-reads.md]
- **FR-018**: Automated tests MUST cover a valid feature file, a feature entry naming a criterion missing from the spec, a feature without the file, a repository entry with criteria, and the merge of repository and feature entries; existing UI states tests change only where a repository entry with criteria now gives the new error. [S: IAC-4] [S: tests/test_packet.py]

### Key Entities

- **Feature UI states file**: `specs/<feature>/ui-states.toml`, agent-writable feature data with the same authority as `spec.md`; holds a `ui_states` list of entries, each linked to that feature's criteria.
- **Repository UI state**: a criterion-less `[[review.ui_states]]` entry in the protected `ballast.toml`; a repository-wide screen shown on every feature's packet.
- **UI state entry**: a name, its criteria (feature entries only) and exactly one of a screenshot `path` or a `check` name; its result is resolved for the head commit.
- **UI states section**: the packet section listing the merged entries with their results, or one `not configured` or `configuration invalid (<reason>)` line; a derived view, never an authority over a criterion's state.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In a repository with two or more features, 0 packets read `configuration invalid` because of another feature's UI states.
- **SC-002**: A feature author declares a criterion-linked screen by editing one file in their feature directory, without operator involvement or a change to protected configuration.
- **SC-003**: 100% of tested invalid configurations (each entry rule, each source, undefined criterion, repository criteria, over 50 entries, unreadable file) produce a `configuration invalid` line with a fixed reason while the rest of the packet is published.
- **SC-004**: In 100% of tested cases, every criterion's evidence state is identical with and without the feature file.
- **SC-005**: A reviewer can tell, for every UI state link in the packet, whether the operator's configuration or an agent declared it.

## Non-goals

- Adding the feature file to the protected inputs or the trust baseline; the operator chose agent-writable (decision 2b). [B: D-06]
- Removing `[[review.ui_states]]` from `ballast.toml`; the operator chose to keep it for criterion-less entries (decision 1b). [B: D-05]
- Capturing screenshots, the `[demo]` table and OpenAPI comparison. [S: .specify/workflow-state/issues/142.md]
- Letting a UI state change a criterion's evidence state. [S: specs/19-acceptance-packet/research.md]
- Showing partial UI results when one source is invalid. [P: D-03]

Every Issue acceptance criterion (IAC-1, IAC-2, IAC-3, IAC-4) is covered by an acceptance criterion above; none is a non-goal.

## Assumptions

- The feature file holds a top-level `[[ui_states]]` array of tables; any other top-level key is a configuration error (D-01, agent-provisional). [P: D-01]
- A repository entry is criterion-less when it omits the `criteria` key; any `criteria` key in `ballast.toml` is the move-to-feature-file error, and feature entries keep the non-empty `AC-NNN` rule (D-02, agent-provisional). [P: D-02]
- An invalid entry from either source makes the whole UI section `configuration invalid`, with a fixed reason naming the failing source (D-03, agent-provisional). [P: D-03]
- Feature entries carry one fixed agent-declared label naming `ui-states.toml`; repository entries are unlabelled (D-04, agent-provisional). [P: D-04]
- The feature file is read at the head commit like `spec.md`, so the spec and its UI states come from the same commit. [I]
- Criterion-less repository entries appear only in the UI states section, never beside a criterion. [I]
- The feature file uses the packet's existing per-file read limit and safe-path rules; no new limit is introduced. [I]
- An existing `ballast.toml` whose UI states name criteria becomes `configuration invalid` with the move reason; projects migrate by moving those entries to the feature file, and no automatic migration is provided. [S: .specify/workflow-state/issues/142.md] [I]
