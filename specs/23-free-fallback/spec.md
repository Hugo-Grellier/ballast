# Feature Specification: Qualify one zero-cost provider fallback

**Feature Branch**: `feat/23-free-fallback`

**Created**: 2026-10-06

**Status**: Draft

**Input**: User description: "Issue #23: when Claude/Codex is unavailable or quota exhausted, one compatible free backend completes an eligible step within policy. Candidate available on the operator host: Ollama (local, CPU-only, model qwen3:4b) through the Codex CLI --oss --local-provider ollama mode."

**Risk**: R2 — adds an execution backend and touches the headless-agent permission model, the privacy boundary for repository content and what `ballast` executes. In this Autonomous run every intermediate decision is agent-provisional; merging the PR is the single human approval.

**Evidence**: [discovery.md](discovery.md) (input evidence only; this spec is the authority).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A quota or availability failure falls back to the local free backend (Priority: P1)

An operator runs feature work through `ballast run` on their own host. A headless step fails because the primary agent reports its usage limit or cannot be reached. The operator has opted into the local fallback, so the trusted wrapper confirms the failed attempt left nothing behind, starts the same step once on the local zero-cost backend, and the step completes. The run keeps moving without paying and without the agent seeing or doing more than before.

**Why this priority**: It is the Issue's main outcome; without it a quota failure stops the run.

**Independent Test**: Simulate a quota failure, then an availability failure, of the primary agent on an eligible step with the fallback enabled; the step completes on the fallback backend under the same confinement.

**Acceptance Scenarios**:

