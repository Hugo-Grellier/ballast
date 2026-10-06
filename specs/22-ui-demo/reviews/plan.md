# Plan review: On-demand UI demo capture linked to the PR

- Review: plan (second round, after the revision for the first round's findings)
- Reviewer: claude/claude-opus-5-5, independent context, same provider as the author (reduced independence)
- Run: Autonomous `d6b5dff2`, R2
- Artifacts reviewed: `plan.md`, `research.md` (R1–R15), `data-model.md`, `quickstart.md` (scenarios 1–23), `contracts/capture-workflow.md`, `contracts/demo-command.md`, against `spec.md` at the PD-0008 digest (FR-001–FR-020, AC-001–AC-019, SC-001–SC-006), `intent.md`, `decisions.md` (DEC-0001) and `autonomous/record.md`.
- Not present at this stage: `tasks.md`; there is no code diff yet. `docs/policies/project/engineering.md` and `docs/policies/project/security.md` do not exist.

## History

The first round requested changes. Its high finding was that the capture job ran PR-head code under the default-branch ref, where the Actions runtime token can write caches that every branch and privileged default-branch workflows restore. It also found an arithmetic `timeout-minutes` expression that Actions does not support, an unpaginated run-list window keyed on the wrong event, and an undocumented exit 124/137 ambiguity. DEC-0001 chose the feature-branch ref with a verified definition. The driving agent resolved it under the operator's standing authority, not a human, and FR-007 and AC-010 were reworded through the spec workflow (commit `356bd4b`, intent PD-0008, marked material). This round reviews the plan as revised.

## What was checked

**The first round's findings.** Each one is addressed in the artifacts, not only in the resolution note:

- Execution scope: research R15, the ADR-0013 rules in the plan, the capture-workflow contract (one job, no cache action, `GITHUB_SHA` check in `Validate demo request` before checkout), refusal 10 (`workflow-differs`) in R9 and the command contract, and the `commit-mismatch` resolution rule in R6. Quickstart scenarios 1, 7, 21 and 22 test it.
- Timeout: a literal `65` backstop, with `timeout --kill-after=30s` enforcing the contract value. Scenario 7 tests it.
- Run-list window: the oldest newest-event date, a `branch=` filter, explicit pages up to 5, and `run-list-truncated`. Scenario 23 tests it.
- Exit 124/137: documented in R5, the contract, the policy subsection and scenario 8.

**The new security boundary.** I traced the R15 argument independently:

- Under a `workflow_dispatch` on the feature branch, the run's ref and cache scope are `refs/heads/<feature branch>`.
- GitHub lets a run restore caches from its own ref, a PR's base branch and the default branch. Feature-branch caches are therefore restored only by that branch's own runs and by PRs based on it. All of these already execute code from that branch or its descendants.
- A `pull_request` run uses the merge ref and never restores the head branch's caches.
- So the runtime token that PR-head code can reach writes no scope that the branch's own push CI cannot already write. A push-triggered CI on the feature branch may hold secrets, but it already runs the same agent-written code, so poisoning its cache gives no new reach.
- The blob check compares the head commit, while GitHub resolves the branch tip at run creation. This race is closed for linking by the `head_sha` postcondition. On the runner, the `GITHUB_SHA` check in the validate step runs before checkout, so a mismatched run executes no PR code under the shipped definition.
- If a moved tip carries a different definition, that definition runs. Only a push with write access can move the tip, and such a push can already run any `on: push` workflow. During `ballast run demo` the invocation lock excludes Ballast's own pushes, and agents hold no push or `gh` authority.
- I agree with rejecting the split-job alternative: the runtime token follows the run, not the job's `permissions`.

**Spec conformance after the rewording.** FR-007's three clauses (identical definition with refusal, no run at another commit presented, no feature-branch code under a default-branch ref) map to R15 steps 1–3 and to scenarios 21, 22 and 1. AC-010's new Then clause maps to the same scenarios plus scenario 7. AC-008 (checkout of the PR head, read-only, no secrets) is unchanged and agrees with the new scope. The rest of the coverage is unchanged since the first round and still holds: every FR maps to a plan element, and every AC to a quickstart scenario. SC-001 is honestly scoped as post-merge operator evidence (R13).

**Authority and sources of truth.** Several things are unchanged from the first round and were re-confirmed:

- The command comes only from protected `ballast.toml`, passed as a dispatch input.
- The ledger event carries no free text.
- GitHub is the authority for runs and media, and the packet stays a projection.
- The new GitHub calls are listed for ADR-0013.

The PR read (`pulls/<n>`) is already allowed by ADR-0006, and the reused `draft_pr._Checkpoint`, `checkpoint(create=...)` and `_classify` exist. ADR numbers ran to 0011 at review time (#13 later took 0012, so this ADR is 0013). No agent permission changes. `tools/setup`, `tools/ballast`, `launcher.py` and `claude-settings.json` stay unchanged, so the R2 boundaries touched remain "what ballast executes" and agent authority, as the record states.

**Failure behavior.** The refusal order writes nothing before dispatch. `failed-retryable` reuses #17's causes. R6's resolution order puts `commit-mismatch` before status, so a run that the validate step rejected still shows the mismatch rather than `request-invalid`. A truncated listing never yields a guessed outcome. A dispatched request exits 0 whatever the capture outcome.

## Remaining points

Three small points remain, none blocking:

- Quickstart scenario 1 expects "exactly ADR-0013's" argv sequence, but the request also makes #17 checkpoint calls (ADR-0003) and the PR read (ADR-0006). The plan's performance goal for the request also omits the PR read. The test author needs the full expected sequence, not only ADR-0013's list.
- The run-list query puts `created=>=<date>` in the path given to `gh api`. The scripted fake cannot show whether the comparison operators reach GitHub intact. Percent-encoding them, or confirming the behavior once, avoids a silent empty listing that would surface only as `run-not-found` after 24 h.
- ADR-0013's "why no new reach" should name PRs based on the feature branch, which also restore its caches. This adds no reach, since those PRs run code from the same branch lineage, but the ADR should state it so the boundary argument is complete.

## Verdict

Approved. The revision closes the first round's security-boundary finding with a design whose argument I could verify step by step, and it fixes the other three findings with tests. Security, dependency (the two pinned actions) and documentation reviews remain required at implementation. The verdict and every disposition here are agent-provisional. The R15 execution-scope choice and the FR-007/AC-010 rewording are listed for the merge reviewer as material.

<!-- ballast-findings: begin -->
## Findings (recorded from the review draft)

- F-005 (low, spec-ambiguity, open): Quickstart scenario 1 expects the argv sequence to be exactly ADR-0013's. The request also makes #17 checkpoint calls (ADR-0003) and the PR read (ADR-0006), and the plan's performance goal for the request omits that PR read. Tasks should spell out the full expected call sequence.
- F-006 (info, implementation-bug, open): The run-list query puts created=&gt;=&lt;date&gt; in the gh api path. The offline fake cannot show whether the comparison operators reach GitHub intact. Percent-encode them, or confirm the behavior once, so a malformed filter cannot silently empty the listing and surface only as run-not-found after 24 h.
- F-007 (info, architecture-issue, open): R15's no-new-reach argument should also name PRs based on the feature branch, which restore its caches. They run code from the same branch lineage, so this adds no reach, but ADR-0013 should say so to make the boundary argument complete.
<!-- ballast-findings: end -->
