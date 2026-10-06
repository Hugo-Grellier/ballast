# Research: Chat mode

Phase 0 decisions for [plan.md](plan.md). Each decision states what was chosen, why, and what was rejected. The spec leaves no NEEDS CLARIFICATION marker; PD-0002 (local conversation logs) is applied in R9. This plan is written inside Autonomous run `2cb9c5c5`, so every decision below is agent-provisional until the human merge decision (BL-INV-006).

**Evidence sources.** The current code in `tools/spec_workflow/` (`launcher.py`, `run.py`, `agent.py`, `autonomy.py`, `artifacts.py`, `branch_sync.py`, `draft_pr.py`, `ledger.py`), ADR-0003 to ADR-0005, `docs/policies/spec-kit-workflow.md`, and `claude --help` run locally. These could not be checked in the planning sandbox and are listed as pilot checks in [quickstart.md](quickstart.md): `codex --help`, `specify workflow run --help`, and an interactive TUI under the confinement of R3.

## R1. Who drives a Chat run: Ballast, one invocation per action

- **Decision**: Chat runs are driven by Ballast, not by the Spec Kit engine. Each operator action is a separate `ballast run ...` invocation: `start --mode chat`, `step`, `status`, `approve`, `reject`, `resolve`, `checks`, `mode`, `publish` ([contracts/cli.md](contracts/cli.md)). The operator's shell is the space "between steps". `run.py` dispatches the new subcommands to a new trusted module, `tools/spec_workflow/chat.py`, which owns the phase graph, the gates, the step lifecycle and the handoff summary.
- **Rationale**:
  - Spec Kit 1.0.11 command steps run `claude -p` / `codex exec`, which cannot hold a conversation. Its gates prompt inside one long engine process, and there is no evidence of a single-step or `--from` option (repo evidence only; see quickstart pilot check P-1). The operator must be able to choose the next phase, re-run an earlier one and edit between phases. A linear engine run does not allow that.
  - One invocation per action makes FR-004 structural. Every agent step is the only agent step of its invocation, so it is always preceded by the launcher's trust baseline, tamper-marker and unfinished-step checks (`launcher._refusal`), and then by `run.py`'s branch synchronization (R5). Nothing long-lived holds stale trust between steps.
  - Resume (FR-018) needs no session state. Any later invocation, in any terminal, reads the operator run record.
  - `artifacts.py` already accepts `--feature` and exposes its checks as functions, so Chat can call the same postconditions in-process. Ballast does not have to forge engine state.
- **Alternatives rejected**:
  - **One Spec Kit workflow per phase** (`ballast-chat-plan`, ...). Each would get its own engine run ID, ledger and pin, which conflicts with one run record (FR-013). It would still not make the command step interactive.
  - **A long-lived REPL** (`ballast run chat` that loops). The trust check would happen once at entry, so later steps would rely on an in-process re-check of a checkout the operator edits meanwhile. Edits between steps would also happen in another terminal while a trusted process holds the run. The `status` command gives the same view without that.
  - **Leaving Chat to plain Claude Code or Codex sessions.** This is today's gap: no trust check, no branch synchronization, no postconditions, no record.

## R2. The phase graph and allowed steps

- **Decision**: Chat uses the step and gate identifiers of `ballast-feature` ([contracts/phase-graph.md](contracts/phase-graph.md)). There are eight producer phases (`specify`, `clarify`, `plan`, `tasks`, `analyze`, `implement`, `reconcile-intent`, `converge`), one `review` phase with a kind, and the seven human gates (`scope`, `intent`, `plan`, `tasks`, `implementation`, `spec-reconciliation`, `final`). Each phase has an entry condition, which is a set of upstream checks and current approvals, and a postcondition, which is the same `artifacts.py` check the `validate-*` step after it runs in `ballast-feature`.
  - A phase is offered, and a `step` for it is started, only when its entry condition passes **at that moment**. The trusted runner evaluates the condition, records the result, and on failure refuses the step and names the failing check.
  - The operator may re-run any phase whose entry condition passes, including an earlier one (edge case "re-runs an earlier step").
