# Engineering review: Setup trusts a checkout it just installed (#55)

- Review: engineering
- Reviewer: engineering reviewer, independent context
- Scope: `git diff 641fa7f..HEAD` on `feat/55-setup-trust` (commits ee50e93, 5201073, 3d0a087, c659760): `tools/spec_workflow/setup_trust.py` (new), `launcher.py`, `branch_sync.py`, `draft_pr.py`, `tools/setup`, `tools/ballast`, `tools/init`, the tests, ADR-0015, the ADR-0007 and ADR-0011 edits, README, the policy template, the roadmap and technical-spec edits. Judged against `spec.md` (FR-001 to FR-020, AC-001 to AC-027), `plan.md`, `research.md`, `data-model.md`, `contracts/`, `tasks.md`, `decisions.md` (DEC-0001 to DEC-0007) and `reviews/plan.md` (F-001 to F-006).
- Policies read: `AGENTS.md`, `docs/policies/engineering.md`, `.agents/skills/ballast-engineering-review/SKILL.md`. `docs/policies/project/engineering.md` does not exist. ADR-0015, ADR-0007, ADR-0011, ADR-0002 and ADR-0005 were read for decision conflicts.
- Working tree note: the tree held uncommitted edits by other reviewers or the implementer (README, ADR-0015, tasks.md, TECHNICAL-SPEC, the policy template, `reviews/documentation.md`). This review reads the committed HEAD code and treats those files as read-only context.
- Commands run: `tests.test_setup_trust` (77 tests, OK), `tests.test_setup.NoOpTests/PrepareTests/RecoverableSetupTests`, `tests.test_ballast.PrepareTriggerTests`, `tests.test_doctor` (85 tests, OK), and `python3 -I -S` import of each `spec_workflow` module in isolation (no circular-import failure from `draft_pr` and `branch_sync` now importing `setup_trust`). The full suite and the live network path were not run.

## What was checked

**Requirement coverage.**
- FR-001 to FR-011 and AC-001 to AC-021 trace to `setup_trust._evaluate` and `_reference`, `tools/setup` (`main`, `prepare`, `settle`, `closing`, the recovered-preparation path and the no-op path) and `tests/test_setup_trust.py`.
- FR-012 to FR-015 and AC-022 to AC-024 trace to `launcher.record_baseline`, `baseline_source`, `operator_baseline`, `_status`, `_trust` and `tools/ballast._trust`.
- FR-016 and FR-020 hold (standard-library only; the module imports cleanly under `-I -S`).
- AC-025 and AC-027 are met by ADR-0015, the ADR-0007 and ADR-0011 annotations, the roadmap, the technical spec, the README and the policy template.
- AC-026 and FR-018 are not met in the tree (ENG-003).

**Eligibility order against ADR-0015.**
- The code order is: standard outside the checkout, tamper and in-progress markers, matching baseline kept, run state, configuration read once, installation record, pointer, committed, reviewed (operator baseline, then reviewed-repository and default branch).
- This equals the ADR's nine conditions and `setup_trust`'s docstring, and DEC-0001 explains the marker-before-keep order.
- Nothing reaches the network before the last step. `ls-remote` and `fetch` run in a throwaway bare repository under operator state with an environment that carries no checkout Git configuration.
- Only the scheme of `origin` is read. `git remote get-url` applies `insteadOf`, but the result is only tested with `startswith("https://")`, so the host and repository never come from the checkout.

**Source authority.**
- `launcher.record_baseline` is the only writer of `trusted.json` and `trusted-source.json`. `setup_trust` decides and calls it. `ballast trust` calls it with `source="trust"`.
- `trusted.json` bytes are identical to the old serialization (`json.dumps(indent=1)`, no trailing newline), so older launchers read them.
- Provenance is display only. The comparison, the refusals and the tamper marker are untouched, and `operator_baseline` fails closed on unreadable or unbound provenance.
- Preparation never opens its own baseline for the decision (`mode == "setup"` gates the keep step and the operator-baseline alternative). `_record` does open `trusted.json` to snapshot it for restore (ENG-004).

