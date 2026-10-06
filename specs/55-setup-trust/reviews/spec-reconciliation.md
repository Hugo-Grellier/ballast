# Spec reconciliation: Setup records the trust baseline (#55)

- Review: spec-reconciliation (with the Spec Kit converge assessment)
- Reviewer: claude (model), a fresh pass by the agent finishing the feature after the second security review; same provider as the author, so it is an independent re-read of the artifacts, not a cross-provider review.
- Scope: branch `feat/55-setup-trust` rebased on `origin/main` (v0.8.1 pin). I read `spec.md`, `plan.md`, `tasks.md`, `decisions.md` (DEC-0001 to DEC-0008), `data-model.md`, `contracts/*.md`, `quickstart.md`, every report in `reviews/` (security, security-2, engineering, test, documentation, e2e), `tools/spec_workflow/setup_trust.py`, `launcher.py`, `tools/setup`, `tools/ballast`, the new tests, ADR-0015, the README and the policy template.
- Converge: no unbuilt feature work remains. T001 to T048 were done; T047 is done by [e2e.md](e2e.md); T049 is this report. The one gap found after the first reviews, SEC2-001 (a reviewed repository was not bound to the configuration reviewed for it), was a specification gap resolved as DEC-0008 and implemented test-first with SEC2-002 and SEC2-003.

Test names below are in `tests/test_setup_trust.py` unless a class from another module is named; the mapping is the one verified in [test.md](test.md) (every named test exists), extended by the tests this pass added.

## Acceptance criteria

