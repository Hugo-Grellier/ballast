# Agent Instructions for Ballast

Ballast is a reusable standard that projects install with `ballast setup`. This repository dogfoods it: `ballast.toml` pins a released version, and the installed policies and skills in `docs/policies/` and `.agents/skills/ballast-*` govern work here like in any other project.

## Work from the right artifact

- Purpose: ship the agent-first engineering standard that projects pin and install.
- Layout: `tools/` (the `ballast` command, `init`, `setup`, the Spec Kit workflow tools and intake helper), `templates/` (policies, skills, Spec Kit workflow and templates, `init/` templates for `ballast init`, copy-once `AGENTS.md` and GitHub files), `tests/` (unittest), `specs/` (product and technical specifications), `docs/plans/` (backport plan).
- Architecture and domain: [`specs/TECHNICAL-SPEC.md`](specs/TECHNICAL-SPEC.md) and [`specs/PRODUCT-SPEC.md`](specs/PRODUCT-SPEC.md). There are no ADRs yet; record a new decision under `docs/adr/`.

Accepted ADRs and the accepted architecture govern design. A ready feature spec in `specs/<number>-<slug>/` defines current requirements, followed by its reviewed plan and tasks. Current code is evidence of behavior, not permission to supersede a decision. Surface conflicts and write a new ADR for an accepted architecture change. Read only the relevant architecture sections and ADRs when changing domain behavior or a boundary.

## Commands

- Install: nothing to install; the tools are stdlib-only. Tests need `pyyaml`, supplied by `uv run --with`.
- Fast gate: `uvx ruff check && uvx ruff format --check` and `uv run --no-project --python 3.13 --with pyyaml python -m unittest tests/test_*.py`. Full local gate: the same suite on a Linux machine with a systemd user session, the Codex CLI and the Spec Kit CLI, so the tests CI skips (real systemd, `bwrap`, Codex sandbox, Spec Kit CLI) also run.
- Record exact verification commands and any unavailable gate in the PR. See the [testing policy](docs/policies/testing.md) for evidence requirements.

## Invariants

- A project commits only `ballast.toml`, its constitution, `docs/policies/project/` and copy-once files; everything else Ballast installs is git-ignored and rebuildable.
- Workflow tools stay standard-library-only and run under `python3 -I -S`; nothing the launcher executes comes from a checkout an agent can write.
- An agent never gains more authority than its caller; protected inputs (`ballast.toml`, `.ballast/`, `.specify/`, `.venv/`) fail closed when changed.

Read the [constitution](.specify/memory/constitution.md) when planning a significant feature or checking a conflict.

## Issue and spec workflow

