# ADR-0021: Check commands run in an environment like CI

- Status: proposed (2026-10-13, with the change for [#146](https://github.com/Hugo-Grellier/ballast/issues/146), [spec](../../specs/146-checks-pass-in-run/spec.md)). Drafted agent-provisionally in Autonomous run `a060b968`; merging the PR is the only human approval that accepts this ADR.
- Risk: R2 (the headless-agent permission model, what Ballast executes).
- Extends: [ADR-0018](0018-runner-recorded-acceptance-checks.md), whose acceptance checks run through the same confinement as the check commands, and [ADR-0010](0010-autonomous-resume-and-bounded-recovery.md), with a resumable limit.

## Context

Autonomous run `864d9151` for #142 ended at `fix-cycle limit (3)` with every review approved and no finding open. Its `[checks]` test command could not pass inside the run, although the same suite passes in CI:

- The runner built a check's environment from its own, which an agent session or a run step had set up. The run variables `BALLAST_SPEC_WORKFLOW` and `SPECKIT_WORKFLOW_RUN_ID` reached the tests, so the ledger's operator-attestation guard refused inside ledger tests.
- The agent git guard (`spec_workflow/guard`) came first on `PATH`, with `BALLAST_GIT`, so packet and governance tests that run `git` stopped with `git-untrusted`.
- The suite ran longer than the 30-minute `[checks]` timeout, and a fix step cannot change `ballast.toml`, so three fix cycles changed nothing.

## Decision

- **Check environment.** Every `[checks]` command and every runner acceptance check runs in the environment `autonomy.check_env` builds: the existing secret filter (`confined_env`), then without `BALLAST_GIT`, `BALLAST_SPEC_WORKFLOW` and `SPECKIT_WORKFLOW_RUN_ID`, and with every agent git guard entry removed from `PATH`. An entry is a guard entry when it is this install's guard directory or its last two components are `spec_workflow/guard`, so a guard from another checkout is removed too. The other entries keep their order; no variable is added. `artifacts.run_commands` is the one call site, so the rule covers Autonomous feedback, fix and final checks, runner acceptance checks, Chat runs and human-gated `ballast run checks`.
- **Confinement unchanged.** The bwrap argv does not change: the host stays read-only, credential paths stay hidden, secret-named variables stay dropped, the checkout stays writable minus protected inputs for check commands and read-only for acceptance checks. The protected-input and tree checks around the commands are unchanged.
- **Agent steps unchanged.** Agent steps keep the guard first on `PATH`, `BALLAST_GIT` and both run variables. `agent.GUARD` refers to `autonomy.GUARD`, so the agent step and the check filter read one value. The guard itself, `ledger._operator_step_guard`, `run._environment` and `chat.py` do not change.
- **Unaddressable timeout.** When every failed feedback check of the latest `run-checks --feedback` timed out and no review finding is blocking or open to fix, the implementation-review recorder blocks at once with the resumable limit `check-timeout`, before it sets a fix state, so no fix cycle is consumed. The condition names each command and the timeout applied to it; a command cut short by the run's remaining wall time says so. The recovery is to raise `[checks] timeout_minutes` in `ballast.toml` or speed up the named commands, run `ballast trust`, then resume, or continue human-gated. Resume re-enters at the feedback checks step (`checks-implementation` or `checks-fix-N`), which re-reads `[checks]` from the trusted `ballast.toml`. Every other case keeps the fix loop, and a timed-out final `run-checks` keeps its `postcondition` block.
- **Recorded timeout.** Each check result gains the additive `timeout_seconds`, the timeout applied to that command.

## Why this grants a check no authority

A check loses variables and `PATH` entries and gains nothing. The run variables grant nothing: the run state, the decision log and the ledger's runner events are written by the runner in operator state, which a check cannot write, so an attestation from a check has nowhere to land. The git guard limits an agent's `git` options because an agent's allowlist matches command text; a check runs trusted commands from the protected `ballast.toml`, under the same bwrap that bounds a guarded agent, so the host git reaches nothing the guarded git could not.

## Consequences

- A project's suite behaves inside a run as it does in CI: tests that run `git` or set the run variables themselves no longer depend on the caller.
- A check that times out with nothing for a fix step to fix stops the run after 0 fix cycles instead of 3, and the operator sees which command and which timeout to change.
- A project whose checks relied on the guard or on the run variables (none is known) sees them gone.
- A run that pins an earlier Ballast keeps the earlier check environment until it pins a release with this change.

## Rejected alternatives

- Keeping the guard and changing each git-using test: every project would have to code around the runner, and a missed test fails only inside a run.
- Filtering in each caller of `run_commands`: three copies of one rule, and a missed caller reopens the bug.
- Clearing the variables in the workflow YAML: misses Chat and human-gated checks and the acceptance checks.
- Relaxing `_operator_step_guard`: it is the guard against attestations from an agent step; the ledger tests clear the variables per test instead.
- A new block category for the timeout: the existing limit vocabulary, validation and resume command already fit an exhausted bound.
- Blocking on any timed-out check: a timeout alongside a real failure or an open finding can still be fixed by a fix step.
