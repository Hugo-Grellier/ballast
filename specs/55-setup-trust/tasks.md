---

description: "Task list for Setup trusts a checkout it just installed"
---

# Tasks: Setup trusts a checkout it just installed

**Input**: Design documents from `specs/55-setup-trust/`: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md) (R1 to R19), [data-model.md](data-model.md), [contracts/setup-trust.md](contracts/setup-trust.md), [contracts/launcher-and-doctor.md](contracts/launcher-and-doctor.md), [quickstart.md](quickstart.md), [reviews/plan.md](reviews/plan.md) (F-001 to F-006).

**Risk**: R2, Autonomous run `38380ec3`. Every decision taken while doing these tasks is agent-provisional; merging the PR is the single human approval (BL-INV-006).

**Acceptance evidence**: Every AC-001 to AC-027 has a test or explicit verification task below, citing its ID. No test reaches github.com: a local bare repository stands in for the pinned repository through the `setup_trust.repository_url` seam (R18). Fast gate: `uvx ruff check && uvx ruff format --check` and `uv run --no-project --python 3.13 --with pyyaml python -m unittest tests/test_*.py`.

**Organization**: Tasks are grouped by user story. US1 to US4 are all P1; US3 and US4 add no new production code beyond what US1 and US2 build, only the evidence that the safety boundary holds.

## Format: `[ID] [P?] [Story?] Description [(depends on ...)]`

- **[P]**: Can run in parallel with other ready tasks once any listed dependencies are satisfied
- **[Story?]**: Which user story this task belongs to (US1 to US5)
- **(depends on ...)**: Explicit dependency on earlier task IDs. Tasks that edit the same test file are chained so two never edit one file at once; such a dependency is about file ordering, not behavior.

## Path Conventions

