# Live check: local zero-cost fallback on the operator host (#23)

- Run: 2026-10-06, by the driving agent (claude/claude-sonnet-5-5) from the operator side: a host shell outside Ballast's confinement, not a confined agent step and not through `ballast run` (no ballast command runs in this worktree). Agent-provisional.
- Host: Codex `codex-cli 0.155.1`, Ollama 0.35.1 serving `127.0.0.1:11434`, CPU only, models `qwen3:4b-16k` (served with `num_ctx 16384`) and `qwen3:4b` (stock). No `/etc/codex`. The operator's real `~/.agents/skills` is not empty.
- Method: a scratch Git project per case under the session scratchpad (`live23/`), a human-gated run record (`run42`, feature `specs/1-demo`, one Codex skill `speckit-plan`), the setting written with `fallback.write_setting` into an operator directory outside `/tmp` (the wrapper refuses a state directory under a temp path, as designed), and the real wrapper `tools/spec_workflow/bin/claude -p /speckit-plan`. The "primary" is a stand-in `claude` that prints the redacted subscription-limit message and exits 1, as the tests and the quickstart simulate a quota failure. Codex, Ollama and the probes are real. No cloud model, sign-in or download was involved; no credential or environment value was printed.
- Result: **PASS**. Every eligibility check I exercised refused or selected as specified, and one real fallback completion ran on the local model.

## Eligibility checks (real Ollama and Codex)

| Case | Setup | Observed | Expected |
| --- | --- | --- | --- |
| Not a recoverable failure | primary prints `boom`, exits 1, fallback on | exit 1, nothing else on stderr, no `route` event, Codex never ran | `unrecognized`: no fallback, no record |
| Setting off | no `fallback.json` | exit 1, the primary's own output, no ledger event | today's behavior |
| Changed state | primary appends to a tracked file, exit 1 | `local fallback refused: changed-state: worktree state changed`; ledger `route` with `failure_cause: quota-exhausted`, `fallback: refused`, `fallback_reason: changed-state` | `changed-state` |
| Model not installed | `qwen3:nope` | `refused: unknown-free-status: model qwen3:nope is not installed` | `unknown-free-status` |
| Context too small | stock `qwen3:4b` (no `num_ctx` in `/api/show`) | `refused: incompatible-capability: served context unknown` | refuse below 16384 (DEC-0004); see note 1 |
| User skills | the operator's real `HOME` with a non-empty `~/.agents/skills` | `refused: permission-mismatch: user skills directory is not empty` | `permission-mismatch` |
| Endpoint override in the environment | `OLLAMA_HOST=127.0.0.1:9` set for the wrapper | not sent to Codex (the variable is stripped, so Codex used `127.0.0.1:11434`); the step ran on the real model (next section) | no endpoint override survives |

Every refusal returned the primary's exit code (1) and sent nothing: the only server requests were `/api/version`, `/api/tags` and `/api/show` with the model name, and Codex never started.

## One real fallback completion

Case `G-endpoint`: model `qwen3:4b-16k`, scratch `HOME` (empty `~/.agents/skills`), `OLLAMA_HOST` set to an unreachable address to show it cannot redirect the step.

- Wrapper stderr: `local fallback: running this step once on ollama qwen3:4b-16k (quota-exhausted)`. Exit code **0** after 546 s (CPU model, one step; the check budget was 10 min).
- Codex argv recorded in `meta.json`: `codex exec --sandbox workspace-write --config sandbox_workspace_write.network_access=false --config sandbox_workspace_write.writable_roots=[] $speckit-plan --oss --local-provider ollama -m qwen3:4b-16k --json`. No bypass flag, no extra writable root, no base-URL key.
- Private `CODEX_HOME` under the wrapper's temporary directory (Codex warned that it would not create helper binaries under `/tmp`; harmless); it is removed afterwards. The model's answer reached the wrapper's stdout. The scratch skill file had no YAML frontmatter, so Codex logged `failed to load skill`; the step still completed, which proves the path, not the skill content.
- `usage.json` in the step's log directory: `counter_source: codex-exec-json`, `input_tokens 9089`, `cached_tokens 0`, `output_tokens 653`, `complete: true`.
- Ledger (`ledger.read` returned no problems), in order:
  1. `route` (runner): attempt 1, `provider: claude`, `failure_cause: quota-exhausted`, `fallback: selected`, `outcome: mechanical-failure`.
  2. `route` (runner): attempt 2, `provider: ollama`, `model: qwen3:4b-16k`, `route_source: fallback`, `outcome: success`, `cause_id` of the failed primary step.
  3. `usage` (client-counter): attempt 2, `provider: ollama`, the counts above.
- `git status` of the scratch project stayed clean: the model changed nothing.

## Start-up egress of the Codex CLI itself (security F-002)

With `ss` on the real fallback process (first run, before the fix), the Codex process held a connection to `127.0.0.1:11434` (Ollama) and two HTTPS connections to Cloudflare addresses that resolve for `chatgpt.com`. With a local CONNECT logger as `HTTPS_PROXY` (answering 503), a bare `codex exec --oss` run (empty `CODEX_HOME`, loopback exempt via `NO_PROXY`) tried `github.com:443`, `api.github.com:443` and `chatgpt.com:443` (twice) within a second of starting, and then went on to start its turn with the local model: those requests are product services (update and feature checks), not the model request, and the step does not depend on them.

After the fix the environment sets every proxy variable to the closed port `127.0.0.1:9` and `NO_PROXY` to loopback. Rerun `I-blackhole` through the real wrapper: exit 0 in 210 s, and sampling `ss` every 3 s for the whole run showed the fallback's Codex process holding only `127.0.0.1:<port> -> 127.0.0.1:11434`. A sampling is not a proof (a short connection can be missed), and a process that ignores the variables is not stopped: this is a reduction, stated as such in the ADR and the policy.

## Not run live

- **Autonomous fallback.** On this host Codex's sandbox does not start inside Ballast's bubblewrap (pilot item 7, DEC-0004), so an Autonomous step must refuse with `incompatible-capability`; it needs an Autonomous run, and no ballast command runs in this worktree. Covered by `RefusalTests` with a fake `bwrap` and `codex`.
- **An operator proxy.** None is set on this host. Codex honors proxy variables (shown below), and the fix strips them from the fallback's environment (`InvocationTests.test_fallback_env`, `PermissionTests.test_extra_env_refused`).
- **A claude-primary Autonomous run, the real Claude quota message, and a cloud-tagged model** (none exists here).

## Notes

1. The stock model's `/api/show` has no `num_ctx` parameter (Ollama's default context applies), so the refusal says `served context unknown` rather than `below 16384`. It is safe and correct; the wording is a low documentation point (recorded in the documentation review).
2. The 546 s completion is the cost of a CPU model on a trivial prompt (pilot item 10: 322 s). A real planning step would very likely exceed a useful time; the step then fails with both attempts recorded, as the ADR states.
