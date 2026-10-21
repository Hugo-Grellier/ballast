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
  scenario without a test reference is invalid. Requirement names are unique
  within a file and scenario names within a requirement. (`specs/` at the root is
  v1 history and stays untouched.)
- Specs state behavior only. Plans stay in issues and `docs/plans/`, decisions in
  ADRs, progress on GitHub. GitHub stays authoritative for issue relationships,
  PRs, merges and CI; the specs are authoritative for intended behavior, which no
  other artifact records, so they add no second source of truth.
- Every behavior-bearing PR (R1, R2) updates the affected spec in the same PR.
  Git keeps the history: no change folders and no archive step.
- A deterministic stdlib checker (`tools/spec_check.py`, run by the fast gate
  and CI) validates the format and uniqueness, that every cited test exists, and
  that no tracked file (`git ls-files`) is matched by the `Covers:` globs of two
  spec files.
- A changed path is *covered* when a `Covers:` glob of some spec matches it, or
  when it matches a coverage-exempt glob that `project/workflow.md` lists (for
  example documentation and test directories). There is no implicit exemption:
  with no list, every changed path needs coverage. Existing behavior is described
  once, without code changes; until then, an R1 PR that changes an uncovered path
  gets `HUMAN`.

### The canonical delta

The approved object is the *normalized delta*: a list of entries, each keyed by
(capability file, requirement name, scenario name or none for the requirement
itself) with a change type (added, modified or removed), the resulting text
(SHALL, WHEN/THEN) and, for modified or removed entries, the base text it
replaces. Moving a scenario to another requirement is a removal plus an
addition. Text is normalized before hashing: LF line endings, trailing
whitespace removed, wrapped lines of one paragraph joined by a single space.
`Test:` lines, `Covers:` lines, open questions and risk are not part of the
delta, so choosing or renaming tests and resolving questions need no new
approval. The hash is SHA-256 over a canonical JSON serialization of the list
sorted by its keys. `spec_check.py` computes it the same way from a delta
document posted on the issue and from the three-dot Git diff
(merge-base...head) of `docs/specs/`, so both sides compare equal exactly when
they describe the same behavior change.

If the base text of a modified or removed entry no longer matches the target
branch (a concurrent PR changed it), the delta is stale: the verdict is `BLOCK`
until a new delta is posted and approved. A stale delta is never handed to the
human to merge as is.

### The human approves the spec delta

- For an R1 or R2 leaf, the clarify/plan phase posts the delta document on the
  issue together with open questions, the proposed risk and the hash. R0 work
  and investigations skip it.
- The approval is an issue comment that quotes the hash and the risk: either
  the human's own comment, or a coordinator comment relaying the human's words
  verbatim with their date, marked as relayed, as for R2 approvals today. Both
  count for `MERGE` (operator decision, 2026-10-21). The approved risk is a
  floor: a PR or reviewer classification below it gives `HUMAN`.
