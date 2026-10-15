# ADR-0019: A feature declares its criterion-linked UI states in its own file

- Status: proposed (2026-10-12, with the change for [#142](https://github.com/Hugo-Grellier/ballast/issues/142)). Agent-provisional in Autonomous run `864d9151`; merging the PR is the human approval that accepts it.
- Superseded by [ADR-0024](0024-ballast-2-migration.md) (2026-10-15, Ballast 2.0). Kept unchanged as the v1.x record.
- Risk: R2 (what the acceptance packet trusts).
- Feature: [142-feature-ui-states](../../specs/142-feature-ui-states/spec.md); research [R1 to R9](../../specs/142-feature-ui-states/research.md); operator decisions 1b and 2b in the Issue intake scope comment.
- Amends: [ADR-0006](0006-review-packet-reads.md), "the packet's configuration lives in the protected `ballast.toml`".

## Context

The acceptance packet reads UI states from `[[review.ui_states]]` in the protected `ballast.toml`, and each entry names the criteria it illustrates. Criterion IDs belong to one feature's spec, but the table is shared by every feature of the repository: an entry written for one feature names criteria another feature's spec does not define, and the packet of that other feature reads `configuration invalid`. Only the operator can edit the table, so an agent implementing a feature cannot declare the screens for its own criteria.

## Decision

- **Feature file.** Criterion-linked UI states live in `specs/<feature>/ui-states.toml`, an agent-writable feature artifact committed like `spec.md`. Its only top-level key is `ui_states`, an array of tables with `name`, a non-empty `criteria` list and exactly one of `path` or `check`.
- **Read at head, checked against its own spec.** The packet reads the file at the PR's head commit only, through the local Git reads it already makes for every feature file, and checks its criteria against the same commit's `spec.md` of that feature and nothing else. Another feature's file is never read.
- **Repository table.** `[[review.ui_states]]` in `ballast.toml` stays operator-owned and holds only criterion-less, repository-wide entries. A `criteria` key there, even an empty list, makes the UI section `configuration invalid` with a reason that says to move the entry. Repository entries are listed first, then the feature's, at most 50 in total.
- **Failure.** Each reason names its source (`ballast.toml:` or `ui-states.toml:`); the repository's is shown when both fail. An invalid source fails only the UI section; the rest of the packet is published.
- **Inert and labeled.** Feature entries are rendered with the fixed label `agent-declared in ui-states.toml`, in the UI states section and beside each criterion they name. Their names are rendered inert. A UI state never changes a criterion's evidence state.
- **Not protected.** The file is not a protected input and not in the trust baseline (decision 2b).

## What it does not add

- No new program, GitHub call, fetch or download: the file is read with the `git cat-file` calls ADR-0006 already lists.
- No agent authority beyond adding labeled, Ballast-built links beside its own feature's criteria: an agent cannot change a criterion's state, the packet's structure, a label or another feature's packet.

## Consequences

- Each feature's packet shows only its own criterion-linked screens, and one feature's entries no longer invalidate another feature's packet.
- A project that declared criteria in `[[review.ui_states]]` reads `configuration invalid` until it moves those entries to the feature's `ui-states.toml`.
- A merge reviewer sees which UI links an agent declared and judges them like any other agent-written artifact.

## Rejected alternatives

- Keeping criterion-linked entries in `ballast.toml` and checking each against every feature's spec: the operator still edits the protected file for every feature's screens.
- Removing `[[review.ui_states]]` (decision 1b): repository-wide screens such as a home page have no feature to belong to.
- Protecting the feature file or adding it to the trust baseline (decision 2b): every screenshot change would need `ballast trust`, and the entries change no evidence state.
- Accepting `criteria = []` in the repository table: one spelling is clearer, and accepting it later breaks no configuration.