| AC | Implementation | Deterministic evidence |
| --- | --- | --- |
| AC-001 | `setup_trust.settle`, `_evaluate`, `_default_branch`, `_observe`; `tools/setup` `settling` | `SetupRecordsTests.test_clean_checkout_is_recorded_and_accepted` (exact output line with repository, branch, 12-hex commit; provenance reference with 40-hex commit; against a real local bare repository through the `repository_url` seam) |
| AC-002 | `launcher.record_baseline`, unchanged `_trust_refusal` | same test: `status --json` is `{installed, refusal: null, baseline_source: "setup"}`, then the real launcher subprocess for `run`, `ledger`, `intake` prints no refusal (weak negative on `"refusing"`, adequate here) |
| AC-003 | `launcher.baseline_source`, `_status`; `tools/ballast` `_recorder`, `_trust` | `test_doctor.TrustSourceTests` (canned `status --json` for `setup`, `trust`, absent, null, junk, refusal variants; one real launcher with `trust`); `TrustProvenanceTests.test_trust_writes_operator_provenance`, `test_a_setup_baseline_is_reported_as_setup`. The `setup` source is never checked through the real doctor (TEST-011) |
| AC-004 | `_evaluate` (operator-baseline branch), `launcher.operator_baseline` | `OperatorBaselineTests` (legacy baseline, bound `trust`, `setup` source rejected, unbound rejected, other configuration rejected; no network command asserted) |
| AC-005 | `_evaluate` (kept branch), `tools/setup` `main` | `test_no_op_setup_without_a_baseline_records_one`, `test_an_operator_baseline_is_left_untouched` (bytes and mtimes), `test_second_setup_leaves_a_matching_baseline_alone` |
| AC-006 | `tools/setup` `prepare`, `settle(mode="prepare")` | `PrepareTrustTests.test_a_new_worktree_is_trusted_by_its_first_command` |
| AC-007 | `_check_committed`, `_default_branch` (DEC-0008 digests) | `test_a_branch_that_changed_the_configuration`, `test_a_branch_that_changed_the_constitution` (installed, no baseline, launcher refusal names `ballast trust`) |
| AC-008 | `tools/setup` `fill_from_candidates` | `test_a_stale_baseline_at_a_reused_path_is_never_reused` (eligible and ineligible); provenance removal not asserted (TEST-003) |
| AC-009 | `settle` (mode `prepare` never reads a baseline) | `test_no_other_checkouts_baseline_is_read_or_copied` (open-call spy plus content equality); the existing `PrepareTests.test_no_baseline_is_inherited` |
| AC-010 | `_check_committed` | `LocalIneligibleTests.test_uncommitted_pin_bump`, `test_uncommitted_constitution`, `test_deleted_constitution_is_a_change` |
| AC-011 | `_default_branch` (digests, then `_observe_in`) | `test_committed_widened_permissions` (network asserted, skipped with the exact reason) |
| AC-012 | `_check_installation`, `_check_parents` | `test_extra_file_under_specify`, `test_edited_installed_file`, `test_a_venv_is_not_written_by_setup`, `test_a_removed_record_file`, `test_a_linked_installed_file`, `test_a_missing_installation_record`, `test_a_standard_inside_the_checkout` |
| AC-013 | `_check_pointer` | `WorktreePointerTests` (forged repository in the checkout, in an agent temp root, missing and wrong back-link, symlinked `.git`, malformed pointers, genuine pointer eligible, primary `.git` directory not checked); the `admin == common/worktrees/<name>` clause is not exercised (TEST-005) |
| AC-014 | `_observe_in`, `_failure`, `_run` | `ObservationTests` (real unreachable path, refused credentials by interception, hung `ls-remote`, hung `fetch`, no default branch, missing and malformed pin, matching operator baseline records with no network command, `_run` bound and stdin closed) |
| AC-015 | `throwaway_environment`, `_observe_in` (`GIT_DIR`, `--get-url`) | `test_local_refs_remotes_and_rewrites_are_ignored` (origin remote, fetched remote ref, `insteadOf`, `refs/remotes/origin/HEAD` all pointed at a repository carrying the widened file; argv log contains only the pinned URL) plus `test_the_url_rule` for the real `repository_url`; `test_only_the_documented_commands_run` |
| AC-016 | `launcher.reviewed_repositories`, `reviewed_configurations`, `add_reviewed`; `_default_branch` | `ReviewedRepositoryTests` (repointed repository with a matching stand-in, never-trusted machine, case-insensitive match, malformed record reads empty) and `EveryRefusalTests` case `unreviewed` |
| AC-017 | `Verdict.lines`, `settle` | `EveryRefusalTests` (six ineligible fixtures through `Setup.main`: exit 0, success line, reason, `ballast trust`, previous baseline and provenance bytes unchanged; unobservable branch; failed installation records nothing) |
| AC-018 | `_precheck`, `tools/setup` marker check | `test_in_progress_marker`, `test_a_marker_makes_setup_refuse`, `PrepareTrustTests.test_a_marker_makes_preparation_refuse` |
| AC-019 | `_precheck` | `test_tamper_marker`, `test_tamper_marker_with_a_matching_baseline` (DEC-0001). The in-progress marker with a matching baseline is not tested (TEST-011) |
| AC-020 | `_saved_runs`, `_unfinished_runs` | `test_saved_run_state_in_the_checkout` (each run-state directory), `test_a_linked_run_state_directory`, `test_unfinished_operator_runs` (active, stopped, unknown, garbage, list, unreadable), `test_finished_and_empty_operator_runs_are_eligible`, `test_an_empty_run_state_directory_is_not_run_state` |
| AC-021 | `_precheck`, `tools/setup` | `test_a_marker_makes_setup_refuse` (a step always holds the marker and setup refuses before reaching `settle`, also on a no-op setup because the marker check precedes `current`); a simulated whole step is not run, which the criterion's own wording does not need |
| AC-022 | launcher comparison unchanged | `SetupBaselineLauncherTests.test_a_changed_input_is_refused_exactly_as_after_trust` (exact refusal text for `status`, `run`, `ledger`, `intake`, exit 2) |
| AC-023 | `_status` | See TEST-008: existing tests gained lines, and six existing lines were edited (documented in DEC-0003 except the `tests/test_ballast.py` one). No launcher trust or refusal test was edited. |
| AC-024 | `launcher._provenance` | `SetupBaselineLauncherTests.test_the_refusal_never_depends_on_the_provenance` (five provenance shapes; same refusal), `test_a_forged_setup_provenance_never_trusts_a_checkout`; `RecordBaselineTests.test_source_and_operator_baseline_for_every_provenance` |
| AC-025 to AC-027 | documents | Documentation; `tests/test_governance.py` was not changed and has no ADR-0015 or BL-INV-002 specific assertion, so these rest on documentation review (as the spec states) |

Additions of this pass:

