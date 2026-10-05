# Review: end-to-end fixes 54171bc and 3716a3f

- Scope: `git diff 314f781..3716a3f -- tools tests` (`tools/spec_workflow/run.py`, `tests/test_spec_workflow.py`), against `reviews/e2e.md` § "Findings fixed on the way" and #18's SEC-002.
- Verification: `uv run --no-project --isolated --python 3.13 --with pyyaml python -m unittest tests.test_spec_workflow` (134 tests, OK, before and after the resolution); `uvx ruff check && uvx ruff format --check` clean. Each fix was reverted in a scratch copy to check that its test fails.

## Findings

1. **Medium, spec violation (SEC-002): resume points `.specify/feature.json` at the feature from `inputs.json`.** `_run_feature` reads `.specify/workflows/runs/<id>/inputs.json` first, and #18's contract (`specs/18-branch-sync/contracts/branch-sync.md`, `data-model.md`) treats that file as agent-writable run state: `resume` takes the feature from the pin, never from it. The branch check already does; the new pointer write did not, so a tampered `inputs.json` could make the operator point discovery at another feature's directory than the one the check validated. No authority widens (the pointer is agent-writable during steps anyway, no operator decision reads it, and the engine resumes with its own stored inputs), but the operator's own write contradicted the contract. Fix: resume points it at `branch_sync.read_pin(ROOT, run_id)["feature"]`, present whenever the check did not block (an unpinned run blocks as `wrong-branch`).
2. **Low, missing test: the resume path of `_point_feature` was untested.** Removing it for `resume` left the suite green. Covered by the resolution's test.
3. **Low, architecture note: an Autonomous start still writes the snapshot and `feature.json` before its branch check.** In a checkout that does not ignore `.specify/`, a start that must rebase would block as `dirty` on them. Installed projects ignore `.specify/*`, and the Autonomous preflight already requires a clean tree before these writes, so this only shows in scratch checkouts like the end-to-end fixture. Left as is; move the writes after `_sync` if such a checkout ever matters.

Checked without findings:

- `.specify/feature.json` is in `launcher.SKIPPED`, so the operator write does not trip the trust check; it is also in `SPECIFY_WRITABLE`.
- Both writes come after the blocked return: a blocked check writes neither the snapshot nor the pointer, and no engine or checkpoint runs. `_point_feature` validates the pattern and writes through `replace_file` (no symlinks); its refusal also precedes the engine.
- Resume never wrote a snapshot, before or after this delta; discovery reads the one the start wrote under `.specify/workflow-state/issues/`.
- Test quality: without 54171bc, `test_start_points_feature_json_at_the_run_before_the_engine` fails; with the snapshot moved back before the check, `BranchSyncEndToEndTests.test_start_synchronizes_before_the_first_step` fails.

- Verdict: changes requested

## Resolution

Finding 1 fixed test-first: `BranchSyncCallTests.test_resume_points_feature_json_at_the_pinned_feature` pins `FEATURE`, writes `specs/4-y` into `inputs.json`, and failed before the change; `run.py` now passes the pinned feature to `_point_feature` on resume. The same test closes finding 2. Finding 3 is accepted as is. Suite and lint pass as above.

- Verdict: approved
