# Migrating from Ballast 1.x to 2.0

Ballast 2.0 drops the v1 installer, trusted launcher and `ballast run`. An existing
agent session follows the [issue workflow](issue-workflow.md), runs workers through
the [standalone adapter](standalone.md), and gets an
[independent review](pair-review.md). A project copies the templates and workflow
documents it wants and runs the helpers from a pinned tag with `uvx`. Nothing is
installed, and `ballast.toml` is no longer read.

[ADR-0024](adr/0024-ballast-2-migration.md#removed-guarantees) lists every v1 guarantee
2.0 removes. Read it before migrating. The main ones:

- No launcher refuses a tampered checkout, and no protected input fails a step.
- The helpers run with your authority from the Ballast tag you pin.
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

Prerequisites: a POSIX host with Python 3.11+, Git, [uv](https://docs.astral.sh/uv/)
for `uvx`, an authenticated `gh` for GitHub.com, and a supported Codex CLI for workers
(see [standalone](standalone.md#scope-and-limits)).

1. **Finish v1 work.** With the v1 command, finish or `ballast discard-runs` every
   open run. Merge or close its Draft PRs.
2. **Pick a Ballast tag.** The coordinator runs the helpers as
   `uvx --from git+https://github.com/Hugo-Grellier/ballast@vX.Y.Z ballast COMMAND`
   (`worktree`, `worker`, `coordinate`, `dashboard`, `merge-check`). The tag in that
   line is the version record; no checkout or local path is needed.
3. **Copy the templates you want.** Review each one and replace the placeholders.
   - `templates/AGENTS.md` → `AGENTS.md`. Merge it with your existing file, keep
     `CLAUDE.md` linked to it, and replace `[ADOPTED TAG]` with your tag.
   - `templates/policies/*.md` → `docs/policies/`.
   - `docs/issue-workflow.md`, `docs/pair-review.md` and `docs/model-routing.md` →
     `docs/policies/`, as described in [workflow copies](#workflow-copies).
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
     decision, except an R0 PR that meets [ADR-0026](adr/0026-r0-merge-on-reviewed-green-head.md)
     (approved and green on its exact head, no release, workflow or dependency
     file); a project can keep human merge for every PR.
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

## Workflow copies

`AGENTS.md` cites the issue workflow, pair review and model routing, so the project
keeps copies of them in `docs/policies/` rather than pointing outside the repository.
Copy each from the tag you pin and start it with one header line naming that tag and
its commit (`git rev-list -n 1 vX.Y.Z`):

```markdown
<!-- Copied from Hugo-Grellier/ballast vX.Y.Z (COMMIT) docs/issue-workflow.md; update per its docs/migration.md. -->
```

Links between the three copies resolve as they are. Point the others at the tag
or at your own copies:

- `../templates/policies/workflow.md` → `workflow.md`, your policy copy;
- `standalone.md`, `execution.md`, `subagent-workers.md` and `adr/...` →
  `https://github.com/Hugo-Grellier/ballast/blob/vX.Y.Z/docs/...` with your tag.

## Moving a 2.1.0 adopter to the pinned form

A project adopted at 2.1.0 or earlier names a `BALLAST_SOURCE` checkout, usually in an
ignored `AGENTS.local.md`, and its `AGENTS.md` cites `BALLAST_SOURCE/docs/*.md`. In one
reviewed commit:

1. Pick the first tag that ships the `ballast` command, or a later one.
2. Add the [workflow copies](#workflow-copies) under `docs/policies/` from that tag.
3. Re-apply the template `AGENTS.md` Issue workflow section: replace each
   `BALLAST_SOURCE/docs/...` reference with the link to its copy, and each
   `python3 -I -S "$BALLAST_SOURCE/tools/NAME.py"` with
   `uvx --from git+https://github.com/Hugo-Grellier/ballast@vX.Y.Z ballast NAME`
   (`merge_check.py` becomes `merge-check`).
4. Remove the `BALLAST_SOURCE` entry from `AGENTS.local.md`, and the file itself if
   nothing else is left in it. The checkout outside the project is no longer read; delete
   it when no other project uses it.
5. Check that `grep -rn BALLAST_SOURCE AGENTS.md docs/` finds nothing and that every
   relative link in `AGENTS.md` opens a file in the repository.

Claims and queues already under `.git/ballast-v2/` stay valid: the pinned command runs
the same helpers. Finish or release an issue claimed with the old checkout before
switching tags mid-issue, so one issue runs one helper version.

## Rolling back

Revert the adoption commit. This restores `ballast.toml` with its `v1.x` pin and the
ignore block. Then install the v1 command from the v1.1.0 README if you removed it,
and run `ballast setup` and `ballast trust`. Issues, PRs and evidence created
under 2.0 stay valid GitHub history.

## Upgrading within 2.x

Read `CHANGELOG.md` for the newer tag, change the tag in the `uvx` line of `AGENTS.md`,
and update your template and workflow copies as described next, including their header
lines.

## Updating adopted templates

Templates are copy-once: Ballast never overwrites your copies, so they drift unless you
compare them. Between your adopted tag `vA` and the new tag `vB`:

- Use the compare view `https://github.com/Hugo-Grellier/ballast/compare/vA...vB` with
  your tags, and look at the files under `templates/` and the three workflow documents.
  From a Ballast checkout, `git diff vA..vB -- templates/ docs/issue-workflow.md
  docs/pair-review.md docs/model-routing.md` shows the same.
- Re-apply the changes that matter to your project and keep your project-specific edits.
  Skip a change when you removed or rewrote that rule on purpose.
- Template links assume the layout in [Adopting 2.0](#adopting-20): policies and workflow
  copies in `docs/policies/` and skills in `.agents/skills/`. If you placed them elsewhere, fix the
  links in the copies you update.
