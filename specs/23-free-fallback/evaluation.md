# Evaluation: Qualify one zero-cost provider fallback

Evidence for [research.md](research.md) R10 and AC-018. Task T028 completes this file after the wrapper exists.

## Pilot

- **Run**: task T001, 2026-10-06, by the driving agent (claude/claude-opus-5-5) acting from the operator side: a host shell outside Ballast's confinement, not a confined agent step and not through `ballast run` (DEC-0002 option 1).
- **Context**: every probe ran from that host shell. Each ran in a scratch directory outside the feature worktree, written `$SCRATCH` below. The Codex runs used `CODEX_HOME=$SCRATCH/<probe>/home`, an empty directory. No Ollama sign-in and no cloud tag pull happened. Account, quota and credential details are redacted, and dates and times in captured messages are replaced with `<date>` and `<time>`.
- **Outcome**: **stop condition holds.** The `--oss` run can't reach the model on this host because Codex 0.155.1 refuses Ollama 0.6.8. A second problem contradicts research R6: no `--config` key can pin the base URL of Codex's built-in Ollama provider. Both are recorded as DEC-0003 in [decisions.md](decisions.md). T001 stays open.

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
