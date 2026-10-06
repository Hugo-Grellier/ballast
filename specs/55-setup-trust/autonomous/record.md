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
| PD-0002 | clarification | assume (agent-provisional) | D-04: setup records no baseline when any run state exists, an operator-state run is unfinished, or the in-progress or BALLAST_TAMPERED marker exists | claude/claude-opus-5-5 (author) | [specs/55-setup-trust/discovery.md](../../../specs/55-setup-trust/discovery.md) `7433bf050ec5` | [specs/55-setup-trust/discovery.md](../../../specs/55-setup-trust/discovery.md), [tools/spec_workflow/launcher.py](../../../tools/spec_workflow/launcher.py) |  |
| PD-0003 | clarification | assume (agent-provisional) | D-05: the baseline's source is a provenance file in operator state beside trusted.json, bound to its digest and reported in the launcher's status --json | claude/claude-opus-5-5 (author) | [specs/55-setup-trust/discovery.md](../../../specs/55-setup-trust/discovery.md) `7433bf050ec5` | [specs/55-setup-trust/discovery.md](../../../specs/55-setup-trust/discovery.md), [tools/spec_workflow/launcher.py](../../../tools/spec_workflow/launcher.py), [tools/ballast](../../../tools/ballast), [docs/adr/0002-cli-standard-manifest.md](../../../docs/adr/0002-cli-standard-manifest.md) |  |

### PD-0001 basis

> Issue #55 (snapshot in .specify/workflow-state/issues/55.md) is an open leaf of Epic #11 with one intake scope comment classifying it as a cohesive feature; the runner verified that gate before the run. It names one outcome: a checkout whose protected inputs are exactly what a trusted, operator-run ballast setup of the pinned standard produced is trusted without a separate operator command, while any differing checkout still needs ballast trust. The in/out boundary is explicit: in scope are setup recording the baseline when committed inputs are unchanged from the commit setup read and no run is in progress, doctor reporting how a baseline was recorded, and the new-worktree path (#15) using it; out of scope are trusting after an agent step, trusting unreviewed ballast.toml or [agents.permissions] edits, and any change to the launcher's fail-closed comparison or BALLAST_TAMPERED marker. The four acceptance criteria form one group owned by this Issue. The Issue's open question about an uncommitted ballast.toml change does not widen the scope: its own out-of-scope list and second acceptance criterion already exclude any ballast.toml that differs from what setup read, so such a change falls outside this feature and keeps needing ballast trust; specification refines it within that boundary. The intake comment records that the operator asked on 2026-10-05 to add this to v1.0; that request is cited from the Issue, and this gate decision remains agent-provisional. Risk is R2 per docs/policies/project/workflow.md (launcher trust model, agent authority); the Issue and intake list no privileged action before merge beyond the Draft PR merge itself, which the operator performs. This satisfies the scope gate in docs/policies/spec-kit-workflow.md.

Refused drafts before this one (agent-provisional retries):

- scope draft must not carry an assumption

### PD-0002 basis

> It only adds refusals inside the eligibility boundary the operator set in D-02 and D-03 and never widens trust; a refused checkout falls back to today's operator `ballast trust`. Run state lives under .specify/workflows/runs and .specify/workflow-state, which the launcher's comparison skips (tools/spec_workflow/launcher.py), so its presence shows agents ran there. Reversible by dropping the extra check.

### PD-0003 basis

> The launcher's comparison stays unchanged as the Issue and IAC-4 require (tools/spec_workflow/launcher.py), doctor keeps reading only status --json (tools/ballast, ADR-0002), and an absent or mismatched provenance file reads as operator trust, so the file can never make a checkout trusted. Reversible: the file is operator state that can be dropped without touching any baseline.

## Reviews

No review recorded yet.

## Open findings

None.

## Fix loop

- Cycles used: 0 of 3

## Block resolutions

- HD-0001 at 2026-10-06T17:45:45+00:00 by operator: resolved the upstream-sync block at discover; resumed in Autonomous at discover; changed during the block: `specs/55-setup-trust/discovery.md`; reference: operator resumed after the upstream-sync block at discover
- HD-0002 at 2026-10-06T17:48:28+00:00 by operator: resolved the postcondition block at validate-discovery; resumed in Autonomous at validate-discovery; changed during the block: `specs/55-setup-trust/discovery.md`; reference: operator resumed after the postcondition block at validate-discovery

## Checks

- run-checks: not run yet
- run-checks ran in the run's worktree, so git-ignored files there were visible to them and are not part of this PR
- agent-reported: none; agent claims never satisfy run-checks

CI results appear on this PR.
