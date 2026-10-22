# Claims and worktrees

Covers: tools/worktree.py

`tools/worktree.py` claims one GitHub leaf issue and prepares a native Git
worktree for it under the clone's shared `ballast-v2` state directory. The
claim record is written before any checkout exists; later helpers revalidate
it before they act. Admission rules a claim must pass are in
[queue admission](queue-admission.md); recovery, settlement and retirement of
a claim are in [coordinator](coordinator.md).

### Requirement: Verified GitHub origin
The helper SHALL accept only an explicit `owner/name` repository whose `origin`
remote is a credential-free `github.com` HTTPS or SSH URL naming that same
repository, and SHALL refuse every other origin.

#### Scenario: Accepted origin forms
- WHEN the origin is `https://github.com/O/N`, `git@github.com:O/N.git` or `ssh://git@github.com/O/N`, with or without `.git`, a trailing slash or a different letter case
- THEN the repository is accepted
- Test: tests/test_standalone_execution.py::OriginFormTests::test_accepted_origins

#### Scenario: Refused origin forms
- WHEN the origin carries credentials, another host, user or port, an SSH alias, or another repository name
- THEN the helper refuses: origin does not match
- Test: tests/test_standalone_execution.py::OriginFormTests::test_refused_origins
- Test: tests/test_standalone_execution.py::ExecutionTests::test_wrong_repository_and_branch_block

#### Scenario: Dot segments
- WHEN the requested repository or the origin path contains a `.` or `..` segment
- THEN the helper refuses
- Test: tests/test_standalone_execution.py::OriginFormTests::test_dot_segments_refused

### Requirement: Exclusive claim before mutation
Preparation SHALL write one claim per issue under the shared lock before
creating the checkout, refuse an issue that already has a claim, and give
each claimed issue its own branch and worktree from the verified base.

#### Scenario: Duplicate claim
- WHEN an issue already has a claim
- THEN preparation refuses: issue already claimed
- Test: tests/test_standalone_execution.py::ExecutionTests::test_linked_worktree_and_duplicate_claim

#### Scenario: Racing coordinators
- WHEN two preparations of the same issue race
- THEN exactly one claims it and the other is refused
- Test: tests/test_queue_admission.py::QueueTests::test_two_coordinators_racing_get_one_claim

#### Scenario: Independent issues
- WHEN two different issues are prepared
- THEN each gets its own checkout
- Test: tests/test_queue_admission.py::QueueTests::test_independent_issues_get_separate_worktrees_within_issue_cap

### Requirement: Fresh integration base
Preparation SHALL read the base branch revision from GitHub, refuse a
malformed response, and refuse when the local `origin/BASE` differs from it.

#### Scenario: Stale base
- WHEN the local remote-tracking base differs from GitHub's
- THEN preparation refuses: integration base is stale
- Test: tests/test_standalone_execution.py::ExecutionTests::test_stale_base_and_setup_failure_preserve_state

#### Scenario: Malformed branch response
- WHEN GitHub's branch reference response is not an object with an object SHA
- THEN preparation refuses
- Test: tests/test_standalone_execution.py::ExecutionTests::test_malformed_host_responses_fail_closed

### Requirement: Failed preparation keeps evidence
A preparation that fails after its claim exists SHALL keep the claim, marked
`setup_failed`, or `preparing` when the process died before marking it.

#### Scenario: Setup failure
- WHEN creating the worktree fails after the claim was written
- THEN the claim stays with status `setup_failed`
- Test: tests/test_standalone_execution.py::ExecutionTests::test_stale_base_and_setup_failure_preserve_state

#### Scenario: Killed before the checkout
- WHEN the process dies before the checkout exists
- THEN the claim stays with status `preparing`
- Test: tests/test_queue_admission.py::QueueTests::test_preparation_killed_before_checkout_is_recreated

### Requirement: Stacked parent
With `--parent`, preparation SHALL accept only an existing, unsettled claim of
the same repository and coordinator whose branch is the requested base and
which has no stacked child yet, and SHALL record the parent link and the
child's stack position.

#### Scenario: Valid parent
- WHEN the parent claim is on the requested base branch
- THEN the child records the parent's issue and attempt, base SHA and stack position, and a grandchild extends the stack
- Test: tests/test_queue_admission.py::QueueTests::test_stacked_preparation_records_parent_and_refuses_bad_parents

