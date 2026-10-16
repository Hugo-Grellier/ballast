# From issue to reviewed PR

## Execution record

For each worker attempt, include the requested and observed model/effort and
verification source required by [model routing](model-routing.md). A routing
mismatch or an unverified launch blocks that worker's task before implementation.

Use the named phases understand, decompose, clarify/plan, implement, verify,
review, and publish, even where sections below group them together. On starting,
record the issue, branch when known, start time in UTC, and the revision of the
instructions being followed (commit or content hash; identify local modifications).
On resuming, link the existing attempt and record the resume; retain its history.

Keep the progress note as the current snapshot. Add concise milestone comments
for completed or skipped phases, blockers, resumed work, and review verdicts.
Batch adjacent phase results in one comment when useful. Record:

```text
Phase | UTC time | completed / skipped / blocked / resumed / failed
Reason or result | evidence link | next action
```

Report a failure or block before stopping, even when no PR exists. Preserve
earlier milestone comments; correct mistakes explicitly. Record a skipped phase
and why it is unnecessary. Record review round numbers and findings resolved or
remaining, and distinguish human decisions from routine agent choices. Link
checks and reviews rather than copying their full logs. Keep secrets, private
reasoning, and sensitive prompt contents out of these records.

At handoff or completion, summarize the outcome, start/end or pause times,
known waiting intervals, human decision count, plan and implementation review
rounds separately, and remaining gaps. Link any later regression or revert back
to the original issue/PR. Use unknown for missing observations; do not reconstruct
runtime, cost, or a successful phase from assumptions. Interrupted traces may be
incomplete: reconcile them with repository and GitHub evidence when resuming.

## 1. Read and recover

Read the issue, all comments, linked requirements, parent/child relationships,
dependencies, and any existing branch or PR. Inspect repository instructions,
working-tree status, relevant code, and CI commands. Use the repository's
authenticated GitHub tooling; confirm the target repository before writing.

On a resume, reconcile the issue's last progress note with the actual branch,
diff, PR reviews, and CI. Reuse matching children and PRs. A stale note is not
evidence that work completed. Preserve unrelated local changes; isolate your
work if necessary. If access or a dependency is missing, report the exact block.

For an investigation request, answer the question with evidence, options, and a
recommendation on the issue, then stop. Do not turn it into implementation.

## 2. Scope and decompose

Identify the outcome, acceptance criteria, constraints, and blockers. Infer
routine technical details from repository evidence and record assumptions.
Ask only for decisions that materially change the outcome or cross `AGENTS.md`
authority boundaries. A conflicting request needs resolution before affected work.

Keep one issue when it delivers one cohesive outcome. Put implementation steps
in a short issue checklist; individual functions and files are not child issues.

Split automatically when the request contains distinct outcomes that can be
specified, reviewed, and merged separately. Stay within the parent's requested
scope. Create each child with its outcome, boundaries, acceptance criteria,
parent link, and dependencies. Map every parent acceptance criterion to a child
or to explicit integration work. Link children from the parent, using native
relationships when available and ordinary links otherwise.

Check existing children before creating new ones. Create and link children
sequentially, inspecting GitHub after a partial failure before retrying. Keep
the parent open while its outcome is incomplete. Work on unblocked children in
dependency order. Independent children may be delegated in isolated branches;
each still gets its own checks and independent review.

Use one PR per independently mergeable child. A child requiring an unmerged
dependency waits for merge; continue independent children and report the wait.
Use one cohesive PR when splitting would produce unusable intermediate states.

## 3. Clarify and plan as needed

For each selected leaf issue, check whether its acceptance criteria are clear
enough to implement. Ask focused questions for unresolved product choices; give
the relevant evidence, options, and a recommendation. Bundle related questions.
Use answers already recorded rather than asking again. If uncertainty prevents
meaningful decomposition, clarify it in step 2 before creating children.

Wait for answers before implementing behavior that depends on them. Continue
independent exploration or tasks while waiting. Record the human's decisions and
update affected acceptance criteria and child boundaries before proceeding.

Scale the plan to the work:

- Small, clear fix: a short checklist and verification command, then implement.
- Work across components, a migration, or a consequential boundary: outline the
  approach, affected interfaces, dependency order, verification, and relevant
  failure or rollback behavior. Ask the independent pair to review the plan using
  [pair-review.md](pair-review.md) before implementation.
- A decision crossing the authority boundaries in `AGENTS.md`: present the plan
  and exact decision for human approval before implementing the affected part.

Routine technical plans need no human approval checkpoint. Resolve blocking plan
review findings before coding; use the same round limit and escalation
rule as the final review ([pair-review.md](pair-review.md#round-limit)). If a required plan review is unavailable, report that
block before implementing the affected work.

Post a concise issue progress note before implementation. Include:

```markdown
### Agent progress
Outcome and acceptance: ...
Plan: [short checklist, or child links in dependency order]
Assumptions / decisions needed: ...
Branch / PR: ...
Verification planned: ...
Next action / blocker: ...
```

Maintain that note at meaningful milestones and handoffs. Keep new product
decisions in their own clearly attributed comments; an agent assumption is not
a human decision. Separate spec/plan/task files are unnecessary for routine work.

## 4. Implement and check

Use a dedicated issue worktree and branch based on the repository's current
target branch. Follow [portable execution](execution.md) for creation, dispatch,
and recovery; reuse the matching worktree and branch when continuing.
To dispatch workers as agent-native subagents, see
[subagent workers](subagent-workers.md).
Implement the plan in small coherent changes.
Verify acceptance criteria, failure behavior, and relevant compatibility.

Run the project's required checks and meaningful tests for the changed behavior.
Record exact commands and outcomes. Explain unavailable checks and failures,
including whether a failure exists on the base branch. Never weaken a check to
make the change pass. Inspect the final diff for scope, accidental files, and
secrets. Update affected docs and commit the intended changes.

If implementation reveals a consequential requirement conflict, record the
evidence and proposed resolution on the issue, then request the human decision.
Continue only work independent of that answer. Update the plan after resolution.

## 5. Review with a pair

Give a separate reviewer the instructions in [pair-review.md](pair-review.md),
the issue and relevant decisions, target base, exact head commit, and check
results. It must inspect the actual code and requirements with fresh context.
Use a separate agent or session; prefer another provider when already available.
Do not provision a paid service just to obtain review.

The reviewer may inspect and run checks but does not edit the author's branch.
An earlier plan review does not replace this review of the implemented change.

Fix actionable findings, rerun affected checks, and request review of the updated
head. For a disputed finding, record the evidence and request pair reassessment;
the author cannot dismiss a blocker alone. Escalate product disagreements to the
human. Repair-round scope, nonblocking findings and the round limit are in
[pair-review.md](pair-review.md#repair-rounds). If an independent reviewer is unavailable, do not
publish; report the missing review to the human. The standalone `publish` helper
refuses a head without a completed review.

## 6. Publish and finish

Push only the intended issue branch. Create or update one PR using the repository
template; reuse an existing matching PR. Link the leaf issue with a closing
reference only when that PR delivers its complete outcome. Link the parent as
context without closing it prematurely. Record the reviewer verdict and reviewed
head in the PR body, with a link to detailed findings when available.

Check required CI and merge status after publication. Resolve failures introduced
by this change. If the branch changes to resolve conflicts, rerun affected checks
and refresh review. If CI is still running, retain a draft and report it as pending.
Identify required CI by the intended workflow, check, and current commit; a
similarly named green check from another workflow is insufficient. Record required,
advisory, and justified skipped checks separately. Keep acceptance requirements
binding even when a hosting platform's branch rules are weaker.

Mark ready for human merge only when:

- Every in-scope acceptance criterion has evidence in the PR.
- Required local checks and CI pass at the current head.
- The independent pair approves the current head, with no unresolved blockers.
- Required human decisions are recorded and the PR has no merge conflicts.
- The description states compatibility/migration effects and remaining limitations.

Otherwise leave the PR as a draft and state the exact blocker and next action.
Use the hosting platform's ready state only after checking these conditions;
successful publication alone does not mean ready.

Update the issue progress note with PR links, verification, review status, and
remaining dependencies. Keep issues open until their outcome merges and is complete.
Report PR links and any blocked children to the user. Stop at human merge.
