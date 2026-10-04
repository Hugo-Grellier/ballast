# Contract: release asset, install line, `self-install`, `--version`

## Release assets (per tag `vX.Y.Z` from this feature on)

- `https://github.com/Hugo-Grellier/ballast/releases/download/vX.Y.Z/ballast`: byte-identical to `tools/ballast` at the tag.
- `https://github.com/Hugo-Grellier/ballast/releases/download/vX.Y.Z/ballast.sha256`: `sha256sum` output for the file named `ballast`.

Producer: the `publish-cli` job in `.github/workflows/release-please.yml`. Only this job has `contents: write`. It verifies its own checksum before uploading.

## Install line (documented in the README, the single copy that tests run)

The contract writes the version as `vX.Y.Z`. The README carries the same line with a real released version (initially the latest release, `v0.1.0`, until the first release with this feature, which Release Please then writes in), inside `<!-- x-release-please-start-version -->` … `<!-- x-release-please-end -->`, so each release bumps it. Tests compare the README line with this contract after replacing the version, and separately run the generic updater's substitution on the **unmodified** README to assert the command names the new version.

```sh
(c=$PATH; PATH=/usr/local/bin:/usr/bin:/bin; v=vX.Y.Z; u=https://github.com/Hugo-Grellier/ballast/releases/download/$v; d=$(TMPDIR=/tmp mktemp -d) && { curl -q -fsSL -o "$d/ballast" "$u/ballast" && curl -q -fsSL -o "$d/ballast.sha256" "$u/ballast.sha256" || { echo "ballast: cannot download $v from $u; nothing installed" >&2; false; }; } && { [ "$(cut -d" " -f1 "$d/ballast.sha256")" = "$(sha256sum <"$d/ballast" | cut -d" " -f1)" ] || { echo "ballast: checksum mismatch for $v; nothing installed" >&2; false; }; } && BALLAST_CALLER_PATH="$c" /usr/bin/python3 -I -S "$d/ballast" self-install)
```

Guarantees: each step runs only after the previous one succeeds. A failed download (unknown version, network loss) or a hash mismatch stops the line before `self-install`, so the existing install is untouched. Nothing is read from the cwd. The whole line runs in a subshell, so the caller's `PATH` is unchanged afterwards and `self-install` reports `PATH` membership against the caller's environment, which the line captures as `c=$PATH` before overriding it and passes as `BALLAST_CALLER_PATH`. Inside, the line uses a fixed system `PATH`, forces the temporary directory to `/tmp` (a caller `TMPDIR` inside a checkout is ignored), compares the expected hash as a value (a checksum file naming any other file cannot pass), and calls Python by absolute path, so a checkout-local `curl`, `sha256sum` or `python3` on the caller's `PATH` is never run. Test: shadow executables planted in the working directory and prepended to `PATH` are not invoked, a planted `sha256sum` that always succeeds cannot bypass verification, a checksum file listing another file fails, `TMPDIR` inside the checkout is ignored, and the caller's `PATH` is intact after the line.

## `ballast self-install [--dir DIR] [--force]`

Installs the running file's own bytes as `DIR/ballast` (default `DIR`: `~/.local/bin`). It does not need a project, and it neither reads nor writes `ballast.toml`.

| Situation | Exit | stdout / stderr (shape) |
| --- | --- | --- |
| no previous file | 0 | `installed ballast vX.Y.Z at DIR/ballast` |
| previous Ballast, other version | 0 | `replaced ballast vA.B.C with vX.Y.Z at DIR/ballast` |
| previous Ballast, version unknown | 0 | `replaced ballast (previous version unknown) with vX.Y.Z at …` |
| same version, same bytes | 0 | `ballast vX.Y.Z is already installed at …` |
| foreign file, directory or any symlink (DEC-0006), no `--force` | 2 | `ballast: DIR/ballast is not a Ballast command; rerun with --force to replace it` |
| I/O failure | 1 | `ballast: cannot install: <error>`; previous file unchanged, temporary file removed |

Every successful run then reports the `PATH` status:

- `DIR` on `PATH`: nothing more.
- otherwise: `DIR is not on PATH; add this line to your shell configuration:` followed by `export PATH="DIR:$PATH"` (AC-005).
- `/usr/bin/python3` missing or older than 3.11: a warning that names the required version, because the installed command uses that interpreter.

## `ballast --version`

Prints `vX.Y.Z` and exits 0. It needs no project and no network, and it runs before `ballast.toml` is read.

## Interpreter guard

On Python older than 3.11, every invocation prints `ballast: needs Python 3.11 or newer (found X.Y)` and exits 1, with no traceback.
