# Implementation review 1: tests

- Reviewer: Claude Opus 5.5 (same provider as the author; independent session, not a cross-provider review)
- Date: 2026-10-05
- Skill: `.agents/skills/ballast-test-review/SKILL.md`
- Scope: `tests/test_packet.py` (53 tests on HEAD `eae5f01`), the packet-related additions in `tests/test_agent_run_ledger.py`, `tests/test_draft_pr.py` and `tests/test_spec_workflow.py`, and `specs/19-acceptance-packet/acceptance-evidence.json`, against AC-001–AC-022 and FR-017.
- Seams: a real temporary Git repository with real commits and a real ledger, a scripted `gh` (no network), real operator records through `autonomy`. That is the right seam for everything except GitHub's own rendering and API, which T052's live check covers.

## Traceability

The manifest maps all 22 criteria (spec digest equals `sha256(spec.md)`); every name loads one existing test. For each, the test was read to confirm it asserts the criterion and fails when the behavior breaks.

| AC | Tests (tests.test_packet unless named) | Fails if broken? |
| --- | --- | --- |
| 001 | CriteriaTests.test_every_criterion_once_in_spec_order_with_title_and_link; EndToEndTests (created, reused) | yes: order, title, line link, count 1 |
| 002 | CriteriaTests.test_states_follow_the_quickstart_rows, test_no_ci_at_head_and_test_file_not_found | yes: exact detail text, test-file and checks links, DEC-0001 ledger reference |
| 003 | test_states_follow_the_quickstart_rows, test_no_manifest_is_missing | yes |
| 004 | test_states_follow_the_quickstart_rows, test_manifest_for_another_spec…, test_dirty_checkout_evidence_is_never_verified | yes: commit, spec, snapshot and (added) manifest staleness each named |
| 005 | DecisionTests.test_autonomous_records…, test_zero_counts… | yes |
| 006 | DecisionTests.test_human_gated_approvals_are_labeled_human, test_autonomous_records…, test_zero_counts… | yes: `human`/`agent-provisional` exclusivity asserted both ways |
| 007 | SourceTests.test_every_artifact_is_linked_at_head | yes |
| 008 | SourceTests.test_absent_artifacts_read_not_present | yes |
| 009 | SourceTests.test_every_summary_line_carries_a_link_or_a_ledger_reference; CheckTests.test_run_checks… | yes: every URL pinned to repo and head/base/run; ledger reference only where no URL |
| 010 | RepublishTests.test_same_sources_make_no_edit_and_record_unchanged | yes: edit-call count and digest |
| 011 | RepublishTests.test_any_source_change_replaces_the_section_in_place | yes: head, base, spec, evidence |
| 012 | RepublishTests.test_header_states_versions_and_time | yes |
| 013 | RepublishTests.test_only_the_packet_span_changes | yes: bytes before/after, CRLF, forbidden edit flags |
| 014 | RepublishTests.test_deleted_section_is_appended_once | yes: created and adopted PRs |
| 015 | ReviewConfigTests.test_not_configured_is_one_line_each | yes, and no contents call |
| 016 | OpenApiTests.test_changes_are_listed…, test_request_field_removed_through_a_ref… | yes: exact lines, `$ref`, cycle |
| 017 | OpenApiTests.test_states_without_a_comparison, test_response_without_inline_content… | yes: each state and reason |
| 018 | UiStateTests.test_results_appear_beside_their_criteria | yes: path, passed, in progress, missing |
| 019 | FailureTests (each failure, no PR/blocked); test_draft_pr.PacketWiringTests…; test_spec_workflow.DraftPrRunTests… | yes: #17 outcome and exit status unchanged, event reason, retry succeeds |
| 020 | HostileTextTests.test_hostile_text_cannot_forge…; InertTests.test_markers_and_html… | yes after TEST-001 (see below) |
| 021 | SizeTests (shortened and archived whole; too large) | yes |
| 022 | CredentialTests.test_no_token_reaches…; InertTests.test_tokens… | yes: stdout, ledger, archive, body |

