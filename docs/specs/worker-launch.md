# Worker launch and route verification

Covers: tools/worker.py
Covers: tools/codex.py

`tools/worker.py` runs one foreground Codex worker on a claim, outside CI,
after verifying the executing route and sandbox. `tools/codex.py` is the
bounded app-server transport and the task-free route probe. A worker is
settled only on backend-confirmed terminal evidence; anything else stays
`unknown` and keeps the issue's writer lock.

### Requirement: Launch preconditions
The worker and the probe SHALL refuse before creating any client process in
CI; the probe SHALL also refuse invalid arguments; the worker SHALL also refuse
inside an issue checkout, on a malformed claim, for a review of a dirty
checkout, without a Linux parent-death binding, after a stop signal, and for an
implementation of an R1 or R2 leaf without an approved spec delta
([spec approval](spec-approval.md)).

#### Scenario: CI
- WHEN a CI marker variable is set
- THEN the worker and the probe refuse without starting a process
- Test: tests/test_codex_routing.py::QualificationTests::test_ci_refuses_before_process_creation
- Test: tests/test_standalone_execution.py::ExecutionTests::test_dirty_review_and_ci_block_without_process

#### Scenario: Inside an issue checkout
- WHEN the worker (not the probe) starts from inside an issue checkout
- THEN it refuses: start the worker outside issue checkouts
- Test: tests/test_queue_admission.py::QueueTests::test_helpers_refuse_to_start_inside_an_issue_checkout

#### Scenario: Invalid probe arguments
- WHEN the probe timeout is not finite and positive, or the model is empty
- THEN it refuses without starting a process
- Test: tests/test_codex_routing.py::QualificationTests::test_invalid_arguments_never_launch_a_process

#### Scenario: Dirty review or corrupt claim
- WHEN a review's checkout has uncommitted changes, or the claim is malformed
- THEN the worker refuses before any client starts
- Test: tests/test_standalone_execution.py::ExecutionTests::test_dirty_review_and_ci_block_without_process
- Test: tests/test_standalone_execution.py::ExecutionTests::test_corrupt_claim_blocks_before_process

#### Scenario: Unbound client lifetime
- WHEN the parent-death signal cannot be set up
- THEN no client starts and the worker settles `not_started`, releasing its lock
- Test: tests/test_standalone_execution.py::ExecutionTests::test_unbound_client_lifetime_never_starts_client

#### Scenario: Unapproved implementation
- WHEN an implementation worker targets an R1 or R2 leaf without an approved spec delta
- THEN it refuses before reserving the lock or starting a client
- Test: tests/test_standalone_execution.py::ExecutionTests::test_unapproved_r1_implement_never_reserves_or_launches

#### Scenario: Stop signal before reservation
- WHEN SIGTERM arrives before the reservation
- THEN no client starts and nothing is reserved
- Test: tests/test_queue_admission.py::QueueTests::test_signal_before_reservation_starts_nothing

### Requirement: Route verified before task input
Before any task input, the worker SHALL require ChatGPT subscription access,
the requested model and effort in the paged model catalog, and a
`thread/start` receipt matching the requested model, effort, provider,
approval policy, working directory and sandbox; the receipt SHALL be recorded
before dispatch, and a mismatch SHALL release the lock without dispatching.

#### Scenario: Verified route
- WHEN every receipt field matches
- THEN `route_verified` is recorded before `task_dispatched` and requested equals observed
- Test: tests/test_standalone_execution.py::ExecutionTests::test_completed_worker_records_receipt_before_dispatch
- Test: tests/test_codex_routing.py::QualificationTests::test_success_checks_receipt_without_task_input_or_sensitive_output

#### Scenario: Wrong access or receipt
- WHEN the account is not ChatGPT, or the receipt's effort, model, sandbox, thread or working directory differs
- THEN the worker refuses, dispatches nothing and releases the lock
- Test: tests/test_standalone_execution.py::ExecutionTests::test_invalid_routes_and_access_never_dispatch
- Test: tests/test_codex_routing.py::QualificationTests::test_mismatched_or_missing_receipt_never_qualifies

#### Scenario: Unsupported pair
- WHEN the model does not support the effort on any catalog page
- THEN no thread is started
- Test: tests/test_codex_routing.py::QualificationTests::test_unsupported_effort_stops_before_thread_creation

#### Scenario: Catalog pagination
- WHEN the catalog has several pages, or repeats a cursor
- THEN every page is read, and a repeated cursor is refused
- Test: tests/test_codex_routing.py::QualificationTests::test_catalog_pages_are_followed_and_repeated_cursor_is_rejected