**Duplicated responsibility.**
- The Git environment rules now exist once (`setup_trust.DROPPED_ENV`, `GIT_LOCATION`, `child_path`, `base_environment`, `throwaway_environment`, `repository_url`).
- In `branch_sync`, the old `_env` body and the throwaway environment (SSH_ASKPASS, DISPLAY, WAYLAND_DISPLAY removed; `GIT_TERMINAL_PROMPT`, `GIT_NO_LAZY_FETCH`, `LC_ALL`, `GIT_ASKPASS`, `SSH_ASKPASS_REQUIRE`; then `GIT_CEILING_DIRECTORIES` and the later `GIT_DIR` and `GIT_OBJECT_DIRECTORY` additions) were compared line by line with the new delegation. The resulting environments are identical, so production behavior is unchanged.
- `draft_pr._pinned_repository` now uses `launcher.split_repository`, which has the same rule. `draft_pr.NAME` is an alias of `launcher.REPOSITORY_NAME`.
- Residual duplication is in ENG-006.

**Concurrency.**
- `settle` runs under the exclusive checkout lock, after the journal is gone, in setup, the no-op path, the recovered-preparation path and preparation.
- The reviewed record is a read-modify-write under `flock`, with atomic replace on read.
- `write_atomic` uses a temporary file, fsync, rename and a directory fsync.
- The post-write recheck and the restore of the previous baseline and provenance close F-004 (`_record`).
- A crash between the provenance and baseline writes is analyzed in ENG-005. The lock-hold duration is analyzed in ENG-001.

**Compatibility.**
- `status --json` omits `baseline_source` without a baseline, so the printed object is byte-identical to before. `tools/ballast._recorder` treats an absent, null or unknown value as "no recorder", so a pinned older launcher keeps working.
- A baseline written by this version has the old format, so an older launcher accepts it.
- The `tools/init` call sets `records_trust = False`, and `--check` never imports `setup_trust`. Setup's no-op path with trust off prints no reminder, as before.
- `_refusal_remedy` is the old if-chain extracted unchanged.

**Existing tests.**
- `git diff 641fa7f..HEAD` on `tests/test_doctor.py` and `tests/test_spec_workflow.py` is additions only (78 and 411 lines, 0 deletions).
- `tests/test_setup.py` has four changed expectations (`RecoverableSetupTests`, `NoOpTests`, two in `PrepareTests`, plus the recovered-preparation subtest), and `tests/test_ballast.py` has one. Each only prepends or appends a `No trust baseline recorded: <reason>.` line or the matching remedy line (via the new `NOT_RECORDED_RUNS` and `NOT_RECORDED_POINTER` constants). No assertion was removed or loosened, and the full `PREPARED`, `nothing changed` and `recovered` texts are still asserted.
- The no-op change is a visible behavior change: a skipped no-op setup now prints a reason and the `ballast trust` reminder where it used to print nothing (ENG-007).

**Error handling.**
- `settle` converts `_Ineligible`, `OSError`, `ValueError` and `SubprocessError` into a skipped verdict. All local and network failure modes seen in the code (offline, timeout, denied, unreadable file, failed write, changed input) reach one of these. The remaining gap is ENG-002.

**ADR-0015 completeness.**
- Conditions, observation commands, timeouts (30 s and 120 s), reviewed record, provenance, rejected alternatives and the two D-02 narrowings are all stated and match the code.
- Gaps are limited to ENG-004 and ENG-009.

## Findings

review: engineering
verdict: changes_required

### ENG-001
- severity: medium
- location: `tools/setup` `hold()`, `LOCK_RETRY_SECONDS = 2.0`, `prepare()`; `tools/spec_workflow/setup_trust.py` `_observe_in` (`LS_REMOTE_TIMEOUT` 30 s, `FETCH_TIMEOUT` 120 s)
- invariant_or_requirement: spec edge case "Two commands prepare the same worktree at once: only the one that installs may record, and the other reports that nothing needed preparing"; ADR-0011 and #15 AC-020 (two first commands never both refuse); research R2 (the lock is held for the decision and the plan accepted up to 150 s).
- evidence:
  - Fact: `prepare()` now holds the exclusive checkout lock while `settle` asks the network.
  - Fact: a second first-command (`run`, `ledger` or `intake`) calls `hold()`. `settled()` takes the shared lock without waiting and fails, then `lock()` fails and raises `RefusedError("another ballast preparation ... holds this checkout")`. `hold()` retries only until `LOCK_RETRY_SECONDS` (2 s) and then raises.
  - Fact: the retry budget was sized for a lock held for milliseconds. A real `ls-remote` plus `fetch` regularly takes more than 2 s, and the bound is 150 s.
  - Fact: the new concurrency tests use local fixtures (no latency), so none exercises a slow observation.
  - Uncertainty: I did not run a delayed-network scenario. The behavior is read from the code path.