1. **AC-001**: **Given** the operator has enabled the fallback and the local backend passes every eligibility check, **When** a headless step's primary attempt fails with a recognized quota-exhausted signal and left the worktree, drafts and protected state unchanged, **Then** the wrapper selects the local free backend, runs the same step once on it, and the step completes. [S: IAC-1] [P: D-04] [P: D-06]
2. **AC-002**: **Given** the same setup, **When** the primary attempt fails because the agent CLI or its provider is unavailable, **Then** the fallback is selected and completes the step in the same way. [S: IAC-1] [S: Issue #23 body]
3. **AC-003**: **Given** the fallback is not enabled (the default), **When** a primary attempt fails on quota or availability, **Then** no fallback runs and the step fails as it does today. [S: IAC-4] [P: D-05]
4. **AC-004**: **Given** the fallback runs, **Then** it uses the same confinement, environment scrubbing, protected-input checks, workspace-write sandbox with tool network off and no extra writable roots as a primary step, and no permission or sandbox bypass option reaches the agent CLI. [S: IAC-2] [B: D-02] [S: tools/spec_workflow/agent.py]

---

### User Story 2 - An ineligible fallback is refused before any content leaves the wrapper (Priority: P1)

When free status, privacy, capability or permissions cannot be established, the fallback is refused before any prompt or repository content is sent, and the step blocks with a reason the operator can read.

**Why this priority**: The fallback is only acceptable if it can never send content to a paid, remote or more permissive backend; this is the R2 boundary.

**Independent Test**: For each refusal cause, run the fallback path against a backend stub that records every request; the stub receives nothing and the step reports the cause.

**Acceptance Scenarios**:

1. **AC-005**: **Given** the operator-named model is not installed locally, or its free status cannot be established, **When** a fallback would be selected, **Then** it is refused as unknown free status and nothing is sent to the backend. [S: IAC-2] [P: D-07]
2. **AC-006**: **Given** the model is a cloud-hosted model or the endpoint is not on the loopback interface, **When** a fallback would be selected, **Then** it is refused as a privacy exclusion and nothing is sent. [S: IAC-2] [B: D-03] [P: D-07]
3. **AC-007**: **Given** the agent CLI lacks the local-provider mode, the model server is not running, or the CLI's own sandbox cannot start inside Ballast's confinement on this host, **When** a fallback would be selected, **Then** it is refused as an incompatible capability, neither sandbox is loosened, and nothing is sent. [S: IAC-2] [B: D-02] [P: D-07]
4. **AC-008**: **Given** the fallback invocation would need any permission, writable root, network access or bypass option the primary step does not have, **When** a fallback would be selected, **Then** it is refused as a permission mismatch and nothing is sent. [S: IAC-2] [B: D-02]
5. **AC-009**: **Given** the primary attempt changed the worktree, drafts or protected state before failing, **When** the failure is otherwise recoverable, **Then** the fallback is refused rather than replaying a partial mutation. [S: IAC-3] [P: D-04]
6. **AC-010**: **Given** the primary attempt failed for a non-recoverable reason (a blocked status, tamper, an exhausted run limit, a refused draft, or an unrecognized error), **Then** the fallback is never triggered. [S: IAC-1] [I]

---

### User Story 3 - Every attempt is visible in the existing run ledger (Priority: P2)

The operator and reviewers can see, from the run ledger alone, that a step fell back, why, and what happened, without any new store or account detail.

**Why this priority**: Evidence is required for review and for the merge approval, but it builds on Stories 1 and 2.

**Independent Test**: After a simulated fallback, a refused fallback and a failed fallback, read the ledger and check each attempt, its reason and outcome; re-run a retried step and check the worktree has no duplicate effect.

**Acceptance Scenarios**:

1. **AC-011**: **Given** a step fell back, **Then** the ledger records the failed primary attempt with its normalized cause, the fallback selection with its reason, the fallback attempt's provider, model and outcome, and usage when the backend reports it. [S: IAC-3] [S: tools/spec_workflow/ledger-schema.md]
2. **AC-012**: **Given** a fallback was refused, **Then** the ledger records the refusal and its cause (unknown free status, privacy exclusion, incompatible capability, permission mismatch or a changed worktree). [S: IAC-3] [S: IAC-2]
3. **AC-013**: **Given** the fallback attempt itself fails, **Then** no further fallback or retry runs, the step fails, and both attempts are in the ledger. [S: IAC-3] [P: D-06]
4. **AC-014**: **Given** a step retried through the fallback, **Then** the step's outputs appear once, with no duplicated file change, draft or ledger effect. [S: IAC-3] [P: D-04]
5. **AC-015**: **Given** the run's agent-step limit would be exceeded by the fallback attempt, **Then** the fallback does not start and the run stops with the existing limit refusal; every fallback attempt counts as an agent step. [S: IAC-3] [P: D-06]
6. **AC-016**: **Given** a review step was completed by the fallback, **Then** the recorded reviewer provider and model are the fallback's, and the PR does not claim cross-provider review on that basis. [S: docs/policies/model-routing.md] [I]
7. **AC-017**: **Given** any fallback ledger entry, **Then** it holds no account, quota or credential detail, and the ledger schema version is unchanged because new kinds or values are additive. [S: tools/spec_workflow/ledger-schema.md] [S: docs/policies/model-routing.md]

---

### User Story 4 - The operator opts in to a backend chosen from evidence (Priority: P2)

The operator turns the fallback on deliberately, for their host, knowing why this backend was chosen, how it is configured and how to turn it off.

**Why this priority**: The Issue requires the candidate to be justified, and the opt-in to be explicit and reversible.

**Independent Test**: Read the evaluation record and documentation; enable and then disable the fallback on the operator's host following the documented steps.

**Acceptance Scenarios**:

1. **AC-018**: **Given** the feature is delivered, **Then** an evaluation record names the candidate (the local model server driven by the agent CLI's local-provider mode), the alternatives considered and why they were rejected, and the evidence of a pilot run on the operator's host, including whether the agent CLI's sandbox nests inside Ballast's confinement there. [S: IAC-4] [B: D-01]
2. **AC-019**: **Given** the documentation, **Then** it states how the operator enables the fallback and names the model, what each refusal means, and the exit path that turns it off. [S: IAC-4] [P: D-05]
3. **AC-020**: **Given** an agent step runs, **Then** the agent cannot enable, configure or widen the fallback; the setting lives outside agent reach and the run record shows whether it was on. [S: IAC-4] [S: AGENTS.md#invariants] [P: D-05]
4. **AC-021**: **Given** a Chat run's interactive step hits a quota or availability failure, **Then** no automatic fallback runs; the operator chooses what to do. [S: IAC-1] [P: D-08]

---

### Edge Cases

- The agent CLI's sandbox does not nest inside Ballast's confinement on the host (the condition the run already handles by giving both roles to Claude): the fallback is refused as an incompatible capability (AC-007).
- The model server is not running or the named model is not pulled: refused before sending content (AC-005, AC-007).
- A model name that runs on the provider's cloud: refused as a privacy exclusion (AC-006).
- The primary attempt edited files or drafts before hitting its quota: refused, never replayed (AC-009).
- The fallback attempt fails or times out: no further attempt; both attempts recorded (AC-013).
- An unrecognized primary error: treated as non-recoverable (AC-010).
- The step limit is reached: existing limit refusal (AC-015).
- The candidate fails its pilot on the qualified host: recorded as a discovery in `decisions.md`, never a silent switch to another backend.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The fallback MUST be off by default and enabled only by an explicit operator-side setting that names the local model, read by the trusted launcher and recorded in the run record. [P: D-05]
- **FR-002**: The system MUST normalize a primary attempt's failure into a fixed cause set; only quota exhausted and provider or CLI unavailable are recoverable, and any unrecognized failure is non-recoverable. [S: Issue #23 body] [I]
- **FR-003**: The system MUST consider the fallback only for a headless step of a human-gated or Autonomous run whose primary attempt failed for a recoverable cause and left the worktree, drafts and protected state unchanged. [P: D-04] [P: D-08]
- **FR-004**: Before any prompt or repository content is sent, the system MUST establish by runtime checks that the endpoint is loopback, the named model is installed locally and is not a cloud model, the agent CLI supports the local-provider mode, and its sandbox starts inside Ballast's confinement; any failed or unknown check MUST refuse the fallback. [S: IAC-2] [B: D-03] [P: D-07]
- **FR-005**: The fallback MUST run with the same confinement, environment scrubbing, protected-input checks and agent CLI permission model as a primary step; no bypass option, extra writable root or tool network access may be added, and neither sandbox may be loosened to make the fallback run. [B: D-02] [S: AGENTS.md#invariants]
- **FR-006**: The system MUST make at most one fallback attempt per step, after one failed primary attempt, with no further retry; every attempt MUST count against the run's agent-step limit. [P: D-06]
- **FR-007**: The system MUST record each primary and fallback attempt, the selection or refusal reason, the outcome and usage when available in the existing run ledger, extending its enumerations additively and storing no account, quota or credential detail. [S: IAC-3] [S: tools/spec_workflow/ledger-schema.md]
- **FR-008**: A refused fallback MUST block the step with a reason the operator can read; the system MUST never route to a paid or metered backend. [S: IAC-2] [S: specs/TECHNICAL-SPEC.md#65-paid-api-guard]
- **FR-009**: The fallback MUST NOT rely on a shipped list of currently free models; eligibility comes from the operator-named model and runtime checks. [S: Issue #23 body] [P: D-07]
- **FR-010**: The feature MUST ship an evaluation record of the candidate and alternatives with pilot evidence from the operator's host, and documentation of configuration, refusal causes and how to turn the fallback off. [S: IAC-4] [B: D-01]
- **FR-011**: Workflow tools MUST stay standard-library-only and run under `python3 -I -S`. [S: AGENTS.md#invariants]

### Key Entities

- **Fallback setting**: the operator's opt-in (on/off) and the named local model; trusted input outside agent reach.
- **Attempt**: one execution of a step by a provider and model, with its normalized cause and outcome.
- **Fallback decision**: selected or refused, with the reason (recoverable cause, or one of the refusal causes).
- **Evaluation record**: candidate, alternatives, pilot evidence on the operator's host, decision.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In tests, 100% of simulated quota and availability failures on an eligible step with the fallback enabled complete the step through the fallback.
- **SC-002**: In tests, each of the four refusal causes and the changed-worktree case sends zero requests to the backend.
- **SC-003**: Every fallback-related attempt and decision in a test run appears in the ledger; a retried step shows zero duplicated effects.
- **SC-004**: An operator can enable and disable the fallback on their host by following the documentation alone, and a pilot run on that host completes or is refused with a recorded cause.
- **SC-005**: No step ever makes more than two attempts (one primary, one fallback).

## Non-goals

- Broad multi-provider routing or a general adapter layer.
- Paid overflow or any metered API.
- A hard-coded permanent list of currently free models.
- Replaying a partially executed mutation.
- Provider account sign-up.
- A direct-API execution harness.
- Fallback inside a Chat run's interactive steps.

## Assumptions

- [P: D-04] Eligibility is decided from evidence that the primary attempt changed nothing, not from a list of step types.
- [P: D-05] The opt-in is an operator-side setting, off by default, recorded in the run record; a `ballast.toml` section could be added later.
- [P: D-06] One fallback attempt per step; the existing step limit stays authoritative.
- [P: D-07] Capability and privacy come from runtime checks on the operator-named model; a wrong check can block but never send content.
- [P: D-08] Only headless steps of human-gated and Autonomous runs fall back.
- [I] Recoverable failures are recognized from the agent CLI's exit status and output against a fixed set of quota and availability signatures.
- [I] A non-recoverable failure never triggers the fallback.
- [I] A review completed by the fallback is recorded as such and does not count as cross-provider review.
- The operator's host has the local model server with a small CPU-only model and an agent CLI with the local-provider mode, as the intake reports; whether the CLI's sandbox nests inside Ballast's confinement there is unknown until the pilot. On the current run the agent CLI's sandbox did not start inside Ballast's confinement, so the pilot must test this first.
- Confined steps keep the host network, so a loopback model server is reachable without relaxing the no-network tool boundary.
- The full local gate (Linux with a systemd user session, the agent CLIs) is required, because confinement and sandbox behavior is skipped in CI.
