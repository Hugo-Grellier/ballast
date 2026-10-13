# Documentation review: 146-checks-pass-in-run (specialists)

- Reviewer: claude-opus-5-5, independent context (agent-provisional)
- Scope: `templates/policies/spec-kit-workflow.md` (the source of the installed `docs/policies/spec-kit-workflow.md`), new `docs/adr/0021-check-command-environment.md`, the "Extended by" note in `docs/adr/0018-runner-recorded-acceptance-checks.md`, and the adopter-facing `README.md` `[checks]` section. Judged against AC-019, AC-020, FR-013, FR-014 and the documentation policy.

## Policy template (AC-019, FR-013)

- The runner contract rows for `checks-implementation`/`checks-fix-N`, `run-checks` and the Chat `checks` row now say "confined, in the check environment" and link to the Autonomous runs section.
- The new **Check timeout** paragraph states the setting `[checks] timeout_minutes`, its default 30 and bounds 1–240 (which match `autonomy.CHECK_TIMEOUT`), that it is read only from the trusted `ballast.toml`, and that the run's remaining wall time also bounds each command. It covers the immediate `check-timeout` block, the absence of a consumed cycle, and the recovery text, which matches `LIMIT_RECOVERY`. It also says where resume re-enters, and that a mixed failure keeps the fix loop while a timed-out final `run-checks` still blocks as `postcondition`.
- The new **Check environment** paragraph names what is removed (guard entries wherever they appear, `BALLAST_GIT`, both run variables) and what is kept (order of the other entries, nothing added, bwrap, read-only host, hidden credentials, secret filter, protected inputs, read-only checkout for acceptance checks). It states the scope (Autonomous, Chat and human-gated; commands and acceptance checks) and that agent steps keep the guard and the variables. It cites ADR-0021 the way ADR-0018 is cited, without a repository link, so the text stays valid when it is installed in another project.
- The recovery section adds the `check-timeout` re-entry point.
- The wording is plain and concrete, and it matches the code.

## ADR-0021 (AC-020, FR-014)

- It has Status (proposed, with the merge as the only acceptance), Risk R2, Extends (ADR-0018 and ADR-0010), Context with the three recorded causes, Decision, a section on why a check gains no authority, Consequences (including projects pinning an earlier release), and Rejected alternatives. It records that agent steps keep both the guard and the run variables. This satisfies AC-020.
- ADR-0018 gains a one-line "Extended by" back-link. Its accepted text is otherwise unchanged.

## Observations

- `README.md` shows `[checks] timeout_minutes = 30` and says the commands "run confined before final acceptance". It does not mention the bounds, the CI-like environment or the `check-timeout` block, and it does not link to the policy's Check timeout and Check environment paragraphs. The policy is the authoritative adopter document, so this is low and open.
- The installed `docs/policies/spec-kit-workflow.md` in this repository comes from the pinned v1.0.0 release and is rebuilt by `ballast setup`. Changing only the template is correct.
- `decisions.md` D-001 proposes switching the `[checks]` command to `tests/parallel.py`. If the operator applies it, `AGENTS.md` "Commands" lists only the sequential command for the fast gate, which is still correct for CI. The PR should state which command the `[checks]` table uses.

<!-- ballast-findings: begin -->
## Findings (recorded from the review draft)

- F-001 (low, spec-ambiguity, open): README.md shows [checks] timeout_minutes = 30 but does not mention its bounds, the CI-like check environment or the check-timeout block, nor link the policy paragraphs; the policy is authoritative, so adopters can still find it.
- F-002 (info, spec-ambiguity, open): If D-001 switches the [checks] command to tests/parallel.py, the PR should state which command [checks] runs, since AGENTS.md lists only the sequential command, which stays correct for CI.
<!-- ballast-findings: end -->
