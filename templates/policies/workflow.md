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
| R2 | Authentication/authorization/access rules, resource identity semantics, deletion or destructive migration, secrets, writes to external authoritative systems, agent write authority, cryptography, CI/deployment permissions, backup/restore, breaking public data format | Human-gated: explicit human approval before the risky change and before merge. Eligible Autonomous run: the pre-change approval is agent-provisional and the merge decision is the single human approval (see [Supervision modes](#supervision-modes)). Checks and specialist reviews in both modes |

"Agent write authority" means an agent or MCP tool gaining authority to write authoritative sources or external systems, secrets, protected branches, CI or deployment permissions, or anything outside its sandbox. A development agent editing source, tests, docs and spec artifacts in its own worktree under the [bounded headless permission model](spec-kit-workflow.md#workflow-runner-contract) is normal R1-capable implementation. Feature PRs of every risk level retain human merge approval. No auto-merge or production deployment is part of this profile.

## Supervision modes

The operator picks the mode of each feature run when starting it; an agent never picks, raises or fakes it.

- **Human-gated** (the default, `ballast run start` without `--mode`): the workflow stops at every human gate (scope, intent, plan, tasks, implementation review, spec reconciliation, final acceptance). Every rule in this policy that names a human approval applies as written.
- **Autonomous** (`ballast run start --mode autonomous`): available only for an eligible feature, a scoped leaf Issue at R0, R1 or R2 that declares no unauthorized privileged action before merge, within any narrowing in `ballast.toml` `[autonomous]`. The run never prompts. At each point where the human-gated mode asks for a human approval or resolution, an agent records an **agent-provisional** decision with its basis and evidence. Intermediate approvals are therefore provisional, and **the merge decision is the single human approval, including for R2**. A provisional decision is never human approval; only merging the PR that contains it accepts it.
- **Chat** (`ballast run start --mode chat`): the operator drives the run one step at a time through `ballast run step RUN PHASE`, talks with the agent during each step, and inspects (`ballast run status RUN`) or edits files between steps. Chat keeps the human-gated approvals: every gate needs `ballast run approve` from the operator's terminal, and nothing an agent writes or says approves a gate, records a check or changes the mode. Every step runs the trusted preflight, including branch synchronization, and the same confinement and postconditions as a headless step. Stop at any time and come back later with `status` and the next `step` (`ballast run resume` refuses a Chat run). Switch a run between chat and human-gated with `ballast run mode RUN chat|human-gated --reason TEXT`; both have the same approval authority, and a switch never hides a failed check or an unapproved decision. Continue a blocked or changes-requested Autonomous run in Chat with `ballast run continue RUN ... --mode chat`. A Chat run is never raised to Autonomous. Working in a plain agent session outside `ballast run` gives none of these guarantees. The [Spec Kit workflow](spec-kit-workflow.md#chat-runs) describes the commands.

Autonomous keeps every check, postcondition, trust and tamper refusal, and every review this policy requires; it runs the independent and specialist reviews itself, and a high or critical finding blocks it (at implementation review, once its fix cycles are spent). It ends with one Draft PR whose body lists every provisional decision, or with a block that names the reason and the recovery command. It never merges, marks a PR ready, releases or deploys. An R2 Autonomous PR states that the risky change was made without prior human approval and lists the R2 boundaries it touches. Implementation findings get a bounded fix loop of three fix cycles per run; a high or critical finding still open after the third blocks the run for a human. A blocked or interrupted run resumes in Autonomous with `ballast run resume` after branch synchronization, recording the operator's block resolution; a resume never raises a limit or the mode, and its decisions stay agent-provisional. A changes-requested run, or one the operator chooses to lower, continues human-gated or in Chat through `ballast run continue`; from then on every remaining gate asks a human. Resume, the fix loop, draft retries and `ballast run checkpoint` are agent-provisional paths: the merge decision stays the single human approval. The [Spec Kit workflow](spec-kit-workflow.md#autonomous-runs) describes the lifecycle.

## Model routing

When the operator can choose the Claude Code or Codex model, follow the [model routing policy](model-routing.md). Route from workflow stage, risk and boundary triggers first; use the cheapest sufficient capability profile and reasoning effort. Only ambiguous free-form work needs the [model-routing classifier skill](../../.agents/skills/ballast-model-routing/SKILL.md). Model strength never replaces R2 human approval (before the change in a human-gated run, at merge in an Autonomous run), deterministic verification or required specialist review.

For significant work, prefer the other provider for independent plan/code/convergence review when practical and record the actual author/reviewer model, routing profile, effort and any escalation in the PR during the initial routing pilot. Subscription-authenticated clients are the default; do not introduce paid API calls merely to automate routing.

## Review triggers

Use independent reviewers where possible. A reviewer reports concrete findings with severity, location, affected invariant and required action; a clean review says what was examined. Static tools own formatting.

| Change | Required reviews |
| --- | --- |
| Normal feature | [Engineering/correctness](../../.agents/skills/ballast-engineering-review/SKILL.md) + [test](../../.agents/skills/ballast-test-review/SKILL.md) |
| Authentication, authorization, access rules, user-facing search/retrieval, secrets, agent authority | Engineering + test + [security](../../.agents/skills/ballast-security-review/SKILL.md) |
| Resource identity or architecture boundary | Engineering + test + architecture review against the relevant ADR or architecture section; add security if disclosure changes |
| Significant dependency or lockfile change | [Dependency evaluation](../../.agents/skills/ballast-dependency-evaluation/SKILL.md); [migration](../../.agents/skills/ballast-dependency-migration/SKILL.md) for foundational replacement |
| Database migration | [Database migration](../../.agents/skills/ballast-database-migration/SKILL.md) + test; add security for permissions or access rules |
| User, configuration or API behavior | [Documentation](../../.agents/skills/ballast-documentation-review/SKILL.md) |
| Significant feature before PR | Spec Kit converge + [spec reconciliation](../../.agents/skills/ballast-spec-reconciliation/SKILL.md) |

## Deterministic gates

Install dependencies from the committed lockfiles. Run the project's fast gate (static checks, unit tests) on every change and its full local gate before a behavior-bearing PR; the project file names both commands and what CI runs. Record exact commands and skipped gates in the PR. CI success is evidence, not a substitute for domain, security or architecture review. The [testing policy](testing.md) defines behavioral evidence.

## Tooling scope

The manual flow works with terminal commands, Claude Code and Codex in the IDE. A separate UI, queue, agent-state database, custom orchestration, metered API billing, automatic R1 merge and automatic deployment are outside this profile. Revisit automation only after a manual pilot demonstrates the artifacts and gates.
