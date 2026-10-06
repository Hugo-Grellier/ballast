# Quickstart: validating demo capture

How to prove the feature works. The contracts are in [contracts/](contracts/) and the entities in [data-model.md](data-model.md).

## Prerequisites

- Fast gate: `uvx ruff check && uvx ruff format --check` and `uv run --no-project --python 3.13 --with pyyaml python -m unittest tests/test_*.py`.
- Every scenario below is offline. `gh` is #17's scripted `_command` fake, Git is a real temporary repository, the clock is injected and the ledger is written through `ledger.append`. No test dispatches a real workflow.

## Scenarios (new `tests/test_demo.py` unless noted)

| # | Scenario | Expected | ACs |
| --- | --- | --- | --- |
| 1 | Valid contract, `reused` Draft PR, `ballast run demo RUN login-journey --no-wait` | The argv sequence is exactly ADR-0012's. The two contents reads return the same blob `sha`. The dispatch stdin JSON has `ref` = the feature branch (never the default branch), `commit` = PR head and the declared command. One `demo_capture` event is written. The output starts `Demo capture: in progress (queued)`. No `pr create` call. | AC-001, AC-010, AC-019 |
| 2 | Run list returns the matching `display_title`, `completed/success`, unexpired artifact | The packet line shows `captured at <head12>` · `[video](…/actions/runs/R/artifacts/A)` · environment · reproduce command | AC-002, AC-007 |
| 3 | Event commit ≠ PR head, for `captured`, `failed` and `missing` | `stale (<outcome> at <commit12>; head is …)`, no `[video]` link | AC-003 |
| 4 | Run `in_progress`, or no run yet within 24 h; then a second checkpoint with the run completed | `in progress (running|queued)` with job link, then the final outcome | AC-004 |
| 5 | Any demo state | The criteria lines, counts and digest of everything outside the demo section are identical with and without demo data. No `approved`/approval wording passes the guard. | AC-005 |
| 6 | Two requests for the same commit and scenario | The packet shows the newer request. The PR body has one packet section and one demo section. No `pr create`. | AC-006 |
| 7 | Static test of `templates/github/workflows/ballast-demo.yml` (pyyaml) | `permissions == {"contents": "read"}`, exactly one job, no job-level permissions, no `secrets.`/`environment:`, no `${{` inside any `run:`, the job's `timeout-minutes` is the integer `65` (not a string, no `${{`), the command step runs `timeout --kill-after=30s "${TIMEOUT}m"` with `TIMEOUT` from `inputs.timeout_minutes` via `env:`, the validate step compares `GITHUB_SHA` with the commit input, the only `uses:` are `actions/checkout` and `actions/upload-artifact` pinned to 40-hex SHAs (no `actions/cache`, no `cache:` input), `persist-credentials: false`, checkout `ref: ${{ inputs.commit }}`, the step names in [capture-workflow.md](contracts/capture-workflow.md#steps-in-order-names-are-part-of-the-contract-research-r5), `workflow_dispatch` the only trigger | AC-008, SC-005 |
| 8 | Docs check (`tests/test_governance.py`, alongside its existing policy-text checks) | `templates/policies/spec-kit-workflow.md` names `ballast run demo`, every packet demo state, the reproduce command, the seeded/nonsensitive data and repository-read-access warning, that a command exiting 124 or 137 itself is reported `timed-out`, and that a feature branch must carry the default branch's `ballast-demo.yml` | AC-007, AC-009 |
| 9 | Failed step `Demo command failed` / `Demo command timed out` / conclusion `cancelled` / conclusion `timed_out` / unknown step | `failed (command-failed|timed-out|cancelled|timed-out|job-failed)` with job link, no video link | AC-011 |
| 10 | Failed step `Demo video missing`; success with `expired: true`; success with no artifact | `missing (no-video|expired|artifact-absent)`, no video link | AC-012 |
| 11 | Failed and missing captures | The packet is published with `updated`, through `gh pr edit`. The argv has no `pr create`. | AC-013 |
| 12 | Checkpoint `skipped no-draft-pr`; `blocked-*`; PR closed or merged | `refused (no-draft-pr|pr-not-open)`, exit 1, no dispatch call, no event | AC-014 |
| 13 | No `[demo]` table | `refused (not-configured)` with remedy. The packet shows `Demo captures: not configured.` and still publishes. | AC-015 |
| 14 | Unknown key; `video = "../x"`; `video = "/etc/x"`; undeclared scenario; each limit at its bound and one past it | `refused (config-invalid|unknown-scenario)` with the fixed reason. The packet shows `configuration invalid (<reason>)`. No dispatch. | AC-016 |
| 15 | Contract without `retention_days`/`timeout_minutes`; with 30/45 | Dispatch inputs `"14"`/`"15"`; `"30"`/`"45"` | AC-017 |
| 16 | `gh` timeout, exit 4, HTTP 401, 403, 404 on the workflow, 500; the fake writes a `ghp_…` token to stderr | `failed-retryable (<cause>)` or `refused (workflow-not-installed)`. No `packet.TOKEN` match in stdout, stderr, the ledger or the packet. | AC-018, SC-006 |
| 17 | `ballast run demo` while the tamper or `in-progress` marker exists, or the run lock is held | `refused (untrusted|lock-held)`, no `gh` call (`tests/test_spec_workflow.py`) | AC-019 |
| 18 | Hostile scenario environment and command: section markers, `[x](javascript:…)`, `@user`, `#12`, backticks, `$…$` | Rendered inert. Exactly one packet marker pair. No link other than Ballast's. | edge case, FR-018 |
| 19 | Event for a removed scenario; scenario with no event; two runs matching one request | `no longer declared`; `not yet requested`; `failed (run-ambiguous)` | FR-010, edge cases |
| 20 | Wait loop: the run completes on the third poll; it never completes | Stops polling at completion. Stops at 120 s of the injected clock with ≤ 12 list reads. Then one checkpoint refresh. | FR-009 |
| 21 | The head commit's `ballast-demo.yml` blob differs from the default branch's, or is absent (404) | `refused (workflow-differs)` with the sync remedy, exit 1, no dispatch call, no event | AC-010 |
| 22 | The matched run's `head_sha` ≠ the event's commit, for a `completed/success` run with an unexpired artifact | `failed (commit-mismatch)` with job link, never a `[video]` link | AC-010, SC-002 |
| 23 | Run list: the match on page 3 (pages 1–2 full); 5 full pages and no match; scenarios' newest events on two dates | Pages are read until the match or a short page. With 5 full pages: `failed (run-list-truncated)`, even within 24 h, and no sixth read. The `created` filter is the older of the two dates, and every list argv has `branch=<feature branch>` | AC-004, plan review F-003 |

## Full local gate

The same suite on a Linux machine with a systemd user session, the Codex CLI and the Spec Kit CLI, so the tests CI skips also run. Record both gates in the PR.

## Post-merge pilot (SC-001, operator)

The live pilot can only run after merge, because the template must be on the project's default branch.

1. In a project with a UI, copy `templates/github/workflows/ballast-demo.yml` from the released Ballast version to `.github/workflows/` on the default branch. Add a `[demo]` scenario and run `ballast trust`.
2. Open a feature run's Draft PR on a branch that carries the same `ballast-demo.yml` (cut after step 1, or synced with the default branch), then run `ballast run demo RUN_ID <scenario>`.
3. Expect, within 120 s or after `ballast run checkpoint RUN_ID`, one demo line on the same PR with a working video link, the head commit, the scenario and the environment. Expect no second PR.
4. Run the line's reproduce command in a clean checkout of that commit and see the same journey (SC-004).

The PR lists this pilot as open post-merge evidence. It is never reported as passed.
