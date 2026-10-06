# Spec reconciliation: Chat mode (#20)

- Review: spec-reconciliation (with the Spec Kit converge assessment)
- Reviewer: claude (model), fresh context, same provider as the author. Codex was unavailable, so there is no cross-provider reviewer.
- Scope: branch `feat/20-chat-mode`, `HEAD` 110d8c8, base 52031c1. I read `spec.md`, `plan.md`, `tasks.md`, `decisions.md` (DEC-0001 to DEC-0003), `data-model.md`, `contracts/*.md`, every report in `reviews/` (with the Resolution sections now appended to the security, engineering and test reviews), the code in `tools/spec_workflow/` (`chat.py`, `run.py`, `agent.py`, `autonomy.py`, `artifacts.py`, `ledger.py`, `draft_pr.py`, `branch_sync.py`, `launcher.py`, `chat_hook.py`, `claude-chat-settings.json`), the new tests, and the public docs (`README.md`, `AGENTS.md`, `templates/policies/spec-kit-workflow.md`, `templates/policies/workflow.md`, `templates/AGENTS.md`, `templates/skills/ballast-feature-intake/SKILL.md`, ADR-0006).
- Executed: 7 single tests, all passing (`PublishTests.test_a_review_changed_after_final_approval_blocks_publish`, `PublishTests.test_final_needs_every_earlier_approval_current`, `StepCloseTests.test_open_write_scope_violation_blocks_until_restored`, `StepEntryTests.test_chat_settings_deny_prompts_outside_dont_ask`, `ForgeryTests.test_each_forgery_attempt_changes_nothing`, `ContinueTests.test_blocked_continuation_is_recovered_by_the_next_step`, `EndToEndTests.test_conversational_feature`). I did not run the full suite; a separate process runs it.
- Checked: `git diff 52031c1 HEAD -- tests/` (excluding the new Chat files) removes no line. `git diff 52031c1 HEAD` is empty for `templates/spec-kit/workflows`, `claude-settings.json`, `tools/ballast`, `tools/setup` and the constitution. `spec.md` has not changed since the spec commit.

Test names below are in `tests/test_chat_mode.py` unless another file is named. Implementation symbols are in `tools/spec_workflow/`.

## Acceptance criteria

