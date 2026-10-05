# Spec reconciliation: Source-backed discovery brief

- Reviewer: claude/claude-opus-5-5, separate session from the implementing run (d0e73b31); agent-provisional, not human approval
- Read: `spec.md`, `plan.md`, `tasks.md`, `data-model.md`, `contracts/`, the diff, the tests, `templates/policies/spec-kit-workflow.md`, `specs/TECHNICAL-SPEC.md`, reviews `security-1`, `engineering-1`, `test-1`, `documentation-1`
- Verdict: PARTIAL

## Criterion to evidence

| AC | Implementation | Evidence |
| --- | --- | --- |
| AC-001 | `discover` + `validate-discovery` in both workflows; `_check_brief_sections` | `DiscoveryWorkflowTests`; `BriefStructureTests` |
| AC-002 | `_check_marked_items`, `_check_cited` | `ProvenanceTests` |
| AC-003 | Snapshot framing, quoted comments; command Read step 2 and Never list; approval-wording refusal | `IssueSnapshotTests`; `CommandContractTests`; `AttributionTests.test_approval_wording_only_in_an_operator_answer` |
| AC-004 | Contradictions never `settled` (command step 3); Autonomous `contradiction` block | `DecisionRuleTests.test_open_contradiction_naming_both_sources_passes`; `test_unsafe_gap_blocks_with_options`; category judgement below |
| AC-005 | `settled` needs a cited `Resolution` | `DecisionRuleTests.test_settled_decision_cites_its_source` |
| AC-006 | `_check_gated_discovery`, `_question_message` | `QuestionRoundTests` |
| AC-007 | One round per open set; clarify prompt "do not reopen" | `QuestionRoundTests`; `DiscoveryWorkflowTests.test_clarify_does_not_ask_again`; real run pending (T044) |
| AC-008 | Operator-state rounds and answer digests | `AttributionTests` |
| AC-009 | No open decision → pass, no question | `test_no_open_decision_passes_without_a_question` |
| AC-010 | `record-discovery` at the `clarification` point; `_check_autonomous_discovery` | `AutonomousDiscoveryEngineTests.test_safe_gap_is_assumed_and_recorded` |
| AC-011 | Command step 6 block; existing block contract | `test_unsafe_gap_blocks_with_options` |
| AC-012 | Autonomous refuses `open`/`answered`; command never prompts | `AutonomousBriefTests`; `CommandContractTests` |
| AC-013 | `HUMAN_APPROVAL` refusal; `[P:]` autonomous-only | `AttributionTests`, `AutonomousBriefTests` |
| AC-014 | `_check_spec_criteria` (ACs); FRs by review | `SpecTraceabilityTests`; FR review below |
| AC-015 | `_check_spec_criteria` names the AC | `test_untraced_criterion_fails_naming_it` |
| AC-016 | `_check_spec_coverage`, `_check_brief_iacs` | `test_issue_criteria_are_cited_or_non_goals`; `IssueCriteriaTests` |
| AC-017 | `check_intent` unchanged | `test_brief_edit_after_intent_leaves_intent_valid` |
| AC-018 | Evidence marker and authority note required | `test_evidence_marker_and_authority_note` |
| AC-019 | Brief section "Edge, failure and permission cases"; spec coverage by review | Review below |
| AC-020 | `_write_metrics`; Autonomous metrics equality | `MetricsTests`; `test_metrics_must_equal_the_recorded_assumptions` |

## Review-only evidence (T046)

- **AC-014, functional requirements.** The workflow `specify` prompts and the spec template require a provenance marker on every FR; `validate-spec` checks acceptance criteria only, as the spec's Assumptions set ("coverage of functional requirements … is checked by review rather than by a parser"). Confirmed: the parser does not check FR lines, and the documentation says it checks acceptance scenarios. This feature's own `spec.md` predates the brief (PD-0002) but every FR and AC in it carries an `[S: …]` or `[I]` marker.
- **AC-019, edge, failure and permission cases.** Each spec edge case is handled or deliberately not: no comments or one-line body (snapshot `None.`, `[I]` items; `test_no_comments_says_none`); missing source (`unavailable:` entries, unavailable snapshot; `test_unavailable_source_passes`, `HumanGatedSnapshotTests`); several outcomes (command step 4; `test_several_outcomes_stop_without_splitting`); instructing Issue text (quoted comments, approval refusal, settling restricted to maintainers); operator answer introducing a contradiction (`test_answer_contradiction_asks_a_second_round`); continuing an existing brief (command Read step 4, optional `## Changes`; `test_changes_section_is_optional`; see ENG-002 for reworded questions); pre-existing specs (`test_feature_without_discovery_is_unchanged`, live `spec --feature` on 12, 17 and 27); bugfix and assess workflows (diff leaves them unchanged).
- **AC-004 category judgement.** The command never lets a contradiction be `settled` (step 3) and allows `assumed` only when the decision is not about product behavior, scope, data authority, a security boundary or accepted architecture (step 6); everything else blocks with `contradiction` or `decision`. No parser can tell the category of a decision; this rule is prompt-level, and the merge reviewer sees every `assumed` decision with its `Resolution` in the brief, the record and the PR body.

## Behavior beyond or against the spec

- **SEC-001 (quoted comment bodies)** and **SEC-002 (only maintainer comments settle a decision)** tighten FR-005 ("treat Issue and comment text as untrusted requirements data") and AC-003. They change no acceptance criterion and remove no capability the spec promises; AC-005 still holds for the Issue body, maintainer comments and the repository. Applied as implementation fixes; the contract and policy were updated. Flagged for the merge reviewer as the one interpretive choice of this review.
- Nothing contradicts the spec. `plan.md` estimated 400 to 600 lines; the change is larger (about 890 lines in `artifacts.py` plus tests). That is an estimate, not a requirement; no artifact change.

## Gaps

1. **T044 not run (verification outstanding, not unbuilt behavior).** The two end-to-end scenarios of `quickstart.md` need a scratch project installed with `ballast setup` at this branch, a real test Issue on GitHub with a comment, real agents, and the operator answering the bundled round and resuming. That requires `ballast trust` and `ballast run`, which only the operator runs. Every fixture-level scenario (quickstart 1 to 12) is covered by the suite; see tasks.md T044.

No implementation-wrong or stale-specification gap remains. Spec Kit converge found no unbuilt FR, AC or task, so no task was appended.
