# Review: spec reconciliation

- Role: reconciliation reviewer
- Agent/model: claude/claude-opus-5-5, the driving agent; same provider as the author and the other reviewers, so independence is reduced
- Base: `origin/main..HEAD` (the whole feature branch, rebased on `b90ea0f` with #82's confined checks)
- Artifacts: [intent.md](../intent.md), [spec.md](../spec.md) (FR-007 and AC-010 as reworded by DEC-0001), [plan.md](../plan.md), [research.md](../research.md), [data-model.md](../data-model.md), [contracts/](../contracts/), [quickstart.md](../quickstart.md), [tasks.md](../tasks.md), [decisions.md](../decisions.md), the plan and implementation reviews in this directory, `tools/spec_workflow/demo.py`, `draft_pr.py`, `packet.py`, `run.py`, `ledger.py`, `ledger-schema.md`, `templates/github/workflows/ballast-demo.yml`, `templates/policies/spec-kit-workflow.md`, `README.md`, `specs/TECHNICAL-SPEC.md`, ADR-0013 and the tests
- Converge: T001..T041 are checked; comparing the plan, contracts, data model and quickstart with the code appended no task. SC-001 and SC-004 are post-merge operator evidence and were never tasks (tasks.md, Acceptance evidence).
- Verdict: CONVERGED

## Criterion to implementation and evidence

| Criterion | Implementation | Evidence (`tests/`) |
|---|---|---|
| AC-001 | `demo.request` → `_Request.execute`: contract, `checkpoint_work(create=False)`, PR head, workflow identity, dispatch on the feature branch, `demo_capture` event, bounded wait, one refresh | `test_demo.RequestTests.test_request_follows_adr_0013_on_the_feature_branch` |
| AC-002 | `resolve` (success → artifact), `format_line` `[video]` for a current `captured` | `test_captured_line_links_the_video` |
| AC-003 | `collect` marks a capture for another commit `stale`; `format_line` links the job, never the video | `test_stale_captures_show_their_commit_and_never_the_video` |
| AC-004 | `_Request.wait` (10 s polls, 120 s bound), `resolve` `in progress`; the checkpoint's packet step refreshes | `test_in_progress_queued_and_run_not_found`, `test_wait_stops_when_the_run_completes`, `test_wait_is_bounded_then_refreshes_once`, `test_no_wait_reads_no_run_list_before_the_refresh` |
| AC-005 | `Sources.demo` read only by `demo.lines`; packet intro line; marker and approval guards in `render` | `test_packet.DemoIsolationTests` |
| AC-006 | `_newest` per scenario; one section; `create=False` | `test_repeated_request_shows_the_newer_one_in_one_section` |
| AC-007 | `_code` shows the declared command in a code span (DEC-0002); `command_changed` note | `test_reproduce_names_the_declared_command`, `test_reproduce_shows_shell_syntax_as_declared`; policy "Reproducing locally" (`test_governance.DemoPolicyTests`) |
| AC-008 | Template: `workflow_dispatch` only, `contents: read`, no secrets, checkout of the requested commit with `persist-credentials: false` | `TemplateTests.test_template_shape`, `TemplateLogicTests` |
| AC-009 | Policy "Data" paragraph and template header | `test_governance.DemoPolicyTests` |
| AC-010 | `check_workflow` blob identity (`workflow-differs`); dispatch ref is the feature branch and never the fetched default branch; template `GITHUB_SHA` and `HEAD` checks; `resolve` `commit-mismatch` | `test_differing_or_absent_head_copy_is_refused`, `test_never_dispatches_on_the_repository_default_branch`, `test_run_at_another_commit_is_commit_mismatch`, `TemplateLogicTests.test_validation_accepts_a_request_and_refuses_hostile_inputs` |
| AC-011 | `FAILED_STEPS` from the failed step's name; exit routing in the template | `test_failure_causes_from_step_names`, `TemplateLogicTests.test_exit_status_routes_to_one_classification_step` |
| AC-012 | `no-video`, `expired`; the template's in-workspace video check | `test_missing_videos`, `TemplateLogicTests.test_video_must_be_a_file_inside_the_workspace` |
| AC-013 | Packet refresh in place through #17's checkpoint | `test_failures_are_published_in_place` |
| AC-014 | `settle`/`head` refusals before any dispatch | `test_pr_states_refuse_without_dispatch` |
| AC-015 | `not-configured` refusal; `Demo captures: not configured.` | `test_absent_contract_refuses_and_the_packet_still_publishes` |
| AC-016 | `demo_config` fixed `ERRORS`, `packet.safe_path` for the video; `unknown-scenario` | `test_invalid_contract_names_a_fixed_reason`, `test_undeclared_scenario_names_the_declared_ones` |
| AC-017 | Defaults 14/15, bounds 1-90/1-60 in Python and in the template | `test_defaults_and_overrides_reach_the_dispatch`, `TemplateLogicTests` |
| AC-018 | `draft_pr._classify` causes; no token in output, ledger or body; read failures while collecting fail the packet step retryable | `test_forge_failures_are_retryable_and_leak_no_token`, `test_failed_reads_while_collecting_fail_the_packet_step` |
| AC-019 | `run.py demo`: `_untrusted` markers and the invocation lock before `demo.request`; agents keep `gh` denied | `test_spec_workflow.DemoAuthorityTests` |

FR-001..FR-020 trace through the same code; FR-015 to ADR-0013's call list (checked against every `_get`, `_runs`, `_failed_step`, `_artifact` and `dispatch` call), FR-016 to the absence of any download argv, FR-020 to `StandardLibraryTests`. The ledger event is covered by `test_agent_run_ledger.DemoCaptureEventTests`. SC-002, SC-003, SC-005 and SC-006 are covered offline by the tests above; SC-001 and SC-004 need a live pilot (below).

## Gaps and how each was settled

- **AC-007 versus the rendering contract** (new knowledge discovered): `packet.inert`'s Markdown escapes and HTML entities show literally inside a code span, so the line did not name the command as declared. Resolved by DEC-0002 option 2; the contract `packet-demo-section.md` and the policy now describe the code-span rendering, and the code and tests follow them. FR-018's "escaped inert data" holds for the command through the code span itself: GitHub renders no markup inside it, and what could leave the span or forge packet text (backticks, control characters, tokens, `<!--`, approval wording) is still neutralized. The spec is unchanged.
- **Default-branch guard** (implementation wrong): `dispatch` compared the ref only with the run's base. It now also refuses the default branch read just before the dispatch, as FR-007 states.
- **Packet read failures, template logic and the stdlib guard** (missing tests): added, see the table.
- **ADR-0013's no-new-reach argument** (plan review F-007, specification stale): now names PRs based on the feature branch.
- **Plan review F-005**: closed by T007, which asserts the full argv sequence. **Plan review F-006**: `_runs` builds the query with `urllib.parse.urlencode`, so `>=` is percent-encoded; `test_request_follows_adr_0013_on_the_feature_branch` decodes it back to `>=<date>`.
- **Documentation**: the policy now names a local error after a successful dispatch and that the outcome is reported by the job that runs the PR's code; the README says to commit the workflow on the default branch before cutting feature branches.

Nothing in the code exceeds the spec: no automatic capture, no local execution, no download, no PR creation, no new agent authority, and the video never changes an evidence state.

## Left open for later work

- `demo.py` uses five private `draft_pr` members, and `demo`, `draft_pr` and `packet` import each other with call-time use only (architecture review F-002). It works and is tested; naming the seam is a refactor for later work.
- Ballast's own Dependabot does not scan `templates/github/workflows/`, so the template's action pins get no update PRs (dependency review F-002). This is a repository-wide question for every shipped template.
- SC-001 (live pilot) and SC-004 (local reproduction of a real captured journey) need the template on a default branch, so they run after merge as part of #24's request-to-PR qualification.
