# Data model: One reusable Draft PR

Entities from the spec's Key Entities, with their sources and validation. Decisions are in [research.md](research.md).

## Programs

Resolved first, by the rule of `resolve_program` in `tools/ballast` (research R3): absolute `PATH` entries only; an entry or resolved executable inside any Git working tree is skipped and the search continues. Every later command uses the resolved absolute path.

| Field | Validation | Failure outcome |
| --- | --- | --- |
| `git` | found outside every working tree | `failed-retryable/git-untrusted` ("git not found outside working trees") |
| `gh` | found outside every working tree | absent from every `PATH` entry: `failed-retryable/gh-missing`; found only in a working tree or relative entry: `failed-retryable/gh-untrusted` ("gh not found outside working trees") |

## Feature identity

Resolved once per checkpoint by trusted code; never stored as a whole.

| Field | Source | Validation | Failure outcome |
| --- | --- | --- | --- |
| `feature` | run input `feature_directory`, read on both start and resume from the run's `.specify/workflows/runs/<RUN_ID>/inputs.json` after the launcher's trust check (that file is a protected input: any agent change fails the step as tampering) | `FEATURE_PATTERN` (existing); the spec-directory exclusion prefix is exactly `feature + "/"` | `blocked-unlinked/no-issue-number` |
| `issue` | `feature` | `specs/([1-9][0-9]{0,8})-…` | `blocked-unlinked/no-issue-number` |
| `issue_title` | `gh api repos/{owner}/{repo}/issues/{issue}` | exists, no `pull_request` key; title truncated to 256 characters | `blocked-unlinked/issue-not-found` |
| `run_id` | `run.py` | `RUN_ID_PATTERN` (existing) | n/a (validated before the run) |
| `local_branch` | `<git> symbolic-ref --quiet --short HEAD` | non-empty, does not start with `-` | `pending/no-branch` |
| branch pin | operator state written at `ballast run start` (outside the checkout) | `local_branch` and `published_branch` must both equal the pinned branch; an upstream under another name is refused, since its name comes from agent-writable `.git/config` even at start (DEC-0006, DEC-0010) | `blocked-unlinked/branch-unpinned`, `blocked-unlinked/branch-mismatch` |
| `remote`, `published_branch` | branch upstream (`<git> for-each-ref`) | both present; `refs/heads/` prefix removed | `pending/not-published` |
| `owner`, `repo` | `<git> remote get-url <remote>` | `OWNER/NAME` parsed from a github.com HTTPS, SCP-style or `ssh://` URL; each part `[A-Za-z0-9._-]{1,100}` | `blocked-unlinked/not-github` |
| pinned repository | `[github] repository` in the protected `ballast.toml` | `OWNER/NAME`, each part `[A-Za-z0-9._-]{1,100}`; the upstream must match it case-insensitively, and the pin is what every `gh` call targets (DEC-0005: `.git/config` is agent-writable) | `blocked-unlinked/no-repository`, `blocked-unlinked/repository-mismatch` |
| `base` | `gh api repos/{owner}/{repo}` → `default_branch` | non-empty, differs from `published_branch` | `failed-retryable/<cause>`, or `pending/on-base-branch` |

## Body inputs

Read on every checkpoint that may write a body; all are data, never executed.

| Field | Source | Rule | Failure outcome |
| --- | --- | --- | --- |
| `template` | `gh api "repos/{owner}/{repo}/contents/.github/pull_request_template.md?ref={base}"` → `content`, base64-decoded as UTF-8 | 404 → none (not an error); the checkout's copy is never read | other failure: `failed-retryable/<cause>` |
| `scope` | `gh api --paginate --slurp "repos/{owner}/{repo}/issues/{issue}/comments?per_page=100"` | the newest comment whose body contains `<!-- ballast-intake:` and whose `author_association` is `OWNER`, `MEMBER` or `COLLABORATOR`; its `Main outcome:`, `Risk:` and `Scope gate:` lines, each one line of at most 500 characters, with `<`, `>` and `@` escaped as `&lt;`, `&gt;`, `&#64;`; none → "no intake scope comment" | `failed-retryable/<cause>` |
| `checked_at` | the checkpoint's clock | UTC, ISO 8601 to the second (`2026-10-04T12:34:56Z`) | n/a |

## Feature PR

The single open PR whose head is `published_branch` in `owner/repo` (not cross-repository) and whose base is `base`. Read from `gh api --paginate --slurp "repos/{owner}/{repo}/pulls?head={owner}:{published_branch}&state=all&per_page=100"`, every page.

