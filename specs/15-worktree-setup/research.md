# Research: Prepare a new worktree on first Ballast use

Phase 0 decisions for [plan.md](plan.md). Each is agent-provisional in this Autonomous run; merging the PR is the single human approval (BL-INV-006).

Evidence is the current code: `tools/ballast` (`command_standard`, `ensure_standard`, `damage`, `declarations`, `main`), `tools/setup` (`Setup.main`, `lock`, `attempt`, `build`, `copy_verified`, `copy_kept`, `copy_from_primary`, `recover`, `roll_back`, `finish`, `validate`), `tools/spec_workflow/launcher.py` (`state_dir`, `read_record`, `checkout_lock`, `_hold`, `_trust_refusal`, `main`), `tools/cli.toml`, ADR-0007 and ADR-0008.

## R1. The CLI triggers preparation; the pinned standard's setup performs it

- **Decision**: `tools/ballast` decides *whether* to prepare; the pinned version's `tools/setup --prepare` decides *how*, and refuses every case it does not handle. For `run`, `ledger` and `intake` only (D-04), the CLI calls preparation when the checkout needs an installation: `.ballast/spec_workflow/run.py` is not a file (the launcher's own `installed` test), or a setup journal (`setup-attempt.json`) exists in the checkout's operator state. It runs `/usr/bin/python3 -IS <standard>/tools/setup --project <root> --prepare` as a child process with inherited stdout and stderr, then, on exit 0, `execv`s the launcher as today; any other exit code is returned unchanged and the launcher does not run.
- **Rationale**: ADR-0002 keeps the CLI from reimplementing setup, and ADR-0007's stage, validation, journal, lock and recovery live in `tools/setup`, so reusing them in a local-only mode keeps every recovery guarantee unchanged (spec Assumptions). The launcher cannot prepare because it runs `execv` into the workflow tool and is not allowed to grow installation logic; the CLI already chooses between `setup` and the launcher. Running the child instead of `execv` is required because the launcher must still run afterwards; the child is the same pinned, verified file `ballast setup` would execute.
- **Alternatives considered**: The launcher calling setup: mixes the trust gate with installation and runs setup under the shared checkout lock the launcher must keep through `execv`. Calling `ballast setup` implicitly (full mode): may download (breaks D-01).

## R2. A version declares that it can prepare

