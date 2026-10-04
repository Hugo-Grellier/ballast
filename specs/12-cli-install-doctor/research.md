# Research: One-command CLI install and `ballast doctor`

Each entry gives the decision, the reason, and the alternatives that were rejected.

## R1. Install channel (FR-007)

- **Decision**: As the spec states. The release asset `ballast` (the byte-identical `tools/ballast` at the tag) and `ballast.sha256` are fetched into `mktemp -d`, checked with the hash comparison in [contracts/install.md](contracts/install.md) and installed by `python3 -I -S "$d/ballast" self-install`.
- **Rationale**: The operator runs only a file that passed the check. The installed file is the reviewed launcher itself, so AC-002 is byte identity, and its `-I -S` shebang isolation survives. The repository stays fixed (BL-INV-004).
- **Alternatives**: `curl | sh`, `uv tool install`/`pipx` (the spec rejects both). A detached signature (cosign or minisign) is out of scope per the spec's assumptions. A checksum fetched from the same origin protects against corruption and truncation, not against a compromised release; ADR-0001 records this limit.

## R2. How the release publishes the asset

- **Decision**: Add a `publish-cli` job to `release-please.yml`, gated on `needs.release-please.outputs.release_created` (see plan.md). It checks out `tag_name`, copies `tools/ballast` to `ballast`, writes `sha256sum ballast > ballast.sha256`, runs the hash comparison in [contracts/install.md](contracts/install.md) as a postcondition, then runs `gh release upload "$tag" ballast ballast.sha256`. Only that job gets `permissions: contents: write`; the workflow default stays `contents: read`.
- **Rationale**: Release Please already creates the tag and release. One extra job keeps everything in one pipeline, and the asset is built from the tagged tree.
- **Alternatives**: Linking to the raw file at the tag (`raw.githubusercontent.com/.../vX.Y.Z/tools/ballast`) with no asset. This needs no workflow change, but no checksum is published with the release, so FR-002 fails. Attaching assets by hand: error-prone and not reproducible.

## R3. CLI version source

- **Decision**: `VERSION = "X.Y.Z"  # x-release-please-version` in `tools/ballast`, listed under `extra-files` in `release-please-config.json` (generic updater). `ballast --version` prints `v` followed by `VERSION`, needs no project and no network (FR-006), and is handled before `ballast.toml` is read.
- **Rationale**: The release PR then bumps the version in the same commit that gets tagged, so the asset at `vX.Y.Z` reports `vX.Y.Z` (AC-001).
- **Alternatives**: Deriving the version from Git at run time (there is no checkout at run time). Stamping it at upload (this breaks byte identity with `tools/ballast` at the tag, AC-002).

## R4. Atomic replace, identity and foreign targets (FR-004, AC-004, edge cases)

- **Decision**: `self-install` reads its own bytes from `Path(__file__)`. It creates `DIR` (default `~/.local/bin`) with mode 0755 if needed. Before writing it resolves `DIR` (`Path.resolve()`) and refuses, installing nothing, when the resolved directory or any parent contains a `.git` entry, so a symlinked install directory can never place the CLI inside a working tree (AC-006, FR-003). Test: a symlinked `~/.local/bin` pointing into a checkout is refused. It writes a temporary file in `DIR` (`NamedTemporaryFile(dir=DIR, delete=False)`), `fchmod 0o755` and `fsync`, re-reads the temporary file and compares its SHA-256 with the source bytes, and only then calls `os.replace` onto `DIR/ballast`; nothing is read after the rename, so any failure leaves the previous target untouched. Classification of an existing target:
  - It contains the line `REPOSITORY = "Hugo-Grellier/ballast"`, so it is a Ballast CLI. The previous version comes from `^VERSION = "(…)"`. If that line is absent (for example the v0.1.0 hand install), the output says "previous version unknown".
  - Same version and same bytes: no-op, reported as success.
  - Not a Ballast CLI, a directory, or any symlink (even one to a Ballast file, DEC-0006): refuse with exit 2 unless `--force` is given; with `--force`, a symlink is replaced by a regular file and never followed.
- **Rationale**: The replace is atomic on one filesystem. On any earlier failure the old file is untouched, and the temporary file is removed in `finally`.
- **Alternatives**: `shutil.copy` onto the target (not atomic). A marker comment (the existing constant already identifies Ballast reliably).

## R5. Interpreter guard

- **Decision**: Right after `from __future__ import annotations`, check `sys.version_info < (3, 11)` before importing `tomllib` and exit with `ballast: needs Python 3.11 or newer (found X.Y)`. `self-install` also warns when `/usr/bin/python3`, the shebang interpreter, is missing or too old, because the installed command would not run.
- **Rationale**: This covers the "interpreter too old, no traceback" edge case for both the install line and the installed command.

## R6. Check table as the single source (FR-008, FR-018)

