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

This is an R2 change. It was made without any prior human approval; the pre-change approval was agent-provisional (none recorded yet).

R2 boundaries touched:

- agent authority
- launcher trust model

## Material provisional changes

None.

## Provisional decisions

| ID | Point | Decision | Summary | Decided by | Artifact | Evidence | Superseded by |
| --- | --- | --- | --- | --- | --- | --- | --- |
| PD-0001 | scope | accept (agent-provisional, after 1 retry) | Issue #55 is one specifiable outcome: ballast setup records the trust baseline for protected inputs it just wrote, so a clean checkout can start a run without a separate ballast trust; agent-provisional. | claude/claude-opus-5-5 (author) | [.specify/feature.json](../../../.specify/feature.json) `b2888ca192d6` | <https://github.com/Hugo-Grellier/ballast/issues/55>, [.specify/feature.json](../../../.specify/feature.json), [docs/policies/spec-kit-workflow.md](../../../docs/policies/spec-kit-workflow.md), [docs/policies/workflow.md](../../../docs/policies/workflow.md), [docs/policies/project/workflow.md](../../../docs/policies/project/workflow.md), [docs/plans/2026-10-02-product-roadmap.md](../../../docs/plans/2026-10-02-product-roadmap.md), [specs/TECHNICAL-SPEC.md](../../../specs/TECHNICAL-SPEC.md), [AGENTS.md](../../../AGENTS.md) |  |

### PD-0001 basis

> Issue #55 (snapshot in .specify/workflow-state/issues/55.md) is an open leaf of Epic #11 with one intake scope comment classifying it as a cohesive feature; the runner verified that gate before the run. It names one outcome: a checkout whose protected inputs are exactly what a trusted, operator-run ballast setup of the pinned standard produced is trusted without a separate operator command, while any differing checkout still needs ballast trust. The in/out boundary is explicit: in scope are setup recording the baseline when committed inputs are unchanged from the commit setup read and no run is in progress, doctor reporting how a baseline was recorded, and the new-worktree path (#15) using it; out of scope are trusting after an agent step, trusting unreviewed ballast.toml or [agents.permissions] edits, and any change to the launcher's fail-closed comparison or BALLAST_TAMPERED marker. The four acceptance criteria form one group owned by this Issue. The Issue's open question about an uncommitted ballast.toml change does not widen the scope: its own out-of-scope list and second acceptance criterion already exclude any ballast.toml that differs from what setup read, so such a change falls outside this feature and keeps needing ballast trust; specification refines it within that boundary. The intake comment records that the operator asked on 2026-10-05 to add this to v1.0; that request is cited from the Issue, and this gate decision remains agent-provisional. Risk is R2 per docs/policies/project/workflow.md (launcher trust model, agent authority); the Issue and intake list no privileged action before merge beyond the Draft PR merge itself, which the operator performs. This satisfies the scope gate in docs/policies/spec-kit-workflow.md.

Refused drafts before this one (agent-provisional retries):

- scope draft must not carry an assumption

## Reviews

No review recorded yet.

## Open findings

None.

## Checks

- run-checks: not run yet
- run-checks ran in the run's worktree, so git-ignored files there were visible to them and are not part of this PR
- agent-reported: none; agent claims never satisfy run-checks

CI results appear on this PR.
