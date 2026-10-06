# Review: implementation (tests)

- Role: test reviewer
- Agent/model: claude/claude-opus-5-5, the driving agent; reduced independence
- Base: `1ce1f9a..HEAD` (`tests/test_setup.py`, `tests/test_ballast.py`, `tests/test_doctor.py`, `tests/test_spec_workflow.py`)
- Artifacts: [spec.md](../spec.md) AC-001 to AC-020 and SC-001 to SC-005, [quickstart.md](../quickstart.md) scenario map, `docs/policies/testing.md`, `docs/policies/project/testing.md`
- Verdict: approved

## Covered criteria

Every AC and SC maps to at least one executable test in the [scenario map](../quickstart.md#scenario-map). Red-before-green was checked by running the new tests against `1ce1f9a` (all 31 new or changed feature tests failed: 246 failures and errors including 200 concurrency subtests) and each review regression test against the commit before its fix.

- **Real seams.** Real `git worktree add` worktrees, real `flock`s held by other processes, real SIGKILL at five points of a preparation, ten concurrent child processes released by a barrier, the real launcher as a subprocess, and the real CLI against a cached standard with a content record (damage detection and declaration read included).
- **No network.** In-process preparations patch `_fetch_source`, `urlretrieve` and `socket.connect` to fail the test; child preparations patch the same plus Spec Kit commands (`FAKE_NETWORK=deny`); CLI children run with only `git` and `python3` on `PATH` and an unreachable proxy. The live run used a network namespace without interfaces.
- **Negative and failure paths.** Other pin, other configuration, added/missing/altered file, execute bit added and removed, record without modes, linked source, unfinished/busy/lockless source, existing stale/modified/partial installation, setup journal, no source, damaged cache, version without the declaration, planted stage link, stage changed after verification, repository configuration that would run a program.
- **Unchanged-state assertions.** `WorktreeCase.prepare()` snapshots every other checkout (tree, run archives, operator state including `trusted.json`) and the worktree's project-owned files around every in-process preparation, so AC-014 is checked in every case, successful or refused.

## Missing or reduced evidence

| ID | Class | Severity | Location | Gap | Action |
|---|---|---|---|---|---|
| TST-001 | missing test | low | AC-005 | `ballast preview` on an uninstalled worktree is not exercised: it builds a disposable project with the target's setup, which needs the network. Its code is unchanged by this feature and does not reach `prepare`. | Accept; stated in the scenario map. |
| TST-002 | missing test | low | AC-016 | "Start, advance and discard a run" is approximated: run state is planted in one worktree, preflight passes there, and the launcher's `discard-runs` removes it; the workflow engine itself is not started offline. Every other worktree's tree and full operator state are compared byte for byte. | Accept; the live run covered `ledger report` after trust. |
| TST-003 | missing test | info | AC-004 | Doctor is checked through its own `_setup_current` and `_trust` functions on the prepared worktree rather than the whole report (whose machine probes need the host). | Accept. |
| TST-004 | missing test | info | SEC-007 | A failing `git worktree list` is not tested (accepted finding). | Accept. |

## Notes

- Full suite at `980511e`: 907 tests, OK, 0 skipped, 709 s; `PrepareConcurrencyTests` takes about 25 s of it.
- A concurrency defect (ENG-004) was caught by the full suite on its first run, which is the purpose of the repeated races; the race loop in `test_one_preparation_per_worktree` was raised from 5 to 10 repetitions after the fix and passed four consecutive isolated runs.
- Existing tests changed only where the behavior intentionally changed: the no-baseline message (FR-008), doctor's remedy (F-005), and `ShimTests.test_runs_the_launcher_of_the_pinned_version`, which now also plants `run.py` so the checkout counts as installed (the planted-launcher check is kept) and asserts the new AC-007 refusal. No test was weakened.
