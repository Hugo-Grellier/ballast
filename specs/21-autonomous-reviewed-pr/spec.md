# Feature Specification: Reach a reviewed PR with provisional Autonomous decisions

**Feature Branch**: `feat/21-autonomous-reviewed-pr`

**Created**: 2026-10-06

**Status**: Draft

**Input**: Issue #21: Autonomous integrates discovery, the full review packet and safe resume, so an eligible feature reaches a reviewed Draft PR and can pause and resume without prompts; the human decides at merge. Written from the discovery brief [discovery.md](discovery.md); the brief stays input evidence and this spec is the authority.

**Risk**: R2 (agent authority and approval gates). In this Autonomous run every intermediate decision is agent-provisional; merging the PR is the single human decision.

## User Scenarios & Testing *(mandatory)*

The operator starts a scoped, eligible Issue with `ballast run start --mode autonomous` and reviews only at merge. Today 3 of 4 recent Autonomous runs ended in a block that cannot be resumed, the workflow has no fix step after implementation review, and a finished run's acceptance packet can never be refreshed. This feature closes those gaps without widening agent authority or weakening any check.

### User Story 1 - A bounded feature reaches a reviewed Draft PR without prompts (Priority: P1)

The operator starts an eligible R1 feature in Autonomous. The run discovers, specifies, plans, implements, gets an independent review, fixes findings within a bounded loop, runs the trusted checks and opens a Draft PR whose record and acceptance packet show every provisional decision. No approval prompt appears before the operator decides at merge.

**Why this priority**: It is the Issue's main outcome; without a review and fix loop an Autonomous PR is not "reviewed".

**Independent Test**: Run the Autonomous workflow on a bounded R1 fixture feature whose implementation review returns a medium finding; the run performs one fix cycle, passes `run-checks` and publishes a Draft PR, with no approval prompt and a complete packet.

**Acceptance Scenarios**:

1. **AC-001**: **Given** an eligible R1 feature started in Autonomous, **When** the run completes, **Then** it publishes a Draft PR that passed an independent implementation review, the trusted checks and every postcondition, and no human approval prompt appeared before merge. [S: IAC-1] [S: Issue #21 body]
2. **AC-002**: **Given** an implementation review that reports a finding, **When** the run continues, **Then** a fix step addresses it and the trusted checks and the review run again, for at most three fix cycles. [S: IAC-1] [B: D-03] [S: docs/policies/workflow.md]
3. **AC-003**: **Given** a high or critical finding still open after the third fix cycle, **When** the loop ends, **Then** the run blocks as exhausted limits with the finding and the recovery named, and never publishes the finding as provisionally passed. [S: IAC-3] [B: D-03] [S: specs/27-autonomous-core/spec.md]
4. **AC-004**: **Given** a published Autonomous run, **When** the operator opens its Draft PR, **Then** the run record and the acceptance packet list every provisional decision with its basis and evidence, every review with its findings and dispositions, and the `run-checks` result. [S: IAC-2] [S: specs/19-acceptance-packet/decisions.md#dec-0002--resolution]
5. **AC-005**: **Given** a run in Autonomous, **When** any check, required security review, validator or postcondition applies to its change, **Then** it runs exactly as in a human-gated run; choosing the mode skips none of them. [S: IAC-2] [S: .specify/memory/constitution.md]
6. **AC-006**: **Given** the implement or fix agent cannot run the `[checks]` commands itself, **When** checks matter to a fix, **Then** their results reach the fix loop only through the trusted `run-checks` step, and the headless agent's permissions are unchanged. [S: IAC-2] [P: D-08]
7. **AC-007**: **Given** an Autonomous run, **When** it records provisional intent, **Then** the intent cites the discovery brief and the spec traced to it, and the record marks it agent-provisional. [S: IAC-4] [S: Issue #21 body]

---

### User Story 2 - A paused or blocked Autonomous run resumes safely (Priority: P1)

A run blocks, before or after implementation, or is interrupted. The operator resolves the cause and runs `ballast run resume RUN_ID`. The trusted launcher synchronizes the branch with the base, records the operator's block resolution and continues Autonomous from the blocked step, without prompts and without any new authority.

**Why this priority**: Most recent Autonomous runs ended in a block that could not be resumed; resume is the "safe resume" part of the outcome.

**Independent Test**: Block a fixture run at a pre-implementation step and another after implementation, advance the base, then resume each; both synchronize, record a block resolution and reach the next step in Autonomous.

**Acceptance Scenarios**:

1. **AC-008**: **Given** an Autonomous run blocked before implementation (for example at `decide-tasks`) and the cause resolved, **When** the operator runs `ballast run resume RUN_ID`, **Then** the run synchronizes its branch and continues Autonomous from the blocked step, running the remaining agent steps. [S: IAC-3] [B: D-01] [P: D-04] [S: Issue comment Hugo-Grellier 2026-10-05T20:44:26Z]
2. **AC-009**: **Given** an Autonomous run blocked after implementation, **When** the operator resumes it after the base advanced, **Then** branch synchronization runs in the trusted launcher before any agent step, and the run continues Autonomous or blocks with an actionable reason. [S: IAC-3] [B: D-01] [S: docs/adr/0005-launcher-branch-synchronization.md]
3. **AC-010**: **Given** a blocked Autonomous run, **When** the operator resumes it, **Then** the trusted command records the resolution as a human decision of kind `block-resolution`, and the run record shows it. [S: IAC-2] [B: D-02] [S: specs/27-autonomous-core/spec.md]
4. **AC-011**: **Given** a pre-implementation block, **When** the operator runs `ballast run continue`, **Then** it refuses with a reason that points to `ballast run resume`, and `continue` of a post-implementation block behaves as before. [S: IAC-3] [P: D-04]
5. **AC-012**: **Given** a spec or plan fixed during a block invalidates a record made earlier in the run, **When** the run resumes, **Then** it re-enters at the earliest step whose recorded input changed, so no stale intent or baseline is trusted. [S: IAC-3] [S: Issue comment Hugo-Grellier 2026-10-05T20:44:26Z] [I]
6. **AC-013**: **Given** a protected input (`ballast.toml`, `.ballast/`, `.specify/`, `.venv/`) changed during the pause or the synchronization, **When** the run resumes, **Then** it fails closed before any agent step and names `ballast trust` as the operator's recovery. [S: IAC-3] [S: docs/adr/0005-launcher-branch-synchronization.md]
7. **AC-014**: **Given** a run started before branch pinning, whose pin has only `branch`, **When** it is resumed, **Then** it blocks as `wrong-branch` with a recovery that states the documented manual operator step, and nothing writes the pin from agent-writable inputs. [S: IAC-3] [P: D-12] [S: Issue comment Hugo-Grellier 2026-10-05T22:07:09Z]
8. **AC-015**: **Given** a run lowered to a continuation run by `continue`, **When** the operator runs `ballast run resume` on the original run, **Then** it is still refused with a pointer to the continuation run. [S: IAC-3] [S: tools/spec_workflow/run.py]
9. **AC-016**: **Given** a resumed Autonomous run, **When** it continues, **Then** its mode, risk and limits are those recorded at start; resume can neither raise a limit nor change the mode, and a mode change needs a trusted operator action. [S: IAC-3] [P: D-09] [S: docs/adr/0004-autonomous-provisional-decisions.md]

---

### User Story 3 - A correctable agent-output error does not end the run (Priority: P2)

A trusted recorder refuses an agent draft for a reason the agent can correct in its own text, such as a finding reason over the length limit or wording that claims a human approval. Instead of ending the run, the agent step reruns with the validator's message, within a small bound.

**Why this priority**: Such errors ended several pilot runs; the fix keeps every validator at its current strength.

**Independent Test**: Feed the review recorder a draft with a finding reason over 1000 characters; the step reruns with the validator message, and a second valid draft is recorded. Repeat with a draft that keeps failing; the run blocks once the retries are exhausted.

**Acceptance Scenarios**:

1. **AC-017**: **Given** a recorder refuses an agent draft for a correctable format or length reason, **When** the refusal happens, **Then** the agent step reruns with the validator's message, at most twice per step, each rerun counting against the agent-step limit. [S: IAC-3] [P: D-05] [S: Issue comment Hugo-Grellier 2026-10-05T22:13:34Z]
2. **AC-018**: **Given** a correctable refusal persists after the retries, or the agent-step limit is reached, **When** the next retry would run, **Then** the run blocks as exhausted limits with the last validator message as its reason. [S: IAC-3] [P: D-05]
3. **AC-019**: **Given** a refusal about state outside the draft (a protected input change, an open high or critical finding, a contradiction with accepted intent, missing authority), **When** it happens, **Then** the run blocks as before and no retry is attempted. [S: IAC-3] [P: D-05]
4. **AC-020**: **Given** an agent draft whose basis claims a human approval for the decision, including a quotation of an approval recorded elsewhere, **When** the recorder checks it, **Then** the guard still refuses it and the step is retried under the same bound; the decide and review commands tell the agent to paraphrase and cite such a source. [S: IAC-4] [P: D-06] [S: Issue comment Hugo-Grellier 2026-10-05T23:00:38Z]
5. **AC-021**: **Given** the review and decide commands, **When** an agent reads them, **Then** they state the length limits the recorder enforces. [S: IAC-3] [P: D-05]
6. **AC-022**: **Given** a feature's `tasks.md` generated from the installed tasks template, **When** `validate-implementation` checks it, **Then** it contains no task for steps the workflow runs itself (full gate, quickstart runs, reviews, converge, reconciliation), and the implementation check is unchanged. [S: IAC-3] [P: D-07] [S: Issue comment Hugo-Grellier 2026-10-05T21:06:09Z]

---

### User Story 4 - The operator refreshes a finished run's packet (Priority: P2)

After a run is published, the operator records new evidence (for example `ballast ledger check`) and refreshes the Draft PR checkpoint and acceptance packet without starting an agent.

**Why this priority**: Without it, evidence recorded after publication never reaches the PR the human decides on.

**Independent Test**: Publish a fixture run, add ledger evidence, run the refresh entry point; the Draft PR checkpoint and packet include the new evidence, no agent ran and the decision log is byte-identical.

**Acceptance Scenarios**:

1. **AC-023**: **Given** an Autonomous run in any status with a Draft PR, including `published`, **When** the operator runs `ballast run checkpoint RUN_ID`, **Then** the Draft PR checkpoint and the acceptance packet are refreshed from the current records, and no agent step runs. [S: IAC-2] [P: D-11] [S: specs/19-acceptance-packet/decisions.md#dec-0002--resolution]
2. **AC-024**: **Given** a refresh, **When** it completes, **Then** the run's decision log, mode and status are unchanged. [S: IAC-4] [P: D-11]
3. **AC-025**: **Given** a run with no Draft PR yet, **When** the operator runs the refresh, **Then** it refuses with an actionable reason and writes nothing. [S: IAC-3] [P: D-11]

---

### User Story 5 - Limits and blocks are bounded and actionable (Priority: P2)

Every Autonomous run is bounded in wall time, attempts and spend, and every stop explains what happened and what the operator can do next.

**Why this priority**: Unattended runs need hard bounds and stops a human can act on.

**Independent Test**: Drive fixture runs into each block category and check the recorded reason and recovery; pause a run across a simulated long gap and resume it within its active-time budget.

**Acceptance Scenarios**:

1. **AC-026**: **Given** each block category (conflict with accepted intent, missing authority, exhausted limits, unsafe uncertainty), **When** a run hits it, **Then** it stops with a reason naming the cause and the operator's next action. [S: IAC-3]
2. **AC-027**: **Given** a run paused between invocations, **When** it resumes, **Then** the wall-time limit counts only time spent inside invocations, and each invocation still stops when the recorded limit is reached. [S: IAC-3] [P: D-09]
3. **AC-028**: **Given** a run, **When** it executes agent steps, **Then** every step, retry and fix cycle counts against the agent-step limit, which is the attempt and spend bound, and the run record states that monetary spend is not measured. [S: IAC-2] [P: D-10]
4. **AC-029**: **Given** any trusted command other than an explicit operator mode action, **When** it runs, **Then** it cannot raise a run to Autonomous or change its mode, and an attempt is refused with an actionable reason. [S: IAC-3] [S: docs/adr/0004-autonomous-provisional-decisions.md]

---

### User Story 6 - Provisional stays distinguishable from accepted (Priority: P3)

Policies, templates and workflow state keep agent-provisional decisions visibly distinct from human-accepted ones, and the merge stays the only human approval. The human-gated workflow keeps its gates.

**Why this priority**: It protects the invariant that a provisional decision is never human approval; most of it exists from #27 and must hold through the new paths.

**Independent Test**: Run the validators against an artifact that presents a provisional decision as accepted, and run the human-gated workflow tests unchanged.

**Acceptance Scenarios**:

1. **AC-030**: **Given** an artifact produced by any new or changed path (fix step, retry, resume, refresh), **When** a validator reads it, **Then** it refuses any artifact that presents a provisional decision as accepted or as a human approval. [S: IAC-4] [S: .specify/memory/constitution.md]
2. **AC-031**: **Given** the policies and templates Ballast installs, **When** a reader looks up Autonomous resume, the fix loop, retries and refresh, **Then** they describe each as agent-provisional and state that merging the PR is the single human approval. [S: IAC-4] [S: docs/policies/project/workflow.md]
3. **AC-032**: **Given** a human-gated run, **When** it executes, **Then** its approvals, `continue` and `resume` behavior are unchanged. [S: IAC-4] [S: specs/27-autonomous-core/spec.md]
4. **AC-033**: **Given** any Autonomous path, **When** it finishes, **Then** the PR stays a Draft and nothing merges, deploys or performs a destructive external action. [S: IAC-4] [S: Issue #21 body]

---

### Edge Cases

- The base advances while a run is paused, and synchronization conflicts: the run blocks before any agent step with the conflict named. [S: docs/adr/0005-launcher-branch-synchronization.md]
- A pre-implementation block has no implementation baseline yet; resume must not require one before implementation runs. [S: Issue comment Hugo-Grellier 2026-10-05T20:44:26Z]
- The fix loop and retries together approach the default 40-step limit; the run blocks as exhausted limits rather than overrunning. [I]
- The wall-time limit is reached in the middle of an agent step; the run stops at the end of that step and blocks as exhausted limits. [S: tools/spec_workflow/autonomy.py]
- A retried step produces a valid draft that contradicts accepted intent; that is a content refusal and blocks without further retry. [P: D-05]
- The refresh runs while another invocation of the same run is active; it refuses rather than racing the active invocation. [I]

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The Autonomous workflow MUST run an independent implementation review, then a bounded fix loop of at most three cycles per run, each followed by the trusted checks and a fresh review; resume continues the recorded cycle count and never resets it. [S: IAC-1] [B: D-03] [S: docs/policies/workflow.md]
- **FR-002**: A high or critical finding still open after the last fix cycle MUST block the run as exhausted limits; lower-severity findings left open MUST appear in the packet with their provisional disposition. [S: IAC-3] [B: D-03] [S: specs/27-autonomous-core/spec.md]
- **FR-003**: Check results MUST reach the fix loop only through the trusted `run-checks` step; the headless agent's command permissions MUST NOT widen, and a test MUST verify this path. [S: IAC-2] [P: D-08]
- **FR-004**: Provisional intent in an Autonomous run MUST cite the discovery brief and the traced spec, and be recorded as agent-provisional. [S: IAC-4] [S: Issue #21 body]
- **FR-005**: The published Draft PR MUST carry the full acceptance packet (#19) and run record, listing every provisional decision with basis and evidence, every review with dispositions, every block resolution and the `run-checks` result. [S: IAC-2] [S: Issue #21 body]
- **FR-006**: Choosing Autonomous MUST NOT skip any check, required security review, validator or postcondition that the human-gated workflow runs. [S: IAC-2] [S: .specify/memory/constitution.md]
- **FR-007**: `ballast run resume RUN_ID` MUST continue a blocked or interrupted Autonomous run in Autonomous from the blocked step, after trusted branch synchronization and before any agent step. [S: IAC-3] [B: D-01] [S: docs/adr/0005-launcher-branch-synchronization.md]
- **FR-008**: Resume MUST work for a block before implementation and MUST NOT require an implementation baseline that does not yet exist. [S: IAC-3] [P: D-04] [S: Issue comment Hugo-Grellier 2026-10-05T20:44:26Z]
- **FR-009**: When a record made earlier in the run is invalidated during a block, resume MUST re-enter at the earliest step whose recorded input changed. [S: IAC-3] [I]
- **FR-010**: Resume MUST record the operator's resolution as a human decision of kind `block-resolution`. [S: IAC-2] [B: D-02]
- **FR-011**: `ballast run continue` of a pre-implementation Autonomous block MUST refuse with a pointer to `ballast run resume`; its behavior for post-implementation blocks MUST be unchanged. [S: IAC-3] [P: D-04]
- **FR-012**: Resume MUST keep the mode, risk and limits recorded at start; it MUST NOT raise a limit or change the mode, and only a trusted operator action changes the mode. [S: IAC-3] [S: docs/adr/0004-autonomous-provisional-decisions.md]
- **FR-013**: A changed protected input MUST fail closed on resume and synchronization, naming `ballast trust` as the recovery. [S: IAC-3] [S: .specify/memory/constitution.md]
- **FR-014**: A run whose pin lacks the feature MUST block as `wrong-branch` with a recovery that names the documented manual operator step; the workflow policy MUST document that step; nothing MUST write the pin from agent-writable inputs. [S: IAC-3] [P: D-12]
- **FR-015**: A new ADR MUST record that a blocked Autonomous run resumes in Autonomous through branch synchronization, updating ADR-0004's continuation rule. [S: IAC-4] [B: D-01] [S: docs/adr/0004-autonomous-provisional-decisions.md]
- **FR-016**: A recorder refusal that the agent can correct in its own draft MUST rerun the agent step with the validator's message, at most twice per step, each rerun counting against the agent-step limit; exhausting the retries MUST block as exhausted limits. [S: IAC-3] [P: D-05]
- **FR-017**: Refusals about state outside the draft MUST stay terminal blocks without retry, and no validator MUST be relaxed. [S: IAC-3] [P: D-05]
- **FR-018**: The approval-wording guard MUST stay as strict as today; the decide and review commands MUST tell the agent to paraphrase and cite a sourced human approval, and to respect the recorder's stated length limits. [S: IAC-4] [P: D-06]
- **FR-019**: The installed tasks template MUST keep workflow-owned steps out of `tasks.md`; the implementation check MUST stay unchanged. [S: IAC-3] [P: D-07]
- **FR-020**: `ballast run checkpoint RUN_ID` MUST refresh the Draft PR checkpoint and acceptance packet of an Autonomous run in any status, run no agent step, and leave the decision log, mode and status unchanged; it MUST refuse with an actionable reason when no Draft PR exists. [S: IAC-2] [P: D-11]
- **FR-021**: The wall-time limit MUST count only time spent inside invocations; each invocation MUST still stop at the recorded limit. [S: IAC-3] [P: D-09]
- **FR-022**: The agent-step limit MUST count every agent step, retry and fix cycle and serve as the attempt and spend bound; the run record MUST state that monetary spend is not measured. [S: IAC-2] [P: D-10]
- **FR-023**: Every block MUST name its category (conflict, missing authority, exhausted limits, unsafe uncertainty) and the operator's next action. [S: IAC-3]
- **FR-024**: Policies, templates and workflow state MUST mark every new or changed Autonomous path as agent-provisional, and validators MUST refuse an artifact that presents a provisional decision as accepted. [S: IAC-4] [S: .specify/memory/constitution.md]
- **FR-025**: The human-gated workflow's approvals, `continue` and `resume` MUST be unchanged. [S: IAC-4] [S: specs/27-autonomous-core/spec.md]
- **FR-026**: No Autonomous path MUST merge, deploy or take a destructive external action; publication, push and Draft PR updates MUST stay with the trusted runner. [S: IAC-4] [S: docs/adr/0004-autonomous-provisional-decisions.md]
- **FR-027**: The workflow tools MUST stay standard-library-only and run under `python3 -I -S`. [S: AGENTS.md]

### Key Entities

- **Autonomous run**: an operator-started run with a mode, risk, limits, a branch and feature pin, a status and a decision log, all in operator state outside agent reach.
- **Provisional decision**: an agent decision with basis and evidence, recorded by a trusted recorder from an agent draft; accepted only by merging the PR that contains it.
- **Block**: a stop with a category, a reason and a recovery; resolved by the operator through a recorded `block-resolution` human decision.
- **Fix cycle**: one fix step, followed by the trusted checks and a fresh review; at most three per run, counted in operator state and never reset by resume.
- **Retry**: a rerun of an agent step after a correctable recorder refusal, carrying the validator's message; at most two per step.
- **Acceptance packet and checkpoint**: the merge evidence on the Draft PR, refreshed by the trusted runner from current records.

## Non-goals

- Automatic merge, deployment and destructive external actions. [S: Issue #21 body]
- Presenting a provisional decision as human approval, or silently escalating agent authority. [S: Issue #21 body]
- Setup patching across integrations (#58). [S: Issue #21 intake scope comment]
- The governance change, the mode setting and provisional gates, delivered by #27. [S: Issue #21 body]
- A monetary spend limit or a paid API route. [P: D-10]
- Widening the headless agent's command permissions. [P: D-08]
- A trusted re-pin command for runs started before branch pinning; it would need its own ADR. [P: D-12]
- A `continue` path that lowers a pre-implementation block into `ballast-feature`. [P: D-04]

Every Issue acceptance criterion (IAC-1 to IAC-4) is covered by an acceptance criterion above; none is a non-goal.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A live pilot of a bounded R1 feature in Autonomous reaches a reviewed Draft PR with zero approval prompts before merge.
- **SC-002**: 100% of the run's provisional decisions, reviews, block resolutions and the `run-checks` result appear in the Draft PR's record and packet.
- **SC-003**: Each of the four block categories has a test showing an actionable reason, and a mode change without a trusted operator action is refused in a test.
- **SC-004**: Tests resume one pre-implementation and one post-implementation block in Autonomous after the base advances, each reaching its next step without a prompt.
- **SC-005**: A single correctable agent-output error never ends a run; it ends a run only after two retries fail or a limit is reached.
- **SC-006**: The human-gated workflow tests pass unchanged, and the headless agent's permission settings are unchanged.
- **SC-007**: A packet refresh of a published run leaves the decision log byte-identical and runs no agent step.
- **SC-008**: The fast gate and the full local gate are recorded in the PR.

## Assumptions

- The default limits (240 minutes active wall time, 40 agent steps) are checked by the plan against the workflow's step count plus three fix cycles and retries; changing a default is a recorded plan decision. [I]
- Resume re-entering at the earliest step whose recorded input changed is how a spec fix made during a block is handled; the plan defines how a changed input is detected. [I]
- A correctable refusal is one the agent can fix by rewriting its own draft (format, length, approval wording); the plan lists the recorder errors in that class. [P: D-05]
- The plan orders the resume and retry fixes first, because they unblock the pilot run for AC-001. [I]
- #27, #16, #18 and #19 are merged; this feature builds on their mode setting, discovery brief, branch synchronization and packet. [S: Issue #21 body]
- Scope follows the operator's 2026-10-03 decision on #11 that split this outcome from #27. [S: Issue #21 body]
- The fix loop allows at most three fix cycles per run, not per phase or per invocation; the count lives in operator state and resume continues it, so a pause never grants fresh cycles. Raising the bound later is a recorded decision. [B: D-03] [I]
- `ballast run checkpoint RUN_ID` covers Autonomous runs only, matching AC-023 and the Issue comment that asks for it; extending it to human-gated runs can be added later without changing their approvals. [P: D-11] [I]
