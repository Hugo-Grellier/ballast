# Security review: 146-checks-pass-in-run (specialists)

- Reviewer: claude-opus-5-5, independent context (agent-provisional)
- Scope: working-tree diff against `d215a63`, focused on the R2 boundary the run declares (headless-agent permission model: the runner's `[checks]` environment). Read `spec.md`, `plan.md`, `decisions.md`, `contracts/check-environment.md`, `contracts/timeout-block.md`, ADR-0021, the security policy, and the changed code in `tools/spec_workflow/{autonomy,artifacts,run,agent}.py`, plus the guard script `tools/spec_workflow/guard/git` and `autonomy._git_binds`.

## Authority of a check

The question for this change is whether a check process gains anything an agent step lacks, or anything the runner trusts.

- **Confinement unchanged.** `run_commands` still builds the bwrap argv with `confined_argv(..., env=dict(os.environ))`, so credential paths it hides are found from the operator environment as before. Only the child environment passed to `subprocess.run` changes, to `autonomy.check_env(dict(os.environ))`. `check_env` starts from `confined_env(env, None)`, so the secret-named filter runs first. It then only removes `BALLAST_GIT`, `BALLAST_SPEC_WORKFLOW`, `SPECKIT_WORKFLOW_RUN_ID` and guard `PATH` entries, and adds nothing. The acceptance checks keep `writable_checkout=False`.
- **The git guard.** `guard/git` refuses `--output`, `difftool` and `mergetool` and then runs `BALLAST_GIT`. It exists because Claude's allowlist matches command text, so it constrains what an agent may type. It is not a sandbox. A check runs the commands from the protected `ballast.toml`, inside the same bwrap where the host is read-only and `.git`, the worktree admin directory and submodule admin directories are bound read-only (`_git_binds`). Whatever the host git can write there, the test code a check already runs (agent-authored Python that can `subprocess` any binary) could already write. Removing the guard from a check's `PATH` therefore widens nothing.
- **Run variables.** `BALLAST_SPEC_WORKFLOW` and `SPECKIT_WORKFLOW_RUN_ID` mark a workflow step so that `ledger._operator_step_guard` refuses an operator attestation. Removing them from a check could matter only if a check could write the run ledger or operator state. Those live in operator state outside the sandbox's writable binds, and the runner records check results itself. An attestation from a check has nowhere to land. `_operator_step_guard` is unchanged (`git diff` shows no change to `ledger.py`), and a new test asserts it refuses with either variable set alone (AC-008).
- **Agent steps unchanged.** `agent.GUARD` now aliases `autonomy.GUARD`, which resolves to the same `tools/spec_workflow/guard` directory. `agent._base_env`, `run._environment`, `chat.py` and the guard script are not in the diff.
- **Trusted timeout.** The timeout comes from `parse_checks(load_config(root))` in `run_checks` and in `_timeout_condition`, both reading the protected `ballast.toml` that the launcher verifies against the trust baseline. No agent draft or fix input feeds it. The resume path for `check-timeout` re-enters at a checks step that re-reads it, and a changed `ballast.toml` still fails closed until `ballast trust`.
- **Block text.** `_timeout_condition` includes each `command` with `!r` from runner-recorded results whose commands come from `ballast.toml`, and it caps the length below the block limit. No agent text reaches the condition.

## Residual observations

- `check_env` keeps empty and relative `PATH` entries, as the contract requires. Before this change the guard came first, so `git` in a check resolved to the guard. Now, if the operator's `PATH` has an empty or relative entry before the host git, a check's `git` could resolve to a file in the writable checkout. This is no escalation, because the check already runs agent-authored code in the same sandbox and nothing outside trusts what that `git` does. It is recorded as info only.
- The parallel runner `tests/parallel.py` is not part of any trusted path. D-001 proposes it as the `[checks]` command, which would become trusted only through an edit to `ballast.toml` made outside a step, followed by `ballast trust` (privileged action `operator-trust`, already authorized for this repository).

## Verification

- Read the code paths listed above and the tests `tests/test_autonomy.py` (`check_env` cases, the guard refusal with each run variable) and `tests/test_autonomous_artifacts.py` (`run_commands` env and unchanged argv for check and acceptance paths; the bwrap-gated `RealCheckEnvironmentTests`).
- I did not run the bwrap-gated test. The implementation reviewers recorded it as skipped where user namespaces are unavailable. AC-005, AC-014 and SC-001 remain deferred to an operator run (T021).

<!-- ballast-findings: begin -->
## Findings (recorded from the review draft)

- F-001 (info, architecture-issue, open): check_env keeps empty or relative PATH entries, so without the guard first, git in a check could resolve to a file in the writable checkout if the operator PATH holds such an entry. This is no escalation: the check already runs agent-authored code in the same sandbox, and nothing outside trusts it.
- F-002 (info, missing-test, open): The bwrap-gated RealCheckEnvironmentTests (AC-005) and the run-level AC-014/SC-001 were not exercised in reviewer sandboxes; they stay with the deferred operator task T021 and must not be cited from this run's v1.0.0 run-checks.
<!-- ballast-findings: end -->
