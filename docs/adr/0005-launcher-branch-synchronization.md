# ADR-0005: The trusted launcher synchronizes the feature branch before agent steps

- Status: proposed (2026-10-05, with feature 18; needs the operator's explicit approval before it is accepted)
- Feature: [18-branch-sync](../../specs/18-branch-sync/spec.md), FR-001, FR-005, FR-007, FR-012, FR-016; plan [§ Proposed architecture decisions](../../specs/18-branch-sync/plan.md#architecture-boundaries); decisions DEC-0001 to DEC-0007 in [decisions.md](../../specs/18-branch-sync/decisions.md)
- Extends: [ADR-0003](0003-launcher-github-authority.md)

## Context

A run can pause for days while its base advances. Agents must not plan, implement or review against a stale base, and they cannot update the branch themselves: they are denied `git push`, and the checkout's Git configuration, attributes and hooks are agent-writable (BL-INV-002, BL-INV-003). Rebasing and pushing the feature branch therefore has to happen on the operator's side, before any agent step, with the operator's Git credentials. ADR-0003 gave the launcher GitHub API authority; this decision extends it to Git transport.

## Decision

- **Where**: `tools/spec_workflow/branch_sync.py`, imported by the trusted `run.py` at startup, after the launcher verified the protected inputs. `run.py` calls it once per `ballast run start`, `resume` and `continue` invocation, before the first agent step. `publish` runs no agent and no check. No agent step can invoke, skip or configure it.
- **Authority**: the check may fetch from, and push with a lease to, only the repository pinned under `[github] repository` in the protected `ballast.toml`, never a remote named by the checkout. It may rewrite only the run's feature branch.
- **Rewrite rule** (DEC-0003, DEC-0004): a feature branch is one whose name, split at `/`, `-`, `_` and `.`, has a segment equal to the feature's Issue number, and that is neither the run's base nor the pinned repository's default branch. One predicate decides it, `autonomy.is_feature_branch`, shared with Autonomous eligibility.
  - Only a feature branch is replayed or pushed.
  - The base branch is only fast-forwarded locally, never replayed or pushed; local-only commits there block as `diverged` with the recovery `git switch -c BRANCH`. Its published branch is the base itself, so the published-branch fast-forward does not apply to it.
  - Any other branch is never rewritten or pushed and blocks as `not-feature-branch` when it is behind.
  - The Issue number comes from operator state only: the feature directory of the operator's `ballast run start` command, pinned with the branch before the first agent step; `resume` and `continue` read it from that pin, never from agent-writable run state. A human-gated `start` without exactly one valid `-i feature_directory` is refused before the check. Bugfix and assess runs started with `specify` directly do not pass through `ballast run` and are not synchronized.
- **Throwaway repository**: every network or merge operation (`ls-remote`, `fetch`, `merge-tree`, `hash-object`, `var`, `push`), and the object probes and reads that go with them (`cat-file`, `rev-parse` of the fetched `refs/sync/*`, `update-ref` of negotiation hints), runs in a bare repository created under the operator state directory with `git init --bare --template=` and the checkout's object format, with an empty configuration, deleted afterwards. The runner refuses any other command. It shares the checkout's object store through `GIT_OBJECT_DIRECTORY`, so every command there adds `-c maintenance.auto=false -c gc.auto=0 -c fetch.writeCommitGraph=false -c core.commitGraph=false`, and no `gc`, `repack`, `prune`, `maintenance`, `fsck` or `commit-graph` command ever runs there. No command can prompt: `GIT_TERMINAL_PROMPT=0`, `GIT_ASKPASS` empty, `SSH_ASKPASS` removed, `SSH_ASKPASS_REQUIRE=never`, no display, `stdin` closed and a new session for network commands.
- **The checkout** sees only local plumbing (`symbolic-ref`, `rev-parse`, `config --get`, `config --get-regexp` and `config --list --name-only`, read as data, `remote get-url origin`, of which only the scheme is used, `status --ignore-submodules=dirty`, `merge-base`, `rev-list`, `diff-tree`, `diff-index`, `diff-files`, `ls-tree`, `read-tree`, `update-ref`, `hash-object --no-filters` without `-w`), with hooks, fsmonitor, the commit-graph, submodule recursion and every configured filter driver disabled and `GIT_NO_LAZY_FETCH=1`. `status` never enters a submodule, whose own configuration could name a filter. No program named by its configuration, attributes or hooks runs.
- **Environment**: the operator's environment minus Git location variables and injected configuration (`GIT_CONFIG_PARAMETERS`, `GIT_CONFIG_COUNT`, `GIT_CONFIG_KEY_*`, `GIT_CONFIG_VALUE_*`), with `PATH` limited to entries outside every working tree and temp root, and with `GIT_NO_REPLACE_OBJECTS=1` and `GIT_GRAFT_FILE=/dev/null`, so replace refs and grafts in the agent-writable `.git` cannot change ancestry answers. `GIT_CONFIG_GLOBAL` and the system configuration are the operator's and stay in effect, as do the operator's own `GIT_EXEC_PATH`, `GIT_SSH_COMMAND` and `GIT_PROXY_COMMAND`.
- **Committer identity** comes from the operator's environment and global or system configuration (`git var GIT_COMMITTER_IDENT` in the throwaway), never from the checkout.
- **Pin**: only `ballast run start` pins a run's branch and feature directory, before the first agent step; a continuation inherits its source run's pin. A `resume` or `continue` of a run whose pin lacks the branch or the feature blocks as `wrong-branch` (DEC-0006).
- **Refused shapes**: shallow checkouts, partial clones and checkouts with `objects/info/alternates` block as `git-unavailable` (DEC-0007; alternates would let the shared store read and push another store's objects), as does a `git` older than 2.41 or found only in a working tree or temp root (DEC-0001).
- **Order**: every local refusal is checked before anything is pushed; then a branch-keyed write-ahead record is written under the operator state directory; then a published feature branch is pushed with `--force-with-lease` on the observed commit; then the checkout moves with `read-tree -m -u` and a compare-and-swap `update-ref`. A sync interrupted after its push is completed by the next invocation on the branch, whatever its run ID (DEC-0005). No recovery of a half-done sync pushes unless its record records a push, so a fast-forward record can never push the base or another branch.
- **Trust**: every HEAD change made by the check is followed by the launcher's own protected-input comparison. A change blocks as `protected-input` and keeps the synchronization, so the operator can review it and run `ballast trust` (DEC-0002).
- **Differences from `git rebase`**: replayed commits are unsigned; merge attributes come from the fetched base (`git --attr-source=BASE merge-tree`), not from each replayed commit or the feature branch; no `rebase.*` configuration applies; merge commits are dropped and their non-merge commits replayed, as `git rebase` does by default.

## Consequences

- Agents always start on a branch that contains the base observed in the same invocation, or no agent starts and the operator gets one cause and one recovery action.
- The launcher now rewrites and force-pushes (with a lease) one branch with operator credentials. The set of branches it may touch is fixed in code by the rewrite rule above.
- A project needs Git 2.41 or later on `PATH` outside every checkout; `ballast doctor` reports the floor.
- Later features extend this boundary by a new ADR: #21 (Autonomous `resume` through synchronization) and roadmap item 4 (branch-level exclusion for the whole invocation).

## Rejected alternatives

- `git rebase` in the checkout, even with `-c` overrides: no override list covers every program-running key, so merge drivers, `gpg.program`, `core.sshCommand` and hooks would run with operator authority.
- Fetching or pushing through `origin`: its URL, `pushurl`, `insteadOf` and `sshCommand` are agent-writable.
- A workflow step that synchronizes: an agent-visible step can be skipped by a resume that starts after it.
- A check in `launcher.py` before `execv`: it would need the run identity, the ledger and the Autonomous record, which belong to `run.py`.
- An operator allowlist of branch patterns in `ballast.toml` (DEC-0004 option B), not chosen.
