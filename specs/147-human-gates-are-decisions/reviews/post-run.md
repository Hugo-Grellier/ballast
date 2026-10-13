# Post-run reviews: implementation of #147

Autonomous run `2e651132` stopped on its wall-time limit (240 minutes) during `review-implementation`, after implementation, `validate-implementation` and `checks-implementation`. Its test check had timed out at the 30-minute `[checks]` limit (#146). The operator chose on 2026-10-13 to finish outside the run: the operator's agent session ran four independent reviews of the working tree (engineering, security, test, documentation, each following its `ballast-*-review` skill, read-only), fixed the findings below, and ran the full suite. Same provider as the author: reduced independence. These reviews are not run records and carry no approval.

## Fixed

| Finding | Severity | Fix |
| --- | --- | --- |
| Engineering F1, security SEC-002: a batch with `intent` wrote `intent.md` before a later gate's requirement could refuse | high | `chat._record_all_or_none` restores `intent.md` on any refusal; test `test_a_later_refusal_restores_intent_md` |
| Engineering F2, security SEC-001: a relayed intent approval wrote `Approved by: human user` | high | `artifacts.record_intent(relayed_by=)` writes `relayed by agent session S`; test `test_a_relayed_intent_approval_never_reads_as_a_human_user` |
| Engineering F3, security SEC-003: an inherited `BALLAST_REFRESHED` forged the refresh line and the runner-only `trust_refresh` event | medium | the launcher drops any inherited value; test `test_an_inherited_announcement_is_never_passed_on` |
| Engineering F4: a failed download of the pinned standard ended every `run`, `ledger` and `intake` | medium | `refresh_before` skips the refresh and the launcher's refusal shows; ADR-0020 states the new download; test `test_a_failed_download_falls_through_to_the_launcher` |
| Security SEC-004, engineering F6: refresh ran inside a step and on every `run status` | low | skipped with `BALLAST_AGENT_STEP` and for `run status`; test `test_never_refreshes_in_a_step_or_for_status` |
| Test T-02: a relayed human-gated engine run read the caller's stdin | medium | `run._launch` gives the engine `/dev/null` without a terminal; test `test_without_a_terminal_the_engine_reads_no_input` |
| Test T-01: the headless Chat step had no real-`bwrap` confinement test | medium | `test_a_headless_step_cannot_reach_operator_records_under_real_bwrap` |
| Engineering F5: a Chat headless usage-limit stop closed as failed | low | treated as interrupted, as in Autonomous |
| Engineering F7: the next-gates hint printed after a failed step and suggested `--through` over unready gates | low | printed only after success, naming the ready gates |
| Documentation DOC-01 to DOC-04 | medium/low | contract row split for relayed `approve`; baseline wording; quoted refresh lines; Chat sentences moved back |
| Security SEC-005, SEC-006 | low | stated as ADR-0020 residual risks |

## Not fixed

- Documentation DOC-05 (matrix footnote for a Chat run switched to human-gated) and DOC-06 (`rerun rerun` rendered by a test-pinned template): wording only.
- Test T-03 to T-07: assertion depth in existing tests (batch listing digests, engine-run refusal side effects, combined recovery line, test naming, human-gated usage-limit record).
- Engineering F6's negative-verdict cache: `run status` no longer refreshes, which removes the frequent case.
