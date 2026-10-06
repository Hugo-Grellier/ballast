# Implementation review 2: security (independent)

- Reviewer: Claude Fable 5.1, a different model and session from the author (Claude Opus 5.5, whose `security-1.md` was same-session). Read-only review; no code changed.
- Date: 2026-10-06
- Skill: `.agents/skills/ballast-security-review/SKILL.md`
- Scope: `git diff origin/main...HEAD` on `feat/21-autonomous-reviewed-pr` at `95736de`: `tools/spec_workflow/{run,agent,artifacts,autonomy,draft_pr,branch_sync}.py`, `templates/spec-kit/workflows/autonomous/workflow.yml` 1.2.0, the `ballast` extension commands, policies, ADR-0010 and the `tests/` diff. Governing texts read: CLAUDE.md, security and workflow policies, constitution BL-INV-006, spec, plan, research R1–R20, the three contracts, DEC-0001, `security-1.md`, `test-1.md`, `spec-reconciliation.md`, ADR-0004 (amended) and ADR-0010.
- Focus (R2): whether any path lets a provisional decision read as human approval or lets an agent resolve its own block; resume safety against branch sync, launcher trust, tamper and in-progress markers, the run-format check and the per-run lock; bounds enforced from operator state; the fix loop's write scope; `checkpoint` authority; untrusted text in prompts, terminal and records; weakened tests.

