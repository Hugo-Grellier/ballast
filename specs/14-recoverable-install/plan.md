# Implementation Plan: Recoverable installs and pin updates

**Branch**: `feat/14-recoverable-install` | **Date**: 2026-10-06 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/14-recoverable-install/spec.md` (intent agent-provisional, PD-0007, digest in [intent.md](intent.md))

**Risk**: R2. The plan changes what `ballast` downloads and verifies, which paths `tools/setup` installs, removes or preserves, and the launcher's refusal conditions. This is an Autonomous run: every design decision below is agent-provisional, not human-approved, and merging the PR is the single human approval (BL-INV-006).

## Summary

`tools/setup` stops deleting the installation before rebuilding it. It builds the complete replacement in a stage project under `.ballast/setup/<attempt>/stage/` (its own Git repository, so Spec Kit cannot reach live paths), validates it, then switches each installed entry with two renames, keeping the previous entry in `.ballast/setup/<attempt>/previous/` until the live installation verifies against the new content record. A journal in operator state, written before each phase, lets the next `ballast setup` roll an interrupted attempt back to the previous installation, or finish one that had already committed. The project constitution is never written in the checkout except on a first installation.

An `flock` in operator state serializes setup per checkout and lets the launcher hold a shared lock for the life of `run`, `ledger` and `intake`, so setup refuses while a workflow command runs and vice versa. An installation record in operator state (ref, fingerprint, digest of every installed file) makes "current and verified" a content check, lets worktrees copy only a verified primary installation, and lets the launcher, `setup --check` and doctor name the pinned and installed versions.

In the CLI, fetching a standard version is serialized per version, published with one rename together with a content record, and verified before setup or preview uses it; damage triggers a refetch or a refusal naming the path. A new `ballast preview <ref>` builds the target with its own setup in a disposable project outside the checkout, and reports the version change, CLI minimum, run compatibility (from a new run-format record and the target's `[runs] resumes`), installed-path and ignore impact, and the ordered commands to finish the update. The README gains an update section covering preview, update, retry and rollback. Decisions are in [research.md](research.md).

## Technical Context

**Language/Version**: Python ≥ 3.11 standard library only (`fcntl`, `hashlib`, `json`, `os`, `ast`, `tomllib`), run under `/usr/bin/python3 -I -S`.

**Primary Dependencies**: None new. External tools already required: `git` (now also `git init` for the stage and `git check-ignore --stdin`), `uvx` (Spec Kit 1.0.11), `patch`.

**Storage**: Files only. Checkout: installed entries and the work area `.ballast/setup/`. Operator state `$XDG_STATE_HOME/ballast/<key>/`: `installation.json`, `setup-attempt.json`, `checkout.lock`, `setup-holder.json`. Cache `$XDG_DATA_HOME/ballast/standard/`: `<ref>/.ballast-cache.json`, `.locks/`. Run archive: `run-format.json`. See [data-model.md](data-model.md).

**Testing**: `unittest`, offline: fakes for Spec Kit commands and source downloads, `file://` archives for the CLI, `SIGKILL` through a wrapper script at named functions (no production fault hook, R12), concurrent subprocesses for locking, before/after snapshots for every "unchanged" claim. One networked end-to-end run on the full gate. See [quickstart.md](quickstart.md).

**Target Platform**: Linux with a systemd user session (the qualified 1.0 host); locking and recovery need only POSIX `flock` and `rename`.

**Project Type**: Single-file CLI (`tools/ballast`) plus the standard's install script and workflow tools.

**Performance Goals**: A no-op setup at a current pin finishes in under 5 s with no network (SC-003): fingerprint, live-content hash and cache verification are each a hash of a few MB.

**Constraints**: Standard library only; nothing executes from the checkout; setup never edits `ballast.toml` or records trust; no new ignore rule, so existing projects need no `.gitignore` change; projects pinning v0.5.0 or earlier keep working with the new CLI.

**Scale/Scope**: `tools/setup` roughly doubles (about 440 → 850 lines); `tools/ballast` gains about 350 lines (cache, preview); `launcher.py` about 60; `run.py` about 15.

No NEEDS CLARIFICATION remains; [research.md](research.md) records R1 to R13.

## Constitution Check

*Gate before Phase 0, re-checked after Phase 1. Result: **PASS** both times, no violations.*

