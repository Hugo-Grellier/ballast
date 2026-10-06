# Data model: Setup trusts a checkout it just installed

All records live in operator state under `$XDG_STATE_HOME/ballast/` (default `~/.local/state/ballast/`), which `launcher.state_dir` refuses when it resolves inside the checkout or an agent temp root. `<state>` is the per-checkout directory `ballast/<sha256(root)[:16]>/`. Decisions are in [research.md](research.md).

## Trust baseline: `<state>/trusted.json` (unchanged)

- **Shape**: flat JSON object, protected-input path → `sha256` hex digest or `link:<target>`; serialized as `json.dumps(inputs, indent=1)` with no trailing newline, exactly as `ballast trust` writes it today.
- **Writers**: `launcher.record_baseline` only, called by `ballast trust` (operator) and by `setup_trust` from `ballast setup` or a preparation when eligible. Write is now atomic (R12); the bytes are unchanged.
- **Readers**: the launcher's comparison (unchanged, FR-015); `setup_trust` reads the checkout's own baseline for the operator-baseline alternative (R7). Preparation removes one left at a reused path before installing and never reads it.

## Baseline provenance: `<state>/trusted-source.json` (new)

| Field | Type | Rule |
| --- | --- | --- |
| `schema` | int | `1` |
| `source` | `"setup"` \| `"trust"` | who recorded the baseline |
| `baseline` | string | `sha256:` + hex digest of the exact `trusted.json` bytes it describes |
| `recorded` | string | UTC ISO-8601, seconds |
| `reference` | object, `setup` only | `{"kind": "default-branch", "repository": "owner/name", "branch": str, "commit": hex}` or `{"kind": "operator-baseline"}` |

- **Bound**: `baseline` equals the digest of the current `trusted.json` bytes.
- **Reported source** (`status --json` `baseline_source`): no readable `trusted.json` → `null`; readable, `source == "setup"` and bound → `"setup"`; anything else (missing, unreadable, unbound, unknown schema, `trust`) → `"trust"` (FR-013, AC-024).
- **Operator-recorded for eligibility** (R7): no provenance file, or readable, `source == "trust"` and bound. Unreadable or unbound is **not** operator-recorded (fail closed).
- **Write order**: provenance first, then `trusted.json`, each atomic (R12). Removed together with the baseline by preparation at a reused path and by setup's post-write recheck (R3).

## Reviewed repositories: `ballast/reviewed-repositories.json` (new, machine-wide)

| Field | Type | Rule |
| --- | --- | --- |
| `schema` | int | `1` |
| `repositories` | list of string | `owner/name`, case-folded, sorted, unique; each part matches the `[github] repository` name rule |

- **Writer**: the launcher's `_trust` only, after writing the baseline: adds the `[github] repository` of the trusted `ballast.toml` snapshot when valid; read-modify-write under `flock` on `ballast/reviewed-repositories.lock`, atomic replace, mode 0600.
- **Readers**: `setup_trust` (setup and preparation). Missing, unreadable, unknown schema or malformed → empty.
- **Holds no digests** and no checkout paths (FR-005, FR-010).

## Installation record: `<state>/installation.json` (read only)

Written by setup as today (`schema`, `ref`, `fingerprint`, `entries`, `files`, `executable`). `setup_trust` reads it through `launcher.read_record` and requires its fingerprint to equal the stamp and this setup's fingerprint (R4).

## Operator-state runs: `<state>/runs/<run-id>/run.json` (read only)

`status` ∈ `active`, `stopped` (unfinished) or `completed`, `published`, `continued` (finished). Unreadable or unknown status counts as unfinished (R11).

## Eligibility (computed, never stored)

Evaluated once per setup or preparation, in this order; the first failing condition is the reason reported. Network access happens only at step 9.

| # | Condition | Ineligible reason (fixed phrase) | Spec |
| --- | --- | --- | --- |
| 1 | `STANDARD` is outside the checkout | setup runs from this checkout, which agents can write | FR-020 |
| 2 | no `BALLAST_TAMPERED`, no in-progress marker | an agent step's marker exists | FR-007, AC-018, AC-019 |
| 3 | no saved run state in the checkout; no unfinished operator-state run | saved run state shows agents ran here | FR-007, AC-020 |
| 4 | snapshot taken; config bytes read once and equal to the snapshot | ballast.toml or the constitution is not a regular file under 256 KiB | R3 |
| 5 | every other protected input equals the current installation record, and vice versa | `<path>` was not written by setup | FR-002, AC-012 |
| 6 | linked worktree pointer names a worktree entry of its repository | the .git pointer does not name a worktree of this repository | FR-006, AC-013 |
| 7 | both config files committed and unchanged from `HEAD` | `<path>` has uncommitted changes | FR-003, AC-010 |
| 8a | both equal the previous operator-recorded baseline → **eligible** (`operator-baseline`) | — | FR-003, AC-004 |
| 8b | `[github] repository` valid and in the reviewed-repositories record | the pinned repository is not one you trusted on this machine / ballast.toml names no valid [github] repository | FR-005, AC-016 |
| 9 | default branch observed and both blob IDs equal → **eligible** (`default-branch`) | could not read `<repo>`'s default branch: `<cause>` / differs from `<repo>`'s default branch and from your last trusted baseline | FR-003, FR-004, AC-001, AC-011, AC-014, AC-015 |

## State transitions of a checkout's baseline

```text
                 setup/prepare eligible             any protected input changes
 (none) ─────────────────────────────▶ setup ────────────────────────────▶ setup (stale: launcher refuses)
   │                                     ▲  │ ballast trust                     │ setup/prepare eligible
   │ ballast trust                       │  ▼                                    ▼
   └──────────────────────────────▶ trust ◀──────────── ballast trust ──── setup (fresh)
                                       │  setup eligible, inputs unchanged → unchanged (FR-011)
                                       │  setup eligible, inputs changed   → setup
                                       │  setup ineligible                 → unchanged (FR-008)
 preparation at a reused path: any → (none) → setup if eligible (AC-008)
```
