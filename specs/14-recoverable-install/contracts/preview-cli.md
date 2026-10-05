# Contract: `ballast preview <ref> [--json]`

A CLI command, run from a project root. It reports what moving the pin to `<ref>` would do and changes nothing in the checkout, its installation, run state, run archives, operator state or `ballast.toml`; only the cache may gain `<ref>` (FR-017, AC-020).

## Arguments and refusals

- `<ref>` must match the CLI's `REF` rule; otherwise exit 2.
- Refuses (exit 2) without a valid pin in `ballast.toml`, with `BALLAST_STANDARD_DIR` set (no cache to preview from), or while `setup-attempt.json` exists (`run ballast setup first`).
- Takes no lock; it opens `checkout.lock` without creating it and refuses when a setup holds it.

## Procedure

1. Fetch and verify `<ref>` in the cache ([cache.md](cache.md)).
2. Read `<ref>/tools/cli.toml` as data: `[cli] minimum`, `[setup] recoverable`, `[runs] resumes`.
3. Build `<ref>` in a disposable project under `$XDG_DATA_HOME/ballast/preview/<random>/` by running its own `tools/setup --project` under `/usr/bin/python3 -I -S`, with `XDG_STATE_HOME` inside the disposable directory ([research R8](../research.md#r8-the-update-preview-is-a-cli-command-that-builds-the-target-in-a-disposable-project)).
4. The "before" side, taken with the same procedure as the "after" side so both describe one set (plan review F-002): when the pinned and target versions are both recoverable, both sides are installation records (the live record when valid and matching the live installation, otherwise the record of a disposable build of the pin); otherwise both sides are walks of disposable builds (every file and link minus `.git`, the seeds, the constitution and `__pycache__`).
5. Compute path impact, ignore impact (read-only `git check-ignore --no-index --stdin` in the checkout) and run compatibility.
6. Delete the disposable directory in every outcome.

A failed build of either side exits 1 naming the side and the target's own setup error; nothing is reported as compatible.

## Human report

```text
Ballast update preview
  pinned     v0.6.0
  installed  v0.6.0
  target     v0.7.0 (recovery guarantees: yes)
  CLI        v0.6.0 meets v0.7.0's minimum 0.1.0

Unfinished runs
  2026-10-05-abc  paused     ballast-run/1  can resume under v0.7.0
  2026-10-04-def  paused     (no format)    cannot resume: finish or discard it before updating

Installed paths
  added    .agents/skills/ballast-new/SKILL.md
  changed  .ballast/spec_workflow/run.py
  removed  docs/policies/old.md
Ignore rules: the current .gitignore covers every installed path
Project-owned files: none would change

To finish the update
  1. Set ref = "v0.7.0" under [standard] in ballast.toml, review and commit it
  2. ballast setup
  3. Review the changed protected inputs: ballast.toml, .ballast/spec_workflow/run.py, ...
  4. ballast trust
  5. Run the project's checks: uvx ruff check; uv run python -m unittest

Blocked: 1 run cannot resume under v0.7.0.
```

When the CLI is below the target's minimum, step 0 is the CLI install line for the needed version and the CLI line says `does not meet`. When the target is not recoverable: `target v0.4.2 (recovery guarantees: no — a failed setup or rollback to this version can leave the checkout without a usable installation)`. When ignore rules must change, the block to add replaces the `Ignore rules` line and becomes a step before `ballast setup`. Step 5 lists `[checks] commands` from `ballast.toml`, or `none configured`.

## JSON (`--json`)

```json
{
  "schema": 1,
  "pinned": "v0.6.0",
  "installed": "v0.6.0",
  "target": "v0.7.0",
  "target_recoverable": true,
  "cli": {"version": "0.6.0", "minimum": "0.1.0", "meets": true},
  "runs": [{"id": "…", "status": "paused", "format": "ballast-run/1", "compatible": true}],
  "paths": {"added": [], "changed": [], "removed": []},
  "ignore": {"ok": true, "not_ignored": [], "block": null},
  "project_owned_changed": [],
  "steps": ["…"],
  "blockers": []
}
```

`installed` is `null` when no installation record exists. `blockers` lists incompatible runs, an unmet CLI minimum and required ignore changes.

## Exit codes

| Exit | Meaning |
| --- | --- |
| 0 | Report produced, no blockers |
| 1 | Report produced with blockers, or a build or fetch failed |
| 2 | Refused before doing anything |
