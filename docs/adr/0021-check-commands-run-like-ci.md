# ADR-0021: `[checks]` commands run like CI, and a check timeout alone stops the fix loop

- Status: proposed (2026-10-13, with the change for [#146](https://github.com/Hugo-Grellier/ballast/issues/146)). The operator chose the check environment, the timeout and the timeout block in the Issue's intake (2026-10-13); merging the PR is the human approval that accepts it.
- Superseded by [ADR-0024](0024-ballast-2-migration.md) (2026-10-15, Ballast 2.0). Kept unchanged as the v1.x record.
- Risk: R2 (the runner's check environment, the headless-agent permission model).
- Amends: the agent git guard's scope (#34) and the fix loop of [ADR-0004](0004-autonomous-provisional-decisions.md) (#21).

## Context

An Autonomous run's `[checks]` commands inherited the workflow's environment, filtered only for secrets. That environment carries the run's markers (`BALLAST_SPEC_WORKFLOW`, `SPECKIT_WORKFLOW_RUN_ID`), so Ballast's own suite failed inside a run and passed from the operator's terminal and in CI: the ledger refused the operator attestations its tests record ("operator attestation is unavailable inside an agent step"). Inside an agent step, which puts the agent git guard first on `PATH` with `BALLAST_GIT`, tests that resolve a trusted `git` also found the guard inside the working tree and stopped with `git-untrusted`; a check launched from such an environment would fail the same way. Run `864d9151` for #142 also showed the suite outrunning `[checks] timeout_minutes`: every review approved, and the fix agent spent the three fix cycles on a timeout it could not change, then the run blocked as `fix-cycle limit (3)`.

## Decision

- **Check environment.** `run_commands`, which runs the `[checks]` commands of `run-checks`, `run-checks --feedback` and `ballast run checks`, and the runner's acceptance checks (ADR-0018), gives each command the operator's environment without secret-named variables (as before), without `BALLAST_GIT`, `BALLAST_SPEC_WORKFLOW` and `SPECKIT_WORKFLOW_RUN_ID`, and without any `spec_workflow/guard` directory on `PATH`. A check runs as CI runs it. The bwrap confinement, the read-only protected inputs and the tamper checks are unchanged.
- **Timeout block.** When the latest feedback checks failed only by timing out, with no high or critical finding, no medium finding left `open` and every verdict approved, the implementation-review recorder blocks at once as a `limit` block, `check-timeout`, instead of opening a fix cycle. Its recovery is to speed up the checks or raise `[checks] timeout_minutes` and run `ballast trust`, then `ballast run resume`. A timeout alongside another failed check or an open finding still opens a fix cycle.
- **This repository.** `[checks] timeout_minutes = 60` in Ballast's own `ballast.toml`.

## Consequences

- A project's suite gets the same result inside a run as in CI; tests need not know about the run's variables or the guard.
- The guard still covers every `git` an agent step runs (#34): check commands are runner-launched, from `ballast.toml` the operator trusted, not agent-chosen.
- `_operator_step_guard` is unchanged: an agent step still cannot record an operator attestation, because the step itself keeps the run's variables.
- A run whose checks only time out stops after one check run instead of three wasted fix cycles; the operator's fix is a `ballast.toml` change, which agents cannot make.

## Rejected alternatives

- Keep the guard and the run variables, and make each affected test independent of them: every project's suite would have to know Ballast's agent environment, and a check would still differ from CI.
- Clear only the run variables: a check started from an environment that carries the guard would still fail a trusted-program lookup, since the guard's directory sits inside the checkout.
- Count a timeout like any failed check: the fix agent cannot change `ballast.toml`, so the cycles are spent for nothing.
