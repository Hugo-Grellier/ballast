# Implementation review 1: engineering

- Reviewer: Claude Opus 5.5 (same provider as the author; independent session, not a cross-provider review)
- Date: 2026-10-05
- Skill: `.agents/skills/ballast-engineering-review/SKILL.md`
- Scope: `git diff origin/main...HEAD` on `feat/19-acceptance-packet` (HEAD `eae5f01`, on main `f683454`): packet.py (new), draft_pr.py, ledger.py, run.py, branch_sync.py, ledger-schema.md, tests.
- Design read: spec.md FR-001–FR-018 and AC-001–AC-022, plan.md, research.md, data-model.md, contracts/, tasks.md, decisions.md DEC-0001, ADR-0003, ADR-0006. The architecture check T053 asks for (ADR-0006 extends ADR-0003) is folded into this review.

```yaml
review: engineering
verdict: approved   # after the fixes in Resolution; changes_required as found
findings:
  - id: ENG-001
    severity: medium
    category: implementation bug
    location: tools/spec_workflow/packet.py:_Step.collect.file_of
    invariant_or_requirement: AC-019, FR-015
    evidence: >
      `TEST_NAME` (and ledger's identical manifest regex) accepts an empty dotted
      segment or a very long name, e.g. `tests.test_gone..test_x`. `file_of`
      turns it into `tests/test_gone//test_x.py`, `exists` calls `_path`, which
      raises ValueError, and the whole packet ends `internal-error` ("report
      it") at every checkpoint instead of rendering the test as unlinked.
    required_action: Skip a candidate path that is not `safe_path`; regression test.
  - id: ENG-002
    severity: medium
    category: spec violation
    location: tools/spec_workflow/packet.py:_capped, build
    invariant_or_requirement: AC-021, FR-014
    evidence: >
      At level 1 an API or UI list over 50 lines is cut in the PR with
      "… N more in the complete packet", but the archive path is printed only
      for levels 2-4 and the ledger's `shortened` is `level > 1`, so a cut
      packet neither names the complete packet nor records itself as shortened.
    required_action: Name the archive path in the overflow line; record `shortened` as "PR text differs from the complete text".
  - id: ENG-003
    severity: low
    category: implementation bug
    location: tools/spec_workflow/packet.py:_causes
    evidence: >
      `_causes` rebuilt `_operations` of both documents for every common
      operation: O(n²); 2000 changed operations took 5.5 s in the launcher.
    required_action: Pass the operations already computed.
  - id: ENG-004
    severity: low
    category: implementation bug
    location: tools/spec_workflow/packet.py:_Step.collect
    evidence: >
      A broken operator record (AutonomyError from find_run/read_log/read_checks,
      or int()/float() of a malformed checks.json entry) and a LedgerError from
      `commit_tree` escape `collect` and become `internal-error` with the remedy
      "report it" rather than a fixed cause. Fail-closed and retryable, and the
      #17 outcome is untouched; only the remedy is unspecific.
    required_action: None now; a later change may map them to `ledger-invalid`.
  - id: ENG-005
    severity: medium
    category: proposed product change
    location: tools/spec_workflow/run.py (_resume_refusal, _publish_command, _continue_command)
    invariant_or_requirement: US3, FR-009
    evidence: >
      The packet is rebuilt only by `_checkpoint`, which runs at the end of
      start, resume and continue. A finished Autonomous run cannot be resumed,
      `ballast run publish` runs no checkpoint, and `continue` makes a new run
      whose packet reads only the new run's ledger. Evidence the operator
      records with `ballast ledger check <autonomous run>` (the packet's own
      hint) can never reach that PR's packet.
    required_action: Operator decision; DEC-0002 proposal written. Policy text made truthful meanwhile (DOC-001).
```

## Checked and sound

- **Requirement coverage**: every FR maps to code. FR-003 rule: a test is `passed` only when its latest event is bound to (commit_tree(head), sha256(spec at head), sha256(manifest at head)); the criterion is `verified` only when all mapped tests pass, else `failed` > `stale` > `not run`, matching the spec assumption and ledger's AC rule. Spec digest mismatch in the manifest makes every mapped criterion `stale`. Unknown manifest IDs listed. Spec without IDs handled.
- **Source authority (FR-002)**: everything is read from the head commit's objects, the run ledger, operator records and GitHub; nothing is stored except the archive copy and one ledger event of codes and IDs. `render` is pure; `_mask`/`_digest` drop only the `Generated:` line, so republishing is byte-identical (AC-010).
- **Fingerprint change**: `implementation_tree` now seeds the private index from HEAD and drops `specs` after `add -A`; `commit_tree` builds the same tree from objects only. The test `test_clean_checkout_with_tracked_ignored_file_equals_head` proves equality including a tracked-but-ignored file. The one-time staleness of older snapshots is documented (ledger-schema upgrade note).
- **`commit` field on verification**: set only when the checkout fingerprint equals `commit_tree(HEAD)`; additive, optional, older streams valid.
- **Ledger schema**: `acceptance_packet` kind is runner-only, enum-checked outcome and reason per outcome, required fields for published/updated/unchanged; `COMMIT`→`OID` rename is internal (field type name `oid`), with branch_sync and draft_pr updated.
- **Failure isolation (FR-015)**: `draft_pr._packet` catches every exception into `failed-retryable/internal-error`, records the event separately, and `run.py` still prints both lines inside its own catch; the #17 outcome object is replaced only in its `packet` field.
- **Concurrency**: the packet edit is not under the clone-wide PR lock, the same as #17's reuse edit; the re-read immediately before `gh pr edit` narrows the race as #17 DEC-0007 accepted. No new shared state.
- **ADR-0006 vs ADR-0003**: the new reads are exactly the ones listed (PR, check runs, contents at two OIDs, local `cat-file`/`ls-tree`/`rev-parse`, private-index `read-tree`/`rm --cached`/`write-tree`); the only write is the PR body section. The ADR wrongly said all of them use `_command` (fixed, security SEC-005). No new ADR needed beyond 0006.
- **Complexity**: one module, no new abstraction layers; the size levels 1–4 are the R14 design. `Sources` is wide but flat data.

## Resolution

- ENG-001 fixed: `file_of` checks `safe_path` before `exists`. Test `CriteriaTests.test_test_name_without_a_safe_path_is_named_unlinked` (failed before: `internal-error`).
- ENG-002 fixed: `_capped` names `speckit-runs/<run>/acceptance-packet.md in the operator's clone` on its overflow line (shared `_archive_path` with the level-2+ header), and `Packet.shortened` is `text != full`. `OpenApiTests.test_long_lists_are_capped_in_the_pr_but_whole_in_the_archive` now asserts both (failed before).
- ENG-003 fixed: `_causes` takes the operations computed by `compare_documents`; the 2000-operation case is now linear. Covered by the existing OpenAPI tests.
- ENG-004 not fixed (low).
- ENG-005: [DEC-0002](../decisions.md#dec-0002--proposal) proposal; policy wording fixed under documentation-1 DOC-001. Implementation unchanged.
- Gates after the fixes:
  - `uvx ruff check && uvx ruff format --check`: passed (204 files already formatted).
  - `uv run --no-project --isolated --python 3.13 --with pyyaml python -m unittest tests/test_*.py`: `Ran 733 tests in 557.247s`, `OK`, none skipped (output kept outside the repository). This host has the systemd user session, Codex CLI, Spec Kit CLI and bwrap, so the tests CI skips also ran. An earlier run before TEST-006 was added: 732 tests, OK.

- Verdict: approved
