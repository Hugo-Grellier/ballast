# Data model: Reach a reviewed PR with provisional Autonomous decisions

Every record below is operator state outside agent reach, written only by trusted code (`run.py`, `artifacts.py` shell steps, `agent.py`). The exceptions are agent-written drafts and the committed `autonomous/record.md`, which the recorders render. Field names extend the #27 records ([27 data model](../27-autonomous-core/data-model.md)). The run record stays at `version: 1`. Every new field is optional, so v0.6.x records still validate.

## Run record (`<operator run dir>/run.json`)

New and changed fields:

| Field | Type | Written by | Rule |
| --- | --- | --- | --- |
| `limits.wall_time_minutes` | int | `start` | Unchanged; the limit is active time (R8). |
| `limits.deadline` | ISO time | v0.6.x records only | Legacy. New records omit it; `validate_run` accepts either `deadline` or `active_seconds`. |
| `active_seconds` | number ≥ 0 | `run.py` at invocation end; resume closes a crashed invocation | Never decreases. |
| `invocation_started_at` | ISO time or null | `run.py` at invocation start, cleared at end | Non-null means an invocation is open (or died). |
| `fix` | object, [fix state](#fix-state) | recorders, `record-fix`, resume reset | Absent means `{"cycles": 0, "state": "idle"}`. |
| `resumes` | list of [resume entries](#resume-entry) | `resume` | Append-only. |
| `status` | enum | trusted code | New transition `stopped → active`, legal only inside `autonomy.resume_run` with a `block-resolution` decision ID. |

Unchanged on resume (R18): `mode_history`, `risk`, `limits` (apart from the legacy seeding below), `integration`, `review_integration`, `cross_provider`, `integration_fallback`, `eligibility`, `issue`, `feature`, `workflow`, `agent_steps` (only grows).

Legacy seeding: when a record has `limits.deadline` and no `active_seconds`, resume sets `active_seconds = min(limit, latest recorded time - started_at)` and drops `deadline`.

### Fix state

```json
{"cycles": 0, "state": "idle"}
```

- `cycles`: 0–3 per run. Incremented only by `record-fix`. Resume never resets it (FR-001).
- `state` transitions:

  | From | Event | To |
  | --- | --- | --- |
  | `idle` | implementation-review recorder: fix needed, `cycles < 3`, fix loop present (R19) | `fix-pending` |
  | `idle` | same, `cycles == 3` | block `limit` (`fix-cycles`) |
  | `idle` | same, no fix needed | `idle` (tree frozen) |
  | `fix-pending` | `record-fix` after a fix step that ran | `review-pending` (`cycles += 1`) |
  | `review-pending` | recheck recorder: fix needed, `cycles < 3` | `fix-pending` |
  | `review-pending` | recheck recorder: fix needed, `cycles == 3` | block `limit` (`fix-cycles`) |
  | `review-pending` | recheck recorder: no fix needed | `idle` (tree frozen) |
  | any | resume with re-entry at or before `record-implementation-review` | `idle` (cycles kept) |

- Fix needed: see [research R2](research.md#r2-what-triggers-a-fix-and-what-happens-when-the-cycles-run-out).
- Invariant: `record-decision --point decision-resolution` refuses unless `state == "idle"` and `frozen_tree` is set.

### Resume entry

```json
{"at": "…", "decision_id": "HD-0001", "block_category": "decision",
 "block_step": "record-tasks", "reentry_step": "decide-tasks",
 "changed_inputs": ["specs/21-…/spec.md"]}
```

## Block (`block.json`, history in `blocks.jsonl`)

New optional fields:

| Field | Type | Rule |
| --- | --- | --- |
| `limit` | `agent-steps` \| `wall-time` \| `fix-cycles` \| `retries` | Only for category `limit`. Resume refuses `agent-steps` and `wall-time`. |
| `inputs` | `{path: sha256}` | Block-time digests of the [re-entry inputs](research.md#r6-re-entry-step-fr-009), written by `run.py` when it records the block; `outside` holds the tree digest outside the feature directory. |
| `command` | string | `ballast run resume RUN_ID` for resumable categories; `BLOCK_COMMAND` accepts it. |

Block class (derived, never stored): `autonomy.BLOCK_CLASSES[category]`, one of `conflict`, `missing authority`, `exhausted limits`, `unsafe uncertainty` (R15).

### Resume eligibility

| Status / block | `resume` outcome |
| --- | --- |
| `stopped`, block in `decision`, `contradiction`, `review-finding`, `postcondition`, `ineligible`, `interrupted`, `limit` (`fix-cycles`, `retries`), `upstream-sync` raised by a resume | resumes |
| `stopped`, `upstream-sync` from a start (no engine state) | refuses: start again |
| `stopped`, `limit` (`agent-steps`, `wall-time`) | refuses: limits cannot be raised |
| `stopped`, `tamper`, `unfinished-step` | refuses: `ballast discard-runs` |
| `stopped`, `forge`, `permission` | refuses: `ballast run publish RUN_ID` |
| `active`, invocation lock held | refuses: active invocation |
| `active`, lock free | closes the clock, records an `interrupted` block, resumes |
| `completed` | refuses: `ballast run publish RUN_ID` |
| `published` | refuses: `ballast run checkpoint RUN_ID` |
| `continued` | refuses: resume the continuation run (unchanged) |

## Human decision (`human-decisions.jsonl`)

Unchanged schema. Resume appends `{"kind": "block-resolution", "ref": …, "resolves": "block", "by": "operator"}`. `ref` is 1–500 characters. Resume refuses a `--ref` that matches `HUMAN_APPROVAL`, because a block resolution is not an approval of any provisional decision.

## Agent step entry (`steps.jsonl`)

New optional fields, written by the wrapper:

| Field | Rule |
| --- | --- |
| `attempt` | 1–3 within one step invocation. |
| `refused` | Validator message (≤ 500 characters) for an attempt whose drafts were refused; `_qualifying_steps` skips such entries. |
| `limit` | `retries`, `agent-steps` or `wall-time` when the wrapper exits `EXIT_LIMIT`. |

A skipped fix-cycle step writes no entry.

## Provisional decision (`decisions.jsonl`)

New runner-owned fields:

| Field | Rule |
| --- | --- |
| `agent.attempts` | Number of attempts the recorded draft took (1 when no retry). |
| `agent.refusals` | Validator messages of the refused attempts, in order. |
| `fix_cycle` | 0 for the first implementation review, N for the recheck after fix cycle N. |
| `supersedes` | Now also set automatically for every single point and review point that is recorded again after a resume or a fix cycle (R6). |

## Feedback checks (`checks-feedback.jsonl`, append-only)

One line per `run-checks --feedback`: `{"cycle": N, "at": …, "results": [{"command", "exit", "seconds", "timed_out", "provenance": "runner"}]}`. `checks.json` stays the final `run-checks` result that the record and packet show as "run-checks".

## Fix input (`.specify/workflow-state/fix-input/<feature-slug>.json`)

Read-only to agent steps (under `.specify/`). Rewritten by the implementation-review recorder when it sets `fix-pending`:

```json
{"feature": "specs/N-slug", "cycle": 1,
 "findings": [{"decision": "PD-0031", "id": "F-002", "severity": "medium",
               "label": "implementation-bug", "reason": "…", "report": "specs/N-slug/reviews/engineering.md"}],
 "checks": [{"command": "…", "exit": 1, "timed_out": false, "output_tail": "…"}]}
```

`output_tail` holds the last 4000 characters, made printable. Agents treat it as untrusted data.

## Invocation lock

`<operator run dir>/invocation.lock`, an exclusive non-blocking `flock` held by `start --mode autonomous`, Autonomous `resume`, `publish` and `checkpoint` for the whole invocation (R13).

## Constants

| Name | Value |
| --- | --- |
| `FIX_CYCLES` | 3 |
| `DRAFT_RETRIES` | 2 |
| `AGENT_STEPS` | `(1, 200, 40)` |
| `WALL_TIME` | `(1, 1440, 240)`, active minutes |
| `AUTONOMOUS_STEPS` | step IDs of `ballast-autonomous` 1.2.0, in order (test-compared with `workflow.yml`) |
