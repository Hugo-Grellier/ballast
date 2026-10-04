- Verdict: PARTIAL

Reviewer: Claude Fable 5.1 (independent of the implementer)

# Spec reconciliation and converge: Autonomous run core (#27)

Scope: `spec.md` (AC-001..AC-025, FR-001..FR-030, SC-001..SC-007), `plan.md`, `tasks.md`, `decisions.md` (DEC-0001..0008, all resolved), `data-model.md`, `contracts/*.md`, the branch diff `origin/main...HEAD` (69 files; `tools/spec_workflow/{autonomy,artifacts,run,agent,ledger}.py`, `tools/feature_intake.py`, `tools/setup`, `templates/`), the tests, README, shipped policies, `AGENTS.md`, the constitution and ADR-0004. Accepted decisions amend the spec and plan where noted.

Evidence checked by this review (2026-10-04, worktree `feat-autonomous-core`, HEAD `0f18900`):

- `uvx ruff check && uvx ruff format --check`: pass (157 files).
- `uv run --no-project --python 3.13 --with pyyaml python -m unittest tests/test_*.py`: `Ran 540 tests in 398.507s`, `OK`, exit 0 (the engine-driven, real-`bwrap` and systemd cases ran on this host; no skip reported in the summary line).
- Every test method and class cited in `tasks.md` and `decisions.md` exists in `tests/` (78 methods, 32 classes checked by script; none missing).
- `templates/spec-kit/workflows/feature/workflow.yml`, `claude-settings.json` and `tools/ballast` are byte-identical to `origin/main` (SC-007).
- `ballast-autonomous` has 39 steps and no `gate`; the step ids match the contract table including `renew-intent` and `run-checks`. `ballast-continue` has the 15 steps of the contract and no `command` step.
- Constitution is 1.1.0 with BL-INV-006; the amendment file is gone (T071a); `ballast.toml` has `[checks]` and `[github] repository`.
- Live pilot (T070) is operator-recorded manual evidence on a private scratch repository; this review did not reach that repository and takes the recorded run IDs and PR URLs as stated.

PARTIAL means: every acceptance criterion has implementation and executable evidence, no requirement is unbuilt, but two tasks are open by construction (T072 is this review, T074 follows it), three artifacts are stale against the delivered code, and three items need the operator's explicit confirmation at merge rather than agent attestation.

## Criterion → implementation → evidence

