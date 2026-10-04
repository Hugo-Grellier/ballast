---

description: "Task list for one-command CLI install and `ballast doctor`"
---

# Tasks: One-command CLI install and `ballast doctor`

**Input**: Design documents from `specs/12-cli-install-doctor/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md)

**Risk**: R2. The plan needs explicit human approval before implementation starts. The two ADRs (T002, T003) record decisions the human approves with the plan. Get approval for any change to the release workflow's permissions, the install line, or what doctor executes before you make it.

**Acceptance evidence**: Every behavior acceptance criterion (AC-001 to AC-016) and every testable success criterion has a test or explicit verification task citing its ID. See the [traceability table](#acceptance-traceability). Tests run offline under the fast gate. Fake releases are served from `file://` URLs. Missing prerequisites are simulated by a controlled `PATH` of stub executables. Read-only behaviour is proven by before/after digest snapshots.

**Organization**: Tasks are grouped by user story. Tasks that edit the same file are serialized through explicit dependencies, even when the code they add is independent.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel with other ready tasks once its listed dependencies are done (it touches a different file).
- **[Story]**: US1 install, US2 machine diagnosis, US3 project readiness.
- Conventions: `tools/ballast` is the single-file global CLI. `tools/setup` and `tools/spec_workflow/launcher.py` belong to the pinned standard. Tests use `unittest` under `tests/`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Release configuration and the decision records the plan proposes.

- [x] T001 [P] Add `"extra-files": ["tools/ballast", "README.md"]` to the `.` package in `release-please-config.json` so the release PR bumps the `VERSION` line marked `# x-release-please-version` and the README install line's version (inside `<!-- x-release-please-start-version -->` … `<!-- x-release-please-end -->` block markers, T009) with the generic updater (research R3, plan.md)
- [x] T002 [P] After the human approves the plan, write `docs/adr/0001-cli-release-asset-install.md`. Record the decision: the CLI is distributed as the unchanged `tools/ballast` release asset `ballast` plus `ballast.sha256`, installed by the verify-then-`self-install` line in `contracts/install.md`, and published by a `publish-cli` job that alone has `contents: write`. Record the rejected alternatives (`curl | sh`, `uv tool install`/`pipx`, a raw-file link without a checksum) and the stated limit: a same-origin checksum detects corruption and truncation, not a compromised release (research R1, R2)
- [x] T003 [P] After the human approves the plan, write `docs/adr/0002-cli-standard-manifest.md`. Record the decision: each standard version declares `[cli] minimum` and `[doctor] probes` in `tools/cli.toml`. The CLI reads that file as data only, and it runs a probe only when the manifest declares it and only from the fetched standard directory. Record the rejected alternatives: reimplementing `_refusal` or the setup fingerprint in the CLI, and detecting capabilities from error output (research R8, `contracts/standard-manifest.md`)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The changes to `tools/ballast` that every story builds on: the version, the interpreter guard, a non-failing pin reader, and dispatch that does not require `ballast.toml`.

**⚠️ CRITICAL**: US1 and US2 changes to `tools/ballast` start only after this phase.

- [x] T004 In `tools/ballast`, add the version check right after `from __future__ import annotations` and before any other import (`tomllib` in particular). When `sys.version_info < (3, 11)`, write `ballast: needs Python 3.11 or newer (found X.Y)` to stderr and exit 1. Add `VERSION = "0.1.0"  # x-release-please-version` next to `REPOSITORY`. Keep `REPOSITORY = "Hugo-Grellier/ballast"` byte-identical, because `self-install` uses that line to recognise Ballast (research R3, R5; `contracts/install.md` interpreter guard)
- [x] T005 In `tools/ballast`, refactor the ref rule into `read_pin(root: Path) -> tuple[str | None, str | None]`, returning `(ref, None)` or `(None, error message)`. The messages stay the same as today's: `cannot read ballast.toml: <error>` and `ballast.toml needs [standard] ref, a tag or commit of the standard`. Make `pinned_ref` call `read_pin` and `fail` on an error, so every command and doctor share one rule (AC-013, research R8.1) (depends on T004)
- [x] T006 In `tools/ballast` `main`, dispatch `--version` (print `v` + `VERSION`, exit 0), `self-install` and `doctor` before `ballast.toml` is read or `BALLAST_STANDARD_DIR` is consulted. Add stub handlers for the last two, which later tasks fill in. Leave the `setup`/`trust`/`run`/`ledger` path unchanged. Update the usage message to list the new commands (FR-006, FR-019) (depends on T005)
- [x] T007 In `tests/test_ballast.py`, add `VersionTests`:
  - `ballast --version` prints `v` + `VERSION` and exits 0 in a directory with no `ballast.toml`, with `XDG_DATA_HOME` pointing to an empty temp directory, and with no fetch attempted (no standard directory is created) (FR-006).
  - The guard prints the required-version message and no `Traceback` when run with a patched `sys.version_info`: execute the file's source with a stub `sys` module whose `version_info` is `(3, 10)` (spec edge case).
  - The existing `ShimTests`, including `test_requires_a_valid_ref`, still pass unchanged (AC-013 message parity).

  (depends on T006)

