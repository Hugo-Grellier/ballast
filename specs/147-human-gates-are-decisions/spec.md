# Feature Specification: Human gates are decisions, not command relays

**Feature Branch**: `feat-147-human-gates-are-decisions`

**Created**: 2026-10-13

**Status**: Draft

**Input**: User description: "Issue #147: human gates are decisions, not command relays; the operator types only what carries a decision and the agent relays start and approvals within the run's autonomy level."

**Discovery brief**: [discovery.md](discovery.md) (input evidence; this spec is the authority)

**Risk**: R2 — changes the launcher's trust model, the headless-agent permission model and what `ballast` executes or downloads. Needs a new ADR that supersedes parts of ADR-0004 and ADR-0009 and amends ADR-0015, and a constitution amendment to BL-INV-002.

## User Scenarios & Testing *(mandatory)*

Give each acceptance scenario a stable ID (`AC-001`, `AC-002`, ...). Task and test descriptions cite the IDs they satisfy, so review can trace each criterion to evidence.

### User Story 1 - Changes merged on the default branch need no trust or setup (Priority: P1)

The operator merges a change to a protected input, for example a `ballast.toml` change, on the pinned repository's default branch. The next run in any checkout of that repository refreshes the trust baseline and regenerates the installed files by itself, and says so, naming the commit it refreshed from. The operator types neither `ballast trust` nor `ballast setup`. A protected-input change that cannot be attributed to the default branch or to an operator-run setup still blocks for `ballast trust`, and no trust path ever records generated agent settings that differ from `ballast.toml`.

**Why this priority**: `ballast trust` came up three times in the #141 run, never because of an untrusted change, and the stale generated settings it accepted broke the implement step. This is the largest share of the operator toil and the core of the trust-model change.

**Independent Test**: In a scratch repository with a reviewed baseline, merge a `ballast.toml` change on the default branch, start a run in another checkout, and observe that it proceeds without `trust` or `setup` and reports the refresh commit; then make a local, unmerged protected-input change and observe the block.

**Acceptance Scenarios**:

