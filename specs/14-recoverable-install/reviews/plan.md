# Plan review: Recoverable installs and pin updates

- Review: plan (engineering review of the design before tasks)
- Reviewer: claude/claude-opus-5-5, fresh context, agent-provisional (not human approval)
- Artifact: [`plan.md`](../plan.md), with [`research.md`](../research.md), [`data-model.md`](../data-model.md), [`quickstart.md`](../quickstart.md) and the five contracts under [`contracts/`](../contracts/)
- Verdict: approved, with four medium items the tasks phase must carry (listed in the draft) and three low items for implementation and security review

## What was read

- Intent and authority: [`intent.md`](../intent.md) (PD-0007) and [`spec.md`](../spec.md) (AC-001 to AC-024, FR-001 to FR-020, SC-001 to SC-007, Assumptions, Edge Cases); the run record [`autonomous/record.md`](../autonomous/record.md) (PD-0001 to PD-0007, R2 notice).
- Policies: `AGENTS.md`, `docs/policies/workflow.md` (risk, supervision modes, review triggers), `docs/policies/project/workflow.md` (Ballast R2 boundaries), `docs/policies/engineering.md`. `docs/policies/project/engineering.md` does not exist. `tasks.md` and `decisions.md` do not exist yet; this review runs before tasks.
- Code the plan claims as evidence: `tools/setup` (`INSTALLED`, `PRESERVED`, `LOCAL_STATE`, `PROMISED`, `IGNORE_PROBES`, `remove_installed`, `matching_primary`, `copy_from_primary`, `install_spec_kit`, `install_standard`, `check`, `main`) and `tools/spec_workflow/launcher.py` (`state_dir`, `digests`, `BASES`, `SKIPPED`, `_refusal`, `_trust`, `_discard`, `_remove_tree`, `main` and its `execv`). ADR numbering: `docs/adr/` holds 0001 to 0005, so the proposed 0006 and 0007 are the next free numbers.
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
