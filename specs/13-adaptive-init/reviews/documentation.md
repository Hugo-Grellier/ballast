# Documentation review: adaptive `ballast init` (#13)

- Review: documentation, specialists recheck after fix cycle 3 (the last) of Autonomous run `3ee0601b`
- Reviewer: claude/claude-opus-5-5, agent-provisional; same provider as the author (reduced independence)
- Scope: README (the init section and manual-adoption fallback), `docs/adr/0012-init-before-pin.md`, the `specs/TECHNICAL-SPEC.md` #13 status line, `AGENTS.md`, the `tools/ballast` docstring, `USAGE`, `INIT_HINT` and `PIN_REMEDY`, the `tools/cli.toml` comment and `templates/init/*`, compared with `tools/init` and `tools/ballast`.
- Read: `docs/policies/documentation.md`, `docs/policies/workflow.md`, the spec, plan, the cycle-3 fix input and the run record. There is no `docs/policies/project/documentation.md`.

## What changed since the last review

`git diff bd6ac47` touches only the run record; no documented file or behavior changed in fix cycle 3.

## Assessment

Flags, supported stacks, absent-only writes, the single `.gitignore` append, the ignored patch, the never-trust and never-commit boundary, rerun behavior and refusal remedies match the code. ADR-0012 extends ADR-0002 without editing its history. No document misstates a safety boundary, permission or recovery step.

## Residual mismatches, re-checked

- README line 68 (and ADR-0012) list `docs/policies/project/` as inspected evidence; `tools/init` never lists or reads that directory beyond the `testing.md` target.
- The TECHNICAL-SPEC #13 status gives the ref order as `--ref`, then the CLI release, then the pin; the code and ADR-0012 put an existing pin first and refuse a different `--ref`.
- `TOO_LARGE` (tools/init:166) states 256 KiB, also for the 1 MiB `.gitignore` limit.
- `AGENTS.md` line 9 still says there are no ADRs, although `docs/adr/` holds ADR-0001 to ADR-0012; the line predates this change.

<!-- ballast-findings: begin -->
## Findings (recorded from the review draft)

- F-001 (low, implementation-bug, open): Unchanged since cycle 0. The README and ADR-0012 list docs/policies/project/ as inspected evidence, and research R6 says its names are read; tools/init never lists or reads that directory beyond the testing.md target. Fix: drop the claim or record the names as present evidence.
- F-002 (low, spec-ambiguity, open): Unchanged since cycle 0. The TECHNICAL-SPEC #13 status gives the ref order as --ref, then the CLI release, then the pin; the code and ADR-0012 put an existing pin first and refuse a different --ref. Same drift as analyze I2; spec reconciliation should fix the wording.
- F-003 (info, implementation-bug, open): Unchanged since cycle 0. A .gitignore over the 1 MiB limit is refused or skipped with the shared TOO_LARGE text, larger than 256 KiB, so the reason states the wrong limit.
- F-004 (info, spec-ambiguity, open): Unchanged since cycle 0. AGENTS.md still says there are no ADRs yet, although docs/adr holds ADR-0001 to ADR-0012. The line predates this change but sits next to the edited layout line.
<!-- ballast-findings: end -->

## Resolution

- F-001: fixed. The README evidence list no longer names `docs/policies/project/`; research R6 now says only `docs/policies/project/testing.md` is checked, for existence. FR-005 lists the directory as permitted evidence, not required.
- F-002: fixed. The TECHNICAL-SPEC #13 status gives the order the code and ADR-0012 use: the existing pin (a different `--ref` cannot move it), otherwise `--ref`, otherwise the CLI's release.
- F-003: fixed test-first. The size reason names the limit that applied (`too_large(limit)`: "larger than 1024 KiB" for `.gitignore`), and an oversized `.gitignore` no longer gets the link remedy (`test_an_oversized_gitignore_names_its_limit`).
- F-004: fixed. `AGENTS.md` says decisions are ADRs under `docs/adr/`.

Gates on the host after the rebase onto `origin/main` (with #82): `uvx ruff check && uvx ruff format --check` pass; the full suite `uv run --no-project --isolated --python 3.13 --with pyyaml python -m unittest tests/test_*.py` passes (counts in [convergence.md](convergence.md)). The networked end-to-end run is in [e2e.md](e2e.md).

- Verdict: approved
