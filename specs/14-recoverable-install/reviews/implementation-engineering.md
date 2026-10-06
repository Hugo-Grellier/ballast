# Review: implementation (engineering)

- Role: code reviewer (requirement coverage, architecture, failure behavior, data integrity, complexity)
- Agent/model: claude/claude-opus-5-5, the driving agent; reduced independence (same model as the author; Codex unavailable, see the security review)
- Base: `1176309..bf5359c`
- Artifacts: [spec.md](../spec.md), [plan.md](../plan.md), [research.md](../research.md), [data-model.md](../data-model.md), [contracts/](../contracts/), [decisions.md](../decisions.md), ADR-0002, ADR-0007, ADR-0008, `docs/policies/engineering.md`
- Verdict: approved

## What was checked

- **Requirement coverage.** FR-001 to FR-020 each trace to code and a test (see [tasks.md](../tasks.md) evidence and the [test review](implementation-tests.md)). Two narrowings are recorded decisions, not silent drift: DEC-0001 (cache guarantees need the new CLI) and DEC-0002 (a kept installation makes rollback offline).
- **Source authority and single ownership.** Setup is the only writer of the installation record, journal and kept record; the launcher owns `state_dir`, digests, the lock helper and the record reader, which setup loads from the same standard version instead of copying; the CLI owns the cache. Two deliberate mirrors exist, each guarded by a test: the CLI's `operator_state`/`installation` against `launcher.state_dir`/`read_record` (`NotFetchedTests`, preview refusal tests), and `RUN_FORMAT` against `tools/cli.toml [runs] format` (`RunFormatTests`).
- **One entry set (F-002).** `entries(root)` is used by the switch, the record, `current`, `--check`, the worktree and kept copies and validation; stray stage outputs fail validation except `DISCARDED`. The live build (T028) confirmed real Spec Kit 1.0.11 produces no other stray output.
- **Partial failure.** Every exception in staging discards the work area and journal; every exception during the switch rolls back by membership and verifies against `before`; a kill at any point is resolved by the journal (five points plus a kill during rollback, tested); Ctrl-C is a `BaseException` and takes the same paths.
- **Concurrency.** Exclusive/shared `flock` with a re-probe that avoids misnaming a just-finished setup; 20 same-checkout races and 20 same-version fetch races tested.
- **Compatibility.** Projects pinning v0.5.0 or older keep their own setup and launcher; the new CLI verifies their cache once (refetching an unrecorded copy); a record left stale by an older setup is ignored (test `test_stale_record_is_ignored`); `tools/cli.toml` additions are new tables, ignored by older CLIs.
- **Complexity.** No new dependency; no production fault hook (kills replace functions in a wrapper); the kept installation reuses the worktree copy's verification instead of a second mechanism.

## Findings

| ID | Class | Severity | Location | Evidence | Required action |
|---|---|---|---|---|---|
| ENG-001 | implementation bug | medium | `tools/setup` `attempt` | A failure preparing the stage (`git init` raises `CalledProcessError`, a seed copy raises `OSError`) escaped as a bare error, and `CalledProcessError` as a traceback; an `OSError` from a rename mid-switch was rolled back but reported without its stage or "the previous installation was kept" (contract `setup.md`). | Report `stage` / `switch` failures in the contract format; tests. |
| ENG-002 | implementation bug | low | `tools/setup` `finish` | An `OSError` in `finish` after `committed` (record write, kept rename) exits 1 with a bare error although the new installation is in place. The journal stays `committed`, the launcher refuses meanwhile, and the next setup completes it and says so. | Accept; the outcome is safe and self-describing on the next run. |
| ENG-003 | spec ambiguity | low | `tools/setup` `copy_kept` | The plan had no way to rebuild the previous version offline (AC-022): a full build downloads Spec Kit sources. | Resolved by DEC-0002 (kept installation, verified copy). |
| ENG-004 | architecture issue | info | Spec Kit 1.0.11 | Spec Kit writes build timestamps into registries (`.specify/bundle-records.json`, `*.manifest.json`, `workflow-registry.json`), so every full rebuild changes trusted inputs and needs `ballast trust`, as before this feature. Reused installations (kept, worktree copy) are byte-identical and need none. | None; noted for the README's "trust after setup" guidance, which already holds. |

## Resolution

- ENG-001: fixed in `bf5359c`; `RecoverableSetupTests.test_switch_and_stage_failures_keep_the_previous_installation` failed before and passes after (exit 1, `setup: switch failed: …` / `setup: stage failed: …`, snapshots unchanged).
- ENG-002: accepted (reason above).
- ENG-003: resolved by DEC-0002.
- ENG-004: no action.
