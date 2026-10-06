# Autonomous run record

Run `38380ec3` for #55 (`specs/55-setup-trust`). Generated from the operator records; every check re-renders it, so an edit fails the next check. Every decision below is agent-provisional; merging the PR that contains this record is the only human approval.

## Mode and risk

- Mode start: autonomous at 2026-10-06T18:30:59+00:00 by operator
- Risk: R2 (scope-record); history: R2 at 2026-10-06T18:30:59+00:00
- Limits (default): 240 minutes wall time, 40 agent steps
- Spend: bounded by the agent-step limit; every agent step, retry and fix cycle counts; monetary spend is not measured
- Authoring integration: claude; review integration: claude
- Integration fallback: codex cannot start its own sandbox inside Ballast's confinement; claude takes both roles (DEC-0004)

## R2 notice

This is an R2 change. It was made without any prior human approval; the pre-change approval was agent-provisional (PD-0005).

R2 boundaries touched:

- agent authority
- launcher trust model

## Material provisional changes

- PD-0004 (clarification, agent-provisional): The default-branch alternative of D-02 counts only for a repository in an operator-state record of reviewed repositories that only ballast trust writes; the first checkout of a never-trusted repository needs one ballast trust.
- PD-0005 (intent, agent-provisional): Agent-provisional: spec.md is one coherent feature: setup and worktree preparation record the trust baseline only for exactly-installed inputs with reviewed committed configuration and no agent trace; everything else still needs ballast trust.
- PD-0007 (plan, agent-provisional): Agent-provisional: plan.md meets spec 55 (FR-001 to FR-020, AC-001 to AC-027); every refusal fails closed and the launcher comparison is unchanged; plan-review findings F-001 to F-006 are carried to tasks and specialist reviews.

## Provisional decisions

