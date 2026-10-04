# Feature Specification: One-command CLI install and `ballast doctor`

**Feature Branch**: `feat-cli-install-ballast-in-one-command-and-diag`

**Created**: 2026-10-03

**Status**: Draft

**Input**: User description: "Issue #12: A new operator can obtain the pinned Ballast CLI without copying a script from a checkout and can see exact prerequisites before running a workflow."

**Tracking**: [Ballast #12](https://github.com/Hugo-Grellier/ballast/issues/12), a leaf of the [Ballast 1.0 Epic](https://github.com/Hugo-Grellier/ballast/issues/11); roadmap Phase 1, items 1 and 3 ([product roadmap](../../docs/plans/2026-10-02-product-roadmap.md)).

**Risk**: R2. The feature changes what `ballast` downloads and how the machine-wide entry point is obtained (the trust model's operator-side root). It needs explicit human approval of intent and plan.

## Context

Today a new operator installs the global `ballast` command by running `install -m 0755 tools/ballast ~/.local/bin/ballast` from a reviewed checkout of this repository. That step requires cloning the source repository, choosing a revision by hand and reviewing it, and nothing records which version was installed. Prerequisites are spread across the README: `git`, `uvx`, `patch` and network access for setup; Linux with a systemd user session for headless steps; an agent CLI; `gh` for intake. An operator learns about a missing one when a command fails partway through.

This feature gives the operator a single, version-pinned install command and a read-only `ballast doctor` command that lists what is present, what is missing and the exact remedy, before any workflow runs. It does not cover `ballast init`, worktree auto-setup or update preview; those are separate Phase 1 items.

## User Scenarios & Testing *(mandatory)*

Give each acceptance scenario a stable ID (`AC-001`, `AC-002`, ...). Task and test descriptions cite the IDs they satisfy, so review can trace each criterion to evidence.

### User Story 1 - Install the Ballast CLI with one command (Priority: P1)

A new operator on a supported machine runs one documented command that names a released Ballast version. Afterwards, `ballast` is on their path, reports that version, and works exactly as a command installed by hand from a reviewed checkout of the same version. The operator never clones this repository or copies a file out of a checkout.

**Why this priority**: Every other Ballast workflow starts from this command. The current manual copy is the first point where adoption fails, and it gives no record of which version the operator trusted.

**Independent Test**: On a clean user account with no prior Ballast install, run the documented command for a released version, then run `ballast --version` and `ballast setup` in a project pinned to that version.

**Acceptance Scenarios**:

1. **AC-001**: **Given** a machine with no `ballast` command, **When** the operator runs the documented install command for release `vX.Y.Z`, **Then** a `ballast` command is installed in a user-owned location outside any project checkout, and `ballast --version` prints `vX.Y.Z`.
2. **AC-002**: **Given** the install command has completed, **When** the installed command is compared with the `tools/ballast` file of release `vX.Y.Z`, **Then** they are byte-identical.
3. **AC-003**: **Given** the downloaded CLI does not match the integrity reference published with the release (corrupted or substituted content), **When** the install command runs, **Then** it refuses, leaves any existing `ballast` command unchanged and names the mismatch.
4. **AC-004**: **Given** an existing `ballast` command (installed by hand or by an earlier run of the install command), **When** the operator runs the install command for another version, **Then** the command is replaced in one step, and the output names the previous and the new version. If the previous version cannot be identified, the output says so.
5. **AC-005**: **Given** the install location is not on the operator's `PATH`, **When** installation finishes, **Then** the output says so and gives the exact line to add to the shell configuration.
6. **AC-006**: **Given** the install command is run from inside a Git working tree, including a checkout of this repository, **When** it installs, **Then** nothing it installs or executes is read from that working tree.

---

### User Story 2 - See exact prerequisites before running a workflow (Priority: P1)

Before running setup or a feature workflow, the operator runs `ballast doctor` and gets one report. It checks each prerequisite and marks it present, missing or unsupported, and for every gap it gives the exact remedy (command to run, package to install, or setting to change). The report states which Ballast commands are blocked by each gap.

**Why this priority**: The issue's second outcome. It turns failures that currently appear partway through a workflow into a checklist the operator can work through before starting.

**Independent Test**: Run `ballast doctor` on a machine where one known prerequisite is removed from `PATH`. Check that the report names that prerequisite, the commands it blocks, and a remedy that fixes it when applied.

**Acceptance Scenarios**:

1. **AC-007**: **Given** a machine where every prerequisite is present, **When** the operator runs `ballast doctor`, **Then** every check is reported as passing and the command exits successfully.
2. **AC-008**: **Given** a required prerequisite is missing (for example `patch` or `uvx`), **When** the operator runs `ballast doctor`, **Then** the report names it, the commands it blocks (for example `ballast setup`), an exact remedy, and the command exits with a failure status.
3. **AC-009**: **Given** the host cannot run headless agent steps (not Linux, or no systemd user session available), **When** the operator runs `ballast doctor`, **Then** the report says headless `ballast run` steps are unsupported on this host and why, and still reports the checks that do not depend on the host type.
4. **AC-010**: **Given** no agent CLI that Ballast can drive is installed, or `gh` is installed but not authenticated, **When** the operator runs `ballast doctor`, **Then** each gap is reported with its remedy and the workflows it blocks, and no credential value is printed.
5. **AC-011**: **Given** the operator runs `ballast doctor` outside any project, **When** it finishes, **Then** it reports the machine checks and says the project checks were skipped because no `ballast.toml` was found.
6. **AC-012**: **Given** any machine or project state, **When** `ballast doctor` runs, **Then** it does not modify the project, the fetched standard versions, the trust baseline or run state. It also does not download anything.

---

### User Story 3 - See the project's Ballast readiness (Priority: P2)

Inside a project, `ballast doctor` also checks the project: whether `ballast.toml` pins a valid version, whether that version is fetched, whether setup has installed it, and whether the launcher would currently refuse because the trust baseline is missing or out of date. Each gap comes with the next command to run.

**Why this priority**: After the machine checks pass, the operator most often needs to know which of `setup` or `trust` comes next. It depends on Story 2's report.

**Independent Test**: In a project whose pinned version is not fetched, run `ballast doctor`. It should name `ballast setup` as the next step. Run setup, then rerun `ballast doctor`; it should name `ballast trust`.

**Acceptance Scenarios**:

1. **AC-013**: **Given** a project whose `ballast.toml` is missing its `[standard] ref` or has an invalid one, **When** the operator runs `ballast doctor`, **Then** the report names the problem and the expected form, using the same rules as other `ballast` commands.
2. **AC-014**: **Given** a project whose pinned version is not fetched, **When** the operator runs `ballast doctor`, **Then** the report says so and names `ballast setup` as the remedy.
3. **AC-015**: **Given** a project that is set up but whose protected inputs differ from the trusted baseline (or have no baseline), **When** the operator runs `ballast doctor`, **Then** the report says the launcher will refuse and names review followed by `ballast trust` as the remedy, without trusting anything itself.
4. **AC-016**: **Given** the installed `ballast` command is older than the version the project pins and that version needs a newer CLI, **When** the operator runs `ballast doctor`, **Then** the report names the mismatch and the install command for a suitable CLI version.

### Edge Cases

- The install command loses network access partway through or is interrupted: no partial `ballast` file is left in place, and any earlier install still works.
- The install target exists but is not a Ballast command (another tool named `ballast`): the install command refuses unless the operator explicitly asks to overwrite it.
- The requested version does not exist or predates the install command: the install command fails, names the version, and does not change the existing install.
- `BALLAST_STANDARD_DIR` is set (developing the standard): `ballast doctor` reports that the local standard is in use and checks it instead of the pinned version.
- The interpreter the CLI runs under is missing or too old to run it: the install command and the installed command both fail with a message naming the required version, not a Python traceback.
- A project's `ballast.toml` cannot be parsed: `ballast doctor` reports the parse error as a project check and still reports the machine checks.
- A prerequisite check takes a long time or hangs (for example, the user session bus does not respond): the check reports itself as inconclusive within a bounded time rather than blocking the report.

## Requirements *(mandatory)*

### Functional Requirements

**Installation**

- **FR-001**: Ballast MUST publish one documented install command that takes an explicit released version and installs the matching `ballast` CLI for the current user. The operator does not need a clone of this repository.
- **FR-002**: The install command MUST obtain the CLI only from this repository's published releases (the fixed source per BL-INV-004). It MUST verify the content against an integrity reference published with that release before placing it.
- **FR-003**: The install command MUST install into a user-owned location outside any project checkout, and MUST NOT read or execute anything from the current working directory or any Git working tree.
- **FR-004**: The install command MUST replace an existing install atomically and leave the previous command intact on any failure. Rerunning it for the same version MUST be a no-op that reports success.
- **FR-005**: The install command MUST report the installed version and location, the previous version when known, and whether the location is on `PATH` with the exact remedy when it is not.
- **FR-006**: The installed CLI MUST report its own version (`ballast --version`) without needing a project or network access.
- **FR-007**: The install channel MUST be the release's CLI asset plus its SHA-256 checksum, fetched, verified and installed by one documented shell line: the line in [contracts/install.md](contracts/install.md), which is the single copy the README shows and the tests run. It runs in a subshell with a fixed system `PATH`, a temporary directory under `/tmp`, a value comparison of the published hash, and `/usr/bin/python3 -I -S`. The verified file's `self-install` subcommand performs the atomic replace, the same-version no-op and the version and `PATH` report (FR-004, FR-005). The installed file is the reviewed single-file launcher, unchanged, so it keeps its `python3 -I -S` isolation; a checksum mismatch installs nothing. *Provisional decision (agent, under the operator's standing authority of 2026-10-03), rejected alternatives: `curl … | sh` (executes unreviewed network code), `uv tool install`/`pipx` (turns the repository into a Python package and runs the launcher from a venv without `-I -S`).*

**Diagnosis**

- **FR-008**: `ballast doctor` MUST check the machine prerequisites of every Ballast command it ships with. These include at least: the Python interpreter the CLI and tools run under, plus its version; `git`, `uvx` and `patch` for setup; network reachability of the fixed release source when setup will need to fetch; Linux, a systemd user session and the transient-unit facility for headless `ballast run` steps; at least one supported agent CLI for agent steps; and an authenticated `gh` for issue intake and PR steps.
- **FR-009**: For each check, `ballast doctor` MUST report a status of passing, missing, unsupported or inconclusive, the Ballast commands or workflow steps the check gates, and, for every status except passing, one exact remedy.
- **FR-010**: Inside a project (a directory with `ballast.toml`), `ballast doctor` MUST also report the pinned version and whether it is valid and fetched, whether setup has installed it in this checkout, and whether the launcher would refuse on trust grounds. Each gap MUST name the next command.
- **FR-011**: `ballast doctor` MUST be read-only: it MUST NOT write project files, fetched versions, trust baselines, run state or ledgers, and MUST NOT download. A reachability check may contact the network only to probe; it MUST NOT download anything. Read-only means no writes to files or persistent state and no downloads; a collected transient systemd scope that leaves no unit or file behind is permitted (DEC-0003).
- **FR-012**: `ballast doctor` MUST work before any standard version is fetched and before the project is trusted. It MUST NOT execute anything from the project checkout (BL-INV-002).
- **FR-013**: `ballast doctor` MUST exit successfully when no check blocks a command, and MUST exit with a failure status when at least one check is missing or unsupported for a command the operator can otherwise reach. Its output MUST state which case applies.
- **FR-014**: `ballast doctor` MUST NOT print credential values, tokens or the contents of secret files. It reports only whether a credential is available.
- **FR-015**: `ballast doctor` MUST offer a machine-readable output alongside the human report so later features (`ballast init`, CI) can consume the same checks.
- **FR-016**: Each prerequisite check MUST finish or report inconclusive within a bounded time, so one unresponsive check cannot stall the report.

**Documentation and consistency**

- **FR-017**: The README's install section MUST lead with the install command and `ballast doctor`. The manual copy from a checkout may remain only as a documented fallback for developing the standard.
- **FR-018**: The prerequisite list MUST have a single source in the shipped tools, so the README and `ballast doctor` cannot drift. The README MAY summarize it but MUST point to `ballast doctor` as authoritative.
- **FR-019**: Existing commands (`setup`, `trust`, `run`, `ledger`) MUST behave unchanged for projects pinning earlier versions. Where they fail on a missing prerequisite today, their error SHOULD suggest `ballast doctor`.

### Key Entities

- **Installed CLI**: the machine-wide `ballast` command. Attributes: version, install location, integrity reference it was verified against.
- **Release CLI asset**: the CLI as published with a tagged release, with its integrity reference. This is the only source the install command accepts.
- **Prerequisite check**: one condition `doctor` evaluates. Attributes: name, scope (machine or project), status, the commands it gates, remedy.
- **Doctor report**: the ordered set of checks for one invocation, plus an overall verdict. It has human-readable and machine-readable forms.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A new operator goes from no Ballast install to a working `ballast --version` with exactly one command, without cloning this repository.
- **SC-002**: On a qualified host (Linux with a systemd user session), an operator who follows only the README and the `doctor` remedies reaches a successful `ballast setup` in a fresh project with no failure caused by a missing prerequisite.
- **SC-003**: For every prerequisite named in FR-008, removing it produces a `doctor` report that names it with a remedy, and applying that remedy makes the check pass. A test covers each prerequisite.
- **SC-004**: Every tested failure of the install command (bad integrity, unknown version, interrupted download, foreign file at the target) leaves the previously installed command byte-identical and runnable.
- **SC-005**: `ballast doctor` completes in under 10 seconds on a qualified host when every check is responsive, and leaves the project, fetched versions, trust baseline and state directories unchanged (verified by snapshot comparison).

## Assumptions

- The qualified 1.0 host is Linux with a systemd user session ([roadmap](../../docs/plans/2026-10-02-product-roadmap.md)). On other hosts, `doctor` reports headless steps as unsupported rather than trying to support them; the install command only needs to work on the qualified host for this feature.
- The supported agent CLIs are the ones the shipped agent wrapper can already drive (Claude Code and Codex); this feature does not add new agents.
- The CLI keeps running under the system Python interpreter at a fixed path with the standard library only (constitution principle 6). The install command does not install Python.
- Release Please already publishes tagged releases. This feature adds the CLI asset and integrity reference to those releases, plus the install command. Signing beyond a published checksum is out of scope unless the clarification for FR-007 requires it.
- `ballast doctor` is implemented by the machine-wide CLI so it works before any version is fetched. Project checks that depend on the pinned version's internals (for example the trust-baseline comparison) use that version's trusted launcher only when it is already fetched, and only in a read-only mode.
- Out of scope: `ballast init`, zero-repeat worktree setup, reliable atomic project installation, update preview and rollback, GitHub/CI configuration checks (branch protection, required checks), and Windows or macOS headless support. Each is a separate roadmap item.
- Reconciled with Issue #12 before intent approval (2026-10-03): its three acceptance criteria map to AC-001–AC-006 (one documented install command; projects still pin a version, not an executable source), AC-008–AC-010 and AC-013–AC-015 (missing prerequisites, unfetched pin, invalid install, missing trust, GitHub and systemd unavailable, each with a remedy) and FR-012/AC-012 with the plan's clean, missing and tampered test states. The issue's exclusions (project bootstrap, feature dependencies, other host platforms) are respected.