| AC | Implementation | Deterministic evidence |
| --- | --- | --- |
| AC-001 | `launcher._refusal`; `run.py` dispatch; `chat.start` (ledger `run`, then `synchronize(starting=True)`) | `StartTests.test_each_preflight_condition_refuses_before_any_agent`, `test_blocked_synchronization_leaves_a_record_without_steps`, `test_start_records_pins_archives_and_runs_no_agent`, `test_integration_that_cannot_run_confined_is_refused` |
| AC-002 | `chat.entry`, `_requirements`, `allowed_actions`, `PHASES` | `PhaseGraphTests.test_each_phase_opens_with_its_entry_condition`, `test_checks_are_cumulative`, `test_allowed_actions_order`; `StepEntryTests.test_step_not_allowed_yet_is_refused_and_recorded` |
| AC-003 | `agent.interactive_argv`, `chat_settings`, `run_interactive`; `autonomy.confined_argv(interactive_pty, readonly_extra)`, `_installed_skill_binds`; `chat_hook.py` (DEC-0001) | `StepEntryTests.test_claude_argv_is_the_contract`, `test_codex_argv_is_the_contract`, `test_chat_settings_keep_every_headless_rule`, `test_chat_settings_deny_prompts_outside_dont_ask`, `test_forbidden_marker_is_refused_before_launch`; `TerminalTests.*`; `tests/test_autonomy.py` `ConfinementTests`. Real denial: `test_real_bwrap_keeps_protected_and_operator_paths_out_of_reach`, `test_real_bwrap_keeps_installed_skills_read_only` (skipped in CI; ran on the full local host per `reviews/pilot.md`) |
| AC-004 | `chat._finish`, `_postconditions`, `_close`, `_check` | `StepCloseTests.test_valid_spec_completes_with_its_postcondition`, `test_invalid_spec_fails_and_blocks_until_a_later_pass`, `test_scope_is_confirmed_stopped_before_the_first_check`, `test_unconfirmed_scope_keeps_the_marker_and_runs_no_check`; `PhaseGraphTests.test_failed_check_blocks_until_a_later_passing_run` |
| AC-005 | `chat.summary`, `status` | `StatusTests.test_summary_matches_the_golden_text`, `test_status_runs_nothing_and_writes_only_out_of_step_changes` |
| AC-006 | `chat.out_of_step`, `_made_stale`, `approval_state`; launcher baseline | `OutOfStepTests.test_operator_edit_is_recorded_and_stales_its_approval`, `test_protected_input_edit_is_refused_by_the_launcher`, `test_rerunning_an_earlier_step_stales_what_it_changed` |
| AC-007 | `chat.approve`, `_gate_decision`, `gate_digest`; `artifacts.record_intent` | `ApprovalTests.test_approval_needs_a_terminal_and_the_exact_text`, `test_approval_while_a_step_is_active_is_refused`, `test_failed_precondition_is_recorded`, `test_rejection_and_staleness` |
| AC-008 | gate state only from `human-decisions.jsonl`; `artifacts.check_intent` (registered block), `human_resolutions`; operator state hidden by bwrap | `ForgeryTests.test_each_forgery_attempt_changes_nothing` (6 attempts, including the launcher `approve`, `mode` and `step` from inside a step); `HeadlessForgeryTests.*`; `tests/test_spec_workflow.py` `ChatArtifactTests`; real-bwrap `test_operator_records_are_out_of_reach_under_real_bwrap` |
| AC-009 | `GATES` (every `ballast-feature` gate); `chat.resolve`; no call to `autonomy.append_decision` | `ResolutionTests.test_chat_asks_for_every_human_gate`, `test_no_chat_command_records_a_provisional_decision`, `test_provisional_intent_block_is_refused_until_approve_intent`, `test_resolve_records_a_human_resolution_bound_to_its_text` |
| AC-010 | `chat.run_step` (lock, `late_close`, `out_of_step`, `synchronize` with the Chat `rerun`, entry); `run._resume_refusal` | `ReturnPreflightTests.test_each_preflight_condition_refuses_a_step`, `test_resume_of_a_chat_run_is_refused`, `test_advanced_base_is_synchronized_before_the_agent`, `test_dirty_tree_blocks_with_the_chat_recovery` |
| AC-011 | `chat.summary` (from the operator record only) | `HandoffTests.test_status_names_failures_gates_and_next_steps_from_the_record` (output identical after logs are deleted) |
| AC-012 | `chat.late_close`, `_finish` (interactive), `agent.run_interactive` signal handling | `InterruptionTests.test_sighup_to_the_wrapper_closes_the_step`, `test_dead_wrapper_is_closed_late_after_discard_runs`, `test_unconfirmed_processes_keep_the_refusal`; `StepCloseTests.test_real_scope_and_bwrap_step_is_confirmed_stopped` (skipped in CI) |
| AC-013 | `chat.Lock`, `_require_no_step`, `_active_chat_runs`; `launcher._unfinished` text | `ConcurrencyTests.test_commands_are_refused_while_a_step_is_active`, `test_the_run_lock_lets_one_invocation_through`; `tests/test_spec_workflow.py` `test_unfinished_step_refusal_names_the_run_and_step` |
| AC-014 | `chat._ledger`, `_ledger_gate`, `_ledger_review`; `ledger` `mode` field and `_chat_report` | `LedgerEvidenceTests.test_full_chat_run_reports_against_ballast_feature`; `tests/test_agent_run_ledger.py` `test_run_mode_is_optional_and_enumerated`, `test_mode_changed_requires_mode`, `test_chat_event_order_is_accepted`; `ProjectChecksTests.test_checks_record_runner_results` |
| AC-015 | `REVIEW_KINDS`, `_review_report`, `_review_event`; `_choose_integrations` | `ReviewStepTests.test_review_runs_with_the_review_integration`, `test_review_report_rules`, `test_single_provider_review_is_not_cross_provider` |
| AC-016 | `chat.publish` (final precondition re-run, DEC-0002), `publish_section`; `autonomy._publish_chat`, `_publication_target` | `PublishTests.test_publish_needs_a_current_final_approval`, `test_publish_commits_pushes_and_opens_one_draft`, `test_a_body_edited_while_publishing_is_left_alone`, `test_oversized_section_falls_back_to_counts`, `test_agent_values_never_claim_an_approval`, `test_a_review_changed_after_final_approval_blocks_publish`, `test_final_needs_every_earlier_approval_current`; `tests/test_draft_pr.py` `test_chat_run_feature_comes_from_its_operator_record` |
| AC-017 | logs under `.specify/workflow-state/<run>/agents/<step>/`; `publish_section` renders records only (`LOGS_LOCAL`) | `PublishTests.test_publish_commits_pushes_and_opens_one_draft` (secret in `stdout.log`, absent from body, commit, tree and ledger); `StepCloseTests.test_logs_are_written_through_the_original_directory` |
| AC-018 | `chat.change_mode`; `autonomy.change_mode`, `_validate_mode_history` | `ModeSwitchTests.test_switches_keep_every_entry_and_every_failure` (byte prefixes unchanged); `tests/test_autonomy.py` `test_switch_between_chat_and_human_gated_only`, `test_only_a_chat_run_switches` |
| AC-019 | checks evaluated again on request, nothing stores a pass | `ModeSwitchTests.test_switches_keep_every_entry_and_every_failure`; `ContinueTests.test_lowering_keeps_failures_and_open_decisions`; `PhaseGraphTests.test_failed_check_blocks_until_a_later_passing_run` |
| AC-020 | `artifacts.check_decisions` (Chat branch), `chat.superseding`, `_source_decisions` | `ModeSwitchTests.test_switches_keep_every_entry_and_every_failure`; `ContinueTests.test_continue_in_chat_keeps_provisional_decisions_provisional`, `test_lowering_keeps_failures_and_open_decisions` |
| AC-021 | `chat.change_mode` and `autonomy.change_mode` (`NEVER_RAISED`) | `ModeSwitchTests.test_switches_keep_every_entry_and_every_failure`; `ContinueTests.test_autonomous_is_never_raised`; `tests/test_autonomy.py` mode-history tests |
| AC-022 | `run._continue_chat`, `chat.continue_run`, `_inherited_pin` | `ContinueTests.test_continue_in_chat_keeps_provisional_decisions_provisional`, `test_changes_requested_continues_the_same_way`, `test_blocked_continuation_is_recovered_by_the_next_step`; `tests/test_autonomy.py` `test_paused_autonomous_run_lowers_to_chat` |

