# Spec reconciliation: adaptive `ballast init` (#13)

- Reviewer: claude/claude-opus-5-5, during the operator's human-gated continuation of Autonomous run `3ee0601b`; same provider as the author (reduced independence)
- Inputs: `spec.md`, `plan.md`, `research.md`, `contracts/`, `tasks.md` (50/50 done), the diff from `origin/main` (`tools/init`, `tools/ballast` `init`, `tools/cli.toml` `[init]`, `templates/init/*`, README, ADR-0012, TECHNICAL-SPEC, AGENTS.md), `tests/test_init.py`, `InitBootstrapTests` in `tests/test_ballast.py`, the reviews in this directory and [e2e.md](e2e.md)

## Criterion to evidence

| Criteria | Implementation | Executable evidence |
| --- | --- | --- |
| AC-001 to AC-003, SC-002 (blank) | `tools/init` stages check to verify; CLI bootstrap | `BlankRepositoryTests` (flags, exactly two prompts on a terminal, preflight after trust); e2e scenario 1 |
| AC-004 | stage `choose` refusal without a terminal | `MaterialChoiceRefusalTests` |
| AC-005, AC-033 | `tools/ballast` `init`, `init_ref`, `declarations().init`, `[cli] minimum` | `InitBootstrapTests` |
| AC-006 to AC-012, SC-003 | absent-only creates, one `.gitignore` append, `.ballast/init/proposed.patch` | `EstablishedRepositoryTests`; e2e scenario 2 (digests, `git apply --check`) |
| AC-009, AC-013 | stage `ignore` probes and rule proposals | `IgnoreConflictTests` |
| AC-013, AC-014, AC-018 to AC-020, SC-005 | trust never written, no commit or remote, inferred permissions commented, setup exceptions mapped to `install` | `BoundaryTests`; e2e (no commit, no remote) |
| AC-015 to AC-017 | `setup.GIT` prefix, no-follow evidence reads, `check` link refusal | `NoExecutionTests`; `ReviewFindingTests.test_a_linked_evidence_file_outside_the_root_is_never_read` |
| AC-021, AC-022, AC-024, AC-025, SC-006 | `verifier()`, `ci_lines()`, evidence comments, skip reasons | `EvidenceTests`; `test_an_oversized_gitignore_names_its_limit` |
| AC-023, AC-026, AC-027 | `fill()`, `agents_values()`, origin parsing, testing addendum | `GeneratedContentTests`; `test_a_description_with_braces_is_kept_verbatim` |
| AC-028 to AC-031, SC-004 | rerun keeps the pin, drift as patch, partial adoption | `RerunTests`; e2e reruns of both scenarios |
| AC-032, AC-034 | `report`, `report_stop` | `ReportTests`; `test_a_stop_after_an_append_reports_it` |
| SC-001 | the whole flow | `post_trust()` in every completing fixture; e2e: one init and one trust give `"refusal": null` for both repositories |
| SC-002 (established, no question) | evidence or `TO CONFIRM`, never a prompt | `test_an_established_terminal_run_asks_nothing`; e2e scenario 2 without a terminal |
| SC-007 | gates and e2e | [convergence.md](convergence.md) (gate results), [e2e.md](e2e.md) |
| FR-022, FR-023 | generic templates, stdlib only, `-IS`, no bytecode | `InvariantTests` |

## Gaps and their diagnosis

1. **FR-003 wording (specification stale).** It still listed "for any repository, evidence it cannot resolve" as a prompted choice, while the accepted clarification (spec Clarifications), R5, T014 and PD-0013 say an established repository is never asked and unresolved values are marked to confirm. The implementation follows the clarification. FR-003 now says so. This clarifies approved behavior and changes no product scope, so no `decisions.md` proposal was needed; the operator re-approves the spec at the continuation's `approve-intent` gate. This closes analyze I1 and engineering F-004.
2. **TECHNICAL-SPEC ref order (documentation stale).** Corrected to the existing pin, otherwise `--ref`, otherwise the CLI release, as ADR-0012 and the code have it (documentation F-002).
3. **README and research R6 claim that `docs/policies/project/` is read (documentation stale).** `tools/init` reads only `testing.md`, for existence. The claim was removed. FR-005 permits the directory as evidence and does not require it (documentation F-001).
4. **Implementation defects found by the reviews and the e2e run (implementation wrong).** These were fixed test-first:
   - the stop report omitted an append to `.gitignore` (AC-034);
   - `fill()` substituted again inside values;
   - the size reason was wrong for `.gitignore`;
   - the remedy for a linked `AGENTS.md` pointed at a patch that did not exist;
   - an abbreviated or repeated `--project`/`--ref` could override what the CLI checked;
   - the `checks` line said "confirm the inferred ones" when nothing was inferred.

   None changes a requirement.

Accepted residuals, all low or info:

- `verifier()` scope (engineering and security F-001). This is a spec-level choice: FR-012 bounds it.
- The private helpers `setup._open_dir` and `launcher._refusal` are shared under ADR-0012.
- AC-020's kept prior installation is setup's own ADR-0007 behavior, tested in `test_setup.py`.
- `python -m nox`/`tox` are not recognised verifiers (e2e note). This is a candidate follow-up.

No behavior exceeds the spec. No accepted ADR is contradicted. ADR-0012 stays the only new decision: it is still number 0012, since `origin/main` has ADR-0001 to ADR-0011.

- Verdict: CONVERGED
