# Ballast

Ballast turns GitHub issues into verified, independently reviewed PRs from the agent
session you already use. The agent coordinates: it scopes the issue, asks only
consequential questions, starts workers with an explicit model and effort in a
separate worktree, runs the checks, gets an independent review and publishes the
PR. You write the issue and decide the merge.

Ballast is a set of workflow instructions, a few standard-library helpers and
copy-once project templates. It installs nothing, runs no daemon and puts no agent
in CI. Projects still on a `v1.x` pin keep working; see
[migrating from 1.x](docs/migration.md).

## Workflow

| Document | Purpose |
| --- | --- |
| [Issue workflow](docs/issue-workflow.md) | Read, scope and decompose, plan, implement, verify, review, publish, with phase records |
| [Pair review](docs/pair-review.md) | Independent review and bounded repair |
| [Model routing](docs/model-routing.md) | Explicit provider, model and effort, verified before task input |
| [Execution contract](docs/execution.md) | Worktrees, ownership, limits and recovery |
| [Standalone adapter](docs/standalone.md) | Workers, worktree claims and the bounded queue without Orca |
| [Orca adapter](docs/orca-execution.md) | Optional: the same contract on Orca |

The [standalone adapter](docs/standalone.md) uses three helpers, run with
`python3 -I -S` from a Ballast checkout:

- [`tools/worktree.py`](tools/worktree.py) claims an issue and prepares its worktree.
- [`tools/worker.py`](tools/worker.py) runs a fresh Codex worker after verifying its
  routing.
- [`tools/coordinate.py`](tools/coordinate.py) runs a finite issue queue: admission,
  limits, pause/cancel/quota, recovery, idempotent draft publication and timing
  status.

Live evidence for each slice is in [`docs/evidence/`](docs/evidence/). The supported
host is a POSIX machine with Python 3.11+, Git, an authenticated `gh` for GitHub.com
and a supported Codex CLI; [standalone](docs/standalone.md#scope-and-limits) lists the
limits.

## Adopting Ballast in a project

Review and copy what you want from [`templates/`](templates/), then follow
[adopting Ballast](docs/migration.md#adopting-20):

- [`AGENTS.md`](templates/AGENTS.md): a short agent entry point to fill in;
- [`policies/`](templates/policies/): engineering, security, testing, dependency,
  migration, documentation, observability, workflow (risk and review matrix) and
  issue-tracker rules;
- [`skills/`](templates/skills/): `ballast-*` review skills for engineering, tests,
  security, documentation, dependencies and database migrations;
- [`github/`](templates/github/): PR and issue templates, Dependabot and a
  Conventional Commit PR-title check.

## Decisions and history

[ADR-0023](docs/adr/0023-ballast-2-portable-agent-workflow.md) and
[ADR-0024](docs/adr/0024-ballast-2-migration.md) define the current design and the 1.x guarantees it
removed. Earlier ADRs, [`specs/`](specs/) and the `v1.x` tags are the 1.x record; the
[v1.1.0 README](https://github.com/Hugo-Grellier/ballast/blob/v1.1.0/README.md)
documents 1.x usage.

## Contributing

See [`AGENTS.md`](AGENTS.md). Release Please opens a release PR from Conventional
Commit titles on `main`; merging it, after human approval, tags `vX.Y.Z` and updates
`CHANGELOG.md`.

## License

[MIT](LICENSE).
