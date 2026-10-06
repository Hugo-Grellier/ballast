<!-- ballast-discovery: input evidence -->
# Discovery brief: setup trusts a checkout it just installed

This brief is input evidence for [spec.md](spec.md). It is not the feature's
authority: once intent is recorded, [spec.md](spec.md) and [intent.md](intent.md)
govern, and later steps do not read requirements from this file.

**Mode**: autonomous
**Issue**: #55 (snapshot `.specify/workflow-state/issues/55.md`, untrusted requirements data)

## Sources

- S-1: Issue #55 body
- S-2: Issue #55 intake scope comment
- S-3: tools/spec_workflow/launcher.py (`_trust`, `_trust_refusal`, `trusted_inputs`, `BASES`, `SKIPPED`, `main` status `--json`)
- S-4: tools/setup (module docstring, `main`, `prepare`, `fill_from_candidates`)
- S-5: tools/ballast (`_trust` doctor check, `before_launcher`, `prepare`)
- S-6: docs/adr/0007-recoverable-installation.md#decision
- S-7: docs/adr/0011-worktree-preparation.md#decision and #rejected-alternatives
- S-8: docs/adr/0002-cli-standard-manifest.md
- S-9: .specify/memory/constitution.md#core-principles (BL-INV-002, BL-INV-003, BL-INV-006) and #governance
- S-10: docs/plans/2026-10-02-product-roadmap.md (phase 2 items 3 and 7)
- S-11: docs/policies/project/workflow.md#r2-boundaries
- S-12: AGENTS.md (invariants; issue and spec workflow; risk)
- S-13: specs/TECHNICAL-SPEC.md#91-v10-target
- S-14: specs/55-setup-trust/autonomous/record.md (PD-0001, scope; HD-0001, the operator's block resolution that changed this brief)
- S-15: the operator's answers to D-01, D-02 and D-03, written in this brief by the operator in commit f290079 during the block HD-0001 records
- unavailable: Issue #55 comments — the snapshot lists none

## Need

- **User**: the operator of a Ballast project, and an agent driving work under the operator's authority, who creates worktrees and pilot checkouts and starts runs in them. [S: Issue #55 body]
- **Job to be done**: create or set up a checkout and start a `ballast run` with no extra command when every protected input was just written by the operator's trusted `ballast setup` of the pinned standard. [S: Issue #55 body]
- **Current pain**: every new checkout needs a separate `ballast trust` before any `ballast run` or `ballast intake`, one human touch per issue worktree and pilot repository, for a baseline the operator did not need to review. [S: Issue #55 body]
- **Intended outcome**: a checkout whose protected inputs are exactly what the trusted setup of the pinned standard produced is trusted without a separate command; any checkout that differs still needs an explicit `ballast trust` after review. [S: Issue #55 body]

## Examples

- A fresh clone at a released pin: the operator runs `ballast setup`, then `ballast run start`; the launcher accepts the checkout and `ballast doctor` says the baseline was recorded by setup. [S: IAC-1]
- A worktree whose `ballast.toml` has an uncommitted pin bump: setup installs, records no baseline and says `ballast trust` is needed. [S: Issue #55 body] [S: IAC-2]
- A checkout holding a `BALLAST_TAMPERED` marker or an unfinished agent step: setup refuses to record a baseline. [S: IAC-3]
- After a setup-recorded baseline, an agent edits `.specify/` scripts: the next `ballast run` fails closed exactly as today. [S: IAC-4] [S: tools/spec_workflow/launcher.py]

## Scope

- `ballast setup`, run from the operator's trusted CLI outside the checkout, records the trust baseline for the inputs it just wrote when the committed inputs (`ballast.toml`, constitution) are unchanged from the commit setup read and no run is in progress. [S: Issue #55 body]
- `ballast doctor` reports how a baseline was recorded: operator `trust` or setup. [S: Issue #55 body]
- The new-worktree preparation path (#15) uses the same recording. [S: Issue #55 body] [S: Issue #55 intake scope comment]

## Non-goals

- Trusting a checkout after an agent step. [S: Issue #55 body]
- Trusting edits to `ballast.toml` or `[agents.permissions]` that no human reviewed. [S: Issue #55 body]
- Any change to the launcher's fail-closed comparison or the `BALLAST_TAMPERED` marker. [S: Issue #55 body]
- Inheriting or copying another checkout's baseline. [S: docs/adr/0011-worktree-preparation.md#rejected-alternatives]

## Constraints

- Workflow tools stay standard-library-only and run under `python3 -I -S`; nothing the launcher executes comes from a checkout an agent can write. [S: AGENTS.md] [S: .specify/memory/constitution.md]
- The trust comparison keeps one owner, the launcher; doctor recomputes nothing and reads the launcher's `status --json`. [S: docs/adr/0002-cli-standard-manifest.md] [S: tools/ballast]
- The baseline lives in operator state (`$XDG_STATE_HOME/ballast/<key>/trusted.json`), never where an agent can write. [S: tools/spec_workflow/launcher.py]
- The change is R2 (launcher trust model, agent authority); in this Autonomous run every pre-change decision is agent-provisional and the merge is the single human approval. [S: docs/policies/project/workflow.md#r2-boundaries] [S: specs/55-setup-trust/autonomous/record.md]
- An accepted architecture change needs a new ADR; a change that weakens a constitution invariant needs R2 approval and a recorded reason. [S: AGENTS.md] [S: .specify/memory/constitution.md#governance]

## Permissions and data authority

- Today only the operator's `ballast trust` writes `trusted.json`; setup never records trust and preparation never reads or records one. [S: tools/spec_workflow/launcher.py] [S: docs/adr/0007-recoverable-installation.md#decision] [S: docs/adr/0011-worktree-preparation.md#decision]
- The feature would give `tools/setup` (and `--prepare`) authority to write the baseline. [S: Issue #55 body]
- `--prepare` runs on the first `ballast run`, `ledger` or `intake`, which an agent driving work may invoke, unlike `ballast trust`, which only the operator runs. [S: tools/ballast] [S: AGENTS.md]
- The operator answered that preparation records a baseline under the same eligibility conditions as `ballast setup`; eligibility ties the committed `ballast.toml` and constitution to the default branch or the previous operator-recorded baseline, so an agent-started command records trust only for committed inputs a human already reviewed. [S: specs/55-setup-trust/autonomous/record.md]
- `ballast.toml` and the constitution are committed project files; a commit on a feature branch is not by itself evidence that a human reviewed it. [I]

## Success evidence

- A test where setup on a clean checkout is followed by an accepted `ballast run start` with no `ballast trust`, and the baseline's recorded source is setup. [S: IAC-1]
- Tests where a differing `ballast.toml`, constitution or other protected input leaves no baseline and setup's message names `ballast trust`. [S: IAC-2]
- Tests where an in-progress marker or `BALLAST_TAMPERED` makes setup refuse to record. [S: IAC-3]
- The launcher's existing refusal tests pass unchanged, plus one where a protected input changed after a setup-recorded baseline fails closed. [S: IAC-4]
- `ballast doctor` output shows the baseline source in both cases. [S: Issue #55 body]

## Edge, failure and permission cases

- An uncommitted `ballast.toml` change (for example a pin bump an agent wrote): never eligible. [S: Issue #55 body] [S: specs/55-setup-trust/autonomous/record.md]
- A committed `ballast.toml` change on a feature branch that no human merged, such as widened `[agents.permissions]`. [S: Issue #55 body]
- A protected input that setup did not write (an extra file under `.specify/`, or a linked worktree's `.git` pointer). [S: tools/spec_workflow/launcher.py] [S: IAC-2]
- Saved run state from earlier runs, which lies outside the baseline. [S: tools/spec_workflow/launcher.py]
- A setup that is a no-op ("nothing changed") on an installed checkout with no baseline, or with an operator baseline that should not be replaced. [S: tools/setup] [I]
- A stale `trusted.json` left at a reused checkout path, which preparation removes today. [S: tools/setup]
- An unfinished setup attempt recovered by the next setup. [S: docs/adr/0007-recoverable-installation.md#decision]

## Issue acceptance criteria

- IAC-1: On a clean checkout, `ballast setup` followed by `ballast run start` works with no `ballast trust`, and the baseline records that setup wrote it.
- IAC-2: When `ballast.toml`, the constitution or any protected input differs from what setup wrote and read, setup records no baseline and says `ballast trust` is needed.
- IAC-3: An agent step can never cause a baseline to be recorded: setup refuses to record one while a run is in progress or a `BALLAST_TAMPERED` marker exists.
- IAC-4: The launcher's checks before every run are unchanged; a later change to a protected input still fails closed.

## Known

- The launcher refuses `run`, `ledger` and `intake` without a `trusted.json` whose digests equal the current inputs under `ballast.toml`, `.ballast/spec_workflow`, `.specify` and `.venv` (plus a worktree `.git` pointer). [S: tools/spec_workflow/launcher.py]
- `trusted.json` is a flat map of path to digest, with no field for who recorded it. [S: tools/spec_workflow/launcher.py]
- Setup prints "Review the changed protected inputs, then run `ballast trust`" after every install, and preparation prints the same for a worktree. [S: tools/setup]
- ADR-0007 states that setup never records trust. [S: docs/adr/0007-recoverable-installation.md#decision]
- ADR-0011 states that trust baselines stay per checkout, preparation never reads one, and trust is an operator review of one checkout, never inherited. [S: docs/adr/0011-worktree-preparation.md#decision]
- BL-INV-002 says the launcher refuses until the operator trusts the current inputs. [S: .specify/memory/constitution.md#core-principles]
- The roadmap keeps "the rule that setup cannot silently trust itself" and says changing the trust boundary needs an approved R2 design. [S: docs/plans/2026-10-02-product-roadmap.md]
- Doctor's trust check reads only `installed` and `refusal` from `status --json`. [S: tools/ballast]
- Uncommitted `ballast.toml` changes are outside this feature. [S: specs/55-setup-trust/autonomous/record.md] [S: IAC-2]
- The operator chose to let setup record the baseline: a new ADR supersedes the ADR-0007 clause and BL-INV-002 is amended (D-01, option A). [S: specs/55-setup-trust/autonomous/record.md]
- The operator chose that a committed `ballast.toml` and constitution are eligible only when they equal those on the default branch's remote-tracking ref or those in the previous operator-recorded baseline (D-02, option B). [S: specs/55-setup-trust/autonomous/record.md]
- The operator chose that the preparation path records a baseline under the D-02 conditions (D-03, option A). [S: specs/55-setup-trust/autonomous/record.md]
- Run state lives under `.specify/workflows/runs` and `.specify/workflow-state`, which the trust comparison skips. [S: tools/spec_workflow/launcher.py]

## Inferred

- The new ADR also supersedes ADR-0011's "preparation never records or reads a baseline", since preparation now reads the previous operator baseline and records one. [I]
- "Unchanged from the commit setup read" by itself admits a `ballast.toml` that an agent committed in a plain session, which is why eligibility is tied to the default branch or the operator baseline. [I]
- Setup records no baseline when any run state exists in the checkout, an operator-state run is unfinished, or the in-progress marker or `BALLAST_TAMPERED` exists; such checkouts keep needing `ballast trust`. [P: D-04]
- The baseline's source is a provenance record in operator state beside `trusted.json`, bound to its digest and reported by the launcher's `status --json`; a missing or mismatched record reads as operator `trust`. [P: D-05]

## Undecided

None.

## Decisions

### D-01: Setup may record the trust baseline
- **Status**: settled
- **Question**: May the operator-run `ballast setup` record `trusted.json` for the inputs it wrote, superseding ADR-0007's "setup never records trust" and narrowing BL-INV-002's "until the operator trusts"?
- **Why it matters**: it is the feature itself; yes needs a new ADR, a constitution amendment and launcher and setup changes, no leaves only messaging work.
- **Sources**: [S: Issue #55 body] [S: docs/adr/0007-recoverable-installation.md#decision] [S: docs/adr/0011-worktree-preparation.md#rejected-alternatives] [S: .specify/memory/constitution.md#core-principles] [S: docs/plans/2026-10-02-product-roadmap.md]
- **Options**:
  - A — Supersede the ADR-0007 clause with a new ADR and amend BL-INV-002 to "until the operator trusts them or the operator's setup recorded them under the stated conditions". Consequence: the feature proceeds as an R2 change accepted only at merge.
  - B — Keep setup unable to trust; reduce the repeat work only through clearer setup and doctor messages. Consequence: the Issue's main outcome (no separate `ballast trust`) is not delivered.
- **Recommended default**: A, because the Issue asks for exactly this change and labels it R2.
- **Answer**:
- **Resolution**: Settled by the operator's answer A ("A for #55", commit f290079, written during the block HD-0001 records): the Issue conflicted with ADR-0007, BL-INV-002 and the roadmap rule, and the operator chose to supersede the ADR-0007 clause with a new ADR and amend BL-INV-002; the change stays R2 and is accepted only at merge. [S: specs/55-setup-trust/autonomous/record.md]

### D-02: Which committed `ballast.toml` and constitution are eligible
- **Status**: settled
- **Question**: When is a committed `ballast.toml` and constitution treated as reviewed enough for setup to record a baseline?
- **Why it matters**: it decides whether an agent that commits a changed `ballast.toml` (for example widened `[agents.permissions]`) can get it trusted without human review, which the Issue puts out of scope.
- **Sources**: [S: Issue #55 body] [S: .specify/memory/constitution.md#core-principles] [S: AGENTS.md]
- **Options**:
  - A — The working-tree files equal `HEAD`. Consequence: simplest; a commit made by an agent in a plain session is trusted.
  - B — The files equal those on the default branch's remote-tracking ref (merged through a reviewed PR) or those in the previous operator-recorded baseline. Consequence: a branch that changes the pin or permissions still needs `ballast trust`; setup reads Git state it does not read today.
  - C — A, plus `[standard]` and `[agents.permissions]` unchanged from the default branch. Consequence: other `ballast.toml` keys committed by an agent are trusted.
- **Recommended default**: B, because it is the only option that ties eligibility to a human review.
- **Answer**:
- **Resolution**: Settled by the operator's answer B (commit f290079, written during the block HD-0001 records): the committed `ballast.toml` and constitution must equal those on the default branch's remote-tracking ref or those in the previous operator-recorded baseline. [S: specs/55-setup-trust/autonomous/record.md] Refinement (2026-10-06, after clarify found the remote-tracking ref agent-writable): the default-branch configuration is observed outside `.git`: setup and preparation ask the repository pinned in `ballast.toml` `[github] repository` (never `.git/config` or `origin`) through the operator's own Git authority with `git ls-remote` plus a fetch into a throwaway repository, the same trusted path as #18's branch synchronization (ADR-0005), and compare blob IDs; offline, unauthenticated or unreadable means not eligible and `ballast trust` is needed. Resolved by the driving agent under the operator's standing authority for v1.0 issues (2026-10-05) as the implementation of the operator's answer, listed for merge review. [S: operator answer 2026-10-06] [S: docs/adr/0005-launcher-branch-synchronization.md]

### D-03: The preparation path records a baseline
- **Status**: settled
- **Question**: Does `tools/setup --prepare`, started by the first `ballast run`, `ledger` or `intake`, record a baseline under the same conditions as `ballast setup`?
- **Why it matters**: preparation can be started by an agent driving work, whereas only the operator runs `ballast trust`; ADR-0011 says preparation never records or reads a baseline.
- **Sources**: [S: Issue #55 body] [S: docs/adr/0011-worktree-preparation.md#decision] [S: AGENTS.md]
- **Options**:
  - A — Yes, under the D-02 conditions, from the verified copy's record. Consequence: new worktrees need no human step; an agent-started command can create trust.
  - B — No; only `ballast setup` records. Consequence: each new worktree still needs `ballast setup` or `ballast trust` once.
- **Recommended default**: A only together with D-02 option B; otherwise B.
- **Answer**:
- **Resolution**: Settled by the operator's answer A (commit f290079, written during the block HD-0001 records): preparation records a baseline under the D-02 conditions, from the verified copy's record. [S: specs/55-setup-trust/autonomous/record.md]

### D-04: Which run state prevents recording
- **Status**: assumed
- **Question**: Besides the in-progress marker and `BALLAST_TAMPERED`, does saved run state from earlier runs prevent setup from recording a baseline?
- **Why it matters**: saved run state lies outside the baseline and shows agents ran in the checkout.
- **Sources**: [S: tools/spec_workflow/launcher.py] [S: IAC-3]
- **Options**:
  - A — Refuse when any run state exists under `.specify/workflows/runs` or `.specify/workflow-state`, or an operator-state run is unfinished. Consequence: stricter; such checkouts keep needing `ballast trust`.
  - B — Refuse only on the in-progress marker and `BALLAST_TAMPERED`, as `ballast trust` does. Consequence: matches today's operator check.
- **Recommended default**: A, because it only removes convenience and is reversible.
- **Answer**:
- **Resolution**: Assumed A. Safe because it only adds refusals inside the boundary the operator set in D-02 and D-03 and never widens trust: a refused checkout falls back to today's `ballast trust`. Reversible by dropping the extra check later.

### D-05: Where the baseline's provenance is recorded
- **Status**: assumed
- **Question**: How does doctor learn whether setup or `ballast trust` recorded the baseline without changing the launcher's comparison?
- **Why it matters**: the comparison is out of scope, and doctor must not recompute trust.
- **Sources**: [S: tools/spec_workflow/launcher.py] [S: docs/adr/0002-cli-standard-manifest.md]
- **Options**:
  - A — A provenance file beside `trusted.json`, bound to its digest and reported in `status --json`. Consequence: comparison untouched; a missing or mismatched provenance file reads as operator `trust`.
  - B — A new `trusted.json` schema with a source field. Consequence: the comparison reader changes.
- **Recommended default**: A, because it leaves the comparison unchanged and is reversible.
- **Answer**:
- **Resolution**: Assumed A. Safe because the launcher's comparison stays unchanged (D-07), doctor keeps reading only `status --json`, and an absent or mismatched provenance file reads as operator `trust`, so it can never make a checkout trusted. Reversible because the file is operator state that can be dropped without touching any baseline.

### D-06: An uncommitted `ballast.toml` change is eligible
- **Status**: settled
- **Question**: Is an uncommitted `ballast.toml` change (for example an agent-written pin bump) ever eligible?
- **Why it matters**: it is the Issue's open question for the scope gate.
- **Sources**: [S: Issue #55 body] [S: IAC-2] [S: specs/55-setup-trust/autonomous/record.md]
- **Resolution**: Never eligible: the Issue's scope requires the committed inputs unchanged from the commit setup read and IAC-2 requires no baseline when `ballast.toml` differs; it keeps needing `ballast trust`. [S: Issue #55 body] [S: IAC-2]

### D-07: The launcher's comparison stays unchanged
- **Status**: settled
- **Question**: May the launcher's pre-run checks or the tamper marker change?
- **Why it matters**: it bounds the implementation to setup, provenance and doctor.
- **Sources**: [S: Issue #55 body] [S: IAC-4]
- **Resolution**: No: the Issue puts any change to the fail-closed comparison and `BALLAST_TAMPERED` out of scope, and IAC-4 requires the checks unchanged. [S: Issue #55 body] [S: IAC-4]

## Changes

- D-01, D-02 and D-03 are settled from the operator's answers (commit f290079, block resolution HD-0001); the answers moved from **Answer** to **Resolution** because an autonomous brief has no answered status. [S: operator answers on Issue #55, 2026-10-06]
- D-04 and D-05 are assumed with their conservative defaults; `## Known`, `## Inferred`, `## Permissions and data authority` and `## Undecided` follow. [I]

## Question metrics

- **Rounds**: 0
- **Questions asked**: 0
- **Assumptions adopted**: 2
