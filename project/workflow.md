# Ballast project workflow

The merge verdict (`tools/merge_check.py`,
[ADR-0027](../docs/adr/0027-spec-approval-living-specs-merge-verdict.md)) reads
this file from the target branch, never from the PR head. Each key line stands
alone at the start of a line, `Key: GLOB` with one glob; a key line of any
other form, or a file without any key line, is malformed, which gives `HUMAN`
for every PR. Key lines inside code fences are ignored.

## Human-only paths

A PR changing one of these paths always needs a human merge, whatever its risk
and coverage: they are the code and the text of the gate that would merge it,
and every file CI executes: all of `tools/` (the gate helpers and every
module the tests import) and all of `tests/`. Any file CI runs or imports can
end the run early (`os._exit(0)` at import) and turn the required checks
green, so a narrower rule by file name would not close that. Matching ignores
case.

Human-only: tools/**
Human-only: tests/**
Human-only: .github/**
Human-only: project/workflow.md
Human-only: AGENTS.md
Human-only: CLAUDE.md
Human-only: docs/issue-workflow.md
Human-only: docs/pair-review.md
Human-only: docs/standalone.md
Human-only: docs/execution.md
Human-only: docs/model-routing.md
Human-only: docs/adr/**
Human-only: templates/policies/**
Human-only: templates/skills/ballast-*/**

## Coverage-exempt paths

A changed path needs a `Covers:` glob of a living spec unless it matches one of
these. Human-only paths stay human-only even when exempt.

Coverage-exempt: tests/**
Coverage-exempt: docs/**
Coverage-exempt: specs/**
Coverage-exempt: README.md
Coverage-exempt: LICENSE
