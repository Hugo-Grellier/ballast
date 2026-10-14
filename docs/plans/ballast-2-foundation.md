# Ballast 2.0 foundation — #175

Parent: #174. The operator approved starting 2.0 in conversation and explicitly
instructed that Ballast 1.x must not run this work. This plan uses ordinary Git,
deterministic checks and independent review. Merge and release remain human decisions.

## Outcome and boundaries

Preserve the agreed portable issue-to-PR workflow in root/docs instructions and a proposed
ADR, and qualify explicit Codex model/effort settings before task execution.
The probe is standalone, stdlib-only and independent of Orca. It creates no model
turn, accepts no task prompt, and changes no v1 launch or trust behavior.

The eventual execution integration is a separate dependent feature. A routing
receipt proves resolved client configuration, not provider-internal computation,
task success, execution confinement, queue recovery, or end-to-end PR readiness.

## Tasks and acceptance evidence

1. Preserve the workflow instructions and research, add ADR-0023 as proposed; review every
   accepted operator constraint against the instruction files (AC1–2).
2. Add `tools/codex.py`: bounded JSON-lines app-server connection, explicit
   model/effort, model-catalog capability check, fresh ephemeral read-only thread,
   strict resolved-receipt comparison, minimal JSON evidence, no `turn/start`
   anywhere in its request allowlist (AC3).
3. Exercise protocol boundaries with a deterministic fake server/transport: CI
   refusal before process launch, unknown/unsupported routes, malformed receipt,
   mismatch, protocol error, EOF, timeout and teardown; success never sends task
   input. Tests use no model or real agent (AC4, AC6).
4. Locally qualify at least two explicit supported route pairs through installed
   Codex, record scrubbed results and limitations without task execution (AC5).
5. Run focused tests and repository lint/format; independently review the final
   diff, fix findings, publish an issue-linked PR with acceptance evidence. Report
   CI truthfully and keep a draft while required verification is pending (AC6).

## Failure and privacy

Every RPC has a shared bounded deadline; malformed, rejected, missing or mismatched
responses fail qualification. The request allowlist is `initialize`, `initialized`,
`model/list`, and `thread/start`, with request-ID correlation. The protocol deadline
includes startup; shutdown has a separate bounded cleanup allowance. Close the
app-server subprocess on all paths.
Never emit raw protocol messages, stderr, account details or absolute destinations.
CI invocation refuses before agent process creation; tests cover the refusal with
an injected fake. Stdlib subprocesses use argument arrays, no shell.

## Deferred milestones

Standalone issue worktree/claim/launch and pair review; retry/resume/queue limits;
optional Orca; v1 migration and 2.0 release. Their runtime guarantees are specified
by the root/docs instruction set but are not implemented by this feature.

## Layout correction requested by the operator

The operator clarified that the rewrite belongs in the existing repository
layout, not `successor/` or `tools/v2/`. Move workflow documents to `docs/`,
the Codex transport/probe to `tools/codex.py`, evidence to `docs/evidence/`,
research to `docs/research/` and task/PR templates to their real `.github/`
locations. Root instructions point to those files. Per-PR branches/worktrees
already isolate development. The final migration retires v1 files and updates
consumer adoption templates; no permanent parallel version tree is retained.
