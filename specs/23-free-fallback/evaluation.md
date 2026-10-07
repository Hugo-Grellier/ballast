# Evaluation: Qualify one zero-cost provider fallback

Evidence for [research.md](research.md) R10 and AC-018. Task T028 completed this file after the wrapper existed; the workflow appends the quickstart pilot (steps 3 to 5) under [Workflow pilot](#workflow-pilot).

## Summary

- **Candidate**: the Codex CLI in local-provider mode, `codex exec --oss --local-provider ollama -m MODEL --json`, against the host's Ollama at its fixed default endpoint `127.0.0.1:11434` (DEC-0003), with a local model served with a context of at least 16384 tokens (DEC-0004).
- **Decision**: qualified, agent-provisional (Autonomous run `f200c320`; merging the PR is the only human approval). The model answered through the candidate on this host (item 10). Human-gated steps can use the fallback. Autonomous steps refuse it with `incompatible-capability`, because Codex's sandbox does not start inside Ballast's bubblewrap here (item 7, DEC-0004 of the run record).
- **Host versions**: `codex-cli 0.155.1`, Ollama 0.35.1 (0.6.8 before the operator's upgrade), Claude Code 2.1.290, bubblewrap 0.11.1, Spec Kit 1.0.11 (item 1 and item 9).

### Alternatives and why they were rejected

From research R1:

| Alternative | Rejected because |
| --- | --- |
| Claude Code pointed at Ollama's Anthropic-compatible endpoint (`ANTHROPIC_BASE_URL`) | Redirects a paid-provider CLI by environment, needs an auth variable `confined_env` removes on purpose, and its tool permission model would need a second qualification. |
| A hosted free tier (OpenRouter free models, Gemini CLI free tier, other hosted endpoints) | Remote and account-bound; free status and privacy terms cannot be established at run time; Issue #23 excludes account sign-up (D-03). |
| LM Studio through `--local-provider lmstudio` | Same path, additive later, but not installed on the operator host, so it could not be piloted. |
| Another agent CLI (aider, opencode) or a direct Ollama API harness | A new permission model to qualify, or the direct-API harness the spec lists as a non-goal. |

### What the pilot established for the wrapper

- **Sandbox nesting, both modes** (item 7, operator terminal): `codex_sandbox_nests` is `False` under Ballast's bubblewrap on this host (`kernel.apparmor_restrict_unprivileged_userns = 1`), and `codex sandbox … -- true` exits 0 without it. The wrapper runs the same probe before each fallback: `codex_sandbox_nests` for an Autonomous step, `codex_sandbox_starts` for a human-gated one.
- **Configuration layers and the empty `CODEX_HOME`** (items 4, 5, 9 and 10): Codex reads `/etc/codex/` (absent here), `$CODEX_HOME/config.toml` and profiles, a project `.codex/config.toml` only when the user configuration trusts the project, and `-c` overrides; skills also load from `~/.agents/skills`. Runs with an empty `CODEX_HOME` needed no login and reached the default endpoint. The wrapper therefore gives the fallback a fresh private `CODEX_HOME`, and refuses with `permission-mismatch` when `/etc/codex` holds anything, a project `.codex/config.toml` exists, or `~/.agents/skills` is not empty.
- **Codex Spec Kit skill path** (item 6): `.agents/skills/<command>/SKILL.md`. A project needs Spec Kit's Codex integration installed for a fallback to run; without the skill for the step's command the fallback refuses as `incompatible-capability` (`codex skill <command> is not installed`).
- **A raw `codex exec --json` run** (item 10, operator terminal, CPU only): `qwen3:4b-16k` answered `ok` after 322 s, exit 0; usage `input_tokens` 11905, `cached_input_tokens` 0, `output_tokens` 110. A run with an open stdin waited for input, so the wrapper closes stdin for the fallback attempt.
- **Signatures adopted** (item 8, research R2): `fallback.SIGNATURES` holds, per integration, the redacted quota and availability messages of item 8, matched only against the last 64 KiB of each output stream. Claude: `You've hit your (monthly spend) limit`, `usage limit reached`, `Credit balance is too low`, `Request rejected (429)` for quota; `API Error: 5xx`, `Connection error.`, `Request timed out`, `Unable to connect to API`, `overloaded_error` for availability. Codex: `You’ve hit your usage limit` (either apostrophe), `Quota exceeded. Check your plan`, `usage_limit_reached` for quota; `unexpected status 5xx`, `stream disconnected before completion`, `exceeded retry limit, last status`, `Connection failed:` for availability. No cause is left without a signature for either integration; any other failure is `unrecognized` and never falls back. The Claude subscription quota message could not be captured without a real account; its signature comes from the CLI's own strings.
- **Expected Autonomous refusal**: on this host every Autonomous fallback refuses with `incompatible-capability: codex sandbox does not start`, as DEC-0004 of the run record predicts. No sandbox is loosened to make it run (FR-005).

## Workflow pilot

Quickstart steps 3 to 5 need `ballast run`, which does not run from the feature worktree. The operator-side equivalent ran the real wrapper in a scratch human-gated run with a stand-in primary that prints the quota message, the real probes, the real Codex 0.155.1 and Ollama 0.35.1 with `qwen3:4b-16k`: every refusal reason that can be produced on this host refused with nothing sent, the setting off changed nothing, and a real fallback step completed in 210 s to 546 s with `route` and `usage` events in the ledger. The details, the Autonomous step that was not run live and the start-up egress finding (Codex contacts `github.com` and `chatgpt.com` itself; the fallback environment now blackholes it) are in [reviews/live-check.md](reviews/live-check.md). The operator's `ballast run start --local-fallback` pilot (quickstart steps 3 to 5, and `--mode autonomous` for the expected `incompatible-capability` refusal) remains for the operator to run before merge.

## Pilot

- **Run**: task T001, 2026-10-06, by the driving agent (claude/claude-opus-5-5) acting from the operator side: a host shell outside Ballast's confinement, not a confined agent step and not through `ballast run` (DEC-0002 option 1).
- **Context**: every probe ran from that host shell. Each ran in a scratch directory outside the feature worktree, written `$SCRATCH` below. The Codex runs used `CODEX_HOME=$SCRATCH/<probe>/home`, an empty directory. No Ollama sign-in and no cloud tag pull happened. Account, quota and credential details are redacted, and dates and times in captured messages are replaced with `<date>` and `<time>`.
- **Outcome**: resolved by item 10 (the history below is kept as recorded). First run: **stop condition holds.** The `--oss` run can't reach the model on this host because Codex 0.155.1 refuses Ollama 0.6.8. A second problem contradicts research R6: no `--config` key can pin the base URL of Codex's built-in Ollama provider. Both are recorded as DEC-0003 in [decisions.md](decisions.md). T001 stays open. **Update, 2026-10-06 (item 9)**: after the Ollama 0.35.1 upgrade the version gate passes, but a trivial `--oss` run still fails because the host serves `qwen3:4b` with a 4096-token context, below Codex's roughly 7.7k-token prompt. T001 stays open (DEC-0004).

### 1. Versions and help

| Command | Outcome |
| --- | --- |
| `codex --version` | `codex-cli 0.155.1` (standalone musl build; `codex doctor` reports 0.160.1 available) |
| `codex exec --help` | lists `--oss` ("Use open-source provider"), `--local-provider <OSS_PROVIDER>` ("lmstudio or ollama") and `--json` ("Print events to stdout as JSONL"). Also lists `--ignore-user-config` ("Do not load `$CODEX_HOME/config.toml`; auth still uses `CODEX_HOME`"), `--ignore-rules`, `--ephemeral`, `--strict-config`, `-p/--profile` ("Layer `$CODEX_HOME/<name>.config.toml` on top of the base user config"), `--enable/--disable <FEATURE>` (equivalent to `-c features.<name>=…`), `--approve-for-me`, `--dangerously-bypass-hook-trust` and `--worktree`. The permission comparison (R6) must treat each of these as outside the canonical profile. |
| `ollama --version` | `ollama version is 0.6.8` |
| `claude --version` | `2.1.290 (Claude Code)` |
| `bwrap --version` | `bubblewrap 0.11.1` |
| `specify --version` | `specify 1.0.11` |

### 2. Base URL pinning

| Command (in `$SCRATCH/keyprobe/proj`, a loopback stub recording requests on port 18555) | Outcome |
| --- | --- |
| `codex exec --oss --local-provider ollama -m qwen3:4b --json --skip-git-repo-check -c 'model_providers.ollama.base_url="http://127.0.0.1:18555/v1"' …` | exit 1: `Error loading config.toml: model_providers contains reserved built-in provider IDs: `ollama`. Built-in providers cannot be overridden. Rename your custom provider (for example, `openai-custom`).` The stub saw nothing. |
| same with `-c 'oss_base_url="…"'` | the key is ignored. Codex contacted the default `127.0.0.1:11434`, and the stub saw nothing (see item 4 for the error). |
| same with environment `CODEX_OSS_BASE_URL=http://127.0.0.1:18555/v1` | the stub saw `GET /v1/models`. Codex reported `Error: OSS setup failed: No running Ollama server detected. Start it with: `ollama serve` …` because the stub answers 503. |
| same with environment `CODEX_OSS_PORT=18555` | the stub saw `GET /v1/models`, with the same error. |
| `strings` on the Codex binary | only `CODEX_OSS_BASE_URL` and `CODEX_OSS_PORT` name an OSS endpoint, plus the config key `oss_provider`, which selects the provider. |

**Result**: Codex 0.155.1 has no `--config` key that sets the base URL of the built-in `ollama` provider. The only overrides are the environment variables `CODEX_OSS_BASE_URL` and `CODEX_OSS_PORT`, which research R6 removes and the permission comparison forbids. A custom provider (`-c model_provider=NAME -c 'model_providers.NAME={…base_url=…}'`, without `--oss`) does accept a `--config` base URL, as item 4's stub runs show. That is a different invocation from the one R1 and R6 describe. → DEC-0003.

### 3. Ollama API fields

| Command | Outcome |
| --- | --- |
| `curl --noproxy '*' http://127.0.0.1:11434/api/version` | `{"version":"0.6.8"}` |
| `curl … /api/tags` | one local model: `name` and `model` `qwen3:4b`, `size` 2620788019, `digest` `a383baf4…d45378`, `details` (`format` gguf, `family` qwen3, `parameter_size` 4.0B, `quantization_level` Q4_K_M). No `remote_model` or `remote_host`. |
| `curl … /api/show -d '{"model":"qwen3:4b"}'` | keys `capabilities` (`completion`, `tools`), `details`, `license`, `model_info`, `modelfile`, `modified_at`, `parameters`, `template`, `tensors`. **No `size` or `digest`**, and no `remote_model` or `remote_host`. |
| cloud tag | none pulled, and none can be on this host: Ollama 0.6.8 predates cloud models. From Ollama's source (`api/types.go` on `main`): `ListModelResponse` and `ShowResponse` carry `remote_model` and `remote_host` (`json:",omitempty"`), so both fields are absent for a local model. From the Ollama cloud documentation (docs.ollama.com/cloud): cloud models use a `cloud` tag (`gemma4:cloud`; size-qualified tags end in `-cloud`) and need an Ollama sign-in. |

**Result**: R5 checks 7 and 8 hold as designed. Size and digest come from the `/api/tags` entry (`/api/show` has neither). A cloud model is recognised by a non-empty `remote_model` or `remote_host` in either response, or by a `cloud` tag in the name. These fields could not be observed on a cloud tag on this host.

### 4. `codex exec --json` event shape and login

| Command | Outcome |
| --- | --- |
| `CODEX_HOME=$SCRATCH/keyprobe/home codex exec --oss --local-provider ollama -m qwen3:4b --json --skip-git-repo-check "Reply with the single word OK."` (in a scratch Git repository) | exit 1 before any model request: `Error: OSS setup failed: Ollama 0.6.8 is too old. Codex requires Ollama 0.13.4 or newer.` No JSON event was printed. No login was asked for before this check. Whether `--oss` needs a login later stays unproven. **The model never answered through the candidate.** → DEC-0003. |
| `CODEX_HOME=$SCRATCH/jsonprobe/home codex exec --json --skip-git-repo-check -c model_provider=loopstub -c 'model_providers.loopstub={name="loopstub",base_url="http://127.0.0.1:18556/v1",wire_api="responses",request_max_retries=0,stream_max_retries=0}' -m qwen3:4b "Reply with the single word OK." < /dev/null` against a loopback stub that streams one Responses API answer | exit 0. The event lines follow (thread ID shortened). |
| the same against a loopback stub that answers 503 | exit 1. The events are `thread.started`, the same `item.completed` warning, `turn.started`, `{"type":"error","message":"unexpected status 503 Service Unavailable: Unknown error, url: http://127.0.0.1:18555/v1/responses"}` and `{"type":"turn.failed","error":{"message":"unexpected status 503 Service Unavailable: …"}}`. Without `< /dev/null`, stderr shows `Reading additional input from stdin...`. |

```jsonl
{"type":"thread.started","thread_id":"01a110fe-…"}
{"type":"item.completed","item":{"id":"item_0","type":"error","message":"Model metadata for `qwen3:4b` not found. Defaulting to fallback metadata; this can degrade performance and cause issues."}}
{"type":"turn.started"}
{"type":"item.completed","item":{"id":"item_1","type":"agent_message","text":"OK"}}
{"type":"turn.completed","usage":{"input_tokens":100,"cached_input_tokens":10,"cache_write_input_tokens":0,"output_tokens":2,"reasoning_output_tokens":0}}
```

**Result** (Codex's own `--json` writer, fed by a stub rather than the model): the R7 shape holds. `agent_message` text sits in `item.completed.item.text`. `turn.completed.usage` has `input_tokens`, `cached_input_tokens`, `cache_write_input_tokens`, `output_tokens` and `reasoning_output_tokens`. A run that succeeds can still emit an `item.completed` with `item.type` `error` (a non-fatal warning), so the parser must not treat it as a failure. In `--json` mode, request failures are printed on stdout as `error` and `turn.failed` events, not on stderr. Every run printed `WARNING: proceeding, even though we could not create PATH aliases: Refusing to create helper binaries under temporary dir "/tmp" …` on stderr when `CODEX_HOME` was under `/tmp`. Codex also wrote system skills into the "empty" `CODEX_HOME` (`skills/.system`).

### 5. Codex configuration layers

| Command | Outcome |
| --- | --- |
| `strings` on the Codex binary | system paths `/etc/codex/config.toml`, `/etc/codex/requirements.toml` and `/etc/codex/managed_config.toml`. Also `legacy_managed_config_file` and `legacy_managed_config_mdm`, and `codex doctor` reports "configuration scope: invocation config, including cloud-managed policy" (a policy fetched for a signed-in account). |
| `ls -la /etc/codex` | absent on this host |
| `CODEX_HOME=$SCRATCH/layers/home codex doctor` in a scratch Git project holding `.codex/config.toml` (`model = "layer-probe-project"`) | `config.toml: $SCRATCH/layers/home/config.toml` (missing), `model: <default>`, `MCP servers: 0`, `auth mode: none`. The project layer was **not** read. |
| the same with `CODEX_HOME=$SCRATCH/layers/home2`, whose `config.toml` marks the scratch project `trust_level = "trusted"` | `model: layer-probe-project`. The project layer is read only for a project the user configuration trusts. |
| `CODEX_HOME=$SCRATCH/skillhome codex debug prompt-input '$speckit-plan hello'` (item 6) | the skill roots include the user directory `~/.agents/skills` (outside `CODEX_HOME`) as well as `$CODEX_HOME/skills/.system` and the project's `.agents/skills`. |

**Result**: Codex 0.155.1 reads these layers:

- the system files under `/etc/codex/` (`config.toml`, `requirements.toml`, `managed_config.toml`), absent here;
- the cloud-managed policy, which needs a sign-in and so stays absent with an empty `CODEX_HOME`;
- `$CODEX_HOME/config.toml`, plus `$CODEX_HOME/<name>.config.toml` with `--profile`;
- the project `.codex/config.toml`, only when the user configuration trusts the project, so never with an empty private `CODEX_HOME`;
- the `-c` overrides.

Instructions and skills also load from outside `CODEX_HOME`: `~/.agents/skills` and the project's `AGENTS.md` and `.agents/skills`. Under Ballast's bubblewrap, the agent-home overlay decides what `~/.agents/skills` holds. R5 check 11 can therefore refuse when any of the three `/etc/codex/` files exists.

### 6. Codex Spec Kit skill path

| Command | Outcome |
| --- | --- |
| `specify init --here --force --non-interactive --integration codex --ignore-agent-tools` in `$SCRATCH/skillproj` | installs `.agents/skills/speckit-<command>/SKILL.md` for analyze, checklist, clarify, constitution, converge, implement, plan, specify, tasks and taskstoissues |
| `CODEX_HOME=$SCRATCH/skillhome codex debug prompt-input '$speckit-plan hello'` | the developer message lists `speckit-plan: Execute the implementation planning workflow … (file: r2/speckit-plan/SKILL.md)` with the skill root `r2` = `$SCRATCH/skillproj/.agents/skills`, and the user message is `$speckit-plan hello` |

**Result**: Codex finds a project's Spec Kit skill at `.agents/skills/<command>/SKILL.md` (R5 check 9 confirmed). This was shown without a model run, by rendering the prompt input.

### 7. Sandbox nesting

| Command | Outcome |
| --- | --- |
| `python3 -I -S -c 'import autonomy; autonomy.codex_sandbox_nests(Path("$SCRATCH/nest"))'` (module from this worktree, run on a scratch Git repository) | `False`. Replaying the same argv showed exit 1 with `bwrap: No permissions to create a new namespace, likely because the kernel does not allow non-privileged user namespaces.` from the bwrap Codex starts inside Ballast's bwrap. The outer `bwrap --ro-bind / / --dev /dev true` succeeds from the host shell. `kernel.apparmor_restrict_unprivileged_userns = 1`. |
| `codex sandbox -c 'sandbox_mode="workspace-write"' -c 'sandbox_workspace_write.network_access=false' -- true` (no bubblewrap) | exit 0 |

**Result**: as research R10 expected (DEC-0004 of [record.md](autonomous/record.md)). An Autonomous step would refuse the fallback with `incompatible-capability`, and a human-gated step passes check 10.

### 8. Quota and availability signatures

| Integration | Cause | Message (redacted) | Source |
| --- | --- | --- | --- |
| codex | quota-exhausted | `ERROR: You’ve hit your usage limit. Upgrade to Pro (https://chatgpt.com/explore/pro), visit https://chatgpt.com/codex/settings/usage to purchase more credits or try again at <date> <time>.` (stderr, exit 1; note the typographic apostrophe U+2019) | earlier run log: `stderr.log` of a human-gated `speckit-ballast-discover` Codex step in a scratch pilot project, 2026-10-05 |
| codex | quota-exhausted | `You’ve hit your usage limit.` variants (`… Upgrade to Plus to continue using Codex …`, `… To get more access now, send a request to your admin …`), `Quota exceeded. Check your plan and billing details.`, error code `usage_limit_reached` | Codex 0.155.1 binary strings |
| codex | provider-unavailable | `unexpected status 503 Service Unavailable: Unknown error, url: <url>` (`error` and `turn.failed` events on stdout in `--json` mode) | captured: item 4's stub run |
| codex | provider-unavailable | `stream disconnected before completion`, `exceeded retry limit, last status: <status>`, `Connection failed: …` | Codex 0.155.1 binary strings |
| claude | quota-exhausted | `You've hit your limit` (ASCII apostrophe; the client composes the line, followed by the reset time), `You've hit your monthly spend limit`, `usage limit reached`, `Credit balance is too low` | Claude Code 2.1.290 binary strings. Not captured: a loopback stub that returned 429 with the unified rate-limit headers, under a dummy API key and an empty `CLAUDE_CONFIG_DIR`, produced only `API Error: Request rejected (429) · rate limited` (stdout, exit 1). The subscription message is not reachable without a real account. |
| claude | provider-unavailable | `API Error: 503 status code (no body). This is a server-side issue, usually temporary — try again in a moment. If it persists, check your inference gateway (<host:port>).` (stdout, exit 1) | captured: `claude -p "Reply OK."` with `ANTHROPIC_BASE_URL` set to a loopback 503 stub, a dummy API key, `CLAUDE_CONFIG_DIR` empty and `CLAUDE_CODE_MAX_RETRIES=0` |
| claude | provider-unavailable | `Connection error.`, `Request timed out`, `Unable to connect to API: …`, `overloaded_error` | Claude Code 2.1.290 binary strings |

The earlier logs searched were the wrapper's `stdout.log` and `stderr.log` files under `.specify/workflow-state/` in the operator's local checkouts (85 non-empty files), plus Ballast's operator state. They held one real quota message (Codex, above). Claude printed both captured messages on stdout, not stderr. No cause lacks a signature for either integration.

### 9. Rerun on Ollama 0.35.1 (2026-10-06, operator host, outside confinement)

Context: the operator upgraded Ollama after DEC-0003. Every probe ran from the host shell in `$SCRATCH` (a scratch directory under the session scratchpad, holding an empty `CODEX_HOME` and a scratch Git repository). No Ollama sign-in, no cloud pull. The Ollama server's own settings were not read or changed.

| Command | Outcome |
| --- | --- |
| `ollama --version` | `ollama version is 0.35.1` |
| `curl --noproxy '*' http://127.0.0.1:11434/api/version` | `{"version":"0.35.1"}` |
| `curl … /api/tags` | one local model, `qwen3:4b`: `size` 2620788019, `digest` `a383baf4…d45378`, `details.context_length` 40960, `capabilities` `tools`, `thinking`, `completion`. No `remote_model` or `remote_host`. |
| `curl … /api/show -d '{"model":"qwen3:4b"}'` | keys `capabilities`, `details`, `license`, `model_info`, `modelfile`, `modified_at`, `parameters`, `template`. `remote_host`, `remote_model`, `size` and `digest` are all absent, as on 0.6.8. A cloud tag could not be observed (none pulled). The recognition rule of item 3 stands: non-empty `remote_model` or `remote_host`, or a `cloud` tag. |
| `CODEX_HOME=$SCRATCH/home codex exec --oss --local-provider ollama -m qwen3:4b --json --skip-git-repo-check "Reply with the word ok" < /dev/null` (no base-URL override, no environment override) | exit 1 after 15 s. The version check now passes and Codex reaches the default `127.0.0.1:11434` without any login or sign-in. Events: `thread.started`, the same `item.completed` of type `error` ("Model metadata for `qwen3:4b` not found…"), `turn.started`, five `error` events `Reconnecting... N/5 (stream disconnected before completion: …)`, a final `error`, then `turn.failed`. Every error carries the server's `exceed_context_size_error` (HTTP 400): `request (7684 tokens) exceeds the available context size (4096 tokens)` (`n_prompt_tokens` 7684, `n_ctx` 4096). No `agent_message` and no `turn.completed` were emitted. |

**Result**: the Ollama version gate is cleared and `--oss` needs no login (the run reached the model server on the default endpoint, with an empty `CODEX_HOME`). The default endpoint works with no override. The model still **cannot answer**: Codex's own instructions for even a trivial prompt are about 7.7k tokens, and Ollama served `qwen3:4b` with a 4096-token context, so the server rejects every request. The `--json` shape of a successful `--oss` run therefore stays unobserved (the stub-fed shape of item 4 is the only evidence). Stop condition: model cannot answer. → DEC-0004.

### 10. `qwen3:4b-16k`, a 16k-context local variant (2026-10-06, operator host, outside confinement)

Context: the operator created a local variant with `ollama create` (`FROM qwen3:4b`, `PARAMETER num_ctx 16384`) on Ollama 0.35.1, CPU only. Probes ran from the host shell in a scratch directory with an empty `CODEX_HOME`. No login, no sign-in.

| Command | Outcome |
| --- | --- |
| `curl --noproxy '*' … /api/show -d '{"model":"qwen3:4b-16k"}'` | `parameters` text holds `num_ctx 16384` (plus `temperature 0.6`, `top_k 20`, `top_p 0.95`, `repeat_penalty 1` and two `stop` lines). `model_info` has `qwen3.context_length` 40960, the model's maximum, not the served context. `capabilities`: `tools`, `thinking`, `completion`. An R5 check reads `num_ctx` from `parameters`. |
| `CODEX_HOME=$SCRATCH/home codex exec --oss --local-provider ollama -m qwen3:4b-16k --skip-git-repo-check --json "Reply with the word ok" < /dev/null` | exit 0 after 322 s (CPU). Events, in order: `thread.started`; `item.completed` of type `error` ("Model metadata for `qwen3:4b-16k` not found. Defaulting to fallback metadata…", benign); `turn.started`; `item.completed` of type `reasoning`; `item.completed` of type `agent_message` with text `ok`; `turn.completed`. Usage: `input_tokens` 11905, `cached_input_tokens` 0, `cache_write_input_tokens` 0, `output_tokens` 110, `reasoning_output_tokens` 0. No login was required. |

Notes: a first attempt without `< /dev/null` printed "Reading additional input from stdin..." and produced no event within 900 s; the wrapper must close stdin (`stdin=DEVNULL`) for the fallback run. A trivial prompt needs about 11.9k input tokens, so 16384 is enough for it but leaves little room for a real step's prompt; the minimum in R5 check 11a is a floor, not a promise that a step fits. Codex also warned it could not create PATH helper aliases under a `/tmp` Codex home, which did not affect the run.

**Result**: the model answers through the candidate, so T001's stop rule no longer applies. DEC-0004 is resolved by option 1, adapted (a local variant with `num_ctx` at least 16384, plus an R5 check on the served context).
