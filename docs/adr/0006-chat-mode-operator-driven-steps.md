# ADR-0006: Chat mode runs operator-driven steps through the trusted launcher

- Status: Proposed (agent-provisional in Autonomous run `2cb9c5c5`; accepted only by the human merge decision)
- Feature: [20-chat-mode](../../specs/20-chat-mode/spec.md); plan [§ Decisions for plan review](../../specs/20-chat-mode/plan.md#decisions-for-plan-review), decisions D-1 to D-7; research R1 to R15
- Extends: [ADR-0004](0004-autonomous-provisional-decisions.md) (the publisher), [ADR-0005](0005-launcher-branch-synchronization.md) (the list of invocations that synchronize)

## Context

An operator who wants to shape a feature in conversation today works in a plain Claude Code or Codex session. That skips the trust baseline, branch synchronization, artifact postconditions and the run's evidence record. A Spec Kit 1.0.11 command step runs `claude -p` or `codex exec`, which cannot hold a conversation, and its engine runs a fixed sequence of steps with gates inside one long process. Chat mode must keep every guarantee of a headless run while the operator chooses the next step, edits files between steps, and talks to the agent during a step (BL-INV-002, BL-INV-003, BL-INV-005).

## Decision

- **Who drives (D-1, R1)**: Ballast drives a Chat run, not the Spec Kit engine. Each operator action is one `ballast run` invocation through the pinned launcher: `start --mode chat`, `step`, `status`, `approve`, `reject`, `resolve`, `checks`, `mode`, `continue --mode chat` and `publish`. `run.py` dispatches them to the trusted module `tools/spec_workflow/chat.py`, imported at startup inside the trust baseline. An agent step is therefore always the only agent step of its invocation, preceded by the launcher's baseline, tamper-marker and unfinished-step checks. The phase and gate identifiers reuse those of `ballast-feature`, so the ledger reports both kinds of run against one definition.
- **Phase graph (R2)**: a phase starts only when its cumulative upstream `artifacts.py` checks and its current human approvals pass at that moment. Each evaluation is appended to a hash-chained event log in operator state. Nothing stores a "blocked" flag: a failed check blocks because it is run again, whatever the mode.
- **Interactive confinement (D-2, R3)**: an interactive step runs `claude --permission-mode dontAsk` or `codex --ask-for-approval never` with the headless rules, inside the Autonomous bubblewrap confinement and a systemd user scope, plus read-only binds of `<root>/.claude` and `<root>/.codex`. bwrap is therefore a Chat prerequisite. A grant made inside the session cannot get past bwrap. Claude's settings for the step are written into the step's log directory before it starts: the installed `claude-settings.json` (with the project's `[agents.permissions]` rules that `tools/setup` merges) plus `claude-chat-settings.json` (edits allowed for `dontAsk`, bypass and auto modes disabled). The Chat deny list can therefore never be narrower than the headless one.
- **Terminal (D-3, R3a)**: the wrapper creates a fresh pty; its child calls `setsid()`, takes the slave as its controlling terminal and holds no descriptor to the operator's terminal. Only for this argv, `autonomy.confined_argv(..., interactive_pty=True)` omits bwrap's `--new-session`; every other caller keeps it. TIOCSTI can then reach only the agent's own pty.
- **Branch synchronization (R5)**: every Chat `step` invocation runs the ADR-0005 check (`starting=False`, recovery text `ballast run step RUN PHASE`) before its agent. `start --mode chat` and `continue --mode chat` run it too and start no agent. ADR-0005's rule, once per invocation before the first agent step, is unchanged; only the list of invocations grows.
- **Human gates (D-4, R11)**: every gate (scope, intent, plan, tasks, implementation, spec reconciliation, final) needs `ballast run approve`, which requires a TTY, no active step, a passing precondition and the typed text `approve GATE`. Each approval is a hash-chained human decision in operator state, bound to the artifact's digest and current only while that digest matches. The tasks digest reads every checkbox as unchecked, so implementing tasks keeps the tasks approval current while a changed task does not. `ballast run resolve` records the human resolution of a `DEC-NNNN` proposal, bound to the resolution text's digest. Chat never records an agent-provisional decision, and agent output never opens a gate.
- **Mode switches (D-5, R12)**: a Chat run switches between `chat` and `human-gated` in the same run; human-gated steps run headless through the unchanged `agent.py`. A paused `ballast-feature` engine run (`ballast run mode RUN chat`) or a stopped Autonomous run (`ballast run continue RUN ... --mode chat`) continues as a linked Chat run. No path raises a run to Autonomous.
- **Publication (D-6, R14)**: `ballast run publish` reuses the Autonomous publisher's commit, push and Draft PR path for a Chat run after a current final approval, and writes a Chat section rendered only from operator records. Conversation logs stay local.
- **Dead wrapper (D-7, R10)**: when the wrapper dies during a step, the `in-progress` marker stays and the launcher refuses, naming the run and step. Recovery is the existing `ballast discard-runs`, which stops the recorded scope; the next Chat invocation closes the step as interrupted and runs its postcondition before any later step.

## Consequences

- An operator can work conversationally with the same preflight, confinement, postconditions, evidence and human approvals as a headless run; the PR states that the run used Chat mode.
- Chat steps need bwrap with user namespaces and a systemd user session, as Autonomous steps already do.
- Approvals for plan, tasks, implementation and final are bound to artifact versions, which is stricter than the human-gated engine gates.
- The runner has a second publication caller and a second ledger report path (Chat events instead of the engine log).

## Rejected alternatives

- One Spec Kit workflow per phase: separate run IDs, ledgers and pins, and the command step still cannot converse.
- A long-lived `ballast run chat` REPL: trust would be checked once while the operator edits the checkout in another terminal.
- Interactive steps with only the headless permission rules: Shift+Tab or `/approvals` inside the session could widen the agent.
- Recording approvals in Spec Kit gate state: that state is agent-reachable and not bound to an artifact version.
- A new launcher recovery command for one dead step: more launcher surface for a rare path (follow-up F-1 if the pilot shows a need).