| Principle | How the design holds it |
| --- | --- |
| 1. Projects own only their files (BL-INV-001) | The work area is under `.ballast/`, already ignored; the ignore block is unchanged. Setup removes only paths the project ignores, and writes the constitution only when absent. |
| 2. Nothing executes from a writable checkout (BL-INV-002) | Journal, installation record and locks are in operator state, outside agent authority. The cache is verified by content before setup or preview executes it. The preview executes only the target's `tools/setup` from the verified cache under `-I -S`, in a disposable directory under `$XDG_DATA_HOME`, never trusts it and never puts it in place. The launcher gains refusals and loses none. |
| 3. Delegated authority (BL-INV-003) | Unchanged for agents. The launcher's shared lock is held by the operator process; agents do not inherit it (closed descriptors, systemd scope). Setup refuses while an agent step is unfinished and never clears that marker. |
| 4. A project picks a version, never a source (BL-INV-004) | `preview <ref>` validates the ref with the same `REF` rule; the repository stays fixed. `tools/cli.toml` additions are data without URLs. |
| 5. Postconditions over exit codes (BL-INV-005) | A switch commits only after the live installation hashes equal to the record; a fetch publishes only after the record is computed; rollback verifies against the previous record. |
| 6. Portable, dependency-free tools | `fcntl`, `os.rename`, `hashlib`, `ast` (parse only): standard library. |
| 7. Generic by default | No project names; the README section is generic. |
| 8. Executable evidence | Every AC and SC maps to a test in [quickstart.md](quickstart.md), including refusals, kills, damage and concurrency. |
| 9. Provisional decisions (BL-INV-006) | This plan, its ADR proposals and its decisions are agent-provisional; no artifact calls them approved. |

## Architecture Boundaries

