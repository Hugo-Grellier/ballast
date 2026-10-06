# Data model: Qualify one zero-cost provider fallback

Entities from [spec.md](spec.md) (Key Entities) as they are stored. Decisions are in [research.md](research.md). Every store already exists except `fallback.json` and the step log's `usage.json`.

## Fallback setting

`$XDG_STATE_HOME/ballast/<checkout key>/runs/<run_id>/fallback.json`, in the run's operator directory (`autonomy.run_dir`), mode 0600, directory 0700, written only by `run.py` (operator commands), read only by the wrapper outside the agent's confinement.

| Field | Type | Rule |
| --- | --- | --- |
| `version` | int | `1` |
| `enabled` | bool | `false` after `--local-fallback off` |
| `provider` | label | `ollama` (the only value) |
| `model` | string | ledger `MODEL` pattern, not starting with `-`, no `cloud` tag (`:cloud`, `-cloud`) |
| `endpoint` | string | `http://<loopback IP literal>:<port>`, no path, user info, query or host name; default `http://127.0.0.1:11434` |
| `set_at` | string | UTC ISO time |
| `set_by` | string | `operator` |

Absent file, unreadable file, symlink, or invalid field: the fallback is off and the wrapper prints one line naming the problem. A corrupt setting never enables anything. `--local-fallback off` rewrites the file with `enabled: false` (kept, so the record shows the change).

## Attempt

One execution of a step's agent. Kept in three places that already exist:

- the step log directory `.specify/workflow-state/<run>/agents/<stamp>-<command>-<integration>/`: `stdout.log`, `stderr.log`, `meta.json` (the fallback's `meta.json` adds `route: "fallback"`, `provider`, `model`; every step's `meta.json` adds `local_fallback: true` while the setting is on, in both modes), and for a fallback `usage.json`;
- Autonomous only: one `steps.jsonl` line in the run's operator directory;
- the ledger `route` event (and `usage` for a fallback), when the setting is on.

Fields added to a `steps.jsonl` entry, all optional, so existing readers and records stay valid:

| Field | On | Values |
| --- | --- | --- |
| `failure_cause` | failed primary | `quota-exhausted`, `provider-unavailable`, `cli-unavailable`, `unrecognized` (others are implied by `exit_code`) |
| `fallback` | failed primary, setting on | `{"decision": "selected" \| "refused", "reason": <refusal cause> \| null}` |
| `route` | fallback | `"fallback"` |
| `provider` | fallback | `"ollama"` |
| `model` | fallback | the setting's model |
| `local_fallback` | every entry while the setting is on | `true` |

A `cli-unavailable` primary is recorded with `ran: false` and counts no agent step.

## Worktree state evidence

Taken before and after a primary attempt only while the setting is on (research R3, DEC-0001). Kept in memory by the wrapper and never written to a record. Only the decision (`changed-state` or not) is recorded.

| Piece | Source | Covers |
| --- | --- | --- |
| tree | `autonomy.tree_digest` (existing) | tracked and untracked non-ignored files, minus protected inputs, `reviews/`, `autonomous/drafts/` |
| reviews | `autonomy.reviews_digest` (existing) | the feature's `reviews/` |
| drafts | the drafts directory listing | no draft created |
| ignored | `autonomy.ignored_digest` (new) | every git-ignored path in the worktree except protected inputs, plus `SPECIFY_WRITABLE`; `lstat` path, type, mode, size, `mtime_ns`, `ctime_ns`, inode, link target |
| refs | `autonomy.refs_digest` (new) | `HEAD` and every ref (`git for-each-ref`) |

Any piece that cannot be established means "cannot be checked". That covers a Git error, an entry `lstat` cannot read, more than 200,000 ignored entries, or more than 10 s for the walk. The result is a `changed-state` refusal.

## Human-gated run record

A human-gated run has no `record.md` or `steps.jsonl`. Whether the fallback was on (AC-020) is shown by:

- `fallback.json` in the run's operator directory: the current setting, kept with `enabled: false` after `off`;
- `ballast run status RUN`: a `Local fallback: off` or `Local fallback: on (ollama MODEL)` line, printed only when `fallback.json` exists;
- each step's `meta.json`: `local_fallback: true` while the setting is on;
- the ledger `route` events of every step that considered the fallback.

