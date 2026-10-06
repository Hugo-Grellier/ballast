# Test review: Chat mode (#20)

- Review: tests
- Reviewer: claude (model), fresh context, same provider. Codex was unavailable (usage limit).
- Scope: the committed tests at `HEAD` (6591e1a) against base 52031c1: `tests/test_chat_mode.py` (new, `ChatCase` harness with fake `systemd-run`, `systemctl`, `bwrap`, `git`, `gh` and `tests/fixtures/chat/fake_tui.py`), plus the new tests in `tests/test_autonomy.py`, `tests/test_spec_workflow.py`, `tests/test_agent_run_ledger.py`, `tests/test_branch_sync.py`, `tests/test_draft_pr.py`, `tests/test_governance.py` and `tests/test_setup.py`. I checked them against `specs/20-chat-mode/spec.md` (AC-001 to AC-022, SC-002, SC-004, SC-005, SC-007, edge cases), the test-task assertions in `tasks.md` (T007 to T061) and `docs/policies/testing.md` with `docs/policies/project/testing.md`. I did not run the suite. Out of scope: three tests fixed after the commit (the two real-bwrap tests and `test_single_provider_review_is_not_cross_provider`, plus the `FAKE_TUI_REPORT` and PATH-filter harness change). Line numbers refer to `HEAD`.

## Criterion-to-test map

