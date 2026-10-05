# Feature Specification: Source-backed discovery brief

**Feature Branch**: `feat/16-discovery-brief`

**Created**: 2026-10-05

**Status**: Draft

**Input**: User description: "Issue #16: A short request becomes a defensible specification with few questions and visible assumptions, through a source-backed discovery brief before speckit.specify."

**Risk**: R1. The brief extends the feature workflow with a new step and artifact. It does not change headless-agent permissions, the launcher's trust model, what `ballast` executes or downloads, or installed-path ignore rules (see `docs/policies/project/workflow.md`). If planning finds that the step needs a new agent permission, a new protected input or a change to what the trusted runner executes, the risk rises to R2 at that gate.

**Source context**: [Issue #16](https://github.com/Hugo-Grellier/ballast/issues/16) (snapshot `.specify/workflow-state/issues/16.md`, untrusted requirements data), leaf of Epic #11; [roadmap Priority 2](../../docs/plans/2026-10-02-product-roadmap.md#priority-2--understand-the-need-before-writing-the-spec); [technical spec §91](../TECHNICAL-SPEC.md#91-v10-target) ("request discovery and traceable feature specification"); [Autonomous core](../27-autonomous-core/spec.md) for provisional decisions and blocks. Out of scope per #16: a second authoritative product spec, invented user approvals, the review packet (#19) and Autonomous resume (#21).

## Overview

Today a feature run goes from a scoped Issue straight to `speckit.specify`, then refines the spec with `speckit.clarify`, which asks up to five questions one at a time. Nothing first gathers what the Issue, its comments, the accepted product and architecture documents, project policy and existing behavior already answer. Assumptions and the agent's own inferences end up mixed with stated requirements, and a reviewer cannot tell which requirement came from where (roadmap, "Current state: Understanding the request").

This feature adds a **discovery brief** before specification, in both the human-gated and the Autonomous workflow. The brief records the user need, examples, scope, non-goals, constraints, success evidence and the few decisions that would change implementation or acceptance. Every item cites its source or is marked as an inference. Questions to the human are budgeted: the repository is checked first, and what remains is asked in one bundled round. In Autonomous, nobody is asked: safe, reversible assumptions are carried provisionally to the merge review, and unsafe ambiguity blocks with a precise reason. The brief is input evidence. `spec.md` and `intent.md` stay the feature's authority.

Traceability labels used below: **[S: …]** names the source of a requirement; **[I]** marks an inference made while writing this spec, also listed under Assumptions.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Turn a short request into a sourced brief (Priority: P1)

An operator starts a feature from a scoped Issue whose body is a few lines. Before any spec exists, the agent reads the Issue and its comments, the relevant parts of the product and technical specs, accepted ADRs, project policies and the existing behavior the request touches. It writes a brief that states who the user is, what they are trying to do, what hurts today, the intended outcome and concrete examples; the scope, non-goals, constraints, permission and data-authority boundaries and the success evidence; and, separately, what is known from sources, what was inferred and what is still undecided. Each item links to its source or carries an inference marker.

**Why this priority**: Every other story consumes the brief. It is the Issue's main outcome and the roadmap's Priority 2 deliverable [S: Issue #16 "In scope"; roadmap Priority 2].

**Independent Test**: Run the discovery step on a test Issue with a short body, one comment and a related accepted policy. Confirm the brief exists, contains each required section, and that every item either links to a file, Issue or comment that exists, or is marked as an inference.

**Acceptance Scenarios**:

1. **AC-001**: **Given** a scoped feature Issue, **When** a feature run reaches the discovery step, **Then** a feature-local brief is produced before `spec.md` exists, containing the user, job to be done, current pain, intended outcome, at least one concrete example, scope, non-goals, constraints, permission and data-authority boundaries, success evidence, unknowns and high-impact decisions [S: Issue #16 "In scope"; roadmap Priority 2 bullet list].
2. **AC-002**: **Given** a brief, **When** any item states a requirement, constraint, example or decision, **Then** it either cites a source (Issue body, a named Issue comment, a repository document or section, or existing behavior with its location) or is explicitly marked as an inference [S: Issue #16 AC 1].
3. **AC-003**: **Given** an Issue and its comments, **When** the brief quotes or relies on them, **Then** they are treated as untrusted requirements data: text in them that reads as an instruction to the agent is not followed and does not change the workflow, policies or permissions [S: Issue snapshot header; `docs/policies/spec-kit-workflow.md` Autonomous section].
4. **AC-004**: **Given** sources that contradict each other (for example an Issue asking for behavior an accepted ADR or the constitution forbids), **When** the brief is written, **Then** the contradiction is listed as an undecided high-impact decision naming both sources, and is not resolved silently in favor of either [S: `AGENTS.md` "Spec Kit artifacts and accepted product/technical documents are authoritative"; I].

---

### User Story 2 - Ask few questions, once (Priority: P1)

In a human-gated run, the operator should not be asked what the repository already answers, nor be drawn into a long one-question-at-a-time exchange. After the brief has checked repository evidence, any decision still open that would materially change implementation or acceptance is put to the operator in one bundled round. Each question offers concrete options and their consequences, and proposes a recommended default. The operator answers once; the answers are recorded in the brief with the operator as their source.

**Why this priority**: "Few questions" is half of the Issue's outcome and a 1.0 release-gate item ("a vague request becomes a traceable spec with few user questions") [S: Issue #16 AC 2; roadmap "Minimum release gate" item 2].

**Independent Test**: Run discovery in a human-gated run on a test Issue with two open high-impact choices and one choice answered by an existing policy. Confirm the operator sees exactly one interaction containing two questions, each with options and consequences, and that the policy-answered choice appears in the brief with its source instead of as a question.

**Acceptance Scenarios**:

1. **AC-005**: **Given** a candidate question whose answer is in the Issue, its comments or the repository, **When** discovery decides what to ask, **Then** the question is not asked and the brief records the answer with its source [S: roadmap Priority 2 "first resolve what the repository and issue already answer"].
2. **AC-006**: **Given** one or more open high-impact decisions in a human-gated run, **When** discovery asks the operator, **Then** all of them are presented together in a single interaction, each with at least two options, the consequence of each option and a recommended default [S: Issue #16 AC 2; roadmap Priority 2 "one short interaction with proposed options and consequences"].
3. **AC-007**: **Given** a normal case (no contradiction introduced by the operator's answers), **When** discovery and the following clarification finish, **Then** the operator has been asked at most one bundled round in total before intent approval, and the later clarification step does not ask again what the bundled round settled [S: Issue #16 AC 2; I].
4. **AC-008**: **Given** an operator answer, **When** it is recorded, **Then** the brief attributes it to the operator and keeps it distinct from agent inferences; an unanswered question stays open and is never recorded as answered [S: Issue #16 "Out of scope: inventing user approvals"].
5. **AC-009**: **Given** a run with no open high-impact decision, **When** discovery finishes, **Then** no question is asked [I].

---

### User Story 3 - Decide or block without asking in Autonomous (Priority: P1)

In an Autonomous run nobody answers questions. When the brief leaves a decision open, the agent adopts a default only if it is low-risk and reversible, records it visibly as an agent-provisional assumption with its basis, and carries it into the Draft PR for the merge review. When no safe default exists, or sources contradict each other on behavior, scope, data authority or a security boundary, the run stops with a precise block naming the decision, the options and their consequences, and how to recover.

**Why this priority**: Autonomous is a required 1.0 mode, and an unattended run must neither guess on unsafe ground nor stall on a prompt [S: Issue #16 AC 3; technical spec §91; Autonomous core AC-005].

**Independent Test**: Run discovery in an Autonomous test run on two Issues: one whose only gap has a safe reversible default, one whose gap chooses between materially different product behaviors. Confirm the first continues with a recorded provisional assumption visible in the run record, and the second stops with a block naming that decision and at least two options, with no prompt in either run.

**Acceptance Scenarios**:

1. **AC-010**: **Given** an Autonomous run and an open decision with a low-risk, reversible default, **When** discovery finishes, **Then** the default is adopted, recorded as an agent-provisional assumption with its basis and evidence, and appears in the run record that the Draft PR exposes for merge review [S: Issue #16 AC 3; roadmap Priority 2 "carries provisional choices into the Draft PR"].
2. **AC-011**: **Given** an Autonomous run and an open decision with no safe, reversible default, or a contradiction about product behavior, scope, data authority, a security boundary or accepted architecture, **When** discovery finishes, **Then** the run blocks with a reason that names the decision, cites the conflicting or missing sources, lists at least two options with consequences and states the recovery path [S: Issue #16 AC 3; `AGENTS.md` human-approval classes; Autonomous core block contract].
3. **AC-012**: **Given** an Autonomous run, **When** discovery runs, **Then** it never prompts the operator or waits for input [S: technical spec §91 "requests no human approval until merge"].
4. **AC-013**: **Given** any brief, spec, record or PR text produced from discovery, **When** it describes a choice made by an agent, **Then** it labels the choice as an inference or agent-provisional and never states or implies human approval [S: Issue #16 "Out of scope: inventing user approvals"; roadmap Priority 2 "must not turn an inference into a claimed user approval"].

---

### User Story 4 - The brief feeds the spec without competing with it (Priority: P1)

The spec author writes `spec.md` from the brief. Each major requirement and each acceptance criterion links back to the brief item, source or marked inference it rests on. A deterministic check refuses a spec whose acceptance criteria lack a source or inference marker. After intent is recorded, only `spec.md` and `intent.md` govern; the brief is kept as evidence and cannot override them.

**Why this priority**: Without traceability the brief is just more prose, and without a clear authority rule it becomes a second source of truth, which the project forbids [S: Issue #16 AC 1 and AC 4; `AGENTS.md` "never add a second source of truth"].

**Independent Test**: Validate two specs written from the same brief: one where every acceptance criterion carries a source or inference marker, and one where a single criterion has neither. Confirm the first passes and the second fails with a message naming that criterion. Then edit the brief after intent is recorded and confirm the recorded intent stays valid and the spec is unchanged.

**Acceptance Scenarios**:

1. **AC-014**: **Given** a brief, **When** `spec.md` is written, **Then** each functional requirement and acceptance criterion cites a source, a brief item, or an explicit inference marker [S: Issue #16 AC 1; roadmap Priority 2 "links back to the source of each major requirement"].
2. **AC-015**: **Given** a `spec.md` in which an acceptance criterion has neither a source nor an inference marker, **When** the spec is validated after specification, **Then** validation fails and names the untraced criterion [S: roadmap Priority 2 "Add checks that every acceptance criterion maps to an observed need or an explicit assumption"].
3. **AC-016**: **Given** the Issue's acceptance criteria, **When** the spec is validated, **Then** each one is covered by a spec acceptance criterion or recorded as a deliberate non-goal; an omission fails validation [S: `speckit.ballast.clarify` step 1; I].
4. **AC-017**: **Given** recorded intent, **When** the brief and `spec.md` disagree, **Then** `spec.md` and `intent.md` govern, the brief is not used as a requirement source for planning, tasks or review, and changing the brief alone neither invalidates nor changes recorded intent [S: Issue #16 AC 4].
5. **AC-018**: **Given** a brief, **When** it is read, **Then** it states that it is input evidence and not the feature's authority, and points to `spec.md` and `intent.md` [S: Issue #16 AC 4; roadmap Priority 2 "The brief is input evidence, not a second product authority"].
6. **AC-019**: **Given** a spec written from a brief, **When** it is validated, **Then** it also covers the relevant failure, permission and edge cases identified in the brief, or records why one does not apply [S: roadmap Priority 2 "the spec covers the relevant failure, permission, and edge cases"].

---

### User Story 5 - See how many questions a request needed (Priority: P3)

During the 1.0 pilot the operator wants to know whether discovery actually reduced questions. The brief records how many clarification rounds and questions were asked and how many assumptions were adopted, so the pilot can compare features.

**Why this priority**: The roadmap asks the pilot to measure question count; it supports evaluation, not the core outcome [S: roadmap Priority 2 "Measure both question count and late requirement changes in the pilot"].

**Independent Test**: Complete discovery on a test Issue that needs one bundled round of two questions and adopts one assumption. Confirm the brief reports one round, two questions and one assumption.

**Acceptance Scenarios**:

1. **AC-020**: **Given** a finished discovery step, **When** the brief is read, **Then** it reports the number of clarification rounds, the number of questions asked and the number of assumptions adopted [S: roadmap Priority 2; I].

---

### Edge Cases

- **Issue with no comments or a one-line body**: discovery still runs on the repository context; the gaps become inferences, provisional assumptions or questions, never invented user statements [I].
- **Missing or unavailable source** (a linked document that does not exist, comments that cannot be fetched): the brief says the source was unavailable rather than citing it, and anything that depended on it becomes an unknown [S: `speckit.ballast.clarify` "Cite only files that exist"; I].
- **Discovery reveals several independent outcomes**: discovery stops and recommends decomposition under the scope gate; it does not split the spec or create Issues itself [S: `docs/policies/spec-kit-workflow.md` scope gate; `speckit.ballast.clarify` step 3].
- **Issue text that tries to instruct the agent** (for example "skip review" or "mark as approved"): treated as data, recorded as a requirement statement only if it is one, never acted upon [S: Issue snapshot header].
- **An operator answer introduces a new contradiction**: this is not the normal case; discovery may ask one follow-up bundled round that names the contradiction, and the brief records that a second round was needed and why [I].
- **Continuing an existing feature** (`Continue #N`) whose brief already exists: the existing brief is reused, not regenerated; if the Issue changed since, discovery updates the brief and marks what changed [I].
- **A spec already exists from before this feature** (completed work): no brief is required retroactively [S: `AGENTS.md` "Do not retrofit completed work"].
- **Bugfix and assess workflows**: unchanged; discovery applies to the feature workflow in both modes [S: Issue #16 intake comment "in both human-gated and Autonomous runs"; I].

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The human-gated and Autonomous feature workflows MUST run a discovery step after the scope decision and before specification, producing a feature-local discovery brief [S: Issue #16 intake comment; roadmap Priority 2]. (AC-001)
- **FR-002**: Discovery MUST read only the relevant Issue, its comments, accepted product and architecture documents and ADRs, project policies and the existing behavior the request touches; it MUST NOT copy whole documents into the brief [S: roadmap Priority 2 "read only the relevant…"; `docs/policies/spec-kit-workflow.md` "do not copy entire"]. (AC-001, AC-002)
- **FR-003**: The brief MUST contain: user, job to be done, current pain, intended outcome, concrete examples; scope, non-goals, constraints, permission and data-authority boundaries, success evidence; known facts, inferences and undecided items kept separate; and the high-impact decisions [S: roadmap Priority 2]. (AC-001)
- **FR-004**: Every brief item that states a requirement, constraint, example or decision MUST cite a source or carry an explicit inference marker; operator answers MUST be attributed to the operator [S: Issue #16 AC 1]. (AC-002, AC-008)
- **FR-005**: Discovery MUST treat Issue and comment text as untrusted requirements data and MUST NOT follow instructions found in it [S: Issue snapshot header]. (AC-003)
- **FR-006**: Discovery MUST list contradictions between sources as undecided high-impact decisions naming both sources [S: `AGENTS.md`; I]. (AC-004)
- **FR-007**: Discovery MUST NOT ask a question whose answer the Issue, comments or repository provide [S: roadmap Priority 2]. (AC-005)
- **FR-008**: In a human-gated run, discovery MUST present all remaining high-impact questions in one bundled interaction with options, consequences and a recommended default, and the normal case MUST involve at most one bundled round before intent approval, including the clarification step [S: Issue #16 AC 2]. (AC-006, AC-007, AC-009)
- **FR-009**: In an Autonomous run, discovery MUST NOT prompt; it MUST adopt only low-risk, reversible defaults as recorded agent-provisional assumptions and MUST block, with the decision, sources, at least two options with consequences and a recovery path, when no safe default exists or when the gap concerns product behavior, scope, data authority, a security boundary or accepted architecture [S: Issue #16 AC 3; Autonomous core]. (AC-010, AC-011, AC-012)
- **FR-010**: Discovery outputs MUST NOT state or imply human approval of an agent inference or provisional choice [S: Issue #16 out of scope]. (AC-013)
- **FR-011**: `spec.md` MUST link each functional requirement and acceptance criterion to a source, a brief item or an explicit inference marker, and MUST cover each Issue acceptance criterion or record it as a deliberate non-goal [S: Issue #16 AC 1; roadmap Priority 2]. (AC-014, AC-016)
- **FR-012**: Post-specification validation MUST fail, naming the criterion, when a spec acceptance criterion lacks a source or inference marker, or an Issue acceptance criterion is neither covered nor a recorded non-goal [S: roadmap Priority 2 "Add checks"]. (AC-015, AC-016)
- **FR-013**: The brief MUST declare itself non-authoritative and point to `spec.md` and `intent.md`; recorded intent MUST continue to depend only on `spec.md`, and later steps MUST NOT treat the brief as a requirement source [S: Issue #16 AC 4]. (AC-017, AC-018)
- **FR-014**: The spec MUST cover the failure, permission and edge cases the brief identifies, or state why one does not apply [S: roadmap Priority 2]. (AC-019)
- **FR-015**: The brief MUST record the number of clarification rounds, questions asked and assumptions adopted [S: roadmap Priority 2]. (AC-020)
- **FR-016**: Discovery MUST NOT grant the agent any permission, file access or network access beyond what the specification step already has, and MUST NOT write outside the feature directory and the Autonomous drafts area [S: Issue #16 "Risk: R1 … without changing agent authority"; `AGENTS.md` invariants].
- **FR-017**: When discovery finds several independent outcomes, it MUST stop and recommend decomposition, without splitting the spec or creating Issues [S: scope gate]. 

### Key Entities

- **Discovery brief**: feature-local, non-authoritative evidence written before the spec. Holds the need, examples, scope, non-goals, constraints, success evidence, unknowns, high-impact decisions and question metrics. Each item has a provenance.
- **Provenance**: the origin of a brief or spec item: a cited source (Issue body, named comment, repository document and section, existing behavior and its location), an operator answer, an agent inference, or an agent-provisional assumption.
- **High-impact decision**: an open choice that would materially change implementation or acceptance, with options, consequences, a recommended default and its resolution status (answered by the operator, provisionally assumed, open, or blocking).
- **Clarification round**: one bundled interaction with the operator; counted in the brief.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In specs produced through discovery, 100% of acceptance criteria and functional requirements carry a source or an explicit inference marker, and the validation check enforces it for acceptance criteria [S: Issue #16 AC 1].
- **SC-002**: In the normal case, the operator answers at most one bundled clarification round per feature before intent approval, measured across the 1.0 pilot features [S: Issue #16 AC 2; roadmap Priority 2 exit evidence].
- **SC-003**: Autonomous runs that pass through discovery show zero operator prompts; every adopted default appears in the run record, and every block names the decision and at least two options [S: Issue #16 AC 3].
- **SC-004**: A reviewer can trace each main requirement of a pilot spec to a user statement, existing policy or marked inference in under 5 minutes without reading the conversation transcript [S: roadmap Priority 2 exit evidence; I for the time bound].
- **SC-005**: Zero cases in which a brief, spec, record or PR presents an agent inference or provisional choice as a human approval [S: Issue #16 out of scope].
- **SC-006**: After intent is recorded, editing the brief never changes which spec version the intent approves [S: Issue #16 AC 4].

## Assumptions

- [I] The brief lives in the feature directory alongside `spec.md` and is committed with the feature's other Spec Kit artifacts; the plan chooses its exact name and layout.
- [I] "Normal case" means no contradiction is introduced by the operator's own answers; a follow-up round is allowed only in that exception and is counted.
- [I] The existing human-gated `speckit.clarify` step stays, but it relies on the brief and does not re-ask settled questions; its five-question, one-at-a-time mode is not the normal path once a brief exists.
- [I] Discovery is delivered as a reusable agent command plus deterministic checks, following the existing pattern of confined agent steps followed by trusted validation (roadmap Priority 2 "implemented as a reusable skill/agent workflow with deterministic checks around its output").
- [I] The traceability check covers acceptance criteria deterministically; coverage of functional requirements and of failure/permission/edge cases is checked by review rather than by a parser.
- [I] Measuring late requirement changes is pilot work outside this feature; this feature only records question and assumption counts.
- [I] Bugfix and assess workflows are unchanged.
- [I] The traceability and Issue-coverage validation (FR-012, AC-015, AC-016) applies only to features that have a discovery brief. Existing specs written before this feature (for example `specs/12-cli-install-doctor`, `specs/17-draft-pr`, `specs/27-autonomous-core`) carry no source or inference markers and are not checked or retrofitted (agent-provisional clarification default; `docs/policies/spec-kit-workflow.md` "Completed work and existing issues are not retrofitted").
- Projects consume the discovery step through `ballast setup` like other installed workflow assets; no project-owned file needs editing [S: `AGENTS.md` invariants].
