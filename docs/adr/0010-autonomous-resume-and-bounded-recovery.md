# ADR-0010: Autonomous runs resume in Autonomous and recover within fixed bounds

- Status: proposed (2026-10-06, with the plan of [feature 21](../../specs/21-autonomous-reviewed-pr/plan.md), research R1–R20). Agent-provisional: written in Autonomous run `fcba2ba4` and its continuation by the driving agent under the operator's standing authority for v1.0 issues; merging the feature PR is the human approval that accepts it.
- Feature: [21-autonomous-reviewed-pr](../../specs/21-autonomous-reviewed-pr/spec.md), FR-001 to FR-027
- Amends: [ADR-0004](0004-autonomous-provisional-decisions.md) (continuation rule). Builds on: [ADR-0005](0005-launcher-branch-synchronization.md)

## Context

ADR-0004 made every blocked Autonomous run continue human-gated "until #18". In the pilots after #18, three of four Autonomous runs ended in a block that `continue` could not recover: a block before implementation has no baseline for `ballast-continue`, a formatting limit on agent text ended a run, and an implementation review had no step to fix what it found. An Autonomous PR is not "reviewed" if the first finding ends the run, and an unattended run that cannot pause and resume safely is not unattended. Any recovery must keep the authority model of ADR-0004 and ADR-0005: agents never decide mode, limits or publication, and nothing runs an agent before the branch is synchronized.

## Decision

- **Autonomous resume** (R5). `ballast run resume RUN_ID [--ref TEXT]` continues a blocked or interrupted Autonomous run in Autonomous. The trusted runner takes the run's invocation lock, synchronizes the branch first (ADR-0005; the pin is read from operator state only), then records the operator's `block-resolution` human decision and moves the run from `stopped` to `active`. That transition exists only there. Resume refuses `-i`, `--mode` and limit flags: mode, risk, limits and integrations stay as recorded at start, and only an explicit operator action changes the mode.
- **Re-entry at the earliest changed input** (R6, R7). When a block is recorded, the runner keeps digests of the feature's discovery brief, spec, intent, plan files, tasks and decisions and, once implementation started, of the tree outside the feature. Resume re-enters at the blocked step, or at the validator of an input that changed during the block when that comes earlier. It rewrites the engine's own state (`.specify/workflows/runs/<id>/state.json`, which agents cannot write) so `specify workflow resume` starts there, and resets the runner's review freeze when it re-enters before the implementation review. The implementation baseline is kept.
- **Bounded fix loop** (R1–R3). `ballast-autonomous` 1.2.0 runs the `[checks]` commands as feedback after implementation, then up to three fix cycles per run (fix, feedback checks, the reviews again). The count lives in operator state and survives a resume. Check output reaches the fix agent only as a read-only data file the recorder writes. After the third cycle, a high or critical finding, a non-approved verdict or a failed check blocks the run as an exhausted limit.
- **Correctable draft retries** (R4). The agent wrapper runs the recorders' own draft checks after an Autonomous agent step; a refusal the agent can correct in its draft reruns the step with the validator's message, at most twice per step, each attempt counted. State refusals stay terminal and no validator is relaxed.
- **Active wall time** (R8, R9). The wall-time limit counts only time inside invocations; the agent-step limit, now 40 by default, counts every attempt and is the spend bound.
- `continue` stays the human-gated path after implementation; before implementation a human-gated `continue` points to `resume`, while `continue --mode chat` (#20) still continues in Chat.

## Consequences

- A blocked Autonomous run, before or after implementation, recovers without lowering, and the record lists every block resolution with its re-entry step.
- The trusted runner now writes one piece of engine state (the reposition). It depends on Spec Kit 1.0.11 resuming at `current_step_index`, which a real-engine test verifies.
- A rewind spends agent steps again under limits a resume cannot raise; a run that runs out blocks and continues human-gated.
- A run started under ballast-autonomous 1.1.0 keeps its own workflow copy, without fix steps: its findings block as before, and a second guard refuses decision resolution while a fix is pending.
- The default agent-step limit changes from 30 to 40.

## Rejected alternatives

- Lowering every recovery to human-gated: the status quo, which cannot resume a block before implementation.
- A new run ID per resume: it would split one run's decision log.
- A fresh engine run per resume, skipping completed steps: changes how the ledger imports the engine log; kept only as the fallback had the reposition failed.
- An agent-driven fix loop that iterates inside one step: the agent would control the bound.
- Truncating or rewriting agent text that breaks a limit: the recorder would author agent output.
