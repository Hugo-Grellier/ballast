# Spec reconciliation: branch synchronization (#18)

- Reviewer: Claude Fable (same provider as the author; Codex quota exhausted until 2026-10-10, so no cross-provider reconciliation)
- Date: 2026-10-05
- Skill: `.agents/skills/ballast-spec-reconciliation/SKILL.md`
- Scope: `git diff origin/main...HEAD` on `feat/18-branch-sync` (commits `3b2faf5`..`b842993`), read against `spec.md` as amended by `decisions.md`, `plan.md`, `research.md`, `data-model.md`, `contracts/*.md`, `quickstart.md`, `tasks.md`, the six review reports, ADR-0005 and the policy template section "Branch synchronization".
- Authority note: `specs/18-branch-sync/spec.md` still hashes to the approved digest (`sha256:617cd4f5…`), so every change since the intent approval lives in `decisions.md` only. Resolutions from 16:55 onward are agent decisions under the operator's delegation; the operator confirms them, and the spec text below, at merge.
- Read-only review: no code, spec or test was changed; this report is the only file written. Gates run from the worktree with the normal `HOME` (`state_dir` refuses a temp root).

## Gates run

- `uvx ruff check`: passed. `uvx ruff format --check`: all files already formatted.
- `uv run --no-project --isolated --python 3.13 --with pyyaml python -m unittest tests/test_branch_sync.py tests/test_spec_workflow.py tests/test_autonomous_run.py tests/test_autonomy.py tests/test_agent_run_ledger.py tests/test_draft_pr.py tests/test_doctor.py` (Git 2.53.0): Ran 550 tests in 487.7s, OK, no error or failure, none skipped.
- Not run here: the four CI-skipped tests outside this feature's modules; T050/T051 record the full suite (641 tests, OK, none skipped).

## Summary

The implementation matches the spec as amended by `decisions.md` (DEC-0001..0007, the plan-review fixes, the tasks-gate items U1/D1/D2/C1/C2 and the implementation-review fixes). Every acceptance criterion, functional requirement and success criterion maps to code in `tools/spec_workflow/branch_sync.py`, `run.py`, `autonomy.py`, `ledger.py`, `draft_pr.py` or `tools/ballast`, and to at least one deterministic test, except the two manual criteria the pilot (T052) covers. The two review items marked "required before merge" are in the diff: SEC-001..007 (`17ae84f`, `b842993`) and E-01..E-06. No code change is needed before merge.

What is not converged is the spec text itself: `spec.md` is frozen at its approved digest, and thirteen sentences in it now describe the design before the deferred resolutions (I1–I6, T1), the review-fix design changes (pin without `feature`, `-i feature_directory` at `start`) and a few places where the delivered mechanism (ls-remote plus conditional fetch, a replay outside the checkout, push before local update) does not use the spec's words. § Spec text changes lists each as concrete replacement text for the operator to approve at merge. Three low-severity documentation details are listed for the T054 pass.

Skill classification: CONVERGED against the spec as amended by `decisions.md`; the spec file needs the amendments below before the two artifacts say the same thing.

## Criterion-to-evidence map

File references are to `tools/spec_workflow/branch_sync.py` unless named. Tests are in `tests/test_branch_sync.py` unless named. "Match" means the behavior matches the spec as amended by `decisions.md`; a trailing `A-n` names the spec text change in § Spec text changes that the delivered behavior needs.

### Acceptance criteria

