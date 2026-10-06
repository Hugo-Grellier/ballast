# Research: On-demand UI demo capture linked to the PR

Phase 0 decisions for [plan.md](plan.md). Each entry gives the decision, the rationale and the alternatives considered. Every decision is agent-provisional in Autonomous run `d6b5dff2`; merging the PR is the only human approval.

## R1. Where the request lives: `ballast run demo RUN_ID SCENARIO`

- **Decision**: a new `run.py` subcommand, `ballast run demo RUN_ID SCENARIO`, bound to a run that already has a Draft PR. It takes the run's invocation lock, as `checkpoint` does, and starts no agent.
- **Rationale**: the run pins the branch, the feature, the ledger the packet reads and the `[github] repository` (ADR-0003, ADR-0005). `ballast run` already holds GitHub authority in `run.py`'s own process, and the launcher already refuses while the tamper marker or an agent step's `in-progress` marker exists. Agents are denied `gh *` (`claude-settings.json`), and the workflow engine never receives the token variables (`draft_pr.TOKEN_VARIABLES`). So FR-004 and AC-019 hold without a new permission rule.
- **Alternatives**: a top-level `ballast demo` command would need its own feature and branch resolution and a second lock. A PR comment or label trigger was rejected by D-02.

## R2. Where the contract lives and what the runner executes

- **Decision**: a `[demo]` table in the protected `ballast.toml` ([contracts/demo-config.md](contracts/demo-config.md)). Ballast reads it from the operator's trusted checkout and validates it. It passes the chosen scenario's `command`, `video`, `timeout_minutes` and `retention_days` to the workflow as dispatch inputs. The workflow is dispatched on the **PR's head branch** ref, never the default branch ([R15](#r15-execution-scope-of-the-capture-run-plan-review-f-001)). Before dispatching, Ballast requires the head commit's `.github/workflows/ballast-demo.yml` to be byte-identical (same Git blob ID) to the default branch's, and refuses with `workflow-differs` otherwise. After the run starts, the run's `head_sha` must equal the requested commit, or the capture is `failed` (`commit-mismatch`). The job checks out the requested commit and runs the command from the input.
- **Rationale**: the command comes from the file `ballast trust` protects, which agents cannot edit (FR-002, AC-010). No copy of `ballast.toml` on any branch, including one an agent wrote, is read on the runner. Agents also cannot edit `.github/**` (`claude-settings.json` denies it), and a feature-branch edit of the workflow is refused before dispatch because the definition that would run is compared with the default branch's.
- **Alternatives**:
  - The workflow reads `ballast.toml` from the default branch. A contract added in the same feature PR would then be unusable before merge, and the runner would need a TOML parser step.
  - The workflow reads `ballast.toml` at the PR head. That is a branch that agents' commits reach, so it was rejected.
- **Accepted consequence**: anyone with write access can dispatch the workflow with any command. They can already push workflows, so this grants nothing new. The job has no secrets and a read-only token (R4). The run executes PR-head code, so it must never run under the default-branch ref; R15 gives the reasoning, and this entry no longer claims the job grants nothing new on that ref.

## R3. Correlating a dispatch with its workflow run

- **Decision**: Ballast generates a random 16-hex-digit request ID and passes it as the `request` input. The workflow sets `run-name: Ballast demo <request>` and uploads the artifact as `ballast-demo-<request>`. To read results, Ballast lists the workflow's `workflow_dispatch` runs on the feature branch, created on or after the window date of [R6](#r6-outcome-resolution-at-a-checkpoint), and matches `display_title` exactly. Ballast ignores the dispatch response body.
- **Rationale**: the classic dispatch endpoint returns `204` with no run ID. Matching on a value only Ballast generates is deterministic and works whether or not GitHub returns run details. More than one matching run is reported as `failed` (`run-ambiguous`), never by guessing.
- **Alternatives**: matching on the newest run after the dispatch time races with other dispatches. Reading the run's inputs is not possible, because the runs API does not return them.

