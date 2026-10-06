# Feature Specification: Setup trusts a checkout it just installed

**Feature Branch**: `feat/55-setup-trust`

**Created**: 2026-10-06

**Status**: Draft

**Input**: User description: "Issue #55: a checkout whose protected inputs are exactly what a trusted ballast setup just produced is trusted without a separate operator command."

**Tracking**: [Ballast #55](https://github.com/Hugo-Grellier/ballast/issues/55), child of Epic #11, milestone v1.0; [product roadmap](../../docs/plans/2026-10-02-product-roadmap.md) phase 2; [technical spec §9.1](../TECHNICAL-SPEC.md#91-v10-target). Related: recoverable installs ([#14](../14-recoverable-install/spec.md)) and new-worktree preparation ([#15](../15-worktree-setup/spec.md)). Written from the [discovery brief](discovery.md).

**Risk**: R2. It changes the launcher's trust model and who may record a trust baseline, two boundaries in [`docs/policies/project/workflow.md`](../../docs/policies/project/workflow.md#r2-boundaries).

**Mode**: Autonomous run `b48b609a`. The operator settled the three design questions D-01, D-02 and D-03 while resolving the run's discovery block; every other decision on this feature is agent-provisional, and merging its PR is the only human approval of the R2 change.

## Context

The launcher refuses `ballast run`, `ballast ledger` and `ballast intake` until a trust baseline in operator state matches the checkout's protected inputs: `ballast.toml`, `.ballast/spec_workflow`, `.specify`, `.venv` and a linked worktree's `.git` pointer. Today only the operator's `ballast trust` writes that baseline, so every fresh clone, issue worktree and pilot repository costs one human command, even when every protected input was just written by the operator's own `ballast setup` of the pinned standard and no agent has run there.

This feature lets setup, and the first-command preparation of a new worktree (#15), record the baseline itself when the checkout holds exactly what setup produced, the committed `ballast.toml` and constitution are ones a human already reviewed, and no agent has run in the checkout. Everything else still needs an explicit `ballast trust`. The launcher's comparison before every run does not change, and `ballast doctor` says who recorded the baseline.

The operator chose this direction knowing it conflicts with two accepted rules: ADR-0007 says setup never records trust, and the constitution's BL-INV-002 says the launcher refuses until the operator trusts the inputs. The operator chose to supersede that ADR-0007 clause with a new ADR and to amend BL-INV-002 so a setup-recorded baseline under the stated conditions also counts (D-01). The same ADR supersedes ADR-0011's rule that preparation never reads or records a baseline.

## User Scenarios & Testing *(mandatory)*

Give each acceptance scenario a stable ID (`AC-001`, `AC-002`, ...). Task and test descriptions cite the IDs they satisfy, so review can trace each criterion to evidence.

### User Story 1 - Set up a clean checkout and start a run with no `ballast trust` (Priority: P1)

The operator clones a project at its released pin, or checks out its default branch, and runs `ballast setup`. Setup installs the pinned standard, sees that the checkout holds exactly what it wrote and that the committed configuration matches the default branch, and records the trust baseline itself. The operator, or an agent driving work for them, then starts `ballast run` with no other command.

**Why this priority**: This is the Issue's main outcome; it removes one human touch per checkout.

**Independent Test**: In a clean clone whose `ballast.toml` and constitution equal the default branch's remote-tracking ref, run `ballast setup`, then `ballast run start`; the launcher accepts the checkout, no `ballast trust` ran, and `ballast doctor` reports that setup recorded the baseline.

**Acceptance Scenarios**:

1. **AC-001**: **Given** a clean checkout whose committed `ballast.toml` and constitution equal those on the default branch's remote-tracking ref, no run state and no tamper marker, **When** the operator runs `ballast setup` and it installs and verifies the pinned standard, **Then** setup records a trust baseline for the checkout's protected inputs and says it did so. [S: IAC-1] [B: D-01] [B: D-02]
2. **AC-002**: **Given** a baseline setup just recorded, **When** `ballast run start` (or `ballast ledger` or `ballast intake`) runs with no `ballast trust` in between, **Then** the launcher accepts the checkout through its unchanged comparison. [S: IAC-1] [S: IAC-4]
3. **AC-003**: **Given** a baseline setup recorded, **When** the operator runs `ballast doctor`, **Then** its trust check reports that setup recorded the baseline; **and given** a baseline the operator recorded with `ballast trust`, **Then** it reports operator `trust`. [S: IAC-1] [S: Issue #55 body] [P: D-05]
4. **AC-004**: **Given** a checkout whose committed `ballast.toml` and constitution differ from the default branch but equal those in the checkout's previous operator-recorded baseline, **When** `ballast setup` runs and the other conditions hold, **Then** setup records the baseline. [B: D-02] [S: IAC-1]
5. **AC-005**: **Given** an installed checkout with no baseline whose inputs are current, **When** `ballast setup` reports that nothing changed and every condition holds, **Then** it records the baseline; **and given** the checkout already has an operator-recorded baseline equal to its current inputs, **Then** setup leaves that baseline and its operator source untouched. [S: tools/setup] [I]

---

### User Story 2 - A new worktree is trusted by its first command (Priority: P1)

An agent driving work for the operator creates an issue worktree and runs its first `ballast run`. Preparation (#15) installs the worktree from a verified local installation and, under the same conditions as setup, records the worktree's baseline, so the run starts with no human step.

**Why this priority**: Issue worktrees are where the repeated human touch costs most; the Issue puts the #15 path in scope and the operator chose that preparation records a baseline (D-03).

**Independent Test**: Create a linked worktree of a trusted project on a branch whose `ballast.toml` and constitution equal the default branch's, then run `ballast run start`; preparation installs, records the baseline, and the run starts with no `ballast trust`.

**Acceptance Scenarios**:

1. **AC-006**: **Given** a new linked worktree whose committed `ballast.toml` and constitution equal those on the default branch's remote-tracking ref, with no run state and no tamper marker, **When** its first `ballast run`, `ledger` or `intake` prepares it from a verified local installation, **Then** preparation records the worktree's baseline and the command proceeds without `ballast trust`. [S: Issue #55 intake scope comment] [B: D-03] [S: IAC-1]
2. **AC-007**: **Given** a new worktree whose branch changed `ballast.toml` or the constitution, **When** its first command prepares it, **Then** preparation installs it, records no baseline, and the launcher refuses with a message naming `ballast trust`. [S: IAC-2] [B: D-02] [B: D-03]
3. **AC-008**: **Given** a stale baseline left in operator state at a reused checkout path, **When** preparation installs the worktree, **Then** the stale baseline is never reused as-is: it is removed, and a new one is recorded only when every condition holds. [S: tools/setup] [S: docs/adr/0011-worktree-preparation.md#rejected-alternatives] [I]
4. **AC-009**: **Given** another checkout's baseline, **When** setup or preparation records a baseline, **Then** it computes it from this checkout's own inputs and never copies or inherits another checkout's baseline. [S: docs/adr/0011-worktree-preparation.md#rejected-alternatives] [B: D-03]

---

### User Story 3 - A checkout that differs from what setup produced still needs `ballast trust` (Priority: P1)

When anything in the checkout is not exactly what setup wrote from reviewed configuration, setup installs as it does today, records nothing, and tells the operator to review the inputs and run `ballast trust`.

**Why this priority**: Without this, an unreviewed change, such as an agent widening `[agents.permissions]`, would be trusted silently; it is the feature's safety boundary.

**Independent Test**: For each differing input below, run `ballast setup` and check that no baseline exists afterwards, setup's message names `ballast trust`, and `ballast run start` is refused.

**Acceptance Scenarios**:

1. **AC-010**: **Given** a `ballast.toml` or constitution with uncommitted changes, such as a pin bump an agent wrote, **When** `ballast setup` runs, **Then** it records no baseline and says `ballast trust` is needed after review. [S: IAC-2] [B: D-06]
2. **AC-011**: **Given** a committed `ballast.toml` or constitution that differs from both the default branch's remote-tracking ref and the previous operator-recorded baseline, such as widened `[agents.permissions]` on a feature branch, **When** `ballast setup` runs, **Then** it records no baseline and says `ballast trust` is needed after review. [S: IAC-2] [B: D-02]
3. **AC-012**: **Given** a protected input setup did not write, such as an extra or edited file under `.specify` or `.ballast/spec_workflow`, **When** `ballast setup` runs, **Then** it records no baseline and says `ballast trust` is needed after review. [S: IAC-2]
4. **AC-013**: **Given** a linked worktree whose `.git` pointer does not name a worktree of the same repository whose default branch setup compared against, **When** setup or preparation runs, **Then** it records no baseline and says `ballast trust` is needed. [S: IAC-2] [S: tools/spec_workflow/launcher.py] [I]
5. **AC-014**: **Given** the default branch's remote-tracking ref is absent or cannot be read, and the checkout has no previous operator-recorded baseline, **When** setup runs, **Then** it records no baseline and says `ballast trust` is needed. [B: D-02] [I]
6. **AC-015**: **Given** setup records no baseline for any reason, **When** it finishes, **Then** its message names the reason and `ballast trust`, the installation itself succeeds or fails exactly as it does today, and any baseline the operator recorded earlier is left untouched. [S: IAC-2] [S: tools/setup] [I]

---

### User Story 4 - An agent step can never lead to a recorded baseline (Priority: P1)

Once an agent has run in a checkout, or might still be running, setup and preparation refuse to record a baseline. A checkout that changes after a setup-recorded baseline is refused by the launcher exactly as today.

**Why this priority**: It keeps an agent from gaining authority its caller never reviewed, a constitution invariant.

**Independent Test**: With an in-progress marker, with a tamper marker, and with saved run state, run `ballast setup` and preparation and check that no baseline is recorded; then, after a setup-recorded baseline, edit a file under `.specify` and check `ballast run start` fails closed.

**Acceptance Scenarios**:

1. **AC-016**: **Given** an agent step's in-progress marker in operator state, **When** `ballast setup` or preparation runs, **Then** it records no baseline and names the remedy. [S: IAC-3]
2. **AC-017**: **Given** a `BALLAST_TAMPERED` marker, **When** `ballast setup` or preparation runs, **Then** it records no baseline and names the remedy. [S: IAC-3]
3. **AC-018**: **Given** saved run state from earlier runs in the checkout, or an unfinished run in operator state, **When** `ballast setup` or preparation runs, **Then** it records no baseline and says `ballast trust` is needed after review. [S: IAC-3] [P: D-04]
4. **AC-019**: **Given** an agent running a workflow step, **When** it starts setup or preparation, **Then** neither records a baseline, because a step always holds the in-progress marker and setup refuses on it. [S: IAC-3] [S: AGENTS.md]
5. **AC-020**: **Given** a baseline setup recorded, **When** any protected input later changes, such as an agent editing `.specify` scripts, **Then** the next `ballast run`, `ledger` or `intake` fails closed with the same refusal as today. [S: IAC-4]
6. **AC-021**: **Given** the launcher's existing trust and refusal tests, **When** the feature is complete, **Then** they pass unchanged, and the launcher's comparison and tamper marker behave as before. [S: IAC-4] [B: D-07]
7. **AC-022**: **Given** a provenance record that is missing, unreadable or not bound to the current baseline, **When** doctor or the launcher's status reports the source, **Then** it reads as operator `trust`, and the record never makes a checkout trusted or untrusted. [P: D-05] [S: IAC-4]

---

### User Story 5 - The governing documents say what changed (Priority: P2)

A maintainer reading the architecture finds the new rule in one place: which ADR clauses are superseded, how BL-INV-002 now reads, and what the operator's documentation says about `ballast trust`.

**Why this priority**: The change overrides an accepted ADR and amends a constitution invariant; without the records the implementation would silently contradict them.

**Independent Test**: Read the new ADR, ADR-0007, ADR-0011, the constitution and the user documentation; each states the setup-recorded baseline and its conditions consistently.

**Acceptance Scenarios**:

1. **AC-023**: **Given** the feature's PR, **When** a reviewer reads the architecture records, **Then** a new ADR records the decision and its conditions, ADR-0007's "setup never records trust" clause and ADR-0011's "preparation never reads or records a baseline" clause are marked superseded by it, and the roadmap's rule that setup cannot silently trust itself is updated to the new conditions. [B: D-01] [B: D-03] [S: docs/plans/2026-10-02-product-roadmap.md]
2. **AC-024**: **Given** the constitution, **When** a reviewer reads BL-INV-002, **Then** it says the launcher refuses until the operator trusts the current inputs or the operator's setup recorded them under the stated conditions, with the amendment's reason recorded. [B: D-01] [S: .specify/memory/constitution.md#governance]
3. **AC-025**: **Given** the user documentation, **When** an operator reads how to start work in a new checkout, **Then** it states when setup or preparation records the baseline, when `ballast trust` is still needed, and how `ballast doctor` shows the source. [S: docs/policies/documentation.md] [S: Issue #55 body]

---

### Edge Cases

- An unfinished setup attempt that the next setup recovers: the recovering setup applies the same conditions to the recovered installation, and an interrupted attempt never leaves a baseline behind. [S: docs/adr/0007-recoverable-installation.md#decision] [I]
- Run state lies outside the trust comparison, so it never changes the baseline; it only prevents setup from recording one. [S: tools/spec_workflow/launcher.py] [P: D-04]
- Two commands prepare the same worktree at once: only the one that installs may record, and the other reports that nothing needed preparing. [S: tools/setup] [I]
- The operator state location resolves where an agent can write: setup refuses as today and records nothing. [S: tools/spec_workflow/launcher.py]
- A primary checkout's `.git` directory is not a protected input, so only a linked worktree's pointer is checked. [S: tools/spec_workflow/launcher.py]

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `ballast setup`, run by the operator, MUST record the checkout's trust baseline after it installs and verifies the pinned standard when, and only when, every eligibility condition in FR-002 to FR-005 holds. [S: IAC-1] [B: D-01]
- **FR-002**: Every protected input MUST be exactly what setup's verified installation wrote; a protected input setup did not write or that differs from it MUST make the checkout ineligible. [S: IAC-2]
- **FR-003**: The working-tree `ballast.toml` and constitution MUST be committed, unchanged from `HEAD`, and equal to those on the default branch's remote-tracking ref or to those in the checkout's previous operator-recorded baseline; otherwise the checkout is ineligible. [S: IAC-2] [B: D-02] [B: D-06]
- **FR-004**: A linked worktree's `.git` pointer MUST name a worktree of the same repository whose default branch FR-003 compared against; otherwise the checkout is ineligible. [S: tools/spec_workflow/launcher.py] [I]
- **FR-005**: The checkout MUST be ineligible while an agent step's in-progress marker or a `BALLAST_TAMPERED` marker exists, while any saved run state exists in the checkout, or while a run in operator state is unfinished. [S: IAC-3] [P: D-04]
- **FR-006**: When the checkout is ineligible, setup MUST record no baseline, MUST leave any existing operator-recorded baseline untouched, MUST complete the installation exactly as it does today, and MUST say which condition failed and that `ballast trust` is needed after review. [S: IAC-2] [I]
- **FR-007**: The first-command preparation of a new worktree (#15) MUST record the worktree's baseline under the same conditions as setup, computed from the worktree's own inputs after its verified installation. [S: Issue #55 intake scope comment] [B: D-03]
- **FR-008**: Neither setup nor preparation MUST ever copy, inherit or reuse another checkout's baseline or a stale baseline left at the same path. [S: docs/adr/0011-worktree-preparation.md#rejected-alternatives] [I]
- **FR-009**: When an operator-recorded baseline already equals the checkout's current inputs, setup MUST leave it and its operator source unchanged. [I]
- **FR-010**: Each recorded baseline MUST carry, in operator state outside every agent's write authority, a provenance record of who recorded it (setup or operator `trust`), bound to that baseline; `ballast trust` MUST record operator provenance. [S: Issue #55 body] [P: D-05]
- **FR-011**: The launcher's `status --json` MUST report the baseline's source; a missing, unreadable or unbound provenance record MUST read as operator `trust`. [P: D-05] [S: docs/adr/0002-cli-standard-manifest.md]
- **FR-012**: `ballast doctor` MUST report how the current baseline was recorded, setup or operator `trust`, reading only the launcher's `status --json` and recomputing nothing. [S: IAC-1] [S: Issue #55 body] [S: docs/adr/0002-cli-standard-manifest.md]
- **FR-013**: The launcher's comparison before every `run`, `ledger` and `intake`, its refusal messages and the `BALLAST_TAMPERED` marker MUST NOT change; a provenance record MUST NOT affect whether a checkout is trusted. [S: IAC-4] [B: D-07]
- **FR-014**: When setup records a baseline it MUST say so in its output instead of asking for `ballast trust`. [S: IAC-1] [S: tools/setup]
- **FR-015**: A new ADR MUST record the decision and its conditions and supersede ADR-0007's "setup never records trust" clause and ADR-0011's "preparation never reads or records a baseline" clause; the roadmap rule that setup cannot silently trust itself MUST be updated to match. [B: D-01] [B: D-03] [S: AGENTS.md]
- **FR-016**: The constitution's BL-INV-002 MUST be amended to allow a setup-recorded baseline under the stated conditions, with the amendment's reason recorded per the constitution's governance. [B: D-01] [S: .specify/memory/constitution.md#governance]
- **FR-017**: The user documentation MUST describe when setup and preparation record a baseline, when `ballast trust` is still needed, and how doctor reports the source. [S: docs/policies/documentation.md]
- **FR-018**: Every tool changed by this feature MUST stay standard-library-only and run under `python3 -I -S`, and nothing it reads to decide eligibility MUST come from a file an agent can write without that change making the checkout ineligible. [S: AGENTS.md] [S: .specify/memory/constitution.md]

### Key Entities

- **Trust baseline**: the operator-state map of each protected input to its digest that the launcher compares before every run; unchanged in shape.
- **Baseline provenance**: an operator-state record beside the baseline saying whether setup or the operator's `ballast trust` recorded it, bound to that exact baseline.
- **Eligibility**: the set of conditions under which setup or preparation may record a baseline: inputs exactly as setup wrote them, reviewed committed configuration, a pointer into the same repository, and no agent trace.
- **Reviewed configuration reference**: the committed `ballast.toml` and constitution on the default branch's remote-tracking ref, or those in the checkout's previous operator-recorded baseline.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Starting work in a fresh clone or new issue worktree of a project on its default-branch configuration takes zero `ballast trust` commands, down from one per checkout.
- **SC-002**: In 100% of tested ineligible cases (uncommitted or unreviewed configuration, extra or edited protected input, foreign worktree pointer, unreadable reference, in-progress or tamper marker, saved run state), no baseline is recorded and the message names `ballast trust`.
- **SC-003**: 100% of the launcher's existing trust and refusal tests pass unchanged.
- **SC-004**: `ballast doctor` names the correct baseline source in every tested case, including a missing or mismatched provenance record.

## Non-goals

- Trusting a checkout after an agent step. [S: Issue #55 body]
- Trusting edits to `ballast.toml` or `[agents.permissions]` that no human reviewed, including uncommitted ones. [S: Issue #55 body] [B: D-06]
- Any change to the launcher's fail-closed comparison or the `BALLAST_TAMPERED` marker. [S: Issue #55 body] [B: D-07]
- Inheriting or copying another checkout's baseline. [S: docs/adr/0011-worktree-preparation.md#rejected-alternatives]

Every Issue acceptance criterion (IAC-1, IAC-2, IAC-3, IAC-4) is covered by an acceptance criterion above; none is a non-goal.

## Assumptions

- Setup and preparation record no baseline when saved run state exists in the checkout or an operator-state run is unfinished, in addition to the in-progress and tamper markers; such checkouts keep needing `ballast trust` (D-04, agent-provisional). [P: D-04]
- The baseline's source is a provenance record in operator state beside the baseline, bound to its digest and reported by the launcher's `status --json`; a missing or mismatched record reads as operator `trust` (D-05, agent-provisional). [P: D-05]
- A commit on a feature branch is not by itself evidence that a human reviewed it; only the default branch's remote-tracking ref, reached through a reviewed merge, or the operator's own earlier baseline counts as reviewed. [I]
- Setup reads the default branch's remote-tracking ref as it stands locally and does not fetch; a stale ref makes a newly merged change ineligible until the next fetch, which only removes convenience. [I]
- A no-op setup on an installed, eligible checkout with no baseline records one, since its inputs are exactly what a verified installation holds. [I]
- A linked worktree's `.git` pointer, written by Git rather than setup, is acceptable only when it points into the same repository, since it is the one protected input setup cannot write. [I]
