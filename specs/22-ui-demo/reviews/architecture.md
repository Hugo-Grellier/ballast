# Architecture review: 22-ui-demo

- Kind: architecture
- Reviewer: claude/claude-opus-5-5, agent-provisional, same provider as the author
- Scope: working tree against the branch start, focused on the accepted ADRs and architecture sections the change touches

## Decisions checked

- **ADR-0003 (launcher GitHub authority)** fixes the `gh` allowlist and says a later feature extends it by a new ADR. The change adds ADR-0012, status `proposed` and agent-provisional until merge. It lists every new call: the workflow read, the two contents reads for the blob `sha`, the one `POST .../dispatches` write, the bounded run list (at most five pages, never `--paginate`), the jobs read and the artifacts read. I compared this list with `demo.py`: `_get` callers, `_runs`, `_failed_step`, `_artifact`, `check_workflow` and `dispatch` make exactly these calls, plus the repository read and PR read already allowed by ADR-0003/0006. No second path to GitHub exists; every call uses #17's `_Checkpoint` seam.
- **ADR-0006 (review packet reads)**: the packet gains one input, `demo.collect`, which reads Actions runs only when a `demo_capture` event exists and the contract is valid. A failed read fails the packet step retryable, as for the existing check-run read. `Sources.demo` is never read by criteria, counts or evidence states (FR-014). The comment in `packet.Sources` and the render order (after UI, before Sources) keep that.
- **ADR-0005/0010/0011 (branch sync, resume, worktree)**: `ballast run demo` starts no agent and pushes nothing. It holds the run's invocation lock like `checkpoint`, so it cannot interleave with a runner push. The tamper and in-progress refusals reuse `draft_pr._untrusted`.
- **Ledger architecture (`ledger-schema.md`)**: `demo_capture` is additive, runner-only, fixed-field and text-free, and `schema_version` stays 1. The schema documents the backward-compatibility consequence (older pinned Ballast rejects such a stream), as it did for `acceptance_packet`. GitHub Actions stays the only source of truth for runs and media; the ledger keeps only the correlation ID, commit, scenario, command digest and PR number, so there is no second source of truth.
- **AGENTS.md invariants**: the tools stay stdlib-only. `demo.py` imports only the standard library and sibling tool modules, and `draft_pr` imports `demo` so `run.py` loads it before any agent step, matching the existing preload rule for `branch_sync`. The command comes only from protected `ballast.toml`, and agents gain no authority.
- **DEC-0001 / R15 execution scope**: ADR-0012's Execution scope section, the template's `GITHUB_SHA` check and `resolve`'s `commit-mismatch` agree. Dispatching on the default branch and splitting the job are recorded as rejected alternatives, with reasons.
- **TECHNICAL-SPEC §9.1**: the status paragraph records on-demand capture as in 1.0, automatic capture as later work, and cites ADR-0012 as proposed, consistent with the roadmap's Priority 6.

## Structure

`demo.py` keeps one responsibility per section: contract, GitHub reads, resolution, rendering and request. Resolution (`resolve`) follows research R6's order and is shared by the bounded wait and the packet refresh, so the request and the checkpoint cannot disagree. `draft_pr.checkpoint` is now a thin wrapper over `checkpoint_work`, which also returns the seam. The existing callers' behavior is unchanged.

## Residual observations

- Plan-review finding F-007 (PD-0009) asked ADR-0012 to name PRs based on the feature branch, which restore its caches, in the no-new-reach argument. The ADR still names only the default branch and the feature branch's own CI. The argument holds, since those PRs run code from the same branch lineage, but the boundary text is incomplete.
- `demo.py` uses five private members of `draft_pr` (`_Checkpoint`, `_classify`, `_json`, `_status`, `_now`), suppressed with `noqa: SLF001`. `draft_pr`, `demo` and `packet` now import each other in a cycle, which works only because every cross-module use happens at call time or inside postponed annotations. The seam ADR-0012 relies on is real but not a named interface; a later refactor of `draft_pr` could break `demo` without a visible contract.

The fast gate's results (the run record lists a failed `ruff`/`unittest` at fix-loop cycle 0) belong to the implementation review and the fix loop, not to this review. Same-provider review: independence is reduced.

<!-- ballast-findings: begin -->
## Findings (recorded from the review draft)

- F-001 (info, architecture-issue, resolved): Plan-review F-007 is still unaddressed: ADR-0012's no-new-reach argument does not name PRs based on the feature branch, which restore its caches. The argument holds because they run code from the same branch lineage, but the ADR should say so. Fixed in 1b0cc91: ADR-0012 names PRs based on the feature branch in its no-new-reach argument.
- F-002 (low, architecture-issue, open): demo.py depends on five private draft_pr members (_Checkpoint, _classify, _json, _status, _now) under noqa SLF001, and draft_pr, demo and packet import each other in a cycle that works only through call-time use and postponed annotations. The seam ADR-0012 relies on is not a named interface, so a later draft_pr refactor could break demo silently; expose it publicly or document the contract.
<!-- ballast-findings: end -->
