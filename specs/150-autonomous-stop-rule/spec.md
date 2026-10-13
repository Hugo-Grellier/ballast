# Feature Specification: Autonomous runs stop only for in-run authority changes

**Feature Branch**: `feat-150-autonomous-runs-stop-only-for-authority-changes`

**Created**: 2026-10-13

**Status**: Draft

**Input**: User description: "Issue #150: an accepted ADR where Autonomous runs stop only for in-run authority changes."

**Risk**: R2. The decision record changes accepted architecture (ADR-0004, ADR-0010) and governs agent authority and the launcher's trust model (`docs/policies/project/workflow.md#r2-boundaries`). This spec is written in an Autonomous run: every decision in it is agent-provisional, and merging the PR is the single human approval.

**Source context**: Issue #150 (snapshot `.specify/workflow-state/issues/150.md`), first leaf of Epic #149. The discovery brief [discovery.md](discovery.md) is input evidence; this spec is the authority for the feature.

## Overview

ADR-0004 lets an Autonomous run record its gate decisions provisionally, yet several parts of the workflow still stop the run for a human before the merge: the clarify step when no safe default exists, the intake gate's `ready-for-agent` label, the run limits, and ADR-0010's resume rule. The operator wants their involvement limited to writing the Issue and merging the PR. This feature records that direction as accepted architecture: a new decision record states when an Autonomous run may still stop, and what it does instead in every other case. The behavior itself is delivered by sibling leaves #151–#154; this feature only writes the decision and points the workflow policy and the technical spec at it.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Read one authoritative stop rule (Priority: P1)

An operator, or an agent implementing a sibling leaf, needs one place that says exactly when an Autonomous run blocks for a human and what it does otherwise. They open the new decision record and find the stop rule, the trusted-author rule, the limit outcome, self-resume after a provider usage limit, and the residual risk with its mitigation.

**Why this priority**: Issue #150 blocks the other leaves of Epic #149; without the decision they have no accepted architecture to implement.

**Independent Test**: Read the new decision record and check that each of the five required elements is present, stated as a rule, and consistent with the constitution's invariants.

**Acceptance Scenarios**:

1. **AC-001**: **Given** the merged change, **When** a reader opens `docs/adr/`, **Then** a new decision record numbered 0020 exists in the repository's ADR form (Status, Feature and Amends lines, then Context, Decision, Consequences and Rejected alternatives), and its Amends line names ADR-0004 and ADR-0010. [S: IAC-1]
2. **AC-002**: **Given** the decision record, **When** a reader looks for the stop rule, **Then** it states that an Autonomous run blocks only for a decision that takes effect before merge (run authority, launcher execution, external writes, credentials) or for a contradiction with an invariant the runner enforces, and that every other decision becomes a material provisional decision listed at the top of the PR. [S: IAC-1]
3. **AC-003**: **Given** the decision record, **When** a reader looks for the trusted-author rule, **Then** it states that an Issue by an author the operator has listed as trusted stands in for the `ready-for-agent` scope approval, and that this trust comes only from operator-controlled data, never from the Issue or an agent-writable file. [B: D-03] [S: IAC-1]
4. **AC-004**: **Given** the decision record, **When** a reader looks for the limit outcome, **Then** it states that reaching any run limit (agent steps, wall time, fix cycles, draft retries), in any phase, publishes a Draft PR that lists open findings and failed checks and marks every unmet acceptance criterion `unverified`, instead of blocking the run. [P: D-04] [S: IAC-1]
5. **AC-005**: **Given** the decision record, **When** a reader looks for self-resume, **Then** it states that the runner resumes a run stopped by a provider usage limit once the limit resets, records the resume as a runner event naming the usage-limit block (never as a human decision), and keeps the run's mode, risk, limits and integrations unchanged. [B: D-05] [S: IAC-1]
6. **AC-006**: **Given** the decision record, **When** a reader looks for the residual risk, **Then** it names decisions concentrated at the merge as the risk and a material-decision cap as the mitigation, and states that reaching the cap gets the limit outcome (a Draft PR stating the cap was reached), with the cap's value and configuration left to #151/#153. [P: D-06] [S: IAC-1]

