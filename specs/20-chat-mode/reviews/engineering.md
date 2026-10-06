# Review: engineering and architecture

- Reviewer: claude (model), fresh context, same provider as the author — Codex unavailable (usage limit)
- Scope: feature #20 Chat mode, branch `feat/20-chat-mode`, committed code at `HEAD` (`6591e1a`) against base `52031c1`. Code: `tools/spec_workflow/chat.py` (new), `run.py`, `agent.py`, `autonomy.py`, `artifacts.py`, `branch_sync.py`, `draft_pr.py`, `ledger.py`, `launcher.py`. Architecture: ADR-0009 against ADR-0003, ADR-0004, ADR-0005 and `specs/TECHNICAL-SPEC.md` §91. Formatting is left to the linters.
- Review kind: `review: engineering`

## What was examined

- Intent and requirements: `specs/20-chat-mode/spec.md` (FR-001 to FR-023, AC-001 to AC-022, SC-001 to SC-007), `plan.md` (D-1 to D-7, Complexity Tracking), `data-model.md`, `research.md` (R14), every `contracts/*.md`, `tasks.md`, including the conventions (reuse list) and the implementation clarifications at the end.
- Policy: `CLAUDE.md` (invariants, R2 rules). `docs/policies/engineering.md` is not in `HEAD`; it is an installed, git-ignored policy, so the review used the skill's checklist and `CLAUDE.md`.
- ADRs: 0003, 0004, 0005 and the new 0009, and the §91 status line of `specs/TECHNICAL-SPEC.md`.
- Code: all of `chat.py`; the full `git diff 52031c1 HEAD -- tools/`; and the unchanged code that Chat calls: `agent.main`/`_autonomous_run`/`_log_dir`, `artifacts.check_intent`/`check_plan`/`check_convergence`/`_approval_path`, `autonomy.publish`, `branch_sync._Sync.intended_branch`/`save_pin` (N-07), `ledger._semantic_problems`/`append`, `run.py` `main`/`_continue_command`.
- Tests: searched `tests/test_chat_mode.py` (93 tests) for the paths the findings name. No test was executed. Another agent is reformatting the working tree, so every finding comes from reading the committed code.

## Findings

### ENG-001 — high — a blocked `continue --mode chat` leaves the run with no way to continue

- Location: `tools/spec_workflow/run.py:1011` (`_continue_chat`), `tools/spec_workflow/chat.py:2456-2491` (`continue_run`), `tools/spec_workflow/branch_sync.py:846-849` and `:1914` (N-07), `tools/spec_workflow/chat.py:1604` (step sync passes no `source_run`).
- Invariant or requirement: FR-021, AC-022, partial-failure consistency. ADR-0005 requires that a continuation inherit its source's pin.
- Evidence (facts):
  - `_continue_chat` changes the source run before it synchronizes. It appends the HD, lowers the source to `chat`, sets it to `continued`, writes it and re-renders `record.md`. Only then does `chat.continue_run` create the linked run and call `synchronize(..., source_run=...)`.
  - A blocked continuation saves no pin for the new run (N-07: `save_pin` waits for `final=True`).
  - Every later `ballast run step NEW PHASE` calls `synchronize(run, rerun=...)` without `source_run`. `intended_branch` then reads an empty pin and stops as `wrong-branch` "has no branch or feature pin". This happens every time, while the recovery line tells the operator to rerun that same `step`.
  - The source is now `continued`, so `_continue_refusal` refuses a second `continue`. The `ballast-chat` record cannot be `resume`d.
  - The headless path (`run.py:948`) is ordered the other way: it synchronizes first and records nothing when blocked.
  - The contract (`contracts/cli.md` § `continue --mode chat`, steps 1–5) prescribes the failing order, so this is also a contract defect.
  - No test covers a blocked `continue --mode chat`.
- Required action: synchronize before recording the HD and lowering the source, as the human-gated continuation does. Alternatively, make a blocked Chat continuation recoverable, for example by having `step` pass `source_run` from `record["continues"]` until the pin exists. Fix the contract order and add a test: a blocked continuation, then a clean retry, keeps the provisional decisions carried.

