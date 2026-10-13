# Decisions: 146-checks-pass-in-run

## D-001 (proposal, implementation): switch the `[checks]` test command to the parallel runner

- **Status**: accepted by the operator on 2026-10-13 in the driving session. The driving agent applied it with T020 (`timeout_minutes = 60`) outside any agent step and ran `ballast trust`.
- **Label**: implementation discovery within the plan's conditional path (T024, research R9). It is not a product change.
- **Observation**: T022 found one speed-up that keeps every test and assertion. `TasksTemplateTests.test_implementation_check_is_unchanged` re-ran all of `ArtifactContractTests` in a child process, which the suite already runs on its own; it now runs only the contract test that asserts its purpose (about 34 s down to about 5 s). The other slow tests spend their time on what they assert: concurrent setups (20 races, SC-004 of their feature), killed-and-recovered processes, real child-process lifetimes, pty-driven Chat steps that must stay in progress while other commands are refused, and the real intake tool against a fake `gh`. Cutting those would weaken them. Projected on the operator's machine, the sequential suite stays about 2848 − 30 ≈ 2818 s, above the 2700 s (45 min) bar of SC-002. `test_chat_mode`, the largest module there, could not be measured in the agent sandbox ([suite-profile.md](suite-profile.md)).
- **Done in this branch**: `tests/parallel.py` (standard library only) runs each `tests/test_*.py` module as `python -m unittest <module>` in a bounded pool (default 4 jobs), prints each module's output in order, and exits 1 when any module fails. `tests/test_parallel.py` covers it. `python -m unittest tests/test_*.py` is unchanged and is still what CI runs (AC-013).
- **Proposal**: change the `[checks]` test command in `ballast.toml` to `uv run --locked python tests/parallel.py`, together with `timeout_minutes = 60` (T020), then run `ballast trust`. Keep `.github/workflows/ci.yml` on the sequential command. No module shares host state that the pool would race on (suite-profile, "Shared host state").
- **If declined**: keep the sequential command. The 60-minute timeout alone still lets a 2818 s suite pass (under 3600 s), and the new `check-timeout` block stops a run at once if it does not.

## D-002 (proposal, implementation): a pre-existing 1-in-240 flake in an acceptance-check test

- **Status**: accepted by the operator on 2026-10-13: fix in a separate Issue, out of this feature's scope.
- **Label**: implementation bug (in a test, not caused by this feature).
- **Observation**: during the T023 after-profile, `tests.test_autonomous_artifacts.AcceptanceChecksTests.test_timeout_and_exhausted_wall_time_are_explicit` failed once with `('AC-002', ..., 'passed', 0)` and passed when its class was rerun. The test fakes a timed-out result with `exit: 124`, while `_acceptance_checks` draws the per-run "passed" exit code with `secrets.choice(range(10, 250))`. When the draw is 124, the fake timeout reads as a pass. This is unrelated to this feature's diff, and it can fail any run's `[checks]` command about once in 240.
- **Proposal**: in a separate change, give the fake result an exit code outside `DONE_CODES` (for example 1, with `timed_out: True`), or patch `secrets.choice` in that test. Not done here, so that unrelated test changes stay out of this feature.

## D-003 (proposal, implementation): fix cycle 1's test-command timeout needs T020 and D-001, not a fix step

- **Status**: resolved on 2026-10-13: the driving agent applied T020 and D-001 outside any step and ran `ballast trust` before resuming.
- **Label**: implementation discovery. This is the timeout case this feature's US4 targets, hit by a run on the pinned v1.0.0 runner, which has no `check-timeout` block.
- **Observation**: fix cycle 1 got exactly one failed check. `uv run --locked python -m unittest tests/test_*.py` hit the timeout (`exit 124`, `timed_out: true`), and no review finding was open. Its output stops just past `tests/test_chat_mode.py`, after about 1100 of the roughly 1690 tests, and it shows no test failure. `ballast.toml` still has `timeout_minutes = 30`, because T020 is deferred to the driving agent. The suite needs about 2818 s (47 min) on the operator's machine ([suite-profile.md](suite-profile.md)), so it cannot finish in 1800 s. Cutting about 40% of the suite's time would need shorter waits in the Chat, setup and recovery tests. That would weaken what they assert, and T022 already ruled it out.
- **Why not fixed here**: a fix step cannot edit `ballast.toml` (protected input) or run `ballast trust`. Skipping or narrowing tests to fit 30 minutes would break FR-007 and AC-011. This fix cycle changes no code or test, and the next fix cycles would hit the same timeout.
- **Proposal**: before the next feedback checks, the driving agent applies T020 (`timeout_minutes = 60`), and D-001 if accepted (`uv run --locked python tests/parallel.py`), outside any step. Then it runs `ballast trust` and resumes. If neither is applied, the run will end at `fix-cycle limit (3)` with nothing changed, as #142 did.

## Wording clarification (no proposal needed)

- T030 said to map AC-005 to the bwrap-gated T008 test. The runner's acceptance checks run each mapped test inside bwrap, where a nested bwrap is not available, so that test would be skipped and recorded as `failed`. `acceptance-evidence.json` maps AC-005 to `[]` (missing) instead, and AC-005 is verified by T008 on a host with user namespaces (`tests.test_autonomous_artifacts.RealCheckEnvironmentTests`) and by the deferred T021.

- T018 (g) said "a timeout plus a high finding or a non-approved verdict: the existing `review-finding` block". In a run with the fix loop, a high finding or a non-approved verdict starts a fix cycle while one remains, and blocks as `fix-cycle limit (3)` after the last cycle. The `review-finding` block applies only to a run without the fix loop. The test asserts those existing rules (AC-017: "the existing fix-loop and blocking rules apply unchanged").