---

### User Story 2 - Trace the amended decisions (Priority: P1)

A reader of ADR-0004 or ADR-0010 must not follow a rule that a later decision replaced. Each amended record carries a note that points to the new record and says which part it changes.

**Why this priority**: Without the notes, ADR-0004 and ADR-0010 would remain a second, conflicting source of truth for when a run stops and how it resumes.

**Independent Test**: Open ADR-0004 and ADR-0010 and follow their amendment notes to ADR-0020; open ADR-0009 and confirm it is unchanged.

**Acceptance Scenarios**:

1. **AC-007**: **Given** the merged change, **When** a reader opens ADR-0004, **Then** it carries a note linking ADR-0020 as the record that narrows when an Autonomous run blocks. [S: IAC-1]
2. **AC-008**: **Given** the merged change, **When** a reader opens ADR-0010, **Then** it carries a note linking ADR-0020 as the record that lets the runner resume a run stopped by a provider usage limit without an operator `block-resolution` record and replaces the limit block with a Draft PR. [S: IAC-1]
3. **AC-009**: **Given** the merged change, **When** a reader looks for Chat runs in ADR-0020, **Then** it states that Chat runs are unaffected because they record no provisional decision and every Chat gate needs the operator, and ADR-0009 is not edited. [P: D-02] [S: IAC-1]

---

### User Story 3 - Find the rule from the workflow policy and the technical spec (Priority: P2)

An agent or operator following the workflow policy, or reading the technical spec's Autonomous sections, needs to reach the new rule without the rule being restated in a second place.

**Why this priority**: The policy and technical spec are where agents read workflow behavior; the reference makes the decision discoverable while the record stays the single authority.

**Independent Test**: Search the workflow policy and the technical spec for a link to ADR-0020 and check that neither restates the rule as its own requirement.

**Acceptance Scenarios**:

1. **AC-010**: **Given** the merged change, **When** a reader opens the Autonomous runs section of `docs/policies/spec-kit-workflow.md`, **Then** it links ADR-0020 as the authority for when an Autonomous run stops and notes that sibling leaves deliver the behavior. [S: IAC-2]
2. **AC-011**: **Given** the merged change, **When** a reader opens `specs/TECHNICAL-SPEC.md`, **Then** it links ADR-0020 near its Autonomous status text. [S: IAC-2]
3. **AC-012**: **Given** the merged change, **When** the fast gate runs (lint, format check and the unit test suite, including the documentation and link checks), **Then** it passes. [S: AGENTS.md]

---

### Edge Cases

