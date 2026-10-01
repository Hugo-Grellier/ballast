---
name: agentic-model-routing
description: Classify an ambiguous engineering request into a capability profile and reasoning effort without choosing a provider or bypassing workflow gates.
---

# Model routing

Read `docs/policies/model-routing.md` and the relevant issue/spec metadata.

Use this skill only when workflow stage, risk and review trigger do not already determine the route. Do not spend a classification pass on obvious work.

Return only:

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

Recommend the lowest sufficient profile. Risk controls human/review gates separately from difficulty. Never recommend `critical` from classification alone; that profile is reserved for evidence-based escalation. If confidence is below 0.75, recommend one profile higher rather than repeatedly reclassifying, unless a missing product decision requires human input.
