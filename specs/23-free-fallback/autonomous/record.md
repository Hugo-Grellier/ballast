# Autonomous run record

Run `f200c320` for #23 (`specs/23-free-fallback`). Generated from the operator records; every check re-renders it, so an edit fails the next check. Every decision below is agent-provisional; merging the PR that contains this record is the only human approval.

## Mode and risk

- Mode start: autonomous at 2026-10-06T10:43:28+00:00 by operator
- Risk: R2 (scope-record); history: R2 at 2026-10-06T10:43:28+00:00
- Limits (default): 240 minutes wall time, 40 agent steps
- Spend: bounded by the agent-step limit; every agent step, retry and fix cycle counts; monetary spend is not measured
- Authoring integration: claude; review integration: claude
- Integration fallback: codex cannot start its own sandbox inside Ballast's confinement; claude takes both roles (DEC-0004)

## R2 notice

This is an R2 change. It was made without any prior human approval; the pre-change approval was agent-provisional (PD-0007).

R2 boundaries touched:

- headless-agent permission model
- privacy boundary for repository content
- what ballast executes

## Material provisional changes

None.

## Provisional decisions

| ID | Point | Decision | Summary | Decided by | Artifact | Evidence | Superseded by |
| --- | --- | --- | --- | --- | --- | --- | --- |
| PD-0001 | scope | accept (agent-provisional) | Issue #23 is one independently specifiable outcome: when Claude/Codex is unavailable or out of quota, one qualified zero-cost backend completes an eligible idempotent step within free-only, privacy and permission policy. | claude/claude-opus-5-5 (author) | [.specify/feature.json](../../../.specify/feature.json) `5bbe248d6d2c` | [.specify/feature.json](../../../.specify/feature.json), [.specify/workflow-state/issues/23.md](../../../.specify/workflow-state/issues/23.md), <https://github.com/Hugo-Grellier/ballast/issues/23>, [docs/policies/spec-kit-workflow.md](../../../docs/policies/spec-kit-workflow.md), [docs/policies/project/workflow.md](../../../docs/policies/project/workflow.md), [docs/policies/model-routing.md](../../../docs/policies/model-routing.md), [docs/plans/2026-10-02-product-roadmap.md](../../../docs/plans/2026-10-02-product-roadmap.md), [specs/TECHNICAL-SPEC.md](../../../specs/TECHNICAL-SPEC.md) |  |
| PD-0002 | clarification | assume (agent-provisional) | D-04: Fall back only when the failed primary attempt left the worktree, drafts and protected state unchanged. | claude/claude-opus-5-5 (author) | [specs/23-free-fallback/discovery.md](../../../specs/23-free-fallback/discovery.md) `66ea8b330df5` | [specs/23-free-fallback/discovery.md](../../../specs/23-free-fallback/discovery.md), [docs/plans/2026-10-02-product-roadmap.md](../../../docs/plans/2026-10-02-product-roadmap.md), [tools/spec_workflow/agent.py](../../../tools/spec_workflow/agent.py) |  |
| PD-0003 | clarification | assume (agent-provisional) | D-05: The opt-in is an operator-side setting, off by default, read by the trusted launcher and recorded in the run record. | claude/claude-opus-5-5 (author) | [specs/23-free-fallback/discovery.md](../../../specs/23-free-fallback/discovery.md) `66ea8b330df5` | [specs/23-free-fallback/discovery.md](../../../specs/23-free-fallback/discovery.md), [.specify/memory/constitution.md](../../../.specify/memory/constitution.md), [AGENTS.md](../../../AGENTS.md), [tools/spec_workflow/autonomy.py](../../../tools/spec_workflow/autonomy.py) |  |
| PD-0004 | clarification | assume (agent-provisional) | D-06: At most one fallback attempt per step after one recoverable primary failure; each attempt counts as an agent step. | claude/claude-opus-5-5 (author) | [specs/23-free-fallback/discovery.md](../../../specs/23-free-fallback/discovery.md) `66ea8b330df5` | [specs/23-free-fallback/discovery.md](../../../specs/23-free-fallback/discovery.md), [tools/spec_workflow/autonomy.py](../../../tools/spec_workflow/autonomy.py), [docs/plans/2026-10-02-product-roadmap.md](../../../docs/plans/2026-10-02-product-roadmap.md) |  |
| PD-0005 | clarification | assume (agent-provisional) | D-07: Capability and privacy are established by runtime probes on the operator-named model; any failed or unknown probe refuses. | claude/claude-opus-5-5 (author) | [specs/23-free-fallback/discovery.md](../../../specs/23-free-fallback/discovery.md) `66ea8b330df5` | [specs/23-free-fallback/discovery.md](../../../specs/23-free-fallback/discovery.md), [docs/plans/2026-10-02-product-roadmap.md](../../../docs/plans/2026-10-02-product-roadmap.md), [tools/spec_workflow/autonomy.py](../../../tools/spec_workflow/autonomy.py) |  |
| PD-0006 | clarification | assume (agent-provisional) | D-08: The fallback covers headless steps of human-gated and Autonomous runs; Chat interactive steps are excluded. | claude/claude-opus-5-5 (author) | [specs/23-free-fallback/discovery.md](../../../specs/23-free-fallback/discovery.md) `66ea8b330df5` | [specs/23-free-fallback/discovery.md](../../../specs/23-free-fallback/discovery.md), [specs/TECHNICAL-SPEC.md](../../../specs/TECHNICAL-SPEC.md), [tools/spec_workflow/agent.py](../../../tools/spec_workflow/agent.py) |  |
| PD-0007 | intent | accept (agent-provisional) | The spec states one coherent feature: an opt-in, default-off local zero-cost fallback for a headless step whose primary attempt failed on quota or availability and changed nothing, refused before any content is sent when free status, privacy, capability or permissions are unknown, with every attempt in the existing ledger. | claude/claude-opus-5-5 (author) | [specs/23-free-fallback/spec.md](../../../specs/23-free-fallback/spec.md) `4b4c64af8d96` | [specs/23-free-fallback/discovery.md](../../../specs/23-free-fallback/discovery.md), [specs/23-free-fallback/spec.md](../../../specs/23-free-fallback/spec.md), [.specify/workflow-state/issues/23.md](../../../.specify/workflow-state/issues/23.md), [specs/23-free-fallback/checklists/requirements.md](../../../specs/23-free-fallback/checklists/requirements.md), [specs/23-free-fallback/autonomous/record.md](../../../specs/23-free-fallback/autonomous/record.md), [docs/policies/spec-kit-workflow.md](../../../docs/policies/spec-kit-workflow.md), [docs/policies/project/workflow.md](../../../docs/policies/project/workflow.md), [docs/policies/model-routing.md](../../../docs/policies/model-routing.md), [.specify/memory/constitution.md](../../../.specify/memory/constitution.md), [AGENTS.md](../../../AGENTS.md) |  |
| PD-0008 | plan-review | accept-finding (agent-provisional) | Plan covers every AC/FR/SC with fail-closed checks and an unchanged off path; three bounded gaps (Codex user config, SC-005 reading, contract mismatch) go to tasks. | claude/claude-opus-5-5 (reviewer) | [specs/23-free-fallback/plan.md](../../../specs/23-free-fallback/plan.md) `a7dcd45d82c5` | [specs/23-free-fallback/reviews/plan.md](../../../specs/23-free-fallback/reviews/plan.md), [specs/23-free-fallback/plan.md](../../../specs/23-free-fallback/plan.md), [specs/23-free-fallback/research.md](../../../specs/23-free-fallback/research.md), [specs/23-free-fallback/contracts/wrapper-fallback.md](../../../specs/23-free-fallback/contracts/wrapper-fallback.md), [specs/23-free-fallback/contracts/ledger.md](../../../specs/23-free-fallback/contracts/ledger.md), [specs/23-free-fallback/data-model.md](../../../specs/23-free-fallback/data-model.md), [specs/23-free-fallback/spec.md](../../../specs/23-free-fallback/spec.md), [tools/spec_workflow/agent.py](../../../tools/spec_workflow/agent.py), [tools/spec_workflow/autonomy.py](../../../tools/spec_workflow/autonomy.py) |  |
| PD-0009 | plan | accept (agent-provisional) | The plan implements the agent-provisional intent (PD-0007) with one new stdlib module, an unchanged off path, fail-closed probes before any content is sent, and additive ledger records; the four plan-review findings are bounded and go to tasks. | claude/claude/claude-opus-5-5 (author) | [specs/23-free-fallback/plan.md](../../../specs/23-free-fallback/plan.md) `a7dcd45d82c5` | [specs/23-free-fallback/plan.md](../../../specs/23-free-fallback/plan.md), [specs/23-free-fallback/spec.md](../../../specs/23-free-fallback/spec.md), [specs/23-free-fallback/intent.md](../../../specs/23-free-fallback/intent.md), [specs/23-free-fallback/reviews/plan.md](../../../specs/23-free-fallback/reviews/plan.md), [specs/23-free-fallback/research.md](../../../specs/23-free-fallback/research.md), [specs/23-free-fallback/data-model.md](../../../specs/23-free-fallback/data-model.md), [specs/23-free-fallback/quickstart.md](../../../specs/23-free-fallback/quickstart.md), [specs/23-free-fallback/contracts/wrapper-fallback.md](../../../specs/23-free-fallback/contracts/wrapper-fallback.md), [specs/23-free-fallback/contracts/ledger.md](../../../specs/23-free-fallback/contracts/ledger.md), [specs/23-free-fallback/contracts/operator-cli.md](../../../specs/23-free-fallback/contracts/operator-cli.md), [specs/23-free-fallback/autonomous/record.md](../../../specs/23-free-fallback/autonomous/record.md), [AGENTS.md](../../../AGENTS.md), [docs/policies/workflow.md](../../../docs/policies/workflow.md), [docs/policies/spec-kit-workflow.md](../../../docs/policies/spec-kit-workflow.md), [docs/policies/project/workflow.md](../../../docs/policies/project/workflow.md) |  |

