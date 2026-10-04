# Feature Specification: Autonomous run core

**Feature Branch**: `feat-autonomous-core`

**Created**: 2026-10-03

**Status**: Draft

**Input**: User description: "Issue #27: An operator can run an eligible feature (R0, R1 or R2) from scoped issue to Draft PR without any human approval prompt; every intermediate decision is recorded as provisional and the human approves once, at merge."

**Risk**: R2. This feature changes who may decide at the workflow's approval gates, which is part of the launcher's trust model and the headless-agent authority model (see `docs/policies/project/workflow.md`). Its intent and merge both need explicit human approval. It is specified and delivered under the current human-gated workflow, not under the mode it introduces.

**Source context**: [roadmap Priority 4](../../docs/plans/2026-10-02-product-roadmap.md#priority-4--let-the-operator-choose-the-level-of-supervision), [technical spec §91](../TECHNICAL-SPEC.md#91-v10-target). [Issue #27](https://github.com/Hugo-Grellier/ballast/issues/27), split from #21 by operator decision on #11. Out of scope per #27: automatic merge, deployment, destructive external actions, discovery (#16), the full review packet (#19), safe Autonomous resume (#18), bounded fix loops (#21 remainder), and changes to the human-gated behavior.

## Overview

Today every feature run stops at seven human gates: scope, intent, plan, tasks, implementation review, spec reconciliation and final acceptance. Autonomous mode lets the operator start an eligible feature once and receive a reviewed Draft PR, with no approval prompt in between. Agents still decide at each gate, but each decision is recorded as **provisional**: the decision, its basis and the evidence behind it. Nothing presents a provisional decision as human-approved. The human approves once, at merge, after seeing the complete decision history. Autonomous changes who decides at the intermediate gates and when. It does not skip checks, reviews, postconditions, the trust boundary or the merge decision.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Run an eligible feature to a Draft PR unattended (Priority: P1)

An operator has a scoped leaf Issue and wants to reach a reviewable Draft PR without supervising each phase. They start a run in Autonomous mode. The workflow goes through specification, clarification, intent, plan, independent plan review, tasks, implementation, independent implementation review, decision reconciliation, convergence and final evidence. It never asks for a human approval. Each gate decision is recorded as provisional, and the run ends with a Draft PR and the record of every decision.

**Why this priority**: This is the feature's promise and the Ballast 1.0 exit evidence for Autonomous. Without it, no other story is useful.

**Independent Test**: Start an Autonomous run on a small eligible R1 test feature in a scratch repository. Confirm it reaches a Draft PR without stopping for input, and that every gate the human-gated workflow would have shown appears in the record as a provisional decision.

**Acceptance Scenarios**:

1. **AC-001**: **Given** a trusted checkout and an eligible scoped Issue, **When** the operator starts the feature run in Autonomous mode, **Then** the run reaches a Draft PR for that Issue without any human approval prompt.
2. **AC-002**: **Given** an Autonomous run, **When** it passes any point where the human-gated workflow requires approval (scope, intent, plan, tasks, implementation review, spec reconciliation, final acceptance), **Then** it records a provisional decision for that gate, with the deciding agent's identity, the decision, its basis and links to the evidence.
3. **AC-003**: **Given** an Autonomous run, **When** any phase finishes, **Then** the same artifact postconditions as in the human-gated workflow are enforced, and a failed postcondition stops the run exactly as it does today.
4. **AC-004**: **Given** an Autonomous run that reaches plan review, implementation review and spec reconciliation, **When** each review runs, **Then** it runs in a context separate from the author's, its reviewer identity is recorded, a high or critical finding blocks the run, and other material findings are recorded as provisional dispositions.
5. **AC-005**: **Given** an Autonomous run where the spec has an open clarification question, **When** a safe and reversible default exists, **Then** the agent adopts it as a recorded provisional assumption instead of asking the operator, and the clarified spec contains no unresolved marker.

---

### User Story 2 - Review every provisional decision once, at merge (Priority: P1)

The human reviewer opens the Draft PR from an Autonomous run. In one place they see every provisional decision: adopted assumptions, intent, plan and task acceptance, review dispositions, accepted discoveries and the final convergence verdict. Each decision links to its evidence and is clearly labeled provisional. The reviewer either merges, which is the single human approval, or requests changes.

**Why this priority**: A provisional decision is acceptable only because a human sees it before merge. If decisions are hidden or blurred with human approvals, the autonomy is unsafe.

**Independent Test**: Inspect the PR from a completed Autonomous run. Check that the decision count in the PR matches the run's record, that each decision is labeled provisional and links to its evidence, and that no artifact or PR text claims a human approval that did not happen.

**Acceptance Scenarios**:

1. **AC-006**: **Given** a completed Autonomous run, **When** the human opens its Draft PR, **Then** the PR shows the run's mode, the feature's risk level and the complete list of provisional decisions, each linked to its basis and evidence.
2. **AC-007**: **Given** any artifact, record or PR text produced by an Autonomous run, **When** it describes a gate decision, **Then** it says the decision is agent-provisional and never states or implies human approval.
3. **AC-008**: **Given** a provisional intent record, **When** the spec changes after that record is made, **Then** the record becomes stale exactly as a human approval does today, and the run cannot proceed on it.
4. **AC-009**: **Given** an Autonomous Draft PR, **When** the reviewer requests changes instead of merging, **Then** the reviewer's feedback can be recorded as a human decision, and work continues from that feedback in the human-gated mode without losing or rewriting earlier provisional decisions.
5. **AC-010**: **Given** an Autonomous run, **When** it finishes, **Then** no step merges the PR, marks it ready on the human's behalf, releases, deploys or performs a destructive external action.

---

### User Story 3 - Stop with a precise block instead of guessing (Priority: P1)

Some situations cannot be decided safely by an agent: an unresolved product contradiction, a missing decision with no safe default, a technical failure, an exhausted limit or unavailable authority. In these cases an Autonomous run stops and reports exactly what blocked it and what the operator can do next. It does not pause on an approval prompt, retry forever or invent a decision.

**Why this priority**: The single-approval promise is safe only if the alternative to a doubtful decision is an explicit stop, not a silent assumption (technical spec §96).

**Independent Test**: Run the scratch feature under each blocking condition: an unresolvable clarification, an unresolved high review finding, a tampered protected input, an exceeded time limit. Check that each stops before the next agent step, with a named block reason and a recovery action, and that no approval prompt appears.

**Acceptance Scenarios**:

1. **AC-011**: **Given** an Autonomous run that meets a decision with no safe, reversible default (contradictory requirements, ambiguous product behavior with materially different outcomes, an irreversible choice), **When** the agent reaches it, **Then** the run stops with a block that names the decision, the options and their consequences, and records no provisional decision for it.
2. **AC-012**: **Given** an Autonomous run, **When** the run exceeds its declared wall-time or attempt limit, **Then** the run stops with a block that names the exhausted limit, and keeps the evidence gathered so far.
3. **AC-013**: **Given** an Autonomous run, **When** a protected input changes, an agent step stays unfinished, or the trust baseline no longer matches, **Then** the run refuses exactly as a human-gated run does today, and Autonomous mode adds no way to continue past it.
4. **AC-014**: **Given** an Autonomous run that stopped on a block, **When** the operator resolves the cause, **Then** the operator can continue only by switching the run to the human-gated mode or starting a new run; an Autonomous `resume` is refused with a reason that names the missing safe-resume support (#18), and the resolution is recorded as a human decision.

---

### User Story 4 - Choose the mode and keep it out of agent reach (Priority: P2)

The operator chooses Autonomous or the existing human-gated mode for each run. The choice is recorded with the run and fixed at start; the only change allowed is a trusted operator action that lowers a paused Autonomous run to the human-gated mode. An agent cannot select, raise or fake the mode, and a mode change never hides an earlier decision or erases an earlier refusal.

**Why this priority**: The mode grants the authority to decide at gates. If an agent could set it, the mode would bypass delegated authority (BL-INV-003).

**Independent Test**: Try to change the mode from inside an agent step, by editing files the agent can write. Check that the run's effective mode does not change. Then lower a paused Autonomous run to the human-gated mode through the trusted operator path and confirm both the change and all earlier decisions appear in the record. Confirm that raising a paused human-gated run to Autonomous is refused.

**Acceptance Scenarios**:

1. **AC-015**: **Given** a run start, **When** the operator selects a mode, **Then** the mode is recorded with the run outside agent-writable state, and a run started without a mode uses the existing human-gated behavior.
2. **AC-016**: **Given** a running or paused run, **When** an agent writes anything it can write in the checkout, **Then** the run's effective mode and eligibility do not change.
3. **AC-017**: **Given** a paused Autonomous run, **When** the operator switches it to the human-gated mode through the trusted operator path, **Then** the change is recorded with its time, the remaining gates prompt for human approval, and the decisions already recorded stay visibly provisional.

---

### User Story 5 - Refuse ineligible features up front (Priority: P2)

Before any agent works on the feature, the operator learns whether the feature can run autonomously. A feature that is not a scoped leaf Issue, or that needs a privileged action before merge, is refused for Autonomous with a reason. The operator can still run it in the human-gated mode. A project can narrow eligibility (for example, exclude R2) but cannot widen it beyond this standard.

**Why this priority**: Eligibility limits what an unattended run can reach. Checking it before work starts avoids a run that can only end in a block.

**Independent Test**: Start Autonomous runs for an Epic, for a feature that declares a pre-merge privileged action, and for an R2 feature in a project whose policy excludes R2. Each must be refused before the first agent step, with its reason. An eligible R0 feature must be accepted.

**Acceptance Scenarios**:

1. **AC-018**: **Given** a scoped leaf Issue with risk R0, R1 or R2 and no pre-merge privileged action, **When** the operator starts an Autonomous run, **Then** the run is accepted as eligible, and its risk level is recorded.
2. **AC-019**: **Given** an Epic or an Issue that fails the scope gate, **When** the operator starts an Autonomous run, **Then** it is refused before any agent step and the refusal names the scope-gate reason.
3. **AC-020**: **Given** a feature that needs a privileged action before merge (deployment, release, writing to an external authoritative system, secret provisioning, changing CI or repository permissions outside the PR diff), **When** the operator starts an Autonomous run, **Then** it is refused unless a project policy explicitly authorizes that action.
4. **AC-021**: **Given** a project policy that narrows Autonomous eligibility, **When** a feature falls outside it, **Then** the run is refused. **Given** a project policy that claims to widen eligibility beyond this standard, **When** a run starts, **Then** the wider setting is ignored and the refusal or warning says so.
5. **AC-022**: **Given** an Autonomous run whose implementation shows that the change needs a higher risk level than recorded, **When** the risk is raised during the run, **Then** eligibility is checked again and the run stops with a block if the new level is not eligible.

---

### User Story 6 - Keep R2 safeguards when the R2 approval moves to merge (Priority: P2)

For an R2 feature, today's policy requires human approval both before the risky change and before merge. In Autonomous, the first approval becomes a provisional decision. The R2-specific safeguards stay in force: required specialist reviews, a block on unresolved high or critical findings, and a prominent R2 notice at merge that lists the R2 boundaries touched.

**Why this priority**: Issue #27 includes R2. Moving the pre-change approval to merge is acceptable only if the merge reviewer sees exactly what risky change they are approving, backed by the same specialist evidence.

**Independent Test**: Run an R2 scratch feature that touches a security boundary in Autonomous. Confirm that the security review ran and was recorded, that an injected unresolved high finding blocks the run, and that the PR lists the R2 boundaries and that the pre-change approval was provisional.

**Acceptance Scenarios**:

1. **AC-023**: **Given** an Autonomous R2 run, **When** it reaches implementation review, **Then** every specialist review required by the review matrix for the touched boundaries runs and is recorded before the run may finish.
2. **AC-024**: **Given** an Autonomous run of any risk level, **When** a review leaves an unresolved finding of high or critical severity, **Then** the run cannot record a provisional acceptance over it and stops with a block.
3. **AC-025**: **Given** a completed Autonomous R2 run, **When** the human opens the Draft PR, **Then** the PR states that the feature is R2, lists the R2 boundaries it touches, and states that the risky change was made without any prior human approval.

---

### Edge Cases

- **Only one model provider is available**: Reviews still run in a separate context. The record states that the review was not cross-provider, and the PR shows that reduced independence.
- **The Draft PR cannot be created or updated** (authentication, network, forge refusal): The run reports a retryable block. The branch and decision record are kept, and nothing is reported as published.
- **The run is interrupted** (Ctrl-C, reboot, killed agent): Existing unfinished-step and tamper refusals apply. Provisional decisions already recorded are kept. A partly recorded decision is not treated as complete.
- **An agent tries to write a human-approval record**, for example by forging the approval block in `intent.md`: In an Autonomous run, validation refuses the record: an Autonomous run accepts only provisional records. Human-gated runs keep today's checks; their hardening is #29.
- **A provisional decision later conflicts with new evidence**: The decision is superseded by a new provisional decision that references it. The original is never edited away.
- **A provisional decision is carried to a human-gated phase or a later feature**: Before merge it counts as not approved. After the PR containing it is merged, the merge is its acceptance.
- **Base branch advanced during the run**: This feature does not add branch synchronization. Behavior is as in today's workflow, and any synchronization is owned by the separate synchronization feature.
- **Clarification produces several independent outcomes**: The run blocks and recommends decomposition. It does not provisionally split the Issue or create child Issues.

## Requirements *(mandatory)*

### Functional Requirements

**Mode and authority**

- **FR-001**: The operator MUST be able to select, per run, either the existing human-gated mode or Autonomous mode when starting a feature run. Without an explicit selection, the run MUST use the human-gated mode.
- **FR-002**: The selected mode and every later change to it MUST be recorded with the run, in state that agent steps cannot write, together with who changed it and when.
- **FR-003**: Only a trusted operator action MAY select a run's mode at start or lower a paused Autonomous run to the human-gated mode. Raising a run's autonomy after start MUST be refused. No artifact, file or output an agent can write MAY change the effective mode, eligibility or limits.
- **FR-004**: A mode change MUST NOT alter, hide or reclassify a decision or refusal recorded before the change.

**Eligibility**

- **FR-005**: Autonomous mode MUST be available for a scoped leaf Issue with risk R0, R1 or R2. Eligibility MUST be checked before the first agent step and checked again whenever the recorded risk level rises.
- **FR-006**: A feature that needs a privileged action before merge MUST be ineligible unless a project policy explicitly authorizes that action. Privileged actions include deployment, release, merge, marking the PR ready, writes to external authoritative systems, secret provisioning, and repository or CI permission changes outside the PR diff. Deployment, release, merge and marking the PR ready can never be authorized (FR-027), so a feature that needs one before merge is always ineligible.
- **FR-007**: A project policy MAY narrow Autonomous eligibility by risk level or by boundary. It MUST NOT widen eligibility beyond this standard.
- **FR-008**: An ineligible start MUST be refused before any agent step, with the reason and with the human-gated mode named as the alternative.

**Provisional decisions**

- **FR-009**: In Autonomous mode, every point where the human-gated workflow requires a human approval or resolution MUST instead produce a provisional decision record. This covers the scope gate, clarification answers, intent, plan, tasks, implementation review, decision resolutions, spec reconciliation and final acceptance.
- **FR-010**: Each provisional decision record MUST include: the gate or decision point, the decision, its basis, links to the evidence, the deciding agent's identity (provider, model and role), the artifact version it applies to, and the time.
- **FR-011**: A provisional decision MUST be distinguishable from a human approval in every artifact, record and PR text, and MUST never be labeled or counted as human approval. In an Autonomous run, validators MUST reject every human-approval record; human approvals are written only by a gate after the operator lowers the run to the human-gated mode. Hardening human-gated runs against forged approvals is out of scope (#29).
- **FR-012**: A provisional intent decision MUST be bound to the exact spec version it accepts, and MUST become stale on any later spec change, as a human intent approval does.
- **FR-013**: Provisional decisions MUST be append-only within a run. A superseding decision MUST reference the one it replaces.
- **FR-014**: The feature's durable artifacts MUST state the run's mode, so that a later reader knows whether gate decisions were human or provisional. A provisional decision becomes accepted only when a human merges the PR that contains it.

**Autonomous progression**

- **FR-015**: Autonomous mode MUST enforce every artifact postcondition, deterministic check, trust verification and tamper refusal that the human-gated workflow enforces, without weakening any of them.
- **FR-016**: Autonomous mode MUST run the independent reviews that the human-gated workflow currently leaves to the operator (plan review, implementation review, spec reconciliation) and the specialist reviews required by the review matrix. Each runs in a context separate from the author's, preferring a different provider when one is available.
- **FR-017**: When clarification finds an open question, the agent MUST adopt a safe, reversible default as a provisional assumption when one exists. Otherwise it MUST block. It MUST NOT leave the question for a human to answer at a prompt during the run.
- **FR-018**: An implementation discovery that the human-gated workflow sends to a human resolution MUST receive a provisional resolution in Autonomous mode. A discovery that changes product behavior, scope, data authority, a security boundary or accepted architecture MUST also appear in the merge-review summary as a material provisional change.
- **FR-019**: A review finding of high or critical severity MUST block the run. It MUST NOT be accepted provisionally, and this feature adds no automatic fix loop (bounded fix loops are owned by #21). A medium finding MAY be accepted provisionally only with a recorded reason.
- **FR-020**: Each Autonomous run MUST have a declared wall-time limit and attempt limit, recorded with the run, set by the operator or by a project default. An agent MUST NOT be able to raise them.

**Blocking**

- **FR-021**: An Autonomous run MUST stop with an explicit block, not an approval prompt, on any of: a decision without a safe default, contradictory requirements, an exhausted limit, a technical or postcondition failure, an unavailable permission or credential, an ineligibility discovered during the run, or a forge failure that prevents publishing.
- **FR-022**: Each block MUST name its reason, the decision or condition involved, the options or recovery action, and the recovery command. All evidence gathered so far MUST be kept.
- **FR-023**: When the operator resolves a block, the resolution MUST be recorded as a human decision. Resuming an Autonomous run MUST be refused until safe Autonomous resume (#18) exists; the operator continues in the human-gated mode or starts a new run.

**Draft PR and merge review**

- **FR-024**: A completed Autonomous run MUST end with one Draft PR linked to the Issue, created by the run, whose body carries the merge-review summary. Reusing an existing PR, shared issue/branch/PR identity and duplicate prevention are owned by the Draft-PR lifecycle feature (#17).
- **FR-025**: The Draft PR MUST show the run mode, the risk level, every provisional decision with links to its basis and evidence, the checks run and skipped, review identities and verdicts, open lower-severity findings, and which decisions are material provisional changes.
- **FR-026**: For an R2 feature, the Draft PR MUST state the R2 level, list the R2 boundaries touched, and state that the pre-change approval was provisional.
- **FR-027**: No Autonomous step MAY merge the PR, mark it ready for review on the human's behalf, release, deploy or perform a destructive external action. The human merge decision remains the single approval and the final gate.
- **FR-028**: When the merge reviewer requests changes, their feedback MUST be recordable as a human decision, and the operator MUST be able to continue from that feedback in the human-gated mode.

**Governance**

- **FR-029**: The shipped workflow policy, risk policy and agent instructions MUST be amended to describe Autonomous mode. In particular, they MUST say that, for an eligible Autonomous run, intermediate approvals are provisional and the merge decision is the single human approval, including for R2. The human-gated mode's approvals MUST stay unchanged.
- **FR-030**: Any constitution or architecture text that the amended governance contradicts MUST be updated in the same change, with the reason and the compatibility impact for projects pinning earlier versions.

### Key Entities

- **Run mode**: The operator-chosen supervision setting of one run (human-gated or Autonomous). It has a history of changes, and each change records who made it and when.
- **Eligibility result**: The outcome of checking a feature against the scope gate, its risk level, any pre-merge privileged actions and the project's narrowing policy. It records the reasons.
- **Provisional decision**: An agent's decision at a point that would otherwise need a human. It has a decision point, decision, basis, evidence links, deciding agent identity, artifact version and time, and can be superseded.
- **Block**: A stop of an Autonomous run. It has a reason category, the condition involved, options or recovery, a resume command and kept evidence.
- **Human decision**: A human action recorded against a run: a mode change, the resolution of a block, review feedback at merge, or the merge itself.
- **Merge-review summary**: The view in the Draft PR that lists mode, risk, all provisional decisions, evidence, reviews and open findings, for the single human approval.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An eligible R1 feature goes from a scoped Issue to a Draft PR in Autonomous mode with zero human approval prompts. The only human approval in its history is the merge decision.
- **SC-002**: In 100% of Autonomous runs, every gate the human-gated workflow would have shown has exactly one current provisional decision or block in the run's record, and the Draft PR lists the same decisions.
- **SC-003**: Zero artifacts, records or PR texts from Autonomous runs claim or imply human approval of a decision a human did not make. This is checked by the test suite and on every pilot run.
- **SC-004**: Every listed blocking condition (no safe default, contradiction, unresolved high or critical finding, exceeded limit, tamper, unfinished step, unavailable permission, ineligibility, forge failure) stops the run before the next agent step, with a named reason and recovery action. Each condition is covered by a test that fails if the stop is removed.
- **SC-005**: No attempt from inside an agent step to change the mode, the eligibility, the limits or a human-approval record changes the run's effective behavior. Each such attempt is covered by a test.
- **SC-006**: A merge reviewer can list every provisional decision of an Autonomous run, and every material one, from the Draft PR alone, without opening the run's local logs.
- **SC-007**: A human-gated run started after this feature shows the same gates and approvals as before it. The existing workflow tests keep passing unchanged.

## Assumptions

- Issue #27's statement that R0, R1 and R2 are all eligible is the decision of record. It goes beyond the roadmap's R1 pilot target. For R2, the pre-change approval becomes provisional and the merge approval stays human; the R2 safeguards in User Story 6 apply.
- The roadmap's other modes (Chat, Guided, Supervised) are not part of this feature. "Human-gated mode" means today's workflow behavior; Chat's interactive entry point is a separate feature.
- Branch synchronization before start and resume, the reusable Draft PR lifecycle, the review packet's richer projections (API, UI, demo) and provider fallback are separate roadmap features. This feature uses them when they exist and does not implement them; FR-024 creates one Draft PR without the #17 lifecycle.
- Spend or cost limits are not enforced, because reliable usage data is not available today. Wall time and attempt counts are the declared limits.
- Run-local agent logs stay local and are never attached to the PR. The PR carries the decision record and links to committed artifacts only.
- The qualified environment is GitHub on Linux with a systemd user session, as for Ballast 1.0.
- Autonomous `resume` is refused until safe resume (#18) exists; a blocked or changes-requested run continues in the human-gated mode.
- A provisional decision does not need to be rewritten as "accepted" after merge. The merged PR is the acceptance evidence.
