# Implementation review 1: security

- Reviewer: Claude Opus 5.5, the driving agent (same provider and same session as the author; not an independent review). A cross-provider security review is still recommended before merge.
- Date: 2026-10-06
- Skill: `.agents/skills/ballast-security-review/SKILL.md`
- Scope: `git diff bc4ea3e..HEAD` on `feat/21-autonomous-reviewed-pr`: `tools/spec_workflow/{run,agent,artifacts,autonomy,draft_pr,branch_sync}.py`, `templates/spec-kit/workflows/autonomous/workflow.yml` 1.2.0, the `ballast` extension commands, policies, ADR-0010.
- Focus (R2): decision authority; provisional versus human approval; resume against branch sync, trust and protected inputs; bounds enforced by trusted code; the authority of `resume` and `checkpoint`; untrusted text in prompts, records and PR text.

```yaml
review: security
verdict: approved   # after the fixes in Resolution; changes_required as found
findings:
  - id: SEC-001
    severity: medium
    category: implementation bug
    invariant: FR-021 (bounds enforced by trusted code)
    location: tools/spec_workflow/run.py:_clock, _run_autonomous
    description: >
      Opening the active-time clock swallowed an AutonomyError and the start
      went on. With no open invocation, `remaining_seconds` would not count the
      invocation's time, so the wall-time bound failed open for that run.
    required_action: Fail closed: no engine without an open clock; a block that says why.
  - id: SEC-002
    severity: low
    category: implementation bug
    invariant: BL-INV-006, FR-010
    location: tools/spec_workflow/run.py:_resume_locked; autonomy.py:_resolution_lines
    description: >
      The block-resolution human decision was appended before the legacy
      active-time seeding and the reset computation; a failure there left a
      recorded resolution without a resume, and the record rendered any such
      resolution as "the run continued human-gated", a mode change that never
      happened.
    required_action: Compute everything that can fail before the decision; render only what happened.
  - id: SEC-003
    severity: low
    category: implementation bug
    invariant: FR-018, T043
    location: tools/spec_workflow/artifacts.py:check_step_drafts, _step_draft
    description: >
      Two new DraftError messages carried an agent-chosen draft file name
      unquoted, so `_retry_message` kept it in the retry note and the record
      (approval wording and markers were already replaced).
    required_action: Quote the name so the retry message drops it as a draft value.
  - id: SEC-004
    severity: info
    category: spec ambiguity
    location: tools/spec_workflow/run.py:_resume_refusal
    description: >
      A run whose invocation is live in a pre-#21 runner process holds no
      invocation lock, so a resume started during an upgrade would treat it
      as interrupted. Upgrades happen between invocations; noted, not fixed.
    required_action: none
```

## What was examined

- **Provisional versus human approval.** The only new human record is `block-resolution`, appended by `run.py` from the operator's command after the synchronization passes (`_resume_locked`), with `resolves: block`. `--ref` matching `HUMAN_APPROVAL` is refused (`ResumeTests.test_ref_must_not_read_as_an_approval`); `--ref` text is rendered through `neutralize` (`test_reference_is_neutralized_in_the_record`). Fix, recheck and retried decisions stay `decisions.jsonl` entries rendered `(agent-provisional, after N retries)`. The approval-wording guard is unchanged and now also drives retries; a quotation of an approval is still refused (`RetryEngineTests.test_quoted_approval_retried`). The PR body guard and the packet's own guard are unchanged (`ProvisionalGuardTests`).
- **Resume and the trust boundary.** Resume runs from the launcher-verified copy after the tamper-marker check, refuses while the in-progress marker exists, and calls `branch_sync.synchronize` with the pinned feature before any record or agent step; a synchronization block (protected input, unpinned run, dirty tree) records only an `upstream-sync` block and no human decision (`test_protected_input_fails_closed`, `test_unpinned_run_blocks_with_manual_step`, `ResumeEngineTests`). A pin naming another feature than the record is refused. The launcher's trust check covers a protected change during the pause (`launcher._refusal`). The engine reposition writes only `.specify/workflows/runs/<id>/state.json`, which agents can neither write (bubblewrap, wrapper digest) nor influence: the step list comes from the run's own workflow copy and the re-entry step is never later than the failed step, so no validator is skipped.
- **Mode and limits.** Resume refuses `-i`, `--mode`, `--wall-time` and `--max-agent-steps`, never calls `change_mode`, and leaves mode history, risk, limits, integrations and eligibility byte-identical (`ResumeRunTests`, `test_resume_keeps_mode_and_limits`, `ModeAuthorityTests`). `stopped → active` exists only in `resume_run`, which requires a recorded `block-resolution`.
- **Bounds.** Fix cycles are counted by `record-fix` in operator state and capped by the recorder; resume keeps the count (`test_cycles_survive_a_resume`). The wrapper skips idle fix steps from the operator record, before counting. Every retry is a full attempt with its own limit check, confinement, scope, in-progress marker and protected-input check; a tamper is never retried (`EXIT_TAMPERED` is not checked). Wall time counts active time, and a dead invocation is closed at its last record (`test_active_invocation_refuses_and_a_dead_one_is_interrupted`).
- **New commands.** `checkpoint` refuses a non-Autonomous run, takes the lock, starts no agent, never creates a PR and writes no run record (`CheckpointTests`); `resume` and `publish` take the same lock. Neither command merges, marks ready or force-pushes (argv assertions).
- **Untrusted text.** Check output reaches the fix agent only through `.specify/workflow-state/fix-input/<slug>.json` (read-only to agents), printable and capped at 4000 characters per command; the record and packet never show it. Retry notes carry validator messages with quoted values, approval wording and markers replaced, printable and capped at 500 characters (`UntrustedTextTests`). Agent permissions are byte-identical to before (`PermissionsUnchangedTests`, `FixLoopTests.test_check_failure_reaches_fix_input_only`).

## Resolution

SEC-001: `_clock` returns False on failure and `_run_autonomous` records a postcondition block without starting the engine (`ResumeTests.test_clock_that_cannot_start_runs_no_engine`). SEC-002: `_resume_locked` computes re-entry, seeding and reset before `append_human_decision`; `_resolution_lines` says "the run continued human-gated" only for a decision named by a lowering, and "the run did not resume" otherwise (`RecoveryRenderTests.test_resolution_without_a_resume_is_not_misreported`). SEC-003: names are quoted (`StepDraftTests`). Fixed in `2b79b8a`.
