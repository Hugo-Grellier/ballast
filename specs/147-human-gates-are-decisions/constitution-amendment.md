# Constitution amendment for #147: the pinned default branch refreshes a reviewed baseline

Written for `.specify/memory/constitution.md` on the operator's resolution of D-02 as option A (HD-0002, 2026-10-13). The constitution is a protected input that the confined implement step cannot edit, so the operator applies this text before merge and then runs `ballast trust` (tasks.md T043, as for #55). As for #27 and #55, the operator's merge of this PR is the approval. Until then the text is agent-provisional (BL-INV-006). The change is MINOR:

- The launcher's refusal, its fail-closed checks and the comparison stay as they are.
- Only who may record the baseline widens, and only under the conditions of [ADR-0021](../../docs/adr/0021-agent-sessions-relay-decisions.md).

Per the constitution's governance it needs explicit human approval as R2 and a recorded reason; this feature's PR merge is that approval.

## Principle 2 (BL-INV-002), replacement text

2. **Nothing executes from a writable checkout before trust (BL-INV-002).** The `ballast` command runs the launcher of the pinned, fetched version, never one from the checkout. The launcher refuses until the current inputs match a baseline that one of three recorded:
   - the operator's `ballast trust`;
   - the operator's `ballast setup` or worktree preparation, under the conditions of ADR-0015 (the checkout holds exactly what setup installed, its committed configuration equals what a human reviewed, and no agent has run there);
   - the operator's `ballast` command refreshing an existing baseline, under the conditions of ADR-0021 (every changed protected input is either installed by setup from the current configuration or equal to the live default branch of the same reviewed repository the baseline names).
   
   It fails closed on a tamper marker or an unfinished agent step, and never records generated agent settings that differ from `ballast.toml`.

## Amendment history, new entry

- **1.3.0** (2026-10-13, #147): amends BL-INV-002 so the operator's `ballast` command may refresh an existing baseline from the pinned repository's live default branch under ADR-0021's conditions.
  - **Reason**: a configuration change merged on the protected default branch cost every checkout one `ballast setup` and one `ballast trust`, and in the #141 run three trusts, none for an untrusted change. Branch protection on that default branch is now the review of such changes for checkouts that already trust the same repository. A repointed `[github] repository`, an unobservable branch, either marker, a `.venv` change, or any change not on the default branch still needs `ballast trust`.
  - **Compatibility**:
    - Projects pinning an earlier Ballast version see no change.
    - With an older global `ballast` command, nothing refreshes until `ballast self-install`.
    - Baselines recorded before the upgrade name no repository and need one `ballast trust` to be refreshable.
    - `ballast setup` preserves a project's own constitution and never rewrites it with this amendment.

## Version line

**Version**: 1.3.0 | **Ratified**: 2026-10-02 | **Last Amended**: 2026-10-13
