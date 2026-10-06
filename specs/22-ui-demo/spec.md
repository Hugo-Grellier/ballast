# Feature Specification: On-demand UI demo capture linked to the PR

**Feature Branch**: `feat/22-ui-demo`

**Created**: 2026-10-06

**Status**: Draft

**Input**: User description: "Issue #22: a reviewer can request a short reproducible video of implemented UI behavior from an existing PR."

**Tracking**: [Ballast #22](https://github.com/Hugo-Grellier/ballast/issues/22), child of Epic #11; roadmap Priority 6 "show implemented functionality with video" ([product roadmap](../../docs/plans/2026-10-02-product-roadmap.md#priority-6--show-implemented-functionality-with-video)); [technical spec §91](../TECHNICAL-SPEC.md#91-v10-target). Depends on the acceptance packet ([#19](../19-acceptance-packet/spec.md)) and the Draft PR lifecycle ([#17](../17-draft-pr/spec.md)). Written from the [discovery brief](discovery.md).

**Risk**: R2. A trusted workflow runs a project-supplied demo command, which touches the boundary on what `ballast` executes or downloads in [`docs/policies/project/workflow.md`](../../docs/policies/project/workflow.md#r2-boundaries).

**Mode**: Autonomous run `d6b5dff2`. The operator's standing authority for this Epic covers running it autonomously; every gate decision on this feature, including the pre-change approval for the R2 boundary, is agent-provisional, and merging its PR is the only human approval.

## Context

A feature run already publishes an acceptance packet on its Draft PR (#19). For a feature with visible UI behavior, the packet can link UI results the project already produced, but Ballast captures nothing itself: a reviewer who wants to see the implemented journey must check out the branch, seed data and run the app by hand.

This feature lets the operator ask, from the existing Draft PR, for a short video of a scenario the project declares. The project's own demo command records it in an isolated CI job from seeded, nonsensitive data; the video is stored as an access-controlled artifact with a limited lifetime, and the packet on the same PR links it with the commit, scenario, environment and outcome. The video helps a reviewer see behavior; it never decides whether behavior passed. Assertions, the acceptance-evidence manifest and recorded checks keep that authority.

## User Scenarios & Testing *(mandatory)*

Give each acceptance scenario a stable ID (`AC-001`, `AC-002`, ...). Task and test descriptions cite the IDs they satisfy, so review can trace each criterion to evidence.

### User Story 1 - Request a demo video and see it on the same PR (Priority: P1)

The operator reviewing a feature's Draft PR wants to see the implemented UI journey before merging. They request a capture through the trusted `ballast` command. The project's declared scenario is recorded at the PR's head commit, and the packet on the same PR gains a demo line linking the video with its commit, scenario, environment and outcome.

**Why this priority**: This is the Issue's main outcome; without it there is no video and nothing to link.

**Independent Test**: In a project that declares one demo scenario, with a feature Draft PR open, request a capture and reach the next packet refresh. The packet on that PR shows one demo line with a working link to the video and the head commit, scenario name, environment and `captured`; no new PR exists.

**Acceptance Scenarios**:

1. **AC-001**: **Given** a project whose protected configuration declares a demo command and a named scenario, and a feature with an open Draft PR, **When** the operator requests a capture for that feature, **Then** the scenario is captured at the PR's head commit by the project's demo command in a CI job, and the request names the dispatched job. [S: IAC-1] [B: D-01] [B: D-02]
2. **AC-002**: **Given** a capture that finished and produced a video, **When** the packet on the same Draft PR is refreshed, **Then** it shows a demo line with a working link to the stored video, the commit SHA it was captured at, the scenario name, the environment and the outcome `captured`. [S: IAC-1] [B: D-08]
3. **AC-003**: **Given** a video was captured for an earlier head commit and the head has since moved, **When** the packet is refreshed, **Then** the demo line shows `stale` with the commit the video belongs to, and never presents it as showing the current head. [S: IAC-1] [S: specs/19-acceptance-packet/spec.md]
4. **AC-004**: **Given** a capture is still running when the request's bounded wait ends or a checkpoint runs, **When** the packet is refreshed, **Then** the demo line shows `in progress` with a link to the running job, and the next `ballast run checkpoint` replaces it with the final outcome. [S: IAC-1] [P: D-07]
5. **AC-005**: **Given** any demo line, **When** the packet is published, **Then** no acceptance criterion's evidence state changes because of the video, and the packet never labels the video as an approval or as proof that a criterion passed. [S: Issue #22 body] [S: specs/19-acceptance-packet/spec.md]
6. **AC-006**: **Given** the operator requests a capture for the same commit and scenario again, **When** it completes, **Then** the packet's single demo section shows the newest capture, the Draft PR is updated in place, and no second PR or second demo section is created. [S: IAC-3] [I]

---

### User Story 2 - Reproduce the journey locally without private data (Priority: P1)

A developer or reviewer wants to see the same journey on their own machine. The packet and the documentation name the command that reproduces the scenario. The recorded journey uses only seeded, nonsensitive data, and the capture job has no secret that could appear on screen.

**Why this priority**: A video nobody can reproduce, or one that leaks a credential, fails the Issue's second criterion and the security policy.

**Independent Test**: From the packet's demo line, copy the named command and run it in a clean checkout of the captured commit; the same scenario runs. Inspect the installed capture workflow: it requests no repository secrets and only read access.

**Acceptance Scenarios**:

1. **AC-007**: **Given** a demo line in the packet, **When** the reviewer reads it, **Then** it names the scenario's command exactly as the project's configuration declares it, and the user documentation explains that running this command at the captured commit reproduces the journey locally. [S: IAC-2] [P: D-05]
2. **AC-008**: **Given** the capture workflow Ballast installs for a project, **When** it runs, **Then** it receives no repository secrets, holds only read access to repository contents, and checks out the PR's head commit to run the declared command. [S: IAC-2] [B: D-04]
3. **AC-009**: **Given** the documentation of the demo contract, **When** a project author reads it, **Then** it states that a scenario must use seeded, nonsensitive data and fake accounts, and that the stored video is readable by anyone with read access to the repository. [S: IAC-2] [S: Issue #22 body] [I]
4. **AC-010**: **Given** an agent on the feature branch edits the capture workflow file or any file outside the protected configuration, **When** the operator requests a capture, **Then** the command and scenario that run come from the protected configuration and the workflow definition comes from the default branch, so the agent's edit does not run with the operator's authority. [S: AGENTS.md#invariants] [B: D-03] [I]

---

### User Story 3 - A failed capture shows as missing evidence (Priority: P1)

When the capture cannot produce a video, the reviewer sees that plainly on the same PR, with the reason, instead of an empty space or a broken link that looks like success.

**Why this priority**: Silent failure would let a reviewer believe the behavior was demonstrated; the Issue requires failure to read as missing evidence.

**Independent Test**: Make the demo command fail, make it time out, and make it exit successfully without writing a video; request a capture for each and refresh the packet. Each shows `failed` or `missing` with a reason, the PR count stays one, and nothing claims a captured demo.

**Acceptance Scenarios**:

1. **AC-011**: **Given** the demo command exits with an error or exceeds the capture timeout, **When** the packet is refreshed, **Then** the demo line shows `failed` with a fixed reason and a link to the job, and no `captured` outcome or video link appears. [S: IAC-3] [B: D-08] [P: D-06]
2. **AC-012**: **Given** the demo command succeeds but writes no video at the declared output path, or the stored video has expired after its retention, **When** the packet is refreshed, **Then** the demo line shows `missing` with the reason, never a working-link presentation. [S: IAC-3] [P: D-06]
3. **AC-013**: **Given** a failed or missing capture, **When** the packet is published, **Then** it is published in place on the existing Draft PR and no new PR is created. [S: IAC-3] [S: specs/19-acceptance-packet/spec.md]
4. **AC-014**: **Given** the feature has no Draft PR, or its PR is closed, merged or blocked, **When** the operator requests a capture, **Then** the request refuses with a remedy, dispatches nothing and creates no PR. [S: IAC-3] [S: docs/policies/spec-kit-workflow.md#acceptance-packet]

---

### User Story 4 - Declare the demo contract once and get clear refusals (Priority: P2)

A project author declares the demo command, its scenarios, output path, retention and timeout in the protected project configuration. A missing or invalid declaration produces a clear refusal or packet state rather than an attempted capture or a broken packet.

**Why this priority**: The contract is what the capture runs, so it must be protected and validated; it matters only once capture exists.

**Independent Test**: With no contract, with an unknown key, with an output path outside the workspace and with an unknown scenario name, request a capture and refresh the packet. Each refuses with a fixed reason and remedy, and the rest of the packet still publishes.

**Acceptance Scenarios**:

1. **AC-015**: **Given** a project whose configuration declares no demo contract, **When** the operator requests a capture, **Then** the request refuses with a remedy naming the configuration to add, and the packet shows the demo as `not configured` while the rest of the packet publishes normally. [S: docs/policies/spec-kit-workflow.md#acceptance-packet] [B: D-03]
2. **AC-016**: **Given** a demo contract with an unknown key, an output path that escapes the workspace, or a request for a scenario the contract does not declare, **When** the request or packet refresh reads it, **Then** it reports a fixed reason naming the problem, dispatches nothing, and the rest of the packet still publishes. [S: tools/spec_workflow/packet.py] [I]
3. **AC-017**: **Given** a demo contract that sets no retention or timeout, **When** a capture runs, **Then** the video is kept 14 days and the capture is stopped after 15 minutes; a contract value within the forge's limits overrides each default. [P: D-06]
4. **AC-018**: **Given** the forge is unreachable or the operator's GitHub access cannot dispatch the capture, **When** the operator requests a capture, **Then** the request fails with a fixed, retryable reason and remedy, and no token or credential appears in its output or in the run's records. [S: docs/adr/0003-launcher-github-authority.md] [S: docs/policies/security.md#untrusted-boundaries]
5. **AC-019**: **Given** an agent running a workflow step, **When** it tries to request a capture, **Then** it cannot, because only the trusted `ballast` command run by the operator holds the authority to dispatch one. [B: D-02] [S: AGENTS.md#invariants]

---

### Edge Cases

- Scenario names, job names and command output written by the project or an agent reach the packet only as inert, escaped text, never as markup or links that change the packet's structure. [S: specs/19-acceptance-packet/spec.md]
- A project without a browser UI declares a demo script or terminal recording as its scenario; the contract does not require a particular recording tool. [S: docs/plans/2026-10-02-product-roadmap.md#priority-6--show-implemented-functionality-with-video]
- The project declares several scenarios: the operator names one per request, and the packet shows the latest outcome for each scenario requested. [I]
- A human deleted the packet's section: the next checkpoint restores it with the demo line, as for any packet section. [S: specs/19-acceptance-packet/spec.md]
- The project has not installed the capture workflow template: the request refuses with a remedy naming the template, rather than dispatching a workflow that does not exist. [I]

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: A project MUST be able to declare, in its protected Ballast configuration, a demo contract naming one or more scenarios, each with the command that runs it, the path where it writes its video and the environment it describes. [S: Issue #22 body] [B: D-03]
- **FR-002**: The demo contract MUST be read only from the protected configuration that agents cannot change; Ballast MUST NOT read the command to run from any file an agent can write. [S: AGENTS.md#invariants] [B: D-03]
- **FR-003**: Ballast MUST validate the contract and refuse a capture, with a fixed reason and remedy, when the contract is absent, has an unknown key, declares an output path outside the workspace, or the requested scenario is undeclared. [S: tools/spec_workflow/packet.py] [I]
- **FR-004**: The operator MUST be able to request a capture for a feature's open Draft PR through the trusted `ballast` command; no agent, PR comment or label MUST be able to request one. [S: IAC-1] [B: D-02]
- **FR-005**: A capture request MUST run the declared scenario at the Draft PR's head commit in a CI job on the forge, not on the operator's machine. [S: IAC-1] [B: D-01] [P: D-05]
- **FR-006**: Ballast MUST ship a capture workflow template that receives no repository secrets, holds read-only repository access, runs the declared command at the requested commit, stops it after the configured timeout and stores the produced video as an access-controlled CI artifact with the configured retention. [S: IAC-2] [B: D-01] [B: D-04] [P: D-06]
- **FR-007**: The capture workflow definition that runs MUST be the one on the repository's default branch, so a change on the feature branch does not run with the operator's authority. [S: AGENTS.md#invariants] [I]
- **FR-008**: Retention MUST default to 14 days and the capture timeout to 15 minutes, each overridable in the contract within the forge's limits. [P: D-06]
- **FR-009**: After dispatching, the request MUST wait a bounded time, then refresh the packet; an unfinished capture MUST show `in progress` and the next run checkpoint MUST refresh it. [P: D-07]
- **FR-010**: The acceptance packet MUST include a demo section that, for each requested scenario, shows the scenario name, the commit SHA, the environment, the reproduce command and one outcome of `captured`, `in progress`, `failed`, `missing`, `stale` or `not configured`, with a link to the video or job when one exists. When a contract is declared but no capture has been requested on the feature, the section lists the declared scenarios as not yet requested, distinct from every outcome above. [S: IAC-1] [S: IAC-3] [B: D-08] [P: clarification-2]
- **FR-011**: The packet MUST show a capture for a commit other than the current head as `stale` with its commit and the outcome it had at that commit, whatever that outcome was, and an expired or absent video as `missing`, never as a working link. [S: IAC-1] [S: IAC-3] [P: D-06] [P: clarification-1]
- **FR-012**: A failed, timed-out or video-less capture MUST be reported as `failed` or `missing` with a fixed reason; Ballast MUST NOT claim a successful demo it cannot link. [S: IAC-3] [B: D-08]
- **FR-013**: A capture request MUST NOT create a PR; it MUST refuse with a remedy when the feature has no open Draft PR, and every packet update MUST be made in place on the existing Draft PR. [S: IAC-3] [S: docs/policies/spec-kit-workflow.md#acceptance-packet]
- **FR-014**: A demo outcome MUST NOT change any acceptance criterion's evidence state, and the packet MUST NOT present a video as an approval or as proof of a criterion. [S: Issue #22 body] [S: specs/19-acceptance-packet/spec.md]
- **FR-015**: Each new forge call Ballast makes for capture (dispatching the workflow and reading its run and artifact) MUST be added to the launcher's fixed GitHub allowlist by a new architecture decision record extending ADR-0003. [S: docs/adr/0003-launcher-github-authority.md] [I]
- **FR-016**: Ballast MUST NOT choose, install or download a browser or recording tool; the project's demo command supplies its own. [S: docs/policies/project/workflow.md#r2-boundaries] [S: docs/plans/2026-10-02-product-roadmap.md#priority-6--show-implemented-functionality-with-video]
- **FR-017**: Forge failures MUST produce a fixed, retryable reason and remedy; no token or credential MUST appear in Ballast's output, records or the packet, and external commands MUST run as argument arrays. [S: docs/policies/security.md#untrusted-boundaries]
- **FR-018**: Project- or agent-written text from the contract or the job (scenario names, environment, command, reasons) MUST reach the packet only as escaped inert data. [S: specs/19-acceptance-packet/spec.md]
- **FR-019**: The user documentation MUST describe the demo contract, how the operator requests a capture, each packet demo outcome, the local reproduce command, and the requirement to use seeded nonsensitive data because the artifact is readable by anyone with repository read access. [S: IAC-2] [S: docs/policies/documentation.md] [P: D-05]
- **FR-020**: The Ballast workflow tools added for this feature MUST stay standard-library-only and run under `python3 -I -S`. [S: AGENTS.md#invariants]

### Key Entities

- **Demo contract**: the project's declaration in protected configuration: scenarios, and for each its command, video output path and environment, plus optional retention and timeout.
- **Demo scenario**: one named, reproducible journey from seeded nonsensitive data; its command is what a developer runs locally.
- **Capture request**: the operator's request for one scenario on one feature's Draft PR, bound to the PR's head commit at request time.
- **Demo capture**: the outcome of one request: scenario, commit SHA, environment, outcome, reason, job link, and the stored video with its expiry when one exists.
- **Packet demo section**: the part of the #19 packet that shows the latest capture per requested scenario; a derived summary, never an authority.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In a pilot on one UI feature PR, the operator requests a capture with one command and, within the request's bounded wait or by the next checkpoint, the same PR shows a working video link with commit, scenario, environment and outcome.
- **SC-002**: 100% of failed, timed-out, video-less, expired, stale, in-progress and unconfigured captures show their own non-`captured` state in the packet; none shows a working-link `captured` state.
- **SC-003**: Across any number of capture requests on a feature, the feature has exactly one PR and the packet exactly one demo section.
- **SC-004**: A reviewer can reproduce the captured journey locally by running the single command the packet names, without any credential.
- **SC-005**: The installed capture workflow grants zero repository secrets and read-only repository access.
- **SC-006**: The packet and the request's output contain no credential in any tested success or failure case.

## Non-goals

- Automatic capture for every UI PR; capture happens only on the operator's request. [S: Issue #22 body] [S: specs/TECHNICAL-SPEC.md#91-v10-target]
- Video as a substitute for assertions. [S: Issue #22 body]
- Committing media binaries to feature branches. [S: Issue #22 body]
- A local capture run by Ballast; local reproduction means running the contract's command directly. [P: D-05]
- Inspecting or redacting video content after capture. [I]
- Forges other than GitHub, and staging or production validation. [S: specs/TECHNICAL-SPEC.md#91-v10-target]

Every Issue acceptance criterion (IAC-1, IAC-2, IAC-3) is covered by an acceptance criterion above; none is a non-goal.

## Assumptions

- Ballast runs nothing new locally for capture beyond forge calls; the project's command runs only on the forge's runner (D-05, agent-provisional). [P: D-05]
- Retention defaults to 14 days and the capture timeout to 15 minutes (D-06, agent-provisional). [P: D-06]
- The request dispatches, waits a bounded time and leaves unfinished captures to the next checkpoint (D-07, agent-provisional). [P: D-07]
- Access to the video follows read access to the repository through its CI artifact; on a public repository that access is public. [I]
- The capture request is a new trusted launcher subcommand bound to the feature's Draft PR; its name is a plan detail. [I]
- The packet's demo section sits beside the existing UI states rather than reusing a UI state's check, so it can show scenario, environment and outcome. [I]
- A repeated request for the same commit and scenario adds a new capture and the packet shows the newest. [I]
- The capture workflow is a copy-once template the project commits and enables on its default branch, like the existing PR-title workflow. [S: templates/github/workflows/pr-title.yml] [I]
- `stale` takes precedence over a capture's own outcome: a capture for a commit other than the current head, whether it was `captured`, `failed` or `missing`, shows `stale` together with its commit and the outcome it had there, so a past failure stays visible and an old video never reads as showing the current head (clarification 1, agent-provisional). [P: clarification-1]
- When a demo contract is declared but no capture has been requested on the feature, the demo section lists the declared scenarios as not yet requested; this is not one of the capture outcomes and is distinct from `not configured` and from a failure (clarification 2, agent-provisional). [P: clarification-2]
