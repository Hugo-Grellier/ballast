# Agent-started execution with Orca

## Entry and ownership

This optional adapter targets [portable execution](execution.md) using Orca.
Read it only when Orca is the selected backend. The portable contract owns queue
limits, worktree isolation, review ownership, cleanup safety, and completion.
Standalone execution has no dependency on this adapter or Orca's skills.

**Status: dispatch blocked.** The installed Orca 1.4.220 public interface does
not establish the required pre-task session verification. Only read-only
qualification is implemented. See [the evidence and remaining acceptance](evidence/orca.md).
Do not launch issue workers through the mappings below until this gap is closed.

After resolving the executable with the installed skill, inspect it with:

```sh
python3 -I -S tools/orca.py --executable orca-ide --model gpt-6-luna --effort low
```

Substitute the resolved executable and selected concrete route. This command
loads the version-matched guides, status and public schema. It always exits 1:
advertised routing flags or a newer version alone never enable dispatch. It
creates no Run, Task, worker, claim or worktree, and emits no account identifiers,
machine paths, terminal previews or raw backend diagnostics. CI and implicit
remote targets are refused before calling Orca. Failure never tries another
executable or switches to standalone.

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

## Required dispatch integration

The inspected orchestration guide supports supervised `worker-start` with a Task,
fresh worktree placement, agent, explicit model, and effort. Resolve concrete
settings using [model-routing.md](model-routing.md). Discover exact flags and capabilities from the installed
guide/help rather than freezing version-specific commands in this document.

The inspected interface supports `new-top-level`, `--repo`, `--base-branch`,
`--model`, and `--effort` for supported agents. In contrast, plain
`worktree create --agent` has no per-call model/effort options. Future integration
must use supervised dispatch without constructing a second worker afterward.

`launch.effective` in 1.4.220 copies requested preferences; matching fields
do not prove resolved session configuration. The inspected interface forbids model/effort options
when reusing `--terminal`; a route change therefore needs a fresh worker session
in the same issue worktree, after the prior writer has settled.

`worker-start` composes launch and task injection. A
receipt inspected only after task delivery cannot prove that a mismatch blocked
execution. Strict routing needs backend validation before injection, or a held
worker released after verification. A runtime capability advertising structured
session hold is insufficient when the public CLI does not expose that operation
for supervised dispatch. Do not call private RPCs or parse a TUI screen as the
missing same-session contract. Integrate and prove a public native guarantee
before enabling this path.

## Lifecycle and recovery

These are mappings for the eventual dispatch integration, not capabilities
implemented by the qualification command. Use them to inspect already existing
native attempts without creating replacement workers.

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

### Recovery mapping for existing attempts

Load the installed orchestration recovery reference before any lifecycle action.
Use the existing Run and Dispatch identities, never a newly created substitute.

| Operation | Native authority / constraint |
| --- | --- |
| Discover repository and worktree | `repo list`, `worktree show`; match explicit repository, configured integration base, actual Git branch/revision and issue. |
| Prepare isolated worktree | Future integration: reserve the portable issue claim before `worktree create`; pass exact repo/base and `--no-parent`, record setup result. Do not launch an agent with that command. |
| Recover unknown mutation | `orchestration request-show --request ID`; inspect Task/Dispatch/terminal residuals. Use the original `--retry-request` only as its receipt directs. Absence does not prove no effect. |
| Refresh worker identity | `orchestration worker-list --run RUN --json`, with remote enumeration/pagination when required by the installed guide. Recover authoritative IDs and handles; old terminal generations are not ownership. |
| Inspect output | `orchestration worker-show` and bounded `worker-read`; a live PTY does not prove a live agent. Respect source-change cursors. |
| Questions/results | Native injected preamble, structured `ask`/reply and `worker_done`; process all messages before acknowledgment. The coordinator never sends worker settlement on its behalf. |
| Release | Only after accepted settlement, native `worker-release`; retained pre-existing/user-owned terminals stay retained. Follow uncertain-release receipts, never substitute terminal closure. |
| Public progress | Project native attempt/phase, route verification and blockers into the issue and card status; omit machine paths, account details and raw terminal text. |

The eventual integration reuses portable admission locks and budgets, recording
only native identity references and verification evidence in the existing claim.
Orca remains lifecycle authority; no second execution database or shadow worker.
Unverifiable liveness retains its reservation. Runtime restart requires inspection
and handle refresh before further input. Cancellation is a request to stop, not
proof of exit. No automatic cleanup, replay or retry is implemented here.

### Remaining live proof

Run the shared acceptance cases in [execution.md](execution.md), including launch
verification before task input. Reuse Orca's guarantees where demonstrated and
implement only the missing glue. These instructions alone launch no workers.
