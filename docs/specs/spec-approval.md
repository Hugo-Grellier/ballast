# Spec approval

Covers: tools/spec_approval.py

`tools/spec_approval.py` is the implement dispatch's spec gate
([ADR-0027](../adr/0027-spec-approval-living-specs-merge-verdict.md)): it reads
the issue's risk line, its posted spec delta and the approval from GitHub, and
recomputes the delta hash with `tools/spec_check.py`. The worker and the
coordinator execution call it before an implementation starts.

### Requirement: Risk line
The gate SHALL read exactly one `Risk: R0|R1|R2` line from the issue body,
refuse any other count, and admit an R0 leaf without reading a delta or an
approval.

#### Scenario: R0 leaf
- WHEN the issue body says `Risk: R0`
- THEN the gate admits it with floor R0 and reads no comments
- Test: tests/test_spec_approval.py::SpecApprovalTests::test_r0_needs_no_delta_or_approval
- Test: tests/test_spec_approval.py::DispatchTests::test_require_reads_the_issue_and_paginated_comments

#### Scenario: Missing or repeated risk line
- WHEN the body has no risk line, two of them, or the template placeholder
- THEN the gate refuses: the issue body needs exactly one `Risk:` line
- Test: tests/test_spec_approval.py::SpecApprovalTests::test_issue_needs_exactly_one_risk_line

### Requirement: Approved current delta
For an R1 or R2 leaf, the gate SHALL require a trusted approval comment whose
first line quotes the hash of the latest trusted delta comment, links an
earlier delta comment of this issue carrying that hash, and SHALL return the
risk floor, the higher of the issue's risk and the approved risk.

#### Scenario: Approved delta
- WHEN the latest delta is approved with its hash
- THEN the gate returns the hash, both links and the floor
- Test: tests/test_spec_approval.py::SpecApprovalTests::test_approved_delta_admits_and_exposes_the_floor
- Test: tests/test_spec_approval.py::SpecApprovalTests::test_approved_empty_delta_admits_a_change_to_no_spec
- Test: tests/test_spec_approval.py::DispatchTests::test_require_reads_the_issue_and_paginated_comments

#### Scenario: No delta or no approval
- WHEN no delta is posted, or no approval is posted
- THEN the gate refuses naming which is missing
- Test: tests/test_spec_approval.py::SpecApprovalTests::test_missing_delta_or_approval_refuses
- Test: tests/test_spec_approval.py::DispatchTests::test_require_refuses_without_approval

#### Scenario: Mismatched or superseded hash
- WHEN the approval quotes another hash, or a later delta changed the hash
- THEN the gate refuses until a matching approval is posted
- Test: tests/test_spec_approval.py::SpecApprovalTests::test_mismatched_hash_refuses
- Test: tests/test_spec_approval.py::SpecApprovalTests::test_superseding_delta_needs_a_new_approval

#### Scenario: Refinement with the same hash
- WHEN a later delta changes only `Test:` lines or open questions
- THEN the earlier approval still counts
- Test: tests/test_spec_approval.py::SpecApprovalTests::test_refinement_that_changes_no_entry_keeps_the_approval

#### Scenario: Approval not on the first line
- WHEN the approval line appears later in a comment or inside a delta
- THEN it does not count
- Test: tests/test_spec_approval.py::SpecApprovalTests::test_only_a_first_line_approval_counts

#### Scenario: Untrusted, early or foreign approval
- WHEN the approval's author is not an owner, member or collaborator, precedes the delta it links, or links another issue's comment
- THEN it does not count
- Test: tests/test_spec_approval.py::SpecApprovalTests::test_untrusted_or_misplaced_approvals_never_count

#### Scenario: Delta misstating its hash
- WHEN a delta comment's `Hash:` line differs from the hash of its content
- THEN the gate refuses
- Test: tests/test_spec_approval.py::SpecApprovalTests::test_delta_misstating_its_hash_refuses
