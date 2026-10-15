# Issue #188 implementation checkpoint

The implementation follows the approved `f47eb5f` plan. It is uncommitted and
requires independent implementation review and human merge approval. No actual
development queue or issue claim was created or changed. No live model, account,
Orca, publication or release operation was used.

## Coordinator evidence and bounded fix pass

The coordinator reported full lint/format success and a real-loopback full suite
result of **65/66 passing** before this fix pass. The sole failure compared entire
reconnect snapshots although issue `timing.elapsed` and `timing.phases.coordinator`
advance (reported elapsed observations: 0.466173 versus 0.457414 seconds).

The coordinator also reported ordinary Chromium QA of issue/worker details,
pause/resume, offline/reconnect, refresh, mobile and cancellation: no page JavaScript
errors and no desktop/mobile horizontal overflow. It reproduced a defect:
disconnect, then select issue #4, and the stale renderer falsely said Connected.
These observations predate the fixes below; **browser retest is pending**.

This sole-writer fix pass, within the existing approved scope:

- Detail rendering no longer writes connection freshness. Only a successful
  snapshot restores Connected. Stale issue/worker clicks preserve disconnected
  or unknown-control-outcome labels and disabled controls; elapsed freshness also
  expires the connection label. Lost control responses remain observation-only,
  with no automatic mutation replay.
- Native UI regression checks exercise both stale click paths, lost mutation
  response and successful observation recovery, readable labelled capacity,
  limits, quota, phase/worker seconds and available token fields, explicit unknowns,
  and a short heading reference with complete queue identity in labelled details.
- Existing selection now projects only fixed/validated dependency reasons for
  selected issues. Arbitrary diagnostics and foreign issue rows remain omitted;
  unavailable selection stays unknown. Added a focused projection check.
- Reconnect equality excludes only the two advancing issue timing values and
  explicitly checks both are nondecreasing. All attempt/worker identities,
  evidence, receipts, settled timings and remaining fields still compare exactly.
- Bootstrap retains up to eight independent sessions, evicting only the oldest
  at capacity. Cookie names include the public bound port and preserve HttpOnly,
  SameSite=Strict and Path=/api. CookieError/ValueError return unauthenticated
  rather than retaining a partially parsed session. Added real-HTTP regression
  coverage for concurrent viewers and controls, bounded eviction, mixed cookies
  from two ports, cookie attributes and malformed-cookie denial. These HTTP tests
  have not been run in this socket-restricted writer sandbox.

Verification after fixes:

- `.venv/bin/ruff check` — passed, all repository rules retained.
- `.venv/bin/ruff format --check` — passed (503 files).
- `git diff --check` — passed.
- `node tests/dashboard_ui.cjs` — passed, native DOM fixture, no browser claim.
- `python -m unittest tests.test_dashboard.DashboardTests.test_durable_projection_without_http tests.test_dashboard.DashboardTests.test_projection_isolation_and_unknown_without_http tests.test_dashboard.DashboardTests.test_native_ui_contract`
  — passed, three tests, including safe recorded dependency reasons.
- `python tests/parallel.py tests/test_codex_routing.py tests/test_queue_admission.py tests/test_standalone_execution.py`
  — passed, 59 tests, zero skipped, three classes.

Coordinator follow-up remains required: rerun the complete real-loopback gate
(including the added session test), browser QA against these fixes, and independent
exact-head implementation review. No socket tests were skipped or replaced, and no
browser retest, full-suite success, review approval or publication is claimed here.
No worker implementation or development local claims were modified in this pass.
The earlier sections below record the original writer session and its then-current
evidence gaps; the coordinator evidence above supersedes those historical gaps
only for the pre-fix revision it actually exercised.

## Checks in the bounded implementation session

- `.venv/bin/ruff check` — passed, repository ALL rules retained.
- `.venv/bin/ruff format --check` — passed.
- `git diff --check` — passed.
- `python tests/parallel.py tests/test_codex_routing.py tests/test_queue_admission.py tests/test_standalone_execution.py`
  — passed, 59 tests, three classes.
- `python -m unittest tests.test_dashboard.DashboardTests.test_durable_projection_without_http tests.test_dashboard.DashboardTests.test_projection_isolation_and_unknown_without_http tests.test_dashboard.DashboardTests.test_native_ui_contract`
  — passed, three tests. These run actual durable claim/admission/worker operations
  in fictional temporary Git repositories with the existing **scripted native
  transport**, plus Node's built-in assertions. This is not live model evidence.
- `node tests/dashboard_ui.cjs` — passed. Pure decisions and the complete browser
  script run against a small text-only DOM fixture: safe text, selected issue and
  worker details, settings differences, stale controls, disconnect/reconnect,
  changed observations, cancellation and no replay/dispatch.
- `python tests/parallel.py tests/test_*.py` — 66 tests, four classes, failed on
  four HTTP tests because this execution sandbox rejects socket creation with
  `PermissionError: [Errno 1] Operation not permitted`. The other 62 pass. The
  HTTP tests deliberately require actual IPv4 loopback requests; they have not
  been replaced with mocks or silently skipped.

## Outstanding evidence

Run the complete gate in an environment permitting local sockets. The HTTP
fixtures cover Host/Origin/session/CSRF/body controls, fixed routes and headers,
queue replacement inside the shared lock, terminal cancellation, selected-claim
and worker isolation, progress, settings receipts, unknown state and browser-session
reconnection. Those HTTP paths remain unverified in this session.

Also outstanding: ordinary-browser visual/keyboard/responsive checks, screenshots,
server disconnect/reopen integration over real loopback, and optional Orca display
verification. Socket restrictions prevent the local browser/integration run here;
Orca operations and nested review agents were explicitly excluded from this writer's
scope. The coordinator must obtain independent implementation review separately.
No CI or PR readiness claim is made. Existing live qualification of unchanged
worker execution is not newly established by these fixtures.

## Changed surface

`tools/dashboard.py` and `tools/dashboard_assets/` implement the optional
foreground service and native UI. `tools/progress.py` and `coordinate record`
provide typed public declarations in existing history. Admission adds immutable
expected-context checking under the existing flock and terminal cancellation,
with legacy control calls otherwise retained. `tests/test_dashboard.py` and
`tests/dashboard_ui.cjs` add deterministic contracts picked up by unittest CI.
`docs/standalone.md` documents explicit agent-callable startup, public progress,
main-conversation authority, optional presentation and lifetime/recovery limits.
