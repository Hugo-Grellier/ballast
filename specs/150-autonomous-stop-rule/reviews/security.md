# Security review: 150-autonomous-stop-rule (specialists recheck after fix cycle 3)

- Review: specialists-recheck (security, agent-provisional)
- Reviewer: claude/claude-opus-5-5, fresh context, not the author of the change
- Run: Autonomous `1d0a2143`, R2 (agent authority, launcher trust model, accepted architecture), fix cycles used 3 of 3, so no cycle remains after this review
- Diff reviewed: the whole change against the branch base `d215a63`, meaning commit `1e0a1fe` plus the working tree (`git diff`, `git status`): `docs/adr/0020-autonomous-stop-rule.md`, amendment notes in ADR-0004 and ADR-0010, one paragraph each in `templates/policies/spec-kit-workflow.md` and `specs/TECHNICAL-SPEC.md`, `AutonomousStopRuleDocumentTests` in `tests/test_governance.py`, and the feature directory. Fix cycle 3 changed one sentence in ADR-0020's Self-resume bullet and two expected phrases in `test_self_resume`.
- Read against: `spec.md`, `intent.md`, `plan.md`, `tasks.md`, `decisions.md` (D-001), `autonomous/record.md`, the fix input for cycle 3, the previous security report, `CLAUDE.md`, `docs/policies/workflow.md`, `docs/policies/security.md`, `docs/policies/project/workflow.md` (R2 boundaries), ADR-0004, ADR-0010, ADR-0016 and ADR-0019 (`0019-autonomous-pr-completion.md`). `docs/policies/project/security.md` does not exist.

## Scope

The diff touches no file under `tools/`, `.agents/` or `.github/` (FR-012). Its security weight is the authority it gives the sibling leaves #151 to #154 once merged.

## What was checked

**Self-resume and ADR-0019 condition (11).** Fixed. ADR-0020 now says a self-resume counts as a block resolved during the run for condition (11), so the run's PR stays a Draft. An opted-in run that stopped on a usage limit and resumed with no operator present can therefore not be marked ready for review. This restores the signal ADR-0019 gives the operator. The sentence keeps the runner event a non-human record, so BL-INV-006 still holds.

**Agent authority (BL-INV-003, BL-INV-006).** Unchanged and sound. Credentials, permissions, forge access, eligibility, undeclared or unauthorized privileged actions (ADR-0016) and runner invariants keep blocking. Only decisions that take effect at merge become material provisional decisions. I found no text claiming a human approval.

**Trusted author.** Unchanged and sound. Trust comes only from operator-controlled data, and an unlisted author without the label stays ineligible.

**Remaining gaps, unchanged text.** The Self-resume bullet still does not say that the resume is armed only by the operator's own invocation through the trusted launcher, or that the runner recognizes a usage limit from data the confined agent cannot write. ADR-0010's lock, sync and re-entry still bind it because ADR-0010 is amended, not replaced. The Limit outcome still does not say that the pre-publication guards (protected-input and tamper verification, record re-render, ADR-0016 privileged actions) apply at limit-time publication. A high security finding left after the fix cycles is still mapped to the limit outcome, so its branch is pushed and can run CI where today it blocks. ADR-0019 conditions (7) and (9) keep such a PR a Draft. Each gap is a statement for #153 or #154, both R2 leaves with their own security review. No code in this change acts on them before merge, and the Delivery bullet keeps today's blocks until those leaves ship.

**Secrets and data exposure.** No hostnames, paths, credentials or tokens appear in the new text.

## Checks

The run record shows `ruff check` and `ruff format --check` exited 0 after cycle 3 and the full unittest command timed out again. `decisions.md` D-001 traces the failures to the ledger's operator-attestation guard inside an agent step, which is a safety guard working as designed. D-001 proposes isolating the tests rather than weakening the guard. In this step, `uv run --locked python -m unittest tests.test_governance` ran 38 tests, OK. Trusted `run-checks` has not run, so AC-012 is unverified.

## Verdict basis

No agent gains authority, and nothing in this documentation-only change acts before merge. The self-resume gap from the last review is fixed. Three medium gaps remain, accepted provisionally with reasons for the merge reviewer, since no fix cycle remains and each belongs to an R2 sibling leaf. Approved.

<!-- ballast-findings: begin -->
## Findings (recorded from the review draft)

- F-001 (medium, architecture-issue, accepted-provisionally): Unchanged: Self-resume does not say the resume is armed only by the operator's own invocation through the trusted launcher, or that a usage limit is recognized from data the confined agent cannot write. ADR-0010's lock, sync and re-entry still bind it; #154 is R2 with its own security review and no code here acts before merge.
- F-002 (medium, architecture-issue, accepted-provisionally): Unchanged: Limit outcome publishes in any phase without saying the pre-publication guards (protected-input/tamper verification, record re-render, ADR-0016 privileged actions) still apply. The stop rule's tamper block partly covers it; #153 is R2 and implements it, and the Delivery bullet keeps today's blocks until then.
- F-003 (info, spec-ambiguity, open): Unchanged: a trusted author's Issue body can later be edited by collaborators with triage or write access; the ready-for-agent label has the same exposure, so no new risk. #152 may pin trust to the Issue state at intake.
- F-004 (medium, architecture-issue, accepted-provisionally): Unchanged: a high finding left after the fix cycles or at plan review/reconciliation goes to the limit outcome, so its branch is pushed and can run CI where today it blocks. ADR-0019 conditions (7) and (9) keep such a PR a Draft; documentation-only here and #153 is R2.
- F-005 (medium, architecture-issue, resolved): Fix cycle 3 states that a self-resume counts as a block resolved during the run for ADR-0019 condition (11), so an unattended resume keeps the PR a Draft; test_self_resume checks it.
<!-- ballast-findings: end -->
