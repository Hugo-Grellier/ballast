# Contract: workflow definitions

`templates/spec-kit/workflows/feature/workflow.yml` (`ballast-feature`) is unchanged.

The two new definitions are installed by `tools/setup` with `specify workflow add --dev`, as `ballast-feature` is:

- `templates/spec-kit/workflows/autonomous/workflow.yml` (`ballast-autonomous`)
- `templates/spec-kit/workflows/continue/workflow.yml` (`ballast-continue`)

Every `shell` step:

- runs `python3 -I -S .ballast/spec_workflow/artifacts.py <check> --run {{ context.run_id }}`;
- never interpolates an input;
- in an Autonomous run, first verifies that the run record exists with `workflow == ballast-autonomous` and `status == active`, and that `record.md` matches the log.

## `ballast-autonomous`

The definition has no `gate` step. The table maps each human gate of `ballast-feature` to its replacement.

| # | Step id | Type | Replaces | Postcondition / effect |
| --- | --- | --- | --- | --- |
| 1 | `preflight` | shell `autonomous-preflight` | `preflight` | Launcher env; run record present, autonomous, active, eligible |
| 2 | `decide-scope` | command `speckit.ballast.decide` (args `scope`) | `scope-gate` | Draft `scope.json` or block |
| 3 | `record-scope` | shell `record-decision --point scope` | — | PD appended; `record.md` rendered |
| 4 | `specify` | command `speckit.specify` | same | — ; its `idea` names the Issue snapshot (DEC-0008) |
| 5 | `validate-spec` | shell `spec` | same | unchanged check |
| 6 | `clarify` | command `speckit.ballast.clarify` | `clarify` | Drafts `clarification-*.json`, or block |
| 7 | `record-clarifications` | shell `record-decision --point clarification` | — | One PD per assumption (zero allowed) |
| 8 | `validate-clarified-spec` | shell `clarified-spec` | same | unchanged check (AC-005) |
| 9 | `decide-intent` | command `speckit.ballast.decide` (args `intent`) | `approve-intent` | Draft `intent.json` |
| 10 | `record-provisional-intent` | shell | `record-intent` | PD; provisional block in `intent.md` |
| 11 | `validate-intent` | shell `intent` | same | Mode-aware `check_intent` |
| 12 | `plan` | command `speckit.plan` | same | — |
| 13 | `validate-plan` | shell `plan` | same | — |
| 14 | `review-plan` | command `speckit.ballast.review` (args `plan`), `integration: {{ inputs.review_integration }}` | `review-plan` gate (manual review) | `reviews/plan.md` + draft |
| 15 | `record-plan-review` | shell `record-decision --point plan-review` | — | Blocks on every high or critical finding, whatever its proposed disposition (FR-019), and on any verdict other than `approved` (every review recorder) |
| 16 | `decide-plan` | command `speckit.ballast.decide` (args `plan`) | `review-plan` approval | Draft |
| 17 | `record-plan` | shell `record-decision --point plan` | — | — |
| 18 | `tasks` | command `speckit.tasks` | same | — |
| 19 | `validate-tasks` | shell `tasks` | same | — |
| 20 | `analyze` | command `speckit.analyze` | same | — |
| 21 | `decide-tasks` | command `speckit.ballast.decide` (args `tasks`) | `review-tasks` | Draft |
| 22 | `record-tasks` | shell `record-decision --point tasks` | — | — |
| 23 | `implementation-baseline` | shell | same | — |
| 24 | `implement` | command `speckit.implement` | `speckit.intent.implement` | — |
| 25 | `validate-implementation` | shell `implementation` | same | In a run with an operator record, also writes `.specify/workflow-state/required-reviews/<slug>.json`, the kinds step 28 will require (same computation, before reviewer-declared kinds); agents read it read-only |
| 26 | `review-implementation` | command `speckit.ballast.review` (args `implementation`), review integration | `review-implementation` gate | `reviews/engineering.md`, `reviews/test.md` |
| 27 | `review-specialists` | command `speckit.ballast.review` (args `specialists`), review integration | (manual today) | One report per required kind listed in the hint of step 25; `architecture` uses `ballast-engineering-review` focused on the ADRs and architecture sections the change touches |
| 28 | `record-implementation-review` | shell `record-decision --point implementation-review` | — | Required-kind coverage (R-08); severity block; risk re-check |
| 29 | `resolve-decisions` | command `speckit.ballast.resolve` | `reconcile-intent` | Provisional `DEC-NNNN — Resolution` records + drafts |
| 30 | `record-resolutions` | shell `record-decision --point decision-resolution` | — | — |
| 30a | `renew-intent` | shell `record-provisional-intent --renew` | — | When `spec.md`'s digest differs from the current intent PD, records a `postcondition` block (stale intent) naming the resolutions that changed it: the runner never decides intent (FR-010, FR-012; implementation review codex-1 F4, DEC-0006), and the continuation's `approve-intent` gate decides the changed spec. Otherwise a no-op. |
| 31 | `validate-decisions` | shell `decisions` | same | Mode-aware: provisional resolutions accepted only in Autonomous mode |
| 32 | `converge` | command `speckit.converge` | same | — |
| 33 | `reconcile-spec` | command `speckit.ballast.review` (args `spec-reconciliation`), review integration | `spec-reconciliation` gate | `reviews/convergence.md` with `- Verdict:` |
| 34 | `record-reconciliation` | shell `record-decision --point spec-reconciliation` | — | — |
| 35 | `validate-convergence` | shell `convergence` | same | Pending tasks block (no fix loop) |
| 35a | `run-checks` | shell `run-checks` (trusted, bubblewrap-confined) | — (agent-reported today) | Refuses before any check unless the code outside `specs/<f>/` still equals `frozen_tree` (review codex-1 F3). Runs `[checks] commands` from `ballast.toml`; non-zero, timeout or missing table blocks (research R-12), and so does a check that changes the checked tree. Records the tree digest taken before the checks (`git write-tree` of the index after `git add --all` in a private index file, excluding protected inputs) in the run record |
| 36 | `decide-final` | command `speckit.ballast.decide` (args `final-acceptance`) | `final-acceptance` | Draft |
| 37 | `record-final` | shell `record-decision --point final-acceptance` | — | Requires one current PD for every point (SC-002); re-hashes every current PD's `artifact` and re-runs `check_intent`; requires the tree digest recorded at `run-checks` to be unchanged |