| Criterion | Tests (path:line at HEAD) | Coverage |
| --- | --- | --- |
| AC-001 | `tests/test_chat_mode.py:844` (start records, pins, archives, runs no agent), `:938` (four launcher conditions, same error text and exit code as a headless start), `:965` (blocked sync), `:892`, `:901`, `:910`, `:923` | Covered |
| AC-002 | `:612`, `:649`, `:729` (phase graph, cumulative checks, `allowed_actions` order), `:982` (refused step named and recorded, no agent), `:1572` | Covered |
| AC-003 | `:1017`, `:1071` (interactive argv is the contract), `:1086`, `:1115` (`FORBIDDEN` refusal), `:1106` (chat settings are a superset), `:1163`, `:1190`, `:1207` (own pty, terminal restored, no TTY refused); `tests/test_autonomy.py:1064`, `:1097` (`--new-session`, `readonly_extra`); real denial only in `:1123` (skipped without bwrap) | Argv shape is covered in CI. Actual denial is covered only by a test that is skipped in CI (TST-004). |
| AC-004 | `:1221`, `:1273`, `:1290`, `:1300`, `:1318`, `:1330`, `:1340`, `:700` | Covered |
| AC-005 | `:1481` (golden summary), `:1485`, `:1507` | Covered |
| AC-006 | `:1518` (out-of-step event, stale HD, new sync before the agent), `:1540`, `:1551`, `:563` | Covered |
| AC-007 | `:1611`, `:1635`, `:1656`, `:1666` | Covered |
| AC-008 | `:1686` (forgery subtests), `:1745` (real bwrap, skipped in CI), `:1792` (broken chain); `tests/test_spec_workflow.py:3314`, `:3354` | Partly covered (TST-001, TST-002) |
| AC-009 | `:1827`, `:1848`, `:1879`, `:1886`; `tests/test_spec_workflow.py:3314` | Covered |
| AC-010 | `:1903` (four conditions refuse `step`), `:1952` (blocked sync), `:1938`, `:1928` | Covered for `step` (see TST-005 for the other return paths) |
| AC-011 | `:1971` (output identical after logs are deleted) | Covered |
| AC-012 | `:2003` (SIGHUP), `:2035` (late close after `discard-runs`, F-003/F-004 fields), `:2061` | Covered against fakes only (TST-004) |
| AC-013 | `:2077` (`step`, `resume`, `continue`, `mode` refused, naming run and step), `:2113`, `:584`; `tests/test_spec_workflow.py:1241` | Covered. The specified barrier race is approximated (TST-009). |
| AC-014 | `:2160`, `:2252`, `:2264`; `tests/test_agent_run_ledger.py:2743` | Covered (SC-003 is weak, TST-007) |
| AC-015 | `:2193`, `:2213`, `:2228` | Covered (TST-008) |
| AC-016 | `:2344`, `:2357`, `:2419`, `:2451`, `:2461`; `tests/test_draft_pr.py:527`, `:535` | Covered (TST-010) |
| AC-017 | `:2357` (secret in `stdout.log`, absent from the body, the commit, tracked files and the ledger; no `.specify/workflow-state` link), `:1221` | Covered |
| AC-018 | `:2477` (byte-prefix unchanged, `switch` entry, `mode-change` HD, ledger `mode-changed`); `tests/test_autonomy.py:1189`, `:1213` | Covered |
| AC-019 | `:2477` (tasks still refused on `plan` after each switch), `:700` | Covered for chat⇄human-gated (TST-003) |
| AC-020 | `:2477` (decisions check stays unresolved), `:2591` (PD stays provisional) | Partly covered (TST-003) |
| AC-021 | `:2477`, `:2629`; `tests/test_autonomy.py:1189`, `:1236` | Covered |
| AC-022 | `:2591`, `:2621`, `:2629` | Covered (TST-011) |
| SC-002 | Start: `:938` + `:965`. Step: `:1903` + `:1952`. Resume: `resume RUN` is always refused (`:1928`). A return goes through `step` (as above). | Covered for start and step. `continue --mode chat` and the linked `mode` entry are not tested under sync failure (TST-005). |
| SC-004 | Approve a gate: `:1686` "approval block", "launcher approve". Record a passing check: "claims". Resolution: "resolution". Change the mode: only `mode_history` unchanged plus the real-bwrap `try_write` at `:1745`. Open a refused step: no attempt. | Partly covered (TST-001, TST-002) |
| SC-005 | chat→human-gated and human-gated→chat: `:2477`. Autonomous→chat (lower): `:2591` (PD only). Engine→chat (linked): `:2524` (approvals only). | Partly covered (TST-003) |
| SC-007 | `git diff 52031c1 HEAD -- tests/ \| grep -c '^-[^-]'` returns 0. The existing test files only gain new classes and methods. | Covered |
| Edge: protected input edited between steps | `:1540` (`ballast.toml`), `:1903` (`.ballast/spec_workflow`) | Covered. `.specify/` and `.venv/` use the same `launcher.BASES` path and are not tested on their own (low, no action). |
| Edge: base branch advances | `:1938`, `:1952` | Covered |
| Edge: step not allowed yet | `:982`, `:1572` | Covered |
| Edge: re-run of an earlier step | `:1551` | Covered |
| Edge: permission not allowed | `:1017` (argv and settings), `:1123` (real bwrap, skipped in CI) | Argv only in CI (TST-004) |
| Edge: integration cannot run confined | `:901`, `:910` (start only) | Covered at start. Not tested at step time (TST-012). |
| Edge: secret in the conversation | `:2357` | Covered |
| Edge: operator ends a step while the agent writes | `:1340` | Covered |
| Edge: no reviewer from another provider | `:910`, `:2228` | Covered for the record and the event. Not covered for the summary (TST-008). |

## Findings

### TST-001: medium. Forgery subtests can pass without the forged step having run

- Location: `tests/test_chat_mode.py:1686-1742` (`test_each_forgery_attempt_changes_nothing`).
- Missing evidence: T040 needs every attempt to happen and then change nothing. The test never checks the `plan` step's exit code. For the "approval block", "claims" and "resolution" attempts, it also never checks that the fake agent ran (`self.agent_ran()`) or that the forged text reached the file. All four attempts share one run, with the checkout restored by hand between subtests. If an earlier attempt leaves state that refuses the next `plan` step (`in-progress` marker, `BALLAST_TAMPERED`, an entry refusal), every later assertion holds without the forgery being tried. The test cannot fail in that case. T040 also asks for "one test per attempt" with `allowed_actions` equal to its value before the step. The test checks a subset relation instead. The comment justifies that, but it is weaker than the task.
- Required action: in each subtest, assert `self.agent_ran()`, assert that the forged content is present after the step (for example the forged block in `intent.md`), and assert that no `in-progress` marker or `BALLAST_TAMPERED` remains. Alternatively, give each attempt its own run or test method.

### TST-002: medium. SC-004 attempts "change the mode" and "open a refused step" have no CI test

