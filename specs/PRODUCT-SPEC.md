# Agent-First Repository Operating System

**Version:** 0.1  
**Status:** Draft  
**Date:** 2026-09-24

## 1. Vision

Create a reusable system that makes it possible to start from an empty repository and end up with a truly production-ready application, with minimal human intervention on the implementation.

The human developer acts mainly as:

- product owner;
- functional decision-maker;
- arbiter of difficult or irreversible choices;
- occasional validator of high-risk changes.

The agents take over as much as possible of:

- specification clarification;
- repository exploration;
- technical planning;
- implementation;
- tests;
- documentation;
- code review;
- architecture review;
- security review;
- dependency management;
- migrations;
- fixes after CI/review;
- creation and maintenance of PRs;
- staging validation;
- release preparation;
- ongoing maintenance.

The goal is not to create a new IDE or to lock the workflow into a particular model.

The repository itself must contain enough rules, context, procedures and guardrails to allow different agents to work on it reliably.

---

# 2. Main objective

Enable the following workflow:

```text
Human product intent
        ↓
Specification
        ↓
Agent planning
        ↓
Independent plan review
        ↓
Implementation
        ↓
Automated verification
        ↓
Independent reviews
        ↓
Fix loop
        ↓
Pull Request
        ↓
CI
        ↓
Staging
        ↓
Runtime validation
        ↓
Risk gate
        ↓
Production

```

With human intervention only when it brings real value.

---

# 3. Core principles

## 3.1 Human-driven, agent-built

The human mainly defines:

```text
WHAT
WHY
constraints
priorities
product decisions
acceptable risk

```

The agents mainly determine:

```text
HOW
implementation details
file changes
tests
refactors
documentation updates

```

The system must avoid turning the human into a permanent supervisor of the agents.

---

## 3.2 Repository as operating system

The repository must be self-contained.

A new agent arriving on the project must be able to determine:

```text
How should I modify this project?
How should I test it?
What am I allowed to change?
What requires additional review?
How should dependencies be chosen?
What security assumptions exist?
How should migrations be performed?
What constitutes "done"?

```

without depending on a conversation history.

---

## 3.3 Agents must remain replaceable

The system must not fundamentally depend on any of:

- Claude Code;
- Codex;
- Open SWE;
- CAO;
- Copilot;
- Cursor;
- Kiro;
- Orca.

These tools must be considered interchangeable engines around a common contract defined in the repository.

---

## 3.4 Deterministic verification over agent confidence

A reply such as:

> "The implementation looks correct."

is not proof.

When something can be validated automatically, automatic validation takes priority.

Examples:

```text
formatter
linter
type checker
unit tests
integration tests
E2E tests
coverage
dependency scan
secret scan
SAST
build
database checks
schema checks
smoke tests
runtime health checks

```

Agents intervene mainly where deterministic verification is insufficient.

---

## 3.5 Independent review

The agent that writes a change must not be its only reviewer.

Minimal workflow:

```text
Implementer
    ↓
automated checks
    ↓
independent reviewer

```

For sensitive changes:

```text
Implementer
    ↓
correctness reviewer
    ↓
architecture reviewer
    ↓
security reviewer
    ↓
test reviewer

```

Not all reviewers necessarily have to run for every change.

---

# 4. Economic constraints

The system must, as far as possible, make use of the subscriptions the user has already paid for.

Current example:

```text
Claude Code
→ Claude subscription

Codex CLI
→ ChatGPT/Codex subscription

```

By default, the system must avoid workflows that require separately billed API calls.

Important consequence:

orchestrators that rely exclusively on provider APIs must not be an essential architectural dependency.

They may remain optional.

---

# 5. Main user interface

## Orca IDE

Orca remains the user's daily environment.

It is mainly used for:

```text
interactive agent sessions
worktrees
local inspection
diff review
terminal access
manual intervention
Claude Code
Codex

```

Orca does not need to become the global orchestrator.

It represents the human cockpit.

---

# 6. GitHub as the coordination bus

GitHub becomes the shared coordination layer between:

```text
Human
Orca
agents
automation
CI
deployment

```

GitHub mainly contains:

```text
Issues
Projects
Pull Requests
reviews
checks
branches
releases
deployments

```

The orchestrator must be replaceable without changing this layer.