Every AC has an implementation and at least one deterministic test that runs in CI. For AC-003 and AC-012, the CI tests check the argv and use fake bwrap and systemd. The real-confinement variants are skipped in CI. `reviews/pilot.md` reports that they ran on a host with real bwrap and systemd.

## Success criteria

| SC | Evidence | State |
| --- | --- | --- |
| SC-001 | `EndToEndTests.test_conversational_feature` (every `step` preceded by a passing `sync`); `PublishTests.test_publish_commits_pushes_and_opens_one_draft` (a full run to a Draft PR against fake `gh`) | Deterministic evidence is complete. The real Issue-to-PR run (quickstart 1 and 4) is still a manual pilot. |
| SC-002 | Start: `StartTests.test_each_preflight_condition_refuses_before_any_agent`, `test_blocked_synchronization_leaves_a_record_without_steps`. Step and return: `ReturnPreflightTests.test_each_preflight_condition_refuses_a_step`, `test_dirty_tree_blocks_with_the_chat_recovery`. Resume: always refused (`test_resume_of_a_chat_run_is_refused`). | Met. `continue --mode chat` under a blocked sync is covered for recovery only. The linked `mode` entry is not covered (TST-005, low). |
| SC-003 | `LedgerEvidenceTests.test_full_chat_run_reports_against_ballast_feature` | Met. It compares against a literal set rather than a human-gated fixture run (TST-007, low, accepted). |
| SC-004 | `ForgeryTests.test_each_forgery_attempt_changes_nothing` (approval block, claims, resolution, launcher `approve`, `mode` and `step`); `HeadlessForgeryTests.*`; real-bwrap record-write test | Met |
| SC-005 | `ModeSwitchTests.test_switches_keep_every_entry_and_every_failure` (chat and human-gated, both ways); `ContinueTests.test_lowering_keeps_failures_and_open_decisions` (autonomous to chat); `ModeSwitchTests.test_a_paused_engine_run_continues_as_a_linked_chat_run` (engine to chat: approvals only) | Met for three of the four switches. The engine-to-Chat link has no failed-check or open-decision case, but it uses the same `entry` and `_check` path (TST-003 residual, accepted). |
| SC-006 | `HandoffTests.test_status_names_failures_gates_and_next_steps_from_the_record`; `StatusTests.test_summary_matches_the_golden_text` | Met |
| SC-007 | No existing test line removed (checked above); unchanged surfaces have an empty diff (T072). | Met. One expected Autonomous change: every confined step now binds the installed skills read-only (SEC-001). ADR-0006 records it as an ADR-0004 amendment, and no existing assertion changed. |