- **Rationale**: Re-evaluating the cumulative checks at each request implements FR-010 without a separate "blocked" flag that could drift. A recorded failure blocks because the same check is run again before the dependent step, and only a later passing run of that check lets the step start. The failure stays in the hash-chained event log (R6). The result does not depend on the mode, so no mode switch can clear it (FR-022). Reusing `ballast-feature` identifiers lets the ledger report Chat runs against the same steps and gates as human-gated runs (R7, SC-003).
- **Alternatives rejected**: A stored "blocked" set cleared by a later pass. It duplicates what the checks already decide, and it could disagree with the artifacts after an edit made between steps.

## R3. Confinement of an interactive step

- **Decision**: An interactive Chat step runs the real agent CLI with the human-gated permission rules, **inside the bubblewrap confinement that Autonomous steps already use**, behind a wrapper-owned pseudo-terminal ([contracts/step-runner.md](contracts/step-runner.md)):
  - **Claude**: `claude --permission-mode dontAsk --setting-sources project --strict-mcp-config --settings .ballast/spec_workflow/claude-chat-settings.json [--model M] "<phase prompt>"`. The chat settings file keeps every allow and deny rule of `claude-settings.json`. It adds `Edit`/`Write` allow rules for `./**`, which `dontAsk` needs because it does not accept edits by itself, and it adds `disableBypassPermissionsMode` and `disableAutoMode`. `dontAsk` denies anything that would prompt (verified in `claude --help` and the permission-mode documentation). `--permission-prompts` is print-only, so it is not passed.
  - **Codex**: `codex --sandbox workspace-write --ask-for-approval never --config sandbox_workspace_write.network_access=false --config sandbox_workspace_write.writable_roots=[] [--model M] "<phase prompt>"` (pilot check P-2).
  - **Both**: the `FORBIDDEN` bypass-flag refusal, the `guard/git` wrapper first on `PATH`, `PYTHONPYCACHEPREFIX`, a `systemd-run --user --scope` unit, the child subreaper, the protected-state digests before and after, the `in-progress` marker, and the tamper marker on a protected change. All are reused from `agent.py`.
  - **bwrap**: `autonomy.confined_argv` / `confined_env` / `confinement_self_test`, the same binds as Autonomous. `.claude/` and `.codex/` in the worktree are also bound read-only, so a rule saved from inside the session cannot reach later steps. Codex is refused for Chat when `codex_sandbox_nests` fails ("integration cannot run confined"). It is never run with its own sandbox off.
- **Why bwrap, when human-gated headless steps do not use it**: a headless step has nobody to answer a prompt, so `--permission-prompts none` binds it. An interactive session cannot be locked the same way. Shift+Tab leaves `dontAsk` for the default cycle, where Claude prompts, and Codex's `/approvals` can switch to full access. FR-005 and the Assumption "a Chat agent gets no extra permissions through interactive prompts" therefore need an OS bound that holds whatever is granted inside the session. bwrap gives that bound: a read-only host, protected inputs and `.git` read-only, operator state and credentials hidden, and the session bus and `systemd-run` unreachable. Deny rules still apply in every Claude mode. The CLI rules give the same permission model as a headless step of the phase. bwrap only removes what an interactive grant could add. bwrap becomes a host prerequisite for Chat, as it already is for Autonomous.
- **The terminal** (R3a below): the wrapper creates a fresh pty. Its child calls `setsid()` and takes the pty slave as its controlling terminal before it executes `systemd-run ... bwrap ... agent`. The wrapper relays bytes between the operator's terminal (in raw mode, restored on every exit path) and the pty master, forwards window-size changes, and writes everything the pty shows to the step log (R9).
- **Alternatives rejected**:
  - The human-gated headless confinement only (no bwrap). An operator-granted prompt or a mode switch inside the session would widen the agent beyond the headless model.
  - `--permission-prompts none` interactively. The help text marks it print-only, so its interactive behavior is unknown.
  - Piping stdout as `agent.py` does. Claude treats a non-TTY stdout as non-interactive.
  - Recording Claude's own JSONL transcript. It is lost in bwrap's temporary overlay of `~/.claude`, it differs per provider, and the agent can write it.

### R3a. `--new-session` for a wrapper-owned pty