---

# 7. Separation between state and artifacts

Principle:

```text
GitHub Issue
= workflow state

Repository
= durable artifacts

Tests
= executable contract

Code
= current implementation

```

Example:

```text
Issue #423

Feature: Project sharing

status: READY
risk: R1

spec:
specs/0423-project-sharing/spec.md

plan:
specs/0423-project-sharing/plan.md

tasks:
specs/0423-project-sharing/tasks.md

```

---

# 8. Specification-driven development

The system must be spec-driven but must not fall into Big Design Up Front.

The specification works as a rolling wave.

Three horizons are maintained.

## NOW

About one feature.

Fully specified and ready to be implemented.

## NEXT

A few features.

The product behavior is known but some details are deliberately left open.

## LATER

Intentions, epics and product directions.

No detailed technical design.

Example:

```text
A = IMPLEMENTING
B = READY
C = DRAFT
D = IDEA

```

While A is being implemented, B can be finalized.

There is no need to wait for A to be fully validated before thinking about B.

However, the technical details of C/D must not be frozen prematurely.

---

# 9. Specification hierarchy

The product must clearly distinguish:

```text
Product vision
      ↓
Product / domain specification
      ↓
Architecture + invariants
      ↓
Feature specification
      ↓
Implementation plan
      ↓
Implementation

```

---

# 10. Specification vs implementation plan

A specification describes:

```text
WHAT must be true
WHY it exists
constraints
expected behavior
acceptance criteria

```

It should normally not impose:

```text
class names
file names
implementation pattern
framework internals
specific functions

```

unless these genuinely constitute a product or architectural constraint.

Correct example:

```text
Users can create projects.

A project must have a name.

Names are unique per user.

Creation requires authentication.

A failed creation must not leave partial persistent state.

```

The implementation plan then answers:

```text
How should the current repository implement this requirement?

```

It is produced after inspecting the existing code.

---

# 11. Specification lifecycle

A spec has an explicit status.

```text
IDEA
 ↓
DISCOVERY
 ↓
DRAFT
 ↓
READY
 ↓
IMPLEMENTING
 ↓
IMPLEMENTED
 ↓
VALIDATED
 ↓
SUPERSEDED

```

An agent should normally start an automatic implementation only from a `READY` specification.

---

# 12. Spec ↔ implementation reconciliation

Every implementation must end with a reconciliation phase.

Questions:

```text
Did implementation satisfy every requirement?

Did implementation introduce behavior not described by the spec?

Did implementation reveal an invalid assumption?

Did architecture change?

Did future specifications become stale?

Was a deliberate deviation introduced?

```

Possible outcomes:

```text
implementation wrong
→ fix implementation

spec wrong
→ update spec

new knowledge
→ update current/future specs

```

The pipeline must not treat:

```text
PR merged

```

as equivalent to:

```text
feature complete

```

---

# 13. No hidden fixes in later specs

A new feature must not quietly repair a previous feature.

If A must be fixed before C:

```text
A2 correction

```

must be explicitly created.

This improves:

```text
traceability
agent understanding
architecture history
change attribution

```

---

# 14. Issue or file for the spec?

Both are allowed.

## Small change

The whole specification can live in the issue.

Example:

```text
Bug
Small UI change
Documentation
Minor behavior adjustment

```

## Significant feature

The issue mainly contains:

```text
goal
summary
status
risk
links
discussion
ownership

```

The durable specification lives in the repository.

For example:

```text
specs/
└── 0423-project-sharing/
    ├── spec.md
    ├── plan.md
    ├── tasks.md
    └── verification.md

```

Advantages:

```text
versioning
branch awareness
PR review
history
agent access
spec/code synchronization

```

---

# 15. Instruction architecture

A huge `AGENTS.md` must not be used.

The system must rely on progressive disclosure.

Architecture:

```text
AGENTS.md
    ↓
policies
    ↓
skills
    ↓
stack-specific instructions

```

---

# 16. Root `AGENTS.md`

The root file contains only invariant rules.

Target size:

```text
~150–250 lines

```

It defines in particular:

```text
engineering priorities
forbidden actions
change discipline
quality expectations
risk classification
skill triggers
review requirements
source-of-truth rules

```

---

# 17. Engineering priority order

When a trade-off is necessary:

```text
1. Correctness
2. Security
3. Data integrity
4. Backward compatibility
5. Maintainability
6. Observability
7. Performance
8. Developer convenience

```

Sacrificing a higher priority for a lower one requires an explicit justification.

---

# 18. Forbidden agent behavior

Agents must never silently:

```text
disable failing tests

weaken assertions

reduce validation

ignore exceptions

introduce broad lint suppressions

introduce broad type suppressions

remove security controls

log credentials/secrets

make irreversible destructive migrations

introduce a dependency without evaluation

change public contracts without documenting compatibility

rewrite unrelated code without justification

```

---

# 19. Contextual skills

Detailed procedures live in dedicated skills.

Indicative structure:

```text
.agents/
├── skills/
│   ├── plan-change/
│   ├── implement-change/
│   ├── verify-change/
│   ├── code-review/
│   ├── architecture-review/
│   ├── security-review/
│   ├── dependency-evaluation/
│   ├── dependency-migration/
│   ├── database-migration/
│   ├── documentation-review/
│   ├── release/
│   └── incident-analysis/
│
└── personas/
    ├── planner.md
    ├── developer.md
    ├── reviewer.md
    ├── architect.md
    └── security-reviewer.md

```

---

# 20. Conditional skill triggering

Example:

```text
Authentication changed
→ security-review

Authorization changed
→ security-review

New dependency
→ dependency-evaluation

Dependency replacement
→ dependency-migration

Persisted data changed
→ database-migration

Architectural boundary changed
→ architecture-review

Externally visible behavior changed
→ documentation-review

```

---

# 21. Documentation policy

Documentation must mainly explain:

```text
WHY
contracts
constraints
invariants
non-obvious behavior
operational implications

```

It must not simply restate the code.

---

# 22. Code comments

Comments are mainly required for:

```text
non-obvious decisions
workarounds
security assumptions
performance constraints
protocol quirks
business invariants
upstream bugs

```

Bad comment:

```text
Increment counter by one.

```

Good comment:

```text
Retry IDs must remain monotonic because downstream deduplication
uses them as an idempotency key.

```

---

# 23. TODO / FIXME

A TODO or FIXME must explain:

```text
why the work remains
what blocks it
relevant issue/reference

```

A TODO cannot be used to silently defer:

```text
security
data correctness
critical validation

```

---

# 24. ADR

An Architecture Decision Record is required for decisions that are hard to reverse.

Examples:

```text
new persistence mechanism
major subsystem
service boundary change
foundational dependency
protocol change
authentication architecture
runtime architecture

```

---

# 25. Dependency policy

An agent must not choose a dependency solely because it is popular or convenient.

Before adding one:

```text
Can existing dependencies solve it?

Can the standard library solve it?

Would a small local implementation be safer?

Is the dependency maintained?

Are releases recent?

Does it support current runtimes?

Known vulnerabilities?

License compatible?

Transitive dependency footprint?

Security posture?

Upgrade history?

Documentation quality?

Bus factor / project maturity?

Replacement difficulty?

```

---

# 26. Dependency freshness

The system must prevent as far as possible:

```text
deprecated dependencies
unmaintained dependencies
obsolete APIs
unsupported runtimes
old examples copied from outdated documentation

```

Agents must check the currently supported versions before adoption.

---

# 27. Dependency automation

A solution such as Renovate or an equivalent can automatically:

```text
detect upgrades
open PRs
group safe upgrades
automerge low-risk upgrades

```

Major upgrades remain subject to the same reviews as normal code.

---

# 28. Dependency migration

Replacing a dependency is a migration.

Expected process:

```text
characterize current behavior
        ↓
identify all usages
        ↓
identify exposed API/contracts
        ↓
evaluate replacement
        ↓
create compatibility boundary if needed
        ↓
implement replacement
        ↓
compare behavior
        ↓
switch default
        ↓
observe
        ↓
remove old implementation
        ↓
remove old dependency
        ↓
remove temporary compatibility code
        ↓
update documentation

```

Not:

```text
uninstall old
install new
rewrite everything
hope CI catches it

```

---

# 29. Database migrations

Destructive changes must follow, as far as possible:

```text
EXPAND
   ↓
DEPLOY compatible application
   ↓
MIGRATE / BACKFILL
   ↓
VERIFY
   ↓
SWITCH
   ↓
OBSERVE
   ↓
CONTRACT

```

Example that is forbidden in a single deployment without justification:

```sql
DROP COLUMN

```

if a potentially active version of the software may still use it.

---

# 30. Cybersecurity

Security must not be reduced to:

```text
dependency scanner
+
SAST

```

It includes:

```text
secure design
threat reasoning
trust boundaries
authorization
authentication
secret management
data exposure
network boundaries
runtime permissions
CI/CD permissions
supply-chain security

```

---

# 31. Security triggers

A specialized security review is triggered for changes touching in particular:

```text
authentication
authorization
permissions
sessions
cookies
cryptography
secrets
user-controlled input
file uploads
network requests
webhooks
serialization
filesystem access
payments
personal data
admin functionality
CI/CD permissions

```

---

# 32. Security reviewer

The security reviewer must receive an independent context.

It looks in particular for:

```text
Where does untrusted data enter?

Which trust boundaries are crossed?

Is authentication sufficient?

Is authorization checked independently?

Can identifiers be enumerated?

Can requests reach internal services?

Can user input reach SQL/shell/templates/filesystem?

Can secrets reach logs/errors/client bundles?

What happens under concurrency?

What happens during partial failure?

```

---

# 33. Security baseline

A standard such as OWASP ASVS can serve as an external baseline rather than a checklist entirely invented locally.

The project must define the appropriate level according to its context.

---

# 34. Agent isolation

Agents are not a security boundary.

Important protections must be external:

```text
sandboxing
filesystem permissions
GitHub permissions
environment protection
secret management
deployment permissions
cloud IAM
branch protection

```

---

# 35. Testing policy

Tests must verify useful behavior, not merely raise a coverage number.

Agents must not be able to:

```text
add trivial tests
exclude difficult code
mock everything
weaken assertions
delete edge cases

```

solely to reach a threshold.

---

# 36. Test hierarchy

Depending on the project:

```text
unit
integration
contract
property-based
E2E
smoke
regression

```

The pipeline must select the relevant categories rather than systematically imposing all of them.

---

# 37. Characterization tests

Before a refactor or a complex migration, the agent must capture the existing behavior when that behavior has to be preserved.

```text
existing behavior
      ↓
characterization tests
      ↓
refactor/migration
      ↓
behavior comparison

```

---

# 38. Deterministic quality gates

Every PR must be able to trigger, depending on the stack:

```text
format check
lint
static analysis
type checking
unit tests
integration tests
coverage
build
dependency review
license checks
secret scanning
SAST
E2E

```

No agent may silently bypass these gates.

---

# 39. Multi-persona review

The system must have specialized reviewers.

## Correctness reviewer

Looks for:

```text
logic errors
edge cases
failure handling
race conditions
invalid assumptions

```

## Architecture reviewer

Looks for:

```text
unnecessary abstractions
boundary violations
coupling
duplicated responsibilities
architecture drift

```

## Test reviewer

Looks for:

```text
missing scenarios
overmocking
weak assertions
coverage gaming
missing regressions

```

## Security reviewer

Looks for vulnerabilities and new trust boundaries.

## Dependency reviewer

Evaluates new packages and migrations.

---

# 40. Review orchestration

Not every persona is launched systematically.

An orchestrator classifies the change, then chooses the necessary reviews.

Example:

```text
documentation-only
→ lightweight review

UI component
→ correctness + tests

dependency addition
→ correctness + dependency

auth endpoint
→ correctness + tests + security

core architecture change
→ correctness + architecture + tests

```

---

# 41. Risk classification

Three initial levels.

## R0 — Low Risk

Examples:

```text
docs
typo
tests
minor internal cleanup
simple isolated bug

```

Can reach human merge review after checks and proportionate review.

## R1 — Normal Engineering Change

Examples:

```text
feature
endpoint
normal refactor
UI change
non-destructive schema extension

```

Can be automatically merged after:

```text
reviews
CI
staging validation

```

## R2 — High Risk

Examples:

```text
authentication
authorization
payments
secrets
crypto
data loss risk
breaking API
irreversible migration
critical infrastructure
production access policy

```

Requires explicit human approval.

---

# 42. Human escalation philosophy

