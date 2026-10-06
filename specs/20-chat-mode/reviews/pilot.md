# Pilot evidence: Chat mode (#20)

T075 needs a real interactive `claude` and `codex` session in a scratch repository with a real GitHub remote. Only the checks that need no interactive session or remote were run here (2026-10-06, Linux, systemd user session, `bwrap` with user namespaces, Spec Kit CLI 1.0.11, codex-cli 0.155.1). The rest moved to #24 (DEC-0004). The fresh-clone `ballast setup` of T071 is done (evidence in `tasks.md` T071).

## Done

| ID | Result |
| --- | --- |
| P-1 | `specify workflow run --help` and `specify workflow resume --help` (1.0.11) list only `--input` and `--json`. There is no single-step option, so R1 stands. |
| P-2 | `codex --help` lists `-s, --sandbox`, `-a, --ask-for-approval` with `never` ("Execution failures are immediately returned to the model") and a positional `[PROMPT]` for the interactive TUI. |
| Codex nesting | `autonomy.codex_sandbox_nests` on this host returns `False`: Codex's own sandbox does not start inside Ballast's bwrap. On this machine Chat therefore refuses Codex for a step and names `claude`, and reviews fall back to `claude` with `cross_provider: false`. |
| Real confinement (automated) | These ran in the full local gate with real `bwrap`, and the last one also with a real `systemd-run --user --scope`: `StepEntryTests.test_real_bwrap_keeps_protected_and_operator_paths_out_of_reach`, `StepEntryTests.test_real_bwrap_keeps_installed_skills_read_only`, `ForgeryTests.test_operator_records_are_out_of_reach_under_real_bwrap` and `StepCloseTests.test_real_scope_and_bwrap_step_is_confirmed_stopped`. |

## Moved to #24

These need a person at a real terminal, the real agent CLIs and a scratch GitHub repository. Per [DEC-0004](../decisions.md#dec-0004--proposal) they run in #24 (cross-repository v1.0 qualification), which the operator runs. The deterministic tests cover each AC, and these checks add evidence about real TUIs:

- **P-3**: in a Claude Chat step, resize the terminal, press Ctrl-C and run `/exit`. Expect the TUI to redraw, Ctrl-C to reach the agent, the step to end and the terminal to be restored, with no mouse mode left on (SEC-006). Codex cannot be checked on this host (no nested sandbox).
- **P-4**: press Shift+Tab out of `dontAsk` and ask for an edit of `ballast.toml` and for `curl`. Expect each tool call to be denied by the Chat hook with the "Press Shift+Tab" message, and no permission prompt (DEC-0001). This also confirms that the installed Claude Code passes `permission_mode` to `PreToolUse` hooks. If it does not, every call is denied, and the hook must be revisited.
- **P-5**: `/permissions`, then save an allow rule. Expect it to fail, because `.claude/` is read-only. A session-only rule must still be denied by the hook outside `dontAsk`.
- **Quickstart scenarios 1–7** with a real GitHub remote, recording run IDs and `ballast ledger report --run RUN` output. Scenario 4 must run its reviews before `approve final`, because a review after final makes it stale (DEC-0002).
