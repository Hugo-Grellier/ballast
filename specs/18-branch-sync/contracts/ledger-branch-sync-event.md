# Contract: `branch_sync` ledger event

An addition to [Agent Run Ledger schema v1](../../../tools/spec_workflow/ledger-schema.md). `schema_version` stays `1`. The kind is additive, as `pull_request` was: an older pinned Ballast rejects a stream that contains it, as with any unknown kind.

## Event

| Envelope field | Value |
| --- | --- |
| `kind` | `branch_sync` |
| `source` | `runner` (required; `ledger.py record` does not offer the kind) |
| `event_id` | random hex, one per check |

`data` fields (`?` = optional):

| Field | Type | Values |
| --- | --- | --- |
| `outcome` | label | `up-to-date`, `synchronized`, `blocked` |
| `cause?` | label | `busy`, `git-unavailable`, `in-progress`, `wrong-branch`, `unknown-base`, `fetch-failed`, `not-feature-branch`, `diverged`, `dirty`, `conflict`, `push-failed`, `protected-input`, `internal-error` |
| `base_ref?` | ref | new type, the pattern in the [data model](../data-model.md#feature-identity-pin) |
| `base_before?` | commit | new type: 40 or 64 lowercase hex |
| `base_after?` | commit | |
| `head_before?` | commit | |
| `head_after?` | commit | |
| `pushed?` | bool | |
| `fast_forwarded?` | bool | HEAD was fast-forwarded (AC-015, the base branch, or no feature commits) |
| `recovered?` | bool | a pending write-ahead record from an earlier invocation was completed (research R5) |
| `recovered_from?` | run ID | the run that wrote that record (`RUN_ID_PATTERN`); it may differ from this run (N-01) |
| `retryable?` | bool | `push-failed` only |
| `overlap?` | int | overlapping file count (R11) |
| `stale_plan?` | bool | |
| `stale_review?` | bool | |

Validation additions:

- `outcome` and `cause` are in `ENUM_FIELDS["branch_sync"]`.
- `blocked` requires `cause`. `up-to-date` and `synchronized` forbid `cause` and require `base_ref`, `base_after`, `head_before` and `head_after`. `synchronized` also requires `pushed`.
- `retryable` is allowed only with `cause == "push-failed"`.
- `recovered` is allowed only with `outcome == "synchronized"`; `recovered_from` only with `recovered` true.
- A blocked `continue` records its event in the source run's stream, not under the continuation's ID (research R1, N-07). A blocked `start` does record under its own new run ID: that run was started, so a stream holding only one `branch_sync` event is valid and `report` handles it.
- No semantic transition rule: the event may follow any event of the run.

No field holds a path, remedy, Git output or free text. Overlapping paths live in `branch-sync/<event_id>.json` beside the stream ([data model](../data-model.md#stale-evidence-record)). The base name is the only name recorded, under the strict `ref` type, because FR-009 requires the base reference.

## Report

The run report adds `branch_sync`: the latest event's `data` plus its `observed_at`, or `{"available": false, "reason": "no check recorded"}`. The text report adds one `branch_sync:` line. Aggregate reports are unchanged.
