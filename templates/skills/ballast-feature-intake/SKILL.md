---
name: ballast-feature-intake
description: Start, fix, investigate, or continue a GitHub issue from agent chat by applying the scope gate, preparing approved issue setup, and handing off to the existing Spec Kit workflow.
---

# Feature intake

Use this skill for `Start #N`, `Fix #N`, `Investigate #N`, `Continue #N`, or an equivalent request in this repository. GitHub is the work tracker; accepted documents and feature artifacts own intent. Read `AGENTS.md`, the issue and all its comments, and the relevant sections of `docs/policies/spec-kit-workflow.md` and `docs/policies/issue-tracker.md`. Use `gh api` for parent, sub-issue and dependency relationships when the installed `gh issue view --json` lacks those fields. Inspect only relevant accepted roadmap/spec/ADR context and existing `specs/<number>-<slug>/` artifacts. If inspection fails, stop without mutation.

## Route

Apply the project's deterministic scope and risk rules before any optional model classifier. Show the evidence for the route:

- **Epic**: identify independently specifiable children, acceptance ownership, material dependencies and the first unblocked child. An unapproved or materially changed map needs human resolution before new children are created. The Epic itself never enters `speckit.specify` or receives `ready-for-agent`.
- **Cohesive feature**: one main outcome, in/out boundary and acceptance group; use `ballast-feature` after scope-gate setup. Do not turn its `tasks.md` entries into Issues.
- **Small bounded bug**: use the existing `bugfix` workflow. **Investigation/spike**: use `assess`. If either exposes new feature intent, return to the feature scope gate.
- **Active feature**: reuse the existing feature directory and its approvals. Read its artifacts and local run state; resume only a run that belongs to this directory. If no valid run exists, use the documented manual/fresh-run route without overwriting artifacts.

Closed, blocked, inaccessible or ambiguous items do not dispatch. Product behavior, scope, acceptance ownership, architecture, authority, identity, security, migration and R2-sensitive decisions pause for the applicable human resolution. A proposal in a comment is not approval. An already approved scope or decomposition authorizes its routine mechanical steps without asking again.

## Mechanical setup

Run `ballast intake --repo OWNER/REPO preflight N` before **every** feature handoff, including one with no GitHub mutation. A nonzero result stops dispatch. The helper checks explicit Epic signals, blockers, state and parentage; you still own semantic scope judgment from the issue and accepted context.

For an approved leaf that needs a scope comment or `ready-for-agent`, call `prepare --issue N --classification feature|bug|assess --scope-file FILE`. The scope file states classification, acceptance grouping, accepted links, and lines beginning `Scope gate:`, `Main outcome:`, `In scope:`, `Out of scope:`, and `Risk: R0|R1|R2`. When the operator wants the feature run in Autonomous mode, the scope file also has the line `Autonomous: yes` and a line `Privileged actions before merge: none` (or a comma-separated list of privileged-action kinds, such as `secret-provisioning`; the kinds are listed in `speckit.ballast.decide`); the helper refuses an Autonomous scope without it, and an Autonomous start refuses a scope record that lacks it. For an approved new Epic child, also pass `--parent P --slug CHILD-SLUG --title TITLE --body-file FILE` and omit `--issue`; the child body states its own outcome, scope, acceptance criteria, dependencies and parent. Keep these temporary files outside tracked paths. Use `--repo OWNER/REPO` in both cases. The helper may create/reuse one child, link its parent, add one scope comment and add `ready-for-agent`; it cannot approve scope. Never use `prepare` to encode an unapproved decomposition or to change unrelated labels, milestone or Project fields.

Read the helper's JSON result. A failure names completed and pending steps; inspect the live issue before retrying with the same parent and slug. A conflicting child, parent or scope marker needs human resolution. Record the selected issue and feature directory in the handoff; rely on Project auto-add. Do not claim an unverified GitHub mutation succeeded.

## Handoff

You run the mechanical commands yourself from this session; add `--relayed-by SESSION` (a name for this session, for example `claude-code:` followed by a short ID) to `ballast run start`, `resume`, `continue` and `approve`, which records that you relayed them. Relay a decision only within the run's autonomy and only after the operator gave it in chat:

- New feature: `ballast run start -i idea="Issue #N: OUTCOME" -i feature_directory=specs/N-slug -i integration=auto --relayed-by SESSION` (or a specific available integration chosen by the operator). Its gates prompt only at the operator's terminal; never answer one.
- New feature in Autonomous mode, only when the operator chose it in chat and the scope says `Autonomous: yes`: `ballast run start --mode autonomous -i issue=N -i idea="Issue #N: OUTCOME" -i feature_directory=specs/N-slug -i integration=auto --relayed-by SESSION` from a feature branch named for the Issue with no open PR (if it refuses on the branch, it prints the `git switch` command to run first). The run records each gate as an agent-provisional decision and ends with a Draft PR or a block; it never asks for approval. If it refuses, report the reason; the human-gated command above is the alternative.
- New feature in Chat mode, only when the operator chose to drive it in conversation: `ballast run start --mode chat -i feature_directory=specs/N-slug -i idea="Issue #N: OUTCOME" --relayed-by SESSION`. Advance it with `ballast run step RUN_ID PHASE --headless` and `ballast run status RUN_ID`. Relay `ballast run approve RUN_ID GATE...` (or `--through GATE`) only after the operator said yes to those gates in chat; show what each gate approves first.
- Existing feature: `ballast run resume RUN_ID --relayed-by SESSION [-i integration=claude|codex]` only for a valid local run, or follow the manual path in `docs/policies/spec-kit-workflow.md`. An Autonomous run keeps its mode and limits; when it stopped on a block that carries a decision (anything but `upstream-sync`, `interrupted` or `postcondition`), ask the operator, then relay `--ref` naming their answer (for example `Issue #N comment, option 2`), never approval words. A Chat run continues with `ballast run status RUN_ID` and `ballast run step RUN_ID PHASE --headless`, never `resume`.
- Never approve a gate on the operator's behalf: relay only an approval the operator gave in chat. Never relay `ballast run reject`, `resolve` or `mode`: these stay at the operator's terminal.
- Bug: `specify workflow run bugfix -i report="Issue #N: REPORT" -i slug=slug`.
- Investigation: `specify workflow run assess -i idea="Issue #N: QUESTION" -i slug=slug`.

`ballast` is the trusted launcher installed outside the checkout (see `docs/policies/spec-kit-workflow.md`); if it refuses, stop and report its reason instead of running `run.py` directly. A change merged on the pinned default branch refreshes trust by itself; when the launcher still asks for `ballast trust`, you may run it on a checkout you set up, outside any step, after reviewing what changed, and you never run it from inside a step.

Intake does not approve intent, material plan changes, R2 decisions, final acceptance, or merge. It does not start implementation automatically after setup. Preserve a clear manual recovery path if a CLI or workflow is unavailable.
