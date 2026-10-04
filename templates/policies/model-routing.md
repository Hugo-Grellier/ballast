# Model routing for engineering agents

This project uses Claude Code and Codex through the maintainers' interactive subscriptions. Model routing is therefore a **quota-efficiency policy**, not an API cost optimizer or an orchestration service. Do not introduce metered API calls, cross-provider credentials, a scheduler, or a routing database to implement this policy.

The operator remains able to override a route. Model availability and subscription limits change over time, so workflow rules target stable capability profiles; concrete model names are centralized here.

## Principles

1. **Deterministic rules first.** Workflow stage, R0/R1/R2 risk, review trigger, and whether the task crosses an architecture/security boundary usually determine the needed capability. Do not spend a model call classifying an obvious route.
2. **Use the lowest sufficient profile.** Expensive models are escalation capacity, not defaults.
3. **Route to a profile, not a brand.** A workflow asks for `economy`, `standard`, `senior`, or `critical`. The table below maps those profiles to currently available models.
4. **Effort is part of the route.** Prefer low/medium effort until evidence justifies escalation. Do not use maximum effort as a habitual default.
5. **Risk and difficulty are separate.** R2 raises review and human-gate requirements. A precise R2 implementation task may still be straightforward, while an R1 architecture task may need a senior model.
6. **Independent review should be genuinely independent.** For significant work, prefer the other provider for plan/code/convergence review when an equivalent profile is available.
7. **Escalate from evidence.** Failed verification, unresolved uncertainty, or repeated rework justify more effort/model capacity; task prestige does not.
8. **No hidden spending.** Subscription-authenticated Claude Code/Codex are the default. A paid API or third-party router requires explicit human approval.

## Capability profiles

Current mapping, reviewed 2026-09-26. Re-check this table when providers change models or subscription availability.

| Profile | OpenAI route | Anthropic route | Intended use |
| --- | --- | --- | --- |
| `economy` | GPT-6 Luna, `none`/low depending on task | Claude Haiku 4.5, lowest supported/default effort | Classification, search/extraction, summaries, mechanical edits, routine documentation |
| `standard` | GPT-6 Sol, medium by default | Claude Sonnet 5, medium by default | Normal specification, task generation, implementation, ordinary correctness/test review |
| `senior` | GPT-6 Astra, medium; high when justified | Claude Opus 5.5, medium; high when justified | Architecture, difficult debugging, security-sensitive reasoning, independent review, convergence |
| `critical` | GPT-6 Astra, xhigh/max only when justified | Claude Opus 5.5, xhigh/max only when justified | Repeated failures, unusually difficult/high-consequence reasoning, final escalation |

If a named model is unavailable in the current subscription/client, use the closest available model in the same provider/profile and record the actual choice. Do not silently fall back to a paid API.

## Default routes

These are defaults, not quality rankings.

| Work | Default profile / effort | Escalate when |
| --- | --- | --- |
| Issue triage, Epic-vs-Feature scope check, labels, extraction | `economy` low | Scope spans several domains or classifier confidence is low |
| Small R0 edit | `economy` low | Behavioral impact appears |
| `speckit-specify` / `speckit-clarify` | `standard` medium | Significant technical ambiguity or boundary conflict |
| `speckit-plan` | `standard` medium | Architecture boundary, R2 concerns, novel persistence/provider design -> `senior` medium |
| Independent plan review | Other provider, `senior` medium | Material unresolved findings |
| `speckit-tasks` / `speckit-analyze` | `standard` medium | Cross-artifact inconsistency remains after one pass |
| Mechanical implementation with precise plan | `economy` medium or `standard` low | Multi-file reasoning or behavior changes become non-trivial |
| Normal R1 implementation | `standard` medium | First bounded implementation attempt fails for reasoning rather than mechanics |
| R2 implementation | `standard` high or `senior` medium | Prefer `senior` when auth/Visibility/identity/destructive data semantics are central |
| Engineering/test/documentation review | `standard` medium, preferably other provider | Architecture/security findings require deeper reasoning |
| Security, architecture, migration review | `senior` medium | Serious unresolved finding or repeated failed fix |
| Spec reconciliation / convergence | Other provider, `senior` medium | Persistent spec/implementation disagreement |
| Repeated difficult failure | `senior` high | After another failed bounded attempt -> `critical` |

