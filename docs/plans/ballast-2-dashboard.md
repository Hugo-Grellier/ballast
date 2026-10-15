# Portable execution dashboard — #188

Risk R2: a browser reaches the existing queue controls. Issue #188 and Epic #174
own the requirements. This is ordinary 2.0 development, without the 1.x launcher
or Spec Kit. Human merge approval remains required.

## One context, existing authority

Add `tools/dashboard.py`, a stdlib-only foreground loopback HTTP server, and a
small HTML/CSS/JS interface with no build step, CDN, runtime dependency or external
font. Explicit CLI arguments bind the project checkout, expected repository and
queue identity. Validate repository, policy and coordinator before serving;
never select a target from a focused Orca window. If requested, creation uses
`admission.create` with explicitly selected issues and existing finite defaults;
otherwise observe the existing queue. Startup prints a local capability URL.
An agent can invoke this directly and optionally open that URL in Orca or an
ordinary browser. Starting the UI starts no worker or scheduler: the existing
agent conversation remains the foreground coordinator and dispatches authorized
work through the standalone helpers.

Project `coordinate.observe`, existing claims, worker results and events into
an allowlisted read model scoped to the bound queue's selected issues. Do not
serve files from execution records or expose raw records, output.txt, paths,
reasoning, account data or protocol streams. No new execution database. Include
queue mode/limits/capacity, recorded waits/control history, issue/attempt/activity,
worker role/status/timestamps/milestones, requested versus observed route and
verification source, known timing/tokens, review rounds, recorded PR link, and
safe evidence references. Render absent questions, plan/check/review evidence and
readiness as unavailable/unknown; existing records do not prove these by a
successful worker turn or a recorded PR. Do not parse arbitrary final output to
infer approvals. Use on-demand existing dependency selection, keeping network
failure and source freshness explicit, rather than inventing eligibility.

## Local control boundary

Bind IPv4 loopback only and validate exact Host for the chosen port. Bootstrap
with a high-entropy URL fragment, exchange it through a same-origin request into
a private in-memory session, and erase it from history; do not put the capability
in query strings, logs or referers. Require authorization for all API reads and
writes, exact Origin for session/control POSTs, JSON with bounded Content-Length,
no CORS, and a session CSRF token/custom header. No side effects on GET. Return
no-store, restrictive CSP, frame-ancestors none, nosniff and no-referrer headers.
No arbitrary shell, file, path, model, retry, release or answer endpoint. The
only browser mutations are fixed pause/resume/cancel actions through
`admission.control`, revalidating queue identity and coordinator on every action.
Cancelled queues stay cancelled. Fail closed on policy replacement or corruption.
Record fixed control reasons rather than browser-supplied arbitrary text.

Untrusted text enters DOM only as textContent; constrain status/class values and
validate external links to the selected GitHub repository. Permit no HTML or
Markdown rendering, inline event handlers or external assets. Expose bounded
allowlisted enums, timestamps, route identifiers and opaque references rather
than copying arbitrary backend diagnostics/evidence. Main conversation handles
questions, decisions, review acceptance and recovery.

## UI and lifecycle

A compact responsive table of selected issues sits under the explicit repository
and queue identity, connection timestamp and pause/resume/cancel controls. Select
an issue for a detail panel with activity, waits, evidence availability and worker
rows; select a worker for route comparison, source, session, milestones and usage.
Use a white surface, charcoal typography, restrained blue accent, clear table
rules and visible focus states. Status must use words as well as color.
Poll with bounded requests; label stale/disconnected observations and disable
controls until a fresh authorized snapshot exists. Provide explicit cancellation
confirmation. No progress percentages or fabricated completion statistics.

The server and workers have foreground lifetimes; no daemon, detached supervisor,
heartbeat ownership proof or new scheduler. Closing/refreshing the page changes
no backend state; reopening observes the same attempts. Server exit stops only
HTTP service. Coordinator exit can leave unknown/interrupted ownership, which
consumes backend capacity until existing positive-evidence reconciliation. The UI
labels coordinator liveness unknown, even with a reachable server. No age/PID
heuristic or browser action releases a claim. Reconnect rereads durable records;
control response loss requires observation, never automatic replay/retry.

## Delivery and verification

1. Independent plan review, resolve blocking findings before implementation.
2. Backend projection, HTTP/session/control boundary, static UI and startup docs.
3. Deterministic unittest fixtures use temporary Git, scripted records/hosting and
   no real agents or Orca. Cover context isolation/replacement, missing/corrupt
   records, safe projection, requested/observed distinction, unknown readiness,
   Host/Origin/auth/CSRF/body limits, traversal/XSS, pause/resume/cancel and stale
   requests, refresh/reconnect and no duplicate dispatch/release.
4. Run repository Ruff and unittest gates. Browser-check layout, issue/worker
   detail, controls, disconnect/reconnect and ordinary-browser operation using
   a synthetic local queue; record it distinctly from live worker evidence.
   Verify optional Orca presentation separately. Preserve screenshots for review.
5. Commit, independent exact-head implementation review, at most three fix rounds;
   publish one draft PR with coverage and gaps. Inspect current-head CI and keep
   draft until all required evidence and reviews pass. Stop at human merge.