## R4. Capture workflow template (`templates/github/workflows/ballast-demo.yml`)

- **Decision**: a copy-once template, committed by the project to `.github/workflows/ballast-demo.yml` on its default branch. Its full shape is in [contracts/capture-workflow.md](contracts/capture-workflow.md):
  - `on: workflow_dispatch` only;
  - `permissions: contents: read`, and no `actions/cache` or other cache step;
  - no `secrets.` reference and no `environment:`;
  - `actions/checkout` and `actions/upload-artifact` pinned by full commit SHA, with `persist-credentials: false`;
  - every input reaches a shell only through `env:`, never `${{ }}` inside `run:`;
  - each input is validated in the job;
  - the command runs under `timeout --kill-after=30s "${TIMEOUT}m"`, which enforces the contract value; the job's `timeout-minutes` is a fixed literal `65` (the 60-minute maximum, the 30 s kill grace, checkout and upload), a backstop only. GitHub Actions expressions have no arithmetic, so the job timeout cannot be derived from the input (plan review F-002);
  - fixed step names report the failure cause;
  - the single video file is uploaded with `retention-days` from the input and `if-no-files-found: error`.
- **Rationale**: this meets FR-006, AC-008, SC-005 and the security policy's script-injection rule. Upload-artifact uses the runner's internal artifact token, so `contents: read` is enough.
- **Alternatives**:
  - `gh run download` or a Ballast-run upload was rejected: Ballast would handle media locally (D-05).
  - A reusable workflow called from Ballast's repository was rejected: it would run code from a source the project does not pin (BL-INV-004).
- **Dependency note**: the two first-party GitHub Actions are new dependencies of the template, not of Ballast's tools. They need a [dependency evaluation](../../.agents/skills/ballast-dependency-evaluation/SKILL.md), and their SHAs are pinned at implementation, with Dependabot's `github-actions` ecosystem able to update them.

## R5. Failure causes without downloading logs

- **Decision**: the template's steps carry fixed names. Ballast reads `actions/runs/<id>/jobs` only for a completed, non-successful run, and maps the first failed step to a reason:

  | Failed step | Outcome | Reason |
  | --- | --- | --- |
  | `Validate demo request` | `failed` | `request-invalid` |
  | `Demo command timed out` (the command step exited 124 or 137 under `timeout`; see the note below) | `failed` | `timed-out` |
  | `Demo command failed` | `failed` | `command-failed` |
  | `Demo video missing` | `missing` | `no-video` |
  | none of these, or conclusion `cancelled`/`timed_out` | `failed` | `cancelled` / `timed-out` / `job-failed` |

- **Exit 124 and 137** (plan review F-004): `timeout` exits 124 when it stops the command and 137 when the 30 s kill grace ends in `SIGKILL`. The job cannot tell these from a command that itself exits 124 or 137, or one killed by the kernel's out-of-memory killer (also 137). All are reported as `timed-out`. This is accepted, and the policy's demo subsection says so.
- **Rationale**: the reasons are fixed and come from structured API fields. No log or command output is read, printed or stored (FR-017, FR-018). A project that edits the template's steps still gets a truthful `failed` (`job-failed`).
- **Alternatives**: parsing logs was rejected (it brings free text and credentials risk). A status file inside the artifact was rejected (it needs a download).

## R6. Outcome resolution at a checkpoint

