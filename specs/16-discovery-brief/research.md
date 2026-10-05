# Research: Source-backed discovery brief

Each entry resolves an open point of the plan's Technical Context or an `[I]` assumption the spec left to planning. Sources are repository paths read for this plan.

## R-01: Where discovery gets the Issue and its comments

- **Decision**: Extend the runner's Issue snapshot (`autonomy.render_issue_snapshot`, `.specify/workflow-state/issues/<N>.md`) with a `## Comments` section listing every Issue comment (author, author association, date, body), and write the snapshot at the start of a human-gated run too. The human-gated start derives `<N>` from `feature_directory` (`specs/<N>-<slug>`, already enforced by `FEATURE_PATTERN`). When `gh` is missing or the read fails, the human-gated start writes a snapshot that says the Issue was unavailable and continues; the Autonomous start keeps failing closed as today.
- **Rationale**: Agent steps cannot call `gh` (Autonomous agents run under `bwrap` without credentials; human-gated Claude Bash is limited to Spec Kit scripts and read-only Git, `docs/policies/spec-kit-workflow.md` "Headless permissions"). Today the snapshot holds only the body and the intake scope comment (`autonomy.py:1874`), and a human-gated run has no snapshot at all, so FR-002 ("the Issue, its comments") cannot be met by the agent alone. The Autonomous eligibility check already lists the comments endpoint (`autonomy.py:1783`); the runner reads, it does not write. The snapshot header already declares the content untrusted requirements data (FR-005, AC-003).
- **Alternatives considered**: Let the agent call `gh` (adds agent authority: violates FR-016 and BL-INV-003, and would be R2). Pass comments through the `idea` input (unbounded shell-visible input, no structure, no cap). Make a missing Issue fatal in human-gated runs (breaks offline human-gated use that works today; the spec's edge case asks for an "unavailable" source instead).
- **Risk note**: This is a read of the Issue the run is for, by the operator-side runner, through the same `gh` the Draft PR checkpoint and Autonomous start already run. It does not change what `ballast` downloads (the fixed standard repository and ref rules), the launcher's trust inputs, agent permissions or install paths, so it stays R1 under `docs/policies/project/workflow.md`. The plan review must confirm this reading.

## R-02: One bundled question round in a human-gated run whose agents are headless

- **Decision**: Use the existing "human-only steps surface as a failed validation" pattern (`docs/policies/spec-kit-workflow.md` "Workflow runner contract"). The `discover` agent step writes every open high-impact decision into `discovery.md` with options, consequences and a recommended default, and leaves each `Answer` empty. The trusted `validate-discovery` step then:
  1. passes with no interaction when no decision is `open` (AC-009);
  2. otherwise records the question set in operator state, prints all questions in one message and fails, telling the operator to fill each `Answer` line in `discovery.md` and run `ballast run resume <run>` (one round, AC-006);
  3. on resume, accepts the answers only for questions it recorded as asked and only if the question text is unchanged, and marks them operator-answered.
- **Rationale**: `speckit.clarify` cannot ask anything in a headless `claude -p` step; the current workflow already relies on a failed validation plus resume for human-only input. Recording what was asked in the operator state directory (`launcher.state_dir`, which no agent can write) lets the validator refuse an `Answer` an agent wrote before the round was asked (AC-008, FR-010), the same defence `record-intent` uses for approval blocks (#29).
- **Alternatives considered**: A Spec Kit `gate` step (gates offer only approve/reject, cannot carry answers, and would prompt even when nothing is open, violating AC-009). A separate operator command such as `record-answers` (extra command to learn; the resume already proves an operator action). Interactive `speckit.clarify` as the round (one question at a time, up to five; the behavior the Issue wants to replace).

## R-03: Recording Autonomous assumptions from discovery

- **Decision**: Reuse the existing `clarification` decision point. The discover command writes one draft per adopted default as `autonomous/drafts/clarification-discovery-<n>.json` (decision `assume`, `assumption.reversible: true`, `assumption.question` starting with the brief's decision ID, for example `D-02: …`). A new `record-discovery` shell step runs `record-decision --point clarification`. Unsafe gaps use the existing `block.json` draft and `RECONCILE_STATUS: BLOCKED_DECISION` with category `decision` or `contradiction`.
- **Rationale**: `clarification` is already a multi-entry `assume` point whose drafts must be reversible (`artifacts.py:1040`), whose recorder accepts zero drafts (`_expected_drafts`) and whose entries `record.md` and the Draft PR body already list (AC-010, SC-003). The draft-name pattern `clarification-[a-z0-9-]{1,40}.json` already admits the `discovery-<n>` suffix. No change to `DECISION_POINTS`, the hash-chained log, the record renderer or the PR body is needed. The block contract already requires a condition, at least two options with consequences, recovery and evidence (AC-011).
- **Alternatives considered**: A new `discovery` decision point (touches the log schema, record renderer, Draft PR summary and `SINGLE_POINTS` accounting for no new information). Writing assumptions only into the brief (not visible in the run record; fails AC-010).

## R-04: Traceability marker syntax

- **Decision**: One inline syntax for the brief and the spec, matching what `specs/16-discovery-brief/spec.md` already uses:
  - `[S: <source>]`: a cited source (Issue body, `Issue comment <author> <date>`, a repository path with optional section, or existing behavior as `path:line` or `path` + symbol);
  - `[I]`: an inference by the agent;
  - `[O: D-NN]`: an operator answer to brief decision `D-NN` (human-gated only);
  - `[P: D-NN]`: an agent-provisional assumption for decision `D-NN` (Autonomous only);
  - in `spec.md` also `[B: D-NN]` or `[B: <section>]`: a brief item.
  The validator matches the marker shape only (`\[(S: [^\]]+|I|O: D-\d{2}|P: D-\d{2}|B: [^\]]+)\]`); whether a cited path exists is checked for `[S: …]` values that look like repository paths, and the rest is left to review.
- **Rationale**: Short, greppable, already in use in this repository's own spec, and distinct from Markdown links so a link alone does not count as provenance. Separate `[O:]` and `[P:]` keep operator answers and agent assumptions apart (AC-008, AC-013).
- **Alternatives considered**: Footnotes (not line-local; harder to check deterministically). YAML front matter per item (heavy for prose). Requiring a Markdown link per item (Issue comments and existing behavior have no stable link inside the checkout).

## R-05: Deterministic Issue acceptance-criterion coverage (AC-016)

- **Decision**: The validator extracts the Issue's criteria from the snapshot's `## Body`: the list items under the first Markdown heading whose text contains "acceptance criteria" (case-insensitive), until the next heading. The brief must list each one, verbatim after whitespace normalization, as `IAC-n` under `## Issue acceptance criteria`. `spec.md` must mention every `IAC-n`, either in an acceptance criterion's marker (for example `[S: IAC-2]`; a prose reference such as `[S: Issue #16 AC 2]` alone does not count, the `IAC-n` token is what is checked) or on a line under a `Non-goals` or `Out of scope` heading. When the snapshot is unavailable or has no such heading, the brief says so and the coverage rule checks only the `IAC-n` items the brief lists.
- **Rationale**: Ballast's own Issue template and intake skill produce a `## Acceptance criteria` checklist (snapshot of #16 above), so the common case is checked deterministically; free-form Issues degrade to a brief-declared list that review covers, without false failures.
- **Alternatives considered**: Matching criterion text inside `spec.md` (rephrasing is normal and would fail spuriously). Leaving coverage to review only (the spec's AC-016 asks for a failing validation).

## R-06: Which specs the traceability check applies to

- **Decision**: The spec traceability and coverage checks run when `<f>/discovery.md` exists **or** the operator state records that discovery ran for the feature (written by `validate-discovery`). In the second case a missing brief fails the spec check.
- **Rationale**: Implements PD-0002 (no retrofit of `specs/12-…`, `17-…`, `27-…`) while denying an agent the shortcut of deleting the brief to skip the check.
- **Alternatives considered**: Repository-wide check (fails every completed feature). A flag in `spec.md` (agent-writable, so it could be dropped).

## R-07: Brief name, location and lifecycle

- **Decision**: `specs/<N>-<slug>/discovery.md`, committed with the feature. On a rerun or `Continue #N`, the discover command updates the existing brief and lists what changed under `## Changes` instead of regenerating it. The brief starts with the marker `<!-- ballast-discovery: input evidence -->` and a sentence pointing to `spec.md` and `intent.md` as the authority (AC-018).
- **Rationale**: Feature-local artifacts sit next to `spec.md` (spec Assumptions). `intent.md` binds only the `spec.md` digest (`artifacts.py` `spec_digest`, `check_intent`), so a brief edit after intent never changes or invalidates recorded intent (AC-017, SC-006) without any new code.
- **Alternatives considered**: `brief.md` (less specific). Keeping the brief in ignored run state (not reviewable in the PR; reviewers need it to trace requirements, SC-004).

## R-08: How specify and clarify consume the brief

- **Decision**: Pass instructions through the existing workflow `input.args` of the `specify` and `clarify` steps: specify writes `spec.md` from `discovery.md`, putting a marker on every FR and AC and citing each `IAC-n`; clarify (human-gated `speckit.clarify`, Autonomous `speckit.ballast.clarify`) must not reopen a decision the brief settled, and may add a `NEEDS CLARIFICATION` marker only for a new contradiction. `speckit.ballast.clarify.md` gets one added rule to that effect. The Ballast spec template states the marker convention in its comments. No patch to upstream `speckit.specify` or `speckit.clarify`.
- **Rationale**: Keeps the Spec Kit patches (`tools/spec-kit/*.patch`) unchanged and the authority with the validator, which fails a spec without markers regardless of how it was written.
- **Alternatives considered**: Patching upstream skills (more patch surface to maintain on each Spec Kit upgrade).

## R-09: Write boundary of the discover step (FR-016)

- **Decision**: No new permission. In Autonomous runs `validate-discovery` also fails when `git status --porcelain` shows a change outside `<f>/` (the worktree was clean at `autonomous-preflight`). Human-gated runs rely on the unchanged Claude/Codex permission model; the command text names the only files it may write.
- **Rationale**: The Autonomous tree is known clean, so the check is exact there; a human-gated worktree may legitimately hold operator changes, so the same check would give false failures.
- **Alternatives considered**: A pre-discovery baseline in human-gated runs (extra step and state for a boundary the permission model already bounds).
