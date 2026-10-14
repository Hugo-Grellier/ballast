# Tasks: Pin specify-cli in pyproject.toml

**Input**: Design documents from `/specs/136-pin-specify-cli/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/](contracts/)

**Acceptance evidence**: Each behavior acceptance criterion maps to tests or explicit verification. The final task writes `acceptance-evidence.json` with the current `spec.md` digest. The mapping is proposed evidence; the workflow ledger records accepted evidence.

**Operator-only checks**: None. CI execution and all verification tasks are executable by the implementation run.

**Workflow-owned steps**: The full project gate, quickstart, specialist reviews, convergence, and spec reconciliation run after implementation and are not tasks here.

**Verification commands**: Test tasks name their commands explicitly. Use one command per invocation and preserve `--locked`.

## Phase 1: Setup

**Purpose**: No new project scaffolding is needed; this is an existing Python tooling repository.

## Phase 2: Foundational

**Purpose**: No shared infrastructure blocks the stories; setup pin behavior, fail-closed validation, and CI adoption have their own acceptance scoped tasks.

## Phase 3: User Story 1 - Setup installs exactly the manifest pin (Priority: P1)

**Goal**: Make the standard checkout's exact pin determine setup's CLI invocation and freshness state.

**Independent Test**: Use a temporary standard root with a chosen exact pin and a different caller working directory; verify the requested `uvx` version comes from the standard manifest and changing it changes the fingerprint.

### Acceptance tests for User Story 1

- [X] T001 [P] [US1] Add `spec-kit = ["specify-cli==1.0.11"]` to `pyproject.toml`, run `uv lock`, and commit the resulting resolution in `uv.lock` [AC-001]
- [X] T002 [P] [US1] Add setup tests in `tests/test_setup.py` proving exact pin use, standard-root authority, and fingerprint change when the pin changes [AC-001] [AC-004] [AC-005]

### Implementation for User Story 1

- [X] T003 [US1] Read and validate one standard-checkout CLI pin snapshot in `tools/setup`, reuse it in the staged builder, remove the duplicate `VERSION` constant, and route it through invocation, fingerprint, output, and install metadata while preserving all existing upstream source SHA constants [AC-001] [AC-004] [AC-005] (depends on T001, T002)
- [X] T004 [US1] Update `specs/14-recoverable-install/contracts/setup.md` to document manifest-rooted pin resolution and its effect on setup freshness [AC-001] (depends on T003)

**Checkpoint**: Setup uses only the standard checkout's manifest for the CLI version, and a pin change makes the existing install stale.

## Phase 4: User Story 2 - Setup refuses an unusable pin (Priority: P1)

**Goal**: Reject a missing, duplicate, malformed, or non-exact pin before any Spec Kit CLI download or execution.

**Independent Test**: For invalid manifest fixtures, assert setup reports `pyproject.toml` and the cause, exits through the existing refusal path, and never invokes the command runner.

### Acceptance tests for User Story 2

- [X] T005 [P] [US2] Add refusal tests in `tests/test_setup.py` for missing group/entry, duplicate entry, non-string entry, range, marker, wildcard, malformed TOML, and unsupported version syntax; assert no CLI command runs [AC-002] [AC-006]

### Implementation for User Story 2

- [X] T006 [US2] Enforce the contract's fail-closed pin validation and actionable `pyproject.toml` errors in `tools/setup`, including before `--check` fingerprint use and before any `uvx` invocation [AC-002] [AC-006] (depends on T003, T005)

**Checkpoint**: Every invalid pin fixture refuses before CLI execution; valid pins continue to use the standard manifest.

## Phase 5: User Story 3 - CLI bumps receive the full gate and review guidance (Priority: P2)

**Goal**: Make the pinned CLI tests run on every pull request and tell maintainers how to review a bump.

**Independent Test**: Inspect the workflow trigger and explicit group selection, then run the CI test command and confirm CLI-gated tests execute instead of skipping. Confirm the dependency policy identifies `pyproject.toml` and `uv.lock` as the pin location and names required bump checks.

### Acceptance tests for User Story 3

- [X] T007 [P] [US3] Update `docs/policies/project/dependencies.md`, `docs/policies/project/testing.md`, and `AGENTS.md` with the pin location, bump review guidance, local pre-trust sync, locked CI test group, and remaining skip conditions [AC-003] [AC-007]

### Implementation for User Story 3

- [X] T008 [US3] Update `.github/workflows/ci.yml` so the all-pull-request unittest command explicitly installs the locked `spec-kit` dependency group [AC-003] (depends on T001)
- [ ] T009 [US3] Verify in pull-request CI that the locked `spec-kit` group installs and the full unittest command passes with the Spec Kit CLI-gated tests run rather than skip; record the CI run for AC-003 (depends on T005, T008)

**Checkpoint**: Every PR installs the locked CLI group for the full test suite, and maintainers have explicit bump review guidance.

## Phase 6: Polish & Acceptance Evidence

**Purpose**: Record the criterion-to-test mapping after the implementation test names are final.

- [X] T010 Write `specs/136-pin-specify-cli/acceptance-evidence.json` with schema version 1, the current SHA-256 digest of `specs/136-pin-specify-cli/spec.md`, and mappings for AC-001 through AC-007: `tests.test_setup.SpecifyPinTests.test_cli_version_comes_from_standard_manifest`; `tests.test_setup.SpecifyPinTests.test_invalid_cli_pin_refuses_before_specify`; `[]` for AC-003 (CI run evidence); `tests.test_setup.SpecifyPinTests.test_cli_pin_comes_from_standard_root`; `tests.test_setup.SpecifyPinTests.test_cli_pin_change_changes_fingerprint`; `tests.test_setup.SpecifyPinTests.test_duplicate_cli_pins_refuse`; and `[]` for AC-007 (policy review evidence) (depends on T002, T003, T004, T005, T006, T007, T008)

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No setup task is needed.
- **Foundational (Phase 2)**: No shared prerequisite is needed.
- **User Stories (Phase 3+)**: Tasks depend on the shared manifest and setup pin behavior only where required. US1 and US2 build the parser boundary; US3's policy edit is independent, while its CI test selection depends on the manifest group.
- **Polish (Phase 6)**: Acceptance mapping depends on the final implementation and verification task set.

### User Story Dependencies

- **User Story 1 (P1)**: Starts with manifest and test tasks; setup implementation depends on both.
- **User Story 2 (P1)**: Its tests can be authored after the initial US1 tests; fail-closed implementation depends on the US1 loader.
- **User Story 3 (P2)**: Dependency policy can proceed independently. CI group selection depends on the manifest group; its end-to-end test verification depends on CI configuration and the validated setup pin.

### Execution Wave DAG

Tasks in one wave can proceed in parallel once all listed dependencies are complete.

```text
Wave 1 (no dependencies):
  T001 [US1] Add the dependency group and update uv.lock
  T002 [US1] Add valid-pin, root-authority, and fingerprint tests
  T007 [US3] Update dependency review guidance

