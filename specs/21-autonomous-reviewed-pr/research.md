# Research: Reach a reviewed PR with provisional Autonomous decisions

Phase 0 decisions for [plan.md](plan.md). Each one is agent-provisional in Autonomous run `fcba2ba4`; merging the PR is the only human approval.

Limits of this research. The planning step ran confined. It could not read the Spec Kit 1.0.11 engine source or run the `specify` CLI. Like #27 ([research](../27-autonomous-core/research.md)), the design relies only on engine behavior this repository already exercises: `command` and `shell` steps, per-step `integration`, `input.args`, run IDs from `SPECKIT_WORKFLOW_RUN_ID`, and `specify workflow resume` of a failed step. One decision (R7) also depends on the engine resuming at a repositioned step. Task T001 verifies that with the real CLI before anything builds on it, and R7 names the fallback. The engine's state shape was read from this run's own state file: `.specify/workflows/runs/<id>/state.json` holds `status`, `current_step_index`, `current_step_id` and `step_results`, and the run directory keeps its own `workflow.yml` copy.

## R1. Fix loop: three unrolled cycles that skip themselves when idle

- **Decision**: `ballast-autonomous` 1.2.0 adds three identical fix cycles between `record-implementation-review` and `resolve-decisions`. Each cycle has six steps:

  | Step | Type | Runs when |
  | --- | --- | --- |
  | `fix-N` | agent `speckit.ballast.fix` | fix state is `fix-pending` |
  | `record-fix-N` | shell `artifacts.py record-fix` | the step before it was a fix that ran |
  | `checks-fix-N` | shell `artifacts.py run-checks --feedback` | fix state is `review-pending` |
  | `review-fix-N` | agent `speckit.ballast.review implementation-recheck` | fix state is `review-pending` |
  | `review-specialists-fix-N` | agent `speckit.ballast.review specialists-recheck` | fix state is `review-pending` |
  | `record-fix-review-N` | shell `record-decision --point implementation-review --recheck` | fix state is `review-pending` |

  The fix state lives in the operator run record (`run.json` field `fix`, [data model](data-model.md#fix-state)). The trusted agent wrapper (`agent.py`) skips an agent step whose condition is false. The skip starts no agent, counts no step and writes no `steps.jsonl` entry. A shell step whose condition is false exits 0 without writing anything. The cycle bound is the persisted counter `fix.cycles`, never the cycle slot. Three slots always cover the three cycles a run may use, even after a resume.
- **Rationale**: the engine has no loop or conditional that this repository exercises. Fixed steps that trusted code skips keep the workflow linear and every agent invocation bounded, and they reuse the wrapper's existing gatekeeping (it already refuses an inactive run or an exhausted limit before starting an agent).
- **Alternatives considered**: a loop or `if` step in Spec Kit (unverified engine support); one fix step that iterates inside an agent (the agent would control the bound); lowering to human-gated on any finding (the status quo, which defeats IAC-1).

## R2. What triggers a fix, and what happens when the cycles run out

- **Decision**: after the implementation reviews (`implementation-review` plus `specialist-review` drafts), the recorder computes **fix needed** when at least one of these holds:
  1. a review verdict is not `approved`;
  2. a finding has severity `critical` or `high`, whatever its disposition;
  3. a finding of severity `medium` or higher has disposition `open`;
  4. the latest feedback check run (R3) has a failed command.

  If no fix is needed, the recorder freezes the tree as today and sets the fix state to `idle`. If a fix is needed and `fix.cycles < 3`, it records the review decisions, writes the fix input (R3) and sets `fix-pending`, without blocking. If a fix is needed and `fix.cycles == 3`, it blocks as `limit` with `limit: fix-cycles`. The block names the open high or critical findings, the failed checks and the recovery (fix by hand and `ballast run resume`, or continue human-gated).

  While a cycle remains, `open` is valid at any severity: it means "fix this". When no cycle remains, the #27 disposition rule applies unchanged: `open` only for `low` and `info`, and `accepted-provisionally` needs a reason. A reviewer that marks a medium finding `open` on the last review gets a correctable refusal (R4). Medium findings left after the loop therefore reach the packet as `accepted-provisionally` with a reason (FR-002), and a non-approved verdict or a high or critical finding after the third cycle still blocks (AC-003). Plan review and spec reconciliation keep #27's rule: a high or critical finding or a non-approved verdict blocks at once.
- **Rationale**: no validator weakens (FR-017). The only new permission is "open means fix" while a cycle remains, and the stricter rule returns on the last review. AC-001's medium finding triggers one cycle through rule 3 or rule 1.
- **Alternatives considered**: triggering only on high or critical findings (a medium finding could never be fixed automatically, against AC-002); letting a non-approved verdict pass after three cycles (weakens #27's "only approved proceeds").

## R3. Check results reach the fix loop only through trusted steps

- **Decision**: `artifacts.py run-checks --feedback` runs the same confined `[checks]` commands as `run-checks` and keeps every guard: the protected-input comparison (tamper block), the "checks must not change the tree" comparison (postcondition block) and the wall-time check. It differs in three ways. It does not require a frozen tree. A failed command is recorded, not a block. It appends one line per run to the operator log `checks-feedback.jsonl`. The workflow runs it once after `validate-implementation` (step `checks-implementation`) and once in each active cycle (`checks-fix-N`). The final blocking `run-checks` before `decide-final` is unchanged.

  The implementation-review recorder then writes the **fix input** `.specify/workflow-state/fix-input/<feature-slug>.json`. It lists the findings to fix (decision ID, finding ID, severity, label, reason, report path), the failed check commands with their exit codes and the last 4000 characters of each output, and the cycle number. The file sits under `.specify/`, which agent steps see read-only, the same way the required-reviews file does (#27). `speckit.ballast.fix` and the recheck reviews read it as untrusted data.
- **Rationale**: D-08. The headless agent's command permissions (`claude-settings.json`, `CONFINED_ALLOW`) stay as they are (FR-003). Check output is project-generated text, so it is passed as data and bounded.
- **Alternatives considered**: letting the agent run the check commands (an R2 permission widening, a non-goal); feeding only the final `run-checks` (check failures would never reach a fix).

## R4. Correctable refusals: retried inside the agent wrapper

- **Decision**: the wrapper validates the drafts an Autonomous agent step created right after the agent exits. It uses the same functions the recorder runs, moved into one draft-contract entry point `artifacts.check_step_drafts(feature, command, args, step)`. A failure in that contract raises a new `DraftError` (a `ContractError` subclass). On a `DraftError` the wrapper moves the refused drafts to operator state (`set-aside/<step>/retry-<n>/`). It reruns the agent with the original prompt plus one appended paragraph that carries the validator's message (printable characters only, at most 500), up to **2 retries per step invocation**. Each rerun is a full attempt: limit check and step count, confinement, a new systemd scope, the protected-input check and its own log directory and `steps.jsonl` entry. The entries of refused attempts carry `refused: <message>` and are ignored by the recorders' `_qualifying_steps`. When the retries are spent, the wrapper exits `EXIT_LIMIT` with the reason `draft refused after 2 retries: <message>` and `limit: retries`. When the step limit or wall time runs out first, the reason carries the last validator message (AC-018).

  Correctable (`DraftError`) means the agent can fix the error by rewriting its own draft:
  - a draft that is not a JSON object, a wrong `point` or `decision`, or a missing required draft (`_expected_drafts`);
  - a length or format violation in a text field: summary 500 characters on one line, basis 2000, finding reason 1000, question and default 1000, block condition 2000, recovery 1000, option 500, consequence 1000, string lists of at most 20 items of 100 characters each;
  - approval wording (`HUMAN_APPROVAL`) or a workflow marker in agent text, quoted or not (D-06);
  - an evidence or artifact path that is not a regular repository file, and a missing review report;
  - an invalid finding ID, severity, label or disposition, `accepted-provisionally` without a reason, or a narrative with findings or severity tags;
  - an invalid `block.json` behind an agent's exit 3.

  Everything else stays terminal and is never retried (FR-017, AC-019): a protected-input change (tamper), a high or critical finding at a point without a fix loop, a review verdict, risk or eligibility rechecks, a stale intent, a frozen-tree or tree-change violation, a contradiction an agent reports, and a missing run record or authority. The recorder keeps calling the same validators. If it still raises a `DraftError` (it should not), that is a postcondition block, as today.

  The recorder stores the attempt count and the refused messages in the decision entry's `agent.attempts` and `agent.refusals`. The record shows "after N retries".
- **Rationale**: D-05 and D-06. The draft stays the agent's own text and no validator changes. The wrapper already owns attempt counting, confinement and draft capture, and the retry needs no engine support. The 2-retry bound is a constant (`DRAFT_RETRIES`).
- **Alternatives considered**: a retry driven by the recorder, re-invoking the agent from inside a shell step (nested agent invocation in a step whose timeout is unknown); unrolled retry steps (about 40 extra workflow steps); truncating agent text (the recorder would rewrite agent output).

## R5. Autonomous resume flow

- **Decision**: `ballast run resume RUN_ID [--ref TEXT]` for a `ballast-autonomous` run replaces `RESUME_REFUSAL` with this sequence in `run.py` (contract: [cli-commands.md](contracts/cli-commands.md#ballast-run-resume)):
  1. Argument check: only `RUN_ID` and an optional `--ref` (1–500 characters, refused when it matches `HUMAN_APPROVAL`). `-i`, `--mode`, `--wall-time` and `--max-agent-steps` are refused: the mode, risk, limits and integrations recorded at start hold (FR-012, AC-016, AC-029).
  2. Tamper marker check (existing).
  3. Status and block check ([data model](data-model.md#resume-eligibility)): `continued` refuses with a pointer to the continuation run (AC-015). `completed` refuses with a pointer to `publish`. `published` refuses with a pointer to `checkpoint`. A `tamper` or `unfinished-step` block refuses with `ballast discard-runs`. A `forge` or `permission` block refuses with `publish`. A start-time `upstream-sync` block (no engine state) refuses with the restart command. A `limit` block for `agent-steps` or `wall-time` refuses: limits cannot be raised; continue human-gated or start a new run. An `active` run whose invocation lock is free is an interrupted invocation: its active time is closed (R8) and it gets an `interrupted` block before going on.
  4. The per-run invocation lock is taken without waiting; a held lock refuses (R13).
  5. Branch synchronization runs through the existing `_sync(run_id, feature=<pinned feature>)` before any agent step (FR-007, AC-009). Its blocks, protected input included (AC-013, `ballast trust` recovery) and an unpinned run (AC-014, R11), stop the resume before anything below. Resume records the sync block as the run's current block with the command `ballast run resume RUN_ID`.
  6. Compute the re-entry step (R6).
  7. Append human decision `block-resolution` (`--ref`, or the default "operator resumed after the <category> block at <step>") with `resolves: block` (FR-010, AC-010).
  8. `autonomy.resume_run`: status `stopped → active` (a new transition, legal only with a `block-resolution` decision ID), a `resumes` entry, a reset of runner state at or after the re-entry step (R6), consumption of pending steps, drafts set aside, and the invocation clock started (R8). The mode history is untouched.
  9. Re-render `autonomous/record.md`, so the first shell step's preamble passes.
  10. Point `.specify/feature.json` at the pinned feature (existing SEC-002 rule).
  11. Reposition the engine at the re-entry step (R7) and run `specify workflow resume RUN_ID`.
  12. `_finish`: publish on completion, or record the new block. The invocation clock is closed, the operator records are archived and the Draft PR checkpoint runs, as for `start`.
- **Rationale**: D-01, D-02, D-04 and ADR-0005 (sync before any agent step, pin from operator state only). The human decision is recorded only after the sync passes, the same order `continue` uses, so a refused or blocked resume leaves no record.
- **Alternatives considered**: lowering to human-gated (the status quo); a new continuation run ID for Autonomous resume (would split one run's decision log across IDs).

## R6. Re-entry step (FR-009)

- **Decision**: the re-entry step is the earliest of:
  - the **block step**: the failed agent step itself; for a failed recorder, the agent step whose drafts it records (for `record-implementation-review` and `record-fix-review-N`, the first reviewer step of that review run); for a failed validator, the validator itself;
  - for each **input that changed during the block**, its mapped step, when that step comes before the block step.

  At stop, `run.py` stores a block-time digest snapshot with the block (`block.inputs`). At resume it compares the current files against it:

  | Input | Re-entry step |
  | --- | --- |
  | `<feature>/discovery.md` | `validate-discovery` |
  | `<feature>/spec.md` | `validate-spec` |
  | `<feature>/intent.md` | `validate-intent` |
  | `<feature>/plan.md`, `research.md`, `data-model.md`, `quickstart.md`, `contracts/` | `validate-plan` |
  | `<feature>/tasks.md` | `validate-tasks` |
  | `<feature>/decisions.md` | `validate-decisions` |
  | tree outside `<feature>/` (excluding ignored files), only once an implementation baseline exists | `validate-implementation` |

  Comparing against the block-time snapshot, not against the digests stored in decisions, keeps legitimate changes the run itself made (for example `implement` ticking off `tasks.md`) from forcing a rewind. Changes from branch synchronization count, so a base change that touches the feature or, after implementation, the code forces a recheck.

  Runner state reset at re-entry: when re-entry is at or before `record-implementation-review`, `frozen_tree`, `checked_tree` and the fix state are cleared. `fix.cycles` is never reset (FR-001). The implementation baseline is never re-taken once it exists: `record_baseline` keeps an existing baseline for the run, so the reviews still cover every change since the first one. A re-recorded single decision point supersedes its current decision automatically, as `intent` already does. A re-recorded review point supersedes every current entry of that point (and of `specialist-review` for `implementation-review`).

  The step order is the constant `autonomy.AUTONOMOUS_STEPS`, mirrored from `workflow.yml`. A test compares the two.
- **Rationale**: AC-012 needs "earliest step whose recorded input changed" to be deterministic and testable. A static map from file to validator also makes the validator run first, and the validator decides whether the agent steps after it see a valid artifact.
- **Alternatives considered**: digests stored in decisions (false rewinds after normal run progress); always rewinding to `decide-intent` (spends the step budget for nothing); blocking when an input changed (not resume).
- **Budget note**: a rewind spends agent steps again, and resume cannot raise the limit. A post-implementation spec change rewinds to `validate-spec` and may exhaust the steps. That run then blocks as `limit` and the operator continues human-gated. The quickstart shows this case.

## R7. Repositioning the engine (verify first)

- **Decision**: before `specify workflow resume`, `run.py` (trusted; `.specify/` is protected from agents) rewrites the run's engine `state.json` atomically. `current_step_id` becomes the re-entry step and `current_step_index` its position in the run's own `workflow.yml` copy (top-level `- id:` lines, in order). The `step_results` of that step and every later one are removed, and `status` becomes `failed`. `log.jsonl` is left untouched (append-only, imported by the ledger). When the re-entry step is the failed step itself, nothing is rewritten.

  **T001 verifies this first with the real CLI** (full local gate): a fixture run fails at a recorder, its state is repositioned two steps earlier, and `specify workflow resume` must run the earlier step next. If the engine rejects a repositioned state, the fallback (recorded in `decisions.md` before implementation continues) is a fresh `specify workflow run ballast-autonomous` under the same run ID, after archiving the old engine directory. In that fallback, trusted code skips every step before the re-entry step, with the same skip mechanism as R1.
- **Rationale**: this is the smallest change that gives an arbitrary re-entry point, and `run.py` already reads this state. The run's own `workflow.yml` copy also explains how old runs behave (R19).
- **Alternatives considered**: engine-only resume (it reruns the failed recorder against a refused draft); a new engine run per resume (changes how the ledger imports `log.jsonl`, so it stays the fallback only).

## R8. Wall time counts active time only (D-09)

- **Decision**: new run records keep `limits.wall_time_minutes` and add `active_seconds` (closed invocations) and `invocation_started_at` (the open one). `remaining_seconds(record) = wall_time_minutes*60 - active_seconds - (now - invocation_started_at)`. `run.py` opens the clock before the first agent step of `start` and `resume` and closes it in `finally`. If an invocation died without closing it, resume closes it at the latest timestamp the run recorded (the last `steps.jsonl` `at`, the block `at`, or `invocation_started_at`), so a crash never adds the downtime. The wrapper and `run-checks` keep calling `remaining_seconds`, which now reads both fields; each step is still stopped at the limit (AC-027). Records from v0.6.x keep `limits.deadline`. While active they behave as before. On resume, `active_seconds` is seeded from `started_at` to their latest recorded timestamp, capped at the limit.
- **Rationale**: a fixed deadline makes an overnight pause end every run. Active time keeps the limit per run, and resume cannot raise it.
- **Alternatives considered**: a per-invocation limit (would let resume grant fresh time).

## R9. Agent-step default: 30 → 40

- **Decision**: `AGENT_STEPS` default becomes 40 (bounds 1–200 unchanged). The workflow has 18 agent steps on its main path; three fix cycles add 9, so 27 at most without retries. Under the default of 30, a run that used all three cycles had 3 steps left for retries and any rewind. 40 leaves 13. Wall time stays 240 active minutes. The record states that spend is bounded by the step limit, that every step, retry and fix cycle counts, and that monetary spend is not measured (FR-022).
- **Rationale**: the spec's assumption asks the plan to check the default and record a change. Resume can never raise a limit, so a default below the designed maximum would turn ordinary runs into blocks that cannot be resumed. The default is a bound, not authority. Projects and operators can still lower it.
- **Alternatives considered**: keeping 30 (the designed path can exhaust it); counting skipped steps (they start no agent).

## R10. `continue` of a pre-implementation block

- **Decision**: `_continue_refusal` refuses a source run that has no implementation baseline. The message: "run X stopped before implementation; resume it in Autonomous: ballast run resume X". Post-implementation `continue` is unchanged (FR-011, AC-011). The existing `upstream-sync` refusal stays first.
- **Rationale**: D-04. `continue-preflight` already needs the baseline, so this replaces a late, confusing failure with an early pointer.

## R11. Runs started before branch pinning (D-12)

- **Decision**: branch sync keeps blocking such a run as `wrong-branch` (ADR-0005, DEC-0006). The `unpinned` recovery text now names the documented manual step: add `"feature": "specs/<N>-<slug>"`, taken from the run record, to the run's pin file under the launcher state directory, then rerun. A new subsection of the spec-kit workflow policy, "Runs started before branch pinning", documents where the pin file is and how to check the feature in the run record. Nothing writes the pin from agent-writable inputs. The pin stays operator state outside the worktree.
- **Rationale**: documentation only; the accepted pin rule is unchanged. The human-gated block stays the same and only its recovery text changes.

## R12. `ballast run checkpoint RUN_ID` (D-11)

- **Decision**: a new `run.py` subcommand dispatched before the `specify` lookup, like `publish`. It refuses a run that is not `ballast-autonomous` or whose invocation lock is held (R13). It calls `draft_pr.checkpoint(root, run_id, create=False)`. With `create=False`, the checkpoint's `settle()` returning no PR ends as `skipped` with reason `no-draft-pr`. A `skipped` outcome records no ledger event and publishes no packet, so the command refuses (exit 2) and has written nothing (AC-025). Otherwise it prints the Draft PR line and the packet line and exits 0, or 1 on `failed-retryable`. It runs no agent and never touches `run.json`, the logs or the record (AC-023, AC-024). Run status does not matter, `published` included.
- **Rationale**: it reuses #17's checkpoint and #19's packet unchanged, apart from the `create` switch.

## R13. Per-run invocation lock

- **Decision**: `run.py` holds an exclusive non-blocking `flock` on `<operator run dir>/invocation.lock` for the whole of `start --mode autonomous`, Autonomous `resume`, `publish` and `checkpoint`. A held lock refuses with "run X has an active invocation". Resume uses it to tell a crashed invocation (status `active`, lock free) from a live one.
- **Rationale**: covers the edge case "refresh while another invocation of the same run is active" and keeps two resumes from racing.

## R14. Record and packet additions

- **Decision**: `render_record` gains `human_decisions` (block resolutions, with their reference text neutralized) and renders:
  - in "Mode and risk": `- Spend: bounded by the agent-step limit; every agent step, retry and fix cycle counts; monetary spend is not measured`;
  - a new "Fix loop" section: cycles used out of 3, and per cycle the review decisions and the feedback check results;
  - a new "Block resolutions" section: each `block-resolution` with the block it resolved, its re-entry step and time;
  - "after N retries" on decisions whose `agent.attempts > 1`.

  Every block line names its class (R15). The packet already lists human decisions, findings and `run-checks` (#19), and keeps doing so.
- **Rationale**: AC-004 and FR-005. Only recorders and run.py re-render the record, never the wrapper. That is why fix-cycle counts are written by `record-fix` and retries are stored in the decision entry: the preamble's "record unchanged" check holds after every agent step.

## R15. Block classes (FR-023)

- **Decision**: `autonomy.BLOCK_CLASSES` maps each category to one of the four classes. **Conflict**: `contradiction`, `review-finding`. **Missing authority**: `permission`, `ineligible`, `forge`. **Exhausted limits**: `limit`, with an optional `limit` field (`agent-steps`, `wall-time`, `fix-cycles`, `retries`). **Unsafe uncertainty**: `decision`, `postcondition`, `tamper`, `unfinished-step`, `interrupted`, `upstream-sync`. The printed block reads `Autonomous run blocked (<class>: <category>)`. `recovery_command` returns `ballast run resume RUN_ID` for every resumable category, and `BLOCK_COMMAND` accepts it. The `RECOVERY` texts say "then resume, or continue human-gated" where both apply.
- **Rationale**: the categories stay as they are, so the existing tests and the packet still hold; the class is a projection.

## R16. Commands, templates and the tasks template

- **Decision**:
  - New command `speckit.ballast.fix`, registered in the `ballast` extension. It reads the fix input, fixes only the listed findings and failed checks, edits code and the feature's `tasks.md` or `decisions.md` only as needed, writes no draft and states that its work is agent-provisional.
  - `speckit.ballast.review` accepts `implementation-recheck` and `specialists-recheck`. It reads the fix input and judges whether each listed item is resolved. It also states the cycle rule (R2).
  - `speckit.ballast.decide`, `speckit.ballast.review`, `speckit.ballast.clarify`, `speckit.ballast.discover` and `speckit.ballast.resolve` state the recorder's length limits (R4). Decide and review also tell the agent to paraphrase and cite a sourced human approval, never quote approval wording (FR-018, AC-020, AC-021).
  - `templates/spec-kit/templates/tasks-template.md` says: never create tasks for steps the workflow runs itself (the full gate, quickstart runs, reviews, converge, spec reconciliation), because `validate-implementation` requires every task done before those steps run. `check_implementation` is unchanged (D-07, FR-019, AC-022).

## R17. ADR-0010

- **Decision**: `docs/adr/0010-autonomous-resume-and-bounded-recovery.md`: a blocked or interrupted Autonomous run resumes in Autonomous through branch synchronization (ADR-0005), with a recorded `block-resolution` and re-entry at the earliest changed input. Implementation findings run a bounded fix loop of three cycles per run. Correctable draft refusals retry twice per step. ADR-0004's continuation rule ("a blocked run cannot resume autonomously; recovery is always human-gated until #18") is amended: `continue` stays the human-gated path, and resume no longer lowers. ADR-0004 gets an "Amended by ADR-0010" line (FR-015).

## R18. Mode and authority on resume

- **Decision**: resume never calls `change_mode` and never writes `mode_history`, `risk`, `limits`, `integration`, `review_integration` or `eligibility`. `validate_run` keeps refusing any raising change. A test asserts that these fields are byte-identical across a resume, and that `resume -i`, `--mode` and the limit flags are refused (AC-016, AC-029, SC-003).

## R19. Runs started under an earlier workflow version

- **Decision**: the engine resumes a run from that run's own `workflow.yml` copy. A run started under 1.1.0 has no fix cycles. The implementation-review recorder checks that copy (`speckit.ballast.fix` present). Without it, the recorder blocks on findings exactly as in #27 instead of setting `fix-pending`, so a pending fix can never be skipped into `resolve-decisions`. As a second guard, `record-decision --point decision-resolution` refuses a run whose fix state is not `idle`.
- **Rationale**: fails closed for in-flight runs, this one (`fcba2ba4`) included.

## R20. Risk and reviews

- **Decision**: risk stays **R2** (agent authority, approval gates, and what the launcher executes: the engine state rewrite and the retry loop in the wrapper). Required reviews, from the [review matrix](../../docs/policies/workflow.md#review-triggers): engineering, security (agent authority, launcher trust, untrusted check output and validator messages in prompts), test (refusal and tamper paths), documentation (policy, ADR-0010, README) and architecture (ADR-0010 amends ADR-0004).
- **Note for the plan decision**: the R2 pre-change approval is agent-provisional (PD-0013). Merging is the single human approval.
