# Test review: 150-autonomous-stop-rule

- Review: implementation recheck after fix cycle 1 (test, agent-provisional)
- Reviewer: claude/claude-opus-5-5, fresh context, not the author of the change
- Reviewed: `AutonomousStopRuleDocumentTests` in `tests/test_governance.py`, `acceptance-evidence.json`, the tasks' test plan including T015, against AC-001 to AC-012, FR-008, FR-009 and FR-012, after fix cycle 1.

## What was checked

**Criterion mapping.** AC-001 to AC-011 still each map to named methods in `acceptance-evidence.json`, every named method exists, and AC-012 keeps an empty list because the trusted checks prove it (ADR-0018). The spec digest still matches `spec.md`.

**Fix-cycle changes.**
- `test_what_still_blocks` now slices the "*Limit outcome instead of a block:*" group and asserts it names "plan review or spec reconciliation" and "failed final `run-checks`". It also asserts the bullet says "A failed `[checks]` command is not a `postcondition`". The new R6 cases from the engineering fix are pinned to their group.
- `test_adr_0010_notes` now expects three notes. It locates the third inside the Consequences section on the sentence "a run that runs out blocks" and asserts that note names "Draft PR". The count went up because content was added; no assertion was loosened.

**Still open.**
- Apart from the new limit-outcome slice, `test_what_still_blocks` still only checks that the fifteen category names appear somewhere in the bullet. If `tamper` or `credential` moved from a "still blocks" group into the material-provisional group, the test would still pass. The limit-group slice shows how to close the gap for the two "still blocks" groups too.
- `test_no_human_approval_wording` covers the ADR-0004 note and the two ADR-0010 Decision notes, but not the new ADR-0010 Consequences note. I read that note and it contains no approval wording, so this is only coverage.

**Execution.**
- `uv run --locked python -m unittest tests.test_governance` passed: 38 tests, OK.
- `uv run --locked ruff check` and `uv run --locked ruff format --check` passed.
- The full suite `uv run --locked python -m unittest tests/test_*.py` timed out in the runner's feedback checks after cycles 0 and 1, and timed out again when I ran it inside this review step. The new tests only read files. AC-012 stays unproven until trusted `run-checks` passes.

## Verdict basis

The fix added real evidence for both engineering fixes without weakening an assertion. The tests prove AC-001 to AC-011 with focused positive and negative checks. The remaining gaps are low-severity strength improvements, plus pending full-gate evidence that the runner decides on.

<!-- ballast-findings: begin -->
## Findings (recorded from the review draft)

- F-001 (low, missing-test, open): test_what_still_blocks checks only that the still-blocks category names appear in the bullet, not their group; moving tamper or credential into the material-provisional group would still pass. Slice the two still-blocks groups as the limit group now is.
- F-002 (low, missing-test, resolved): test_adr_0010_notes now expects three notes and checks the Consequences note names Draft PR; test_what_still_blocks pins plan review, spec reconciliation and the failed final run-checks in the limit-outcome group.
- F-003 (info, missing-test, open): AC-012 evidence is still pending: the full unittest feedback check timed out after cycles 0 and 1 and in this review step; trusted run-checks must pass before the criterion is verified.
- F-004 (low, missing-test, open): test_no_human_approval_wording does not cover the new ADR-0010 Consequences note; reading it shows no approval wording, so only coverage is missing.
<!-- ballast-findings: end -->