- **Affected areas**: the pinned standard's `tools/setup` (stage, journal, record, lock, recovery, `--check` states) and `tools/spec_workflow/launcher.py` (shared checkout lock, two refusals); `tools/spec_workflow/run.py` (run-format record); the standard manifest `tools/cli.toml`; the global command `tools/ballast` (cache lock, record and verification, `preview`, not-fetched message); `README.md`.
- **Contracts and data flow**: `ballast setup` → CLI verifies or fetches the cache → standard's `tools/setup` locks the checkout, recovers, builds the stage, validates, switches, writes `installation.json`. `ballast run|ledger|intake` → CLI → launcher checks journal, lock, pin versus record, then trust. `ballast preview <ref>` → CLI verifies or fetches `<ref>` → runs `<ref>`'s own setup in a disposable project → diffs against `installation.json` or a disposable build of the pin. Ownership stays single: setup owns the installation record and fingerprint, the launcher owns trust and `state_dir`, the CLI owns the cache; `tools/setup` loads `state_dir`, `digests` and `IN_PROGRESS` from the standard's own `launcher.py` instead of copying them. Contracts: [setup.md](contracts/setup.md), [operator-state.md](contracts/operator-state.md), [cache.md](contracts/cache.md), [preview-cli.md](contracts/preview-cli.md), [launcher-and-manifest.md](contracts/launcher-and-manifest.md).
- **Architecture references**: [constitution](../../.specify/memory/constitution.md) BL-INV-001 to BL-INV-006; [ADR-0002](../../docs/adr/0002-cli-standard-manifest.md) (manifest as data), extended here; [roadmap](../../docs/plans/2026-10-02-product-roadmap.md) Phase 1 items 5 and 6; [v1.0 target](../TECHNICAL-SPEC.md#91-v10-target); [project workflow R2 boundaries](../../docs/policies/project/workflow.md).
- **Proposed architecture decisions** (agent-provisional; an ADR under `docs/adr/` is written with the implementation and becomes accepted only when the PR merges):
  1. **ADR-0006 Recoverable installation.** Setup stages, journals and switches installations; the journal, installation record and checkout lock live in operator state; the installation record, not the stamp, defines "current and verified"; the launcher holds a shared checkout lock and refuses an unfinished setup or a pin that differs from the installed ref (R1 to R5, R11, R13).
  2. **ADR-0007 Verified cache and update preview.** The CLI publishes each cached version with a content record under a per-version lock and verifies it before setup and preview; `ballast preview` builds the target with its own setup in a disposable project; `tools/cli.toml` gains `[setup] recoverable` and `[runs] format|resumes`, and runs record their format (R6 to R10).

## Repository Impact

| Path | Change |
| --- | --- |
| `tools/setup` | Split building from switching: `Setup` builds into a given project root (the stage) instead of `self.root`; new attempt lifecycle (lock, recover, preflight, stage, validate, switch, verify, commit); installation record; verified worktree copy into the stage; `--check` states `interrupted`, `stale: pinned …`, `modified: <path>`; failure messages per stage; `INSTALLED` entry `.ballast` becomes `.ballast/spec_workflow` and `.ballast/.setup-version`; one `entries(root)` rule and a `DISCARDED` list (F-002); the `PRESERVED` restore writes only in the stage and the checkout's constitution is created only when absent; a new `IGNORE_PROBES` entry for `.ballast/setup/`; refusal of symlinked ancestors and link-safe work-area removal (F-007). |
| `tools/spec_workflow/launcher.py` | Shared `checkout.lock` taken before the journal is read and kept through `execv` (F-006); refusals for an unfinished setup and for pinned ≠ installed (valid record only, F-003); `trust` and `discard-runs` hold the shared lock and refuse during an unfinished setup (F-005); `status --json` reports both; a `read_record` helper shared with setup. |
| `tools/spec_workflow/run.py` | `RUN_FORMAT` constant, written as `run-format.json` into the run archive at start; a test keeps it equal to `tools/cli.toml [runs] format`. |
| `tools/cli.toml` | `[setup] recoverable = true`; `[runs] format`, `resumes`. `[cli] minimum` unchanged (R7). |
| `tools/ballast` | Per-version fetch lock; content record and single-rename publication; verification and refetch before `setup`; `preview <ref> [--json]`; not-fetched refusal names the installed ref; usage and module docstring. |
| `README.md` | New "Updating the pinned version" section: update the CLI first, `ballast preview`, change the pin, `ballast setup`, review, `ballast trust`, checks; retry after a failed setup; rollback to the previous pin; what a version older than this feature does not guarantee. Adjust the reinstall sentence in "Installing the Spec Kit workflow". |
| `docs/adr/0006-recoverable-installation.md`, `docs/adr/0007-verified-cache-and-update-preview.md` | New; status agent-provisional until merge. |
| `tests/test_setup.py` | Stage, validation, switch, recovery table, fault injection per stage, kills at ≥ 5 points, locks, no-op, worktree copy verification, constitution and project policy preservation. |
| `tests/test_ballast.py` | Cache lock, record, verification, refetch, refusal, concurrent fetch count, not-fetched message. |
| `tests/test_preview.py` | New: preview report and JSON, run compatibility, path and ignore impact against an actual update, read-only snapshot, non-recoverable target. |
| `tests/test_spec_workflow.py` | Launcher lock and refusals, `status --json`, run-format record, the format-bump guard. |
| `tests/test_doctor.py` | `setup-current` shows `interrupted` and `stale: pinned …` details. |

## Feature Artifacts

```text
specs/14-recoverable-install/
├── intent.md
├── spec.md
├── plan.md             # this file
├── research.md         # Phase 0 decisions R1–R13
├── data-model.md       # entities, locations, state transitions, rollback table
├── contracts/
│   ├── setup.md                    # setup order, messages, exit codes, --check
│   ├── operator-state.md           # installation.json, setup-attempt.json, locks
│   ├── cache.md                    # cache layout, record, fetch and verify
│   ├── preview-cli.md              # ballast preview report, JSON, exit codes
│   └── launcher-and-manifest.md    # launcher refusals, run format, cli.toml
├── quickstart.md       # validation scenarios mapped to ACs and SCs
├── checklists/
├── autonomous/
├── tasks.md            # next: speckit-tasks
├── decisions.md        # only if implementation discovers one
└── reviews/
```

## Plan review resolutions

The plan review ([reviews/plan.md](reviews/plan.md)) found four medium and three low items. Each is resolved in the design artifacts above; the review report's Resolution section names the exact change.

- **F-001** (rollback of removed entries): the journal flags each entry `new` or not, and rollback is keyed on that flag ([data-model](data-model.md#setup-attempt)); a kill test uses a version that removes an entry.
- **F-002** (one entry set): `entries(root)` is the single rule for switch, record, verification and copy; other stage outputs are either in `DISCARDED` or fail `validate stage paths`; the preview compares like with like ([R1](research.md#r1-build-into-a-stage-project-then-switch-entry-by-entry), [R8](research.md#r8-the-update-preview-is-a-cli-command-that-builds-the-target-in-a-disposable-project)).
- **F-003** (stale record): a record is valid only while its fingerprint equals the live stamp ([R3](research.md#r3-the-installation-record-is-the-authority-for-current-and-verified)); a test covers B → pre-feature A → B.
- **F-004** (cache guarantees under an old CLI): kept as a scope limitation, recorded in [DEC-0001](decisions.md) for the merge review.
- **F-005**, **F-006** (launcher lock order, trust during setup): adopted ([launcher contract](contracts/launcher-and-manifest.md)).
- **F-007** (link safety in the work area): adopted as validation check (6) and link-safe deletion ([R4](research.md#r4-validation-before-the-switch-verification-after-it)); the security review confirms it.

## Complexity Tracking

No constitution violations.
