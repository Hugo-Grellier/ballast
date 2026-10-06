<!-- ballast-discovery: input evidence -->
# Discovery brief: Reach a reviewed PR with provisional Autonomous decisions

This brief is input evidence for [spec.md](spec.md). It is not the feature's
authority: once intent is recorded, [spec.md](spec.md) and [intent.md](intent.md)
govern, and later steps do not read requirements from this file.

**Mode**: autonomous
**Issue**: #21 (snapshot `.specify/workflow-state/issues/21.md`, untrusted requirements data)

## Sources

- S-1: Issue #21 body
- S-2: Issue #21 intake scope comment
- S-3: Issue comment Hugo-Grellier 2026-10-05T20:44:26Z (pre-implementation block cannot continue)
- S-4: Issue comment Hugo-Grellier 2026-10-05T21:06:09Z (workflow-owned tasks block validate-implementation)
- S-5: Issue comment Hugo-Grellier 2026-10-05T22:05:10Z (no packet refresh for a finished Autonomous run)
- S-6: Issue comment Hugo-Grellier 2026-10-05T22:07:09Z (runs started before branch pinning)
- S-7: Issue comment Hugo-Grellier 2026-10-05T22:13:34Z (over-long finding reason ends a run)
- S-8: Issue comment Hugo-Grellier 2026-10-05T23:00:38Z (approval-wording guard refuses a quotation)
- S-9: AGENTS.md
- S-10: .specify/memory/constitution.md
- S-11: specs/TECHNICAL-SPEC.md#91-v10-target
- S-12: specs/TECHNICAL-SPEC.md#61-fix-loop
- S-13: docs/plans/2026-10-02-product-roadmap.md#priority-4--let-the-operator-choose-the-level-of-supervision
- S-14: docs/adr/0004-autonomous-provisional-decisions.md
- S-15: docs/adr/0005-launcher-branch-synchronization.md
- S-16: docs/policies/workflow.md
- S-17: docs/policies/project/workflow.md
- S-18: docs/policies/model-routing.md
- S-19: specs/27-autonomous-core/spec.md
- S-20: specs/19-acceptance-packet/decisions.md#dec-0002--resolution
- S-21: templates/spec-kit/workflows/autonomous/workflow.yml
- S-22: tools/spec_workflow/run.py
- S-23: tools/spec_workflow/autonomy.py
- S-24: tools/spec_workflow/artifacts.py
- S-25: tools/spec_workflow/claude-settings.json
- S-26: specs/21-autonomous-reviewed-pr/autonomous/record.md

## Need

