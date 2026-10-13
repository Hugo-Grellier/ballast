# Engineering review: Declare UI states per feature (implementation recheck)

- Review: implementation-recheck, engineering, after fix cycle 3 (the last; no cycle remains)
- Reviewer: claude/claude-opus-5-5, fresh context, independent of the author and fix steps
- Run: Autonomous `864d9151`; this verdict is agent-provisional
- Diff: working tree against `dfa191c` (`tools/spec_workflow/packet.py`, `tests/test_packet.py`, `tests/test_governance.py`, `templates/policies/spec-kit-workflow.md`, `docs/adr/0006-review-packet-reads.md`, new `docs/adr/0019-feature-local-ui-states.md`, the feature directory)

## What fix cycle 3 had to fix

The cycle 3 fix input lists no findings and no verdicts. Its only failed check is the `[checks]` test command, which hit its timeout again (exit 124). The output tail looks the same as in cycles 1 and 2: errors early in glob order, including the ledger's `operator attestation is unavailable inside an agent step` (D-001), then long runs of passing tests until the timeout.

No tracked file changed in fix cycle 3. The only newer files are the run record, run state and the ruff cache. `decisions.md` still holds D-001 and D-002 from earlier cycles, unchanged. The run record's Fix loop shows `3 of 3` cycles used. The test check timed out after cycles 1, 2 and 3, and exited 1 after cycle 0.

Since this is the last review, the failed check stops the run for a human whatever verdict I give. A human has to resolve D-001 and D-002. This review does not resolve them.

## Whole-change recheck

The source has not changed since the cycle 1 recheck. I read the full diff again:

- `review_config(root)` validates the repository table as the `ballast.toml` source. Any `criteria` key there gives the move-to-feature-file reason. That rule runs before the unknown-key rule (FR-004, AC-011).
- `feature_ui_states` checks the feature file in this order: absent → `None`, then too large, not text, invalid TOML, an extra top-level key, and finally the shared validator against this spec's IDs only (FR-002, FR-009).
- `collect` reads `ui-states.toml` through the existing `read()` closure. That closure serves only names that `git ls-tree` lists under `<feature>/` at head, and it reads them with `git cat-file` under `FILE_LIMIT`. So another feature's file and the working-tree copy are out of reach (FR-003, FR-014, AC-005, AC-006). The new code adds no git or gh call, program or fetch.
- The comment at the call site accepts that a failed `cat-file` shows as "not UTF-8 text". That settles plan-review F-001 explicitly. The UI section is derived data, and the next checkpoint reads it again.
- `merge_ui_states`:
  - gives the repository's reason first;
  - places repository entries before feature entries;
  - applies the 50-entry limit to the total;
  - keeps `openapi` and `api_error` through `replace` (FR-005, FR-008).
- Repository entries carry `criteria=()`, so they never attach to a criterion (FR-006). UI results do not feed evidence states (FR-012).
- The `AGENT_LABEL` constant marks feature entries in both the criterion detail and the UI section. Names still go through `inert()`, and links are still built by Ballast (FR-010, FR-011).
- ADR-0019 (proposed, agent-provisional) records the architecture change, and ADR-0006 carries an amendment note pointing to it. The code stays stdlib-only.

The implementation still matches the spec, plan and contracts. I found no new defect.

## Checks I ran

- `uvx ruff check` and `uvx ruff format --check`: passed (478 files formatted).
- `python -m unittest tests/test_governance.py`: 23 tests, OK.
- `python -m unittest tests/test_packet.py tests/test_governance.py`: 101 tests ran in 32 s, with 83 failures and 27 errors. Every failure I inspected is the Draft PR checkpoint stopping at `failed-retryable/git-untrusted` ("git not found outside working trees") and leaving the packet `pending/no-pr`. The cause is the checkout's guard `git` placed first on `PATH` inside an agent step. I could not rerun with a system `git` first on `PATH`: that needed an approval this session cannot get.

The packet suite runs in about 30 s, so this change is not the cause of the 30-minute timeout. Still, neither this run nor any earlier step has recorded `tests/test_packet.py` passing. The 19 acceptance criteria depend mostly on that suite, so they have no observed passing evidence. A human must get a passing fast gate from the operator's terminal or CI before merge.

`AGENTS.md` was not used: `CLAUDE.md` holds the project instructions. `docs/policies/project/engineering.md` is absent.

<!-- ballast-findings: begin -->
## Findings (recorded from the review draft)

- F-001 (low, spec-ambiguity, open): After 1.0.0, a ballast.toml whose [[review.ui_states]] names criteria reads configuration invalid. The spec and ADR-0019 accept this break, but the PR title or changelog entry should state the migration: move those entries to specs/&lt;feature&gt;/ui-states.toml.
- F-002 (medium, missing-test, accepted-provisionally): No run has observed tests/test_packet.py passing. The checks after cycles 1-3 timed out and every agent step stops the suite at git-untrusted. The cause looks environmental (D-001, D-002), but no fix cycle remains and the failed check already stops the run. A human must see the fast gate pass in the operator's terminal or CI before merge.
<!-- ballast-findings: end -->
