# Ballast Constitution

## Core principles

1. **Projects own only their own files (BL-INV-001).** A project commits `ballast.toml`, its constitution, `docs/policies/project/` and the copy-once templates it adopted. Everything `tools/setup` installs is git-ignored, rebuildable from the pinned version, and refused when the project does not ignore it.
2. **Nothing executes from a writable checkout before trust (BL-INV-002).** The `ballast` command runs the launcher of the pinned, fetched version, never one from the checkout. The launcher refuses until the operator trusts the current inputs, and fails closed on a tamper marker or an unfinished agent step.
3. **Delegated authority (BL-INV-003).** A headless agent never gains more authority than its caller. It cannot edit `ballast.toml`, the installed tools or run state; a change to a protected input fails the step.
4. **A project picks a version, never a source (BL-INV-004).** The repository `ballast` downloads from is fixed in the command; `ballast.toml` only selects a tag or commit.
5. **Postconditions over exit codes (BL-INV-005).** A workflow phase succeeds only when its artifact contract holds; an agent exiting 0 proves nothing.
6. **Portable, dependency-free tools.** Workflow tools use only the Python standard library and run under `python3 -I -S`, so a planted `.pth` or bytecode cannot run in operator commands.
7. **Generic by default.** Shipped material carries no project's names or domain rules; projects extend policies through `docs/policies/project/<name>.md`.
8. **Executable evidence.** Behavior changes need tests that fail when the behavior breaks, including refusal and tamper paths.

## Governance

The specifications in `specs/` describe intent; this constitution states the invariants a change must preserve. A change that weakens an invariant needs explicit human approval as R2 and a recorded reason. Amend this constitution through a reviewed change that states the reason and compatibility impact for projects pinning earlier versions.

**Version**: 1.0.0 | **Ratified**: 2026-10-02 | **Last Amended**: 2026-10-02
