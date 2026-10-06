# Data model: Prepare a new worktree on first Ballast use

Extends [feature 14's data model](../14-recoverable-install/data-model.md). Only additions and new rules are listed; every other field, location and transition is unchanged. Decisions are in [research.md](research.md).

## Locations

| Data | Location | Writer | Change |
| --- | --- | --- | --- |
| Installation record | `$XDG_STATE_HOME/ballast/<key>/installation.json` | `tools/setup` | Adds `executable` (R5) |
| Kept record | `…/<key>/kept-installation.json` | `tools/setup` | A kept record written by this version carries `executable` too |
| Setup journal | `…/<key>/setup-attempt.json` | `tools/setup` | Adds `mode`, `source` (R6, R7) |
| Setup holder | `…/<key>/setup-holder.json` | `tools/setup` | Adds `mode` (R7) |
| Trust baseline | `…/<key>/trusted.json` | launcher `trust` only | Removed by preparation only when it predates the worktree (R8) |
| Standard manifest | `<standard>/tools/cli.toml` | the standard | Adds `[setup] prepare` (R2) |
| Run state, in-progress marker, checkout lock | unchanged, per checkout | unchanged | never read or copied across checkouts |

`<key>` is `sha256(resolved checkout path)[:16]`, so every entry above is per worktree.

## Installation record (addition)

```json
{
 "schema": 1,
 "ref": "v0.7.0",
 "fingerprint": "1.0.11 <sha256>",
 "spec_kit": "1.0.11",
 "recorded": "2026-10-06T10:00:00+00:00",
 "entries": [".ballast/spec_workflow", "..."],
 "files": {".ballast/spec_workflow/run.py": "<sha256>", ".claude/skills/ballast-x": "link:../../.agents/skills/ballast-x"},
 "executable": [".specify/scripts/python/setup_plan.py"]
}
```

- `executable`: sorted list of every regular file under `entries` (minus `LOCAL_STATE` and `__pycache__`, as `files`) whose mode has any execute bit. Every listed path is a key of `files` whose value is not a `link:`.
- Readers that predate it ignore it; `schema` stays `1`.

## Candidate source

Not persisted; built per preparation.

| Field | Meaning |
| --- | --- |
| `kind` | `kept` (own or another checkout's), `live` |
| `checkout` | resolved path of the checkout that holds it |
| `path` | `checkout` for `live`; `checkout/.ballast/setup/kept` for `kept` |
| `record` | `installation.json` (live, through `launcher.read_record`) or `kept-installation.json` (kept), read after the shared lock is held |
| `rejected` | `None`, or the reason it was not used |

Order: own kept → primary live → primary kept → each other linked worktree's live, then kept, in `git worktree list` order. A checkout with no `installation.json` holds no live candidate and one with no `.ballast/setup/kept` directory no kept candidate; neither is reported or counted. The first candidate with `rejected = None` after copying is the source.

Rejection reasons (stable text, used in the outcome and tests):

| Reason | Rule |
| --- | --- |
| `its path no longer exists` | Git lists it as prunable or the path is missing |
| `its setup did not finish` | `setup-attempt.json` exists in its state |
| `it has no checkout lock` | its `checkout.lock` file does not exist; preparation never creates one in another checkout's state (F-004) |
| `it is being set up` | its `checkout.lock` cannot be taken shared |
| `it has no installation record` | no valid record (live) or kept record |
| `it is for <ref>, not <pin>` | `record.ref` differs from the pin |
| `it was built for another configuration` | `record.fingerprint` differs (`ballast.toml` bytes, standard content or Spec Kit version) |
| `its record predates file-mode checks` | no `executable` list |
| `it reaches its installation through a symbolic link at <path>` | a directory between the checkout and a recorded entry (for a kept copy, including `.ballast/setup/kept`) is a link |
| `its content differs from its record at <path>` | stage copy digests differ |
| `its file modes differ from its record at <path>` | stage copy executable set differs |
| `it is unreadable: <error>` | any `OSError` while reading or copying |

## Setup journal (additions)

| Field | Values | Meaning |
| --- | --- | --- |
| `mode` | `"setup"` (absent in journals written before this feature means `setup`), `"prepare"` | Which command wrote it |
| `source` | resolved path or `null` | The candidate the stage was copied from (prepare only); informational |

A `prepare` journal always has `before = {}`, `before_ref = null`, `before_record = null`.

## Setup holder (addition)

`{"pid": 1234, "started": "…", "ref": "v0.7.0", "mode": "prepare"}`; `mode` selects `another ballast setup` or `another ballast preparation` in the refusal.

## Manifest addition

```toml
[setup]
recoverable = true
# The first `ballast run`, `ledger` or `intake` in a checkout with no
# installation prepares it from a verified installation on this machine (#15).
prepare = true
```

Absent or not `true` means the version cannot prepare (R2).

## State transitions: worktree installation under `--prepare`

```text
                    ┌───────────────── refuse: "already holds an installation; run `ballast setup`"
                    │
installed? ── yes ──┘
   │ no
   ▼
journal? ── mode=setup ──► refuse: "setup did not finish…; run `ballast setup` to recover"
   │ mode=prepare
   ├── staging ─────────► discard work ──┐
   ├── switching ───────► roll back ─────┤
   ├── committed, same fingerprint ─► finish ─► installed (done, no new copy)
   └── committed, other fingerprint ─► roll back ─┤
   │ none                                         │
   ▼                                              ▼
in-progress marker? ── yes ──► refuse (`ballast discard-runs`)
   │ no
   ▼
current for ref and fingerprint? ── yes ──► "nothing to prepare", exit 0 (F-001)
   │ no
   ▼
installation present (live_entries)? ── yes ──► refuse (`ballast setup`)
   │ no
   ▼
candidates ── none verifies ──► refuse: "no verified installation of <pin> …; run `ballast setup`" (no stage left)
   │ one verifies
   ▼
staging (journal mode=prepare) ─► validate ─► switching ─► verify live ─► committed ─► finish ─► installed
```

Every arrow into `refuse` exits 2 and leaves the worktree as it found it, apart from a completed recovery. A stage or switch failure exits 1, rolled back by today's rules.

## Validation rules (summary)

- Prepare only when nothing of an installation exists (stamp, valid record or any `Setup.live_entries` path, which excludes an entry holding a tracked file, F-002). A live installation already current for this ref and fingerprint is reported as `nothing to prepare` and exits 0 (F-001).
- Accept a source only if all of R4's rules hold; check content and modes on the stage copy, never on the source alone.
- Never write `ballast.toml`, the constitution, `docs/policies/project/`, another checkout's files or its operator state.
- Never read any `trusted.json`; remove this worktree's own only when it predates the worktree (R8).
