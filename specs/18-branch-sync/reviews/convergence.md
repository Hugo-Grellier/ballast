# Convergence: branch synchronization (#18)

- Date: 2026-10-05
- Inputs: `reviews/spec-reconciliation.md` (RECONCILED WITH SPEC AMENDMENTS), the operator's approval of A-1..A-13, the delegated decisions and ADR-0005 (`decisions.md` § Operator confirmation), and `reviews/pilot.md`.

## Result

- `spec.md` carries A-1..A-13 and the intent approval was re-recorded on the amended text, so the spec and `decisions.md` now say the same thing.
- ADR-0005 is accepted.
- The pilot found one defect after reconciliation: the `conflict` recovery named a local base ref the check never updates, and left a published branch to block `diverged` after the by-hand rebase. Fixed as an implementation defect (recovery wording only; no requirement changed): FR-010 requires one recovery action that works, and SC-003 requires following it without reading Ballast source. The contract table and the policy section carry the new text; `test_conflict_recovery_works_as_printed` follows it literally. The rerun of pilot steps 4–5 passed.
- `tasks.md`: every task is complete.
- No open decision, no open review finding.

- Verdict: CONVERGED
