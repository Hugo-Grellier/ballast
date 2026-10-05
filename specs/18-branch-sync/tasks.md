---

description: "Task list for Branch Synchronization Before Agent Steps"
---

# Tasks: Branch Synchronization Before Agent Steps

**Input**: Design documents from `specs/18-branch-sync/`: [plan.md](plan.md) (revision 4), [spec.md](spec.md), [research.md](research.md) (R1–R15), [data-model.md](data-model.md), [contracts/branch-sync.md](contracts/branch-sync.md), [contracts/ledger-branch-sync-event.md](contracts/ledger-branch-sync-event.md), [quickstart.md](quickstart.md), [decisions.md](decisions.md) (DEC-0001–DEC-0007, resolved)

**Prerequisites**: plan.md (R2; the plan gate for revision 4 was approved by the agent under the operator's delegation, recorded in decisions.md; merge still needs the operator's explicit approval), spec.md, research.md, data-model.md, contracts/

**Acceptance evidence**: Each acceptance criterion `AC-001`–`AC-021` has at least one deterministic test task below (see [AC traceability](#acceptance-criteria-traceability)). Quickstart scenario numbers (`Q1`–`Q47`) name the setup and expectation each test implements. The scratch-repository pilot (T052) adds manual evidence for SC-003 and SC-004, which need a real GitHub remote; it replaces no test.

**Organization**: Tasks are grouped by user story. US1, US2 and US4 are P1; US3 is P2. Phases follow priority, so US4 (P1) comes before US3 (P2); story labels keep the spec's numbering.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel: a different file from every other task in the same wave, and no unfinished dependency
- **[Story]**: US1, US2, US3, US4 from spec.md
- Test tasks cite the acceptance criteria (`AC-NNN`), functional requirements (`FR-NNN`), decisions (`DEC-NNNN`) and review findings (`F-`, `N-`, `P-`) they prove
- Tests are written first and must fail before the implementation task that depends on them

## Conventions used by every task

- The module is `tools/spec_workflow/branch_sync.py`: standard library only, runs under `python3 -I -S`, imported by `run.py` at startup. It reuses `draft_pr._resolve`, `draft_pr._child_path`, `draft_pr.GIT_LOCATION`, `draft_pr._Locked`, `autonomy.GIT_HARDENING`, `autonomy.filter_overrides`, `autonomy.is_feature_branch`, `autonomy._push_url` (scheme rule only), `launcher.state_dir`, `launcher.trusted_inputs`, `launcher.BASES` and `launcher.SKIPPED`. It does not change `autonomy._push` or `launcher.py`.
- Two runners only: `_checkout(argv)` (in the checkout: `GIT_HARDENING`, `filter_overrides`, `GIT_NO_LAZY_FETCH=1`) and `_throwaway(argv, *, network=False)` (always `GIT_HARDENING` then `NO_MAINTENANCE`, `GIT_OBJECT_DIRECTORY`, the askpass/prompt environment of research R3a; network calls with `stdin=DEVNULL`, `start_new_session=True`). No other code path runs `git`. Neither ever uses a shell.
- Test seams, and nothing else is patched: `branch_sync._url(root, owner, name)` (returns a `file://` URL in tests), `branch_sync._crash(point)` (no-op in production; tests raise at `after-push`, `after-read-tree`, `after-update-ref`, `after-record`), `branch_sync._git_version()`, and `branch_sync.ARGV_LOG` (a list the throwaway runner appends to when not `None`).
- Cause names, details, recovery wording and printed lines are copied verbatim from [contracts/branch-sync.md](contracts/branch-sync.md) § Printed output and § Causes and recovery; do not paraphrase.
- "Unchanged" means research R14: HEAD, `git ls-files -s`, `git diff-index --cached HEAD`, `git status --porcelain=v1 -z` and the remote branch equal their values before the run, and no `rebase-merge`, `rebase-apply` or `MERGE_HEAD` exists. Every blocked-outcome test asserts it unless the contract names an SC-002 exception (DEC-0002, DEC-0005), and asserts exactly one `branch_sync` event, one `Recovery:` line, and the exit status.
- Run tests with `uv run --no-project --python 3.13 --with pyyaml python -m unittest tests/test_branch_sync.py tests/test_spec_workflow.py tests/test_autonomous_run.py tests/test_autonomy.py tests/test_agent_run_ledger.py tests/test_draft_pr.py tests/test_doctor.py`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Record the architecture decision and create the module and test harness.

- [X] T001 [P] Draft ADR-0005 "Launcher-side branch synchronization" in `docs/adr/0005-launcher-branch-synchronization.md` with status `Proposed`, from plan.md § Proposed architecture decisions item 1: the Git transport authority (fetch, push with lease) extending ADR-0003; the rewrite rule (one predicate `autonomy.is_feature_branch`; base branch fast-forward only; other branches never rewritten; no-Issue invocations block `not-feature-branch`; bugfix and assess runs via `specify` are not synchronized); the throwaway-repository boundary (empty config and template, no prompts, no maintenance or gc, shared object store); committer identity from operator configuration; only `start` pins (DEC-0006); shallow and partial clones refused (DEC-0007); the recovery invariant (no row pushes unless the record records a push, P-01); the differences from `git rebase` (unsigned commits, attributes from the base, no `rebase.*`). Mark it as needing human approval; do not set it to `Accepted`.
- [X] T002 [P] Create the `tools/spec_workflow/branch_sync.py` skeleton: module docstring stating the trust boundary (FR-012); constants `GIT_FLOOR = (2, 41)`, `NO_MAINTENANCE = ("-c", "maintenance.auto=false", "-c", "gc.auto=0", "-c", "fetch.writeCommitGraph=false")`, `LS_REMOTE_TIMEOUT = 30`, `NETWORK_TIMEOUT = 600`, `CAUSES` (the 13 causes of FR-009), `OUTCOMES`, `REF` and `COMMIT` patterns from data-model.md § Feature identity, `IN_PROGRESS_MARKERS` (research R4 step 3); frozen dataclass `Outcome` with the data-model § Synchronization state fields plus `outcome`, `cause`, `detail`, `recovery`, `retryable`, `recovered_from`, `note`; the four test seams of Conventions; `synchronize(root, run_id, *, feature, starting=False, branch=None, base=None, source_run=None) -> Outcome` returning a `blocked`/`internal-error` outcome with detail `NotImplementedError`; `format_lines(outcome) -> list[tuple[str, str]]` (stream, text) stub.
- [X] T003 Create the harness in `tests/test_branch_sync.py` (depends on T002): a `Scratch` helper building, in a temporary directory, a bare "GitHub" remote with `main`, a checkout cloned from it with `ballast.toml` pinning `[github] repository = "o/r"`, a trusted baseline (`launcher` `trusted.json` in a temporary `state_dir`), the feature directory `specs/18-x`, the branch `feat/18-x`, and `branch_sync._url` patched to the remote's `file://` URL; helpers `advance_base(files)`, `publish()`, `push_as_someone_else()`, `add_pre_receive(reject=False)` recording each received ref to a file, `snapshot()` / `assert_unchanged(before)` per Conventions, `events(run_id)` reading the ledger stream, `global_config(**keys)` writing a file set through `GIT_CONFIG_GLOBAL`, `marker_program(name)` writing a script that creates a marker file, and `run_check(**kwargs)` calling `synchronize` with a fixed run ID and pinned state. Add one smoke test that imports the module and builds a `Scratch`.

**Checkpoint**: module and harness importable; `uvx ruff check` passes.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Ledger event kind, the non-blocking lock, the shared feature-branch predicate, the two Git runners, pin and write-ahead record storage, outcome output and recording, and the `run.py` call sites. Every user story needs all of them.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T004 [P] Write `branch_sync` ledger tests in `tests/test_agent_run_ledger.py`: a valid event (source `runner`) is accepted for each outcome with the fields of [the event contract](contracts/ledger-branch-sync-event.md); rejected: unknown outcome or cause, `blocked` without `cause`, `up-to-date`/`synchronized` with `cause` or missing any of `base_ref`, `base_after`, `head_before`, `head_after`, `synchronized` without `pushed`, `retryable` with a cause other than `push-failed`, `recovered` with a non-`synchronized` outcome, `recovered_from` without `recovered` true or failing `RUN_ID_PATTERN`, a `ref` value failing the data-model pattern (`-x`, `a..b`, `x.lock`, `@{`), a `commit` that is not 40 or 64 lowercase hex, any extra field; a stream holding only one `branch_sync` event is valid; `ledger.py record` does not offer the kind; `report` returns the latest event's `data` plus `observed_at`, or `{"available": false, "reason": "no check recorded"}`, and the text report has one `branch_sync:` line. [FR-009]
- [X] T005 Implement the `branch_sync` kind in `tools/spec_workflow/ledger.py` (depends on T004): `FIELDS` and `ENUM_FIELDS` entries, new `ref` and `commit` value types in `_valid_value`, the per-outcome rules in `validate`, the exclusion from `record`, and the `report` / `_text_report` entry. `schema_version` stays 1.
- [X] T006 [P] Document the `branch_sync` kind in `tools/spec_workflow/ledger-schema.md` (depends on T005): fields, the `ref` and `commit` types, per-outcome requirements, the `branch-sync/<event_id>.json` side file, the report entry, and the compatibility note (additive; an older pinned Ballast rejects a stream containing it).
- [X] T007 [P] Write lock tests in `tests/test_draft_pr.py`: `_Locked(path, wait=0)` reports busy at once, distinct from `LockUnavailableError`, when another process holds the `flock` (spawned with `multiprocessing` holding a real lock), and the default wait is still `LOCK_WAIT`, so existing `draft_pr` behavior is unchanged. [FR-016]
- [X] T008 Add the `wait` argument to `draft_pr._Locked` in `tools/spec_workflow/draft_pr.py` (depends on T007): default `LOCK_WAIT`; `wait=0` makes one non-blocking `flock` attempt and reports busy distinctly from `LockUnavailableError` (broken state).
- [X] T009 [P] Write predicate tests in `tests/test_autonomy.py`: `is_feature_branch(name, issue, base, default_branch)` is true for `feat/18-branch-sync`, `18-branch-sync`, `fix_18.x` with issue 18; false for `feat/180-x`, `v18`, `develop`, a name equal to `base`, a name equal to `default_branch`, and any name when `issue` is `None` (research R15, N-05). [FR-005, AC-021, DEC-0004]
- [X] T010 Implement `autonomy.is_feature_branch` in `tools/spec_workflow/autonomy.py` (depends on T009): split at `/`, `-`, `_`, `.`; decimal segment equal to the Issue number; not the base, not the default branch. Make `check_eligibility` call it (with `base` = the default branch) instead of its own "not `HEAD`, not the default branch" test, and change `BRANCH_REFUSAL` to "autonomous needs a feature branch named for the Issue without an open PR".
- [X] T011 Write foundation tests in `tests/test_branch_sync.py` (depends on T003): `branch_sync.py` imports only the standard library and sibling workflow modules and runs under `python3 -I -S` (C1); every argv in `ARGV_LOG` starts with the resolved absolute `git` and contains `GIT_HARDENING` then `NO_MAINTENANCE`; the throwaway environment has `GIT_TERMINAL_PROMPT=0`, `GIT_NO_LAZY_FETCH=1`, `GIT_ASKPASS=""`, `SSH_ASKPASS_REQUIRE=never` and no `SSH_ASKPASS`, `DISPLAY`, `WAYLAND_DISPLAY` or `GIT_CONFIG_*`; the throwaway is `git init --bare --template=` with the checkout's object format and is deleted afterwards; a checkout-local `git` first on `PATH` is never executed; `_git_version` returning 2.40 → `git-unavailable` "git 2.40 is older than 2.41" [DEC-0001, N-02]; pin and write-ahead record files are mode `0600` in a `0700` directory, replaced atomically, and refused under the checkout or a temp root; a record failing validation is reported, never treated as absent [N-11]; `format_lines` shell-quotes names inside commands and strips control characters elsewhere, never prints Git output [FR-013]; `synchronize` with an injected `RuntimeError` returns `blocked`/`internal-error` with detail `RuntimeError`, with `KeyboardInterrupt` returns detail "interrupted", and with a failing ledger write turns an otherwise non-blocked outcome into `internal-error` "not recorded" [DEC-0001, FR-009].
- [X] T012 Implement the runners, `git` resolution and version check, and the throwaway repository in `tools/spec_workflow/branch_sync.py` (depends on T002, T011): `_checkout` and `_throwaway` per Conventions and contract § External commands; `git` via `draft_pr._resolve` with `_git_version` parsing `git version X.Y`; throwaway created in a `tempfile.TemporaryDirectory` under `state_dir` with `--object-format` read by `rev-parse --show-object-format` and accepted only as `sha1` or `sha256` (F-09); the allowed throwaway command list enforced by an assertion in `_throwaway`.
- [X] T013 Implement lock, pin and write-ahead record storage in `tools/spec_workflow/branch_sync.py` (depends on T008, T012): key `sha256(branch)[:16]`; lock `<state_dir>/branch-sync/<key>.lock` via `draft_pr._Locked(path, wait=0)` (busy → `busy`, `LockUnavailableError` → `internal-error`); pin `<state_dir>/draft-pr/<run>.json` read and written with `branch`, `base`, `base_commit` (data-model § Feature identity); record `<state_dir>/branch-sync/<key>.json` with `branch`, `old_head`, `new_head`, `published_old`, `run_id`, `written_at` (data-model § Write-ahead record), validated on read; both written atomically.
- [X] T014 Implement the outcome layer and the R4 pipeline frame in `tools/spec_workflow/branch_sync.py` (depends on T005, T010, T013): the recovery text table copied from the contract; `format_lines` for every success and block form of contract § Printed output; `_record` appending one `branch_sync` event (source `runner`) with only the event-contract fields, to `source_run` when the outcome is blocked and `source_run` is set (N-07); the `synchronize` wrapper that never raises (exceptions, `KeyboardInterrupt`, failed record write per T011); the R4 step sequence 1–15 as private functions in order, each step not yet implemented returning `internal-error` so the frame is testable.
- [X] T015 [P] Write `run.py` integration tests in `tests/test_spec_workflow.py` (depends on T002), in the existing `EngineRunTests` harness, with `branch_sync.synchronize` replaced by a recorder returning a chosen outcome: it is called exactly once for `start`, `resume` and `continue` and never for `publish`, at the four sites of the contract § Call sites, before `_launch`, with `starting` true only for `start` [FR-001]; for each of the 13 causes, a blocked outcome prints the block lines on stderr, exits 1 (130 for "interrupted"), never executes the fake `specify`, and runs no Draft PR checkpoint [FR-001, FR-010, SC-001]; `_launch` no longer calls `draft_pr.pin_branch` [R12]; `continue` draws the new run ID first, passes the source pin's `branch` and `base` and `source_run`, and a blocked `continue` writes no decision, leaves the source record unchanged, and creates no `speckit-runs/<new_id>/` archive and no pin for the new ID [AC-005, N-07, Q4]; `run.py --help` describes the check [FR-014].
- [X] T016 Integrate the check in `tools/spec_workflow/run.py` and `tools/spec_workflow/draft_pr.py` (depends on T014, T015): import `branch_sync` at startup; call it at the four contract sites; print `format_lines`; on `blocked` return `EXIT_BLOCKED` or `EXIT_INTERRUPTED` before `_launch` without the checkpoint; remove the pin call from `_launch` and remove `draft_pr.pin_branch` (or make it delegate to `branch_sync`), keeping `_branch_pin` reading `branch` only; update the module docstring to describe the check (FR-014).

**Checkpoint**: Foundation ready: `run.py` calls a check that records one event and stops on every block.

---

## Phase 3: User Story 1 - Resume on the current base (Priority: P1) 🎯 MVP

**Goal**: A paused run whose base advanced resumes on a branch rebased onto the current base, and the ledger and output say so.

**Independent Test**: Q1: pause a run, add a non-conflicting base commit, resume. The fake `specify` sees a HEAD containing the new base commit; the ledger and the printed line show base and HEAD before and after.

### Acceptance tests for User Story 1

- [X] T017 [US1] Write synchronization tests in `tests/test_branch_sync.py` (depends on T003): Q1 behind, clean, unpublished → `synchronized`, HEAD contains the new base, event and printed line carry base before/after and HEAD before/after [AC-001, AC-003, FR-004, FR-005, FR-009]; Q2 already contains the base → `up-to-date`, HEAD unchanged, no `fetch` in `ARGV_LOG` when both commits are local, a repeat records `up-to-date` again [AC-002, SC-005]; Q3 `starting` on a behind branch → synchronized, pin holds `branch`, `base`, `base_commit`; the same with the remote unreachable → `fetch-failed`, pin holds `branch` only; then reachable → `base` filled from the default branch with one `ls-remote` [AC-004, FR-002, N-06]; Q11 second variant, a #17 pin with `branch` only → `base` filled [N-06]; Q30 unpublished variant, no commits beyond the old base → fast-forwarded, nothing pushed; Q31 base advanced only by an empty commit / only in `specs/18-x/` → `synchronized` [FR-004]; Q32 base force-pushed with the old `base_commit` pinned → only feature commits replayed; with none pinned → `diverged` [edge "base rewritten"].
- [X] T018 [US1] Write replay-fidelity and object-store tests in `tests/test_branch_sync.py` (depends on T003): Q8 base `CHANGELOG.md merge=union`, both sides prepend → `synchronized` with both lines; a `merge=union` only on the feature branch is not honoured; `ARGV_LOG` shows `--attr-source=<new base>` before `merge-tree` [FR-005, F-05, N-02]; replayed commits keep author, message and encoding byte-for-byte, drop `gpgsig`, and a commit already upstream is dropped; Q37 global `gc.auto=1`, `gc.pruneExpire=now`, loose objects and an unrelated branch `side` → `synchronized`, `git fsck` clean, `git log side` reads every commit [FR-006, FR-012, F-01]; Q38 SHA-256 scratch repository → `synchronized`, throwaway uses `sha256` [F-09].
- [X] T019 [P] [US1] Write end-to-end `run.py` tests in `tests/test_spec_workflow.py` with the real `synchronize` against a `Scratch`-style repository (depends on T003, T015): `resume` of a paused run after a base commit → the fake `specify` records a HEAD containing it [AC-001]; `start` on a behind branch → synchronized before the first step [AC-004]; `continue` of an Autonomous run with a `decision` block → the check runs, the new pin holds the source `branch` and `base`, then the decision is recorded [AC-005, Q4 second variant].

### Implementation for User Story 1

- [X] T020 [US1] Implement identity, remote observation and the up-to-date path in `tools/spec_workflow/branch_sync.py` (depends on T014, T017): R4 step 4 for the pinned and `starting` cases (pin `{branch}` at `start` only); R3 `ls-remote --symref` with or without `refs/heads/BASE`, `refs/haves/*` hints, the `cat-file -e` probes in the throwaway and the conditional `fetch --no-tags --no-write-fetch-head` into `refs/sync/base` and `refs/sync/published`; the pin's `base` written only after a successful `ls-remote`; the repository only from `ballast.toml` and the URL from `_url`; R4 step 9 `merge-base --is-ancestor` → `up-to-date`; `base_commit` updated after `up-to-date`.
- [X] T021 [US1] Implement the old base and the replay in `tools/spec_workflow/branch_sync.py` (depends on T018, T020): R8 old-base selection; `rev-list --reverse --topo-order --no-merges OLD_BASE..HEAD`; per commit the R2 `merge-tree` argv, exit 1 as conflict with `--name-only -z` paths, the already-upstream drop, commit text rewrite (`tree`, `parent`, no `gpgsig`, fresh `committer` from `git var GIT_COMMITTER_IDENT` in the throwaway, "no committer identity" → `internal-error`), `hash-object -t commit -w --stdin`; no feature commits → new HEAD is the base commit.
- [X] T022 [US1] Implement the R5 mutation for an unpublished feature branch in `tools/spec_workflow/branch_sync.py` (depends on T021): step 1 pre-mutation checks (HEAD still `OLD`, else `busy`, tree clean per R6, ignored-file overlap from `diff-tree` ∩ `status --ignored=matching --untracked-files=all`, `read-tree -m -u --dry-run OLD NEW`); step 2 write-ahead record with `published_old` null; step 4 `read-tree -m -u OLD NEW` then `update-ref -m "ballast: sync onto BASE" refs/heads/BRANCH NEW OLD`; step 5 pin `base_commit` then record delete; `_crash` calls at each point; the `synchronized` outcome and its printed line.

**Checkpoint**: Q1–Q3, Q8, Q11, Q30–Q32, Q37, Q38 pass. Do not ship US1 alone: US2 and US4 are also P1 and carry the refusals and the trust recheck.

---

## Phase 4: User Story 2 - Stop safely when the branch cannot be updated (Priority: P1)

**Goal**: Every unsafe or unknown state blocks before any agent with `BLOCKED_UPSTREAM_SYNC`, one cause and one recovery, and leaves the checkout unchanged.

**Independent Test**: Force each blocked cause in a scratch repository; each invocation exits 1 before any agent step, prints the cause and one recovery, and leaves the checkout unchanged with no rebase in progress.

### Acceptance tests for User Story 2

- [X] T023 [US2] Write blocked-cause tests in `tests/test_branch_sync.py` (depends on T003): Q5 modified tracked file / untracked file → `dirty`, unchanged; only ignored `.agents/skills/ballast-x` → `synchronized` [AC-006, A-8, FR-006]; Q6 ignored local `.env` the base starts tracking → `dirty` "ignored files would be overwritten: .env", `.env` content unchanged [AC-006, F-07]; Q7 same lines edited → `conflict` naming the commit and path, unchanged, no rebase in progress [AC-007]; Q9 remote path removed with `base_commit` pinned → `fetch-failed`, pinned commit not used; base ref deleted → `unknown-base`, default branch not substituted; no `[github] repository` → `unknown-base` [AC-008, FR-002, FR-003, A-6]; Q10 `MERGE_HEAD` → `in-progress`; detached HEAD → `wrong-branch`; other branch → `wrong-branch` [AC-009]; Q11 first variant, `resume` of a run with no pin → `wrong-branch` "run {id} has no branch pin", no pin written [DEC-0006]; Q12 after each block of Q5–Q10 the cause is removed and the rerun succeeds from the top [AC-010]; Q28 behind on `develop` / `develop` up to date / `feat/180-x` for Issue 18 / the default branch when the run's base is another branch / no feature directory → `not-feature-branch`, `up-to-date`, `not-feature-branch` ×3, nothing pushed [AC-021, DEC-0004]; Q29 run on `main`: no local commits → fast-forwarded, `pre-receive` records no push; one local commit → `diverged` with `git switch -c`; dirty → `dirty`, no `read-tree` in the log [FR-005, DEC-0003, N-10]; Q33 branch name and conflicting path with shell metacharacters and newlines → printed escaped [FR-013]; Q34 Ctrl-C during the replay → `internal-error` "interrupted", unchanged, rerun normal [DEC-0001]; Q35 ledger write fails after the local update → `internal-error` "not recorded", branch synchronized; rerun → `up-to-date` [FR-009].
- [X] T024 [US2] Write environment-refusal tests in `tests/test_branch_sync.py` (depends on T003): Q36 version seam 2.40, and `git` only inside the checkout → `git-unavailable` [DEC-0001]; Q39 remote needing a credential, `GIT_ASKPASS`, `SSH_ASKPASS` and global `core.askPass` naming a marker program, `DISPLAY` set → `fetch-failed` well under the timeout, marker absent [FR-010, F-11, N-09]; Q41 blobless clone from a stand-in remote with `uploadpack.allowFilter` and a marker `uploadpack` on `origin` / a full clone with only `remote.origin.promisor` / only `extensions.partialClone` → `git-unavailable` "partial clone", unchanged, marker absent [FR-012, AC-017, DEC-0007]; Q42 `--depth 1` clone → `git-unavailable` "shallow checkout", recovery `git fetch --unshallow` [N-12].
- [X] T025 [US2] Write concurrency tests in `tests/test_branch_sync.py` (depends on T003): Q26 lock held by another process → `busy`, unchanged [AC-019, FR-016]; Q27 two processes synchronize the same branch → exactly one `synchronized`, one `busy`, branch equal to the single-run result [AC-020]; Q19 a commit lands on the local branch after the replay, before the local update (seam) → `busy`, nothing pushed, unchanged; rerun → `synchronized` including the new commit [FR-007, FR-016, F-03].
- [X] T026 [P] [US2] Write Autonomous tests in `tests/test_autonomous_run.py` (depends on T010): Q13 Autonomous `start` with a conflicting base → block category `upstream-sync`, run `stopped`, block `command` is the `ballast run start --mode autonomous` restart, no decision record; `continue RUN_ID --reason block-resolved --ref x` refused with "nothing to continue" [AC-011, FR-011, F-06]; Q44 Autonomous `start` on `develop` and on `feat/180-x` for Issue 18 → refused by eligibility with "a feature branch named for the Issue", no run record [AC-021, N-05]; `recovery_command(run_id, "upstream-sync")` returns the restart command and matches `BLOCK_COMMAND`; `RESUME_REFUSAL` names #21.
- [X] T027 [P] [US2] Write a doctor test in `tests/test_doctor.py`: a fake `git` reporting 2.40 makes `ballast doctor` report the 2.41 floor; 2.41 passes [DEC-0001, N-02, Q36].

### Implementation for User Story 2

- [X] T028 [US2] Implement the refusals in `tools/spec_workflow/branch_sync.py` (depends on T022, T023, T024): R4 step 2 shape checks (`rev-parse --is-shallow-repository`; `config --get extensions.partialClone`, `--get-regexp` for `remote.*.promisor` and `remote.*.partialclonefilter`, read as data); step 3 in-progress markers and `index.lock` (P-03); step 4 detached, wrong branch and unpinned `resume`/`continue` (DEC-0006); step 5 `unknown-base` vs `fetch-failed` classification from exit status and the advertisement, never from printed Git output; step 7 branch kind via `autonomy.is_feature_branch` and the Issue number from the feature directory; step 10 base-branch fast-forward through R5 (record `published_old` null, never pushed) or `diverged`, other branch → `not-feature-branch`; step 11 `dirty` with the first ten paths; conflicts → `conflict` with the commit and first twenty paths; every recovery string from the contract table.
- [X] T029 [US2] Implement the lost-CAS path in `tools/spec_workflow/branch_sync.py` (depends on T025, T028): when `update-ref` fails, cause `busy`, record kept; restore with `read-tree -m -u NEW HEAD` only while `diff-index --cached --quiet NEW` and `diff-files --quiet` hold (P-04); otherwise leave the tree as it is.
- [X] T030 [US2] Add the `upstream-sync` block category in `tools/spec_workflow/autonomy.py` (depends on T026): `BLOCK_CATEGORIES`, `RECOVERY["upstream-sync"]` "Remove the cause shown, then start the run again.", `recovery_command` returning the restart command, `RESUME_REFUSAL` pointing at #21 (A-9).
- [X] T031 [US2] Wire Autonomous blocks in `tools/spec_workflow/run.py` (depends on T016, T030): an Autonomous `start` whose check blocks records `autonomy.make_block("upstream-sync", CONDITION, run_id=...)` through `_stop` with the condition `BLOCKED_UPSTREAM_SYNC (CAUSE): DETAIL. Recovery: ACTION` (data-model § Autonomous block); `_continue_command` refuses a source run whose current block is `upstream-sync` with the R10 message; never call `append_decision` or `append_human_decision` for a sync.
- [X] T032 [US2] Report the Git 2.41 floor in `tools/ballast` `doctor` (depends on T027), using the existing program resolution.

**Checkpoint**: every blocked cause of FR-009 except `push-failed` and `protected-input` is covered and leaves the checkout unchanged.

---

## Phase 5: User Story 4 - Never let synchronization bypass the trust boundary (Priority: P1)

**Goal**: A sync that brings in changed protected inputs fails closed; the check runs only in trusted code with the operator's configuration; overlapping evidence is marked stale.

**Independent Test**: Q23: advance the base with a `ballast.toml` change and resume. The sync completes, `protected-input` names `ballast.toml`, no agent starts, and the next `ballast run` is refused until `ballast trust`.

### Acceptance tests for User Story 4

- [X] T033 [US4] Write trust-boundary tests in `tests/test_branch_sync.py` (depends on T003): Q23 base changes `ballast.toml` → sync completes, `protected-input` names `ballast.toml` from the pre-mutation diff, the launcher's `_refusal` refuses afterwards [AC-016, FR-008, DEC-0002]; Q24 `.git/config` with an `origin` URL, `url.<x>.insteadOf` for https and ssh, `core.sshCommand`, `include.path`, `credential.helper`, a filter driver, `user.name`/`user.email`; `reference-transaction` and `pre-push` hooks; a merge driver in the feature's `.gitattributes` → fetch and push reach the pinned repository, no marker file exists, replayed commits carry the `GIT_CONFIG_GLOBAL` committer [AC-017, FR-012, F-08, F-12]; Q47 published, base changes `.specify/memory/constitution.md`, crash `after-update-ref` before the record delete → the next `ballast run` is refused by the launcher with no check and no event; after `ballast trust` row 1 clears the record and the outcome is `up-to-date` [FR-008, AC-016, P-05].
- [X] T034 [US4] Write overlap tests in `tests/test_branch_sync.py` (depends on T003): Q25 base and feature both changed `tools/a.py`, `plan.md` and a review exist → `synchronized`, `overlap` 1, `stale_plan` and `stale_review` true, `branch-sync/<event_id>.json` lists `tools/a.py` with at most 200 paths and `truncated`, the printed line names the stale evidence, no gate added; without evidence or without overlap no file is written [AC-018, FR-015].
- [X] T035 [P] [US4] Write stale-entry tests in `tests/test_draft_pr.py` (depends on T007): the Ballast section renders one dated entry per stale-evidence file whose `feature` matches, across all run archives of the clone, oldest first, with the base move, the stale evidence and the first 20 paths escaped; files of another feature are ignored; a malformed file is skipped [AC-018, FR-015].

### Implementation for User Story 4

- [X] T036 [US4] Implement the protected-input checks in `tools/spec_workflow/branch_sync.py` (depends on T029, T033): R9 pre-mutation `diff-tree -r --name-only --no-renames -z OLD NEW -- launcher.BASES` minus `launcher.SKIPPED`; R4 step 14 after every HEAD change (`head_after != head_before`): `launcher.trusted_inputs(root)` compared with `trusted.json` as `launcher._refusal` does → `protected-input` with the first ten names (or the differing digest names), the sync kept; fix the runners from T012 if any Q24 marker fires.
- [X] T037 [US4] Implement overlap and stale evidence in `tools/spec_workflow/branch_sync.py` (depends on T034, T036): R11 overlap `diff-tree MB NEW_BASE` ∩ `diff-tree MB OLD_HEAD`; plan evidence from `<feature>/plan.md` at `OLD_HEAD`; review evidence from a `review` or `convergence` ledger event or `<feature>/reviews/` at `OLD_HEAD`; event fields `overlap`, `stale_plan`, `stale_review`; the side file of data-model § Stale evidence record; the printed note.
- [X] T038 [US4] Render stale-evidence entries in `draft_pr._section` in `tools/spec_workflow/draft_pr.py` (depends on T008, T035): read the side files per data-model § Stale evidence record and append the dated entries; no gate, no review re-run.

**Checkpoint**: no path that moves HEAD skips the trust recheck; overlap is visible in the ledger, output and Draft PR.

---

## Phase 6: User Story 3 - Keep a published branch and its PR consistent (Priority: P2)

**Goal**: A published feature branch moves to the rebased HEAD only under a lease; divergence and push failures block; a sync interrupted after its push is completed by the next invocation.

**Independent Test**: Q14: publish the branch, advance the base, resume; the remote branch moves to the rebased HEAD. Q15/Q16: if someone else pushed, `diverged` and both branches keep their commits.

### Acceptance tests for User Story 3

- [X] T039 [US3] Write published-branch tests in `tests/test_branch_sync.py` (depends on T003): Q14 published equals local, base advanced → remote moved to the rebased HEAD [AC-012, FR-007]; Q15 both sides have commits → `diverged`, both unchanged [AC-013]; Q16 the published branch moves between observation and push (seam) → `diverged`, local unchanged, published keeps the other push [AC-013, FR-007]; Q17 `pre-receive` rejects → `push-failed`, `retryable` false; remote unreachable at push → `retryable` true; local unchanged [AC-014]; Q20 local strictly behind its published branch, clean, base contained → fast-forwarded, `up-to-date` with `fast_forwarded` [AC-015]; Q21 published one commit ahead with a `.specify/` change → fast-forward then `protected-input` naming it [AC-015, AC-016, F-02]; Q22 local behind published and dirty, base contained → `up-to-date`, not fast-forwarded, printed note, tree unchanged; base not contained → `dirty` [AC-015, AC-006, F-13]; Q30 published variant → fast-forwarded and pushed with the lease; Q45 AC-015 on `main` and on `develop`, crash `after-record`, then a commit on the old local branch → rerun reports `diverged` with `git pull --rebase`, `pre-receive` records no push on either branch [AC-015, AC-021, DEC-0003, DEC-0004, P-01].
- [X] T040 [US3] Write recovery-table tests in `tests/test_branch_sync.py` (depends on T003): Q18 published, failure injected `after-push` → `internal-error` with "the published branch already holds …" and "rerun to finish the synchronization", record present; process killed `after-push`; unpublished and published crash `after-read-tree`; the P-02 variant with an edited tracked file and a new untracked file before the rerun; each rerun as `resume`, as `starting` with a new run ID (Autonomous restart and new human-gated `start`) and as a continuation with a new ID → `synchronized`, `recovered` true, `recovered_from` the first run, local at the pushed commit, record deleted; in the P-02 variant `git status` shows exactly the edit and the untracked file [AC-005, AC-014, FR-007, SC-002, N-01, DEC-0005, P-02]; Q40 completion blocked `dirty` after the push → the "a previous synchronization already pushed …" detail and the "move these changes aside without committing" recovery; then the operator commits → `synchronized`, `recovered`, the new commit replayed onto the pushed commit with lease on it; with a conflicting commit → `conflict` with the `git rebase --onto` recovery, record kept; a commit between push and CAS → `busy`, tree clean against the new HEAD; the P-04 variant (bare commit of the staged tree) → `busy`, then row 5 with no push [AC-006, AC-007, AC-014, FR-006, N-03, P-04]; Q43 unpublished, killed `after-record`, `git gc --prune=now` deletes `new_head` → record cleared, normal classification; invalid JSON record → `internal-error` "invalid write-ahead record", record kept, unchanged [FR-006, FR-009, N-11]; Q46 crash during `read-tree -m -u` (seam writes part of `new_head`'s files over an `old_head` index), with an `index.lock` → `in-progress` first, no `read-tree` ran; without (and after removing the lock) → `dirty` "an interrupted update left these files at the synchronized content", recovery `git restore --source={new_head} --staged --worktree .`, record kept, nothing pushed; after that command → `synchronized`, `recovered`; one path differing from `new_head` → the normal `dirty` advice [AC-009, FR-006, FR-007, SC-002, P-03].

### Implementation for User Story 3

- [X] T041 [US3] Implement published-branch classification in `tools/spec_workflow/branch_sync.py` (depends on T036, T039): R4 step 8 from the observed published commit (never from `refs/remotes/*`): local ahead or equal → continue; strictly behind and clean → AC-015 fast-forward through R5 with `published_old == new_head`; strictly behind and dirty → skip with the printed note (F-13); both ahead → `diverged`.
- [X] T042 [US3] Implement the push in `tools/spec_workflow/branch_sync.py` (depends on T041): R5 step 3 for a published feature branch only, skipped when `NEW == OBSERVED`; `push --force-with-lease=refs/heads/BRANCH:OBSERVED URL NEW:refs/heads/BRANCH` from the throwaway (600 s); lease rejection → `diverged`; other failures → `push-failed`, `retryable` for timeout or transport, not for a remote rejection; the record kept on every failure; post-push block detail and recovery (DEC-0005).
- [X] T043 [US3] Implement the recovery state machine in `tools/spec_workflow/branch_sync.py` (depends on T040, T042): R4 step 6 before branch-kind classification, under the lock, for the record of the current branch whatever run wrote it; invalid record → `internal-error`, kept; `cat-file -e new_head` in the throwaway; rows 1, 2, 3, 3b (`hash-object --no-filters` without `-w` against `ls-tree new_head`), 4, 5 (replay `old_head..L` onto `new_head`, lease `new_head`), 6 and 7 of research R5 in order; the invariant that no row pushes unless the record records a push (P-01); post-push `dirty` variants (P-06); `recovered` and `recovered_from` on the outcome; R4 step 14 after any HEAD change.

**Checkpoint**: every quickstart scenario Q1–Q47 passes.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Operator documentation, installed-copy refresh, gates, pilot evidence, reviews and reconciliation.

- [X] T044 [P] Add a "Branch synchronization" section to `templates/policies/spec-kit-workflow.md` (depends on T031, T038, T043): when the check runs; which branches it may rewrite, and that bugfix and assess runs started with `specify` are not synchronized; the Git 2.41 floor; shallow checkouts and partial clones refused with their recoveries; unpinned runs; the outcomes; every cause with its recovery from the contract table; the `protected-input` exception and the post-push exception to "nothing changed"; what is never done (stash, reset, discard, push without lease, overwrite ignored files); the differences from `git rebase`; staleness in the Draft PR. [FR-014]
- [X] T045 [P] Add one sentence to the workflow section of `README.md` pointing to the policy's "Branch synchronization" section (depends on T044). [FR-014]
- [X] T046 [P] Update `specs/TECHNICAL-SPEC.md` §90 and §91: "safe branch synchronization on start and resume" delivered by #18; the Autonomous `resume` dependency left to #21 (depends on T043).
- [X] T047 [P] Reconcile `docs/adr/0005-launcher-branch-synchronization.md` with the implemented behavior, still `Proposed` (depends on T001, T043).
- [X] T048 Add a documentation test in `tests/test_branch_sync.py` asserting every cause and recovery in `branch_sync`'s recovery table appears in `templates/policies/spec-kit-workflow.md`'s "Branch synchronization" section, and that `run.py --help` and `ballast run --help` (through `tools/ballast`) mention the check (depends on T044). [FR-014, SC-003]
- [ ] T049 In a fresh clone of this branch, run `BALLAST_STANDARD_DIR=<this checkout> ballast setup` and confirm the installed `docs/policies/spec-kit-workflow.md` equals the template and `git status --short` shows no tracked change outside plan.md § Repository Impact; record the evidence here (depends on T044). [BL-INV-001]
- [ ] T050 Run the fast gate and record commands and results for the PR: `uvx ruff check && uvx ruff format --check` and `uv run --no-project --python 3.13 --with pyyaml python -m unittest tests/test_*.py` (depends on T006, T032, T037, T043, T045, T046, T047, T048, T049).
- [ ] T051 Run the full local gate on Linux with a systemd user session, the Codex CLI and the Spec Kit CLI, so the four CI-skipped tests also run; record the result or the unavailable gate and why (depends on T050).
- [ ] T052 Operator scratch-repository pilot per [quickstart.md](quickstart.md) § Scratch-repository pilot, steps 1–5, on the full-gate host against a real GitHub repository; record the transcript in the PR as the roadmap exit evidence [AC-001, AC-007, SC-003, SC-004]. Manual evidence because a real GitHub remote and real agents are needed; every AC also has a deterministic test (depends on T050).
- [ ] T053 Run the R2 reviews and store reports in `specs/18-branch-sync/reviews/`: security review (Git transport authority with operator credentials, untrusted names and configuration, the throwaway boundary, lazy fetch and askpass, the recovery table's push invariant), engineering review, test review against the traceability table below, documentation review of the policy section and ADR-0005. Use a cross-provider reviewer (Codex) if its quota is available (from 2026-10-10); otherwise record why not (depends on T050).
- [ ] T054 Resolve open items in `specs/18-branch-sync/decisions.md`, run Spec Kit converge and the spec reconciliation skill, then ask the operator to approve ADR-0005 and set it to `Accepted` only after that approval (depends on T051, T052, T053).

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: none. T001 and T002 are independent.
- **Foundational (Phase 2)**: T004, T007, T009 need nothing; T011 needs T003; T012–T014 need T011 and the ledger, lock and predicate tasks; T015 needs T002; T016 needs T014 and T015. Blocks all stories.
- **US1 (Phase 3)**: tests need only T003/T015; implementation needs T014.
- **US2 (Phase 4)**: tests need only T003/T010; `branch_sync` implementation follows US1's mutation (T022), because the base-branch fast-forward and the dirty checks reuse it.
- **US4 (Phase 5)**: tests need only T003/T007; implementation follows US2's lost-CAS path (T029) in the same file and needs the R5 mutation.
- **US3 (Phase 6)**: tests need only T003; implementation follows US4's recheck (T036), because the AC-015 fast-forward and every recovery row end in it.
- **Polish (Phase 7)**: after all stories.

### User Story Dependencies

- **US1 (P1)**: after Foundational. No dependency on other stories.
- **US2 (P1)**: after US1's T022 for the `branch_sync.py` work; T026/T027/T030/T032 are independent of US1.
- **US4 (P1)**: after US1's T022 (mutation) and, for file order, US2's T029.
- **US3 (P2)**: after US4's T036. Its tests are independent.

### Within Each User Story

- Tests first, failing; then implementation. `tools/spec_workflow/branch_sync.py` and `tests/test_branch_sync.py` are each edited by one task at a time.

## Execution Wave DAG

Tasks in a wave have every dependency met by earlier waves. Tasks in one wave that edit the same file run one after another; only `[P]` tasks touch a file no other task in their wave touches.

| Wave | Tasks | Notes |
| --- | --- | --- |
| 1 | T001, T002, T004, T007, T009 | ADR, module skeleton, ledger, lock and predicate tests: five different files |
| 2 | T003, T005, T008, T010, T015 | harness; ledger kind; `_Locked` wait; predicate; `run.py` tests |
| 3 | T006, T019, T026, T027, T035; then in `tests/test_branch_sync.py`: T011, T017, T018, T023, T024, T025, T033, T034, T039, T040 | every test written before the code it proves; the `test_branch_sync.py` tasks run in sequence |
| 4 | T012, T030, T032, T038 | runners (`branch_sync.py`), `upstream-sync` (`autonomy.py`), doctor (`tools/ballast`), stale entries (`draft_pr.py`) |
| 5 | T013 | lock, pin, record storage |
| 6 | T014 | outcome layer and pipeline frame |
| 7 | T016, T020 | `run.py` integration; identity and up-to-date path |
| 8 | T021, T031 | replay; Autonomous block wiring (`run.py`) |
| 9 | T022 | R5 mutation |
| 10 | T028 | refusals |
| 11 | T029 | lost-CAS path |
| 12 | T036 | protected-input checks |
| 13 | T037 | overlap and stale evidence |
| 14 | T041 | published-branch classification |
| 15 | T042 | push with lease |
| 16 | T043 | recovery state machine |
| 17 | T044, T046, T047 | policy section, technical spec, ADR |
| 18 | T045, T048, T049 | README, documentation test, installed-copy refresh |
| 19 | T050 | fast gate |
| 20 | T051, T052, T053 | full gate, pilot, reviews |
| 21 | T054 | reconciliation and ADR approval |

## Parallel Example: Wave 3

```text
Task: "Document the branch_sync kind in tools/spec_workflow/ledger-schema.md"                 (T006)
Task: "Write end-to-end run.py tests in tests/test_spec_workflow.py"                          (T019)
Task: "Write Autonomous tests in tests/test_autonomous_run.py"                                 (T026)
Task: "Write a doctor test in tests/test_doctor.py"                                            (T027)
Task: "Write stale-entry tests in tests/test_draft_pr.py"                                      (T035)
Task: "Write all branch_sync tests in tests/test_branch_sync.py (T011, T017, T018, T023–T025, T033, T034, T039, T040), one after another"
```

## Implementation Strategy

### MVP first (User Story 1)

1. Phases 1 and 2: `run.py` calls a check that records one event and stops on every block.
2. Phase 3: a clean, unpublished, behind feature branch is rebased before the first agent step.
3. **Stop and validate**: run US1's tests and the fast gate. Do not ship US1 alone: without US2's refusals and US4's trust recheck, a sync could rewrite an unsafe branch or bring in unreviewed protected inputs. US1, US2 and US4 are all P1.

### Incremental delivery

1. Foundation → US1 → US2 → US4 is the minimum mergeable increment (all P1): synchronized when safe, blocked otherwise, never past the trust boundary.
2. US3 adds published branches, the lease and the recovery table. It is required before merge: after #17 most feature branches are published, and a published branch without US3 blocks or skips the push.
3. Polish: documentation, gates, pilot, R2 reviews, reconciliation, ADR approval.

## Acceptance criteria traceability

| Criterion | Test or verification tasks |
| --- | --- |
| AC-001 | T017 (Q1), T019, T052 |
| AC-002 | T017 (Q2) |
| AC-003 | T017 (Q1) |
| AC-004 | T017 (Q3), T019 |
| AC-005 | T015, T019, T040 (Q18 continuation rerun) |
| AC-006 | T023 (Q5, Q6), T039 (Q22), T040 (Q40) |
| AC-007 | T023 (Q7), T040 (Q40), T052 |
| AC-008 | T023 (Q9) |
| AC-009 | T023 (Q10, Q11), T040 (Q46) |
| AC-010 | T023 (Q12) |
| AC-011 | T026 (Q13) |
| AC-012 | T039 (Q14) |
| AC-013 | T039 (Q15, Q16) |
| AC-014 | T039 (Q17), T040 (Q18, Q40) |
| AC-015 | T039 (Q20, Q21, Q22, Q45) |
| AC-016 | T033 (Q23, Q47), T039 (Q21) |
| AC-017 | T033 (Q24), T024 (Q41) |
| AC-018 | T034 (Q25), T035 |
| AC-019 | T025 (Q26) |
| AC-020 | T025 (Q27) |
| AC-021 | T009, T023 (Q28), T026 (Q44), T039 (Q45) |
| FR-001, SC-001 | T015, T019 |
| FR-002, FR-003 | T017 (Q3), T023 (Q9, Q11) |
| FR-004 | T017 (Q1, Q31) |
| FR-005 | T017, T018 (Q8), T023 (Q28, Q29) |
| FR-006, SC-002 | every block test's "unchanged" assertion; T018 (Q37), T023 (Q5, Q6, Q29), T024 (Q41, Q42), T040 (Q40, Q43, Q46) |
| FR-007 | T025 (Q19), T039 (Q14, Q16, Q17), T040 |
| FR-008 | T033 (Q23, Q47), T039 (Q21) |
| FR-009 | T004, T011, T023 (Q35), T040 (Q43) |
| FR-010 | T015, T024 (Q39); every block test |
| FR-011 | T026 (Q13) |
| FR-012 | T011, T018 (Q8, Q37), T024 (Q39, Q41), T033 (Q24) |
| FR-013 | T011, T023 (Q33) |
| FR-014 | T015, T044, T045, T048 |
| FR-015 | T034, T035 |
| FR-016 | T007, T025 |
| SC-003 | T048, T052 |
| SC-004 | T052 |
| SC-005 | T017 (Q2) |
| DEC-0001 | T011, T023 (Q34, Q35), T024 (Q36), T027 |
| DEC-0006 | T015, T023 (Q11) |
| DEC-0007 | T024 (Q41) |

## Notes

- R2: ADR-0005 and the merge need explicit human approval; no task sets the ADR to `Accepted` before that.
- Do not weaken a failing test; record any discovery that conflicts with the spec in `specs/18-branch-sync/decisions.md` and stop for a resolution.
- Commit after each task or logical group.
