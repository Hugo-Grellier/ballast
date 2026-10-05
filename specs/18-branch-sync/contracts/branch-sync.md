# Contract: branch synchronization check

The interface between `run.py` and `tools/spec_workflow/branch_sync.py`, and what the operator sees. Design reasons are in [research.md](../research.md); entities are in [data-model.md](../data-model.md).

## Entry point

```python
branch_sync.synchronize(
    root: Path,
    run_id: str,
    *,
    feature: str | None,       # validated feature directory: at start the Issue number (R15) and the pin; ledger attribution until the pin is read
    starting: bool = False,    # start: the run has had no agent step yet
    branch: str | None = None, # continue: the source run's pinned branch
    base: str | None = None,   # continue: the source run's recorded base
    source_run: str | None = None,  # continue: where a blocked outcome is recorded
) -> branch_sync.Outcome
```

- The run's pin is read first (R12). With `starting`, a missing pin is written with the current branch and `feature`; `base` is added only after the `ls-remote` that provides it (N-06). A `resume` whose pin lacks `branch` or `feature`, or a `continue` with `branch` `None` or a source pin without `feature`, blocks as `wrong-branch` with the recovery to start a new run and writes no pin (DEC-0006). The check never pins a branch at `resume`.
- Every input of the rewrite rule is operator state (SEC-002): the branch, the base and the Issue number come from the pin (at `resume` and `continue`) or from the operator's command (at `start`), never from `inputs.json` or another file an agent step can write. `run.py start` refuses a missing, invalid or repeated `-i feature_directory` before calling the check (E-01).
- `continue`: the current branch must equal `branch`. The continuation's pin (`branch`, `feature`, `base`, `base_commit`) is written only on a non-blocked outcome. A blocked outcome's ledger event goes to `source_run`, whose archive exists, so no archive is created for a continuation that never ran (N-07).
- The write-ahead record is read from `<state_dir>/branch-sync/<key>.json` for the current branch, whatever run wrote it (N-01).
- It never raises. An unexpected exception becomes `blocked` with cause `internal-error` and the exception class name as detail. `KeyboardInterrupt` becomes `internal-error` with the detail "interrupted", and `run.py` exits `130` (DEC-0001). Neither is ever treated as success.
- It records exactly one `branch_sync` ledger event before it returns ([event contract](ledger-branch-sync-event.md)). If recording fails, an otherwise successful outcome becomes `blocked` with cause `internal-error` and the detail "not recorded". No agent starts on an unrecorded check. The branch stays synchronized, and the next invocation records `up-to-date`.
- `run.py` prints `branch_sync.format_lines(outcome)`. On `blocked` it returns `EXIT_BLOCKED` (1), or `EXIT_INTERRUPTED` (130) for "interrupted", without calling `_launch`. In a human-gated run it does not run the Draft PR checkpoint. An Autonomous `start` first records the `upstream-sync` block through `_stop`.

## Call sites in `run.py`

| Invocation | When | `starting` | `branch` | `base` | `source_run` |
| --- | --- | --- | --- | --- | --- |
| `start` (human-gated) | after `specify` is found, before `_launch` | true | `None` | `None` | `None` |
| `start --mode autonomous` | after `write_run`, before `_launch` | true | `None` | `None` | `None` |
| `resume` | after `_resume_refusal` and `specify`, before `_launch` | false | `None` | `None` | `None` |
| `continue` | after source validation and the `upstream-sync` refusal (R10), before `append_human_decision`; the new run ID is drawn first | false | source pin's `branch` (or `None`) | source pin's `base` (or `None`) | source run ID |
| `publish` | never | — | — | — | — |

`_launch(..., start=True)` no longer calls `draft_pr.pin_branch`. The check writes the pin.

## Printed output

Success, one line on stdout:

```text
Branch sync: up-to-date feat/18-x with main (a1b2c3d4e5f6)
Branch sync: up-to-date feat/18-x with main (a1b2c3d4e5f6); published branch is ahead; not fast-forwarded: uncommitted changes
Branch sync: up-to-date feat/18-x with main (a1b2c3d4e5f6); fast-forwarded to the published branch
Branch sync: synchronized feat/18-x onto main (a1b2c3d4e5f6..0f9e8d7c6b5a), HEAD 111111111111 -> 222222222222, pushed
Branch sync: synchronized ... ; completed the interrupted synchronization from run 1a2b3c4d
Branch sync: synchronized ... ; plan and review evidence may be stale: 3 files changed on both sides (see the Draft PR)
```

