---
name: ballast-spec-reconciliation
description: Independently compare a significant feature's spec, implementation, tests, and documentation before its PR; classify convergence and actionable gaps.
---

# Spec reconciliation

Run after Spec Kit `converge` and implementation of any appended tasks. Read `spec.md`, `plan.md`, `tasks.md`, changed code, tests and public docs. For each acceptance criterion, identify implementation and executable evidence. Find behavior that contradicts or exceeds the spec, stale assumptions and architecture conflicts. Spec Kit converge appends remaining tasks; this review checks the final relationship among artifacts.

Return `CONVERGED`, `PARTIAL` or `FAILED`, with a compact criterion-to-evidence map and actionable gaps. Diagnose each gap as implementation wrong, specification stale, or new knowledge discovered. Correct the appropriate artifact explicitly; never edit the spec only to excuse a mismatch. Record a new ADR when an accepted architecture decision changes.
