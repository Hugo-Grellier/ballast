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
