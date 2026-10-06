# Contract: `ballast init` in the global CLI

The CLI part of `ballast init` (R1 to R3 of [research.md](../research.md)). The CLI only bootstraps; [init-tool.md](init-tool.md) owns everything after `execv`.

## Synopsis

```text
ballast init [--ref REF] [--description TEXT] [--stack python|node|rust|go|neutral]
```

`init` is dispatched in `main` before `command_standard`, like `doctor` and `preview`, so it never calls `pinned_ref` on a missing `ballast.toml`. The CLI parses only `--ref` (`parse_known_args`); every other argument passes to the tool unchanged.

## Order

1. Root = `Path.cwd()`.
2. Ref:
   - no `ballast.toml` (`lstat`): `--ref` when given, else `v{VERSION}`;
   - `ballast.toml` present: `read_pin(root)`; an error refuses with it. A `--ref` different from the pin refuses: `ballast: refusing: ballast.toml pins PIN; init keeps the pin. To move it, run \`ballast preview REF\`, then edit the pin`.
   - The ref must match `REF` and contain no `..`, else refuse.
3. Standard: `BALLAST_STANDARD_DIR` set → that directory (the existing "using local standard" notice); else `ensure_standard(root, ref)` (the cache outside the repository; its existing fetch failure message).
4. Manifest, read as data (`tomllib`): refuse unless `[init] supported = true`: `ballast: refusing: standard REF has no \`init\`; pass --ref with a release that has it, or upgrade the CLI`. Refuse when `[cli] minimum` is above `VERSION`, naming the install line for that minimum (as doctor's `cli-version` remedy).
5. `os.execv("/usr/bin/python3", ["/usr/bin/python3", "-IS", STANDARD/tools/init, "--project", ROOT, "--ref", REF, *rest])`.

Every refusal exits 2 and happens before step 5, with nothing written in the root (AC-033, FR-020). Steps 1 to 4 write only the per-machine cache (PD-0014).

## Manifest addition (`tools/cli.toml`)

```toml
[init]
# `ballast init` runs this version's tools/init before a project pins it (#13).
supported = true
```

`[cli] minimum` is unchanged. A version without `[init]` predates init.

## Other CLI changes

- `USAGE` and the module docstring list `init`.
- A missing or unreadable `ballast.toml` for `setup`, `trust`, `run`, `ledger` and `intake` names `ballast init` in its message; doctor's `PIN_REMEDY` names `ballast init` first, then the manual pin.
- No other command changes; `doctor` stays read-only and never runs init.
