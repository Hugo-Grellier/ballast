<!-- ballast-discovery: input evidence -->
# Discovery brief: Capture a UI walkthrough on demand and link it to the PR

This brief is input evidence for [spec.md](spec.md). It is not the feature's
authority: once intent is recorded, [spec.md](spec.md) and [intent.md](intent.md)
govern, and later steps do not read requirements from this file.

**Mode**: autonomous
**Issue**: #22 (snapshot `.specify/workflow-state/issues/22.md`, untrusted requirements data)

## Sources

- S-1: Issue #22 body
- S-2: Issue #22 intake scope comment
- S-3: AGENTS.md#invariants
- S-4: .specify/memory/constitution.md (BL-INV-001, BL-INV-002, BL-INV-003, BL-INV-006)
- S-5: specs/TECHNICAL-SPEC.md#91-v10-target
- S-6: docs/plans/2026-10-02-product-roadmap.md#priority-6--show-implemented-functionality-with-video
- S-7: docs/plans/2026-10-02-product-roadmap.md#priority-5--make-review-moments-useful
- S-8: docs/policies/project/workflow.md#r2-boundaries
- S-9: docs/policies/security.md#untrusted-boundaries
- S-10: docs/policies/spec-kit-workflow.md#acceptance-packet
- S-11: docs/policies/spec-kit-workflow.md#autonomous-runs
- S-12: docs/adr/0003-launcher-github-authority.md
- S-13: docs/adr/0006-review-packet-reads.md
- S-14: specs/19-acceptance-packet/spec.md (FR-011, FR-012, AC-018)
- S-15: tools/spec_workflow/packet.py (`review_config`, `_ui_states`)
- S-16: tools/spec_workflow/artifacts.py (`run_checks`, `project_checks`)
- S-17: templates/github/workflows/pr-title.yml
- S-18: specs/22-ui-demo/autonomous/record.md
- unavailable: Issue #22 comments — the snapshot records none
- unavailable: docs/policies/project/security.md — the project provides no security extension

## Need

