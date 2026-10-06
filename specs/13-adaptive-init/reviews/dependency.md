# Dependency review: adaptive `ballast init` (#13)

- Review: dependency, specialists recheck after fix cycle 3 (the last) of Autonomous run `3ee0601b`
- Reviewer: claude/claude-opus-5-5, agent-provisional; same provider as the author (reduced independence)
- Scope: every package, lockfile, requirements file, image, Action and runtime the change from `11134f1` adds or alters.
- Read: `docs/policies/dependencies.md`, `docs/policies/project/dependencies.md`, `pyproject.toml`, `tools/init`, the cycle-3 fix input and the run record.

## What changed since the last review

`git diff bd6ac47` touches only the run record; nothing dependency-relevant changed in fix cycle 3.

## Assessment

- No package, lockfile, `requirements*.txt`, container image or GitHub Action is added or updated.
- The only `pyproject.toml` edit adds `tools/init` to ruff's `extend-include`: lint configuration, not a dependency.
- `tools/init` imports only the standard library and runs under `python3 -I -S`. Its Python floor (3.11, for `tomllib` and `datetime.UTC`) matches `tools/setup` and ruff's `target-version`.
- CI workflows are scanned with a line scanner, not a YAML library, keeping the workflow tools standard-library-only (FR-023).
- It starts only `git`, through the config-safe `setup.GIT` prefix. Setup's `uvx` and Spec Kit pins are unchanged; tests still get `pyyaml` through `uv run --with`.

## Checks

Both ruff commands exit 2 because `uvx` cannot write the read-only `~/.local/share/uv/tools` in the runner's confinement, before ruff starts. That is the environment, not a dependency defect; the lint gate must still pass in a writable environment before merge.

Recommendation: accept.

<!-- ballast-findings: begin -->
## Findings (recorded from the review draft)

None.
<!-- ballast-findings: end -->
