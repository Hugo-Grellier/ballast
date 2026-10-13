# Security review: 150-autonomous-stop-rule (recheck after fix cycle 1)

- Review: specialists-recheck (security, agent-provisional)
- Reviewer: claude/claude-opus-5-5, fresh context, not the author of the change
- Run: Autonomous `1d0a2143`, R2 (agent authority, launcher trust model, accepted architecture)
- Fix input: `.specify/workflow-state/fix-input/150-autonomous-stop-rule.json`, cycle 1. It carried the engineering findings PD-0009 F-001 (classify plan-review, spec-reconciliation and failed final `run-checks` outcomes) and F-002 (note on ADR-0010's Consequences limit sentence). No security finding was in the fix input.
- Diff reviewed: the whole working tree against `09fb427` (`git diff`, `git status`): new `docs/adr/0020-autonomous-stop-rule.md`, amendment notes in ADR-0004 and ADR-0010 (now three in ADR-0010), one paragraph each in `templates/policies/spec-kit-workflow.md` and `specs/TECHNICAL-SPEC.md`, `AutonomousStopRuleDocumentTests` in `tests/test_governance.py`, and the feature directory.
- Read against: `spec.md`, `intent.md`, `plan.md`, `tasks.md`, `autonomous/record.md`, the previous `reviews/security.md` (PD-0012), `AGENTS.md`, `docs/policies/workflow.md`, `docs/policies/security.md`, `docs/policies/project/workflow.md` (R2 boundaries), ADR-0004, ADR-0010, ADR-0016, the template's `run-checks` and Autonomous-runs sections, and `tools/spec_workflow/artifacts.py` `run_checks` for today's block classes. `decisions.md` and `docs/policies/project/security.md` do not exist.

## Scope

The change contains no runner, validator, skill or workflow code (FR-012 holds: the diff touches no file under `tools/`, `.agents/` or `.github/`). Its security weight is the authority it grants the sibling leaves #151 to #154 once merged. I reviewed the whole ADR again, with attention to what the fix added.

## What the fix changed

The **What still blocks** mapping now classifies a high or critical finding or non-approved verdict at plan review or spec reconciliation, and a failed final `run-checks`, as the limit outcome, and states that a failed `[checks]` command is not a `postcondition`. A check command that changes protected inputs or the tree still blocks: in `artifacts.py` those raise `tamper` and `postcondition` separately from the failed-command block, and the ADR keeps both in the runner-invariant group. ADR-0010's Consequences sentence now carries an ADR-0020 note.

## What was checked

**Agent authority (BL-INV-003, BL-INV-006).** Unchanged from the first review and still sound: credentials, permissions, forge access, eligibility, undeclared or unauthorized privileged actions (ADR-0016) and runner invariants keep blocking; only decisions whose effect waits for the merge become material provisional decisions; a Draft PR cannot merge without the operator. No new text claims a human approval; `test_no_human_approval_wording` applies `autonomy.HUMAN_APPROVAL` to every new passage and passes.

**Trusted author.** Unchanged and sound: trust only from operator-controlled data; an unlisted author without the label stays ineligible.

**Self-resume.** Not changed by the fix. The ADR still does not say that an unattended resume is armed only by the operator's own invocation and runs the trusted launcher path, nor that the usage limit is recognized from data the confined agent cannot write. ADR-0010's lock, sync and re-entry still bind the resume because ADR-0010 is amended, not replaced.

**Limit outcome publication.** Not changed by the fix, and the fix widens its reach. The mapping now sends `review-finding` after the fix cycles, and a high finding at any review, to the limit outcome. That includes a high or critical **security** finding. Today such a finding blocks and nothing is pushed. Under the ADR the runner publishes a Draft PR, which pushes the branch; a push can start CI with the repository's permissions, so a change the security review flagged (for example an edit under `.github/workflows/`) could execute before any human has looked. The ADR's own stop rule arguably covers this, since CI execution on push takes effect before merge, but the explicit mapping says otherwise, and the ADR does not say that limit-time publication keeps the pre-publication guards (protected-input and tamper verification, ADR-0016's privileged-action check) or that a security finding about pre-merge execution still blocks.

**Failed final run-checks.** Publishing after a failed final `run-checks` happens after the review freeze and the protected-input and tree checks have run, so it pushes a reviewed, frozen tree. I found no new exposure there beyond the general CI-on-push point above.

**Secrets and data exposure.** No hostnames, paths, credentials or tokens in the new text.

**Checks.** `uv run --locked python -m unittest tests.test_governance` (38 tests) passes locally, and `uv run --locked ruff check` and `ruff format --check` pass. The run record shows the full suite feedback check timed out in cycles 0 and 1; AC-012 depends on the trusted `run-checks`, which has not run yet.

## Verdict basis

The decision keeps every pre-merge authority boundary and both invariants, and the change carries no code, so no agent can act on these gaps before merge. The two earlier gaps remain, and the fix adds a third, related one: the limit outcome now covers security findings, so the ADR should keep a security finding about pre-merge execution blocking, or require limit-time publication to pass the same guards as normal publication. Each is a one-sentence ADR clarification, and #153 and #154 are R2 leaves with their own security review. I approve with them accepted provisionally, for the merge reviewer to see.

<!-- ballast-findings: begin -->
## Findings (recorded from the review draft)

- F-001 (medium, architecture-issue, accepted-provisionally): Unchanged by the fix: Self-resume does not say the resume is armed only by the operator's own invocation and runs the trusted launcher path, or that a usage limit is recognized from data the confined agent cannot write. ADR-0010's lock, sync and re-entry still bind it because it is amended, not replaced. #154 is R2 with its own security review and no code here acts before merge, so it can wait for merge review.
- F-002 (medium, architecture-issue, accepted-provisionally): Unchanged by the fix: Limit outcome publishes in any phase without saying the pre-publication guards (protected-input/tamper verification, record re-render, ADR-0016 privileged actions) still apply or that a failing guard still blocks; a pushed branch can run CI. The stop rule's tamper block partly covers it; #153 is R2 and implements it, so it can wait for merge review.
- F-003 (info, spec-ambiguity, open): A trusted author's Issue body can later be edited by collaborators with triage or write access; the ready-for-agent label has the same exposure, so no new risk. #152 may pin trust to the Issue state at intake.
- F-004 (medium, architecture-issue, accepted-provisionally): New with the fix: the mapping sends review-finding after the fix cycles, and high findings at any review, to the limit outcome, so a high security finding (for example an unreviewed .github/workflows edit) is now pushed in a Draft PR and can run CI where today it blocks. Keep a security finding about pre-merge execution blocking, or require F-002's guards. Documentation-only here and #153 is R2, so it can wait for merge review.
<!-- ballast-findings: end -->
