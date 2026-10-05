# Contract: `tools/setup` (reached through `ballast setup`)

Arguments are unchanged: `tools/setup [--project DIR] [--check]`.

## Order of operations

1. Resolve `state_dir(root)`; refuse (exit 2) when it is unavailable or agent-writable.
2. Take the checkout lock exclusively, non-blocking. Busy: refuse (exit 2) before writing anything, naming the holder (AC-009, AC-015).
3. Recover an unfinished attempt from `setup-attempt.json`, if any, and print one line saying which installation the checkout now holds (AC-004, AC-011).
4. Refuse (exit 2) while the launcher's `in-progress` marker exists (AC-015).
5. If the installation is current and verified: print `nothing changed: <ref> is set up and verified` and exit 0 without writing to the checkout, the cache or the network (AC-012).
6. Refuse (exit 2) when the ignore rules are wrong, as today, before staging.
7. Build the stage (copy from a verified primary checkout, or full build), validate it, switch, verify, commit (see [data model](../data-model.md#setup-attempt)).

The order guarantees that no refusal in steps 1, 2, 4 or 6 writes to the checkout.

## Messages and exit codes

| Exit | When | stderr (one line, then optional detail) |
| --- | --- | --- |
| 0 | Installed, or nothing changed | stdout as today, plus `review the changed protected inputs, then run `ballast trust`` after a change |
| 1 | A stage failed | `setup: <stage> failed: <cause>. The previous installation was kept. Next: <action>` |
| 2 | Refused before writing | `setup: refusing: <reason>. Next: <action>` |

`<stage>` names exactly one of: `fetch <source>` (a Spec Kit source), `spec-kit <command>` (for example `spec-kit extension add intent`), `patch <file>`, `copy from primary`, `validate <check>` (`required outputs`, `ignore rules`, `stage paths`, `filesystem`, `content`), `switch`. `<action>` is fixed per stage: network and source failures say `check network access (ballast doctor), then rerun ballast setup`; Spec Kit and patch failures say `rerun ballast setup; if it fails again, restore the previous pin`; validation failures name the path or rule to fix.

Refusal reasons and their actions:

| Reason | Action |
| --- | --- |
| `another ballast setup (PID n, started T, ref R) holds this checkout` | wait for it to finish |
| `a ballast run, ledger or intake command is running in this checkout` | wait for it to end |
| `an agent step did not finish` | `review the checkout, then run ballast discard-runs` (setup never clears the marker) |
| `the operator state directory … is inside the checkout or a temp directory` | set `XDG_STATE_HOME` elsewhere |
| `installed entries are on different filesystems: <path>` | keep the checkout on one filesystem |
| ignore rules (as today, with the block) | add the block to `.gitignore` |

Recovery lines (step 3): `recovered an interrupted setup: the previous installation (<ref>) is in place`, `… no installation was in place before it; none is now`, or `… the new installation (<ref>) is complete`.

## Worktree copy (AC-014)

A linked worktree copies from its primary checkout only when the primary's `installation.json` fingerprint equals this checkout's fingerprint, the primary's live installation matches that record, and the primary's checkout lock can be taken shared. The copy goes into the stage, never into live paths, and is validated like a build. Otherwise setup prints `full installation: <reason>`, with reason one of `the primary checkout has no installation record`, `the primary installation is for another version or configuration`, `the primary installation differs from its record at <path>`, `the primary checkout is being set up`.

## `--check` (read-only; doctor's `setup-check` probe)

Writes nothing and takes no lock. Prints one state line; exit 0 only for `current`.

| State | Exit |
| --- | --- |
| `current` | 0 |
| `absent` | 1 |
| `interrupted: run ballast setup` | 1 |
| `stale: pinned <B>, installed <A>; restore ref = "<A>" in ballast.toml, or fix the cause and rerun ballast setup` | 1 |
| `stale` (same pin, different fingerprint) | 1 |
| `incomplete: <path>` / `modified: <path>` (live content differs from the record) | 1 |

Older doctors print the state line verbatim, so the new detail reaches them unchanged.

## Never

Setup never edits `ballast.toml`, never writes the trust baseline or clears operator markers, never overwrites `.specify/memory/constitution.md` or anything under `docs/policies/project/`, and never removes a path the project does not ignore (FR-005, FR-018).
