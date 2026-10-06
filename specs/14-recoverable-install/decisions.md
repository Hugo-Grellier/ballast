# Decisions

## DEC-0001 — Proposal

- **Source**: plan review [F-004](reviews/plan.md#findings), [research R7](research.md#r7-cli-and-standard-responsibilities-and-no-minimum-bump). FR-009 (serialized, never-partial cache fetch), FR-012 (cache content record and verification), AC-010 and AC-013 are implemented in the global `ballast` CLI, which is installed per machine and updated separately from the pinned standard. A project that pins the standard version shipping this feature, on a machine whose CLI is older, gets the checkout guarantees (the pinned version's own `tools/setup` and launcher) but not the cache guarantees.
- **Classification**: spec ambiguity (the spec states the cache requirements unconditionally; the plan delivers them only with an updated CLI).
- **Proposal**: keep `tools/cli.toml [cli] minimum` at `0.1.0` and state the limitation: the cache guarantees need a CLI that includes this feature. The README's update section tells the operator to update the CLI first, and `ballast preview` (itself a new CLI command) reports the CLI version. Raising the minimum would not enforce anything (only `ballast doctor` reads it, as a report) and cannot name the CLI release that ships this feature before Release Please cuts it, so it would make `doctor` report this repository's own pin as blocked until then.
- **Alternatives**: raise `[cli] minimum` to the release that ships this feature in a follow-up once it is published; make the standard's `tools/setup` refuse when launched by an older CLI (it cannot tell which CLI launched it without a new handshake).

## DEC-0001 — Resolution

- **Status**: decided by the driving agent under the operator's standing authority for v1.0 issues (2026-10-05); listed for the merge review.
- **Decision**: accept the proposal. FR-009 and FR-012 hold on machines whose `ballast` CLI includes this feature; the README update section and the PR state the limitation. A follow-up may raise `[cli] minimum` once the release that ships this feature exists.

## DEC-0002 — Proposal

- **Source**: implementation of T023 (AC-022, FR-019, SC-007). The plan relies on the standard cache for a rollback without network, but a rollback is a full setup of the previous version, and a full build downloads the pinned Spec Kit sources (`_fetch_source`) and runs `uvx --from specify-cli==…`, both of which use the network. With staging alone, AC-022 ("restored without a network request") cannot hold.
- **Classification**: technical choice inside accepted intent (the plan missed how a build gets its Spec Kit sources).
- **Proposal**: when a switch commits, keep the entries it replaced in `.ballast/setup/kept/` and their installation record as `kept-installation.json` in operator state, one generation only. A later setup whose fingerprint equals the kept record's copies the kept entries into the stage and uses them only when the copy hashes exactly to that record, through the same verified copy as the worktree copy (FR-013); otherwise it builds normally. The copy is validated and switched like any build, so every guarantee of User Story 1 still applies. The kept area is under the already ignored `.ballast/`, outside the trusted inputs (`launcher.BASES`), and costs one extra installation on disk (a few MB).
- **Alternatives**: a per-machine cache of Spec Kit source archives (the CLI does not own setup's sources, and `uvx` would still resolve against PyPI); dropping AC-022's "without a network request" (a spec change).

## DEC-0002 — Resolution

- **Status**: decided by the driving agent under the operator's standing authority for v1.0 issues (2026-10-05); listed for the merge review.
- **Decision**: accept the proposal. Implemented in `tools/setup` (`copy_kept`, `finish`) and recorded in [data-model.md](data-model.md#installation), [contracts/operator-state.md](contracts/operator-state.md) and ADR-0007; evidence `RecoverableSetupTests.test_rollback_reuses_the_previous_installation` (downloads and Spec Kit calls denied).
