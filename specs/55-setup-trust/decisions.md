# Decisions

Every decision here is agent-provisional (autonomous run `38380ec3`, implemented outside the run by an operator-assigned agent); merging the PR is the only human approval (BL-INV-006). DEC-0001 and DEC-0002 resolve plan-review findings F-003 and F-005 as task T001 asked. DEC-0003 to DEC-0006 record where the implementation had to depart from the plan's wording; each is listed for merge review.

## DEC-0001 - Evaluate the markers before keeping a matching baseline (plan-review F-003)

- **Classification**: spec ambiguity, resolved toward AC-019.
- **Decision**: `settle` checks `BALLAST_TAMPERED` and the in-progress marker before the "keep a matching baseline" step, so a skipped verdict names the remedy even when the baseline matches. Nothing is written either way, and the launcher still refuses. `contracts/setup-trust.md` order of evaluation is updated to match.

## DEC-0002 - Recording through the operator baseline writes `setup` provenance (plan-review F-005)

- **Classification**: spec ambiguity, resolved in the documentation.
- **Decision**: a baseline recorded through the operator-baseline alternative carries `setup` provenance, so a later setup that records again needs the network (the default branch) or `ballast trust`. The README and the policy template say so; the operator reference is not carried forward, because a chain of setup recordings must always end at an operator review or the default branch.

## DEC-0003 - A skipped verdict's reason is printed before preparation's own lines, and existing exact-output tests gain that line

