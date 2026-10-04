# Quickstart: validating the Draft PR checkpoint

How to prove the feature works. Behavior details are in the [checkpoint contract](contracts/pr-checkpoint.md) and the [data model](data-model.md).

## Prerequisites

- Fast gate tools: `uv`, Python 3.13 (see `CLAUDE.md`).
- Live check only: an authenticated `gh` 2.48 or later installed outside any Git working tree, and a disposable GitHub repository you can push to, with an open Issue carrying an intake scope comment (`<!-- ballast-intake:` marker) and a `.github/pull_request_template.md` on the default branch.

## 1. Deterministic tests (no network)

```bash
uvx ruff check && uvx ruff format --check
uv run --no-project --python 3.13 --with pyyaml python -m unittest tests/test_draft_pr.py tests/test_spec_workflow.py tests/test_agent_run_ledger.py
```

`tests/test_draft_pr.py` drives `draft_pr.checkpoint` against a real temporary Git repository (branch, upstream configuration, remote URL) and a scripted fake for `_command` that serves `gh` responses, including multi-page `--paginate --slurp` lists. Program resolution runs against temporary `PATH` directories. Expected: every scenario below passes.

| Scenario (FR-014 situation) | Expected outcome | Covers |
| --- | --- | --- |
| No PR, implementation file outside `specs/<feature>/` in the diff | `created`; `gh pr create` got `--draft`, the base, the head, the Issue title and a body whose marked section holds `Related to #N`, the feature path, the run ID and a UTC ISO 8601 checkpoint time, and no closing keyword | AC-001, AC-002, FR-016 |
| Base-branch template present (contents API returns base64) | body is the decoded template, a blank line, then the marked section; a different `.github/pull_request_template.md` in the checkout is never read | FR-016 |
| Template contents API returns 404 | body is the marked section only; outcome `created` | FR-016 |
| Template contents API returns HTTP 502 | `failed-retryable/github-error`, no create | FR-016, AC-010 |
| Intake comment with `<!-- ballast-intake:` and the three lines | the section lists `Main outcome:`, `Risk:` and `Scope gate:` as written | FR-016 |
| No intake comment; a comment with the lines but no marker | the section reads `Scope: no intake scope comment` | FR-016 |
| Several intake comments, the newest on the second page | the newest one from an OWNER, MEMBER or COLLABORATOR is used | FR-016 |
| Newest marker comment authored by a CONTRIBUTOR or NONE | ignored; an older member comment is used, or "no intake scope comment" | FR-016 |
| Published diff touches only `specs/17-draft-pr/spec.md` | `pending/no-meaningful-change`; no PR (exact prefix `specs/17-draft-pr/`) | AC-005 |
| Resume with only `RUN_ID` (no `-i feature_directory`) | the checkpoint reads the feature from the run's `inputs.json` and reuses the same PR | AC-006 |
| Intake lines containing `@org/team`, `<!-- ballast:draft-pr:end -->` and `<script>` | written as `&#64;org/team`, `&lt;!-- …--&gt;`, `&lt;script&gt;`; the body still has exactly one begin and one end marker | FR-016, edge case |
| Branch without upstream; compare returns 404 | `pending/not-published`, no create call | AC-003 |
| Empty `files` in the compare | `pending/no-meaningful-change` | AC-003, AC-004 |
| Only `specs/<feature>/` files in the compare | `pending/no-meaningful-change` | AC-005 |
| 300 spec-only files | `pending/diff-unclassified` | FR-003 |
| Existing Ballast Draft PR whose section equals the canonical text (fixed clock) | `reused`, no edit call | AC-006 |
| Existing Ballast PR with a section from another run or an older checkpoint time | `reused`, one edit; every byte outside the markers (template text, human text before and after) is identical | AC-006, FR-007 |
| Hand-opened PR without section or Issue reference | `reused`, the body edit appends the section and keeps every other byte | AC-007 |
| Hand-opened PR already referencing `#N` | `reused`, no edit | AC-007 |
| Ready PR (`draft: false`) | `reused`; no `--draft`, `ready` or title argument in any call | AC-008 |
| One open PR with base `release` while the default branch is `main` | `blocked-ambiguous/base-mismatch`; the line says `PR #N targets release, expected main`; no create or edit | identity |
| Closed PR only on the second page of the list | `blocked-closed`, no create | AC-012 |
| Two open PRs for the head | `blocked-ambiguous`, both addresses printed, no create or edit | AC-011 |
| Only a closed / merged PR | `blocked-closed` / reason `merged`, no create, edit or reopen | AC-012 |
| Cross-repository PR with the same head name | ignored, then `created` | edge case |
| `gh` not on `PATH` | `failed-retryable/gh-missing` | AC-010 |
| A checkout-local `gh` (writing a sentinel file when run) is first on `PATH`, a trusted `gh` later | the trusted absolute path is in every `gh` argv; the sentinel is never written | FR-001, BL-INV-002 |
| Only a checkout-local `gh` (and a relative `PATH` entry) | `failed-retryable/gh-untrusted`, line says `gh not found outside working trees`; sentinel never written, no command run | FR-001 |
| Only a checkout-local `git` | `failed-retryable/git-untrusted`; sentinel never written | FR-001 |
| `gh` exit 4 / HTTP 401 / HTTP 403 / timeout / HTTP 502 | `gh-unauthenticated` / `gh-unauthenticated` / `gh-forbidden` / `github-unreachable` / `github-error` | AC-010 |
| Default branch lookup fails | `failed-retryable`, no create | edge case |
| Feature `specs/draft-pr`; Issue 404; Issue is a PR; GitLab remote | `blocked-unlinked` with `no-issue-number` / `issue-not-found` / `issue-not-found` / `not-github` | AC-013 |
| Two threads checkpoint the same feature against one shared fake GitHub | exactly one create call; the other returns `reused` | AC-009 |
| Another clone created the PR first: fake `gh pr create` exits 1 with `a pull request for branch "x" into branch "main" already exists`, the next list returns that PR | `reused` with the section edit, not an error | AC-009, FR-009 |
| List after create returns the new PR with `draft: false` or another base | `blocked-ambiguous/create-unverified`, never `created` | BL-INV-005 |
| Lock held by another process for longer than the wait | `failed-retryable/lock-busy` | FR-009 |
| Fake `gh` stderr and JSON containing `ghp_` / `gho_` tokens and an `Authorization:` header, across every outcome | none of them appears in stdout, stderr or the ledger file | AC-014 |
| Tamper marker present | `skipped`, no command run, no ledger event | FR-001 |
| Hostile issue title, branch name `--help`, feature path with shell metacharacters | argv passed verbatim with no shell; `--help` refused before any call | edge case |

