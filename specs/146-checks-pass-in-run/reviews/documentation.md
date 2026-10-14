# Documentation review: 146-checks-pass-in-run (specialists, after the run-checks block)

- Reviewer: claude-opus-5-5, independent context (agent-provisional)
- Scope: `templates/policies/spec-kit-workflow.md` (the source of the installed policy), `docs/adr/0021-check-command-environment.md`, the "Extended by" note in `docs/adr/0018-runner-recorded-acceptance-checks.md`, the `ballast.toml` `[checks]` change, the docstring of `tests/parallel.py`, `README.md` and the repository `AGENTS.md`. Judged against AC-019, AC-020, FR-013, FR-014 and `docs/policies/documentation.md`. The branch base is `0bddeb8`. Since 4491448, no documentation file changed. Only the run record and two review reports did.

## Policy template (AC-019, FR-013)

- The runner contract rows for `checks-implementation`/`checks-fix-N`, `run-checks` and the Chat `checks` row say "confined, in the check environment" and link to the Autonomous runs section. The fix-loop row names the immediate `check-timeout` block.
- The **Check timeout** paragraph covers `[checks] timeout_minutes`: its default of 30, its bounds of 1–240 (matching `autonomy.CHECK_TIMEOUT`), its trusted source, and the wall-time bound. It also covers the immediate block with no cycle consumed, the recovery (matching `LIMIT_RECOVERY`), the re-entry step, the mixed-failure case and the final `run-checks` `postcondition` block. HD-0002 matches that last statement in practice.
- The **Check environment** paragraph names what is removed, what is kept, the scope across every mode, and that agent steps keep the guard and the variables. It cites ADR-0021 "in the Ballast repository", so the installed text stays valid in other projects.
- The recovery section names the `check-timeout` re-entry point.
- The block-category table at line 682 still lists the `limit` forms as the agent-step limit, wall-time limit, fix cycles and draft retries, without `check-timeout`. The Check timeout paragraph documents it, but the table is incomplete.

## ADR-0021 (AC-020, FR-014)

- The ADR has a Status (`proposed`, with the merge as its only acceptance), Risk R2, Extends (ADR-0018, and ADR-0010 as amended by ADR-0020), Context, Decision, why a check gains no authority, Consequences and Rejected alternatives. It records that agent steps keep the guard and the run variables, and that `check-timeout` becomes a limit outcome once #153 ships. `CheckEnvironmentDocumentTests` asserts these points.
- ADR-0018 gains a one-line back-link, and its accepted text is otherwise unchanged.

## `[checks]` command and repository docs

- `ballast.toml` runs `uv run --locked python tests/parallel.py` with `timeout_minutes = 60`. The docstring of `tests/parallel.py` says that the sequential command stays what CI runs. `AGENTS.md` and `CLAUDE.md` list the sequential command, which matches CI and AC-013. A reader of `AGENTS.md` does not learn that `[checks]` uses the parallel runner. The plan review settled that this belongs in the PR body.
- `README.md` line 158 still shows `timeout_minutes = 30` as an example. It does not mention the bounds, the CI-like environment or the `check-timeout` block. The policy is the authoritative adopter document.
- The installed `docs/policies/spec-kit-workflow.md` comes from the pinned release. Changing only the template is correct.
- The PR body needs to describe HD-0002 accurately. The final check failed in-run, and the operator classified it as a flake on the strength of a green rerun outside the run (1483 s). That duration is operator-reported, not runner-recorded. The engineering and test reports already ask for this.

## Verification

- Read the template sections above (grep for `check-timeout` and the block-category table), ADR-0018, ADR-0020, ADR-0021, `README.md` near line 158 and `AGENTS.md`. Confirmed with `git diff 4491448 --stat` that no documentation file changed since the last approved documentation review.

<!-- ballast-findings: begin -->
## Findings (recorded from the review draft)

- F-001 (low, spec-ambiguity, open): README.md shows [checks] timeout_minutes = 30 but does not mention its bounds, the CI-like check environment or the check-timeout block, and does not link the policy paragraphs; the policy is authoritative, so adopters can still find it.
- F-002 (low, spec-ambiguity, open): The policy's block-category table lists the limit forms (agent steps, wall time, fix cycles, draft retries) without check-timeout; the Check timeout paragraph documents it, but the table is incomplete.
- F-003 (info, spec-ambiguity, open): AGENTS.md lists only the sequential test command, correct for CI (AC-013), while [checks] runs tests/parallel.py; the PR body must state both commands and present HD-0002's 1483 s as operator-reported, not runner-recorded.
<!-- ballast-findings: end -->
