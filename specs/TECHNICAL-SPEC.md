# Agent-First Repository Operating System

**Technical Specification v0.1**  
**Status:** Draft  
**Date:** 2026-09-24  
**Depends on:** Product Specification v0.1

---

# 1. Purpose

This specification defines the technical architecture of a repository standard that allows interchangeable development agents to turn product specifications into production-ready software with minimal human intervention.

The system must provide:

- a standard repository structure;
- a specification format;
- a work state machine;
- contracts for the different agent roles;
- versioned engineering policies;
- deterministic quality gates;
- specialized agentic reviews;
- risk management;
- a human escalation mechanism;
- an orchestrator abstraction;
- a GitHub integration;
- an integration with CLI agents such as Claude Code and Codex;
- a progressive path toward full automation.

The system must not depend on a particular agent, model or orchestrator.

---

# 2. Normative language

The following terms are normative:

- **MUST**: mandatory;
- **MUST NOT**: forbidden;
- **SHOULD**: recommended unless a documented reason exists;
- **SHOULD NOT**: discouraged unless a documented reason exists;
- **MAY**: optional.

---

# 3. Architectural principles

## 3.1 Repository-owned process

All the rules needed to modify a project correctly MUST be present in the repository or referenced from it.

Agentic conversations are not a durable source of truth.

Important decisions MUST be persisted in one of the following artifacts:

```text
specification
ADR
issue
pull request
documentation
tests
code

```

---

## 3.2 Provider-independent agents

The system MUST be able to use several engines:

```text
Claude Code
Codex CLI
GitHub Copilot
OpenCode
future agents

```

Changing engines MUST NOT require rewriting:

```text
specifications
engineering policies
architecture documentation
tests
GitHub workflow

```

---

## 3.3 Deterministic verification first

Any behavior that can be verified automatically SHOULD be verified automatically.

An agentic reviewer does not replace:

```text
compiler
type checker
test suite
linter
security scanner
build system
runtime checks

```

---

## 3.4 Independent evaluation

An agent that implemented a change MUST NOT be the only mechanism responsible for approving it.

Critical reviews SHOULD be run in a context separate from the implementer's.

---

## 3.5 Progressive disclosure

Global instructions MUST remain short.

Specialized procedures MUST be loaded only when they are relevant.

---

# 4. High-level architecture

The system is divided into five planes.

```text
┌──────────────────────────────────────────────┐
│ CONTROL PLANE                                │
│ GitHub Issues / Projects / PR / labels       │
└────────────────────┬─────────────────────────┘
                     │
┌────────────────────▼─────────────────────────┐
│ ARTIFACT PLANE                               │
│ specs / policies / ADR / docs / tests        │
└────────────────────┬─────────────────────────┘
                     │
┌────────────────────▼─────────────────────────┐
│ EXECUTION PLANE                              │
│ Claude / Codex / other coding agents         │
└────────────────────┬─────────────────────────┘
                     │
┌────────────────────▼─────────────────────────┐
│ VERIFICATION PLANE                           │
│ CI / tests / scans / reviewers               │
└────────────────────┬─────────────────────────┘
                     │
┌────────────────────▼─────────────────────────┐
│ DELIVERY PLANE                               │
│ staging / runtime validation / production    │
└──────────────────────────────────────────────┘

```

---

# 5. Control plane

GitHub is the initial reference control plane.

It stores:

```text
work item status
discussion
priority
risk
ownership
links to specifications
pull requests
review state
CI state
release state

```

GitHub does not necessarily have to store the full content of complex specifications.

---

# 6. Artifact plane

The repository is the versioned source of durable artifacts.

Target structure:

```text
/
├── AGENTS.md
├── CLAUDE.md
├── README.md
├── SECURITY.md
│
├── specs/
│   ├── product/
│   ├── features/
│   ├── bugs/
│   └── archive/
│
├── docs/
│   ├── architecture/
│   │   ├── overview.md
│   │   ├── boundaries.md
│   │   └── adr/
│   │
│   ├── policies/
│   │   ├── engineering.md
│   │   ├── testing.md
│   │   ├── documentation.md
│   │   ├── security.md
│   │   ├── dependencies.md
│   │   ├── migrations.md
│   │   ├── compatibility.md
│   │   └── observability.md
│   │
│   └── operations/
│       ├── deployment.md
│       ├── rollback.md
│       ├── backup-restore.md
│       └── incident-response.md
│
├── .agents/
│   ├── skills/
│   │   ├── triage/
│   │   ├── specify/
│   │   ├── plan/
│   │   ├── implement/
│   │   ├── verify/
│   │   ├── code-review/
│   │   ├── architecture-review/
│   │   ├── security-review/
│   │   ├── dependency-evaluation/
│   │   ├── dependency-migration/
│   │   ├── database-migration/
│   │   ├── documentation-review/
│   │   ├── spec-reconciliation/
│   │   └── release/
│   │
│   └── personas/
│       ├── planner.md
│       ├── implementer.md
│       ├── reviewer.md
│       ├── architect.md
│       └── security-reviewer.md
│
├── scripts/
│   ├── check
│   ├── test
│   ├── verify
│   └── security
│
└── .github/
    ├── ISSUE_TEMPLATE/
    ├── workflows/
    ├── pull_request_template.md
    ├── CODEOWNERS
    └── dependabot.yml / renovate.json

```

This structure is a baseline and MAY be adapted to the stack.

