# ADR-0025: optional local dashboard projects standalone execution

- Status: proposed; human merge acceptance required.
- Issue: [#188](https://github.com/Hugo-Grellier/ballast/issues/188).
- Risk: R2, because a browser can request existing execution controls.
- Extends: ADR-0023 and ADR-0024; standalone remains the only execution backend.

## Context

The operator accepted a portable local UI beside the existing agent conversation.
An ordinary browser must work independently of Orca. Native Orca worker launch
is outside this feature; the optional display does not restore that adapter.

## Decision

A stdlib foreground HTTP server binds one explicitly selected repository, queue
and coordinator, using the existing Git-common execution state. It projects
selected claims, worker receipts/events and coordinator evidence. It owns no
worker, scheduler or execution database and supplies no detached supervision.

The browser receives a private local fragment capability and exchanges it for an
in-memory session. Exact Host and Origin checks, HttpOnly SameSite cookies, CSRF
protection, fixed routes and a restrictive CSP protect the local control surface.
Reads and controls fail closed when immutable queue context changes. Controls
reuse admission's locked mutations; cancellation cannot transition back to pause
or running. No browser action can release ownership, retry, answer, approve or
publish work. Same-user malicious peers remain outside the existing cooperative
backend's protection guarantees.

The main conversation coordinator can append typed public progress declarations
to existing claim history. It curates summaries and records references/revisions;
private worker output is never parsed as evidence. GitHub remains authoritative
for issues, PRs and checks. Declarations are labelled coordinator-recorded, stale
when their revision changes, and unknown when evidence is absent. A readiness
declaration is not a human approval or independently verified hosting result.

The server exposes allowlisted fields and selected attempts only. Unrelated work
contributes to labelled clone-wide capacity because admission enforces that shared
budget. Worker settings requested and observed remain distinct. Server reachability
proves no coordinator liveness; interruptions retain existing unknown ownership.
Closing a page changes no execution state. Restarting observes the same records
and requires a new browser session; no automatic dispatch or replay occurs.

## Consequences

There is no UI build chain or required browser service. The operator retains the
server's foreground process and main conversation. Known questions and review/check
findings require explicit public declarations by the coordinator; absent records
remain unknown. The browser is optional presentation for the existing workflow.
