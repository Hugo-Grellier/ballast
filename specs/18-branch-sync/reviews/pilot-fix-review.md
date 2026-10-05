# Pilot fix review (security + engineering)

- Scope: `git diff 015c490..544af68` (branch `feat/18-branch-sync`): `RECOVERY["conflict"]`, the new `RECOVERY["conflict-published"]`, `_Sync.conflict`, the `run.py` stdout flush, `test_conflict_recovery_works_as_printed`, and the contract, policy, decisions and tasks text.
- Reviewer: Claude Opus (same provider as the author), 2026-10-05.
- Gate: `uv run --no-project --isolated --python 3.13 --with pyyaml python -m unittest tests.test_branch_sync`: `Ran 80 tests ... OK`.
- Regression check: `branch_sync.py` from `015c490` overlaid on a `git archive 544af68` copy fails the new test (the recovery string assertion fails: `git rebase main` versus the new text).

## What holds

- **Reachability.** `conflict()` is only called from `replay()`. `replay()` is called from `rebase_feature()` and from recovery row 5 in `recover()`. Row 5 always passes `pushed=new`, so it takes `conflict-pushed` before the new branch. `rebase_feature()` runs only when `kind() == "feature"`. `autonomy.is_feature_branch` excludes both the run's base and the repository default, and `classify` stops on `base` and `other` first. So `conflict-published` cannot print a force-push for the base or default branch.
- **Lease value.** `self.published` comes from the `ls-remote` advertisement or `rev-parse refs/sync/published`, and both are validated with `COMMIT.fullmatch`, so it is a full 40- or 64-hex SHA. `shlex.quote` leaves it unchanged. By the time `rebase_feature` runs, `follow_published` has either fast-forwarded to it, returned because it equals or is an ancestor of the head, or blocked with `diverged`. The local dirty case blocks in `rebase_feature` first. So the lease names the published commit this invocation observed, and that commit is an ancestor of what the operator rebases. If anyone pushes in the meantime, the lease fails closed.
- **Row 5 interplay.** The precedence is right. When the branch was pushed by an earlier synchronization, the operator gets `git rebase --onto {new_head} {old_head} {branch}`. The result descends from the published head, so no force-push is needed or printed.
- **Pilot evidence.** `reviews/pilot.md` lines 99-113 show the published-branch recovery (`conflict-published`) run by hand against GitHub and passing.
- **Recovery semantics.** `git pull --rebase origin <base>` fetches the base itself, which fixes the pilot defect: `ls-remote` never updates the local base. For a published branch, the follow-up push is needed, because otherwise the next invocation blocks with `diverged`.
- **`run.py` flush.** This is correct and enough. `stderr` is line-buffered in Python 3.9 and later, and the engine writes after `_sync` returns.

## Findings

### PFR-01 (medium, security / implementation bug): a branch name starting with `+` makes the printed push force a different branch without a lease

`_recovery` replaces values that start with `-` with a placeholder, but `shlex.quote("+x-18")` returns `+x-18` unchanged. `+x-18` is a valid ref name (`git check-ref-format refs/heads/+x-18` succeeds), and it is a feature branch for Issue 18, because `is_feature_branch` splits names at `-` and finds the segment `18`. The printed command is then:

```
git push --force-with-lease=+x-18:<sha> origin +x-18
```

Git reads the refspec `+x-18` as "force-push local `x-18` to remote `x-18`". The lease names a ref that is not being pushed, so it protects nothing. I reproduced this in a scratch repository: the command printed `+ b25dc01...f979129 x-18 -> x-18 (forced update)` and left `+x-18` untouched. So a command printed by the trusted launcher, run as printed, overwrites an unrelated branch with no lease. Before this delta, no recovery text printed a push.

Fix (pick one):
- Treat a leading `+` like a leading `-` in `_recovery`, for branch-type values, and add a test.
- Or make the push unambiguous: `git push --force-with-lease=refs/heads/{branch}:{published} {remote} HEAD:refs/heads/{branch}`.

Either way, also guard the `{branch}` refspec position in `diverged` (`git pull --rebase origin +x-18` forces a fetch into `FETCH_HEAD`, which does no harm, but the inconsistency is still there).

### PFR-02 (low, architecture issue): `{remote}` = `origin` is not the repository the check trusted

The check reads the base and the published branch from the pinned `[github] repository` URL, and never from `origin`. In a fork layout (`origin` = fork, `upstream` = pinned repository), the printed `git pull --rebase origin main` rebases onto the fork's base, which may be stale. The push goes to the fork, where the lease SHA from the pinned repository will usually not match. That is a safe refusal, but a confusing one. In a checkout with no `origin`, both commands fail. This is not a vulnerability: the operator runs the commands, and the lease fails closed. The same pattern already exists in `diverged`. Consider printing the pinned repository URL (`{repo}`) in place of the remote name, since that is what the lease was observed against. Otherwise, document the assumption that `origin` is the pinned repository next to the policy table.

### PFR-03 (low, security / documentation): the recovery now has the operator run `git push` in an agent-writable checkout

Ballast's own Git calls disable hooks, fsmonitor and filters. The operator's by-hand `git pull` and `git push` do not, so `.git/hooks/pre-push`, `core.hooksPath`, `core.fsmonitor` and `url.*.insteadOf` from the checkout's config run under the operator's credentials. This is not new in kind: the old `git rebase` and the `diverged` `git pull` already ran Git there. The push adds the `pre-push` hook and credential-bearing transport. Consider one sentence in the policy section saying that by-hand recovery runs the checkout's Git configuration and hooks as the operator.

### PFR-04 (low, missing test): the test runs a hand-copied command, not the printed one

`test_conflict_recovery_works_as_printed` asserts the exact string. That assertion is what fails on the old code, so the regression is covered. It then runs `pull` and `push` with hard-coded argv, so a drift between the template and what the test executes would only be caught through the string assertion. Quoting and placeholders are not exercised: `BRANCH` is a plain name. A stronger test would `shlex.split` the two commands out of `outcome.recovery` and run them, and would add one case with a branch name that needs quoting or starts with `+` (see PFR-01). The rest of the test is sound. Local `main` is stale (`advance_base` pushes through a separate clone), the pull really conflicts (asserted through `--diff-filter=U`), the lease is the SHA observed before the check, and the final check returns `up-to-date`, which shows that `diverged` no longer follows.

## Verdict

PFR-01 is a small, local fix to `_recovery` or the template, plus one test. With that change, the rest of the delta is correct and safe to print.

- Verdict: APPROVE WITH CHANGES

## Resolution (2026-10-05)

- PFR-01: fixed. `_recovery` prints a placeholder for a value starting with `+` as for `-`; `test_names_are_quoted_and_escaped` asserts `+x-18` never reaches the printed push.
- PFR-02, PFR-03: documented in the policy section, before "What the check never does": `origin` must name the pinned repository, and the by-hand recoveries run Git in the checkout with the operator's credentials.
- PFR-04: accepted as is; the PFR-01 assertion covers the `+`/`-` quoting the review asked for.