#### Scenario: Refused parents
- WHEN the parent claim is missing, is the issue itself, is on another branch, already has a child, or is settled
- THEN preparation refuses and writes no claim
- Test: tests/test_queue_admission.py::QueueTests::test_stacked_preparation_records_parent_and_refuses_bad_parents

### Requirement: Claim revalidation
Before a helper acts on a claim it SHALL check that the record is well
formed and ready, that the checkout belongs to this clone, branch and base,
and SHALL derive Git metadata from the claim, never from the worker-writable
checkout gitfile or inherited `GIT_*` variables.

#### Scenario: Malformed claim
- WHEN the claim record is not a well-formed object
- THEN validation refuses: issue claim is malformed
- Test: tests/test_standalone_execution.py::ExecutionTests::test_corrupt_claim_blocks_before_process

#### Scenario: Claim not ready
- WHEN the claim status is not `ready`
- THEN validation refuses
- Test: tests/test_queue_admission.py::QueueTests::test_interrupted_preparation_and_legacy_claim_are_recovered
- Test: tests/test_standalone_execution.py::ExecutionTests::test_worker_main_reports_claim_and_lock_reasons

#### Scenario: Branch differs
- WHEN the checkout is on another branch than the claim's
- THEN validation refuses
- Test: tests/test_standalone_execution.py::ExecutionTests::test_wrong_repository_and_branch_block

#### Scenario: Hostile Git environment
- WHEN the caller sets `GIT_INDEX_FILE`, `GIT_OBJECT_DIRECTORY` or `GIT_CONFIG_*`
- THEN helper Git ignores them and reads the claim's repository
- Test: tests/test_standalone_execution.py::ExecutionTests::test_inherited_git_variables_cannot_redirect_helper_git

#### Scenario: Worker-written gitfile
- WHEN a worker points the checkout's `.git` at another repository
- THEN helper Git uses the pinned admin directory and runs nothing from it
- Test: tests/test_standalone_execution.py::ExecutionTests::test_worker_written_gitfile_cannot_run_host_commands
- Test: tests/test_queue_admission.py::QueueTests::test_publish_ignores_worker_written_gitfile

### Requirement: Fixed diagnostics
The command SHALL print a local-only claim handle on success and, on
refusal, exit 1 with a fixed reason that carries no backend payload.

#### Scenario: Fixed reason
- WHEN preparation is refused with a fixed reason
- THEN the command exits 1 and prints that reason
- Test: tests/test_standalone_execution.py::ExecutionTests::test_main_reports_fixed_reasons_and_stays_generic_otherwise

### Requirement: Open leaf target and explicit input
Preparation SHALL accept only an open GitHub issue that is not a pull request and has no sub-issues, SHALL refuse a non-positive issue number or an invalid base branch name before any host call, and SHALL refuse a malformed issue response or child summary.

#### Scenario: Target is not an open leaf issue
- WHEN the target issue is closed, is a pull request, has sub-issues, or the response names another number
- THEN preparation refuses: target is not an open leaf issue, and writes no claim
- Test: tests/test_standalone_execution.py::ExecutionTests::test_prepare_refuses_targets_that_are_not_open_leaves

#### Scenario: Non-positive issue or invalid base branch
- WHEN the issue number is below 1 or the base branch name is empty, starts with a symbol, contains a space or shell character, or exceeds 128 characters
- THEN preparation refuses: issue and integration branch must be explicit, before any host call
- Test: tests/test_standalone_execution.py::ExecutionTests::test_prepare_refuses_bad_issue_number_and_base_name

#### Scenario: Malformed issue response
- WHEN GitHub's issue response is not an object, or its child summary is not an object
- THEN preparation refuses: the issue response or child summary is malformed
- Test: tests/test_standalone_execution.py::ExecutionTests::test_prepare_refuses_malformed_issue_response_and_summary

### Requirement: Prepared checkout identity
After creating the worktree, preparation SHALL verify that the checkout's HEAD is the claim's base revision and its branch is the claim's branch, and SHALL refuse otherwise.

#### Scenario: Checkout differs from its claim
- WHEN the new checkout's HEAD or branch differs from the claim
- THEN preparation refuses: prepared checkout identity differs from its claim, and the claim stays with status `setup_failed`
- Test: tests/test_standalone_execution.py::ExecutionTests::test_prepared_checkout_identity_must_match_claim
