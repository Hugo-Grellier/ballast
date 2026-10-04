# Feature Specification: One reusable Draft PR for issue-linked feature work

**Feature Branch**: `feat-github-draft-pr`

**Created**: 2026-10-04

**Status**: Draft

**Input**: User description: "Issue #17: Issue-linked implementation becomes visible in exactly one Draft PR after the first meaningful pushed commit."

**Tracking**: [Ballast #17](https://github.com/Hugo-Grellier/ballast/issues/17); roadmap Priority 3, item 2 "Early Draft PR" ([product roadmap](../../docs/plans/2026-10-02-product-roadmap.md#priority-3--make-long-running-feature-work-safe-and-visible), derived from [LoreForge #111](https://github.com/Hugo-Grellier/LoreForge/issues/111)); [technical spec §90 and §91](../../specs/TECHNICAL-SPEC.md#91-v10-target) ("safe branch synchronization and one reusable GitHub Draft PR").

**Risk**: R2. The trusted launcher gains GitHub write authority (creating and editing a pull request) and runs a new external tool outside the agent sandbox. Both are named R2 boundaries in [`docs/policies/project/workflow.md`](../../docs/policies/project/workflow.md). Intent and plan need explicit human approval.

**Source note**: Reconciled with Issue #17 (`issue.md`) before intent approval; FR-016 adds the template and scope summary the issue requires. The outcome comes from the run input; the scope comes from the roadmap item and the technical spec. Before approving intent, check the spec against the Issue's acceptance criteria.

## Context

Today a feature run under `ballast run` commits its work on a local feature branch. Nothing makes that work visible on GitHub. Agents are denied `git push` and `gh`. Draft PRs are opened by hand, sometimes late, sometimes twice, and sometimes without a link to the Issue. A reviewer cannot follow a long-running feature until someone remembers to open the PR. After a pause or a switch to another agent, nothing guarantees that the new work lands in the PR opened before.

This feature gives the trusted launcher one job: once an issue-linked feature branch has real work on GitHub, make sure exactly one Draft PR shows it. Reuse that PR on every later invocation, and report clearly when this cannot be done yet. Making the PR ready for review, merging it, synchronizing the branch with its base and branch-level locking are out of scope. The roadmap lists them as separate items.

## User Scenarios & Testing *(mandatory)*

Give each acceptance scenario a stable ID (`AC-001`, `AC-002`, ...). Task and test descriptions cite the IDs they satisfy, so review can trace each criterion to evidence.

### User Story 1 - Feature work appears in a Draft PR without a manual step (Priority: P1)

An operator runs a feature through `ballast run` for an issue-linked feature directory (`specs/<issue>-<slug>/`). As soon as the feature branch on GitHub holds its first meaningful change, a Draft PR exists for it. The PR targets the base branch and links the Issue. The operator and reviewers can follow progress there without having opened anything themselves.

**Why this priority**: This is the main outcome of the Issue. Without it, feature work stays invisible until the very end.

**Independent Test**: In a disposable GitHub repository with no PR, run a feature until its branch on GitHub holds a meaningful change, then let the run invocation end. Exactly one open Draft PR now exists for the branch. It links the Issue and the run ledger records it.

**Acceptance Scenarios**:

1. **AC-001**: **Given** an issue-linked run whose branch on GitHub holds a meaningful change and has no open PR, **When** a `ballast run` invocation for that run reaches a PR checkpoint, **Then** one Draft PR is created from the feature branch to the base branch, and its description links the Issue, the feature directory and the run.
2. **AC-002**: **Given** the PR was created, **When** the operator looks at the run's ledger or status output, **Then** it shows the PR number, the PR address and the state `created`.
3. **AC-003**: **Given** an issue-linked run whose branch is not on GitHub yet, or holds no meaningful change compared with the base, **When** a PR checkpoint is reached, **Then** no PR is created, the run continues, and the status shows `pending` with the reason: branch not published, or no meaningful change yet.
4. **AC-004**: **Given** the branch on GitHub differs from the base only by empty commits, or by commits whose combined changes cancel out, **When** a PR checkpoint is reached, **Then** the state remains `pending`.
5. **AC-005**: **Given** the branch on GitHub holds only feature specification artifacts and no implementation change, **When** a PR checkpoint is reached, **Then** the outcome follows the meaning of "meaningful change" defined in FR-003. A branch whose published difference touches only `specs/<feature>/` is not a meaningful change, so no Draft PR is created yet (provisional decision under the operator's standing authority, 2026-10-03, from Issue #17's "first eligible pushed implementation diff").

---

### User Story 2 - Every later invocation reuses the same PR (Priority: P1)

Over the life of a feature the operator pauses, resumes, switches agents or opens a PR by hand. Every later invocation finds the existing PR and records it. No invocation opens a second PR, and none undoes a human change to the PR's state.

**Why this priority**: "Exactly one" is half of the outcome. A duplicate PR splits review and evidence, which is worse than having no PR.

**Independent Test**: Run several invocations against a branch that already has a PR: one opened by Ballast, one opened by hand, one already marked ready for review. Each still has exactly one PR, unchanged except for the marked Ballast section.

**Acceptance Scenarios**:

1. **AC-006**: **Given** a Draft PR that Ballast created earlier for this branch, **When** the run is resumed (with the same or another agent) and reaches a PR checkpoint, **Then** no new PR is created, the existing PR is recorded as `reused`, and new commits on the branch appear in that PR.
2. **AC-007**: **Given** a PR that a human opened by hand from the feature branch, **When** a PR checkpoint is reached, **Then** Ballast adopts it as the feature's PR, records it as `reused`, and leaves its title, description and draft or ready state unchanged, except for one Ballast-marked section that adds the Issue link if it is missing.
3. **AC-008**: **Given** the feature's PR has been marked ready for review by a human, **When** a PR checkpoint is reached, **Then** Ballast does not turn it back into a draft.
4. **AC-009**: **Given** two invocations for the same feature reach a PR checkpoint at the same time, **When** both finish, **Then** at most one PR exists for the branch.

---

### User Story 3 - Failures are visible and safe to retry (Priority: P2)

When GitHub cannot be reached, credentials are missing or the situation is ambiguous, the operator sees exactly why there is no PR and what to do. The next invocation retries on its own. The feature work itself is never lost or blocked because the PR step failed.

**Why this priority**: PR visibility supports the work; it is not the work. A failure must be visible but must not stop progress or cause a wrong PR.

**Independent Test**: Simulate an unavailable GitHub CLI, missing authentication, a network failure, several open PRs for the branch and a merged PR for the branch. Check each reported state, the remedy and the retry behavior.

**Acceptance Scenarios**:

1. **AC-010**: **Given** the GitHub CLI is missing, unauthenticated, lacks permission, or GitHub cannot be reached, **When** a PR checkpoint is reached, **Then** the run's workflow outcome is unchanged, the status shows `failed-retryable` with the cause and one actionable remedy, and the next checkpoint tries again.
2. **AC-011**: **Given** more than one open PR has the feature branch as its head, **When** a PR checkpoint is reached, **Then** Ballast creates and edits nothing, and reports `blocked-ambiguous` with every matching PR address.
3. **AC-012**: **Given** the only PR for the feature branch is closed or merged, **When** a PR checkpoint is reached, **Then** Ballast neither reopens it nor creates a new one, and reports `blocked-closed` with the PR address and the decision the operator must make.
4. **AC-013**: **Given** the feature directory does not start with an Issue number, or the Issue does not exist in the repository, **When** a PR checkpoint is reached, **Then** no PR is created and the status reports `blocked-unlinked` with the reason.
5. **AC-014**: **Given** any outcome of a PR checkpoint, **When** the operator reads the output and the ledger, **Then** no credential, token or authentication header appears in them.

---

### Edge Cases

- The feature branch is pushed under a different name on GitHub (its upstream does not match the local branch), or has no upstream: Ballast treats the branch as unpublished (`pending`), and the reason says so with the command to publish it under its own name. The upstream's name lives in Git configuration an agent can write, so it is never followed (DEC-0010).
- A PR from a fork, or with another head repository, names a branch of the same name: it is not treated as the feature's PR.
- The base branch cannot be determined: `failed-retryable` with the reason. No PR is opened against a guessed base.
- An agent writes text meant to change the PR title or description (in the spec, a commit message or a branch name): the PR content comes only from fixed wording, the Issue number and title, the intake scope comment on the Issue, the pull-request template as committed on the **base** branch on GitHub (never the feature branch's copy), and paths that Ballast checks. Untrusted text is never run as code or passed to a shell.
- The operator deletes the Ballast-marked section of a reused PR: Ballast restores at most the Issue link, and touches nothing else.
- A run is aborted or discarded: the PR is left as it is. Closing it is the operator's decision.
- The PR checkpoint is reached when the agent sandbox is unavailable: the checkpoint runs in trusted launcher code and does not depend on the sandbox.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The PR checkpoint MUST run only in trusted launcher code, after launcher trust verification and outside the agent sandbox. No agent gains GitHub write authority or credentials through this feature.
- **FR-002**: The launcher MUST reach a PR checkpoint at least when a `ballast run` start or resume invocation ends, whether the workflow completed, paused at a gate or failed.
- **FR-003**: A branch MUST count as holding a meaningful change only when the branch as published on GitHub has a non-empty content difference from its base. Only differences outside the feature's own spec directory `specs/<feature>/` count (see AC-005). When GitHub cannot list the whole difference (its compare lists at most 300 files), Ballast does not conclude: the status is `pending` with a reason saying the difference could not be classified and a remedy to open the PR by hand, which Ballast then adopts (DEC-0008).
- **FR-004**: Ballast MUST NOT push commits in this feature; it observes the published branch. Publishing the branch stays an operator action, or the Autonomous publisher's (#27); this feature only observes what is on GitHub, per Issue #17's "defer until a remote diff exists" (provisional decision, 2026-10-03 standing authority).
- **FR-005**: Before creating a PR, Ballast MUST look for open PRs from the same repository whose head is the feature branch. If it finds one, it reuses it. If it finds several, it reports `blocked-ambiguous`. If the only matching PR is closed or merged, it reports `blocked-closed`.
- **FR-006**: A created PR MUST be a draft, target the base branch and include a Ballast-marked section that links the Issue, the feature directory and the run. The link MUST NOT close the Issue when the PR merges.
- **FR-007**: On a reused PR, Ballast MUST change nothing except its own marked section. It MUST NOT change the draft or ready state, the title, labels, reviewers or human-written text.
- **FR-008**: Ballast MUST NOT mark a PR ready for review, merge it, close it or reopen it.
- **FR-009**: Concurrent checkpoints for the same feature MUST result in at most one PR. Before creating a PR, Ballast checks again for an existing one under exclusion.
- **FR-010**: Each checkpoint MUST record its outcome in the run ledger: one of `pending`, `created`, `reused`, `failed-retryable`, `blocked-ambiguous`, `blocked-closed`, `blocked-unlinked`. For created and reused outcomes it also records the PR number and address; for the others, the reason. `ballast run` output MUST show the latest outcome.
- **FR-011**: A PR checkpoint failure MUST NOT change the workflow's exit status or step state. It also MUST NOT discard, rewrite or block local feature work.
- **FR-012**: The checkpoint MUST derive the Issue number from the feature directory (`specs/<number>-<slug>/`) and confirm that the Issue exists before creating a PR.
- **FR-013**: The checkpoint MUST NOT write credentials or authentication material to output, logs, the ledger or the PR.
- **FR-014**: The checkpoint MUST be covered by deterministic tests that need no network: no PR, existing Ballast PR, hand-opened PR, ready PR, several PRs, closed or merged PR, unpublished branch, empty diff, missing or unauthenticated CLI, network failure, unlinked feature directory and concurrent checkpoints.
- **FR-015**: User-facing documentation MUST describe when a Draft PR appears, the recorded states and their remedies, and the authority the launcher uses.
- **FR-016**: A created PR's description MUST contain the project's pull-request template read from the base branch on GitHub (when one exists), followed by a Ballast section with the Issue reference, a scope summary taken from the Issue's intake scope comment (`Main outcome`, `Risk` and `Scope gate` lines, when present), and the run status (feature directory, run ID, last checkpoint time). Ballast always creates the PR as a draft and never changes its readiness (FR-008); readiness and merge follow the workflow mode and the human merge rule (Issue #17 acceptance; provisional decision under the operator's standing authority, 2026-10-03).

### Key Entities

- **Feature identity**: Issue number, feature directory, local branch, published branch, base branch. It is resolved once per checkpoint in trusted code.
- **Feature PR**: the single open PR whose head is the feature's published branch in the same repository. It has a number, an address, a draft or ready state and a Ballast-marked section.
- **PR checkpoint outcome**: one recorded state per checkpoint, with a timestamp, the run, the PR reference or a reason, and a remedy for blocked or failed states.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In the pilot features, every issue-linked feature with published work has exactly one PR. The duplicate PR count is zero.
- **SC-002**: A Draft PR exists no later than the end of the first `ballast run` invocation after the branch's first meaningful published change. No human action is needed beyond that publication.
- **SC-003**: All 12 checkpoint situations listed in FR-014 are covered by passing deterministic tests.
- **SC-004**: Every failed or blocked checkpoint tells the operator in one message what is wrong and the one action to take. No PR failure ends or alters a run's workflow result.
- **SC-005**: No agent permission or sandbox rule grants `git push`, `gh` or GitHub credentials after this feature, as checked by the existing agent settings tests.

## Assumptions

- The qualified environment is the 1.0 environment: GitHub, Linux, a systemd user session and an authenticated GitHub CLI on the operator's machine. `ballast doctor` already reports GitHub access.
- The base branch is the repository's default branch unless the run records another base. Choosing or changing the base belongs to the synchronization feature.
- Branch synchronization, branch-level locking across the whole invocation, ready-for-review policy per autonomy mode, review packets and demo links are separate roadmap items. This feature only leaves room for them, through the marked section and the ledger states.
- The PR title is the Issue title as written, truncated to 256 characters. Humans may edit it afterwards.
- Only `ballast run` invocations reach PR checkpoints. Agent chat sessions outside `ballast run` are out of scope.
- An adopted project that does not use GitHub Issues gets `blocked-unlinked` and no PR. Supporting other forges is out of scope.
