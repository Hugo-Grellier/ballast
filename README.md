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

`tools/setup` installs pinned Spec Kit sources and this standard's workflow tooling into a project. Everything it writes is rebuildable and git-ignored; the project commits only its own files.

1. Add the ignore block that `tools/setup` prints on its first run to the project's `.gitignore`. The block keeps `.specify/memory/constitution.md` tracked.
2. Optionally add `agentic.toml` at the project root to extend the headless-agent permissions:

   ```toml
   [agents.permissions]
   extra_allow = ["Bash(./scripts/check)"]
   extra_deny = ["Edit(./private/**)"]
   ```

3. From a checkout of this repository, run `tools/setup --project /path/to/project`. It needs `git`, `uvx`, `patch`, and network access to GitHub.

The result is Spec Kit with its bugfix and assess bundles, the multi-model-review, status-report and intent extensions, the explicit-task-dependencies preset, the `agentic-feature` workflow and its tools under `.agentic/`, the `agentic-*` skills under `.agents/skills/` (linked from `.claude/skills/`), and the standard's policies under `docs/policies/`. Project-specific additions go in `docs/policies/project/`, which setup never touches. A rerun is a no-op until this repository or `agentic.toml` changes. A new Git worktree copies the installation from its primary checkout when both match. A reinstall keeps `.specify/workflows/runs/` and the project constitution.

### Running the workflow

Headless agent steps need Linux with a systemd user session. The operator entry point lives outside the checkout, because an agent can rewrite anything inside it:

```bash
install -m 0755 .agentic/spec_workflow/launcher.py ~/.local/bin/agentic-workflow
agentic-workflow trust                 # from the reviewed project root
agentic-workflow run start|resume ...
agentic-workflow ledger snapshot|check|report ...
```

Install the launcher again whenever `launcher.py` changes, and run `trust` again after reviewing any change to `agentic.toml`, `.agentic/`, `.specify/` or `.venv/`, including a rerun of `tools/setup`. The launcher refuses to run while those inputs differ from the trusted baseline, while an `AGENTIC_TAMPERED` marker exists, or after an agent step that did not finish its check. Its baseline and the agent run ledger live in `$XDG_STATE_HOME/agentic/`.

## Status

Initial draft. The Spec Kit workflow tooling is backported from LoreForge; policies, skills, GitHub templates, and profiles have not yet been populated.
