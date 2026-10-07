# Convergence: local zero-cost fallback

- Feature: [spec.md](../spec.md) (#23, R2, Autonomous run `f200c320` continued human-gated; the merge is the single human approval)
- Base: `origin/main` at `51edd7d` (after #93, #96, #99 and #89), branch `feat/23-free-fallback` rebased on it

## Evidence

- **Tasks**: T001 to T037 checked, each with evidence in [tasks.md](../tasks.md); converge appended none.
- **Decisions**: DEC-0001 to DEC-0004 resolved in [decisions.md](../decisions.md).
- **Reviews**: [plan](plan.md), [security](security.md), [engineering](engineering.md), [test](test.md), [documentation](documentation.md), [live check](live-check.md), [spec reconciliation](spec-reconciliation.md). Every critical, high and medium finding is fixed test-first (the high proxy finding F-001 and the medium F-002 included) or resolved with a reason; each report has a Resolution section and an approved verdict.
- **Rebase**: one conflict in `tools/spec_workflow/agent.py` against #96 (exclusive in-progress claim); both kept (the claim and its cleanup on failure, plus the fallback's metadata, `stdin` and log descriptor handling).
- **Gates** after the rebase: `uvx ruff check && uvx ruff format --check` clean (418 files). Full suite `uv run --no-project --isolated --python 3.13 --with pyyaml python -m unittest tests/test_*.py`: 1411 tests, 2506 s, 2 failures, both in `tests.test_chat_mode` with exit 130 under load (known flake #94: `ConcurrencyTests.test_the_run_lock_lets_one_invocation_through`, `ReturnPreflightTests.test_advanced_base_is_synchronized_before_the_agent`); rerun alone, both pass. Every other test passes, the fallback tests included.

## Unavailable or reduced

- Cross-provider review was not possible; reviews were done by the same model family as the implementation, so independence is reduced.
- Pilot quickstart steps through `ballast run start --local-fallback` and an Autonomous fallback were not run live (see [spec reconciliation](spec-reconciliation.md) gaps); they are covered offline and by the live wrapper check.

- Verdict: CONVERGED
