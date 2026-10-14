# Documentation review: 146-checks-pass-in-run (specialists)

- Reviewer: claude-opus-5-5, independent context (agent-provisional)
- Scope: `templates/policies/spec-kit-workflow.md` (the source of the installed policy), `docs/adr/0021-check-command-environment.md` including the uncommitted T031 edit, the "Extended by" note in `docs/adr/0018-runner-recorded-acceptance-checks.md`, the `ballast.toml` `[checks]` change in `bd80a3e`, the docstring of `tests/parallel.py`, and the adopter-facing `README.md` and repository `AGENTS.md`. Judged against AC-019, AC-020, FR-013, FR-014 and `docs/policies/documentation.md`.

## Policy template (AC-019, FR-013)

- The runner contract rows for `checks-implementation`/`checks-fix-N`, `run-checks` and the Chat `checks` row say "confined, in the check environment" and link to the Autonomous runs section. The fix-loop row names the immediate `check-timeout` block.
- The **Check timeout** paragraph states `[checks] timeout_minutes`, its default 30 and bounds 1–240 (matching `autonomy.CHECK_TIMEOUT`), that it is read only from the trusted `ballast.toml`, and that the remaining wall time bounds each command. It covers the immediate block with no cycle consumed, the recovery (matching `LIMIT_RECOVERY`), the re-entry step, the mixed-failure case, and the final `run-checks` `postcondition` block.
- The **Check environment** paragraph names what is removed and what is kept, the scope (every mode, commands and acceptance checks), and that agent steps keep the guard and the variables. It cites ADR-0021 "in the Ballast repository", as the policy does for ADR-0018 and ADR-0020, so the installed text stays valid in other projects.
- The recovery section names the `check-timeout` re-entry point.
- The **Stop rule** paragraph, which came with the rebase, already defers to ADR-0020, so the policy needed no edit for the new ADR-0021 citation. T031 correctly left it alone.
- The block-category table still lists the `limit` forms as "the agent-step limit, the wall-time limit, the three fix cycles, or the two draft retries", without `check-timeout`. The Check timeout paragraph covers it, so a reader can find it, but the table is now incomplete.

## ADR-0021 (AC-020, FR-014)

- It has Status (`proposed`, with the merge as its only acceptance), Risk R2, Extends, Context with the three recorded causes, Decision, why a check gains no authority, Consequences and Rejected alternatives. It records that agent steps keep the guard and the run variables.
- After T031, `Extends:` names ADR-0020 as the amendment to ADR-0010, and a Consequences bullet says that `check-timeout` becomes a Draft-PR limit outcome once #153 ships, with the resumable block applying until then. That matches ADR-0020's Delivery section. T032 asserts both in `tests/test_governance.py`, and the method name is unchanged, so the `acceptance-evidence.json` mapping for AC-020 still holds.
- ADR-0018 gains a one-line back-link, and its accepted text is otherwise unchanged.

## `[checks]` command and repository docs

- `ballast.toml` now runs `uv run --locked python tests/parallel.py` with `timeout_minutes = 60`. `tests/parallel.py`'s docstring says that the sequential command stays what CI runs and gives the usage. `AGENTS.md` and `CLAUDE.md` list the sequential command for the fast gate, which matches `.github/workflows/ci.yml` and AC-013. So the docs are correct, but a reader of `AGENTS.md` does not learn that the run's `[checks]` uses the parallel runner. The second plan review (F-003) settles that in the PR body, which must state both commands.
- `README.md` still shows `[checks] timeout_minutes = 30` and says the commands "run confined before final acceptance". It does not mention the bounds, the CI-like environment or the `check-timeout` block, and it does not link the policy paragraphs. The policy is the authoritative adopter document.
- The installed `docs/policies/spec-kit-workflow.md` comes from the pinned release and is rebuilt by `ballast setup`. Changing only the template is correct.

## Verification

- Read the template sections above, ADR-0018, ADR-0020 and ADR-0021, `README.md` lines 150–165, `AGENTS.md`, `.github/workflows/ci.yml`, and `tests/test_governance.py` `CheckEnvironmentDocumentTests`.
- Checked that `tasks.md` T020 and T024 now record their outcomes, and that Phase 9 (T031–T033) is in the wave list and dependency notes.

<!-- ballast-findings: begin -->
## Findings (recorded from the review draft)

- F-001 (low, spec-ambiguity, open): README.md shows [checks] timeout_minutes = 30 but does not mention its bounds, the CI-like check environment or the check-timeout block, and does not link the policy paragraphs; the policy is authoritative, so adopters can still find it.
- F-002 (low, spec-ambiguity, open): The policy's block-category table lists the limit forms (agent steps, wall time, fix cycles, draft retries) without check-timeout; the Check timeout paragraph documents it, but the table is now incomplete.
- F-003 (info, spec-ambiguity, open): AGENTS.md lists only the sequential test command, correct for CI (AC-013), while [checks] now runs tests/parallel.py; the PR body must state both commands, as the second plan review's F-003 requires.
<!-- ballast-findings: end -->
