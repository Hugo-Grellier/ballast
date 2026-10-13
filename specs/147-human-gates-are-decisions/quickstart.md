# Quickstart: validating #147

How to prove the feature end to end. Behavior is defined in [contracts/trust-refresh.md](contracts/trust-refresh.md) and [contracts/cli.md](contracts/cli.md), and record shapes in [data-model.md](data-model.md).

## Prerequisites

- `uv sync --locked` before any `ballast trust`.
- The fast gate: `uv run --locked ruff check && uv run --locked ruff format --check` and `uv run --locked python -m unittest tests/test_*.py`.
- The full gate on Linux with a systemd user session, `bwrap`, the Claude Code or Codex CLI, and the Spec Kit CLI. The headless Chat step and usage-limit tests that need real confinement are skipped elsewhere, and the PR records which were skipped.
- For the end-to-end run, the disposable scratch repository (`[autonomous] authorized_privileged_actions` includes `scratch-repository`) with branch protection on its default branch, and a CLI from this branch (`ballast self-install` from the working copy, or `BALLAST_STANDARD_DIR` set to it).

## Acceptance criteria → evidence

| AC | Evidence (test module → focus) |
| --- | --- |
| AC-001 | `tests/test_setup_trust.py` refresh: a stand-in bare repository whose default branch carries a new `ballast.toml` (changed `extra_allow`). `setup --refresh` regenerates and records `default-branch` with the commit, and the launcher passes. `tests/test_ballast.py`: the trigger runs refresh only for `inputs-changed` or `pin-mismatch` with the declaration. `tests/test_spec_workflow.py`: the run output line. |
| AC-002 | `test_setup_trust.py`: an uncommitted edit, a branch-only commit, and a `.venv` change each give `not refreshed` with byte-identical state, and the launcher still names `ballast trust`. |
| AC-003 | `test_spec_workflow.py`: `trust` with stale `claude-settings.json` refuses, writes no baseline, and leaves the reviewed record unchanged. A malformed `[agents.permissions]` also refuses. |
| AC-004 | `test_setup_trust.py`: a regeneration whose settings differ (patched producer) records nothing and restores the previous baseline. |
| AC-005 | `test_setup_trust.py`: repointed to an unreviewed repository and to another reviewed repository, and legacy provenance without a repository. No refresh in any case. |
| AC-006 | `test_setup_trust.py`: offline, a timeout, an `insteadOf` rewrite, a tamper marker and the in-progress marker. No network command runs when a local condition fails (argv log). |
| AC-007, AC-009 | `tests/test_governance.py`: the policy table and ADR-0020 list the matrix of `actor.py` (names compared), including the decision-free block categories, and the ADR carries its supersedes and amends lines and the pseudo-terminal residual risk. Review step: documentation review. |
| AC-008 | The end-to-end run below, counting operator actions. |
| AC-010 | `tests/test_chat_mode.py`: a relayed approve in Chat writes an HD with `by: relayed`, `relayed_by` and ref `relayed approve GATE`. Status, `record.md` and the PR section show "relayed by agent session" and never "by operator". |
| AC-011, AC-012 | `test_chat_mode.py` and `tests/test_autonomous_run.py`: a relayed approve in a human-gated run (including a Chat run switched to human-gated) and in an Autonomous run is refused, and the HD file is unchanged. A terminal-less human-gated `start --relayed-by` (and a relayed human-gated `resume`) with `approve` piped on stdin pauses at the Spec Kit engine gate and records no approval (plan-review F-001); it is skipped only where the human-gated fixtures already skip without the Spec Kit CLI. |
| AC-013 | `test_autonomous_run.py`: a relayed `start --mode autonomous` writes `mode_history[0]` with `by: relayed`, and `record.md` renders "by agent session S (relayed)". Terminal-less without the flag, it is refused. |
| AC-014 | `test_chat_mode.py` `ForgeryTests`: a fake agent in a step runs `ballast run approve --relayed-by x` and `start --mode autonomous --relayed-by x`, and both are refused (marker). `test_spec_workflow.py`: `BALLAST_AGENT_STEP=1` refuses every launcher command except `status`. |
| AC-015 | `test_chat_mode.py`: `step --headless` builds the confined argv (bwrap, scope, confined lists) and stops at the next pending gate. The full gate runs it under real bwrap. |
| AC-016 | `test_spec_workflow.py` and `test_chat_mode.py`: `reject --relayed-by` and terminal-less `reject` are refused with nothing recorded; terminal-less `trust` outside a step still works, and inside a step it is refused (D-09). |
| AC-017, AC-018 | `test_chat_mode.py`: four pending gates, one prompt listing four artifacts and digests, one typed line, four HDs in one chain, with `--through tasks` selecting the same set. |
| AC-019 | `test_chat_mode.py`: a not-pending gate, a mismatched typed line, a failing precondition on the third gate, and a crash injected before the atomic write. Each leaves the HD file and the ledger unchanged. |
| AC-020 | `test_chat_mode.py`: a terminal-less batch in a human-gated run is refused, and a relayed batch in Chat writes relayed HDs per gate. |
| AC-021, AC-022 | `test_spec_workflow.py`: `discard-runs --help` exits 0 with run state byte-identical, and `discard-runs --bogus` exits 2 with the same. |
| AC-023 | `test_spec_workflow.py`: after a discard with unchanged inputs, the Next line names no `trust` and the next run passes the launcher. With changed inputs, it names `trust`. |
| AC-024 | `tests/test_autonomous_recovery.py`: a postcondition block at `validate-implementation`, then resume, rewrites the engine state to `implement`. |
| AC-025, AC-026 | `tests/test_agent_run_ledger.py` or `test_autonomous_recovery.py`: a fake CLI prints a usage-limit message and exits 1 with the scope confirmed stopped, giving an `interrupted` block, resumable, with the marker removed. A killed wrapper gives the marker left and `unfinished-step`. |
| AC-028 | `tests/test_autonomous_recovery.py`: for each category in `BLOCK_CATEGORIES` outside the decision-free set, a relayed `resume` without `--ref` is refused with the D-08 text, and a relayed `continue` without `--ref` with today's argument refusal (the test asserts which text fires, plan-review F-003), each with the HD file and run state byte-identical; with `--ref` they record a relayed `block-resolution` carrying the ref. A `--ref` matching `HUMAN_APPROVAL` is refused. For `upstream-sync`, `interrupted` and `postcondition`, a relayed resume without `--ref` succeeds and is recorded as relayed. A test asserts the decision-free set is exactly those three, so widening it fails until the test changes. |
| AC-027 | `test_autonomous_run.py`: at a fake terminal, `switch feat-N-slug` creates and switches, and the start proceeds. Without a terminal it refuses, prints `git switch -c feat-N-slug`, and HEAD is unchanged. |