| ID | Point | Decision | Summary | Decided by | Artifact | Evidence | Superseded by |
| --- | --- | --- | --- | --- | --- | --- | --- |
| PD-0001 | scope | accept (agent-provisional) | Issue #55 is one independently specifiable outcome: a checkout whose protected inputs are exactly what a trusted ballast setup produced is trusted without a separate ballast trust; anything else still needs it. | claude/claude-opus-5-5 (author) | [.specify/feature.json](../../../.specify/feature.json) `b2888ca192d6` | [.specify/feature.json](../../../.specify/feature.json), <https://github.com/Hugo-Grellier/ballast/issues/55>, [docs/policies/spec-kit-workflow.md](../../../docs/policies/spec-kit-workflow.md), [docs/policies/project/workflow.md](../../../docs/policies/project/workflow.md), [docs/plans/2026-10-02-product-roadmap.md](../../../docs/plans/2026-10-02-product-roadmap.md) |  |
| PD-0002 | clarification | assume (agent-provisional) | D-04: setup records no baseline when any run state exists under .specify/workflows/runs or .specify/workflow-state, an operator-state run is unfinished, or the in-progress or BALLAST_TAMPERED marker exists. | claude/claude-opus-5-5 (author) | [specs/55-setup-trust/discovery.md](../../../specs/55-setup-trust/discovery.md) `b6f904a2816e` | [specs/55-setup-trust/discovery.md](../../../specs/55-setup-trust/discovery.md), [tools/spec_workflow/launcher.py](../../../tools/spec_workflow/launcher.py) |  |
| PD-0003 | clarification | assume (agent-provisional) | D-05: the baseline's source is a provenance file in operator state beside trusted.json, bound to its digest and reported by the launcher's status --json; missing or mismatched reads as operator trust. | claude/claude-opus-5-5 (author) | [specs/55-setup-trust/discovery.md](../../../specs/55-setup-trust/discovery.md) `b6f904a2816e` | [specs/55-setup-trust/discovery.md](../../../specs/55-setup-trust/discovery.md), [tools/spec_workflow/launcher.py](../../../tools/spec_workflow/launcher.py), [tools/ballast](../../../tools/ballast), [docs/adr/0002-cli-standard-manifest.md](../../../docs/adr/0002-cli-standard-manifest.md) |  |
| PD-0004 | clarification | assume (agent-provisional) | The default-branch alternative of D-02 counts only for a repository in an operator-state record of reviewed repositories that only ballast trust writes; the first checkout of a never-trusted repository needs one ballast trust. | claude/claude-opus-5-5 (author) | [specs/55-setup-trust/spec.md](../../../specs/55-setup-trust/spec.md) `4b7ebd8ada20` | [specs/55-setup-trust/spec.md](../../../specs/55-setup-trust/spec.md), [specs/55-setup-trust/discovery.md](../../../specs/55-setup-trust/discovery.md), [docs/adr/0005-launcher-branch-synchronization.md](../../../docs/adr/0005-launcher-branch-synchronization.md), [tools/spec_workflow/launcher.py](../../../tools/spec_workflow/launcher.py) |  |
| PD-0005 | intent | accept (agent-provisional) | Agent-provisional: spec.md is one coherent feature: setup and worktree preparation record the trust baseline only for exactly-installed inputs with reviewed committed configuration and no agent trace; everything else still needs ballast trust. | claude/claude-opus-5-5 (author) | [specs/55-setup-trust/spec.md](../../../specs/55-setup-trust/spec.md) `4b7ebd8ada20` | [specs/55-setup-trust/discovery.md](../../../specs/55-setup-trust/discovery.md), [specs/55-setup-trust/spec.md](../../../specs/55-setup-trust/spec.md), [.specify/workflow-state/issues/55.md](../../../.specify/workflow-state/issues/55.md), [specs/55-setup-trust/autonomous/record.md](../../../specs/55-setup-trust/autonomous/record.md), [docs/policies/project/workflow.md](../../../docs/policies/project/workflow.md), [docs/policies/spec-kit-workflow.md](../../../docs/policies/spec-kit-workflow.md), [docs/adr/0005-launcher-branch-synchronization.md](../../../docs/adr/0005-launcher-branch-synchronization.md), [docs/adr/0007-recoverable-installation.md](../../../docs/adr/0007-recoverable-installation.md), [docs/adr/0011-worktree-preparation.md](../../../docs/adr/0011-worktree-preparation.md), [.specify/memory/constitution.md](../../../.specify/memory/constitution.md) |  |
| PD-0006 | plan-review | accept-finding (agent-provisional) | Plan meets spec 55 and keeps every refusal fail-closed; two medium architecture items (ADR-0011 offline wording, duplicated Git environment) carried to tasks and specialist reviews. | claude/claude-opus-5-5 (reviewer) | [specs/55-setup-trust/plan.md](../../../specs/55-setup-trust/plan.md) `24baecb86646` | [specs/55-setup-trust/reviews/plan.md](../../../specs/55-setup-trust/reviews/plan.md), [specs/55-setup-trust/plan.md](../../../specs/55-setup-trust/plan.md), [specs/55-setup-trust/research.md](../../../specs/55-setup-trust/research.md), [specs/55-setup-trust/data-model.md](../../../specs/55-setup-trust/data-model.md), [specs/55-setup-trust/contracts/setup-trust.md](../../../specs/55-setup-trust/contracts/setup-trust.md), [specs/55-setup-trust/contracts/launcher-and-doctor.md](../../../specs/55-setup-trust/contracts/launcher-and-doctor.md), [specs/55-setup-trust/quickstart.md](../../../specs/55-setup-trust/quickstart.md), [specs/55-setup-trust/spec.md](../../../specs/55-setup-trust/spec.md), [docs/adr/0011-worktree-preparation.md](../../../docs/adr/0011-worktree-preparation.md), [tools/spec_workflow/branch_sync.py](../../../tools/spec_workflow/branch_sync.py), [tools/spec_workflow/launcher.py](../../../tools/spec_workflow/launcher.py) |  |
| PD-0007 | plan | accept (agent-provisional) | Agent-provisional: plan.md meets spec 55 (FR-001 to FR-020, AC-001 to AC-027); every refusal fails closed and the launcher comparison is unchanged; plan-review findings F-001 to F-006 are carried to tasks and specialist reviews. | claude/claude-opus-5-5 (author) | [specs/55-setup-trust/plan.md](../../../specs/55-setup-trust/plan.md) `24baecb86646` | [specs/55-setup-trust/plan.md](../../../specs/55-setup-trust/plan.md), [specs/55-setup-trust/spec.md](../../../specs/55-setup-trust/spec.md), [specs/55-setup-trust/intent.md](../../../specs/55-setup-trust/intent.md), [specs/55-setup-trust/reviews/plan.md](../../../specs/55-setup-trust/reviews/plan.md), [specs/55-setup-trust/research.md](../../../specs/55-setup-trust/research.md), [specs/55-setup-trust/data-model.md](../../../specs/55-setup-trust/data-model.md), [specs/55-setup-trust/contracts/setup-trust.md](../../../specs/55-setup-trust/contracts/setup-trust.md), [specs/55-setup-trust/contracts/launcher-and-doctor.md](../../../specs/55-setup-trust/contracts/launcher-and-doctor.md), [specs/55-setup-trust/quickstart.md](../../../specs/55-setup-trust/quickstart.md), [specs/55-setup-trust/discovery.md](../../../specs/55-setup-trust/discovery.md), [.specify/workflow-state/issues/55.md](../../../.specify/workflow-state/issues/55.md), [docs/policies/project/workflow.md](../../../docs/policies/project/workflow.md), [docs/policies/workflow.md](../../../docs/policies/workflow.md), [docs/policies/spec-kit-workflow.md](../../../docs/policies/spec-kit-workflow.md), [docs/adr/0011-worktree-preparation.md](../../../docs/adr/0011-worktree-preparation.md), [.specify/memory/constitution.md](../../../.specify/memory/constitution.md) |  |

