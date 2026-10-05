# Plan review: source-linked acceptance packet (#19)

- Review: plan
- Reviewer: claude/claude-opus-5-5, fresh context, acting as reviewer for Autonomous run `97858712` (same provider as the author; the run record notes the codex fallback, DEC-0004)
- Verdict: approved (agent-provisional)

## What was reviewed

The feature's `spec.md`, `intent.md` (provisional digest PD-0003), `plan.md`, `research.md` (R1–R18), `data-model.md`, `quickstart.md`, the three contracts (`checkpoint-integration.md`, `packet-format.md`, `ledger-acceptance-packet-event.md`) and the run record `autonomous/record.md`. `tasks.md` and `decisions.md` do not exist yet, which is expected at the plan gate. The policy context was `AGENTS.md`, `docs/policies/workflow.md` (risk table and review matrix), `docs/policies/engineering.md`, `docs/policies/project/workflow.md` (R2 boundaries) and ADR-0003. `docs/policies/project/engineering.md` does not exist.

The plan's claims about existing code were checked against the code itself:

- `tools/spec_workflow/ledger.py:992-1005`: `_approved_spec_ids` matches only `^- **AC-NNN**:`. This spec, like the Spec Kit template, writes `1. **AC-NNN**:`, so the R6 defect is real and fixing it falls within the feature's scope.
- `ledger.py:717-724` and `975-989`: `implementation_tree` builds a private index from the worktree alone and is the `tree` of `artifact_digests`. All of its callers (`ledger.py:950, 1765, 2412, 2433, 2442, 2521`) compare values inside the ledger, so R3's seeded-index change and the new `commit_tree` stay inside one module.
- `ledger.py:2428-2462`: `ledger check` records `snapshot`, `spec_digest` and `manifest_digest` but no commit. That matches R3's premise and the new optional `commit` field.
- `ledger.py:317`: `RUNNER_ONLY` already holds `pull_request`, so adding `acceptance_packet` follows the same additive pattern as #17.
- `tools/spec_workflow/draft_pr.py:46-47, 442, 710-754, 986-1015`: the #17 markers differ from the proposed packet markers. `_after`, the re-read-before-edit rule (DEC-0007), `gh pr edit --body-file -` and the `checkpoint` → `_record` order all exist where the plan puts the packet step. Only `create` takes the clone-wide lock (`draft_pr.py:811`), and the packet's body edits follow #17's unlocked `reuse` path with the same re-read guard.
- `tools/spec_workflow/autonomy.py:162-165`: `HUMAN_APPROVAL` is the same pattern the packet-format contract cites. `autonomy.py` imports `draft_pr` only lazily (`_trusted()`), so `draft_pr` → `packet` → `autonomy` creates no import cycle when the module loads.
- `draft_pr.py:67`: #17 already reads the intake comment's `Risk:` field, which R7 relies on for human-gated runs.
- `docs/adr/0003-launcher-github-authority.md:17,28`: the command allowlist is fixed, and "later features extend this allowlist by a new ADR rather than adding a second path". Proposed ADR-0006 is the route that ADR asks for.

## Coverage against the spec

Every acceptance criterion from AC-001 to AC-022 and every FR-017 situation has at least one named scenario in `quickstart.md`. Every edge case in the spec has a research decision: unknown criteria, a spec without IDs, a stale manifest, CI in progress, an adopted PR, a closed or blocked PR and human-gated mode. The FR-to-design trace holds:

- trusted launcher only, inside #17's checkpoint and after its tamper refusal (FR-001, R1);
- a regenerable projection with no new store (FR-002, data model);
- five evidence states bound to the head fingerprint, spec and manifest (FR-003, R3/R4);
- labels copied from structured records only (FR-004/005, R7);
- Ballast-built links and a sources section (FR-006, packet format);
- a masked digest for idempotency and one marked section (FR-008/009, R13);
- JSON-only OpenAPI read through the existing `gh` (FR-010/012, R10);
- configuration in the protected `ballast.toml` (R12), with an inert renderer (FR-013, R9);
- level-based shortening and an archive copy (FR-014, R14/R15);
- failure isolation (FR-015, checkpoint contract);
- token redaction (FR-016);
- policy documentation and ADR-0006 (FR-018).

