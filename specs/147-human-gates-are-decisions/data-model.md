# Data model: Human gates are decisions, not command relays

All records live in operator state (`$XDG_STATE_HOME/ballast/...`), where no agent can write. Changes are additive: every record written before this feature stays valid, and the launcher's baseline comparison format (`trusted.json`) does not change. Decisions are in [research.md](research.md).

## Trust baseline provenance (`<state>/trusted-source.json`)

| Field | Type | Rule |
| --- | --- | --- |
| `schema` | `1` | Unchanged. |
| `source` | `"trust" \| "setup" \| "default-branch"` | `default-branch` is new and written only by `setup --refresh` (R4). |
| `baseline` | `sha256:<hex>` | Bound to the exact `trusted.json` bytes. Unchanged. |
| `recorded` | ISO-8601 UTC | Unchanged. |
| `repository` | `owner/name`, case-folded | New. The `[github] repository` of the reviewed `ballast.toml`. Written by `trust` (when the trusted `ballast.toml` names a valid one), by `setup` and by `default-branch`. Absent in legacy records. |
| `reference` | object | `setup`: as today. `default-branch`: `{repository, branch, commit}` of the observed tip. |

**Reading rules**

- `baseline_source()` returns `trust` when the record is missing, unreadable or unbound, as today.
- `operator_baseline()` accepts only `source == "trust"`. This is unchanged, so a refreshed baseline is not an "operator baseline" for ADR-0015's offline alternative.
- `refresh_repository()` (new) returns `repository` only from a bound record. Otherwise it returns `None`, which makes the checkout ineligible (R2, step 2).

## Reviewed repositories (`$XDG_STATE_HOME/ballast/reviewed-repositories.json`)

The schema is unchanged. The record gains a second writer: a successful refresh adds the new (`ballast.toml`, constitution) digest pair under the same repository key (R4). The refresh never adds a repository name.

## Refresh eligibility (transient, not stored)

```text
changed  = {p : baseline[p] != current[p]}
installed(p)  : p under .ballast/spec_workflow, or an installed .specify path
tracked(p)    : regular file at HEAD, working bytes == HEAD blob (hardened plumbing)
eligible      = no markers
              ∧ provenance.repository == casefold(ballast.toml [github] repository)
              ∧ repository ∈ reviewed record
              ∧ ∀p ∈ changed: installed(p) ∨ tracked(p)
              ∧ observe(default branch) ok
              ∧ ∀p ∈ changed ∩ tracked: ls-tree(tip, p) is a regular blob == blob_id(bytes)
recordable    = eligible ∧ install ok
              ∧ ∀p ∈ snapshot: installed(p) → record.files[p] == snapshot[p]
                               tracked-changed(p) → observed blob
                               otherwise → previous baseline
              ∧ claude-settings.json == generated_settings(standard, ballast.toml)
```

The first false term is reported (`not refreshed: <reason>`), and nothing is written.

## Human decision (`runs/<run>/human-decisions.jsonl`, `HD-NNNN`)

| Field | Change |
| --- | --- |
| `by` | `"operator"` (terminal) or `"relayed"` (new). |
| `relayed_by` | New. Required when `by == "relayed"` and forbidden otherwise. It must match `[A-Za-z0-9][A-Za-z0-9._:-]{0,79}` and not match `HUMAN_APPROVAL`. |
| `ref` | For a relayed `gate-approval` it is exactly `relayed approve GATE`. A relayed record never quotes chat text. |

**Validation**

- `validate_human_decision` accepts both `by` values with the field rule above.
- A `gate-approval` or `gate-rejection` with `by == "relayed"` is valid only in a run whose effective mode at that entry is `chat`. A `gate-rejection` is never relayed (R8).
- The kinds `gate-rejection` and `decision-resolution` are refused with `relayed`.
- A relayed `block-resolution` of a block whose category is outside `actor.DECISION_FREE` (`upstream-sync`, `interrupted`, `postcondition`) must carry a non-empty `ref` that passes the `HUMAN_APPROVAL` guard (D-08, AC-028).

**Batch writing**: `append_human_decisions(run_dir, [d1..dn])` assigns consecutive IDs, chains each line to the previous one, and writes the whole file atomically (`write_atomic`). Either every line exists or none does.

## Mode history entry (`run.json` `mode_history[]`)

| Field | Change |
| --- | --- |
| `by` | `"operator"` or `"relayed"`, same rule. |
| `relayed_by` | Same rule as above. |

`_validate_mode_history` accepts both. The existing transition rules are unchanged (`NEVER_RAISED`, lower and switch only). A `switch` entry (`ballast run mode`) must be `operator` (R8).

## Actor (transient, `actor.py`)

```text
resolve(options, command) ->
  --relayed-by S given          -> Actor("relayed", S)   # validated, then mode matrix
  stdin.isatty ∧ stdout.isatty  -> Actor("operator")
  otherwise                     -> Refused("without a terminal, name the relaying agent session with --relayed-by")
allowed(command, mode, actor, block=None, ref=None)
                                -> matrix in contracts/cli.md; a relayed resume or
                                   continue of block.category ∉ DECISION_FREE needs ref
```

## Block categories and wrapper exits

| Source | Today | New |
| --- | --- | --- |
| A failed `validate-implementation`, category `postcondition` | Re-entry at `validate-implementation` | Re-entry at `implement` (R12) |
| An agent CLI usage-limit signature, wrapper confirmed stopped | `postcondition` ("step X failed") | `EXIT_USAGE_LIMIT` → `interrupted`, resumable (R13) |
| A wrapper that died during a step | `unfinished-step` | Unchanged |
| Branch sync recheck: protected-input change | Recovery: "setup, then trust" | Recovery: rerun the same command, which refreshes or else names `trust` (R3) |

## Chat gate approval state

`approval_state` is unchanged (`pending`, `current`, `stale`, `rejected`). Batch selection uses `pending ∪ stale`. Status rendering appends `, relayed by agent session S` to `approved, current (HD-x)` lines whose HD is relayed.
