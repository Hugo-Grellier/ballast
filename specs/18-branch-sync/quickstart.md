# Quickstart: validating branch synchronization

How to show that the feature works. The behavior is defined in the [check contract](contracts/branch-sync.md) and the [ledger event contract](contracts/ledger-branch-sync-event.md); this guide only says what to run and what to expect.

## Prerequisites

- Python 3.11+ and `uv`. Git 2.41 or later on `PATH` outside any checkout.
- No network: the tests use a local bare repository as the remote ([research R14](research.md#r14-testing-approach)).

## Automated gates

```bash
uvx ruff check && uvx ruff format --check
uv run --no-project --python 3.13 --with pyyaml python -m unittest tests/test_*.py
```

New and changed test files:

| File | Covers |
| --- | --- |
| `tests/test_branch_sync.py` (new) | the `synchronize` scenarios below, against real temporary repositories |
| `tests/test_spec_workflow.py` | `run.py` call order; no agent step after a block; exit status 1 and 130; pin ownership; `continue` passes the source branch and base; a blocked `continue` records under the source run and leaves no archive or pin for the new ID |
| `tests/test_autonomous_run.py` | `upstream-sync` block category, restart recovery command, `continue` refused, no decision record; eligibility uses `is_feature_branch` |
| `tests/test_agent_run_ledger.py` | `branch_sync` validation and report |
| `tests/test_draft_pr.py` | stale-evidence entries in the Ballast section; `_Locked` with `wait=0` |
| `tests/test_doctor.py` | Git version floor 2.41 ([DEC-0001](decisions.md), N-02) |

## Scenarios

Every scenario uses a scratch repository with a bare "GitHub" remote, a pinned `[github] repository`, a trusted baseline, a feature directory `specs/18-x` and, unless stated, the branch `feat/18-x`. A fake `specify` records whether it ran: "no agent" means it never ran. "Unchanged" means HEAD, `git ls-files -s`, `git diff-index --cached HEAD`, `git status --porcelain=v1 -z` and the remote branch match their values before the run, and no `rebase-merge`, `rebase-apply` or `MERGE_HEAD` exists. The `.git/index` bytes are not compared ([research R14](research.md#r14-testing-approach)).

| # | Setup | Command | Expect | Covers |
| --- | --- | --- | --- | --- |
| 1 | paused run; base +1 non-conflicting commit; branch unpublished, clean | `resume` | `synchronized`; the fake `specify` sees a HEAD that contains the new base commit; ledger has base before/after and HEAD before/after; printed line shows them | AC-001, AC-003, FR-001, FR-004, FR-005, FR-009 |
| 2 | branch already contains the base | `start`, `resume`, `continue`; then `resume` again | `up-to-date`, HEAD unchanged, one event each; no fetch when both commits are local; the repeat records `up-to-date` again | AC-002, AC-005, SC-005, edge "repeated" |
| 3 | new run on a branch behind the base / the same with the remote unreachable, then reachable | `start` / `start`, then `resume` | synchronized before the first step; pin holds `branch`, `base`, `base_commit` / first: `fetch-failed`, pin holds `branch` only (no `base` before a successful `ls-remote`); second: `base` filled with the default branch, one `ls-remote` call | AC-004, FR-002 (N-06) |
| 4 | Autonomous run with a `decision` block, continued while the base advanced; source pin on `feat/18-x`, `main` checked out / `feat/18-x` checked out; a conflicting base, continued twice / source run with no pin | `continue` | `wrong-branch` against the source branch / check runs, new pin has the source `branch` and `base`, then the decision is recorded / each blocked continue writes no decision, leaves the source run as it was, records its `branch_sync` event in the source run's stream, and creates no `speckit-runs/<new_id>/` archive and no pin for the new ID / `wrong-branch` "no branch pin", recovery "start a new run" | AC-005, FR-001, R12 (F-10, N-07, DEC-0006) |
| 5 | behind; a modified tracked file / an untracked file / only ignored `.agents/skills/ballast-x` | `resume` | `dirty` for the first two, unchanged; synchronized for the third | AC-006, A-8, FR-006 |
| 6 | behind; an ignored local `.env`; the base starts tracking `.env` | `resume` | `dirty` "ignored files would be overwritten: .env"; `.env` content unchanged; unchanged | FR-006, AC-006 (F-07) |
| 7 | feature and base edit the same lines | `resume` | `conflict` naming the commit and path; unchanged; no rebase in progress | AC-007, FR-005 |
| 8 | the base has `CHANGELOG.md merge=union`; base and feature both prepend a line | `resume` | `synchronized`; both lines present; a `merge=union` line only on the feature branch is not honoured; the argv log shows `--attr-source=NEW_BASE` before `merge-tree` | FR-005, A-1 (F-05, N-02) |
| 9 | pin already holds `base_commit`; remote path removed / base ref deleted / no `[github] repository` | `resume` | `fetch-failed` and the pin's `base_commit` is not used as the base / `unknown-base`, the default branch not substituted / `unknown-base` | AC-008, FR-002, FR-003, A-6 |
| 10 | `MERGE_HEAD` present; detached HEAD; other branch checked out | `resume` | `in-progress`; `wrong-branch`; `wrong-branch` | AC-009 |
| 11 | run with no pin (started before #17's pin), on `feat/18-x` / run with a #17 pin holding `branch` only | `resume` | `wrong-branch` "run {id} has no branch pin", recovery "start a new run"; no pin written; no agent / check proceeds and fills `base` with the default branch | FR-002, R12 (DEC-0006, N-06) |
| 12 | after each block in 5–10, remove the cause | rerun | the check runs from the top and succeeds | AC-010 |
| 13 | Autonomous start, base advanced with a conflict | `start --mode autonomous`, then `continue RUN_ID --reason block-resolved --ref x` | block category `upstream-sync`, run `stopped`, block `command` is the `ballast run start --mode autonomous` restart; no decision record; `continue` refused with "nothing to continue" | AC-011, FR-011 (F-06) |
| 14 | published branch equals local; base advanced | `resume` | remote branch moved to the rebased HEAD | AC-012, FR-007 |
| 15 | someone pushed to the published branch, and local has its own commits too | `resume` | `diverged`; both branches unchanged | AC-013 |
| 16 | published branch moves between fetch and push (a hook in the test seam pushes first) | `resume` | `diverged`; local unchanged; published keeps the other push | AC-013, FR-007 |
| 17 | `pre-receive` rejects; remote unreachable at push | `resume` | `push-failed`, `retryable` false / true; local unchanged | AC-014, FR-007 |
| 18 | published; failure injected after the push / process killed after the push / unpublished, process killed between `read-tree` and `update-ref` / published, killed between `read-tree` and `update-ref` / published, killed between `read-tree` and `update-ref`, then a tracked file edited and an untracked file added before the rerun (P-02) | `resume` (or, for the second and third rerun variants, `start --mode autonomous` / `continue`), then again: `resume` / `start --mode autonomous` (new run ID) / `continue` (new continuation ID) / a new human-gated `start` | first: blocked (`internal-error`), detail "the published branch already holds …", recovery "rerun to finish the synchronization", `branch-sync/<key>.json` holds the record; second, in every variant: `synchronized` with `recovered` true and `recovered_from` the first run, local at the pushed commit, no manual step, record deleted; in the P-02 variant, `git status` afterwards shows exactly the edited file and the untracked file | AC-014, FR-007, SC-002 (F-03, N-01, DEC-0005, P-02) |
| 19 | local branch gets a new commit after the replay but before the push (test seam) | `resume`, then `resume` | first: `busy`, nothing pushed, unchanged; second: `synchronized` including the new commit | FR-007, FR-016 (F-03) |
| 20 | local strictly behind its published branch, clean; base contained | `resume` | fast-forwarded to published; `up-to-date` with `fast_forwarded` | AC-015 |
| 21 | published branch one commit ahead with a change under `.specify/`; local clean | `resume` | fast-forward, then `protected-input` naming the `.specify/` path; no agent | AC-015, AC-016, FR-008 (F-02) |
| 22 | local strictly behind published, dirty; base contained / base not contained | `resume` | `up-to-date`, not fast-forwarded, printed note; working tree unchanged / `dirty` | AC-015, AC-006 (F-13) |
| 23 | base changes `ballast.toml` | `resume` | sync completes; `protected-input` names `ballast.toml` (from the pre-mutation diff); next `ballast run` refused until `ballast trust` | AC-016, FR-008, SC-002 exception, DEC-0002 |
| 24 | `.git/config` with agent-written `origin` URL, `url.<x>.insteadOf` for https and ssh, `core.sshCommand`, `include.path`, `credential.helper`, a filter driver and `user.name`/`user.email`; a `reference-transaction` and a `pre-push` hook; a merge driver in the feature's `.gitattributes` | `resume` | fetch and push go to the pinned repository; none of the configured programs runs (marker files absent); replayed commits carry the operator's global committer, not the `.git/config` one | AC-017, FR-012 (F-08, F-12) |
| 25 | base and feature both changed `tools/a.py`; `plan.md` and a review exist | `resume` | `synchronized`, `overlap` 1, `stale_plan`/`stale_review` true; `branch-sync/<event>.json` lists `tools/a.py`; Draft PR section shows the entry; no gate added | AC-018, FR-015 |
| 26 | lock held by another process | `resume` | `busy`; unchanged | AC-019, FR-016 |
| 27 | two processes synchronize the same branch concurrently | both | exactly one `synchronized`, one `busy`; branch equals the single-run result | AC-020, FR-016 |
| 28 | behind on `develop` / `develop` up to date / `feat/180-x` for Issue 18 / the repository's default branch when the run's base is another branch / no feature directory | `resume` | `not-feature-branch`, nothing rewritten or pushed / `up-to-date` / `not-feature-branch` / `not-feature-branch` / `not-feature-branch` | AC-021, FR-005, DEC-0004 |
| 29 | run on `main` itself: no local commits, base advanced / one local commit, base advanced / no local commits, base advanced, a modified tracked file | `start` | fast-forwarded to the base, `pre-receive` records no push / `diverged` with `git switch -c` recovery, nothing pushed / `dirty`, unchanged, no `read-tree` ran | FR-005, FR-006, DEC-0003 (F-08, N-10) |
| 30 | feature branch with no commits beyond the old base, behind; unpublished / published | `resume` | fast-forwarded to the base, nothing pushed / fast-forwarded and pushed with the lease | edge "no commits beyond the base" (F-08) |
| 31 | base advanced only by an empty commit / only in `specs/18-x/` | `resume` | `synchronized` each time; the new base commit is in HEAD | FR-004, edge "empty or spec-dir commit" (F-08) |
| 32 | base force-pushed; pin has the old `base_commit` / has none | `resume` | only feature commits replayed / `diverged` | edge "base rewritten" |
| 33 | branch name and conflicting path contain shell metacharacters and newlines | `resume` | printed as escaped text; no command interpreted them | FR-013 |
| 34 | Ctrl-C during the replay | `resume`, then rerun | first: `internal-error` "interrupted", exit 130, unchanged; second: normal check | edge "interrupted", DEC-0001 |
| 35 | ledger write fails after the local update | `resume`, then `resume` | first: `internal-error` "not recorded", no agent, branch synchronized; second: `up-to-date` | DEC-0001, FR-009 (F-08) |
| 36 | git 2.40 (version seam), or git only inside the checkout | `resume` | `git-unavailable` "older than 2.41"; `ballast doctor` reports the 2.41 floor | DEC-0001 (N-02) |
| 37 | operator global config `gc.auto=1`, `gc.pruneExpire=now`; the checkout has loose objects under `objects/17/` and an unrelated branch `side` of old loose objects | `resume` | `synchronized`; `git fsck` clean; `git log side` reads every commit | FR-006, FR-012 (F-01) |
| 38 | SHA-256 scratch repository and remote | `resume` | `synchronized`; the throwaway uses `sha256` | F-09 |
| 39 | the remote needs a credential the operator's helper does not supply; `GIT_ASKPASS`, `SSH_ASKPASS` and `core.askPass` (global) name a marker program, `DISPLAY` set | `resume` | `fetch-failed` at once, no prompt, no wait for the timeout; the askpass marker is absent | FR-010 (F-11, N-09) |
| 40 | published; the completion after a push is blocked `dirty` (tree dirtied after the push, test seam), then the operator commits / a commit lands between the push and the CAS `update-ref` (test seam) | `resume`, then `resume` | first: `dirty` with "a previous synchronization already pushed …" and the "move these changes aside without committing" recovery / `busy` with "rerun to finish the synchronization", the failed-CAS restore resets the index and worktree to the new HEAD's tree, so the tree is clean against that commit; second: `synchronized`, `recovered` true, the new commit replayed onto the pushed commit, pushed with lease on it, record deleted; with a conflicting commit: `conflict` with the `git rebase --onto` recovery and the record kept / third variant (P-04): between `read-tree` and the CAS, a bare `git commit` of the staged tree (`X`, tree equal to `new_head`'s) → `busy`, `git status` clean at `X`; rerun → row 5 drops the empty replay, local update `X → new_head`, no push (`NEW == OBSERVED`), `synchronized` with `recovered` true | FR-006, FR-007 (N-03, P-04) |
| 41 | blobless clone (`--filter=blob:none`, stand-in remote with `uploadpack.allowFilter` so the clone really is partial) whose `origin` has a marker `uploadpack`; base advanced, published / a full clone with only `remote.origin.promisor` set / only `extensions.partialClone` set | `resume` | `git-unavailable` "partial clone", recovery "clone the repository again without --filter, then rerun"; unchanged, nothing fetched or pushed, the `origin` marker is absent; the same for each configuration variant | FR-012, AC-017 (N-04, DEC-0007) |
| 42 | shallow clone (`--depth 1`), behind | `resume` | `git-unavailable` "shallow checkout", recovery `git fetch --unshallow`; unchanged | FR-006 (N-12) |
| 43 | unpublished; killed between the record write and `update-ref`, then `git gc --prune=now` deletes `new_head` / record file holding invalid JSON | `resume` | the record is cleared and the check classifies as usual (`dirty` from the staged tree, normal recovery) / `internal-error` "invalid write-ahead record", record kept, unchanged | FR-006, FR-009 (N-11) |
| 44 | Autonomous `start` on `develop`, and on `feat/180-x` for Issue 18 | `start --mode autonomous` | refused by eligibility with "a feature branch named for the Issue"; no run record; the same predicate as scenario 28 | AC-021, FR-005 (N-05) |
| 45 | AC-015 on `main` (run's base) and on `develop` (other): local strictly behind its published branch, clean; killed between the record write and `update-ref`; then a commit on the old local branch | `resume`, then `resume` | rerun: the record's `published_old` equals its `new_head`, so row 5 does not apply; row 7 clears the record and the check reports `diverged` with `git pull --rebase`; `pre-receive` records no push on either branch | FR-005, AC-015, AC-021, DEC-0003, DEC-0004 (P-01) |
| 46 | published and unpublished: a crash during `read-tree -m -u` (part of `new_head`'s files written over an `old_head` index; test seam), with an `index.lock` left (SIGKILL) / without (Ctrl-C); then a variant where one dirty path differs from `new_head` | `resume`, then (lock variant) remove the lock and `resume`, then run the printed command and `resume` | lock variant first: `in-progress` "another git process may hold the index", no `read-tree` ran; then (both variants) `dirty` "an interrupted update left these files at the synchronized content", recovery `git restore --source={new_head} --staged --worktree .`, record kept, nothing pushed again; after the command: `synchronized`, `recovered` true (row 3), record deleted / differing path: row 3b does not match, the normal `dirty` advice | FR-006, FR-007, AC-009, SC-002 (P-03) |
| 47 | published; base changes `.specify/memory/constitution.md`; killed after `update-ref`, before the record delete | `resume`, then `ballast trust`, then `resume` | the next `ballast run` is refused by the launcher (no check runs, no event); after `ballast trust`: row 1 clears the record, `up-to-date` | FR-008, AC-016 (P-05) |

### Coverage

| Requirement | Scenarios |
| --- | --- |
| AC-001 | 1 |
| AC-002 | 2 |
| AC-003 | 1 |
| AC-004 | 3 |
| AC-005 | 2, 4, 18 |
| AC-006 | 5, 6, 22, 29, 40 |
| AC-007 | 7, 40 |
| AC-008 | 9 |
| AC-009 | 10, 11, 46 |
| AC-010 | 12 |
| AC-011 | 13 |
| AC-012 | 14 |
| AC-013 | 15, 16 |
| AC-014 | 17, 18, 40 |
| AC-015 | 20, 21, 22, 45 |
| AC-016 | 21, 23, 47 |
| AC-017 | 24, 41 |
| AC-018 | 25 |
| AC-019 | 26 |
| AC-020 | 27 |
| AC-021 | 28, 44, 45 |
| FR-001 | 1, 2, 4; `test_spec_workflow.py` call order |
| FR-002 | 3, 9, 11 |
| FR-003 | 9 |
| FR-004 | 1, 31 |
| FR-005 | 1, 7, 8, 28, 29, 44, 45 |
| FR-006 | 5, 6, 29, 37, 40, 41, 42, 43, 46; "unchanged" assertion of every block |
| FR-007 | 14, 16, 17, 18, 19, 40, 46 |
| FR-008 | 21, 23, 47 |
| FR-009 | 1, 35, 36, 43; every scenario asserts one event (scenario 4: in the source run for a blocked `continue`); `test_agent_run_ledger.py` |
| FR-010 | every block scenario asserts the line, one recovery and the exit status; 18, 39, 40, 46 |
| FR-011 | 13 |
| FR-012 | 8, 24, 37, 39, 41 |
| FR-013 | 33 |
| FR-014 | documentation check below |
| FR-015 | 25 |
| FR-016 | 19, 26, 27, 40 |
| SC-002 exceptions (DEC-0002, DEC-0005) | 23; 18, 40, 46 |
| DEC-0006 | 4, 11 |
| DEC-0003, DEC-0004 through recovery (P-01) | 29, 45 |
| DEC-0007 | 41 |

Documentation (FR-014): `templates/policies/spec-kit-workflow.md` has a "Branch synchronization" section listing every cause and its recovery, matching the [contract table](contracts/branch-sync.md#causes-and-recovery), the feature-branch rule (and that bugfix and assess runs started with `specify` are not synchronized), the Git 2.41 floor, shallow checkouts and partial clones refused (with their recoveries), the `protected-input` exception to "nothing changed", and the differences from `git rebase` (unsigned commits, attributes from the base). `run.py --help` (its docstring) describes the check.

## Scratch-repository pilot (SC-004)

On the full-gate host (Linux, systemd user session, Spec Kit CLI), in a scratch project that pins this Ballast:

1. On a branch named for the Issue (`feat/N-x`), `ballast trust`, then `ballast run start -i idea="Issue #N: ..." -i feature_directory=specs/N-x` and stop at the first gate.
2. Push a non-conflicting commit to `main` on GitHub.
3. `ballast run resume RUN_ID`. Expect the one-line `Branch sync: synchronized ...` before the gate re-appears, and `git log` showing the new `main` commit under the feature commits.
4. Push a conflicting commit to `main`, and resume again. Expect `BLOCKED_UPSTREAM_SYNC (conflict)` and its recovery, with no agent step started and `git status` unchanged.
5. Follow the printed recovery and confirm the next resume succeeds without reading Ballast source (SC-003).

Record the transcript in the PR as the roadmap exit evidence.
