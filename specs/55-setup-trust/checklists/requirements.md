# Specification Quality Checklist: Setup trusts a checkout it just installed

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-10-06
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic (no implementation details)
- [x] All acceptance scenarios are defined
- [x] Edge cases are identified
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification

## Notes

- Ballast is a developer CLI, so its commands (`ballast setup`, `ballast trust`, `ballast doctor`, `status --json`), protected paths and operator state are the product's user-facing surface, not implementation detail. The spec names them as the Issue does and leaves the provenance format, comparison code and Git calls to the plan.
- Every acceptance criterion and functional requirement ends with a provenance marker. IAC-1 to IAC-4 are each cited by at least one acceptance criterion, and none is a non-goal.
- D-01, D-02 and D-03 are the operator's settled answers, cited as brief items. D-04 and D-05 are agent-provisional (`[P: D-NN]`). D-06 and D-07 were settled from the Issue.
- The default branch is observed live from the repository pinned in `ballast.toml`, never from a local ref or remote (FR-004, AC-014, AC-015).
- FR-005 and AC-016: a committed `[github] repository` that names another repository must not make a checkout eligible, because otherwise the live observation could be pointed at a repository an agent controls. Only repositories in the operator-state record of reviewed repositories, which only `ballast trust` writes, count.
- Rerun for run 38380ec3: the run ID and the Mode line were updated. Both D-02 narrowings (observing through the pinned repository, and the reviewed-repositories record) are now marked as agent inferences (`[I]`) listed for merge review, not attributed to the operator. The earlier `[P: clarification-1]` marker was replaced because it named no brief decision.
- The spec postcondition (`artifacts.py spec`) and a local traceability script could not be run in this session because the commands needed approval. Markers, AC IDs and IAC coverage were checked by reading the spec; the runner's `validate-spec` step checks them mechanically.
