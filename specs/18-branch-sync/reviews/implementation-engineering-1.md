# Implementation review 1: engineering, tests and documentation

- Reviewer: Claude Opus (same provider as the author; not an independent cross-provider review)
- Date: 2026-10-05
- Scope: `git diff origin/main...HEAD` on `feat/18-branch-sync` (commits `3b2faf5`, `5f1828e`): `tools/spec_workflow/branch_sync.py`, the `run.py`, `autonomy.py`, `draft_pr.py`, `ledger.py` and `tools/ballast` changes, their tests, `templates/policies/spec-kit-workflow.md`, README, `run.py` docstring, `ledger-schema.md`, ADR-0005 and TECHNICAL-SPEC. Reviews: engineering, tests and documentation. Security is reviewed separately.
- Design read: spec.md, decisions.md (DEC-0001..0007 and the deferred wording I1–I6 and T1, applied as resolutions), research R1–R15, contracts/branch-sync.md.
- Gates run (foreground, Git 2.53.0, Python 3.13):
  - `uvx ruff check`: passed. `uvx ruff format --check`: 176 files already formatted.
  - `uv run --no-project --isolated --python 3.13 --with pyyaml python -m unittest tests/<module>.py`: `test_branch_sync` 66 OK, `test_spec_workflow` 123 OK, `test_autonomous_run` 56 OK, `test_autonomy` 103 OK, `test_draft_pr` 83 OK, `test_agent_run_ledger` 69 OK, `test_doctor` 33 OK, `test_governance` 2 OK.
  - Not run: the full suite in one invocation, and the four tests that need systemd, Codex or the Spec Kit CLI.
  - Two behaviors were confirmed with a throwaway probe test in the scratchpad that uses the `Scratch` harness (E-01, E-02). It is not committed.

## Summary

The core is sound. The classification order, the R5 mutation order (pre-checks, write-ahead record, lease push, `read-tree`, CAS `update-ref`), the P-04 restore, recovery rows 1, 3, 3b, 4, 5, 6 and 7, the base-branch and feature-branch rules, and the protected-input recheck on every HEAD change all match research R4/R5/R9/R15. The tests use real Git against a bare stand-in remote, and nearly every acceptance criterion has a test that fails when the behavior breaks.

Four medium findings need a change before merge:

- an unrecorded or misleading outcome for `ballast run start` without a feature directory;
- the wrong cause at `start` during a rebase;
- stale-evidence records lost when a sync is kept but blocked;
- recovery row 5 reading attributes from the feature commit.

Row 2, the one recovery row that pushes from a record, also needs a test. The rest is low-severity simplification and documentation.

## Findings

### Medium

**E-01: implementation bug, FR-009 (item 4). `ballast run start` without a valid `-i feature_directory` gives an unrecorded or misleading outcome.**
- Location: `tools/spec_workflow/run.py:963` (`_option_feature` may return None or an invalid value); `tools/spec_workflow/branch_sync.py:1700-1704` (`record` raises without a feature) and `:1796-1818`.
- Evidence (probe): an up-to-date branch gives `blocked internal-error "not recorded"`. A behind branch gives `not-feature-branch`, but the event is silently not recorded: `ledger.read` returns `[]`. That violates FR-009 ("each check MUST record one outcome") and the policy's "Every check records one `branch_sync` event". `_Sync.__init__` also maps a value that fails `FEATURE_PATTERN` to None, so the same happens with a mistyped directory.
- Proposed behavior: `ballast-feature` declares `feature_directory` as `required: true`, and without it Spec Kit would prompt for it. `run.py start` (human-gated) should refuse during argument validation, before the tamper check and the sync, with exit 2: `start needs -i feature_directory=specs/<issue>-<slug>`. Autonomous `start` already requires a feature. One invalid value gets the same refusal (`FEATURE_PATTERN.fullmatch`), and a repeated `-i feature_directory` is refused too, so the check and Spec Kit cannot read different values. The not-feature-branch path for "no Issue number" then cannot happen through `ballast run`, so keep it only as defense.
- Required action:
  - Add the refusal and a `BranchSyncCallTests` case: start without the input, and with `feature_directory=nope`, returns 2, never calls `synchronize` and writes no pin.
  - Update the "or no feature directory" policy row (`templates/policies/spec-kit-workflow.md:689`), ADR-0005 line 19 and research R15 to say `start` refuses instead.

