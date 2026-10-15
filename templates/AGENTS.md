# Agent Instructions for [PROJECT NAME]

This file is a starting point. Copy it to the repository root (link `CLAUDE.md` to it so Claude Code and Codex share one entry point), replace the placeholders, and remove rules that do not apply. Agents load this file automatically, so it stays committed and short; detailed rules live in `docs/policies/` and the project's `docs/policies/project/`.

## Work from the right artifact

- Purpose: [WHAT THIS PROJECT DOES]
- Layout: [WHERE THE APPLICATION, MIGRATIONS, CLIENTS AND TESTS LIVE]
- Architecture and domain: [ACCEPTED ARCHITECTURE DOCUMENT], ADRs in [ADR DIRECTORY], domain glossary in [GLOSSARY PATH].

Accepted ADRs and the accepted architecture govern design; the issue states the outcome and acceptance criteria. Current code is evidence of behavior, not permission to supersede a decision. Surface conflicts and write a new ADR for an accepted architecture change. Read only the relevant architecture sections and ADRs when changing domain behavior or a boundary.

## Commands

- Install: [LOCKED DEPENDENCY INSTALL COMMANDS]
- Fast gate: [COMMAND]. Full local gate: [COMMAND].
- Record exact verification commands and any unavailable gate in the PR. See the [testing policy](docs/policies/testing.md) for evidence requirements.

## Invariants

- [PROJECT INVARIANTS]

## Issue workflow

Ballast source: [PATH TO A BALLAST CHECKOUT AT THE ADOPTED TAG]. Its `docs/` holds the workflow; read only the file the current phase needs.

- For `Start #N`, `Fix #N`, `Investigate #N` or `Continue #N`, follow its `docs/issue-workflow.md`: read the issue and comments, scope and decompose, ask only consequential questions, plan as needed, implement, verify, review, publish. Dispatch only an actionable leaf issue, never an unresolved Epic.
- Each implementing issue gets its own branch and worktree with one writer. Workers use an explicit model and effort, verified before task input (`docs/model-routing.md`). Without Orca, use `docs/standalone.md`; with Orca, `docs/orca-execution.md`.
- An independent reviewer follows `docs/pair-review.md`, at most three review/fix rounds, then escalate to a human.
- Record phases, blockers, review rounds and waits on the issue; unknown stays unknown. Agents run outside CI; CI runs deterministic checks only.

## Risk and conditional guidance

Classify R0 (docs/cleanup), R1 (normal feature, non-destructive extension) or R2 ([PROJECT R2 BOUNDARIES; see `docs/policies/workflow.md`]). R2 requires explicit human approval of the risky change and of the merge. Every PR needs human merge approval; an agent never merges, releases or deploys, and an agent decision is never presented as human approval. The [review matrix](docs/policies/workflow.md#review-triggers) selects reviewers; do not run every specialist on every change.

| When changing | Read and use |
| --- | --- |
| Any implementation | [Engineering policy](docs/policies/engineering.md); [engineering review](.agents/skills/ballast-engineering-review/SKILL.md) for feature review |
| Auth, access rules, search/retrieval, user-facing access, secrets, agent tools | [Security policy](docs/policies/security.md) and [security review](.agents/skills/ballast-security-review/SKILL.md) |
| Behavior or acceptance evidence | [Testing policy](docs/policies/testing.md) and [test review](.agents/skills/ballast-test-review/SKILL.md) |
| Dependency or provider | [Dependency policy](docs/policies/dependencies.md) and [evaluation](.agents/skills/ballast-dependency-evaluation/SKILL.md); [migration](.agents/skills/ballast-dependency-migration/SKILL.md) for foundational replacement |
| Schema/data migration | [Migration policy](docs/policies/migrations.md) and [database migration](.agents/skills/ballast-database-migration/SKILL.md) |
| Public behavior, config, API, ADR | [Documentation policy](docs/policies/documentation.md) and [documentation review](.agents/skills/ballast-documentation-review/SKILL.md) |
| Jobs, retries, provider failures | [Observability policy](docs/policies/observability.md) |

Each policy also reads `docs/policies/project/<name>.md` when it exists.

Never silently weaken a failing test, validation, authorization, lint/type rule or error result; change source authority; add a second source of truth; or mix unrelated refactors into the work. Resolve a genuine conflict explicitly.

## PRs and local environment

Link the issue, map its acceptance criteria to evidence, state risk, checks and reviews; include screenshots for visible UI changes. [RELEASE OR COMMIT-TITLE CONVENTION]

Do not expose secrets in code, logs, examples or generated files. Keep hostnames, IPs, server paths and credentials out of tracked files, commits, issues and PRs; put local destinations in an ignored `AGENTS.local.md`. Before a destructive operation or an externally visible release action, follow the project's approval process: [PROCESS OR LINK]