- **Decision**: `tools/cli.toml` gains `[setup] prepare = true`. The CLI reads it as data, like `[setup] recoverable` (`declarations`). When the pinned version does not declare it (AC-007), the CLI refuses an uninstalled checkout itself, before the launcher, with `nothing is installed in this checkout; run \`ballast setup\``, exit 2, and makes no request.
- **Rationale**: FR-013. A version older than this feature has no `--prepare` flag; passing it would fail with an argparse error rather than a precise refusal. Today such a checkout reaches the launcher, which prints its usage text, which does not name `ballast setup`; the CLI refusal makes AC-007's "refusal naming `ballast setup`" true for every pinned version.
- **Consequence**: Using the feature needs a CLI and a standard release that both include it; `[cli] minimum` stays unchanged (an older CLI never prepares and keeps today's behavior).

## R3. Network: never, and the cache must verify

- **Decision**: On the preparing commands the CLI keeps today's not-fetched refusal (`standard <ref> is not fetched; run \`ballast setup\``) and, when the version is cached, verifies it with `damage()` before running its setup; damage refuses with `the cached standard <ref> is damaged at <path>; run \`ballast setup\` to fetch it again`, exit 2, and fetches nothing (AC-013). `setup --prepare` never calls `install_spec_kit` or `_fetch_source`: when no candidate verifies it refuses instead of falling back to a full build (D-01).
- **Rationale**: FR-002 and FR-005; the testing policy's "only `setup` and `preview` download" and "a cached version is verified against its content record before use". Verifying costs one hash of the standard tree (a few MB), well inside SC-005.
- **With `BALLAST_STANDARD_DIR`**: no cache is read or verified (today's rule for a local standard); the declaration and `tools/setup` come from that directory (spec Edge Cases).

## R4. Candidate sources: every recorded installation of this repository on this machine

- **Decision**: In order, the first that verifies wins (D-03, option A): (1) this checkout's own kept installation (`.ballast/setup/kept` with `kept-installation.json`); then, for each other checkout listed by `git worktree list --porcelain -z` run in this checkout (primary first, then linked worktrees in Git's order), (2) its live installation with `installation.json`, and (3) its kept installation with `kept-installation.json`. Entries Git marks `prunable` or whose path does not exist are skipped with a reason (spec Edge Cases). Every candidate is read only through operator state keyed by its resolved path (`launcher.state_dir`).
- **Acceptance rules** (FR-004), each rejection with a reason kept for the outcome:
  1. Not unfinished: the candidate's `setup-attempt.json` is absent → else `its setup did not finish`.
  2. Not in progress: a shared, non-blocking `checkout.lock` on the candidate succeeds and is held through the copy → else `it is being set up`. The lock is opened only when the lock file exists, so preparation never creates a file in another checkout's operator state; a candidate without one is rejected with `it has no checkout lock` (plan review F-004).
  3. A record exists and is valid, read **after** the lock is taken (closes the read-then-lock window of today's `copy_from_primary`): for a live installation `launcher.read_record` (fingerprint equals the candidate's stamp); for a kept one the existing `copy_kept` checks.
  4. Same pin and configuration: `record.ref == self.ref` and `record.fingerprint == self.fingerprint()`. The fingerprint already digests `ballast.toml` bytes, the standard's `tools/` and `templates/` and the Spec Kit version, so a different `[agents.permissions]` differs (AC-009); the ref check rejects a byte-identical standard reached through a different tag, whose record would otherwise name another pin.
  5. Content and modes: the copy into the stage hashes equal to `record.files` (`copy_verified`), and every copied file's executable bit equals the record's `executable` list (R5).
- **Rationale**: Reuses #14's records and verified copy; no new store, no new trust (D-03). A matching fingerprint means the same `tools/setup` wrote the source record, so the source is held to exactly the rules this version would apply. Holding the source's shared lock blocks a setup there for the length of one copy (well under SC-005) and never blocks its `run`, `ledger` or `intake` (also shared).
- **Safety of the candidate list**: Git's worktree metadata lives in the common directory, which the agent sandbox keeps read-only; even a forged entry only yields a candidate whose copy must hash equal to an operator-written record for that exact path, so no unrecorded or altered content can be accepted.
- **Alternatives considered**: A new per-machine installation store (D-03 option B, non-goal). Primary only (option C): AC-003 requires siblings and kept copies. Copying from the cache plus a Spec Kit download: needs network.

## R5. The installation record lists executable files

- **Decision**: `validate()` adds `"executable": [<sorted paths of installed regular files with any execute bit>]` to the installation record, which keeps `schema: 1` (readers ignore unknown keys; `launcher.read_record` and the CLI's `installation()` are unchanged). `copy_verified` compares the stage copy's executable set to the record's list when the record has one; `--prepare` additionally rejects a candidate whose record has no list (`its record predates file-mode checks`). `ballast setup`'s existing primary copy also gains the check when the list is present.
- **Rationale**: D-06 option A. The content digests (`launcher.digests`) do not cover modes, and changing that format would invalidate every trust baseline. Because a usable candidate shares this version's fingerprint, its record was written by this version's `validate()` and has the list; a record without it can only come from an earlier version and is never this fingerprint's, so the extra rejection is defense in depth.
- **Alternatives considered**: Comparing against the source's live modes: that is the thing being checked. A record schema bump: every older reader would discard current records.

## R6. Which states preparation acts on, and recovery

- **Decision** (D-05, FR-007): under the exclusive checkout lock, `--prepare`:
  1. Reads the journal, if any. A journal whose `mode` is `prepare` is recovered (R7); when that finished a committed attempt at the current fingerprint, preparation ends successfully there. Any other journal refuses with the launcher's existing `setup did not finish in this checkout; run \`ballast setup\` to recover`, exit 2.
  2. Refuses while the launcher's `in-progress` marker exists, as setup does.
  3. Reports `nothing to prepare: this checkout is already installed for <ref>` and exits 0 when the live installation is current for this ref and fingerprint (`Setup.current`), so a second command started together with the first reaches the launcher (plan review F-001).
  4. Refuses when anything of an installation is present: a stamp, a valid record, or any path `Setup.live_entries` lists (ADR-0007's `entries(root)` minus entries holding a tracked file, F-002) → `this checkout already holds an installation (<--check status>); run \`ballast setup\``, exit 2. Only a checkout with no installation at all is prepared.
- **Rationale**: A command other than `setup` must never switch an installation a paused run may depend on (D-05). `entries(root)` is ADR-0007's single definition of an installation and `live_entries` the one switch and record use, so "no installation" uses the same rule; a project file tracked under `docs/policies/` is never an installation.

## R7. Recovering an interrupted preparation

- **Decision**: Every preparation journal has `mode: "prepare"` and an empty `before` (R6 guarantees nothing was installed). Recovery, run first by the next preparing command or by `ballast setup`:
  - `staging`: discard the work area (today's rule).
  - `switching`: `roll_back` (today's rule); verification against the empty `before` proves nothing is left.
  - `committed` with the journal's fingerprint equal to the current one: `finish` (today's rule, ADR-0007), so a preparation that already verified live is completed, not redone.
  - `committed` with a different fingerprint (the pin or `ballast.toml` changed meanwhile, spec Edge Cases): roll back instead, removing the new entries and the installation record if `finish` had written it; the worktree is then uninstalled for the new pin and preparation continues against it.
  - Each case prints `recovered an interrupted preparation: <what is in place>` (AC-018), and preparation then continues; `ballast setup` recovers the same journal and continues with a full setup.
- **Rationale**: AC-018 and AC-019 with ADR-0007's mechanism unchanged; the only addition is rolling a committed *first* preparation back when its fingerprint no longer applies, which is safe because the entries are git-ignored and rebuildable and nothing preceded them. `roll_back` already handles a committed switch: every planned entry is `new`, the live entry exists and its staged path does not, so it is moved back into the work area and discarded.
- **Concurrency in one worktree** (AC-020): the exclusive `flock` lets one preparation run; a second refuses at once naming the holder from `setup-holder.json`, which gains `mode` so the message reads `another ballast preparation (PID …, started …, ref …) holds this checkout; wait for it to finish, then rerun the command`. No waiting, matching #14's refusal rule.

## R8. Preparation never writes project-owned files or trust

- **Decision**: In prepare mode `finish` never creates the constitution (a first full setup still does), seeds are copied only into the stage, and nothing in `docs/policies/project/` or `ballast.toml` is opened for writing (FR-011). Preparation reads, in another checkout's operator state, only `installation.json`, `kept-installation.json`, `setup-attempt.json` (existence) and `checkout.lock`; it never opens `trusted.json` anywhere (FR-009, AC-012).
- **Stale baseline at a reused path**: operator state is keyed by the checkout's resolved path, so a worktree re-created where a removed one lived finds that checkout's old `trusted.json`. Because a prepared worktree had no installation, any baseline already in its state directory predates it; preparation deletes it before the switch and prints `removed a trust baseline left by an earlier checkout at this path`. AC-002 (and SC-003's "no baseline it did not record itself") then holds whatever the path's history. This removes operator state only for the worktree being prepared, never records one, and costs at most one extra `ballast trust`.
- **Alternatives considered**: Leaving it: a re-created worktree could pass preflight on a baseline nobody recorded for it. Refusing: blocks a legitimate re-creation for no safety gain.

## R9. The launcher's preflight says exactly what is missing

- **Decision**: `_trust_refusal`'s no-baseline message becomes `no trusted baseline for this checkout; review its protected inputs (<inputs>), then run \`ballast trust\``, where `<inputs>` lists the input bases that exist (`ballast.toml`, `.ballast/spec_workflow`, `.specify`, `.venv`, and `.git` for a linked worktree's pointer, from `input_bases`). The `no trusted baseline` prefix is kept, so doctor's classification and remedy are unchanged. For an uninstalled checkout, `trust` and `discard-runs` refuse with `nothing is installed in this checkout; run \`ballast setup\`, or \`ballast run\`, \`ledger\` or \`intake\` to prepare it from a verified installation on this machine` (FR-012) instead of the usage text, and record nothing.
- **Rationale**: FR-008 and AC-002 ask for a precise statement of the inputs to review and the next action; the launcher already knows both. The usage text on an uninstalled checkout never named how to install.

## R10. Verification approach

- **Decision**: Offline `unittest`, reusing `tests/test_setup.py`'s fakes (`fake_run`, `fake_fetch`, archives per ref) and kill wrapper (no production fault hook, as feature 14's R12). New cases create real linked worktrees with `git worktree add` in a temporary repository, with `XDG_STATE_HOME` and `XDG_DATA_HOME` in the test directory. "No network" is asserted by replacing `_fetch_source` and `urllib.request.urlretrieve` with functions that fail the test, and by running CLI children with `PATH` lacking `uvx`. Concurrency runs ten child processes released together by a shared barrier file. Every "unchanged" claim uses before/after snapshots of the worktree's project-owned files, the source checkouts' trees and their operator state. SC-002's 20 repetitions run as a looped test marked slow but kept in the suite (each repetition copies a fake installation of a few kB). The networked end-to-end scratch-project run, with two worktrees, is recorded in the PR.
- **Rationale**: FR-015, Constitution principle 8, and the project testing policy.

## Unresolved

None. Every Technical Context item is decided above.
