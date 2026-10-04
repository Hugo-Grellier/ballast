# Contract: `[autonomous]` in `ballast.toml`

The table is optional. When it is absent, Autonomous allows R0, R1 and R2, authorizes no privileged action before merge, and uses 240 minutes and 30 agent steps.

```toml
[autonomous]
risk = ["R0", "R1"]                       # narrows the standard's R0, R1, R2
excluded_boundaries = ["agent authority"] # an R2 boundary listed in the scope record ⇒ ineligible
authorized_privileged_actions = ["secret provisioning"]
wall_time_minutes = 120
max_agent_steps = 24
```

| Key | Type | Effect | Widening input → handling |
| --- | --- | --- | --- |
| `risk` | list of `R0`/`R1`/`R2` | Intersected with `{R0,R1,R2}` | Any other value is ignored with a warning |
| `excluded_boundaries` | list of str | Narrows only | — |
| `authorized_privileged_actions` | list of str | Allows a declared pre-merge action | `merge`, `release`, `deploy` and `mark ready` are always ignored with a warning (FR-027) |
| `wall_time_minutes` | int 1–1440 | Default limit | Out of range → refusal at start |
| `max_agent_steps` | int 1–200 | Default limit | Out of range → refusal at start |
| any other key | — | — | Ignored, with the warning `cannot widen eligibility` (FR-007, AC-021) |

`ballast.toml` is a trusted input (`launcher.BASES`), so an agent edit fails the step as tampering. `tools/setup` already reads the file and must accept the new table without changing installed permissions.

The operator's `--wall-time` and `--max-agent-steps` override the project defaults for a single run, within the same ranges.

## `[checks]`

Required for Autonomous starts; ignored by human-gated runs. It names the commands the trusted `run-checks` step runs, confined, before final acceptance (research R-12).

```toml
[checks]
commands = [
  "uvx ruff check",
  "uvx ruff format --check",
  "uv run --no-project --python 3.13 --with pyyaml python -m unittest tests/test_*.py",
]
timeout_minutes = 30
```

| Key | Type | Effect |
| --- | --- | --- |
| `commands` | non-empty list of str | Each runs with `sh -c` in the worktree under bubblewrap (R-02); non-zero exit blocks |
| `timeout_minutes` | int 1–240, default 30 | Per command; a timeout blocks |

A missing table or an empty `commands` list refuses an Autonomous start before any agent step, naming `[checks]` as the remedy. `ballast.toml` is a trusted input, so an agent cannot change which checks count. This repository's own `ballast.toml` gains the table above in this feature.
