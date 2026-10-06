# Autonomous run record

Run `d6b5dff2` for #22 (`specs/22-ui-demo`). Generated from the operator records; every check re-renders it, so an edit fails the next check. Every decision below is agent-provisional; merging the PR that contains this record is the only human approval.

## Mode and risk

- Mode start: autonomous at 2026-10-06T12:19:11+00:00 by operator
- Risk: R2 (scope-record); history: R2 at 2026-10-06T12:19:11+00:00
- Limits (default): 240 minutes wall time, 40 agent steps
- Spend: bounded by the agent-step limit; every agent step, retry and fix cycle counts; monetary spend is not measured
- Authoring integration: claude; review integration: claude
- Integration fallback: codex cannot start its own sandbox inside Ballast's confinement; claude takes both roles (DEC-0004)

## R2 notice

This is an R2 change. It was made without any prior human approval; the pre-change approval was agent-provisional (PD-0007).

R2 boundaries touched:

- what ballast executes or downloads

## Material provisional changes

None.

## Provisional decisions

| ID | Point | Decision | Summary | Decided by | Artifact | Evidence | Superseded by |
| --- | --- | --- | --- | --- | --- | --- | --- |
| PD-0001 | scope | accept (agent-provisional) | Issue #22 is one independently specifiable outcome: on-demand, reproducible UI demo capture linked to the existing PR packet, with a clear in/out boundary. | claude/claude-opus-5-5 (author) | [.specify/feature.json](../../../.specify/feature.json) `210210cad29b` | [.specify/feature.json](../../../.specify/feature.json), <https://github.com/Hugo-Grellier/ballast/issues/22>, [.specify/workflow-state/issues/22.md](../../../.specify/workflow-state/issues/22.md), [docs/policies/spec-kit-workflow.md](../../../docs/policies/spec-kit-workflow.md), [docs/policies/project/workflow.md](../../../docs/policies/project/workflow.md), [specs/19-acceptance-packet](../../../specs/19-acceptance-packet), [tools/spec_workflow/packet.py](../../../tools/spec_workflow/packet.py) |  |
| PD-0002 | clarification | assume (agent-provisional) | D-05: Ballast adds no local capture; the contract's demo command is the same one a developer runs locally, named in the docs and packet. | claude/claude-opus-5-5 (author) | [specs/22-ui-demo/discovery.md](../../../specs/22-ui-demo/discovery.md) `778ef01db257` | [specs/22-ui-demo/discovery.md](../../../specs/22-ui-demo/discovery.md), [docs/policies/project/workflow.md](../../../docs/policies/project/workflow.md), [tools/spec_workflow/artifacts.py](../../../tools/spec_workflow/artifacts.py) |  |
| PD-0003 | clarification | assume (agent-provisional) | D-06: Demo artifacts default to 14-day retention and a 15-minute capture timeout, both configurable in the contract within GitHub's limits. | claude/claude-opus-5-5 (author) | [specs/22-ui-demo/discovery.md](../../../specs/22-ui-demo/discovery.md) `778ef01db257` | [specs/22-ui-demo/discovery.md](../../../specs/22-ui-demo/discovery.md), [docs/plans/2026-10-02-product-roadmap.md](../../../docs/plans/2026-10-02-product-roadmap.md) |  |
| PD-0004 | clarification | assume (agent-provisional) | D-07: The request dispatches, waits a bounded time and refreshes the packet; an unfinished capture shows in progress until ballast run checkpoint refreshes it. | claude/claude-opus-5-5 (author) | [specs/22-ui-demo/discovery.md](../../../specs/22-ui-demo/discovery.md) `778ef01db257` | [specs/22-ui-demo/discovery.md](../../../specs/22-ui-demo/discovery.md), [docs/policies/spec-kit-workflow.md](../../../docs/policies/spec-kit-workflow.md) |  |
| PD-0005 | clarification | assume (agent-provisional) | A capture for a non-head commit shows stale with its commit and the outcome it had there, whatever that outcome was | claude/claude-opus-5-5 (author) | [specs/22-ui-demo/spec.md](../../../specs/22-ui-demo/spec.md) `0e63d22f16eb` | [specs/22-ui-demo/spec.md](../../../specs/22-ui-demo/spec.md), [specs/22-ui-demo/discovery.md](../../../specs/22-ui-demo/discovery.md), [.specify/workflow-state/issues/22.md](../../../.specify/workflow-state/issues/22.md) |  |
| PD-0006 | clarification | assume (agent-provisional) | With a declared contract and no capture requested yet, the demo section lists the declared scenarios as not yet requested | claude/claude-opus-5-5 (author) | [specs/22-ui-demo/spec.md](../../../specs/22-ui-demo/spec.md) `0e63d22f16eb` | [specs/22-ui-demo/spec.md](../../../specs/22-ui-demo/spec.md), [specs/22-ui-demo/discovery.md](../../../specs/22-ui-demo/discovery.md), [.specify/workflow-state/issues/22.md](../../../.specify/workflow-state/issues/22.md) |  |
| PD-0007 | intent | accept (agent-provisional) | spec.md states one coherent feature: operator-requested demo capture in a secretless CI job from a protected ballast.toml contract, linked in the existing #19 packet with commit/scenario/environment/outcome, failures shown as missing evidence. | claude/claude-opus-5-5 (author) | [specs/22-ui-demo/spec.md](../../../specs/22-ui-demo/spec.md) `0e63d22f16eb` | [specs/22-ui-demo/discovery.md](../../../specs/22-ui-demo/discovery.md), [specs/22-ui-demo/spec.md](../../../specs/22-ui-demo/spec.md), [specs/22-ui-demo/checklists/requirements.md](../../../specs/22-ui-demo/checklists/requirements.md), [.specify/workflow-state/issues/22.md](../../../.specify/workflow-state/issues/22.md), <https://github.com/Hugo-Grellier/ballast/issues/22>, [AGENTS.md](../../../AGENTS.md), [docs/policies/project/workflow.md](../../../docs/policies/project/workflow.md), [docs/policies/security.md](../../../docs/policies/security.md), [docs/adr/0003-launcher-github-authority.md](../../../docs/adr/0003-launcher-github-authority.md), [specs/19-acceptance-packet/spec.md](../../../specs/19-acceptance-packet/spec.md) |  |

