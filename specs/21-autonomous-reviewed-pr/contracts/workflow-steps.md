# Contract: `ballast-autonomous` 1.2.0 steps

Changes from 1.1.0 ([workflow.yml](../../../templates/spec-kit/workflows/autonomous/workflow.yml)). Every other step is unchanged. Shell steps still receive only the run ID plus fixed flags.

## Inserted after `validate-implementation`

```yaml
  - id: checks-implementation
    type: shell
    run: python3 -I -S .ballast/spec_workflow/artifacts.py run-checks --run {{ context.run_id }} --feedback
```

## Inserted after `record-implementation-review`, three times (N = 1, 2, 3)

```yaml
  - id: fix-N
    command: speckit.ballast.fix
    integration: "{{ inputs.integration }}"

  - id: record-fix-N
    type: shell
    run: python3 -I -S .ballast/spec_workflow/artifacts.py record-fix --run {{ context.run_id }}

  - id: checks-fix-N
    type: shell
    run: python3 -I -S .ballast/spec_workflow/artifacts.py run-checks --run {{ context.run_id }} --feedback

  - id: review-fix-N
    command: speckit.ballast.review
    integration: "{{ inputs.review_integration }}"
    input:
      args: implementation-recheck

  - id: review-specialists-fix-N
    command: speckit.ballast.review
    integration: "{{ inputs.review_integration }}"
    input:
      args: specialists-recheck

  - id: record-fix-review-N
    type: shell
    run: python3 -I -S .ballast/spec_workflow/artifacts.py record-decision --run {{ context.run_id }} --point implementation-review --recheck
```

`workflow.version` becomes `1.2.0`.

## Step behavior

| Step | When the fix state does not match | When it matches |
| --- | --- | --- |
| `checks-implementation` | always runs | records feedback results; a failed command is not a block; tamper, tree change and wall time still block |
| `record-implementation-review` | (always runs) | records the reviews. If a fix is needed, sets `fix-pending` and writes the fix input, or blocks `limit`/`fix-cycles` when the cycles are spent or `review-finding` when the run's workflow copy has no fix steps (R19). If no fix is needed, freezes the tree |
| `fix-N` (wrapper) | skips: no agent, no step count, no `steps.jsonl` entry | runs `speckit.ballast.fix` confined |
| `record-fix-N` | exits 0, writes nothing | requires that the last unconsumed step is a `speckit.ballast.fix` that ran, and that `check_implementation` passes (else a postcondition block). Increments `fix.cycles`, sets `review-pending`, re-renders the record |
| `checks-fix-N` | exits 0, writes nothing | as `checks-implementation` |
| `review-fix-N`, `review-specialists-fix-N` (wrapper) | skip | run as reviewer steps |
| `record-fix-review-N` | exits 0, writes nothing | as `record-implementation-review`, with `fix_cycle = N`, superseding the current implementation and specialist reviews |
| `record-resolutions` | (always runs) | also refuses unless the fix state is `idle` and the tree is frozen |

The wrapper and the shell steps read the fix state from `run.json` at the start of the step. "Matches" means `fix-pending` for `fix-N`, and `review-pending` for the checks, review and recheck-recorder steps of a cycle.

## Command contracts

- `speckit.ballast.fix`: input is `.specify/workflow-state/fix-input/<slug>.json` (untrusted data). It may change code, tests and the feature's `tasks.md` and `decisions.md`. It must not create drafts, change reviews or the `autonomous/` directory, or run the `[checks]` commands. It ends with a short summary of what it changed per finding and check, and never claims approval.
- `speckit.ballast.review implementation-recheck` / `specialists-recheck`: the same draft contract as `implementation` / `specialists`, plus the fix input. Each listed finding is either resolved (disposition `resolved`, with a reason) or still present. The command states the remaining cycles (`3 - cycles`) and that `open` is valid above `low` only while a cycle remains.
- Every decision and review command states the recorder's limits ([research R4](../research.md#r4-correctable-refusals-retried-inside-the-agent-wrapper)) and, for decide and review, the rule "paraphrase and cite a sourced human approval; never quote approval wording".
