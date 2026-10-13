# Engineering review: 146-checks-pass-in-run (implementation)

- Reviewer: claude-opus-5-5, independent context (agent-provisional)
- Scope: working-tree diff against `d215a63` (`tools/spec_workflow/{autonomy,artifacts,run,agent}.py`, `templates/policies/spec-kit-workflow.md`, ADR-0018 note, new ADR-0021, `tests/parallel.py`), judged against `spec.md`, `plan.md`, `tasks.md`, `decisions.md`, the contracts and the engineering policy.

## What was checked

**Check environment (FR-001 to FR-004).** `autonomy.check_env` starts from `confined_env(env, None)`, so the secret filter is unchanged, then pops `BALLAST_GIT` and both run variables and drops every `PATH` entry whose normalized path is `GUARD` or ends in `spec_workflow/guard`, keeping empty entries and order. It is pure: it never mutates its argument or reads `os.environ`. `run_commands` now passes `check_env(dict(os.environ))` as the child environment while `confined_argv` still receives the operator environment, so the bwrap argv (read-only host, hidden credential paths, read-only checkout for acceptance checks) is unchanged. Every check path (feedback, fix, final, acceptance, Chat and human-gated `checks`) goes through `run_commands`, which satisfies FR-003 by construction. `agent.GUARD = autonomy.GUARD` keeps the same value; `agent._base_env`, `run._environment`, `chat.py`, the guard script and `ledger._operator_step_guard` are untouched (FR-004, FR-005).

**Timeout block (FR-009, FR-010).** `_timeout_only` returns the latest feedback failures only when all of them timed out and `_blocking` and `_open_to_fix` are empty. In `record_decision` the rule runs right after `review_rule` and before the `block`/`limit` branches, `_check_dispositions`, the required-kinds check and any fix-state write, only for `implementation-review` with the fix loop. That ordering matches plan-review F-002: no cycle is consumed on the first record, on a recheck or at the last cycle. `_block` raises, so no later rule runs. The final `run-checks` path is unchanged (AC-018). `check-timeout` is appended to `LIMIT_KINDS` (not `FIXED_LIMITS`), so it is resumable. `LIMIT_LABELS` and `LIMIT_RECOVERY` carry the contract text. `_reentry` maps the block to `checks-implementation` or `checks-fix-N` only when that step exists, and an earlier changed input still wins. `timeout_seconds` is additive.

**Trusted inputs (FR-011, FR-012).** `_timeout_condition` reads the configured timeout only through `autonomy.parse_checks(load_config(...))`, falling back to the default. No agent text feeds it. The changed modules import only the standard library and siblings. `ballast.toml`, `uv.lock`, `pyproject.toml` and `ci.yml` are unchanged.

**Suite speed and parallel runner (FR-007, FR-008, D-001).** The only speed-up narrows a governance test's child process to the one contract test that asserts its purpose; the rest of that class still runs in the suite, and the test now asserts `Ran 1 test`. `tests/parallel.py` is standard-library only, bounded (default 4 jobs, `-j` validated), and exits 1 on any failure. `python -m unittest tests/test_*.py` still runs everything. The suite profile projects the sequential suite at about 2818 s on the operator's machine, above the 2700 s bar of SC-002, so meeting AC-012/SC-002 depends on D-001 (switching the `[checks]` command, a `ballast.toml` edit only the driving agent can make, with `ballast trust`) and on the operator's measurement. That is noted in the findings.

**Edge notes, no action needed.** A wall-time cut produces a resumable `check-timeout` block whose condition says the wall time ran out (plan-review F-001). A resume there will meet the run's wall-time limit at the next step, which is the existing behavior. The suffix rule also drops a non-Ballast `PATH` directory literally named `spec_workflow/guard`. The contract and ADR-0021 accept that, and it only removes entries.

## Verification run by the reviewer

- `uv run --locked python -m unittest tests/test_autonomy.py tests/test_autonomous_recovery.py tests/test_agent_run_ledger.py tests/test_parallel.py`: 352 tests OK (30 skipped, environment-gated).
- `uv run --locked python -m unittest tests/test_autonomous_artifacts.py tests/test_governance.py tests/test_autonomous_run.py`: 271 tests OK (2 skipped, including the bwrap-gated `RealCheckEnvironmentTests`, because bwrap with user namespaces is unavailable in this reviewer sandbox).
- `uv run --locked ruff check` and `uv run --locked ruff format --check`: clean.
- `sha256sum spec.md` equals the `spec_digest` in `acceptance-evidence.json` and the intent's provisional digest.
- Not run here: `tests/test_spec_workflow.py`, `tests/test_chat_mode.py` and the full suite. The full suite is the runner's `run-checks`.

<!-- ballast-findings: begin -->
## Findings (recorded from the review draft)

- F-001 (medium, spec-ambiguity, accepted-provisionally): SC-002/AC-012 (under 45 min) is projected unmet by the sequential suite (about 2818 s). It depends on D-001, which switches the [checks] command to tests/parallel.py. That is a ballast.toml edit only the driving agent can make, with ballast trust, and the operator must measure it. A fix step cannot edit ballast.toml, so a fix cycle would change nothing. The 60-minute timeout and the new check-timeout block keep the run safe if D-001 is declined. The merge reviewer should confirm D-001 and the recorded durations.
- F-002 (low, implementation-bug, open): When the run's wall time cuts a feedback check, the recorder records a resumable check-timeout block, but resuming then meets the fixed wall-time limit at the next step. The condition says the wall time ran out (plan-review F-001), so the operator is not misled. Note only.
- F-003 (info, spec-ambiguity, open): AC-005, AC-014 and SC-001 have no runner-recorded evidence: the bwrap-gated test cannot run nested in acceptance checks, and the run's own v1.0.0 run-checks does not exercise check_env. They rest on the deferred T021, and the PR must not cite this run's run-checks as FR-001 evidence.
<!-- ballast-findings: end -->
