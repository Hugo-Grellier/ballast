# Feature Specification: Pin specify-cli in pyproject.toml

**Feature Branch**: `feat-setup-pin-specify-cli-in-pyproject.toml-so`

**Created**: 2026-10-14

**Status**: Draft

**Input**: User description: "Issue #136. Read the Issue in .specify/workflow-state/issues/136.md first. Set SPECIFY_FEATURE_DIRECTORY=specs/136-pin-specify-cli before creating spec.md; keep this path for the feature's later artifacts."

**Risk**: R2. Setup downloads and runs the pinned Spec Kit CLI, so this feature changes where the version that Ballast downloads and executes comes from. [S: Issue #136 body]

## Clarifications

### Session 2026-10-14

- Q: Besides `ballast setup`, which other places that refer to the Spec Kit CLI should follow the manifest pin? → A: Setup only. The `ballast doctor` install hint and the `specify` that `ballast run` finds on PATH are out of scope. [O: operator, clarify 2026-10-14]

## User Scenarios & Testing *(mandatory)*

Give each acceptance scenario a stable ID (`AC-001`, `AC-002`, ...). Task and test descriptions cite the IDs they satisfy, so review can trace each criterion to evidence.

### User Story 1 - Setup installs exactly the version the manifest pins (Priority: P1)

A Ballast maintainer bumps the Spec Kit CLI version in one place: the exact pin in the standard's dependency manifest. The next `ballast setup` installs that version. Nobody edits setup code, and setup never runs a CLI version the manifest does not name.

**Why this priority**: This is the core of the Issue. Until the pin lives in the manifest, Dependabot cannot see the version and every bump is a manual code edit.

**Independent Test**: Point setup at a standard checkout whose manifest pins version X and record the CLI version setup asks for. Change the pin to Y, rerun, and confirm the requested version is Y with no other file changed.

**Acceptance Scenarios**:

1. **AC-001**: **Given** the standard's manifest declares an exact `specify-cli` pin in its Spec Kit dependency group, **When** setup installs or runs the Spec Kit CLI, **Then** it requests exactly that version. Changing only the manifest pin changes the version setup requests, with no change to setup code. [S: IAC-1]
2. **AC-004**: **Given** setup runs from a consuming project whose own manifest names a different (or no) `specify-cli` version, **When** setup resolves the CLI version, **Then** it uses the pin from the Ballast standard checkout and ignores the consuming project's manifest. [B: Edge, failure and permission cases] [I]
3. **AC-005**: **Given** a project already installed with one pin, **When** the standard's pin changes and setup runs again, **Then** setup treats the install as out of date and reinstalls with the new version. It does not report the old install as current. [I]

---

### User Story 2 - Setup refuses an unusable pin (Priority: P1)

If the manifest pin is missing, a range, or malformed, setup stops with a clear error that names the problem. It does not fall back to an unpinned or default CLI version.

**Why this priority**: The pin decides what code Ballast downloads and runs. Failing closed is a security requirement, not a convenience.

**Independent Test**: Run setup against standard manifests with the pin missing, with a range, and with unparsable content. Confirm each run stops before any CLI download or execution and names the cause.

**Acceptance Scenarios**:

1. **AC-002**: **Given** the standard's manifest has no `specify-cli` entry in the Spec Kit group, or that entry is not an exact `==` version (for example `>=1.0`, `~=1.0.11`, an unversioned name, or an extra marker or wildcard), or the manifest cannot be parsed, **When** setup runs, **Then** it exits with an error that names the manifest and the problem, and it does not invoke the Spec Kit CLI. [S: IAC-2]
2. **AC-006**: **Given** the Spec Kit group declares `specify-cli` more than once, **When** setup runs, **Then** it refuses rather than picking one of the entries. [I]

---

### User Story 3 - A CLI bump gets the full gate and a documented review (Priority: P2)

When Dependabot opens a PR that bumps `specify-cli`, the PR runs the same full CI gate as any other change, and that gate includes the tests that need the Spec Kit CLI. The dependency policy tells the reviewer where the pin lives and what to check before merging.

**Why this priority**: The automation is only safe if a bump is checked against the CLI it introduces and reviewed against upstream changes and Ballast's patches.

**Independent Test**: On a PR that changes only the `specify-cli` pin and its lockfile entry, confirm that CI runs the lint, unit test and dogfood jobs and that the Spec Kit CLI tests run rather than skip. Read the dependency policy and confirm it names the pin's location and the bump review steps.

**Acceptance Scenarios**:

1. **AC-003**: **Given** a Dependabot PR that bumps the `specify-cli` pin, **When** CI runs, **Then** the full gate runs, and the Spec Kit CLI tests run against the bumped version instead of being skipped. [S: IAC-3]
2. **AC-007**: **Given** a maintainer reviewing a CLI bump, **When** they read the project dependency policy, **Then** it states that the CLI pin lives in the Spec Kit dependency group of `pyproject.toml` (locked in `uv.lock`) and that the upstream source SHAs stay in setup. It also says a bump needs an upstream diff and license review and a check that the Spec Kit patches still apply. [S: Issue #136 body] [S: docs/policies/project/dependencies.md]

---

### Edge Cases

- No Spec Kit dependency group, or a group without `specify-cli`: refuse with an error that names the missing entry (AC-002). [S: Issue #136 body]
- Range, compatible-release, wildcard, unversioned or marker-qualified requirement: refuse, because only an exact `==` version is allowed (AC-002). [S: Issue #136 body]
- Duplicate `specify-cli` entries: refuse (AC-006). [I]
- `specify-cli` appears only in another group (for example `dev`): treat it as missing. [I]
- Unparsable manifest: refuse and name the manifest (AC-002). [S: IAC-2]
- Setup runs with an isolated, site-free interpreter: reading the pin must not need any third-party package. [S: .specify/memory/constitution.md]
- Read-only check mode (`--check`) must read the same pin and refuse the same invalid pins, without writing anything. [I]
- A Dependabot PR that changes only `uv.lock`, or only the pin, still gets the full gate (AC-003). [B: Edge, failure and permission cases]

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The standard's `pyproject.toml` MUST declare the Spec Kit CLI as one exact `specify-cli==<version>` entry in a dedicated `spec-kit` dependency group, and `uv.lock` MUST be updated and committed to match. [S: Issue #136 body] [S: docs/policies/dependencies.md]
- **FR-002**: Setup MUST read the CLI version from the Ballast standard checkout's `pyproject.toml`, never from the consuming project, and MUST use it for every Spec Kit CLI invocation setup makes. Other commands that refer to the CLI are out of scope (see Non-goals). [S: Issue #136 body] [I] [O: clarify 2026-10-14]
- **FR-003**: Setup MUST NOT contain a second, hard-coded copy of the CLI version. The manifest is the only source. [S: Issue #136 body]
- **FR-004**: Setup MUST refuse, before any CLI download or execution, when the pin is missing, duplicated, not an exact `==` version, or the manifest cannot be parsed. The error MUST name the manifest and the reason. [S: IAC-2] [I]
- **FR-005**: Reading and validating the pin MUST use only the Python standard library and MUST work under `python3 -I -S`. [S: .specify/memory/constitution.md] [S: Issue #136 intake scope comment]
- **FR-006**: The install's freshness fingerprint MUST change when the pin changes, so that setup's check reports an older install as out of date. [I]
- **FR-007**: CI MUST run the Spec Kit CLI tests, rather than skip them, with the CLI version pinned in the manifest, on every pull request, including Dependabot pull requests. [S: IAC-3] [O: D-01]
- **FR-008**: The project dependency policy MUST document the pin's location and the review a bump needs: upstream diff, license, and confirmation that the patches under `tools/spec-kit/` still apply. [S: Issue #136 body] [S: docs/policies/project/dependencies.md]
- **FR-009**: The pinned upstream source SHAs (Spec Kit core, extensions and preset) MUST stay in setup and unchanged. [S: Issue #136 body]
- **FR-010**: Tests MUST cover the valid-pin path (the requested version follows the manifest) and each refusal path in AC-002 and AC-006. [S: docs/policies/testing.md] [S: IAC-2]

### Key Entities

- **CLI pin**: the single exact `specify-cli` version in the standard's `spec-kit` dependency group. It decides which Spec Kit CLI version setup downloads and runs.
- **Standard manifest**: the Ballast standard checkout's `pyproject.toml`, which is the only authority for the pin. Consuming projects' manifests are out of scope.
- **Lockfile**: `uv.lock`, which records the resolved pin for Dependabot and the gate.

### Non-goals

- Changing the Spec Kit core, extension or preset git source SHAs. [S: Issue #136 body]
- Adding runtime dependencies to the shipped tools. [S: Issue #136 intake scope comment]
- Moving any other upstream pin into the manifest.
- Changing the `ballast doctor` Spec Kit install hint, which stays `uv tool install specify-cli`. [O: clarify 2026-10-14]
- Changing how `ballast run` finds the `specify` CLI, including checking it against the pin. A run keeps using the `specify` on PATH. [O: clarify 2026-10-14]

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A Spec Kit CLI bump touches exactly two files, `pyproject.toml` and `uv.lock`, with zero edits to setup code.
- **SC-002**: Each invalid pin case (missing, range, malformed manifest, duplicate) stops setup before any CLI download or execution: 0 of these cases runs the CLI.
- **SC-003**: Dependabot can open a PR that bumps the CLI pin, with no manual workflow step needed to surface the update.
- **SC-004**: On a CLI-bump PR, the Spec Kit CLI tests report as run rather than skipped.

## Assumptions

- The Issue body, intake scope comment and acceptance criteria IAC-1 to IAC-3 come from the validated [discovery brief](discovery.md). This spec is the authority for the feature.
- Dependabot's `uv` ecosystem, which already watches `/`, updates exact pins in a PEP 735 dependency group, so no new Dependabot entry is needed. Planning confirms this.
- CI's test job currently skips CLI-dependent tests because `specify` is not on PATH. The operator selected installing the pinned CLI on every PR so those tests run in every full gate. This changes what CI downloads, which is part of this feature's R2 classification. [S: tests/test_spec_workflow.py:2035] [O: D-01]
- Bumping the pin should make setup reinstall. The current freshness fingerprint includes the version, so this assumption keeps existing behavior intact. [I]
- The project requires Python 3.11 or later, which provides the standard-library TOML reader. [S: pyproject.toml]
