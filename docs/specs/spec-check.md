# Spec check

Covers: tools/spec_check.py

`tools/spec_check.py` validates the living specs under `docs/specs/` and
computes the canonical delta hash ([format](../spec-format.md),
[ADR-0027](../adr/0027-spec-approval-living-specs-merge-verdict.md)). It is
read-only and offline.

### Requirement: Spec structure
The checker SHALL accept a spec whose requirements carry a name and a SHALL
statement, and whose scenarios carry a name, a WHEN line, a THEN line and at
least one test reference, and SHALL report one defect per violation otherwise.

#### Scenario: Conforming spec
- WHEN a spec has `Covers:` lines, named requirements with SHALL and complete scenarios
- THEN no defect is reported
- Test: tests/test_spec_check.py::SpecFormatTests::test_valid_spec_passes

#### Scenario: Requirement without SHALL
- WHEN a requirement body has no SHALL
- THEN a "without a SHALL" defect is reported
- Test: tests/test_spec_check.py::SpecFormatTests::test_requirement_without_shall

#### Scenario: Requirement without a name
- WHEN a `### Requirement:` heading has no name
- THEN a "requirement without a name" defect is reported
- Test: tests/test_spec_check.py::SpecFormatTests::test_requirement_without_name

#### Scenario: Unknown level-three heading
- WHEN a `###` heading is not `Requirement: NAME`
- THEN a defect names the expected heading forms
- Test: tests/test_spec_check.py::SpecFormatTests::test_unknown_level_three_heading

#### Scenario: Scenario without WHEN or THEN
- WHEN a scenario lacks a WHEN line or a THEN line
- THEN a defect asks for both lines
- Test: tests/test_spec_check.py::SpecFormatTests::test_scenario_without_when_or_then

#### Scenario: Scenario outside a requirement
- WHEN a `#### Scenario:` heading precedes any requirement
- THEN a "scenario outside a requirement" defect is reported
- Test: tests/test_spec_check.py::SpecFormatTests::test_scenario_outside_requirement

#### Scenario: Duplicate names
- WHEN a file repeats a requirement name, or a requirement repeats a scenario name
- THEN a duplicate defect names it
- Test: tests/test_spec_check.py::SpecFormatTests::test_duplicate_requirement
- Test: tests/test_spec_check.py::SpecFormatTests::test_duplicate_scenario

#### Scenario: Missing or late Covers line
- WHEN a spec has no `Covers:` line, or one after the first requirement
- THEN a defect is reported for it
- Test: tests/test_spec_check.py::SpecFormatTests::test_missing_or_late_covers

### Requirement: Test references
Every `Test: path::Class::method` reference SHALL name a repository-relative
file and a method defined directly in a top-level class of it; any other
reference is a defect.

#### Scenario: Scenario without a test reference
- WHEN a scenario has no `Test:` line
- THEN a "no `Test: path::Class::method` reference" defect is reported
- Test: tests/test_spec_check.py::SpecFormatTests::test_scenario_without_test_reference

#### Scenario: Malformed reference
- WHEN a reference does not have three `::`-separated parts
- THEN a "malformed test reference" defect is reported
- Test: tests/test_spec_check.py::SpecFormatTests::test_malformed_test_reference

#### Scenario: Missing file, class or method
- WHEN the referenced file, class or method does not exist
- THEN a "not found" defect names the missing part
- Test: tests/test_spec_check.py::SpecFormatTests::test_reference_to_missing_file
- Test: tests/test_spec_check.py::SpecFormatTests::test_reference_to_missing_class_or_method

#### Scenario: Reference outside the repository
- WHEN a reference path escapes the repository root
- THEN an "outside the repository" defect is reported
- Test: tests/test_spec_check.py::SpecFormatTests::test_reference_outside_repository

### Requirement: Code fences
Inside a CommonMark code fence, headings and `Covers:` lines SHALL be body
text, and a fence left open at the end of a spec SHALL be a defect.

#### Scenario: Heading inside a fence
- WHEN a fenced block in a scenario holds `###` or `####` lines
- THEN they are body text and no defect is reported
- Test: tests/test_spec_check.py::SpecFormatTests::test_heading_inside_a_code_fence_is_body_text
- Test: tests/test_spec_check.py::SpecFormatTests::test_fence_rules_follow_commonmark

#### Scenario: Fenced Covers line
- WHEN a `Covers:` line appears inside a fence
- THEN it is not read as a glob
- Test: tests/test_spec_check.py::SpecFormatTests::test_fenced_lines_do_not_count_as_covers

#### Scenario: Unclosed fence
- WHEN a fence is still open at the end of the spec
- THEN a "code fence left open" defect is reported
- Test: tests/test_spec_check.py::SpecFormatTests::test_unclosed_fence_is_refused

