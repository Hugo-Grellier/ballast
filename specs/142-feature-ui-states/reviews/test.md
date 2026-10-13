# Test review: Declare UI states per feature (implementation recheck)

- Review: implementation-recheck, test, after fix cycle 3 (the last; no cycle remains)
- Reviewer: claude/claude-opus-5-5, fresh context, independent of the author and fix steps
- Run: Autonomous `864d9151`; this verdict is agent-provisional
- Diff: `tests/test_packet.py`, `tests/test_governance.py` and `acceptance-evidence.json` against `dfa191c`

## The fix

Cycle 3 had no review findings. Its only input was the `[checks]` test command, which timed out for the third time in a row. The fix step changed no tracked file. No test, source or decision file is newer than the cycle 2 reports, so the test files are the same ones the cycle 2 recheck reviewed.

## Whole-change recheck

- Every test ID in `acceptance-evidence.json` exists in `tests/test_packet.py` or `tests/test_governance.py`, and each criterion AC-001 to AC-019 maps to at least one test.
- The assertions prove the criteria:
  - exact section lines and the criterion-row text with the agent label (AC-001, AC-010, AC-014);
  - exact fixed reasons with the source prefix (AC-002 to AC-004, AC-011, AC-013);
  - another feature's clashing and invalid file (AC-005, AC-009);
  - a different working-tree copy (AC-006);
  - each split of the 50-entry limit (AC-012);
  - a hostile name (AC-015);
  - unchanged evidence states with no file, a valid file and an invalid file (AC-016);
  - the documentation assertions (AC-017 to AC-019).
- The negative paths are covered:
  - every entry rule for both sources;
  - invalid TOML, non-UTF-8 bytes and files over 1 MiB;
  - an extra top-level key;
  - the repository reason taking precedence.
- `ReviewConfigTests` loops that do not commit still keep cases with the same reason apart.
- No existing assertion was weakened. Only `ReviewConfigTests` and `UiStateTests` changed their expectations, as T004 and T010 allow (FR-018).

## Checks I ran

- `uvx ruff check` and `uvx ruff format --check`: passed.
- `python -m unittest tests/test_governance.py`: 23 tests, OK. This covers AC-017 to AC-019.
- `python -m unittest tests/test_packet.py tests/test_governance.py`: 101 tests in 32 s, 83 failures, 27 errors. Each `PacketCase` I inspected stops at `git-untrusted` from the guard `git` on `PATH` and reads `pending/no-pr`. I could not rerun with a system `git`: this session cannot get the approval that needs.

## Evidence gap

The testing policy needs observed evidence for each criterion. AC-001 to AC-016 rely on `tests/test_packet.py`, and no run has observed that suite passing:

- the cycle 0 feedback check exited 1;
- the checks after cycles 1, 2 and 3 timed out;
- every agent step stops the suite at the git guard.

The suite's short run time and the shape of the failures point to the environment (D-001, D-002), not to this diff. Still, an environmental explanation does not replace a passing run. With no fix cycle left, this gap goes to the human. Before merge, the fast gate has to pass from the operator's terminal or CI.

<!-- ballast-findings: begin -->
## Findings (recorded from the review draft)

- F-001 (medium, missing-test, accepted-provisionally): No run has observed tests/test_packet.py, the evidence for AC-001 to AC-016, passing. The feedback checks after cycles 1-3 timed out and every agent step stops the suite at the git guard. The cause looks environmental (D-001, D-002), but no fix cycle remains. A human must see the fast gate pass in the operator's terminal or CI before merge.
- F-002 (low, missing-test, open): FR-014 (no new program or GitHub call) has no executable assertion on the git/gh call set. It is not an acceptance criterion; by reading, the only new read is a cat-file through the existing helper.
<!-- ballast-findings: end -->
