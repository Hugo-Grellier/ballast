# Project workflow

Ballast's merge verdict (`ballast merge-check`) reads this file from the target
branch, never from the PR head, so a PR cannot remove its own exclusion;
`spec_check.py` reads the checkout's copy for its informational uncovered list.
Copy it to `project/workflow.md` at the repository root (not
`docs/policies/project/`). Each key line stands alone at the start of a line,
`Key: GLOB` with one glob; a key line of any other form, or a file without any
key line, is malformed, which gives `HUMAN` for every PR. For `merge-check`, key
lines inside code fences are ignored. Without this file every PR, R0 included, gets `HUMAN`.

## Human-only paths

A PR changing one of these paths always needs a human merge, whatever its risk
and coverage. List your own R2 surfaces (access rules, destructive migrations,
secrets, deployment and CI permissions) and the code and text that define the
gate, including every file CI executes or imports: any of them can turn the
required checks green. Matching ignores case. To keep a human merge for every
PR, list `Human-only: **` and nothing else is needed.

Human-only: .github/**
Human-only: AGENTS.md
Human-only: CLAUDE.md
Human-only: project/workflow.md
Human-only: docs/policies/**
Replace or delete the next line: left as is, the file is malformed and every PR
gets `HUMAN`.

Human-only: [YOUR R2 SURFACE GLOB]

## Coverage-exempt paths

A changed path needs a `Covers:` glob of a living spec in `docs/specs/` unless it
matches one of these. Human-only paths stay human-only even when exempt.

Coverage-exempt: tests/**
Coverage-exempt: docs/**
Coverage-exempt: README.md
Coverage-exempt: LICENSE