| Field | Source field | Notes |
| --- | --- | --- |
| `number` | `number` | positive int |
| `url` | `html_url` | must match `https://github.com/{owner}/{repo}/pull/{number}` exactly, otherwise the entry is ignored as foreign |
| `state` | `state`, `merged_at` | `open`, `closed`, or `merged` when `merged_at` is set |
| `draft` | `draft` | read only; never changed |
| `base` | `base.ref` | an open PR whose base differs from `base` is `blocked-ambiguous/base-mismatch`, never reused |
| `head` | `head.ref` | must equal `published_branch` |
| `head_owner` | `head.repo.owner.login` | must equal `owner`; otherwise the entry is a fork and ignored |
| `body` | `body` | read to locate the marked section; only the section is ever rewritten |

### Marked section

Delimited by `<!-- ballast:draft-pr:begin -->` and `<!-- ballast:draft-pr:end -->`. Canonical text in the [checkpoint contract](contracts/pr-checkpoint.md#pr-content). It is built from fixed wording, `issue`, `feature`, `run_id`, `checked_at` and `scope`. On reuse:

| Body state | Action |
| --- | --- |
| one section, equal to canonical text | none |
| one section, different (always the case after a new checkpoint time) | rewrite the text between the markers; every byte outside them is kept |
| no section, Issue already referenced (`#N` as a whole token, or `github.com/{owner}/{repo}/issues/N`) | none |
| no section, Issue not referenced | append the whole marked Ballast section after a blank line (AC-007; DEC-0003) |
| several sections, or unbalanced markers | none; outcome still `reused`, reason `section-unmanaged` |
| any edit above | first re-read the PR; when its body differs from the listed body, no edit and reason `body-changed` (DEC-0007; GitHub offers no conditional update, so a sub-second window remains) |

## PR checkpoint outcome

One per checkpoint. Recorded as a ledger event of kind `pull_request` ([ledger contract](contracts/ledger-pull-request-event.md)) and printed as one line.

| Outcome | Reasons | Recorded fields |
| --- | --- | --- |
| `pending` | `no-branch`, `not-published`, `on-base-branch`, `no-meaningful-change`, `diff-unclassified` | `reason`, `issue` |
| `created` | none | `issue`, `pr_number`, `pr_url` |
| `reused` | none, `section-unmanaged` or `body-changed` | `issue`, `pr_number`, `pr_url`, `reason?` |
| `failed-retryable` | `gh-missing`, `gh-unauthenticated`, `gh-forbidden`, `github-unreachable`, `github-error`, `lock-busy`, `internal-error` | `reason`, `issue?` |
| `failed-retryable` | `gh-untrusted`, `git-untrusted` | `reason`, `issue?` |
| `blocked-ambiguous` | `several-open`, `base-mismatch`, `create-unverified` | `reason`, `issue`, `matches`; `pr_number`/`pr_url` for `base-mismatch` and `create-unverified` |
| `blocked-closed` | `closed`, `merged` (`merged` when any match was merged) | `reason`, `issue`, `matches`, `pr_number`/`pr_url` of the most recent match |
| `blocked-unlinked` | `no-issue-number`, `issue-not-found`, `not-github`, `no-repository`, `repository-mismatch`, `branch-unpinned`, `branch-mismatch` | `reason`, `issue?` |

`gh-untrusted` and `git-untrusted` are reasons of the existing `failed-retryable` state (research, plan-review decisions).

### Transitions

There is no stored state machine: each checkpoint recomputes the outcome from Git and GitHub, so every state is retried on the next invocation. The expected progression is `pending → created → reused → reused …`. `failed-retryable` can occur at any point and resolves on its own. The four `blocked-*` states resolve only after an operator action (install `gh` or `git` outside working trees, close duplicates or fix a PR's base, reopen or open a PR by hand, rename the feature directory). Ballast always creates a Draft and never moves a PR between draft, ready, closed or merged (FR-008).

### Decision order

1. Tamper or in-progress marker → `skipped` (printed only).
2. `issue` from `feature` → `blocked-unlinked/no-issue-number`.
3. `git` resolution → `failed-retryable/git-untrusted`.
4. `local_branch` → `pending/no-branch`.
5. Upstream → `pending/not-published`; `owner`/`repo` → `blocked-unlinked/not-github`; no valid `[github] repository` in `ballast.toml` → `blocked-unlinked/no-repository`; upstream repository differs from it (case-insensitively) → `blocked-unlinked/repository-mismatch` (DEC-0005).
6. `gh` resolution → `failed-retryable/gh-missing`, `failed-retryable/gh-untrusted`.
7. `base` → `failed-retryable`; `pending/on-base-branch`.
8. Issue lookup → `blocked-unlinked/issue-not-found`; Issue comments → `scope`.
9. PR list → `blocked-ambiguous` (`several-open`, `base-mismatch`), `reused` (with the section edit), `blocked-closed`.
10. Compare → `pending/not-published`, `pending/no-meaningful-change`, `pending/diff-unclassified`.
11. Template → body.
12. Under the lock: list again (step 9 rules), `gh pr create --draft`, list again → `created` when base, head and draft match, else `blocked-ambiguous/create-unverified`. A create refused with `already exists` → list again and apply step 9 (normally `reused`).
