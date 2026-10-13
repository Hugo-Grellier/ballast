# Quickstart: validating the Autonomous stop rule decision

## Prerequisites

- Python ≥ 3.11 and `uv`, with `uv sync --locked` done. No network or GitHub access.
- Required statements: [contracts/adr-0020.md](contracts/adr-0020.md).

## Commands

```sh
uv run --locked ruff check && uv run --locked ruff format --check
uv run --locked python -m unittest tests/test_governance.py
uv run --locked python -m unittest tests/test_*.py
```

## Scenarios

`AutonomousStopRuleDocumentTests` in `tests/test_governance.py` covers each row.

| # | AC | Check | Expected |
| --- | --- | --- | --- |
| 1 | AC-001 | Open `docs/adr/0020-autonomous-stop-rule.md`. | Header: Status `accepted`, Feature, Amends naming ADR-0004 and ADR-0010; sections Context, Decision, Consequences, Rejected alternatives. |
| 2 | AC-002 | Stop rule bullet. | The two blocking conditions with their four authority kinds; every other decision a material provisional decision at the top of the PR. |
| 3 | AC-003 | Trusted author bullet. | Stands in for `ready-for-agent`; operator-controlled data only, never the Issue or an agent-writable file. |
| 4 | AC-004 | Limit outcome bullet. | Every limit, in any phase, publishes a Draft PR with open findings, failed checks and unmet criteria `unverified`. |
| 5 | AC-005 | Self-resume bullet. | Runner event, never a human decision; no `block-resolution`; mode, risk, limits, integrations unchanged. |
| 6 | AC-006 | Residual risk bullet. | Decisions concentrated at the merge; material-decision cap with the limit outcome; value left to #151/#153. |
| 7 | AC-007 | ADR-0004. | An `Amended by [ADR-0020]` note on the continuation bullet. |
| 8 | AC-008 | ADR-0010. | `Amended by [ADR-0020]` notes on resume and the fix-loop limit. |
| 9 | AC-009 | ADR-0020 Chat bullet; `git diff main -- docs/adr/0009-*` | "Chat runs are unaffected"; ADR-0009 diff empty. |
| 10 | AC-010 | `templates/policies/spec-kit-workflow.md`, Autonomous runs. | "ADR-0020 in the Ballast repository" after the block table; no restated conditions. |
| 11 | AC-011 | `specs/TECHNICAL-SPEC.md`. | `**Status (#150, …)**` paragraph linking the ADR. |
| 12 | AC-012 | The commands above. | All pass; no test skipped or weakened beyond the existing environment skips. |
| — | FR-009 | `HUMAN_APPROVAL` over every changed document. | No match. |
| — | FR-012 | `git diff --stat main` | Only `docs/adr/`, `templates/policies/spec-kit-workflow.md`, `specs/TECHNICAL-SPEC.md`, `tests/test_governance.py` and `specs/150-autonomous-stop-rule/`. |
