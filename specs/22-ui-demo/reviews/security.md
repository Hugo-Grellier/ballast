# Security review: 22-ui-demo

- Kind: security
- Reviewer: claude/claude-opus-5-5, agent-provisional, same provider as the author
- Scope: working tree against the branch start; specialist review required by `.specify/workflow-state/required-reviews/22-ui-demo.json` (R2: agent authority, what `ballast` executes or downloads)

## What was reviewed

- `tools/spec_workflow/demo.py` (contract parsing, GitHub reads, run resolution, packet rendering, the request and its one dispatch)
- `tools/spec_workflow/run.py` (`ballast run demo`: argument handling, tamper and in-progress markers, invocation lock, output)
- `tools/spec_workflow/draft_pr.py` (`checkpoint_work`, `pull_head`), `packet.py` (demo section wiring), `ledger.py` and `ledger-schema.md` (`demo_capture` kind)
- `templates/github/workflows/ballast-demo.yml` (the copy-once capture workflow)
- `docs/adr/0013-demo-capture-dispatch.md`, `specs/22-ui-demo/decisions.md` DEC-0001, research R15
- `tests/test_demo.py` (request, template, workflow identity and inert-rendering tests)

Policies read: `docs/policies/security.md`, `docs/policies/project/workflow.md` (R2 boundaries), `AGENTS.md` invariants. `docs/policies/project/security.md` does not exist.

## Paths traced

**Who can request a capture.** The only entry point is the trusted `ballast run demo` subcommand, dispatched in `run.py` before the generic tamper check but with its own `_untrusted` check that refuses on the tamper marker and on an agent step's `in-progress` marker, then the run's invocation lock. Agents keep `Bash(gh *)`, `Edit(./.github/**)` and `Edit(./ballast.toml)` denied and receive no token, so an agent step cannot dispatch, and cannot alter the command or the workflow definition (AC-019, FR-004).

**Where the executed command comes from.** `demo_config` reads only the `[demo]` table of the root `ballast.toml`, which is a protected input under `ballast trust`. Scenario names, environment and command are validated (printable, bounded, one line; names against a fixed pattern; video through `packet.safe_path`). No branch copy of `ballast.toml` is read, on the runner or locally. Ballast never runs the command locally and never downloads a browser, recorder, log or artifact (FR-016).

**Execution scope on the forge (DEC-0001, R15).** The dispatch `ref` is the run's published feature branch, and the code refuses it if it equals the run's base. Before dispatching, Ballast compares the Git blob of `.github/workflows/ballast-demo.yml` at the PR head commit with the default branch's and refuses `workflow-differs` when they differ or the head copy is absent. The job rejects a run whose `GITHUB_SHA` is not the requested commit and checks the checked-out `HEAD` again. Ballast links a result only when the run's `head_sha` equals the requested commit; any other run is `failed (commit-mismatch)` and its artifact is never read. The race between the blob check and GitHub resolving the branch tip is caught by those last two checks, as ADR-0013 argues. PR-head code therefore runs only under the feature branch's ref, and its runtime-token cache scope stays the feature branch's own.

**The workflow template.** The only trigger is `workflow_dispatch`, with `permissions: contents: read` at workflow level and no job override. There is no `secrets.` reference and no `environment:`. Every input reaches a shell only through `env:`; `${{ }}` appears only in `run-name` and `with:` values, after the validation step. Both actions are pinned by commit SHA, checkout uses `persist-credentials: false`, and there is no cache action. The video path is checked as relative, without `..`, and resolved inside `$GITHUB_WORKSPACE` before upload. `tests/test_demo.py` `TemplateTests` asserts these properties statically.

**Credentials and untrusted output.** Every `gh` call goes through #17's checkpoint seam (resolved program, list argv, hardened environment, empty working directory, 30 s limit). The dispatch body goes on stdin as JSON, never on the command line. `gh` output is parsed into typed fields; only fixed cause codes reach the output line or the ledger. The run's title, step names and artifact names are compared against fixed values and never printed. The `demo_capture` ledger event is runner-only, holds codes and IDs only, and is written after a successful dispatch. Packet text from the contract passes through `packet.inert`; links are built only from validated integer run and artifact IDs.

**Malformed input.** Invalid contract keys, out-of-range retention or timeout, duplicate or malformed names, multi-line commands and unsafe video paths produce fixed errors with no dispatch. An invalid run ID or argument count is refused before any `gh` call. Run-list and job responses with unexpected shapes raise `github-error`, never "nothing found".

**Disclosure.** The video is an Actions artifact with the repository's read access. The documentation and template header state that scenarios must use seeded, nonsensitive data and fake accounts, and that the video is readable by anyone with repository read access, which on a public repository is everyone (AC-009).

## Residual observations

Two points remain. Neither opens a path beyond what ADR-0013 already accepts.

- `dispatch` refuses a branch equal to the run's base, not one equal to the repository's default branch that `check_workflow` has just read. Those differ only for a PR whose base is not the default branch. The published branch is the runner's own feature branch, so this is defense in depth.
- The step that classifies the outcome runs in the same job as PR-head code. That code can write `$GITHUB_OUTPUT`/`$GITHUB_ENV` or leave a background process, so `captured` versus `failed` is reported by untrusted code. This is acceptable only because a video is never evidence or approval (FR-014), which the packet's intro line states.

Same-provider review: independence is reduced. Live behavior of GitHub (cache scopes, `GITHUB_SHA` for `workflow_dispatch`) is taken from research R15 and is not exercised offline; the SC-001 pilot is post-merge.

<!-- ballast-findings: begin -->
## Findings (recorded from the review draft)

- F-001 (low, implementation-bug, resolved): demo._Request.dispatch refuses a branch equal to the run's base, not the repository default branch that check_workflow already read. They differ only for a PR whose base is not the default branch, and the published branch is the runner's own feature branch, so this is defense in depth: compare against the fetched default branch as well. Fixed in 78759c2: dispatch refuses the default branch check_workflow read; test_never_dispatches_on_the_repository_default_branch.
- F-002 (info, spec-ambiguity, resolved): The outcome steps run in the same job as PR-head code, which can write GITHUB_OUTPUT/GITHUB_ENV or leave a background process, so captured versus failed is reported by untrusted code. Acceptable because a video is never evidence or approval (FR-014); worth one sentence in the policy's Demo capture section. Fixed in 1b0cc91: the policy's Demo capture section says the outcome is reported by the job that runs the PR's code.
<!-- ballast-findings: end -->
