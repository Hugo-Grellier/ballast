# Autonomous run record

Run `gold01` for #27 (`specs/27-demo-run`). Generated from the operator records; every check re-renders it, so an edit fails the next check. Every decision below is agent-provisional; merging the PR that contains this record is the only human approval.

## Mode and risk

- Mode start: autonomous at 2026-10-03T12:00:00+00:00 by operator
- Risk: R1 (scope-record); history: R1 at 2026-10-03T12:00:00+00:00
- Limits (default): 240 minutes wall time, 30 agent steps
- Spend: bounded by the agent-step limit; every agent step, retry and fix cycle counts; monetary spend is not measured
- Authoring integration: claude; review integration: claude

## Material provisional changes

- PD-0007 (decision-resolution, agent-provisional): DEC-0001 resolved: keep scope

## Provisional decisions

| ID | Point | Decision | Summary | Decided by | Artifact | Evidence | Superseded by |
| --- | --- | --- | --- | --- | --- | --- | --- |
| PD-0001 | scope | accept (agent-provisional) | Accepted | claude/model-x (author) | [specs/27-demo-run/spec.md](../../../specs/27-demo-run/spec.md) `abababababab` | [specs/27-demo-run/spec.md](../../../specs/27-demo-run/spec.md) |  |
| PD-0002 | intent | accept (agent-provisional) | Intent \| accepted @​team | claude/model-x (author) | [specs/27-demo-run/spec.md](../../../specs/27-demo-run/spec.md) `abababababab` | [specs/27-demo-run/spec.md](../../../specs/27-demo-run/spec.md) | PD-0008 |
| PD-0003 | plan-review | accept-finding (agent-provisional) | Accepted | claude/model-x (reviewer) | [specs/27-demo-run/spec.md](../../../specs/27-demo-run/spec.md) `abababababab` | [specs/27-demo-run/spec.md](../../../specs/27-demo-run/spec.md) |  |
| PD-0004 | plan | accept (agent-provisional) | Accepted | claude/model-x (author) | [specs/27-demo-run/spec.md](../../../specs/27-demo-run/spec.md) `abababababab` | [specs/27-demo-run/spec.md](../../../specs/27-demo-run/spec.md) |  |
| PD-0005 | tasks | accept (agent-provisional) | Accepted | claude/model-x (author) | [specs/27-demo-run/spec.md](../../../specs/27-demo-run/spec.md) `abababababab` | [specs/27-demo-run/spec.md](../../../specs/27-demo-run/spec.md) |  |
| PD-0006 | implementation-review | accept-finding (agent-provisional) | Accepted | claude/model-x (reviewer) | [specs/27-demo-run/spec.md](../../../specs/27-demo-run/spec.md) `abababababab` | [specs/27-demo-run/spec.md](../../../specs/27-demo-run/spec.md) |  |
| PD-0007 | decision-resolution | resolve (agent-provisional) | DEC-0001 resolved: keep scope | claude/model-x (author) | [specs/27-demo-run/spec.md](../../../specs/27-demo-run/spec.md) `abababababab` | [specs/27-demo-run/spec.md](../../../specs/27-demo-run/spec.md) |  |
| PD-0008 | intent | accept (agent-provisional) | Renewed intent | claude/model-x (author) | [specs/27-demo-run/spec.md](../../../specs/27-demo-run/spec.md) `abababababab` | [specs/27-demo-run/spec.md](../../../specs/27-demo-run/spec.md) |  |
| PD-0009 | spec-reconciliation | accept-finding (agent-provisional) | Accepted | claude/model-x (reviewer) | [specs/27-demo-run/spec.md](../../../specs/27-demo-run/spec.md) `abababababab` | [specs/27-demo-run/spec.md](../../../specs/27-demo-run/spec.md) |  |
| PD-0010 | final-acceptance | accept (agent-provisional) | Accepted | claude/model-x (author) | [specs/27-demo-run/spec.md](../../../specs/27-demo-run/spec.md) `abababababab` | [specs/27-demo-run/spec.md](../../../specs/27-demo-run/spec.md) |  |

### PD-0001 basis

> Basis for scope.
> Second line @​someone &lt;!-- x --&gt;

### PD-0002 basis

> Basis for intent.
> Second line @​someone &lt;!-- x --&gt;

### PD-0003 basis

> Basis for plan-review.
> Second line @​someone &lt;!-- x --&gt;

### PD-0004 basis

> Basis for plan.
> Second line @​someone &lt;!-- x --&gt;

### PD-0005 basis

> Basis for tasks.
> Second line @​someone &lt;!-- x --&gt;

### PD-0006 basis

> Basis for implementation-review.
> Second line @​someone &lt;!-- x --&gt;

### PD-0007 basis

> Basis for decision-resolution.
> Second line @​someone &lt;!-- x --&gt;

### PD-0008 basis

> Basis for intent.
> Second line @​someone &lt;!-- x --&gt;

### PD-0009 basis

> Basis for spec-reconciliation.
> Second line @​someone &lt;!-- x --&gt;

### PD-0010 basis

> Basis for final-acceptance.
> Second line @​someone &lt;!-- x --&gt;

## Reviews

- PD-0003 plan: approved; reviewer claude/model-x; cross-provider: no; report [specs/27-demo-run/reviews/plan.md](../../../specs/27-demo-run/reviews/plan.md)
- PD-0006 engineering: approved; reviewer claude/model-x; cross-provider: no; report [specs/27-demo-run/reviews/engineering.md](../../../specs/27-demo-run/reviews/engineering.md)
- PD-0009 spec-reconciliation: approved; reviewer claude/model-x; cross-provider: no; report [specs/27-demo-run/reviews/spec-reconciliation.md](../../../specs/27-demo-run/reviews/spec-reconciliation.md)

Reduced independence: reviews used the authoring provider.

## Open findings

- PD-0006 F-001 (medium, missing-test, accepted-provisionally): Covered by the pilot

## Checks

- runner: `true` exited 0 in 0.2s
- run-checks ran in the run's worktree, so git-ignored files there were visible to them and are not part of this PR
- agent-reported: none; agent claims never satisfy run-checks

CI results appear on this PR.
