# Orca qualification: #179 remains blocked

Inspected 2026-10-15: Orca **1.4.220**, Codex **0.162.1**. Development base:
`af4e739271123ef1425b3b8e2150f7d3698632bd`. No issue worker was dispatched.

## Observations

- The installed public `agent-context` schema exposes explicit `model` and
  `effort` on `orchestration worker-start`. It forbids those options with
  `--terminal`. Its public CLI has no supervised hold/verify/release operation.
- The runtime advertises `orchestration.worker-launch-preferences.v1` and
  `agent-session.structured.hold.v1`. Advertising these does not establish a
  public supervised pre-task validation path.
- The installed main bundle constructs effective launch preferences by copying
  the requested agent/model/effort. Task delivery is part of `worker-start`,
  before the caller can inspect its return. Consequently matching preferences
  are insufficient evidence under [model routing](../model-routing.md).
- Upstream source at inspected snapshot
  [`6ade7a5`](https://github.com/stablyai/orca/tree/6ade7a5af02d5faf4a91401e0edc6dea6b12d11a/src/main/runtime/rpc/methods/orchestration/worker)
  independently shows this in `worker-launch-preferences.ts` and
  `local-worker-start.ts`. This snapshot is a source reference, not a claim
  that upstream HEAD equals the installed build.
- A task-free fresh Codex TUI with explicit model/effort can display them in
  local `/status`. The independent pair rejected using that screen plus a
  separate catalog probe as a replacement for a native same-session receipt.
  Adoption has no demonstrated binding to the unchanged observed session.
  The probe received no model task and its unsupervised terminal was closed.
  Account details and raw terminal output are not committed.

## What ships

`tools/orca.py` reads the selected executable's guides, status and command schema
and reports sanitized capability facts with `dispatch: blocked`, observed route
unknown, and no created resources. It never calls an agent or a mutation.
Unknown versions remain blocked until an actual dispatch contract is integrated
and demonstrated. This is a qualification slice, not a complete execution backend.

Plan review round 1 rejected the TUI workaround and recommended this gate.
Implementation review and exact verification evidence belong in the draft PR.

## Acceptance accounting

| #179 requirement | Evidence / remaining work |
| --- | --- |
| Correct managed worktree and base | Development worktree created through Orca from the recorded main revision; automatic issue claim/placement integration remains unimplemented. |
| Verified route before task | Unsupported dispatch is blocked before any mutation; successful native dispatch proof remains blocked. |
| Accepted / started / settled / PR-ready | Native mapping documented; no live dispatch proof. Qualification is never reported as started or ready. |
| Launch failure and restart recovery | Native inspection/replay mapping documented; live recovery cases remain blocked. |
| Unknown liveness retains ownership | No unknown attempt is released or duplicated by this command; native live cases remain blocked. |
| Questions, settlement, cleanup and projections | Contract mapping documented; live acceptance remains blocked. |
| Standalone and CI independence | Deterministic fixtures and unchanged standalone suites; CI invokes no Orca or agents. Exact results in PR. |
| No paid/recurring/merge/destructive actions | Qualification only; no fallback or mutation path. |

## Required next change

A public native operation must resolve the actual session's model, effort,
provider and permission limits before input, and bind release/delivery to that
verified session. It must preserve structured supervision, recovery identity and
cleanup ownership. Once available, integrate it against the installed guide and
prove every portable acceptance case. Do not relax routing or silently move an
Orca-owned attempt to standalone. #179 stays open and its PR stays draft.