- required_action: Choose and record one of: (a) make `hold()` wait at least as long as the observation bound, or until the holder finishes, before refusing; (b) keep the 2 s budget and state in `decisions.md` and the contract that a concurrent first command during a slow observation now refuses with the holder's PID, with the remedy "wait and rerun". Add a test with a stubbed slow observation (hold the lock, start a second preparation) that shows the chosen result. Do not leave R2's 150 s bound silent about `hold()`.

### ENG-002
- severity: low
- location: `tools/setup` `settle()` (the `import setup_trust` and `setup_trust.settle` call), `main()`, `prepare()`; `setup_trust.settle` docstring ("never raises")
- invariant_or_requirement: FR-008 and AC-017 ("the installation itself succeeds or fails exactly as it does today").
- evidence:
  - Fact: `settle` catches only `_Ineligible`, `OSError`, `ValueError` and `SubprocessError`. The `import setup_trust` is outside any handler.
  - Fact: an unexpected `KeyError`, `TypeError` or `ImportError` (a malformed record, a missing module in a damaged cache) propagates after the installation is committed and the lock is about to be released. `main()` then never prints "Spec Kit ... are set up", and `cli()` turns `RuntimeError`, `ValueError` or `OSError` into exit 1 and anything else into a traceback.
  - Uncertainty: I found no concrete trigger on a well-formed state. This is a defensive gap, not an observed failure.
- required_action: Wrap the import and the `settle` call in `tools/setup` so any `Exception` becomes a skipped verdict that names the error and `ballast trust` (this is a trust boundary where the decision must never change the installation outcome). Correct the "never raises" docstring or make it true. Add one test that makes `setup_trust.settle` raise and shows the installation still reports success.

### ENG-003
- severity: medium
- location: `.specify/memory/constitution.md` (unchanged); `specs/55-setup-trust/constitution-amendment.md`; `tasks.md` T038
- invariant_or_requirement: FR-018, AC-026 (BL-INV-002 amended with the reason recorded); constitution governance for an R2 change.
- evidence:
  - Fact: BL-INV-002 in the tree still says the launcher refuses until the operator trusts the inputs, while ADR-0015 and the code let setup record them. T038 records that the file is a protected input and the amendment text is parked in the feature folder.
  - Fact: the amendment text, the version bump (1.2.0) and the history entry exist and match the ADR's conditions.
  - Uncertainty: whether the operator applies it as part of this PR is outside the code; the spec says the merge is the approval.
- required_action: Keep AC-026 and FR-018 explicitly open in `tasks.md` and the spec status, and make the PR description name the operator step (apply the amendment, bump the version) as a required follow-up so the accepted invariant and the code are not left contradicting each other. No code change.

### ENG-004
- severity: low
- location: `docs/adr/0015-setup-recorded-trust-baseline.md` Decision (conditions 3 and 9, "Supersedes in part"); `setup_trust._evaluate`, `_reference` (`mode == "setup"`), `_record`; `decisions.md` DEC-0004
- invariant_or_requirement: FR-009 ("preparation records under the same conditions as setup"); ADR consistency with code.
- evidence:
  - Fact: ADR-0015 lists the matching-baseline step (3) and the operator-baseline alternative (9a) without saying they apply to setup only. The code skips both in preparation (DEC-0004).
  - Fact: ADR-0015 says it supersedes ADR-0011's "never reads any trusted.json" for the checkout's own baseline, while the decision logic in preparation never reads it. `_record` still opens `trusted.json` and `trusted-source.json` through `_read_regular` to snapshot them for restore. On the eligible path both are already removed by `fill_from_candidates`, so the read finds nothing.
  - Consequence: an offline preparation can never record, even when the worktree's configuration equals the primary checkout's operator baseline. This is a narrower rule than FR-009's wording, listed only as a "clarification" in DEC-0004.
- required_action: State in ADR-0015 that conditions 3 and 9a apply to setup only, name the offline-preparation consequence, and describe `_record`'s read as a restore snapshot. Reclassify DEC-0004 as a departure from FR-009 for merge review, not a clarification.