- **Decision**: For Chat steps only, `confined_argv` omits bwrap's `--new-session` **when, and only when,** the confined process's stdin, stdout and stderr are the slave of a pty that the wrapper created for this step and the wrapper's child has already made that slave its controlling terminal. Headless and Autonomous steps keep `--new-session`.
- **Rationale**: `--new-session` exists against TIOCSTI injection into the caller's terminal (CVE-2017-5226). With a wrapper-owned pty the agent's controlling terminal is the inner pty, so TIOCSTI can only push bytes into the agent's own input. The agent holds no descriptor to the operator's terminal; the wrapper relays it. Keeping `--new-session` would leave the TUI without a controlling terminal: no `SIGWINCH`, `/dev/tty` fails, and job control is gone (research agent, from knowledge; pilot check P-3).
- **Verification**: a test asserts that the confined process has no open descriptor to the wrapper's own terminal and that its controlling terminal is the step's pty. A second test asserts that `--new-session` is still present for every non-Chat call.
- This changes the agent confinement, an R2 boundary. It is listed for plan review as D-3.

## R4. Step lifecycle and the end of a step

- **Decision**: `ballast run step RUN PHASE` takes these steps in order ([contracts/step-runner.md](contracts/step-runner.md)):
  1. Run lock (R8).
  2. Close any step still marked active (R10).
  3. Out-of-step change detection (R6).
  4. Branch synchronization (R5).
  5. Entry condition (R2).
  6. Confinement self-test and integration choice.
  7. Record step start (active step written to `run.json`), write `in-progress`.
  8. Interactive session.
  9. Stop the scope and confirm it is gone, reap descendants, compare protected state.
  10. Postcondition and cumulative checks.
  11. Phase write-scope check.
  12. Record step close, ledger events, archive, Draft PR checkpoint.

  The step ends when the agent CLI exits (`/exit`, Ctrl-D), when the operator presses the wrapper's escape sequence (`Ctrl-]` twice within a second) to end it while the agent is still working, or when the wrapper receives `SIGHUP`, `SIGTERM` or `SIGINT`. In every case the scope is stopped and confirmed gone **before** any check (FR-009). A step whose scope cannot be confirmed stopped is recorded as such: the `in-progress` marker stays, and the existing unfinished-step refusal applies.
- **Outcome values**: `completed` (agent exited, postcondition passed), `failed` (postcondition or write-scope failed), `interrupted` (ended by signal, escape or wrapper loss), `tampered` (protected change), `refused` (entry condition, preflight or confinement failed; no agent ran).
- **Write scope (FR-008)**: before `implement`, a step may change only `specs/<f>/`. `review` may change only `specs/<f>/reviews/`. `implement`, `reconcile-intent` and `converge` may change any path the confinement leaves writable. A violation fails the step and lists the paths. It is not a tamper unless a protected input changed. The check compares the operator-side tree manifests taken before and after the step (R6).
- **Rationale**: This mirrors `agent.main` and the `validate-*` step that follows each producer, so BL-INV-005 holds per step. Recording the active step in operator state before the agent starts lets a later invocation tell an interrupted step from a completed one without trusting any agent-writable file.

## R5. Branch synchronization before every Chat agent step

- **Decision**: `start --mode chat` calls `branch_sync.synchronize(..., starting=True)` to pin the branch and the feature, as a human-gated start does. Every `step` calls it with `starting=False`, so the Issue number comes from the pin, before the agent starts. `status`, `approve`, `reject`, `resolve`, `mode` and `checks` start no agent and do not synchronize. `publish` keeps the publisher's own push rules. `branch_sync` gains a `rerun` text parameter, so a Chat block prints `ballast run step RUN PHASE` as its recovery and not `ballast run resume`.
- **Rationale**: ADR-0005 runs the check "once per invocation, before the first agent step". A Chat `step` invocation has exactly one agent step, so the rule is unchanged. Only the list of invocations grows, which the ADR-0009 proposal records. The pin, the rewrite rule and the throwaway repository are reused as they are.
- **Consequence noted for operators**: agents cannot commit, so the tree is usually dirty between Chat steps. When the base has moved, synchronization blocks as `dirty` (existing cause) with the recovery to commit first. That matches the spec edge case "base branch advances": the check synchronizes or stops before the agent with the existing block.

## R6. The operator run record and the event log

