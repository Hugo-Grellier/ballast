# Decisions: Autonomous PR completion

## DEC-0001: Report an `unverified` completion outcome

- Type: contract-discovery
- Status: accepted by the operator on 2026-10-13, in the operator's session after the human-gated `implement` step of run 6263f734
- Discovery: the implementation, following plan-review finding F-001, prints `PR completion: unverified …` and records the outcome `unverified` with the reason `forge-unverified` when `gh pr ready` succeeds but reading the PR back does not show it ready at the published commit. The spec named only two outcomes, ready and Draft.
- Resolution: add `unverified` as a third outcome. FR-009 and FR-010 name it, AC-019 covers it, and an edge case states it is never reported as `ready`.
- Propagation: `spec.md` (FR-009, FR-010, AC-019, Edge Cases); `acceptance-evidence.json` (AC-019 and the new spec digest). The intent approval must be given again for the new spec digest.

## DEC-0002: An R2 boundary keeps the PR a Draft at any risk level

- Type: implementation discovery (security tightening, security review SEC-001)
- Status: proposed by the agent; it fails closed, and it is accepted or rejected at merge
- Discovery: condition (3) of FR-005 read only `run["risk"]["level"]`. A run record can declare R2 boundaries (`risk.boundaries`) while its level reads R0 or R1, and the runner would then mark the PR ready for a change that touches an R2 boundary.
- Resolution: condition (3) also fails, with the reason code `risk` and the fixed text `R2 boundaries declared`, when the run record declares any R2 boundary. FR-005(3) becomes "risk is R0 or R1 and no R2 boundary is declared".
- Propagation: `spec.md` (FR-005), `data-model.md`, `completion.py` (`_risk`), `tests/test_completion.py` (`EvaluateTests.test_risk`), ADR-0019, the README and `templates/policies/spec-kit-workflow.md`; `acceptance-evidence.json` (new spec digest). The intent approval must be given again for the new spec digest.

## DEC-0003: Chat adoption of a PR the runner marked ready

- Type: implementation discovery (engineering review F-01)
- Status: proposed by the agent; documented now, the code change is a follow-up
- Discovery: after the runner marks a PR ready, `ballast run continue RUN --mode chat --reason changes-requested` refuses, because Chat adoption needs a Draft PR.
- Resolution: for now the operator first converts the PR back with `gh pr ready --undo <n>`, then continues. A follow-up lets Chat adoption accept a PR that the run's own `pr_completion` event shows the runner marked ready.
- Propagation: `spec.md` (Edge Cases), ADR-0019 (Consequences), `templates/policies/spec-kit-workflow.md` (PR completion).
