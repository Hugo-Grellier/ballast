# ADR-0027: the human approves the spec; living specs record behavior; a computed verdict decides the merge

- Status: proposed (2026-10-21, [#264](https://github.com/Hugo-Grellier/ballast/issues/264), Epic [#263](https://github.com/Hugo-Grellier/ballast/issues/263)). Merging its PR is the human approval that accepts it; the leaves implement it.
- Risk: R2 (changes merge authority and admission semantics, invariants of `AGENTS.md`).
- Amends: [ADR-0023](0023-ballast-2-portable-agent-workflow.md) ("routine tasks need no parallel spec tree", "preserve human merge approval") and [ADR-0024](0024-ballast-2-migration.md). Extends [ADR-0026](0026-r0-merge-on-reviewed-green-head.md) (R0 merge on a reviewed green head, [#219](https://github.com/Hugo-Grellier/ballast/issues/219)) to R1. Their text stays as history; where they conflict, this ADR governs once accepted.
- Basis: operator's conversation of 2026-10-21, after reading [Interlock](https://github.com/renzrollon/interlock) and [OpenSpec](https://github.com/Fission-AI/OpenSpec).

## Context

Every PR needs a human merge approval. In practice the human cannot reread a
diff of hundreds or thousands of lines, so the approval either stalls the queue
or certifies what nobody read. The decision the human is good at, "is this the
behavior we want", is made late, after the code exists, when a wrong idea is
most expensive to undo.

Ballast also has no durable description of what the system currently does.
Issues hold scope and progress, PRs hold evidence, ADRs hold decisions; the
behavior itself is spread across code and tests. A reviewer or a new worker
reconstructs it each time.

Interlock and OpenSpec move the human checkpoint to a short behavior spec before
implementation, keep living specs of current behavior, and replace the merge
approval with checks that have a correct answer. Ballast already has the
execution half (bounded workers, verified routes, independent review on an
exact head, CI on that head); it lacks the spec half.

## Decision

### Living specs are mandatory

- `docs/specs/` holds one Markdown file per capability describing current
  behavior. A file opens with one or more `Covers: GLOB` lines naming the source
  paths whose behavior it describes. Under it, `### Requirement: NAME` carries a
  SHALL statement, and `#### Scenario: NAME` carries WHEN/THEN lines and one or
  more `Test: path::Class::method` references to the tests that enforce it. A
  scenario without a test reference is invalid. (`specs/` at the root is v1
  history and stays untouched.)
- Specs state behavior only. Plans stay in issues and `docs/plans/`, decisions in
  ADRs, progress on GitHub. GitHub stays authoritative for issue relationships,
  PRs, merges and CI; the specs are authoritative for intended behavior, which no
  other artifact records, so they add no second source of truth.
- Every behavior-bearing PR (R1, R2) updates the affected spec in the same PR.
  Git keeps the history: no change folders and no archive step.
- A deterministic stdlib checker (`tools/spec_check.py`, run by the fast gate
  and CI) validates the format, that every cited test exists, and that no two
  files cover the same path.
- A changed path is *covered* when a `Covers:` glob of some spec matches it.
  Documentation, tests and `docs/specs/` itself need no coverage. Existing
  behavior is described once, without code changes; until then, an R1 PR that
  changes an uncovered path gets `HUMAN`.

### The canonical delta

The approved object is the *normalized delta*: for each requirement and
scenario that is added, modified or removed, its capability file, kind, name,
resulting text (SHALL, WHEN/THEN) and, for modified or removed entries, the base
text it replaces. `Test:` lines, `Covers:` lines, open questions and risk are not
part of it, so choosing or renaming tests and resolving questions need no new
approval. The hash is SHA-256 over a canonical JSON serialization of that list,
sorted by file and name. `spec_check.py` computes it from a delta document posted
on the issue and from a Git diff of `docs/specs/` the same way, so both sides
compare equal exactly when they describe the same behavior change.

If the base text of a modified or removed entry no longer matches the target
branch (a concurrent PR changed it), the delta is stale: the verdict is `HUMAN`
until a new delta is approved.

### The human approves the spec delta

- For an R1 or R2 leaf, the clarify/plan phase posts the delta document on the
  issue together with open questions, the proposed risk and the hash. R0 work
  and investigations skip it.
- The human approves by a direct issue comment that quotes the hash and the
  risk. The approved risk is a floor: a PR or reviewer classification below it
  gives `HUMAN`.
- A relayed approval (the coordinator quoting the human) stays valid for plans,
  as today, but never yields `MERGE`: an R1 PR whose spec approval is relayed
  gets `HUMAN`.
- The implement dispatch refuses an R1/R2 leaf without an approval link whose
  hash matches the posted delta. A changed requirement or scenario needs a new
  approval. Questions that change no observable behavior stay "decide, flag and
  continue" (Epic #149).
- An R1 PR whose diff changes no spec is not R1 under this ADR: it is either R0
  (ticked and confirmed as such under ADR-0026) or it needs an approved empty
  delta, which records that the human accepts "no behavior change".

Trust boundary: Ballast's agents post with the operator's GitHub identity, so a
"direct" comment cannot be told apart from one an agent wrote. The rule rests,
as R2 approvals already do, on the coordinator never posting an approval except
as a marked relay. A separate identity for agents would make it checkable; that
is a follow-up, not part of this ADR.

### Conformance is checked, not reread

- CI (`spec_check.py`, no network) recomputes the hash of the PR's `docs/specs/`
  diff against its base and compares it with the hash stated in the PR body's
  Spec section. `pr_body.py` requires that section, with the hash and the
  approval comment link, for R1 and R2.
- `merge_check.py` (local, with `gh`) then checks that the linked comment is on
  the linked issue, is direct, quotes the same hash, postdates the posted delta,
  and that the delta's base text still matches the target branch. "Conformance
  green" means both checks pass on the PR head.
- Each added or modified scenario cites a test. The test review records, per
  such scenario, that the test fails on the base (a test file that does not exist
  on the base counts as failing) and passes on the head; for a removed scenario,
  that its tests were removed or no longer assert it. The verdict trusts that
  review record; it does not rerun tests on the base.
- A finding is dismissed only with a `file:line` citation in the diff, and the
  pair reassesses it; the author still cannot dismiss a blocker alone.

### A computed verdict decides the merge

`tools/merge_check.py` returns one verdict for the PR's current head, with its
reasons and what would raise it:

- `MERGE`: the ADR-0026 conditions hold (independent review approved the exact
  head and confirmed the risk, every required check passed on it, not a draft,
  nothing changed after review, no excluded path), and the PR is R0, or R1 with a
  direct spec approval, green conformance and every changed path covered.
- `HUMAN`: R2; an excluded path; a risk below the approved floor, disputed or
  raised; a relayed spec approval; a stale delta; an uncovered changed path. The
  output is the handoff: approved spec, risky paths, surviving review findings.
  The human reviews that, not the full diff.
- `BLOCK`: missing or stale review, a failing or missing required check, a
  draft, a head that moved, or a hash mismatch.

Excluded paths are the ADR-0026 list plus the project's human-only globs in
`project/workflow.md`. Ballast declares its own R2 surfaces there: at least
`tools/merge_check.py`, `tools/spec_check.py`, `tools/pr_body.py`,
`tools/admission.py`, `tools/coordinate.py`, `tools/worker.py`,
`tools/worktree.py`, `tools/codex.py` and `.github/`. A PR changing the gate
that would merge it therefore never merges itself.

The coordinator merges only on `MERGE`, with `--squash --match-head-commit`. The
merge is reported as merged under this ADR, never as a human approval.

### Unchanged

R2 changes still need explicit human approval of the plan and of the merge.
Release, deployment, destructive cleanup and paid services still need a human.
Agents never run in CI. A project can keep a human merge for every PR in its
`project/workflow.md`. This ADR depends on ADR-0026; its PR merges after
[#252](https://github.com/Hugo-Grellier/ballast/pull/252).

## Invariants that change

| Text | Today | After | Leaf |
| --- | --- | --- | --- |
| `AGENTS.md` (`CLAUDE.md` links to it): Risk section, Invariants "Merge, release … need explicit human approval" | every PR needs human merge approval | the verdict rule; R2, release, destructive and paid actions keep a human | [#269](https://github.com/Hugo-Grellier/ballast/issues/269) |
| `AGENTS.md` layout and architecture lines | `specs/` is history; no living specs | `docs/specs/` is authoritative for current behavior | [#265](https://github.com/Hugo-Grellier/ballast/issues/265) |
| `templates/AGENTS.md`, `templates/policies/workflow.md` ("an agent never merges") | every PR needs human merge approval | the verdict rule, with the opt-out to keep a human merge | #269, [#270](https://github.com/Hugo-Grellier/ballast/issues/270) |
| ADR-0023 ("routine tasks need no parallel spec tree", "preserve human merge/release approval"), ADR-0024 ("no agent merges") | as quoted | living specs for every behavior change; merges follow the verdict | this ADR; text changes in #265 and #269 |
| `docs/issue-workflow.md` step 3 | routine plans need no human checkpoint | R1/R2 need a directly approved spec delta | [#267](https://github.com/Hugo-Grellier/ballast/issues/267) |
| `docs/pair-review.md`, test review skill | criteria mapped to evidence | scenario fail-on-base evidence; dismissal needs `file:line` | [#268](https://github.com/Hugo-Grellier/ballast/issues/268) |

## Consequences

The human looks at the spec, the one place they can judge, and at the R2
handoff; R0 and R1 PRs complete without waiting. Living specs give reviewers and
workers the current behavior without reconstructing it.

The spec approval becomes the main human decision: a careless approval approves
the wrong behavior, so the delta stays short and in behavior terms. Behavior no
scenario describes is not protected by the verdict; the engineering and test
reviews still examine the whole diff. A misclassified R2 change merged as R1 is
the main residual risk, bounded by the approved risk floor, the reviewer's risk
confirmation, the excluded paths and the revert workflow. A coordinator that
posted an approval as if it were the human would defeat the spec gate; that is
the trust boundary named above, the same one R2 approvals rely on today.
Bootstrapping specs for existing behavior is real work and delays `MERGE` for
paths not yet covered.

## Alternatives

- Adopt OpenSpec as a dependency: it brings a Node toolchain, which conflicts
  with stdlib-only helpers, and a change-folder tree that duplicates what the PR
  diff already shows. Its format is reused; the tool is not.
- Adopt Interlock: it targets Claude Code only and replaces execution Ballast
  already verifies (routes, claims, settlement). Its principles are reused:
  one human checkpoint at the spec, decisions with a correct answer moved into
  code, degradation stated rather than silent.
- Keep the human merge for every PR: the status quo, rejected because it
  certifies diffs nobody reads.
- Merge R1 on review and CI alone, without a spec: no human ever judges the
  intended behavior; rejected.
