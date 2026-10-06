# Contract: Chat run record and ledger events

There are two stores. Both are written only by trusted operator-side code.

- **Operator run record** (source of truth): `$XDG_STATE_HOME/ballast/<checkout>/runs/<run>/`. Its files are `run.json`, `steps.jsonl`, `events.jsonl`, `human-decisions.jsonl` and `manifests/` ([data-model.md](../data-model.md)). After each invocation it is archived under `<git common dir>/speckit-runs/<run>/operator/`. `_archive_operator` today copies to `autonomous/`; it is renamed by mode, and Autonomous keeps `autonomous/`.
- **Ledger** (the audit stream shared with headless runs): `<git common dir>/speckit-runs/<run>/events.jsonl`. It uses the existing schema, version 1, and Chat appends with `source: "runner"`.

## Ledger events from a Chat run

| When | Kind | `data` |
| --- | --- | --- |
| `start --mode chat` | `run` | `status: started`, `workflow_id: ballast-feature`, `workflow_digest` of the archived trusted definition, `policy_digest` as today, **new field** `mode: chat` |
| Each branch check | `branch_sync` | unchanged |
| Step start | `step` | `step_id` = the `ballast-feature` step ID of the phase, `status: started`, `log_line` = the Chat run's own monotonic counter |
| Step close | `step` | same `step_id` and `log_line` as its start, `status: completed` or `failed` (`interrupted` and `tampered` map to `failed`) |
| Step close | `snapshot` | tree and feature digests, as the runner snapshot |
| Gate approval or rejection | `step` started and completed for the gate step ID, then `gate` | `choice: approve` or `reject`, `log_line` of that gate step |
| Review step close | `review` | reviewer provider and model, role, `cross_provider`, verdict mapped to the ledger enum |
| `checks` | `verification` | one per command, with runner provenance, bound to the current digests |
| `mode` switch or continuation | `run` | **new value** `status: mode-changed`, with `mode` |
| Draft PR checkpoint or publish | `pull_request` | unchanged |

`_semantic_problems` already accepts this order: one `run started` first, each step's completion after its start, and a gate matched to a completed step entry. The only schema change is the additive `mode` field on `run` and the `mode-changed` value in the `run.status` enum; `ledger-schema.md` documents both.

## Ledger report for a Chat run

`ballast ledger report --run RUN` recognizes `mode: chat` on the `run` event. It reads the archived `archive/run/workflow.yml` (the trusted `ballast-feature` definition copied at start) and `archive/run/chat.json` (the phase graph), not engine `state.json` or `log.jsonl`. Compliance is computed against the same step and gate IDs:

- every producer step's latest entry completed;
- every gate's latest choice `approve`, made after the latest completion of the steps it covers;
- review and convergence evidence fresh at final acceptance, as today.

The report's run section shows the mode history.

## Archive layout for a Chat run

```text
<git common dir>/speckit-runs/<run>/
├── events.jsonl          # ledger (existing)
├── policy.json           # existing archive_policy
├── run/
│   ├── workflow.yml      # trusted ballast-feature definition, copied at start
│   └── chat.json         # phase graph projection, copied at start
├── state/agents/<step>/  # stdout.log + meta.json per step (local only)
└── operator/             # copy of the operator run record after each invocation
```
