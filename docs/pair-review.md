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
Coverage: <criteria, affected paths, boundaries and checks inspected>
Findings:
- <severity; file:line; requirement or invariant; trigger and consequence; fix>
Verification gaps: <none, or missing evidence>
```

Use `changes_required` for concrete defects or missing required acceptance
evidence, and `blocked` when missing access or an unresolved decision prevents
review. With no findings, say so and name what was inspected. Approval covers
only the reviewed head and scope; it is not a human merge decision.
