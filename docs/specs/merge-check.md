# Merge check

Covers: tools/merge_check.py

`tools/merge_check.py` computes the merge verdict of
[ADR-0027](../adr/0027-spec-approval-living-specs-merge-verdict.md), which
extends the R0 rule of [ADR-0026](../adr/0026-r0-merge-on-reviewed-green-head.md),
for a reviewed head: `MERGE`, `HUMAN` or `BLOCK`, with each reason and what
would raise it. It merges only on `MERGE` and only with `--merge`.

### Requirement: Verdict and precedence
The check SHALL return `BLOCK` when any blocking reason holds, otherwise
`HUMAN` when any human reason holds, otherwise `MERGE`; any state not listed
under `MERGE` or `HUMAN`, an unreadable or malformed response included, SHALL
be `BLOCK`. Every reason SHALL carry what would raise the verdict.

#### Scenario: Precedence
- WHEN an R2 PR is otherwise mergeable, and then also a draft
- THEN the verdict is `HUMAN`, and then `BLOCK` with the human reason still listed
- Test: tests/test_merge_check.py::MergeVerdictTests::test_block_takes_precedence_over_human_and_human_over_merge

#### Scenario: Malformed PR response
- WHEN GitHub returns something other than the PR object, or malformed closing issues
- THEN the verdict is `BLOCK`
- Test: tests/test_merge_check.py::MergeVerdictTests::test_refuses_unreadable_github_response

### Requirement: MERGE
The check SHALL return `MERGE` for an R0 PR that meets the ADR-0026 conditions,
changes no path a `Covers:` glob matches and only adds spec entries, and for an
R1 PR that also has an unedited approval of its spec delta on a closing issue
and every changed path covered.

#### Scenario: R0 merge command
- WHEN every R0 condition holds
- THEN the output is `MERGE` with `gh pr merge N --repo github.com/OWNER/NAME --squash --match-head-commit HEAD`
- Test: tests/test_merge_check.py::MergeVerdictTests::test_prints_exact_squash_merge_pinned_to_reviewed_head

#### Scenario: R0 adding spec entries
- WHEN an R0 PR only adds spec entries
- THEN the verdict is `MERGE`
- Test: tests/test_merge_check.py::MergeVerdictTests::test_r0_adding_spec_entries_only_merges

#### Scenario: Approved, conformant, covered R1
- WHEN the reviewed head's three-dot `docs/specs/` delta hashes to the hash an approval on the closing issue quotes, and every changed path is covered
- THEN the verdict is `MERGE` and names the approval
- Test: tests/test_merge_check.py::MergeVerdictTests::test_r1_with_approved_conformant_covered_spec_merges
- Test: tests/test_merge_check.py::MergeVerdictTests::test_covered_ballast_r1_pr_merges

### Requirement: BLOCK on review, PR state and checks
The check SHALL block when the review did not approve the head, the reviewed
head is not a full commit SHA, the PR is not open, is a draft, has a head other
than the reviewed head, or does not tick exactly one risk, and when a required
check of the base branch never reported, any run of it did not pass, or none is
configured.

#### Scenario: Unapproved verdict
- WHEN the verdict is not `approved`
- THEN the verdict is `BLOCK`
- Test: tests/test_merge_check.py::MergeVerdictTests::test_refuses_unapproved_verdict

#### Scenario: Short reviewed head
- WHEN the reviewed head is not a 40-character SHA
- THEN the verdict is `BLOCK`
- Test: tests/test_merge_check.py::MergeVerdictTests::test_refuses_short_reviewed_head

#### Scenario: Head moved after review
- WHEN the PR head differs from the reviewed head
- THEN the verdict is `BLOCK`: the review is stale
- Test: tests/test_merge_check.py::MergeVerdictTests::test_refuses_head_changed_after_review

#### Scenario: Draft or closed PR
- WHEN the PR is a draft or not open
- THEN the verdict is `BLOCK`
- Test: tests/test_merge_check.py::MergeVerdictTests::test_refuses_draft
- Test: tests/test_merge_check.py::MergeVerdictTests::test_refuses_closed

#### Scenario: Body risk
- WHEN the body ticks no risk or more than one
- THEN the verdict is `BLOCK`
- Test: tests/test_merge_check.py::MergeVerdictTests::test_refuses_pr_body_without_exactly_one_risk_ticked

