# #179: optional Orca adapter

Base: `af4e739271123ef1425b3b8e2150f7d3698632bd` (#178 merged).
Risk: R2. Ordinary development under the 2.0 exception; human merge required.

## Finding and plan

Orca 1.4.220 can select model/effort, but its public `worker-start` injects the
task before returning a receipt. Its effective launch preferences copy the
requested preferences. This cannot satisfy the pre-task routing gate.

1. Add an optional, read-only qualification command in `tools/orca.py`. Load
   the selected binary's version-matched guides, status and public schema.
   Project only sanitized facts; refuse CI, remote targets and dispatch.
2. Document native worktree, lifecycle and recovery mappings and the exact
   missing contract. Preserve standalone and native Orca authority.
3. Verify deterministic refusal paths without any Orca or agent process in CI;
   run the discovery command locally against the installed runtime.
4. Publish a draft PR with the outstanding live acceptance cases. Enable no
   dispatch until a native same-session pre-task receipt is integrated and
   demonstrated. Do not invent a future capability or approve a new version
   by version number alone.

Independent plan review, round 1: `changes_required` on the proposed terminal
`/status` workaround; the pair recommended this fail-closed slice. A screen
snapshot plus a separate catalog probe cannot prove that adoption targets the
same unchanged session. No task was delivered during the local metadata probe;
its unsupervised qualification terminal was closed afterward. This plan resolves
that finding by retaining the dispatch block. Implementation review is separate.

## Remaining dependency

Orca needs a public native hold/verify/release operation or equivalent guarantee
that resolves model, effort, provider, permissions and session identity before
task input, and binds delivery to that verified session. Then verify all #179
acceptance cases through actual native dispatch, including restart, partial
launch, cancellation, settlement and cleanup. A routing waiver is not assumed.
