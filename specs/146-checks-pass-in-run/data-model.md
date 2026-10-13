# Data model: Make the [checks] test command pass inside an Autonomous run

No new file or store. The entities below are values the runner builds or records in operator state.

## Check environment

The environment `run_commands` gives every check process ([contracts/check-environment.md](contracts/check-environment.md)).

| Field | Rule |
| --- | --- |
| Source | The runner's process environment (`os.environ`) |
| Secret-named variables | Dropped by `confined_env(env, None)`, unchanged |
| `BALLAST_GIT` | Removed |
| `BALLAST_SPEC_WORKFLOW`, `SPECKIT_WORKFLOW_RUN_ID` | Removed |
| `PATH` | Every guard entry removed ([research R2](research.md#r2-how-a-guard-entry-on-path-is-recognized)); other entries, including empty ones, keep their order; unset stays unset |
| Every other variable | Kept with its value |

Not stored. Built once per `run_commands` call and passed to each command's `subprocess.run`. The bwrap argv is still built from the operator's environment.

## Run variables

`autonomy.RUN_VARIABLES = ("BALLAST_SPEC_WORKFLOW", "SPECKIT_WORKFLOW_RUN_ID")`. Set for workflow and Chat steps by `run.py` and `chat.py` (unchanged). Read by `ledger._operator_step_guard` (unchanged) and removed by the check environment.

## Check result (additive field)

Each element of `checks.json` and of a `checks-feedback.jsonl` entry's `results`:

| Field | Type | Status |
| --- | --- | --- |
| `command` | string | unchanged |
| `exit` | int | unchanged (124 on timeout) |
| `seconds` | float | unchanged |
| `timed_out` | bool | unchanged |
| `provenance` | `"runner"` | unchanged |
| `output_tail` | string | unchanged (feedback, failed only) |
| `timeout_seconds` | int | **new**: the timeout applied, `timeout_minutes * 60` or the run's remaining wall time when smaller |

Readers ignore unknown keys; a result without `timeout_seconds` (an older run) is named with the configured timeout instead.

## Check timeout

`[checks] timeout_minutes` in protected `ballast.toml`, parsed by `autonomy.parse_checks`, bounded by `CHECK_TIMEOUT = (1, 240, 30)` (unchanged). This repository sets `60`.

## Unaddressable timeout block

A block of category `limit` with `limit = "check-timeout"` ([contracts/timeout-block.md](contracts/timeout-block.md)).

| Field | Value |
| --- | --- |
| `category` | `limit` (class "exhausted limits") |
| `limit` | `check-timeout` (new in `LIMIT_KINDS`; not in `FIXED_LIMITS`, so resumable) |
| `condition` | `check timeout reached: ` + each timed-out command with its applied timeout |
| `recovery` | `LIMIT_RECOVERY["check-timeout"]` |
| `command` | `ballast run resume RUN_ID` |
| `step_id` | the recorder step that blocked |
| `evidence` | the review reports, as for the other recorder blocks |

### When it is recorded

```text
implementation-review recorder (first or --recheck), fix loop enabled
  failed = latest feedback results with exit != 0
  if failed and all(timed_out) and not blocking and not open_to_fix:
      block check-timeout            # fix-cycle count unchanged
  else:
      existing rules: block / limit fix-cycles / fixing / strict
```

### Resume transition

| Blocked step | Re-entry step |
| --- | --- |
| `record-implementation-review` | `checks-implementation` |
| `record-fix-review-N` | `checks-fix-N` |

The earliest of this step and any changed-input step wins, as for every resume (#21 R6).