### PD-0001 basis

> Per the scope and decomposition gate in docs/policies/spec-kit-workflow.md, Issue #22 has one main outcome (a reviewer requests a short reproducible video of implemented UI behavior from an existing PR), an explicit in-scope list (demo command/scenario contract, capture on request with seeded nonsensitive data, access-controlled artifact storage, link in the #19 PR packet with commit/scenario metadata) and an explicit out-of-scope list (automatic capture for every UI PR, video replacing assertions, committing media to branches). Its three acceptance criteria form one group (successful capture bound to commit/scenario/environment, local reproducibility without private data, failed capture reported as missing evidence without a duplicate PR) and share one cohesive design, so it is not an Epic. The intake scope comment records it as a leaf feature of Epic #11 with the same boundary. Its dependency #19 is present in the repository (specs/19-acceptance-packet, tools/spec_workflow/packet.py), so the link target exists. Risk stays R2 as recorded: the trusted workflow would invoke project-supplied demo commands, which touches the docs/policies/project/workflow.md boundary on what ballast executes. This acceptance is agent-provisional; the merge decision remains the single human approval for the R2 change.

### PD-0002 basis

> IAC-2 asks that the journey be reproducible locally; running the contract's own command on a developer's machine meets it without a second Ballast execution path for project commands, which docs/policies/project/workflow.md lists as an R2 boundary. It adds no authority, and a confined local capture like [checks] (tools/spec_workflow/artifacts.py) can be added later without changing the contract.

### PD-0003 basis

> The roadmap asks for media in an access-controlled location with retention (docs/plans/2026-10-02-product-roadmap.md, Priority 6) but names no value. A demo serves one review, so a short retention and a bounded capture are safe defaults; they change neither scope nor authority, the project can override them in its contract, and the values can be changed later.

### PD-0004 basis

> The acceptance packet already refreshes at checkpoints and never waits for CI (docs/policies/spec-kit-workflow.md, Acceptance packet). Reusing that refresh keeps the request command bounded, never claims a result before it exists (IAC-3), adds no authority, and a blocking wait can be added later as a flag.

### PD-0005 basis

> FR-010 gives each demo line one outcome and FR-011 marks any capture for another commit as stale, but neither says what a stale capture that had failed or gone missing shows. The discovery brief does not cover this case. Showing stale plus the original outcome keeps a past failure visible (IAC-3) and never presents an old video as the current head (IAC-1, #19 head binding). It only affects how the derived packet is presented, adds no authority or execution, stores no data, and a later change can alter the rendering on the next checkpoint without migration.

### PD-0006 basis

> FR-010 lists outcomes only for requested scenarios plus not configured for a missing contract, so a configured project with no request has no defined packet state. The discovery brief does not cover this case, though D-08 values telling a failure apart from no request. A distinct not-yet-requested listing claims no success and no failure, changes no evidence state (FR-014), adds no authority, execution or stored data, and only affects the derived packet's rendering, which a later change can alter on the next checkpoint.

### PD-0007 basis

> The spec traces to discovery.md (D-01..D-08, no Undecided items) and covers all three Issue #22 criteria: IAC-1 by AC-001..AC-006, IAC-2 by AC-007..AC-010, IAC-3 by AC-011..AC-014, with AC-015..AC-019 for contract validation, forge failures and agent refusal. Outcome, non-goals (no automatic capture, video never replaces assertions, no media on branches, no Ballast-installed recorder, GitHub only) match the Issue and intake comment. Constraints honour AGENTS.md invariants: contract only in protected ballast.toml (FR-002), workflow definition from the default branch (FR-007), no secrets and read-only token (FR-006), stdlib-only tools (FR-020), new gh calls via a new ADR extending ADR-0003 (FR-015). The two clarification defaults (stale precedence, not-yet-requested listing) are recorded as PD-0005 and PD-0006 and only affect derived packet rendering. No NEEDS CLARIFICATION marker remains and the requirements checklist is complete. Risk stays R2 for the boundary on what ballast executes (docs/policies/project/workflow.md); the pre-change R2 approval is agent-provisional and the merge stays the single human approval. A live pilot (SC-001) can only run after the template reaches a default branch, so it is post-merge evidence for the plan to address, not a pre-merge privileged action. No docs/policies/project/security.md exists.

## Reviews

No review recorded yet.

## Open findings

None.

## Fix loop

- Cycles used: 0 of 3

## Block resolutions

- HD-0001 at 2026-10-06T12:51:37+00:00 by operator: resolved the postcondition block at specify; resumed in Autonomous at specify; reference: operator resumed after the postcondition block at specify

## Checks

- run-checks: not run yet
- run-checks ran in the run's worktree, so git-ignored files there were visible to them and are not part of this PR
- agent-reported: none; agent claims never satisfy run-checks

CI results appear on this PR.
