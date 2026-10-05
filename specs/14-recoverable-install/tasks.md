---

description: "Task list for recoverable installs and pin updates"
---

# Tasks: Recoverable installs and pin updates

**Input**: Design documents from `specs/14-recoverable-install/`
**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md), [decisions.md](decisions.md)

**Acceptance evidence**: every acceptance criterion and success criterion maps to a test task below; the [quickstart](quickstart.md) names the scenario for each. Tests are written first and must fail before the implementation task that satisfies them.

**Risk**: R2 (what `ballast` downloads and executes; the paths `tools/setup` installs, removes or preserves; the launcher's refusal conditions).

## Format: `[ID] [P?] [Story?] Description [(depends on ...)]`

- **[P]**: can run in parallel with other ready tasks once its dependencies are done
- **[Story]**: US1 to US4 from [spec.md](spec.md)
- Test tasks cite the `AC-NNN` / `SC-NNN` they prove

## Phase 1: Foundational (blocking prerequisites)

**Purpose**: the shared pieces every story uses: test fixtures, the one entry set, the installation record reader and the checkout lock.

- [x] T001 [P] Test fixtures in `tests/test_setup.py`: a disposable Git project with the shipped ignore block, `XDG_STATE_HOME` from `operator_state`, a fake Spec Kit build (versions A and B, B adds one entry and drops one policy), a snapshot helper over the checkout (files and links, including ignored ones), operator state and run archives, and a `SIGKILL` wrapper script that replaces one named function (research R12)
  - Evidence: `ProjectCase`, `fake_run`, `fake_fetch`, `WRAPPER`, `tree` in `tests/test_setup.py`.
- [x] T002 [P] `tools/spec_workflow/launcher.py`: `SETUP_ATTEMPT`, `INSTALLATION`, `CHECKOUT_LOCK` names; `read_record(root, state)` returning the installation record only while its fingerprint equals `.ballast/.setup-version` (F-003); `checkout_lock(state, shared)` opening `checkout.lock` with `O_NOFOLLOW` and taking a non-blocking `flock`
  - Evidence: `read_record`, `checkout_lock`, `SETUP_ATTEMPT`/`INSTALLATION`/`CHECKOUT_LOCK` in `tools/spec_workflow/launcher.py`; exercised by `TrustedLauncherTests` and `RecoverableSetupTests`.
- [x] T003 `tools/setup`: `entries(root)` (the single entry rule, F-002), `DISCARDED`, `live_digests(root, paths)` over entries minus `LOCAL_STATE` and `__pycache__`, loading `state_dir`, `digests`, `IN_PROGRESS` and the T002 helpers from the standard's own `launcher.py`; the build (`install_spec_kit`, `install_standard`) runs against a given project root (the stage) (depends on T002)
  - Evidence: `entries`, `installed_digests`, `DISCARDED`, the launcher loaded from the standard and `Setup(stage)` builds in `tools/setup`.

**Checkpoint**: the stage can be built and described; nothing switches yet.

## Phase 2: User Story 1 - A failed or interrupted setup leaves the previous installation usable (Priority: P1) MVP

**Goal**: build into a stage, validate, switch with a journal, recover after a kill; the launcher refuses a mixed installation.

**Independent Test**: inject a failure at each stage and kill at five points in a disposable project with a trusted installation and a paused run; compare snapshots and run the launcher preflight.

### Acceptance tests for User Story 1

- [x] T004 [P] [US1] Tests in `tests/test_setup.py`: failing each Spec Kit source fetch, each `specify` call and each patch exits 1 naming `fetch <source>`, `spec-kit <command>` or `patch <file>`, says the previous installation was kept, leaves no `.ballast/setup/` and an unchanged snapshot, including the constitution, `docs/policies/project/`, run state, run archives and `trusted.json` [AC-001, AC-002, AC-006] (depends on T001, T003)
  - Evidence: `RecoverableSetupTests.test_failed_stages_keep_the_previous_installation` (7 stages, snapshots of checkout, archives and operator state).
- [x] T005 [P] [US1] Tests in `tests/test_setup.py`: validation refuses a stage missing a promised output, with an un-ignored path, containing the stage's absolute path, holding an unexpected output (F-002), or after `OSError(ENOSPC)` in a copy; a symbolic link as an ancestor of a live entry or of `.ballast/setup` is refused (F-007); each case names the check and leaves the checkout unchanged [AC-003, AC-006] (depends on T001, T003)
  - Evidence: `RecoverableSetupTests.test_invalid_stage_is_never_switched`, `test_linked_work_area_is_refused`.
- [x] T006 [P] [US1] Kill tests in `tests/test_setup.py` through the wrapper: during staging, after `switching` is journaled, after the first rename, mid-switch, after `committed` is journaled, with version B dropping an entry (F-001); the next setup prints the recovery line and the checkout equals the full previous or full new snapshot; a second kill during rollback recovers too [AC-004, AC-006, AC-011, SC-001] (depends on T001, T003)
  - Evidence: `RecoverableSetupTests.test_killed_setup_is_recovered` (5 points), `test_kill_during_rollback_is_recovered`; a presence-only rollback mutation fails it.
- [x] T007 [P] [US1] Launcher tests in `tests/test_spec_workflow.py`: with `setup-attempt.json` present, `run`, `ledger`, `intake`, `trust` and `discard-runs` exit 2 naming `ballast setup`; with setup holding the lock, they say setup is running (lock checked first, F-006); `trust` holds the shared lock while it hashes (F-005); `status --json` reports the attempt and takes no lock [AC-005] (depends on T001, T002)
  - Evidence: `TrustedLauncherTests.test_unfinished_setup_is_refused`, `test_running_setup_is_reported_as_running`, `test_workflow_tool_keeps_the_shared_lock`.
- [x] T008 [P] [US1] Tests for AC-007 and AC-008 in `tests/test_setup.py`, `tests/test_spec_workflow.py`, `tests/test_ballast.py` and `tests/test_doctor.py`: after a failed or recovered setup at an unchanged pin, `launcher.py status --json` reports `refusal: null` with no `trust`; with the pin changed to B and B failing (B fetched) or B not fetched, `--check`, the launcher, the CLI refusal and `ballast doctor` name pinned B, installed A and both recovery actions; after B → pre-feature A → B the stale record is ignored and A-only policies are removed (F-003) [AC-007, AC-008, SC-002] (depends on T001, T002)
  - Evidence: `RecoverableSetupTests.test_failure_at_an_unchanged_pin_keeps_trust`, `test_changed_pin_names_both_versions`, `test_stale_record_is_ignored`; `TrustedLauncherTests.test_pinned_and_installed_versions_differ`; `NotFetchedTests`; `ProjectTests.test_pinned_and_installed_versions_are_named`.

### Implementation for User Story 1

- [x] T009 [US1] `tools/setup`: the attempt lifecycle per [contracts/setup.md](contracts/setup.md): exclusive lock and holder, recovery from the journal (rollback table keyed on `new`, verification against `before`), stage creation as its own Git repository with seeds, build, validation checks (1) to (6), switch, live verification, commit (constitution only when absent, record, work-area removal with `_remove_tree`), stage-named failure messages and exit codes, cleanup on any surviving failure including Ctrl-C (depends on T003, T004, T005, T006)
  - Evidence: `Setup.main`, `attempt`, `build`, `validate`, `switch`, `roll_back`, `finish`, `recover` in `tools/setup`; the T004 to T006 tests pass.
- [x] T010 [US1] `tools/setup --check`: `interrupted`, `stale: pinned …, installed …` (valid record only), `stale`, `incomplete: <path>`, `modified: <path>`, `current`; writes nothing and takes no lock (depends on T009, T008)
  - Evidence: `Setup.check` in `tools/setup`; `CheckTests`, `NoOpTests.test_modified_installation_is_not_current`, `test_changed_pin_names_both_versions` pass.
- [x] T011 [US1] `tools/spec_workflow/launcher.py`: shared lock before the journal check, kept inheritable through `execv`; refusals for an unfinished attempt and for pinned ≠ installed; `trust` and `discard-runs` under the shared lock, refusing during an attempt; `status --json` reports both refusals (depends on T002, T007, T008)
  - Evidence: `_hold`, `_setup_refusal` and `main` in `launcher.py`; T007 tests and the existing `TrustedLauncherTests` pass.
- [x] T012 [US1] `tools/ballast`: the not-fetched refusal and doctor's `standard-fetched` detail name the installed ref from a valid `installation.json` with both recovery actions; doctor's trust remedy says `ballast setup` for setup refusals (depends on T008, T011)
  - Evidence: `installed_detail`, the not-fetched refusal, doctor's `standard-fetched` detail and trust remedies in `tools/ballast`; T008 CLI and doctor tests pass.

**Checkpoint**: User Story 1 works on its own: failures and kills never leave a mixed installation.

## Phase 3: User Story 2 - Concurrent and repeated setups are safe (Priority: P1)

**Goal**: one setup per checkout, one fetch per version, a no-op rerun, content-verified cache and worktree copies.

**Independent Test**: two setups in one checkout and two fetches from sibling worktrees; a rerun with downloads denied; one corrupted file in the cache and in a primary installation.

### Acceptance tests for User Story 2

- [x] T013 [P] [US2] Tests in `tests/test_setup.py`: a helper holding the lock exclusively makes setup exit 2 naming its PID and write nothing; a helper holding it shared makes setup name the running command; the `in-progress` marker makes setup name `ballast discard-runs`; after the holder is killed, setup proceeds; two concurrent setups in one checkout, repeated 20 times, never both run [AC-009, AC-011, AC-015, SC-004] (depends on T001, T009)
  - Evidence: `SetupLockTests` (holder named, shared holder, in-progress marker, 20 races).
- [x] T014 [P] [US2] Test in `tests/test_setup.py`: a second setup at a current pin with every download and Spec Kit call raising prints `nothing changed`, leaves the checkout and operator record unchanged and takes under 5 s [AC-012, SC-003] (depends on T001, T009)
  - Evidence: `NoOpTests.test_rerun_changes_nothing`.
- [x] T015 [P] [US2] Tests in `tests/test_setup.py`: a linked worktree copies a verified primary installation into its stage; a primary with a missing, added or altered installed file, no record, another fingerprint or a held lock is not copied and setup says `full installation: <reason>` [AC-014, SC-005] (depends on T001, T009)
  - Evidence: `WorktreeCopyTests` (verified copy, three damages, three fallbacks).
- [x] T016 [P] [US2] Cache tests in `tests/test_ballast.py`: a fetch writes `.ballast-cache.json` and publishes with one rename; a failing download leaves no `.fetch-*` and a clear message; a missing, added or altered file or a missing record is detected before `setup` uses the copy and refetched, or refused naming the path when the refetch fails; two processes fetching one uncached ref download once, 20 times; a killed fetch holder does not block [AC-001, AC-010, AC-011, AC-013, SC-004, SC-005] (depends on T001)
  - Evidence: `CacheTests` and `CompatibilityTests` in `tests/test_ballast.py`.

### Implementation for User Story 2

- [x] T017 [US2] `tools/setup`: refusal naming the setup holder or the running launcher command, and the `in-progress` refusal; the no-op path (valid record, same fingerprint, live content equal) before any write or download; the verified worktree copy into the stage with its `full installation:` reasons (depends on T009, T013, T014, T015)
  - Evidence: `Setup.lock`, the `in-progress` refusal, `Setup.current`, `copy_from_primary`/`copy_verified` in `tools/setup`; T013 to T015 pass.
- [x] T018 [US2] `tools/ballast`: per-version fetch lock with bounded wait, stale `.fetch-*`/`.damaged-*` cleanup, content record, single-rename publication, verification and refetch before `setup`, refusal naming the damaged path, fetch failure message (depends on T016)
  - Evidence: `cache_record`, `damage`, `fetch_lock`, `fetch`, `ensure_standard` in `tools/ballast`; `CacheTests` pass.

**Checkpoint**: User Stories 1 and 2 both hold.

## Phase 4: User Story 3 - Preview a pin update before changing it (Priority: P2)

**Goal**: `ballast preview <ref>` reports the version change, CLI minimum, run compatibility, path and ignore impact, and the ordered steps, changing nothing.

**Independent Test**: preview another version in a project with a paused run, compare with an actual update of a copy, and confirm the project is unchanged.

### Acceptance tests for User Story 3

- [x] T019 [P] [US3] Tests in `tests/test_spec_workflow.py`: `run.py` writes `run-format.json` into the run archive at start; `RUN_FORMAT` equals `tools/cli.toml [runs] format`; a recorded digest of the Spec Kit `VERSION` and the shipped workflows' step IDs fails the test when either changes while the format string stays the same [AC-017] (depends on T001)
  - Evidence: `RunFormatTests` (format equals the manifest; basis digest guard) and `test_launcher_records_the_run_format_at_start` in `tests/test_spec_workflow.py`.
- [x] T020 [P] [US3] Tests in `tests/test_preview.py` with fixture standards A and B in the cache: the report and `--json` name pinned, target, installed, CLI minimum and whether it is met [AC-016]; runs with and without a resumable format [AC-017]; added, changed and removed paths equal the difference of an actual update of a copy, ignore impact and an empty project-owned list [AC-018, SC-006]; the ordered steps [AC-019]; checkout, run archives, operator state and `ballast.toml` unchanged and no `preview/` left after successful, failing and refused previews [AC-020]; a target without `[setup] recoverable` is reported as without the guarantees [AC-021]; refusals for a bad ref, `BALLAST_STANDARD_DIR`, an unfinished attempt and a held lock (depends on T001)
  - Evidence: `tests/test_preview.py` (`PreviewTests`: report and JSON, runs, paths against an actual update, ignore impact, steps, read-only snapshots, older target, failed build, refusals).

### Implementation for User Story 3

- [x] T021 [P] [US3] `tools/cli.toml` `[setup] recoverable` and `[runs] format`/`resumes`; `tools/spec_workflow/run.py` `RUN_FORMAT` written as `run-format.json` under `archive_lock` when a run starts (depends on T019)
  - Evidence: `[setup]` and `[runs]` in `tools/cli.toml`; `RUN_FORMAT` and `_archive_format` in `tools/spec_workflow/run.py`; T019 tests pass.
- [x] T022 [US3] `tools/ballast preview <ref> [--json]` per [contracts/preview-cli.md](contracts/preview-cli.md): fetch and verify, read the target manifest and ignore block as data (`ast`, parse only), disposable builds under `$XDG_DATA_HOME/ballast/preview/` with their own `XDG_STATE_HOME`, same-procedure diff, read-only ignore check, run compatibility, steps, exit codes, removal in every outcome; usage line (depends on T018, T020, T021)
  - Evidence: `preview`, `compare`, `update_report`, `render_preview`, `preview_refusal`, `disposable_build`, `unfinished_runs` in `tools/ballast`; T020 tests pass.

**Checkpoint**: an operator can preview an update before editing the pin.

## Phase 5: User Story 4 - Roll back to the previous pin (Priority: P2)

**Goal**: restoring the previous pin reinstalls it from the cache with the same guarantees; the README documents the paths.

**Independent Test**: update A → B with a paused and an archived run, follow the README rollback; no download, project files and run evidence unchanged.

### Acceptance tests for User Story 4

- [ ] T023 [P] [US4] Test in `tests/test_setup.py` and `tests/test_ballast.py`: after A → B with A cached, restoring pin A and running setup with downloads denied reinstalls A equal to a fresh A installation; constitution, `docs/policies/project/`, run state, run archives and `trusted.json` unchanged; the launcher refuses until `trust` [AC-022, AC-023, SC-007] (depends on T001, T017, T018)
- [ ] T024 [P] [US4] Test in `tests/test_ballast.py`: the README's update section documents preview, update, retry after a failed update and rollback, and every `ballast <subcommand>` it shows is accepted by the CLI or the launcher [AC-024] (depends on T001)

### Implementation for User Story 4

- [ ] T025 [US4] `README.md`: "Updating the pinned version" section (update the CLI first, `ballast preview`, pin change, `ballast setup`, review, `ballast trust`, checks; retry; rollback; what an older version does not guarantee; DEC-0001's CLI note); adjust the reinstall sentence (depends on T022, T024)

**Checkpoint**: all stories hold.

## Phase 6: Polish and cross-cutting

- [ ] T026 [P] `docs/adr/0006-recoverable-installation.md` and `docs/adr/0007-verified-cache-and-update-preview.md` (status Proposed; accepted when the PR merges) (depends on T017, T022)
- [ ] T027 [P] Module docstrings and usage in `tools/setup` and `tools/ballast` match the new states and commands; `IGNORE_PROBES` gains `.ballast/setup/` (depends on T017, T022)
- [ ] T028 End-to-end check on a scratch project with `BALLAST_STANDARD_DIR` pointing at this working copy ([quickstart](quickstart.md#end-to-end-full-gate-network)): setup, trust, a failing patch keeps the previous installation and `status --json` stays clear, a rerun prints `nothing changed`, a `kill -9` during Spec Kit steps is recovered; record the commands and results [AC-002, AC-004, AC-007, AC-012] (depends on T017, T011)

## After implementation (workflow-owned)

Not tasks: the workflow runs these after the tasks are done. The full local gate (fast gate plus the CI-skipped tests on a host with a systemd user session, Codex and Spec Kit), the security, engineering, test and documentation reviews into `reviews/`, decision reconciliation, `speckit.converge`, spec reconciliation and `reviews/convergence.md`, and any operator pilot.

## Dependencies & Execution Order

- **Phase 1** blocks everything. T001 and T002 are independent; T003 needs T002.
- **US1** (T004 to T012) needs Phase 1. US2's setup work (T013 to T015, T017) builds on T009; its cache work (T016, T018) needs only T001.
- **US3** needs the cache (T018) for the preview; T019/T021 are independent of US1 and US2.
- **US4** needs US2's setup and cache (T017, T018) and the preview (T022) for the README.
- Within a story, tests come first and fail before the implementation task.

## Execution Wave DAG

```text
Wave 1 (no dependencies):
  T001 [P] Test fixtures
  T002 [P] Launcher record reader and lock helper

Wave 2:
  T003  Entry set, live digests, build into a given root (depends on T002)
  T016 [P] [US2] Cache tests (depends on T001)
  T019 [P] [US3] Run-format tests (depends on T001)
  T020 [P] [US3] Preview tests (depends on T001)
  T024 [P] [US4] README test (depends on T001)
  T007 [P] [US1] Launcher refusal tests (depends on T001, T002)
  T008 [P] [US1] AC-007/AC-008 tests (depends on T001, T002)

Wave 3:
  T004 [P] [US1] Failure tests (depends on T001, T003)
  T005 [P] [US1] Validation tests (depends on T001, T003)
  T006 [P] [US1] Kill tests (depends on T001, T003)
  T018  [US2] Cache implementation (depends on T016)
  T021 [P] [US3] Manifest and run format (depends on T019)

Wave 4:
  T009  [US1] Attempt lifecycle (depends on T003, T004, T005, T006)
  T011  [US1] Launcher refusals (depends on T002, T007, T008)

Wave 5:
  T010  [US1] --check states (depends on T009, T008)
  T012  [US1] CLI pinned/installed messages (depends on T008, T011)
  T013 [P] [US2] Lock and marker tests (depends on T001, T009)
  T014 [P] [US2] No-op test (depends on T001, T009)
  T015 [P] [US2] Worktree copy tests (depends on T001, T009)

Wave 6:
  T017  [US2] Refusals, no-op, verified copy (depends on T009, T013, T014, T015)
  T022  [US3] Preview command (depends on T018, T020, T021)

Wave 7:
  T023 [P] [US4] Rollback test (depends on T001, T017, T018)
  T025  [US4] README section (depends on T022, T024)
  T026 [P] ADRs (depends on T017, T022)
  T027 [P] Docstrings and probes (depends on T017, T022)
  T028  End-to-end check (depends on T017, T011)
```

## Implementation Strategy

MVP is User Story 1 (T001 to T012): it alone removes the destructive failure mode. User Story 2 completes the P1 safety guarantee; User Stories 3 and 4 add the reviewed-update path.

## Notes

- `tools/setup`, `launcher.py` and `run.py` stay standard-library only and run under `python3 -I -S`.
- No production fault hook: kills replace a named function in a wrapper (research R12).
- Snapshots compare files and links; an empty parent directory created for a first installation is not an installed path.
