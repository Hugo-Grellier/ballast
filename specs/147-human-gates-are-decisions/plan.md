# Implementation Plan: Human gates are decisions, not command relays

**Branch**: `feat-147-human-gates-are-decisions` | **Date**: 2026-10-13 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/147-human-gates-are-decisions/spec.md` (intent agent-provisional, PD-0009, digest in [intent.md](intent.md))

**Risk**: R2. The plan touches four [R2 boundaries](../../docs/policies/project/workflow.md#r2-boundaries): the launcher's trust model (a new baseline source), the headless-agent permission model (who may run which `ballast` command, and a confined headless Chat step), what `ballast` executes or downloads (the pre-launcher refresh fetches the pinned standard and runs setup), and the paths setup installs (regeneration during refresh).

This is Autonomous run `2e651132`. Every design decision below is agent-provisional, not human-approved, and merging the PR is the single human approval (BL-INV-006). D-01, D-03, D-04 and D-05 are settled from the Issue body; D-02 is the operator's block resolution HD-0002 (option A); D-06 and D-07 are agent-provisional (PD-0002, PD-0003). D-08 is the operator's resolution of plan-review F-001 (HD-0003): a relayed `resume` or `continue` of a decision-carrying block needs `--ref`. D-09 is the operator's resolution at the tasks gate (HD-0004): `ballast trust` keeps today's terminal-free behavior, so the agent session may run it outside a step, never inside one. The second plan review's findings are folded into the design: F-001 (engine gates prompt only at a terminal) in research R8, the ADR-0020 content list and the AC-011 test; F-002 (a human-gated run records no relayed actor) and F-003 (`continue` takes only Autonomous sources) in [cli.md](contracts/cli.md#agent-command-matrix). Two agent inferences narrow D-02 and are listed for merge review in [research R2](research.md#r2-refresh-eligibility-fr-001-fr-003-ac-002-ac-005-ac-006):

- The any-bytes rule applies only to refreshing an existing baseline of the same repository.
- `.venv` changes are never attributable.

One agent inference narrows D-08 and is listed for merge review in [research R8](research.md#r8-which-relays-each-mode-allows-fr-008-fr-010-fr-012-ac-011-to-ac-016-ac-028): block categories the spec names in neither list (`tamper`, `unfinished-step`, `permission`, `forge`, `credential`, and any added later) are treated as carrying a decision, so their relay needs `--ref`.

## Summary

Four changes remove every operator command that carries no decision, without weakening a check.

1. **Trust follows the pinned default branch.**
   - Before running the launcher for `run`, `ledger` or `intake`, the global `ballast` command asks the launcher why it would refuse. On a protected-input change or a pin mismatch, it runs the pinned standard's `setup --refresh` under the exclusive lock.
   - The refresh records nothing unless every condition holds:
     - the baseline's provenance names the same reviewed repository `ballast.toml` pins;
     - every changed protected input is either installed by setup or a committed file equal to the live default branch, observed through ADR-0015's hardened throwaway path;
     - no marker exists;
     - after the normal installation regenerates `.ballast/spec_workflow` from the current `ballast.toml`, the generated agent settings equal what `ballast.toml` produces.
   - It then records a `default-branch` baseline naming the commit, and the run prints it.
   - `ballast trust` refuses stale generated settings.
   - The launcher's comparison, refusals and markers are unchanged, so anything else still blocks for `ballast trust`.
2. **Agent sessions run mechanical commands and relay decisions.**
   - A new `actor` rule makes every decision record say who acted: `operator` at a terminal, or `relayed` with `--relayed-by SESSION`. Without either, the command is refused.
   - Relayed approvals are accepted only in Chat runs, and relayed `start --mode autonomous` only when the run is eligible.
   - Relayed `resume` and `continue` of a run stopped on a block that carries a decision (decision, contradiction, review-finding, fix-cycle limit, ineligible) need `--ref` naming the operator's in-chat answer, or are refused (operator decision D-08 on Issue #147, plan-review F-001). Blocks that carry no decision (branch sync, interruption, usage limit, postcondition) may be resumed without asking. Both are recorded as relayed.
   - `reject`, `resolve` and `mode` stay terminal-only. `trust` keeps today's terminal-free behavior, so the agent session may run it on a checkout it set up; inside a step it is refused (operator decision D-09 on Issue #147).
   - A confined headless Chat step (`step --headless`) lets the session advance a Chat run between gates.
   - Every renderer shows "relayed by agent session S" and never "by operator" for those records.
3. **Batch approval.** `approve RUN GATE...` or `--through GATE` validates every gate under one lock, lists every decision, takes one typed line (or one relay in Chat), and appends all HDs atomically.
4. **Recovery without extra commands.**
   - `discard-runs` handles `--help`, refuses unknown arguments, and names `ballast trust` only when inputs actually changed.
   - Resume after an implementation postcondition reruns `implement`.
   - A confirmed-stopped usage-limit exit becomes a resumable `interrupted` stop.
   - Autonomous start offers an Issue-named branch at a terminal and prints the command without one.

A new ADR-0020 records the agent command matrix, the actor rule and the refresh. It supersedes the terminal-only parts of ADR-0004 and ADR-0009, and amends ADR-0015 and ADR-0010. Constitution 1.3.0 amends BL-INV-002 ([constitution-amendment.md](constitution-amendment.md)). Decisions R1 to R14 are in [research.md](research.md).

## Technical Context

**Language/Version**: Python ≥ 3.11 standard library only, under `python3 -I -S`.

**Primary Dependencies**: No new runtime dependency. External tools, all already required:

- `git` ≥ 2.41, resolved outside working trees and temp roots (ADR-0005 path);
- `bwrap` and a systemd user session for confined steps;
- the agent CLIs;
- the pinned standard archive from the fixed source (ADR-0001 and ADR-0008 cache).

**Storage**: Operator state only:

- `trusted-source.json` gains `repository` and the `default-branch` source;
- `human-decisions.jsonl` and `mode_history` gain `by: relayed` with `relayed_by`;
- the reviewed record gains a second writer (refresh, adding a pair under an existing repository);
- the `trusted.json` format is unchanged.

See [data-model.md](data-model.md).

**Testing**: `unittest`, offline.

- Stand-in bare repositories through the `setup_trust.repository_url` seam, with the argv log proving which Git commands ran.
- In-process TTY stand-ins (`TTY`) and real `openpty` helpers for prompts.
- Fake agent CLIs for usage-limit output.
- Crash injection before the atomic HD write.
- One networked end-to-end scratch run, recorded in the PR ([quickstart.md](quickstart.md)).

**Target Platform**: The qualified 1.0 host: Linux with a systemd user session, GitHub.

**Project Type**: The global CLI (`tools/ballast`), the install script (`tools/setup`), and the workflow tools (`tools/spec_workflow/`), plus policies, templates, the ADR and the constitution.

**Performance Goals**: An unchanged checkout pays one extra `status --json` call (a digest pass the launcher repeats anyway). The refresh path adds one `ls-remote` and one depth-1 blob-less fetch (bounded at 30 s and 120 s), plus a normal installation, only when protected inputs changed.

**Constraints**:

- Standard library only, `-I -S`.
- Nothing the launcher or refresh executes comes from the checkout: setup and the launcher come from the pinned standard, and Git is resolved outside agent-writable paths.
- No eligibility decision trusts agent-writable data unless a change to it can only make the checkout ineligible.
- No prompt on the refresh path.
- Existing refusal and tamper tests pass unedited.
- Older global CLIs and older pinned standards keep today's behavior (declaration-gated).

**Scale/Scope** (estimates):

| Path | Change |
| --- | --- |
| `setup_trust.py` | about +220 (`refresh_eligible`, `record_refresh`, multi-path `ls-tree`) |
| `launcher.py` | about +120 (provenance fields, `generated_settings`, `merge_permissions`, `_trust` checks, `status` fields, `discard-runs` arguments and Next line, `BALLAST_AGENT_STEP`) |
| `tools/setup` | about +60 (`--refresh`, import of `merge_permissions`) |
| `tools/ballast` | about +60 (trigger, declaration) |
| new `actor.py` | about 120 |
| `run.py` | about +150 (`--relayed-by` parsing, batch arguments, re-entry mapping, usage-limit category, branch offer) |
| `chat.py` | about +200 (batch approval, relayed records, headless step, `mode` terminal, rendering) |
| `autonomy.py` | about +80 (schema, `append_human_decisions`, rendering, recovery texts) |
| `agent.py` | about +40 (`--confined`, usage-limit classification, `BALLAST_AGENT_STEP`) |
| `branch_sync.py` | recovery text |

Docs: one ADR, the constitution, two policies plus their installed mirrors, AGENTS.md and two templates, one skill, README, and the technical spec.

No NEEDS CLARIFICATION remains.

## Constitution Check

*Gate before Phase 0, re-checked after Phase 1. Result: **PASS with one justified amendment** both times. BL-INV-002 is amended as the operator decided in D-02 (HD-0002), through the constitution's governance (R2, recorded reason), not violated silently. See Complexity Tracking.*

| Principle | How the design holds it |
| --- | --- |
| 1. Projects own only their files (BL-INV-001) | All new records are operator state. Regeneration uses the existing installer and ignore rules, and writes nothing new in the checkout. |
| 2. Nothing executes from a writable checkout before trust (BL-INV-002) | **Amended** ([constitution-amendment.md](constitution-amendment.md)). The launcher still refuses until a baseline matches, and the comparison is unchanged. The refresh runs from the pinned standard (setup subprocess, launched by the global CLI), observes the default branch only through the hardened throwaway path, regenerates before recording, and refuses on either marker. `trust` and refresh both refuse generated settings that differ from `ballast.toml` (FR-004). |
| 3. Delegated authority (BL-INV-003) | Agents inside steps still run no `ballast` command (the marker, plus `BALLAST_AGENT_STEP` as defence in depth). The headless Chat step runs under Autonomous confinement, never less. An agent session acts only with the operator's own authority and every decision it relays is labeled. `reject`, `resolve` and `mode` stay at the operator's terminal. `trust` keeps today's terminal-free behavior outside a step and stays refused inside one (D-09). |
| 4. A project picks a version, never a source (BL-INV-004) | The refresh downloads only the pinned ref from the fixed source through the existing verified cache (`ensure_standard`). |
| 5. Postconditions over exit codes (BL-INV-005) | The refresh records only after content checks (installation record, observed blob IDs, generated settings bytes, re-snapshot). Usage-limit classification changes only the stop category, never the postcondition check. Resume into `implement` still runs `validate-implementation` afterwards. |
| 6. Portable, dependency-free tools | Standard library only. `actor.py` is imported from the trusted installed tools, inside the baseline like `chat.py`. |
| 7. Generic by default | No project names. The branch proposal uses the feature directory, and messages are generic. |
| 8. Executable evidence | Every AC maps to a test in [quickstart.md](quickstart.md), including every refusal and tamper path in FR-019 ([contracts/trust-refresh.md](contracts/trust-refresh.md#refusal-and-tamper-tests-required-fr-019-sc-005)). |
| 9. A provisional decision is never human approval (BL-INV-006) | Relayed approvals are refused in Autonomous runs, never rendered as operator-typed, and quote no chat text. This plan, ADR-0020 (proposed until merge) and the amendment are agent-provisional. |

## Architecture Boundaries

- **Affected areas**:
  - the global CLI `tools/ballast` (refresh trigger);
  - the install script `tools/setup` (`--refresh`, shared settings producer);
  - `tools/spec_workflow/setup_trust.py` (refresh eligibility and recording);
  - `tools/spec_workflow/launcher.py` (provenance, settings check in `trust`, `status --json` fields, `discard-runs`, step-environment refusal);
  - new `tools/spec_workflow/actor.py` (actor rule and command matrix);
  - `run.py` (argument parsing, re-entry, stop categories, branch offer);
  - `chat.py` (batch and relayed approvals, headless step, `mode` terminal, rendering);
  - `autonomy.py` (record schemas, atomic append, renderers, recovery texts);
  - `agent.py` (confined flag, usage-limit classification, step environment);
  - `branch_sync.py` (recovery text).
- **Contracts and data flow**:
  - Refresh: `ballast run|ledger|intake` → `tools/ballast` → launcher `status --json` (`refusal_kind`) → [`inputs-changed` or `pin-mismatch` and declared] → `ensure_standard(pin)` → `setup --refresh` (exclusive lock → `refresh_eligible` → `attempt` → `record_refresh` → `record_baseline(default-branch)` → `add_reviewed`) → execv launcher (unchanged comparison) → `run.py` (prints the refresh line).
  - Approvals: `run.py` → `actor.resolve` + `actor.allowed` → `chat` batch approval → `autonomy.append_human_decisions`.
  - Ownership: the launcher owns trust records and the comparison; setup owns the installation and asks `setup_trust`; `actor.py` owns attribution; `autonomy.py` owns decision records and their rendering.
  - Contracts: [trust-refresh.md](contracts/trust-refresh.md), [cli.md](contracts/cli.md).
- **Architecture references**:
  - [constitution](../../.specify/memory/constitution.md) BL-INV-002, BL-INV-003, BL-INV-006 and governance;
  - [ADR-0004](../../docs/adr/0004-autonomous-provisional-decisions.md), [ADR-0005](../../docs/adr/0005-launcher-branch-synchronization.md), [ADR-0008](../../docs/adr/0008-verified-cache-and-update-preview.md), [ADR-0009](../../docs/adr/0009-chat-mode-operator-driven-steps.md), [ADR-0010](../../docs/adr/0010-autonomous-resume-and-bounded-recovery.md), [ADR-0015](../../docs/adr/0015-setup-recorded-trust-baseline.md), [ADR-0016](../../docs/adr/0016-privileged-action-kinds-and-policy-refresh.md) (`--refresh-policy` reads `ballast.toml` only from a `trust` baseline: unchanged, and stated in ADR-0020);
  - [technical spec §37 and §9.1](../TECHNICAL-SPEC.md).
- **Proposed architecture decisions** (agent-provisional; written with the implementation, accepted only when the PR merges):
  1. **ADR-0020 Agent sessions run mechanical commands and relay decisions within the run's autonomy.** It records:
     - the agent command matrix ([cli.md](contracts/cli.md#agent-command-matrix));
     - the actor rule;
     - the default-branch refresh and its conditions;
     - the trust settings check;
     - batch approval, headless Chat steps and the recovery changes;
     - the dependency on Spec Kit engine gates prompting only at a terminal (F-001);
     - residual risks: branch protection is the review of configuration changes for checkouts already trusting the repository; a relayed approval or `--ref` is an unverifiable labeled claim; the terminal test is not proof of a human, since an agent session can allocate a pseudo-terminal (first plan review); `trust` has no terminal test (D-09), so the step boundary alone keeps a confined agent from vouching for its changes; `.venv` changes still need trust; `BALLAST_AGENT_STEP` is not a boundary.
     
     It supersedes in part ADR-0004 (rejected alternative "piping approvals") and ADR-0009 D-1 and D-4. It amends ADR-0015 (third provenance source, reviewed record's second writer, any-bytes refresh for the same repository) and ADR-0010 (re-entry at `implement`).
  2. **Constitution 1.3.0**: BL-INV-002 as in [constitution-amendment.md](constitution-amendment.md).

## Repository Impact

| Path | Change |
| --- | --- |
| `tools/ballast` | Before the launcher for `run`, `ledger` and `intake`: read `status --json`; on `inputs-changed` or `pin-mismatch` with `[setup] refresh`, call `ensure_standard` and run `setup --refresh`; `Declarations.refresh`. |
| `tools/cli.toml` | `[setup] refresh = true`. |
| `tools/setup` | `--refresh` mode; plain setup runs `record_refresh` when `settle` skips and a named-repository baseline exists; `merge_permissions` imported from the launcher; docstring. |
| `tools/spec_workflow/setup_trust.py` | `refresh_eligible()`, `record_refresh()`, multi-path tree observation reusing `_observe_in`, changed-set classification. |
| `tools/spec_workflow/launcher.py` | `merge_permissions` (moved), `generated_settings()`; `record_baseline(..., repository=)`; `refresh_repository()`; `_trust` settings check (no terminal check, D-09), writing `repository`; `status --json` `refusal_kind` and `baseline_commit`; `discard-runs` `--help`, argument refusal and conditional Next line; `BALLAST_AGENT_STEP` refusal; `BALLAST_REFRESHED` hand-off; `RECOVER` text; docstring. |
| `tools/spec_workflow/actor.py` | New: `Actor`, `resolve()`, `allowed()`, the session pattern, the matrix data. |
| `tools/spec_workflow/run.py` | `--relayed-by` on start, resume, continue and approve; batch and `--through` parsing in `_chat_command`; Autonomous and human-gated refusals for relays; `_block_step` maps `validate-implementation` to `implement`; `EXIT_USAGE_LIMIT` maps to `interrupted`; the branch offer in `_start_autonomous`; refresh line output. |
| `tools/spec_workflow/chat.py` | `approve_many()` (batch, all-or-nothing, relayed variant); `mode` needs a terminal and typed text; `step --headless` through confined `_headless`; status, `allowed_actions` and `publish_section` show relayed actors. |
| `tools/spec_workflow/autonomy.py` | `by` and `relayed_by` in human decisions and mode history (validators); `append_human_decisions()`; `new_run(actor=)`; `_mode_lines` and `_resolution_lines` rendering; `RECOVERY` texts for `unfinished-step`, `tamper` and `interrupted` (usage limit). |
| `tools/spec_workflow/agent.py` | `--confined` for Chat headless steps; usage-limit classification without a configured fallback; `EXIT_USAGE_LIMIT`; `BALLAST_AGENT_STEP=1` in every step environment. |
| `tools/spec_workflow/branch_sync.py` | `RECOVERY["protected-input"]` text. |
| `ballast.toml` (this repository) | Unchanged: the comment above `[autonomous]` stays accurate because `trust` keeps working without a terminal (D-09). |
| `docs/adr/0020-agent-sessions-relay-decisions.md` | New; proposed until merge. |
| `docs/adr/0004-…`, `0009-…`, `0010-…`, `0015-…` | One "superseded in part" or "amended by ADR-0020" note beside each affected clause. |
| `.specify/memory/constitution.md` | BL-INV-002, version 1.3.0, history entry. |
| `templates/policies/spec-kit-workflow.md`, `templates/policies/workflow.md`, and their `docs/policies/` mirrors | Agent command matrix, relayed decisions, batch approval, headless Chat step, refresh, recovery texts. |
| `AGENTS.md`, `templates/AGENTS.md`, `templates/init/agents-section.md` | Replace "an agent never runs `ballast run`" with the session and step distinction, plus the relay rules. |
| `templates/skills/ballast-feature-intake/SKILL.md` (and its installed copy) | Handoff: the session runs mechanical commands and relays approvals only in Chat after an in-chat yes. |
| `README.md`, `specs/TECHNICAL-SPEC.md` (§37, §9.1) | Same content in user and architecture form. |
| `tests/test_setup_trust.py`, `test_setup.py`, `test_ballast.py`, `test_spec_workflow.py`, `test_chat_mode.py`, `test_autonomy.py`, `test_autonomous_run.py`, `test_autonomous_recovery.py`, `test_agent_run_ledger.py`, `test_branch_sync.py`, `test_governance.py` | New classes per [quickstart.md](quickstart.md). Existing terminal-less `start`, `resume` and `continue` calls pass `--relayed-by` or the TTY stand-in. Assertions that such calls record `by: operator` change by design (FR-011) and are listed in tasks. No refusal, tamper or validation test is weakened. |

## Feature Artifacts

```text
specs/147-human-gates-are-decisions/
├── discovery.md               # input evidence
├── intent.md
├── spec.md
├── plan.md                    # this file
├── research.md                # Phase 0 decisions R1–R14
├── data-model.md              # provenance, HD and mode-history actors, eligibility, categories
├── contracts/
│   ├── trust-refresh.md       # trigger, setup --refresh, trust settings check, refusal tests
│   └── cli.md                 # agent command matrix, --relayed-by, batch approve, headless step, discard-runs, branch offer
├── quickstart.md              # AC → test map, end-to-end scratch run
├── constitution-amendment.md  # BL-INV-002 text, 1.3.0
├── checklists/
├── autonomous/
├── tasks.md                   # next: speckit-tasks
├── decisions.md               # only if implementation discovers one
└── reviews/
```

**Suggested waves for tasks** (dependencies only; tasks decide the detail):

1. `actor.py` and the record schemas (`autonomy.py`).
2. In parallel: the refresh (launcher, `setup_trust`, setup, `tools/ballast`); relayed and batch approvals plus the headless step (`run.py`, `chat.py`, `agent.py`); the recovery fixes.
3. ADR, constitution, policies and docs.
4. The full gate and the end-to-end scratch run.

**Required reviews** ([review matrix](../../docs/policies/workflow.md#review-triggers)): engineering, security (trust model, agent authority), test, documentation (ADR, policies, public CLI). Cross-provider review is preferred for this R2 change when practical.

**Before merge**: the operator runs `ballast trust` for the changed protected inputs (authorized `operator-trust`) and the end-to-end scratch run (authorized `scratch-repository`).

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
| --- | --- | --- |
| BL-INV-002 amended: a refresh by the operator's `ballast` command may record a baseline from the live default branch for any bytes | IAC-1 as the operator resolved D-02 (option A, HD-0002); governance allows it as R2 with a recorded reason | Option B or C (ADR-0015 unchanged, or non-widening keys only): the #141 `extra_allow` case would still need `ballast trust` |
| The refresh is triggered in the global CLI and runs setup as a subprocess, so a second pre-launcher step joins worktree preparation | Only the global CLI can fetch a newly pinned standard, and only setup may replace `.ballast/spec_workflow` under the exclusive lock | Refreshing in the launcher or `run.py`: no download path, and it would replace the code that is running |
| A terminal-less decision-recording command must name its session (`--relayed-by`) or is refused | FR-011: no relayed action may read as operator-typed, and today a terminal-less `start --mode autonomous` records `by operator` | Inferring sessions from provider environment variables (unreliable, spoofable); silently labeling them `unnamed` (hides which session acted) |
| `ballast run mode` now needs a terminal | Without it, a session could switch a human-gated run to Chat and relay its gates, defeating FR-010 | Leaving `mode` open; tracking how Chat mode was entered (blocks the user story, since `start --mode chat` itself is relayed) |