The human must not be called upon because:

```text
the agent is uncertain about a filename
a test failed
a library API is unfamiliar

```

Agents must investigate on their own.

Escalate for:

```text
ambiguous product behavior
conflicting requirements
irreversible decision
high security/business risk
significant cost
legal/licensing ambiguity
fundamental architecture tradeoff

```

---

# 43. Target autonomous pipeline

```text
                    ISSUE / SPEC
                         │
                         ▼
                    TRIAGE AGENT
                         │
               classify scope/risk
                         │
                         ▼
                    PLANNER
                         │
                  inspect repository
                         │
                  produce plan
                         │
                         ▼
                 PLAN REVIEWER
                         │
                 approve / revise
                         │
                         ▼
                  IMPLEMENTER
                         │
                         ▼
              deterministic checks
                         │
                  failure ─────┐
                         │      │
                         ▼      │
               REVIEW ORCHESTRATOR
                         │
           ┌─────────────┼─────────────┐
           ▼             ▼             ▼
     correctness     architecture     tests
           │             │             │
           └─────────────┼─────────────┘
                         │
                conditional reviewers
                         │
              security/dependency/
                    migration/docs
                         │
                         ▼
                      findings
                         │
               problems ──────► implementer
                         │
                      clean
                         │
                         ▼
                         PR
                         │
                         ▼
                     GitHub CI
                         │
                    failure loop
                         │
                         ▼
                     STAGING
                         │
                   smoke / E2E
                         │
                         ▼
                  SPEC RECONCILIATION
                         │
                         ▼
                  RISK ASSESSMENT
                           │
                           ▼
                    HUMAN MERGE
                           │
                           ▼
                      PRODUCTION

```

---

# 44. Runtime validation

Passing CI does not guarantee production correctness.

When applicable, deployments should include:

```text
staging
smoke tests
E2E tests
health checks
canary
error monitoring
rollback

```

---

# 45. Production readiness

A project is not considered production-ready solely because it compiles and tests pass.

Relevant aspects include:

```text
deployment
configuration
secret handling
logging
metrics
tracing
health checks
alerting
backups
restore testing
rollback
incident response
resource limits
security
dependency management
data migrations

```

---

# 46. Observability

Agents modifying production behavior must consider whether new observability is needed.

Questions:

```text
How will failure be detected?

Can operators distinguish expected and unexpected failures?

Are important state transitions visible?

Are logs actionable?

Are sensitive values excluded?

Does a new critical path require metrics?

```

---

# 47. Model routing

Not all work requires the most expensive or most intelligent model.

The router can use smaller models for:

```text
classification
simple repository search
mechanical edits
basic test generation
documentation
changelog generation
simple dependency investigation

```

More powerful models for:

```text
ambiguous specifications
architecture
complex debugging
dependency migrations
security
cross-module reasoning
final adversarial review

```

---

# 48. Subscription-aware routing

When Claude and Codex are both available through a subscription:

an asymmetric strategy is preferable.

Example:

```text
Codex
├── exploration
├── routine implementation
├── tests
├── mechanical refactors
└── documentation

Claude
├── specification clarification
├── architecture
├── difficult reasoning
├── plan challenge
└── final adversarial review

```

The actual routing must remain configurable based on:

```text
quota
task
model capability
availability
user preference

```

---

# 49. Token efficiency

Instructions must be designed to minimize unnecessary context.

Principles:

```text
short root instructions
progressive disclosure
file-scoped instructions
task-specific skills
summaries instead of history dumps
persistent artifacts
independent small review contexts

```

Do not systematically inject:

```text
all architecture docs
all policies
all previous discussions
entire project history

```

---

# 50. Persistent state

Important decisions must never exist only in an agent's conversation.

They must end up in:

```text
issue
spec
ADR
code
tests
documentation
PR

```

This way an agent can be replaced or restarted without losing the project state.

---

# 51. Tool architecture

No orchestrator is currently considered mandatory.

The solutions explored include in particular:

```text
Open SWE
CAO
OpenHands
Kiro
Claude/Codex orchestration projects
GitHub coding agents
local custom orchestration

```

CAO was identified as technically interesting but is not considered an established product decision.

---

# 52. Orchestrator abstraction

The pipeline must be able to work with different backends.

Conceptually:

```text
              Agent Runtime Interface
                        │
       ┌────────────────┼────────────────┐
       ▼                ▼                ▼
   Claude Code        Codex          Future agent

```

The orchestration must not require specifications or policies to know which runtime is used.

---

# 53. CLI-native execution preference

When possible, prefer the official CLIs:

```text
claude
codex

```

rather than extracting or directly manipulating OAuth tokens.

This:

```text
preserves provider authentication
reduces credential handling
uses existing subscriptions
reduces implementation fragility

```

---

# 54. Avoid hidden API costs

The system must make it explicitly visible when an action:

```text
uses subscription quota
uses paid API
uses external cloud compute

```

The default mode must be able to work without additional API cost.

---

# 55. Candidate repository structure

```text
repo/
│
├── AGENTS.md
├── CLAUDE.md
├── README.md
├── SECURITY.md
│
├── specs/
│   ├── product/
│   ├── features/
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
│       └── incident-response.md
│
├── .agents/
│   ├── skills/
│   └── personas/
│
├── scripts/
│   ├── check
│   ├── test
│   ├── security
│   └── verify
│
└── .github/
    ├── ISSUE_TEMPLATE/
    ├── workflows/
    ├── CODEOWNERS
    └── pull_request_template.md

```

---

# 56. Stack overlays

The system must separate:

```text
universal engineering rules

```

from:

```text
Python-specific rules
TypeScript-specific rules
Rust-specific rules
React-specific rules
FastAPI-specific rules
etc.

```

Example:

```text
.agent-standard/
    core/

overlays/
    python/
    typescript/
    react/
    fastapi/

```

This must make it possible to compose a new project without duplicating all the instructions.

---

# 57. Greenfield bootstrap

For an empty repository:

```text
product description
       ↓
stack selection
       ↓
repository bootstrap
       ↓
engineering constitution
       ↓
architecture draft
       ↓
production baseline
       ↓
initial feature specs
       ↓
agent implementation

```

The bootstrap must immediately generate the essential safeguards rather than adding them after several weeks of development.

---

# 58. Existing approaches worth borrowing from

## GitHub Spec Kit

Interesting for:

```text
constitution
specify
clarify
plan
tasks
analyze
implement
converge

```

The spec/code convergence concept is particularly relevant.

However, the product does not necessarily have to depend directly on Spec Kit.

---

## Open SWE

Interesting for:

```text
issue → autonomous worker → PR
persistent agent threads
follow-up
review
CI feedback loops

```

Less interesting if its execution requires additional API consumption.

---

## OpenHands

Interesting for:

```text
agent skills
automation
sandboxing
review separation
progressive instructions

```

---

## Kiro

Interesting as an integrated example:

```text
requirements
design
tasks
implementation

```

But too tightly coupled to a specific platform to become the core of the system.

---

## Orca

Remains the preferred human cockpit.

---

# 59. Agent-first anti-patterns

The system must explicitly avoid:

```text
one giant AGENTS.md

one agent doing implementation + approval

trusting model confidence

specifying implementation months in advance

letting specs silently become stale

letting agents disable checks

dependency addition without evaluation

dependency migration in one huge rewrite

irreversible DB migrations in one deploy

every change triggering every reviewer

human confirmation for trivial decisions

hidden paid API usage

critical state stored only in chat history

tool/vendor lock-in

massive process before the project needs it

```

---

# 60. Desired developer experience

The target experience should be close to:

```text
I describe what I want.

The system helps clarify it.

I mark the feature READY.

Agents investigate the repository.

They create and review a plan.

They implement it.

They test it.

Independent agents review it.

They fix discovered problems.

CI verifies the result.

The feature is deployed to staging.

Acceptance is checked.

Low-risk changes progress automatically.

I am interrupted only if:
- product intent is ambiguous,
- risk is high,
- or an irreversible decision is required.

```

---

# 61. Target human workflow

The user's daily routine should ideally be:

```text
Orca
+
GitHub Project
+
Issues
+
PRs

```

and not a set of specialized dashboards.

The user must be able to:

```text
see current work
see blocked work
reply to agents
inspect diff
take over locally
request another review
approve high-risk changes

```

---

# 62. Definition of Done

A feature is `DONE` only when:

