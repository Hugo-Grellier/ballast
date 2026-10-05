# Autonomous run record

Run `8935922b` for #14 (`specs/14-recoverable-install`). Generated from the operator records; every check re-renders it, so an edit fails the next check. Every decision below is agent-provisional; merging the PR that contains this record is the only human approval.

## Mode and risk

- Mode start: autonomous at 2026-10-05T21:54:30+00:00 by operator
- Risk: R2 (scope-record); history: R2 at 2026-10-05T21:54:30+00:00
- Limits (default): 240 minutes wall time, 30 agent steps
- Authoring integration: claude; review integration: claude
- Integration fallback: codex cannot start its own sandbox inside Ballast's confinement; claude takes both roles (DEC-0004)

## R2 notice

This is an R2 change. It was made without any prior human approval; the pre-change approval was agent-provisional (PD-0007).

R2 boundaries touched:

- paths tools/setup installs, removes or preserves
- what ballast executes or downloads

## Material provisional changes

None.

## Provisional decisions

| ID | Point | Decision | Summary | Decided by | Artifact | Evidence | Superseded by |
| --- | --- | --- | --- | --- | --- | --- | --- |
| PD-0001 | scope | accept (agent-provisional) | Issue #14 is one independently specifiable leaf outcome: a failed setup or pin update leaves the previous usable installation and paused run evidence intact. | claude/claude-opus-5-5 (author) | [.specify/feature.json](../../../.specify/feature.json) `19ee175ad99b` | [.specify/feature.json](../../../.specify/feature.json), [.specify/workflow-state/issues/14.md](../../../.specify/workflow-state/issues/14.md), <https://github.com/Hugo-Grellier/ballast/issues/14>, [docs/policies/spec-kit-workflow.md](../../../docs/policies/spec-kit-workflow.md), [docs/policies/project/workflow.md](../../../docs/policies/project/workflow.md), [specs/TECHNICAL-SPEC.md](../../../specs/TECHNICAL-SPEC.md), [specs/12-cli-install-doctor](../../../specs/12-cli-install-doctor), [AGENTS.md](../../../AGENTS.md) |  |
| PD-0002 | clarification | assume (agent-provisional) | Damaged cached version: refetch a fresh copy when reachable, else refuse naming the damaged path | claude/claude-opus-5-5 (author) | [specs/14-recoverable-install/spec.md](../../../specs/14-recoverable-install/spec.md) `beebca872e21` | [specs/14-recoverable-install/spec.md](../../../specs/14-recoverable-install/spec.md), [docs/policies/spec-kit-workflow.md](../../../docs/policies/spec-kit-workflow.md) |  |
| PD-0003 | clarification | assume (agent-provisional) | Holder liveness for checkout and cache locks is checked on the same machine only | claude/claude-opus-5-5 (author) | [specs/14-recoverable-install/spec.md](../../../specs/14-recoverable-install/spec.md) `beebca872e21` | [specs/14-recoverable-install/spec.md](../../../specs/14-recoverable-install/spec.md) |  |
| PD-0004 | clarification | assume (agent-provisional) | Setup refusing on an unfinished agent step names the existing launcher recovery and never clears the marker | claude/claude-opus-5-5 (author) | [specs/14-recoverable-install/spec.md](../../../specs/14-recoverable-install/spec.md) `beebca872e21` | [specs/14-recoverable-install/spec.md](../../../specs/14-recoverable-install/spec.md), [tools/spec_workflow/launcher.py](../../../tools/spec_workflow/launcher.py) |  |
| PD-0005 | clarification | assume (agent-provisional) | A second setup in the same checkout refuses; a second same-version cache fetch waits | claude/claude-opus-5-5 (author) | [specs/14-recoverable-install/spec.md](../../../specs/14-recoverable-install/spec.md) `beebca872e21` | [specs/14-recoverable-install/spec.md](../../../specs/14-recoverable-install/spec.md), [specs/14-recoverable-install/checklists/requirements.md](../../../specs/14-recoverable-install/checklists/requirements.md) |  |
| PD-0006 | clarification | assume (agent-provisional) | A target version that declares no run-state compatibility is treated as unable to resume runs | claude/claude-opus-5-5 (author) | [specs/14-recoverable-install/spec.md](../../../specs/14-recoverable-install/spec.md) `beebca872e21` | [specs/14-recoverable-install/spec.md](../../../specs/14-recoverable-install/spec.md), [specs/14-recoverable-install/checklists/requirements.md](../../../specs/14-recoverable-install/checklists/requirements.md) |  |
| PD-0007 | intent | accept (agent-provisional) | Agent-provisional intent: spec.md for #14 is one coherent feature (recoverable setup, safe concurrent/repeated setup, read-only pin-update preview, documented rollback) with clear constraints, non-goals and traceable acceptance criteria AC-001..AC-024, and no unresolved marker. | claude/claude-opus-5-5 (author) | [specs/14-recoverable-install/spec.md](../../../specs/14-recoverable-install/spec.md) `beebca872e21` | [specs/14-recoverable-install/spec.md](../../../specs/14-recoverable-install/spec.md), [specs/14-recoverable-install/checklists/requirements.md](../../../specs/14-recoverable-install/checklists/requirements.md), [.specify/workflow-state/issues/14.md](../../../.specify/workflow-state/issues/14.md), <https://github.com/Hugo-Grellier/ballast/issues/14>, [AGENTS.md](../../../AGENTS.md), [docs/policies/workflow.md](../../../docs/policies/workflow.md), [docs/policies/spec-kit-workflow.md](../../../docs/policies/spec-kit-workflow.md), [docs/policies/project/workflow.md](../../../docs/policies/project/workflow.md), [specs/TECHNICAL-SPEC.md](../../../specs/TECHNICAL-SPEC.md), [specs/12-cli-install-doctor/spec.md](../../../specs/12-cli-install-doctor/spec.md) |  |

