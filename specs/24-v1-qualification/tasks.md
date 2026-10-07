# Tasks: Qualify the Ballast 1.0 request-to-PR path

**Spec**: [spec.md](spec.md) · **Plan**: [plan.md](plan.md) · **Evidence**: [qualification.md](qualification.md)

## Wave 1 (independent)

- [X] T001 Run the full local gate and ruff on the qualified host and record the test count, skip count and every mandatory-on-host test (AC-003)
- [X] T002 Create the private disposable repository with `ballast init --ref v0.9.0`, the copy-once GitHub files and a `[demo]` scenario; trust; file and intake two Issues (AC-001)
- [X] T003 Check the LoreForge adoption branch state and its own gate; preview the move to v0.9.0 (AC-001)

## Wave 2

- [X] T004 P1: an Autonomous run of blank Issue #1 to a Draft PR, from a fresh worktree; record any block and its resolution (depends on T002) (AC-001, AC-002 D1, D7b)
- [X] T005 P2: a Chat run of blank Issue #2 to a Draft PR in a real pty; run #20's P-3, P-4 and P-5 (depends on T002) (AC-001)
- [X] T006 Request the UI demo on P1's PR, refresh the packet, and reproduce it locally (#22 SC-001 and SC-004) (depends on T004) (AC-001)
- [X] T007 P3: the local fallback drill with a stand-in quota failure (depends on T002) (AC-002 D6)
- [X] T008 Re-pin LoreForge's adoption branch to v0.9.0 through a failed and then a successful setup (depends on T003) (AC-001, AC-002 D2)

## Wave 3

- [X] T009 P4: a LoreForge Issue run from a fresh worktree to a Draft PR, including the operator's own full gate (depends on T008) (AC-001, AC-002 D7c)
- [X] T010 Drills on dedicated runs: stale resume, conflict at sync, fetch failure and a killed wrapper (depends on T002) (AC-002 D3, D4, D5, D7a)
- [X] T011 File each defect as an Issue with a milestone decision, and link it (#111, #112, #113, #114)

## Wave 4

- [X] T012 Write the release checklist: v1.0 issues, specs, ADRs, required checks read with `gh api`, operator-only steps (depends on T011) (AC-004)
- [X] T013 Get an independent review of the evidence and fix its findings (depends on T001 to T012)
- [X] T014 Open the PR, with `Refs #24` and blockers unless every AC passes (depends on T013): #115
