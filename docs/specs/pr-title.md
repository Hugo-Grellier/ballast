# PR title

Covers: .github/workflows/pr-title.yml
Covers: templates/github/workflows/pr-title.yml

The PR title workflow requires a Conventional Commit title, because a squash
merge uses it as the commit subject and Release Please builds the changelog
from it. Adopters copy the workflow from `templates/github/workflows/`.

### Requirement: Conventional Commit title
The PR title workflow SHALL pass a title of the form `<type>(optional-scope)[!]: <description>` with a type of feat, fix, docs, refactor, test, build, ci, chore, perf or revert, SHALL refuse any other title and print the title with the expected form, and the adopter template SHALL be byte-identical to the repository workflow.

#### Scenario: Accepted titles
- WHEN the title has an allowed type, an optional scope and `!`, a colon, and a non-blank description
- THEN the workflow step exits 0
- Test: tests/test_pr_title.py::PrTitleWorkflowTests::test_accepts_conventional_titles

#### Scenario: Refused titles
- WHEN the title has an unknown type, a missing colon or description, a blank description, an empty or malformed scope, or a space before the colon
- THEN the workflow step exits 1 and prints `Invalid PR title:` with the title
- Test: tests/test_pr_title.py::PrTitleWorkflowTests::test_refuses_other_titles

#### Scenario: Adopter copy equal
- WHEN the repository and adopter workflow files are compared
- THEN they are identical
- Test: tests/test_pr_title.py::PrTitleWorkflowTests::test_adopter_copy_equals_repository_copy
