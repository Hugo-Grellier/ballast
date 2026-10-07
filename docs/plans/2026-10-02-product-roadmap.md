# Ballast product roadmap (draft)

**Status:** 1.0 scope agreed with the operator on 2026-10-03; delivery priorities remain a draft. This is a roadmap, not an approved feature spec or permission to change the launcher trust boundary.

**Tracking:** [Ballast 1.0 Epic](https://github.com/Hugo-Grellier/ballast/issues/11) and [v1.0 milestone](https://github.com/Hugo-Grellier/ballast/milestone/1). The Epic's leaf issues own implementation outcomes; this document records the product sequence and release boundary.

## Product promise

For a request in an adopted repository, Ballast should help the operator establish the real user need, turn it into a sound feature spec, and reach a reviewable Draft PR. Creating another worktree or installing an update should not require repeating a fragile setup ritual. The operator should choose how closely to supervise the work, resume safely after a pause, and see a short, comprehensible acceptance package.

LoreForge is the proving ground; Ballast remains project and stack independent. Feature artifacts carry an explicit human-approved or agent-provisional status. Project policies, Git, and GitHub retain their existing roles; summaries, videos, and dashboards are derived evidence.

## Current state

| Capability | Evidence in this repository | Assessment |
| --- | --- | --- |
| Versioned adoption | `tools/ballast`, `tools/setup`, `ballast.toml`; ignored generated installation | Working foundation. There is no first-run `init`: the operator must create the pin and ignore rules, copy or adapt project-owned files, run setup, and review/trust the result. |
| Worktree and update experience | `setup` copies an exact-fingerprint install from the primary checkout when available | Each worktree still needs an explicit setup call; a mismatch falls back to full installation, and setup removes the previous install before the replacement is complete. |
| Understanding the request | Issue intake, scope gate, `speckit.specify`, and `speckit.clarify` | The workflow can refine a spec, but it lacks one discovery brief that gathers evidence, separates assumptions from decisions, and budgets questions to the user. |
| Feature workflow | `templates/spec-kit/workflows/feature/workflow.yml`, artifact validators, issue intake | Covers specification through final acceptance with human gates and deterministic postconditions. |
| Agent boundary | Trusted `launcher.py`, bounded `agent.py`, protected inputs and tamper refusal | Strong foundation, currently Linux/systemd dependent for headless steps. |
| Execution evidence | Local run archive and append-only ledger | Captures run, gate, route, review and verification evidence; the operator still has to assemble much of it manually. |
| Branch and PR lifecycle | No branch synchronization or Draft PR management in `tools/spec_workflow/` | A paused run can resume on a stale branch. Issue-linked work is not automatically visible in a PR. |
| Provider execution | Claude and Codex wrappers; model routing policy | Policy selects a capability profile, but there is no automatic multi-provider fallback, quota/budget enforcement, or general adapter layer. |
| Human review | Text gates, status-report extension, PR template | Canonical artifacts exist, but API/UI impact and acceptance evidence are not yet projected into a concise review surface. |
| Operator control | Fixed workflow gates; manual interactive work is documented separately | There is no per-run choice between conversational, guided, and more autonomous execution. |
| Demonstration | No feature demo capture contract | UI changes can be tested by a project, but Ballast does not collect a shareable walkthrough. |

The technical and product specs describe a much broader future system. They should not be treated as evidence that staging automation, full review orchestration, PR lifecycle management, or provider fallback already ship.

## Priority 0 — prove one complete pilot

Use one real LoreForge feature from scoped issue to reviewed Draft PR. Record every manual handoff and failure. Verify the archived-run ledger report after the fix in [Ballast #9](https://github.com/Hugo-Grellier/ballast/issues/9), and make the operator path explain the next command and blocking reason. Confirm LoreForge's Ballast adoption before using it as the pilot ([LoreForge PR #124](https://github.com/Hugo-Grellier/LoreForge/pull/124)).

**Exit evidence:** a repeatable run can be installed, trusted, paused, resumed, and reviewed; its ledger report works on the archived run; manual steps and elapsed time are recorded. This supplies a baseline for later features.

## Priority 1 — one-command adoption, updates, and worktrees

**`ballast init` is the public entry point for a repository that does not yet use Ballast.** It detects whether the repository is empty or established, inspects only relevant files, proposes a small project profile, applies safe changes in one invocation, and finishes with a readiness report and the next command. `ballast setup` remains the idempotent installer behind adoption and later worktree preparation. A supported one-command distribution path for the Ballast CLI must replace the current manual copy of `tools/ballast` into `~/.local/bin/`.

1. **Adapt to the repository.** In an empty directory or repository, take a short product description and either a chosen stack or a stack-neutral starting point; initialize Git if needed. In an established repository, inspect manifests, package managers, test/lint/build commands, CI, deployment boundaries, architecture docs, existing `AGENTS.md`/`CLAUDE.md`, Git conventions, and project policies. Detect capabilities such as API, browser UI, database, and migrations only from evidence; show any uncertain inference. Do not execute discovered project commands during inspection.
2. **Generate a usable project profile.** Create `ballast.toml`, the ignore block, project-owned constitution and policy addenda, and a concise agent-instruction entry point. Propose relevant PR/CI templates and verification commands; do not install every stack integration by default. Preserve existing tracked files and offer a reviewable patch for conflicts. Keep project facts in committed project-owned files and rebuildable standard files ignored, following the current ownership invariant.
3. **Verify adoption immediately.** Check that the generated instructions resolve, ignored paths are correct, pinned sources are available, the trust boundary is intact, the chosen check commands exist, and the first workflow can reach a safe preflight. `ballast doctor` reports missing tools, credentials, unsupported platform features, and GitHub/CI configuration with exact remedies. Consolidate review of the generated protected inputs and the operator's initial trust action into the `init` experience while preserving the rule that setup records a baseline only under ADR-0015's conditions (exactly what it installed, configuration a human reviewed, no agent trace) and says so. A first-time user should not have to discover the required order from README errors.
4. **Zero-repeat worktree setup.** On the first `ballast` command in a new worktree, detect the project's pin and materialize the exact matching installation from a verified local cache, using only the trusted operator-side bootstrap. No separate `ballast setup` command or repeat network fetch should be needed when the pin is cached. Keep run state and mutable project data local to the worktree; never copy them from the primary checkout. Handle worktrees on different pins independently.
5. **Reliable installation.** Build the replacement in a temporary location, validate its contents and ignore rules, then switch it into place atomically where possible. Serialize concurrent setup/update attempts and preserve the previous usable installation if fetching, patching, or validation fails. Verify copied/cached content, not just a stamp file.
6. **Explain and prepare updates.** Provide a read-only status/doctor view with pinned, cached, and installed versions; incompatibilities; stale worktrees; and the exact recovery action. An update preview should show the changed version, generated-file impact, active-run compatibility, and required checks before the committed `ballast.toml` pin changes. Support retry and rollback to the previous pin without losing paused run evidence.
7. **Reduce repeat trust work carefully.** The current trust model requires operator review when executable inputs change. First make unchanged worktrees fast to verify. Setup and a worktree's first command record their own baseline under ADR-0015's conditions (#55); investigate inheritance of another checkout's baseline only when the full protected-input digest and pin match an independently trusted source; any mismatch still requires explicit `ballast trust`. Changing this boundary needs an approved R2 design.

**Exit evidence:** `ballast init` brings both a blank repository and an established repository with existing instructions/CI to a usable first workflow without hand-editing generated paths. Re-running it is idempotent and preserves existing project files. Creating ten worktrees at the same pin requires no repeated network setup or manual setup command; a worktree on another pin gets its own correct install. Interrupted installation leaves the prior version runnable, and no active run or constitution is lost. The operator can see why trust or an update is required.

## Priority 2 — understand the need before writing the spec

Add a **discovery brief** before `speckit.specify`, implemented as a reusable skill/agent workflow with deterministic checks around its output. It should read only the relevant issue, comments, existing product/architecture decisions, comparable behavior, and project policy, then produce:

- the user, job to be done, current pain, intended outcome, and concrete examples;
- scope, non-goals, constraints, permissions/data authority, and success evidence;
- what is known from sources, what the agent inferred, and what remains undecided;
- the few decisions that would materially change implementation or acceptance.

Use a **question budget**: first resolve what the repository and issue already answer, then group the remaining high-impact choices into one short interaction with proposed options and consequences. The agent may adopt low-risk, reversible assumptions under the selected autonomy mode, but records them visibly. It must not turn an inference into a claimed user approval. In Autonomous, it carries provisional choices into the Draft PR for the merge review; if a missing decision prevents a safe, coherent implementation, it reports a precise block rather than repeatedly asking the user.

The brief is input evidence, not a second product authority. `spec.md` and `intent.md` remain the feature artifacts, with links back to the source of each major requirement. Add checks that every acceptance criterion maps to an observed need or an explicit assumption, and that the spec covers the relevant failure, permission, and edge cases. Measure both question count and late requirement changes in the pilot.

**Exit evidence:** a short request plus existing repository context yields a reviewable spec with at most one bundled clarification round for the normal case; unresolved assumptions and their consequences are visible. A reviewer can trace the main requirements to user statements, existing policy, or marked inference.

## Priority 3 — make long-running feature work safe and visible

1. **Shared feature identity.** Resolve issue, local branch, remote branch, authoritative base, and existing PR once in trusted operator code. Reject ambiguous ownership. Use one identity for synchronization, PR lifecycle, and evidence.
2. **Early Draft PR** ([LoreForge #111](https://github.com/Hugo-Grellier/LoreForge/issues/111)). On first implementation commit with a remote diff, create or reuse one Draft PR. Keep a pending state before a diff exists. Reuse manually opened PRs and update the same PR across resumes or agent switches. Make auth/network failure retryable and visible. Ready-for-review follows the selected mode's review policy; merge remains a human decision.
3. **Upstream synchronization before each invocation** (the proposed stale-branch feature in the current discussion). After launcher trust verification, fetch and compare the base graph on every `run start` and `run resume`. Rebase a clean branch when required, abort conflicts, and refuse unknown fetch state. Update a published branch using a lease. Record old/current base and resulting HEAD. Recheck protected inputs and invalidate affected plan/review evidence when upstream overlaps relevant files.
4. **Branch-level exclusion.** Hold one deterministic lock from synchronization through the workflow invocation, so two runs cannot race on the same feature branch.

The synchronization and PR hooks belong outside the sandboxed agent. A dirty in-progress checkout may block an automatic rebase; the recovery path must say how to checkpoint or finish local changes without discarding them. If a rebase changes protected workflow inputs, the existing operator review and `ballast trust` rule still applies. This phase changes what the trusted launcher can mutate or execute, so it needs R2 review and explicit human approval before implementation.

**Exit evidence:** resume after `main` advances either runs on the new base or stops before an agent with an actionable `BLOCKED_UPSTREAM_SYNC` report. One issue-linked feature has exactly one reusable Draft PR. Conflict, dirty tree, fetch failure, repeated resume, published branch, and concurrent invocation are covered by deterministic tests.

## Priority 4 — let the operator choose the level of supervision

Offer simple, per-run autonomy presets over one workflow. **Chat and Autonomous are required for 1.0**; Guided and Supervised are later refinements. Each mode must state who can make decisions and when those decisions become accepted:

| Mode | Operator experience | Automatic progress |
| --- | --- | --- |
| **Chat** | Conversation similar to a normal coding-agent session. The operator chooses the next step and can inspect or edit between steps. | Ballast still checks trust, records evidence, and enforces artifact postconditions. |
| **Guided** | Ballast proposes the next action and pauses after each major phase for operator review. | A selected phase can run and retry mechanical checks within declared limits. |
| **Supervised** | Ballast continues across phases and asks when a product decision or required approval is reached. | Planning, implementation, checks, review, and fix loops run within a time/retry/cost budget. |
| **Autonomous** | From a scoped issue, Ballast prepares and reviews the complete Draft PR without asking for human approval along the way. The human reviews once at merge. | The agent makes and records provisional intent, plan, and implementation decisions; checks, independent reviews, and fix loops continue within declared limits. |

The mode is an **operator-side run setting**, recorded with the run and every change to it. Effective autonomy is capped by the project's risk and approval policy. Increasing autonomy during a run requires an explicit trusted operator action; an agent cannot promote its own authority. Modes determine who makes intermediate decisions and when to pause; they do not weaken tests, security checks, postconditions, or the final human merge gate. A setting should also bound wall time, attempts, spend, and allowed external actions. Chat mode needs an interactive entry point that still performs the same trusted preflight before an agent works on the branch.

**Target behavior for Autonomous:** internal intent, plan, task, review, correction, and final-evidence gates proceed without human approval. An agent's decisions are explicitly marked *provisional* in the run and PR; they must never be represented as human-approved artifacts. At merge, the human sees the complete decision history and either accepts the package or requests changes. Technical failures, unresolved contradictions, conflicts, exhausted limits, or unavailable permissions can still block the run. The mode does not deploy, release, merge, or perform destructive external actions before that human decision. A feature that needs pre-merge privileged action is ineligible for Autonomous until a project policy explicitly authorizes that action.

**Governance change required before implementation:** today's Ballast instructions require human approval of intent, plan, material changes, R2 work, and final acceptance. Autonomous therefore cannot be enabled merely by adding a CLI flag. First revise the workflow policy, artifact states, and any affected constitution/architecture rules so provisional agent decisions can carry work to a Draft PR and the merge review can be the single human approval point for eligible runs. Keep the current approvals for Chat and any later Guided/Supervised modes unless their own policies are deliberately changed. The 1.0 pilot must exercise both Chat and Autonomous on bounded R1 work after that governance change.

**Exit evidence:** an eligible R1 feature can run from scoped issue to reviewed Draft PR in Autonomous with no approval prompt; the only human approval is at merge. The PR exposes every provisional decision and the same verification evidence as a supervised run. Changing the mode mid-run cannot hide a decision, bypass a check, or erase an earlier refusal.

## Priority 5 — make review moments useful

Generate one **review packet** from canonical artifacts at each human review point (the merge review in Autonomous) and attach or link it from the Draft PR. It should show:

- intent with its human-approved or agent-provisional status, and decisions needed now;
- feature/base/head SHAs, synchronization status, and whether evidence was invalidated;
- changed behavior and risk area;
- each acceptance criterion with its verification link or an explicit missing-evidence state;
- checks, review findings, unresolved decisions, and next operator action;
- optional API, UI, and demo links when the project supplies them.

The packet must retain links to `spec.md`, `plan.md`, `tasks.md`, reviews, and the diff. It must never silently promote a generated summary into product authority. Start with Markdown in the PR/run archive, using the current ledger and status report; measure whether a separate web control plane is needed after real pilots.

**API projection:** let a project provide its OpenAPI generation/check command and output path. For LoreForge, compare generated OpenAPI with the PR base and publish a readable contract change summary; `oasdiff` is a candidate project-side CI tool. A breaking classification should be surfaced for human review, not interpreted as automatic product approval. Interactive API exploration and lint rules can follow when the pilot shows a need.

**UI projection:** begin with the existing Playwright journeys and screenshots in LoreForge. Name the states that map to acceptance criteria and link their CI artifacts. Add visual diff tooling or Storybook only for states that become hard to review or reproduce. A prototype before implementation is useful when visual intent is materially uncertain; it should be accepted as an explicit feature artifact, not generated for every feature.

**Exit evidence:** at the merge review, an operator can answer what changed, see behavior, find failed/missing evidence and provisional decisions, and decide whether to accept without first reading the whole code diff.

## Priority 6 — show implemented functionality with video

Provide a **project-supplied demo contract** for UI features: a deterministic script or Playwright test that starts from seeded, nonsensitive data and walks through the accepted user journey. For 1.0, an operator can request capture for a specific feature/PR; Ballast records a short video and links it from the existing Draft PR and review packet. Capture the commit SHA, test/scenario name, environment, and outcome beside the video. Keep the media in a CI artifact or other access-controlled location with retention, rather than committing binaries to the feature branch. Routine UI PRs do not trigger recording automatically.

For LoreForge, the first slice can turn on Playwright video for one successful acceptance journey, with a fixed viewport and fixtures. A trace remains the debugging artifact; the short video serves human functional review. If the workflow has no browser UI, use a project-specific demo script or a concise CLI recording. A video demonstrates a path; automated assertions and other acceptance evidence still decide whether behavior passed.

**Exit evidence:** after an on-demand capture request, a reviewer can open a 30–90 second walkthrough from the PR, identify the exact commit and scenario shown, and reproduce the journey locally. Failed capture reports missing evidence without manufacturing a success claim.

## Priority 7 — cost-aware execution, in slices

[LoreForge #94](https://github.com/Hugo-Grellier/LoreForge/issues/94) spans several independently valuable outcomes and should be decomposed under Ballast's scope gate before implementation:

1. **Observe first:** record actual selected harness/model, recoverable failure reason, usage when available, and elapsed time using the existing ledger. Establish how often quota failures block work.
2. **One compatible fallback, required for 1.0:** retain Claude/Codex as existing harnesses, add one opt-in zero-cost alternative end to end, and prove that capability, repository privacy policy, and agent permission bounds survive a switch. Choose the concrete backend through the feature evaluation and pilot, not by freezing a currently-free provider in this roadmap.
3. **Minimum 1.0 guard:** provide free-only operation, explicit provider opt-in, bounded fallback attempts, and refusal when eligibility, price, privacy terms, or execution capability are unknown. Record every attempt and why it was selected or rejected. Paid overflow stays disabled.
4. **Later budget and provider breadth:** add paid overflow with per-task/daily budgets, direct API or local adapters, and more free sources only when the pilot shows useful coverage. Discover volatile free models from providers where supported; do not freeze current free-model names into Ballast logic.

Fallback applies at an idempotent workflow step boundary. It must not replay a partly executed agent mutation blindly. Direct API access is a different execution harness from a coding-agent CLI and needs its own tool, context, secret, and privacy design. The existing headless no-network boundary is not relaxed by this roadmap. Provider, budget, secret, and trust changes require security/architecture review and R2 approval where they affect agent authority or launcher behavior.

**Exit evidence:** a simulated quota exhaustion selects the one qualified free backend, records the decision, and completes without duplicating side effects; an unsuitable or privacy-disallowed backend, or one whose free status cannot be established, is refused. Real pilot data then decides whether more adapters are worthwhile.

## Minimum release gate for 1.0

The indispensable promise is **reliable adoption and a complete, recoverable path to a human merge decision**. The qualified 1.0 integration target is GitHub on Linux with a systemd user session. Before calling Ballast 1.0, demonstrate all of the following on a blank repository and on an established repository such as LoreForge:

1. The Ballast CLI has a supported one-command install path; `ballast init` creates a correct, project-adapted starting point in one invocation; `doctor` explains anything the environment cannot provide. Repeating init, creating worktrees, updating a pin, and rolling back do not corrupt project files or active runs.
2. A vague request becomes a traceable spec with few user questions. An eligible R1 feature reaches a reviewed Draft PR in Autonomous without approval prompts, and the same workflow is usable interactively in Chat. The merge review clearly distinguishes provisional decisions from accepted ones.
3. A paused run safely resumes after its base advances; dirty trees, conflicting rebases, fetch failures, concurrent runs, incomplete agent steps, and lost credentials fail with recovery instructions before another agent starts.
4. The PR presents acceptance evidence, checks, open findings, and API/UI impact when applicable. For a visible feature, an on-demand demo can be captured and linked to the same PR with its exact commit and scenario. Missing evidence remains visibly missing; a generated summary never claims approval on its own.
5. The trusted launcher and install/update path pass the complete security and workflow test gate on Linux with a systemd user session, including tests currently skipped in ordinary CI. External prerequisites are stated plainly. GitHub branch protection or rulesets enforce required checks at merge. [GitHub rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/creating-rulesets-for-a-repository)
6. One zero-cost backend is qualified as a recoverable fallback from a Claude/Codex quota or availability failure, within the same permission and privacy boundary. Free-only mode prevents a paid route; failure and fallback attempts are observable.

**1.0 decisions recorded with the operator on 2026-10-02 and 2026-10-03:** a verified PR ready for a human merge decision; Chat and Autonomous as required modes; GitHub as the integrated forge; Linux with a systemd user session as the qualified host; one qualified free fallback; and on-demand UI video linked to the PR. Staging, production release, paid overflow, broad provider routing, and automatic video for every UI PR are outside this milestone. The [technical spec's 1.0 target](../../specs/TECHNICAL-SPEC.md#91-v10-target) now records this boundary; the product vision still extends to production in later releases.

## Later, only if the pilot justifies it

- Integrated staging/runtime validation and release preparation.
- A dedicated web control plane if Markdown/PR projections do not support human decisions.
- Broader visual design tooling, API portals, and learned model routing.
- Generalized cross-project metrics and hosted services.

## Suggested first vertical slice

After LoreForge adoption, create fresh worktrees for two comparable, initially underspecified UI/API features. Take each through discovery, a reviewable spec, implementation, Draft PR, a pause while `main` advances, safe resume, API/UI evidence, and a human merge decision. Run one in Chat (with explicit intermediate approvals) and one in Autonomous (with provisional intermediate decisions). Request a Playwright demo video for one PR. Track: setup commands and elapsed time per worktree, clarification rounds, late requirement changes, stale resumes blocked or synchronized, duplicate PRs, operator interventions by mode, time spent preparing a gate, acceptance criteria with evidence, and whether the video helped the decision. The pilots should reveal integration gaps before Ballast builds a new interface or many provider adapters.
