# Contract: configuration and start flag

## `ballast.toml`

```toml
[autonomous]
completion = "ready"              # "draft" (default) or "ready"
completion_max_severity = "low"   # "low" (default), "info" or "none"
```

- Missing table or missing key: `completion` behaves as `draft`, and `completion_max_severity` as `low`. Output, ledger and run record are identical to the previous release (FR-001, FR-013).
- `completion` with any other value, including different case such as `"Ready"`: stderr `ballast: ignored [autonomous] completion 'Ready': cannot widen eligibility`. The run's configured value is `draft` (FR-002).
- `completion_max_severity` with any other value: stderr `ballast: ignored [autonomous] completion_max_severity 'medium': cannot widen eligibility`. The threshold stays `low` (FR-006).
- A non-string value is treated the same way as an unknown value. It is not a refusal, so a typo never blocks an otherwise eligible run.
- `ballast.toml` is a protected input. Changing it needs `ballast trust`. The run reads it once at start (and on `--refresh-policy`, only from the `ballast trust` baseline). A checkout copy an agent changes is never read for this purpose (FR-004, AC-013).
- `completion` is the one `[autonomous]` key that can let the runner do more than today. It is documented as an operator opt-in that ADR-0019 records, not as a widening of eligibility. It never makes an ineligible start eligible.

## `ballast run start --mode autonomous --completion draft|ready`

| Given | Result |
| --- | --- |
| `--completion` without `--mode autonomous` | refused: `--completion needs --mode autonomous` (exit as other start refusals) |
| a value other than `draft` or `ready` | refused: `--completion must be draft or ready` |
| given twice | refused: `--completion given twice` (existing `_split_mode` rule) |
| `ready`, configured value not `ready` | refused before eligibility checks write anything and before any agent step: `--completion ready cannot widen ballast.toml [autonomous] completion (draft)` (AC-015) |
| `draft`, configured `ready` | run starts, effective `draft`, `completion_flag = "draft"` in the snapshot (AC-016) |
| `ready`, configured `ready` | run starts, effective `ready` |
| `draft`, nothing configured | run starts, effective `draft`, snapshot records the flag, nothing is reported (R4) |

`ballast run resume` and `ballast run continue` refuse `--completion` with their existing messages. `--completion` joins `RESUME_FLAGS`, so the resume refusal names the recorded-at-start rule.

## `ballast run resume RUN_ID --refresh-policy`

It re-reads `completion` and `completion_max_severity` from the `ballast trust` baseline, keeps the recorded start flag, and recomputes the effective value (AC-018). The existing "Re-read [autonomous]…" stdout line is unchanged. The recorded `previous`/`current` snapshots show the change.

A refresh resume also records a `block-resolution` human decision, so condition (11) keeps that run's PR a Draft. The refresh still changes the recorded policy (research R11 and data-model).
