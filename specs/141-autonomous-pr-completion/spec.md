# Feature Specification: Autonomous PR completion policy

**Feature Branch**: `feat/141-autonomous-pr-completion`

**Created**: 2026-10-12

**Status**: Draft

**Input**: User description: "Issue #141: an eligible Autonomous run marks its published PR ready for review when the operator's ballast.toml policy allows it, otherwise leaves a Draft and records why."

**Risk**: R2. The trusted runner gains a forge action (marking a PR ready), which changes the launcher's trust model and what the runner executes (`docs/policies/project/workflow.md`). The feature was planned in Autonomous run `478cbe23` and finished in human-gated run `6263f734` and the operator's session; merging the PR is the single human approval.

**Source context**: [Issue #141](https://github.com/Hugo-Grellier/ballast/issues/141) and its intake scope comment (operator decisions dated 2026-10-12), the [discovery brief](discovery.md), ADR-0004, ADR-0016, ADR-0018 and the Publication row of the [Spec Kit workflow](../../docs/policies/spec-kit-workflow.md#workflow-runner-contract). This feature amends the rule from #27 (`specs/27-autonomous-core/spec.md` AC-010) and the Publication contract that no step marks a PR ready. A new ADR records the amendment.

## Overview

Every Autonomous run ends today with a Draft PR. For a converged, low-risk run whose checks all passed, the operator still has to mark the PR ready by hand before reviewing and merging it, and that step adds no information. This feature adds an opt-in completion policy that the operator sets in `ballast.toml`. When the policy allows it and every eligibility condition holds, the trusted runner marks the published PR ready for review. Otherwise the PR stays a Draft and the run says why. Marking a PR ready approves nothing: merging stays the only human approval, and no agent can mark a PR ready or influence the decision.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A converged low-risk run ends with a PR ready for review (Priority: P1)

An operator has set `[autonomous] completion = "ready"` in `ballast.toml`. They start an Autonomous run on an R1 Issue. The run converges, its configured checks pass, and its acceptance packet shows every criterion verified. After publication the runner marks the PR ready for review and says so, and the operator goes straight to reviewing and merging.

**Why this priority**: This is the feature's purpose. It removes the manual `gh pr ready` step seen in the LoreForge pilot.

**Independent Test**: With `completion = "ready"` and operator records that meet every eligibility condition, run the Autonomous publication against a stand-in forge CLI. Check that it asks the forge exactly once to mark the published PR ready, prints that it did, and records the outcome in the ledger.

**Acceptance Scenarios**:

1. **AC-001**: **Given** `[autonomous] completion = "ready"` and an Autonomous run that meets every eligibility condition, **When** publication succeeds, **Then** the runner marks the published PR ready for review exactly once, as the operator, and the run output states that the PR is ready for review. [S: IAC-2] [S: Issue #141 intake scope comment]
2. **AC-002**: **Given** an Autonomous run whose PR the runner marked ready, **When** the outcome is recorded, **Then** the ledger holds one entry naming the PR, the published commit and the outcome `ready`. [S: IAC-2] [S: IAC-4]
3. **AC-019**: **Given** an eligible run with `completion = "ready"` whose request to mark the PR ready the forge accepted, **When** reading the PR back shows it still a Draft or at a head other than the published commit, **Then** the `PR completion:` line reports `unverified` with that reason instead of claiming ready or Draft, and the ledger records the outcome `unverified` with the reason `forge-unverified`. [S: DEC-0001] [S: specs/141-autonomous-pr-completion/reviews/plan.md]
4. **AC-003**: **Given** a PR this run already marked ready, **When** a later checkpoint updates that PR, **Then** the update succeeds without asking the forge to mark it ready again, and the PR is not turned back into a Draft; a `ballast run publish` of the already published run is refused without any forge call. [S: tools/spec_workflow/autonomy.py] [I]

---

### User Story 2 - An ineligible run stays a Draft and says why (Priority: P1)

The same operator runs an R2 change, or a run whose packet has an unverified criterion. The PR stays a Draft. The `PR completion:` line names the condition that failed, and the ledger records the same reason, so the operator knows why the PR still needs their attention.

**Why this priority**: The fallback is what makes the policy safe. Without a clear reason, the operator cannot trust that a Draft means something.

**Independent Test**: For each eligibility condition, build operator records that meet every other condition and fail that one. Check that the PR stays a Draft, the forge is never asked to mark it ready, and the printed line and ledger name that condition.

**Acceptance Scenarios**:

1. **AC-004**: **Given** `completion = "ready"` and a run at risk R2, **When** publication succeeds, **Then** the PR stays a Draft and the `PR completion:` line and the ledger give the reason as risk R2. [S: IAC-4] [S: Issue #141 intake scope comment]
2. **AC-005**: **Given** `completion = "ready"` and a run that fails exactly one eligibility condition in FR-005, **When** publication succeeds, **Then** the PR stays a Draft, the forge is never asked to mark it ready, and the printed reason and the ledger reason both name that condition. [S: IAC-4] [S: Issue #141 intake scope comment]
3. **AC-006**: **Given** `completion = "ready"` and a run that fails several eligibility conditions, **When** publication succeeds, **Then** the PR stays a Draft and the reason names every failed condition, in the order FR-005 lists them. [S: IAC-4] [I]
4. **AC-007**: **Given** `completion = "ready"`, an eligible run and a PR head that is not the commit publication pushed (someone pushed to the branch meanwhile), **When** the runner reads the PR back, **Then** the PR stays a Draft and the reason says the PR head is not the published commit. [S: IAC-4] [P: D-07]
5. **AC-008**: **Given** an eligible run with `completion = "ready"`, **When** the forge refuses or fails to mark the PR ready, **Then** the PR stays a Draft, the reason gives the forge failure, and the run's exit status and step state are the same as for a successful publication. [S: IAC-4] [P: D-09]
6. **AC-009**: **Given** an open finding whose severity is above `[autonomous] completion_max_severity`, **When** publication succeeds, **Then** the PR stays a Draft and the reason names the finding's severity; with the key unset, open `low` and `info` findings do not keep the PR a Draft. [S: IAC-4] [P: D-06]

---

### User Story 3 - No configuration, no change (Priority: P1)

An operator who has never heard of the policy keeps getting exactly today's Draft PR, with the same output and ledger.

**Why this priority**: Projects pin Ballast releases; an upgrade must not change what an existing Autonomous run does.

**Independent Test**: Run the Autonomous publication with no `completion` key and compare the PR state, the printed lines and the ledger entries with today's.

**Acceptance Scenarios**:

1. **AC-010**: **Given** a `ballast.toml` with no `[autonomous]` table or no `completion` key, **When** an Autonomous run publishes, **Then** the PR is a Draft, the forge is never asked to mark it ready, and the printed output and ledger entries are the same as before this feature. [S: IAC-1]
2. **AC-011**: **Given** `completion = "draft"`, **When** an Autonomous run publishes, **Then** the PR stays a Draft, the forge is never asked to mark it ready, and the printed output and ledger entries are the same as with no configuration. [S: IAC-1] [S: Issue #141 intake scope comment]
3. **AC-012**: **Given** a human-gated or Chat run, or an Autonomous run lowered to one of those modes before publication, **When** it publishes or checkpoints, **Then** the PR is never marked ready, whatever `completion` says. [S: IAC-1] [S: docs/policies/spec-kit-workflow.md#draft-pr] [I]

---

### User Story 4 - Only the operator controls the policy and the result (Priority: P1)

An agent working inside the run cannot make its own PR ready: it cannot change the policy, cannot widen it, cannot mark the PR ready itself, and cannot alter the records the runner decides from.

**Why this priority**: Marking ready must stay a runner decision over operator records. Otherwise an agent could present its own work as ready, which breaks BL-INV-003.

**Independent Test**: Change every agent-writable input (decision drafts, feature artifacts, the checkout's `ballast.toml` copy) toward `ready` and toward eligibility, and check that neither the effective policy nor the result changes. Start a run with a widening flag and check that it is refused before any agent step.

**Acceptance Scenarios**:

1. **AC-013**: **Given** a run started with `completion = "draft"` in the trusted `ballast.toml`, **When** an agent step changes the checkout's `ballast.toml` copy to `ready`, **Then** the effective policy stays `draft` and the PR stays a Draft. [S: IAC-5] [S: .specify/memory/constitution.md#BL-INV-003]
2. **AC-014**: **Given** an ineligible run, **When** an agent step writes drafts or feature artifacts that claim convergence, verified criteria, low risk or passing checks, **Then** the eligibility result is unchanged, because it is computed only from operator records. [S: IAC-5] [S: docs/adr/0004-autonomous-provisional-decisions.md]
3. **AC-015**: **Given** `completion = "draft"` or no `completion` key, **When** the operator starts an Autonomous run with `--completion ready`, **Then** the start is refused before any agent step, with a message that the flag cannot widen `ballast.toml`. [S: IAC-5] [P: D-05]
4. **AC-016**: **Given** `completion = "ready"`, **When** the operator starts an Autonomous run with `--completion draft`, **Then** the run's effective policy is `draft`, it is recorded in the run's policy snapshot, and the PR stays a Draft with the reason that the run's start flag chose `draft`. [S: IAC-5] [P: D-05]
5. **AC-017**: **Given** any agent step of any run, **When** it requests to mark a PR ready, **Then** the request is refused as a never-authorizable privileged action, as it is today. [S: IAC-5] [S: docs/adr/0016-privileged-action-kinds-and-policy-refresh.md]
6. **AC-018**: **Given** an Autonomous run started with `--completion draft`, **When** it is resumed with `--refresh-policy` after the operator set `completion = "ready"` and ran `ballast trust`, **Then** the effective policy stays `draft`; and **given** a run started without the flag, the refreshed `completion` value applies to the run's policy snapshot, though condition (11) of FR-005 still keeps a resumed run's PR a Draft. [S: IAC-5] [P: D-05]

---

### Edge Cases

- `completion` set to an unknown value (for example `"merge"` or `"Ready"`): the effective policy is `draft`, and the start prints a warning that the value cannot widen eligibility. It is never treated as `ready`.
- `completion_max_severity` set to an unknown value or one wider than `low`: the threshold stays `low` and the start prints a warning; it never lets more findings through than the fix loop does.
- The acceptance packet was not published, or failed to publish: the PR stays a Draft with that reason. This includes a Draft PR checkpoint that skipped or failed after a reported publication: the outcome is still printed and recorded, with the reason that the packet was not published.
- The PR was marked ready by a human before a `ballast run publish` retry: the retry behaves as it does today; this feature only accepts a non-draft PR that this run marked ready.
- A `ballast run checkpoint` on an Autonomous run never marks the PR ready, even when the run would be eligible.
- The forge CLI is missing or unauthenticated: same as a forge failure (AC-008).
- The forge accepted the request to mark the PR ready, but the read-back does not show it ready at the published commit: the outcome is `unverified` (AC-019), never `ready`.
- The request to mark the PR ready failed or timed out, or the step was interrupted after it: the runner reads the PR back once. It reports `ready` when GitHub shows the PR ready at the published commit, a Draft with the forge failure only when GitHub still shows the run's Draft at that commit, and `unverified` otherwise. Once the request is issued, it never reports a Draft it cannot see.
- After the runner marked a PR ready, `ballast run continue RUN --mode chat` refuses to adopt it, because Chat adoption needs a Draft PR: the operator first converts it back with `gh pr ready --undo <n>` (DEC-0003).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `ballast.toml` MUST accept `[autonomous] completion` with the values `draft` and `ready`; a missing key or table means `draft`. [S: Issue #141 intake scope comment] [B: D-01]
- **FR-002**: An unknown `completion` value MUST yield the effective policy `draft` and a start warning; it MUST never yield `ready`. [I]
- **FR-003**: `ballast run start --mode autonomous` MUST accept `--completion draft|ready`. A value wider than the trusted `ballast.toml` MUST refuse the start before any agent step. The effective value MUST be recorded in the run's policy snapshot. [P: D-05]
- **FR-004**: The effective policy MUST come only from the trusted `ballast.toml` snapshot taken at start, narrowed by the start flag. A `--refresh-policy` resume MUST re-read `completion` from the `ballast trust` baseline and still apply the start flag's narrowing. No agent output and no checkout copy of `ballast.toml` may change it. [S: docs/adr/0016-privileged-action-kinds-and-policy-refresh.md] [P: D-05]
- **FR-005**: The runner MUST decide eligibility deterministically from operator records only, checking in this order, with a named reason for each failure: (1) the run is in Autonomous mode at publication; (2) the effective policy is `ready`; (3) risk is R0 or R1 and no R2 boundary is declared; (4) no privileged action is declared; (5) final acceptance is recorded; (6) the recorded spec-reconciliation review verdict is `approved`; (7) no open finding is above the configured severity; (8) the configured `[checks]` commands passed in `run-checks` on the tree publication committed; (9) the acceptance packet was published and every criterion in it is `verified`; (10) no material provisional change was recorded; (11) no block was resolved during the run; (12) the PR head read back is the commit publication pushed. [S: Issue #141 intake scope comment] [P: D-07]
- **FR-006**: `[autonomous] completion_max_severity` MUST accept `low` (the default: open `low` and `info` findings are allowed), `info` (only `info` allowed) or `none` (no open finding allowed). Any other value MUST keep `low` and print a start warning. [P: D-06]
- **FR-007**: The runner MUST evaluate eligibility once, at the end of an Autonomous publication (from start, resume or a `ballast run publish` retry), after the acceptance packet attempt. `ballast run checkpoint` MUST never mark a PR ready. [P: D-08]
- **FR-008**: When every condition holds, the runner MUST mark the PR ready by running the GitHub CLI as the operator against the pinned `[github] repository`, resolved the way the Draft PR checkpoint resolves it. No agent step may run it, and no credential may be passed to an agent. [S: Issue #141 intake scope comment] [B: D-04] [S: docs/policies/spec-kit-workflow.md#draft-pr]
- **FR-009**: When the trusted `ballast.toml` sets `completion = "ready"`, the runner MUST print the outcome on one `PR completion:` line: ready for review; Draft with the failed conditions (including a start flag that narrowed the run to `draft`); or unverified, when the forge accepted the request but reading the PR back does not show it ready at the published commit. Otherwise FR-013 applies and no `PR completion:` line is printed. [S: IAC-2] [S: IAC-4]
- **FR-010**: When the trusted `ballast.toml` sets `completion = "ready"`, the runner MUST record the outcome (PR, published commit, `ready`, `draft` or `unverified`, and the reasons for a Draft or an unverified result) in the run ledger as an operator record. Otherwise FR-013 applies and no outcome is recorded. [S: IAC-4] [S: docs/policies/spec-kit-workflow.md#draft-pr]
- **FR-011**: A failed attempt to mark the PR ready MUST leave a Draft with the failure as its reason, and MUST NOT change the run's exit status or step state. [P: D-09]
- **FR-012**: Later checkpoints MUST accept a non-draft PR that this run marked ready, and MUST NOT ask the forge to mark it ready again; `ballast run publish` of an already published run MUST be refused without any forge call. [S: tools/spec_workflow/autonomy.py] [I]
- **FR-013**: With no `completion` key or with `draft`, the printed output, the PR state and the ledger MUST be identical to today's. [S: IAC-1]
- **FR-014**: Human-gated and Chat runs, and the Draft PR checkpoint, MUST keep their current "never marks ready" behavior. [S: docs/policies/spec-kit-workflow.md#draft-pr]
- **FR-015**: Marking ready MUST stay a never-authorizable privileged action for agents. [S: docs/adr/0016-privileged-action-kinds-and-policy-refresh.md] [B: D-04]
- **FR-016**: A new ADR MUST record that the trusted runner may mark an eligible Autonomous PR ready, amending ADR-0004's publication decision and the narrowing-only rule for `[autonomous]`. The Publication contract, the Draft PR and Autonomous sections of the Spec Kit workflow policy, the technical spec and the configuration docs MUST be updated to match. [S: AGENTS.md] [B: D-03] [S: Issue #141 intake scope comment]
- **FR-017**: No document, record or output produced by this feature may describe marking ready as an approval; merging stays the single human approval. [S: .specify/memory/constitution.md#BL-INV-006]

### Non-goals

- IAC-3 (merging the PR or enabling GitHub auto-merge) is out of scope: the intake moved it to #143, ADR first. [S: Issue #141 intake scope comment] [B: D-02]
- A per-Issue `Completion:` line in the intake scope record. [S: Issue #141 intake scope comment]
- Marking a PR ready from any agent step. [S: Issue #141 intake scope comment]
- Waiting for GitHub CI results on the published head before deciding; CI and branch protection still decide the merge. [P: D-07]
- Any change to human-gated or Chat runs, or to the Draft PR checkpoint's "never marks ready" rule. [S: docs/policies/spec-kit-workflow.md#draft-pr]

### Key Entities

- **Completion policy**: the operator's choice, `draft` or `ready`, with the finding-severity threshold. It comes from the trusted `ballast.toml` snapshot and may be narrowed by the start flag. It is part of the run's policy snapshot.
- **Eligibility result**: the ordered list of failed conditions (empty when eligible), computed from operator records: run record, decision log, ledger, review findings, `run-checks` results, publication result and packet build.
- **Completion outcome**: a ledger record of the PR, the published commit, `ready`, `draft` or `unverified`, and the reasons.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A run like the LoreForge pilot (R1, converged, all checks passing, every criterion verified) with `completion = "ready"` ends with a PR ready for review and needs zero manual steps before review.
- **SC-002**: Each of the 12 eligibility conditions has a test in which failing only that condition keeps the PR a Draft with that condition named as the reason.
- **SC-003**: Without a `completion` key, a run's printed output and ledger entries are byte-identical to the previous release's for the same run.
- **SC-004**: None of the agent-writable inputs tested (drafts, feature artifacts, the checkout's `ballast.toml` copy) changes the effective policy or the eligibility result.
- **SC-005**: The fast gate passes; the full gate is recorded, or listed as unavailable, in the PR.

## Assumptions

- Marking a PR ready approves nothing, so merging stays the single human approval and BL-INV-006 holds. [I]
- Eligibility is a pure function of operator records, so it can be tested without GitHub. [I]
- An unknown `completion` value falls back to `draft` with a warning, as unknown `[autonomous] risk` entries are ignored with a warning today, rather than refusing the start. [I]
- When several conditions fail, listing all of them in a fixed order makes the reason complete and deterministic. [I]
- Whether the outcome extends the existing `pull_request` ledger event or adds a new event is a plan decision; a new event kind is rejected by older pinned versions, as ADR-0018 records. [I]
- A run lowered to human-gated or Chat mode never marks ready, because condition (1) checks the mode at publication. [I]
- The completion outcome is printed and recorded only when the trusted `ballast.toml` sets `completion = "ready"`. With no key, `draft` or an unknown value (which FR-002 turns into `draft`), the PR line and ledger are today's (FR-013), and condition (2) is never reported. When the start flag narrows `ready` to `draft`, the outcome is reported with that reason (AC-016). This resolves the overlap between FR-009/FR-010 and FR-013. It only affects output and ledger content, so it is reversible before merge. (Agent-provisional clarification.) [I]
- D-05 to D-09 of the discovery brief are agent-provisional assumptions (PD-0002 to PD-0006) and are reversible before merge. [P: D-05] [P: D-06] [P: D-07] [P: D-08] [P: D-09]
