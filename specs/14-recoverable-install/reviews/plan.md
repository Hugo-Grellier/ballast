# Plan review: Recoverable installs and pin updates

- Review: plan (engineering review of the design before tasks)
- Reviewer: claude/claude-opus-5-5, fresh context, agent-provisional (not human approval)
- Artifact: [`plan.md`](../plan.md), with [`research.md`](../research.md), [`data-model.md`](../data-model.md), [`quickstart.md`](../quickstart.md) and the five contracts under [`contracts/`](../contracts/)
- Verdict: approved, with four medium items the tasks phase must carry (listed in the draft) and three low items for implementation and security review

## What was read

- Intent and authority: [`intent.md`](../intent.md) (PD-0007) and [`spec.md`](../spec.md) (AC-001 to AC-024, FR-001 to FR-020, SC-001 to SC-007, Assumptions, Edge Cases); the run record [`autonomous/record.md`](../autonomous/record.md) (PD-0001 to PD-0007, R2 notice).
- Policies: `AGENTS.md`, `docs/policies/workflow.md` (risk, supervision modes, review triggers), `docs/policies/project/workflow.md` (Ballast R2 boundaries), `docs/policies/engineering.md`. `docs/policies/project/engineering.md` does not exist. `tasks.md` and `decisions.md` do not exist yet; this review runs before tasks.
- Code the plan claims as evidence: `tools/setup` (`INSTALLED`, `PRESERVED`, `LOCAL_STATE`, `PROMISED`, `IGNORE_PROBES`, `remove_installed`, `matching_primary`, `copy_from_primary`, `install_spec_kit`, `install_standard`, `check`, `main`) and `tools/spec_workflow/launcher.py` (`state_dir`, `digests`, `BASES`, `SKIPPED`, `_refusal`, `_trust`, `_discard`, `_remove_tree`, `main` and its `execv`). ADR numbering: `docs/adr/` holds 0001 to 0005, so the proposed 0006 and 0007 are the next free numbers (renumbered 0007 and 0008 after feature 19 took 0006).
- Live installation in this worktree: the ignored paths setup produced (`git status --ignored`), and a search of the installed `.specify/` and `.ballast/` files for the absolute checkout path. None was found, so the plan's validation check (3) ("no staged text file contains the stage's absolute path") does not reject today's build.

## How the plan was checked

1. **Requirement coverage.** Each FR was traced to a research decision, a contract and a quickstart scenario. Every AC and SC has a scenario; the kill test names at least five points (SC-001); concurrency is repeated 20 times (SC-004); the README test checks that documented commands exist (AC-024). FR-001/002 map to R1 and R4, FR-003/004 to R2 and R11, FR-005 to R13 and the "never touched" list, FR-006 to keeping the work area under `.ballast/` (outside `launcher.BASES`), FR-008 to FR-010 to R5 and R6, FR-011 to R3, FR-012 to R6, FR-013 to the worktree copy contract, FR-014 to R5, FR-015 to FR-017 to R8 to R10, FR-018 to the "Never" sections, FR-019 to R6 and AC-022, FR-020 to the README row.
2. **Source authority and single ownership.** Setup owns the installation record, the launcher owns trust and `state_dir`, and the CLI owns the cache. `tools/setup` imports `state_dir`, `digests` and `IN_PROGRESS` from the standard's own launcher instead of copying them. Journal, record and locks live in operator state, outside agent write authority (BL-INV-002), and the stamp is demoted to a compatibility artifact. The run-format constant is duplicated between `run.py` and `tools/cli.toml`, with a test that keeps them equal, following the existing `TEMP_ROOTS` precedent.
3. **Partial failure and recovery.** The state machine (`staging` → `switching` → `committed`), the per-entry rollback table and the post-rollback verification against `previous_record` were walked for a kill at each transition and inside the switch. Rollback is idempotent across a second kill: after the first rename of row 3, the state is that of row 2. Two gaps are in the draft: entries the new version removes, and a record that has gone stale.
4. **Concurrency.** The exclusive and shared `flock` interleavings between setup and `run`, `ledger` and `intake` were checked in both orders. Each order either refuses or proceeds safely, and the kernel releases the lock on death, so FR-010 needs no PID heuristic. `subprocess` closes inherited descriptors by default, so agents spawned by `run.py` do not keep the lock alive. No workflow tool invokes `tools/setup`, so the shared lock held across `execv` cannot deadlock a run against itself. `trust` and `discard-runs` check only that the journal exists and take no lock; this is in the draft as a low item.
5. **Trust model (R2).** `BASES` covers all of `.specify` minus `SKIPPED`, so every `.specify` entry setup switches is a trusted input. A rolled-back rename restores identical bytes, so AC-007 holds. The launcher gains refusals and loses none. `trust` refuses mid-attempt. Setup never writes `trusted.json` and never clears `in-progress`.
6. **Compatibility.** Old setups after a rollback, old CLIs against a new standard, caches written by an old CLI, and runs without a recorded format were each traced through the plan. The old-CLI and stale-record cases are in the draft.
7. **Complexity.** The new concepts (journal, record, two locks, cache record, preview) each answer a stated FR. No new dependency is added. Fault injection uses no production hook (R12).

