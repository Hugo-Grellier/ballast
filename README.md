# Ballast

Ballast keeps a repository steady while AI coding agents move fast. It is a reusable, repository-level baseline: a Spec Kit feature workflow with deterministic artifact checks, a bounded headless-agent runner, review skills, engineering policies, and agent instruction templates.

This repository is the source of the standard. Projects pin a version and install it into git-ignored paths with `ballast setup`; only `AGENTS.md` and the PR template are copied once, because agents and GitHub read them from committed files.

## Repository map

- [`specs/PRODUCT-SPEC.md`](specs/PRODUCT-SPEC.md) describes the users, problem, goals, and product boundaries.
- [`specs/TECHNICAL-SPEC.md`](specs/TECHNICAL-SPEC.md) describes the repository structure and the conventions for template content.
- [`tools/ballast`](tools/ballast) is the global command; [`tools/setup`](tools/setup) installs Spec Kit and the standard into a project; [`tools/spec_workflow/`](tools/spec_workflow/) holds the validators, agent wrapper, trusted launcher and run ledger; [`tools/feature_intake.py`](tools/feature_intake.py) is the GitHub intake helper.
- [`templates/policies/`](templates/policies/) are the base policies installed into `docs/policies/`; [`templates/skills/`](templates/skills/) are the `ballast-*` skills; [`templates/spec-kit/`](templates/spec-kit/) holds the feature workflow and Spec Kit templates.
- [`templates/AGENTS.md`](templates/AGENTS.md) and [`templates/github/`](templates/github/) (PR template, Dependabot configuration, Conventional Commit PR-title workflow) are copy-once templates. Stack-specific CI stays in each project.
- `profiles/` is reserved for curated combinations of templates and will be added later.

## Using the copy-once templates

Review each template before copying it into a project. Replace project-specific placeholders, remove guidance that does not apply, and keep the resulting instructions close to the code they govern. Treat templates as a starting point, not as a substitute for the target project's own conventions.

## Installing the Ballast CLI

Once per machine, run this line. It downloads the `ballast` command of one release and its SHA-256 checksum into a fresh directory under `/tmp`, checks the checksum, and installs the command as `~/.local/bin/ballast`; on a mismatch or a failed download it installs nothing. It reads nothing from the current directory, so it is safe to run inside any checkout.

<!-- x-release-please-start-version -->
```sh
(c=$PATH; PATH=/usr/local/bin:/usr/bin:/bin; v=v0.2.0; u=https://github.com/Hugo-Grellier/ballast/releases/download/$v; d=$(TMPDIR=/tmp mktemp -d) && { curl -q -fsSL -o "$d/ballast" "$u/ballast" && curl -q -fsSL -o "$d/ballast.sha256" "$u/ballast.sha256" || { echo "ballast: cannot download $v from $u; nothing installed" >&2; false; }; } && { [ "$(cut -d" " -f1 "$d/ballast.sha256")" = "$(sha256sum <"$d/ballast" | cut -d" " -f1)" ] || { echo "ballast: checksum mismatch for $v; nothing installed" >&2; false; }; } && BALLAST_CALLER_PATH="$c" /usr/bin/python3 -I -S "$d/ballast" self-install)
```
<!-- x-release-please-end -->

If the download fails with 404, that release predates the installer; use the developer fallback below.

Then check the machine and, from a project root, the project:

```bash
ballast --version
ballast doctor            # add --json for a machine-readable report
```

`ballast doctor` is read-only: it downloads and writes nothing. It reports each prerequisite as passing, missing, unsupported or inconclusive, names the commands each gap blocks and gives the exact fix, and exits 1 while any command is blocked. Its checks are the authoritative prerequisite list; in summary:

- `python`: `/usr/bin/python3` 3.11 or newer, which runs every Ballast tool.
- `cli-on-path`: the `ballast` command on `PATH`.
- `git`, `uvx` and `patch` for `ballast setup`, and `network`: HTTPS access to GitHub and PyPI the first time a version is fetched.
- `linux`, `systemd-user` and `systemd-run`: headless agent steps of `ballast run` need Linux with a systemd user session that can start transient scopes.
- `specify` (the Spec Kit CLI) and `agent-cli` (Claude Code or Codex) for `ballast run`.
- `gh`, authenticated, for issue intake and PR steps.

Inside a project it also checks the pin in `ballast.toml`, whether that version is fetched, the CLI version it needs, whether setup is current, and whether the launcher would refuse until `ballast trust`.

