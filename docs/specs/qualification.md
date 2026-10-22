# Qualification

Covers: tools/qualify.py

`tools/qualify.py` runs the queue, claim, worker, review and publish path end
to end: `local` against fakes, `live` against Codex and GitHub on an
operator-named disposable repository. It deletes nothing. `local --entry CMD`
substitutes an installed `ballast` command for the default.

### Requirement: Local end-to-end run
Local mode SHALL drive every helper through the `ballast` command, by default
this checkout's `tools/cli.py`, against a fake app-server and a fake `gh`, and SHALL print path-free evidence of a selected issue, a
completed implementation and read-only review on an unchanged head, and a
published PR awaiting review.

#### Scenario: Successful run
- WHEN local qualification runs
- THEN it exits 0 with evidence naming both workers, the reviewed head, the PR and `pr_wait`, and no local path or review text
- Test: tests/test_qualify.py::LocalModeTests::test_claim_worker_review_publish_end_to_end

#### Scenario: Worker-written gitfile
- WHEN the implementer points `.git` at a hostile repository
- THEN coordinator Git runs nothing from it
- Test: tests/test_qualify.py::LocalModeTests::test_worker_written_gitfile_cannot_run_host_commands

#### Scenario: Wrong work or rejected review
- WHEN the implementation adds anything other than the artifact, commits, or the review does not end with `Verdict: approve`
- THEN the run exits 1 before publication
- Test: tests/test_qualify.py::LocalModeTests::test_wrong_work_or_rejected_review_fails_before_publication

#### Scenario: Named entry command
- WHEN local qualification runs with `--entry CMD`
- THEN every helper step runs through CMD instead of `tools/cli.py`, and the run completes as with the default
- Test: tests/test_qualify.py::LocalModeTests::test_entry_option_drives_helpers_through_the_named_command

### Requirement: Live safety
Live mode SHALL run only with `--confirm-disposable` on a repository named
`OWNER/ballast-qualification-*`, reserve a new ledger file exclusively, record
each creation before its effect, never delete anything, and list the
commands that would remove what it created.

#### Scenario: Unconfirmed or wrongly named repository
- WHEN confirmation is missing or the name lacks the prefix
- THEN live mode refuses before any command, and `--ledger` is required
- Test: tests/test_qualify.py::LiveModeTests::test_refuses_without_confirmation_or_prefix

#### Scenario: Existing or reserved ledger
- WHEN the ledger exists or another run reserves it
- THEN live mode refuses and leaves it untouched
- Test: tests/test_qualify.py::LiveModeTests::test_existing_ledger_is_never_overwritten
- Test: tests/test_qualify.py::LiveModeTests::test_concurrent_run_cannot_take_a_reserved_ledger

#### Scenario: Leftovers listed, never deleted
- WHEN a run created or reused the repository
- THEN its result lists the repository delete, or the branch delete and issue close, and nothing is deleted
- Test: tests/test_qualify.py::LiveModeTests::test_created_repository_is_listed_never_deleted
- Test: tests/test_qualify.py::LiveModeTests::test_reused_repository_lists_its_branch_and_issue

#### Scenario: Uncertain effects
- WHEN an issue creation response is lost, the id lookup fails after creation, or creation itself failed
- THEN the ledger keeps a findable title, records the creation, or lists a check instead of a delete
- Test: tests/test_qualify.py::LiveModeTests::test_lost_issue_response_leaves_a_findable_title
- Test: tests/test_qualify.py::LiveModeTests::test_creation_is_recorded_before_the_id_lookup
- Test: tests/test_qualify.py::LiveModeTests::test_unconfirmed_creation_lists_a_check_never_a_delete

#### Scenario: Failed run
- WHEN a live run fails
- THEN it deletes nothing and keeps its ledger
- Test: tests/test_qualify.py::LiveModeTests::test_failed_run_deletes_nothing_and_keeps_its_ledger
