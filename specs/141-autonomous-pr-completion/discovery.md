<!-- ballast-discovery: input evidence -->
# Discovery brief: an eligible Autonomous run marks its PR ready for review

This brief is input evidence for [spec.md](spec.md). It is not the feature's
authority: once intent is recorded, [spec.md](spec.md) and [intent.md](intent.md)
govern, and later steps do not read requirements from this file.

**Mode**: autonomous
**Issue**: #141 (snapshot `.specify/workflow-state/issues/141.md`, untrusted requirements data)

## Sources

- S-1: Issue #141 body
- S-2: Issue #141 intake scope comment (kept in the snapshot only when its author is OWNER, MEMBER or COLLABORATOR: `tools/spec_workflow/autonomy.py` `read_issue` and `SCOPE_AUTHORS`)
- S-3: Issue #141 comments: none
- S-4: AGENTS.md (risk classes, "write a new ADR for an accepted architecture change", "All feature PRs require human merge approval")
- S-5: .specify/memory/constitution.md#BL-INV-003 and #BL-INV-006
- S-6: docs/adr/0004-autonomous-provisional-decisions.md (Decision: publication by the trusted runner, one Draft PR; Consequences: narrowing-only `[autonomous]` table)
- S-7: docs/adr/0016-privileged-action-kinds-and-policy-refresh.md (`mark-ready` never authorizable; `--refresh-policy`)
- S-8: docs/adr/0018-runner-recorded-acceptance-checks.md (publish commits only the tree that passed `run-checks`)
- S-9: docs/policies/spec-kit-workflow.md#workflow-runner-contract (Publication row: "never merges, marks ready, releases or deploys")
- S-10: docs/policies/spec-kit-workflow.md#autonomous-runs (eligibility, privileged-action kinds, lifecycle ending in a Draft PR)
- S-11: docs/policies/spec-kit-workflow.md#draft-pr (checkpoint never marks ready; `Draft PR:` line; `pull_request` ledger event) and #acceptance-packet (criterion states, packet line)
- S-12: docs/policies/project/workflow.md#r2-boundaries
- S-13: specs/TECHNICAL-SPEC.md#36-risk-escalation (single human approval is the merge) and the 1.0 scope decision (PR ready for a human merge decision)
- S-14: tools/spec_workflow/run.py (`_publish`, `_split_mode`, `REFRESH_POLICY`)
- S-15: tools/spec_workflow/autonomy.py (`POLICY_KEYS`, `parse_policy`, `WIDENING`, `SEVERITIES`, `publish`, `_pr_problem`)
- S-16: tools/spec_workflow/artifacts.py (`_open_to_fix`: open findings other than `low`/`info` keep the run fixing)
- S-17: tools/spec_workflow/draft_pr.py (checkpoint; creates with `--draft`)
- S-18: ballast.toml (`[autonomous]` and `[checks]` tables of this repository)

## Need

