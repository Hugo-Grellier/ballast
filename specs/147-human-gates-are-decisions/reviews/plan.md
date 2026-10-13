# Plan review: Human gates are decisions, not command relays

- Review: plan (third pass, after block resolution HD-0004)
- Reviewer: claude-opus-5-5 (independent context; same provider as the author, as the run record notes for DEC-0004)
- Feature: `specs/147-human-gates-are-decisions` (Autonomous run `2e651132`, R2)
- The verdict and findings are agent-provisional and are rendered by the recorder from the review draft.

## What was reviewed

- `plan.md`, `spec.md` (intent PD-0009), `research.md` (R1 to R14 and the governing-documents section), `contracts/cli.md`, `quickstart.md`, `tasks.md` (now present) and `autonomous/record.md` (PD-0001 to PD-0009; block resolutions HD-0001 to HD-0004).
- `AGENTS.md`, `docs/policies/workflow.md`, `docs/policies/project/workflow.md` and the engineering review skill. `decisions.md` does not exist, which is expected before implementation. `docs/policies/project/engineering.md` does not exist.
- Spot checks of the current tree: `_trust` in `tools/spec_workflow/launcher.py` (it refuses on the tamper marker and on the `in-progress` marker before anything else), the step list of `.specify/workflows/ballast-feature/workflow.yml` (the `tasks`, `analyze` and `review-tasks` steps follow this review), and the tracked files under `docs/policies/` (only `project/` is tracked).

## Changes since the second pass

The operator resolved the tasks-gate block as D-09 (HD-0004, recorded on Issue #147): `ballast trust` keeps today's terminal-free behavior, so the operator's agent session may run it outside a workflow step and never inside one. The plan was checked for each place D-09 touches:

- Summary item 2, Constitution Check principle 3, the `launcher.py` row of Repository Impact ("no terminal check, D-09") and the `ballast.toml` row (unchanged) all state D-09.
- Research R8 keeps `reject`, `resolve` and `mode` terminal-only and states the consequence for the `operator-trust` privileged-action kind.
- The ADR-0020 residual-risk list in the plan and in research now carries the D-09 risk: without a terminal test on `trust`, the step boundary alone keeps a confined agent from vouching for its own changes.
- The second-pass findings are folded in: the engine-gate dependency (research R8, the ADR list, the AC-011 test in quickstart), the human-gated record question (the cli.md matrix row now says no operator run record exists and none is added), and `continue` as Autonomous-source only (cli.md, with the test asserting which refusal fires).

## How the plan was judged

The D-09 boundary was checked against the code rather than the text alone. `_trust` already refuses while the `in-progress` marker exists, and the step sandbox hides operator state, so "refused inside a step" holds today without new code. `BALLAST_AGENT_STEP` adds defence in depth, and the plan correctly says it is not the boundary. "On a checkout the session set up" is policy wording the launcher cannot enforce; the residual-risk entry states that plainly, which is adequate for merge review.

Coverage: AC-016 now reads both ways (reject refused, trust outside a step works, trust inside a step refused), and quickstart and the T023 test plan match it. The other criteria were traced as in the second pass; nothing in the trust-refresh design (R1 to R6), batch approval (R9), the headless Chat step (R10) or recovery (R11 to R14) changed.

Downstream consistency: `tasks.md` was changed during the HD-0004 block and is regenerated or revised by the `tasks` and `analyze` steps that run after this review. It still carries pre-D-09 text in several places, and its ADR task omits the D-09 risk. Separately, the plan and research say policies are mirrored into `docs/policies/`, while only `docs/policies/project/` is tracked and `tasks.md` correctly says the rest are git-ignored installed copies. The draft's findings record these.

## Boundaries checked

Trust inside a step (marker refusal in `_trust`, sandbox, environment variable as defence in depth only), relays from a confined step, the actor rule's refusal of an unnamed terminal-less decision, `mode` at a terminal against a human-gated to Chat switch, the fail-closed decision-free block set, same-repository anchoring of the refresh, and BL-INV-006 rendering of relayed records.

<!-- ballast-findings: begin -->
## Findings (recorded from the review draft)

- F-001 (medium, spec-violation, accepted-provisionally): tasks.md still contradicts D-09: T024 adds a terminal check to _trust ('ballast trust needs the operator at a terminal'), T045 tells AGENTS.md and its templates that trust is terminal-only, the Phase 4 goal says trust stays at the operator's terminal, and Wave 3 labels T024 'trust terminal'. This conflicts with the operator's D-09 resolution, spec AC-016 and FR-010, plan.md and research R8, and with T023's own test that terminal-less trust outside a step records a baseline. plan.md, the artifact under review, is correct. The tasks and analyze steps run next and must remove these lines; T023 makes the conflict fail a test rather than pass silently.
- F-002 (low, missing-test, open): plan.md and research list the D-09 residual risk for ADR-0020 (trust has no terminal test, so only the step boundary keeps a confined agent from vouching for its own changes), but T041's residual-risk list omits it and T049's governance test checks only the pseudo-terminal risk. T041 also cites that risk as 'plan-review F-002', a first-pass identifier. Tasks should add the D-09 risk to T041 and T049.
- F-003 (low, spec-ambiguity, open): plan.md Repository Impact ('and their docs/policies/ mirrors') and research's governing-documents section ('mirrored into docs/policies/ by the same change') say the installed policies are edited, but only docs/policies/project/ is tracked and tasks.md Phase 7 correctly says not to edit the rest. Also stale in tasks.md: T001's contract edits are already in cli.md, and Parallel Opportunities still lists the dropped ballast.toml comment and the deferred constitution in Wave 1.
<!-- ballast-findings: end -->