**E-02: implementation bug, AC-009. At `start`, a rebase or merge in progress is reported as `wrong-branch` with an unusable recovery.**
- Location: `branch_sync.py:702-716` (`execute` calls `intended_branch()` before `in_progress()`) and `:749-754`.
- Evidence (probe, a conflicted `git rebase` on the feature branch, then `check(starting=True)`): `wrong-branch | HEAD is detached | git switch <pinned>, then your ballast run start command`. `git switch` refuses while a rebase is in progress, and `<pinned>` is a placeholder because a new run has no pin. R4 puts `in-progress` (step 3) before identity (step 4). `resume` and `continue` follow that order because they read the pin, not HEAD. `start` does not, because it needs HEAD to choose the lock key.
- Required action:
  - In `intended_branch`, when `starting` and `current_branch()` is None, call `self.in_progress()` before stopping with `wrong-branch`. `resolve_git` has already run.
  - For a detached HEAD at `start` with nothing in progress, use a recovery that names no pin, for example `git switch FEATURE-BRANCH, then {rerun}`, with `feature_branch()` as the suggestion.
  - Add a test: a conflicted rebase, then `check(starting=True)` reports `in-progress` "a rebase is in progress".

**E-03: implementation bug, AC-018/FR-015. Stale-evidence records are lost when the synchronization is kept but the outcome is blocked.**
- Location: `branch_sync.py:1340` (`find_overlap` runs before `finish`/`recheck`), `:1731` (the overlap file is written only for `synchronized`) and `:677-698` (`blocked()` drops `overlap`/`stale_*`).
- Evidence: a base that changes both a protected input and a file the feature's plan covers rebases the branch, sets `self.overlap`, and then `recheck` blocks `protected-input`. The sync stays (AC-016), but neither the event nor `branch-sync/<event>.json` records the overlap. After `ballast trust`, the next check is `up-to-date` and never computes it. The Draft PR therefore never shows the staleness. The same loss happens to the DEC-0005 completions, recovery rows 4 and 5, which never call `find_overlap`.
- Required action:
  - Write the overlap file, and the `overlap`/`stale_*` event fields (the ledger schema does not forbid them on `blocked`), whenever HEAD changed and the change was kept. Today that is `synchronized` or `protected-input`.
  - For rows 4 and 5, either store `old_base` in the write-ahead record and compute the overlap on completion, or state the limitation in research R11 and the policy.
  - Add a test: a protected-input change plus an overlap keeps a stale record.

**E-04: spec violation, research R2 and ADR-0005 ("an agent's `.gitattributes` on the feature branch is never consulted"). Recovery row 5 replays with `--attr-source` set to the feature commit.**
- Location: `branch_sync.py:1180` (`self.replay(old, new, local, pushed=new)`) and `:1404` (`attr_source=new_base`).
- Evidence: in row 5, `new_base` is the record's `new_head`, which is the pushed feature commit, not the fetched base. `merge=union`, `binary` and `text`/`eol` therefore come from the feature branch's `.gitattributes`, against the stated invariant. A merge driver still runs only from the operator's global configuration, so the impact is merge semantics, not code execution. Security review should still note it.
- Required action: give `replay` a separate `attributes` argument (default `new_base`), and pass `self.base_after` from row 5. Extend `test_conflicting_commit_after_a_pushed_sync`, or add a test, that asserts the row-5 `merge-tree` argv carries `--attr-source=<fetched base>`.

**T-01: missing test, R5 recovery row 2. The only recovery row that pushes from a record has no test.**
- Location: `branch_sync.py:1154-1160`.
- Evidence: research calls row 2 "not reachable with push-first; cheap to cover", but the code pushes with a lease and no test reaches it. A regression in its condition (`records_push`, `published == published_old`) could push a fast-forward record, which is the P-01 invariant.
- Required action: build the state by hand. Write a record `{old, new, published_old=P}` with `new` a replayed commit, move the local branch to `new` with `git update-ref`, and leave the remote at `P`. Assert `synchronized`, `recovered`, `pushed`, and published equal to `new`. Add the negative case: the same state with `published_old == new_head` must not push, and must fall through to row 7. Alternatively, delete row 2 and let row 7 report it, but then update research R5 and the invariant text.

### Low

**E-05: hardening (item 5). The throwaway allow-list is an `assert`.**
- Location: `branch_sync.py:620-621`.
- Evidence: under `-O` the check disappears. In practice the launcher runs `python3 -I -S`, and `-I` ignores `PYTHONOPTIMIZE`, so there is no environment path to `-O` today. ADR-0005 nevertheless states "The runner refuses any other command", and that is the gc-safety invariant of R3a.
- Required action: `if args[0] not in THROWAWAY_COMMANDS: raise RuntimeError(f"git {args[0]} is not allowed in the throwaway")`, which becomes `internal-error`. Do the same for `self.bare is None`. The other `assert`s are type narrowing and can stay. `test_runners_harden_every_command` can add one negative call.

