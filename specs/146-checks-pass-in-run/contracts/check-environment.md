# Contract: the check environment

Covers AC-001 to AC-006, FR-001 to FR-004, FR-012. See [data-model.md](../data-model.md#check-environment).

## Interface

```text
autonomy.GUARD: Path                      # tools/spec_workflow/guard; agent.GUARD refers to it
autonomy.RUN_VARIABLES: tuple[str, str]   # ("BALLAST_SPEC_WORKFLOW", "SPECKIT_WORKFLOW_RUN_ID")
autonomy.check_env(env: dict[str, str]) -> dict[str, str]
```

`check_env` is pure: it never reads `os.environ` or the filesystem and never mutates its argument.

## Rules

1. Start from `confined_env(env, None)`.
2. Drop `BALLAST_GIT` and each name in `RUN_VARIABLES`.
3. If `PATH` is present, split it on `os.pathsep` and drop every entry that is a guard entry: its `os.path.normpath` equals `os.path.normpath(GUARD)`, or its last two components are `spec_workflow` and `guard`. Rejoin the rest in order. An empty `PATH` stays empty; an absent one stays absent.
4. Return the result; everything else is kept as is.

## Callers

| Caller | Path | Gets `check_env` |
| --- | --- | --- |
| `artifacts.run_commands` | the only call site; every path below goes through it | yes |
| `artifacts.run_checks` (`--feedback`, final) | Autonomous `checks-implementation`, `checks-fix-N`, `run-checks` | yes |
| `artifacts._acceptance_checks` | runner acceptance checks (`read_only=True`) | yes |
| `artifacts.project_checks` | Chat runs and human-gated `ballast run checks` | yes |
| `agent._base_env`, Chat interactive launch, `run._environment`, `chat.py` | agent and workflow steps | **no**: unchanged |

`confined_argv` keeps receiving the operator's environment (`env=dict(os.environ)`) to locate the credential paths it hides; its argv does not change.

## Guarantees

- The confinement of a check (bwrap, read-only host, hidden credential paths, writable checkout minus protected inputs, read-only checkout for acceptance checks) is unchanged.
- No variable is added; `PATH` only loses entries.
- The protected-input and tree-change checks around `run_commands` are unchanged.
