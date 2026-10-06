# Spec reconciliation

- Reviewer: Claude Opus 5.5, the driving agent (not independent)
- Date: 2026-10-06
- Skill: `.agents/skills/ballast-spec-reconciliation/SKILL.md`
- Inputs: [spec.md](../spec.md), [plan.md](../plan.md), [research.md](../research.md), [data-model.md](../data-model.md), [contracts/](../contracts/), [tasks.md](../tasks.md), [decisions.md](../decisions.md), the diff `bc4ea3e..HEAD`, the tests mapped in [test-1.md](test-1.md), the policies, README and ADR-0007.

## Criterion to implementation and evidence

| Requirement | Implementation | Evidence |
| --- | --- | --- |
| FR-001, FR-002, AC-002, AC-003 | `artifacts.review_rule`, `record_decision` (`--recheck`), `record_fix`; workflow 1.2.0 fix cycles | `FixStateTests`, `RecordFixTests`, *engine* `FixLoopTests` |
| FR-003, AC-006 | `run_checks(feedback=True)`, fix input file; wrapper permissions unchanged | `FeedbackChecksTests`, `PermissionsUnchangedTests`, *engine* fix-input case |
| FR-004, AC-007 | `_check_intent_evidence`; decide command | `IntentEvidenceTests` |
| FR-005, AC-004 | `render_record`/`render_pr_body` (fix loop, block resolutions, retries, spend) | `RecoveryRenderTests`, goldens, *engine* PR body |
| FR-006, AC-005 | workflow 1.2.0 keeps every check | `test_every_human_gated_check_is_kept` |
| FR-007–FR-013, AC-008–AC-016 | `run._resume_autonomous`, `_reentry`, `_reposition_engine`, `autonomy.resume_run`, `_continue_refusal` | `ResumeTests`, `ContinueRefusalTests`, `ReentryTests`, `EngineRepositionTests`, *engine* `ResumeEngineTests` |
| FR-014, AC-014 | `branch_sync` `unpinned` text; policy "Runs started before branch pinning" | `test_unpinned_resume_is_refused`, `DocumentationTests` |
| FR-015 | ADR-0007; ADR-0004 amendment | `PolicyWordingTests` |
| FR-016–FR-018, AC-017–AC-021 | `DraftError`, `check_step_drafts`, wrapper retry loop; command wording | `StepDraftTests`, `AttemptCountTests`, `CommandWordingTests`, *engine* `RetryEngineTests` |
| FR-019, AC-022 | tasks template | `TasksTemplateTests` |
| FR-020, AC-023–AC-025 | `run._checkpoint_command`, `draft_pr.checkpoint(create=False)` | `CheckpointTests`, `RefreshOnlyTests` |
| FR-021, AC-027 | active time in `autonomy`; clock in `run.py` (fails closed) | `ActiveRecordTests`, `ResumeTests` active-time cases |
| FR-022, AC-028 | `AGENT_STEPS` 40; every attempt counted; spend line | `AttemptCountTests`, `RecoveryRenderTests.test_spend_line` |
| FR-023, AC-026 | `BLOCK_CLASSES`, printed block | `BlockClassTests` |
| FR-024, FR-025, AC-029–AC-032 | guards unchanged; policies; human-gated path unchanged | `ProvisionalGuardTests`, `PolicyWordingTests`, `HumanGatedUnchangedTests`, `ModeAuthorityTests` |
| FR-026, AC-033 | no new forge write path | argv assertions in `FixLoopTests`, `ResumeEngineTests`, `CheckpointTests` |
| FR-027 | standard library only, `python3 -I -S` | all shell steps run that way in the tests |

## Gaps and diagnoses

- **New knowledge (resolved):** DEC-0001, a resume after the base advanced first blocks as `dirty`; policy and tests follow #18's recovery. SC-004 holds after that documented recovery.
- **Specification stale (not material):** the spec's edge case "the default 30-step limit" and its assumption text name 30 steps; the plan changed the default to 40 (R9, recorded in ADR-0007). `spec.md` is left unchanged so the digest bound to the provisional intent (PD-0013) stays valid; fold the wording into the next spec revision or the human-gated intent approval.
- **Artifact sync (done):** the fix input carries a `verdicts` list (non-approved reviews need a fix without a finding, R2 rule 1); `data-model.md` updated. Decisions record `agent.attempts` and `agent.refusals` on every entry (1 and `[]` without a retry), as the data model says.
- **Implementation choice within the contract:** `run-checks --feedback` keeps the contract's single argv for `checks-implementation` and `checks-fix-N`; it runs when a cycle is under review or before the first implementation review (idle fix state, no frozen tree).
- **Pending outside this feature:** SC-001 (live pilot after merge) and SC-008 (gates recorded in the PR) are operator steps by design.

No behavior contradicts or exceeds the spec; no accepted architecture changes beyond ADR-0007, which the plan proposed.

- Verdict: CONVERGED
