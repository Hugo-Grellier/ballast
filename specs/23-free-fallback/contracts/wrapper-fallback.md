# Contract: wrapper fallback (`agent.py` + `fallback.py`)

Implements FR-002 to FR-009 and AC-001 to AC-016. Decisions are in [research.md](../research.md) R2 to R9; states are in [data-model.md](../data-model.md#fallback-decision).

## Module boundary

`tools/spec_workflow/fallback.py`: standard library only, imported by `agent.py` and `run.py`, no top-level side effects. Public functions:

| Function | Contract |
| --- | --- |
| `read_setting(root, run_id) -> Setting \| None` | `None` when absent or off; raises `SettingError` when invalid (the wrapper prints it and treats it as off) |
| `write_setting(root, run_id, model \| None) -> Setting` | validates, writes 0600 through `autonomy` helpers; `None` model = off. There is no endpoint argument: the endpoint is the constant `OLLAMA_ENDPOINT` (`http://127.0.0.1:11434`, DEC-0003) |
| `validate_model(text)` | raises `SettingError` with the fixed messages in [operator-cli.md](operator-cli.md) |
| `classify(integration, exit_code, blocked, contained, tail, *, cli_found) -> str` | the normalized cause; pure |
| `RECOVERABLE` | `frozenset({"quota-exhausted", "provider-unavailable", "cli-unavailable"})` |
| `probe(setting, *, root, autonomous, codex, prompt, env) -> str \| None` | runs checks 5 to 11 and 11a of research R5 in order within one 10 s budget; `env` is the environment `fallback_env` built, and check 5 owns the endpoint-override refusal (`privacy-exclusion`), which therefore wins over `permission_mismatch` (plan-review PD-0013 F-001); requests only `OLLAMA_ENDPOINT`; returns the refusal reason or `None`; sends only the model name |
| `fallback_argv(codex, prompt, model) -> list[str]` | research R6: `permission_args("codex", ["exec", prompt])` plus `--oss`, `--local-provider ollama`, `-m MODEL`, `--json`; no `-c model_providers.ollama.*` or other base-URL key, which Codex refuses; never forwards primary extra arguments |
| `fallback_env(env, codex_home) -> dict` | `confined_env(env, None)` minus `OLLAMA_HOST`, `CODEX_OSS_BASE_URL`, `CODEX_OSS_PORT`, with `CODEX_HOME` set to the wrapper's private, empty directory (research R6) |
| `permission_mismatch(argv, env, codex_home, *, codex, prompt, model) -> bool` | exact allowlist: true unless `argv == fallback_argv(codex, prompt, model)` token for token and `env` holds only `confined_env` names plus `CODEX_HOME == codex_home` and none of `CODEX_OSS_BASE_URL`, `CODEX_OSS_PORT`, `OLLAMA_HOST`. No token list to keep current (plan-review F-002) |
| `state_evidence(root, feature) -> dict \| None` | research R3 pieces (tree, reviews, drafts, ignored, refs); `None` when any piece cannot be established |
| `codex_prompt(prompt) -> str` | `/speckit-x rest` → `$speckit-x rest`; a `$` prompt is unchanged |
| `parse_events(lines) -> Events` | agent message text, summed usage, `complete`; raises `EventError` when unparsable |
| `record(root, run_id, feature, events)` | appends `route` and `usage` events through `ledger.append` with the fixed event IDs |

HTTP: only `OLLAMA_ENDPOINT` (`http://127.0.0.1:11434`, the endpoint Codex's `--oss` uses with no override), `urllib.request.build_opener(ProxyHandler({}))`, 5 s timeout, `GET /api/version`, `GET /api/tags`, `POST /api/show`. Response bodies are capped at 1 MiB and parsed as JSON. Any error is the reason the check names.

## `agent.main` flow change

```text
real = _real_executable(integration)       # FileNotFoundError -> cause cli-unavailable
...
before = state_evidence(...) if setting on else None
exit_code, entry = _attempt(...)            # primary, unchanged
cause = fallback.classify(...)
if setting on and not chat and cause in RECOVERABLE and attempt == 1 and not refusals:
    reason = changed_state(before, state_evidence(...)) or fallback.probe(...) or permission check
    record primary route (fallback=selected|refused, reason)
    if reason: stderr "local fallback refused: ..."; append entry; return exit_code
    record = _autonomous_run(...)           # counts the step; Refusal -> existing limit path
    exit_code, entry = _attempt(..., fallback=setting)   # once
    record fallback route + usage
    if drafts refused: step fails (see below), no retry
    append entry; return exit_code
else:
    unchanged path (draft retries as today; a recoverable cause on a retry
    attempt is recorded as failure_cause but never falls back)
```

- The fallback is considered only on the step's first attempt. A draft-retry attempt never falls back, and a fallback is never followed by a draft retry, so a step that falls back makes exactly two attempts (SC-005, FR-006, DEC-0001).
- The fallback's `CODEX_HOME` is a fresh 0700 directory inside the attempt's private directory, removed after the attempt. Under bubblewrap it is the Codex home the confinement exposes. No user Codex configuration file is read (plan-review F-001), and a non-empty `~/.agents/skills` refuses the fallback (F-003).
- With the setting off, no new digest, probe, file or ledger event exists: the step behaves byte-for-byte as before (AC-003). Tests compare argv, `steps.jsonl` and ledger with and without the feature present.
- `_attempt` gains one keyword, `fallback: Setting | None`. When set, it uses `fallback_argv`/`fallback_env`, `integration="codex"`, `--json` parsing for `BLOCKING` and the terminal, the timeout of research R9, and writes `route`, `provider` and `model` into `meta.json` and the entry. Confinement, scope, subreaper, protected-state check, tamper marker and draft snapshotting are the same code path as a primary attempt.
- A fallback that exits 0 with a refused draft ends the step with `EXIT_LIMIT`, `limit: "retries"` and the reason `draft refused after the local fallback: <message>`, using the existing limit-condition wording. It is not retried.
- Exit codes are unchanged: success 0; a refused fallback returns the primary's code; a failed fallback returns its own code (`EXIT_BLOCKED`, `EXIT_TAMPERED`, `EXIT_LIMIT` or the CLI's).

## Refusal reasons (fixed)

| Reason | Checks |
| --- | --- |
| `changed-state` | tree, reviews, drafts, ignored paths or refs differ after the primary, or any of them cannot be checked |
| `privacy-exclusion` | an endpoint override variable (`CODEX_OSS_BASE_URL`, `CODEX_OSS_PORT`, `OLLAMA_HOST`) in the built environment; model entry remote or cloud |
| `unknown-free-status` | model not listed, or listed without size and digest |
| `incompatible-capability` | server not answering, or older than Ollama 0.13.4 or of unknown version; served context below 16384 or unknown (`num_ctx`, DEC-0004); codex missing or without `--oss`/`--local-provider`; the project's Codex skill for the step's Spec Kit command missing; Codex sandbox not starting under the step's confinement; the checks exceeding their 10 s budget |
| `permission-mismatch` | argv or env not exactly the one the wrapper builds (any added, removed or changed token); a Codex configuration layer outside the private `CODEX_HOME` exists or could not be established; the user skills directory `~/.agents/skills` is non-empty, a symlink or unreadable (plan-review F-003) |

## Review provenance

`artifacts.py`: for a step entry with `route: "fallback"`, the review entry's `cross_provider` is `false`, and the draft's `agent.provider` and `agent.model` are the entry's `provider` and `model`, not the agent-reported model. `draft_pr.py` and `packet.py` read these fields as they do today, so no PR text claims cross-provider review on the fallback's basis (AC-016).

A human-gated run has no step entries or recorder. There the wrapper's runner `route` event (`route_source: fallback`, the review command as `stage`) is the provenance, and `ledger.report` stops counting the run's reviews as cross-provider ([ledger.md](ledger.md#report)). Each step's `meta.json` also records `route`, `provider` and `model`.
