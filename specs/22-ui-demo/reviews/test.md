# Test review: On-demand UI demo capture (#22)

- Review: implementation (test), first review, before any fix cycle
- Reviewer: claude-opus-5-5, fresh context, same provider as the author
- Inputs: `spec.md` AC-001..AC-019 and SC-001..SC-006, `quickstart.md` scenarios 1–23, `tasks.md` (Acceptance Criteria Coverage and the analyze items carried forward: C1, C2, C3), `docs/policies/testing.md` and `docs/policies/project/testing.md`.
- Tests read: `tests/test_demo.py` (new) and the additions to `tests/test_packet.py`, `tests/test_spec_workflow.py`, `tests/test_agent_run_ledger.py` and `tests/test_governance.py`.

## Mapping of criteria to executable evidence

| Criterion | Evidence |
| --- | --- |
| AC-001, AC-019 (dispatch, call order, feature-branch ref) | `RequestTests.test_request_follows_adr_0012_on_the_feature_branch` runs through `run.main`. It asserts the five reads before the dispatch, the dispatch argv, `ref == feat-x` and not `main`, string inputs, the ledger event and its position between two `pull_request` events, and no `pr create`. This also closes analyze C2. |
| AC-002 | `PacketLineTests.test_captured_line_links_the_video` |
| AC-003 | `test_stale_captures_show_their_commit_and_never_the_video` (captured, failed and missing at an old commit) |
| AC-004, FR-009 | `test_in_progress_queued_and_run_not_found`, `test_wait_stops_when_the_run_completes`, `test_wait_is_bounded_then_refreshes_once` and `test_no_wait_reads_no_run_list_before_the_refresh`, with an injected clock and sleep |
| AC-005, FR-014 | `test_packet.DemoIsolationTests` (everything outside the section is identical for each demo state; marker and approval guards) |
| AC-006, SC-003 | `test_repeated_request_shows_the_newer_one_in_one_section` |
| AC-007 | `test_reproduce_names_the_declared_command` and `test_hostile_project_text_is_inert`. Both use commands without characters that `inert` escapes (see DEC-0002 in the engineering review). |
| AC-008, AC-017, SC-005 | `TemplateTests.test_template_shape` (static) and `test_defaults_and_overrides_reach_the_dispatch` |
| AC-009 | `test_governance.DemoPolicyTests` |
| AC-010 | `test_differing_or_absent_head_copy_is_refused`, `test_run_at_another_commit_is_commit_mismatch`, and the template test's `GITHUB_SHA` check |
| AC-011, AC-012 | `test_failure_causes_from_step_names` and `test_missing_videos` (also no log or artifact download argv) |
| AC-013 | `test_failures_are_published_in_place` |
| AC-014 | `test_pr_states_refuse_without_dispatch` (no PR, several, closed, merged) |
| AC-015, AC-016 | `test_absent_contract_refuses_and_the_packet_still_publishes`, `test_invalid_contract_names_a_fixed_reason` (each bound, and one past it) and `test_undeclared_scenario_names_the_declared_ones` |
| AC-018, SC-006 | `test_forge_failures_are_retryable_and_leak_no_token`: five request stages × five failures, a token on stderr, and `packet.TOKEN` checked in stdout, the ledger and the PR body |
| Authority (AC-019) | `test_spec_workflow.DemoAuthorityTests`: tamper marker, in-progress marker, held lock and bad arguments, each with no `gh` call |
| Ledger | `test_agent_run_ledger.DemoCaptureEventTests`: accept, reject values outside the contract, not offered by `record`, newest per scenario in `report` |

The tests drive the real seams: `run.main`, `demo.request`, `draft_pr.checkpoint` and `packet` collect/render, with only `gh` faked by #17's scripted fake. The negative cases assert both the refusal text and the absence of a dispatch, an event and a PR, so they fail if a refusal path starts dispatching. SC-001 and SC-004 are post-merge pilot evidence (research R13), so no offline test can cover them.

## Gaps

- The packet contract's rule "a GitHub read failure while collecting demo data makes the packet step `failed-retryable`" (`packet.py:999-1002`) has no test. `DemoGitHub.failures` is exercised only for the request stages (`repo`, `pull`, `workflow`, `blob`, `dispatch`), never for the run-list, jobs or artifacts reads made by `demo.collect`. This is analyze item C1, carried forward by tasks and still open.
- The template's shell and expression logic is checked only for presence:
  - the validation regexes;
  - the `if:` routing of exits 124/137, other non-zero exits and 0 to the three classification steps;
  - the `realpath` workspace check.
  The `if:` expressions are not asserted at all.
- FR-020 has no import guard for `demo.py`; `test_branch_sync.py:353` has one for its own module (analyze C3).

## Gate evidence

I could not run the suite in this reviewer session. The home directory is read-only, so `isolate_operator_state` fails to create `~/.local/state/ballast-tests/*` and 659 tests error in setup. The runner's cycle-0 feedback checks also failed, and the engineering review names a confirmed `ruff format` violation. Passing tests are therefore not yet demonstrated for this diff. The trusted `[checks]` run must show them.

<!-- ballast-findings: begin -->
## Findings (recorded from the review draft)

- F-001 (medium, missing-test, resolved): packet.py:999-1002 turns a demo.ReadError from demo.collect into a failed-retryable packet step, as packet-demo-section.md requires. No test makes the run-list, jobs or artifacts read fail; DemoGitHub.failures is exercised only for the request stages. A regression that swallowed the error and rendered queued, or crashed the step, would pass. Add a packet test for each of the three reads that asserts failed-retryable with the classified cause and an unchanged Draft PR outcome. Fixed in 78759c2: test_failed_reads_while_collecting_fail_the_packet_step covers the run-list, jobs and artifacts reads.
- F-002 (low, missing-test, resolved): The template test asserts that steps exist, are ordered and are named, but not their logic. The if: expressions that route exits 124/137, other non-zero exits and 0 to the three classification steps are never asserted, and the validation regexes and the realpath workspace check never run. Assert the if: strings, and run the Validate and video-check scripts under bash with fixture env values, both valid and hostile. Fixed in 78759c2: TemplateLogicTests evaluates the if: routing and runs the validation and video-check scripts under bash.
- F-003 (low, missing-test, resolved): FR-020 requires demo.py to stay standard-library-only, but no test guards its imports. test_branch_sync.py has a sys.stdlib_module_names guard for its own module (analyze C3). Add the same check for demo.py. Fixed in 78759c2: StandardLibraryTests guards demo.py's imports and imports it under python -I -S.
<!-- ballast-findings: end -->