Probe: three hand mutations of packet.py, each run against tests/test_packet.py and reverted: (M1) accept any passing event regardless of its binding: 2 failures; (M2) let `stale` win over `failed` in one criterion: **survived** (TEST-006); (M3) drop `html.escape` in `inert`: 1 failure. After TEST-006, M2 fails `test_mixed_results_take_the_first_state_in_order`.

```yaml
review: tests
verdict: approved   # after the fixes in Resolution; changes_required as found
findings:
  - id: TEST-001
    severity: medium
    category: missing test
    location: tests/test_packet.py:InertTests, HostileTextTests
    description: >
      AC-020's hostile text had no GitHub math (`$…$`) and no bidirectional
      control, so the inert gap found in security-1 SEC-001/SEC-002 was not
      caught.
    required_action: Add both to the inert and hostile-text tests.
  - id: TEST-002
    severity: medium
    category: missing test
    location: tests/test_packet.py:CriteriaTests
    description: >
      No test for a manifest test name that passes validation but maps to no
      safe path (engineering-1 ENG-001), so the internal-error was invisible.
    required_action: Regression test asserting `published` and the unlinked name.
  - id: TEST-003
    severity: low
    category: missing test
    location: tests/test_agent_run_ledger.py:test_commit_tree_touches_neither_worktree_nor_index_and_runs_no_hook
    description: >
      Hooks (`post-index-change`, `post-checkout`, `pre-commit`) are planted and
      proven inert, but a configured `core.fsmonitor` command is not; the
      override exists in NO_HOOKS and `_command`.
    required_action: Optional; add a `core.fsmonitor` sentinel when next touched.
  - id: TEST-004
    severity: low
    category: missing test
    location: tests/test_packet.py:CriteriaTests
    description: The `manifest` staleness branch of `_test` had no test.
    required_action: One assertion.
  - id: TEST-005
    severity: low
    category: missing test
    location: tests/test_packet.py:OpenApiTests.test_long_lists_are_capped…
    description: >
      Asserted the overflow line but not that it names the archive or that the
      ledger records `shortened` (engineering-1 ENG-002).
    required_action: Assert both.
  - id: TEST-006
    severity: medium
    category: missing test
    location: tests/test_packet.py:CriteriaTests
    description: >
      The spec's precedence for a criterion with mixed results (failed, then
      stale, then not run) was not tested: making `stale` win over `failed`
      passed all 53 tests (mutation M2).
    required_action: Test a criterion with one failed and one stale test, and one with stale and not-run tests.
```

## Notes

- `CollectTests.test_git_commands_only_read_with_paths_after_double_dash` sees only `_command` calls; `commit_tree`'s calls go through `ledger._git` and are covered by the ledger hook test instead. Not a gap, but the test name can mislead.
- AC evidence through the ledger: T050 records that `ballast ledger check` was not run for this feature (intent digest predates DEC-0001), so this PR's own packet will show `not run` until the operator records checks; see DEC-0002 for why an Autonomous run cannot then refresh it.

## Resolution

- TEST-001 fixed: `InertTests.test_math_and_bidi_controls_are_inert` and an extended `HostileTextTests` hostile string (split-`\text{}` approval in `$…$`, U+202E) with asserts on `$` and U+202E; both failed before the SEC-001/SEC-002 fix.
- TEST-002 fixed: `CriteriaTests.test_test_name_without_a_safe_path_is_named_unlinked` (failed before: `internal-error`).
- TEST-003 not fixed (low).
- TEST-004 fixed: `test_dirty_checkout_evidence_is_never_verified` also asserts `stale` with `manifest <12>`.
- TEST-005 fixed: overflow line names `speckit-runs/<run>/acceptance-packet.md` and the event has `shortened: true` (failed before).
- TEST-006 fixed: `CriteriaTests.test_mixed_results_take_the_first_state_in_order`, which fails under M2.
- The three new tests are added to acceptance-evidence.json (AC-004, AC-019, AC-020); its spec digest is unchanged.
- tests/test_packet.py: 53 → 56 tests. Full gate: see [engineering-1.md](engineering-1.md#resolution).

- Verdict: approved
