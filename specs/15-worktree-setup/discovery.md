<!-- ballast-discovery: input evidence -->
# Discovery brief: prepare a new worktree on first Ballast use

This brief is input evidence for [spec.md](spec.md). It is not the feature's
authority: once intent is recorded, [spec.md](spec.md) and [intent.md](intent.md)
govern, and later steps do not read requirements from this file.

**Mode**: autonomous
**Issue**: #15 (snapshot `.specify/workflow-state/issues/15.md`, untrusted requirements data)

## Sources

- S-1: Issue #15 body
- S-2: Issue #15 intake scope comment
- S-3: AGENTS.md
- S-4: .specify/memory/constitution.md#Core principles
- S-5: specs/TECHNICAL-SPEC.md#91. v1.0 target
- S-6: docs/plans/2026-10-02-product-roadmap.md#Priority 1
- S-7: docs/adr/0007-recoverable-installation.md
- S-8: docs/adr/0008-verified-cache-and-update-preview.md
- S-9: specs/14-recoverable-install/spec.md
- S-10: docs/policies/project/workflow.md#R2 boundaries
- S-11: docs/policies/project/testing.md
- S-12: tools/ballast (`command_standard`, `ensure_standard`, `main`)
- S-13: tools/setup (`build`, `copy_from_primary`, `copy_verified`, `entries`)
- S-14: tools/spec_workflow/launcher.py (`state_dir`, `read_record`, `_refusal`, `_trust`, `main`)
- S-15: tools/cli.toml

## Need

