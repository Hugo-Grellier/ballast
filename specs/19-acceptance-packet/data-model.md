# Data model: acceptance packet

Everything here is derived at a checkpoint and held in memory. The only things persisted are the archive copy of the packet text and one ledger event (FR-002). Decisions are in [research.md](research.md); the rendered text is in [contracts/packet-format.md](contracts/packet-format.md).

## Sources (read, never written)

`Sources` is a frozen bundle that `packet.collect` builds and the pure function `packet.render` consumes. `render` does no I/O, so tests drive it directly.

| Field | Type | From |
| --- | --- | --- |
| `owner`, `repo` | validated names | #17 identity (`ballast.toml` pin) |
| `run_id`, `feature`, `issue` | validated | #17 identity |
| `pr_number` | int | #17 outcome |
| `head`, `base` | Git object ID | fresh `pulls/<n>` read |
| `feature_version` | Git tree ID | `git rev-parse <head>:<feature>` |
| `spec_version` | sha256 hex | `spec.md` blob at head |
| `files` | map of feature-relative path → present | `git ls-tree -r --name-only <head> -- <feature>/` |
| `spec_text` | str (≤ 1 MB) | `spec.md` at head |
| `manifest` | `Manifest` or `None` | `acceptance-evidence.json` at head |
| `decisions_md` | str or `None` | `decisions.md` at head |
| `head_fingerprint` | sha256 hex | `ledger.commit_tree(root, head, git)` |
| `events` | ledger events | `ledger.read(root, run_id)`, no problems |
| `run_record`, `decisions`, `human_decisions`, `checks` | autonomy records or `None` | `autonomy.read_run` and its siblings, only when `run.json` exists |
| `scope_risk` | str or `None` | #17's intake `Risk:` line |
| `check_runs` | list of `CheckRun` | R8 read |
| `config` | `ReviewConfig` | `[review]` of `ballast.toml` |
| `openapi` | `ApiComparison` or `None` | R10 |
| `generated_at` | UTC datetime | clock (injected in tests) |

## Criterion

| Field | Rule |
| --- | --- |
| `id` | `AC-NNN`, from `ledger.spec_criteria`, in spec order, first occurrence only |
| `title` | inert text (R9), ≤ 120 characters |
| `line` | 1-based line in `spec.md` at head; link `blob/<head>/<feature>/spec.md?plain=1#L<line>` |
| `state` | one of `EvidenceState` |
| `reason` | fixed text, for any state except `verified` |
| `tests` | list of `TestEvidence` |
| `ui` | list of `UiResult` mapped to this ID |
| `ci` | link to the head commit's check runs, `commit/<head>/checks`, when `check_runs` is not empty; else `no CI result at head`. Suite-wide CI never changes `state` (R4, DEC-0001) |

## EvidenceState

`verified`, `failed`, `not run`, `stale`, `missing`. Derivation is R4. Only `verified` needs every mapped test passed at `(head_fingerprint, spec_version, manifest_digest)`.

```text
no manifest / AC not mapped ─────────────► missing
manifest.spec_digest ≠ spec_version ─────► stale (spec version <x>)
any test failed at head ─────────────────► failed
else any test stale ─────────────────────► stale
else any test with no event ─────────────► not run
else (all passed at head) ───────────────► verified
```

## TestEvidence

