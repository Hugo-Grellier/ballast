# ADR-0020: Autonomous runs stop only for authority that takes effect before merge

- Status: accepted (2026-10-13, with the change for #150), agent-provisional in Autonomous run `1d0a2143` until the operator merges the PR; that merge is the human approval that accepts it.
- Superseded by [ADR-0024](0024-ballast-2-migration.md) (2026-10-15, Ballast 2.0). Kept unchanged as the v1.x record.
- Risk: R2 (agent authority, the launcher's trust model, accepted architecture).
- Feature: [150-autonomous-stop-rule](../../specs/150-autonomous-stop-rule/spec.md); research [R1 to R9](../../specs/150-autonomous-stop-rule/research.md).
- Amends: [ADR-0004](0004-autonomous-provisional-decisions.md) (when a run blocks; recovery from a block) and [ADR-0010](0010-autonomous-resume-and-bounded-recovery.md) (resume after a provider usage limit; the limit block).

## Context

ADR-0004 lets an Autonomous run record its gate decisions provisionally, but the run still stops for the operator before the merge in several places: clarification without a safe default blocks as `decision`, the intake gate needs the `ready-for-agent` label, every run limit blocks, and ADR-0010 resumes a stopped run only after the operator records a `block-resolution` decision, including after a provider usage limit. The operator's goal is to write the Issue and merge the PR, and nothing in between. Most of these stops guard no authority: a decision that only shapes the PR's content can wait for the merge reviewer, who already approves every provisional decision at once. What must still stop the run is authority that would take effect before anyone reviews it.

## Decision

- **Stop rule.** An Autonomous run blocks only for a decision that takes effect before merge, that is one about run authority, launcher execution, external writes or credentials, or for a contradiction with an invariant the runner enforces. Every other decision the run would have stopped for is recorded as a material provisional decision, with its options, basis and evidence, and listed at the top of the PR for the merge reviewer.
- **What still blocks.** Today's block categories fall under the rule as follows:
  - *Pre-merge authority, still blocks:* `credential`, `permission`, `forge`, `ineligible`, and any undeclared or unauthorized privileged action before merge, such as `secret-provisioning` or `external-write` (ADR-0016).
  - *Runner-enforced invariant, still blocks:* `tamper`, `unfinished-step`, `postcondition` and any protected-input change (BL-INV-002, BL-INV-003, BL-INV-005). A failed `[checks]` command is not a `postcondition`: it is evidence about the change, not a runner invariant.
  - *Material provisional decision instead of a block:* `decision` (no safe default) and `contradiction` with accepted intent or architecture, since neither takes effect before merge.
  - *Limit outcome instead of a block:* `limit` in every form; `review-finding` once the fix cycles are spent; a high or critical finding or a non-approved verdict at plan review or spec reconciliation, which have no fix cycle, so their cycles count as spent at once; and a failed final `run-checks`, whose failed commands the Draft PR lists.
  - *Not a decision, outside the rule:* `interrupted` and `upstream-sync` are technical stops with nothing to decide and keep today's recovery; so does a provider usage limit, except that the runner resumes it itself (**Self-resume**).
- **Trusted author.** An Issue written by an author the operator lists as trusted stands in for the `ready-for-agent` scope approval. The list comes only from operator-controlled data, never from the Issue or an agent-writable file; an Issue without the label whose author is not listed stays ineligible. #152 delivers the list's form.
- **Limit outcome.** Reaching any run limit (agent steps, wall time, fix cycles, draft retries), in any phase, publishes a Draft PR instead of blocking the run. The PR lists the open findings and failed checks and marks every unmet acceptance criterion `unverified`; a limit reached before a spec exists leaves every criterion `unverified`. #153 delivers how the acceptance packet renders `unverified`.
- **Self-resume.** When a provider usage limit stops a run, the runner resumes it once the limit resets, without an operator `block-resolution` record. It records the resume as a runner event naming the usage-limit block, never a human decision, and keeps the run's mode, risk, limits and integrations unchanged. A self-resume counts as a block resolved during the run for [ADR-0019](0019-autonomous-pr-completion.md) condition (11), so the run's PR stays a Draft. #154 delivers the mechanics.
- **Residual risk.** The rule moves more choices to the merge, so the risk is decisions concentrated at the merge: a reviewer facing many material provisional decisions at once. The mitigation is a runner-enforced material-decision cap. A run that reaches it gets the limit outcome, a Draft PR stating the cap was reached. #151 and #153 set the cap's value and configuration.
- **Chat runs.** Chat runs are unaffected: they record no provisional decision, and every Chat gate needs the operator. ADR-0009 stands unchanged.
- **Invariants.** BL-INV-003 and BL-INV-006 are kept unchanged, and no constitution amendment is made: no agent gains authority, and a material provisional decision is never human approval; merging the PR stays the single human approval.
- **Delivery.** This record changes no code. The behavior is delivered by #151, #152, #153 and #154; until each ships, the blocks, limits and resume of ADR-0004 and ADR-0010 apply as written.

## Consequences

- The operator writes the Issue and merges the PR; an eligible run otherwise reaches a Draft PR without stopping, except for pre-merge authority and invariant violations.
- More decisions reach the merge reviewer, listed at the top of the PR with their basis; the material-decision cap bounds how many.
- A run that runs out of a limit still leaves a reviewable Draft PR, with its gaps marked `unverified` rather than hidden.
- The workflow policy and the technical spec point here instead of restating the rule.
- Each of #151 to #154 implements one part of this decision without a new one from the operator.

## Rejected alternatives

- Status `proposed` until #151 to #154 ship: the sibling leaves would have no accepted architecture to implement.
- A superseding ADR: most of ADR-0004 and ADR-0010 still holds, so amendment notes keep their history readable.
- Restating the rule in the workflow policy: a second source of truth that would drift from this record.
- Blocking on every `decision`: keeps the operator in the loop for choices the merge reviewer already approves.
