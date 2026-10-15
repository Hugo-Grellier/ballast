# Bounded queue qualification — 2026-10-14

Status: **representative live queue run on a fictional target**. It exercises
admission, capacity, dependency blocking, pause, idempotent publication, the
review backlog and live cancellation with real Codex sessions and GitHub. It does
not claim cross-clone ownership, a live quota pause or release readiness.

## Authorized scenario

The operator asked for this live run on public `Hugo-Grellier/ballast-v2-smoke`
(fictional content; no automatic merge or deletion). The coordinator was an
existing agent session using the helpers from this branch; no Orca or Ballast 1.x.

Fictional issues: [#3](https://github.com/Hugo-Grellier/ballast-v2-smoke/issues/3)
farewell helper, [#4](https://github.com/Hugo-Grellier/ballast-v2-smoke/issues/4)
shouted greeting, [#5](https://github.com/Hugo-Grellier/ballast-v2-smoke/issues/5)
`Blocked by: #3`, [#6](https://github.com/Hugo-Grellier/ballast-v2-smoke/issues/6)
cancellation fixture. Base: `main` at `b44a9bb`.

## Queue run (one clone)

Queue over #3, #4, #5 with `issues=1, workers=2, backlog=2, attempts=3`, 90 minutes.

| Step | Observed |
| --- | --- |
| `select` | eligible `[3]`, waiting for capacity `[4]`, blocked `#5: prerequisite #3 has no merged change` |
| Prepare #4 while #3 active | refused by the issue cap; no claim written |
| Implement #3 | fresh Codex 0.162.1 session, `gpt-6-luna`/`low` requested = observed before task input, `completed`, 78,830 total tokens |
| Coordinator checks | `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest -v`: 2 tests pass; the new test fails against the original helper; `git diff --check` clean |
| Pause, then review | review worker refused with `Queue is paused or cancelled` before any client started; no attempt spent |
| Resume, review #3 | fresh read-only session, `gpt-6-sol`/`medium`, head unchanged, `VERDICT: APPROVED` |
| `publish` twice | one draft [PR #7](https://github.com/Hugo-Grellier/ballast-v2-smoke/pull/7) at head `e7bd5a7`; the second call reused it |
| `settle pr_wait` | issue slot freed; backlog 1/2; `select` now eligible `[4]`, #5 still blocked |
| #4 end to end | same routes, checks and approval; draft [PR #8](https://github.com/Hugo-Grellier/ballast-v2-smoke/pull/8) at head `5ef90a6` |
| Prepare #5 with backlog 2/2 | refused by the human-review backlog limit, with 0 active issues and 0 workers |

Final `status`: 0 active issues, 0 workers, backlog 2, two issues awaiting human
review, no unknown workers. Per issue: one implementation and one review attempt,
rework 0, worker elapsed time and token totals, and the control history
`admitted → worker_reserved → turn_permitted → … → published → pr_wait`.

## Live cancellation (separate clones)

A worker on #6 was told to edit, then run `sleep 120`. The coordinator recorded
`control cancelled` about 17 seconds after the task was accepted.

- **First run (before the fix):** the worker sent `turn/interrupt`; the real
  client confirmed `interrupted` 88 ms later and the worker settled `cancelled`,
  releasing its lock. But the sandboxed `sleep` kept running: Codex's Linux
  sandbox runs tool commands in their own session, which is reparented away from
  the client and outlives it. Releasing the lock was therefore unproven.
- **Fix:** after the client exits, the worker settles only when no process runs
  inside the checkout (Linux `/proc` working directories), waiting at most 30
  seconds; otherwise, or where processes cannot be inspected, it stays `unknown`
  and keeps the lock. It never kills processes itself.
- **Second run (with the fix):** interrupt requested; 32 seconds later the
  worker reported `Processes still run in the checkout; outcome unknown` and kept
  its lock. The coordinator stopped the leftover sandbox session, confirmed no
  process remained in the checkout, and ran `release` with that evidence: the
  lock was removed, the worker result became `released`, and the partial edits
  stayed in the checkout. Both #6 claims were then settled `stopped`.

## Phase timing from the live records

`status` on the same records (taken while both PRs still awaited review):

| Issue | Elapsed | Implement | Review | Worker setup | Human-review wait | Coordinator |
| --- | --- | --- | --- | --- | --- | --- |
| #3 | 1,575 s | 9 s | 19 s | 3 s | 1,472 s | 73 s |
| #4 | 1,460 s | 11 s | 12 s | 1 s | 1,413 s | 22 s |

Queue: 1 s paused (the pause check), 2 PRs published, 0 merged, 0 reopened. The
cancellation queue reports #6 stopped after 98 s, 49 s of it running.

## Not exercised live

- Quota pause: cannot be triggered on demand; covered by scripted
  `usageLimitExceeded` tests, including the backend reset window.
- Lost publication response and recovery after a killed preparation: scripted only.
- No CI workflow exists on the fixture's `main`, so the smoke PRs have no CI run.

No merge, release, issue closure or deletion was performed.
