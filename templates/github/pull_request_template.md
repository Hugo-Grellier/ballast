## Summary

## Related issue

Link the leaf issue and state whether this PR closes it. Link its parent Epic or planned Milestone when relevant.

## Acceptance evidence

Map each acceptance criterion of the issue to its check, test or review evidence. Link the plan when one was written.

## Risk

- [ ] R0
- [ ] R1
- [ ] R2 — link the human approval comment on the issue or PR, and say whether it is direct or relayed by the coordinator

## Spec

For R1 and R2: the approved spec delta and how this PR meets it. A PR that changes no spec states the hash of its approved empty delta; a reviewer cannot waive it.

Spec hash: <`spec_check.py --diff-hash BASE` of this PR, equal to the approved hash>
Spec approval: <link to the issue comment starting `Spec approved:`>

Scenario to test map: each added or modified scenario, its `Test:` reference, and the fail-on-base evidence of the test review; each removed scenario and what happened to its tests. For R0: “none”.

## Affected areas

## Verification performed

Commands and results at the submitted head; note any gate not run and why.

## Independent review

Reviewer (provider + model, effort), reviewed head, verdict, rounds, and findings fixed or remaining. List triggered specialist reviews, or “none” with reason.

## Execution evidence

Link the issue's phase/attempt history and instruction revision. State requested versus observed worker routes, known waits and remaining gaps. For coordinator executions, name them and say their routes are self-reported and unverified. Keep local destinations, raw worker output and account details private.

## Migration impact

## Security impact

## Known limitations / follow-up

Follow the project's PR title convention. Add screenshots for visible UI changes.