- AC-016 and FR-005, extended by DEC-0008: `ReviewedConfigurationTests` (repointed reviewed repository needs its own review; the exact reviewed configuration is eligible; a name without digests is not; pairs accumulate; decided before any network command; malformed digests read as empty), `TrustProvenanceTests.test_trust_records_the_reviewed_digests_and_says_so_once`.
- AC-015, extended by SEC2-002: `RewrittenUrlTests` (an `insteadOf` rewrite in the operator's global Git configuration is unobservable; an unrelated configuration still observes), and `ObservationTests.test_only_the_documented_commands_run` (the `--get-url` command is local and has no transport).
- AC-003 and FR-014, extended by SEC2-003: `TrustSourceTests.test_the_trust_check_lists_the_reviewed_repositories`, `TrustProvenanceTests.test_reviewed_lists_the_repositories_and_writes_nothing`.
- Real GitHub transport, credentials and the five scenarios of the quickstart: [e2e.md](e2e.md), all steps run passed.

## Functional requirements

FR-001 to FR-004, FR-006 to FR-012 and FR-020: as mapped above and in test.md (FR-020: `SharedRulesTests.test_the_module_imports_only_the_standard_library_and_the_launcher_set`, `test_check_and_doctor_never_import_it`). FR-005: amended by DEC-0008, spec text updated (the record holds the two reviewed digests per repository and no checkout path). FR-013, FR-014: `status --json` `baseline_source` and doctor's trust detail, which now also lists the reviewed repositories. FR-015: the comparison, its refusals and `trusted.json`'s format are unchanged (`SetupBaselineLauncherTests`). FR-016: `Verdict.lines`. FR-017: ADR-0015, ADR-0007 and ADR-0011 notes, roadmap, technical spec. FR-018: see gap G-1. FR-019: README and `templates/policies/spec-kit-workflow.md`, updated for DEC-0008.

## Contradictions, excess and stale assumptions found

- Stale (fixed): spec FR-005, the Reviewed repositories entity, the AC-016 wording, `data-model.md`, `contracts/launcher-and-doctor.md`, `plan.md`'s rationale row, `quickstart.md` (expected message of step 4), the README paragraph, the policy template and ADR-0015 all said the record holds no digests. They now say what DEC-0008 decided. The change was a specification gap, so the spec was corrected explicitly with its decision, not to excuse the code.
- Stale (fixed): `constitution-amendment.md`'s compatibility sentence now names the changed-default-branch case.
- Excess: none. `launcher.py reviewed --json` and doctor's list are the display SEC2-003 asked for and write nothing; an older launcher refuses the command and doctor shows nothing.
- Architecture: ADR-0015 stays `proposed` until the PR merges; its residual risks now state the digest binding, the trust in the operator's Git environment and the sandbox assumption of the pointer check. No other accepted decision changed, so no new ADR.

## Gaps

- G-1 (not a code gap, an operator action at merge): AC-026 and FR-018 require BL-INV-002 in `.specify/memory/constitution.md` to carry the amendment. The constitution is a protected input an agent never edits (as for #27), so the amendment text in `constitution-amendment.md` is the evidence and the operator applies it when merging. Until then the constitution still reads as before; the code and ADR-0015 do not depend on it.
- G-2 (accepted, in decisions.md): DEC-0003 and DEC-0007 relax T035's "no edited lines" for ten setup-output expectations and three whole-object status assertions; DEC-0008 adds four expectations changed from "differs from ... default branch" to "was not reviewed for" (an unreviewed widened configuration is refused before the network) and one trust-output assertion.
- G-3 (accepted residual): SEC2-004 (SHA-1 blob IDs on a blob-less fetch) and SEC2-005 (the reviewed repository's default branch is whatever it holds when observed; now also bound by the reviewed digests) stay as documented in ADR-0015.
- Quickstart step 6e (a repository the operator cannot read, pinned after a first trust) was not run for lack of a second private repository; the same message is exercised live by an https clone without a credential helper and by `test_refused_credentials`.

## Gates

- `uvx ruff check` and `uvx ruff format --check`: pass.
- Full suite after the rebase and the SEC2 fixes: `Ran 1457 tests`, one failure, `StepCloseTests.test_open_write_scope_violation_blocks_until_restored` (exit 130 under load, known flake #94); it passes alone. Nothing was skipped.
- `tests.test_governance` passes after the ADR renumbering to 0015.

- Verdict: CONVERGED