### ENG-002 — medium — the final approval excludes `reviews/`, so review evidence can change after final approval and still be published

- Location: `chat.py:400-406` (`Run.tree` excludes `specs/<f>/reviews`), `chat.py:643-644` (`final` digest), `chat.py:2652-2665` (`publish` checks only that `final` is current and the project checks), `chat.py:193-199` and `:1419-1420` (a `spec-reconciliation` review step writes `reviews/convergence.md` and stays in scope).
- Invariant or requirement: FR-016 ("after final acceptance is approved"), FR-015, AC-007 (an approval is bound to the exact artifact version), BL-INV-005.
- Evidence (facts): after `approve final`, the operator can run `step review --kind spec-reconciliation`. Its entry needs only `decisions` and `tasks-done`. The agent rewrites `convergence.md` with `- Verdict: FAILED`. That makes the `spec-reconciliation` approval stale, but `final` stays current because its tree digest leaves out `reviews/`. `_reactivate` therefore does not fire, and `publish` succeeds. The PR then carries a FAILED convergence report under a header saying every gate was approved. Other review reports can change in the same way after final approval.
- Required action: either bind the `final` digest to the tree including `reviews/`, or re-evaluate and record the `final` precondition (convergence and a current `spec-reconciliation` approval) inside `publish`. Add a test for "a review changed after final approval".

### ENG-003 — medium — upstream approvals are not cumulative, and the PR shows stale approvals as plain approvals

- Location: `chat.py:122-127` (`implement` entry), `chat.py:255-273` (`final` precondition), `chat.py:2533-2534` (section header), `chat.py:2571-2581` (approvals table), `ledger.py:2376` (`stale_gates`).
- Invariant or requirement: AC-006 and the edge case "re-runs an earlier step" (approvals become stale), FR-013, SC-003, single source of truth for compliance.
- Evidence (facts):
  - After `approve tasks`, re-running `step plan` (whose entry needs only intent) changes `plan.md` and makes the plan approval stale.
  - `implement` still opens (tasks check, tasks approval, baseline), and neither `implementation`, `final` nor `publish` requires a current plan approval.
  - The PR "Human approvals" table renders every `gate-approval` HD with the same fixed operator-approval wording, without saying whether it is current. The fixed header claims every listed gate was approved, even when rows are rejections.
  - The ledger projection (`_chat_report`) marks such a gate as stale and the run `incomplete_or_noncompliant`, while the run record lets it publish. Two projections of the same record disagree on compliance.
  - The phase-graph contract specifies these entries, so this is a spec ambiguity rather than a deviation from the contract.
- Required action:
  - Decide in `decisions.md` whether a stale upstream approval blocks downstream phases, `final` and `publish`. The recommendation is that `final` requires every gate approval to be current.
  - Render each approval's currency (current, stale or superseded) in the PR table and the summary, and word the header so it is true when rows are rejections.
  - Align the ledger report rule with the runner's rule.

### ENG-004 — medium — a run whose start was blocked can still take steps, and its ledger then becomes permanently invalid

- Location: `chat.py:1256-1262` (`start` returns before the ledger `run` event when synchronization is blocked), `chat.py:2483-2485` (the same in `continue_run`), `chat.py:933-941` (`_ledger` reports failures only), `ledger.py:693` and `:766`.
- Invariant or requirement: FR-013, AC-014 (every step recorded with the same identity), SC-003. The ledger is the audit projection.
- Evidence (facts):
  - After a blocked `start --mode chat`, the run record stays `active` and, for a starting sync, the pin is usually saved already.
  - Nothing refuses `approve RUN scope` or `step RUN specify` on that run. `_scope_check` passes with or without a pin.
  - The first `step` appends a ledger `step started` with no earlier `run started`.
  - From then on `_semantic_problems` reports "step outside active run", and every later `ledger.append` for the run fails "invalid existing ledger". `_ledger` only prints this to stderr, so the run proceeds with no ledger evidence.
  - Uncertainty: this was traced through the code, not executed.