## Reviews this change still needs

The run is R2 and touches what `ballast` downloads and executes (the cache and `ballast preview` running a target's `tools/setup`) and the paths `tools/setup` installs, removes or preserves. Security and architecture review are therefore required, and documentation review is required for `README.md` and the two ADRs. The security review should cover:

- the preview executing an unpinned target's setup with operator authority;
- link-safety of setup's renames and deletions in the agent-writable `.ballast/setup/` work area;
- the shared lock's lifetime across `execv`.

## Findings

The full reasons are in the review draft [`autonomous/drafts/plan-review.json`](../autonomous/drafts/plan-review.json); F-003's reason was shortened there to fit the 1,000-character field limit, with its meaning unchanged.

| ID | Class | Severity | Location | Summary |
|---|---|---|---|---|
| F-001 | implementation bug | medium | data-model.md rollback table | Rollback keyed only on the filesystem does not cover entries the new version removes; a kill during the switch could delete part of the previous installation. |
| F-002 | spec ambiguity | medium | research.md R1/R4, contracts/preview-cli.md | Switch, validation and preview use different definitions of the installation; Spec Kit byproducts such as `.specify/.workflow-install.lock` fall between them. |
| F-003 | implementation bug | medium | research.md R3, contracts/operator-state.md | `installation.json` goes stale after a pre-feature setup runs (rollback to an older version), misleading the pinned/installed messages, removal and `--check`. |
| F-004 | spec ambiguity | medium | research.md R7 | Keeping `[cli] minimum` means an older CLI gives none of the cache guarantees FR-009/FR-012 state unconditionally. |
| F-005 | implementation bug | low | contracts/launcher-and-manifest.md | `trust` and `discard-runs` take no lock and can race a setup that has not yet journaled `switching`. |
| F-006 | spec ambiguity | low | contracts/launcher-and-manifest.md | The journal check precedes the lock check, so a running setup is reported as interrupted. |
| F-007 | architecture issue | low | data-model.md | Renames and deletions in the agent-writable work area are not required to be link-safe. |

## Resolution

Plan decision by the driving agent (the author role), after the Autonomous run blocked at `record-plan-review`. Every medium finding is resolved in the design artifacts; the low ones are adopted too, because each fix is small.

- **F-001 — resolved.** The journal's `entries` carry a `new` flag; [data-model.md](../data-model.md#setup-attempt) replaces the rollback table with one keyed on that flag, adds the rows for removed entries, and verifies a rollback against `before` (the live digests taken when the attempt started, so a pre-feature installation without a record is verified too). [operator-state.md](../contracts/operator-state.md) shows the new fields. Tasks carry a kill test with a version that drops an entry.
- **F-002 — resolved.** One rule, `entries(root)`, defines the installation for the switch, the record, live verification, the worktree copy and the no-op check ([R1](../research.md#r1-build-into-a-stage-project-then-switch-entry-by-entry)). Stage outputs outside it are either in the explicit `DISCARDED` list (`.specify/.workflow-install.lock`) or fail `validate stage paths` ([R4](../research.md#r4-validation-before-the-switch-verification-after-it)). The preview takes both sides with one procedure: record against record when both versions are recoverable, otherwise walk against walk of disposable builds ([R8](../research.md#r8-the-update-preview-is-a-cli-command-that-builds-the-target-in-a-disposable-project), [preview contract](../contracts/preview-cli.md)).
- **F-003 — resolved.** A record is valid only while its fingerprint equals the live `.ballast/.setup-version`; every reader ignores a stale one ([R3](../research.md#r3-the-installation-record-is-the-authority-for-current-and-verified), [operator-state.md](../contracts/operator-state.md)). The removal set is the entry rule on the live checkout (whose `docs/policies/*.md` glob finds policies only an older version installed) plus a valid record's entries. Tasks carry a B → pre-feature A → B test.
- **F-004 — resolved as a recorded limitation.** [DEC-0001](../decisions.md) keeps `[cli] minimum` and states that the cache guarantees need a CLI that includes this feature; the README update section says to update the CLI first. Listed for the merge review.
- **F-005 — adopted.** `trust` and `discard-runs` hold the shared checkout lock while they work and refuse during a setup or an unfinished attempt ([launcher contract](../contracts/launcher-and-manifest.md)).
- **F-006 — adopted.** The launcher takes the lock before it reads the journal.
- **F-007 — adopted.** Setup refuses when an ancestor of a live entry or of the work area is a symbolic link, before staging and again before switching, and deletes the work area with the launcher's link-safe `_remove_tree` ([R4](../research.md#r4-validation-before-the-switch-verification-after-it)). The security review still covers it.
