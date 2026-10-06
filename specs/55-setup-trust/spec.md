# Feature Specification: Setup trusts a checkout it just installed

**Feature Branch**: `feat/55-setup-trust`

**Created**: 2026-10-06

**Status**: Draft

**Input**: User description: "Issue #55: a checkout whose protected inputs are exactly what a trusted ballast setup just produced is trusted without a separate operator command."

**Tracking**: [Ballast #55](https://github.com/Hugo-Grellier/ballast/issues/55), child of Epic #11, milestone v1.0; [product roadmap](../../docs/plans/2026-10-02-product-roadmap.md) phase 2; [technical spec §9.1](../TECHNICAL-SPEC.md#91-v10-target). Related: recoverable installs ([#14](../14-recoverable-install/spec.md)), new-worktree preparation ([#15](../15-worktree-setup/spec.md)) and the launcher's branch synchronization ([#18](../18-branch-sync/spec.md), [ADR-0005](../../docs/adr/0005-launcher-branch-synchronization.md)). Written from the [discovery brief](discovery.md).

**Risk**: R2. It changes the launcher's trust model and who may record a trust baseline, two boundaries in [`docs/policies/project/workflow.md`](../../docs/policies/project/workflow.md#r2-boundaries).

**Mode**: Autonomous run `38380ec3`. The operator settled the three design questions D-01, D-02 and D-03 in their answers to an earlier run's discovery block, recorded in the brief. Two agent inferences only narrow the operator's D-02 answer and are listed for merge review: the default branch is observed through the pinned repository rather than a local ref an agent can move, and only a repository the operator already reviewed counts. Every other decision on this feature is agent-provisional, and merging its PR is the only human approval of the R2 change.

## Context

The launcher refuses `ballast run`, `ballast ledger` and `ballast intake` until a trust baseline in operator state matches the checkout's protected inputs: `ballast.toml`, `.ballast/spec_workflow`, `.specify`, `.venv` and a linked worktree's `.git` pointer. Today only the operator's `ballast trust` writes that baseline, so every fresh clone, issue worktree and pilot repository costs one human command, even when every protected input was just written by the operator's own `ballast setup` of the pinned standard and no agent has run there.

This feature lets setup, and the first-command preparation of a new worktree (#15), record the baseline itself when the checkout holds exactly what setup produced, the committed `ballast.toml` and constitution are ones a human already reviewed, and no agent has run in the checkout. "Reviewed" means equal to the files on the default branch of the repository pinned in `ballast.toml`, as observed live from that repository with the operator's own Git authority, or equal to the files in the checkout's previous operator-recorded baseline. Everything else still needs an explicit `ballast trust`. The launcher's comparison before every run does not change, and `ballast doctor` says who recorded the baseline.

The operator chose this direction knowing it conflicts with two accepted rules: ADR-0007 says setup never records trust, and the constitution's BL-INV-002 says the launcher refuses until the operator trusts the inputs. The operator chose to supersede that ADR-0007 clause with a new ADR and to amend BL-INV-002 so a setup-recorded baseline under the stated conditions also counts (D-01). The same ADR supersedes ADR-0011's rule that preparation never reads or records a baseline.

## User Scenarios & Testing *(mandatory)*

Give each acceptance scenario a stable ID (`AC-001`, `AC-002`, ...). Task and test descriptions cite the IDs they satisfy, so review can trace each criterion to evidence.

### User Story 1 - Set up a clean checkout and start a run with no `ballast trust` (Priority: P1)

The operator clones a project at its released pin, or checks out its default branch, and runs `ballast setup`. Setup installs the pinned standard, sees that the checkout holds exactly what it wrote and that the committed configuration matches the pinned repository's default branch, and records the trust baseline itself. The operator, or an agent driving work for them, then starts `ballast run` with no other command.

**Why this priority**: This is the Issue's main outcome; it removes one human touch per checkout.

**Independent Test**: In a clean clone whose `ballast.toml` and constitution equal those on the pinned repository's default branch, run `ballast setup`, then `ballast run start`; the launcher accepts the checkout, no `ballast trust` ran, and `ballast doctor` reports that setup recorded the baseline.

**Acceptance Scenarios**:

1. **AC-001**: **Given** a clean checkout whose committed `ballast.toml` and constitution equal those on the default branch of the repository pinned in `ballast.toml`, as observed from that repository during this setup, where that repository is in the operator's record of reviewed repositories, with no run state and no tamper marker, **When** the operator runs `ballast setup` and it installs and verifies the pinned standard, **Then** setup records a trust baseline for the checkout's protected inputs and says it did so. [S: IAC-1] [B: D-01] [B: D-02]
2. **AC-002**: **Given** a baseline setup just recorded, **When** `ballast run start` (or `ballast ledger` or `ballast intake`) runs with no `ballast trust` in between, **Then** the launcher accepts the checkout through its unchanged comparison. [S: IAC-1] [S: IAC-4]
3. **AC-003**: **Given** a baseline setup recorded, **When** the operator runs `ballast doctor`, **Then** its trust check reports that setup recorded the baseline; **and given** a baseline the operator recorded with `ballast trust`, **Then** it reports operator `trust`. [S: IAC-1] [S: Issue #55 body] [P: D-05]
4. **AC-004**: **Given** a checkout whose committed `ballast.toml` and constitution differ from the pinned repository's default branch but equal those in the checkout's previous operator-recorded baseline, **When** `ballast setup` runs and the other conditions hold, **Then** setup records the baseline. [B: D-02] [S: IAC-1]
5. **AC-005**: **Given** an installed checkout with no baseline whose inputs are current, **When** `ballast setup` reports that nothing changed and every condition holds, **Then** it records the baseline; **and given** the checkout already has an operator-recorded baseline equal to its current inputs, **Then** setup leaves that baseline and its operator source untouched. [S: tools/setup] [I]

---

### User Story 2 - A new worktree is trusted by its first command (Priority: P1)

An agent driving work for the operator creates an issue worktree and runs its first `ballast run`. Preparation (#15) installs the worktree from a verified local installation and, under the same conditions as setup, records the worktree's baseline, so the run starts with no human step.

**Why this priority**: Issue worktrees are where the repeated human touch costs most; the Issue puts the #15 path in scope and the operator chose that preparation records a baseline (D-03).

**Independent Test**: Create a linked worktree of a trusted project on a branch whose `ballast.toml` and constitution equal the pinned repository's default branch, then run `ballast run start`; preparation installs, records the baseline, and the run starts with no `ballast trust`.

**Acceptance Scenarios**:

1. **AC-006**: **Given** a new linked worktree whose committed `ballast.toml` and constitution equal those on the pinned repository's default branch, as observed from that repository during preparation, where that repository is in the operator's record of reviewed repositories, with no run state and no tamper marker, **When** its first `ballast run`, `ledger` or `intake` prepares it from a verified local installation, **Then** preparation records the worktree's baseline and the command proceeds without `ballast trust`. [S: Issue #55 intake scope comment] [B: D-03] [B: D-02] [S: IAC-1]
2. **AC-007**: **Given** a new worktree whose branch changed `ballast.toml` or the constitution, **When** its first command prepares it, **Then** preparation installs it, records no baseline, and the launcher refuses with a message naming `ballast trust`. [S: IAC-2] [B: D-02] [B: D-03]
3. **AC-008**: **Given** a stale baseline left in operator state at a reused checkout path, **When** preparation installs the worktree, **Then** the stale baseline is never reused as-is: it is removed, and a new one is recorded only when every condition holds. [S: tools/setup] [S: docs/adr/0011-worktree-preparation.md#rejected-alternatives] [I]
4. **AC-009**: **Given** another checkout's baseline, **When** setup or preparation records a baseline, **Then** it computes it from this checkout's own inputs and never copies or inherits another checkout's baseline. [S: docs/adr/0011-worktree-preparation.md#rejected-alternatives] [B: D-03]

---

### User Story 3 - A checkout that differs from what setup produced still needs `ballast trust` (Priority: P1)

When anything in the checkout is not exactly what setup wrote from reviewed configuration, or the reviewed configuration cannot be observed, setup installs as it does today, records nothing, and tells the operator to review the inputs and run `ballast trust`.

**Why this priority**: Without this, an unreviewed change, such as an agent widening `[agents.permissions]`, would be trusted silently; it is the feature's safety boundary.

**Independent Test**: For each differing or unobservable input below, run `ballast setup` and check that no baseline exists afterwards, setup's message names the reason and `ballast trust`, and `ballast run start` is refused.

**Acceptance Scenarios**:

1. **AC-010**: **Given** a `ballast.toml` or constitution with uncommitted changes, such as a pin bump an agent wrote, **When** `ballast setup` runs, **Then** it records no baseline and says `ballast trust` is needed after review. [S: IAC-2] [B: D-06]
2. **AC-011**: **Given** a committed `ballast.toml` or constitution that differs from both the pinned repository's default branch and the previous operator-recorded baseline, such as widened `[agents.permissions]` on a feature branch, **When** `ballast setup` runs, **Then** it records no baseline and says `ballast trust` is needed after review. [S: IAC-2] [B: D-02]
3. **AC-012**: **Given** a protected input setup did not write, such as an extra or edited file under `.specify` or `.ballast/spec_workflow`, **When** `ballast setup` runs, **Then** it records no baseline and says `ballast trust` is needed after review. [S: IAC-2]
4. **AC-013**: **Given** a linked worktree whose `.git` pointer does not name a worktree entry of the local repository the checkout belongs to, **When** setup or preparation runs, **Then** it records no baseline and says `ballast trust` is needed. [S: IAC-2] [S: tools/spec_workflow/launcher.py] [I]
5. **AC-014**: **Given** the pinned repository's default branch cannot be observed, because the machine is offline, the operator's Git authority is missing or refused, `[github] repository` is absent or malformed, or the repository cannot be read, and the checkout has no previous operator-recorded baseline whose files match, **When** setup or preparation runs, **Then** it records no baseline and says `ballast trust` is needed. [B: D-02] [S: IAC-2]
6. **AC-015**: **Given** a local default-branch ref, `origin` remote or other repository setting in the checkout's Git configuration that an agent moved or repointed so it shows the changed `ballast.toml` as the default branch, **When** setup or preparation runs, **Then** the comparison ignores those local settings, asks only the repository pinned in `ballast.toml`, and records no baseline. [B: D-02] [S: docs/adr/0005-launcher-branch-synchronization.md] [S: IAC-2]
7. **AC-016**: **Given** a committed `ballast.toml` whose `[github] repository` was changed to name a different repository whose default branch carries that same changed file, **When** setup or preparation runs, **Then** it records no baseline and says `ballast trust` is needed after review, because that repository is not in the operator's record of reviewed repositories, or because that exact configuration was not reviewed for it. The same holds for the first checkout of any project whose repository the operator never trusted on this machine. [S: IAC-2] [S: Issue #55 body] [B: D-02] [I]
8. **AC-017**: **Given** setup records no baseline for any reason, **When** it finishes, **Then** its message names the reason and `ballast trust`, the installation itself succeeds or fails exactly as it does today, and any baseline the operator recorded earlier is left untouched. [S: IAC-2] [S: tools/setup] [I]

---

### User Story 4 - An agent step can never lead to a recorded baseline (Priority: P1)

Once an agent has run in a checkout, or might still be running, setup and preparation refuse to record a baseline. A checkout that changes after a setup-recorded baseline is refused by the launcher exactly as today.

**Why this priority**: It keeps an agent from gaining authority its caller never reviewed, a constitution invariant.

**Independent Test**: With an in-progress marker, with a tamper marker, and with saved run state, run `ballast setup` and preparation and check that no baseline is recorded; then, after a setup-recorded baseline, edit a file under `.specify` and check `ballast run start` fails closed.

**Acceptance Scenarios**:

1. **AC-018**: **Given** an agent step's in-progress marker in operator state, **When** `ballast setup` or preparation runs, **Then** it records no baseline and names the remedy. [S: IAC-3]
2. **AC-019**: **Given** a `BALLAST_TAMPERED` marker, **When** `ballast setup` or preparation runs, **Then** it records no baseline and names the remedy. [S: IAC-3]
3. **AC-020**: **Given** saved run state from earlier runs in the checkout, or an unfinished run in operator state, **When** `ballast setup` or preparation runs, **Then** it records no baseline and says `ballast trust` is needed after review. [S: IAC-3] [P: D-04]
4. **AC-021**: **Given** an agent running a workflow step, **When** it starts setup or preparation, **Then** neither records a baseline, because a step always holds the in-progress marker and setup refuses on it. [S: IAC-3] [S: AGENTS.md]
5. **AC-022**: **Given** a baseline setup recorded, **When** any protected input later changes, such as an agent editing `.specify` scripts, **Then** the next `ballast run`, `ledger` or `intake` fails closed with the same refusal as today. [S: IAC-4]
6. **AC-023**: **Given** the launcher's existing trust and refusal tests, **When** the feature is complete, **Then** they pass unchanged, and the launcher's comparison and tamper marker behave as before. [S: IAC-4] [B: D-07]
7. **AC-024**: **Given** a provenance record that is missing, unreadable or not bound to the current baseline, **When** doctor or the launcher's status reports the source, **Then** it reads as operator `trust`, and the record never makes a checkout trusted or untrusted. [P: D-05] [S: IAC-4]

---

### User Story 5 - The governing documents say what changed (Priority: P2)

A maintainer reading the architecture finds the new rule in one place: which ADR clauses are superseded, how BL-INV-002 now reads, and what the operator's documentation says about `ballast trust`.

**Why this priority**: The change overrides an accepted ADR and amends a constitution invariant; without the records the implementation would silently contradict them.

**Independent Test**: Read the new ADR, ADR-0007, ADR-0011, the constitution and the user documentation; each states the setup-recorded baseline and its conditions consistently.

**Acceptance Scenarios**:

1. **AC-025**: **Given** the feature's PR, **When** a reviewer reads the architecture records, **Then** a new ADR records the decision and its conditions, including how the pinned repository's default branch is observed, ADR-0007's "setup never records trust" clause and ADR-0011's "preparation never reads or records a baseline" clause are marked superseded by it, and the roadmap's rule that setup cannot silently trust itself is updated to the new conditions. [B: D-01] [B: D-02] [B: D-03] [S: docs/plans/2026-10-02-product-roadmap.md]
2. **AC-026**: **Given** the constitution, **When** a reviewer reads BL-INV-002, **Then** it says the launcher refuses until the operator trusts the current inputs or the operator's setup recorded them under the stated conditions, with the amendment's reason recorded. [B: D-01] [S: .specify/memory/constitution.md#governance]
3. **AC-027**: **Given** the user documentation, **When** an operator reads how to start work in a new checkout, **Then** it states when setup or preparation records the baseline, that doing so needs network access and the operator's Git authority for the pinned repository, when `ballast trust` is still needed, and how `ballast doctor` shows the source. [S: docs/policies/documentation.md] [S: Issue #55 body] [B: D-02]

---

### Edge Cases

- An unfinished setup attempt that the next setup recovers: the recovering setup applies the same conditions to the recovered installation, and an interrupted attempt never leaves a baseline behind. [S: docs/adr/0007-recoverable-installation.md#decision] [I]
- Run state lies outside the trust comparison, so it never changes the baseline; it only prevents setup from recording one. [S: tools/spec_workflow/launcher.py] [P: D-04]
- Two commands prepare the same worktree at once: only the one that installs may record, and the other reports that nothing needed preparing. [S: tools/setup] [I]
- The operator state location resolves where an agent can write: setup refuses as today and records nothing. [S: tools/spec_workflow/launcher.py]
- A primary checkout's `.git` directory is not a protected input, so only a linked worktree's pointer is checked. [S: tools/spec_workflow/launcher.py]
- The pinned repository's default branch moves between the observation and the recording: the baseline reflects the observation made in the same invocation; a later merge is picked up by the next setup. [B: D-02] [I]
- A slow or hanging network request: observing the default branch never prompts for credentials and gives up within a bounded time, which counts as unobservable and records no baseline. [B: D-02] [I]

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `ballast setup`, run by the operator, MUST record the checkout's trust baseline after it installs and verifies the pinned standard when, and only when, every eligibility condition in FR-002 to FR-006 holds. [S: IAC-1] [B: D-01]
- **FR-002**: Every protected input MUST be exactly what setup's verified installation wrote; a protected input setup did not write or that differs from it MUST make the checkout ineligible. [S: IAC-2]
- **FR-003**: The working-tree `ballast.toml` and constitution MUST be committed, unchanged from `HEAD`, and equal in content to those on the default branch of the repository pinned in `ballast.toml` `[github] repository`, or to those in the checkout's previous operator-recorded baseline; otherwise the checkout is ineligible. [S: IAC-2] [B: D-02] [B: D-06]
- **FR-004**: The pinned repository's default branch and its files MUST be observed live during the same setup or preparation, from that repository only and with the operator's own Git authority, by the same trusted path the launcher uses for branch synchronization; no local ref, remote, URL or other setting from the checkout's Git configuration MAY name the repository, its default branch or the files compared. When the observation fails for any reason, the default-branch alternative of FR-003 MUST count as unmet. [B: D-02] [S: docs/adr/0005-launcher-branch-synchronization.md] [I]
- **FR-005**: Changing `[github] repository` MUST NOT by itself make a checkout eligible: a committed `ballast.toml` whose pinned repository differs from the one a human reviewed MUST be ineligible, even when the newly named repository's default branch carries the same file. The default-branch alternative of FR-003 MUST count only for a repository in the operator-state record of reviewed repositories. Only `ballast trust` writes that record: it adds the repository named in the `ballast.toml` it trusts, and, since DEC-0008, the digests of that `ballast.toml` and the constitution as reviewed for that repository, and nothing else (no checkout path). The default-branch alternative counts only when the files setup observes equal a pair reviewed for that same repository. [S: IAC-2] [S: Issue #55 body] [B: D-02] [I]
- **FR-006**: A linked worktree's `.git` pointer MUST name a worktree entry of the local repository the checkout belongs to; otherwise the checkout is ineligible. [S: tools/spec_workflow/launcher.py] [I]
- **FR-007**: The checkout MUST be ineligible while an agent step's in-progress marker or a `BALLAST_TAMPERED` marker exists, while any saved run state exists in the checkout, or while a run in operator state is unfinished. [S: IAC-3] [P: D-04]
- **FR-008**: When the checkout is ineligible, setup MUST record no baseline, MUST leave any existing operator-recorded baseline untouched, MUST complete the installation exactly as it does today, and MUST say which condition failed and that `ballast trust` is needed after review. [S: IAC-2] [I]
- **FR-009**: The first-command preparation of a new worktree (#15) MUST record the worktree's baseline under the same conditions as setup, computed from the worktree's own inputs after its verified installation. [S: Issue #55 intake scope comment] [B: D-03]
- **FR-010**: Neither setup nor preparation MUST ever copy, inherit or reuse another checkout's baseline or a stale baseline left at the same path. [S: docs/adr/0011-worktree-preparation.md#rejected-alternatives] [I]
- **FR-011**: When an operator-recorded baseline already equals the checkout's current inputs, setup MUST leave it and its operator source unchanged. [I]
- **FR-012**: Each recorded baseline MUST carry, in operator state outside every agent's write authority, a provenance record of who recorded it (setup or operator `trust`), bound to that baseline; `ballast trust` MUST record operator provenance. [S: Issue #55 body] [P: D-05]
- **FR-013**: The launcher's `status --json` MUST report the baseline's source; a missing, unreadable or unbound provenance record MUST read as operator `trust`. [P: D-05] [S: docs/adr/0002-cli-standard-manifest.md]
- **FR-014**: `ballast doctor` MUST report how the current baseline was recorded, setup or operator `trust`, reading only the launcher's `status --json` and recomputing nothing. [S: IAC-1] [S: Issue #55 body] [S: docs/adr/0002-cli-standard-manifest.md]
- **FR-015**: The launcher's comparison before every `run`, `ledger` and `intake`, its refusal messages and the `BALLAST_TAMPERED` marker MUST NOT change; a provenance record MUST NOT affect whether a checkout is trusted. [S: IAC-4] [B: D-07]
- **FR-016**: When setup records a baseline it MUST say so in its output instead of asking for `ballast trust`. [S: IAC-1] [S: tools/setup]
- **FR-017**: A new ADR MUST record the decision and its conditions, including how the default branch is observed, and supersede ADR-0007's "setup never records trust" clause and ADR-0011's "preparation never reads or records a baseline" clause; the roadmap rule that setup cannot silently trust itself MUST be updated to match. [B: D-01] [B: D-02] [B: D-03] [S: AGENTS.md]
- **FR-018**: The constitution's BL-INV-002 MUST be amended to allow a setup-recorded baseline under the stated conditions, with the amendment's reason recorded per the constitution's governance. [B: D-01] [S: .specify/memory/constitution.md#governance]
- **FR-019**: The user documentation MUST describe when setup and preparation record a baseline, the network and Git authority that needs, when `ballast trust` is still needed, and how doctor reports the source. [S: docs/policies/documentation.md] [B: D-02]
- **FR-020**: Every tool changed by this feature MUST stay standard-library-only and run under `python3 -I -S`; nothing it reads to decide eligibility MAY come from a file an agent can write unless a change to that file makes the checkout ineligible, and no program named by the checkout's Git configuration, attributes or hooks MAY run. [S: AGENTS.md] [S: .specify/memory/constitution.md] [S: docs/adr/0005-launcher-branch-synchronization.md]

### Key Entities

- **Trust baseline**: the operator-state map of each protected input to its digest that the launcher compares before every run; unchanged in shape.
- **Baseline provenance**: an operator-state record beside the baseline saying whether setup or the operator's `ballast trust` recorded it, bound to that exact baseline.
- **Eligibility**: the set of conditions under which setup or preparation may record a baseline: inputs exactly as setup wrote them, reviewed committed configuration, a pointer into the same local repository, and no agent trace.
- **Reviewed configuration reference**: the `ballast.toml` and constitution on the default branch of the pinned repository, observed live with the operator's Git authority, or those in the checkout's previous operator-recorded baseline.
- **Reviewed repositories**: an operator-state record, written only by `ballast trust`, of the repositories named in `ballast.toml` files the operator trusted on this machine; it holds identities and, per repository, the digests of the `ballast.toml` and constitution reviewed for it, and decides which pinned repository's default branch counts as reviewed.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Starting work in a fresh clone or new issue worktree of a project on its default-branch configuration, with network access, takes zero `ballast trust` commands once the operator has trusted that project's repository on the machine, down from one per checkout.
- **SC-002**: In 100% of tested ineligible cases (uncommitted or unreviewed configuration, a repointed pinned repository, a moved local ref or remote, an unobservable default branch, an extra or edited protected input, a foreign worktree pointer, an in-progress or tamper marker, saved run state), no baseline is recorded and the message names `ballast trust`.
- **SC-003**: 100% of the launcher's existing trust and refusal tests pass unchanged.
- **SC-004**: `ballast doctor` names the correct baseline source in every tested case, including a missing or mismatched provenance record.

## Non-goals

- Trusting a checkout after an agent step. [S: Issue #55 body]
- Trusting edits to `ballast.toml` or `[agents.permissions]` that no human reviewed, including uncommitted ones. [S: Issue #55 body] [B: D-06]
- Any change to the launcher's fail-closed comparison or the `BALLAST_TAMPERED` marker. [S: Issue #55 body] [B: D-07]
- Inheriting or copying another checkout's baseline. [S: docs/adr/0011-worktree-preparation.md#rejected-alternatives]
- Recording a baseline offline: without a live observation of the pinned repository and no matching operator baseline, `ballast trust` stays the path. [B: D-02]
- Recording a baseline in the first checkout of a project whose repository the operator has never trusted on the machine: that checkout needs one `ballast trust`, which also records the repository as reviewed (agent inference narrowing D-02, listed for merge review). [I]

Every Issue acceptance criterion (IAC-1, IAC-2, IAC-3, IAC-4) is covered by an acceptance criterion above. IAC-1 is narrowed only for the first checkout of a never-trusted repository, as stated in the non-goal above.

## Assumptions

- Setup and preparation record no baseline when saved run state exists in the checkout or an operator-state run is unfinished, in addition to the in-progress and tamper markers; such checkouts keep needing `ballast trust` (D-04, agent-provisional). [P: D-04]
- The baseline's source is a provenance record in operator state beside the baseline, bound to its digest and reported by the launcher's `status --json`; a missing or mismatched record reads as operator `trust` (D-05, agent-provisional). [P: D-05]
- A commit on a feature branch is not by itself evidence that a human reviewed it; only the pinned repository's default branch, reached through a reviewed merge, or the operator's own earlier baseline counts as reviewed. [I]
- The default branch is observed live from the pinned repository, never from a local remote-tracking ref, because the checkout's refs and Git configuration are agent-writable. This is an agent inference that only narrows the operator's D-02 answer (anything unobservable means not eligible), and it is listed for merge review. [B: D-02] [I]
- The repository named in `[github] repository` is itself part of the reviewed configuration: a checkout that repoints it is treated like any other unreviewed `ballast.toml` change. Nothing inside the checkout can tell the reviewed repository from a repointed one, since a repointed repository's default branch can carry the same changed file. So setup and preparation count the default-branch alternative only for a repository the operator already reviewed: one named in the `ballast.toml` of a baseline the operator recorded with `ballast trust` on this machine, in any checkout. Only `ballast trust` writes that record of reviewed repositories, in operator state. It holds repository identities and, per repository, the digests of the `ballast.toml` and constitution the operator trusted (DEC-0008), so a repository counts only for the exact configuration reviewed for it and no checkout's baseline is inherited (FR-010). The first checkout of a project on a machine therefore still needs one `ballast trust`. After that, fresh clones and new worktrees of that project need none. This is an agent inference that only narrows the operator's D-02 answer, is reversible by dropping the record, and is listed for merge review. [B: D-02] [I]
- A no-op setup on an installed, eligible checkout with no baseline records one, since its inputs are exactly what a verified installation holds. [I]
- A linked worktree's `.git` pointer, written by Git rather than setup, is acceptable only when it points into the same local repository, since it is the one protected input setup cannot write. [I]
