# Engineering review: 146-checks-pass-in-run (implementation, after the resume)

- Reviewer: claude/claude-opus-5-5, independent context (agent-provisional)
- Scope: the whole change against the rebased base `617df9c`: commits fa1eefe and bd80a3e plus the working tree (T031 to T033). Files: `tools/spec_workflow/{autonomy,artifacts,run,agent}.py`, `ballast.toml`, `templates/policies/spec-kit-workflow.md`, ADR-0018's back-link, ADR-0021, `tests/parallel.py` and the test changes. Judged against `spec.md`, `intent.md`, `plan.md`, `tasks.md`, `decisions.md` (D-001 to D-003), both contracts, the engineering policy and the run record (HD-0001, PD-0014 to PD-0016).

## Why this review ran again

After HD-0001 (rebase on `617df9c`, ADR renumbered 0021, T020 and D-001 applied outside any step, then `ballast trust`), the plan and tasks were reviewed again. The implementing step then did T031 to T033. This review covers the whole change again, not only those tasks.

## What was checked

**Check environment (FR-001 to FR-005).** `autonomy.check_env` applies `confined_env(env, None)` (secret filter unchanged), then removes `BALLAST_GIT` and both `RUN_VARIABLES`, and drops `PATH` entries equal to `GUARD` or ending in `spec_workflow/guard`. It keeps order and empty entries and adds nothing. `run_commands` is the only place that builds a check's environment. It passes `check_env(dict(os.environ))` as the child environment, while `confined_argv` still builds the bwrap argv (`--unshare-pid`, `--die-with-parent`, hidden credential paths, read-only checkout for acceptance checks) from the operator environment. Every check path reaches `run_commands`. `agent.GUARD` now aliases `autonomy.GUARD` with the same value. Agent steps, `run._environment` and `ledger._operator_step_guard` are unchanged: `ledger.py` and `.github/` are not in the diff.

**Timeout block (FR-009, FR-010, AC-015 to AC-018).** `_timeout_only` fires only when the latest feedback run has failures, all of them `timed_out`, and `_blocking` and `_open_to_fix` are empty. In `record_decision` it runs after `review_rule` and `evidence`, and before the `block`/`limit` branches, `_check_dispositions`, the required-kinds check and any fix-state write. It runs only for `implementation-review` with the fix loop. `_block` raises `BlockedError`, so no cycle is consumed. `check-timeout` is in `LIMIT_KINDS` and not in `FIXED_LIMITS`, so it is resumable. Its label and recovery match the contract. `_reentry` maps the block to `checks-implementation` or `checks-fix-N` only when that step exists, and otherwise falls back to the usual block step. `_timeout_condition` reads the timeout only from the trusted `ballast.toml`, uses the default when the file is unreadable, separates the wall-time cut from the configured timeout, and bounds the condition length. `timeout_seconds` is an additive result field.

**Changes after the resume.**
- `ballast.toml` (bd80a3e): `[checks]` now runs `uv run --locked python tests/parallel.py` with `timeout_minutes = 60`. This is T020 and D-001, done outside any step through `operator-trust`, as tasks require. `ci.yml`, `AGENTS.md` and `CLAUDE.md` keep the sequential command, so AC-013 holds. The run record's fix loop shows the next feedback run, with the parallel runner, exited 0.
- ADR-0021: the `Extends:` line now says ADR-0010 is amended by ADR-0020. A new Consequences bullet says `check-timeout` becomes a Draft-PR limit outcome once #153 ships, and that the resumable block applies until then. This matches ADR-0020's Limit outcome and Delivery paragraphs. The Decision section is unchanged. The plan-review finding PD-0014 F-001 is settled.
- `tests/test_governance.py`: `test_adr_0021_records_the_boundary` also asserts `0020-autonomous-stop-rule.md` and `#153`. The method name and every earlier assertion are kept, so the AC-020 mapping is still valid.
- `spec.md` is unchanged since bd80a3e, and its sha256 still equals the `spec_digest` in `acceptance-evidence.json` (T033).

**`tests/parallel.py`.** Standard library only. It runs a bounded thread pool of `python -m unittest <module>` child processes from the checkout root (default 4 jobs, `-j` must be at least 1) and exits 1 on any failed module. `pool.map` prints results in module order. As a result, a module's output appears only after it and every earlier module have finished. When the `[checks]` timeout kills the run, the kept `output_tail` lists the modules that finished, not the module that hung. That limits the diagnosis the new `check-timeout` block is meant to give. It is noted as a low finding. The command keeps the whole suite: it globs every `tests/test_*.py`.

## Verification

This reviewer session could not run `ruff` or `unittest`: commands that need approval were refused, and no approval is possible in this session. The execution evidence is therefore the trusted runner's feedback checks in the run record (Fix loop: `ruff check`, `ruff format --check` and `python tests/parallel.py` all exited 0). The targeted module runs of the first implementation reviews (PD-0009, PD-0013) predate T031 to T033. The code was read directly. `git diff 617df9c -- tools/spec_workflow/ledger.py .github` is empty. `sha256sum spec.md` matches the evidence digest.

## Assessment

The implementation still matches the spec and plan. The post-resume changes are small, stay inside the tasks' scope, and settle the second plan review. The open notes concern deferred operator evidence (SC-002 timing, AC-005, AC-014, SC-001) and diagnostics. None is a correctness defect that a fix step could or should address now.

<!-- ballast-findings: begin -->
## Findings (recorded from the review draft)

- F-001 (low, missing-test, open): SC-002/AC-012 (suite under 45 min) now rests on D-001, applied in bd80a3e; the record shows the feedback checks passed with tests/parallel.py under the 60-minute timeout but not their duration. The PR must state the measured run-checks seconds. A fix step cannot produce that number.
- F-002 (low, implementation-bug, open): When the run's wall time cuts a feedback check, the recorder records a resumable check-timeout block, but resuming meets the fixed wall-time limit at the next step. The condition says the wall time ran out, so the operator is not misled. Note only.
- F-003 (low, implementation-bug, open): tests/parallel.py prints each module's output through pool.map in module order, so output appears only once a module and every earlier one finish. When the [checks] timeout kills the run, the kept output_tail names finished modules, not the one that hung, which weakens the diagnosis the check-timeout block aims to give. Printing as each module completes (as_completed) or a start line would fix it.
- F-004 (info, spec-ambiguity, open): AC-005, AC-014 and SC-001 have no runner-recorded evidence: the bwrap-gated test cannot run nested in acceptance checks, and the run's v1.0.0 run-checks does not exercise check_env. They rest on the deferred T021; the PR must not cite this run's run-checks as FR-001 evidence.
<!-- ballast-findings: end -->
