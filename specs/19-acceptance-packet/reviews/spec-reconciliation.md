# Spec reconciliation

- Reviewer: Claude Opus 5.5 (same provider as the author; independent session)
- Date: 2026-10-06
- Skill: `.agents/skills/ballast-spec-reconciliation/SKILL.md`
- Scope: `git diff origin/main...HEAD` at `ebfaecb` for #19 (`tools/spec_workflow/packet.py`, `ledger.py`, `draft_pr.py`, `run.py`, `autonomy.py`, `artifacts.py`, `ledger-schema.md`, `tests/test_packet.py` and the packet additions in `tests/test_draft_pr.py`, `tests/test_agent_run_ledger.py`, `tests/test_spec_workflow.py`, `templates/policies/spec-kit-workflow.md` §Acceptance packet, `docs/adr/0006-review-packet-reads.md`, `specs/TECHNICAL-SPEC.md`), against `spec.md` (digest `sha256:9e01600b…`, equal to the approved intent digest and to `acceptance-evidence.json`), `plan.md`, `research.md`, the contracts and `tasks.md`. The diff also carries #16's files (`origin/main` predates its merge); they are out of scope here.
- Spec Kit converge: every task but T053 is checked with evidence; no built-versus-specified gap was found that needs a new task, so none was appended to `tasks.md`.

## Evidence

- Gates (2026-10-06, at `ebfaecb`): `uvx ruff check && uvx ruff format --check` passed. `uv run --no-project --isolated --python 3.13 --with pyyaml python -m unittest tests/test_packet.py tests/test_draft_pr.py tests/test_agent_run_ledger.py` ran 227 tests, OK. The full suite result is recorded in [convergence.md](convergence.md).
- Manifest: `acceptance-evidence.json` maps AC-001 to AC-022 to existing tests in `tests/test_packet.py` (test-1 traceability table, re-checked against the class docstrings).
- Live: [live-check.md](live-check.md) steps 1–7 PASS on a scratch GitHub repository, SEC-003 re-check PASS.

## Criterion-to-evidence map

