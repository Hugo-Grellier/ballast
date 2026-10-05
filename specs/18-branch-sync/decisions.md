# Decisions

Three proposals came up while planning. Each needs a human resolution at the plan gate before `speckit-tasks`.

## DEC-0001 — Proposal

- **Source**: planning, [research R2 and R4](research.md#r2-rebase-without-running-the-checkouts-git-configuration). The replay needs `git merge-tree --write-tree --merge-base`, available from Git 2.40. It must use a `git` found outside every working tree and temp root, as #17 does. FR-009's ten causes have none for "the launcher cannot run a trusted, capable `git`".
- **Classification**: spec ambiguity.
- **Proposal**: add two blocked causes to FR-009.
  - `git-unavailable`. Its detail is "git not found outside working trees" or "git X.Y is older than 2.40". Its recovery is "put a system git 2.40 or later on PATH ahead of any checkout directory". `ballast doctor` reports the same version floor.
  - `internal-error`, for an unexpected exception, Ctrl-C during the check, or a ledger write that failed. Its recovery is "report it with the run ID, then rerun". It still blocks: no agent starts on a check that did not finish and was not recorded.

  Without these causes, the check would have to report a misleading cause or guess the branch's state, which the spec forbids.

## DEC-0002 — Proposal

- **Source**: planning, [research R9](research.md#r9-protected-input-recheck). SC-002 says that in every blocked case, HEAD, index, working tree and published branch are unchanged. AC-016 says that for a protected-input change "the rebase completes, the trust check runs again on the result, fails closed". Both cannot hold for `protected-input`.
- **Classification**: spec ambiguity.
- **Proposal**: follow AC-016, the more specific criterion. `protected-input` is the one blocked cause that keeps the completed synchronization, and pushes it when the branch is published. SC-002 covers every other cause. Amend SC-002 to say "every blocked case except `protected-input` (AC-016)". The alternative is to refuse before the rebase. `ballast trust` could not then accept the change, because the change would not be in the checkout, and the operator would need a manual rebase. That contradicts AC-016's recovery.

## DEC-0003 — Proposal

- **Source**: planning, [research R5](research.md#r5-updating-the-published-and-local-branch). The spec does not cover a run whose branch is the base branch itself (for example `ballast run start` on `main`). Rebasing local commits onto the fetched base and pushing would push to the base branch.
- **Classification**: spec ambiguity.
- **Proposal**: when the run's branch equals its base, the check only fast-forwards: it never replays and never pushes. With local-only commits, the cause is `diverged`, with the recovery "run the feature on its own branch: git switch -c BRANCH". The edge case "no commits beyond the base: fast-forwarded" is unchanged.

## DEC-0004 — Proposal

- **Source**: plan peer review [plan-review-fable-1.md](reviews/plan-review-fable-1.md) F-04. Any branch a run starts on (for example `develop` or `release/*`) would be rebased onto the base and pushed with a lease; DEC-0003 only guards a run on the base branch itself.
- **Classification**: proposed product change.
- **Proposal**: define which branches synchronization may rewrite. A: only a branch whose name contains the feature's Issue number as a whole segment and that is neither the base nor the repository's default branch; any other branch is never rewritten and, when behind, blocks with a new cause `not-feature-branch`. B: an operator allowlist of branch patterns in `ballast.toml`.

## DEC-0001 — Resolution

- **Status**: accepted by the operator, 2026-10-05 (human resolution at the plan gate).
- **Resolution**: Add the blocked causes `git-unavailable` and `internal-error` to FR-009, as proposed, with the review's corrections (F-08): the data model's `internal-error` row covers a failure after a completed sync, and Ctrl-C during the check exits with the interrupted status.
- **Changed now**: spec FR-009.

## DEC-0002 — Resolution

- **Status**: accepted with changes by the operator, 2026-10-05.
- **Resolution**: `protected-input` keeps the completed synchronization (AC-016) and SC-002 gets the matching exception. With the review's F-02 change: the protected-input trust recheck runs whenever HEAD changed, including the AC-015 fast-forward, and the protected diff is detected before any mutation so the outcome is known in advance.
- **Changed now**: spec SC-002 and FR-008.

## DEC-0003 — Resolution

- **Status**: accepted by the operator, 2026-10-05, broadened by DEC-0004.
- **Resolution**: A run on its base branch only fast-forwards; it never replays and never pushes. Local-only commits there block with `diverged` and the recovery `git switch -c BRANCH`.
- **Changed now**: spec edge cases.

## DEC-0004 — Resolution

- **Status**: accepted by the operator, 2026-10-05: option A.
- **Resolution**: Synchronization rewrites only a feature branch: its name contains the feature's Issue number as a whole segment (for example `18` in `feat/18-branch-sync` or `18-branch-sync`), and it is neither the run's base nor the pinned repository's default branch. Any other branch is never rewritten; when it is behind, the run blocks with cause `not-feature-branch` and the recovery to synchronize it manually or run the feature on its own branch. ADR-0005 states this rule.
- **Changed now**: spec FR-005, FR-009 and AC-021.

## Plan review findings (plan-review-fable-1)

- **Status**: the operator accepted every finding (F-01 to F-14) with the reviewer's fixes, 2026-10-05; the plan gate was rejected for revision and a fresh peer review.
- **AC-011 reading (F-06)**: "the existing block-recovery path" for a blocked Autonomous start is restarting it (`ballast run start --mode autonomous ...`), not `ballast run continue`, which refuses a run with no artifacts ([research R10](research.md)).

## DEC-0005 — Proposal

- **Source**: plan revision 2 ([research R5](research.md)). After a successful push, a later failure (CAS lost, crash, Ctrl-C) leaves the published branch moved while the outcome is blocked, so SC-002 cannot hold.
- **Classification**: spec ambiguity.
- **Proposal**: A: amend SC-002 with a second exception; the next invocation completes the sync from the write-ahead pin. B: push the old commit back with a lease before reporting the block.

## DEC-0005 — Resolution

- **Status**: accepted by the operator, 2026-10-05: option A.
- **Resolution**: SC-002 gains a second exception: a block after a successful push leaves the published branch at the rebased commit, and the next invocation completes the synchronization from the write-ahead pin. No compensating push.
- **Changed now**: spec SC-002.

## DEC-0006 — Proposal

- **Source**: plan revision 2 (F-10). A `resume` of a run with no branch pin (started before #17) has no trusted record of its branch; agents can change HEAD during earlier steps.
- **Classification**: spec ambiguity.
- **Proposal**: A: pin the branch checked out at resume. B: block with `wrong-branch` and the recovery "start a new run".

## DEC-0006 — Resolution

- **Status**: accepted by the operator, 2026-10-05: option B.
- **Resolution**: A `resume` (or `continue`) of a run with no branch pin blocks with cause `wrong-branch` and the recovery to start a new run. The check never pins a branch after the run's first agent step could have changed HEAD.
- **Changed now**: spec edge cases; plan R12 and the contract are updated after the round-2 review.
- **Round-2 review (plan-review-fable-2)**: the operator accepted N-01 to N-12 with the reviewer's fixes and kept DEC-0006 option B, 2026-10-05. N-02 raises DEC-0001's Git floor to 2.41: `--attr-source` is a global option added in Git 2.41.

## Operator delegation (2026-10-05 16:55)

- The operator instructed the agent driving run `0e05c06c` to "do what you think is best, work in autonomy". From this point, workflow gate answers and decision resolutions in this run are made by the agent (Claude) under that delegation, each recorded here with its rationale; they are not individual human approvals. Merging the R2 pull request still requires the operator's explicit approval.

## DEC-0007 — Proposal

- **Source**: plan revision 3 (N-04) and [plan-review-fable-3](reviews/plan-review-fable-3.md). Support partial clones on Git 2.46 or later with a pre-mutation blob-presence check, or refuse them like shallow checkouts.
- **Classification**: spec ambiguity.
- **Proposal**: A: support (Git ≥ 2.46 and blob check). B: refuse with `git-unavailable` and the recovery to re-clone without `--filter`; keep `GIT_NO_LAZY_FETCH=1` as defense in depth.

## DEC-0007 — Resolution

- **Status**: resolved by the agent under the operator's delegation, 2026-10-05: option B.
- **Rationale**: the review reproduced that the support path's printed recovery does not work and that its blob check cannot be proven against GitHub's server behavior; no partial clone is in the qualified 1.0 setup. Support stays described in research as a later extension.

## Round-3 review (plan-review-fable-3)

- **Status**: resolved by the agent under the operator's delegation, 2026-10-05: apply P-01 to P-06 with the reviewer's fixes (P-03 with the half-written-path row and its one-command recovery).

## Plan gate (revision 4)

- **Status**: approved by the agent under the operator's delegation, 2026-10-05.
- **Rationale**: three peer-review rounds (plan-review-fable-1..3) with every finding applied; revision 4 applies P-01..P-06 and DEC-0007. Accepted with it: the partial-clone recovery prints one action (re-clone without `--filter`; SC-003), with the in-place conversion recorded in research; recovery row 3b asks for one manual command after a crash during `read-tree`, a stated exception to contract guarantee 8 that follows the spec's rule never to resume a half-done update on its own. Cross-provider review was not available (Codex quota until 2026-10-10); implementation review should use Codex if available by then.

## Tasks gate (analyze report)

- **Status**: approved by the agent under the operator's delegation, 2026-10-05. The operator acknowledged at 17:15 that the agent would approve the plan gate and continue to merge readiness.
- **G1**: the R2 pre-change approval on file is the agent's, under that delegation; the operator's explicit merge approval is the human R2 approval of the plan and implementation, and the PR says so.
- **Applied now**: U1 (`busy` when HEAD moved before the mutation: research R5 step 1, T022), D1 (T019 depends on T003), D2 (plan Repository Impact), C1 (T011 import check), C2 (T048 covers `ballast run --help`).
- **Deferred to the operator at merge (spec wording only, design unchanged)**: I1 (edge case: an interrupted sync with a write-ahead record is completed by the next invocation, DEC-0005; an operation in progress or a half-written update blocks), I2 (FR-006 gets SC-002's exceptions), I3 (SC-002/FR-006 exception for a branch moved by an outside actor during the check, `busy`), I4 (AC-010 allows the write-ahead record of an unfinished sync), I5 (FR-009 `git-unavailable` also covers shallow checkouts and partial clones, DEC-0007), I6 (AC-011 names the restart path), T1 (A-1: "rebase" means the replay in ADR-0005). Amending the approved spec now would re-record the intent approval as "human user", which an agent decision under delegation is not; implementation follows these resolutions in this file.

## Implement-step interruption (2026-10-05 18:33)

- **What happened**: the headless implement step left its test suite running in the background; the wrapper could not confirm those processes stopped, failed the step (exit 4) and wrote `BALLAST_TAMPERED` with the single reason "(agent processes could not be stopped)".
- **Checked**: no `ballast-agent-*` scope or test process remained; every protected workflow input still matched the operator's trust baseline (no changed input).
- **Resolved by the agent under the operator's delegation**: the implement output was committed (`wip(18)` commit), the marker removed and `ballast discard-runs` run (the run stays archived under the Git common directory as `0e05c06c`). The trust baseline was not re-recorded. A fresh `ballast run` would re-run `specify` over the approved spec, so the feature continues on the documented manual path: remaining tasks, reviews, reconciliation and convergence are done interactively and validated with `artifacts.py --feature`.

## Implementation review fixes (2026-10-05)

Findings of [implementation-security-fable-1](reviews/implementation-security-fable-1.md) and [implementation-engineering-1](reviews/implementation-engineering-1.md), applied by the agent under the operator's delegation. Each test fails with its fix reverted. Tests are in `tests/test_branch_sync.py` unless named otherwise.

- **SEC-001** → `status` uses `--ignore-submodules=dirty`: no `git status` runs inside a gitlink under its own configuration; a changed gitlink still blocks as `dirty`. Test: `test_nested_repository_configuration_never_runs`.
- **SEC-002** → `start` pins `feature` with the branch; `resume` and `continue` take the Issue number (and the feature) from the pin, never from `inputs.json` or the run record. A pin without `feature` blocks as `wrong-branch`, like one without `branch` (DEC-0006). Tests: `test_issue_number_comes_from_the_pin`, `test_unpinned_resume_is_refused`, `test_spec_workflow` `test_resume_takes_the_issue_number_from_the_pin`.
- **SEC-003** → stale-evidence records live in `<state_dir>/branch-sync/stale/<sha256(feature)[:16]>/`; the reader skips non-regular files and files over 16 KiB (also catching `MemoryError`/`RecursionError`), shows the newest 20 entries with "and N earlier", and renders paths as code spans with backticks removed. Data model, R11, the event contract and `ledger-schema.md` updated. Tests: `test_draft_pr` `StaleEvidenceSectionTests` (`test_planted_or_oversized_records_stay_bounded`, `test_paths_are_code_spans_and_bounded`, `test_records_in_the_git_directory_are_ignored`).
- **SEC-004** → both runners set `GIT_NO_REPLACE_OBJECTS=1` and `GIT_GRAFT_FILE=/dev/null`, and add `-c core.commitGraph=false`; `rev-list` names and parent headers are validated before use. Tests: `test_replace_refs_and_grafts_do_not_hide_the_base`, `test_runners_harden_every_command`.
- **SEC-005** → `shape()` refuses `objects/info/alternates` as `git-unavailable` ("alternate object store", one recovery). Test: `EnvironmentRefusalTests.test_alternates_are_refused`.
- **SEC-006 / E-05** → the throwaway allow-list and `bare` check raise `RuntimeError` instead of `assert`. Test: `test_throwaway_allow_list_holds_without_assert`.
- **E-01** → `run.py start` (human-gated) refuses a missing, invalid or repeated `-i feature_directory` with exit 2 before the tamper check, the sync and the pin; policy, ADR-0005, R15 and the contract say so. Test: `test_spec_workflow` `test_start_needs_one_valid_feature_directory`.
- **E-02** → at `start`, a detached HEAD runs `in_progress()` first; the `wrong-branch` recovery then names the feature's branch. Test: `test_start_during_a_rebase_reports_the_rebase`.
- **E-03** → a `protected-input` block carries `overlap`/`stale_*` and writes the stale record; the write-ahead record keeps `old_base`/`new_base`, so recovery rows 4 and 5 report the overlap. Tests: `test_kept_protected_input_sync_keeps_its_stale_record`, `test_completion_from_the_record_keeps_its_stale_record`.
- **E-04** → recovery row 5 replays with `--attr-source` = the fetched base. Test: `test_row_5_reads_attributes_from_the_fetched_base`.
- **E-06** → a recorded `base_commit` missing from the store blocks `diverged` (R8 updated). Test: `test_recorded_base_missing_locally_blocks`.
- **T-01** → recovery row 2 and its P-01 negative. Test: `test_local_moved_but_push_missing`.
- **T-02** → Q12 rerun after `fetch-failed` (`test_base_that_cannot_be_fetched_is_never_guessed`), Q45 recovery per subtest (`test_fast_forward_record_never_pushes`), Q47 no event and not `recovered` (`test_crash_after_a_protected_update_is_caught_by_the_launcher`), `test_no_committer_identity_changes_nothing`, `test_every_operation_in_progress_blocks`.
- **S-01, S-02, S-03, S-05** → `new_pin` removed (`save_pin(final=True)`), `CAUSES`/`OUTCOMES` removed in favor of `ledger.SYNC_CAUSES`, one `draft_pr.printable` helper, `_Block.retryable`/`interrupted` fields. Behavior-neutral; covered by the existing suite. S-04 (reuse `autonomy` JSON helpers) not done: not requested, and the extra `chmod 0700` would need its own review.
- **Docs** → ADR-0005 checkout command list (`remote get-url`, `config --list`/`--get-regexp`, `status --ignore-submodules=dirty`, `ls-files` dropped), environment and refused shapes; `run.py` docstring names the two exceptions; policy pin, requirements, stale-evidence and table rows.

Design changes for the operator to confirm at merge:

- A `resume` or `continue` of a run whose pin has a branch but no feature (any run started before this fix, including #17 pins) now blocks as `wrong-branch` and asks for a new run, instead of reading the Issue number from `inputs.json`. Chosen to match DEC-0006 (fail closed); the review's alternative was an Issue number of none, blocking only when a rewrite is needed.
- A human-gated `ballast run start` now needs `-i feature_directory` on the command line; Spec Kit would otherwise have prompted for it.
- The write-ahead record has two new required fields; no released version wrote records, so none is migrated.
- **Design changes from the fixes, accepted by the agent under the operator's delegation (2026-10-05)**: (1) `resume`/`continue` of a run whose pin lacks `feature` (any run started before this change) blocks `wrong-branch` with "start a new run", failing closed like DEC-0006; (2) a human-gated `ballast run start` needs `-i feature_directory` on the command line (E-01); (3) the write-ahead record gains `old_base`/`new_base`; no released version wrote records, so nothing is migrated. The operator confirms these at merge.
