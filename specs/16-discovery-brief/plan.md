# Implementation Plan: Source-backed discovery brief

**Branch**: `feat/16-discovery-brief` | **Date**: 2026-10-05 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/16-discovery-brief/spec.md` (agent-provisional intent PD-0003; Issue #16).

**Risk**: R1, re-checked at this gate (see [Risk re-check](#risk-re-check)).

## Summary

Add a `discover` step between the scope decision and `speckit.specify` in both `ballast-feature` and `ballast-autonomous`. A new extension command, `speckit.ballast.discover`, writes `specs/<N>-<slug>/discovery.md`: a non-authoritative brief in which every item carries a provenance marker (`[S: …]`, `[I]`, `[O: D-NN]`, `[P: D-NN]`) and every high-impact decision is `settled` by a source, left `open` (human-gated), `assumed` (Autonomous, safe and reversible) or blocks the run. A trusted `artifacts.py discovery` check validates the brief, asks all open questions in one failed-validation round that the operator answers by editing the brief and resuming, attributes answers to the operator through operator state, and counts rounds and questions. Autonomous assumptions reuse the existing `clarification` decision point, so they reach `record.md` and the Draft PR unchanged. `check_spec` gains a traceability rule for features that went through discovery: every acceptance criterion carries a marker and every Issue acceptance criterion (`IAC-n`) is covered or a non-goal. The runner's Issue snapshot gains the Issue comments and is also written at human-gated start. Intent stays bound to `spec.md` alone.

## Technical Context

**Language/Version**: Python 3.13 standard library only; workflow tools run under `python3 -I -S` (constitution principle 6).

**Primary Dependencies**: Spec Kit CLI ≥ 1.0.11 (workflow engine, extension commands); `gh` on the operator side for the Issue snapshot; no new dependency.

**Storage**: Files. `specs/<N>-<slug>/discovery.md` (committed); `.specify/workflow-state/issues/<N>.md` (runner-written, ignored); `launcher.state_dir()/discovery/<sha256(feature)>.json` (operator state, unreachable by agents).

**Testing**: `unittest` (`tests/test_*.py`), fixture repositories and fake `gh`/agent scripts already in `tests/fixtures/autonomy/`.

**Target Platform**: Linux with a systemd user session for workflow runs (unchanged); validators and unit tests run anywhere Python 3.13 runs.

**Project Type**: CLI tooling plus installed workflow templates, policies and agent commands.

**Performance Goals**: None beyond today's: `validate-discovery` reads one brief and one snapshot; the snapshot stays within the existing 60,000-character cap.

**Constraints**: No new agent permission, protected input or launcher trust input (FR-016, BL-INV-003). Only `ballast.toml`, the constitution, `docs/policies/project/` and copy-once files are project-owned (BL-INV-001); the brief is a feature artifact like `spec.md`. No text may present an agent decision as human approval (BL-INV-006). Validators fail closed (BL-INV-005).

**Scale/Scope**: One new command, one new check, one extended check, two workflow edits, one runner change, documentation; roughly 400–600 lines of Python and tests.

All open points from the spec's `[I]` assumptions are resolved in [research.md](research.md) (R-01 to R-09).

## Constitution Check

*Pre-research and post-design; both pass.*

| Principle | Assessment |
| --- | --- |
| 1. Projects own only their own files (BL-INV-001) | Pass. New installed files (`speckit.ballast.discover.md`, workflow versions) are under the existing git-ignored `.specify/` install paths; no ignore-block or install-path change. `discovery.md` is a feature artifact committed like `spec.md`. |
| 2. Nothing executes from a writable checkout before trust (BL-INV-002) | Pass. The new check runs as `python3 -I -S .ballast/spec_workflow/artifacts.py`, a protected, trusted input; the human-gated snapshot is written by `run.py` after the launcher's trust check. |
| 3. Delegated authority (BL-INV-003) | Pass. The discover agent gets the same permissions as `specify`. Operator answers are attributed through operator state no agent can write (R-02). |
| 4. A project picks a version, never a source (BL-INV-004) | Pass. No change to fetch or ref rules. The Issue read uses the `[github] repository` already pinned in `ballast.toml`. |
| 5. Postconditions over exit codes (BL-INV-005) | Pass. `discover` is followed by `validate-discovery` (and `record-discovery` in Autonomous); `specify` is followed by the extended `spec` check. |
| 6. Portable, dependency-free tools | Pass. Stdlib only. |
| 7. Generic by default | Pass. The command and brief format carry no project names; project policies are read through `docs/policies/project/`. |
| 8. Executable evidence | Pass with tasks: refusal paths (unmarked item, pre-filled answer, changed question, missing brief after `ran`, uncovered `IAC-n`, write outside `<f>/`, approval wording) each get a failing-when-broken test. |
| 9. A provisional decision is never human approval (BL-INV-006) | Pass. Autonomous assumptions are recorded as `clarification` PDs; `[P:]` vs `[O:]` markers keep them apart; `HUMAN_APPROVAL` wording is refused in the brief. |

No violation; Complexity Tracking is empty.

### Risk re-check

The spec's risk note asks this gate to re-check R2 triggers in `docs/policies/project/workflow.md`:

- Headless-agent permission model (`claude-settings.json`, wrapper argv, protected inputs, tamper handling): unchanged.
- Launcher trust model: unchanged; operator state gains a `discovery/` subdirectory in the existing state directory, written only by the trusted validator, like `approvals/` (#29).
- What `ballast` executes or downloads (fixed repository, ref rules, fetch path): unchanged. The human-gated start now reads the run's Issue and comments with `gh`, which the Draft PR checkpoint already does for human-gated runs (`draft_pr.py`); this is not the standard's fetch path.
- Ignore block and install paths: unchanged.

Risk stays **R1**. The plan reviewer should confirm the reading of the `gh` Issue read (research R-01).

## Architecture Boundaries

- **Affected areas**: workflow definitions (`templates/spec-kit/workflows/feature`, `.../autonomous`); the `ballast` Spec Kit extension (`templates/spec-kit/extensions/ballast/`); trusted validators (`tools/spec_workflow/artifacts.py`); runner and Issue snapshot (`tools/spec_workflow/run.py`, `tools/spec_workflow/autonomy.py`); Spec Kit spec template; the shipped workflow policy and technical spec.
- **Contracts and data flow**: runner (operator) → Issue snapshot (untrusted data) → `discover` agent → `discovery.md` (+ Autonomous drafts) → `record-discovery` (Autonomous, trusted) → `validate-discovery` (trusted, operator state) → `specify` agent reads the brief → `validate-spec` (trusted, traceability) → clarify → intent bound to `spec.md` only. The brief never flows past specification as a requirement source (FR-013). Contracts: [discovery-brief.md](contracts/discovery-brief.md), [discover-command.md](contracts/discover-command.md), [workflow-and-validator.md](contracts/workflow-and-validator.md).
- **Architecture references**: [`specs/TECHNICAL-SPEC.md` §9.1](../TECHNICAL-SPEC.md#91-v10-target) (request discovery); [Autonomous core](../27-autonomous-core/spec.md) (provisional decisions, blocks, record); `docs/policies/spec-kit-workflow.md` "Workflow runner contract" and "Autonomous runs"; constitution BL-INV-003, -005, -006.
- **Proposed architecture decisions**: None needing an ADR. The choice to reuse the `clarification` point (R-03) and the failed-validation question round (R-02) follow existing patterns.

## Design

### Human-gated flow (`ballast-feature` 1.2.0)

```text
preflight → scope-gate → discover → validate-discovery
   (open decisions? → fail once with all questions → operator fills Answers → ballast run resume)
