# Agent-started execution with Orca

> **Not available.** This adapter is a contract only. Orca does not yet expose a
> native receipt of a session's model, effort, provider and permissions before task
> delivery, which [model routing](model-routing.md) requires ([#179](https://github.com/Hugo-Grellier/ballast/issues/179)).
> The operator dropped it from 2.0 on 2026-10-15. Use the [standalone adapter](standalone.md).

## Entry and ownership

This optional adapter implements [portable execution](execution.md) using Orca.
Read it only when Orca is the selected backend. The portable contract owns queue
limits, worktree isolation, review ownership, cleanup safety, and completion.
Standalone execution has no dependency on this adapter or Orca's skills.

Use Orca's installed `orca-cli` and `orchestration` skills and version-matched
guides. Resolve the correct executable as those skills require, then use it
consistently. Read status/capabilities and discover the repository; never infer
the target from an unrelated focused window. If Orca is unavailable, report the
block rather than silently switching worktree managers or execution hosts.

Queue requests are supervised work: keep ownership until all authorized attempts
settle or report a precise external block. A separately requested full handoff
transfers ownership and follows Orca's handoff contract instead.

## One issue, one implementation worktree

Use Orca worktree placement instead of raw `git worktree` for Orca-managed state.
For independent issues, use `new-top-level` with the exact discovered repository
and configured integration base. Orca parent/child lineage is a UI relationship,
not proof of the correct Git base. Use stacked branches only when explicitly
chosen, with their dependencies and merge order recorded. Do not inherit the
launching conversation's feature branch as the issue's base.

Bind issue number, branch, PR, worktree identity, execution host, and authoritative
Task/Dispatch together. Use the installed issue-linking interface where supported;
otherwise keep the association in execution state, following the portable
contract's privacy rules.

Respect repository setup hooks and record their result. If the startup policy
lets the worker start alongside setup, gate implementation and checks on needed
setup completion.

## Dispatch with explicit routing

The installed orchestration guide supports supervised `worker-start` with a Task,
fresh worktree placement, agent, explicit model, and effort. Resolve concrete
settings using [model-routing.md](model-routing.md); pass the selected pair through
supported launch options. Discover exact flags and capabilities from the installed
guide/help rather than freezing version-specific commands in this document.

The inspected interface supports `new-top-level`, `--repo`, `--base-branch`,
`--model`, and `--effort` for supported agents. In contrast, plain
`worktree create --agent` has no per-call model/effort options. Prefer supervised
dispatch for tracked queue execution, without constructing a second agent terminal
afterward.

Compare `launch.requested` with `launch.effective`, and record what the receipt
actually proves. Effective launch configuration is not independent attestation of
the provider's internal execution. Apply the routing verification contract and
report missing observations. The inspected interface forbids model/effort options
when reusing `--terminal`; a route change therefore needs a fresh worker session
in the same issue worktree, after the prior writer has settled.

Verify the ordering too: `worker-start` composes launch and task injection. A
receipt inspected only after task delivery cannot prove that a mismatch blocked
execution. Strict routing needs backend validation before injection, or a held
worker released after verification. Establish that behavior in the integration
pilot; add a narrow adapter change if the installed path cannot provide it.

## Lifecycle and recovery

Use Orca Run/Task/Dispatch state, structured questions/replies, and completion
messages for supervision. Include the issue, phase, route, ownership, acceptance,
and relevant artifacts in each task. Let Orca provide the live worker lifecycle
preamble; copying IDs into a prompt does not confer lifecycle authority.

A `worker_done` report settles an attempt under Orca's contract. It remains subject
to the portable contract's distinction between settlement and accepted results.

Inspect failed launch receipts, residual resources, and recovery instructions
before any retry. Use the runtime's request replay/idempotency mechanism when
available. Preserve Orca's `live` / `unverifiable` / `exited` verdicts. Follow its
stop, settlement, and release rules;
do not substitute terminal closure for orchestration cleanup.

Project phase milestones and blockers into issue progress and a short Orca card
status. Recover the existing Run/attempts after coordinator restart. Release settled
worker processes through Orca when appropriate; checkout removal/archival remains
subject to the portable cleanup contract.

## Integration acceptance

Run the shared acceptance cases in [execution.md](execution.md), including launch
verification before task input. Reuse Orca's guarantees where demonstrated and
implement only the missing glue. These instructions alone launch no workers.
