# Feature Specification: Branch Synchronization Before Agent Steps

**Feature Branch**: `feat/18-branch-sync`

**Created**: 2026-10-05

**Status**: Implemented, pending merge

**Input**: User description: "Issue #18: no workflow agent starts on a feature branch known to be behind its authoritative base."

**Tracking**: [Ballast #18](https://github.com/Hugo-Grellier/ballast/issues/18); roadmap Priority 3, item 3 "Upstream synchronization before each invocation" ([product roadmap](../../docs/plans/2026-10-02-product-roadmap.md)); [technical spec §90 and §91](../TECHNICAL-SPEC.md#90-v03-target) ("safe branch synchronization on start and resume"). Consumers named elsewhere: the Autonomous resume refusal ([#27 FR-023](../27-autonomous-core/spec.md)) and the Draft PR base ([#17 assumptions](../17-draft-pr/spec.md)).

**Source note**: the specify step could not read the Issue body (agents are denied `gh`, and human-gated runs have no Issue snapshot). At the intent gate the operator reconciled this spec with the Issue's scope and acceptance criteria: serializing branch mutation (AC-019, AC-020, FR-016) is in scope as the Issue states, and the Issue's "unsafe overlap" is overlap with protected inputs, which blocks (AC-016), while overlap with plan or review evidence is marked stale (AC-018).

## Overview

A feature run can pause for hours or days. Meanwhile the base branch (usually `main`) keeps moving: new policies, a new Ballast pin, fixes to code the feature touches. Today `ballast run start`, `resume` and `continue` start agents on the branch as it is, so agents can plan, implement and review against a stale base. Their output then conflicts or is wrong when it reaches the PR.

With this feature, the trusted launcher checks the feature branch against its authoritative base before any workflow agent runs. If the branch is behind and can be updated safely, the launcher updates it, records the update and continues. Otherwise it stops before any agent starts and reports `BLOCKED_UPSTREAM_SYNC`, the cause and one recovery action. The launcher never discards local work and never guesses when it cannot determine the branch's state.

## User Scenarios & Testing *(mandatory)*

Each acceptance scenario has a stable ID (`AC-001`, `AC-002`, ...). Task and test descriptions cite the IDs they satisfy, so review can trace each criterion to evidence.

### User Story 1 - Resume on the current base (Priority: P1)

An operator paused a feature run and `main` advanced in the meantime. When the operator resumes or continues the run, the launcher brings the feature branch up to date with the base before the next agent step, so every agent works from the current base. The operator sees that the branch was synchronized and from which base to which.

**Why this priority**: This is the stale-resume failure the roadmap names, and the guarantee the Issue title states. Without it, every later artifact may rest on an outdated base.

**Independent Test**: Start a run in a scratch repository and pause it at a gate. Add a commit to the base that does not conflict, then resume. The next agent step runs on a branch that contains the new base commit, and the run ledger records the old base, the new base and the resulting HEAD.

**Acceptance Scenarios**:

1. **AC-001**: **Given** a paused run whose branch is clean, unpublished and behind the base with no conflicts, **When** the operator runs `ballast run resume`, **Then** the branch is rebased onto the current base before any agent step starts, and the next agent step runs on the rebased branch.
2. **AC-002**: **Given** a run whose branch already contains the current base, **When** any `ballast run` invocation that starts agent steps begins, **Then** the branch is left unchanged and the ledger records the outcome `up-to-date`.
3. **AC-003**: **Given** a successful synchronization, **When** it completes, **Then** the run ledger records the base reference, the previous and new base commits, the previous and resulting HEAD and the outcome `synchronized`, and `ballast run` output shows them in one line.
4. **AC-004**: **Given** a new run started with `ballast run start` on a branch that is behind the base, **When** the start proceeds, **Then** the branch is synchronized as in AC-001 before the first agent step.
5. **AC-005**: **Given** `ballast run continue` (the Autonomous-to-human-gated continuation), **When** it starts agent steps, **Then** the same check runs first.

---

### User Story 2 - Stop safely when the branch cannot be updated (Priority: P1)

Sometimes the launcher cannot update the branch safely: the checkout has uncommitted changes, the rebase conflicts, the base cannot be fetched, or someone else has pushed to the published feature branch. In each case the launcher leaves the branch and the working tree exactly as they were, starts no agent, and tells the operator what is wrong and the one action to take.

**Why this priority**: The guarantee includes refusing when the state is unknown or unsafe. An unsafe automatic rebase that loses or rewrites work is worse than a stale branch.

**Independent Test**: Force each blocking cause in a scratch repository. Each invocation exits before any agent step with `BLOCKED_UPSTREAM_SYNC`, a named cause and a recovery command. Afterwards the branch HEAD, the working tree and the index are unchanged, and no rebase is left in progress.

**Acceptance Scenarios**:

1. **AC-006**: **Given** a branch behind the base whose working tree or index has uncommitted changes, **When** an invocation begins, **Then** nothing is rebased, no agent starts, and the report names the cause `dirty` and tells the operator how to commit or finish the local changes without discarding them.
2. **AC-007**: **Given** a branch whose replay onto the base conflicts, **When** an invocation begins, **Then** the branch HEAD, index and working tree are left as they were (the replay runs outside the checkout, so there is nothing to abort), no agent starts, and the report names the cause `conflict`, the conflicting commit and the conflicting paths.
3. **AC-008**: **Given** the base cannot be fetched (network failure, missing credentials, unknown repository or base reference), **When** an invocation begins, **Then** no agent starts and the report names the cause `fetch-failed` or `unknown-base`. The launcher does not fall back to a cached base and does not treat the branch as current.
4. **AC-009**: **Given** a checkout with an operation already in progress (rebase, merge, cherry-pick, revert or bisect) or a stale `index.lock`, a detached HEAD, or a branch other than the one the run started on, **When** an invocation begins, **Then** no agent starts and the report names the cause.
5. **AC-010**: **Given** any blocked synchronization, **When** the operator removes the cause and invokes the run again, **Then** the check runs again from the beginning. The only state carried over is the write-ahead record of a synchronization that was already pushed or half-applied, which the next invocation on the branch completes or clears (DEC-0005).
6. **AC-011**: **Given** an Autonomous run whose synchronization is blocked, **When** the block is reported, **Then** it is recorded as a block in its own category, `upstream-sync`, alongside the existing block categories, and recovered by removing the cause and starting the run again (`ballast run start --mode autonomous ...`). `ballast run continue` refuses it: no agent step ran, so there is nothing to continue.
7. **AC-019**: **Given** another `ballast run` invocation is synchronizing the same branch, **When** a second invocation begins, **Then** it does not touch the branch, no agent starts, and the report names the cause `busy` and tells the operator to retry after the other invocation finishes.
8. **AC-020**: **Given** two invocations race to synchronize the same branch, **When** both run, **Then** at most one mutates the branch, the other blocks with `busy`, and the branch ends in a state one invocation alone could produce.
9. **AC-021**: **Given** a run on a branch that is not a feature branch (for example `develop`), behind the base, **When** an invocation begins, **Then** the branch and its published copy are not rewritten, no agent starts, and the report names the cause `not-feature-branch` (DEC-0004).

---

### User Story 3 - Keep a published branch and its PR consistent (Priority: P2)

Once the feature branch is on GitHub (for example after #17 opened its Draft PR), rebasing it locally is not enough: the published branch must move as well, without overwriting commits someone else pushed.

**Why this priority**: Published branches are the normal case after the first implementation commit. A rebase that is not pushed, or a push that overwrites other commits, would break the one-Draft-PR guarantee from #17.

**Independent Test**: Publish the feature branch, advance the base, and resume. The published branch is updated to the rebased HEAD only if it still points where the launcher last saw it. If someone pushed in between, the run blocks and both the local and the published branch keep their commits.

**Acceptance Scenarios**:

1. **AC-012**: **Given** a published branch with no commits beyond the local branch, behind the base, **When** synchronization rebases it, **Then** the published branch is updated to the rebased HEAD, but only if it still points at the commit observed before the rebase.
2. **AC-013**: **Given** the published branch moved after the launcher observed it, or holds commits the local branch lacks, **When** synchronization runs, **Then** neither branch is rewritten, no agent starts, and the report names the cause `diverged` and how to reconcile the two.
3. **AC-014**: **Given** the push of the rebased branch fails for any reason, **When** the failure is detected, **Then** the local branch is still at its previous HEAD (the push precedes the local update), no agent starts, and the report says whether a retry alone can succeed.
4. **AC-015**: **Given** the local branch is strictly behind its own published branch (no local-only commits) and clean, **When** an invocation begins, **Then** it is fast-forwarded to the published branch before the base check; nothing is pushed, the ledger event carries `fast_forwarded`, and the outcome is `up-to-date` when the base is then contained or `synchronized` when a rebase follows. With uncommitted changes the fast-forward is skipped with a printed note when the base is contained, and the run blocks with `dirty` otherwise. [Assumption A-4]

---

### User Story 4 - Never let synchronization bypass the trust boundary (Priority: P1)

The base may change protected workflow inputs, for example a new `ballast.toml` pin or a policy update. A rebase must not quietly bring changed protected inputs into a run the operator trusted under different inputs.

**Why this priority**: Synchronization is the first launcher step that rewrites the checkout an agent will use. If it skipped the trust check, any commit on the base could change what agents are allowed to do.

**Independent Test**: Advance the base with a change to `ballast.toml` and resume. The rebase completes, the trust recheck fails closed, no agent starts, and the report tells the operator to review the change and run `ballast trust`.

**Acceptance Scenarios**:

1. **AC-016**: **Given** a synchronization that changes a protected input (`ballast.toml`, `.ballast/`, `.specify/`, `.venv/`), **When** the rebase completes, **Then** the trust check runs again on the result, fails closed, no agent starts, and the report names the changed inputs and says that only the operator can run `ballast trust`.
2. **AC-017**: **Given** any invocation, **When** synchronization runs, **Then** it runs after launcher trust verification and before any agent step. No agent can run, skip or influence it, and it reads the base location only from operator-controlled configuration, never from an agent-writable remote setting.
3. **AC-018**: **Given** synchronization changed files the feature's existing plan or review evidence covers, **When** it completes, **Then** the launcher records the overlapping files, marks the affected plan and review evidence stale in the run ledger and the Draft PR, and continues. It adds no gate and re-runs no review; the human approving the merge sees the staleness.

---

### Edge Cases

- **Base advanced only in the feature's own spec directory, or by an empty commit**: still counts as behind. The branch is synchronized, because "behind" means the base commit is not in the branch's history.
- **The run's recorded base was deleted or renamed upstream**: `unknown-base`. The launcher never substitutes the default branch for a recorded base.
- **The branch has no commits beyond the base**: it is fast-forwarded to the base. Nothing is published unless the branch was already published.
- **The base was rewritten (force-pushed) since the last synchronization**: the rebase uses the previously recorded base commit as the old base when it is still known. Otherwise the run blocks with cause `diverged` rather than replaying base commits onto the branch.
- **Ignored, rebuildable files that Ballast installs** (for example `.agents/skills/ballast-*`): they are not uncommitted changes and do not count as dirty.
- **Interrupted synchronization** (Ctrl-C or a crash): before the push and the local update, the next invocation finds nothing to complete and clears the write-ahead record. After a successful push, or between the steps of the local update, the next invocation on the branch, whatever its run ID, completes the synchronization from the write-ahead record and says so (DEC-0005). A Git operation left in progress blocks first with `in-progress`, and an update interrupted while writing the working tree blocks with `dirty` and the one command `git restore --source=NEW_HEAD --staged --worktree .`; the launcher never resumes a half-done Git operation on its own.
- **Repeated invocations with no base change**: each records `up-to-date` and changes nothing.
- **A run whose pin lacks the branch or the feature directory** (started before #17, or before #18 pinned the feature): `resume` and `continue` block with `wrong-branch` and the recovery to start a new run. The check never pins a branch or a feature after an agent step could have changed HEAD or the run's inputs (DEC-0006, SEC-002).
- **The run's branch is the base itself** (for example a run started on `main`): it is only fast-forwarded, never replayed or pushed; local-only commits block with `diverged` and the recovery `git switch -c BRANCH` (DEC-0003).
- **Two invocations on the same branch at the same time**: the second blocks with `busy` (AC-019, AC-020). The lock covers synchronization only; branch-level exclusion for the whole invocation remains roadmap item 4.
- **Bugfix and assess workflows**: `ballast run` starts only the feature workflows, which always name a feature directory; bugfix and assess runs started with `specify` directly are not synchronized.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Every `ballast run` invocation that may start a workflow agent step (`start`, `resume`, `continue`) MUST run the synchronization check after launcher trust verification and before the first agent step. A human-gated `ballast run start` MUST name exactly one valid `-i feature_directory=specs/<issue>-<slug>`; otherwise it is refused (exit 2) before the check, so the check always knows the Issue number it pins.
- **FR-002**: The authoritative base MUST be the base the run recorded at start. If the run recorded none, it MUST be the default branch of the repository pinned in operator-controlled configuration. It MUST NOT come from agent-writable git configuration or files. The branch, the base and the Issue number the rewrite rule uses come from the run's pin, written by `ballast run start` from the operator's command, or from that command itself at `start`; never from agent-writable run inputs.
- **FR-003**: The check MUST observe the current base commit from the pinned repository on every invocation (`ls-remote`), and fetch its objects when they are missing locally. When the observation or the fetch fails, or the base cannot be resolved, the result MUST be `BLOCKED_UPSTREAM_SYNC` with no fallback to a previously observed base; the pin's `base_commit` is never used as the current base.
- **FR-004**: A branch MUST count as behind exactly when the fetched base commit is not an ancestor of the branch HEAD.
- **FR-005**: When the branch is behind, clean, on the run's recorded branch, a feature branch (its name contains the feature's Issue number as a whole segment, and it is neither the base nor the pinned repository's default branch; DEC-0004) and has no operation in progress, the launcher MUST rebase it onto the fetched base. A behind branch that is not a feature branch MUST NOT be rewritten; the run blocks with `not-feature-branch`. A run on its base branch only fast-forwards (DEC-0003). A replay that conflicts MUST leave the branch at its previous HEAD; no rebase is ever left in progress.
- **FR-006**: The launcher MUST NOT discard, stash, reset or overwrite uncommitted changes, local-only commits or published commits. Every blocked outcome MUST leave the branch HEAD, index and working tree as they were before the invocation, with the exceptions SC-002 names.
- **FR-007**: For a published feature branch, the rebased HEAD MUST be pushed before the local branch moves, and only on the condition that the published branch still points at the commit observed in the same invocation. When that condition fails, or the push fails, the local branch MUST be left at its previous HEAD and the run blocked. A failure after a successful push leaves the published branch at the rebased commit; the next invocation on the branch, whatever its run ID, completes the synchronization from the write-ahead record (DEC-0005).
- **FR-008**: Whenever synchronization changed HEAD (a rebase or a fast-forward), the launcher MUST re-run the protected-input trust check and fail closed on any change, as for any other protected-input change (DEC-0002).
- **FR-009**: Each check MUST record one outcome in the run ledger: `up-to-date`, `synchronized` or `blocked`. It MUST record the base reference, the previous and current base commit, and the previous and resulting HEAD, each when the check got far enough to know it; a blocked outcome records what it knew. A blocked outcome MUST also record its cause: `dirty`, `conflict`, `fetch-failed`, `unknown-base`, `in-progress`, `wrong-branch`, `diverged`, `push-failed`, `protected-input`, `busy`, `not-feature-branch`, `git-unavailable` (no trusted `git` 2.41 or later, a shallow checkout, a partial clone, or a checkout with `objects/info/alternates`; DEC-0001, DEC-0007) or `internal-error` (an unexpected failure, an interrupted check or a failed ledger write; it still blocks) (DEC-0001, DEC-0004).
- **FR-010**: A blocked outcome MUST print `BLOCKED_UPSTREAM_SYNC`, the cause, the relevant detail (the conflicting commit and paths, the changed protected inputs, the local and published commits when both are known), and one recovery action. It MUST then exit with a non-zero status before any agent step starts.
- **FR-011**: In an Autonomous run, a blocked synchronization MUST be recorded as a block in its own category and recovered through the existing block-recovery path. A synchronization MUST NOT be recorded as a decision of any kind.
- **FR-012**: Synchronization MUST run only in trusted launcher code. No agent step can invoke, skip or configure it, and it MUST NOT execute code from the checkout being synchronized (for example, repository git hooks during rebase or push).
- **FR-013**: Every input that comes from the repository or remote (branch names, commit messages, conflicting paths) MUST be treated as untrusted data: shown as text, never run as code or passed to a shell.
- **FR-014**: The operator documentation (the installed Spec Kit workflow policy and `ballast run` help) MUST describe the check, each blocked cause and its recovery action.
- **FR-015**: When synchronization changes files that existing plan or review evidence covers, the launcher MUST record the overlapping files, mark that evidence stale in the run ledger and the Draft PR, and continue (AC-018).
- **FR-016**: Synchronization MUST hold a per-branch lock in the operator's state directory, outside every agent's write authority, from the fetch until the branch (and any published branch) is updated or restored. An invocation that cannot take the lock MUST block with cause `busy` without touching the branch.

### Key Entities

- **Authoritative base**: the base reference (recorded at run start, or the pinned repository's default branch) and the commit it pointed at when last fetched.
- **Synchronization outcome**: one record per invocation in the run ledger: timestamp, run, base reference, previous and current base commit, previous and resulting HEAD, outcome, and cause and recovery action for a blocked outcome.
- **Feature identity**: the Issue number, feature directory, local branch, published branch and base, resolved once in trusted code and shared with the #17 PR checkpoint (roadmap item 1).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In deterministic tests, no agent step starts in any invocation whose branch, at the start of that invocation, does not contain the fetched base commit. This holds for 100% of the covered cases: up-to-date, behind-clean, dirty, conflict, fetch failure, unknown base, operation in progress, wrong branch, published, diverged, failed push, protected-input change, concurrent invocation, and repeated invocation.
- **SC-002**: In every blocked case the branch HEAD, index, working tree and published branch are byte-for-byte the same before and after the invocation, except: `protected-input`, which keeps the completed synchronization (AC-016, DEC-0002); a block after a successful push, which leaves the published branch at the rebased commit for the next invocation to complete (DEC-0005); and `busy` after another actor moved the branch during the check, where HEAD is that actor's commit and the index and working tree match it, with only the synchronization's own output dropped.
- **SC-003**: Every blocked outcome gives the operator, in one message, the cause and exactly one recovery action. An operator can recover from each cause in the scratch-repository pilot without reading Ballast source.
- **SC-004**: In the scratch-repository pilot, a run paused while the base advances resumes on the new base, or stops before any agent with `BLOCKED_UPSTREAM_SYNC`. This is the roadmap's exit evidence for this item.
- **SC-005**: When the base has not moved, the check adds no visible delay beyond one `ls-remote` (no fetch runs when the observed commits are already local) and leaves the run otherwise unchanged.

## Assumptions

- **A-1**: Synchronization rebases, as the roadmap item specifies, not a merge of the base into the branch. "Rebase" means the replay ADR-0005 describes: the feature's commits are replayed onto the fetched base in a throwaway repository with `git merge-tree`, and the branch then moves to the result with one compare-and-swap. `git rebase` never runs in the checkout, so nothing is ever left in progress to abort; replayed commits are unsigned, merge attributes come from the fetched base, and no `rebase.*` configuration applies. This keeps the branch linear for the #17 Draft PR and for merge by rebase or merge commit.
- **A-2**: The check runs once per invocation, at its start. A base that advances while an invocation is running is caught by the next invocation, not mid-run.
- **A-3**: Choosing or changing a run's base is out of scope (#17 assigned it here, but only the recorded-or-default rule in FR-002 is needed). A later Issue can add a base override.
- **A-4**: Fast-forwarding a clean local branch to its own published branch (AC-015) is safe and in scope, because it cannot lose local work. Any divergence blocks.
- **A-5**: Branch-level exclusion across the whole invocation (roadmap item 4) is out of scope; FR-016 serializes only the synchronization itself, as the Issue requires.
- **A-6**: GitHub is the only supported forge, as in #17. A run with no pinned GitHub repository blocks with `unknown-base` instead of skipping the check.
- **A-7**: This feature changes what the trusted launcher mutates (it rewrites and pushes branches) and what it fetches. The roadmap classifies it as **R2**, which needs explicit human approval before implementation in a human-gated run, and security review.
- **A-8**: The rebuildable, git-ignored files Ballast installs are not inputs to the "dirty" decision. Only tracked and untracked-but-not-ignored changes are.
- **A-9**: `ballast run resume` stays refused for Autonomous runs (#27 FR-023). This feature synchronizes every invocation that starts agent steps; lifting the refusal belongs to #21 ("Autonomous `resume` through branch synchronization").

## Clarifications

### Session 2026-10-05

- Q: When synchronization changes files the feature's plan or review evidence covers, what happens to that evidence? → A: Record the overlapping files, mark the affected evidence stale in the run ledger and the Draft PR, and continue (operator, option A).
- Q: Does this feature lift #27's refusal of `ballast run resume` for Autonomous runs? → A: No. Keep the refusal; #21 lifts it (operator, option B).
