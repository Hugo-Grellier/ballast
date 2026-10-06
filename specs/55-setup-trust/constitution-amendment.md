# Constitution amendment for #55: setup may record the trust baseline

Apply this to `.specify/memory/constitution.md`, which is a protected input an agent never edits (as for #27): the operator replaces BL-INV-002, adds the amendment history entry and updates the version line. The change is MINOR: the launcher's refusal, its fail-closed checks and the comparison stay as they are; only who may record the baseline widens, and only under the conditions of [ADR-0014](../../docs/adr/0014-setup-recorded-trust-baseline.md). Per the constitution's governance it needs explicit human approval as R2 and a recorded reason; this feature's PR merge is that approval.

## Principle 2 (BL-INV-002), replacement text

2. **Nothing executes from a writable checkout before trust (BL-INV-002).** The `ballast` command runs the launcher of the pinned, fetched version, never one from the checkout. The launcher refuses until the operator trusts the current inputs, or until the operator's `ballast setup` or worktree preparation recorded them under the conditions of ADR-0014 (the checkout holds exactly what setup installed, its committed configuration equals what a human reviewed, and no agent has run there), and fails closed on a tamper marker or an unfinished agent step.

## Amendment history, new entry

- **1.2.0** (2026-10-06, #55): amends BL-INV-002 so a baseline recorded by the operator's `ballast setup` or worktree preparation under ADR-0014's conditions also counts. Reason: every fresh clone, issue worktree and pilot repository cost one human `ballast trust` although every protected input had just been written by the operator's own setup of the pinned standard from configuration already reviewed; the amendment removes that command only where nothing unreviewed can be recorded (committed configuration equal to the pinned repository's default branch or to the operator's own earlier baseline, no extra protected input, no run state, no marker), and the launcher's comparison before every run is unchanged. Compatibility: projects pinning an earlier Ballast version see no change; projects that upgrade need one `ballast trust` per machine to record the repository as reviewed, after which fresh checkouts need none. `ballast setup` preserves a project's own constitution and never rewrites it with this amendment.

## Version line

**Version**: 1.2.0 | **Ratified**: 2026-10-02 | **Last Amended**: 2026-10-06
