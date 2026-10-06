# Implementation review 1: engineering (and architecture)

- Reviewer: Claude Opus 5.5, the driving agent (same provider and session as the author; not independent).
- Date: 2026-10-06
- Skill: `.agents/skills/ballast-engineering-review/SKILL.md`
- Scope: `git diff bc4ea3e..HEAD`; spec FR-001–FR-027; plan, research R1–R20, data model, contracts; ADR-0004, ADR-0005, new ADR-0010.

```yaml
review: engineering
verdict: approved   # after the fixes below
findings:
  - id: ENG-001
    severity: medium
    location: tools/spec_workflow/run.py:_engine_steps
    invariant_or_requirement: R7
    evidence: >
      The first version read step IDs from `- id:` lines only. The engine
      dumps its workflow copy with `yaml.safe_dump(sort_keys=False)`, so that
      holds today, but a dump with another key order silently produced a
      partial step list and a wrong re-entry (seen in the offline harness).
    required_action: Parse the items of the top-level `steps:` list whatever the key order; an item without an ID makes the list unusable and the resume refuses.
  - id: ENG-002
    severity: medium
    location: tools/spec_workflow/run.py:_resume_refusal
    invariant_or_requirement: data-model resume eligibility (upstream-sync raised by a resume resumes)
    evidence: >
      `autonomy.resumable` excludes `upstream-sync`, so a resume's own
      synchronization block fell through to the limit refusal and could never
      be resumed (caught by ResumeEngineTests).
    required_action: Refuse `upstream-sync` only without engine state; reserve the limit refusal for `limit` blocks.
  - id: ENG-003
    severity: medium
    location: tools/spec_workflow/draft_pr.py:checkpoint
    invariant_or_requirement: AC-025
    evidence: >
      With `create=False`, an unpublished branch ended `pending
      (not-published)`, which records a ledger event and a packet, while AC-025
      requires "no Draft PR" to refuse and write nothing.
    required_action: Map `pending` and `blocked-unlinked` to `skipped`/`no-draft-pr` when not creating.
  - id: ENG-004
    severity: low
    location: specs/21-autonomous-reviewed-pr/decisions.md
    invariant_or_requirement: SC-004, AC-009, #18 FR-006
    evidence: >
      A resume after the base advanced blocks once as `dirty`: the paused run's
      work is uncommitted and #18 never commits it.
    required_action: DEC-0001 (resolved: keep #18's rule, document the recovery).
```

## Behavior and boundaries checked

- **Fix loop (FR-001–FR-003, R1–R3).** The fix-needed rule (non-approved verdict, high/critical finding, medium `open`, failed latest feedback check), the state table of the data model, the three-cycle cap, and the R19 guard for 1.1.0 workflow copies are implemented in `artifacts.review_rule`, `record_decision` and `record_fix`; the second guard refuses decision resolution unless the fix state is idle and the tree frozen. The wrapper and the shell steps read the state from `run.json`; `run-checks --feedback` runs exactly when a cycle is under review or before the first review (idle, no frozen tree), which distinguishes `checks-implementation` from an idle `checks-fix-N` without changing the contract's argv.
- **Supersession.** A single point recorded again supersedes its current decision; a review point supersedes every current entry of the point (and specialist reviews for implementation review), so the final-acceptance "one current per point" rule holds across fix cycles and resumes. `supersedes` may now be a list; `superseded`, `current_decisions` and `append_decision` accept both forms.
- **Resume (R5–R8, R13).** Order: arguments, tamper marker, eligibility, lock, eligibility again under the lock, interrupted handling, synchronization, re-entry, decision, `resume_run`, record render, feature pointer, engine reposition, engine, clock close, `_finish`, archive, checkpoint. A failure after the decision blocks the run as a postcondition rather than leaving it active. The block-time input snapshot is kept across a synchronization block (otherwise a change made before the first resume attempt would be lost).
- **Retries (R4).** `check_step_drafts` calls the recorder's own validators; only `DraftError` is retried; `_qualifying_steps` ignores refused attempts so a refused draft is never recorded.
- **Architecture.** ADR-0010 records the amendment of ADR-0004's continuation rule; ADR-0005's "synchronize before any agent step" and "pin from operator state only" hold. The default step limit change (30 → 40) is recorded in ADR-0010 and R9. No new dependency; stdlib only (`fcntl` for the lock).
- **Complexity.** The retry loop moved the wrapper body into `_attempt` without changing the human-gated path (a single attempt, no draft check, same argv, `HumanGatedUnchangedTests`). No unrelated refactor.

## Resolution

ENG-001–ENG-003 fixed and tested (`EngineStepListTests`, `ResumeTests.test_unpinned_run_blocks_with_manual_step`, `RefreshOnlyTests.test_unpublished_branch_is_skipped_too`); ENG-004 recorded as DEC-0001.
