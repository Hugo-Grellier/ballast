# Contract: Manifest-pinned Spec Kit CLI for setup

## Authority and parsing

- `tools/setup` reads `<standard-root>/pyproject.toml`, where the root is derived from the setup script location.
- `[dependency-groups].spec-kit` contains exactly one requirement for `specify-cli`.
- The accepted requirement is a canonical exact stable numeric pin of the form `specify-cli==N.N...`; ranges, markers, wildcards, duplicates, malformed TOML, and unsupported version forms are refused.
- Parsing uses only Python's standard library and works under `python3 -I -S`.

## Failure behavior

- Resolve and validate the pin before invoking `uvx`, `specify`, or another operation that downloads or executes the CLI.
- Invalid input exits with setup's existing refusal behavior and an actionable error naming `pyproject.toml` and the specific problem.
- `--check` reads the same authoritative pin and reflects it in the same fingerprint calculation; it remains read-only.

## Valid behavior

- Every setup CLI invocation uses exactly the parsed version.
- The fingerprint and install reporting use that same value.
- A version change makes the prior installation stale.
- A consuming project's `pyproject.toml` is never consulted.

## CI contract

The pull request test job explicitly installs the `spec-kit` dependency group from `uv.lock` before running the full unittest suite. This makes the CLI-dependent tests execute on each pull request. Ordinary default `uv sync --locked` does not include this group.
