# ADR-0012: `ballast init` runs before a pin, as a tool the standard declares

- Status: proposed, agent-provisional (Autonomous run of [feature 13](../../specs/13-adaptive-init/plan.md)); accepted only when its PR merges
- Feature: [13-adaptive-init](../../specs/13-adaptive-init/spec.md), FR-001, FR-004, FR-014, FR-015, FR-016, FR-020, FR-021
- Extends: [ADR-0002](0002-cli-standard-manifest.md)

## Context

Every CLI command so far starts from the project's pin: `ballast.toml` names the standard version, and the CLI runs that version's tools from the per-machine cache, never from the checkout (ADR-0002, ADR-0008). Adopting a repository meant writing that pin by hand, copying the ignore block setup prints after refusing, adapting the copy-once templates and running setup. A command that adopts a repository has to run before any pin exists, and what it generates (the ignore block, installed paths, templates) differs per standard version.

## Decision

- `init` is the only CLI command that runs without `ballast.toml`. The CLI only bootstraps it: it chooses the ref (`--ref`, else its own release `v{VERSION}`; on a rerun the existing pin, which `init` never moves), fetches that version into the cache with the existing verified fetch (or uses `BALLAST_STANDARD_DIR`), and reads its `tools/cli.toml` as data.
- A version declares the tool with `[init] supported = true`. The CLI refuses, with exit 2 and before running anything from the standard or writing in the project, when the declaration is missing or the version's `[cli] minimum` is above the CLI's version; each refusal names the remedy (another `--ref`, a CLI upgrade, or moving the pin with `ballast preview` and a reviewed edit). `[cli] minimum` is not bumped for `init`.
- Otherwise the CLI runs that version's `tools/init` with `/usr/bin/python3 -IS` from the fetched directory, passing `--project ROOT --ref REF` and the remaining arguments.
- The standard owns inspection, generation and installation. `tools/init` reads a fixed, size-bounded list of evidence files as data, never executes a command it detects, runs git only with hooks, pager and fsmonitor disabled, creates only absent project-owned files (exclusively, never through a link), appends setup's ignore block when it is missing, writes every other proposed change to an existing file as one ignored patch (`.ballast/init/proposed.patch`), installs through the same version's `tools/setup` in process, and reports readiness.
- `init` never records trust, never commits, pushes or adds a remote, and adds no active headless-agent permission. The operator reviews the generated protected inputs and runs `ballast trust`.

## Consequences

- Generated files and the ignore block always match the version that installs them: one source per artifact, in the standard.
- Projects pinning versions without `[init]`, and older CLIs, keep working; an older CLI simply has no `init` subcommand.
- A rerun is a safe readiness check: it keeps the pin and every existing project file, and proposes drift as a patch.
- Fetching into the per-machine cache may precede a refusal; nothing is written in the project before one.

## Rejected alternatives

- All of init in the CLI: it would duplicate the ignore block, probes and templates per version and drift from the pinned setup.
- Probing for `tools/init` without a declaration: a file is not a contract, and an older version would be sent a command it does not know (ADR-0002).
- Letting `init` move a pin or regenerate `ballast.toml`: it would overwrite project-owned configuration; pin changes keep their reviewed path through `ballast preview`.
