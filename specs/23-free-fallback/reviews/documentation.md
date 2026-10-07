# Documentation review: local zero-cost fallback (#23)

- Review: documentation. Agent-provisional, run during the operator's human-gated continuation of Autonomous run `f200c320` (not human approval).
- Reviewer: claude/claude-sonnet-5-5, driving agent (reduced independence).
- Method: `.agents/skills/ballast-documentation-review/SKILL.md` and `docs/policies/documentation.md`; the diff to `README.md`, `templates/policies/spec-kit-workflow.md` (new "Local fallback" section), `templates/policies/model-routing.md`, `specs/TECHNICAL-SPEC.md` (6.4 and the #23 status), `tools/spec_workflow/ledger-schema.md`, `docs/adr/0014-local-zero-cost-fallback.md` and the `run.py` usage text, compared with the code and the live check. There is no `docs/policies/project/documentation.md`.

## Checked

- The flag syntax and its refusals (`--local-fallback MODEL|off`, Chat refusal, no endpoint option), the printed `Local fallback:` line, `status`, `record.md` and `meta.json` evidence match `run.py`, `fallback.py` and the live output.
- Every refusal reason, the 16384 context, the 0.13.4 Ollama minimum, the Spec Kit Codex skill prerequisite, the non-empty `~/.agents/skills` remedy, the one-attempt rule and the never-cross-provider review rule match the code. The Autonomous refusal on a host where Codex's sandbox does not nest is stated as a limitation, not hidden.
- Ledger additions are described in `ledger-schema.md` (additive, schema version 1, an older pinned Ballast rejects them) and in `contracts/ledger.md`.
- ADR-0014 is proposed, not accepted, and says why its number differs from the plan's; it extends ADR-0003 and ADR-0010 without editing their history. The model-routing policy says the fallback is an availability route, never a capability choice.

## Findings

- F-001 (medium, implementation-bug): the policy said the wrapper refuses when `OLLAMA_HOST` or `CODEX_OSS_*` is set, but the wrapper removes the variables from the fallback's environment (observed live), so it never refuses on them. A reader would expect a refusal that cannot occur.
- F-002 (medium, implementation-bug): the ADR and the policy implied that nothing leaves the machine, but the Codex CLI itself contacts `github.com` and `chatgpt.com` at start-up (security F-002). The documents must state what the mitigation does and does not guarantee.
- F-003 (low, implementation-bug): the policy's evidence bullet named `./scripts/agent-metrics`, which this repository does not ship; `ballast ledger report` covers it.
- F-004 (low, spec-ambiguity): the plan, tasks and run record call the ADR ADR-0012. The ADR file is 0014 and its header explains the renumbering.
- F-005 (low, spec-ambiguity): a stock model with no `num_ctx` gets the refusal text `served context unknown`; the policy reads `below 16384 or unknown`, which covers it.

## Resolution

- F-001: fixed. The policy now says the wrapper removes the endpoint variables and every proxy variable, and that the refusal covers one that survives.
- F-002: fixed. The policy, ADR-0014 (Decision, residual risk) and the technical spec say that every proxy-aware request of Codex is pointed at a closed local port, loopback is exempt, and this reduces egress without being a network boundary.
- F-003: fixed (`ballast ledger report --run RUN_ID`).
- F-004: accepted; the plan, tasks and run record are digest-bound to recorded reviews, and the ADR documents the renumbering.
- F-005: accepted, covered by the existing wording.

- Verdict: approved
