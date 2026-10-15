# Current verification

The coordinator reports the full 67-test gate and GitHub CI green at
`6389f3436586dd8541d958c767b0b4ab5593e0d3`; ordinary desktop/mobile browser
checks, real CLI restart observation and optional Orca display are already
recorded in [dashboard evidence](../evidence/dashboard.md). Those results do
not verify the uncommitted review fixes below. Coordinator full-gate repetition,
any required browser follow-up and independent review remain pending.

## Implementation review round 1 fixes

This bounded sole-writer pass addresses DASH-001 and DASH-002 against the
reviewed head above, within the approved dashboard plan:

- Route provider/model/effort use the backend's bounded
  `[A-Za-z0-9][A-Za-z0-9._-]{0,127}` syntax. Actual durable projection tests
  preserve distinct dotted requested/observed models, accept the 128-character
  boundary and reject malformed/overlong values. Private keys remain omitted;
  dotted session and worker identifiers remain rejected by the unchanged opaque
  identifier validator. No worker/path validation was loosened.
- Confirmed backend `cancelled` is preserved as a status and timestamped
  milestone. The existing scripted transport/queue fixture setup produces a real
  terminal interrupted notification and durable cancelled result/event. Projection
  retains that exact event timestamp. A separate unconfirmed interrupt remains
  unknown with its ownership marker retained, and a completed worker remains
  completed after subsequent queue cancellation. `tools/worker.py` is unchanged.
- A native POSIX helper/child test exercises the existing two-second selection
  timeout without changing it. The helper runs in its own process group; SIGKILL
  return status and an already-reaped parent are checked. A child readiness pipe
  followed by EOF proves no live descendant retains the pipe, without arbitrary
  sleeps or process-disappearance polling. Finally cleanup kills the fixture
  group and waits; fixture alarms bound failure paths. No shell, agent, network
  or Orca is involved.

The route and cancellation regressions failed against the original implementation
before the fixes (three failing tests); the native cleanup test already passed.
After the fixes, these exact checks passed:

```sh
.venv/bin/ruff check --no-cache
.venv/bin/ruff format --check --no-cache
git diff --check
python -m unittest tests.test_dashboard.DashboardTests.test_durable_projection_without_http tests.test_dashboard.DashboardTests.test_projection_isolation_and_unknown_without_http tests.test_dashboard.DashboardTests.test_route_validation_in_projection tests.test_dashboard.DashboardTests.test_scripted_cancellation_projection_without_http tests.test_dashboard.DashboardTests.test_selection_timeout_kills_and_reaps_own_group tests.test_dashboard.DashboardTests.test_native_ui_contract
```

The focused unittest command passed all six tests, including native JavaScript
contracts. Ruff format checked 482 files. The attempted full gate,
`python tests/parallel.py tests/test_*.py`, ran **70 tests, zero skipped**:
65 passed and five existing real-loopback HTTP tests errored at socket creation
with `PermissionError: [Errno 1] Operation not permitted`. The denied tests are
`test_http_boundary_and_controls`,
`test_independent_bounded_sessions_and_malformed_cookies`,
`test_progress_validation_unknown_worker_and_dependency_budget`,
`test_replacement_is_checked_inside_control_lock` and
`test_scripted_transport_projection_evidence_and_reconnect`. They were neither
skipped nor replaced. Full repaired-tree verification is blocked by this sandbox's
socket restriction and requires the coordinator's permitted environment; no new
browser, CI or full-gate success is claimed.

Only dashboard projection, dashboard tests and this existing checkpoint changed.
No backend behavior, runtime timeout, model/provider/effort route, credentials,
agents, development claims, commits, publication, merge or release were used or
changed. The local native fixture left no live subprocesses.

## Historical writer checkpoint

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
