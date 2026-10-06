# Data model: On-demand UI demo capture

Entities from [spec.md](spec.md#key-entities), as implemented in [plan.md](plan.md). Decisions are in [research.md](research.md).

## DemoConfig (from `[demo]` in protected `ballast.toml`)

| Field | Type | Rule | Default |
| --- | --- | --- | --- |
| `retention_days` | int | 1–90 | 14 |
| `timeout_minutes` | int | 1–60 | 15 |
| `scenarios` | tuple[DemoScenario, ...] | 1–20 entries, unique names | |
| `error` | str \| None | the fixed reason when invalid; `scenarios` is then empty | |
| `configured` | bool | False when no `[demo]` table exists | |

Parsing never raises. An unreadable `ballast.toml` gives `configured=False`, as `packet.review_config` does. Any rule violation gives one fixed `error`: `demo is not a table`, `demo has an unknown key`, `retention_days must be 1-90`, `timeout_minutes must be 1-60`, `scenarios must be 1-20 tables`, `scenario has an unknown key`, `scenario name must match [A-Za-z0-9._-]{1,64}`, `scenario names must be unique`, `scenario command must be 1-1000 printable characters on one line`, `scenario video is not a safe repository path`, `scenario environment must be 1-80 printable characters`. The full contract is in [contracts/demo-config.md](contracts/demo-config.md).

## DemoScenario

| Field | Type | Rule |
| --- | --- | --- |
| `name` | str | `[A-Za-z0-9._-]{1,64}` |
| `command` | str | 1–1000 printable characters, no newline; run by `bash -c` on the runner and locally by a developer |
| `video` | str | `packet.safe_path`; the one file the command writes |
| `environment` | str | 1–80 printable characters; rendered inert |
| `command_digest` | str (derived) | sha256 hex of `command` as UTF-8 |

## CaptureRequest (one `ballast run demo` invocation; transient)

| Field | Source |
| --- | --- |
| `run_id` | argument; the run must exist |
| `scenario` | argument; must be declared |
| `pr_number`, `head` | #17 checkpoint (`create=False`) outcome `reused`, then the PR read |
| `branch` | the feature branch the run pins; the PR's head ref by #17's construction |
| `default_branch` | `gh api repos/<o>/<r>` (`default_branch`) |
| workflow blob IDs | contents reads at `head` and at `default_branch`; must be equal, else `refused (workflow-differs)` |
| `request` | `secrets.token_hex(8)`; 16 lowercase hex |
| dispatch body | `{"ref": branch, "inputs": {"request", "scenario", "commit": head, "command", "video", "timeout_minutes", "retention_days"}}` |

State transitions of a request: `refused` (R9, nothing written) or `failed-retryable` (dispatch failed, nothing written), or `dispatched`. A dispatch records a `demo_capture` event, waits at most 120 s, then refreshes the packet.

## Ledger event `demo_capture` (runner-only)

| Field | Type | Rule |
| --- | --- | --- |
| `scenario` | str | `[A-Za-z0-9._-]{1,64}` |
| `commit` | oid | 40 or 64 hex |
| `request` | str | `[0-9a-f]{16}` |
| `command_digest` | str | `[0-9a-f]{64}` |
| `pr_number` | int | ≥ 1 |

The event is written only after the dispatch call succeeds. It has no free text. The envelope (`sequence`, `timestamp`, `run_id`, `feature`, `source: runner`) is the ledger's own. Documented in `tools/spec_workflow/ledger-schema.md`.

## DemoCapture (resolved at each checkpoint; derived, never stored)

| Field | Type | Notes |
| --- | --- | --- |
| `scenario` | str | |
| `commit` | oid | from the event |
| `outcome` | enum | `captured`, `in progress`, `failed`, `missing` |
| `reason` | str \| None | fixed: `queued`, `running`, `request-invalid`, `timed-out`, `command-failed`, `cancelled`, `job-failed`, `run-not-found`, `run-ambiguous`, `run-list-truncated`, `commit-mismatch`, `no-video`, `expired`, `artifact-absent` |
| `stale` | bool | `commit != head` |
| `run_id` | int \| None | the workflow run, for the job link |
| `artifact_id` | int \| None | only when `outcome == captured` |
| `command_changed` | bool | the event's digest ≠ the current scenario's digest |

The resolution order is [research R6](research.md#r6-outcome-resolution-at-a-checkpoint). `captured` requires `artifact_id`. Every other outcome has no artifact link (FR-012, SC-002).

## DemoSection (on `packet.Sources.demo`)

| State | When | Renders |
| --- | --- | --- |
| not configured | `configured=False` | `Demo captures: not configured.` |
| configuration invalid | `error` set | `Demo captures: configuration invalid (<reason>).` |
| listed | contract valid | one line per declared scenario: either `not yet requested`, or the resolved DemoCapture, `stale` first when applicable |

The line format is in [contracts/packet-demo-section.md](contracts/packet-demo-section.md). An event for a scenario no longer declared is shown as `<name>: no longer declared` with no link, so a removed scenario never shows a working link.

## Relationships

- One run → many `demo_capture` events → the newest event per scenario is shown.
- One DemoCapture ↔ one GitHub workflow run on the feature branch (matched by `display_title == "Ballast demo <request>"`, then required to have `head_sha == commit`) ↔ at most one artifact `ballast-demo-<request>`.
- The packet is a projection of: the PR (head), the run ledger (events), `ballast.toml` (contract) and GitHub Actions (runs, jobs, artifacts). None of these reads the packet back.