- Location: `tests/test_chat_mode.py:1701-1711` (attempt list), `:1745` (real-bwrap only).
- Missing evidence: SC-004 says each attempt is covered by a test. The only agent-side attempt through the launcher is `ballast run approve`. No attempt has the agent run `ballast run mode RUN human-gated` or `ballast run step RUN tasks` from inside the step. Under the fake bwrap, no attempt writes `run.json` or `human-decisions.jsonl` and then asserts the "after each" invariants. The real-bwrap variant (`:1745`) is skipped in CI, runs in a `specify` step rather than a `plan` step, and only checks that the write failed. It does not check `mode_history`, approvals or `tasks` afterwards. `:1792` covers a forged chain line, but the test writes it, not an agent.
- Required action: add `run` attempts for `ballast run mode RUN human-gated --reason x` and `ballast run step RUN tasks` to the `attempts` map, asserting the refusal text and an unchanged `mode_history` and entry state. In the real-bwrap test, also assert the "after each" invariants.

### TST-003: medium. SC-005 is not proven for the `lower` (Autonomous→Chat) and linked (engine→Chat) switches

- Location: `tests/test_chat_mode.py:2524`, `:2591`; `:2477` covers only chat⇄human-gated.
- Missing evidence: SC-005 needs tests for each allowed switch showing that failed checks still block and unapproved decisions stay unapproved. The continuation test checks only that PDs stay provisional. It has no failed check or open `DEC` in the source run that it then asserts still blocks in the Chat run. The linked-run test checks intent carry-over and that `plan` is re-asked. It checks no failed check, no open decision, and no re-asked `tasks` approval (which T060 requires). AC-020 also has no test for a resolution through `resolve` after a switch. The test checks only the decisions check, not the `converge` entry or a later clearing.
- Required action: give the Autonomous source and the paused engine run an invalid `plan.md` and an open `DEC-0001` proposal. After continuation or linking, assert that `tasks` is refused on `plan` and that the decisions check is unresolved until `resolve`. Assert that `tasks` approval is `pending` in the linked run.

### TST-004: medium. The real confinement and process seams are fakes in CI

- Location: `FAKE_BWRAP` and `FAKE_SYSTEMCTL` in `tests/test_chat_mode.py:96-121`; `:1123` and `:1745` (`skipUnless(_bwrap_works())`); `.github/workflows/ci.yml` installs no bwrap; `docs/policies/project/testing.md:4` still says "Four tests skip in CI".
- Missing evidence: in CI, AC-003, FR-005 and the "permission not allowed" edge case rest on argv and settings equality. Under the pass-through bwrap the agent can write `ballast.toml` (`:1318` relies on this). FR-009 and AC-012 rest on a `systemctl is-active` stub that reports `inactive` whatever the real process state. `:2035` runs `discard-runs` successfully while the fake agent PID is still alive, which a real scope would refuse. No test, even a skipped one, runs an interactive step under a real `systemd-run --user --scope` and confirms its stop. These are R2 boundaries.
- Required action: add a `skipUnless` real-systemd test that runs one interactive step with the fake TUI under real `systemd-run` and `bwrap` and checks scope stop and confirmation. Record in T074 that the real-bwrap and real-systemd Chat tests ran, not skipped. Update the CI-skip count in `docs/policies/project/testing.md` (and `CLAUDE.md`, which repeats it) to name the new skipped tests.

### TST-005: low. SC-002 "resume" covers `step` but not the other return entry points

- Location: `tests/test_chat_mode.py:1903`, `:1952`, `:2077`.
- Missing evidence: `continue --mode chat` and `mode` on a paused engine run both run branch synchronization (`chat.continue_run`, the linked path in `chat.change_mode`). No test shows a blocked synchronization on those entries starting no agent and leaving a correct record and refusal. The four launcher conditions are shared code and only the `in-progress` case is exercised for them (`:2077`), which is acceptable.
- Required action: add one dirty-tree case each for `continue --mode chat` and the linked `mode`, asserting `BLOCKED_UPSTREAM_SYNC`, a `sync` event with `blocked`, no step entries and no agent report.

### TST-006: low. "Before any agent" omits the `in-progress` check on the step-refusal paths

