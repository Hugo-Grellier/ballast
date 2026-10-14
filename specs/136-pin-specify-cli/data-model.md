# Data Model: Setup CLI pin

## Authority

The standard checkout's `pyproject.toml` is the sole authority for the Spec Kit CLI version. The pin is stored as one entry in `[dependency-groups].spec-kit`:

```toml
[dependency-groups]
spec-kit = ["specify-cli==1.0.11"]
```

`uv.lock` records the resolved package and transitive dependencies for commands that install the group. It is not an alternate version authority for setup's `uvx` invocation.

## Parsed value

Setup derives the manifest path from its own standard root. It reads TOML using `tomllib`, requires exactly one `specify-cli` entry in the `spec-kit` list, and extracts the numeric stable version following `==`. The parsed version is immutable input for the duration of one setup process.

Missing group, missing entry, duplicate entry, non-string entry, non-exact requirement, unsupported version syntax, unreadable file, or malformed TOML is invalid state. Setup reports a refusal naming `pyproject.toml` and the cause before running any command that can download or execute `specify`.

## Derived uses

The validated version supplies:

- the `uvx --from specify-cli==<version>` argument;
- setup's freshness fingerprint, so a changed pin invalidates the existing installation;
- status, success, and installation-record fields that currently derive from the hard-coded constant.

No copy of the version is maintained in setup code. The source SHAs for Spec Kit core, extensions, and preset are separate pins and remain unchanged.