- **User**: an operator who runs several Ballast feature runs in parallel, each in its own Git worktree of one adopted repository. [S: Issue #15 body] [S: docs/plans/2026-10-02-product-roadmap.md#Priority 1]
- **Job to be done**: create a worktree and start or continue a run there without repeating a setup ritual. [S: Issue #15 body]
- **Current pain**: each new worktree needs an explicit `ballast setup`; any command other than `setup` in an uninstalled worktree stops with "run `ballast setup`", and a worktree whose primary checkout is on another pin or configuration falls back to a full installation that downloads Spec Kit sources again. [S: docs/plans/2026-10-02-product-roadmap.md#Current state] [S: tools/setup] [S: tools/spec_workflow/launcher.py]
- **Intended outcome**: the first `ballast` command in a new worktree at a pin whose matching installation is already verified on this machine materializes that installation and reaches the launcher's preflight, with no separate setup and no network access; the preflight then states precisely what trust the worktree still needs. [S: Issue #15 body] [S: IAC-1]

## Examples

- Ten worktrees are created from `main` pinned at `v0.6.0`; the primary checkout is installed and verified at `v0.6.0`. In each, `ballast run start ...` materializes the installation from the verified local copy without a download and then refuses at preflight with "no trusted baseline for this worktree; review the installed protected inputs, then run `ballast trust`". [S: IAC-1] [S: docs/plans/2026-10-02-product-roadmap.md#Priority 1]
- A worktree on a branch that pins `v0.5.0` while the primary is at `v0.6.0`: it never receives the `v0.6.0` installation; if no verified `v0.5.0` installation is available locally it stops and names `ballast setup` instead of downloading. [S: IAC-2] [S: docs/policies/project/testing.md]
- A worktree whose `ballast.toml` adds `[agents.permissions]` rules the primary does not have: its fingerprint differs, so the primary's installation (and its generated `claude-settings.json`) is not reused. [S: IAC-2] [S: tools/setup]
- A materialization is killed halfway through its switch; the next command in that worktree finishes or rolls back the attempt and retries, never leaving a mixed installation. [S: IAC-3] [S: docs/adr/0007-recoverable-installation.md]

## Scope

- Materialize the matching, content-verified installation into a new worktree on its first `ballast` command, from what is already verified on this machine. [S: Issue #15 body] [S: Issue #15 intake scope comment]
- Keep mutable state per worktree: run state, the trust baseline, the in-progress marker and the setup journal stay local to each checkout. [S: Issue #15 body] [S: tools/spec_workflow/launcher.py]
- Report trust requirements precisely after materialization. [S: Issue #15 body]
- Tests for ten concurrent and mixed-pin worktrees, a missing cache, an interruption and a retry. [S: IAC-3]

## Non-goals

- Copying another worktree's or the primary's run state. [S: Issue #15 body]
- Treating a different pin, or a different `ballast.toml` configuration, as equivalent. [S: Issue #15 body] [S: IAC-2]
- Bypassing protected-input trust, or recording or inheriting a trust baseline on the operator's behalf (#55). [S: Issue #15 intake scope comment]
- `ballast init`, automatic pin changes and update previews. [S: specs/14-recoverable-install/spec.md] [S: docs/plans/2026-10-02-product-roadmap.md#Priority 1]

## Constraints

- Only `setup` and `preview` download; every other command runs an already fetched, verified version. [S: docs/policies/project/testing.md] [S: tools/ballast]
- Nothing executes from a writable checkout before trust; the launcher and setup run from the pinned standard outside the checkout. [S: .specify/memory/constitution.md#Core principles]
- Workflow tools stay standard-library-only and run under `python3 -I -S`. [S: AGENTS.md#Invariants]
- One rule (`entries(root)`) defines an installation; copies are accepted only when they hash to a valid installation record; switches are staged, journaled and serialized by the checkout lock. [S: docs/adr/0007-recoverable-installation.md]
- A cached standard version is used only after it verifies against its content record. [S: docs/adr/0008-verified-cache-and-update-preview.md]
- R2: this changes installed paths and the launcher's trust model; the pre-change approval is agent-provisional and the merge decision is the single human approval. [S: docs/policies/project/workflow.md#R2 boundaries] [S: Issue #15 body]
- A change to `tools/setup` or `tools/ballast` needs the end-to-end scratch-project run as well as the fast gate. [S: docs/policies/project/testing.md]

## Permissions and data authority

- The trust baseline (`trusted.json`) lives in per-checkout operator state keyed by the checkout path, and a linked worktree's `.git` pointer is a trusted input, so baselines are inherently per worktree. [S: tools/spec_workflow/launcher.py]
- Only the operator runs `ballast trust`; materialization must never record or copy a baseline. [S: AGENTS.md] [S: Issue #15 intake scope comment]
- Installation records live in operator state, outside agent write authority; a materialized copy is accepted only against such a record. [S: docs/adr/0007-recoverable-installation.md]
- The pinned `ref` and the `ballast.toml` bytes (including `[agents.permissions]`) define the installation fingerprint; they stay the project's committed authority and are never edited by materialization. [S: tools/setup] [S: .specify/memory/constitution.md#Core principles]

## Success evidence

- A test creates a new worktree at a pin with a verified local installation, blocks network access, runs a non-setup `ballast` command, and observes a materialized installation and the launcher's trust refusal with no download. [S: IAC-1]
- Tests show no reuse across a different pin, a different `ballast.toml` permission configuration, or content that differs from its record, and that no trust baseline is shared. [S: IAC-2]
- A ten-worktree concurrent and mixed-pin test, plus missing-cache, killed-materialization and retry tests, show independent run state and complete installations. [S: IAC-3] [S: docs/policies/project/testing.md]
- The end-to-end scratch-project run, recorded in the PR. [S: docs/policies/project/testing.md]

## Edge, failure and permission cases

- No verified matching installation on this machine: the command does not download and names `ballast setup` as the next step. [S: docs/policies/project/testing.md] [P: D-03]
- The standard cache for the pin is damaged: refuse naming the damaged path, as `setup` does, without fetching. [S: docs/adr/0008-verified-cache-and-update-preview.md] [I]
- The source installation is being set up, differs from its record, or is for another fingerprint: it is not used. [S: tools/setup] [P: D-03]
- Two commands in one new worktree at once: the exclusive checkout lock lets one materialize; the other refuses or waits rather than interleaving. [S: docs/adr/0007-recoverable-installation.md] [I]
- The pinned standard version predates this feature: the CLI cannot ask it to materialize and keeps the current "run `ballast setup`" refusal. [S: tools/cli.toml] [I]
- The worktree already holds a stale, modified or other-pin installation: existing refusals stand. [P: D-05]
- A tamper marker or an unfinished agent step in the worktree: existing launcher refusals stand. [S: tools/spec_workflow/launcher.py]

## Issue acceptance criteria

- IAC-1: A new worktree at a cached matching pin reaches preflight without a separate setup command or network fetch.
- IAC-2: Different pins, changed permissions and mismatched protected-input digests cannot reuse an unrelated installation or trust baseline.
- IAC-3: Ten concurrent/mixed worktrees retain independent mutable state; tests cover missing cache, interruption and retry.

## Known

- Setup already copies the primary checkout's installation into a worktree when the copy hashes to the primary's record and the fingerprints match; otherwise it does a full installation. [S: specs/14-recoverable-install/spec.md] [S: tools/setup]
- A full installation downloads pinned Spec Kit sources from GitHub, so the standard cache alone does not make a worktree installable offline. [S: tools/setup]
- The `ballast` CLI runs `tools/setup` only for `setup`; for other commands it execs the pinned launcher, which refuses when nothing is installed. [S: tools/ballast] [S: tools/spec_workflow/launcher.py]
- Operator state (installation record, journal, checkout lock, trust baseline) is keyed by the checkout's resolved path. [S: tools/spec_workflow/launcher.py]
- Run state lives inside each checkout under `.specify/workflows/runs` and `.specify/workflow-state` and is excluded from installation records and copies. [S: tools/setup] [S: tools/spec_workflow/launcher.py]
- The kept previous installation lets a rollback reinstall without a download. [S: docs/adr/0007-recoverable-installation.md]
- New-worktree automatic setup was explicitly deferred from feature 14 to this Issue; trust recorded by setup belongs to #55. [S: specs/14-recoverable-install/spec.md]
- A pinned version declares what it supports to the CLI in `tools/cli.toml`, read as data. [S: docs/adr/0008-verified-cache-and-update-preview.md] [S: tools/cli.toml]

## Inferred

- "Preflight" in IAC-1 means the launcher's refusal checks; a new worktree always stops there at "no trusted baseline" until the operator trusts it. [I]
- Materialization should run the pinned standard's own `tools/setup` from the verified cache in a cache-only mode, reusing its stage, validation, journal and lock, so ADR-0007's guarantees hold unchanged. [I]
- The CLI should learn from a new `tools/cli.toml` declaration that a pin supports materialization, as ADR-0008 did for `[setup] recoverable`; this needs a CLI release. [I]
- A "cached matching pin" means a verified installation with the same fingerprint (pin and `ballast.toml` bytes) is available locally from the kept copy, the primary checkout or another linked worktree of the same repository. [P: D-03]
- Only commands that need the installation (`run`, `ledger`, `intake`) materialize; `trust`, `discard-runs`, `doctor`, `status` and `preview` do not. [P: D-04]
- Materialization applies only when the worktree has no installation, or holds an interrupted first materialization to recover. [P: D-05]
- "Changed permissions" in IAC-2 covers both `[agents.permissions]` in `ballast.toml` and the files' executable bits. [P: D-06]
- The plan should record the extended copy sources and the first-command trigger in a new ADR that extends ADR-0007. [I]

## Undecided

None.

## Decisions

### D-01: Missing cache on a non-setup command
- **Status**: settled
- **Question**: When no verified matching installation exists locally, does the first command fetch over the network or stop?
- **Why it matters**: It decides whether non-setup commands may download, and what the missing-cache test asserts.
- **Sources**: [S: docs/policies/project/testing.md] [S: tools/ballast] [S: IAC-1]
- **Options**:
  - A — Stop with a precise message naming `ballast setup`. Consequence: the download rule holds; the operator runs setup once for an uncached pin.
  - B — Run a full setup with network access. Consequence: breaks the rule that only `setup` and `preview` download.
- **Recommended default**: A, because the testing policy makes it critical evidence.
- **Answer**:
- **Resolution**: A. Only `setup` and `preview` download [S: docs/policies/project/testing.md] [S: tools/ballast]; IAC-1 only promises an offline result at a cached pin [S: IAC-1].

### D-02: Trust baseline for a new worktree
- **Status**: settled
- **Question**: Does a materialized worktree inherit a trust baseline from the primary or a sibling?
- **Why it matters**: It decides whether preflight passes or stops at trust, and the R2 surface.
- **Sources**: [S: Issue #15 intake scope comment] [S: IAC-2] [S: docs/plans/2026-10-02-product-roadmap.md#Priority 1]
- **Options**:
  - A — No inheritance; report precisely that the worktree needs review and `ballast trust`. Consequence: the trust model is unchanged.
  - B — Inherit when digests and pin match. Consequence: changes the trust boundary; owned by #55.
- **Recommended default**: A, because the Issue excludes it.
- **Answer**:
- **Resolution**: A. Recording a trust baseline on the operator's behalf is out of scope (#55) [S: Issue #15 intake scope comment], no trust baseline may be reused [S: IAC-2], and inheritance is a later, separately approved R2 design [S: docs/plans/2026-10-02-product-roadmap.md#Priority 1].

### D-03: Where the verified matching installation comes from
- **Status**: assumed
- **Question**: Which local sources may a new worktree materialize its installation from?
- **Why it matters**: It defines a "cached matching pin" for IAC-1 and whether ten worktrees at a pin other than the primary's avoid repeated downloads.
- **Sources**: [S: Issue #15 intake scope comment] [S: docs/adr/0007-recoverable-installation.md] [S: tools/setup] [S: docs/plans/2026-10-02-product-roadmap.md#Priority 1]
- **Options**:
  - A — Any installation record already on this machine for this repository: the kept copy, the primary checkout, and the other linked worktrees, each used only when its fingerprint matches and the copy hashes to its record. Consequence: no new store; the first worktree at a new pin still needs `ballast setup`, later ones copy from it.
  - B — A new per-machine installation cache under `$XDG_DATA_HOME/ballast/`, keyed by fingerprint, written after each committed setup. Consequence: independent of any checkout's state, but a new trusted store and its own locking and pruning.
  - C — The primary checkout only (today's behavior). Consequence: worktrees at a pin other than the primary's always reinstall from the network.
- **Recommended default**: A, because it reuses #14's verified records and copy path with no new store.
- **Answer**:
- **Resolution**: A, agent-provisional. Safe: every candidate is accepted only through the existing verified copy against a record in operator state, so no new trust is extended and the trust baseline is still required. Reversible: installations are git-ignored and rebuildable, and moving to B later changes only where copies come from.

### D-04: Which commands materialize
- **Status**: assumed
- **Question**: Which `ballast` commands materialize an installation in a new worktree?
- **Why it matters**: It decides the CLI entry points that change and what "first command" means in tests.
- **Sources**: [S: tools/ballast] [S: tools/spec_workflow/launcher.py] [S: .specify/memory/constitution.md#Core principles]
- **Options**:
  - A — Only `run`, `ledger` and `intake`; `trust` and `discard-runs` keep refusing on an uninstalled worktree with a message naming how to install; `doctor`, `status` and `preview` stay read-only. Consequence: `trust` never records a baseline over files materialized in the same command.
  - B — Every launcher command, including `trust`. Consequence: one `ballast trust` could install and trust files the operator never saw.
- **Recommended default**: A, because it keeps the trust step after the operator can review what was materialized.
- **Answer**:
- **Resolution**: A, agent-provisional. Safe: it narrows behavior relative to B and keeps BL-INV-002 and doctor's read-only contract intact. Reversible: adding a command to the trigger list later is a small change.

### D-05: Which worktree states materialize
- **Status**: assumed
- **Question**: Does the first-command path act only on a worktree with no installation, or also replace a stale, modified or other-pin one?
- **Why it matters**: It decides whether a command other than `setup` can switch an existing installation under paused run state.
- **Sources**: [S: Issue #15 body] [S: tools/spec_workflow/launcher.py] [S: docs/adr/0007-recoverable-installation.md]
- **Options**:
  - A — Only when the worktree has no installation, or holds an interrupted first materialization to recover; every other state keeps today's refusal naming `ballast setup`. Consequence: existing installations change only through `setup`.
  - B — Also replace stale or other-pin installations from the cache. Consequence: a run command could silently switch an installation that a paused run depends on.
- **Recommended default**: A, because the Issue is about a new worktree.
- **Answer**:
- **Resolution**: A, agent-provisional. Safe: it leaves every existing refusal and the explicit `setup` path unchanged. Reversible: widening to B later only adds cases.

### D-06: Meaning of "changed permissions" in IAC-2
- **Status**: assumed
- **Question**: Which permissions must differ to prevent reuse?
- **Why it matters**: It decides which mismatch tests IAC-2 needs and whether the installation record must also cover file modes.
- **Sources**: [S: IAC-2] [S: tools/setup]
- **Options**:
  - A — Both: `[agents.permissions]` in `ballast.toml` (already in the fingerprint) and the executable bits of copied files (checked when copying). Consequence: one more check in the verified copy, and tests for both.
  - B — Only `[agents.permissions]`. Consequence: a copied file whose mode differs from what its version builds would be accepted.
- **Recommended default**: A, because it is the stricter reading.
- **Answer**:
- **Resolution**: A, agent-provisional. Safe: it only adds refusals. Reversible: a mode check can be dropped without data loss.

## Question metrics

- **Rounds**: 0
- **Questions asked**: 0
- **Assumptions adopted**: 4
