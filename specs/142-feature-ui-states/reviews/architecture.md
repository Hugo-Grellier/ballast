# Architecture review: Declare UI states per feature (recheck after fix cycle 3)

- Kind: architecture
- Reviewer: claude-opus-5-5, fresh context, independent of the author and fix steps
- Scope: the whole working-tree diff against `dfa191c`, focused on the accepted ADRs and architecture sections it touches: ADR-0006 (review packet reads), the new ADR-0019, the constitution's protected-input invariant, and `specs/TECHNICAL-SPEC.md` / `specs/PRODUCT-SPEC.md`. I read it with `spec.md`, `intent.md`, `plan.md`, `tasks.md`, `decisions.md`, `CLAUDE.md` and `docs/policies/project/workflow.md`.
- Fix input: cycle 3, the last cycle. It carried no findings and no verdicts. Its only failed check is the `[checks]` test command, which timed out again (exit 124). By modification time, no tracked file changed in cycle 3: `packet.py`, both ADRs and the policy template date from implementation, the tests from fix cycle 1, and `decisions.md` from fix cycle 2.

## Accepted architecture touched

- **ADR-0006.** ADR-0006 says the packet's configuration lives in the protected `ballast.toml`. This change departs from that for criterion-linked UI states. ADR-0019 records the departure with status `proposed`, agent-provisional in run `864d9151`; the merge decides whether it is accepted. That is the new ADR `CLAUDE.md` requires for a change to accepted architecture.
- **Amendment form.** ADR-0006 carries an italic note pointing to ADR-0019, and ADR-0019 has an `Amends:` line. Both follow the repository's precedents (ADR-0007/0015, ADR-0004/0010).
- **ADR-0006 call allowlist.** The change adds no new program, GitHub call or Git command. The file goes through the existing `read()` closure in `collect`, which returns nothing for a name that `git ls-tree` did not list under the feature at head, and otherwise reads it with `cat-file` under `FILE_LIMIT`.
- **Invariants.** The protected inputs and the trust baseline are unchanged, as the operator decided in the Issue #142 intake comment (decision 2b). The code stays standard-library-only (`tomllib` was already imported). There is no second source of truth: criterion-linked entries live only in the feature file, and a `criteria` key in `ballast.toml` is an explicit error that runs before the unknown-key rule (decision 1b).
- **TECHNICAL-SPEC / PRODUCT-SPEC.** Neither describes UI-state configuration, so neither needs a change.

## Design fit

- One validator, `_ui_states`, serves both sources, with the source deciding the allowed keys and the criteria rule. `feature_ui_states` and `merge_ui_states` are pure functions, and I/O stays in `collect`.
- `review_config` no longer takes `spec_ids`, which removes the cross-feature coupling that caused the Issue.
- `merge_ui_states` keeps `openapi` and `api_error` through `dataclasses.replace`, gives the repository's reason first, and applies the 50-entry limit to the total.

## decisions.md

D-001 and D-002 propose a separate Issue to give the runner's `[checks]` commands an environment without the agent git guard and the run variables. That would change the run machinery and the guard, which is R2 work outside this feature. Keeping it out of this diff respects the rule against unrelated refactors, and nothing in the architecture of this change depends on it. Both proposals are still open; a human must resolve them, and this review does not.

## Verification and run state

- This review is architectural; the diff's design is unchanged since the cycle 1 recheck, and I found no new issue.
- The `[checks]` test command timed out after cycles 1, 2 and 3, and no step has recorded `tests/test_packet.py` passing. With no cycle left, that failed check stops the run for a human whatever this verdict says. A passing fast gate from the operator's terminal or CI is still needed before merge.

<!-- ballast-findings: begin -->
## Findings (recorded from the review draft)

None.
<!-- ballast-findings: end -->
