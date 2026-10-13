# Contract: completion output and ledger event

## When it appears

Only for an Autonomous run whose snapshot has `completion_configured = "ready"`, and only in the invocation that published (even when that invocation's Draft PR checkpoint skipped or failed: the outcome is then a Draft with `packet`, `acceptance packet not published`): `ballast run start`, `ballast run resume`, or a `ballast run publish` retry. In every other case, `ballast run checkpoint`, Chat and human-gated runs included, nothing below is printed or recorded (FR-007, FR-013, FR-014).

## Line order on a reported publication

```text
Draft PR: https://github.com/OWNER/NAME/pull/7
Every intermediate decision is agent-provisional; merging the PR is the only human approval.
Draft PR: reused #7 https://github.com/OWNER/NAME/pull/7
Acceptance packet: published #7 head 0123456789ab
PR completion: ready-for-review #7 https://github.com/OWNER/NAME/pull/7; merging stays the only human approval
```

A `ballast run publish` retry prints the same lines. It runs the checkpoint and packet only on a reported run (research R2).

## Line grammar

```text
PR completion: ready-for-review #<n> <url>; merging stays the only human approval
PR completion: draft #<n> <url>: <reason>[; <reason>]...
PR completion: unverified #<n> <url>: the forge did not report the PR ready at the published commit
```

- `unverified` is printed only when `gh pr ready` succeeded and the verification read-back did not show `draft: false` at the published commit (the head race of research R8). The line never says the PR is a Draft, because it may not be.

- Reasons are in condition order (FR-005, AC-006), with the fixed wording listed in [data-model.md](../data-model.md#eligibility-result).
- No `gh` output, token, agent-written text or file content is printed.
- No wording presents marking ready as an approval. The text passes `autonomy.HUMAN_APPROVAL`, and a test asserts this (FR-017).
- An exception or interrupt inside the step before `gh pr ready` is issued prints `PR completion: draft #<n> <url>: completion check failed (<ExceptionName>)`. If `<n>` is unknown, the number and URL are left out. After the request is issued, an exception or interrupt is `unverified`, never a Draft.

## Exit status and run state

Unchanged by the step in every case, a forge failure included. The exit status is the publication's (0), the run status stays `published`, and no block is written (FR-011, AC-008).

## Ledger event `pr_completion`

Source `runner`. It is in `RUNNER_ONLY`, so `ballast ledger record` refuses it. One event per reported evaluation.

```json
{"kind": "pr_completion", "source": "runner",
 "data": {"outcome": "draft", "pr_number": 7,
          "commit": "0123456789abcdef0123456789abcdef01234567",
          "reasons": ["risk", "packet"]}}
```

```json
{"kind": "pr_completion", "source": "runner",
 "data": {"outcome": "ready", "pr_number": 7,
          "commit": "0123456789abcdef0123456789abcdef01234567"}}
```

Validation (`ledger.validate`):

- `outcome` ∈ {`ready`, `draft`, `unverified`}. `pr_number` int. `commit` oid.
- `reasons` (new value type `labels`: a list of 1–16 unique labels) is required with `draft` and `unverified` and forbidden with `ready`. With `unverified` it is exactly `["forge-unverified"]`, and `cause` is absent. Each element ∈ `COMPLETION_REASONS`.
- `cause` ∈ `PR_REASONS["failed-retryable"]`, allowed only when `reasons` contains `forge-failed` or `pr-unreadable`.
- Source must be `runner`.

`ballast ledger report --run RUN_ID` shows the latest `pr_completion` beside the latest `pull_request` and `acceptance_packet`. `tools/spec_workflow/ledger-schema.md` documents the kind and the `labels` type.

## Forge calls

On a fully eligible evaluation, in order, all through the trusted `gh` (resolved outside working trees, run from an empty directory, `--repo` always explicit):

1. `gh api repos/<repo>/pulls/<n>`: the read-back for condition (12). It is made on every reported evaluation, so a failed condition (12) is listed with the others.
2. `gh pr ready <n> --repo <repo>`: only when (1)–(12) all hold.
3. `gh api repos/<repo>/pulls/<n>`: the post-ready verification (`draft` is `false`, head unchanged). It is also made after a failed or timed-out call 2, which GitHub may still have applied: ready at the published commit is `ready`; the run's Draft still at that commit is `draft` with `forge-failed` and its cause; anything else, a failed read included, is `unverified`.

On an ineligible run only call 1 is made. The forge is never asked to mark the PR ready (AC-004, AC-005).
