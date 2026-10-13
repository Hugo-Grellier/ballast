<!-- ballast-discovery: input evidence -->
# Discovery brief: Autonomous runs stop only for in-run authority changes

This brief is input evidence for [spec.md](spec.md). It is not the feature's
authority: once intent is recorded, [spec.md](spec.md) and [intent.md](intent.md)
govern, and later steps do not read requirements from this file.

**Mode**: autonomous
**Issue**: #150 (snapshot `.specify/workflow-state/issues/150.md`, untrusted requirements data)

## Sources

- S-1: Issue #150 body
- S-2: .specify/workflow-state/issues/150.md#intake-scope-comment (the intake scope comment; the Issue has no other comments)
- S-3: docs/adr/0004-autonomous-provisional-decisions.md
- S-4: docs/adr/0010-autonomous-resume-and-bounded-recovery.md
- S-5: docs/adr/0009-chat-mode-operator-driven-steps.md
- S-6: docs/adr/0016-privileged-action-kinds-and-policy-refresh.md
- S-7: docs/adr/0017-deferred-operator-tasks-and-unmapped-criteria.md
- S-8: .specify/memory/constitution.md
- S-9: docs/policies/spec-kit-workflow.md#autonomous-runs
- S-10: docs/policies/spec-kit-workflow.md#scope-and-decomposition-gate
- S-11: docs/policies/spec-kit-workflow.md#acceptance-packet
- S-12: docs/policies/project/workflow.md#r2-boundaries
- S-13: docs/policies/issue-tracker.md
- S-14: specs/TECHNICAL-SPEC.md (status paragraphs near the branch-synchronization and Chat-mode sections)
- S-15: tools/spec_workflow/autonomy.py (eligibility: `ready-for-agent` label and `SCOPE_AUTHORS`)
- S-16: .claude/skills/speckit-ballast-clarify/SKILL.md
- S-17: specs/150-autonomous-stop-rule/autonomous/record.md (PD-0001)
- unavailable: Epic #149 and sibling Issues #151–#154 — agents cannot call `gh`; only the #150 snapshot is readable in the run

## Need

