# Agent Instructions for Ballast

Ballast is a portable agent workflow: an existing agent session turns GitHub issues into verified, independently reviewed PRs, with explicit worker routing, bounded execution and recorded evidence. This repository is its source: workflow instructions in `docs/`, stdlib helpers in `tools/`, and copy-once content for projects in `templates/`. It follows its own workflow.

## Work from the right artifact

- Layout: `docs/` (the workflow: [issue workflow](docs/issue-workflow.md), [pair review](docs/pair-review.md), [model routing](docs/model-routing.md), [execution contract](docs/execution.md), [standalone](docs/standalone.md) and [Orca](docs/orca-execution.md) adapters, [migration](docs/migration.md)), `tools/` (Codex transport and probe, worker, worktree claims, bounded queue), `templates/` (policies, `ballast-*` review skills, starter `AGENTS.md`, GitHub files), `tests/` (unittest), `docs/plans/` and `docs/evidence/` (per-issue plans and live evidence).
- Architecture: [ADR-0023](docs/adr/0023-ballast-2-portable-agent-workflow.md) and [ADR-0024](docs/adr/0024-ballast-2-migration.md) govern the current design. ADRs 0001–0021 and `specs/` are history, not current authority.

Accepted ADRs govern design; the issue states the outcome and acceptance criteria. Current code is evidence of behavior, not permission to supersede a decision. Surface conflicts and write a new ADR under `docs/adr/` for an accepted architecture change.

## Commands

- Install: `uv sync --locked`. The shipped tools are stdlib-only; only the gate's `ruff` is pinned in `uv.lock`.
- Fast gate (also CI): `uv run --locked ruff check && uv run --locked ruff format --check` and `uv run --locked python tests/parallel.py tests/test_*.py` (the same classes as `python -m unittest tests/test_*.py`, one process per class, in parallel).
- Live qualification (outside CI, when a change touches worker launch, routing or publication): a fictional issue on a disposable repository, recorded under `docs/evidence/`.
- Record exact verification commands and any unavailable gate in the PR. See the [testing policy](templates/policies/testing.md) for evidence requirements.

## Invariants

- Shipped tools use only the Python standard library and run under `python3 -I -S`. No daemon, scheduler, database service or recurring timer.
- An agent never gains more authority than its caller. Workers run under the native CLI sandbox; the helpers grant no escalation.
- Every worker has an explicit model and effort, verified before task input; a mismatch or missing observation blocks it.
- One writer per issue worktree. Unknown liveness consumes capacity and blocks a duplicate; settlement needs terminal evidence.
- GitHub is authoritative for issue relationships, PRs, merges and CI; local records never become a second source of truth.
- Agents never run in CI. Merge, release, destructive cleanup and paid services need explicit human approval.
- Shipped templates carry no project's names or domain rules. Behavior changes need tests that fail when the behavior breaks, including refusal paths.

## Issue workflow

For `Start #N`, `Fix #N`, `Investigate #N` or `Continue #N`, follow the [issue workflow](docs/issue-workflow.md). Dispatch only an actionable leaf issue. Each leaf gets its own branch and worktree; use the [standalone adapter](docs/standalone.md) or, optionally, [Orca](docs/orca-execution.md) for workers, and [pair review](docs/pair-review.md) for independent review. Write a plan under `docs/plans/` when the change needs one.

## Risk and conditional guidance

Classify R0 (docs/cleanup), R1 (normal feature, non-destructive extension) or R2. R2 here, beyond the [base list](templates/policies/workflow.md#risk): what the worker launches and its sandbox/permission arguments; claim, lock, admission and settlement semantics; what the helpers execute, push or write to GitHub; the release workflow. R2 needs explicit human approval of the change and the merge. Every PR needs human merge approval. The [review matrix](templates/policies/workflow.md#review-triggers) selects reviewers; do not run every specialist on every change.

| When changing | Read and use |
| --- | --- |
| Any implementation | [Engineering policy](templates/policies/engineering.md); [engineering review](templates/skills/ballast-engineering-review/SKILL.md) |
| Agent tools, worker permissions, secrets, GitHub writes | [Security policy](templates/policies/security.md) and [security review](templates/skills/ballast-security-review/SKILL.md) |
| Behavior or acceptance evidence | [Testing policy](templates/policies/testing.md) and [test review](templates/skills/ballast-test-review/SKILL.md) |
| Dependency or GitHub Action | [Dependency policy](templates/policies/dependencies.md) and [evaluation](templates/skills/ballast-dependency-evaluation/SKILL.md) |
| Public behavior, templates, ADR | [Documentation policy](templates/policies/documentation.md) and [documentation review](templates/skills/ballast-documentation-review/SKILL.md) |
| Retries, quota, provider failures | [Observability policy](templates/policies/observability.md) |

Never silently weaken a failing test, validation, authorization, lint/type rule or error result; change source authority; add a second source of truth; or mix unrelated refactors into the work. Resolve a genuine conflict explicitly.

## PRs and local environment

Follow the PR template: link the issue, map acceptance criteria to evidence, state risk, checks, review and execution evidence. Use a Conventional Commit PR title: Release Please builds `CHANGELOG.md` and the `vX.Y.Z` tags from it. The repository allows squash merges only.

Do not expose secrets in code, logs, examples or generated files. Keep hostnames, IPs, server paths and credentials out of tracked files, commits, issues and PRs; put local destinations in an ignored `AGENTS.local.md`. Before a destructive operation or an externally visible release action, get explicit human approval in the PR or conversation.
