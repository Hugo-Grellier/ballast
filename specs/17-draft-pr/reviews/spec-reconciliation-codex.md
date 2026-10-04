FAILED

The committed `origin/main...HEAD` diff covers the main Draft PR flow, but the authority boundary and failure handling are not ready for acceptance. This is a read-only review; the test names below identify executable evidence in the repository, not tests rerun in this session.

| Criterion | Code file:line | Executable evidence |
| --- | --- | --- |
| AC-001 / FR-006, FR-016 — create a Draft PR | `draft_pr.py:473, 748, 767` | `CreationTests.test_meaningful_change_without_pr_creates_one_draft`; `BodyTests.test_base_branch_template_precedes_the_section` |
| AC-002 / FR-010 — report and record it | `draft_pr.py:391, 945`; `ledger.py:1788` | `LedgerReportTests.test_report_shows_latest_pull_request_outcome` |
| AC-003–005 / FR-003, FR-004 — wait for a meaningful published diff | `draft_pr.py:494, 718` | `PendingTests.test_head_missing_on_github_is_not_published`, `test_spec_only_or_empty_differences_are_not_meaningful`, `test_capped_spec_only_list_is_unclassified` |
| AC-006–008 / FR-005, FR-007, FR-008 — reuse without changing readiness or human text | `draft_pr.py:614, 630, 672` | `ReuseTests.test_canonical_section_is_reused_without_edit`, `test_hand_opened_pr_without_reference_gets_the_section`, `test_ready_pr_is_never_turned_back_into_a_draft` |
| AC-009 / FR-009 — concurrent checkpoints | `draft_pr.py:767, 904` | `ConcurrencyTests.test_two_concurrent_checkpoints_create_one_pr` |
| AC-010 / FR-002, FR-011 — retryable failure without changing the run result | `draft_pr.py:363, 957`; `run.py:170, 210` | `RetryableFailureTests.test_each_stage_and_failure_is_retryable_with_its_remedy`; `DraftPrRunTests.test_raising_checkpoint_never_changes_the_exit_status` |
| AC-011–012 — ambiguous, closed or merged PR | `draft_pr.py:630` | `BlockedOutcomeTests.test_two_open_prs_are_ambiguous`, `test_closed_or_merged_pr_blocks` |
| AC-013 / FR-012 — Issue identity | `draft_pr.py:494, 594` | `IdentityTests.test_feature_without_issue_number_is_unlinked_before_any_command`, `test_missing_issue_or_pull_request_number_is_unlinked` |
| AC-014 / FR-001, FR-013 — credential boundary | `draft_pr.py:231, 945`; `run.py:148` | `LeakageTests.test_no_credential_reaches_output_or_ledger`; `DraftPrRunTests.test_engine_never_receives_github_tokens_but_checkpoint_does` |

FR-014 has named offline tests for its listed situations. FR-015 has operator documentation in `templates/policies/spec-kit-workflow.md:516`. The working tree gained uncommitted edits during this review; this verdict applies to **committed HEAD**.

### Actionable gaps

1. **Implementation wrong — initial branch authority.** `pin_branch` trusts the current Git `HEAD` at the start of a *new* run (`draft_pr.py:282`; `run.py:159`). The accepted threat model treats that state as agent writable. An earlier agent can leave the checkout on another branch in the pinned repository, which the next run then adopts with operator GitHub authority. Bind new-run branch identity to operator-controlled intent and add a two-run steering test. Reconcile the proposed ADR-0003 before its approval.

2. **Implementation wrong — operator state and executable locations.** `state_dir` accepts `XDG_STATE_HOME` under an agent-writable location (`launcher.py:68`), allowing the branch pin to be changed. Reject such a state path and test it. `ledger.py:369` also trusts absolute `PATH` entries outside Git trees and the enumerated temp roots; establish that those roots exhaust each supported agent’s write authority, or restrict executable resolution further.

3. **Implementation wrong — malformed successful GitHub responses.** In committed HEAD, malformed PR-list JSON becomes an empty list (`draft_pr.py:614, 824`), permitting creation without a reliable existing-PR check. Malformed compare data becomes `pending/no-meaningful-change` (`draft_pr.py:732`). Make these retryable failures and add negative tests. An **uncommitted** edit addresses the compare case only; it does not resolve the committed diff or the PR-list case.

4. **Specification stale — accepted decision drift.** The spec still says a differently named upstream is followed (`spec.md:82`), while DEC-0010 and `draft_pr.py:568` treat it as unpublished. FR-003 and the policy promise a PR for every meaningful published diff, while DEC-0008 permits `pending/diff-unclassified` at GitHub’s 300-file cap. Explicitly reconcile those promises with the provisional decisions; do not change the spec merely to excuse behavior. The plan’s `python3 -I` and “never reads agent-written text” statements (`plan.md:11, 15`), research R5, and checked T010/T042 descriptions also need correction. The launcher now uses `-IS`.

5. **New knowledge discovered — qualification is incomplete.** T038 is checked, but its evidence says the spec-only live step was skipped and used a direct `draft_pr` invocation on Ballast rather than the specified disposable-project `ballast run` path. Complete and record that live path, including the skipped step. T039’s required R2 reviews and T040’s reconciliation and human approval of proposed ADR-0003 remain unchecked (`tasks.md:142–144`). No new task is needed for those existing entries.

A read-only converge pass would require new tasks for gaps 1–4; it would leave T038–T040 open. No files were modified by this review.