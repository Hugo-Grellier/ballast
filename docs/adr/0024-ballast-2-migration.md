# ADR-0024: Ballast 2.0 replaces the v1 installer, launcher and runner

- Status: proposed (2026-10-15, with the change for [#180](https://github.com/Hugo-Grellier/ballast/issues/180)). The operator decided the scope in conversation; merging the PR is the human approval that accepts it.
- Risk: R2 (removes what `ballast` executes, the trust model and the installed paths).
- Accepts: [ADR-0023](0023-ballast-2-portable-agent-workflow.md).
- Supersedes: ADRs 0001–0021 (both files numbered 0019 and both numbered 0021) and the v1 constitution (`.specify/memory/constitution.md`, version 1.3.0, kept in history and at the `v1.x` tags).

## Context

ADR-0023 proposed a portable agent workflow and required a migration to name every
replaced v1 decision and removed guarantee. #177 and #178 delivered the standalone
issue-to-PR slice and the bounded queue with live evidence. The optional Orca adapter
(#179) is not part of 2.0: Orca exposes no native routing receipt before task delivery,
and the operator dropped it on 2026-10-15. Standalone is the only execution path. The operator decided on 2026-10-15 that v1 tests and tools are not needed for
2.0 (removed in #185), that this repository switches fully to 2.0, and that projects keep
the generic policies and review skills as copy-once content.

## Decision

- Ballast 2.0 is the workflow in `docs/`, the stdlib helpers in `tools/` and the
  copy-once content in `templates/`. There is no installer, pinned install, trusted
  launcher, run ledger or `ballast` command. A project copies the templates it wants
  and runs the helpers from a Ballast checkout it selected.
- ADR-0023 is accepted. ADRs 0001–0021 and the v1 constitution describe v1.x only.
  They stay unchanged as records, each marked superseded by this ADR.
- `specs/` stays as the v1.x product, technical and feature record. Current authority
  is ADR-0023, this ADR and `docs/`.
- The 2.0 invariants replace the constitution:
  - Shipped tools use only the Python standard library and run under `python3 -I -S`.
    No daemon, scheduler, database service or recurring timer.
  - An agent never gains more authority than its caller. Workers run under the
    native CLI sandbox, and the helpers grant no escalation.
  - Every worker has an explicit model and effort, verified before task input. A
    mismatch or missing observation blocks it.
  - One writer per issue worktree. Unknown liveness consumes capacity and blocks a
    duplicate, and settlement needs terminal evidence.
  - GitHub is authoritative for issue relationships, PRs, merges and CI. Local
    records never become a second source of truth.
  - Agents never run in CI. Merge, release, destructive cleanup and paid services
    need explicit human approval.
  - Shipped templates carry no project's names or domain rules. Behavior changes
    need tests that fail when the behavior breaks.

## Removed guarantees

| v1 guarantee (source) | In 2.0 |
| --- | --- |
| A project commits only its own files; everything installed is git-ignored and rebuildable (BL-INV-001, ADR-0007/0011/0012) | Changed. Project ownership stays, but nothing is installed: copied templates become the project's own committed files |
| A verified install of a pinned version; the project picks a version, never a source, and the source repository is fixed in the command (BL-INV-004, ADR-0001/0002/0008) | Removed. The operator chooses the Ballast checkout and its tag; nothing verifies the origin or content of the helpers |
| Nothing executes from a writable checkout before trust; trust baselines and refresh (BL-INV-002, ADR-0003/0005/0015/0021) | Removed. The coordinator and the helpers run with the caller's authority from the operator's checkout |
| Protected inputs and tamper markers fail a step closed (BL-INV-003) | Removed. Workers are confined by the native CLI sandbox. Coordinator records are cooperative and can be edited by the operator or a peer with the same access |
| Postcondition-checked phases, artifact validators, run ledger and acceptance packet (BL-INV-005, ADR-0006/0017/0018) | Replaced by phase records on the issue, PR acceptance evidence, independent review and settlement on backend terminal evidence. Missing evidence is reported as unknown |
| Human-gated, Chat and Autonomous runs; agent-provisional decisions and relays (BL-INV-006, ADR-0004/0009/0010/0016/0019/0020/0021) | Replaced by one coordinator session with independent review. Human merge stays the approval, and no agent merges or marks a decision as human |
| Demo capture, local zero-cost fallback, check commands run like CI (ADR-0013/0014/0021) | Removed. CI runs the project's deterministic checks |

## Consequences

- Projects pinned to a `v1.x` tag keep working unchanged. `docs/migration.md` describes
  how to stay on v1, adopt 2.0 or roll back.
- Release Please publishes 2.0.0 without the `ballast` CLI asset, after the operator
  approves the release PR.
- Open v1 issues are closed or superseded with links, as listed in the migration plan.