→ specify (from discovery.md) → validate-spec (+ traceability) → clarify (no re-ask)
→ validate-clarified-spec → approve-intent → …unchanged
```

### Autonomous flow (`ballast-autonomous` 1.1.0)

```text
autonomous-preflight → decide-scope → record-scope → discover
   (unsafe gap → block.json, RECONCILE_STATUS: BLOCKED_DECISION → run stops)
→ record-discovery (record-decision --point clarification)
→ validate-discovery → specify → validate-spec (+ traceability)
→ clarify → record-clarifications → …unchanged
```

### Code changes

1. **`autonomy.py`**: `render_issue_snapshot` takes the comment list and renders `## Comments` within the cap (contract); a helper reads the Issue and its comments for one number with the existing `_gh`/`_gh_list` and `repository()`. The Autonomous start passes the comments it already lists.
2. **`run.py`**: human-gated `start` reads `feature_directory` from its inputs, derives `<N>`, writes the snapshot, or an "could not be read" snapshot on any `AutonomyError`/missing `gh`, before launching the workflow. No token reaches the engine (unchanged `TOKEN_VARIABLES` handling).
3. **`artifacts.py`**:
   - `check_discovery(feature)`: brief parser (sections, list items, markers, `D-NN` blocks, `IAC-n`), mode-specific rules, operator-state round handling, metrics rewrite (human-gated), Autonomous write-boundary check via `autonomy.git status --porcelain`. Registered in `CHECKS` as `discovery`.
   - `check_spec`: when `_discovery_ran(feature)`, apply the traceability rules; reuse the brief parser.
   - Small shared helpers for the operator-state file, following `_approval_path`.
