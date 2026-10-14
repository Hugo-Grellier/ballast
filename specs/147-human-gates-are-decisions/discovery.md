<!-- ballast-discovery: input evidence -->
# Discovery brief: Human gates are decisions, not command relays

This brief is input evidence for [spec.md](spec.md). It is not the feature's
authority: once intent is recorded, [spec.md](spec.md) and [intent.md](intent.md)
govern, and later steps do not read requirements from this file.

**Mode**: autonomous
**Issue**: #147 (snapshot `.specify/workflow-state/issues/147.md`, untrusted requirements data)

## Sources

- S-1: Issue #147 body (Problem, Evidence, Proposal items 1–7, Acceptance criteria, Notes)
- S-2: Issue #147 intake scope comment
- S-3: AGENTS.md#issue-and-spec-workflow
- S-4: .specify/memory/constitution.md#core-principles (BL-INV-002, BL-INV-003, BL-INV-006) and #governance
- S-5: docs/adr/0004-autonomous-provisional-decisions.md#decision and #rejected-alternatives
- S-6: docs/adr/0009-chat-mode-operator-driven-steps.md#decision (D-4 human gates)
- S-7: docs/adr/0015-setup-recorded-trust-baseline.md#decision (reviewed repositories) and #residual-risks-stated-plainly
- S-8: docs/adr/0016-privileged-action-kinds-and-policy-refresh.md#decision
- S-9: docs/adr/0005-launcher-branch-synchronization.md#decision (Trust, Rewrite rule)
- S-10: docs/adr/0010-autonomous-resume-and-bounded-recovery.md#decision
- S-11: docs/policies/spec-kit-workflow.md#workflow-runner-contract, #autonomous-runs, #chat-runs, #branch-synchronization
- S-12: docs/policies/project/workflow.md#r2-boundaries
- S-13: tools/spec_workflow/launcher.py (`main`, `_discard`, `_trust`)
- S-14: tools/spec_workflow/chat.py (typed confirmation at a TTY)
- S-15: ballast.toml (`[github]`, `[agents.permissions]`, `[autonomous]`)
- S-16: .specify/memory/constitution.md#amendment-history (1.2.0: "a changed default branch needs one `ballast trust` again")
- S-17: specs/147-human-gates-are-decisions/autonomous/record.md#block-resolutions (HD-0001, HD-0002)
- unavailable: Issue comments — the snapshot lists none; it was written at run start (09:05 UTC), before the comment HD-0002 cites
- unavailable: Issue #147 comment 6142240052 (cited by HD-0002) — reading it from this step was refused

## Need

