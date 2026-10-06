# Feature Specification: Recoverable installs and pin updates

**Feature Branch**: `feat/14-recoverable-install`

**Created**: 2026-10-05

**Status**: Draft

**Input**: User description: "Issue #14: A failed setup or version update leaves the previous usable installation and paused run evidence intact."

**Tracking**: [Ballast #14](https://github.com/Hugo-Grellier/ballast/issues/14), a leaf of the [Ballast 1.0 Epic](https://github.com/Hugo-Grellier/ballast/issues/11); roadmap Phase 1, items 5 and 6 ([product roadmap](../../docs/plans/2026-10-02-product-roadmap.md)); [v1.0 target](../TECHNICAL-SPEC.md#91-v10-target). Blocked by #12, delivered as [`specs/12-cli-install-doctor`](../12-cli-install-doctor/spec.md).

**Risk**: R2. The feature changes what `ballast` downloads and executes, and which paths `tools/setup` installs, removes or preserves. This run is Autonomous: the pre-change approval is agent-provisional and merging the PR is the single human approval.

## Context

`ballast setup` fetches the pinned standard version into a per-machine cache once, then runs that version's `tools/setup`. Today setup first deletes the previous installation and then builds the replacement in place in the checkout. If fetching a Spec Kit source, running Spec Kit, applying a patch or validating the result fails, or the process is killed, the checkout is left with no usable installation. The project's constitution is protected only by an in-process restore, which a killed process skips. A cached standard version is trusted because its directory exists, and an installation copied from the primary checkout is trusted because its stamp matches; neither check looks at the content. Two setup attempts in the same checkout, or two fetches of the same version from two worktrees, can interleave their writes. An operator who wants to change the pin sees what changes only after the change, and the recovery path after a bad update is not documented.

Run state already survives a successful reinstall: setup keeps `.specify/workflows/runs` and `.specify/workflow-state`, run archives live in the Git common directory, and the trust baseline lives in operator state outside the checkout. This feature makes the same hold for every failure.

It does not create worktree installations automatically (#15), change pins automatically, or trust changed executable inputs on the operator's behalf (#55).

## User Scenarios & Testing *(mandatory)*

Give each acceptance scenario a stable ID (`AC-001`, `AC-002`, ...). Task and test descriptions cite the IDs they satisfy, so review can trace each criterion to evidence.

### User Story 1 - A failed or interrupted setup leaves the previous installation usable (Priority: P1)

An operator with a working, trusted installation and a paused run runs `ballast setup`, either to repair the installation or after changing the pin. The setup fails: the network drops, a Spec Kit step errors, a patch no longer applies, validation finds a problem, or the process is killed. Afterwards the checkout still holds the previous installation, complete and unchanged. The paused run, its evidence and the constitution are untouched. If the pin did not change, the operator resumes the run without running `ballast trust` again. The failure message says what failed, that the previous installation was kept, and the exact next action.

**Why this priority**: This is the main outcome of the Issue. An install that destroys the working version on failure turns a transient error into a blocked feature run, and a lost constitution or run is lost work.

**Independent Test**: In a disposable project with a trusted installation and a paused run, inject a failure at each setup stage and kill the process at several points, then compare the installed files, run state and constitution with the snapshot taken before, and run the launcher's preflight.

**Acceptance Scenarios**:

1. **AC-001**: **Given** a checkout with a valid installation, **When** setup fails while fetching the standard version or a Spec Kit source, **Then** every installed path is byte-identical to before, no partially fetched content is left in the cache or the checkout, and setup exits non-zero naming the failed source.
2. **AC-002**: **Given** a checkout with a valid installation, **When** setup fails in a Spec Kit installation step or because a patch does not apply, **Then** every installed path is byte-identical to before and setup exits non-zero naming the failed step.
3. **AC-003**: **Given** a checkout with a valid installation, **When** the replacement fails validation (required outputs missing, ignore rules wrong, content not matching what was built), **Then** the replacement is never put in place, every installed path is byte-identical to before, and the message names the failed check.
4. **AC-004**: **Given** a setup in progress, **When** the process is killed at any point before, during or after the switch to the new installation, **Then** the next `ballast setup` detects the unfinished attempt and leaves the checkout with either the complete previous installation or the complete new one, never a mix, and says which.
5. **AC-005**: **Given** a checkout whose last setup was interrupted, **When** any other `ballast` command that runs the launcher is invoked, **Then** it refuses and names `ballast setup` as the recovery action, instead of running against a mixed installation.
6. **AC-006**: **Given** any failure or interruption in AC-001 to AC-004, **When** the operator inspects the checkout, **Then** the project's constitution, `docs/policies/project/`, run state (`.specify/workflows/runs`, `.specify/workflow-state`), the run archives in the Git common directory and the operator's trust baseline are unchanged.
7. **AC-007**: **Given** a trusted installation, a paused run and an unchanged pin, **When** a setup fails or is interrupted and the checkout is left with the previous installation, **Then** `ballast run resume` passes the trust preflight without a new `ballast trust`.
8. **AC-008**: **Given** the pin was changed and setup for the new version failed, **When** the operator runs `ballast doctor` or any launcher command, **Then** the output names the pinned version, the installed version, and the two recovery actions: restore the previous pin, or fix the cause and rerun setup.

---

### User Story 2 - Concurrent and repeated setups are safe (Priority: P1)

An operator, a script or two worktrees run setup at the same time, or the operator reruns setup out of habit. Attempts in one checkout never interleave writes, two worktrees fetching the same version share one complete copy, and a rerun at an unchanged, verified pin changes nothing. Damaged cached or copied content is detected by content, not by a stamp, and never installed.

**Why this priority**: Without serialization and content checks, a correct stage-and-switch can still install a half-written or corrupted version, so this is part of the same safety guarantee as User Story 1.

**Independent Test**: Start two setups in one checkout, and two in sibling worktrees at the same uncached pin; rerun setup at a current pin and record file changes and network access; corrupt one file in the cache and in a primary checkout's installation, then run setup.

**Acceptance Scenarios**:

1. **AC-009**: **Given** a setup running in a checkout, **When** a second setup starts in the same checkout, **Then** the second one refuses before writing anything and names the attempt that holds the checkout; the first completes unaffected.
2. **AC-010**: **Given** two worktrees pinned to the same uncached version, **When** both run setup at once, **Then** the version is downloaded and extracted once, both installations come from that complete copy, and neither sees a partial cache.
3. **AC-011**: **Given** a setup attempt whose process died while holding the checkout or the cache, **When** a later setup starts, **Then** it detects that the holder is gone and proceeds, recovering per AC-004, instead of waiting or refusing forever.
4. **AC-012**: **Given** a checkout whose installation is current and verified for its pin, **When** the operator runs setup again, **Then** setup reports that nothing changed, modifies no file in the checkout or the cache, and makes no network request.
5. **AC-013**: **Given** a cached standard version with a missing, added or altered file, **When** setup or an update preview uses it, **Then** the damage is detected, the damaged copy is never installed, and the version is fetched again or the command refuses naming the damaged path.
6. **AC-014**: **Given** a primary checkout whose installation stamp matches but whose installed content differs from what that version builds, **When** a worktree runs setup, **Then** the worktree does not copy it, falls back to a full installation, and says why.
7. **AC-015**: **Given** an agent step left unfinished in a checkout, or a workflow run invocation active there, **When** setup is started in that checkout, **Then** it refuses before writing anything and names the reason.

---

### User Story 3 - Preview a pin update before changing it (Priority: P2)

Before editing the committed pin, the operator asks Ballast what moving to a named version would do. The preview shows the version change, whether each unfinished run in the checkout can continue under the new version, which generated files would be added, changed or removed, and the exact commands and reviews needed to finish the update. It changes nothing in the checkout, the installation, the run state or the trust baseline.

**Why this priority**: The preview turns an update from trial and error into a reviewed decision, but the recovery guarantees of User Stories 1 and 2 protect the operator even without it.

**Independent Test**: In a project pinned to one version with a paused run, preview a different version; compare the report with the actual result of changing the pin and running setup in a copy of the project, and confirm the original project is byte-identical afterwards.

**Acceptance Scenarios**:

1. **AC-016**: **Given** a project pinned to version A, **When** the operator previews an update to version B, **Then** the report names A, B, the installed version and the minimum `ballast` CLI version B requires, and says whether the installed CLI meets it.
2. **AC-017**: **Given** unfinished runs in the checkout, **When** the operator previews an update, **Then** the report lists each run with whether version B declares it can resume it, and treats a run as incompatible when B declares nothing, telling the operator to finish or discard that run first.
3. **AC-018**: **Given** a preview of version B, **When** it completes, **Then** it lists every installed path B would add, change or remove, any change B needs in the project's ignore rules, and confirms that no project-owned file would change.
4. **AC-019**: **Given** a preview of version B, **When** it completes, **Then** it lists in order the exact commands and reviews to finish the update: the pin change, `ballast setup`, the changed protected inputs to review, `ballast trust`, and the project's configured checks.
5. **AC-020**: **Given** any preview, successful or not, **When** it finishes, **Then** the checkout, its installation, run state, run archives and trust baseline are byte-identical to before; only the per-machine cache may have gained version B.
6. **AC-021**: **Given** version B predates this feature, **When** the operator previews it, **Then** the report says that setup and rollback for B do not carry the recovery guarantees of this feature.

---

### User Story 4 - Roll back to the previous pin (Priority: P2)

After an update the operator finds a problem and returns to the previous version. They restore the previous pin and rerun setup. The previous version is reinstalled from the cache without a download. The constitution, project policies, paused runs and run archives are intact, and the operator reviews and trusts the restored inputs as for any change. The README documents this path and the retry path after a failed update.

**Why this priority**: Rollback is the last safety net for an update that installed cleanly but does not work for the project; it reuses the setup path of User Stories 1 and 2.

**Independent Test**: Update a project with a paused run and an archived run from version A to B, then follow the documented rollback steps; check that A's installation is restored without a network request, and that the constitution, project policies, run state and archives match the snapshots.

**Acceptance Scenarios**:

1. **AC-022**: **Given** a project updated from version A to B with A still cached, **When** the operator restores pin A and runs setup, **Then** A's installation is restored without a network request and matches a fresh installation of A.
2. **AC-023**: **Given** a rollback from B to A, **When** it completes, **Then** the constitution, `docs/policies/project/`, run state and run archives are unchanged, and the launcher refuses until the operator runs `ballast trust`; nothing is trusted on their behalf.
3. **AC-024**: **Given** the README, **When** an operator follows its update section, **Then** it documents preview, update, retry after a failed update, and rollback to the previous pin, with the exact commands, and a test checks that the documented commands exist.

---

### Edge Cases

- The cache directory for the pinned version exists but is empty or holds only part of an extraction from an older `ballast` version: it is treated as damaged (AC-013).
- The disk fills during staging: the staged copy is discarded and the previous installation is kept (AC-003).
- Two worktrees on different pins run setup at once: each proceeds independently; only same-version cache work is serialized.
- The pin names a tag that moved upstream after it was cached: the cached copy is used as long as it is intact; detecting a moved tag is out of scope.
- The operator previews or rolls back to a version that predates this feature: that version's own setup runs, so its failures are not recoverable; the preview says so (AC-021). The constitution is still preserved by that version's own restore, and run archives live outside the checkout.
- A rollback target is no longer cached: setup downloads it, with the same guarantees as any setup.
- Setup runs with `BALLAST_STANDARD_DIR` set to a working copy: the guarantees for the checkout's installation still apply; cache verification does not, because no cache is used.
- The project's ignore rules are wrong: setup refuses before staging, as today, and the previous installation is untouched.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Setup MUST build and validate the complete replacement installation before changing any installed path in the checkout, and MUST keep the previous installation complete until the replacement is in place (AC-001 to AC-003).
- **FR-002**: Setup MUST validate the replacement before switching: every required output present, the project's ignore rules covering every installed path, and the installed content matching what was built (AC-003).
- **FR-003**: Setup MUST record an unfinished attempt durably, so that after an interruption the next setup completes the switch or restores the previous installation, and reports which (AC-004, AC-011).
- **FR-004**: Launcher commands MUST refuse to run against a checkout whose setup attempt is unfinished, naming `ballast setup` as the recovery (AC-005).
- **FR-005**: Setup MUST NOT modify, move or delete the project's constitution, `docs/policies/project/`, other project-owned files, run state, run archives or the operator's state, in any outcome including a killed process (AC-006, AC-023).
- **FR-006**: When setup fails and the pin is unchanged, the checkout's protected inputs MUST be exactly those of the previous trusted state, so the existing trust baseline still applies (AC-007).
- **FR-007**: Every setup failure MUST exit non-zero with a message naming the failed stage, stating that the previous installation was kept, and giving the next action. `ballast doctor` MUST report a pinned version that differs from the installed one, with the recovery actions (AC-001 to AC-003, AC-008).
- **FR-008**: Setup attempts in one checkout MUST be mutually exclusive; a second attempt refuses before writing and names the holder (AC-009).
- **FR-009**: Fetching a standard version into the per-machine cache MUST be serialized per version, MUST never expose a partial copy, and MUST let a waiting attempt reuse the completed copy (AC-010).
- **FR-010**: A held checkout or cache whose holding process no longer exists MUST NOT block later attempts (AC-011).
- **FR-011**: Setup at an unchanged pin whose installation is current and verified MUST change no file and make no network request (AC-012).
- **FR-012**: The cache MUST record the content of each fetched version when it is fetched. Setup and the update preview MUST verify a cached version against that record before using it, and MUST refetch or refuse on any difference (AC-013).
- **FR-013**: A worktree MUST copy the primary checkout's installation only when the copied content matches what its version builds; otherwise it performs a full installation and says why (AC-014).
- **FR-014**: Setup MUST refuse while an agent step is unfinished or a workflow run invocation is active in the same checkout (AC-015).
- **FR-015**: Ballast MUST provide an update preview for a named target version that reports the version change, the CLI version requirement, active-run compatibility, generated-file and ignore-rule impact, and the ordered commands and reviews needed to finish the update (AC-016 to AC-019, AC-021).
- **FR-016**: A standard version MUST declare which run-state formats it can resume, and the preview MUST treat an undeclared format as incompatible (AC-017).
- **FR-017**: The update preview MUST NOT change the checkout, its installation, run state, run archives, the trust baseline or the committed pin; it MAY add the target version to the per-machine cache and build a disposable installation outside the checkout, running only that version's own setup from the fixed repository, never trusted and never put in place (AC-020).
- **FR-018**: Ballast MUST NOT change `ballast.toml` and MUST NOT record trust on the operator's behalf during setup, preview, retry or rollback (AC-023).
- **FR-019**: Rolling back to a cached previous pin MUST reinstall that version from the cache without a network request, with the same guarantees as any setup (AC-022, AC-023).
- **FR-020**: The README MUST document preview, update, retry after failure and rollback with exact commands (AC-024).

### Key Entities

- **Installation**: The set of git-ignored paths setup owns in one checkout, built from one standard version and the project's `ballast.toml`, identified by its version and content fingerprint.
- **Staged installation**: A complete replacement built and validated outside the live installed paths, not yet in effect.
- **Setup attempt**: One setup invocation for one checkout; holds the checkout exclusively and leaves a durable record while unfinished.
- **Cached version**: One standard version extracted into the per-machine cache, with a content record taken when it was fetched.
- **Run evidence**: Run state in the checkout, run archives in the Git common directory, Autonomous run records, and the operator's trust baseline and markers.
- **Update preview**: A read-only report for one target version: version change, CLI requirement, run compatibility, file and ignore-rule impact, required commands.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In a fault-injection suite covering every setup stage (fetch, each Spec Kit step, each patch, validation, switch) plus process kills at no fewer than five points, 100% of cases leave a runnable installation (previous or new, never mixed), and 0 cases change the constitution, project policies, run state, run archives or trust baseline.
- **SC-002**: After a failed setup at an unchanged pin, a paused run resumes with zero extra operator commands (no reinstall, no re-trust).
- **SC-003**: Repeating setup at a current pin changes 0 files, makes 0 network requests and finishes in under 5 seconds on a typical developer machine.
- **SC-004**: Across 20 runs of two concurrent setups (same checkout, and sibling worktrees at the same uncached pin), 0 runs produce an interleaved or partial installation or cache, and each uncached version is downloaded exactly once per same-version race.
- **SC-005**: 100% of single-file corruptions (missing, added or altered file) in a cached version or a primary checkout's installation are detected before installation.
- **SC-006**: For a version pair used in testing, the preview's list of added, changed and removed installed paths matches the actual difference after updating, with no omissions.
- **SC-007**: An operator can roll back to the previous pin using only the README's documented commands, with no network access when the version is cached, in at most three commands followed by the usual trust review.

## Assumptions

- The guarantees apply when the target version's own setup includes this feature. Updating into such a version from v0.5.0 or earlier is protected, because the new version's setup runs; rolling back to an older version runs that version's setup, which the preview flags (AC-021).
- Installed paths are scattered across the checkout (`.ballast/`, parts of `.specify/`, skill directories, `docs/policies/*.md`), so a single atomic rename of everything is not possible. The guarantee is that an interruption is always detected and resolved to a complete previous or a complete new installation, not that the switch is one filesystem operation.
- A second setup in the same checkout refuses rather than waits, because it is almost always an operator mistake; a second fetch of the same version waits, because sibling worktrees legitimately race on a shared cache.
- The per-machine cache and operator state are outside every agent's write authority (BL-INV-002, #34); cache verification guards against incomplete or damaged content, not against an attacker who controls the operator's account.
- Pin changes stay manual and reviewed in Git; the preview informs that decision and never makes it. Re-trust after any change of protected inputs stays an explicit operator action (#55 owns setup-recorded trust).
- Runs do not yet record a run-state format that a version can declare compatibility with; this feature introduces that declaration, and runs from versions without it are reported as incompatible until finished or discarded.
- A damaged cached version (AC-013) is never repaired in place or installed. Setup and the preview fetch a fresh complete copy when the source is reachable, with the same per-version serialization as any fetch (FR-009); when it is not, they refuse and name the damaged path.
- Detecting that the holder of a checkout or cache is gone (AC-011, FR-010) covers processes on the same machine only. The cache is per-machine; a checkout or cache shared across machines over a network filesystem is not supported by this guarantee.
- When setup refuses because an agent step is unfinished or a run invocation is active (AC-015), it names the recovery the launcher already offers for that state (`ballast discard-runs` for an unfinished agent step, or waiting for the active invocation to end) and never clears the marker itself.
- Detecting a release tag that was moved upstream after caching is out of scope.
- New-worktree automatic setup (#15), `ballast init` and automatic version bumps are out of scope.
