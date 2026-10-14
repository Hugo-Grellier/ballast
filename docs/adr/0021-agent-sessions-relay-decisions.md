# ADR-0021: Agent sessions run mechanical commands and relay decisions within the run's autonomy

- Status: proposed (2026-10-13, with the change for [#147](https://github.com/Hugo-Grellier/ballast/issues/147)). Agent-provisional in Autonomous run `2e651132`; merging the PR is the human approval that accepts it.
- Risk: R2 (the launcher's trust model, headless-agent permissions, what `ballast` executes, the paths setup installs).
- Feature: [147-human-gates-are-decisions](../../specs/147-human-gates-are-decisions/spec.md); research [R1 to R14](../../specs/147-human-gates-are-decisions/research.md); contracts [cli.md](../../specs/147-human-gates-are-decisions/contracts/cli.md) and [trust-refresh.md](../../specs/147-human-gates-are-decisions/contracts/trust-refresh.md); operator decisions D-02 (HD-0002), D-08 (HD-0003) and D-09 (HD-0004) on Issue #147.
- Supersedes in part: [ADR-0004](0004-autonomous-provisional-decisions.md) (the rejected alternative "piping approvals"), [ADR-0009](0009-chat-mode-operator-driven-steps.md) (D-1, the operator's list of actions, and D-4, approvals only from a terminal).
- Amends: [ADR-0010](0010-autonomous-resume-and-bounded-recovery.md) (re-entry after an implementation postcondition), [ADR-0015](0015-setup-recorded-trust-baseline.md) (a third provenance source, a second writer of the reviewed record, the refresh).

## Context

A run asked the operator to type commands that carried no decision: `ballast trust` and `ballast setup` after a change merged on the default branch, `ballast discard-runs` and a forced re-trust after a dead step, a resume after a usage limit, a separate `approve` per gate. The operator drives runs from an agent session (Claude Code or Codex, outside any `ballast run` step), so every such command was a relay of something already decided, or of nothing. A human gate is worth its cost only when it asks for a decision.

## Decision

### Agent command matrix

"Agent session" is the operator's own Claude Code or Codex session, outside any step. An agent inside a step runs no `ballast` command. `tools/spec_workflow/actor.py` holds this matrix as data; the policy table and this table name the same commands.

| Command | Agent session | Recorded actor | Human-gated run | Chat run | Autonomous run |
| --- | --- | --- | --- | --- | --- |
| `ballast setup` | may run | none | yes | yes | yes |
| `ballast intake` | may run | none | yes | yes | yes |
| `ballast run status` | may run | none | yes | yes | yes |
| `ballast run start` | may run, with `--relayed-by` | none: a human-gated run has no operator run record | yes | n/a | n/a |
| `ballast run start --mode chat` | may run, with `--relayed-by` | relayed mode start | n/a | yes | n/a |
| `ballast run start --mode autonomous` | relays after a yes in chat, with `--relayed-by` | relayed mode start | n/a | n/a | yes, when eligible |
| `ballast run resume` | relays, with `--relayed-by`; `--ref` for a block that carries a decision | relayed block resolution | yes (no record) | n/a | yes |
| `ballast run continue` | relays, with `--relayed-by` and `--ref` | relayed block resolution or mode change | n/a | n/a | yes (Autonomous source only) |
| `ballast run step --headless` | may run | none (step records) | n/a | yes | n/a |
| `ballast run step` | refused (needs a terminal) | none | n/a | operator | n/a |
| `ballast run publish` | may run | none | n/a | yes, after a current final approval | runner publishes |
| `ballast run approve` | relays after a yes in chat, with `--relayed-by` | relayed gate approval | refused | yes | refused |
| `ballast run reject` | refused (terminal only) | operator | operator | operator | n/a |
| `ballast run resolve` | refused (terminal only) | operator | operator | operator | n/a |
| `ballast run mode` | refused (terminal only) | operator | operator | operator | n/a |
| `ballast trust` | may run outside a step, on a checkout the session set up; refused inside one | none (`source: trust`) | | | |
| `ballast discard-runs` | may run | none | | | |
| `ballast ledger` | may run | as before | | | |

By autonomy level:

- **Human-gated**: the session may start and resume the run with `--relayed-by`; every gate is a Spec Kit engine gate that prompts only at the operator's terminal, so nothing in the run is recorded as relayed. A relayed `approve` is refused.
- **Chat**: the session may start the run, run `step --headless`, and relay `approve` (one gate or a batch) after the operator's yes in chat. `reject`, `resolve`, `mode` and an interactive `step` stay at the operator's terminal.
- **Autonomous**: the session relays the start after a yes in chat, and `resume` and `continue` of a stopped run. A relayed `approve` is refused: the run has no human gate before merge.

### Who acted (R7)

Every record that says who acted (`HD-NNNN` human decisions, `mode_history` entries) takes its actor from one rule: `--relayed-by SESSION` given, the actor is `relayed` and the session is recorded (`[A-Za-z0-9][A-Za-z0-9._:-]{0,79}`, never matching the human-approval wording guard); otherwise, stdin and stdout both terminals, the actor is the `operator`; otherwise the command is refused before anything is written. `start`, `resume`, `continue` and a Chat `approve` accept `--relayed-by`; every other command refuses it. A relayed gate approval's reference is `relayed approve GATE` and quotes no chat text. Every renderer (`record.md`, `ballast run status`, the Chat PR section, the ledger's gate event) shows `relayed by agent session S` and never `by operator` for a relayed record.

### Decisions in blocks (D-08)

A relayed `resume` or `continue` of a block that carries a decision needs `--ref` naming the operator's in-chat answer (for example `Issue #147 comment, option 2`). Only `upstream-sync`, `interrupted` (including a usage limit) and `postcondition` carry no decision; every other category, including any added later, does until it is classified. `continue` already requires `--ref` for every block. Today's preconditions still refuse first: `tamper` and `unfinished-step` never resume in Autonomous.

### Trust follows the reviewed default branch (D-02)

Before `ballast run`, `ledger` or `intake`, the global `ballast` command asks the launcher's `status --json` why it would refuse. On `inputs-changed` or `pin-mismatch`, and when the pinned standard declares `[setup] refresh = true`, it runs the pinned standard's `tools/setup --refresh` from the verified cache, ignores its exit status, and executes the launcher as before. Setup, under the exclusive checkout lock, records a baseline with `source: default-branch` only when, in order:

1. the standard is outside the checkout, and neither `BALLAST_TAMPERED` nor the `in-progress` marker exists;
2. the baseline's provenance names a repository, `ballast.toml` pins the same one (case-folded), and `ballast trust` reviewed it on this machine;
3. every changed protected input is either installed by setup or a regular file committed at `HEAD` and unchanged from it; `.venv`, the `.git` pointer, links and uncommitted files are never attributable;
4. every committed change equals the default branch, observed through ADR-0015's throwaway repository (an `insteadOf` rewrite, no default branch, a timeout or no access all refuse; a link or a submodule is not the file);
5. after the normal installation regenerates `.ballast/spec_workflow`, every installed input equals the installation record, every committed one its observed blob, every other one the previous baseline, and `claude-settings.json` equals what `ballast.toml` produces.

It then re-snapshots, restores the previous baseline and provenance on any difference, and adds the new (`ballast.toml`, constitution) pair to the reviewed record for that repository. The first `ballast run` afterwards prints `trust baseline refreshed from OWNER/NAME BRANCH at COMMIT12` once and records it in the run's ledger. A plain `ballast setup` does the same when its own decision skipped. The launcher's comparison, refusals and markers are unchanged, so anything else still needs `ballast trust`.

Two narrowings of D-02 are listed for merge review: the any-bytes rule applies only to refreshing an existing baseline of the same repository (ADR-0015's fresh-checkout path keeps its reviewed-pair check), and `.venv` changes are never attributable.

### Trust checks the generated settings (R6)

`merge_permissions` moved to the launcher, which is now the one producer of `claude-settings.json`. `ballast trust` refuses, writing nothing, when the installed settings differ from what `ballast.toml` produces or `[agents.permissions]` is malformed. It keeps today's terminal-free behavior outside a step (D-09) and its refusals with either marker.

### Batch approval, headless Chat steps and recovery (R9 to R14)

- `ballast run approve RUN GATE...` or `--through GATE` validates every gate under one lock, lists each decision with its artifact and digest, takes one typed line (or, relayed in Chat, no prompt), re-reads every digest and appends every `HD` in one atomic rewrite: all or none.
- `ballast run step RUN PHASE --headless` runs a Chat step under the Autonomous confinement (bwrap, systemd scope, confined allow and deny lists, self-test) through `agent.py --confined`, then names the gates now pending and the batch command.
- `discard-runs` takes `--help` and refuses other arguments, and names `ballast trust` only when protected inputs differ from the baseline.
- A failed `validate-implementation` postcondition resumes at `implement` (amends ADR-0010's re-entry rule).
- A step whose CLI hit its usage limit, and whose processes were confirmed stopped, stops as `interrupted`, resumable without `discard-runs` or `trust`.
- An Autonomous start on a branch not named for the Issue offers the branch at a terminal (typed `switch BRANCH`) and otherwise prints the switch and rerun commands.

### Step boundary

The `in-progress` marker refuses every launcher command while a step runs, and the step's sandbox hides operator state; that is the boundary. Every step's environment also carries `BALLAST_AGENT_STEP=1`, and the launcher refuses every command but `status` while it is set. That variable is defence in depth, not a boundary.

### Dependency on engine gates

A relayed human-gated `start` or `resume` records no approval because Spec Kit engine `gate` steps prompt only at a terminal; without one they pause. If a later Spec Kit read gate answers from a non-terminal stdin, this ADR's guarantee for human-gated runs no longer holds, and the relay must be refused there.

## Consequences

- Merged configuration, pin and constitution changes need neither `ballast trust` nor `ballast setup`; a one-time `ballast trust` names the repository in a legacy baseline.
- The operator types only decisions: an approval in Chat, a `reject`, a `resolve`, a mode switch, an answer that `--ref` cites, and the merge.
- Every relayed decision is labeled with its agent session, in records, status and the PR.

## Residual risks

- Branch protection on the pinned default branch is now the only review of configuration changes, including widened `[agents.permissions]` and `[autonomous]`, for a checkout with an existing baseline of that repository.
- A relayed approval, or a relayed `--ref` resolving a decision block, is a labeled claim the launcher cannot verify.
- The terminal test (stdin and stdout are terminals) that guards `reject`, `resolve`, `mode` and human-gated approvals is not proof of a human: an agent session can allocate a pseudo-terminal. The boundary is ADR-0009 D-4's, and this ADR makes agent sessions routine `ballast` callers (first plan review).
- `ballast trust` has no terminal test (D-09): on a checkout the operator's agent session set up, that session can vouch for its own protected-input changes outside a step. Only the step boundary (the `in-progress` marker, and the sandbox hiding operator state) keeps an agent inside a step from doing so.
- `ballast trust` run by an agent session on a checkout whose `[github] repository` it repointed records that repository as reviewed in operator state shared by every checkout, so later default-branch bytes of that repository refresh automatically in each worktree pinning it.
- To refresh, `ballast run`, `ledger` and `intake` may download the newly pinned standard before the launcher runs (never inside a step, never for `run status`); a failed download skips the refresh and the launcher's own refusal shows.
- A step's usage-limit stop is classified from the agent's output tail, which the agent controls; it can turn its own failure into a decision-free `interrupted` block. Resume reruns the step, so the gain is bounded.
- `.venv` changes still need `ballast trust`.
- `BALLAST_AGENT_STEP` is not a boundary.

## Rejected alternatives

- Refreshing inside the launcher or `run.py`: neither can download a newly pinned standard, and `run.py` runs from the installation the refresh replaces.
- Inferring the agent session from provider environment variables: undocumented, spoofable and absent for Codex.
- Labeling terminal-less commands with an `unnamed` session: it hides which session acted.
- Allowing every relayed resume (the first plan): an agent could resolve its own run's decision block unseen. Refusing relayed resolution of decision blocks outright: the operator would type a command for a decision already given in chat (D-08 chose `--ref`).
- Leaving `ballast run mode` without a terminal: a session could switch a human-gated run to Chat and relay its gates.
- Approving several gates by looping the single-gate path: a crash or a failing third precondition would leave gates half-approved.
