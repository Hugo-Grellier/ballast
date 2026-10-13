# Implementation Plan: Autonomous runs stop only for in-run authority changes

**Branch**: `feat-150-autonomous-runs-stop-only-for-authority-changes` | **Date**: 2026-10-13 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/150-autonomous-stop-rule/spec.md` (intent agent-provisional, PD-0005, digest in [intent.md](intent.md))

**Risk**: R2, rechecked in [research R9](research.md#r9-risk-recheck). The change amends accepted ADRs on agent authority and the launcher trust model; it changes no executed code. **Mode**: Autonomous run `1d0a2143`. Every decision here is agent-provisional, including the pre-change R2 approval; merging the PR is the only human approval.

## Summary

A documentation-only change that records the Autonomous stop rule as accepted architecture:

1. **ADR-0020** (`docs/adr/0020-autonomous-stop-rule.md`, new) states the stop rule, how today's block categories fall under it, the trusted-author rule, the limit outcome, usage-limit self-resume, the residual risk with its material-decision cap, that Chat runs are unaffected, that BL-INV-003 and BL-INV-006 are unchanged, and that #151–#154 deliver the behavior.
2. **Amendment notes** on ADR-0004 and ADR-0010 point to ADR-0020 for the parts it changes. ADR-0009 is untouched.
3. **References**: one paragraph in the policy template's Autonomous runs section, one status paragraph in the technical spec. Neither restates the rule.
4. **A governance test** pins the required statements, the notes, the references and the absence of approval wording.

## Technical Context

**Language/Version**: Markdown; Python ≥ 3.11 standard library for the test.

**Primary Dependencies**: none new.

**Storage**: N/A. No runtime state, ledger or configuration change.

**Testing**: `unittest`, offline, a new `AutonomousStopRuleDocumentTests` class in `tests/test_governance.py` modelled on `FeatureUiStatesDocumentTests`.

**Target Platform**: the repository's documentation; the policy template ships to projects through the next release.

**Project Type**: decision record and documentation in the Ballast standard.

**Performance Goals**: N/A.

**Constraints**:
- No change to runner, validator, skill or workflow code (FR-012).
- No text states or implies a human approval that did not happen; `HUMAN_APPROVAL` in `autonomy.py` must not match (FR-009, BL-INV-006).
- The ADR is the single authority; the policy and technical spec only reference it (FR-011).
- Shipped template text stays generic: no Ballast Issue numbers, no relative link into `docs/adr/` (constitution principle 7).
- Accepted ADRs are amended by notes, never rewritten (constitution governance, technical spec §55).

**Scale/Scope**: one new ADR (about 60 lines), three amendment notes, one policy paragraph, one technical-spec paragraph, one test class (about 80 lines).

No NEEDS CLARIFICATION remains. Two interpretations are flagged for the plan review rather than decided silently:

- AC-010 names `docs/policies/spec-kit-workflow.md`, which is git-ignored and installed; the plan edits its source, `templates/policies/spec-kit-workflow.md`, and cites the ADR in the template's existing "ADR-NNNN in the Ballast repository" form instead of a Markdown link ([R1](research.md#r1-which-file-carries-the-workflow-policy-reference), [R2](research.md#r2-how-the-policy-cites-adr-0020)).
- FR-002 says a run "blocks only for" two conditions; the plan reads it as governing decisions and keeps `interrupted` and `upstream-sync`, which offer no decision, as technical stops with today's recovery ([R6](research.md#r6-how-the-stop-rule-classifies-todays-blocks)).

## Constitution Check

*Gate before Phase 0, re-checked after Phase 1. Result: **PASS** both times, no violations.*

| Principle | How the design holds it |
| --- | --- |
| 1. Projects own only their files (BL-INV-001) | The installed `docs/policies/` copy is not edited; the template is the source. No new installed or committed project file. |
| 2. Nothing executes from a writable checkout (BL-INV-002) | No executed code changes. ADR-0020 keeps tamper, unfinished-step and protected-input stops blocking. |
| 3. Delegated authority (BL-INV-003) | Every pre-merge authority (run authority, launcher execution, external writes, credentials) still blocks. Trusted authors come only from operator-controlled data. Self-resume keeps mode, risk, limits and integrations. No agent gains authority. |
| 4. A project picks a version, never a source (BL-INV-004) | Nothing is downloaded or fetched. |
| 5. Postconditions over exit codes (BL-INV-005) | `postcondition` stays a blocking runner-enforced invariant. |
| 6. Portable, dependency-free tools | No tool changes; the test uses the standard library. |
| 7. Generic by default | The template paragraph names no Ballast Issue and no project. |
| 8. Executable evidence | `AutonomousStopRuleDocumentTests` maps AC-001 to AC-011; the fast gate is AC-012 ([quickstart](quickstart.md)). |
| 9. A provisional decision is never human approval (BL-INV-006) | ADR-0020 is accepted and agent-provisional until merge; the self-resume event is never a human decision; material decisions are agent-provisional and listed for the merge reviewer. The test checks no `HUMAN_APPROVAL` match. |

## Architecture Boundaries

- **Affected areas**: architecture decisions (`docs/adr/`), the operator workflow policy template, the technical spec, governance tests.
- **Contracts and data flow**: ADR-0020 is the source of truth for when an Autonomous run stops; ADR-0004 and ADR-0010 point to it; the policy template and technical spec reference it. Required statements: [contracts/adr-0020.md](contracts/adr-0020.md). Concepts and authorized transitions: [data-model.md](data-model.md).
- **Architecture references**: [constitution](../../.specify/memory/constitution.md) BL-INV-003, BL-INV-006; [ADR-0004](../../docs/adr/0004-autonomous-provisional-decisions.md); [ADR-0009](../../docs/adr/0009-chat-mode-operator-driven-steps.md); [ADR-0010](../../docs/adr/0010-autonomous-resume-and-bounded-recovery.md); [ADR-0016](../../docs/adr/0016-privileged-action-kinds-and-policy-refresh.md); [R2 boundaries](../../docs/policies/project/workflow.md#r2-boundaries).
- **Proposed architecture decisions** (agent-provisional here; the merge approves them):
  1. **ADR-0020 Autonomous runs stop only for authority that takes effect before merge.** Amends ADR-0004 (when a run blocks) and ADR-0010 (usage-limit resume, the limit block). Content per [contracts/adr-0020.md](contracts/adr-0020.md).

## Repository Impact

| Path | Change |
| --- | --- |
| `docs/adr/0020-autonomous-stop-rule.md` | New ADR-0020, accepted and agent-provisional until merge ([R5](research.md#r5-adr-file-status-and-header), [R6](research.md#r6-how-the-stop-rule-classifies-todays-blocks)). |
| `docs/adr/0004-autonomous-provisional-decisions.md` | One italic amendment note on the continuation bullet ([R7](research.md#r7-amendment-notes-on-adr-0004-and-adr-0010)). |
| `docs/adr/0010-autonomous-resume-and-bounded-recovery.md` | Italic amendment notes on the resume and fix-loop bullets. |
| `templates/policies/spec-kit-workflow.md` | One **Stop rule** paragraph after the block-class table ([R3](research.md#r3-where-the-policy-reference-goes-and-what-it-says)). |
| `specs/TECHNICAL-SPEC.md` | One `**Status (#150, Autonomous stop rule):**` paragraph ([R4](research.md#r4-where-the-technical-spec-references-adr-0020)). |
| `tests/test_governance.py` | New `AutonomousStopRuleDocumentTests` ([R8](research.md#r8-verification)). |

Unchanged: `docs/adr/0009-chat-mode-operator-driven-steps.md`, the constitution, every file under `tools/`, the skills, the workflow definitions, `docs/policies/` (installed), `ballast.toml`, and the existing `test_adr_0010_amends_adr_0004` assertions.

## Feature Artifacts

```text
specs/150-autonomous-stop-rule/
├── intent.md
├── discovery.md
├── spec.md
├── plan.md            # this file
├── research.md        # Phase 0 decisions R1–R9
├── data-model.md
├── contracts/
│   └── adr-0020.md
├── quickstart.md      # validation scenarios mapped to ACs
├── tasks.md           # next: speckit.tasks
├── decisions.md       # only when implementation discovers a decision
├── reviews/
└── autonomous/record.md
```

## Complexity Tracking

No constitution violation; nothing to justify.
