# Autonomous run record

Run `b48b609a` for #55 (`specs/55-setup-trust`). Generated from the operator records; every check re-renders it, so an edit fails the next check. Every decision below is agent-provisional; merging the PR that contains this record is the only human approval.

## Mode and risk

- Mode start: autonomous at 2026-10-06T12:19:11+00:00 by operator
- Risk: R2 (scope-record); history: R2 at 2026-10-06T12:19:11+00:00
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

- PD-0005 (intent, agent-provisional): Spec for #55 is one coherent feature: setup and worktree preparation record the trust baseline only for exactly-installed inputs with reviewed configuration and no agent trace; launcher comparison unchanged; agent-provisional.

## Provisional decisions

| ID | Point | Decision | Summary | Decided by | Artifact | Evidence | Superseded by |
| --- | --- | --- | --- | --- | --- | --- | --- |
| PD-0001 | scope | accept (agent-provisional, after 1 retry) | Issue #55 is one specifiable outcome: ballast setup records the trust baseline for protected inputs it just wrote, so a clean checkout can start a run without a separate ballast trust; agent-provisional. | claude/claude-opus-5-5 (author) | [.specify/feature.json](../../../.specify/feature.json) `b2888ca192d6` | <https://github.com/Hugo-Grellier/ballast/issues/55>, [.specify/feature.json](../../../.specify/feature.json), [docs/policies/spec-kit-workflow.md](../../../docs/policies/spec-kit-workflow.md), [docs/policies/workflow.md](../../../docs/policies/workflow.md), [docs/policies/project/workflow.md](../../../docs/policies/project/workflow.md), [docs/plans/2026-10-02-product-roadmap.md](../../../docs/plans/2026-10-02-product-roadmap.md), [specs/TECHNICAL-SPEC.md](../../../specs/TECHNICAL-SPEC.md), [AGENTS.md](../../../AGENTS.md) |  |
| PD-0002 | clarification | assume (agent-provisional) | D-04: setup records no baseline when any run state exists, an operator-state run is unfinished, or the in-progress or BALLAST_TAMPERED marker exists | claude/claude-opus-5-5 (author) | [specs/55-setup-trust/discovery.md](../../../specs/55-setup-trust/discovery.md) `7433bf050ec5` | [specs/55-setup-trust/discovery.md](../../../specs/55-setup-trust/discovery.md), [tools/spec_workflow/launcher.py](../../../tools/spec_workflow/launcher.py) |  |
| PD-0003 | clarification | assume (agent-provisional) | D-05: the baseline's source is a provenance file in operator state beside trusted.json, bound to its digest and reported in the launcher's status --json | claude/claude-opus-5-5 (author) | [specs/55-setup-trust/discovery.md](../../../specs/55-setup-trust/discovery.md) `7433bf050ec5` | [specs/55-setup-trust/discovery.md](../../../specs/55-setup-trust/discovery.md), [tools/spec_workflow/launcher.py](../../../tools/spec_workflow/launcher.py), [tools/ballast](../../../tools/ballast), [docs/adr/0002-cli-standard-manifest.md](../../../docs/adr/0002-cli-standard-manifest.md) |  |
| PD-0004 | clarification | assume (agent-provisional) | The default-branch alternative counts only for a pinned repository in an operator-state record of reviewed repositories that only ballast trust writes | claude/claude-opus-5-5 (author) | [specs/55-setup-trust/spec.md](../../../specs/55-setup-trust/spec.md) `34ce48963133` | [specs/55-setup-trust/spec.md](../../../specs/55-setup-trust/spec.md), [specs/55-setup-trust/discovery.md](../../../specs/55-setup-trust/discovery.md), [.specify/workflow-state/issues/55.md](../../../.specify/workflow-state/issues/55.md), [tools/spec_workflow/launcher.py](../../../tools/spec_workflow/launcher.py) |  |
| PD-0005 | intent | accept (agent-provisional) | Spec for #55 is one coherent feature: setup and worktree preparation record the trust baseline only for exactly-installed inputs with reviewed configuration and no agent trace; launcher comparison unchanged; agent-provisional. | claude/claude-opus-5-5 (author) | [specs/55-setup-trust/spec.md](../../../specs/55-setup-trust/spec.md) `34ce48963133` | [specs/55-setup-trust/discovery.md](../../../specs/55-setup-trust/discovery.md), [specs/55-setup-trust/spec.md](../../../specs/55-setup-trust/spec.md), [.specify/workflow-state/issues/55.md](../../../.specify/workflow-state/issues/55.md), [specs/55-setup-trust/checklists/requirements.md](../../../specs/55-setup-trust/checklists/requirements.md), [specs/55-setup-trust/autonomous/record.md](../../../specs/55-setup-trust/autonomous/record.md), [docs/policies/project/workflow.md](../../../docs/policies/project/workflow.md), [docs/policies/spec-kit-workflow.md](../../../docs/policies/spec-kit-workflow.md), [docs/adr/0005-launcher-branch-synchronization.md](../../../docs/adr/0005-launcher-branch-synchronization.md) |  |
| PD-0006 | plan-review | accept-finding (agent-provisional, after 1 retry) | Plan meets the spec and stays fail-closed; two medium items carried provisionally, three low items open for tasks and specialist review | claude/claude-opus-5-5 (reviewer) | [specs/55-setup-trust/plan.md](../../../specs/55-setup-trust/plan.md) `78e8ea30d30d` | [specs/55-setup-trust/reviews/plan.md](../../../specs/55-setup-trust/reviews/plan.md), [specs/55-setup-trust/plan.md](../../../specs/55-setup-trust/plan.md), [specs/55-setup-trust/research.md](../../../specs/55-setup-trust/research.md), [specs/55-setup-trust/data-model.md](../../../specs/55-setup-trust/data-model.md), [specs/55-setup-trust/spec.md](../../../specs/55-setup-trust/spec.md), [docs/adr/0011-worktree-preparation.md](../../../docs/adr/0011-worktree-preparation.md) |  |

