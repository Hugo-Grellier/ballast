# Plan review: Setup trusts a checkout it just installed

- Review: plan (engineering, independent context)
- Reviewer: claude/claude-opus-5-5, Autonomous run `38380ec3`; agent-provisional
- Artifacts: `plan.md`, `research.md` (R1 to R19), `data-model.md`, `contracts/setup-trust.md`, `contracts/launcher-and-doctor.md`, `quickstart.md`, judged against `spec.md` (FR-001 to FR-020, AC-001 to AC-027), `intent.md` (PD-0005), `discovery.md` and the run record.
- Policies read: `AGENTS.md`, `docs/policies/workflow.md`, `docs/policies/project/workflow.md`, `docs/policies/engineering.md` and the engineering review skill. `docs/policies/project/engineering.md` does not exist. `tasks.md` and `decisions.md` do not exist yet (plan stage).
- This report replaces the one written in the earlier, ineligible run `b48b609a`. The review was done again from scratch against the artifacts as they now stand. Since that run, the artifacts changed only in how they attribute the D-02 narrowing (agent inference `[I]`, listed for merge review); the design itself did not change.

## What was checked

**Requirement coverage.** Every FR maps to a research decision, a data-model row or a contract step. Every AC from AC-001 to AC-027 has a row in `quickstart.md` with a test module or a review step. The eligibility table in `data-model.md` puts every local refusal (rows 1 to 8b) before the only network step (row 9). That matches FR-004, AC-014 to AC-016 and the contract's claim that an ineligible checkout costs no network request. The non-goals still hold: the plan records no trust after an agent step, accepts no unreviewed `ballast.toml`, and leaves the comparison and `BALLAST_TAMPERED` unchanged. `_trust_refusal` is untouched and never reads provenance (R12, FR-015).

**Source authority and the trust boundary.** The launcher owns all three records in operator state: the baseline, its provenance and the reviewed-repositories record. It writes them through `record_baseline` and `_add_reviewed`. Setup only decides whether to call it (R1), so `trusted.json` keeps a single owner. A reviewed reference has two possible sources:

- the operator's own baseline, which counts only when its provenance is absent (legacy) or names `trust` and is bound, and fails closed otherwise (R7);
- the default branch of a repository in a record that only `ballast trust` writes (R8).

A forged `HEAD`, local ref, `origin` or `insteadOf` cannot create eligibility, because the snapshot bytes must still equal a reference observed in a throwaway repository with its own object store (R5, R9). Only `origin`'s scheme is read, as `branch_sync._url` does today; I checked this in `tools/spec_workflow/branch_sync.py`. A setup-recorded baseline never serves as a reviewed reference, so every chain of setup recordings ends at an operator review or the default branch.

**Code claims checked against the tree.**

- `launcher.BASES` is `ballast.toml`, `.ballast/spec_workflow`, `.specify` and `.venv`. `SKIPPED` covers `.specify/workflows/runs` and `.specify/workflow-state`, so run state lies outside the comparison, as R11 and the spec's edge case say.
- Preparation is started by the global CLI (`tools/ballast` `prepare`, which runs the pinned `tools/setup --prepare`) before the launcher runs. A run record therefore does not yet exist when the first `ballast run` prepares a worktree, and row 3 does not refuse every preparation-through-run.
- `autonomy.GIT_HARDENING` exists. The branch-sync throwaway environment (`DROPPED_ENV`, `_child_path`, `GIT_NO_REPLACE_OBJECTS`, `GIT_GRAFT_FILE`, `GIT_TERMINAL_PROMPT=0`, empty `GIT_ASKPASS`, `SSH_ASKPASS_REQUIRE=never`, the dropped display variables) matches what R9 lists.
- `_url` is already a test seam that `tests/test_branch_sync.py` patches, so delegating it keeps that seam.

**Partial failure and concurrency.**

