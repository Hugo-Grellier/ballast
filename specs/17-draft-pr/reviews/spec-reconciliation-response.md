# Response to spec-reconciliation-codex.md (2026-10-04)

| Gap | Diagnosis | Resolution |
| --- | --- | --- |
| 1. Initial branch authority | accepted residual | DEC-0012 (a): `ballast run start` prints `Draft PR: branch pinned: <branch>` before any agent runs; exploitation needs an earlier compromised run and is limited to Draft PR metadata in the pinned repository. Launcher-wide Git write boundary tracked in #34. |
| 2. Operator state and executable locations | implementation wrong (state) / accepted boundary (PATH) | The pin is neither written nor trusted under the checkout or a temp root (T044, `test_pin_in_agent_writable_state_is_never_trusted`). PATH boundary: DEC-0012 (b); launcher-wide state directory and PATH allow-list tracked in #34. |
| 3. Malformed successful responses | implementation wrong | Fixed: PR list and Issue comments must be a list of pages, compare must carry a `files` list, else `failed-retryable/github-error` (`test_malformed_list_is_retryable_never_empty`, `test_malformed_compare_is_retryable_not_empty`). |
| 4. Accepted decision drift | specification stale | `spec.md` edge case and FR-003 amended for DEC-0010 and DEC-0008; intent re-approved under standing authority with provenance in `intent.md`. |
| 5. Qualification incomplete | new knowledge | Step 2 run live on a throwaway spec-only branch; direct checkpoint invocation documented in T038 with the `run.py` path covered by `DraftPrRunTests`. T039 (reviews) and T040 (this reconciliation, ADR) are being closed now. |
