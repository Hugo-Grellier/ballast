# Live check: acceptance packet (T052)

- Date: 2026-10-06 (run timestamps are UTC, 2026-10-05T22:06Z to 22:16Z)
- Standard: this checkout (`BALLAST_STANDARD_DIR=<path>/feat-19-acceptance-packet`, at `7c90b5b`), launcher `<path>/.local/bin/ballast`
- Project: disposable private repository `Hugo-Grellier/ballast-pilot`, Issue [#10](https://github.com/Hugo-Grellier/ballast-pilot/issues/10), branch `feat/10-char-count`, Draft PR [#11](https://github.com/Hugo-Grellier/ballast-pilot/pull/11)
- Run: `2978c4c4`, human-gated (`ballast-feature`), integration `claude`; every `start`/`resume` had stdin from `/dev/null` and paused at `scope-gate`, so no agent step ran
- Procedure: [quickstart §2](../quickstart.md#2-live-check-operator-disposable-repository) steps 1 to 7, plus a CI-link check and the SEC-003 check from [security-1.md](security-1.md)

## Setup

```text
$ gh issue create --title "Add a char-count helper" --body '... ## Acceptance criteria ...'
https://github.com/Hugo-Grellier/ballast-pilot/issues/10
$ git switch -c feat/10-char-count origin/main
$ ballast setup
Spec Kit 1.0.11 and the standard are set up.
$ git status --short            # empty
$ ballast trust
trusted 125 workflow inputs for <path>/dev/personal/ballast-pilot
```

Fixture committed and pushed as `8f844c3` (implementation, test, spec, manifest):

- `specs/10-char-count/spec.md`: `- **AC-001**: \`count_chars\` returns the number of characters, like #8 and Hugo-Grellier/ballast-pilot#5 **When** called with "abc" **Then** it returns 3.` The two references are deliberate, for SEC-003.
- `specs/10-char-count/acceptance-evidence.json`: schema 1, `spec_digest` = SHA-256 of spec.md, `AC-001 → tests.test_text.CountCharsTests.test_three_chars`.
- `src/pilot/text.py`: `count_chars`; `tests/test_text.py`: `CountCharsTests.test_three_chars`. `python3 -m unittest discover -s tests`: OK.

## Step 1. Start; Draft PR and first packet — PASS

```text
$ ballast run start -i idea="Issue #10: Add a char-count helper" -i feature_directory=specs/10-char-count -i integration=claude </dev/null
Branch sync: up-to-date feat/10-char-count with main (2ad1b68ec49f)
  ▸ [preflight] shell …
  ▸ [scope-gate] gate …
Run 2978c4c4: paused at step scope-gate
Draft PR: created #11 https://github.com/Hugo-Grellier/ballast-pilot/pull/11
Acceptance packet: published #11 head 8f844c3199f3
```

PR body packet:

```text
- Feature: `specs/10-char-count/` version `e1b7c8b78064` (spec `sha256:727fcfdaa597`)
- Base: `2ad1b68ec49f` · Head: `8f844c3199f3` · [diff](…/compare/2ad1b68…...8f844c3…)
- Run: `2978c4c4` (human-gated)
- Criteria: 1 · verified 0 · failed 0 · not run 1 · stale 0 · missing 0
| [AC-001](…/blob/8f844c3…/specs/10-char-count/spec.md?plain=1#L7) | … | not run | no check recorded at head: [`tests.test_text.CountCharsTests.test_three_chars`](…/blob/8f844c3…/tests/test_text.py): not run |
API: not configured.   UI states: not configured.   decisions/reviews/run record: not present
```

- Expected: `Acceptance packet: published #N head <sha>`; every criterion `not run` or `missing`.
- Observed: as expected. The packet sits after the #17 section, between one begin and one end marker.

## Step 2. `ballast ledger check`, then resume — PASS

The first two attempts stopped on prerequisites of `ledger check` that predate #19 (see Observations 1):

```text
$ ballast ledger check 2978c4c4 AC-001 tests.test_text.CountCharsTests.test_three_chars </dev/null
agent ledger: [Errno 2] No such file or directory: '<path>/ballast-pilot/specs/10-char-count/intent.md'
  -> committed and pushed specs/10-char-count/intent.md carrying `sha256:<spec digest>` (24335db)
agent ledger: [Errno 2] No such file or directory: '<path>/ballast-pilot/.venv/bin/python'
  -> python3 -m venv --without-pip .venv; ballast trust   (trusted 136 workflow inputs); git status clean
$ ballast ledger check 2978c4c4 AC-001 tests.test_text.CountCharsTests.test_three_chars </dev/null
(no output, exit 0; ledger event 17: kind verification, AC-001, commit 24335dbaea12, exit_code 0)
$ ballast run resume 2978c4c4 </dev/null
Draft PR: reused #11 https://github.com/Hugo-Grellier/ballast-pilot/pull/11
Acceptance packet: updated #11 head 24335dbaea12
```

```text
- Criteria: 1 · verified 1 · failed 0 · not run 0 · stale 0 · missing 0
| [AC-001](…/blob/24335db…/specs/10-char-count/spec.md?plain=1#L7) | … | verified | 1/1 tests passed at head: [`tests.test_text.CountCharsTests.test_three_chars`](…/blob/24335db…/tests/test_text.py) (ledger event 17 of run 2978c4c4) · CI at head: no CI result at head |
```

- Expected: `updated`, AC-001 `verified`, links to the test's ledger event and to the head commit's check runs.
- Observed: `updated`, `verified`, the ledger event named by run and sequence (DEC-0001). The pilot had no CI, so the packet correctly said `no CI result at head` (the head-checks link appears only when GitHub reports a check run). The CI link was then exercised separately, see "CI link check" below.

## Step 3. Resume with no change — PASS

```text
$ ballast run resume 2978c4c4 </dev/null
Draft PR: reused #11 https://github.com/Hugo-Grellier/ballast-pilot/pull/11
Acceptance packet: unchanged #11 head 24335dbaea12
$ cmp <(packet section before) <(packet section after) && echo packet-identical
packet-identical
$ diff body-before body-after
< - Last checkpoint: 2026-10-05T22:08:22Z
> - Last checkpoint: 2026-10-05T22:08:43Z
```

PR edit history (GraphQL `userContentEdits`, timestamps in each revision):

```text
22:08:45Z  Last checkpoint 22:08:43Z / Generated 22:08:25Z   <- this resume: #17 section only
22:08:27Z  Last checkpoint 22:08:22Z / Generated 22:08:25Z   <- step 2 packet edit
22:08:24Z  Last checkpoint 22:08:22Z / Generated 22:06:49Z   <- step 2 #17 edit
```

- Expected: `unchanged`; the edit history shows no packet edit.
- Observed: `unchanged`; the only revision from this resume is #17's `Last checkpoint` line, and the packet (`Generated: 22:08:25Z`) is byte-identical. Note: the PR does show an edit per checkpoint, made by the #17 section, not by the packet (AC-010 holds for the packet).

## Step 4. Implementation change, resume — PASS

```text
$ (edit docstring in src/pilot/text.py); git commit; git push      # 34c7155
$ ballast run resume 2978c4c4 </dev/null
Acceptance packet: updated #11 head 34c715522250
- Criteria: 1 · verified 0 · failed 0 · not run 0 · stale 1 · missing 0
| [AC-001](…) | … | stale | evidence belongs to commit 24335dbaea12: [`tests.test_text.CountCharsTests.test_three_chars`](…/blob/34c7155…/tests/test_text.py) (ledger event 17 of run 2978c4c4): stale (commit `24335dbaea12`) |
```

- Expected: AC-001 `stale`, the earlier commit named.
- Observed: as expected.

## Step 5. Delete the packet section, add an own line, resume — PASS

The packet span was removed and `Operator note: keep this line (T052 step 5).` appended, with `gh pr edit 11 --body-file <file>` instead of the web UI.

```text
$ ballast run resume 2978c4c4 </dev/null
Acceptance packet: published #11 head 34c715522250
$ grep -n "Operator note\|acceptance-packet:\|draft-pr:" body
1:<!-- ballast:draft-pr:begin -->
10:<!-- ballast:draft-pr:end -->
12:Operator note: keep this line (T052 step 5).
14:<!-- ballast:acceptance-packet:begin -->
64:<!-- ballast:acceptance-packet:end -->
```

- Expected: the packet appended again, the operator's line kept.
- Observed: `published` (0 markers before), appended after the operator's line, which is kept. The line was still present after every later checkpoint.

## Step 6. `[review] openapi`, OpenAPI change, resume — PASS

To exercise the comparison rather than only `added in this PR`, a v1 document was pushed to the pilot's `main` (`1f02d4b`, `GET /count` with an optional `text`, `GET /slug`) and merged into the branch. The branch then changed it (`a96a665`): `text` required, `POST /count` added, `/slug` removed, and `ballast.toml` gained `[review] openapi = "docs/api/openapi.json"` in the same commit.

```text
$ git push; git status --short    # empty
$ ballast trust
trusted 136 workflow inputs for <path>/dev/personal/ballast-pilot
$ ballast run resume 2978c4c4 </dev/null
Acceptance packet: updated #11 head a96a6655038e
- Base: `1f02d4bd3d8e` · Head: `a96a6655038e` · [diff](…)
### API changes
API (`docs/api/openapi.json`, base → head): 1 added, 1 removed, 1 changed; 2 potentially breaking.
This classification is automatic and needs human review; it is not an approval.
- added: POST /count
- removed: GET /slug — potentially breaking (operation removed)
- changed: GET /count — potentially breaking (parameter now required)
```

- Expected: the API section.
- Observed: the API section with the correct classification. The operations are written without the backticks shown in the contract example (Observation 2).

## Step 7. Every Sources link resolves at the head SHA — PASS

Each packet link was resolved through the authenticated API (`gh api -i`): `blob/<sha>/<path>` as `repos/…/contents/<path>?ref=<sha>`, `compare/<b>...<h>` as `repos/…/compare/…`, `commit/<sha>/checks` as `repos/…/commits/<sha>/check-runs`, `runs/<id>` as `repos/…/check-runs/<id>`. (A private repository's github.com pages do not accept an API token, so the API is the check.) After the CI link check below, at head `75ff18c`:

```text
200 head=True compare diff -> …/compare/1f02d4bd3d8e…...<head>
200 head=True blob    AC-001 -> …/blob/<head>/specs/10-char-count/spec.md?plain=1#L7   (line 7 is the AC-001 item)
200 head=True blob    tests.test_text.CountCharsTests.test_three_chars -> …/blob/<head>/tests/test_text.py
200 head=True commit  check runs -> …/commit/<head>/checks
200           runs    test -> …/runs/112002096117   (check run head_sha = <head>)
200 head=True blob    intent.md -> …/blob/<head>/specs/10-char-count/intent.md
200 head=True blob    spec.md -> …/blob/<head>/specs/10-char-count/spec.md
200 head=True blob    acceptance-evidence.json -> …/blob/<head>/specs/10-char-count/acceptance-evidence.json
links 8 bad 0
```

The same check at step 6's head `a96a665`: 6 links, 0 bad. Absent artifacts (plan, tasks, decisions, reviews, run record) read `not present` with no link.

- Expected: each link opens the named file at the head SHA (SC-002).
- Observed: as expected.

## CI link check (step 2's check-runs link) — PASS

A workflow running the unit tests was pushed (`75ff18c`). Once its check run completed:

```text
$ ballast ledger check 2978c4c4 AC-001 tests.test_text.CountCharsTests.test_three_chars </dev/null   # exit 0
$ ballast run resume 2978c4c4 </dev/null
Acceptance packet: updated #11 head 75ff18cbc3aa
| [AC-001](…) | … | verified | 1/1 tests passed at head: [`tests.test_text.CountCharsTests.test_three_chars`](…/blob/<head>/tests/test_text.py) (ledger event 59 of run 2978c4c4) · CI at head: [check runs](…/commit/<head>/checks) |
- GitHub check runs at head: [test](…/runs/112002096117) completed/success
```

- Expected: a `verified` row links the head commit's check runs when GitHub reports one (AC-002).
- Observed: as expected; both links resolve (step 7).

## SEC-003. Does `\#` stop GitHub cross-references? — FAIL

Rendered PR body (`gh api repos/Hugo-Grellier/ballast-pilot/pulls/11 -H "Accept: application/vnd.github.html+json" --jq .body_html`), packet source `like \#8 and Hugo-Grellier/ballast-pilot\#5`, data attributes removed:

```text
<td>`count_chars` returns the number of characters, like <a class="issue-link js-issue-link" href="https://github.com/Hugo-Grellier/ballast-pilot/issues/8">#8</a> and <a class="issue-link js-issue-link" href="https://github.com/Hugo-Grellier/ballast-pilot/issues/5">#5</a></td>
```

The publication also created cross-reference events from PR #11 on both issues (`gh api repos/…/issues/N/timeline`):

```text
#5: [{"at":"2026-10-05T22:06:52Z","n":11}]
#8: [{"at":"2026-10-05T21:48:33Z","n":9},{"at":"2026-10-05T22:06:52Z","n":11}]
```

Variants rendered with `gh api markdown -f mode=gfm -f context=Hugo-Grellier/ballast-pilot`:

| Input | Rendered |
| --- | --- |
| `\#8`, `&#35;8`, `owner/repo\#5`, `owner/repo&#35;5` | issue link |
| `#` + U+200B + `8` (or `#&#8203;8`) | plain text |
| `@` + U+200B + `Hugo-Grellier` (what `inert` emits today) | plain text |
| `GH-8` (not escaped by `inert`) | issue link |
| a 40-hex commit SHA (not escaped) | commit link (no timeline event) |

- Expected: agent-written text renders inert; FR-013 says it "MUST NOT ... inject links outside quoted text".
- Observed: the backslash escape does not stop GitHub's reference autolinker. Agent text in the packet (spec titles, decision summaries, finding reasons, check names) turns into issue links and writes cross-reference backlinks on the referenced issues or PRs. The same applies to `GH-N`. Commit SHAs become links with no backlink.
- Classification: spec violation (FR-013), low severity. It grants no authority, and a private repository's references are visible only to its readers.
- Likely cause and fix: `tools/spec_workflow/packet.py` `inert()` escapes `#` with a backslash (research R9's punctuation list). Breaking `#` before a digit with U+200B, as `inert` already does for `@`, renders plain text (verified above). `GH-` followed by a digit needs the same treatment (for example `GH-` + U+200B), and so does a bare hex SHA, if commit links count as injected links. Add a unit test for `#N`, `owner/repo#N` and `GH-N`.

## Observations (not failures)

1. `ballast ledger check` needs `specs/<feature>/intent.md` to carry `sha256:<spec digest>`, and `.venv/bin/python` to exist. A missing one stops it with a raw `agent ledger: [Errno 2] No such file or directory: '<absolute path>'`, with no remedy. This predates #19 (`ledger._approved_spec_ids` on `main` reads `intent.md` the same way). The message also prints an absolute path. The command prints nothing on success. A clearer message ("no intent.md approving this spec" / "create .venv, then `ballast trust`") would help an operator following quickstart step 2.
2. [contracts/packet-format.md](../contracts/packet-format.md) shows API operations in backticks (`` `POST /orders` ``). The implementation and `tests/test_packet.py` write them bare (`- added: POST /count`). This is contract wording drift only.
3. A `python3 -m venv .venv` that fails at `ensurepip` still leaves `.venv/bin/python`. `ballast trust` and `ledger check` accepted it (ledger event 15). It was recreated with `--without-pip`, which gave event 17, before relying on it.
4. Every checkpoint edits the PR body once for #17's `Last checkpoint` line, so the edit history is never empty after a resume. The packet itself made no edit on the unchanged run.

## Result

- Quickstart §2 steps 1–7: PASS (plus the CI link check: PASS)
- SEC-003: FAIL (FR-013, low; fix in `packet.inert`)
- T052 stays unchecked until SEC-003 is fixed and its rendering re-checked.
- Verdict: FAIL
