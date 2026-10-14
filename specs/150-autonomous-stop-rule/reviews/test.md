# Test review: 150-autonomous-stop-rule

- Review: implementation recheck after fix cycle 3 (test, agent-provisional)
- Reviewer: claude/claude-opus-5-5, fresh context, not the author of the change
- Reviewed: `AutonomousStopRuleDocumentTests` in `tests/test_governance.py`, `acceptance-evidence.json` and the tasks' test plan, against AC-001 to AC-012, FR-008, FR-009 and FR-012. The diff is taken against the branch base `d215a63`. Fix cycle 3 added "condition (11)" and "stays a Draft" to `test_self_resume`.

## What was checked

**Criterion mapping.** AC-001 to AC-011 each map to named methods in `acceptance-evidence.json`, and every named method exists. AC-012 keeps an empty list because the trusted checks prove it (ADR-0018). The cycle 3 change stays under AC-005's existing method, so the mapping needs no update.

**Fix cycle 3.** `test_self_resume` slices the Self-resume bullet and now pins the new ADR-0019 condition (11) sentence. Deleting that sentence or moving it to another bullet would fail the test. This closes the gap the previous test review raised. `test_adr_0020_links_resolve` covers the new ADR-0019 link. No assertion was weakened, skipped or removed.

**Strength.** Phrases are checked inside their Decision bullet, not anywhere in the file. The limit-outcome group is sliced and pinned. The amendment notes are located inside their named ADR-0004 and ADR-0010 bullets and the ADR-0010 Consequences sentence. Negative checks cover restating the rule in the policy and technical spec, links in the policy paragraph, sibling Issue numbers in the generic template, the unedited ADR-0009 and the recorder's `HUMAN_APPROVAL` pattern.

**Remaining gaps.**
- `test_what_still_blocks` checks that the two still-blocks groups' category names appear in the bullet, not which group holds them.
- `test_no_human_approval_wording` does not include the ADR-0010 Consequences note. The note has no approval wording, so only coverage is missing.

**Execution.**
- `uv run --locked python -m unittest tests.test_governance`: 38 tests, OK.
- `uv run --locked ruff check` and `uv run --locked ruff format --check`: passed.
- The full suite timed out in every feedback check, including the one after cycle 3. Its output shows the agent-step operator-attestation errors `decisions.md` D-001 records, in modules this diff does not touch. AC-012 stays unverified until trusted run-checks or CI pass.

## Verdict basis

The tests prove AC-001 to AC-011 with focused positive and negative checks, now including the condition (11) sentence, and weaken nothing. The remaining items are low-severity strength gaps and the pending full-gate evidence, which the trusted runner decides. Approved.

<!-- ballast-findings: begin -->
## Findings (recorded from the review draft)

- F-001 (low, missing-test, open): test_what_still_blocks checks only that the still-blocks category names appear in the bullet, not their group; moving tamper or credential into the material-provisional group would still pass.
- F-002 (low, missing-test, open): test_no_human_approval_wording does not cover the ADR-0010 Consequences note; reading it shows no approval wording, so only coverage is missing.
- F-003 (info, missing-test, open): AC-012 evidence is pending: the full unittest feedback check timed out after every cycle, and trusted run-checks or CI must pass before the criterion is verified. The condition (11) sentence is now pinned by test_self_resume.
<!-- ballast-findings: end -->