| ID | Implementation (packet.py unless named) | Executable evidence (tests.test_packet unless named) | State |
| --- | --- | --- | --- |
| AC-001 | criterion parse in spec order, title, `_line` link | CriteriaTests.test_every_criterion_once_in_spec_order_with_title_and_link; EndToEndTests | met |
| AC-002 | `evaluate`, `_blob` test-file link, `_checks`, ledger reference (DEC-0001) | CriteriaTests.test_states_follow_the_quickstart_rows, test_no_ci_at_head_and_test_file_not_found, test_test_name_without_a_safe_path_is_named_unlinked | met |
| AC-003 | `missing` with reason | test_states_follow_the_quickstart_rows, test_no_manifest_is_missing | met |
| AC-004 | `failed`/`not run`/`stale` naming commit, spec, snapshot, manifest | test_states_follow_the_quickstart_rows, test_manifest_for_another_spec…, test_dirty_checkout_evidence_is_never_verified, test_mixed_results_take_the_first_state_in_order | met |
| AC-005 | risk, decisions, findings, explicit zero counts | DecisionTests.test_autonomous_records…, test_zero_counts… | met |
| AC-006 | `human` / `agent-provisional` labels as recorded; "not an approval" line | DecisionTests.test_human_gated_approvals_are_labeled_human, test_autonomous_records… | met |
| AC-007 | sources section pinned to head, compare link | SourceTests.test_every_artifact_is_linked_at_head; live-check SC-002 link walk | met |
| AC-008 | `not present` | SourceTests.test_absent_artifacts_read_not_present | met |
| AC-009 | link or `ledger event <seq> of run <id>` | SourceTests.test_every_summary_line_carries_a_link_or_a_ledger_reference; CheckTests | met |
| AC-010 | digest compare, no edit, `unchanged` | RepublishTests.test_same_sources_make_no_edit_and_record_unchanged; live-check step (no packet edit) | met |
| AC-011 | in-place replace, `updated` | RepublishTests.test_any_source_change_replaces_the_section_in_place | met |
| AC-012 | header: feature version, base, head, time | RepublishTests.test_header_states_versions_and_time | met |
| AC-013 | span-only body edit (#17 rule) | RepublishTests.test_only_the_packet_span_changes | met |
| AC-014 | re-append when deleted | RepublishTests.test_deleted_section_is_appended_once | met |
| AC-015 | one line each when not configured | ReviewConfigTests.test_not_configured_is_one_line_each | met |
| AC-016 | `compare_documents`, `BREAKING`, human-review line | OpenApiTests.test_changes_are_listed…, test_request_field_removed_through_a_ref… | met |
| AC-017 | `no API change` / `added` / `removed` / `could not compare (<reason>)` | OpenApiTests.test_states_without_a_comparison, test_response_without_inline_content… | met |
| AC-018 | UI states beside criteria, `missing` | UiStateTests.test_results_appear_beside_their_criteria | met |
| AC-019 | fixed reasons and remedies, #17 outcome untouched | FailureTests; test_draft_pr.PacketWiringTests; test_spec_workflow.DraftPrRunTests | met |
| AC-020 | `inert` (escape, `$`, bidi, zero-width breaks for `@`, `#N`, `GH-N`) | HostileTextTests; InertTests incl. test_math_and_bidi_controls_are_inert, test_issue_references_never_autolink | met (see G2) |
| AC-021 | `_capped`, archive path named | SizeTests; OpenApiTests.test_long_lists_are_capped_in_the_pr_but_whole_in_the_archive | met |
| AC-022 | token and auth-header redaction | CredentialTests.test_no_token_reaches…; InertTests | met |

| FR | Evidence | State |
| --- | --- | --- |
| FR-001 | launcher-only call at the #17 checkpoint after trust; test_draft_pr PacketWiringTests (FR-001); security-1 authority row | met |
| FR-002 | CollectTests (objects at head, no new store); regeneration is deterministic (FR-009 tests) | met |
| FR-003 | CriteriaTests | met |
| FR-004, FR-005 | DecisionTests, CheckTests | met |
| FR-006 | SourceTests; DEC-0001 ledger references | met |
| FR-007 | RepublishTests.test_header_states_versions_and_time | met |
| FR-008, FR-009 | RepublishTests; ledger `acceptance-packet` event (test_agent_run_ledger) | met |
| FR-010, FR-012 | OpenApiTests (contents API reads only, nothing executed or downloaded; ADR-0006) | met |
| FR-011 | UiStateTests | met |
| FR-013 | InertTests, HostileTextTests; live-check SEC-003 re-check | met (see G2) |
| FR-014 | SizeTests | met |
| FR-015 | FailureTests, PacketWiringTests | met |
| FR-016 | CredentialTests | met |
| FR-017 | every listed situation has a class above; 227 targeted tests pass | met |
| FR-018 | `templates/policies/spec-kit-workflow.md` §Acceptance packet; documentation-1 approved | met |

| SC | Evidence | State |
| --- | --- | --- |
| SC-001 | `verified` only from passing evidence bound to head and spec (mutation M1 in test-1 fails two tests) | met in tests; pilot spot checks are post-merge |
| SC-002 | test_every_criterion_once…; live-check followed every Sources link at head | met |
| SC-003 | RepublishTests; live-check: no packet edit on the unchanged run | met |
| SC-004 | live-check packet on PR #11 of the scratch repository | met |
| SC-005 | FailureTests, PacketWiringTests; FR-017 row | met |

Edge cases: unknown criteria and a spec without IDs (CriteriaTests.test_unknown_criteria_and_spec_without_ids), manifest for an earlier spec (test_manifest_for_another_spec…), advanced base (test_advanced_base_keeps_head_bound_evidence), adopted PR (test_deleted_section_is_appended_once, adopted case), closed or blocked PR (FailureTests.test_no_pr_or_blocked_pr_makes_no_packet_call), human-gated run (test_human_gated_approvals_are_labeled_human), CI in progress (CheckTests and UiStateTests `not run (in progress)`, see G1).

## Gaps

- **G1 — spec edge case wording (specification stale, low).** The edge case "criteria whose only evidence is CI show `not run` with a link to the pending CI run" does not match the delivered design: under research R4 and DEC-0001 a criterion's evidence is its manifest tests, and CI is suite-wide and never changes a criterion's state. The behavior it describes exists for a UI state backed by a check run (`not run (in progress)` with the run link). Research R4 already records this reading, and no behavior is in doubt. Not edited in `spec.md`: the edit is wording only, and changing `spec.md` would make the intent approval recorded today (run `28d06dc0`) and the manifest's `spec_digest` stale, which turns every criterion `stale`. Fold the wording into the next spec revision.
- **G2 — bare commit SHAs autolink (implementation, low, residual).** The live check found that GitHub turns a bare 40-hex SHA in agent text into a commit link (no backlink, same repository). `inert` now breaks `#N`, `owner/repo#N` and `GH-N`, but not SHAs. FR-013 forbids injected links; a same-repository commit link grants nothing and posts nothing, so security-1 and the live check rate it low. Accepted for this PR; candidate for a small follow-up in `inert`.
- **G3 — contract drift (specification stale, fixed).** [packet-format.md](../contracts/packet-format.md) showed API operations in backticks; the implementation and tests write them bare (live-check observation 2). Corrected in the contract to match delivered behavior.
- **G4 — Autonomous packet refresh (new knowledge, resolved).** DEC-0002 option 3: the packet of a finished Autonomous run is final; the refresh entry point belongs to #21. US3 "stays current" holds for human-gated runs.
- **G5 — Autonomous packets show `not run` (new knowledge, follow-up).** Per-criterion evidence comes from `ballast ledger check`, so an Autonomous run's packet shows `not run` until the operator records checks. Follow-up to propose in the PR (plan §Review notes): let `run-checks` record per-criterion evidence by running the manifest's mapped tests; a new command path, so R2 under FR-012.

No behavior contradicts or exceeds the spec, and no accepted architecture decision changes (ADR-0006 extends ADR-0003 through the route ADR-0003 names; engineering-1 checked it).

## Spec text changes

None to `spec.md`. One contract wording fix (G3).

- Verdict: CONVERGED