### PD-0001 basis

> Per the scope and decomposition gate in docs/policies/spec-kit-workflow.md, the Issue has one main outcome (a single qualified free fallback for an eligible step), a clear in/out boundary (in: evaluating and opting into one candidate, normalized recoverable-failure and capability checks, free-only/privacy/permission eligibility, bounded retries, route evidence in the existing ledger; out: broad multi-provider routing, paid overflow, hard-coded free-model lists, replaying partial mutations, account sign-up), and four acceptance criteria that form one group testable together (simulated failure selects and completes; ineligibility refuses before content is sent; ledger evidence without duplicate side effects; candidate chosen from evaluation with config and exit path). It reuses the existing ledger and routing policy (docs/policies/model-routing.md) rather than adding a subsystem, so it needs one plan. It is a leaf of Epic #11 per the intake scope comment, which the trusted runner verified. Risk stays R2: it adds an execution backend and touches what ballast executes and the headless-agent permission model (docs/policies/project/workflow.md); in this Autonomous run the pre-change decision is agent-provisional and the merge is the single human approval. The intake comment names a local Ollama candidate via the Codex CLI oss mode as the starting point; the spec must still justify the choice from evaluation evidence per the fourth criterion. No privileged action is needed before merge.

### PD-0002 basis

> Narrowest eligibility rule; it never replays a partial mutation (docs/plans/2026-10-02-product-roadmap.md line 132; Issue #23 puts replaying a partial mutation out of scope). Widening eligibility later is additive and needs no data change.

### PD-0003 basis

> Keeps the setting outside agent reach like the run's integration choice (constitution BL-INV-003, AGENTS.md invariants); nothing host-specific is committed; adding a ballast.toml section later is additive.

### PD-0004 basis

> Smallest bound that meets IAC-1; the run's existing agent-step limit stays authoritative (tools/spec_workflow/autonomy.py AGENT_STEPS); raising the bound later is a configuration change.

### PD-0005 basis

> Probes only refuse, so an error blocks a step but never sends content; this avoids the hard-coded free-model list the Issue excludes (docs/plans/2026-10-02-product-roadmap.md line 130); the probe set can be extended later.

### PD-0006 basis

> Narrows the feature: in Chat the operator is present and can switch integration manually (specs/TECHNICAL-SPEC.md section 91); adding Chat later is additive.

### PD-0007 basis

> spec.md traces to discovery.md and covers all four Issue #23 criteria: IAC-1 by AC-001 to AC-004, IAC-2 by AC-005 to AC-010, IAC-3 by AC-011 to AC-017, IAC-4 by AC-018 to AC-021. Its non-goals match the Issue and intake out-of-scope list (no multi-provider routing, paid overflow, hard-coded free-model list, partial-mutation replay, account sign-up), plus two narrowings that are additive to widen later (no direct-API harness, no Chat interactive fallback). Constraints keep the AGENTS.md invariants and constitution: same confinement and permission model, no sandbox loosening or bypass option (FR-005), stdlib-only tools (FR-011), operator-only opt-in outside agent reach (FR-001, AC-020), no account or quota detail in the ledger (FR-007, docs/policies/model-routing.md). The five assumed brief decisions D-04 to D-08 are already recorded as agent-provisional PD-0002 to PD-0006 and each picks the narrower, reversible option. No [NEEDS CLARIFICATION] marker remains and the brief has no undecided item. The known risk that the Codex sandbox may not nest inside Ballast's confinement on the host is handled by the spec: refuse as incompatible capability (AC-007) and record a rejected pilot in decisions.md rather than switching backend silently. Risk stays R2 with the boundaries already in the run record; no privileged action is needed before merge.

### PD-0008 basis

> Independent plan review against spec.md, intent.md (PD-0007), the run record and the engineering, workflow and project R2 policies. Every AC and SC maps to a planned test or artifact in quickstart.md. The code anchors the plan relies on exist in agent.py, autonomy.py, ledger.py and artifacts.py with the shapes assumed. Source authority stays single: the launcher owns the setting, the wrapper owns attempts, and the ledger stays the one record. The off path is unchanged, and every host-dependent check fails closed. The remaining gaps can each be fixed by a task and do not invalidate the design. The most important: the permission comparison ignores the user's Codex config file, so in a Claude-primary run the fallback may get MCP servers or a notify program the primary never had. tasks.md and decisions.md do not exist yet, which is expected at plan review.

### PD-0009 basis

> plan.md traces every AC-001..AC-021, FR-001..FR-011 and SC-001..SC-005 of spec.md to a design element and to a test or artifact in quickstart.md, and stays inside the spec's non-goals (no model list, no paid route, no Chat fallback, no partial-mutation replay). Its Constitution Check passes: the launcher owns the operator-only setting outside agent reach, codex is resolved as a trusted program, confinement and both sandboxes are never loosened, the ledger stays the single record with schema version 1, and tools stay stdlib-only, matching the AGENTS.md invariants. The independent plan review (reviews/plan.md, PD-0008) confirmed the code anchors exist and found no blocking defect. Its findings must be closed during tasks: F-001 (medium) needs a task that pins or refuses Codex user-config mcp_servers/notify so the fallback is never wider than the primary (AC-006, AC-008); F-002 needs the SC-005 reading in research.md R9 (draft retries predate the feature) recorded as a decision or wording clarification; F-003 needs one route_source cross-field rule shared by data-model.md and contracts/ledger.md; F-004 needs the human-gated run record for AC-020 defined. The tasks gate should refuse tasks that leave any of these unaddressed. Host facts unknown until the R10 pilot (Codex config key, --json shape, sandbox nesting) only make checks refuse, never send content. Risk stays R2 per docs/policies/project/workflow.md; the plan proposes ADR-0012 for the boundary, which stays proposed until merge. This decision is agent-provisional.

## Reviews

- PD-0008 plan: approved; reviewer claude/claude-opus-5-5; cross-provider: no; report [specs/23-free-fallback/reviews/plan.md](../../../specs/23-free-fallback/reviews/plan.md)

Reduced independence: reviews used the authoring provider.

## Open findings

- PD-0008 F-001 (medium, spec-violation, accepted-provisionally): R6 permission_mismatch and the R5 privacy probes inspect only argv, env and the Ollama model entry. Codex still reads the operator's config.toml (agent_homes only overlays CODEX_HOME), so its mcp_servers, notify program or profiles reach the fallback. A Claude primary runs with --strict-mcp-config and project-only settings, so the fallback can be wider than the actual primary (AC-008) and can send content off loopback through an MCP server or notify (AC-006). It does not block planning because the config is operator-owned, not agent-writable, and a task can close it: pin mcp_servers and notify empty through allowlisted --config overrides, or refuse as permission-mismatch when they are set, with tests and a pilot check.
- PD-0008 F-002 (low, spec-ambiguity, open): SC-005 says no step ever makes more than two attempts, but R9 reads it as two attempts beyond the existing draft-retry loop and lets a draft-retry primary fall back. That reading is reasonable, because draft retries predate this feature, but it should be recorded as a decision or a spec wording clarification rather than left implicit in research.md.
- PD-0008 F-003 (low, spec-ambiguity, open): The two contracts disagree. data-model.md says route_source fallback forbids failure_cause; contracts/ledger.md says it forbids failure_cause and fallback. Pick one rule before tasks are written so ledger tests have one source.
- PD-0008 F-004 (low, spec-ambiguity, open): AC-020 asks that the run record show whether the fallback was on. Autonomous runs get a record.md line, but a human-gated run has no record.md and writes nothing about the setting unless a fallback is considered. Its only trace is fallback.json and the printed start line. A task should state what counts as the human-gated run record.

## Checks

- run-checks: not run yet
- run-checks ran in the run's worktree, so git-ignored files there were visible to them and are not part of this PR
- agent-reported: none; agent claims never satisfy run-checks

CI results appear on this PR.
