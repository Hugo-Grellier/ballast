# Decisions: Autonomous run core

## DEC-0001 — Proposal

- **Found during**: T004 (implementation, 2026-10-04).
- **Conflict**: The plan and T004 name the ADR `docs/adr/0001-autonomous-provisional-decisions.md` as "the first ADR in this repository". Since the plan was approved, `main` gained `docs/adr/0001-cli-release-asset-install.md` and `docs/adr/0002-cli-standard-manifest.md` (feature 12), so `0001` is taken.
- **Label**: spec ambiguity (artifact numbering only; no behavior change).
- **Proposal**: Record the ADR as `docs/adr/0003-autonomous-provisional-decisions.md`, the next free number on this branch. The parallel branch `feat-github-draft-pr` also drafts a `0003` (`0003-launcher-github-authority.md`), so whichever merges second renumbers its ADR; settle the final number at merge and update the references in `tasks.md`, `plan.md` and the ADR.
- **Needs**: human resolution (operator).

## DEC-0002 — Proposal

- **Found during**: T045 and T046 (implementation, 2026-10-04).
- **Conflict**: Research R-10 and T045 map "a launcher trust-baseline mismatch" to a `trust` block, and T046 asks for an engine case that records one. The launcher (`launcher.py`, unchanged by the plan) refuses every `ballast run` subcommand before it executes `run.py` when a trusted input changed (BL-INV-002), so no run code can write a `trust` block: the refusal happens instead, and the stopped run keeps its earlier block.
- **Label**: spec ambiguity.
- **Evidence**: `AutonomousBlockEngineTests.test_trust` in `tests/test_spec_workflow.py`: after `ballast trust`, a changed `ballast-continue` workflow makes `ballast run continue` exit 2 with `ballast: refusing:`; no continuation run is created and the stopped run's block is unchanged.
- **Proposal**: Keep the launcher refusal as the behavior for a trust mismatch (it is stronger than a block and needs no trusted code to run). Either drop `trust` from the block categories, or keep it reserved for a future launcher that records it; update R-10, T045 and T046 accordingly.
- **Needs**: human resolution (operator).

## DEC-0003 — Proposal

- **Found during**: T048 (implementation, 2026-10-04).
- **Conflict**: T048 expects "an agent edit to `ballast.toml` fails the step as tampering (exit 4)". Under the approved confinement (D-7, R-02), `ballast.toml` is bound read-only inside `bwrap`, so the edit fails at the filesystem: nothing changes, the wrapper sees no protected change, and the step does not exit 4.
- **Label**: spec ambiguity (test expectation; the protection is stronger than described).
- **Evidence**: `AutonomousConfinementEngineTests.test_agent_writes_change_nothing_operator_side` (real `bwrap`, Claude and Codex integrations): writes to `ballast.toml`, `run.json` and `decisions.jsonl`, and agent-invoked `run.py start` and `run.py publish`, all fail; mode, eligibility, limits and `ballast.toml` are unchanged and the run publishes normally. The exit-4 path is still covered behind a simulated confinement hole: `AutonomousBlockEngineTests.test_tamper` (a `bwrap` that passes the self-test but does not confine) records a `tamper` block.
- **Proposal**: Accept the two tests as T048's evidence: under real confinement a protected-input edit is refused outright; the wrapper's exit 4 remains the second guard.
- **Needs**: human resolution (operator).

## DEC-0004 — Proposal

- **Found during**: T067 (host verification, 2026-10-04; Ubuntu, bwrap 0.11.1, `apparmor_restrict_unprivileged_userns=1`, Codex CLI installed).
- **Conflict**: Plan review left "verify Codex's own sandbox starts nested inside `bwrap`" to the implementer. It does not: inside Ballast's `bwrap`, `codex sandbox -c sandbox_mode="workspace-write" -- ...` fails with `bwrap: No permissions to create a new namespace`, and so does a plain nested `bwrap` (also with `--unshare-user` on the outer one). Codex's `workspace-write` sandbox is itself `bwrap`-based, so in an Autonomous run every Codex shell command (including the file reads a reviewer needs) would fail. `run.py` picks Codex as the reviewer whenever its CLI is on `PATH`, so this affects most Autonomous runs on this host, not only Codex-authored ones. The engine tests pass only because their fake Codex runs no sandbox.
- **Label**: architecture issue.
- **Options**:
  1. In Autonomous confined steps only, run Codex with its own sandbox off (`--sandbox danger-full-access`, network still pinned off in config), relying on Ballast's `bwrap` for confinement. This changes the agent permission model (`FORBIDDEN` refuses that flag today), so it is R2 and needs operator approval and a security review.
  2. Refuse Codex for Autonomous steps when a nested-sandbox probe fails: the start falls back to Claude for both roles with `cross_provider: false` (reduced independence, already rendered in the PR), and a Codex-only host is refused with a reason.
  3. Document a host prerequisite that allows nested user namespaces for the agent sandbox, and add the nested probe to `confinement_self_test()` so a host without it refuses Autonomous Codex steps.
- **Recommendation**: option 2 now (no permission-model change, fails closed), option 1 as a follow-up if cross-provider review under `bwrap` is wanted.
- **Needs**: human resolution (operator); R2 if option 1.
- **Also recorded (no conflict)**: Spec Kit's bash scripts (`create-new-feature.sh`, `setup-plan.sh`, `check-prerequisites.sh`) run inside the confinement with `.git` read-only in both a primary checkout and a linked worktree, and the branch stays unchanged. The Checks section now states that `run-checks` saw git-ignored files that the PR does not carry.