### PD-0001 basis

> Issue #55 (snapshot in .specify/workflow-state/issues/55.md) is an open leaf of Epic #11 with one intake scope comment classifying it as a cohesive feature; the runner verified that gate before the run. It names one outcome: a checkout whose protected inputs are exactly what a trusted, operator-run ballast setup of the pinned standard produced is trusted without a separate operator command, while any differing checkout still needs ballast trust. The in/out boundary is explicit: in scope are setup recording the baseline when committed inputs are unchanged from the commit setup read and no run is in progress, doctor reporting how a baseline was recorded, and the new-worktree path (#15) using it; out of scope are trusting after an agent step, trusting unreviewed ballast.toml or [agents.permissions] edits, and any change to the launcher's fail-closed comparison or BALLAST_TAMPERED marker. The four acceptance criteria form one group owned by this Issue. The Issue's open question about an uncommitted ballast.toml change does not widen the scope: its own out-of-scope list and second acceptance criterion already exclude any ballast.toml that differs from what setup read, so such a change falls outside this feature and keeps needing ballast trust; specification refines it within that boundary. The intake comment records that the operator asked on 2026-10-05 to add this to v1.0; that request is cited from the Issue, and this gate decision remains agent-provisional. Risk is R2 per docs/policies/project/workflow.md (launcher trust model, agent authority); the Issue and intake list no privileged action before merge beyond the Draft PR merge itself, which the operator performs. This satisfies the scope gate in docs/policies/spec-kit-workflow.md.

Refused drafts before this one (agent-provisional retries):

- scope draft must not carry an assumption

### PD-0002 basis

> It only adds refusals inside the eligibility boundary the operator set in D-02 and D-03 and never widens trust; a refused checkout falls back to today's operator `ballast trust`. Run state lives under .specify/workflows/runs and .specify/workflow-state, which the launcher's comparison skips (tools/spec_workflow/launcher.py), so its presence shows agents ran there. Reversible by dropping the extra check.

### PD-0003 basis

> The launcher's comparison stays unchanged as the Issue and IAC-4 require (tools/spec_workflow/launcher.py), doctor keeps reading only status --json (tools/ballast, ADR-0002), and an absent or mismatched provenance file reads as operator trust, so the file can never make a checkout trusted. Reversible: the file is operator state that can be dropped without touching any baseline.

### PD-0004 basis

> The spec left to the plan how setup tells the reviewed [github] repository from a repointed one. That left AC-001 and AC-006 (fresh clone, new worktree) in tension with FR-005, because a repointed repository's default branch can carry the same changed ballast.toml, so nothing in the checkout can anchor review. The discovery brief does not cover repointing; D-01..D-03 stay as settled. Accepting whatever repository ballast.toml names would break FR-005 and the Issue's out-of-scope rule on unreviewed ballast.toml edits, so it is not a viable alternative. The adopted default only narrows eligibility. It follows the spec's existing rule that a checkout is ineligible when setup cannot tell. The record holds repository identities, never digests, so it is not baseline inheritance (FR-010). It narrows IAC-1 only for the first checkout of a never-trusted repository, which still needs one ballast trust, stated as a non-goal. It is reversible: dropping the record or the check later loses no data and can only restore today's ballast trust path. Listed for merge review with the R2 change.

### PD-0005 basis

