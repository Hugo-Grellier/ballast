# Contract: launcher `trust`, `status --json` and doctor

Owners: `tools/spec_workflow/launcher.py` (baseline, provenance, reviewed repositories, status) and `tools/ballast` (doctor). Data shapes: [data-model.md](../data-model.md).

## `launcher.record_baseline`

```python
record_baseline(root: Path, state: Path, inputs: dict[str, str], *,
                source: Literal["setup", "trust"], reference: dict | None = None) -> None
```

- Serializes `inputs` exactly as today: `json.dumps(inputs, indent=1).encode()`.
- Writes `trusted-source.json` (bound to the digest of those bytes), then `trusted.json`; each through a temporary file opened with `O_NOFOLLOW | O_CREAT | O_TRUNC`, mode 0600, `fsync`, `rename`, directory `fsync`.
- Raises `OSError` on failure; the caller reports it. It does not decide eligibility.

## `ballast trust` (launcher `_trust`)

Unchanged: refusals (tamper marker, in-progress marker, not installed, lock, unfinished setup), the digest set and the output line `trusted N workflow inputs for ROOT`. Changed:

1. Writes through `record_baseline(..., source="trust")`, so a provenance record naming `trust` is written with the baseline.
2. Then adds the trusted `ballast.toml`'s `[github] repository`, case-folded, to `reviewed-repositories.json` when it is a valid `OWNER/NAME`; nothing otherwise. A failure to update that record is reported on stderr as a warning (`could not record OWNER/NAME as reviewed: <cause>; setup will not trust its fresh checkouts`) and does not change the exit status: the baseline itself was recorded.

## `status --json`

```json
{"installed": true, "refusal": null, "baseline_source": "setup"}
```

- `installed` and `refusal`: unchanged, computed exactly as today.
- `baseline_source`: `"setup"` | `"trust"`, per the data-model reading rule, present only once a baseline exists (the key is omitted without one, so the output for a checkout with no baseline stays exactly as before: decisions.md DEC-0007). Computed without the checkout lock and without writing; an `OSError` from `state_dir` omits it.
- The comparison in `_trust_refusal` does not read provenance (FR-015).

## Doctor `trust` check (`tools/ballast`)

Status classification (`passing`, `missing`, `inconclusive`) and remedies are unchanged. The detail gains the source when `baseline_source` is a string:

| Launcher answer | Detail |
| --- | --- |
| accepted, `setup` | `the launcher accepts this checkout; baseline recorded by ballast setup` |
| accepted, `trust` | `the launcher accepts this checkout; baseline recorded by ballast trust` |
| refused, source known | `launcher will refuse: <refusal>; the current baseline was recorded by ballast setup` (or `ballast trust`) |
| key absent (no baseline, or an older launcher) | today's text |

Doctor never reads `trusted.json`, provenance or the reviewed record itself (ADR-0002, FR-014).