4. **`speckit.ballast.discover.md`** (new) and `extension.yml` (command entry; description no longer Autonomous-only); **`speckit.ballast.clarify.md`**: do not reopen a decision the brief settled or assumed.
5. **Workflows**: add the steps and `input.args` above; bump versions.
6. **`templates/spec-kit/templates/spec-template.md`**: a comment stating the marker convention and the `IAC-n` coverage rule.

### Documentation

- `templates/policies/spec-kit-workflow.md`: lifecycle diagrams (both modes), runner-contract table row for `discover`, the question round, the Autonomous table, the snapshot now holding comments and being written at human-gated start.
- `specs/TECHNICAL-SPEC.md`: workflow description where it lists the steps (only the affected section).
- `CHANGELOG.md` is generated by Release Please; no manual entry.

The installed `docs/policies/` copy in this repository is rebuilt from the pinned version and is not edited.

## Requirement coverage

| Requirement | Where |
| --- | --- |
| FR-001, AC-001 | Workflow steps; `check_discovery` required sections |
| FR-002 | Command reads list; review |
| FR-003, FR-004, AC-002 | Brief contract; marker rule in `check_discovery` |
| FR-005, AC-003 | Snapshot header (existing) and comments as data; command "Never"; approval-wording refusal |
| FR-006, AC-004 | Decision rules; Autonomous `contradiction` block |
| FR-007, AC-005 | `settled` status with source; command procedure |
| FR-008, AC-006, AC-007, AC-009 | Failed-validation round; clarify instruction; no-open pass |
| FR-009, AC-010–AC-012 | Command procedure; `record-discovery`; Autonomous rules in `check_discovery`; existing block contract |
| FR-010, AC-008, AC-013 | Operator-state attribution; `[O:]`/`[P:]` rules; `HUMAN_APPROVAL` refusal |
| FR-011, FR-012, AC-014–AC-016 | `check_spec` traceability (ACs and `IAC-n`); FR markers by review |
| FR-013, AC-017, AC-018 | Evidence marker and authority note; `check_intent` unchanged |
| FR-014, AC-019 | Brief edge-case section; plan and spec-reconciliation review |
| FR-015, AC-020 | Question metrics from operator state / recorded PDs |
| FR-016 | No permission change; Autonomous write-boundary check |
| FR-017 | Command step 4 (decomposition block) |

## Repository Impact

| Path | Change |
| --- | --- |
| `tools/spec_workflow/artifacts.py` | New `discovery` check; extended `check_spec`; operator-state helper |
| `tools/spec_workflow/autonomy.py` | Snapshot with comments; Issue reader |
| `tools/spec_workflow/run.py` | Human-gated snapshot at start |
| `templates/spec-kit/extensions/ballast/commands/speckit.ballast.discover.md` | New |
| `templates/spec-kit/extensions/ballast/extension.yml` | Register command |
| `templates/spec-kit/extensions/ballast/commands/speckit.ballast.clarify.md` | No re-ask rule |
| `templates/spec-kit/workflows/feature/workflow.yml`, `.../autonomous/workflow.yml` | New steps, args, versions |
| `templates/spec-kit/templates/spec-template.md` | Marker convention comment |
| `templates/policies/spec-kit-workflow.md`, `specs/TECHNICAL-SPEC.md` | Documentation |
| `tests/test_discovery.py` (new), `tests/test_spec_workflow.py`, `tests/test_autonomy.py`, `tests/test_autonomous_artifacts.py`, `tests/test_autonomous_run.py` | Tests; workflow step lists and fake-agent maps gain `discover` |

## Feature Artifacts

```text
specs/16-discovery-brief/
├── intent.md
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── discovery-brief.md
│   ├── discover-command.md
│   └── workflow-and-validator.md
├── checklists/requirements.md
├── autonomous/record.md
├── tasks.md           # next step
├── decisions.md       # only when implementation discovers a decision
└── reviews/
```

This feature's own run started before the discover step existed, so it has no `discovery.md` and is not retrofitted (PD-0002).

## Complexity Tracking

No constitution violation to justify.
