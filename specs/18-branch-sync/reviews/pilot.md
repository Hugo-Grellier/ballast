# Scratch-repository pilot (T052)

- Date: 2026-10-05
- Host: Linux, systemd user session, Git 2.53.0, Spec Kit CLI 1.0.11
- Repository: private disposable scratch repository on GitHub, pinning this branch through `BALLAST_STANDARD_DIR`; feature branch `feat/9-sync-pilot` (one commit, published)
- Run: human-gated `ballast-feature`, paused at its first gate (`scope-gate`) every time; no agent step ran.

## Finding and fix

The first pass of step 5 failed SC-003: the conflict recovery said `git rebase main`, but the check observes the base with `ls-remote` and never updates local `main` or `origin/main`, so the rebase reported "up to date" and changed nothing. And for a published branch the by-hand rebase rewrites the published commits, so the next invocation would block `diverged`. The recovery now reads `git pull --rebase origin {base}`, and for a published branch adds `git push --force-with-lease={branch}:{published} origin {branch}` before the rerun. `PublishedBranchTests.test_conflict_recovery_works_as_printed` follows the printed recovery literally. A second fix: `run.py` flushes stdout after the sync line, which a piped log otherwise showed after the engine's output.

## Transcript

Step 1, start:

```
$ ballast run start -i idea="Issue #9: sync pilot" -i feature_directory=specs/9-sync-pilot
ballast: using local standard <this worktree>

Running workflow: Ballast Feature Workflow (ballast-feature)
Version: 1.1.0

  ▸ [preflight] shell …
  ▸ [scope-gate] gate …

Status: paused
Run ID: 5a8dbf79

Resume with: specify workflow resume 5a8dbf79
Branch sync: up-to-date feat/9-sync-pilot with main (536f7adfa5ba)

Run 5a8dbf79: paused at step scope-gate
Agent logs: .specify/workflow-state/5a8dbf79/agents/
Draft PR: blocked-unlinked (issue-not-found): create the Issue, or fix the number in the feature directory
exit 0
```

Step 2, a non-conflicting commit on `main` (GitHub contents API):

```
5cc0fd8c2d3e4f1b07c88067206b18121fe42136
```

Step 3, resume:

```
$ ballast run resume 5a8dbf79
ballast: using local standard <this worktree>
  ▸ [scope-gate] gate …

Status: paused
Branch sync: synchronized feat/9-sync-pilot onto main (536f7adfa5ba..5cc0fd8c2d3e), HEAD 463c5b5ac8ae -> aca415b0b0a2, pushed

Run 5a8dbf79: paused at step scope-gate
Agent logs: .specify/workflow-state/5a8dbf79/agents/
Draft PR: blocked-unlinked (issue-not-found): create the Issue, or fix the number in the feature directory
exit 0
$ git log --oneline -4
aca415b docs: add the sync pilot note
5cc0fd8 docs: upstream change A (pilot step 2)
536f7ad docs: adopt the Ballast AGENTS.md template
5a3cc5b chore: let agents run env-prefixed quickstart commands
$ git ls-remote origin feat/9-sync-pilot
aca415b0b0a2d17daa771e9a43009bf21c86da81	refs/heads/feat/9-sync-pilot
```

Step 4, a conflicting commit on `main` (`notes/sync-pilot.md` added upstream), then resume. HEAD and `git status` are unchanged and no agent log directory exists:

```
$ git status --porcelain; git rev-parse HEAD (before)
aca415b0b0a2d17daa771e9a43009bf21c86da81
$ ballast run resume 5a8dbf79
ballast: using local standard <this worktree>
BLOCKED_UPSTREAM_SYNC (conflict): replaying aca415b0b0a2 conflicts in notes/sync-pilot.md
Recovery: rebase by hand: git rebase main, resolve, then ballast run resume 5a8dbf79
exit 1
$ git status --porcelain; git rev-parse HEAD (after)
aca415b0b0a2d17daa771e9a43009bf21c86da81
ls: cannot access '.specify/workflow-state/5a8dbf79/agents/': No such file or directory
```

Step 5, first pass: the old recovery did nothing (the finding above):

```
$ git rev-parse main origin/main
536f7adfa5ba52be158f6e0dbcab3efc347174db
536f7adfa5ba52be158f6e0dbcab3efc347174db
$ git rebase main
Current branch feat/9-sync-pilot is up to date.
exit 0
```

After the fix (`ballast setup` and `ballast trust` in the scratch repository), step 4 again:

```
$ ballast run resume 5a8dbf79
ballast: using local standard <this worktree>
BLOCKED_UPSTREAM_SYNC (conflict): replaying aca415b0b0a2 conflicts in notes/sync-pilot.md
Recovery: rebase by hand: git pull --rebase origin main, resolve, git push --force-with-lease=feat/9-sync-pilot:aca415b0b0a2d17daa771e9a43009bf21c86da81 origin feat/9-sync-pilot, then ballast run resume 5a8dbf79
exit 1
```

Step 5, the printed recovery followed literally, then resume:

```
$ git pull --rebase origin main
Auto-merging notes/sync-pilot.md
CONFLICT (add/add): Merge conflict in notes/sync-pilot.md
error: could not apply aca415b... docs: add the sync pilot note
Could not apply aca415b... # docs: add the sync pilot note
$ (resolve) printf ... > notes/sync-pilot.md; git add; git rebase --continue
 1 file changed, 1 insertion(+)
$ git push --force-with-lease=feat/9-sync-pilot:aca415b0b0a2d17daa771e9a43009bf21c86da81 origin feat/9-sync-pilot
exit 0
$ ballast run resume 5a8dbf79
ballast: using local standard <this worktree>
Branch sync: up-to-date feat/9-sync-pilot with main (2ad1b68ec49f)
  ▸ [scope-gate] gate …

Status: paused

Run 5a8dbf79: paused at step scope-gate
Agent logs: .specify/workflow-state/5a8dbf79/agents/
Draft PR: blocked-unlinked (issue-not-found): create the Issue, or fix the number in the feature directory
exit 0
$ git log --oneline -4
4cc7068 docs: add the sync pilot note
2ad1b68 docs: conflicting upstream note (pilot step 4)
5cc0fd8 docs: upstream change A (pilot step 2)
536f7ad docs: adopt the Ballast AGENTS.md template
```

- Verdict: PASS (AC-001, AC-007, SC-003, SC-004)
