---

description: "Task list for One reusable Draft PR for issue-linked feature work"
---

# Tasks: One reusable Draft PR for issue-linked feature work

**Input**: Design documents from `specs/17-draft-pr/`: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/pr-checkpoint.md](contracts/pr-checkpoint.md), [contracts/ledger-pull-request-event.md](contracts/ledger-pull-request-event.md), [quickstart.md](quickstart.md)

**Prerequisites**: plan.md (R2, needs explicit human approval), spec.md, research.md, data-model.md, contracts/

**Acceptance evidence**: Each acceptance criterion `AC-001`–`AC-014` has at least one deterministic test task below (see [AC traceability](#acceptance-criteria-traceability)). The live GitHub check (T038) adds manual evidence, because a real pull request cannot be created offline; it does not replace any test.

**Organization**: Tasks are grouped by user story. US1 and US2 are both P1; US3 is P2.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel: a different file from every other task in the same wave, and no unfinished dependency
- **[Story]**: US1, US2, US3 from spec.md
- Test tasks cite the acceptance criteria (`AC-NNN`), functional requirements (`FR-NNN`) or invariants they prove
- Tests are written first and must fail before the implementation task that depends on them

## Conventions used by every task

- The module is `tools/spec_workflow/draft_pr.py`: standard library only, runs under `python3 -I`, imports `FEATURE_PATTERN` and `RUN_ID_PATTERN` from `artifacts` and `ledger` the same way `run.py` does (its directory is already on `sys.path`). It must not import `tools/ballast`; it reimplements the `resolve_program` / `in_working_tree` rule (see `tools/ballast` lines 168–172 and 321–344).
- Every external command goes through `draft_pr._command(argv, *, stdin=None) -> Result`; `PATH` is read through `draft_pr._path_entries()`; the clock through `draft_pr._now()`. These three are the only test seams (contract § Test seam).
- In `tests/test_draft_pr.py`, the fake `_command` forwards argv whose program is the resolved `git` to the real `git` in the temporary repository, and serves argv whose program is the resolved `gh` from a script. It records every argv, asserts absolute program paths, and is thread-safe.
- Outcome names, reasons, remedies and output wording are copied verbatim from [contracts/pr-checkpoint.md](contracts/pr-checkpoint.md) and [data-model.md](data-model.md); do not paraphrase.
- Run tests with `uv run --no-project --python 3.13 --with pyyaml python -m unittest tests/test_draft_pr.py tests/test_spec_workflow.py tests/test_agent_run_ledger.py`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Record the architecture decision, fix one artifact inconsistency, and create the module and test skeletons.

- [x] T001 [P] Draft ADR-0003 "Launcher-side GitHub authority" in `docs/adr/0003-launcher-github-authority.md` with status `Proposed`: the trusted `run.py` may call the operator's `gh` after a run, resolved outside every Git working tree, with the fixed command allowlist of plan.md § Proposed architecture decisions; agents stay denied and receive none of `GH_TOKEN`, `GITHUB_TOKEN`, `GH_ENTERPRISE_TOKEN`, `GITHUB_ENTERPRISE_TOKEN`; the checkpoint refuses to act while `BALLAST_TAMPERED` or the `in-progress` marker exists. Mark it as needing human approval; do not set it to `Accepted`.
- [x] T002 [P] In `specs/17-draft-pr/plan.md` § Architecture Boundaries, change the data flow `draft_pr.checkpoint(root, run_id, feature)` to `draft_pr.checkpoint(root, run_id)` (feature read from the run's `inputs.json`), matching [contracts/pr-checkpoint.md](contracts/pr-checkpoint.md) § Entry point. Wording fix only.
- [x] T003 Create `tools/spec_workflow/draft_pr.py` skeleton: module docstring stating the trust boundary; constants `MARK_BEGIN = "<!-- ballast:draft-pr:begin -->"`, `MARK_END = "<!-- ballast:draft-pr:end -->"`, `INTAKE_MARK = "<!-- ballast-intake:"`, `TOKEN_VARIABLES` (the four GitHub token names, also used by `run.py`), `GH_ENV = {"GH_PROMPT_DISABLED": "1", "GH_NO_UPDATE_NOTIFIER": "1", "GH_PAGER": "cat", "NO_COLOR": "1"}`, `TIMEOUT = 30`, `LOCK_WAIT = 60`, a `REASONS` mapping outcome → allowed reasons and a `REMEDIES` mapping `(outcome, reason)` → remedy text from the contract table; frozen dataclass `Outcome(state, reason, issue, pr_number, pr_url, addresses: tuple[str, ...], remedy)`; `Result` (returncode, stdout, stderr, timed_out); `_command` running a list argv with `shell=False`, `cwd=root`, `timeout=TIMEOUT`, env `{**os.environ, **GH_ENV}`, mapping `TimeoutExpired` to `timed_out=True`; `_path_entries()` returning `os.environ["PATH"]` split on `os.pathsep`; `_now()` returning UTC `datetime`; `checkpoint(root: Path, run_id: str) -> Outcome` raising `NotImplementedError`.
- [x] T004 Create the harness in `tests/test_draft_pr.py` (depends on T003): a `TempRepo` helper (git init with `main` and a feature branch `feat-x`, remote `origin` = `https://github.com/o/r.git`, upstream set through `git config branch.feat-x.remote/merge` without pushing, `.specify/workflows/runs/<RUN>/inputs.json` holding `feature_directory=specs/17-draft-pr`); a `FakeGitHub` that patches `draft_pr._command` as described in Conventions, answers `--paginate --slurp` calls with a JSON array of pages, can raise per-call failures (exit code, `HTTP NNN` stderr, timeout) and records all argv; helpers to build trusted and checkout-local `bin/` directories (a checkout-local fake writes a sentinel file when run) and patch `draft_pr._path_entries`; a fixed `_now`; canned JSON builders for repository, Issue, comments, pulls, compare and contents responses. Add a single smoke test that imports the module.

**Checkpoint**: module and harness importable; `uvx ruff check` passes.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Ledger event kind, trusted program resolution, the trust re-check, identity resolution, error classification, outcome output and recording, and the `run.py` integration. Every user story needs all of them.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [x] T005 [P] Write ledger validation tests in `tests/test_agent_run_ledger.py`: a valid `pull_request` event (source `runner`) is accepted for every outcome, `failed-retryable` included, with each reason of the data model; rejected: unknown outcome, unknown reason, `created` or `reused` without `pr_number` or `pr_url`, `pending` without `reason`, a non-GitHub or non-`/pull/N` `pr_url`, any extra free-text field; `ledger.py record` does not offer `pull_request` as a kind; a `pull_request` event may follow any other event of the run (no transition rule). [FR-010, FR-013]
- [x] T006 Implement the `pull_request` kind in `tools/spec_workflow/ledger.py` (depends on T005): `FIELDS["pull_request"] = {"outcome": "label", "reason?": "label", "issue?": "int", "pr_number?": "int", "pr_url?": "url", "matches?": "int"}`; `ENUM_FIELDS["pull_request"]` with the seven outcomes and the union of reasons; a new `url` value type in `_valid_value` with pattern `https://github\.com/[A-Za-z0-9._-]{1,100}/[A-Za-z0-9._-]{1,100}/pull/[1-9][0-9]{0,9}`; in `validate`, `created`/`reused` require `pr_number` and `pr_url` and every other outcome requires `reason`; reasons checked against the outcome's allowed set; add `"pull_request"` to the set excluded from the `record` subcommand's choices. `schema_version` stays 1.
- [x] T007 [P] Document the `pull_request` kind in `tools/spec_workflow/ledger-schema.md` (depends on T006): fields, types, per-outcome requirements, the `url` type, the report entry, and the compatibility note (additive; an older pinned Ballast rejects streams containing it).
- [x] T008 Write program-resolution and trust tests in `tests/test_draft_pr.py` (depends on T004): a checkout-local `gh` first on `PATH` and a trusted `gh` later → every `gh` argv starts with the trusted absolute path and the sentinel is never written [FR-001, BL-INV-002]; only a checkout-local `gh` plus a relative `PATH` entry → `failed-retryable/gh-untrusted`, line contains `gh not found outside working trees`, sentinel unwritten, no `gh` command run [FR-001]; `gh` absent from every entry → `failed-retryable/gh-missing` with the remedy `install the GitHub CLI; ballast doctor checks it` [AC-010]; only a checkout-local `git` → `failed-retryable/git-untrusted`, sentinel unwritten [FR-001]; `BALLAST_TAMPERED` present, and separately the `in-progress` marker present → outcome `skipped`, printed `Draft PR: skipped: <marker> exists; restore the checkout`, no command run, no ledger event [FR-001].
- [x] T009 Implement trusted resolution and the trust re-check in `tools/spec_workflow/draft_pr.py` (depends on T003, T008): `_in_working_tree(path)` and `_resolve(name) -> tuple[str | None, bool]` (path, shadowed-only) by the `resolve_program` rule over `_path_entries()`; `_trusted_programs()` mapping results to `git-untrusted`, `gh-missing`, `gh-untrusted`; `_untrusted_marker(root)` returning the marker name when `root / "BALLAST_TAMPERED"` exists (`os.path.lexists`) or the `in-progress` file exists at the path `agent.py` writes (`state_dir(root) / IN_PROGRESS`; compute the same path without importing `agent.py`). Resolution order follows data-model § Decision order steps 1, 3 and 6.
- [x] T010 Write identity-resolution tests in `tests/test_draft_pr.py` (depends on T004): feature `specs/draft-pr` → `blocked-unlinked/no-issue-number` [AC-013]; feature with shell metacharacters fails `FEATURE_PATTERN` → `blocked-unlinked/no-issue-number`, no command run; detached HEAD → `pending/no-branch`; a branch named `--help` → `pending/no-branch` before any `gh` call; no upstream → `pending/not-published`, no `gh pr create` [AC-003]; upstream `refs/heads/other-name` → the published name `other-name` is used in every later argv; GitLab remote → `blocked-unlinked/not-github` [AC-013]; HTTPS, SCP-style and `ssh://` github.com URLs parse to `o/r`; repository lookup failure → `failed-retryable`, no create (edge case: no guessed base); default branch equal to the published branch → `pending/on-base-branch`; Issue 404, and Issue carrying `pull_request` → `blocked-unlinked/issue-not-found` [AC-013, FR-012]; resume with only `RUN_ID` (no `-i feature_directory`) reads the feature from `inputs.json` [AC-006].
- [x] T011 Implement identity resolution and error classification in `tools/spec_workflow/draft_pr.py` (depends on T009, T010): read `feature_directory` from `.specify/workflows/runs/<run_id>/inputs.json` and validate with `FEATURE_PATTERN`; Issue number with `specs/([1-9][0-9]{0,8})-`; local branch with `<git> symbolic-ref --quiet --short HEAD` (refuse empty or `-`-prefixed); upstream with `<git> for-each-ref --format=%(upstream:remotename)%00%(upstream:remoteref) refs/heads/<branch>`; remote URL with `<git> remote get-url <remote>` parsed by the three github.com forms, `owner` and `repo` matched against `[A-Za-z0-9._-]{1,100}`; `default_branch` from `<gh> api repos/<owner>/<repo>`; Issue from `<gh> api repos/<owner>/<repo>/issues/<n>`; `_classify(result) -> reason` per research R4 (exit 4 or `HTTP 401` → `gh-unauthenticated`; `HTTP 403`, or `HTTP 404` on the repository → `gh-forbidden`; timeout or no HTTP status → `github-unreachable`; other status → `github-error`), never keeping `gh` stdout or stderr beyond parsing. Branch names in `gh api` paths are quoted with `urllib.parse.quote(..., safe="")`.
- [x] T012 Implement output and recording in `tools/spec_workflow/draft_pr.py` (depends on T006, T011): `format_line(outcome) -> str` producing `Draft PR: <state>[ (<reason>)][ #<number> <url>][: <remedy>]`, listing every address for `blocked-ambiguous/several-open` and `blocked-closed`; `_record(root, run_id, feature, outcome)` appending a `pull_request` event (source `runner`) through `ledger.new_event` and `ledger.append`, with only the fields of the data-model outcome table; `checkpoint` wraps its body so any exception becomes `failed-retryable/internal-error` (printed with the exception type name only) and is recorded when the ledger is writable; `skipped` records nothing. **Analyze C1:** `ledger._git` must resolve `git` with the same safe resolver (absolute PATH entries, nothing inside any Git working tree) instead of bare `git`; when none is found it raises `LedgerError("git not found outside working trees")`. Add a ledger test: a checkout-local `git` first on PATH is never executed by `ledger.append` or `ledger.common_dir`.
- [x] T013 [P] Write `run.py` integration tests in `tests/test_spec_workflow.py` (depends on T004), in the existing `EngineRunTests` harness: a fake `specify` exiting 0, 1 and 130 with a `draft_pr.checkpoint` that raises `RuntimeError`, and one that raises `KeyboardInterrupt`, → exit status unchanged and `Draft PR: failed-retryable (internal-error)` printed [FR-002, FR-011]; with all four token variables set in the operator environment, the fake `specify` dumps its environment and an agent step's environment: none of the four appears, while the checkpoint's `_command` env contains all four [BL-INV-003, SC-005]; the checkpoint is called exactly once, after `import_run`, for `start` and for `resume`, with the run ID [FR-002]; `claude-settings.json` still denies `git push*` and `gh *` and the Codex sandbox is unchanged [SC-005]. **Analyze G2:** add a case where the workflow pauses at a gate (engine exit status for a paused run) and the checkpoint still runs once and records its outcome [FR-002].
- [x] T014 Integrate the checkpoint in `tools/spec_workflow/run.py` (depends on T012, T013): import `draft_pr` at startup next to `ledger` (before any agent runs); build the workflow engine's `env` from `os.environ` minus `draft_pr.TOKEN_VARIABLES`; in the `finally` block, after `import_run`, call `draft_pr.checkpoint(ROOT, run_id)` inside `try/except (Exception, KeyboardInterrupt)`, print `draft_pr.format_line(outcome)` on stdout, and on exception print `Draft PR: failed-retryable (internal-error)` plus the exception type name; never assign `status` in that block. Update the module docstring to mention the Draft PR checkpoint and the stripped token variables.

**Checkpoint**: Foundation ready: the checkpoint resolves trusted programs and identity, classifies failures, prints and records an outcome, and runs at the end of every invocation without touching its exit status.

---

## Phase 3: User Story 1 - Feature work appears in a Draft PR without a manual step (Priority: P1) 🎯 MVP

**Goal**: When the published branch has a meaningful change and no PR exists, create one Draft PR to the default branch with the base branch's template and a Ballast section; otherwise report `pending` with its reason.

**Independent Test**: Against `FakeGitHub` with no PR and a compare listing a file outside `specs/17-draft-pr/`, `checkpoint` returns `created`, one `gh pr create --draft` was issued with the expected argv and body, and the ledger report shows the PR number, address and `created`.

### Acceptance tests for User Story 1

- [x] T015 [US1] Write creation tests in `tests/test_draft_pr.py` (depends on T004): no PR and `src/x.py` in the compare → `created`; the create argv is exactly `<gh> pr create --repo o/r --draft --base main --head feat-x --title <Issue title> --body-file -`; the stdin body's marked section holds `Related to #17`, `` `specs/17-draft-pr/` ``, the run ID and the fixed UTC time `2026-10-04T12:34:56Z`, and contains no `Closes`, `Fixes` or `Resolves` keyword [AC-001, FR-006]; the ledger event is `created` with `pr_number` and `pr_url` and the printed line is `Draft PR: created #42 https://github.com/o/r/pull/42` [AC-002]; a 300-character Issue title is truncated to 256; a cross-repository PR (head owner `fork`) with the same head name is ignored, then `created` (edge case).
- [x] T016 [US1] Write `pending` tests in `tests/test_draft_pr.py` (depends on T004): compare 404 → `pending/not-published`, no create [AC-003]; empty `files` (empty or self-cancelling commits) → `pending/no-meaningful-change` [AC-003, AC-004]; only `specs/17-draft-pr/spec.md`, and a rename whose `filename` and `previous_filename` are both inside `specs/17-draft-pr/` → `pending/no-meaningful-change` [AC-005]; a file under `specs/17-draft-prx/` or `specs/other/` counts as meaningful → `created` (exact prefix `specs/17-draft-pr/`) [AC-005, FR-003]; a rename from inside to outside the spec directory counts as meaningful; 300 spec-only files → `pending/diff-unclassified` [FR-003]; in every `pending` case no create or edit argv was issued.
- [x] T017 [US1] Write body-content tests in `tests/test_draft_pr.py` (depends on T004): template contents API returns base64 → body is the decoded template, a blank line, then the section, and a different `.github/pull_request_template.md` in the checkout never appears [FR-016]; template 404 → body is the section only, outcome `created` [FR-016]; template `HTTP 502` → `failed-retryable/github-error`, no create [FR-016, AC-010]; an intake comment with the marker and `Main outcome:`, `Risk:`, `Scope gate:` lines → those lines in the section as written; no intake comment, and a comment with the lines but no marker → `- Scope: no intake scope comment`; several intake comments with the newest on the second page → the newest from an `OWNER`/`MEMBER`/`COLLABORATOR` is used; newest marker comment from `CONTRIBUTOR` or `NONE` → ignored in favour of an older member comment, or "no intake scope comment"; a line over 500 characters is cut to 500; intake lines containing `@org/team`, `<!-- ballast:draft-pr:end -->` and `<script>` → `&#64;org/team`, `&lt;!-- ballast:draft-pr:end --&gt;`, `&lt;script&gt;`, and the body has exactly one begin and one end marker [FR-016, edge case].
- [x] T018 [P] [US1] Write ledger report tests in `tests/test_agent_run_ledger.py` (depends on T006): after two `pull_request` events (`pending`, then `created`) `report --json` shows `pull_request` equal to the latest event's `data` plus its `observed_at`, and the text report has one `pull_request:` line; with no event it shows `{"available": false, "reason": "no checkpoint recorded"}`; aggregate reports are unchanged [AC-002].

### Implementation for User Story 1

- [x] T019 [US1] Implement the PR lookup in `tools/spec_workflow/draft_pr.py` (depends on T011, T015): `<gh> api --paginate --slurp "repos/<owner>/<repo>/pulls?head=<owner>:<quoted published>&state=all&per_page=100"`, flatten every page, keep entries whose `head.ref` equals the published branch, `head.repo.owner.login` equals `owner` and `html_url` equals `https://github.com/<owner>/<repo>/pull/<number>`; derive `open`/`closed`/`merged` (from `merged_at`); return the filtered list. When the list is empty, continue to the compare (data-model § Decision order step 9, "none" branch); the other branches are added in T026 and T031.
- [x] T020 [US1] Implement the meaningful-change check in `tools/spec_workflow/draft_pr.py` (depends on T016, T019): `<gh> api repos/<owner>/<repo>/compare/<quoted base>...<quoted published>`; 404 → `pending/not-published`; meaningful when any `files` entry has a `filename`, or for a rename a `previous_filename`, not starting with `feature + "/"`; 300 entries with none outside → `pending/diff-unclassified`; otherwise `pending/no-meaningful-change`; other failures through `_classify`.
- [x] T021 [US1] Implement the body builder in `tools/spec_workflow/draft_pr.py` (depends on T011, T017): template via `<gh> api "repos/<owner>/<repo>/contents/.github/pull_request_template.md?ref=<quoted base>"`, base64-decoded as UTF-8, 404 = none, other failures classified; scope comment via `<gh> api --paginate --slurp "repos/<owner>/<repo>/issues/<n>/comments?per_page=100"`, newest by `created_at` among comments containing `INTAKE_MARK` with `author_association` in `{OWNER, MEMBER, COLLABORATOR}`, copying the `Main outcome:`, `Risk:`, `Scope gate:` lines, one line each, at most 500 characters, escaping `<`, `>`, `@`; `_section(issue, feature, run_id, checked_at, scope)` producing the canonical text of the contract exactly; `_title(issue_title)` truncated to 256 characters.
- [x] T022 [US1] Implement creation under the lock in `tools/spec_workflow/draft_pr.py` (depends on T019, T020, T021): open `<git common dir>/ballast-pr.lock` (from `ledger.common_dir`) refusing a symlink or non-regular file, `fcntl.flock` exclusive non-blocking with retries up to `LOCK_WAIT` seconds, else `failed-retryable/lock-busy`; inside, list again (T019), then `<gh> pr create --repo <owner>/<repo> --draft --base <base> --head <published> --title <title> --body-file -` with the body on stdin, then list again and return `created` only when exactly one open PR exists with base `base`, head `published` and `draft: true`, else `blocked-ambiguous/create-unverified` with its address.
- [x] T023 [US1] Add the `pull_request` report entry in `tools/spec_workflow/ledger.py` `report` and `_text_report` (depends on T006, T018), per [contracts/ledger-pull-request-event.md](contracts/ledger-pull-request-event.md) § Report.

**Checkpoint**: US1 is functional: an unpublished or spec-only branch is `pending`, a published implementation change yields one verified Draft PR, and the ledger report shows it.

---

## Phase 4: User Story 2 - Every later invocation reuses the same PR (Priority: P1)

**Goal**: Adopt the single open PR for the head and base (Ballast-created or hand-opened), changing at most the Ballast-marked section, and never produce a second PR, including under concurrency.

**Independent Test**: With a Ballast PR, a hand-opened PR and a ready PR each already open for the head, every checkpoint returns `reused`, issues no create, and any edit changes only the bytes between the markers.

### Acceptance tests for User Story 2

- [x] T024 [US2] Write reuse tests in `tests/test_draft_pr.py` (depends on T004): a Ballast Draft PR whose section equals the canonical text (fixed clock) → `reused`, no edit argv [AC-006]; a section from another run or an older checkpoint time → `reused`, exactly one `<gh> pr edit <N> --repo o/r --body-file -`, every byte outside the markers (template text, human text before and after) identical [AC-006, FR-007]; a hand-opened PR with no section and no Issue reference → `reused`, the edit appends a blank line and the section and keeps every other byte [AC-007]; a hand-opened PR already referencing `#17` as a whole token, or `github.com/o/r/issues/17` → `reused`, no edit, while `#170` does not count as a reference [AC-007]; a ready PR (`draft: false`) → `reused`, and no argv anywhere contains `--draft`, `--ready`, `--title`, `--base`, `--add-label`, `--add-reviewer`, `ready`, `merge`, `close` or `reopen` [AC-008, FR-007, FR-008]; two sections, or unbalanced markers → `reused/section-unmanaged`, no edit; a hand-opened PR is adopted even when the compare would be `no-meaningful-change` (lookup before compare) [AC-007]; one open PR with base `release` while the default is `main` → `blocked-ambiguous/base-mismatch`, line contains `PR #7 targets release, expected main`, no create or edit. **Analyze G1:** also assert that every recorded `git` argv is one of `symbolic-ref`, `for-each-ref`, `remote get-url`, `rev-parse` (never `push`, `fetch`, `commit`) [FR-004].
- [x] T025 [US2] Write concurrency tests in `tests/test_draft_pr.py` (depends on T004): two threads run `checkpoint` against one shared thread-safe `FakeGitHub` whose list reflects created PRs → exactly one create argv overall; one thread returns `created`, the other `reused` [AC-009, FR-009]; another clone created the PR first: `gh pr create` exits 1 with stderr `a pull request for branch "feat-x" into branch "main" already exists` and the next list returns that PR → `reused` with the section edit, not an error [AC-009, FR-009]; the list after create returns the new PR with `draft: false`, or with another base → `blocked-ambiguous/create-unverified`, never `created` [BL-INV-005]; the lock held by another process for longer than a patched short `LOCK_WAIT` → `failed-retryable/lock-busy`, no create [FR-009]; a symlinked lock file is refused.

### Implementation for User Story 2

- [x] T026 [US2] Implement reuse in `tools/spec_workflow/draft_pr.py` (depends on T022, T024): in the lookup decision, one open PR with `base.ref == base` → `reused`; one open PR with another base → `blocked-ambiguous/base-mismatch` with `pr_number`, `pr_url`, `matches` and the remedy `PR #N targets X, expected Y: change its base on GitHub, or close it`; section handling per data-model § Marked section (equal → none; one differing section → replace only the text between the markers; none and Issue referenced as `#N` whole token or `github.com/<owner>/<repo>/issues/N` → none; none and not referenced → append after a blank line; several or unbalanced → `section-unmanaged`), the edit through `<gh> pr edit <N> --repo <owner>/<repo> --body-file -` with the body on stdin, its failures classified as `failed-retryable`. Reuse is decided before the compare, so the body builder (T021) runs for a reused PR too. **Analyze A1:** on reuse only the marked-section builder runs; the template is never fetched for a reused PR.
- [x] T027 [US2] Handle the cross-clone refusal in `tools/spec_workflow/draft_pr.py` (depends on T025, T026): when `gh pr create` fails and its stderr matches `already exists`, list again and apply the T026 rules (normally `reused` with the section edit); keep `LOCK_WAIT` a module constant tests can patch.

**Checkpoint**: US1 and US2 both work: repeated, resumed, hand-opened, ready and concurrent cases converge on exactly one PR.

---

## Phase 5: User Story 3 - Failures are visible and safe to retry (Priority: P2)

**Goal**: Every failure or ambiguity yields one `failed-retryable` or `blocked-*` outcome with a fixed reason and remedy, changes nothing on GitHub when ambiguous, leaks no credential, and is retried on the next invocation.

**Independent Test**: Scripting an unavailable CLI, missing authentication, a network failure, two open PRs and a merged PR yields the documented outcome, remedy and no write call for each, and a following checkpoint with a healthy fake succeeds.

### Acceptance tests for User Story 3

- [x] T028 [US3] Write retryable-failure tests in `tests/test_draft_pr.py` (depends on T004): for each `gh` stage (repository, Issue, comments, PR list, compare, template, create, edit) and each failure (exit 4, `HTTP 401`, `HTTP 403`, timeout, `HTTP 502`) → `failed-retryable` with `gh-unauthenticated` / `gh-unauthenticated` / `gh-forbidden` / `github-unreachable` / `github-error` and the contract remedy (`run gh auth login` for unauthenticated) [AC-010]; a second `checkpoint` with a healthy fake then succeeds (retry needs no state) [AC-010]; the workflow outcome is unaffected (covered in `run.py` by T013) [AC-010].
- [x] T029 [US3] Write blocked-outcome tests in `tests/test_draft_pr.py` (depends on T004): two open PRs for the head → `blocked-ambiguous/several-open`, `matches=2`, both addresses printed before the remedy, no create or edit [AC-011]; only a closed PR → `blocked-closed/closed`; only a merged PR, or a closed and a merged one → `blocked-closed/merged`, `pr_number`/`pr_url` of the most recent match, no create, edit or reopen [AC-012]; a closed PR present only on the second page of the list → `blocked-closed`, no create [AC-012].
- [x] T030 [US3] Write credential-leakage and hostile-input tests in `tests/test_draft_pr.py` (depends on T004): a fake whose stderr and JSON contain `ghp_…`, `gho_…` and `Authorization: token …`, run through every outcome reachable by the fake → none of those strings appears in captured stdout, stderr or the ledger file [AC-014, FR-013]; a hostile Issue title (`$(rm -rf ~)`, backticks, `--draft=false`) reaches `gh pr create` as one verbatim argv element after `--title`; a helper raising inside `checkpoint` → `failed-retryable/internal-error`, the exception message not printed.

### Implementation for User Story 3

- [x] T031 [US3] Implement the remaining lookup outcomes in `tools/spec_workflow/draft_pr.py` (depends on T019, T029): two or more open → `blocked-ambiguous/several-open` with every address and `matches`; none open and one or more closed or merged → `blocked-closed` with reason `merged` when any match was merged, else `closed`, `matches`, and the most recent match's number and address (by `closed_at`, falling back to number).
- [x] T032 [US3] Close the failure paths in `tools/spec_workflow/draft_pr.py` (depends on T026, T027, T028, T030, T031): route every `gh` call stage listed in T028 through `_classify`; ensure `format_line` and `_record` take only fixed reason codes, validated numbers, URLs built from validated `owner`/`repo`/`number`, and GitHub base names for `base-mismatch`; confirm no code path writes `Result.stdout` or `Result.stderr` to stdout, stderr, the ledger or a PR body. Run T028–T030 to green.

**Checkpoint**: All three stories work independently; all 12 FR-014 situations have passing tests (SC-003).

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Operator documentation, gates, live evidence, reviews and reconciliation.

- [x] T033 [P] Add a "Draft PR" section to `templates/policies/spec-kit-workflow.md` (depends on T014, T032): when a Draft PR appears (end of every `ballast run` start or resume, once the published branch has a change outside `specs/<feature>/`), what the body contains (base-branch template, Ballast section, intake scope lines), that Ballast never pushes and never changes readiness, merges, closes or reopens, the seven states with each reason and remedy from the contract, the authority used (operator's `gh` 2.48+, resolved outside working trees; token variables withheld from agents), and the ledger `pull_request` entry. [FR-015]
- [x] T034 [P] Add one paragraph to the workflow section of `README.md` pointing to the policy's "Draft PR" section (depends on T033). [FR-015]
- [x] T035 Run `ballast setup` (or the documented refresh) so the installed `docs/policies/spec-kit-workflow.md` matches the template, and confirm `git status` shows no new tracked file outside the plan's Repository Impact table (depends on T033). [BL-INV-001] Evidence (2026-10-04): in a fresh clone of this branch, `BALLAST_STANDARD_DIR=<this checkout> ballast setup` installed `docs/policies/spec-kit-workflow.md` byte-identical to the template (Draft PR section included) and `git status --short` was empty; done in a clone so this checkout's trust baseline stays untouched.
- [x] T036 Run the fast gate and record commands and results for the PR: `uvx ruff check && uvx ruff format --check` and `uv run --no-project --python 3.13 --with pyyaml python -m unittest tests/test_*.py` (depends on T007, T014, T023, T032, T034, T035). [SC-003]
- [x] T037 Run the full local gate on Linux with a systemd user session, the Codex CLI and the Spec Kit CLI so the four CI-skipped tests also run; record the result or the unavailable gate and why (depends on T036).
- [ ] T038 Operator live check per [quickstart.md](quickstart.md) § 2 in a disposable GitHub repository, steps 1–6, and record each command and result in the PR description, including any step not run [AC-001, AC-002, AC-003, AC-005, AC-006, AC-007, AC-008, AC-010]. Manual evidence because creating a real PR needs GitHub; AC-004, AC-009, AC-011–AC-014 rely on the deterministic tests only (depends on T036).
- [ ] T039 Run the R2 reviews and store reports in `specs/17-draft-pr/reviews/`: security review (new external authority, credential handling, untrusted text into `gh` argv and the PR body, intake-comment author rule), engineering review, test review against this AC traceability table, documentation review of the policy section and ADR-0003 (depends on T001, T036).
- [ ] T040 Resolve open items in `specs/17-draft-pr/decisions.md` if any, run Spec Kit converge and the spec reconciliation skill, then ask the operator to approve ADR-0003 and set its status to `Accepted` only after that approval (depends on T037, T038, T039).

---
- [x] T041 Apply accepted DEC-0003, DEC-0004 and DEC-0005 (depends on T032): fix the data-model reuse row; in `_command` keep only `PATH` entries outside every working tree, drop Git location variables, override `core.fsmonitor`/`core.hooksPath`, and start every `gh` call in an empty temporary directory; read `[github] repository` from `ballast.toml` and stop as `blocked-unlinked/no-repository` or `repository-mismatch` before any `gh` call. Tests: `CommandSeamTests.test_child_path_keeps_only_entries_outside_working_trees`, `test_gh_never_reads_the_checkouts_git_config` (a real `core.fsmonitor` sentinel, shown to fire with both guards removed), `IdentityTests.test_missing_or_invalid_pinned_repository_is_unlinked`, `test_remote_redirected_away_from_pinned_repository_is_refused`, `test_pinned_repository_matches_case_insensitively`; the fake asserts every `gh` call starts outside the checkout. Update the contract, data model, research, quickstart, ADR-0003, policy and README.
- [x] T042 Apply accepted DEC-0006, DEC-0007 and DEC-0008 and the R2 review's implementation fixes (depends on T041): `draft_pr.pin_branch` records branch and upstream in operator state at `ballast run start` (run.py, before the engine; never on resume) and the checkpoint stops as `blocked-unlinked/branch-unpinned` or `branch-mismatch` before any `gh` call; re-read the PR before an edit and stop as `reused/body-changed` when its body changed; paginate the compare to GitHub's 3000 files; match the head repository's full name. Tests: `IdentityTests.test_run_without_a_branch_pin_is_unlinked`, `test_branch_switched_after_start_is_refused`, `test_upstream_redirected_after_start_is_refused`, `test_branch_pin_lives_outside_the_checkout`, `ReuseTests.test_body_edited_during_the_check_is_left_alone`, `test_edit_rereads_the_pr_right_before_writing`, `test_failed_reread_is_retryable_and_writes_nothing`, `PendingTests.test_change_beyond_the_first_page_is_meaningful`, `CreationTests.test_pr_from_another_repository_of_the_same_owner_is_ignored`, `DraftPrRunTests.test_start_pins_the_branch_before_the_engine_and_resume_never_does`, `test_failing_pin_never_stops_the_start`; each guard removed once and caught.

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: none. T001 and T002 are independent of code.
- **Foundational (Phase 2)**: T005–T007 need nothing from Phase 1; T008–T014 need T003/T004. Blocks all stories.
- **US1 (Phase 3)**: tests need only T004/T006; implementation needs T011 (identity) and T006.
- **US2 (Phase 4)**: tests need only T004; implementation builds on US1's lookup, body and creation (T019–T022), because reuse rewrites the same section and the cross-clone path follows a create.
- **US3 (Phase 5)**: tests need only T004; implementation needs T019 and, for T032, the US2 edit path.
- **Polish (Phase 6)**: after all stories.

### User Story Dependencies

- **US1 (P1)**: after Foundational. No dependency on other stories.
- **US2 (P1)**: after US1's T022 (lookup, body builder and creation). Independently testable with a pre-existing PR in the fake.
- **US3 (P2)**: T031 after US1's T019; T032 after US2's T026/T027. Its tests are independent.

### Within Each User Story

- Tests first, failing; then implementation in `draft_pr.py`, one task at a time (same file).

## Execution Wave DAG

Tasks in a wave have every dependency met by earlier waves. Tasks in one wave that edit the same file (`tests/test_draft_pr.py` or `tools/spec_workflow/draft_pr.py`) run one after another; only `[P]` tasks touch a file no other task in their wave touches.

| Wave | Tasks | Notes |
| --- | --- | --- |
| 1 | T001, T002, T003, T005 | ADR, plan fix, module skeleton, ledger tests: four different files |
| 2 | T004, T006 | harness; ledger kind |
| 3 | T007, T013, T018; then in `tests/test_draft_pr.py`: T008, T010, T015, T016, T017, T024, T025, T028, T029, T030 | all tests written before the code they prove; the `test_draft_pr.py` tasks run in sequence |
| 4 | T009, T023 | resolution and trust (`draft_pr.py`); ledger report (`ledger.py`) |
| 5 | T011 | identity and classification |
| 6 | T012, T019, T021 | output and recording, PR lookup, body builder (same file, in sequence) |
| 7 | T014, T020, T031 | `run.py` integration in parallel with the compare check and blocked outcomes (`draft_pr.py`, in sequence) |
| 8 | T022 | creation under the lock |
| 9 | T026 | reuse and section edit |
| 10 | T027 | cross-clone refusal |
| 11 | T032 | failure paths closed |
| 12 | T033, T035 after T033, T034 after T033 | documentation and installed-copy refresh |
| 13 | T036 | fast gate |
| 14 | T037, T038, T039 | full gate, live check, reviews |
| 15 | T040 | reconciliation and ADR approval |

## Parallel Example: Wave 3

```text
Task: "Document the pull_request kind in tools/spec_workflow/ledger-schema.md"            (T007)
Task: "Write run.py integration tests in tests/test_spec_workflow.py"                   (T013)
Task: "Write ledger report tests in tests/test_agent_run_ledger.py"                     (T018)
Task: "Write all draft_pr tests in tests/test_draft_pr.py (T008, T010, T015–T017, T024, T025, T028–T030), one after another"
```

## Implementation Strategy

### MVP first (User Story 1)

1. Phase 1 and Phase 2: the checkpoint runs at the end of every invocation, prints and records an outcome, and never changes the exit status.
2. Phase 3: a Draft PR is created when the published branch has a meaningful change.
3. **Stop and validate**: run US1's tests and the fast gate. US1 alone does not handle a branch that already has a PR, so do not ship it without US2: "exactly one" is half the outcome (spec US2 is also P1).

### Incremental delivery

1. Foundation → US1 (create) → US2 (reuse, concurrency) is the minimum mergeable increment.
2. US3 adds the remaining blocked outcomes and the failure hardening; it is required before merge because of FR-013/AC-014 and SC-004.
3. Polish: documentation, gates, live check, R2 reviews, reconciliation, ADR approval.

## Acceptance criteria traceability

| Criterion | Test or verification tasks |
| --- | --- |
| AC-001 | T015, T038 |
| AC-002 | T015, T018, T038 |
| AC-003 | T010, T016, T038 |
| AC-004 | T016 |
| AC-005 | T016, T038 |
| AC-006 | T010, T024, T038 |
| AC-007 | T024, T038 |
| AC-008 | T024, T038 |
| AC-009 | T025 |
| AC-010 | T008, T017, T028, T013, T038 |
| AC-011 | T029 |
| AC-012 | T029 |
| AC-013 | T010 |
| AC-014 | T030 |
| FR-001 / BL-INV-002 | T008 |
| FR-002, FR-011 | T013 |
| FR-003 | T016 |
| FR-009 | T025 |
| FR-010, FR-013 | T005, T030 |
| FR-015 | T033, T034, T039 |
| FR-016 | T015, T017 |
| SC-005 / BL-INV-003 | T013 |
| BL-INV-005 | T025 |

## Notes

- R2: the plan, ADR-0003 and the merge need explicit human approval; no task sets the ADR to `Accepted` before that.
- Do not weaken a failing test; record any discovery that conflicts with the spec in `specs/17-draft-pr/decisions.md` and stop for a human decision.
- Commit after each task or logical group.