Block, on stderr, exit status 1:

```text
BLOCKED_UPSTREAM_SYNC (conflict): replaying 4d3c2b1a0f9e conflicts in tools/a.py, docs/b.md
Recovery: rebase by hand: git pull --rebase origin main, resolve, then ballast run resume RUN_ID
```

Names and paths are data. Names are shell-quoted when they appear in a command and stripped of control characters everywhere else. Git's own output is never printed.

## Causes and recovery

Exactly one recovery action per cause and detail (SC-003). `{…}` are quoted values.

| Cause | Detail | Recovery |
| --- | --- | --- |
| `busy` | — | "another ballast run is synchronizing {branch}; retry when it finishes" |
| `git-unavailable` | "git not found outside working trees", "git {v} is older than 2.41" or "git version unknown" (unparsable `git version` output) | "put a system git 2.41 or later on PATH ahead of any checkout directory" |
| `git-unavailable` | "shallow checkout" | "git fetch --unshallow, then rerun" |
| `git-unavailable` | "partial clone" (DEC-0007) | "clone the repository again without --filter, then rerun" |
| `git-unavailable` | "alternate object store" (SEC-005: `objects/info/alternates` exists) | "clone the repository again without alternates, then rerun" |
| `in-progress` | "a {operation} is in progress" | "finish or abort the {operation} yourself, then rerun" |
| `in-progress` | "another git process may hold the index ({path} exists)" (P-03) | "if no git process is running, remove {path}, then rerun" |
| `wrong-branch` | "HEAD is detached" or "on {current}, run started on {pinned}"; at `start`, a detached HEAD is reported after `in-progress` (E-02) and `{pinned}` is the feature's branch name | "git switch {pinned}, then rerun" |
| `wrong-branch` | "run {id} has no branch pin", "... no feature pin" or "... no branch or feature pin" "(started before branch pinning)" (DEC-0006, SEC-002) | "start a new run: your ballast run start command" |
| `unknown-base` | "no [github] repository in ballast.toml", "{base} does not exist on {repo}" or "{repo} has no default branch" | "declare [github] repository and run ballast trust" or "restore {base} on {repo}; Ballast never substitutes another base" |
| `fetch-failed` | "could not fetch {base} from {repo}" | "check network access and credentials for {repo} (Ballast cannot answer a prompt), then rerun" |
| `not-feature-branch` | "{branch} is not the feature branch of #{issue}; Ballast rewrites only a branch named for the Issue" or "the run has no feature directory, so no Issue number" | "synchronize {branch} yourself, or run the feature on its own branch: git switch -c {feature-branch}" |
| `diverged` | "{branch} and the published branch both have commits the other lacks ({local} vs {published})", "the published branch moved during the check", "the base was rewritten and the old base is unknown" or "{branch} is the base branch and has local commits" | "reconcile by hand: git pull --rebase {remote} {branch}, then rerun", the same for a moved branch, "rebase by hand onto {base}, then rerun" or "git switch -c {new-branch}" respectively |
| `dirty` | "uncommitted changes: {paths}", "ignored files would be overwritten: {paths}" or "untracked files are in the way: {paths}" | "commit or finish these changes (Ballast never stashes or discards them), then rerun"; for ignored or untracked files: "move or commit these files, then rerun" |
| `dirty` (completing a synchronization already pushed) | "a previous synchronization already pushed {new_head}; uncommitted changes: {paths}" | "move these changes aside without committing them (Ballast never stashes or discards them), then rerun to finish the synchronization" (N-03) |
| `dirty` (completing a synchronization already pushed) | "a previous synchronization already pushed {new_head}; ignored files would be overwritten: {paths}" or "…; untracked files are in the way: {paths}" (P-06) | "move or commit these files, then rerun to finish the synchronization" |
| `dirty` (recovery row 3b: an update interrupted during `read-tree`) | "an interrupted update left these files at the synchronized content: {paths}" (P-03) | "git restore --source={new_head} --staged --worktree ., then rerun to finish the synchronization" |
| `conflict` | "replaying {commit} conflicts in {paths}" | "rebase by hand: git pull --rebase {remote} {base}, resolve, then rerun"; for a published branch "rebase by hand: git pull --rebase {remote} {base}, resolve, git push --force-with-lease={branch}:{published} {remote} {branch}, then rerun" |
| `conflict` (recovery row 5: commits made after a pushed synchronization) | "replaying {commit} onto the already pushed {new_head} conflicts in {paths}" | "git rebase --onto {new_head} {old_head} {branch}, resolve, then rerun" |
| `push-failed` | "pushing {branch} failed; a retry {can / cannot} succeed alone" | retryable: "rerun"; not: "check {repo}'s branch rules for {branch} (protection, required signatures), then rerun" |
| `protected-input` | "the base changed protected inputs: {names}" (or "the published branch changed ...") | "review these changes, then run ballast trust (operator only)" |
| `internal-error` (DEC-0001) | exception class name, "interrupted" or "not recorded" | "report it with the run ID, then rerun" |
| `internal-error` | "no committer identity" | "set user.name and user.email in your global Git configuration, then rerun" |
| `internal-error` | "invalid write-ahead record" | "report it with the run ID; Ballast keeps {record path} until you check {branch} and its published branch and delete it" |
| any cause after a successful push (`busy`, `internal-error`) | the cause's detail, then "the published branch already holds {new_head}" | "rerun to finish the synchronization" (DEC-0005) |

