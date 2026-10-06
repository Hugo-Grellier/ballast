# Implementation Plan: Chat mode

**Branch**: `feat/20-chat-mode` | **Date**: 2026-10-06 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/20-chat-mode/spec.md`. Its intent is agent-provisional: PD-0003 in [autonomous/record.md](autonomous/record.md), Autonomous run `2cb9c5c5`.

**Risk**: R2. Chat adds an interactive agent path through the launcher's trust model, changes the agent confinement for interactive steps, and gives the trusted runner a second publication caller. All three are R2 boundaries in [`docs/policies/project/workflow.md`](../../docs/policies/project/workflow.md). In this Autonomous run every plan decision below is agent-provisional, and the merge decision is the single human approval (BL-INV-006).

## Summary

An operator runs a feature conversationally, one phase at a time, through `ballast run`. Chat keeps the trust, synchronization, postcondition, evidence and human-approval guarantees of a headless run.

How it works ([research.md](research.md)):

- **Ballast drives the run, one invocation per action** (R1). `ballast run start --mode chat` creates an operator run record and pins the branch. Later actions are separate invocations: `step`, `status`, `approve`, `reject`, `resolve`, `checks`, `mode` and `publish`. Each agent step is therefore the only agent step of its invocation and always follows the launcher's trust, tamper and unfinished-step checks, then branch synchronization (R5). The operator edits and inspects in their own shell between invocations.
- **The phase graph** (R2) reuses the `ballast-feature` step and gate IDs. The runner offers or starts a phase only when its cumulative upstream checks and current approvals pass at that moment. Each evaluation is recorded, so a failure blocks until a later run of the same check passes, whatever the mode.
- **Interactive confinement** (R3, R3a). The agent runs as `claude --permission-mode dontAsk` or `codex -a never`, with the headless rules, inside the Autonomous bubblewrap confinement and a systemd scope, behind a wrapper-owned pty. Anything not allowed is denied. A grant made inside the session cannot get past bwrap.
- **Step close** (R4). The runner stops and confirms the scope, compares protected inputs, runs the phase's `artifacts.py` postcondition and a write-scope check, and records the step in operator state and in the ledger.
- **Human gates** (R11). `approve`, `reject` and `resolve` need a TTY and typed confirmation, are refused while a step is active, and bind each approval to the exact artifact digest. Agent output never opens a gate.
- **Evidence** (R6, R7). The operator run record is the source of truth. It holds hash-chained human decisions and events, step entries and tree manifests. The ledger gets the same event kinds as a headless run, plus a `mode` field.
- **Publication** (R14). `publish` reuses the Autonomous publisher, made mode-aware, after a current final approval. It commits, pushes and writes a Chat evidence section into the single Draft PR.
- **Mode switches** (R12). Chat and human-gated switch in the same run; human-gated steps then run headless through the unchanged `agent.py`. A `ballast-feature` run, or a stopped Autonomous run through `continue --mode chat`, continues as a linked Chat run. No path raises a run to Autonomous.

## Technical Context

**Language/Version**: Python ≥3.11, standard library only (`pty`, `termios`, `tty`, `fcntl`, `select`, `signal` are added to the modules used). Workflow tools run under the system `/usr/bin/python3 -I -S`. Tests run on 3.13.

**Primary Dependencies**:

- **Agent CLIs**: interactive `claude` (`--permission-mode dontAsk`, verified in `claude --help`) and `codex` (`--ask-for-approval never`, pilot check P-2).
- **Confinement**: `bwrap` (already required for Autonomous), and `systemd-run --user` and `git` 2.41 or later, both unchanged.
- **Forge**: `gh`, operator side only, unchanged.
- **Spec Kit CLI 1.0.11**: unchanged, and not used to drive Chat runs.
- **New Python packages**: none. Tests keep `pyyaml` through `uv run --with`.

**Storage**: Local files only:

- The operator run record under `$XDG_STATE_HOME/ballast/<checkout>/runs/<run>/`: `run.json`, `steps.jsonl`, `events.jsonl` (new), `human-decisions.jsonl` (new kinds) and `manifests/` (new).
- The ledger and archive under `<git common dir>/speckit-runs/<run>/`.
- Agent logs under `.specify/workflow-state/<run>/agents/`.
- No new committed file except feature artifacts and the existing `intent.md` approval block. See [data-model.md](data-model.md).

**Testing**:

- `unittest` in a new `tests/test_chat_mode.py`, using:
  - a fake interactive agent driven through a pty;
  - fake `gh`, `git`, `systemd-run` and `bwrap` placed in `trusted_directory()`;
  - a temporary `XDG_STATE_HOME` and temporary Git repositories.
- Cases needing a real `bwrap`, systemd or agent CLI are skipped where unavailable, as today.
- Operator pilot scenarios are in [quickstart.md](quickstart.md).

**Target Platform**: GitHub on Linux with a systemd user session (the qualified 1.0 environment).

**Project Type**: A CLI and workflow standard installed into other repositories.

**Performance Goals**: Nothing user-visible beyond today's behavior:

- one `ls-remote` per `step` (existing branch-check cost);
- one tree manifest per invocation, which hashes tracked and unignored files once;
- the pty relay adds no measurable latency at terminal speeds.

**Constraints**:

- Stdlib only, under `-I -S`.
- Nothing executes from an agent-writable path before trust.
- No agent gains approval, record, push, PR or state-directory authority, and no permission prompt is offered.
- `templates/spec-kit/workflows/*/workflow.yml` are byte-identical to `main`.
- Existing tests pass with their assertions unchanged (SC-007).
- One active agent step per checkout at a time (the existing marker).

**Scale/Scope**:

- One Chat run per feature, with any number of steps; there is no step or wall-time limit (Assumptions).
- Conversation logs are bounded only by the session.
- About 9 new or extended `run` subcommands, one new module (`chat.py`), and changes in `run.py`, `agent.py`, `autonomy.py`, `artifacts.py`, `branch_sync.py`, `draft_pr.py`, `ledger.py`, `launcher.py` (refusal text only) and the shipped documentation.

## Constitution Check

*Gate before Phase 0; re-checked after Phase 1 design (result below).*

| Principle | How the design complies | Status |
| --- | --- | --- |
| BL-INV-001 Projects own only their own files | The new `chat.py` and `claude-chat-settings.json` live in `.ballast/spec_workflow/`, which `tools/setup` installs wholesale and the project ignores. Chat state is in the operator state directory and the Git common directory. The only committed effects are canonical feature artifacts and the existing `intent.md` approval block. No ignore-probe change. | Pass |
| BL-INV-002 Nothing executes from a writable checkout before trust | Every Chat action is a `ballast run` invocation through the pinned launcher, which verifies the baseline, the tamper marker and the `in-progress` marker before executing `run.py`. `chat.py` is imported by `run.py` at startup, before any agent step, inside the baseline. The interactive agent runs only after branch synchronization, and the synchronization's own protected-input re-check applies. | Pass |
| BL-INV-003 Delegated authority | Interactive steps run with the headless rules (deny-without-prompt), inside bwrap, with operator state, `.git`, protected inputs, `.claude/` and `.codex/` out of reach or read-only. Approvals, resolutions, mode changes and publication exist only as operator commands, refused while a step is active. A protected change fails the step and writes the tamper marker. | Pass |
| BL-INV-004 A project picks a version, never a source | No change to `tools/ballast` fetch rules. | Pass |
| BL-INV-005 Postconditions over exit codes | Every step close runs the phase's `artifacts.py` postcondition and the cumulative checks, plus a write-scope check. An agent exit of 0, a "Verdict" line or a conversation claim proves nothing. | Pass |
| 6. Portable, dependency-free tools | Stdlib `pty`, `termios`, `fcntl`, `select` and `signal`; no new package. | Pass |
| 7. Generic by default | Phase names, review kinds and messages are generic. Project specifics stay in `ballast.toml` (`[checks]`, `[github]`). | Pass |
| 8. Executable evidence | Every refusal path (each preflight condition × start, step and resume; each forgery attempt; each mode switch; each concurrency case) has a test that fails if the stop is removed (SC-002, SC-004, SC-005). See Verification Strategy. | Pass |
| BL-INV-006 A provisional decision is never human approval | Chat never writes a provisional decision. A continued Autonomous run's PDs stay labeled `agent-provisional` in its log, its `record.md`, the Chat summary and the PR, even after a human approval supersedes them. Chat approvals are real human decisions and are rendered only from `gate-approval` records. | Pass |
| Governance: weakening an invariant needs R2 and a reason | No invariant is weakened. Dropping bwrap's `--new-session` for a wrapper-owned pty (R3a) narrows no guarantee, because TIOCSTI can reach only the agent's own pty. It is still an R2 confinement change and is listed as D-3. | Pass |

**Post-design re-check**: Passed after Phase 1. No violation needs justification. The two duplications are under Complexity Tracking.

## Architecture Boundaries

- **Affected areas**:
  - The trusted launcher path: `launcher.py` (refusal text) → `run.py` (new subcommands) → new `chat.py`.
  - The agent wrapper (`agent.py`: interactive launch beside the headless one).
  - Confinement and the operator record (`autonomy.py`).
  - Artifact validators (`artifacts.py`: feature from an operator record, the Chat decisions rule, mode-neutral project checks).
  - Branch synchronization (`branch_sync.py`: recovery text).
  - The Draft PR checkpoint (`draft_pr.py`: feature resolution without engine state).
  - The ledger (`ledger.py`: `mode` field and the Chat report path).
  - Shipped policies, skills and copy-once templates.
  - Repository governance docs: `specs/TECHNICAL-SPEC.md` §91, `README.md`, `AGENTS.md`, `CLAUDE.md`, and the new ADR.
- **Contracts and data flow**:
  1. The operator runs `ballast run <action> RUN ...`. The launcher refuses or executes `run.py`, which dispatches to `chat.py` ([contracts/cli.md](contracts/cli.md)).
  2. `chat.py` reads and appends the operator run record, calls `branch_sync.synchronize`, evaluates `artifacts.py` checks in-process, and launches the agent through `agent.run_interactive` (Chat) or the existing headless `agent.py` path (human-gated) ([contracts/step-runner.md](contracts/step-runner.md), [contracts/phase-graph.md](contracts/phase-graph.md)).
  3. At each close it appends ledger events and archives ([contracts/run-record.md](contracts/run-record.md)). `publish` calls `autonomy.publish` in Chat mode ([contracts/pr-evidence.md](contracts/pr-evidence.md)).
  4. Source of truth: the operator run record. The ledger, the handoff summary and the PR section are projections. Canonical intent stays in the feature artifacts, and the intent approval stays the registered `intent.md` block.
- **Architecture references**:
  - [Technical spec §91](../TECHNICAL-SPEC.md#91-v10-target) (Chat as a required 1.0 mode), §37 (human intervention), §46 (agent permission model), §35 R2.
  - [Roadmap Priority 4](../../docs/plans/2026-10-02-product-roadmap.md#priority-4--let-the-operator-choose-the-level-of-supervision).
  - [ADR-0003](../../docs/adr/0003-launcher-github-authority.md), [ADR-0004](../../docs/adr/0004-autonomous-provisional-decisions.md), [ADR-0005](../../docs/adr/0005-launcher-branch-synchronization.md).
  - `templates/policies/spec-kit-workflow.md` "Workflow runner contract" and "Branch synchronization".
  - [Constitution](../../.specify/memory/constitution.md).
- **Proposed architecture decisions**: Record ADR `docs/adr/0009-chat-mode-operator-driven-steps.md`. It covers:
  - Ballast, not the Spec Kit engine, drives Chat runs, one invocation per action (R1);
  - interactive steps run under bwrap behind a wrapper-owned pty without `--new-session` (R3, R3a);
  - every Chat `step` is an invocation that runs branch synchronization (extends ADR-0005's list, not its rule);
  - human gate approvals for every gate are bound to artifact digests in operator state (R11);
  - the Autonomous publisher becomes the publisher for Chat too (extends ADR-0004).

  The ADR is agent-provisional in this run and accepted only by the merge.

## Decisions for plan review

Each decision is agent-provisional in this Autonomous run and is decided at the plan decision point. The merge reviewer sees all of them.

| ID | Decision | Recommendation |
| --- | --- | --- |
| D-1 | Ballast drives Chat runs as one invocation per action, outside the Spec Kit engine; the phase and gate IDs reuse `ballast-feature`. | Accept (R1, R2). |
| D-2 | Interactive steps run inside the Autonomous bwrap confinement, so bwrap becomes a Chat prerequisite, even though human-gated headless steps do not use it. | Accept (R3): an interactive session cannot lock its own permission mode. |
| D-3 | Omit bwrap `--new-session` only for a Chat step whose stdio is a wrapper-owned pty that is its controlling terminal. | Accept (R3a), with the two tests named there and pilot check P-3. |
| D-4 | Approvals for every gate (not only intent) are human decisions bound to artifact digests in operator state, given by `ballast run approve` with typed TTY confirmation. Resolutions need `ballast run resolve`. | Accept (R11). This is stricter than human-gated, never weaker. |
| D-5 | In a Ballast-driven run, "human-gated" means headless steps through the unchanged `agent.py`. A `ballast-feature` run or a stopped Autonomous run continues in Chat only as a linked run; engine gate approvals other than intent are re-asked. | Accept (R12). |
| D-6 | `publish` reuses the Autonomous publisher's commit, push and PR path for Chat after a current final approval, with a Chat section. | Accept (R14). |
| D-7 | Interrupted steps whose wrapper died are recovered through the existing `ballast discard-runs`; there is no new launcher command. | Accept (R10); revisit only if the pilot shows it is too coarse. |

## Repository Impact

New files:

- `tools/spec_workflow/chat.py`: phase graph, entry conditions and gates, the step lifecycle, out-of-step detection, the handoff summary, Chat ledger events and the Chat PR section renderer.
- `tools/spec_workflow/claude-chat-settings.json`.
- `tests/test_chat_mode.py`, plus `tests/fixtures/chat/fake_tui.py` (a fake interactive agent that reads the pty and writes scripted artifacts or forgeries).
- `docs/adr/0009-chat-mode-operator-driven-steps.md`.

Changed files:

- `tools/spec_workflow/run.py`:
  - `--mode chat` on `start`;
  - the `step`, `status`, `approve`, `reject`, `resolve`, `checks` and `mode` subcommands;
  - `continue --mode chat`;
  - Chat `publish`;
  - the Chat `resume` refusal;
  - the usage text.
- `tools/spec_workflow/agent.py`: `run_interactive()` (pty relay, interactive argv, shared containment helpers) beside `main()`. Headless argv is unchanged.
- `tools/spec_workflow/autonomy.py`:
  - `MODES` gains `chat`, and `WORKFLOWS` gains `ballast-chat`;
  - mode-history `switch` and `lower → chat` rules;
  - new human-decision kinds;
  - `confined_argv(..., interactive_pty=False, readonly_extra=())`;
  - mode-aware `publish` and renderer selection;
  - `_archive_operator` target naming.
- `tools/spec_workflow/artifacts.py`:
  - a `Feature` from an operator Chat record (with the registered-approval check enabled);
  - the Chat decisions rule;
  - a mode-neutral `run_checks` core;
  - `record_intent` callable for a Chat continuation, removing the provisional block.
- `tools/spec_workflow/branch_sync.py`: a `rerun` text parameter for Chat recovery lines.
- `tools/spec_workflow/draft_pr.py`: `identify` falls back to the operator record or the pin when no engine `inputs.json` exists.
- `tools/spec_workflow/ledger.py` and `ledger-schema.md`: the `mode` field and `mode-changed` status on `run`, and the Chat report path.
- `tools/spec_workflow/launcher.py`: the unfinished-step refusal names the run and step. No other logic changes.
- Templates:
  - `templates/policies/spec-kit-workflow.md` (a "Chat runs" section and runner-contract rows);
  - `templates/policies/workflow.md` (modes);
  - `templates/AGENTS.md`;
  - `templates/skills/ballast-feature-intake/SKILL.md` (the Chat start command).
- Repository-owned files: `AGENTS.md`, `CLAUDE.md`, `README.md`, `specs/TECHNICAL-SPEC.md` (§91 status line).

Unchanged:

- every `templates/spec-kit/workflows/*/workflow.yml`;
- `claude-settings.json`;
- `tools/ballast`;
- `tools/setup` (it already copies `tools/spec_workflow/` wholesale);
- the constitution.

## Verification Strategy

| Acceptance | Evidence |
| --- | --- |
| AC-001, AC-010, SC-002 | For each of the five preflight conditions (changed baseline, tamper marker, unfinished step, changed protected input, blocked synchronization) × `start --mode chat`, `step` and Chat `resume`: refused before any agent spawn, with the headless reason. The fake agent records whether it ran. |
| AC-002, FR-007, edge "step not allowed yet" | Phase-graph unit tests: each phase is offered only when its entry checks pass. A refused phase names the failing check and `E-NNNN`. Re-running an earlier phase is allowed. |
| AC-003, FR-005, edge "permission the step does not allow" | Argv tests: `dontAsk`, the chat settings deny list ⊇ `claude-settings.json`, `-a never`, `FORBIDDEN` refused, bwrap present, `.claude/` and `.codex/` read-only. Confined tests: writes to `ballast.toml`, operator state and `.git` fail inside the step. Pilot P-4 and P-5. |
| AC-004, FR-009, FR-010, edge "ends a step while writing" | Lifecycle tests: the postcondition runs only after the scope is confirmed gone. A failed postcondition blocks dependents until a later passing run, and the failure stays in `events.jsonl`. An unconfirmed scope keeps `in-progress` and exits 4. |
| AC-005, AC-011, FR-019, SC-006 | `status` golden test: every handoff field is rendered from the record, with no conversation log present. |
| AC-006, FR-011, edges "protected input between steps" and "re-runs an earlier step" | An out-of-step edit is recorded with its paths and stale HDs. A protected-input edit makes the launcher refuse. Re-running `specify` after `approve plan` makes the intent and plan approvals stale. |
| AC-007, AC-008, AC-009, FR-006, FR-015, SC-004 | Forgery tests, one each: an approval block written by the agent; `RECONCILE_STATUS`, "approved" and "Verdict" text; `run.json` or `human-decisions.jsonl` unreachable from the step; `ballast run approve` from inside a step (launcher refusal); `approve` without a TTY; a resolution written by the agent without `resolve`. None opens a gate or records a pass. |
| AC-012 | The wrapper gets `SIGHUP` mid-step and closes the step as interrupted with its postcondition. For a dead wrapper, the marker is kept, `discard-runs` runs, and the next invocation records the step as interrupted before any other step. |
| AC-013, FR-012 | A second `step`, a headless `resume` and `continue` while a step is active are each refused, and the message names the run and step. Two concurrent `step` invocations: the flock lets exactly one run. |
| AC-014, FR-013, SC-003 | Ledger tests: a Chat run's events validate against the schema, `ledger report` is valid with `mode: chat`, and the evidence kinds match a human-gated fixture run. |
| AC-015, FR-014, edge "no other provider" | A review step uses the review integration in a fresh process, with write scope limited to `reviews/`. `cross_provider` is true or false as appropriate, and the record states it. |
| AC-016, AC-017, FR-016, FR-017, edge "secret in conversation" | Publisher test with fake `git` and `gh`: refused without a current final approval; only `add`, `commit`, `push` (no force) and `pr create --draft` or edit. Golden Chat section; no `speckit-runs`, `.specify/workflow-state` or log content in the body. |
| AC-018 to AC-021, FR-020, FR-022, SC-005 | Every allowed switch keeps earlier entries byte-identical and failed checks still blocking. Unconfirmed resolutions and PDs keep their status. Every raise to Autonomous is refused. `mode` on a `ballast-feature` run makes a linked run and refuses `resume`. |
| AC-022, FR-021 | `continue --mode chat`: an HD, `lower → chat`, a linked run, PDs listed as provisional, and after `approve intent` the PD is shown superseded and still labeled provisional. |
| Edge "integration cannot run confined" | Failed self-test, and Codex without a nested sandbox: refused for that integration with the reason, and the other integration is named. |
| FR-001 | No `chat` path is reachable except through `run.py` behind the launcher. `chat.py` refuses execution as `__main__`. |
| FR-023 | A governance test asserts that the Chat sections exist in the shipped policies, `AGENTS.md` template and intake skill. Documentation review. |
| SC-007 | Existing `tests/test_*.py` pass with their assertions unchanged; fixture-only changes are listed in the PR. Every `workflow.yml` is byte-identical to `main`. |

Required reviews (review matrix):

- engineering and test;
- security (agent authority, trust model, confinement change D-3, publication);
- documentation (public CLI, policy and ADR);
- architecture (ADR-0009);
- spec reconciliation before the PR.

Use a cross-provider reviewer when Codex can run confined. Otherwise the record states single-provider review (DEC-0004 in the run record).

## Feature Artifacts

```text
specs/20-chat-mode/
├── intent.md
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── cli.md
│   ├── phase-graph.md
│   ├── step-runner.md
│   ├── run-record.md
│   └── pr-evidence.md
├── checklists/
├── autonomous/        # run record projection of run 2cb9c5c5
├── tasks.md           # next: speckit-tasks
├── decisions.md       # only when implementation discovers a decision
└── reviews/           # plan review, implementation reviews, pilot, convergence
```

## Follow-ups (out of scope, to file as Issues)

- **F-1**: A narrower recovery than `discard-runs` for one dead Chat step (D-7), if the pilot shows a need.
- **F-2**: Autonomous resume (#21) and the richer review packet (#19) will consume Chat records as they do Autonomous ones.
- **F-4**: Detect agent writes to git-ignored paths that later agents read (for example `AGENTS.local.md`), which no tree manifest lists ([DEC-0003](decisions.md); security review SEC-002, SEC-008).
- **F-5**: Low findings that the implementation reviews left open (`reviews/security.md`, `engineering.md`, `test.md`), filed as one hardening Issue, #66:
  - SEC-001 for headless steps: add the installed skills to `agent._protected_state`.
  - SEC-006: drain the terminal before the flush, and filter OSC 52.
  - SEC-002: fail closed past the 500-path cap.
  - SEC-008: earlier step logs are readable by later agents.
  - SEC-009: create the `in-progress` marker exclusively, across runs.
  - SEC-010: `.claude/settings.json` written by a headless step.
  - ENG-005: the shared commit, push and PR tail.
  - ENG-007, ENG-008, ENG-010, ENG-012, ENG-013.
  - TST-005 to TST-012.
- **F-3**: A provider-native transcript (Claude `--session-id` JSONL) as an optional second local log, bound out of bwrap's overlay.

## Complexity Tracking

| Item | Why needed | Simpler alternative rejected because |
| --- | --- | --- |
| A second publication caller (`autonomy.publish` in Chat mode) | FR-016 requires the trusted runner to publish Chat evidence into the single Draft PR. | The #17 checkpoint never pushes and its section carries no steps, approvals, reviews or checks. |
| A Chat path in `ledger report` beside the engine import | SC-003 compares Chat and human-gated records in one format. | Writing engine `state.json` and `log.jsonl` for Chat would forge state the engine never produced. |
