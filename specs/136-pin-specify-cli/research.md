# Research: Pin specify-cli in pyproject.toml

**Feature**: [spec.md](spec.md)
**Date**: 2026-10-14

## Existing implementation

- `tools/setup` defines `VERSION = "1.0.11"`; setup uses it in the `uvx --from specify-cli==...` command and in setup freshness and install reporting. Replace all uses with one validated manifest value so the pin has one source of truth.
- `tools/setup` derives `STANDARD` from its own file location. This is the correct authority when setup runs in a consuming project.
- `pyproject.toml` already has a `dev` dependency group, and `uv.lock` is committed. The CI workflow runs the unittest suite on pull requests. `tests/test_spec_workflow.py` skips a CLI-dependent test class when `specify` is absent from PATH.
- The project requires Python 3.11+, so the setup interpreter has `tomllib` available even under `-I -S`.

## Dependency evaluation

The repository already uses `specify-cli==1.0.11` through uvx. The proposed move preserves that direct version while making it visible to Dependabot. PyPI identifies 1.0.11 as a non-yanked MIT release requiring Python 3.11 or newer. It is not the latest release as of 2026-10-14 (PyPI lists 1.1.3); retaining 1.0.11 is a relocation of the current pin, and a later Dependabot update should receive an upstream diff and patch-compatibility review. No published advisories were found in the checked PyPI/GitHub advisory listings. These checks are not a guarantee that the package or its dependencies are vulnerability-free.

The package adds a material CI download (about a 0.98 MB wheel; runtime dependencies include Typer, Click, Rich, PyYAML, Packaging, Pathspec, Readchar, and json5). The CLI may make further network requests for catalogs, extensions, or release information. CI already runs CLI-aware tests conditionally, so installing the selected pin makes that existing coverage active.

## Dependency-group behavior and lock boundary

Use a dedicated `spec-kit` dependency group. uv includes the default `dev` group in ordinary project commands; adding `spec-kit` explicitly with `--group spec-kit` for CI installs it without making it part of normal default syncs. The CI install is resolved from the committed lockfile.

The setup invocation remains `uvx --from specify-cli==<version>`. uvx does not use this project's `uv.lock`, so the lockfile pins the group used by CI but does not pin uvx's transitive environment. The direct package version remains exact in both cases. Changing runtime to use the locked group would be a separate design decision and is outside this feature.

## Pin validation recommendation

Setup must not import `packaging` or any other third-party parser. Validate the one requirement string with a small standard-library check: exact package name, `==`, and stable numeric dot-separated version components; reject whitespace variants if they are not canonical, duplicate entries, markers, wildcards, ranges, prerelease/local suffixes, and malformed TOML. This is narrower than all PEP 440 exact forms but matches the current stable pin and project dependency practice. Keep the accepted format documented and tested.

## Sources

- Local behavior: `tools/setup`, `pyproject.toml`, `uv.lock`, `.github/workflows/ci.yml`, `tests/test_setup.py`, `tests/test_spec_workflow.py`.
- [uv dependency groups](https://docs.astral.sh/uv/concepts/dependencies/): groups are selectively included; explicit group selection supports the CI setup.
- [specify-cli 1.0.11 on PyPI](https://pypi.org/project/specify-cli/1.0.11/): release metadata, Python requirement, license, artifacts.
- [spec-kit v1.0.11 release](https://github.com/github/spec-kit/releases/tag/v1.0.11): upstream release identity.
- [spec-kit security advisories](https://github.com/github/spec-kit/security/advisories): checked for published upstream advisories.
- [spec-kit license](https://github.com/github/spec-kit/blob/v1.0.11/LICENSE): MIT license.
- Read-only dependency review by `/root/dep_research` (2026-10-14); no repository files or tests changed by the review.
