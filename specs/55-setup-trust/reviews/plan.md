# Plan review: Setup trusts a checkout it just installed

- Review: plan (engineering, independent context)
- Reviewer: claude/claude-opus-5-5, Autonomous run `b48b609a`; agent-provisional
- Artifacts: `plan.md`, `research.md` (R1 to R19), `data-model.md`, `contracts/setup-trust.md`, `contracts/launcher-and-doctor.md`, `quickstart.md`, judged against `spec.md` (FR-001 to FR-020, AC-001 to AC-027), `intent.md` (PD-0005), `discovery.md` and the run record.
- Policies read: `AGENTS.md`, `docs/policies/workflow.md`, `docs/policies/project/workflow.md`, `docs/policies/engineering.md`, the engineering review skill. `docs/policies/project/engineering.md` does not exist. `tasks.md` and `decisions.md` do not exist yet (plan stage).

## What was checked

Requirement coverage. Every FR maps to a research decision and every AC to a test location or review step in `quickstart.md`. The eligibility table in `data-model.md` orders all local refusals (rows 1 to 8b) before the only network step (row 9), which matches FR-004, AC-014 to AC-016 and the "no request for an ineligible checkout" claim. The non-goals (no trust after an agent step, no unreviewed `ballast.toml`, no change to the comparison or `BALLAST_TAMPERED`) are preserved: `_trust_refusal` is untouched and provenance is never read by it (R12, FR-015).

Source authority and the trust boundary. The baseline, its provenance and the reviewed-repositories record are all operator state owned by the launcher (`record_baseline`, `_add_reviewed`), and setup only decides whether to call it (R1), so the launcher stays the single owner of `trusted.json`. The reviewed reference is either the operator's own baseline, read fail-closed when provenance is unreadable or unbound (R7), or the default branch of a repository in a record only `ballast trust` writes (R8). A forged `HEAD`, local ref, `origin` or `insteadOf` cannot create eligibility, because the snapshot bytes must still equal a reviewed reference observed outside the checkout's object store (R5, R9). Only `origin`'s scheme is read, as `branch_sync._url` does today (verified in `tools/spec_workflow/branch_sync.py`).

Code claims verified against the tree. `launcher.BASES` includes `.venv` and `input_bases` adds a linked worktree's `.git` pointer only; `SKIPPED` covers `.specify/workflows/runs` and `.specify/workflow-state`, so run state is outside the comparison as R11 and the spec edge case say. `installed_digests` in `tools/setup` uses `launcher.digests`, so the installation record's `files` and the snapshot share one digest format, making R4's entry-by-entry comparison sound. `Setup.main` and `Setup.prepare` hold the exclusive lock across `recover`, the in-progress refusal, the `current` short-circuit and `attempt`, so the call sites listed in the contract exist and can run before the lock is released. `autonomy.GIT_HARDENING` and the branch-sync throwaway environment (`DROPPED_ENV`, `GIT_NO_REPLACE_OBJECTS`, `GIT_TERMINAL_PROMPT=0`, empty `GIT_ASKPASS`, `SSH_ASKPASS_REQUIRE=never`) match what R9 says it reuses. The test harness loads `tools/setup` in-process or in a child wrapper that patches module attributes, so the planned `setup_trust.repository_url` seam is reachable offline.

Partial failure and concurrency. Provenance is written before `trusted.json`, each atomically, and the crash case reads as `trust` for the old baseline (R12). The post-write snapshot recheck closes the check-to-write window (R3). The reviewed record is read-modify-write under `flock` (R8). Recording happens only after the journal is gone, so an interrupted attempt never records (R2).

Governing documents. ADR-0014 is the next free number. The two superseded clauses exist as quoted: ADR-0007 line "never records trust" and ADR-0011 "Preparation never reads any `trusted.json`". The constitution amendment is routed through governance with a recorded reason (R17), and the Complexity Tracking table justifies the amendment, the machine-wide record and the new network read.

## Areas examined most closely

How ADR-0011's description of preparation compares with what the plan adds to it; how the throwaway Git environment planned for `setup_trust` relates to the one branch synchronization already uses; the order of the contract's steps against the remedies AC-019 names; the rollback paths after the post-write recheck, read against FR-008; and what happens to the operator-baseline alternative and to an interrupted network step on the next setup. R4 already documents that a checkout `.venv`, never written by setup, makes a checkout ineligible. The review draft holds the resulting items.

## Verdict

The design meets the spec and keeps every refusal fail-closed; nothing examined lets an unreviewed input be recorded. The items in the review draft can be resolved while writing ADR-0014, the module and the tasks, and are carried to the security and architecture specialist reviews and to merge review.

<!-- ballast-findings: begin -->
## Findings (recorded from the review draft)

- F-001 (medium, architecture-issue, accepted-provisionally): ADR-0011 says preparation is local-only, never downloads and reaches the trust preflight with no network, but R17 supersedes only its trusted.json clause while the plan adds a network observation to preparation. ADR-0014 as planned would leave ADR-0011 contradicting the new behavior. Fixable by extending R17's list of superseded clauses when ADR-0014 is written; carried to tasks and the architecture review.
- F-002 (medium, architecture-issue, accepted-provisionally): R9 and the contract restate branch synchronization's throwaway Git environment (DROPPED_ENV, the PATH restriction, the prompt and askpass variables) instead of sharing it; only the URL rule moves to a shared place. Two copies of security-relevant rules can drift, against FR-004's same trusted path. Fixable by sharing the environment builder when the module is written; carried to tasks and the security review.
- F-003 (low, spec-ambiguity, open): Contract step 1 keeps a matching baseline before the local conditions run, so with a BALLAST_TAMPERED marker and a matching baseline setup reports the baseline unchanged instead of naming the remedy AC-019 asks for. Nothing is recorded; this is a message gap only.
- F-004 (low, spec-violation, open): The recheck and OSError paths remove the baseline record_baseline just wrote; if that write replaced an older operator-recorded baseline, the older one is lost, departing from FR-008 in a rare race. The result is fail-closed: ballast trust is needed again.
- F-005 (low, spec-ambiguity, open): Recording through the operator-baseline alternative (row 8a) replaces trust provenance with setup, consuming that alternative for later setups; a setup interrupted in the network step after a committed preparation leaves a current installation that later reports nothing to prepare without recording. Both fail closed to ballast trust; worth stating in the documentation or tasks.
<!-- ballast-findings: end -->
