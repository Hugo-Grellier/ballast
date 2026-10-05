# Plan review 1: Branch Synchronization Before Agent Steps (#18)

- **Reviewer**: Claude Fable (claude-fable-5-1). Same provider as the author; used because the Codex quota is exhausted until 2026-10-10, so cross-provider independence is reduced. Treat this as a same-provider review and keep the cross-provider slot for the implementation.
- **Date**: 2026-10-05
- **Risk**: R2 (A-7). Plan gate, before `speckit-tasks`.
- **Scope reviewed**: `spec.md` (approved digest in `intent.md`), `plan.md`, `research.md` R1–R14, `data-model.md`, `quickstart.md`, `decisions.md` DEC-0001–0003, `contracts/branch-sync.md`, `contracts/ledger-branch-sync-event.md`; constitution 1.1.0, ADR-0003, ADR-0004, `docs/policies/project/workflow.md`; the code the plan builds on: `run.py` (`main`, `_launch`, `_start_autonomous`, `_continue_command`, `_stop`), `draft_pr.py` (`pin_branch`, `_branch_pin`, `_resolve`, `_command`, `_Locked`, `checkpoint`), `autonomy.py` (`_push`, `_push_url`, `GIT_HARDENING`, `filter_overrides`, `trusted_program`, `BLOCK_CATEGORIES`, `RECOVERY`, `RESUME_REFUSAL`), `launcher.py` (`state_dir`, `trusted_inputs`, `_refusal`), `ledger.py` (`FIELDS`, `_semantic_problems`, `append`).
- **Method**: read-only inspection plus scratch-repository experiments with Git 2.53 (the Git on this host) for the claims that depend on Git behavior: the `GIT_OBJECT_DIRECTORY` throwaway, `merge-tree --write-tree --merge-base` replay semantics against `git rebase`, attribute handling in a bare repository, `read-tree -m -u` against ignored files, `symbolic-ref` on a hand-written `HEAD`, and `push --force-with-lease` from a bare repository. Each finding that rests on an experiment says so.
- **Labels**: spec violation, implementation bug (design), architecture issue, missing test, spec ambiguity, proposed product change. No praise below; what is not listed held up under inspection.

## Findings, ranked by severity

### F-01 — critical — implementation bug (design): the throwaway fetch can garbage-collect the checkout's object store

- **Where**: `research.md` R2 and R3; `contracts/branch-sync.md` § External commands (`GIT_OBJECT_DIRECTORY=<common dir>/objects`); `plan.md` § Summary.
- **Problem**: The throwaway bare repository uses `GIT_OBJECT_DIRECTORY` pointing at the checkout's object store, so fetched and replayed objects land there. `git fetch` ends by spawning `git maintenance run --auto` in the throwaway, which inherits `GIT_OBJECT_DIRECTORY`. When the auto-gc threshold trips (`gc.auto`, default 6700 loose objects, sampled from `objects/17/`; a repository agents commit to crosses it routinely, and the operator's global config may lower it), `gc` repacks and prunes **the checkout's object directory using the throwaway's refs as the reachability roots**. The throwaway holds only `refs/sync/*` and `refs/haves/*`. Every other branch, stash and reflog of the checkout is unreachable from its point of view. **Reproduced**: a checkout with an unrelated `side` branch of 1500 loose objects aged 30 days; one throwaway fetch with `-c gc.auto=200 -c gc.pruneExpire=now` left `git fsck` reporting `refs/heads/side: invalid sha1 pointer` and `git log side` failing with `bad object`. With the default `gc.pruneExpire` (2 weeks) the loss is limited to loose objects older than two weeks, which in a repository that has not run its own gc recently is most of the recent history of every branch other than the one being synchronized. The existing `autonomy._push` does not have this exposure: it uses `objects/info/alternates` (borrowed objects are never pruned by the borrower) and `push` runs no maintenance.
- **Fix**: Every throwaway command runs with `-c maintenance.auto=false -c gc.auto=0` (and keep `gc.autoDetach` irrelevant by never letting it start). Put them next to `GIT_HARDENING` as a named tuple so the shared context manager cannot be used without them. Record in the contract that no command in the throwaway may run `gc`, `repack`, `prune`, `maintenance` or `fsck --lost-found`. Add a test: operator global config `gc.auto=1`, a checkout with at least one loose object under `objects/17/` and an unrelated branch, then one `synchronized` outcome; assert `git fsck` is clean and the unrelated branch's commits still read. If `_push` is moved onto the shared manager, it must keep the same flags; `plan.md` currently promises "behavior unchanged" for `_push` while switching its object sharing mechanism, which is not the same behavior.

