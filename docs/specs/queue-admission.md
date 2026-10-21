# Queue admission

Covers: tools/admission.py

`tools/admission.py` holds the clone-wide queue policy and the claim
records under one POSIX lock. It admits issues, reserves workers, counts
attempts, records controls and settlements, and closes or retires what is
finished. Unknown ownership always consumes capacity.

### Requirement: Finite queue policy
A queue SHALL be created once with explicit positive limits, a bounded
selection and an optional review fallback naming another provider than the
worker's, a model and an approval issue or comment URL on the same
repository; an existing queue SHALL never be replaced, and a malformed policy
SHALL fail closed.

#### Scenario: Queue already exists
- WHEN a queue is created while another is configured
- THEN creation refuses: recover it instead of resetting its budget
- Test: tests/test_queue_admission.py::QueueTests::test_close_archives_a_finished_queue_for_a_new_one

#### Scenario: Malformed policy
- WHEN `queue.json` does not match the schema
- THEN admission refuses: queue policy is malformed
- Test: tests/test_queue_admission.py::QueueTests::test_corrupt_policy_fails_closed

#### Scenario: Invalid review fallback
- WHEN the fallback names the worker's provider, lacks a model or approval, has an extra key, or links a PR or another repository
- THEN creation refuses and a policy carrying it is malformed
- Test: tests/test_coordinator_execution.py::CoordinatorExecutionTests::test_fallback_refused_while_paused_and_policy_is_validated

### Requirement: Issue admission
Admission SHALL reserve a fresh claim only for a selected issue of the queue's
repository, for the queue's coordinator, while the queue runs and while the
issue and human-review backlog limits have room, counting claims without a
recorded activity as unknown.

#### Scenario: Issue limit
- WHEN the issue limit is reached
- THEN admission refuses and no claim is written
- Test: tests/test_queue_admission.py::QueueTests::test_independent_issues_get_separate_worktrees_within_issue_cap

#### Scenario: Pre-queue claim
- WHEN a claim made before the queue exists has no activity
- THEN it counts as unknown and fills the issue limit
- Test: tests/test_queue_admission.py::QueueTests::test_unknown_claim_and_worker_consume_capacity

#### Scenario: Outside issue or foreign coordinator
- WHEN the issue is not selected, or the caller is not the queue's coordinator
- THEN admission refuses
- Test: tests/test_queue_admission.py::QueueTests::test_foreign_coordinator_and_outside_issue_are_rejected

#### Scenario: Backlog limit
- WHEN published PRs not yet confirmed merged fill the backlog limit
- THEN admission refuses until GitHub confirms a merge
- Test: tests/test_queue_admission.py::QueueTests::test_backlog_holds_until_github_confirms_merge

#### Scenario: Paused queue
- WHEN the queue is paused
- THEN admission and new workers are refused until an explicit resume
- Test: tests/test_queue_admission.py::QueueTests::test_pause_blocks_admission_and_turns_without_inferring_stop

#### Scenario: Finished queue
- WHEN the queue is cancelled or past its deadline
- THEN admission refuses, naming the queue, its coordinator and `close --reason`
- Test: tests/test_queue_admission.py::QueueTests::test_another_coordinator_closes_only_a_finished_settled_queue

#### Scenario: Spent attempts carry over
- WHEN an issue with retired attempts of this queue is admitted again
- THEN the new claim keeps the highest spent attempts per role of this queue only
- Test: tests/test_queue_admission.py::QueueTests::test_new_attempt_keeps_this_queues_spent_attempts

### Requirement: Worker reservation
A worker reservation SHALL take the issue's single writer lock and a slot of
the clone-wide worker limit together, and SHALL refuse while another worker
or a coordinator execution holds the issue, when the claim is not admitted
and owned by this queue and coordinator, when its policy vanished, or when
the worker or attempt limit is reached.

#### Scenario: Writer lock held
- WHEN another worker holds the issue's lock, including an unknown one
- THEN reservation refuses: another worker holds this issue
- Test: tests/test_standalone_execution.py::ExecutionTests::test_unconfirmed_completion_retains_lock

#### Scenario: Coordinator execution holds the issue
- WHEN a coordinator execution is open on the claim
- THEN reservation refuses
- Test: tests/test_coordinator_execution.py::CoordinatorExecutionTests::test_implementation_lifecycle_takes_no_worker_capacity_or_lock

