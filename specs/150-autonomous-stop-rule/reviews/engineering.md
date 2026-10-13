# Engineering review: 150-autonomous-stop-rule

- Review: implementation recheck after fix cycle 1 (engineering, agent-provisional)
- Reviewer: claude/claude-opus-5-5, fresh context, not the author of the change
- Run: Autonomous `1d0a2143`, fix cycles used 1 of 3, so 2 remain
- Diff reviewed: the whole working tree against `09fb427` (`git diff` and `git status`), not only the fix: new `docs/adr/0020-autonomous-stop-rule.md`; amendment notes in `docs/adr/0004-autonomous-provisional-decisions.md` and `docs/adr/0010-autonomous-resume-and-bounded-recovery.md`; one paragraph each in `templates/policies/spec-kit-workflow.md` and `specs/TECHNICAL-SPEC.md`; `AutonomousStopRuleDocumentTests` in `tests/test_governance.py`; the feature directory.
- Read against: `spec.md`, `intent.md`, `plan.md`, `tasks.md` (including T015, the fix-cycle task), `acceptance-evidence.json`, the previous engineering report, the fix input `.specify/workflow-state/fix-input/150-autonomous-stop-rule.json`, the "Fix loop" section of `autonomous/record.md`, `AGENTS.md`, `docs/policies/workflow.md` and the engineering review skill. `decisions.md` does not exist.

## What was checked

**Fix-input F-001 (R6 mapping gaps).** The **What still blocks** bullet of ADR-0020 now gives the limit outcome to a high or critical finding or a non-approved verdict at plan review or spec reconciliation, reasoning that those steps have no fix cycle so their cycles count as spent at once. It also gives the limit outcome to a failed final `run-checks`, whose failed commands the Draft PR lists, and says explicitly that a failed `[checks]` command is not a `postcondition` because it is evidence about the change, not a runner invariant. Both cases the previous review named are now classified. #151 and #153 can implement them without a new operator decision (SC-003). The classification is consistent with the Stop rule: neither case takes effect before merge, and the Limit outcome bullet already promises that failed checks are listed in the PR.

**Fix-input F-002 (stale ADR-0010 Consequences).** ADR-0010's Consequences sentence "a run that runs out blocks and continues human-gated" now carries a third `*Amended by [ADR-0020]…*` note saying the run publishes a Draft PR that marks unmet criteria `unverified`. The original text is kept, matching the amendment-note convention of R7. ADR-0010 no longer holds a second, unannotated rule.

**Whole change, again.** FR-001 to FR-012 still hold: the header, sections and Decision bullets match the contract; the Status line remains accepted and agent-provisional until the operator merges the PR (FR-009); ADR-0009 is untouched; no file under `tools/`, `.agents/` or the workflow definitions changed (FR-012). The fix did not touch `spec.md`, and the evidence file's digest still matches `sha256sum spec.md` (`27c32447…`). The policy and technical-spec paragraphs still only point to ADR-0020. The pre-merge-authority and runner-invariant groups are unchanged, so BL-INV-003 and BL-INV-006 hold.

**Still open from the first review.** The **Self-resume** bullet still does not say that an unattended resume takes ADR-0010's trusted path (invocation lock, branch synchronization first per ADR-0005, re-entry at the earliest changed input). It is low severity: the bullet keeps mode, risk, limits and integrations fixed, and the security and architecture specialists approved it. A sentence would still save #154 a choice.

**Verification run.** In this review I ran `uv run --locked python -m unittest tests.test_governance` (38 tests, OK), `uv run --locked ruff check` (passed) and `uv run --locked ruff format --check` (passed). The record's "Fix loop" shows the full-suite feedback check `uv run --locked python -m unittest tests/test_*.py` timed out again after cycle 1. When I ran the same suite with a 590-second limit inside this review step, it was also killed by the timeout. The diff adds only file-reading tests that finish in about 20 seconds, and the timed-out output in the fix input shows errors such as "operator attestation is unavailable inside an agent step", which come from tests that need the operator's environment. So the timeout most likely comes from the confinement and is not a defect in this change. It still means AC-012 has no passing evidence until trusted `run-checks` shows the gate passing.

## Verdict basis

Both fix-input findings are resolved in the ADR text and pinned by tests. The rest of the change still meets the spec and keeps every authority boundary. What remains is a low-severity wording gap and the pending full-gate evidence, which the trusted runner decides on, not this review.

<!-- ballast-findings: begin -->
## Findings (recorded from the review draft)

- F-001 (medium, spec-violation, resolved): ADR-0020 What still blocks now maps a high finding or non-approved verdict at plan review or spec reconciliation, and a failed final run-checks, to the limit outcome, and says a failed [checks] command is not a postcondition; test_what_still_blocks pins both.
- F-002 (medium, architecture-issue, resolved): ADR-0010 Consequences now carries an Amended by ADR-0020 note saying a run that runs out publishes a Draft PR with unmet criteria unverified; test_adr_0010_notes expects three notes and checks that one.
- F-003 (low, spec-ambiguity, open): Self-resume still does not say an unattended resume takes the ADR-0010 trusted path (invocation lock, branch sync first per ADR-0005, re-entry at earliest changed input); one sentence would spare #154 that choice.
- F-004 (info, missing-test, open): The full unittest feedback check timed out after cycles 0 and 1 and again in this review step; the new tests only read files and pass in about 20s, so AC-012 evidence waits on trusted run-checks.
<!-- ballast-findings: end -->
