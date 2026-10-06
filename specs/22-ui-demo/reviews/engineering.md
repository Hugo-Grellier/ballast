# Engineering review: On-demand UI demo capture (#22)

- Review: implementation (engineering), first review, before any fix cycle
- Reviewer: claude-opus-5-5, fresh context, same provider as the author
- Inputs: `spec.md` (FR-001..FR-020, AC-001..AC-019 at the PD-0008 digest), `intent.md`, `plan.md`, `data-model.md`, the four contracts, `tasks.md` (T001..T041 all checked), `decisions.md` (DEC-0001 resolved, DEC-0002 open), `docs/policies/engineering.md`, `docs/policies/workflow.md`, `docs/policies/project/workflow.md`, ADR-0003/0006 and the new ADR-0013.
- Diff: the working tree against `11134f1` (the branch's last commit before the feature's own two docs commits). New: `tools/spec_workflow/demo.py`, `templates/github/workflows/ballast-demo.yml`, `tests/test_demo.py`, `docs/adr/0013-demo-capture-dispatch.md`. Changed: `draft_pr.py`, `packet.py`, `run.py`, `ledger.py`, `ledger-schema.md`, the policy template, `README.md`, `specs/TECHNICAL-SPEC.md` and four test files.

## What I checked

**Requirement coverage.** I traced each FR to code:

- FR-001..FR-003: `demo.demo_config` parses only the root `ballast.toml` and maps every rule to one fixed `ERRORS` string; it never raises, and the request refuses `not-configured`, `config-invalid` and `unknown-scenario` before any `gh` call.
- FR-004, AC-019: `run.py demo` checks `draft_pr._untrusted` (tamper and in-progress markers) and the run's invocation lock before calling `demo.request`. Agents still have no token and `gh` is still denied to them.
- FR-005..FR-007, AC-010: `_Request.check_workflow` requires an active workflow and equal blob IDs at the head commit and on the default branch. A missing head copy reads as `workflow-differs`. The dispatch `ref` is `work.run.published`, the feature branch. The template rejects a run whose `GITHUB_SHA` is not the requested commit and re-checks `git rev-parse HEAD` after checkout. `resolve` checks `head_sha` before status, so a run at another commit is `commit-mismatch` and its artifact is never read. A dispatch by someone with write access on the default branch can only run the default branch tip, because the `GITHUB_SHA == commit` check blocks it otherwise, so there is no path to default-branch caches.
- FR-008: the defaults are 14/15, the bounds are checked in Python and again in the workflow, and the job keeps the literal 65-minute backstop.
- FR-009: the wait sleeps 10 s and then reads page 1, at most 12 times within 120 s of the monotonic seam. It then makes exactly one `checkpoint(create=False)` refresh.
- FR-010..FR-012: `resolve` follows research R6 (ambiguous, truncated, not found within 24 h, mismatch, running, success→artifact, failed step→reason). `format_line` emits `[video]` only for a current `captured` capture. A stale capture links the job.
- FR-013: both checkpoint calls use `create=False`, and the request goes on only for `reused`.
- FR-014: `Sources.demo` is read only by `demo.lines` in `render`.
- FR-015: ADR-0013 lists exactly the calls that `demo.py` makes.
- FR-016: nothing is downloaded.
- FR-017: every call goes through `_Checkpoint.api`/`gh`, and failures map through `draft_pr._classify` to fixed causes.
- FR-018: name, environment and command pass through `packet.inert`.
- FR-020: `demo.py` imports only the standard library and sibling modules.

**Source authority and identity.** The contract comes from the protected `ballast.toml`. Requests come from the runner-only ledger events, and those events hold no free text. Runs and media come from GitHub Actions, and the head comes from the PR. Nothing reads the packet back. The random 16-hex request ID is the only correlation key.

**Import order.** The cycle `demo` ↔ `draft_pr` ↔ `packet` resolves because `draft_pr` only binds the module name, and `packet` uses `demo.*` at call time. `Sources.demo`'s annotation is lazy under `from __future__ import annotations`. `run.py` imports `demo` before any agent step.

