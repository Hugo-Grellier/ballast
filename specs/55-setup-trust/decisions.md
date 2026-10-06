# Decisions

Autonomous run `38380ec3`, implemented outside the run by an operator-assigned agent. Every resolution below was made by the driving agent under the operator's standing authority for v1.0 issues (2026-10-05) and is listed for merge review; merging the PR is the human decision point (BL-INV-006). DEC-0001 and DEC-0002 resolve plan-review findings F-003 and F-005 as task T001 asked. DEC-0003 to DEC-0008 record where the implementation had to depart from the plan's wording.

## DEC-0001 — Proposal

- **Found during**: plan review (finding F-003), task T001.
- **Conflict**: the order of evaluation in `contracts/setup-trust.md` does not say whether `settle` checks `BALLAST_TAMPERED` and the in-progress marker before or after the "keep a matching baseline" step, so a skipped verdict might not name the remedy when the baseline matches (AC-019).
- **Label**: spec ambiguity.
- **Options**:
  1. Check the markers first, so the verdict always names the remedy.
  2. Keep a matching baseline first and report the markers only when no baseline matches.
- **Needs**: a resolution before the contract is final.

## DEC-0001 — Resolution

- **Status**: resolved by the driving agent under the operator's standing authority for v1.0 issues (2026-10-05), listed for merge review. Option 1.
- **Resolution**: `settle` checks `BALLAST_TAMPERED` and the in-progress marker before the "keep a matching baseline" step, so a skipped verdict names the remedy even when the baseline matches. Nothing is written either way, and the launcher still refuses. `contracts/setup-trust.md` order of evaluation is updated to match.
- **Rationale**: resolved toward AC-019.

## DEC-0002 — Proposal

- **Found during**: plan review (finding F-005), task T001.
- **Conflict**: it is unspecified what provenance a baseline recorded through the operator-baseline alternative carries, and so whether a later setup that records again can chain from it without the network or `ballast trust`.
- **Label**: spec ambiguity.
- **Options**:
  1. The baseline carries `setup` provenance; a later recording needs the network (the default branch) or `ballast trust`.
  2. Carry the operator reference forward, so a chain of setup recordings can continue offline.
- **Needs**: a resolution before the documentation is final.

## DEC-0002 — Resolution

- **Status**: resolved by the driving agent under the operator's standing authority for v1.0 issues (2026-10-05), listed for merge review. Option 1.
- **Resolution**: a baseline recorded through the operator-baseline alternative carries `setup` provenance, so a later setup that records again needs the network (the default branch) or `ballast trust`. The README and the policy template say so.
- **Rationale**: the operator reference is not carried forward, because a chain of setup recordings must always end at an operator review or the default branch.

## DEC-0003 — Proposal

- **Found during**: implementation, updating the setup-output tests.
- **Conflict**: FR-008 and AC-017 require a skipped verdict's reason to be printed; AC-023 and research R18 assume ineligible fixtures keep today's output. The two cannot both hold for setup-output tests that assert the whole output of an ineligible fixture.
- **Label**: spec ambiguity.
- **Options**:
  1. Always print the reason (FR-008, AC-017, SC-002 are the safety-relevant requirements), place it before `Prepared the ... installation ...` so the output still ends with today's two lines, and update the affected exact-output tests.
  2. Keep today's output for ineligible fixtures and omit the reason there, which breaks FR-008.
- **Needs**: a resolution before the tests are final.

## DEC-0003 — Resolution