#### Scenario: Protocol errors
- WHEN the client returns invalid JSON, ends, errors, answers another request or sends an oversized line
- THEN nothing qualifies and no backend payload is shown
- Test: tests/test_codex_routing.py::QualificationTests::test_protocol_errors_eof_and_malformed_json_are_not_receipts

### Requirement: Sandbox roots and scratch directory
Each worker SHALL get a private `0700` scratch directory as its only extra
write root, with `TMPDIR`, the uv cache and the XDG cache pointed into it and
the system temp roots excluded; a review thread SHALL work in its scratch,
with the checkout in no write root and no project-root search above it. The
receipt SHALL show exactly those roots, and a settled worker's scratch SHALL be
removed while an `unknown` one's is kept.

#### Scenario: Roles and roots
- WHEN an implementation or review worker starts
- THEN the implementer works in the checkout with the scratch as write root, and the reviewer works in its scratch with no write root, is told to read the checkout's `AGENTS.md`, and loads no project root markers
- Test: tests/test_standalone_execution.py::ExecutionTests::test_each_role_writes_only_its_private_scratch

#### Scenario: Receipt roots differ
- WHEN the receipt shows other, extra or missing write roots, temp roots not excluded, a read-only sandbox, a review cwd in the checkout, or instructions loaded from above the scratch
- THEN the worker refuses before dispatch and removes the scratch
- Test: tests/test_standalone_execution.py::ExecutionTests::test_receipt_must_show_exactly_the_scratch_root
- Test: tests/test_standalone_execution.py::ExecutionTests::test_missing_write_roots_blocks_before_dispatch

#### Scenario: Temporary files in a review
- WHEN a review's tool command creates temporary files
- THEN they land in the scratch, which is removed, and the checkout stays clean
- Test: tests/test_standalone_execution.py::ExecutionTests::test_review_test_with_temp_files_leaves_checkout_clean
- Test: tests/test_standalone_execution.py::ExecutionTests::test_uv_run_with_scratch_environment_leaves_checkout_untouched

#### Scenario: Process left in the scratch
- WHEN a process still runs in the scratch after the turn
- THEN the worker stays `unknown`, keeps its lock and its scratch
- Test: tests/test_standalone_execution.py::ExecutionTests::test_process_left_in_scratch_keeps_worker_unknown

### Requirement: Task boundary
The task text SHALL be prefixed with a boundary that forbids clone-wide Git
state (`git stash`, `git worktree`, switching branches) and asks for a
comparison with `git diff BASE`, names the checkout, and tells a review to
read the checkout's `AGENTS.md`.

#### Scenario: Clone-wide Git state
- WHEN a turn starts
- THEN its input names `git stash`, `git worktree`, switching branches and `git diff`
- Test: tests/test_standalone_execution.py::ExecutionTests::test_handoff_forbids_clone_wide_git_state

#### Scenario: Checkout and review instructions
- WHEN an implementation or review turn starts
- THEN its input names the checkout, and only a review's input asks to read the checkout's `AGENTS.md`
- Test: tests/test_standalone_execution.py::ExecutionTests::test_each_role_writes_only_its_private_scratch

### Requirement: Confirmed settlement
A worker SHALL settle `completed`, `cancelled`, `timeout` or `quota` only from
a matching terminal turn notification followed by a quiet checkout and scratch;
every other ending SHALL leave it `unknown` with its lock held, keeping a
completed turn's output.

#### Scenario: Unconfirmed completion
- WHEN the turn fails, a notification is malformed, or the client shutdown fails
- THEN the worker is `unknown` and its lock blocks the next worker
- Test: tests/test_standalone_execution.py::ExecutionTests::test_unconfirmed_completion_retains_lock
- Test: tests/test_standalone_execution.py::ExecutionTests::test_malformed_notification_preserves_unknown
- Test: tests/test_queue_admission.py::QueueTests::test_client_shutdown_failure_keeps_completed_output

#### Scenario: Survivor in the checkout
- WHEN a process, the worker's or not, still runs in the checkout past the quiet bound
- THEN the worker is `unknown`, names the PID and command, and keeps the completed output
- Test: tests/test_queue_admission.py::QueueTests::test_surviving_sandbox_process_keeps_worker_unknown
- Test: tests/test_queue_admission.py::QueueTests::test_unrelated_process_in_checkout_is_named_and_output_kept

#### Scenario: Survivor detection
- WHEN processes are scanned
- THEN one working inside the checkout is found, an unreadable same-user process started after the worker counts, and names are sanitized and bounded
- Test: tests/test_queue_admission.py::QueueTests::test_survivors_finds_a_process_inside_the_checkout
- Test: tests/test_queue_admission.py::QueueTests::test_unreadable_same_user_process_is_a_survivor
- Test: tests/test_queue_admission.py::QueueTests::test_non_utf8_process_name_is_still_named
- Test: tests/test_queue_admission.py::QueueTests::test_survivor_names_are_bounded

