# Review: implementation (security)

- Role: security reviewer (R2: what `ballast` downloads and executes, the paths `tools/setup` installs, moves and removes, the launcher's trust model)
- Agent/model: claude/claude-opus-5-5, the driving agent. Reduced independence: the same model wrote the change. The cross-provider pass (Codex CLI, read-only sandbox) could not run: `You've hit your usage limit … try again at Oct 10th, 2026`.
- Base: `1176309..bf5359c` (`tools/setup`, `tools/ballast`, `tools/spec_workflow/launcher.py`, `tools/spec_workflow/run.py`, `tools/cli.toml`, tests, README, ADR-0006/0007)
- Artifacts: [spec.md](../spec.md), [research.md](../research.md), [contracts/](../contracts/), [decisions.md](../decisions.md), `docs/policies/security.md`, `docs/policies/project/workflow.md`, constitution BL-INV-001 to BL-INV-006
- Verdict: approved

## What was examined

- **Operator state vs agent-writable checkout (BL-INV-002, #34).** The journal, installation record, kept record, lock and holder live in `launcher.state_dir`, which refuses the checkout and agent temp roots; setup refuses to run when it is unavailable. Everything setup reads from the checkout to decide a move is either a fixed rule (`entries`) or comes from a record in operator state; journal paths are checked (`ATTEMPT` pattern for `work`, `_safe` for entries).
- **Content trust.** Every reused tree (the primary checkout's installation, `.ballast/setup/kept/`, a cached standard version) is used only after its copy hashes exactly to a record held outside agent authority (`copy_verified`, `damage`). A reader that follows a planted link while copying gets content that must still equal the recorded digests, so foreign content is never installed. Bytecode is excluded from cache records, and `tools/setup` sets `dont_write_bytecode` so the doctor probe writes nothing next to the cached launcher.
- **Link safety (plan review F-007).** `check_links` refuses a link at any parent of every entry and of `.ballast/setup` before staging and again for every planned path before switching; renames move the final component, never through it; work-area and kept deletions go through `launcher._remove_tree` (`O_NOFOLLOW` on every parent, `rmtree` with `dir_fd`) or `unlink` for a link; the constitution is created with `O_EXCL | O_NOFOLLOW` after a link check of its parents. Test: `test_linked_work_area_is_refused` (nothing written outside).
- **Removal scope.** Setup removes only entries that the project's ignore rules ignore (`git check-ignore --no-index`), never `ballast.toml`, the constitution, `docs/policies/project/`, run state, run archives or operator markers; snapshot tests cover each.
- **Locking.** `flock` in operator state: setup exclusive, launcher shared for `run`/`ledger`/`intake` (kept through `execv`; `subprocess` closes it for every child, so agents never hold it) and for `trust`/`discard-runs`; lock checked before the journal (F-005, F-006). The kernel releases a dead holder's lock (tests kill holders).
- **Trust model.** The launcher only gained refusals (running setup, unfinished attempt, pinned ≠ installed); `BASES`, `SKIPPED` and the baseline format are unchanged; `.ballast/setup/` is outside `BASES`, so a leftover work area or the kept copy never changes the baseline (AC-007 test). Setup never writes `trusted.json` and never clears `in-progress` (test).
- **What `ballast` downloads and executes.** The repository stays fixed and refs keep the `REF` rule (`preview` too). Fetch publishes tree and record with one rename under a per-version lock; stale extractions are matched by `.fetch-<ref>+`, which no other version can match. `preview` executes only a verified cached version's own `tools/setup`, under `/usr/bin/python3 -I -S`, with `XDG_STATE_HOME` and the working directory inside a disposable directory under `$XDG_DATA_HOME`, never trusted or put in place; it reads the target's manifest and ignore block as data (`tomllib`, `ast.literal_eval`).

## Findings

| ID | Class | Severity | Location | Evidence | Required action |
|---|---|---|---|---|---|
| SEC-001 | implementation bug | low | `tools/ballast` `disposable_build` | The target's setup ran with the checkout as its working directory; a relative write by an older setup would land in the checkout. No such write was found, but nothing prevented it. | Run it with `cwd` in the disposable directory. |
| SEC-002 | implementation bug | low | `tools/ballast` `render_preview` | Run IDs (directory names) and run states come from the agent-writable checkout and were printed raw, so an agent could plant terminal control sequences in the operator's report. | Replace control characters before printing; test. |
| SEC-003 | architecture issue | low | `tools/setup` `roll_back` | If a setup older than this feature runs while a journal from a killed new setup is pending, the next new setup's rollback treats that older installation's entries as "new" and moves them aside. Its verification against `before` fails loudly (`roll back failed`), the journal is removed and the following setup rebuilds. Running an older setup is outside this feature's guarantees (spec Assumptions); the launcher of the new version refuses everything while the journal exists. | Accept; documented here. |
| SEC-004 | architecture issue | info | `tools/setup` `check_links` / `switch` | Between the link check and a rename a surviving agent process could swap a parent for a link. Setup holds the lock, the launcher refuses while it runs, setup refuses while an agent step is unfinished, and agent scopes are killed at step end. | Accept; residual risk. |
| SEC-005 | architecture issue | info | `tools/ballast` `disposable_build` | The target's setup gets the operator's environment, as `ballast setup` does; tokens in it reach a version the operator named but has not pinned. Same authority as updating the pin and running setup. | Accept. |

## Resolution

- SEC-001: fixed in `bf5359c` (`cwd=work`); the read-only snapshots of `tests/test_preview.py` (AC-020) still pass.
- SEC-002: fixed in `bf5359c` (`printable`); regression test `PreviewTests.test_checkout_text_cannot_drive_the_terminal` failed before the fix and passes after.
- SEC-003, SEC-004, SEC-005: accepted with the reasons above; listed for the merge review as residual risks of this R2 change.
