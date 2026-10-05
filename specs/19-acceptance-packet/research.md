# Research: Source-linked acceptance packet

Phase 0 decisions for [plan.md](plan.md). Each entry gives the decision, why, and what else was considered. Decisions marked **provisional** are agent-provisional in Autonomous run `97858712`; the plan gate records them and merge is the human approval.

## R1. Where the packet is built and published

- **Decision**: A new trusted module `tools/spec_workflow/packet.py`, called from `draft_pr.checkpoint` after the #17 outcome is decided and recorded, only when that outcome is `created` or `reused`. It uses the checkpoint's resolved identity (owner, repo, run, feature, `git`, `gh`) and its single command seam `_command`. Its own failures are caught inside the checkpoint and become an `acceptance_packet` outcome; the #17 `Outcome` returned to `run.py` is unchanged (FR-015). `run.py` prints a second line, `Acceptance packet: …`.
- **Rationale**: #17 already owns PR identity, program resolution, the hardened environment, tamper refusal and the "re-read before edit" rule (DEC-0007). Reusing them adds no new authority path (FR-001). One seam keeps every test offline (FR-017).
- **Alternatives**: a separate `run.py` call after `_checkpoint` (would duplicate identity resolution and need the PR found again); folding the packet into the #17 section (would make a packet failure change the #17 outcome and break FR-008's separate sections); publishing from the #27 publisher (runs only in Autonomous mode, and only once).

## R2. What "head commit", "base commit" and "feature version" are

- **Decision**:
  - **Head commit** and **base commit**: `head.sha` and `base.sha` from a fresh `gh api repos/<o>/<r>/pulls/<n>` read at the start of the packet step. The packet describes what GitHub shows as the PR, not the local checkout.
  - The head commit must exist in the local object store (`git cat-file -e <sha>^{commit}`); Ballast never fetches (ADR-0003). Absent → `pending/head-not-local` with the remedy to fetch the branch.
  - **Feature version**: the Git tree ID of `<head>:<feature>` (`git rev-parse <head>:<feature>`), shown as 12 hex characters. Any change to any feature artifact changes it, whatever else the head commit contains (spec assumption).
  - **Spec version**: SHA-256 of `spec.md` at the head commit, the same digest the ledger records as `spec_digest`.
- **Rationale**: the ledger already identifies specs by SHA-256 and implementation by a tree fingerprint, so these values compare directly with recorded evidence. A Git tree ID for the whole feature directory is free to compute and content-addressed.
- **Alternatives**: hashing each artifact into a combined digest (more code, same meaning); reading the local branch tip (could include unpushed commits the reviewer cannot see).

## R3. Binding recorded evidence to the head commit

- **Decision**: A criterion is `verified` only from operator-attested `verification` events (`ledger check`) whose `snapshot` equals the **implementation fingerprint of the head commit**, whose `spec_digest` equals the spec version at head, and whose `manifest_digest` equals the SHA-256 of `acceptance-evidence.json` at head. The fingerprint of a commit is computed by one new ledger function, `commit_tree(root, commit, git)`: a private temporary index, `read-tree <commit>`, `rm -r --cached -q --ignore-unmatch -- specs`, `write-tree`, then SHA-256 of the tree ID, which is the formula `implementation_tree` already uses.
- `implementation_tree` changes so both agree: it seeds its private index with `read-tree HEAD` (when `HEAD` exists), runs the existing `add -A -- . :!specs`, then removes `specs` from that index. Without the seed, tracked files that match an ignore rule were left out of the worktree fingerprint but present in a commit's, so evidence for a clean checkout could never match its commit. After the change, a clean checkout's fingerprint equals its `HEAD` fingerprint. Snapshots recorded before the change compare as different, which shows as `stale`, never as a false `verified`.
- `ledger check` adds an optional `commit` field (Git object ID) to its `verification` event when the checkout is clean, meaning its fingerprint equals `commit_tree(HEAD)`. The packet uses it to name the commit stale evidence belongs to (AC-004). Without it the packet names the spec version or the implementation snapshot's short fingerprint.
- **Rationale**: the existing rule "an AC passes only when all mapped methods pass for the same implementation snapshot and manifest version" is kept unchanged (spec assumption, PD-0002), and is now tied to the reviewed commit. Every mismatch fails safe, as `stale`.
- **Alternatives**: binding by commit only (the ledger does not record commits today, and a dirty checkout would wrongly match its `HEAD`); scanning the commits between base and head for a matching fingerprint (up to N extra Git calls per checkpoint for a label).

