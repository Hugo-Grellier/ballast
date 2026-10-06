---

description: "Task list for feature 15: prepare a new worktree on first Ballast use"
---

# Tasks: Prepare a new worktree on first Ballast use

**Input**: Design documents from `specs/15-worktree-setup/`: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/prepare.md](contracts/prepare.md), [contracts/cli-and-launcher.md](contracts/cli-and-launcher.md), [quickstart.md](quickstart.md), [reviews/plan.md](reviews/plan.md)

**Prerequisites**: plan accepted (PD-0008, agent-provisional). Plan-review findings F-001 to F-005 are settled in T001 and carried into the tasks that implement and test them.

**Risk**: R2, Autonomous run. Every decision below is agent-provisional; merging the PR is the single human approval.

**Acceptance evidence**: Every AC-001 to AC-020 maps to at least one test task below, and SC-001 to SC-005 to a test or the recorded end-to-end run. All new tests are offline: `_fetch_source` and `urllib.request.urlretrieve` fail the test if called, and CLI children run with a `PATH` that has no `uvx`.

**Organization**: Tasks are grouped by user story. The three stories are all P1; US1 is the MVP, US2 and US3 harden it.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel with other ready tasks (different files, dependencies met)
- **[Story]**: US1, US2, US3 from spec.md
- Test tasks cite the acceptance criteria they prove, e.g. `[AC-001]`
- Within a wave, tasks that edit the same file (mostly `tests/test_setup.py` and `tools/setup`) run one after another

## Settled plan-review findings (applied by T001)

- **F-001**: under the exclusive lock, when the live installation is current for this ref and fingerprint (`Setup.current`), `--prepare` prints `nothing to prepare: this checkout is already installed for <ref>` and exits 0, so a second command started together with the first reaches the launcher.
- **F-002**: "installation present" (prepare step 5) uses `Setup.live_entries`, which excludes entries holding a tracked file, not raw `entries(root)`.
- **F-003**: the launcher checks "installed" before `_hold` for `trust` and `discard-runs`, so an uninstalled checkout gets the refusal and no `checkout.lock` or state directory is created.
- **F-004**: a candidate whose `checkout.lock` file is absent is rejected with `it has no checkout lock`; preparation never creates a file in another checkout's operator state.
- **F-005**: doctor's trust check on an uninstalled checkout names `ballast setup`, and also the first `ballast run`, `ledger` or `intake` when the pinned version declares `[setup] prepare`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Bring the contracts in line with the settled findings and open the ADR before code changes.

- [x] T001 Amend the feature contracts for F-001 to F-005 (see "Settled plan-review findings" above): in `specs/15-worktree-setup/contracts/prepare.md` add the F-001 "nothing to prepare" exit-0 step between steps 4 and 5 and its output line, and reword step 5 to use `Setup.live_entries` (F-002); in `specs/15-worktree-setup/contracts/cli-and-launcher.md` state that the installed check runs before `_hold` for `trust`/`discard-runs` (F-003) and add the doctor remedy wording (F-005); in `specs/15-worktree-setup/data-model.md` add rejection reason `it has no checkout lock` (F-004) and change the "Prepare only when" rule to `live_entries` (F-002); in `specs/15-worktree-setup/research.md` R4 rule 2 and R6 rule 3 to match. Wording only; no intent change.. Evidence: Done in the Autonomous run's implement step (contracts, data-model, research carry F-001 to F-005); later refined for candidate reporting, the parent-link reason and the shared-lock F-001 check.
- [x] T002 [P] Write `docs/adr/0009-worktree-preparation.md` with status "Proposed (accepted on merge)", extending ADR-0007 per plan.md "Proposed architecture decisions": first `run`/`ledger`/`intake` runs the pinned setup in `--prepare` mode declared by `[setup] prepare`; sources widened to every recorded live or kept installation of the repository on this machine, accepted by pin, fingerprint, content and executable bits; `executable` record field; committed first preparation at another fingerprint rolled back; trust baselines never read across checkouts, a predating one removed. Link ADR-0002, ADR-0007, ADR-0008 and this feature's research R1 to R9 (depends on T001). Evidence: `docs/adr/0009-worktree-preparation.md`, commit af19a63.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared test fixtures, the record and journal format changes, and the version declaration that every story builds on.

