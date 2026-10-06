# Contract: ledger additions (schema v1)

Implements FR-007, AC-011 to AC-017. Field definitions are in [data-model.md](../data-model.md#ledger-additions-schema-v1-additive).

## Validation (`ledger.py`)

- `ENUM_FIELDS["route"]`: `route_source` adds `fallback`; new enums `failure_cause`, `fallback`, `fallback_reason`.
- `FIELDS["route"]` adds `failure_cause?`, `fallback?`, `fallback_reason?` (`label`).
- `validate` cross-field rules: `fallback_reason` needs `fallback: refused`; `fallback: refused` needs `fallback_reason`; `route_source: fallback` forbids `failure_cause` and `fallback`.
- `route` stays recordable by `ledger.py record`; the wrapper writes with source `runner`.
- The schema version is unchanged. An older pinned Ballast rejects a stream holding the new value or fields, as with every earlier additive change. `ledger-schema.md` gains one paragraph saying so.

## Events per case

| Case | Events (source `runner`) |
| --- | --- |
| setting off, any failure | none (as today) |
| recoverable failure on a draft-retry attempt | primary `route` with `failure_cause` and no `fallback` field; no fallback is considered |
| recoverable failure, fallback refused | `route` {stage, provider: primary, route_source: operator-choice, attempt n, cause_id, outcome: mechanical-failure, failure_cause, fallback: refused, fallback_reason} |
| recoverable failure, fallback selected and succeeded | primary `route` (fallback: selected) + fallback `route` {provider: ollama, model, route_source: fallback, attempt n+1, cause_id, outcome: success} + `usage` when reported |
| fallback failed | as above with the fallback `outcome` `mechanical-failure`, `rejected` (refused draft) or `incomplete` (timeout, interruption) |
| step limit exhausted before the fallback | primary `route` (fallback: selected), then the existing limit refusal; no fallback `route` |

Repeating the write of any of these with the same event ID is a no-op (`ledger.append` compares content), so a re-run cannot duplicate them (AC-014).

## Report

`ledger.report` already lists `actual_routes` and counts `route_sources`. It now also counts `fallback` and shows the refusal reasons in `actual_routes`. The text report needs no new line.

Review provenance (AC-016): when a run holds a `route` event with source `runner`, `route_source: fallback`, `outcome: success` and a stage that is a `ballast-review` command, `cross_provider_reviews` is 0 for that run, every `review_provider_availability` and `outcome.reviews` item has `cross_provider: false`, and `routing.fallback_reviews` counts those routes. The rule covers human-gated and Autonomous runs alike. It is run-wide and conservative: it can under-count a genuine cross-provider review in that run, but it never claims one on the fallback's basis. Usage totals follow the existing rule: unavailable when any recorded route attempt lacks a counter.