```text
spec satisfied
tests pass
required reviews pass
documentation synchronized
dependencies acceptable
migrations verified
CI green
runtime validation successful
spec reconciliation completed

```

For deployed features:

```text
deployment succeeded
health checks pass
rollback path exists

```

---

# 63. Success metrics

The system will be considered effective if, in the long run:

```text
most R0 changes require no human intervention

most R1 changes require only product acceptance

R2 changes clearly identify why human approval is required

agents rarely need repository conventions re-explained

spec/code drift is detected

dependency quality does not degrade over time

security-sensitive changes receive specialized review

agent/model replacements do not require repository redesign

```

Possible measures:

```text
human interventions per PR
agent fix-loop count
CI first-pass rate
escaped defects
rollback rate
spec reconciliation failures
security findings after merge
dependency age
time READY → merged
cost per feature
subscription/API usage

```

---

# 64. MVP

The first version must not try to build the whole software factory.

Proposed MVP:

```text
AGENTS.md constitution

core policy documents

spec template

issue template

spec lifecycle

risk classification

planner instructions

implementer instructions

reviewer instructions

security-review instructions

dependency-evaluation instructions

GitHub Actions quality gates

Claude Code + Codex compatibility

GitHub state machine

basic fix/review loop

```

The pipeline can initially be triggered manually from Orca.

---

# 65. Phase suivante

After the model is validated:

```text
automatic READY detection

automatic agent dispatch

parallel specialized reviews

subscription-aware model routing

automatic fix loops

staging deployment

spec convergence

risk-based review before human merge

production validation

continuous dependency maintenance

```

---

# 66. Open questions

The following choices are deliberately left open.

### Orchestration engine

Build a thin in-house layer or adapt:

```text
CAO
Open SWE
other existing orchestrator
GitHub-native workflows

```

### Specification engine

Use directly:

```text
Spec Kit

```

or only borrow its conceptual model.

### GitHub Projects

Determine whether the GitHub Project is really the main state machine or only a view.

### Local versus always-on execution

Decide whether the orchestration runs:

```text
on developer workstation
home server
GitHub runner
small dedicated machine
hybrid

```

### Merge review threshold

Determine which evidence a human needs to merge R1 changes confidently, without weakening required checks or review.

### Product acceptance

Determine which features still require human visual/functional validation.

---

# 67. Long-term product direction

The system may eventually become an installable repository/template:

```text
agentic-repo-standard

```

or a CLI:

```text
agentrepo init

agentrepo doctor

agentrepo spec

agentrepo run

agentrepo review

agentrepo status

```

But the CLI must not become mandatory to work with the project.

The artifact format must remain simple:

```text
Markdown
YAML
Git
GitHub
shell commands
standard CI

```

so that the system remains understandable and recoverable without proprietary tooling.

---

# 68. Core product principle

The goal is not:

> to make Claude code automatically.

Nor:

> to make Codex code automatically.

The goal is:

> to build repositories in which interchangeable agents can reliably develop, test, document, review, maintain and ship software, with the human focused on the product and on high-impact decisions.

The quality of the system therefore rests on five pillars:

```text
SPECIFICATION
     +
ENGINEERING POLICIES
     +
INDEPENDENT REVIEW
     +
DETERMINISTIC VERIFICATION
     +
RISK-BASED HUMAN CONTROL

```

and not on the quality of a single agent.

---

# 69. North Star

In the long run, the ideal operation is:

```text
                         HUMAN
                           │
                    product direction
                           │
                           ▼
                     SPECIFICATION
                           │
                           ▼
                   READY WORK QUEUE
                           │
                           ▼
              ┌────────────────────────┐
              │  AGENT ENGINEERING     │
              │                        │
              │ investigate            │
              │ plan                   │
              │ implement              │
              │ test                   │
              │ document               │
              │ review                 │
              │ fix                    │
              └───────────┬────────────┘
                          │
                          ▼
               DETERMINISTIC GATES
                          │
                          ▼
                    RUNTIME PROOF
                          │
                          ▼
                      RISK GATE
                    /           \
               reversible      critical
                   │               │
                   ▼               ▼
              automation         HUMAN
                    \             /
                     \           /
                        PRODUCTION

```

The product must move toward a software factory in which:

**the human governs, the agents execute, and automatic proof controls.**
