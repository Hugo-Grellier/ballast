# Data model: Declare UI states per feature

All types live in `tools/spec_workflow/packet.py` and are frozen dataclasses. Only the fields this feature adds or changes are listed; the rest are #19's.

## Feature UI states file (`<feature>/ui-states.toml`)

Agent-writable, committed project data with the authority of `spec.md`. Read only at the PR's head commit. Format and rules: [contracts/ui-states-file.md](contracts/ui-states-file.md).

| Field | Type | Rule |
| --- | --- | --- |
| `ui_states` | array of tables | Optional. The only allowed top-level key. Absent: the file adds no entries. |

## Repository UI state (`[[review.ui_states]]` in `ballast.toml`)

Operator-owned, protected, read from the run's root. Same entry fields as a feature entry except `criteria`, which is forbidden.

## `UiState` (one validated entry)

| Field | Type | Change | Notes |
| --- | --- | --- | --- |
| `name` | `str` | — | 1-80 characters; agent-written when `agent`. Rendered through `inert`. |
| `criteria` | `tuple[str, ...]` | now empty for repository entries | Feature entries: non-empty, each `AC-NNN` defined by the head commit's `spec.md`. |
| `path` | `str \| None` | — | Safe repository-relative path. Exactly one of `path`, `check`. |
| `check` | `str \| None` | — | 1-100 printable characters. |
| `agent` | `bool` | **new**, default `False` | `True` for entries from `ui-states.toml`. Drives the label only. |

## `UiResult` (an entry's result at head)

| Field | Type | Change | Notes |
| --- | --- | --- | --- |
| `name`, `criteria`, `result`, `path`, `run` | — | — | As #19. `result` is `present`, `passed`, `failed`, `not run`, `not run (in progress)` or `missing`. |
| `agent` | `bool` | **new**, default `False` | Copied from `UiState.agent` by `ui_result`. |

## `ReviewConfig` (in `Sources.config`)

Holds the merged view after `collect`; before the merge it holds the repository entries only.

| Field | Type | Change | Notes |
| --- | --- | --- | --- |
| `ui_states` | `tuple[UiState, ...] \| None` | now the merged tuple | `None` when neither source declares UI states (research R5). Repository entries first, then feature entries, file order. At most 50. |
| `ui_error` | `str \| None` | reasons now carry a source prefix | One fixed reason from [the reason list](contracts/ui-states-file.md#fixed-reasons). When set, `ui_states` is `None`. |
| `openapi`, `api_error` | — | — | Unchanged. |

## `Criterion.ui`

Unchanged type. Holds the `UiResult`s whose `criteria` contain the criterion's ID, which after this change are feature entries only. `Criterion.state` and `reason` are computed before and never read it (FR-012).

## Functions

| Function | Input | Output | Notes |
| --- | --- | --- | --- |
| `review_config(root)` | run root | `ReviewConfig` | Drops the `spec_ids` argument. Repository entries via `_ui_states(value, "ballast.toml")`. |
| `_ui_states(value, source, spec_ids=None)` | raw `ui_states` value | `(states \| None, reason \| None)` | Source-dependent criteria rule and reason prefix (research R2, R3). |
| `feature_ui_states(text, spec_ids, *, present, too_large)` | head-commit text of the file | `(states \| None, reason \| None)` | Pure. Absent file → `(None, None)`. File-level reasons, then `_ui_states(..., "ui-states.toml", spec_ids)` with `agent=True`. |
| `merge_ui_states(config, states, error)` | repository config, feature result | `ReviewConfig` | Applies research R4's order and the 50 total limit. |

## State of the UI section

```text
neither source declares ui_states              -> "UI states: not configured."
repository invalid                             -> "configuration invalid (ballast.toml: …)"
else feature file invalid                      -> "configuration invalid (ui-states.toml: …)"
else more than 50 in total                     -> "configuration invalid (more than 50 UI states)"
else merged tuple, empty                       -> "None (0)."
else merged tuple                              -> one line per entry (label on feature entries)
```
