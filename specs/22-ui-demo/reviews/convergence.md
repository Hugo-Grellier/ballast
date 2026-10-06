# Convergence: on-demand UI demo capture

- Feature: [spec.md](../spec.md) (#22, R2, Autonomous run `d6b5dff2`, blocked at `record-implementation-review` by Ballast bug #83 and completed by hand for the human-gated continuation)
- Base: `origin/main` at `b90ea0f` (rebased; #82's confined checks kept)

## Evidence

- **Tasks**: T001 to T041 checked; converge appended none. SC-001 and SC-004 were never tasks: tasks.md lists them as post-merge operator evidence.
- **Decisions**: DEC-0001 (feature-branch execution scope, FR-007/AC-010 rewording) and DEC-0002 (the reproduce command shown as declared in a code span) each have a resolution by the driving agent under the operator's standing authority for v1.0 issues, listed for the merge review.
- **Reviews**: [plan](plan.md), [engineering](engineering.md), [security](security.md), [test](test.md), [documentation](documentation.md), [architecture](architecture.md), [dependency](dependency.md), [spec reconciliation](spec-reconciliation.md). Every medium finding is fixed, test-first where it changes behavior: the format gate, DEC-0002's rendering, the untested packet read failures, and the outdated action pins (fixed in the dependency review). No critical or high finding was raised. Low and info findings are fixed except two, which stay open with a reason: architecture F-002 (private `draft_pr` seam) and dependency F-002 (Dependabot does not scan `templates/`).
- **Fast gate** at the final code commit: `uvx ruff check && uvx ruff format --check` clean; `uv run --no-project --isolated --python 3.13 --with pyyaml python -m unittest tests/test_*.py`, 1231 tests (results in the PR). The host has a systemd user session, the Codex CLI, the Spec Kit CLI and `bwrap`, so the tests CI skips also ran.

## Unavailable or reduced

- Cross-provider review: every review used the authoring provider, so independence is reduced.
- Live GitHub behavior (cache scope of a `workflow_dispatch` run on a feature branch, `GITHUB_SHA`, artifact links) is taken from research R15 and is not exercised offline.
- Post-merge follow-ups for #24 (request-to-PR qualification): SC-001, a live pilot capture on one UI feature PR once `ballast-demo.yml` is on a default branch; SC-004, a reviewer reproducing that captured journey locally from the packet's command without credentials.
- The workflow-owned gates of the human-gated continuation (intent approval, `run-checks`, the recorded reviews, final acceptance) are still to run.

- Verdict: CONVERGED
