# Contract: operator opt-in (`ballast run`)

Implements FR-001, AC-003, AC-019, AC-020 and AC-021. Storage is described in [data-model.md](../data-model.md#fallback-setting).

## Start

```text
ballast run start [--mode human-gated|autonomous] --local-fallback MODEL -i ...
```

- `_split_mode` takes `--local-fallback` out of the start options (same rules as `--mode`: `--name value` or `--name=value`, not twice, a value after `-i` is an input value).
- Refused before any engine or agent starts, exit 2, nothing written:
  - with `--mode chat`: `--local-fallback is not available in Chat runs; the operator chooses in Chat`;
  - an invalid model: `--local-fallback needs a local model name such as qwen3:4b`;
  - a cloud tag: `--local-fallback refuses cloud model MODEL: content would leave this machine`;
  - `--local-fallback-endpoint` (any form) is not an option (DEC-0003). T026 adds no parser for it and T024 tests that start and resume refuse it with exit 2 and write nothing. The fallback always uses Ollama's default endpoint `http://127.0.0.1:11434` (DEC-0003).
- On success, before the engine starts, `fallback.json` is written to the new run's operator directory, and the model's current `/api/tags` digest is recorded in it (a second line says so when Ollama does not serve the model, and the fallback then refuses until the operator resumes with the flag again), and one line is printed: `Local fallback: on (ollama MODEL at 127.0.0.1:11434); turn it off with ballast run resume RUN --local-fallback off`.
- The flag only stores the setting. It probes nothing; the checks run when a fallback would be selected.

## Resume

```text
ballast run resume RUN --local-fallback MODEL|off
```

- Accepted for human-gated and Autonomous resumes next to their existing options; refused for a Chat run with the Chat message above.
- `off` writes `enabled: false`; a model replaces the setting. Same validation and messages as start. Printed: `Local fallback: on (...)` or `Local fallback: off`.
- Without the flag, the stored setting is kept.

## Visibility

- An Autonomous `record.md` "Mode and risk" section adds `- Local fallback: off` or `- Local fallback: on (ollama MODEL)`, and the run's fallback attempts appear as step entries in the existing sections.
- `ballast run status RUN` prints `Local fallback: off` or `Local fallback: on (ollama MODEL)` for a human-gated or Autonomous run whose operator directory holds `fallback.json`. Without that file its output is unchanged. This is the human-gated run's record of the setting (AC-020, plan-review F-004), together with `local_fallback: true` in each step's `meta.json` while the setting is on.
- Fallback evidence is read from the ledger report (`./scripts/agent-metrics --run RUN`), which lists `route` events with `route_source` counts.

## What agents cannot do

`fallback.json` lives under `$XDG_STATE_HOME`, which `state_dir` already refuses when it resolves inside the checkout or an agent temp root. Bubblewrap does not bind it, and Codex's sandbox does not make it writable. The wrapper reads it with `O_NOFOLLOW` and treats any invalid content as off. No environment variable or `ballast.toml` key enables the fallback.