- **Decision**: A Chat run uses the operator run record that Autonomous introduced, `$XDG_STATE_HOME/ballast/<checkout>/runs/<run>/` ([data-model.md](data-model.md)):
  - `run.json`: `workflow: "ballast-chat"`, `mode: "chat"`, `active_step`, `driver`, `baseline`, `start_head`.
  - `steps.jsonl`: one start and one close entry per step.
  - `human-decisions.jsonl`: hash-chained, with new kinds `gate-approval`, `gate-rejection`, `decision-resolution` and `mode-change`.
  - A new hash-chained `events.jsonl` (`E-NNNN`): every check run (postcondition, entry condition, project checks), review, out-of-step change and refusal.

  Every result is appended and never rewritten.
- **Out-of-step changes (FR-011)**: at each step close, and after each `approve`, the runner stores a manifest `{path: sha256}` of every tracked and unignored file outside `.git`. It is computed operator-side with filters, hooks and fsmonitor disabled (`autonomy.filter_flags`, `hash-object --no-filters`). The next invocation compares it with the current tree. Any difference is appended as an `out-of-step-change` event attributed to `operator`, with the changed paths and the approvals it made stale.
- **Staleness**: each gate approval is bound to a digest: the spec digest for intent (existing `spec_digest`), the `plan.md` digest, the `tasks.md` digest, the tree digest for `implementation` and `final`, and the `reviews/convergence.md` digest for `spec-reconciliation`. An approval is current only while its digest matches. Nothing is invalidated by hand, so an edit made between steps, an agent edit and a re-run of an earlier step all make approvals stale the same way (edge case "re-runs an earlier step").
- **Rationale**: The operator state directory is the only store no agent can write (BL-INV-003); bwrap hides it during a Chat step. Hash chains reuse `autonomy.read_log` / `append_log`. Plain human-gated runs have no operator record today. Chat is the first non-Autonomous mode with one, which FR-002 requires.
- **Alternatives rejected**: Storing approvals as Spec Kit gate state. That state is agent-reachable run state, and the human-gated gates for plan, tasks and final are bound to no artifact version (AC-007 requires the exact version).

## R7. Same evidence as a headless run: the ledger

- **Decision**: A Chat run writes the same local ledger as a headless run, `<git common dir>/speckit-runs/<run>/events.jsonl` ([contracts/run-record.md](contracts/run-record.md)):
  - a `run` event at start, carrying the new additive field `mode`;
  - `step` events for each phase with the `ballast-feature` step ID;
  - `gate` events for each human approval or rejection;
  - `snapshot` events at each close;
  - `branch_sync` events (unchanged);
  - `review` events;
  - `pull_request` events (unchanged).

  At start the runner archives the trusted `ballast-feature` definition and a `chat.json` phase-graph projection under `archive/run/`. `ledger report` gains a Chat path: it computes compliance against the same steps and gates from the Chat events instead of the engine log. The schema version stays 1; the new field and the Chat path are additive.
- **Rationale**: SC-003 compares the run records of a Chat run and a human-gated run. The ledger is the record both kinds of run share, and the PR reviewer sees the same feature identity. The operator run record stays the source of truth for decisions; the ledger is the audit stream.
- **Alternatives rejected**: Forging Spec Kit `state.json` / `log.jsonl` so the existing importer works. That would write engine state Ballast did not observe.

## R8. One active step at a time

- **Decision**: Three layers enforce FR-012:
  1. **The checkout-wide `in-progress` marker** exists while any agent step runs. `launcher._refusal` already refuses every `ballast run`, `ballast ledger` and `ballast intake` while it exists. The message changes to name the active step: the marker's unit name `ballast-agent-<run>-<step>.scope` gives the run and the step.
  2. **A per-run `fcntl.flock`** on `runs/<run>/lock` is held for the whole invocation by every Chat command that changes the run. Two invocations racing before the marker is written are serialized; the loser is refused and the reason names the active step.
  3. **`run.json.active_step`**: `resume` of a Chat run ID, and `continue` or `mode` of a run with an active step, are refused and the active step is named.
- **Rationale**: The marker already covers headless invocations on the same checkout, and it is outside agent reach. The lock closes the window between the launcher's check and the marker write.

## R9. Conversation logs stay local (PD-0002)

