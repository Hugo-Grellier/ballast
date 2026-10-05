# Implementation Plan: Branch Synchronization Before Agent Steps

**Branch**: `feat/18-branch-sync` | **Date**: 2026-10-05 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/18-branch-sync/spec.md` (intent approved 2026-10-05, digest in [intent.md](intent.md))

**Risk**: R2 (A-7). The trusted launcher now fetches, rewrites and pushes the feature branch with the operator's Git credentials. DEC-0001 to DEC-0007 in [decisions.md](decisions.md) are resolved. Revision 2 applied [plan review 1](reviews/plan-review-fable-1.md); revision 3 applied [plan review 2](reviews/plan-review-fable-2.md) (N-01 to N-12), DEC-0005 option A and DEC-0006 option B; revision 4 applies [plan review 3](reviews/plan-review-fable-3.md) (P-01 to P-06) and DEC-0007 option B. Explicit human approval is required before implementation.

## Summary

Before any agent step of `ballast run start`, `resume` or `continue`, `run.py` calls a new trusted module, `branch_sync.py`, which was imported at startup after the launcher verified the inputs. The module takes a per-branch lock in the operator state directory (reusing `draft_pr._Locked` with no wait) and checks the checkout: no operation in progress, and on the run's pinned branch. Only `start` pins the branch; a `resume` or `continue` of a run with no branch pin blocks (DEC-0006). It then reads the base and the published branch from the repository pinned in `ballast.toml`, using `ls-remote` and, only when objects are missing (probed in the throwaway, never through the checkout's `origin`), `fetch`, in a throwaway bare repository with an empty configuration and maintenance and gc disabled, because it shares the checkout's object store. The run's recorded base is used, or that repository's default branch for a run that has none. When the base is an ancestor of HEAD, the outcome is `up-to-date`. Otherwise only a feature branch (named for the feature's Issue, neither the base nor the default branch) is rewritten; the base branch is only fast-forwarded, and any other branch blocks. On a clean checkout, the check replays the feature's commits onto the base with `git --attr-source=BASE merge-tree --write-tree` and `hash-object`, in the same throwaway repository. The index and working tree are never touched during the replay, so a conflict changes nothing. Before anything is pushed, it checks that the update would overwrite no ignored file and that `read-tree --dry-run` succeeds, and writes a write-ahead record keyed by the branch, next to its lock. A published branch is then pushed with a lease on the observed commit. Only then is the checkout moved with `read-tree -m -u` and a compare-and-swap `update-ref`. A sync interrupted after its push is completed by the next invocation on that branch, whatever its run ID (DEC-0005). Every HEAD change, including a fast-forward to the published branch, is followed by the protected-input trust recheck. Files both the base and the feature changed mark the plan and review evidence stale in the ledger and the Draft PR. Every check records one `branch_sync` ledger event. A block prints `BLOCKED_UPSTREAM_SYNC`, the cause and one recovery action, exits 1 and starts no agent. In an Autonomous run it becomes an `upstream-sync` block. See [research.md](research.md) for each decision.

## Technical Context

**Language/Version**: Python ≥ 3.11 standard library only, under `python3 -I -S` (as `run.py`).

**Primary Dependencies**: None at runtime. External: `git` 2.41 or later (`merge-tree --merge-base` is 2.40; the global `git --attr-source` option is 2.41, N-02), resolved outside every working tree and temp root, as in #17. Shallow checkouts (N-12) and partial clones (DEC-0007 option B) are refused; `GIT_NO_LAZY_FETCH=1` stays on every command as defense in depth. `gh` is not used.

**Storage**: The identity pin `<state_dir>/draft-pr/<run>.json` (extended with `base` and `base_commit`), the lock `<state_dir>/branch-sync/<key>.lock` and, next to it, the branch-keyed write-ahead record `<state_dir>/branch-sync/<key>.json` (N-01), the ledger `events.jsonl` (new kind) and `branch-sync/<event_id>.json` under `<git common dir>/speckit-runs/<run>/`. New Git objects go into the checkout's object store; nothing in the throwaway repository can gc, repack or prune it.

**Testing**: `unittest`, offline, against real temporary Git repositories with a local bare repository as the remote ([research R14](research.md#r14-testing-approach), [quickstart.md](quickstart.md)).

**Target Platform**: The qualified 1.0 host: Linux, systemd user session, GitHub.

**Project Type**: Workflow tool inside the installed standard (`tools/spec_workflow/`).

**Performance Goals**: An up-to-date check costs one `ls-remote` (30 s limit) and at most one incremental fetch (600 s limit), and no fetch when both commits are already local (SC-005). `ls-remote` stays on every invocation: it tells "not published" apart from a failure, and the feature-branch rule needs the default branch (research R3, F-14). The replay costs one `merge-tree` and one `hash-object` per feature commit.

**Constraints**: Standard library only; no shell; no bare `git`; never stash, reset, discard, or push without a lease; never overwrite or delete ignored files; never rewrite or push the base or any branch that is not the feature branch; no maintenance or gc in the throwaway repository; no terminal prompts; no program named by the checkout's configuration, attributes or hooks runs; Git output is never printed.

**Scale/Scope**: A new module of about 500 lines, about 60 lines in `run.py`, about 40 in `ledger.py`, about 20 each in `autonomy.py` and `draft_pr.py` (`_Locked` wait argument), a few in `tools/ballast` (doctor), one new test file, and documentation.

No NEEDS CLARIFICATION remains. DEC-0001 to DEC-0007 are resolved and the spec is amended (SC-002's post-push exception, DEC-0005; the unpinned-run edge case, DEC-0006).

## Constitution Check

*Gate before Phase 0, re-checked after Phase 1. Result: **PASS** both times, no violations. Re-checked after revision 2: DEC-0001 to DEC-0004 are resolved and refine the spec without touching an invariant; F-01 to F-14 strengthen BL-INV-002 and BL-INV-005. Re-checked after revision 3: N-04 and N-09 close two more paths to agent-writable configuration and interactive programs (BL-INV-002); N-01, N-03 and N-11 make the half-done-sync postconditions hold on every rerun path (BL-INV-005); N-05 removes a second definition of the rewrite boundary. Re-checked after revision 4: P-01 keeps the recovery path inside the rewrite boundary (BL-INV-003); P-02 to P-04 make every crash point land in a row whose outcome the operator can act on (BL-INV-005); DEC-0007 removes the partial-clone path rather than adding a second Git floor.*

| Principle | How the design holds it |
| --- | --- |
| 1. Projects own only their files (BL-INV-001) | The module ships in `tools/spec_workflow/`, which `tools/setup` already installs into the ignored `.ballast/`. Lock, pin and throwaway repository live in the operator state directory, and ledger records live in the Git common directory. The only tracked change is the feature branch's own history, rewritten on the operator's behalf, which is the feature. |
| 2. Nothing executes from a writable checkout (BL-INV-002) | `branch_sync` is imported by `run.py` at startup, after `launcher._refusal`, before any agent step. `git` is resolved outside working trees and temp roots. Fetch, replay and push run in a throwaway repository with an empty config, an empty template, no terminal prompt, and maintenance and gc disabled (research R2, R3a), the `autonomy._push` pattern. The committer identity comes from the operator's configuration, never from the checkout. Merge attributes come from the fetched base, never from the feature branch. Checkout-side commands are local plumbing with hooks, fsmonitor and filters disabled. The repository comes from protected `ballast.toml`, never from `.git/config` (AC-017). After every HEAD change, including the AC-015 fast-forward, the launcher's own `trusted_inputs` comparison runs again (R9). |
| 3. Delegated authority (BL-INV-003) | The new authority (fetch, push with lease) stays in launcher code and is limited to the feature branch named for the Issue (R15). Agents gain nothing. `claude-settings.json`, the Codex sandbox and the token stripping are unchanged, and agents still cannot push. No agent step can invoke, skip or configure the check (FR-012). |
| 4. A project picks a version, never a source (BL-INV-004) | Not touched: nothing about the Ballast download path changes. |
| 5. Postconditions over exit codes (BL-INV-005) | `synchronized` is recorded only after the CAS `update-ref` succeeded and HEAD equals the replay result. The push is accepted only on the lease. A `git` exit 0 alone is never treated as success. A half-done sync is detected from the write-ahead record and the observed branches, not assumed. |
| 6. Portable, dependency-free tools | Standard library only. Git is already required. |
| 7. Generic by default | No project names. Any GitHub repository and base name works. |
| 8. Executable evidence | Every AC, every cause and the refusal paths (hostile config, hooks, drivers, names) have a scenario in [quickstart.md](quickstart.md). |
| 9. A provisional decision is never human approval (BL-INV-006) | A sync is never recorded as a decision (FR-011). The Autonomous block is a block, and DEC-0001 to DEC-0004 were resolved by the operator, not by an agent. |

## Architecture Boundaries

- **Affected areas**: the run entry point `tools/spec_workflow/run.py` (call sites and exit), a new trusted module `tools/spec_workflow/branch_sync.py`, the ledger `tools/spec_workflow/ledger.py` and its schema note, `autonomy.py` (block category, restart recovery command, resume refusal wording), `draft_pr.py` (pin writer moved out, `_Locked` wait argument, stale-evidence entries in the section), `tools/ballast` (doctor Git version), and operator documentation.
- **Contracts and data flow**: `run.py` → `branch_sync.synchronize(root, run_id, ...)` → the pin (operator state), `ballast.toml` and Git (the resolved `git`, throwaway repository, then the checkout) → one `Outcome` → `ledger.append` (`branch_sync` event), the optional stale-evidence file, and printed lines. On `blocked`, `run.py` stops, or for an Autonomous start records the block through `_stop`. On success, `_launch` runs as before, and the final Draft PR checkpoint renders stale-evidence entries. GitHub remains the source of truth for the published branch. The ledger only records observations. The pin stays the single feature identity (R12). See [contracts/branch-sync.md](contracts/branch-sync.md), [contracts/ledger-branch-sync-event.md](contracts/ledger-branch-sync-event.md) and [data-model.md](data-model.md).
- **Architecture references**: [constitution](../../.specify/memory/constitution.md) BL-INV-002, BL-INV-003 and BL-INV-006; [technical spec §90 and §91](../TECHNICAL-SPEC.md#90-v03-target); [roadmap Priority 3 item 3](../../docs/plans/2026-10-02-product-roadmap.md); [ADR-0003](../../docs/adr/0003-launcher-github-authority.md) (launcher GitHub authority) and [ADR-0004](../../docs/adr/0004-autonomous-provisional-decisions.md); [project R2 rules](../../docs/policies/project/workflow.md); [ledger schema](../../tools/spec_workflow/ledger-schema.md); #17 [research](../17-draft-pr/research.md) R3 and R5 and #27 FR-023.
- **Proposed architecture decisions** (each needs human approval, then an ADR):
  1. **ADR-0005 Launcher-side branch synchronization.** Status: proposed. This extends ADR-0003's operator-side authority from GitHub API calls to Git transport. Before agent steps, trusted launcher code may fetch from and push with a lease to the repository pinned in `ballast.toml`, and rewrite the run's feature branch. It states the rewrite rule (DEC-0004, DEC-0003): a feature branch is one whose name, split at `/`, `-`, `_` and `.`, has a segment equal to the feature's Issue number and that is neither the run's base nor the pinned repository's default branch, decided by one predicate (`autonomy.is_feature_branch`) shared with Autonomous eligibility (N-05); a `ballast run` invocation without an Issue number is never synchronized by rewrite and blocks `not-feature-branch` when behind, and bugfix and assess runs started with `specify` are not synchronized (N-08); only a feature branch is rewritten or pushed; the base branch is only fast-forwarded locally; any other branch blocks as `not-feature-branch` when behind. Network and merge operations run only in a throwaway repository with an empty configuration and template, no prompts, and no maintenance or gc, since it shares the checkout's object store. The committer identity comes from the operator's configuration. The checkout sees only local plumbing with hooks, fsmonitor and filters disabled. Nothing is pushed without a lease. Only `start` pins a run's branch (DEC-0006). Shallow checkouts and partial clones are refused (DEC-0007). The recovery of a half-done sync never pushes unless its write-ahead record records a push, so a fast-forward record cannot push the base or another branch (P-01). It lists the differences from `git rebase` (unsigned commits, attributes from the base, no `rebase.*` configuration). Later features (#21 Autonomous resume, roadmap item 4 branch exclusion) will extend this boundary.

## Repository Impact

| Path | Change |
| --- | --- |
| `tools/spec_workflow/branch_sync.py` | New: lock (via `draft_pr._Locked`), identity and pin (written at `start` only; an unpinned `resume` or `continue` blocks; `continue`'s source branch and base; `base` written after `ls-remote`), in-progress check, Git version (2.41) and checkout-shape checks (shallow, partial clone), its own throwaway repository (`--template=`, object format, `NO_MAINTENANCE`, `GIT_TERMINAL_PROMPT=0`, `GIT_NO_LAZY_FETCH=1`, askpass disabled, no terminal), object probes in the throwaway, `ls-remote` and conditional fetch, the branch-keyed write-ahead record and its recovery table, feature-branch rule (via `autonomy.is_feature_branch`), published-branch classification, AC-015 fast-forward, replay with the global `git --attr-source`, operator committer identity, pre-mutation checks (ignored files, `read-tree --dry-run`, protected diff), push with lease, CAS local update and restore, trust recheck on every HEAD change, overlap, pin update, outcome, recovery text, ledger event, stale-evidence file. |
| `tools/spec_workflow/run.py` | Import `branch_sync`. Call it at the four sites in the [contract](contracts/branch-sync.md#call-sites-in-runpy); `start` passes `starting`; `continue` draws the new run ID first and passes the source pin's branch and base and the source run ID, under which a blocked continuation's event is recorded (N-07). On block, print and return `EXIT_BLOCKED` (or `EXIT_INTERRUPTED` for Ctrl-C) before `_launch`, and in an Autonomous start record the `upstream-sync` block via `_stop`. `_continue_command` refuses a run whose block is `upstream-sync`. Stop pinning in `_launch`. Update the docstring (FR-014). |
| `tools/spec_workflow/autonomy.py` | `is_feature_branch(name, issue, base, default_branch)`, the one feature-branch predicate, owned here because `branch_sync` imports `autonomy` and `autonomy` imports only `launcher` (N-05); `check_eligibility` uses it and `BRANCH_REFUSAL` says "named for the Issue". `upstream-sync` in `BLOCK_CATEGORIES` and `RECOVERY`; `recovery_command` returns the `ballast run start --mode autonomous` restart for it. `RESUME_REFUSAL` points at #21. `_push` is not changed: it keeps its alternates throwaway. |
| `tools/spec_workflow/draft_pr.py` | The pin writer moves to `branch_sync` (`pin_branch` is removed or delegates; `_branch_pin` unchanged and ignores the new fields). `_Locked` gains `wait` (default `LOCK_WAIT`). `_section` appends dated stale-evidence entries for the feature (R11). |
| `tools/spec_workflow/ledger.py` | `branch_sync` in `FIELDS` and `ENUM_FIELDS` (13 causes, `recovered`, `recovered_from`); `ref` and `commit` value types; per-outcome required fields; excluded from `record`; latest outcome in `report` and `_text_report`. |
| `tools/spec_workflow/ledger-schema.md` | Document the kind, its fields, the side file and the compatibility note. |
| `tools/ballast` | `doctor` reports Git older than 2.41 ([DEC-0001](decisions.md), N-02). |
| `tests/test_branch_sync.py` | New: scenarios 1–3, 5–12, 14–47 of [quickstart.md](quickstart.md); `tests/test_autonomy.py` gains the shared `is_feature_branch` cases (T009). |
| `tests/test_spec_workflow.py` | Scenario 4. Call order and sites, no `specify` execution after a block, exit 1 and 130, the pin written by the check only and only at `start`, `continue` blocked before any record, its event in the source run, no archive or pin for the new ID. |
| `tests/test_autonomous_run.py` | Scenarios 13 and 44; `upstream-sync` restart command; `continue` refused; no decision record; eligibility through `is_feature_branch`. |
| `tests/test_agent_run_ledger.py` | `branch_sync` validation (required fields per outcome, `retryable` rule, types) and report. |
| `tests/test_draft_pr.py` | Stale-evidence entries rendered, escaped and bounded; `_Locked` with `wait=0` returns at once. |
| `tests/test_doctor.py` | Git version floor. |
| `templates/policies/spec-kit-workflow.md` | New section "Branch synchronization": when the check runs, which branches it may rewrite (and that bugfix and assess runs started with `specify` are not synchronized), the Git 2.41 floor, shallow and partial clones, unpinned runs, the outcomes, every cause with its recovery, the `protected-input` exception, what is never done, the differences from `git rebase`, and staleness in the Draft PR (FR-014). The installed `docs/policies/` copy is refreshed by `ballast setup`. |
| `README.md` | One sentence in the workflow section pointing to that section. |
| `specs/TECHNICAL-SPEC.md` | §90/§91: mark "safe branch synchronization on start and resume" as delivered by #18, and record the remaining #21 dependency. |
| `docs/adr/0005-launcher-branch-synchronization.md` | New, status proposed: the authority, the throwaway boundary and the feature-branch rewrite rule (DEC-0003, DEC-0004). Accepted with the feature. |

`tools/setup`, `tools/cli.toml`, `claude-settings.json`, `agent.py`, `launcher.py` and the workflow YAML files are unchanged. `launcher.py`'s `trusted_inputs` and `state_dir` are reused, not changed.

## Feature Artifacts

```text
specs/18-branch-sync/
├── intent.md
├── spec.md
├── plan.md            # this file
├── research.md        # Phase 0 decisions R1–R15 (R3a: throwaway repository, partial and shallow checkouts)
├── data-model.md      # pin, write-ahead record, outcome, causes, transitions, stale record
├── contracts/
│   ├── branch-sync.md
│   └── ledger-branch-sync-event.md
├── quickstart.md      # validation scenarios mapped to ACs
├── decisions.md       # DEC-0001–0007, resolved
├── checklists/
├── tasks.md           # next: speckit-tasks
└── reviews/           # plan-review-fable-1.md, -2.md, -3.md
```

## Review notes

- **Decisions resolved**: DEC-0001 (`git-unavailable`, `internal-error`; floor raised to Git 2.41 by N-02), DEC-0002 (`protected-input` keeps the sync; recheck on every HEAD change), DEC-0003 (base branch: fast-forward only, never push), DEC-0004 option A (feature-branch rule, `not-feature-branch`), DEC-0005 option A (SC-002's post-push exception; the next invocation completes, no compensating push) and DEC-0006 option B (an unpinned `resume` or `continue` blocks `wrong-branch`; the plan's revision-2 "pin at resume" and review 2's recommendation 2 are superseded). The spec's FR-005, FR-008, FR-009, SC-002, AC-021 and edge cases are amended.
- **Recovery table, revision 3**: changed materially. The N-01 fix by itself does not change it (only where the record lives and who can read it). Three other changes do: a new row 5 for a local branch that advanced beyond `old_head` while the published branch is at `new_head` (N-03); the `cat-file -e new_head` precondition and "invalid record is `internal-error`, kept" (N-11); and a reordering found while applying them: the "interrupted between `read-tree` and `update-ref`" row now precedes "push done, local not" and covers a published branch, because in revision 2 that published case hit row 3's "still clean" check and blocked `dirty` instead of completing. Review 2 asked for a third plan review only if the N-01 fix changed the table; the N-01 fix did not, but the table did, so whether to run a third review (scoped to research R5 and quickstart 18, 40 and 43) is the operator's call.
- **Choices made in this revision that the reviewer did not spell out**: `is_feature_branch` lives in `autonomy`, not `branch_sync`, to avoid an import cycle (N-05); a blocked `continue` records under the source run rather than accepting phantom archives (N-07); partial clones were supported on Git 2.46 or later in revision 3 (N-04), now refused by DEC-0007 option B, with the support design kept in research R3a as a later extension; the CAS-failure restore runs only while the tree is still exactly `NEW` (found with N-03), and targets the current HEAD's tree since revision 4 (P-04); the record's originating run is reported as `recovered_from`.
- The check runs before the Draft PR checkpoint of the same invocation, so the PR's base sees the synchronized branch. A blocked human-gated invocation runs no checkpoint (R13).
- `ballast run resume` stays refused for Autonomous runs (A-9). Only the refusal's wording moves to #21.
- **Recovery table, revision 4** (plan review 3): row 3 reduced to the index probe (P-02); a new row 3b for a crash during `read-tree` that blocks with one printed command, consistent with the spec edge case "interrupted synchronization … never resumes a half-done rebase on its own" (P-03); rows 2 and 5 limited to records that record a push, with the invariant stated under the table (P-01). Review 3 marked P-03 as allowed to become a task; it is in the design now, so `speckit-tasks` derives its tasks from R5 like the other rows.
- Required reviews (R2): security review (new Git transport authority with operator credentials, untrusted names and config, the throwaway-repository boundary, lazy fetch and askpass), engineering review, test review, and documentation review for the policy section and ADR-0005. Plan reviews 1, 2 and 3 were same-provider (Codex quota exhausted until 2026-10-10); keep the cross-provider slot for the implementation.

## Complexity Tracking

No constitution violations.

## Revision 2 (after plan-review-fable-1)

| Finding | Addressed in |
| --- | --- |
| F-01 throwaway gc can prune the checkout | research R3a (`NO_MAINTENANCE`, object sharing, why gc cannot reach); contract § External commands and guarantee 6; quickstart 37. `_push` unchanged. |
| F-02 AC-015 fast-forward skips the trust recheck | research R4 step 14, R9 (recheck on every HEAD change, pre-mutation protected diff); contract guarantee 7; quickstart 21, 23 |
| F-03 half-done sync after the push | research R5 (pre-mutation checks with `read-tree --dry-run`, write-ahead record in the pin (moved to a branch-keyed file by N-01, revision 3), recovery state machine, known limit (resolved by DEC-0005)); data model pin `sync`, `recovered`; ledger contract `recovered`; quickstart 18, 19 |
| F-04 / DEC-0004 rewrite boundary | research R15, R4 steps 7 and 10; contract § Which branches may be rewritten, `not-feature-branch`; ADR-0005 (proposed) rule; quickstart 28 |
| DEC-0003 base branch | research R15; quickstart 29 |
| F-05 attributes in the bare throwaway | research R2 (`--attr-source=NEW_BASE`, residual differences); quickstart 8 |
| F-06 Autonomous recovery | research R10 (restart command, `continue` refused); data model § Autonomous block; quickstart 13 |
| F-07 ignored files overwritten | research R5 step 1, R6; contract `dirty` details; quickstart 6 |
| F-08 test gaps | quickstart 9 (no cached base), 29, 30, 31, 18, 35 (data model `internal-error` row fixed), 24 (hostile keys), R14 and quickstart "unchanged" (`ls-files -s`) |
| F-09 object format | research R3a (`--object-format`); quickstart 38 |
| F-10 missing pin, `continue`'s branch | research R12; contract entry point `branch`; quickstart 4, 11 |
| F-11 prompts, template hooks | research R3a (`GIT_TERMINAL_PROMPT=0`, no terminal, `--template=`); quickstart 39 |
| F-12 committer identity | research R2 (`git var GIT_COMMITTER_IDENT` in the throwaway); quickstart 24 |
| F-13 AC-015 with a dirty tree | research R4 (step 8 and "AC-015 with a dirty tree"); quickstart 22 |
| F-14 `ls-remote` round trip | research R3 (kept on every invocation, with the reason; fetch made conditional); plan § Performance Goals |
| Lock reuse (review scope note) | research R7 (`draft_pr._Locked` with `wait=0`) |
| DEC-0001 review corrections | data model `internal-error` row; contract exit 130 for Ctrl-C |

## Revision 3 (after plan-review-fable-2)

| Item | Addressed in |
| --- | --- |
| N-01 write-ahead record keyed by run | research R5 step 2 (`<state_dir>/branch-sync/<key>.json` next to the lock, with `branch`, `run_id`, `written_at`), R4 step 6, R7, R12 (pin no longer holds it); data model § Write-ahead record; contract entry point and guarantee 8; ledger contract `recovered_from`; quickstart 18 (rerun as `resume`, Autonomous restart, `continue`, new `start`) |
| N-02 `--attr-source` placement, Git 2.41 | research R2 step 1 argv and Requirement, R4 step 2; contract § External commands and `git-unavailable` rows; plan § Technical Context, § Repository Impact (`doctor`); DEC-0001 floor (decisions.md round-2 note); quickstart prerequisites, 8 (argv log), 36 |
| N-03 local advanced beyond `old_head` | research R5 recovery row 5, post-push `dirty` advice ("move aside without committing"), row-5 `conflict` recovery, CAS restore guard; contract `dirty` and `conflict` rows; data model causes; quickstart 40 |
| N-04 lazy fetch in a partial clone | research R3 step 2 (probe in the throwaway, `GIT_NO_LAZY_FETCH=1`), R3a (checkout-side `GIT_NO_LAZY_FETCH=1`, partial clone below 2.46 refused, blob-presence check), R5 step 1; contract § External commands (no probes in the checkout); quickstart 41 (partial-clone support superseded by DEC-0007 option B in revision 4) |
| N-05 two definitions of "feature branch" | research R15 "One predicate" (`autonomy.is_feature_branch`, owner and reason); plan § Repository Impact `autonomy.py`, ADR-0005; contract guarantee 10; quickstart 44 |
| N-06 pin `base` before its `ls-remote` | research R3 step 1, R4 steps 4–5, R12 `base`; data model pin `base`; contract entry point; quickstart 3, 11 |
| N-07 phantom archive on a blocked `continue` | research R1, R12; contract entry point (`source_run`) and call sites; ledger contract validation note; quickstart 4 |
| N-08 vacuous bugfix/assess claim | research R15 (no-Issue invocations block; bugfix and assess via `specify` not synchronized); plan ADR-0005 and policy row; quickstart documentation check |
| N-09 askpass | research R3a environment (`GIT_ASKPASS` empty, `SSH_ASKPASS` removed, `SSH_ASKPASS_REQUIRE=never`, `DISPLAY`/`WAYLAND_DISPLAY` removed); contract § External commands; quickstart 39 |
| N-10 base-branch fast-forward vs dirty | research R4 step 10 and "Every fast-forward is an R5 mutation", R5 step 1; data model transitions; quickstart 29 (dirty variant) |
| N-11 missing `new_head`, invalid record | research R5 recovery preconditions and row 3 probe (reduced to `diff-index --cached --quiet new_head` by P-02 in revision 4); data model § Write-ahead record, `internal-error` row; contract `internal-error` row; quickstart 43 |
| N-12 shallow checkouts | research R3a, R4 step 2; contract `git-unavailable` row; data model causes; quickstart 42 |
| DEC-0005 option A | research R5 "A block after a successful push" (detail "the published branch already holds …", recovery "rerun to finish the synchronization"); contract post-push row and guarantee 8; data model `busy`/`internal-error` rows; quickstart 18, 40; coverage row "SC-002 exceptions" |
| DEC-0006 option B | research R4 step 4, R12; contract entry point, `wrong-branch` row, guarantee 9; data model pin `branch` and `wrong-branch` row; quickstart 4, 11 |

## Revision 4 (after plan-review-fable-3)

| Item | Addressed in |
| --- | --- |
| P-01 row 5 pushes for a fast-forward record | research R5 step 2 (`published_old` as the "records a push" marker), step 3 (push skipped when `NEW == OBSERVED`), recovery preamble, rows 2 and 5 (precondition), invariant under the table; R4 "Every fast-forward is an R5 mutation"; data model `published_old`, write-ahead note, transitions; contract guarantee 3; quickstart 45, 40 (third variant: no push when `NEW == OBSERVED`), coverage row "DEC-0003, DEC-0004 through recovery" |
| P-02 row 3 stricter than `update-ref` needs | research R5 row 3 (`L == old_head` and `diff-index --cached --quiet new_head` only; `status` refresh, `diff-files`, untracked and `P` conditions dropped) and the row-3 note; quickstart 18 (edit and untracked file before the rerun) |
| P-03 crash during `read-tree`, stale `index.lock` | research R4 step 3 (`index.lock` → `in-progress`), R5 row 3b (hash test against `new_head`, minimal action: block `dirty` with `git restore --source={new_head} --staged --worktree .`, converges on row 3) and its note, "A block after a successful push", R14 (crash seam); data model `in-progress` and `dirty` rows, transitions; contract `in-progress` and row-3b `dirty` rows, checkout commands (`hash-object --no-filters`, no `-w`), guarantee 8; quickstart 46 |
| P-04 failed-CAS restore targets `OLD` | research R5 step 4 (`read-tree -m -u NEW HEAD` under the same guards); data model `busy` row, transitions; plan review notes; quickstart 40 (first variant wording, third variant: bare commit of the staged tree) |
| P-05 row 1 skips the recheck | research R5 note under the table (the launcher's `_refusal` covers it); contract guarantee 7; quickstart 47 |
| P-06 post-push `dirty` variants | research R5 "A block after a successful push"; data model `dirty` row; contract post-push `dirty` row for ignored and untracked files |
| DEC-0007 option B partial clones refused | research R3a (one rule: `extensions.partialClone`, `remote.*.promisor` or `remote.*.partialclonefilter` → `git-unavailable` "partial clone", recovery "clone the repository again without --filter, then rerun"; `GIT_NO_LAZY_FETCH=1` kept; "Later extension" note with the 2.46 floor, blob check and test needs), R4 step 2, R5 step 1 (blob check removed), R14 (no 2.46 seam); data model `git-unavailable` row, transitions; contract `git-unavailable` row, checkout `config` keys, throwaway commands (`cat-file --batch-check` removed); plan § Technical Context (floor stays 2.41), ADR-0005; quickstart prerequisites, 41 (refused, three configuration variants), documentation check |
| Review 3 note on DEC-0006 | research R12 (an unpinned `resume`/`continue` blocks before the recovery table, so it never completes or clears another run's record) |
