# Plan review: Autonomous PR completion policy

- Review: plan (engineering review of the design artifacts)
- Run: `478cbe23`, feature `specs/141-autonomous-pr-completion`
- Reviewer: claude/claude-opus-5-5, same provider as the author (reduced independence, DEC-0004)
- This verdict is agent-provisional. Merging the PR stays the only human approval.

## What was reviewed

- Artifacts: `spec.md`, `intent.md` (PD-0008), `plan.md`, `research.md` (R1–R15), `data-model.md`, `contracts/config-and-cli.md`, `contracts/output-and-ledger.md`, `quickstart.md`, and the run record `autonomous/record.md` (PD-0001 to PD-0008). `tasks.md` and `decisions.md` do not exist yet, as expected before `speckit.tasks`.
- Policies: `AGENTS.md`, `docs/policies/workflow.md` (review matrix), `docs/policies/engineering.md`, `docs/policies/project/workflow.md` (R2 boundaries). There is no `docs/policies/project/engineering.md`.
- Code that the plan cites, checked at the branch base `81d39fc`:
  - `tools/spec_workflow/run.py`: `_checkpoint` (549) returns nothing today and swallows every exception. `_run_autonomous` (872–876) and `_resume_engine` (2093–2097) call `_checkpoint` in `finally` after `_finish` → `_publish`. `_publish` (1147) sets `published` before printing. `_publish_command` (1297–1333) runs no checkpoint and refuses a `published` run. `RESUME_FLAGS` is at 1685. `_resume_locked` records `block-resolution` (2026).
  - `tools/spec_workflow/autonomy.py`: `publish` (4030) returns only `ok`, `category`, `message` and `url`, and refuses a tree other than `checked_tree`. `_pr_problem` (4441) requires an open draft. `NEVER_AUTHORIZED` includes `mark ready` (273). `WIDENING` is the "cannot widen eligibility" warning (182). `parse_policy`, `privileged_union`, `current`, `read_checks` and `effective_mode` exist.
  - `tools/spec_workflow/draft_pr.py`: reuse never checks draft state; only the create verification at 981 does. `checkpoint_work` attaches the packet outcome. `_command`, `_resolve` and `_classify` exist.
  - `tools/spec_workflow/packet.py`: `PacketOutcome` carries `state`, `head`, `pr_number` and `counts`; the states include `published`, `updated` and `unchanged`.
  - `templates/spec-kit/workflows/autonomous/workflow.yml` 328–355: `record-reconciliation`, then `validate-convergence`, then `run-checks`, then `record-final`.
- Documentation surface: a search of `templates/`, `README.md`, `specs/TECHNICAL-SPEC.md` and `docs/adr/` for statements that a PR is never marked ready. The plan's Repository Impact covers the Publication row and line 1229 of `templates/policies/spec-kit-workflow.md`, the Autonomous bullet of `templates/policies/workflow.md`, the README, the technical spec, and ADR-0004 through ADR-0019. ADR-0006's "no ready change" still holds, because the packet does not change. The `mark-ready` wording in `speckit.ballast.decide` and ADR-0016 stays true.

## How the design holds the requirements

- **Requirement coverage.** FR-001 to FR-017 and AC-001 to AC-018 each map to a contract clause or a quickstart scenario. SC-002 has one scenario per condition. SC-003 compares the stdout, the run record and the ledger byte for byte against a disabled baseline.
- **Source authority.** The policy comes only from the start snapshot or the `ballast trust` baseline. The start flag is stored apart from the configured value, so a refresh can still narrow the result (R3, AC-018). Eligibility reads the run record, the decision log, the human decisions, `checks.json`, the packet outcome held in memory, and one forge read-back. Agent-written `convergence.md` is never read; condition (6) uses the recorded reconciliation verdict, which the workflow gates through `validate-convergence` before final acceptance. This is sound.
- **Failure behavior.** `_complete` runs after `_checkpoint` inside the same `finally`, so the exit status is already fixed. The plan turns every exception into `internal-error`, mirroring `_checkpoint`. A process that dies between publication and completion leaves a Draft, because the hand-off is never persisted (R1). This fails closed.
- **Compatibility.** The new snapshot fields are added only when a key or the flag is set. `publish` gains return keys, but nothing persists them. The new `pr_completion` kind is written only on reported runs, so an unconfigured ledger stays readable by older pinned versions, the same pattern ADR-0018 records.
- **Publish retry (R2).** It is correct that a retry with no checkpoint could never satisfy condition (9). Running the checkpoint only on a reported run keeps FR-013. `_checkpoint` takes no run lock of its own, so calling it inside `_invocation_lock` should not deadlock. The implementation tests should confirm this.
- **Postconditions.** `ready` is recorded only after a read-back shows `draft: false` at the published commit (BL-INV-005). One edge breaks this: a head push that races the ready call (F-001).
- **Scope.** Merge and auto-merge stay out (#143). No agent authority is added, and `mark-ready` stays never-authorizable. R2 is classified correctly (`docs/policies/project/workflow.md`: what `ballast` executes, the launcher's trust model).

## Notes for later reviews

- Because the same provider wrote and reviewed this plan, the security review should be independent where practical. It should also confirm that the completion module calls `draft_pr._command` the way the Draft PR checkpoint does.
- Expected outcome for this run: it records a material decision (PD-0008) and is R2, so under its own conditions (3) and (10) its PR would stay a Draft.
- Required specialist kinds for this R2 change: security, architecture and documentation, with test review at implementation.

<!-- ballast-findings: begin -->
## Findings (recorded from the review draft)

- F-001 (medium, implementation-bug, accepted-provisionally): R8 residual race: if a push lands between the read-back and gh pr ready, the PR becomes ready, but the plan records outcome draft (forge-unverified) and prints 'PR completion: draft'. That ledger fact is unverified, which goes against BL-INV-005. The window is narrow, marking ready approves nothing, and the human merge still gates. Tasks should word the forge-unverified line and event so they do not assert the PR is a Draft, for example by stating the PR state was not verified. ADR-0019 should name this.
- F-002 (low, spec-ambiguity, open): AC-003's publish-retry clause is vacuous: a run is published before completion runs, and publish refuses a published run (run.py 1319). The plan pins this with tests (R11). Spec reconciliation should reword AC-003 and FR-012.
- F-003 (low, spec-ambiguity, open): FR-009 and AC-004 say the reason appears on the Draft PR line. The plan prints a separate 'PR completion:' line after the packet line (R10). The behavior is equivalent, but spec reconciliation should align the wording.
- F-004 (low, spec-ambiguity, open): AC-018's second clause makes the refreshed completion value apply, but every --refresh-policy resume records a block-resolution. Condition (11) then always keeps that run's PR a Draft, so the refreshed value changes only the snapshot. The plan states this. The spec should say it explicitly.
- F-005 (low, implementation-bug, open): Internal inconsistency: research R9 allows cause only with forge-failed, while data-model and the output contract also allow it with pr-unreadable. Tasks should follow the contract and update R9 to match.
- F-006 (info, architecture-issue, open): Conditions (6), (7) and (10) read verdicts, severities and the material flag that trusted recorders recorded but agents drafted (R7). This adds no trust beyond ADR-0004, but the merge reviewer and the security review should weigh it.
<!-- ballast-findings: end -->