### Requirement: Command and coverage
The command SHALL exit 0 when every spec conforms and 1 on any defect, SHALL
refuse a tracked file covered by two spec files and any non-flat or non-`.md`
file under `docs/specs/`, and with `--changed-from REF` SHALL report, without
failing, each changed path no `Covers:` glob or coverage exemption matches.

#### Scenario: No specs directory
- WHEN the repository has no `docs/specs/`
- THEN the check exits 0 with a notice
- Test: tests/test_spec_check.py::SpecCheckCommandTests::test_repository_without_specs_passes_with_notice

#### Scenario: Defects fail the command
- WHEN a spec has a defect
- THEN the command exits 1 and prints the defect
- Test: tests/test_spec_check.py::SpecCheckCommandTests::test_valid_specs_pass_and_defects_fail

#### Scenario: Overlapping coverage
- WHEN two spec files' globs both match a tracked file
- THEN the command exits 1 naming the file, while an overlap on untracked paths only passes
- Test: tests/test_spec_check.py::SpecCheckCommandTests::test_overlap_is_checked_over_tracked_files

#### Scenario: Stray file under docs/specs
- WHEN `docs/specs/` holds a subdirectory or a non-Markdown file
- THEN the check exits 1 and `--diff-hash` exits 2 naming it
- Test: tests/test_spec_check.py::SpecCheckCommandTests::test_stray_files_under_specs_are_refused

#### Scenario: Uncovered changed paths
- WHEN paths changed since the merge-base with REF match no `Covers:` glob
- THEN each is printed as `uncovered: PATH`, the exit code stays 0, and `docs/specs/` and `Coverage-exempt:` globs of `project/workflow.md` are exempt
- Test: tests/test_spec_check.py::SpecCheckCommandTests::test_uncovered_changed_paths_are_reported

#### Scenario: Glob semantics
- WHEN a glob uses `*`, `?` or `**`
- THEN `*` and `?` stay within one directory and `**` crosses directories
- Test: tests/test_spec_check.py::SpecCheckCommandTests::test_glob_semantics

### Requirement: Canonical delta hash
The checker SHALL hash a delta document (`--delta-hash`) and the three-dot
`docs/specs/` diff (`--diff-hash`) to the same SHA-256 exactly when they
describe the same behavior change, over normalized text that excludes `Test:`
and `Covers:` lines.

#### Scenario: Document and diff agree
- WHEN a delta document describes the same modified scenario as the Git diff
- THEN both hashes are equal
- Test: tests/test_spec_check.py::DeltaHashTests::test_modified_scenario_hashes_equal
- Test: tests/test_spec_check.py::DeltaHashTests::test_added_spec_file

#### Scenario: Wrong base text
- WHEN a delta document's `Base:` text differs from the real base
- THEN its hash differs from the diff's
- Test: tests/test_spec_check.py::DeltaHashTests::test_base_text_is_part_of_the_hash

#### Scenario: Three-dot diff
- WHEN the target branch gained unrelated spec changes after the fork point
- THEN the diff hash ignores them
- Test: tests/test_spec_check.py::DeltaHashTests::test_three_dot_diff_ignores_target_branch_progress

#### Scenario: Removed requirement
- WHEN a requirement is removed
- THEN it and each of its scenarios are listed as removed entries
- Test: tests/test_spec_check.py::DeltaHashTests::test_removed_requirement_lists_its_scenarios

#### Scenario: What changes the hash
- WHEN a SHALL, WHEN or THEN line or any key element of an entry changes
- THEN the hash changes, while entry order, `Test:` and `Covers:` lines, CRLF, trailing whitespace and rewrapping do not change it
- Test: tests/test_spec_check.py::DeltaHashTests::test_shall_when_then_changes_change_the_hash
- Test: tests/test_spec_check.py::DeltaHashTests::test_key_elements_each_change_the_hash
- Test: tests/test_spec_check.py::DeltaHashTests::test_hash_is_independent_of_entry_order
- Test: tests/test_spec_check.py::DeltaHashTests::test_test_and_covers_lines_are_not_part_of_the_delta
- Test: tests/test_spec_check.py::DeltaHashTests::test_normalization_rules

#### Scenario: Malformed delta document
- WHEN a delta document repeats an entry key, has an empty heading name, leaves a fence open, or has a modified entry without `Base:`
- THEN it is refused
- Test: tests/test_spec_check.py::DeltaHashTests::test_delta_with_duplicate_key_or_empty_name_is_refused
- Test: tests/test_spec_check.py::DeltaHashTests::test_unclosed_fence_in_a_delta_is_refused
- Test: tests/test_spec_check.py::DeltaHashTests::test_modified_entry_without_base_is_refused

#### Scenario: Fenced heading in a delta
- WHEN a delta entry body holds a fenced `##` line
- THEN it stays part of the entry text
- Test: tests/test_spec_check.py::DeltaHashTests::test_heading_inside_a_code_fence_in_a_delta