**E-06: deviation from research R8. A recorded base commit that is no longer in the object store falls back to `merge-base`.**
- Location: `branch_sync.py:1350-1360`.
- Evidence: R8 says that when `base_commit` is neither an ancestor of the new base nor of HEAD, or is unknown, the check blocks `diverged`. The `else` branch treats "recorded but missing locally" like "never recorded" and uses `merge-base`. After a force-pushed base whose old commit was pruned, that can replay rewritten-away base commits, which the spec's "base rewritten" edge case forbids. The case is rare: the recorded commit is usually reachable from HEAD.
- Required action: when `recorded` is set but `not self.has(recorded)`, block `diverged` (`base-rewritten`), or document the fallback in R8.

**S-01: simplification. `new_pin` duplicates `pin`.**
- Location: `branch_sync.py:527`, `:780`, `:937`, `:1537`, `:1666-1668`.
- Evidence: for a continuation, `new_pin` is `dict(pin)`, and every later write sets the same key in both. For other runs it is unused.
- Required action: drop `new_pin`. In `finish`, write `self.pin` to `_pin_path(root, run_id)`, which is already the continuation's new ID. Keep `save_pin` a no-op for continuations.

**S-02: simplification. A second source of truth for causes and outcomes.**
- Location: `branch_sync.py:66-81` against `ledger.py` `SYNC_CAUSES` and `SYNC_OUTCOMES`.
- Evidence: `OUTCOMES` is unused. `CAUSES` is used only by two tests.
- Required action: delete both and use `ledger.SYNC_CAUSES` (sorted where order matters).

**S-03: simplification. Two copies of the same escaping helper are added in this diff.**
- Location: `branch_sync.py:279-281` (`_text`) and `draft_pr.py:503-504` (`_printable`).
- Required action: keep one. `branch_sync` already imports `draft_pr`, so it can use `draft_pr._printable` or a renamed public helper.

**S-04: simplification. The JSON file helpers duplicate `autonomy`.**
- Location: `branch_sync.py:366-393` against `autonomy._read_bytes`, `autonomy._write_bytes` and `autonomy.write_json` (atomic `mkstemp`, `fsync`, replace, real-directory check). `_url` (`:243`) repeats `autonomy._push_url`'s scheme rule. That one is acceptable as the test seam.
- Required action: reuse `autonomy.write_json` (catch `AutonomyError` where `OSError` is caught now) and an `O_NOFOLLOW` reader. Keep the extra `chmod 0700` only if it is needed for the pre-existing `draft-pr/` directory, and say so in a comment.

**S-05: simplification. Block metadata travels through side channels.**
- Location: `branch_sync.py:1594-1606` (`block.retryable = ...  # type: ignore`) and `:696-697` (`retryable=getattr(...)`, `interrupted=block.detail == "interrupted"`).
- Required action: give `_Block` `retryable: bool | None = None` and `interrupted: bool = False` fields, and set `interrupted=True` in the `KeyboardInterrupt` handler instead of inferring it from the detail text.

**T-02: weak tests named by the implementer, and one gap.**
- Q12/AC-010 after `fetch-failed` (`test_base_that_cannot_be_fetched_is_never_guessed`, `tests/test_branch_sync.py:841`): after `moved.rename(self.s.remote)`, assert `self.s.check().outcome == "synchronized"` before switching the pin to `develop`.
- Q45 (`:1518`): assert the recovery for each subtest: `main` gives `git switch -c 18-x`, and `develop` gives `git pull --rebase origin develop, then ...`. The two `diverged` paths have different recoveries, and the test cannot tell them apart now.
- Q47 (`:1301`): assert that the killed run recorded no `branch_sync` event, so `self.s.events() == []` before the rerun. Also assert the rerun's outcome is not `recovered`. Row 1 clears without a HEAD change, so P-05 relies on the launcher.
- Q27 (`:1176`): the two checks run in threads of one process. That is still a real `flock` contention, because each check opens its own file description, so it exercises AC-020. Cross-process exclusion is covered by Q26 and cross-clone exclusion by the lease (Q16). No change is needed. A one-line comment saying why threads suffice would help.
- No test covers `internal-error` "no committer identity" (R2, F-12). Add one with `GIT_CONFIG_GLOBAL` pointing at a file without `[user]`, `GIT_COMMITTER_NAME`/`EMAIL` and `EMAIL` unset, and `user.useConfigOnly=true`. Expect `internal-error` with the `no-committer` recovery and an unchanged checkout.
- AC-009 lists cherry-pick, revert and bisect, but only `MERGE_HEAD` (and `index.lock`) are exercised. A loop over `IN_PROGRESS_MARKERS` that writes each marker would cover the rest cheaply.

