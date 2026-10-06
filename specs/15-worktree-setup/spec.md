# Feature Specification: Prepare a new worktree on first Ballast use

**Feature Branch**: `feat/15-worktree-setup`

**Created**: 2026-10-06

**Status**: Draft

**Input**: User description: "Issue #15: An operator can create multiple worktrees without manually repeating ballast setup in each one."

**Tracking**: [Ballast #15](https://github.com/Hugo-Grellier/ballast/issues/15), a leaf of the [Ballast 1.0 Epic](https://github.com/Hugo-Grellier/ballast/issues/11); roadmap Priority 1 ([product roadmap](../../docs/plans/2026-10-02-product-roadmap.md)); [v1.0 target](../TECHNICAL-SPEC.md#91-v10-target). Blocked by #14, delivered as [`specs/14-recoverable-install`](../14-recoverable-install/spec.md). Input evidence: [discovery brief](discovery.md).

**Risk**: R2. The feature changes which paths are installed into a checkout, when, and from where, and what the launcher reports about trust. This run is Autonomous: the pre-change approval is agent-provisional and merging the PR is the single human approval.

## Context

An operator who runs several feature runs in parallel gives each one its own Git worktree of the same adopted repository. Today every new worktree needs an explicit `ballast setup` before anything else works: any other `ballast` command in an uninstalled worktree stops and tells the operator to run setup. Setup itself copies the primary checkout's installation when the copy verifies against the primary's installation record and the configuration matches; otherwise it performs a full installation, which downloads Spec Kit sources again even when an identical, verified installation already exists in a sibling worktree on the same machine.

Feature 14 made installations recoverable and content-verified, and explicitly left automatic worktree preparation to this Issue. This feature lets the first `ballast` command that needs an installation in a new worktree build it from what is already verified on this machine, with no separate setup step and no network access, and then stop at the launcher's preflight with a precise statement of the trust that worktree still needs.

It does not copy run state between checkouts, treat a different pin or configuration as equivalent, or record or inherit a trust baseline on the operator's behalf (#55).

## User Scenarios & Testing *(mandatory)*

Give each acceptance scenario a stable ID (`AC-001`, `AC-002`, ...). Task and test descriptions cite the IDs they satisfy, so review can trace each criterion to evidence.

### User Story 1 - A new worktree reaches preflight on its first command (Priority: P1)

An operator creates a new worktree of a project whose pin already has a verified installation on this machine, in the primary checkout or in another worktree. Without running `ballast setup`, they start a feature run there. Ballast prepares the worktree's installation from the verified local copy, with no download, and the launcher's preflight then tells them exactly what remains: this worktree has no trusted baseline yet, which protected inputs to review, and that `ballast trust` is the next step. After they trust it, the run starts as in any installed checkout.

**Why this priority**: This is the main outcome of the Issue. Repeating setup in every worktree is the friction that makes parallel feature runs costly, and a full reinstall per worktree also needs the network.

**Independent Test**: In a disposable project with an installed, verified primary checkout, create a new worktree, block network access, run `ballast run start` there, and check that a complete installation appeared, no network request was made, and the command stopped at the trust preflight with the expected message; then run `ballast trust` and confirm the run starts.

**Acceptance Scenarios**:

1. **AC-001**: **Given** a primary checkout with a verified installation at pin X, and a new worktree of the same repository at pin X with the same `ballast.toml` and no installation, **When** the operator runs a command that needs the installation (`ballast run`, `ballast ledger` or `ballast intake`) in the new worktree with network access blocked, **Then** the worktree receives a complete installation identical to the verified source, no network request is made, no separate setup command was run, and the command reaches the launcher's preflight. [S: IAC-1] [P: D-03] [P: D-04]
2. **AC-002**: **Given** a worktree whose installation was just prepared by its first command, **When** the launcher's preflight runs, **Then** it refuses with a message stating that this worktree has no trusted baseline, naming the protected inputs to review and `ballast trust` as the next action, and no trust baseline is recorded for the worktree. [S: IAC-1] [S: Issue #15 body] [B: D-02]
3. **AC-003**: **Given** the primary checkout is at another pin or configuration but a sibling worktree or the kept previous installation holds a verified installation that matches the new worktree's pin and `ballast.toml`, **When** the first command runs in the new worktree, **Then** the installation is prepared from that matching source without a network request. [S: IAC-1] [P: D-03]
4. **AC-004**: **Given** a worktree prepared on its first command, **When** the operator runs `ballast doctor` and later `ballast trust` followed by the same run command, **Then** doctor reports an installation that is current and verified for the pin, and the run command proceeds past preflight without preparing the installation again. [S: IAC-1] [I]
5. **AC-005**: **Given** a new worktree with no installation, **When** the operator runs `ballast trust` or `ballast discard-runs` there, **Then** the command installs nothing, records no baseline, and refuses with a message naming how to install; and when the operator runs `ballast doctor`, `ballast status` or `ballast preview`, nothing in the worktree changes. [P: D-04]
6. **AC-006**: **Given** a worktree that already holds an installation that is stale, modified or for another pin, **When** a command that needs the installation runs there, **Then** no preparation from a local source happens and the existing refusal naming `ballast setup` stands. [P: D-05]
7. **AC-007**: **Given** a worktree pinned to a standard version that predates this feature, **When** a command that needs the installation runs in that worktree with no installation, **Then** the command keeps today's refusal naming `ballast setup` and makes no network request. [S: Issue #15 body] [I]

---

### User Story 2 - Nothing is reused across a different pin, configuration or content (Priority: P1)

The operator's worktrees are not all alike: one branch pins an older version, another adds agent permission rules to `ballast.toml`, and an installation somewhere on the machine may have been edited by hand. A new worktree only ever receives an installation that was built for exactly its pin and configuration and that still matches its installation record, file modes included. No worktree reuses another checkout's trust baseline, even when their protected inputs are byte-identical.

**Why this priority**: Reusing a mismatched installation would run code or agent permissions the project never pinned, and reusing a trust baseline would bypass the operator's review. Without these guarantees User Story 1 is unsafe to ship.

**Independent Test**: Set up sources at one pin and configuration, then create worktrees that differ in pin, in `[agents.permissions]`, and against a source whose content or file mode was altered after its record was taken; run the first command in each and check that no mismatched installation was used, that nothing was downloaded, and that each refusal names the reason; check that a worktree identical to a trusted primary still has no baseline.

**Acceptance Scenarios**:

1. **AC-008**: **Given** verified installations on this machine only at pin X, **When** the first command runs in a new worktree pinned to Y, **Then** the worktree never receives the pin-X installation, makes no network request, and refuses naming `ballast setup` for pin Y. [S: IAC-2] [B: D-01]
2. **AC-009**: **Given** a verified source installation whose `ballast.toml` differs from the new worktree's, including only in its `[agents.permissions]` rules, **When** the first command runs in the new worktree, **Then** that source, including its generated agent settings, is not used. [S: IAC-2] [P: D-06]
3. **AC-010**: **Given** a candidate source whose installed content differs from its installation record (a file added, missing or altered) or whose copied files' executable bits differ from what its version builds, **When** the first command runs in a new worktree, **Then** that source is not used, the worktree is left without a partial installation from it, and the outcome names why the source was rejected. [S: IAC-2] [P: D-06]
4. **AC-011**: **Given** a candidate source whose own setup is unfinished or in progress, **When** the first command runs in a new worktree, **Then** that source is not used. [S: IAC-2] [P: D-03]
5. **AC-012**: **Given** a primary checkout with a recorded trust baseline and a new worktree whose protected inputs are byte-identical to the primary's, **When** the first command prepares the worktree's installation, **Then** the primary's or any sibling's baseline is never consulted, copied or recorded for the worktree, and preflight refuses until the operator trusts this worktree. [S: IAC-2] [B: D-02] [S: Issue #15 intake scope comment]
6. **AC-013**: **Given** the per-machine copy of the pinned standard version is damaged, **When** the first command runs in a new worktree at that pin, **Then** the command refuses naming the damaged path, as setup does, and fetches nothing. [S: IAC-2] [I]
7. **AC-014**: **Given** any preparation, successful or not, **When** it finishes, **Then** the worktree's `ballast.toml`, constitution and `docs/policies/project/` are unchanged, and the source checkout's files, installation record, run state and trust baseline are byte-identical to before. [S: Issue #15 body] [S: Issue #15 intake scope comment] [I]

---

### User Story 3 - Many worktrees stay independent through concurrency, interruption and retry (Priority: P1)

The operator creates ten worktrees at once, on two pins, and starts runs in all of them. Each one prepares its own installation and keeps its own run state, trust baseline and setup bookkeeping; work in one never changes another. If a preparation is killed halfway, the next command in that worktree finishes or undoes it and the operator simply retries. If no verified installation for a worktree's pin exists yet, the command says so and names `ballast setup`; once setup has run in one worktree at that pin, the others prepare from it.

**Why this priority**: The Issue's acceptance criteria require the parallel case and its failure modes; a feature that works for one worktree but interleaves or loses state at ten does not deliver the outcome.

**Independent Test**: Create ten worktrees across two pins with a verified source for each, start their first commands concurrently, then advance a run in one and compare the others' state; kill a preparation at several points and rerun; remove the matching source for one pin and run the first command there.

**Acceptance Scenarios**:

1. **AC-015**: **Given** ten new worktrees of one repository across two pins, with a verified installation available locally for each pin, **When** their first commands run concurrently, **Then** each worktree ends with a complete installation for exactly its own pin and configuration, no network request is made, and each stops at its own trust preflight. [S: IAC-3] [S: IAC-1] [P: D-03]
2. **AC-016**: **Given** the ten worktrees of AC-015, **When** a run is started, advanced or discarded in one of them, **Then** the run state, trust baseline, in-progress marker, setup journal and checkout lock of every other worktree and of the source checkouts are unchanged, and no worktree received run state from another checkout. [S: IAC-3] [S: Issue #15 body]
3. **AC-017**: **Given** a new worktree whose pin and configuration have no verified installation on this machine, **When** its first command runs, **Then** the command makes no network request, leaves no partial installation, and refuses naming `ballast setup`; and after the operator runs `ballast setup` in that worktree, a later new worktree at the same pin and configuration is prepared from it without a network request. [S: IAC-3] [B: D-01] [P: D-03]
4. **AC-018**: **Given** a preparation killed at any point before, during or after placing the installation, **When** the next command that needs the installation runs in that worktree, **Then** it completes or rolls back the interrupted attempt, never leaves a mix of old and new files, and says which it did. [S: IAC-3] [P: D-05]
5. **AC-019**: **Given** a preparation that failed or was interrupted, or a missing source that was later provided, **When** the operator reruns the command, **Then** the worktree ends with the same installation an uninterrupted first preparation would have produced. [S: IAC-3]
6. **AC-020**: **Given** two commands that need the installation start at once in the same new worktree, **When** both try to prepare it, **Then** only one prepares it; the other refuses or waits, naming the attempt that holds the worktree, and the two never interleave writes. [S: IAC-3] [I]

---

### Edge Cases

- Several candidate sources match: any one that verifies is used; the result is the same installation, because it must match the same record content (AC-003). [P: D-03]
- A candidate source is a checkout that has since been removed or whose path no longer exists: it is skipped like any source that fails verification (AC-010). [I]
- A new worktree holds an interrupted preparation and its pin was changed in the meantime: the interrupted attempt is rolled back and the worktree is treated as uninstalled for the new pin (AC-018, AC-008). [P: D-05]
- An agent step is left unfinished or a tamper marker is present in the worktree: the existing launcher refusals stand after preparation. [S: tools/spec_workflow/launcher.py]
- The operator sets `BALLAST_STANDARD_DIR` to a working copy of the standard: the same matching and verification rules apply to the sources; no per-machine standard cache is used. [I]
- The per-machine standard cache holds the pinned version but no checkout on the machine has a matching installation: this is the missing-cache case (AC-017), because a full installation needs network access. [S: tools/setup] [B: D-01]

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: In a worktree with no installation, `ballast run`, `ballast ledger` and `ballast intake` MUST prepare the installation from a verified local source before running the launcher, with no separate setup command (AC-001, AC-003). [S: IAC-1] [P: D-04]
- **FR-002**: Preparation MUST make no network request; every other outcome that would need one MUST refuse naming `ballast setup` (AC-001, AC-008, AC-013, AC-017). [S: IAC-1] [B: D-01]
- **FR-003**: Candidate sources MUST be limited to installations already recorded on this machine for the same repository: the kept previous installation, the primary checkout and the other linked worktrees (AC-003). [P: D-03]
- **FR-004**: A source MUST be used only when its pin and `ballast.toml` bytes match the new worktree's, its setup is not unfinished or in progress, and its content, including files' executable bits, matches its installation record (AC-008 to AC-011). [S: IAC-2] [P: D-03] [P: D-06]
- **FR-005**: Preparation MUST use the pinned standard version only after it verifies against its content record, and MUST refuse naming the damaged path otherwise (AC-013). [S: IAC-2] [I]
- **FR-006**: Preparation MUST place the installation with the same staged, journaled and lock-serialized switch as setup, so an interruption is always completed or rolled back by the next command and never leaves a mixed installation (AC-018, AC-019, AC-020). [S: IAC-3] [I]
- **FR-007**: Preparation MUST act only on a worktree that has no installation or holds an interrupted first preparation; every other installation state MUST keep today's refusal naming `ballast setup` (AC-006, AC-018). [P: D-05]
- **FR-008**: After preparation the launcher's preflight MUST state precisely that the worktree has no trusted baseline, which protected inputs to review, and that `ballast trust` is the next action (AC-002). [S: Issue #15 body] [S: IAC-1]
- **FR-009**: Preparation MUST NOT record, copy, inherit or consult another checkout's trust baseline, and `ballast trust` MUST NOT prepare an installation (AC-002, AC-005, AC-012). A baseline already in the worktree's own operator state when preparation installs it predates that installation (its path was reused) and MUST be removed without being read, naming the removal (DEC-0002). [B: D-02] [P: D-04] [S: Issue #15 intake scope comment]
- **FR-010**: Run state, the trust baseline, the in-progress marker, the setup journal and the checkout lock MUST stay per worktree; preparation MUST NOT copy run state from any checkout (AC-016). [S: IAC-3] [S: Issue #15 body]
- **FR-011**: Preparation MUST NOT change the worktree's `ballast.toml`, constitution or project policies, or anything in a source checkout or its operator state (AC-014). [S: Issue #15 intake scope comment] [I]
- **FR-012**: `ballast trust` and `ballast discard-runs` MUST refuse on an uninstalled worktree with a message naming how to install, except that `ballast discard-runs` clears an unfinished agent step whose marker that worktree holds (DEC-0001); `ballast doctor`, `ballast status` and `ballast preview` MUST stay read-only on it (AC-005). [P: D-04]
- **FR-013**: The CLI MUST prepare a worktree only when the pinned standard version declares that it supports preparation; otherwise it MUST keep today's refusal naming `ballast setup` (AC-007). [I]
- **FR-014**: Every refusal MUST name the reason (no matching source, rejected source and why, damaged standard copy, another attempt holds the worktree, existing installation state) and the next action (AC-008, AC-010, AC-017, AC-020). [S: Issue #15 body] [I]
- **FR-015**: Tests MUST cover ten concurrent mixed-pin worktrees, a missing source, an interrupted preparation and a retry, and the end-to-end scratch-project run MUST be recorded in the PR (AC-015 to AC-019). [S: IAC-3] [S: docs/policies/project/testing.md]

### Key Entities

- **Worktree**: One checkout of the adopted repository, the primary checkout or a linked worktree; owns its installation and its mutable state.
- **Installation**: The git-ignored paths setup owns in one checkout, built from one standard version and the project's `ballast.toml`.
- **Installation record**: The content record of a checkout's installation, kept in operator state outside agent write authority; a copy is accepted only when it matches one.
- **Fingerprint**: The pin and the `ballast.toml` bytes that an installation was built for; two installations are interchangeable only when their fingerprints match.
- **Candidate source**: A verified installation on this machine for the same repository (kept copy, primary checkout or sibling worktree) that may be copied into a new worktree.
- **Per-worktree mutable state**: Run state, trust baseline, in-progress marker, setup journal and checkout lock; never shared or copied.
- **Trust baseline**: The operator's recorded digests of one worktree's protected inputs; recorded only by `ballast trust` in that worktree.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In a new worktree at a pin with a verified local installation, the operator reaches the trust step with one command, zero setup commands and zero network requests.
- **SC-002**: Across 20 repetitions of ten concurrent first commands in worktrees on two pins, 0 repetitions produce a missing, mixed or wrong-pin installation, and 0 change another worktree's run state or trust state.
- **SC-003**: 100% of tested mismatches (different pin, different agent permissions, altered, added or missing file, changed executable bit, unfinished source setup) prevent reuse, and 0 tested cases give a worktree a trust baseline it did not record itself.
- **SC-004**: Killing a preparation at no fewer than five points leaves, in 100% of cases, a worktree that the next command completes or rolls back to a complete state, and a retry produces the same installation as an uninterrupted preparation.
- **SC-005**: Preparing a worktree from a local source takes under 10 seconds on a typical developer machine, against a full installation that needs the network.

## Non-goals

- Copying another worktree's or the primary checkout's run state. [S: Issue #15 body]
- Treating a different pin, or a different `ballast.toml` configuration, as equivalent. [S: Issue #15 body]
- Bypassing protected-input trust, or recording or inheriting a trust baseline on the operator's behalf; setup-recorded trust belongs to #55. [S: Issue #15 intake scope comment] [B: D-02]
- A new per-machine installation store separate from the existing installation records. [P: D-03]
- Replacing a stale, modified or other-pin installation outside `ballast setup`. [P: D-05]
- `ballast init`, automatic pin changes and update previews. [S: specs/14-recoverable-install/spec.md]

## Assumptions

- "Preflight" in the Issue means the launcher's refusal checks; a new worktree always stops there at "no trusted baseline" until the operator trusts it, because baselines are per checkout and never inherited (D-02). [I]
- A "cached matching pin" means a verified installation with the same fingerprint already exists on this machine for this repository; the standard cache alone is not enough, because a full installation downloads Spec Kit sources (D-03, agent-provisional). The first worktree at a new pin or configuration still needs `ballast setup`; later ones prepare from it. [P: D-03]
- Only `run`, `ledger` and `intake` prepare an installation, so `ballast trust` never records a baseline over files prepared in the same command (D-04, agent-provisional). [P: D-04]
- Preparation applies only to a worktree with no installation or an interrupted first preparation; existing installations change only through `ballast setup` (D-05, agent-provisional). [P: D-05]
- "Changed permissions" covers both `[agents.permissions]` in `ballast.toml`, already part of the fingerprint, and the executable bits of copied files (D-06, agent-provisional). [P: D-06]
- Preparation reuses the pinned standard's own setup in a local-only mode, so feature 14's staging, verification, journal and lock guarantees hold unchanged; the extended sources and the first-command trigger are recorded in a new ADR extending ADR-0007. [I]
- The CLI learns that a pinned version supports preparation from a declaration the version ships, as for recoverable setup; using the feature therefore needs both a CLI release and a standard release that include it. [I]
- Holder detection for the worktree lock covers processes on the same machine only, as in feature 14. [S: specs/14-recoverable-install/spec.md]