- Location: `tests/test_chat_mode.py:1903-1926`, `:1952-1965`.
- Missing evidence: the Conventions define "before any agent" as no fake report, no `start` entry and no `in-progress` marker. The tests check the first two. For every condition except `in-progress` itself, they do not check that the marker is absent after the refusal.
- Required action: assert that the marker is absent after each non-`in-progress` refusal.

### TST-007: low. SC-003 compares against a hard-coded set, not a human-gated run

- Location: `tests/test_chat_mode.py:2177-2179`.
- Missing evidence: T052 asks for the event kinds and identity fields to equal those of a human-gated fixture run. The test compares against a literal set, so a change in what human-gated runs record would not be caught.
- Required action: build the comparison set from a human-gated fixture's ledger, as the existing ledger tests do, or document why the literal set is authoritative.

### TST-008: low. Review report rules do not isolate the "missing" case, and the summary's cross-provider statement is untested

- Location: `tests/test_chat_mode.py:2213-2226`, `:2228`.
- Missing evidence: the "outside reviews" subtest writes the report, so the following "missing" subtest runs with the report already present. "Missing" is then the same as "unchanged", and removing the missing-report rule would not fail the test. No subtest checks why the step failed. T053 also requires the summary to state `cross_provider`, which `:2228` does not check.
- Required action: delete the report before "missing" (or reorder the subtests). Assert the failing check name in each subtest. Assert the cross-provider line in `chat.summary`.

### TST-009: low. The concurrency race is approximated

- Location: `tests/test_chat_mode.py:2113`.
- Missing evidence: T048 specifies two `step` invocations started together, with a barrier seam after the lock is taken. The test takes the lock itself and runs one invocation. `reject`, `resolve` and `publish` while a step is active are not tested (T051, T055).
- Required action: add the two-process race, or record the approximation. Add active-step refusal cases for `reject`, `resolve` and `publish`.

### TST-010: low. Publication omits some task-listed assertions

- Location: `tests/test_chat_mode.py:2357`.
- Missing evidence: T055 lists a commit with hooks and filters disabled and protected paths refused, a push without force from a throwaway repository, and a golden section text. The test checks the skeleton lines, the approval rows and the pushed SHA only. The shared `autonomy.publish` path may already cover the rest in the Autonomous publisher tests, but the Chat test does not show it.
- Required action: point to the Autonomous publisher tests that cover these behaviors (in the PR evidence), or assert them for the Chat caller.

### TST-011: low. `changes-requested` continuation and the source refusals are thin

- Location: `tests/test_chat_mode.py:2621`.
- Missing evidence: T061 says `--reason changes-requested` "behaves the same" and that `--mode chat` "applies the same source refusals as today". The test checks only the decision kind and that one Chat run was created. It does not check the lower entry, `continued` status, the PD listing, or a refused source (for example an active Autonomous run).
- Required action: assert the same fields as `:2591`, and add one refused-source case with `--mode chat`.

### TST-012: low. An integration that cannot run confined is not tested at step time

- Location: `tests/test_chat_mode.py:901`, `:910`.
- Missing evidence: the edge case says the start or the step is refused. Only `start` is tested. A step whose self-test or Codex nesting probe fails after start is not.
- Required action: break the fake bwrap after start and assert that `step` is refused with the reason, before any agent runs.

## Notes

- SC-007 holds: no existing test line was removed or changed. T072's evidence matches.
- The harness drives the real launcher and `run.py` in subprocesses on real ptys, and the "before any agent" signal (the fake TUI report) is reset per step. This is the right seam for most criteria. The in-process `approve_in_process` and `call` helpers skip the launcher for setup only; launcher-level approval is proven separately at `:1611` and `:1635`.

## Resolution

Checked against commit 110d8c8 with `git diff f7e91fb 110d8c8 -- tests docs AGENTS.md`. Line numbers above refer to the reviewed `HEAD` (6591e1a). I did not run the suite. The real-scope test result comes from the fixing session's report.