- **Decision**: One module-level tuple `MACHINE_CHECKS` in `tools/ballast`. Each entry has a name, a probe function, the gated commands and a remedy template. The README carries a short summary and points to `ballast doctor`. A test asserts that every check name appears in the README summary, so the two cannot drift silently.
- **Alternatives**: A separate data file (`tools/ballast` must stay a single file to be a one-asset install). Generating the README (not justified for about 12 entries).

## R7. Machine checks

| Check | Probe | Gates |
| --- | --- | --- |
| `python` | `/usr/bin/python3` exists and reports ≥ 3.11 (`-I -S -c` printing `sys.version_info`) | every command |
| `cli-on-path` | `shutil.which("ballast")` resolves to a Ballast CLI | every command, from any directory |
| `git` | `which git` | setup, run, intake |
| `uvx` | `which uvx` | setup |
| `patch` | `which patch` | setup |
| `network` | HTTPS `HEAD` to the exact archive URL `ballast setup` fetches for the pinned ref (the `https://github.com/<repository>/archive/<commit>.tar.gz` URL from `tools/setup`, 3 s), so reachability is tested on the endpoint setup uses, plus one `HEAD` per other host setup contacts (the Spec Kit source and extension archives on `github.com`, and the package index `uvx` resolves from); each host is reported separately, and any host not probed is listed as `unverified`; run only when the project's pinned version is not fetched, otherwise reported as `skipped` | setup (first fetch) |
| `linux` | `sys.platform == "linux"` | run (headless) |
| `systemd-user` | `systemctl --user show --property=Version`, exit 0 (3 s) | run (headless) |
| `systemd-run` | `systemd-run --user --scope --quiet --collect --setenv=PATH=/usr/bin:/bin /usr/bin/true` exits 0 (3 s), with the probe's own environment `PATH` also set to `/usr/bin:/bin`: a transient scope actually starts. Presence alone is reported as `inconclusive`. No file is written. | run (headless) |
| `specify` | `which specify` | run |
| `agent-cli` | `which claude` or `which codex` | run agent steps |
| `gh` | `which gh` and `gh auth status` exit 0, output discarded (3 s) | intake, PR steps |

FR-011 is read as forbidding writes to files and persistent state, not every runtime effect: the `systemd-run` probe starts one transient scope with `--collect`, which writes no file and leaves no persistent unit or state behind once `/usr/bin/true` exits (DEC-0003). A scope that definitely fails to start is `unsupported` and blocks; a probe that times out stays `inconclusive`.

When `linux` fails, the `systemd-*` checks are reported as `unsupported` with the reason "headless steps need Linux". Host-independent checks still run (AC-009). The remedies are exact commands or settings, for example `uv` install docs and `loginctl enable-linger "$USER"`, `gh auth login`. The remedy text is listed in [data-model.md](data-model.md).

## R8. Project checks and the read-only probes (FR-010, AC-013–016)

- **Decision**: In order:
  1. `ballast-toml`: parse and validate the ref. This reuses the existing ref rule, refactored into `read_pin(root) -> (ref | None, error | None)`, which `pinned_ref` also calls (same rules, AC-013).
  2. `standard-fetched`: does `standard_dir(ref)` exist? Before any probe executes, doctor resolves the standard directory and each probe file (`Path.resolve()`); if either lies inside the project root or the enclosing Git working tree, or under any directory containing a `.git` entry, the probes are not run and the checks report `inconclusive` ("standard directory resolves into a working tree"). Test: a fetched directory symlinked to the checkout, and an `XDG_DATA_HOME` inside the checkout, execute nothing. Remedy: `ballast setup`. With `BALLAST_STANDARD_DIR` set, the local directory is reported, and checks against it are data-only: doctor reads files there but never executes anything from it, so `setup-current` and `trust` report `inconclusive` with the reason "local standard: probes not executed" (FR-012).
  3. `cli-version`: if the fetched `tools/cli.toml` has `[cli] minimum` above `VERSION`, the check fails. The remedy is the install line for the release named by `minimum` itself (a `vX.Y.Z` tag that exists, because the manifest is only bumped at or after that release), for both tag and commit pins (AC-016). Doctor cannot know offline whether `minimum` is published, so it always gives the install line for `minimum` and adds: "if this release is not published yet, the pin needs an unreleased CLI: pin a release instead". Test: a commit pin with a `minimum` above `VERSION` prints both. Tests: a commit pin and a tag pin older than `minimum` both produce the install line for `minimum`.
  4. `setup-current`: if the manifest lists the `setup-check` probe, run `/usr/bin/python3 -I -S <standard>/tools/setup --project ROOT --check` (exit 0 current, 1 stale or absent). Otherwise report `inconclusive` (file presence does not prove the stamp is current) with the note "freshness not checked: pinned version predates doctor".
  5. `trust`: if the manifest lists the `launcher-status` probe, run `/usr/bin/python3 -I -S <standard>/tools/spec_workflow/launcher.py status --json` in ROOT. It reports `refusal: null | "<reason>"`; the remedy is "review the checkout, then `ballast trust`" (AC-015). Otherwise the check is `inconclusive`, with that same remedy.
  6. Outside a project (no `ballast.toml` in cwd): every project check is reported as `skipped`, with the reason "no ballast.toml found" (AC-011).