### F-02 — high — spec violation (FR-008, AC-016): the AC-015 fast-forward skips the protected-input recheck

- **Where**: `research.md` R4 steps 6–7 and R9 ("after a sync that changed HEAD"); `data-model.md` § Outcome (`up-to-date` with `head_after` = the published commit) and § State transitions (trust recheck appears only on the replay path); `quickstart.md` scenario 15.
- **Problem**: When the local branch is strictly behind its published branch and clean, the launcher fast-forwards the checkout to the published commit and, if the base is then contained, returns `up-to-date`. That path changes the checkout and runs no `trusted_inputs` comparison. Anyone who can push to the feature branch (a collaborator, a leaked token, a mistaken push from another clone) can change `.specify/` workflow scripts or `ballast.toml`; this invocation then runs agent steps on them. The launcher's own refusal check ran before the fast-forward, so it does not catch it, and FR-008 requires the recheck after any synchronization that changed the checkout. The spec's AC-016 names `.specify/` precisely because the engine executes it.
- **Fix**: Run the recheck whenever `head_after != head_before`, including the AC-015 path and the "no commits beyond the base, fast-forwarded" edge case. Make it the last step before returning any non-blocked outcome, so no future path can skip it. Add a scenario: published branch one commit ahead with a change under `.specify/`; expect the fast-forward, then `protected-input`, no agent.

### F-03 — high — implementation bug (design): the push-then-update ordering does not self-heal; R5's AC-015 claim is false after a replay

- **Where**: `research.md` R5 ("the published branch moved, so the next invocation sees the local branch strictly behind it and fast-forwards, AC-015"); `data-model.md` § State transitions (`local update → blocked(busy) (restored)`); SC-002.
- **Problem**: After a replay, `NEW` is not a descendant of `OLD`. If anything fails between the successful lease push and the CAS `update-ref` (CAS lost, `read-tree -m -u` refusing, disk full, Ctrl-C, a crash), the published branch holds `NEW` and the local branch holds `OLD`, which share no ancestry beyond the old base. The next invocation classifies that as "both have commits the other lacks" → `diverged`, with the recovery `git pull --rebase`, which only works because Git's patch-id dedupe drops the duplicates. So the plan's stated recovery (`busy`/`push-failed`, then AC-015 heals it) does not occur, SC-002 ("published branch unchanged in every blocked case") is broken for a cause the plan labels `busy`, and the operator is left with a manual merge for a state the launcher created. The window is small but it is exactly the window a crash or Ctrl-C hits, and `internal-error` (DEC-0001) explicitly covers Ctrl-C.
- **Fix**: (1) Write-ahead record: before the push, write `{"sync": {"old_head": OLD, "new_head": NEW}}` into the pin (operator state, already the identity record); clear it after the CAS succeeds. At the start of every check, when the pin holds a pending sync and the observed state is `published == new_head and local == old_head` (push done, local not), complete the local update; when `local == new_head and published == old_head` (not reachable with push-first, but cheap to cover), complete the push with lease `old_head`; anything else clears the record and proceeds. (2) Run `git read-tree -m -u --dry-run OLD NEW` (the flag exists) and the HEAD/clean re-check **before** the push, so the common local refusals happen while nothing has been pushed. (3) Add scenarios: "branch moved between fetch and update-ref" and "process killed after the push" (simulate by injecting a failure after the push in the test seam); both must end `synchronized` on the following invocation with no manual step.

### F-04 — high — architecture issue / proposed product change: any branch a run starts on becomes a force-push target

