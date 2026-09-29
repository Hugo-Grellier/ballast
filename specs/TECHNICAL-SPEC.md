# Agent-First Repository Operating System

**Technical Specification v0.1**  
**Status:** Draft  
**Date:** 2026-09-24  
**Depends on:** Product Specification v0.1

---

# 1. Purpose

Cette spécification définit l’architecture technique d’un standard de repository permettant à des agents de développement interchangeables de transformer des spécifications produit en logiciel production-ready avec un minimum d’intervention humaine.

Le système doit fournir :

- une structure standard de repository ;
- un format de spécification ;
- une state machine de travail ;
- des contrats pour les différents rôles agents ;
- des politiques engineering versionnées ;
- des quality gates déterministes ;
- des reviews agentiques spécialisées ;
- une gestion du risque ;
- un mécanisme d’escalade humaine ;
- une abstraction de l’orchestrateur ;
- une intégration GitHub ;
- une intégration avec des agents CLI tels que Claude Code et Codex ;
- un chemin progressif vers l’automatisation complète.

Le système ne doit pas dépendre d’un agent, d’un modèle ou d’un orchestrateur particulier.

---

# 2. Normative language

Les termes suivants sont normatifs :

- **MUST** : obligatoire ;
- **MUST NOT** : interdit ;
- **SHOULD** : recommandé sauf raison documentée ;
- **SHOULD NOT** : déconseillé sauf raison documentée ;
- **MAY** : optionnel.

---

# 3. Architectural principles

## 3.1 Repository-owned process

Toutes les règles nécessaires pour modifier correctement un projet MUST être présentes ou référencées depuis le repository.

Les conversations agentiques ne sont pas une source de vérité durable.

Les décisions importantes MUST être persistées dans l’un des artifacts suivants :

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

Le système MUST pouvoir utiliser plusieurs moteurs :

```text
Claude Code
Codex CLI
GitHub Copilot
OpenCode
future agents

```

Le changement de moteur MUST NOT nécessiter de réécrire :

```text
specifications
engineering policies
architecture documentation
tests
GitHub workflow

```

---

## 3.3 Deterministic verification first

Tout comportement vérifiable automatiquement SHOULD être vérifié automatiquement.

Un reviewer agentique ne remplace pas :

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

Un agent ayant implémenté un changement MUST NOT être le seul mécanisme chargé de l’approuver.

Les reviews critiques SHOULD être exécutées dans un contexte séparé de celui de l’implementer.

---

## 3.5 Progressive disclosure

Les instructions globales MUST rester courtes.

Les procédures spécialisées MUST être chargées uniquement lorsqu’elles sont pertinentes.

---

# 4. High-level architecture

Le système est divisé en cinq plans.

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

GitHub est le control plane de référence initial.

Il stocke :

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

GitHub ne doit pas nécessairement stocker le contenu complet des specifications complexes.

---

# 6. Artifact plane

Le repository constitue la source versionnée des artifacts durables.

Structure cible :

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

Cette structure est un baseline et MAY être adaptée au stack.

---

# 7. Instruction hierarchy

L’ordre de résolution des instructions est :

```text
1. platform / organization policy
2. root AGENTS.md
3. directory-scoped AGENTS.md
4. task-specific specification
5. relevant skill
6. implementation plan
7. local implementation conventions

```

Une instruction de niveau inférieur MUST NOT silencieusement contredire une instruction de niveau supérieur.

En cas de contradiction, l’agent MUST signaler le conflit.

---

# 8. Root [AGENTS.md](http://AGENTS.md) contract