### PD-0001 basis

> Issue #55 is an open leaf of Epic #11 with one intake scope comment classifying it as a cohesive feature with a single outcome, and its four acceptance criteria form one group (setup records a baseline on a clean checkout; no baseline when any protected or committed input differs; no baseline while a run is in progress or a tamper marker exists; launcher checks unchanged). The in/out boundary is explicit: in scope are setup recording the baseline, doctor reporting its origin and the new-worktree path (#15) using it; out of scope are trusting after an agent step, trusting unreviewed ballast.toml or [agents.permissions] edits, and any change to the launcher's fail-closed comparison or BALLAST_TAMPERED marker. This meets the scope gate in docs/policies/spec-kit-workflow.md. The Issue's open question (uncommitted ballast.toml change) has a safe default that the Issue itself implies: never eligible, because the scope requires committed inputs unchanged from the commit setup read and the second acceptance criterion requires no baseline when ballast.toml differs; it keeps needing ballast trust, which is the conservative, reversible choice. The work is R2 (launcher trust model, per docs/policies/project/workflow.md) as already recorded by intake; the intake comment marks it Autonomous-eligible with no privileged actions before merge. The merge remains the single human decision.

### PD-0002 basis

> The launcher skips saved run state in its trust comparison (tools/spec_workflow/launcher.py), so run state shows agents ran in the checkout without being covered by the baseline; IAC-3 requires that no agent step can cause a baseline. Refusing on any run state only adds refusals inside the eligibility the operator set in D-02 and D-03 and never widens trust: a refused checkout falls back to today's operator ballast trust. Reversible by dropping the extra check later.

### PD-0003 basis

> The Issue puts any change to the launcher's fail-closed comparison out of scope (IAC-4), and doctor must not recompute trust: it reads only the launcher's status --json (tools/ballast, docs/adr/0002-cli-standard-manifest.md). A separate provenance file leaves trusted.json and its comparison unchanged; an absent or mismatched provenance file reads as operator trust, so it can never make a checkout trusted. Reversible because the file is operator state that can be dropped without touching any baseline.

### PD-0004 basis

> The brief settles D-02 (default branch or previous operator baseline) but does not cover a committed ballast.toml whose [github] repository was repointed to a repository whose default branch carries the same changed file; nothing inside the checkout tells the reviewed repository from a repointed one, so the observation could be steered to a repository an agent controls, which the Issue puts out of scope (unreviewed ballast.toml edits). The default only narrows eligibility: a refused checkout falls back to today's operator ballast trust, the record holds repository identities and never digests, so no baseline is inherited (FR-010). It narrows IAC-1 for the first checkout of a never-trusted repository, stated as a non-goal in spec.md, and adds an operator-state record, so it is marked material for merge review. Reversible by dropping the record and the check; no migration, data loss or broken promise.

### PD-0005 basis

> spec.md traces to discovery.md with no unresolved marker (Undecided: none). Outcome, non-goals and constraints match Issue #55: IAC-1 to IAC-4 are each covered (AC-001/002/003, AC-010 to AC-017, AC-018 to AC-021, AC-022/023). D-01, D-02 and D-03 are the operator's recorded answers in the brief at commit f290079 (earlier block HD-0001); the spec follows them: a new ADR supersedes the ADR-0007 and ADR-0011 clauses and BL-INV-002 is amended (FR-017, FR-018). D-04 and D-05 are safe, reversible agent-provisional defaults that only add refusals or leave the launcher comparison unchanged (FR-015). Two agent inferences only narrow D-02 and are marked [I] for merge review: the default branch is observed live from the pinned repository on the ADR-0005 path, and only repositories in an operator-state record written by ballast trust count (PD-0004); the resulting narrowing of IAC-1 for a never-trusted repository is stated as a non-goal. Every refusal falls back to today's ballast trust, so no path widens agent authority beyond D-02. The change is R2 (docs/policies/project/workflow.md: launcher trust model, agent authority) and is material because it changes a security boundary and accepted architecture; the merge is the single human decision on it.

### PD-0006 basis

> Independent re-review for run 38380ec3 of plan.md, research.md R1-R19, data-model.md, both contracts and quickstart.md against spec.md FR-001-FR-020 and AC-001-AC-027. Every AC maps to a test or review step and every FR to a design decision; local refusals precede the only network step; provenance never feeds the launcher comparison; reviewed references are only an operator baseline (fail closed on unbound provenance) or the default branch of a repository only ballast trust records. Code claims checked in launcher.py (BASES, SKIPPED), branch_sync.py (_url, throwaway env), autonomy.GIT_HARDENING and tools/ballast prepare ordering. docs/policies/project/engineering.md, tasks.md and decisions.md are absent (plan stage). Findings are fixable while writing ADR-0014, setup_trust.py and tasks; none lets an unreviewed input be recorded.

