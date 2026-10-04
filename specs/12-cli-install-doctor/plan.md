# Implementation Plan: One-command CLI install and `ballast doctor`

**Branch**: `feat-cli-install-ballast-in-one-command-and-diag` | **Date**: 2026-10-03 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/12-cli-install-doctor/spec.md` (intent approved 2026-10-03, digest in [intent.md](intent.md))

**Risk**: R2 (what `ballast` downloads, how the operator-side entry point is obtained, the release workflow's write permission). Needs explicit human approval of this plan.

## Summary

Each tagged release publishes the unchanged `tools/ballast` file as a release asset `ballast`, next to `ballast.sha256`. The documented install line downloads both into a fresh temporary directory, checks the hash with `sha256sum -c`, and runs the verified file's new `self-install` subcommand. That subcommand atomically replaces `~/.local/bin/ballast`, does nothing when the same version is already installed, refuses to overwrite a file that is not Ballast, and reports the previous and new versions and whether the location is on `PATH`. The CLI gains a `VERSION` constant, kept current by Release Please, and `ballast --version`.

`ballast doctor` is a new read-only subcommand of the same single-file CLI. It runs a fixed table of machine checks concurrently, each with a time limit. That table is the single source for the prerequisite list. Inside a project it adds checks on the pinned ref, whether that version is fetched, the minimum CLI version, setup freshness and trust readiness. Setup freshness and trust readiness come from read-only probes of the pinned version: `tools/setup --check` and `launcher.py status --json`. Doctor runs a probe only when the fetched version's `tools/cli.toml` manifest declares it, so older pinned versions are never sent an unknown flag. Output is a human report or, with `--json`, a versioned machine-readable document. The exit code is 0 when nothing is blocked and 1 otherwise. See [research.md](research.md) for each decision.

## Technical Context

**Language/Version**: Python ≥ 3.11 standard library only (`tomllib`). Run as `/usr/bin/python3 -I -S` (shebang) or `python3 -I -S` (install line).

**Primary Dependencies**: None at runtime. External tools that are only probed: `git`, `uvx`, `patch`, `systemctl`, `systemd-run`, `specify`, `claude`/`codex`, `gh`. The install line uses `curl`, `mktemp` and `sha256sum` (coreutils).

**Storage**: Files only. Install target `~/.local/bin/ballast`; fetched versions `$XDG_DATA_HOME/ballast/standard/<ref>/`; trust state `$XDG_STATE_HOME/ballast/<key>/` (read only by doctor); setup stamp `.ballast/.setup-version` (read only by doctor).

**Testing**: `unittest`, offline. Fake releases are served from `file://` URLs. Prerequisites are removed by giving doctor a controlled `PATH` that contains stub executables. Before/after snapshot digests prove doctor writes nothing.

**Target Platform**: Linux with a systemd user session, the qualified 1.0 host. On other POSIX hosts doctor still runs and reports headless steps as unsupported.

**Project Type**: Single-file CLI plus a GitHub Actions release step.

**Performance Goals**: `ballast doctor` finishes in under 10 s on a responsive qualified host (SC-005). Every probe has a 3 s limit and probes run concurrently.

**Constraints**: Standard library only. Under `-I -S`, never import or execute from the cwd or the project checkout. Print no credential values. Doctor writes nothing and downloads nothing (an HTTP `HEAD` probe is allowed). Projects pinning v0.1.0 keep working unchanged.

**Scale/Scope**: About 12 machine checks and 6 project checks. `tools/ballast` grows from about 100 to about 450 lines.

No NEEDS CLARIFICATION remains: FR-007 was settled in the spec, and the remaining design choices are recorded in [research.md](research.md).

## Constitution Check

*Gate before Phase 0, re-checked after Phase 1. Result: **PASS** both times, no violations.*

| Principle | How the design holds it |
| --- | --- |
| 1. Projects own only their files (BL-INV-001) | Doctor writes nothing. `self-install` writes only `~/.local/bin/ballast`. The new `tools/cli.toml` ships with the standard and lands in no project path. |
| 2. Nothing executes from a writable checkout (BL-INV-002) | The install line runs only the hash-verified file in a `mktemp` directory under `-I -S`. Doctor executes only `/usr/bin/python3` against files under the fetched standard directory (`tools/setup --check`, `launcher.py status`), never a file under the project root. `BALLAST_STANDARD_DIR` keeps its existing developer meaning and is reported. |
| 3. Delegated authority (BL-INV-003) | Not touched. Doctor reads trust state but never writes it and never calls `trust`. |
| 4. A project picks a version, never a source (BL-INV-004) | The release URL in the install line and the probe URL are fixed to `Hugo-Grellier/ballast`. `tools/cli.toml` is data read from the fetched version and has no URL field. |
| 5. Postconditions over exit codes (BL-INV-005) | `self-install` re-reads the temporary file and compares its digest with the source before the atomic replace; nothing is read after it, so a failure never removes the previous install. The release job checks the uploaded asset's hash. |
| 6. Portable, dependency-free tools | Standard library only. A version guard runs before the `tomllib` import, so an old interpreter fails with a message instead of a traceback. |
| 7. Generic by default | Checks name only Ballast's own prerequisites. |
| 8. Executable evidence | Every AC and SC-003/SC-004 maps to a test in [quickstart.md](quickstart.md), including the refusal paths: bad hash, foreign target, interrupted install, unknown version and the read-only snapshot. |

