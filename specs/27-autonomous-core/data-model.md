# Data model: Autonomous run core

All operator records live under `state_dir(root)/runs/<run-id>/`, where `state_dir` is the existing `launcher.state_dir()` (`$XDG_STATE_HOME/ballast/<sha256(checkout)[:16]>/`). Directories are created with mode `0700`. Only `run.py`, the agent wrapper and trusted `shell` steps write these files; agents cannot (see [research R-02](research.md#r-02-where-the-mode-limits-and-eligibility-live)). JSON is UTF-8, and writes go through a temporary file plus `os.replace`, opened with `O_NOFOLLOW`. Readers treat a missing, malformed or unknown-version file as a refusal, never as a default.

Committed projections live in the feature directory: `specs/<f>/autonomous/record.md` and the provisional block in `intent.md`.

## Run record: `run.json`

| Field | Type | Rules |
| --- | --- | --- |
| `version` | int | `1` |
| `run_id` | str | `[A-Za-z0-9_-]{1,64}`, equal to the directory name |
| `feature` | str | `specs/<n>-<slug>`, validated by `artifacts.Feature` |
| `issue` | int | Equal to `<n>` |
| `workflow` | str | `ballast-feature`, `ballast-autonomous` or `ballast-continue` |
| `mode_history` | list of Mode change | Append-only; at least one entry; the last entry is the effective mode |
| `status` | str | `active` → `stopped` / `completed` → `published` / `continued` |
| `risk` | Risk record | Autonomous only |
| `eligibility` | Eligibility result | Autonomous only |
| `limits` | Limits | Autonomous only |
| `agent_steps` | int | ≥0; incremented by the wrapper before each agent step |
| `integration`, `review_integration` | str | `claude` or `codex`; `cross_provider` is a bool |
| `integration_fallback` | str, optional | Present only when Codex's own sandbox could not start inside Ballast's confinement at run start, so Claude took both roles; holds the fixed reason (DEC-0004) |
| `continues` | str or null | Source run ID for a `ballast-continue` run |
| `started_at` | str | ISO-8601 UTC |

State transitions (only trusted code moves them):

```text
active ──workflow completed──▶ completed ──publish ok──▶ published
   │                               └──publish failed──▶ stopped (block: forge)
   └──any other end──▶ stopped (block.json written)
stopped|completed|published ──`run continue`──▶ continued   (new run created)
```

`resume` is allowed only when the effective mode is `human-gated`. The wrapper refuses an agent step unless `status == "active"`.

### Mode change

`{ "mode": "human-gated"|"autonomous", "at": ISO, "by": "operator", "action": "start"|"lower", "reason": str|null, "decision_id": "HD-NNNN"|null }`

- `start` is valid only as the first entry. `lower` is valid only from `autonomous` to `human-gated`.
- No code path appends a raise. An attempt to raise is refused before any write (FR-003).

### Risk record

`{ "level": "R0"|"R1"|"R2", "source": "scope-record"|"raised", "history": [{ "level", "at", "decision_id" }], "boundaries": [str] }`

The level only rises. `boundaries` lists the R2 boundaries touched, as declared in the scope record or in drafts, and is deduplicated.

### Eligibility result

`{ "eligible": bool, "checked_at": ISO, "reasons": [str], "privileged_actions": [str], "policy": Policy snapshot, "ignored_policy": [str] }`

Each refusal reason is a fixed phrase from [contracts/cli.md](contracts/cli.md#refusals). The policy snapshot is taken at start, and every later risk re-check uses it.

### Policy snapshot

The parsed, narrowed `[autonomous]` table from `ballast.toml` ([contracts/config.md](contracts/config.md)): `{ "risk": [..], "excluded_boundaries": [..], "authorized_privileged_actions": [..] }`.

### Limits

`{ "wall_time_minutes": int, "deadline": ISO, "max_agent_steps": int, "source": "operator"|"project"|"default" }`. Wall time is between 1 and 1440 minutes; the step limit is between 1 and 200.

## Provisional decision: `decisions.jsonl` (append-only, hash-chained)

One JSON object per line:

| Field | Rules |
| --- | --- |
| `id` | `PD-NNNN`, sequential from `PD-0001` |
| `prev` | SHA-256 of the previous line's bytes, or 64 zeros for the first |
| `point` | One of `scope`, `clarification`, `intent`, `plan`, `plan-review`, `tasks`, `implementation-review`, `specialist-review`, `decision-resolution`, `spec-reconciliation`, `final-acceptance` |
| `decision` | One of `accept`, `assume`, `resolve`, `accept-finding`, `block`. `block` is never written to this log; it goes to `block.json`. |
| `summary` | 1–500 characters; one line |
| `basis` | 1–2000 characters |
| `evidence` | List of 1–20 repository-relative paths or `https://` links. Paths must exist and stay inside the checkout. |
| `artifact` | `{ "path": str, "sha256": str }`, the version the decision applies to |
| `agent` | `{ "provider": "claude"|"codex" (runner), "model": str|"unreported" (agent-reported), "role": "author"|"reviewer", "step_id": str (runner) }` |
| `material` | bool. True for a discovery that changes product behavior, scope, data authority, a security boundary or accepted architecture (FR-018). |
| `supersedes` | `PD-NNNN` or null. The referenced ID must exist and must not already be superseded. |
| `review` | Present only for review points: Review entry |
| `assumption` | Present only for `clarification`: `{ "question", "default", "reversible": true }` |
| `at` | ISO-8601 UTC, written by the runner |

Invariants:

- Exactly one current, non-superseded decision exists per point (SC-002), except `clarification`, `decision-resolution` and `specialist-review`, which may have several.
- The recorder blocks the run (`review-finding`) on every `critical` or `high` finding, whatever disposition the review proposes, including `resolved`. The report is kept for human-gated recovery. An agent's claim that it resolved such a finding is not accepted in Autonomous, because #27 has no fix loop (FR-019; plan review F-3).
- A line is never rewritten. A line without its trailing newline, or with a broken `prev` chain, makes the log unreadable, and the run refuses (spec edge case: "a partly recorded decision is not treated as complete").

### Review entry

`{ "kind": "plan"|"engineering"|"test"|"security"|"documentation"|"architecture"|"dependency"|"database-migration"|"spec-reconciliation", "verdict": "approved"|"changes-requested"|"partial"|"failed", "report": "specs/<f>/reviews/<kind>.md", "cross_provider": bool, "author_provider": str, "findings": [{ "id": "F-NNN", "severity": "critical"|"high"|"medium"|"low"|"info", "label": "spec-violation"|"implementation-bug"|"architecture-issue"|"missing-test"|"spec-ambiguity"|"proposed-product-change", "disposition": "resolved"|"accepted-provisionally"|"open", "reason": str|null, "evidence": [path|url] }] }`

`resolved` and `accepted-provisionally` are valid only for `medium` and below; `accepted-provisionally` also needs a `reason`. `open` is valid only for `low` and `info`.

## Block: `block.json`

`{ "category": "decision"|"contradiction"|"review-finding"|"limit"|"postcondition"|"tamper"|"unfinished-step"|"permission"|"ineligible"|"forge"|"interrupted", "step_id": str|null, "condition": str, "options": [{ "option": str, "consequence": str }], "recovery": str, "command": str, "evidence": [path], "at": ISO }`

- Only one current block exists per run, and a new one replaces the old. Earlier blocks are kept in `blocks.jsonl`.
- `decision` and `contradiction` blocks come from the agent draft `drafts/block.json` and must list at least two options.
- `command` is always one of `ballast run continue RUN_ID ...`, `ballast run publish RUN_ID`, `ballast discard-runs`, or `ballast run start ...` (FR-022, FR-023).

## Human decision: `human-decisions.jsonl` (append-only, hash-chained)

`{ "id": "HD-NNNN", "prev": sha, "kind": "mode-change"|"block-resolution"|"merge-feedback", "ref": str (1–500 chars: a PR review URL or short text), "resolves": "block"|null, "at": ISO, "by": "operator" }`

Written only by `ballast run continue`. Merge itself is GitHub's record and is not mirrored.

## Agent draft (agent-writable input): `specs/<f>/autonomous/drafts/<point>.json`

The draft is untrusted input, validated by the recorder against [contracts/decision-draft.md](contracts/decision-draft.md) and then deleted. A recorder accepts a draft only when the protected `meta.json` of the immediately preceding agent step lists it with a matching SHA-256 ([workflow contract](contracts/workflow.md), round 6 H-3). Fields the runner owns (`id`, `prev`, `at`, `agent.provider`, `agent.step_id`) are ignored when present, and a warning is recorded.

## Committed projections

- `specs/<f>/autonomous/record.md`: rendered deterministically from `run.json` (mode history, risk, limits) and `decisions.jsonl`. Every validator in an Autonomous run re-renders it and compares bytes. A difference fails with "autonomous record was edited outside the recorder" (FR-011, FR-013).
- `intent.md` provisional block:

  ```text
  <!-- workflow-provisional: begin -->
  - **Status**: agent-provisional, not human-approved
  - **Decision**: PD-NNNN
  - **Decided by**: <provider>/<model> (<role>)
  - **Recorded**: <ISO>
  - **Source**: ballast-autonomous run (<run-id>)
  - **Spec**: specs/<f>/spec.md
  - **Provisional spec digest**: sha256:<64 hex>
  <!-- workflow-provisional: end -->
  ```

  The block is stale as soon as `spec_digest(spec.md)` differs (FR-012, AC-008). A spec change made by a later provisional decision needs a new `intent` decision that supersedes the old one.
