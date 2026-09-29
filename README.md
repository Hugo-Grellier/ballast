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

## Status

Initial draft. The structure and scope are documented; policies, skills, GitHub templates, and profiles have not yet been populated.
