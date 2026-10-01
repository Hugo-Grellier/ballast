# Agentic Repo Standard

Agentic Repo Standard is a reusable, repository-level baseline for working with AI coding agents. It defines clear project instructions and a place to add reusable policies, skills, and GitHub workflow templates.

This repository is the source of the standard. The files under `templates/` are intended to be copied or adapted into another repository; they are not automatically installed.

## Repository map

- [`specs/PRODUCT-SPEC.md`](specs/PRODUCT-SPEC.md) describes the users, problem, goals, and product boundaries.
- [`specs/TECHNICAL-SPEC.md`](specs/TECHNICAL-SPEC.md) describes the repository structure and the conventions for template content.
- [`templates/AGENTS.md`](templates/AGENTS.md) is the starting point for repository-specific agent instructions.
- `templates/policies/`, `templates/skills/`, and `templates/github/` are extension points for future reusable material.
- `profiles/` is reserved for curated combinations of templates and will be added later.

## Using the templates

Review each template before copying it into a project. Replace project-specific placeholders, remove guidance that does not apply, and keep the resulting instructions close to the code they govern. Treat templates as a starting point, not as a substitute for the target project's own conventions.

## Installing the Spec Kit workflow

`tools/setup` installs pinned Spec Kit sources and this standard's workflow tooling into a project. Everything it writes is rebuildable and git-ignored; the project commits only its own files. Projects reach it through one global command:

1. Once per machine, from a reviewed checkout of this repository: `install -m 0755 tools/agentic-workflow ~/.local/bin/agentic-workflow`.
2. Add `agentic.toml` at the project root. It pins the standard version (a tag or commit) and can extend the headless-agent permissions:

   ```toml
   [standard]
   ref = "v0.1.0"

   [agents.permissions]
   extra_allow = ["Bash(./scripts/check)"]
   extra_deny = ["Edit(./private/**)"]
   ```

3. From the project root, run `agentic-workflow setup`. It downloads the pinned version once into `$XDG_DATA_HOME/agentic/standard/<ref>/`, then runs its `tools/setup`. On the first run, add the ignore block it prints to the project's `.gitignore`; the block keeps `.specify/memory/constitution.md` tracked. Setup needs `git`, `uvx`, `patch`, and network access to GitHub.

The result is Spec Kit with its bugfix and assess bundles, the multi-model-review, status-report and intent extensions, the explicit-task-dependencies preset, the `agentic-feature` workflow and its tools under `.agentic/`, the `agentic-*` skills under `.agents/skills/` (linked from `.claude/skills/`), and the standard's policies under `docs/policies/`. Project-specific additions go in `docs/policies/project/`, which setup never touches. A rerun is a no-op until this repository or `agentic.toml` changes. A new Git worktree copies the installation from its primary checkout when both match. A reinstall keeps `.specify/workflows/runs/` and the project constitution.

### Running the workflow

Headless agent steps need Linux with a systemd user session. The operator entry point must live outside the checkout, because an agent can rewrite anything inside it. `agentic-workflow` therefore runs the launcher of the project's pinned version from `$XDG_DATA_HOME/agentic/standard/<ref>/`, never from the checkout:

```bash
agentic-workflow trust                 # from the reviewed project root
agentic-workflow run start|resume ...
agentic-workflow ledger snapshot|check|report ...
```

Only `setup` downloads; the other commands refuse a version that is not fetched yet. The repository is fixed in `agentic-workflow`, so `agentic.toml` chooses a version, never a source. Run `trust` again after reviewing any change to `agentic.toml`, `.agentic/`, `.specify/` or `.venv/`, including a rerun of setup. To work on the standard itself, set `AGENTIC_STANDARD_DIR` to a local checkout. The launcher refuses to run while those inputs differ from the trusted baseline, while an `AGENTIC_TAMPERED` marker exists, or after an agent step that did not finish its check. Its baseline and the agent run ledger live in `$XDG_STATE_HOME/agentic/`.

## Status

Initial draft. The Spec Kit workflow tooling is backported from LoreForge; policies, skills, GitHub templates, and profiles have not yet been populated.