## Functional requirements

| FRs | Implementation | Evidence | State |
| --- | --- | --- | --- |
| FR-001, FR-002 | `run.py` dispatch behind the launcher; `chat.py` refuses `__main__`; `autonomy` `ballast-chat` record and `mode_history` in `state_dir` | `DispatchTests.*`; `RecordLayerTests.*`; `tests/test_autonomy.py` `ChatRecordTests` | Met |
| FR-003, FR-006, FR-015 | human-decision kinds, registered intent block, `resolve`, record-only gate state | AC-007 to AC-009 tests | Met |
| FR-004 | `run_step` preflight order | AC-001 and AC-010 tests | Met |
| FR-005 | interactive argv, chat settings and hook, bwrap | AC-003 tests | Met for Claude. Codex has a residual: see gap G-3. |
| FR-007, FR-008, FR-010 | `entry`, `allowed_actions`, `_in_scope`, `_violations_check` (DEC-0003) | `PhaseGraphTests.*`, `StepCloseTests.test_write_outside_the_phase_scope_fails`, `test_open_write_scope_violation_blocks_until_restored`, `EndToEndTests` (no Chat-only artifact) | Met |
| FR-009 | `_finish`, `late_close` | AC-004 and AC-012 tests | Met for the interactive driver. Not met for the headless driver of a Chat run switched to human-gated: see gap G-1. |
| FR-011 | `out_of_step`, `_made_stale` | AC-006 tests | Met for operator edits. Files merged by branch synchronization are not attributed (ENG-010, low). |
| FR-012 | `Lock`, `active_step`, marker | AC-013 tests | Met for one run. Two runs in one checkout can race on the shared marker (SEC-009, low). |
| FR-013, FR-014 | `steps.jsonl`, `events.jsonl`, ledger events, review events | AC-014 and AC-015 tests | Met. Low inaccuracies remain: the log path of a headless step (ENG-007), `cross_provider` computed two ways (ENG-008), and a launch error recorded as `interrupted` (ENG-013). |
| FR-016, FR-017 | `chat.publish`, `_publish_chat`, `publish_section` | AC-016 and AC-017 tests | Met. The PR header wording is now inaccurate (gap G-2). |
| FR-018, FR-019 | per-invocation actions, `summary` | AC-010 and AC-011 tests | Met |
| FR-020, FR-021, FR-022 | `change_mode`, `continue_run`, `_link_engine_run` | AC-018 to AC-022 tests | Met |
| FR-023 | Chat sections in the four shipped documents, README, AGENTS.md, ADR-0006 | `tests/test_governance.py` `test_each_document_describes_starting_and_inspecting_a_chat_run`, `test_spec_kit_policy_has_the_chat_section`; `tests/test_setup.py` `test_installs_chat_and_keeps_project_rules_for_chat_steps`; `reviews/documentation.md` (approved) | Met |

