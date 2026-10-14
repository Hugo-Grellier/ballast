# Standalone foreground execution

Use this adapter when an existing agent starts one leaf issue without Orca.
The coordinator follows [the issue workflow](issue-workflow.md), owns decisions,
checks and publication, and uses two helpers from the operator-selected Ballast
2.0 source tree. The helpers do not install or activate Ballast 1.x.

## Scope and limits

This slice supports GitHub.com and the installed Codex app-server with authorized
ChatGPT subscription access. Other hosts, providers, API-key access, unsupported
models/efforts and missing configuration receipts block. No implicit paid fallback.
Use a POSIX host with Python 3.11+, Git, authenticated `gh` and the qualified
Codex CLI outside CI. Windows execution is currently blocked because this worker
requires bounded nonblocking pipe writes.

Without a [queue](#bounded-queue), run one issue and one worker at a time. Workers run in the foreground, at most
900 seconds each (300 by default), with 64 KiB task/final-message limits and a
1 MiB protocol-message limit. The coordinator permits at most three review/fix
rounds and one issue PR. A fresh session is required for each worker. Worker
nested delegation is disabled in the client and forbidden in the handoff.

This is a cooperative agent workflow under native CLI sandbox permissions, with
read access supplied by the installed client. It does not supply the v1 trusted
launcher, protect records from the operator or a malicious peer, isolate external
services, enforce policy against arbitrary alternate CLIs, or provide detached
supervision. Review local/project agent configuration before launch. Preserve the
operator's existing authority; these helpers authorize no sandbox escalation.

## Prepare

1. Read the issue and comments. Verify repository identity, actionable leaf scope,
   acceptance criteria, dependencies, relevant decisions, existing branches/PRs
   and active work. Ask consequential questions and plan only as needed. Existing
   linked work must be reconciled before creating another attempt.
2. Select the integration branch explicitly. Fetch it with native Git, then use
   the operator-selected helper source. From that Ballast source checkout, set
   its root; `PROJECT_CHECKOUT` names the already selected target repository:

   ```sh
   BALLAST_SOURCE="$(git rev-parse --show-toplevel)"
   python3 -I -S "$BALLAST_SOURCE/tools/worktree.py" \
     --repo OWNER/REPOSITORY --issue NUMBER --base main --cwd "$PROJECT_CHECKOUT"
   ```

3. Retain the returned **local-only** claim handle. The helper verifies origin and
   the current remote base, claims the issue exclusively, and creates a new issue
   branch and Git worktree. Read the local claim to locate it. Run any authorized
   project setup there before dispatch. Setup failure blocks dependent work.

Claims and execution records live under `ballast-v2/` in Git's common directory,
shared by its linked worktrees. They contain local paths and stay untracked.
This prevents duplicate dispatch within that clone. It does not coordinate other
clones or hosts. A failed setup preserves its claim and residual files. Do not
remove a claim or infer exit from age/PID to retry; inspect and reconcile first.

## Execute and observe

Select explicit model and effort from [model routing](model-routing.md). Write a
bounded local task file with issue, phase, acceptance criteria, relevant decisions,
scope, allowed checks and completion evidence. Keep publication with the coordinator.

```sh
python3 -I -S "$BALLAST_SOURCE/tools/worker.py" \
  --claim "$ISSUE_CLAIM" --task "$TASK_FILE" \
  --model CONCRETE_MODEL --effort SUPPORTED_EFFORT \
  --role implement --timeout 300
```

The same executing session must establish authorized subscription access, catalog
support and matching resolved model/effort, provider, working directory, sandbox,
no additional write roots/networking and approval policy before task input.
Implementation uses workspace write access; review uses read-only access. Both
exclude writable temporary directories. No caller conversation is supplied.

Local `workers/ID/events.jsonl` records created, route verified, task dispatched,
accepted and final milestones with timestamps. `result.json` associates attempt,
worker session, requested/observed route, client version, head and fixed failure
reason when the protocol/configuration check supplies one. `output.txt`
contains final model output for coordinator inspection; it remains private and
is never publication-ready evidence by itself. Raw protocol, reasoning, account
identity and tool streams are not retained by the helper.

A successful backend turn and client exit produce `completed`; this does not
establish task acceptance. Pre-delivery failures produce `not_started`. Uncertain
delivery, timeout, malformed completion, failed turn or unconfirmed shutdown
preserve `unknown` and the worker lock. The helper closes/reaps its client, but
makes no claim that all external effects stopped. No automatic retry, stale-lock
reclaim, detached operation or general resume is implemented in this slice.
Report the local worker reference and blocker; inspect actual liveness/effects
before replacement. A [queue](#bounded-queue) adds pause, cancel, quota and
recorded reconciliation; it still never reclaims a lock by age or PID.

## Check and review

Inspect the diff and run the project's meaningful checks in the issue worktree.
Record command, result, code revision and relevant integration base. A model's
assertion does not substitute for checks. Commit the intended diff, pause edits,
and record its clean head before review.

Start a separate worker with `--role review` and an explicit route chosen for
review difficulty. Its task names the exact head, base, issue acceptance and
review criteria. The helper checks a clean committed head before review and the
same clean head afterward. Read the review's findings and verdict. A completed
turn is not an approval. Follow [pair review](pair-review.md), repair actionable
findings within the round limit, and repeat affected checks and independent
review. Any subsequent code/base change invalidates affected evidence.

## Publish and decide readiness

Revalidate the repository, issue branch, reviewed head and integration base.
Inspect existing linked PRs again, then push using the authorized native Git
credentials and create or update **one draft PR** with `gh`. Use a body file for
multiline text. Include issue linkage, risk, acceptance evidence, check commands,
reviewed head/verdict and limitations. Public records use opaque worker/attempt
references and links; remove local paths and private model output.

Inspect GitHub's submitted head/base and required checks. Record intended workflow,
check name, execution link and revision; verify a synthetic merge check corresponds
to the reviewed head and relevant base. Missing, pending, failed, unrelated or
stale checks keep the PR draft. If authentication cannot create a workflow, report
that concrete capability gap and retain draft; do not claim CI passed. An empty
check list is not success. Mark ready only when acceptance, fresh independent
review and all intended checks are complete. Human approval is required to merge.

Record the PR URL, submitted head, review worker/verdict and workflow run in the
local claim as publication evidence; retain its preparation status separately
from PR readiness. Keep the claim and checkout while the PR awaits merge. Do not merge, release,
delete worktrees/repositories or schedule recurring work automatically.

## Bounded queue

To work several selected leaf issues, configure one finite queue in the same
clone. Queue state shares the `ballast-v2/` directory and one short local
`flock`; GitHub stays authoritative for dependencies, PRs, merges and CI. Every
helper invocation in a queue needs `BALLAST_COORDINATOR` set to the queue's
coordinator reference; workers inherit it and cannot raise a limit.

```sh
export BALLAST_COORDINATOR=COORDINATOR_REF
python3 -I -S "$BALLAST_SOURCE/tools/coordinate.py" --cwd "$PROJECT_CHECKOUT" \
  create --repo OWNER/REPOSITORY --issue 12 --issue 13 \
  --coordinator "$BALLAST_COORDINATOR" --revision INSTRUCTION_REVISION
python3 -I -S "$BALLAST_SOURCE/tools/coordinate.py" --cwd "$PROJECT_CHECKOUT" select
```

Defaults are one active issue, two workers (review and helpers included), two
PRs awaiting humans, three attempts per worker role and one hour; override each
with `--issues`, `--workers`, `--backlog`, `--attempts` and `--seconds`. A queue
cannot be recreated to reset its budget.

- `select` reports eligible issues within the remaining budgets, issues waiting
  for capacity, existing claims, and blocked issues with their reasons: native
  `blockedBy` or `Blocked by:` prerequisites that are unmerged, cross-repository
  or cyclic. A closed prerequisite counts only with a merged closing PR. `select`
  still reports stacked work as blocked; stacking stays an explicit coordinator
  exception, prepared directly, with its merge order recorded in the PRs.
- `worktree.py` admits a claim and `worker.py` reserves a worker under the same
  lock. Claims and worker locks from before the queue, or with unknown outcome,
  consume capacity. A fresh turn needs a permit that rechecks controls and spends
  one attempt; qualification failures before it spend none. A claim bound to a
  queue fails closed if that queue's policy is missing or replaced.
- `control paused|running|cancelled --reason TEXT` records a control. Pause
  blocks new admissions and turns. Cancel makes live workers send
  `turn/interrupt` and wait at most 30 seconds for terminal evidence; otherwise
  the worker stays `unknown` with its lock. Sandboxed tool commands can outlive
  the client, so any worker settles only once no process runs inside its
  checkout (Linux `/proc`; elsewhere the outcome stays `unknown`). `running` after a pause also clears
  a quota pause. A cancelled queue is not resumed by a control.
- A structured `usageLimitExceeded`/`rateLimitExceeded` turn error settles the
  worker as `quota` and pauses dispatch until the backend-reported window reset,
  or until an explicit `running` control when no window was reported. Nothing
  retries, buys capacity or skips review.
- `publish --claim CLAIM --title TEXT --body-file FILE` requires the pushed
  reviewed head, reuses the one matching PR on the claim branch, creates a draft
  only when none exists, and re-queries after an uncertain response. Several,
  foreign or stale PRs block.
- `settle --claim CLAIM ACTIVITY --evidence TEXT` records positive coordinator
  evidence. Allowed moves: `active` to `pr_wait`, `stopped` or `unknown`;
  `unknown` to `stopped` or `active`; `pr_wait` to `active`, `stopped` or
  `merged` (only when GitHub reports the PR merged); `stopped` to `active`.
  Moving into `active` rechecks controls and the issue cap. Any recorded PR
  consumes backlog until merged. Another coordinator takes over an active issue
  only after a recorded `stopped`.
- `release --claim CLAIM --worker ID --evidence TEXT` frees an `unknown` worker
  lock after the coordinator has positive stop evidence (for example the backend
  thread's terminal state) and marks that worker's result `released`. Nothing
  releases a lock by age or PID. Coordinator identity and evidence are trusted
  references, not authentication.
- `recover --claim CLAIM --evidence TEXT` adopts an existing attempt after an
  interrupted preparation or restart, or binds a pre-queue claim to the queue.
  If preparation died before its checkout existed, it creates that checkout at
  the recorded branch and base. It verifies checkout, branch and base, refuses
  while a worker lock remains, and rechecks controls and the issue cap. It never
  deletes or replaces a checkout.
- `status` projects the queue, used capacity and per-issue control history,
  derived only from recorded timestamps:
  - per worker: role, outcome, setup (until the task was accepted) and running
    seconds, token totals or `unavailable`; a directory without a result is
    `unrecorded`;
  - per issue: elapsed time split into `implement`, `review`, `worker_setup`,
    `human_review_wait` (time in `pr_wait`) and `coordinator` (the rest: checks,
    decisions, publication); rework, review rounds, `reopened` (a `pr_wait` sent
    back to `active`, a regression signal) and the evidence trail of every
    settlement;
  - per queue: paused/cancelled/quota time (a known quota window ends on its
    own) and throughput: hours, PRs published, merged and published per hour.

  Compare runs by these fields. `status` never deletes checkouts, merges or
  schedules work.