`run.py` publishes after step 37 (contract [cli.md](cli.md#ballast-run-publish-run_id)). The publisher recomputes the tree digest and refuses (`postcondition` block) unless it equals the one recorded at `run-checks`, so the published tree is the tree that passed checks and every review (plan review round 5).

**Frozen code after implementation review (round 6, H-2).** `record-implementation-review` (28) records the tree digest of everything outside `specs/<f>/`. `record-resolutions` (30), the recorder after `converge` (32) and `record-reconciliation` (34) refuse any change to that digest: after the reviews, author steps may change only the spec, plan, tasks, `decisions.md` and drafts. A resolution or convergence that needs a code change records a block (no fix loop in #27). Test: a source edit made in `resolve-decisions` or `converge` blocks the run.

**Drafts belong to the step that wrote them (round 6, H-3).** Before every agent step the wrapper moves any existing file in `specs/<f>/autonomous/drafts/` aside into the operator run directory, and after the step it lists the drafts the step created, with their SHA-256, in its protected `meta.json`. A recorder accepts only drafts listed for the immediately preceding agent step and refuses any other file in `drafts/`, so a draft planted by an earlier step (for example a review draft written by the author during `implement`) can never be attributed to a reviewer. The same rule covers every decision point. Test: a review draft planted before the reviewer step is refused.

**Writes after review.** Only `decide-final` (36) runs an agent after `run-checks`. It may write only its decision draft: the recorder at 37 fails the step when the tree digest changed. Reviewer steps (14, 26, 27, 33) may write only their report narrative and drafts: the recorder after each compares the tree digest taken before the review step, excluding `specs/<f>/reviews/` and `specs/<f>/autonomous/drafts/`, and fails on any other change. Tests: an edit made by `decide-final`, and a source edit made by a reviewer step, each block the run.

## `ballast-continue`

Steps:

```text
preflight (continue-preflight)
validate-clarified-spec
gate approve-intent → record-intent → validate-intent
validate-plan → gate review-plan
validate-tasks → gate review-tasks
validate-implementation → gate review-implementation
validate-decisions → gate spec-reconciliation
validate-convergence → gate final-acceptance
```

Gate messages and `show_file` match `ballast-feature`, and `on_reject: retry` is unchanged. There is no `command` step. A missing artifact fails its validator, and the operator completes that work interactively, then resumes; resume is allowed because the mode is human-gated.

## `.specify/extensions/ballast` commands

`speckit.ballast.decide` and `speckit.ballast.clarify` read the Issue snapshot `.specify/workflow-state/issues/<N>.md` as untrusted requirements data (DEC-0008).

Each command is installed from `templates/spec-kit/extensions/ballast/`. Its common rules:

- Read the policies, the skill files and the feature artifacts it names.
- Never edit `autonomous/record.md`, `intent.md` approval or provisional blocks, `.specify/`, `.ballast/` or `ballast.toml`.
- Write exactly the draft(s) named in [decision-draft.md](decision-draft.md).
- To stop, write `drafts/block.json` and print `RECONCILE_STATUS: BLOCKED_DECISION`.
- Label any text it writes about a gate as "agent-provisional"; never write "approved by" a human (AC-007).
