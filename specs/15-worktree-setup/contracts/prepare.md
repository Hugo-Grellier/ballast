# Contract: `tools/setup --prepare`

Run by the CLI only (see [cli-and-launcher.md](cli-and-launcher.md)), from the pinned, verified standard, as `/usr/bin/python3 -IS <standard>/tools/setup --project <root> --prepare`. It never downloads, never runs `uvx`, `patch` or Spec Kit, and never falls back to a full installation. Decisions: [research.md](../research.md) R4 to R8; entities: [data-model.md](../data-model.md).

## Order

1. Resolve operator state (`launcher.state_dir`); failure → refuse as setup does.
2. Under a shared, non-blocking checkout lock, no journal and an installation current for this ref and fingerprint → print `nothing to prepare: …` and exit 0, so a command started with the first one proceeds even while the first runs its launcher (plan review F-001). Then take the exclusive checkout lock; held → refuse naming the holder and its mode.
3. Journal present: `mode` `prepare` → recover ([R7](../research.md#r7-recovering-an-interrupted-preparation)) and print the outcome; when recovery finished a committed attempt at the current fingerprint, exit 0 here (the installation is complete). Any other mode → refuse.
4. `in-progress` marker → refuse naming `ballast discard-runs`.
5. The live installation is current for this ref and fingerprint (`Setup.current`) → print `nothing to prepare: this checkout is already installed for <ref>` and exit 0, so a second command started together with the first reaches the launcher (plan review F-001).
6. Any part of an installation present (`Setup.live_entries`, which excludes entries holding a tracked file, F-002) → refuse naming `ballast setup`.
7. `check_links(PARENTS)`, `check_ignored()` as setup.
8. Walk candidates in order ([data-model.md](../data-model.md#candidate-source)); for each rejected one print `skipped <path>: <reason>`. None verifies → discard the stage (and `.ballast/` when the attempt created it), remove the journal, refuse; `<n> checked` counts the candidates walked.
9. Remove a pre-existing `trusted.json` in this worktree's state, printing that it did.
10. Validate, switch, verify, commit and finish exactly as setup (ADR-0007), without creating the constitution.
11. Print the result and exit 0.

## Output (stdout)

```text
nothing to prepare: this checkout is already installed for v0.7.0                             # alone, exit 0 (F-001)
recovered an interrupted preparation: no installation was in place before it; none is now     # only after a recovery
skipped /home/op/repo: it is for v0.6.0, not v0.7.0                                              # one line per rejected candidate
removed a trust baseline recorded before this installation                                     # only when one existed
Prepared the v0.7.0 installation from /home/op/repo-wt3 (verified, nothing downloaded).
Review this worktree's protected inputs, then run `ballast trust`.
```

## Refusals (stderr, exit 2, `setup: refusing: <reason>. Next: <action>`)

| Case | Reason | Next |
| --- | --- | --- |
| Lock held by setup or preparation | `another ballast <setup\|preparation> (PID p, started t, ref r) holds this checkout` | `wait for it to finish, then rerun the command` |
| Lock held by a launcher command | existing text | existing text |
| Non-prepare journal | `setup did not finish in this checkout` | `run \`ballast setup\` to recover` |
| `in-progress` marker | `an agent step did not finish` | `review the checkout, then run \`ballast discard-runs\`` |
| Installation present | `this checkout already holds an installation (<setup --check status>)` | `run \`ballast setup\`` |
| No candidate verifies | `no verified installation of <pin> with this ballast.toml on this machine (<n> checked)` | `run \`ballast setup\` once here (it may download); later worktrees at this pin are then prepared from it` |
| Ignore rules / links | existing setup text | existing setup text |

Stage, validation, switch and rollback failures keep setup's exit 1 messages; a stage whose record differs from the record of the copy that verified fails with `validate stage failed: the stage changed after it was verified at <path>` (security review SEC-003).

## Guarantees

- Network: none (no `urllib`, no `uvx`).
- Links: the copy opens every directory on both sides with `O_NOFOLLOW` and creates every file with `O_EXCL`; a candidate reached through a linked directory is rejected; copied modes drop set-id and group/world write bits; git runs with `core.fsmonitor` disabled (security review SEC-001, SEC-002).
- Writes, in this worktree only: the work area under `.ballast/setup/`, installed entries, and this worktree's operator state (`setup-attempt.json`, `setup-holder.json`, `checkout.lock`, `installation.json`, deletion of a stale `trusted.json`).
- In another checkout: opens its existing `checkout.lock` shared, reads its records and installed files. Writes nothing there; a candidate whose `checkout.lock` file is absent is rejected with `it has no checkout lock` rather than creating one (F-004).
- Never reads any `trusted.json`; never copies `LOCAL_STATE`, `.specify/workflow-state` or anything outside `record.entries`.
- `ballast setup` recovers a `prepare` journal by the same rules and then runs a full setup.

## `--check` and full setup

Unchanged, except: `validate()` writes `executable` into every new record, and `copy_verified` compares executable bits whenever the record lists them (so `ballast setup`'s primary copy gains the check).