## R4. Evidence state of one criterion (FR-003, PD-0002)

- **Decision**: For each `AC-NNN` in spec order:
  1. no readable manifest at head, or the AC is not in it → `missing`, with what is missing (no manifest, or no mapped test);
  2. the manifest's `spec_digest` differs from the spec version at head → `stale`, naming the spec version the manifest was written for (edge case);
  3. otherwise, for each mapped test take the newest operator-attested `verification` event with that `ac_id` and `check_id`, preferring events bound to head (R3): `passed`/`failed` at head, `stale` if only events for another snapshot, spec or manifest exist, `not run` if none exist;
  4. the AC is `verified` when every mapped test passed at head; otherwise it takes the first of `failed`, `stale`, `not run` present among its tests. Each test is listed with its own result beside the AC.
- A manifest entry for an AC the spec no longer defines is listed on one "Evidence for unknown criteria" line (edge case).
- **Rationale**: the order follows PD-0002. Per-test results stay visible, so the combined state never hides a detail.
- **Alternatives**: deriving per-AC state from suite-wide `run-checks` or CI. Rejected: a passing suite does not show that a named test ran rather than being skipped, and the ledger schema already says suite-wide checks do not prove an AC.

## R5. Consequence: Autonomous runs show `not run` until the operator checks

- **Finding**: `run-checks` runs the project's `[checks]` commands as whole suites and records them in `checks.json`; it records no per-AC `verification` events. Per-AC evidence exists only after the operator runs `ballast ledger check RUN_ID AC-NNN <test>`. So an Autonomous PR's packet shows every mapped criterion as `not run` until the operator records checks. That is accurate, not a defect of the packet.
- **Decision**: The packet's criteria section ends with one fixed line telling the operator how to record per-criterion evidence (`ballast ledger check RUN_ID AC-NNN TEST`). Running the manifest's mapped tests from `run-checks` would be a new command path, which is R2 under FR-012, and is left for a follow-up Issue, proposed in the PR description.
- **Alternatives**: treating a green `run-checks` as evidence for every AC (violates R4 and the ledger schema).

## R6. Criteria parsing, and a ledger defect

- **Finding (implementation bug)**: `ledger._approved_spec_ids` matches only `- **AC-NNN**:` list items, while every spec in this repository, and the Spec Kit template, writes `1. **AC-NNN**:`. So `archive_manifest`, and with it `ledger check`, rejects every real spec with "approved spec has no AC IDs". Test fixtures use the `- ` form, which is why tests pass.
- **Decision**: one parser, `ledger.spec_criteria(text) -> list[(ac_id, title, line)]`, accepts both `- **AC-NNN**:` and `N. **AC-NNN**:` list items in document order. Both `_approved_spec_ids` and the packet use it. An ID repeated in the spec is listed once, at its first position. A spec with no IDs gives "no acceptance criteria found" and a spec link (edge case). The title is the text after the ID up to the first `**When**`, or the first 120 characters, rendered inert (R9). Fixing a defect needs no decision record (AGENTS.md).

## R7. Decisions, approvals, findings, risk and mode

- **Decision**: All are read from records Ballast already keeps. The packet never infers authority from prose.

| Packet line | Source | Label |
| --- | --- | --- |
| Mode | Autonomous: operator `run.json` mode history; otherwise `human-gated` | as recorded |
| Risk | Autonomous: `run.json` `risk.level`; human-gated: the `Risk:` line of the Issue's intake scope comment by a repository member (already read by #17); otherwise `not recorded` | names its source |
| Provisional decisions | Autonomous: operator `decisions.jsonl`, current entries | `agent-provisional`, linked to their row in the committed `autonomous/record.md` at head |
| Human decisions | `human-decisions.jsonl` (Autonomous); ledger `gate` events with a choice and `human_action` events (human-gated) | `human`, with the gate or action ID and the ledger source label (`runner`, `operator-attested`) |
| Feature decisions | `decisions.md` at head: each `DEC-NNNN` heading, `unresolved` when it has a Proposal and no Resolution | `see record`; the packet does not classify who decided |
| Open findings | Autonomous decision log findings with disposition `open` or `accepted-provisionally`; ledger `finding` events whose latest resolution is `open` | severity, linked to the report path recorded in the decision, or to `reviews/<review_id>.md` at head when it exists, otherwise to `reviews/` |