R2 still requires the human gates in the engineering workflow regardless of model strength; in an Autonomous run, the R2 approval is the merge decision.

In an Autonomous run, the runner picks the review integration, not a model: review steps use the other provider when its CLI is installed, and otherwise the authoring provider in a fresh context. A single-provider run is recorded as `cross-provider: no`, and its Draft PR states that review independence was reduced, so the merge reviewer can weigh it.

## Classifier rule

Do **not** run a classifier when the route follows directly from the table above.

Use a cheap classifier only for ambiguous free-form requests such as "take care of #123" where stage, risk, and complexity are not already known. The classifier recommends a **profile and effort**, never a concrete model/provider and never permission to bypass a human gate.

Return this compact shape:

```yaml
task_kind: triage | specification | planning | implementation | review | investigation
risk_candidate: R0 | R1 | R2
complexity: low | medium | high
architecture_boundary: true | false
security_sensitive: true | false
scope: single_file | multi_file | multi_boundary
long_horizon: true | false
recommended_profile: economy | standard | senior
effort_hint: low | medium | high
confidence: 0.0-1.0
reason: <one short sentence>
```

If confidence is below 0.75, do not rerun classifiers repeatedly. Route conservatively one profile higher or ask the human only when the missing information is a product decision.

The classifier itself should use an `economy` route. If the current session is already on a more expensive model, do not create extra work solely to classify a route that can be inferred directly.

## Provider balancing and independent review

For equivalent routes, the operator may select the provider with more subscription capacity remaining. Do not store quota/account details in the repository.

For significant features:

- if OpenAI authored the material plan or implementation, prefer Anthropic for the independent review;
- if Anthropic authored it, prefer OpenAI;
- if cross-provider review is unavailable, use a fresh context and record that limitation;
- do not use an expensive model simply to repeat a clean deterministic check.

The review model is selected by the review's difficulty/risk, not automatically one tier above the author.

## Bounded escalation

Escalation is local to the task:

1. Start at the default profile/effort.
2. If a bounded attempt fails because of reasoning uncertainty, raise **effort once** where sensible.
3. If the next attempt fails for the same underlying reason, raise **profile once** or switch provider.
4. Use `critical` only after repeated evidence, a genuinely exceptional reasoning problem, or explicit human choice.
5. A failing test caused by an ordinary implementation defect is not by itself a reason to jump to the largest model.

Do not continue autonomous fix/escalation loops beyond the limits already defined in the engineering and Spec Kit workflows.

## Pilot evidence

For the first 2-3 significant features after adopting this policy, record only enough metadata to tune this policy:

```text
role/stage
provider + model actually used
routing profile
effort
whether escalation occurred
verification result
independent review verdict
```

Feature review reports already record the reviewer model. Significant PRs should summarize author/reviewer routing and escalation in the PR template. Do not record hidden reasoning, account/quota details, secrets, or token-by-token telemetry.

After the pilot, review the project's actual outcomes. Only build automatic dispatch or a learned router if repeated ambiguous routing or measurable quota waste justifies it. Until then, this document plus the existing risk/workflow signals is the routing system.

The local [agent-run ledger](spec-kit-workflow.md#local-agent-run-evidence)
records these observations for explicitly instrumented runs. A route record
names the exact `Work` row above and the actual profile and effort. The report
compares that row with the observed route; a route above its default without a
recorded escalation or human override is a signal for review, not a claim that
the default would have succeeded. Missing provider or model identity stays
unavailable. A client usage total is shown only for complete, non-overlapping
invocation counters with a source label and digest; subscription quotas and
account details remain outside the ledger.
