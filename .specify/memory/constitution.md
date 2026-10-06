# Ballast Constitution

## Core principles

1. **Projects own only their own files (BL-INV-001).** A project commits `ballast.toml`, its constitution, `docs/policies/project/` and the copy-once templates it adopted. Everything `tools/setup` installs is git-ignored, rebuildable from the pinned version, and refused when the project does not ignore it.
2. **Nothing executes from a writable checkout before trust (BL-INV-002).** The `ballast` command runs the launcher of the pinned, fetched version, never one from the checkout. The launcher refuses until the operator trusts the current inputs, or until the operator's `ballast setup` or worktree preparation recorded them under the conditions of ADR-0015 (the checkout holds exactly what setup installed, its committed configuration equals what a human reviewed, and no agent has run there), and fails closed on a tamper marker or an unfinished agent step.
3. **Delegated authority (BL-INV-003).** A headless agent never gains more authority than its caller. It cannot edit `ballast.toml`, the installed tools or run state; a change to a protected input fails the step.
4. **A project picks a version, never a source (BL-INV-004).** The repository `ballast` downloads from is fixed in the command; `ballast.toml` only selects a tag or commit.
5. **Postconditions over exit codes (BL-INV-005).** A workflow phase succeeds only when its artifact contract holds; an agent exiting 0 proves nothing.
6. **Portable, dependency-free tools.** Workflow tools use only the Python standard library and run under `python3 -I -S`, so a planted `.pth` or bytecode cannot run in operator commands.
7. **Generic by default.** Shipped material carries no project's names or domain rules; projects extend policies through `docs/policies/project/<name>.md`.
8. **Executable evidence.** Behavior changes need tests that fail when the behavior breaks, including refusal and tamper paths.
9. **A provisional decision is never human approval (BL-INV-006).** A provisional decision is never human approval; only merging the PR that contains it accepts it. In an Autonomous run, agents record agent-provisional decisions at the points where a human-gated run asks for approval; no artifact, record or PR text may present one as human-approved, and validators in an Autonomous run refuse every human-approval record. Human-gated runs keep their approvals unchanged.

## Governance

The specifications in `specs/` describe intent; this constitution states the invariants a change must preserve. A change that weakens an invariant needs explicit human approval as R2 and a recorded reason. Amend this constitution through a reviewed change that states the reason and compatibility impact for projects pinning earlier versions.

## Amendment history

- **1.1.0** (2026-10-04, #27): adds BL-INV-006. Reason: Autonomous runs move every intermediate approval, including the R2 pre-change approval, to a single human merge approval; the invariant keeps agent decisions from ever counting as that approval. Compatibility: projects pinning an earlier Ballast version see no change; projects that upgrade keep human-gated runs as before and gain the Autonomous mode only when the operator selects it. `ballast setup` preserves a project's own constitution and never rewrites it with this amendment.
- **1.2.0** (2026-10-06, #55): amends BL-INV-002 so a baseline recorded by the operator's `ballast setup` or worktree preparation under ADR-0015's conditions also counts. Reason: every fresh clone, issue worktree and pilot repository cost one human `ballast trust` although every protected input had just been written by the operator's own setup of the pinned standard from configuration already reviewed; the amendment removes that command only where nothing unreviewed can be recorded (committed configuration equal to the pinned repository's default branch or to the operator's own earlier baseline, no extra protected input, no run state, no marker), and the launcher's comparison before every run is unchanged. Compatibility: projects pinning an earlier Ballast version see no change; projects that upgrade need one `ballast trust` per machine to record the repository and the reviewed configuration, after which fresh checkouts of that configuration need none (a changed default branch needs one `ballast trust` again). `ballast setup` preserves a project's own constitution and never rewrites it with this amendment.

**Version**: 1.2.0 | **Ratified**: 2026-10-02 | **Last Amended**: 2026-10-06
