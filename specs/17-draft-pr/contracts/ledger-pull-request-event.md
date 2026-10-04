# Contract: `pull_request` ledger event

An addition to [Agent Run Ledger schema v1](../../../tools/spec_workflow/ledger-schema.md). `schema_version` stays `1`.

## Event

| Envelope field | Value |
| --- | --- |
| `kind` | `pull_request` |
| `source` | `runner` (required) |
| `event_id` | random hex, one per checkpoint |

`data` fields (`?` = optional):

| Field | Type | Values |
| --- | --- | --- |
| `outcome` | label | `pending`, `created`, `reused`, `failed-retryable`, `blocked-ambiguous`, `blocked-closed`, `blocked-unlinked` |
| `reason?` | label | the reasons in the [data model](../data-model.md#pr-checkpoint-outcome) |
| `issue?` | int | Issue number |
| `pr_number?` | int | PR number |
| `pr_url?` | url | new type: `https://github\.com/[A-Za-z0-9._-]{1,100}/[A-Za-z0-9._-]{1,100}/pull/[1-9][0-9]{0,9}` |
| `matches?` | int | matching PR count for `blocked-ambiguous` and `blocked-closed` |

No field holds free text: base and branch names (for example the two bases of `base-mismatch`) and scope text appear only in the printed line or the PR body, never in the ledger.

Validation additions:

- `outcome` and `reason` are in `ENUM_FIELDS["pull_request"]`.
- `created` and `reused` require `pr_number` and `pr_url`; every other outcome requires `reason`.
- No semantic transition rule: a `pull_request` event may follow any event of the run.
- `ledger.py record` does not offer `pull_request`, like `run`, `step`, `gate` and `snapshot`: only the checkpoint writes it.

## Report

`ledger.py report --run RUN_ID [--json]` adds `pull_request`: the latest event's `data` plus its `observed_at`, or `{"available": false, "reason": "no checkpoint recorded"}`. The text report adds one `pull_request: {...}` line. Aggregate reports are unchanged.

## Compatibility

Additive. Streams written before this feature remain valid. A stream containing a `pull_request` event is rejected by an older pinned Ballast's reader, as with any unknown kind; `ledger-schema.md` states this.
