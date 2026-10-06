# Implementation review 1: documentation

- Reviewer: Claude Opus 5.5, the driving agent (same provider and session as the author; not independent).
- Date: 2026-10-06
- Skill: `.agents/skills/ballast-documentation-review/SKILL.md`
- Scope: `README.md`, `templates/policies/{spec-kit-workflow,workflow}.md`, `templates/skills/ballast-feature-intake/SKILL.md`, the `ballast` extension commands and `extension.yml`, `templates/spec-kit/templates/tasks-template.md`, `docs/adr/0010-*.md`, the ADR-0004 amendment, `specs/TECHNICAL-SPEC.md` §61/§91, `run.py` usage text.

```yaml
review: documentation
verdict: approved   # after the fixes below
findings:
  - id: DOC-001
    severity: medium
    location: templates/policies/spec-kit-workflow.md (Acceptance packet)
    description: >
      The packet paragraph still said a finished Autonomous run's packet keeps
      its published states; `ballast run checkpoint` now refreshes it.
    required_action: Name `checkpoint` as the refresh path (done).
  - id: DOC-002
    severity: medium
    location: templates/policies/spec-kit-workflow.md (Workflow runner contract)
    description: >
      The runner contract table had no rows for the feedback checks, the fix
      cycle steps and the wrapper's draft retries.
    required_action: Add the rows (done).
  - id: DOC-003
    severity: low
    location: templates/policies/spec-kit-workflow.md (Draft PR)
    description: The checkpoint triggers did not include `ballast run checkpoint`.
    required_action: Add it, noting it never creates a PR (done).
  - id: DOC-004
    severity: low
    location: specs/TECHNICAL-SPEC.md §91 and the branch-sync note
    description: Both still said Autonomous resume was refused until #21.
    required_action: Describe the delivered behavior with links to the spec and ADR-0010 (done).
```

## Checked

- The policies describe resume (eligibility table, re-entry, block resolution, refusals, the `dirty` case of DEC-0001), the fix loop, draft retries, active wall time and the spend bound, block classes, `checkpoint`, and "Runs started before branch pinning" (pin location, reading the feature from the run record, never from the checkout); each says the path is agent-provisional and merging the PR is the single human approval. `workflow.md` keeps the three-cycle escalation rule.
- The `unpinned` recovery text in `branch_sync.py` matches the policy table verbatim (`DocumentationTests`).
- README: commands, defaults (40 steps, active minutes), resume and checkpoint.
- ADR-0010 is Proposed and agent-provisional, states its context, decision, consequences and rejected alternatives; ADR-0004 keeps its history and gains "Amended by ADR-0010" lines.
- Commands state the recorder's limits and the paraphrase rule; `speckit.ballast.fix` treats its input as untrusted data; the decide command asks intent to cite the brief and the spec.
- Installed copies (`docs/policies/`, `.agents/skills/`) are git-ignored and rebuilt by `ballast setup`; they were not edited.
