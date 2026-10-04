# ADR-0004: Autonomous runs record agent-provisional decisions outside agent reach

- Status: proposed (with the plan of [feature 27](../../specs/27-autonomous-core/plan.md), decisions D-1, D-3, D-6 and D-7)
- Feature: [27-autonomous-core](../../specs/27-autonomous-core/spec.md), FR-001 to FR-030
- Numbering: the plan named this ADR `0001`; `0003` went to feature 17's ADR, which merged first, so this is `0004`; see [DEC-0001](../../specs/27-autonomous-core/decisions.md)

## Context

Every feature run stops at seven human gates. Issue #27 lets the operator run an eligible feature (R0, R1 or R2) to a Draft PR with no approval prompt, so that agents decide at those gates and the human approves once, at merge. The gate decisions then come from agents, so the mode, the decision record and publication must stay out of agent reach, and nothing may present an agent decision as human approval. Spec Kit 1.0.11 gates always prompt on a TTY, and there is no evidence of conditional steps. The human-gated workflow must stay byte-identical (SC-007).

## Decision

- **A separate gate-less workflow** (D-1, research R-01). `ballast-autonomous` replaces each gate of `ballast-feature` with an agent decision step followed by a trusted recorder step, and keeps every validator. `run.py` selects it from the operator-chosen mode. `ballast-feature` is unchanged.
- **An operator-state, hash-chained decision log with committed projections** (research R-05). The mode, limits, eligibility and the provisional decisions live in `$XDG_STATE_HOME/ballast/<checkout>/runs/<run>/`, where no agent can write. Agents write only untrusted drafts; trusted recorders validate them and append them to `decisions.jsonl`, where each line carries the SHA-256 of the previous one. `specs/<f>/autonomous/record.md` and the provisional block in `intent.md` are deterministic projections that every later check re-renders and compares, so an edit fails the run.
- **Publication by the trusted runner** (D-3, research R-11). After the workflow completes, `run.py`, as the operator, commits the changes since the recorded start `HEAD` with hooks and filters disabled, pushes the branch without force and opens one Draft PR whose body is rendered from the log. Agents never get push, PR, merge or release authority.
- **Continuation as a gate-only workflow** (research R-10). Autonomous `resume` is refused until #18. `ballast run continue` records a human decision, lowers the run to human-gated and starts `ballast-continue`, which has only validators and the human gates. Earlier provisional decisions stay in the log and in `record.md`. No path raises a run to Autonomous.
- **Bubblewrap confinement for Autonomous agent steps** (D-7, research R-02). Every Autonomous agent step and the `run-checks` step runs under `bwrap` with a read-only host, a writable worktree minus its protected inputs, the operator state and Git directory read-only, credentials and the session bus hidden. A missing `bwrap` or a failed self-test refuses the start. Human-gated runs are unchanged.
- **Constitution BL-INV-006** (D-6): a provisional decision is never human approval; only merging the PR that contains it accepts it.

## Consequences

- An eligible feature reaches a Draft PR unattended, and the merge reviewer sees every provisional decision, its basis and its evidence from the PR alone.
- Two more workflow definitions and a `ballast` Spec Kit extension ship with the standard; a gate-structure change in `ballast-feature` must be mirrored in `ballast-continue` (a test compares the gates).
- `bwrap` with user namespaces becomes a host prerequisite for Autonomous only.
- `ballast.toml` gains a required `[checks]` table for Autonomous and an optional, narrowing-only `[autonomous]` table.
- A blocked run cannot resume autonomously; recovery is always human-gated until #18.

## Rejected alternatives

- One workflow with mode-conditional gates: engine support is unverified, and it risks changing human-gated behavior.
- Piping `approve` into gate prompts: the runner would approve on the human's behalf and the record would read as a human approval.
- An agent-written committed Markdown record, or the run ledger, as the source of truth: the first is forgeable, the second forbids prose and may be reachable from a primary checkout.
- Publishing from a workflow shell step: a forge failure would fail a step that an Autonomous run cannot resume.
- systemd `ReadOnlyPaths` instead of `bwrap`: silently ignored by a user manager on hosts that restrict unprivileged user namespaces.
