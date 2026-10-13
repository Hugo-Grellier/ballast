# Architecture review: 150-autonomous-stop-rule (specialists recheck after fix cycle 3)

- Review: specialists-recheck (architecture, agent-provisional), using the engineering review skill focused on the accepted ADRs and architecture sections the change touches
- Reviewer: claude/claude-opus-5-5, fresh context, not the author of the change
- Run: Autonomous `1d0a2143`, R2, fix cycles used 3 of 3, so no cycle remains after this review
- Diff reviewed: the whole change against the branch base `d215a63` (#155, ADR-0019), meaning commit `1e0a1fe` plus the working tree (`git diff`, `git status`). Fix cycle 3 changed one sentence of `docs/adr/0020-autonomous-stop-rule.md`, two expected phrases in `test_self_resume` in `tests/test_governance.py` and added T016 to `tasks.md`; the rest of the working tree is the run record and review reports.
- Read against: `spec.md`, `intent.md`, `plan.md`, `tasks.md`, `decisions.md` (D-001), `autonomous/record.md` (Fix loop, Block resolutions), `.specify/workflow-state/fix-input/150-autonomous-stop-rule.json` (cycle 3, engineering F-001), `.specify/workflow-state/required-reviews/150-autonomous-stop-rule.json`, the previous architecture report, `CLAUDE.md`, `docs/policies/workflow.md`, `docs/policies/engineering.md`, `docs/policies/project/workflow.md`, ADR-0004, ADR-0009, ADR-0010, ADR-0014, ADR-0019 (`0019-autonomous-pr-completion.md`) and `specs/TECHNICAL-SPEC.md` around the Autonomous status text.

## What changed in fix cycle 3

The Self-resume bullet now ends: a self-resume counts as a block resolved during the run for ADR-0019 condition (11), so the run's PR stays a Draft. I checked ADR-0019's condition (11) ("no block resolved during the run") and its Consequences ("Every resume records a `block-resolution` human decision, so condition (11) keeps a resumed run's PR a Draft"). The new sentence keeps that outcome for an unattended usage-limit resume. It does so without making the runner event a human decision, because condition (11) is about a resolved block, not about who resolved it. The link points at `0019-autonomous-pr-completion.md`, the right one of the two files numbered 0019. #154 no longer has to choose, which meets SC-003.

## Whole change, re-checked

- Form and lineage: ADR-0020 keeps the repository's ADR form and amends ADR-0004 and ADR-0010 with inline italic notes. ADR-0009 is not edited. The technical spec and the policy template only point to ADR-0020.
- Mapping against ADR-0019: limit-outcome PRs fail (9), leftover findings fail (7), a non-approved plan review or reconciliation fails (6), a failed final `run-checks` fails (8), a material provisional decision fails (10), and now a self-resume fails (11). None of the new publish-instead-of-block paths can reach ready for review.
- FR-012: no file under `tools/`, `.agents/` or `.github/` changed. The change is documentation and document tests only.
- The ADR-0019 Consequences sentence "Every resume records a `block-resolution` human decision" is literally no longer true once #154 ships, but ADR-0020's new sentence keeps its effect, and ADR-0020 is the later, linked record. This is a wording observation, not a conflict.

## Earlier observations, re-checked

The three low items from earlier reviews are unchanged because their text is unchanged: the order of self-resume and the ADR-0014 local fallback is unstated; "A failed `[checks]` command is not a `postcondition`" reads as present fact; no leaf is named for making plan review, spec reconciliation and a failed final `run-checks` publish instead of block. None changes a boundary or requirement, and each can be settled by #153 or #154.

## Checks

The run record's Fix loop shows `ruff check` and `ruff format --check` exited 0 after cycle 3, and the full unittest command timed out again. `decisions.md` D-001 traces this to the ledger tests' operator-attestation guard inside an agent step, which this diff does not touch. In this review step, `uv run --locked python -m unittest tests.test_governance` ran 38 tests, OK. Trusted `run-checks` has not run, so AC-012 is still unverified. Because no fix cycle remains, the runner treats the timed-out check as an exhausted limit. That decision belongs to the runner, not to this review.

## Verdict basis

The architecture gap I accepted provisionally in the last review is fixed by the sentence that review asked for. The change is consistent with ADR-0004, ADR-0010 and ADR-0019 and keeps one source of truth. Only low observations remain. Approved.

<!-- ballast-findings: begin -->
## Findings (recorded from the review draft)

- F-003 (low, spec-ambiguity, open): Unchanged: ADR-0014's local fallback also triggers on quota failure and ADR-0020 does not order self-resume against it. #154 can settle it without changing the stop rule.
- F-004 (low, spec-ambiguity, open): Unchanged: 'A failed [checks] command is not a postcondition' reads as present fact while today's runner still blocks a failed final command as postcondition; 'is no longer treated as' would be clearer.
- F-005 (low, spec-ambiguity, open): Unchanged: no sibling leaf is named for making plan review, spec reconciliation and a failed final run-checks publish instead of block; #153 is the natural owner and the Delivery bullet covers the interim.
- F-006 (medium, architecture-issue, resolved): Fix cycle 3 added to Self-resume that a self-resume counts as a block resolved during the run for ADR-0019 condition (11), so the PR stays a Draft; test_self_resume checks the phrases.
<!-- ballast-findings: end -->
