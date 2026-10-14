# Security review: 146-checks-pass-in-run (specialists, after the run-checks block)

- Reviewer: claude-opus-5-5, independent context (agent-provisional)
- Scope: the whole change against the branch base `0bddeb8` (commits 752f88b, b72b578 and 4491448, plus the working tree). Since 4491448, the working tree changes only `autonomous/record.md` and the engineering and test reports. The review focused on the declared R2 boundary: the headless-agent permission model and what Ballast executes. Here that means the `[checks]` environment, the `[checks]` command and the new `check-timeout` block. Read `spec.md`, `plan.md`, `tasks.md`, `decisions.md`, ADR-0018, ADR-0020, ADR-0021, `docs/policies/security.md`, `docs/policies/workflow.md`, `docs/policies/project/workflow.md`, the changed code in `tools/spec_workflow/{autonomy,artifacts,run,agent}.py`, `tests/parallel.py` and `ballast.toml`, and the run record's Block resolutions.

## Why this review ran again

The final `run-checks` failed with exit 1 after 1064.2 s and blocked as `postcondition`. The operator resolved that block as HD-0002 on 2026-10-14. They called it a flake and re-recorded trust, and the run resumed at `validate-implementation`. The record lists only `outside` as changed during the block. `git diff 4491448` shows no code, test, policy, ADR or `ballast.toml` change. So the security surface is the same one the earlier specialist review (PD-0020) approved, and this review checks it again in full.

## Authority of a check

- **Confinement unchanged.** `run_commands` still builds the bwrap argv from the operator environment. Only the child environment changed, to `autonomy.check_env(dict(os.environ))`. `check_env` first applies `confined_env(env, None)`, so the secret-named filter runs before anything else. It then removes `BALLAST_GIT`, both `RUN_VARIABLES` and every `PATH` entry that is this install's guard or ends in `spec_workflow/guard`. It adds nothing. Acceptance checks keep the read-only checkout.
- **Git guard.** The guard limits the `git` options an agent can type, because an agent's allowlist matches command text. It is not a sandbox. A check runs trusted commands from the protected `ballast.toml` inside the same bwrap, with a read-only host and hidden credential paths. Test code could already start any binary, so the host `git` reaches nothing new.
- **Run variables.** They make `ledger._operator_step_guard` refuse an attestation inside a step. The run state, decision log and ledger runner events live in operator state, which a check cannot write. A check without the variables therefore still cannot attest. `git diff 0bddeb8 -- tools/spec_workflow/ledger.py tools/spec_workflow/chat.py tools/spec_workflow/guard .github` is empty.
- **Agent steps unchanged.** `agent.GUARD` now aliases `autonomy.GUARD`, which is the same directory. The agent step environment and `run._environment` are not in the diff.
- **Trusted timeout and block text.** `_timeout_condition` reads minutes only from `parse_checks(load_config(root))`, and falls back to the constant default. The command strings it quotes come from runner-recorded results whose commands come from `ballast.toml`, and the text is length-bounded. No draft or fix input reaches it. `check-timeout` is resumable but not in `FIXED_LIMITS`. That fits its recovery: the operator changes a trusted input and runs `ballast trust`, and a changed `ballast.toml` still fails closed until then. `_reentry` overrides the step only for a `limit` block of kind `check-timeout`, and an earlier changed input still wins.

## The `[checks]` command

- `ballast.toml` runs `uv run --locked python tests/parallel.py` with `timeout_minutes = 60`, inside the 1–240 bound. The driving agent applied both outside any step (D-001 and T020, which the operator chose on 2026-10-13 per `decisions.md`). Trust was re-recorded through the `operator-trust` action that `ballast.toml` authorizes.
- `tests/parallel.py` comes from the agent-writable checkout. The previous command imported checkout test modules too, so the trust model is unchanged. It uses only the standard library and starts only `sys.executable -m unittest <module>` without a shell. Only its exit code and a bounded output tail are trusted. Before the final `run-checks`, the frozen tree check holds it to reviewed content. On a timeout, bwrap's `--unshare-pid` and `--die-with-parent` end its workers.

## The HD-0002 failure

The in-run failure of the parallel command is a reliability question, not an authority one. A failed check blocks the run, and that is fail-closed. Nothing about the failure gave a check or a step more authority. Its cause is not recorded in the repository: the output tail is in operator state, which this session cannot read. The engineering and test reports carry that diagnostic gap.

## Residual observations

- `check_env` keeps empty and relative `PATH` entries, as the contract requires. Without the guard first, a check's `git` could resolve inside the writable checkout if the operator's `PATH` holds such an entry. That is not an escalation: the check already runs agent-authored code in the same sandbox, and nothing outside trusts that `git`.
- The bwrap-gated `RealCheckEnvironmentTests` (AC-005) and the run-level AC-014 and SC-001 stay with the deferred operator task T021. This run's pinned v1.0.0 runner does not exercise `check_env`, so its `run-checks` is not evidence of FR-001.

## Verification

- Read the code paths above and `autonomy.confined_argv`. Confirmed with `git diff 4491448 --stat` that only the record and two reports changed since the last approved specialist review. Confirmed that the ledger, Chat, guard and `.github` diffs against `0bddeb8` are empty.
- Ran no test. The trusted runner records the `[checks]` result.

<!-- ballast-findings: begin -->
## Findings (recorded from the review draft)

- F-001 (info, architecture-issue, open): check_env keeps empty or relative PATH entries, so without the guard first, git in a check could resolve to a file in the writable checkout if the operator PATH holds such an entry. No escalation: the check already runs agent-authored code in the same sandbox, and nothing outside trusts it.
- F-002 (info, architecture-issue, open): The [checks] command runs tests/parallel.py from the agent-writable checkout. The trust model is unchanged (unittest already imported checkout tests), it runs confined, only its exit code and a bounded tail are used, and the frozen tree check holds it to reviewed content. Recorded so the merge reviewer sees the ballast.toml change.
- F-003 (info, missing-test, open): The bwrap-gated RealCheckEnvironmentTests (AC-005) and the run-level AC-014 and SC-001 stay with the deferred operator task T021; this run's pinned v1.0.0 run-checks does not exercise check_env and is not evidence of FR-001.
<!-- ballast-findings: end -->
