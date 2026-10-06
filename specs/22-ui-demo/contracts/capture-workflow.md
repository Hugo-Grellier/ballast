# Contract: the capture workflow template

The template is the copy-once file `templates/github/workflows/ballast-demo.yml`. A project commits it as `.github/workflows/ballast-demo.yml` on its default branch; feature branches carry the same file. Ballast dispatches it on the **PR's head branch** ref, never the default branch, so the PR-head code the job runs can write only the feature branch's cache scope. Ballast dispatches only when the head commit's copy has the same Git blob ID as the default branch's, and it links a result only when the run's `head_sha` is the requested commit ([research R15](../research.md#r15-execution-scope-of-the-capture-run-plan-review-f-001), FR-007, AC-010).

## Required shape (checked by a static test of the template)

| Property | Value | Requirement |
| --- | --- | --- |
| trigger | `on: workflow_dispatch` only, with string inputs `request`, `scenario`, `commit`, `command`, `video`, `timeout_minutes`, `retention_days` (all required) | FR-004 |
| `run-name` | `Ballast demo ${{ inputs.request }}` | R3 correlation |
| `permissions` | exactly `contents: read` at the workflow level; no job-level override | FR-006, SC-005 |
| jobs | exactly one job | R15 |
| secrets | no `secrets.` expression and no `environment:` anywhere | AC-008 |
| runner | `ubuntu-latest`; the project may edit it | |
| job `timeout-minutes` | the integer literal `65`, no expression (the 60-minute maximum, the 30 s kill grace, checkout and upload). The contract value is enforced by the command step's `timeout`, not by the job | AC-017 backstop, plan review F-002 |
| inputs in shells | only through `env:`; no `${{ ... }}` inside any `run:` script | script injection |
| actions | exactly `actions/checkout` and `actions/upload-artifact`, each pinned to a full 40-hex commit SHA with a version comment; no `actions/cache` and no `cache:` input | dependency policy, R15 |
| checkout | `ref: ${{ inputs.commit }}`, `persist-credentials: false`, `fetch-depth: 1` | AC-008 |

## Steps, in order (names are part of the contract, research R5)

1. **`Validate demo request`**: rejects the run unless all of these hold:
   - `request` matches `^[0-9a-f]{16}$`;
   - `scenario` matches `^[A-Za-z0-9._-]{1,64}$`;
   - `commit` matches `^[0-9a-f]{40}([0-9a-f]{24})?$`;
   - `timeout_minutes` is an integer from 1 to 60;
   - `retention_days` is an integer from 1 to 90;
   - `video` is relative, has no `..` segment and no leading `/`;
   - `command` is non-empty and one line;
   - `GITHUB_SHA` equals `commit` (the branch tip GitHub ran is the requested commit).
2. **Checkout** at `inputs.commit`. The next step then verifies `git rev-parse HEAD` equals `commit`.
3. **`Run demo command`**: runs `timeout --kill-after=30s "${TIMEOUT}m" bash -c "$DEMO_COMMAND"` with `set +e`, and writes `exit=<code>` to `$GITHUB_OUTPUT`. This `timeout` is what enforces the contract's `timeout_minutes` (validated 1–60 in step 1). The step itself always succeeds. Its environment has `DEMO_COMMAND`, `TIMEOUT` (from `inputs.timeout_minutes` through `env:`) and `CI=true`, and no token.
4. **`Demo command timed out`**: runs only when the exit is 124 or 137, and exits 1. A command that itself exits 124 or 137, or is killed by the out-of-memory killer (137), is reported as `timed-out` too; the policy's demo subsection says so (plan review F-004).
5. **`Demo command failed`**: runs only for any other non-zero exit, and exits 1.
6. **`Demo video missing`**: runs only when the exit is 0 and `$VIDEO` is not a regular file inside the workspace (checked with `realpath` against `$GITHUB_WORKSPACE`), and exits 1.
7. **Upload**: `actions/upload-artifact` with `name: ballast-demo-${{ inputs.request }}`, `path: ${{ inputs.video }}`, `retention-days: ${{ inputs.retention_days }}`, `if-no-files-found: error`, `compression-level: 0`.

## GitHub reads that interpret the run (ADR-0013)

| Call | Used for |
| --- | --- |
| `contents/.github/workflows/ballast-demo.yml?ref=<head commit>` and `?ref=<default branch>` | blob `sha` of each copy; dispatch only when equal (before dispatch) |
| `actions/workflows/ballast-demo.yml/runs?event=workflow_dispatch&branch=<feature branch>&created=>=<date>&per_page=100&page=<n>` | match `display_title`; `status`, `conclusion`, `id`, `head_sha`. The date is the oldest of the scenarios' newest events; pages until one has fewer than 100 runs, at most 5 ([research R6](../research.md#r6-outcome-resolution-at-a-checkpoint)) |
| `actions/runs/<id>/jobs?per_page=100` | first failed step's `name` (only for a completed, non-successful run) |
| `actions/runs/<id>/artifacts?name=ballast-demo-<request>` | `id`, `expired` (only for a successful run) |

Ballast never downloads the artifact or the logs.