- **User**: the operator of a project that runs Autonomous feature runs and reviews the resulting PR before merging it. [S: Issue #141 body]
- **Job to be done**: get a converged, low-risk Autonomous run to a PR that is ready for review without a manual `gh pr ready`. [S: Issue #141 body]
- **Current pain**: every Autonomous run ends with a Draft PR, so even a converged R1 run with every check passing needs the operator to mark it ready by hand, a step that adds no information. [S: Issue #141 body]
- **Intended outcome**: an eligible Autonomous run marks its published PR ready for review when the operator's policy allows it, and otherwise leaves a Draft and records why. [S: Issue #141 intake scope comment]

## Examples

- LoreForge pilot: Hugo-Grellier/LoreForge#128 produced PR #138 with spec reconciliation CONVERGED, every review approved, every check passing and risk R1, yet the PR still needed `gh pr ready` and a manual merge. [S: Issue #141 body]
- A project sets `[autonomous] completion = "ready"`; an R1 run converges, its checks pass and its packet has only `verified` criteria, so `run.py` marks the PR ready and the run output says so. [S: IAC-2]
- The same project runs an R2 change; the PR stays a Draft and the reason (risk R2) is printed and recorded in the ledger. [S: IAC-4]
- A project with no `completion` key gets a Draft PR exactly as today. [S: IAC-1]

## Scope

- `[autonomous] completion = "draft" | "ready"` in `ballast.toml`, default `draft`. [S: Issue #141 intake scope comment]
- A `ballast run start --mode autonomous` flag that may only narrow the configured policy. [S: Issue #141 intake scope comment]
- Deterministic eligibility checked by `run.py` after publication: risk R0/R1, no privileged actions, final acceptance recorded, spec reconciliation CONVERGED, no open finding above the configured severity, every configured check passing on the published head, an acceptance packet with only `verified` criteria, no material provisional change and no block resolved during the run. [S: Issue #141 intake scope comment]
- `gh pr ready` run by `run.py` as the operator, never by an agent. [S: Issue #141 intake scope comment]
- The fallback reason on the Draft PR line and in the ledger. [S: Issue #141 intake scope comment]
- Updates to the Publication contract, the technical spec and the docs. [S: Issue #141 intake scope comment]
- A new ADR amending ADR-0004's publication decision, since the runner gains a forge action. [S: AGENTS.md]

## Non-goals

- Merging the PR or enabling GitHub auto-merge (moved to #143, ADR first). [S: Issue #141 intake scope comment]
- A per-Issue `Completion:` line in the intake scope record. [S: Issue #141 intake scope comment]
- Marking a PR ready from any agent step. [S: Issue #141 intake scope comment]
- Any change to human-gated or Chat runs, or to the Draft PR checkpoint's "never marks ready" rule. [S: docs/policies/spec-kit-workflow.md#draft-pr]
- Waiting for GitHub CI on the published head before deciding. [P: D-07]

## Constraints

- A provisional decision is never human approval; merging stays the single human approval, and marking ready is not an approval. [S: .specify/memory/constitution.md#BL-INV-006]
- `mark-ready` stays a never-authorizable privileged action for agents; only the trusted runner may run it. [S: docs/adr/0016-privileged-action-kinds-and-policy-refresh.md]
- `ballast.toml` is a protected input agents cannot change; an agent never gains authority beyond its caller. [S: .specify/memory/constitution.md#BL-INV-003]
- `[autonomous]` is documented as narrowing-only and unknown keys are ignored with a "cannot widen eligibility" warning, so `completion` must be added as a recognised key with a documented exception. [S: tools/spec_workflow/autonomy.py] [S: docs/adr/0004-autonomous-provisional-decisions.md]
- The Publication contract today says the publisher never marks ready; that sentence changes for an eligible run only. [S: docs/policies/spec-kit-workflow.md#workflow-runner-contract]
- The change touches the launcher's trust model and what the runner executes, so it is R2. [S: docs/policies/project/workflow.md#r2-boundaries]
- Workflow tools stay standard-library-only; `gh` is resolved and run as the Draft PR checkpoint does. [S: AGENTS.md] [S: docs/policies/spec-kit-workflow.md#draft-pr]
- An accepted architecture change is recorded as a new ADR. [S: AGENTS.md]

## Permissions and data authority

- The completion policy comes only from the trusted `ballast.toml` snapshot taken at start (or a `--refresh-policy` resume reading a `ballast trust` baseline), never from agent output. [S: docs/adr/0016-privileged-action-kinds-and-policy-refresh.md] [S: Issue #141 intake scope comment]
- The eligibility inputs come from operator records (decision log, ledger, run record, publication result, packet build), which agent steps cannot write. [S: docs/adr/0004-autonomous-provisional-decisions.md] [S: docs/adr/0018-runner-recorded-acceptance-checks.md]
- `gh pr ready` runs with the operator's GitHub CLI against the pinned `[github] repository`; tokens stay withheld from agents. [S: docs/policies/spec-kit-workflow.md#draft-pr]
- The start flag can only narrow the configured policy, never widen it. [S: Issue #141 intake scope comment]

## Success evidence

- Unit tests for each eligibility condition, each producing a Draft with its named reason when it fails. [S: IAC-4]
- A test that no configuration yields today's Draft PR output and ledger. [S: IAC-1]
- A test that an eligible run with `ready` calls `gh pr ready` once for the published PR and prints that it did. [S: IAC-2]
- Tests that agent-writable inputs (drafts, artifacts, the checkout's `ballast.toml` copy) cannot change the policy or the result, and that a widening start flag is refused. [S: IAC-5]
- The fast gate passes, and the full gate is recorded or listed as unavailable. [S: AGENTS.md]

## Edge, failure and permission cases

- No `[autonomous]` table, or no `completion` key: Draft as today. [S: IAC-1]
- `completion` with an unknown value: refused or ignored with a warning, never treated as `ready`. [I]
- Start flag wider than `ballast.toml` (flag `ready`, config `draft`): the start is refused before any agent step. [P: D-05]
- Risk R2, any declared privileged action, a material provisional change, or a block resolved during the run: Draft with the reason. [S: Issue #141 intake scope comment]
- Acceptance packet not published, or a criterion `missing`, `failed` or `not run`: Draft with the reason. [S: Issue #141 intake scope comment]
- PR head differs from the commit publication pushed (a human pushed meanwhile): Draft with the reason. [P: D-07]
- `gh pr ready` fails (network, permission): Draft with a reason; the run's exit status and step state do not change. [P: D-09]
- After the PR is ready, later checkpoints and a `ballast run publish` retry must accept a non-draft PR this run marked ready; `autonomy._pr_problem` currently rejects a PR that "is not a draft". [S: tools/spec_workflow/autonomy.py]
- A run lowered by `ballast run continue` to human-gated or Chat never marks ready. [I]
- An Autonomous run resumed with `--refresh-policy` uses the refreshed `completion`, still narrowed by the start flag. [P: D-05]

## Issue acceptance criteria

- IAC-1: With no configuration, an Autonomous run ends with a Draft PR exactly as today.
- IAC-2: With `ready` configured and every eligibility condition met, the PR is marked ready for review after publication, and the run output says so.
- IAC-3: With `merge` configured and every eligibility condition met, the PR is merged (or set to auto-merge) through GitHub, and branch protection is never bypassed.
- IAC-4: When any condition fails, the PR stays a Draft and the reason is printed and recorded in the ledger.
- IAC-5: An agent cannot change the policy or the eligibility result.

## Known

- IAC-3 is moved to #143; this feature covers IAC-1, IAC-2, IAC-4 and IAC-5. [S: Issue #141 intake scope comment]
- The policy lives in `ballast.toml` as `[autonomous] completion`, values `draft` and `ready`, default `draft`. [S: Issue #141 intake scope comment]
- The run is R2, Autonomous, with no privileged actions before merge. [S: Issue #141 intake scope comment]
- The Publication row and the Draft PR checkpoint both state that Ballast never marks a PR ready. [S: docs/policies/spec-kit-workflow.md#workflow-runner-contract] [S: docs/policies/spec-kit-workflow.md#draft-pr]
- `run.py` `_publish` prints `Draft PR: <url>` after `autonomy.publish`; this is the line that gains the outcome. [S: tools/spec_workflow/run.py]
- Finding severities are `critical`, `high`, `medium`, `low`, `info`; open findings other than `low`/`info` already keep the run in its fix loop. [S: tools/spec_workflow/autonomy.py] [S: tools/spec_workflow/artifacts.py]
- Publish commits only the tree that passed `run-checks`. [S: docs/adr/0018-runner-recorded-acceptance-checks.md]
- The ledger already has a `pull_request` event. [S: docs/policies/spec-kit-workflow.md#draft-pr]

## Inferred

- Marking ready changes no approval: the merge stays the only human approval, so BL-INV-006 holds. [I]
- The eligibility function should be pure over operator records so it is testable without GitHub. [I]
- The ledger outcome can extend the `pull_request` event or add a new event; the plan chooses, noting that a new event kind is rejected by older pinned versions (as ADR-0018 records). [I]
- The start flag is `--completion draft|ready`; a wider value than the configuration refuses the start; the effective policy is recorded in the run's policy snapshot. [P: D-05]
- `[autonomous] completion_max_severity` accepts `low` (default: open `low`/`info` findings allowed), `info` or `none`. [P: D-06]
- "Every configured check passing on the published head" means the `[checks]` commands passed in `run-checks` on the tree publication committed, and the PR head is that commit when read back. [P: D-07]
- Eligibility is evaluated once, at the end of the Autonomous publication (start, resume, or `ballast run publish` retry), never by `ballast run checkpoint`. [P: D-08]
- A failed `gh pr ready` leaves a Draft with its reason and does not change the run's exit status. [P: D-09]

## Undecided

None.

## Decisions

### D-01: Where the policy lives and which values it takes
- **Status**: settled
- **Question**: Is the policy in `ballast.toml`, the scope record, or both, and which values exist?
- **Why it matters**: decides the config parser, the trust boundary and whether intake changes.
- **Sources**: [S: Issue #141 body] [S: Issue #141 intake scope comment]
- **Options**:
  - A — `[autonomous] completion = "draft"|"ready"` in `ballast.toml` with a narrowing start flag. Consequence: operator-owned, protected input.
  - B — also a per-Issue `Completion:` scope line. Consequence: intake changes too.
- **Recommended default**: A, because the operator chose it at intake.
- **Answer**:
- **Resolution**: A; the intake scope comment limits it to `draft|ready`, puts it in `ballast.toml` with a narrowing start flag and rules out a per-Issue line [S: Issue #141 intake scope comment].

### D-02: Whether merge or auto-merge is in scope
- **Status**: settled
- **Question**: Does this feature implement `merge` (IAC-3)?
- **Why it matters**: merge would change the single-human-approval principle and need an ADR first.
- **Sources**: [S: Issue #141 body] [S: Issue #141 intake scope comment] [S: docs/adr/0004-autonomous-provisional-decisions.md]
- **Options**:
  - A — no; `merge` moves to #143. Consequence: IAC-3 is out of this feature.
  - B — yes. Consequence: conflicts with ADR-0004 until a new ADR is accepted.
- **Recommended default**: A, because the intake split it.
- **Answer**:
- **Resolution**: A; merge and auto-merge are out of scope and moved to #143 [S: Issue #141 intake scope comment].

### D-03: Whether the change needs a new ADR
- **Status**: settled
- **Question**: Does letting the runner mark a PR ready need a new ADR?
- **Why it matters**: ADR-0004 decides the runner opens one Draft PR and the `[autonomous]` table only narrows; the Publication contract says the runner never marks ready.
- **Sources**: [S: AGENTS.md] [S: docs/adr/0004-autonomous-provisional-decisions.md] [S: docs/policies/spec-kit-workflow.md#workflow-runner-contract]
- **Options**:
  - A — a new ADR amending ADR-0004's publication decision, proposed with this feature and accepted by the merge. Consequence: the trust-model change is recorded where design is governed.
  - B — only update the policy docs. Consequence: the docs and the accepted ADR disagree.
- **Recommended default**: A, because the repository requires an ADR for an accepted architecture change.
- **Answer**:
- **Resolution**: A; AGENTS.md says to "write a new ADR for an accepted architecture change" and the intake scope comment puts the Publication contract update in scope [S: AGENTS.md] [S: Issue #141 intake scope comment].

### D-04: Who runs `gh pr ready`
- **Status**: settled
- **Question**: Does an agent step or the trusted runner mark the PR ready?
- **Why it matters**: decides whether `mark-ready` ever enters agent authority.
- **Sources**: [S: Issue #141 intake scope comment] [S: docs/adr/0016-privileged-action-kinds-and-policy-refresh.md]
- **Options**:
  - A — `run.py` as the operator, after publication. Consequence: agents keep no forge authority.
  - B — an agent step. Consequence: contradicts ADR-0016.
- **Recommended default**: A, because ADR-0016 never authorizes `mark-ready` for agents.
- **Answer**:
- **Resolution**: A; the intake scope comment names `gh pr ready` by `run.py` and puts marking ready from any agent step out of scope [S: Issue #141 intake scope comment].

### D-05: Start flag name and how it narrows
- **Status**: assumed
- **Question**: What is the start flag, and what happens when it would widen the configured policy?
- **Why it matters**: decides the CLI surface, refusal behavior and resume behavior.
- **Sources**: [S: Issue #141 intake scope comment] [S: tools/spec_workflow/run.py] [S: docs/adr/0016-privileged-action-kinds-and-policy-refresh.md]
- **Options**:
  - A — `--completion draft|ready`; a value wider than `ballast.toml` refuses the start before any agent step; the effective value is in the run's policy snapshot; resume never takes the flag, and `--refresh-policy` re-reads `completion`, still narrowed by the start flag. Consequence: fail-closed, matches existing limit flags.
  - B — a widening flag is ignored with a warning. Consequence: the operator may believe a run will be marked ready when it will not.
- **Recommended default**: A, because refusing is fail-closed and the flag can only lower authority.
- **Answer**:
- **Resolution**: A assumed. The flag only removes authority and a refusal happens before any agent runs, so it is safe; the name and refusal are reversible before merge.

### D-06: The configured finding-severity threshold
- **Status**: assumed
- **Question**: Where is "the configured severity" set, and what is its default?
- **Why it matters**: decides which open findings keep a PR a Draft.
- **Sources**: [S: Issue #141 intake scope comment] [S: tools/spec_workflow/autonomy.py] [S: tools/spec_workflow/artifacts.py]
- **Options**:
  - A — `[autonomous] completion_max_severity`, values `low` (default: open `low`/`info` allowed), `info` or `none`; nothing wider is accepted. Consequence: the default matches what the fix loop already lets through, and operators can only be stricter.
  - B — a fixed threshold with no key. Consequence: contradicts "configured severity".
- **Recommended default**: A, because it keeps the existing fix-loop boundary and can only narrow.
- **Answer**:
- **Resolution**: A assumed. It never lets more through than the run's own fix loop, it only affects whether a PR leaves Draft, and the key and default are reversible before merge.

### D-07: Which checks must pass on the published head
- **Status**: assumed
- **Question**: Does "every configured check passing on the published head" mean the `[checks]` commands or GitHub check runs?
- **Why it matters**: GitHub CI would have to be awaited after the push; `[checks]` results are already recorded.
- **Sources**: [S: Issue #141 intake scope comment] [S: docs/adr/0018-runner-recorded-acceptance-checks.md] [S: ballast.toml]
- **Options**:
  - A — the `[checks]` commands passed in `run-checks` on the tree publication committed, and the PR head read back before `gh pr ready` is that commit. Consequence: deterministic and immediate; CI still runs and branch protection still gates merge.
  - B — wait for GitHub check runs on the head. Consequence: polling, timeouts and a new failure class.
- **Recommended default**: A, because ADR-0018 binds the published tree to the passing checks, and ready is not merge.
- **Answer**:
- **Resolution**: A assumed. Marking ready approves nothing, CI and branch protection still decide the merge, and waiting for CI can be added later.

### D-08: When eligibility is evaluated
- **Status**: assumed
- **Question**: At which commands does `run.py` evaluate and act?
- **Why it matters**: decides whether `ballast run checkpoint` gains a forge write.
- **Sources**: [S: docs/policies/spec-kit-workflow.md#draft-pr] [S: tools/spec_workflow/run.py]
- **Options**:
  - A — once, at the end of an Autonomous publication (start, resume or `ballast run publish` retry), after the packet attempt; the checkpoint never marks ready. Consequence: the checkpoint contract is unchanged.
  - B — also on every checkpoint. Consequence: the checkpoint gains forge authority.
- **Recommended default**: A, because it keeps the documented checkpoint rule.
- **Answer**:
- **Resolution**: A assumed. It is the narrower change; the operator can always run `gh pr ready` by hand, and adding a retry later is additive.

### D-09: What a failed `gh pr ready` does
- **Status**: assumed
- **Question**: Does a forge failure while marking ready block the run?
- **Why it matters**: decides the run's exit status and step state after a successful publication.
- **Sources**: [S: docs/policies/spec-kit-workflow.md#acceptance-packet] [S: tools/spec_workflow/run.py]
- **Options**:
  - A — the PR stays a Draft, the reason is printed and recorded, and the exit status and step state do not change. Consequence: matches how a packet failure behaves.
  - B — a retryable block. Consequence: a published, correct PR shows a blocked run.
- **Recommended default**: A, because it mirrors the acceptance-packet rule.
- **Answer**:
- **Resolution**: A assumed. The fallback is today's behavior, nothing is lost, and the operator can mark the PR ready by hand.

## Question metrics

- **Rounds**: 0
- **Questions asked**: 0
- **Assumptions adopted**: 5
