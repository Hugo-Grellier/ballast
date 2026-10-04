# Contract: PR checkpoint

Module `tools/spec_workflow/draft_pr.py`, installed as `.ballast/spec_workflow/draft_pr.py`. Standard library only.

## Entry point

```python
def checkpoint(root: Path, run_id: str) -> Outcome
# `feature` is read inside from .specify/workflows/runs/<run_id>/inputs.json
# (validated with FEATURE_PATTERN), so start and resume share one trusted source.
```

- Called by `run.py` once per `start` or `resume` invocation, after `import_run`, whatever the workflow exit status.
- Never raises to `run.py` for a GitHub, Git or ledger failure; `run.py` additionally catches `Exception` and `KeyboardInterrupt` around the call, so the invocation's exit status is never changed (FR-011).
- Writes nothing in the worktree. Writes only the ledger event (through `ledger.append`) and the lock file `<git common dir>/ballast-pr.lock`.
- `Outcome` is a small frozen dataclass: `state`, `reason | None`, `issue | None`, `pr_number | None`, `pr_url | None`, `addresses: tuple[str, ...]`, `remedy | None`.

## Environment boundary

- `run.py` builds the workflow engine's environment from `os.environ` **without** `GH_TOKEN`, `GITHUB_TOKEN`, `GH_ENTERPRISE_TOKEN` and `GITHUB_ENTERPRISE_TOKEN`, so no agent step receives them.
- The checkpoint runs in `run.py`'s own process and passes `os.environ` (tokens included) plus `GH_PROMPT_DISABLED=1`, `GH_NO_UPDATE_NOTIFIER=1`, `GH_PAGER=cat`, `NO_COLOR=1` to its own commands, with these changes (DEC-0004):
  - `PATH` keeps only the absolute entries outside every Git working tree, the checkout included, and outside the agent-writable temp roots `/tmp`, `/var/tmp`, `/dev/shm` and `$TMPDIR` (DEC-0011), because `gh` runs `git` itself; programs are resolved by the same rule;
  - `GIT_DIR`, `GIT_WORK_TREE`, `GIT_COMMON_DIR` and `GIT_INDEX_FILE` are dropped;
  - `GIT_CONFIG_COUNT`/`GIT_CONFIG_KEY_n`/`GIT_CONFIG_VALUE_n` set `core.fsmonitor=false` and `core.hooksPath=/dev/null`, and `GIT_CEILING_DIRECTORIES` is the parent of the working directory.
- Every `gh` call starts in a fresh empty temporary directory, never in the checkout, and names `--repo` (or an `api` path with the repository) explicitly. The checkout's `.git/config` is agent-writable; `gh` must never read it.

## Program resolution

`<git>` and `<gh>` below are absolute paths resolved by the rule of `resolve_program` in `tools/ballast`: absolute `PATH` entries only; skip an entry inside any Git working tree, and a resolved executable inside one; continue with later entries. A bare `git` or `gh` is never executed.

| Result | Outcome |
| --- | --- |
| `git` not found outside working trees | `failed-retryable/git-untrusted`, no command runs |
| `gh` absent from every `PATH` entry | `failed-retryable/gh-missing` |
| `gh` found only in a working tree or relative entry | `failed-retryable/gh-untrusted`, never executed |

## External commands

All run with a list argv, `shell=False`, `cwd=root`, a 30 s timeout and the environment above. Their output is parsed, never printed. Lists read every page.

