# Agent-First Repository Operating System

**Version:** 0.1  
**Status:** Draft  
**Date:** 2026-09-24

## 1. Vision

Créer un système réutilisable permettant de partir d’un dépôt vide et d’arriver à une application réellement production-ready, avec un minimum d’intervention humaine sur l’implémentation.

Le développeur humain agit principalement comme :

- product owner ;
- décideur fonctionnel ;
- arbitre des choix difficiles ou irréversibles ;
- validateur occasionnel des changements à haut risque.

Les agents prennent en charge autant que possible :

- clarification de spécification ;
- exploration du repository ;
- planification technique ;
- implémentation ;
- tests ;
- documentation ;
- revue de code ;
- revue architecture ;
- revue sécurité ;
- gestion des dépendances ;
- migrations ;
- corrections après CI/review ;
- création et maintenance des PR ;
- validation en staging ;
- préparation des releases ;
- maintenance continue.

L’objectif n’est pas de créer un nouvel IDE ni d’enfermer le workflow dans un modèle particulier.

Le repository lui-même doit contenir suffisamment de règles, de contexte, de procédures et de garde-fous pour permettre à différents agents de travailler dessus de manière fiable.

---

# 2. Objectif principal

Permettre le workflow suivant :

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

Avec intervention humaine uniquement lorsque celle-ci apporte une vraie valeur.

---

# 3. Principes fondamentaux

## 3.1 Human-driven, agent-built

L’humain définit principalement :

```text
WHAT
WHY
constraints
priorities
product decisions
acceptable risk

```

Les agents déterminent principalement :

```text
HOW
implementation details
file changes
tests
refactors
documentation updates

```

Le système doit éviter de transformer l’humain en superviseur permanent des agents.

---

## 3.2 Repository as operating system

Le repository doit être autonome.

Un nouvel agent arrivant sur le projet doit pouvoir déterminer :

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

sans dépendre d’une conversation historique.

---

## 3.3 Agents must remain replaceable

Le système ne doit dépendre fondamentalement ni de :

- Claude Code ;
- Codex ;
- Open SWE ;
- CAO ;
- Copilot ;
- Cursor ;
- Kiro ;
- Orca.

Ces outils doivent être considérés comme des moteurs interchangeables autour d’un contrat commun défini dans le repository.

---

## 3.4 Deterministic verification over agent confidence

Une réponse :

> “The implementation looks correct.”

n’est pas une preuve.

Lorsque quelque chose peut être validé automatiquement, la validation automatique est prioritaire.

Exemples :

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

Les agents interviennent surtout là où la vérification déterministe est insuffisante.

---

## 3.5 Independent review

L’agent qui écrit une modification ne doit pas être son unique reviewer.

Workflow minimal :

```text
Implementer
    ↓
automated checks
    ↓
independent reviewer

```

Pour les changements sensibles :

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

Tous les reviewers ne doivent pas nécessairement être exécutés pour chaque changement.

---

# 4. Contraintes économiques

Le système doit autant que possible exploiter les abonnements déjà payés par l’utilisateur.

Exemple actuel :

```text
Claude Code
→ abonnement Claude

Codex CLI
→ abonnement ChatGPT/Codex

```

Le système doit éviter par défaut les workflows nécessitant des appels API facturés séparément.

Conséquence importante :

les orchestrateurs utilisant exclusivement des API provider ne doivent pas être une dépendance architecturale essentielle.

Ils peuvent rester optionnels.

---

# 5. Interface utilisateur principale

## Orca IDE

Orca reste l’environnement quotidien de l’utilisateur.

Il sert principalement à :

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

Orca n’a pas besoin de devenir l’orchestrateur global.

Il représente le cockpit humain.

---

# 6. GitHub comme bus de coordination

GitHub devient la couche de coordination partagée entre :

```text
Human
Orca
agents
automation
CI
deployment

```

GitHub contient principalement :

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

L’orchestrateur doit pouvoir être remplacé sans changer cette couche.

---

# 7. Séparation entre état et artifacts

Principe :

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

Exemple :

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