## Architecture Boundaries

- **Affected areas**: the global command `tools/ballast` (new `--version`, `self-install`, `doctor`); the pinned standard's `tools/setup` (new read-only `--check`) and `tools/spec_workflow/launcher.py` (new read-only `status`); a new standard manifest `tools/cli.toml`; the release pipeline `.github/workflows/release-please.yml` and `release-please-config.json`; `README.md`.
- **Contracts and data flow**: release tag → asset `ballast` + `ballast.sha256` → install line verifies → `self-install` → `~/.local/bin/ballast`. On the project side, `ballast doctor` reads `ballast.toml`, then the fetched standard's `tools/cli.toml`, then runs that standard's read-only probes. The trust baseline stays owned by `launcher.py`, and setup freshness by `tools/setup`, so doctor recomputes neither and no second source of truth appears. See [contracts/](contracts/) and [data-model.md](data-model.md).
- **Architecture references**: [constitution](../../.specify/memory/constitution.md) BL-INV-002 and BL-INV-004; [roadmap](../../docs/plans/2026-10-02-product-roadmap.md) Phase 1; [project workflow risk rules](../../docs/policies/project/workflow.md).
- **Proposed architecture decisions** (each needs human approval, then an ADR under `docs/adr/`, the repository's first):
  1. **ADR-0001 CLI distribution channel.** The CLI is distributed as a release asset with a SHA-256 checksum, installed by a verify-then-`self-install` line (the spec's FR-007 provisional decision). The release workflow gets a job with `contents: write` that uploads the asset.
  2. **ADR-0002 CLI/standard compatibility manifest.** A standard version declares in `tools/cli.toml` the minimum CLI version it needs and which read-only doctor probes it supports. The CLI reads this file as data and never executes it.

## Repository Impact

| Path | Change |
| --- | --- |
| `tools/ballast` | `VERSION` constant with a Release Please marker; Python version guard; `--version`; `self-install [--dir DIR] [--force]`; `doctor [--json]`; a `doctor` hint in existing failure messages (FR-019). |
| `tools/cli.toml` | New manifest: `[cli] minimum`, `[doctor] probes`. |
| `tools/setup` | New `--check`: compares the stamp with the fingerprint and writes nothing; also mentions `ballast doctor` when `uvx` or `patch` is missing. |
| `tools/spec_workflow/launcher.py` | New `status --json`: reports install presence and the result of `_refusal()` without writing. |
| `.github/workflows/release-please.yml` | Give the Release Please step `id: release` and expose `release_created` and `tag_name` as job outputs. New job `publish-cli` with `needs: release-please` and `if: needs.release-please.outputs.release_created == 'true'` (step outputs are not visible across jobs): checks out `needs.release-please.outputs.tag_name`, writes `ballast.sha256`, verifies it and uploads both files with `gh release upload`, with `GH_TOKEN: ${{ github.token }}` on that step and `permissions: contents: write` on the job only. A workflow-lint test asserts this wiring. |
| `release-please-config.json` | `extra-files: ["tools/ballast", "README.md"]` so the release PR bumps `VERSION` and the README install line's version (`x-release-please-version` marker), keeping the documented line a single copy-paste command (SC-001). |
| `README.md` | The install section leads with the install line and `ballast doctor`, followed by a prerequisite summary that points to doctor; the manual copy stays as the developer fallback. |
| `docs/adr/0001-cli-release-asset-install.md`, `docs/adr/0002-cli-standard-manifest.md` | New, after approval. |
| `tests/test_ballast.py` | Extended: version, self-install and the README install line run against a `file://` release. |
| `tests/test_doctor.py` | New: one test per prerequisite (SC-003), project checks, JSON schema, the read-only snapshot and timeouts. |
| `tests/test_setup.py`, `tests/test_spec_workflow.py` | `setup --check` and `launcher status` are read-only and report correctly. |
| `tests/test_ballast.py` (FR-019) | Command-level regressions against a fixture project pinned to v0.1.0: `setup`, `trust`, `run` (refusal path) and `ledger report` produce today's results with the new CLI. |

## Feature Artifacts

```text
specs/12-cli-install-doctor/
├── intent.md
├── spec.md
├── plan.md            # this file
├── research.md        # Phase 0 decisions
├── data-model.md      # entities, statuses, check table
├── contracts/
│   ├── install.md     # release assets, install line, self-install
│   ├── doctor-cli.md  # doctor arguments, report, exit codes
│   ├── doctor-report.schema.json
│   └── standard-manifest.md  # tools/cli.toml and the read-only probes
├── quickstart.md      # validation scenarios mapped to ACs
├── tasks.md           # next: speckit-tasks
├── decisions.md       # only if implementation discovers one
└── reviews/
```

## Complexity Tracking

No constitution violations.
