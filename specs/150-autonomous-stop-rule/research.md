# Research: Autonomous runs stop only for in-run authority changes

Each entry records a design decision for [plan.md](plan.md). Sources are the spec, the discovery brief, the Issue #150 snapshot, ADR-0004, ADR-0009, ADR-0010, ADR-0016, ADR-0019, the constitution, `templates/policies/spec-kit-workflow.md`, `specs/TECHNICAL-SPEC.md`, `tests/test_governance.py` and `.gitignore`. Every decision here is agent-provisional; merging the PR is the only human approval.

## R1. Which file carries the workflow policy reference

- **Decision**: edit `templates/policies/spec-kit-workflow.md`, the source of the policy. `docs/policies/spec-kit-workflow.md` is not edited.
- **Rationale**: `.gitignore` ignores `docs/policies/*.md`; that copy is installed by `ballast setup` from the pinned release (BL-INV-001, CLAUDE.md invariant). An edit there would not be in the PR and would be overwritten. AC-010 names the installed path a reader opens; it shows the reference once a release containing the template change is pinned. Feature 142 changed the same template for the same reason.
- **Alternatives**: editing the installed copy (lost, not committed); editing both (a second source of truth).

## R2. How the policy cites ADR-0020

- **Decision**: cite it as plain text, "ADR-0020 in the Ballast repository", the form the template already uses for ADR-0003, ADR-0005, ADR-0006, ADR-0018 and ADR-0019.
- **Rationale**: the template ships to every project, where `docs/adr/0020-…` does not exist; a relative link would break there, which is why `test_links_resolve` skips `templates/`. The shipped text stays generic (constitution principle 7), so it names no Ballast Issue number: it says later Ballast releases deliver the behavior. AC-010's "links" is read as this established citation form; the spec is not edited, because that would change the spec digest PD-0005 recorded. The plan review may confirm or ask for a spec wording fix.
- **Alternatives**: an absolute GitHub URL (no precedent in the template, and it ties shipped text to one forge URL); a relative link (broken in projects).

## R3. Where the policy reference goes and what it says

