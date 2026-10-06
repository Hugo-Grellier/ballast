# Feature Specification: Chat mode

**Feature Branch**: `feat/20-chat-mode`

**Created**: 2026-10-05

**Status**: Draft

**Input**: User description: "Issue #20: An operator can work conversationally, one step at a time, while Ballast keeps the same safety and evidence guarantees as a headless run."

**Risk**: R2. Chat adds an interactive agent path through the launcher's trust model and changes how agent authority is granted during a run. Both are R2 boundaries in `docs/policies/project/workflow.md`. This spec is being prepared in an Autonomous run, so every intermediate decision about it is agent-provisional and the merge decision is the single human approval.

**Source context**: [roadmap Priority 4](../../docs/plans/2026-10-02-product-roadmap.md#priority-4--let-the-operator-choose-the-level-of-supervision), [technical spec §91](../TECHNICAL-SPEC.md#91-v10-target), [Issue #20](https://github.com/Hugo-Grellier/ballast/issues/20) (leaf of Epic #11). It depends on branch synchronization (#18, landed). Out of scope per #20: a new IDE, any bypass of the trusted launcher, separate canonical artifacts for Chat, and Autonomous resume (#21).

## Overview

Today an operator can run a feature in two ways. They can run it through `ballast run`, where agents work headless and the operator answers gate prompts. Or they can work in a normal Claude Code or Codex session with the Spec Kit commands. The second way feels natural, but it skips trust verification, branch synchronization, artifact postconditions and the run's evidence record. Work done there cannot show the PR reviewer the same guarantees as a headless run.

Chat mode is a third per-run mode alongside human-gated and Autonomous. The operator starts the run through the trusted launcher, picks the next workflow step and talks with the agent during that step. Between steps they can inspect the run and edit files. Ballast performs the trusted preflight before every agent step and confines the agent the same way as a headless step. When the step ends, Ballast checks its artifact postconditions and records the step, its checks, reviews and decisions in the same run record a headless run uses. Gate approvals stay human, as in the human-gated mode. Chat changes who drives the order of steps and how the operator talks to the agent. It does not change who approves, what is checked or which artifacts are canonical.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Work through a feature one conversational step at a time (Priority: P1)

An operator has a scoped leaf Issue and wants to shape the spec in conversation instead of answering prompts after headless steps. They start a run in Chat mode. Ballast verifies trust and synchronizes the branch, then asks which step to run. The operator picks `specify` and discusses the spec with the agent until satisfied, then ends the step. Ballast checks the spec's postcondition and records the step. The operator reads the spec, edits a paragraph by hand, approves intent through the trusted approval action and continues with `plan`.

**Why this priority**: This is the feature's main outcome and the 1.0 requirement for Chat. Without it, the operator's only conversational option bypasses every Ballast guarantee.

**Independent Test**: In a scratch repository with a trusted checkout, start a Chat run for a small test Issue. Run `specify` conversationally, end the step, edit `spec.md`, approve intent and run `plan`. Confirm that the run record lists both steps with their agent identity and postcondition results, the operator edit and the human intent approval. Confirm that the artifacts are the ones a headless run would produce.

**Acceptance Scenarios**:

1. **AC-001**: **Given** a trusted checkout and a scoped leaf Issue, **When** the operator starts a feature run in Chat mode through the trusted launcher, **Then** Ballast performs the same preflight as a headless start (trust baseline, tamper marker, unfinished steps, protected inputs, branch synchronization) before any agent runs, and refuses with the same reason when any of them fails.
2. **AC-002**: **Given** a Chat run waiting between steps, **When** the operator asks for the next step, **Then** Ballast offers only the workflow steps whose upstream artifact checks currently pass, and the operator chooses which one to run.
3. **AC-003**: **Given** a Chat step in progress, **When** the operator and the agent converse, **Then** the agent works under the same permission model and confinement as a headless step of the same phase, and anything that model does not allow is denied, not offered to the operator as a prompt.
4. **AC-004**: **Given** a Chat step that ends, **When** Ballast closes it, **Then** it runs that phase's artifact postcondition and the cumulative upstream checks, records the result, and a failed postcondition prevents every step that depends on it until a later run of the step passes.
5. **AC-005**: **Given** a Chat run between steps, **When** the operator inspects it, **Then** they see the run's mode, feature identity, completed steps with their results, failed checks, pending gates, open decisions and the steps currently allowed.
6. **AC-006**: **Given** a Chat run between steps, **When** the operator edits feature files, **Then** the next step starts only after the preflight passes again, Ballast records that artifacts changed outside an agent step, and any approval bound to a changed artifact becomes stale as it does today.

---

### User Story 2 - Approve gates as a human, never through the conversation (Priority: P1)

At intent, plan, tasks and final acceptance, the operator approves the artifact through Ballast's trusted approval action. The agent cannot approve a gate, write an approval that counts or record a check result that counts, whatever it writes or says in the conversation.

**Why this priority**: A conversational agent sits closer to the operator than a headless one, so it is easier to blur "the agent said it is fine" with "the human approved it". The human-gated approvals stay in force in Chat (roadmap Priority 4), so this boundary must hold.

**Independent Test**: In a Chat step, have the agent write an approval block into `intent.md`, claim in conversation that the intent is approved, and report that the checks passed. Confirm that the next step that needs intent approval is still refused, and that the run record shows no approval and no passing check.

**Acceptance Scenarios**:

1. **AC-007**: **Given** a Chat run at a gate, **When** the operator approves through the trusted approval action, **Then** the approval is recorded as a human decision bound to the exact artifact version, outside agent-writable state.
2. **AC-008**: **Given** a Chat step, **When** the agent writes an approval record, edits the run's mode or state, or claims in conversation that a gate is approved or a check passed, **Then** no gate opens, no check is recorded as passed and the run's effective mode does not change.
3. **AC-009**: **Given** a Chat run, **When** the workflow reaches a point where the human-gated mode needs a human approval or resolution, **Then** Chat needs the same human approval or resolution, and never records an agent-provisional decision in its place.

---

### User Story 3 - Leave and resume a Chat run safely (Priority: P1)

The operator stops in the middle of a feature, closes the terminal and comes back the next day after `main` has advanced. They resume the Chat run. Ballast performs the trusted preflight and synchronizes the branch, then shows where the run stopped: steps done, a failed check from yesterday, the pending plan gate and an open decision. The operator continues from there.

**Why this priority**: Operators rarely finish a feature in one sitting. A conversational mode that loses state or skips the preflight on return would recreate the gap it is meant to close.

**Independent Test**: Run two steps of a Chat run, leave one postcondition failed, end the session and advance the base branch. Resume the run and confirm that branch synchronization runs before the first agent step, the handoff summary shows the failed check and pending gates, and no step that depends on the failed check is offered.

**Acceptance Scenarios**:

1. **AC-010**: **Given** a Chat run the operator left between steps, **When** they resume it through the trusted launcher, **Then** Ballast performs the full preflight, including branch synchronization, before any agent step, and refuses with the same reason as a headless resume when any part fails.
2. **AC-011**: **Given** a resumed Chat run, **When** it opens, **Then** it shows a handoff summary of the run's state (mode, feature identity, completed steps, failed checks, pending gates, open decisions, allowed next steps) built from the run record, not from the conversation history.
3. **AC-012**: **Given** a Chat step whose session ended without the step being closed (closed terminal, crash, killed agent), **When** the operator returns, **Then** the step is recorded as interrupted, its postcondition is checked before any later step, and the run continues only if Ballast confirms the step's agent processes are gone; otherwise the existing unfinished-step refusal applies.
4. **AC-013**: **Given** a Chat run with a step in progress, **When** a second Chat session or a headless invocation tries to work on the same run, **Then** it is refused with a reason that names the active step.

---

### User Story 4 - Record the same evidence a headless run would give the PR (Priority: P2)

When the feature is ready, the operator runs the checks and reviews, approves final acceptance and asks Ballast to publish the Draft PR. The PR reviewer sees the same feature identity, checks, reviews and decisions they would see for a headless run, plus the fact that the run was driven in Chat.

**Why this priority**: Chat is acceptable only if its PR is as reviewable as a headless one. This is the second acceptance criterion of #20.

**Independent Test**: Take a scratch feature through Chat to a Draft PR, and the same feature through the human-gated mode. Compare their run records and PR evidence: the same kinds of entries must appear (identity, steps, agent identities, checks, reviews, decisions, approvals), with the mode labeled in each.

**Acceptance Scenarios**:

1. **AC-014**: **Given** a Chat run, **When** any step, check, review, decision or approval happens, **Then** it is recorded in the same run record and with the same feature identity (Issue, feature directory, branch, run) as a headless run, together with the run's mode.
2. **AC-015**: **Given** a Chat run, **When** the operator runs an independent review step, **Then** the review runs in a context separate from the authoring steps, its reviewer identity and verdict are recorded, and the PR evidence shows whether it was cross-provider.
3. **AC-016**: **Given** a Chat run with final acceptance approved and checks recorded, **When** the operator asks to publish, **Then** the trusted runner, not the agent, creates or updates the feature's single Draft PR with the same evidence a headless run provides, labeled as a Chat run.
4. **AC-017**: **Given** a Chat run, **When** it records conversation logs, **Then** they stay local to the operator's machine and are never attached to or quoted in the PR; the PR links only committed artifacts and the run record.

---

### User Story 5 - Switch modes without losing a failure or promoting a decision (Priority: P2)

The operator may move a run between Chat and the human-gated mode, for example to let a long `implement` step run headless and then come back to Chat to review it. They may also continue a blocked Autonomous run in Chat to finish the missing work in conversation. No switch hides an earlier failure or turns an unapproved decision into an approved one, and no switch can raise a run to Autonomous.

**Why this priority**: This is the third acceptance criterion of #20. A mode switch that resets state would let an operator, or an agent that influences them, get past a failed check by changing modes.

**Independent Test**: In a Chat run with a failed check and an open decision proposal, switch to the human-gated mode and back. Confirm both still block exactly as before. Try to switch the run to Autonomous and confirm the refusal. Continue a blocked Autonomous run in Chat and confirm its provisional decisions stay labeled provisional until a human approval supersedes them.

**Acceptance Scenarios**:

1. **AC-018**: **Given** a run in Chat or human-gated mode, **When** the operator switches it to the other mode through the trusted operator action, **Then** the change is recorded with its time and actor, and every earlier step, check, review, decision and refusal stays in the record unchanged.
2. **AC-019**: **Given** a run with a failed check or postcondition, **When** its mode changes, **Then** the failure still blocks the steps that depend on it, and only a later passing run of the same check clears that block, with the failure still in the history.
3. **AC-020**: **Given** a run with an open decision proposal or an agent-provisional decision, **When** its mode changes, **Then** the decision keeps its status, and only a human approval or resolution through the trusted path can accept it.
4. **AC-021**: **Given** a Chat run, **When** anyone asks to switch it to Autonomous, **Then** the switch is refused, as for any raise of autonomy after start.
5. **AC-022**: **Given** a blocked or changes-requested Autonomous run, **When** the operator continues it in Chat through the trusted continue action, **Then** the human decision is recorded, the run continues in Chat, and its earlier provisional decisions stay visibly provisional until a human approval supersedes each one.

---

### Edge Cases

- **The operator edits a protected input between steps** (`ballast.toml`, `.ballast/`, `.specify/`, `.venv/`): the next step is refused exactly as a headless invocation would be. The operator reviews the change and runs `ballast trust` before continuing.
- **The base branch advances during a long Chat session**: the next agent step's preflight synchronizes the branch, or stops before the agent with the existing upstream-sync block.
- **The operator wants a step the workflow does not allow yet**, for example `plan` before intent is approved: Ballast refuses it and names the missing upstream check. The operator can still edit files directly.
- **The operator re-runs an earlier step**, for example `specify` after `plan`: the step runs, and every approval and check bound to the changed artifacts becomes stale, as it does when a headless run changes them.
- **The agent asks for a permission the step does not allow**, for example to edit `ballast.toml`: the request is denied without a prompt. The operator can make the change themselves between steps, and the next preflight then applies.
- **The selected integration cannot run confined**: the Chat start or step is refused for that integration with the reason, and the operator can choose another integration.
- **The conversation contains a secret** pasted by the operator: the conversation log stays local, and nothing from it is published.
- **The operator ends a step while the agent is still writing**: Ballast stops the agent and confirms its processes are gone before checking the postcondition.
- **No reviewer from another provider is available**: the review still runs in a separate context, and the record and PR state that it was not cross-provider.

## Requirements *(mandatory)*

### Functional Requirements

**Mode and entry point**

- **FR-001**: The operator MUST be able to select Chat mode per run when starting a feature run through the trusted launcher. Chat MUST NOT be reachable through a path that skips the launcher.
- **FR-002**: Chat mode MUST be recorded with the run in state that agent steps cannot write, as the human-gated and Autonomous modes are, with every later change, its actor and its time.
- **FR-003**: Chat MUST keep every human approval and resolution the human-gated mode requires. It MUST NOT record agent-provisional decisions in their place.

**Trusted preflight and confinement**

- **FR-004**: Before every agent step in a Chat run, not only at start and resume, Ballast MUST perform the same preflight as a headless invocation: trust baseline, tamper marker, unfinished steps, protected inputs and branch synchronization. A failed preflight MUST stop before the agent runs, with the same reason and recovery as for a headless run.
- **FR-005**: A Chat agent step MUST run under the same permission model, write boundary and Git guard as a headless step of the same phase. Anything that model does not allow MUST be denied. The operator MUST NOT be prompted to grant it during the step.
- **FR-006**: Nothing an agent writes, prints or says in a Chat step MAY change the run's mode, approvals, recorded checks or allowed steps.

**Operator-controlled steps**

- **FR-007**: Between steps, the operator MUST be able to choose the next step among the workflow phases whose upstream checks pass, re-run an earlier step, run an independent review, run the project's checks, approve or resolve through the trusted path, switch mode, inspect the run, or stop.
- **FR-008**: Each Chat step MUST map to one workflow phase and produce or change only that phase's canonical artifacts. Chat MUST NOT introduce separate canonical artifacts.
- **FR-009**: When a Chat step ends, normally or not, Ballast MUST confirm that the step's agent processes are gone before it checks the phase's postcondition and the cumulative upstream checks, and it MUST record the result. When it cannot confirm this, the existing unfinished-step refusal MUST apply.
- **FR-010**: A failed postcondition or check MUST block every step that depends on it until a later run of the same check passes. The failure MUST stay in the run's history.
- **FR-011**: Changes to feature files made between steps MUST be recorded as made outside an agent step, and MUST make any approval or check bound to the changed artifact stale, as they do in the human-gated mode.
- **FR-012**: At most one step MAY be active in a run at a time. A second Chat session or a headless invocation on a run with an active step MUST be refused, with a reason that names the active step.

**Evidence and publication**

- **FR-013**: A Chat run MUST record, in the same run record and format as a headless run, the feature identity (Issue, feature directory, branch, run), each step with its phase, agent identity (provider, model, role), start, end and outcome, every postcondition and check result, every review with its reviewer identity and verdict, every decision and every human approval.
- **FR-014**: An independent review in Chat MUST run in a context separate from the authoring steps, preferring another provider when one is available. The record MUST state whether it was cross-provider.
- **FR-015**: Agent claims about checks, reviews or approvals made in a Chat step MUST NOT satisfy any check or gate. Only results recorded by Ballast's trusted path count.
- **FR-016**: Publication of a Chat run MUST be done by the trusted runner on the operator's request, after final acceptance is approved, into the feature's single Draft PR. The PR MUST carry the same evidence a headless run provides and state that the run used Chat mode.
- **FR-017**: Ballast MUST keep each Chat step's conversation log in the same git-ignored local run state as a headless step's logs. Conversation logs MUST stay local and MUST NOT be attached to, quoted in or linked from the PR.

**Handoff and resume**

- **FR-018**: The operator MUST be able to stop a Chat run between steps and resume it later through the trusted launcher, from the same or a new terminal session.
- **FR-019**: On resume and on inspect, Ballast MUST show a handoff summary built from the run record: mode, feature identity, completed steps with outcomes, failed checks, stale approvals, pending gates, open decisions and the allowed next steps. The summary MUST NOT depend on the conversation history.

**Mode switching**

- **FR-020**: Only a trusted operator action MAY switch a run between Chat and the human-gated mode. Switching a run to Autonomous after start MUST be refused.
- **FR-021**: The operator MUST be able to continue a blocked or changes-requested Autonomous run in Chat through the trusted continue action, as they can in the human-gated mode today. The continuation MUST be recorded as a human decision.
- **FR-022**: A mode switch MUST NOT erase, hide or reclassify a recorded step, check result, review, decision, approval or refusal. A failed check MUST still block after the switch. An unapproved or provisional decision MUST keep its status until a human approval or resolution through the trusted path supersedes it.

**Governance**

- **FR-023**: The shipped workflow policy, the Spec Kit workflow guidance and the agent instructions MUST describe Chat mode: how to start, inspect, continue, resume and switch it, that its approvals are human, and that working outside `ballast run` gives none of its guarantees.

### Key Entities

- **Chat run**: A feature run whose mode is Chat. It has the same feature identity and run record as other runs, and a sequence of operator-chosen steps.
- **Chat step**: One conversational agent session for one workflow phase. It has a phase, agent identity, start, end, outcome (completed, interrupted, refused) and the postcondition results checked when it closed.
- **Preflight result**: The outcome of the trusted checks performed before an agent step, with its refusal reason when it fails.
- **Out-of-step change**: A change to feature files detected between steps, attributed to the operator, with the approvals and checks it made stale.
- **Handoff summary**: A view of a run's current state built from the run record, shown on inspect and resume.
- **Mode change**: A recorded switch between Chat and human-gated, or a continuation from Autonomous into Chat, with its actor, time and reason.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An operator can take a small R1 feature from a scoped Issue to a Draft PR entirely in Chat, and every agent step in its history was preceded by a passing preflight.
- **SC-002**: Each preflight refusal condition (changed trust baseline, tamper marker, unfinished step, changed protected input, failed branch synchronization) stops a Chat start, resume and next step before any agent runs. Each condition is covered by a test that fails if the stop is removed.
- **SC-003**: For the same feature taken through Chat and through the human-gated mode, the run records contain the same kinds of evidence (identity, steps, agent identities, checks, reviews, decisions, approvals), differing only in the mode label and the step sequence.
- **SC-004**: No attempt from inside a Chat step to approve a gate, record a passing check, change the mode or open a refused step changes the run's behavior. Each attempt is covered by a test.
- **SC-005**: After any sequence of mode switches, 100% of failed checks and unapproved decisions recorded before the switches still block or remain unapproved. This is covered by tests for each allowed switch.
- **SC-006**: An operator who resumes a Chat run can name its failed checks, pending gates and next allowed steps from the handoff summary alone, without reading the earlier conversation.
- **SC-007**: Human-gated and Autonomous runs started after this feature behave as before it. Their existing tests keep passing unchanged.

## Assumptions

- Chat keeps the human-gated approvals, as the roadmap requires ("keep the current approvals for Chat"). Chat and human-gated have the same approval authority, so switching between them is not a raise of autonomy. Switching to Autonomous after start stays refused.
- A step is a workflow phase. Free-form conversation happens inside a step, and its result is checked as that phase's output. An operator who wants unscoped agent help picks the phase the help serves. A free-form step type is not part of this feature.
- The operator's own edits between steps are operator authority. They are recorded and re-checked, but not refused, except for protected inputs, which fail closed as today.
- A Chat agent gets no extra permissions through interactive prompts. This is the safe default for an R2 boundary. Widening it would need its own decision.
- Chat supports the agent integrations the headless runner can confine. An integration that cannot run inside Ballast's confinement is refused for Chat, as it is for a headless step.
- Chat keeps a local conversation log for each step, stored like a headless step's stdout and stderr logs in git-ignored run state and never published. Not keeping one, or keeping it for a shorter time, is a later change that loses no committed data.
- Chat runs have no wall-time or attempt limit, because the operator is present. Limits stay an Autonomous feature.
- The reusable Draft PR lifecycle (#17) and branch synchronization (#18) exist and are reused. The richer review packet (#19) and Autonomous resume (#21) are separate features. Chat uses them when they exist.
- The qualified environment is GitHub on Linux with a systemd user session, as for Ballast 1.0.
