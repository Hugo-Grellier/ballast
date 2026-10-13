# Data model: Autonomous PR completion policy

Entities from [spec.md](spec.md) (Key Entities). Design reasons are in [research.md](research.md).

## Completion policy (part of the run's policy snapshot)

Stored in the run record (operator state), at `eligibility.policy`, beside `risk`, `excluded_boundaries` and `authorized_privileged_actions`. Each field is present only in the cases listed below. A run with no `completion` key, no `completion_max_severity` key and no `--completion` flag has a snapshot identical to today's.

| Field | Values | Present when | Source |
| --- | --- | --- | --- |
| `completion_configured` | `draft`, `ready` | `[autonomous] completion` is set | trusted `ballast.toml` at start, or the `ballast trust` baseline on `--refresh-policy`; an unknown value is stored as `draft`, with a warning |
| `completion_max_severity` | `low`, `info`, `none` | `[autonomous] completion_max_severity` is set | same; an unknown value is stored as `low`, with a warning |
| `completion_flag` | `draft`, `ready` | `--completion` was given at start | the start flag; never changed afterwards, a refresh included |
| `completion` | `draft`, `ready` | either `completion_configured` or `completion_flag` is present | `completion_policy(configured, flag)` |

**Rules**

- `completion_policy(configured, flag)`: `ready` only when `configured == "ready"` and `flag in {None, "ready"}`. Otherwise `draft`. A missing `configured` counts as `draft`.
- Start: `flag == "ready"` and `configured != "ready"` refuses the start before any record is written (FR-003, AC-015).
- `--refresh-policy`: replaces `completion_configured` and `completion_max_severity` from the trusted baseline (removing them when they are no longer set), keeps `completion_flag`, and recomputes `completion` (FR-004, AC-018). The block-resolution entry keeps `previous`/`current` as today.
- Missing `completion_max_severity` means `low`.
- **Reported**: `completion_configured == "ready"` (R4). Only a reported run prints a completion line or writes a `pr_completion` event.

## Publication (in-process only)

Built by `run._publish` from `autonomy.publish`'s result after a successful publication. It is consumed by `_complete` in the same invocation and never persisted (research R1).

| Field | Meaning |
| --- | --- |
| `repo` | `OWNER/NAME` pinned in `[github] repository`, as publication resolved it |
| `pr_number` | the created or adopted PR |
| `url` | its address |
| `commit` | the commit `_commit_and_push` pushed (`git rev-parse HEAD` after the push) |

`autonomy.publish` gains the additive return keys `repo`, `number` and `commit`. Existing keys (`ok`, `category`, `message`, `url`) are unchanged.

## Completion inputs (frozen, collected by the I/O layer)

| Field | From |
| --- | --- |
| `run` | `autonomy.read_run` |
| `decisions` | `autonomy.read_decisions` (hash-chained log) |
| `human` | `autonomy.read_human_decisions` |
| `checks` | `autonomy.read_checks` (`checks.json`) |
| `packet` | `PacketOutcome` from this invocation's checkpoint, or `None` |
| `commit` | the publication's pushed commit |
| `pr` | the PR read back once through the trusted `gh` (`repos/<repo>/pulls/<n>`), or a read-failure cause code |

## Eligibility result

`evaluate(inputs) -> tuple[Reason, ...]`. The tuple is empty when the run is eligible. It is ordered by condition number and holds at most one `Reason` per condition.

`Reason`: `code` (fixed, below) and `text` (fixed wording filled only with validated values).

| # | Code | Printed text (example) |
| --- | --- | --- |
| 1 | `mode` | `the run is in human-gated mode, not autonomous` |
| 2 | `policy-draft` | `the run's start flag chose draft` |
| 3 | `risk` | `risk R2`, or `R2 boundaries declared` at R0 or R1 (security review SEC-001) |
| 4 | `privileged-action` | `privileged actions declared: external-write, other` (kinds via `autonomy.action_kind`) |
| 5 | `no-final-acceptance` | `no final acceptance recorded` |
| 6 | `not-converged` | `spec reconciliation is not recorded as approved and converged` |
| 7 | `open-finding` | `2 open findings above the low threshold, highest medium` |
| 8 | `checks` | `run-checks did not pass on the published tree` (or `run-checks not run`) |
| 9 | `packet` | `acceptance packet not published` (also when the checkpoint skipped or failed), `acceptance packet failed-retryable (too-large)`, `acceptance packet head is not the published commit`, or `criteria not all verified: 1 failed, 2 not run, 0 stale, 1 missing` |
| 10 | `material-change` | `material provisional change PD-0003` |
| 11 | `block-resolved` | `a block was resolved during the run (HD-0001)` |
| 12 | `head-moved` | `the PR head is not the published commit`; `pr-changed`: `PR #7 is not an open draft from the run's branch`; `pr-unreadable`: `the PR could not be read back (github-unreachable)` |

Outcome-only codes (after a fully eligible evaluation):

| Code | Printed text |
| --- | --- |
| `forge-failed` | `marking ready failed (gh-forbidden)`; the cause is a Draft PR `failed-retryable` code. After a failed call, only when the read-back still shows the run's Draft at the published commit |
| `forge-unverified` | `the forge did not report the PR ready at the published commit`; the outcome is `unverified`, never `draft` (plan-review F-001). Also after a failed, timed-out or interrupted `gh pr ready` whose read-back is not the Draft at the published commit, or fails |
| `internal-error` | `completion check failed (<ExceptionName>)` |

Condition (2) can only fail on a reported run when the flag narrowed it, so its one text names the flag.

## Completion outcome

Printed as one line (contract: [contracts/output-and-ledger.md](contracts/output-and-ledger.md)) and recorded as one runner-only ledger event.

| Field | Type | Rule |
| --- | --- | --- |
| `outcome` | label, `ready`, `draft` or `unverified` | `ready` only after a verified `gh pr ready`; `unverified` when `gh pr ready` succeeded but the read-back did not show the PR ready at the published commit |
| `pr_number` | int | required |
| `commit` | oid | the published commit; required |
| `reasons?` | labels (1–16 unique codes from the tables above, in condition order) | required for `draft` and `unverified` (exactly `["forge-unverified"]` for `unverified`), forbidden for `ready` |
| `cause?` | label from `ledger.PR_REASONS["failed-retryable"]` | only with reason `forge-failed` or `pr-unreadable` |

**State transitions**: none on the run. The run's status (`published`), exit status and step state are those publication set, whatever the outcome (FR-011). The PR goes Draft → ready for review at most once, and only in this step.
