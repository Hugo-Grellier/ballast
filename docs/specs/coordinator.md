# Coordinator

Covers: tools/coordinate.py
Covers: tools/progress.py

`tools/coordinate.py` is the coordinator's command line over one bounded
queue: create, select, control, close, record progress, publish, run
coordinator executions, recover, settle, release, retarget, retire and
observe. `tools/progress.py` validates the public progress declarations it
records. Admission rules are in [queue admission](queue-admission.md).

### Requirement: Project checkout only
The command SHALL refuse to run from inside an issue checkout or the shared
state directory, before any Git call, and SHALL print only a fixed reason or
an exception type on refusal.

#### Scenario: Inside an issue checkout
- WHEN `--cwd` or the process directory is an issue checkout
- THEN the command refuses: run queue commands from the project checkout
- Test: tests/test_queue_admission.py::QueueTests::test_recovery_and_cli_refuse_untrusted_git_inputs
- Test: tests/test_queue_admission.py::QueueTests::test_helpers_refuse_to_start_inside_an_issue_checkout

#### Scenario: Diagnostics
- WHEN an operation is refused
- THEN the command exits 1 with the fixed reason, or only the exception type for any other error
- Test: tests/test_standalone_execution.py::ExecutionTests::test_coordinate_main_reports_fixed_reasons_only

#### Scenario: Review fallback options
- WHEN `create` gets `--review-fallback` without `--review-fallback-approval`, the reverse, or a fallback not of the form `PROVIDER:MODEL`
- THEN creation refuses
- Test: tests/test_coordinator_execution.py::CoordinatorExecutionTests::test_fallback_refused_while_paused_and_policy_is_validated

### Requirement: Selection
Selection SHALL report, for each queue issue, why it is blocked, which issues
are eligible within the remaining issue and backlog room, which wait for
capacity and which are claimed; a prerequisite counts only when it is a
same-repository issue closed by a merged PR, and a lookup failure SHALL block
only the issue it concerns.

#### Scenario: Blockers and capacity
- WHEN issues form a dependency cycle, name a cross-repository prerequisite, or depend on an issue closed without a merged change
- THEN each is blocked with its reason, and eligible work is bounded by the remaining room
- Test: tests/test_queue_admission.py::QueueTests::test_selection_reports_blockers_and_bounds_eligible_work

#### Scenario: Unreadable or oversized input
- WHEN a prerequisite cannot be read, the native list has more pages, or a `Blocked by` line is too long
- THEN only that issue is blocked as unknown or not evaluable
- Test: tests/test_queue_admission.py::QueueTests::test_selection_isolates_unreadable_and_written_prerequisites
- Test: tests/test_queue_admission.py::QueueTests::test_unreadable_native_prerequisite_is_looked_up_alone
- Test: tests/test_queue_admission.py::QueueTests::test_pull_request_numbered_prerequisite_stays_batched
- Test: tests/test_queue_admission.py::QueueTests::test_malformed_node_isolates_only_that_issue

#### Scenario: Halted queue
- WHEN the queue is paused, cancelled or expired
- THEN nothing is eligible and the report names why, including `close --reason` for a finished queue
- Test: tests/test_queue_admission.py::QueueTests::test_selection_isolates_unreadable_and_written_prerequisites
- Test: tests/test_queue_admission.py::QueueTests::test_cancelled_queue_selection_names_close
- Test: tests/test_queue_admission.py::QueueTests::test_another_coordinator_closes_only_a_finished_settled_queue

#### Scenario: Batched reads
- WHEN selection reads queue issues and prerequisites
- THEN it uses one aliased query per batch of up to 100, and none for native prerequisites that carry their closing PRs
- Test: tests/test_queue_admission.py::QueueTests::test_selection_batches_queue_and_prerequisite_reads
- Test: tests/test_queue_admission.py::QueueTests::test_native_prerequisites_need_no_second_call
- Test: tests/test_queue_admission.py::QueueTests::test_many_prerequisites_are_chunked

#### Scenario: Planned path overlap
- WHEN `--planned` maps queue issues to paths or `path::function`
- THEN each pair is advised `parallel`, `serialize` or `stack`, and a malformed plan is refused
- Test: tests/test_queue_admission.py::QueueTests::test_overlap_report_suggests_parallel_serialize_or_stack

### Requirement: Publication
Publish SHALL, for the queue's coordinator only, require a completed
independent review of this attempt on the pushed, unchanged head, then create
one draft PR or reuse the single matching one, and record it on the claim; any
malformed worker record, a stale, closed, foreign or duplicate PR SHALL block.