#### Scenario: Missing, failing or pending check
- WHEN a required check never reported, or any run of it did not pass
- THEN the verdict is `BLOCK`
- Test: tests/test_merge_check.py::MergeVerdictTests::test_refuses_missing_failing_or_pending_required_checks

#### Scenario: Rulesets and protection
- WHEN required checks come from legacy protection, or no required check is configured
- THEN the legacy check is required, and an empty set blocks
- Test: tests/test_merge_check.py::MergeVerdictTests::test_reads_required_checks_from_rulesets_and_protection

#### Scenario: Unreadable base rules
- WHEN the rules or branch response is malformed, or the base branch name is malformed
- THEN the verdict is `BLOCK`
- Test: tests/test_merge_check.py::MergeVerdictTests::test_refuses_unreadable_base_rules

#### Scenario: Failed GitHub read with parseable output
- WHEN a `gh` read exits with an error, even with parseable partial output
- THEN the verdict is `BLOCK`, except the failing and pending exit codes of `gh pr checks`
- Test: tests/test_merge_check.py::MergeVerdictTests::test_refuses_failed_github_reads_even_with_parseable_output

### Requirement: BLOCK on the spec delta
The check SHALL recompute the spec hash from the reviewed head's three-dot
`docs/specs/` diff against the target branch and the posted delta's hash from
its comment, never trusting the PR body, and SHALL block an R1 PR without an
approval (a PR changing no spec needs an approved empty delta), a hash that no
approval quotes, a delta or approval edited after the approval, and a stale
delta: a modified or removed entry whose base text no longer matches the target
branch, or an added entry the target branch already has.

#### Scenario: R1 without approval
- WHEN an R1 PR's closing issue has a delta but no approval
- THEN the verdict is `BLOCK`
- Test: tests/test_merge_check.py::MergeVerdictTests::test_r1_without_approval_blocks

#### Scenario: R1 changing no spec
- WHEN an R1 PR changes no spec and only a non-empty delta is approved
- THEN the verdict is `BLOCK`, and `MERGE` once an empty delta is approved
- Test: tests/test_merge_check.py::MergeVerdictTests::test_r1_changing_no_spec_needs_an_approved_empty_delta

#### Scenario: Hash mismatch
- WHEN the head's spec change differs from the approved delta
- THEN the verdict is `BLOCK`
- Test: tests/test_merge_check.py::MergeVerdictTests::test_hash_mismatch_blocks

#### Scenario: Edited after approval
- WHEN the approval was edited, or the delta was edited after the approval
- THEN the verdict is `BLOCK`, while a delta edited before the approval still merges
- Test: tests/test_merge_check.py::MergeVerdictTests::test_edited_approval_or_delta_after_approval_blocks

#### Scenario: Stale delta
- WHEN the target branch changed a modified entry's base text, or already has an added entry
- THEN the verdict is `BLOCK`
- Test: tests/test_merge_check.py::MergeVerdictTests::test_stale_delta_blocks

### Requirement: Changed paths
The check SHALL read every page of the PR's changed files, count a rename
under both names, and block a malformed or incomplete file list.

#### Scenario: Paginated and incomplete file lists
- WHEN an excluded path is on a later page, or fewer files are listed than the PR reports
- THEN the verdict is `HUMAN`, or `BLOCK` for the incomplete list
- Test: tests/test_merge_check.py::MergeVerdictTests::test_reads_every_page_of_files
- Test: tests/test_merge_check.py::MergeVerdictTests::test_refuses_truncated_file_list

#### Scenario: Malformed file entries
- WHEN a file entry is not an object or has a missing, empty or non-string name
- THEN the verdict is `BLOCK`
- Test: tests/test_merge_check.py::MergeVerdictTests::test_refuses_malformed_file_entries

### Requirement: HUMAN
The check SHALL return `HUMAN` for an R2 PR, a disputed risk, a release or
dependency PR, a changed path that is excluded (the ADR-0026 list, `--exclude`,
or a `Human-only:` glob of `project/workflow.md` read from the target branch,
never the PR head), a missing, unreadable or malformed `project/workflow.md`
on the target branch, no closing issue, a closing issue outside the repository
or without one parseable `Risk:` line, a confirmed risk below the highest
closing-issue `Risk:` line and approved risk, a changed path no `Covers:` glob
or `Coverage-exempt:` glob of the target branch matches, and an R0 PR changing
a covered path or modifying or removing a spec entry.

#### Scenario: R2
- WHEN the reviewer confirmed R2
- THEN the verdict is `HUMAN`
- Test: tests/test_merge_check.py::MergeVerdictTests::test_r2_needs_a_human