#### Scenario: Worker limit with unknown workers
- WHEN held locks, unknown ones included, fill the worker limit
- THEN reservation refuses: total worker limit reached
- Test: tests/test_queue_admission.py::QueueTests::test_review_counts_in_worker_budget_and_attempts_do_not_reset
- Test: tests/test_queue_admission.py::QueueTests::test_unknown_claim_and_worker_consume_capacity

#### Scenario: Claim needs reconciliation
- WHEN the claim predates the queue or belongs to another coordinator
- THEN reservation refuses until it is recovered
- Test: tests/test_queue_admission.py::QueueTests::test_interrupted_preparation_and_legacy_claim_are_recovered
- Test: tests/test_queue_admission.py::QueueTests::test_queue_mutations_require_the_queue_coordinator

#### Scenario: Policy vanished
- WHEN a queue-bound claim's policy is missing
- THEN reservation and settlement refuse: policy is missing
- Test: tests/test_queue_admission.py::QueueTests::test_bound_claim_fails_closed_without_its_policy

### Requirement: Attempt budget
A worker attempt SHALL be spent when its turn is permitted, after route
qualification, and SHALL never reset on resume; only a backend-confirmed
cancellation SHALL give its attempt back, once.

#### Scenario: Attempt limit
- WHEN a role's attempts reach the limit
- THEN the next worker is refused: worker attempt limit reached
- Test: tests/test_queue_admission.py::QueueTests::test_review_counts_in_worker_budget_and_attempts_do_not_reset

#### Scenario: Qualification failure
- WHEN a worker fails before its turn permit
- THEN no attempt is spent
- Test: tests/test_queue_admission.py::QueueTests::test_qualification_failure_spends_no_attempt

#### Scenario: Cancelled turn refunded once
- WHEN a turn settles `cancelled` after an operator signal
- THEN its attempt is refunded once, even if released again
- Test: tests/test_queue_admission.py::QueueTests::test_operator_cancelled_attempts_are_refunded

#### Scenario: Timeout and unknown keep counting
- WHEN a turn settles `timeout`, or stays unknown and is released
- THEN its attempt stays spent
- Test: tests/test_queue_admission.py::QueueTests::test_timeout_and_unknown_attempts_keep_counting

### Requirement: Release on stop evidence
An unknown worker's lock SHALL be released only by the coordinator naming
that exact reservation with bounded stop evidence, which marks its result
`released`.

#### Scenario: Release
- WHEN the coordinator releases the held reservation with evidence
- THEN the lock is removed, the result is `released` and a new worker may start
- Test: tests/test_queue_admission.py::QueueTests::test_unknown_worker_is_released_only_with_evidence

#### Scenario: Wrong reservation
- WHEN the named worker does not hold the lock
- THEN release refuses: no such worker reservation
- Test: tests/test_queue_admission.py::QueueTests::test_unknown_worker_is_released_only_with_evidence

### Requirement: Coordinator ownership
Every queue mutation SHALL require `BALLAST_COORDINATOR` to equal the queue's
coordinator, and an unset or empty value SHALL never match; claims made
before any queue need no coordinator.

#### Scenario: Wrong, empty or unset coordinator
- WHEN control, settlement, release, publication, PR recording, close, recovery, reservation or progress runs under another, empty or unset reference
- THEN it refuses and changes no record or checkout
- Test: tests/test_queue_admission.py::QueueTests::test_queue_mutations_require_the_queue_coordinator

#### Scenario: Pre-queue claim
- WHEN no queue exists
- THEN release, PR recording and settlement work without a coordinator and record none
- Test: tests/test_queue_admission.py::QueueTests::test_pre_queue_claim_needs_no_coordinator

### Requirement: Settlement transitions
Settlement SHALL record a supported activity transition with bounded
evidence, recheck the issue limit when work becomes active again, and let a
claim stranded under another coordinator only be stopped, by the queue's
coordinator, while no writer lock exists.

#### Scenario: Unsupported transition
- WHEN a transition is not allowed, such as `pr_wait` to `unknown` or a pre-queue claim to `active`
- THEN settlement refuses
- Test: tests/test_queue_admission.py::QueueTests::test_transitions_recheck_issue_cap
- Test: tests/test_queue_admission.py::QueueTests::test_legacy_claim_cannot_be_taken_over_without_stop

#### Scenario: Reactivation over the issue limit
- WHEN a settled issue returns to active work while the issue limit is full
- THEN settlement refuses
- Test: tests/test_queue_admission.py::QueueTests::test_transitions_recheck_issue_cap

