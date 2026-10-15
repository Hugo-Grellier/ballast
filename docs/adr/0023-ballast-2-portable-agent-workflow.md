# ADR-0023: Ballast 2.0 uses a portable agent workflow with explicit execution evidence

- Status: accepted by [ADR-0024](0024-ballast-2-migration.md) when its PR merges ([#180](https://github.com/Hugo-Grellier/ballast/issues/180))
- Issues: #174 (2.0), #175 (foundation)
- Basis: operator's 2.0 design conversation, 2026-10-14

## Context

The operator found Ballast 1.x too expensive to use and evolve. The desired result
is high throughput from GitHub issues to verified, independently reviewed PRs,
primarily launched from an existing agent conversation. V1's full Spec Kit/run
lifecycle is not the desired 2.0 execution path. The operator explicitly instructed
that v1 must not be used to build 2.0.

## Proposed decision

- Ship a short project entry point and modular Markdown instructions: understand,
  decompose, clarify/plan as needed, implement, verify, review, publish. GitHub
  issues hold scope/progress and PRs hold acceptance/review evidence. Consequential
  architecture decisions remain ADRs. Routine tasks need no parallel spec tree.
- Each implementing leaf owns an isolated Git worktree. The development coordinator
  manages bounded worker ownership outside CI, with standalone execution required
  and Orca optional behind the same contract. CI performs deterministic verification.
- Resolve model and effort explicitly for every worker and attempt. Capability
  validation and resolved backend evidence precede task input. Missing observations,
  mismatches or unsupported settings block affected execution. Record what the
  backend proves; never claim provider-internal attestation.
- Retain phase/attempt history, requirements evidence, human decisions, failures,
  review rounds, waiting and instruction revisions. Use existing backend lifecycle
  facilities where available and a minimal local record for standalone recovery.
- Bound concurrent workers, retries, escalation, quota waits and ready-PR backlog.
  Respect native permissions. Preserve human merge/release approval. New paid
  services, recurring automation and destructive actions require authorization.

## V1 boundaries and migration

This foundation is additive and does not activate v2 or weaken v1 invariants.
Before switching active behavior, a migration feature must reconcile the
constitution and accepted architecture, including ADR-0001/0002 (installation and
version manifest), ADR-0003 (trusted launcher GitHub authority), ADR-0004/0009/0010
(run modes and lifecycle), and ADR-0011/0015/0021 (worktree trust and operator-session
rules). ADR-0021 is currently duplicated; reference its filename/title explicitly
until #170 and the remaining numbering collision are resolved.

The proposed v2 execution path uses the caller's authorized native tools and
permissions; it does not promise v1's trusted external launcher or tamper checks.
The migration must name those removed guarantees and the resulting operational
boundaries rather than relabeling them as preserved. Retain v1 tags and historical
specs/decisions; re-triage unfinished work, including #149 and its related issues.
No existing issue is closed and no existing ADR is superseded by this proposal.

## First executable proof

The foundation adds a standalone Codex app-server qualification probe. It starts
no model turn and returns only sanitized configuration evidence. Subsequent work
must separately prove task execution, worktree ownership, recovery, queue limits,
independent review and PR readiness before claiming a functional 2.0 release.

## Alternatives

Continuing the v1 runner for this migration conflicts with the operator's explicit
instruction. Requiring Orca conflicts with portability. A new generic workflow
engine would introduce maintenance before a vertical slice demonstrates the need.