> spec.md traces to discovery.md: D-01 (supersede the ADR-0007 clause, amend BL-INV-002), D-02 option B and D-03 option A follow the operator's answers recorded in the brief (commit f290079, block HD-0001); D-04 and D-05 are agent-provisional (PD-0002, PD-0003). Outcome, constraints (FR-001..FR-020), non-goals and AC-001..AC-027 form one feature; every Issue criterion IAC-1..IAC-4 is cited, the checklist reports no NEEDS CLARIFICATION marker and none remains in spec.md or discovery.md. Non-goals match the Issue's out-of-scope list: no trust after an agent step, no unreviewed ballast.toml or [agents.permissions] edits, no change to the fail-closed comparison or BALLAST_TAMPERED (FR-015, AC-023). Two refinements are material and listed for merge review: the D-02 refinement observes the default branch live from the pinned repository instead of an agent-writable remote-tracking ref (FR-004, AC-014, AC-015), and clarification 1 (PD-0004) counts the default-branch alternative only for repositories in an operator-state record that only ballast trust writes (FR-005, AC-016). Both only narrow eligibility and fall back to today's ballast trust; the second narrows IAC-1 for the first checkout of a never-trusted repository, stated as a non-goal. Governing-document updates (new ADR, BL-INV-002 amendment, docs) are in scope (AC-025..AC-027). Risk stays R2 per docs/policies/project/workflow.md. No privileged action is needed before merge.

### PD-0006 basis

> Checked every FR and AC against research R1-R19, the data-model eligibility order (all local refusals before the single network step), the contracts and quickstart; verified code claims against the tree (launcher BASES and SKIPPED, installed_digests sharing launcher.digests, Setup lock scope, autonomy.GIT_HARDENING, the branch_sync environment and URL rule). The launcher stays the single owner of the baseline; a forged ref, origin or insteadOf cannot create eligibility. The two medium items (ADR-0011 network wording not superseded; duplicated Git environment rules) are fixable while writing ADR-0014 and the module, so the plan can proceed. docs/policies/project/engineering.md does not exist; tasks.md and decisions.md do not exist yet at plan stage.

Refused drafts before this one (agent-provisional retries):

- specs/55-setup-trust/reviews/plan.md carries findings or severity tags in its narrative; every finding belongs in the review draft

## Reviews

- PD-0006 plan: approved; reviewer claude/claude-opus-5-5; cross-provider: no; report [specs/55-setup-trust/reviews/plan.md](../../../specs/55-setup-trust/reviews/plan.md)

Reduced independence: reviews used the authoring provider.

## Open findings

- PD-0006 F-001 (medium, architecture-issue, accepted-provisionally): ADR-0011 says preparation is local-only, never downloads and reaches the trust preflight with no network, but R17 supersedes only its trusted.json clause while the plan adds a network observation to preparation. ADR-0014 as planned would leave ADR-0011 contradicting the new behavior. Fixable by extending R17's list of superseded clauses when ADR-0014 is written; carried to tasks and the architecture review.
- PD-0006 F-002 (medium, architecture-issue, accepted-provisionally): R9 and the contract restate branch synchronization's throwaway Git environment (DROPPED_ENV, the PATH restriction, the prompt and askpass variables) instead of sharing it; only the URL rule moves to a shared place. Two copies of security-relevant rules can drift, against FR-004's same trusted path. Fixable by sharing the environment builder when the module is written; carried to tasks and the security review.
- PD-0006 F-003 (low, spec-ambiguity, open): Contract step 1 keeps a matching baseline before the local conditions run, so with a BALLAST_TAMPERED marker and a matching baseline setup reports the baseline unchanged instead of naming the remedy AC-019 asks for. Nothing is recorded; this is a message gap only.
- PD-0006 F-004 (low, spec-violation, open): The recheck and OSError paths remove the baseline record_baseline just wrote; if that write replaced an older operator-recorded baseline, the older one is lost, departing from FR-008 in a rare race. The result is fail-closed: ballast trust is needed again.
- PD-0006 F-005 (low, spec-ambiguity, open): Recording through the operator-baseline alternative (row 8a) replaces trust provenance with setup, consuming that alternative for later setups; a setup interrupted in the network step after a committed preparation leaves a current installation that later reports nothing to prepare without recording. Both fail closed to ballast trust; worth stating in the documentation or tasks.

## Fix loop

- Cycles used: 0 of 3

## Block resolutions

- HD-0001 at 2026-10-06T17:45:45+00:00 by operator: resolved the upstream-sync block at discover; resumed in Autonomous at discover; changed during the block: `specs/55-setup-trust/discovery.md`; reference: operator resumed after the upstream-sync block at discover
- HD-0002 at 2026-10-06T17:48:28+00:00 by operator: resolved the postcondition block at validate-discovery; resumed in Autonomous at validate-discovery; changed during the block: `specs/55-setup-trust/discovery.md`; reference: operator resumed after the postcondition block at validate-discovery
- HD-0003 at 2026-10-06T17:52:27+00:00 by operator: resolved the contradiction block at clarify; resumed in Autonomous at validate-discovery; changed during the block: `specs/55-setup-trust/discovery.md`; reference: operator resumed after the contradiction block at clarify
- HD-0004 at 2026-10-06T18:28:44+00:00 by operator: resolved the upstream-sync block at record-plan; resumed in Autonomous at decide-plan; reference: operator resumed after the upstream-sync block at record-plan

## Checks

- run-checks: not run yet
- run-checks ran in the run's worktree, so git-ignored files there were visible to them and are not part of this PR
- agent-reported: none; agent claims never satisfy run-checks

CI results appear on this PR.
