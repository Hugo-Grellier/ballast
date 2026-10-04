# Contract: `ballast run` command line

The trusted launcher (`launcher.py`) still verifies the checkout and then executes `run.py`. Every refusal below exits `2` before Spec Kit starts and before any agent step. It prints `ballast: refusing: <reason>` and a next command.

## `ballast run start`

```text
ballast run start [--mode human-gated|autonomous] [--wall-time MINUTES] [--max-agent-steps N] \
    -i idea="Issue #N: OUTCOME" -i feature_directory=specs/N-slug [-i integration=auto|claude|codex] \
    [-i issue=N]
```

- Without `--mode`, the run starts `ballast-feature` exactly as today (FR-001). `--wall-time` and `--max-agent-steps` are refused without `--mode autonomous`.
- With `--mode autonomous`:
  - `-i issue=N` is required and must match the number in `feature_directory`.
  - `run.py` checks eligibility (data-model: Eligibility result).
  - It creates the run record with `status=active`.
  - It sets `review_integration`.
  - It starts `ballast-autonomous` with inputs `idea`, `feature_directory`, `integration` and `review_integration`.
  - Mode, limits and eligibility are not workflow inputs.
- The current branch must not be the repository's default branch, and no open PR may exist for it (it is checked again at publish).

### Refusals

| Condition | Reason text (prefix) |
| --- | --- |
| Issue is closed, an Epic, has sub-issues, or has an open blocker | `not eligible for autonomous: scope gate: ...` |
| Missing `ready-for-agent` or a single intake scope comment | `not eligible for autonomous: issue has no recorded scope gate` |
| Scope comment lacks `Risk:` or `Privileged actions before merge:` | `not eligible for autonomous: scope record lacks <field>` |
| Risk not in the narrowed policy | `not eligible for autonomous: risk Rn excluded by ballast.toml [autonomous]` |
| Unauthorized pre-merge privileged action | `not eligible for autonomous: privileged action <a> before merge` |
| `gh` unavailable or the query failed | `cannot check autonomous eligibility: <cause>` (fails closed) |
| Default branch or existing PR | `autonomous needs a feature branch without an open PR` |

Each refusal ends with: `Run it human-gated instead: ballast run start -i idea=... -i feature_directory=...`. Widening keys found in `ballast.toml` are printed as `ignored [autonomous] <key>: cannot widen eligibility`.

## `ballast run resume RUN_ID [-i integration=...]`

Unchanged for human-gated and `ballast-continue` runs. For a run whose effective mode is `autonomous`, it is refused with: `autonomous resume is not supported until safe resume (#18); continue human-gated: ballast run continue RUN_ID --reason block-resolved --ref TEXT` (FR-023, AC-014).

## `ballast run continue RUN_ID --reason block-resolved|changes-requested --ref TEXT`

- Valid only for an Autonomous run with `status` `stopped`, `completed` or `published`. The run must not already be `continued`.
- Appends a human decision (`block-resolution` or `merge-feedback`) and a `lower` mode change. Then it marks the source run `continued` and starts a new `ballast-continue` run with `continues=RUN_ID`, copying `implementation-baseline.json` from the source run's state.
- Every gate in `ballast-continue` prompts a human. Earlier provisional decisions stay in the log and in `record.md` (FR-004, AC-017).
- There is no option to raise the mode, and `--mode` is refused here (FR-003).

## `ballast run publish RUN_ID`

Retries publication for an Autonomous run whose status is `completed`, or `stopped` with a `forge` block. It never resumes the workflow and never runs an agent.

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | Workflow completed; for Autonomous, the Draft PR is published |
| 1 | Workflow ended without completing; for Autonomous, a block is printed |
| 2 | Refused before start |
| 130 | Interrupted |

## Agent wrapper additions (`agent.py`)

| Exit | Cause |
| --- | --- |
| 3 | Existing: `RECONCILE_STATUS: BLOCKED_*` |
| 4 | Existing: protected change |
| 5 | New: limit exhausted before or during the step |
| 2 | Existing usage error; also a run record that is not `active`, or that is missing for an Autonomous workflow |

For an Autonomous run, the wrapper:

1. reads the run record;
2. refuses unless `status == active`, `deadline` has not passed and `agent_steps < max_agent_steps`;
3. increments `agent_steps`;
4. bounds the agent wait by the remaining time.

The protected-file check runs as before.