### PD-0007 basis

> plan.md is written against spec.md at the digest recorded for PD-0005 in intent.md (sha256 4b7ebd8a..., verified unchanged), and reviews/plan.md (PD-0006) reviewed this exact plan.md (24baecb8...). Every FR maps to a research decision, data-model row or contract step, and every AC to a test or review step in quickstart.md. Local refusals precede the only network step; provenance never feeds the launcher comparison, its messages or BALLAST_TAMPERED (FR-015, Issue IAC-4); reviewed references are only an operator baseline with bound trust provenance or the default branch of a repository that only ballast trust records (PD-0004), so no path lets an agent step or an unreviewed ballast.toml reach a recorded baseline (IAC-2, IAC-3). The Constitution Check passes with one amendment to BL-INV-002, which follows D-01 from the discovery brief and goes through governance with a recorded reason; ADR-0014 is proposed until merge. Review findings are fixable during implementation: F-001 (extend ADR-0014's superseded clauses to ADR-0011's no-network wording) and F-002 (share branch_sync's throwaway environment builder) are medium architecture items to be turned into tasks; F-003 to F-006 are low/info and fail closed. The change stays R2 (docs/policies/project/workflow.md: launcher trust model, agent authority) and is material because it amends a security boundary and accepted architecture; the PR merge is the single human decision. docs/policies/project/engineering.md does not exist. No privileged action is needed before merge.

## Reviews

- PD-0006 plan: approved; reviewer claude/claude-opus-5-5; cross-provider: no; report [specs/55-setup-trust/reviews/plan.md](../../../specs/55-setup-trust/reviews/plan.md)

Reduced independence: reviews used the authoring provider.

## Open findings

- PD-0006 F-001 (medium, architecture-issue, accepted-provisionally): ADR-0011 says --prepare is local-only, never downloads, and reaches the trust preflight with no network, but R17 supersedes only its trusted.json clause while the plan adds a live network observation to preparation. ADR-0014 as planned would leave ADR-0011 contradicting the new behavior. Resolvable by extending R17's superseded-clause list when ADR-0014 is written (the download wording stays true; the no-network outcome does not); carried to tasks and the architecture review.
- PD-0006 F-002 (medium, architecture-issue, accepted-provisionally): R9 and the setup-trust contract restate branch synchronization's throwaway Git environment (DROPPED_ENV, PATH restriction, prompt and askpass variables, display variables) instead of sharing it; only the URL rule moves to a shared function. Two copies of security-relevant rules can drift, against FR-004's 'same trusted path'. Resolvable by sharing the environment builder when setup_trust.py is written; carried to tasks and the security review.
- PD-0006 F-003 (low, spec-ambiguity, open): Contract step 1 keeps a matching baseline before the local conditions run, so with a BALLAST_TAMPERED marker and a matching baseline setup reports the baseline unchanged instead of naming the remedy AC-019 asks for. Nothing is recorded and the launcher still refuses; message gap only.
- PD-0006 F-004 (low, spec-violation, open): The post-write recheck and OSError paths remove the baseline record_baseline just wrote; if that write replaced an older operator-recorded baseline, the older one is lost, departing from FR-008 in a rare race. Fails closed: ballast trust is needed again. Keeping the previous bytes for restore would close it.
- PD-0006 F-005 (low, spec-ambiguity, open): Recording through the operator-baseline alternative (row 8a) replaces trust provenance with setup, so the next pin update with unchanged configuration can no longer use that offline alternative and needs the network or ballast trust. Fails closed; worth stating in the docs or carrying the operator reference forward.
- PD-0006 F-006 (info, spec-ambiguity, open): R9 compares only the blob ID from ls-tree; a default-branch ballast.toml that is a symlink (mode 120000) whose target text equals the checkout file's bytes would match. Not a practical widening, but requiring mode 100644 or 100755 in the parsed ls-tree entry makes the comparison exact.

## Fix loop

- Cycles used: 0 of 3

## Block resolutions

- HD-0001 at 2026-10-06T18:34:29+00:00 by operator: resolved the postcondition block at validate-discovery; resumed in Autonomous at validate-discovery; changed during the block: `specs/55-setup-trust/discovery.md`; reference: operator resumed after the postcondition block at validate-discovery

## Checks

- run-checks: not run yet
- run-checks ran in the run's worktree, so git-ignored files there were visible to them and are not part of this PR
- agent-reported: none; agent claims never satisfy run-checks

CI results appear on this PR.
