# Contract: `ballast run` commands

Exit statuses as today: 0 success, 1 blocked, 2 refused, 130 interrupted. Every refusal prints `ballast: refusing: <reason>` on stderr and writes no operator record, no human decision, no pin and no engine state. Human-gated `start`, `resume` and `continue` keep their current behavior (FR-025), apart from the wording of the `unpinned` recovery text (R11).

## `ballast run resume`

```text
ballast run resume RUN_ID [--ref TEXT]
```

For a `ballast-autonomous` run (an operator run record exists):

| Situation | Result |
| --- | --- |
| any `-i NAME=VALUE`, `--mode`, `--wall-time`, `--max-agent-steps` | refused: "an Autonomous resume keeps the mode, risk, limits and integrations recorded at start" |
| `--ref` empty, over 500 characters, or matching `HUMAN_APPROVAL` | refused |
| status or block not resumable ([data model](../data-model.md#resume-eligibility)) | refused, naming the command that applies |
| invocation lock held | refused: "run RUN_ID has an active invocation" |
| branch sync blocked | exit 1 (130 when interrupted); prints the `BLOCKED_UPSTREAM_SYNC` lines; records block `upstream-sync` with command `ballast run resume RUN_ID`; no human decision; no agent |
| otherwise | records `block-resolution`, prints `Recorded HD-NNNN (block-resolution); run RUN_ID resumes in Autonomous at <step>` plus `changed during the block: <paths>` when any, runs the workflow, then publishes or blocks like `start` |

Output order: the sync line comes first, then the resume line, then the engine output, then the publish or block lines, then the `Draft PR:` and packet lines.

For a run without an operator run record (human-gated), nothing changes.

## `ballast run continue`

Unchanged, plus one refusal checked after the existing `upstream-sync` refusal (FR-011, AC-011):

| Situation | Result |
| --- | --- |
| source run has no implementation baseline | refused: "run RUN_ID stopped before implementation; resume it in Autonomous: ballast run resume RUN_ID" |

## `ballast run checkpoint`

```text
ballast run checkpoint RUN_ID
```

| Situation | Result |
| --- | --- |
| extra arguments, or invalid RUN_ID | refused |
| no operator run record, or the workflow is not `ballast-autonomous` | refused: "run RUN_ID is not an autonomous run" |
| invocation lock held | refused: "run RUN_ID has an active invocation" |
| no open Ballast Draft PR for the run's branch | refused: "run RUN_ID has no Draft PR yet; ballast run publish RUN_ID opens it once the run completes". Exit 2, no ledger event, no packet, no archive write |
| PR found (`reused` / packet `published`, `updated`, `unchanged`) | prints the `Draft PR:` line and the packet line; exit 0 |
| `failed-retryable` | prints both lines; exit 1 |

It runs in any run status, `published` included. It starts no agent and does not read or write `run.json`, `decisions.jsonl`, `human-decisions.jsonl`, `block.json` or `record.md` (AC-023, AC-024). It runs before the `specify` lookup, like `publish`.

## Printed block

```text
Autonomous run blocked (<class>: <category>): <condition>
  option: <option> -> <consequence>
Recovery: <recovery>
Next: <command>
```

`<class>` is one of `conflict`, `missing authority`, `exhausted limits`, `unsafe uncertainty` (FR-023). For `limit` the condition starts with the limit that was reached: `agent-step limit`, `wall-time limit`, `fix-cycle limit (3)` or `draft retries (2)`.