## Edge cases

| Edge case | Evidence | State |
| --- | --- | --- |
| Protected input edited between steps | `OutOfStepTests.test_protected_input_edit_is_refused_by_the_launcher`; `ReturnPreflightTests.test_each_preflight_condition_refuses_a_step` | Met |
| Base branch advances | `ReturnPreflightTests.test_advanced_base_is_synchronized_before_the_agent`, `test_dirty_tree_blocks_with_the_chat_recovery` | Met |
| Step not allowed yet | `StepEntryTests.test_step_not_allowed_yet_is_refused_and_recorded` | Met |
| Re-run of an earlier step | `OutOfStepTests.test_rerunning_an_earlier_step_stales_what_it_changed` | Met |
| Permission the step does not allow | Argv and settings tests, the hook test, real-bwrap tests (skipped in CI) | Met in CI by construction. The real denial without a prompt is pilot P-4. |
| Integration cannot run confined | `StartTests.test_integration_that_cannot_run_confined_is_refused`, `test_codex_without_a_nested_sandbox_names_claude` | Met at start. At step time it is implemented (`run_step` calls `_confinable`) but untested (TST-012, low). |
| Secret in the conversation | `PublishTests.test_publish_commits_pushes_and_opens_one_draft` | Met for publication. Later agents can still read earlier logs (SEC-008, low). |
| Operator ends a step while the agent writes | `StepCloseTests.test_escape_ends_a_step_while_the_agent_writes` | Met |
| No reviewer from another provider | `ReviewStepTests.test_single_provider_review_is_not_cross_provider` | Met for the record. The summary line is untested (TST-008, low). |

## Decisions and contract drift

- **DEC-0001** (Claude `PreToolUse` hook; Codex `/approvals` residual) changes `contracts/step-runner.md` § Interactive argv. For Claude it tightens the contract to match FR-005, and `spec.md` still agrees. For Codex it records a residual instead: an operator's `/approvals` can widen a Codex session past the headless permission model, up to the bwrap bound. FR-005 says the step "MUST run under the same permission model". `spec.md` does not mention this exception. See G-3.
- **DEC-0002** (`final` binds the whole tree, needs every earlier approval current, and `publish` checks it again) changes `data-model.md` § Gate digest binding, `contracts/phase-graph.md` and `contracts/pr-evidence.md`. It only tightens, and FR-016 and AC-007 already imply it. `spec.md` agrees and needs no change. One side effect is stated in the engineering review: a code change after `approve implementation` needs a new implementation approval before `final`. `templates/policies/spec-kit-workflow.md` does say that `final` needs every earlier approval current.
- **DEC-0003** (`open-write-scope` entry check) changes `contracts/phase-graph.md`. It only tightens, as FR-008 and FR-010 require. `spec.md` agrees.
- The `tasks.md` implementation clarifications (tasks digest, cumulative `converge` entry, `plan` entry with intent state, generated Claude settings, verdict pattern, SHA-256 manifest, the `mode-changed` ledger event) are each written into the contract they touch and do not change intent.
- `contracts/cli.md` now orders the ledger `run` event before synchronization (ENG-004) and documents recovery after a blocked continuation (ENG-001). The code matches both.
- All three DEC resolutions were decided by the driving agent under the standing v1.0 authority and listed for the merge review. The merge decision is the human decision on each.

## Gaps

