# Plan review: Declare UI states per feature

- Review: plan
- Reviewer: claude/claude-opus-5-5 (independent context, same provider as the author because of DEC-0004)
- Artifact: `specs/142-feature-ui-states/plan.md`, with `research.md`, `data-model.md`, `contracts/ui-states-file.md`, `contracts/packet-ui-section.md` and `quickstart.md`
- Verdict: agent-provisional; see the findings rendered by the recorder

## What was read

- `AGENTS.md`, `CLAUDE.md`, `docs/policies/workflow.md`, `docs/policies/engineering.md`, `docs/policies/project/workflow.md` (R2 boundaries) and `docs/policies/project/testing.md`. There is no `docs/policies/project/engineering.md`.
- `intent.md` (agent-provisional, PD-0006), `spec.md` (AC-001 to AC-019, FR-001 to FR-018), `discovery.md` decisions D-01 to D-07 as cited by the spec, and the run record `autonomous/record.md`.
- `tasks.md` and `decisions.md` do not exist yet. That is expected at the plan gate; tasks come next.
- Current code: `tools/spec_workflow/packet.py` (`review_config`, `_ui_states`, `blob`, `collect` and its `read` helper, `_detail`, `_ui_text`, `_ui_lines`, `_source`, `FILE_LIMIT`, `UI_LIMIT`) and the test class layout of `tests/test_packet.py` (`ReviewConfigTests`, `UiStateTests`, `HostileTextTests`, `OpenApiTests`).
- `docs/adr/0006-review-packet-reads.md` (line 28 holds the configuration statement the plan amends) and `docs/adr/0007-recoverable-installation.md` (the precedent for the italic amendment note). The next free ADR number is 0019; `docs/adr/` holds 0001 to 0018.
- `templates/policies/spec-kit-workflow.md`, acceptance packet section, which today documents `[[review.ui_states]]` with criteria.

## Requirement coverage

Each spec requirement maps to a plan element:

- FR-001, AC-006: `collect` reads `ui-states.toml` through the existing `read` helper, which serves only names `git ls-tree` lists at head and reads them with `git cat-file` at head. The spec and the feature file therefore come from one commit, and the working tree is never read (research R1). Verified against `collect` lines 842-861.
- FR-002, FR-003, AC-001 to AC-003, AC-005, AC-009: one validator `_ui_states(value, source, spec_ids)`. The feature source always gets the head commit's `spec_ids`, so another feature's spec or file cannot be consulted. `review_config(root)` drops `spec_ids`, which makes the repository table's validity independent of the PR (research R2). `review_config` has one caller (`collect`, line 1027), so dropping the argument breaks nothing else.
- FR-004, AC-011: the repository `criteria` key, even `[]`, is checked first within each entry and gives the move reason.
- FR-005, AC-012, D-07: the total limit is applied in `merge_ui_states`. The single-source limit inside `_ui_states` is kept.
- FR-006, FR-007, AC-007, AC-008, AC-010: repository entries get `criteria=()`, so the existing `Criterion.ui` filter (line 1037) never attaches them. Research R5 keeps the absent versus declared-empty distinction.
- FR-008, FR-009, AC-004: every failure is a fixed reason prefixed by the source, and the section is one line. TOML, UTF-8 and size failures are file-level reasons. The `blob` helper already returns the too-large flag and `None` for non-UTF-8 text.
- FR-010, FR-011, AC-014, AC-015: one fixed label, `agent-declared in ui-states.toml`, rendered in parentheses so it cannot form a Markdown link with what follows. Names stay `inert(name, 80)`. Links are built only by `_blob` and `_run_link` from a validated `safe_path` or an integer run ID. The `check` value is never rendered.
- FR-012, AC-016: evidence states are computed before UI results attach (line 1036 replaces only `ui`). A three-way comparison test is planned.
- FR-013, FR-014, FR-015: no change to the protected inputs, the trust baseline, programs or GitHub calls. The plan reuses the `git cat-file` reads ADR-0006 already allows for feature artifacts and stays on `tomllib`.
- FR-016, FR-017, AC-017 to AC-019: a policy template rewrite, a new ADR-0019, and an amendment note on ADR-0006 line 28 in the ADR-0007 style.
- FR-018: the quickstart maps each scenario to an AC. Research R3 explains why every existing `ReviewConfigTests` UI case changes: each one uses a repository entry with `criteria`, so each now gives the move error. That is the change FR-018 allows. The cases are rewritten as criterion-less entries so that each rule stays covered.

## Architecture and authority

- The R2 boundary is stated once and correctly: the review packet's trust model. Research R9 checks the other three R2 boundaries against `docs/policies/project/workflow.md` and finds them unchanged. That matches the code: no launcher, settings, setup or ignore-rule change is planned.
- Source authority is clear and single: `ballast.toml` for repository-wide screens, the head commit's `ui-states.toml` for criterion-linked screens, and the head commit's `spec.md` for criterion IDs. The packet stays a derived view. No second source of truth is introduced, because the repository table can no longer hold criteria.
- The agent gains only labelled, inert links beside its own feature's criteria. That is the bound the operator's decision 2b in the Issue #142 intake comment accepted, and research R8 explains why paths are not limited to the feature directory.
- The proposed ADR-0019 is the right record for an accepted-architecture change. It is marked proposed and agent-provisional.
- The failure order (repository first, research R4) settles the edge case the spec left to the plan, and gives a stable reason across PRs.

## Failure behavior and compatibility

- An existing `ballast.toml` whose UI states carry criteria becomes `configuration invalid` with the move reason. The spec accepts this break and provides no automatic migration (spec Assumptions). The packet still publishes.
- An unreadable `ballast.toml` keeps #19's behavior (no `[review]` table), so feature entries still show. `review is not a table` stays unprefixed and is shared with the API section.
- The plan adds `ui-states.toml` to `too_large` through the shared helper. `too_large` is read only by `_source` for named sources, so the addition has no side effect.

## Complexity

The change is small and local: about 60 lines in one module, two dataclass fields with defaults, two pure functions and one validator argument. Nothing unrelated is refactored. A second validator was rejected because it would duplicate seven rules.

## Residual points

The recorder renders the findings. None blocks tasks: each is a precision point for the task or test author.

<!-- ballast-findings: begin -->
## Findings (recorded from the review draft)

- F-001 (low, spec-ambiguity, open): Research R1 maps a listed ui-states.toml whose text is None to 'not UTF-8 text' unless too large, but Step.blob also returns None when git cat-file -s or blob fails for another reason. A transient git read failure would then show a misleading fixed reason instead of failing retryable as spec.md does. Tasks should either fail retryable on a git error or accept the conflation explicitly; either way the packet is not stopped wrongly by agent data.
- F-002 (low, missing-test, open): merge_ui_states returns a ReviewConfig built from the repository config; the plan does not state that openapi and api_error are carried over, and no quickstart scenario combines an [review] openapi path with a feature file. Add one assertion (API section unchanged when a feature file is present) so a merge that drops the API fields is caught.
- F-003 (info, spec-ambiguity, open): The fixed-reasons table in contracts/ui-states-file.md lists 'more than 50 UI states' before 'ui_states is not a list of tables' for each source, while _ui_states and research R4 check the list shape first. Reorder the table rows so the contract matches the validation order the tests will assert.
- F-004 (info, spec-ambiguity, open): The plan says the installed docs/policies/ copy refreshes via ballast setup. In this repository that copy comes from the pinned release in ballast.toml, so it only changes after a release and a pin bump, not in this PR. No edit to docs/policies/ is needed; the wording is only imprecise.
<!-- ballast-findings: end -->
