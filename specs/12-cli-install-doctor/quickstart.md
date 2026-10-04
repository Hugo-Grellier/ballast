# Quickstart validation: One-command CLI install and `ballast doctor`

Contracts: [install](contracts/install.md), [doctor](contracts/doctor-cli.md), [manifest and probes](contracts/standard-manifest.md). Entities: [data-model.md](data-model.md).

## Prerequisites

- Linux, `/usr/bin/python3` ≥ 3.11, `uv`, coreutils `sha256sum`, `curl`.
- Fast gate: `uvx ruff check && uvx ruff format --check` and `uv run --no-project --python 3.13 --with pyyaml python -m unittest tests/test_*.py`.

## Automated scenarios (offline, in `tests/`)

The tests serve a fake release from a temp directory as `file://…/releases/download/<tag>/{ballast,ballast.sha256}`. They run the README install line with only the base URL replaced, under a temporary `HOME` and a controlled `PATH`.

| Scenario | Evidence |
| --- | --- |
| Fresh install prints the version, and the target is byte-identical to `tools/ballast` | AC-001, AC-002, SC-001 |
| Corrupted asset: the hash comparison fails and prints `checksum mismatch`, the previous target stays byte-identical and runnable | AC-003, SC-004 |
| Upgrade from a v0.1.0-style file without `VERSION` reports "previous version unknown"; from a versioned file it reports previous → new; a rerun with the same version is a no-op | AC-004, FR-004 |
| `DIR` not on `PATH` prints the `export PATH=…` line | AC-005 |
| Line run from inside a Git checkout that contains a planted `tools/ballast` and `sitecustomize.py`: neither is used | AC-006 |
| Unknown tag (404 via a missing `file://` path), interrupted download (truncated asset), foreign target without `--force`: target unchanged | edge cases, SC-004 |
| Python older than 3.11 (simulated by patching the guard's `version_info`): message, no traceback | edge case |
| `--version` with no project and no network | FR-006 |
| All stubs present: every check `passing`, exit 0 | AC-007 |
| One test per machine check, removing its stub from `PATH`: named, gated, remedy given, exit 1; restoring it passes | AC-008, SC-003 |
| Non-Linux and no-systemd simulation: headless steps `unsupported`, other checks still reported | AC-009 |
| No agent CLI; a `gh` stub whose `auth status` fails and prints a token-shaped string: gaps reported, string absent from text and JSON | AC-010, FR-014 |
| Outside a project: project checks `skipped` with "no ballast.toml found" | AC-011 |
| Digest snapshot of project, `XDG_DATA_HOME`, `XDG_STATE_HOME` and `~/.local/bin` before and after every doctor test: unchanged; no network beyond `HEAD` | AC-012, FR-011 |
| Missing or invalid ref and unparsable `ballast.toml`: same messages as `pinned_ref`, machine checks still present | AC-013, edge case |
| Pinned version not fetched → `ballast setup`; fetched with stale stamp → `ballast setup`; no baseline → `ballast trust` | AC-014, AC-015 |
| Fetched standard whose `tools/cli.toml` minimum is above `VERSION` → mismatch and install line | AC-016 |
| Fetched standard without `tools/cli.toml` (v0.1.0 layout): no probe is executed (a sentinel stub proves it), checks are presence-only or `inconclusive` | R8 compatibility |
| A `systemctl` stub that sleeps 30 s: `systemd-user` `inconclusive`, total under 10 s | FR-016, SC-005 |
| `--json` output validates against `contracts/doctor-report.schema.json` (structural check with stdlib, no jsonschema dependency) | FR-015 |
| Every machine check name appears in the README prerequisite summary | FR-018 |
| `setup --check` and `launcher.py status --json` leave the project and state directory unchanged | probe contracts |

## Manual end-to-end (required for `tools/ballast` and `tools/setup` changes)

The [project testing policy](../../docs/policies/project/testing.md) requires this run. On a qualified host with a scratch project:

1. Install from this branch as the developer fallback (`install -m 0755 tools/ballast ~/.local/bin/ballast`), then run `ballast --version`.
2. `ballast doctor` in the scratch project pinned to this branch's commit, before setup: it names `ballast setup`. (`BALLAST_STANDARD_DIR` is data-only for doctor, so its project probes report `inconclusive`; that is checked by the automated tests, not here.)
3. `ballast setup` → `ballast doctor` names `ballast trust` → `ballast trust` → `ballast doctor` exits 0.
4. `ballast ledger report`; `git status` is clean apart from the project's own files.
5. After the first release that carries this feature, run the README install line on a clean account and confirm SC-001 and SC-002. This is recorded as post-release verification in the PR, because no asset exists before that release.

## Expected outcome

All automated scenarios pass in the fast gate. The manual run is recorded in the PR with exact commands. The `publish-cli` job is checked on the first release by downloading the asset and comparing its SHA-256 with `ballast.sha256`.