"rerun" means the same `ballast run` command, and the recovery prints it in full: `ballast run resume RUN_ID`, `ballast run start ...` (the original arguments are not echoed, so the text reads "your ballast run start command"), or `ballast run continue RUN_ID ...`. A blocked `continue` is retried with the same command; its event is under the source run. In an Autonomous start, the block's `command` field is the restart command, and `continue` refuses that run (R10).

## Which branches may be rewritten

Only a feature branch: its name, split at `/`, `-`, `_` and `.`, has a segment equal to the feature's Issue number, and it is neither the run's base nor the pinned repository's default branch. The base branch is only fast-forwarded and never pushed. Any other branch is never rewritten or pushed and blocks as `not-feature-branch` when behind (research R15, DEC-0003, DEC-0004).

## External commands

Every command uses the `git` resolved by `draft_pr._resolve`: an absolute `PATH` entry outside every working tree and temp root. Commands use list argv, no shell, the `draft_pr._command` environment (`GIT_LOCATION` variables dropped, child `PATH` filtered), and `autonomy.GIT_HARDENING` (`-c core.hooksPath=/dev/null -c core.fsmonitor=false`).

**In the checkout** (also with `autonomy.filter_overrides`, and with `GIT_NO_LAZY_FETCH=1` as defense in depth: partial clones are refused, and a promisor configuration that appears anyway never fetches through `origin`, N-04, DEC-0007): `symbolic-ref`, `rev-parse` (`--verify`, `--git-path`, `--git-common-dir`, `--show-object-format`, `--is-shallow-repository`), `config --get` / `--get-regexp` (`extensions.partialClone`, `remote.*.promisor`, `remote.*.partialclonefilter`, read as data, DEC-0007), `config --list --name-only -z` (filter driver names, read as data), `status --porcelain=v1 -z --ignore-submodules=dirty` (with and without `--ignored=matching`; `dirty` so no `git status` runs inside a submodule under its own configuration, SEC-001), `merge-base --is-ancestor`, `merge-base`, `rev-list --reverse --topo-order --no-merges`, `diff-tree -r --name-only --no-renames -z`, `diff-index --quiet` / `--cached --quiet`, `diff-files --quiet`, `remote get-url origin` (scheme only), `read-tree -m -u` (with and without `--dry-run`), `update-ref`, `ls-tree`, `hash-object --no-filters` without `-w` (recovery row 3b, P-03: computes a blob ID, writes no object). Every checkout command also carries `-c submodule.recurse=false -c core.commitGraph=false`, and both runners set `GIT_NO_REPLACE_OBJECTS=1` and `GIT_GRAFT_FILE=/dev/null`, so replace refs, grafts and a forged commit-graph in the agent-writable `.git` cannot change an ancestry answer (SEC-004); commit names read from `rev-list` and commit headers are validated before use. None of them reach the network, run a merge driver, sign, or start maintenance. Object-existence probes (`cat-file -e`) never run here. Ballast never runs `git restore` or `update-index`; the row-3b recovery is the operator's command. The committer identity is never read here.

