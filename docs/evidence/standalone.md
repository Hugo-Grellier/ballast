# Standalone execution qualification — 2026-10-14

Status: **one foreground issue-to-ready-PR scenario qualified**. This record does not claim release
readiness, cross-clone ownership, detached recovery or an implemented queue.

## Authorized scenario

The operator authorized public `Hugo-Grellier/ballast-v2-smoke` with fictional
content and no automatic merge/deletion. From an existing agent conversation:

- [Issue #1](https://github.com/Hugo-Grellier/ballast-v2-smoke/issues/1) asks the
  greeting helper to use `friend` for empty/whitespace names and preserve names.
- Native Git worktree branch `issue-1-6556a0d3` starts from integration head
  `b44a9bb3059636661fa72747f82e624825ce8662`.
- Attempt `6556a0d373a74e46aad35fdc8efbe282` uses local exclusive issue/worker
  claims; no manual human dispatch, Orca or Ballast 1.x execution is used.
- [PR #2](https://github.com/Hugo-Grellier/ballast-v2-smoke/pull/2) submits
  final head `e7de33018502475b64a82a9598dc7ff2d800cb86` and links the issue.

## Explicit executing routes

The coordinator read only its own current session's local `turn_context` model
and effort metadata: `gpt-6.1-sol` / `medium`. It did not scan other conversations
or publish the source's local destination. This is launcher metadata, not a
provider-internal execution claim.

| Worker | Explicit requested = observed | Session evidence before task input |
| --- | --- | --- |
| Implementation `428767e82daf4fa2bae914306abf956e` | OpenAI `gpt-6-luna` / `low` | Codex 0.162.1 `thread/start`, fresh session `01a13a8b-6721-7a63-953d-452f5fc446bb`, workspace-write |
| Final review `cba16f8dbd9a49f695d7baf593284784` | OpenAI `gpt-6-sol` / `medium` | Codex 0.162.1 `thread/start`, separate fresh session `01a13a91-5f36-73c2-92b5-5025afb12957`, read-only |

Both executing sessions validated authorized subscription mode, catalog support,
model/effort, provider, working directory, sandbox, no network/additional write
roots and approval policy before `turn/start`. No API-key or provider fallback.
The implementation differs from its launcher in **both model and effort**.
Receipts establish resolved client configuration, not provider-internal attestation.

Private local records preserve receipt → dispatch → input acceptance → completion
ordering. Raw account identifiers, reasoning/tool streams and local paths are
excluded from this public record. Final worker output remains local.

## Meaningful acceptance and review

- Original code produces `Hello, !` for blank input.
- The implementation worker changed only `greetings.py` and `test_greetings.py`.
  After the operator granted workflow scope, the coordinator added the
  deterministic workflow and invalidated/refreshed final-head review and checks.
- `python3 -m unittest -v` passes all 3 tests on the submitted head.
- Running the new tests against the original helper fails both empty/whitespace
  cases while the ordinary-name case passes. Tests detect the requested behavior.
- `git diff --check` passes; committed checkout is clean.
- The fresh read-only reviewer inspected the exact head/base, independently ran
  `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest -v`, and returned APPROVED with no
  findings. The helper confirms unchanged clean head after review.

## CI and readiness

GitHub initially rejected the push containing `.github/workflows/checks.yml`
because the OAuth app lacked `workflow` scope. The operator granted the scope;
its actual availability was checked before the workflow was published. The
blocked draft state was preserved until new-head review and CI were complete.

[Smoke checks run 38570775803](https://github.com/Hugo-Grellier/ballast-v2-smoke/actions/runs/38570775803)
passed `unit` at head `e7de33018502475b64a82a9598dc7ff2d800cb86`, event
`pull_request`. It runs only deterministic unittest checks, no agents, with
`contents: read`. The PR base remains `b44a9bb3059636661fa72747f82e624825ce8662`;
GitHub's synthetic merge `185408b454a94a41967788e00200127d9263ef50` has exactly
that base and submitted head as parents. No empty/unrelated check list was
accepted as success.

Initial review approved source head `9a3e5bccc5c557e9e5008ab2c651a72629c2721d`.
After adding the workflow, final independent review approved the new head above,
including the deterministic workflow and fresh local checks. A separate live
review also exercised the helper's final nonblocking pipe implementation.
The PR is ready for human review/merge. No merge, release or deletion occurred.

## Deterministic helper evidence and remaining limits

`tests/test_standalone_execution.py` uses real temporary Git repositories and scripted
in-memory app-server output, with no real agent or hosting call. Alongside the
foundation routing tests, it covers local duplicate ownership, checkout identity,
stale base/setup failure, explicit host, account and receipt denial, missing write
scope, notification ordering, unconfirmed completion locks, CI refusal and CLI
explicit-route forwarding. These fixtures do not substitute for live evidence.

The current worker requires POSIX pipes and foreground execution. Failed or
uncertain task delivery retains unknown state and lock; it does not automatically
resume or prove all external effects stopped. Native CLI sandboxing and cooperative
instructions are the boundary, without v1's trusted-launcher/tamper guarantees.

## Source layout correction

The original live scenario preceded the operator's request to develop directly
in the normal repository layout. Its helpers now live at `tools/worktree.py`
and `tools/worker.py`, sharing `tools/codex.py`; deterministic checks now import
those modules directly. Original session/head receipts above remain historical
evidence for that scenario, rather than a claim that renamed commands were
executed before they existed.

After relocation, `python3 -I -S tools/worker.py --help` succeeded, all 24
renamed routing/execution tests passed, and the relocated worker module
established a fresh Codex 0.162.1 workspace-write session with requested equal
to observed `gpt-6-luna` / `low`, correct sandbox and `task_started: false`.
No additional model turn was sent for this metadata recheck.
