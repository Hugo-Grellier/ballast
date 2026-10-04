Autonomous run gold01 for #27 — all intermediate decisions are agent-provisional. Merging this PR is the only human approval.

## Mode and risk

- Mode start: autonomous at 2026-10-03T12:00:00+00:00 by operator
- Risk: R1 (scope-record); history: R1 at 2026-10-03T12:00:00+00:00
- Limits (default): 240 minutes wall time, 30 agent steps
- Authoring integration: claude; review integration: codex

## Material provisional changes

- PD-0007 (decision-resolution, agent-provisional): DEC-0001 resolved: keep scope

## Provisional decisions

| ID | Point | Decision | Summary | Decided by | Artifact | Evidence | Superseded by |
| --- | --- | --- | --- | --- | --- | --- | --- |
| PD-0001 | scope | accept (agent-provisional) | Accepted | claude/model-x (author) | [specs/27-demo-run/spec.md](https://github.com/acme/demo/blob/27-demo-run/specs/27-demo-run/spec.md) `abababababab` | [specs/27-demo-run/spec.md](https://github.com/acme/demo/blob/27-demo-run/specs/27-demo-run/spec.md) |  |
| PD-0002 | intent | accept (agent-provisional) | Intent \| accepted @​team | claude/model-x (author) | [specs/27-demo-run/spec.md](https://github.com/acme/demo/blob/27-demo-run/specs/27-demo-run/spec.md) `abababababab` | [specs/27-demo-run/spec.md](https://github.com/acme/demo/blob/27-demo-run/specs/27-demo-run/spec.md) | PD-0008 |
| PD-0003 | plan-review | accept-finding (agent-provisional) | Accepted | codex/model-x (reviewer) | [specs/27-demo-run/spec.md](https://github.com/acme/demo/blob/27-demo-run/specs/27-demo-run/spec.md) `abababababab` | [specs/27-demo-run/spec.md](https://github.com/acme/demo/blob/27-demo-run/specs/27-demo-run/spec.md) |  |
| PD-0004 | plan | accept (agent-provisional) | Accepted | claude/model-x (author) | [specs/27-demo-run/spec.md](https://github.com/acme/demo/blob/27-demo-run/specs/27-demo-run/spec.md) `abababababab` | [specs/27-demo-run/spec.md](https://github.com/acme/demo/blob/27-demo-run/specs/27-demo-run/spec.md) |  |
| PD-0005 | tasks | accept (agent-provisional) | Accepted | claude/model-x (author) | [specs/27-demo-run/spec.md](https://github.com/acme/demo/blob/27-demo-run/specs/27-demo-run/spec.md) `abababababab` | [specs/27-demo-run/spec.md](https://github.com/acme/demo/blob/27-demo-run/specs/27-demo-run/spec.md) |  |
| PD-0006 | implementation-review | accept-finding (agent-provisional) | Accepted | codex/model-x (reviewer) | [specs/27-demo-run/spec.md](https://github.com/acme/demo/blob/27-demo-run/specs/27-demo-run/spec.md) `abababababab` | [specs/27-demo-run/spec.md](https://github.com/acme/demo/blob/27-demo-run/specs/27-demo-run/spec.md) |  |
| PD-0007 | decision-resolution | resolve (agent-provisional) | DEC-0001 resolved: keep scope | claude/model-x (author) | [specs/27-demo-run/spec.md](https://github.com/acme/demo/blob/27-demo-run/specs/27-demo-run/spec.md) `abababababab` | [specs/27-demo-run/spec.md](https://github.com/acme/demo/blob/27-demo-run/specs/27-demo-run/spec.md) |  |
| PD-0008 | intent | accept (agent-provisional) | Renewed intent | claude/model-x (author) | [specs/27-demo-run/spec.md](https://github.com/acme/demo/blob/27-demo-run/specs/27-demo-run/spec.md) `abababababab` | [specs/27-demo-run/spec.md](https://github.com/acme/demo/blob/27-demo-run/specs/27-demo-run/spec.md) |  |
| PD-0009 | spec-reconciliation | accept-finding (agent-provisional) | Accepted | codex/model-x (reviewer) | [specs/27-demo-run/spec.md](https://github.com/acme/demo/blob/27-demo-run/specs/27-demo-run/spec.md) `abababababab` | [specs/27-demo-run/spec.md](https://github.com/acme/demo/blob/27-demo-run/specs/27-demo-run/spec.md) |  |
| PD-0010 | final-acceptance | accept (agent-provisional) | Accepted | claude/model-x (author) | [specs/27-demo-run/spec.md](https://github.com/acme/demo/blob/27-demo-run/specs/27-demo-run/spec.md) `abababababab` | [specs/27-demo-run/spec.md](https://github.com/acme/demo/blob/27-demo-run/specs/27-demo-run/spec.md) |  |

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

- PD-0003 plan: approved; reviewer codex/model-x; cross-provider: yes; report [specs/27-demo-run/reviews/plan.md](https://github.com/acme/demo/blob/27-demo-run/specs/27-demo-run/reviews/plan.md)
- PD-0006 engineering: approved; reviewer codex/model-x; cross-provider: yes; report [specs/27-demo-run/reviews/engineering.md](https://github.com/acme/demo/blob/27-demo-run/specs/27-demo-run/reviews/engineering.md)
- PD-0009 spec-reconciliation: approved; reviewer codex/model-x; cross-provider: yes; report [specs/27-demo-run/reviews/spec-reconciliation.md](https://github.com/acme/demo/blob/27-demo-run/specs/27-demo-run/reviews/spec-reconciliation.md)

## Open findings

- PD-0006 F-001 (medium, missing-test, accepted-provisionally): Covered by the pilot

## Checks

- runner: `true` exited 0 in 0.2s
- run-checks ran in the run's worktree, so git-ignored files there were visible to them and are not part of this PR
- agent-reported: none; agent claims never satisfy run-checks

CI results appear on this PR.

## Changed paths

- `specs/27-demo-run/spec.md`
- `src/demo.py`

Refs #27
