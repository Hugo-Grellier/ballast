# Feature Specification: Qualify the Ballast 1.0 request-to-PR path

**Feature Branch**: `test/24-v1-qualification`

**Created**: 2026-10-07

**Status**: Evidence recorded; see [qualification.md](qualification.md)

**Input**: Issue #24: "Demonstrate the complete 1.0 promise before tagging a release. Run the full local gate on the qualified Linux/systemd host and pilot blank plus established repositories through init, update/worktree, discovery, Chat and Autonomous, sync, PR, packet, on-demand video and free fallback. Record recovery drills and exact checks."

**Risk**: R1 (integration evidence). Nothing in this change touches CI, rulesets, the launcher or what `ballast` executes. The one GitHub setting the release gate needs (a ruleset that requires checks on `main`) is R2 and is listed as an operator action in [release-checklist.md](release-checklist.md), not made here.

**Sources**: [docs/plans/2026-10-02-product-roadmap.md](../../docs/plans/2026-10-02-product-roadmap.md#minimum-release-gate-for-10), [specs/TECHNICAL-SPEC.md §91](../TECHNICAL-SPEC.md#91-v10-target), the pilots deferred to this issue by #20 ([pilot.md](../20-chat-mode/reviews/pilot.md), DEC-0004), #21 (SC-001 live pilot, [quickstart](../21-autonomous-reviewed-pr/quickstart.md#live-pilot-operator-after-merge)), #22 (SC-001 and SC-004, [convergence](../22-ui-demo/reviews/convergence.md)) and #23 (live `--local-fallback` pilot, [convergence](../23-free-fallback/reviews/convergence.md)).

## Scope

In scope: running the released v0.9.0 on the qualified host against a new blank repository and against LoreForge, recording exact commands, run IDs, PR links and outcomes; the full local test gate; the recovery drills; a release checklist that links every v1.0 issue, spec and ADR and reads GitHub's required-check configuration.

Out of scope (from #24): publishing a release, tagging v1.0.0, merging any PR, adding staging or production deployment, changing CI or rulesets. Fixing a defect found here is out of scope unless it is trivial; each defect is filed as an Issue and linked from the report.

## Acceptance criteria

1. **AC-001**: A blank repository and LoreForge each complete the path to a Draft PR ready for a human merge decision; Chat and Autonomous modes are both exercised, and one requested UI demo is captured and linked.
2. **AC-002**: Fresh worktree, failed update, stale resume, merge conflict at sync, fetch failure, provider fallback and partial agent failure each have recorded recovery evidence (command, output excerpt, outcome).
3. **AC-003**: All mandatory tests, including the systemd, bwrap, Codex and Spec Kit tests CI skips, pass on the qualified host; any unavailable check is an explicit blocker.
4. **AC-004**: The release checklist links the v1.0 issues, specs and ADRs, confirms GitHub's required checks by reading them, and leaves merge and the v1.0.0 tag and release to the human operator.

## Verification

Each criterion is verified by the evidence in [qualification.md](qualification.md): exact commands, run IDs, PR links and ledger excerpts. A criterion whose evidence is incomplete is reported as blocked with the blocking Issue, never as passed.

## Assumptions and constraints

- The driving agent acts under the operator's standing authority for v1.0 issues (2026-10-05): it may answer workflow gates after reviewing the artifact, run `ballast trust` on checkouts it set up, create one private disposable repository, and open PRs. It may not merge, push to an existing default branch, change rulesets, tag or release. Gate answers it gave are therefore agent answers under that authority, not decisions a human typed; the report says so wherever a PR body reads "approved by the operator".
- The qualified host is the operator's Linux machine with a systemd user session, bubblewrap with user namespaces, Spec Kit CLI 1.0.11, codex-cli 0.155.1, Claude Code 2.1.290 and Ollama 0.35.1 serving `qwen3:4b-16k`.