**⚠️ CRITICAL**: No user-story implementation starts until its foundational dependencies here are done.

- [x] T003 Add a `WorktreeCase(ProjectCase)` fixture in `tests/test_setup.py`: a temporary repository with `git worktree add` linked worktrees, `XDG_STATE_HOME`/`XDG_DATA_HOME` inside the test directory, a helper that runs a faked `ballast setup` at a given ref in a checkout (reusing `fake_run`, `fake_fetch` and per-ref archives), a no-network guard that patches `_fetch_source` and `urllib.request.urlretrieve` to fail the test, a `run_prepare(checkout)` helper invoking `tools/setup --project <checkout> --prepare` under `python3 -IS` with a `PATH` lacking `uvx`, and `snapshot(paths)`/`assertUnchanged(before, after)` helpers covering project-owned files (`ballast.toml`, constitution, `docs/policies/project/`), each source checkout's tree and its operator-state directory. Evidence: `WorktreeCase` in `tests/test_setup.py`: real `git worktree add`, offline guard on `_fetch_source`, `urlretrieve` and `socket.connect`; children via the kill wrapper (barrier, `--prepare`, socket guard).
- [x] T004 Write failing tests in `tests/test_setup.py` `WorktreeCopyTests` [AC-010]: a fresh `ballast setup` record has a sorted `executable` list of installed regular files with an execute bit (no `link:` values, no `LOCAL_STATE`/`__pycache__`); `ballast setup`'s existing primary copy is rejected when a copied file's execute bit differs from the record; a record without `executable` is still accepted by `ballast setup`'s copy (depends on T003). Evidence: `WorktreeCopyTests.test_record_lists_executable_files`, `test_changed_file_mode_is_not_copied`, `test_record_without_modes_is_still_copied`; red on 1ce1f9a, green on dedc146.
- [x] T005 In `tools/setup`, make `validate()` write `executable` into every new installation and kept record per data-model.md, and make `copy_verified()` compare the stage copy's executable set to the record's list whenever the record has one, returning the `its file modes differ from its record at <path>` reason (depends on T004). Evidence: commit dedc146 (`validate`, `copy_verified`, `executables`).
- [x] T006 [P] In `tools/setup`, add `mode` (`"setup"` default, absent read as `setup`) and `source` (path or `null`) to the journal written by `attempt()`, and `mode` to `setup-holder.json` written under `lock()`; make the held-lock refusal read `another ballast <setup|preparation> (PID p, started t, ref r) holds this checkout. Next: wait for it to finish, then rerun the command` per contracts/prepare.md. Evidence: commit dedc146 (journal `mode`/`source`, holder `mode`, refusal text); asserted in `PrepareConcurrencyTests.test_one_preparation_per_worktree`.
- [x] T007 [P] Add `prepare = true` with its comment under `[setup]` in `tools/cli.toml` (data-model.md "Manifest addition"), and extend `declarations()` in `tools/ballast` to also return whether the version declares `[setup] prepare = true` (absent or not `true` → cannot prepare); update its callers. Evidence: commit fd4d811 (`tools/cli.toml`, `Declarations`).

**Checkpoint**: Records list executable files, journals carry a mode, and the CLI can read the declaration.

---

## Phase 3: User Story 1 - A new worktree reaches preflight on its first command (Priority: P1) 🎯 MVP

**Goal**: The first `ballast run`, `ledger` or `intake` in a new worktree prepares its installation offline from a verified local installation, then stops at a precise trust preflight.

**Independent Test**: With a verified primary installation, create a worktree, block the network, run `ballast run start` there: a complete installation appears, nothing is fetched, the command stops at the trust preflight naming the inputs and `ballast trust`; after `ballast trust` the run starts.

### Acceptance tests for User Story 1

