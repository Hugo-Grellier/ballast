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

Run one issue and one worker at a time. Workers run in the foreground, at most
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
   the operator-selected helper source (`BALLAST_V2_SOURCE` below):

   ```sh
   python3 -I -S "$BALLAST_V2_SOURCE/tools/worktree.py" \
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
python3 -I -S "$BALLAST_V2_SOURCE/tools/worker.py" \
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
before replacement. Queue/recovery support is a separate milestone.

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