- **Decision**: one short paragraph, **Stop rule**, right after the block-class table in [Autonomous runs](../../templates/policies/spec-kit-workflow.md#autonomous-runs). It says ADR-0020 in the Ballast repository is the authority for when an Autonomous run stops, that later Ballast releases deliver it, and that the blocks, limits and resume described in this section apply until then. It does not restate the rule's conditions.
- **Rationale**: the block table is where a reader looks for "when does a run stop". Saying the current text still applies avoids a policy that describes behavior the shipped tools do not have (FR-011, FR-012).
- **Alternatives**: restating the rule in the policy (second source of truth); a note in each of Blocks, Limits and Resume (three places to keep in sync).

## R4. Where the technical spec references ADR-0020

- **Decision**: a new `**Status (#150, Autonomous stop rule):**` paragraph right after the paragraph that ends "Technical failures, conflicts, exhausted limits and unavailable authority may still block a run." (the Autonomous status text near the Chat-mode status). It links `../docs/adr/0020-autonomous-stop-rule.md`, says the decision is accepted and agent-provisional until the PR merges, and that #151–#154 deliver it. §37 (Human intervention contract) and the existing paragraph are not rewritten.
- **Rationale**: matches the `**Status (#20 …)**` and `**Status (#23 …)**` precedent; one link keeps the ADR the single authority (AC-011, FR-011). The technical spec is Ballast-only, so Issue numbers and a relative link are fine there.
- **Alternatives**: rewriting §37 and the "may still block" sentence now (describes undelivered behavior and restates the rule).

## R5. ADR file, status and header

- **Decision**: `docs/adr/0020-autonomous-stop-rule.md`, title "ADR-0020: Autonomous runs stop only for authority that takes effect before merge". Header lines:
  - Status: accepted (2026-10-13, with the change for #150), agent-provisional in Autonomous run `1d0a2143` until the operator merges the PR, which is the human approval that accepts it (FR-009, D-01, ADR-0004's form).
  - Risk: R2 (agent authority, the launcher trust model, accepted architecture).
  - Feature: link to `specs/150-autonomous-stop-rule/spec.md`.
  - Amends: ADR-0004 (when a run blocks; recovery from a block) and ADR-0010 (resume after a provider usage limit; the limit block).
- **Rationale**: AC-001 fixes the number, form and Amends targets; ADR-0019 shows the Risk line. The wording is checked against `HUMAN_APPROVAL` in `tools/spec_workflow/autonomy.py`: no "human-approved" or "approved by the operator".
- **Alternatives**: "proposed" (D-01 option B, rejected in the spec).

## R6. How the stop rule classifies today's blocks

- **Decision**: the ADR's Decision lists today's block categories (from the policy's block table) under the rule, so each sibling leaf can name what it changes (SC-003):
  - **Keep blocking, pre-merge authority**: `credential`, `permission`, `forge`, `ineligible`, and any undeclared or unauthorized privileged action (ADR-0016 kinds such as `secret-provisioning` and `external-write`).
  - **Keep blocking, runner-enforced invariant**: `tamper`, `unfinished-step`, `postcondition` and any protected-input change (BL-INV-002, -003, -005).
  - **Become a material provisional decision**: `decision` (no safe default) and `contradiction` with accepted intent or architecture, since neither takes effect before merge.
  - **Get the limit outcome**: `limit` in every category, and `review-finding` once the fix cycles are spent (it already reports as an exhausted limit).
  - **Not a decision, outside the rule**: `interrupted` and `upstream-sync` are technical stops with no decision to make; they keep today's recovery, as does a provider usage limit except that the runner resumes it itself.
- **Rationale**: follows directly from the rule's two conditions and the spec's edge cases; FR-002 governs decisions, and a killed runner or an unsynchronizable branch offers none.
- **Spec ambiguity flagged for plan review**: FR-002 says a run "blocks only for" the two conditions; this plan reads it as covering decisions, leaving the two technical stops in place. If the plan review disagrees, the alternative is to state that #151–#154 decide them, which still keeps the ADR within FR-012.
- **Alternatives**: leave the mapping out (siblings would need a new decision, failing SC-003).

## R7. Amendment notes on ADR-0004 and ADR-0010

- **Decision**: an italic `*Amended by [ADR-0020](0020-autonomous-stop-rule.md): …*` note, as ADR-0006 carries for ADR-0019, appended to:
  - ADR-0004's "Continuation as a gate-only workflow" bullet, naming the narrowed stop rule (AC-007);
  - ADR-0010's "Autonomous resume" bullet and its "Bounded fix loop" bullet: resume after a provider usage limit needs no `block-resolution` record, and an exhausted limit publishes a Draft PR instead of blocking (AC-008).
  Status lines and decisions of both ADRs are otherwise unchanged; ADR-0009 is not edited (FR-007).
- **Rationale**: the constitution's governance and §55 forbid rewriting an accepted ADR to hide history; a note keeps the old text and points forward.
- **Alternatives**: a superseding ADR (most of ADR-0004 and ADR-0010 still holds).

## R8. Verification

- **Decision**: add `AutonomousStopRuleDocumentTests` to `tests/test_governance.py`, following `FeatureUiStatesDocumentTests`. It checks the ADR header, the five elements, the Chat and invariant statements, the amendment notes, that ADR-0009 has no ADR-0020 reference, the policy and technical-spec references, that the policy does not restate the rule, the absence of `HUMAN_APPROVAL` matches, and that ADR-0020's relative links resolve. The fast gate is the end-to-end check (AC-012).
- **Rationale**: constitution principle 8 asks for executable evidence; FR-012 forbids runner, validator, skill and workflow code, not tests. Phrase checks pin the required statements without fixing the prose.
- **Alternatives**: manual reading only (no regression guard).

## R9. Risk recheck

- **Decision**: R2 stands. The change amends accepted ADRs on agent authority and the launcher trust model (`docs/policies/project/workflow.md#r2-boundaries`), though it changes no executed code. No privileged action before merge.