- **Classification**: spec ambiguity (FR-008 and AC-017 require the reason; AC-023 and research R18 assume ineligible fixtures keep today's output).
- **Decision**: the two requirements cannot both hold for setup-output tests that assert the whole output of an ineligible fixture. FR-008, AC-017 and SC-002 are the safety-relevant ones, so the reason is always printed. For a preparation the reason line comes before `Prepared the ... installation ...` so the output still ends with today's two lines (`tests` using `endswith` keep passing unchanged). Nine existing tests in `tests/test_setup.py` that assert the full output of an ineligible fixture (`NoOpTests.test_rerun_changes_nothing`, `RecoverableSetupTests.test_tracked_files_are_never_removed_or_replaced`, `PrepareTests.test_new_worktree_is_prepared_offline`, `test_no_baseline_is_inherited` and the five subtests of `test_killed_preparation_is_recovered`) now expect the added reason line through two constants (`NOT_RECORDED_RUNS`, `NOT_RECORDED_POINTER`); no assertion was removed or loosened and no launcher trust or refusal test was touched. The same added reason line is the one edit to `tests/test_ballast.py` (`PrepareTriggerTests.test_run_prepares_then_reaches_preflight`, which compares the whole output of a first `ballast run` in a worktree whose configuration pins no repository). Task T035's "no edited lines" therefore holds for the launcher's trust and refusal tests and for `tests/test_spec_workflow.py`, `tests/test_doctor.py` and `tests/test_branch_sync.py`, and is relaxed to these ten expectation lines for the setup-output tests.

## DEC-0004 - Preparation never reads its own baseline

- **Classification**: a departure from FR-009's "same conditions as setup" that research R7 already states and ADR-0011 requires (a baseline at a reused path is removed, never reused); listed for merge review (engineering ENG-004). Consequence: an offline preparation can never record, because only the default-branch alternative applies to it.
- **Decision**: `settle(mode="prepare")` skips the "keep a matching baseline" step and the operator-baseline alternative. A preparation installs a checkout that held nothing, and any baseline found in its state predates it and was just removed (AC-008); not opening it keeps `PrepareTests.test_no_baseline_is_inherited` (no `trusted.json` opened) true for every ineligible case.

## DEC-0005 - The default branch name uses the ledger's branch pattern

- **Classification**: implementation defect fix, no proposal needed.
- **Decision**: `<default>` must match `ledger.REF`, which branch synchronization already uses for the same purpose, not `launcher.REF` (a standard version pattern without slashes), so a default branch such as `release/1` is observable. It still rejects a leading `-`, `..`, `@{`, `//` and anything outside `[A-Za-z0-9._/-]`.

## DEC-0006 - Interfaces

- **Classification**: implementation detail.
- **Decision**: `launcher.record_baseline(state, inputs, *, source, reference=None)`, `launcher.baseline_source(state)` and `launcher.operator_baseline(state)` take the state directory only (they never needed the checkout root); the reviewed record needs the root only to validate `XDG_STATE_HOME` (`reviewed_repositories(root)`, `add_reviewed(root, repository)`). The shared Git rules live in `setup_trust` (`DROPPED_ENV`, `GIT_LOCATION`, `child_path`, `base_environment`, `throwaway_environment`, `repository_url`); `branch_sync` and `draft_pr` delegate to them, so there is one copy of the security-relevant environment (plan-review F-002). Acceptance tests for the setup and preparation flows live in the new `tests/test_setup_trust.py` rather than `tests/test_setup.py`, which only gained the nine expectation updates above.

## DEC-0007 - `status --json` omits `baseline_source` without a baseline

- **Classification**: implementation detail serving AC-023.
- **Decision**: the key is present only when a baseline exists (`"setup"` or `"trust"`); with none it is omitted rather than `null`, so the printed JSON for a checkout without a baseline is byte-identical to before and `PrepareTriggerTests.test_non_preparing_commands` (which compares the whole object) passes unedited. Doctor treats an absent and a `null` key the same.
- **Residual conflict with AC-023 and SC-003**: FR-013 requires the key once a baseline exists, and two existing launcher tests compare the whole object after `ballast trust` (`TrustedLauncherTests.test_status_reports_the_refusal_without_writing` and `test_pinned_and_installed_versions_differ`). Their three whole-object assertions gain `"baseline_source": "trust"`; no other line of those tests changed and no refusal or comparison assertion was touched. This is the only edit to a launcher trust or refusal test; it is listed for merge review.

## DEC-0008 - A reviewed repository is bound to the configuration reviewed for it (security SEC-004, SEC2-001, engineering ENG-009)

- **Status**: resolved by the driving agent under the operator's standing authority for v1.0 issues (2026-10-05), listed for merge review. It is not an operator approval; merging the PR is the human approval.
- **Classification**: proposed product change (it amends FR-005, which forbade digests in the record).
- **Observation**: the record was machine-wide and digest-free, so a checkout whose committed `ballast.toml` was repointed to a second reviewed repository whose default branch carried the same configuration files was eligible (demonstrated by security-2 E1: a widened `[agents.permissions]` was recorded).
- **Decision**: option (b). `ballast trust` records, per repository, the digests of the `ballast.toml` and constitution it trusted (the pairs accumulate). Setup and preparation count the default branch only when the checkout's two files equal a pair reviewed for the repository its `ballast.toml` pins, checked before any network request; "reviewed" thus means both equal to the live default branch and reviewed for that repository. A name without a pair, or any malformed part of the record, is eligible for nothing. The checkout's own earlier operator baseline (re-setup) is unchanged and needs no record.
- **Consequences**: a repoint to another reviewed repository is no longer eligible unless that exact configuration was reviewed for it; a default branch that moves to new bytes needs one `ballast trust` per machine before fresh checkouts of it are recorded; the record can grow by one pair per trusted configuration. FR-005, the Reviewed repositories entity, AC-016, data-model, the launcher contract, ADR-0015, README and the policy template are updated. SEC2-003 is addressed together: `ballast trust` prints a line when it adds to the record and `ballast doctor` lists the reviewed repositories (`launcher.py reviewed --json`).
- **Edits to existing tests**: the fixture records the digests with the repository; four expectations of "differs from ... default branch" for an unreviewed widened configuration now expect "was not reviewed for" (refused earlier, without network), and the trust-output assertion gains the one new line.
