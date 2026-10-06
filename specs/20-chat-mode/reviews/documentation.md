# Documentation review: Chat mode (#20)

- Review: documentation
- Reviewer: claude (claude-opus-5-5), the agent finishing the implementation, same provider as the author. Codex was unavailable (usage limit), so there is no cross-provider reviewer.
- Scope: `52031c1..HEAD` plus the review fixes: `README.md`, `AGENTS.md` (and `CLAUDE.md`, a link to it), `templates/AGENTS.md`, `templates/policies/spec-kit-workflow.md`, `templates/policies/workflow.md`, `templates/skills/ballast-feature-intake/SKILL.md`, `specs/TECHNICAL-SPEC.md` §91, `docs/adr/0006-chat-mode-operator-driven-steps.md`, `docs/policies/project/testing.md`, `tools/spec_workflow/ledger-schema.md`, and the feature contracts.

## What was checked

- **Public CLI.** Every command in the README block and in the policy's command table exists in `run.py`'s usage, with the same arguments: `start --mode chat`, `step [--kind]`, `status`, `approve`, `reject --reason`, `resolve`, `checks`, `mode`, `continue --mode chat` and `publish`. The `resume` refusal text in the policy matches `run._resume_refusal`.
- **Permission wording.** The README, the policy and ADR-0006 describe the interactive model as it is implemented: `dontAsk` (Claude) or `--ask-for-approval never` (Codex), the headless rules, bwrap and a systemd scope, and read-only `.claude/` and `.codex/`. They now also cover the `PreToolUse` hook outside `dontAsk` and the read-only installed skills (DEC-0001, SEC-001). Nothing claims more than the code enforces. The Codex `/approvals` residual is stated in DEC-0001.
- **Failure states and recovery.** These are documented with their recovery: preflight refusals, `BLOCKED_UPSTREAM_SYNC` with the `ballast run step RUN PHASE` recovery, the unfinished-step refusal with `ballast discard-runs`, a tampered step, an integration that cannot run confined, and a final approval made stale. A blocked `continue --mode chat` is recovered by the next `step` (contracts/cli.md).
- **Human authority.** Every shipped text says approvals exist only through `ballast run approve` from a terminal, that an agent never approves, and that work outside `ballast run` has none of these guarantees (FR-023). `tests/test_governance.py` checks these phrases in the four shipped files.
- **ADR.** ADR-0006 is new and `Proposed`. It now states the ADR-0004 and ADR-0005 rules it amends (review finding ENG-011) and the three review decisions. ADR-0004 and ADR-0005 are unchanged, so the decision history is kept.
- **Testing guidance.** `docs/policies/project/testing.md` and `AGENTS.md` no longer say "four tests skip in CI". They name the kinds of test CI skips, including the real-confinement Chat tests (review finding TST-004).
- **Ledger schema.** `ledger-schema.md` documents the optional `mode` field and the `mode-changed` status as additive changes, with `schema_version` 1 kept.

## Findings

```yaml
review: documentation
verdict: approved
findings:
  - id: DOC-001
    severity: low
    location: templates/policies/spec-kit-workflow.md (Chat runs, "Interactive confinement")
    description: >
      The Codex side of DEC-0001 is not in the shipped policy: an operator's
      `/approvals` inside a Codex Chat session can widen that session up to the
      bwrap bound. It is recorded in decisions.md, which the merge reviewer
      reads, but not where an operator would look.
    required_action: >
      Add one sentence to the policy.
    resolution: >
      Fixed: the "Interactive confinement" paragraph now says Codex has no such
      hook and that `/approvals` can widen a Codex step up to the bwrap bound.
  - id: DOC-002
    severity: low
    location: specs/20-chat-mode/quickstart.md
    description: >
      Scenario 4 expects publication after the reviews. With DEC-0002, a review
      run after `approve final` makes final stale. The order "reviews, then
      approve final, then publish" is right but implicit.
    required_action: >
      None needed for the merge; the pilot follows the documented order.
```

- Verdict: approved