### ENG-005
- severity: low
- location: `launcher.record_baseline` (provenance first, then baseline) and its docstring; `baseline_source`, `operator_baseline`
- invariant_or_requirement: FR-013 (a missing or unbound record reads as operator `trust`); data-model partial-write behavior; F-004.
- evidence:
  - Fact: `record_baseline` replaces the old `trusted-source.json` before it writes the new `trusted.json`. A kill between the two leaves the old baseline with a provenance bound to a baseline that was never written.
  - Fact: `baseline_source` then reads `trust`, and `operator_baseline` returns `None` (a provenance file exists but is unbound), so eligibility fails closed.
  - Fact: the docstring's "which reads as the old baseline's `trust`" is correct only if the old baseline was operator-recorded. If the old baseline was setup-recorded, doctor and `status --json` now name the operator, overstating human review. This is display only: the comparison never reads provenance.
  - Related, low: a kill leaves `trusted.json.<random>` temporary files in the state directory (`write_atomic`), and `setup-trust/<random>/` scratch directories after a kill during observation; nothing cleans them.
- required_action: Accept and document it accurately (state both outcomes in the docstring and ADR consequences), since reordering the writes only moves the window. Optionally have the next `settle` remove stale `trusted.json.*` and `setup-trust/*` entries.

### ENG-006
- severity: low
- location: `setup_trust._run`, `Result`, `GIT_FLOOR`, `NO_MAINTENANCE`, `_git_program`, `repository_url` (unused `root`); `branch_sync._run`, `Result`, `GIT_FLOOR`, `NO_MAINTENANCE`, `_git_version`, `DROPPED_ENV` alias; `draft_pr` and `branch_sync` PATH handling
- invariant_or_requirement: plan-review F-002 (one copy of security-relevant Git rules); FR-004 ("the same trusted path"); engineering policy on duplicated responsibility.
- evidence:
  - Fact: the environment builders are shared, but the bounded runner (timeout, `start_new_session` for network, `Result`), the Git-version floor and probe, and the maintenance-off flags are copied between the two modules. `_git_program` also runs `git version` twice per `settle` (from `_check_committed` and `_reference`).
  - Fact: `branch_sync.DROPPED_ENV` is now an alias used only by `_git_version`.
  - Fact: `branch_sync` PATH now comes from `setup_trust.child_path(root)` reading `os.environ` directly. It used to go through `draft_pr._path_entries`, so a test patching that seam no longer affects `branch_sync`. Production is identical, and no test in the repository relies on it.
- required_action: Optional. Move the runner, `Result`, `GIT_FLOOR` and the version probe into the shared module (or add a drift test, like `SharedRulesTests` for the environment), call `_git_program` once, and drop the unused `root` argument.

