# Workflow: Ballast specifics

## R2 boundaries

In addition to the base list, these changes are R2 and need explicit human approval before the change and before merge:

- the headless-agent permission model: `claude-settings.json`, the wrapper's argv rules, protected inputs and tamper handling;
- the launcher's trust model: trusted inputs, refusal conditions, state location;
- what `ballast` executes or downloads: the fixed repository, the ref rules, the fetch path;
- the ignore block and the paths `tools/setup` installs, removes or preserves.

## Gates

The fast gate and full gate are in [`testing.md`](testing.md). Record both in the PR, with the end-to-end scratch run when `tools/setup` or `tools/ballast` changes.

## Syncing from LoreForge

Until LoreForge consumes Ballast, port its workflow-tool changes with a three-way merge (old LoreForge file and new LoreForge file, both renamed, against the current Ballast file) and record the source commit in the plan's sync log.