```yaml
review: security
verdict: changes_required
findings:
  - id: SEC2-001
    severity: medium
    category: implementation bug
    invariant: BL-INV-006, FR-012, ADR-0004 ("no path raises a run to Autonomous"), R13
    location: tools/spec_workflow/run.py:1136 (_continue_command), :1445-1510 (_resume_locked); tools/spec_workflow/autonomy.py:636 (resume_run)
    description: >
      `ballast run continue` is the one run-mutating command that does not
      take the per-run invocation lock (holders: start :663, publish :1064,
      checkpoint :1088, resume :1439), and `_resume_locked` resumes from the
      `record` dict it read before branch synchronization (:1448) without
      re-reading it afterwards; `resume_run` mutates and validates the dict it
      is handed and never reads `run.json`. Race: a resume holds the lock and
      sits in `_sync` (fetch, rebase); the operator, or a second session or
      automation acting on the same blocked run, runs `continue RUN_ID`.
      `continue` passes `_continue_refusal` (status still `stopped`), records
      the `mode-change` human decision, `change_mode` + `set_status(continued)`
      and starts `ballast-continue`. The resume then appends its
      `block-resolution` and calls `resume_run(ROOT, record)` with the stale
      dict: status `stopped` in memory, so the transition passes and
      `write_run` overwrites `run.json` with status `active` and a
      `mode_history` without the lowering. Result: a run the operator just
      lowered runs in Autonomous again with the lowering erased from the
      authority record, while a `ballast-continue` run with
      `continues=RUN_ID` runs the human-gated gates in the same worktree.
      Not reachable by an agent (both commands are operator-only, operator
      state is read-only inside bwrap), so no agent gains authority; it is a
      lost-update defect in the record that decides mode.
    required_action: >
      Take `_invocation_lock(run_id)` of the source run in `_continue_command`
      around sync, record and launch (the plan's R13 and the module docstring
      list only start/resume/publish/checkpoint). In `_resume_locked`,
      re-read `run.json` and `block.json` after `_sync` and before
      `append_human_decision`, and refuse (no human decision, no block
      change) when status, mode history or block differ from what the
      eligibility check saw. Tests: `continue` while another invocation holds
      the lock is refused with "has an active invocation"; a resume whose
      record changed during sync refuses and appends no `block-resolution`.
  - id: SEC2-002
    severity: low
    category: implementation bug
    invariant: FR-023, AC-026 (every stop names the operator's next action)
    location: tools/spec_workflow/run.py:1104-1133 (_continue_refusal), :1352-1358 (_resume_refusal, fixed limits); tools/spec_workflow/autonomy.py:981 (recovery_command)
    description: >
      A `limit` block with kind `agent-steps` or `wall-time` before
      implementation (no `implementation-baseline.json`, for example at
      `decide-tasks` after a rewind spent the steps) is unrecoverable by the
      two commands that point at each other: the block's own `command`
      (`recovery_command` -> `ballast run continue ...`) and `resume` both
      say "continue human-gated", and `continue` refuses with "stopped before
      implementation; resume it in Autonomous". Only the unnamed third option
      (a new run with a larger limit) works. No authority impact.
    required_action: >
      In `_continue_refusal`, point to `resume` only when
      `autonomy.resumable(block["category"], block.get("limit"))`; for a
      fixed-limit block without a baseline name `RESTART_COMMAND` (and have
      `recovery_command` do the same, or let `run.py` pass `command=`). Test:
      a pre-implementation `limit`/`agent-steps` block; both commands and the
      printed `Next:` name the restart.
  - id: SEC2-003
    severity: low
    category: missing test
    invariant: FR-001/AC-002 ("a fix step addresses it"); `speckit.ballast.fix` "Never" list
    location: tools/spec_workflow/artifacts.py:2705 (record_fix), :2772 (check_step_drafts), :2198 (_reviewer_tree_check); tools/spec_workflow/agent.py:454 (_review_exclusions)
    description: >
      The recorders do not relate fix outputs to the findings that triggered
      the cycle. `record-fix` checks only that the last unconsumed step was a
      `speckit-ballast-fix` that exited 0 and that `check_implementation`
      holds; `record-decision --recheck` accepts any valid review, including
      one that lists none of the fix input's finding IDs with verdict
      `approved`, after which the tree is frozen. The fix command's rule
      "never edit `<f>/reviews/`" is unenforced: `_reviewer_tree_check` runs
      for reviewer steps only and every step's `tree_before` excludes
      `reviews/` and `drafts/`, so the fix (author) agent may rewrite the
      previous review reports the recheck reviewer is told to read.
      Mitigations in place: the fix input lives under `.specify/` (read-only
      to agents, written by the recorder from the operator log), the recorded
      findings are in `decisions.jsonl`, the recheck reviewer rewrites every
      report and draft, and in cross-provider runs it is another provider.
      The trust anchor is therefore the independent reviewer, as in #27; the
      gap is that a careless or single-provider recheck can clear findings
      without the recorder noticing.
    required_action: >
      In `check_step_drafts` and `record_decision` for `implementation-recheck`
      / `specialists-recheck`, require each finding `id` of the current fix
      input (keyed by its review `kind`) to appear in the recheck's findings
      with some disposition; a missing one is a `DraftError` (correctable, so
      it retries). In `record_fix`, digest `<f>/reviews/` before the fix step
      (store it in the wrapper's step entry next to `tree_before`) and block
      `postcondition` when it changed. Tests: a recheck that omits a listed
      finding is refused and retried; a fix step that edits a report blocks.
  - id: SEC2-004
    severity: low
    category: implementation bug
    invariant: security policy "treat model output as untrusted"; pre-existing from #27, widened in reach by #21
    location: tools/spec_workflow/autonomy.py:1041 (_text), :1152 (validate_block_draft); tools/spec_workflow/artifacts.py:1766 (_text_field); tools/spec_workflow/run.py:957 (_print_block)
    description: >
      Agent-authored block text reaches the operator's terminal unneutralized.
      `_text` and `_text_field` check length, approval wording and markers,
      not printability, and `_print_block` writes `condition`, every option
      and `recovery` raw to stdout. An agent's `block.json` may carry ANSI,
      OSC or carriage-return sequences that erase or rewrite the printed
      `Recovery:` and `Next:` lines at the moment the operator decides what
      to run next (`resume`, `continue`, `discard-runs`). #21 made the new
      texts it introduced printable (`_retry_message` :468, `_printable` for
      the fix input) and `neutralize`s what the record renders, but this
      pre-existing path is now the one the operator reads before every
      resume. The record is unaffected (block conditions are not rendered
      there).
    required_action: >
      Enforce printable text (keep `\n` and `\t`) in `_text` and
      `_text_field`, or escape non-printables in `_print_block`. Test: a block
      draft whose condition contains `\x1b[2K` is refused (or printed with
      the escape replaced).
  - id: SEC2-005
    severity: info
    category: missing test
    location: tests/test_autonomous_run.py (test_reviewer_role, planted-draft test), tests/test_autonomous_recovery.py (RetryEngineTests)
    description: >
      The two wrapper tests moved from `/speckit-ballast-review plan` to
      `/speckit-ballast-review audit`. `plan` now has a draft contract
      (`plan-review`), so the fake agent's missing draft would be retried
      twice and exit `EXIT_LIMIT`; `audit` has none. The assertions kept
      (reviewer role from the command name, planted-draft capture) do not
      depend on the argument, and the retry contract is pinned by
      `RetryEngineTests` (`test_retries_exhausted_blocks_limit`,
      `test_step_limit_during_retry`). No regression is hidden. The rest of
      the removed test lines are message or default changes (block class
      prefix, limit 30 -> 40, active time replacing `deadline`, the lifted
      `RESUME_REFUSAL`, the 1.2.0 run-format digest with its recorded basis,
      intent drafts now citing the discovery brief).
    required_action: none required; optionally one wrapper-seam test with `plan` asserting exit 5 after three attempts.
  - id: SEC2-006
    severity: info
    category: architecture issue
    location: tools/spec_workflow/launcher.py:66-73 (SKIPPED), tools/spec_workflow/run.py:789 (_engine_steps), :827 (_reposition_engine); tools/spec_workflow/artifacts.py:2367 (fix_loop)
    description: >
      The per-run workflow copy and engine state under
      `.specify/workflows/runs/<id>/` are outside the launcher's trust
      baseline (the engine writes there) and are protected from agents by
      bubblewrap plus the wrapper's digest check. #21 makes trusted code read
      them for step order, re-entry and fix-loop presence. Both tamper
      directions during a pause fail closed: removing `speckit.ballast.fix`
      makes `fix_loop` False and findings block as in #27; adding it to a
      1.1.0 copy sets `fix-pending` that no step consumes and
      `record-resolutions` refuses a non-idle fix state. Noted, no action.
    required_action: none
  - id: SEC2-007
    severity: info
    category: spec ambiguity
    location: tools/spec_workflow/run.py:1375-1399 (_reentry)
    description: >
      A block recorded without `inputs` (a run stopped before this change)
      yields no change detection on resume: `recorded` is empty, so
      `current` is not computed and the run re-enters at the block step even
      if the spec was edited during the pause. `renew-intent` and every
      validator after the block step still run, so stale intent is caught
      later rather than at `validate-spec`. Worth one sentence in the
      policy's resume section.
    required_action: none required
```

## What was examined

- **Provisional versus human approval (focus 1).** The only new human record is `block-resolution`, appended by `run.py` from the operator's command after synchronization (`_resume_locked` :1493), with `resolves: block`; `--ref` is refused when it matches `HUMAN_APPROVAL` (`_resume_options` :1283) and neutralized when rendered (`_resolution_lines`). `resume_run` is the only `stopped -> active` transition and requires that recorded `block-resolution` by ID. No agent can run `resume`, `continue` or `checkpoint`: the launcher executes `run.py` with operator authority after the trust, tamper and in-progress checks, and inside bubblewrap the operator state is read-only. Fix, recheck and retried decisions stay `decisions.jsonl` entries rendered agent-provisional ("after N retries"); `_guard_body` still refuses a PR body with approval wording. The retry loop reruns the agent with the recorder's message only; a draft that quotes an approval is refused and retried, and `_retry_message` drops quoted values, approval wording and markers before the text enters the prompt or the record. An agent cannot resolve its own block: a block draft ends the step (exit 3), `run.py` records it, and only the operator's `resume` or `continue` continues.
- **Resume safety (focus 2).** Every resume passes the launcher (`_refusal`: trust baseline, tamper marker, in-progress marker, setup lock and pin match), then `run.py`'s tamper check, `_resume_options`, `_resume_refusal` (continued, completed, published, non-autonomous, in-progress, publish-retry and discard categories, fixed limits, missing engine state), the pin/record feature match, the lock, and `branch_sync.synchronize` with the feature read from the pin (ADR-0005) before any record or agent step. A sync block, protected-input change included, records only an `upstream-sync` block whose command is `ballast run resume` and keeps the earlier block's input snapshot (DEC-0001); no human decision is written. Resuming that block works because `upstream-sync` is refused only when no engine state exists (:1348). The re-entry step is never later than the failed step (`_reentry`), so no validator is skipped; `_reposition_engine` writes only the engine's own `state.json` under `.specify/`, atomically, and drops later `step_results`. The lock is `flock(LOCK_EX|LOCK_NB)` on an operator-state file with `O_NOFOLLOW|O_CLOEXEC`, released by the kernel on process death, so no stale lock can exist; an `active` record with a free lock is closed at its last recorded time and blocked `interrupted`. The gap found is the `continue` command outside the lock and the stale record across sync (SEC2-001).
- **Bounds (focus 3).** `FIX_CYCLES`, `DRAFT_RETRIES` and `AGENT_STEPS` are constants in trusted code; `fix.cycles`, `agent_steps`, `active_seconds` and `invocation_started_at` live in `run.json` (operator state) and `_validate_progress` bounds them. `record_fix` increments cycles only from `fix-pending`; `review_rule` grants a cycle only while `cycles < 3`, so `fix-pending` is never set with no fix step left; `resume_run` keeps cycles and `_validate_progress` refuses more than three. Every retry attempt passes `_autonomous_run` (wall time, step count, confinement) before the agent starts, so retries cannot exceed the step limit; after a resume a step gets fresh retries by design, still under the step limit. Wall time counts only open invocations, is closed in `finally`, and a crash is closed at the last recorded moment, never at the resume. Resume refuses every mode and limit flag and never writes `mode_history`, `risk`, `limits` or integrations.
- **Fix loop (focus 4).** The fix agent runs confined with the implement step's authority: writable worktree minus the protected inputs, no `[checks]` execution, no `gh`. Check output reaches it only as `.specify/workflow-state/fix-input/<slug>.json`, written by the recorder (`_write_fix_input` :2441), printable and capped at 4000 characters per command; agents cannot write under `.specify/` (bubblewrap read-only, wrapper digest, tamper marker). Headless permission arguments are unchanged (`permission_args`, `CONFINED_ALLOW/DENY`, `claude-settings.json` untouched). A draft written by the fix agent cannot be recorded (`step_points` returns none for `speckit.ballast.fix`; the next reviewer step sets stray drafts aside; `_qualifying_steps` for a review point takes trailing reviewer steps only). Editing `record.md` fails the preamble, `intent.md` with an approval block fails `record-fix` (tested), and a spec edit is caught by `renew-intent`. The recorders do not, however, relate the recheck to the fix input or protect `reviews/` from the fix step (SEC2-003).
- **`checkpoint` (focus 5).** Dispatched after the tamper check and before the `specify` lookup; `_source_run` requires a valid `RUN_ID` and a `ballast-autonomous` record; the lock is taken; `draft_pr.checkpoint(create=False)` turns a missing PR, an unpublished branch (`pending`) and an unlinked run into `skipped`/`no-draft-pr` with no ledger event, packet or run-record write, and the command refuses. The reuse path edits the PR body only (`gh pr edit`); `draft_pr.py` never pushes, changes readiness or merges, and `checkpoint` writes none of `run.json`, the logs or `record.md`.
- **Untrusted text (focus 6).** Prompt: the retry note carries a validator message with quoted values, approval wording and markers replaced, printable, 500 characters. Record and PR body: `neutralize` on refs, refusals, summaries and notes; the PR body guard. Terminal: retry reasons and limit conditions are printable; block-draft text is not (SEC2-004). Ledger: `steps.jsonl` and `checks-feedback.jsonl` are written only by the wrapper and `run-checks` in operator state.
- **Tests (focus 7).** `git diff origin/main...HEAD -- tests` removes no assertion without a replacement; see SEC2-005. `tests.test_autonomous_recovery`, `tests.test_autonomous_run` and `tests.test_autonomy` were run offline (`uv run --no-project --isolated --python 3.13 --with pyyaml python -m unittest ...`): 231 tests, OK; the host-dependent cases skip as in CI.

## Verdict

- Verdict: changes requested. SEC2-001 is the blocker and is a small change (one lock in `continue`, one re-read in `_resume_locked`, two tests); SEC2-002 to SEC2-004 are low and can ride along or follow; the rest is informational.