| Purpose | Command |
| --- | --- |
| Local branch | `<git> symbolic-ref --quiet --short HEAD` |
| Branch pin | written by `run.py` at `ballast run start`, before the engine: `$XDG_STATE_HOME/ballast/<key>/draft-pr/<run>.json` with `branch`; every checkpoint requires the local branch to equal it (`blocked-unlinked/branch-mismatch`) and its published name to equal it (`pending/not-published`); no pin → `blocked-unlinked/branch-unpinned`; all before any `gh` call (DEC-0006, DEC-0010) |
| Upstream | `<git> for-each-ref --format=%(upstream:remotename)%00%(upstream:remoteref) refs/heads/<branch>` |
| Remote URL | `<git> remote get-url <remote>` |
| Repository and base | `<gh> api repos/<owner>/<repo>` |
| Issue | `<gh> api repos/<owner>/<repo>/issues/<issue>` |
| Intake scope comment | `<gh> api --paginate --slurp "repos/<owner>/<repo>/issues/<issue>/comments?per_page=100"` ; selects the newest comment containing `<!-- ballast-intake:` whose `author_association` is `OWNER`, `MEMBER` or `COLLABORATOR` |
| PRs for the head | `<gh> api --paginate --slurp "repos/<owner>/<repo>/pulls?head=<owner>:<published>&state=all&per_page=100"`; fields read: `number`, `state`, `draft`, `merged_at`, `base.ref`, `head.ref`, `head.repo.owner.login`, `html_url`, `body` |
| Diff | `<gh> api repos/<owner>/<repo>/compare/<base>...<published>` (one response: GitHub lists at most 300 files, on the first page only; 300 or more → never concluded, `pending/diff-unclassified`; DEC-0008) |
| Template | `<gh> api "repos/<owner>/<repo>/contents/.github/pull_request_template.md?ref=<base>"`; 404 = no template |
| Create | `<gh> pr create --repo <owner>/<repo> --draft --base <base> --head <published> --title <title> --body-file -` (body on stdin) |
| Verify creation | the PR list command again |
| Re-read before edit | `<gh> api repos/<owner>/<repo>/pulls/<number>`; a body that differs from the listed one → `reused/body-changed`, no edit (DEC-0007) |
| Edit section | `<gh> pr edit <number> --repo <owner>/<repo> --body-file -` (body on stdin) |

Branch names are passed as separate arguments; a name starting with `-` is refused as `pending/no-branch` before any call. Path and query segments interpolated into `gh api` paths are validated (`owner` and `repo` by the pattern in the [data model](../data-model.md)) and branch names are URL-quoted with `urllib.parse.quote(..., safe="")`. `--paginate --slurp` needs `gh` 2.48 or later.

## PR identity rules

- Keep only list entries with `head.ref == <published>`, head owner `== <owner>` and `html_url == https://github.com/<owner>/<repo>/pull/<number>`.
- Two or more open → `blocked-ambiguous/several-open`.
- One open with `base.ref != <base>` → `blocked-ambiguous/base-mismatch`; the printed line names both bases ("PR #N targets X, expected Y"). Never `reused`.
- One open with the resolved base → `reused`.
- None open, one or more closed or merged → `blocked-closed`.
- After `gh pr create`, list again: `created` only when exactly one open PR exists and its base, head and `draft: true` match; otherwise `blocked-ambiguous/create-unverified`.
- `gh pr create` refused with `already exists` (another clone created it): list again and apply these rules, normally `reused`.

## PR content

Created PR:

- **Title**: the Issue title as written, truncated to 256 characters.
- **Body**: the base branch's template (when one exists), a blank line, then the marked section.
- **Draft**: always; the base is `<base>`; no labels, reviewers or assignees.

```text
<!-- ballast:draft-pr:begin -->
## Ballast

Related to #<issue>

- Feature: `<feature>/`
- Run: `<run_id>`
- Last checkpoint: <checked_at, UTC ISO 8601>
- Scope:
  - Main outcome: <escaped line>
  - Risk: <escaped line>
  - Scope gate: <escaped line>
<!-- ballast:draft-pr:end -->
```

A missing scope line is omitted. Without an intake scope comment, the scope item reads `- Scope: no intake scope comment`. Scope text is plain text with `<`, `>` and `@` written as `&lt;`, `&gt;`, `&#64;`; it is never executed or passed to a shell. `Related to` is never a closing keyword (FR-006).

