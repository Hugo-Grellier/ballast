# Implementation Plan: Adapt Ballast to blank and established repositories

**Branch**: `feat/13-adaptive-init` | **Date**: 2026-10-06 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/13-adaptive-init/spec.md` (intent agent-provisional, PD-0015, digest in [intent.md](intent.md))

**Risk**: R2. Init generates protected inputs (`ballast.toml`, the constitution under `.specify/`), writes the ignore block and, through setup, the installed paths, and sits next to the launcher's trust boundary. This is an Autonomous run: every design decision below is agent-provisional, not human-approved, and merging the PR is the single human approval (BL-INV-006).

## Summary

`ballast init` makes a blank or established repository usable with one command followed by the operator's own `ballast trust`. The global CLI only bootstraps: it picks the ref (`--ref`, else its own `v{VERSION}`, else the existing pin), fetches that version into the per-machine cache, checks that its `tools/cli.toml` declares `[init] supported = true` and that the CLI meets its minimum, and runs that version's new `tools/init` from the fetched directory.

`tools/init` runs one stage sequence for every repository: `check`, `inspect` a fixed, size-bounded, link-safe list of evidence files as data, `choose` the material choices (blank only: description and stack, by flag or terminal prompt, refused without a terminal), `plan` every write in memory, then `git-init` (only when there is no repository), `ignore` (append setup's block when the probes fail, probe again, stop with a patch on a conflicting rule), `write` absent files only with exclusive, no-follow creation, `patch` (one ignored `.ballast/init/proposed.patch` for every change to an existing file), `install` through setup in process, `verify` and `report`. Evidence-backed commands become active checks citing their source; inferred ones and every `extra_allow` suggestion stay commented. Init never runs a detected command, never records trust, and never commits or pushes. A rerun creates only what is absent, keeps the pin and reports drift as a patch. Decisions are in [research.md](research.md) R1 to R17.

## Technical Context

**Language/Version**: Python ≥ 3.11 standard library only, run under `/usr/bin/python3 -I -S`.

**Primary Dependencies**: None new. `git` (`rev-parse`, `init --template=`, `check-ignore`, `remote get-url`), always with setup's config-safe prefix. `tomllib`, `json`, `difflib`, `shlex`, `importlib` from the standard library.

**Storage**: Files only. Generated, tracked: `ballast.toml`, `.gitignore` (create or append), `.specify/memory/constitution.md`, `AGENTS.md`, `CLAUDE.md` link, `docs/policies/project/testing.md`. Ignored: `.ballast/init/proposed.patch`. Manifest `tools/cli.toml` gains `[init] supported`. No new operator state. See [data-model.md](data-model.md).

**Testing**: `unittest`, offline: `tests/test_init.py` runs `tools/init` in process with `tests/test_setup.py`'s `fakes()` patched onto the setup module init loads, an audit hook proving only `git` starts, scratch fixtures for every edge case, and a post-trust `launcher._refusal` check; `tests/test_ballast.py` covers the CLI bootstrap. One networked end-to-end scratch run (blank and established) recorded in the PR. See [quickstart.md](quickstart.md).

**Target Platform**: Linux with a systemd user session (the qualified 1.0 host); init itself needs only POSIX file APIs and `git`.

**Project Type**: Single-file CLI (`tools/ballast`) plus the standard's tools and templates.

**Performance Goals**: Inspection reads at most about 40 files of at most 256 KiB each; init's own work (excluding setup's install) under 2 s.

**Constraints**: Nothing executes from the checkout; nothing detected is executed; no trust, commit, push or remote; existing files byte-identical except an appended ignore block; refusals before the first write leave the target untouched; projects pinning older versions and older CLIs keep working.

**Scale/Scope**: new `tools/init` about 700 lines; `tools/ballast` about +60; `tools/cli.toml` +3; three templates under `templates/init/`; new ADR; README and technical spec sections; `tests/test_init.py` and CLI tests.

No NEEDS CLARIFICATION remains; [research.md](research.md) records R1 to R17.

## Constitution Check

*Gate before Phase 0, re-checked after Phase 1. Result: **PASS** both times, no violations.*

| Principle | How the design holds it |
| --- | --- |
| 1. Projects own only their files (BL-INV-001) | Init creates only project-owned files (`ballast.toml`, constitution, `docs/policies/project/testing.md`, `AGENTS.md`, `CLAUDE.md`) and the ignore block, takes the block and probes from the same version's setup, probes created files to be not ignored, and installs only through setup's ignore and link checks. The patch lives under ignored `.ballast/init/`. |
| 2. Nothing executes from a writable checkout (BL-INV-002) | The CLI runs only the fetched (or `BALLAST_STANDARD_DIR`) version's `tools/init` under `-I -S`; init imports only its sibling setup and launcher; evidence is parsed as data and never executed; git runs with hooks, pager and fsmonitor disabled. The launcher still refuses until the operator's `ballast trust`. |
| 3. Delegated authority (BL-INV-003) | Init adds no active `extra_allow` rule and never writes a trust baseline; protected inputs it generates take effect only after operator trust. |
| 4. A project picks a version, never a source (BL-INV-004) | The ref defaults to the CLI's version or the existing pin and passes `REF` validation; the source stays `REPOSITORY`. `[init]` holds no URL. |
| 5. Postconditions over exit codes (BL-INV-005) | Readiness is verified after install: setup status `current`, probes, link resolution, launcher refusal, command presence; a `not-ready` check fails the run. |
| 6. Portable, dependency-free tools | Standard library only; CI is scanned line by line, no YAML library. |
| 7. Generic by default | New templates carry no project names; `AGENTS.md` reuses the generic copy-once template; unknowns read `TO CONFIRM`. |
| 8. Executable evidence | Every AC and SC maps to a test in [quickstart.md](quickstart.md), including refusals, link, git-config, no-execution and rerun cases. |
| 9. Provisional decisions (BL-INV-006) | This plan, research R1 to R17 and the ADR-0012 proposal are agent-provisional; no artifact calls them approved. |

## Architecture Boundaries

- **Affected areas**: the global command `tools/ballast` (`init` bootstrap, messages naming init); the standard's new `tools/init`; `tools/cli.toml` (`[init]`); new `templates/init/`; `README.md`; `specs/TECHNICAL-SPEC.md`; `AGENTS.md` layout line. `tools/setup` and `tools/spec_workflow/launcher.py` are reused unchanged, as modules.
- **Contracts and data flow**: `ballast init` → CLI: ref (flag, own version or pin) → `ensure_standard` (cache) → manifest `[init]` and `[cli] minimum` → `execv tools/init` → check → inspect (evidence as data) → choose → plan → git-init → ignore (setup's `GITIGNORE`/`IGNORE_PROBES`) → write (exclusive creates) → patch → `Setup.main()` → verify (setup status, probes, launcher `_refusal`) → report → operator reviews and runs `ballast trust`. Ownership is unchanged: setup owns the ignore block, installed paths and installation records; the launcher owns trust; the CLI owns ref choice and the cache; init owns only the generated project files and the patch. Contracts: [cli-init.md](contracts/cli-init.md), [init-tool.md](contracts/init-tool.md), [generated-files.md](contracts/generated-files.md).
- **Architecture references**: [constitution](../../.specify/memory/constitution.md) BL-INV-001 to BL-INV-006; [ADR-0001](../../docs/adr/0001-cli-release-asset-install.md) (CLI version); [ADR-0002](../../docs/adr/0002-cli-standard-manifest.md) (manifest as data), extended here; [ADR-0007](../../docs/adr/0007-recoverable-installation.md) (recoverable setup, reused); [ADR-0008](../../docs/adr/0008-verified-cache-and-update-preview.md) (verified cache, preview for pin changes); [ADR-0011](../../docs/adr/0011-worktree-preparation.md); [roadmap Priority 1](../../docs/plans/2026-10-02-product-roadmap.md); [project workflow R2 boundaries](../../docs/policies/project/workflow.md); [PRODUCT-SPEC §5.7](../PRODUCT-SPEC.md); [TECHNICAL-SPEC §9.1](../TECHNICAL-SPEC.md).
- **Proposed architecture decisions** (agent-provisional; written with the implementation as `docs/adr/0012-init-before-pin.md`, accepted only when the PR merges):
  1. **ADR-0012 `init` runs before a pin, as a declared standard tool.** Extends ADR-0002: `init` is the only CLI command that works without `ballast.toml`; the CLI chooses the ref (its own version by default, the existing pin on rerun), fetches it, requires `[init] supported = true` and the manifest's CLI minimum, and runs that version's `tools/init` from the fetched directory; the standard owns inspection, generation and installation through its own setup; init creates only absent project files, proposes every other change as an ignored patch, never executes detected commands, never records trust, never commits or pushes (R1 to R3, R8 to R11, R13).

## Repository Impact

| Path | Change |
| --- | --- |
| `tools/init` | New. Stages per [init-tool.md](contracts/init-tool.md): argument and root checks, evidence reader (no-follow, size-bounded), CI line scanner and check classifier, choice prompts, profile and write plan, renderers for [generated-files.md](contracts/generated-files.md), ignore stage, exclusive writer, patch builder, setup call, readiness checks, report. Loads `tools/setup` and `tools/spec_workflow/launcher.py` as modules. |
| `tools/ballast` | `init` subcommand before `command_standard` per [cli-init.md](contracts/cli-init.md); `[init]` read added to the manifest reading; `USAGE`, docstring; missing-pin messages and `PIN_REMEDY` name `ballast init`. |
| `tools/cli.toml` | `[init] supported = true`. |
| `templates/init/constitution.md` | New generic project constitution template. |
| `templates/init/agents-section.md` | New Ballast section proposed for an existing instruction file. |
| `templates/init/testing.md` | New project testing addendum template. |
| `docs/adr/0012-init-before-pin.md` | New; proposed until merge. |
| `README.md` | Adoption starts with `ballast init` (what it writes, asks, never does, and the `ballast trust` step); the manual steps stay as the fallback for pins without init. |
| `specs/TECHNICAL-SPEC.md` | CLI command list and the manifest's `[init]` declaration. |
| `AGENTS.md` | Layout line mentions `templates/init/`. |
| `tests/test_init.py` | New: every fixture of [quickstart.md](quickstart.md). |
| `tests/test_ballast.py` | `InitBootstrapTests`: default ref, `--ref` validation, pin conflict, missing `[init]`, minimum too high, untouched root on refusal, `execv` arguments, `BALLAST_STANDARD_DIR`. |
| `tests/test_doctor.py` | Updated `PIN_REMEDY` text. |

## Feature Artifacts

```text
specs/13-adaptive-init/
├── discovery.md        # input evidence
├── intent.md
├── spec.md
├── plan.md             # this file
├── research.md         # Phase 0 decisions R1–R17
├── data-model.md       # repository, evidence, profile, write plan, report, stages
├── contracts/
│   ├── cli-init.md          # CLI bootstrap, manifest [init], refusals
│   ├── init-tool.md         # tools/init stages, exit codes, report
│   └── generated-files.md   # ballast.toml, constitution, AGENTS.md, addendum, patch
├── quickstart.md       # AC/SC → test map and end-to-end run
├── checklists/
├── autonomous/
├── tasks.md            # next: speckit-tasks
├── decisions.md        # only if implementation discovers one
└── reviews/
```

## Complexity Tracking

No constitution violations.
