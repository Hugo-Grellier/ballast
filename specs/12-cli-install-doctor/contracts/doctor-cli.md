# Contract: `ballast doctor`

```text
ballast doctor [--json]
```

- Runs from any directory. The cwd is a project when it contains `ballast.toml`; there is no upward search, which matches every other `ballast` command.
- Works before any version is fetched and before trust. It never fetches, writes, trusts or downloads (FR-011, FR-012).
- `BALLAST_STANDARD_DIR` set: the report says `using local standard <path>`, and project checks use that directory instead of the pinned fetched one.

## Human report (stdout)

```text
Ballast doctor (CLI v0.2.0)

Machine
  ok           python        /usr/bin/python3 3.12
  missing      patch         needed by: ballast setup
                             fix: sudo apt install patch
  unsupported  systemd-user  needed by: ballast run (headless steps)
                             no systemd user session; fix: loginctl enable-linger "$USER", then log in again
  ...
Project /path/to/project (pinned v0.2.0)
  ok           ballast-toml  ref v0.2.0
  missing      trust         needed by: ballast run, ballast ledger
                             launcher will refuse: no trusted baseline
                             fix: review the checkout, then run `ballast trust`

Blocked: ballast run, ballast setup (2 gaps). Exit 1.
```

The last line is always present. It reads either `Everything Ballast needs is in place.` or `Blocked: <commands> (<n> gaps).` Exact column widths and wording are not part of the contract; the check names, statuses, gates and remedies are.

## Machine-readable report (`--json`, stdout)

A single JSON document that follows [doctor-report.schema.json](doctor-report.schema.json). Field meanings are in [data-model.md](../data-model.md#doctor-report). The JSON report never contains credential values.

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | verdict `ok`: no check is `missing` or `unsupported` |
| 1 | verdict `blocked` |
| 2 | usage error (unknown option) |

## Timing

Each probe finishes within 3 s or reports `inconclusive` ("did not answer within 3 s"). Probes run concurrently.
