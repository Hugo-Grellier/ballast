# Plan review: 150-autonomous-stop-rule

- Review: plan (engineering review of the plan, agent-provisional)
- Reviewer: claude/claude-opus-5-5, fresh context, not the author of the plan
- Artifacts reviewed: `plan.md`, `research.md` (R1–R9), `data-model.md`, `contracts/adr-0020.md`, `quickstart.md`, against `spec.md`, `intent.md` (PD-0005), `discovery.md` and `autonomous/record.md`. `tasks.md` and `decisions.md` do not exist yet; that is expected at this point.
- Policies and sources read: `AGENTS.md`, the engineering review skill, the constitution, ADR-0004, ADR-0010, the Autonomous runs section of `templates/policies/spec-kit-workflow.md`, the Autonomous status text of `specs/TECHNICAL-SPEC.md`, `tests/test_governance.py`, `HUMAN_APPROVAL` in `tools/spec_workflow/autonomy.py` and `.gitignore`.

## What was checked

**Requirement coverage.** Every FR-001 to FR-012 and AC-001 to AC-012 maps to a row of the contract, and every AC has a quickstart scenario and a planned test assertion. The five required ADR elements (stop rule, trusted author, limit outcome, self-resume, residual risk), the Chat statement, the invariant statement and the delivery statement are each a separate contract bullet.

**Repository claims.** I confirmed these against the tree:
- `.gitignore` ignores `docs/policies/*.md`, so R1 is right to edit the template and not the installed copy.
- The template already cites ADRs as plain text in the form "ADR-NNNN in the Ballast repository" (ADR-0003, ADR-0005, ADR-0018, ADR-0019). `test_links_resolve` skips `templates/`. R2 is consistent with that.
- The technical spec paragraph that ends "may still block a run." exists, and a `**Status (#20, Chat mode):**` paragraph follows it. The R4 placement and form match the precedent.
- `FeatureUiStatesDocumentTests` and `test_adr_0010_amends_adr_0004` exist. Their phrase-check and link-resolution pattern is the one R8 reuses.
- `HUMAN_APPROVAL` matches "human-approved" and "approved by the operator/human/user". The planned ADR-0020 status wording in R5 avoids both phrases.
- The constitution IDs the plan cites (BL-INV-002, -003, -005, -006) are correct. The plan does not amend any of them, as FR-008 requires.

**Source authority.** ADR-0020 is the single authority. The policy template and the technical spec only point to it, and the contract has a negative check that the template does not repeat the phrase "takes effect before merge". ADR-0004 and ADR-0010 get forward notes and are not rewritten, which follows the constitution's governance rule. ADR-0009 stays untouched, and a test checks that.

**Scope.** No runner, validator, skill or workflow code changes (FR-012). The new governance test is not one of those excluded kinds. The quickstart's `git diff --stat` check bounds the paths the change may touch.

**Authority boundaries.** Credentials, permissions, forge access, eligibility, undeclared privileged actions, tamper, unfinished steps and protected inputs all stay blocking. Trusted-author data comes only from operator-controlled sources. Self-resume keeps mode, risk, limits and integrations. Nothing grants an agent pre-merge authority, so BL-INV-003 holds. Every decision stays agent-provisional and the merge remains the single approval, so BL-INV-006 holds.

**Flagged interpretations.**
- R1/R2 reads AC-010's "links" as the template's established citation form. That reading is sound. The PR should still note that the installed `docs/policies/` copy shows the reference only after a release with the template change is pinned.
- R6 keeps `interrupted` and `upstream-sync` outside the stop rule. That is consistent with FR-002, because neither offers a decision.

**Gaps in R6's category mapping (SC-003).** R6 sorts today's block categories so each sibling leaf can name what it changes. Two cases are left unclassified or ambiguous:
1. Plan review and spec reconciliation still use a stricter rule today: a high finding or a non-approved verdict blocks at once, with no fix cycles. R6 maps `review-finding` to the limit outcome only "once the fix cycles are spent". It does not say what happens at those two points.
2. R6 keeps every `postcondition` failure blocking as a runner-enforced invariant (BL-INV-005). It does not say whether a failed final `run-checks` counts as such a postcondition. If it does, the run blocks. If it does not, the run publishes a Draft PR listing the failed check, as the limit outcome already does.

The ADR author can settle both in the Decision mapping during implementation, without changing the spec.

**Amendment completeness.** R7 adds notes to ADR-0010's "Autonomous resume" and "Bounded fix loop" bullets. ADR-0010's Consequences still says "a run that runs out blocks and continues human-gated", and no planned note covers that sentence. A reader would then still find the replaced limit rule there.

**Verification.** The planned test pins the required statements as phrases without fixing the prose. It also checks for no approval wording, that relative links resolve and that ADR-0009 is unchanged. The fast gate (AC-012) is the end-to-end check. Together these are proportionate evidence for a documentation-only change.

## Verdict basis

The design meets the approved spec. It respects the constitution and the accepted ADR process, and it does not expand scope. The remaining items are a mapping ambiguity and a stale-sentence risk. Both can be fixed in the ADR text during implementation, and the implementation and documentation reviews will check them. None of them changes a requirement, a boundary or the risk class.

<!-- ballast-findings: begin -->
## Findings (recorded from the review draft)

- F-001 (medium, spec-ambiguity, accepted-provisionally): R6's mapping leaves two cases open: a high finding or non-approved verdict at plan review or spec reconciliation (today it blocks at once, with no fix cycle), and whether a failed final run-checks is a blocking postcondition or gets the limit outcome. Sibling leaves #151 and #153 would otherwise need a new decision (SC-003). The ADR author can add both to the Decision mapping during implementation without a spec change, and the implementation and documentation reviews will check them.
- F-002 (low, architecture-issue, open): R7 notes only ADR-0010's resume and fix-loop bullets. Its Consequences sentence 'a run that runs out blocks and continues human-gated' stays without a note, which leaves a stale limit rule in place (FR-010 intent). Add an amendment note there too.
- F-003 (info, spec-ambiguity, open): AC-010 names the installed docs/policies/spec-kit-workflow.md, which is git-ignored. The plan verifies the template instead, using the plain-text citation form. That is sound, but the PR should state that the installed copy shows the reference only after a release with the template change is pinned.
<!-- ballast-findings: end -->