- **User**: the operator of a Ballast project who starts Autonomous runs and wants to be involved only in writing the Issue and merging the PR [S: Issue #150 body]
- **Job to be done**: record, as accepted architecture, when an Autonomous run may stop for a human and what it does instead of stopping, so that sibling leaves #151–#154 can implement it [S: .specify/workflow-state/issues/150.md#intake-scope-comment]
- **Current pain**: ADR-0004 makes gate decisions provisional, yet the clarify skill, the intake gate, the limits and ADR-0010's resume rule still stop for a human mid-run [S: Issue #150 body]
- **Intended outcome**: an accepted ADR stating the stop rule, the trusted-author rule, publish-unverified instead of a limit block, unattended self-resume after a provider usage limit, and the residual risk with its material-decision cap, referenced from the workflow policy and the technical spec [S: Issue #150 body]

## Examples

- A clarify question with no safe default (today a `decision` block per the clarify skill) becomes a material provisional decision listed at the top of the Draft PR instead of a stop [S: .claude/skills/speckit-ballast-clarify/SKILL.md]
- A run that exhausts the agent-step limit (today a `limit` block resumed only by `continue` or a new run) publishes a Draft PR whose acceptance packet marks unmet criteria `unverified` [S: docs/policies/spec-kit-workflow.md#autonomous-runs]
- A run stopped by a provider usage limit is resumed by the runner after the limit resets, without an operator `block-resolution` record [S: Issue #150 body]
- An Issue whose author the project trusts can start an Autonomous run without the `ready-for-agent` label, which `autonomy.py` requires today [S: tools/spec_workflow/autonomy.py]
- A run that would need `secret-provisioning` or an `external-write` before merge still blocks, because that decision takes effect before merge [S: Issue #150 body]

## Scope

- A new ADR under `docs/adr/` defining the stop rule, trusted-author rule, limit outcome, self-resume and residual risk [S: .specify/workflow-state/issues/150.md#intake-scope-comment]
- Status or amendment notes on ADR-0004 and ADR-0010, and on ADR-0009 only if Chat is affected [S: .specify/workflow-state/issues/150.md#intake-scope-comment]
- References to the new ADR from `docs/policies/spec-kit-workflow.md` and `specs/TECHNICAL-SPEC.md` [S: IAC-2]

## Non-goals

- Implementing clarify/decide behavior (#151), the intake allowlist and Epic decomposition (#152), the token budget and unverified publication (#153), or quota self-resume (#154) [S: .specify/workflow-state/issues/150.md#intake-scope-comment]
- Issues #146, #147, #141 and #143 [S: .specify/workflow-state/issues/150.md#intake-scope-comment]
- Changing any runner, validator, skill or workflow code in this feature; the ADR authorizes behavior that later leaves deliver [I]

## Constraints

- An accepted architecture change is made by a new ADR, not by changing code first [S: AGENTS.md]
- A provisional decision is never human approval; merging the PR is the single approval (BL-INV-006), so the ADR must present every in-run decision as agent-provisional [S: .specify/memory/constitution.md]
- An agent never gains more authority than its caller; protected inputs stay fail-closed (BL-INV-003) [S: .specify/memory/constitution.md]
- The change touches agent authority and the launcher trust model and amends accepted ADRs, so it is R2 [S: docs/policies/project/workflow.md#r2-boundaries]
- ADR files follow the existing form: Status, Feature, Amends lines, then Context, Decision, Consequences, Rejected alternatives [S: docs/adr/0016-privileged-action-kinds-and-policy-refresh.md]
- The next free ADR number is 0020 [S: docs/adr/0019-feature-local-ui-states.md]
- No privileged action is needed before merge [S: .specify/workflow-state/issues/150.md#intake-scope-comment]

## Permissions and data authority

- The ADR becomes the authority for the stop rule; the workflow policy and technical spec reference it rather than restating it as a second source of truth [S: AGENTS.md]
- Authority that takes effect before merge (run authority, launcher execution, external writes, credentials) stays with the operator and still blocks a run [S: Issue #150 body]
- Trust in an Issue author must come from operator-controlled data, never from the Issue or an agent-writable file [S: docs/adr/0016-privileged-action-kinds-and-policy-refresh.md]
- The decisions in this run, including the ADR's acceptance, are agent-provisional until the operator merges the PR [S: specs/150-autonomous-stop-rule/autonomous/record.md]

## Success evidence

- `docs/adr/0020-*.md` exists, amends ADR-0004 and ADR-0010, and contains each of the five required elements [S: IAC-1]
- ADR-0004 and ADR-0010 carry a note pointing to the new ADR [S: IAC-1]
- `docs/policies/spec-kit-workflow.md` and `specs/TECHNICAL-SPEC.md` link the new ADR [S: IAC-2]
- The fast gate (ruff and the unittest suite) passes, since documentation tests may check links and ADR form [S: AGENTS.md]

## Edge, failure and permission cases

- A Chat run never records provisional decisions and every gate is human, so the stop rule does not apply to it [S: docs/adr/0009-chat-mode-operator-driven-steps.md]
- `tamper`, `unfinished-step`, `postcondition` and protected-input changes are runner-enforced invariants and keep blocking under the new rule [S: docs/policies/spec-kit-workflow.md#autonomous-runs]
- `credential`, `permission`, `forge` and `ineligible` blocks concern credentials, external writes or run authority and keep blocking [I]
- A limit reached before any spec exists still yields a Draft PR under the assumed limit outcome; every criterion is then `unverified` [P: D-04]
- Too many material decisions concentrate risk at merge; the material-decision cap bounds this [S: Issue #150 body]
- An untrusted Issue author without `ready-for-agent` is still refused as ineligible [I]

## Issue acceptance criteria

- IAC-1: An accepted ADR amends ADR-0004 and ADR-0010 (and ADR-0009 if Chat is affected), and states the stop rule, the trusted-author rule, the limit outcome, self-resume and the residual risk.
- IAC-2: `docs/policies/spec-kit-workflow.md` and `specs/TECHNICAL-SPEC.md` reference it.

## Known

- The stop rule: block only for a decision that takes effect before merge (run authority, launcher execution, external writes, credentials) or a contradiction with a runner-enforced invariant; every other decision is a material provisional decision surfaced at the top of the PR [S: Issue #150 body]
- A trusted-author Issue stands in for the `ready-for-agent` scope approval [S: Issue #150 body]
- The limit block is replaced by a Draft PR whose acceptance packet marks unmet criteria `unverified` [S: Issue #150 body]
- The runner resumes a run stopped by a provider usage limit without an operator `block-resolution` record, amending ADR-0010 [S: Issue #150 body]
- The residual risk is decisions concentrated at merge, mitigated by a material-decision cap [S: Issue #150 body]
- Today eligibility requires `ready-for-agent` and one scope comment by OWNER, MEMBER or COLLABORATOR [S: tools/spec_workflow/autonomy.py]
- Today resume records the operator's `block-resolution` human decision and is the only `stopped` to `active` transition [S: docs/adr/0010-autonomous-resume-and-bounded-recovery.md]
- The acceptance packet has states `verified`, `failed`, `stale`, `not run` and `missing`; there is no `unverified` state yet [S: docs/policies/spec-kit-workflow.md#acceptance-packet]
- Earlier agent-written ADRs are marked accepted with a note that they stay provisional until the operator merges the PR [S: docs/adr/0004-autonomous-provisional-decisions.md]
- This leaf blocks the other leaves of Epic #149 [S: Issue #150 body]

## Inferred

- The ADR can keep BL-INV-006 unchanged, because the rule only moves more decisions to the single merge approval that the invariant already defines [I]
- `unverified` is the ADR's term for any criterion not `verified`; the packet's exact rendering is left to #153 [I]
- ADR-0009 is not amended; the ADR states that Chat runs are unaffected [P: D-02]
- Every `limit` category publishes a Draft PR (agent steps, wall time, fix cycles, draft retries), with open findings and failed checks listed and unmet criteria `unverified` [P: D-04]
- The material-decision cap is a runner-enforced limit; reaching it gets the limit outcome (a Draft PR that says the cap was reached) rather than a mid-run stop; #151/#153 set its default and configuration [P: D-06]

## Undecided

None.

## Decisions

### D-01: How the ADR states its acceptance
- **Status**: settled
- **Question**: IAC-1 asks for an "accepted" ADR, but an Autonomous run cannot record human acceptance; what status line does the ADR carry?
- **Why it matters**: wording that claims a human decision for the ADR before merge breaks BL-INV-006 and fails the approval-wording guard
- **Sources**: [S: .specify/memory/constitution.md] [S: docs/adr/0004-autonomous-provisional-decisions.md]
- **Options**:
  - A — "accepted" status that says it stays agent-provisional until the operator merges the PR, as ADR-0004 does. Consequence: meets IAC-1 once merged without claiming approval
  - B — "proposed" status. Consequence: IAC-1 holds only after a follow-up status edit
- **Recommended default**: A, because it matches repository precedent
- **Answer**:
- **Resolution**: A. ADR-0004's status line is the precedent for an agent-written ADR marked accepted and provisional until merge [S: docs/adr/0004-autonomous-provisional-decisions.md]; the constitution makes the merge the approval [S: .specify/memory/constitution.md].

### D-02: Whether ADR-0009 (Chat) is amended
- **Status**: assumed
- **Question**: Does the stop rule affect Chat runs enough to amend ADR-0009?
- **Why it matters**: decides whether IAC-1's conditional ADR-0009 amendment is in the change
- **Sources**: [S: docs/adr/0009-chat-mode-operator-driven-steps.md] [S: Issue #150 body]
- **Options**:
  - A — Do not amend ADR-0009; the new ADR states that Chat runs are unaffected. Consequence: Chat keeps every human gate
  - B — Add an amendment note to ADR-0009. Consequence: an edit to an ADR whose decision does not change
- **Recommended default**: A, because Chat never records provisional decisions and every Chat gate is a human approval
- **Answer**:
- **Resolution**: A. Safe and reversible: the rule concerns only Autonomous runs, Chat records no provisional decision (ADR-0009), and a later note can be added if a sibling leaf touches Chat.

### D-03: Where trust in an Issue author comes from
- **Status**: settled
- **Question**: What makes an Issue author "trusted" for the rule that replaces `ready-for-agent`?
- **Why it matters**: it is the security boundary for who can dispatch an unattended agent run
- **Sources**: [S: .specify/workflow-state/issues/150.md#intake-scope-comment] [S: docs/adr/0016-privileged-action-kinds-and-policy-refresh.md] [S: tools/spec_workflow/autonomy.py]
- **Options**:
  - A — An author on an operator-controlled intake allowlist, implemented by #152; the ADR states the rule and that trust never comes from agent-writable data. Consequence: the ADR does not fix the list format
  - B — Any OWNER, MEMBER or COLLABORATOR author. Consequence: trust follows repository roles, not an explicit list
- **Recommended default**: A
- **Answer**:
- **Resolution**: A. The intake scope comment assigns the "intake allowlist" to #152 [S: .specify/workflow-state/issues/150.md#intake-scope-comment]; ADR-0016 establishes that authority comes only from operator-trusted configuration [S: docs/adr/0016-privileged-action-kinds-and-policy-refresh.md].

### D-04: Which limits publish instead of blocking
- **Status**: assumed
- **Question**: Does the publish-unverified outcome apply to every `limit` category and to a limit reached before implementation?
- **Why it matters**: decides which blocks the ADR removes
- **Sources**: [S: Issue #150 body] [S: docs/policies/spec-kit-workflow.md#autonomous-runs]
- **Options**:
  - A — Every `limit` category (agent steps, wall time, fix cycles, draft retries), in any phase, publishes a Draft PR with open findings and failed checks listed and unmet criteria `unverified`. Consequence: no limit stops the run for a human
  - B — Only limits after implementation publish; earlier ones still block. Consequence: some runs still stop mid-way
- **Recommended default**: A, because a Draft PR takes no effect before merge and the Issue replaces "the limit block" without exception
- **Answer**:
- **Resolution**: A. Safe and reversible: a Draft PR can't be merged without the human, nothing takes effect before merge, and #153 delivers and can narrow the mechanics.

### D-05: How self-resume is recorded
- **Status**: settled
- **Question**: What does the runner record when it resumes a run stopped by a provider usage limit?
- **Why it matters**: ADR-0010 makes the operator's `block-resolution` the only `stopped` to `active` transition
- **Sources**: [S: Issue #150 body] [S: docs/adr/0010-autonomous-resume-and-bounded-recovery.md]
- **Options**:
  - A — A runner event naming the usage-limit block, never a human decision; mode, risk, limits and integrations unchanged; mechanics in #154. Consequence: ADR-0010 is amended for this one block cause
  - B — Keep requiring the operator record. Consequence: contradicts the Issue
- **Recommended default**: A
- **Answer**:
- **Resolution**: A. The Issue asks for resume "without an operator `block-resolution` record (amends ADR-0010)" [S: Issue #150 body]; BL-INV-006 forbids recording it as a human decision [S: .specify/memory/constitution.md].

### D-06: The material-decision cap's outcome and value
- **Status**: assumed
- **Question**: What happens when a run reaches the material-decision cap, and does the ADR fix its value?
- **Why it matters**: decides whether the mitigation adds a mid-run stop
- **Sources**: [S: Issue #150 body] [S: .specify/workflow-state/issues/150.md#intake-scope-comment]
- **Options**:
  - A — The cap is a runner-enforced limit and gets the limit outcome: the run publishes a Draft PR stating the cap was reached; #151/#153 set the default and configuration. Consequence: no new human stop
  - B — Reaching the cap blocks the run for a human. Consequence: adds a mid-run stop the Issue wants removed
- **Recommended default**: A, because it follows the Issue's own limit outcome
- **Answer**:
- **Resolution**: A. Safe and reversible: the ADR is a document that the merge reviewer reads, the value can be tuned in #151/#153, and the Draft PR still needs the human merge.

### D-07: Whether the constitution needs an amendment
- **Status**: settled
- **Question**: Does the stop rule weaken a constitutional invariant and so need a constitution amendment?
- **Why it matters**: an invariant change needs its own R2 amendment and history entry
- **Sources**: [S: .specify/memory/constitution.md]
- **Options**:
  - A — No amendment; BL-INV-003 and BL-INV-006 are kept unchanged. Consequence: only ADRs and references change
  - B — Amend BL-INV-006. Consequence: a broader change outside the Issue's scope
- **Recommended default**: A
- **Answer**:
- **Resolution**: A. BL-INV-006 already lets agents decide wherever a human-gated run asks and makes the merge the single approval; pre-merge authority still blocks, so BL-INV-003 is untouched [S: .specify/memory/constitution.md].

## Question metrics

- **Rounds**: 0
- **Questions asked**: 0
- **Assumptions adopted**: 3

## Changes

- 2026-10-13: reworded the BL-INV-006 constraint and D-01's "Why it matters" after the recorder refused the earlier wording as an approval claim; no decision changed.
