# Documentation review: 150-autonomous-stop-rule (recheck after fix cycle 1)

- Review: specialists-recheck (documentation, agent-provisional)
- Reviewer: claude/claude-opus-5-5, fresh context, not the author of the change
- Run: Autonomous `1d0a2143`, R2
- Fix input: cycle 1, engineering findings PD-0009 F-001 (R6 mapping cases) and F-002 (ADR-0010 Consequences note)
- Diff reviewed: the whole working tree against `09fb427` (`git diff`, `git status`)
- Read against: `docs/policies/documentation.md` (no `docs/policies/project/documentation.md` exists), the documentation review skill, `spec.md` AC-001 to AC-011, `plan.md`, `tasks.md`, `autonomous/record.md`, the previous `reviews/documentation.md` (PD-0011), ADR-0004, ADR-0009, ADR-0010, `templates/policies/spec-kit-workflow.md` and `specs/TECHNICAL-SPEC.md`.

## What was checked

**ADR-0020.** Each required element (stop rule, trusted author, limit outcome, self-resume, residual risk) is a lead-bolded Decision bullet that states a rule, plus the Chat-runs, Invariants and Delivery bullets. The new mapping cases (plan review, spec reconciliation, failed final `run-checks`) read clearly and fit the existing sub-bullet structure. Relative links resolve (`test_adr_0020_links_resolve`). The status line claims no human approval.

**Amendment notes.** ADR-0004 has one note, on the Continuation bullet. ADR-0010 now has three: on Autonomous resume, on Bounded fix loop and, new in this cycle, on the Consequences sentence "a run that runs out blocks and continues human-gated". The original text is kept in each case, so the history stays readable. A reader of ADR-0010 no longer finds two conflicting limit rules (PD-0011 F-001 resolved).

**Policy template and technical spec.** The template's **Stop rule** paragraph sits after the block table, cites "ADR-0020 in the Ballast repository" in plain text (the template's form for installed copies), says later releases deliver it and that the current section applies until then, and restates nothing. The technical spec's status paragraph links ADR-0020 and names #151 to #154. Neither is a second source of truth.

**Other places.** The fix touched only ADR-0010 and ADR-0020 among public documents. README, `docs/*.md` and `specs/PRODUCT-SPEC.md` still hold no separate statement of the stop, limit or `ready-for-agent` rules (unchanged from the first review).

## Remaining observations

- The ADR-0004 note sits on the Continuation bullet. ADR-0004 has no bullet about when a run blocks, so it is the closest fit, but a reader looking for the block rule may not look there (PD-0011 F-002, unchanged).
- The installed `docs/policies/spec-kit-workflow.md` is git-ignored and shows the Stop rule paragraph only after a release containing it is pinned; the PR should say so (PD-0011 F-003, plan-review F-003).
- "A failed `[checks]` command is not a `postcondition`" reads as a statement about today, while today's runner and the template table still treat it as one until #153 ships. The Delivery bullet resolves the conflict, but the wording could say "is no longer treated as".

## Checks

`uv run --locked python -m unittest tests.test_governance` (38 tests), `uv run --locked ruff check` and `ruff format --check` pass locally; the full-suite feedback check timed out in cycles 0 and 1 (run record).

## Verdict basis

The fix removed the only documentation conflict (the unannotated ADR-0010 Consequences limit sentence). What remains is placement and wording detail and a PR note. Approved.

<!-- ballast-findings: begin -->
## Findings (recorded from the review draft)

- F-001 (low, spec-ambiguity, resolved): ADR-0010's Consequences sentence now carries an ADR-0020 note, so a reader no longer finds two conflicting limit rules.
- F-002 (low, spec-ambiguity, open): The ADR-0004 note sits on the Continuation bullet; ADR-0004 has no bullet on when a run blocks, so it is the closest fit, but a reader may not look there.
- F-003 (info, spec-ambiguity, open): The installed docs/policies/spec-kit-workflow.md is git-ignored and shows the Stop rule paragraph only after a release containing it is pinned; the PR should say so.
- F-004 (low, spec-ambiguity, open): 'A failed [checks] command is not a postcondition' reads as present fact while today's runner and template still treat it as one until #153 ships; say 'is no longer treated as'.
<!-- ballast-findings: end -->