---

# 7. Instruction hierarchy

The instruction resolution order is:

```text
1. platform / organization policy
2. root AGENTS.md
3. directory-scoped AGENTS.md
4. task-specific specification
5. relevant skill
6. implementation plan
7. local implementation conventions

```

A lower-level instruction MUST NOT silently contradict a higher-level instruction.

In case of contradiction, the agent MUST report the conflict.

---

# 8. Root `AGENTS.md` contract

The root `AGENTS.md` SHOULD stay under roughly 250 lines.

It defines only:

```text
repository purpose
engineering priorities
source-of-truth hierarchy
forbidden behaviors
standard verification commands
spec workflow
risk model
skill triggers
escalation rules

```

It must not contain the full procedures for:

```text
security review
dependency evaluation
database migration
release
documentation review

```

These procedures belong in skills.

---

# 9. `CLAUDE.md` and provider-specific files

Where possible:

```text
CLAUDE.md → AGENTS.md

```

or a functional equivalent.

Provider-specific files SHOULD contain only:

```text
provider-specific invocation
tool-specific caveats
compatibility shim

```

They MUST NOT duplicate the whole engineering policy.

---

# 10. Specification storage

Significant features are stored under:

```text
specs/features/<work-id>-<slug>/

```

Example:

```text
specs/features/0423-project-sharing/
├── spec.md
├── plan.md
├── tasks.md
├── verification.md
└── decisions.md

```

Not all of these files are mandatory for a small feature.

---

# 11. Specification metadata

`spec.md` SHOULD start with structured frontmatter.

Example:

```yaml
---
id: F-0423
title: Project sharing
status: ready
risk: R1
issue: 423
created: 2026-09-24
updated: 2026-09-24
depends_on:
  - F-0398
supersedes: []
owners:
  - product
---

```

Minimum fields:

```text
id
title
status
risk
issue

```

---

# 12. Specification states

Allowed values:

```text
idea
discovery
draft
ready
implementing
implemented
validated
superseded
cancelled

```

Nominal transition:

```text
idea
 ↓
discovery
 ↓
draft
 ↓
ready
 ↓
implementing
 ↓
implemented
 ↓
validated

```

---

# 13. Work item states

The operational GitHub state machine can be more detailed than the specification's.

Baseline:

```text
BACKLOG
DISCOVERY
SPECIFYING
READY
PLANNING
IMPLEMENTING
VERIFYING
REVIEWING
STAGING
BLOCKED
DONE

```

---

# 14. State transition authority

Transitions SHOULD be automatable.

Examples:

```text
spec approved
→ READY

agent starts work
→ IMPLEMENTING

PR opened
→ REVIEWING

all required checks pass
→ STAGING

runtime verification passes
→ DONE

```

An agent MUST NOT mark `DONE` if the Definition of Done conditions are not satisfied.

---

# 15. Issue contract

An issue linked to a complex specification SHOULD contain:

```yaml
type: feature
risk: R1
spec: specs/features/0423-project-sharing/spec.md
status: READY

```

The body contains at least:

```text
goal
user/business context
links
open questions

```

The issue remains the discussion surface.

The repository remains the durable source of the spec.

---

# 16. Small work items

For a sufficiently small change, the whole spec MAY stay in the issue.

Typical criteria:

```text
single concern
low architectural impact
no migration
no dependency change
no security boundary change
small diff expected

```

---

# 17. Specification format

A feature spec SHOULD contain:

```text
Context
Goal
Non-goals
Actors
Functional requirements
Behavioral requirements
Security/privacy constraints
Compatibility constraints
Acceptance criteria
Failure behavior
Observability requirements
Open questions

```

The spec SHOULD avoid implementation details.

---

# 18. Implementation plan format

`plan.md` is produced after exploring the repository.

It contains:

```text
Current system analysis
Affected components
Proposed design
Data flow
API/schema changes
Migration strategy
Backward compatibility
Test strategy
Observability impact
Deployment impact
Rollback strategy
Files/components expected to change
Risks
Alternatives considered

```

---

# 19. Tasks format

`tasks.md` breaks the plan down into executable units.

Each task SHOULD have:

```yaml
id: T-01
status: pending
risk: low
depends_on: []

```

and describe a testable unit of work.

A task must not be merely:

```text
implement backend

```

It must be precise enough to produce a verifiable result.

---

# 20. Verification artifact

`verification.md` contains the final proof.

Indicative structure:

```text
Requirements coverage

R1 → PASS via test X
R2 → PASS via test Y
R3 → manual/runtime validation Z

Automated checks

Unit: PASS
Integration: PASS
E2E: PASS
Typecheck: PASS
Security: PASS

Known limitations

Deviations from specification

Runtime verification

Final verdict:
CONVERGED | PARTIAL | FAILED

```

---

# 21. Spec Kit integration

Spec Kit MAY be used as the implementation of the SDD layer.

Mapping:

```text
Spec Kit constitution
→ project principles

speckit.ballast.discover (+ validate-discovery)
→ discovery.md (input evidence, not authority)

speckit specify
→ spec.md (traced to discovery.md)

speckit plan
→ plan.md

speckit tasks
→ tasks.md

speckit implement
→ implementation phase

speckit converge
→ verification/reconciliation

```

