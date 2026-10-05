# Quickstart: validating the acceptance packet

How to show the feature works. The behavior is defined in the [packet format](contracts/packet-format.md), the [checkpoint integration](contracts/checkpoint-integration.md), the [ledger event](contracts/ledger-acceptance-packet-event.md) and the [data model](data-model.md).

## Prerequisites

- Fast gate: `uv`, Python 3.13 (see `CLAUDE.md`).
- Live check only: everything #17's live check needs (an authenticated `gh` 2.48 or later outside any working tree, a disposable GitHub repository with an Issue and the `[github] repository` pin), plus a workflow that creates at least one check run.

## 1. Deterministic tests (no network)

```bash
uvx ruff check && uvx ruff format --check
uv run --no-project --python 3.13 --with pyyaml python -m unittest tests/test_packet.py tests/test_draft_pr.py tests/test_agent_run_ledger.py tests/test_spec_workflow.py
```

`tests/test_packet.py` builds a real temporary Git repository with commits for base and head (feature artifacts, implementation files, optionally an OpenAPI JSON), writes ledger events with `ledger.append`, and serves `gh` responses from #17's scripted `_command` fake. The clock is injected. `render` is also tested directly on hand-built `Sources`.

| Scenario | Expected | Covers |
| --- | --- | --- |
| Spec with AC-001…AC-006 as `1. **AC-NNN**:` items; manifest maps five | six rows in spec order, each with a title and a `spec.md?plain=1#L<n>` link at head | AC-001, SC-002 |
| AC-001 tests all passed, events bound to head's fingerprint, spec and manifest | `verified`, each test linked to its file at head, its ledger event named, and the head's check runs linked when present | AC-002, DEC-0001 |
| AC-002 one test failed at head, one passed | `failed`, both per-test results listed | AC-004, PD-0002 |
| AC-003 not in manifest; separately, no manifest at head | `missing` with "no test named" / "no acceptance-evidence.json" | AC-003 |
| AC-004 passed only on an earlier commit (event has `commit`) | `stale`, naming `commit <12>` | AC-004 |
| AC-005 passed for an earlier spec digest | `stale`, naming `spec <12>` | AC-004 |
| Manifest `spec_digest` ≠ spec at head | every mapped AC `stale` with that spec version | edge case |
| AC-006 mapped, no events | `not run` and the `ballast ledger check` hint | AC-004 |
| Dirty checkout check (fingerprint ≠ head) | `stale`, never `verified` | FR-003 |
| Manifest names AC-031, absent from spec | "Evidence for unknown criteria: AC-031" line | edge case |
| Spec with no AC IDs | "No acceptance criteria found" and a spec link | edge case |
| Autonomous records: PDs (one superseded), an open medium finding, risk R1 | risk `R1 (run record)`, each PD `agent-provisional` with a record link, finding with severity and report link | AC-005, AC-006 |
| Human-gated: ledger gate `approve` events, intake `Risk:` line | `human; observed by runner`, risk from the intake comment, no `agent-provisional` | AC-006 |
| No decisions, findings or checks | `None (0).` in each section and zero counts | AC-005, FR-004 |
| Every artifact present (incl. `reviews/*.md`, `autonomous/record.md`) | one link each, pinned to the head SHA, and a `compare/<base>...<head>` link | AC-007, AC-009 |
| `plan.md`, `decisions.md`, `reviews/` absent | each `not present`, no link; packet published | AC-008 |
| Second checkpoint, same sources, different clock | no `pr edit` call; ledger `unchanged` with the same `packet_digest` | AC-010, SC-003 |
| New head SHA / new base SHA / spec changed / a new verification event | section replaced in place, one marker pair; `updated` | AC-011 |
| Header | feature version, base, head and `Generated:` time present | AC-012 |
| Body with human text before and after, the #17 section and the #27 summary | only the packet span differs, byte for byte; argv has no `--title`, `--base`, label, reviewer, `--ready` or `--draft` | AC-013 |
| Packet markers deleted by a human | appended once at the end; everything else identical; `published` | AC-014 |
| Two begin markers, or end before begin | `failed-retryable/section-unmanaged`, no edit | FR-008 |
| Body changed between read and edit | `failed-retryable/body-changed`, no edit | FR-008 |
| No `[review]` table | `API: not configured.` and `UI states: not configured.` only | AC-015 |
| OpenAPI JSON at base and head: one op added, one removed, one response changed, one request field newly required | listed by method and path; removal and the required field flagged as potentially breaking; review sentence present | AC-016 |
| OpenAPI unchanged / 404 at base / 404 at head / YAML / 502 | `no API change` / `added in this PR` / `removed in this PR` / `could not compare (not JSON)` / `could not compare (github-error)`; rest published | AC-017 |
| UI states: one `path` present at head, one `check` success, one `check` in progress, one `path` absent | link at head, `passed` with run link, `not run (in progress)`, `missing`, each beside its AC | AC-018, edge case |
| Invalid `[review]` (`../x`, `AC-1`, both `path` and `check`) | `configuration invalid (<reason>)`; rest published | R12 |
| #17 outcome `pending`, `failed-retryable`, `blocked-closed` | packet `pending/no-pr` or `pending/pr-blocked`, no packet `gh` call; #17 line unchanged | AC-019, edge case |
| `spec.md` absent at head; manifest invalid JSON; ledger stream corrupt | `source-unreadable` / `manifest-malformed` / `ledger-invalid`, with the remedy; existing section untouched | AC-019 |
| Head commit not in the local object store | `pending/head-not-local` | AC-019 |
| `gh` 401 / 403 / unreachable on the check-runs read | `failed-retryable/gh-unauthenticated` / `gh-forbidden` / `github-unreachable` | AC-019 |
| `packet.publish` raises; `run.py` exit statuses 0, 1, 130 | packet `failed-retryable/internal-error`; #17 outcome and exit status unchanged; next checkpoint retries | AC-019, FR-015, SC-005 |
| Spec titles, PD summaries and finding reasons containing both packet markers, `<!-- workflow-` markers, `[x](https://evil)`, `https://evil`, `@org/team`, `` ` ``, `|`, "approved by the human", "verified" | escaped inert text; exactly one marker pair; no link to `evil`; states and labels unchanged; body passes the `HUMAN_APPROVAL` guard outside inert data | AC-020, FR-013 |
| PR body with 60,000 characters of human text | packet shortened: header, risk, counts, every non-verified AC, every finding and PD kept; archive note present; full text in `speckit-runs/<run>/acceptance-packet.md` (mode 0600) | AC-021, FR-014 |
| Human text leaves no room even at level 4 | `failed-retryable/too-large`, section unchanged | FR-014 |
| `GH_TOKEN=ghp_…` set; a source containing `github_pat_…` and `Authorization: Bearer …`; `gh` stderr with a token | no token in stdout, ledger, archive or PR body | AC-022, FR-016 |
| `ledger.spec_criteria` on `-` and `1.` forms; `ledger check` on a `1.`-form spec | both parsed; the manifest archives (defect fix, R6) | R6 |
| `implementation_tree` on a clean checkout with a tracked ignored file equals `commit_tree(HEAD)`; dirty differs | equal / different | R3 |
| `ledger check` on a clean checkout records `commit`; on a dirty one it does not | as stated | R3 |
| `acceptance_packet` validation: required fields per outcome, unknown reason, non-runner source, offered by `record` | rejected / rejected / rejected / absent | ledger contract |

## 2. Live check (operator, disposable repository)

1. Start a human-gated run on an issue-linked branch with one criterion mapped in `acceptance-evidence.json`, push an implementation change and let the checkpoint open the Draft PR. Expect `Acceptance packet: published #N head <sha>`, and every criterion `not run` or `missing`.
2. Run `ballast ledger check RUN_ID AC-001 <test>` on the clean, pushed checkout, then `ballast run resume RUN_ID`. Expect `updated`, with AC-001 `verified` and links to the test's ledger event and to the head commit's check runs.
3. Resume again with no change. Expect `unchanged`, and the PR's edit history shows no packet edit.
4. Commit and push a change to one implementation file, then resume. AC-001 now shows `stale` with the earlier commit named.
5. Delete the packet section in the GitHub UI and add a line of your own, then resume. Expect the packet appended again and your line kept.
6. Add `[review] openapi = "<path>"` to `ballast.toml`, run `ballast trust`, commit an OpenAPI JSON change, push, and resume. Expect the API section.
7. Follow every link in the Sources section. Each opens the named file at the head SHA (SC-002).

## 3. Upgrade note to verify

After upgrading, snapshots recorded by the previous `implementation_tree` no longer match, so earlier per-criterion checks read `stale` once. Re-run `ballast ledger check` for each criterion.
