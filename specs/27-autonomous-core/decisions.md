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
- **Settled at merge (2026-10-04)**: `feat-github-draft-pr` (#17, PR #33) merged to `main` first with `docs/adr/0003-launcher-github-authority.md`, so this branch renamed its ADR to `docs/adr/0004-autonomous-provisional-decisions.md` (title `ADR-0004`) when it merged `origin/main`, and updated the references in `plan.md` and `tasks.md` (T004, T071, T073).

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

## DEC-0006 — Proposal

- **Found during**: implementation review codex-1, finding F4 (2026-10-04).
- **Conflict**: [contracts/workflow.md](contracts/workflow.md) step 30a, as approved, had `renew-intent` append a superseding intent decision attributed to `runner` (no deciding agent) when a resolution changed `spec.md`. FR-010 requires every provisional decision to name the deciding agent (provider, model, role), and FR-012 requires a stale intent to stop the run. The approved spec wins over the contract.
- **Label**: spec violation (implementation and contract against FR-010 and FR-012).
- **Changed (fail-closed, pending this resolution)**: `renew_intent()` in `tools/spec_workflow/artifacts.py` no longer records an intent decision. When the spec digest differs from the current intent decision, it records a `postcondition` block naming the resolutions that changed the spec; the operator continues human-gated and `approve-intent` decides the changed spec. Step 30a, `data-model.md` and the plan's acceptance row are updated; `spec.md` is unchanged. Test: `ProvisionalIntentTests.test_renew_blocks_stale_intent_after_a_spec_change` (task T069d).
- **Options**:
  1. Keep the block (current code): any spec-changing resolution ends the Autonomous part of the run.
  2. Add an agent step to `ballast-autonomous` after `record-resolutions` (for example `speckit.ballast.decide` with args `intent`, recorded by `record-decision --point intent`) so a deciding agent supersedes the stale intent and the run continues; `--renew` then only verifies that the current intent matches the spec.
- **Recommendation**: option 1 for #27 (smallest change, no new agent authority); option 2 as a follow-up if spec-changing resolutions turn out to be common.
- **Needs**: human resolution (operator).

## DEC-0006 — Resolution

- Option 1, provisional under the operator's standing authority for Epic #11 children (2026-10-04); confirm at merge. A `spec.md` change made by resolutions blocks the Autonomous run as stale intent; the operator continues human-gated, where `approve-intent` decides. It fails closed, satisfies FR-012 without a new agent step, and keeps a deciding identity for every intent decision (FR-010).

## DEC-0007 — Proposal

- **Found during**: merging `origin/main` into this branch (2026-10-04), after #17 (Draft PR checkpoint, PR #33) merged first.
- **Conflict**: #17's accepted behavior runs `draft_pr.checkpoint` once at the end of every `ballast run` invocation; it creates or reuses the branch's one Draft PR. FR-024 here has `run.py` open the Draft PR itself, and the approved publisher refuses any open PR on the branch ("reuse is #17"). Merged as is, three things break:
  1. Order: the checkpoint ran inside `_launch`, before `_finish` publishes. On a branch already published with a change outside `specs/<f>/`, it would open a #17 PR first, and the publisher would then refuse its own run (`postcondition`, not retryable).
  2. Retry: when publication fails after the push, the checkpoint at the end of that invocation can open the PR; `ballast run publish` then refuses for the same reason, and the PR never gets the merge-review summary (FR-025).
  3. Hardening: the publisher and eligibility ran `gh` and `git` found by `shutil.which` (a checkout or `/tmp` copy could run with the operator's token), started `gh` inside the checkout (it reads the agent-writable `.git/config`, #17 DEC-0004) and took the repository from `gh repo view` of the agent-writable remote (#17 DEC-0005).
- **Not a conflict**: the checkpoint does not clobber the publisher's record. The publisher's body has no `<!-- ballast:draft-pr:begin -->` section and references the Issue (`for #N`, `Refs #N`), so `reuse()` leaves it unchanged; on a body with one section it rewrites only that section.
- **Label**: architecture issue (two approved features sharing one PR identity and one GitHub authority).
- **Proposal** (smallest change that keeps both guarantees):
  1. `run.py` calls the checkpoint once per invocation, in a `finally`, after everything else: after `_launch` for a human-gated start or resume, after `_finish` (publication) and the operator archive for an Autonomous start, and after the continuation for `continue`. Tokens stay withheld from the engine; the branch is pinned at every start before the engine and never on resume; the checkpoint never changes the exit status. `publish` runs no engine and no checkpoint, as #17 specifies the checkpoint for start and resume.
  2. The publisher adopts exactly one open PR on the branch whose body has one Ballast section for this feature (one the checkpoint opened): it pushes as before and edits that PR's body to the merge-review summary followed by the same section. Any other open PR is still refused. The adopted PR is not re-checked for draft state: the checkpoint only opens drafts and the publisher never changes readiness.
  3. The publisher and the eligibility check run `gh` and `git` through draft_pr's helpers: `_resolve` (outside every working tree and agent temp root), `_command` (empty temporary directory for `gh`, trusted `PATH`, Git location variables dropped, fsmonitor and hooks off) and `_pinned_repository` (`[github] repository` in `ballast.toml`). Every `gh pr` call names `--repo`, and `pr create` also names `--base` and `--head`. The publisher refuses (`postcondition`) when `origin` is not that repository, because `origin` receives the push. A missing pin is a retryable `forge` refusal at publication and an `ineligible` refusal at start.
- **Needs**: human resolution (operator).

## DEC-0007 — Resolution

- Accepted as proposed, provisional under the operator's standing authority for Epic #11 children (2026-10-04); confirm at merge. Both features' guarantees hold on every path: one PR per feature branch, the publisher's summary on it, one Ballast section at most, the checkpoint once per invocation without changing the exit status, and GitHub authority used only through the #17 hardening.
- **Changed**: `tools/spec_workflow/run.py` (`_checkpoint`, called from `main`, `_start_autonomous` and `_continue_command`); `tools/spec_workflow/autonomy.py` (`git`, `_gh`, `_gh_list`, `repository`, `publish`, `_origin_is`, `_adoptable`, `_adopt_pr`, `_create_pr`); the test fixtures (`AutonomyCase` pins `acme/demo`, names `origin` by its GitHub URL with a `pushInsteadOf` to the bare repository, and trusts the test temp root; the fake `gh` reads `--body-file -`, wraps `--slurp` pages and supports `pr edit`); the `stopped` engine helper now asserts that no PR is published instead of no `Draft PR` text, since #17 prints its line on every run; `templates/policies/spec-kit-workflow.md` (Publication row, Draft PR section), `README.md`, `contracts/config.md`; task T069f.
- **Tests**: listed in T069f. `test_publication_then_checkpoint_leaves_one_pr` runs an Autonomous start that publishes, then the real checkpoint: one `pr create`, no `pr edit`, the checkpoint reports `reused #7` and records it in the ledger. The unchanged `tests/test_draft_pr.py` and `DraftPrRunTests` pass.
- **Follow-up (commit review, 2026-10-04)**: two gaps in the first version, fixed within the same resolution. (1) Adoption checked only the body: the publisher now adopts a listed PR only when its head is a branch of the pinned repository itself (`isCrossRepository` false, head repository name and owner and the PR URL equal to the pin, case-insensitively), the rule of `draft_pr._pull_request`. (2) Validating `origin`'s fetch URL did not bound the push, and a second review showed that enumerating dangerous keys cannot be complete (a `url` subsection with spaces defeated the parser; `core.sshCommand`, `credential.helper` and includes run commands with the operator's credentials). The publisher now pushes HEAD's commit to `refs/heads/<branch>` at a URL rebuilt from the pin (the scheme of `origin`) from a throwaway bare repository in operator state with an empty config that borrows the checkout's objects, so no checkout configuration applies; Git location and `GIT_CONFIG_*` variables are dropped, `PATH` is draft_pr's trusted one, and `core.hooksPath=/dev/null` and `core.fsmonitor=false` stay set; the operator's global configuration and credentials still apply; it then records `origin` as the branch's upstream for the checkpoint. Task T069h.

- **Follow-up (implementation review codex-2, 2026-10-04)**: two publisher findings, fixed within this resolution. (1) High, FR-024: `publish` accepted a created PR from `gh pr create`'s output and adopted a listed PR without knowing its base or draft state. It now reads every PR back with `gh api repos/<pinned>/pulls/<n>` and requires, as draft_pr's `verify()` does, an open draft to the default branch from `<pinned>:<branch>`. A created PR that fails this is a `postcondition` block naming the problem. An adoption candidate that fails it, for example one a human marked ready or retargeted, is not adopted and is refused as before (`reuse is #17`). The publisher never changes a PR's readiness, so it does not adopt a ready PR. (2) Medium, ADR-0003: adoption replaced the whole body from an entry read before the commit and push. It now re-reads the PR just before `gh pr edit` and leaves a body that changed since it was read, as a retryable `forge` block. It only sets its own section between `<!-- ballast:autonomous:begin -->` and `<!-- ballast:autonomous:end -->`: it replaces that section, or inserts it before the #17 section, and keeps every other byte. Task T069j.

## DEC-0008 — Proposal

- **Found during**: the operator's live pilot (2026-10-04; scratch repository, Issue #1).
- **Gap**: in an Autonomous run no agent sees the Issue body. Agents are denied `gh` and receive only the `idea` input (the Issue title), so the clarify agent reported that all its defaults rested on the title alone and the spec ignored the Issue's acceptance criteria. Nobody checks intent against the Issue before merge, so this defeats the point of the run. The approved artifacts do not say how the Issue reaches agents.
- **Label**: spec ambiguity (missing input; no authority change).
- **Proposal**: at an eligible start, after eligibility has read the Issue through the hardened `gh` and the pinned repository, `run.py` writes a snapshot (number, title, labels, body, the one intake scope comment) to `.specify/workflow-state/issues/<N>.md`. It is framed as untrusted Issue data and capped at 60,000 characters, with `[truncated by Ballast]` marking any cut. `.specify/` is bound read-only in agent steps, so agents can read it but not change it. The Autonomous `specify` idea names it, and `speckit.ballast.decide` (scope) and `speckit.ballast.clarify` read it and take the acceptance criteria from it. `ballast-feature` is unchanged (SC-007).
- **Needs**: human resolution (operator).

## DEC-0008 — Resolution

- Accepted as proposed, provisional under the operator's standing authority for Epic #11 children (2026-10-04); confirm at merge. The path is keyed by Issue number, not run ID, so a command template can name it from `<f>` alone; each start replaces it.
- **Changed**: `tools/spec_workflow/autonomy.py`, `tools/spec_workflow/run.py`, `templates/spec-kit/extensions/ballast/commands/speckit.ballast.decide.md` and `speckit.ballast.clarify.md`, `templates/policies/spec-kit-workflow.md`, `plan.md`, `data-model.md`, `contracts/workflow.md`; task T069i.
- **Tests**: listed in T069i.