| ID | Implementing code | Test evidence | Match |
| --- | --- | --- | --- |
| AC-001 | `rebase_feature` 1394–1418, `replay` 1445–1517, `mutate` 1549–1633; `run.py` `main` 975–982 calls `_sync` before `_launch` | `ResumeOnCurrentBaseTests.test_behind_clean_unpublished_is_synchronized`; `test_spec_workflow.BranchSyncEndToEndTests.test_resume_runs_the_engine_on_the_new_base` | Match (A-1: "rebase" is the replay) |
| AC-002 | `classify` 1323–1324 → `finish("up-to-date")`; `record` 1787–1835 | `test_up_to_date_needs_no_fetch_and_repeats` (two invocations, two `up-to-date` events, snapshot unchanged) | Match |
| AC-003 | `finish` 1756–1778, `record` (event fields), `format_lines` 332–366 | `test_behind_clean_unpublished_is_synchronized` (event and printed line); `test_agent_run_ledger.LedgerTests.test_branch_sync_events_accept_each_outcome` | Match |
| AC-004 | `run.py` 975 `_sync(run_id, feature=_option_feature(options), starting=True)`; `intended_branch` 788–805 pins `branch` and `feature` | `test_start_pins_branch_then_base_after_ls_remote`; `BranchSyncEndToEndTests.test_start_synchronizes_before_the_first_step` | Match (A-10: `-i feature_directory` required) |
| AC-005 | `run.py` `_continue_command` 801–812: new ID drawn, source pin's `branch`/`base`, `source_run`, before `append_human_decision` | `test_autonomous_run.UpstreamSyncRunTests.test_continue_checks_then_pins_the_continuation`, `test_blocked_continue_changes_no_record`, `test_continue_needs_the_source_branch`; `RecoveryTests.test_failure_after_the_push_is_completed_by_any_next_invocation` (continuation rerun) | Match |
| AC-006 | `rebase_feature` 1398–1400, `mutate` 1563–1592 (tracked, ignored-overwrite, untracked-in-the-way), `dirty_block` 1635–1645 | `BlockedCauseTests.test_dirty_checkouts_are_never_touched`, `test_ignored_file_the_base_tracks_is_not_overwritten`; `PublishedBranchTests.test_dirty_tree_is_not_fast_forwarded`; `RecoveryTests.test_completion_blocked_dirty_then_committed` | Match |
| AC-007 | `replay` 1500–1501, `conflict` 1519–1545; the replay runs in the throwaway, so HEAD never moves and nothing is aborted | `test_conflict_changes_nothing` (snapshot unchanged, no rebase in progress), `test_conflicting_commit_after_a_pushed_sync` | Match in effect (A-2: nothing to "abort") |
| AC-008 | `observe` 934–1022 (`ls-remote --symref` against the pinned repository), `fetch` 1032–1053, `fetch_failed` 1055–1061; `unknown-base` for no `[github] repository`, missing base, no default branch | `test_base_that_cannot_be_fetched_is_never_guessed` (pinned `base_commit` not used; default never substituted; no repository); `EnvironmentRefusalTests.test_no_prompt_ever_runs` | Match |
| AC-009 | `in_progress` 862–883 (rebase, merge, cherry-pick, revert, bisect, `index.lock`), `identity` 885–898, `intended_branch` 806–831 (unpinned `resume`/`continue`) | `test_operations_and_branches`, `test_every_operation_in_progress_blocks`, `test_start_during_a_rebase_reports_the_rebase`, `test_unpinned_resume_is_refused`; `RecoveryTests.test_crash_during_read_tree` | Match, exceeds the list (A-12) |
| AC-010 | No per-run state: each invocation re-observes the remote; the only carried state is the branch-keyed write-ahead record (`recover` 1203–1254) | reruns inside `test_base_that_cannot_be_fetched_is_never_guessed`, `test_dirty_checkouts_are_never_touched`, `test_conflict_changes_nothing`, `test_ctrl_c_during_the_replay`; `RecoveryTests.test_pruned_new_head_and_the_record_is_cleared` | Match as amended (A-5) |
| AC-011 | `run.py` `_sync_block` 274–293 (`make_block("upstream-sync", …)` through `_stop`, no decision), `_continue_refusal` 750–770; `autonomy.py` `BLOCK_CATEGORIES`, `RECOVERY["upstream-sync"]`, `recovery_command` → `RESTART_COMMAND` | `UpstreamSyncRunTests.test_blocked_autonomous_start_is_an_upstream_sync_block`, `test_recovery_command_and_resume_refusal` | Match as amended (A-8) |
| AC-012 | `mutate` step 3 1609–1615, `push` 1661–1673 (`--force-with-lease=refs/heads/B:OBSERVED`, observed in the same invocation) | `PublishedBranchTests.test_published_branch_moves_under_a_lease`, `test_published_branch_without_feature_commits` | Match |
| AC-013 | `follow_published` 1365–1373 (`diverged`, both commits named); `push` 1674–1681 (lease rejection → `diverged`) | `test_both_sides_have_commits`, `test_published_branch_moves_during_the_check` | Match (A-13: the lease variant cannot name the actual published commit) |
| AC-014 | `push` 1682–1698 (`retryable`, two recoveries); the push precedes the local update (1609 before 1617), so the local branch has not moved | `test_failed_push_restores_nothing_because_nothing_moved` (rejection and unreachable remote) | Match in effect (A-2: nothing to "restore") |
| AC-015 | `follow_published` 1343–1364 (strictly behind and clean → `mutate(push=False)`; dirty → note; both ahead → `diverged`) | `test_behind_its_published_branch_fast_forwards`, `test_fast_forward_brings_protected_inputs_to_the_recheck`, `test_dirty_tree_is_not_fast_forwarded`, `test_fast_forward_record_never_pushes` (P-01 on `main` and `develop`) | Match (A-11: recorded outcome) |
| AC-016 | `mutate` 1593–1604 (pre-mutation diff over `launcher.BASES` minus `SKIPPED`), `recheck` 1702–1725 (launcher's own comparison), `finish` 1757 | `TrustBoundaryTests.test_protected_input_from_the_base_fails_closed`, `test_crash_after_a_protected_update_is_caught_by_the_launcher` (P-05); `PublishedBranchTests.test_fast_forward_brings_protected_inputs_to_the_recheck`; `StaleEvidenceTests.test_kept_protected_input_sync_keeps_its_stale_record` | Match |
| AC-017 | `run.py` imports `branch_sync` at startup (89) and calls it at the four contract sites only; `observe` 936–951 (`draft_pr._pinned_repository`, `_url`; `origin` supplies the scheme only); `_env` 572–584, `checkout` 619–632, `throwaway` 634–677 | `test_spec_workflow.BranchSyncCallTests.test_called_once_before_the_engine_for_start_and_resume`, `test_publish_never_runs_the_check`, `test_every_block_stops_before_any_agent_and_any_checkpoint`; `TrustBoundaryTests.test_checkout_configuration_never_runs`, `test_nested_repository_configuration_never_runs`, `test_replace_refs_and_grafts_do_not_hide_the_base`; `EnvironmentRefusalTests.test_partial_clones_are_refused`, `test_alternates_are_refused`; `FoundationTests.test_runners_harden_every_command`, `test_checkout_git_is_never_executed` | Match |
| AC-018 | `find_overlap` 1727–1750, `record` 1818–1834 (stale record in operator state), `draft_pr._section`/`_stale_entries`/`_stale_record`/`_code` | `StaleEvidenceTests.test_overlap_marks_plan_and_review_stale`, `test_no_evidence_or_no_overlap_writes_nothing`, `test_completion_from_the_record_keeps_its_stale_record`; `test_draft_pr.StaleEvidenceSectionTests` (five tests, including the SEC-007 marker case) | Match |
| AC-019 | `execute` 743–749 (`draft_pr._Locked(lock, wait=0)` → `busy`); `draft_pr._Locked(path, wait=…)` | `ConcurrencyTests.test_lock_held_by_another_process` (real second process); `test_draft_pr.LockWaitTests` | Match |
| AC-020 | the lock plus two compare-and-swaps: `mutate` 1561–1562 (HEAD still old, else `busy`, U1) and `update_ref` 1647–1659 (P-04) | `test_two_checks_race` (two threads with separate lock descriptors; one `synchronized`, one `busy`, branch equals the single-run result), `test_commit_after_the_replay_is_busy_then_kept`, `RecoveryTests.test_commit_between_the_push_and_the_compare_and_swap` | Match |
| AC-021 | `kind` 1306–1313, `classify` 1327–1340 (`not-feature-branch`); `autonomy.is_feature_branch` | `test_autonomy.FeatureBranchTests` (two tests); `BlockedCauseTests.test_only_feature_branches_are_rewritten`, `test_issue_number_comes_from_the_pin`; `UpstreamSyncRunTests.test_eligibility_uses_the_feature_branch_rule`; `PublishedBranchTests.test_fast_forward_record_never_pushes` | Match |

### Functional requirements

| ID | Implementing code | Test evidence | Match |
| --- | --- | --- | --- |
| FR-001 | `run.py` 527 (Autonomous start, after `write_run` 519), 803 (`continue`), 975–979 (`start`, `resume`); `publish` has no call | `BranchSyncCallTests` (five tests) | Match (A-10) |
| FR-002 | `intended_branch` 786–831 (pin at `start`; pin's `branch`/`feature` at `resume`; source pin at `continue`), `observe` 952–998 (default branch from the same `ls-remote --symref`, pinned only after it, N-06), `read_pin` 413–437 | `test_start_pins_branch_then_base_after_ls_remote`, `test_a_17_pin_gets_its_base`, `test_base_that_cannot_be_fetched_is_never_guessed`, `test_unpinned_resume_is_refused`, `test_issue_number_comes_from_the_pin`; `BranchSyncEndToEndTests.test_resume_takes_the_issue_number_from_the_pin` | Match (A-9) |
| FR-003 | `observe`: `ls-remote` on every invocation, the base commit taken from that advertisement; `fetch` only when the observed commit is missing locally (1009–1011); the pin's `base_commit` never stands in | `test_up_to_date_needs_no_fetch_and_repeats`, `test_base_that_cannot_be_fetched_is_never_guessed`, `test_recorded_base_missing_locally_blocks` | Match in intent (A-3: "fetch on every invocation" is "observe on every invocation") |
| FR-004 | `is_ancestor` 1065–1070 under `GIT_NO_REPLACE_OBJECTS`, `GIT_GRAFT_FILE`, `core.commitGraph=false`; `classify` 1323 | `test_empty_and_spec_only_base_commits_count_as_behind`, `test_replace_refs_and_grafts_do_not_hide_the_base` | Match |
| FR-005 | `classify`, `rebase_feature`, `fast_forward_base` 1375–1392 (DEC-0003), `replay` with `--attr-source=<fetched base>` | `ReplayFidelityTests` (six tests), `test_only_feature_branches_are_rewritten`, `test_run_on_the_base_branch_only_fast_forwards`, `test_rewritten_base`, `test_no_commits_beyond_the_base_fast_forwards` | Match (A-2) |
| FR-006 | `mutate` order (checks, record, push, `read-tree`, CAS), `dirty_block`, `update_ref` P-04 guard; nothing calls `stash`, `reset`, `checkout`, `restore` | `Scratch.assert_unchanged` in every blocked-outcome test; `test_operator_gc_never_prunes_the_checkout`; `RecoveryTests.test_crash_during_read_tree`, `test_kill_between_read_tree_and_update_ref` | Match as amended (A-4) |
| FR-007 | `mutate` 1609–1615 (lease on the commit observed in the same invocation, before the local update), `push`, `recover` row 2 (`records_push`, P-01) | `PublishedBranchTests` (lease, moved during the check, failed push); `RecoveryTests.test_local_moved_but_push_missing`, `test_failure_after_the_push_is_completed_by_any_next_invocation` | Match as amended (A-2, DEC-0005) |
| FR-008 | `recheck` 1702–1725 runs in `finish` after every path that moves HEAD (`fast_forward_base`, `rebase_feature`, `follow_published`, recovery rows 2–5); row 1 (moved by a crashed invocation) is caught by `launcher._refusal` (P-05) | `test_protected_input_from_the_base_fails_closed`, `test_fast_forward_brings_protected_inputs_to_the_recheck`, `test_crash_after_a_protected_update_is_caught_by_the_launcher` | Match |
| FR-009 | `ledger.py` `SYNC_OUTCOMES`, `SYNC_CAUSES` (13), `FIELDS["branch_sync"]`, `_validate_branch_sync`, `RUNNER_ONLY`, `report`; `record` 1787–1835; `synchronize` 1883–1906 (failed record → `internal-error` "not recorded") | `LedgerTests` (five `branch_sync` tests); `FoundationTests.test_failed_record_blocks_an_otherwise_good_outcome`, `test_never_raises`, `test_old_git_is_refused`; `test_ctrl_c_during_the_replay` | Match as amended (A-7, A-13) |
| FR-010 | `format_lines` 338–342; `run.py` `_sync` 243–265, `_sync_status` 267–272 (exit 1, or 130 when interrupted) | `BranchSyncCallTests.test_every_block_stops_before_any_agent_and_any_checkpoint` (13 causes, stderr, exit, no `specify`, no checkpoint); `SyncCase.assertBlocked` in every blocked test (one `Recovery:` line) | Match (A-13) |
| FR-011 | `run.py` `_sync_block` records only a block; `_continue_command` runs the check before `append_human_decision` | `test_blocked_autonomous_start_is_an_upstream_sync_block` (no decision record), `test_blocked_continue_changes_no_record` | Match |
| FR-012 | module boundary (docstring 1–25); `throwaway` allow-list raising `RuntimeError` (644–647); `GIT_HARDENING`, `NO_RECURSION`, `filter_flags`, prompt variables; committer from `git var` in the throwaway | `test_standard_library_and_sibling_imports_only`, `test_runners_harden_every_command`, `test_throwaway_allow_list_holds_without_assert`, `test_checkout_configuration_never_runs`, `test_nested_repository_configuration_never_runs`, `test_no_prompt_ever_runs`, `test_operator_gc_never_prunes_the_checkout`, `test_no_committer_identity_changes_nothing` | Match |
| FR-013 | `_text` (= `draft_pr.printable`), `_recovery` (`shlex.quote`, placeholder for names starting with `-`), `_paths`; `COMMIT`/`REF` validation of every name read from Git | `test_names_are_quoted_and_escaped`, `test_untrusted_names_are_printed_as_data` | Match |
| FR-014 | `templates/policies/spec-kit-workflow.md` § Branch synchronization; `README.md`; `run.py` docstring; `tools/ballast` `doctor` floor | `DocumentationTests` (three tests), `BranchSyncCallTests.test_help_describes_the_check`, `test_doctor.MachineTests.test_git_older_than_the_sync_floor` | Match (G-02, G-04 are low) |
| FR-015 | as AC-018 | as AC-018 | Match |
| FR-016 | `execute` 743–762: lock keyed by `sha256(branch)[:16]` under `state_dir`, taken before `shape()` and held through `classify()` (observation, fetch, replay, push, local update, recheck) | `test_lock_held_by_another_process`, `test_two_checks_race`; `LockWaitTests.test_wait_zero_reports_busy_at_once`, `test_default_wait_and_broken_lock_are_unchanged` | Match |

### Success criteria

| ID | Evidence | Status |
| --- | --- | --- |
| SC-001 | `BranchSyncCallTests.test_every_block_stops_before_any_agent_and_any_checkpoint` (every cause), `BranchSyncEndToEndTests.test_blocked_resume_starts_no_engine`, `test_blocked_autonomous_start_is_an_upstream_sync_block`; every listed case (up-to-date, behind-clean, dirty, conflict, fetch failure, unknown base, in progress, wrong branch, published, diverged, failed push, protected-input, concurrent, repeated) has a `branch_sync` test | Met |
| SC-002 | `assert_unchanged` in every blocked test except the named exceptions (DEC-0002, DEC-0005; and `busy` after an outside move, where `test_commit_between_the_push_and_the_compare_and_swap` asserts the tree is clean against the mover's HEAD) | Met as amended (A-4) |
| SC-003 | one recovery per cause and detail (`RECOVERY` 129–187, `DocumentationTests.test_every_cause_and_recovery_is_documented`); "without reading Ballast source" is pilot step 5 | Deterministic part met; manual part pending T052 (expected) |
| SC-004 | pilot steps 1–5 in `quickstart.md` | Pending T052 (expected) |
| SC-005 | `test_up_to_date_needs_no_fetch_and_repeats`: exactly one `ls-remote`, no `fetch`, snapshot unchanged | Met (A-3: "one fetch" is "one `ls-remote`") |

## Gaps

Each gap is labelled; "diagnosis" follows the skill (implementation wrong, specification stale, new knowledge).

| ID | Label | Diagnosis | Where | What | Action |
| --- | --- | --- | --- | --- | --- |
| G-01 | spec ambiguity | specification stale | `spec.md` (frozen at the approved digest) | Thirteen passages describe the pre-resolution design or use words the delivered mechanism does not (see § Spec text changes) | Operator approves A-1..A-13 at merge; no code change |
| G-02 | spec ambiguity, missing test (low) | new knowledge | `resolve_git` 772–773; `contracts/branch-sync.md` § Causes; policy table | `git-unavailable` has a third detail, "git version unknown" (a `git` whose `version` output does not parse), that the contract and policy rows do not list and no test exercises; the recovery is the "put a system git 2.41 or later on PATH" one, which fits | Add the detail to the contract row (and, if wanted, one `_git_version` seam test); not blocking |
| G-03 | spec ambiguity (low) | specification stale | `data-model.md:143` § Stale evidence record | Says "each path as a code span with backticks removed"; since SEC-007 (`draft_pr._code`) `<!--` is also broken up so no path can spell the section marker; the round-2 security review asked for this sentence to follow | One-sentence update in the T054 documentation pass |
| G-04 | spec ambiguity (low) | specification stale | `contracts/branch-sync.md` § Printed output | The `up-to-date` line gains "; fast-forwarded to the published branch" after an AC-015 fast-forward (`format_lines` 348–349); the contract lists the dirty-skip note but not this suffix; the policy describes the fast-forward but not the line | Add the example line to the contract; not blocking |
| G-05 | missing test (manual, expected) | — | T052 | SC-003 step 5 and SC-004 need a real GitHub remote and real agents | Operator pilot, transcript in the PR |
| G-06 | architecture (expected) | — | ADR-0005, T054 | ADR-0005 is `Proposed`; the R2 approval on file is the agent's under delegation | Operator accepts ADR-0005 and the merge |

Nothing is labelled spec violation, implementation bug or proposed product change: no behavior contradicts the spec as amended, and the exceeding behaviors (revert, bisect and `index.lock` as `in-progress`; `fast_forwarded` on `up-to-date`; the third `git-unavailable` detail) are additive and fail closed.

Informational, no action: AC-020's race test (`test_two_checks_race`) runs two threads with separate lock descriptors rather than two processes, as T025 records; the `flock` semantics are the same, and AC-019 uses a real second process. `run.py` `_run_feature` still reads `inputs.json` for the `feature` argument at `resume`, but `intended_branch` replaces it with the pin's `feature` before any decision (SEC-002); the agent-writable value only attributes a ledger event of a check blocked before the pin is read.

## Spec text changes for the operator to approve at merge

Consolidates I1–I6 and T1 from `decisions.md` (tasks gate), the review-fix design changes and the new items G-01 found. Each is replacement text for `spec.md`. Approving them re-records the intent approval digest; `decisions.md` is already authoritative for the behavior.

**A-1 (T1) — Assumption A-1.** Replace with:

> **A-1**: Synchronization rebases, as the roadmap item specifies, not a merge of the base into the branch. "Rebase" means the replay ADR-0005 describes: the feature's commits are replayed onto the fetched base in a throwaway repository with `git merge-tree`, and the branch then moves to the result with one compare-and-swap. `git rebase` never runs in the checkout, so nothing is ever left in progress to abort; replayed commits are unsigned, merge attributes come from the fetched base, and no `rebase.*` configuration applies. This keeps the branch linear for the #17 Draft PR and for merge by rebase or merge commit.

**A-2 (new; with T1) — AC-007, FR-005 last sentence, AC-014, FR-007.** Replace:

> **AC-007**: **Given** a branch whose replay onto the base conflicts, **When** an invocation begins, **Then** the branch HEAD, index and working tree are left as they were (the replay runs outside the checkout, so there is nothing to abort), no agent starts, and the report names the cause `conflict`, the conflicting commit and the conflicting paths.

> FR-005, last sentence: A replay that conflicts MUST leave the branch at its previous HEAD; no rebase is ever left in progress.

> **AC-014**: **Given** the push of the rebased branch fails for any reason, **When** the failure is detected, **Then** the local branch is still at its previous HEAD (the push precedes the local update), no agent starts, and the report says whether a retry alone can succeed.

> **FR-007**: For a published feature branch, the rebased HEAD MUST be pushed before the local branch moves, and only on the condition that the published branch still points at the commit observed in the same invocation. When that condition fails, or the push fails, the local branch MUST be left at its previous HEAD and the run blocked. A failure after a successful push leaves the published branch at the rebased commit; the next invocation on the branch, whatever its run ID, completes the synchronization from the write-ahead record (DEC-0005).

**A-3 (new) — FR-003 and SC-005.** Replace:

> **FR-003**: The check MUST observe the current base commit from the pinned repository on every invocation (`ls-remote`), and fetch its objects when they are missing locally. When the observation or the fetch fails, or the base cannot be resolved, the result MUST be `BLOCKED_UPSTREAM_SYNC` with no fallback to a previously observed base; the pin's `base_commit` is never used as the current base.

> **SC-005**: When the base has not moved, the check adds no visible delay beyond one `ls-remote` (no fetch runs when the observed commits are already local) and leaves the run otherwise unchanged.

**A-4 (I2, I3) — FR-006 and SC-002.** Replace:

> **FR-006**: The launcher MUST NOT discard, stash, reset or overwrite uncommitted changes, local-only commits or published commits. Every blocked outcome MUST leave the branch HEAD, index and working tree as they were before the invocation, with the exceptions SC-002 names.

> **SC-002**: In every blocked case the branch HEAD, index, working tree and published branch are byte-for-byte the same before and after the invocation, except: `protected-input`, which keeps the completed synchronization (AC-016, DEC-0002); a block after a successful push, which leaves the published branch at the rebased commit for the next invocation to complete (DEC-0005); and `busy` after another actor moved the branch during the check, where HEAD is that actor's commit and the index and working tree match it, with only the synchronization's own output dropped.

**A-5 (I4) — AC-010.** Replace:

> **AC-010**: **Given** any blocked synchronization, **When** the operator removes the cause and invokes the run again, **Then** the check runs again from the beginning. The only state carried over is the write-ahead record of a synchronization that was already pushed or half-applied, which the next invocation on the branch completes or clears (DEC-0005).

**A-6 (I1) — Edge case "Interrupted synchronization".** Replace:

> **Interrupted synchronization** (Ctrl-C or a crash): before the push and the local update, the next invocation finds nothing to complete and clears the write-ahead record. After a successful push, or between the steps of the local update, the next invocation on the branch, whatever its run ID, completes the synchronization from the write-ahead record and says so (DEC-0005). A Git operation left in progress blocks first with `in-progress`, and an update interrupted while writing the working tree blocks with `dirty` and the one command `git restore --source=NEW_HEAD --staged --worktree .`; the launcher never resumes a half-done Git operation on its own.

**A-7 (I5) — FR-009, the `git-unavailable` item.** Replace `git-unavailable (no trusted git 2.41 or later)` with:

> `git-unavailable` (no trusted `git` 2.41 or later, a shallow checkout, a partial clone, or a checkout with `objects/info/alternates`; DEC-0001, DEC-0007)

**A-8 (I6) — AC-011.** Replace:

> **AC-011**: **Given** an Autonomous run whose synchronization is blocked, **When** the block is reported, **Then** it is recorded as a block in its own category, `upstream-sync`, alongside the existing block categories, and recovered by removing the cause and starting the run again (`ballast run start --mode autonomous ...`). `ballast run continue` refuses it: no agent step ran, so there is nothing to continue.

**A-9 (review fix SEC-002, design change 1) — Edge case "A run with no branch pin" and FR-002.** Replace the edge case with:

> **A run whose pin lacks the branch or the feature directory** (started before #17, or before #18 pinned the feature): `resume` and `continue` block with `wrong-branch` and the recovery to start a new run. The check never pins a branch or a feature after an agent step could have changed HEAD or the run's inputs (DEC-0006, SEC-002).

Append to FR-002:

> The branch, the base and the Issue number the rewrite rule uses come from the run's pin, written by `ballast run start` from the operator's command, or from that command itself at `start`; never from agent-writable run inputs.

**A-10 (review fix E-01, design change 2) — FR-001.** Append:

> A human-gated `ballast run start` MUST name exactly one valid `-i feature_directory=specs/<issue>-<slug>`; otherwise it is refused (exit 2) before the check, so the check always knows the Issue number it pins.

**A-11 (new) — AC-015.** Replace:

> **AC-015**: **Given** the local branch is strictly behind its own published branch (no local-only commits) and clean, **When** an invocation begins, **Then** it is fast-forwarded to the published branch before the base check; nothing is pushed, the ledger event carries `fast_forwarded`, and the outcome is `up-to-date` when the base is then contained or `synchronized` when a rebase follows. With uncommitted changes the fast-forward is skipped with a printed note when the base is contained, and the run blocks with `dirty` otherwise. [Assumption A-4]

**A-12 (new) — AC-009.** Replace the opening with:

> **Given** a checkout with an operation already in progress (rebase, merge, cherry-pick, revert or bisect) or a stale `index.lock`, a detached HEAD, or a branch other than the one the run started on, ...

**A-13 (new) — FR-009 and FR-010 details.** In FR-009 replace "It MUST record the base reference, the previous and current base commit, and the previous and resulting HEAD." with:

> It MUST record the base reference, the previous and current base commit, and the previous and resulting HEAD, each when the check got far enough to know it; a blocked outcome records what it knew.

In FR-010 replace "(conflicting paths, changed protected inputs, the observed and actual published commits)" with:

> (the conflicting commit and paths, the changed protected inputs, the local and published commits when both are known)

Housekeeping, optional: `spec.md` line 7 `**Status**: Draft` can become `Implemented, pending merge` in the same amendment.

Not spec text: the write-ahead record's two new fields (`old_base`, `new_base`; design change 3) are in `data-model.md` and `contracts/branch-sync.md` already, and no released version wrote records.

## Does anything require a code change before merge?

No. The items the reviews marked "required before merge" are in the diff and tested: SEC-001..006 and E-01..E-06 in `17ae84f`, SEC-007 in `b842993` (`draft_pr._code` breaks up `<!--`; `StaleEvidenceSectionTests.test_paths_are_code_spans_and_bounded` asserts one end marker). G-02..G-04 are documentation lines for the T054 pass. What remains is operator work: T052 (pilot transcript in the PR), T054 (resolve this report's amendments in `decisions.md`, Spec Kit converge, approve ADR-0005 and set it to `Accepted`, confirm the three design changes), and the human R2 merge approval.

- Verdict: RECONCILED WITH SPEC AMENDMENTS
