# Review: implementation (documentation)

- Role: documentation reviewer
- Agent/model: claude/claude-opus-5-5, the driving agent; reduced independence
- Base: `1ce1f9a..HEAD` (`README.md`, `docs/adr/0009-worktree-preparation.md`, `tools/ballast` usage and docstring, `tools/setup` docstring, `tools/cli.toml` comment, launcher messages)
- Artifacts: `docs/policies/documentation.md`, [spec.md](../spec.md), [contracts/](../contracts/), ADR-0007
- Verdict: approved (after the fixes below)

## What was examined

- **README.** The new "Worktrees" section states the trigger (first `run`, `ledger` or `intake`), the source rule (an installation on this machine for the same repository whose pin and `ballast.toml` match and whose files and execute bits match its record), no download, the stop at the trust check with the inputs to review, per-worktree trust and run state, and the limitation (the first worktree at a new pin or configuration needs `ballast setup`). The old sentence about copying from the primary moved there.
- **Operator-facing messages.** Every refusal names its reason and next action (FR-014): no source, rejected source and why (one line each), damaged cache, another preparation holding the checkout, existing installation, setup journal, version without the declaration. The launcher's no-baseline refusal names the inputs present and `ballast trust`. Checked against the contracts' exact text by the tests.
- **ADR.** ADR-0009 extends ADR-0007 without editing it; status Proposed until the PR merges; it records the trigger, the local-only mode, candidate rules, the safe copy, the record field, recovery of a committed preparation at another fingerprint, trust handling and the `discard-runs` exception, with rejected alternatives.
- **Help text.** `ballast` usage and module docstring, `tools/setup --help` (`--prepare`) and its docstring.

## Findings

| ID | Class | Severity | Location | Evidence | Required action |
|---|---|---|---|---|---|
| DOC-001 | spec ambiguity | low | `specs/15-worktree-setup/contracts/`, `data-model.md` | Implementation refinements were not yet in the contracts: silent non-candidates, the parent-link rejection reason, the shared-lock F-001 check, the stage-changed failure, the copy's link safety, the reworded baseline line, the `discard-runs` exception. | Update the contracts and data model. |
| DOC-002 | spec ambiguity | low | `docs/adr/0009-worktree-preparation.md` | The ADR did not yet state the copy's link safety, the stage comparison, the `core.fsmonitor` rule or the `discard-runs` exception. | Update the ADR. |
| DOC-003 | missing documentation | info | README | The README does not mention that copied files lose set-id and group/world write bits. It is an internal safety rule with no operator action; ADR-0009 records it. | Accept. |

## Resolution

- DOC-001, DOC-002: fixed in the documentation commit that adds this review.
- DOC-003: accepted.
