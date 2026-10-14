# Specification Quality Checklist: Human gates are decisions, not command relays

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-10-13
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

- The product is a command-line tool, so `ballast` command names, gate names and file names such as `ballast.toml` are the user-facing surface, not implementation detail. The spec names no module, function, flag for relaying or storage format.
- Traceability: AC-001 to AC-027 each carry a provenance marker; IAC-1 to IAC-8 are all cited by acceptance-criterion markers; `[P: …]` cites only the assumed D-06 and D-07; settled D-01 to D-05 are cited as `[B: D-NN]`.
- These traceability rules were checked by hand against `tools/spec_workflow/artifacts.py`. Running the validator directly was not possible in this session.
- R2: planning must produce the new ADR (superseding parts of ADR-0004 and ADR-0009, amending ADR-0015) and the BL-INV-002 constitution amendment, and must schedule the end-to-end scratch run.
