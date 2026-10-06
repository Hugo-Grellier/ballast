# Decisions

## DEC-0001 — Proposal

- **Source**: implementation security/engineering review [ENG-001](reviews/implementation-engineering.md#findings). An agent step's `in-progress` marker can remain in a checkout with no installation: a worktree re-created at a path whose earlier checkout left a marker, or an installation removed after a killed step. Preparation (contract step 4) and `ballast setup` refuse while the marker exists, naming `ballast discard-runs`; FR-012 and contract F-003 make `discard-runs` refuse on an uninstalled checkout, naming `ballast setup`. The operator is sent in a circle and can leave only by deleting operator state by hand.
- **Classification**: spec ambiguity (FR-012 did not consider an uninstalled checkout holding an unfinished agent step).
- **Proposal**: `ballast discard-runs` refuses on an uninstalled checkout except when that checkout's `in-progress` marker exists; then it runs as on an installed checkout (stops the step's scope, removes local run state, clears the marker). It still creates nothing when no marker exists (F-003 holds), `trust` keeps refusing, and nothing is installed by it (FR-009 and D-04 hold).
- **Alternatives**: let setup and preparation ignore a marker on an uninstalled checkout (would skip stopping a possibly live agent scope); tell the operator to delete operator state by hand (an undocumented manual path through operator state).

## DEC-0001 — Resolution

- **Status**: decided by the driving agent under the operator's standing authority for v1.0 issues (2026-10-05); listed for the merge review.
- **Decision**: accept the proposal. Implemented in `tools/spec_workflow/launcher.py` (`_marked`, `main`); FR-012, AC-005 and [contracts/cli-and-launcher.md](contracts/cli-and-launcher.md) state the exception; evidence `TrustedLauncherTests.test_unfinished_step_is_discarded_on_an_uninstalled_checkout` (failed before the change) and `test_uninstalled_checkout_is_refused_without_writing` (unchanged, still passes).

## DEC-0002 — Proposal

- **Source**: tasks analysis U1 (recorded in PD-0009), [research R8](research.md#r8-preparation-never-writes-project-owned-files-or-trust), plan "Proposed architecture decisions". Operator state is keyed by the checkout's path, so a worktree re-created where a removed one lived finds that checkout's `trusted.json`. The accepted plan removes such a baseline during preparation; spec.md does not say so.
- **Classification**: spec ambiguity (behavior accepted in the plan, missing from the spec).
- **Proposal**: add to FR-009 that a baseline already in a worktree's own operator state when preparation installs it predates the installation and is removed (never read), so the worktree still needs its own `ballast trust`; the outcome names the removal. This only narrows trust and costs one extra `ballast trust`.
- **Alternatives**: leave the baseline (a re-created worktree could pass preflight on a baseline nobody recorded for it); refuse preparation (blocks a legitimate re-creation).

## DEC-0002 — Resolution

- **Status**: decided by the driving agent under the operator's standing authority for v1.0 issues (2026-10-05); listed for the merge review.
- **Decision**: accept the proposal; FR-009 updated. Evidence `PrepareTests.test_no_baseline_is_inherited` (reused-path case). The same situation under `ballast setup` (no preparation) is unchanged and noted as accepted residual risk SEC-005 in the [security review](reviews/implementation-security.md).