GitHub Issues track status, discussion, dependencies and implementation progress; they do not replace accepted product or feature intent. Read the issue and comments. Before `speckit.specify`, apply the [scope gate](docs/policies/spec-kit-workflow.md#scope-and-decomposition-gate): dispatch only an actionable leaf Issue, never an unresolved Epic. Use the full Spec Kit workflow for new features and meaningful behavior changes, the bugfix workflow for a small bounded fix, and the assess workflow for research or a spike. Before changing a feature, read its `intent.md`, `spec.md`, `plan.md`, `tasks.md`, review reports and unresolved `decisions.md` as applicable. The human approves intent, material plan changes and final acceptance. Tasks use explicit dependencies and execution waves, and each acceptance criterion has test or other verification evidence.

For `Start #N`, `Fix #N`, `Investigate #N`, or `Continue #N`, use the [feature-intake skill](.agents/skills/ballast-feature-intake/SKILL.md). It inspects the Issue, applies the scope gate, reconciles approved GitHub setup, and hands off to the existing workflow. Start and resume feature runs only through `ballast run`; if it refuses, stop and report why. Only the operator runs `ballast trust`.

Chat mode lets the operator drive a run conversationally: `ballast run start --mode chat -i feature_directory=specs/N-slug`, then `ballast run step RUN PHASE`, `ballast run status RUN` and `ballast run mode RUN chat|human-gated --reason TEXT`; a Chat run continues with `status` and the next `step`, never `resume`. Every gate needs `ballast run approve` from the operator's terminal: an agent in a Chat step never approves, never claims an approval and never runs `ballast run`. A plain agent session outside `ballast run` gets none of the run's guarantees. See [Chat runs](docs/policies/spec-kit-workflow.md#chat-runs).

Spec Kit artifacts and accepted product/technical documents are authoritative for intent. When implementation evidence conflicts with approved intent, stop at the conflict and record a feature-local proposal in `decisions.md`; agents may fix defects and clarify wording without a proposal, but every other discovery needs a human resolution, and product behavior, scope, data authority, security boundaries or accepted architecture changes require human approval. Update the spec, plan and tasks after approval before continuing. Reviews label findings as spec violation, implementation bug, architecture issue, missing test, spec ambiguity or proposed product change. Model roles are interchangeable; do not configure a permanent author/reviewer pairing. See the [Spec Kit workflow](docs/policies/spec-kit-workflow.md), the [risk and review matrix](docs/policies/workflow.md) and the [issue guidance](docs/policies/issue-tracker.md). Do not retrofit completed work.

## Risk and conditional guidance

Classify R0 (docs/cleanup), R1 (normal feature, non-destructive extension) or R2 (see [`docs/policies/project/workflow.md`](docs/policies/project/workflow.md): headless-agent permissions, the launcher's trust model, what `ballast` executes or downloads, installed-path ignore rules). R2 requires explicit human approval: before the change in a human-gated run; in an eligible Autonomous run (`ballast run start --mode autonomous`), every intermediate decision is agent-provisional and the merge decision is the single human approval, including for R2. A provisional decision is never human approval. All feature PRs require human merge approval. The [review matrix](docs/policies/workflow.md#review-triggers) selects reviewers; do not run every specialist on every change.

| When changing | Read and use |
| --- | --- |
| Any implementation | [Engineering policy](docs/policies/engineering.md); [engineering review](.agents/skills/ballast-engineering-review/SKILL.md) for feature review |
| Auth, access rules, search/retrieval, user-facing access, secrets, agent tools | [Security policy](docs/policies/security.md) and [security review](.agents/skills/ballast-security-review/SKILL.md) |
| Behavior or acceptance evidence | [Testing policy](docs/policies/testing.md) and [test review](.agents/skills/ballast-test-review/SKILL.md) |
| Dependency or provider | [Dependency policy](docs/policies/dependencies.md) and [evaluation](.agents/skills/ballast-dependency-evaluation/SKILL.md); [migration](.agents/skills/ballast-dependency-migration/SKILL.md) for foundational replacement |
| Schema/data migration | [Migration policy](docs/policies/migrations.md) and [database migration](.agents/skills/ballast-database-migration/SKILL.md) |
| Public behavior, config, API, ADR | [Documentation policy](docs/policies/documentation.md) and [documentation review](.agents/skills/ballast-documentation-review/SKILL.md) |
| Jobs, retries, provider failures | [Observability policy](docs/policies/observability.md) |
| Significant spec completion | Resolve feature decisions, run Spec Kit converge and [spec reconciliation](.agents/skills/ballast-spec-reconciliation/SKILL.md) |

Each policy also reads `docs/policies/project/<name>.md` when it exists.

Never silently weaken a failing test, validation, authorization, lint/type rule or error result; change source authority; add a second source of truth; or mix unrelated refactors into the work. Resolve a genuine conflict explicitly.

## Model routing

When model choice is under operator control, follow [model routing](docs/policies/model-routing.md): use deterministic workflow/risk rules before classification, choose the lowest sufficient `economy`/`standard`/`senior` profile, and escalate from evidence rather than by default. Use the [routing classifier](.agents/skills/ballast-model-routing/SKILL.md) only for ambiguous work. Prefer cross-provider independent review for significant features when practical. Do not switch to a paid API or store account/quota details in the repository.

## PRs and local environment

Link the issue and spec, state risk, checks and required reviews; include screenshots for visible UI changes. Use a Conventional Commit PR title: Release Please builds `CHANGELOG.md` and the `vX.Y.Z` tags projects pin from it. Prefer a merge commit or rebase so each change keeps its own changelog entry.

Do not expose secrets in code, logs, examples or generated files. Keep hostnames, IPs, server paths and credentials out of tracked files, commits, issues and PRs; put local destinations in an ignored `AGENTS.local.md`. Before a destructive operation or an externally visible release action, get explicit human approval in the PR or conversation.