- **Where**: `research.md` R4 step 4 ("at `start` the current branch becomes the pin"), R5; DEC-0003; the Issue's out-of-scope line "arbitrary developer branches".
- **Problem**: The only guard against rewriting a shared branch is DEC-0003's `branch == base`. A run started on `develop`, `release/1.x`, a long-lived integration branch or a colleague's branch is rebased onto `main` and force-pushed with a lease. The lease protects against lost commits, not against rewriting history that other clones track. ADR-0003 bounded the launcher's GitHub authority to a fixed allowlist; the proposed ADR-0005 grants "rewrite the run's local feature branch" without defining "feature branch". `#17` already prints `pending (on-base-branch)` and the intake skill says "from a feature branch", so the convention exists but nothing enforces it at the moment the launcher gains force-push authority.
- **Fix**: Define the rewrite rule in ADR-0005 and enforce it in step 4: the pinned branch must not be the recorded base, must not be the repository's default branch (available from the same `ls-remote --symref`), and must not be a name the operator excluded. The last part is the product question for the human: either (a) a fixed rule (for example the branch must carry the feature's Issue number, as `specs/<issue>-` does for the directory; Ballast's own branches are `feat/<issue>-slug`) or (b) an operator allowlist pattern in `ballast.toml` (protected, so trusted) with a safe default such as `feat/*`, `fix/*`. Anything else blocks with `wrong-branch` and the detail "`X` is not a feature branch; Ballast rewrites only feature branches". This is a product change to the spec's Key Entities (feature identity), so it needs a decision entry, not a silent plan change.

### F-05 — medium — implementation bug (design): `merge-tree` in the bare throwaway ignores the tree's `.gitattributes`

