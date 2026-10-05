# Research: Recoverable installs and pin updates

Phase 0 decisions for [plan.md](plan.md). Each decision is agent-provisional in this Autonomous run; merging the PR is the single human approval (BL-INV-006).

Evidence is the current code: `tools/setup` (deletes then rebuilds in place, `Setup.main`), `tools/ballast` (`fetch`, `main`, doctor), `tools/spec_workflow/launcher.py` (`state_dir`, `_refusal`, `trusted_inputs`), `tools/spec_workflow/run.py` (`_record`) and `tools/spec_workflow/ledger.py` (`archive_dir`, `flock`-based `_lock`).

## R1. Build into a stage project, then switch entry by entry

- **Decision**: Setup builds the complete replacement in a stage directory `.ballast/setup/<attempt>/stage/`, which is its own Git repository (`git init`), seeded only with the inputs a build reads (`ballast.toml`, `.gitignore`, and the constitution when present). Every Spec Kit command, patch and copy runs with the stage as its project root. After validation (R4), setup switches each installed entry with two `rename(2)` calls: live → `.ballast/setup/<attempt>/previous/`, stage → live. Backups are deleted only after the live installation is verified against the new record.
- **Rationale**: Installed paths are scattered (`.ballast/spec_workflow`, parts of `.specify/`, skill directories, `docs/policies/*.md`), so one atomic rename is impossible (spec Assumptions). Renames inside one filesystem are atomic per entry, preserve bytes and modes, and need no copy, so a journal can always tell which side of each entry is live (R2). A separate Git repository makes the stage its own project root, so Spec Kit can never resolve the checkout's toplevel and write into live paths. `.ballast/` is already ignored by the shipped block and only `.ballast/spec_workflow` is a trusted input (`launcher.BASES`), so a leftover work area never changes the trust baseline (FR-006) and no project edits its `.gitignore`.
- **Evidence the move is safe**: worktrees already receive a copied installation (`copy_from_primary`) and run, so installed content does not depend on its absolute location. Validation still refuses any staged text file that contains the stage's absolute path (R4).
- **Alternatives considered**: Building in place behind a backup copy (today's order plus a copy): a copy of `.specify` doubles disk use and a killed copy leaves two partial trees. A top-level `.ballast-staging/` directory: needs a new ignore line, which would make every existing project's next setup refuse. Staging under `/tmp`: agent-writable and usually another filesystem, so no atomic rename.

## R2. A journal in operator state decides recovery

- **Decision**: Setup writes `setup-attempt.json` in the checkout's operator state directory (`launcher.state_dir(root)`) with an atomic replace and `fsync` before each phase change: `staging` → `switching` (with the ordered entry list) → `committed`. The next setup, before anything else, recovers: `staging` → delete the work area, previous installation kept; `switching` → roll every entry back from `previous/`; `committed` → finish the switch (delete backups). It then reports which installation the checkout holds and continues with the requested setup.
- **Rationale**: FR-003 needs a durable record that survives a killed process, and AC-004 needs a deterministic resolution. Rolling back an unfinished switch always reaches the previous installation, whose bytes are intact in `previous/` or still live. Rolling forward only from `committed` means the new installation was already verified live. Operator state is outside every agent's write authority (#34), so an agent cannot forge a journal that makes setup move files.
- **Alternatives considered**: Journal inside the checkout: agent-writable. Roll forward whenever the stage is complete: needs a second validation of a stage an interrupted process may have left half-moved; rollback is simpler and equally complete. Recovery as a separate command: one more thing for the operator to know; the spec names `ballast setup` as the recovery.

## R3. The installation record is the authority for "current and verified"

- **Decision**: On commit, setup writes `installation.json` in operator state: the pinned ref, the existing fingerprint, the Spec Kit version and a digest of every installed file and link, in the `launcher.digests` format (`sha256` hex, or `link:<target>`). Runtime paths under installed entries (`LOCAL_STATE`) are excluded. `.ballast/.setup-version` keeps being written as today, for older setups after a rollback, and new code no longer reads it.
- **Uses**: no-op detection (FR-011: fingerprint equal **and** live content equal to the record), worktree copy (FR-013), the launcher's pinned-versus-installed refusal (AC-008), doctor's detail, the preview's "before" side (FR-015), and removal of entries a previous version installed but the new one does not.
- **Rationale**: The stamp is in the checkout and records inputs, not content, which is why AC-014's damaged primary passes today. A content record in operator state cannot be rewritten by an agent and has one writer (setup).
- **Alternatives considered**: Extending the stamp: agent-writable. Recomputing what a version builds on demand: needs a full build and network on every check.

## R4. Validation before the switch, verification after it

- **Decision**: Before switching, setup refuses the stage when any check fails, naming it: (1) every `PROMISED` output exists in the stage; (2) `git check-ignore --no-index --stdin` in the real checkout ignores every staged path, and the existing `IGNORE_PROBES` still hold; (3) no staged text file contains the stage's absolute path; (4) all staged entries and the checkout's installed entries are on one filesystem (`st_dev`). Setup then records the stage's digests as the new record. After the switch it hashes the live installation and rolls back on any difference.
- **Rationale**: FR-002 lists the three checks; (3) and (4) make R1's move safe. Verifying after the switch makes "content matching what was built" a postcondition (BL-INV-005) rather than an assumption about `rename`.

## R5. One checkout lock for setup and the launcher

- **Decision**: An `flock` on `checkout.lock` in operator state. Setup takes `LOCK_EX | LOCK_NB` and writes its holder (PID, start time, ref) into `setup-holder.json`. The launcher takes `LOCK_SH | LOCK_NB` before its refusal check for `run`, `ledger` and `intake`, and keeps the descriptor across `execv` (`os.set_inheritable`), so the lock lasts as long as the workflow tool runs. Setup refuses when the lock is held, naming the setup holder or "a `ballast run`, `ledger` or `intake` command"; the launcher refuses while a setup holds it. Setup also refuses while the launcher's `in-progress` marker exists, naming `ballast discard-runs`, and never clears it.
- **Rationale**: FR-008 and FR-014 need mutual exclusion, and FR-010 needs a dead holder to never block: the kernel releases an `flock` when its process dies, so no PID liveness heuristic is needed (same-machine only, as the spec assumes). `ledger.py` and `draft_pr.py` already use `flock`. Agents do not inherit the descriptor: `subprocess` closes inherited descriptors by default and agents run in a systemd scope started by the manager.
- **Alternatives considered**: A PID file with liveness checks: PID reuse makes it unreliable. Waiting instead of refusing in one checkout: the spec chose refusal.

## R6. The cache: per-version lock, content record, single rename

- **Decision**: In `tools/ballast`, `fetch` takes a blocking `flock` on `standard/.locks/<ref>.lock` (bounded wait, then a refusal naming the lock), re-checks for a verified copy after acquiring it, removes stale `.fetch-*` directories, extracts into `standard/.fetch-<random>/`, writes `.ballast-cache.json` (schema 1, every file and link with digest and executable bit) into the extracted tree, and publishes tree and record with one `rename`. Before `setup` and `preview` use a cached version, the CLI verifies it against its record. A missing record, or a missing, added or altered file, is damage: the damaged tree is renamed to `.damaged-<random>` and removed, then fetched again under the same lock; when the fetch fails the command refuses and names the damaged path.
- **Rationale**: FR-009, FR-012 and AC-010/AC-013. The record inside the tree is published by the same rename, so there is never a tree without its record from this CLI. A partial extraction from an older CLI has no record and is treated as damaged (spec Edge Cases). Other launcher commands keep today's existence check (the spec requires verification for setup and preview only), so their latency does not change.
- **Consequence**: A version cached by a CLI older than this feature is fetched again once. A rollback to such a version needs network once; the README says so.
- **Alternatives considered**: A sidecar record next to the tree: two renames, with a window where one exists without the other. Trusting the archive's own hash: GitHub's codeload archives are not byte-stable.

## R7. CLI and standard responsibilities, and no minimum bump

- **Decision**: The checkout guarantees (R1 to R5, launcher refusals) live in the standard version's `tools/setup` and `launcher.py`; the cache guarantees (R6), the preview and the not-fetched message live in the CLI. `tools/cli.toml [cli] minimum` stays `0.1.0`, because the standard relies on no new CLI behavior.
- **Rationale**: A pinned version's own setup always runs (ADR-0002 keeps the CLI from reimplementing it), and the cache is read only by the CLI. Raising the minimum would block projects whose operators have not updated the CLI, without making any checkout guarantee stronger. The README update section tells operators to update the CLI first to gain cache verification and the preview.

## R8. The update preview is a CLI command that builds the target in a disposable project

- **Decision**: `ballast preview <ref> [--json]`. It fetches and verifies the target into the cache, reads the target's `tools/cli.toml` as data, and runs the target's own `tools/setup --project <disposable>` under `/usr/bin/python3 -I -S`, where `<disposable>` is a fresh Git repository under `$XDG_DATA_HOME/ballast/preview/<random>/` seeded with copies of `ballast.toml` (with `[standard] ref` set to the target), `.gitignore` plus the target's ignore block, and the constitution. `XDG_STATE_HOME` points into the same disposable directory, so the target's setup never touches real operator state. The "after" side is a walk of the disposable project minus its seeds and `.git`; the "before" side is the installation record when the live installation matches it, otherwise a disposable build of the pinned version by the same procedure. The directory is deleted afterwards, in every outcome.
- **Rationale**: FR-015/FR-017 and SC-006: diffing two real builds is the only way to match the actual result for any target, including versions older than this feature, which take no new flag. The target's ignore block is read from its `tools/setup` with `ast` (`GITIGNORE` and `IGNORE_PROBES` literals), parse-only, never executed. Ignore impact is then `git check-ignore --no-index --stdin` in the real checkout over every target path and probe, read-only.
- **Network**: the disposable build downloads Spec Kit sources; the preview may therefore need network even with the target cached. AC-020 permits only the cache to change, and the disposable directory is removed.
- **Alternatives considered**: A `--plan` flag in the target's setup: unavailable for older targets. Diffing standard trees: misses Spec Kit's generated files. Running the build under `/tmp`: agent-writable, so an agent could plant files and mislead the report.

## R9. Run-state format declarations

- **Decision**: `tools/cli.toml` gains `[runs] format = "ballast-run/1"` (the format this version writes) and `resumes = ["ballast-run/1"]` (formats it can resume). `run.py` (which runs from the checkout, so it holds the value as a `RUN_FORMAT` constant that a test keeps equal to `[runs] format`) writes `run-format.json` (`{"schema": 1, "format": "ballast-run/1"}`) into the run archive (`archive_dir`, in the Git common directory) when a run starts. The preview lists every run under `.specify/workflows/runs/` whose engine `state.json` status is not `completed`, reads its archived format, and marks it compatible only when the target's `resumes` names that format. A missing record or declaration is incompatible, with "finish or discard this run before updating". A test fails when the Spec Kit `VERSION` or a shipped workflow's step IDs change while the format string stays the same, forcing a deliberate format decision.
- **Rationale**: FR-016 and the spec assumption that runs record no format today. The archive is outside the checkout and outside agent write authority.
- **Alternatives considered**: Deriving compatibility from Spec Kit versions: Ballast's own workflow and records change between versions too.

## R10. `[setup] recoverable` marks versions with these guarantees

- **Decision**: `tools/cli.toml` gains `[setup] recoverable = true`. The preview reports a target without it as not carrying this feature's recovery guarantees (AC-021), including a rollback to it.
- **Rationale**: Same pattern as `[doctor] probes` (ADR-0002): capability is declared as data, never detected by executing.

## R11. Pinned versus installed version messages

- **Decision**: The launcher refuses `run`, `ledger` and `intake`, before the trust comparison, when operator state holds an unfinished `setup-attempt.json` ("setup did not finish; run `ballast setup`") or when `installation.json` names a ref other than the pin ("pinned vB, installed vA: restore `ref = "vA"` in `ballast.toml`, or fix the cause and rerun `ballast setup`"). `tools/setup --check` reports `interrupted` and `stale: pinned vB, installed vA; …` with the same two actions; doctor shows that detail unchanged. When the pinned version is not fetched, the CLI's refusal names the installed ref from `installation.json` and both actions.
- **Rationale**: AC-005 and AC-008. A pin change already fails the trust comparison (`ballast.toml` is a trusted input), but that message names neither version nor the recovery. `installation.json` is read as data by the CLI (one field, `ref`), like `tools/cli.toml`.

## R12. Fault injection without production test seams

- **Decision**: Tests inject failures by patching `Setup` methods in-process (existing `test_setup.py` style), and kills by running a small wrapper script that loads `tools/setup`, replaces one named function with `os.kill(os.getpid(), SIGKILL)` and calls `Setup.main()`. No environment variable or flag in production code triggers a fault.
- **Rationale**: SC-001 needs kills at five or more points; a production fault hook would be an operator-reachable switch for no user value.

## R13. Constitution and other project-owned files are never written in the checkout

- **Decision**: The stage's constitution is discarded with the stage. Setup copies `.specify/memory/constitution.md` from the stage into the checkout only when the checkout has none (first installation), with an exclusive create that never overwrites.
- **Rationale**: FR-005 for every outcome, including a killed process, which today's in-process restore (`PRESERVED`) cannot cover.

## Unresolved

None. Every Technical Context item is decided above.