- Required action: write the `run started` ledger event before synchronization, or refuse `step` and `approve` on a Chat run whose start or continuation never recorded it. Mark such a run so the summary says to start again. Add a test.

### ENG-005 — medium — `_publish_chat` copies the Autonomous publisher instead of reusing it

- Location: `autonomy.py:2632-2744` (`_publish_chat`) against `autonomy.py:2487-2630` (`publish`); `chat.py:2497-2498` and `autonomy.py:2747-2748` (`CHAT_BEGIN`/`CHAT_END` defined twice).
- Invariant or requirement: the conventions in `tasks.md` ("reuses, and does not copy … `publish`"), plan D-6 and R14 ("reuses the Autonomous publisher"), no duplicated responsibility on an R2 boundary.
- Evidence (facts):
  - About 90 lines are copied: repository and branch checks, origin, `gh pr list`, adoption, `program_findings`, `git add --all`, the staged-path refusal, commit, push, and adopt-or-create.
  - The copies have already diverged. Chat drops the Git configuration snapshot check and the allowed-paths check that the Autonomous path has, and adds a pin check that the Autonomous path lacks.
  - A future hardening of one publisher will silently miss the other.
- Required action: extract the shared commit, push and Draft PR sequence into one helper with the mode-specific body, its guard and its preconditions as parameters, and define the Chat markers once. Write down why the configuration snapshot and allowed-paths checks do not apply to Chat, or apply them.

### ENG-006 — low — the run record is read before the lock is taken

- Location: `chat.py:1594-1595`, and the same pattern in `_gate_decision` (`:2156-2157`), `resolve`, `checks`, `publish` and `status`.
- Invariant or requirement: concurrency (R8). The operator run record is the source of truth.
- Evidence (facts): `load()` reads `run.json`, and only then does `Lock.__enter__` take the non-blocking `flock`. If another invocation finishes entirely between the two, this invocation works on the old record. Its next `run.save()` then overwrites the other's change, for example the `baseline` written by `approve tasks`. The window is very small, because the lock is non-blocking and every other overlap is refused.
- Required action: re-read `run.json` after the lock is taken.

### ENG-007 — low — a headless (human-gated) Chat step records a log path that holds no logs

