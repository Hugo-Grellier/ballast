# Implementation Plan: Declare UI states per feature

**Branch**: `feat-142-review-declare-ui-states-per-feature` | **Date**: 2026-10-12 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/142-feature-ui-states/spec.md` (intent agent-provisional, PD-0006, digest in [intent.md](intent.md))

**Risk**: R2, rechecked in [research R9](research.md#r9-risk-recheck-against-the-r2-boundaries). Criterion-linked UI states move from the protected `ballast.toml` to the agent-writable `specs/<feature>/ui-states.toml`, which changes what the packet trusts. Proposed as ADR-0019. **Mode**: Autonomous run `864d9151`. Every decision here is agent-provisional, including the pre-change R2 approval; merging the PR is the only human approval.

## Summary

The acceptance packet reads UI states from two sources and merges them:

1. **Repository entries**: `[[review.ui_states]]` in the protected `ballast.toml`, read from the run's root as today. An entry may no longer carry `criteria`; any `criteria` key, even an empty list, makes the UI section `configuration invalid` with a reason that says to move the entry to the feature's `ui-states.toml`.
2. **Feature entries**: `[[ui_states]]` in `<feature>/ui-states.toml`, read at the PR's head commit through the reads `collect` already makes for every feature file (`git ls-tree`, `git cat-file`). Entries use the existing schema and rules, and their criteria are checked against the head commit's `spec.md` of the same feature only.

`_ui_states` gains a source argument. The source selects the criteria rule (forbidden for the repository, required and checked against the spec for the feature) and prefixes every fixed reason with the failing source (`ballast.toml:` or `ui-states.toml:`). A new pure function parses the feature file's text. A merge function returns either the merged tuple (repository first, at most 50 in total) or one fixed reason, the repository's first when both sources fail. `UiState` and `UiResult` gain an `agent` flag. Feature entries render with the fixed label `agent-declared in ui-states.toml`, both in the UI states section and beside each criterion. Repository entries carry no criteria, so they appear only in the section. A UI result is still attached to `Criterion.ui` only, so no evidence state can change.

Documentation follows: the acceptance packet section of `templates/policies/spec-kit-workflow.md`, a new ADR-0019 that amends ADR-0006's configuration statement, and a one-line amendment note in ADR-0006.

## Technical Context

**Language/Version**: Python ≥ 3.11, standard library only (`tomllib`). `packet.py` is imported at `run.py` startup and runs under `python3 -I -S`.

**Primary Dependencies**: none new. External programs stay #17's resolved `git` and `gh`; no new call is made.

**Storage**: a new agent-writable, committed feature file `specs/<feature>/ui-states.toml`. The PR description holds the derived packet; the archive copy under the Git common directory is unchanged. No ledger or run-record change.

**Testing**: `unittest`, offline, in `tests/test_packet.py`, with the existing `PacketCase` fixture: a temporary Git repository, the scripted `_command` fake for `gh`, and the feature directory written then committed as the head.

**Target Platform**: the qualified 1.0 host (Linux, authenticated `gh`).

**Project Type**: a workflow tool inside the installed standard (`tools/spec_workflow/packet.py`), plus its policy template and an ADR.

**Performance Goals**: at most one extra `git cat-file -s` and one `git cat-file blob` per checkpoint, and only when the feature directory lists `ui-states.toml`. No extra GitHub call.

**Constraints**:
- No new program, GitHub call, fetch, download or execution (FR-014, ADR-0006).
- The feature file is never a protected input and never enters the trust baseline (FR-013).
- Every value from the feature file is rendered inert or used only after validation to build a Ballast link (FR-011).
- No UI state changes a criterion's evidence state (FR-012).
- An invalid source never stops the packet (FR-008).

**Scale/Scope**:
- About 60 changed lines in `packet.py` (`UiState`, `UiResult`, `review_config`, `_ui_states`, a new `feature_ui_states`, a new `merge_ui_states`, `collect`, `_detail`, `_ui_lines`).
- About 150 lines of tests in `tests/test_packet.py`.
- One policy subsection rewrite, one new ADR, one note in ADR-0006.

No NEEDS CLARIFICATION remains. The spec left one choice to the plan: which source is reported when both are invalid. [Research R4](research.md#r4-failure-order-and-the-limit) decides it: the repository table's reason, because it is the operator-owned source and its result is the same on every feature's packet.

## Constitution Check

*Gate before Phase 0, re-checked after Phase 1. Result: **PASS** both times, no violations.*

| Principle | How the design holds it |
| --- | --- |
| 1. Projects own only their files (BL-INV-001) | `ui-states.toml` is a committed feature artifact under `specs/`, like `spec.md`. `packet.py` installs as before into the ignored `.ballast/`. `tools/setup` is unchanged. |
| 2. Nothing executes from a writable checkout (BL-INV-002) | The feature file is data, parsed with `tomllib` by the trusted, already-imported `packet.py`. Nothing in it is executed, imported or used as a command. A `check` value is only compared with check-run names returned by GitHub. |
| 3. Delegated authority (BL-INV-003) | `ballast.toml` stays protected and read from the run's root. An agent gains only the ability to add Ballast-built, labelled links beside its own feature's criteria (SC-005). It cannot change a criterion's state, the packet's structure, a label or another feature's packet. The protected-input list and the trust baseline are unchanged (FR-013). |
| 4. A project picks a version, never a source (BL-INV-004) | Nothing is downloaded or fetched. |
| 5. Postconditions over exit codes (BL-INV-005) | A feature entry is shown only after every rule holds against the head commit's spec; any failure is a fixed `configuration invalid` reason. Evidence states are computed before UI results attach and never read them. |
| 6. Portable, dependency-free tools | Standard library only (`tomllib`). |
| 7. Generic by default | The file name, schema and label are generic; the policy example uses neutral names. |
| 8. Executable evidence | Every AC maps to a test in [quickstart](quickstart.md), including each invalid rule per source, hostile names and the unchanged evidence states. |
| 9. A provisional decision is never human approval (BL-INV-006) | ADR-0019 is marked proposed and agent-provisional until merge. The new label text passes #19's `HUMAN_APPROVAL` guard: it says "agent-declared", never "approved". |

## Architecture Boundaries

- **Affected areas**: the packet `tools/spec_workflow/packet.py` (configuration parsing, collection, rendering of the UI states); the operator policy template `templates/policies/spec-kit-workflow.md`; the ADRs.
- **Contracts and data flow**:
  - `_Step.collect`: `read("spec.md")` → `spec_ids` → `review_config(root)` (repository entries, criteria forbidden) → `read("ui-states.toml")` at head → `feature_ui_states(text, spec_ids, *, present, too_large)` → `merge_ui_states(config, feature)` → `ui_result` per merged state → `Criterion.ui` for feature entries naming that criterion → `Sources.config` and `Sources.ui` → `render` (`_detail`, `_ui_lines`).
  - Sources of truth: `ballast.toml` (operator) for repository-wide screens; `ui-states.toml` at head (agent) for criterion-linked screens; `spec.md` at head for the criterion IDs; GitHub check runs and the head tree for results. The packet stays a derived view.
  - Contracts: [ui-states-file.md](contracts/ui-states-file.md) (file and repository table schema, reasons) and [packet-ui-section.md](contracts/packet-ui-section.md) (rendering). Entities in [data-model.md](data-model.md).
- **Architecture references**:
  - [constitution](../../.specify/memory/constitution.md) BL-INV-002, -003, -006;
  - [ADR-0006](../../docs/adr/0006-review-packet-reads.md) ("the packet's configuration lives in the protected `ballast.toml`");
  - #19 [research R11 and R12](../19-acceptance-packet/research.md), [packet format](../19-acceptance-packet/contracts/packet-format.md#ui-states);
  - [R2 boundaries](../../docs/policies/project/workflow.md#r2-boundaries).
- **Proposed architecture decisions** (agent-provisional here; the merge approves them):
  1. **ADR-0019 Feature-local UI states.** Criterion-linked UI states move from the protected `ballast.toml` to the agent-writable `specs/<feature>/ui-states.toml`, read at the head commit. `[[review.ui_states]]` keeps only criterion-less, operator-owned entries merged with the feature's. Feature entries are labelled agent-declared and never change a criterion's state. It amends ADR-0006's "the packet's configuration lives in the protected `ballast.toml`" to "except criterion-linked UI states, which a feature declares in its own agent-writable file". The packet gains no new program, GitHub call, fetch or authority.

## Repository Impact

| Path | Change |
| --- | --- |
| `tools/spec_workflow/packet.py` | `UiState.agent` and `UiResult.agent` (default `False`). `review_config(root)` drops its `spec_ids` argument and validates repository entries with `_ui_states(value, REPOSITORY)`. `_ui_states(value, source, spec_ids=None)`: the source picks the criteria rule and prefixes each reason. New `feature_ui_states(text, spec_ids, *, present, too_large)` parses the file (top-level key rule, TOML and text errors) and returns `(states, error)`. New `merge_ui_states(config, states, error)` returns a `ReviewConfig` with the merged tuple or one reason, and applies the 50 total limit. `collect` reads `ui-states.toml` with the existing `read` helper and merges before `ui_result`. `ui_result` copies `agent`. `_detail` and `_ui_lines` render the label and omit the empty criteria list for repository entries. Docstrings of `UiState` and `ReviewConfig` updated. |
| `tests/test_packet.py` | `ReviewConfigTests`: the existing invalid cases are rewritten as criterion-less repository entries with the `ballast.toml:` prefix, plus the move error (with `criteria = []` and with IDs). New `FeatureUiStateTests` for AC-001 to AC-016 (see [quickstart](quickstart.md)). `UiStateTests` moves its four criterion-linked entries to the feature file, otherwise unchanged in its results; its section line gains the label. |
| `templates/policies/spec-kit-workflow.md` | Acceptance packet section: the feature file with schema and example, the criterion-less repository table, the merge and 50 total limit, the move error, the agent-declared label, failing-source reasons, and how screenshots are kept current (AC-017, AC-018). The installed `docs/policies/` copy refreshes via `ballast setup`. |
| `docs/adr/0019-feature-local-ui-states.md` | New (ADR-0019, proposed, agent-provisional). |
| `docs/adr/0006-review-packet-reads.md` | One italic amendment note on the "What it does not add" configuration line pointing to ADR-0019, as ADR-0007 does for ADR-0015. Status and decision unchanged. |

Unchanged: `draft_pr.py`, `run.py`, `launcher.py`, `agent.py`, `autonomy.py`, `ledger.py`, `artifacts.py`, `claude-settings.json`, the protected-input list and trust baseline, `specs/19-acceptance-packet/` (completed work is not retrofitted; its packet-format contract is extended by [packet-ui-section.md](contracts/packet-ui-section.md)), and `specs/TECHNICAL-SPEC.md` (it has no acceptance packet configuration statement to amend).

## Feature Artifacts

```text
specs/142-feature-ui-states/
├── intent.md
├── discovery.md
├── spec.md
├── plan.md            # this file
├── research.md        # Phase 0 decisions R1–R9
├── data-model.md
├── contracts/
│   ├── ui-states-file.md
│   └── packet-ui-section.md
├── quickstart.md      # validation scenarios mapped to ACs
├── tasks.md           # next: speckit.tasks
├── decisions.md       # only when implementation discovers a decision
├── reviews/
└── autonomous/record.md
```

## Complexity Tracking

No constitution violation; nothing to justify.
