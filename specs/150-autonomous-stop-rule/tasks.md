---

description: "Task list for #150: Autonomous runs stop only for in-run authority changes"
---

# Tasks: Autonomous runs stop only for in-run authority changes

**Input**: Design documents from `specs/150-autonomous-stop-rule/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/adr-0020.md](contracts/adr-0020.md), [quickstart.md](quickstart.md)

**Risk**: R2, documentation-only (plan, research R9). Autonomous run `1d0a2143`: every decision in this file is agent-provisional; merging the PR is the single human approval. No task changes runner, validator, skill or workflow code (FR-012).

**Acceptance evidence**: Every acceptance criterion maps to a test method in a new `AutonomousStopRuleDocumentTests` class in `tests/test_governance.py`, except AC-012, which the workflow's checks prove (the fast gate is workflow-owned). T014 writes `acceptance-evidence.json`.

**Verification commands**: Each command below runs on its own, with no `&&`, pipe or leading `VAR=value`, in a form `ballast.toml`'s `extra_allow` rules match:

- `uv run --locked python -m unittest tests.test_governance.AutonomousStopRuleDocumentTests`
- `uv run --locked python -m unittest tests.test_governance`
- `uv run --locked ruff check`
- `uv run --locked ruff format --check`
- read-only `git diff` and `git status`

**Test conventions** (follow `FeatureUiStatesDocumentTests`, `tests/test_governance.py:414`): fold whitespace with `" ".join(text.split())` before `assertIn`; one `subTest` per required phrase; resolve relative links with the existing `\]\(([^)#\s]+)(?:#[^)]*)?\)` pattern. Import `autonomy` the way `tests/test_packet.py` does (insert `tools/spec_workflow` on `sys.path`, `import autonomy  # noqa: E402`) to reach `autonomy.HUMAN_APPROVAL`. The class docstring cites `#150` and the ACs it covers. Phrases come from [contracts/adr-0020.md](contracts/adr-0020.md); pin the quoted statements there, not the surrounding prose.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no unmet dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Test and verification tasks cite the acceptance criterion ID(s) they prove.

---

## Phase 1: Setup (Shared Infrastructure)

No setup: the repository, `uv` environment and test module already exist, and the feature adds no dependency.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The test class every story's tests are added to.

- [X] T001 Add an empty `AutonomousStopRuleDocumentTests(unittest.TestCase)` class at the end of `tests/test_governance.py` (before the `if __name__ == "__main__":` block), with `ADR = "docs/adr/0020-autonomous-stop-rule.md"`, a `folded(self, name: str) -> str` helper returning the whitespace-folded text of `ROOT / name`, a `decision_bullet(self, lead: str) -> str` helper returning the folded text of the ADR-0020 `## Decision` bullet that starts with `- **<lead>**` up to the next bullet or section, and the `autonomy` import described under Test conventions

**Checkpoint**: The class exists; story tests can be added.

---

## Phase 3: User Story 1 - Read one authoritative stop rule (Priority: P1) 🎯 MVP

**Goal**: ADR-0020 exists and states the stop rule, the block mapping, the trusted-author rule, the limit outcome, self-resume, the residual risk, Chat runs, the invariants and delivery.

**Independent Test**: `uv run --locked python -m unittest tests.test_governance.AutonomousStopRuleDocumentTests` passes its US1 methods against `docs/adr/0020-autonomous-stop-rule.md`.

### Acceptance tests for User Story 1

> Write these first; they fail until T003 lands.

- [X] T002 [US1] Add to `AutonomousStopRuleDocumentTests` in `tests/test_governance.py`: `test_adr_0020_header_and_sections` [AC-001] (title `# ADR-0020: Autonomous runs stop only for authority that takes effect before merge`; `- Status: accepted (2026-10-13` and `agent-provisional` and `until the operator merges the PR` in the Status line; a `- Risk: R2` line; `- Feature: [150-autonomous-stop-rule](../../specs/150-autonomous-stop-rule/spec.md)`; one `- Amends:` line containing both `[ADR-0004](0004-autonomous-provisional-decisions.md)` and `[ADR-0010](0010-autonomous-resume-and-bounded-recovery.md)`; headings `## Context`, `## Decision`, `## Consequences`, `## Rejected alternatives` in that order); `test_stop_rule` [AC-002] (bullet **Stop rule** contains "takes effect before merge", "run authority", "launcher execution", "external writes", "credentials", "an invariant the runner enforces", "material provisional decision", "top of the PR"); `test_what_still_blocks` [AC-002, SC-003] (bullet **What still blocks** names `credential`, `permission`, `forge`, `ineligible`, `secret-provisioning`, `external-write`, `tamper`, `unfinished-step`, `postcondition`, `decision`, `contradiction`, `limit`, `review-finding`, `interrupted`, `upstream-sync` per research R6); `test_trusted_author` [AC-003] (`ready-for-agent`, "operator-controlled", "never from the Issue or an agent-writable file", "#152"); `test_limit_outcome` [AC-004] ("agent steps", "wall time", "fix cycles", "draft retries", "in any phase", "Draft PR", "open findings", "failed checks", "`unverified`", "#153"); `test_self_resume` [AC-005] ("provider usage limit", "without an operator `block-resolution` record", "runner event", "never a human decision", "mode, risk, limits and integrations", "#154"); `test_residual_risk` [AC-006] ("decisions concentrated at the merge", "material-decision cap", "cap was reached", "#151", "#153"); `test_invariants_and_delivery` [FR-008, FR-012] ("BL-INV-003 and BL-INV-006", "no constitution amendment", "#151, #152, #153 and #154"); `test_no_human_approval_wording` [FR-009] (`autonomy.HUMAN_APPROVAL.search` on the ADR-0020 text is `None`); `test_adr_0020_links_resolve` [AC-001] (every non-URL relative link in ADR-0020 exists) (depends on T001)

### Implementation for User Story 1

- [X] T003 [P] [US1] Write `docs/adr/0020-autonomous-stop-rule.md` per [contracts/adr-0020.md](contracts/adr-0020.md) and research R5–R6: the header lines in contract order (Status accepted 2026-10-13 with the change for #150, agent-provisional in Autonomous run `1d0a2143` until the operator merges the PR; Risk R2; Feature link; Amends ADR-0004 and ADR-0010 on one line); `## Context` (ADR-0004 and ADR-0010 still stop the run for clarify without a safe default, `ready-for-agent`, run limits and usage-limit resume; the operator's goal is Issue plus merge); `## Decision` with bold-lead bullets **Stop rule**, **What still blocks** (the R6 mapping in five groups), **Trusted author**, **Limit outcome**, **Self-resume**, **Residual risk**, **Chat runs** ("Chat runs are unaffected": they record no provisional decision and every Chat gate needs the operator; ADR-0009 stands), **Invariants**, **Delivery**; `## Consequences` (more decisions reach the merge reviewer, listed at the top of the PR; the cap bounds them; the policy and technical spec point here; until #151–#154 ship, today's blocks apply); `## Rejected alternatives` (status `proposed`; a superseding ADR; restating the rule in the policy). No wording that `autonomy.HUMAN_APPROVAL` matches, e.g. no "human-approved" or "approved by the operator"
- [X] T004 [US1] Run `uv run --locked python -m unittest tests.test_governance.AutonomousStopRuleDocumentTests` and fix `docs/adr/0020-autonomous-stop-rule.md` until every US1 method passes, without loosening an assertion [AC-001, AC-002, AC-003, AC-004, AC-005, AC-006] (depends on T002, T003)

**Checkpoint**: ADR-0020 is complete and verified on its own.

---

## Phase 4: User Story 2 - Trace the amended decisions (Priority: P1)

**Goal**: ADR-0004 and ADR-0010 point forward to ADR-0020; ADR-0009 is untouched.

**Independent Test**: The US2 methods of `AutonomousStopRuleDocumentTests` pass, and `git diff main -- docs/adr/0009-chat-mode-operator-driven-steps.md` is empty.

### Acceptance tests for User Story 2

- [X] T005 [US2] Add to `AutonomousStopRuleDocumentTests` in `tests/test_governance.py`: `test_adr_0004_note` [AC-007] (the folded ADR-0004 text contains `*Amended by [ADR-0020](0020-autonomous-stop-rule.md):` inside the "Continuation as a gate-only workflow" bullet, and the note names when an Autonomous run blocks); `test_adr_0010_notes` [AC-008] (ADR-0010 contains two `*Amended by [ADR-0020](0020-autonomous-stop-rule.md):` notes, one in the "Autonomous resume" bullet naming "provider usage limit" and "`block-resolution`", one in the "Bounded fix loop" bullet naming "Draft PR"); `test_chat_runs_unaffected` [AC-009] (bullet **Chat runs** of ADR-0020 contains "Chat runs are unaffected" and "every Chat gate needs the operator"; `docs/adr/0009-chat-mode-operator-driven-steps.md` contains no `0020`). Leave the existing `test_adr_0010_amends_adr_0004` unchanged (depends on T002)

### Implementation for User Story 2

- [X] T006 [P] [US2] Append one italic note `*Amended by [ADR-0020](0020-autonomous-stop-rule.md): …*` to the "Continuation as a gate-only workflow" bullet in `docs/adr/0004-autonomous-provisional-decisions.md`, saying ADR-0020 narrows when an Autonomous run blocks; change nothing else (research R7)
- [X] T007 [P] [US2] Append italic `*Amended by [ADR-0020](0020-autonomous-stop-rule.md): …*` notes to the "Autonomous resume" bullet (a run stopped by a provider usage limit resumes without an operator `block-resolution` record) and to the "Bounded fix loop" bullet (an exhausted limit publishes a Draft PR instead of blocking) in `docs/adr/0010-autonomous-resume-and-bounded-recovery.md`; change nothing else (research R7)
- [X] T008 [US2] Run `uv run --locked python -m unittest tests.test_governance` and `git diff main -- docs/adr/0009-chat-mode-operator-driven-steps.md` (expect empty); fix the notes until the US2 methods and the existing `PolicyWordingTests.test_adr_0010_amends_adr_0004` pass [AC-007, AC-008, AC-009] (depends on T003, T005, T006, T007)

**Checkpoint**: Both amended records trace to ADR-0020; ADR-0009 unchanged.

---

## Phase 5: User Story 3 - Find the rule from the workflow policy and the technical spec (Priority: P2)

**Goal**: The policy template and technical spec reference ADR-0020 without restating it.

**Independent Test**: The US3 methods of `AutonomousStopRuleDocumentTests` pass.

### Acceptance tests for User Story 3

- [X] T009 [US3] Add to `AutonomousStopRuleDocumentTests` in `tests/test_governance.py`: `test_policy_cites_adr_0020` [AC-010] (in `templates/policies/spec-kit-workflow.md`, the `## Autonomous runs` section has a paragraph starting `**Stop rule.**` placed after the block-class table, containing "ADR-0020 in the Ballast repository" and "later Ballast releases"; the section does not contain "takes effect before merge" and the paragraph has no `](` link into `docs/adr/` or `../`; the template names no `#150`–`#154`); `test_technical_spec_links_adr_0020` [AC-011] (`specs/TECHNICAL-SPEC.md` has a paragraph starting `**Status (#150, Autonomous stop rule):**` containing `(../docs/adr/0020-autonomous-stop-rule.md)` and "#151", "#154", placed after the paragraph ending "may still block a run.", and not containing "takes effect before merge"); extend `test_no_human_approval_wording` [FR-009] to every changed document: ADR-0020, the ADR-0004 and ADR-0010 notes, the policy paragraph and the technical-spec paragraph (depends on T005)

### Implementation for User Story 3

- [X] T010 [P] [US3] Add one paragraph starting `**Stop rule.**` right after the block-class table in `## Autonomous runs` of `templates/policies/spec-kit-workflow.md`: ADR-0020 in the Ballast repository is the authority for when an Autonomous run stops; later Ballast releases deliver it; the blocks, limits and resume this section describes apply until then. Do not restate the rule's conditions, link `docs/adr/`, or name a Ballast Issue number; do not edit `docs/policies/spec-kit-workflow.md` (research R1–R3)
- [X] T011 [P] [US3] Add a `**Status (#150, Autonomous stop rule):**` paragraph right after the paragraph ending "Technical failures, conflicts, exhausted limits and unavailable authority may still block a run." in `specs/TECHNICAL-SPEC.md`: link [ADR-0020](../docs/adr/0020-autonomous-stop-rule.md), say the decision is accepted and agent-provisional until the PR merges, and that #151–#154 deliver it; do not rewrite §37 or the existing paragraph (research R4)
- [X] T012 [US3] Run `uv run --locked python -m unittest tests.test_governance` and fix the two paragraphs until the US3 methods and the existing policy tests (`GovernanceTests`, `PolicyWordingTests`, `ChatGovernanceTests`, `LocalFallbackDocumentTests.test_links_resolve`) pass [AC-010, AC-011] (depends on T009, T010, T011, T008)

**Checkpoint**: All three stories verified.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T013 Run `uv run --locked ruff check` and then `uv run --locked ruff format --check`, fix `tests/test_governance.py` until both pass, then run `git diff --stat main` and `git status` and confirm only `docs/adr/0004-autonomous-provisional-decisions.md`, `docs/adr/0010-autonomous-resume-and-bounded-recovery.md`, `docs/adr/0020-autonomous-stop-rule.md`, `templates/policies/spec-kit-workflow.md`, `specs/TECHNICAL-SPEC.md`, `tests/test_governance.py` and `specs/150-autonomous-stop-rule/` changed [FR-012, AC-012] (depends on T012)
- [X] T014 Write `specs/150-autonomous-stop-rule/acceptance-evidence.json` with `schema_version` 1, `spec_digest` the sha256 of `specs/150-autonomous-stop-rule/spec.md`, and `criteria` mapping AC-001 → `tests.test_governance.AutonomousStopRuleDocumentTests.test_adr_0020_header_and_sections` and `.test_adr_0020_links_resolve`; AC-002 → `.test_stop_rule`, `.test_what_still_blocks`; AC-003 → `.test_trusted_author`; AC-004 → `.test_limit_outcome`; AC-005 → `.test_self_resume`; AC-006 → `.test_residual_risk`; AC-007 → `.test_adr_0004_note`; AC-008 → `.test_adr_0010_notes`; AC-009 → `.test_chat_runs_unaffected`; AC-010 → `.test_policy_cites_adr_0020`; AC-011 → `.test_technical_spec_links_adr_0020`; AC-012 → `[]` (the workflow's fast gate proves it) (depends on T013)
- [X] T015 Fix cycle 1 (engineering review F-001, F-002): in the **What still blocks** bullet of `docs/adr/0020-autonomous-stop-rule.md`, give the limit outcome to a high or critical finding or a non-approved verdict at plan review or spec reconciliation (no fix cycle, so spent at once) and to a failed final `run-checks`, and state that a failed `[checks]` command is not a `postcondition`; append a third `*Amended by [ADR-0020](0020-autonomous-stop-rule.md): …*` note to ADR-0010's Consequences sentence "a run that runs out blocks and continues human-gated"; extend `test_what_still_blocks` and make `test_adr_0010_notes` expect three notes, one on that Consequences sentence naming "Draft PR"; rerun `uv run --locked python -m unittest tests.test_governance`, `uv run --locked ruff check` and `uv run --locked ruff format --check` [SC-003, AC-002, AC-008] (depends on T014)
- [X] T016 Fix cycle 3 (engineering review F-001): in the **Self-resume** bullet of `docs/adr/0020-autonomous-stop-rule.md`, state that a self-resume counts as a block resolved during the run for [ADR-0019](../../docs/adr/0019-autonomous-pr-completion.md) condition (11), so the run's PR stays a Draft; extend `test_self_resume` with "condition (11)" and "stays a Draft" [SC-003, AC-005] (depends on T015)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: none.
- **Foundational (Phase 2)**: T001 blocks every story's test task.
- **User stories**: each story's documents are independent files; their tests share `tests/test_governance.py`, so test tasks run in sequence (T002 → T005 → T009) to avoid edit conflicts.
- **Polish**: after all stories.

### User Story Dependencies

- **US1 (P1)**: after T001. No dependency on another story.
- **US2 (P1)**: notes link ADR-0020, so its verification (T008) needs T003; its edits (T006, T007) are independent.
- **US3 (P2)**: its edits (T010, T011) are independent; its verification (T012) runs after T008 so the whole module is green.

### Within Each Story

- Tests are written first and fail until the documents land.
- Verification closes each story.

## Execution Wave DAG

| Wave | Tasks | Waits for |
| --- | --- | --- |
| 1 | T001, T003, T006, T007, T010, T011 | — |
| 2 | T002 | T001 |
| 3 | T004, T005 | T002 (+ T003 for T004) |
| 4 | T008, T009 | T005 (+ T003, T006, T007 for T008) |
| 5 | T012 | T008, T009, T010, T011 |
| 6 | T013 | T012 |
| 7 | T014 | T013 |
| 8 | T015 | T014 |

```text
T001 ─▶ T002 ─▶ T005 ─▶ T009 ─┐
          │       │           ├─▶ T012 ─▶ T013 ─▶ T014
T003 ─────┼─▶ T004│           │
          │       ▼           │
T006 ─────┼──▶  T008 ─────────┤
T007 ─────┘                   │
T010 ─────────────────────────┤
T011 ─────────────────────────┘
```

(T003 feeds T004 and T008.)

## Parallel Opportunities

- Wave 1: the ADR, both amendment notes, the policy paragraph and the technical-spec paragraph are separate files and need nothing but the contract: T003, T006, T007, T010, T011 together with T001.
- Test tasks share one file and stay sequential.

## Implementation Strategy

### MVP (User Story 1)

T001 → T002 + T003 → T004: ADR-0020 alone gives the sibling leaves #151–#154 their accepted architecture (SC-001, SC-003).

### Incremental delivery

1. US1: ADR-0020 verified.
2. US2: amendment notes, so ADR-0004 and ADR-0010 stop being a second source of truth.
3. US3: discoverability from the policy and technical spec.
4. Polish: lint, scope check, acceptance evidence. The fast gate, reviews, converge and spec reconciliation are workflow-owned and not tasks here.

## Notes

- Amend accepted ADRs by notes only; never rewrite their Status or Decision text.
- If implementation finds a conflict with the spec (for example the AC-010 citation form or the R6 reading of FR-002), record it in `specs/150-autonomous-stop-rule/decisions.md` instead of changing the spec.
