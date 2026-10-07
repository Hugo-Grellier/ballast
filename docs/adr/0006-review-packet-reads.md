# ADR-0006: Review packet reads under the launcher's GitHub authority

- Status: accepted (2026-10-07, by the operator for the 1.0 release, after its PR merged). Previously: proposed (2026-10-05, with the plan of [feature 19](../../specs/19-acceptance-packet/plan.md#architecture-boundaries); agent-provisional in Autonomous run `97858712`, accepted only when the operator merges the feature PR)
- Feature: [19-acceptance-packet](../../specs/19-acceptance-packet/spec.md), FR-001, FR-002, FR-008, FR-012; research [R1](../../specs/19-acceptance-packet/research.md#r1-where-the-packet-is-built-and-published), [R8](../../specs/19-acceptance-packet/research.md#r8-ci-results), [R10](../../specs/19-acceptance-packet/research.md#r10-openapi-comparison-fr-010-fr-012), [R18](../../specs/19-acceptance-packet/research.md#r18-risk-recheck-against-the-r2-boundaries)
- Extends: [ADR-0003](0003-launcher-github-authority.md), whose fixed command allowlist says a later feature extends it by a new ADR

## Context

The Draft PR checkpoint (#17) is the only place Ballast uses GitHub authority. Feature 19 adds an acceptance packet to the same Draft PR: a derived summary of each acceptance criterion's evidence, the run's decisions, findings and checks, and links to the canonical sources at the PR's head commit. Building it needs reads ADR-0003 does not list: the PR's head and base commits, the check runs of the head commit, an optional OpenAPI document at two commits, and the feature artifacts at the head commit from the local object store. Publishing it needs a second Ballast-marked section in the PR body.

## Decision

- The packet is built by the trusted module `packet.py`, imported with `draft_pr.py` at `run.py` startup, and runs only inside the #17 checkpoint, after its outcome is recorded and only when that outcome is `created` or `reused`. It uses the checkpoint's resolved `git` and `gh`, its hardened environment and its `_command` seam, except for the implementation fingerprint, which needs a private `GIT_INDEX_FILE` that `_command` removes: `ledger.commit_tree` runs Git resolved outside every working tree, with filter drivers, hooks (including `post-index-change`) and fsmonitor disabled.
- The allowlist gains these read calls:
  - `gh api repos/<o>/<r>/pulls/<n>` (already used for the re-read), for the head and base commits;
  - `gh api --paginate --slurp repos/<o>/<r>/commits/<head>/check-runs?per_page=100`;
  - `gh api repos/<o>/<r>/contents/<path>?ref=<commit>` for the one OpenAPI path configured in the protected `ballast.toml`, at the base and head commits;
  - `git cat-file -e`, `git cat-file blob`, `git ls-tree -r -z --name-only` and `git rev-parse --verify` on commit object IDs, with `--` before every path;
  - `git read-tree`, `git rm --cached` and `git write-tree` on a private temporary index (`GIT_INDEX_FILE`), to fingerprint a commit's implementation tree without touching the worktree or the user's index.
- `gh pr edit <n> --repo <o>/<r> --body-file -` may also rewrite a second marked section, `<!-- ballast:acceptance-packet:begin -->` to `<!-- ballast:acceptance-packet:end -->`, under the same rule as the #17 section: re-read the PR just before writing, write only when the body is unchanged, and leave every byte outside the section as it was.
- Every link in the packet is built by Ballast from validated parts. Text from agent-writable sources is rendered inert. `gh` output is parsed, never printed or stored.

## What it does not add

- No new program: the same resolved `git` and `gh`.
- No fetch, push or commit; nothing is downloaded or executed.
- No GitHub write other than the PR body; no title, base, label, reviewer, draft or ready change.
- No agent authority: agents keep every denial, and the packet's configuration lives in the protected `ballast.toml`.

## Consequences

- The PR shows each criterion's evidence state at the head commit, and a packet failure never changes the #17 outcome or the run's exit status.
- The packet reads the head commit from the local object store; a head commit missing locally is `pending/head-not-local` until the operator fetches the branch.
- A further GitHub call needs another ADR.

## Rejected alternatives

- Reading the base commit's OpenAPI document from local Git: the base commit may be absent locally, and Ballast never fetches.
- Running an OpenAPI diff tool: a download or dependency, which is R2 under FR-012.
- Running the manifest's mapped tests from `run-checks` to get a check run per criterion: a new command path, left for a follow-up.