### Requirement: Cancel, deadline and signals
On queue cancel, its deadline or SIGTERM/SIGINT, the worker SHALL interrupt
the turn and wait a bounded time for its terminal notification and for
surviving tool commands; a confirmed interrupt settles `cancelled` or
`timeout`, anything else stays `unknown`.

#### Scenario: Cancel
- WHEN the queue is cancelled during a turn and the backend confirms the interrupt
- THEN the worker settles `cancelled` and releases its lock
- Test: tests/test_queue_admission.py::QueueTests::test_cancel_interrupts_live_worker_and_releases_on_terminal

#### Scenario: Deadline
- WHEN the worker's timeout passes and the backend confirms the interrupt
- THEN the worker settles `timeout`
- Test: tests/test_queue_admission.py::QueueTests::test_deadline_interrupts_and_settles_timeout

#### Scenario: Unconfirmed interrupt
- WHEN the backend ends, rejects the interrupt, stays silent past the interrupt bound, or a survivor outlasts the extra wait
- THEN the worker stays `unknown` with its lock
- Test: tests/test_queue_admission.py::QueueTests::test_cancel_without_terminal_evidence_stays_unknown
- Test: tests/test_queue_admission.py::QueueTests::test_deadline_without_quiet_terminal_evidence_stays_unknown
- Test: tests/test_standalone_execution.py::ExecutionTests::test_interrupt_bound_ends_a_silent_backend
- Test: tests/test_queue_admission.py::QueueTests::test_survivor_past_the_interrupt_bound_keeps_worker_unknown

#### Scenario: Tool command outlives the interrupt
- WHEN a tool command still runs after a confirmed interrupt and then exits
- THEN the worker records `survivors_exited` and settles
- Test: tests/test_queue_admission.py::QueueTests::test_interrupted_turn_settles_once_surviving_tool_command_exits

#### Scenario: Signals
- WHEN SIGTERM or SIGINT arrives before dispatch, after dispatch, or to the whole process group
- THEN the worker settles `not_started` without a turn permit, or `cancelled` on a confirmed interrupt, else `unknown`, and restores the previous handlers
- Test: tests/test_queue_admission.py::QueueTests::test_signal_before_dispatch_settles_not_started
- Test: tests/test_queue_admission.py::QueueTests::test_signal_after_dispatch_interrupts_or_stays_unknown
- Test: tests/test_queue_admission.py::QueueTests::test_group_signal_after_dispatch_settles_cancelled
- Test: tests/test_standalone_execution.py::ExecutionTests::test_main_uses_explicit_pair_and_sanitizes_errors

#### Scenario: Killed worker
- WHEN the worker process is killed
- THEN its client, in its own session, dies with it
- Test: tests/test_queue_admission.py::QueueTests::test_client_dies_with_a_killed_worker

### Requirement: Quota outcome
A turn failing with a structured usage or rate limit error SHALL settle
`quota`, record the backend's reset time of an exhausted window or none, and
pause the queue, keeping no account data.

#### Scenario: Quota with a reset time
- WHEN an exhausted window reports its reset time
- THEN the result records `quota` and that `retry_at`, and the policy holds no plan data
- Test: tests/test_queue_admission.py::QueueTests::test_quota_with_known_window_pauses_until_reset

#### Scenario: Quota without a reset time
- WHEN no reset time is known
- THEN `retry_at` is none and the queue stays paused
- Test: tests/test_queue_admission.py::QueueTests::test_quota_without_window_needs_explicit_resume

### Requirement: Bounded transport
The transport SHALL bound every read and write by one deadline, allow only
listed methods, kill and reap a client that does not exit, and treat a
nonzero client exit as a failure.

#### Scenario: Deadline and allowlist
- WHEN the deadline passes, or a method outside the allowlist is sent
- THEN the call fails
- Test: tests/test_codex_routing.py::QualificationTests::test_shared_deadline_and_request_allowlist
- Test: tests/test_standalone_execution.py::ExecutionTests::test_stopped_reader_cannot_block_task_write

#### Scenario: Hung or failing client
- WHEN the client ignores shutdown, or exits nonzero
- THEN it is killed and reaped, and a nonzero exit is not qualified
- Test: tests/test_codex_routing.py::QualificationTests::test_hung_process_is_killed_and_reaped
- Test: tests/test_codex_routing.py::QualificationTests::test_nonzero_process_exit_is_not_qualified
- Test: tests/test_codex_routing.py::QualificationTests::test_exit_failure_racing_with_shutdown_is_not_qualified

