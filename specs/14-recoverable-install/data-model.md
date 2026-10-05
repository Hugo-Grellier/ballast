# Data model: Recoverable installs and pin updates

Entities from the [spec](spec.md#key-entities), with their storage, owner and validation. Decisions are in [research.md](research.md). File formats are in [contracts/operator-state.md](contracts/operator-state.md) and [contracts/cache.md](contracts/cache.md).

## Where things live

| Entity | Location | Writer | Agent-writable |
| --- | --- | --- | --- |
| Installation (live) | Installed entries in the checkout (below) | `tools/setup` | Yes (checkout); guarded by trust |
| Staged installation | `.ballast/setup/<attempt>/stage/` | `tools/setup` | Yes; validated before use, deleted after |
| Previous installation (backup) | `.ballast/setup/<attempt>/previous/` | `tools/setup` | Yes; restored only by rename, verified against the previous record |
| Installation record | `$XDG_STATE_HOME/ballast/<key>/installation.json` | `tools/setup` | No |
| Setup attempt journal | `$XDG_STATE_HOME/ballast/<key>/setup-attempt.json` | `tools/setup` | No |
| Checkout lock and holder | `$XDG_STATE_HOME/ballast/<key>/checkout.lock`, `setup-holder.json` | `tools/setup` (exclusive), launcher (shared) | No |
| Cached version and its record | `$XDG_DATA_HOME/ballast/standard/<ref>/`, `<ref>/.ballast-cache.json` | `ballast` CLI | No |
| Cache lock | `$XDG_DATA_HOME/ballast/standard/.locks/<ref>.lock` | `ballast` CLI | No |
| Run format record | `<git-common-dir>/speckit-runs/<run-id>/run-format.json` | `run.py` | No |
| Version declarations | `tools/cli.toml` of each standard version | release | No (cache) |
| Disposable preview build | `$XDG_DATA_HOME/ballast/preview/<random>/` | `ballast preview` | No; deleted in every outcome |

`<key>` is `launcher.state_dir(root)`: the first 16 hex digits of the SHA-256 of the resolved checkout path.

## Installation

- **Installed entries** (the unit of a switch): `.ballast/spec_workflow`, `.ballast/.setup-version`; each `.specify/` entry in `INSTALLED`, except that `.specify/workflows` is switched child by child, leaving `runs`; every skill directory or link matching `SKILLS`; `docs/policies/<name>.md` for each shipped policy. Entries recorded in the previous `installation.json` that the new version no longer builds are removed in the same switch, and only when the project ignores them.
- **Never touched**: `.specify/memory/constitution.md` (copied in only when absent, R13), `docs/policies/project/`, `.specify/workflows/runs`, `.specify/workflow-state`, `.specify/bugs`, `.specify/assessments`, `ballast.toml`, every tracked file.
- **Identity**: pinned ref, fingerprint (`VERSION` plus the digest of the standard's `tools/`, `templates/` and `ballast.toml`, as today) and the content digests of the installation record.
- **Current and verified** (FR-011): the record's fingerprint equals the computed one, and hashing the live entries (minus `LOCAL_STATE`) gives exactly the record's files.

## Setup attempt

Fields: `schema`, `attempt` (random ID), `pid`, `started`, `ref`, `fingerprint`, `phase`, `entries` (ordered relative paths), `work` (the attempt's work-area path), `previous_record` (the record before the attempt, or null), `record` (the new record, from `switching` on).

State transitions:

```text
(none) ──acquire lock, recover, preflight──▶ staging
staging ──build + validate ok──▶ switching ──all renames + live verification ok──▶ committed ──backups deleted, record written──▶ (none)
staging ──any failure──▶ (none)               work area deleted; checkout untouched
switching ──any failure──▶ (none)             every entry rolled back from previous/
killed in staging    → next setup: delete work area                → "previous installation kept"
killed in switching  → next setup: roll back every entry           → "previous installation restored"
killed in committed  → next setup: delete backups, write record     → "new installation completed"
```

Rollback per entry, using the journal's entry list and the filesystem:

| `previous/<e>` | live `<e>` | `stage/<e>` | Meaning | Action |
| --- | --- | --- | --- | --- |
| absent | old | present | not yet moved | nothing |
| present | absent | present | moved out, not in | rename `previous/<e>` → live |
| present | new | absent | switched | rename live → `stage/<e>`, then `previous/<e>` → live |
| absent | new | absent | entry new in this version | remove live |

After rollback, setup verifies the live installation against `previous_record` when there is one and reports a difference instead of claiming success.

## Cached version

Fields of `.ballast-cache.json`: `schema` (1), `ref`, `fetched` (UTC time), `files` (relative path → `{"sha256": hex, "exec": bool}` or `{"link": target}`). The record file itself is excluded from verification.

States: absent → fetching (`.fetch-*`, invisible to readers) → verified → damaged (missing record, or any missing, added or altered entry) → refetched or refused.

## Run evidence

Unchanged by setup, preview, retry and rollback in every outcome: `.specify/workflows/runs/`, `.specify/workflow-state/`, the archives under `<git-common-dir>/speckit-runs/`, Autonomous records, and the operator's `trusted.json`, `in-progress` and tamper marker. New: `run-format.json` in each new run's archive.

An **unfinished run** is a directory under `.specify/workflows/runs/` whose `state.json` `status` is not `completed`.

## Version declarations (`tools/cli.toml`)

| Key | Type | Meaning |
| --- | --- | --- |
| `[cli] minimum` | `X.Y.Z` | Unchanged (ADR-0002); stays `0.1.0`. |
| `[doctor] probes` | list | Unchanged. |
| `[setup] recoverable` | bool | This version's setup stages, journals and switches (AC-021). Absent means false. |
| `[runs] format` | string | The run-state format this version writes. |
| `[runs] resumes` | list of strings | Formats this version can resume. Absent means none. |

## Update preview

Fields (see [contracts/preview-cli.md](contracts/preview-cli.md)): pinned ref, target ref, installed ref (or `unknown`), target CLI minimum and whether this CLI meets it, target `recoverable`, runs (ID, status, format, compatible), paths (`added`, `changed`, `removed`), ignore rules (`ok` or the paths not ignored and the block to add), project-owned files changed (always an empty list, or the preview fails), ordered steps, blockers.
