# Quickstart: Pin specify-cli

## Change the pin

1. Edit the single `specify-cli==...` entry under `[dependency-groups].spec-kit` in `pyproject.toml`.
2. Refresh `uv.lock` with the repository's locked uv workflow.
3. Review the upstream release diff and license, then verify the patches under `tools/spec-kit/` still apply and the CLI-dependent tests pass.

The setup source should not need an edit for a version bump. The setup invocation uses the version from the standard checkout's manifest; the consuming project's manifest has no effect.

## Verify behavior

- Run the focused setup tests for the valid pin, pin-change fingerprint, standard-root lookup, and refusal cases.
- Run the full unittest suite with the `spec-kit` group installed, as CI does, and confirm CLI-gated tests run rather than skip.
- Run the repository lint and format checks required by the project gate.
- Confirm the pinned source SHAs in `tools/setup` did not change.

An invalid, missing, duplicate, or non-exact pin must fail before `uvx` runs. The refusal should identify `pyproject.toml` and the invalid declaration.