- The implement dispatch refuses an R1/R2 leaf without an approval whose quoted
  hash equals the hash it recomputes from the posted delta document. A changed
  requirement or scenario needs a new approval. Questions that change no
  observable behavior stay "decide, flag and continue" (Epic #149).
- An R1 PR whose diff changes no spec is not R1 under this ADR: it is either R0
  (ticked and confirmed as such under ADR-0026, and subject to the risk floor of
  its issue) or it needs an approved empty delta, which records that the human
  accepts "no behavior change". A reviewer cannot waive the spec change alone.

Trust boundary: Ballast's agents post with the operator's GitHub identity, so
no check can tell a human comment from one an agent wrote, and a relay is by
design written by the coordinator. The spec gate therefore rests on the
coordinator posting an approval only when the human gave it, quoted verbatim,
as R2 approvals already do. A separate identity for agents
([#274](https://github.com/Hugo-Grellier/ballast/issues/274)) would make the
human's own comments checkable; relays would still rest on that trust.

### Conformance is checked, not reread

- CI (`spec_check.py`, no network) recomputes the hash of the PR's three-dot
  `docs/specs/` diff and compares it with the hash stated in the PR body's Spec
  section, for early feedback. `pr_body.py` requires that section, with the hash
  and the approval comment link, for R1 and R2.
- `merge_check.py` (local, with `gh`) does not trust the PR body: it recomputes
  the spec hash from the reviewed head itself, recomputes the posted delta's
  hash from that comment's content, and requires both to equal the hash the
  approval quotes. It also requires the approval to be on the PR's closing issue
  and to postdate the delta, and the delta's base text to still match the target
  branch. A delta or approval comment edited after the approval gives `BLOCK`.
  "Conformance green" means these checks pass on the reviewed head.
- Each added or modified scenario cites a test. The test review records, per
  such scenario, that the test fails on the base (a test file that does not exist
  on the base counts as failing) and passes on the head; for a removed scenario,
  that its tests were removed or no longer assert it. The verdict trusts that
  review record; it does not rerun tests on the base.
- A finding is dismissed only with a `file:line` citation in the diff, and the
  pair reassesses it; the author still cannot dismiss a blocker alone.

### A computed verdict decides the merge

`tools/merge_check.py` returns one verdict for the PR's current head, with its
reasons and what would raise it. On every PR, R0 included, it resolves the
closing issue and reads the risk proposed or approved there.

- `MERGE`: the ADR-0026 conditions hold (independent review approved the exact
  head and confirmed the risk, every required check passed on it, not a draft,
  nothing changed after review, no excluded path), the confirmed risk is not
  below the issue's risk, and the PR is R0, or R1 with an approval, green
  conformance and every changed path covered.
- `HUMAN`: R2; an excluded path; a confirmed risk below the issue's proposed or
  approved risk; a disputed or raised risk; an uncovered changed path; a
  missing, unreadable or malformed `project/workflow.md` on the target branch.
  The output is the handoff: approved spec, risky paths, surviving review
  findings. The human reviews that, not the full diff.
- `BLOCK`: missing or stale review, a failing or missing required check, a
  draft, a head that moved, a hash mismatch, an edited delta or approval, or a
  stale delta.

Excluded paths are the ADR-0026 list plus the project's human-only globs in
`project/workflow.md`. `merge_check.py` reads that file from the target branch,
never from the PR head, so a PR cannot remove its own exclusion. Ballast
declares its own R2 surfaces there, the code and the text that define the gate:
at least `tools/merge_check.py`, `tools/spec_check.py`, `tools/pr_body.py`,
`tools/admission.py`, `tools/coordinate.py`, `tools/worker.py`,
`tools/worktree.py`, `tools/codex.py`, `tools/progress.py`, every module these
import, `tests/parallel.py` and any other runner CI executes as a gate,
`.github/`, `project/workflow.md`, `AGENTS.md`, `CLAUDE.md`,
`docs/issue-workflow.md`, `docs/pair-review.md`, `docs/adr/`,
`templates/policies/` and `templates/skills/ballast-*`. These paths are excluded
whatever the stated risk and whatever their coverage, so a PR changing the gate
that would merge it, in code or in prose, never merges itself.

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
| `docs/issue-workflow.md` step 3 and "separate spec/plan/task files are unnecessary" | routine plans need no human checkpoint; no spec files | R1/R2 need an approved spec delta; living specs updated in the PR | [#267](https://github.com/Hugo-Grellier/ballast/issues/267) |
| `docs/issue-workflow.md` step 6 ("ready for human merge", "Stop at human merge"), `docs/standalone.md`, `README.md` and `docs/pair-review.md` as amended by #252 | stop at a human merge (R1/R2 after #252) | stop at the verdict; merge on `MERGE`, hand off on `HUMAN` | #269 |
| `docs/migration.md` ("human merge stays the approval") | as quoted | the spec approval and the verdict | #270 |
| `docs/pair-review.md`, test review skill | criteria mapped to evidence | scenario fail-on-base evidence; dismissal needs `file:line` | [#268](https://github.com/Hugo-Grellier/ballast/issues/268) |

## Consequences

The human looks at the spec, the one place they can judge, and at the R2
handoff; R0 and R1 PRs complete without waiting. Living specs give reviewers and
workers the current behavior without reconstructing it.

The spec approval becomes the main human decision: a careless approval approves
the wrong behavior, so the delta stays short and in behavior terms. Behavior no
scenario describes is not protected by the verdict; the engineering and test
reviews still examine the whole diff. A misclassified R2 change merged as R1 is
the main residual risk, bounded by the issue's risk floor, the reviewer's risk
confirmation, the excluded paths and the revert workflow. A coordinator that
posted or relayed an approval the human never gave would defeat the spec gate;
that is the trust boundary named above, the same one R2 approvals rely on today,
and with relays accepted for `MERGE` it is the gate's main assumption.
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
