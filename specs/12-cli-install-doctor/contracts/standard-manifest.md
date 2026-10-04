# Contract: standard manifest and read-only probes

These are interfaces between the machine-wide CLI and a fetched standard version. Doctor reads the manifest as data. It runs a probe only when the manifest declares it, and only from the fetched standard directory, never from the project checkout.

## `tools/cli.toml`

```toml
[cli]
minimum = "0.2.0"   # lowest CLI version this standard version supports

[doctor]
probes = ["setup-check", "launcher-status"]
```

- Missing file: no CLI minimum and no probes, as with standard v0.1.0.
- Parse error or bad value: the `cli-version` check is `inconclusive`, and the probes are treated as absent.
- Bump `minimum` only when the standard relies on a CLI behavior added after the current minimum.

## Probe `setup-check`

```text
/usr/bin/python3 -I -S <standard>/tools/setup --project <root> --check
```

| Exit | Meaning | Doctor status |
| --- | --- | --- |
| 0 | the stamp matches the fingerprint | `passing` |
| 1 | stamp missing or stale, or an installed output the stamp promises is absent (for example `.ballast/spec_workflow/run.py`, `.ballast/feature_intake.py`, `.specify/workflows/ballast-feature/workflow.yml`); stdout says which | `missing`, remedy `ballast setup` |
| other / timeout | | `inconclusive` |

Writes nothing. It skips `check_ignored`, `remove_installed` and every install step.

## Probe `launcher-status`

```text
cd <root> && /usr/bin/python3 -I -S <standard>/tools/spec_workflow/launcher.py status --json
```

stdout: `{"installed": bool, "refusal": null | "<reason>"}`. The reason has the same text `_refusal()` gives `run` and `ledger` today. Exit 0 whenever it can report. Writes nothing and never creates the state directory.

| Result | Doctor status |
| --- | --- |
| `installed: false` | `missing` with remedy `ballast setup` when `ballast.toml` pins a version (setup should be present); `skipped` only outside a project. Test: deleting `.ballast/spec_workflow/run.py` after setup makes both `setup-current` and `trust` report `missing`. |
| `refusal: null` | `passing` |
| `refusal: "..."` | `missing`, detail is the reason, remedy "review the checkout, then run `ballast trust`" (after `ballast discard-runs` when the reason is an unfinished agent step, or after restoring the checkout and deleting the marker for `BALLAST_TAMPERED`) |
| unparsable output / timeout | `inconclusive` |