| ID | Gap | Diagnosis | Artifact to change |
| --- | --- | --- | --- |
| G-1 | FR-009 and the step-runner contract (agent changes are never attributed to the operator) are not met for the headless driver. In a Chat run switched to human-gated, `_finish` checks `scope_stopped` only when `interactive`. A killed `agent.py` wrapper therefore gets its postconditions run while agents may still be alive, and its close records `scope_stopped: True`. Later edits are then attributed to the operator (SEC-007). The marker stays, so the launcher still refuses the next command. | Implementation wrong (low) | `tools/spec_workflow/chat.py` `_finish`: treat `scope_stopped: False` the same way for both drivers. Add a test with a SIGKILLed headless wrapper. |
| G-2 | The PR section's fixed header line (`contracts/pr-evidence.md:27`) claims that every gate listed below it was approved. After DEC-0002, rows can be marked `(stale)` or `(superseded)`, and rejections are listed too, so the header can be false (ENG-003 residual). The header text is fixed by the contract. | Specification stale (contract) | `contracts/pr-evidence.md` header line, then `chat.publish_section` and its golden test |
| G-3 | FR-005 has no Codex exception, but DEC-0001 accepts that `/approvals` widens a Codex step past the headless model (network and commands inside bwrap). This is a loosening, not a tightening, so it should appear where intent is read. Practical exposure is small: on the qualified host Codex cannot nest its sandbox, so Chat refuses Codex. | New knowledge discovered | `spec.md` Assumptions (one sentence naming the operator-initiated Codex residual), or the merge reviewer's explicit acceptance of DEC-0001 for Codex |
| G-4 | The reviews leave non-blocking residuals that no artifact tracks. The plan's follow-up list has only F-1 to F-4. Untracked: SEC-007, SEC-008 (log hiding), SEC-009, SEC-010, the headless-step skill writes (SEC-001 residual), the hook's `python3` from `PATH` (a hook that cannot start does not fail closed), the 500-path cap in `_violations_check`, ENG-007, ENG-008, ENG-010, ENG-012, ENG-013, and TST-005 to TST-012. | New knowledge discovered | `plan.md` § Follow-ups (add F-5 onward, or one entry pointing to the review IDs), then file Issues |
| G-5 | T077 names the reconciliation report `reviews/convergence.md`. That is also the file `artifacts.check_convergence` and the `ballast-feature` `spec-reconciliation` gate read. This report is `reviews/spec-reconciliation.md`, so the convergence check will not see its verdict. | Specification stale (tasks) | Either copy this verdict into `reviews/convergence.md`, or correct T077 |

## Unbuilt tasks (converge)

- T001 to T072 are marked done, and the code and tests above confirm each one. T071's fresh-clone `ballast setup` part was replaced by `tests/test_setup.py` `ChatInstallTests` and an install in `ChatCase`. The operator part is still open under T074 and the pilot.
- T073 to T077 are unchecked. They are workflow gates, not feature work: the fast gate (T073, running in another process), the full local gate (T074), the pilot (T075, partly done in `reviews/pilot.md`), the reviews (T076: plan, engineering, security, test and documentation are all `approved` after resolution; there is no separate architecture report, and ADR-0006 was reviewed inside the engineering review), and reconciliation (T077, this report). None is unbuilt code.
- Converge would append no new implementation task for an AC. If G-1 and G-2 are fixed in this feature, they become two small tasks (code with a test, and contract wording with a golden test).

## Manual evidence still pending

- Pilot P-3: resize, Ctrl-C and `/exit` in a real Claude TUI, with the terminal restored and no mouse mode left on. Codex cannot be checked on this host.
- Pilot P-4: Shift+Tab out of `dontAsk`, then ask for an edit of `ballast.toml` and for `curl`. Each tool call must be denied by the hook, with no prompt. This also confirms that Claude Code passes `permission_mode` to `PreToolUse` hooks.
- Pilot P-5: `/permissions` with a saved allow rule fails on the read-only `.claude/`, and a session-only rule is still denied outside `dontAsk`.
- Quickstart scenarios 1 to 7 with a real GitHub remote, with run IDs and `ballast ledger report --run RUN` output. In scenario 4, reviews must come before `approve final` (DEC-0002).
- The T071 operator part (fresh-clone `ballast setup`) and the T074 record that the real-bwrap and real-systemd Chat tests ran on that host and were not skipped.

