# Independent review of the #24 evidence

- Reviewer: codex-cli 0.155.1, `codex exec -s read-only`, with the `ballast-test-review` skill and `docs/policies/testing.md`. It cross-checked the claims against the raw logs on the operator's host. This review is cross-provider: the evidence was written by Claude.
- Date: 2026-10-07
- First verdict: changes requested (7 findings)

| # | Label, severity | Finding | Disposition |
| --- | --- | --- | --- |
| 1 | overclaim, high | LoreForge `verify` ran `campaigns.spec.ts` and `jobs.spec.ts` only. `health.spec.ts` is in no Playwright project. | Fixed. qualification.md now says the browser test never ran. A comment on LoreForge#127 asks the human reviewer to wire it in. |
| 2 | overclaim, high | #22 SC-004 was claimed as met although the packet's command failed. | Fixed. It is now "not met as written", and the release checklist lists it. |
| 3 | evidence gap, high | The fallback drill does not show a usable fallback for gate item 6. | Fixed. D6 now states it, and the release checklist lists it for the operator's decision. |
| 4 | evidence gap, medium | D2 to D5 and D7a lacked raw transcripts, and D2 did not verify preservation. | Fixed. D3, D4, D5 and D7a were rerun under `script`. D2 was rerun with a digest of the installed tree before and after the failure (identical). qualification.md quotes the transcripts, which stay on the operator's host. |
| 5 | spec violation, medium | #24 asks for the normal scope and intent workflow; the artifacts were hand-written. | Resolved as [DEC-0001](../decisions.md#dec-0001-spec-plan-and-tasks-written-by-hand-instead-of-through-ballast-run) under standing authority and listed for merge review. |
| 6 | overclaim, medium | T014 was ticked, and the checklist called the PR open, before the PR existed. | Fixed. T014 is ticked only once the PR exists. |
| 7 | evidence gap, low | No kept ruff output. | Fixed. Ruff was rerun and its output and exit codes are quoted under AC-003. |

- Verdict after fixes: the findings are addressed as above. The reviewer did not re-run.

## Final pass (v0.10.0), round 1

- Reviewer: codex-cli 0.155.1, `codex exec -s read-only`, with the same skill. It cross-checked the claims against the final-pass logs.
- Date: 2026-10-08
- Verdict: changes requested (3 findings)

| # | Label, severity | Finding | Disposition |
| --- | --- | --- | --- |
| 1 | overclaim, high | AC-001 "Pass" relied on LoreForge evidence from v0.9.0 only. | Fixed. LoreForge was re-pinned to v0.10.0 and Issue LoreForge#128 ran Autonomous to Draft PR LoreForge#129, with 5 of 5 criteria verified. Its one block is filed as #124. |
| 2 | evidence gap, low | The saved PR #8 body predated the demo, and the checks were queued in it. | Fixed. The post-demo body and the completed `gh pr checks` output for #8 and #9 were saved, and qualification.md quotes the refreshed demo line. |
| 3 | evidence mismatch, medium | A checklist milestone row listed #111, #112 and #114 as open, and a blocker row had four cells. | Fixed. A scripted replacement had swapped the two rows; both are restored. |

## Final pass (v0.10.0), round 2

- Verdict: changes requested (3 findings). Round 1's three findings were confirmed fixed.

| # | Label, severity | Finding | Disposition |
| --- | --- | --- | --- |
| 1 | overclaim, high | PR #9's body says the gates were approved by a human operator, while the report says the agent answered them. | Fixed where possible without changing Ballast. Every pilot PR (#3, #4, #9, LoreForge #127, #129) now has a comment saying the gates were agent-answered under standing authority and that no human has approved any gate. The report says so too. |
| 2 | evidence gap, medium | LoreForge #129's `acceptance` check was still pending. | Fixed. The check completed `pass` (4m59s) and the saved check output is updated. |
| 3 | spec violation, high | "No blockers" while the fallback produced no usable artifact does not meet gate item 6 as worded. | Recorded as an explicit operator decision ([DEC-0003](../decisions.md#dec-0003-release-gate-item-6-met-as-a-qualified-mechanism-with-a-known-model-limit)) that narrows how gate item 6 is read. The checklist flags it for confirmation at merge. |

## Final pass (v0.10.0), round 3

- Verdict: changes requested. Finding 2 of round 2 was confirmed fixed, and two findings remain:
  1. **The Chat PR body attributes gates to a human** (high). The comments add context but do not correct Ballast's generated body. Not changed: the body is Ballast's correct output for its design, where the terminal user is the operator. The pilot's substitution of the agent for the human is disclosed in the comments and in the report. Left for the operator.
  2. **Gate item 6 is unmet as worded** (high). DEC-0003 is an exception, not a demonstration. The checklist and summary now call it a release exception that the operator confirms at merge.
- The reviewer advises `Refs #24`, not `Closes #24`. PR #115 follows that advice. The operator closes #24 if they confirm DEC-0003.
