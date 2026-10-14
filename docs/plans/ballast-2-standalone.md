### Proposed implementation plan — standalone slice

Dependency: #175 / PR #176. The operator explicitly authorized a stacked draft branch while #176 awaits merge, and creation of the public Hugo-Grellier/ballast-v2-smoke target. Merge #176 before this feature; neither merge nor scratch deletion is authorized. This plan does not assert that the runtime already exists.

#### Design

Keep phase logic in the agent instructions. Add only the execution primitives the ordinary Git/CLI tools do not already supply:

1. **Prepare and claim.** Resolve the requested GitHub repository against the checkout's remote identity, read the issue and its existing work/PR relationships, require an actionable leaf with acceptance criteria, and select the configured integration base. Use an exclusive per-issue claim in local state shared by this Git repository's worktrees. Record an attempt ID before creating the isolated checkout; preserve residual state on failure rather than guessing that retry is safe.
2. **Execute one bounded worker.** Extend/reuse the #175 JSON-lines transport to start a fresh Codex session with explicit model, effort, working directory, sandbox and approval policy. Validate the supported pair, authorized account/provider mode, and resolved session receipt before sending any task input. Implementation uses the authorized write boundary; review uses read-only access. Neither operation inherits the caller's conversation. Missing runtime evidence blocks the task. No metered API or provider substitution is implicit.
3. **Observe the attempt.** Record scrubbed local start/configuration/phase/completion events and the authoritative session identity. Bound runtime and output. Distinguish backend completion, failed work, interruption and unknown state. The first slice runs in the foreground and makes no detached-supervisor or general resume guarantee; #178 owns recovery and queue scheduling.
4. **Let the coordinator verify and review.** The driving agent runs project checks with argument arrays, reads the final diff, and launches a separate verified review session against a stable head. Use the existing maximum of three review/fix rounds. Model output and a successful worker exit are not acceptance evidence by themselves. Workers may not create untracked nested agents to bypass routing or concurrency controls.
5. **Publish with existing tooling.** The coordinator uses authenticated Git/GitHub tooling to reuse or create the issue branch and one PR. Verify the intended target before writes, retain a draft for incomplete evidence, and identify required CI by workflow, check, head and relevant base. Human merge remains the endpoint. Keep publishing policy in the instructions unless a concrete missing primitive requires code.

No workflow DSL, generic scheduler, plugin registry, daemon, remote service, new account or dashboard is introduced. The new implementation must operate without Orca; Orca's adapter is #179. CI runs only deterministic tests and never creates a real agent process.

#### Evidence

- Temporary Git repositories and fake hosting/process adapters prove repository/base checks, exclusive claims, partial setup failures, invalid routes, forbidden auth modes, bounded output/time, completion versus failure, review invalidation and publication identity. Do not label fixture evidence as a live GitHub success.
- One uninterrupted agent-started live scenario must deliberately choose both a model and effort different from the launcher's observed settings. It proves the executing session's receipt before its task turn, meaningful sandboxed work, a check that would fail without that work, a fresh independent review receipt, and publication of the linked PR.
- End-to-end publication must use an explicitly authorized scratch target with a fictional bounded issue, as required by AC1. The scope, destination and resulting PR are recorded; mocks or an unrelated development issue cannot substitute for that live scenario. The operator authorized the public Hugo-Grellier/ballast-v2-smoke target, which has been created.
- Record client versions, requested/observed pairs, commands/results, reviewer verdict, and limitations. Never publish account data, raw prompts/transcripts, credentials or local machine destinations.

#### Open integration details to resolve from evidence

- The exact app-server account/permission receipt fields supported by the installed client; reject unknown auth modes rather than infer free access.
- Where the local claim/attempt record lives in Git's common directory, including atomic ownership and linked-worktree behavior. No timestamp alone authorizes reclaim.
- Which existing native delegation operations can be reused without weakening pre-task configuration verification. Begin with the qualified Codex transport, keeping profiles independent of a permanent author/reviewer pairing.
- The public scratch target is authorized and created. Initial workflow publication was blocked by OAuth scope. The operator granted it; the workflow, final-head review and matching CI now pass. See `docs/evidence/standalone.md` for live evidence.


#### Preparatory review and feasibility update

A separate reviewer accepted the minimal two-primitive approach and identified the two live-evidence details above; they are now explicit. The operator resolved both live target and stacked-branch decisions in conversation. Local common-directory claims protect coordinators sharing that Git repository; cross-clone/host exclusivity is not claimed.

On 2026-10-14, a metadata-only local Codex preflight established that the installed client exposes an authorized subscription-mode check and a resolved workspace-write receipt with no networking and no additional writable roots. No model turn was sent, and no account identifiers or plan/quota details are recorded. This resolves protocol feasibility for the installed client, not execution/publication acceptance.

#### In-place layout correction

Following the operator's clarification, the shared transport is `tools/codex.py`,
preparation is `tools/worktree.py`, and execution is `tools/worker.py`. Instructions
and live evidence live in `docs/standalone.md` and `docs/evidence/standalone.md`.
Imports, isolated script bootstrapping, check names and links follow those paths.
The original live scenario remains historical evidence; renamed-module checks
and a fresh metadata-only executing-session preflight validate the relocation.
