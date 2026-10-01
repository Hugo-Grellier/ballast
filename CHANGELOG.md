# Changelog

Notable changes to this project are recorded here. This draft has no release version yet.

## Unreleased

### Added

- Initial repository structure and product and technical specifications.
- Starter `AGENTS.md` template.
- Spec Kit feature workflow with deterministic artifact postconditions, bounded headless agent wrapper and launcher (`tools/spec_workflow/`), with the Spec Kit spec/plan/tasks templates and regression tests. Imported from LoreForge (#104). The workflow id is `agentic-feature`, the tools install under `.agentic/spec_workflow/`, and shell steps use `python3`.
- `tools/setup` installs pinned Spec Kit sources, its patches and the workflow tooling into a project's git-ignored paths, merges project permissions from `agentic.toml`, refuses to run until the installed paths are ignored, and copies an existing installation into a new worktree. Generalized from LoreForge's `setup-speckit`.
- Agent run ledger and metrics (`ledger.py`, `ledger-schema.md`): append-only run events, acceptance checks bound to approved spec and manifest digests, and one-run and aggregate reports. Synced from LoreForge #112.
- Trusted operator launcher (`launcher.py`), installed outside the checkout as `agentic-workflow`, with a trusted-input baseline, a tamper marker and per-agent systemd scopes. Synced from LoreForge #113.
- `templates/policies/model-routing.md`, the quota-efficiency routing policy the ledger compares observed routes against. Installed projects read it from `docs/policies/model-routing.md`.
- `agentic-feature-intake` skill and its bounded `gh` helper for `Start/Fix/Investigate/Continue #N`, handing feature runs to `agentic-workflow`. Synced from LoreForge #105 and #113.
- `templates/policies/spec-kit-workflow.md`, the workflow guide, with project specifics moved to `docs/policies/project/`.
- `tools/setup` also installs the standard's skills, the intake helper and the policies, and ends by asking the operator to review and run `agentic-workflow trust`.
- `tools/agentic-workflow`, the global command installed once per machine. `setup` fetches the standard version pinned in `agentic.toml` (`[standard] ref`) and runs its `tools/setup`; every other command runs that version's launcher from outside the checkout.
- Review and routing skills (`agentic-engineering-review`, `-test-review`, `-documentation-review`, `-security-review`, `-spec-reconciliation`, `-dependency-evaluation`, `-dependency-migration`, `-database-migration`, `-model-routing`) and their base policies (engineering, documentation, testing, dependencies, migrations, observability, security, the risk and review `workflow`, issue tracker and triage labels). Each policy defers to a project's `docs/policies/project/<name>.md`. Generalized from LoreForge.
- `templates/AGENTS.md` carries the generic agent guide (artifacts, issue and spec workflow, risk table, conditional policy table, routing, PR rules) with project placeholders; `templates/github/pull_request_template.md` carries the PR template. Both are copied once, since agents and GitHub read them from committed files.
- This repository's CI runs the test suite.

### Changed

- Workflow tools no longer require Python 3.14: exception tuples are parenthesized.
- The base headless-agent permission list keeps only project-neutral rules; project commands and paths are added per project.
- Spec Kit templates, the workflow registry and the feature workflow are installed rather than committed in each project.

- The agent wrapper hashes bytecode, the whole `.venv`, `.specify/` and `agentic.toml`, runs agents without writing bytecode, and kills every descendant before its final check. Validators run under `python3 -I -S`. Headless steps now require Linux with a systemd user session. Synced from LoreForge #113.

### Fixed

- The Spec Kit skills patch no longer garbles the `implementation-defect` rule of `speckit-intent-decisions`.