| Criterion | Implementation | Executable evidence |
| --- | --- | --- |
| AC-001, SC-001 | `run.py _start_autonomous` → `ballast-autonomous` (no `gate` step); `autonomy.publish` | `AutonomousWorkflowDefinitionTests`; `AutonomousEngineTests.test_runs_to_a_draft_pr_without_a_prompt`; `RunStartTests.test_autonomous_start_records_run_and_publishes`; pilot run `031d34f9` → PR #6 |
| AC-002, FR-009, FR-010 | `artifacts.py record-decision` (runner fills provider, step_id, role, at); `autonomy.append_decision` | `RecordDecisionTests`; `AutonomousEngineTests` (one current PD per point) |
| AC-003, FR-015 | Autonomous preamble in every `--run` check; unchanged validators; `run-checks` | `AutonomousEngineTests.test_failed_validator_stops_the_run`; `RunChecksTests.*`; `AutonomousBlockEngineTests.test_postcondition` |
| AC-004, FR-016 | review recorders (`plan-review`, `implementation-review`, `specialist-review`, `spec-reconciliation`), `cross_provider` runner-filled, high/critical → `review-finding` block, verdict ≠ approved blocks | `ReviewRecorderTests` (incl. `test_only_an_approved_verdict_proceeds`); `RunStartTests.test_single_provider_review`; DEC-0004 fallback tests |
| AC-005, FR-017 | `record-decision --point clarification`; `clarified-spec` unchanged; `speckit.ballast.clarify` | `ClarificationTests.test_one_decision_per_assumption`, `test_irreversible_assumption_is_refused`; `AutonomousBlockEngineTests.test_several_outcomes_recommend_decomposition` |
| AC-006, FR-025, SC-006 | `autonomy.render_pr_body`, `render_record`, 60,000-char fallback | golden fixtures `pr-body-*.md`, `record-*.md` (`RecordRenderTests`); pilot PR #6 body |
| AC-007, FR-011, SC-003 | wording regex in recorder and renderer; `check_intent` refuses approval blocks in Autonomous runs | `RecordDecisionTests` (forged phrase refused); `ProvisionalIntentTests.test_forged_human_approval_is_refused`; golden body never matches the regex |
| AC-008, FR-012 | provisional block bound to spec digest; `--renew` blocks a changed spec (DEC-0006) | `ProvisionalIntentTests.test_spec_change_makes_it_stale`, `test_renew_blocks_stale_intent_after_a_spec_change`; `FinalAcceptanceTests.test_stale_intent_is_rejected` |
| AC-009, FR-028, FR-023 | `run.py _continue_command` (HD + `lower`, `ballast-continue`) | `RunContinueTests.*`; `AutonomousContinueEngineTests.test_changes_requested_starts_ballast_continue`; pilot run `08d120ba` |
| AC-010, FR-027 | publisher argv (push of HEAD to the pinned URL from a bare repo; `pr create --draft`; read-only `gh api`) | `PublisherTests.test_argv_never_merges_or_forces`; `NEVER_AUTHORIZED` ignored in policy (`PolicyTests`) |
| AC-011, FR-021, FR-022 | block draft validation (two options, no-safe-default reason), `block.json`, `RECOVERY` commands | `BlockRecordTests`; `RunBlockTests.test_invalid_or_missing_draft_still_blocks_as_decision`; `AutonomousBlockEngineTests.test_decision`, `test_contradiction` |
| AC-012, FR-020 | `agent.py` `EXIT_LIMIT = 5`, deadline and step counter, bounded wait | `AgentWrapperAutonomousTests.test_expired_deadline_refuses_before_spawn`, `test_step_limit_refuses_before_spawn`, `test_agent_outliving_the_deadline_is_stopped`; `AutonomousBlockEngineTests.test_limit`; pilot run `655fb10c` |
| AC-013 | wrapper tamper exit 4, unfinished-step refusal, launcher trust refusal (DEC-0002: no `trust` block) | `RunBlockTests.test_tamper_keeps_its_category_despite_the_kept_marker`, `test_unfinished_step`; `AutonomousBlockEngineTests.test_tamper`, `test_unfinished_step`, `test_trust`; `BlockRecordTests.test_no_trust_block` |
| AC-014 | `run.py` resume refusal naming #18; `continue` records an HD | `RunBlockTests.test_resume_is_refused_for_autonomous_runs`, `test_resume_of_human_gated_run_is_unchanged`; pilot step 3 |
| AC-015, FR-001 | `--mode` default human-gated; mode only in operator state | `RunStartTests.test_default_mode_keeps_todays_argv`, `test_mode_limits_and_eligibility_are_not_workflow_inputs`, `test_limits_need_autonomous_mode` |
| AC-016, SC-005, FR-003 | `confined_argv` (bwrap, protected inputs ro, state dir unreachable), `record.md` byte comparison | `ConfinementTests`, `RealConfinementTests`; `AutonomousConfinementEngineTests.test_agent_writes_change_nothing_operator_side` (DEC-0003); `RunRecordTests.test_lower_only_from_paused_autonomous_and_raise_refused` |
| AC-017, FR-004 | `lower` mode change with time and actor; earlier PDs rendered | `RunContinueTests.test_continue_records_human_decision_and_lowers`, `test_no_path_raises_a_human_gated_run`; `AutonomousContinueEngineTests` |
| AC-018 | `check_eligibility` risk recorded | `EligibilityTests.test_eligible_risk_levels_are_recorded`; `RunRefusalTests.test_eligible_r0_starts_with_its_risk` |
| AC-019, FR-008 | `_scope_problems` (closed, epic/sub-issues, open blocker), scope comment rules | `EligibilityTests.test_scope_gate_refusals`, `test_missing_scope_record`; `RunRefusalTests.test_scope_gate_refusals`, `test_missing_scope_fields`; pilot #2 |
| AC-020, FR-006 | privileged-actions line and authorization; `feature_intake._scope_text` | `EligibilityTests.test_missing_privileged_actions_line`, `test_privileged_actions`; `RunRefusalTests.test_privileged_action_and_narrowed_risk`; `tests/test_feature_intake.py`; pilot #3 |
| AC-021, FR-007 | `[autonomous]` narrowing only; widening keys warned | `PolicyTests.test_narrowing_and_ignored_widening`; `EligibilityTests.test_widening_key_is_ignored_with_warning`; `RunRefusalTests` (`cannot widen eligibility` printed); pilot #4 |
| AC-022, FR-005 | recorder risk re-check against the start snapshot; publisher union re-check | `RiskRecheckTests.*`; `PublisherTests.test_raised_excluded_risk_blocks_publication`, `test_unauthorized_privileged_action_blocks_publication` |
| AC-023 | `required_kinds()` (security always; architecture for R2/boundaries; path triggers), hint file for the specialists step | `ImplementationReviewTests.*`; `AutonomousEngineTests.test_r2_specialists_follow_the_required_reviews_hint`; pilot run `c64210f1` |
| AC-024, FR-019 | severity rules in review recorder | `ReviewRecorderTests` severity cases; `AutonomousBlockEngineTests` review-finding case |
| AC-025, FR-026 | R2 notice in `render_record`/`render_pr_body` | `RecordRenderTests.test_r2_notice_only_for_r2`; `pr-body-r2.md`; pilot PR #7 |
| FR-002, FR-013 | `mode_history` append-only, hash-chained logs | `RunRecordTests`, `HashChainTests` (`test_forged_history_is_refused`, `test_supersedes_must_name_a_current_decision`) |
| FR-014 | `record.md` mode section; `intent.md` provisional block | golden `record-*.md` |
| FR-018 | `material` flag, "Material provisional changes" section; `check_decisions` mode-aware | `DecisionsTests`; golden fixtures |
| FR-024 | `publish()` (DEC-0007/T069f/h/j hardening and adoption) | `PublisherTests.*` (verified read-back, pinned push, adoption rules); `PublisherCheckpointTests.*` |
| FR-029, FR-030 | policies, `AGENTS.md`/`templates/AGENTS.md`, PR template, model routing, constitution 1.1.0, TECHNICAL/PRODUCT spec | `tests/test_governance.py` (2 cases); documentation diff read by this review |
| SC-002 | `record-final` one current PD per point | `FinalAcceptanceTests`; `AutonomousEngineTests` |
| SC-004 | one engine case per block category | `AutonomousBlockEngineTests` (`decision`, `contradiction`, `limit`, `tamper`, `unfinished_step`, `postcondition`, `ineligible`, `forge`, `permission`, `interrupted`, `several_outcomes`) |
| SC-007 | unchanged workflow file and permissions | `AutonomousWorkflowDefinitionTests`; whole suite |

