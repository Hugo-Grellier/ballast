# Standalone foreground execution

Use this adapter when an existing agent starts one leaf issue without Orca.
The coordinator follows [the issue workflow](issue-workflow.md), owns decisions,
checks and publication, and uses two helpers from the operator-selected Ballast
checkout.

## Scope and limits

This slice supports GitHub.com and the installed Codex app-server with authorized
ChatGPT subscription access. Other hosts, providers, API-key access, unsupported
models/efforts and missing configuration receipts block. No implicit paid fallback.
Use a POSIX host with Python 3.11+, Git, authenticated `gh` and the qualified
Codex CLI outside CI. `worker.py` runs only on Linux: it binds its client's
lifetime with the Linux parent-death signal and reads `/proc` to settle.
Elsewhere it refuses before starting a client (`not_started`, reservation
released). Windows execution is also blocked because this worker requires
bounded nonblocking pipe writes.

Without a [queue](#bounded-queue), run one issue and one worker at a time. Each
worker has a `--timeout` of at most 900 seconds (300 by default); settling after
it can take about 190 seconds more (see [execute and observe](#execute-and-observe)
for running it as a background command). Task and final messages are limited to
64 KiB, protocol messages to 1 MiB. The coordinator enforces the [round limit](pair-review.md#round-limit)
and permits one issue PR. A fresh session is required for each worker. Worker
nested delegation is disabled in the client and forbidden in the handoff.

This is a cooperative agent workflow under native CLI sandbox permissions, with
read access supplied by the installed client. It does not supply a trusted
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

The origin must name `github.com` itself, as `https://github.com/OWNER/REPOSITORY`,
`ssh://git@github.com/OWNER/REPOSITORY` or `git@github.com:OWNER/REPOSITORY`
(each with an optional `.git` and trailing `/`). Credentials in the URL, other
hosts and SSH host aliases (`git@github-work:...`) are refused. To push through
an alias, keep the origin canonical and rewrite only the push URL. The
`pushInsteadOf` base must match the form of the origin; a base that does not
match rewrites nothing:

```sh
# origin is https://github.com/OWNER/REPOSITORY
git config url."git@ALIAS:".pushInsteadOf "https://github.com/"
# origin is git@github.com:OWNER/REPOSITORY
git config url."git@ALIAS:".pushInsteadOf "git@github.com:"
# origin is ssh://git@github.com/OWNER/REPOSITORY
git config url."git@ALIAS:".pushInsteadOf "ssh://git@github.com/"
```

Observed with Git 2.53: `git remote get-url origin` still returns the canonical
URL and `git remote get-url --push origin` returns the alias form. Do not use
`url.<base>.insteadOf` for this: it rewrites the URL that `git remote get-url
origin` reports, so the helper refuses the alias.

Fetches stay on the canonical URL. The operator needs working credentials for
that account on the canonical transport (an HTTPS credential, or the default SSH
key); otherwise fetch fails or authenticates as another account.

Claims and execution records live under `ballast-v2/` in Git's common directory,
shared by its linked worktrees. They contain local paths and stay untracked.
This prevents duplicate dispatch within that clone. It does not coordinate other
clones or hosts. A failed setup preserves its claim and residual files. Do not
remove a claim or infer exit from age/PID to retry; inspect and reconcile first.
A settled attempt makes room for a new one only through `coordinate.py retire`
(below).

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

At `--timeout` the worker interrupts its turn rather than abandoning it, so it
can run up to about 190 seconds longer: at most 30 seconds for the interrupted
turn's terminal evidence, then up to 150 seconds for the checkout to go quiet
(30 seconds, plus 120 for a sandboxed tool command that outlives the interrupt)
and a few seconds for client shutdown. An agent harness may stop foreground commands
sooner (Claude Code's Bash tool defaults to 120 seconds, at most 600). Run the
worker as a background command of the harness and wait for it to exit, or choose
a `--timeout` that leaves that margin below the harness limit. A SIGKILL leaves
the worker `unknown` with its lock held.

The worker starts the Codex client in its own session. SIGTERM/SIGINT sent to
the worker's PID or to its process group (Ctrl-C in its terminal, `kill` on the
group) reaches only the worker, which settles through the interrupt path. A
signal that reaches the client directly still ends the worker `unknown` with its
lock held: one sent to the client's PID or session, or a recursive tree kill
that enumerates the worker's descendants and signals each PID. Stop a worker by
signalling its PID or its process group. The worker binds the client's lifetime
to its own through the Linux parent-death signal: if the worker dies first, even
by SIGKILL, the kernel SIGKILLs the client. Commands the client started in their
own sessions can still outlive it; nothing settles that worker, which stays
`unknown` with its lock held until an operator inspects the checkout.

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

Coordinator processes (shells, editors, the dashboard, queue commands) must not
run with their working directory inside an issue checkout while a worker is
active: settlement waits until nothing runs there, and it cannot tell a
coordinator process from a worker's. The worker, dashboard and queue commands
refuse to start from inside one. If processes remain after the turn, the block
reason names each by PID and command name (never arguments); the worker stays
`unknown` with its lock held, but a turn the backend confirmed is recorded as
`turn: completed` in `result.json` and its `output.txt` is kept.

A successful backend turn and client exit produce `completed`; this does not
establish task acceptance. Pre-delivery failures produce `not_started`, as does
SIGTERM or SIGINT before the task is dispatched. After dispatch, the deadline and
SIGTERM/SIGINT take the queue cancellation path: the worker sends
`turn/interrupt` and waits at most 30 seconds for the matching terminal turn.
A backend-confirmed interrupted turn in a quiet checkout settles as `timeout`
(deadline) or `cancelled` (signal) and releases the worker lock. A tool command
can outlive the interrupt, so after one the worker watches the checkout up to
150 seconds (a completed turn: 30) and settles once two consecutive scans find
it quiet, recording `survivors_exited` with the seconds it waited in
`events.jsonl`. A process still running at that bound keeps the worker `unknown`
with its lock; nothing is inferred from a process's age or PID. Uncertain
delivery, a rejected interrupt or missing terminal evidence, malformed
completion, failed turn, survivors or unconfirmed shutdown preserve `unknown`
and the worker lock. The helper closes/reaps its client, but
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
review criteria, and the coordinator's check evidence for that head: each
command, its result and the revision it ran on. The review worker stays
read-only with no writable temporary directory, so it cannot run tests that
create files (Ballast's own do); it may run read-only checks and reports any
check it could not run under `Verification gaps`. The helper checks a clean
committed head before review and the same clean head afterward.
Read the review's findings and verdict. A completed turn is not an approval.
Follow [pair review](pair-review.md), repair actionable findings within the
round limit, and repeat affected checks and independent
review. Any subsequent code/base change invalidates affected evidence.

## Publish and decide readiness

Revalidate the repository, issue branch, reviewed head and integration base.
Inspect existing linked PRs again, then push using the authorized native Git
credentials and create or update **one draft PR** with `gh`. Use a body file for
multiline text and run the PR body check on it first, as in the
[issue workflow](issue-workflow.md#6-publish-and-finish); a failure, such as an R2
body without its approval link, stops publication. Include issue linkage, risk,
acceptance evidence, check commands, reviewed head/verdict and limitations. Public records use opaque worker/attempt
references and links; remove local paths and private model output.

Inspect GitHub's submitted head/base and required checks. Record intended workflow,
check name, execution link and revision; verify a synthetic merge check corresponds
to the reviewed head and relevant base. Missing, pending, failed, unrelated or
stale checks keep the PR draft. If authentication cannot create a workflow, report
that concrete capability gap and retain draft; do not claim CI passed. An empty
check list is not success. Mark ready only when acceptance, fresh independent
review and all intended checks are complete. Human approval is required to merge, except an R0 PR that
`tools/merge_check.py` accepts ([ADR-0026](adr/0026-r0-merge-on-reviewed-green-head.md)).

Record the PR URL, submitted head, review worker/verdict and workflow run in the
local claim as publication evidence; retain its preparation status separately
from PR readiness. Keep the claim and checkout while the PR awaits merge. Do not merge (outside that R0 rule), release,
delete worktrees/repositories or schedule recurring work automatically.

## Bounded queue

To work several selected leaf issues, configure one finite queue in the same
clone. Queue state shares the `ballast-v2/` directory and one short local
`flock`; GitHub stays authoritative for dependencies, PRs, merges and CI. Every
helper invocation in a queue needs `BALLAST_COORDINATOR` set to the queue's
coordinator reference; `control`, `settle`, `release`, `publish`, `recover` and `retarget`
refuse otherwise, and an unset or empty value is never recorded. Workers inherit
it and cannot raise a limit.

```sh
export BALLAST_COORDINATOR=COORDINATOR_REF
python3 -I -S "$BALLAST_SOURCE/tools/coordinate.py" --cwd "$PROJECT_CHECKOUT" \
  create --repo OWNER/REPOSITORY --issue 12 --issue 13 \
  --coordinator "$BALLAST_COORDINATOR" --revision INSTRUCTION_REVISION
python3 -I -S "$BALLAST_SOURCE/tools/coordinate.py" --cwd "$PROJECT_CHECKOUT" select
```

Defaults are one active issue, two workers (review and helpers included), two
PRs awaiting humans, three attempts per worker role and one hour; override each
with `--issues`, `--workers`, `--backlog`, `--attempts` and `--seconds`.
`--review-fallback PROVIDER:MODEL --review-fallback-approval URL` records the
[quota review fallback](#quota-review-fallback) policy; omit it unless the
operator approved that route. A queue cannot be recreated to reset its budget. Once it is finished, `close --reason
TEXT` archives it as `queue-ID.json` (still shown by `status` under `closed`) so the
clone can create the next queue. Close refuses a queue that is neither cancelled
nor past its deadline, any of its claims still `active`, `unknown` or `pr_wait`,
and any worker lock; settle, release or reconcile them first. When the queue's
coordinator session has ended, another coordinator (its own `BALLAST_COORDINATOR`,
never the ended one's) may close it under exactly those conditions; the archive
records `closed_by` and `previous_coordinator`. Age or PID never decides it: a
queue with budget left still requires its own coordinator. While a finished
queue stays open, `worktree.py` and `select` name it, its coordinator and the
`close` command instead of claiming work.

- `select` reports eligible issues within the remaining budgets, issues waiting
  for capacity, existing claims, and blocked issues with their reasons: native
  `blockedBy` or `Blocked by:` prerequisites that are unmerged, cross-repository
  or cyclic. A closed prerequisite counts only with a merged closing PR. A
  `Blocked by:` prerequisite still blocks; stacking stays an explicit
  coordinator choice. `select --planned FILE` also reports overlap: `FILE` is a
  JSON object mapping queue issue numbers to planned entries, `"path"` or
  `"path::function"` (no code analysis). Entries overlap when they name the
  same file and either names no function or both name the same one. Each pair
  of planned issues gets its shared entries and a suggestion: `parallel`
  (nothing shared), `stack` (shared, both eligible now) or `serialize` (shared,
  one cannot start now). A malformed file or an issue outside the queue refuses.
- `worktree.py --parent P --base BRANCH` prepares a stacked claim on the
  parent claim's pushed branch (`BRANCH` must be that claim's branch, pushed and
  fetched like any base). The parent claim must exist in this clone, share
  repository and coordinator, not be `merged` or `stopped`, and have no other
  stacked child. The claim records `parent` (issue and attempt) and
  `stack_position` (root 1).
- `worktree.py` admits a claim and `worker.py` reserves a worker under the same
  lock. Claims and worker locks from before the queue, or with unknown outcome,
  consume capacity. A fresh turn needs a permit that rechecks controls and spends
  one attempt; qualification failures before it spend none. The attempt stays
  spent when the worker settles `completed`, `timeout`, `quota` or `unknown`
  (a failed turn or lost evidence after dispatch is `unknown`). It is refunded,
  once, with an `attempt_refunded` milestone naming the worker, only when the
  worker settles `cancelled`: a backend-confirmed interrupt caused by a queue
  cancel or SIGTERM/SIGINT. A claim bound to a
  queue fails closed if that queue's policy is missing or replaced.
- `control paused|running|cancelled --reason TEXT` records a control. Pause
  blocks new admissions and turns. Cancel makes live workers send
  `turn/interrupt` and wait at most 30 seconds for terminal evidence, then up to
  150 seconds for the checkout to go quiet; otherwise the worker stays `unknown`
  with its lock. Sandboxed tool commands can outlive
  the client, so any worker settles only once no process runs inside its
  checkout in two consecutive scans (Linux `/proc`; the worker refuses to start
  elsewhere). A same-user process started after the worker whose working
  directory cannot be read counts as still running. A process that forks
  between scans can still escape detection; a per-worker cgroup would close
  that gap. `running` after a pause also clears
  a quota pause. A cancelled queue is not resumed by a control.
- A structured `usageLimitExceeded`/`rateLimitExceeded` turn error settles the
  worker as `quota` and pauses dispatch until the backend-reported window reset,
  or until an explicit `running` control when no window was reported. Nothing
  retries, buys capacity or skips review. Under the queue's operator policy, a
  coordinator review may continue on the named
  [fallback route](#quota-review-fallback) while the pause blocks dispatch.
- `publish --claim CLAIM --title TEXT --body-file FILE` first requires a
  `--role review` worker of the claim's attempt whose recorded status is
  `completed` and whose recorded head before and after the turn both equal the
  checkout head; a review of another head or attempt, or a `cancelled`,
  `quota`, `unknown` or `released` review, blocks before any GitHub call. It
  does not read the verdict: a completed review is not an approval, and the
  coordinator still reads the findings before publishing. A coordinator
  execution's review (below) never satisfies it, except a
  [quota review fallback](#quota-review-fallback) under the queue's operator
  policy. It then requires that
  head pushed, reuses the one matching PR on the claim branch, creates a draft
  only when none exists, and re-queries after an uncertain response. Several,
  foreign or stale PRs block. A stacked claim targets its parent branch;
  `publish` refuses when its parent claim is missing or replaced, when GitHub
  reports the parent PR merged (retarget first), or when the parent's pushed
  head is not in the child: fetch first when that head (or any commit it
  compares) is missing from the local object store, rebase first when the
  parent's pushed branch still contains the child's recorded base revision,
  push the parent first when a retarget restacked it locally, and otherwise a
  fixed refusal (below): the parent's pushed branch was rewritten. For any
  claim in a stack, the PR body gets a `## Stack` section with the merge order, root first, and re-publishing
  an existing PR rewrites its body with `gh pr edit` so each PR carries the
  current order.
- `retarget --claim CLAIM --evidence TEXT`, after the parent merges: requires
  GitHub to report the parent's recorded PR merged, the parent's base pushed and
  fetched, the parent's merged head in the child, and no worker lock or open
  coordinator execution on the child or any later stack member. It rebases the
  child `--onto` the base from the parent's merged head (squash merges
  included), then restacks each later member from its parent's old head onto
  the parent's new head and records that head as the member's `base_sha`; a
  conflict anywhere aborts, restores every checkout and changes no record. It
  records the new base, drops `parent`, moves later members up one position, and
  records `retargeted` (and `restacked` on later members) milestones with both
  heads. An existing child PR is marked `retarget_pending` until GitHub reports
  it on the new base: retarget reads the PR's base and edits it only when it
  differs, so after a failed or uncertain edit, run `retarget` again; it only
  reconciles the PR. A parent merged head missing from the local object store
  refuses with "fetch the parent's head first". It does not push. The new heads
  have no review or check
  evidence: push them, run fresh reviews, then `publish` again; CI runs on the
  push.
- Never rewrite a stacked parent's pushed branch (amend, rebase onto a moved
  base, force-push) while it has a child: rebasing the child onto it would drop
  the child's recorded base revision and leave a claim nothing validates again.
  `publish` and `retarget` refuse the child with a fixed reason instead of
  advising a rebase. If it happens anyway, `settle` the child `stopped`, close
  its PR, `retire` its claim, and prepare a new child attempt on the parent's
  current head. The helpers rewrite a parent only inside
  `retarget`, which restacks every later member and records its new base
  revision in the same step.
- `settle --claim CLAIM ACTIVITY --evidence TEXT` records positive coordinator
  evidence. Allowed moves: `active` to `pr_wait`, `stopped` or `unknown`;
  `unknown` to `stopped` or `active`; `pr_wait` to `active`, `stopped` or
  `merged` (only when GitHub reports the PR merged); `stopped` to `active`.
  Moving into `active` rechecks controls and the issue cap. Any recorded PR
  consumes backlog until merged. A claim left `active` or `unknown` under
  another coordinator reference (a record written before queue mutations
  required the queue's coordinator) can only be settled `stopped`, by the
  queue's coordinator, while no `.worker` lock exists for it; the history entry
  records the previous owner. Any other claim passes to the queue's coordinator
  on its next settle.
- `retire --claim CLAIM --evidence TEXT` moves a `stopped` or `merged` claim
  aside as `retired-issue-N-ATTEMPT.json` with a `retired` milestone, so
  `worktree.py` can prepare the issue again and `--parent` no longer counts it
  as the parent's child. It refuses any other activity, a `.worker` lock, an
  open coordinator execution, a live stacked child of the claim, and a stopped
  claim whose recorded PR GitHub does not report closed (a recorded PR
  consumes backlog until merged; a closed one no longer awaits review). A new
  attempt of the same issue in the same queue keeps the retired attempts' spent
  worker attempts. Like `close`, it checks the current queue, not the claim's
  own: with a queue only its coordinator retires, and claims of a closed queue
  can be retired. Nothing is deleted: the checkout and branch stay, `status`
  lists retired records under `retired` with their history and keeps counting
  their published and merged PRs, and the dashboard shows a retired attempt's
  last activity until a new attempt of the issue replaces it.
- `release --claim CLAIM --worker ID --evidence TEXT` frees an `unknown` worker
  lock after the coordinator has positive stop evidence (for example the backend
  thread's terminal state) and marks that worker's result `released`. Nothing
  releases a lock by age or PID. Coordinator identity and evidence are trusted
  references, not authentication.
- `execution start|finish` records work the coordinator does itself instead of
  dispatching a worker (see [Coordinator executions](#coordinator-executions)).
- `recover --claim CLAIM --evidence TEXT` adopts an existing attempt after an
  interrupted preparation or restart, or binds a pre-queue claim to the queue.
  If preparation died before its checkout existed, it creates that checkout at
  the recorded branch and base. It verifies checkout, branch and base, refuses
  while a worker lock remains, and rechecks controls and the issue cap. It never
  deletes or replaces a checkout.
- `status` projects the queue, used capacity and per-issue control history,
  derived only from recorded timestamps:
  - per worker: role, outcome, `executor` (`worker` or `coordinator`),
    `route_verified`, setup (until the task was accepted) and running seconds,
    token totals or `unavailable`, and a review's verdict and round when
    recorded; a directory without a result is `unrecorded`; a worker still
    running or `unknown`, or an open coordinator execution (`running`), counts
    up to now;
  - per issue: elapsed time split into `implement`, `review`, `worker_setup`,
    `human_review_wait` (time in `pr_wait`) and `coordinator` (the rest: checks,
    decisions, publication); rework, review rounds, `reopened` (a `pr_wait` sent
    back to `active`, a regression signal) and the evidence trail of every
    settlement;
  - per queue: paused/cancelled/quota time (a known quota window ends on its
    own) and throughput: hours, PRs published, merged and published per hour.

  Compare runs by these fields. `status` never deletes checkouts, merges or
  schedules work.

### Coordinator executions

A coordinator may implement or review an issue itself, or through its own
subagents, instead of dispatching `worker.py`. Record that shortcut so it stays
observable:

```sh
python3 -I -S "$BALLAST_SOURCE/tools/coordinate.py" --cwd "$PROJECT_CHECKOUT" \
  execution start --claim CLAIM --executor coordinator --role implement|review \
  --provider PROVIDER --model MODEL --effort EFFORT
python3 -I -S "$BALLAST_SOURCE/tools/coordinate.py" --cwd "$PROJECT_CHECKOUT" \
  execution finish --claim CLAIM --worker ID --status completed|cancelled \
  [--verdict approved|changes_required|blocked --round 1..3]
```

`start` writes `workers/ID/result.json` and `events.jsonl` in the worker record
shape with `executor: coordinator`, `route_verified: false`, `source:
coordinator-reported` and status `running`, and adds `execution_started` to the
claim history. It requires the queue's coordinator, a running queue and an
active claim, as a worker reservation does; a review also needs a clean
committed head. `finish` sets the final status and head, and a completed review
must carry a verdict and round and an unchanged clean head. Only a completed
review takes them.

- The route is self-reported, never verified. No option sets it verified;
  `status` and the dashboard derive `route_verified` from `worker.py`'s thread
  receipt, so an edited record still shows as unverified, and `finish` refuses
  it.
- An execution takes no worker capacity, spends no attempt and holds no
  `.worker` lock. One writer per checkout still holds: `start` refuses while a
  worker lock or another open execution exists, and a worker reservation refuses
  while an execution is open. `finish` accepts only an open coordinator record,
  so it never settles a worker, and `release` never applies to one.
- Setup is zero (the work starts when recorded); running time counts in the
  issue's `implement` and `review` phases and review rounds, as for workers.
- A coordinator review never satisfies `publish`, except under the
  [quota review fallback](#quota-review-fallback) below. Reference it from the
  PR's execution evidence or a `review`/`readiness` progress record, as
  self-reported and unverified.
- If `finish` fails partway, rerun it with the same outcome: it completes the
  missing steps without rechecking the head. A different outcome is refused.

### Quota review fallback

When the worker backend's quota is exhausted, independent review may continue
as a coordinator execution on another provider, only under an explicit operator
policy recorded in the queue configuration:
`create ... --review-fallback PROVIDER:MODEL --review-fallback-approval URL`.
`URL` is the operator's approval of that route, a GitHub issue or issue comment
link on the queue's repository; a policy without it is refused. The policy
cannot be added to an existing queue, and the worker's own provider (`openai`)
is refused. Without it nothing changes.

The coordinator writes this policy, and only the approval link's shape is
checked: the reference is not attested locally. Like the coordinator identity,
it is a trusted local record, so the guarantee holds only for an approval the
operator actually gave. Hand-editing `queue.json` is outside the guarantee.

- It applies only after a recorded `quota` outcome: while the queue is running
  and dispatch is blocked by a quota pause alone, `execution start --role
  review` on exactly the policy's provider and model is accepted and marked
  `fallback: quota`. A pause, cancel, deadline, another route or an
  implementation execution is still refused.
- The quota pause stays in place: worker reservations and turns keep refusing,
  nothing retries the worker backend or buys capacity, and only an explicit
  `running` control or the reported reset window ends it.
- `publish` accepts, in place of a worker review, a completed fallback execution
  of the claim's attempt whose recorded head before, after and reviewed all equal
  the checkout head, on the policy's route, in a queue whose history records the
  quota pause. Its verdict is not read. A review of another head or attempt,
  without the policy, without the quota outcome, or started outside the quota
  pause (for example after an operator `running` resume) is refused before any
  GitHub call. For independence, it is also refused when a recorded `implement`
  execution of the same attempt used the same provider and model.
- The PR body gets a `## Review route` section naming the fallback provider,
  model and requested effort, quoting the approval link, and stating that the
  route is unverified (the model is coordinator-reported and the effort is not
  verifiable), that the review's occurrence and independence are
  coordinator-attested, and that the approval reference is not attested
  locally. `publish`
  records the PR in the claim as usual, so `settle merged` later sees it.

## Qualification

`tools/qualify.py` drives the coordinator path above end to end, running every
shipped helper as a subprocess: `coordinate create` and `select`, `worktree.py`,
an `implement` worker, a coordinator commit, a `review` worker on that head, a
push, `coordinate publish` and `settle pr_wait`. The run fails on any helper
failure, a worker that does not end `completed`, an issue the queue does not
select, an implementation that commits anything or changes anything but adding
a regular `QUALIFICATION.md` with the single line `qualified`, or a review whose last line is not
`Verdict: approve`. The review output is read for that line only and never
enters the evidence. It prints JSON evidence without local paths: Ballast revision, base and
head, each worker's requested and observed route, sandbox and heads, the PR and
the final activity. Run it from outside any issue checkout. Once a worker has
run, its Git calls in the checkout use the claim's pinned Git directory with
hooks and the filesystem monitor off, never the worker-writable `.git` gitfile.

**Local mode** needs no network, model, account, credentials or approval, so any
agent may run it:

```sh
python3 -I -S "$BALLAST_SOURCE/tools/qualify.py" local
```

It builds a throwaway clone in a temporary directory whose origin is the
canonical `https://github.com/example/ballast-qualification-local`, with pushes
rewritten to a local bare repository. The `gh` and `codex` found on `PATH` are
fakes served by the same script: the fake app-server reports the requested
route and sandbox and completes one turn, the implementation turn writing
`QUALIFICATION.md`; the fake `gh` answers issue, branch, pull request and
GraphQL reads from the local repository and records created PRs. Global and
system Git configuration are ignored, and the directory is removed on exit.
The gate runs it (`tests/test_qualify.py`). It cannot show that the real Codex
client, GitHub or the operator's credentials behave as the fakes do.

**Live mode** runs the same path with the installed Codex and the real `gh`:

```sh
python3 -I -S "$BALLAST_SOURCE/tools/qualify.py" live \
  --repo OWNER/ballast-qualification-NAME --confirm-disposable \
  --model CONCRETE_MODEL --effort SUPPORTED_EFFORT --ledger FILE
```

It refuses without `--confirm-disposable` or when the repository name does not
start with `ballast-qualification-`. It reuses an existing repository of that
name or creates a private one with a README (its default branch must be
`main`), opens one fictional issue, clones the repository into a temporary
directory and runs the path. The ledger `FILE` must not exist; the run reserves
it exclusively, so a second or concurrent run never overwrites it. It records
what the run created before each step: the repository creation attempt, its
confirmed creation once `gh repo create` succeeded, then GitHub's immutable
repository id; the issue's unique title, then its number; and the
issue branch with its pushed commit. If an issue's creation response is lost,
the printed commands include a search for that title.

Live mode never deletes anything. Removing a repository or branch is
destructive cleanup and needs an explicit human decision. A successful run
prints, under `leftovers`, the commands that would remove what it created: the
repository if this run confirmed creating it, otherwise the branch (which
closes its PR) and the issue. An attempted but unconfirmed creation lists
`gh repo view REPO --json id,createdAt` to check, never a deletion. After a failed run the ledger lists the same items. The operator
checks the repository id and branch head against the ledger before running
them. The worker turns use the operator's Codex subscription.

| Change | Mode |
| --- | --- |
| Documentation only | none |
| Coordinator steps, claims, admission, settlement, publish rules | local (in the gate) |
| Worker launch, sandbox or permission arguments, Codex protocol, routing, the `gh` or `git push` calls of publication | local, then live |

Live mode may create a GitHub repository and spends subscription usage, so it
needs operator authorization. The operator can grant it once,
in the conversation or in the ignored `AGENTS.local.md`, naming the owner, the
route and the limits, for example: "Agents may run `qualify.py live` on
`OWNER/ballast-qualification-*` with model M and effort E, at most N runs per
issue, creating repositories under that prefix." Without such an
authorization each live run needs its own approval, and the PR lists the
missing live run as a gap. Record the printed evidence under `docs/evidence/`.

## Local execution dashboard

The existing agent conversation can start a foreground dashboard directly from
an operator-selected Ballast source tree. Explicit inputs select the project;
a focused Orca window never selects execution context. No agent, scheduler or
worker starts merely because this UI starts. To create an authorized finite
queue and observe it in one call (defaults are the bounded queue defaults above):

```sh
export BALLAST_COORDINATOR=COORDINATOR_REF
python3 -I -S "$BALLAST_SOURCE/tools/dashboard.py" \
  --cwd "$PROJECT_CHECKOUT" --repo OWNER/REPOSITORY \
  --coordinator "$BALLAST_COORDINATOR" --create --issue 12 --issue 13 \
  --revision INSTRUCTION_REVISION
```

For an existing queue, replace `--create`, `--issue` and `--revision` with
`--queue QUEUE_ID`. Custom finite limits can be configured with the existing
`coordinate create` operation before binding the dashboard. The caller supplies
its existing coordinator reference in the environment; this cooperative identity
is not account authentication. Keep the server in a managed foreground terminal
for its intended lifetime. The printed local URL contains a private fragment
capability; deliver it to the authorized conversation and avoid public logs.
The browser exchanges it for an HttpOnly SameSite cookie and clears the fragment.
Do not share the capability with an untrusted browser user.

Open the URL in an ordinary browser; no Orca installation, account or hosting is
needed. If Orca presentation is requested and available, the coordinator can use
its existing embedded-browser navigation capability to open this exact returned
URL. Orca does not launch or supervise workers. Opening a tab is optional;
standalone coordination and execution remain the operations documented above.

The UI shows only selected queue claims and workers joined through their claim
reservations. Other/legacy claims contribute only to labelled clone-wide capacity.
It never serves private output, checkout paths, raw histories or protocol streams.
The issue list shows recorded activity, PR readiness and pending attention;
issue titles appear only when supplied by an authoritative snapshot. Selected
issue evidence lists recorded entries first and groups missing kinds as unknown.
Pending questions and blockers point back to the main conversation. Worker
settings and evidence appear beside the selected issue, with requested and
observed settings shown separately; each names its executor, and any route
without a `worker.py` receipt, including every coordinator execution, is marked
"unverified route". The header labels live, stale and
disconnected observations; polling preserves issue and worker selection.
Dependency selection uses the existing selector at most once per minute, with a
two-second bound on the complete helper process group. A failed source is unknown;
the observation timestamp identifies cached information. It does not dispatch.

Pause prevents new admissions/turns; resume reuses the existing backend control
and clears quota pauses as documented above. Cancellation asks existing workers
to stop, requires browser confirmation and is terminal for browser controls.
Completed workers remain recorded as completed after cancellation. Unknown work
retains ownership and consumes capacity. No browser retry, release, recovery,
answer, model switching, publication or merge operation exists. Queue replacement
or immutable context changes invalidate reads and controls, with context checked
inside the control mutation lock. Return to the main conversation to reconcile.

### Public progress evidence

The coordinator records actual public evidence in existing claim history; this
is the only progress producer. For example, after a real check:

```sh
python3 -I -S "$BALLAST_SOURCE/tools/coordinate.py" --cwd "$PROJECT_CHECKOUT" \
  record --claim "$ISSUE_CLAIM" --kind check --state passed \
  --summary 'Focused checks passed' --revision FULL_COMMIT_SHA \
  --reference https://github.com/OWNER/REPOSITORY/actions/runs/123
```

Kinds/states are: phase (`understand`, `decompose`, `plan`, `implement`, `verify`,
`review`, `publish`, `blocked`); plan (`proposed`, `accepted`, `blocked`);
question (`pending`, `answered`); decision (`pending`, `resolved`);
check (`pending`, `passed`, `failed`); review (`pending`, `accepted`,
`changes_required`, `blocked`); readiness (`draft`, `blocked`, `ready`). Review
may supply `--round 1..3`. Check/review/readiness require a full revision (40 or 64 lowercase hex).
Question/decision require an issue/comment reference back to the main conversation's
public decision record. Other optional references must be exact selected-repository
GitHub issue/comment, PR or Actions run URLs. Unknown fields are rejected.

Summaries are bounded public declarations curated by the authorized coordinator.
It is responsible for excluding secrets, account details, private reasoning and
paths; validation also rejects control characters and secret-shaped text (API-key,
token, JWT, private-key and URL-credential shapes, `AKIA` and `ASIA` AWS access
keys, `Bearer` and `Authorization Basic|Digest|Negotiate|Token` values,
`password=`-style assignments including prefixed names, `pass=`/`pwd=`
assignments, absolute paths of two or more segments, `file:/` URLs, `~`, drive
paths, `output.txt`). Slack (`xox?-`) and JWT (`eyJ`) prefixes match
case-insensitively, accepting rare false positives to stay strict. A custom `Authorization <scheme> <value>` is not matched: it
cannot be told apart from ordinary prose.
Never copy raw final worker output into this producer or treat it as approval.
The browser cannot record evidence or answer questions. Viewing it conveys no
approval. Evidence is labelled coordinator-recorded; revision-bound declarations
become stale when pinned claim HEAD changes. Missing HEAD/evidence stays unknown.
Recorded worker completion, accepted review, check success and PR readiness are
separate facts. A readiness declaration is a coordinator assertion, not merge
authority, and does not waive the required fresh review/check/acceptance evidence.

### Lifetime and recovery

Server and workers have foreground lifetimes. The server owns only HTTP; its exit
stops no worker and supervises none. Refresh/reopen reads the same durable attempts.
Reopen the printed capability URL after restarting the server to establish a new
in-memory session. Up to eight independent browser sessions can observe one server;
a ninth bootstrap expires the oldest session. Cookies are scoped by bound server
port so dashboards on the same host do not overwrite each other's session.
Page closure changes no backend state. Disconnected/stale views
disable controls; a lost control response is observed, never automatically replayed.
Reachable HTTP proves no coordinator liveness: that field remains unknown.
Coordinator exit may leave interrupted/unknown ownership until the existing
positive-evidence recovery protocol reconciles it. No age/PID heuristic frees work.
