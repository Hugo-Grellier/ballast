# Implementation Plan: On-demand UI demo capture linked to the PR

**Branch**: `feat/22-ui-demo` | **Date**: 2026-10-06 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/22-ui-demo/spec.md` (intent agent-provisional, PD-0007, digest in [intent.md](intent.md))

**Risk**: R2, rechecked in [research R14](research.md#r14-risk-recheck). The change adds a path by which `ballast` causes a project command to run (on the forge runner) and one new GitHub write (workflow dispatch), proposed as ADR-0012. **Mode**: Autonomous run `d6b5dff2`. Every decision here is agent-provisional, including the pre-change R2 approval; merging the PR is the only human approval.

## Summary

The operator runs `ballast run demo RUN_ID SCENARIO`, a new trusted `run.py` subcommand.

1. It reads the scenario from a new `[demo]` table in the protected `ballast.toml`, and refuses with a fixed reason when there is no open Draft PR.
2. It checks that the PR head's copy of the copy-once GitHub Actions workflow (`ballast-demo.yml`) is byte-identical to the default branch's, then dispatches it on the **PR's head branch** ref, never the default branch, so the PR-head code it runs can write no cache scope beyond the feature branch's ([research R15](research.md#r15-execution-scope-of-the-capture-run-plan-review-f-001)). The dispatch inputs are the PR's head commit, the declared command, the video path, the timeout and the retention, plus a random request ID.
3. The workflow has no secrets and `contents: read`. It checks out the head commit, runs the command under `timeout` (which enforces the contract timeout; the job's fixed 65-minute limit is a backstop), and uploads the one video file as an Actions artifact (14 days and 15 minutes by default).
4. Ballast records a `demo_capture` ledger event, waits at most 120 s, and refreshes the #19 packet through the existing #17 checkpoint.

At every checkpoint, the packet's new **Demo captures** section matches each scenario's newest request to its run on the feature branch by `display_title`, and requires the run's `head_sha` to be the requested commit. It reads the run's status, the failed step name and the artifact. It shows one outcome per scenario: `captured` (video link), `in progress`, `failed` (including `commit-mismatch`), `missing`, `stale` (with the commit and the outcome there), `not yet requested`, `not configured` or `configuration invalid`.

The video never changes a criterion's evidence state. Ballast never runs the project's command locally, and never downloads a browser, a recorder or the media.

## Technical Context

**Language/Version**: Python ≥ 3.11, standard library only. The new `demo.py` is imported through `draft_pr`/`packet` at `run.py` startup, before any agent step, and runs under `python3 -I -S`. The workflow template is GitHub Actions YAML with bash steps.

**Primary Dependencies**: no Python dependency. External programs are #17's resolved `git` and `gh` (≥ 2.48). The template uses `actions/checkout` and `actions/upload-artifact`, pinned by SHA, and needs a dependency evaluation ([research R4](research.md#r4-capture-workflow-template-templatesgithubworkflowsballast-demoyml)).

**Storage**: the ledger `events.jsonl` gains the new `demo_capture` kind. GitHub Actions holds the runs and artifacts, which are the source of truth for the media. The PR description holds the derived packet. No new local store.

**Testing**: `unittest`, offline. The fixtures are #17's scripted `_command` fake for `gh`, a temporary Git repository, an injected clock and a monotonic sleep seam for the wait. The template gets a static YAML test (pyyaml, test-only).

**Target Platform**: the qualified 1.0 host (Linux, authenticated `gh` with Actions write access to the repository) and GitHub-hosted `ubuntu-latest` runners.

**Project Type**: a workflow tool inside the installed standard (`tools/spec_workflow/`), plus a copy-once template.

**Performance Goals**:
- The request makes 1 workflow read, 1 repository read, 2 contents reads and 1 dispatch, plus ≤ 12 run-list reads (page 1) during the wait.
- Each checkpoint makes 1–5 run-list page reads (1 unless the feature branch has more than 100 demo runs since the window date), plus ≤ 1 jobs read or ≤ 1 artifacts read per declared scenario (≤ 20).
- Every call is bounded by #17's 30 s limit.

**Constraints**:
- No `${{ }}` in shell scripts.
- No secrets in the job.
- Inert rendering of project text.
- Links built only from validated integers.
- No log or artifact download.
- No free text in the ledger.
- The dispatch ref is always the PR's head branch, never the default branch, and only after the workflow blob at the head equals the default branch's.
- The template's job `timeout-minutes` is a literal (Actions expressions have no arithmetic).

**Scale/Scope**:
- `demo.py`: about 450 lines (config, request, resolve, render lines).
- About 40 lines in `packet.py`, 15 in `draft_pr.py` (one exposed helper), 60 in `run.py` and 40 in `ledger.py`.
- One template of about 90 lines.
- One new test file.
- Documentation and ADR-0012.

No NEEDS CLARIFICATION remains. All three D-05/D-06/D-07 assumptions and both clarifications (PD-0005, PD-0006) are realized as specified. [Research R7](research.md#r7-ledger-event-demo_capture) adds one presentation note, "declared command changed", to keep AC-007 truthful. It does not change behavior or authority. The plan review's F-001 changed how FR-007 is realized: the capture runs on the PR's head branch with a definition verified identical to the default branch's ([research R15](research.md#r15-execution-scope-of-the-capture-run-plan-review-f-001)). FR-007 and AC-010 need a wording change that keeps their intent; it is recorded in [decisions.md DEC-0001](decisions.md#dec-0001--proposal), and spec.md is not edited by the plan.

## Constitution Check

*Gate before Phase 0, re-checked after Phase 1. Result: **PASS** both times, no violations.*

| Principle | How the design holds it |
| --- | --- |
| 1. Projects own only their files (BL-INV-001) | `demo.py` installs with `tools/spec_workflow/` into the ignored `.ballast/`. The project commits only `[demo]` in its own `ballast.toml` and the copy-once workflow, the same category as `pr-title.yml`. `tools/setup` is unchanged. |
| 2. Nothing executes from a writable checkout (BL-INV-002) | Locally, Ballast runs only #17's resolved `gh` and `git` through `_command`. The project command runs only on the forge runner, from the trusted `ballast.toml` value. The workflow definition that runs is the feature branch's copy only when its blob equals the default branch's (checked before dispatch), and a run at any other commit is never linked (`commit-mismatch`), so no changed feature-branch file runs with the operator's authority (research R15). |
| 3. Delegated authority (BL-INV-003) | No agent permission changes: agents keep `Bash(gh *)` and `Edit(./.github/**)`/`Edit(./ballast.toml)` denied, and receive no token. `ballast run demo` is refused during an agent step by the launcher's in-progress marker. The PR-head code the job runs executes under the feature branch's ref, so the Actions runtime token it can reach writes only the cache scope that branch's own runs already write; it gains no reach into default-branch caches or privileged default-branch workflows (research R15, plan review F-001). |
| 4. A project picks a version, never a source (BL-INV-004) | Nothing is downloaded by Ballast. The template is a copy of the pinned version, and its actions are pinned by SHA. |
| 5. Postconditions over exit codes (BL-INV-005) | `captured` requires a successful run *and* an unexpired artifact with the request's name. The `demo_capture` event is written only after the dispatch call succeeds. A packet edit keeps #19's re-read and section checks. |
| 6. Portable, dependency-free tools | Standard library only. pyyaml is used by tests only. |
| 7. Generic by default | Generic scenario contract; any recording tool; no project names in the template. |
| 8. Executable evidence | Every AC maps to a [quickstart](quickstart.md) scenario, including refusal, hostile text, token leakage and template-shape tests. |
| 9. A provisional decision is never human approval (BL-INV-006) | The section states that a video is neither evidence nor approval. The text passes #19's `HUMAN_APPROVAL` guard. ADR-0012 is marked agent-provisional until merge. |

## Architecture Boundaries

- **Affected areas**:
  - a new trusted module `tools/spec_workflow/demo.py`;
  - the packet `tools/spec_workflow/packet.py` (demo section in `Sources` and `render`);
  - the PR checkpoint `tools/spec_workflow/draft_pr.py` (reused unchanged except for an exposed PR-head read);
  - the run command `tools/spec_workflow/run.py` (`demo` subcommand);
  - the ledger `tools/spec_workflow/ledger.py` (`demo_capture` kind) and its schema note;
  - a copy-once template under `templates/github/workflows/`;
  - the operator documentation.
- **Contracts and data flow**:
  - Request: `run.py demo` → `demo.request` → `draft_pr.checkpoint(create=False)` (`reused`) → PR, repository and workflow reads → workflow blob identity check (head vs default branch) → dispatch on the feature branch → `demo_capture` event → bounded wait → `draft_pr.checkpoint(create=False)` → `packet.publish`.
  - Packet: `packet._Step.collect` → `demo.collect(step, head, events)` (bounded, paginated run list for the feature branch; jobs; artifacts) → `Sources.demo` → `render`.
  - Sources of truth: `ballast.toml` for the contract, the ledger for requests, GitHub Actions for runs and media, and the PR for the head.
  - Contracts: [demo-config.md](contracts/demo-config.md), [demo-command.md](contracts/demo-command.md), [capture-workflow.md](contracts/capture-workflow.md), [packet-demo-section.md](contracts/packet-demo-section.md) and [data-model.md](data-model.md).
- **Architecture references**:
  - [constitution](../../.specify/memory/constitution.md) BL-INV-002, -003, -004, -006;
  - [ADR-0003](../../docs/adr/0003-launcher-github-authority.md) and [ADR-0006](../../docs/adr/0006-review-packet-reads.md);
  - [technical spec §91](../TECHNICAL-SPEC.md#91-v10-target);
  - #19 [packet format](../19-acceptance-packet/contracts/packet-format.md) and [checkpoint integration](../19-acceptance-packet/contracts/checkpoint-integration.md);
  - [ledger schema](../../tools/spec_workflow/ledger-schema.md).
- **Proposed architecture decisions** (agent-provisional here; the merge approves them):
  1. **ADR-0012 Demo capture dispatch under the launcher's GitHub authority.** This extends ADR-0003/0006 with the reads and the one dispatch write in [research R12](research.md#r12-new-github-calls-adr-0012). It also sets these rules:
     - untrusted PR-head code never runs in a workflow run whose ref is the default branch: the dispatch ref is always the PR's head branch;
     - Ballast dispatches only when the head commit's `ballast-demo.yml` blob equals the default branch's, and links a result only when the run's `head_sha` is the requested commit; the race between the check and the dispatch is bounded by these two checks and grants nothing a push to the branch does not (research R15);
     - the command comes only from trusted `ballast.toml`;
     - the job has no secrets and `contents: read`, uses no cache action, and has a fixed `timeout-minutes` backstop;
     - Ballast never downloads logs or artifacts, and executes nothing new locally.

## Repository Impact

| Path | Change |
| --- | --- |
| `tools/spec_workflow/demo.py` | New. `DemoConfig`/`DemoScenario` and `demo_config(root)`; `request(root, run_id, scenario, wait=True)`, returning a `DemoOutcome` with fixed reasons and remedies, including the workflow blob identity check (research R15); `collect(step, head, events)` → `DemoSection`, with the bounded run-list pagination; `resolve` (research R6, including `commit-mismatch` and `run-list-truncated`); `lines(section, level)` for the packet; `format_line`; `event_data`. |
| `tools/spec_workflow/packet.py` | `Sources.demo`. `collect` calls `demo.collect`, and a GitHub read failure there fails the step as `failed-retryable`. `render` adds `### Demo captures` after UI states, with a count line at level ≥ 3. |
| `tools/spec_workflow/draft_pr.py` | Import `demo` (so `run.py` imports it before any agent step). Expose the existing `_Checkpoint` seam for `demo.request`. No behavior change. |
| `tools/spec_workflow/run.py` | `demo` in `COMMANDS`, with `_demo_command(options)` under `_invocation_lock`. Prints the demo, Draft PR and packet lines. Usage and docstring updated. |
| `tools/spec_workflow/ledger.py` | `demo_capture` in `FIELDS`, `RUNNER_ONLY` and the source map. Field patterns for `scenario`, `request` and `command_digest`. `report` shows the latest capture per scenario. |
| `tools/spec_workflow/ledger-schema.md` | Document `demo_capture`. |
| `templates/github/workflows/ballast-demo.yml` | New copy-once template ([capture-workflow.md](contracts/capture-workflow.md)). |
| `tests/test_demo.py` | New: quickstart scenarios 1–6 and 9–20, plus the template static test (7). |
| `tests/test_packet.py`, `tests/test_spec_workflow.py`, `tests/test_agent_run_ledger.py`, `tests/test_governance.py` | Demo section isolation from criteria; `run demo` refusals and lock; event validation; policy text (scenario 8). |
| `templates/policies/spec-kit-workflow.md` | New subsection "Demo capture" after "Acceptance packet". It covers the `[demo]` table, copying the template to the default branch (and why a feature branch must carry the same file: the capture runs on the feature branch's ref so PR code cannot write default-branch caches), `ballast run demo`, each outcome and reason (a command that itself exits 124 or 137 is reported `timed-out`), the reproduce command, local reproduction without credentials, seeded nonsensitive data and the artifact's read access. The installed `docs/policies/` copy refreshes via `ballast setup`. |
| `README.md` | The copy-once template list names the demo capture workflow. |
| `specs/TECHNICAL-SPEC.md` | §91: on-demand demo capture is in 1.0, and automatic capture is later. |
| `docs/adr/0012-demo-capture-dispatch.md` | New (ADR-0012). |

`tools/setup`, `tools/ballast`, `tools/cli.toml`, `launcher.py`, `agent.py`, `claude-settings.json`, `autonomy.py`, `chat.py` and `artifacts.py` are unchanged. Chat and human-gated checkpoints show the demo section through the same `draft_pr.checkpoint` path.

## Feature Artifacts

```text
specs/22-ui-demo/
├── intent.md
├── discovery.md
├── spec.md
├── plan.md            # this file
├── research.md        # Phase 0 decisions R1–R14
├── data-model.md
├── contracts/
│   ├── demo-config.md
│   ├── demo-command.md
│   ├── capture-workflow.md
│   └── packet-demo-section.md
├── quickstart.md      # validation scenarios mapped to ACs, post-merge pilot
├── checklists/
├── autonomous/        # run record (rendered by the runner)
├── tasks.md           # next: speckit-tasks
├── decisions.md       # DEC-0001: capture execution scope (plan review F-001)
└── reviews/
```

## Review notes

- **Required reviews** (R2, [review matrix](../../docs/policies/workflow.md#review-triggers)):
  - engineering review;
  - security review: a new execution path, a new GitHub write, script injection in the template, and project text rendered into the PR;
  - test review;
  - documentation review: the policy subsection and ADR-0012;
  - dependency evaluation: `actions/checkout` and `actions/upload-artifact` in the template.
- **For the plan gate**:
  - confirm R2 and accept ADR-0012 as an extension of ADR-0003/0006;
  - accept that the command is passed as a dispatch input from the trusted local `ballast.toml` rather than read on the runner ([research R2](research.md#r2-where-the-contract-lives-and-what-the-runner-executes));
  - accept the capture's execution scope: feature-branch ref with a verified definition instead of default-branch dispatch ([research R15](research.md#r15-execution-scope-of-the-capture-run-plan-review-f-001)), and the FR-007/AC-010 wording change it needs ([decisions.md DEC-0001](decisions.md#dec-0001--proposal));
  - accept that the live pilot (SC-001) is post-merge operator evidence ([research R13](research.md#r13-pilot-evidence-sc-001)).
- **Known limit, documented**: captures belong to the run's ledger. A `ballast run continue` starts a new run whose packet lists the scenarios as `not yet requested` until the operator requests again.

## Complexity Tracking

No constitution violations.
