# Plan review: Make the [checks] test command pass inside an Autonomous run

- Review kind: plan (engineering review of the design before tasks)
- Reviewer: claude/claude-opus-5-5, independent context
- Run: Autonomous `a060b968`; this verdict is agent-provisional

## What was reviewed

- `spec.md` (AC-001 to AC-020, FR-001 to FR-015, SC-001 to SC-005), `intent.md` (PD-0005, agent-provisional) and the run record's decisions PD-0001 to PD-0005.
- `plan.md`, `research.md` (R1 to R13), `data-model.md`, `contracts/check-environment.md` and `contracts/timeout-block.md`.
- `AGENTS.md`, `docs/policies/workflow.md` (review matrix), `docs/policies/project/workflow.md` (R2 boundaries), `docs/policies/engineering.md`, and the `ballast-engineering-review` skill.
- `tasks.md` and `decisions.md` do not exist yet; that is expected before the tasks step.

## How the design was checked against the code

- `artifacts.run_commands` (`tools/spec_workflow/artifacts.py`) is the single place that builds a check's environment today (`autonomy.confined_env(dict(os.environ), None)`), and `run_checks`, `_acceptance_checks` and `project_checks` all reach it. Changing that one line to `check_env` covers FR-001 and FR-003 without a second source of truth, as R1 claims.
- `confined_argv` adds only `--setenv` for private directories and no `--clearenv`, so bwrap passes the `subprocess.run` environment through. Filtering the `env` argument therefore does reach the confined command, while the argv (and so the confinement, FR-002) stays built from the operator environment. The contract keeps that split explicitly.
- `confined_env` drops secret-named variables and does not touch `PATH`, so applying it first and then removing guard entries and the three variables is a strict narrowing: nothing is added (contract guarantee).
- The recorder: `review_rule` returns `fixing` while a cycle remains and `limit` at the last one; `record_decision` then blocks or sets the fix state. Inserting the timeout-only rule ahead of both, using `_failed_feedback`, `_blocking` and `_open_to_fix`, matches the contract table and leaves AC-016 and AC-017 on today's paths. The final `run-checks` path is separate and stays a `postcondition` block (AC-018).
- `LIMIT_KINDS`, `LIMIT_LABELS`, `FIXED_LIMITS` and `resumable()` in `autonomy.py`: a new kind outside `FIXED_LIMITS` is resumable without a new block category, and block validation already checks `limit in LIMIT_KINDS`. The other consumer (`run.py`, wrapper limit mapping) falls back safely for unknown kinds.
- `run._reentry` picks the earliest of the blocked step and changed-input steps; `ballast.toml` is a protected input, so without the planned mapping a resume would re-enter at the recorder and re-read the stale feedback. The mapping targets `checks-implementation` and `checks-fix-N`, which exist in `AUTONOMOUS_STEPS`.
- `ballast.toml` pins `v1.0.0`, has `timeout_minutes = 30` and lists `operator-trust` in `[autonomous] authorized_privileged_actions`, so R10's edit outside a step followed by `ballast trust` is within the recorded authorization. `docs/adr/` has two 0019 files, so 0020 is the next free number (R12).

## Assessment

The plan meets every acceptance criterion with a small, centralized change, keeps the agent step environment and `_operator_step_guard` unchanged, and stays standard-library-only. The risk level R2 and the required reviews (engineering, security, test, documentation) follow the review matrix. R11 honestly states that this run's own checks use the pinned v1.0.0 runner and cannot prove AC-014 or SC-001; the PR must carry that as a deferred verification.

The findings in the draft are low or informational: how a timeout bounded by the run's remaining wall time is labelled, where the new rule sits relative to the required-kinds check, and the evidence gap R11 already names. None blocks tasks.

<!-- ballast-findings: begin -->
## Findings (recorded from the review draft)

- F-001 (low, spec-ambiguity, open): When a command's timeout was cut to the run's remaining wall time (R8), the plan still records a resumable check-timeout block whose recovery says to raise timeout_minutes, although wall-time is a fixed limit that raising the timeout cannot address. The condition text names the wall-time case; tasks should either test that wording or record that case as the wall-time limit, so the recovery is not misleading.
- F-002 (info, spec-ambiguity, open): The contract places the timeout-only rule before the limit and fixing handling, which in record_decision is also before the required-kinds check. That matches the existing review-finding block, but tasks should state the exact insertion point and test that a timeout block leaves the fix state and cycle count unchanged on both the first record and --recheck.
- F-003 (info, missing-test, open): AC-014 and SC-001 cannot be proven by this run's pinned v1.0.0 runner (R11). The PR must record them as verified by a run on this checkout's runner or as a deferred operator task after release, and must not cite this run's own run-checks as evidence of FR-001.
<!-- ballast-findings: end -->