| Field | Rule |
| --- | --- |
| `test` | `tests.test_….test_…` as in the manifest (pattern-checked) |
| `result` | `passed`, `failed`, `stale`, `not run` |
| `belongs_to` | for `stale`: `commit <12 hex>` (from the event's `commit`), else `spec <12 hex>` when its spec digest differs, else `manifest <12 hex>`, else `snapshot <12 hex>` |
| `file` | repository path of the test module at head, or `None`: the longest dotted prefix of `test` whose `<prefix with / >.py` exists at head (`git cat-file -e <head>:<path>`); linked as `blob/<head>/<path>`, else the name is shown unlinked with `file not found at head` (DEC-0001) |
| `source` | the ledger source label (`operator-attested`) and the event sequence number, rendered as `ledger event <seq> of run <run_id>` because the ledger is local and has no URL (DEC-0001) |

## Manifest

The existing schema 1 (`schema_version`, `spec_digest`, `criteria: {AC-NNN: [test, …]}`). The packet checks its **schema shape only** (F-001): valid JSON, exactly those keys, `schema_version` 1, a SHA-256 `spec_digest`, and for each `AC-NNN` a non-empty list of `tests.test_….test_…` names; anything else is `manifest-malformed`. A `spec_digest` that differs from the spec, an AC the spec lacks and a spec AC the manifest lacks are not malformed: they give `stale`, the unknown-criteria line and `missing` (R4). There is no intent-approval check, since the packet reports and does not approve. `digest` is the SHA-256 of the file bytes. IDs not in the spec go on the "unknown criteria" line.

## Decision lines

| Kind | Fields | Label |
| --- | --- | --- |
| `ProvisionalDecision` | `id` (`PD-NNNN`), `point`, inert `summary`, `superseded_by?`, record line | `agent-provisional` |
| `HumanDecision` | `id` or gate `step_id`, `choice`/`action`, ledger source label | `human` |
| `FeatureDecision` | `DEC-NNNN`, `resolved: bool`, line in `decisions.md` | `see record` |

## Finding

`id`, `severity` (`critical`…`info`), `disposition` (`open`, `accepted-provisionally`), inert `reason`, `link` (R7). Only open findings are listed; zero is written as `None (0)`.

## CheckLine

Either `RunCheck` (from `checks.json`: inert command, exit, seconds, timed out; labeled `runner, before publication, not bound to the head commit`) or `CheckRun` (`id` int, inert `name`, `status` ∈ `queued|in_progress|completed|…`, `conclusion?`; link built from `id`). Ledger `verification` events without `ac_id` are listed with their status, including `skipped` and `unavailable`.

## ReviewConfig

```toml
[review]
openapi = "docs/api/openapi.json"      # optional repository path

[[review.ui_states]]                    # optional, at most 50
name = "Login error"                    # 1–80 characters
criteria = ["AC-003"]                   # AC-NNN list, at least one
path = "docs/screens/login-error.png"   # exactly one of path / check
# check = "ui / login-error"            # GitHub check run name, 1–100 characters
```

Paths: relative, `/`-separated segments matching `[A-Za-z0-9._-]{1,100}`, no `.` or `..` segment, at most 300 characters. Invalid → the section says `configuration invalid (<reason>)` (R12).

## ApiComparison

| Field | Rule |
| --- | --- |
| `state` | `no API change`, `changed`, `added in this PR`, `removed in this PR`, `could not compare` |
| `reason?` | for `could not compare`: `not JSON`, `too large`, `not an OpenAPI document`, `unreadable`, `github-error` |
| `added`, `removed`, `changed` | sorted `(METHOD, path)` lists |
| `breaking` | subset, each with a fixed cause: `operation removed`, `parameter removed`, `parameter now required`, `request body now required`, `request field removed`, `request field now required` |

## UiResult

`name`, `criteria`, `kind` (`path` or `check`), `result` (`present`, `passed`, `failed`, `not run`, `missing`), and a link built by Ballast or `None`.

## Packet

| Field | Rule |
| --- | --- |
| `text` | rendered section with markers, at the level chosen by R14 |
| `full_text` | level-1 text, for the archive |
| `masked_digest` | SHA-256 of `text` with the `Generated:` line removed |
| `shortened` | `level > 1` |
| `counts` | per `EvidenceState` |

## PacketOutcome

Frozen dataclass: `state` (`published`, `updated`, `unchanged`, `pending`, `failed-retryable`), `reason?`, `remedy?`, `detail?` (exception type only), and for a published state `pr_number`, `head`, `base`, `feature_version`, `packet_digest`, `shortened`, `counts`. Printed as one line ([contracts/checkpoint-integration.md](contracts/checkpoint-integration.md)) and recorded as one `acceptance_packet` event ([contracts/ledger-acceptance-packet-event.md](contracts/ledger-acceptance-packet-event.md)).

### State transitions

There is no stored state machine. Each checkpoint recomputes the outcome from GitHub and the sources. Across checkpoints on one PR:

```text
(no section) ──publish──► published
published/updated/unchanged ──same masked text──► unchanged
published/updated/unchanged ──different text────► updated
any ──section deleted by a human──► published (appended again)
any ──failure──► pending | failed-retryable (section left as it was) ──next checkpoint──► retry
```
