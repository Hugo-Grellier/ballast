# Implementation Plan: Setup trusts a checkout it just installed

**Branch**: `feat/55-setup-trust` | **Date**: 2026-10-06 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/55-setup-trust/spec.md` (intent agent-provisional, PD-0005, digest in [intent.md](intent.md))

**Risk**: R2. The plan changes the launcher's trust model and who may record a trust baseline ([R2 boundaries](../../docs/policies/project/workflow.md#r2-boundaries)), and adds a network read with the operator's Git credentials to setup. This is Autonomous run `38380ec3`: every design decision below is agent-provisional, not human-approved, and merging the PR is the single human approval (BL-INV-006). D-01, D-02 and D-03 are the operator's answers recorded in the [discovery brief](discovery.md) (commit f290079); D-04, D-05 and the reviewed-repositories record are agent-provisional (PD-0002 to PD-0004). Two agent inferences only narrow D-02 and are listed for merge review: the default branch is observed live from the pinned repository, and only a repository the operator already reviewed counts.

## Summary

After `ballast setup` installs and verifies the pinned standard, or after the first `ballast run`, `ledger` or `intake` prepares a new worktree (#15), and while that command still holds the exclusive checkout lock, a new trusted module `setup_trust.py` decides whether to record the checkout's trust baseline. It takes one snapshot of the protected inputs and records it only when every condition holds: setup runs from the pinned copy outside the checkout; no tamper or in-progress marker, saved run state or unfinished operator-state run exists; every protected input other than `ballast.toml` and the constitution is exactly what the installation record says setup wrote; a linked worktree's `.git` pointer names a worktree entry of its own repository; `ballast.toml` and the constitution are committed and unchanged from `HEAD`; and those two files equal either the checkout's previous operator-recorded baseline (checked first, offline) or the files on the default branch of the repository pinned in `[github] repository`. The default branch is observed live, only for a repository in a machine-wide operator-state record that only `ballast trust` writes, with `ls-remote` and a depth-1, blob-less fetch into a throwaway repository with its own object store, through ADR-0005's hardened path and the operator's own Git credentials; blob IDs are compared. Anything else records nothing and says why and that `ballast trust` is needed, with the installation's result unchanged.

The launcher gains one writer, `record_baseline`, used by both `ballast trust` and setup, which writes the unchanged `trusted.json` plus a provenance record bound to its exact bytes. `ballast trust` also adds the trusted `ballast.toml`'s repository to the reviewed record. `status --json` reports `baseline_source`, and doctor shows it. The comparison before every `run`, `ledger` and `intake`, its messages and the tamper marker do not change. A new ADR-0014 supersedes the ADR-0007 and ADR-0011 clauses, and the constitution's BL-INV-002 is amended (D-01). Decisions R1 to R19 are in [research.md](research.md).

## Technical Context

**Language/Version**: Python ≥ 3.11 standard library only, under `python3 -I -S`.

**Primary Dependencies**: None new at runtime. External: `git` 2.41 or later resolved outside every working tree and temp root (the ADR-0005 floor), used for local plumbing in the checkout and `init`, `ls-remote`, `fetch`, `rev-parse`, `ls-tree` in a throwaway repository. The operator's Git credentials for the pinned GitHub repository, over HTTPS or SSH as `origin`'s scheme selects. No `gh`.

**Storage**: Operator state only. Per checkout `<state>/`: `trusted.json` (unchanged format, now written atomically), new `trusted-source.json` (provenance), temporary `setup-trust/<random>/` (throwaway repository, removed). Machine-wide `$XDG_STATE_HOME/ballast/reviewed-repositories.json` and its `.lock` (new). Reads `installation.json` and `runs/<id>/run.json`. See [data-model.md](data-model.md).

**Testing**: `unittest`, offline; a local bare repository stands in for the pinned GitHub repository through the `setup_trust.repository_url` seam; real temporary Git repositories and linked worktrees; an argv log proves which Git commands ran and that none ran when a local condition fails. One networked end-to-end run on a scratch repository, recorded in the PR. See [quickstart.md](quickstart.md).

**Target Platform**: The qualified 1.0 host: Linux with a systemd user session, GitHub.

**Project Type**: The standard's install script (`tools/setup`), its workflow tools (`tools/spec_workflow/`) and the global CLI (`tools/ballast`).

**Performance Goals**: Local conditions add one digest pass over the protected inputs (already done by `current()`). The network path adds one `ls-remote` and one depth-1 blob-less fetch (one commit and its trees), bounded at 30 s and 120 s; it runs only when the operator-baseline alternative fails and the repository is reviewed.

**Constraints**: Standard library only, `-I -S`; nothing that decides eligibility comes from agent-writable data unless a change to it only makes the checkout ineligible (FR-020); no program named by the checkout's Git configuration, attributes or hooks runs; never prompts; launcher comparison, refusal messages and `BALLAST_TAMPERED` unchanged (FR-015); existing trust and refusal tests pass unedited (AC-023); projects pinned to earlier versions and older global CLIs keep working.

**Scale/Scope**: New `tools/spec_workflow/setup_trust.py` about 350 lines; `launcher.py` about +80 (`record_baseline`, provenance reading, reviewed record, `status` key, `_trust` changes); `tools/setup` about +40 (calls and output); `branch_sync.py` about −8 (URL rule moved); `tools/ballast` about +15 (doctor detail); docs and one ADR.

No NEEDS CLARIFICATION remains.

## Constitution Check

*Gate before Phase 0, re-checked after Phase 1. Result: **PASS with one justified amendment** both times: BL-INV-002 is amended as the operator decided in D-01, through the constitution's governance (R2 change, recorded reason), not violated silently. See Complexity Tracking.*

| Principle | How the design holds it |
| --- | --- |
| 1. Projects own only their files (BL-INV-001) | Setup writes nothing new in the checkout; every new record is operator state. The constitution and `ballast.toml` are read, never written. |
| 2. Nothing executes from a writable checkout before trust (BL-INV-002) | **Amended** (D-01): the launcher still refuses until a baseline matches; the baseline may now also be recorded by the operator's setup or preparation under ADR-0014's conditions. Nothing from the checkout executes: the decision runs in the pinned copy (and records nothing when setup runs from the checkout, R16); Git is resolved outside working trees, with hooks, fsmonitor, filters, replace refs and grafts disabled; the throwaway has its own empty configuration and object store. The tamper and in-progress checks are unchanged and also block recording. |
| 3. Delegated authority (BL-INV-003) | An agent cannot reach a recorded baseline: an agent step holds the in-progress marker (setup refuses, AC-021); recording needs every protected input exactly as installed and the configuration equal to what a human reviewed (default branch of an operator-reviewed repository, or the operator's own baseline); the reviewed-repositories record is written only by `ballast trust`. |
| 4. A project picks a version, never a source (BL-INV-004) | No new download of the standard. The only new network read is of the project's own pinned repository, named in the reviewed `ballast.toml`, on the operator's credentials, as ADR-0005 already allows. |
| 5. Postconditions over exit codes (BL-INV-005) | Recording depends on content checks (digests against the record, blob IDs against the observed commit) and a post-write snapshot recheck, never on a command's exit status alone. |
| 6. Portable, dependency-free tools | Standard library only; Git via fixed list argv; `--check` does not import the new module. |
| 7. Generic by default | No project names; messages and docs are generic. |
| 8. Executable evidence | Every AC maps to a test or a review step in [quickstart.md](quickstart.md), including every refusal, tamper, network-failure and repointing path. |
| 9. Provisional decisions (BL-INV-006) | This plan, ADR-0014 (proposed until merge), the constitution amendment and R1 to R19 are agent-provisional; no artifact calls them approved. |

## Architecture Boundaries

- **Affected areas**: the pinned standard's install script `tools/setup` (calls the trust decision at the end of `main` and `prepare`, prints its verdict, removes a stale provenance record with a stale baseline); new `tools/spec_workflow/setup_trust.py` (eligibility, default-branch observation, decision); `tools/spec_workflow/launcher.py` (`record_baseline`, provenance reading, reviewed-repositories record, `_trust`, `status --json`); `tools/spec_workflow/branch_sync.py` (uses the shared URL rule); the global command `tools/ballast` (doctor detail only).
- **Contracts and data flow**: `ballast setup` → pinned `tools/setup` → lock → recover → install or no-op → `setup_trust.settle` → [keep | local conditions → operator baseline | reviewed record → throwaway `ls-remote` + `fetch` → blob comparison] → `launcher.record_baseline(source="setup")` → recheck → release lock. Preparation follows the same path after its attempt. `ballast trust` → launcher `_trust` → `record_baseline(source="trust")` → reviewed record. `ballast doctor` → launcher `status --json` (`baseline_source`). Ownership: the launcher owns every operator-state trust record and the comparison; setup owns the installation and only asks `setup_trust`; doctor reads JSON only. Contracts: [setup-trust.md](contracts/setup-trust.md), [launcher-and-doctor.md](contracts/launcher-and-doctor.md).
- **Architecture references**: [constitution](../../.specify/memory/constitution.md) BL-INV-002, BL-INV-003, BL-INV-006 and governance; [ADR-0002](../../docs/adr/0002-cli-standard-manifest.md) (doctor reads launcher JSON); [ADR-0005](../../docs/adr/0005-launcher-branch-synchronization.md) (pinned repository, hardened Git, throwaway, environment); [ADR-0007](../../docs/adr/0007-recoverable-installation.md) (lock, journal, record; "never records trust" superseded); [ADR-0011](../../docs/adr/0011-worktree-preparation.md) (preparation; "never reads a baseline" superseded for the checkout's own); [technical spec §9.1](../TECHNICAL-SPEC.md#91-v10-target); [roadmap phase 2 items 3 and 7](../../docs/plans/2026-10-02-product-roadmap.md).
- **Proposed architecture decisions** (agent-provisional; written with the implementation, accepted only when the PR merges):
  1. **ADR-0014 Setup-recorded trust baseline.** The operator's `ballast setup` and worktree preparation record the checkout's baseline when the R2 to R16 conditions hold; the reviewed configuration is the pinned repository's default branch observed live through the hardened throwaway path, for a repository in the operator's reviewed record, or the checkout's previous operator-recorded baseline; provenance beside the baseline, reported by `status --json`; `ballast trust` writes operator provenance and the reviewed record. Supersedes ADR-0007 "never records trust" and ADR-0011 "never reads any `trusted.json`" for the checkout's own baseline.
  2. **Constitution 1.2.0**: BL-INV-002 amended as in [research R17](research.md#r17-governing-documents-fr-017-to-fr-019).

## Repository Impact

| Path | Change |
| --- | --- |
| `tools/spec_workflow/setup_trust.py` | New: `settle()`, the eligibility conditions in data-model order, `repository_url()`, the throwaway observer and blob-ID helpers, following [setup-trust.md](contracts/setup-trust.md). |
| `tools/spec_workflow/launcher.py` | `record_baseline()`; `TRUSTED_SOURCE`, `REVIEWED` names; `baseline_source(root, state)`; `reviewed_repositories()` reader and `_add_reviewed()` writer; `_trust` writes through `record_baseline` and adds the repository; `status --json` adds `baseline_source`; docstring. `_trust_refusal` untouched. |
| `tools/setup` | Lazy import of `setup_trust` from `STANDARD/tools/spec_workflow`; call `settle()` on the paths in the contract's table and print the verdict block in place of today's trust line; `fill_from_candidates` also removes a stale `trusted-source.json`; module docstring ("never records or reads a trust baseline" replaced). |
| `tools/spec_workflow/branch_sync.py` | `_url` delegates to `setup_trust.repository_url`, keeping the `_url` seam its tests patch. |
| `tools/ballast` | Doctor `_trust` appends the reported source to its detail. |
| `docs/adr/0014-setup-recorded-trust-baseline.md` | New; proposed until merge. |
| `docs/adr/0007-recoverable-installation.md`, `docs/adr/0011-worktree-preparation.md` | One "superseded in part by ADR-0014" note beside each affected clause. |
| `.specify/memory/constitution.md` | BL-INV-002 amended; version 1.2.0; amendment history entry with reason and compatibility. |
| `docs/plans/2026-10-02-product-roadmap.md` | Phase 2 items 3 and 7 reworded to the ADR-0014 conditions. |
| `specs/TECHNICAL-SPEC.md` | §9.1 "Status (#55)" paragraph. |
| `README.md` | Worktrees, Running the workflow, pin update and rollback: when setup or preparation records, the network and Git authority needed, the one `ballast trust` per project per machine, when `ballast trust` is still needed, doctor's source. |
| `templates/policies/spec-kit-workflow.md` | The trust section: the same, in policy form. |
| `tests/test_setup_trust.py` | New: eligibility matrix, observation (stand-in bare repository, argv log), recording, recheck. |
| `tests/test_setup.py` | New classes for setup and preparation flows (AC-001, AC-002, AC-005 to AC-009, AC-018, AC-021); existing classes unchanged. |
| `tests/test_spec_workflow.py` | New classes: `record_baseline`, provenance reading, reviewed record, `status --json` key, AC-022, AC-024; existing trust tests unchanged. |
| `tests/test_doctor.py` | Source in the trust detail; older launcher without the key. |
| `tests/test_branch_sync.py` | Unchanged; still patches `branch_sync._url`. |

## Feature Artifacts

```text
specs/55-setup-trust/
├── discovery.md        # input evidence
├── intent.md
├── spec.md
├── plan.md             # this file
├── research.md         # Phase 0 decisions R1–R19
├── data-model.md       # baseline, provenance, reviewed record, eligibility, transitions
├── contracts/
│   ├── setup-trust.md          # settle(): when, order, Git commands, output
│   └── launcher-and-doctor.md  # record_baseline, trust, status --json, doctor
├── quickstart.md       # AC → test map and end-to-end run
├── checklists/
├── autonomous/
├── tasks.md            # next: speckit-tasks
├── decisions.md        # only if implementation discovers one
└── reviews/
```

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
| --- | --- | --- |
| BL-INV-002 amended: a baseline may be recorded by the operator's setup or preparation, not only by `ballast trust` | Issue #55's outcome; the operator chose it in D-01, and the constitution's governance allows it as an R2 change with a recorded reason (R17) | D-01 option B (messages only) does not remove the per-checkout human command the Issue targets |
| A machine-wide reviewed-repositories record, with the reviewed configuration digests per repository (DEC-0008) | Without it, a repointed `[github] repository` whose default branch carries the same changed file would be trusted (AC-016, FR-005) | Trusting whichever repository `ballast.toml` names fails open; per-checkout records never exist in a fresh clone or worktree |
| A network read in setup and in preparation (which ADR-0011 kept offline) | Agent inference narrowing D-02 (listed for merge review): the reviewed default branch must be observed live, never from agent-writable local refs | Local remote-tracking ref: agent-writable; offline-only operation: covered by the operator-baseline alternative, but cannot trust fresh clones |
