# Data model: Adapt Ballast to blank and established repositories

In-memory structures of `tools/init` and the files it writes. Nothing here is persisted by init except the generated project-owned files, the `.gitignore` change and the ignored patch; init writes no operator state of its own. Decisions are in [research.md](research.md); formats in [contracts/](contracts/).

## Target repository

| Field | Type | Rule |
| --- | --- | --- |
| `root` | path | The resolved working directory the CLI passes as `--project`. |
| `git` | `none` \| `repository` | From `git rev-parse --show-toplevel` (R13). A different toplevel refuses in `check`. |
| `kind` | `blank` \| `established` | `blank` when the root holds no entry other than `.git`; otherwise `established`. |
| `pinned` | ref or none | `[standard] ref` of an existing `ballast.toml` (adopted or partial repository). |

## Evidence item

One entry of the fixed list (R6), recorded whether or not it was usable.

| Field | Type | Rule |
| --- | --- | --- |
| `path` | relative path | From the fixed list only; never outside the root. |
| `kind` | `manifest` \| `lockfile` \| `makefile` \| `ci` \| `instructions` \| `architecture` \| `policy` \| `remote` | |
| `status` | `read` \| `present` \| `skipped` | `present`: existence-only kinds. |
| `reason` | text, when `skipped` | `symbolic link`, `not a regular file`, `larger than 256 KiB`, `not UTF-8`, `parse error: ...`, `more than 20 workflows`. Reported (AC-017, AC-025). |

## Detected value

| Field | Type | Rule |
| --- | --- | --- |
| `key` | `description` \| `stack` \| `check` \| `github` \| `architecture` \| `adr` \| `policy` | |
| `value` | single-line text | Control characters escaped; no backtick (R15). |
| `source` | `PATH:LINE`, `PATH`, `git remote origin`, `operator` or none | `operator` for a flag or prompt answer. |
| `confidence` | `direct` \| `inferred` \| `operator` | `inferred` values are written inactive and marked (FR-011, FR-012). |

Validation: a `check` is `direct` only by R7's rules; a command found as both keeps `direct` and the first direct source; `github` matches `OWNER/REPO` (R13).

## Project profile

The minimal choices init derives, every one a detected value:

| Field | Blank repository | Established repository |
| --- | --- | --- |
| `ref` | `--ref` or `v{CLI VERSION}` | the existing pin, else as blank |
| `description` | operator (flag or prompt; material) | manifest `description`, else `TO CONFIRM` (never asked) |
| `stack` | operator: `python`, `node`, `rust`, `go` or `neutral` | detected stacks, else `neutral` (inferred) |
| `checks` | inferred gate of the chosen stack (inactive) | direct and inferred commands (R7) |
| `github` | from `origin` if any, else omitted | same |
| `permissions` | commented `extra_allow` per check, inferred | same |

## Write plan

Computed in stage `plan` before the first write; the report's "written" and "not written" lists come from it.

| Entry | Fields | Rule |
| --- | --- | --- |
| `create` | path, bytes or link target | Only when the path does not exist (`lstat`); exclusive create (R9). |
| `ignore` | `none` \| `create` \| `append` | R8; the only change to an existing tracked file (FR-007). |
| `proposal` | path, original bytes, proposed bytes, reason | Becomes a hunk of the init patch (R10). |
| `git_init` | bool | True only when `git` is `none`. |

Invariant: no `create` path exists before the write; no `proposal` path is ever written.

## Init patch

`.ballast/init/proposed.patch`: unified diff of every `proposal`, `a/`/`b/` prefixes, files in path order; absent when there is no proposal; printed instead when the path is not ignored (R10).

## Readiness report

| Field | Type | Rule |
| --- | --- | --- |
| `kind` | `blank` \| `established` | |
| `written`, `kept` | path lists | `kept`: planned targets that already existed. |
| `skipped_evidence` | evidence items with reasons | |
| `inferred` | detected values to confirm | |
| `patch` | path or `none` | |
| `checks` | list of `(name, status, detail)` | names `instructions`, `ignored-paths`, `pinned-version`, `trust-boundary`, `checks`; status `ready` \| `warning` \| `not-ready` (R12). |
| `integrations` | list | Optional files not written, each with how to add it (FR-017). |
| `protected_inputs` | path list | `ballast.toml`, `.specify/`, `.ballast/spec_workflow/`. |
| `next` | text | `ballast trust` before trust; `ballast run ...` when a matching baseline exists. |

## Stages and transitions

```text
check → inspect → choose → plan ─┬─ (refusal: exit 2, target untouched)
                                 └→ git-init → ignore ─┬─ conflict: patch, stop (exit 1)
                                                       └→ write → patch → install ─┬─ setup refused/failed: stop (exit 2/1), prior installation kept
                                                                                   └→ verify → report (exit 0, or 1 if not-ready)
```

A stop at any stage reports the stage, the written paths, the planned paths not written and how to continue (AC-034). A rerun starts again at `check` and completes only what is absent (AC-030).
