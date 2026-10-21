# Merge check

Covers: tools/merge_check.py

`tools/merge_check.py` checks the R0 merge precondition of
[ADR-0026](../adr/0026-r0-merge-on-reviewed-green-head.md) on a reviewed head
and prints the pinned merge command; it merges only with `--merge`. Every
refusal is a fixed reason and runs no merge.

### Requirement: Reviewer evidence
The check SHALL refuse unless the independent review approved the head, the
reviewer confirmed R0, and the reviewed head is a full commit SHA.

#### Scenario: Unapproved verdict
- WHEN the verdict is not `approved`
- THEN the check refuses: the review did not approve this head
- Test: tests/test_merge_check.py::MergeCheckTests::test_refuses_unapproved_verdict

#### Scenario: Risk not confirmed R0
- WHEN the reviewer confirmed another risk
- THEN the check refuses and a human merges
- Test: tests/test_merge_check.py::MergeCheckTests::test_refuses_risk_the_reviewer_did_not_confirm_as_r0

#### Scenario: Short reviewed head
- WHEN the reviewed head is not a 40-character SHA
- THEN the check refuses
- Test: tests/test_merge_check.py::MergeCheckTests::test_refuses_short_reviewed_head

### Requirement: Pull request state
The check SHALL refuse a PR that is not open, is a draft, has a head other than
the reviewed head, comes from a release or dependency branch or a bot author,
or whose body does not tick R0 and only R0.

#### Scenario: Head changed after review
- WHEN the PR head differs from the reviewed head
- THEN the check refuses
- Test: tests/test_merge_check.py::MergeCheckTests::test_refuses_head_changed_after_review

#### Scenario: Draft or closed PR
- WHEN the PR is a draft or not open
- THEN the check refuses
- Test: tests/test_merge_check.py::MergeCheckTests::test_refuses_draft
- Test: tests/test_merge_check.py::MergeCheckTests::test_refuses_closed

#### Scenario: Body risk
- WHEN the body ticks no risk, another risk, or R0 with another
- THEN the check refuses: tick R0 and no other risk
- Test: tests/test_merge_check.py::MergeCheckTests::test_refuses_pr_body_without_only_r0_ticked

#### Scenario: Release and dependency PRs
- WHEN the head branch is a Release Please, Dependabot or Renovate branch, or the author is a bot
- THEN the check refuses: a human merges it
- Test: tests/test_merge_check.py::MergeCheckTests::test_refuses_release_and_dependency_prs

#### Scenario: Malformed PR response
- WHEN GitHub returns something other than the PR object
- THEN the check refuses
- Test: tests/test_merge_check.py::MergeCheckTests::test_refuses_unreadable_github_response

### Requirement: Changed paths
The check SHALL read every page of the PR's changed files, count a rename
under both names, and refuse a PR changing a workflow, release, dependency or
project-excluded (`--exclude`) path, or whose file list is malformed or
incomplete.

#### Scenario: Excluded paths
- WHEN a changed path is under `.github/`, a changelog, version or release file, or a dependency manifest or lockfile
- THEN the check refuses
- Test: tests/test_merge_check.py::MergeCheckTests::test_refuses_excluded_paths

#### Scenario: Project-excluded paths
- WHEN a changed path matches an `--exclude` glob
- THEN the check refuses, while it passes without that glob
- Test: tests/test_merge_check.py::MergeCheckTests::test_refuses_project_excluded_paths

#### Scenario: Rename out of an excluded path
- WHEN a file is renamed from an excluded path
- THEN the check refuses, while a rename between ordinary paths passes
- Test: tests/test_merge_check.py::MergeCheckTests::test_refuses_renames_from_excluded_paths

#### Scenario: Paginated and incomplete file lists
- WHEN the excluded path is on a later page, or fewer files are listed than the PR reports
- THEN the check refuses
- Test: tests/test_merge_check.py::MergeCheckTests::test_reads_every_page_of_files
- Test: tests/test_merge_check.py::MergeCheckTests::test_refuses_truncated_file_list

#### Scenario: Malformed file entries
- WHEN a file entry is not an object or has a missing, empty or non-string name
- THEN the check refuses
- Test: tests/test_merge_check.py::MergeCheckTests::test_refuses_malformed_file_entries

### Requirement: Required checks
The check SHALL collect the base branch's required checks from rulesets and
branch protection, refuse when none is configured or the rules are
unreadable, and refuse unless every required check reported and every run of
it passed on the PR head.

#### Scenario: Missing, failing or pending check
- WHEN a required check never reported, or any run of it did not pass
- THEN the check refuses
- Test: tests/test_merge_check.py::MergeCheckTests::test_refuses_missing_failing_or_pending_required_checks

#### Scenario: Rulesets and protection
- WHEN required checks come from legacy protection, or no required check is configured
- THEN the legacy check is required, and an empty set refuses
- Test: tests/test_merge_check.py::MergeCheckTests::test_reads_required_checks_from_rulesets_and_protection

#### Scenario: Unreadable base rules
- WHEN the rules or branch response is malformed, or the base branch name is malformed
- THEN the check refuses
- Test: tests/test_merge_check.py::MergeCheckTests::test_refuses_unreadable_base_rules

#### Scenario: Failed GitHub read with parseable output
- WHEN a `gh` read exits with an error, even with parseable partial output
- THEN the check refuses, except the failing and pending exit codes of `gh pr checks`
- Test: tests/test_merge_check.py::MergeCheckTests::test_refuses_failed_github_reads_even_with_parseable_output

### Requirement: Merge command
On success the check SHALL print the squash merge command pinned with
`--match-head-commit` to the reviewed head, SHALL merge only with `--merge`,
SHALL report a merge GitHub refuses, and SHALL refuse to run inside an issue
checkout.

#### Scenario: Printed command
- WHEN every precondition holds
- THEN the output is `gh pr merge N --repo github.com/OWNER/NAME --squash --match-head-commit HEAD`
- Test: tests/test_merge_check.py::MergeCheckTests::test_prints_exact_squash_merge_pinned_to_reviewed_head

#### Scenario: Merge only on request
- WHEN `--merge` is absent
- THEN no merge call is made; with it, the pinned merge runs and the result says merged
- Test: tests/test_merge_check.py::MergeCheckTests::test_merge_only_with_explicit_flag

#### Scenario: GitHub refuses the merge
- WHEN the merge call fails
- THEN the check refuses
- Test: tests/test_merge_check.py::MergeCheckTests::test_merge_refused_by_github_is_reported

#### Scenario: Inside an issue checkout
- WHEN the command runs inside an issue checkout
- THEN it refuses before any GitHub call
- Test: tests/test_merge_check.py::MergeCheckTests::test_refuses_to_run_inside_an_issue_checkout
