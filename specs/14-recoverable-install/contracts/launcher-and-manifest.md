# Contract: launcher refusals, run format and `tools/cli.toml` additions

## Launcher (`tools/spec_workflow/launcher.py`)

For `run`, `ledger` and `intake`, in this order, each refusal exiting 2 with `ballast: refusing: <reason>`:

1. Existing: state directory unavailable.
2. **New**: take `checkout.lock` shared, non-blocking; busy → `ballast setup is running in this checkout; wait for it to finish`. The descriptor stays open and inheritable through `execv` (FR-014). Taken before the journal is read, so a running setup is never reported as interrupted (plan review F-006).
3. **New**: `setup-attempt.json` exists → `setup did not finish in this checkout; run ballast setup to recover` (AC-005).
4. **New**: a valid `installation.json` (its fingerprint equals `.ballast/.setup-version`) names a ref other than the `ballast.toml` pin → `pinned <B>, installed <A>: restore ref = "<A>" in ballast.toml, or fix the cause and rerun ballast setup` (AC-008). Without a record (an installation made before this feature) the check is skipped and the trust comparison still refuses a changed pin.
5. Existing: tamper marker, `in-progress`, trust baseline.

`status --json` keeps its shape (`installed`, `refusal`) and reports reasons 2 and 4 as `refusal`; it takes no lock. `trust` and `discard-runs` hold the same shared lock while they work, refusing when a setup holds it, and refuse while `setup-attempt.json` exists (a trust taken mid-switch would vouch for a mixed installation; plan review F-005). Nothing else changes in the trust model: `BASES`, `SKIPPED` and the baseline format are unchanged, and `.ballast/setup/` is outside `BASES`.

## Run format (`tools/spec_workflow/run.py`)

On `ballast run start`, after the run ID is known and before the first step, `run.py` writes `run-format.json` into `archive_dir(root, run_id)` under `archive_lock`:

```json
{"schema": 1, "format": "ballast-run/1"}
```

The value is a `RUN_FORMAT` constant in `run.py`, which runs from the checkout and cannot read the standard's `tools/cli.toml`; a test keeps it equal to `[runs] format`, as `TEMP_ROOTS` is kept equal between the CLI and the launcher.

## `tools/cli.toml` additions (extends ADR-0002)

```toml
[setup]
# This version's setup stages, journals and switches installations.
recoverable = true

[runs]
# The run-state format this version writes, and the formats it can resume.
format = "ballast-run/1"
resumes = ["ballast-run/1"]
```

The CLI reads these as data. Absent `[setup] recoverable` means false; absent `[runs] resumes` means no run is resumable. Change `format` (and decide `resumes`) whenever a change makes saved run state unresumable: the Spec Kit version, a shipped workflow's step IDs, or Ballast's run records. A test fails when the Spec Kit `VERSION` or the step IDs change while `format` does not.
