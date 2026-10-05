# Contract: `acceptance_packet` ledger event and `verification.commit`

Additions to [Agent Run Ledger schema v1](../../../tools/spec_workflow/ledger-schema.md). `schema_version` stays `1`, the pattern of #17's `pull_request` event.

## New value type

`oid`: a Git object ID, `[0-9a-f]{40}` or `[0-9a-f]{64}`.

## `acceptance_packet` event

| Envelope field | Value |
| --- | --- |
| `kind` | `acceptance_packet` |
| `source` | `runner` (required) |

`data` (`?` = optional):

| Field | Type | Values |
| --- | --- | --- |
| `outcome` | label | `published`, `updated`, `unchanged`, `pending`, `failed-retryable` |
| `reason?` | label | `PACKET_REASONS[outcome]` ([research R17](../research.md#r17-outcomes-reasons-and-remedies)) |
| `pr_number?` | int | |
| `head?`, `base?`, `feature_version?` | oid | |
| `packet_digest?` | sha | SHA-256 of the masked packet text |
| `shortened?` | bool | |
| `verified?`, `failed?`, `not_run?`, `stale?`, `missing?` | int | criterion counts |

Validation:

- `outcome`, and `reason` per outcome, are in `ENUM_FIELDS["acceptance_packet"]`.
- `published`, `updated` and `unchanged` require `pr_number`, `head`, `base`, `feature_version`, `packet_digest` and all five counts. `pending` and `failed-retryable` require `reason`. `head` and `base` are kept when they are known.
- The kind is in `RUNNER_ONLY`: `ledger.py record` does not offer it.
- No transition rule: it may follow any event of the run.
- No free-text field. Remedies, names and exception details appear only in the printed line.

## `verification.commit`

`verification` gains `commit?` (`oid`). `ledger check` sets it to `HEAD`'s ID only when the checkout's implementation fingerprint equals `commit_tree(HEAD)`, meaning the checked code is exactly that commit's. Older events without it stay valid.

## Report

`ledger.py report --run RUN_ID [--json]` adds `acceptance_packet`: the latest event's `data` plus `observed_at`, or `{"available": false, "reason": "no packet recorded"}`. The text report adds one `acceptance_packet: {...}` line. Aggregate reports are unchanged.

## Fingerprint functions

- `implementation_tree(root)`: private index seeded with `read-tree HEAD` when `HEAD` exists, then `add -A -- . :!specs`, `rm -r --cached -q --ignore-unmatch -- specs` and `write-tree`, giving the SHA-256 of the tree ID. On a clean checkout it equals `commit_tree(root, HEAD)`.
- `commit_tree(root, commit, git=_git)`: private index, `read-tree <commit>`, the same `rm` and `write-tree`, giving the SHA-256 of the tree ID. It never touches the worktree or the user's index, and runs no filter or hook.
- `spec_criteria(text) -> list[tuple[str, str, int]]`: `(AC-NNN, title text, line)` for list items `- **AC-NNN**:` and `N. **AC-NNN**:`, first occurrence, in document order. `_approved_spec_ids` uses it.

## Compatibility

Additive. Streams written before this feature remain valid. As with any unknown kind, a stream containing `acceptance_packet` is rejected by an older pinned Ballast; `ledger-schema.md` states this. Snapshots recorded before the `implementation_tree` change no longer match a re-snapshot of the same tree, so evidence they bind reads `stale` and needs re-checking once. The quickstart and release notes say so.
