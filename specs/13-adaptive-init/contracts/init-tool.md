# Contract: `tools/init`

The standard tool that adopts a repository (R4 to R14 of [research.md](../research.md)). Runs under `/usr/bin/python3 -I -S`, standard library only, from the fetched standard directory (or `BALLAST_STANDARD_DIR`). Generated file formats are in [generated-files.md](generated-files.md).

## Invocation

```text
tools/init --project ROOT --ref REF [--description TEXT] [--stack python|node|rust|go|neutral]
```

Only the CLI is expected to call it. It loads the sibling `tools/setup` and `tools/spec_workflow/launcher.py` as modules and uses their `GITIGNORE`, `IGNORE_PROBES`, `GIT`, `PARENTS`, `_open_dir`, `printable`, `Setup`, `pinned_ref` and `_refusal`; it defines none of them again.

## Stages

| Stage | Does | Writes | Stops with |
| --- | --- | --- | --- |
| `check` | Validate arguments and ref; `ballast.toml`'s pin equals `--ref` when present; `git rev-parse --show-toplevel`; a link on any planned parent path or on `.gitignore`. | nothing | refusal (2): `inside the repository at X; run \`ballast init\` at its root`; `P is a symbolic link; init never writes through a link` |
| `inspect` | Read the fixed evidence list (R6); classify blank or established. | nothing | — (unusable files are skipped and reported) |
| `choose` | Description and stack: flag, else prompt on a terminal (blank only), else refuse. | nothing | refusal (2): `missing the product description; pass --description TEXT` / `missing the stack; pass --stack python\|node\|rust\|go\|neutral`; invalid value names the rule |
| `plan` | Build the profile and write plan; render every file and the patch; parse the rendered `ballast.toml` back. | nothing | failure (1) on a render error (a defect) |
| `git-init` | `git init --template=` only when no repository. | `.git/` | failure (1) |
| `ignore` | R8: probes; create or append the block; probe again; on conflict build the ignore proposal. | `.gitignore` | failure (1): `installed paths are not ignored: PATH (rule SOURCE:LINE:PATTERN)`; the patch is written first |
| `write` | Exclusive creates (R9) in this order: `ballast.toml`, `.specify/memory/constitution.md`, `docs/policies/project/testing.md`, `AGENTS.md`, `CLAUDE.md`. An existing path is kept, never replaced. | created files only | refusal (2) on a link met during the write; failure (1) on an OS error |
| `patch` | Write, replace or remove `.ballast/init/proposed.patch` (R10). | ignored patch | failure (1) |
| `install` | `Setup(root).main()` in process. | installed, ignored paths (setup's own contract) | setup's refusal (2) or stage failure (1), message prefixed `install:`; setup keeps the prior installation |
| `verify` | Readiness checks (R12). | nothing | — (results go to the report) |
| `report` | Print the report to stdout. | nothing | — |

Every git call uses `GIT` with stdin closed. Init's own stages start no other program: no detected command, no `gh`, no commit, push or remote (AC-015, AC-016, AC-018). During `install`, setup starts its own programs (`uvx`, `patch`, git) under its own contract (F-007). Init never writes `trusted.json` or any other operator state; setup's own installation record is setup's (AC-014).

## Exit codes

- `0`: the report has no `not-ready` check (warnings allowed).
- `1`: a stage failed, or a readiness check is `not-ready`.
- `2`: a refusal; in stages `check` to `plan` the target directory is untouched.

## Report (stdout)

```text
ballast init: established repository at ROOT (pin vX.Y.Z)
Written: ballast.toml, .specify/memory/constitution.md, docs/policies/project/testing.md
Kept: AGENTS.md, CLAUDE.md, .github/workflows/ci.yml
Appended the Ballast ignore block to .gitignore
Skipped evidence: package.json (parse error: ...)
To confirm (inferred): description; check "make check" (Makefile:12)
Proposed patch: .ballast/init/proposed.patch (AGENTS.md: Ballast section)
Readiness:
  instructions    warning    AGENTS.md has no Ballast section; see the proposed patch
  ignored-paths   ready      18 probes hold; created project files are not ignored
  pinned-version  ready      vX.Y.Z installed and current
  trust-boundary  ready      no trust baseline; the launcher refuses until `ballast trust`
  checks          warning    pytest: found; extra_allow does not cover "pytest" (see ballast.toml)
Not written (optional): templates/github/pull_request_template.md, dependabot.yml, workflows/pr-title.yml, stack CI; copy them from the standard's templates/github/ (README: Using the copy-once templates)
Review these protected inputs: ballast.toml, .specify/, .ballast/spec_workflow/
Next: review the files above, then run `ballast trust`
```

On a stop, instead of the readiness block:

```text
ballast init: stopped at STAGE: CAUSE
Written: ...
Not written: ...
Next: ACTION, then rerun `ballast init`
```

Lines are stable for tests; every value passes through `printable`.

## Reruns

The same stages run on an adopted or partial repository; `write` creates only what is absent, `install` is setup's no-op when current, and drift becomes proposals (R14). A second run on an adopted repository changes no tracked file and prints the same report (AC-028).