- **Decision**: The pty relay writes the terminal stream of each Chat step to `.specify/workflow-state/<run>/agents/<stamp>-<phase>-<integration>/stdout.log`, next to a `meta.json` like a headless step's. These are the same ignored directory and file names a headless step uses. The `speckit-runs` archive keeps a copy. No PR body, Issue comment or committed file links to or quotes them, and the PR states that the conversation logs stay local.
- **Rationale**: FR-017 and PD-0002 reuse the existing headless log behavior. A single raw stream is provider-neutral. The log file is opened through a directory handle taken before the agent starts, as `agent._open_log` does, so an agent that replaces the path cannot redirect the writes.

## R10. Interrupted steps and recovery

- **Decision**:
  - If the wrapper itself survives (agent crash, closed terminal, `SIGHUP`, `SIGTERM`), it closes the step as `interrupted` in the same invocation: stop the scope, confirm, compare protected state, run the postcondition.
  - If the wrapper died too, the `in-progress` marker remains and the launcher refuses with the active step named. Recovery is the existing `ballast discard-runs`: it stops the recorded scope and refuses unless systemd confirms it gone. It does not touch the operator run record. The next Chat invocation sees `run.json.active_step` with no close entry, records the step as `interrupted`, and runs its postcondition and the cumulative checks before any later step (AC-012).
- **Rationale**: This reuses the one recovery path whose process-stopping guarantee is already reviewed. No new launcher operator command is needed. The trust baseline still guards the protected inputs at the next invocation.
- **Alternatives rejected**: A new `ballast recover-step` launcher command that keeps other runs' saved state. It is more launcher surface for a rare path; it can be a follow-up if the pilot shows `discard-runs` is too coarse.

## R11. Human approvals and resolutions

- **Decision**: `ballast run approve RUN GATE` and `reject RUN GATE --reason TEXT` are the trusted gate actions. `ballast run resolve RUN DEC-NNNN` confirms a human resolution of a decision proposal ([contracts/cli.md](contracts/cli.md)). Each action:
  - is refused while any step is active (R8);
  - checks the gate's precondition (R2);
  - prints the artifact path and digest, then requires typed confirmation from a TTY (`approve plan`), so it cannot be piped;
  - appends a `gate-approval`, `gate-rejection` or `decision-resolution` human decision with the bound digest.

  `approve intent` also calls the existing `record_intent`, which writes and registers the human approval block in `intent.md`, so `check_intent` stays the intent postcondition. In a Chat run, the Chat decisions check requires every `DEC-NNNN — Resolution` to have a current `decision-resolution` human decision bound to that resolution's text digest. An agent that writes a resolution during a step therefore resolves nothing (AC-008, AC-009).
- **Rationale**: An agent step cannot reach these actions. The launcher refuses while the marker exists, and bwrap hides the state directory. The TTY confirmation mirrors Spec Kit's gate prompt and keeps unattended scripts from approving. Agent output (conversation text, `RECONCILE_STATUS`, a "Verdict" line, an approval-looking block) never satisfies a gate (FR-015), because only these records count.
- **Alternatives rejected**:
  - Treating the start command as scope approval. The human-gated mode asks for scope separately (FR-003).
  - Attributing resolutions by diffing `decisions.md` across steps. It is fragile, and an explicit human action is clearer.

## R12. Mode switches

- **Decision** ([contracts/cli.md](contracts/cli.md), [data-model.md](data-model.md)):
  - **Chat ⇄ human-gated, same run**: `ballast run mode RUN human-gated|chat --reason TEXT`. In a Ballast-driven run, `human-gated` means each `step` runs the phase **headless** through the existing `agent.py` path (`claude -p` / `codex exec`, unchanged argv), with the same gates, approvals, checks and record. It covers the story "let a long `implement` run headless, then come back to Chat". The switch appends a `switch` entry to `mode_history` and a `mode-change` human decision.
  - **`ballast-feature` (Spec Kit) run → Chat**: `ballast run mode RUN chat --reason TEXT` on a paused or stopped engine run creates a linked Chat run (`continues: RUN`) from the source's trusted branch pin. It leaves the engine state untouched and refuses a later `resume` of the source. Intent approval carries over through its registered block. Other gate approvals live only in agent-reachable engine state, so they are re-asked in Chat, never carried.
  - **Autonomous → Chat**: `ballast run continue RUN --reason block-resolved|changes-requested --ref TEXT --mode chat`. The human decision and the lowering (`autonomous → chat`) are recorded, and a linked Chat run starts. The source's provisional decisions stay in its log and in `autonomous/record.md`. The Chat handoff lists each one as agent-provisional until a Chat human approval of the same point supersedes it. Without `--mode`, `continue` keeps today's `ballast-continue` behavior.
  - **Anything → Autonomous**: refused, with the existing "never raised" wording.
