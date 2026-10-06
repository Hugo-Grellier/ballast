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

This is an R2 change. It was made without any prior human approval; the pre-change approval was agent-provisional (none recorded yet).

R2 boundaries touched:

- launcher trust model

## Material provisional changes

None.

## Provisional decisions

| ID | Point | Decision | Summary | Decided by | Artifact | Evidence | Superseded by |
| --- | --- | --- | --- | --- | --- | --- | --- |
| PD-0001 | scope | accept (agent-provisional) | Issue #55 is one independently specifiable outcome: a checkout whose protected inputs are exactly what a trusted ballast setup produced is trusted without a separate ballast trust; anything else still needs it. | claude/claude-opus-5-5 (author) | [.specify/feature.json](../../../.specify/feature.json) `b2888ca192d6` | [.specify/feature.json](../../../.specify/feature.json), <https://github.com/Hugo-Grellier/ballast/issues/55>, [docs/policies/spec-kit-workflow.md](../../../docs/policies/spec-kit-workflow.md), [docs/policies/project/workflow.md](../../../docs/policies/project/workflow.md), [docs/plans/2026-10-02-product-roadmap.md](../../../docs/plans/2026-10-02-product-roadmap.md) |  |
| PD-0002 | clarification | assume (agent-provisional) | D-04: setup records no baseline when any run state exists under .specify/workflows/runs or .specify/workflow-state, an operator-state run is unfinished, or the in-progress or BALLAST_TAMPERED marker exists. | claude/claude-opus-5-5 (author) | [specs/55-setup-trust/discovery.md](../../../specs/55-setup-trust/discovery.md) `b6f904a2816e` | [specs/55-setup-trust/discovery.md](../../../specs/55-setup-trust/discovery.md), [tools/spec_workflow/launcher.py](../../../tools/spec_workflow/launcher.py) |  |
| PD-0003 | clarification | assume (agent-provisional) | D-05: the baseline's source is a provenance file in operator state beside trusted.json, bound to its digest and reported by the launcher's status --json; missing or mismatched reads as operator trust. | claude/claude-opus-5-5 (author) | [specs/55-setup-trust/discovery.md](../../../specs/55-setup-trust/discovery.md) `b6f904a2816e` | [specs/55-setup-trust/discovery.md](../../../specs/55-setup-trust/discovery.md), [tools/spec_workflow/launcher.py](../../../tools/spec_workflow/launcher.py), [tools/ballast](../../../tools/ballast), [docs/adr/0002-cli-standard-manifest.md](../../../docs/adr/0002-cli-standard-manifest.md) |  |

### PD-0001 basis

> Issue #55 is an open leaf of Epic #11 with one intake scope comment classifying it as a cohesive feature with a single outcome, and its four acceptance criteria form one group (setup records a baseline on a clean checkout; no baseline when any protected or committed input differs; no baseline while a run is in progress or a tamper marker exists; launcher checks unchanged). The in/out boundary is explicit: in scope are setup recording the baseline, doctor reporting its origin and the new-worktree path (#15) using it; out of scope are trusting after an agent step, trusting unreviewed ballast.toml or [agents.permissions] edits, and any change to the launcher's fail-closed comparison or BALLAST_TAMPERED marker. This meets the scope gate in docs/policies/spec-kit-workflow.md. The Issue's open question (uncommitted ballast.toml change) has a safe default that the Issue itself implies: never eligible, because the scope requires committed inputs unchanged from the commit setup read and the second acceptance criterion requires no baseline when ballast.toml differs; it keeps needing ballast trust, which is the conservative, reversible choice. The work is R2 (launcher trust model, per docs/policies/project/workflow.md) as already recorded by intake; the intake comment marks it Autonomous-eligible with no privileged actions before merge. The merge remains the single human decision.

### PD-0002 basis

> The launcher skips saved run state in its trust comparison (tools/spec_workflow/launcher.py), so run state shows agents ran in the checkout without being covered by the baseline; IAC-3 requires that no agent step can cause a baseline. Refusing on any run state only adds refusals inside the eligibility the operator set in D-02 and D-03 and never widens trust: a refused checkout falls back to today's operator ballast trust. Reversible by dropping the extra check later.

### PD-0003 basis

> The Issue puts any change to the launcher's fail-closed comparison out of scope (IAC-4), and doctor must not recompute trust: it reads only the launcher's status --json (tools/ballast, docs/adr/0002-cli-standard-manifest.md). A separate provenance file leaves trusted.json and its comparison unchanged; an absent or mismatched provenance file reads as operator trust, so it can never make a checkout trusted. Reversible because the file is operator state that can be dropped without touching any baseline.

## Reviews

No review recorded yet.

## Open findings

None.

## Checks

- run-checks: not run yet
- run-checks ran in the run's worktree, so git-ignored files there were visible to them and are not part of this PR
- agent-reported: none; agent claims never satisfy run-checks

CI results appear on this PR.