#### Scenario: Disputed risk
- WHEN the PR ticks one risk and the reviewer confirmed another
- THEN the verdict is `HUMAN`
- Test: tests/test_merge_check.py::MergeVerdictTests::test_disputed_risk_needs_a_human

#### Scenario: Release and dependency PRs
- WHEN the head branch is a Release Please or dependency branch, or the author is a bot
- THEN the verdict is `HUMAN`
- Test: tests/test_merge_check.py::MergeVerdictTests::test_refuses_release_and_dependency_prs

#### Scenario: Excluded paths
- WHEN a changed path is under `.github/`, a changelog, version or release file, a dependency manifest or lockfile, or matches `--exclude`, also as a rename's old name
- THEN the verdict is `HUMAN` and the path is listed
- Test: tests/test_merge_check.py::MergeVerdictTests::test_refuses_excluded_paths
- Test: tests/test_merge_check.py::MergeVerdictTests::test_refuses_project_excluded_paths
- Test: tests/test_merge_check.py::MergeVerdictTests::test_refuses_renames_from_excluded_paths

#### Scenario: Human-only globs from the target branch
- WHEN a PR changes a human-only path, also while removing its glob
- THEN the verdict is `HUMAN`, judged by the target branch's globs
- Test: tests/test_merge_check.py::MergeVerdictTests::test_human_only_globs_come_from_the_target_branch
- Test: tests/test_merge_check.py::MergeVerdictTests::test_ballast_gate_surfaces_need_a_human

#### Scenario: Missing or malformed project workflow
- WHEN the target branch has no `project/workflow.md`, or a key line not of the form `Key: GLOB`
- THEN the verdict is `HUMAN`
- Test: tests/test_merge_check.py::MergeVerdictTests::test_missing_or_malformed_workflow_on_target_needs_a_human

#### Scenario: Risk floor
- WHEN the PR closes no issue, one without a parseable risk, one in another repository, or one whose risk or approved risk is above the confirmed risk
- THEN the verdict is `HUMAN`
- Test: tests/test_merge_check.py::MergeVerdictTests::test_closing_issue_and_its_risk_set_the_floor
- Test: tests/test_merge_check.py::MergeVerdictTests::test_approved_risk_raises_the_floor

#### Scenario: Uncovered path
- WHEN a changed path matches no `Covers:` and no coverage-exempt glob
- THEN the verdict is `HUMAN` and the path is listed
- Test: tests/test_merge_check.py::MergeVerdictTests::test_uncovered_changed_path_needs_a_human

#### Scenario: R0 touching specified behavior
- WHEN an R0 PR changes a covered path, or modifies or removes a spec entry
- THEN the verdict is `HUMAN`
- Test: tests/test_merge_check.py::MergeVerdictTests::test_r0_changing_a_covered_path_needs_a_human
- Test: tests/test_merge_check.py::MergeVerdictTests::test_r0_modifying_or_removing_a_spec_entry_needs_a_human

#### Scenario: Handoff
- WHEN the verdict is `HUMAN`
- THEN the output lists the risky paths, the approved spec and the review findings given with `--finding`
- Test: tests/test_merge_check.py::MergeVerdictTests::test_handoff_lists_paths_spec_and_findings

### Requirement: Merge command
The check SHALL merge only on `MERGE` and only with `--merge`, squash and
pinned with `--match-head-commit` to the reviewed head, SHALL then comment that
it merged under ADR-0027 and that this is not a human approval, SHALL report a
merge GitHub refuses as `BLOCK`, and SHALL refuse to run inside an issue
checkout.

#### Scenario: Merge only on MERGE and on request
- WHEN `--merge` is absent, or the verdict is `HUMAN`
- THEN no merge call is made; with it on `MERGE`, the pinned merge runs and the merge comment names ADR-0027
- Test: tests/test_merge_check.py::MergeVerdictTests::test_merge_only_on_merge_and_with_explicit_flag

#### Scenario: GitHub refuses the merge
- WHEN the merge call fails
- THEN the verdict is `BLOCK`
- Test: tests/test_merge_check.py::MergeVerdictTests::test_merge_refused_by_github_is_reported

#### Scenario: Inside an issue checkout
- WHEN the command runs inside an issue checkout
- THEN it refuses before any GitHub call
- Test: tests/test_merge_check.py::MergeVerdictTests::test_refuses_to_run_inside_an_issue_checkout
