# Agent-first development workflow

This is the operational profile: risk classification, review triggers and deterministic gates. Agents use this file, `AGENTS.md`, the Ballast [issue workflow](https://github.com/Hugo-Grellier/ballast/blob/main/docs/issue-workflow.md) and conditional policies for daily work. Project-specific risk boundaries, gate commands and review triggers live in [`project/workflow.md`](project/workflow.md) when the project provides one; they extend this policy and win on conflict.

## Work and artifacts

GitHub Issues are the work queue, discussion, dependency and status surface; PRs carry acceptance and review evidence. An issue states the outcome and acceptance criteria. Dispatch only an actionable leaf issue; an unresolved Epic coordinates child work and is not implemented directly. Plan after dispatch, and only as much as the change needs. Consequential architecture decisions become ADRs. Read the domain glossary and relevant architecture sections/ADRs only when the change touches domain or architecture.

Each implementing issue uses its own branch and worktree. Stop automated fix attempts at the pair-review round limit and escalate unresolved findings to a human.

## Risk

Classify the change in its issue/PR before implementation. Raise risk if the actual diff crosses a stronger boundary. The project file lists its own R2 boundaries.

| Level | Typical changes | Gate |
| --- | --- | --- |
| R0 | Typo, docs, test-only cleanup, naming, formatting | Deterministic checks; independent review that confirms R0 before an agent merge |
| R1 | Normal UI/API feature, search/index, background job, provider behind an existing boundary, non-destructive schema extension, read-only integration | Checks, correctness and test reviews; specialists by trigger |
| R2 | Authentication/authorization/access rules, resource identity semantics, deletion or destructive migration, secrets, writes to external authoritative systems, agent write authority, cryptography, CI/deployment permissions, backup/restore, breaking public data format | Explicit human approval of the risky change and of the merge. Checks and specialist reviews |

"Agent write authority" means an agent or MCP tool gaining authority to write authoritative sources or external systems, secrets, protected branches, CI or deployment permissions, or anything outside its sandbox. A development agent editing source, tests and docs in its own worktree under the native CLI sandbox is normal R1-capable implementation. R1 and R2 PRs need human merge approval. An agent never releases or deploys on its own, and an agent decision is never presented as human approval.

An R0 PR may be squash-merged by the coordinating agent without a separate human approval only when all of these hold on the PR's current head:

- an independent review approved that exact head and confirmed R0; the risk classification is part of the reviewed evidence, and a reviewer who would raise it does not approve the PR as R0;
- every required check passed on that head, and at least one check is required;
- the PR is open, not a draft, ticks R0 and no other risk, and its head equals the reviewed head.

Release PRs, dependency PRs and any change to `.github/` (workflows, permissions), release files or dependency manifests and lockfiles always need a human merge, as does a PR whose risk is disputed. The Ballast `tools/merge_check.py` helper checks these conditions, refuses an incomplete or malformed changed-file list, and merges only on explicit request, pinned to the reviewed head; pass the project's other dependency manifests or deployment paths with `--exclude GLOB`. A project can keep human merge for every PR in its project file.

## Model routing

Follow the Ballast [model routing](https://github.com/Hugo-Grellier/ballast/blob/main/docs/model-routing.md) guidance: explicit model and effort per worker, verified before task input, the lowest sufficient setting, escalation from evidence. Model strength never replaces R2 human approval, deterministic verification or required specialist review. Prefer the other provider for independent review of significant work when practical. Subscription-authenticated clients are the default; do not introduce paid API calls merely to automate routing.

## Review triggers

Use independent reviewers where possible. A reviewer reports concrete findings with severity, location, affected invariant and required action; a clean review says what was examined. Static tools own formatting.

| Change | Required reviews |
| --- | --- |
| Normal feature | [Engineering/correctness](../../.agents/skills/ballast-engineering-review/SKILL.md) + [test](../../.agents/skills/ballast-test-review/SKILL.md) |
| Authentication, authorization, access rules, user-facing search/retrieval, secrets, agent authority | Engineering + test + [security](../../.agents/skills/ballast-security-review/SKILL.md) |
| Resource identity or architecture boundary | Engineering + test + architecture review against the relevant ADR or architecture section; add security if disclosure changes |
| Significant dependency, lockfile or GitHub Action change | [Dependency evaluation](../../.agents/skills/ballast-dependency-evaluation/SKILL.md); [migration](../../.agents/skills/ballast-dependency-migration/SKILL.md) for foundational replacement |
| Database migration | [Database migration](../../.agents/skills/ballast-database-migration/SKILL.md) + test; add security for permissions or access rules |
| User, configuration or API behavior | [Documentation](../../.agents/skills/ballast-documentation-review/SKILL.md) |

## Deterministic gates

Install dependencies from the committed lockfiles. Run the project's fast gate (static checks, unit tests) on every change and its full local gate before a behavior-bearing PR; the project file names both commands and what CI runs. Record exact commands and skipped gates in the PR. CI runs deterministic checks only, never agents. CI success is evidence, not a substitute for domain, security or architecture review. The [testing policy](testing.md) defines behavioral evidence.