1. **AC-001**: **Given** a checkout whose baseline was reviewed for the pinned repository, **When** a change to a protected input (including `ballast.toml`) is merged on that repository's default branch and the next run starts, **Then** the run needs no `ballast trust` and no `ballast setup`, regenerates the installed files from the new configuration, and its output says the baseline was refreshed and from which default-branch commit. [S: IAC-1] [B: D-02] [B: D-05]
2. **AC-002**: **Given** a reviewed baseline, **When** a protected input differs from both the observed default branch and the output of an operator-run `ballast setup` from such inputs (for example a local edit or an unmerged branch change), **Then** the run blocks and names `ballast trust` as the fix, and nothing is refreshed. [S: IAC-2] [B: D-05]
3. **AC-003**: **Given** generated agent settings that no longer match what the current `ballast.toml` produces (for example a stale `extra_allow`), **When** the operator runs `ballast trust`, **Then** trust refuses, records no baseline, and names the regeneration that fixes it. [S: IAC-3]
4. **AC-004**: **Given** generated agent settings that differ from `ballast.toml`, **When** any automatic refresh path (default-branch sync or setup-recorded baseline) would record them, **Then** it refuses to record them and the run blocks instead. [S: IAC-3] [B: D-05]
5. **AC-005**: **Given** the `[github] repository` value is changed by a commit to point at a different repository, **When** the next run starts, **Then** the new repository inherits no trust and the run blocks for `ballast trust`. [S: docs/adr/0015-setup-recorded-trust-baseline.md#decision] [S: IAC-2]
6. **AC-006**: **Given** the default branch cannot be observed through the trusted Git path (network failure, a URL rewrite), or a tamper marker or an unfinished agent step exists, **When** a run starts after a protected-input change, **Then** no automatic refresh happens and the run blocks as it does today. [S: docs/adr/0015-setup-recorded-trust-baseline.md#residual-risks-stated-plainly] [S: IAC-2]

---

### User Story 2 - The agent runs mechanical commands and relays decisions within the run's autonomy (Priority: P1)

The operator works in an agent session. That session runs every `ballast` command that carries no decision (`start`, `resume`, `continue`, headless `step`, `status`, `publish`, `setup`, `intake`). When a decision is due, the agent asks in chat; after the operator says yes, it may relay `start --mode autonomous` and, in a Chat run, a gate approval. The launcher records each relayed action as relayed, naming the relaying agent session, and never presents it as typed by the operator. `reject` stays operator-only, and a human-gated run keeps operator-typed approvals. `ballast trust` keeps working without a terminal, so the agent session may run it on a checkout it set up, as this repository's `ballast.toml` authorizes today (operator decision D-09 on Issue #147).

**Why this priority**: it removes the commands in the #141 run that carried no decision (resume, continue, step) and the TTY round trips for decisions already made in chat, while keeping the record honest about who did what.

**Independent Test**: Start a Chat run from an agent session, run its steps headless, relay one approval after an in-chat yes, and inspect the run record and status output; then attempt the same relay in a human-gated run and observe the refusal.

**Acceptance Scenarios**:

1. **AC-007**: **Given** the workflow policy, **When** a reader looks for which `ballast` commands an agent session may run, **Then** it lists `start`, `resume`, `continue`, headless `step`, `status`, `publish`, `setup` and `intake` as agent-runnable, `ballast trust` as agent-runnable on a checkout the session set up, `approve`, `reject`, `resolve` and `mode` as operator-reserved, and the relayed exceptions per autonomy level, including relayed `resume` and `continue` of a run stopped on a decision. [S: IAC-5] [B: D-04] [S: Issue #147 comment, D-08]
2. **AC-008**: **Given** an eligible R1 feature, **When** the operator drives it from intake to a merged PR through an agent session, **Then** the only actions the operator performs are the decisions (approvals, given in chat or at a TTY as the mode allows) and the merge. [S: IAC-5] [B: D-04]
3. **AC-009**: **Given** the new ADR, **When** a reader looks up an autonomy level (human-gated, Chat, Autonomous), **Then** it states which `ballast` commands an agent session may run at that level, including relayed `start --mode autonomous` and relayed `approve`, and it supersedes the TTY-only parts of ADR-0004 and ADR-0009 and amends ADR-0015 and constitution invariant BL-INV-002. [S: IAC-7] [B: D-01] [B: D-02]
4. **AC-010**: **Given** a Chat run with a pending gate, **When** the operator's agent session relays an approval the operator gave in chat, **Then** the approval is recorded as relayed, names the relaying agent session, quotes no approval wording, and status and the run record display it as relayed, never as TTY-typed. [S: IAC-8] [B: D-01]
5. **AC-011**: **Given** a human-gated run with a pending gate, **When** an agent session attempts a relayed approval, **Then** it is refused, nothing is recorded, and the refusal says the operator must approve at a TTY. [S: IAC-8] [B: D-01]
6. **AC-012**: **Given** an Autonomous run, **When** an agent session attempts a relayed approval, **Then** it is refused because an Autonomous run has no human gate before merge, and no human-approval record is written. [S: IAC-8] [S: .specify/memory/constitution.md#core-principles]
7. **AC-013**: **Given** the operator said yes in chat to an Autonomous start for an eligible Issue, **When** the agent session relays `ballast run start --mode autonomous`, **Then** the run starts and its record states the mode start was relayed by the named agent session, not typed by the operator. [S: IAC-7] [S: IAC-8] [B: D-01]
8. **AC-014**: **Given** an agent running inside a confined workflow step, **When** it attempts any `ballast run` command, including a relayed approval or start, **Then** it is refused as today; only the operator's own agent session outside any step may relay. [S: AGENTS.md#issue-and-spec-workflow] [S: IAC-8]
9. **AC-015**: **Given** a Chat run, **When** the agent session runs the next step headless, **Then** the step runs under the same confinement as an Autonomous step without the operator's terminal, and the run stops at the next gate for the operator's decision. [S: Issue #147 body] [B: D-04]
10. **AC-016**: **Given** an agent session, **When** it attempts `ballast run reject`, **Then** the command still requires the operator at a TTY and is never accepted as relayed; **When** it runs `ballast trust` outside any workflow step, **Then** trust behaves as today (no terminal required), and inside a workflow step it is refused. [S: Issue #147 body] [B: D-04] [S: Issue #147 comment, D-09]
11. **AC-028**: **Given** an Autonomous run stopped on a block that carries a decision (decision, contradiction, review-finding, fix-cycle limit or ineligible), **When** the agent session relays `ballast run resume` or `continue` after the operator answered in chat, **Then** it must pass `--relayed-by` and a `--ref` naming the operator's answer, and the block resolution is recorded as relayed by that session; without `--ref` the relay is refused and nothing is recorded. A run stopped on a block that carries no decision (branch synchronization, interruption, usage limit, postcondition) may be resumed by the agent session without asking, still recorded as relayed. [S: Issue #147 comment, D-08]

---

### User Story 3 - Approve several pending gates at once (Priority: P2)

When several gates are pending (for example scope, intent, plan and tasks after provisional recording), the operator approves them with one command that lists every decision being approved and asks for one typed confirmation.

**Why this priority**: four separate TTY approvals in the #141 run carried decisions already made; one confirmation keeps the decision while removing the repetition.

**Independent Test**: With four pending gates, run the batch approval at a TTY, confirm once, and check that all four are recorded with the listed decisions; repeat with a gate that is not pending and check nothing is recorded.

**Acceptance Scenarios**:

1. **AC-017**: **Given** a run with pending gates scope, intent, plan and tasks, **When** the operator runs `ballast run approve RUN scope intent plan tasks` at a TTY, **Then** the command shows every decision being approved and takes one typed confirmation that records all four. [S: IAC-4] [B: D-03]
2. **AC-018**: **Given** the same pending gates, **When** the operator runs `ballast run approve RUN --through tasks`, **Then** it selects every pending or stale gate up to and including tasks, lists each, and takes one typed confirmation. [S: IAC-4] [B: D-03]
3. **AC-019**: **Given** a batch that names a gate that is neither pending nor stale, or a confirmation that does not match, **When** the batch approval runs, **Then** it records no approval at all and says why. [S: IAC-4] [I]
4. **AC-020**: **Given** a batch approval in a human-gated run, **When** no TTY is attached, **Then** it is refused; in a Chat run a relayed batch follows the relayed-approval rules and is recorded as relayed per gate. [S: IAC-4] [S: IAC-8] [B: D-03]

---

### User Story 4 - Recover without extra commands (Priority: P2)

Common interruptions recover through the commands the agent may already run: `discard-runs` does not force a re-trust when nothing protected changed and honours `--help`; `resume` after an implementation postcondition block reruns `implement`; a step stopped by a usage limit closes as interrupted and resumable; an Autonomous start on a branch not named for the Issue offers the right branch.

**Why this priority**: each of these cost the #141 run one or more operator commands with no decision in them, but they are narrower than the trust and relay changes.

**Independent Test**: Exercise each recovery path in a scratch repository and count the operator commands needed.

**Acceptance Scenarios**:

1. **AC-021**: **Given** existing run state, **When** the operator runs `ballast discard-runs --help`, **Then** it prints help, exits successfully and changes nothing. [S: IAC-6]
2. **AC-022**: **Given** existing run state, **When** `ballast discard-runs` is given an unknown argument, **Then** it refuses and changes nothing. [S: IAC-6] [I]
3. **AC-023**: **Given** protected inputs unchanged since the recorded baseline, **When** the operator discards runs and a run starts next, **Then** no `ballast trust` is required. [S: Issue #147 body]
4. **AC-024**: **Given** a run blocked by a `postcondition` failure on implementation, **When** it is resumed, **Then** it reruns `implement` rather than re-entering at `validate-implementation`. [S: Issue #147 body]
5. **AC-025**: **Given** an agent step stopped by a usage limit whose wrapper confirmed the agent's processes stopped, **When** the operator or agent next looks at the run, **Then** the step is closed as interrupted and the run is resumable without `discard-runs` or `trust`. [S: Issue #147 body] [P: D-07]
6. **AC-026**: **Given** an agent step whose wrapper died without confirming the agent's processes stopped, **When** the next run starts, **Then** it keeps the unfinished-step refusal. [S: docs/adr/0009-chat-mode-operator-driven-steps.md#decision] [P: D-07]
7. **AC-027**: **Given** an Autonomous start on a branch whose name lacks the Issue number, **When** it runs at a TTY, **Then** it offers to create or switch to a branch named for the Issue and proceeds on a yes; without a TTY it refuses and prints the exact branch command, never switching the checkout unasked. [S: Issue #147 body] [P: D-06]

---

### Edge Cases

- The default branch moves between the observation and the refresh: the refresh records only the commit it observed and names it; a later move is evaluated on the next run.
- The default branch changes `[agents.permissions]` or `[autonomous]` in a way that widens authority: it is refreshed automatically (D-02, option A); the new ADR states this residual risk, so branch protection on the pinned repository becomes that review.
- Regenerating installed files during sync needs the pinned standard downloaded: the download uses the same fixed source as `ballast setup`; if it fails, the run blocks with one combined fix instead of refreshing partially.
- A relayed approval names a gate that is not pending, or a gate the mode does not allow: refused, nothing recorded.
- The operator's agent session cannot prove that the operator said yes: the record is a labeled claim by that session, never shown as operator-typed.
- `discard-runs` after protected inputs did change: re-trust is still required, as today.
- A relayed and a TTY approval for the same gate race: the first recorded wins; the second is refused as not pending.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The launcher MUST refresh the trust baseline itself when every changed protected input matches the pinned `[github] repository` default branch, observed through the trusted Git path of ADR-0005 and ADR-0015, or was produced by an operator-run `ballast setup` from such inputs, and MUST report that the baseline was refreshed and from which commit. [S: IAC-1] [B: D-02]
- **FR-002**: The launcher MUST regenerate the installed files, including generated agent settings, when branch sync or the default-branch refresh brings in a `ballast.toml` change, or block with one combined fix when regeneration cannot complete. [S: Issue #147 body] [B: D-05]
- **FR-003**: The launcher MUST keep blocking for `ballast trust` when any protected-input change cannot be attributed to the default branch or to an operator-run setup, when the pinned repository was repointed, when the default branch cannot be observed, or when a tamper marker or unfinished agent step exists. [S: IAC-2] [S: docs/adr/0015-setup-recorded-trust-baseline.md#decision]
- **FR-004**: `ballast trust` and every automatic refresh MUST refuse to record generated agent settings that differ from what the current `ballast.toml` produces. [S: IAC-3]
- **FR-005**: `ballast discard-runs` MUST print help for `--help` and refuse unknown arguments, changing nothing in either case. [S: IAC-6] [I]
- **FR-006**: `ballast discard-runs` MUST NOT force a re-trust when protected inputs are unchanged since the recorded baseline. [S: Issue #147 body]
- **FR-007**: `ballast run approve` MUST accept several gates, as a list or as `--through GATE`, show every decision being approved, take one typed confirmation, and record either all of them or none. [S: IAC-4] [B: D-03]
- **FR-008**: The workflow policy MUST list the `ballast` commands an agent session may run (`start`, `resume`, `continue`, headless `step`, `status`, `publish`, `setup`, `intake`) and those reserved for the operator (`approve`, `reject`, `resolve`, `mode`; `trust` is agent-runnable outside a step, D-09), with the relayed exceptions per autonomy level, and which block categories carry a decision so that a relayed `resume` or `continue` of them needs the operator's in-chat answer as `--ref`. [S: IAC-5] [B: D-04] [S: Issue #147 comment, D-08]
- **FR-009**: A Chat run MUST offer a headless `step` the agent session can run under the same confinement as Autonomous steps, stopping at each gate for the operator's decision. [S: Issue #147 body] [B: D-04]
- **FR-010**: The launcher MUST accept a relayed approval only in a Chat run, and a relayed `start --mode autonomous` only for a run eligible for Autonomous mode; it MUST refuse a relayed approval in a human-gated or Autonomous run and every relayed `reject`; `trust` keeps today's terminal-free behavior outside a workflow step (D-09). [S: IAC-8] [B: D-01]
- **FR-011**: A relayed action MUST be recorded and displayed as relayed, naming the relaying agent session and quoting no approval wording, and MUST never be presented as typed by the operator in any record, status output, artifact or PR text. [S: IAC-8] [S: .specify/memory/constitution.md#core-principles]
- **FR-012**: An agent inside a confined workflow step MUST remain unable to run `ballast run` commands, including relayed ones. [S: AGENTS.md#issue-and-spec-workflow]
- **FR-013**: A new ADR MUST record which `ballast` commands an agent session may run at each autonomy level, including relayed `start --mode autonomous` and `approve`, supersede the conflicting parts of ADR-0004 and ADR-0009, amend ADR-0015, and state the residual risk that branch protection on the pinned default branch becomes the review of configuration changes. [S: IAC-7] [B: D-01] [B: D-02]
- **FR-014**: The constitution MUST carry an amendment to BL-INV-002 that admits the default-branch refresh, with reason and compatibility recorded in its amendment history. [B: D-02] [S: specs/147-human-gates-are-decisions/autonomous/record.md#block-resolutions]
- **FR-015**: `ballast run resume` after a `postcondition` block on implementation MUST rerun `implement`. [S: Issue #147 body]
- **FR-016**: A step whose wrapper confirmed the agent's processes stopped, including after a usage limit, MUST close as interrupted and resumable; a step whose wrapper died unconfirmed MUST keep the unfinished-step refusal. [S: Issue #147 body] [P: D-07]
- **FR-017**: Autonomous start on a branch not named for the Issue MUST offer to create or switch to an Issue-named branch at a TTY, and without a TTY refuse and print the exact branch command. [S: Issue #147 body] [P: D-06]
- **FR-018**: The operator-facing documentation (workflow policy, AGENTS.md guidance and its template, chat-run instructions) MUST describe the agent-runnable commands, relayed decisions and automatic refresh consistently with the new ADR. [S: IAC-5] [S: IAC-7] [I]
- **FR-019**: Tests MUST cover the refusal and tamper paths of every new automatic or relayed path: unattributed change, repointed repository, unobservable branch, stale generated settings, relayed approval in a forbidding mode, relay from inside a step. [S: .specify/memory/constitution.md#core-principles]
- **FR-020**: The workflow tools MUST stay standard-library-only and run under `python3 -I -S`, and nothing the launcher executes during a refresh or regeneration may come from an agent-writable checkout. [S: .specify/memory/constitution.md#core-principles]

### Key Entities

- **Trust baseline**: the operator-state record of reviewed protected inputs; gains a refresh origin (default-branch commit or operator-run setup) that run output names.
- **Approval record**: a per-gate record of a human decision; gains an origin of either TTY-typed by the operator or relayed by a named agent session, with no quoted approval wording for relayed ones.
- **Mode start record**: who started a run in a given mode; gains the relayed origin for `start --mode autonomous`.
- **Agent command matrix**: the policy and ADR table of which `ballast` commands an agent session may run, operator-reserved commands, and the relayed exceptions per autonomy level.

### Non-goals

- Model routing (#138), context budget (#143), autonomous PR completion (#141), and the runner check environment and timeout bug (#146).
- Letting an agent run `ballast run reject`, or `ballast trust` inside a workflow step; outside a step `trust` keeps today's terminal-free behavior (D-09).
- Changing what a confined agent inside a step may do.
- Splitting the work into Epic children.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Replaying the #141 scenario (a `ballast.toml` change merged on the default branch, then a feature run through implementation) needs zero `ballast trust` and zero `ballast setup` commands from the operator, against three trusts and one setup before.
- **SC-002**: For an eligible R1 feature driven from an agent session, every operator action is a decision or the merge; the share of operator-typed commands that carry no decision drops from 9 of 14 in the #141 run to 0.
- **SC-003**: Approving four pending gates takes one command and one typed confirmation instead of four of each.
- **SC-004**: 100% of relayed actions in tested runs are displayed as relayed with the agent session named; none appears as operator-typed.
- **SC-005**: Every refusal path listed in FR-019 has a test that shows the block and that nothing was recorded.

## Assumptions

- The launcher cannot verify that the operator said yes in chat; a relayed approval is a labeled claim by the operator's agent session, which is why it is recorded as relayed. [I]
- Only the operator's own agent session outside any confined step can relay; the existing step confinement is the boundary. [I]
- A batch approval is all-or-nothing, so a partial batch never leaves gates half approved. [I]
- `discard-runs` refuses unknown arguments, like the other `ballast` subcommands. [I]
- Autonomous start without a TTY prints the branch command instead of prompting (D-06). [P: D-06]
- Only a step whose wrapper confirmed its processes stopped closes as interrupted (D-07). [P: D-07]
- The ADR text and the constitution amendment stay agent-provisional until the PR merge, which is the single human approval of this Autonomous R2 run. [I]
- The non-goal on agent-run `trust` follows the operator's D-09 resolution (HD-0004), which postdates the discovery brief: an agent session may run `ballast trust` outside a workflow step as today, never inside one, and never `ballast run reject`. The brief's non-goal and the Issue body's "trust is operator-reserved" read as superseded by D-09 on this point. [I]
- A change to `tools/ballast` or `tools/setup` needs the end-to-end scratch run before merge, as the project workflow policy requires. [S: docs/policies/project/workflow.md#gates]
