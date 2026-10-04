# Decisions: Autonomous run core

## DEC-0001 — Proposal

- **Found during**: T004 (implementation, 2026-10-04).
- **Conflict**: The plan and T004 name the ADR `docs/adr/0001-autonomous-provisional-decisions.md` as "the first ADR in this repository". Since the plan was approved, `main` gained `docs/adr/0001-cli-release-asset-install.md` and `docs/adr/0002-cli-standard-manifest.md` (feature 12), so `0001` is taken.
- **Label**: spec ambiguity (artifact numbering only; no behavior change).
- **Proposal**: Record the ADR as `docs/adr/0003-autonomous-provisional-decisions.md`, the next free number on this branch. The parallel branch `feat-github-draft-pr` also drafts a `0003` (`0003-launcher-github-authority.md`), so whichever merges second renumbers its ADR; settle the final number at merge and update the references in `tasks.md`, `plan.md` and the ADR.
- **Needs**: human resolution (operator).