| Finding | Status | Evidence | Agree |
| --- | --- | --- | --- |
| TST-001 | fixed | `ForgeryTests.test_each_forgery_attempt_changes_nothing` now asserts, in every subtest, `self.agent_ran()`, that each `write`/`append` payload is in its file after the step, and that neither the `in-progress` marker nor `BALLAST_TAMPERED` remains. A subtest can no longer pass because its step was refused. | Yes. The subset check on opened actions is still weaker than T040's equality, but the comment justifies it (a forged block can only stale intent), and it still fails if anything opens. |
| TST-002 | fixed | New "launcher mode" and "launcher step" attempts: the agent runs `ballast run mode RUN human-gated` and `ballast run step RUN tasks` from inside the `plan` step. Each asserts exit 2, "an agent step is active", `run.mode == "chat"`, plus the shared invariants (no new approval, unchanged `mode_history`, `tasks` still refused). | Yes. Direct writes to operator records stay covered only by the real-bwrap test, which is skipped in CI. That is accepted because bwrap is the boundary being tested. |
| TST-003 | fixed (residual low) | New `ContinueTests.test_lowering_keeps_failures_and_open_decisions`: after `continue --mode chat`, `tasks` is refused on `plan`, the `plan` gate precondition fails, and the summary lists `DEC-0001` as unresolved. The linked-run test now also asserts that the `tasks` approval is `pending`. | Yes. The engine→Chat linked run still has no failed-check or open-decision case. Its entry checks go through the same `chat.entry` and `_check` path proven for the lowered and switched runs, so I accept that as residual. |
| TST-004 | fixed (follow-up for evidence) | New `StepCloseTests.test_real_scope_and_bwrap_step_is_confirmed_stopped`, skipped unless bwrap and a systemd user manager are present. It runs a step under real `systemd-run` and `bwrap`, ends it with the escape, and asserts `interrupted`, `scope_stopped: true`, a non-active unit and no marker. `docs/policies/project/testing.md` and `AGENTS.md` (which `CLAUDE.md` links to) no longer give a count of skipped tests. The fixing session reports that the test ran and passed on a host with systemd and bwrap. | Yes. Follow-up: record in T074 that this test and the real-bwrap Chat tests ran there, not skipped. |
| TST-005 | partly fixed (low, accepted) | New `ContinueTests.test_blocked_continuation_is_recovered_by_the_next_step` covers a blocked sync on `continue --mode chat` and its recovery through `step`. | Partly. It does not assert that no agent ran or that the record has no step entries, and the linked `mode` entry is still untested. Low; no action required before merge. |
| TST-006 | accepted (low) | Unchanged. | Yes, low. |
| TST-007 | accepted (low) | Unchanged. | Yes, low. |
| TST-008 | accepted (low) | Unchanged. The "missing report" case is still the same as "unchanged". | Yes, low. Worth fixing when the file is next touched. |
| TST-009 | accepted (low) | Unchanged. | Yes, low. |
| TST-010 | accepted (low) | Unchanged. | Yes, low. |
| TST-011 | accepted (low) | Unchanged. | Yes, low. |
| TST-012 | accepted (low) | Unchanged. | Yes, low. |

### Updated feature tests

- `PhaseGraphTests.test_gate_digests_follow_the_binding`: `final` now binds the whole tree (`tree_digest(root, ())`) per DEC-0002, which has a recorded resolution in `decisions.md`. The test now also asserts that changing a review leaves the `implementation` digest unchanged and changes the `final` digest. This is stronger than before and still proves the gate-digest binding.
- `ProjectChecksTests.test_final_needs_checks_for_the_current_tree`: one line was added. It re-approves `implementation` after the source edit, because DEC-0002 requires every earlier approval to be current. Every original assertion is kept: refused without checks, refused after an edit, approved after fresh checks, and back to `active` after a later edit. Not weakened.
- `StartTests.test_blocked_synchronization_leaves_a_record_without_steps`: the ledger assertion is inverted to require the `run` event (ENG-004). T024 says nothing about the ledger for a blocked start. The record-without-steps, `sync` event and no-agent assertions are unchanged. This is a behavior change made by the engineering fix, not a weakening.
- SC-007 still holds: `git diff 52031c1 110d8c8 -- tests/ | grep -c '^-[^-]'` prints 0. The three edits above change tests added by this feature, not tests that existed before it.

No medium or higher finding remains open. TST-004 has a follow-up for evidence (T074). The low findings are accepted.

- Verdict: approved
