# ADR-0026: R0 PRs merge on an approved, green, unchanged head

- Status: proposed (2026-10-16, with the change for [#219](https://github.com/Hugo-Grellier/ballast/issues/219)). The operator requested it on 2026-10-15 and approved the R2 change on 2026-10-16; merging the PR is the human approval that accepts it.
- Risk: R2 (changes merge authority, an invariant of `AGENTS.md`).
- Amends: [ADR-0023](0023-ballast-2-portable-agent-workflow.md), whose invariant required human approval for every merge.

## Context

Every PR needed a human merge approval. R0 PRs (#212, #214) waited for one after
their independent review and CI were complete; the human decision added delay but
no evidence, because an R0 change has no behavior to accept. R1 and R2 changes do,
and the human merge remains their acceptance.

## Decision

The coordinator may squash-merge an R0 PR without a separate human approval when
all of these hold for the PR's current head:

- an independent pair review approved that exact head and confirmed R0 itself:
  the risk classification is reviewed evidence, so a reviewer who would raise the
  risk does not approve the PR as R0;
- every required check passed on that head, and at least one is required;
- the PR is open, not a draft, ticks R0 and no other risk, and nothing changed
  after the review (PR head equals reviewed head).

`tools/merge_check.py` checks these conditions read-only with `gh` and prints the
exact `gh pr merge N --squash --match-head-commit SHA` command. It merges only with
an explicit `--merge`; `--match-head-commit` makes GitHub refuse a head that moved
after the check. It reads the review verdict and confirmed risk from its caller,
who takes them from the pair review of that head.

Excluded, so a human still merges them whatever their stated risk:

- Release Please PRs, dependency PRs (Dependabot, Renovate, any bot author) and
  any change to `.github/` (workflows, permissions, ownership), release files
  (`CHANGELOG.md`, Release Please configuration and manifest, `version.txt`) or
  dependency manifests and lockfiles;
- a PR whose risk is disputed or raised by the reviewer or by its actual diff.

Release, deployment, destructive cleanup and paid services still need explicit
human approval. The coordinator states in the PR that it merged under this ADR; the
merge is never presented as a human approval.

## Consequences

R0 work completes without waiting for the operator. A misclassified R1 change
merged as R0 is the main risk; the reviewer's R0 confirmation and the path
exclusions bound it, and a revert PR follows the normal workflow. Adopters inherit
the rule through `templates/policies/workflow.md`; a project can keep human merge
for every PR in its `project/workflow.md`.
