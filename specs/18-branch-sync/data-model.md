# Data model: Branch Synchronization Before Agent Steps

Entities the check reads and writes. Rationale is in [research.md](research.md); the operator-facing contract is in [contracts/branch-sync.md](contracts/branch-sync.md).

## Feature identity (pin)

`<state_dir>/draft-pr/<run_id>.json`, written only by `branch_sync` in trusted launcher code, mode `0600` in a `0700` directory, replaced atomically (write to a temporary file, then `os.replace`). It extends the #17 branch pin; no second identity record is created (R12).

| Field | Type | Set | Meaning |
| --- | --- | --- | --- |
| `branch` | string | at `start` (the current branch, before the first agent step), or for a continuation on a non-blocked outcome (the source run's branch). Never at `resume` (DEC-0006). | Local branch the run works on; also the published branch name. Never changed afterwards. |
| `base` | ref | after the `ls-remote` that provides it succeeded: at `start`, or on the first check of a pin that lacks it (N-06) | Authoritative base (FR-002). Never changed afterwards (A-3). |
| `base_commit` | commit | after every `up-to-date` or `synchronized` outcome | Base commit last observed; old base for a rewritten base (R8) and a fetch negotiation hint. Never used as the current base (FR-003). |
| `feature` | `specs/<N>-<slug>` | with `branch` at `start`, from the operator's `-i feature_directory`; a continuation copies its source run's | Feature directory whose Issue number decides which branch may be rewritten (R15). `resume` and `continue` read it here, never from agent-writable run state (SEC-002). |

- `ref`: `[A-Za-z0-9._/-]{1,200}`, not starting with `-` or `/`, no `..`, `//`, `@{` or trailing `.lock`/`/`. A recorded or remote name that fails this is `unknown-base`.
- `commit`: `[0-9a-f]{40}` or `[0-9a-f]{64}`.
- A `resume` or `continue` whose run (for `continue`, the source run) has no pin, or a pin without `branch` or `feature`, blocks as `wrong-branch` (DEC-0006).

## Write-ahead record

`<state_dir>/branch-sync/<key>.json`, next to the lock `<key>.lock`, with the same key `sha256(branch)[:16]` (R5, R7, N-01). Same writer, modes and atomic replace as the pin; read and written only under the lock. Keyed by branch, not by run, so any later invocation on the branch finds it: `resume`, `continue`, the Autonomous restart or a new `start`.

| Field | Type | Meaning |
| --- | --- | --- |
| `branch` | string | the branch the record belongs to; must equal the current branch |
| `old_head` | commit | branch HEAD before the mutation |
| `new_head` | commit | branch HEAD the mutation moves to |
| `published_old` | commit or null | observed published commit, the push lease; null for an unpublished branch and for the base-branch fast-forward. The record records a push exactly when it is non-null and differs from `new_head`; the AC-015 fast-forward records `published_old == new_head` and pushes nothing (P-01) |
| `old_base`, `new_base` | commit or null, both or neither | the replay's old and new base, so a completion from the record reports stale evidence (R11, E-03); null for a fast-forward |
| `run_id` | run ID | run that wrote it; reported as `recovered_from` when completed |
| `written_at` | timestamp | when it was written |

- Written before every mutation (R5 step 2); deleted after the pin's `base_commit` is set (R5 step 5), or by the recovery table (R5).
- A record file that exists but fails validation is `internal-error` ("invalid write-ahead record") and is kept, never treated as absent (N-11).
- No recovery row pushes unless the record records a push (P-01, research R5 invariant).

## Synchronization state (in memory, one per invocation)

| Field | Source |
| --- | --- |
| `branch` | `git symbolic-ref --quiet --short HEAD`, checked against the pin |
| `issue` | the feature directory's number (R15), or none |
| `kind` | `feature`, `base` or `other` (R15) |
| `head_before` | `git rev-parse --verify HEAD^{commit}` |
| `default_branch` | `ls-remote --symref` `HEAD` |
| `base_ref` | pin `base`, else `default_branch` |
| `base_before` | pin `base_commit`, may be absent |
| `base_after` | `ls-remote` value, or the fetched `refs/sync/base` |
| `published` | `ls-remote` value, or the fetched `refs/sync/published`; absent when unpublished |
| `old_base` | R8 |
| `head_after` | replay result, published commit (AC-015), base commit (fast-forward), or `head_before` |
| `protected` | names from the pre-mutation diff (R9) |
| `pushed` | whether the published branch was updated |
| `recovered` | whether a pending write-ahead record was completed (R5); with `recovered_from`, the run ID that wrote it |
| `overlap` | R11 path list |

## Outcome

Exactly one per invocation that reaches the check (FR-009).

| Outcome | Required fields | Optional fields |
| --- | --- | --- |
| `up-to-date` | `base_ref`, `base_after`, `head_before`, `head_after` (= `head_before`, or the published commit after an AC-015 fast-forward) | `base_before`, `fast_forwarded` |
| `synchronized` | `base_ref`, `base_after`, `head_before`, `head_after`, `pushed` | `base_before`, `fast_forwarded`, `recovered`, `overlap`, `stale_plan`, `stale_review` |
| `blocked` | `cause` | every field known when the block occurred; `retryable` for `push-failed`; `overlap`, `stale_plan`, `stale_review` for `protected-input`, which keeps the synchronization |

### Causes

| Cause | Detected at (research R4 step) | Detail shown | Branch state after |
| --- | --- | --- | --- |
| `busy` | 1, or the CAS in R5 | none; after a push, "the published branch already holds {new_head}" | unchanged before the push; after a push, published at the new HEAD and the record kept, completed by the next invocation (DEC-0005, SC-002 exception). After a lost CAS, an index and worktree holding only the sync's output are reset to the current HEAD's tree, never to `OLD` (P-04) |
| `git-unavailable` (DEC-0001) | 2 | untrusted, older than 2.41, shallow checkout, or partial clone (R3a, DEC-0007) | unchanged |
| `in-progress` | 3 | the operation (rebase, merge, cherry-pick, revert, bisect), or an `index.lock` present (P-03) | unchanged |
| `wrong-branch` | 4 | detached, current vs pinned branch, or no branch pin at `resume`/`continue` (DEC-0006) | unchanged; no pin written |
| `unknown-base` | 5 | missing repository pin, missing base ref, empty repository | unchanged |
| `fetch-failed` | 5 | none (Git output withheld) | unchanged |
| `not-feature-branch` (DEC-0004) | 10 | the branch, and why it is not a feature branch | unchanged |
| `diverged` | 8, 10, 12, 13 | local and published commits, base rewritten, published branch moved, or base branch with local commits | unchanged |
| `dirty` | 11, R5 step 1 for any mutation (including the fast-forwards and a record completion), or recovery row 3b | first ten uncommitted paths, ignored files the update would overwrite, or paths `read-tree --dry-run` refused; for a completion, "a previous synchronization already pushed {new_head}" before any of the three (P-06); for row 3b, "an interrupted update left these files at the synchronized content: {paths}" (P-03) | unchanged; for a completion after a push, published already at the new HEAD and the record kept; for row 3b, the half-written tree as the crash left it and the record kept |
| `conflict` | 12, or recovery row 5 | the commit being replayed and its conflicting paths (first twenty) | unchanged; in row 5, published already at the record's `new_head` and the record kept |
| `push-failed` | 13 | whether a retry alone can succeed | unchanged locally; published unchanged unless a timed-out push landed, which the next invocation completes |
| `protected-input` | 14 | changed input names (first ten) | synchronized (spec SC-002 exception, DEC-0002) |
| `internal-error` (DEC-0001) | any step, a failed pin, record or ledger write, an invalid write-ahead record, Ctrl-C | exception class name, "interrupted", "not recorded", "no committer identity" or "invalid write-ahead record"; after a push, "the published branch already holds {new_head}" | before step 13: unchanged. During step 13: as left by R5, with the write-ahead record kept, so the next invocation completes or clears it. After the local update (for example the ledger write failed): synchronized; the next invocation records `up-to-date`. |

The detail and recovery text are in the [contract](contracts/branch-sync.md#causes-and-recovery). The ledger records only the cause code (see [the ledger event contract](contracts/ledger-branch-sync-event.md)).

## State transitions

```text
invocation ─▶ lock, git version and checkout shape (shallow, partial clone), in-progress (incl. index.lock), identity/pin
                 ──blocked(busy|git-unavailable|in-progress|wrong-branch)
                   (wrong-branch also: no branch pin at resume/continue, DEC-0006)
           ─▶ ls-remote, fetch if objects missing (probe in the throwaway); pin base
                 ──blocked(unknown-base|fetch-failed)
           ─▶ branch-keyed write-ahead record?  complete (recovered) or clear  (R5 table)
                 ──blocked(internal-error: invalid record | dirty: row 3b, interrupted read-tree | any R5 cause)  record kept
                 (no row pushes unless the record records a push, P-01)
           ─▶ branch kind: feature | base | other
           ─▶ published:  local < published: clean → fast-forward (AC-015, through R5), dirty → skip
                 ──blocked(diverged)
           ─▶ base ⊆ HEAD ──▶ (HEAD changed? trust recheck) ──▶ up-to-date
           ─▶ behind:  other → blocked(not-feature-branch)
                       base  → fast-forward (through R5: dirty → blocked(dirty)), or blocked(diverged)
                       dirty → blocked(dirty)
           ─▶ old base; no feature commits → fast-forward, else replay
                 ──blocked(conflict|diverged)
           ─▶ pre-mutation checks (clean, ignored overlap, read-tree --dry-run, protected diff)
                 ──blocked(dirty|busy)
           ─▶ write-ahead record ─▶ push (published feature branch only, and only when NEW != OBSERVED)
                 ──blocked(diverged|push-failed)      record kept
           ─▶ local update (read-tree -m -u, CAS update-ref)
                 ──blocked(busy)  tree reset to HEAD's tree if it still holds only NEW, record kept
           ─▶ pin base_commit, delete record
           ─▶ trust recheck (every HEAD change) ──blocked(protected-input) (kept)
           ─▶ overlap ─▶ synchronized
```

Every arrow to `blocked` before the push or a local update leaves HEAD, index, working tree and the published branch unchanged (SC-002). A later invocation always starts again from the top (AC-010); the only state it inherits is a pending write-ahead record for the branch, whatever run wrote it, which it completes or clears before classifying. Every fast-forward goes through the same pre-mutation checks, record and local update as a replay (N-10). Nothing else about a block is persisted except the ledger event and, for an Autonomous run, the block record.

## Autonomous block

An Autonomous `start` that blocks records `autonomy.make_block("upstream-sync", CONDITION, run_id=...)`:

- `condition`: `BLOCKED_UPSTREAM_SYNC (CAUSE): DETAIL. Recovery: ACTION`;
- `recovery`: "Remove the cause shown, then start the run again.";
- `command`: `ballast run start --mode autonomous ... (your original start command)` (F-06);
- `evidence`: `[]`.

The run status becomes `stopped` (`run._stop`). No decision record is written (FR-011). `ballast run continue` refuses a run whose current block is `upstream-sync` (R10).

## Stale evidence record

`<state_dir>/branch-sync/stale/<sha256(feature)[:16]>/<event_id>.json`, in operator state (SEC-003), same writer and modes as the pin, written for a kept synchronization (`synchronized`, or blocked `protected-input`) with a non-empty overlap and existing evidence (R11):

```json
{"event_id": "…", "run_id": "…", "feature": "specs/N-slug",
 "observed_at": "…", "base_ref": "main",
 "base_before": "…", "base_after": "…", "stale": ["plan", "review"],
 "paths": ["tools/x.py", "…"], "truncated": false}
```

`paths` holds at most 200 entries. The Draft PR section reads the feature's directory: it skips a file that is not regular, is over 16 KiB or does not parse, or whose `feature` does not match, and shows the newest 20 entries oldest first, with "and N earlier" before them, each path as a code span with backticks removed and `<!--` broken up, so no path can spell the section's markers (SEC-007). Keyed by feature, not run, so a continuation keeps its source run's staleness visible.