- **Executable resolution (plan review; broadened by DEC-0005)**: programs and resolved `PATH` entries inside *any* Git working tree are rejected, and the search continues on later entries. Known limitation: on a machine whose home directory is itself a Git working tree (a dotfiles repository), tools under `~/.local/bin` are reported `missing`, and the note says why. every external program doctor runs (`git`, `gh`, `systemctl`, `systemd-run`, `specify`, agent CLIs) is resolved with `shutil.which` against a filtered `PATH` that drops relative entries and any entry inside the project root or any Git working tree; a program found only there is reported `missing` with a note. Tests: shadow `gh` and `systemctl` in the checkout on `PATH` are not executed; `BALLAST_STANDARD_DIR=$PWD` executes nothing from the checkout.
- **Rationale**: The trust comparison and the setup fingerprint stay with their owners (no second source of truth). Gating probes on the manifest means an older pinned version is never sent an unknown flag; v0.1.0's `tools/setup` would reject one through argparse anyway, but doctor never relies on that. Only files under the fetched standard directory execute (BL-INV-002).
- **Alternatives**: Reimplementing `_refusal` and `fingerprint` in the CLI (duplicates logic and drifts per version). Parsing error output from old versions to detect capability (fragile).

## R9. Statuses, verdict and exit code (FR-009, FR-013)

- **Decision**: Check statuses are `passing`, `missing`, `unsupported`, `inconclusive`, plus `skipped` for a check that does not apply in this context. AC-011 uses "skipped", so this records how the spec's wording is read. The exit code is 1 when any check is `missing` or `unsupported`, otherwise 0. The final line names the verdict and the commands that are blocked. `inconclusive` never fails the run but is always shown with a remedy.
- **Rationale**: Under this rule, the spec's "a command the operator can otherwise reach" condition is met whenever any check blocks a command: on an unsupported host, `ballast run` is blocked whether or not an agent CLI is present, and the exit status is 1 in both cases.

## R10. Bounded time (FR-016, SC-005)

- **Decision**: Run local probes in a `concurrent.futures.ThreadPoolExecutor` (they are subprocesses with their own `timeout` and are killed on expiry). Network probes do not use the executor, because it joins its threads at interpreter exit: each runs in its own `threading.Thread(daemon=True)` writing into a queue. Each subprocess call uses `timeout=3`, and the network probe uses `urlopen(..., timeout=3)` with `method="HEAD"`. A timeout reports `inconclusive` and kills the child. Network probes run in daemon threads; the main thread waits on each with a wall-clock deadline (`queue.get(timeout=…)`, 5 s overall for the network group), so a stalled DNS resolution cannot hold the report: the check is reported `inconclusive` and the process exits without joining the thread. Test: a resolver that never answers (patched `socket.getaddrinfo`) still yields a report within the deadline. Worst-case wall time is about 3 s plus scheduling.

- **HTTP result mapping (DEC-0007)**: 2xx and 3xx count as reachable, with redirects never followed (one `HEAD`); 404 or no connection is `missing` and blocks setup; 403, 429 and 5xx are `inconclusive`.

## R11. Read-only guarantee (FR-011, AC-012, SC-005)

- **Decision**: Doctor opens files only for reading. Subprocesses get `stdin=DEVNULL`. The probes it runs are themselves read-only (`setup --check`, `launcher status`). Tests take a recursive digest snapshot of the project, `XDG_DATA_HOME`, `XDG_STATE_HOME` and `~/.local/bin` before and after `doctor` and compare them, using stub executables on `PATH`. `__pycache__` cannot appear because the CLI runs with `-I -S` and `PYTHONDONTWRITEBYTECODE=1` is set for probes.

## R12. Credentials (FR-014)

- **Decision**: `gh auth status` output is captured and discarded, and only the exit code is used. No environment variable value is ever printed. A test plants a fake `gh` that prints a token-shaped string and asserts the string is absent from both the human and the JSON output.

## R13. Existing commands (FR-019)

- **Decision**: Existing shim messages ("not fetched", "cannot read ballast.toml", "has no launcher") gain the suffix `; run \`ballast doctor\` for details`. In new standard versions, `tools/setup`'s missing-`uvx`/`patch` message also mentions doctor. Command dispatch is otherwise unchanged, so projects pinning v0.1.0 behave as before.