- **Decision**: for each scenario, take the newest `demo_capture` ledger event of the run (by sequence). Resolve it in this order:
  1. No matching run yet: `in progress` (`queued`), unless 24 h have passed since the dispatch. Then it is `failed` (`run-not-found`). When the listing stopped at its page bound (below) before it was complete, an unmatched request is `failed` (`run-list-truncated`) instead, whatever its age.
  2. The run's `head_sha` is not the event's `commit`: `failed` (`commit-mismatch`), linking the run, never the artifact ([R15](#r15-execution-scope-of-the-capture-run-plan-review-f-001)).
  3. Run not `completed`: `in progress` (`running`), linking the run.
  4. `success`: the artifact `ballast-demo-<request>` must exist and not be `expired`. Then it is `captured`, linking the artifact. Otherwise it is `missing` (`expired` or `artifact-absent`).
  5. Any other conclusion: R5.

  Then, if the event's `commit` is not the PR's current head, the line shows `stale` with the commit and the resolved outcome there (FR-011, PD-0005).
- **Run-list window** (plan review F-003): every scenario's newest event is resolved again at each checkpoint, and nothing is cached. So the window starts at the UTC date of the **oldest** of those newest events (`created=>=<date>`), not at the earliest pending one. The list is also filtered to `branch=<feature branch>`, so it holds only this feature's demo runs. Ballast reads pages of 100 (`page=1, 2, ...`) until a page has fewer than 100 runs, and at most 5 pages (500 runs). Each page is one bounded `gh api` call; `--paginate` is not used. Hitting the bound gives the `run-list-truncated` rule above, never a guessed outcome. The wait loop (R8) reads only page 1, from the dispatch date.
- **Link shapes**: the artifact link is `https://github.com/<o>/<r>/actions/runs/<run>/artifacts/<artifact>` and the job link is `…/actions/runs/<run>`. Both are built from validated integers only.
- **Rationale**: GitHub stays the source of truth for the run and the media. The ledger keeps only what Ballast decided: the scenario, commit, request and command digest. The packet remains a regenerable projection (#19 FR-002).

## R7. Ledger event `demo_capture`

- **Decision**: a new runner-only kind with `scenario`, `commit` (oid), `request` (16 hex), `command_digest` (sha256 hex) and `pr_number`. It is written only after the dispatch call succeeds. There is no free text: the scenario name is restricted to `[A-Za-z0-9._-]{1,64}`. The environment and command are rendered from the current contract. When the current command's digest differs from the event's, the line adds `(declared command changed since this capture)`, so the reproduce command is never presented as the one that ran when it is not (AC-007).
- **Alternatives**: storing the command text in the ledger would add free text, against #19's ledger rule. An operator-state file outside the ledger would be a second record of the same fact.

## R8. Bounded wait after dispatch (D-07)

- **Decision**: after dispatching, poll the run list every 10 s for at most 120 s, until the run completes. Then run the #17 checkpoint with `create=False`, which publishes the packet. An unfinished capture shows `in progress`. `ballast run checkpoint RUN_ID` (Autonomous) or the next run invocation refreshes it. `--no-wait` skips the polling but still refreshes the packet.
- **Rationale**: at most 12 list reads and no long-blocking command. The packet refresh reuses the existing checkpoint path, so publication rules (re-read before edit, one section, in place) are unchanged (FR-013, AC-006, AC-013).

## R9. Refusals before dispatch

- **Decision**: checks run in a fixed order, and the first failing one prints `Demo capture: refused (<reason>): <remedy>` and exits 1:
  1. `untrusted`: tamper or in-progress marker.
  2. `lock-held`.
  3. `not-configured`: no `[demo]` table.
  4. `config-invalid`: the reason is named.
  5. `unknown-scenario`.
  6. `no-draft-pr`: the #17 checkpoint with `create=False` is `skipped`.
  7. `pr-not-open`: any outcome other than `reused`.
  8. `workflow-not-installed`: the workflow read returns 404.
  9. `workflow-disabled`: the workflow's `state` is not `active`.
  10. `workflow-differs`: the blob ID of `.github/workflows/ballast-demo.yml` at the PR head commit is absent or differs from the one on the default branch (two contents reads, R15).

  GitHub failures print `Demo capture: failed-retryable (<cause>)` with `draft_pr._classify`'s causes and exit 1. Nothing is dispatched and no ledger event is written in any of these cases (AC-014, AC-015, AC-016, AC-018).
- **Rationale**: this reuses #17's PR settlement instead of a second PR lookup, so a capture can never create a PR (FR-013).

## R10. Contract limits

- **Decision**:

  | Key | Rule | Default |
  | --- | --- | --- |
  | `retention_days` | integer 1–90 (GitHub's maximum; a repository setting may lower it, and GitHub then applies the lower value) | 14 |
  | `timeout_minutes` | integer 1–60 | 15 |
  | `[[demo.scenarios]]` | 1–20 entries, unique names | |
  | scenario `name` | `[A-Za-z0-9._-]{1,64}` | |
  | scenario `command` | 1–1000 printable characters, one line | |
  | scenario `video` | `packet.safe_path` (relative, plain segments, no `..`) | |
  | scenario `environment` | 1–80 printable characters | |
  | anything else | `unknown key` | |

- **Rationale**: these are the limits from D-06 and AC-017. 20 scenarios keep the packet's GitHub reads bounded.

## R11. Packet integration

- **Decision**: `packet._Step.collect` calls `demo.collect`, which adds a `demo` field to `Sources`. `render` places a `### Demo captures` section after `### UI states`. The section states that a video helps a reviewer see behavior and is not evidence of a criterion. Criteria, counts and evidence states never read demo data (FR-014, AC-005).
- **Failure handling**: a GitHub read failure in `demo.collect` fails the packet step as `failed-retryable` with the classified cause, as a check-run read failure does today. The rest of the run is unaffected, and the next checkpoint retries.
- **Shortening**: at size level 3 and above the section shrinks to one count line.
- **Rationale**: this follows the existing UI-state and check-run patterns. No new packet state is needed.

## R12. New GitHub calls (ADR-0012)

- **Decision**: a new [ADR-0012](../../docs/adr/0012-demo-capture-dispatch.md) extends ADR-0003 and ADR-0006 with:
  - `gh api repos/<o>/<r>/actions/workflows/ballast-demo.yml` (read);
  - `gh api --method POST repos/<o>/<r>/actions/workflows/ballast-demo.yml/dispatches --input -` (the one new write, JSON on stdin);
  - `gh api "repos/<o>/<r>/contents/.github/workflows/ballast-demo.yml?ref=<ref>"`, once with the PR head commit and once with the default branch, for the blob `sha` only (R15);
  - `gh api "repos/<o>/<r>/actions/workflows/ballast-demo.yml/runs?event=workflow_dispatch&branch=<feature branch>&created=>=<date>&per_page=100&page=<n>"`, n ≤ 5 (R6);
  - `gh api "repos/<o>/<r>/actions/runs/<id>/jobs?per_page=100"`;
  - `gh api "repos/<o>/<r>/actions/runs/<id>/artifacts?name=ballast-demo-<request>"`.

  The repository read that is already allowed supplies the default branch. The dispatch body's `ref` is the feature branch the run pins, which is the PR's head ref by #17's construction.
- **Rationale**: FR-015. There is no new program, no local execution of the project's command, and no download.

## R13. Pilot evidence (SC-001)

- **Decision**: all acceptance criteria are verified offline with a scripted `gh` fake and a static check of the template. The live pilot needs the template on a default branch with a real UI scenario, so it is post-merge evidence. The PR records it as an open item for the operator, not as a passed check.
- **Rationale**: a live dispatch from this run would be a privileged external action before the human merge approval.

## R14. Risk recheck

- **Decision**: R2 stands. The change adds a path by which `ballast` causes a project command to execute (on the forge runner) and a new GitHub write (dispatch). It does not change agent permissions, the trust model, the fetch path or the ignore rules. The execution scope of that command is decided in R15. Required reviews: engineering, security, test, documentation and dependency evaluation (for the template's actions).

## R15. Execution scope of the capture run (plan review F-001)

- **Problem**: the capture job runs PR-head code, which agents write. Any code in a job can obtain the run's Actions runtime token. It can read it from the runner worker process (GitHub-hosted runners give the job user passwordless `sudo`), or rewrite an already-downloaded action that a later step executes. That token writes Actions cache entries scoped to the run's ref. If the run's ref is the default branch, every branch and the project's privileged default-branch workflows restore what that code writes. A feature branch's own push or `pull_request` CI cannot write that scope today.
- **Decision**: the run's ref is the PR's head branch, so the only cache scope the job can write is `refs/heads/<feature branch>`. The definition that GitHub loads from that branch is trusted by checking it, not by its location:
  1. **Before dispatch**, Ballast reads the blob `sha` of `.github/workflows/ballast-demo.yml` at the PR head commit and on the default branch (contents API). It dispatches only when they are equal, and refuses `workflow-differs` otherwise, with nothing dispatched and nothing recorded. The default-branch copy must still exist, because GitHub dispatches only workflows present on the default branch (`workflow-not-installed`).
  2. **On the runner**, `Validate demo request` also rejects the run unless `GITHUB_SHA` equals the `commit` input. The checkout uses `ref: ${{ inputs.commit }}` and verifies `HEAD`.
  3. **After the run starts**, Ballast's postcondition is the run's `head_sha` from the runs API. A run whose `head_sha` is not the requested commit is `failed` (`commit-mismatch`), and its artifact is never linked (R6). This covers a push to the branch between the check and the dispatch: the dispatch `ref` must be a branch name, and GitHub resolves its tip only when it creates the run.
- **Why this grants no new reach**:
  - The caches the job can write are readable only by runs whose ref is the feature branch. Those runs already execute that branch's code.
  - A `pull_request` run restores from its merge ref and the base branch, never from the head branch. The default branch never restores feature-branch caches.
  - Artifacts are scoped to the run. Job code can at most replace or add artifacts in its own run, and Ballast reads artifacts only of the run it matched by request ID.
  - In the race of step 3, whoever moves the branch tip can already run any definition on that branch with a push (an `on: push` workflow). Pushing needs write access, and agents cannot push. During `ballast run demo`, the run's invocation lock excludes Ballast's own pushes and the launcher refuses while an agent step is in progress. The race also cannot lead to a linked video.
- **Alternatives**:
  - **Keep the default-branch ref and split the job.** Run the command in a job with `permissions: {}` and no `actions/upload-artifact`, and hand only a size-bounded file to a separate upload job. Rejected: the runtime token and its cache scope belong to the run and its ref, not to a job's `permissions` or to the actions it uses. A job with `permissions: {}` that uses no action still receives the token. "No cache use" cannot be enforced against code that holds the token. The split would add a second job and a hand-off channel and still leave default-branch cache writes reachable.
  - **Keep the default-branch ref and accept the residual risk in ADR-0012.** Rejected: it gives agent-written code new reach into privileged default-branch workflows, which BL-INV-003 forbids.
  - **A `pull_request`-triggered capture** (merge-ref scope). Rejected: Ballast cannot dispatch a `pull_request` event. A label or comment trigger was rejected by D-02.
  - **A feature-branch caller of a reusable workflow pinned to the default branch.** Rejected: the caller file on the branch still needs the same identity check, so it adds a second file and no safety.
- **Consequences**:
  - A feature branch must contain the same `ballast-demo.yml` as the default branch. A branch cut before the template was installed, or one that changed it, is refused with the remedy to sync the branch with the default branch.
  - FR-007 and AC-010 described the guarantee as "the definition comes from the default branch". The guarantee is now "the definition is identical to the default branch's, and no PR-head code runs under the default-branch ref". That needs a spec wording change: [decisions.md DEC-0001](decisions.md#dec-0001--proposal).
  - ADR-0012 records these rules and the race's bound.
