# Test review: 55-setup-trust (setup records the trust baseline)

- Reviewer: test reviewer, independent context
- Change: `git diff 641fa7f..HEAD`, branch `feat/55-setup-trust`, risk R2 (launcher trust model)
- Scope examined: `tests/test_setup_trust.py` (all, main evidence); the new classes at the end of `tests/test_spec_workflow.py` (`RecordBaselineTests`, `LauncherStateCase`, `TrustProvenanceTests`, `SetupBaselineLauncherTests`); `TrustSourceTests` in `tests/test_doctor.py`; the nine expectation updates in `tests/test_setup.py` and the one in `tests/test_ballast.py`; read against `tools/spec_workflow/setup_trust.py`, the `launcher.py` provenance/reviewed-repository functions, `tools/setup` (`settle`, `report_*`, preparation's stale-baseline removal) and `tools/ballast` (doctor).
- Policies and artifacts read: `.agents/skills/ballast-test-review/SKILL.md`, `docs/policies/testing.md`, `docs/policies/project/testing.md`, `specs/55-setup-trust/spec.md` (AC-001 to AC-027), `quickstart.md` (AC to test table), `tasks.md`, `decisions.md`.
- Run: the new test classes of `tests/test_setup_trust.py` (all pass) and, for mutations, classes from `tests/test_setup.py`, `tests/test_spec_workflow.py` and `tests/test_doctor.py`. Mutations were applied only to a copy of the tracked tree in the scratchpad (`.../scratchpad/mut`); the repository files were never modified (`git status` shows no change under `tools/` or `tests/`). The full suite was not run.

## Covered criteria

| Criterion | Evidence |
| --- | --- |
| AC-001 | `SetupRecordsTests.test_clean_checkout_is_recorded_and_accepted` (exact output line with repository, branch, 12-hex commit; provenance reference with 40-hex commit; against a real local bare repository through the `repository_url` seam) |
| AC-002 | same test: `status --json` is `{installed, refusal: null, baseline_source: "setup"}`, then the real launcher subprocess for `run`, `ledger`, `intake` prints no refusal (weak negative on `"refusing"`, adequate here) |
| AC-003 | `test_doctor.TrustSourceTests` (canned `status --json` for `setup`, `trust`, absent, null, junk, refusal variants; one real launcher with `trust`); `TrustProvenanceTests.test_trust_writes_operator_provenance`, `test_a_setup_baseline_is_reported_as_setup`. The `setup` source is never checked through the real doctor (TEST-011) |
| AC-004 | `OperatorBaselineTests` (legacy baseline, bound `trust`, `setup` source rejected, unbound rejected, other configuration rejected; no network command asserted) |
| AC-005 | `test_no_op_setup_without_a_baseline_records_one`, `test_an_operator_baseline_is_left_untouched` (bytes and mtimes), `test_second_setup_leaves_a_matching_baseline_alone` |
| AC-006 | `PrepareTrustTests.test_a_new_worktree_is_trusted_by_its_first_command` |
| AC-007 | `test_a_branch_that_changed_the_configuration`, `test_a_branch_that_changed_the_constitution` (installed, no baseline, launcher refusal names `ballast trust`) |
| AC-008 | `test_a_stale_baseline_at_a_reused_path_is_never_reused` (eligible and ineligible); provenance removal not asserted (TEST-003) |
| AC-009 | `test_no_other_checkouts_baseline_is_read_or_copied` (open-call spy plus content equality); the existing `PrepareTests.test_no_baseline_is_inherited` |
| AC-010 | `LocalIneligibleTests.test_uncommitted_pin_bump`, `test_uncommitted_constitution`, `test_deleted_constitution_is_a_change` |
| AC-011 | `test_committed_widened_permissions` (network asserted, skipped with the exact reason) |
| AC-012 | `test_extra_file_under_specify`, `test_edited_installed_file`, `test_a_venv_is_not_written_by_setup`, `test_a_removed_record_file`, `test_a_linked_installed_file`, `test_a_missing_installation_record`, `test_a_standard_inside_the_checkout` |
| AC-013 | `WorktreePointerTests` (forged repository in the checkout, in an agent temp root, missing and wrong back-link, symlinked `.git`, malformed pointers, genuine pointer eligible, primary `.git` directory not checked); the `admin == common/worktrees/<name>` clause is not exercised (TEST-005) |
| AC-014 | `ObservationTests` (real unreachable path, refused credentials by interception, hung `ls-remote`, hung `fetch`, no default branch, missing and malformed pin, matching operator baseline records with no network command, `_run` bound and stdin closed) |
| AC-015 | `test_local_refs_remotes_and_rewrites_are_ignored` (origin remote, fetched remote ref, `insteadOf`, `refs/remotes/origin/HEAD` all pointed at a repository carrying the widened file; argv log contains only the pinned URL) plus `test_the_url_rule` for the real `repository_url`; `test_only_the_documented_commands_run` |
| AC-016 | `ReviewedRepositoryTests` (repointed repository with a matching stand-in, never-trusted machine, case-insensitive match, malformed record reads empty) and `EveryRefusalTests` case `unreviewed` |
| AC-017 | `EveryRefusalTests` (six ineligible fixtures through `Setup.main`: exit 0, success line, reason, `ballast trust`, previous baseline and provenance bytes unchanged; unobservable branch; failed installation records nothing) |
| AC-018 | `test_in_progress_marker`, `test_a_marker_makes_setup_refuse`, `PrepareTrustTests.test_a_marker_makes_preparation_refuse` |
| AC-019 | `test_tamper_marker`, `test_tamper_marker_with_a_matching_baseline` (DEC-0001). The in-progress marker with a matching baseline is not tested (TEST-011) |
| AC-020 | `test_saved_run_state_in_the_checkout` (each run-state directory), `test_a_linked_run_state_directory`, `test_unfinished_operator_runs` (active, stopped, unknown, garbage, list, unreadable), `test_finished_and_empty_operator_runs_are_eligible`, `test_an_empty_run_state_directory_is_not_run_state` |
| AC-021 | `test_a_marker_makes_setup_refuse` (a step always holds the marker and setup refuses before reaching `settle`, also on a no-op setup because the marker check precedes `current`); a simulated whole step is not run, which the criterion's own wording does not need |
| AC-022 | `SetupBaselineLauncherTests.test_a_changed_input_is_refused_exactly_as_after_trust` (exact refusal text for `status`, `run`, `ledger`, `intake`, exit 2) |
| AC-023 | See TEST-008: existing tests gained lines, and six existing lines were edited (documented in DEC-0003 except the `tests/test_ballast.py` one). No launcher trust or refusal test was edited. |
| AC-024 | `SetupBaselineLauncherTests.test_the_refusal_never_depends_on_the_provenance` (five provenance shapes; same refusal), `test_a_forged_setup_provenance_never_trusts_a_checkout`; `RecordBaselineTests.test_source_and_operator_baseline_for_every_provenance` |
| AC-025 to AC-027 | Documentation; `tests/test_governance.py` was not changed and has no ADR-0014 or BL-INV-002 specific assertion, so these rest on documentation review (as the spec states) |
| FR-012, FR-020 and write order | `RecordBaselineTests` (bytes equal today's serialization, provenance written first, crash between writes, 0600 and no link followed, ten concurrent `add_reviewed` processes); `SharedRulesTests` (shared environment, stdlib-only imports, `--check` and doctor never import `setup_trust`); `RecordStepTests` (recheck and rollback) |

## Review

review: tests
verdict: changes_required

The suite is behavioral, uses a real Git repository for the observation seam, a real launcher subprocess for acceptance and a real `ls-remote`/`fetch` against a local bare repository with and without `uploadpack.allowFilter`. The mutation results below show that nearly every eligibility condition fails a test when removed. One spec-listed edge case (recovery) has no executable evidence of the recording behavior, and a few conditions survive mutation; these are listed below. Only TEST-001 is required before merge; the rest are recommended hardening.

## Findings

### TEST-001 (medium): recovered setup and recovered preparation never exercise the recording path

- Location: `tests/test_setup_trust.py` (no recovery test); `tests/test_setup.py` `PrepareTests.test_killed_preparation_is_recovered` and `RecoverableSetupTests`; `tools/setup` `prepare()` (`self.report_recovered(self.settle(state))`) and `main()` after `recover()`.
- Evidence: the spec's first edge case says the recovering setup applies the same conditions and an interrupted attempt never leaves a baseline behind. The only recovery tests build their worktrees under `/tmp` (so the pointer check always skips) or in a checkout with saved run state, and they now assert only the `NOT_RECORDED_*` lines. Mutation `recover_settle` (replace the recovered preparation's `settle` with a stub) was caught only because the stub raised `NameError`, not because a recorded or not-recorded outcome changed.
- Required action: in `TrustWorktreeCase` (outside `/tmp`) kill a preparation at each point, including `committed`, retry, and assert a baseline with `setup` provenance exists only after the committed-point recovery and the retry, equals `launcher.trusted_inputs(worktree)`, and that no baseline exists between the kill and the retry. Add the equivalent for an interrupted `ballast setup` recovered by the next setup (no baseline after the kill, one after the retry on an eligible fixture).

### TEST-002 (low): preparation's refusal to read its own baseline is unguarded at the unit level

- Location: `tools/spec_workflow/setup_trust.py` `_reference` (`if mode == "setup" else None`).
- Evidence: mutation `prepare_reads_baseline_full` (always read the operator baseline) survived the whole new suite plus `PrepareTests.test_no_baseline_is_inherited` and `test_new_worktree_is_prepared_offline`, because `tools/setup` always removes the baseline first. The guard is defense in depth for FR-010 (R2), currently untested.
- Required action: add a direct `settle(..., mode="prepare")` test with a matching operator baseline in state and committed configuration that differs from the default branch; expect `skipped` with the `DIFFERS` reason, and the same call with `mode="setup"` recording.

### TEST-003 (low): a stale provenance record at a reused path is not asserted removed

- Location: `tools/setup` `fill_from_candidates` (`_remove_file(state / launcher.TRUSTED_SOURCE)`); `tests/test_setup_trust.py` `PrepareTrustTests.test_a_stale_baseline_at_a_reused_path_is_never_reused`.
- Evidence: mutation `no_remove_provenance` survived. AC-008 and quickstart say baseline and provenance are removed.
- Required action: in the `changed=True` variant assert `trusted-source.json` is absent after preparation.

### TEST-004 (low): the shared Git environment test depends on the ambient environment

- Location: `tests/test_setup_trust.py` `SharedRulesTests.test_branch_sync_shares_the_git_environment`, first assertion block.
- Evidence: deleting `GIT_TERMINAL_PROMPT` (and `GIT_ASKPASS`) from `throwaway_environment` survived when the runner exported `GIT_TERMINAL_PROMPT` and `GIT_ASKPASS` (as this review's environment does) and was caught only with those variables unset. The test can pass vacuously on such a machine.
- Required action: wrap the first block in `patch.dict(os.environ)` that removes `GIT_TERMINAL_PROMPT`, `GIT_ASKPASS`, `SSH_ASKPASS_REQUIRE` and `GIT_NO_LAZY_FETCH` first.

### TEST-005 (low): the `.git` pointer's `admin == common/worktrees/<name>` clause is untested

- Location: `tools/spec_workflow/setup_trust.py` `_check_pointer`; `WorktreePointerTests`.
- Evidence: mutation `admin_in_common` (drop that clause) survived. Every pointer test fails earlier on another clause (inside the checkout, agent temp root, back-link, malformed).
- Required action: add a case with an admin directory outside the checkout and temp roots whose `commondir` and `gitdir` back-link are consistent but which is not `<common>/worktrees/<name>` (for example the common directory itself or a sibling directory).

### TEST-006 (low): the config bytes-versus-snapshot digest check has no test

- Location: `tools/spec_workflow/setup_trust.py` `_evaluate` (`_no(CHANGED)` after reading the configuration files).
- Evidence: mutation `config_digest` survived. This is the guard against a swap between `launcher.trusted_inputs` and the single read; the post-write recheck covers a later swap but not this one.
- Required action: patch `setup_trust._read_regular` (or write the file from a patched `launcher.trusted_inputs`) so the bytes differ from the snapshot digest; expect `skipped` with the `CHANGED` text and no network command.

### TEST-007 (low): network timeouts' wiring and default-branch name validation are untested

- Location: `tools/spec_workflow/setup_trust.py` `_observe_in` (`timeout=LS_REMOTE_TIMEOUT`, `FETCH_TIMEOUT`; `ledger.REF.fullmatch(target)`).
- Evidence: mutations `ls_timeout` (drop the explicit `ls-remote` timeout, falling back to 30 s local default... same value, so only the intent is lost) and `upgrade_branch` (accept any advertised branch name) survived. `test_run_bounds_a_command_and_never_prompts` proves `_run` bounds a command; the hung-request tests replace `_run` wholesale, so neither shows the observation passes a timeout.
- Required action: record the `timeout` keyword in an `_run` interception and assert both network commands carry a bound at or below the documented values; add a stand-in whose HEAD symref names a branch the pattern refuses (for example with `..` or a space) and expect `no default branch`.

### TEST-008 (low): AC-023 is met in substance but not to the letter, and one edit is unrecorded

- Location: `tests/test_ballast.py` `PrepareTriggerTests` (1 line removed, 6 added); `tests/test_setup.py` (5 lines removed, 27 added); `specs/55-setup-trust/decisions.md` DEC-0003; `tasks.md` T035.
- Evidence: `git diff --numstat` shows 6 existing lines modified. DEC-0003 records the nine `tests/test_setup.py` expectations; the `tests/test_ballast.py` edit is not recorded, and T035 required no edited lines. Every edit only prepends the new "No trust baseline recorded" lines to an exact-output assertion; no assertion was removed or weakened, and no launcher trust or refusal test changed (`TrustedLauncherTests` and the refusal tests are untouched).
- Required action: add the `tests/test_ballast.py` edit to DEC-0003 and note the T035 deviation, so the reconciliation does not report an unexplained edit of an existing test.

### TEST-009 (low): a non-regular configuration file other than a link or an oversized file is untested

- Location: `tools/spec_workflow/setup_trust.py` `_read_regular` (`O_NONBLOCK`, `S_ISREG`); `LocalIneligibleTests`.
- Evidence: links (`test_a_link_for_the_configuration`) and size (`test_an_oversized_configuration`) are covered. Mutation `regular_check` survived (a directory or FIFO is still rejected later, by a read error or a digest mismatch), and nothing guards against setup hanging on a FIFO if `O_NONBLOCK` is lost.
- Required action: add a FIFO `ballast.toml` case (with a bounded test timeout) and a directory case, each expecting `skipped` and no hang.

### TEST-010 (low): two concurrent preparations are exercised only sequentially

- Location: `tests/test_setup_trust.py` `PrepareTrustTests.test_a_second_preparation_records_nothing`; spec edge case "Two commands prepare the same worktree at once".
- Evidence: task T022 asked for a concurrent preparation that finds the work done and records nothing; the delivered test runs the second preparation after the first. The existing `PrepareConcurrencyTests` does not assert on the baseline.
- Required action: in the existing concurrency class (or here), run two preparations of the same worktree at once and assert exactly one baseline write (one `Recorded` line across both outputs) and the loser's "nothing to prepare".

### TEST-011 (info): small evidence gaps and naming

- `TrustSourceTests.test_the_real_launcher_reports_each_source` checks only `trust`; doctor's `setup` wording is proven against a canned launcher answer only, which is adequate for FR-014 (doctor recomputes nothing) but never end to end with a setup-recorded baseline.
- DEC-0001 covers both markers, but the in-progress marker with a matching baseline is tested only for the tamper marker.
- `test_check_and_doctor_never_import_it` proves `tools/setup --check` does not import `setup_trust` by running it under `-I -S` with a `sys.modules` assertion (mutation `check_imports` was caught); the doctor half is a text search of `tools/ballast` for `setup_trust`.
- AC-021 shares its evidence with AC-018.
- The real GitHub URL path (HTTPS or SSH, real credentials) cannot be tested offline; `test_the_url_rule` and the quickstart's end-to-end check recorded in the PR carry it.

## Mutations tried

Applied to a copy of the tracked tree, running the new classes of `tests/test_setup_trust.py` unless noted. Result "caught" means at least one test failed.

| Mutation | Result |
| --- | --- |
| skip the `HEAD`-versus-working-tree check (`_check_committed`) | caught (4 tests) |
| skip the reviewed-repositories check | caught (7) |
| drop the mode and type check of the default-branch blob (symlink accepted) | caught (`test_a_symbolic_link_is_not_the_file`) |
| skip the post-write recheck | caught (`test_an_input_changing_during_the_check`) |
| skip the saved-run-state and unfinished-run check; keep only one of the two halves | caught (10, 6 and 4 tests) |
| let preparation read an operator baseline (`_reference`) | survived (TEST-002) |
| let preparation read the held baseline (`_evaluate`) | caught (9) |
| treat any held baseline as "kept" | caught (13) |
| skip the tamper marker check; check it after the "kept" step | caught (3 each) |
| skip the in-progress marker check | caught (1) |
| skip `_check_pointer`; drop the temp-root clause; drop the back-link clause | caught (9, 2, 2) |
| drop the `admin == common/worktrees/<name>` clause | survived (TEST-005) |
| skip `_check_installation` | caught (7) |
| standard inside the checkout allowed | caught (1) |
| accept any default-branch comparison result | caught (10) |
| skip the restore of the previous baseline after a failed record | caught (3) |
| drop `O_NOFOLLOW`; drop the size limit | caught (1 each) |
| drop the `S_ISREG` check | survived (TEST-009) |
| drop the configuration-versus-snapshot digest check | survived (TEST-006) |
| `_run` ignores a timeout; real `repository_url` returns the checkout's origin | caught (1 each) |
| drop `GIT_TERMINAL_PROMPT` or `GIT_ASKPASS` from the throwaway environment | survived with the ambient variables set, caught with them unset (TEST-004) |
| run throwaway Git without `GIT_DIR` and in the checkout | caught (30 failing, mostly incidental; AC-015's own test is among them) |
| drop the explicit `ls-remote` timeout | survived (TEST-007) |
| accept any default-branch name without `ledger.REF` | survived (TEST-007) |
| drop `--filter=blob:none` | survived (efficiency only; no behavioral requirement) |
| launcher: `operator_baseline` accepts `setup` provenance | caught (2) |
| launcher: provenance not bound to the baseline bytes | caught (6) |
| launcher: `ballast trust` records source `setup` | caught (4) |
| launcher: `ballast trust` stops recording the repository | caught (3) |
| tools/setup: stop removing the stale baseline in preparation | caught (3) |
| tools/setup: stop removing the stale provenance | survived (TEST-003) |
| tools/setup: import `setup_trust` at module level | caught (`test_check_and_doctor_never_import_it`) |
| tools/setup: recovered preparation's settle replaced by a stub | caught only through a `NameError` (TEST-001) |

## Resolution

Resolved by the implementer after the review; new tests are in `tests/test_setup_trust.py` unless noted.

- TEST-001 (medium): fixed. `PrepareTrustTests.test_a_killed_preparation_records_only_once_complete` (kill at `validate`, `switching` and `committed`, no baseline between, recorded after the retry), `test_a_recovered_preparation_that_is_ineligible_records_nothing`, and `RecoveredSetupTests` for an interrupted setup.
- TEST-002 (low): fixed. `PreparationBaselineTests` calls `settle` directly in both modes.
- TEST-003 (low): fixed. The stale-baseline test asserts `trusted-source.json` exists before and is absent after preparation.
- TEST-004 (low): fixed. `SharedRulesTests` clears the ambient variables first.
- TEST-005 (low): fixed. `WorktreePointerTests.test_an_admin_directory_that_is_not_a_worktree_entry`.
- TEST-006 (low): fixed. `ConfigurationReadTests.test_bytes_that_differ_from_the_snapshot`.
- TEST-007 (low): fixed. `ObservationTests.test_the_network_commands_are_bounded` and `test_a_default_branch_name_the_tool_refuses`.
- TEST-008 (low): fixed. `decisions.md` DEC-0003 now lists the `tests/test_ballast.py` edit and relaxes T035's "no edited lines" for the setup-output tests only.
- TEST-009 (low): fixed. `ConfigurationReadTests.test_a_directory_or_a_pipe_is_not_a_configuration_file`.
- TEST-010 (low): fixed. `PrepareTrustTests.test_two_preparations_at_once_record_once` runs two preparations in threads.
- TEST-011 (info): no action. Doctor's `setup` wording is proven against a canned launcher answer, which is what FR-014 requires; the end-to-end check on a scratch repository covers the real path.

Verdict after resolution: approved.
