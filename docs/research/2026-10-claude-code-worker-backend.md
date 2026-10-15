# Claude Code as a verified Ballast worker backend

Investigation for [#204](https://github.com/Hugo-Grellier/ballast/issues/204), run on 2026-10-15 against the installed Claude Code 2.1.300 on Linux, on subscription access. Risk R0: this note documents behavior and changes no tool, sandbox or permission.

## Questions

1. Can a headless Claude Code session start with an explicit model and effort, and does it report the resolved model and effort before task input?
2. Which arguments give an implementation worker workspace-only writes and a review worker read-only access, without granting more than the caller has?
3. How are the terminal turn, interrupts, token usage and quota errors observed?

The bar is what `tools/worker.py` verifies for Codex before task input: model, effort, provider, sandbox type, approval policy, cwd, network access and writable roots, all read from the `thread/start` receipt. [Model routing](../model-routing.md) also requires that a value that "cannot be observed" blocks the worker.

## Method

- **Client surface.** `claude --version` and `claude --help`, plus the official pages for headless use, the Agent SDK TypeScript reference (message and control types), sandboxing and model configuration.
- **Probes.** Three headless sessions, each run in its own empty temporary directory with `--input-format stream-json --output-format stream-json --verbose --no-session-persistence --safe-mode --permission-prompts none`. Each sent the `initialize` control request first, then one user message, `Reply with OK`, and contained no task content. The environment was rebuilt from an allowlist (home, path and the client config directory), so neither an API key nor a parent-session variable reached the child. `ANTHROPIC_API_KEY` was unset, and no settings file defines an API key or an `apiKeyHelper`. Every probe confirmed subscription access: `apiKeySource: "none"` in `system/init`, and `subscriptionType` set in the `initialize` response. Probe 1 still picked up a base URL from the user settings (see finding 2). The sandbox came from `--settings` (`enabled`, `failIfUnavailable`, `allowUnsandboxedCommands: false`). The probe script, raw output and debug logs stayed outside the repository. This note quotes only field names and values that matter for routing.

| Probe | Model | Effort | Permission mode | Extra arguments | Model request |
| --- | --- | --- | --- | --- | --- |
| 1 | `sonnet` (alias) | `low` | `dontAsk` | none | yes, one turn |
| 2 | `claude-opus-5-5` | `medium` | `acceptEdits` | `--restricted --tools Read,Edit,Write,Glob,Grep,Bash`, `/effort status` first, then an interrupt | none |
| 3 | `claude-opus-4-6` | `xhigh` | `dontAsk` | `--restricted --tools Read,Glob,Grep`, `/effort status` first, then an interrupt | none |

Probe 3 asks for a level that the catalog lists as unsupported for that model.

## Findings

### 1. Model is verifiable; effort is not

**Setting.** `--model` takes an alias or a full model name. `--effort` takes `low`, `medium`, `high`, `xhigh` or `max`. The documented precedence is:

1. For effort, an explicit choice: `CLAUDE_CODE_EFFORT_LEVEL`, `--effort` or `/effort`. The docs list these together without ranking them against each other.
2. The settings `modelSettings.<model>.effortLevel` or `effortLevel`.
3. The model default.

For the model, `--model` beats `ANTHROPIC_MODEL`, which beats the settings `model` key.

**Capability catalog, before task input.** The `initialize` control response lists `models[]` with `value`, `resolvedModel` and `supportedEffortLevels`, and an `account` object whose `subscriptionType` is set on subscription access. Its role matches Codex `model/list`: probe 1 returned it before any user message, so a launcher can reject an unsupported model and effort pair, or a missing subscription, before the session sees any work.

**Session receipt.** `system/init` is emitted only once the first user message arrives, not at startup: probe 1 received nothing but the control response before it sent `Reply with OK`. A local slash command also triggers it without a model request. In probes 2 and 3, `/effort status` produced `system/init` and a synthetic reply (`model: "<synthetic>"`, `total_cost_usd: 0`, empty `modelUsage`) before any task text. The receipt carries:

- `model`: the resolved full ID (`sonnet` was reported as `claude-sonnet-5-5`, and full names came back unchanged);
- `permissionMode`, `cwd` (the probe directory in every probe) and `tools` (exactly the `--tools` list when one is given);
- `apiKeySource: "none"` on subscription access, `claude_code_version` and `session_id`;
- `capabilities`, including `interrupt_receipt_v1` and `interrupt_cancel_queued_v1`.

**Effort is not reported.** In all three probes, `system/init` carried `effort: null`. The SDK reference explains why: Claude Code fills that field only for Remote Control clients and omits it from the init message an application reads. There is no fallback source:

- `/effort status` echoes the selected level, not the applied one. Probe 3 reported `Current effort level: xhigh` for `claude-opus-4-6`, whose catalog entry lists only `low`, `medium`, `high` and `max`. The model configuration page states that an unsupported level silently "falls back to the highest supported level at or below the one you set", so the session actually ran at `high`.
- A managed `maxEffortLevel` also silently caps `--effort` ("naming a higher level with `--effort` … runs at the cap instead").
- The undocumented init field `per_turn_effort_active` was `true` in probe 2 and `false` in probe 3. It is not a level and has no documented meaning, so it cannot be used.
- No effort value appears in the debug log, in assistant messages, or in the result's `usage` and `modelUsage`.

Checking the catalog before launch removes the unsupported-level fallback, but not a managed cap, and Ballast still cannot observe the applied level. By the routing contract, effort is unverified and the worker is blocked.

**Model drift after launch.** A `--fallback-model` chain, or a `fallbackModel` setting, switches models for one turn after an availability error and only shows a notice. Each assistant `message.model` and the keys of the result's `modelUsage` show the model that actually answered. A settlement check would require `modelUsage` to contain only the requested model, and a launcher must never pass `--fallback-model`.

### 2. Sandbox and permissions

Claude Code has two layers. Permission rules and modes decide whether a tool call runs. The OS sandbox (bubblewrap and socat on Linux) confines only the shell commands that Bash, PowerShell and Monitor run. The file tools (Read, Edit and Write) follow permission rules, not the sandbox. Hooks, MCP servers and helper commands run outside the sandbox with the user's full access.

| Codex receipt field | Claude Code equivalent | In the receipt before task input |
| --- | --- | --- |
| `model` | `system/init.model` | Yes |
| `reasoningEffort` | none | **No** |
| `modelProvider: openai` | `apiKeySource: "none"` plus `account.subscriptionType`; `modelUsage.*.provider: "firstParty"` only after a model request | Partly |
| `approvalPolicy: never` | `--permission-prompts none` plus `permissionMode` (`dontAsk` or `acceptEdits`) | Yes (`permissionMode`) |
| `cwd` | `system/init.cwd` | Yes |
| `sandbox.type` | `sandbox.enabled` with `failIfUnavailable: true`: startup fails closed if the sandbox cannot start | No; configured, not reported |
| `networkAccess: false` | Sandbox network with no allowed domains and `strictAllowlist: true`; WebFetch and WebSearch removed with `--tools` | No; configured, not reported |
| `writableRoots: []`, tmp excluded | Sandboxed shell writes go to cwd, a per-user temp directory, and the shared `.git` of a linked worktree (except `hooks` and `config`). File-tool writes are confined to the working directories by `--restricted` | No, and tmp is writable by default |
| `ephemeral: true` | `--no-session-persistence` | Not applicable |

Arguments that keep a worker within its caller's authority:

- **`--restricted`** ignores user, project and local settings files, removes the code-running tools unless `--tools` names them, confines the file tools to the working directories, and refuses `bypassPermissions`. Probe 1 ran without it, and its debug log showed the user settings `env` block re-injecting variables that the launcher had scrubbed, including a base URL. Probes 2 and 3 ran with it, and their logs reported `settingsEnv keys: none` and that user-settings permission rules were ignored. Without `--restricted`, a user setting such as `permissions.defaultMode: auto`, a pinned `model`, per-model effort or broad allow rules would leak into the worker. Managed settings and `--settings` still apply. `--strict-mcp-config` also drops MCP servers.
- **`--tools`** fixes the tool set exactly, as each probe's `system/init.tools` showed. Omitting `Task`/`Agent`, `SendMessage`, `Workflow`, the cron tools, `WebFetch` and `WebSearch` enforces "no spawned agents, no network" as configuration rather than a prompt request.
- **`--bare`** is not usable. It accepts only `ANTHROPIC_API_KEY` or an `apiKeyHelper`, never subscription OAuth, so it would need the paid API fallback that #204 rules out.
- **Never:** `--dangerously-skip-permissions`, `--allow-dangerously-skip-permissions`, or the `bypassPermissions` or `auto` permission modes.
- **Environment.** The launcher must build the child environment from an allowlist, as the probes did. A coordinating Claude session exports an effort variable, a gateway base URL and OAuth token variables into its children. `CLAUDE_CODE_EFFORT_LEVEL`, `ANTHROPIC_MODEL`, `ANTHROPIC_DEFAULT_*_MODEL`, `ANTHROPIC_API_KEY` and `ANTHROPIC_BASE_URL` would each override or redirect the route.

Proposed roles:

- **Review (read-only):** `--restricted --strict-mcp-config --tools Read,Glob,Grep --permission-mode dontAsk --permission-prompts none`. With no shell and no write tool, this is strictly read-only. It is narrower than the Codex read-only sandbox, which still lets a reviewer run read-only commands such as tests. A reviewer that needs Bash would rely on `sandbox.filesystem.denyWrite` on the checkout, and this investigation did not test that.
- **Implementation (workspace write):** `--restricted --strict-mcp-config --tools Read,Edit,Write,Glob,Grep,Bash --permission-mode acceptEdits --permission-prompts none --settings '{"sandbox":{"enabled":true,"failIfUnavailable":true,"allowUnsandboxedCommands":false,"network":{"allowedDomains":[],"strictAllowlist":true}}}'`. Sandboxed Bash runs without prompts (`autoAllowBashIfSandboxed` defaults to true). Anything that would prompt is denied and reported in `permission_denials`. Two differences from Codex remain: the per-user temp directory is writable, and a linked worktree's shared `.git` is writable.

The sandbox state is not in any receipt. Ballast can only verify its own launch configuration and rely on the fail-closed startup. This is a second, smaller gap next to effort.

### 3. Terminal state, interrupts, usage and quota

- **Terminal turn.** The last message of a turn is `type: "result"` with:
  - `subtype`: `success` or an `error_*` value;
  - `is_error`, `terminal_reason`, `stop_reason` and `num_turns`;
  - `permission_denials`, which the docs call authoritative.

  Probe 1 ended with `success`, `terminal_reason: "completed"` and exit code 0. The process exits non-zero on failure. SIGTERM exits with code 143 and records no result for the interrupted turn, so Ballast must treat a missing `result` as unknown, which matches its rule that settlement needs terminal evidence. `-p` also waits for background work it started, up to a default 10-minute idle cap, so the existing survivor check still applies.
- **Interrupt.** In stream-json input mode, send a `control_request` with `subtype: "interrupt"`. With `interrupt_receipt_v1` advertised, probes 2 and 3 got a `control_response` (`still_queued: []`) before a result with `subtype: "error_during_execution"`, `terminal_reason: "aborted_streaming"`, `is_error: true` and exit code 1. Ballast's mapping carries over: the outcome is cancelled only when Ballast requested the interrupt and the matching result reports an aborted `terminal_reason`.
- **Token usage.** The result carries:
  - `usage`: input, output, cache-read and cache-creation tokens, plus `output_tokens_details.thinking_tokens`;
  - `modelUsage`, keyed by model: token counts, `costUSD`, `provider` and `costBasis: "list"`;
  - `total_cost_usd`.

  The cost is a list-price estimate, which on a subscription stands for quota rather than money. Assistant messages also carry per-request `usage`. Probe 1 spent about 11,200 cache-creation tokens and 4 output tokens on a one-word reply, which is the fixed startup cost of a fresh worker session.
- **Quota.** A `rate_limit_event` arrives during the turn.
  - Documented fields: `status` (`allowed`, `allowed_warning` or `rejected`), `resetsAt` and `utilization`. A subscription with exhausted usage reports `errorCode: "credits_required"`.
  - Also observed, though undocumented: `rateLimitType` (`five_hour`), the overage fields, and `unifiedWindows.{five_hour,seven_day}.{utilization,resetsAt}`.
  - Retryable failures emit `system/api_retry` with `error: "rate_limit"`, and a fatal API error ends with `terminal_reason: "api_error"` and `api_error_status`.

  These map onto Ballast's quota pause:
  - `status: "rejected"` pauses the work, with the backend's `resetsAt` as the retry window, as Codex's exhausted-window `resetsAt` does today;
  - `credits_required` stops the work and never purchases capacity.

  The exhaustion path was not observed live.

## Verdict

Claude Code can run as a headless worker with an explicit model and effort, on subscription access, and with:

- a model and permission receipt before task input, at no model cost;
- a tool set fixed by configuration;
- correlated terminal, interrupt, usage and quota signals.

It cannot report the effort it actually applies. `system/init.effort` is null for SDK clients, `/effort status` echoes a level the model does not support, and unsupported or capped levels change silently. Under [model routing](../model-routing.md) step 4 and the `AGENTS.md` invariant ("a mismatch or missing observation blocks it"), a Claude Code worker is **blocked as unverified today**. That is the capability gap, and it is upstream: Ballast cannot close it by configuration.

Options:

1. **Wait for the client (recommended).** Ask upstream to fill `system/init.effort` for stream-json and SDK clients with the applied level, after fallback and caps. The field already exists in the type. Probe 3's sequence (`initialize`, then `/effort status`, then an interrupt) costs no model request, so rerunning it after each client upgrade detects when the gap closes.
2. **Accept a weaker evidence class by ADR.** For example, "effort selected, catalog-supported and echoed, not observed", recorded as unverified, for review workers only. That changes the routing contract and the `AGENTS.md` invariant, so it needs an explicit operator decision. This note does not recommend it: the probes show that the echo can be wrong.

## Proposed ADR outline (for when the gap closes)

**ADR-0026: Claude Code as a second standalone worker backend.**

- **Context.** Review on another provider (model routing). Codex is the only verified backend. This note's evidence.
- **Decision.**
  - Transport: `claude -p` with stream-json in both directions, launched by a stdlib helper under `python3 -I -S`. No Agent SDK package, which would be a non-stdlib dependency.
  - Environment: an allowlist.
  - Arguments: fixed per role, as above.
  - Preflight, all before task input:
    1. `initialize`: the catalog must contain the pair, `subscriptionType` must be set, and `apiKeySource` must be `none`.
    2. A local command that produces `system/init`.
    3. The receipt must match exactly: `model`, `effort`, `permissionMode`, `cwd`, the `tools` set, and `interrupt_receipt_v1` in `capabilities`.
  - Settlement: the result message correlated with the session, `modelUsage` containing only the requested model, `permission_denials` recorded, and a missing result treated as unknown.
  - Quota and interrupt: mapped as in finding 3.
- **Consequences.** The sandbox state is configured but not observed. Temp and the shared `.git` are writable. The read-only reviewer cannot run commands. Every session pays about 11k cache-creation tokens to start.
- **Alternatives rejected.**
  - `--bare`: API key only.
  - An interactive session in tmux: no structured receipts.
  - Relying on `/effort status` or `per_turn_effort_active`: unreliable, as probe 3 showed.

## Follow-up leaf issues (proposed, not filed)

1. **Upstream request** (operator, external): report the applied effort in `system/init` for stream-json and SDK clients. Everything below waits on it, or on an explicit decision for option 2.
2. **R2:** a stdlib stream-json transport for Claude Code with the preflight receipt check, and refusal tests for: missing or null effort, model mismatch, an unexpected tool, a permission mode other than the requested one, an API-key source, and a missing interrupt capability.
3. **R2:** select Claude Code as a backend in `tools/worker.py`, with role arguments, the environment allowlist, and settlement and quota mapping. Fake-CLI tests should cover the interrupt receipt, SIGTERM with no result, `rejected` and `credits_required` rate limits, and a fallback model appearing in `modelUsage`.
4. **R2:** a live probe that `sandbox.filesystem.denyWrite` can make the checkout and temp directory read-only for a Bash-enabled reviewer, and that `strictAllowlist` blocks network access without prompting.
5. **Live qualification:** a fictional issue on a disposable repository with a Codex implementer and a Claude Code reviewer, recorded under `docs/evidence/`.

## Limits

- One client version (2.1.300) on one Linux host, with one subscription.
- The quota exhaustion, `api_error` and model-fallback paths come from the documentation and were not observed.
- No managed settings capped effort on this machine, so the cap behavior is documented, not observed.