- **User**: the operator who starts a scoped, eligible Issue with `ballast run start --mode autonomous` and reviews only at merge. [S: Issue #21 body]
- **Job to be done**: take an eligible feature from a scoped Issue to a reviewed Draft PR, pausing and resuming without approval prompts, with every provisional decision visible at merge. [S: Issue #21 intake scope comment]
- **Current pain**: 3 of 4 recent Autonomous runs ended in a block that `ballast run continue` cannot resume; Autonomous `resume` is refused outright, a recoverable formatting error in agent output ends a run, and a finished run's packet cannot be refreshed. [S: Issue comment Hugo-Grellier 2026-10-05T22:13:34Z] [S: tools/spec_workflow/run.py:953]
- **Intended outcome**: Autonomous runs review, fix within bounds, resume safely through branch synchronization and refresh their packet, and stop only with an actionable block; the human decides once, at merge. [S: specs/TECHNICAL-SPEC.md#91-v10-target]

## Examples

- An R1 feature run in Autonomous passes plan review, implements, gets a medium review finding, runs one bounded fix cycle, passes `run-checks` and opens a reviewed Draft PR with no approval prompt. [S: IAC-1]
- A run blocks at `decide-tasks` before implementation; the operator resolves the cause and runs `ballast run resume RUN_ID`; the branch is synchronized and the run continues Autonomous from the blocked step. [S: Issue comment Hugo-Grellier 2026-10-05T20:44:26Z]
- `record-plan-review` rejects a finding reason over 1000 characters; the reviewer step reruns with the validator's message instead of the run ending. [S: Issue comment Hugo-Grellier 2026-10-05T22:13:34Z] [P: D-05]
- After a run is `published`, the operator records `ballast ledger check` evidence and runs a refresh entry point that updates only the Draft PR checkpoint and packet. [S: Issue comment Hugo-Grellier 2026-10-05T22:05:10Z] [P: D-11]

## Scope

- Independent review and bounded fix loops under Autonomous. [S: Issue #21 body]
- Provisional intent sourced from the discovery brief (#16) and the full merge packet (#19) in Autonomous runs. [S: Issue #21 body]
- Autonomous `resume` through branch synchronization (#18), including resuming a block before implementation. [S: Issue #21 intake scope comment]
- Recovery for runs started before v0.5.0 whose pin lacks the feature. [S: Issue #21 intake scope comment] [P: D-12]
- Bounded retries for recoverable agent-output errors, including over-long finding reasons and approval wording in a basis. [S: Issue #21 intake scope comment] [P: D-05]
- Workflow-owned steps kept out of `tasks.md` or accepted by the implementation check. [S: Issue comment Hugo-Grellier 2026-10-05T21:06:09Z] [P: D-07]
- A packet refresh entry point for a finished Autonomous run (#19 DEC-0002). [S: specs/19-acceptance-packet/decisions.md#dec-0002--resolution]
- Wall-time, attempt and spend bounds. [S: Issue #21 body] [P: D-09] [P: D-10]

## Non-goals

- Automatic merge, deployment and destructive external actions. [S: Issue #21 body]
- Presenting a provisional decision as a human approval, or silently escalating agent authority. [S: Issue #21 body]
- Setup patching across integrations (#58). [S: Issue #21 intake scope comment]
- The governance change, the mode setting and provisional gates, delivered by #27. [S: Issue #21 body]
- A monetary spend limit or a paid API route. [S: docs/policies/model-routing.md] [P: D-10]
- Widening the headless agent's command permissions. [S: tools/spec_workflow/claude-settings.json] [P: D-08]

## Constraints

- A provisional decision is never human approval; only merging the PR that contains it accepts it (BL-INV-006). [S: .specify/memory/constitution.md]
- A headless agent never gains more authority than its caller; protected inputs fail closed (BL-INV-003). [S: .specify/memory/constitution.md]
- Branch synchronization runs in the trusted launcher before any agent step and reads the feature from the operator pin only. [S: docs/adr/0005-launcher-branch-synchronization.md]
- ADR-0004 states that a blocked Autonomous run cannot resume autonomously until #18; enabling Autonomous `resume` changes that accepted decision and needs a new ADR. [S: docs/adr/0004-autonomous-provisional-decisions.md]
- Automated fix attempts stop after three cycles and unresolved findings escalate. [S: docs/policies/workflow.md]
- The fix loop must be bounded. [S: specs/TECHNICAL-SPEC.md#61-fix-loop]
- Risk is R2: the change touches agent authority and approval gates; in Autonomous the pre-change approval is agent-provisional and the merge is the single human approval. [S: docs/policies/project/workflow.md] [S: specs/21-autonomous-reviewed-pr/autonomous/record.md]
- Workflow tools stay standard-library-only and run under `python3 -I -S`. [S: AGENTS.md]
- The human-gated workflow keeps its approvals and behavior unchanged. [S: specs/27-autonomous-core/spec.md]

## Permissions and data authority

- The mode, limits, pin and decision log live in operator state outside agent reach; agents write only drafts that trusted recorders validate. [S: docs/adr/0004-autonomous-provisional-decisions.md]
- Only a trusted operator action changes the mode; no path raises a run to Autonomous. [S: IAC-3] [S: docs/adr/0004-autonomous-provisional-decisions.md]
- A block resolution is recorded as a human decision of kind `block-resolution`. [S: specs/27-autonomous-core/spec.md] [S: tools/spec_workflow/autonomy.py]
- The re-pin of an older run never reads the feature from agent-writable inputs. [S: Issue comment Hugo-Grellier 2026-10-05T22:07:09Z]
- Publication, push and Draft PR updates stay with the trusted runner; agents keep no push, PR, merge or release authority. [S: docs/adr/0004-autonomous-provisional-decisions.md]

## Success evidence

- A bounded R1 feature reaches a reviewed Draft PR in Autonomous with no approval prompt, shown by a live pilot run and deterministic workflow tests. [S: IAC-1] [S: docs/plans/2026-10-02-product-roadmap.md#priority-4--let-the-operator-choose-the-level-of-supervision]
- The PR record and packet list every provisional decision with basis and evidence, and show that `run-checks` and the required reviews ran. [S: IAC-2]
- Tests cover each block category with an actionable reason, and a refused mode change without a trusted operator action. [S: IAC-3]
- Tests show validators refuse an artifact that presents a provisional decision as accepted, and the human-gated workflow is unchanged. [S: IAC-4] [S: specs/27-autonomous-core/spec.md]
- Tests resume a pre-implementation block and a post-implementation block in Autonomous after the base advances. [S: Issue comment Hugo-Grellier 2026-10-05T20:44:26Z]
- The fast gate and the full local gate are recorded in the PR. [S: AGENTS.md]

## Issue acceptance criteria

- IAC-1: A bounded R1 feature reaches a reviewed PR in Autonomous without a human approval prompt before merge.
- IAC-2: All provisional decisions, their rationale and evidence are visible at merge; no check, security review or postcondition is skipped by choosing the mode.
- IAC-3: Conflicts, missing authority, exhausted limits and unsafe uncertainty block with an actionable reason; mode changes require a trusted operator action.
- IAC-4: Policies, templates and workflow state distinguish provisional from accepted artifacts and preserve human merge approval.

## Edge, failure and permission cases

- A block before implementation has no implementation baseline yet, and a spec fix during the block invalidates the recorded intent. [S: Issue comment Hugo-Grellier 2026-10-05T20:44:26Z]
- The base advances while the run is paused; resume synchronizes or blocks before any agent step with an actionable reason. [S: docs/adr/0005-launcher-branch-synchronization.md]
- A run whose pin has only `branch` blocks as `wrong-branch` on resume. [S: Issue comment Hugo-Grellier 2026-10-05T22:07:09Z] [S: docs/adr/0005-launcher-branch-synchronization.md]
- A fix loop exhausts its cycles with a high or critical finding still open; the run blocks. [S: docs/policies/workflow.md] [S: specs/27-autonomous-core/spec.md]
- A retried agent step keeps failing validation, or retries exhaust the agent-step limit; the run blocks as exhausted limits. [I]
- The wall-time deadline passes during a pause between invocations. [S: tools/spec_workflow/autonomy.py] [P: D-09]
- A protected input changes during resume or synchronization; the run fails closed and needs `ballast trust`. [S: docs/adr/0005-launcher-branch-synchronization.md]
- An agent draft quotes a sourced human approval from another record; the wording guard refuses it. [S: Issue comment Hugo-Grellier 2026-10-05T23:00:38Z]
- `ballast run resume` of a run lowered by `continue` keeps being refused, pointing to the continuation run. [S: tools/spec_workflow/run.py]
- A refresh of a `published` run's packet runs no agent step and cannot change the decision log. [P: D-11]

## Known

- Autonomous `resume` is refused today with a message naming #21. [S: tools/spec_workflow/autonomy.py]
- The Autonomous workflow already runs discover, record-discovery and validate-discovery before `speckit.specify`. [S: templates/spec-kit/workflows/autonomous/workflow.yml]
- The workflow has no fix step: implementation review is followed by resolve-decisions, and #27 added no automatic fix loop. [S: templates/spec-kit/workflows/autonomous/workflow.yml] [S: specs/27-autonomous-core/spec.md]
- Limits are a wall-time deadline set at start (default 240 minutes) and a maximum of agent steps (default 30). [S: tools/spec_workflow/autonomy.py]
- #27 enforced no spend limit because reliable usage data is not available. [S: specs/27-autonomous-core/spec.md]
- Usage is a subscription quota, not metered spend; no paid API without a human decision. [S: docs/policies/model-routing.md]
- The headless agent may run only Spec Kit scripts and read-only git commands, so it cannot run the `[checks]` commands itself. [S: tools/spec_workflow/claude-settings.json]
- The acceptance packet of a finished Autonomous run is final today; #19 left the refresh entry point to #21. [S: specs/19-acceptance-packet/decisions.md#dec-0002--resolution]
- The approval-wording guard matches any approval phrase, including a quotation. [S: tools/spec_workflow/autonomy.py] [S: Issue comment Hugo-Grellier 2026-10-05T23:00:38Z]
- Branch synchronization (#18) is meant to cover Autonomous `resume` once #21 lands. [S: specs/TECHNICAL-SPEC.md#91-v10-target]

## Inferred

- The roughly 18 agent steps of the Autonomous workflow plus three fix cycles and a few retries fit the default 30-step limit only narrowly; the plan should check the default. [I]
- The plan should order the resume and retry fixes first, because they unblock the pilot for IAC-1. [I]
- Retries and fix cycles count against the agent-step limit, which serves as the attempt bound. [P: D-10]
- Check results reach the fix loop through the trusted `run-checks` step rather than the agent's own shell. [P: D-08]
- Autonomous `resume` re-enters `ballast-autonomous` at the blocked step; `continue` of a pre-implementation block refuses with a pointer to `resume`. [P: D-04]
- The approval-wording guard stays strict; the decide and review commands tell the agent to paraphrase and cite. [P: D-06]

## Undecided

None.

## Decisions

### D-01: Does Autonomous resume stay Autonomous?
- **Status**: settled
- **Question**: Does `ballast run resume` of a blocked Autonomous run continue in Autonomous through branch synchronization, or must it still lower to human-gated?
- **Why it matters**: decides whether a new ADR replaces ADR-0004's continuation rule and whether the resume path runs agent steps without prompts.
- **Sources**: [S: Issue #21 body] [S: specs/TECHNICAL-SPEC.md#91-v10-target] [S: docs/adr/0004-autonomous-provisional-decisions.md]
- **Options**:
  - A — Resume stays Autonomous after branch synchronization. Consequence: a new ADR updates ADR-0004's continuation rule.
  - B — Keep lowering to human-gated. Consequence: the Issue's main outcome is not met.
- **Recommended default**: A, because the Issue and the technical spec name it as this feature's outcome.
- **Answer**:
- **Resolution**: A. The Issue's main outcome and the v1.0 target say #21 lets Autonomous `resume` go through branch synchronization [S: Issue #21 body] [S: specs/TECHNICAL-SPEC.md#91-v10-target]; ADR-0004 bounded its refusal to "until #18" [S: docs/adr/0004-autonomous-provisional-decisions.md].

### D-02: How is a block resolution recorded on resume?
- **Status**: settled
- **Question**: When the operator resumes a blocked Autonomous run, is the resolution recorded as a human decision?
- **Why it matters**: decides what the resume command records and what the merge record shows.
- **Sources**: [S: specs/27-autonomous-core/spec.md] [S: tools/spec_workflow/autonomy.py]
- **Options**:
  - A — Record a `block-resolution` human decision from the trusted command. Consequence: the record shows who resolved the block.
  - B — Resume without a record. Consequence: the merge review loses the history.
- **Recommended default**: A, because FR-023 of #27 requires it.
- **Answer**:
- **Resolution**: A. FR-023 requires a block resolution to be recorded as a human decision [S: specs/27-autonomous-core/spec.md], and `block-resolution` is an existing human decision kind [S: tools/spec_workflow/autonomy.py].

### D-03: Fix loop bound
- **Status**: settled
- **Question**: How many automatic fix cycles run before a remaining finding blocks?
- **Why it matters**: sets the loop bound, its test and the block reason.
- **Sources**: [S: docs/policies/workflow.md] [S: specs/TECHNICAL-SPEC.md#61-fix-loop] [S: specs/27-autonomous-core/spec.md]
- **Options**:
  - A — Three cycles, then a high or critical finding blocks. Consequence: matches the workflow policy.
  - B — A configurable bound. Consequence: a new setting to validate.
- **Recommended default**: A, because the policy states it.
- **Answer**:
- **Resolution**: A. The workflow policy stops automated fix attempts after three cycles and escalates [S: docs/policies/workflow.md]; high and critical findings never pass provisionally [S: specs/27-autonomous-core/spec.md].

### D-04: Recovery path for a pre-implementation block
- **Status**: assumed
- **Question**: How does a run that blocked before implementation continue?
- **Why it matters**: decides whether `continue` gains a new lowering path into `ballast-feature` or `resume` covers the case.
- **Sources**: [S: Issue comment Hugo-Grellier 2026-10-05T20:44:26Z] [S: tools/spec_workflow/run.py]
- **Options**:
  - A — Autonomous `resume` re-enters `ballast-autonomous` at the blocked step; `continue` of a pre-implementation block refuses with a pointer to `resume`. Consequence: one new path, no cross-workflow step mapping.
  - B — `continue` also lowers into `ballast-feature` from the blocked step. Consequence: a step mapping between two workflows to build and keep aligned.
- **Recommended default**: A, because the comment accepts either path and A adds the least new surface.
- **Answer**:
- **Resolution**: A. Safe and reversible: it adds no authority, keeps `continue` unchanged for post-implementation blocks, and B can be added later.

### D-05: Recoverable agent-output errors
- **Status**: assumed
- **Question**: What happens when a recorder refuses an agent draft for a format reason such as a finding reason over 1000 characters?
- **Why it matters**: decides whether such an error ends the run and how retries are bounded.
- **Sources**: [S: Issue comment Hugo-Grellier 2026-10-05T22:13:34Z] [S: tools/spec_workflow/artifacts.py]
- **Options**:
  - A — Rerun the agent step with the validator's message, at most twice per step, counted against the agent-step limit; the command states the limit. Consequence: the draft stays the agent's own text.
  - B — Truncate with a pointer to the report. Consequence: the recorder rewrites agent text.
- **Recommended default**: A, because nothing rewrites agent output and the bound is reused.
- **Answer**:
- **Resolution**: A. Safe and reversible: the validator stays unchanged, content refusals (high findings, contradictions, protected inputs) stay terminal blocks, and the retry count is a setting.

### D-06: Approval wording in a quoted source
- **Status**: assumed
- **Question**: Should the approval-wording guard accept a quotation of a sourced human approval?
- **Why it matters**: decides whether the guard changes or the agent paraphrases.
- **Sources**: [S: Issue comment Hugo-Grellier 2026-10-05T23:00:38Z] [S: tools/spec_workflow/autonomy.py] [S: .specify/memory/constitution.md]
- **Options**:
  - A — Keep the guard; the decide and review commands tell the agent to paraphrase and cite, and a refusal is retried under D-05. Consequence: BL-INV-006 enforcement unchanged.
  - B — Accept quotations with a source. Consequence: a weaker guard that needs its own security review.
- **Recommended default**: A, because it keeps the existing guard.
- **Answer**:
- **Resolution**: A. Safe and reversible: no guard is weakened; only command wording and retry behavior change.

### D-07: Workflow-owned tasks in tasks.md
- **Status**: assumed
- **Question**: How are post-implementation steps the workflow runs itself kept from blocking `validate-implementation`?
- **Why it matters**: decides whether the tasks template or the implementation check changes.
- **Sources**: [S: Issue comment Hugo-Grellier 2026-10-05T21:06:09Z] [S: templates/spec-kit/workflows/autonomous/workflow.yml]
- **Options**:
  - A — The tasks template and preset keep workflow-owned steps out of `tasks.md`; the check is unchanged. Consequence: no task can be skipped by tagging it.
  - B — The check accepts tasks tagged as later workflow steps. Consequence: a tag an agent could misuse to skip work.
- **Recommended default**: A, because it does not weaken a check.
- **Answer**:
- **Resolution**: A. Safe and reversible: the implementation check keeps its strength and template guidance can change later.

### D-08: Check results for the confined agent
- **Status**: assumed
- **Question**: How does the implement or fix agent learn whether the `[checks]` commands pass?
- **Why it matters**: decides whether the headless permission model widens.
- **Sources**: [S: Issue comment Hugo-Grellier 2026-10-05T21:06:09Z] [S: tools/spec_workflow/claude-settings.json] [S: docs/policies/project/workflow.md]
- **Options**:
  - A — The trusted, confined `run-checks` step runs them and feeds failures to the bounded fix loop; agent permissions are unchanged and a test verifies this path. Consequence: no R2 permission change.
  - B — Allow the agent to run the `[checks]` commands. Consequence: an R2 change to the headless-agent permission model.
- **Recommended default**: A, because it keeps the permission model as it is.
- **Answer**:
- **Resolution**: A. Safe and reversible: it preserves the current boundary; widening it stays a separate decision.

### D-09: Wall time across pauses
- **Status**: assumed
- **Question**: Does the wall-time limit count the time a run is paused between invocations?
- **Why it matters**: with the current fixed deadline, a run paused overnight can never resume.
- **Sources**: [S: tools/spec_workflow/autonomy.py] [S: Issue #21 body]
- **Options**:
  - A — Count only time inside invocations; limits stay as set at start and resume cannot widen them. Consequence: the record stores active time per invocation.
  - B — Keep the fixed deadline. Consequence: resume after a long pause blocks as exhausted.
- **Recommended default**: A, because resume would otherwise rarely work.
- **Answer**:
- **Resolution**: A. Safe and reversible: each invocation still stops at the limit, and resume cannot raise it.

### D-10: Spend bound
- **Status**: assumed
- **Question**: How is the Issue's spend bound enforced?
- **Why it matters**: decides whether a cost measure is built.
- **Sources**: [S: Issue #21 body] [S: specs/27-autonomous-core/spec.md] [S: docs/policies/model-routing.md]
- **Options**:
  - A — Bound spend through the agent-step limit, counting every retry and fix cycle; the record states that monetary spend is not measured. Consequence: no new data source.
  - B — Add a token or cost limit. Consequence: depends on usage data that is not reliably available.
- **Recommended default**: A, because subscription quota is the cost and steps are measured.
- **Answer**:
- **Resolution**: A. Safe and reversible: it only stops runs earlier, and a usage limit can be added when data exists.

### D-11: Packet refresh entry point
- **Status**: assumed
- **Question**: Which entry point refreshes the packet of a finished Autonomous run?
- **Why it matters**: decides the new command surface.
- **Sources**: [S: Issue comment Hugo-Grellier 2026-10-05T22:05:10Z] [S: specs/19-acceptance-packet/decisions.md#dec-0002--resolution]
- **Options**:
  - A — `ballast run checkpoint RUN_ID`: Draft PR checkpoint and packet only, no agent, any run status. Consequence: reuses the #17 checkpoint unchanged.
  - B — Let `ballast run publish` checkpoint a `published` run. Consequence: overloads publish.
- **Recommended default**: A, because the Issue comment proposes it and it reuses the existing checkpoint.
- **Answer**:
- **Resolution**: A. Safe and reversible: it runs no agent and writes no decision.

### D-12: Runs started before branch pinning
- **Status**: assumed
- **Question**: How does the operator recover a run whose pin lacks the feature?
- **Why it matters**: a new trusted command would change ADR-0005's pin rule.
- **Sources**: [S: Issue comment Hugo-Grellier 2026-10-05T22:07:09Z] [S: docs/adr/0005-launcher-branch-synchronization.md]
- **Options**:
  - A — Document the manual operator step in the block's recovery and the policy. Consequence: no change to the accepted pin rule.
  - B — Add a trusted re-pin command. Consequence: an ADR change to the launcher's state writes.
- **Recommended default**: A, because the comment allows it and it leaves the accepted architecture unchanged.
- **Answer**:
- **Resolution**: A. Safe and reversible: documentation only; a command can follow.

## Question metrics

- **Rounds**: 0
- **Questions asked**: 0
- **Assumptions adopted**: 9