#### Scenario: Review required
- WHEN no worker review of this attempt completed on this exact head, or the review is from a coordinator execution
- THEN publish refuses before any GitHub write
- Test: tests/test_queue_admission.py::QueueTests::test_publish_requires_a_completed_review_of_this_head_and_attempt
- Test: tests/test_coordinator_execution.py::CoordinatorExecutionTests::test_publish_never_counts_a_coordinator_review

#### Scenario: Unpushed head
- WHEN the branch on GitHub is not the reviewed head
- THEN publish refuses: push the reviewed head
- Test: tests/test_queue_admission.py::QueueTests::test_stale_or_duplicate_prs_block_publication

#### Scenario: Lost creation response
- WHEN the PR creation response is lost
- THEN a re-query finds the one created PR, and a later publish reuses it
- Test: tests/test_queue_admission.py::QueueTests::test_lost_publication_response_recovers_one_pr

#### Scenario: Conflicting PRs
- WHEN several PRs use the branch, the PR is closed unmerged, or it targets another base or source repository
- THEN publish refuses
- Test: tests/test_queue_admission.py::QueueTests::test_stale_or_duplicate_prs_block_publication
- Test: tests/test_queue_admission.py::QueueTests::test_closed_or_forkless_prs_block_cleanly

#### Scenario: Worker-written gitfile
- WHEN the checkout gitfile points at another repository
- THEN publish reads the head through the claim's pinned Git directory
- Test: tests/test_queue_admission.py::QueueTests::test_publish_ignores_worker_written_gitfile

### Requirement: Stacked publication and retargeting
A stacked child SHALL be published against its parent's branch with the
stack's merge order in the body, SHALL be refused when its parent moved, was
rewritten, merged or is missing locally, and retarget SHALL rebase it and its
descendants onto the parent's base only once GitHub reports the parent
merged, leaving no review valid for the new head.

#### Scenario: Merge order
- WHEN a stack member is published or republished
- THEN its PR targets the parent branch and its body lists the merge order, the coordinator's body file unchanged
- Test: tests/test_queue_admission.py::QueueTests::test_stacked_publication_targets_parent_and_writes_order

#### Scenario: Parent moved or merged
- WHEN the parent branch advanced, or the parent PR merged
- THEN publish asks to rebase the child, or to retarget it first
- Test: tests/test_queue_admission.py::QueueTests::test_stacked_publication_targets_parent_and_writes_order
- Test: tests/test_queue_admission.py::QueueTests::test_fetched_parent_commit_missing_locally_asks_for_a_rebase

#### Scenario: Rewritten parent
- WHEN the parent's pushed commit was rewritten
- THEN publish and retarget refuse, advising to stop the child, and keep its claim valid
- Test: tests/test_queue_admission.py::QueueTests::test_rewritten_parent_refuses_the_child_and_keeps_its_claim

#### Scenario: Parent head not fetched
- WHEN the parent's head or merged head is not in the local object store
- THEN publish and retarget ask to fetch it first
- Test: tests/test_queue_admission.py::QueueTests::test_missing_parent_object_asks_for_a_fetch

#### Scenario: Retarget after merge
- WHEN GitHub reports the parent merged
- THEN the child and its descendants are rebased onto the new base, the PR base is moved, and publish needs a new review
- Test: tests/test_queue_admission.py::QueueTests::test_retarget_after_github_merge_rebases_and_invalidates_review
- Test: tests/test_queue_admission.py::QueueTests::test_three_pr_stack_stays_valid_through_squash_merges
- Test: tests/test_queue_admission.py::QueueTests::test_restack_drops_commits_the_parent_rewrote

#### Scenario: Retarget refusals
- WHEN the parent is not merged, a worker or execution holds a stack member, the rebase conflicts, the parent claim is missing or foreign, or the claim is not stacked
- THEN retarget refuses and every checkout and claim is unchanged
- Test: tests/test_queue_admission.py::QueueTests::test_retarget_after_github_merge_rebases_and_invalidates_review
- Test: tests/test_queue_admission.py::QueueTests::test_descendant_conflict_restores_every_checkout
- Test: tests/test_queue_admission.py::QueueTests::test_retarget_refuses_missing_foreign_and_conflicting_parents

#### Scenario: Failed PR base edit
- WHEN the PR base edit fails or its response is lost
- THEN the claim stays `retarget_pending` and a retry only reconciles the PR base
- Test: tests/test_queue_admission.py::QueueTests::test_retarget_retries_a_failed_pr_base_edit
- Test: tests/test_queue_admission.py::QueueTests::test_retarget_reconciles_a_lost_pr_base_edit

