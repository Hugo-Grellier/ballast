# Research: Declare UI states per feature

Each entry records a design decision for [plan.md](plan.md). Sources are the current code (`tools/spec_workflow/packet.py`), #19's research and the operator decisions in the Issue #142 intake comment.

## R1. Where and when the feature file is read

- **Decision**: `_Step.collect` reads `ui-states.toml` with its existing `read(name)` helper, after `spec.md` and before the UI results are resolved. The helper already serves only names listed by `git ls-tree -r -z --name-only <head> -- <feature>/` and reads them with `git cat-file -s` and `git cat-file blob` at the head commit, with the 1 MiB `FILE_LIMIT`. Presence is `"ui-states.toml" in files`; a listed file whose text is `None` is either too large (the helper's flag, which also adds it to `too_large`) or not UTF-8.
- **Rationale**: the spec and its UI states come from the same commit (AC-006), and ADR-0006 already allows these reads for feature artifacts (FR-014). The working tree is never read, so an uncommitted edit cannot reach the packet.
- **Alternatives**: reading `<root>/<feature>/ui-states.toml` from the working tree, like `ballast.toml`, was rejected: it could disagree with the head commit's spec and with what the PR shows.

## R2. Validation shared by both sources

- **Decision**: `_ui_states(value, source, spec_ids=None)` keeps its rule order and fixed rule texts, with two source-dependent changes:
  - **Repository** (`ballast.toml`): before any other entry rule, an entry with a `criteria` key, even `[]`, fails with `UI state criteria belong in the feature's ui-states.toml`. The allowed keys are `name`, `path`, `check`. A valid entry gets `criteria=()`.
  - **Feature** (`ui-states.toml`): the allowed keys and rules are today's, including the non-empty `AC-NNN` list, and `spec_ids` is always passed, so the undefined-criterion rule always applies.
  - `review_config(root)` no longer takes `spec_ids`: repository entries carry no criteria to check, so the protected table's validity no longer depends on which feature's packet is built (AC-009).
- **Rationale**: one validator keeps the entry schema identical across sources (FR-002, D-01). Checking the `criteria` key first on repository entries gives the migration message rather than an unrelated rule for configurations written before this change (AC-011, D-02).
- **Alternatives**: a second validator for feature entries would duplicate seven rules. Silently ignoring repository `criteria` would hide stale configuration and could link the wrong feature's screen.

## R3. Fixed reasons name the failing source

- **Decision**: every UI reason except the limit is `<source>: <rule>`, where `<source>` is the fixed text `ballast.toml` or `ui-states.toml`. The full list is in [contracts/ui-states-file.md](contracts/ui-states-file.md#fixed-reasons). The feature file adds four file-level reasons: `not valid TOML`, `not UTF-8 text`, `larger than 1 MiB` and `has a top-level key other than ui_states`.
- **Rationale**: AC-002, AC-003, AC-004 and AC-013 require the reason to name the failing source. The reasons stay fixed Ballast text: neither the feature path nor any value from either file appears in them, so a reason cannot carry agent-written text. The PR's feature is already named in the packet header, so `ui-states.toml` is unambiguous.
- **Consequence for existing tests**: every existing `ReviewConfigTests` UI case uses a repository entry with `criteria`, so each now gives the move error (FR-018 allows exactly this change). The cases are rewritten as criterion-less repository entries to keep each rule covered, with the new `ballast.toml:` prefix, and the criteria rules move to the feature file.
- **Alternatives**: naming the source in a separate sentence would change the one-line section contract of #19 R12.

## R4. Failure order and the limit

- **Decision**:
  1. The repository table is validated first. If it is invalid, its reason is shown and the feature file's result is not reported (the spec's open edge case).
  2. Otherwise, if the feature file is invalid, its reason is shown.
  3. Otherwise, if the repository entries and the feature entries together exceed 50, the reason is `more than 50 UI states`, without a source prefix (AC-012 gives the exact text). A single source with more than 50 entries gives the same reason, checked before its entries are validated, as today.
  4. Otherwise the merged tuple is repository entries then feature entries, in file order.
- **Rationale**: the repository table's validity is the same for every feature's packet, so reporting it first gives the operator one stable message across all PRs. The whole section fails on any error, never showing partial results (D-03, FR-008). The limit applies to the total (D-07).
- **Alternatives**: reporting the feature file first would make the operator's own misconfiguration appear only on some packets.

## R5. "Not configured" versus "none"

- **Decision**: the merged result is `None` (section reads `UI states: not configured.`) only when neither source declares UI states: `ballast.toml` has no `review.ui_states` and the feature file is absent or has no `ui_states` key. A declared but empty list on either side gives `None (0).`, as an empty repository list does today.
- **Rationale**: keeps today's distinction between "absent" and "declared empty" and gives the spec's edge case (file without `ui_states`) the `not configured` line (AC-007).

## R6. Rendering the agent-declared label

- **Decision**: one fixed string `agent-declared in ui-states.toml`, written by Ballast, never derived from the file.
  - Section line, feature entry: `- <inert name> (<AC IDs>, agent-declared in ui-states.toml): <result>`.
  - Section line, repository entry: `- <inert name>: <result>` (no empty parentheses).
  - Beside a criterion: ` · UI <inert name> (agent-declared in ui-states.toml): <result>`. Only feature entries reach a criterion, because repository entries have no criteria.
  - The shortened count line at level ≥ 3 is unchanged and counts both sources.
- **Rationale**: SC-005 needs every link's origin to be visible, and AC-014 needs the label only on feature entries. Parentheses, not brackets, so the label can never join a following `(` into a Markdown link. Names keep `inert(name, 80)`; the AC IDs and paths shown are validated (`AC-NNN`, `safe_path`) and links are built by `_blob` and `_run_link` from validated parts (FR-011). The label contains no approval word, so #19's `HUMAN_APPROVAL` guard is unaffected.
- **Alternatives**: a separate subsection per source would add a heading and a second limit to the shortening rules. Labelling repository entries "operator-configured" was not chosen: AC-014 asks for no label on them.

## R7. Evidence states stay independent

- **Decision**: `evaluate` computes every criterion's state before any UI result exists, and the merge only replaces `Criterion.ui`. `Criterion.state` and `reason` never read `ui`. No change is needed; a test compares every criterion's state and reason with and without a feature file, valid and invalid (AC-016, SC-004).
- **Rationale**: #19 R11 already guarantees this; the test keeps it true with an agent-writable source.

## R8. What a feature entry can point at

- **Decision**: a feature entry's `path` is any safe repository-relative path and its `check` any check-run name, as for the repository table; Ballast shows the result at the head commit under the agent-declared label and never treats it as evidence.
- **Rationale**: the agent can already commit any file and name any check in `tasks.md` or `spec.md`; the label tells the reviewer the link was declared by an agent (spec edge case "unrelated or misleading result"). Restricting paths to the feature directory would break the common `docs/screens/` layout of the Issue's example.

## R9. Risk recheck against the R2 boundaries

- **Decision**: R2 stands. The boundary touched is the review packet's trust model: what the packet reads from operator-owned configuration versus agent-written files. Nothing else in the [R2 list](../../docs/policies/project/workflow.md#r2-boundaries) changes:
  - headless-agent permissions: unchanged; agents could already write `specs/**`;
  - the launcher's trust model: protected inputs and the trust baseline unchanged (FR-013);
  - what `ballast` executes or downloads: unchanged (FR-014); the file is parsed by `tomllib`;
  - installed-path ignore rules: unchanged; the file is committed project data.
- **Record**: ADR-0019 states the move and its bound (labelled, inert, no state change, own feature only) and amends ADR-0006. The operator chose the agent-writable file (decision 2b) and keeping the repository table (decision 1b) in the Issue intake comment; the remaining choices (D-01 to D-04) are agent-provisional and listed in the run record.
