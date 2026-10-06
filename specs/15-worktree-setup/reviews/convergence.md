# Convergence: prepare a new worktree on first Ballast use

- Feature: [spec.md](../spec.md) (#15, R2, Autonomous run `ccdd9716`; its `speckit.implement` step stopped on an agent OAuth failure (#65) after a partial implementation, which was completed by hand from that point)
- Base: `1ce1f9a..HEAD`; implementation baseline recorded by the run at tree `1f64b4bc4d7d`

## Evidence

- **Tasks**: T001 to T035 checked, each with evidence in [tasks.md](../tasks.md); converge appended none.
- **Decisions**: DEC-0001 (`discard-runs` clears an unfinished step on an uninstalled checkout) and DEC-0002 (stale baseline removal stated in FR-009), each resolved by the driving agent under the operator's standing authority for v1.0 issues and listed for the merge review.
- **Reviews**: [plan](plan.md) (F-001 to F-005 settled in T001 and tested), [security](implementation-security.md), [engineering](implementation-engineering.md), [tests](implementation-tests.md), [documentation](implementation-documentation.md), [spec reconciliation](spec-reconciliation.md). Two high (SEC-001, SEC-002) and three medium (SEC-003, ENG-001, ENG-004) findings were fixed test-first; low findings are fixed or accepted with a reason; residual risks SEC-005b, SEC-006, SEC-007, ENG-008, ENG-009 are listed for the merge review.
- **Fast gate** at `980511e`: `uvx ruff check && uvx ruff format --check` clean; `uv run --no-project --isolated --python 3.13 --with pyyaml python -m unittest tests/test_*.py`: 907 tests OK, 0 skipped, 709 s. The host has a systemd user session, the Codex CLI and the Spec Kit CLI, so this is also the full local gate.
- **End to end**: scratch project, primary set up with the network, two worktrees prepared with no network interface, trust refusal, `--check` current, trust then `ledger report`, per-worktree state, clean `git status` ([quickstart.md](../quickstart.md#end-to-end-scratch-project-run-record-in-the-pr)).

## Unavailable or reduced

- Cross-provider review: not run; the security pass by a fresh-context agent of the same model reduces but does not remove the shared-model blind spot. The operator may want a Codex pass before merge.
- Not checked live: preparation from a real cached pinned version without `BALLAST_STANDARD_DIR` (needs a published release carrying this feature; the cached-standard path is covered offline by `PrepareTriggerTests`), and doctor's full report on a prepared worktree with probes enabled for the same reason.
- The workflow-owned gates of the human-gated continuation (`run-checks`, recorded reviews, final acceptance) are still to run.

- Verdict: CONVERGED