To develop the standard itself, install from a reviewed checkout of this repository instead: `install -m 0755 tools/ballast ~/.local/bin/ballast`.

## Installing the Spec Kit workflow

`tools/setup` installs pinned Spec Kit sources and this standard's workflow tooling into a project. Everything it writes is rebuildable and git-ignored; the project commits only its own files. Projects reach it through one global command:

1. Once per machine, install the `ballast` command (see [Installing the Ballast CLI](#installing-the-ballast-cli)) and run `ballast doctor`.
2. Add `ballast.toml` at the project root. It pins the standard version (a tag or commit) and can extend the headless-agent permissions:

   ```toml
   [standard]
   ref = "v0.1.0"

   [agents.permissions]
   extra_allow = ["Bash(./scripts/check)"]
   extra_deny = ["Edit(./private/**)"]
   ```

3. From the project root, run `ballast setup`. It downloads the pinned version once into `$XDG_DATA_HOME/ballast/standard/<ref>/`, then runs its `tools/setup`. On the first run, add the ignore block it prints to the project's `.gitignore`; the block keeps `.specify/memory/constitution.md` tracked. Setup needs `git`, `uvx`, `patch`, and network access to GitHub; `ballast doctor` checks them.

The result is Spec Kit with its bugfix and assess bundles, the multi-model-review, status-report and intent extensions, the explicit-task-dependencies preset, the `ballast-feature` workflow and its tools under `.ballast/`, the `ballast-*` skills under `.agents/skills/` (linked from `.claude/skills/`), and the standard's policies under `docs/policies/`. Project-specific additions go in `docs/policies/project/`, which setup never touches. A rerun is a no-op until this repository or `ballast.toml` changes. A new Git worktree copies the installation from its primary checkout when both match. A reinstall keeps `.specify/workflows/runs/` and the project constitution.

### Running the workflow

Headless agent steps need Linux with a systemd user session. The operator entry point must live outside the checkout, because an agent can rewrite anything inside it. `ballast` therefore runs the launcher of the project's pinned version from `$XDG_DATA_HOME/ballast/standard/<ref>/`, never from the checkout:

```bash
ballast trust                 # from the reviewed project root
ballast run start|resume ...
ballast ledger snapshot|check|report ...
```

Only `setup` downloads; the other commands refuse a version that is not fetched yet. The repository is fixed in `ballast`, so `ballast.toml` chooses a version, never a source. Run `trust` again after reviewing any change to `ballast.toml`, `.ballast/`, `.specify/` or `.venv/`, including a rerun of setup. To work on the standard itself, set `BALLAST_STANDARD_DIR` to a local checkout. The launcher refuses to run while those inputs differ from the trusted baseline, while an `BALLAST_TAMPERED` marker exists, or after an agent step that did not finish its check. Its baseline and the agent run ledger live in `$XDG_STATE_HOME/ballast/`.

At the end of every `ballast run` invocation the launcher makes sure one Draft PR shows an issue-linked feature once its published branch holds a change outside `specs/<feature>/`, and reuses that PR afterwards. It uses your authenticated `gh` 2.48 or later, never pushes, and never marks a PR ready, merges or closes it. The [Draft PR section of the Spec Kit workflow policy](templates/policies/spec-kit-workflow.md#draft-pr) lists the reported states and their remedies.

## Dogfooding

This repository installs Ballast like any project: `ballast.toml` pins a released version, `AGENTS.md` comes from the template, and Ballast-specific rules live in `docs/policies/project/` and `.specify/memory/constitution.md`. CI installs the working copy into the repository on every PR and fails if the install leaves any file that is not ignored.

## Releases

Release Please opens a release PR from Conventional Commit titles on `main`; merging it tags `vX.Y.Z`, updates `CHANGELOG.md`, `version.txt`, the CLI's `VERSION` and the install line above, and publishes the GitHub release. A follow-up job attaches the unchanged `tools/ballast` and its `ballast.sha256` to that release, for the install line. Projects pin those tags in `ballast.toml`. The workflow needs a `RELEASE_PLEASE_TOKEN` repository secret (a fine-grained token with contents and pull-request write access) so its release PR runs CI.

## Status

Draft, backported from LoreForge. The [backport plan](docs/plans/2026-09-28-loreforge-backport.md) tracks parity before the first release; profiles are not yet defined.
