# Engineering review: 150-autonomous-stop-rule

- Review: implementation recheck after fix cycle 3 (engineering, agent-provisional)
- Reviewer: claude/claude-opus-5-5, fresh context, not the author of the change
- Run: Autonomous `1d0a2143`, fix cycles used 3 of 3, so none remain; this is the last implementation review
- Diff reviewed: the whole change against the branch base `d215a63` (`origin/main` after the upstream sync that brought in #155 and ADR-0019), meaning commit `1e0a1fe` plus the working tree (`git diff`, `git status`). Fix cycle 3 changed one sentence in the Self-resume bullet of `docs/adr/0020-autonomous-stop-rule.md`, added two phrases to `test_self_resume` in `tests/test_governance.py`, and added task T016 to `tasks.md`. The other working-tree changes are re-rendered review reports and the run record.
- Read against: `spec.md`, `intent.md`, `plan.md`, `tasks.md`, `decisions.md` (D-001), `acceptance-evidence.json`, the cycle 3 fix input (engineering F-001, one timed-out check), the run record's "Fix loop", `CLAUDE.md`/`AGENTS.md`, `docs/policies/workflow.md`, `docs/policies/engineering.md`, `docs/policies/project/workflow.md`, ADR-0019 and the engineering review skill.

## What was checked

**Fix cycle 3 (F-001).** The Self-resume bullet now states that a self-resume counts as a block resolved during the run for ADR-0019 condition (11), so the run's PR stays a Draft. I read ADR-0019: condition (11) is "no block resolved during the run", and its Consequences rely on every resume recording a `block-resolution`. The new sentence settles the case ADR-0020 created by removing that record for usage limits. It takes the fail-closed reading, and #154 no longer has to choose (SC-003). The link `0019-autonomous-pr-completion.md` resolves. Two ADR-0019 files share the number 0019; the link names the right one. The sentence stays inside ADR-0020's scope and changes no code (FR-012). F-001 is resolved.

**Whole change, re-read.** FR-001 to FR-012 still hold. ADR-0020 keeps the ADR form, an accepted and agent-provisional Status (FR-009), and an Amends line naming ADR-0004 and ADR-0010. The Decision maps every block category: pre-merge authority and runner invariants still block, `decision` and `contradiction` become material provisional decisions, and limits, spent fix cycles, non-approved plan or reconciliation verdicts and a failed final `run-checks` get the limit outcome. Trust comes only from operator-controlled data. No text claims a human approval. ADR-0009 is unchanged. The policy template and the technical spec only point to ADR-0020 (FR-011). Nothing under `tools/`, `.agents/`, `templates/skills` or the workflow definitions changed.

**ADR-0019 interactions.** ADR-0019's Consequences still say that every resume records a `block-resolution`. After ADR-0020 that is no longer literally true for a self-resume. The new sentence keeps the effect that sentence protects, so the gap is wording only and does not justify a further cycle. A limit-outcome PR marks criteria `unverified`, so condition (9) keeps it a Draft. Material provisional decisions fail condition (10).

**Earlier low items.** Self-resume still does not restate that an unattended resume takes ADR-0010's trusted path (F-002). ADR-0010 is amended rather than replaced, so its rules still bind. "A failed `[checks]` command is not a `postcondition`" still reads as present fact while the Delivery bullet keeps today's behavior until #153 ships (F-003). Both remain low.

**Verification run in this review.** `uv run --locked python -m unittest tests.test_governance`: 38 tests, OK. `uv run --locked ruff check`: passed. `uv run --locked ruff format --check`: 515 files already formatted. The full suite timed out in all four feedback checks, including the one after cycle 3. Its output shows the agent-step operator-attestation guard errors D-001 records, in modules this diff does not touch. No in-run run of the full suite passed, so AC-012 depends on trusted `run-checks` or CI. The runner decides whether that check outcome ends the run at its limit.

## Verdict basis

Fix cycle 3 removed the only medium finding. The change meets its spec and authority boundaries, and only low and info items remain. On the code, the change is approved. The full-suite check timed out again for environmental reasons outside this diff. It is still a failed check, and the runner decides it.

<!-- ballast-findings: begin -->
## Findings (recorded from the review draft)

- F-001 (medium, spec-ambiguity, resolved): Fix cycle 3 added to the Self-resume bullet that a self-resume counts as a block resolved during the run for ADR-0019 condition (11), so the PR stays a Draft; test_self_resume pins both phrases and passes.
- F-002 (low, spec-ambiguity, open): Self-resume still does not restate that an unattended resume takes the ADR-0010 trusted path (invocation lock, branch sync first per ADR-0005, re-entry at the earliest changed input). ADR-0010 is amended, not replaced, so its rules still bind.
- F-003 (low, spec-ambiguity, open): 'A failed [checks] command is not a postcondition' reads as present fact, while today's runner treats a failed final check as a postcondition until #153 ships (Delivery bullet). 'Is no longer treated as' would be exact.
- F-004 (info, missing-test, open): The full unittest feedback check timed out after all four cycles, with the agent-step operator-attestation errors D-001 records, in modules this diff does not touch. AC-012 evidence waits on trusted run-checks or CI.
- F-005 (info, spec-ambiguity, open): ADR-0019 Consequences still say every resume records a block-resolution, which is no longer literally true for a self-resume. ADR-0020 keeps its effect through the condition (11) sentence, so only the wording is stale.
<!-- ballast-findings: end -->