- A Chat run never records provisional decisions; the stop rule does not apply to it, and the record says so (AC-009). [S: docs/adr/0009-chat-mode-operator-driven-steps.md]
- `tamper`, `unfinished-step`, `postcondition` and protected-input changes are runner-enforced invariants; the record keeps them blocking. [S: docs/policies/spec-kit-workflow.md#autonomous-runs]
- `credential`, `permission`, `forge` and `ineligible` blocks concern credentials, external writes or run authority; the record keeps them blocking. [I]
- A run that needs `secret-provisioning` or an `external-write` before merge still blocks, because that decision takes effect before merge. [S: Issue #150 body]
- A limit reached before any spec exists still yields a Draft PR; every criterion is then `unverified`. [P: D-04]
- An Issue without `ready-for-agent` whose author is not trusted is still refused as ineligible. [I]

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The change MUST add one decision record, ADR-0020, under `docs/adr/` in the repository's ADR form, amending ADR-0004 and ADR-0010. [S: IAC-1]
- **FR-002**: ADR-0020 MUST state the stop rule: an Autonomous run blocks only for a decision that takes effect before merge (run authority, launcher execution, external writes, credentials) or a contradiction with a runner-enforced invariant; every other decision is a material provisional decision listed at the top of the PR. [S: Issue #150 body]
- **FR-003**: ADR-0020 MUST state that an Issue by an operator-trusted author stands in for the `ready-for-agent` scope approval, that trust comes only from operator-controlled data, and that the allowlist's form is delivered by #152. [B: D-03]
- **FR-004**: ADR-0020 MUST state that every run limit, in any phase, publishes a Draft PR listing open findings and failed checks and marking unmet criteria `unverified`, and leave the acceptance packet's rendering of `unverified` to #153. [P: D-04]
- **FR-005**: ADR-0020 MUST state that the runner resumes a run stopped by a provider usage limit without an operator `block-resolution` record, recording a runner event that is never a human decision, with mechanics delivered by #154. [B: D-05]
- **FR-006**: ADR-0020 MUST name the residual risk (decisions concentrated at merge) and its mitigation (a material-decision cap that gets the limit outcome when reached). [P: D-06]
- **FR-007**: ADR-0020 MUST state that Chat runs are unaffected, and ADR-0009 MUST NOT be edited. [P: D-02]
- **FR-008**: ADR-0020 MUST state that BL-INV-003 and BL-INV-006 are kept unchanged and that no constitution amendment is made. [B: D-07]
- **FR-009**: ADR-0020's status line MUST say it is accepted and stays agent-provisional until the operator merges the PR, following ADR-0004's precedent, and no text in the change may state or imply a human approval that did not happen. [B: D-01]
- **FR-010**: ADR-0004 and ADR-0010 MUST each carry a note linking ADR-0020 and naming the part it changes. [S: IAC-1]
- **FR-011**: `docs/policies/spec-kit-workflow.md` and `specs/TECHNICAL-SPEC.md` MUST link ADR-0020 without restating the rule as a second source of truth. [S: IAC-2]
- **FR-012**: The change MUST NOT modify runner, validator, skill or workflow code; the behavior ADR-0020 authorizes is delivered by #151–#154. [S: .specify/workflow-state/issues/150.md#intake-scope-comment]

### Key Entities

- **Stop rule**: the condition under which an Autonomous run blocks for a human: a pre-merge authority decision or a runner-enforced invariant contradiction.
- **Material provisional decision**: an agent decision that would previously have stopped the run; it is listed at the top of the PR for the merge reviewer.
- **Trusted author**: an Issue author named in operator-controlled data, whose Issue counts as scope approval.
- **Limit outcome**: the Draft PR a run publishes on reaching a limit, with unmet criteria `unverified`.
- **Material-decision cap**: the runner-enforced bound on material provisional decisions in one run.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All five required elements (stop rule, trusted-author rule, limit outcome, self-resume, residual risk) are present in ADR-0020: 5 of 5.
- **SC-002**: Both amended records (ADR-0004, ADR-0010) and both referencing documents (workflow policy, technical spec) link ADR-0020: 4 of 4.
- **SC-003**: Each of the sibling leaves #151–#154 can name the section of ADR-0020 it implements without needing a new decision from the operator.
- **SC-004**: The fast gate passes with no test weakened or skipped.

## Non-goals

- Implementing clarify/decide behavior (#151), the intake allowlist and Epic decomposition (#152), the token budget and unverified publication (#153), or quota self-resume (#154).
- Issues #146, #147, #141 and #143.
- Amending the constitution or ADR-0009.

## Assumptions

- The rule moves more decisions to the single merge approval BL-INV-006 already defines, so the invariant stays unchanged. [I]
- `unverified` is ADR-0020's term for any criterion not `verified`; the acceptance packet's exact states are left to #153. [I]
- Agents cannot read Epic #149 or Issues #151–#154 in this run; the sibling scopes come from the #150 intake scope comment. [S: .specify/workflow-state/issues/150.md#intake-scope-comment]
- The next free ADR number is 0020. [S: docs/adr/0019-feature-local-ui-states.md]
