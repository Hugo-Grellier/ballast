# Test review 1: Source-backed discovery brief

- review: tests
- Reviewer: claude/claude-opus-5-5, separate session from the implementing run (d0e73b31); agent-provisional, not human approval
- Read: `docs/policies/testing.md`, `docs/policies/project/testing.md`, `spec.md` AC-001 to AC-020, `tasks.md` acceptance coverage, the new and changed tests
- Verdict: approved

## Criterion to evidence

| AC | Executable evidence |
| --- | --- |
| AC-001 | `DiscoveryWorkflowTests.test_feature_discovers_after_the_scope_gate`, `test_autonomous_records_then_validates_discovery`; `BriefStructureTests.test_each_required_section_is_required`, `test_each_need_item_is_required` |
| AC-002 | `ProvenanceTests` (unmarked item named, cited path must exist, link is not a marker, unavailable source) |
| AC-003 | `IssueSnapshotTests.test_comments_are_rendered_oldest_first_as_data`, `test_comment_bodies_cannot_forge_a_header`; `CommandContractTests.test_snapshot_is_untrusted_requirements_data`, `test_only_maintainer_comments_settle_a_decision`; approval-wording refusals |
| AC-004 | `DecisionRuleTests.test_open_contradiction_naming_both_sources_passes`; `AutonomousDiscoveryEngineTests.test_unsafe_gap_blocks_with_options` (`contradiction` block); category judgement by review (reconciliation) |
| AC-005 | `DecisionRuleTests.test_settled_decision_cites_its_source`; `QuestionRoundTests.test_no_open_decision_passes_without_a_question` |
| AC-006 | `QuestionRoundTests.test_open_decisions_are_asked_together_once`, `test_rerun_before_answering_asks_the_same_round` |
| AC-007 | `DiscoveryWorkflowTests.test_clarify_does_not_ask_again` (prompt text); one round in `QuestionRoundTests` |
| AC-008 | `AttributionTests` (answer before a round, outside the round, empty answer, answered status, digests, unchanged answer, operator marker) |
| AC-009 | `QuestionRoundTests.test_no_open_decision_passes_without_a_question` |
| AC-010 | `AutonomousDiscoveryEngineTests.test_safe_gap_is_assumed_and_recorded` (real engine: record.md and PR body); `AutonomousBriefTests.test_assumed_decision_needs_a_recorded_assumption`; `test_discovery_assumption_is_a_clarification` |
| AC-011 | `test_unsafe_gap_blocks_with_options`; `DecisionRuleTests.test_blocking_decision_never_passes` |
| AC-012 | `AutonomousBriefTests.test_open_answered_and_operator_markers_fail`; `CommandContractTests.test_never_prompts_answers_or_claims_approval` |
| AC-013 | `test_approval_wording_only_in_an_operator_answer`, `test_approval_wording_fails_even_in_an_answer`, `test_provisional_marker_is_autonomous_only` |
| AC-014 | `SpecTraceabilityTests.test_untraced_criterion_fails_naming_it`, `test_scenario_without_an_id_fails`; FR markers by review |
| AC-015 | `test_untraced_criterion_fails_naming_it` |
| AC-016 | `test_issue_criteria_are_cited_or_non_goals`; `IssueCriteriaTests` |
| AC-017 | `test_brief_edit_after_intent_leaves_intent_valid` |
| AC-018 | `BriefStructureTests.test_evidence_marker_and_authority_note` |
| AC-019 | Review only (spec Assumptions); see the reconciliation report |
| AC-020 | `MetricsTests`, `AutonomousBriefTests.test_metrics_must_equal_the_recorded_assumptions` |

Denial and failure paths have their own tests: malformed state, symlinked state, deleted brief after `ran`, write outside the feature, unreadable Issue and missing `gh` at a human-gated start, the Autonomous start still failing closed, an oversized snapshot. The engine cases drive the real Spec Kit engine with the fake agent and confinement, which is the right seam for the workflow ordering; the validators are exercised as subprocesses (`run_check`), not mocked.

## Findings

- TST-001 (high, missing test evidence): `AutonomousDiscoveryEngineTests.test_safe_gap_is_assumed_and_recorded` failed (see ENG-001). Required: fix the fixture, keep the check.
- TST-002 (low): the CI-skipped tests (systemd user session, Codex sandbox, Spec Kit CLI) must run once for a workflow-file change (`docs/policies/project/testing.md`). Required: run the full suite on this host and confirm no test skipped.
- TST-003 (info): AC-007 and the "no re-ask" rule are prompt text checked by string assertions; only a real agent run (T044) shows the behavior. Not fixable by a unit test.
- TST-004 (info): `discovery_fixtures.snapshot_text` renders comments unquoted, unlike the runner after SEC-001. `test_criteria_heading_inside_a_comment_is_ignored` stays meaningful (it is the stronger case: an unquoted heading is still ignored). No change.

## Resolution

- TST-001: fixed (fixture cites existing files); both engine tests pass.
- TST-002: done. The full suite ran on this host (systemd user session, Codex CLI, Spec Kit CLI, bwrap) with no skipped test; counts in tasks.md T042/T043.
- TST-003, TST-004: no change; T044 stays open for the real-agent run.

- Verdict: approved