- **Status**: resolved by the driving agent under the operator's standing authority for v1.0 issues (2026-10-05), listed for merge review. Option 1.
- **Resolution**: the reason is always printed; for a preparation the reason line comes before `Prepared the ... installation ...`, so tests using `endswith` keep passing unchanged. Nine existing tests in `tests/test_setup.py` that assert the full output of an ineligible fixture (`NoOpTests.test_rerun_changes_nothing`, `RecoverableSetupTests.test_tracked_files_are_never_removed_or_replaced`, `PrepareTests.test_new_worktree_is_prepared_offline`, `test_no_baseline_is_inherited` and the five subtests of `test_killed_preparation_is_recovered`) now expect the added reason line through two constants (`NOT_RECORDED_RUNS`, `NOT_RECORDED_POINTER`); no assertion was removed or loosened and no launcher trust or refusal test was touched.
- **Changed now**: the same added reason line is the one edit to `tests/test_ballast.py` (`PrepareTriggerTests.test_run_prepares_then_reaches_preflight`, which compares the whole output of a first `ballast run` in a worktree whose configuration pins no repository). Task T035's "no edited lines" therefore holds for the launcher's trust and refusal tests and for `tests/test_spec_workflow.py`, `tests/test_doctor.py` and `tests/test_branch_sync.py`, and is relaxed to these ten expectation lines for the setup-output tests.

## DEC-0004 — Proposal

- **Found during**: implementation of preparation.
- **Conflict**: FR-009 says a preparation records "under the same conditions as setup", but research R7 and ADR-0011 require that a baseline at a reused path is removed, never reused. Reading its own baseline would contradict that.
- **Label**: departure from FR-009's wording (engineering ENG-004).
- **Options**:
  1. `settle(mode="prepare")` skips the "keep a matching baseline" step and the operator-baseline alternative. Consequence: an offline preparation can never record, because only the default-branch alternative applies to it.
  2. Let a preparation keep a matching baseline, contradicting R7 and ADR-0011.
- **Needs**: a resolution before merge review.

## DEC-0004 — Resolution

- **Status**: resolved by the driving agent under the operator's standing authority for v1.0 issues (2026-10-05), listed for merge review. Option 1.
- **Resolution**: `settle(mode="prepare")` skips the "keep a matching baseline" step and the operator-baseline alternative. A preparation installs a checkout that held nothing, and any baseline found in its state predates it and was just removed (AC-008).
- **Rationale**: not opening it keeps `PrepareTests.test_no_baseline_is_inherited` (no `trusted.json` opened) true for every ineligible case.

## DEC-0005 — Proposal

- **Found during**: implementation of the default branch name check.
- **Conflict**: the plan validated `<default>` with `launcher.REF`, a standard version pattern without slashes, so a default branch such as `release/1` would be rejected. `ledger.REF`, which branch synchronization already uses for the same purpose, accepts it.
- **Label**: implementation defect, no product change.
- **Options**:
  1. Match `ledger.REF`; still reject a leading `-`, `..`, `@{`, `//` and anything outside `[A-Za-z0-9._/-]`.
  2. Keep `launcher.REF`.
- **Needs**: a resolution recorded for review.

## DEC-0005 — Resolution

- **Status**: resolved by the driving agent under the operator's standing authority for v1.0 issues (2026-10-05), listed for merge review. Option 1.
- **Resolution**: `<default>` must match `ledger.REF`, so a default branch such as `release/1` is observable.

## DEC-0006 — Proposal

- **Found during**: implementation of the launcher and setup-trust interfaces.
- **Conflict**: the plan's interface wording took a checkout root where the functions never needed one, and left the Git rules duplicated across modules and the acceptance tests' location open.
- **Label**: implementation detail.
- **Options**:
  1. `launcher.record_baseline(state, inputs, *, source, reference=None)`, `launcher.baseline_source(state)` and `launcher.operator_baseline(state)` take the state directory only; the reviewed record needs the root only to validate `XDG_STATE_HOME` (`reviewed_repositories(root)`, `add_reviewed(root, repository)`). The shared Git rules live in `setup_trust` (`DROPPED_ENV`, `GIT_LOCATION`, `child_path`, `base_environment`, `throwaway_environment`, `repository_url`), and `branch_sync` and `draft_pr` delegate to them. Acceptance tests live in the new `tests/test_setup_trust.py`.
  2. Follow the plan's wording literally, keeping separate copies of the environment rules.
- **Needs**: a resolution recorded for review.

## DEC-0006 — Resolution

