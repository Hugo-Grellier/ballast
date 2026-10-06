<!-- ballast-discovery: input evidence -->
# Discovery brief: Qualify one zero-cost provider fallback

This brief is input evidence for [spec.md](spec.md). It is not the feature's
authority: once intent is recorded, [spec.md](spec.md) and [intent.md](intent.md)
govern, and later steps do not read requirements from this file.

**Mode**: autonomous
**Issue**: #23 (snapshot `.specify/workflow-state/issues/23.md`, untrusted requirements data)

## Sources

- S-1: Issue #23 body
- S-2: Issue #23 intake scope comment (in the snapshot `.specify/workflow-state/issues/23.md`)
- S-3: docs/plans/2026-10-02-product-roadmap.md#priority-7--cost-aware-execution-in-slices (lines 121–134) and the 1.0 release gate item 6 (line 145)
- S-4: specs/TECHNICAL-SPEC.md#91-v10-target
- S-5: specs/TECHNICAL-SPEC.md#64-subscription-aware-routing and #65-paid-api-guard
- S-6: specs/PRODUCT-SPEC.md#54-avoid-hidden-api-costs and #53-cli-native-execution-preference
- S-7: docs/policies/model-routing.md (principle 8, the capability-profile note at line 29, the ledger paragraph at line 124)
- S-8: docs/policies/project/workflow.md#r2-boundaries
- S-9: .specify/memory/constitution.md (principles 3, 5, 6, 8, 9)
- S-10: AGENTS.md#invariants
- S-11: tools/spec_workflow/agent.py (headless permission model, lines 89–157; step attempts, lines 896–980)
- S-12: tools/spec_workflow/autonomy.py (confinement keeps the host network, line 1994; Codex sandbox nesting probe and DEC-0004 fallback, lines 2225–2265; step limits, lines 186–191)
- S-13: tools/spec_workflow/ledger-schema.md and tools/spec_workflow/ledger.py (`route` fields and enumerations, lines 185–290)
- S-14: specs/23-free-fallback/autonomous/record.md (PD-0001 scope decision, R2 boundaries)
- unavailable: https://github.com/Hugo-Grellier/LoreForge/issues/94 — external Issue, not in the snapshot; only its roadmap summary (S-3) was read
- unavailable: docs/adr/ — no ADR covers provider fallback or execution backends; ADR-0004 (provisional decisions) applies only to the run's process

## Need

