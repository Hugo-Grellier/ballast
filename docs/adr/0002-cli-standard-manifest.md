# ADR-0002: A standard version declares its CLI needs in `tools/cli.toml`

- Status: accepted (with the plan of [feature 12](../../specs/12-cli-install-doctor/plan.md), 2026-10-03)
- Feature: [12-cli-install-doctor](../../specs/12-cli-install-doctor/spec.md), FR-010 to FR-012, AC-013 to AC-016

## Context

`ballast doctor` is part of the machine-wide CLI, so it must work with whatever standard version a project pins, including versions older than doctor. Setup freshness belongs to `tools/setup` and trust readiness to `tools/spec_workflow/launcher.py`; both differ per version.

## Decision

- Each standard version from this feature on ships `tools/cli.toml` (contract: [standard-manifest.md](../../specs/12-cli-install-doctor/contracts/standard-manifest.md)):
  - `[cli] minimum`: the lowest CLI version it works with, bumped only when it relies on newer CLI behaviour;
  - `[doctor] probes`: the read-only probes it supports, `setup-check` (`tools/setup --check`) and `launcher-status` (`launcher.py status --json`).
- The CLI parses this file as data with `tomllib` and never executes it. It runs a probe only when the manifest declares it, only with `/usr/bin/python3 -I -S`, and only from the fetched standard directory; it refuses when that directory or a probe file resolves into the project or any Git working tree, and executes nothing for `BALLAST_STANDARD_DIR`.
- A missing manifest means a version older than doctor: no minimum, no probes; the affected checks are `inconclusive` with a remedy.

## Consequences

- The trust comparison and the setup fingerprint keep one owner each; doctor recomputes neither.
- An older pinned version is never sent a flag it does not know.
- The file ships with the standard and lands in no project path (BL-INV-001).

## Rejected alternatives

- Reimplementing `_refusal` or the setup fingerprint in the CLI: a second source of truth that drifts per version.
- Detecting capabilities from error output of older versions: fragile, and it executes code that was never meant to answer.
