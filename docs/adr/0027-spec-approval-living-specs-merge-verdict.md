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
  behavior: `### Requirement: NAME` with a SHALL statement, and under it
  `#### Scenario: NAME` with WHEN/THEN lines and one or more `Test:` references
  to the tests that enforce it. A scenario without a test reference is invalid.
  (`specs/` at the root is v1 history and stays untouched.)
- Specs state behavior only. Plans stay in issues and `docs/plans/`, decisions in
  ADRs, progress on GitHub. GitHub stays authoritative for issue relationships,
  PRs, merges and CI; the specs are authoritative for intended behavior, which no
  other artifact records, so they add no second source of truth.
- Every behavior-bearing PR (R1, R2) updates the affected spec in the same PR.
  The PR's diff of `docs/specs/` is the change delta: no change folders and no
  archive step, because Git already keeps the history.
- A deterministic stdlib checker (`tools/spec_check.py`, run by the fast gate
  and CI) validates the format and that every cited test exists.
- Existing behavior is described once, without code changes, before the merge
  verdict applies to a capability. Until a touched capability has a spec, an R1
  PR touching it gets `HUMAN`.

### The human approves the spec delta

- For an R1 or R2 leaf, the clarify/plan phase posts the spec delta on the issue
  in a fixed shape: added, modified and removed requirements and scenarios, open
  questions, risk, and a content hash. R0 work and investigations skip it.
- The human approves by an issue comment naming that hash, directly or relayed
  verbatim as for R2 approvals today. The implement dispatch refuses an R1/R2
  leaf without an approval whose hash matches the posted delta.
- Changing a requirement or scenario after approval needs a new approval.
  Questions that change no observable behavior stay "decide, flag and continue"
  (Epic #149).

### Conformance is checked, not reread

- The PR's `docs/specs/` change must equal the approved delta (checked by hash).
  An R1/R2 PR that changes no spec fails unless the reviewer records that no
  observable behavior changed.
- Each new or modified scenario cites a test, and the test review records that
  the test fails on the base and passes on the head.
- A finding is dismissed only with a `file:line` citation in the diff, and the
  pair reassesses it; the author still cannot dismiss a blocker alone.

### A computed verdict decides the merge

`tools/merge_check.py` returns one verdict for the PR's current head, with its
reasons and what would raise it:

- `MERGE`: the ADR-0026 conditions hold (independent review approved the exact
  head and confirmed the risk, every required check passed on it, not a draft,
  nothing changed after review, no excluded path), and the PR is R0, or R1 with
  a recorded spec approval and a green conformance check on that head.
- `HUMAN`: R2; an excluded path (the ADR-0026 list plus the project's human-only
  globs in `project/workflow.md`); a disputed or raised risk; spec drift; a
  touched capability without a spec. The output is the handoff: approved spec,
  risky paths, surviving review findings. The human reviews that, not the full
  diff.
- `BLOCK`: missing or stale review, a failing or missing required check, a
  draft, or a head that moved.

The coordinator merges only on `MERGE`, with `--squash --match-head-commit`. The
merge is reported as merged under this ADR, never as a human approval.

### Unchanged

R2 changes still need explicit human approval of the plan and of the merge.
Release, deployment, destructive cleanup and paid services still need a human.
Agents never run in CI. A project can keep a human merge for every PR in its
`project/workflow.md`.

## Invariants that change

| Text | Today | After | Leaf |
| --- | --- | --- | --- |
| `AGENTS.md`/`CLAUDE.md` risk section | "Every PR needs human merge approval" | the verdict rule; R2 keeps human merge | [#269](https://github.com/Hugo-Grellier/ballast/issues/269) |
| `templates/policies/workflow.md` | same, for adopters | same | #269, [#270](https://github.com/Hugo-Grellier/ballast/issues/270) |
| ADR-0023 | no parallel spec tree for routine tasks | living specs for every behavior change | [#265](https://github.com/Hugo-Grellier/ballast/issues/265) |
| `docs/issue-workflow.md` step 3 | routine plans need no human checkpoint | R1/R2 need an approved spec delta | [#267](https://github.com/Hugo-Grellier/ballast/issues/267) |
| `docs/pair-review.md`, test review skill | criteria mapped to evidence | scenario fail-on-base evidence; dismissal needs `file:line` | [#268](https://github.com/Hugo-Grellier/ballast/issues/268) |

## Consequences

The human looks at the spec, the one place they can judge, and at the R2
handoff; R0 and R1 PRs complete without waiting. Living specs give reviewers and
workers the current behavior without reconstructing it.

The spec approval becomes the main human decision: a careless approval approves
the wrong behavior, so the delta stays short and in behavior terms. Behavior no
scenario describes is not protected by the verdict; the engineering and test
reviews still examine the whole diff. A misclassified R2 change merged as R1 is
the main residual risk, bounded by the reviewer's risk confirmation, the
excluded paths and the revert workflow. Bootstrapping specs for existing
behavior is real work and delays `MERGE` for capabilities not yet described.

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