- **Status**: resolved by the driving agent under the operator's standing authority for v1.0 issues (2026-10-05), listed for merge review. Option 1.
- **Resolution**: the interfaces are as in option 1. There is one copy of the security-relevant environment (plan-review F-002). Acceptance tests for the setup and preparation flows live in `tests/test_setup_trust.py` rather than `tests/test_setup.py`, which only gained the nine expectation updates of DEC-0003.

## DEC-0007 — Proposal

- **Found during**: implementation of `status --json` (AC-023).
- **Conflict**: AC-023 and SC-003 want the printed JSON for a checkout without a baseline unchanged, while FR-013 requires `baseline_source` once a baseline exists. Two existing launcher tests compare the whole object after `ballast trust` (`TrustedLauncherTests.test_status_reports_the_refusal_without_writing` and `test_pinned_and_installed_versions_differ`).
- **Label**: implementation detail serving AC-023, with a residual conflict.
- **Options**:
  1. Include the key only when a baseline exists (`"setup"` or `"trust"`) and omit it otherwise; the three whole-object assertions of the two tests above gain `"baseline_source": "trust"`.
  2. Always include the key as `null` without a baseline, which changes the output for every checkout without one and breaks `PrepareTriggerTests.test_non_preparing_commands`.
- **Needs**: a resolution before merge review, since it edits launcher trust tests.

## DEC-0007 — Resolution

- **Status**: resolved by the driving agent under the operator's standing authority for v1.0 issues (2026-10-05), listed for merge review. Option 1.
- **Resolution**: the key is omitted rather than `null` without a baseline, so the printed JSON for a checkout without a baseline is byte-identical to before and `PrepareTriggerTests.test_non_preparing_commands` (which compares the whole object) passes unedited. Doctor treats an absent and a `null` key the same.
- **Changed now**: the three whole-object assertions of the two launcher tests gain `"baseline_source": "trust"`; no other line of those tests changed and no refusal or comparison assertion was touched. This is the only edit to a launcher trust or refusal test.

## DEC-0008 — Proposal

- **Found during**: security review (SEC-004, SEC2-001) and engineering review (ENG-009).
- **Conflict**: the reviewed-repositories record was machine-wide and digest-free (FR-005 forbade digests), so a checkout whose committed `ballast.toml` was repointed to a second reviewed repository whose default branch carried the same configuration files was eligible. Security-2 E1 demonstrated it: a widened `[agents.permissions]` was recorded.
- **Label**: proposed product change (it amends FR-005).
- **Options**:
  1. Keep the record digest-free and accept the repoint.
  2. (b) `ballast trust` records, per repository, the digests of the `ballast.toml` and constitution it trusted (the pairs accumulate). Setup and preparation count the default branch only when the checkout's two files equal a pair reviewed for the repository its `ballast.toml` pins, checked before any network request.
- **Needs**: a resolution before merge review.

## DEC-0008 — Resolution

- **Status**: resolved by the driving agent under the operator's standing authority for v1.0 issues (2026-10-05), listed for merge review. Option 2 (b).
- **Resolution**: "reviewed" means both equal to the live default branch and reviewed for that repository. A name without a pair, or any malformed part of the record, is eligible for nothing. The checkout's own earlier operator baseline (re-setup) is unchanged and needs no record.
- **Consequences**: a repoint to another reviewed repository is no longer eligible unless that exact configuration was reviewed for it; a default branch that moves to new bytes needs one `ballast trust` per machine before fresh checkouts of it are recorded; the record can grow by one pair per trusted configuration. FR-005, the Reviewed repositories entity, AC-016, data-model, the launcher contract, ADR-0015, README and the policy template are updated. SEC2-003 is addressed together: `ballast trust` prints a line when it adds to the record and `ballast doctor` lists the reviewed repositories (`launcher.py reviewed --json`).
- **Changed now**: the fixture records the digests with the repository; four expectations of "differs from ... default branch" for an unreviewed widened configuration now expect "was not reviewed for" (refused earlier, without network), and the trust-output assertion gains the one new line.
