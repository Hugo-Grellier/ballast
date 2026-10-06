# Implementation review 1: tests

- Reviewer: Claude Opus 5.5, the driving agent (same provider and session as the author; not independent).
- Date: 2026-10-06
- Skill: `.agents/skills/ballast-test-review/SKILL.md`
- Scope: the new `tests/test_autonomous_recovery.py` and the extensions of `test_autonomy`, `test_autonomous_artifacts`, `test_autonomous_run`, `test_spec_workflow`, `test_draft_pr`, `test_branch_sync`, `test_governance`.

```yaml
review: tests
verdict: approved   # after the fixes below
covered: AC-001..AC-033 (map below)
findings:
  - id: TST-001
    severity: medium
    location: tests/test_autonomous_recovery.py
    description: >
      The changed-input re-entry (AC-012) and the end-to-end fix loop were
      proven only by real-engine tests, which CI skips (no Spec Kit, systemd
      user session or bwrap there).
    required_action: >
      Add an offline re-entry case through run.py with the engine stub (done:
      ResumeTests.test_changed_inputs_send_the_resume_back); the fix-loop state
      machine is offline in test_autonomous_artifacts (FixStateTests,
      RecordFixTests) and the wrapper gate in AttemptCountTests.
  - id: TST-002
    severity: low
    location: tests/test_autonomous_run.py (AgentWrapperAutonomousTests)
    description: >
      Two existing wrapper tests used `/speckit-ballast-review plan` with a
      deliberately invalid draft; the new retry loop retried them to a limit.
      They now use an argument without a draft contract; their subject (role
      and draft attribution) is unchanged, and the retry path has its own tests.
    required_action: none (documented in the test).
```

## Criterion to evidence

| Criteria | Evidence (CI-run unless marked *engine*) |
| --- | --- |
| AC-001, AC-002, AC-004, AC-033 | *engine* `FixLoopTests.test_medium_finding_one_cycle_then_publish`; `FixStateTests`, `RecordFixTests`, `RecoveryRenderTests` |
| AC-003, FR-002 | *engine* `FixLoopTests.test_high_finding_after_three_cycles_blocks_limit`; `FixStateTests.test_high_finding_after_three_cycles_blocks_as_limit`, `test_medium_open_on_the_last_review_is_a_draft_error` |
| AC-005, FR-006 | `AutonomousWorkflowDefinitionTests.test_every_human_gated_check_is_kept`, `test_version_and_step_order` |
| AC-006, FR-003 | *engine* `test_check_failure_reaches_fix_input_only`; `FeedbackChecksTests`; `PermissionsUnchangedTests` |
| AC-007, FR-004 | `IntentEvidenceTests` |
| AC-008, AC-009, AC-010, SC-004 | *engine* `ResumeEngineTests` (both base-advance cases); `ResumeTests.test_resume_records_and_reenters` |
| AC-011 | `ContinueRefusalTests` |
| AC-012 | *engine* `test_changed_spec_reenters_at_validate_spec`; `ResumeTests.test_changed_inputs_send_the_resume_back` |
| AC-013 | `ResumeTests.test_protected_input_fails_closed` |
| AC-014 | `ResumeTests.test_unpinned_run_blocks_with_manual_step`, `test_branch_sync.test_unpinned_resume_is_refused` |
| AC-015 | `ResumeTests.test_resume_of_continued_run_refused` |
| AC-016, AC-029 | `RunBlockTests.test_autonomous_resume_refuses_mode_limits_and_inputs`, `ResumeTests.test_resume_keeps_mode_and_limits`, `ModeAuthorityTests`, `ResumeRunTests` |
| AC-017–AC-020, SC-005 | *engine* `RetryEngineTests`; `StepDraftTests`, `AttemptCountTests.test_every_attempt_counts` |
| AC-021 | `CommandWordingTests` |
| AC-022 | `TasksTemplateTests` |
| AC-023–AC-025, SC-007 | `CheckpointTests`, `RefreshOnlyTests` |
| AC-026 | `BlockClassTests` |
| AC-027 | `ActiveRecordTests`, `ResumeTests.test_active_time_after_a_long_pause`, `test_active_invocation_refuses_and_a_dead_one_is_interrupted`, `AttemptCountTests.test_a_step_still_stops_at_the_limit` |
| AC-028 | `AttemptCountTests` |
| AC-030 | `ProvisionalGuardTests`, `UntrustedTextTests` |
| AC-031 | `PolicyWordingTests` |
| AC-032, SC-006 | `PermissionsUnchangedTests`, `HumanGatedUnchangedTests`, unchanged human-gated resume and continue tests, `test_feature_workflow_is_unchanged` |
| R7 | *engine* `EngineRepositionTests` |

Negative paths covered: every non-resumable row of the eligibility table, refused `--ref`, held lock, protected input, unpinned run, tamper never retried (wrapper path unchanged), state refusals not retried, retries exhausted, step limit during a retry, old workflow copy, decision resolution while a fix is pending, idle cycle slots writing nothing, checkpoint without a PR writing nothing. SC-001 (live pilot) stays an operator step after merge.
