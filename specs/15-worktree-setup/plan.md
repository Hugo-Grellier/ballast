# Implementation Plan: Prepare a new worktree on first Ballast use

**Branch**: `feat/15-worktree-setup` | **Date**: 2026-10-06 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/15-worktree-setup/spec.md` (intent agent-provisional, PD-0006, digest in [intent.md](intent.md))

**Risk**: R2. The plan changes which paths are installed into a checkout, when and from where, and what the launcher reports about trust. This is an Autonomous run: every design decision below is agent-provisional, not human-approved, and merging the PR is the single human approval (BL-INV-006).

## Summary

The first `ballast run`, `ledger` or `intake` in a checkout with no installation prepares one without a separate setup and without network access. The global CLI detects the uninstalled checkout, checks that the pinned version declares `[setup] prepare` in its `tools/cli.toml`, verifies the cached version against its content record, and runs that version's own `tools/setup --prepare` before handing the command to the launcher as today.

`--prepare` is a local-only mode of ADR-0007's attempt: same exclusive checkout lock, journal, stage, validation, switch, live verification and recovery. Instead of downloading, it fills the stage from the first verified candidate among the installations already recorded on this machine for the same repository: its own kept copy, then the primary's and each linked worktree's live and kept installations. A candidate is used only when it is not being set up or unfinished, its pin and fingerprint (standard content plus `ballast.toml` bytes) equal the worktree's, and the stage copy hashes equal to the candidate's record, executable bits included (the record gains an `executable` list). No match refuses naming `ballast setup`. Preparation acts only on a checkout with no installation or an interrupted preparation, never records or reads a trust baseline, and the launcher then refuses at preflight naming the protected inputs to review and `ballast trust`. Decisions are in [research.md](research.md).

## Technical Context

**Language/Version**: Python ≥ 3.11 standard library only, run under `/usr/bin/python3 -I -S`.

**Primary Dependencies**: None new. `git` (adds `git worktree list --porcelain -z`); no `uvx`, `patch` or network on the preparation path.

**Storage**: Files only. Per-checkout operator state `$XDG_STATE_HOME/ballast/<key>/`: `installation.json` gains `executable`; `setup-attempt.json` and `setup-holder.json` gain `mode`. Standard manifest `tools/cli.toml` gains `[setup] prepare`. See [data-model.md](data-model.md).

**Testing**: `unittest`, offline, reusing `tests/test_setup.py`'s fakes and SIGKILL wrapper; real linked worktrees; network calls fail the test; ten-process concurrency; before/after snapshots of project-owned files and of every source checkout and its operator state. One networked end-to-end scratch-project run with two worktrees, recorded in the PR. See [quickstart.md](quickstart.md).

**Target Platform**: Linux with a systemd user session (the qualified 1.0 host); preparation itself needs only POSIX `flock` and `rename`.

**Project Type**: Single-file CLI (`tools/ballast`) plus the standard's install script and launcher.

**Performance Goals**: Preparation under 10 s (SC-005): one cache verification, one `git worktree list`, a copy and two hashes of an installation of a few MB.

**Constraints**: No network on any command but `setup` and `preview`; nothing executes from a checkout; no trust baseline recorded, copied or read across checkouts; existing installations change only through `ballast setup`; projects pinning older versions and older CLIs keep working.

**Scale/Scope**: `tools/setup` about +150 lines (candidates, prepare mode, recovery rule, mode check); `tools/ballast` about +40 (trigger, declaration, damage refusal); `launcher.py` about +20 (messages); `tools/cli.toml` +3; ten-worktree tests.

No NEEDS CLARIFICATION remains; [research.md](research.md) records R1 to R10.

## Constitution Check

*Gate before Phase 0, re-checked after Phase 1. Result: **PASS** both times, no violations.*

| Principle | How the design holds it |
| --- | --- |
| 1. Projects own only their files (BL-INV-001) | Preparation writes only installed, ignored entries and the ignored work area, through setup's ignore and link checks; it never writes `ballast.toml`, the constitution (not even when absent) or `docs/policies/project/`. No new ignore rule. |
| 2. Nothing executes from a writable checkout (BL-INV-002) | The CLI runs only the pinned version's `tools/setup` from the cache after verifying it against its record, under `-I -S`. Copied content is accepted only when it hashes equal to a record in operator state; the worktree still refuses at the trust preflight until the operator runs `ballast trust`, which never prepares. |
| 3. Delegated authority (BL-INV-003) | Unchanged for agents. Preparation runs only from operator commands; another checkout is read under its shared lock and never written; no baseline crosses checkouts. |
| 4. A project picks a version, never a source (BL-INV-004) | No new download or source; candidates are local installations whose record pin equals `ballast.toml`'s ref. `[setup] prepare` is data without URLs. |
| 5. Postconditions over exit codes (BL-INV-005) | A candidate counts only after its stage copy matches its record in content and modes; the switch commits only after the live installation matches; recovery verifies against the empty `before`. |
| 6. Portable, dependency-free tools | Standard library only; `git worktree list` is a fixed subcommand with data parsed by `-z`. |
| 7. Generic by default | No project names; messages and README text are generic. |
| 8. Executable evidence | Every AC and SC maps to a test in [quickstart.md](quickstart.md), including refusals, mismatches, kills, concurrency and no-network checks. |
| 9. Provisional decisions (BL-INV-006) | This plan, its ADR proposal and decisions D-03 to D-06 are agent-provisional; no artifact calls them approved. |

## Architecture Boundaries

- **Affected areas**: the global command `tools/ballast` (preparation trigger, declaration read, damage refusal on preparing commands, uninstalled refusal for old versions); the pinned standard's `tools/setup` (`--prepare` mode, candidate sources, `executable` record field and check, prepare-journal recovery, holder mode); `tools/spec_workflow/launcher.py` (no-baseline and not-installed messages); `tools/cli.toml`; `README.md`.
- **Contracts and data flow**: `ballast run|ledger|intake` → CLI: pinned version fetched? (else refuse, no network) → checkout needs an installation and version declares `prepare`? → cache verifies? → `tools/setup --prepare` (lock, recover, state check, candidates, stage copy, validate, switch, record) → `execv` launcher → trust preflight refusal → operator `ballast trust` → run. Ownership is unchanged: setup owns installation records and the journal, the launcher owns trust, the CLI owns the cache and only reads `tools/cli.toml` and `setup-attempt.json` existence as data. Contracts: [prepare.md](contracts/prepare.md), [cli-and-launcher.md](contracts/cli-and-launcher.md).
- **Architecture references**: [constitution](../../.specify/memory/constitution.md) BL-INV-001 to BL-INV-006; [ADR-0002](../../docs/adr/0002-cli-standard-manifest.md) (manifest as data); [ADR-0007](../../docs/adr/0007-recoverable-installation.md) (stage, journal, record, lock), extended here; [ADR-0008](../../docs/adr/0008-verified-cache-and-update-preview.md) (verified cache); [feature 14 contracts](../14-recoverable-install/contracts/); [roadmap Priority 1](../../docs/plans/2026-10-02-product-roadmap.md); [project workflow R2 boundaries](../../docs/policies/project/workflow.md).
- **Proposed architecture decisions** (agent-provisional; written with the implementation as `docs/adr/0009-worktree-preparation.md`, accepted only when the PR merges):
  1. **ADR-0009 Worktree preparation from verified local installations.** Extends ADR-0007: the first `run`, `ledger` or `intake` in a checkout with no installation runs the pinned setup in a local-only `--prepare` mode, declared by `[setup] prepare`; sources widen from the primary to every recorded live or kept installation of the repository on this machine, each accepted only by pin, fingerprint, content and executable bits; the installation record lists executable files; a committed first preparation whose fingerprint no longer applies is rolled back; trust baselines stay per checkout and are never read across checkouts, and one predating a worktree is removed (R1 to R9).

## Repository Impact

| Path | Change |
| --- | --- |
| `tools/setup` | `--prepare` flag and `Setup.prepare()` following [prepare.md](contracts/prepare.md); `candidates()` from `git worktree list --porcelain -z`; `copy_candidate()` taking the source's shared lock before reading its record; `validate()` writes `executable`; `copy_verified()` checks executable bits; journal and holder `mode`; `recover()` rolls back a committed `prepare` journal at another fingerprint; `finish()` skips the constitution in prepare mode; module docstring. `copy_from_primary` keeps its behavior for `ballast setup` and moves its record read after the lock. |
| `tools/ballast` | `PREPARING = ("run", "ledger", "intake")`; `needs_installation(root)`; `declarations()` also returns `prepare`; preparation step in `main` per [cli-and-launcher.md](contracts/cli-and-launcher.md); damage refusal without fetch; usage text and docstring. |
| `tools/spec_workflow/launcher.py` | No-baseline message listing present inputs and `ballast trust`; not-installed refusal for `trust`, `discard-runs` and old-CLI `run`/`ledger`/`intake`. |
| `tools/cli.toml` | `[setup] prepare = true`. |
| `README.md` | Replace the worktree sentence in "Installing the Spec Kit workflow" with a short "Worktrees" paragraph: first command prepares, no download, trust per worktree, first worktree at a new pin needs `ballast setup`. |
| `docs/adr/0009-worktree-preparation.md` | New; proposed until merge. |
| `tests/test_setup.py` | `PrepareTests`, `PrepareConcurrencyTests`; `executable` record and mode-check cases for the existing worktree copy. |
| `tests/test_ballast.py` | `PrepareTriggerTests`: trigger conditions, declaration absent, damaged cache, no network, exit codes, non-preparing commands. |
| `tests/test_spec_workflow.py` | Updated no-baseline text; not-installed refusal for `trust`/`discard-runs`. |
| `tests/test_doctor.py` | Doctor still classifies the new no-baseline text; read-only on an uninstalled worktree. |

## Feature Artifacts

```text
specs/15-worktree-setup/
├── discovery.md        # input evidence
├── intent.md
├── spec.md
├── plan.md             # this file
├── research.md         # Phase 0 decisions R1–R10
├── data-model.md       # record, journal, holder, candidates, transitions
├── contracts/
│   ├── prepare.md             # tools/setup --prepare order, output, refusals
│   └── cli-and-launcher.md    # CLI trigger, launcher messages, cli.toml
├── quickstart.md       # AC/SC → test map and end-to-end run
├── checklists/
├── autonomous/
├── tasks.md            # next: speckit-tasks
├── decisions.md        # only if implementation discovers one
└── reviews/
```

## Complexity Tracking

No constitution violations.