Reused PR: only the text between the markers may change, and only when it differs from the canonical text, by the rules in the [data model](../data-model.md#marked-section). Text outside the markers is never touched. Ballast never passes `--title`, `--base`, `--add-label`, `--add-reviewer`, `--ready` or `--draft` to `gh pr edit`, and never calls `gh pr ready`, `merge`, `close` or `reopen` (FR-007, FR-008).

## Output

One line on stdout after the run summary:

```text
Draft PR: <state>[ (<reason>)][ #<number> <url>][: <remedy>]
```

For `blocked-ambiguous/several-open` and `blocked-closed` the line lists every matching address before the remedy. A `skipped` checkpoint prints `Draft PR: skipped: <marker> exists; restore the checkout`. No `gh` output, environment value or credential is ever printed (FR-013).

## Causes and remedies

| State / reason | Remedy printed |
| --- | --- |
| `pending/no-branch` | check out the feature branch, then resume |
| `pending/not-published` | publish the branch, e.g. `git push -u <remote or origin> <branch>` |
| `pending/on-base-branch` | run the feature on its own branch |
| `pending/no-meaningful-change` | none: a Draft PR opens once implementation changes are pushed |
| `pending/diff-unclassified` | open the PR by hand; Ballast will adopt it |
| `reused/section-unmanaged` | keep one Ballast section in the PR body |
| `reused/body-changed` | none: the PR body changed during the check; the next run refreshes the section |
| `failed-retryable/gh-missing` | install the GitHub CLI; `ballast doctor` checks it |
| `failed-retryable/gh-unauthenticated` | run `gh auth login` |
| `failed-retryable/gh-forbidden` | grant your GitHub account write access to `<owner>/<repo>` |
| `failed-retryable/github-unreachable` | check the network; the next run retries |
| `failed-retryable/github-error` | the next run retries; check GitHub status, or upgrade `gh` to 2.48 or later, if it persists |
| `failed-retryable/lock-busy` | another checkpoint is running; the next run retries |
| `failed-retryable/internal-error` | report it with the run ID; the next run retries |
| `failed-retryable/gh-untrusted` | gh not found outside working trees: install it in a directory outside any Git working tree and put that directory on `PATH` |
| `failed-retryable/git-untrusted` | git not found outside working trees: put a system `git` on `PATH` ahead of any checkout directory |
| `blocked-ambiguous/several-open` | close all but one of the listed PRs |
| `blocked-ambiguous/base-mismatch` | PR #N targets X, expected Y: change its base on GitHub, or close it |
| `blocked-ambiguous/create-unverified` | check the listed PR on GitHub: its base, head or draft state is not what Ballast requested |
| `blocked-closed/closed` or `/merged` | reopen the PR, or open a new one by hand from this branch; Ballast will adopt it |
| `blocked-unlinked/no-issue-number` | name the feature directory `specs/<issue>-<slug>/` |
| `blocked-unlinked/issue-not-found` | create the Issue, or fix the number in the feature directory |
| `blocked-unlinked/not-github` | none: Draft PRs need a GitHub upstream |
| `blocked-unlinked/branch-unpinned` | start a new run with `ballast run start` on the feature branch |
| `blocked-unlinked/branch-mismatch` | check out BRANCH, the branch this run started on, with its upstream, then resume |
| `blocked-unlinked/no-repository` | declare `[github] repository = "OWNER/NAME"` in `ballast.toml`, then run `ballast trust` |
| `blocked-unlinked/repository-mismatch` | the branch's upstream is not OWNER/NAME, the repository pinned in `ballast.toml`: push the branch there, or fix the pin and run `ballast trust` |

## Test seam

`draft_pr` runs every external command through one function, `_command(argv, *, stdin=None, cwd, root=None) -> Result` (`root` is the checkout when `cwd` is not), so tests replace it with a scripted fake that asserts the exact argv sequence (absolute program paths included) and returns canned JSON, exit codes, timeouts and stderr. Program resolution reads `PATH` through a separate function so tests can point it at temporary directories. No test touches the network (FR-014).
