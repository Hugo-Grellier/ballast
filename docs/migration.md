# Migrating from Ballast 1.x to 2.0

Ballast 2.0 drops the v1 installer, trusted launcher and `ballast run`. An existing
agent session follows the [issue workflow](issue-workflow.md), runs workers through
the [standalone adapter](standalone.md), and gets an
[independent review](pair-review.md). A project copies the templates it wants. Nothing
is installed, and `ballast.toml` is no longer read.

[ADR-0024](adr/0024-ballast-2-migration.md#removed-guarantees) lists every v1 guarantee
2.0 removes. Read it before migrating. The main ones:

- No launcher refuses a tampered checkout, and no protected input fails a step.
- The helpers run with your authority from the Ballast checkout you choose.
- There are no gates or run ledger. The issue, the PR and the review hold the evidence,
  and human merge stays the approval.

## Staying on v1

Nothing changes for a project that keeps a `v1.x` pin:

- The `v1.x` tags, their release assets and the v1 documentation stay published. The
  last v1 release is [v1.1.0](https://github.com/Hugo-Grellier/ballast/tree/v1.1.0),
  and its [README](https://github.com/Hugo-Grellier/ballast/blob/v1.1.0/README.md)
  has the CLI install line and every v1 command.
- Do not set `ref` in `ballast.toml` to a 2.x tag. 2.x has no `tools/setup`, so
  `ballast setup` cannot install it.

## Adopting 2.0

Prerequisites: a POSIX host with Python 3.11+, Git, an authenticated `gh` for
GitHub.com, and a supported Codex CLI for workers (see [standalone](standalone.md#scope-and-limits)).

1. **Finish v1 work.** With the v1 command, finish or `ballast discard-runs` every
   open run. Merge or close its Draft PRs.
2. **Select a Ballast source.** Clone this repository at a 2.x tag outside the
   project. The coordinator runs the helpers from that checkout and reads its `docs/`.
3. **Copy the templates you want.** Review each one and replace the placeholders.
   - `templates/AGENTS.md` → `AGENTS.md`. Merge it with your existing file, keep
     `CLAUDE.md` linked to it, and set the "Ballast source" path.
   - `templates/policies/*.md` → `docs/policies/`.
   - `templates/skills/ballast-*` → `.agents/skills/`. Link `.claude/skills/` to
     them when you use Claude Code.
   - `templates/github/` → `.github/`: PR template, issue template, Dependabot and
     PR-title workflow.

   These files were ignored and reinstalled in v1. In 2.0 the project commits them.
   Keep `docs/policies/project/`: the policies still read it.
4. **Move project rules into `AGENTS.md`.**
   - Check commands from `ballast.toml` `[checks]` go to the Commands section.
   - Invariants from `.specify/memory/constitution.md` go to the Invariants section.
   - `[autonomous]` authorizations have no 2.0 equivalent. Every merge is a human
     decision.
5. **Remove v1 files** in the same reviewed commit:
   - `ballast.toml`, `.ballast/` and `.specify/`;
   - the installed `speckit-*` skills;
   - the Ballast ignore block in `.gitignore`.

   Keep any `.specify/` record you still want as history; it no longer drives anything.
6. **Optional machine cleanup.** Once no project on the machine uses v1, remove the
   v1 command (`~/.local/bin/ballast`), its cache and its state. The cache is
   `$XDG_DATA_HOME/ballast/standard/`, by default `~/.local/share/ballast/standard/`.
   The state is `$XDG_STATE_HOME/ballast/`, by default `~/.local/state/ballast/`. Check
   whether those variables are set first. This cleanup cannot be undone except by
   reinstalling v1.

## Rolling back

Revert the adoption commit. This restores `ballast.toml` with its `v1.x` pin and the
ignore block. Then install the v1 command from the v1.1.0 README if you removed it,
and run `ballast setup` and `ballast trust`. Issues, PRs and evidence created
under 2.0 stay valid GitHub history.

## Upgrading within 2.x

Fetch a newer 2.x tag in the Ballast source checkout and read `CHANGELOG.md`.
Compare `templates/` between the two tags and apply the changes you want to your
copies. Copy-once files are never overwritten for you.