- Location: `chat.py:1649-1650` (creates `agents/<name>/`), `chat.py:1473` (records it as `log`), `agent.py:166` (`_log_dir` writes to its own `<stamp>-<command>-<integration>` directory).
- Invariant or requirement: FR-013 and FR-017 (the step's log lives in local run state and is referenced by the record).
- Evidence (facts): in `human-gated` mode, `agent.py` writes `stdout.log`, `stderr.log` and `meta.json` under a different directory name. The close entry points to an empty directory.
- Required action: record the directory `agent.py` actually used (for example by passing the step name through, or by finding it after the step), or do not create the empty directory and record `log: null` for headless steps.

### ENG-008 — low — cross-provider is computed two ways

- Location: `chat.py:1507-1521` (the run record uses the integration of every author step), `chat.py:1528-1540` (the ledger gets `author_provider = run.record["integration"]`), `ledger.py` `_chat_report` (recomputes from those).
- Invariant or requirement: FR-014, a single source of truth (projections must agree).
- Evidence (facts): when an author step overrides `-i integration`, the run-record `review` event and the ledger report can give opposite `cross_provider` answers for the same review.
- Required action: put the run record's `cross_provider` value into the ledger event and report it as recorded.

### ENG-009 — low — dead code and repeated helpers in `chat.py`

- Location: `chat.py:71` (`ESCAPE`), `:201` (`VERDICTS`), `:275` (`OUTCOMES`), `:785` (`evaluate`, used only by a test); the "record one `check` event" block repeated in `evaluate`, `_requirement` (`:839`), `_postconditions` (`:1366`, `:1379`, `:1398`) and `_requirement_event` (`:2234`); the operator record archived twice per invocation (`chat.archive` `:1035` and `run.py:375` `_archive_operator`, both to `operator/`).
- Invariant or requirement: no unnecessary complexity or duplicated responsibility.
- Evidence (facts): grep finds no non-test caller of these constants or of `evaluate`. Every Chat command runs both archive copies.
- Required action: remove the unused names, route check recording through one helper, and keep one archive call.

### ENG-010 — low — changes from branch synchronization are not attributed

- Location: `chat.py:1597` (`out_of_step` before synchronization), `:1604` (synchronization), `:1655-1656` (`last_manifest` overwritten with the post-sync tree).
- Invariant or requirement: FR-011 (changes between steps are recorded with the approvals they make stale).
- Evidence (facts): files a base merge brings in during `step` appear neither as an out-of-step change nor as step changes. Tree-bound approvals (`implementation`, `final`) become stale with no recorded cause, and the summary says only "the artifact changed since".
- Required action: after a synchronization that changed `HEAD`, record an `out-of-step-change` (actor `sync`, with the ledger pointer) before taking `tree_before`.

### ENG-011 — low — ADR-0009 does not name every decision it amends

- Location: `docs/adr/0009-chat-mode-operator-driven-steps.md` ("Extends" line); `chat.py:2440-2443` (`mode` on an engine run writes the pin through private `branch_sync._write_json`/`_pin_path`).
- Invariant or requirement: architecture authority (accepted ADRs govern; a change needs an explicit record).
- Evidence (facts):
  - ADR-0004 says a continuation "lowers the run to human-gated", "recovery is always human-gated until #18" and that bwrap is a prerequisite "for Autonomous only". ADR-0009 changes all three: lowering to `chat`, a Chat continuation, and bwrap for Chat. Yet it says it extends ADR-0004 only for the publisher.
  - ADR-0005 says "only `ballast run start` pins a run's branch". The `mode` link copies a pin outside `branch_sync`'s write path.
- Required action: list these amendments in ADR-0009 (Context and Consequences), and give `branch_sync` a public "inherit pin" entry point instead of the private calls.

### ENG-012 — low — a checks run that tampered with protected inputs still counts

- Location: `chat.py:2307-2345` (`checks` records the `project-checks` event with its results before the tamper return), `chat.py:751-765` (`_checks_result`).
- Invariant or requirement: BL-INV-005. A check that changed protected inputs proves nothing.
- Evidence (facts): when a check command changes a protected input and exits 0, the event is recorded as passing for the tree. After the operator restores the files and deletes the tamper marker, the tree can match again, and that result satisfies `final`'s checks requirement.
- Required action: record `protected_changes` on the event and treat a non-empty value as failed in `_checks_result`.

### ENG-013 — low — a launch error is recorded as an interrupted step

- Location: `chat.py:1743-1746` (an `OSError`, `ValueError` or `AutonomyError` from `run_interactive` is caught), `chat.py:1894` (outcome `interrupted`, exit 130).
- Invariant or requirement: FR-013 (accurate step outcomes), the CLI exit-code contract.
- Evidence (facts): a step whose agent never started, for example because `bwrap` failed after the self-test or the argv was refused, is recorded as `interrupted` and exits 130, as if the operator had pressed Ctrl-C.
- Required action: record such a launch failure as `failed` with the error, and exit 1 or 2.

## Sound

- **SC-007, the existing paths are unchanged in behavior** (facts, from the diff):
  - `autonomy.publish` gained only an early `workflow == ballast-chat` branch. `_adopt_pr`'s `merge` defaults to `_with_summary`, and the Autonomous body and its `HUMAN_APPROVAL` guard are untouched.
  - `confined_argv` emits byte-identical argv when `interactive_pty=False` and `readonly_extra=()`.
  - `_archive_operator` keeps `autonomous/` for every workflow except `ballast-chat`, and keeps the old behavior when the record is unreadable.
  - `artifacts.check_intent` is unchanged. A Chat `Feature` sets `run_id` but never `run`, so the registered-block branch applies. `check_decisions` adds a separate `feature.chat` branch.
  - The `run_checks` refactor keeps the frozen-tree check, the deadline and the `limit` block, and only moves the loop into `run_commands`.
  - `draft_pr._run_feature` changes behavior only when `inputs.json` is missing, which was a crash before.
  - The ledger changes are additive: an optional `mode`, `mode-changed` that requires `action: ended`, and a Chat-only report branch selected by `mode: chat` on the first `run` event.
  - `change_mode` now validates before it appends, and the lowering rules for Autonomous are unchanged.
  - The human-gated `continue` only moved the `specify` lookup after argument checks, still before any write.
- **Source authority**: approvals, resolutions, mode changes, steps and checks live only in the operator record, with hash-chained HD and E logs. The handoff summary and the PR section are rendered from that record and never from conversation logs (FR-019, FR-017). The ledger is written only as a best-effort projection.
- **Agent authority**: an interactive step runs `dontAsk` or `-a never` under bwrap with operator state hidden and `.claude/` and `.codex/` read-only. Gates need a TTY, a typed confirmation, no active step and a digest re-check after confirmation, and the launcher refuses every command while `in-progress` exists. A `FORBIDDEN` marker is refused in the prompt and the model. Settings for an interactive step are written before the protected snapshot, and the deny list is a superset of the installed headless one.
- **Crash consistency of a step**: the order is `active_step`, then the `start` entry, then the marker. An unconfirmed scope keeps the marker and exits 4. A late close writes `attribution: uncertain` and `protected_compared: false`. A close entry written without the `active_step` clear is detected by `_closed`. A failed postcondition stays in `events.jsonl` and blocks because checks are evaluated again; nothing stores a "blocked" flag (FR-010, AC-019).
- **Mode rules**: `switch` is allowed only for `ballast-chat` between `chat` and `human-gated`, `lower` only from `autonomous`, and every move to `autonomous` is refused (FR-020, AC-021). A Chat run never writes a provisional decision, and carried PDs keep their provisional label with their superseding HD (BL-INV-006, AC-022).
- **ADR-0009 against ADR-0003 and ADR-0005**: the Chat publisher runs behind the launcher in `run.py`'s process with the operator's `gh`, which is ADR-0003's boundary. Every `step` synchronizes once before its one agent step, which extends ADR-0005's list but not its rule. No new ADR beyond 0009 is needed. ENG-011 asks it to name the ADR-0004 and ADR-0005 amendments.
- **Scope**: every new subcommand, input and field traces to the contracts or the documented implementation clarifications. No silent scope expansion was found.

## Resolution

- Verified against commit `110d8c8`, diff `f7e91fb..110d8c8` (code, contracts, `decisions.md`, ADR-0009, tests). The new and changed tests were read, not executed.
- Status values: **fixed** (the change closes the finding), **accepted** (left as is, no action needed), **follow-up** (left open as a non-blocking issue to file).

| ID | Status | Evidence | Closes the finding? |
| --- | --- | --- | --- |
| ENG-001 | fixed | `chat._inherited_pin` returns the source's branch, base and `source_run` when a continuation has no pin of its own. `continue_run` and `run_step` both synchronize with it, so a later `step` goes through the continuation path and saves the pin on success (`save_pin(final=True)`). A run linked with `mode` already has a copied pin and gets `{}`. `contracts/cli.md` step 5 documents the recovery. Test: `ContinueTests.test_blocked_continuation_is_recovered_by_the_next_step` (blocked, no pin, ledger has `run`, then a step succeeds and pins `27-demo-run`). | Yes. The source still becomes `continued` before synchronization, but the linked run is now recoverable, so this ordering is no longer a dead end. |
| ENG-002 | fixed | DEC-0002. `gate_digest("final")` is now `tree_digest(root, ())`, which includes `reviews/`, and `_gate_paths("final")` matches every path. `publish` re-evaluates and records `gate_precondition(run, "final")`. Test: `PublishTests.test_a_review_changed_after_final_approval_blocks_publish` (FAILED convergence leaves final stale, publish exits 2, no `pr create`). | Yes. |
| ENG-003 | fixed | DEC-0002. `GATES["final"]["pre"]` now also requires the scope, intent, plan, tasks and implementation approvals to be current. The PR approvals rows end with `(current)`, `(stale)` or `(superseded)`. Test: `PublishTests.test_final_needs_every_earlier_approval_current`. | Yes, in substance. A small wording issue remains: the fixed header still says "every gate below was approved", while the table can also list rejections (`chat.py:2895`). This is low and non-blocking; marked follow-up. |
| ENG-004 | fixed | The ledger `run` event is now appended before synchronization in `start` and `continue_run`. `contracts/cli.md` reorders the start steps to match. The ENG-001 test asserts a `run` event exists after a blocked continuation, and the ledger helper asserts no problems. | Yes. |
| ENG-005 | fixed (partly) | `autonomy._publication_target` holds the branch, pin, origin, PR-lookup and adoption checks for both publishers. Its refusals raise `AutonomyError(..., "postcondition")`, which `publish` turns into the same `refuse` result, so the Autonomous output is unchanged. `CHAT_BEGIN` and `CHAT_END` are defined once, in `autonomy`. The `_publish_chat` docstring explains why it has no configuration snapshot or allowed-path list. The staged-path refusal, commit, push and create-or-adopt code are still in both functions. | Yes, for the riskiest shared part, and the remaining differences are now documented. The leftover copying is low; marked follow-up. |
| ENG-006 | fixed | `Lock.__enter__` re-reads `run.json` (`autonomy.read_run`) once it holds the lock. | Yes. Minor: if that read raises, the lock descriptor stays open until the process exits; this is harmless for a one-shot CLI. |
| ENG-007 | follow-up | Unchanged: a headless step's `log` still points to the directory `run_step` created, not the one `agent.py` used. | No. Low and non-blocking. |
| ENG-008 | follow-up | Unchanged: the run record and the ledger still compute `cross_provider` in two ways. | No. Low and non-blocking. |
| ENG-009 | accepted | Unchanged: the dead constants, `evaluate` and the double archive remain. These are cleanup only. | Not applicable. |
| ENG-010 | follow-up | Unchanged: files a synchronization merge brings in are still unattributed. | No. Low and non-blocking. |
| ENG-011 | fixed | ADR-0009 Consequences now list the three ADR-0004 amendments and the ADR-0005 pin-copy amendment. The private `branch_sync` calls in `_link_engine_run` remain. | Yes, for the architecture record. |
| ENG-012 | follow-up | Unchanged: a checks run that tampered still records results that can count. | No. Low and non-blocking. |
| ENG-013 | follow-up | Unchanged: an interactive launch error is still recorded as `interrupted`, exit 130. | No. Low and non-blocking. |

### Regressions checked

- **Autonomous output**: unchanged. The `_publication_target` extraction keeps the Autonomous order (eligibility and risk checks first) and the same refusal texts and categories.
- **Every confined step now binds the skills read-only**: `_installed_skill_binds` is added to `confined_argv` for every caller, Autonomous agent steps and `run-checks` included. This changes Autonomous argv (SC-007 scope). It is a security hardening (SEC-001), is recorded as an ADR-0004 amendment in ADR-0009, and has its own new test without changing existing assertions. It is not a regression.
- **More re-approvals before `final`**: `final` now needs a current `implementation` approval, and `implementation` binds the tree without `reviews/`. So a `reconcile-intent` or `converge` step that changes code after `approve implementation` means the operator must approve implementation again before `final`. This is intended under DEC-0002 (stricter, never weaker), but it adds operator friction worth stating in the workflow policy. It is not a defect.
- **`open-write-scope` (DEC-0003)**: this entry check is new behavior from the security review. It only adds a blocking check (an out-of-scope change blocks later steps until restored or changed) and closes by operator action; no regression found.
- **Unrelated security fixes in the same commit**: `chat_hook.py`, the terminal reset with `TCSAFLUSH`, and `_safe`/`printable` on agent text shown to the operator. They change no engineering behavior covered here and were not reviewed in depth; they belong to the security review.

### Still open (non-blocking)

ENG-003 header wording, ENG-005 remaining duplication, ENG-007, ENG-008, ENG-010, ENG-012 and ENG-013, all low. No critical, high or medium finding remains.

- Verdict: approved
