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
safe evidence references. Known workflow evidence must become visible: add a coordinator-only `coordinate
record` operation that appends schema-validated `progress` entries to the existing
claim history under its admission lock. No parallel database or browser write API.
The producer is the main conversation coordinator after it obtains the actual
question/check/review/phase evidence; worker completion never produces approval.
Kinds: phase, plan, question, decision, check, review and readiness. Each entry has
an explicit state from a per-kind enum, a bounded coordinator-curated public
summary, and optional reference restricted to an exact selected-repository GitHub
issue/comment, PR or Actions run URL; check/review/readiness also bind a full
revision. No paths, protocol, private output or arbitrary metadata are accepted.
Summaries are intentionally public-safe declarations by the authorized coordinator,
not extracted worker text. Reject credential-like text/control characters and
sensitive field names; raw backend histories are never exposed. Documentation
makes the producer responsible for excluding secrets/private reasoning. Question
and decision records link to the main conversation's issue reference; no browser
answer or inferred human approval. Projection preserves event timestamps and
marks unrecorded evidence unknown, recorded evidence as coordinator-recorded and
old revisions stale rather than current approval. Current claim checkout HEAD is
read through pinned Git admin metadata solely for evidence freshness. No browser
path selection/file access. Do not parse final worker output to infer evidence. Use on-demand existing dependency selection, keeping network
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
Extend `admission.control` with optional expected queue/coordinator identity,
validated inside its existing lock before mutation; existing caller behavior
otherwise remains compatible. Reject any transition away from cancelled,
including cancelled-to-paused, closing the existing two-step resume loophole.
Capture repository, queue id, coordinator and selected issue membership at binding;
recheck the full immutable context within the mutation lock and on every snapshot.
Fail closed on policy replacement or corruption. The new progress producer uses
the same ownership and selected-claim admission checks.
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
confirmation. No progress percentages or fabricated completion statistics. Filter full claims
by exact repository, queue id and selected issue numbers before deriving issue
views, then join workers by those selected attempt IDs. Legacy pre-queue claims
remain visible only as aggregate capacity pressure, requiring explicit existing
recovery/adoption to join this queue. Workers without results use only joined
reservation/event identity and show unknown. Clone-wide used capacity is labelled
as such because backend admission counts other claims; never expose their rows,
identities or global throughput as selected queue metrics. Field-level projection
allows only known route keys provider/model/effort, known token keys totalTokens,
inputTokens/cachedInputTokens/cacheWriteInputTokens/outputTokens/reasoningOutputTokens,
fixed milestone enums and validated UUID/hex/session identifiers; malformed values
become unknown. Arbitrary reason/evidence/token fields and raw errors are omitted.
Server logs never include URLs, request headers/bodies, records or backend errors.

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
4. Deterministic UI behavior also runs in CI without a browser dependency: factor
   state/render decisions into testable native JavaScript and execute Node's
   built-in assertions/test runner through the unittest gate (CI's installed Node,
   no agents, Orca, network or downloaded npm dependencies). Exercise selected
   details, text-safe rendering, stale/disconnected disabled controls, changed
   snapshots, reconnect without dispatch, and terminal cancellation state.
   Run repository Ruff and unittest gates. Browser-check layout, issue/worker
   detail, controls, disconnect/reconnect and ordinary-browser operation using
   a synthetic local queue; record it distinctly from live worker evidence.
   Verify optional Orca presentation separately. Preserve screenshots for review.
   Separately record local standalone integration using real loopback HTTP and
   actual durable claim/worker/control operations with a scripted native worker
   transport: conversation-driven startup, pending question and plan/check/review
   evidence, attempted settings versus receipts, pause/resume, cancellation,
   server disconnect/reopen against the same attempts and honest PR readiness.
   Label the scripted transport explicitly; do not claim a new live model or
   hosting end-to-end run. Existing #177/#178 live qualification remains evidence
   for unchanged worker execution. No extra real model spend for UI fixtures.
5. Commit, independent exact-head implementation review, at most three fix rounds;
   publish one draft PR with coverage and gaps. Inspect current-head CI and keep
   draft until all required evidence and reviews pass. Stop at human merge.

## Plan review round 1 resolution

Independent review of `ad24be6` required changes. This revision retains all issue
acceptance rather than reducing scope: typed coordinator progress in existing
claim history resolves the missing structured evidence source. It also defines
atomic context/ownership checks, terminal cancellation, pre-projection membership
joins, explicit field allowlists, deterministic CI UI checks and local standalone
integration evidence. A second independent plan review must resolve these
findings before coding. The first review attempt had no usable result after a
liveness block; the second completed with the findings above.
