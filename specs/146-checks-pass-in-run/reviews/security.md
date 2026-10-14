# Security review: 146-checks-pass-in-run (specialists)

- Reviewer: claude-opus-5-5, independent context (agent-provisional)
- Scope: the whole change since the branch start `617df9c` (commits `fa1eefe` and `bd80a3e`, plus the uncommitted T031–T033 edits to ADR-0021, `tests/test_governance.py` and `tasks.md`). Focus: the R2 boundary the run declares, the headless-agent permission model and what Ballast executes, here the `[checks]` environment and the `[checks]` command itself. Read `spec.md`, `plan.md`, `tasks.md`, `decisions.md`, both contracts, ADR-0020, ADR-0021, `docs/policies/security.md`, `docs/policies/workflow.md` and `docs/policies/project/workflow.md`, and the changed code in `tools/spec_workflow/{autonomy,artifacts,run,agent}.py`, `tests/parallel.py` and `ballast.toml`.

## Authority of a check

- **Confinement unchanged.** `run_commands` still builds the bwrap argv from the operator environment; only the child environment changes, to `autonomy.check_env(dict(os.environ))`. `check_env` starts from `confined_env(env, None)`, so the secret-named filter runs first. It then only removes `BALLAST_GIT`, both run variables and guard `PATH` entries, and adds nothing. Acceptance checks keep the read-only checkout.
- **Git guard.** The guard constrains which `git` options an agent may type, because an agent's allowlist matches command text. It is not a sandbox. A check runs the trusted commands from the protected `ballast.toml`, inside the same bwrap with a read-only host and read-only Git admin directories. The test code a check already runs can start any binary, so a host `git` on `PATH` reaches nothing new.
- **Run variables.** They mark a workflow step so that `ledger._operator_step_guard` refuses an operator attestation. The ledger and run state sit in operator state outside the sandbox's writable binds, and the runner records check results itself, so a check without the variables still cannot attest. `ledger.py` is not in the diff, and the new ledger tests cover the guard with each variable alone.
- **Agent steps unchanged.** `agent.GUARD` now aliases `autonomy.GUARD`, the same directory. `agent._base_env`, `run._environment`, `chat.py` and the guard script are not in the diff.
- **Trusted timeout.** `run_checks` and `_timeout_condition` read the timeout from `parse_checks(load_config(root))`, that is from the protected `ballast.toml`. No draft or fix input feeds it. The `check-timeout` resume re-enters at a checks step that reads it again, and a changed `ballast.toml` still fails closed until `ballast trust`. `check-timeout` is resumable but not in `FIXED_LIMITS`, which matches its recovery: the operator changes a trusted input, not a run limit.
- **Block text.** `_timeout_condition` includes each `command` with `!r` from runner-recorded results whose commands come from `ballast.toml`, and it caps the length below the block limit. No agent text reaches the condition.

## The `[checks]` command change (commit `bd80a3e`)

- The driving agent changed `ballast.toml` outside any step (D-001 and T020, which the operator chose on 2026-10-13 per `decisions.md`) and then ran `ballast trust`, the privileged action `operator-trust` that `ballast.toml` authorizes for this repository. No agent step edited a protected input.
- The new command `uv run --locked python tests/parallel.py` runs a file from the agent-writable checkout. The previous command did too, since `unittest` imports every test module from the checkout, so the trust model is unchanged. The command still runs confined, and the runner uses only its exit code and a bounded output tail. Before the final `run-checks`, code outside the feature directory must still equal the tree frozen at implementation review, so the runner executed reviewed content.
- `tests/parallel.py` is standard-library only and starts only `sys.executable -m unittest <module>`, with no shell. It exits 1 when any module fails, including one that finds no tests, so it fails closed. On a timeout, the runner kills bwrap, which runs with `--unshare-pid` and `--die-with-parent`, so no worker process outlives the check.
- The timeout went from 30 to 60 minutes, inside the 1–240 bounds, and the run's remaining wall time still bounds each command.

## Residual observations

- `check_env` keeps empty and relative `PATH` entries, as the contract requires. Without the guard first, a check's `git` could resolve to a file in the writable checkout if the operator's `PATH` holds such an entry before the host git. That is no escalation, because the check already runs agent-authored code in the same sandbox and nothing outside trusts what that `git` does.
- The bwrap-gated `RealCheckEnvironmentTests` (AC-005) and the run-level AC-014 and SC-001 were not exercised here. They stay with the deferred operator task T021. This run's own `run-checks`, on the pinned v1.0.0 runner, is not evidence of FR-001.

## Verification

- Read the code paths above, `tests/test_autonomy.py` (`check_env` cases, the guard refusal with each run variable), `tests/test_autonomous_artifacts.py` (`run_commands` environment and unchanged argv for both paths), `tests/test_parallel.py`, and `autonomy.confined_argv` for the bwrap flags.
- Reviewed the uncommitted diff: ADR-0021 now cites ADR-0020, and the governance test asserts it. Neither changes a security boundary.
- I ran no test. The `[checks]` result is the runner's to record.

<!-- ballast-findings: begin -->
## Findings (recorded from the review draft)

- F-001 (info, architecture-issue, open): check_env keeps empty or relative PATH entries, so without the guard first, git in a check could resolve to a file in the writable checkout if the operator PATH holds such an entry. No escalation: the check already runs agent-authored code in the same sandbox, and nothing outside trusts it.
- F-002 (info, architecture-issue, open): The [checks] command now runs tests/parallel.py from the agent-writable checkout. The trust model is unchanged (unittest already imported checkout tests), it runs confined, only its exit code is trusted, and bwrap --unshare-pid --die-with-parent ends its workers on a timeout. Recorded so the merge reviewer sees the ballast.toml change.
- F-003 (info, missing-test, open): The bwrap-gated RealCheckEnvironmentTests (AC-005) and the run-level AC-014 and SC-001 were not exercised in this review; they stay with the deferred operator task T021, and this run's v1.0.0 run-checks is not evidence of FR-001.
<!-- ballast-findings: end -->