### Requirement: Worker diagnostics
The worker command SHALL use the explicit model and effort it is given and
print a fixed reason, or a generic one for any other error, never a backend
payload.

#### Scenario: Fixed and generic reasons
- WHEN the worker is refused
- THEN it prints the fixed reason, such as a held lock or a claim not ready, or a generic one
- Test: tests/test_standalone_execution.py::ExecutionTests::test_main_reports_fixed_reasons_and_stays_generic_otherwise
- Test: tests/test_standalone_execution.py::ExecutionTests::test_worker_main_reports_claim_and_lock_reasons

### Requirement: Launch input bounds
The worker SHALL refuse, before it reserves a lock or starts a client, task input that is empty or over 65536 bytes, a timeout that is not finite or not above zero and at most 900 seconds, a model or effort that is not an explicit identifier, and a missing `codex` on PATH; the probe SHALL also refuse a missing `codex` and a `--cwd` that is not a directory, before it starts a client.

#### Scenario: Task input bounds
- WHEN the task file is empty, or holds more than 65536 bytes
- THEN the worker refuses before reserving a lock or starting a client, and exactly 65536 bytes are accepted
- Test: tests/test_standalone_execution.py::ExecutionTests::test_task_input_outside_the_bounds_never_launches

#### Scenario: Timeout bounds
- WHEN the worker timeout is not finite, is zero or negative, or is over 900 seconds
- THEN the worker refuses before reserving a lock or starting a client, and exactly 900 seconds are accepted
- Test: tests/test_standalone_execution.py::ExecutionTests::test_timeout_outside_the_bounds_never_launches

#### Scenario: Non-identifier route
- WHEN the model or the effort is empty, starts with a separator, holds a character outside letters, digits, dot, underscore and hyphen, or is longer than 128 characters
- THEN the worker refuses before reserving a lock or starting a client
- Test: tests/test_standalone_execution.py::ExecutionTests::test_non_identifier_model_or_effort_never_launches

#### Scenario: Codex missing
- WHEN `codex` is not on PATH
- THEN the worker and the probe refuse without starting a client, and the worker reserves nothing
- Test: tests/test_standalone_execution.py::ExecutionTests::test_missing_codex_never_reserves_or_launches
- Test: tests/test_codex_routing.py::QualificationTests::test_probe_refuses_a_missing_codex

#### Scenario: Probe working directory
- WHEN the probe `--cwd` is a file
- THEN the probe refuses without starting a client
- Test: tests/test_codex_routing.py::QualificationTests::test_probe_refuses_a_cwd_that_is_not_a_directory

### Requirement: Review evidence and turn integrity
A review worker SHALL be refused, and left `unknown` with its lock held, when the checkout head moved or its status became dirty during the turn; a worker SHALL stay `unknown` with its lock held on a final output over 65536 bytes or on a response or approval request it did not expect during a turn; a scratch directory that cannot be removed SHALL be recorded as `scratch_left` and SHALL NOT fail a settled worker.

#### Scenario: Head moved during a review
- WHEN the checkout head differs after a review turn
- THEN the worker is refused with "Reviewed checkout changed", stays `unknown` and keeps its lock
- Test: tests/test_standalone_execution.py::ExecutionTests::test_review_that_moves_the_head_is_refused

#### Scenario: Checkout dirtied during a review
- WHEN the checkout has uncommitted or untracked changes after a review turn
- THEN the worker is refused with "Reviewed checkout changed", stays `unknown` and keeps its lock
- Test: tests/test_standalone_execution.py::ExecutionTests::test_review_that_dirties_the_checkout_is_refused

#### Scenario: Oversized final output
- WHEN the final message is over 65536 bytes, counted in bytes and not characters
- THEN the worker stays `unknown` and keeps its lock; a message of exactly 65536 bytes is kept
- Test: tests/test_standalone_execution.py::ExecutionTests::test_final_output_over_the_cap_leaves_worker_unknown
- Test: tests/test_standalone_execution.py::ExecutionTests::test_final_output_at_the_cap_is_kept

#### Scenario: Unexpected message during a turn
- WHEN the backend sends a response or an approval request the worker did not ask for while a turn runs
- THEN the worker stays `unknown`, keeps its lock and settles nothing
- Test: tests/test_standalone_execution.py::ExecutionTests::test_unexpected_response_during_a_turn_leaves_worker_unknown
- Test: tests/test_standalone_execution.py::ExecutionTests::test_approval_request_during_a_turn_leaves_worker_unknown

#### Scenario: Scratch removal fails
- WHEN removing a settled worker's scratch directory fails
- THEN the worker still settles `completed`, releases its lock and records `scratch_left`
- Test: tests/test_standalone_execution.py::ExecutionTests::test_failed_scratch_removal_is_recorded_and_not_fatal