- R12 writes provenance before `trusted.json`, each atomically. After a crash between the two writes, the old baseline reads as `trust`.
- The post-write snapshot recheck closes the window between the check and the write (R3).
- The reviewed record is read-modify-write under `flock` (R8).
- Recording happens only after the journal is gone, so an interrupted attempt never records (R2). The exclusive lock keeps `run`, `ledger`, `intake` and `trust` out while the decision is written. The network step holds that lock for at most 150 s, a bounded cost the plan accepts in R2.

**Governing documents.**

- ADR-0015 is the next free number.
- ADR-0007's clause "never records trust" exists as quoted.
- ADR-0011's "Preparation never reads any `trusted.json`" exists as quoted, but ADR-0011 also says preparation is local-only, never downloads and reaches the trust preflight with no network. R17 does not supersede those statements.
- The constitution amendment goes through governance with a recorded reason (R17). Complexity Tracking justifies the amendment, the machine-wide record and the new network read.

## Areas examined most closely

- How ADR-0011's local-only and no-network wording compares with the network observation the plan adds to preparation.
- Whether R9's environment is the "same trusted path" FR-004 names, or a second copy of it.
- The contract's step order (keep a matching baseline first) against the remedy AC-019 names.
- The rollback after the post-write recheck, read against FR-008.
- How recording through the operator-baseline alternative uses up that alternative for later setups.
- What `ls-tree` reports for a configuration path that is not a regular file on the default branch.

R4 already states that a `.venv` in the checkout, which setup never writes, makes a checkout ineligible.

## Verdict

The design meets the spec, and every refusal fails closed. Nothing I examined lets an unreviewed input be recorded or widens an agent's authority beyond the operator's D-02 answer. The items in the review draft can be resolved while ADR-0015, the module and the tasks are written. They are carried to the security and architecture specialist reviews and to merge review.

<!-- ballast-findings: begin -->
## Findings (recorded from the review draft)

- F-001 (medium, architecture-issue, accepted-provisionally): ADR-0011 says --prepare is local-only, never downloads, and reaches the trust preflight with no network, but R17 supersedes only its trusted.json clause while the plan adds a live network observation to preparation. ADR-0015 as planned would leave ADR-0011 contradicting the new behavior. Resolvable by extending R17's superseded-clause list when ADR-0015 is written (the download wording stays true; the no-network outcome does not); carried to tasks and the architecture review.
- F-002 (medium, architecture-issue, accepted-provisionally): R9 and the setup-trust contract restate branch synchronization's throwaway Git environment (DROPPED_ENV, PATH restriction, prompt and askpass variables, display variables) instead of sharing it; only the URL rule moves to a shared function. Two copies of security-relevant rules can drift, against FR-004's 'same trusted path'. Resolvable by sharing the environment builder when setup_trust.py is written; carried to tasks and the security review.
- F-003 (low, spec-ambiguity, open): Contract step 1 keeps a matching baseline before the local conditions run, so with a BALLAST_TAMPERED marker and a matching baseline setup reports the baseline unchanged instead of naming the remedy AC-019 asks for. Nothing is recorded and the launcher still refuses; message gap only.
- F-004 (low, spec-violation, open): The post-write recheck and OSError paths remove the baseline record_baseline just wrote; if that write replaced an older operator-recorded baseline, the older one is lost, departing from FR-008 in a rare race. Fails closed: ballast trust is needed again. Keeping the previous bytes for restore would close it.
- F-005 (low, spec-ambiguity, open): Recording through the operator-baseline alternative (row 8a) replaces trust provenance with setup, so the next pin update with unchanged configuration can no longer use that offline alternative and needs the network or ballast trust. Fails closed; worth stating in the docs or carrying the operator reference forward.
- F-006 (info, spec-ambiguity, open): R9 compares only the blob ID from ls-tree; a default-branch ballast.toml that is a symlink (mode 120000) whose target text equals the checkout file's bytes would match. Not a practical widening, but requiring mode 100644 or 100755 in the parsed ls-tree entry makes the comparison exact.
<!-- ballast-findings: end -->