- The packet states, in fixed wording, that it is a derived summary, that the linked sources are authoritative, and that it is not an approval (FR-005). The finished text is checked against #27's `HUMAN_APPROVAL` pattern outside quoted data, the same guard #27 uses.
- **Alternatives**: parsing review report Markdown for findings. Rejected: free-form, agent-written, unreliable. Reports are linked as sources instead.

## R8. CI results

- **Decision**: one new read, `gh api --paginate --slurp "repos/<o>/<r>/commits/<head>/check-runs?per_page=100"`. Each check run is listed with name, status and conclusion. Ballast builds the link itself from the validated numeric ID, `https://github.com/<o>/<r>/runs/<id>`, and never copies a URL from the response. Commit statuses from the legacy status API are not read; the packet says "GitHub check runs" so the scope is explicit.
- CI runs are suite-wide, so they never change a criterion's state (R4). They appear in the checks section and as UI-state results (R11). A CI run still in progress shows as `in progress`, and the next checkpoint refreshes it; Ballast does not wait (edge case).
- **Clarification of the spec edge case** ("criteria whose only evidence is CI show `not run`"): under R4 a criterion's evidence is its manifest tests. The edge case applies to a UI state backed by a check run, which shows `not run` with a link while the run is pending. This reads the spec's wording against FR-003 and the spec assumption on the manifest. It changes no behavior.

## R9. Rendering agent-written text inertly (FR-013, FR-016)

- **Decision**: every value from an agent-writable source (spec titles, decision summaries, finding reasons, DEC headings, check and UI-state names) goes through one function, `inert(text, limit)`:
  - one line, whitespace collapsed, capped at `limit` characters with `…`;
  - `&`, `<`, `>` HTML-escaped, so no marker, comment or tag can appear raw in the body;
  - Markdown punctuation `\ ` `` ` `` `* _ [ ] ( ) # | ! ~` backslash-escaped, so no link, image, emphasis or table cell break;
  - `://` and `www.` broken with a zero-width space, so GFM autolinks cannot form;
  - `@` followed by a word broken with a zero-width space (no mentions);
  - GitHub token shapes (`gh[pousr]_…`, `github_pat_…`) and `Authorization:`/`Bearer` values replaced with `[redacted]`.
- Every link in the packet is built by Ballast from validated parts: owner and repo, a commit ID, and a repository path checked against `PATH_SEGMENT`. None is copied from a source.
- States and labels are computed from records, never from text, so hostile text cannot change them. The finished packet must contain exactly one begin marker and one end marker, its own; otherwise it is not published (`failed-retryable/internal-error`).
- **Alternatives**: `autonomy.neutralize` alone, which leaves Markdown links and autolinks working; code spans, which would leave raw marker text in the body.

## R10. OpenAPI comparison (FR-010, FR-012)

- **Decision**: the project configures `[review] openapi = "<repository path>"` in `ballast.toml` (R12). The packet reads the document at base and head with `gh api "repos/<o>/<r>/contents/<path>?ref=<sha>"`, the read #17 already uses for the template. Responses over 1 MB, which the contents API does not return inline, give `could not compare (too large)`.
- **JSON only**: workflow tools are standard-library-only and Python has no YAML parser. A YAML document gives `could not compare (not JSON)`, and the documentation says to commit a JSON rendering. YAML support would need a dependency decision of its own.
- Comparison: operations are `(METHOD, path)` for the eight HTTP methods under `paths`. Added, removed and changed are by canonical JSON of the operation together with its path-level parameters. **Potentially breaking**: a removed operation; a removed parameter; a parameter newly `required`; a request body newly `required`; a top-level request-body schema property removed or newly in `required` (local `#/components/...` `$ref` resolved, depth 5, cycle-safe). Response changes count as `changed` without the breaking flag. The section always carries the fixed sentence that the classification needs human review and is not an approval.
- States: `not configured` (one line), `no API change`, `added in this PR`, `removed in this PR`, `could not compare (<fixed reason>)`. Each reason is fixed: `not JSON`, `too large`, `not an OpenAPI document`, `unreadable`, `github-error`. The rest of the packet is published in every case (AC-017).
- Limits: at most 2,000 operations per document, or `could not compare (too large)`. At most 50 lines per list in the PR; the archive copy keeps everything.
- **FR-012 check**: no new program is run and nothing is downloaded to execute. The document is read as data through the existing `gh`.
- **Alternatives**: `openapi-diff` or `oasdiff` (a download or dependency, so R2); reading the base from local Git (the base commit may not be present locally, and Ballast never fetches).

