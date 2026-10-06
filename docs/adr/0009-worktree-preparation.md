# ADR-0009: A new worktree is prepared from a verified local installation

- Status: proposed (with the plan of [feature 15](../../specs/15-worktree-setup/plan.md), 2026-10-06); accepted when its PR merges
- Feature: [15-worktree-setup](../../specs/15-worktree-setup/spec.md); decisions R1 to R9 in its [research](../../specs/15-worktree-setup/research.md)
- Extends: [ADR-0007](0007-recoverable-installation.md) (stage, journal, record, lock); relies on [ADR-0002](0002-cli-standard-manifest.md) (manifest as data) and [ADR-0008](0008-verified-cache-and-update-preview.md) (verified cache)

## Context

Every new worktree needed its own `ballast setup` before its first `ballast run`, `ledger` or `intake`, although the installation it needs usually already exists on the machine, in the primary checkout or another worktree. ADR-0007 let `ballast setup` copy the primary's installation when it verifies, but only the primary, only through a separate command that may download, and without checking file modes, which the content digests do not cover.

## Decision

- The first `ballast run`, `ledger` or `intake` in a checkout with no installation (no `.ballast/spec_workflow/run.py`, or a setup journal in its operator state) runs the pinned version's own `tools/setup --prepare` before the launcher, from the verified cache, when that version declares `[setup] prepare = true` in its `tools/cli.toml`. A version without the declaration gets a CLI refusal naming `ballast setup`. No other command prepares; `trust` and `discard-runs` on an uninstalled checkout refuse before taking the checkout lock and create nothing, except that `discard-runs` clears an unfinished agent step left there, which setup and preparation refuse on (feature 15 DEC-0001).
- `--prepare` is a local-only mode of ADR-0007's attempt: the same exclusive lock, journal (now with `mode` and `source`), stage, validation, switch, live verification and recovery. It never downloads, never runs Spec Kit or `patch`, and never falls back to a full installation. It acts only on a checkout holding no installation (by `live_entries`, so a tracked project file is not one) or an interrupted preparation; a checkout already current for its pin answers `nothing to prepare` and exits 0, checked first under the shared lock so a second command started with the first proceeds even once the first runs its launcher; any other installation is refused naming `ballast setup`.
- The stage is filled from the first verified candidate among the installations recorded on this machine for the same repository: this checkout's own kept copy, then the primary's live and kept installations, then each linked worktree's, in `git worktree list` order. A checkout with neither an installation record nor a kept copy holds no candidate and is not reported; one Git lists but whose path is gone is rejected. A candidate is used only when it has no unfinished setup, its existing `checkout.lock` can be taken shared (held through the copy; a missing lock file rejects it rather than creating one), its record (read after the lock) names this pin and this fingerprint and lists executable files, no directory between the checkout and a recorded entry is a symbolic link, and the stage copy hashes equal to that record, executable bits included. Every rejection is printed with its reason; none verifies → refusal naming `ballast setup`, leaving no work area behind.
- The copy never goes through a link: every directory on both sides is opened with `O_NOFOLLOW`, every file is created with `O_EXCL`, a failed copy is removed the same way, and copied modes drop set-id and group/world write bits. A preparation switches in only a stage whose new record equals the record of the copy that verified. Setup runs git with `core.fsmonitor` disabled, so repository configuration never starts a program before the trust preflight. `ballast setup`'s own verified copies (primary, kept) use the same copy.
- The installation record gains `executable`, the sorted list of installed regular files with an execute bit. `copy_verified` compares modes whenever the record lists them, so `ballast setup`'s primary copy gains the check too; preparation rejects a record without the list.
- A committed preparation whose fingerprint no longer matches (the pin or `ballast.toml` changed before recovery) is rolled back, not finished: nothing preceded it and its entries are rebuildable.
- Trust baselines stay per checkout. Preparation never reads any `trusted.json`; one already in the prepared worktree's state predates the worktree (its path was reused) and is removed. The launcher's no-baseline refusal names the inputs to review and `ballast trust`.

## Consequences

- A worktree at a pin and `ballast.toml` already installed somewhere on the machine reaches the trust preflight with one command and no network; the first worktree at a new pin or configuration still needs `ballast setup`.
- A setup in a source checkout waits out one copy (it refuses while the shared lock is held); the source's own `run`, `ledger` and `intake` are never blocked.
- Using the feature needs a CLI and a pinned standard that both include it; older combinations keep a refusal naming `ballast setup`.
- Records written before this decision lack `executable`, so they are never a preparation source; a `ballast setup` in that checkout rewrites them.

## Rejected alternatives

- A per-machine installation store: a second source of truth with its own lifecycle (feature 15 non-goal).
- The launcher preparing: it would mix the trust gate with installation and hold the shared lock it keeps through `execv`.
- Calling a full `ballast setup` implicitly: it may download.
- Copying a trust baseline with an identical installation: trust is an operator review of one checkout, never inherited.
- Comparing modes against the source's live files: that is the thing being checked.
