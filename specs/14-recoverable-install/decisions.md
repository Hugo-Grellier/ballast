# Decisions

## DEC-0001 — Proposal

- **Source**: plan review [F-004](reviews/plan.md#findings), [research R7](research.md#r7-cli-and-standard-responsibilities-and-no-minimum-bump). FR-009 (serialized, never-partial cache fetch), FR-012 (cache content record and verification), AC-010 and AC-013 are implemented in the global `ballast` CLI, which is installed per machine and updated separately from the pinned standard. A project that pins the standard version shipping this feature, on a machine whose CLI is older, gets the checkout guarantees (the pinned version's own `tools/setup` and launcher) but not the cache guarantees.
- **Classification**: spec ambiguity (the spec states the cache requirements unconditionally; the plan delivers them only with an updated CLI).
- **Proposal**: keep `tools/cli.toml [cli] minimum` at `0.1.0` and state the limitation: the cache guarantees need a CLI that includes this feature. The README's update section tells the operator to update the CLI first, and `ballast preview` (itself a new CLI command) reports the CLI version. Raising the minimum would not enforce anything (only `ballast doctor` reads it, as a report) and cannot name the CLI release that ships this feature before Release Please cuts it, so it would make `doctor` report this repository's own pin as blocked until then.
- **Alternatives**: raise `[cli] minimum` to the release that ships this feature in a follow-up once it is published; make the standard's `tools/setup` refuse when launched by an older CLI (it cannot tell which CLI launched it without a new handshake).

## DEC-0001 — Resolution

- **Status**: decided by the driving agent under the operator's standing authority for v1.0 issues (2026-10-05); listed for the merge review.
- **Decision**: accept the proposal. FR-009 and FR-012 hold on machines whose `ballast` CLI includes this feature; the README update section and the PR state the limitation. A follow-up may raise `[cli] minimum` once the release that ships this feature exists.