Wave 2 (T001 and/or T002 as listed):
  T003 [US1] Implement manifest pin loading and propagate the value (depends on T001, T002)
  T005 [US2] Add invalid-pin refusal tests (depends on T002)
  T008 [US3] Select the locked group in CI (depends on T001)

Wave 3:
  T004 [US1] Update setup contract (depends on T003)
  T006 [US2] Enforce refusal behavior (depends on T003, T005)

Wave 4:
  T009 [US3] Verify the full suite and CLI test execution in pull-request CI (depends on T006, T008)

Wave 5:
  T010 Write acceptance-evidence.json (depends on T002, T003, T005, T006, T007, T008)
```

### Parallel Opportunities

- T001, T002, and T007 touch separate files and can start together.
- T003, T004, and T008 can proceed in parallel after their declared prerequisites.
- T004 and T006 touch separate files and can proceed in parallel after T003/T005 as declared.

## Implementation Strategy

### MVP First

Complete US1 first: the dependency group and lock, tests, manifest-backed setup pin, and setup contract update. This delivers the core Dependabot-visible pin and verifies setup uses it. Then complete the refusal behavior and all-PR CI coverage before considering the feature complete.

### Incremental Delivery

1. Add and lock the package group; establish valid pin, source-root, and freshness evidence.
2. Implement the loader and replace all existing hard-coded version uses.
3. Add invalid-pin refusal coverage and ensure failure precedes CLI invocation.
4. Enable the locked group in CI and update dependency guidance.
5. Verify the full suite in pull-request CI and write acceptance evidence for all seven criteria. The focused local CLI tests and setup smoke run are recorded separately; the full local suite is deferred by operator direction.
