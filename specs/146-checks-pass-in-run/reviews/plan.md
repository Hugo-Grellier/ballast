# Plan review: Make the [checks] test command pass inside an Autonomous run

- Review kind: plan (engineering review of the design), second pass after the run resumed at `validate-plan`
- Reviewer: claude/claude-opus-5-5, independent context
- Run: Autonomous `a060b968`; this verdict is agent-provisional

## Why this review ran again

The run blocked at `checks-fix-1` on an upstream sync. The operator resolved it (HD-0001 in the run record): the branch was rebased on `main` at 617df9c, the feature's ADR was renumbered from 0020 to 0021 because `main` now holds `docs/adr/0020-autonomous-stop-rule.md`, and T020 and D-001 were applied outside any step (commit bd80a3e: `[checks]` test command `uv run --locked python tests/parallel.py`, `timeout_minutes = 60`), followed by `ballast trust`. The plan, research, tasks, quickstart and decisions changed during the block, so the plan is reviewed again against the rebased base.

## What was reviewed

- `spec.md`, `intent.md`, `plan.md`, `research.md` (R1 to R13), `data-model.md`, both contracts, `quickstart.md`, `tasks.md`, `decisions.md` (D-001 to D-003 and the wording clarifications) and the run record.
- `AGENTS.md`, `docs/policies/workflow.md` (review matrix), `docs/policies/project/workflow.md` (R2 boundaries), `docs/policies/engineering.md` and the `ballast-engineering-review` skill.
- The accepted architecture now on the base: `docs/adr/0020-autonomous-stop-rule.md`, which amends ADR-0004 and ADR-0010, and the policy's Stop rule paragraph in `templates/policies/spec-kit-workflow.md`; plus `docs/adr/0021-check-command-environment.md` and `docs/adr/0018-runner-recorded-acceptance-checks.md`.
- `git diff 617df9c..HEAD` for `ballast.toml`, `.github/` and `AGENTS.md`/`CLAUDE.md`.

## How the design was checked

- The design is unchanged from the first plan review (PD-0006): one pure `check_env` at the single `run_commands` call site, an unchanged bwrap argv, unchanged agent steps and `_operator_step_guard`, and the timeout-only recorder rule with its `_reentry` mapping. The earlier code checks still hold.
- The earlier findings are carried into tasks: the wall-time wording (first F-001) is in the tasks header and T017/T019; the insertion point and the unchanged cycle count on first record and recheck (first F-002) are in T014 and T018; the deferred AC-014/SC-001 evidence (first F-003) stays with R11 and T021.
- Numbering: `docs/adr/` now has 0020 (stop rule, from `main`) and 0021 (this feature). Plan, research, tasks, quickstart, the policy template and the ADR itself use 0021. `spec.md` and `discovery.md` still say 0020.
- D-001 sits inside the plan's conditional path (R9, the `tests/parallel.py` row): the parallel runner was needed, the `[checks]` command change went through the `ballast.toml` and `ballast trust` path R10 prescribes, and `.github/workflows/ci.yml` is not in the diff, so CI keeps the sequential command (AC-013). `operator-trust` is listed in `[autonomous] authorized_privileged_actions`.
- ADR-0020 against this design: its stop rule makes every `limit` a limit outcome (a Draft PR) instead of a block, but its Delivery section keeps ADR-0010's blocks and limits as written until #151 to #154 ship, and the policy's Stop rule paragraph says the same. A new resumable `limit` kind is therefore consistent with the accepted architecture today and falls under the limit outcome once #153 ships. The plan's architecture references and ADR-0021 cite ADR-0010 but not the ADR-0020 amendment.

## Assessment

The rebased plan still meets every acceptance criterion with a small, centralized change and stays standard-library-only. Risk stays R2, and the required reviews (engineering, security, test, documentation, with architecture for the R2 boundary) follow the review matrix. D-001 and T020 are in the plan's own conditional scope and were applied outside a step through the authorized trust path. The remaining notes concern references and wording, not the design; none blocks implementation.

<!-- ballast-findings: begin -->
## Findings (recorded from the review draft)

- F-001 (low, architecture-issue, open): The plan's architecture references and ADR-0021 extend ADR-0010 but do not cite ADR-0020, which amends it: under ADR-0020 every limit, check-timeout included, becomes a Draft-PR limit outcome once #153 ships. The policy's Stop rule paragraph already covers this, so behavior is consistent today; ADR-0021 or the plan should note it so #153 treats check-timeout like the other limits.
- F-002 (info, spec-ambiguity, open): spec.md and discovery.md still say the new ADR is numbered 0020; after the rebase it is 0021. This is a wording clarification that spec reconciliation can record, not a change of intent.
- F-003 (info, missing-test, open): With D-001 applied, [checks] runs tests/parallel.py while CI and AGENTS.md keep the sequential command. The PR should state both commands and the measured run-checks duration for SC-002, and keep AC-014 and SC-001 as deferred evidence (R11, T021), not cite this run's v1.0.0 run-checks for FR-001.
<!-- ballast-findings: end -->
