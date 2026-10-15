# ADR-0019: The trusted runner marks an eligible, opted-in Autonomous PR ready for review

- Status: proposed (2026-10-12, with the change for [#141](https://github.com/Hugo-Grellier/ballast/issues/141), [spec](../../specs/141-autonomous-pr-completion/spec.md)). Drafted agent-provisionally in Autonomous run `478cbe23`; the operator approved the feature intent in human-gated run `6263f734`. Merging the PR is the only human approval that accepts this ADR.
- Superseded by [ADR-0024](0024-ballast-2-migration.md) (2026-10-15, Ballast 2.0). Kept unchanged as the v1.x record.
- Risk: R2 (what Ballast executes, the launcher's trust model).
- Amends: [ADR-0004](0004-autonomous-provisional-decisions.md), its publication decision ("opens one Draft PR") and its narrowing-only `[autonomous]` consequence. Extends: [ADR-0003](0003-launcher-github-authority.md), its fixed command list.

## Context

ADR-0004 makes every Autonomous run end with a Draft PR, and the Publication contract says no step marks a PR ready. For a converged R1 run whose checks all passed and whose acceptance packet shows every criterion verified, the operator then marks the PR ready by hand before reviewing it, as in the LoreForge pilot. That step adds no information. Marking a PR ready approves nothing: GitHub branch protection, CI and the human merge still gate the change. It is still a forge write that the runner does not make today, so it needs an operator opt-in and must stay out of agent reach.

## Decision

- **Opt-in.** `ballast.toml` gains `[autonomous] completion = "draft" | "ready"` (default `draft`) and `completion_max_severity = "low" | "info" | "none"` (default `low`). An unknown value is stored as the default with the existing "cannot widen eligibility" warning. `completion` is an explicit operator opt-in to one runner action, never a wider eligibility: it makes no ineligible start eligible. `ballast run start --mode autonomous --completion draft` narrows one run; `--completion ready` without a configured `ready` refuses the start before any record is written. The run's policy snapshot records the configured value, the flag and the effective value. `resume --refresh-policy` re-reads the configured values from the `ballast trust` baseline and keeps the flag.
- **Where and when.** `run.py` evaluates once, after the Draft PR checkpoint and acceptance packet of the invocation that published (`start`, `resume`, or a `ballast run publish` retry, which then also runs the checkpoint and packet). The publication's PR and pushed commit pass in-process, never persisted. Only a run whose snapshot has `completion_configured = "ready"` prints or records anything, so a project without the key sees today's output and ledger exactly. `ballast run checkpoint`, Chat and human-gated runs never evaluate.
- **Twelve conditions, from operator records only.** A pure function (`completion.evaluate`) checks, in order, and lists every failure: (1) Autonomous at publication; (2) effective policy `ready`; (3) risk R0 or R1 and no R2 boundary declared; (4) no privileged action declared; (5) final acceptance recorded; (6) the recorded spec-reconciliation review approved; (7) no `open` or `accepted-provisionally` finding above the threshold; (8) `[checks]` passed in `run-checks` on the tree publication committed; (9) the acceptance packet was published at the pushed commit with every criterion `verified`; (10) no material provisional change; (11) no block resolved during the run; (12) one read-back shows the PR still the run's open Draft at the pushed commit. Condition (3) also fails when the run record declares an R2 boundary, whatever its level. Its inputs are the run record, the hash-chained decision log, the human decisions, `checks.json`, this invocation's packet outcome and that read-back. The code reads only operator records, but some of them hold agent-provisional content: a decision's verdict, finding severities and `material` flag began as an agent draft that a trusted recorder validated ([research R7](../../specs/141-autonomous-pr-completion/research.md#r7-agent-derived-values-inside-operator-records)), and `checks.json` is runner-recorded as [ADR-0018](0018-runner-recorded-acceptance-checks.md) describes. No agent-written file, draft or checkout copy of `ballast.toml` is read.
- **The forge action.** Only when no condition fails does the runner run `gh pr ready <n> --repo <pinned>` as the operator, through `draft_pr`'s resolved `gh`, hardened environment and empty working directory. ADR-0003's command list gains this one command. A second read-back must show `draft: false` at the pushed commit before `ready` is recorded (BL-INV-005). A call that succeeded but whose read-back does not show the PR ready is `unverified`. A failed, timed-out or interrupted call may still have been applied, so the runner reads the PR back once: ready at the pushed commit is `ready`, the run's Draft still at that commit keeps the Draft with a fixed cause code, and anything else is `unverified`. Once the request is issued, a Draft is never reported blindly.
- **Output and evidence.** One `PR completion:` line (`ready-for-review`, `draft` with every reason, or `unverified`) and one runner-only `pr_completion` ledger event with fixed reason codes. No `gh` output, token or agent text is printed or recorded. The step never changes the exit status, the run's status or its block.
- **Agents.** `mark-ready` stays a never-authorizable privileged-action kind (ADR-0016); agents still cannot run `gh` or write operator records.
- **Not an approval.** Marking ready is not an approval. Merging stays the only human approval (BL-INV-006), and every line, record and document says so.

## Consequences

- A converged, low-risk, opted-in run reaches review with zero manual steps; any other run keeps a Draft and names why.
- Every resume records a `block-resolution` human decision, so condition (11) keeps a resumed run's PR a Draft, a `--refresh-policy` resume included.
- Residual head race: GitHub's ready-for-review mutation takes no expected head. A push between the read-back and `gh pr ready` leaves a ready PR at another head; the post-ready read-back records `unverified`, and the PR is not converted back, which would be a further forge write. Branch protection and the human merge still gate it, as with #17 DEC-0007's accepted body race.
- Conditions (6), (7) and (10) read decisions that trusted recorders validated but whose content began as an agent draft, the provenance every Autonomous decision already has. The merge reviewer sees each one in the PR.
- A stream holding a `pr_completion` event is rejected by an older pinned Ballast, as ADR-0018 records for `runner-recorded`. Without the opt-in no such event is written.
- A PR the runner marked ready cannot be adopted by `ballast run continue RUN --mode chat`, which needs a Draft: the operator first runs `gh pr ready --undo <n>`. Letting adoption accept a runner-marked-ready PR is a follow-up ([DEC-0003](../../specs/141-autonomous-pr-completion/decisions.md)).
- Merging and GitHub auto-merge stay out of scope (#143, ADR first).

## Rejected alternatives

- Marking ready inside the publisher: it runs before the packet exists, so condition (9) could never hold.
- Persisting a pending-completion flag in the run record: it changes every run record and leaves a state a later command could act on.
- Reading `reviews/convergence.md` or other feature artifacts for eligibility: they are agent-written.
- `gh api graphql` with `markPullRequestReadyForReview`: another call path with no stronger guarantee.
- `gh pr ready --undo` after an unverified ready: one more forge write that widens the R2 surface.
- Stopping at the first failed condition: the operator needs every reason to act on a Draft.
