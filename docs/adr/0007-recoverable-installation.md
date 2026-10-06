# ADR-0007: Setup stages, journals and switches an installation

- Status: proposed (with the plan of [feature 14](../../specs/14-recoverable-install/plan.md), 2026-10-06); accepted when its PR merges
- Feature: [14-recoverable-install](../../specs/14-recoverable-install/spec.md), FR-001 to FR-014, FR-019, AC-001 to AC-015, AC-022, AC-023

## Context

`tools/setup` deleted the previous installation and rebuilt it in place, so a failed download, a Spec Kit or patch error, or a killed process left a checkout without a usable installation, and the constitution survived only through an in-process restore. "Current" meant a matching stamp, which says nothing about content, so a damaged primary checkout was copied into worktrees. Installed paths are scattered over `.ballast/`, `.specify/`, skill directories and `docs/policies/`, so one atomic rename of everything is impossible.

## Decision

- One rule (`entries(root)`) defines an installation: its entries are the unit of a switch, the record, verification, the worktree copy and the no-op check.
- Setup builds the whole replacement in a stage, `.ballast/setup/<attempt>/stage/`, its own Git repository, validates it (required outputs, ignore rules, no stage path in a staged file, no unexpected output, one filesystem, no link among the parents), then switches each entry with two renames, keeping the previous entry aside until the live installation hashes equal to what was built.
- A journal, `setup-attempt.json` in the checkout's operator state, is written durably before each phase. The next setup rolls an unfinished switch back, keyed on whether each entry belongs to the new installation, or finishes a committed one, and says which.
- The installation record, `installation.json` in operator state, holds the ref, fingerprint, entries and content digests. It is valid only while its fingerprint equals the live stamp. It, not the stamp, defines "current and verified", and a worktree copies its primary only when the copied content equals the primary's record.
- The entries a switch replaced are kept in `.ballast/setup/kept/` with their record, so a rollback to the previous pin reinstalls them, verified, without a download.
- An `flock` on `checkout.lock` in operator state serializes setup (exclusive) against `run`, `ledger`, `intake`, `trust` and `discard-runs` (shared, kept through `execv` by the workflow tool). The launcher refuses while a setup runs, while a journal exists, or while a valid record names a ref other than the pin.
- Setup never writes the project's constitution except to create it when absent, never edits `ballast.toml`, never records trust and never clears operator markers. *Superseded in part by [ADR-0015](0015-setup-recorded-trust-baseline.md): "never records trust" no longer holds; setup records the baseline itself under that ADR's conditions.*

## Consequences

- Any failure or interruption leaves a complete previous or a complete new installation, never a mix; at an unchanged pin the trust baseline still holds.
- A switch needs the stage and the live entries on one filesystem, and the checkout briefly holds two installations.
- A version older than this decision runs its own setup, without these guarantees; the record then goes stale and every reader ignores it.

## Rejected alternatives

- Building in place behind a backup copy: doubles disk use and a killed copy leaves two partial trees.
- A journal or record in the checkout: an agent could write them.
- A PID file for mutual exclusion: PID reuse makes it unreliable; the kernel releases an `flock` on death.
