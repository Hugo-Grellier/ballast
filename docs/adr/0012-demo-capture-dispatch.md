# ADR-0012: Demo capture dispatch under the launcher's GitHub authority

- Status: proposed (2026-10-06, with the plan of [feature 22](../../specs/22-ui-demo/plan.md#architecture-boundaries); agent-provisional in Autonomous run `d6b5dff2`, accepted only when the operator merges the feature PR)
- Feature: [22-ui-demo](../../specs/22-ui-demo/spec.md), FR-004, FR-006, FR-007, FR-015, AC-010; research [R2](../../specs/22-ui-demo/research.md#r2-where-the-contract-lives-and-what-the-runner-executes), [R12](../../specs/22-ui-demo/research.md#r12-new-github-calls-adr-0012), [R15](../../specs/22-ui-demo/research.md#r15-execution-scope-of-the-capture-run-plan-review-f-001); [decisions.md DEC-0001](../../specs/22-ui-demo/decisions.md#dec-0001--proposal)
- Extends: [ADR-0003](0003-launcher-github-authority.md) and [ADR-0006](0006-review-packet-reads.md), whose fixed command allowlist says a later feature extends it by a new ADR

## Context

Feature 22 lets the operator request a short video of implemented UI behavior for the feature's open Draft PR, and shows the result in the acceptance packet. The capture runs the project's own scenario command on a GitHub-hosted runner, so Ballast never installs a browser or recorder and never runs the command locally. Starting that run needs Ballast's first GitHub write other than the PR body: a `workflow_dispatch`. Reading its result needs Actions reads ADR-0003 and ADR-0006 do not list.

The capture job runs code from the PR head, which agents write. Any code in a job can obtain the run's Actions runtime token, and that token writes Actions cache entries scoped to the run's ref. A run whose ref is the default branch would let PR-head code write caches that every branch and the project's privileged default-branch workflows restore. A feature branch's own CI cannot write that scope today (research R15, plan review F-001).

## Decision

- The request is the trusted `run.py` subcommand `ballast run demo RUN_ID SCENARIO [--no-wait]`, run by the operator. It holds the run's invocation lock and refuses while the tamper marker or an agent step's `in-progress` marker exists. It starts no agent. The scenario, its command, the video path, the timeout and the retention come only from the `[demo]` table of the protected `ballast.toml`; no copy of `ballast.toml` on any branch is read on the runner.
- Every call goes through the #17 checkpoint's seam: the resolved `gh`, a list argv, the hardened environment, an empty working directory and the 30 s limit. `gh` output is parsed, never printed or stored.
- The allowlist gains these calls:
  - `gh api repos/<o>/<r>/actions/workflows/ballast-demo.yml` (read): the workflow must exist and be `active`;
  - `gh api "repos/<o>/<r>/contents/.github/workflows/ballast-demo.yml?ref=<ref>"` (read), once at the PR head commit and once on the default branch, for the blob `sha` only;
  - `gh api --method POST repos/<o>/<r>/actions/workflows/ballast-demo.yml/dispatches --input -` (the one new write), with the JSON body on stdin;
  - `gh api "repos/<o>/<r>/actions/workflows/ballast-demo.yml/runs?event=workflow_dispatch&branch=<feature branch>&created=>=<date>&per_page=100&page=<n>"` (read), one bounded call per page, at most 5 pages, never `--paginate`;
  - `gh api "repos/<o>/<r>/actions/runs/<id>/jobs?per_page=100"` (read), only for a completed run that did not succeed;
  - `gh api "repos/<o>/<r>/actions/runs/<id>/artifacts?name=ballast-demo-<request>"` (read), only for a successful run.
  The PR read and the repository read are already allowed by ADR-0003 and ADR-0006.
- **Execution scope.** Untrusted PR-head code never runs in a workflow run whose ref is the default branch:
  - the dispatch `ref` is always the feature branch the run pinned, which is the PR's head ref, and never the default branch;
  - Ballast dispatches only when the head commit's `ballast-demo.yml` has the same Git blob ID as the default branch's, and refuses `workflow-differs` otherwise, with nothing dispatched and nothing recorded;
  - the job rejects a run whose `GITHUB_SHA` is not the requested commit, and checks out that commit;
  - Ballast links a result only when the run's `head_sha` is the requested commit; any other run is `failed (commit-mismatch)` and its artifact is never linked.
  The dispatch `ref` must be a branch name, so GitHub resolves its tip only when it creates the run. A push between the check and the dispatch is caught by the last two rules. Whoever can move the branch tip can already run any definition on that branch with a push, so the race grants nothing new; agents cannot push, and the run's lock excludes Ballast's own pushes during the request.
- **The job's constraints**, checked by a static test of the template: `workflow_dispatch` is the only trigger; `permissions: contents: read` at the workflow level and no job-level override; no `secrets.` reference and no `environment:`; inputs reach shells only through `env:`; `actions/checkout` and `actions/upload-artifact` are pinned by commit SHA, with `persist-credentials: false` and no cache action or `cache:` input; the command runs under `timeout`, and the job's `timeout-minutes` is a fixed backstop.
- Correlation uses a random 16-hex request ID that only Ballast generates: the run's name is `Ballast demo <request>` and its artifact is `ballast-demo-<request>`. Several runs with one name are `failed (run-ambiguous)`, never a guess.
- The `demo_capture` ledger event is written only after the dispatch call succeeds. It has no free text.

## What it does not add

- No new program and no local execution: Ballast never runs the project's command, and never downloads a browser, a recorder, a log or an artifact.
- No GitHub write other than the one dispatch and the existing PR body edit; no PR is ever created by a capture.
- No agent authority: agents keep `Bash(gh *)`, `Edit(./.github/**)` and `Edit(./ballast.toml)` denied, and never receive a token.

## Consequences

- A capture's outcome is evidence for the reviewer, never a criterion's state and never an approval. A failed or missing capture shows as missing evidence with a fixed reason.
- A feature branch must carry the default branch's `ballast-demo.yml`. A branch cut before the template was installed, or one that changed it, is refused until it is synced with the default branch.
- Anyone with write access can dispatch the workflow with any command. They can already push workflows, so this grants nothing new; the job has no secrets and a read-only token.
- The video is an Actions artifact, readable by anyone with read access to the repository. The project's scenario must use seeded, nonsensitive data and fake accounts.
- A further GitHub call needs another ADR.

## Rejected alternatives

- Dispatching on the default branch: PR-head code would reach default-branch caches through the run's runtime token, which a job's `permissions` cannot remove (BL-INV-003).
- Splitting the job so the command runs without the upload action: the runtime token and its cache scope belong to the run and its ref, not to a job, so the split adds a hand-off and closes nothing.
- A `pull_request`-triggered capture: Ballast cannot dispatch that event, and a label or comment trigger would let others request captures (D-02).
- Reading the run's logs or downloading the artifact to tell a failure's cause: it brings free text and credentials risk into Ballast; fixed step names give the cause from structured fields.
