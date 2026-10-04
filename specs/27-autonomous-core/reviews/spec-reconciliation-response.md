# Response to convergence.md (Fable reconciliation, 2026-10-04)

| Gap | Diagnosis | Resolution |
| --- | --- | --- |
| 1. plan.md lists `ledger.py` as unchanged | specification stale | Fixed: only the ledger schema is unchanged; the T069b filter-driver change is named. |
| 2. "existing cases stay unmodified" | new knowledge (T069o, DEC-0007) | Fixed in plan.md and tasks.md: fixture-only changes are listed; no existing assertion was weakened. |
| 3. ADR 0004 status asserts a merge | artifact wording | Fixed: "provisional until the operator merges the feature PR". |
| 4. An agent ran `ballast trust` | process deviation | Surfaced in the PR description for the operator: trust in the #27 worktree and the pilot was re-recorded by the coordinating agent on the operator's explicit instruction ("do the trust", "keep going until both are merged"); every operator should re-run `ballast setup` and `ballast trust` after merge anyway. |
| 5. Reviewer model is agent-reported | known ceiling | Disclosed in the PR description; FR-010's runner-filled fields (provider, role, step) are unaffected. |

With 1–3 fixed and 4–5 disclosed, the reconciliation is converged.