Le [`AGENTS.md`](http://AGENTS.md) racine SHOULD rester inférieur à environ 250 lignes.

Il définit uniquement :

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

Il ne doit pas contenir les procédures complètes de :

```text
security review
dependency evaluation
database migration
release
documentation review

```

Ces procédures appartiennent aux skills.

---

# 9. [CLAUDE.md](http://CLAUDE.md) and provider-specific files

Lorsque possible :

```text
CLAUDE.md → AGENTS.md

```

ou équivalent fonctionnel.

Les fichiers provider-specific SHOULD uniquement contenir :

```text
provider-specific invocation
tool-specific caveats
compatibility shim

```

Ils MUST NOT dupliquer toute la politique engineering.

---

# 10. Specification storage

Les features significatives sont stockées sous :

```text
specs/features/<work-id>-<slug>/

```

Exemple :

```text
specs/features/0423-project-sharing/
├── spec.md
├── plan.md
├── tasks.md
├── verification.md
└── decisions.md

```

Tous ces fichiers ne sont pas obligatoires pour une petite feature.

---

# 11. Specification metadata

[`spec.md`](http://spec.md) SHOULD commencer par un frontmatter structuré.

Exemple :

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

Champs minimaux :

```text
id
title
status
risk
issue

```

---

# 12. Specification states

Valeurs autorisées :

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

Transition nominale :

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

La state machine opérationnelle GitHub peut être plus détaillée que la specification.

Baseline :

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

Les transitions SHOULD être automatisables.

Exemples :

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

Un agent MUST NOT marquer `DONE` si les conditions de Definition of Done ne sont pas satisfaites.

---

# 15. Issue contract

Une issue liée à une specification complexe SHOULD contenir :

```yaml
type: feature
risk: R1
spec: specs/features/0423-project-sharing/spec.md
status: READY

```

Le body contient au minimum :

```text
goal
user/business context
links
open questions

```

L’issue reste la surface de discussion.

Le repository reste la source durable de la spec.

---

# 16. Small work items

Pour un changement suffisamment petit, toute la spec MAY rester dans l’issue.

Critères typiques :

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

Une feature spec SHOULD contenir :

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

La spec SHOULD éviter les détails d’implémentation.

---

# 18. Implementation plan format

[`plan.md`](http://plan.md) est produit après exploration du repository.

Il contient :

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

[`tasks.md`](http://tasks.md) découpe le plan en unités exécutables.

Chaque task SHOULD avoir :

```yaml
id: T-01
status: pending
risk: low
depends_on: []

```

et décrire une unité de travail testable.

Une task ne doit pas uniquement être :

```text
implement backend

```

Elle doit être suffisamment précise pour produire un résultat vérifiable.

---

# 20. Verification artifact

[`verification.md`](http://verification.md) contient la preuve finale.

Structure indicative :

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

Spec Kit MAY être utilisé comme implémentation de la couche SDD.

Mapping :

```text
Spec Kit constitution
→ project principles

speckit specify
→ spec.md

speckit plan
→ plan.md

speckit tasks
→ tasks.md

speckit implement
→ implementation phase

speckit converge
→ verification/reconciliation

```

Le système MUST néanmoins conserver ses artifacts dans des formats suffisamment standards pour pouvoir abandonner Spec Kit ultérieurement.

Spec Kit est donc une implementation possible, pas un format propriétaire obligatoire.

---

# 22. Agent execution model

Tous les agents sont vus comme implémentant une abstraction logique :

```text
AgentRuntime

```

Interface conceptuelle :

```text
run(role, task, context, permissions) -> result
continue(run_id, feedback) -> result
cancel(run_id)
status(run_id)

```

Le runtime concret peut être :

```text
Claude Code CLI
Codex CLI
OpenCode
Copilot
future service

```

---

# 23. Execution isolation

Chaque tâche d’implémentation SHOULD s’exécuter dans :

```text
isolated worktree
or
isolated sandbox

```

Le travail agentique ne SHOULD pas s’exécuter directement dans le checkout principal de l’utilisateur.

Nom de branche recommandé :

```text
agent/<work-id>-<slug>

```

Exemple :

```text
agent/F-0423-project-sharing

```

---

# 24. Orca integration

Orca est considéré comme une human interface locale.

Le système SHOULD être compatible avec :

```text
worktrees created by Orca
Claude Code launched by Orca
Codex launched by Orca
local PR inspection
manual takeover

```

L’orchestrateur MUST NOT exiger que l’utilisateur quitte Orca pour effectuer une intervention manuelle.

---

# 25. Agent roles

Rôles logiques minimum :

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

Rôles conditionnels :

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

Entrées :

```text
issue/spec
repository metadata
risk policy

```

Sorties :

```yaml
work_type: feature
risk: R1
required_reviews:
  - correctness
  - tests
requires_spec: true
requires_human_approval: false

```

Le triage agent ne modifie pas le code.

---

# 27. Planner

Le planner MUST :

```text
read the specification
inspect existing code
inspect relevant ADRs
inspect applicable policies
identify affected interfaces
identify risks
produce plan.md

```

Le planner SHOULD utiliser un modèle capable de raisonnement fort lorsque l’impact est important.

---

# 28. Plan reviewer

Le plan reviewer travaille avec un contexte séparé.

Il vérifie :

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

Verdicts :

```text
APPROVED
CHANGES_REQUIRED
BLOCKED

```

---

# 29. Implementer

L’implementer reçoit :

```text
spec.md
approved plan.md
tasks.md
applicable policies
relevant existing code

```

Il MUST :

```text
implement only approved scope
update tests
update relevant docs
run local verification
record deviations

```

Il MUST NOT modifier la specification produit afin de faire correspondre celle-ci à son implémentation.

---

# 30. Fix agent

Un fix agent reçoit :

```text
current diff
verification failures
review findings

```

Il doit corriger les findings sans introduire de scope supplémentaire.

La boucle est bornée.

Exemple :

```text
max_review_fix_cycles = 3

```

Après dépassement :

```text
BLOCKED

```

ou escalade vers un modèle plus puissant.

---

# 31. Review orchestrator

Le review orchestrator ne juge pas lui-même nécessairement le code.

Il détermine les reviewers nécessaires en fonction du diff et du risque.

Pseudo-règles :

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

Chaque reviewer produit un format structuré.

Exemple :

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

Severities :

```text
info
low
medium
high
critical

```

---

# 33. Review policy

Les findings :

```text
critical
high

```

MUST bloquer la progression.

Les findings `medium` SHOULD bloquer sauf acceptation explicite documentée.

`low` MAY être reporté dans une issue technique.

---

# 34. Risk engine

Le risque est calculé à partir :

```text
user declaration
triage agent
changed files
changed subsystem
dependency diff
database diff
security-sensitive patterns

```

Le résultat le plus conservateur SHOULD gagner.

---

# 35. Risk levels

## R0

Faible risque.

Exemples :

```text
docs
formatting
tests only
minor isolated internal fix

```

Peut être auto-merge.

---

## R1

Risque engineering standard.

Exemples :

```text
normal feature
UI behavior
new endpoint
internal refactor
non-destructive schema extension

```

Peut progresser sans humain si toutes les gates passent.

---

## R2

Risque élevé.

Exemples :

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

MUST nécessiter une décision humaine avant merge ou production.

---

# 36. Risk escalation

Un changement initialement R0/R1 MUST être reclassifié si l’implémentation révèle :

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

L’orchestrateur SHOULD éviter d’interrompre l’humain pour les problèmes résolubles techniquement.

Escalade seulement pour :

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

---

# 38. Deterministic verification API

Le repository SHOULD exposer une commande stable :

```bash
./scripts/verify

```

ou équivalent.

Cette commande constitue le contrat principal entre agents et CI.

Elle SHOULD regrouper les vérifications adaptées au projet.

---

# 39. Verification stages

Baseline logique :

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

Tous les projets ne sont pas obligés d’avoir toutes les étapes.

---

# 40. Local vs CI checks

Les checks sont divisés en :

```text
FAST
FULL

```

Exemple :

```bash
./scripts/check
./scripts/verify

```

`check` :

```text
format
lint
typecheck
targeted tests

```

`verify` :

```text
all checks
integration
security
build
E2E

```

---

# 41. Coverage policy

Le projet MAY définir un seuil de couverture.

Mais coverage seul MUST NOT être considéré comme une preuve de qualité.

Le test reviewer recherche également :

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

Avant une migration ou un refactor comportemental important :

```text
existing behavior
→ characterization tests
→ modification
→ equivalence validation

```

Si le comportement existant est incorrect, la différence doit être explicitement liée à la specification.

---

# 43. Security architecture

La sécurité est divisée en :

```text
static security
agentic security review
runtime security
execution isolation
supply chain security

```

---

# 44. Static security baseline

Selon le stack :

```text
SAST
dependency vulnerability scan
secret scan
container scan
license scan
IaC scan

```

Les outils exacts restent stack-specific.

---

# 45. Agent security review

Une security review est obligatoire lorsqu’un diff touche une frontière de confiance.

Le reviewer analyse notamment :

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

Les personas SHOULD avoir des permissions différentes.

Exemple :

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

Un reviewer SHOULD être read-only.

---

# 47. Production credentials

Les agents MUST NOT recevoir automatiquement :

```text
production database credentials
production shell access
root cloud credentials
organization-wide tokens

```

Les credentials sensibles MUST être séparés du contexte agentique.

---

# 48. Dependency evaluation workflow

Tout ajout d’une dépendance significative déclenche :

```text
dependency-evaluation

```

Output :

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

Avant introduction, l’agent SHOULD vérifier :

```text
latest stable version
release recency
maintenance activity
runtime support
deprecated status
security advisories
license

```

Il MUST NOT copier automatiquement un snippet utilisant une API obsolete simplement parce qu’il apparaît dans une ancienne documentation ou Stack Overflow.

---

# 50. Dependency updates

Renovate, Dependabot ou équivalent SHOULD assurer la détection automatique des mises à jour.

Policy indicative :

```text
patch
→ auto PR
→ auto merge if safe

minor
→ auto PR
→ tests + dependency review

major
→ migration workflow

```

---

# 51. Dependency migration workflow

Une migration de dépendance suit :

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

Un remplacement massif en un seul commit SHOULD être évité.

---

# 52. Database migration workflow

Par défaut :

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

Les migrations destructives simultanées à la suppression du code associé SHOULD être interdites pour les systèmes déployés progressivement.

---

# 53. Documentation architecture

Trois catégories principales :

```text
product/domain
engineering
operations

```

Le code ne doit pas devenir l’unique documentation de comportements complexes.

---

# 54. Documentation update detection

Un changement SHOULD déclencher un docs review lorsqu’il modifie :

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

Nom :

```text
docs/architecture/adr/NNNN-short-title.md

```

Sections :

```text
Status
Context
Decision
Alternatives
Consequences
Migration implications
References

```

Un ADR accepté ne doit pas être réécrit pour masquer l’historique.

Il est remplacé par un nouvel ADR qui le `supersedes`.

---

# 56. Spec reconciliation

Avant validation :

```text
spec
↕
implementation
↕
tests
↕
documentation

```

Le reconciliation agent produit :

```text
CONVERGED
PARTIAL
FAILED

```

Une feature n’est pas `validated` tant que la reconciliation n’est pas `CONVERGED`, sauf waiver explicite.

---

# 57. CI architecture

Workflow recommandé :

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

Les jobs SHOULD être parallélisés lorsque possible.

---

# 58. Required checks

Le repository MUST configurer ses branch/ruleset protections pour empêcher le merge si les checks obligatoires échouent.

Un agent ne doit pas pouvoir contourner cela via une simple modification du workflow dans sa PR.

Les changements de CI critiques SHOULD être considérés au moins R1, souvent R2.

---

# 59. PR contract

Une PR générée par agent SHOULD contenir :

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

Lorsqu’un agent produit une modification, son rôle SHOULD être visible.

Exemple :

```text
Implemented-by: codex/implementer
Reviewed-by: claude/correctness
Security-reviewed-by: claude/security

```

Cela peut vivre dans :

```text
PR body
check output
automation metadata

```

sans nécessairement polluer les commits.

---

# 61. Fix loop

Pipeline :

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

La boucle MUST être bornée.

Après N échecs :

```text
upgrade model
or
human escalation

```

---

# 62. Model routing interface

Le routeur reçoit :

```yaml
role: planner
risk: R1
complexity: high
context_size: medium
requires_tools: true

```

Il retourne :

```yaml
provider: anthropic
runtime: claude-code
tier: strong

```

Le provider concret n’est pas codé dans les specs.

---

# 63. Model tiers

Trois niveaux logiques :

```text
FAST
STANDARD
STRONG

```

FAST :

```text
classification
simple edits
search
changelog
formatting

```

STANDARD :

```text
normal implementation
tests
routine review

```

STRONG :

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

Le router SHOULD pouvoir déclarer :

```yaml
billing_mode:
  - subscription
  - api
  - local

```

Configuration exemple :

```yaml
providers:
  claude:
    runtime: claude-code
    billing: subscription

  codex:
    runtime: codex-cli
    billing: subscription

```

Le mode par défaut SHOULD préférer `subscription` lorsque demandé par l’utilisateur.

---

# 65. Paid API guard

Une exécution API payante SHOULD être explicitement autorisable.

Exemple :

```yaml
allow_metered_api: false

```

Si aucun runtime compatible n’est disponible :

```text
BLOCK

```

plutôt que fallback silencieux vers une API facturée.

---

# 66. Orchestrator requirements

L’orchestrateur retenu ou développé MUST fournir au minimum :

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

Il SHOULD fournir :

```text
parallel runs
persistent state
resume
web/CLI inspection
agent messaging

```

---

# 67. Orchestrator non-requirements

Il n’est pas nécessaire que l’orchestrateur :

```text
own the product backlog
replace GitHub
replace Orca
store specifications
provide its own editor

```

Le projet doit éviter de créer un deuxième système de project management.

---

# 68. Orchestration adapter

Interface interne conceptuelle :

```python
class AgentAdapter:
    start(...)
    send(...)
    status(...)
    stop(...)
    collect_result(...)

```

Adapters possibles :

```text
ClaudeCodeAdapter
CodexAdapter
OpenCodeAdapter
RemoteAgentAdapter

```

---

# 69. Local orchestrator implementation

Si une couche d’orchestration maison devient nécessaire, Python est le choix initial recommandé pour le prototype en raison de :

```text
subprocess management
GitHub integration
structured data
rapid iteration
cross-platform support
existing user preference

```

Ce choix n’est pas architecturalement obligatoire.

---

# 70. Git worktree strategy

Chaque implementer SHOULD travailler dans un worktree distinct.

Exemple :

```text
.worktrees/
├── F-0423-implementation/
├── F-0424-bugfix/
└── F-0425-review-fix/

```

Deux agents ne SHOULD pas modifier simultanément le même worktree.

---

# 71. Parallelism policy

Les tâches peuvent être parallélisées uniquement si leurs write sets sont suffisamment indépendants.

Safe :

```text
backend implementation
+
read-only security review of another PR

```

Potentially unsafe :

```text
two agents editing same migration
two agents modifying same API contract

```

Le planner SHOULD identifier les possibilités de parallélisme.

---

# 72. Runtime validation

Après merge ou avant production selon le projet :

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

Toute feature R1/R2 SHOULD répondre avant déploiement :

```text
How do we rollback code?

How do we rollback data?

Can the old version run against the new schema?

What happens to writes made after deployment?

```

---

# 74. Production release

Pipeline cible :

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

Pour chaque nouveau chemin critique, le planner doit déterminer si sont nécessaires :

```text
logs
metrics
traces
health check
alert
dashboard

```

Une feature invisible en cas de panne n’est pas nécessairement production-ready.

---

# 76. Agent pipeline observability

Le système lui-même doit produire :

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

Aucune chaîne de pensée privée n’est requise.

Le système conserve uniquement les outputs opérationnels nécessaires.

---

# 77. Audit artifact

Chaque work item MAY produire :

```text
.agent-runs/<work-id>/summary.json

```

Exemple :

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

Ce fichier MAY être stocké hors Git si trop volatile.

---

# 78. Token efficiency

Le context builder ne charge que :

```text
root instructions
task spec
approved plan
directly applicable policy
relevant architecture docs
relevant code

```

Il SHOULD éviter :

```text
entire docs tree
all historical issues
all ADRs
full git history
all previous agent transcripts

```

---

# 79. Context retrieval

Le contexte est obtenu en priorité par :

```text
explicit references
repo search
dependency graph
code navigation
directory-scoped instructions

```

et non par chargement complet du repository dans le prompt.

---

# 80. Policy versioning

Les policies sont versionnées avec le code.

Lorsqu’une policy change de manière importante, les specs `READY` SHOULD être réévaluées.

Les features déjà `VALIDATED` ne sont pas automatiquement invalidées.

---

# 81. Policy maintenance

Un job périodique MAY analyser :

```text
obsolete tool references
obsolete dependency rules
dead documentation links
unsupported runtime versions
outdated security baseline
stale AGENTS instructions

```

Résultat :

```text
maintenance PR

```

---

# 82. Definition of Ready

Une feature est `READY` lorsque :

```text
goal understood
scope bounded
acceptance criteria defined
blocking questions resolved
dependencies identified
initial risk assigned

```

Elle n’a pas besoin d’avoir un implementation plan à ce stade.

---

# 83. Definition of Planned

Une feature est `PLANNED` lorsque :

```text
repository inspected
plan produced
migration strategy defined
test strategy defined
plan independently reviewed

```

---

# 84. Definition of Implemented

Une feature est `IMPLEMENTED` lorsque :

```text
code complete
local checks pass
tests updated
required docs updated
PR created

```

Cela ne signifie pas `DONE`.

---

# 85. Definition of Validated

Une feature est `VALIDATED` lorsque :

```text
CI green
required reviews pass
spec reconciliation converged
required runtime verification passes

```

---

# 86. Definition of Done

Une work item est `DONE` lorsque :

```text
validated
merged
required deployment completed
post-deploy checks pass
follow-up work explicitly tracked

```

---

# 87. MVP v0.1

La première implementation du standard couvre uniquement :

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

Pas d’orchestration automatique obligatoire.

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

Cette phase sert à valider les contrats avant d’automatiser.

---

# 89. v0.2 target

Automatiser :

```text
READY detection
agent dispatch
worktree creation
structured role invocation
review orchestration
fix loops
GitHub status updates

```

L’humain reste nécessaire pour tous les merges.

---

# 90. v0.3 target

Ajouter :

```text
R0 auto merge
selected R1 auto merge
staging automation
runtime validation
risk-based human gates
subscription-aware routing

```

---

# 91. v1.0 target

Objectif :

```text
product specification
      ↓
mostly autonomous engineering factory
      ↓
production

```

avec intervention humaine principalement pour :

```text
product ambiguity
R2 decisions
acceptance of major behavior
exception handling

```

---

# 92. Reference implementation strategy

Ne pas commencer par construire un gros orchestrateur.

Ordre recommandé :

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

Ces choix sont des defaults, pas des hard dependencies.

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

Non décidé en v0.1 :

```text
CAO
Open SWE
OpenHands
custom orchestrator
GitHub-native agent orchestration

```

Aucun ne doit être requis pour adopter le standard.

---

# 95. Compatibility requirement

Le système MUST pouvoir fonctionner dans sa forme dégradée uniquement avec :

```text
Git
GitHub
Markdown
shell
one coding agent
CI

```

Toutes les autres briques améliorent l’automatisation mais ne doivent pas rendre le repository incompréhensible sans elles.

---

# 96. Failure philosophy

Le système préfère :

```text
blocked with explicit reason

```

à :

```text
silent assumption

```

Exemples de conditions de blocage :

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

Cette architecture ne cherche pas encore à :

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

Le standard sera considéré techniquement viable lorsqu’un repository pilote démontre :

1. une feature non triviale écrite en spec ;
2. un plan généré par un agent ;
3. une implementation par un autre agent ;
4. des tests et quality gates automatiques ;
5. une review indépendante ;
6. une correction automatique d’au moins un finding ;
7. une reconciliation spec/code ;
8. une PR complète ;
9. aucun contexte conversationnel indispensable perdu entre les étapes ;
10. remplacement de l’implementer Claude ↔ Codex sans modifier la spec ou le workflow ;
11. aucune consommation API payante lorsqu’un mode subscription-only est demandé ;
12. possibilité de reprendre manuellement le travail dans Orca.

---

# 99. Recommended pilot

LoreForge est un bon candidat pour valider le système.

Phase pilote recommandée :

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

Ne pas automatiser davantage avant d’avoir exécuté plusieurs features de cette manière.

Le résultat de cette expérimentation doit alimenter la Technical Specification v0.2.

---

# 100. Core technical invariant

Le cœur du système peut être résumé ainsi :

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

Aucune étape ne doit dépendre exclusivement de la confiance dans la réponse de l’agent précédent.

---

# 101. Architectural north star

À terme :

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

L’orchestrateur est remplaçable.

Les modèles sont remplaçables.

Les IDE sont remplaçables.

Les artifacts, policies, preuves et contrats du repository constituent le système durable.