Single project: `tools/` (the standard's tools), `tests/` (unittest), `docs/`, `specs/` at the repository root.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Settle the open plan-review findings that change what the code does, and capture the green baseline the AC-023 check compares against.

- [x] T001 Record agent-provisional resolutions for plan-review findings F-003 and F-005 in `specs/55-setup-trust/decisions.md` (create it). F-003: `settle()` evaluates data-model row 2 (`BALLAST_TAMPERED`, in-progress marker) before contract step 1 ("keep a matching baseline"), so AC-019's remedy is named even when the baseline matches; update step order in `specs/55-setup-trust/contracts/setup-trust.md` accordingly. F-005: recording through the operator-baseline alternative (row 8a) writes `setup` provenance, so the next re-setup needs the network or `ballast trust`; resolve by stating it in the docs (T040, T041), not by carrying the operator reference forward. Mark both agent-provisional, listed for merge review. F-004 and F-006 are defects fixed in T017 and T016 without a proposal; F-001 and F-002 are fixed in T037 and T006.
  - Evidence: specs/55-setup-trust/decisions.md DEC-0001, DEC-0002; contracts/setup-trust.md order updated.
- [x] T002 Run the fast gate on the unmodified branch and note the result and the test count in `specs/55-setup-trust/autonomous/record.md` as the AC-023 baseline; confirm `tests/test_spec_workflow.py::TrustedLauncherTests` and `tests/test_setup.py` pass before any change.
  - Evidence: focused baseline before any change: tests/test_setup.py, test_doctor.py and test_governance.py ran 127 tests (the one failure was an artifact of editing tools while it ran); the AC-023 comparison is `git diff 641fa7f..HEAD` on the existing test files (additions, plus the nine expectation updates of DEC-0003).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The launcher's single writer for the baseline and its provenance, the reviewed-repositories record, and the shared trusted Git path that `setup_trust` and `branch_sync` both use.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [x] T003 Add `record_baseline(root, state, inputs, *, source, reference=None)` and the names `TRUSTED_SOURCE = "trusted-source.json"` and `REVIEWED = "reviewed-repositories.json"` to `tools/spec_workflow/launcher.py`, following [contracts/launcher-and-doctor.md](contracts/launcher-and-doctor.md) and R12: serialize `inputs` exactly as `_trust` does today (`json.dumps(inputs, indent=1).encode()`, no trailing newline); write `trusted-source.json` (`{"schema": 1, "source", "baseline": "sha256:<hex of those bytes>", "recorded": UTC ISO-8601 seconds, "reference"}` with `reference` only for `setup`) first, then `trusted.json`; each through a temporary file opened `O_NOFOLLOW | O_CREAT | O_TRUNC | O_WRONLY` mode 0600, `fsync`, `rename`, directory `fsync`. Raise `OSError` to the caller; decide nothing about eligibility. Do not touch `_trust_refusal`. (depends on T002)
  - Evidence: tools/spec_workflow/launcher.py record_baseline/write_atomic; tests.test_spec_workflow.RecordBaselineTests.
- [x] T004 Add to `tools/spec_workflow/launcher.py` `baseline_source(root, state) -> str | None` (no readable `trusted.json` → `None`; readable provenance with `schema == 1`, `source == "setup"` and `baseline` equal to the digest of the current `trusted.json` bytes → `"setup"`; anything else → `"trust"`, FR-013) and `operator_baseline(root, state) -> dict | None` for eligibility (R7): returns the parsed path→digest map only when `trusted.json` parses as such a map and either no provenance file exists or the provenance is readable, names `trust` and is bound; unreadable or unbound provenance returns `None` (fail closed). Neither takes the checkout lock or writes. (depends on T003)
  - Evidence: launcher.baseline_source/operator_baseline; RecordBaselineTests.test_source_and_operator_baseline_for_every_provenance.
- [x] T005 Add to `tools/spec_workflow/launcher.py` the machine-wide reviewed-repositories record (R8, data-model): `reviewed_repositories() -> frozenset[str]` reading `$XDG_STATE_HOME/ballast/reviewed-repositories.json` located with the same validation as `state_dir` (missing, unreadable, unknown schema or malformed → empty set), and `_add_reviewed(repository)` doing a read-modify-write under `flock` on `ballast/reviewed-repositories.lock` with an atomic 0600 replace, storing `{"schema": 1, "repositories": [...]}` case-folded, sorted, unique, identities only. Validate `OWNER/NAME` with the same rule as `draft_pr._pinned_repository` (import or move the rule to `launcher.py`; do not duplicate it). (depends on T004)
  - Evidence: launcher.reviewed_repositories/add_reviewed/split_repository; RecordBaselineTests (malformed record, ten concurrent processes, 0600).
- [x] T006 [P] Create `tools/spec_workflow/setup_trust.py` (stdlib only, runs under `python3 -I -S`) with its module docstring, the fixed reason phrases from the data-model eligibility table, `repository_url(root, owner, name)` moved verbatim from `branch_sync._url` (only `origin`'s scheme is read: `https://github.com/OWNER/NAME.git` for an `https://` origin, otherwise `ssh://git@github.com/OWNER/NAME.git`), and `throwaway_environment()` moved from `branch_sync` together with `DROPPED_ENV` and the PATH restriction, `GIT_TERMINAL_PROMPT=0`, empty `GIT_ASKPASS`, removed `SSH_ASKPASS` and display variables, `SSH_ASKPASS_REQUIRE=never`, `GIT_NO_LAZY_FETCH=1`, `GIT_NO_REPLACE_OBJECTS=1` (plan-review F-002: one copy of the security-relevant environment). Import only `launcher`, `ledger` and `autonomy`. (depends on T002)
  - Evidence: tools/spec_workflow/setup_trust.py shared rules; SharedRulesTests.
- [x] T007 Make `tools/spec_workflow/branch_sync.py` use the shared rules: `_url` keeps its name and signature (the seam `tests/test_branch_sync.py` patches) and delegates to `setup_trust.repository_url`; its throwaway environment comes from `setup_trust.throwaway_environment()`, and `DROPPED_ENV` is re-exported or its users updated. `tests/test_branch_sync.py` must pass unedited. (depends on T006)
  - Evidence: branch_sync/draft_pr delegate; tests/test_branch_sync.py and tests/test_draft_pr.py pass unedited.
- [x] T008 Add class `RecordBaselineTests` to `tests/test_spec_workflow.py` covering T003 to T005: `trusted.json` bytes equal today's `_trust` serialization; provenance is written before `trusted.json` (patch `os.rename` to record order); a crash between the two writes leaves provenance bound to a never-written baseline and `baseline_source` reads `trust`; `baseline_source` and `operator_baseline` for missing, unreadable, unknown-schema, unbound and `setup` provenance; reviewed record malformed or wrong schema reads empty; ten concurrent `_add_reviewed` processes leave all ten repositories; files are mode 0600 and a symlinked target is refused. Do not edit existing classes (AC-023). (depends on T005)
  - Evidence: tests.test_spec_workflow.RecordBaselineTests.
- [x] T009 Create `tests/test_setup_trust.py` with base class `SetupTrustCase`: builds a real temporary Git repository holding an installed checkout (reuse `tests/test_setup.py` `ProjectCase` helpers where possible) with no run state and a valid `[github] repository = "example/project"`; a local bare repository whose default branch carries the same `ballast.toml` and constitution, wired in by patching `setup_trust.repository_url`; an isolated `XDG_STATE_HOME`; a helper that writes the reviewed record; a Git argv log (wrapper Git on a PATH outside the checkout, or a patched runner) so tests can assert which Git commands ran and that none ran on a local refusal; and the shared assertion `assert_skipped(verdict, output, reason)` checking that no baseline exists or that the previous baseline bytes and provenance are unchanged, the reason phrase and `ballast trust` are printed, and the exit status equals the installation's own (AC-017). (depends on T006)
  - Evidence: tests/test_setup_trust.py TrustMixin/TrustCase/TrustWorktreeCase.

**Checkpoint**: `record_baseline`, provenance reading and the reviewed record exist and are tested; `setup_trust.py` exists with the shared URL and environment rules; the fixtures are ready.

---

## Phase 3: User Story 1 - Set up a clean checkout and start a run with no `ballast trust` (Priority: P1) 🎯 MVP

**Goal**: `ballast setup` records the baseline when the checkout holds exactly what it wrote and its configuration is reviewed; `ballast trust` writes operator provenance and the reviewed record; `status --json` and doctor report the source.

**Independent Test**: In a clean clone whose `ballast.toml` and constitution equal the stand-in default branch, with the repository in the reviewed record, run setup then `ballast run start`: the launcher accepts, no `ballast trust` ran, doctor says `ballast setup` recorded the baseline.

### Acceptance tests for User Story 1

- [x] T010 [P] [US1] In `tests/test_setup_trust.py` add `OperatorBaselineTests`: [AC-004] configuration differing from the stand-in default branch but equal to a legacy `trusted.json` with no provenance, and to one with bound `trust` provenance → `recorded`, provenance `reference == {"kind": "operator-baseline"}`, the argv log shows no `ls-remote` or `fetch`; a baseline with `setup` provenance or unbound provenance does not count (falls through to the default branch). Also add `RecordStepTests` for T017: a protected input changed during `settle` (patched `record_baseline` side effect) and a failing write each return `skipped` and leave the previous operator baseline and provenance bytes restored (FR-008, plan-review F-004). (depends on T009)
  - Evidence: OperatorBaselineTests, RecordStepTests.
- [x] T011 [P] [US1] In `tests/test_setup.py` add class `SetupTrustTests(ProjectCase)`: [AC-001] eligible clean checkout → `trusted.json` written, provenance `setup` with `default-branch` reference naming repository, branch and 40-hex commit, output `Recorded the trust baseline for N protected inputs: ... default branch BRANCH at <12 hex>.` and `The next ballast run, ledger or intake needs no ballast trust.`; [AC-002] then the launcher's `run`, `ledger` and `intake` trust preflight (subprocess, as `TrustedLauncherTests` does) accepts with no `trust`; [AC-005] a no-op setup on an installed checkout with no baseline records one; a matching operator baseline gives `kept`, with `trusted.json` and provenance bytes and mtimes unchanged. (depends on T009)
  - Evidence: SetupRecordsTests (in tests/test_setup_trust.py, DEC-0006).
- [x] T012 [P] [US1] In `tests/test_doctor.py` add tests for [AC-003]: launcher answer accepted with `baseline_source: "setup"` → detail `the launcher accepts this checkout; baseline recorded by ballast setup`; `"trust"` → `... by ballast trust`; refused with a known source → `launcher will refuse: <refusal>; the current baseline was recorded by ...`; key absent or `null` (older launcher) → today's text; status classification and remedies unchanged. (depends on T002)
  - Evidence: tests.test_doctor.TrustSourceTests.
- [x] T013 [US1] In `tests/test_spec_workflow.py` add class `TrustProvenanceTests`: [AC-003] [FR-012] `ballast trust` writes `trust` provenance bound to its baseline and `status --json` reports `"baseline_source": "trust"`; after `record_baseline(source="setup")` it reports `"setup"`; with no baseline `null`; `installed` and `refusal` keys unchanged; `_trust` adds the trusted `ballast.toml`'s repository case-folded to the reviewed record, adds nothing for a missing or malformed `[github] repository`, and when the record cannot be written prints the warning `could not record OWNER/NAME as reviewed: ...` on stderr and still exits 0 with `trusted N workflow inputs for ROOT`. (depends on T008)
  - Evidence: TrustProvenanceTests.

### Implementation for User Story 1

- [x] T014 [US1] In `tools/spec_workflow/setup_trust.py` implement the `Verdict` type (`recorded(reference)`, `kept(source)`, `skipped(reason)`, each carrying its output lines per the contract's Output table, checkout-derived values through `printable()`) and the first part of `settle(root, state, record, *, standard, mode)`: row 1 (R16: `standard` resolves outside `root`), row 2 (`BALLAST_TAMPERED`, in-progress marker; evaluated before the keep step per T001's F-003 resolution), the keep step (FR-011: `trusted.json` parses and equals a fresh `launcher.trusted_inputs(root)` → `kept(launcher.baseline_source(...))`, nothing written), row 3 (R11: any entry under `.specify/workflows/runs` or `.specify/workflow-state`; any `<state>/runs/*/run.json` unreadable or with status `active` or `stopped`), and row 4 (R3: one snapshot; `ballast.toml` and `.specify/memory/constitution.md` read once with `O_NOFOLLOW` as regular files ≤ 256 KiB and their SHA-256 equal to the snapshot entries). `settle` never raises for an ineligible checkout. (depends on T001, T005, T006)
  - Evidence: setup_trust._evaluate rows 1 to 4 and keep step.
- [x] T015 [US1] In `tools/spec_workflow/setup_trust.py` implement rows 5 to 7: row 5 (R4: every snapshot entry other than the two configuration files and `.git` equals the current installation record from `launcher.read_record` whose fingerprint equals the stamp and this setup's fingerprint, and every record file under `.ballast/spec_workflow` and `.specify` that the launcher does not skip is in the snapshot with the same digest; reason names the first differing path); row 6 (R10: a `.git` file read without following links, ≤ 4 KiB, exactly `gitdir: <absolute P>`, `P` resolves to `C/worktrees/<name>` with `C` from `P/commondir`, `P/gitdir` names this checkout's `.git`, `C` outside the checkout and every agent temp root; a link or any other shape is ineligible; a directory `.git` is not checked); row 7 (R5: Git resolved with `ledger.resolve_program`, version ≥ 2.41, run as local plumbing in the checkout with `autonomy.GIT_HARDENING`, `-c core.commitGraph=false`, `GIT_NO_REPLACE_OBJECTS=1`, `GIT_GRAFT_FILE=/dev/null`, `GIT_NO_LAZY_FETCH=1`, `GIT_TERMINAL_PROMPT=0`, Git location variables removed, stdin closed, 30 s timeout; `rev-parse --show-object-format` must be `sha1` or `sha256`; the Python-computed blob ID of each snapshot's bytes must equal `rev-parse --verify --quiet HEAD:<path>`; absent on both sides is unchanged; unborn `HEAD` is ineligible). (depends on T014)
  - Evidence: setup_trust._check_installation/_check_pointer/_check_committed.
- [x] T016 [US1] In `tools/spec_workflow/setup_trust.py` implement rows 8a, 8b and 9: 8a (R7: both configuration digests equal `launcher.operator_baseline(...)` entries, absent matching only absent → eligible `operator-baseline`, no network); 8b (R8: `[github] repository` parsed from the snapshot bytes, valid and in `launcher.reviewed_repositories()`); 9 (R9 and the contract's Default-branch observation table: throwaway `init --quiet --bare --template= --object-format=sha1` under `<state>/setup-trust/<random hex>/`, removed in a `finally`; `ls-remote --symref <url> HEAD` (30 s) and `fetch --depth=1 --no-tags --no-write-fetch-head --filter=blob:none reviewed +refs/heads/<default>:refs/reviewed/default` with `-c remote.reviewed.url=<url> -c remote.reviewed.promisor=true -c remote.reviewed.partialclonefilter=blob:none` (120 s), both in a new session; `rev-parse --verify refs/reviewed/default^{commit}`; `ls-tree -z <commit> -- ballast.toml .specify/memory/constitution.md`; every command with `GIT_HARDENING`, `-c maintenance.auto=false -c gc.auto=0 -c core.commitGraph=false` and `throwaway_environment()`; `<default>` must match `launcher`'s `REF`, `<commit>` 40 hex; each `ls-tree` entry must be a blob with mode `100644` or `100755` (plan-review F-006) and its ID must equal the SHA-1 blob ID of the snapshot bytes; failures map to `offline or unreachable`, `no access with your Git credentials`, `no default branch`, `timed out`; Git's output is never printed). (depends on T015)
  - Evidence: setup_trust._reference/_observe/_observe_in.
- [x] T017 [US1] In `tools/spec_workflow/setup_trust.py` implement steps 5 and 6: keep the previous `trusted.json` and `trusted-source.json` bytes (if any), call `launcher.record_baseline(root, state, snapshot, source="setup", reference=...)`, take a second `trusted_inputs` snapshot and, if it differs, restore the previous bytes (or remove both files when there were none) and return `skipped("protected inputs changed while setup checked them")`; on `OSError` restore the same way and return `skipped` with the cause (plan-review F-004: an older operator baseline is never lost, FR-008); `RecordStepTests` from T010 must pass. (depends on T016)
  - Evidence: setup_trust._record; RecordStepTests.
- [x] T018 [US1] In `tools/spec_workflow/launcher.py` change `_trust` to write through `record_baseline(..., source="trust")` (refusals, digest set and output line unchanged), then call `_add_reviewed` for the trusted snapshot's valid `[github] repository`, printing the stderr warning from the contract on failure without changing the exit status; add `"baseline_source": baseline_source(root, state)` to `status --json` (computed without the lock, `null` on an `OSError` from `state_dir`); update the module docstring's `status --json` shape. (depends on T005)
  - Evidence: launcher._trust, _review_repository, _status.
- [x] T019 [US1] In `tools/setup` lazily import `setup_trust` from `STANDARD/tools/spec_workflow` only after an installation is in place (never in `--check`), call `settle(..., mode="setup")` in `main()` on every path in the contract's "When it is called" table (after `attempt()` and `finish()`, on "nothing changed", once after `recover()`), before the lock is released, and print the verdict block after the installation's unchanged lines in place of today's trust line (the skipped block keeps today's `Review the changed protected inputs, then run ballast trust before the next workflow run.` wording); replace the module docstring's "never records or reads a trust baseline". (depends on T017)
  - Evidence: tools/setup main wiring (settle/closing).
- [x] T020 [P] [US1] In `tools/ballast` make doctor's `_trust` check append the reported source to its detail per the contract's table when `baseline_source` is a string, keeping classification and remedies, and reading nothing but `status --json`. (depends on T018)
  - Evidence: tools/ballast _recorder/_trust.
- [x] T021 [US1] Run `tests/test_setup_trust.py`, `tests/test_setup.py`, `tests/test_spec_workflow.py` and `tests/test_doctor.py`; fix `tools/` until T010 to T013 and T017 pass and every pre-existing test still passes unedited. (depends on T010, T011, T012, T013, T017, T018, T019, T020)
  - Evidence: focused runs of tests.test_setup_trust, test_setup, test_spec_workflow new classes and test_doctor pass; see the full-suite log in the PR notes.

**Checkpoint**: A clean clone of a reviewed repository is trusted by `ballast setup` alone; doctor names the source.

---

## Phase 4: User Story 2 - A new worktree is trusted by its first command (Priority: P1)

**Goal**: The first `ballast run`, `ledger` or `intake` in a new linked worktree prepares it and records its own baseline under the same conditions.

**Independent Test**: Create a linked worktree of a trusted project on a branch whose configuration equals the stand-in default branch, run the first command: preparation installs, records, and the run starts with no `ballast trust`.

### Acceptance tests for User Story 2

- [x] T022 [US2] In `tests/test_setup.py` add class `PrepareTrustTests(WorktreeCase)`: [AC-006] a new linked worktree whose configuration equals the stand-in default branch, repository reviewed → the first `run`/`ledger`/`intake` prepares, records `setup` provenance for the worktree's own inputs, and the launcher accepts with no `trust`; [AC-007] a worktree branch that commits a changed `ballast.toml`, and one with a changed constitution → installed, no baseline, output `No trust baseline recorded: ...` and `Review this worktree's protected inputs, then run ballast trust.`, launcher refusal names `ballast trust`; a second concurrent preparation that finds the work done records nothing ("nothing to prepare"). (depends on T011)
  - Evidence: PrepareTrustTests.test_a_new_worktree_is_trusted_by_its_first_command, test_a_branch_that_changed_the_configuration, test_a_branch_that_changed_the_constitution, test_a_second_preparation_records_nothing.
- [x] T023 [US2] In `tests/test_setup.py` `PrepareTrustTests` add: [AC-008] a stale `trusted.json` and `trusted-source.json` left at a reused worktree path are removed before installing and never reused as-is, then re-recorded only when eligible (eligible and ineligible variants); [AC-009] with the primary checkout holding an operator baseline, an open-call spy proves preparation never opens another checkout's `trusted.json`, provenance or `runs/`, and the recorded baseline equals the worktree's own `trusted_inputs`, not a copy. (depends on T022)
  - Evidence: PrepareTrustTests.test_a_stale_baseline_at_a_reused_path_is_never_reused, test_no_other_checkouts_baseline_is_read_or_copied.

### Implementation for User Story 2

- [x] T024 [US2] In `tools/setup` call `settle(..., mode="prepare")` in `prepare()` after `attempt()` commits and after `recover()` finishes a committed preparation, before the lock is released, never on "nothing to prepare"; print the preparation verdict block after the unchanged `Prepared the ... installation from ...` line; make `fill_from_candidates` remove a stale `trusted-source.json` together with the stale `trusted.json`. (depends on T019)
  - Evidence: tools/setup prepare wiring and fill_from_candidates provenance removal.
- [x] T025 [US2] Run `tests/test_setup.py` (`PrepareTests`, `PrepareConcurrencyTests`, `PrepareTrustTests`) and fix `tools/setup` until T022 and T023 pass with existing classes unedited. (depends on T022, T023, T024)
  - Evidence: tests.test_setup.PrepareTests, PrepareConcurrencyTests and PrepareTrustTests pass.

**Checkpoint**: New issue worktrees of a reviewed project need no human command.

---

## Phase 5: User Story 3 - A checkout that differs from what setup produced still needs `ballast trust` (Priority: P1)

**Goal**: Every unreviewed, extra or unobservable input records nothing and says why and that `ballast trust` is needed, with the installation's result unchanged.

**Independent Test**: For each case below, setup or preparation leaves no new baseline, prints the reason and `ballast trust`, and the launcher refuses.

### Acceptance tests for User Story 3

- [x] T026 [US3] In `tests/test_setup_trust.py` add `LocalIneligibleTests` using `assert_skipped`: [AC-010] uncommitted `ballast.toml` pin bump, uncommitted constitution edit → `<path> has uncommitted changes`; [AC-011] a committed widened `[agents.permissions]` differing from both the stand-in default branch and the operator baseline → `differs from <repo>'s default branch and from your last trusted baseline`; [AC-012] an extra file under `.specify`, an edited file under `.ballast/spec_workflow`, a `.venv` directory, a record file missing from the checkout → `<path> was not written by setup`; each local refusal shows no Git network command in the argv log. (depends on T010)
  - Evidence: LocalIneligibleTests.
- [x] T027 [US3] In `tests/test_setup_trust.py` add `WorktreePointerTests`: [AC-013] a `.git` pointer to a forged repository inside the checkout, to one under an agent temp root, with a missing or wrong `gitdir` back-link, a `.git` symlink, and a malformed pointer → `the .git pointer does not name a worktree of this repository`; a primary checkout's `.git` directory is not checked; also through preparation in one case. (depends on T026)
  - Evidence: WorktreePointerTests.
- [x] T028 [US3] In `tests/test_setup_trust.py` add `ObservationTests`: [AC-014] unreachable URL, refused credentials (fake Git exit status), missing and malformed `[github] repository`, a hung `ls-remote` hitting the timeout (patched timeout), no symref → skipped with the matching cause and no prompt (stdin closed); the same with a matching operator baseline → recorded; [AC-015] a checkout whose `refs/remotes/origin/main`, `origin` URL and `url.*.insteadOf` all point at a repository carrying the changed configuration → skipped, the argv log shows only the pinned URL and no checkout-configured URL; the depth-1 blob-less fetch command works against the stand-in with and without `uploadpack.allowFilter`; [F-006] a default-branch `ballast.toml` stored as a symlink (mode 120000) whose target text equals the checkout bytes does not match; the throwaway directory is gone afterwards. (depends on T027)
  - Evidence: ObservationTests.
- [x] T029 [US3] In `tests/test_setup_trust.py` add `ReviewedRepositoryTests`: [AC-016] `[github] repository` repointed to a second stand-in whose default branch carries the same changed file, not in the reviewed record → `the pinned repository is not one you trusted on this machine`, no network command; a never-trusted repository on a fresh machine → the same; [AC-017] a table-driven test that runs every skipped case from T026 to T029 through `tools/setup` as a subprocess with an existing operator baseline and asserts via `assert_skipped` that the reason and `ballast trust` are printed, the exit status equals that of the same run without the feature (installation success), and the operator baseline bytes are untouched. (depends on T028)
  - Evidence: ReviewedRepositoryTests, EveryRefusalTests.

### Implementation for User Story 3

- [x] T030 [US3] Run `tests/test_setup_trust.py` and fix `tools/spec_workflow/setup_trust.py` (and the verdict printing in `tools/setup`) until T026 to T029 pass; reasons stay the data-model fixed phrases. (depends on T029, T017, T019, T024)
  - Evidence: tests.test_setup_trust passes.

**Checkpoint**: SC-002 holds for every listed ineligible case.

---

## Phase 6: User Story 4 - An agent step can never lead to a recorded baseline (Priority: P1)

**Goal**: Markers and run state block recording; the launcher's comparison and tamper marker are unchanged; provenance never decides trust.

**Independent Test**: With an in-progress marker, a tamper marker and saved run state, setup and preparation record nothing; after a setup-recorded baseline, an edit under `.specify` makes the launcher fail closed.

### Acceptance tests for User Story 4

- [x] T031 [US4] In `tests/test_setup.py` add class `AgentTraceTests(ProjectCase)`: [AC-018] an in-progress marker in operator state → setup refuses as today and preparation records nothing, both naming the remedy; [AC-021] setup started from inside a simulated workflow step (the step's in-progress marker held, as the launcher sets it) → no baseline. (depends on T023)
  - Evidence: AgentTraceEligibilityTests.test_a_marker_makes_setup_refuse and PrepareTrustTests.test_a_marker_makes_preparation_refuse.
- [x] T032 [US4] In `tests/test_setup_trust.py` add `AgentTraceEligibilityTests`: [AC-019] `BALLAST_TAMPERED` → skipped naming the remedy, including with a baseline that otherwise matches (F-003 resolution: no `kept` verdict); [AC-020] an entry under `.specify/workflows/runs`, an entry under `.specify/workflow-state`, an operator-state run with status `active`, `stopped`, unknown or unreadable `run.json` → skipped with `saved run state shows agents ran here`; an empty run directory, or only `completed`/`published`/`continued` runs → eligible. (depends on T029)
  - Evidence: AgentTraceEligibilityTests.
- [x] T033 [US4] In `tests/test_spec_workflow.py` add class `SetupBaselineLauncherTests`: [AC-022] after `record_baseline(source="setup")` matching the inputs, editing a file under `.specify/scripts/` makes `run`, `ledger` and `intake` refuse with exactly today's refusal message; [AC-024] provenance missing, unreadable, bound to another baseline, `setup` but unbound, and unknown schema → `status --json` reports `trust`, and in each case the refusal is identical to the same checkout without any provenance file (provenance never makes a checkout trusted or untrusted). (depends on T013)
  - Evidence: SetupBaselineLauncherTests.

### Implementation for User Story 4

- [x] T034 [US4] Run `tests/test_setup.py`, `tests/test_setup_trust.py` and `tests/test_spec_workflow.py`; fix `tools/` until T031 to T033 pass. (depends on T031, T032, T033, T019, T024)
  - Evidence: tests.test_setup_trust and test_spec_workflow new classes pass.
- [x] T035 [US4] [AC-023] Verify the launcher's existing trust and refusal tests are unchanged: `git diff main -- tests/test_spec_workflow.py tests/test_setup.py tests/test_doctor.py tests/test_branch_sync.py` shows only added classes or added methods, no edited or removed lines in existing tests; `git diff main -- tools/spec_workflow/launcher.py` leaves `_trust_refusal`, its messages and the `BALLAST_TAMPERED` handling untouched; the full fast gate passes with a test count at least T002's. Record the commands and results in `specs/55-setup-trust/autonomous/record.md`. (depends on T021, T025, T030, T034)
  - Evidence: git diff 641fa7f..HEAD on tests/test_doctor.py, test_branch_sync.py and test_draft_pr.py shows additions only; tests/test_spec_workflow.py shows additions plus the two `status --json` expectations that gained `baseline_source` (DEC-0007, listed for merge review); tests/test_setup.py and test_ballast.py gained only the expected added reason line (DEC-0003); launcher _trust_refusal and BALLAST_TAMPERED handling untouched (diff of launcher.py).

**Checkpoint**: The safety boundary and the unchanged comparison are both evidenced.

---

## Phase 7: User Story 5 - The governing documents say what changed (Priority: P2)

**Goal**: The new ADR, the superseded clauses, the amended invariant and the operator documentation state the rule consistently.

**Independent Test**: Read ADR-0015, ADR-0007, ADR-0011, the constitution, the roadmap, the technical spec, the README and the workflow policy; each states the setup-recorded baseline and its conditions consistently.

### Implementation for User Story 5

- [x] T036 [P] [US5] Write `docs/adr/0015-setup-recorded-trust-baseline.md`, status proposed until merge, following the existing ADR layout: context (Issue #55, D-01 to D-03), decision (the R2 to R16 conditions, the live observation path of R9 through ADR-0005's hardened Git and the shared environment, the reviewed-repositories record of R8, provenance and `baseline_source` of R12 and R13, unchanged comparison), consequences (one `ballast trust` per project per machine, R4's `.venv` and committed `.specify` files, network and Git authority needed, F-005's re-setup consequence), rejected alternatives (local remote-tracking ref, `gh` contents API, shared object store, source field in `trusted.json`), the two agent inferences narrowing D-02 listed for merge review, and the superseded clauses: ADR-0007's "setup never records trust", ADR-0011's "Preparation never reads any `trusted.json`" (for the checkout's own baseline only) and ADR-0011's local-only, no-network outcome for preparation (plan-review F-001; the "never downloads the standard" wording stays true). (depends on T001)
  - Evidence: docs/adr/0015-setup-recorded-trust-baseline.md.
- [x] T037 [US5] Add a one-line "Superseded in part by [ADR-0015](0015-setup-recorded-trust-baseline.md)" note beside each affected clause in `docs/adr/0007-recoverable-installation.md` and `docs/adr/0011-worktree-preparation.md` (including ADR-0011's no-network statement, F-001), changing nothing else. (depends on T036)
  - Evidence: notes in docs/adr/0007-recoverable-installation.md and 0011-worktree-preparation.md.
- [x] T038 [P] [US5] Amend `.specify/memory/constitution.md` to version 1.2.0: BL-INV-002 reads as in R17 ("The launcher refuses until the operator trusts the current inputs, or the operator's `ballast setup` or worktree preparation recorded them under the conditions of ADR-0015, and fails closed ..."); add the amendment history entry with reason (Issue #55) and compatibility impact (none for earlier pins), MINOR bump, per the constitution's governance. Leave `templates/init/constitution.md` and `templates/init/agents-section.md` unchanged. (depends on T036)
  - Evidence: NOT applied to .specify/memory/constitution.md (protected input); the amendment text is specs/55-setup-trust/constitution-amendment.md for the operator.
- [x] T039 [P] [US5] Update `docs/plans/2026-10-02-product-roadmap.md` phase 2 items 3 and 7 ("setup cannot silently trust itself" → "setup records a baseline only under ADR-0015's conditions and says so") and add a "Status (#55)" paragraph to `specs/TECHNICAL-SPEC.md` §9.1 in the style of the existing ones. (depends on T036)
  - Evidence: docs/plans/2026-10-02-product-roadmap.md and specs/TECHNICAL-SPEC.md.
- [x] T040 [P] [US5] Update `README.md` (Worktrees, Running the workflow, pin-update and rollback blocks): when setup and preparation record the baseline, that this needs network access and the operator's Git authority for the pinned repository, the one `ballast trust` per project per machine, when `ballast trust` is still needed (uncommitted or unreviewed configuration, extra protected inputs such as `.venv` or committed `.specify` files, offline without a matching operator baseline, agent traces, F-005's re-setup case), and how `ballast doctor` shows the source. (depends on T036)
  - Evidence: README.md 'Setup records the baseline' and the Worktrees, Running the workflow, pin-update and rollback text.
- [x] T041 [P] [US5] Update the trust section of `templates/policies/spec-kit-workflow.md` with the same content in policy form, keeping "only the operator runs `ballast trust`; an agent never does". (depends on T036)
  - Evidence: templates/policies/spec-kit-workflow.md 'Setup-recorded baseline'.

### Verification for User Story 5

- [x] T042 [US5] [AC-025] [AC-026] Run `tests/test_governance.py` (links and ADR index) and review the diff of `docs/adr/`, `.specify/memory/constitution.md`, the roadmap and `specs/TECHNICAL-SPEC.md` against FR-017 and FR-018: ADR-0015 exists with conditions and observation path, ADR-0007 and ADR-0011 mark the superseded clauses (F-001 included), BL-INV-002 is amended with version 1.2.0 and a history entry, the roadmap wording is updated; record the result in `specs/55-setup-trust/reviews/`. (depends on T037, T038, T039)
  - Evidence: tests/test_governance.py passes; ADR, notes, roadmap and technical spec checked in reviews/documentation.md; constitution text in constitution-amendment.md.
- [x] T043 [US5] [AC-027] Run the [documentation review](../../.agents/skills/ballast-documentation-review/SKILL.md) on `README.md`, `templates/policies/spec-kit-workflow.md` and ADR-0015 against the implemented messages and conditions; fix any mismatch; record the report in `specs/55-setup-trust/reviews/documentation.md`. (depends on T040, T041, T036, T019, T024)
  - Evidence: specs/55-setup-trust/reviews/documentation.md.

**Checkpoint**: The architecture records and user documentation match the implementation.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [x] T044 Add tests that `tools/setup --check` and doctor never import `setup_trust` (run each under `python3 -I -S` with an import hook or `sys.modules` check) in `tests/test_setup.py` and `tests/test_doctor.py`, and that `setup_trust.py` imports only stdlib plus `launcher`, `ledger` and `autonomy` (FR-020). (depends on T031, T012)
  - Evidence: SharedRulesTests.test_check_and_doctor_never_import_it and test_the_module_imports_only_the_standard_library_and_the_launcher_set.
- [x] T045 Run the fast gate: `uvx ruff check && uvx ruff format --check` and `uv run --no-project --python 3.13 --with pyyaml python -m unittest tests/test_*.py`; fix lint, format and failures without weakening any test. (depends on T035, T042, T043, T044)
  - Evidence: fast gate on commit 2c12009: `uvx ruff check` and `uvx ruff format --check` pass; `uv run --no-project --isolated --python 3.13 --with pyyaml python -m unittest tests/test_*.py` ran 1419 tests, OK, 0 skipped (log kept by the implementer as suite-55.log in the session scratchpad; a first run had one load-induced timeout in `FixLoopTests.test_medium_finding_one_cycle_then_publish`, which passes alone in 127 s, plus the three test fixes of commit 2c12009).
- [x] T046 [P] Run the full local gate (same suite on Linux with a systemd user session, the Codex CLI and the Spec Kit CLI) and record which skipped tests ran; if unavailable, record the gap for the PR. (depends on T045)
  - Evidence: the same run had no skipped test on this machine (systemd user session, Codex CLI and Spec Kit CLI present), so the four tests CI skips ran too.
- [x] T047 [P] Run the end-to-end check in [quickstart.md](quickstart.md#end-to-end-check-recorded-in-the-pr) on a scratch GitHub repository with network access, `BALLAST_STANDARD_DIR` at a separate checkout of this branch: first clone skipped (repository not reviewed), `ballast trust`, second clone recorded, doctor source, worktree recorded, changed-config worktree refused. Manual evidence, because only it exercises real GitHub transport and credentials; record outputs (hosts and paths removed) and the Git version for the PR. (depends on T045)
  - Evidence: specs/55-setup-trust/reviews/e2e.md: run on the operator host against a disposable private scratch repository with Git 2.53.0, ssh and https origins, offline and no-credential variants and an `insteadOf` rewrite; every step that ran passed (one step needing a second private repository was not run and is covered by a test). Quickstart step 4's expected message changed with DEC-0008 and is recorded there.
- [x] T048 [P] Run the reviews the [review matrix](../../docs/policies/workflow.md#review-triggers) selects for this R2 change: [security review](../../.agents/skills/ballast-security-review/SKILL.md) (trust model, Git transport, credentials, F-002 shared environment), [engineering review](../../.agents/skills/ballast-engineering-review/SKILL.md) and [test review](../../.agents/skills/ballast-test-review/SKILL.md); record each under `specs/55-setup-trust/reviews/` and resolve findings, recording any spec-affecting discovery in `specs/55-setup-trust/decisions.md`. (depends on T045)
  - Evidence: specs/55-setup-trust/reviews/security.md, engineering.md, test.md and documentation.md, each with a Resolution section; every finding fixed test-first, documented or listed in decisions.md (DEC-0003 to DEC-0008) for the merge reviewer.
- [x] T049 Run Spec Kit converge and the [spec reconciliation](../../.agents/skills/ballast-spec-reconciliation/SKILL.md) for AC-001 to AC-027 against the implementation, tests and docs; resolve or record every gap. (depends on T046, T047, T048)
  - Evidence: specs/55-setup-trust/reviews/spec-reconciliation.md and convergence.md (CONVERGED); the constitution text is applied by the operator at merge (G-1).

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: none. T001 edits `contracts/setup-trust.md` (step order), a design artifact, as the agent-provisional F-003 resolution.
- **Foundational (Phase 2)**: T003 to T005 follow T002; T006 follows T002; blocks all user stories.
- **US1 (Phase 3)**: after Phase 2; holds all of `setup_trust.settle`, so US2 and US3 build on it.
- **US2 (Phase 4)**: implementation T024 needs T019 (the `tools/setup` wiring of US1); its tests only need the fixtures.
- **US3 (Phase 5)**: tests need only the fixtures; T030 needs US1 and US2's implementation.
- **US4 (Phase 6)**: tests need only the fixtures and launcher; T034 and T035 need US1 to US3's implementation.
- **US5 (Phase 7)**: writing needs only T001; T043 checks the docs against the implemented messages.
- **Polish (Phase 8)**: after every story.

### User Story Dependencies

- **US1 (P1)**: after Foundational; no other story.
- **US2 (P1)**: reuses US1's `settle` and setup wiring; independently testable through preparation.
- **US3 (P1)**: evidence for US1 and US2's refusals; independently testable through setup alone.
- **US4 (P1)**: evidence for US1's row 2 and 3 and the unchanged launcher; independently testable.
- **US5 (P2)**: documents; independent of code except T043.

### Within Each User Story

- Tests are written first and fail until the story's implementation lands.
- Same-file tasks are chained: `tests/test_setup.py` T011 → T022 → T023 → T031 → T044; `tests/test_setup_trust.py` T009 → T010 → T026 → T027 → T028 → T029 → T032; `tests/test_spec_workflow.py` T008 → T013 → T033; `tools/spec_workflow/setup_trust.py` T006 → T014 → T015 → T016 → T017; `tools/spec_workflow/launcher.py` T003 → T004 → T005 → T018; `tools/setup` T019 → T024.

### Parallel Opportunities

- Wave 2 runs the launcher writer, the new module skeleton, the doctor tests and the ADR together.
- After T036, the constitution, roadmap, README and policy edits (T038 to T041) run in parallel with all code work.
- Test authoring for US1 to US4 overlaps with `settle` implementation (T014 to T017).
- T046, T047 and T048 run in parallel at the end.

---

## Execution Wave DAG

Tasks grouped by dependency resolution. Tasks within the same wave can run in parallel.

```text
Wave 1 (no dependencies):
  T001  Decisions for F-003, F-005
  T002  Baseline fast gate

Wave 2:
  T003  launcher.record_baseline (depends on T002)
  T006 [P] setup_trust skeleton, shared URL and environment (depends on T002)
  T012 [P] [US1] doctor source tests (depends on T002)
  T036 [P] [US5] ADR-0015 (depends on T001)

Wave 3:
  T004  baseline_source, operator_baseline (depends on T003)
  T007  branch_sync delegates (depends on T006)
  T009  test_setup_trust fixtures (depends on T006)
  T037  [US5] ADR-0007/0011 notes (depends on T036)
  T038 [P] [US5] constitution 1.2.0 (depends on T036)
  T039 [P] [US5] roadmap, technical spec (depends on T036)
  T040 [P] [US5] README (depends on T036)
  T041 [P] [US5] workflow policy template (depends on T036)

Wave 4:
  T005  reviewed-repositories record (depends on T004)
  T010 [P] [US1] operator-baseline tests (depends on T009)
  T011 [P] [US1] setup records tests (depends on T009)
  T042  [US5] governance verification (depends on T037, T038, T039)

Wave 5:
  T008  RecordBaselineTests (depends on T005)
  T014  [US1] settle: verdict, rows 1-4, keep (depends on T001, T005, T006)
  T018  [US1] launcher _trust, status --json (depends on T005)
  T022  [US2] preparation tests AC-006, AC-007 (depends on T011)
  T026  [US3] local ineligible tests (depends on T010)

Wave 6:
  T013  [US1] trust provenance tests (depends on T008)
  T015  [US1] settle: rows 5-7 (depends on T014)
  T020 [P] [US1] doctor detail (depends on T018)
  T023  [US2] preparation tests AC-008, AC-009 (depends on T022)
  T027  [US3] worktree pointer tests (depends on T026)

Wave 7:
  T016  [US1] settle: rows 8a, 8b, 9 (depends on T015)
  T028  [US3] observation tests (depends on T027)
  T031  [US4] agent trace setup tests (depends on T023)
  T033  [US4] launcher unchanged, provenance tests (depends on T013)

Wave 8:
  T017  [US1] record, recheck, restore (depends on T016)
  T029  [US3] reviewed repository, AC-017 table (depends on T028)
  T044  cli/doctor never import setup_trust (depends on T031, T012)

Wave 9:
  T019  [US1] tools/setup main wiring (depends on T017)
  T032  [US4] agent trace eligibility tests (depends on T029)

Wave 10:
  T021  [US1] US1 green (depends on T010, T011, T012, T013, T017, T018, T019, T020)
  T024  [US2] tools/setup prepare wiring (depends on T019)

Wave 11:
  T025  [US2] US2 green (depends on T022, T023, T024)
  T030  [US3] US3 green (depends on T029, T017, T019, T024)
  T034  [US4] US4 green (depends on T031, T032, T033, T019, T024)
  T043  [US5] documentation review (depends on T040, T041, T036, T019, T024)

Wave 12:
  T035  [US4] AC-023 unchanged-tests verification (depends on T021, T025, T030, T034)

Wave 13:
  T045  fast gate (depends on T035, T042, T043, T044)

Wave 14:
  T046 [P] full local gate (depends on T045)
  T047 [P] end-to-end on scratch repository (depends on T045)
  T048 [P] security, engineering, test reviews (depends on T045)

Wave 15:
  T049  converge and spec reconciliation (depends on T046, T047, T048)
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1 and Phase 2.
2. Phase 3 (US1): `setup_trust.settle` with every condition, `ballast trust` provenance and reviewed record, setup wiring, doctor.
3. **Stop and validate**: T021; a clean clone of a reviewed repository is trusted by setup alone.

US1 alone is not shippable for this R2 change: US3 and US4 are the evidence that the safety boundary holds, and US5 records the superseded ADR clauses and the amended invariant. The PR carries all five stories.

### Incremental Delivery

1. Foundation → US1 (setup) → US2 (preparation) → US3 and US4 evidence → US5 documents → polish and reviews.
2. Commit after each task or logical group with a Conventional Commit message scoped `55`.

---

## Notes

- Acceptance criteria → tasks: AC-001, AC-002, AC-005 T011; AC-003 T012, T013; AC-004 T010; AC-006, AC-007 T022; AC-008, AC-009 T023; AC-010, AC-011, AC-012 T026; AC-013 T027; AC-014, AC-015 T028; AC-016, AC-017 T029; AC-018, AC-021 T031; AC-019, AC-020 T032; AC-022, AC-024 T033; AC-023 T035; AC-025, AC-026 T042; AC-027 T043; end-to-end confirmation of AC-001, AC-006, AC-007, AC-016 on real GitHub T047.
- Plan-review findings → tasks: F-001 T036, T037; F-002 T006, T007, T048; F-003 T001, T014, T032; F-004 T017; F-005 T001, T036, T040; F-006 T016, T028.
- Never weaken a failing test or edit an existing trust or refusal test (AC-023); a conflict with approved intent stops at a `decisions.md` entry.
