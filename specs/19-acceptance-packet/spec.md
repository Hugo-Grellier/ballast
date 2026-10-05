# Feature Specification: Source-linked acceptance packet on the Draft PR

**Feature Branch**: `feat/19-acceptance-packet`

**Created**: 2026-10-05

**Status**: Draft

**Input**: User description: "Issue #19: The human can understand changed behavior and missing evidence from the PR before reading the full diff, through a source-linked acceptance packet on the Draft PR."

**Tracking**: [Ballast #19](https://github.com/Hugo-Grellier/ballast/issues/19), child of Epic #11; roadmap Priority 5 "make review moments useful" ([product roadmap](../../docs/plans/2026-10-02-product-roadmap.md#priority-5--make-review-moments-useful)); [technical spec §91](../TECHNICAL-SPEC.md#91-v10-target) ("the PR also carries concise, source-linked acceptance evidence, checks and unresolved decisions"). Depends on the Draft PR lifecycle ([#17](../17-draft-pr/spec.md)) and reads the Autonomous run record ([#27](../27-autonomous-core/spec.md)).

**Risk**: R1. The packet is review output derived from existing authority, published through the Draft PR checkpoint that #17 already gives the trusted launcher. It adds no agent authority, no new GitHub write beyond the launcher's own marked PR text, and no new command execution path. The plan rechecks this against the R2 boundaries in [`docs/policies/project/workflow.md`](../../docs/policies/project/workflow.md); if the OpenAPI or UI projection would make Ballast execute or download something new, that part is R2.

**Mode**: Autonomous run `97858712`. Every gate decision on this feature is agent-provisional; merging its PR is the only human approval.

## Context

A feature run already leaves good evidence behind: the spec with stable acceptance IDs, the plan and tasks, an acceptance-evidence manifest that names the test for each criterion, `run-checks` results in the ledger, review reports, decisions, the Autonomous run record and CI results on the PR. #17 makes one Draft PR exist for the feature, and #27 puts the run's merge-review summary in it.

What the human still lacks is one view that joins these. To learn whether criterion AC-004 is proven, they open the spec, then tasks, then the manifest, then the test, then the CI run, and they still cannot tell whether that CI run was for the commit they are looking at. Missing evidence is invisible because nothing lists what should be there. The roadmap calls the result "canonical artifacts exist, but … acceptance evidence [is] not yet projected into a concise review surface".

This feature adds that surface: a short acceptance packet in the Draft PR, regenerated at each PR checkpoint from the canonical sources, bound to the commits it describes, and linking back to every source. It summarizes; it never replaces or overrides a source, and it never claims an approval that a source does not record.

## User Scenarios & Testing *(mandatory)*

Give each acceptance scenario a stable ID (`AC-001`, `AC-002`, ...). Task and test descriptions cite the IDs they satisfy, so review can trace each criterion to evidence.

### User Story 1 - See each criterion's evidence, or its absence, in the PR (Priority: P1)

A human opens the feature's Draft PR to decide whether to accept it. Before reading any code, they read the packet: every acceptance criterion of the feature's spec, each with the evidence that proves it and that evidence's result, or an explicit "missing" state. Beside it they see the risk level, every provisional decision and every open review finding.

**Why this priority**: This is the Issue's main outcome. Without it the human must reconstruct coverage by hand or trust a summary that hides gaps.

**Independent Test**: For a feature whose spec has several criteria, where some have passing evidence, one has a failing test, one has no named evidence and one has evidence from an older commit, reach a PR checkpoint and read the packet. Every criterion is listed once with the right state and a link to its evidence or to the place evidence should be.

**Acceptance Scenarios**:

1. **AC-001**: **Given** a feature whose spec defines acceptance criteria and whose acceptance-evidence manifest names verification for some of them, **When** a PR checkpoint publishes the packet, **Then** the packet lists every criterion ID from the spec exactly once, in spec order, each with a short title taken from the spec, a link to the criterion in the spec, and one evidence state.
2. **AC-002**: **Given** a criterion whose named evidence passed in a recorded check run at the packet's head commit, **When** the packet is published, **Then** the criterion shows `verified` with a link to each named test's file at the head commit and a link to the check run or CI result for the head commit when one exists; evidence recorded only in the local run ledger, which has no URL, is named by its run ID and event sequence instead (DEC-0001).
3. **AC-003**: **Given** a criterion with no named evidence, or a feature with no acceptance-evidence manifest yet, **When** the packet is published, **Then** the criterion shows `missing` and the packet states what is missing; it never shows such a criterion as verified.
4. **AC-004**: **Given** a criterion whose named evidence failed, was not run at the head commit, or was recorded only for an earlier head commit or an earlier spec version, **When** the packet is published, **Then** the criterion shows `failed`, `not run` or `stale` respectively, and the packet names the commit or spec version the evidence belongs to.
5. **AC-005**: **Given** recorded provisional decisions, open review findings and a recorded risk level, **When** the packet is published, **Then** the packet shows the risk level, lists each provisional decision with its ID and a link to its record, lists each open finding with its severity and a link to its review report, and shows a count of zero explicitly when there are none.
6. **AC-006**: **Given** a human-gated run with recorded human approvals and an Autonomous run with provisional decisions, **When** each packet is published, **Then** each approval or decision is labeled as human or agent-provisional exactly as its source records it, and the packet itself is never presented as an approval.

---

### User Story 2 - Locate every canonical source from the packet (Priority: P1)

From the packet, the reviewer jumps directly to the spec, plan, tasks, decisions, review reports, run record and the diff, each at the commit the packet describes, so they can check any summary line against its source.

**Why this priority**: A summary the reviewer cannot trace to its source is a second, weaker source of truth. Direct links keep the canonical artifacts authoritative.

**Independent Test**: Publish a packet for a feature that has all canonical artifacts and for one missing some. Follow every link in the packet: each resolves to the named artifact at the packet's head commit, and each absent artifact is listed as absent rather than linked.

**Acceptance Scenarios**:

1. **AC-007**: **Given** a feature directory with intent, spec, plan, tasks, decisions, review reports and a run record, **When** the packet is published, **Then** it contains a sources section with one link per artifact, each pinned to the packet's head commit, and a link to the diff between the packet's base and head commits.
2. **AC-008**: **Given** a feature directory where one or more of those artifacts do not exist yet, **When** the packet is published, **Then** each absent artifact is listed as `not present` with no link, and the rest of the packet is still published.
3. **AC-009**: **Given** any summary line in the packet (criterion title, decision, finding, check), **When** the reviewer looks at it, **Then** it carries a link to the source record it was derived from, or, for a record that exists only in the local run ledger and has no URL, names its run ID and event sequence (DEC-0001).

---

### User Story 3 - The packet stays current and honest about which commits it describes (Priority: P1)

As work continues, the packet on the same Draft PR is updated in place. It always says which feature version, base commit and head commit it describes, so a reviewer can tell when evidence no longer matches the code under review.

**Why this priority**: Evidence for a different commit is not evidence. Duplicated or stale packets would mislead the reviewer at the decision point.

**Independent Test**: Reach several PR checkpoints on one feature: with no change, after a new commit, after a spec change, and after a human edits other parts of the PR description. Check that one packet exists, that it is unchanged when nothing changed, that it reflects each new commit and that the human's text is untouched.

**Acceptance Scenarios**:

1. **AC-010**: **Given** a published packet, **When** a later PR checkpoint runs with the same feature version, base and head commits and the same recorded evidence, **Then** the packet makes no edit to the PR description and the ledger records the packet as `unchanged`.
2. **AC-011**: **Given** a published packet, **When** a later PR checkpoint runs after the head commit, base commit, feature version or recorded evidence changed, **Then** the existing packet is replaced in place, the PR still has exactly one packet, and the ledger records it as `updated`.
3. **AC-012**: **Given** any published packet, **When** the reviewer reads its header, **Then** it states the feature version, the base commit and the head commit it was derived from, and the time it was generated.
4. **AC-013**: **Given** a PR description containing human-written text, the #17 Ballast section and the #27 merge-review summary, **When** the packet is published or updated, **Then** only the packet's own marked section changes; all other text, the title, labels, reviewers and draft or ready state stay unchanged.
5. **AC-014**: **Given** a human deleted the packet's marked section, **When** the next PR checkpoint runs, **Then** the packet is appended again as one marked section and nothing else changes.

---

### User Story 4 - API contract changes and UI states appear when the project provides them (Priority: P2)

A project that publishes an OpenAPI document configures where Ballast finds it; the packet then summarizes the API operations added, removed and changed against the PR base. A project that has named UI states configures them with the criterion they show and where their screenshots or results are; the packet links them beside those criteria.

**Why this priority**: API and UI impact are the changes a reviewer most needs to see without reading code, but only some projects have them. The packet must be useful without them.

**Independent Test**: Publish packets for three projects: one with neither configured, one with an OpenAPI artifact that changed against the base (an operation added, one removed, one with a changed response), and one with configured UI states, some with results and one without. Check each packet's API and UI sections.

**Acceptance Scenarios**:

1. **AC-015**: **Given** a project with no OpenAPI artifact and no UI states configured, **When** the packet is published, **Then** it contains no API or UI section beyond one line saying each is not configured.
2. **AC-016**: **Given** a project with a configured OpenAPI artifact that differs between the base and head commits, **When** the packet is published, **Then** it lists the operations added, removed and changed (by method and path), marks removed operations and removed or newly required request fields as potentially breaking, and states that this classification needs human review and is not an approval.
3. **AC-017**: **Given** a configured OpenAPI artifact that is unchanged, absent at one of the two commits, or cannot be read, **When** the packet is published, **Then** the API section says `no API change`, `added in this PR`, `removed in this PR` or `could not compare` with the reason, and the rest of the packet is still published.
4. **AC-018**: **Given** configured UI states mapped to acceptance criteria, **When** the packet is published, **Then** each state appears beside its criterion with a link to its screenshot or result for the head commit, and a state with no result for the head commit shows `missing`.

---

### User Story 5 - A packet failure never blocks the work or leaks a secret (Priority: P2)

When a source cannot be read, GitHub cannot be reached or the packet would be too long, the operator sees why, the run continues, and the next checkpoint retries.

**Why this priority**: The packet supports review; it is not the work. Like the Draft PR itself, its failure must be visible but harmless.

**Independent Test**: Simulate an unreadable source, a malformed manifest, GitHub unavailable, a packet over the size limit and agent-written text containing marker strings or fake approval claims. Check the outcome, the ledger and the PR text for each.

**Acceptance Scenarios**:

1. **AC-019**: **Given** the packet cannot be built or published (unreadable or malformed source, GitHub unreachable, no Draft PR yet), **When** a PR checkpoint runs, **Then** the run's workflow outcome and step state are unchanged, the ledger records `failed-retryable` or `pending` with the cause and one remedy, and the next checkpoint tries again.
2. **AC-020**: **Given** feature artifacts written by an agent that contain the packet's marker text, link syntax pointing elsewhere, or text claiming approval or verification, **When** the packet is published, **Then** that text appears only as quoted data, cannot end or forge the marked section, and cannot change any criterion's evidence state or decision label.
3. **AC-021**: **Given** a packet that would exceed the space GitHub allows in a PR description alongside the existing text, **When** it is published, **Then** the packet keeps its header, risk, counts, every non-`verified` criterion, every open finding and every provisional decision, shortens the rest, and names the path of the complete packet in the run archive (the archive is local to the operator's clone, so the PR cannot link it).
4. **AC-022**: **Given** any packet outcome, **When** the operator reads the output, ledger, archive and PR, **Then** no credential, token or authentication header appears in them.

---

### Edge Cases

- The spec has no acceptance-criterion IDs (an older or non-Spec-Kit feature): the packet says no criteria were found and links the spec; it does not invent criteria.
- The manifest names a criterion that no longer exists in the spec: the packet lists it under a separate "evidence for unknown criteria" line so the mismatch is visible.
- The acceptance-evidence manifest was written for an earlier spec version: every criterion it covers shows `stale` with the spec version the manifest names.
- CI is still running for the head commit: criteria whose only evidence is CI show `not run` with a link to the pending CI run; the packet is refreshed at the next checkpoint. Ballast does not wait for CI.
- The base branch advanced after the evidence was recorded but the head did not: the packet shows the new base commit and flags that the diff and API comparison use it; evidence bound to the unchanged head stays valid.
- A PR adopted from a human (#17 AC-007): the packet is added as its own marked section the same way.
- The PR is closed, merged or blocked (#17 `blocked-*` states): no packet is published, and the ledger says why.
- A run is in the human-gated mode: the packet is published the same way, with human approvals labeled as human.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The packet MUST be built and published only by trusted launcher code at the PR checkpoints defined by #17, after launcher trust verification and outside the agent sandbox. No agent gains GitHub write authority, credentials or a way to publish the packet itself.
- **FR-002**: The packet MUST be derived only from canonical sources: the feature's artifacts at the head commit (intent, spec, plan, tasks, decisions, review reports, acceptance-evidence manifest, run record), the run ledger, recorded check results, and CI results on GitHub for the head commit. It MUST NOT introduce a new authoritative store; deleting the packet and regenerating it from the same sources MUST reproduce it.
- **FR-003**: The packet MUST list every acceptance-criterion ID defined in the spec, exactly once and in spec order, with one evidence state: `verified`, `failed`, `not run`, `stale` or `missing`. Only evidence recorded as passing at the packet's head commit and for the current spec version MAY yield `verified`.
- **FR-004**: The packet MUST show the run's mode, the recorded risk level, each provisional decision and human approval labeled as recorded, each open review finding with severity, and the latest check results with what was skipped. It MUST show zero counts explicitly.
- **FR-005**: The packet MUST NOT state or imply that a criterion is verified, a decision approved or the PR acceptable, beyond what its sources record. It MUST state that it is a derived summary and that the linked sources are authoritative.
- **FR-006**: The packet MUST link each summary line to its source (a record held only in the local run ledger is named by run ID and event sequence, DEC-0001) and MUST include a sources section linking intent, spec, plan, tasks, decisions, each review report, the run record and the base-to-head diff, pinned to the head commit. Absent sources MUST be listed as `not present`.
- **FR-007**: The packet MUST state the feature version, base commit and head commit it was derived from and when it was generated. The feature version identifies the content of the feature artifacts the packet read.
- **FR-008**: The packet MUST live in one Ballast-marked section of the Draft PR description, separate from #17's section and #27's summary. Publishing MUST replace only that section, append it when absent, and leave all other PR content and state unchanged, consistent with #17 FR-007.
- **FR-009**: Publishing MUST be idempotent: the same sources and commits MUST produce byte-identical packet text, apart from the generation time, and in that case MUST NOT edit the PR. The ledger MUST record each checkpoint's packet outcome as `published`, `updated`, `unchanged`, `pending` or `failed-retryable`, with the commits when known and a reason when not published.
- **FR-010**: A project MAY configure an OpenAPI artifact location. When configured, the packet MUST compare the artifact at the base and head commits and list operations added, removed and changed by method and path, flag removals and newly required or removed request fields as potentially breaking, and state that the classification requires human review. When not configured, the packet MUST say so in one line.
- **FR-011**: A project MAY configure named UI states, each mapped to acceptance-criterion IDs and to where its screenshot or result is found for a given commit. When configured, the packet MUST link each state's result for the head commit beside its criteria, or show `missing`. Capturing screenshots or demos is out of scope (#22).
- **FR-012**: The OpenAPI and UI projections MUST NOT add a command Ballast executes or a tool it downloads. They read artifacts that the project's existing configured checks or CI already produce, or that are committed. If the plan finds this insufficient, the change is R2 and needs its own approval.
- **FR-013**: All text taken from agent-writable sources MUST be rendered as inert data: it MUST NOT be able to end or forge the marked section, inject links outside quoted text, or alter a state or label the packet computes.
- **FR-014**: When the packet would exceed the space available in the PR description, it MUST keep the header, risk, counts, every criterion not in `verified` state, and every open finding and provisional decision; it MUST shorten the remainder and name the complete packet kept in the run archive (R15: the archive is local, so the PR cannot link it).
- **FR-015**: A packet failure MUST NOT change the workflow's exit status, step state or the #17 PR checkpoint outcome, and MUST NOT discard or block feature work. The next checkpoint MUST retry.
- **FR-016**: The packet, its archive copy, the ledger and output MUST NOT contain credentials or authentication material.
- **FR-017**: Packet generation MUST be covered by deterministic tests that need no network, covering every evidence state, missing and malformed sources, unknown criteria in the manifest, human and provisional labels, idempotent and changed republishing, a deleted section, a human-edited description, OpenAPI configured and not, UI states configured and not, oversize packets, hostile agent-written text and GitHub failures.
- **FR-018**: User-facing documentation MUST describe the packet, its evidence states, how a project configures the OpenAPI artifact and UI states, and that the packet is a derived summary, not an approval.

### Key Entities

- **Acceptance packet**: the derived review summary for one feature at one checkpoint. Bound to a feature version, base commit and head commit; has a generation time, an outcome in the ledger and a complete copy in the run archive.
- **Criterion evidence entry**: one acceptance-criterion ID with its spec title and link, its evidence state, the named verification items and the check or CI result each relies on, with the commit and spec version that result belongs to.
- **Source link**: a link to a canonical artifact or record pinned to the head commit, or a `not present` marker.
- **API change summary**: the operations added, removed and changed between base and head for the configured OpenAPI artifact, with potentially breaking items flagged.
- **UI state link**: a configured named state, the criteria it shows, and its result for the head commit or `missing`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For every feature PR in the pilot, a reviewer can tell from the packet alone, without opening the diff, which acceptance criteria are verified at the head commit and which are not; spot checks find zero criteria shown as `verified` whose evidence did not pass at that commit.
- **SC-002**: 100% of a feature's spec criteria appear in its packet, and 100% of links in the sources section resolve to the named artifact at the packet's head commit.
- **SC-003**: Across repeated checkpoints on the pilot PRs, each PR carries exactly one packet, and checkpoints with no source change cause zero PR description edits made by the packet.
- **SC-004**: At the merge review, the operator can answer what changed, find failed or missing evidence, provisional decisions and open findings, and locate any canonical source within one click from the packet.
- **SC-005**: No packet failure alters a run's workflow result, and every situation listed in FR-017 is covered by a passing deterministic test.

## Assumptions

- The Draft PR exists and is maintained by #17; this feature publishes at #17's checkpoints and reuses its PR identity, exclusion and failure handling rather than adding its own.
- The #27 merge-review summary stays where it is. The packet links the run record and reuses its decisions, findings and checks; consolidating the two sections is left to a later change (Autonomous integration beyond #27 is #21).
- The existing acceptance-evidence manifest, which names the tests proving each criterion for a given spec version, is the source of criterion-to-evidence mapping. A criterion it does not cover is `missing`; the packet does not infer evidence from test names or task text.
- A criterion mapped to several tests whose results differ takes one state. It is `verified` only when every mapped test passed at the head commit for the current manifest and spec version, matching the existing ledger rule that an AC passes only when all its mapped methods pass for the same snapshot and manifest version. Otherwise it takes the first applicable state in the order `failed`, `stale`, `not run`, and the packet lists each test's own result beside it. This is an agent-provisional default: it only changes how existing results are rendered and can be revised without migration.
- "Feature SHA" in the Issue is read as the feature version: an identifier of the feature artifacts' content at the head commit, so a spec change makes earlier evidence stale even when the head commit moves for other reasons.
- OpenAPI comparison works on the configured artifact as a document; it needs no new dependency, consistent with the standard-library-only rule for workflow tools. A richer comparison tool may run in the project's own CI and be linked as a UI-style result.
- The packet is Markdown in the PR description and run archive. No dashboard, web view or new status database is added.
- The qualified environment is the 1.0 environment: GitHub, Linux, a systemd user session and an authenticated GitHub CLI on the operator's machine.
