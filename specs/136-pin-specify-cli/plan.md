# Implementation Plan: Pin specify-cli in pyproject.toml

**Branch**: `feat-setup-pin-specify-cli-in-pyproject.toml-so` | **Date**: 2026-10-14 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/136-pin-specify-cli/spec.md`

**Risk**: R2. This changes the source of the version that setup downloads and executes, and adds the CLI to CI downloads. The operator approved the R2 pre-change gate for this feature; the final merge still requires human approval.

## Summary

Move the existing `specify-cli` version pin from `tools/setup` into a dedicated `spec-kit` dependency group in the standard checkout's `pyproject.toml`, and lock it in `uv.lock`. Setup will parse and validate that committed manifest with `tomllib` before any Spec Kit download, then use the validated version for its invocation, fingerprint, status output, and install metadata. CI will explicitly install the `spec-kit` group for every pull request so CLI-dependent tests run. The project dependency policy will explain the new pin location and bump review.

Keep the setup interpreter dependency-free and preserve the existing upstream source SHAs. The dependency group is for development and CI; normal `uv sync --locked` continues to install only the default `dev` group.

## Technical Context

**Language/Version**: Python 3.11+, including standard-library `tomllib`.
**Primary Dependencies**: `specify-cli` exact pin in a dedicated uv dependency group; setup itself remains standard-library-only.
**Storage**: `pyproject.toml` is the pin authority; `uv.lock` records its resolved dependency graph.
**Testing**: `unittest`; setup tests exercise pin parsing and refusal before the command runner; the CI test job installs the group before running the suite.
**Target Platform**: Supported Ballast developer and CI environments; setup remains runnable as `python3 -I -S`.
**Project Type**: Python CLI/tooling repository.
**Performance Goals**: No material change; parse one small TOML file before setup.
**Constraints**: No third-party imports from shipped tools; fail closed on missing, duplicate, malformed, or non-exact pins; read only the standard checkout manifest; keep default developer installs unchanged; preserve the existing source SHAs.
**Scale/Scope**: One package pin, one lockfile, setup's pin resolution, the all-PR CI test job, dependency guidance, and focused tests.

## Constitution Check

- **Portable, dependency-free tools**: Pass. Use `tomllib` and `re` from the standard library; do not import uv or packaging at runtime.
- **Source authority and fail-closed behavior**: Pass. Resolve `pyproject.toml` from the `tools/setup` checkout root and reject invalid declarations before constructing or running `uvx`.
- **Executable evidence**: Pass when implementation adds tests for the valid pin and every refusal path, including no command invocation on refusal.
- **Downloads and execution**: R2 is approved at the pre-change gate. CI's explicit dependency-group install is part of the approved feature scope.
- **No project-wide architecture change**: Pass. No constitution, trust, launcher, or source-SHA changes are proposed.

## Architecture Boundaries

- **Affected areas**: Setup's manifest boundary and fingerprint (`tools/setup`); dependency declaration and lock (`pyproject.toml`, `uv.lock`); CI test environment (`.github/workflows/ci.yml`); setup boundary tests (`tests/test_setup.py`); CLI-gated workflow tests (`tests/test_spec_workflow.py`); project dependency guidance (`docs/policies/project/dependencies.md`).
- **Contracts and data flow**: `pyproject.toml` owns the exact package version. `tools/setup` reads the file under its own `STANDARD` checkout root, validates the `spec-kit` group, and passes the resulting version as an argument to `uvx`. The version also participates in setup's fingerprint and existing user-visible install records. CI asks uv to install the `spec-kit` group from the committed lock before running tests. The consuming project's manifest is never consulted.
- **Architecture references**: [Constitution](../../.specify/memory/constitution.md), [dependency policy](../../docs/policies/dependencies.md), [project dependency policy](../../docs/policies/project/dependencies.md), [setup contract](../14-recoverable-install/contracts/setup.md), [ADR-0002](../../docs/adr/0002-cli-standard-manifest.md) for per-version ownership, and [ADR-0007](../../docs/adr/0007-recoverable-installation.md) for setup fingerprint and installation records.
- **Proposed architecture decisions**: None. This relocates an existing pin within the accepted dependency policy.

## Design Decisions for Plan Review

1. **Install the group explicitly in CI.** Use the existing `spec-kit` dependency group with `uv run --locked --group spec-kit ...` (or equivalent workflow install followed by the test command). This makes CI exercise the lockfile while keeping ordinary `uv sync --locked` developer environments unchanged. It does not make `uvx` consume `uv.lock`; its transitive environment remains resolved by uvx. This matches the selected all-PR CI scope and limits default environment changes.
2. **Accept only stable numeric release pins.** Validate the requirement as exactly `specify-cli==N.N...` with numeric dot-separated components, with no markers, wildcard, local version, range, or suffix. This matches the existing stable pin and dependency policy. If maintainers want the full PEP 440 exact-version surface later, that should be a separately specified behavior change rather than adding a dependency parser to setup.
3. **Use the standard checkout as root.** Load the manifest from `Path(__file__).resolve().parent.parent`, never the caller's working directory. The tests should use a temporary standard root or a narrow loader seam to prove this boundary.

## Repository Impact

- `pyproject.toml`, `uv.lock`: add the exact `specify-cli` pin to `[dependency-groups].spec-kit` and refresh the lock.
- `tools/setup`: replace the hard-coded version with a standard-library manifest loader; validate before the CLI command path; route the loaded version through every existing setup use of the old constant, including fingerprint and rendered/recorded version values.
- `tests/test_setup.py`: cover manifest pin selection, standard-root authority, duplicate/missing/group/range/malformed refusals, and refusal before command execution; retain fingerprint freshness coverage.
- `.github/workflows/ci.yml`: explicitly install the `spec-kit` group in the all-PR test job before running unittest.
- `docs/policies/project/dependencies.md`: move the CLI version pin guidance to `pyproject.toml`/`uv.lock`; keep upstream git source SHAs in setup and preserve the existing diff, license, and patch review requirements.
- `docs/policies/project/testing.md`, `AGENTS.md`: install the locked `spec-kit` group before trust for local CLI tests, and describe which environment-dependent tests still skip in CI.
- `specs/14-recoverable-install/contracts/setup.md`: document that setup requires and validates the standard checkout's CLI pin before any CLI invocation, including `--check` behavior if the current contract requires it to resolve the fingerprint.
- `tests/test_spec_workflow.py`: use the current CLI-gated tests as CI evidence; change tests only if installation reveals a real incompatibility.

## Feature Artifacts

```text
specs/136-pin-specify-cli/
├── intent.md
├── discovery.md
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── contracts/
│   └── setup-pin.md
├── quickstart.md
├── tasks.md            # after plan approval
└── reviews/            # material reviews and convergence evidence
```

## Complexity Tracking

No constitution violations or new abstractions are proposed.
