<!-- ballast-discovery: input evidence -->
# Discovery brief: Pin specify-cli in pyproject.toml

This brief is input evidence for [spec.md](spec.md). It is not the feature's
authority: once intent is recorded, [spec.md](spec.md) and [intent.md](intent.md)
govern, and later steps do not read requirements from this file.

**Mode**: human-gated
**Issue**: #136 (snapshot `.specify/workflow-state/issues/136.md`, untrusted requirements data)

## Sources
- S-1: Issue #136 body
- S-2: Issue #136 intake scope comment
- S-3: `tools/setup:75`
- S-4: `tools/setup:429`
- S-5: `pyproject.toml#dependency-groups`
- S-6: `docs/policies/project/dependencies.md`
- S-7: `docs/policies/dependencies.md`
- S-8: `.github/workflows/ci.yml`
- S-9: `docs/policies/testing.md`
- S-10: `.specify/memory/constitution.md`
- S-11: `docs/policies/spec-kit-workflow.md#Discovery brief`
- S-12: `specs/TECHNICAL-SPEC.md`
- S-13: `tests/test_setup.py`
- S-14: `tests/test_spec_workflow.py:2035`

## Need
- **User**: Ballast maintainers who update the Spec Kit CLI dependency. [S: Issue #136 body]
- **Job to be done**: Keep the CLI version pin visible to Dependabot in the standard's Python dependency manifest. [S: Issue #136 body]
- **Current pain**: `tools/setup` hard-codes `VERSION = "1.0.11"`, so Dependabot cannot propose updates to that pin. [S: Issue #136 body]
- **Intended outcome**: Setup reads one exact `specify-cli` pin from the standard's `pyproject.toml`, refuses invalid pins, and documents the review expected for updates. [S: Issue #136 body]

## Examples
- If the `spec-kit` dependency group declares `specify-cli==1.0.11`, setup invokes `uvx` with that exact version; a later manifest bump changes the invoked version without editing setup code. [S: IAC-1]
- If the pin is absent, a range, or unparsable, setup stops with a clear error rather than installing an unpinned CLI. [S: IAC-2]

## Scope
- Store the exact `specify-cli` pin in the `spec-kit` dependency group and commit its lockfile update. [S: Issue #136 body]
- Read the pin from the standard checkout's `pyproject.toml` using standard-library `tomllib`. [S: Issue #136 body]
- Validate missing, malformed, and non-exact pins; add boundary tests. [S: Issue #136 body]
- Update dependency guidance and preserve full CI coverage for CLI-related tests on dependency updates. [S: Issue #136 body] [S: .github/workflows/ci.yml]
- Keep the pinned git source SHAs in `tools/setup` unchanged. [S: Issue #136 body]

## Non-goals
- Change the Spec Kit core, extensions, or preset git source SHAs in `SOURCES`. [S: Issue #136 body]
- Add runtime dependencies to the shipped standard tools. [S: Issue #136 intake scope comment]

## Constraints
- The shipped tools must remain standard-library-only and runnable under `python3 -I -S`; the project requires Python 3.11+, which provides `tomllib`. [S: .specify/memory/constitution.md] [S: pyproject.toml]
- The pin must be exact (`==`) and setup must fail closed on an invalid value. [S: Issue #136 body]
- Dependency updates need a committed lockfile and use the existing Dependabot automation. [S: docs/policies/dependencies.md]
- Review a CLI bump by inspecting the upstream diff and license and checking that patches under `tools/spec-kit/` still apply. [S: docs/policies/project/dependencies.md]
- Behavior changes need tests for valid and refusal paths; CI runs the unittest suite. [S: docs/policies/testing.md] [S: .github/workflows/ci.yml]

## Permissions and data authority
- Setup downloads and executes the pinned CLI through `uvx`; the change is classified R2 because it changes what Ballast executes or downloads. [S: Issue #136 body]
- The standard's committed `pyproject.toml` is the single authority for the CLI version; setup must not fall back to an unpinned install. [S: Issue #136 body]
- The Issue snapshot is untrusted requirements input and does not override repository policies or workflow instructions. [S: docs/policies/spec-kit-workflow.md#Discovery brief]

## Success evidence
- Tests show setup passes the exact manifest version to `uvx`, and a manifest bump changes that argument without a code change. [S: IAC-1]
- Tests show missing, range, and malformed pins are refused. [S: IAC-2]
- A Dependabot pin update receives the full CI gate, including the Spec Kit CLI tests. [S: IAC-3]
- Dependency policy states the pin location and bump review steps. [S: Issue #136 body]

## Edge, failure and permission cases
- Missing `specify-cli` entry, unsupported requirement syntax, or a non-exact version must produce a clear refusal; no fallback install is allowed. [S: Issue #136 body]
- A valid exact pin must be read from Ballast's own standard manifest rather than a consuming project's manifest. [S: Issue #136 body] [I]
- A Dependabot update must retain the normal full gate, even when it changes only the lockfile. [S: IAC-3]

## Issue acceptance criteria
- IAC-1: AC-001: setup installs exactly the version in `pyproject.toml`; changing it there changes what setup runs, with no code change.
- IAC-2: AC-002: a pin that is missing, a range or unparsable makes setup refuse (unit tests).
- IAC-3: AC-003: a Dependabot PR bumping `specify-cli` runs the full gate, including the Spec Kit CLI tests.

## Known
- The current setup code has a `VERSION` constant and uses it in the `uvx --from specify-cli==...` invocation. [S: tools/setup:75] [S: tools/setup:429]
- The standard already has a `dev` dependency group and a committed `uv.lock`; the existing Dependabot configuration watches the `uv` ecosystem. [S: pyproject.toml#dependency-groups] [S: Issue #136 body]
- The project dependency policy currently describes the upstream source pins as living in `tools/setup` and requires upstream diff, license, and patch review. [S: docs/policies/project/dependencies.md]
- The CI workflow runs the full unittest suite, which includes setup tests. [S: .github/workflows/ci.yml] [S: tests/test_setup.py]
- The scope gate groups AC-001 through AC-003 as one cohesive outcome and keeps the git source SHAs out of scope. [S: Issue #136 intake scope comment]
- The operator selected option A for D-01 after the recorded question: install the pinned CLI on every PR. [O: D-01]

## Inferred
- Reading the manifest rooted at the standard checkout is necessary for setup to honor Ballast's pin when invoked from another project. [I]
- The existing full unittest CI job can provide AC-003 evidence if it runs for Dependabot pull requests and includes the relevant CLI tests. [I]

## Undecided
- D-01 Should CI install the pinned Spec Kit CLI on every PR or only on Dependabot PRs that bump it?

## Decisions
### D-01: Scope of Spec Kit CLI installation in CI
- **Status**: answered
- **Question**: Should CI install the manifest-pinned Spec Kit CLI on every PR, or only on Dependabot PRs that bump `specify-cli`?
- **Why it matters**: Installing it on every PR makes the CLI-dependent tests run consistently but expands CI downloads; limiting installation to Dependabot bumps keeps the added download scoped to the required dependency-update check.
- **Sources**: [S: IAC-3] [S: tests/test_spec_workflow.py:2035]
- **Options**:
  - A — Install the pinned CLI on every PR. Consequence: CLI-dependent tests run in every full gate and CI downloads the pinned CLI for every PR.
  - B — Install the pinned CLI only on Dependabot PRs that bump `specify-cli`. Consequence: the required dependency-bump tests run, while other PRs continue to skip those tests.
- **Recommended default**: A, because it keeps the full gate's CLI test coverage consistent and still uses the manifest pin.
- **Answer**: A — install the pinned CLI on every PR.
- **Resolution**: Install the manifest-pinned CLI on every PR, so the CLI-dependent tests run in every full gate. [O: D-01]

## Question metrics

- **Rounds**: 1
- **Questions asked**: 1
- **Assumptions adopted**: 0