#### Scenario: Stranded foreign claim
- WHEN an active claim belongs to another coordinator
- THEN only a stop by the queue's coordinator without a writer lock is accepted, recording the previous coordinator
- Test: tests/test_queue_admission.py::QueueTests::test_active_transfer_needs_stop_evidence
- Test: tests/test_queue_admission.py::QueueTests::test_queue_coordinator_stops_a_stranded_foreign_claim

### Requirement: Queue controls
Pause, resume and cancel SHALL be recorded without inferring that active
workers stopped; a cancelled queue SHALL not be resumed or paused, a resume
SHALL clear a quota pause, and a control bound to an expected context SHALL
refuse a replaced queue.

#### Scenario: Cancelled queue
- WHEN a cancelled queue is paused or resumed
- THEN the control refuses
- Test: tests/test_dashboard.py::DashboardTests::test_durable_projection_without_http

#### Scenario: Replaced context
- WHEN the queue changed since the caller bound its context
- THEN the control refuses
- Test: tests/test_dashboard.py::DashboardTests::test_durable_projection_without_http
- Test: tests/test_dashboard.py::DashboardTests::test_replacement_is_checked_inside_control_lock

### Requirement: Quota pause
A structured quota error SHALL pause dispatch until the backend's reset time,
or until an explicit resume when the reset time is unknown.

#### Scenario: Known window
- WHEN the quota window has a reset time
- THEN admission refuses until that time passes
- Test: tests/test_queue_admission.py::QueueTests::test_quota_with_known_window_pauses_until_reset

#### Scenario: Unknown window
- WHEN no reset time is known
- THEN the pause holds however long until the operator resumes
- Test: tests/test_queue_admission.py::QueueTests::test_quota_without_window_needs_explicit_resume

### Requirement: Close a finished queue
Close SHALL archive only a cancelled or expired queue whose claims are all
settled and with no worker lock held; its coordinator, or under those same
conditions any bounded other reference, may close it, and the archive SHALL
record who closed it.

#### Scenario: Live budget
- WHEN the queue still has budget
- THEN close refuses
- Test: tests/test_queue_admission.py::QueueTests::test_close_archives_a_finished_queue_for_a_new_one

#### Scenario: Unsettled claim or held lock
- WHEN a claim of the queue is active, unknown or awaiting merge, or any worker lock exists
- THEN close refuses
- Test: tests/test_queue_admission.py::QueueTests::test_close_archives_a_finished_queue_for_a_new_one
- Test: tests/test_queue_admission.py::QueueTests::test_another_coordinator_closes_only_a_finished_settled_queue

#### Scenario: Cancelled queue before its deadline
- WHEN a cancelled queue is closed before its deadline
- THEN it is archived
- Test: tests/test_queue_admission.py::QueueTests::test_close_accepts_a_cancelled_queue_before_its_deadline
- Test: tests/test_queue_admission.py::QueueTests::test_cancelled_queue_selection_names_close

#### Scenario: Another coordinator
- WHEN another reference closes a finished settled queue
- THEN it is archived with `closed_by` and `previous_coordinator`, while an empty or unset reference is refused
- Test: tests/test_queue_admission.py::QueueTests::test_another_coordinator_closes_only_a_finished_settled_queue

#### Scenario: No queue
- WHEN no queue is configured
- THEN close refuses
- Test: tests/test_queue_admission.py::QueueTests::test_close_archives_a_finished_queue_for_a_new_one

### Requirement: Retire a settled claim
Retirement SHALL move a `stopped` or `merged` claim aside with a `retired`
milestone, only for the current queue's coordinator, with bounded evidence,
a well-formed identity, no writer lock or open execution, no stacked child,
no existing archive, and while its activity and PR are those the caller
checked.

#### Scenario: Retire
- WHEN a settled claim meets every condition
- THEN it moves to `retired-issue-N-ATTEMPT.json` and the issue can be prepared again
- Test: tests/test_queue_admission.py::QueueTests::test_retire_moves_a_settled_claim_aside_and_refuses_otherwise

#### Scenario: Refused retirements
- WHEN the claim is active, unknown or awaiting merge, holds a worker or execution, has a malformed identity or evidence, has a stacked child, is already retired, changed since the check, or the caller is not the coordinator
- THEN retirement refuses and nothing moves
- Test: tests/test_queue_admission.py::QueueTests::test_retire_moves_a_settled_claim_aside_and_refuses_otherwise
