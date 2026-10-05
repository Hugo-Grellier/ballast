# Contract: operator state written by setup

All files live in `launcher.state_dir(root)` (`$XDG_STATE_HOME/ballast/<key>/`, mode `0700`), which refuses locations inside the checkout or an agent temp root. Every JSON file is written to a sibling `*.tmp`, `fsync`ed and renamed into place; the directory is `fsync`ed after the rename. Readers treat an unreadable or unknown-schema file as absent, except the journal, whose unreadability is a refusal (`setup-attempt.json is unreadable; inspect it, then remove it to retry`).

## `installation.json` (writer: setup; readers: setup, launcher, CLI)

```json
{
  "schema": 1,
  "ref": "v0.6.0",
  "fingerprint": "1.0.11 <sha256>",
  "spec_kit": "1.0.11",
  "recorded": "2026-10-06T12:00:00+00:00",
  "entries": [".ballast/spec_workflow", ".claude/skills/ballast-feature-intake"],
  "files": {
    ".ballast/spec_workflow/run.py": "<sha256>",
    ".claude/skills/ballast-feature-intake": "link:../../.agents/skills/ballast-feature-intake"
  }
}
```

- `files` uses the `launcher.digests` value format and covers every installed entry, excluding `LOCAL_STATE`.
- The CLI reads only `ref` and `fingerprint`, as data, and never fails on a missing or unreadable file.
- **Validity**: every reader uses the record only while its `fingerprint` equals the checkout's `.ballast/.setup-version` (stripped); otherwise the record is stale (an older setup ran since) and is treated as absent. `files` also excludes `__pycache__`.

## `kept-installation.json` (writer and reader: setup)

The previous `installation.json`, written when a switch commits and the entries it replaced were kept in `.ballast/setup/kept/` (DEC-0002). Removed before the kept entries are replaced.

## `setup-attempt.json` (writer and reader: setup; existence check: launcher, `--check`, preview)

```json
{
  "schema": 1,
  "attempt": "<random hex>",
  "pid": 12345,
  "started": "2026-10-06T12:00:00+00:00",
  "ref": "v0.6.0",
  "fingerprint": "1.0.11 <sha256>",
  "phase": "staging | switching | committed",
  "work": ".ballast/setup/<attempt>",
  "before": {".ballast/spec_workflow/run.py": "<sha256>"},
  "before_ref": "v0.5.0 or null",
  "before_record": { "...": "the valid previous installation.json, or null" },
  "entries": [{"path": ".ballast/spec_workflow", "new": true}, {"path": "docs/policies/old.md", "new": false}],
  "record": { "...": "the new record, from switching on" }
}
```

Removed when an attempt ends, in every outcome the process survives. Its presence after the process ended is an unfinished attempt.

## `checkout.lock` and `setup-holder.json`

- `checkout.lock`: an empty regular file opened `O_NOFOLLOW`. Setup holds `LOCK_EX`; the launcher holds `LOCK_SH` for `run`, `ledger` and `intake`, kept through `execv`. Neither waits.
- `setup-holder.json`: `{"pid", "started", "ref"}`, written by setup after taking the lock and read only when the lock is busy, to name the holder. A stale file with a free lock is overwritten.

## Not changed

`trusted.json`, `in-progress` and the agent run ledger keep their formats and owners. Setup reads `in-progress` and never writes any of them.