In `tests/test_spec_workflow.py` (existing `run.py` harness):

| Scenario | Expected | Covers |
| --- | --- | --- |
| Workflow exits 0, 1 and 130 with a checkpoint that raises | exit status unchanged, `Draft PR: failed-retryable (internal-error)` printed | FR-002, FR-011 |
| Operator environment sets `GH_TOKEN`, `GITHUB_TOKEN`, `GH_ENTERPRISE_TOKEN` and `GITHUB_ENTERPRISE_TOKEN`; a fake `specify` dumps the environment it and its agent step receive | none of the four variables is in the dump, while the checkpoint's `_command` receives all four | BL-INV-003, SC-005 |
| Checkpoint called after `import_run` for start and resume | called once with the run ID and feature | FR-002 |
| `claude-settings.json` still denies `git push*` and `gh *` | unchanged | SC-005 |

In `tests/test_agent_run_ledger.py`:

| Scenario | Expected | Covers |
| --- | --- | --- |
| Valid `pull_request` events for every outcome, `failed-retryable` included | accepted | FR-010 |
| Unknown outcome or reason, missing `pr_url` on `created`, missing `reason` on `pending`, non-GitHub `pr_url`, free-text field | rejected | FR-010, FR-013 |
| `report` after two checkpoints | shows the latest outcome | AC-002 |

## 2. Live check in a disposable repository (operator, before merge)

From a scratch project that pins this branch's commit, declares `[github] repository = "OWNER/NAME"` in `ballast.toml` (then `ballast trust`), and has Issue `#N`:

1. `ballast run start -i idea="Issue #N: …" -i feature_directory=specs/N-demo` on a feature branch with no upstream, and stop at the first gate. Expect `Draft PR: pending (not-published)`.
2. Push a commit touching only `specs/N-demo/`, then `ballast run resume RUN_ID`. Expect `pending (no-meaningful-change)`.
3. Push a commit changing a file outside `specs/`, resume. Expect `Draft PR: created #P https://github.com/…/pull/P`; on GitHub the PR is a draft, targets the default branch, starts with the default branch's pull-request template, and its Ballast section links the Issue without a closing keyword and shows the intake scope lines, the run ID and the checkpoint time.
4. Add a line of your own outside the Ballast section, mark the PR ready for review on GitHub, resume with `-i integration=codex`. Expect `reused #P`; the PR is still ready, its title and your line are unchanged, and only the section's checkpoint time moved.
5. `gh auth logout`, resume. Expect `failed-retryable (gh-unauthenticated): run gh auth login` and the workflow's usual exit status. Log in again and resume: `reused #P`.
6. `ballast ledger report --run RUN_ID` shows `pull_request` with the latest outcome.
7. `git remote set-url origin https://github.com/OTHER/NAME`, resume. Expect `blocked-unlinked (repository-mismatch)` and no change on GitHub; restore the URL.

Record the commands and results in the PR description, with any step you could not run.