Spec edge cases: single provider (`test_single_provider_review`, golden single-provider fixtures); forge failure keeps branch and record, nothing reported as published (`test_publication_failure_is_a_retryable_forge_block`, `test_forge_failure_is_retryable`); interruption (`RunBlockTests.test_interrupted_run`, `AutonomousBlockEngineTests.test_interrupted`); forged approval (`test_forged_human_approval_is_refused`); supersession (`HashChainTests`); several clarification outcomes (`test_several_outcomes_recommend_decomposition`). Base-branch advance: not implemented, as the spec says.

## Converge: approved requirements and tasks not built

- No FR, AC or SC is without an implementation. No code task is open: T001–T071a and T073 are ticked with evidence.
- Open by construction: **T072** (this review and its outcome) and **T074** (PR description; depends on T072). Both remain; neither is unbuilt behavior.
- Behavior that exceeds the spec, each covered by an accepted decision: Codex-sandbox fallback to Claude for both roles (DEC-0004; FR-016 "preferring a different provider" still holds when it can run); adoption of the #17 checkpoint PR instead of refusing it (DEC-0007 amends FR-024 "created by the run"); the Issue snapshot `.specify/workflow-state/issues/<N>.md` (DEC-0008); `--renew` blocking instead of superseding intent (DEC-0006, stricter than contract step 30a as approved). None contradicts the spec text.