### Requirement: Coordinator executions
A coordinator execution SHALL record work the coordinator itself does with a
role and an explicit provider, model and effort, take neither worker capacity
nor the writer lock but exclude workers and other executions, never count as
a verified route, refuse an implementation of an R1 or R2 leaf without an
approved spec delta ([spec approval](spec-approval.md)), and finish once: a completed review with a verdict and a
round 1 to 3 on an unchanged clean head, anything else without them.

#### Scenario: Lifecycle
- WHEN an implementation execution starts and finishes
- THEN it is recorded `running` then `completed`, unverified, with no worker capacity or attempt used, and the issue is free afterwards
- Test: tests/test_coordinator_execution.py::CoordinatorExecutionTests::test_implementation_lifecycle_takes_no_worker_capacity_or_lock

#### Scenario: Unapproved implementation
- WHEN an implementation execution starts on an R2 leaf without an approved spec delta
- THEN it refuses before recording anything, while a review execution is not gated
- Test: tests/test_coordinator_execution.py::CoordinatorExecutionTests::test_unapproved_r2_implementation_is_refused_before_recording

#### Scenario: Review verdict
- WHEN a review execution finishes
- THEN a dirty start, a missing or invalid verdict or round, a verdict on a non-review, or a moved head is refused
- Test: tests/test_coordinator_execution.py::CoordinatorExecutionTests::test_review_records_verdict_round_and_an_unchanged_clean_head

#### Scenario: Refused records
- WHEN the role or route is malformed, the caller is not the coordinator, a worker holds the issue, or the ID names a worker record or is malformed
- THEN start or finish refuses
- Test: tests/test_coordinator_execution.py::CoordinatorExecutionTests::test_malformed_foreign_and_worker_records_are_refused

#### Scenario: Never verified
- WHEN a record claims a verified route or receipt source
- THEN status and the dashboard still project it unverified, and no option sets it
- Test: tests/test_coordinator_execution.py::CoordinatorExecutionTests::test_route_cannot_be_marked_verified
- Test: tests/test_coordinator_execution.py::CoordinatorExecutionTests::test_status_and_dashboard_project_executor_and_marker

#### Scenario: Separate options
- WHEN `execution start` lacks `--executor coordinator` or carries finish options, or `finish` carries start options
- THEN the command refuses
- Test: tests/test_coordinator_execution.py::CoordinatorExecutionTests::test_cli_names_the_executor_and_separates_actions

#### Scenario: Interrupted finish
- WHEN a finish was interrupted after a partial write
- THEN a retry with the same outcome completes it and any other outcome is refused
- Test: tests/test_coordinator_execution.py::CoordinatorExecutionTests::test_interrupted_finish_resumes_with_the_same_outcome

### Requirement: Quota fallback review
During a recorded quota pause, and only under the queue's review fallback
policy, a coordinator review execution on exactly the fallback route SHALL be
allowed and SHALL count for publish when it completed on this attempt's
head and that route did not implement the attempt; the PR body SHALL then
state the unverified route and the operator's approval.

#### Scenario: Fallback publishes
- WHEN the fallback review approves the pushed head during the quota pause
- THEN publish creates the PR with a review route section, the quota pause stays and workers are still refused
- Test: tests/test_coordinator_execution.py::CoordinatorExecutionTests::test_quota_fallback_review_publishes_under_the_operator_policy

#### Scenario: Fallback refused
- WHEN there is no policy, no recorded quota pause, the queue is paused, the operator resumed before the review, the route implemented the attempt, or the review is of another attempt or head
- THEN the review does not count and publish refuses
- Test: tests/test_coordinator_execution.py::CoordinatorExecutionTests::test_fallback_refused_without_policy
- Test: tests/test_coordinator_execution.py::CoordinatorExecutionTests::test_fallback_refused_without_a_quota_outcome
- Test: tests/test_coordinator_execution.py::CoordinatorExecutionTests::test_fallback_refused_while_paused_and_policy_is_validated
- Test: tests/test_coordinator_execution.py::CoordinatorExecutionTests::test_normal_review_after_an_operator_resume_is_refused
- Test: tests/test_coordinator_execution.py::CoordinatorExecutionTests::test_fallback_refused_when_its_route_implemented_the_attempt
- Test: tests/test_coordinator_execution.py::CoordinatorExecutionTests::test_fallback_refused_from_another_attempt_on_the_same_head
- Test: tests/test_coordinator_execution.py::CoordinatorExecutionTests::test_fallback_refused_for_a_review_of_another_head