Each AC also has a deterministic test, so this pending manual evidence does not on its own block convergence. At 110d8c8 the assessment was PARTIAL: G-1 (a MUST in FR-009, for the headless driver) and G-2 (false wording in the PR evidence) were actionable and unfixed, and G-3 to G-5 needed artifact updates. The Resolution below re-checks them.

## Resolution

I re-checked the gaps against `git diff 110d8c8 HEAD` (`83d04c2` fix, `cf2de2e` docs). I read the changes and ran the named single tests: `HeadlessForgeryTests.test_unconfirmed_headless_stop_leaves_the_step_open`, `HeadlessForgeryTests.test_headless_step_keeps_todays_argv`, `StepEntryTests.test_chat_settings_deny_prompts_outside_dont_ask` and `PublishTests.test_publish_commits_pushes_and_opens_one_draft`. All four pass. I did not run the full suite.

| Gap | Status | Evidence |
| --- | --- | --- |
| G-1 | fixed | `chat._finish` now keeps the step open whenever `scope_stopped` is false, whatever the driver (`if not result["scope_stopped"]`). It exits 4 and writes no close entry. The marker that `agent.py` leaves keeps the launcher refusing until `ballast discard-runs`. The next invocation then closes the step through `late_close`, with uncertain attribution to the step and never to the operator. Test: `HeadlessForgeryTests.test_unconfirmed_headless_stop_leaves_the_step_open` (no `close` entry, `active_step.scope_stopped` false, exit 4). |
| G-2 | fixed | `contracts/pr-evidence.md`, `chat.publish_section` and the publication test now share one header: every gate decision below was made by the operator through `ballast run approve` or `reject`, and publishing needs every gate's latest approval current. That holds with rejections and with `(stale)` or `(superseded)` rows. The wording rule now allows the approval phrase only in `gate-approval` rows. |
| G-3 | fixed | The Assumptions in `spec.md` now state DEC-0001's Codex residual: the operator's own `/approvals` can widen a Codex session up to the bwrap bound, as an operator action rather than an agent prompt. Spec, DEC-0001, the shipped policy and the contract now agree. |
| G-4 | fixed | `plan.md` follow-up F-5 lists the open low findings (SEC-001 for headless steps, SEC-002 cap, SEC-006, SEC-008 to SEC-010, ENG-005, ENG-007, ENG-008, ENG-010, ENG-012, ENG-013, TST-005 to TST-012), to be filed as one hardening Issue. SEC-007 is fixed by G-1. The hook's interpreter residual is also fixed: `agent.chat_settings` replaces `python3` with the trusted `sys.executable` by absolute path, and the hook test asserts it. |
| G-5 | handled by the workflow | The driving agent copies this verdict into `reviews/convergence.md`, which `artifacts.check_convergence` and the `spec-reconciliation` gate read. No artifact change is needed for it here. |

These are the only code changes since 110d8c8. They touch only the Chat paths and the Chat test file. The Autonomous and headless engine paths are unchanged, so SC-007 still holds.

What remains:
- **Workflow gates T073 to T077.** The driving agent reports that the full local gate at 110d8c8 ran 790 tests, OK, with none skipped, including the real bwrap and systemd Chat tests, and that ruff is clean. I did not verify this, and it predates `83d04c2`, so T073 and T074 should be recorded again at the final `HEAD`.
- **Manual evidence.** Pilot P-3 to P-5 and quickstart scenarios 1 to 7 need a real TUI and a GitHub remote. Every AC also has a deterministic test, so this evidence adds confidence but does not block convergence.
- **Low follow-ups.** They are tracked as F-5, and none contradicts an AC.

Every AC and SC now has an implementation and deterministic executable evidence, and no actionable gap remains in the spec, plan, contracts or code.

- Verdict: CONVERGED