## R11. UI states (FR-011)

- **Decision**: `[[review.ui_states]]` entries in `ballast.toml`: `name` (≤ 80 characters), `criteria` (list of `AC-NNN`), and exactly one of `path` (a repository path to a committed screenshot or result, checked at the head commit with `git cat-file -e <head>:<path>`) or `check` (the name of a GitHub check run on the head commit, from R8's response).
- Result beside each mapped criterion: a link to the blob at head, or `passed` / `failed` / `not run (in progress)` with a link to the check run, or `missing`. A UI state never changes the criterion's state. A criterion that the spec does not define is reported as a configuration problem in the UI section.
- Capturing screenshots is #22 and out of scope. Ballast only links what exists.

## R12. Configuration location

- **Decision**: a new optional `[review]` table in the project's `ballast.toml`: `openapi` and `ui_states`. `ballast.toml` is already a protected, trusted input read by the launcher (`[github]`, `[checks]`), and `ballast trust` already covers changes to it. Agents cannot change it, so an agent cannot point the API comparison elsewhere to hide a change.
- Invalid configuration (wrong types, unsafe path, unknown AC format, more than 50 UI states) does not stop the packet. The API or UI section says `configuration invalid (<fixed reason>)`, and the rest is published.
- **R2 recheck**: this adds keys to an existing trusted input. It does not add a trusted input, change a refusal condition or move state, so it stays R1. See [R18](#r18-risk-recheck-against-the-r2-boundaries).
- **Alternatives**: a committed file under `docs/policies/project/`. It is agent-writable at head; reading it from the base commit would work but adds a second configuration surface.

## R13. Marked section, idempotency and the "unchanged" outcome

- **Decision**: markers `<!-- ballast:acceptance-packet:begin -->` and `<!-- ballast:acceptance-packet:end -->`. Exactly one pair is replaced in place. With none, the packet is appended after all existing text with `_after` (#17), so it is added again when a human deletes it (AC-014). Any other count, or an end before a begin, gives `failed-retryable/section-unmanaged`, and nothing is edited.
- The packet text contains one line `- Generated: <UTC ISO 8601>`. The comparison masks that line. Equal masked text → `unchanged`, no `pr edit` (AC-010, FR-009). The ledger records `packet_digest`, the SHA-256 of the masked text.
- Write: re-read `pulls/<n>` just before editing. A body that changed since the step's first read gives `failed-retryable/body-changed`, and nothing is written (#17 DEC-0007). `gh pr edit <n> --repo <o>/<r> --body-file -` with the full new body is the only write, the command ADR-0003 already allows.
- **Clarification of AC-010**: #17 refreshes its own `Last checkpoint` line on each checkpoint, so the PR description can change even when the packet does not. AC-010 and FR-009 are read as "publishing the packet makes no edit". The test runs with a fixed clock, as #17's do, so the whole checkpoint makes no edit call. This is a reading of the wording and changes no behavior.

## R14. Size (FR-014, AC-021)

- **Decision**: budget = 65,536 (GitHub's body limit) − length of the body outside the packet section − 1,024 margin. The packet is rendered in levels, the first that fits wins:
  1. full;
  2. `verified` criteria collapse to one line of IDs, per-test detail is dropped for them, and the sources section keeps its links;
  3. the API and UI lists keep counts and breaking items only;
  4. per-test lines of non-`verified` criteria are dropped, keeping each criterion's state and reason.
- Header, risk, counts, every non-`verified` criterion, every open finding and every provisional decision are never dropped. A shortened packet says so and names the complete copy (R15). If level 4 still does not fit → `failed-retryable/too-large`, and the existing section is left unchanged.

## R15. Run-archive copy

- **Decision**: the complete level-1 packet is written atomically, mode 0600, to `<git common dir>/speckit-runs/<run>/acceptance-packet.md` (`ledger.archive_dir`), overwritten at each checkpoint that builds a packet. It is the local operator archive #17 and the ledger already use, outside every worktree.
- The PR cannot link a local file. A shortened packet therefore names it as `speckit-runs/<run>/acceptance-packet.md in the operator's clone (run <id>)`: a relative location, never an absolute path or host (AGENTS.md privacy rule). This is how AC-021's "links the complete packet in the run archive" is met.

## R16. Ledger event

- **Decision**: a new kind `acceptance_packet`, source `runner`, `RUNNER_ONLY`, additive, `schema_version` stays 1 (the pattern #17 used). Fields: `outcome` (`published`, `updated`, `unchanged`, `pending`, `failed-retryable`), `reason?`, `pr_number?`, `head?`, `base?` and `feature_version?` (new `oid` type: 40 or 64 lowercase hex), `packet_digest?` (sha), `shortened?` (bool), and the counts `verified`, `failed`, `not_run`, `stale`, `missing` (int, optional). `published`, `updated` and `unchanged` require `pr_number`, `head`, `base`, `feature_version` and `packet_digest`; `pending` and `failed-retryable` require `reason`. The report adds `acceptance_packet`, the latest event, the way it shows `pull_request`. `verification` gains `commit?` (`oid`) (R3).
- No free text: causes are fixed reason codes, and the remedy appears only in the printed line.

## R17. Outcomes, reasons and remedies

| Outcome / reason | When | Remedy printed |
| --- | --- | --- |
| `published` | no section existed | — |
| `updated` | section replaced | — |
| `unchanged` | masked text equal | — |
| `pending/no-pr` | #17 outcome is `pending` or `failed-retryable` | as the Draft PR line says |
| `pending/pr-blocked` | #17 outcome is `blocked-*` (closed, merged, ambiguous, unlinked) | as the Draft PR line says |
| `pending/head-not-local` | PR head commit absent locally | fetch the feature branch, then resume |
| `failed-retryable/github-*`, `gh-*` | same classification as #17 (`_classify`) | #17's remedy text |
| `failed-retryable/body-changed` | body changed between read and edit | none: the next run retries |
| `failed-retryable/section-unmanaged` | not exactly one marker pair | keep at most one acceptance-packet section in the PR body |
| `failed-retryable/source-unreadable` | `spec.md` absent, unreadable or over 1 MB at head (any other feature artifact over 1 MB is listed as `not present (too large)`, AC-008) | commit a readable `spec.md`; the next run retries |
| `failed-retryable/manifest-malformed` | `acceptance-evidence.json` at head is not valid schema-1 JSON | fix the manifest; `ballast ledger check` validates it |
| `failed-retryable/ledger-invalid` | `ledger.read` reports problems | run `ballast ledger report RUN_ID` |
| `failed-retryable/too-large` | level 4 exceeds the budget | shorten the PR description outside Ballast's sections |
| `failed-retryable/internal-error` | anything else, with the exception type | report it with the run ID; the next run retries |

A malformed manifest is a failure, not "every criterion missing", because AC-019 names a malformed source as a build failure and rendering `missing` would misstate what was recorded. A missing manifest is `missing` (AC-003). Tamper or in-progress markers produce no packet attempt, as #17's `skipped`.

## R18. Risk recheck against the R2 boundaries

| Boundary ([project workflow](../../docs/policies/project/workflow.md)) | Touched? |
| --- | --- |
| Headless-agent permissions | No. `claude-settings.json`, wrapper rules, protected inputs and tamper handling are unchanged. Agents get no new tool or token. |
| Launcher trust model: trusted inputs, refusal conditions, state location | No new trusted input: `[review]` keys sit in the existing protected `ballast.toml`. Refusal conditions are #17's. State goes in the existing run archive. |
| What `ballast` executes or downloads | No new program. The same resolved `git` and `gh`. New read-only calls: `gh api` check runs and contents at a commit, and `git` plumbing reads (`cat-file`, `ls-tree`, `rev-parse`, `read-tree`/`rm --cached`/`write-tree` on a private index). Nothing is downloaded to execute. |
| Installed paths and ignore block | No. `packet.py` installs with `tools/spec_workflow/`, which `tools/setup` already copies. |

**Result: R1 holds.** The change does extend ADR-0003's fixed command allowlist, which that ADR says needs a new ADR. That is proposed as ADR-0005 (plan § Architecture Boundaries). The plan-gate reviewer should confirm R1 explicitly. If they judge the allowlist extension to be a trust-model change, the risk becomes R2: an Autonomous run may continue, with the R2 notice in the PR.
