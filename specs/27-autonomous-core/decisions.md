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

## DEC-0005 — Proposal

- **Found during**: T045 (implementation, 2026-10-04).
- **Gap**: T045 maps "an unavailable credential or permission reported by the publisher or an agent block draft" to `permission`. The publisher source exists (`gh pr create` failing on authentication, or `gh` missing, gives a retryable `permission` block). The agent source does not: the approved block-draft contract ([contracts/decision-draft.md](contracts/decision-draft.md#block-draft-blockjson)) allows only `decision` and `contradiction`, so an agent that lacks a permission can only report it as one of those. As T045 instructs, no mapping was invented.
- **Label**: spec ambiguity.
- **Proposal**: Keep the contract as is (agents never name a `permission` block; a missing permission inside a confined step surfaces as a failed step, hence `postcondition`), and narrow T045 and R-10 to the publisher source. Alternatively, allow `permission` in agent block drafts, which changes an approved contract.
- **Needs**: human resolution (operator).

## DEC-0001 — Resolution

- **Status**: accepted by the operator, 2026-10-04 (human resolution).
- **Resolution**: Keep `docs/adr/0003-autonomous-provisional-decisions.md` on this branch. The final ADR number is settled at merge against `feat-github-draft-pr`'s `0003-launcher-github-authority.md`: whichever branch merges second renumbers its ADR and updates its references in `plan.md`, `tasks.md` and the ADR.
- **Changed now**: nothing.
- **Tests**: none (artifact numbering only).

## DEC-0002 — Resolution

- **Status**: accepted by the operator, 2026-10-04 (human resolution).
- **Resolution**: A changed trusted input stays a launcher refusal (`ballast: refusing:` before `run.py` executes); there is no `trust` block category.
- **Changed**: `trust` removed from `BLOCK_CATEGORIES` and `RECOVERY` in `tools/spec_workflow/autonomy.py`, so a block naming it is refused; the block schema in `data-model.md`, research R-10, plan decision D-8 and tasks T045 and T046 updated.
- **Tests**: `BlockRecordTests.test_no_trust_block` (`tests/test_autonomy.py`); `AutonomousBlockEngineTests.test_trust` (`tests/test_spec_workflow.py`) is T046's evidence for the refusal. T045 and T046 ticked.

## DEC-0003 — Resolution

- **Status**: accepted by the operator, 2026-10-04 (human resolution).
- **Resolution**: Under real confinement an agent edit to `ballast.toml` is refused at the filesystem; the wrapper's exit 4 is the second guard behind a confinement hole.
- **Changed**: T048's text now names both tests as its evidence; no code change.
- **Tests**: `AutonomousConfinementEngineTests.test_agent_writes_change_nothing_operator_side` (real `bwrap`, both integrations) and `AutonomousBlockEngineTests.test_tamper` (exit 4, `tamper` block). T048 ticked.

## DEC-0004 — Resolution

- **Status**: accepted by the operator, 2026-10-04 (human resolution): option 2.
- **Resolution**: Codex's sandbox is never disabled. Whenever Codex would take either role, `run.py` probes once at run start (the result is kept in the run record for the whole run): `autonomy.codex_sandbox_nests()` runs `codex sandbox -c sandbox_mode="workspace-write" -c sandbox_workspace_write.network_access=false -- true` inside Ballast's `bwrap` with `--unshare-net`. If it fails, Claude takes both the author and reviewer roles (`cross_provider: false`), the run record gets `integration_fallback` with the fixed reason `autonomy.CODEX_FALLBACK`, the start output prints it and `record.md` renders it. A host without `claude` is refused with the same reason. Option 1 (Codex unsandboxed under `bwrap`) stays a possible R2 follow-up.
- **Changed**: `tools/spec_workflow/autonomy.py` (`CODEX_FALLBACK`, `codex_sandbox_nests`, run-record validation, record rendering), `tools/spec_workflow/run.py` (`_start_autonomous`), `templates/policies/spec-kit-workflow.md` (review row), plan decision D-9, research R-07 review routing, `data-model.md` (`integration_fallback`), `contracts/cli.md`, tasks T067 and new T067a.
- **Tests**: `RunStartTests.test_nested_codex_sandbox_keeps_cross_provider_review`, `test_codex_without_nested_sandbox_falls_back_to_claude` (failed before the fallback existed: the workflow got `review_integration=codex` or `integration=codex`), `test_codex_only_host_without_nested_sandbox_is_refused` and `test_no_probe_without_codex` (`tests/test_autonomous_run.py`); `CodexNestedSandboxTests.test_probe_reports_no_nested_sandbox` (`tests/test_spec_workflow.py`, real `codex` and `bwrap`, skipped unless `apparmor_restrict_unprivileged_userns=1`), which passes on the qualified host (bwrap 0.11.1), where the probe fails with `bwrap: No permissions to create a new namespace`. T067 and T067a ticked.

## DEC-0005 — Resolution

- **Status**: accepted by the operator, 2026-10-04 (human resolution).
- **Resolution**: Only the publisher reports a `permission` block (`gh` missing or unauthenticated at publication). The block-draft contract is unchanged: agents report only `decision` or `contradiction`, and a missing permission inside a confined step fails the step.
- **Changed**: T045 and research R-10 narrowed to the publisher source; `contracts/decision-draft.md` states that agents never report `permission`.
- **Tests**: `RunBlockTests.test_publisher_permission_failure` (`tests/test_autonomous_run.py`), `AutonomousBlockEngineTests.test_permission` (`tests/test_spec_workflow.py`), and a new `permission` case in `BlockRecordTests.test_agent_block_draft_rules` (`tests/test_autonomy.py`) refusing it in an agent draft. T045 ticked.
