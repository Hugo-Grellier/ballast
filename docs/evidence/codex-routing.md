# Standalone routing qualification — #175

Date: 2026-10-14. Installed client: Codex CLI 0.162.1. Commands executed outside
CI, directly from an issue worktree with Python's isolated stdlib mode:

```sh
python3 -I -S tools/codex.py --model gpt-6.1-sol --effort medium
python3 -I -S tools/codex.py --model gpt-6-luna --effort low
```

| Requested model / effort | Observed model / effort | Receipt | Task started |
| --- | --- | --- | --- |
| gpt-6.1-sol / medium | gpt-6.1-sol / medium | qualified | false |
| gpt-6-luna / low | gpt-6-luna / low | qualified | false |

Both commands exited 0. The model catalog advertised each effort for its model.
The resolved `thread/start` response matched the explicit pair, OpenAI provider,
assigned directory, read-only/no-network sandbox and never-approve policy. No
parent conversation was forked or resumed. No task prompt or `turn/start` was sent.

This proves resolved client configuration for these particular new sessions. It
does not attest provider-internal computation, actual task execution, nested
delegation, resumed sessions, billing, queue recovery, independent review, or PR
readiness. Do not reuse it as qualification for another worker invocation. No
account, quota, prompt, machine destination or credential data is included here.

Deterministic tests replace process creation with in-memory protocol streams.
They exercise mismatches, absent fields, unsupported efforts, pagination, malformed
JSON, rejected RPC, unexpected response IDs, EOF, deadline, CI refusal and shutdown.
These tests start no real agent, including when collected by the existing CI suite.

Protocol references: the installed client's generated app-server schema, especially
`ThreadStartParams`, `ThreadStartResponse`, `ModelListParams`, and the
[official app-server documentation](https://learn.chatgpt.com/docs/app-server).
The generated local schema is evidence for the tested binary, not a new shipped
protocol definition.

## In-place layout recheck

After the operator requested normal repository locations, both commands above
were rerun from `tools/codex.py` on 2026-10-14. Codex 0.162.1 again reported
requested equal to observed for both pairs, `status: qualified`, and
`task_started: false`. The relocation introduces no model task or paid fallback.
