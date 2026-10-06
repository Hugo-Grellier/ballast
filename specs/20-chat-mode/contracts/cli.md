# Contract: Chat commands

Every command is `ballast run ...` from the checkout root. The launcher first refuses on a changed trust baseline, a tamper marker or an `in-progress` marker; the last refusal now names the active run and step ([step-runner.md](step-runner.md)). `run.py` then refuses on the tamper marker again before importing other modules, as today. Exit codes are the existing ones: `0` done, `1` blocked (failed check, refused step, upstream-sync block), `2` refused (usage, wrong state, launcher), `4` a step changed protected inputs, `130` interrupted.

Human-gated and Autonomous invocations without the new options behave as before (SC-007).

## `start --mode chat`

```text
ballast run start --mode chat -i feature_directory=specs/N-slug \
    [-i idea="Issue #N: ..."] [-i integration=auto|claude|codex] [-i model=NAME]
```

- `--wall-time` and `--max-agent-steps` are refused with `--mode chat`, as with human-gated.
- It refuses unless exactly one valid `feature_directory` is given (the existing human-gated rule), the Chat integration can run confined (bwrap self-test, and for Codex the nested-sandbox probe), and no other Chat run in this checkout has an active step.
- In order, it:
  1. creates the run record (`mode: chat`, `workflow: ballast-chat`);
  2. archives the `ballast-feature` definition and the phase graph;
  3. appends the ledger `run` event with `mode: chat`, before synchronization, so a blocked start still has a valid ledger for its later steps (review finding ENG-004);
  4. runs branch synchronization with `starting=True` (pins the branch and feature);
  5. prints the handoff summary;
  6. runs the Draft PR checkpoint.
- **No agent runs.** A blocked synchronization leaves the record with no steps and prints the existing `BLOCKED_UPSTREAM_SYNC` line.
- `idea` is stored and used as the `specify` prompt; if omitted, `specify` uses `Issue #N`.

## `step`

```text
ballast run step RUN_ID PHASE [--kind KIND] [-i integration=claude|codex] [-i model=NAME]
```

- `PHASE` is a phase of [phase-graph.md](phase-graph.md). `--kind` is required for `review` and refused otherwise.
- Refused when the run is not a Ballast-driven (`ballast-chat`) run or is `published`, or when the run lock is held.
- The sequence is [step-runner.md](step-runner.md) §Lifecycle. Stdout ends with one line, `Step <step>: <outcome>`, then the failing check, if any, then the next allowed actions.
- In `chat` mode the agent is interactive. In `human-gated` mode the same phase runs headless through `agent.py` with unchanged argv, and the same lifecycle, checks and records apply around it.
- Exit: `0` completed, `1` failed or refused by an entry condition, `4` tampered, `130` interrupted.

## `status`

```text
ballast run status RUN_ID
```

- Prints the handoff summary ([data-model.md](../data-model.md#handoff-summary-derived-never-stored)). It writes nothing, except that it appends an `out-of-step-change` event when the tree differs from the last manifest. It runs no agent and no synchronization.
- It also works on a `ballast-autonomous` run: it shows the record and points to `continue --mode chat`.

## `approve`, `reject`

```text
ballast run approve RUN_ID GATE
ballast run reject RUN_ID GATE --reason TEXT
```

- `GATE` is `scope`, `intent`, `plan`, `tasks`, `implementation`, `spec-reconciliation` or `final`.
- Refused unless stdin and stdout are a TTY, no step is active, and the gate's precondition ([phase-graph.md](phase-graph.md#gates)) passes now. Each precondition check is recorded.
- It prints the gate, the artifact path, its digest and, for a carried Autonomous run, the provisional decisions this approval supersedes. The operator must then type `approve GATE` (or `reject GATE`) exactly. Anything else changes nothing and exits `2`.
- `approve intent` also writes and registers the human approval block in `intent.md` (`artifacts.record_intent`).
- `approve tasks` records the implementation baseline tree in `run.json`.
- `approve final` sets the run status to `completed`.

## `resolve`

```text
ballast run resolve RUN_ID DEC-NNNN
```

- Refused unless there is a TTY, no step is active, and `decisions.md` has `DEC-NNNN — Proposal` with a `Resolution`.
- It shows the resolution text and its digest, then requires typing `resolve DEC-NNNN`. It records a `decision-resolution` human decision. In a Chat run, the decisions check counts only resolutions with a current human decision.

## `checks`

```text
ballast run checks RUN_ID
```

- Runs every `[checks] commands` entry under the confined check loop. With no `[checks]` table, it records `unavailable`.
- Refused while a step is active. No agent and no synchronization.

## `mode`

```text
ballast run mode RUN_ID chat|human-gated --reason TEXT
```

| Source | Target | Result |
| --- | --- | --- |
| `ballast-chat` run | the other of `chat`, `human-gated` | Same run. Appends a `switch` entry and a `mode-change` HD. |
| `ballast-feature` engine run, paused or failed, with a branch pin | `chat` | New linked Chat run, `continues: RUN_ID`; `resume RUN_ID` is refused from then on. |
| any run | `autonomous` | Refused: "autonomy is never raised after start". |
| a run with an active step | any | Refused; the reason names the step. |

## `continue --mode chat`

```text
ballast run continue RUN_ID --reason block-resolved|changes-requested --ref TEXT [--mode chat|human-gated]
```

- Without `--mode`, or with `--mode human-gated`, behavior is unchanged: `ballast-continue`.
- With `--mode chat`, it applies the same source refusals. It then:
  1. records the human decision;
  2. lowers the source `autonomous → chat` and sets it to `continued`;
  3. re-renders the source's `autonomous/record.md`;
  4. creates the linked Chat run with the source's pin;
  5. runs branch synchronization for the new run. When it is blocked, the Chat run keeps no pin of its own, and each later `step` synchronizes from the source's pin, as the continuation did, until one succeeds (review finding ENG-001);
  6. prints the handoff summary, which lists the provisional decisions still to be superseded.
- No agent runs.
- `--mode autonomous` is refused, with the existing "never raised" wording.

## `publish`

```text
ballast run publish RUN_ID
```

- For a `ballast-chat` run, it is refused unless the `final` approval is current (the tree equals the approved tree) and no step is active.
- It then runs the mode-aware publisher ([pr-evidence.md](pr-evidence.md)) and sets the run to `published`.
- No agent and no check runs.
- The Autonomous `publish` behavior is unchanged.

## `resume`

`resume RUN_ID` of a `ballast-chat` run is refused with "Chat runs continue with `ballast run step RUN_ID PHASE`; see `ballast run status RUN_ID`". `resume` of a `ballast-feature` run that a Chat run continues is refused and names that Chat run.