- [x] T008 [US1] Write failing `PrepareTests(WorktreeCase)` in `tests/test_setup.py`: `test_new_worktree_is_prepared_offline` [AC-001] (installation equals the source record, no fetch, record ref and fingerprint equal the worktree's, no constitution created, timing under 10 s on the fake installation [SC-005]); `test_sibling_and_kept_sources` [AC-003] (primary at Y with sibling at X → copied from sibling; primary's kept X → copied from kept; output names the source); `test_existing_installation_is_never_replaced` [AC-006] (stale, one modified file, other-pin and partial installations → `this checkout already holds an installation (…)`, next `ballast setup`, tree unchanged; plus an F-002 subtest where a project-tracked file under `docs/policies/` does not count as an installation and preparation proceeds) (depends on T003). Evidence: `PrepareTests.test_new_worktree_is_prepared_offline`, `test_sibling_and_kept_sources`, `test_existing_installation_is_never_replaced`, `test_tracked_policy_is_not_an_installation` (F-002); red on base.
- [x] T009 [P] [US1] Write failing `PrepareTriggerTests` in `tests/test_ballast.py` against the CLI with a local standard: `test_run_prepares_then_reaches_preflight` [AC-001, AC-002, SC-001] for each of `run`, `ledger`, `intake` (prepare output, then launcher exit 2 with the full no-baseline message, no `trusted.json`, no `ballast setup` invoked, no fetch); `test_doctor_trust_then_run` [AC-004] (`setup --check` current, doctor setup check passing, after `trust` the run passes preflight with no journal and the record unchanged); `test_non_preparing_commands` [AC-005] (`trust`, `discard-runs` refuse with the install message and write nothing; `doctor`, `status --json`, `preview` leave the worktree snapshot unchanged); `test_version_without_declaration` [AC-007] (standard without `[setup] prepare` → `nothing is installed in this checkout; run \`ballast setup\``, exit 2, `tools/setup` never run, no fetch; a journal-only checkout falls through to the launcher's unfinished-setup refusal) (depends on T003). Evidence: `PrepareTriggerTests` in `tests/test_ballast.py` (preflight per command, doctor/trust/run, non-preparing commands, no declaration); `preview` not exercised offline (it needs the network to build its disposable project) and unchanged by this feature.
- [x] T010 [P] [US1] Write failing tests in `tests/test_spec_workflow.py` `TrustedLauncherTests` [AC-002, AC-005]: the no-baseline refusal reads `no trusted baseline for this checkout; review its protected inputs (<present bases>), then run \`ballast trust\`` listing only existing bases (with and without `.venv`, `.git` pointer for a linked worktree); `trust` and `discard-runs` on an uninstalled checkout refuse with the new install message, exit 2, and create no state directory or `checkout.lock` even when the state directory already exists (F-003); `run`/`ledger`/`intake` on an uninstalled checkout give the same message. Evidence: `TrustedLauncherTests.test_no_baseline_names_the_inputs_to_review`, `test_uninstalled_checkout_is_refused_without_writing` (F-003); red on base.
- [x] T011 [P] [US1] Write failing tests in `tests/test_doctor.py` `ProjectTests` [AC-004, AC-005]: doctor still classifies the new no-baseline text as "trust missing"; doctor on an uninstalled worktree changes nothing (snapshot); its remedy names `ballast setup` and, when the pinned version declares `[setup] prepare`, also the first `ballast run`, `ledger` or `intake` (F-005). Evidence: `ProjectTests.test_setup_then_trust` names both remedies and setup alone without the declaration; doctor's write-nothing snapshot covers the uninstalled checkout.

### Implementation for User Story 1

- [x] T012 [US1] Add `Setup.candidates()` in `tools/setup`: parse `git worktree list --porcelain -z` run in this checkout, skip this checkout, yield in data-model.md order (own kept → primary live → primary kept → each other linked worktree's live then kept), and mark entries Git lists as `prunable` or whose path is missing with `its path no longer exists` (depends on T008). Evidence: `Setup.candidates()`, commit dedc146: a checkout without a record or kept copy holds no candidate and is not reported.
- [x] T013 [US1] Add `Setup.copy_candidate(candidate, stage)` in `tools/setup` per research.md R4: reject when the candidate's `setup-attempt.json` exists, when its `checkout.lock` file is absent (`it has no checkout lock`, F-004) or a shared non-blocking lock fails (`it is being set up`); hold the shared lock through the copy; read the record only after the lock (`launcher.read_record` for live, `copy_kept`'s checks for kept); reject on ref (`it is for <ref>, not <pin>`), fingerprint (`it was built for another configuration`), missing `executable` (`its record predates file-mode checks`), and `copy_verified` content/mode mismatch; wrap `OSError` as `it is unreadable: <error>`; on rejection discard the stage contents so no partial copy remains; never open `trusted.json` (depends on T005, T006, T012). Evidence: `Setup.copy_candidate()`, `mismatch()`, `_share()`, `_linked_parent()`, commit dedc146.
- [x] T014 [US1] Add the `--prepare` flag to `cli()` and `Setup.prepare()` in `tools/setup` following the amended contracts/prepare.md order: state dir, exclusive lock (holder `mode: prepare`), journal handling (prepare journal → `recover`, other → refusal), in-progress refusal, F-001 `Setup.current` → `nothing to prepare` exit 0, F-002 `live_entries` installation-present refusal, `check_links(PARENTS)`/`check_ignored()`, candidate walk printing `skipped <path>: <reason>`, no-candidate refusal `no verified installation of <pin> with this ballast.toml on this machine (<n> checked)` with the contract's next action (stage discarded, journal removed), then validate/switch/verify/commit/finish as setup with the constitution skipped, and the two closing output lines; never call `install_spec_kit` or `_fetch_source`; update the module docstring (depends on T013). Evidence: `--prepare`, `Setup.prepare()`, `settled()`, commit dedc146.
- [x] T015 [US1] In `tools/spec_workflow/launcher.py`, change `_trust_refusal`'s no-baseline text to list the existing `input_bases` and `ballast trust` (keep the `no trusted baseline` prefix), and in `main` check "installed" before `_hold` for `trust` and `discard-runs`, refusing with the contract's install message (exit 2, nothing created); give `run`/`ledger`/`intake` the same refusal when nothing is installed (depends on T010). Evidence: commit b6f1804.
- [x] T016 [US1] In `tools/ballast`, add `PREPARING = ("run", "ledger", "intake")`, `needs_installation(root)` (`run.py` not a file, or `operator_state(root)/setup-attempt.json` exists) and the preparation step in `main` per contracts/cli-and-launcher.md steps 1 to 5: old-version refusal (or fall through for journal-only), `damage()` refusal without fetch unless `BALLAST_STANDARD_DIR` is set, child `[PYTHON, "-IS", standard/"tools/setup", "--project", root, "--prepare"]` with inherited stdio and `cwd=root` returning its non-zero exit code, then `execv` as today; add the one-sentence usage text and docstring change (depends on T007, T009, T014). Evidence: commit fd4d811 (`PREPARING`, `needs_installation`, `prepare`).
- [x] T017 [US1] Update doctor's `_trust` remedy in `tools/ballast` for an uninstalled checkout to also name the first `ballast run`, `ledger` or `intake` when `declarations()` reports `prepare` (F-005) (depends on T007, T011). Evidence: commit fd4d811.

**Checkpoint**: T008 to T011 pass; a new worktree reaches the trust preflight with one command and no download.

---

## Phase 4: User Story 2 - Nothing is reused across a different pin, configuration or content (Priority: P1)

**Goal**: A worktree only ever receives an installation built for exactly its pin and `ballast.toml`, matching its record including file modes, and never another checkout's trust baseline.

**Independent Test**: Create worktrees differing in pin, in `[agents.permissions]`, and against a source altered after its record; each first command rejects the source with a named reason, fetches nothing; a worktree identical to a trusted primary still has no baseline.

### Acceptance tests for User Story 2

- [x] T018 [US2] Write failing tests in `tests/test_setup.py` `PrepareTests`: `test_other_pin_is_never_used` [AC-008] (only pin-X sources, worktree at Y → refusal naming `ballast setup`, no Y entries, reason `it is for X, not Y`, no fetch); `test_other_configuration_is_never_used` [AC-009] (only `[agents.permissions]` differs → `it was built for another configuration`, generated `claude-settings.json` absent); `test_mismatched_content_is_rejected` [AC-010, SC-003] with subtests for an added, missing and altered file, a changed executable bit and a record without `executable`, each reason printed and no partial installation left; `test_unfinished_or_busy_source_is_rejected` [AC-011] (source journal present; source exclusive lock held by another process; source without a `checkout.lock` file, F-004, and no file created in its state) (depends on T003). Evidence: `PrepareTests.test_other_pin_is_never_used`, `test_other_configuration_is_never_used`, `test_mismatched_content_is_rejected` (6 subtests), `test_unfinished_or_busy_source_is_rejected` (journal, held lock, no lock file), plus `test_source_reached_through_a_link_is_rejected`.
- [x] T019 [US2] Write failing `PrepareTests.test_no_baseline_is_inherited` in `tests/test_setup.py` [AC-012, SC-003]: a trusted primary with byte-identical inputs; after preparation the worktree has no `trusted.json`, an `open` audit shows no `trusted.json` anywhere was opened for reading, and preflight still refuses; plus a stale `trusted.json` at a reused worktree path is removed with the `removed a trust baseline left by an earlier checkout at this path` line (depends on T003). Evidence: `PrepareTests.test_no_baseline_is_inherited` (audit hook on `open`; reused-path removal).
- [x] T020 [P] [US2] Write failing `PrepareTriggerTests.test_damaged_standard_refuses` in `tests/test_ballast.py` [AC-013]: a cached standard with one altered file → `the cached standard <ref> is damaged at <path>; run \`ballast setup\` to fetch it again`, exit 2, no fetch, worktree snapshot unchanged, `tools/setup` never run (depends on T003). Evidence: `PrepareTriggerTests.test_damaged_standard_refuses`.
- [x] T021 [US2] Wrap every `PrepareTests` case in `tests/test_setup.py`, successful or refused, with `snapshot`/`assertUnchanged` of the worktree's `ballast.toml`, constitution and `docs/policies/project/`, and of each source checkout's tree, installation record, run state and `trusted.json` [AC-014] (depends on T008, T018, T019). Evidence: `WorktreeCase.prepare()` snapshots every other checkout (tree, archives, operator state incl. `trusted.json`) and this worktree's project-owned files around every in-process preparation.

### Implementation for User Story 2

- [x] T022 [US2] In `Setup.prepare()` in `tools/setup`, delete a pre-existing `trusted.json` in this worktree's own state before the switch and print the contract line (research.md R8); confirm no code path in prepare mode reads any `trusted.json` (depends on T014, T019). Evidence: commit dedc146 (`fill_from_candidates`).
- [x] T023 [US2] In `tools/setup`, move `copy_from_primary`'s record read after its shared lock is taken (closing the read-then-lock window for `ballast setup`), reusing `copy_candidate`'s lock-then-read order without changing its other behavior; extend `WorktreeCopyTests` with a case proving the record is read under the lock (depends on T013). Evidence: commit dedc146; `WorktreeCopyTests.test_primary_record_is_read_under_its_lock` (red on base).

**Checkpoint**: T018 to T021 pass; every mismatch prevents reuse and no baseline crosses checkouts.

---

## Phase 5: User Story 3 - Many worktrees stay independent through concurrency, interruption and retry (Priority: P1)

**Goal**: Ten concurrent mixed-pin worktrees each prepare their own installation and keep their own state; a killed preparation is completed or rolled back by the next command; a missing source refuses cleanly and a retry converges.

**Independent Test**: Start ten first commands on two pins at once; advance a run in one and compare the others; SIGKILL a preparation at several points and rerun; remove the matching source for one pin and run there.

### Acceptance tests for User Story 3

- [x] T024 [US3] Write `PrepareConcurrencyTests(WorktreeCase).test_ten_worktrees_two_pins` in `tests/test_setup.py` [AC-015, SC-002]: ten worktrees across two pins, one verified source per pin, ten preparations released together by a barrier file, repeated 20 times; each worktree's record ref and fingerprint equal its own pin's, content equals the source record, no fetch, each refuses at its own launcher preflight (depends on T003). Evidence: `PrepareConcurrencyTests.test_ten_worktrees_two_pins` (20 repetitions).
- [x] T025 [US3] Write `PrepareConcurrencyTests.test_state_stays_per_worktree` in `tests/test_setup.py` [AC-016]: after the ten preparations, start, advance and discard a run in one worktree; every other worktree's and source's `.specify/workflows/runs/`, `trusted.json`, `in-progress` marker, `setup-attempt.json` and `checkout.lock` are unchanged and no worktree holds another's run state (depends on T003). Evidence: `PrepareConcurrencyTests.test_state_stays_per_worktree` (run state planted and discarded through the launcher in one worktree; the engine itself is not started offline).
- [x] T026 [US3] Write `PrepareTests.test_missing_source_then_setup` in `tests/test_setup.py` [AC-017]: no verified installation for the pin → refusal naming `ballast setup`, no stage or journal left, no fetch; after a faked `ballast setup` in that worktree, a new worktree at the same pin and `ballast.toml` is prepared from it offline (depends on T003). Evidence: `PrepareTests.test_missing_source_then_setup`.
- [x] T027 [US3] Write `PrepareTests.test_killed_preparation_is_recovered` in `tests/test_setup.py` [AC-018, AC-019, SC-004] with the existing SIGKILL wrapper at no fewer than five points (journal `staging`, mid-copy, journal `switching`, mid-switch rename, journal `committed`): the next preparation prints `recovered an interrupted preparation: …`, never leaves mixed files, and the final tree and record equal an uninterrupted preparation's; plus a committed preparation whose pin changed meanwhile is rolled back and the worktree is prepared for the new pin; plus `ballast setup` recovers a `prepare` journal and continues with a full setup (depends on T003). Evidence: `PrepareTests.test_killed_preparation_is_recovered` (copytree, validate, switching, rename, committed), `test_committed_preparation_at_a_changed_pin_is_rolled_back`, `test_setup_recovers_a_preparation`, `test_unfinished_setup_is_not_recovered_by_preparation`.
- [x] T028 [US3] Write `PrepareConcurrencyTests.test_one_preparation_per_worktree` in `tests/test_setup.py` [AC-020]: two concurrent preparations in one new worktree → one prepares, the other refuses naming `another ballast preparation (PID …)` and the wait-then-rerun action, final tree equals the source record; plus the F-001 sequenced case, where the second takes the lock after the first finished and exits 0 with `nothing to prepare` (depends on T003). Evidence: `PrepareConcurrencyTests.test_one_preparation_per_worktree` (held, sequenced, launcher-held and 5 unsequenced races).

### Implementation for User Story 3

- [x] T029 [US3] Extend `Setup.recover()` in `tools/setup` for `mode: prepare` journals per research.md R7: `staging` discards the work area, `switching` rolls back against the empty `before`, `committed` at the current fingerprint finishes and lets `prepare()` exit 0, `committed` at another fingerprint rolls back the new entries and any record `finish` wrote; print `recovered an interrupted preparation: <what is in place>`; `ballast setup` recovers the same journal then runs a full setup (depends on T006, T014, T027). Evidence: commit dedc146 (`recover`).

**Checkpoint**: T024 to T028 pass, including the 20-repetition loop.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [x] T030 [P] Replace the worktree sentence in "Installing the Spec Kit workflow" in `README.md` with a short "Worktrees" paragraph: the first `ballast run`, `ledger` or `intake` in a new worktree prepares its installation from a verified installation on this machine without downloading; trust is per worktree (`ballast trust` there); the first worktree at a new pin or `ballast.toml` still needs `ballast setup` (depends on T016). Evidence: commit af19a63.
- [x] T031 Reconcile `docs/adr/0009-worktree-preparation.md` with the implemented behavior (F-001 to F-005, recovery rules, rejection reasons), keeping status Proposed (depends on T002, T016, T022, T029). Evidence: commit af19a63, status Proposed.
- [x] T032 Run the fast gate and record the output for the PR: `uvx ruff check && uvx ruff format --check` and `uv run --no-project --python 3.13 --with pyyaml python -m unittest tests/test_*.py` (depends on T005, T015, T016, T017, T020, T021, T022, T023, T024, T025, T026, T028, T029, T030, T031). Evidence: `uvx ruff check && uvx ruff format --check` clean; `uv run --no-project --isolated --python 3.13 --with pyyaml python -m unittest tests/test_*.py` at `980511e`: 907 tests OK, 0 skipped, 709 s.
- [x] T033 Run the full local gate on a Linux machine with a systemd user session, the Codex CLI and the Spec Kit CLI, because `tools/spec_workflow/launcher.py` changes; record the result or, if no such machine is available, record that gate as unavailable in the PR (depends on T032). Evidence: The same run is the full local gate: this host has a systemd user session, the Codex CLI and the Spec Kit CLI (doctor: systemd-user, systemd-run, specify, agent-cli ok), and no test was skipped.
- [x] T034 Run the end-to-end scratch-project run from quickstart.md with two worktrees and the network blocked in them (`unshare -rn` or equivalent), and record commands, outputs and measured preparation time in the PR [AC-001, AC-002, AC-004, SC-001, SC-005]: prepare output then trust refusal in each worktree, doctor setup-current passing, `ballast trust && ballast ledger report` passing, per-worktree `installation.json` and no `trusted.json` before its own trust, clean `git status` apart from project-owned files in primary and worktrees (depends on T032). Evidence: Recorded in [quickstart.md](quickstart.md#end-to-end-scratch-project-run-record-in-the-pr): two worktrees prepared under `unshare -rn` in 0.57 s, trust refusal naming the inputs, `--check` current, trust then `ledger report` passing, per-worktree state, clean `git status`.
- [x] T035 Update the scenario map in `specs/15-worktree-setup/quickstart.md` with the final test names and record evidence for each AC and SC, ready for spec reconciliation (depends on T032). Evidence: [quickstart.md](quickstart.md#scenario-map) lists the final tests and evidence per AC and SC.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: T001 first; T002 after it. Neither blocks code.
- **Foundational (Phase 2)**: T003 blocks every test task; T005, T006, T007 block the implementation tasks that use the record, journal and declaration.
- **US1 (Phase 3)**: needs T003 to T007. Delivers the MVP.
- **US2 (Phase 4)**: tests need only T003; T022 and T023 need US1's `prepare()` and `copy_candidate()` (T013, T014). The rejection rules US2 tests are implemented in T013.
- **US3 (Phase 5)**: tests need only T003; T029 needs T006 and T014.
- **Polish (Phase 6)**: after all stories.

### User Story Dependencies

- **US1**: independent after Foundational.
- **US2**: its acceptance tests are independent; its implementation builds on US1's `copy_candidate()` and `prepare()`.
- **US3**: its acceptance tests are independent; its recovery implementation builds on US1's `prepare()`.

### Within Each User Story

- Tests are written first and fail before their implementation task.
- `candidates()` → `copy_candidate()` → `prepare()` → CLI trigger.

## Execution Wave DAG

| Wave | Tasks | Unblocked by |
| --- | --- | --- |
| 1 | T001, T003, T006, T007, T010, T011 | nothing |
| 2 | T002, T004, T008, T009, T015, T017, T018, T019, T020, T024, T025, T026, T027, T028 | T001; T003; T007 + T011; T010 |
| 3 | T005, T012, T021 | T004; T008; T008 + T018 + T019 |
| 4 | T013 | T005, T006, T012 |
| 5 | T014, T023 | T013 |
| 6 | T016, T022, T029 | T014 (+ T007, T009; T019; T006, T027) |
| 7 | T030, T031 | T016; T002, T016, T022, T029 |
| 8 | T032 | all implementation and test tasks |
| 9 | T033, T034, T035 | T032 |

Wave 2 holds many `tests/test_setup.py` tasks (T004, T008, T018, T019, T024 to T028): write them one after another, or in parallel only on separate test classes merged afterward. T009 and T020 share `tests/test_ballast.py`; T015 and T017 are in different files and parallel with the tests.

## Parallel Example: Wave 2

```text
Task: "T009 PrepareTriggerTests in tests/test_ballast.py"
Task: "T015 launcher no-baseline and not-installed messages in tools/spec_workflow/launcher.py"
Task: "T017 doctor remedy in tools/ballast"
Task: "T002 ADR-0009 in docs/adr/0009-worktree-preparation.md"
Task: "T008, then T018, T019, T024–T028 in tests/test_setup.py (one writer)"
```

## Implementation Strategy

### MVP First (User Story 1)

1. T001, T003 to T007.
2. T008 to T017: a new worktree is prepared offline by its first command and stops at the trust preflight.
3. **Validate**: T008 to T011 pass; run the quickstart steps for one worktree.

### Incremental Delivery

1. US1 → MVP.
2. US2 → every mismatch rejected with a reason, no baseline inheritance, project and source files untouched.
3. US3 → ten-worktree concurrency, interruption recovery, missing source and retry.
4. Polish → README, ADR, gates, end-to-end run, evidence map.

All three stories are P1 and ship together in one PR; the order above only sequences the work.

## Notes

- Reviews required at merge for this R2 change (review matrix): engineering, security, test, documentation, and architecture against ADR-0007; then Spec Kit converge and spec reconciliation.
- Any discovery that changes intent, scope or a security boundary goes to `specs/15-worktree-setup/decisions.md` before continuing.
- Never weaken an existing `tests/test_setup.py` fault-injection or `WorktreeCopyTests` case to make a new one pass.
