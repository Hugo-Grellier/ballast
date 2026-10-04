# Implementation Plan: One reusable Draft PR for issue-linked feature work

**Branch**: `feat-github-draft-pr` | **Date**: 2026-10-04 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/17-draft-pr/spec.md` (intent approved 2026-10-04, digest in [intent.md](intent.md))

**Risk**: R2. The trusted launcher gains GitHub write authority through the operator's `gh`, and `ballast` executes a new external tool. Needs explicit human approval of this plan.

## Summary

At the end of every `ballast run` start or resume invocation, `run.py` calls a new trusted module, `draft_pr.py`, after archiving and importing the run. The module resolves the feature's Issue, branch, upstream, GitHub repository and default branch from Git configuration and GitHub. It never reads agent-written text. `git` and the operator's `gh` are resolved like `ballast doctor`'s `resolve_program` (absolute `PATH` entries outside every Git working tree) and called by absolute path with fixed arguments. It lists every PR whose head is that branch, paginated. One open PR with the resolved base is adopted, and at most its Ballast-marked section changes; an open PR with another base blocks. When none exists and the published branch differs from the base outside `specs/<feature>/`, it creates one Draft PR under a lock in the Git common directory, with the base branch's pull-request template followed by a Ballast section (Issue link, intake scope summary, run status), then re-reads it to verify base, head and draft state. A creation refused because another clone already opened the PR becomes a reuse. Every other situation produces one of the spec's outcomes, or `failed-retryable`, with a fixed reason and remedy. The outcome is printed as one line and recorded as a new `pull_request` ledger event. Nothing in the checkpoint can change the workflow's exit status. Agents gain no new permission, and `run.py` now strips the four GitHub token variables from the environment it gives the workflow engine. See [research.md](research.md) for each decision.

## Technical Context

**Language/Version**: Python ≥ 3.11 standard library only. `run.py` runs under `python3 -I`, and the module is imported at startup, before any agent step.

**Primary Dependencies**: None at runtime. External tools: `git` (already used) and the operator's `gh` 2.48 or later (new for the launcher; `ballast doctor` already probes it), both resolved outside every Git working tree and called by absolute path.

**Storage**: The ledger `events.jsonl` under `<git common dir>/speckit-runs/<run>/` (new event kind) and a lock file `<git common dir>/ballast-pr.lock`. GitHub holds the PR itself.

**Testing**: `unittest`, offline. A real temporary Git repository supplies branch and upstream configuration; a scripted fake replaces the single command seam for `gh`; temporary `PATH` directories exercise program resolution. Thread-based concurrency test against a shared fake, plus a fake cross-clone `already exists` refusal, and an agent-boundary environment test in the `run.py` harness.

**Target Platform**: The qualified 1.0 host: Linux, systemd user session, authenticated `gh`, GitHub.

**Project Type**: Workflow tool inside the installed standard (`tools/spec_workflow/`).

**Performance Goals**: The checkpoint adds at most five `gh` calls on reuse (repository, Issue, comments, PR list, edit) and nine when creating (plus compare, template, a second list, create and a verifying list), plus one request per extra page of 100 PRs or comments. Each call has a 30 s limit, and the lock wait is at most 60 s.

**Constraints**: Standard library only; no shell; no bare `gh` or `git`; no `gh` output, environment value or credential printed or stored (FR-013); no push, no fetch (FR-004); always a Draft, never ready, merge, close or reopen (FR-008); never alters the exit status (FR-011).

**Scale/Scope**: One new module of about 450 lines, about 45 lines in `run.py`, about 60 in `ledger.py`, one new test file, documentation.

No NEEDS CLARIFICATION remains.

## Constitution Check

*Gate before Phase 0, re-checked after Phase 1. Result: **PASS** both times, no violations.*

| Principle | How the design holds it |
| --- | --- |
| 1. Projects own only their files (BL-INV-001) | `draft_pr.py` ships inside `tools/spec_workflow/`, which `tools/setup` already installs into the ignored `.ballast/`. The lock and ledger live in the Git common directory. No tracked file is written. |
| 2. Nothing executes from a writable checkout (BL-INV-002) | The module is loaded by `run.py` at startup, after the launcher verified the inputs, and before any agent can write. The checkpoint first refuses to act when `BALLAST_TAMPERED` or the in-progress marker exists (research R2). It executes only `git` and the operator's `gh`, each resolved to an absolute path outside every Git working tree (research R3), with fixed argv; a checkout-local `gh` first on `PATH` is never run. `.git/config` is agent-writable, so it is treated as untrusted (DEC-0004, DEC-0005): `gh` starts in an empty temporary directory and never reads it, `gh`/`git` get only `PATH` entries outside working trees with `core.fsmonitor`/`core.hooksPath` overridden and Git location variables dropped, and the upstream remote must match the repository pinned in the protected `ballast.toml`. Ballast's own `git` reads only refs, the upstream and the remote URL. |
| 3. Delegated authority (BL-INV-003) | The new GitHub authority stays with the operator-side launcher. `claude-settings.json` and the Codex sandbox are unchanged and still deny `git push` and `gh` (SC-005). `run.py` removes `GH_TOKEN`, `GITHUB_TOKEN`, `GH_ENTERPRISE_TOKEN` and `GITHUB_ENTERPRISE_TOKEN` from the environment it passes to the workflow engine (research R3), so an operator token cannot reach an agent; the checkpoint, in `run.py`'s own process, keeps them. Other inherited variables are noted in research R12. |
| 4. A project picks a version, never a source (BL-INV-004) | Not touched: the checkpoint downloads nothing. |
| 5. Postconditions over exit codes (BL-INV-005) | `created` is recorded only after a second, paginated listing confirms exactly one open PR for the head whose base, head and draft state match the request; a mismatch is `blocked-ambiguous`. `gh` exit 0 alone is never treated as success. |
| 6. Portable, dependency-free tools | Standard library only. |
| 7. Generic by default | No project names. The marker, wording and reasons are generic, and any GitHub repository works. |
| 8. Executable evidence | Every FR-014 situation, every AC, FR-016 body content and the refusal paths (tamper marker, checkout-local `gh`/`git`, agent token environment, base mismatch, hostile names and scope text, token leakage) have a named test in [quickstart.md](quickstart.md). |

## Architecture Boundaries

- **Affected areas**: the run entry point `tools/spec_workflow/run.py` (checkpoint call), a new trusted module `tools/spec_workflow/draft_pr.py`, the ledger `tools/spec_workflow/ledger.py` and its schema note, and operator documentation.
- **Contracts and data flow**: `run.py` → `import_run` → `draft_pr.checkpoint(root, run_id)` (feature read from the run's `inputs.json`) → Git config and GitHub (via the resolved `git` and `gh`) → one `Outcome` → `ledger.append` (`pull_request` event) and one printed line. GitHub stays the source of truth for the PR. The ledger only records observations, so no second source of truth appears: every checkpoint recomputes the outcome from GitHub. See [contracts/pr-checkpoint.md](contracts/pr-checkpoint.md), [contracts/ledger-pull-request-event.md](contracts/ledger-pull-request-event.md) and [data-model.md](data-model.md).
- **Architecture references**: [constitution](../../.specify/memory/constitution.md) BL-INV-002 and BL-INV-003; [technical spec §59 (PR contract) and §91 (v1.0 target)](../../specs/TECHNICAL-SPEC.md#91-v10-target); [roadmap Priority 3 item 2](../../docs/plans/2026-10-02-product-roadmap.md#priority-3--make-long-running-feature-work-safe-and-visible); [project R2 rules](../../docs/policies/project/workflow.md); [ledger schema](../../tools/spec_workflow/ledger-schema.md).
- **Proposed architecture decisions** (each needs human approval, then an ADR):
  1. **ADR-0003 Launcher-side GitHub authority.** The trusted `run.py` may call the operator's `gh` after a run, resolved outside every Git working tree, with a fixed command allowlist (`api` reads of the repository, Issue, Issue comments, pulls, compare and template contents; `pr create --draft`; `pr edit --body-file`), only when no tamper or in-progress marker exists. Agents stay denied and receive no GitHub token variable. This is the boundary later features (#27 publisher, ready-for-review policy, review packets) will extend, so it should be stated once.

## Repository Impact

| Path | Change |
| --- | --- |
| `tools/spec_workflow/draft_pr.py` | New: program resolution (the `resolve_program` rule), identity resolution, command seam, paginated PR lookup with base check, compare classification, template and intake-comment reading, lock, create and verify or section edit, outcome, remedy text, ledger event. |
| `tools/spec_workflow/run.py` | Import `draft_pr` at startup; remove the four GitHub token variables from the workflow engine's `env`; call `checkpoint` in `finally` after `import_run`, guarded so no exception changes `status`; print the outcome line. Update the module docstring. |
| `tools/spec_workflow/ledger.py` | `pull_request` in `FIELDS` and `ENUM_FIELDS`; new `url` value type; per-outcome required fields; excluded from `record`; latest outcome in `report` and `_text_report`. |
| `tools/spec_workflow/ledger-schema.md` | Document the kind, its fields and the compatibility note. |
| `tests/test_draft_pr.py` | New: the FR-014 scenarios, FR-016 body content, program resolution, base mismatch, pagination, cross-clone refusal, AC-014 leakage and hostile-input tests ([quickstart.md](quickstart.md)). |
| `tests/test_spec_workflow.py` | `run.py` calls the checkpoint once per start/resume, and a raising checkpoint leaves exit statuses 0, 1 and 130 unchanged. The workflow engine's environment lacks the four GitHub token variables while the checkpoint's has them. The agent settings still deny `git push` and `gh`. |
| `tests/test_agent_run_ledger.py` | `pull_request` validation and report. |
| `templates/policies/spec-kit-workflow.md` | New section "Draft PR": when it appears, what the body contains, the seven states and their remedies, the authority used and the `gh` requirement (FR-015). The installed `docs/policies/` copy is refreshed by `ballast setup`. |
| `README.md` | One paragraph in the workflow section pointing to that policy section. |
| `docs/adr/0003-launcher-github-authority.md` | New, after approval. |

`tools/setup`, `tools/ballast`, `tools/cli.toml`, `claude-settings.json` and `agent.py` are unchanged.

## Feature Artifacts

```text
specs/17-draft-pr/
├── issue.md
├── intent.md
├── spec.md
├── plan.md            # this file
├── research.md        # Phase 0 decisions R1–R12, plan reviews 1–2 folded in
├── data-model.md      # identity, PR, outcome, decision order
├── contracts/
│   ├── pr-checkpoint.md
│   └── ledger-pull-request-event.md
├── quickstart.md      # validation scenarios mapped to ACs
├── checklists/
├── tasks.md           # next: speckit-tasks
├── decisions.md       # only if implementation discovers one
└── reviews/
```

## Review notes

- Issue #17's acceptance criteria (template, scope/status summary, readiness per mode) are covered by FR-016 and research R9: the template comes from the base branch on GitHub, the summary from the Issue's intake scope comment (newest comment carrying `<!-- ballast-intake:`), and Ballast always creates a Draft and never changes readiness, merges, closes or reopens (FR-008).
- Plan reviews 1 and 2 are resolved in every artifact: safe program resolution (R3, contract, data model, quickstart), token removal from the agent environment (R3, contract, quickstart), base-checked paginated lookup and verified creation (R7), cross-clone refusal handling (R8) and the FR-016 body (R9).
- **Decided (agent, provisional, standing authority)**: a `gh` or `git` found only inside working trees is `failed-retryable` with reason `gh-untrusted` / `git-untrusted`; FR-010's seven outcomes are unchanged. A `gh` absent from `PATH` stays `failed-retryable/gh-missing` as AC-010 requires.
- Required reviews (R2): security review (new external authority, credential handling, untrusted text into `gh` argv), engineering review, test review, and documentation review for the policy section and ADR.

## Complexity Tracking

No constitution violations.
