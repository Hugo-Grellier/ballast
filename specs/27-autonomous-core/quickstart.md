# Quickstart: validating Autonomous runs

How to prove the feature end to end. Contracts: [cli](contracts/cli.md), [workflow](contracts/workflow.md), [drafts](contracts/decision-draft.md), [PR summary](contracts/pr-summary.md), [config](contracts/config.md). Records: [data-model.md](data-model.md).

## 1. Fast gate (every change, CI)

```bash
uvx ruff check && uvx ruff format --check
uv run --no-project --python 3.13 --with pyyaml python -m unittest tests/test_*.py
```

Expected: everything passes. The existing `tests/test_spec_workflow.py` cases pass unmodified (SC-007). New unit suites, which use a fake `gh` on `PATH` and a temporary `XDG_STATE_HOME`:

- `tests/test_autonomy.py`: eligibility, policy narrowing, run record, hash-chained logs, blocks, rendering, wording guard, publisher argv.
- New cases in `tests/test_spec_workflow.py`: mode-aware `check_intent`, record tamper detection, wrapper limits and inactive-run refusal, the `ballast-autonomous` step order and absence of gates, and `ballast-continue` with no command steps.

## 2. Full local gate (Linux, systemd user session, Codex CLI, Spec Kit CLI)

The same suite runs on the qualified machine, so the engine-driven cases also run. They are skipped in CI:

- `EngineRunTests` existing cases (human-gated, unchanged).
- New `AutonomousEngineTests`. The fake integration writes drafts and artifacts. The cases are:
  - The run reaches `record-final` without a TTY prompt (AC-001), with one current PD per point (AC-002, SC-002).
  - A postcondition failure stops the run (AC-003).
  - A fake reviewer with a `high` finding blocks at `record-plan-review` (AC-024).
  - An exhausted wall-time limit blocks before the next agent step (AC-012).
  - An agent edit to `ballast.toml` or the run record leaves the effective mode unchanged and fails as tampering (AC-013, AC-016, SC-005).
  - A forged `workflow-approval` block in `intent.md` is refused (spec edge case).
  - Editing `spec.md` after `record-provisional-intent` makes `validate-plan` fail as stale (AC-008).

## 3. Scratch-repository pilot (operator, before merge)

Prerequisites: a scratch GitHub repository you own, with Ballast installed from this branch (`BALLAST_STANDARD_DIR=<this checkout> ballast setup`), then `ballast trust`. You also need an authenticated `gh`, the Claude and Codex CLIs, and a systemd user session.

1. **Eligible R1 run (US1, US2; SC-001, SC-006)**
   - Create Issue *N* with an acceptance-criteria section and the label `ready-for-agent`. Add an intake scope comment containing `Risk: R1` and `Privileged actions before merge: none`.
   - Create a feature branch. Add a `[checks]` table to the scratch repository's `ballast.toml` with a passing command (for example `commands = ["true"]`) and run `ballast trust` again.
   - Run `ballast run start --mode autonomous -i issue=N -i idea="Issue #N: ..." -i feature_directory=specs/N-demo`.
   - Expect no prompt, exit 0, and a Draft PR. Its body lists the mode, the risk, and every PD with links. `specs/N-demo/autonomous/record.md` matches it.
   - The PR is still a draft and is not merged.
2. **Refusals before any agent step (US5)**
   - Start Autonomous for an Issue labelled `epic`, for a scope record with `Privileged actions before merge: deploy`, and for an R2 Issue with `[autonomous] risk = ["R0","R1"]` in the scratch `ballast.toml`.
   - Expect exit 2, a named reason, the human-gated alternative, and no `.specify/workflow-state/<run>/agents/` directory.
   - Add `[autonomous] allow_epics = true` and expect the warning `cannot widen eligibility` (AC-021).
3. **Blocks (US3)**
   - Use an Issue whose acceptance criteria contradict each other: expect a `decision` or `contradiction` block with options, and exit 1.
   - Start with `--wall-time 1`: expect a `limit` block.
   - Run `ballast run resume RUN_ID`: expect a refusal naming #18 (AC-014).
4. **Lowering and changes-requested (US2 AC-009, US4 AC-017)**
   - Run `ballast run continue RUN_ID --reason changes-requested --ref <review URL>`.
   - Expect a new `ballast-continue` run that prompts at `approve-intent` first. `record.md` still lists the earlier PDs, and `human-decisions.jsonl` has the HD entry.
   - Run `ballast run start --mode autonomous ...` for a paused human-gated run's feature: expect no path that raises an existing run.
5. **R2 run (US6)**
   - Use a scratch feature touching a declared security boundary, at risk R2.
   - Expect a security review entry, and the PR's R2 notice listing the boundaries and stating that the pre-change approval was provisional.

Record the run IDs, the PR URLs and any skipped step in this feature's PR (testing policy).