- **Where**: `research.md` R2 ("what `git rebase` does by default", A-1); `contracts/branch-sync.md` § Guarantees 5.
- **Problem**: In a bare repository with no index, ORT reads no `.gitattributes` from the trees being merged, so `merge=union`, `merge=ours`, `-merge`/`binary`, `text`/`eol` and `merge.renormalize` behave differently from `git rebase` in a checkout. **Reproduced**: `CHANGELOG.md merge=union`, both sides prepend a line; `git rebase` is clean, `merge-tree --write-tree` in the throwaway exits 1 (conflict). Release Please-style changelogs and lockfiles with `merge=ours` are common; the launcher would block with `conflict` where the operator's own `git rebase` succeeds, and the recovery text sends them to do exactly that, which contradicts SC-003's "recover without reading Ballast source" in spirit. The same experiment showed that an attribute-selected merge driver did **not** run in the bare throwaway even though the operator's global config defined it, so the current design is safe but imprecise.
- **Fix**: Run `merge-tree` with `--attr-source=<NEW_BASE>` (Git 2.40, the same floor as `--merge-base`). Reproduced: with `--attr-source=NEW` the union case merges clean. Taking attributes from the fetched **base** keeps them operator-controlled (an agent's `.gitattributes` on the feature branch is not consulted), and a driver still runs only when the operator's global configuration defines it. Document the residual deltas from `git rebase`: unsigned commits, base-side attributes, no `rebase.*` configuration. Add scenario: `merge=union` in the base, both sides change the file; expect `synchronized`.

### F-06 — medium — spec ambiguity (AC-011) / implementation bug (design): the Autonomous recovery command cannot work

- **Where**: `research.md` R10; `data-model.md` § Autonomous block (`command: ballast run continue RUN_ID --reason block-resolved --ref TEXT`).
- **Problem**: An Autonomous `start` that blocks on synchronization has run no agent step. `ballast run continue` records a human decision, lowers the run and starts `ballast-continue`, a gate-only workflow of validators and gates (ADR-0004). On a feature with no artifacts it fails at the first validator, leaving a `continued` run and a new run that failed on nothing. The plan chose this only so AC-011 has "the existing block-recovery path". That path already has three variants (`continue`, `publish`, `discard-runs`); "restart" is the right one here.
- **Fix**: For `upstream-sync` blocks recorded before any agent step, `recovery_command` is the `ballast run start --mode autonomous ...` invocation ("remove the cause shown, then start again"), and `_continue_command` refuses to continue a run whose only block is `upstream-sync` with no recorded step (detail: nothing to continue). Record the AC-011 reading in `decisions.md` for the human. Scenario 10 then asserts the restart command and that `continue` is refused.

### F-07 — medium — implementation bug (design) + missing test: ignored local files are overwritten, and the restore deletes them

- **Where**: `research.md` R5 and R6 (A-8: ignored files are not dirty); FR-006 ("never discard").
- **Problem**: `read-tree -m -u OLD NEW` silently overwrites an ignored working-tree file when `NEW` tracks a file at that path, and the restore `read-tree -m -u NEW OLD` then **deletes** it (reproduced: an ignored `ign` became the tracked content, and the restore removed the file). `git rebase` has the same first half, but Ballast's design explicitly keeps ignored files out of the dirty decision, installs ignored trees itself (`.ballast/`, `.agents/skills/ballast-*`) and promises in FR-006 never to discard local files. A locally ignored `.env` that the base starts tracking is the realistic case.
- **Fix**: Before mutating, intersect `diff-tree -r --name-only OLD NEW` (or `OLD HEAD..published` for AC-015) with `status --porcelain -z --ignored=matching` paths; a non-empty intersection blocks as `dirty` with the detail "ignored files would be overwritten: {paths}". The `--dry-run` from F-03 does not catch this (ignored files pass `verify_absent`). Add the scenario.

### F-08 — medium — missing tests (coverage gaps in `quickstart.md`)

- FR-003 "no fallback": scenario 7 must start from a pin that already holds `base_commit` and assert that value is not used when the fetch fails (today the scenario only forces the failure).
- DEC-0003 success half: run on the base branch, no local commits, base advanced → fast-forward, **no push attempted** (assert on the stand-in remote's `pre-receive` that nothing arrived).
- Edge "no commits beyond the base → fast-forwarded, nothing published unless already": no scenario.
- Edge "base advanced only by an empty commit or only in the feature's spec directory → still behind": no scenario (FR-004).
- F-03's two scenarios, F-02's scenario, F-05's scenario, F-07's scenario, F-01's gc test.
- `internal-error` after a completed sync (ledger write fails after `update-ref`): the data-model row says "unchanged if raised before step 11; otherwise as left by the R5 restore", but after step 11 the state is `synchronized` and nothing restores it. Document it and test that the next invocation records `up-to-date`.
- Scenario 17 (hostile checkout config) should also plant `include.path`, `credential.helper`, `url.<x>.insteadOf` for both schemes, and a `reference-transaction` hook; the last one fires on `update-ref` and is the one plumbing-side hook the design relies on `core.hooksPath=/dev/null` to silence.
- SC-002 tests compare the index "byte-for-byte"; `git status` refreshes and may rewrite `.git/index`. Compare `git ls-files -s` and `diff-index --cached HEAD` instead, or the test is flaky for the wrong reason.

### F-09 — low — implementation bug (design): object format is not carried into the throwaway

- **Where**: `contracts/branch-sync.md` § External commands (`git init --bare`); `data-model.md` (`commit` allows 64-hex).
- **Problem**: `git init --bare` creates a SHA-1 repository. With a SHA-256 checkout, `GIT_OBJECT_DIRECTORY` sharing fails. `autonomy._push` has the same latent gap through alternates.
- **Fix**: `git init --bare --object-format=$(git rev-parse --show-object-format)` (read in the checkout, data only). One test with a SHA-256 scratch repository, or state SHA-1 only in the contract and refuse with `git-unavailable`.

### F-10 — low — spec ambiguity: missing pin on `resume`; `continue`'s pinned branch

- **Where**: `research.md` R4 step 4 and R12; `contracts/branch-sync.md` § Entry point and § Call sites.
- **Problem**: (a) A run started before this feature, or whose pin write failed (`_launch` swallows that today), has no pinned branch; `resume` then has nothing to compare and the plan does not say what happens. (b) For `continue`, `data-model.md` says the new pin takes the **source** run's `branch`, but the entry point has no `branch` parameter and R4 says "at `start` the current branch becomes the pin"; with `start=True` the continuation would pin whatever is checked out, which is the behavior `wrong-branch` exists to prevent.
- **Fix**: (a) No pin on `resume` → `wrong-branch`, detail "run has no pinned branch", recovery "start a new run on the feature branch" (matches #17's `branch-unpinned`). (b) Add `branch: str | None` to the entry point; `continue` passes the source pin's branch and the check compares against it.

### F-11 — low — implementation bug (design): unattended network commands can hang on prompts; throwaway template hooks

- **Where**: `contracts/branch-sync.md` § External commands.
- **Problem**: `ls-remote`, `fetch` and `push` inherit the operator's terminal; an expired credential or an unknown host key prompts, and an Autonomous `start` waits up to 600 s for a prompt nobody answers. `git init --bare` also copies the operator's `init.templateDir`/`GIT_TEMPLATE_DIR` hooks into the throwaway; `core.hooksPath=/dev/null` neutralizes them, but `--template=` (empty) removes the dependency on that override.
- **Fix**: Set `GIT_TERMINAL_PROMPT=0` in the throwaway environment; init with `--template=`; classify the prompt failure as `fetch-failed`/`push-failed` with the existing recovery.

### F-12 — low — security note: committer identity is read from agent-writable configuration

- **Where**: `research.md` R2 ("the checkout's effective `user.name`/`user.email`").
- **Problem**: `.git/config` is agent-writable (#17 DEC-0004); replayed commits are then pushed by the operator with an agent-chosen committer. It is data, not code, and agents already commit under that identity, so the exposure is attribution only.
- **Fix**: Read `user.name`/`user.email` with `git config --get` **in the throwaway** (empty local config → the operator's global identity), the same place the push's authority comes from. Mention it in ADR-0005.

### F-13 — low — spec ambiguity: AC-015 when the tree is dirty

- **Where**: `research.md` R4 step 6 vs step 7; `data-model.md` § State transitions (`published → blocked(diverged|dirty)`).
- **Problem**: A branch that already contains the base, is strictly behind its published branch and has work in progress blocks as `dirty`, although R4 step 7 says an up-to-date branch is never inspected for dirt. The spec only says the fast-forward happens when clean.
- **Fix**: State the rule: strictly behind published and dirty → skip the fast-forward, continue; if the base then needs a replay, `dirty` blocks as usual, and a later replay+push is impossible while the local branch lacks published commits because step 6 classifies that as `diverged`. Add the scenario.

### F-14 — low — missing test / design: `ls-remote` round trip when the base is pinned

- **Where**: `research.md` R3.
- **Problem**: `ls-remote --symref` runs on every invocation although the default branch is needed only when the pin has no `base`; the fetch alone gives the base and published commits. Not a defect, one avoidable 30 s-bounded network call per invocation (SC-005 counts "one fetch").
- **Fix**: Skip `ls-remote` when the pin holds `base`, or keep it and say why (the published-branch existence check without a fetch error). Either is fine; the contract should not list it as unconditional if it is not.

## Spec coverage

| ID | Design | Test | Gap |
| --- | --- | --- | --- |
| AC-001–005 | R1, R4 | sc. 1–4 | — |
| AC-006 | R6 | sc. 5 | F-07 (ignored overwrite) |
| AC-007 | R2 | sc. 6 | F-05 (attribute parity) |
| AC-008 | R3 | sc. 7 | F-08 (pin `base_commit` not used) |
| AC-009 | R4 3–4 | sc. 8 | — |
| AC-010 | R4 | sc. 9 | — |
| AC-011 | R10 | sc. 10 | F-06 |
| AC-012 | R5 | sc. 11 | — |
| AC-013 | R4 6, R5 | sc. 12–13 | — |
| AC-014 | R5 | sc. 14 | F-03 (failure after push) |
| AC-015 | R4 6 | sc. 15 | F-02, F-13 |
| AC-016 | R9 | sc. 16 | F-02 (fast-forward path) |
| AC-017 | R1, R3 | sc. 17 | F-08 (more config keys) |
| AC-018 | R11 | sc. 18 | — |
| AC-019–020 | R7 | sc. 19–20 | — |
| FR-001–002 | R1, R12 | sc. 2–3 | F-10 |
| FR-003–004 | R3 | sc. 7 | F-08 |
| FR-005–007 | R2, R5 | sc. 6, 11–14 | F-03, F-07 |
| FR-008 | R9 | sc. 16 | F-02 |
| FR-009–011 | R13, R10, ledger contract | sc. 1, 10, ledger tests | — |
| FR-012–013 | R2, R13 | sc. 17, 22 | F-01 (maintenance child), F-12 |
| FR-014 | plan § Repository Impact | docs check | — |
| FR-015 | R11 | sc. 18 | — |
| FR-016 | R7 | sc. 19–20 | — |
| Edge cases | R4, R8 | sc. 21, 23 | F-08 (empty commit, spec-dir-only, no-commits-beyond-base) |

## Proposals in `decisions.md`

- **DEC-0001** (`git-unavailable`, `internal-error`): **accept**, with two revisions. The data-model row for `internal-error` must add the state "synchronized" for a failure after `update-ref` (ledger write, see F-08), and the contract must settle the exit status for a Ctrl-C turned into `internal-error` (the contract says 1; `run.py` uses 130 elsewhere). `ballast doctor` reporting the 2.40 floor is fine and small.
- **DEC-0002** (`protected-input` keeps the completed sync): **accept with changes**. AC-016's wording is explicit and approved, and the content comes from the operator's base branch, so keeping and pushing it is defensible. Required changes: the recheck must cover every path that changes HEAD (F-02); detect the protected-input change from `diff-tree OLD NEW -- ballast.toml .specify` (minus launcher `SKIPPED`) **before** the mutation so the printed names do not depend on a working-tree scan, and keep the post-mutation `trusted_inputs` comparison as the authoritative decision; amend SC-002 as proposed and name the exception in the policy section (FR-014).
- **DEC-0003** (run on the base branch: fast-forward only, never push): **accept, broaden** per F-04: the rule should cover the repository's default branch and whatever the human picks as the feature-branch rule, and it belongs in ADR-0005 as the definition of what the launcher may rewrite. The success half needs its test (F-08).

## Scope and simpler alternatives

- **`merge-tree` replay versus `git rebase`**: justified. `git rebase` in the checkout runs agent-writable configuration; `git rebase` in a throwaway needs a full working tree under the state directory (slow, and it writes every file of the repository to disk for each check); `git replay` is experimental. The experiment replayed a four-commit history (plain change, change already upstream, originally empty commit, binary conflict) and produced the same kept/dropped set and, with equal timestamps, the same commit IDs as `git rebase`. Keep it, with `--attr-source` (F-05) and the gc flags (F-01).
- **`refs/haves/*` negotiation**: not creep. Without refs in the throwaway, every fetch would download the whole base history; `GIT_OBJECT_DIRECTORY` does not feed negotiation.
- **Lock**: reuse `draft_pr._Locked` (already `O_NOFOLLOW | O_CREAT | LOCK_NB`, regular-file check) with a zero wait instead of a second implementation; the only difference the spec wants is "no wait".
- **Stale-evidence side file plus Draft PR entries (R11)**: in scope; AC-018 names both the ledger and the Draft PR. Keep the 200-path cap.
- **Not creep but worth naming in the plan**: moving `_push` onto a shared throwaway helper changes `_push` from alternates to `GIT_OBJECT_DIRECTORY`. Either keep `_push` on alternates and share only the environment and `init` code, or carry F-01's flags and add `_push` to the gc test.

## Verdict

- Verdict: REVISE

Blocking: F-01 (reproduced data loss in the checkout), F-02 (FR-008 bypass on the fast-forward path), F-03 (non-recoverable state after a push, SC-002), F-04 (undefined rewrite boundary for a new force-push authority; needs the human's product decision before ADR-0005). F-05 to F-08 should land in the same plan revision; F-09 to F-14 can be tasks.