**Checkpoint**: `ballast --version` works anywhere, and the existing commands behave exactly as before.

---

## Phase 3: User Story 1 - Install the Ballast CLI with one command (Priority: P1) 🎯 MVP

**Goal**: One documented line downloads a released `ballast`, verifies its SHA-256 and installs it atomically into `~/.local/bin`. No checkout is involved.

**Independent Test**: Under a temp `HOME`, run the README install line against a `file://` fake release. Then `ballast --version` prints the release version and the installed file is byte-identical to `tools/ballast`.

### Implementation for User Story 1

- [x] T008 [US1] In `tools/ballast`, implement `self-install [--dir DIR] [--force]` as specified in `contracts/install.md` and research R4:
  - Read its own bytes from `Path(__file__)`. Default `DIR` is `~/.local/bin`; create it with mode 0755 when absent.
  - Resolve `DIR`. Refuse and install nothing when the resolved directory or any parent contains a `.git` entry.
  - Classify the existing `DIR/ballast`:
    - A file containing `REPOSITORY = "Hugo-Grellier/ballast"` is a Ballast CLI. Take the previous version from `^VERSION = "(…)"`, or report "previous version unknown" when that line is absent.
    - Same version and same bytes: report `ballast vX.Y.Z is already installed at …` and exit 0.
    - A foreign file, a directory, or any symlink (DEC-0006): exit 2 with the contract message unless `--force` is given.
  - Write the new file with `NamedTemporaryFile(dir=DIR, delete=False)`, then `fchmod 0o755` and `fsync`; re-read the **temporary file** and compare its SHA-256 with the source bytes, and only then `os.replace` it over the target. Verification happens before the atomic rename, so any failure (including the digest read) leaves the previous file untouched; nothing is read after the rename. Test: a forced digest mismatch on the temporary file leaves the previous target byte-identical. Remove the temporary file in `finally`. On any I/O failure, exit 1 with `ballast: cannot install: <error>` and leave the previous file unchanged.
  - Print `installed …` or `replaced … with …` using the contract wording.
  - Report `PATH` membership against `BALLAST_CALLER_PATH`, falling back to `PATH`. When `DIR` is not on it, print the `export PATH="DIR:$PATH"` line.
  - Warn, naming Python 3.11, when `/usr/bin/python3` is missing or older than 3.11.

  (depends on T006)
