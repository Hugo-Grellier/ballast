# Bug Fix: systemd-run expands `$` in Codex prompts

- **Slug**: systemd-run-expands-dollar
- **Fixed**: 2026-10-03
- **Assessment**: ./assessment.md
- **Status**: applied

## Summary

The agent wrapper now asks the resolved `systemd-run` whether it supports `--expand-environment` (via `--help`) and, when it does, passes `--expand-environment=no` before `--`, so agent arguments such as `$speckit-plan` reach the CLI unchanged on systemd >= 254. Older or unreadable `systemd-run` keeps the scope without the option.

## Changes

| File | Change | Notes |
|------|--------|-------|
| `tools/spec_workflow/agent.py` | modified | `_containment()` probes `systemd-run --help` (5 s timeout, no shell; `OSError`/timeout = unsupported) and returns `(path, options)`; `main()` inserts the options before `--`. |
| `tests/test_spec_workflow.py` | modified | `FAKE_SYSTEMD_RUN` models systemd >= 254 by default (answers `--help` with the option, blanks `$` words unless `--expand-environment=no`) and < 254 under `FAKE_SYSTEMD_PRE_254` (help lacks the option, rejects it). |
| `tests/test_spec_workflow.py` | added tests | One pre-254 test, one real-systemd test. |

## Diff Highlights

```python
try:
    usage = subprocess.run(
        [systemd_run, "--help"], capture_output=True, timeout=5, check=False
    ).stdout
except (OSError, subprocess.TimeoutExpired):
    usage = b""
if b"--expand-environment" in usage:
    return systemd_run, ["--expand-environment=no"]
return systemd_run, []
```

## Tests Added or Updated

- `AgentWrapperTests::test_codex_gets_workspace_write_sandbox` — unchanged test, now meaningful: the default fake behaves like systemd >= 254, so `$speckit-tasks` must arrive byte-for-byte (AC 1, AC 3).
- `AgentWrapperTests::test_dollar_prompt_survives_systemd_without_expand_option` — fake < 254 rejects the option; the wrapper omits it and the prompt arrives intact (AC 2).
- `ScopeContainmentTests::test_real_scope_passes_a_dollar_prompt_unchanged` — real `systemd-run` with a fake `codex`; covers the real option spelling. Skipped without a systemd user manager.

## Local Verification

- `uvx ruff check && uvx ruff format --check` → all checks passed, 60 files formatted.
- `uv run --no-project --python 3.13 --with pyyaml python -m unittest tests/test_*.py` → `Ran 145 tests`, `OK` (Linux, systemd 259 user session; the real-systemd test ran).
- Regression check: with `agent.py` reverted to `HEAD`, `test_codex_gets_workspace_write_sandbox` and `test_real_scope_passes_a_dollar_prompt_unchanged` fail; the pre-254 test passes either way, as expected for the compatibility guard.

## Deviations from Assessment

None.

## Follow-ups

- R2: needs explicit human approval on the PR before merge.
- No real systemd < 254 host was available; the < 254 path is covered by the fake only.
