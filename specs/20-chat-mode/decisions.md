# Decisions

## DEC-0001 — Proposal

- **Observed during**: implementation security review (`reviews/security.md`, SEC-003)
- **Classification**: contract-discovery
- **Observation**: FR-005 and AC-003 say a Chat agent gets nothing its headless rules do not allow, and the operator is never prompted to grant it. In an interactive Claude session, Shift+Tab leaves `dontAsk`, and the other permission modes prompt. In Codex, `/approvals` can switch the session's approval policy. ADR-0009 (D-2) accepted bwrap as the bound for any grant, but the spec forbids the prompt itself, and bwrap keeps host network access and command execution that a headless step's rules deny.
- **Proposed decision**:
  - Claude: the generated step settings add a `PreToolUse` hook (`.ballast/spec_workflow/chat_hook.py`, inside the trust baseline) that blocks every tool call unless the session's `permission_mode` is `dontAsk`. It fails closed when the field is missing, and the settings set `disableAllHooks: false`. Leaving `dontAsk` then leads to a denial that names the way back, never to a prompt.
  - Codex: no per-call hook exists. A slash command such as `/approvals` is a deliberate operator command, not a prompt the agent raises (`--ask-for-approval never`). Its effect stays inside Ballast's bwrap and scope, and protected inputs, operator state and `.git` stay out of reach.
  - Pilot checks P-4 (Shift+Tab) and P-5 (`/permissions`) verify this on the real CLIs.
- **Evidence**: `tools/spec_workflow/chat_hook.py`; `tools/spec_workflow/claude-chat-settings.json`; `tests/test_chat_mode.py` `StepEntryTests.test_chat_settings_deny_prompts_outside_dont_ask`; `research.md` R3; ADR-0009 D-2.
- **Affected artifacts**: `contracts/step-runner.md` § Interactive argv; ADR-0009 D-2 (unchanged: bwrap stays the outer bound)
- **Status**: resolved below

## DEC-0001 — Resolution

- Decision: accepted. Decided by the driving agent under the operator's standing authority for v1.0 issues (2026-10-05). Listed for the merge review.
- Rationale: the hook enforces FR-005 for Claude with no change to the spec. For Codex, the residual is an explicit operator action inside the confinement the plan already accepted (D-2), not a prompt. If the pilot shows the hook input lacks `permission_mode`, every tool call is denied (fail closed), and the gap shows at once.

## DEC-0002 — Proposal

- **Observed during**: implementation engineering and security reviews (`reviews/engineering.md` ENG-002, ENG-003; `reviews/security.md` SEC-004)
- **Classification**: contract-discovery
- **Observation**: `final` was bound to the tree digest without `specs/<f>/reviews/`. Its precondition did not require the earlier gate approvals to be current, and `publish` checked only that `final` was current. A review rewritten after final approval, for example `convergence.md` turned to FAILED, or a plan approval made stale by re-running `plan` after `approve tasks`, could still be published under a header saying every gate was approved. The phase-graph contract specified exactly this, so the gap is in the contract.
- **Proposed decision**:
  - Bind `final` to the whole tree, `reviews/` included.
  - Make the `final` precondition require every earlier gate approval to be current (`scope`, `intent`, `plan`, `tasks`, `implementation`, `spec-reconciliation`).
  - Have `publish` evaluate and record the `final` precondition again.
  - Show each approval's state, `current`, `stale` or `superseded`, in the PR's approvals table.
  - Steps between gates keep their own entry conditions; only acceptance and publication need every approval current.
- **Evidence**: `tools/spec_workflow/chat.py` (`GATES["final"]`, `gate_digest`, `publish`, `publish_section`); `tests/test_chat_mode.py` `PublishTests.test_a_review_changed_after_final_approval_blocks_publish`, `PublishTests.test_final_needs_every_earlier_approval_current`.
- **Affected artifacts**: `data-model.md` § Gate digest binding; `contracts/phase-graph.md` (gate `final`, `publish`); `contracts/pr-evidence.md` § Wording rules
- **Status**: resolved below

## DEC-0002 — Resolution

- Decision: accepted. Decided by the driving agent under the operator's standing authority for v1.0 issues (2026-10-05). Listed for the merge review.
- Rationale: this is stricter than before and never weaker. FR-016 ("after final acceptance is approved") and AC-007 (approval bound to the exact artifact version) already require it, and it makes the runner and the ledger report agree on compliance.

## DEC-0003 — Proposal

- **Observed during**: implementation security review (`reviews/security.md`, SEC-002)
- **Classification**: contract-discovery
- **Observation**: a write outside a phase's write scope failed that step, but the change stayed in the tree, and no later entry condition read it. The next step's passing write-scope check then hid the failure from the handoff summary, and the change became part of the tree that later approvals bind to.
- **Proposed decision**:
  - Every phase entry, and the `implementation` and `final` preconditions, run a recorded `open-write-scope` check.
  - The check fails while any path named by a failed write-scope check still holds exactly what that step left.
  - The operator closes it by restoring the path or by changing it themselves. Either way it becomes an operator change, recorded as an out-of-step change.
  - Writes to git-ignored files stay outside the manifest. The installed skills, the main such target, are now bound read-only (SEC-001). Other ignored paths are follow-up F-4.
