# Convergence: recoverable installs and pin updates

- Feature: [spec.md](../spec.md) (#14, R2, Autonomous run `8935922b` completed by hand after its `record-plan-review` block)
- Base: `52031c1..HEAD`; implementation baseline recorded before T001 at tree `47e9bf5b7c1c`

## Evidence

- **Tasks**: T001 to T028 checked, each with evidence in [tasks.md](../tasks.md); converge appended none.
- **Decisions**: DEC-0001 (cache guarantees need the new CLI) and DEC-0002 (kept installation for an offline rollback) each have a resolution by the driving agent under the operator's standing authority for v1.0 issues, listed for the merge review.
- **Reviews**: [plan](plan.md) (7 findings resolved), [tasks analysis](tasks-analysis.md), [security](implementation-security.md), [engineering](implementation-engineering.md), [tests](implementation-tests.md), [documentation](implementation-documentation.md), [spec reconciliation](spec-reconciliation.md). Every critical, high and medium finding is fixed test-first; low findings are fixed or accepted with a reason. No critical or high finding was raised.
- **Fast gate** at `bf5359c`: `uvx ruff check && uvx ruff format --check` clean; `uv run --no-project --isolated --python 3.13 --with pyyaml python -m unittest tests/test_*.py`: 705 tests OK, 0 skipped, 567 s. The host has a systemd user session, the Codex CLI, the Spec Kit CLI and `bwrap`, so the tests CI skips ran: this is also the full local gate's suite.
- **End to end** (project testing policy): scratch project with real Spec Kit and network (T028): setup, trust, ledger report, clean `git status`, failed patch at an unchanged pin, no-op rerun, `kill -9` during Spec Kit steps and during the switch, real cache fetch and refetch, `ballast preview v0.4.2`.

## Unavailable or reduced

- Cross-provider review: Codex CLI reported its usage limit (until 2026-10-10); every review was done by the same model as the author, so independence is reduced. The operator may want a Codex pass before merge.
- Not checked live: a worktree copy of a real installation, two real worktrees racing a GitHub download, a rollback between two published versions carrying this feature (see [spec reconciliation](spec-reconciliation.md)).
- The workflow-owned gates of the human-gated continuation (`run-checks`, the recorded reviews, final acceptance) are still to run.

- Verdict: CONVERGED