In both the human-gated (`ballast-feature`) and the Autonomous (`ballast-autonomous`) workflows, a `discover` step runs after the scope decision and before `speckit.specify`. It writes a source-backed discovery brief from the Issue, its comments and the relevant repository documents. A human-gated run asks the open high-impact decisions in one bundled round, answered in the brief and attributed through operator state. An Autonomous run records safe, reversible defaults as agent-provisional `clarification` decisions, or blocks. Once discovery ran, the spec check requires every acceptance criterion to carry a provenance marker and every Issue acceptance criterion to be covered or listed as a non-goal. `spec.md` and `intent.md` remain the feature's authority; see `docs/policies/spec-kit-workflow.md` (Discovery brief).

The system MUST nonetheless keep its artifacts in formats standard enough to allow abandoning Spec Kit later.

Spec Kit is therefore a possible implementation, not a mandatory proprietary format.

---

# 22. Agent execution model

All agents are seen as implementing a logical abstraction:

```text
AgentRuntime

```

Conceptual interface:

```text
run(role, task, context, permissions) -> result
continue(run_id, feedback) -> result
cancel(run_id)
status(run_id)

```

The concrete runtime can be:

```text
Claude Code CLI
Codex CLI
OpenCode
Copilot
future service

```

---

# 23. Execution isolation

Each implementation task SHOULD run in:

```text
isolated worktree
or
isolated sandbox

```

Agentic work SHOULD NOT run directly in the user's main checkout.

Recommended branch name:

```text
agent/<work-id>-<slug>

```

Example:

```text
agent/F-0423-project-sharing

```

---

# 24. Orca integration

Orca is considered a local human interface.

The system SHOULD be compatible with:

```text
worktrees created by Orca
Claude Code launched by Orca
Codex launched by Orca
local PR inspection
manual takeover

```

The orchestrator MUST NOT require the user to leave Orca to perform a manual intervention.

---

# 25. Agent roles

Minimum logical roles:

```text
triage
specifier
planner
plan reviewer
implementer
verification agent
code reviewer
review orchestrator
fix agent
spec reconciliation agent

```

Conditional roles:

```text
architecture reviewer
security reviewer
dependency reviewer
migration reviewer
documentation reviewer
release reviewer

```

---

# 26. Triage agent

Inputs:

```text
issue/spec
repository metadata
risk policy

```

Outputs:

```yaml
work_type: feature
risk: R1
required_reviews:
  - correctness
  - tests
requires_spec: true
requires_human_approval: false

```

The triage agent does not modify code.

---

# 27. Planner

The planner MUST:

```text
read the specification
inspect existing code
inspect relevant ADRs
inspect applicable policies
identify affected interfaces
identify risks
produce plan.md

```

The planner SHOULD use a model with strong reasoning capability when the impact is significant.

---

# 28. Plan reviewer

The plan reviewer works with a separate context.

It checks:

```text
spec coverage
architecture compatibility
unnecessary complexity
missing migration work
missing tests
security consequences
rollback feasibility
scope creep

```

Verdicts:

```text
APPROVED
CHANGES_REQUIRED
BLOCKED

```

---

# 29. Implementer

The implementer receives:

```text
spec.md
approved plan.md
tasks.md
applicable policies
relevant existing code

```

It MUST:

```text
implement only approved scope
update tests
update relevant docs
run local verification
record deviations

```

It MUST NOT modify the product specification in order to make it match its implementation.

---

# 30. Fix agent

A fix agent receives:

```text
current diff
verification failures
review findings

```

It must fix the findings without introducing additional scope.

The loop is bounded.

Example:

```text
max_review_fix_cycles = 3

```

After the limit is exceeded:

```text
BLOCKED

```

or escalation to a more powerful model.

---

# 31. Review orchestrator

The review orchestrator does not necessarily judge the code itself.

It determines the required reviewers based on the diff and the risk.

Pseudo-rules:

```text
if auth_changed:
    security_review = required

if dependency_changed:
    dependency_review = required

if migration_changed:
    migration_review = required

if architecture_boundary_changed:
    architecture_review = required

if public_behavior_changed:
    documentation_review = required

```

---

# 32. Reviewer contract

Each reviewer produces a structured format.

Example:

```yaml
review: security
verdict: changes_required

findings:
  - id: SEC-01
    severity: high
    file: src/auth/session.py
    description: Session invalidation is incomplete.
    required_action: Invalidate existing refresh tokens.

```

Severities:

```text
info
low
medium
high
critical

```

---

# 33. Review policy

Findings of severity:

```text
critical
high

```

MUST block progression.

`medium` findings SHOULD block unless explicitly accepted and documented.

`low` MAY be deferred to a technical issue.

---

# 34. Risk engine

Risk is computed from:

```text
user declaration
triage agent
changed files
changed subsystem
dependency diff
database diff
security-sensitive patterns

```

The most conservative result SHOULD win.

---

# 35. Risk levels

## R0

Low risk.

Examples:

```text
docs
formatting
tests only
minor isolated internal fix

```

May reach human merge review after proportionate checks and review.

---

## R1

Standard engineering risk.

Examples:

```text
normal feature
UI behavior
new endpoint
internal refactor
non-destructive schema extension

```

May progress without a human if all gates pass.

---

## R2

High risk.

Examples:

```text
authentication
authorization
payments
cryptography
secret handling
destructive migration
data deletion
breaking public API
critical infrastructure
production permission changes

```

MUST require a human decision before merge or production.

---

# 36. Risk escalation

A change initially classified R0/R1 MUST be reclassified if the implementation reveals:

```text
new trust boundary
unexpected migration
breaking API
new dependency with broad privileges
production permission change
data-loss possibility

```

---

# 37. Human intervention contract

The orchestrator SHOULD avoid interrupting the human for technically solvable problems.

Escalate only for:

```text
ambiguous product requirement
contradictory requirements
R2 approval
irreversible decision
significant external cost
license/legal uncertainty
unresolved architecture tradeoff
repeated agent failure

```

In the human-gated mode, the human also approves at each workflow gate (scope, intent, plan, tasks, implementation review, spec reconciliation, final acceptance), and an R2 change needs that approval before the change.

In an eligible Autonomous run (#27), the run does not interrupt the human at those gates. An agent records each gate decision as agent-provisional, with its basis and evidence; a provisional decision is never human approval (constitution BL-INV-006). The single human approval is the merge of the Draft PR, including for R2, whose PR states that the risky change was made without prior human approval. An escalation from the list above becomes a block that stops the run with its reason and recovery command; the operator continues human-gated.

---

# 38. Deterministic verification API

The repository SHOULD expose a stable command:

```bash
./scripts/verify

```

or an equivalent.

This command is the main contract between agents and CI.

It SHOULD group the checks suited to the project.

---

# 39. Verification stages

Logical baseline:

```text
format
lint
typecheck
unit
integration
build
coverage
security
dependency
e2e

```

Not all projects are required to have all stages.

---

# 40. Local vs CI checks

Checks are divided into:

```text
FAST
FULL

```

Example:

```bash
./scripts/check
./scripts/verify

```

`check`:

```text
format
lint
typecheck
targeted tests

```

`verify`:

```text
all checks
integration
security
build
E2E

```

---

# 41. Coverage policy

The project MAY define a coverage threshold.

But coverage alone MUST NOT be considered proof of quality.

The test reviewer also looks for:

```text
meaningful assertions
edge cases
failure paths
overmocking
unreachable tests
excluded modules

```

---

# 42. Characterization tests

Before a migration or a significant behavioral refactor:

```text
existing behavior
→ characterization tests
→ modification
→ equivalence validation

```

If the existing behavior is incorrect, the difference must be explicitly linked to the specification.

---

# 43. Security architecture

Security is divided into:

```text
static security
agentic security review
runtime security
execution isolation
supply chain security

```

---

# 44. Static security baseline

Depending on the stack:

```text
SAST
dependency vulnerability scan
secret scan
container scan
license scan
IaC scan

```

The exact tools remain stack-specific.

---

# 45. Agent security review

A security review is mandatory when a diff touches a trust boundary.

The reviewer analyzes in particular:

```text
authentication
authorization
input validation
output encoding
SSRF
path traversal
injection
serialization
filesystem
network access
secret exposure
PII exposure
concurrency
partial failure
privilege escalation

```

---

# 46. Agent permission model

Personas SHOULD have different permissions.

Example:

```text
planner:
  filesystem: read
  shell: read-only
  network: docs/research
  git_write: false

reviewer:
  filesystem: read
  git_write: false

implementer:
  filesystem: write
  shell: true
  git_write: branch-only

release:
  deployment: controlled

```

A reviewer SHOULD be read-only.

---

# 47. Production credentials

Agents MUST NOT automatically receive:

```text
production database credentials
production shell access
root cloud credentials
organization-wide tokens

```

Sensitive credentials MUST be separated from the agentic context.

---

# 48. Dependency evaluation workflow

Any addition of a significant dependency triggers:

```text
dependency-evaluation

```

Output:

```yaml
package: example
version: 4.2.1
reason: Required for ...
alternatives:
  - standard-library
  - existing-package
maintenance: healthy
license: MIT
known_vulnerabilities: none
transitive_risk: low
replacement_cost: medium
decision: approved

```

---

# 49. Dependency freshness requirements

Before introducing a dependency, the agent SHOULD verify:

```text
latest stable version
release recency
maintenance activity
runtime support
deprecated status
security advisories
license

```

It MUST NOT automatically copy a snippet that uses an obsolete API simply because it appears in old documentation or on Stack Overflow.

---

# 50. Dependency updates

Renovate, Dependabot, or an equivalent SHOULD provide automatic detection of updates.

Indicative policy:

```text
patch
→ auto PR
→ required checks + human merge

minor
→ auto PR
→ tests + dependency review

major
→ migration workflow

```

---

# 51. Dependency migration workflow

A dependency migration follows:

```text
inventory
↓
characterization
↓
replacement evaluation
↓
compatibility strategy
↓
parallel implementation when practical
↓
behavior comparison
↓
switch
↓
observation
↓
old dependency removal
↓
cleanup

```

A massive replacement in a single commit SHOULD be avoided.

---

# 52. Database migration workflow

By default:

```text
EXPAND
↓
DEPLOY
↓
BACKFILL
↓
VERIFY
↓
SWITCH
↓
OBSERVE
↓
CONTRACT

```

Destructive migrations performed at the same time as the removal of the associated code SHOULD be forbidden for progressively deployed systems.

---

# 53. Documentation architecture

Three main categories:

```text
product/domain
engineering
operations

```

Code must not become the sole documentation of complex behaviors.

---

# 54. Documentation update detection

A change SHOULD trigger a docs review when it modifies:

```text
public API
CLI
configuration
deployment
user-visible behavior
architecture
operational procedure

```

---

# 55. ADR contract

Name:

```text
docs/architecture/adr/NNNN-short-title.md

```

Sections:

```text
Status
Context
Decision
Alternatives
Consequences
Migration implications
References

```

An accepted ADR must not be rewritten to hide history.

It is replaced by a new ADR that `supersedes` it.

---

# 56. Spec reconciliation

Before validation:

```text
spec
↕
implementation
↕
tests
↕
documentation

```

The reconciliation agent produces:

```text
CONVERGED
PARTIAL
FAILED

```

A feature is not `validated` until the reconciliation is `CONVERGED`, unless there is an explicit waiver.

---

# 57. CI architecture

Recommended workflow:

```text
PR created
     │
     ▼
FAST CHECKS
     │
     ▼
BUILD
     │
     ▼
TESTS
     │
     ▼
SECURITY
     │
     ▼
DEPENDENCY REVIEW
     │
     ▼
AGENT REVIEWS
     │
     ▼
SPEC RECONCILIATION

```

Jobs SHOULD be parallelized where possible.

---

# 58. Required checks

The repository MUST configure its branch/ruleset protections to prevent merging if the mandatory checks fail.

An agent must not be able to bypass this through a simple modification of the workflow in its PR.

Critical CI changes SHOULD be considered at least R1, often R2.

---

# 59. PR contract

An agent-generated PR SHOULD contain:

```text
Summary

Related issue/spec

Implementation notes

Risk classification

Tests performed

Required reviewers

Migration notes

Deployment notes

Known limitations

```

---

# 60. Agent identity

When an agent produces a change, its role SHOULD be visible.

Example:

```text
Implemented-by: codex/implementer
Reviewed-by: claude/correctness
Security-reviewed-by: claude/security

```

This can live in:

```text
PR body
check output
automation metadata

```

without necessarily polluting the commits.

---

# 61. Fix loop

Pipeline:

```text
implementation
↓
verification
↓
review
↓
findings
↓
fix
↓
verification
↓
review

```

The loop MUST be bounded.

After N failures:

```text
upgrade model
or
human escalation

```

---

# 62. Model routing interface

The router receives:

```yaml
role: planner
risk: R1
complexity: high
context_size: medium
requires_tools: true

```

It returns:

```yaml
provider: anthropic
runtime: claude-code
tier: strong

```

The concrete provider is not hard-coded in the specs.

---

# 63. Model tiers

Three logical levels:

```text
FAST
STANDARD
STRONG

```

FAST:

```text
classification
simple edits
search
changelog
formatting

```

STANDARD:

```text
normal implementation
tests
routine review

```

STRONG:

```text
architecture
complex planning
security
migration
difficult debugging
adversarial review

```

---

# 64. Subscription-aware routing

The router SHOULD be able to declare:

```yaml
billing_mode:
  - subscription
  - api
  - local

```

Example configuration:

```yaml
providers:
  claude:
    runtime: claude-code
    billing: subscription

  codex:
    runtime: codex-cli
    billing: subscription

```

The default mode SHOULD prefer `subscription` when requested by the user.

---

# 65. Paid API guard

A paid API execution SHOULD require explicit authorization.

Example:

```yaml
allow_metered_api: false

```

If no compatible runtime is available:

```text
BLOCK

```

rather than a silent fallback to a billed API.

---

# 66. Orchestrator requirements

The chosen or developed orchestrator MUST provide at a minimum:

```text
dispatch agent
capture result
track run state
cancel run
continue run
worktree/sandbox selection
role permissions
failure handling
structured output

```

It SHOULD provide:

```text
parallel runs
persistent state
resume
web/CLI inspection
agent messaging

```

---

# 67. Orchestrator non-requirements

The orchestrator does not need to:

```text
own the product backlog
replace GitHub
replace Orca
store specifications
provide its own editor

```

The project must avoid creating a second project management system.

---

# 68. Orchestration adapter

Conceptual internal interface:

```python
class AgentAdapter:
    start(...)
    send(...)
    status(...)
    stop(...)
    collect_result(...)
```

Possible adapters:

```text
ClaudeCodeAdapter
CodexAdapter
OpenCodeAdapter
RemoteAgentAdapter

```

---

# 69. Local orchestrator implementation

If an in-house orchestration layer becomes necessary, Python is the recommended initial choice for the prototype because of:

```text
subprocess management
GitHub integration
structured data
rapid iteration
cross-platform support
existing user preference

```

This choice is not architecturally mandatory.

---

# 70. Git worktree strategy

Each implementer SHOULD work in a separate worktree.

Example:

```text
.worktrees/
├── F-0423-implementation/
├── F-0424-bugfix/
└── F-0425-review-fix/

```

Two agents SHOULD NOT modify the same worktree simultaneously.

---

# 71. Parallelism policy

Tasks can be parallelized only if their write sets are sufficiently independent.

Safe:

```text
backend implementation
+
read-only security review of another PR

```

Potentially unsafe:

```text
two agents editing same migration
two agents modifying same API contract

```

The planner SHOULD identify the opportunities for parallelism.

---

# 72. Runtime validation

After merge or before production, depending on the project:

```text
deploy staging
↓
health checks
↓
smoke
↓
E2E
↓
observability check
↓
optional canary

```

---

# 73. Rollback contract

Every R1/R2 feature SHOULD answer before deployment:

```text
How do we rollback code?

How do we rollback data?

Can the old version run against the new schema?

What happens to writes made after deployment?

```

---

# 74. Production release

Target pipeline:

```text
validated PR
↓
merge
↓
artifact build
↓
artifact signing/provenance
↓
staging
↓
runtime verification
↓
risk gate
↓
production
↓
post-deploy verification

```

---

# 75. Observability requirements

For each new critical path, the planner must determine whether the following are needed:

```text
logs
metrics
traces
health check
alert
dashboard

```

A feature that is invisible during an outage is not necessarily production-ready.

---

# 76. Agent pipeline observability

The system itself must produce:

```text
run ID
role
runtime
start/end
work item
result
token/quota usage where available
failure reason
review findings
fix cycle count

```

No private chain of thought is required.

The system keeps only the necessary operational outputs.

---

# 77. Audit artifact

Each work item MAY produce:

```text
.agent-runs/<work-id>/summary.json

```

Example:

```json
{
  "work_id": "F-0423",
  "runs": [
    {
      "role": "planner",
      "runtime": "claude-code",
      "result": "approved"
    },
    {
      "role": "implementer",
      "runtime": "codex",
      "result": "completed"
    }
  ]
}

```

This file MAY be stored outside Git if it is too volatile.

---

# 78. Token efficiency

The context builder loads only:

```text
root instructions
task spec
approved plan
directly applicable policy
relevant architecture docs
relevant code

```

It SHOULD avoid:

```text
entire docs tree
all historical issues
all ADRs
full git history
all previous agent transcripts

```

---

# 79. Context retrieval

Context is obtained primarily through:

```text
explicit references
repo search
dependency graph
code navigation
directory-scoped instructions

```

and not by loading the entire repository into the prompt.

---

# 80. Policy versioning

Policies are versioned with the code.

When a policy changes significantly, `READY` specs SHOULD be re-evaluated.

Features that are already `VALIDATED` are not automatically invalidated.

---

# 81. Policy maintenance

A periodic job MAY analyze:

```text
obsolete tool references
obsolete dependency rules
dead documentation links
unsupported runtime versions
outdated security baseline
stale AGENTS instructions

```

Result:

```text
maintenance PR

```

---

# 82. Definition of Ready

A feature is `READY` when:

```text
goal understood
scope bounded
acceptance criteria defined
blocking questions resolved
dependencies identified
initial risk assigned

```

It does not need to have an implementation plan at this stage.

---

# 83. Definition of Planned

A feature is `PLANNED` when:

```text
repository inspected
plan produced
migration strategy defined
test strategy defined
plan independently reviewed

```

---

# 84. Definition of Implemented

A feature is `IMPLEMENTED` when:

```text
code complete
local checks pass
tests updated
required docs updated
PR created

```

This does not mean `DONE`.

---

# 85. Definition of Validated

A feature is `VALIDATED` when:

```text
CI green
required reviews pass
spec reconciliation converged
required runtime verification passes

```

---

# 86. Definition of Done

A work item is `DONE` when:

```text
validated
merged
required deployment completed
post-deploy checks pass
follow-up work explicitly tracked

```

---

# 87. MVP v0.1

The first implementation of the standard covers only:

```text
repository structure
AGENTS.md baseline
core policies
feature spec format
GitHub issue linkage
risk classification
planner role
implementer role
correctness reviewer
security reviewer
dependency reviewer
scripts/check
scripts/verify
GitHub CI
manual agent dispatch from Orca
Spec Kit compatibility
spec reconciliation

```

No mandatory automatic orchestration.

---

# 88. MVP workflow

```text
Human creates/specifies feature
        ↓
Spec Kit / manual spec
        ↓
READY
        ↓
Human launches planner in Orca
        ↓
plan.md
        ↓
independent review
        ↓
Human launches implementer
        ↓
PR
        ↓
CI
        ↓
reviewer agents
        ↓
fix loop
        ↓
converge
        ↓
human merge

```

This phase serves to validate the contracts before automating.

---

# 89. v0.2 target

Automate:

```text
READY detection
agent dispatch
worktree creation
structured role invocation
review orchestration
fix loops
GitHub status updates

```

A human remains necessary for all merges.

---

# 90. v0.3 target

Add:

```text
issue-linked Draft PR lifecycle
safe branch synchronization on start and resume
worktree and update reliability
operator-facing evidence and recovery paths
human merge review for every feature PR

```

Safe branch synchronization on start and resume is delivered by #18
([`specs/18-branch-sync/`](18-branch-sync/spec.md), ADR-0005): before the first
agent step of every `ballast run start`, `resume` and `continue`, trusted
launcher code rebases the run's feature branch onto its authoritative base and
pushes a published one with a lease, or blocks before any agent with
`BLOCKED_UPSTREAM_SYNC`. Autonomous `resume` goes through the same
synchronization since #21 ([`specs/21-autonomous-reviewed-pr/`](21-autonomous-reviewed-pr/spec.md), ADR-0010).

---

# 91. v1.0 target

**Scope decision, 2026-10-03:** Ballast 1.0 takes a feature from a request in an adopted repository to a verified GitHub PR ready for a **human merge decision**. It does not promise staging deployment or production release. The broader product vision in `PRODUCT-SPEC.md` remains a later target.

The qualified 1.0 environment is GitHub on Linux with a systemd user session. A blank repository and an established repository must both be supported. The required operator modes are Chat and Autonomous; Guided and Supervised may follow later.

The complete path is:

```text
one-command Ballast installation and project-adapted init
      ↓
request discovery and traceable feature specification
      ↓
Chat or Autonomous workflow
      ↓
implementation, deterministic checks, independent review, correction
      ↓
safe branch synchronization and one reusable GitHub Draft PR
      ↓
acceptance evidence and an on-demand UI demo when requested
      ↓
PR ready for human merge decision

```

Branch synchronization (#18) covers every invocation that starts agent steps, including every Chat `step`. Since #21 (ADR-0010) a blocked or interrupted Autonomous run resumes in Autonomous through it, recording the operator's block resolution, or continues human-gated or in Chat; implementation findings get a bounded fix loop (§61) of three cycles per run in `ballast-autonomous` 1.2.0; `ballast run checkpoint` refreshes a finished run's Draft PR evidence.

Autonomous makes intermediate intent, plan and implementation decisions provisionally and records their basis. For an eligible feature, it requests no human approval until merge. Chat keeps the operator in the conversation while using the same trusted preflight and evidence contracts. Technical failures, conflicts, exhausted limits and unavailable authority may still block a run. No mode silently approves its own PR or merges it.

**Status (#20, Chat mode):** `ballast run start --mode chat` starts a Ballast-driven run whose phases the operator runs one invocation at a time (`step`, `status`, `approve`, `reject`, `resolve`, `checks`, `mode`, `publish`), each through the trusted launcher. Interactive steps run under the Autonomous confinement behind a wrapper-owned pty; every gate is a human decision bound to an artifact digest in operator state; a Chat run switches with the human-gated mode, continues a stopped Autonomous run, and is never raised to Autonomous. Contracts: [`specs/20-chat-mode/`](20-chat-mode/spec.md); decision: [ADR-0009](../docs/adr/0009-chat-mode-operator-driven-steps.md) (proposed).

**Status (#13, project-adapted init):** the global CLI's commands are `init`, `setup`, `preview`, `trust`, `run`, `ledger`, `intake`, `discard-runs`, `doctor`, `self-install` and `--version`. `ballast init [--ref REF] [--description TEXT] [--stack python|node|rust|go|neutral]` is the only one that runs before a pin: the CLI chooses the ref (the existing pin, which init keeps and a different `--ref` cannot move; without a pin, `--ref`, else its own release), fetches that version and runs its `tools/init` under `/usr/bin/python3 -IS`. A standard version declares the tool in its manifest `tools/cli.toml` with `[init] supported = true`, read as data next to `[cli] minimum`, `[doctor] probes`, `[setup] recoverable`/`prepare` and `[runs] format`/`resumes`; the CLI refuses a version without it, or one whose minimum exceeds the CLI, before writing in the project. `tools/init` inspects a fixed, bounded evidence list as data, creates only absent project-owned files (`ballast.toml`, the constitution, `AGENTS.md` with its `CLAUDE.md` link, an evidence-backed `docs/policies/project/testing.md`) from `templates/init/` and `templates/AGENTS.md`, appends setup's ignore block when missing, proposes every other change as the ignored `.ballast/init/proposed.patch`, installs through `tools/setup` and reports readiness; it never runs detected commands, records trust, commits or pushes. Contracts: [`specs/13-adaptive-init/`](13-adaptive-init/spec.md); decision: [ADR-0012](../docs/adr/0012-init-before-pin.md) (proposed).

One compatible zero-cost execution backend must be qualified as an opt-in fallback when the existing Claude/Codex route is unavailable or its quota is exhausted. Free-only and privacy/permission constraints apply before selection; fallback attempts are bounded and recorded. Paid overflow and broad provider support are later work.

A UI demo video is captured **on request** from a project-supplied reproducible scenario and linked to the existing PR with its commit and scenario. Routine UI PRs do not require automatic capture. The PR also carries concise, source-linked acceptance evidence, checks and unresolved decisions.

**Status (#22, on-demand demo capture):** on-demand capture is in 1.0; automatic capture stays later work. The operator runs `ballast run demo RUN_ID SCENARIO` for a run with an open Ballast Draft PR. Ballast reads the scenario from the `[demo]` table of the protected `ballast.toml` and dispatches the project's copy-once `ballast-demo.yml` workflow on the feature branch, never the default branch. It dispatches only when the branch's copy of that workflow is the default branch's blob. The job has no secrets and a read-only token, runs the declared command under a timeout, and uploads one video as an Actions artifact. The acceptance packet's demo section links the video only when the run's commit is the PR head, and shows any other outcome as missing evidence; a video never changes a criterion's state. Contracts: [`specs/22-ui-demo/`](22-ui-demo/spec.md); decision: [ADR-0013](../docs/adr/0013-demo-capture-dispatch.md) (proposed).

**Status (#55, setup-recorded trust):** `ballast setup` and a worktree's first-command preparation record the checkout's trust baseline themselves when it holds exactly what they installed and its committed `ballast.toml` and constitution are ones a human reviewed: equal to the default branch of the repository pinned in `[github] repository` (observed live through ADR-0005's trusted Git path in a throwaway repository, and counted only for a repository `ballast trust` reviewed on this machine), or, for `ballast setup` only, equal to the checkout's own baseline from `ballast trust`. No saved run state, marker, extra protected input or foreign worktree pointer may exist; otherwise nothing is recorded and `ballast trust` stays the path. The baseline gains a bound provenance record (`trusted-source.json`), reported as `baseline_source` by `status --json` and shown by `ballast doctor`; the launcher's comparison, refusals and tamper marker are unchanged. Contracts: [`specs/55-setup-trust/`](55-setup-trust/spec.md); decision: [ADR-0015](../docs/adr/0015-setup-recorded-trust-baseline.md) (proposed; supersedes parts of ADR-0007 and ADR-0011).

The 1.0 release gate and phased implementation map are in [`docs/plans/2026-10-02-product-roadmap.md`](../docs/plans/2026-10-02-product-roadmap.md). The reconciliation of the human-gated approvals with Autonomous's provisional-decision model is specified in [`specs/27-autonomous-core/`](27-autonomous-core/spec.md): for an eligible Autonomous run, every intermediate approval, including the R2 pre-change approval, is agent-provisional and the merge decision is the single human approval; the human-gated mode keeps its approvals. Selecting a CLI mode does not itself weaken the trust boundary: the mode is recorded in operator state, agent steps run confined, and publication is done by the trusted runner, never by an agent.

Later releases may add:

```text
staging and production validation
additional forges and host platforms
paid overflow and more providers
automatic demo capture and richer review interfaces

```

---

# 92. Reference implementation strategy

Do not start by building a large orchestrator.

Recommended order:

```text
1. standardize artifacts
2. standardize policies
3. standardize agent contracts
4. prove manually with Claude/Codex
5. automate repeatable transitions
6. introduce orchestration adapter
7. automate safe risk classes

```

---

# 93. Technology choices — initial defaults

These choices are defaults, not hard dependencies.

```text
Source control:
Git + GitHub

Specification:
Markdown + YAML frontmatter
optionally Spec Kit

Issue tracking:
GitHub Issues + Projects

CI:
GitHub Actions

Agent runtimes:
Claude Code
Codex CLI

Human cockpit:
Orca IDE

Dependency automation:
Renovate preferred
Dependabot acceptable

Security baseline:
OWASP ASVS-inspired policy

Release:
repository-specific

```

---

# 94. Explicitly deferred choices

Not decided in v0.1:

```text
CAO
Open SWE
OpenHands
custom orchestrator
GitHub-native agent orchestration

```

None of them must be required to adopt the standard.

---

# 95. Compatibility requirement

The system MUST be able to operate in its degraded form with only:

```text
Git
GitHub
Markdown
shell
one coding agent
CI

```

All the other building blocks improve automation but must not make the repository incomprehensible without them.

---

# 96. Failure philosophy

The system prefers:

```text
blocked with explicit reason

```

to:

```text
silent assumption

```

Examples of blocking conditions:

```text
unresolved product conflict
unsafe migration
high-risk security uncertainty
repeated verification failures
dependency license conflict
required infrastructure unavailable

```

---

# 97. Non-goals v0.1

This architecture does not yet seek to:

```text
replace GitHub
replace Orca
invent a new programming agent
host models
implement a new CI engine
create a proprietary spec language
record private agent chain-of-thought
fully remove human responsibility

```

---

# 98. Acceptance criteria for this technical design

The standard will be considered technically viable when a pilot repository demonstrates:

1. a non-trivial feature written as a spec;
2. a plan generated by an agent;
3. an implementation by another agent;
4. automatic tests and quality gates;
5. an independent review;
6. automatic correction of at least one finding;
7. a spec/code reconciliation;
8. a complete PR;
9. no essential conversational context lost between steps;
10. replacement of the implementer Claude ↔ Codex without modifying the spec or the workflow;
11. no paid API consumption when a subscription-only mode is requested;
12. the ability to manually resume the work in Orca.

---

# 99. Recommended pilot

LoreForge is a good candidate to validate the system.

Recommended pilot phase:

```text
existing LoreForge architecture
        ↓
install/adopt Spec Kit
        ↓
choose next significant feature
        ↓
produce spec
        ↓
produce reviewed plan
        ↓
implement through Orca
        ↓
independent Claude/Codex review
        ↓
CI
        ↓
Spec Kit converge
        ↓
record friction points

```

Do not automate further before having run several features this way.

The result of this experiment must feed into Technical Specification v0.2.

---

# 100. Core technical invariant

The core of the system can be summarized as follows:

```text
SPEC
 │
 ▼
PLAN
 │
 ▼
IMPLEMENTATION
 │
 ▼
DETERMINISTIC EVIDENCE
 │
 ▼
INDEPENDENT REVIEW
 │
 ▼
SPEC RECONCILIATION
 │
 ▼
RISK GATE
 │
 ▼
DELIVERY

```

No step must depend exclusively on trust in the previous agent's response.

---

# 101. Architectural north star

Eventually:

```text
                       HUMAN
                         │
                  product intent
                         │
                         ▼
                   GitHub / Spec
                         │
                         ▼
                 READY WORK QUEUE
                         │
                    ORCHESTRATOR
                         │
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
       planner       implementer      reviewers
          │              │              │
          └──────────────┼──────────────┘
                         │
                         ▼
                 deterministic CI
                         │
                         ▼
                  reconciliation
                         │
                         ▼
                    runtime proof
                         │
                         ▼
                     risk gate
                    /         \
               autonomous     human
                    \         /
                     \       /
                    production

```

The orchestrator is replaceable.

The models are replaceable.

The IDEs are replaceable.

The repository's artifacts, policies, evidence, and contracts constitute the durable system.
