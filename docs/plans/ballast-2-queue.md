# Bounded queue and recovery — #178

Stacked on #177 / PR #181. The operator described a PR stack for the full 2.0;
keep one branch/worktree per leaf and merge in order. Build with ordinary tools,
not Ballast 1.x or Spec Kit. This is an implementation plan, not completed proof.

## Shape

Keep the existing agent as foreground coordinator and preserve #177's two
execution primitives. Add atomic admission/control operations. No daemon, workflow DSL, database service or timers.

One small POSIX module owns a short-held `flock` in the existing Git common
state directory. Under that lock it reads/writes queue policy, reserves issue
admission and worker slots, records pause/quota/cancel controls, and projects
status from the existing issue claims and worker records. Existing claim and
worker records remain authoritative for their attempts; GitHub remains authority
for issue relationships, PR identity/merge and CI. Queue policy does not duplicate
backend execution truth. Atomic writes preserve unknown/partial states.

## Operations and boundaries

1. **Configure a one-time selected queue.** Explicit repository, selected leaf
   issues, coordinator reference, instruction revision and finite limits. Defaults
   proposed for the solo pilot: one active implementation issue, two total worker
   slots (including review/helpers), two ready PRs, three worker/review repair
   attempts per phase and a finite queue timebox. Project/request overrides are
   explicit; a worker cannot raise its limits. No background issue-author trigger,
   recurring schedule or implicit expansion to unrelated issues.
2. **Select eligible work.** Read GitHub issue/dependency/linked-PR evidence using
   the already verified host/repository. Resolve native dependencies and explicit
   `Blocked by` references, report cycles, unknown/cross-repository prerequisites
   and required unmerged PRs. Block affected issues; return independent eligible
   work within admission, worker, elapsed-time and PR-backlog budgets. Stacking is
   an explicit exception with recorded merge order. A closed dependency alone
   cannot prove its required code merged.
3. **Enforce admission at the primitives.** Preparation uses the shared lock and
   per-issue claim; workers obtain their exclusive issue lock and total worker
   reservation under the same lock before creating a client. Immediately before
   `turn/start`, reserve a turn permit and recheck pause/cancel under the lock;
   a pause after that permit treats the turn as already active. Review/helper work
   counts in the same budget. Unknown locks consume capacity. Durable claims survive settled work: actively
   editing/repairing/unknown attempts count against the issue cap; positively
   settled PR-wait states release issue admission but consume backlog capacity.
   Count blocked/unverified drafts too, so they cannot bypass the backlog cap.
   Missing/corrupt
   policy or identity fails closed. Standalone single-issue operation keeps its
   bounded default when no queue is configured.
4. **Recover without guessing.** Inspect existing claims/worktrees, worker
   receipts/results and linked PRs before retry. Reuse matching artifacts.
   Completed workers with durable evidence can advance; unresolved delivery or
   liveness remains unknown. No timestamp/PID-only reclaim. Explicit reconciliation
   records positive stop/completion evidence and the responsible coordinator;
   it never deletes a checkout or asserts unseen backend completion. An active
   issue's coordinator transfer requires recorded explicit handoff/stop evidence.
5. **Quota, pause and cancellation.** Classify only structured backend usage/rate
   errors, preserve a backend-provided retry window privately when available,
   otherwise record unknown. Quota blocks affected dispatch without busy retries,
   paid fallback or skipped review. Pause blocks new admissions/turns. Cancel
   is observed by live workers while awaiting backend messages. Workers request
   `turn/interrupt` and bound the wait for terminal evidence; the result is
   confirmed terminal state or
   unknown, never automatic release. A restart reads these controls first.
6. **Publish idempotently.** Coordinator searches matching repository/stable branch/issue
   PRs before a create and re-queries after uncertain responses, including when
   the branch advanced after the response was lost. Confirm head/base before
   reusing an existing PR; do not create another to conceal a stale revision. Existing PRs are
   reused, foreign/multiple candidates block. Save PR/head/check/review evidence
   locally; only GitHub-confirmed merge removes backlog pressure. No auto merge,
   deletion or release. Publication remains native Git/GitHub tooling.
7. **Observe actual work.** Durable UTC phase/attempt events, instruction revision,
   waiting, review rounds, routing receipts, known elapsed time and backend token
   counts or unavailable. Derive throughput/rework/waiting summaries from records;
   never invent cost, account identity or missing runtime. Public projections are
   scrubbed and reference authoritative local/GitHub evidence.

## Legacy requirements reconciliation

- #152: an explicitly selected issue/queue authorizes this task; no unattended
  trusted-author trigger, v1 allowlist installer or automatic timer is adopted.
- #153: finite elapsed/attempt limits and evidence-based route escalation remain;
  a hard token spending cap is not claimed where the backend cannot enforce it.
  Environment failures stop repair rather than spend model retries. Unverified
  work can be published draft with its gap, never mislabeled ready.
- #154: structured quota pause/retry window is retained. No unapproved unattended
  self-resume service or recurring timer is introduced.
- #159: record supplied token counts and measured elapsed time, otherwise
  unavailable. No transcript reconstruction, telemetry collector or estimated
  provider billing.
- #168: independent worktrees, bounded parallel selection, dependencies, dry-run
  and status are retained. Its v1 trust/Autonomous-mode mechanics do not apply.
  The agent owns phase execution; native helpers enforce atomic admission/control.

No legacy issue is silently closed or declared satisfied by this slice.

## Evidence before publication

- Deterministic native temporary-Git/scripted-backend cases: two independent
  issue worktrees; two coordinators racing for one claim; issue and all-worker
  caps; unknown occupancy; cycle/unknown/unmerged prerequisites; pause/cancel;
  quota unknown/known window and bounded retry; restart after partial launch;
  PR response loss with one recovered PR; backlog capacity and no destructive
  cleanup. No real agent, hosting call or credential is required in CI.
- Representative foreground integration with native local processes proves
  independent issue admission, shared capacity, interruption and recovered state;
  distinguish it from a live model/GitHub end-to-end proof. Reuse #177's separately
  qualified executing-session boundary, refreshing actual-client evidence if its
  protocol path changes materially.
- Independent plan review before coding, exact-head implementation review and
  project checks before stacked draft PR. Document incomplete capabilities.

## Plan review and layout correction

The independent reviewer accepted the short-lock/coordinator design and required
three state rules: atomic turn permits with cancellation observation; durable
claim lifetime separate from active issue/backlog slots; and stable branch/issue
identity when reconciling an uncertain publication. Those rules are incorporated
above. The operator clarified that 2.0 belongs directly in the existing layout:
this feature extends `tools/worktree.py`, `tools/worker.py` and ordinary `docs/`
files. It introduces no versioned product subtree.

## Implementation status

`tools/admission.py` holds the lock, policy and controls; `tools/worktree.py`
and `tools/worker.py` call it; `tools/coordinate.py` exposes configure, select,
control, settle, publish and status. `tests/test_queue_admission.py` covers the
deterministic cases above with temporary Git and scripted hosting/backend.
Two independent review rounds found and closed recovery, fail-closed and
transition gaps (release/recover operations, policy binding, transition table).
Known gaps: stacked prerequisites are a coordinator exception without recorded
merge order in the tool; observation lacks phase-level waiting and acceptance
mapping (acceptance 8 partial). Representative live integration evidence is
still to be recorded separately.
