# Agent-first development workflow

This is the operational profile: risk classification, review triggers and deterministic gates. Agents use this file, `AGENTS.md`, the Spec Kit artifacts and conditional policies for daily work. Project-specific risk boundaries, gate commands and review triggers live in [`project/workflow.md`](project/workflow.md) when the project provides one; they extend this policy and win on conflict.

## Work and artifacts

GitHub Issues are the work queue, discussion, dependency and status surface. A small bug or narrow technical task can carry its full scope and acceptance criteria in the issue. A significant new feature uses `specs/<number>-<slug>/spec.md`, `plan.md` and `tasks.md` created by Spec Kit. The issue links the durable spec. Do not turn Spec Kit into the architecture record or migrate completed work.

`ready-for-agent` applies to a leaf Issue that passed the [scope gate](spec-kit-workflow.md#scope-and-decomposition-gate); an unresolved Epic coordinates child work and is not dispatched for implementation. The implementation plan is created **after** dispatch. Read the issue and comments, then the feature spec if present. Read the domain glossary and relevant architecture sections/ADRs only when the change touches domain or architecture.

The [Spec Kit workflow](spec-kit-workflow.md) owns the detailed feature lifecycle, human intent/plan/final gates, dependency waves, cross-model handoffs and feature-local decisions. `speckit-intent-implement` is available, while normal IDE and terminal implementation remain supported with explicit reconciliation. Spec Kit's `converge` appends missing work to `tasks.md`; it does not amend `spec.md` to excuse code. Stop automated fix attempts after three cycles and escalate unresolved findings to a human.

For each significant spec, state source authority, identity, access rules, persistence, partial failure, provider/offline behavior, migration, observability and rollback when relevant. Plans identify affected boundaries, test seams and conditional reviews. Keep irrelevant headings out of small specs.

## Risk

Classify the change in its issue/PR before implementation. Raise risk if the actual diff crosses a stronger boundary. The project file lists its own R2 boundaries.

| Level | Typical changes | Gate |
| --- | --- | --- |
| R0 | Typo, docs, test-only cleanup, naming, formatting | Deterministic checks; review optional |
| R1 | Normal UI/API feature, search/index, background job, provider behind an existing boundary, non-destructive schema extension, read-only integration | Checks, correctness and test reviews; specialists by trigger |
| R2 | Authentication/authorization/access rules, resource identity semantics, deletion or destructive migration, secrets, writes to external authoritative systems, agent write authority, cryptography, CI/deployment permissions, backup/restore, breaking public data format | Explicit human approval before the risky change and before merge; checks and specialist reviews |

"Agent write authority" means an agent or MCP tool gaining authority to write authoritative sources or external systems, secrets, protected branches, CI or deployment permissions, or anything outside its sandbox. A development agent editing source, tests, docs and spec artifacts in its own worktree under the [bounded headless permission model](spec-kit-workflow.md#workflow-runner-contract) is normal R1-capable implementation. Feature PRs of every risk level retain human merge approval. No auto-merge or production deployment is part of this profile.

## Model routing

When the operator can choose the Claude Code or Codex model, follow the [model routing policy](model-routing.md). Route from workflow stage, risk and boundary triggers first; use the cheapest sufficient capability profile and reasoning effort. Only ambiguous free-form work needs the [model-routing classifier skill](../../.agents/skills/agentic-model-routing/SKILL.md). Model strength never replaces R2 human approval, deterministic verification or required specialist review.

For significant work, prefer the other provider for independent plan/code/convergence review when practical and record the actual author/reviewer model, routing profile, effort and any escalation in the PR during the initial routing pilot. Subscription-authenticated clients are the default; do not introduce paid API calls merely to automate routing.

## Review triggers

Use independent reviewers where possible. A reviewer reports concrete findings with severity, location, affected invariant and required action; a clean review says what was examined. Static tools own formatting.

| Change | Required reviews |
| --- | --- |
| Normal feature | [Engineering/correctness](../../.agents/skills/agentic-engineering-review/SKILL.md) + [test](../../.agents/skills/agentic-test-review/SKILL.md) |
| Authentication, authorization, access rules, user-facing search/retrieval, secrets, agent authority | Engineering + test + [security](../../.agents/skills/agentic-security-review/SKILL.md) |
| Resource identity or architecture boundary | Engineering + test + architecture review against the relevant ADR or architecture section; add security if disclosure changes |
| Significant dependency or lockfile change | [Dependency evaluation](../../.agents/skills/agentic-dependency-evaluation/SKILL.md); [migration](../../.agents/skills/agentic-dependency-migration/SKILL.md) for foundational replacement |
| Database migration | [Database migration](../../.agents/skills/agentic-database-migration/SKILL.md) + test; add security for permissions or access rules |
| User, configuration or API behavior | [Documentation](../../.agents/skills/agentic-documentation-review/SKILL.md) |
| Significant feature before PR | Spec Kit converge + [spec reconciliation](../../.agents/skills/agentic-spec-reconciliation/SKILL.md) |

## Deterministic gates

Install dependencies from the committed lockfiles. Run the project's fast gate (static checks, unit tests) on every change and its full local gate before a behavior-bearing PR; the project file names both commands and what CI runs. Record exact commands and skipped gates in the PR. CI success is evidence, not a substitute for domain, security or architecture review. The [testing policy](testing.md) defines behavioral evidence.

## Tooling scope

The manual flow works with terminal commands, Claude Code and Codex in the IDE. A separate UI, queue, agent-state database, custom orchestration, metered API billing, automatic R1 merge and automatic deployment are outside this profile. Revisit automation only after a manual pilot demonstrates the artifacts and gates.
