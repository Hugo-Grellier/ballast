# Plan: coordinator executions (#197)

Risk R2 (a write path next to admission and settlement state). Operator approval
relayed on #197.

## Record

`coordinate.py execution start` creates `workers/ID/` beside `tools/worker.py`'s
records, in the same shape: `result.json` (`worker`, `attempt`, `role`, `status`,
`requested` route, `head_before`, `head_after`, `tokens: "unavailable"`) and
`events.jsonl` (`created`, `task_accepted`, then the final status). It adds
`executor: "coordinator"`, `route_verified: false` and
`source: "coordinator-reported"`; `observed` stays absent because nothing
observed the route. A review also records `reviewed_head`, `verdict`
(`approved`, `changes_required`, `blocked`) and `round` (1..3). The claim history
gets `execution_started` / `execution_finished` milestones so the dashboard joins
the record through the claim, as it does for `worker_reserved`.

## CLI

```text
coordinate.py execution start  --claim C --role implement|review --executor coordinator
                               --provider P --model M --effort E
coordinate.py execution finish --claim C --worker ID --status completed|cancelled
                               [--verdict V --round N]   # review only, required when completed
```

Start requires the queue coordinator, a running queue and an active claim, like
a worker reservation. A review needs a clean committed head. Finish requires the
same coordinator but not a running queue, so a paused or cancelled queue can still
close its open records. Finishing a completed review rechecks that the head is
unchanged and clean.

## Capacity and locks

A coordinator execution takes no worker capacity, spends no worker attempt and
never creates or reads-and-removes the `.worker` lock. To keep one writer per
issue checkout, start refuses while a worker holds the lock or another
coordinator execution of the claim is open, and `admission.reserve_worker`
refuses while a coordinator execution of the claim is open. Finish only accepts a
record with `executor: coordinator`, `route_verified: false` and status
`running`, so it cannot settle a real worker or finish twice; `release` keeps
requiring the worker lock, which a coordinator execution never holds.

## Unverified marker

There is no flag that sets the route verified. Readers derive the marker, they do
not trust the field: `worker_view` and the dashboard report
`route_verified: true` only for a record without `executor` whose `source` is the
Codex thread receipt. A coordinator record edited to `route_verified: true` still
projects as unverified, and finish refuses it.

## Status and dashboard

`worker_view` adds `executor` (`worker` or `coordinator`) and `route_verified`; a
new status `running` marks an open coordinator execution (it is not `unknown`: a
coordinator record has no process to lose). Setup is zero (created and accepted
at start), running is start to finish, so `issue_view` phases count it like a
worker. The dashboard lists executor, an "unverified route" marker, source
`coordinator-reported`, verdict and round.

## Publish

`publish` keeps requiring a completed `worker.py --role review` worker, and a
coordinator review record never satisfies it (`reviewed` skips any record with an
`executor`). Coordinator decision after review round 1: changing what `publish`
accepts would need live qualification on a disposable repository, which this run
does not have. A coordinator review is referenced only from the PR body's
execution evidence or a `review`/`readiness` progress record, stated as
self-reported and unverified. Publishing a shortcut-reviewed head therefore
stays outside `publish` until a verified review exists.

## Partial failure

`finish` persists the result, the final event and the claim milestone in turn.
A retry with the same outcome completes whatever is missing (the head check is
not repeated: the outcome was already recorded); a different outcome is refused.
A failure in `start` after its record but before the claim milestone leaves an
orphan `running` record that holds nothing; `status` shows it.

## Evidence

Unit tests: lifecycle (start/finish, events, timing), refusals (malformed route,
wrong executor, duplicate open, finish twice, finish a worker record, verdict on
implement, dirty or moved review head), capacity and lock independence (both
directions), marker tamper, status and dashboard projection, publish refusing a
coordinator review, finish resumed after a failure between each persistence step.