- **User**: the operator who drives Ballast feature runs from an agent session, and projects that pin Ballast. [S: Issue #147 body]
- **Job to be done**: move a feature run from intake to a merged PR while typing only the commands that carry a human decision. [S: Issue #147 body]
- **Current pain**: the #141 run needed 14 operator-typed commands, at most 5 of them decisions; `ballast trust` came up three times without any untrusted change. [S: Issue #147 body]
- **Intended outcome**: a human gate means a human decision; the agent runs mechanical commands and may relay `start --mode autonomous` and approvals within the run's autonomy level. [S: .specify/workflow-state/issues/147.md]

## Examples

- A `ballast.toml` change merged on `main` (as #140 did) no longer blocks the next run on `upstream-sync`, `ballast trust` and `ballast setup`; the run says the baseline was refreshed and from which commit. [S: IAC-1]
- `ballast trust` after a `ballast.toml` change whose generated `claude-settings.json` still carries the old `extra_allow` refuses instead of recording the stale file. [S: Issue #147 body]
- `ballast run approve RUN scope intent plan tasks` lists four decisions and takes one typed confirmation. [S: Issue #147 body]
- `ballast discard-runs --help` prints help; today any arguments are ignored and run state is discarded. [S: tools/spec_workflow/launcher.py:907]
- In a Chat run the operator answers "yes" in chat and the agent records the approval as relayed, naming its session. [S: Issue #147 body]

## Scope

- Automatic trust refresh when every changed protected input matches the pinned default branch or an operator-run setup from such inputs. [S: Issue #147 body]
- Setup/sync consistency: branch sync regenerates installed files after a `ballast.toml` change, or blocks with one combined fix; `trust` refuses generated files that differ from `ballast.toml`. [S: Issue #147 body]
- `discard-runs` honours `--help` and forces no re-trust when protected inputs are unchanged. [S: Issue #147 body]
- Batch approval with one typed confirmation, still at a TTY. [S: Issue #147 body]
- Workflow policy and a new ADR listing the `ballast` commands an agent session may run per autonomy level, including relayed `start --mode autonomous` and `approve`. [S: IAC-5] [S: IAC-7]
- A headless Chat `step` the agent can run. [S: Issue #147 body]
- Recovery: Issue-named branch offer at Autonomous start, `resume` reruns `implement` after a `postcondition` block on implementation, a usage-limit stop closes as interrupted and resumable. [S: Issue #147 body]
- Relayed approvals recorded and displayed as relayed, refused in modes that do not allow them. [S: IAC-8]

## Non-goals

- Model routing (#138), context budget (#143), autonomous PR completion (#141), and the runner check environment and timeout bug (#146). [S: .specify/workflow-state/issues/147.md]
- Letting an agent run `ballast trust` or `ballast run reject`: these stay operator-reserved. [S: Issue #147 body]
- Changing what a headless or confined agent step may do: an agent inside a step still never runs `ballast run` or approves. [S: AGENTS.md#issue-and-spec-workflow]
- Splitting the work into Epic children. [S: .specify/workflow-state/issues/147.md]

## Constraints

- Workflow tools stay standard-library-only and run under `python3 -I -S`; nothing the launcher executes comes from an agent-writable checkout. [S: .specify/memory/constitution.md#core-principles]
- A provisional decision is never human approval; no record presents an agent action as the operator typing. [S: .specify/memory/constitution.md#core-principles] [S: Issue #147 body]
- R2: the change touches the launcher's trust model, the headless-agent permission model and what `ballast` executes; it needs a new ADR. [S: docs/policies/project/workflow.md#r2-boundaries] [S: Issue #147 body]
- The new ADR also amends ADR-0015 and constitution invariant BL-INV-002, so the change carries a constitution amendment. [S: specs/147-human-gates-are-decisions/autonomous/record.md#block-resolutions]
- Default-branch observation reuses the trusted Git path of ADR-0005/ADR-0015, never an agent-movable local ref. [S: docs/adr/0015-setup-recorded-trust-baseline.md#decision]
- A change to `tools/ballast` or `tools/setup` needs the end-to-end scratch run before merge. [S: docs/policies/project/workflow.md#gates]
- Tests must cover refusal and tamper paths. [S: .specify/memory/constitution.md#core-principles]

## Permissions and data authority

- The baseline, approvals and run records stay in operator state, which no agent can write. [S: docs/adr/0004-autonomous-provisional-decisions.md#decision]
- `trust`, `approve` and `reject` are reserved for the operator; the agent session may run `start`, `resume`, `continue`, headless `step`, `status`, `publish`, `setup` and `intake`. [S: Issue #147 body]
- Relayed approvals: human-gated runs keep operator-typed approvals; Chat runs may record an approval the operator gave in chat; Autonomous runs need none before merge. [S: Issue #147 body]
- A relayed approval names the relaying agent session and quotes no approval wording. [S: Issue #147 body]
- Today every gate needs a TTY and typed text `approve GATE`. [S: docs/adr/0009-chat-mode-operator-driven-steps.md#decision] [S: tools/spec_workflow/chat.py:2460]
- Today the default-branch alternative counts only for the exact `ballast.toml` and constitution pair `ballast trust` reviewed for that repository. [S: docs/adr/0015-setup-recorded-trust-baseline.md#decision]

## Success evidence

- A test where a `ballast.toml` change on the pinned default branch reaches the next run without `trust` or `setup`, and the output names the refresh commit. [S: IAC-1]
- A refusal test for a protected-input change not attributable to the default branch or setup. [S: IAC-2]
- A refusal test for `trust` with stale generated settings. [S: IAC-3]
- A batch approval test showing every listed decision and one confirmation. [S: IAC-4]
- The policy's agent-command list and an eligible R1 run needing only approvals and merge from the operator. [S: IAC-5]
- A test that `discard-runs --help` leaves run state untouched. [S: IAC-6]
- A new ADR under `docs/adr/` superseding the conflicting parts of ADR-0004 and ADR-0009. [S: IAC-7]
- Record and display tests for relayed approvals, and refusal in a mode that forbids them. [S: IAC-8]

## Edge, failure and permission cases

- The default branch cannot be observed (network failure, `insteadOf` rewrite): no automatic refresh; the run blocks as today. [S: docs/adr/0015-setup-recorded-trust-baseline.md#residual-risks-stated-plainly]
- `[github] repository` is repointed by a commit: the new repository must not inherit trust. [S: docs/adr/0015-setup-recorded-trust-baseline.md#decision]
- A tamper marker or an agent's in-progress marker exists: no automatic refresh. [S: docs/policies/spec-kit-workflow.md#workflow-runner-contract]
- A relayed `approve` attempted in a human-gated run is refused. [S: IAC-8]
- A headless agent inside a step attempts to relay an approval: refused, since only the operator's agent session may relay. [S: AGENTS.md#issue-and-spec-workflow]
- Sync pulls a pin change: regenerating installed files downloads the pinned standard, an R2 "what `ballast` downloads" path. [S: docs/policies/project/workflow.md#r2-boundaries]
- `resume` after a `postcondition` block on implementation re-enters at `validate-implementation` today, not `implement`. [S: Issue #147 body]

## Issue acceptance criteria

- IAC-1: For a change merged on the pinned default branch (including a `ballast.toml` change), the next run needs no `ballast trust` and no `ballast setup`, and the run output says the baseline was refreshed and from which commit.
- IAC-2: A protected-input change that does not match the default branch or an operator-run setup still blocks and needs `ballast trust`.
- IAC-3: Generated agent settings can never be trusted while they differ from `ballast.toml`.
- IAC-4: Several pending gates can be approved with one command and one typed confirmation that lists each decision.
- IAC-5: The workflow policy lists which `ballast` commands an agent session may run, and the run for an eligible R1 feature needs only approvals and the merge from the operator.
- IAC-6: `ballast discard-runs --help` prints help and changes nothing.
- IAC-7: A new ADR records which `ballast` commands an agent session may run at each autonomy level, including relayed `start --mode autonomous` and `approve`, and supersedes the conflicting parts of ADR-0004 and ADR-0009.
- IAC-8: A relayed approval is recorded and displayed as relayed, never as a TTY-typed approval, and is refused in a mode that does not allow it.

## Known

- The operator decided on 2026-10-13 to deliver all of #147 in one Issue and one PR, and chose agent-relayed approvals scaled by autonomy level. [S: .specify/workflow-state/issues/147.md]
- `discard-runs` ignores its arguments and discards run state. [S: tools/spec_workflow/launcher.py:924]
- `trust` records the baseline without comparing generated settings with `ballast.toml`. [S: tools/spec_workflow/launcher.py:785]
- Approval requires a TTY and typed confirmation. [S: tools/spec_workflow/chat.py:2460]
- ADR-0004 rejected piping approvals into gate prompts because the record would read as human approval. [S: docs/adr/0004-autonomous-provisional-decisions.md#rejected-alternatives]
- A branch-sync HEAD change to a protected input blocks as `protected-input` for operator review and `ballast trust`. [S: docs/adr/0005-launcher-branch-synchronization.md#decision]
- ADR-0015 states that a moved default branch with different configuration bytes is not eligible until reviewed (SEC2-005, closed by digests). [S: docs/adr/0015-setup-recorded-trust-baseline.md#residual-risks-stated-plainly]
- A `--refresh-policy` resume reads `ballast.toml` only from a `trust`-recorded baseline. [S: docs/adr/0016-privileged-action-kinds-and-policy-refresh.md#decision]
- The operator resolved D-02 as option A in HD-0002: the new ADR also amends ADR-0015 and BL-INV-002, and IAC-1 stands as written. [S: specs/147-human-gates-are-decisions/autonomous/record.md#block-resolutions]
- This project authorizes `operator-trust` and `scratch-repository` as pre-merge privileged actions. [S: ballast.toml]

## Inferred

- Relayed approvals can only be relayed by the operator's own agent session outside any confined step; confined steps already cannot run `ballast`, so the boundary is the existing confinement. [I]
- The launcher cannot verify that the operator said yes in chat; a relayed approval is a recorded claim by the operator's session, which is why it must be labeled as relayed. [I]
- D-01 and D-02 settle the conflicts with ADR-0004, ADR-0009 and ADR-0015 only through the new ADR and the constitution amendment; the ADR text stays agent-provisional until the merge. [I]
- The new ADR states the residual risk D-02 accepts: anyone who can merge to the pinned default branch of a reviewed repository can change `[agents.permissions]` or `[autonomous]` without a local review, so branch protection becomes that review; a repointed `[github] repository` still never inherits trust. [I]
- Autonomous start without a TTY prints the branch command instead of prompting. [P: D-06]
- Only a step whose wrapper confirmed its processes stopped closes as interrupted; the dead-wrapper path keeps the unfinished-step refusal. [P: D-07]

## Undecided

None.

## Decisions

### D-01: Relayed approvals versus ADR-0004 and ADR-0009
- **Status**: settled
- **Question**: May the operator's agent session record approvals and start Autonomous runs, against the TTY-only rule of ADR-0004 and ADR-0009?
- **Why it matters**: decides whether `approve` gains a non-TTY relayed path and whether the new ADR supersedes those ADRs.
- **Sources**: [S: Issue #147 body] [S: docs/adr/0004-autonomous-provisional-decisions.md#rejected-alternatives] [S: docs/adr/0009-chat-mode-operator-driven-steps.md#decision] [S: AGENTS.md#work-from-the-right-artifact]
- **Options**:
  - A — Relay per autonomy level, recorded as relayed, through a new ADR. Consequence: IAC-7 and IAC-8 are met; ADR-0004 and ADR-0009 are superseded in part.
  - B — Keep TTY-only approvals. Consequence: IAC-7 and IAC-8 fail.
- **Recommended default**: A, because the Issue requires it.
- **Answer**:
- **Resolution**: A. The operator decided on 2026-10-13, in the Issue body (proposal 7), to supersede the TTY-only parts of ADR-0004 and ADR-0009 through a new ADR, the route AGENTS.md prescribes for an accepted architecture change [S: Issue #147 body] [S: AGENTS.md#work-from-the-right-artifact]. Agent steps keep their prohibition, and BL-INV-006 is preserved because relayed approvals are never shown as TTY-typed.

### D-02: Automatic trust for default-branch configuration the operator never reviewed
- **Status**: settled
- **Question**: Should a `ballast.toml` or constitution merged on the pinned default branch become trusted automatically, though ADR-0015 accepts only the exact configuration pair `ballast trust` reviewed?
- **Why it matters**: IAC-1 requires it, ADR-0015 forbids it (SEC2-001, SEC2-005), and the Issue supersedes only ADR-0004 and ADR-0009; the choice decides whether anyone who can merge to the default branch can widen `[agents.permissions]` or `[autonomous]` on every operator machine without a local review.
- **Sources**: [S: IAC-1] [S: docs/adr/0015-setup-recorded-trust-baseline.md#decision] [S: docs/adr/0015-setup-recorded-trust-baseline.md#residual-risks-stated-plainly] [S: .specify/memory/constitution.md#core-principles] [S: .specify/memory/constitution.md#amendment-history] [S: specs/147-human-gates-are-decisions/autonomous/record.md#block-resolutions]
- **Options**:
  - A — The new ADR also amends ADR-0015 and BL-INV-002: the live default branch of a repository `ballast trust` already reviewed counts as reviewed for any bytes. Consequence: IAC-1 met as written; branch protection becomes the only review of configuration changes; a constitution amendment is needed.
  - B — Keep ADR-0015: auto-refresh only installed files regenerated from an already reviewed configuration; a new configuration still needs one `ballast trust`, which shows the diff. Consequence: IAC-1 not met for `ballast.toml` changes (the #141 case still needs a trust).
  - C — Auto-refresh only `ballast.toml` changes that cannot widen authority (for example `[standard] ref` or `[checks]`), with `[agents.permissions]`, `[autonomous]` and `[github]` changes still needing `ballast trust`. Consequence: IAC-1 met in part; the #140 `extra_allow` case still needs a trust.
- **Recommended default**: A with residual risks stated in the ADR, because it matches the Issue's intent; it needs the operator's decision because it changes a security boundary and an accepted ADR the Issue does not name.
- **Answer**:
- **Resolution**: A. The operator resolved the contradiction block in HD-0002 (2026-10-13T09:13:50Z) as option A, citing Issue #147 comment 6142240052: the new ADR also amends ADR-0015 and BL-INV-002, and IAC-1 stands as written [S: specs/147-human-gates-are-decisions/autonomous/record.md#block-resolutions]. The ADR must state the residual risk and keep the repointed-repository and unobservable-branch refusals of ADR-0015.

### D-03: Batch approval syntax
- **Status**: settled
- **Question**: How are several gates approved at once?
- **Why it matters**: decides the CLI surface tested for IAC-4.
- **Sources**: [S: Issue #147 body] [S: IAC-4]
- **Options**:
  - A — Positional gate list, with `--through GATE` as the shorthand. Consequence: both forms from the Issue.
  - B — Only one of the forms. Consequence: a smaller surface.
- **Recommended default**: A, because the Issue names both.
- **Answer**:
- **Resolution**: A, as proposal 4 states, still at a TTY with one typed confirmation that lists each decision [S: Issue #147 body].

### D-04: Commands an agent session may run
- **Status**: settled
- **Question**: Which `ballast` commands may the operator's agent session run?
- **Why it matters**: defines the policy list for IAC-5 and the ADR for IAC-7.
- **Sources**: [S: Issue #147 body] [S: IAC-5] [S: IAC-7]
- **Options**:
  - A — `start`, `resume`, `continue`, headless `step`, `status`, `publish`, `setup`, `intake`; `trust`, `approve`, `reject` reserved, except relayed `approve` and `start --mode autonomous` per autonomy level. Consequence: as proposals 5 and 7.
  - B — A narrower list. Consequence: IAC-5 fails for an R1 run.
- **Recommended default**: A, because the Issue lists it.
- **Answer**:
- **Resolution**: A, from proposals 5 and 7 of the Issue body [S: Issue #147 body].

### D-05: Setup and sync consistency
- **Status**: settled
- **Question**: After sync pulls a `ballast.toml` change, does the launcher regenerate installed files or block with one combined fix?
- **Why it matters**: IAC-1 requires no `ballast setup` after a default-branch change.
- **Sources**: [S: Issue #147 body] [S: IAC-1] [S: IAC-3]
- **Options**:
  - A — Regenerate during sync from the pinned standard. Consequence: IAC-1 met; the sync path now runs setup.
  - B — Block with one combined fix. Consequence: IAC-1 fails for `ballast.toml` changes.
- **Recommended default**: A, because IAC-1 forbids a separate setup.
- **Answer**:
- **Resolution**: A for changes that can be refreshed automatically (IAC-1); B remains the fallback when regeneration cannot be attributed to the default branch (IAC-2) [S: IAC-1] [S: IAC-2].

### D-06: Issue-named branch offer without a TTY
- **Status**: assumed
- **Question**: How does Autonomous start "offer" an Issue-named branch when the agent session runs it without a TTY?
- **Why it matters**: decides whether start can switch branches without operator input.
- **Sources**: [S: Issue #147 body] [S: docs/adr/0005-launcher-branch-synchronization.md#decision]
- **Options**:
  - A — Prompt at a TTY; without one, refuse and print the exact `git switch -c` command. Consequence: no unasked branch change.
  - B — Create and switch automatically. Consequence: fewer commands, but the launcher changes branches unprompted.
- **Recommended default**: A, because it never moves the checkout without an answer.
- **Answer**:
- **Resolution**: A, assumed. It adds no authority (the agent session can run the printed command itself) and is a UX detail of the refusal, reversible in a later release.

### D-07: Which stopped steps close as interrupted
- **Status**: assumed
- **Question**: Which agent-step stops close as interrupted and resumable instead of `unfinished-step`?
- **Why it matters**: widening it could weaken the dead-wrapper and tamper protection.
- **Sources**: [S: Issue #147 body] [S: docs/adr/0009-chat-mode-operator-driven-steps.md#decision]
- **Options**:
  - A — Only steps whose wrapper confirmed the agent's processes stopped (including a usage-limit exit); a dead wrapper keeps the unfinished-step refusal. Consequence: the #141 case recovers; no tamper path weakens.
  - B — Every stop, including a dead wrapper. Consequence: a killed wrapper no longer forces review.
- **Recommended default**: A, because it keeps the existing refusal where processes are unconfirmed.
- **Answer**:
- **Resolution**: A, assumed. It is the narrower reading of proposal 6, keeps the dead-wrapper refusal of ADR-0009 D-7, and can be widened later.

## Changes

- 2026-10-13: rerun after HD-0001 (operator resumed at discover in Autonomous). No answer to D-02 is visible: the Issue snapshot predates HD-0001 and has no comments, and HD-0001 records only the resume. D-02 stays open and blocks again; added S-16, S-17 and the unavailable sources that explain why.
- 2026-10-13: rerun after HD-0002. D-02 settled as option A from the operator's block resolution HD-0002; added the ADR-0015 and BL-INV-002 amendment to Constraints and Known, the residual-risk inference, and the cited comment as unavailable. Undecided is now empty.

## Question metrics

- **Rounds**: 0
- **Questions asked**: 0
- **Assumptions adopted**: 2
