# Implementation review 1: documentation

- Reviewer: Claude Opus 5.5 (same provider as the author; independent session, not a cross-provider review)
- Date: 2026-10-05
- Skill: `.agents/skills/ballast-documentation-review/SKILL.md`
- Scope: `templates/policies/spec-kit-workflow.md` § Acceptance packet, `README.md`, `tools/spec_workflow/ledger-schema.md`, `docs/adr/0006-review-packet-reads.md`, module docstrings of packet.py, draft_pr.py and run.py, against the code on HEAD `eae5f01` and FR-018.

```yaml
review: documentation
verdict: approved   # after the fixes in Resolution; changes_requested as found
findings:
  - id: DOC-001
    severity: medium
    category: spec violation (documented behavior that does not exist)
    location: templates/policies/spec-kit-workflow.md, § Acceptance packet, "Per-criterion evidence …"
    description: >
      The policy tells the operator that after recording `ballast ledger check`
      evidence "the next checkpoint (`ballast run resume`, `continue` or
      `publish`) then shows them". `ballast run publish` runs no checkpoint
      (run.py `_publish_command`) and refuses a run already `published`;
      `resume` is refused for an Autonomous run (`_resume_refusal`); `continue`
      starts a new run whose packet reads only the new run's ledger. For the
      Autonomous case the sentence describes a path that does not exist.
    required_action: State the real refresh points truthfully; raise the gap as a decision (DEC-0002).
  - id: DOC-002
    severity: low
    category: implementation bug (boundary text)
    location: docs/adr/0006-review-packet-reads.md, Decision
    description: >
      "It uses the checkpoint's resolved git and gh, its hardened environment
      and its `_command` seam" is not true of the implementation fingerprint
      (`ledger.commit_tree` runs ledger's Git with a private index, NO_HOOKS and
      filters off). Same as security-1 SEC-005.
    required_action: Name the exception and its hardening.
  - id: DOC-003
    severity: low
    category: spec ambiguity
    location: templates/policies/spec-kit-workflow.md, § Acceptance packet, shortening paragraph
    description: >
      The policy did not say that a list longer than 50 lines is cut in the PR
      even when the packet otherwise fits (ENG-002 behavior).
    required_action: One clause.
  - id: DOC-004
    severity: low
    category: spec ambiguity
    location: templates/policies/spec-kit-workflow.md, remedy table (`pending`/`head-not-local`)
    description: >
      "fetch the feature branch, then resume" cannot be followed for an
      Autonomous run, whose resume is refused. Part of DEC-0002.
    required_action: Resolve with DEC-0002.
```

## Checked and accurate

- **FR-018 coverage**: the policy subsection describes the packet, the five evidence states with their meaning, recording per-criterion evidence with `ballast ledger check RUN_ID AC-NNN TEST` (argument order matches ledger.py's `check` parser), why Autonomous runs show `not run`, the `[review]` table with a valid TOML example (keys, limits and the path-or-check rule match `_ui_states`), the JSON-only OpenAPI limit, the breaking-change classes (match `BREAKING` and `_causes`, top-level request fields only), `configuration invalid (<reason>)`, the archive path and mode 0600, inert rendering, the printed line format (matches `format_line`) and every outcome/reason/remedy (matches `REMEDIES` and `ledger.PACKET_REASONS`), and that the packet is a derived summary and not an approval.
- **README**: one sentence linking the subsection, says "not an approval". Accurate.
- **ledger-schema.md**: the `acceptance_packet` kind, its required fields per outcome, the `oid` type, the optional `commit` on `verification`, the seeded fingerprint and its upgrade note, and `spec_criteria`'s two list forms all match ledger.py.
- **ADR-0006**: status `proposed`, agent-provisional, extends ADR-0003 as that ADR requires; the allowlist matches the calls in packet.py (`pulls/<n>`, paginated `check-runs`, `contents/<path>?ref=`, `cat-file -e/-s/blob`, `ls-tree -r -z --name-only`, `rev-parse --verify`, private-index `read-tree`/`rm --cached`/`write-tree`); the rejected alternatives match research R5 and R10. ADR history preserved (0001–0005 untouched).
- **Docstrings**: draft_pr.py and run.py describe the packet step and the second printed line correctly.
- No UI change, so no screenshots; the installed `docs/policies/` copy was correctly left alone.

## Resolution

- DOC-001 fixed: the paragraph now says the packet is rebuilt only at the checkpoint that ends `ballast run start`, `resume` and `continue`, from that run's own ledger and records; that a finished Autonomous run cannot be resumed and `publish` runs no checkpoint, so its packet keeps its published states; and that `continue` reads only the new run's ledger. The behavior gap is [DEC-0002](../decisions.md#dec-0002--proposal) (proposed product change, operator decision).
- DOC-002 fixed in ADR-0006 (shared with SEC-005).
- DOC-003 fixed: "a list longer than 50 lines is cut in the PR" added to the shortening paragraph.
- DOC-004 left to DEC-0002.

- Verdict: approved
