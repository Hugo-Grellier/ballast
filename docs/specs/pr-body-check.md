# PR body check

Covers: tools/pr_body.py
Covers: templates/github/scripts/pr_body.py
Covers: templates/github/workflows/pr-body.yml
Covers: templates/github/pull_request_template.md
Covers: .github/workflows/pr-body.yml
Covers: .github/pull_request_template.md

`tools/pr_body.py` checks a PR body against the PR template; CI runs it on
the pull request event payload. Adopters get an identical copy under
`templates/github/`.

### Requirement: Template structure
The check SHALL report every template `##` section missing from the body, a
missing `Closes #N` or `Refs #N` issue link, and any number of ticked risk boxes
other than one; content inside HTML comments SHALL not count.

#### Scenario: Complete body
- WHEN a body has every section, an issue link and one ticked risk box
- THEN no problem is reported
- Test: tests/test_pr_body.py::PrBodyTests::test_complete_body_passes

#### Scenario: Missing section
- WHEN any one template section is missing
- THEN it is reported as `missing section: ## NAME`
- Test: tests/test_pr_body.py::PrBodyTests::test_each_missing_heading_is_reported

#### Scenario: Missing issue link
- WHEN the body has no `Closes #N` or `Refs #N`
- THEN a missing issue link is reported
- Test: tests/test_pr_body.py::PrBodyTests::test_missing_issue_link

#### Scenario: Zero or several risk boxes
- WHEN no risk box or more than one is ticked
- THEN the check asks for exactly one
- Test: tests/test_pr_body.py::PrBodyTests::test_risk_boxes

#### Scenario: Commented-out content
- WHEN the issue link is only inside an HTML comment
- THEN it does not count
- Test: tests/test_pr_body.py::PrBodyTests::test_commented_out_content_does_not_count

### Requirement: R2 approval link
When R2 is ticked, the Risk section SHALL contain a link to a GitHub issue or
PR comment or review; R0 and R1 SHALL need none.

#### Scenario: R2 with and without a link
- WHEN R2 is ticked
- THEN an `issuecomment` or `pullrequestreview` link in the Risk section passes, and a missing or non-comment link is reported
- Test: tests/test_pr_body.py::PrBodyTests::test_r2_needs_an_approval_comment_link

#### Scenario: Link outside the Risk section
- WHEN the approval link appears only in another section
- THEN R2 is still reported as lacking it
- Test: tests/test_pr_body.py::PrBodyTests::test_approval_link_outside_risk_section_does_not_count

#### Scenario: R0 and R1
- WHEN R0 or R1 is ticked without a link
- THEN no problem is reported
- Test: tests/test_pr_body.py::PrBodyTests::test_r0_and_r1_need_no_approval_link

### Requirement: Command line
The command SHALL read the body from `--body-file` or from the
`pull_request` of a GitHub event payload, exit 0 on a conforming body, 1 on a
defect and 2 on an event without a pull request, treating CRLF as LF.

#### Scenario: Body file and event payload
- WHEN the body comes from a file or an event payload, including a null body
- THEN a conforming body exits 0 and a defective or empty one exits 1 with the defect on stderr
- Test: tests/test_pr_body.py::PrBodyTests::test_cli_body_file_and_event_payload

#### Scenario: CRLF body
- WHEN the body uses CRLF line endings
- THEN it passes like its LF form
- Test: tests/test_pr_body.py::PrBodyTests::test_crlf_event_payload_passes

#### Scenario: Event without a pull request
- WHEN the event payload has no `pull_request`
- THEN the command exits 2
- Test: tests/test_pr_body.py::PrBodyTests::test_event_without_pull_request_is_refused

### Requirement: Workflow and adopter copies
The adopter copies of the script and the PR template SHALL be byte-identical
to the source, and both PR body workflows SHALL read the body from the event
file and skip Dependabot and Release Please PRs.

#### Scenario: Adopter copies
- WHEN the template copies are compared with the source
- THEN they are identical and the adopter workflow passes `$GITHUB_EVENT_PATH`, never interpolating the body
- Test: tests/test_pr_body.py::PrBodyTests::test_adopter_copies_match_the_source

#### Scenario: Generated PRs
- WHEN a PR is opened by Dependabot or from a `release-please--` branch
- THEN both workflows skip the check
- Test: tests/test_pr_body.py::PrBodyTests::test_generated_prs_are_skipped