Le système doit être spec-driven mais ne doit pas tomber dans le Big Design Up Front.

La specification fonctionne en rolling wave.

Trois horizons sont maintenus.

## NOW

Une feature environ.

Complètement spécifiée et prête à être implémentée.

## NEXT

Quelques features.

Le comportement produit est connu mais certains détails restent volontairement ouverts.

## LATER

Intentions, epics et directions produit.

Pas de design technique détaillé.

Exemple :

```text
A = IMPLEMENTING
B = READY
C = DRAFT
D = IDEA

```

Pendant l’implémentation de A, B peut être finalisée.

Il n’est pas nécessaire d’attendre la validation complète de A avant de réfléchir à B.

En revanche, les détails techniques de C/D ne doivent pas être figés prématurément.

---

# 9. Hiérarchie des specifications

Le produit doit distinguer clairement :

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

Une specification décrit :

```text
WHAT must be true
WHY it exists
constraints
expected behavior
acceptance criteria

```

Elle ne doit normalement pas imposer :

```text
class names
file names
implementation pattern
framework internals
specific functions

```

sauf lorsque ceux-ci constituent réellement une contrainte produit ou architecturale.

Exemple correct :

```text
Users can create projects.

A project must have a name.

Names are unique per user.

Creation requires authentication.

A failed creation must not leave partial persistent state.

```

Le plan d’implémentation répond ensuite :

```text
How should the current repository implement this requirement?

```

Il est produit après inspection du code existant.

---

# 11. Lifecycle d’une specification

Une spec possède un statut explicite.

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

Un agent ne doit normalement démarrer une implémentation automatique que depuis une specification `READY`.

---

# 12. Reconciliation spec ↔ implementation

Toute implémentation doit finir par une phase de reconciliation.

Questions :

```text
Did implementation satisfy every requirement?

Did implementation introduce behavior not described by the spec?

Did implementation reveal an invalid assumption?

Did architecture change?

Did future specifications become stale?

Was a deliberate deviation introduced?

```

Résultat possible :

```text
implementation wrong
→ fix implementation

spec wrong
→ update spec

new knowledge
→ update current/future specs

```

Le pipeline ne doit pas considérer :

```text
PR merged

```

comme équivalent à :

```text
feature complete

```

---

# 13. Pas de corrections cachées dans les specs suivantes

Une nouvelle feature ne doit pas discrètement réparer une feature précédente.

Si A doit être corrigé avant C :

```text
A2 correction

```

doit être explicitement créée.

Cela améliore :

```text
traceability
agent understanding
architecture history
change attribution

```

---

# 14. Issue ou fichier pour la spec ?

Les deux sont autorisés.

## Petite modification

Toute la specification peut vivre dans l’issue.

Exemple :

```text
Bug
Small UI change
Documentation
Minor behavior adjustment

```

## Feature significative

L’issue contient principalement :

```text
goal
summary
status
risk
links
discussion
ownership

```

La specification durable vit dans le repository.

Par exemple :

```text
specs/
└── 0423-project-sharing/
    ├── spec.md
    ├── plan.md
    ├── tasks.md
    └── verification.md

```

Avantages :

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

