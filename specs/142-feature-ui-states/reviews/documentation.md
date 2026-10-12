# Documentation review: Declare UI states per feature (recheck after fix cycle 3)

- Kind: documentation
- Reviewer: claude-opus-5-5, fresh context, independent of the author and fix steps
- Scope: the documentation in the whole working-tree diff against `dfa191c`. That covers the acceptance packet section of `templates/policies/spec-kit-workflow.md`, the amendment note in `docs/adr/0006-review-packet-reads.md` and the new `docs/adr/0019-feature-local-ui-states.md`. I checked them against AC-017, AC-018, AC-019, FR-016 and FR-017, the documentation policy and `tools/spec_workflow/packet.py`.
- Fix input: cycle 3, the last cycle. It carried no findings, only the timed-out test check. No tracked file changed in cycle 3; the documents are unchanged since implementation. I re-read them in full against the current code.

## Requirement coverage

- **AC-017 / FR-016.** The policy gives:
  - the feature file's location and its only top-level key;
  - the entry schema with an example, and a criterion-less `[[review.ui_states]]` example;
  - the order (repository entries first) and the 50-entry total;
  - the exact move-to-feature-file error, including for `criteria = []`;
  - the `agent-declared in ui-states.toml` label, and that repository entries carry none;
  - the rule that a UI state never changes a criterion's state.

  Each statement matches `_ui_states`, `merge_ui_states`, `AGENT_LABEL`, `_detail` and `_ui_lines`.
- **AC-018.** It explains how to keep a screenshot current: commit the `path` file with the change, read `check` for the head commit only, and expect `missing` when the head commit has no result. This matches `ui_result`.
- **AC-019 / FR-017.** ADR-0019 records the move and amends ADR-0006, which points back to it. It states that no new program, call, fetch, download or authority is added, and it lists the rejected alternatives. The policy cites ADR-0019 beside ADR-0006.
- **Migration.** The policy, the ADR's Consequences section and the error text all tell a project to move its `criteria` entries to the feature file.
- **Installed copy.** `docs/policies/spec-kit-workflow.md` comes from the pinned release and is correctly left unchanged. The README and the top-level specs do not describe this configuration.
- **decisions.md.** D-001 and D-002 are run-machinery proposals. They need no change to user-facing documentation in this feature.

## Accuracy notes carried forward

- The policy says a UI reason names its failing source, and ADR-0019's Failure bullet says each reason names its source, but `more than 50 UI states` has no prefix, as AC-012 specifies. A short exception in both texts would make them exact.
- A feature file with `ui_states = []` renders `None (0).`, not `not configured`. A test asserts this, but the policy does not describe it.

## Verification and run state

The documents and code are unchanged since the cycle 2 recheck, where `tests.test_governance` (including `FeatureUiStatesDocumentTests` for AC-017 to AC-019) and ruff passed. The `[checks]` test command timed out after cycles 1, 2 and 3; with no cycle left, that stops the run for a human regardless of this verdict.

<!-- ballast-findings: begin -->
## Findings (recorded from the review draft)

- F-001 (low, spec-ambiguity, open): The policy and ADR-0019 say a UI reason names the failing source (ballast.toml: or ui-states.toml:), but 'more than 50 UI states' has no prefix, as AC-012 specifies. A short exception in both texts would make them exact.
- F-002 (info, spec-ambiguity, open): A feature file with ui_states = [] renders None (0) rather than not configured. A test asserts this, but the policy does not describe it. The behavior matches the existing ballast.toml behavior.
<!-- ballast-findings: end -->
