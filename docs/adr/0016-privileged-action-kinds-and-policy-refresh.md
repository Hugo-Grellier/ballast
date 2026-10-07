# ADR-0016: Privileged actions are fixed kinds, and the operator can refresh a run's policy

- Status: proposed (2026-10-07, with the fix for Issue #95). Resolved by the driving agent under the operator's standing authority for v1.0 issues (2026-10-05), listed for merge review; merging the PR is the human approval that accepts it.
- Amends: [ADR-0004](0004-autonomous-provisional-decisions.md) (the `[autonomous]` policy snapshot) and [ADR-0010](0010-autonomous-resume-and-bounded-recovery.md) (resume keeps everything recorded at start)

## Context

An Autonomous run compares every declared pre-merge privileged action with `[autonomous] authorized_privileged_actions` by exact text. Agents phrase the same action differently from run to run, so no authorization in `ballast.toml` ever matched (#95, item 5). The run also keeps the policy snapshot taken at start, so an authorization the operator adds after an `ineligible` block never reaches that run, and the only recovery was a new run (#95, item 2).

## Decision

- **Kinds, not text.** A draft or review entry declares each action as `KIND` or `KIND: description`. `KIND` is one of `operator-trust`, `scratch-repository`, `secret-provisioning`, `network-access`, `external-write`, `permission-change` (authorizable), `deploy`, `release`, `merge`, `mark-ready` (never authorizable, FR-027) or `other` (never authorizable: an action no kind covers always blocks). The recorder refuses any other kind as a correctable draft error, so the step is retried. Authorization compares only the declared action's kind (case and spacing of the declaration are folded), and only a configuration entry spelled exactly as a kind authorizes that kind.
- **Legacy entries keep working, never wider.** An `authorized_privileged_actions` entry that is not exactly a kind (`secret provisioning`, `operator-trust: only for X`, free text) is kept with a warning and authorizes only an action with exactly its text (a scope record or a decision already in a run's log), as before. New drafts cannot produce most such text, so a legacy entry can only authorize less than before. An entry or action that is `other` or starts with a never-authorized action (`deploy production`) is never authorized, even by exact text.
- **Policy refresh is an explicit operator resume.** `ballast run resume RUN_ID --refresh-policy` re-reads `[autonomous]` after branch synchronization, replaces the run's policy snapshot and records the previous and new policy with the block resolution, which the run record shows. It reads `ballast.toml` only when its bytes equal the baseline `ballast trust` recorded, with bound `trust` provenance; a baseline `ballast setup` recorded (ADR-0015), a legacy baseline without provenance, or none, refuses, and the operator runs `ballast trust` again. A refreshed policy that no longer allows the run's risk, boundaries or declared actions refuses the resume and records nothing. Limits, mode, risk and integrations still never change on resume.

## Consequences

- An operator authorizes a class of action once per project (for example `operator-trust`), and agents can match it.
- Authority still comes only from the operator: an agent cannot edit `ballast.toml` (a protected input), setup cannot record a baseline while a run is unfinished, and the refresh reads only bytes the operator's own `ballast trust` vouched for. Anyone able to run `ballast run resume` can apply the trusted policy to a stopped run, but not change what it says. A refresh can widen a run only to what the operator trusted, and can also narrow it.
- A project whose `ballast.toml` lists free-text actions gets a warning on every Autonomous start and should replace them with kinds; this repository's own entries are left for the operator to migrate.

## Rejected alternatives

- Re-reading `[autonomous]` on every resume: it would silently change a run whose operator only meant to resolve a block.
- Fuzzy matching of free text: unpredictable authority.
- A separate launcher command to re-evaluate eligibility: the resume already holds the run lock, synchronizes the branch and records the operator's block resolution, which is where the change belongs.