## Gaps

1. **plan.md "Unchanged" list is stale (specification stale).** `plan.md` Repository Impact says `ledger.py` and the ledger schema are unchanged, but T069b changed `tools/spec_workflow/ledger.py` (`_git` now imports `autonomy.filter_flags` and empties filter drivers; the schema is unchanged). Fix: drop `ledger.py` from the "Unchanged" list, keep "the ledger schema", and note the T069b import in the BL-INV-002 row (the module stays inside `.ballast/spec_workflow/`).
2. **"existing cases stay unmodified" is no longer literally true (new knowledge, T069o).** `plan.md` and `tasks.md` state that `tests/test_spec_workflow.py` gets new cases only. The diff changes fixture setup in `AgentWrapperTests`, `ScopeContainmentTests` and `TrustedLauncherTests` (fake `systemd-run` moved to `trusted_directory()` because `trusted_program()` refuses working-tree and temp-root copies) and `tests/test_agent_run_ledger.py::isolated_cli` (copies `autonomy.py` and `launcher.py` next to `ledger.py`). No assertion changed, so SC-007 ("the same gates and approvals as before") holds; the artifact sentences should say "assertions unchanged; fixtures adjusted for T069o/T069b" rather than "unmodified".
3. **ADR-0004 status asserts a merge that has not happened (artifact wording).** The status line reads "accepted … confirmed by the operator's merge of the feature PR" while the PR is not merged. DEC-0006, DEC-0007 and DEC-0008 and the ADR acceptance are explicitly "provisional under the operator's standing authority; confirm at merge". Fix: word the ADR status as "accepted under standing authority; confirmed when the feature PR merges", and list the four items the merge reviewer confirms (DEC-0006, DEC-0007, DEC-0008, ADR-0004) in the PR description (T074).
4. **`ballast trust` was run by an agent (process deviation to surface, not a code gap).** T005 and T071a evidence record that the coordinating agent re-ran `ballast trust` "under the operator's standing authority". `AGENTS.md` (unchanged on this point) says "Only the operator runs `ballast trust`", and the launcher's trust model is an R2 boundary. The trust baseline on the operator's host is therefore one an agent attested. Recommended: the operator re-runs `ballast trust` on the merged checkout and the PR description names this; if the standing authority is meant to cover trust, amend `AGENTS.md`/`templates/AGENTS.md` instead (R2, human decision). This review does not change either.
5. **Reviewer `model` identity is agent-reported (known ceiling, no action).** FR-010 asks for the deciding agent's provider, model and role; the runner fills provider, role and step, and `model` comes from the draft (`unreported` when absent), so the model name in `record.md` and the PR is the agent's own claim. The data model says so; the PR does not. Optional follow-up: state "model as reported by the agent" in the Reviews and decision-table column headers.

No implementation-wrong gap was found. Gaps 1–3 are artifact edits (plan.md, tasks.md, ADR-0004 status line, PR description); gap 4 is an operator action; gap 5 is optional wording.

## Notes for the merge reviewer

- `git status` in the worktree shows `specs/27-autonomous-core/tasks.md` as modified with an empty content diff (stat-only); nothing uncommitted differs from HEAD.
- The pilot's two Draft PRs, three refusals, two blocks and one continuation are recorded in T070 with run IDs; they were not re-verified against GitHub by this review.
- Required reviews (T071): codex-1 REJECT, codex-2 REJECT, fable-3 APPROVE WITH CHANGES; every finding is closed by T069a–T069p or a resolved DEC. Fable-3 and this review are same-provider (Codex out of quota), so the merge review is the independent cross-provider check the model-routing policy prefers.