**In the throwaway repository** (`git init --quiet --bare --template= --object-format=FORMAT` under `<state_dir>`, empty config, deleted afterwards):

- Every command adds `NO_MAINTENANCE` (`-c maintenance.auto=false -c gc.auto=0 -c fetch.writeCommitGraph=false -c core.commitGraph=false`) after `GIT_HARDENING`, and runs with `GIT_OBJECT_DIRECTORY=<checkout common dir>/objects`, `GIT_TERMINAL_PROMPT=0`, `GIT_NO_LAZY_FETCH=1`, `GIT_ASKPASS` empty, `SSH_ASKPASS_REQUIRE=never`, and `SSH_ASKPASS`, `DISPLAY` and `WAYLAND_DISPLAY` removed (N-09). Network commands run with `stdin` closed and in a new session, so nothing can prompt.
- Allowed commands: `update-ref refs/haves/*`, `cat-file -e` (object-existence probe, N-04), `ls-remote --symref` (30 s, every invocation), `fetch --no-tags --no-write-fetch-head` (600 s, only when an observed commit is missing locally), `git --attr-source=NEW_BASE <GIT_HARDENING> <NO_MAINTENANCE> merge-tree --write-tree --merge-base=PARENT_OF_C --name-only -z PARENT C` (the global option before the subcommand, Git 2.41, N-02), `cat-file commit`, `var GIT_COMMITTER_IDENT`, `hash-object -t commit -w --stdin`, `push --force-with-lease=refs/heads/B:OBSERVED` (600 s).
- The runner raises (never an `assert`, which `python -O` removes) on any other command (SEC-006). Recovery row 5 replays with `--attr-source` set to the fetched base, not the pushed feature commit (E-04).
- No command in the throwaway may be `gc`, `repack`, `prune`, `maintenance`, `fsck` or `commit-graph`. Its object directory is the checkout's, and its refs are not the checkout's refs, so any of them could delete the checkout's objects (research R3a).

`autonomy._push` is not changed by this feature; it keeps its own throwaway with `objects/info/alternates`.

## Guarantees

1. No agent step starts in an invocation whose check did not return `up-to-date` or `synchronized` (FR-001, SC-001).
2. Before the push (research R4 step 13), nothing but new unreferenced objects and the operator-side pin is written. Every block before then leaves HEAD, index, working tree and the published branch unchanged (FR-006, SC-002).
3. Nothing is stashed, reset, discarded or force-pushed without a lease. Ignored files are never overwritten or deleted. The base branch and any branch that is not a feature branch are never pushed or rewritten, including by the recovery of a half-done sync: no recovery row pushes unless the write-ahead record records a push (`published_old` non-null and different from `new_head`), and a fast-forward never pushes (P-01).
4. The repository comes only from `ballast.toml` and the base only from the pin or that repository's default branch (FR-002, AC-017). The pin's `base_commit` is never used as the current base (FR-003).
5. No program named by the checkout's configuration or attributes runs, and the committer identity does not come from the checkout (FR-012).
6. No command run by the check can garbage-collect, repack or prune the checkout's object store.
7. Every HEAD change made by the check is followed by the protected-input recheck before any non-blocked outcome (FR-008). A HEAD change whose invocation crashed before the recheck (recovery row 1) is covered by the launcher's `_refusal`, which refuses the next `ballast run` before the check runs (P-05).
8. A sync interrupted after its push is completed by the next invocation on the same branch without a manual step, whatever its run ID (`resume`, `continue`, the Autonomous restart, a new `start`), because the write-ahead record is keyed by branch (research R5, N-01). Its block says "rerun to finish the synchronization" (DEC-0005). One interruption point needs one printed command first: a crash during `read-tree -m -u` (recovery row 3b) prints `git restore --source={new_head} --staged --worktree .`, after which the rerun completes (P-03); a stale `index.lock` it left is reported first as `in-progress`.
9. Only `start` pins a branch; a `resume` or `continue` without a branch pin blocks as `wrong-branch` (DEC-0006).
10. "Feature branch" has one definition, `autonomy.is_feature_branch`, used by this check and by Autonomous eligibility (research R15, N-05).
