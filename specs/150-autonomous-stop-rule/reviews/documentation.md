# Documentation review: 150-autonomous-stop-rule (specialists recheck after fix cycle 3)

- Review: specialists-recheck (documentation, agent-provisional)
- Reviewer: claude/claude-opus-5-5, fresh context, not the author of the change
- Run: Autonomous `1d0a2143`, R2, fix cycles used 3 of 3, so no cycle remains after this review
- Diff reviewed: the whole change against the branch base `d215a63`, meaning commit `1e0a1fe` plus the working tree (`git diff`, `git status`). Fix cycle 3 changed one sentence of ADR-0020's Self-resume bullet, extended `test_self_resume` and added T016 to `tasks.md`.
- Read against: `docs/policies/documentation.md` (no `docs/policies/project/documentation.md` exists), the documentation review skill, `spec.md` AC-001 to AC-011 and FR-009 to FR-011, `plan.md`, `tasks.md`, `decisions.md`, `autonomous/record.md`, the fix input for cycle 3, the previous documentation report, ADR-0004, ADR-0009, ADR-0010, both files numbered ADR-0019, `templates/policies/spec-kit-workflow.md`, `specs/TECHNICAL-SPEC.md` and `README.md`.

## What was checked

**The fix.** The Self-resume bullet now says a self-resume counts as a block resolved during the run for ADR-0019 condition (11), so the run's PR stays a Draft. The sentence is short, links `0019-autonomous-pr-completion.md`, and keeps the earlier statement that the resume is a runner event and never a human decision. It closes the inconsistency I raised last time: a reader of ADR-0019's Consequences ("a resumed run's PR stays a Draft") now finds the same outcome in ADR-0020. That Consequences sentence still says every resume records a `block-resolution` human decision. That stops being literally true once #154 ships, but ADR-0020 is the later record and states the outcome. A note on ADR-0019 is still optional and goes beyond FR-010.

**ADR-0020 as a whole.** Each required element is a bold-led Decision bullet that states a rule. `test_adr_0020_links_resolve` covers the links, and the status line claims no human approval (FR-009, `test_no_human_approval_wording`).

**Policy template, technical spec and README.** Unchanged in this cycle. The template's Stop rule paragraph cites ADR-0020 and keeps today's text in force until a pinned release delivers it. The template's PR-completion text and README's "a resumed run stays a Draft" stay correct after the fix, and now also hold for self-resume. The technical spec's status paragraph only links ADR-0020. None restates the rule.

**ADR numbering.** `docs/adr/` holds two records numbered 0019 (`0019-autonomous-pr-completion.md` from #155 and `0019-feature-local-ui-states.md` from #145). This collision came in upstream and was not caused by this change. ADR-0020 always links the file, so its references are unambiguous. The plain text "ADR-0019" is ambiguous for a reader who does not follow the link.

## Earlier observations, re-checked

Unchanged because the text is unchanged: the ADR-0004 note sits on the Continuation bullet, the closest fit but not an obvious place to look; the installed `docs/policies/spec-kit-workflow.md` shows the Stop rule paragraph only after a release containing it is pinned, which the PR should state; "A failed `[checks]` command is not a `postcondition`" reads as present fact.

## Checks

The run record shows `ruff check` and `ruff format --check` exited 0 after cycle 3 and the full unittest command timed out (`decisions.md` D-001). In this step, `uv run --locked python -m unittest tests.test_governance` ran 38 tests, OK. Trusted `run-checks` has not run.

## Verdict basis

The documents stay one source of truth, consistent with each other and with ADR-0019. The one medium gap from the last review is fixed. Only low and informational observations remain. Approved.

<!-- ballast-findings: begin -->
## Findings (recorded from the review draft)

- F-002 (low, spec-ambiguity, open): Unchanged: the ADR-0004 note sits on the Continuation bullet; ADR-0004 has no bullet on when a run blocks, so it is the closest fit, but a reader may not look there.
- F-003 (info, spec-ambiguity, open): Unchanged: the installed docs/policies/spec-kit-workflow.md is git-ignored and shows the Stop rule paragraph only after a release containing it is pinned; the PR should say so.
- F-004 (low, spec-ambiguity, open): Unchanged: 'A failed [checks] command is not a postcondition' reads as present fact while today's runner and template still treat it as one until #153 ships; 'is no longer treated as' would be clearer.
- F-005 (medium, spec-ambiguity, resolved): Fix cycle 3 states in ADR-0020 Self-resume that a self-resume counts as a resolved block for ADR-0019 condition (11), so the PR stays a Draft; the two ADRs now agree. An ADR-0019 Consequences note stays optional and beyond FR-010.
- F-006 (info, spec-ambiguity, open): Two ADRs are numbered 0019 (#145 and #155), an upstream collision not caused by this change; ADR-0020 links the file so its references are unambiguous, but plain 'ADR-0019' text is not.
<!-- ballast-findings: end -->
