# Implementation review 1: security

- Reviewer: Claude Opus 5.5 (same provider as the author; independent session, not a cross-provider review)
- Date: 2026-10-05
- Skill: `.agents/skills/ballast-security-review/SKILL.md`
- Scope: `git diff origin/main...HEAD` on `feat/19-acceptance-packet` (HEAD `eae5f01`): `tools/spec_workflow/packet.py`, the `draft_pr.py`, `ledger.py`, `run.py` and `branch_sync.py` changes, their tests, ADR-0006.
- Design read: spec.md (FR-001, FR-012, FR-013, FR-016, AC-020, AC-022), decisions.md DEC-0001, research R1, R8, R9, R10, R18, ADR-0003, ADR-0006, #18 SEC-007 (`draft_pr._code`).

```yaml
review: security
verdict: approved   # after the fixes in Resolution; changes_required as found
findings:
  - id: SEC-001
    severity: medium
    category: implementation bug
    invariant: FR-013, AC-020
    location: tools/spec_workflow/packet.py:inert
    description: >
      `inert` escapes HTML, Markdown punctuation, autolinks and mentions, but not
      `$`. GitHub renders `$...$` and `$$...$$` as LaTeX in PR descriptions, so a
      spec title, decision summary, finding reason or check-run name such as
      `$\color{green}\text{appr}\text{oved by the human}$` renders as styled text
      that spells an approval or a state; splitting it across `\text{}` groups
      also defeats the HUMAN_APPROVAL guard. It cannot change a computed state
      cell, but it is not inert data.
    required_action: Render `$` as `&#36;`; test it in InertTests and HostileTextTests.
  - id: SEC-002
    severity: low
    category: implementation bug
    location: tools/spec_workflow/packet.py:CONTROL
    description: >
      Bidirectional and zero-width formatting characters (U+202A-202E,
      U+2066-2069, U+200B-200F, U+FEFF) passed through `inert`, allowing
      visually reordered titles (Trojan-Source style) in the packet.
    required_action: Strip them with the C0 controls.
  - id: SEC-003
    severity: low
    category: spec ambiguity
    location: tools/spec_workflow/packet.py:inert
    description: >
      `#` is backslash-escaped, but GitHub's reference autolinker (`owner/repo#N`,
      `GH-N`, commit SHAs) works on rendered text; whether `\#` suppresses a
      cross-reference was not verified (no network seam). Worst case is a
      cross-reference backlink from agent text; it grants nothing and a private
      repository's references are visible only to its readers.
    required_action: None now; check during T052's live run.
  - id: SEC-004
    severity: low
    category: spec ambiguity
    location: tools/spec_workflow/packet.py:evaluate
    description: >
      `verified` trusts `operator-attested` `verification` events in the run
      ledger under `.git/speckit-runs/`. Autonomous agent steps get `.git`
      read-only (autonomy bubblewrap `--ro-bind`), so they cannot forge one;
      in a human-gated run the agent CLI's own sandbox decides. This is the
      existing ledger trust model (ledger-schema: "provenance, not an
      attestation"), not new in this feature.
    required_action: None; the packet labels itself a derived summary.
  - id: SEC-005
    severity: low
    category: implementation bug (documentation of a boundary)
    location: tools/spec_workflow/packet.py module docstring; docs/adr/0006-review-packet-reads.md
    description: >
      Both state that every command goes through the checkpoint's `_command`.
      `ledger.commit_tree` does not: it needs a private GIT_INDEX_FILE, which
      `_command` strips, so it runs `ledger._git`. Verified safe (see below),
      but the boundary text was wrong.
    required_action: Correct the docstring and ADR-0006.
```

## What was examined

| Surface | Result |
| --- | --- |
| PR-body rendering | Every value from an agent-writable or third-party source goes through `inert` (spec titles, decision summaries and points, human-action labels, finding IDs, severities and reasons, `run-checks` commands, check-run names, statuses and conclusions, UI state names, OpenAPI paths, risk). The rest is validated before use: AC IDs (`ledger.AC`), PD/HD IDs (hash-chained log enforces `PD-NNNN`), DEC IDs (regex), test names (`TEST_NAME`, inside a code span, no backtick possible), hex digests, run ID, feature (`FEATURE_PATTERN`), the OpenAPI path (protected `ballast.toml`, `safe_path`), review report names from `ls-tree` (`safe_path` filter). `html.escape` removes `<`, so no value can spell `<!-- ballast:acceptance-packet:… -->`, the #17 markers or `<!-- workflow-`; `render` also refuses a text with other than one BEGIN and one END. Compared with #18 SEC-007, the packet has no unescaped code span carrying agent text. Gap: `$` (SEC-001), bidi controls (SEC-002). |
| Links | Built only by `_blob`, `_line`, `_compare`, `_run_link`, `_checks` from a validated `owner/repo`, a 40/64-hex OID, a `safe_path` path and an int; check-run `html_url` from GitHub is ignored (test asserts `evil` absent). |
| Marker spoofing in the body | `_span` refuses two sections, a reversed pair or a lone marker (`section-unmanaged`), and `_publish` checks every byte outside the span is kept and the count is one before writing; re-read immediately before `gh pr edit` (`body-changed`). |
| GitHub reads | `repos/<o>/<r>/pulls/<n>`, `…/commits/<head>/check-runs`, `…/contents/<quote(path)>?ref=<oid>`: `<o>/<r>` is the pinned `[github] repository`, `<n>` the #17 PR, `<head>`/`<base>` OIDs validated from the PR read, the path from protected `ballast.toml` and `safe_path`. All through `_Checkpoint.gh`: absolute `gh` resolved outside work trees, run from an empty temp directory (never reads the agent-writable `.git/config`), checkout PATH entries dropped, `GH_PROMPT_DISABLED`, 30 s timeout. The token is gh's own (operator environment or gh config); agents never receive `GH_TOKEN`/`GITHUB_TOKEN` (run.py) and cannot redirect the repo, path or ref. `gh` output is parsed, never printed or stored; only fixed reason codes reach the ledger. |
| Local Git | Packet reads (`cat-file -e/-s/blob`, `ls-tree -r -z --name-only … --`, `rev-parse --verify <oid>:<feature>`) run through `_command` with `core.hooksPath=/dev/null` and `core.fsmonitor=false` (GIT_CONFIG_COUNT) and GIT_DIR/GIT_INDEX_FILE removed. `cat-file blob` applies no filter. `commit_tree`: every call is `ledger._git(root, *NO_HOOKS, …)` (`read-tree`, `rm --cached`, `write-tree`), so `post-index-change` cannot run when the private index is written; `ledger._git` resolves Git outside work trees and disables every configured filter driver; the commit is `HEAD` or an OID (an `--output=` value is refused, tested). `implementation_tree` also passes NO_HOOKS on all four index-writing calls; `_has_head`/`rev-parse` write no index. The hook test plants `post-index-change`, `post-checkout` and `pre-commit` and asserts no sentinel, unchanged index and worktree. fsmonitor is overridden but not exercised by a test (low; see test-1 TEST-003). |
| Reads from the agent-writable checkout | Feature artifacts, the manifest and test-file existence are read from the object store at the PR head, not the worktree, size-capped at 1 MiB, decoded strictly, parsed as data; a malformed manifest is a fixed reason. `acceptance-evidence.json` only selects which tests to look up; states come from ledger events. The OpenAPI document comes from GitHub contents at two OIDs, capped at 1 MiB and 2000 operations, `$ref` resolution local-only with depth 5 and cycle stop; nothing is executed or downloaded (FR-012 holds). Only `ballast.toml` is read from the worktree, and it is a protected input. Deep JSON raising RecursionError ends as `internal-error`, retryable, without effect on the #17 outcome. |
| Archive | `speckit-runs/<run>/acceptance-packet.md`, run ID validated, symlinked parent refused by `archive_dir`, temp file then `os.replace` (a planted symlink is replaced, not followed), mode 0600; content is the rendered packet (no path, host or token; tested). |
| Secrets | `inert` redacts `gh*_`/`github_pat_` tokens and `Authorization`/`Bearer` values; outcomes hold codes and validated IDs; `format_line` prints exception type names only; AC-022 test covers stdout, ledger, archive and body with `GH_TOKEN` set and a token in `gh` stderr and in an exception message. |
| Authority | The packet runs only inside the #17 checkpoint after `_untrusted` passed and only for `created`/`reused`; no new program, no fetch, push or commit; the only write is the PR body section. |

## Resolution

- SEC-001 fixed: `inert` renders `$` as `&#36;`. Tests: `InertTests.test_math_and_bidi_controls_are_inert`; `HostileTextTests` now carries a split-`\text{}` approval in `$…$` and asserts no `$` in the body. Both failed before the fix.
- SEC-002 fixed: `CONTROL` also strips U+200B–U+200F, U+202A–U+202E, U+2060–U+2069 and U+FEFF; same tests (`‮` in the hostile text).
- SEC-003 not fixed (low, unverified without network); listed for T052.
- SEC-004 not fixed (low, existing trust model).
- SEC-005 fixed: packet.py docstring and ADR-0006 Decision now name the `commit_tree` exception and its hardening.
- Gates: see [engineering-1.md](engineering-1.md#resolution).

- Verdict: approved
