# Bug Verification: systemd-run expands `$` in Codex prompts

- **Slug**: systemd-run-expands-dollar
- **Tested**: 2026-10-03
- **Assessment**: ./assessment.md
- **Fix**: ./fix.md
- **Result**: verified

## Summary

On systemd 259 the agent wrapper, run under real `systemd-run`, now delivers a `$speckit-plan` prompt byte-for-byte; the same test against the unfixed `agent.py` loses the prompt. The full suite (145 tests) and lint pass, with no regressions.

## Checks Performed

| Check | Command / Action | Result | Notes |
|-------|------------------|--------|-------|
| Reproduction, raw systemd (assessment steps 1-2) | `systemd-run --user --scope --quiet --collect [--expand-environment=no] -- printf '%s\n' '$speckit-specify hi'` | pass | Host still expands without the option (exit 0, blank line); with `--expand-environment=no` the argument survives. Confirms the mechanism the fix relies on. |
| Reproduction through the wrapper (post-fix) | `ScopeContainmentTests::test_real_scope_passes_a_dollar_prompt_unchanged` (real `systemd-run`, fake `codex`) | pass | `tools/spec_workflow/bin/codex exec '$speckit-plan'` → fake Codex receives `$speckit-plan`. |
| Fail-before check | New tests copied into a throwaway `git worktree` at `HEAD` (unfixed `agent.py`) | pass (fails as expected) | `test_codex_gets_workspace_write_sandbox` and the real-scope test fail; the pre-254 test passes, as expected for a compatibility guard. Worktree removed afterwards. |
| New / updated tests | `uv run --no-project --python 3.13 --with pyyaml python -m unittest -v <3 tests>` | pass | AC 1 (byte-for-byte on >= 254), AC 2 (< 254 still runs, option omitted), AC 3 (`$` prompt test through the wrapper). |
| Regression suite | `uv run --no-project --python 3.13 --with pyyaml python -m unittest tests/test_*.py` | pass | `Ran 145 tests`, `OK`, on Linux with a systemd 259 user session, so the real-systemd tests ran. |
| Lint / format | `uvx ruff check && uvx ruff format --check` | pass | `All checks passed!`, `61 files already formatted`. |
| Real Codex CLI end-to-end (`ballast run`, `integration=codex`) | — | not-run | Would launch a real Codex agent session (paid, networked); the wrapper test with a fake `codex` covers the argument path. |
| Real systemd < 254 | — | not-run | No such host available; covered by the `FAKE_SYSTEMD_PRE_254` fake only. |

## Output Excerpts

```
$ systemd-run --version | head -1
systemd 259 (259.5-0ubuntu3.4)

# unfixed agent.py + new tests
FAIL: test_codex_gets_workspace_write_sandbox
AssertionError: Lists differ: [..., 'sandbox_workspace_write.network_access=false', ''] != [..., '$speckit-tasks']
FAIL: test_real_scope_passes_a_dollar_prompt_unchanged
AssertionError: 'sandbox_workspace_write.network_access=false' != '$speckit-plan'
FAILED (failures=2)

# fixed
Ran 3 tests in 0.586s
OK
Ran 145 tests in 49.206s
OK
```

## Residual Risks

- The systemd < 254 path is verified only against a fake that rejects the option; no real older host was tested.
- The feature probe matches the literal `--expand-environment` in `systemd-run --help`. A build that renamed or hid the option from `--help` would silently fall back to today's (expanding) behaviour.
- A real Codex run was not exercised; the real-scope test stands in for it with a fake `codex` binary.
- R2 change (how the launcher executes agents): needs explicit human approval on the PR.

## Recommendation

Close the bug once the PR is approved and merged. The fix is verified end-to-end through real `systemd-run` 259 on the wrapper path, with a demonstrated fail-before/pass-after. Optional follow-up: one `ballast run` with `integration=codex` after merge to confirm the full path with the real CLI.
