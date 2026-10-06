# Test review: adaptive `ballast init` (implementation recheck after fix cycle 3)

- Feature: `specs/13-adaptive-init`
- Review: `implementation-recheck` (kind `test`), after fix cycle 3 of 3. This is the last review, and no fix cycle remains.
- Reviewer: claude-opus-5-5 (same provider as the author, so independence is reduced)
- Base: `11134f1`; head `bd6ac47` plus the run record

## Scope of this recheck

Fix cycle 3 received no findings, only the failing `[checks]`. `git diff bd6ac47` changes only the run record. The tests under review are therefore unchanged since the earlier cycles: `tests/test_init.py` and `InitBootstrapTests` in `tests/test_ballast.py`.

## What was checked

- **Coverage.** I mapped AC-001..AC-034 and SC-001..SC-006 to assertions in `tests/test_init.py` and `tests/test_ballast.py`.
  - Only the network and setup's external commands are faked.
  - These parts are real: git, ignore rules, symbolic links, an audit hook for process starts, and the launcher preflight after trust.
  - Negative paths assert absent files, no journal, no started process, unchanged bytes and the named stop stage.
- **Gaps from earlier cycles.** These three remain:
  - AC-020 is tested only without a prior installation.
  - SC-002's zero prompts for an established repository is not asserted with a terminal attached.
  - No test covers an evidence file that is itself a link pointing outside the root.
- **Execution evidence.** The runner's cycle-3 unit run exited 1, and the fix input's output tail shows 785 tests, 677 errors, 1 failure and 14 skips.
  - The errors come from `outside_temp()` (`tests/test_autonomy.py:89`), which cannot create `~/.local/state/ballast-tests` on a read-only file system.
  - The same failure happened in all four recorded runs, so the new tests have not yet passed in any recorded run.
  - The tests are judged as written.
- **Project testing policy.** `docs/policies/project/testing.md` also requires an end-to-end run on a scratch project for a `tools/ballast` change, and none is recorded. For this feature that run should include `ballast init` on a blank scratch repository and on an established one. Only the operator runs `ballast trust`, so no fix cycle could have supplied it.

## Conclusion

The tests cover the acceptance criteria with real seams and meaningful negative cases, and the remaining coverage gaps are low. Two pieces of evidence are still missing: a passing gate run, and the end-to-end scratch-project run. All fix cycles are used and the checks still fail, so the run stops for a human. Both runs belong in the PR before merge.

<!-- ballast-findings: begin -->
## Findings (recorded from the review draft)

- F-001 (low, missing-test, open): Still present: AC-020 is tested only without a prior installation. No rerun forces setup's fetch or switch to fail over an existing install and asserts that the prior tree and record are kept.
- F-002 (low, missing-test, open): Still present: SC-002's zero prompts for an established repository is not asserted with a terminal attached and a failing input() stub.
- F-003 (low, missing-test, open): Still present: no test covers an evidence file that is itself a symbolic link pointing outside the root. The code handles that case with O_NOFOLLOW and fstat.
- F-004 (medium, missing-test, accepted-provisionally): docs/policies/project/testing.md requires an end-to-end scratch-project run for a tools/ballast change, and here it should include ballast init on a blank and an established repository. The unit gate has also never passed in this sandbox. Only the operator runs ballast trust, so the PR must show both runs before merge.
<!-- ballast-findings: end -->

## Resolution

- F-001: accepted (low). Keeping the prior installation when setup fails is setup's own ADR-0007 behavior, covered by `tests/test_setup.py` (#14); init only calls `Setup.main` in process and maps its exceptions to a stop at `install`, which `test_a_failed_install_names_the_stage` covers.
- F-002: fixed. `test_an_established_terminal_run_asks_nothing` attaches a terminal and makes `input()` fail.
- F-003: fixed. `test_a_linked_evidence_file_outside_the_root_is_never_read` links `pyproject.toml` outside the root: skipped as `symbolic link`, its description never used.
- F-004: resolved. The full gate passes on the host, and the networked end-to-end run on a blank and an established (cloned public) repository is recorded in [e2e.md](e2e.md). It found one wording defect, fixed test-first (`test_no_check_at_all_is_named_as_missing`).

Gates on the host after the rebase onto `origin/main` (with #82): `uvx ruff check && uvx ruff format --check` pass; the full suite `uv run --no-project --isolated --python 3.13 --with pyyaml python -m unittest tests/test_*.py` passes (counts in [convergence.md](convergence.md)). The networked end-to-end run is in [e2e.md](e2e.md).

- Verdict: approved
