# ADR-0014: Setup records the trust baseline when it installed exactly what a human reviewed

- Status: proposed (with the implementation of [feature 55](../../specs/55-setup-trust/spec.md), 2026-10-06); accepted when its PR merges
- Feature: [55-setup-trust](../../specs/55-setup-trust/spec.md), FR-001 to FR-020, AC-001 to AC-027; decisions R1 to R19 in its [research](../../specs/55-setup-trust/research.md)
- Supersedes in part: [ADR-0007](0007-recoverable-installation.md) ("setup never records trust") and [ADR-0011](0011-worktree-preparation.md) ("Preparation never reads any `trusted.json`" for the checkout's own baseline, and preparation's local-only, no-network outcome)
- Builds on: [ADR-0005](0005-launcher-branch-synchronization.md) (the trusted Git path), [ADR-0002](0002-cli-standard-manifest.md) (doctor reads the launcher's `status --json`)
- Amends: BL-INV-002 of the constitution (text in the feature's `constitution-amendment.md`; the operator applies it to the protected `.specify/memory/constitution.md`)

## Context

The launcher refuses `ballast run`, `ledger` and `intake` until a trust baseline in operator state matches the checkout's protected inputs. Only the operator's `ballast trust` wrote it, so every fresh clone, issue worktree and pilot repository cost one human command, even when every protected input had just been written by the operator's own `ballast setup` and no agent had run there. The operator chose, knowing it conflicts with two accepted rules, to let setup and a worktree's first-command preparation record the baseline under stated conditions (Issue #55; discovery decisions D-01 to D-03). Any such change must keep an unreviewed `ballast.toml` (for example widened `[agents.permissions]`) and any agent trace from ever becoming trusted.

## Decision

Setup, and a preparation that just installed a worktree, record the baseline themselves when, and only when, every condition holds. They check them in this order, report the first failure, and reach the network last:

1. The standard they run from lies outside the checkout.
2. No `BALLAST_TAMPERED` marker and no agent step's in-progress marker exists.
3. A baseline that already equals the current inputs is left untouched, with its source.
4. The checkout holds no saved run state, and operator state holds no unfinished run.
5. `ballast.toml` and the constitution are regular files, read once; the digests recorded are of these bytes.
6. Every other protected input equals what the verified installation record lists, and every recorded file under `.ballast/spec_workflow` and `.specify` is present unchanged. A `.venv`, a committed `.specify` file other than the constitution, or an edited installed file makes the checkout ineligible.
7. A linked worktree's `.git` pointer names a worktree of the repository it belongs to, outside the checkout and every agent temp directory, with a matching back-link.
8. Both configuration files are committed and unchanged from `HEAD`.
9. Both are reviewed, meaning equal to one of:
   - the checkout's previous baseline when `ballast trust` recorded it (no network); or
   - the files on the default branch of the repository `ballast.toml` pins in `[github] repository`, observed live, when that repository is in the machine's record of repositories `ballast trust` reviewed.

Recording is atomic and verified: the inputs are snapshotted once, written, and snapshotted again; a difference, or a failed write, removes the new baseline and restores the previous one. A preparation first removes a baseline or provenance left at a reused path and never opens another checkout's.

**Observing the default branch.** The launcher's trusted Git path from ADR-0005 is reused: the same URL rule (`setup_trust.repository_url`, the scheme from `origin`, everything else from the pin) and the same environment builders, now shared rather than copied (Git outside working trees, location and configuration variables removed, `PATH` without checkout or temp entries, no prompts, no `askpass`). Unlike branch synchronization, the throwaway bare repository has its own object store under operator state and is deleted afterwards. Only `ls-remote --symref URL HEAD`, then a depth-1, blob-less `fetch` of the default branch into it, `rev-parse` and `ls-tree` of the two files run; blob IDs are compared with the IDs of the snapshot bytes, and only regular-file entries count. No ref, remote, URL rewrite or other setting of the checkout names the repository, branch or files. Every network command is bounded (30 s and 120 s) and prompts for nothing. A failure of any kind means "unobservable", which means not eligible.

**Reviewed repositories.** Nothing in a checkout can tell the reviewed repository from one a commit repointed `[github] repository` to, whose default branch can carry the same changed file. So the default-branch alternative counts only for a repository in `$XDG_STATE_HOME/ballast/reviewed-repositories.json`, written only by `ballast trust` (it adds the repository named in the `ballast.toml` it trusts). It holds identities, never digests, so no baseline is inherited.

**Provenance.** `trusted-source.json` beside `trusted.json` names who recorded the baseline (`setup` or `trust`), bound to the digest of the exact baseline bytes, with the reference the setup used. The launcher's `status --json` reports it as `baseline_source`; a missing, unreadable or unbound record reads as `trust`. `ballast doctor` shows it by reading only that JSON. The launcher's comparison, its refusals and the tamper marker do not read it and do not change.

## Consequences

- With network access and the operator's Git authority for the pinned repository, a fresh clone or new issue worktree of a project on its default-branch configuration needs no `ballast trust`, once the operator trusted that repository on this machine. The first checkout of a project on a machine still needs one; a project whose baselines predate this decision needs one per machine to populate the record.
- An agent cannot make a baseline: a step always holds the in-progress marker, run state anywhere refuses, and any later change to a protected input is refused by the unchanged launcher.
- Recording through the previous operator baseline replaces its `trust` provenance with `setup`, so the next re-setup at a changed pin with unchanged configuration needs the network or `ballast trust` again. This fails closed and is stated in the documentation (plan-review F-005).
- Setup holds the checkout lock for up to a few minutes while it asks the network; a hung request ends in "timed out" and no baseline.
- Preparation is no longer strictly offline: it never downloads the standard, but an eligible one asks the pinned repository.

## Agent inferences narrowing the operator's answer (D-02), listed for merge review

- The default branch is observed through the pinned repository on the trusted Git path, never from a local remote-tracking ref an agent can move.
- Only a repository the operator already reviewed counts, so the first checkout of a never-trusted repository needs `ballast trust`.

## Rejected alternatives

- A local `refs/remotes/origin/<default>` ref (D-02 as first worded): agent-writable, so an agent would choose what counts as reviewed.
- The GitHub contents API through `gh`: a second authority and transport for a fact the trusted Git path already reads.
- Sharing the checkout's object store, as branch synchronization does: unnecessary here and it would let planted objects answer the lookup.
- A source field inside `trusted.json`: changes the format the comparison reads.
- Accepting whatever repository `ballast.toml` names: a commit could repoint it.
- Inheriting another checkout's baseline: trust is a review of one checkout.