The plan reports PD-0002's ordering rule (`failed` before `stale` before `not run`) as an agent-provisional default. R5 states honestly that Autonomous runs will show `not run` until the operator records per-criterion checks, and it leaves the R2 alternative to a follow-up.

## Risk recheck

I confirm R1. R18 walks through the four project R2 boundaries:

- agents get no new permission, token or tool;
- `[review]` adds keys to an input that is already trusted and protected, not a new trusted input;
- the launcher runs no new program and downloads nothing; its new calls are read-only `gh api` and Git plumbing on a private index;
- installed paths do not change.

The one GitHub write is the PR-body edit ADR-0003 already allows, applied to a second marked section. Under ADR-0003's own wording, extending the read allowlist calls for an ADR, not a trust-model change. That makes ADR-0006 an architecture-boundary record, and the review matrix requires an architecture review of it at implementation time.

## Reviews this change needs

The plan's notes require engineering, test, security and documentation reviews. I add `architecture`, because ADR-0006 extends ADR-0003's authority allowlist. These kinds are listed in the draft's `required_kinds`; the engineering and test reviews come from the implementation review.

## Observations for the implementer

The draft records the findings and their dispositions. In summary:

1. The data model says the packet validates the manifest "with the same rules as `ledger.archive_manifest` except the intent-approval check". Those rules also reject:
   - a `spec_digest` that differs from the current spec;
   - an AC set that differs from the spec's set.

   Applied as written, they would turn the R4 `stale`, `missing` and "unknown criteria" cases into `failed-retryable/manifest-malformed`. R4 and the quickstart define the intended behavior unambiguously, so the tasks have to name a validation that checks schema shape only.
2. #17 rewrites its `Last checkpoint` line whenever the time changes (`draft_pr.py:727-731`). On a real clock, a checkpoint with no source change still edits the PR description. R13 narrows AC-010 to the packet's own edit and tests with a fixed clock, but it does not mention SC-003's "zero PR description edits".
3. The `implementation_tree` change also changes the `snapshot` that review and convergence events bind to (`ledger.py:1765, 2412-2424`), not only verification events. The upgrade note mentions only per-criterion checks.

<!-- ballast-findings: begin -->
## Findings (recorded from the review draft)

- F-001 (medium, spec-violation, accepted-provisionally): The data model's Manifest section says the packet validates the manifest with the same rules as ledger.archive_manifest, minus the intent check. Those rules also require spec_digest to equal the current spec, the manifest's AC set to equal the spec's set, and every list to be non-empty. Applied literally, they would turn the R4 'stale' state (manifest written for an earlier spec), 'missing' (AC not mapped, AC-003) and the 'unknown criteria' edge case into failed-retryable/manifest-malformed. R4, the packet format and the quickstart rows define the intended behavior unambiguously, so this can wait for the tasks: they must name a validation that checks schema shape only, and the existing quickstart rows test it.
- F-002 (low, spec-ambiguity, open): #17 rewrites its 'Last checkpoint' line whenever the time changes (draft_pr.py reuse), so on a real clock a checkpoint with no source change still edits the PR description. R13 narrows AC-010 to the packet's own edit and tests with a fixed clock. SC-003 ('zero PR description edits') gets no such reading. Clarify both to mean edits made by the packet, during spec reconciliation or as a wording fix.
- F-003 (low, architecture-issue, open): The seeded implementation_tree also changes the snapshot that review and convergence events bind to (ledger.py report freshness and the record binding), not only per-criterion verification events. For a run that spans the upgrade, the ledger report will show earlier reviews as stale. The upgrade note in the quickstart and contract mentions only re-running ledger check, so it should also cover reviews and convergence.
<!-- ballast-findings: end -->
