# Plan: Qualify the Ballast 1.0 request-to-PR path

**Spec**: [spec.md](spec.md) · **Risk**: R1 (integration evidence)

## Approach

Run the released CLI (v0.9.0, installed at the operator's `~/.local/bin`) exactly as an operator would, on the qualified host, and record what happens. Nothing in this repository changes except this feature directory.

| Pilot | Repository | Mode | Feature |
| --- | --- | --- | --- |
| P1 | new private `Hugo-Grellier/ballast-qual-blank-20261007`, created with `ballast init --ref v0.9.0` | Autonomous | Issue #1: undo a mistaken click (page button + library method); the UI demo is requested on its PR |
| P2 | same | Chat | Issue #2: a readable text form for `Counter` |
| P3 | same | human-gated with `--local-fallback qwen3:4b-16k` | drill feature: a fake `claude` that reports a usage limit forces the fallback |
| P4 | LoreForge, adoption branch `chore/adopt-ballast` re-pinned to v0.9.0 | Autonomous | Issue #126: an unauthenticated health and version probe |

Recovery drills run against P1 to P4 or against dedicated drill runs (`6-drill`, `7-drill`) in the blank repository, so a drill never risks a pilot's PR.

## Constraints that shape the drills

- No push to an existing default branch. A "base advances while the run is paused" drill therefore uses a second branch of the disposable repository as the run's base: the run starts while that branch is the repository default (so it is pinned as the base), the default goes back to `main`, and the base branch then advances with ordinary pushes to a non-default branch.
- No ruleset change: the checklist reads the configuration and lists the missing ruleset as an operator action.
- Interactive Chat steps run in a private `tmux` server (real pty); gate answers in human-gated runs go through the gate driver's answers file only after the artifact was read.

## Workflow

The Spec Kit assess workflow is not used for this issue: its output (a problem definition and shaped concept) does not fit an evidence-gathering release qualification, and running `ballast run` on this repository would need a v0.9.0 setup of the Ballast worktree itself, which the qualification does not test. The spec, plan and tasks are written by hand from the issue ([DEC-0001](decisions.md#dec-0001-spec-plan-and-tasks-written-by-hand-instead-of-through-ballast-run)); [qualification.md](qualification.md) is the deliverable. An independent review of the report runs before the PR (T013).