- **User**: the operator or reviewer deciding whether to merge a Draft PR for a feature with visible UI behavior. [S: Issue #22 body]
- **Job to be done**: request, from an existing PR, a short reproducible video of the implemented UI journey and see it linked in the PR with the commit, scenario and environment it shows. [S: Issue #22 body] [S: IAC-1]
- **Current pain**: Ballast has no demo capture contract; a project can test UI changes, but Ballast collects no shareable walkthrough, and the #19 packet only links UI results the project already produced ("Ballast captures nothing itself"). [S: docs/plans/2026-10-02-product-roadmap.md] [S: docs/policies/spec-kit-workflow.md#acceptance-packet]
- **Intended outcome**: on request, a project-supplied reproducible scenario is recorded and linked to the same PR with its commit and scenario, while automated assertions still decide whether behavior passed. [S: specs/TECHNICAL-SPEC.md#91-v10-target] [S: docs/plans/2026-10-02-product-roadmap.md#priority-6--show-implemented-functionality-with-video]

## Examples

- LoreForge declares one Playwright acceptance journey with a fixed viewport and seeded fixtures; the operator requests capture for its feature PR, and the packet gains a demo line linking a short video with the head commit, the scenario name, the environment and `captured`. [S: docs/plans/2026-10-02-product-roadmap.md#priority-6--show-implemented-functionality-with-video] [S: IAC-1]
- A project without a browser UI declares a demo script or concise CLI recording as its scenario instead of a Playwright test. [S: docs/plans/2026-10-02-product-roadmap.md#priority-6--show-implemented-functionality-with-video]
- The demo command fails or produces no video; the packet shows the demo as failed or missing with the reason, no success is claimed, and the existing Draft PR is updated in place. [S: IAC-3]
- A developer reruns the same scenario on their machine with the command the packet names and sees the same journey. [S: IAC-2] [P: D-05]

## Scope

- A project demo command and scenario contract, declared by the project. [S: Issue #22 body]
- Capture on explicit operator request, from seeded nonsensitive data. [S: Issue #22 body]
- Storage of the media as an access-controlled artifact with retention, never committed to the feature branch. [S: Issue #22 body] [S: docs/plans/2026-10-02-product-roadmap.md#priority-6--show-implemented-functionality-with-video]
- A link in the #19 packet on the existing Draft PR with commit SHA, scenario name, environment and outcome. [S: Issue #22 intake scope comment] [S: docs/plans/2026-10-02-product-roadmap.md#priority-6--show-implemented-functionality-with-video]
- Reporting a failed or unavailable capture as missing evidence. [S: IAC-3]
- User documentation of the contract, the request and the packet line. [S: docs/policies/documentation.md]

## Non-goals

- Automatic capture for every UI PR. [S: Issue #22 body] [S: specs/TECHNICAL-SPEC.md#91-v10-target]
- Video as a substitute for assertions: a video never changes a criterion's evidence state. [S: Issue #22 body] [S: docs/plans/2026-10-02-product-roadmap.md#priority-6--show-implemented-functionality-with-video]
- Committing media binaries to feature branches. [S: Issue #22 body]
- Ballast choosing, installing or downloading a browser or recording tool; the project supplies its own. [S: docs/policies/project/workflow.md#r2-boundaries] [S: docs/plans/2026-10-02-product-roadmap.md#priority-6--show-implemented-functionality-with-video]
- Inspecting or redacting video content after capture. [I]
- Forges other than GitHub, staging or production validation. [S: specs/TECHNICAL-SPEC.md#91-v10-target]

## Constraints

- Risk is R2: a trusted workflow invokes project-supplied demo commands, which touches "what `ballast` executes or downloads"; in this Autonomous run the pre-change approval is agent-provisional and the merge is the single human approval. [S: Issue #22 body] [S: docs/policies/project/workflow.md#r2-boundaries] [S: specs/22-ui-demo/autonomous/record.md]
- Nothing the launcher executes comes from a checkout an agent can write; an agent never gains more authority than its caller. [S: AGENTS.md#invariants] [S: .specify/memory/constitution.md]
- The trusted launcher holds GitHub authority through a fixed `gh` allowlist; a new GitHub call extends that allowlist by a new ADR. [S: docs/adr/0003-launcher-github-authority.md]
- The packet is a derived summary bound to the head commit; it never presents itself as an approval. [S: specs/19-acceptance-packet/spec.md] [S: .specify/memory/constitution.md]
- The #19 packet projections add no command Ballast executes; the demo capture is that new execution path, so it is this feature's R2 part. [S: specs/19-acceptance-packet/spec.md]
- A project commits only `ballast.toml`, its constitution, `docs/policies/project/` and copy-once files. [S: .specify/memory/constitution.md]
- Workflow tools stay standard-library-only and run under `python3 -I -S`. [S: AGENTS.md#invariants]
- Credentials and tokens stay out of logs and artifacts; external commands run as argument arrays. [S: docs/policies/security.md#untrusted-boundaries]

## Permissions and data authority

- Only the operator requests a capture, through the trusted `ballast` command; agents cannot call `gh` and cannot request one. [S: IAC-1] [S: docs/adr/0003-launcher-github-authority.md]
- The demo contract lives in protected `ballast.toml`, which agents cannot change. [S: docs/policies/spec-kit-workflow.md#acceptance-packet] [S: AGENTS.md#invariants]
- The capture job receives no repository secrets and a read-only token, so no credential exists to be recorded. [S: IAC-2] [S: docs/policies/security.md#untrusted-boundaries]
- The video is evidence only; the spec, acceptance-evidence manifest and recorded checks stay the authority for whether behavior passed. [S: Issue #22 body] [S: specs/19-acceptance-packet/spec.md]
- Access to the media follows read access to the GitHub repository through its Actions artifact; on a public repository that read access is public, which is why the scenario uses only nonsensitive seeded data. [I]

## Success evidence

- A pilot capture on a UI feature PR shows a working video link on the same PR with commit, scenario, environment and outcome. [S: IAC-1] [S: docs/plans/2026-10-02-product-roadmap.md]
- Deterministic tests without network cover a captured, failed, missing, in-progress and unconfigured demo in the packet, the dispatch argv, and that a request never creates a PR. [S: IAC-3] [S: docs/policies/testing.md]
- The capture workflow template has no secrets, `contents: read` permissions, and runs the contract's command at the PR head commit. [S: IAC-2]
- The docs name the local command that reproduces the scenario. [S: IAC-2] [P: D-05]
- The fast gate and the full local gate are recorded in the PR. [S: AGENTS.md]

## Edge, failure and permission cases

- The project has no demo contract: the request refuses with a remedy, and the packet shows the demo as not configured. [S: docs/policies/spec-kit-workflow.md#acceptance-packet]
- The contract is invalid (unknown key, unsafe output path, unknown scenario): a fixed reason, never a stop of the rest of the packet. [S: tools/spec_workflow/packet.py]
- The demo command fails, times out or writes no video: the outcome is `failed` or `missing` with the reason; no success is claimed. [S: IAC-3] [P: D-06]
- The capture is still running at the checkpoint: the packet shows it as in progress and the next checkpoint refreshes it. [P: D-07]
- The head commit moves after capture: the demo is shown as stale for the old commit, never as current. [S: specs/19-acceptance-packet/spec.md] [S: IAC-1]
- The artifact expired after its retention: the packet shows the demo as expired or missing, not as a working link. [P: D-06]
- No Draft PR exists yet, or the PR is closed, merged or blocked: the request refuses and creates no PR. [S: IAC-3] [S: docs/policies/spec-kit-workflow.md#acceptance-packet]
- An agent changes the demo workflow file on the feature branch: the dispatched workflow definition comes from the default branch, so the agent's change does not run with the operator's authority. [S: AGENTS.md#invariants] [I]
- Agent-written scenario names or command output reach the packet only as inert data. [S: specs/19-acceptance-packet/spec.md]
- GitHub is unreachable or `gh` lacks permission to dispatch a workflow: a fixed retryable reason and remedy, never a token in output. [S: docs/adr/0003-launcher-github-authority.md]
- A repeated request for the same commit and scenario adds a new capture without a second PR or a second packet section. [S: IAC-3] [I]

## Issue acceptance criteria

- IAC-1: An operator requests capture for a UI feature and receives a working video link on the same PR, bound to its commit, scenario and environment.
- IAC-2: The demonstrated journey is reproducible locally and keeps credentials/private data out of the recording.
- IAC-3: A failed capture is reported as missing evidence; no successful demo is claimed and no duplicate PR is created.

## Known

- #19 is implemented: the packet already reads `[review]` from `ballast.toml`, including `[[review.ui_states]]` with a committed path or a GitHub check run, and states that Ballast captures nothing itself. [S: tools/spec_workflow/packet.py] [S: docs/policies/spec-kit-workflow.md#acceptance-packet]
- Project commands already run from protected `ballast.toml` (`[checks] commands`), confined, by trusted `artifacts.py`. [S: tools/spec_workflow/artifacts.py]
- ADR-0003 fixes the `gh` allowlist and says later features extend it by a new ADR; ADR-0006 extended it for packet reads. [S: docs/adr/0003-launcher-github-authority.md] [S: docs/adr/0006-review-packet-reads.md]
- Ballast already ships a copy-once GitHub Actions workflow template with `contents: read`. [S: templates/github/workflows/pr-title.yml]
- The roadmap names a CI artifact or other access-controlled location with retention for the media, and commit SHA, scenario name, environment and outcome as its metadata. [S: docs/plans/2026-10-02-product-roadmap.md#priority-6--show-implemented-functionality-with-video]
- Automatic demo capture is a later release. [S: specs/TECHNICAL-SPEC.md#91-v10-target]
- The run's scope decision PD-0001 records the feature as one cohesive R2 outcome. [S: specs/22-ui-demo/autonomous/record.md]

## Inferred

- The plan needs a new ADR extending ADR-0003 with the workflow dispatch and the run and artifact reads. [I]
- The request is a new trusted launcher subcommand bound to the feature's Draft PR; its name is a plan detail. [I]
- The packet gains a demo section beside the UI states, rather than reusing a UI state's `check`, so it can show scenario, environment and outcome. [I]
- Ballast executes nothing new locally beyond `gh` calls; the project's command runs on the GitHub runner. [P: D-05]
- Artifact retention defaults to 14 days, configurable within GitHub's limit, and a capture is bounded by a timeout. [P: D-06]
- The request returns after dispatching; a bounded wait or the next `ballast run checkpoint` fills in the result. [P: D-07]

## Undecided

None.

## Decisions

### D-01: Where the capture runs and the media is stored
- **Status**: settled
- **Question**: Is the video recorded on the operator's machine or in a GitHub Actions job, and where is it stored?
- **Why it matters**: decides the execution path, the storage, the link the PR can carry and the new GitHub authority.
- **Sources**: [S: IAC-1] [S: docs/plans/2026-10-02-product-roadmap.md#priority-6--show-implemented-functionality-with-video] [S: specs/TECHNICAL-SPEC.md#91-v10-target] [S: specs/19-acceptance-packet/spec.md]
- **Options**:
  - A — A GitHub Actions job runs the project's demo command and uploads the video as an Actions artifact with retention. Consequence: a working, access-controlled link on the PR; a new workflow template and new `gh` calls.
  - B — Capture locally and keep the file in the operator's run archive. Consequence: the PR cannot link a local file, so IAC-1 fails.
- **Recommended default**: A, because it is the only option that gives the PR a working, access-controlled link.
- **Answer**:
- **Resolution**: A. The roadmap names a CI artifact with retention [S: docs/plans/2026-10-02-product-roadmap.md#priority-6--show-implemented-functionality-with-video]; IAC-1 requires a working link on the same PR [S: IAC-1]; GitHub is the integrated forge [S: specs/TECHNICAL-SPEC.md#91-v10-target]; and a local archive cannot be linked from the PR [S: specs/19-acceptance-packet/spec.md].

### D-02: Who requests a capture and how
- **Status**: settled
- **Question**: Is capture requested by the operator through the trusted `ballast` command, or by a PR comment or label?
- **Why it matters**: decides who can make the project's code run with a recording, and the GitHub authority used.
- **Sources**: [S: IAC-1] [S: docs/adr/0003-launcher-github-authority.md] [S: Issue #22 body]
- **Options**:
  - A — The operator runs a trusted `ballast` subcommand that dispatches the capture workflow for the PR's head. Consequence: only someone with the operator's GitHub write access requests it; the allowlist grows by a new ADR.
  - B — A PR comment or label triggers the workflow. Consequence: anyone able to comment or label triggers execution, and agents' text could request it.
- **Recommended default**: A, because the Issue names the operator and the launcher holds GitHub authority.
- **Answer**:
- **Resolution**: A. IAC-1 says "an operator requests capture" [S: IAC-1], and ADR-0003 makes the trusted launcher the only holder of GitHub authority, extended by a new ADR [S: docs/adr/0003-launcher-github-authority.md].

### D-03: Where the demo contract lives
- **Status**: settled
- **Question**: Is the demo command and scenario contract declared in `ballast.toml` or in another project file?
- **Why it matters**: decides whether an agent on the feature branch can change what the trusted workflow executes.
- **Sources**: [S: AGENTS.md#invariants] [S: docs/policies/spec-kit-workflow.md#acceptance-packet] [S: tools/spec_workflow/artifacts.py]
- **Options**:
  - A — A table in protected `ballast.toml`, read like `[checks]` and `[review]`. Consequence: agents cannot change it; editing it needs `ballast trust`.
  - B — A separate project file. Consequence: an agent could change the command the trusted workflow runs.
- **Recommended default**: A, because it follows the invariant and the existing pattern.
- **Answer**:
- **Resolution**: A. Nothing the launcher executes comes from a checkout an agent can write [S: AGENTS.md#invariants]; `[checks]` and `[review]` already come from protected `ballast.toml` [S: tools/spec_workflow/artifacts.py] [S: docs/policies/spec-kit-workflow.md#acceptance-packet].

### D-04: Secrets in the capture job
- **Status**: settled
- **Question**: May the capture job receive repository secrets, for example to log in to the demonstrated app?
- **Why it matters**: decides whether a credential can appear in the recording and what the workflow template grants.
- **Sources**: [S: IAC-2] [S: docs/policies/security.md#untrusted-boundaries] [S: Issue #22 body]
- **Options**:
  - A — No secrets and a read-only token; the scenario seeds nonsensitive data and fake accounts. Consequence: a demo needing a real login must seed a local fake account.
  - B — Allow named secrets. Consequence: a credential or private data can be recorded in the video.
- **Recommended default**: A, because IAC-2 requires credentials to stay out of the recording.
- **Answer**:
- **Resolution**: A. The Issue requires seeded nonsensitive data and credentials kept out of the recording [S: IAC-2] [S: Issue #22 body]; tokens stay out of artifacts [S: docs/policies/security.md#untrusted-boundaries].

### D-05: Local reproduction
- **Status**: assumed
- **Question**: Does Ballast run the demo locally, or does local reproducibility mean the contract's command runs unchanged on a developer's machine?
- **Why it matters**: decides whether Ballast gains a second, local execution path for project demo commands.
- **Sources**: [S: IAC-2] [S: docs/policies/project/workflow.md#r2-boundaries] [S: tools/spec_workflow/artifacts.py]
- **Options**:
  - A — No Ballast local capture; the contract's command is the same one a developer runs locally, and the docs and packet name it. Consequence: one execution path, on the runner.
  - B — A confined local capture like `[checks]`. Consequence: a second R2 execution path and local video handling.
- **Recommended default**: A, because it meets IAC-2 with the least new execution.
- **Answer**:
- **Resolution**: A. Safe and reversible: it adds no execution path or authority, and a confined local capture can be added later without changing the contract.

### D-06: Retention and capture limits
- **Status**: assumed
- **Question**: What artifact retention and capture timeout apply by default?
- **Why it matters**: sets the workflow template's defaults, the expired-link case and the failure on timeout.
- **Sources**: [S: docs/plans/2026-10-02-product-roadmap.md#priority-6--show-implemented-functionality-with-video] [S: Issue #22 body]
- **Options**:
  - A — 14-day retention and a 15-minute timeout, each configurable in the contract within GitHub's limits. Consequence: short-lived media; an expired link shows as missing.
  - B — The repository's default retention and no timeout. Consequence: media lives up to 90 days and a stuck capture holds a runner.
- **Recommended default**: A, because a demo serves one review and must be bounded.
- **Answer**:
- **Resolution**: A. Safe and reversible: they are defaults the project can change in its contract, and they affect neither scope nor authority.

### D-07: When the result reaches the packet
- **Status**: assumed
- **Question**: Does the request wait for the capture to finish, or does a later checkpoint pick up the result?
- **Why it matters**: decides the request's exit behavior and the packet's in-progress state.
- **Sources**: [S: docs/policies/spec-kit-workflow.md#acceptance-packet] [S: IAC-3]
- **Options**:
  - A — Dispatch, wait a bounded time, refresh the packet; if unfinished, show it in progress and let `ballast run checkpoint` refresh it. Consequence: no long blocking command; an extra state.
  - B — Block until the workflow finishes. Consequence: the command can hang for the capture's full duration.
- **Recommended default**: A, because the packet already refreshes at checkpoints without waiting for CI.
- **Answer**:
- **Resolution**: A. Safe and reversible: it reuses the existing checkpoint refresh, never claims a result before it exists, and B can be added as a flag.

### D-08: How a failed capture appears
- **Status**: settled
- **Question**: How is a failed, timed-out or video-less capture reported?
- **Why it matters**: decides the packet states and the PR handling on failure.
- **Sources**: [S: IAC-3] [S: specs/19-acceptance-packet/spec.md]
- **Options**:
  - A — The packet's demo line shows failed or missing with the reason, on the existing PR. Consequence: missing evidence stays visible.
  - B — Omit the demo line. Consequence: a reviewer cannot tell a failure from no request.
- **Recommended default**: A, because the Issue requires it.
- **Answer**:
- **Resolution**: A. IAC-3 requires a failed capture reported as missing evidence with no duplicate PR [S: IAC-3]; #19 publishes the packet in place on the one Draft PR [S: specs/19-acceptance-packet/spec.md].

## Question metrics

- **Rounds**: 0
- **Questions asked**: 0
- **Assumptions adopted**: 3
