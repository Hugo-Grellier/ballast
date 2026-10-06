# Contract: `ballast run demo`

```text
ballast run demo RUN_ID SCENARIO [--no-wait]
```

The command is run by the operator from a terminal. It is a trusted `run.py` subcommand and starts no agent. It holds the run's invocation lock (start, resume, continue, publish, checkpoint and demo exclude each other). Any run mode works, as long as the run has an open Ballast Draft PR.

## Sequence

1. The launcher's existing refusals apply first: an untrusted input, the tamper marker, or an unfinished agent step.
2. Parse `[demo]` ([demo-config.md](demo-config.md)) and find `SCENARIO`.
3. `draft_pr.checkpoint(root, run_id, create=False)`. Continue only on `reused`. That call never creates a PR, and it records its own `pull_request` event and refreshes the packet as `ballast run checkpoint` does.
4. Read the PR for its head commit (`gh api repos/<o>/<r>/pulls/<n>`) and the repository for its default branch (`gh api repos/<o>/<r>`).
5. Read the workflow (`gh api repos/<o>/<r>/actions/workflows/ballast-demo.yml`). It must exist with `state == "active"`.
6. Read the blob `sha` of `.github/workflows/ballast-demo.yml` at the PR head commit and on the default branch (`gh api "repos/<o>/<r>/contents/.github/workflows/ballast-demo.yml?ref=<ref>"`, twice). They must be equal ([research R15](../research.md#r15-execution-scope-of-the-capture-run-plan-review-f-001)).
7. Dispatch: `gh api --method POST repos/<o>/<r>/actions/workflows/ballast-demo.yml/dispatches --input -`, with stdin `{"ref": "<feature branch>", "inputs": {"request": "<16 hex>", "scenario": "<name>", "commit": "<head>", "command": "<command>", "video": "<path>", "timeout_minutes": "<n>", "retention_days": "<n>"}}`. All input values are strings. The `ref` is the branch the run pins, which is the PR's head ref; it is never the default branch.
8. Append the `demo_capture` ledger event ([data-model.md](../data-model.md#ledger-event-demo_capture-runner-only)).
9. Unless `--no-wait`: poll the runs list every 10 s, for at most 120 s, until the matching run is `completed`.
10. `draft_pr.checkpoint(root, run_id, create=False)` again, to refresh the packet.

Every `gh` call goes through `draft_pr._Checkpoint`'s `gh`/`api` seam: resolved program, argument list, hardened environment, empty working directory and 30 s limit. `gh` output is parsed, never printed or stored.

## Output

```text
Demo capture: <state>[ (<reason>)][ <scenario> at <commit12>][: <remedy or link>]
Draft PR: ...
Acceptance packet: ...
```

| State | Reason | Exit | Remedy / detail |
| --- | --- | --- | --- |
| `refused` | `untrusted` | 1 | the launcher's existing remedy |
| `refused` | `lock-held` | 1 | wait for the other invocation of this run |
| `refused` | `not-configured` | 1 | declare `[demo]` with a scenario in `ballast.toml`, then run `ballast trust` |
| `refused` | `config-invalid` | 1 | fix `[demo]` (`<reason>`), then run `ballast trust` |
| `refused` | `unknown-scenario` | 1 | declared scenarios: `<names>` |
| `refused` | `no-draft-pr` | 1 | `ballast run publish RUN_ID` opens it once the run completes |
| `refused` | `pr-not-open` | 1 | the Draft PR line names the cause; a capture needs an open Ballast Draft PR |
| `refused` | `workflow-not-installed` | 1 | copy `templates/github/workflows/ballast-demo.yml` of the pinned Ballast version to `.github/workflows/` on the default branch |
| `refused` | `workflow-disabled` | 1 | enable the `ballast-demo.yml` workflow in the repository's Actions settings |
| `refused` | `workflow-differs` | 1 | the feature branch's `.github/workflows/ballast-demo.yml` is missing or differs from the default branch's; sync the branch with the default branch, then request again |
| `failed-retryable` | `github-unreachable`, `gh-unauthenticated`, `gh-forbidden`, `github-error` | 1 | #17's fixed remedies; `gh-forbidden` names that dispatching needs Actions write access |
| `captured`, `in progress`, `failed`, `missing` | as in the packet | 0 | the job or artifact link |

A refusal or a `failed-retryable` dispatch writes no ledger event and creates no PR. A dispatched request exits 0 whatever the capture's outcome. The capture's outcome is evidence for the reviewer, not a command failure. No output line contains a token: they are fixed strings and validated IDs, and are checked with `packet.TOKEN` in tests (AC-018, SC-006).
