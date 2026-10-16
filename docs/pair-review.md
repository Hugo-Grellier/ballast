# Independent pair review

Use this file in a separate review agent or session. Review the change; leave
edits to the author.

## Inputs and scope

Read repository instructions, the issue and comments, relevant accepted
requirements and decisions, the full diff against the target base, and the exact
head commit under review. Inspect affected callers, tests, and failure paths.
Use the author's summary and check results as leads to verify. If an input is
inaccessible or the checked-out head differs, report the gap before giving a verdict.

For a plan review, evaluate the proposed approach and record its version or issue
comment link. Approval of a plan does not approve the eventual implementation.

## Review

- Map every acceptance criterion to implementation and verification; flag gaps.
- Find correctness failures, regressions, concurrency problems, partial failures,
  and data loss risks. Explain a concrete trigger and consequence.
- Check relevant boundaries: access control, untrusted input, secrets, identity,
  compatibility, migrations, and external effects when touched by the change.
- Compare the design with existing contracts and patterns. Identify unnecessary
  dependencies, duplicated authority, or abstractions that can be removed.
- Check that tests exercise the intended behavior and that required checks cover
  the submitted head. Run focused checks when necessary and available.
- Verify documentation describes the behavior actually shipped.

Prioritize actionable defects. Label optional improvements as nonblocking. Do
not demand unrelated cleanup or expand product scope. When requirements conflict,
name the conflicting sources and the decision needed.

## Result

Return:

```text
Reviewed head: <full commit SHA; or plan link for a plan review>
Verdict: approved | changes_required | blocked
CI on reviewed head: pass | fail | pending
Coverage: <criteria, affected paths, boundaries and checks inspected>
Findings:
- <severity; file:line; requirement or invariant; trigger and consequence; fix>
Verification gaps: <none, or missing evidence>
```

Use `changes_required` for concrete defects or missing required acceptance
evidence, and `blocked` when missing access or an unresolved decision prevents
review. With no findings, say so and name what was inspected. Approval covers
only the reviewed head and scope; it is not a human merge decision.

Report CI as observed on the exact reviewed SHA; a local gate does not stand in
for it. `fail` blocks approval. `pending` (no PR yet, or still running) does not
block approval but is stated under `Verification gaps`. The coordinator confirms
CI `pass` on that same head before marking the PR ready or merging
([issue workflow, step 6](issue-workflow.md#6-publish-and-finish)). Any head
change after approval invalidates both the review and the CI check.

## Repair rounds

A repair round re-reviews the author's fixes for the earlier findings.

- Scope: the delta since the reviewed head plus any code the delta affects (callers,
  tests, docs). The reviewer need not redo the full review, and may be the same
  reviewer as the previous round.
- Use a fresh full review of the head, by a reviewer without the earlier rounds,
  when the delta changes the risk class, is large relative to the original change,
  or is round three.
- Each round returns the full result block for its head, including CI.

Nonblocking findings default to a follow-up issue. The author may apply one in the
same PR only when it is trivial and inside the issue's scope. The coordinator does
not commit changes to the author's branch; it sends the suggestion to the author.
Any change made after a review, including one for a nonblocking finding, is a new
delta and needs review before approval.

## Round limit

At most three review/fix rounds. After the third, stop automatic repair and report
the unresolved findings in a draft PR; the operator decides how to proceed. This is
the only statement of the limit; other documents link here.
