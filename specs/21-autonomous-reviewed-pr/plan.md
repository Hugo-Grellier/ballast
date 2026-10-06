# Implementation Plan: Reach a reviewed PR with provisional Autonomous decisions

**Branch**: `feat/21-autonomous-reviewed-pr` | **Date**: 2026-10-06 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/21-autonomous-reviewed-pr/spec.md` (intent agent-provisional, PD-0013, digest in [intent.md](intent.md)); discovery brief [discovery.md](discovery.md) as input evidence.

**Risk**: R2 (agent authority, approval gates, what the launcher executes). **Mode**: Autonomous run `fcba2ba4`. Every decision here is agent-provisional; merging the PR is the only human approval.

## Summary

Autonomous runs stop being one-shot. Four mechanisms, all in trusted code, close the gaps the pilots hit:

1. **Bounded fix loop** (US1). `ballast-autonomous` 1.2.0 runs the `[checks]` commands as feedback after implementation. The implementation reviews then decide whether a fix is needed. Three unrolled fix cycles (fix, record, feedback checks, recheck reviews, record) run only while the operator-state fix state asks for them; otherwise the agent wrapper skips them at no step cost. The count is three cycles per run and never resets. After the third cycle, a high or critical finding or a non-approved verdict blocks as an exhausted limit. Check output reaches the fix agent only through a trusted, read-only fix input file, so the headless agent's permissions are unchanged ([R1–R3](research.md)).
2. **Autonomous resume** (US2). `ballast run resume RUN_ID [--ref TEXT]` no longer refuses. It checks the run's status and block, takes a per-run lock and runs branch synchronization before any agent step. It then records a `block-resolution` human decision and computes the re-entry step: the block step, or earlier when a spec, plan, tasks or code input changed during the block. The engine is repositioned there and the run continues in Autonomous with its recorded mode, risk and limits. Wall time counts only active invocation time. ADR-0007 amends ADR-0004's continuation rule ([R5–R8](research.md), [R17](research.md#r17-adr-0007)).
3. **Correctable draft retries** (US3). Right after an Autonomous agent step, the wrapper runs the recorder's own draft-contract validators. A `DraftError` (length, format, approval wording, missing draft or path) reruns the agent at most twice, with the validator's message, each attempt counting against the step limit. State refusals stay terminal. Commands state the limits and the paraphrase rule, and the tasks template keeps workflow-owned steps out of `tasks.md` ([R4](research.md#r4-correctable-refusals-retried-inside-the-agent-wrapper), [R16](research.md#r16-commands-templates-and-the-tasks-template)).
4. **Packet refresh and actionable stops** (US4–US6). `ballast run checkpoint RUN_ID` refreshes the Draft PR checkpoint and acceptance packet of an Autonomous run in any status without an agent, and refuses, writing nothing, when no Draft PR exists. Every block names its class and its next command. The record shows the fix loop, block resolutions, retries and the spend statement ([R12–R15](research.md)).

Implementation order follows the spec's assumption: resume and retries first (they unblock the pilot), then the fix loop, then refresh, documentation and the ADR.

## Technical Context

**Language/Version**: Python ≥ 3.11 standard library only. `run.py`, `artifacts.py` and `agent.py` run under `python3 -I -S` from the installed `.ballast/` copy.

**Primary Dependencies**: none new. External programs are unchanged: Spec Kit `specify` ≥ 1.0.11 (engine), `git`, `gh`, `bwrap`, `systemd-run`, and the `claude`/`codex` CLIs through the wrapper.

**Storage**: operator state outside the worktree. `run.json` gains `fix`, `resumes`, `active_seconds` and `invocation_started_at`, plus a new `stopped → active` transition. `block.json` gains `limit` and `inputs`. New files: `checks-feedback.jsonl` and `invocation.lock`. Agent-read-only `.specify/workflow-state/fix-input/<slug>.json`. Engine `state.json` is repositioned by `run.py` on resume. See [data-model.md](data-model.md).

**Testing**: `unittest`, mostly offline, with the existing fake agent and fake `specify` fixtures, temporary Git repositories, a bare `origin`, an injected clock and argv logs. Real-engine and real-confinement scenarios run only in the full local gate. See [quickstart.md](quickstart.md).

**Target Platform**: the qualified 1.0 host: Linux, systemd user session, bubblewrap, authenticated `gh`, GitHub.

**Project Type**: workflow tooling of the installed standard (`tools/spec_workflow/`, `templates/spec-kit/`, `templates/policies/`).

**Performance Goals**: a skipped fix-cycle step costs one wrapper start and no agent. Resume adds one branch sync, a few file digests and one atomic state rewrite before the engine starts. Checkpoint costs #17's and #19's calls and nothing else.

**Constraints**: no validator, guard or permission is relaxed (FR-017, FR-018, FR-003). Protected inputs fail closed. The mode is never raised. No merge, deploy or destructive action. Agent text, check output and validator messages enter prompts and PR text only bounded and neutralized.

**Scale/Scope**: about 300 lines in `artifacts.py` (fix state, `record-fix`, `run-checks --feedback`, `check_step_drafts`, `DraftError`, supersession, re-entry inputs), 250 in `run.py` (resume, checkpoint, lock, engine reposition, clock), 150 in `agent.py` (skip and retry loop), 150 in `autonomy.py` (record fields, transitions, block classes, active time, rendering), about 10 in `draft_pr.py` (`create=False`). Plus 18 workflow steps, one new command, five command edits, the tasks template, two policy files, ADR-0007, README, and one new test file with extensions to five existing ones.

No open clarification remains. One engine assumption (R7) is verified first by T001, with a recorded fallback.

## Constitution Check

*Gate before Phase 0, re-checked after Phase 1. Result: **PASS** both times, no violations.*

| Principle | How the design holds it |
| --- | --- |
| 1. Projects own only their files (BL-INV-001) | Every change lands in installed, git-ignored material (`tools/spec_workflow/`, workflow, commands, templates, policies) or in operator state outside the worktree. The only committed project file a run touches is still `autonomous/record.md`, rendered by recorders. |
| 2. Nothing executes from a writable checkout (BL-INV-002) | Resume and checkpoint run from the launcher-verified `.ballast/` copy, after the tamper-marker check. The engine state rewrite is done by `run.py` under `.specify/`, which agents see read-only. Retries run inside the trusted wrapper with the same confinement, scope, in-progress marker and protected-input check per attempt. |
| 3. Delegated authority (BL-INV-003) | `claude-settings.json`, `CONFINED_ALLOW`/`CONFINED_DENY` and the Codex sandbox flags are unchanged. A test asserts it. Check results reach agents only as a read-only data file. Resume refuses `-i`, `--mode` and limit flags, and never writes mode, risk, limits or integrations. The pin is read only from operator state. A protected-input change on resume or sync blocks with `ballast trust` as the recovery. |
| 4. A project picks a version, never a source (BL-INV-004) | Not touched. |
| 5. Postconditions over exit codes (BL-INV-005) | A skipped step proves nothing and is followed by a shell step that checks the fix state. `record-fix` runs `check_implementation`. The recheck recorder re-derives "fix needed" from recorded drafts and check logs. `decision-resolution` refuses a non-idle fix state. The final `run-checks` and every #27 postcondition stay. |
| 6. Portable, dependency-free tools | Standard library only. `flock` comes from `fcntl`. The engine step list is read from `- id:` lines of the run's `workflow.yml` copy, not with a YAML library. |
| 7. Generic by default | No project names. The fix loop uses the project's own `[checks]`. |
| 8. Executable evidence | Every AC maps to a named scenario in [quickstart.md](quickstart.md), including refusals, tamper, protected-input, exhausted limits and old-workflow paths. |
| 9. A provisional decision is never human approval (BL-INV-006) | Fix, retry and recheck decisions are agent-provisional entries. The only new human record is `block-resolution`, written by the operator command, and its `--ref` is refused when it reads as an approval. The approval-wording guard is unchanged and now also drives retries. Validators still refuse every human-approval record in an Autonomous run. Merge stays the single approval. |

## Architecture Boundaries

- **Affected areas**: the trusted launcher-side runner `tools/spec_workflow/run.py` (resume, checkpoint, continue refusal, invocation lock, active-time clock, engine reposition, block snapshot); the operator record model `tools/spec_workflow/autonomy.py`; the trusted shell-step validators and recorders `tools/spec_workflow/artifacts.py`; the agent wrapper `tools/spec_workflow/agent.py`; the PR checkpoint `tools/spec_workflow/draft_pr.py` (reuse-only switch); branch sync recovery text in `tools/spec_workflow/branch_sync.py`; the Autonomous workflow definition and `ballast` Spec Kit extension commands; the tasks template; policies and ADRs.
- **Contracts and data flow**:
  - Fix loop: `run-checks --feedback` → `checks-feedback.jsonl` → implementation-review recorder (drafts plus feedback) → `run.json.fix` and the fix input file → wrapper gate → `speckit.ballast.fix` → `record-fix` → feedback checks → recheck reviews → recheck recorder. See [contracts/workflow-steps.md](contracts/workflow-steps.md).
  - Retry: wrapper → agent → `artifacts.check_step_drafts` → `DraftError` → set-aside and rerun with the message → `steps.jsonl` attempts → recorder takes the last attempt. See [contracts/draft-retry.md](contracts/draft-retry.md).
  - Resume: CLI → eligibility → lock → `branch_sync.synchronize` → re-entry from block-time inputs → `append_human_decision` → `resume_run` → record render → engine reposition → `specify workflow resume` → `_finish` → checkpoint. Checkpoint: CLI → lock → `draft_pr.checkpoint(create=False)` → packet. See [contracts/cli-commands.md](contracts/cli-commands.md).
  - Sources of truth are unchanged. Operator records hold mode, limits, decisions and the fix state. The pin holds branch and feature. Spec Kit artifacts hold intent. The ledger holds evidence. The record and packet are projections.
- **Architecture references**: [constitution](../../.specify/memory/constitution.md) BL-INV-002, -003, -005, -006; [ADR-0004](../../docs/adr/0004-autonomous-provisional-decisions.md) (continuation rule amended); [ADR-0005](../../docs/adr/0005-launcher-branch-synchronization.md) (sync before any agent step, pin from operator state, DEC-0006 unpinned rule kept); [ADR-0006](../../docs/adr/0006-review-packet-reads.md) (packet reads, unchanged); [technical spec §61 fix loop](../TECHNICAL-SPEC.md#61-fix-loop) and [§91 v1.0 target](../TECHNICAL-SPEC.md#91-v10-target); [workflow policy review triggers](../../docs/policies/workflow.md#review-triggers); #27 [data model](../27-autonomous-core/data-model.md); #19 [DEC-0002](../19-acceptance-packet/decisions.md#dec-0002--resolution).
- **Proposed architecture decisions** (agent-provisional here; the merge approves them):
  1. **ADR-0007 Autonomous resume and bounded recovery** ([R17](research.md#r17-adr-0007)). A blocked or interrupted Autonomous run resumes in Autonomous through branch synchronization, with a recorded `block-resolution`, re-entry at the earliest changed input, and the trusted runner repositioning the engine. Implementation findings run a fix loop of three cycles per run, and correctable draft refusals retry twice per step. Amends ADR-0004's "recovery is always human-gated until #18". `continue` remains the human-gated path.
  2. **Default agent-step limit 30 → 40** ([R9](research.md#r9-agent-step-default-30--40)), so that three fix cycles and a few retries fit under a limit that resume cannot raise.

## Repository Impact

| Path | Change |
| --- | --- |
| `tools/spec_workflow/run.py` | Autonomous `resume` flow (R5), re-entry computation and engine reposition (R6, R7), block-time input snapshot in `_stop`, active-time clock around `start`/`resume` (R8), `checkpoint` subcommand (R12), invocation lock (R13), pre-implementation `continue` refusal (R10), printed block class (R15), docstring. |
| `tools/spec_workflow/autonomy.py` | Optional run fields and their validation; `stopped → active` via `resume_run`; `remaining_seconds` with active time and the legacy deadline; `AGENT_STEPS` default 40; `FIX_CYCLES`, `DRAFT_RETRIES`, `AUTONOMOUS_STEPS`, `BLOCK_CLASSES`; block `limit`/`inputs`; `recovery_command` and `BLOCK_COMMAND` for resume; `RECOVERY` texts; `RESUME_REFUSAL` removed for Autonomous; `render_record` gains human decisions, fix loop, retries and the spend line. |
| `tools/spec_workflow/artifacts.py` | `DraftError`; `STEP_POINTS` and `check_step_drafts`; `record-fix` check; `run-checks --feedback`; fix-needed rule and fix input file; `--recheck` and automatic supersession; `_qualifying_steps` skips refused attempts; attempts and refusals in entries; disposition rule with the cycle condition; old-workflow guard (R19); `record_baseline` keeps an existing baseline; `decision-resolution` fix-state guard; `_frozen_check` message. |
| `tools/spec_workflow/agent.py` | Fix-cycle skip gate before counting; per-attempt loop with draft check, set-aside, retry note and `EXIT_LIMIT` reasons; `steps.jsonl` attempt fields. The agent argv and permission arguments are unchanged apart from the prompt text. |
| `tools/spec_workflow/draft_pr.py` | `checkpoint(root, run_id, *, create=True)`; `create=False` ends `skipped`/`no-draft-pr` when no PR exists. |
| `tools/spec_workflow/branch_sync.py` | `unpinned` recovery text names the manual pin step (R11). |
| `templates/spec-kit/workflows/autonomous/workflow.yml` | Version 1.2.0: `checks-implementation` and three fix cycles ([contract](contracts/workflow-steps.md)). |
| `templates/spec-kit/extensions/ballast/commands/speckit.ballast.fix.md` | New command. |
| `templates/spec-kit/extensions/ballast/extension.yml` | Register `speckit.ballast.fix`. |
| `templates/spec-kit/extensions/ballast/commands/speckit.ballast.{decide,review,clarify,discover,resolve}.md` | Recorder limits. Decide and review: paraphrase-and-cite. Review: `*-recheck` arguments and the cycle rule. |
| `templates/spec-kit/templates/tasks-template.md` | No tasks for workflow-owned steps (R16). |
| `templates/policies/spec-kit-workflow.md` | Autonomous sections: resume (re-entry, block resolution, what refuses), fix loop, retries, `checkpoint`, active wall time and the spend bound, block classes, "Runs started before branch pinning". All agent-provisional, merge the single approval. |
| `templates/policies/workflow.md` | Replace "blocked Autonomous runs continue only human-gated until #18" with resume plus the fix loop bound; keep the three-cycle escalation rule. |
| `docs/adr/0007-autonomous-resume-and-bounded-recovery.md` | New. |
| `docs/adr/0004-autonomous-provisional-decisions.md` | "Amended by ADR-0007" line on the continuation rule. |
| `specs/TECHNICAL-SPEC.md` | Only where §61 or §91 contradict the shipped behavior; spec reconciliation decides. |
| `README.md` | One sentence on resume and `checkpoint` in the workflow section. |
| `tests/test_autonomous_recovery.py` | New: fix loop, resume, retry, checkpoint, block classes, active time, provisional guard ([quickstart](quickstart.md)). |
| `tests/test_autonomous_run.py`, `tests/test_autonomy.py`, `tests/test_autonomous_artifacts.py`, `tests/test_spec_workflow.py`, `tests/test_draft_pr.py`, `tests/test_governance.py`, `tests/test_branch_sync.py` | Extensions listed in the quickstart; updated `RESUME_REFUSAL`, `unpinned`, default-limit and `frozen_check` expectations. No assertion is weakened. |

`tools/setup`, `tools/ballast`, `tools/cli.toml`, `launcher.py`, `ledger.py`, `packet.py` and `claude-settings.json` are unchanged. `ballast setup` installs the changed templates.

## Feature Artifacts

```text
specs/21-autonomous-reviewed-pr/
├── discovery.md       # input evidence (#16)
├── intent.md          # agent-provisional (PD-0013)
├── spec.md
├── plan.md            # this file
├── research.md        # Phase 0 decisions R1–R20
├── data-model.md
├── contracts/
│   ├── cli-commands.md
│   ├── workflow-steps.md
│   └── draft-retry.md
├── quickstart.md      # validation scenarios mapped to ACs
├── checklists/
├── autonomous/        # run record (rendered by the runner)
├── tasks.md           # next: speckit-tasks
├── decisions.md       # only if implementation discovers one (e.g. the R7 fallback)
└── reviews/
```

## Review notes

- **Required reviews** (R2, [review matrix](../../docs/policies/workflow.md#review-triggers)): engineering; security (agent authority, launcher trust, the engine state rewrite, untrusted check output and validator messages in prompts, `--ref` text); test (refusal, tamper, limit and old-workflow paths); documentation (policies, README, ADR-0007); architecture (ADR-0007 amends ADR-0004).
- **For the plan decision**: confirm R2. Accept ADR-0007 and the step-default change (R9). Note that T001 must confirm the engine reposition (R7) before resume work builds on it. If it fails, the fallback goes to `decisions.md` as a proposal and is not silently adopted.
- **Task ordering** (for `speckit.tasks`): wave 1 is T001 (engine spike) plus record-model groundwork (active time, block fields, classes, lock). Wave 2 is resume and the `continue` refusal, then retries and the `DraftError` split. Wave 3 is the fix loop, workflow 1.2.0 and the fix command. Wave 4 is checkpoint, record rendering, commands, the tasks template, policies, ADR-0007 and README. Per D-07, tasks must not include the full gate, quickstart runs, reviews, converge or reconciliation, which the workflow runs itself.
- **Known limit**: a resume that rewinds far (for example after a post-implementation spec change) spends agent steps again and may block as `limit`. Then the operator continues human-gated. Resume cannot raise limits, by design.

## Complexity Tracking

No constitution violations.
