# Ballast project workflow

The merge verdict (`tools/merge_check.py`,
[ADR-0027](../docs/adr/0027-spec-approval-living-specs-merge-verdict.md)) reads
this file from the target branch, never from the PR head. Each key line stands
alone at the start of a line, `Key: GLOB` with one glob; any other form of a
key line makes the file malformed, which gives `HUMAN` for every PR.

## Human-only paths

A PR changing one of these paths always needs a human merge, whatever its risk
and coverage: they are the code and the text of the gate that would merge it,
and the modules the gate helpers import.

Human-only: tools/merge_check.py
Human-only: tools/spec_check.py
Human-only: tools/spec_approval.py
Human-only: tools/pr_body.py
Human-only: tools/admission.py
Human-only: tools/coordinate.py
Human-only: tools/worker.py
Human-only: tools/worktree.py
Human-only: tools/codex.py
Human-only: tools/progress.py
Human-only: tools/cli.py
Human-only: tools/qualify.py
Human-only: tests/parallel.py
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