**D-01: documentation. ADR-0005's list of checkout commands is incomplete.**
- Location: `docs/adr/0005-launcher-branch-synchronization.md:21`.
- Evidence: the code also runs `remote get-url origin` (scheme only, `branch_sync.py:885`) and `config --list --name-only -z` / `config --get-regexp` (`:655`, `:796`). The contract lists `remote get-url` and `--get-regexp`. The list also names `ls-files`, which the module never runs.
- Required action: align the ADR with the contract: add `remote get-url` (scheme only) and `config --list --name-only` / `--get-regexp` (read as data), and drop `ls-files` or keep it as "may".

**D-02: documentation. A few statements become accurate only with the fixes above.**
- `templates/policies/spec-kit-workflow.md:671`, "Every check records one `branch_sync` event": true after E-01.
- `:689`, the `not-feature-branch` row "or no feature directory": replace it with the `start` refusal from E-01.
- The `wrong-branch` row says `git switch {pinned}`. Add the `start` case from E-02.
- The `run.py` docstring ("When the branch cannot be updated safely it changes nothing") omits the two documented exceptions (`protected-input`, a block after a push). Add "(see the policy for the two exceptions)".
- No further action needed:
  - The policy table covers every cause and every `RECOVERY` key, which `test_every_cause_and_recovery_is_documented` checks.
  - `ledger-schema.md`'s cause list and per-outcome rules match `ledger._validate_branch_sync`.
  - README and TECHNICAL-SPEC are accurate.

## Checked and found consistent

- **R4 order**: lock, then `git`/shape, `in-progress`, identity/pin, `ls-remote`/fetch, record recovery, kind, published branch, ancestor test, base/other/feature, dirty, replay, mutation, recheck, overlap. The exceptions are E-02 and `resolve_git` running before the lock. The latter is harmless: `git-unavailable` is reported ahead of `busy`.
- **Recovery table**: the order of rows 1, 3, 3b, 4, 5, 6 and 7, the `cat-file -e new_head` pre-probe, and the P-01 invariant (`records_push` gates rows 2 and 5) match R5. `test_fast_forward_record_never_pushes` covers the invariant.
- **Mutation order**: pre-checks (HEAD and branch still `OLD`, clean, ignored-path intersection, `read-tree --dry-run`, protected diff), then the write-ahead record, a lease push only when `new != observed`, `read-tree -m -u`, and CAS `update-ref`. The P-04 restore runs only while the index and worktree hold nothing but the sync's output.
- **Recheck**: `recheck` uses the launcher's comparison against `trusted.json` whenever `head != head_before`, which covers replay, AC-015, the base fast-forward and record completions. A missing baseline fails closed.
- **Branch rules**: `autonomy.is_feature_branch` is the one predicate (`test_eligibility_uses_the_feature_branch_rule`, Q28). The base branch only fast-forwards and never pushes (Q29).
- **`continue`**: it records a blocked check under the source run, leaves no phantom archive or pin, and changes no human decision (`test_blocked_continue_changes_no_record`).
- **Feature identity at `resume`**: `_run_feature` reads `.specify/workflows/runs/<id>/inputs.json`. That path is excluded from the launcher's digest, but `agent.py._protected_state` hashes it around every agent step, so only `SPECIFY_WRITABLE` is writable, and a change leaves the tamper marker that `run.py` refuses on. #17's `draft_pr.identify` relies on the same protection. No finding here, but the security review should confirm it.
- **Requirement coverage**:
  - AC-001: Q1, `test_resume_runs_the_engine_on_the_new_base`.
  - AC-002: Q2. AC-003: Q1. AC-004: Q3, `test_start_synchronizes_before_the_first_step`.
  - AC-005: `test_continue_checks_then_pins_the_continuation` and the `continue` rerun in `RecoveryTests`.
  - AC-006: Q5. AC-007: Q7. AC-008: Q9. AC-009: Q10, plus E-02 and T-02. AC-010: Q5, Q7, Q10 and Q34, plus T-02.
  - AC-011: Q13. AC-012: Q14. AC-013: Q15, Q16. AC-014: Q17. AC-015: Q20, Q22. AC-016: Q23, Q21.
  - AC-017: Q24, Q36, Q39, `test_runners_harden_every_command`. AC-018: Q25, `test_draft_pr` T035, plus E-03.
  - AC-019: Q26. AC-020: Q27, Q16. AC-021: Q28, Q44.
  - FR-001 and FR-010: `BranchSyncCallTests`. FR-009: `test_agent_run_ledger`, plus E-01. FR-011: Q13. FR-013: Q33. FR-014: `DocumentationTests`. FR-016: Q26.
- **Simplicity (item 3)**: most of the 68 KB is the recovery table, the fixed recovery texts and their docstrings, which the design requires. Apart from S-01..S-05 there is no dead code beyond the unused `OUTCOMES` and `_url`'s unused `root` parameter, which the seam explains. No speculative abstraction.

- Verdict: APPROVE WITH CHANGES
