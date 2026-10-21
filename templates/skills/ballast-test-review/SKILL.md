---
name: ballast-test-review
description: Review tests and acceptance evidence for a behavior change, including negative cases, failure paths, integration seams, and regressions.
---

# Test review

Read the issue/spec acceptance criteria, changed behavior, tests and testing policy: Read `docs/policies/testing.md`, plus `docs/policies/project/testing.md` when it exists. Map each material criterion to executable evidence. Check denial and failure paths, overmocking, fixtures, and whether a real database, browser or API seam is needed. Flag a test that cannot fail when the relevant behavior breaks.

For a change to the living specs (`docs/specs/`), record per scenario, from the base and the head checked out in your scratch directory:

- each added or modified scenario: its `Test:` references, the command run, and that the test fails on the base and passes on the head. A test file that does not exist on the base counts as failing there. A test that passes on the base does not enforce the change: `changes_required`.
- each removed scenario: that its tests were removed or no longer assert it.

The merge verdict trusts this record and does not rerun tests on the base, so a scenario without it is missing evidence.

Report `review: tests`, `verdict: approved | changes_required`, covered criteria, the per-scenario record, missing evidence, exact location and required action. Do not request a coverage percentage or tests that merely mirror implementation.