### PD-0001 basis

> Agent-provisional scope decision. The Issue snapshot names a single main outcome (recoverable setup and pin updates) with an explicit in/out boundary: in scope are staging and validating a replacement before switching, verifying cached/copied content, serializing concurrent installs, previewing pin updates and a rollback path; out of scope are automatic unreviewed version bumps, trusting changed executable inputs on the operator's behalf (#55) and new-worktree setup (#15). The four acceptance criteria form one group: each is a facet of the same install-transaction design (stage-then-switch, a lock, a preview before switching, rollback to the prior pin), so they share one plan and are reviewable and testable together, meeting the scope gate in docs/policies/spec-kit-workflow.md. It is a leaf of Epic #11, not the Epic. Its blocker #12 is delivered on this branch (specs/12-cli-install-doctor, commit c766441). Risk stays R2: per docs/policies/project/workflow.md it touches what ballast downloads/executes and the paths tools/setup installs, removes or preserves, so this pre-change decision is agent-provisional and the merge decision remains the single human approval.

### PD-0002 basis

> AC-013 allowed either refetch or refusal without saying when. Refetching rebuilds a disposable per-machine cache from the pinned upstream source and never installs or edits the damaged copy; refusing when offline loses nothing. A later change can pick a different policy without migration or data loss.

### PD-0003 basis

> The cache is per-machine and the spec has no multi-host requirement. Limiting stale-holder detection to local processes adds no persisted format and can be widened later without migration.

### PD-0004 basis

> AC-015 required a refusal but no way out. The launcher already offers `ballast discard-runs` for an unfinished agent step (tools/spec_workflow/launcher.py). Pointing to that keeps one recovery path and gives setup no new authority over run state, so it can be changed later without loss.

### PD-0005 basis

> This default was written into the spec's Assumptions during specify and is recorded here. Refusing is the conservative choice for a same-checkout race and writes nothing. Waiting on a shared cache fetch is needed for AC-010. Switching the same-checkout case to waiting later changes no stored data.

### PD-0006 basis

> This default was written into the spec's Assumptions during specify and is recorded here. Reporting incompatibility is the conservative reading. The preview is read-only and only advises the operator, so a later version can declare compatibility without any migration.

### PD-0007 basis

> Agent-provisional. spec.md states one outcome matching the Issue snapshot: a failed or interrupted setup or pin update leaves the previous installation, constitution, project policies, run state, run archives and trust baseline intact. Its four user stories map one-to-one to the Issue's four acceptance criteria (failure/interrupt preservation; serialized and idempotent setup with content verification; update preview of version, run compatibility, generated-file impact and required checks; documented and verified rollback), and each FR cites the AC IDs it satisfies. Constraints keep the Issue's non-goals: no automatic pin change and no trust recorded on the operator's behalf (FR-018, #55), no new-worktree setup (#15), tag-move detection out of scope. No [NEEDS CLARIFICATION] marker remains; the open choices are recorded as agent-provisional reversible assumptions PD-0002..PD-0006, and the requirements checklist passes. Success criteria are measurable (fault-injection, race and corruption counts). Risk stays R2 per docs/policies/project/workflow.md (what ballast executes or downloads; paths tools/setup installs, removes or preserves); the checklist flags FR-016 (run-state compatibility declaration) and FR-017 (preview running the target version's setup in a disposable directory, never trusted or put in place) for security review at plan time, per docs/policies/workflow.md. The spec does not widen scope beyond the Issue's in-scope list, so this decision is not material.

## Reviews

No review recorded yet.

## Open findings

None.

## Checks

- run-checks: not run yet
- run-checks ran in the run's worktree, so git-ignored files there were visible to them and are not part of this PR
- agent-reported: none; agent claims never satisfy run-checks

CI results appear on this PR.