Review provenance (AC-016) comes from the ledger. A run holding a runner `route` with `route_source: fallback`, `outcome: success` and a `ballast-review` stage reports no review as cross-provider ([contracts/ledger.md](contracts/ledger.md#report)).

## Normalized cause

Pure function of (integration, exit code, blocking status, containment, output tail, CLI found).

```text
exit 0, no blocking status            -> success
EXIT_BLOCKED / BLOCKED_* reported     -> blocked
EXIT_TAMPERED / not contained         -> tampered
EXIT_LIMIT / wall-time timeout        -> limit
EXIT_INTERRUPTED                      -> interrupted
draft refused by the recorder         -> draft-refused
CLI not on PATH                       -> cli-unavailable      (recoverable)
nonzero, tail matches quota table     -> quota-exhausted      (recoverable)
nonzero, tail matches availability    -> provider-unavailable (recoverable)
anything else                         -> unrecognized
```

## Fallback decision

```text
primary attempt finished
  ├─ setting off or invalid ─────────────────────────────► step result as today (no record)
  ├─ Chat run ───────────────────────────────────────────► as today
  ├─ cause not recoverable ──────────────────────────────► as today
  ├─ not the step's first attempt (a draft retry) ────────► as today (cause recorded)
  └─ recoverable, first attempt
       ├─ state changed or uncheckable ► refused: changed-state
       ├─ endpoint not loopback ─────► refused: privacy-exclusion
       ├─ server not answering ──────► refused: incompatible-capability
       ├─ model not installed ───────► refused: unknown-free-status
       ├─ model remote / cloud ──────► refused: privacy-exclusion
       ├─ codex lacks --oss ─────────► refused: incompatible-capability
       ├─ codex sandbox won't start ─► refused: incompatible-capability
       ├─ checks over 10 s ──────────► refused: incompatible-capability
       ├─ other Codex config layer ──► refused: permission-mismatch
       ├─ argv/env wider than primary► refused: permission-mismatch
       ├─ step limit exhausted ──────► existing limit refusal (run stops)
       └─ selected ──► fallback attempt (once)
                          ├─ success, drafts accepted ─► step succeeds
                          └─ any failure / refused draft / timeout ─► step fails, no retry
```

A refusal ends the step with the primary's exit code and a stderr line `local fallback refused: <reason>: <detail>`. The detail is a fixed phrase per check (for example `model qwen3:4b is not installed`) and holds no output, prompt or account text.

## Ledger additions (schema v1, additive)

`ENUM_FIELDS["route"]`:

- `route_source` += `fallback`
- new `failure_cause`: `quota-exhausted`, `provider-unavailable`, `cli-unavailable`, `unrecognized`
- new `fallback`: `selected`, `refused`
- new `fallback_reason`: `unknown-free-status`, `privacy-exclusion`, `incompatible-capability`, `permission-mismatch`, `changed-state`

`FIELDS["route"]` += `failure_cause?`, `fallback?`, `fallback_reason?` (labels). Validation: `fallback_reason` requires `fallback: refused`; `refused` requires `fallback_reason`; `route_source: fallback` forbids `failure_cause` and `fallback` (the same rule as [contracts/ledger.md](contracts/ledger.md#validation-ledgerpy)).

`usage` is unchanged; the fallback's event uses existing fields (`invocation_id` = the fallback step ID, `stage`, `scope: invocation`, `counter_source: codex-exec-json`, `counter_digest`, token counts, `complete`, `provider: ollama`, `model`, `step_id`, `attempt`, `cause_id`).

Event IDs: `fallback:<primary step>:<attempt>:route` and `fallback:<primary step>:<attempt>:usage`. The `(stage, cause_id, attempt)` uniqueness rule holds because the primary and the fallback use attempts n and n+1 under the primary step's `cause_id`.

## Evaluation record

`specs/23-free-fallback/evaluation.md` (tracked): candidate, alternatives with rejection reasons (from R1), host versions, each pilot probe with command and outcome, the sandbox-nesting result in both modes, one pilot step's duration, outcome and usage, the decision, and the R2 signatures adopted with their redacted source messages.
