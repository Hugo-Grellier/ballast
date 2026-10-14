# Portable agent execution

## Entry and backend

The normal entry point is an existing agent conversation: `Start #N` or `Work
the queue, up to N issues concurrently`. The caller coordinates the authorized
work through an execution backend outside CI. Routine dispatch needs no manual
terminal commands from the human; ask only for missing decisions or permissions.

Standalone execution is a required path: Git, repository-host tooling, and
installed agent CLIs or native delegation tools. Orca is optional. With Orca,
use [the Orca adapter](orca-execution.md) for backend-specific operations. Choose
the backend explicitly at entry and retain ownership through completion. An
interrupted Orca attempt cannot silently become a standalone duplicate.

Every backend must implement the same observable operations: discover capabilities,
claim/recover an issue, prepare/reuse its worktree, launch with a verified route,
receive questions/results, observe status, stop safely, and release settled work.
Follow [model routing](model-routing.md) for model/effort and the issue workflow
for acceptance. Extra UI features never substitute for these contracts.

## Queue and ownership

- Claim each eligible leaf issue once with an authoritative active attempt.
  Inspect existing worktrees, branches, PRs, and attempts before dispatch.
- Resolve concurrency, elapsed-time, retry/escalation, and ready-PR backlog limits
  from the request or configured project defaults. Ask once for missing queue
  limits. Count helpers and reviewers in the worker budget; nested work cannot
  reset it. Stop pulling work when a limit is reached.
- Dispatch in priority/dependency order. A pause stops new dispatches; cancellation
  requests stopping active work. Neither operation authorizes file deletion.
- Recover existing attempts after a coordinator restart. Unknown liveness consumes
  capacity until reconciled and never authorizes a duplicate editor.
- A queue request is one-time work. Recurring schedules require explicit human
  authorization naming their purpose and limits. Quota exhaustion pauses affected
  work; record known retry windows. Never purchase capacity or skip required review.

## Worktree contract

Each implementing leaf issue gets an isolated Git worktree and issue branch from
the configured integration base. Reuse it on resume. Preserve unrelated user edits;
verify the assigned repository, checkout, and branch before writing. Parent/child
task relationships do not imply stacked Git branches. Use stacking only when
explicitly chosen and record its merge order.

Use one implementation writer per checkout. Review a recorded head while edits
are paused, or use a separate review checkout. Serialize mutating checks against
the same checkout. Worktrees do not isolate ports, databases, external effects,
or shared build outputs; allocate resources separately or serialize affected work.
Record setup results and gate dependent work on setup completion. Refresh branches
and affected checks/review after dependency merges or integration-base changes.

Keep issue, branch, PR, checkout identity, attempt, and worker session associated.
Store local paths and execution metadata in ignored local state; public issue/PR
records use opaque attempt references, branch links, and evidence. Retain the
checkout while its PR awaits merge. Destructive cleanup needs human authorization
and checks for dirty files, unpublished commits, and live workers.

## Standalone backend

Use Git's native worktree operations, repository-host tooling, and explicit agent
launch configuration. Read the installed tools' help rather than assuming flags.
Launch a fresh session with a bounded handoff and explicit working directory,
model, effort, and permission limits. Keep the caller as coordinator; use a
separate session for independent review. Unsupported routing blocks the affected
task under the routing contract rather than requiring Orca.

Keep a small durable execution record shared across this repository's worktrees:
issue claim, attempt ID, checkout/branch, coordinator and worker identity, verified
route, timestamps, status, and evidence/result references. Use exclusive claim
updates so competing coordinators cannot dispatch the same issue. A stale
timestamp or reused process ID alone is not proof of exit or ownership.

Native delegation may supply lifecycle records. For CLI subprocesses, capture
startup/configuration receipts, status, exit result, and completion output. A
reliable detached process owner is needed if workers outlive the launching agent
turn; otherwise stop at a recoverable checkpoint and report that limitation.
Bind observations to the correct process/session; expose unknown state honestly.
Use a small local adapter only for capabilities the chosen tools do not provide.
Do not require a daemon, server, paid service, or dashboard for standalone use.

## Lifecycle and acceptance

Distinguish created, ready, started, settled, and PR-ready. Input acceptance or
heartbeat does not prove success. Verify worker results against acceptance checks
and independent review. Inspect partial launch effects before retrying; replay
requests safely when supported. Timeout or lost contact means unknown until
positive evidence establishes exit. Record a safe stop before replacement.

Project milestones into issue progress and preserve history across sessions.
Prove the same acceptance cases on standalone and Orca paths: agent-started work,
correct worktree/base, two independent issues, duplicate-claim prevention, verified
routing, setup failure, interrupted launch, restart/resume, dependency waiting,
stable-head review, cancellation, and honest PR readiness. Neither backend is
implemented or validated by adopting these instructions alone.
