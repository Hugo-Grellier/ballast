# Decisions: Adaptive init

## DEC-0001 — Proposal

- **Found during**: independent security review of PR #86 (SEC-001, 2026-10-06).
- **Conflict**: Research R7 listed `uv run`, `uvx` and `make <target>` as recognised verifiers with any following program or target, and `npm|pnpm|yarn|bun run` with any script. A hostile repository's CI could therefore place `uv run python -c ...`, `uvx twine upload`, `make deploy`, `npm run publish` or `pytest -p <plugin>` in `ballast.toml` as active `[checks] commands`, presented with an `# evidence:` comment as if they were sanctioned gates. FR-012 and AC-021 make a CI step that "runs a verification command" an active check; R7 is where "verification command" is defined.
- **Label**: spec ambiguity (security hardening; FR-012 and AC-021 stay true, R7 narrows).
- **Proposal**: A CI command is direct only when it runs a known verifier: `uv run`/`uvx` must be followed immediately by one, `make` only for `test|check|lint`, `<pm> run` only for the named scripts (`test`, `lint`, `check`, `typecheck`, `format:check`), `npx` only for its listed tools, and `pytest` not with `-p`. Any other command of those shapes is written commented and marked inferred, so it never runs until the operator moves it. `spec.md` is unchanged; research R7, `README.md` and `templates/init/testing.md` say so.
- **Needs**: human resolution (operator).

## DEC-0001 — Resolution

- **Status**: accepted provisionally by the agent under the operator's standing authority for v1.0 issues (2026-10-05); listed for the operator's merge review of PR #86.
- **Resolution**: as proposed.
- **Changed now**: `tools/init` `verifier()` returns `direct`, `inferred` or none; `detect_checks` records the inferred kind. Research R7, `README.md` and `templates/init/testing.md` updated.
- **Tests**: `EvidenceTests.test_only_known_verifiers_in_ci_become_active_checks` in `tests/test_init.py`.
