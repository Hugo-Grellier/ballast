# Bug Assessment: systemd-run expands `$` in Codex prompts

- **Slug**: systemd-run-expands-dollar
- **Created**: 2026-10-03
- **Source**: https://github.com/Hugo-Grellier/ballast/issues/26 (host: github.com; policy: allowlisted; read with `gh issue view`)
- **Verdict**: valid
- **Severity**: high

## Report (verbatim or summarized)

Issue #26, "fix(agent): systemd-run expands $ in Codex prompts". `ballast run` with `integration=codex` (or `auto` resolving to Codex) fails at the first agent step on systemd >= 254:

```
Invalid environment variable name evaluates to an empty string: speckit-specify Issue #12: ...
No prompt provided. Either specify one as an argument or pipe the prompt into stdin.
Status: failed
```

Acceptance criteria from the issue:

- Agent arguments reach the agent CLI byte-for-byte, including a leading `$`, on systemd >= 254.
- systemd < 254, which lacks `--expand-environment`, still runs the agent (the flag is passed only when `systemd-run` supports it).
- A test covers a `$`-prefixed prompt through the wrapper.

Intake comment (owner): bug, R2, in scope = pass `--expand-environment=no` when supported plus a regression test; out of scope = raising the minimum systemd version, other containment changes, `ballast doctor` (#12). Workaround: `ballast run resume RUN_ID -i integration=claude`.

## Symptom

Under `systemd-run` >= 254, the wrapper's `systemd-run --user --scope ... -- codex exec '$speckit-<cmd> ...'` substitutes `$speckit` (an unset variable) with an empty string, so Codex receives no prompt and the step fails. Expected: the prompt reaches Codex unchanged. Claude prompts (`/speckit-...`) are unaffected.

## Reproduction

Reproduced locally on systemd 259 (259.5-0ubuntu3.4):

1. `systemd-run --user --scope --quiet --collect -- printf '%s\n' '$speckit-specify hi'` prints `Invalid environment variable name evaluates to an empty string: speckit-specify hi` followed by an empty line, and exits 0.
2. `systemd-run --user --scope --quiet --collect --expand-environment=no -- printf '%s\n' '$speckit-specify hi'` prints `$speckit-specify hi`.
3. `systemd-run --help` lists `--expand-environment=BOOL`.

Note: systemd-run exits 0 in step 1, so the failure surfaces only as the agent CLI's own error.

## Suspected Code Paths

- `tools/spec_workflow/agent.py:main()` (the `argv = [systemd_run, "--user", "--scope", "--quiet", "--collect", f"--unit=...", "--", *argv]` block) — builds the scope command without `--expand-environment=no`; this is the only `systemd-run` invocation that carries agent arguments.
- `tools/spec_workflow/agent.py:_containment()` — resolves `systemd-run` and checks `scope_available()`; the natural place to probe flag support once.
- `tools/spec_workflow/launcher.py:scope_available()` — only checks that a user manager answers; carries no version information.
- `tests/test_spec_workflow.py:FAKE_SYSTEMD_RUN` — the stand-in `exec`s the command after `--` verbatim, so it cannot model expansion. That is why `test_codex_gets_workspace_write_sandbox` (which already passes `$speckit-tasks`) did not catch the bug.

## Root Cause Hypothesis

systemd 254 made `systemd-run` expand `$VAR`/`${VAR}` in the command line by default (`--expand-environment=yes`). The wrapper predates or ignored that change and passes the agent prompt as a command-line argument, so a Codex prompt beginning with `$speckit-...` is rewritten before Codex starts. Confidence: high (reproduced, and adding the flag restores the argument).

## Proposed Remediation

**Preferred** (operator decision, 2026-10-03): In `agent.py`, decide once whether `systemd-run` supports `--expand-environment` by running the resolved `systemd-run --help` and checking for the literal `--expand-environment`; if present, insert `--expand-environment=no` before `--` in the scope command in `main()`. Treat a failing probe as "unsupported" so older hosts keep running unchanged, and never skip the scope. Fold the probe into `_containment()` (e.g. return the flag list alongside the path) to keep `main()` linear. This tests the capability directly and also covers distro builds that backport the flag.

**Alternatives**:
- Parse `systemd-run --version` (flag introduced in 254). Not chosen: misses backports and infers a capability from a version number.
- Always pass the flag. Smallest diff, but breaks systemd < 254 (`unrecognized option`), violating acceptance criterion 2.
- Escape `$` as `$$` in agent arguments. Works only when expansion is on, so it still needs version detection, and it corrupts arguments on < 254. Rejected.

**Files likely to change**:
- `tools/spec_workflow/agent.py`
- `tests/test_spec_workflow.py`

**Tests to add or update**:
- Make the fake `systemd-run` model >= 254: answer `--help` with or without `--expand-environment` (env var, default: with), and when it supports the flag and `--expand-environment=no` is absent, blank `$word` tokens in the command the way systemd does. Then `test_codex_gets_workspace_write_sandbox` (or a new focused test) asserts Codex receives `$speckit-tasks` byte-for-byte.
- Fake whose `--help` lacks the flag and that rejects unknown options: the wrapper omits the flag and the agent still runs with its prompt intact.
- Optional, in the real-systemd gated classes: run the `codex` wrapper with a fake `codex` binary under real `systemd-run` and assert the `$`-prefixed prompt arrives. Covers the real flag spelling; skipped in CI without a user manager.

## Risks & Considerations

- R2 per the issue: changes how the launcher executes agents. No change to permissions, sandboxing or scope containment; the flag only disables argument rewriting. Needs explicit human approval.
- The version probe runs a binary resolved from `PATH` (already the case for `systemd-run` itself); no new trust surface, but the probe must not fail open into skipping containment — on probe error, still use the scope, just without the flag.
- Wrapper runs under `python3 -I -S`, stdlib-only: the probe must use `subprocess` with a short timeout and no shell.
- Distro builds that backport the flag to < 254 would be missed by version parsing (harmless: same behaviour as today). Builds reporting >= 254 without the flag are not known.
- Same latent risk for `${VAR}` and any `$` later in a prompt (e.g. issue text pasted into the prompt); the fix covers all of them, not just the leading token.

## Open Questions

- None. Operator chose the `--help` probe.
