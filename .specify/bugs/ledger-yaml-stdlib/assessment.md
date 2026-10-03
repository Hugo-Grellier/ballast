# Bug Assessment: Ledger report crashes while loading archived workflow YAML

- **Slug**: ledger-yaml-stdlib
- **Created**: 2026-10-02
- **Source**: https://github.com/Hugo-Grellier/ballast/issues/9
- **Source host**: github.com
- **URL policy**: allowlisted
- **Verdict**: valid
- **Severity**: high

## Report (verbatim or summarized)

The supplied report identifies Issue #9 as “ledger report crashes on archived runs: yaml import under python3 -I -S.” The GitHub page could not be retrieved in this environment (web fetch returned a cache miss; GitHub CLI could not connect), so its body, comments, and any exact run ID or traceback remain unverified. The verbatim URL is https://github.com/Hugo-Grellier/ballast/issues/9.

## Symptom

For an instrumented run with a saved workflow, `ballast ledger report --run RUN_ID` raises an uncaught `ModuleNotFoundError: No module named 'yaml'` when it reaches the archived workflow loader. It should produce the run report, including workflow compliance evidence. The same loader is used by ledger import, and aggregate reports that visit such a run can also fail.

## Reproduction

1. Use the installed launcher's ledger execution mode, which runs `ledger.py` with Python `-I -S` (`tools/spec_workflow/launcher.py:61`, `:248`).
2. Select an instrumented run with a saved `workflow.yml` and events, then request `ballast ledger report --run RUN_ID`. The report calls `_workflow_steps()` and `_workflow_identity()` for that run.
3. On this host, `python3 -I -S -c 'import yaml'` fails with `ModuleNotFoundError`. Calling `_workflow_document()` under those flags reproduces the same exception before the workflow file is read. The full launcher command was not run here because no archived run fixture is available in this checkout.

[NEEDS CLARIFICATION: The issue's exact command, traceback, and affected run IDs could not be fetched.]

## Suspected Code Paths

- `tools/spec_workflow/launcher.py:61` and `:248` — the ledger command is executed with `-IS`.
- `tools/spec_workflow/ledger.py:931-963` — workflow step and identity readers call `_workflow_document()`, which imports PyYAML before reading `workflow.yml`.
- `tools/spec_workflow/ledger.py:1567-1576` — an instrumented report reaches those readers for the active or archived run.
- `tools/spec_workflow/ledger.py:2002-2014` — aggregate reports call `report()` for each instrumented run.
- `tools/spec_workflow/ledger.py:2313` — the CLI catches ledger and data errors but not `ModuleNotFoundError`, so the exception escapes as a traceback.
- `tests/test_agent_run_ledger.py:252-264` and `:2246-2273` — YAML and archived-run tests execute inside the normal test interpreter, where PyYAML is available; they do not exercise the isolated CLI runtime.

## Root Cause Hypothesis

**Confidence: high.** The trusted launcher deliberately starts the ledger under `-I -S`, excluding site-packages, while `_workflow_document()` imports the third-party `yaml` package unconditionally. The isolated import failure and call to `_workflow_document()` were reproduced locally. The import occurs before its `try` block, and neither `report()` nor the CLI catches `ModuleNotFoundError`. This conflicts with the documented standard-library-only workflow-tool invariant. No ledger-data corruption is indicated; the report is unavailable.

## Proposed Remediation

**Preferred**: Remove the PyYAML dependency from `ledger.py`. Read only the workflow ID, version, step IDs, and gate types needed from the engine's normalized archived `workflow.yml` using a deliberately limited standard-library parser, with explicit accepted syntax and `LedgerError` on unsupported or malformed input. Keep digest and identity checks intact. Use a real normalized workflow fixture to establish the accepted syntax so existing archives remain readable. Do not relax the `-I -S` launch mode.

**Alternative**: Archive a validated JSON projection of those workflow fields when the run is created, then report from JSON. This avoids parsing YAML in the ledger, but existing archives still need a compatible read path or migration and the projection must be integrity-bound to the archived workflow.

**Files likely to change**:

- `tools/spec_workflow/ledger.py`
- `tests/test_agent_run_ledger.py`

**Tests to add or update**:

- Spawn the ledger in a subprocess under `python3 -I -S` against a disposable archived run and assert `report --run RUN_ID` succeeds without site-packages. Cover `report --all` and import if they use the same reader.
- Verify the accepted engine-normalized YAML forms and malformed/unsupported YAML fail with a controlled ledger error; preserve archived identity and digest mismatch checks.

## Risks & Considerations

- A narrow YAML reader must reject unsupported forms rather than silently misread workflow identity or step order; those fields determine compliance evidence.
- Archived runs must remain readable after worktree removal. Adding JSON only for new runs would leave older archives broken.
- This is an availability failure in a read/report path, with no evidence of lost ledger events. It also masks report status behind a traceback.
- The current tests depend on PyYAML in the normal interpreter, which conceals the installed command's isolation behavior. The fix should preserve the documented trusted-launcher and standard-library-only boundaries.

## Open Questions

- [NEEDS CLARIFICATION: Does the issue include a concrete archived workflow form outside the repository's normalized test fixture? The issue page was unavailable.]

## Review Notes (gate approved 2026-10-02)

- Issue #9 body confirmed: existing archives (LoreForge holds 7 runs) must stay readable; archives contain engine-normalized PyYAML `safe_dump` output only, so the reader targets that form and rejects anything else. Compare against a real archived `workflow.yml` shape, not only the test fixture.
- Acceptance criteria in Issue #9 require a subprocess test of `ledger.py report --all` under `python3 -I -S` with an archived-run fixture (not optional), and that test must fail on current `main`.
- `ledger.py` must import nothing outside the standard library.
