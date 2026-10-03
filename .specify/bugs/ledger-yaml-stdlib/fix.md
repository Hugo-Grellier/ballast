# Bug Fix: Ledger reports on archived workflow YAML

- **Slug**: ledger-yaml-stdlib
- **Fixed**: 2026-10-02T15:10:20+02:00
- **Assessment**: ./assessment.md
- **Status**: applied

## Summary

Replaced the ledger's PyYAML import with a standard-library reader for the workflow identity and step fields in engine-normalized archived YAML. Isolated ledger import and archived reports now run under `python3 -I -S`.

## Changes

| File | Change | Notes |
|------|--------|-------|
| `tools/spec_workflow/ledger.py` | modified | Reads only the needed block-style YAML fields; rejects unsupported or ambiguous forms with `LedgerError`, including mapping entries nested beneath scalar step fields. |
| `tests/test_agent_run_ledger.py` | modified | Adds isolated CLI coverage for import and archived reports, invalid YAML rejection, and identity and digest checks. |

## Tests Added or Updated

- `test_imports_engine_normalized_workflow_yaml` — covers wrapped fields and nested lists seen in a real archived engine workflow.
- `test_isolated_cli_reports_archived_run` — runs `report --all` and `report --run` on an archived run under `-I -S`.
- `test_isolated_cli_imports_run` — runs ledger import under `-I -S`.
- `test_isolated_cli_rejects_unsupported_workflow_yaml` and `test_workflow_reader_rejects_ambiguous_identity_and_steps` — require a controlled error for unsupported or ambiguous input.
- `test_workflow_digest_check_remains_enforced` and `test_workflow_identity_check_remains_enforced` — preserve archived integrity checks.
- A review follow-up added a malformed indentation case to `test_workflow_reader_rejects_ambiguous_identity_and_steps`; it failed before the reader change and passed afterward.

## Local Verification

- `python3 -m unittest tests.test_agent_run_ledger` → 58 passed.
- `python3 -m unittest tests/test_*.py` → 143 passed, 2 skipped.
- `UV_CACHE_DIR=/tmp/ledger-bug-test-uv-cache uvx ruff check && UV_CACHE_DIR=/tmp/ledger-bug-test-uv-cache uvx ruff format --check` → passed after the review follow-up.
- `git diff --check` → passed.
- Ran the archived `report --all` regression test with the original `ledger.py` copied into a disposable test location → failed with `ModuleNotFoundError: No module named 'yaml'` as expected; the changed version passed.
- Parsed a real archived engine workflow under `python3 -I -S` → identity and 26 steps extracted.
- `UV_CACHE_DIR=/tmp/ledger-bug-test-uv-cache uv run --no-project --python 3.13 --with pyyaml python -m unittest tests/test_*.py` → 143 passed after the review follow-up.
- The current ledger code reported five real LoreForge archives and produced an aggregate report under Python 3.13 `-I -S` after the review follow-up.

## Deviations from Assessment

The remediation stayed within the assessed code and test files. The Ruff suppression tags for six-argument functions remain necessary with the version used by the prescribed `uvx ruff` gate.

## Follow-ups

- Verification is recorded in `./test.md`.