### Requirement: Recovery, settlement and retirement
Recovery SHALL adopt an existing attempt only after checking its recorded
identity and recreating a checkout an interrupted preparation never made;
settling `merged` SHALL require GitHub to report the PR merged; retiring a
stopped claim SHALL require its PR to be closed.

#### Scenario: Interrupted preparation
- WHEN a claim stayed `preparing` without a checkout
- THEN recover creates it at the recorded branch and base and marks the claim ready and active
- Test: tests/test_queue_admission.py::QueueTests::test_preparation_killed_before_checkout_is_recreated
- Test: tests/test_queue_admission.py::QueueTests::test_interrupted_preparation_and_legacy_claim_are_recovered

#### Scenario: Recovery refusals
- WHEN the recorded branch, base or checkout path is not the shape preparation writes, or a worker lock is held
- THEN recover refuses
- Test: tests/test_queue_admission.py::QueueTests::test_recovery_and_cli_refuse_untrusted_git_inputs
- Test: tests/test_queue_admission.py::QueueTests::test_interrupted_preparation_and_legacy_claim_are_recovered

#### Scenario: Merge confirmation
- WHEN `settle merged` runs before GitHub reports the PR merged
- THEN it refuses and the backlog slot stays used
- Test: tests/test_queue_admission.py::QueueTests::test_backlog_holds_until_github_confirms_merge

#### Scenario: Stopped claim with an open PR
- WHEN a stopped claim's PR is still open
- THEN retire refuses until it is closed
- Test: tests/test_queue_admission.py::QueueTests::test_retire_moves_a_settled_claim_aside_and_refuses_otherwise

### Requirement: Observation
Status SHALL derive capacity, per-issue phases, waiting, rework, reopenings
and throughput from the durable records only, report a missing measurement
as unavailable, keep retired attempts listed and counted, and count only the
current queue's claims toward throughput.

#### Scenario: Derived history
- WHEN workers ran on an issue
- THEN status reports rework, tokens or `unavailable`, and the phase set
- Test: tests/test_queue_admission.py::QueueTests::test_observation_derives_history_and_reports_unavailable

#### Scenario: Phases and waits
- WHEN the history holds review waits, rework, pauses and quota windows
- THEN phases, human review wait, reopenings and paused time are computed once per overlapping span
- Test: tests/test_queue_admission.py::QueueTests::test_phase_waiting_and_regressions_from_fixed_history
- Test: tests/test_queue_admission.py::QueueTests::test_timing_edge_cases_from_review

#### Scenario: Worker time
- WHEN a worker is still running or ended unknown, or settled
- THEN its running time counts until now, or stops at its terminal event
- Test: tests/test_queue_admission.py::QueueTests::test_live_worker_runtime_counts_until_now
- Test: tests/test_queue_admission.py::QueueTests::test_deadline_interrupts_and_settles_timeout

#### Scenario: Closed and retired records
- WHEN a queue was closed or attempts retired
- THEN their claims stay listed, retired ones keep counting, and a closed queue's PRs do not count for the new queue
- Test: tests/test_queue_admission.py::QueueTests::test_close_archives_a_finished_queue_for_a_new_one
- Test: tests/test_queue_admission.py::QueueTests::test_retire_moves_a_settled_claim_aside_and_refuses_otherwise

### Requirement: Public progress declarations
`record` SHALL append only a known kind and state with a short summary free
of control characters, secret shapes and local paths, references only to the
selected repository's issues, PRs or runs, and a full SHA-1 or SHA-256
revision where one is given or required, for the queue's coordinator.

#### Scenario: Summary filter
- WHEN a summary contains a token, password, key, credential URL or local path
- THEN it is refused, while ordinary words and public URLs pass
- Test: tests/test_progress.py::ProgressValidationTests::test_summary_filter

#### Scenario: Revision shape
- WHEN a revision is not 40 or 64 lowercase hex characters
- THEN the declaration is refused
- Test: tests/test_progress.py::ProgressValidationTests::test_revision_accepts_sha1_and_sha256_only

#### Scenario: Refused records
- WHEN a declaration has an unknown field, a foreign reference, no revision for a check, or the caller is not the coordinator
- THEN `record` refuses
- Test: tests/test_dashboard.py::DashboardTests::test_progress_validation_unknown_worker_and_dependency_budget
