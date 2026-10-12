# Contract: UI states sources

Two sources declare UI states for a PR's acceptance packet. This contract extends #19's `[review]` configuration ([research R11, R12](../../19-acceptance-packet/research.md)).

## Feature file: `specs/<feature>/ui-states.toml`

Committed in the feature directory, agent-writable, read at the PR's head commit only.

```toml
[[ui_states]]                          # repository and feature entries: at most 50 in total
name = "Login error"                   # 1-80 characters
criteria = ["AC-003"]                  # non-empty; AC-NNN IDs this feature's spec.md defines
path = "docs/screens/login-error.png"  # a committed file, or instead:
# check = "ui / login-error"           # a GitHub check run on the head commit
```

- Top-level keys: only `ui_states`. A file without it adds no entries.
- `ui_states`: an array of tables.
- Entry keys: `name`, `criteria`, and exactly one of `path` or `check`; no other key.
- `criteria` is checked against the `AC-NNN` IDs of the same commit's `<feature>/spec.md`, and nothing else.
- Not protected; not in the trust baseline; changing it never fails a step.

## Repository table: `[[review.ui_states]]` in `ballast.toml`

Protected, operator-owned, read from the run's root as today.

```toml
[[review.ui_states]]
name = "Home page"
check = "ui / home"                    # or path = "docs/screens/home.png"
```

- Entry keys: `name`, and exactly one of `path` or `check`. **No `criteria` key**, not even `criteria = []`.
- Shown on every feature's packet, merged with that feature's entries, never beside a criterion.

## Fixed reasons

The UI section reads `UI states: configuration invalid (<reason>).` with exactly one of these reasons. Sources are checked in this order, and the first failure is shown:

| Order | Reason | When |
| --- | --- | --- |
| 1 | `review is not a table` | `review` in `ballast.toml` is not a table (unchanged, shared with the API section). |
| 1 | `ballast.toml: ui_states is not a list of tables` | |
| 1 | `more than 50 UI states` | `review.ui_states` alone has more than 50 entries. |
| 1 | `ballast.toml: UI state criteria belong in the feature's ui-states.toml` | An entry has a `criteria` key. Checked before the other entry rules. |
| 1 | `ballast.toml: UI state has an unknown key` | |
| 1 | `ballast.toml: UI state name must be 1-80 characters` | |
| 1 | `ballast.toml: UI state needs exactly one of path or check` | |
| 1 | `ballast.toml: UI state path is not a safe repository path` | |
| 1 | `ballast.toml: UI state check must be 1-100 characters` | |
| 2 | `ui-states.toml: larger than 1 MiB` | Over `FILE_LIMIT`. |
| 2 | `ui-states.toml: not UTF-8 text` | Listed at head but its blob is not readable UTF-8 text. |
| 2 | `ui-states.toml: not valid TOML` | `tomllib` rejects it. |
| 2 | `ui-states.toml: has a top-level key other than ui_states` | |
| 2 | `ui-states.toml: ui_states is not a list of tables` | |
| 2 | `more than 50 UI states` | `ui_states` alone has more than 50 entries. |
| 2 | `ui-states.toml: UI state has an unknown key` | |
| 2 | `ui-states.toml: UI state name must be 1-80 characters` | |
| 2 | `ui-states.toml: UI state criteria must be AC-NNN IDs` | Missing, empty, or not `AC-NNN`. |
| 2 | `ui-states.toml: UI state needs exactly one of path or check` | |
| 2 | `ui-states.toml: UI state path is not a safe repository path` | |
| 2 | `ui-states.toml: UI state check must be 1-100 characters` | |
| 2 | `ui-states.toml: UI state names a criterion the spec does not define` | Includes a spec with no criteria. |
| 3 | `more than 50 UI states` | Both sources valid, more than 50 entries together. |

Within one entry, rules apply in the table's order. A reason never contains a value from either file or the feature path.

An unreadable or invalid `ballast.toml` as a whole is unchanged from #19: it reads as no `[review]` table.
