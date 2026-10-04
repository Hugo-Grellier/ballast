# ADR-0001: Distribute the CLI as a checksummed release asset

- Status: accepted (with the plan of [feature 12](../../specs/12-cli-install-doctor/plan.md), 2026-10-03)
- Feature: [12-cli-install-doctor](../../specs/12-cli-install-doctor/spec.md), FR-001 to FR-007

## Context

Operators installed the global `ballast` command by copying `tools/ballast` from a reviewed checkout. That needs a clone, a revision chosen by hand, and leaves no record of the installed version. The command is the operator-side root of the trust model (BL-INV-002, BL-INV-004), so how it is obtained is an R2 decision.

## Decision

- Each tagged release carries the unchanged `tools/ballast` at the tag as the asset `ballast`, and `ballast.sha256` (`sha256sum` output for it).
- A `publish-cli` job in `.github/workflows/release-please.yml` builds both from the tagged tree, verifies the checksum and uploads them. It runs only when Release Please created a release, and it alone has `contents: write`; the workflow default stays `contents: read`.
- Operators install with the single line in [contracts/install.md](../../specs/12-cli-install-doctor/contracts/install.md), which the README carries with a real version that Release Please bumps. It runs in a subshell with a fixed system `PATH` and a temporary directory under `/tmp`, compares the published hash as a value, and only then runs `/usr/bin/python3 -I -S "$d/ballast" self-install`.
- `self-install` replaces `~/.local/bin/ballast` atomically, verifies the written bytes before the rename, refuses a target that is not a regular Ballast file, including any symlink, unless `--force` is given and refuses any directory inside a Git working tree.
- The CLI carries `VERSION`, bumped by Release Please, and prints it with `ballast --version`.

## Consequences

- No clone is needed, and the installed file is byte-identical to the reviewed `tools/ballast`, keeping its `-I -S` isolation.
- A checksum fetched from the same origin detects corruption and truncation, not a compromised release or account. Signing (for example cosign or minisign) is out of scope and would need a new decision.
- Releases before the first one carrying this job have no asset; the line fails with a 404 and changes nothing, and the README points to the developer fallback.

## Rejected alternatives

- `curl … | sh`: executes unreviewed network code before any check.
- `uv tool install` or `pipx`: turns the repository into a Python package and runs the launcher from a virtual environment without `-I -S`.
- A raw-file link to `tools/ballast` at the tag: no integrity reference is published with the release (FR-002).