- **Evidence**: `tools/spec_workflow/chat.py` (`_violations_check`, `_requirements`, `gate_precondition`); `tests/test_chat_mode.py` `StepCloseTests.test_open_write_scope_violation_blocks_until_restored`.
- **Affected artifacts**: `contracts/phase-graph.md` (entry conditions)
- **Status**: resolved below

## DEC-0003 — Resolution

- Decision: accepted. Decided by the driving agent under the operator's standing authority for v1.0 issues (2026-10-05). Listed for the merge review.
- Rationale: FR-008 and FR-010 require a failed check to block until it passes. Without this rule the write-scope check could fail and still let the out-of-scope change through. The operator keeps full authority over the tree between steps.

## DEC-0004 — Proposal

- **Observed during**: pilot (T075, `reviews/pilot.md`)
- **Classification**: verification-scope
- **Observation**: T075's interactive pilot checks need a person at a real terminal with the real agent TUIs and a scratch GitHub remote: P-3 (terminal restored after a resize, Ctrl-C and `/exit`), P-4 (Shift+Tab out of `dontAsk` is denied by the Chat hook without a prompt), P-5 (saving a `/permissions` rule is refused) and quickstart scenarios 1–7 with a real interactive session. A driving agent cannot run them.
- **Proposed decision**: move these checks to #24 (cross-repository v1.0 qualification), which the operator runs. P-1, P-2 and the Codex sandbox nesting probe are done and stay recorded in `reviews/pilot.md`.
- **Evidence**: every boundary these checks exercise has a deterministic test, including real `systemd-run` plus `bwrap` confinement (`StepCloseTests.test_real_scope_and_bwrap_step_is_confirmed_stopped`, `StepEntryTests.test_real_bwrap_keeps_protected_and_operator_paths_out_of_reach`, `StepEntryTests.test_real_bwrap_keeps_installed_skills_read_only`, `ForgeryTests.test_operator_records_are_out_of_reach_under_real_bwrap`, `StepEntryTests.test_chat_settings_deny_prompts_outside_dont_ask`); see the AC traceability in `tasks.md`.
- **Affected artifacts**: `tasks.md` T075; `reviews/pilot.md`
- **Status**: resolved below

## DEC-0004 — Resolution

- Decision: accepted. Decided by the driving agent under the operator's standing authority for v1.0 issues (2026-10-05). Listed for the merge review.
- Rationale: the checks add evidence about real TUIs, not coverage of a boundary: each boundary they touch is already tested deterministically, with real confinement. #24 runs the same checks across repositories with a person at the terminal, so they lose nothing by moving there.

## DEC-0005 — Proposal

- **Observed during**: v1.0 qualification (#24), blank pilot; Issue #111
- **Classification**: implementation bug (AC-016: the Draft PR carries "the same evidence a headless run provides")
- **Observation**: `ballast run publish` for a Chat run opened the Draft PR with the Chat section only. The #17 checkpoint, which publishes the #19 acceptance packet, ran after every Chat step but not after publication, when the branch is usually first pushed. `ballast run checkpoint` refused Chat runs as "not an autonomous run", so no later refresh existed.
- **Proposed decision**: Chat `publish` runs the same Draft PR checkpoint, and so the same packet builder, after a successful publication, as every Chat step does. `ballast run checkpoint RUN_ID` accepts a Chat run, under both the run's invocation lock (held by `demo`) and the Chat run's own lock (held by a running step), and never creates a PR. `ballast run demo`, which also edits the PR body, takes the Chat run's lock too, so it waits for a Chat step or publication instead of racing it. After publication the checkpoint only refreshes; it never creates a second PR. The packet's existing run line names the run ID and its current mode (`chat` while the run stays in Chat); `packet.py` is unchanged.
- **Alternatives**: a documented Chat-only refresh such as a `step`; it would start an agent to refresh evidence.
- **Affected artifacts**: `tools/spec_workflow/chat.py`, `tools/spec_workflow/run.py`, `templates/policies/spec-kit-workflow.md`, `README.md`
- **Status**: resolved below

## DEC-0005 — Resolution

- Decision: accepted. Resolved by the driving agent under the operator's standing authority for v1.0 issues (2026-10-05). Listed for the merge review.
- Rationale: it reuses the #17 checkpoint and #19 packet unchanged, so Chat and Autonomous PRs carry one packet format, and the refresh needs no agent. Evidence: `PublishTests.test_publish_and_checkpoint_carry_the_acceptance_packet`.
