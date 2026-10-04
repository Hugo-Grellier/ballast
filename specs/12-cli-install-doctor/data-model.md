# Data Model: One-command CLI install and `ballast doctor`

## Installed CLI

| Field | Source | Rule |
| --- | --- | --- |
| `version` | `VERSION` constant in the file | `X.Y.Z`; printed as `vX.Y.Z` |
| `location` | `self-install --dir`, default `~/.local/bin/ballast` | user-owned and outside any project checkout |
| `digest` | SHA-256 of the file bytes | equals the release's `ballast.sha256` (AC-002) |

Classification of an existing file at the install target:

```text
absent            → install
ballast(same ver, same bytes) → no-op, success
ballast(other or unknown ver) → replace atomically, report previous → new
foreign / directory           → refuse (exit 2) unless --force
```

## Release CLI asset

| Field | Rule |
| --- | --- |
| tag | `vX.Y.Z` created by Release Please |
| `ballast` | byte-identical to `tools/ballast` at the tag |
| `ballast.sha256` | one line, `<64 hex>  ballast` (the `sha256sum` format) |

Releases before the first one carrying this feature have no asset. The install line fails on `curl -f` and changes nothing.

## Standard manifest (`tools/cli.toml`, in each standard version from this feature on)

| Key | Type | Meaning |
| --- | --- | --- |
| `[cli] minimum` | `"X.Y.Z"` | lowest CLI version this standard version works with |
| `[doctor] probes` | list of strings from {`setup-check`, `launcher-status`} | read-only probes this version supports |

An absent manifest means a version older than this feature: no CLI minimum and no probes. Unknown probe names are ignored.

## Prerequisite check

| Field | Type | Rule |
| --- | --- | --- |
| `name` | string | stable identifier (table below); used in JSON and in the README summary |
| `scope` | `machine` \| `project` | |
| `status` | `passing` \| `missing` \| `unsupported` \| `inconclusive` \| `skipped` | |
| `gates` | list of strings | commands or steps blocked when the check is not passing |
| `detail` | string | short observed fact, never a credential value |
| `remedy` | string \| null | required unless the status is `passing` or `skipped` |

Machine checks: `python`, `cli-on-path`, `git`, `uvx`, `patch`, `network`, `linux`, `systemd-user`, `systemd-run`, `specify`, `agent-cli`, `gh`. Probes and gates are in [research.md R7](research.md#r7-machine-checks).

Project checks: `ballast-toml`, `standard-fetched`, `cli-version`, `setup-current`, `trust`. Logic is in [research.md R8](research.md#r8-project-checks-and-the-read-only-probes-fr-010-ac-013016).

Dependencies: when `ballast-toml` fails, the later project checks are `skipped`. When `standard-fetched` fails, `cli-version`, `setup-current` and `trust` are `skipped` with remedy context "after `ballast setup`". When `linux` is not passing, `systemd-user` and `systemd-run` are `unsupported`.

## Doctor report

| Field | Rule |
| --- | --- |
| `schema` | `1` |
| `cli_version` | `VERSION` |
| `project` | absolute root, or `null` outside a project |
| `standard` | `{ "ref": str \| null, "path": str \| null, "local": bool }` |
| `checks` | ordered: machine checks, then project checks |
| `verdict` | `ok` when no check is `missing`/`unsupported`, otherwise `blocked` |
| `blocked` | sorted union of `gates` over the blocking checks |

The exit code is 0 for `ok` and 1 for `blocked`. Formal shape: [contracts/doctor-report.schema.json](contracts/doctor-report.schema.json).
