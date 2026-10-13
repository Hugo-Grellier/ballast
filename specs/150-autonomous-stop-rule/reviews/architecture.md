# Architecture review: 150-autonomous-stop-rule (recheck after fix cycle 1)

- Review: specialists-recheck (architecture, agent-provisional), using the engineering review skill focused on the accepted ADRs and architecture sections the change touches
- Reviewer: claude/claude-opus-5-5, fresh context, not the author of the change
- Run: Autonomous `1d0a2143`, R2
- Fix input: cycle 1, engineering findings PD-0009 F-001 (R6 mapping cases) and F-002 (ADR-0010 Consequences note)
- Diff reviewed: the whole working tree against `09fb427` (`git diff`, `git status`)
- Read against: `spec.md`, `intent.md`, `plan.md`, `research.md`, `contracts/adr-0020.md`, `tasks.md`, `autonomous/record.md`, the previous `reviews/architecture.md` (PD-0010), `AGENTS.md`, `docs/policies/workflow.md`, `docs/policies/engineering.md`, `docs/policies/project/workflow.md`, ADR-0004, ADR-0009, ADR-0010, ADR-0014, ADR-0016, `specs/TECHNICAL-SPEC.md` around the Autonomous status text, the template's Autonomous-runs block table, and `tools/spec_workflow/artifacts.py` `run_checks`. `decisions.md` does not exist.

## Form and lineage

ADR-0020 keeps the repository's form (Status, Risk, Feature, Amends, then Context, Decision, Consequences, Rejected alternatives). Amendment by inline italic note follows the precedent in ADR-0004, ADR-0006 and ADR-0010. ADR-0009 is unedited. The status line describes the merge as the future acceptance, matching ADR-0004 and ADR-0010.

## Fix-cycle items

**Mapping completeness (PD-0010 F-001, PD-0009 F-001).** The *Limit outcome instead of a block* sub-bullet now covers a high or critical finding or non-approved verdict at plan review and spec reconciliation ("their cycles count as spent at once") and a failed final `run-checks`. With `review-finding`, `limit` and the material-provisional group, every block category in the template's table now has a stated outcome, so #151 and #153 can implement without a new decision (SC-003). Resolved.

**ADR-0010 Consequences (PD-0010 F-002).** The sentence "a run that runs out blocks and continues human-gated" now carries an ADR-0020 note saying the run publishes a Draft PR instead. ADR-0010 has no remaining unannotated limit rule. `test_adr_0010_notes` pins three notes. Resolved.

## Remaining and new observations

**Postcondition wording.** The mapping says "A failed `[checks]` command is not a `postcondition`". Today `run_checks` in `artifacts.py` blocks a failed final command with category `postcondition`, and the template table lists `postcondition` under unsafe uncertainty. The ADR is reclassifying it, which is a legitimate decision, but the sentence reads as a description of the present. The Delivery bullet keeps today's blocks until the siblings ship, so there is no live contradiction. Rewording it as a reclassification would make the change clearer to #153.

**Ownership of the new cases.** The Limit outcome bullet names #153 for rendering `unverified`. It does not say which leaf makes plan review, spec reconciliation and failed final `run-checks` publish instead of block. #153 is the natural owner, and the Delivery bullet covers the gap until then, so this is low.

**Self-resume and local fallback (PD-0010 F-003).** Still unstated: ADR-0014's local fallback also triggers on quota failure, and ADR-0020 does not order self-resume against it. #154 can settle it without changing the stop rule.

**Technical spec placement.** The status paragraph sits after "may still block a run." and points to ADR-0020 without restating the rule, so there is no second source of truth.

## Checks

`uv run --locked python -m unittest tests.test_governance` (38 tests), `uv run --locked ruff check` and `ruff format --check` pass locally. The full-suite feedback check timed out in cycles 0 and 1 (run record); the trusted `run-checks` has not run yet.

## Verdict basis

The fix closed both architecture gaps, so the mapping is complete and ADR-0010 has no stale limit rule. What remains is wording and ownership detail that changes no boundary, requirement or risk class. Approved.

<!-- ballast-findings: begin -->
## Findings (recorded from the review draft)

- F-001 (medium, spec-ambiguity, resolved): The Limit outcome sub-bullet now covers a high finding or non-approved verdict at plan review and spec reconciliation and a failed final run-checks.
- F-002 (low, architecture-issue, resolved): ADR-0010's Consequences sentence now carries an ADR-0020 note; test_adr_0010_notes expects three notes.
- F-003 (low, spec-ambiguity, open): ADR-0014's local fallback also triggers on quota failure; ADR-0020 does not order self-resume against it. #154 can settle it without changing the stop rule.
- F-004 (low, spec-ambiguity, open): 'A failed [checks] command is not a postcondition' reads as present fact, while run_checks in artifacts.py blocks a failed final command as postcondition today. Reword it as a reclassification ('is no longer treated as').
- F-005 (low, spec-ambiguity, open): No sibling leaf is named for making plan review, spec reconciliation and failed final run-checks publish instead of block; #153 is the natural owner and the Delivery bullet covers the interim.
<!-- ballast-findings: end -->
