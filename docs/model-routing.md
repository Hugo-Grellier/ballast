# Explicit worker model and effort

## Contract

Select a route for every task or phase, whether started by a human, a coordinator,
or another worker. Resolve the route to an explicit provider, concrete model ID,
and supported effort setting. Pass both model and effort through the execution
tool's configuration. Prompt text asking a model to act like another model does
not change the runtime. A worker can use the same settings as its parent only
when its own route explicitly selects that pair.

The parent conversation's model and effort are never routing defaults. This rule
applies to nested delegation, retries, resumes, and review workers. It does not
expand permissions: workers remain within the caller's authorized access and
sandbox. The coordinator dispatches routed work rather than performing it itself
as a silent fallback.
Execution backends must respect the outside-CI boundary in `AGENTS.md`; CI is not
a worker placement or availability fallback.

## Choose

Maintain one project route map from the profiles below to installed provider/
model/effort pairs. Configure this map before dispatch; discover supported values
from the installed client. Keep credentials and account limits outside the repo.

| Work | Starting profile / effort intent |
| --- | --- |
| Extraction, triage, mechanical edits | economy / low |
| Clarification, ordinary planning, implementation, correctness review | standard / medium |
| Difficult diagnosis, architecture or security reasoning | senior / medium |

These are capability intents, not portable provider argument values. The route
map must resolve them to concrete supported settings; no unresolved profile or
implicit effort reaches dispatch. Select review capacity for the review's own
difficulty, with fresh context and another provider when available. A sensitive
change still needs the human decisions defined in `AGENTS.md`.

Raise effort or capacity only with a recorded reason, such as unresolved reasoning
after a bounded attempt. Reroute the affected task, keeping the existing review
round limit. An ordinary code defect alone does not justify the largest model.
Honor explicit human route overrides within available access and permissions.

## Launch and verify

The execution integration must:

1. Validate that the selected backend can explicitly set both model and effort,
   including any custom-role configuration that can override spawn arguments.
2. Start a worker with the resolved settings and a bounded task handoff: issue,
   phase, acceptance criteria, relevant decisions, code/artifact references,
   permission limits, and completion evidence required. Use fresh context when
   conversation inheritance prevents configuration overrides.
3. Read the backend's session/configuration receipt before releasing task work.
   Compare the requested pair with the resolved model and effort, recording the
   source and session identity. Agent self-identification is not verification.
4. If values mismatch, are unsupported, or cannot be observed, mark routing as
   blocked/unverified and stop that worker's task. Try an explicitly configured,
   authorized execution backend if available. Report the capability gap otherwise.

Never silently substitute a model, provider, effort, inherited session, or paid
API. A fallback must be allowed by the project route map or an explicit human
decision, and must receive its own launch verification. The one exception is
the standalone [quota review fallback](standalone.md#quota-review-fallback): an
operator-approved review route used only after a recorded quota outcome, whose
publication states the route unverified. Provider credentials and
permissions are separate from model selection; changing model does not establish
cross-provider execution capability.

When a client cannot verifiably change an existing worker's settings, start a new
worker and hand off its current state. Revalidate resumes and record any verified
in-session switch. Preserve task history across those worker sessions.

## Observe

For each attempt, link the issue/phase and parent/worker session IDs, route-map
revision, selection reason, requested provider/model/effort, observed settings,
verification source and status, switches or fallbacks, and result. An unsupported
effort must have an explicit backend capability record; it cannot be presented
as a verified low/medium/high setting. Unknown observations remain unknown.

Use these records to identify unnecessary high-capacity dispatch, ignored effort,
fallbacks, and whether escalation actually improves outcomes. Record usage or
cost only when supplied by the backend.

## Integration acceptance

Before claiming enforced routing, demonstrate with actual backend session records:

- Human-started and agent-started tasks select the same configured worker route
  despite different parent settings.
- Both model and effort overrides take effect, including nested delegation,
  custom roles, retries, and resumed work.
- A model-only or effort-only setting cannot leak the other value from the parent.
- Unsupported settings, mismatches, and missing observations prevent task work;
  any authorized fallback is explicit and verified.
- A route change takes effect in a new worker or a verified session switch.

Markdown defines this contract. Enforcement and these acceptance checks belong
in the execution integration; this starter alone does not implement them.