- **User**: the Ballast operator running feature work through `ballast run` on their own Linux host with Claude Code and Codex subscriptions [S: Issue #23 body] [S: specs/TECHNICAL-SPEC.md#91-v10-target]
- **Job to be done**: keep an eligible workflow step moving when the Claude/Codex route is unavailable or out of quota, without paying and without widening what the agent may see or do [S: Issue #23 body]
- **Current pain**: there is no automatic provider fallback; a quota or availability failure stops the step and the run [S: docs/plans/2026-10-02-product-roadmap.md:24]
- **Intended outcome**: one qualified, opt-in, zero-cost backend completes an eligible idempotent step within free-only, privacy and permission policy, with every attempt recorded in the existing ledger [S: IAC-1] [S: IAC-3]

## Examples

- An Autonomous run's headless step fails because Claude reports its usage limit; the operator has opted into the local fallback; the wrapper confirms the step left nothing behind, selects Codex CLI in `--oss` mode against the local Ollama model, the step completes, and the ledger shows the failed primary attempt, the selection reason and the fallback outcome [S: IAC-1] [S: IAC-3] [P: D-04]
- The configured Ollama model is a cloud-hosted tag, or the endpoint is not on loopback: the fallback is refused before any prompt or repository content is sent, and the step blocks with the reason [S: IAC-2] [S: .specify/workflow-state/issues/23.md#intake-scope-comment]
- The primary attempt failed on quota after it had already edited files: the fallback is refused rather than replaying a partial mutation [S: docs/plans/2026-10-02-product-roadmap.md:132] [P: D-04]
- On a host where Codex's own sandbox cannot start inside Ballast's confinement, the fallback is refused as a capability mismatch instead of loosening the sandbox [S: tools/spec_workflow/autonomy.py:2225] [S: .specify/memory/constitution.md]

## Scope

- Evaluate one candidate backend and record the evaluation and pilot evidence that justify it [S: IAC-4] [S: .specify/workflow-state/issues/23.md#intake-scope-comment]
- An explicit, default-off operator opt-in, with a documented configuration and exit path [S: IAC-4] [S: docs/plans/2026-10-02-product-roadmap.md:129] [P: D-05]
- Normalize recoverable primary failures (quota exhausted, provider or CLI unavailable) into a fixed cause set that can trigger the fallback [S: Issue #23 body]
- Eligibility checks before selection: free-only, privacy, permission and capability; refusal when any is unknown [S: IAC-2] [S: docs/plans/2026-10-02-product-roadmap.md:129]
- Bounded fallback attempts that cannot duplicate side effects [S: IAC-3] [P: D-06]
- Route and fallback evidence in the existing run ledger, extending its fixed enumerations additively [S: IAC-3] [S: tools/spec_workflow/ledger-schema.md]

## Non-goals

- Broad multi-provider routing or a general adapter layer [S: Issue #23 body]
- Paid overflow or any metered API [S: Issue #23 body] [S: specs/TECHNICAL-SPEC.md#65-paid-api-guard]
- A hard-coded permanent list of currently free models [S: Issue #23 body] [S: docs/plans/2026-10-02-product-roadmap.md:130]
- Replaying a partially executed mutation [S: Issue #23 body]
- Provider account sign-up [S: .specify/workflow-state/issues/23.md#intake-scope-comment]
- A direct-API execution harness, which needs its own tool, context, secret and privacy design [S: docs/plans/2026-10-02-product-roadmap.md:132]
- Fallback inside a Chat run's interactive steps [P: D-08]

## Constraints

- The existing headless no-network boundary is not relaxed [S: docs/plans/2026-10-02-product-roadmap.md:132]
- No permission or sandbox bypass flag may reach the agent CLI (`dangerously`, `bypassPermissions`, `danger-full-access`, `network_access`) [S: tools/spec_workflow/agent.py:89]
- Codex runs with `workspace-write`, tool network off and no extra writable roots [S: tools/spec_workflow/agent.py:146]
- Workflow tools stay standard-library-only under `python3 -I -S` [S: .specify/memory/constitution.md] [S: AGENTS.md#invariants]
- A headless agent never gains more authority than its caller; the opt-in is a trusted input outside agent reach [S: .specify/memory/constitution.md] [S: AGENTS.md#invariants]
- No quota or account details are stored in the repository or the ledger [S: docs/policies/model-routing.md:83] [S: tools/spec_workflow/ledger-schema.md]
- Every fallback attempt counts against the run's agent-step limit [S: tools/spec_workflow/autonomy.py:186] [P: D-06]
- R2: headless-agent permission model, privacy boundary and what `ballast` executes [S: docs/policies/project/workflow.md#r2-boundaries] [S: specs/23-free-fallback/autonomous/record.md]

## Permissions and data authority

- The fallback runs under the same bwrap confinement, environment scrubbing and protected-input checks as the primary step [S: tools/spec_workflow/autonomy.py:1908] [S: docs/plans/2026-10-02-product-roadmap.md:128]
- Repository content may go only to a model served on the loopback interface by a locally present, non-cloud model [S: .specify/workflow-state/issues/23.md#intake-scope-comment] [S: IAC-2] [P: D-07]
- Only the operator opts in; an agent cannot enable, configure or widen the fallback [S: .specify/memory/constitution.md] [P: D-05]
- The ledger stays the single record of attempts; the Draft PR reads from it and never becomes a second source [S: docs/policies/model-routing.md:124] [S: AGENTS.md#invariants]

## Success evidence

- A test that simulates a quota or availability failure and shows the fallback selected and the eligible step completed [S: IAC-1]
- Refusal tests for unknown free status, incompatible capability, privacy exclusion and permission mismatch that prove nothing was sent to the backend [S: IAC-2] [S: .specify/memory/constitution.md]
- Ledger events for each attempt, its selection reason, outcome and usage when available; a test that a retried step leaves no duplicate side effect [S: IAC-3]
- An evaluation record naming the candidate, the alternatives considered and a pilot run on the operator's host, plus documentation of configuration and how to turn it off [S: IAC-4]
- The full local gate on Linux with a systemd user session, because confinement and Codex-sandbox behavior is skipped in CI [S: AGENTS.md#commands]

## Edge, failure and permission cases

- Codex's sandbox does not nest inside Ballast's bwrap on the host (the existing DEC-0004 condition): refuse as capability mismatch [S: tools/spec_workflow/autonomy.py:2225] [S: .specify/memory/constitution.md]
- Ollama not running, model not pulled, or endpoint not loopback: refuse before sending content [S: IAC-2] [P: D-07]
- An Ollama model tag that runs in the provider's cloud: privacy exclusion and unknown free status [S: .specify/workflow-state/issues/23.md#intake-scope-comment] [P: D-07]
- The primary attempt changed files or drafts before failing: refuse, never replay [S: docs/plans/2026-10-02-product-roadmap.md:132] [P: D-04]
- The fallback itself fails: no further fallback; the step fails with both attempts recorded [P: D-06]
- A non-recoverable primary failure (blocked status, tamper, limit exhausted, refused draft): never triggers the fallback [S: tools/spec_workflow/agent.py:95] [I]
- A review step completed by the fallback: the reviewer provider and model are recorded as they were, and the PR does not claim cross-provider review [S: docs/policies/model-routing.md] [I]
- The step limit is reached by the fallback attempt: the run stops with the existing limit refusal [S: tools/spec_workflow/autonomy.py:186] [I]

## Issue acceptance criteria

- IAC-1: A simulated quota or availability failure selects one qualified free backend and completes an eligible idempotent step.
- IAC-2: Unknown free status, incompatible capability, privacy exclusion and permission mismatch refuse the fallback before repository content is sent.
- IAC-3: Attempts, selection reason, outcome and usage when available appear in the existing run ledger; retries cannot duplicate side effects.
- IAC-4: The candidate backend is chosen from an evaluation and pilot evidence, with a documented configuration and exit path.

## Known

- The intake names the leading candidate: the host's local Ollama with a local model, driven by the Codex CLI's `--oss --local-provider ollama` mode; local, no account, no data leaves the machine [S: .specify/workflow-state/issues/23.md#intake-scope-comment]
- The concrete backend must be chosen through evaluation and pilot, not frozen in the roadmap [S: docs/plans/2026-10-02-product-roadmap.md:128]
- Fallback applies at an idempotent step boundary and never replays a partial mutation blindly [S: docs/plans/2026-10-02-product-roadmap.md:132]
- Refusal is required when eligibility, price, privacy terms or execution capability are unknown; paid overflow stays disabled [S: docs/plans/2026-10-02-product-roadmap.md:129] [S: specs/TECHNICAL-SPEC.md#91-v10-target]
- When no compatible runtime is available the system blocks rather than falling back to a billed API [S: specs/TECHNICAL-SPEC.md#65-paid-api-guard]
- Confined agent steps keep the host network, so a loopback model server is reachable without relaxing the no-network tool boundary [S: tools/spec_workflow/autonomy.py:1994] [S: tools/spec_workflow/agent.py:146]
- Codex's own sandbox may fail to start inside Ballast's confinement; Autonomous runs already detect this per run and fall back to Claude for both roles [S: tools/spec_workflow/autonomy.py:2231] [S: specs/23-free-fallback/autonomous/record.md]
- The ledger `route` kind already carries `provider`, `model`, `attempt`, `cause_id`, `outcome` and `route_source` with fixed enumerations, and new kinds or values are added without bumping `schema_version` [S: tools/spec_workflow/ledger.py:185] [S: tools/spec_workflow/ledger-schema.md]
- The wrapper already retries refused drafts up to two times and counts every attempt as an agent step [S: tools/spec_workflow/agent.py:896] [S: tools/spec_workflow/autonomy.py:191]

## Inferred

- The candidate's viability on the qualified host depends on whether Codex's sandbox nests inside bwrap there; the plan's evaluation must test it first, and an evaluation that rejects the candidate is a decision for `decisions.md`, not a silent swap [I]
- Recoverable failure detection reads the agent CLI's exit status and output for a fixed set of quota and availability signatures; anything unrecognized is not recoverable [I]
- The ledger needs additive enumeration values (for example a `fallback` route source and failure causes) rather than a new store [I]
- Fallback eligibility requires the primary attempt to have left the worktree, drafts and protected state unchanged [P: D-04]
- The opt-in is an operator-side setting, off by default, recorded in the run record where agents cannot write [P: D-05]
- At most one fallback attempt per step, after one failed primary attempt [P: D-06]
- Capability and privacy are checked by runtime probes plus the operator-named model before any prompt is sent [P: D-07]
- The fallback covers headless steps of human-gated and Autonomous runs only [P: D-08]

## Undecided

None.

## Decisions

### D-01: Which backend is the candidate
- **Status**: settled
- **Question**: Which zero-cost backend does this feature evaluate and qualify?
- **Why it matters**: It fixes the execution path, the privacy argument and what the evaluation must prove.
- **Sources**: [S: .specify/workflow-state/issues/23.md#intake-scope-comment] [S: docs/plans/2026-10-02-product-roadmap.md:128] [S: specs/PRODUCT-SPEC.md#53-cli-native-execution-preference]
- **Options**:
  - A — Codex CLI `--oss --local-provider ollama` against the host's local Ollama model. Consequence: reuses the existing Codex wrapper path and permission model; local and accountless.
  - B — A hosted free tier or another agent CLI. Consequence: needs account, privacy-terms and permission-model evaluation that the Issue does not scope.
- **Recommended default**: A, because the intake names it and it stays CLI-native.
- **Answer**:
- **Resolution**: A, as the leading candidate named in the intake scope comment [S: .specify/workflow-state/issues/23.md#intake-scope-comment]; the plan's evaluation and pilot must still justify it per IAC-4 and the roadmap [S: docs/plans/2026-10-02-product-roadmap.md:128].

### D-02: What happens when the candidate cannot run under Ballast's confinement
- **Status**: settled
- **Question**: If Codex's sandbox cannot start inside bwrap, may the fallback relax either sandbox?
- **Why it matters**: It decides whether the fallback can ever widen agent authority.
- **Sources**: [S: .specify/memory/constitution.md] [S: tools/spec_workflow/agent.py:89] [S: docs/plans/2026-10-02-product-roadmap.md:132]
- **Options**:
  - A — Refuse the fallback as an incompatible capability. Consequence: the fallback is unavailable on such a host; authority never widens.
  - B — Run Codex without its sandbox or outside bwrap. Consequence: an agent gains more authority than its caller.
- **Recommended default**: A, because B is forbidden.
- **Answer**:
- **Resolution**: A. BL-INV-003 forbids more authority than the caller, the wrapper refuses sandbox-bypass flags, and the roadmap does not relax the boundary [S: .specify/memory/constitution.md] [S: tools/spec_workflow/agent.py:89] [S: docs/plans/2026-10-02-product-roadmap.md:132].

### D-03: What counts as free and private
- **Status**: settled
- **Question**: Which endpoints and models pass the free-only and privacy checks?
- **Why it matters**: It is the refusal boundary IAC-2 tests.
- **Sources**: [S: .specify/workflow-state/issues/23.md#intake-scope-comment] [S: IAC-2] [S: docs/plans/2026-10-02-product-roadmap.md:129]
- **Options**:
  - A — Only a loopback endpoint serving a locally present, non-cloud model; anything else or unknown is refused. Consequence: no repository content leaves the machine.
  - B — Any endpoint the operator configures. Consequence: free status and privacy cannot be established.
- **Recommended default**: A, because the intake's privacy argument is that no data leaves the machine.
- **Answer**:
- **Resolution**: A, from the intake ("local, no account, no data leaves the machine") and the rule that unknown free status or privacy refuses [S: .specify/workflow-state/issues/23.md#intake-scope-comment] [S: IAC-2] [S: docs/plans/2026-10-02-product-roadmap.md:129].

### D-04: Which steps are eligible
- **Status**: assumed
- **Question**: When is a failed step eligible for a fallback attempt?
- **Why it matters**: It decides whether a fallback can duplicate or build on a partial mutation.
- **Sources**: [S: docs/plans/2026-10-02-product-roadmap.md:132] [S: Issue #23 body] [S: tools/spec_workflow/agent.py:221]
- **Options**:
  - A — Only when the primary attempt left the worktree, drafts and protected state unchanged, checked by the wrapper before the fallback starts. Consequence: some quota failures late in a step block instead of falling back.
  - B — A fixed allowlist of step types considered idempotent. Consequence: a step that did mutate before failing could be replayed.
- **Recommended default**: A, because it is checked from evidence rather than assumed per step type.
- **Answer**:
- **Resolution**: Assumed A. It is the narrower rule, needs no replay, and widening eligibility later is additive; it does not change product scope beyond the Issue's "eligible idempotent step".

### D-05: Where the operator opts in
- **Status**: assumed
- **Question**: Where is the fallback enabled and configured?
- **Why it matters**: It decides who can turn the fallback on and what the documented exit path is.
- **Sources**: [S: .specify/memory/constitution.md] [S: AGENTS.md#invariants] [S: tools/spec_workflow/autonomy.py:428]
- **Options**:
  - A — An operator-side setting, off by default, read by the trusted launcher and recorded in the run record. Consequence: per-host opt-in; nothing committed; agents cannot reach it.
  - B — A `ballast.toml` section. Consequence: project-wide and visible in PRs, but a host-specific setting lands in a committed file.
- **Recommended default**: A, because the fallback depends on the operator's host and both options keep the setting outside agent reach.
- **Answer**:
- **Resolution**: Assumed A. Off by default, stored where the run record already stores the integration, so the trust boundary is unchanged; moving to or adding a `ballast.toml` section later is additive.

### D-06: How many attempts
- **Status**: assumed
- **Question**: How many primary and fallback attempts may one step make?
- **Why it matters**: It bounds spend of the step limit and the chance of duplicate effects.
- **Sources**: [S: tools/spec_workflow/autonomy.py:186] [S: docs/plans/2026-10-02-product-roadmap.md:129] [S: IAC-3]
- **Options**:
  - A — One fallback attempt after one recoverable primary failure; no further retry; each attempt counts as an agent step. Consequence: a flaky fallback fails the step.
  - B — Several fallback retries with backoff. Consequence: more step budget used and more retries to prove side-effect free.
- **Recommended default**: A, because it is the smallest bound that meets IAC-1.
- **Answer**:
- **Resolution**: Assumed A. It is the strictest bound, keeps the existing step limit authoritative, and raising it later is a configuration change.

### D-07: How capability and privacy are established
- **Status**: assumed
- **Question**: What must hold before the fallback receives a prompt?
- **Why it matters**: It is the check IAC-2 requires to happen before any repository content is sent.
- **Sources**: [S: IAC-2] [S: tools/spec_workflow/autonomy.py:2231] [S: docs/plans/2026-10-02-product-roadmap.md:130]
- **Options**:
  - A — Runtime probes: the operator-named model is installed locally and is not a cloud model, the endpoint is loopback, the Codex CLI supports the local-provider mode and its sandbox nests; any failed or unknown probe refuses. Consequence: no model list is hard-coded.
  - B — A shipped list of known-good free models. Consequence: freezes currently-free model names, which the Issue excludes.
- **Recommended default**: A, because B is out of scope.
- **Answer**:
- **Resolution**: Assumed A. Probes only refuse, so a wrong probe can block but never send content; the probe set can be extended later.

### D-08: Which run modes use the fallback
- **Status**: assumed
- **Question**: Does the fallback apply to headless steps only, or also to Chat interactive steps?
- **Why it matters**: Interactive steps run behind a pty with the operator present, which changes failure detection and who chooses.
- **Sources**: [S: specs/TECHNICAL-SPEC.md#91-v10-target] [S: tools/spec_workflow/agent.py:641]
- **Options**:
  - A — Headless steps of human-gated and Autonomous runs only. Consequence: a Chat operator switches integration themselves.
  - B — Also Chat interactive steps. Consequence: a second detection path through the pty session.
- **Recommended default**: A, because the operator is already present in Chat.
- **Answer**:
- **Resolution**: Assumed A. It narrows the feature, the operator keeps manual control in Chat, and adding Chat later is additive.

## Question metrics

- **Rounds**: 0
- **Questions asked**: 0
- **Assumptions adopted**: 5