## End-to-end scratch run (required: `tools/setup` and `tools/ballast` change)

1. In the scratch repository on `main`, the operator runs `ballast setup` and `ballast trust` once. This records the baseline with `repository` and the reviewed record.
2. Create a feature branch for a small Issue. From an agent session, run `ballast run start --mode chat --relayed-by claude-code:e2e -i feature_directory=specs/N-slug`, then headless steps (`ballast run step RUN specify --headless`, and so on).
3. Merge a `ballast.toml` change (`extra_allow` plus one entry) to `main` through a PR. Merge `main` into the feature branch from the agent session (or let `ballast run step` synchronize it, then rerun the same command).
4. Expected: the next `ballast run ...` prints `refreshed the trust baseline from OWNER/NAME main at <commit>`, and `.ballast/spec_workflow/claude-settings.json` contains the new rule. The operator typed neither `trust` nor `setup` (SC-001).
5. The agent session relays `ballast run approve RUN --through tasks --relayed-by claude-code:e2e` after the operator's yes in chat. `ballast run status RUN` shows each gate "relayed by agent session claude-code:e2e" (SC-004).
6. At the operator's terminal: `ballast run approve RUN implementation spec-reconciliation final`, one typed line (SC-003). The agent session runs `ballast run publish RUN`, and the operator merges.
7. Negative checks in the same scratch checkout:
   - edit `ballast.toml` locally, then `ballast run status RUN` refuses and names `ballast trust` (AC-002);
   - `ballast run reject` from the agent session is refused, and `ballast trust` from the agent session still works (AC-016, D-09);
   - `ballast discard-runs --help` changes nothing (AC-021).
8. Record the count of operator actions (decisions plus merge only, SC-002) and the commands in the PR.
