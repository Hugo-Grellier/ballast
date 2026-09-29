# Changelog

Notable changes to this project are recorded here. This draft has no release version yet.

## Unreleased

### Added

- Initial repository structure and product and technical specifications.
- Starter `AGENTS.md` template.
- Spec Kit feature workflow with deterministic artifact postconditions, bounded headless agent wrapper and launcher (`tools/spec_workflow/`), with the Spec Kit spec/plan/tasks templates and regression tests. Imported from LoreForge (#104). The workflow id is `agentic-feature`, the tools install under `.agentic/spec_workflow/`, and shell steps use `python3`.
- `tools/setup` installs pinned Spec Kit sources, its patches and the workflow tooling into a project's git-ignored paths, merges project permissions from `agentic.toml`, refuses to run until the installed paths are ignored, and copies an existing installation into a new worktree. Generalized from LoreForge's `setup-speckit`.

### Changed

- Workflow tools no longer require Python 3.14: exception tuples are parenthesized.
- The base headless-agent permission list keeps only project-neutral rules; project commands and paths are added per project.
- Spec Kit templates, the workflow registry and the feature workflow are installed rather than committed in each project.

### Fixed

- The Spec Kit skills patch no longer garbles the `implementation-defect` rule of `speckit-intent-decisions`.
