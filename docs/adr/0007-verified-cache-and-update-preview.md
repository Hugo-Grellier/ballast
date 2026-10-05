# ADR-0007: A verified standard cache and a read-only update preview

- Status: proposed (with the plan of [feature 14](../../specs/14-recoverable-install/plan.md), 2026-10-06); accepted when its PR merges
- Feature: [14-recoverable-install](../../specs/14-recoverable-install/spec.md), FR-009, FR-012, FR-015 to FR-017, AC-010, AC-013, AC-016 to AC-021; extends [ADR-0002](0002-cli-standard-manifest.md)

## Context

The CLI trusted a cached standard version because its directory existed, so a partial extraction or a damaged file was executed. Two worktrees fetching one version could interleave. An operator learned what a pin change did only after making it, and saved runs did not say which run-state format they used.

## Decision

- The CLI fetches a version under a per-version `flock` (`standard/.locks/<ref>.lock`), extracts it into `.fetch-<ref>+<random>`, writes `.ballast-cache.json` (every file and link with its digest and executable bit) into the tree, and publishes tree and record with one rename. `setup` and `preview` verify a cached copy against its record before using it; a damaged copy is set aside and fetched again, or the command refuses naming the damaged path.
- `ballast preview <ref> [--json]` fetches and verifies the target, reads its `tools/cli.toml` and ignore block as data, runs the target's own `tools/setup` in a disposable project under `$XDG_DATA_HOME/ballast/preview/` with its own operator state, and compares it with the current installation by one procedure (record against record, or walk against walk of two disposable builds). It reports versions, the CLI minimum, run compatibility, path and ignore impact and the ordered steps, and changes nothing but the cache.
- `tools/cli.toml` gains `[setup] recoverable` (ADR-0006 applies) and `[runs] format`/`resumes`; `run.py` records the format in each new run's archive. An undeclared format is incompatible.
- `[cli] minimum` stays unchanged ([DEC-0001](../../specs/14-recoverable-install/decisions.md)): the cache guarantees and the preview need a CLI that includes them.

## Consequences

- A cached version is never executed unless its content matches what was downloaded; a version cached by an older CLI is downloaded again once.
- The preview matches an actual update because it is one, built elsewhere; it may need network.
- A change that makes saved runs unresumable must change `[runs] format`; a test fails when the Spec Kit version or a shipped workflow's step IDs change without a decision.

## Rejected alternatives

- A sidecar record next to the tree: two renames, with a window where one exists without the other.
- Trusting the archive's hash: GitHub's generated archives are not byte-stable.
- A `--plan` flag in setup: versions older than the preview could not answer it.