### ENG-007
- severity: info
- location: `tools/setup` `closing()`, `report_prepared()`; `tests/test_setup.py` expectations (`NOT_RECORDED_RUNS`, `NOT_RECORDED_POINTER`); DEC-0003
- invariant_or_requirement: AC-017 and FR-008 (say why nothing was recorded) against R18 (ineligible fixtures keep today's output).
- evidence:
  - Fact: a no-op `ballast setup` that records nothing now prints the reason and "Review the changed protected inputs, then run `ballast trust` before the next workflow run", although nothing changed. The line order also differs between modes: setup prints the verdict after "Spec Kit ... are set up", while preparation prints the reason before "Prepared the ...". Both are recorded in DEC-0003.
  - Fact: each changed expectation in `tests/test_setup.py` and `tests/test_ballast.py` is only an added reason or remedy line. Nothing was weakened.
- required_action: None required. Consider a neutral remedy wording for the no-op case.

### ENG-008
- severity: low
- location: `setup_trust._record` (`previous = [_read_regular(path, 1 << 20) ...]` before the `try`)
- invariant_or_requirement: FR-008 (a failure to record leaves the installation and the earlier baseline untouched, with a message that names the cause).
- evidence:
  - Fact: a previous `trusted.json` larger than 1 MiB makes `_read_regular` raise `OSError("larger than 1024 KiB")` before anything is written. `settle` reports "could not record it (larger than 1024 KiB)" for an otherwise eligible checkout.
  - Uncertainty: this needs an operator baseline that includes a large `.venv` while the new checkout has none. I did not construct it.
  - It fails closed and changes nothing on disk.
- required_action: Drop the cap for the restore read (it is operator state) or use `launcher`'s size-free read, and cover it with one test.

### ENG-009
- severity: medium
- location: `launcher.reviewed_repositories`, `add_reviewed`, `_review_repository`; `setup_trust._reference` (the `NOT_REVIEWED` check); ADR-0015 "Reviewed repositories"; spec Assumptions
- invariant_or_requirement: FR-005, AC-016 (changing `[github] repository` must not by itself make a checkout eligible); the feature's safety boundary (an unreviewed `ballast.toml` is never recorded).
- evidence:
  - Fact: the record is machine-wide and holds repository identities only, with no binding to a project or checkout. Any committed `ballast.toml` that equals the default branch of any reviewed repository is eligible in any checkout.
  - Scenario (read from the code, not run): checkout B of project B is repointed by an agent to `[github] repository = "Y"` where Y is a repository the operator trusted for another project, with `ballast.toml` and constitution set to Y's current default-branch files (for example, Y's wider `[agents.permissions]`). After the operator runs `ballast setup` in B, `_reference` finds Y reviewed and the files equal, so a baseline is recorded for a configuration no human reviewed for B.
  - Fact: AC-016 and the spec's Assumptions only cover a repository the operator never reviewed. The spec does accept "in any checkout" for the reviewed record, so this follows the written design; ADR-0015 does not state the cross-project consequence.
  - Uncertainty: how practical this is depends on Y's file differing from B's reviewed one and on an agent knowing a reviewed repository name. Whether a project binding is wanted is a product decision for merge review.
- required_action: State the cross-project consequence in ADR-0015's consequences and in the list of agent inferences for merge review, or tighten the rule (for example, also require the checkout's own previous operator baseline, when one exists, to name the same repository). The security review should rule on it.

## Resolution

Resolved by the implementer after the review.

- ENG-001 (medium): fixed. The holder file now records `phase: settling` while `settle` runs; a second preparation waits up to `SETTLE_WAIT_SECONDS` (240 s) for a live settling holder and still refuses a plain holder after `LOCK_RETRY_SECONDS`, so two first commands do not both refuse while the network is asked. Tests: `PrepareTrustTests.test_a_second_preparation_waits_for_a_baseline_decision` (fails without the wait), `test_a_second_preparation_still_refuses_a_plain_holder`, `test_a_stale_settling_holder_does_not_wait`, `test_two_preparations_at_once_record_once`.
- ENG-002 (low): fixed. `settle` converts any exception into a skipped verdict, and `tools/setup` falls back to `Unrecorded` when the module cannot be loaded or crashes, so a committed installation never becomes a failed setup. Tests: `test_an_unexpected_failure_never_escapes`, `test_a_crash_in_the_decision_never_fails_the_installation`.
- ENG-003 (medium): operator step, not an agent edit. `.specify/memory/constitution.md` is a protected input; the amendment is `specs/55-setup-trust/constitution-amendment.md` (version 1.2.0), applied by the operator at merge as for #27. Until then BL-INV-002 reads as before and the code is more permissive than it; the PR says so.
- ENG-004 (low): documented. ADR-0015 states the own-baseline alternative is setup-only; `decisions.md` DEC-0004 records the departure from FR-009's wording (research R7 and ADR-0011 already required it).
- ENG-005 (low): partly fixed. A killed setup's scratch directories are removed by the next observation (`test_stale_scratch_directories_are_removed`). A temporary file left by a SIGKILL inside the state directory is left as it is (operator-only, small, replaced by the next write); the `record_baseline` docstring is unchanged because its crash behavior is what the tests pin.
- ENG-006 (low): accepted. The version probe now runs once per `settle`; the Git runner and `Result` shape of `branch_sync` and `setup_trust` stay separate because merging them changes a 1,900-line module outside this feature. The security-relevant environment rules are shared.
- ENG-007 (info): no action; DEC-0003 records the output order.
- ENG-008 (low): fixed. The previous baseline is read in full for the restore.
- ENG-009 (medium): not an implementation defect; the spec accepts a machine-wide record. Documented in ADR-0015 "Residual risks" and README, and proposed for human resolution as DEC-0008.

Verdict after resolution: approved, with the operator steps (constitution) and DEC-0008 for the merge reviewer.