Un énorme [`AGENTS.md`](http://AGENTS.md) ne doit pas être utilisé.

Le système doit reposer sur progressive disclosure.

Architecture :

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

# 16. Root [AGENTS.md](http://AGENTS.md)

Le fichier racine contient uniquement les règles invariantes.

Taille cible :

```text
~150–250 lines

```

Il définit notamment :

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

Lorsqu’un compromis est nécessaire :

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

Sacrifier une priorité supérieure pour une priorité inférieure nécessite une justification explicite.

---

# 18. Forbidden agent behavior

Les agents ne doivent jamais silencieusement :

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

Les procédures détaillées vivent dans des skills dédiés.

Structure indicative :

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

Exemple :

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

La documentation doit expliquer principalement :

```text
WHY
contracts
constraints
invariants
non-obvious behavior
operational implications

```

Elle ne doit pas simplement reformuler le code.

---

# 22. Code comments

Commentaires requis principalement pour :

```text
non-obvious decisions
workarounds
security assumptions
performance constraints
protocol quirks
business invariants
upstream bugs

```

Mauvais commentaire :

```text
Increment counter by one.

```

Bon commentaire :

```text
Retry IDs must remain monotonic because downstream deduplication
uses them as an idempotency key.

```

---

# 23. TODO / FIXME

Un TODO ou FIXME doit expliquer :

```text
why the work remains
what blocks it
relevant issue/reference

```

Un TODO ne peut pas être utilisé pour différer silencieusement :

```text
security
data correctness
critical validation

```

---

# 24. ADR

Architecture Decision Record requis pour les décisions difficiles à inverser.

Exemples :

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

Un agent ne doit pas choisir une dépendance uniquement parce qu’elle est populaire ou pratique.

Avant ajout :

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

Le système doit empêcher autant que possible :

```text
deprecated dependencies
unmaintained dependencies
obsolete APIs
unsupported runtimes
old examples copied from outdated documentation

```

Les agents doivent vérifier les versions actuellement supportées avant adoption.

---

# 27. Dependency automation

Une solution telle que Renovate ou équivalent peut automatiquement :

```text
detect upgrades
open PRs
group safe upgrades
automerge low-risk upgrades

```

Les upgrades importantes restent soumises aux mêmes reviews que du code normal.

---

# 28. Dependency migration

Remplacer une dépendance constitue une migration.

Processus attendu :

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

Pas de :

```text
uninstall old
install new
rewrite everything
hope CI catches it

```

---

# 29. Database migrations

Les changements destructifs doivent suivre autant que possible :

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

Exemple interdit dans un déploiement unique sans justification :

```sql
DROP COLUMN

```

si une version potentiellement active du logiciel peut encore l’utiliser.

---

# 30. Cybersecurity

La sécurité ne doit pas être réduite à :

```text
dependency scanner
+
SAST

```

Elle comprend :

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

Une revue sécurité spécialisée est déclenchée pour les changements touchant notamment :

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

Le security reviewer doit recevoir un contexte indépendant.

Il cherche notamment :

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

Un standard tel que OWASP ASVS peut servir de baseline externe plutôt qu’une checklist entièrement inventée localement.

Le projet doit définir le niveau approprié selon son contexte.

---

# 34. Agent isolation

Les agents ne constituent pas une frontière de sécurité.

Les protections importantes doivent être externes :

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

Les tests doivent vérifier du comportement utile, pas simplement augmenter un chiffre de coverage.

Les agents ne doivent pas pouvoir :

```text
add trivial tests
exclude difficult code
mock everything
weaken assertions
delete edge cases

```

uniquement pour atteindre un seuil.

---

# 36. Test hierarchy

Selon le projet :

```text
unit
integration
contract
property-based
E2E
smoke
regression

```

Le pipeline doit sélectionner les catégories pertinentes plutôt que toutes les imposer systématiquement.

---

# 37. Characterization tests

Avant un refactor ou une migration complexe, l’agent doit capturer le comportement existant lorsque celui-ci doit être conservé.

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

Chaque PR doit pouvoir déclencher selon le stack :

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

Aucun agent ne peut contourner silencieusement ces gates.

---

# 39. Multi-persona review

Le système doit disposer de reviewers spécialisés.

## Correctness reviewer

Recherche :

```text
logic errors
edge cases
failure handling
race conditions
invalid assumptions

```

## Architecture reviewer

Recherche :

```text
unnecessary abstractions
boundary violations
coupling
duplicated responsibilities
architecture drift

```

## Test reviewer

Recherche :

```text
missing scenarios
overmocking
weak assertions
coverage gaming
missing regressions

```

## Security reviewer

Recherche vulnérabilités et nouvelles trust boundaries.

## Dependency reviewer

Évalue nouveaux packages et migrations.

---

# 40. Review orchestration

Toutes les personas ne sont pas lancées systématiquement.

Un orchestrateur classifie le changement puis choisit les reviews nécessaires.

Exemple :

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

Trois niveaux initiaux.

## R0 — Low Risk

Exemples :

```text
docs
typo
tests
minor internal cleanup
simple isolated bug

```

Peut être auto-mergé après checks/review.

## R1 — Normal Engineering Change

Exemples :

```text
feature
endpoint
normal refactor
UI change
non-destructive schema extension

```

Peut être automatiquement mergé après :

```text
reviews
CI
staging validation

```

## R2 — High Risk

Exemples :

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

Nécessite approbation humaine explicite.

---

# 42. Human escalation philosophy

L’humain ne doit pas être sollicité parce que :

```text
the agent is uncertain about a filename
a test failed
a library API is unfamiliar

```

Les agents doivent investiguer eux-mêmes.

Escalade pour :

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
                     RISK GATE
                       /     \
                    R0/R1     R2
                      │        │
                 auto merge   human
                      │        │
                      └────┬───┘
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

Questions :

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

Tous les travaux ne nécessitent pas le modèle le plus coûteux ou intelligent.

Le routeur peut utiliser des modèles plus petits pour :

```text
classification
simple repository search
mechanical edits
basic test generation
documentation
changelog generation
simple dependency investigation

```

Modèles plus puissants pour :

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

Lorsque Claude et Codex sont tous les deux disponibles via abonnement :

une stratégie asymétrique est préférable.

Exemple :

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

Le routage réel doit rester configurable selon :

```text
quota
task
model capability
availability
user preference

```

---

# 49. Token efficiency

Les instructions doivent être conçues pour minimiser le contexte inutile.

Principes :

```text
short root instructions
progressive disclosure
file-scoped instructions
task-specific skills
summaries instead of history dumps
persistent artifacts
independent small review contexts

```

Ne pas injecter systématiquement :

```text
all architecture docs
all policies
all previous discussions
entire project history

```

---

# 50. Persistent state

Les décisions importantes ne doivent jamais exister uniquement dans la conversation d’un agent.

Elles doivent finir dans :

```text
issue
spec
ADR
code
tests
documentation
PR

```

Ainsi un agent peut être remplacé ou redémarré sans perdre l’état du projet.

---

# 51. Tool architecture

Aucun orchestrateur n’est pour l’instant retenu comme obligatoire.

Les solutions explorées comprennent notamment :

```text
Open SWE
CAO
OpenHands
Kiro
Claude/Codex orchestration projects
GitHub coding agents
local custom orchestration

```

CAO a été identifié comme techniquement intéressant mais n’est pas considéré comme une décision produit acquise.

---

# 52. Orchestrator abstraction

Le pipeline doit pouvoir fonctionner avec différents backends.

Conceptuellement :

```text
              Agent Runtime Interface
                        │
       ┌────────────────┼────────────────┐
       ▼                ▼                ▼
   Claude Code        Codex          Future agent

```

L’orchestration ne doit pas imposer aux specifications ou aux policies de connaître le runtime utilisé.

---

# 53. CLI-native execution preference

Lorsque possible, préférer les CLI officielles :

```text
claude
codex

```

plutôt que d’extraire ou manipuler directement les tokens OAuth.

Cela :

```text
preserves provider authentication
reduces credential handling
uses existing subscriptions
reduces implementation fragility

```

---

# 54. Avoid hidden API costs

Le système doit rendre explicitement visible lorsqu’une action :

```text
uses subscription quota
uses paid API
uses external cloud compute

```

Le mode par défaut doit pouvoir fonctionner sans coût API additionnel.

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

Le système doit séparer :

```text
universal engineering rules

```

de :

```text
Python-specific rules
TypeScript-specific rules
Rust-specific rules
React-specific rules
FastAPI-specific rules
etc.

```

Exemple :

```text
.agent-standard/
    core/

overlays/
    python/
    typescript/
    react/
    fastapi/

```

Cela doit permettre de composer un nouveau projet sans dupliquer toutes les instructions.

---

# 57. Greenfield bootstrap

Pour un repository vide :

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

Le bootstrap doit générer immédiatement les garde-fous essentiels plutôt que les ajouter après plusieurs semaines de développement.

---

# 58. Existing approaches worth borrowing from

## GitHub Spec Kit

Intéressant pour :

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

Le concept de convergence spec/code est particulièrement pertinent.

Le produit ne doit cependant pas forcément dépendre directement de Spec Kit.

---

## Open SWE

Intéressant pour :

```text
issue → autonomous worker → PR
persistent agent threads
follow-up
review
CI feedback loops

```

Moins intéressant si son exécution exige une consommation API additionnelle.

---

## OpenHands

Intéressant pour :

```text
agent skills
automation
sandboxing
review separation
progressive instructions

```

---

## Kiro

Intéressant comme exemple intégré :

```text
requirements
design
tasks
implementation

```

Mais trop couplé à une plateforme spécifique pour devenir le cœur du système.

---

## Orca

Reste le cockpit humain privilégié.

---

# 59. Agent-first anti-patterns

Le système doit explicitement éviter :

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

L’expérience cible doit être proche de :

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

Le quotidien de l’utilisateur doit idéalement être :

```text
Orca
+
GitHub Project
+
Issues
+
PRs

```

et non un ensemble de dashboards spécialisés.

L’utilisateur doit pouvoir :

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

Une feature n’est `DONE` que lorsque :

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

Pour les features déployées :

```text
deployment succeeded
health checks pass
rollback path exists

```

---

# 63. Success metrics

Le système sera considéré efficace si, à terme :

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

Mesures possibles :

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

La première version ne doit pas chercher à construire toute la software factory.

MVP proposé :

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

Le pipeline peut initialement être déclenché manuellement depuis Orca.

---

# 65. Phase suivante

Après validation du modèle :

```text
automatic READY detection

automatic agent dispatch

parallel specialized reviews

subscription-aware model routing

automatic fix loops

staging deployment

spec convergence

risk-based auto merge

production validation

continuous dependency maintenance

```

---

# 66. Questions encore ouvertes

Les choix suivants restent volontairement non figés.

### Orchestration engine

Construire une fine couche maison ou adapter :

```text
CAO
Open SWE
other existing orchestrator
GitHub-native workflows

```

### Specification engine

Utiliser directement :

```text
Spec Kit

```

ou seulement reprendre son modèle conceptuel.

### GitHub Projects

Déterminer si GitHub Project constitue réellement la state machine principale ou seulement une vue.

### Local versus always-on execution

Décider si l’orchestration tourne :

```text
on developer workstation
home server
GitHub runner
small dedicated machine
hybrid

```

### Auto-merge threshold

Déterminer progressivement quels changements R1 peuvent réellement être auto-mergés.

### Product acceptance

Déterminer quelles features nécessitent encore une validation visuelle/fonctionnelle humaine.

---

# 67. Long-term product direction

Le système peut éventuellement devenir un repository/template installable :

```text
agentic-repo-standard

```

ou un CLI :

```text
agentrepo init

agentrepo doctor

agentrepo spec

agentrepo run

agentrepo review

agentrepo status

```

Mais le CLI ne doit pas devenir obligatoire pour travailler avec le projet.

Le format des artifacts doit rester simple :

```text
Markdown
YAML
Git
GitHub
shell commands
standard CI

```

afin que le système reste compréhensible et récupérable sans outil propriétaire.

---

# 68. Core product principle

La finalité n’est pas :

> faire coder Claude automatiquement.

Ni :

> faire coder Codex automatiquement.

La finalité est :

> construire des repositories dans lesquels des agents interchangeables peuvent développer, tester, documenter, reviewer, maintenir et livrer du logiciel de manière fiable, avec l’humain concentré sur le produit et les décisions à fort impact.

La qualité du système repose donc sur cinq piliers :

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

et non sur la qualité d’un agent unique.

---

# 69. North Star

À terme, le fonctionnement idéal est :

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

Le produit doit tendre vers une software factory dans laquelle :

**l’humain gouverne, les agents exécutent, et les preuves automatiques contrôlent.**