**Partial failure.** A refusal or a failed read before dispatch writes nothing. The event is appended only after a successful dispatch. A read failure during the wait leaves `queued`, and the packet refresh then reports the real state. In `packet._Step.collect`, a `demo.ReadError` fails the packet step `failed-retryable` and leaves the Draft PR outcome unchanged. The race between the identity check and the dispatch is bounded by the two postconditions, as ADR-0013 states.

**Template.** It has one job, `contents: read`, no `secrets.` and no `environment:`. Inputs reach shells only through `env:`, the two actions are pinned by SHA, and checkout uses `persist-credentials: false`. The `if:` conditions of the three classification steps are mutually exclusive, and their implicit `success()` keeps the upload step to the success path. The `realpath -e` workspace check stops a symlink from pointing outside the workspace.

**Complexity and scope.** No unrelated refactor. The `draft_pr` change only splits `checkpoint` into `checkpoint_work` and adds `pull_head`, with no behavior change. The `ledger.py` addition follows the `acceptance_packet` pattern.

## Gate evidence

I could not run the fast gate in this reviewer session: the confined environment's home directory is read-only, so `uvx` cannot install ruff. The unittest suite errored in setup because it could not create its temporary operator state under `~/.local/state/ballast-tests` (659 errors, all `OSError: [Errno 30]`). One governance test also failed; it runs a nested subprocess that hits the same constraint. These results are environmental, not evidence either way. The run record's fix loop shows that the runner's cycle-0 feedback checks also failed (`ruff check` 2, `ruff format --check` 2, unittest 1). By inspection, `tools/spec_workflow/ledger.py:2038` reads `syncs =[event ...`, which `ruff format --check` rejects, so the format gate fails on the diff itself.

## Open decision

DEC-0002 (the rendering of the reproduce command) has no resolution yet. The implementation follows the current contract, which is safe but not always copyable. See the findings in the draft.

## Residual risk for the merge reviewer

- ADR-0013 adds the launcher's first GitHub write other than the PR body edit, and it is agent-provisional.
- DEC-0001 was resolved by the driving agent under the operator's standing authority.
- The live pilot (SC-001, SC-004) is post-merge evidence.
- This review has the same provider as the author.

<!-- ballast-findings: begin -->
## Findings (recorded from the review draft)

- F-001 (medium, implementation-bug, resolved): tools/spec_workflow/ledger.py:2038 reads 'syncs =[event for event in events ...]', which ruff format --check rejects, so the fast gate fails on this diff. The run record's cycle-0 feedback checks show all three gate commands failing. Fix: format the file, then run the full fast gate (ruff check, ruff format --check, unittest) and make it pass. Fixed before commit: ledger.py and the new files are formatted and the fast gate passes (ruff check, ruff format --check, full unittest suite).
- F-002 (medium, spec-ambiguity, resolved): AC-007 asks the line to name the command exactly as declared, and SC-004 asks that it be copyable to reproduce the journey. packet.inert backslash-escapes _ ( ) * \| ! ~ #, turns &lt; &gt; &amp; $ into entities and inserts zero-width spaces after :// and www. GitHub shows a code span literally, so a command such as ./demo_login.sh &gt; out.webm is shown altered. DEC-0002 records this, with options, and has no resolution yet. The current rendering is safe. Choosing the rendering is a decision for the resolve step and the merge reviewer, not a defect the fix step can settle. DEC-0002 resolved (option 2): the command is shown as declared in a code span; fix 6b41594 with tests.
- F-003 (low, implementation-bug, resolved): _Request.dispatch guards against the default branch by comparing the dispatch ref with work.run.base, but check_workflow has already read the repository's actual default_branch. When the run's base is not the default branch, the guard does not check the stated invariant (never dispatch on the default branch). Pass the default branch read in check_workflow to dispatch and refuse when the ref equals it. Fixed in 78759c2: dispatch refuses the default branch check_workflow read; test_never_dispatches_on_the_repository_default_branch.
<!-- ballast-findings: end -->
