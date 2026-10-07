# ADR-0017: Operator-only tasks are deferred to the PR by the recorder, and a criterion may map to no test

- Status: proposed (2026-10-07, with the fix for [#112](https://github.com/Hugo-Grellier/ballast/issues/112)). Resolved by the driving agent under the operator's standing authority for v1.0 issues (2026-10-05), listed for merge review; merging the PR is the human approval that accepts it.
- Amends: feature 21's D-07 (the implementation check stays unchanged) and the manifest rule of [ADR-0006](0006-review-packet-reads.md)'s packet and `ledger-schema.md` (every AC maps to at least one test).

## Context

An Autonomous run of an R1 UI feature blocked at `validate-implementation`: `speckit.tasks` generated a manual browser check and a demo recording, which the confined agent cannot do, and only an operator rewriting `tasks.md` let the run reach its Draft PR. Two causes:

- The tasks guidance Ballast installs in `.specify/templates/tasks-template.md` never reaches the agent. Spec Kit resolves the `explicit-task-dependencies` preset's own `tasks-template.md` first, so #21's "Workflow-owned steps" paragraph (D-07, option A) was shadowed too.
- Even with guidance, a visible criterion can need an operator check, and D-07 left no way to keep such a task open.

The same run's packet showed every criterion `missing`: `acceptance-evidence.json` had to map every AC to a unit test, so one UI criterion made the whole manifest unrepresentable, including the criteria that do have tests.

## Decision

- **Guidance where it is read.** `preset.patch` carries Ballast's task guidance (acceptance evidence, operator-only checks, workflow-owned steps) into the preset's tasks template, and the tasks skill says not to create tasks the agent cannot do. Demo captures are requested with `ballast run demo`, never as a task.
- **Recorded deferral, Autonomous only** (D-07 option B, bounded). A remaining operator-only task is tagged `[DEFERRED-TO-PR]` among its leading tags and left open. The trusted recorder of the `tasks` decision lists every open tagged task in that decision (`deferred`, a runner-owned field an agent draft cannot set). `validate-implementation` and `convergence` accept an open task only when it is tagged and listed, with the same text, in the current tasks decision. A task tagged later, or a listed task whose tag or text changed, stays pending and blocks. Chat and human-gated runs accept no deferral.
- **Visible, never evidence.** The run record and the Draft PR body show a `Deferred to the PR` section from the tasks decision; the acceptance packet lists the open tagged tasks at head, linked to their lines, and names them on the rows of the criteria they cite, verified ones included. In an Autonomous run, an open tagged task the current tasks decision does not list with the same text is shown as pending, not deferred, and names no criterion. Task text is inert. A deferred task never changes a criterion's state.
- **A criterion may map to no test.** `acceptance-evidence.json` may map an AC to `[]`. The ledger reports that AC as `missing`, never `passed`, `ballast ledger check` refuses any test for it, and the packet shows it `missing`. The manifest still names every approved AC, so totals stay honest.

## Consequences

- An eligible UI feature can reach its Draft PR unattended; what it could not verify is listed in three places for the merge reviewer.
- The tasks agent could tag real work as deferred. That choice is agent-provisional like every Autonomous decision, recorded before implementation, visible in the record, PR and packet, and reviewed at merge. An implementation that changes nothing still fails the existing check.
- A manifest using `[]` is refused by an older pinned Ballast.
- The trusted runner still records no per-criterion check in an Autonomous run: evidence comes only from `ballast ledger check`. Running mapped tests from the runner is a new execution path (R2) left to #117, as ADR-0006 already noted.

## Rejected alternatives

- Guidance only (D-07 option A as is): it did not reach the agent, and a criterion needing a browser check still has no task that can be ticked.
- Accepting any tagged task without the recorded list: the implement or fix agent could defer work after the fact.
- A manifest entry such as `"manual"` that counts as evidence: an agent would mark its own criterion verified.
