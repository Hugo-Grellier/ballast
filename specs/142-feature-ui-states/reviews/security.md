# Security review: Declare UI states per feature (recheck after fix cycle 3)

- Kind: security
- Reviewer: claude-opus-5-5, fresh context, independent of the author and fix steps
- Scope: the whole working-tree diff on `feat-142-review-declare-ui-states-per-feature` against `dfa191c`. The changed files are `tools/spec_workflow/packet.py`, `tests/test_packet.py`, `tests/test_governance.py`, `templates/policies/spec-kit-workflow.md`, `docs/adr/0006-review-packet-reads.md` and the new `docs/adr/0019-feature-local-ui-states.md`. I read the diff against `spec.md`, `intent.md`, `plan.md`, `tasks.md`, `decisions.md`, the security policy, `docs/policies/project/workflow.md` (R2 boundaries) and `CLAUDE.md`.
- Fix input: cycle 3, the last cycle. It carried no findings and no verdicts. Its only failed check is the `[checks]` test command, which timed out again (exit 124). No tracked file changed in cycle 3, so no security-relevant file changed since the cycle 1 recheck.

## Trust boundary under review

The change moves criterion-linked UI states from the protected `ballast.toml` into the agent-writable `specs/<feature>/ui-states.toml`. The operator chose this on 2026-10-12 in the Issue #142 intake scope comment (decisions 1b and 2b). I checked again that agent-written data can add nothing to the packet except labeled, Ballast-built links beside its own feature's criteria.

## What I checked again

- **Read path (FR-014, AC-006).** `collect` calls `read(FEATURE)`. That closure returns nothing for a name `git ls-tree` did not list under the feature directory at the head commit, and otherwise reads through `Step.blob` (`cat-file -s`, `cat-file blob`) under the 1 MiB limit, recording `too_large`. The working tree is never read, and no other feature's file can be reached. No new `git` or `gh` invocation, program, fetch or download is added.
- **Parsing.** `feature_ui_states` returns a fixed reason for a file that is oversized, not UTF-8, not valid TOML, or has a top-level key other than `ui_states`. Agent data cannot raise out of this function and stop the packet; a failed `cat-file` reads as "not UTF-8 text", which only degrades the derived UI section.
- **Validation.** Feature entries go through the shared `_ui_states` validator: only known keys; a 1-80 character name; non-empty `AC-NNN` criteria that this feature's spec defines at the same commit; exactly one of a `safe_path` path or a printable check name of 1-100 characters; at most 50 entries per source and in total after `merge_ui_states`.
- **Rendering (FR-010, FR-011, AC-014, AC-015).** Names go through `inert()`. Criteria are rendered only after the `AC-NNN` match. Links are built from the validated path or the integer run id. `AGENT_LABEL` is a module constant Ballast appends whenever `agent` is set, and `agent` is set only from the source argument, so an agent cannot remove the label or forge a repository entry.
- **Evidence state (FR-012, AC-016).** UI results feed only `Criterion.ui` and the UI section. Repository entries carry `criteria=()`.
- **Protected inputs (FR-013).** The diff does not touch the launcher, the sandbox, the protected-input lists, the trust baseline or `ballast.toml`.
- **Secrets.** The diff, its examples and the ADR contain no secret, hostname or local path.
- **decisions.md.** D-002 proposes giving the runner's `[checks]` commands an environment without the agent git guard. That touches the guard and the run machinery, an R2 boundary. It correctly stays a proposal outside this diff, and nothing here weakens the guard. A human has to resolve it.

## Residual observation

A feature entry may point at any committed file or any check on the head commit, including an unrelated check that passed. The spec accepts this as an edge case. The fixed agent-declared label and FR-012 bound the risk. I carry it forward as information for the merge reviewer.

## Run state

The `[checks]` test command timed out after cycles 1, 2 and 3, and no step has recorded `tests/test_packet.py` passing, so the negative-case tests behind this review have no observed pass. With no cycle left, that failed check stops the run for a human regardless of this verdict.

<!-- ballast-findings: begin -->
## Findings (recorded from the review draft)

- F-001 (info, spec-ambiguity, open): A feature entry may name any committed path or head-commit check, including an unrelated passing one, and the packet shows it beside the criterion. The spec accepts this edge case. The fixed agent-declared label and FR-012 bound it, and the merge reviewer should judge these links like other agent-written content.
<!-- ballast-findings: end -->