- [x] T009 [P] [US1] Rewrite the install section of `README.md`. Lead with the install line copied exactly from `contracts/install.md`, inside a fenced block with a stable marker comment so tests can extract the single copy. Follow it with `ballast --version` and `ballast doctor`. Keep `install -m 0755 tools/ballast ~/.local/bin/ballast` only as the documented fallback for developing the standard (FR-001, FR-017). Write the line with a real version (`v0.1.0`), not the `vX.Y.Z` placeholder, followed by one sentence: "If the download fails with 404, that release predates the installer; use the developer fallback below." (the merge-to-release window; the operator's agent merges the Release Please PR immediately after this feature, see decisions.md), and wrap the fenced install block in `<!-- x-release-please-start-version -->` and `<!-- x-release-please-end -->` so the generic updater (with `README.md` in `extra-files`, T001) bumps the version inside the command; a test simulates the bump by applying the generic updater's semver substitution to the unmodified README and asserts the command now names the new version; the README-line test must not substitute a test tag before checking that the README carries a concrete version
- [x] T010 [P] [US1] In `.github/workflows/release-please.yml`:
  - Give the Release Please step `id: release`, and expose `release_created` and `tag_name` as job outputs.
  - Add a job `publish-cli` with `needs: release-please`, `if: needs.release-please.outputs.release_created == 'true'` and job-level `permissions: contents: write`. Leave the workflow default at `contents: read`.
  - The job checks out `needs.release-please.outputs.tag_name` and copies `tools/ballast` to `ballast`. It writes `sha256sum ballast > ballast.sha256`, verifies it with `sha256sum -c ballast.sha256`, and runs `gh release upload "$tag" ballast ballast.sha256` with `GH_TOKEN: ${{ github.token }}` on that step.

  (FR-002, FR-007, research R2)
- [x] T011 [P] [US1] Create `tests/test_release_workflow.py`. Parse `.github/workflows/release-please.yml` with PyYAML and assert:
  - The workflow default permission is `contents: read`.
  - The Release Please step has `id: release`, and the job exposes `release_created` and `tag_name` outputs.
  - `publish-cli` needs `release-please`, is gated on `needs.release-please.outputs.release_created == 'true'`, has `contents: write`, and checks out the tag.
  - The upload step sets `GH_TOKEN`, and the asset is copied from `tools/ballast` without modification (AC-002, build side).

  Also parse `release-please-config.json` and assert that `tools/ballast` is listed under `extra-files` (depends on T001, T010)
- [x] T012 [US1] In `tests/test_ballast.py`, add `InstallTests` and its harness:
  - The harness builds a fake release directory `releases/download/<tag>/{ballast,ballast.sha256}` from `tools/ballast` with a stamped test version. It extracts the install line from `README.md` by its marker, substitutes the tag, and replaces the `https://github.com/Hugo-Grellier/ballast/releases/download` base with the `file://` URL. It runs the line with `bash -c` under a temp `HOME` and a controlled `PATH`.
  - A fresh install creates `~/.local/bin/ballast`, which prints the release version with `--version` (AC-001, SC-001) and is byte-identical to the released file (AC-002).
  - Rerunning the same version is a no-op and reports `already installed` (FR-004).
  - With `~/.local/bin` absent from the caller's `PATH`, the output contains `export PATH="…/.local/bin:$PATH"` and the caller's `PATH` is unchanged after the line (AC-005).

  (depends on T007, T008, T009)
- [x] T013 [US1] In `tests/test_ballast.py` `InstallTests`, add the refusal and upgrade paths. Each failure case asserts that the previously installed file stays byte-identical and still runs `--version` (SC-004).
  - A corrupted asset prints `checksum mismatch` and installs nothing. A `ballast.sha256` that names another file also fails (AC-003).
  - An upgrade from a v0.1.0-style file without `VERSION` reports "previous version unknown". An upgrade from a versioned Ballast file reports previous → new (AC-004).
  - An unknown tag (missing `file://` path) and a truncated asset both leave the target unchanged.
  - A foreign file and a directory at the target are refused with exit 2. `--force` replaces the foreign file.
  - A simulated I/O failure exits 1 and leaves no temporary file in `DIR`.

  (depends on T012)
- [x] T014 [US1] In `tests/test_ballast.py` `InstallTests`, add the isolation tests (AC-006, FR-003). Run the install line from inside a temporary Git checkout that contains a planted `tools/ballast`, a `sitecustomize.py`, and shadow `curl`, `sha256sum` and `python3` executables prepended to `PATH`, with `TMPDIR` pointing inside the checkout. Assert that:
  - No planted file runs (each writes a sentinel when executed).
  - A shadow `sha256sum` that always succeeds cannot bypass verification of a corrupted asset.
  - The temporary directory is not created under the checkout.
  - `self-install --dir` pointing at a symlink into the checkout is refused, and nothing is written there.

  (depends on T013)

**Checkpoint**: The install line works end to end against a fake release, and every refusal leaves the previous install intact. US1 is shippable on its own.

---

## Phase 4: User Story 2 - See exact prerequisites before running a workflow (Priority: P1)

**Goal**: `ballast doctor [--json]` reports each machine prerequisite as passing, missing, unsupported or inconclusive. It names the gated commands and an exact remedy, and it exits 0 or 1. It never writes, downloads or prints a credential.

**Independent Test**: Remove one stub from the controlled `PATH`, run `ballast doctor`, and check that the report names that check, its gated commands and its remedy, and that the exit code is 1. Restore the stub and the check passes.

### Implementation for User Story 2

- [x] T015 [US2] In `tools/ballast`, add the report model from data-model.md:
  - A check record with `name`, `scope`, `status`, `gates`, `detail` and `remedy`. The statuses are `passing`, `missing`, `unsupported`, `inconclusive` and `skipped`.
  - The verdict is `ok` unless a check is `missing` or `unsupported`, otherwise `blocked`. `blocked` is the sorted union of the blocking checks' gates.
  - The human renderer follows `contracts/doctor-cli.md`: a `Machine` section, then a `Project` section, then a final line that reads `Everything Ballast needs is in place.` or `Blocked: <commands> (<n> gaps).`
  - The `--json` renderer emits `schema: 1`, `cli_version`, `project`, `standard`, `checks`, `verdict` and `blocked`.
  - `doctor` exits 0 for `ok`, 1 for `blocked`, and 2 with a usage message for an unknown option.
  - Outside a project, every project check is reported `skipped` with the detail "no ballast.toml found" (AC-011, FR-009, FR-013, FR-015).

  (depends on T008)
- [x] T016 [US2] In `tools/ballast`, add two helpers (research R8 executable resolution, R10, R11, R12):
  - A safe executable resolver: `shutil.which` against a filtered `PATH` that drops relative entries and any entry whose **resolved** path (`Path.resolve()`, following symlinks) lies inside the project root or any Git working tree (any ancestor with a `.git` entry, DEC-0005); the selected executable is also resolved and rejected when it lies there. Test: a `PATH` entry `/tmp/bin` symlinked to `<checkout>/bin` with a shadow `gh` is not executed. A program found only there is reported `missing`, with a note.
  - A probe runner that runs a resolved program with `stdin=DEVNULL` and `timeout=3`, with stdout and stderr captured and discarded, and with `PYTHONDONTWRITEBYTECODE=1` in its environment. It kills the child on timeout and returns `inconclusive` with "did not answer within 3 s".

  (depends on T015)
- [x] T017 [US2] In `tools/ballast`, add the module-level `MACHINE_CHECKS` table, the single source of the prerequisite list (FR-008, FR-018). It covers `python`, `cli-on-path`, `git`, `uvx`, `patch`, `linux`, `systemd-user`, `systemd-run`, `specify`, `agent-cli` and `gh`, with the probes and gates from research R7 and an exact remedy for each. Rules:
  - `python` probes `/usr/bin/python3 -I -S` for version ≥ 3.11 through a patchable module constant.
  - `systemd-run` must actually start a transient scope, running `/usr/bin/true` with `PATH=/usr/bin:/bin`; when the program is present but the scope definitely fails to start, it is `unsupported` and blocks; a timeout is `inconclusive` (DEC-0004).
  - `gh` uses only the exit code of `gh auth status`.
  - When `linux` is not passing, `systemd-user` and `systemd-run` are `unsupported` with "headless steps need Linux".

  Run the local probes concurrently in a `ThreadPoolExecutor` (AC-008, AC-009, AC-010, FR-014, FR-016) (depends on T016)
- [x] T018 [US2] In `tools/ballast`, add the `network` check (research R7, R10):
  - Inside a project whose pinned ref (read with `read_pin`) is not fetched, send an HTTPS `HEAD` with `urlopen(..., timeout=3)` to the exact `ARCHIVE` URL `ballast setup` fetches for that ref. Also send one `HEAD` per other host setup contacts: the Spec Kit source and extension archives, and the package index `uvx` resolves from.
  - Report each host separately, and list any host not probed as `unverified` in the detail.
  - Report `skipped` when the version is already fetched, when outside a project, or when the pin is invalid.
  - Run each probe in its own `threading.Thread(daemon=True)` that writes to a queue. The main thread waits on the queue with a 5 s overall deadline, so a stalled resolver yields `inconclusive` without holding process exit.
  - Never download a body (FR-011, FR-016).

  (depends on T017)
- [x] T019 [US2] In `README.md`, under the install section, add a short prerequisite summary. Name every machine check from `MACHINE_CHECKS` by its exact identifier and state that `ballast doctor` is the authoritative list (FR-017, FR-018) (depends on T009, T018)

### Tests for User Story 2

- [x] T020 [US2] Create `tests/test_doctor.py` with its harness and add the AC-007 test (depends on T018).
  - The harness loads `tools/ballast` as a module, as `tests/test_ballast.py` does, and builds a stub bin directory with a working stub for every probed program (`git`, `uvx`, `patch`, `systemctl`, `systemd-run`, `specify`, `claude`, `codex`, `gh`, and a Ballast-identified `ballast`). It runs doctor both as a subprocess (controlled `PATH`, temp `HOME`, `XDG_DATA_HOME`, `XDG_STATE_HOME`) and in-process, with patched `sys.platform`, `PYTHON` and `urllib.request.urlopen`. The urlopen fake records each request's method.
  - Every doctor invocation goes through a wrapper that takes a recursive SHA-256 snapshot of the project, `XDG_DATA_HOME`, `XDG_STATE_HOME` and `~/.local/bin` before and after, and asserts they are equal (AC-012, SC-005).
  - AC-007 test: with every stub present, every check is `passing` and doctor exits 0 with `Everything Ballast needs is in place.`
- [x] T021 [US2] In `tests/test_doctor.py`, add one `subTest` per machine check (AC-008, SC-003). Remove that check's prerequisite: delete the stub, patch `PYTHON` to a missing path for `python`, and make the urlopen fake fail for `network`. Assert:
  - The check is reported `missing` or `unsupported` by name, with its gates (for example `ballast setup` for `patch` and `uvx`) and a non-empty remedy.
  - The human report's final line names the blocked commands, and the exit code is 1.

  Then restore the prerequisite and assert the check is `passing` (depends on T020)
- [x] T022 [US2] In `tests/test_doctor.py`, add the host and credential tests. Each asserts that every remedy is present:
  - Patched `sys.platform = "darwin"`: `linux` fails and both `systemd-*` checks are `unsupported` with "headless steps need Linux", while `git`, `uvx`, `patch`, `gh` and `agent-cli` are still reported (AC-009).
  - A `systemctl` stub that exits non-zero: `systemd-user` is not passing and gates headless `ballast run` (AC-009).
  - No `claude` or `codex` stub: `agent-cli` is missing and gates the agent steps (AC-010).
  - A `gh` stub whose `auth status` exits 1 after printing `ghp_FAKEtoken0123456789` to stdout and stderr: `gh` is missing with remedy `gh auth login`, and the token string is absent from both the human and the `--json` output (AC-010, FR-014).

  (depends on T021)
- [x] T023 [US2] In `tests/test_doctor.py`, add three tests:
  - Outside a project: every machine check is reported, every project check is `skipped` with "no ballast.toml found", and the exit code reflects machine checks only (AC-011).
  - The urlopen fake recorded only `HEAD` requests, and no file was created anywhere under the snapshot roots (AC-012, FR-011).
  - `--json` output passes a stdlib structural validation against `specs/12-cli-install-doctor/contracts/doctor-report.schema.json`: required keys, `additionalProperties`, enums, the `cli_version` pattern, and a non-empty `remedy` whenever the status is `missing`, `unsupported` or `inconclusive`. Unknown options exit 2 (FR-015).

  (depends on T022)
- [x] T024 [US2] In `tests/test_doctor.py`, add the time-bound and isolation tests:
  - A `systemctl` stub that sleeps 30 s: `systemd-user` is `inconclusive` with "did not answer within 3 s" and the whole run finishes in under 10 s (FR-016, SC-005).
  - Patch `socket.getaddrinfo` to block forever for a project whose pin is not fetched: `network` is `inconclusive` and the subprocess exits within the deadline (FR-016).
  - Shadow `gh` and `systemctl` placed inside the project checkout and prepended to `PATH`, plus a relative `PATH` entry, are never executed (sentinel file absent), and they are reported as found only in the checkout (FR-012).

  (depends on T023)
- [x] T025 [US2] In `tests/test_doctor.py`, assert that every `name` in `MACHINE_CHECKS` appears in the `README.md` prerequisite summary and that the summary points to `ballast doctor` (FR-018) (depends on T019, T024)

**Checkpoint**: `ballast doctor` gives a complete, read-only machine report, both human and JSON. US2 works without US3.

---

## Phase 5: User Story 3 - See the project's Ballast readiness (Priority: P2)

**Goal**: Inside a project, doctor reports the pin, whether that version is fetched, the CLI minimum, setup freshness and trust readiness, each with the next command. The last two come from read-only probes owned by the pinned version.

**Independent Test**: In a project whose pinned version is not fetched, doctor names `ballast setup`. With the version fetched but no trust baseline, it names `ballast trust`.

### Implementation for User Story 3

- [x] T026 [P] [US3] In `tools/spec_workflow/launcher.py`, add `status --json`, handled in `main` before the `.ballast/spec_workflow/run.py` presence check. It prints `{"installed": <run.py is a file>, "refusal": null | "<_refusal(root) text>"}` and exits 0 whenever it can report. When not installed, it reports `refusal: null`. It must never create `state_dir(root)` or write any file. Mention `status --json` in the module docstring (`contracts/standard-manifest.md` launcher-status)
- [x] T027 [P] [US3] In `tests/test_spec_workflow.py`, test `launcher.py status --json`. Cover these states:
  - Not installed: `installed: false`.
  - Installed with no baseline: refusal "no trusted baseline…".
  - After `trust`: `refusal: null`.
  - After changing a protected input: "workflow inputs changed…".
  - With `BALLAST_TAMPERED` present, and with an in-progress marker: the matching reasons.

  For every state, assert that the project and the state directory are unchanged (snapshot) and that the state directory is not created when absent (AC-015 probe side) (depends on T026)
- [x] T028 [P] [US3] In `tools/setup`, add a `--check` flag. It compares `self.stamp` with `self.fingerprint()` and checks that the installed outputs the stamp promises exist (`.ballast/spec_workflow/run.py`, `.ballast/feature_intake.py`, `.specify/workflows/ballast-feature/workflow.yml`); it prints `current`, `stale`, `absent` or `incomplete: <path>`, and exits 0 for current or 1 otherwise. It skips `check_ignored`, `remove_installed` and every install step, and writes nothing. Also append `; run \`ballast doctor\` for details` to the existing missing-`uvx`/`patch` error message (`contracts/standard-manifest.md` setup-check, research R13)
- [x] T029 [P] [US3] In `tests/test_setup.py`, test `setup --check`. It exits 1 with `absent` before setup, 0 after a stamp matching the fingerprint is written, 1 with `stale` after the fingerprint input changes, and 1 with `incomplete: .ballast/spec_workflow/run.py` after that file is deleted while the stamp stays valid. In every case the project is unchanged (snapshot), and no network access is attempted (patched `urlretrieve` raises). Also assert that the missing-`uvx`/`patch` message mentions `ballast doctor` (AC-014 probe side, FR-019) (depends on T028)
- [x] T030 [US3] Create `tools/cli.toml` with `[cli] minimum = "0.1.0"` and `[doctor] probes = ["setup-check", "launcher-status"]`. Add a comment: bump `minimum` only when this standard relies on a CLI behaviour added after it (`contracts/standard-manifest.md`). Confirm that `tools/setup` does not copy this file into any project path (BL-INV-001) (depends on T026, T028)
- [x] T031 [US3] In `tools/ballast`, add the project checks in order: `ballast-toml`, `standard-fetched`, `cli-version`, `setup-current` and `trust` (research R8, data-model dependencies).
  - `ballast-toml` uses `read_pin`. On a parse error or a bad ref it reports `missing` with the same message, the later project checks are `skipped`, and the machine checks still run.
  - `standard-fetched` checks `standard_dir(ref)` and has remedy `ballast setup`. With `BALLAST_STANDARD_DIR` set, it reports `using local standard <path>` and sets `standard.local = true`. Against a local standard, it reads files but executes nothing, so `setup-current` and `trust` are `inconclusive` with "local standard: probes not executed".
  - Before any probe runs, resolve the standard directory and each probe file. When either is inside the project root or the enclosing Git working tree, or under a directory containing `.git`, run no probe and report `inconclusive` with "standard directory resolves into a working tree".
  - `cli-version` parses the fetched `tools/cli.toml` with `tomllib` as data. When `minimum` is above `VERSION`, the check is `missing` and the remedy is the README install line with `v<minimum>`. When `minimum` is not a published release, say that no suitable published CLI exists and that the project should pin a release. A parse error or bad value makes it `inconclusive` and the probes count as absent.
  - `setup-current` runs `/usr/bin/python3 -I -S <standard>/tools/setup --project ROOT --check` only when the manifest lists `setup-check`. Otherwise it is `inconclusive` with "freshness not checked: pinned version predates doctor".
  - `trust` runs `/usr/bin/python3 -I -S <standard>/tools/spec_workflow/launcher.py status --json` in ROOT only when the manifest lists `launcher-status`, and maps the result per the contract table. Its remedy is "review the checkout, then run `ballast trust`", with the `discard-runs` or tamper-marker variant where it applies.
  - When `standard-fetched` fails, `cli-version`, `setup-current` and `trust` are `skipped` with "after `ballast setup`".

  (depends on T018, T030)

### Tests for User Story 3

- [x] T032 [US3] In `tests/test_doctor.py`, add the project tests. The fixture copies this repository's `tools/` tree into `XDG_DATA_HOME/ballast/standard/<ref>/` so the real probes run.
  - Missing `ballast.toml` ref, invalid refs (`../x`, `-x`, `a/b`) and an unparsable `ballast.toml`: `ballast-toml` reports the same text as `pinned_ref`, and the machine checks are still present (AC-013, edge case).
  - Pinned version not fetched: `standard-fetched` is `missing` with remedy `ballast setup`, and the later checks are `skipped` (AC-014).
  - Fetched with an absent or stale setup stamp: `setup-current` is `missing` with remedy `ballast setup` (AC-014).
  - Set up with no baseline: `trust` reports the launcher will refuse, with remedy review then `ballast trust`. After the test runs the launcher's `trust`, `trust` is `passing`. Doctor itself never creates the baseline (AC-015).
  - A fetched `tools/cli.toml` whose minimum is above `VERSION`: `cli-version` is `missing` with the install line for that minimum, for both a tag pin and a commit pin (AC-016).

  (depends on T025, T031)
- [x] T033 [US3] In `tests/test_doctor.py`, add the compatibility and execution-boundary tests (FR-012, research R8):
  - A fetched standard in the v0.1.0 layout (no `tools/cli.toml`) whose `tools/setup` and `launcher.py` write a sentinel when executed: no sentinel appears, and `setup-current` and `trust` are `inconclusive` with a remedy.
  - A malformed `tools/cli.toml`: `cli-version` is `inconclusive` and no probe runs.
  - `BALLAST_STANDARD_DIR=$PWD` in a checkout with sentinel tools: nothing executes, and the report says `using local standard`.
  - A fetched directory that is a symlink into the checkout, and an `XDG_DATA_HOME` inside the checkout: nothing executes, and the checks report "resolves into a working tree".

  (depends on T032)

**Checkpoint**: Doctor names the next command (`setup` or `trust`) for every project state, and it never executes from a writable checkout.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [x] T034 In `tools/ballast`, append `; run \`ballast doctor\` for details` to the existing "is not fetched", "cannot read ballast.toml" and "has no launcher" failures, without changing command dispatch. Update the module docstring to describe `--version`, `self-install` and `doctor`, and to describe the install line as the primary install path (FR-017, FR-019, research R13) (depends on T031)
- [x] T035 In `tests/test_ballast.py`, add FR-019 regressions against a fixture project pinned to `v0.1.0`, with a fetched standard built from the v0.1.0 layout (no `tools/cli.toml`, no probes) (FR-019). Assert that:
  - `ballast setup` with a stubbed `tools/setup`, `ballast trust`, the `ballast run start` refusal path before trust, and `ballast ledger report` produce the same exit codes and outputs as before. The only allowed difference is the doctor hint on the failure messages.
  - `test_requires_a_valid_ref` and `test_only_setup_fetches` still match.

  (depends on T014, T034)
- [x] T036 [P] Review `README.md` and the `tools/ballast` docstring against `contracts/install.md` and `contracts/doctor-cli.md` with the [documentation review](../../.agents/skills/ballast-documentation-review/SKILL.md). Check that the install line, the prerequisite summary, the developer fallback and the `ballast doctor` usage agree, and that every relative link resolves (FR-017) (depends on T019, T034)
- [x] T037 Run the fast gate: `uvx ruff check && uvx ruff format --check` and `uv run --no-project --python 3.13 --with pyyaml python -m unittest tests/test_*.py`. Fix failures without weakening tests. Record the exact commands and results for the PR (depends on T011, T027, T029, T033, T035, T036)
- [x] T038 Run the full local gate on a Linux host with a systemd user session, the Codex CLI and the Spec Kit CLI, so the four CI-skipped tests also run. This is required because `tools/spec_workflow/launcher.py` changed. Also time `ballast doctor` on that host, which must stay under 10 s (SC-005). Record the results for the PR (depends on T037)
- [x] T039 Perform the manual end-to-end run from `quickstart.md` on a scratch project, as `docs/policies/project/testing.md` requires for `tools/ballast` and `tools/setup` changes. Run, in order:
  - `install -m 0755 tools/ballast ~/.local/bin/ballast`, then `ballast --version`.
  - `BALLAST_STANDARD_DIR=$PWD ballast doctor`, which names `ballast setup`.
  - `ballast setup`, then `ballast doctor`, which names `ballast trust`.
  - `ballast trust`, then `ballast doctor`, which exits 0.
  - `ballast ledger report`, and a clean `git status` apart from the project's own files.

  This is SC-002 evidence on the qualified host. Record the exact commands and output for the PR (depends on T037)
- [x] T040 Run the reviews the [review matrix](../../docs/policies/workflow.md#review-triggers) selects for this R2 change, with findings written under `specs/12-cli-install-doctor/reviews/`:
  - [security review](../../.agents/skills/ballast-security-review/SKILL.md): install line, `self-install` target resolution, doctor executable resolution and probe execution, release job permissions, credential output.
  - [engineering review](../../.agents/skills/ballast-engineering-review/SKILL.md).
  - [test review](../../.agents/skills/ballast-test-review/SKILL.md): the AC traceability below.
  - Resolve or record every finding.

  (depends on T038, T039)
- (workflow step, not a task — DEC-0002) T041 Resolve any open `specs/12-cli-install-doctor/decisions.md` entries with the human. Then run Spec Kit converge and the [spec reconciliation](../../.agents/skills/ballast-spec-reconciliation/SKILL.md) for this significant feature, and update `spec.md`, `plan.md` and `tasks.md` for accepted changes (depends on T040)
- (post-release PR checklist, not a task — DEC-0002) T042 After merge and the first release that carries this feature, verify the release:
  - Download the release's `ballast` and `ballast.sha256` and confirm the hash matches and the file is byte-identical to `tools/ballast` at the tag (`publish-cli` postcondition).
  - Run the README install line on a clean user account and confirm `ballast --version` (SC-001).
  - Follow only the README and doctor remedies to a successful `ballast setup` in a fresh project (SC-002).

  Record this in the PR as post-release verification, because no asset exists before that release (depends on T041)

---

## Acceptance Traceability

| Criterion | Evidence task(s) |
| --- | --- |
| AC-001 | T012 |
| AC-002 | T012 (install side), T011 (release job copies `tools/ballast` unchanged), T042 |
| AC-003 | T013 |
| AC-004 | T013 |
| AC-005 | T012 |
| AC-006 | T014 |
| AC-007 | T020 |
| AC-008 | T021 |
| AC-009 | T022 |
| AC-010 | T022 |
| AC-011 | T023 |
| AC-012 | T020 (snapshot on every doctor run), T023 |
| AC-013 | T007, T032 |
| AC-014 | T029, T032 |
| AC-015 | T027, T032 |
| AC-016 | T032 |
| FR-006 | T007 |
| FR-012 | T024, T033 |
| FR-014 | T022 |
| FR-015 | T023 |
| FR-016 | T024 |
| FR-018 | T025 |
| FR-019 | T029, T035 |
| SC-001 | T012 (offline), T042 (real release) |
| SC-002 | T039 (developer install), T042 (README install) |
| SC-003 | T021 |
| SC-004 | T013, T014 |
| SC-005 | T020, T024, T038 |
| Edge cases | T007 (old interpreter), T013 (interrupted, unknown version, foreign target), T024 (hang), T032 (unparsable `ballast.toml`), T033 (`BALLAST_STANDARD_DIR`) |

---

## Execution Wave DAG

Each wave starts when every task it depends on is done. Tasks in one wave can run in parallel. The long tail through `tests/test_doctor.py` is serialized only because those tasks edit the same file.

| Wave | Tasks | Notes |
| --- | --- | --- |
| 1 | T001, T002, T003, T004, T009, T010, T026, T028 | Config, ADRs (after plan approval), the version and guard, README install section, release job, and both read-only probes |
| 2 | T005, T011, T027, T029, T030 | `read_pin`, workflow test, probe tests, manifest |
| 3 | T006 | Dispatch |
| 4 | T007, T008 | Version tests; `self-install` |
| 5 | T012, T015 | Install tests begin; doctor report model |
| 6 | T013, T016 | |
| 7 | T014, T017 | US1 complete |
| 8 | T018 | Machine checks complete |
| 9 | T019, T020, T031 | README summary; doctor tests begin; project checks |
| 10 | T021, T034 | |
| 11 | T022, T035, T036 | |
| 12 | T023 | |
| 13 | T024 | |
| 14 | T025 | US2 complete |
| 15 | T032 | |
| 16 | T033 | US3 complete |
| 17 | T037 | Fast gate |
| 18 | T038, T039 | Full gate, manual end-to-end |
| 19 | T040 | Reviews |
| 20 | T041 | Converge and reconciliation |
| 21 | T042 | After release only |

```text
T001 ─► T011 ◄─ T010
T004 ─► T005 ─► T006 ─► T007 ─┐
                       └► T008 ─┼► T012 ─► T013 ─► T014 ─────────────────┐
T009 ───────────────────────────┘                                        │
T008 ─► T015 ─► T016 ─► T017 ─► T018 ─► T020 ─► T021 ─► T022 ─► T023 ─► T024 ─► T025 ─► T032 ─► T033
T009 + T018 ─► T019 ─► T025                                              │
T026 ─► T027      T026 + T028 ─► T030 ─► T031 (also after T018) ─► T032  │
T028 ─► T029      T031 ─► T034 ─► T035 (after T014) ◄────────────────────┘
T019 + T034 ─► T036
{T011,T027,T029,T033,T035,T036} ─► T037 ─► {T038,T039} ─► T040 ─► T041 ─► T042
```

## Dependencies & Story Order

- **Setup (Phase 1)**: No dependencies. The ADRs wait for human approval of the plan, not for code.
- **Foundational (Phase 2)**: Blocks the `tools/ballast` work of every story.
- **US1 (P1)**: Needs Phase 2 only. It is the MVP.
- **US2 (P1)**: Needs Phase 2. Its `tools/ballast` work follows `self-install` (T008) only because both edit the same file; it does not need US1 behaviour.
- **US3 (P2)**: The probes (T026–T030) can start in wave 1. The project checks (T031) build on the report model and runner from US2.
- **Polish**: Needs all stories. T042 runs only after a release.

## Implementation Strategy

1. **MVP**: Phases 1–3 (US1). The CLI can be installed with one verified command, and `--version` works. This is releasable alone. `doctor` stays a stub until US2.
2. **Increment 2**: Phase 4 (US2). Machine diagnosis with JSON output.
3. **Increment 3**: Phase 5 (US3). Project readiness through the manifest-gated read-only probes.
4. **Close-out**: Phase 6. Gates, the manual end-to-end run, R2 reviews, reconciliation, then post-release verification.

Stop at any checkpoint to validate that story on its own. Any discovery that conflicts with the approved spec or plan goes to `decisions.md` for human resolution before work continues. Run the README command exactly as committed, with no version substitution, on a clean account after the release, and record the output in the PR.

---

## Phase 7: Convergence

- [x] T043 In `.github/workflows/release-please.yml` `publish-cli`, after `gh release upload`, download the release's `ballast` and `ballast.sha256` (`gh release download "$TAG" -p ballast -p ballast.sha256 -D uploaded`), and fail the job unless `uploaded/ballast` is byte-identical to `tools/ballast` and its SHA-256 equals the value in `uploaded/ballast.sha256`. Extend `tests/test_release_workflow.py` to assert that this step runs after the upload. This changes the release workflow, so get human approval first (R2) per plan: Constitution Check principle 5, "The release job checks the uploaded asset's hash" (partial)
- [x] T044 [US3] In `tools/ballast` `project_checks`, when `BALLAST_STANDARD_DIR` names a directory that does not exist or has no `tools/` directory, report `standard-fetched` as `missing` with the path and the remedy "set BALLAST_STANDARD_DIR to a checkout of the standard, or unset it", not `passing`. Add a test to `tests/test_doctor.py` per spec edge case `BALLAST_STANDARD_DIR` and FR-010 (partial)
- [x] T045 [US1] When a download fails, make the install line print `ballast: cannot download $v from $u; nothing installed` to stderr, because over HTTPS curl's own 404 message does not name the version. Update `contracts/install.md`, `INSTALL_LINE` in `tools/ballast` and the README block together. In `tests/test_ballast.py`, assert in the `unknown version` subtest that stderr names the requested tag. This changes the install line, so get human approval first (R2) per spec edge case "requested version does not exist… names the version" (partial)
- [x] T046 [US2] In `tools/ballast` `_check_agent`, keep the `resolve_program` note when neither `claude` nor `codex` resolves, so an agent CLI found only in a checkout or another Git working tree is reported with "ignored … found only in the checkout". Add a `tests/test_doctor.py` case per T016, "a program found only there is reported `missing`, with a note" (partial)
