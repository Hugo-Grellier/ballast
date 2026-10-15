# Ballast 2.0 release evidence — #180

Date: 2026-10-15. This is the acceptance summary for the 2.0 release candidate. It
links the slice records rather than repeating them. The operator approves the release
by merging the Release Please PR ([#189](https://github.com/Hugo-Grellier/ballast/pull/189)).

## Scope of 2.0

| Delivered | Issue | Evidence |
| --- | --- | --- |
| Explicit model/effort qualification before task input | #175 | [codex-routing.md](codex-routing.md) |
| Standalone issue-to-ready-PR slice | #177 | [standalone.md](standalone.md) |
| Bounded queue: admission, limits, pause/cancel, recovery, publication, timing | #178 | [queue.md](queue.md) |
| v1 retirement, migration guide, ADR-0024, copy-once templates | #180 | #185, #187; [migration guide](../migration.md) |

Not in 2.0:

- **Optional Orca adapter (#179).** Orca exposes no native receipt of a session's
  model, effort, provider and permissions before task delivery. The read-only probe in
  draft PR #186 confirms the block. The operator dropped the adapter on 2026-10-15, so
  standalone is the only execution path. [`orca-execution.md`](../orca-execution.md)
  stays as a contract marked not available.

## Verification

- CI runs deterministic checks only: ruff lint and format, and `unittest` over
  `tests/test_*.py`. No agent, network credential or model runs in CI.
- `main` at `b3263c0` (#187 merged):
  [CI run 38717315876](https://github.com/Hugo-Grellier/ballast/actions/runs/38717315876)
  passed. Local gate: 59 tests in 3 classes, OK.
- The release PR changes only `CHANGELOG.md`, `version.txt` and the manifest. Its
  checks must pass at its final head before merging.
- Every slice had an independent review in a separate model session; see each PR.

## Live integration evidence

All live runs used the public fictional repository `Hugo-Grellier/ballast-v2-smoke`,
real Codex 0.162.1 sessions, and no merge or deletion.

- **Standalone (#177):** issue #1 became ready PR #2. Implementation ran on
  `gpt-6-luna`/`low` and review on `gpt-6-sol`/`medium`, each requested = observed
  before task input. The new tests fail on the original code; the reviewer approved
  the final head; fixture CI passed.
- **Queue (#178):** two issues were delivered one at a time under `issues=1, workers=2,
  backlog=2`. The run showed the issue cap, dependency blocking (#5 blocked by unmerged
  #3), the pause refusal, idempotent publication (two `publish` calls, one PR) and the
  backlog refusal at 2/2.
- **Live cancellation (#178):** it found a real gap: sandboxed tool commands outlive the
  client. Fixed so a worker settles only when no process runs in its checkout. The rerun
  stayed `unknown` until the coordinator stopped the leftover session and released it
  with evidence.

## Throughput and quality observed

From [queue.md](queue.md#phase-timing-from-the-live-records), on small fictional
issues:

| Issue | Elapsed | Agent work (implement + review) | Coordinator | Waiting for human review |
| --- | --- | --- | --- | --- |
| #3 | 1,575 s | 28 s | 73 s | 1,472 s (93%) |
| #4 | 1,460 s | 23 s | 22 s | 1,413 s (97%) |

- **Throughput:** agent time is seconds per issue; human review dominates elapsed
  time. The ready-PR backlog cap (2) is therefore the binding limit, by design: it
  keeps unreviewed PRs from piling up.
- **Cost:** one implementation session used 78,830 tokens. Two fresh worker sessions
  per issue replace the roughly two dozen per-step sessions of a v1 Autonomous run.
  [v1 research](../research/2026-10-ballast-run-token-cost.md) found that the workflow
  around v1's implementation step cost about 90% of a run. The runs used different
  providers and tasks, so no ratio is claimed.
- **Quality:** each delivered issue had tests that fail on the original code, an
  independent review at the exact head, and zero rework rounds. The tradeoff: fewer
  enforced gates than v1. Correctness rests on checks, review and human merge rather
  than artifact postconditions.

## Limits and remaining gaps

- No trusted launcher, tamper checks or verified install; see
  [ADR-0024](../adr/0024-ballast-2-migration.md#removed-guarantees).
- Codex app-server on GitHub.com only, POSIX hosts, foreground workers. Windows is
  blocked by pipe handling.
- Process-quiet settlement is Linux-only. A process forking between the two scans can
  escape detection; a per-worker cgroup would close that gap.
- One clone's local state: no cross-clone ownership. Coordinator records are
  cooperative, not tamper-proof.
- Not exercised live: quota pause (provider-triggered), lost publication response,
  recovery after a killed preparation. All three are covered by scripted tests.
- Throughput numbers come from two small fictional issues (n = 2). They show where
  time goes, not expected durations on real work.
- Orca adapter not available (#179).