- **Rationale**: Chat and human-gated have the same approval authority (Assumptions), so a switch between them is not a raise. Keeping one run ID for Chat ⇄ human-gated satisfies AC-018 ("every earlier entry stays unchanged"). Failures and decisions keep blocking because allowed steps are recomputed from the checks and current human decisions, never from the mode (FR-022).
- **Alternatives rejected**: Handing a Chat run back to Spec Kit's `ballast-feature` engine. The engine cannot start mid-workflow (P-1), and two drivers of one run would split the record.

## R13. Independent review in Chat

- **Decision**: `ballast run step RUN review --kind plan|implementation|security|test|documentation|spec-reconciliation` starts a reviewer step. It gets a fresh process and session (no conversation carried over), uses the run's review integration (the other provider when its CLI is on `PATH` and confinable, else the same provider), takes role `reviewer`, has write scope `specs/<f>/reviews/` only, and its prompt names the matching shipped review skill. At close the runner records a `review` event with the reviewer identity (provider, model if Ballast passed `--model`, else `unreported`), `cross_provider` (reviewer provider ≠ every authoring provider in the run), the report path and digest, and the verdict read from the report's last `- Verdict:` line, restricted to `approved|changes-requested|CONVERGED|PARTIAL|FAILED`.
- **Rationale**: FR-014 asks for a separate context and an honest cross-provider flag. The verdict is reviewer evidence shown to the human; it never opens a gate (FR-015).

## R14. Project checks and publication

- **Decision**:
  - **`ballast run checks RUN`** runs the `[checks]` commands through the confined check loop of `artifacts.run_checks`, made mode-neutral: no wall-time limit and no frozen-tree prerequisite for Chat. Results with `runner` provenance and the tree digest are appended as `check` events. With no `[checks]` table the result is recorded as `unavailable`.
  - **`approve final`** requires the convergence check, a current `spec-reconciliation` approval, and a checks result for the current tree that passed or is recorded `unavailable`.
  - **`ballast run publish RUN`** requires a current `final` approval and a tree equal to the approved one. It then reuses the Autonomous publisher (`autonomy.publish`) made mode-aware: commit as the operator with hooks and filters disabled, push without force from a throwaway repository to the pinned repository, create or adopt the single Draft PR. It writes a Chat summary section rendered from the operator record ([contracts/pr-evidence.md](contracts/pr-evidence.md)).
  - The per-invocation Draft PR checkpoint (#17) also runs after `start` and `step`, as for human-gated runs. It resolves the feature from the operator record or the pin when no engine `inputs.json` exists.
- **Rationale**: FR-016 asks that the trusted runner, not the agent, create or update the single Draft PR after final acceptance, with headless-equivalent evidence. The publisher already has the reviewed commit and push path, and only its body and its mode checks change. Human approvals are real in Chat, so the Chat renderer lists them as human decisions. The `HUMAN_APPROVAL` wording guard stays in force for Autonomous bodies and for any agent-derived text.
- **Alternatives rejected**: Requiring the operator to push and relying only on the checkpoint. The checkpoint's section carries no steps, checks, reviews or decisions, so the PR would lack the evidence FR-016 requires.

## R15. Documentation and governance

- **Decision**: These documents gain Chat sections: `templates/policies/spec-kit-workflow.md`, `templates/policies/workflow.md`, `templates/AGENTS.md`, `templates/skills/ballast-feature-intake/SKILL.md` (Chat start command), the repository's `AGENTS.md`/`CLAUDE.md`, `README.md`, and `specs/TECHNICAL-SPEC.md` §91. Each covers how to start, inspect, continue, resume and switch; that approvals are human; and that a plain agent session outside `ballast run` gives none of these guarantees (FR-023). ADR-0009 records the operator-driven step loop, interactive confinement (R3, R3a), the per-step synchronization list and Chat publication. The constitution is unchanged, because no invariant is weakened.
