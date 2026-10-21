# Dashboard

Covers: tools/dashboard.py
Covers: tools/dashboard_assets/**

`tools/dashboard.py` serves a foreground, loopback-only projection of one
explicitly bound queue, with pause, resume and cancel controls. The browser
UI is `tools/dashboard_assets/`.

### Requirement: Start outside issue checkouts
The dashboard SHALL refuse to start inside an issue checkout.

#### Scenario: Inside an issue checkout
- WHEN the dashboard starts inside an issue checkout
- THEN it exits 1 without serving
- Test: tests/test_queue_admission.py::QueueTests::test_helpers_refuse_to_start_inside_an_issue_checkout

### Requirement: HTTP boundary
The server SHALL bind IPv4 loopback, serve only its fixed assets and
authenticated JSON, require the exact Host header, the same Origin, a
capability exchanged for an HttpOnly SameSite=Strict session cookie and a CSRF
header, accept only bounded JSON bodies, keep at most eight sessions, and send
restrictive headers on every response.

#### Scenario: Unauthorized requests
- WHEN a snapshot has no session, the Host is foreign, a path is not a fixed asset, or the session exchange comes from another Origin
- THEN the server answers 403
- Test: tests/test_dashboard.py::DashboardTests::test_http_boundary_and_controls

#### Scenario: Control requests
- WHEN a control has a wrong CSRF token, a non-JSON or oversized body, or an unsupported action
- THEN it is refused with 403 or 400, and a supported one changes the mode
- Test: tests/test_dashboard.py::DashboardTests::test_http_boundary_and_controls

#### Scenario: Sessions and cookies
- WHEN several sessions exist, cookies are malformed, or two dashboards share a host
- THEN each session is independent, malformed cookies are refused, the oldest of more than eight is dropped, and cookies are named per port
- Test: tests/test_dashboard.py::DashboardTests::test_independent_bounded_sessions_and_malformed_cookies

### Requirement: Bound context
Every snapshot and control SHALL revalidate the bound repository, queue and
coordinator and SHALL answer 409 when the queue was replaced, is unreadable,
or the control is not allowed, such as resuming a cancelled queue.

#### Scenario: Replaced or unreadable queue
- WHEN the policy changes inside the control lock or becomes unreadable
- THEN controls and snapshots answer 409 and the mode is unchanged
- Test: tests/test_dashboard.py::DashboardTests::test_replacement_is_checked_inside_control_lock
- Test: tests/test_dashboard.py::DashboardTests::test_snapshot_derives_outside_lock_and_refuses_replacement

#### Scenario: Cancelled queue
- WHEN a cancelled queue is paused or resumed from the dashboard
- THEN the request answers 409
- Test: tests/test_dashboard.py::DashboardTests::test_http_boundary_and_controls

#### Scenario: Another coordinator
- WHEN the server runs under another coordinator reference
- THEN controls answer 409
- Test: tests/test_dashboard.py::DashboardTests::test_progress_validation_unknown_worker_and_dependency_budget

### Requirement: Public projection
The snapshot SHALL project only claims of the bound queue, joined workers and
validated progress, with whitelisted route values, tokens and timestamps, no
private output, reasons or paths, and SHALL show a worker without a terminal
record as `unknown`; a retired attempt SHALL stay until a new claim of the
issue replaces it.

#### Scenario: Private data excluded
- WHEN records hold private reasons, foreign claims, account data or paths
- THEN none appears in the snapshot, and an invalid session identifier is null
- Test: tests/test_dashboard.py::DashboardTests::test_scripted_transport_projection_evidence_and_reconnect
- Test: tests/test_dashboard.py::DashboardTests::test_projection_isolation_and_unknown_without_http

#### Scenario: Route values
- WHEN an observed route value is too long, starts with a dot, contains a path or space, or is not a string
- THEN it is projected as null, and an invalid worker identifier is skipped
- Test: tests/test_dashboard.py::DashboardTests::test_route_validation_in_projection

#### Scenario: Worker states
- WHEN workers completed, were cancelled, timed out, or ended without terminal evidence
- THEN they are projected with that status and their milestones, the last as `unknown`
- Test: tests/test_dashboard.py::DashboardTests::test_scripted_cancellation_projection_without_http
- Test: tests/test_dashboard.py::DashboardTests::test_timed_out_worker_is_projected_settled
- Test: tests/test_dashboard.py::DashboardTests::test_progress_validation_unknown_worker_and_dependency_budget

#### Scenario: Evidence freshness
- WHEN a progress record names a revision
- THEN it is `current` while it equals the checkout head and `stale` after the head moves
- Test: tests/test_dashboard.py::DashboardTests::test_scripted_transport_projection_evidence_and_reconnect
- Test: tests/test_dashboard.py::DashboardTests::test_durable_projection_without_http

#### Scenario: Retired attempt
- WHEN an issue's attempt was retired
- THEN it stays projected until a new claim of the issue replaces it
- Test: tests/test_dashboard.py::DashboardTests::test_retired_attempt_stays_in_projection_until_replaced

### Requirement: Bounded dependency refresh
Dependency state SHALL come from the selection helper, run at most once a
minute in its own process group, killed with its descendants after two
seconds, projecting only known reason shapes and `unknown` on any failure.

#### Scenario: Timeout
- WHEN selection exceeds its bound
- THEN its whole process group is killed and reaped, and dependencies are `unknown`
- Test: tests/test_dashboard.py::DashboardTests::test_selection_timeout_kills_and_reaps_own_group
- Test: tests/test_dashboard.py::DashboardTests::test_progress_validation_unknown_worker_and_dependency_budget

#### Scenario: Reason filter
- WHEN selection returns reasons of unknown shape or for unselected issues
- THEN only the known reasons of selected issues are projected
- Test: tests/test_dashboard.py::DashboardTests::test_projection_isolation_and_unknown_without_http

### Requirement: Browser UI
The UI SHALL render all text as text, never HTML, enable controls only on a
fresh observation of a non-cancelled queue, and link only to the bound
repository.

#### Scenario: UI contract
- WHEN the UI renders snapshots, stale observations and hostile text
- THEN text is never rendered as HTML, controls follow freshness and mode, and foreign links are refused
- Test: tests/test_dashboard.py::DashboardTests::test_native_ui_contract
