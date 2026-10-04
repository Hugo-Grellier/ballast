---

description: "Task list for the Autonomous run core (Issue #27)"
---

# Tasks: Autonomous run core

**Input**: Design documents from `specs/27-autonomous-core/`: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md)

**Prerequisites**: plan.md, spec.md (intent approved, see [intent.md](intent.md)), research.md, data-model.md, contracts/

**Risk**: R2. Human approval of these tasks and human merge approval are required. The work runs under the current human-gated workflow, not under the mode it introduces.

**Acceptance evidence**: Every behavior acceptance criterion (`AC-001`–`AC-025`) and success criterion (`SC-001`–`SC-007`) is cited by at least one test or verification task below. Tests are written first in each task and must fail before the implementation that satisfies them. Engine-driven, real-`bwrap` and real-systemd cases are skipped where the host lacks Spec Kit, user namespaces, systemd or Codex, as the existing suites do; the full local gate (T069) runs them. The GitHub path has no automated seam beyond a fake `gh`, so the operator pilot (T070) records manual evidence for it.

**Organization**: Tasks are grouped by user story. Most code lives in a few shared files (`autonomy.py`, `artifacts.py`, `run.py`, `agent.py`), so tasks that touch the same file are chained by explicit dependencies even when they belong to different stories; `[P]` is used only across different files.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel with other ready tasks (different files, dependencies satisfied)
- **[Story]**: User story the task belongs to (US1–US6)
- Test and verification tasks cite the criteria they prove, e.g. `[AC-001]`

## Path Conventions

Tools in `tools/`, shipped templates in `templates/`, tests in `tests/` (unittest, run with `uv run --no-project --python 3.13 --with pyyaml python -m unittest tests/test_*.py`). All workflow tools stay standard-library-only and run under `python3 -I -S`. New test modules:

- `tests/test_autonomy.py`: units of `tools/spec_workflow/autonomy.py`
- `tests/test_autonomous_artifacts.py`: `artifacts.py` recorders and mode-aware checks
- `tests/test_autonomous_run.py`: `run.py` and `agent.py` behavior with a fake `gh`, a temporary `XDG_STATE_HOME` and temporary Git repositories
- `tests/test_governance.py`: governance text assertions

`tests/test_spec_workflow.py` gets new cases only (workflow definitions and engine-driven `AutonomousEngineTests`); existing cases stay unmodified (SC-007).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create the new module, test scaffolding, extension skeleton and decision record.

- [x] T001 Create `tools/spec_workflow/autonomy.py` skeleton: module docstring, stdlib-only imports that work under `python3 -I -S`, and the constant vocabularies from [data-model.md](data-model.md) and the contracts — decision points, multi-entry points (`clarification`, `decision-resolution`, `specialist-review`), decision kinds, block categories, review kinds, severities, finding labels, dispositions, the refusal phrase prefixes from [contracts/cli.md](contracts/cli.md#refusals), wall-time range 1–1440 (default 240), step range 1–200 (default 30), never-authorized actions (`merge`, `release`, `deploy`, `mark ready`), the AC-007 wording regex `(?i)\b(human[- ]approved|approved by (the )?(human|operator|user))\b`, the hardened Git prefix `-c core.hooksPath=/dev/null -c core.fsmonitor=false`, and `run_dir(root, run_id)` built on `launcher.state_dir()`
- [x] T002 [P] Create test scaffolding in `tests/fixtures/autonomy/` (fake `gh` script that serves canned Issue, comment, sub-issue, PR-list and repo JSON from a directory named by an environment variable and records its argv; fake `git` argv recorder that delegates to the real `git`; a fake agent integration that writes given artifacts and drafts) and a reusable base class in `tests/test_autonomy.py` that creates a temporary `XDG_STATE_HOME`, a temporary Git repository on a feature branch with a bare `origin`, and puts the fakes on `PATH`, using the same import pattern the existing tests use for shared helpers
- [x] T003 [P] Create `templates/spec-kit/extensions/ballast/extension.yml` declaring the commands `speckit.ballast.decide`, `speckit.ballast.clarify`, `speckit.ballast.review` and `speckit.ballast.resolve`, mirroring the manifest format of an installed local extension (for example `.specify/extensions/intent/extension.yml`), and create the empty `templates/spec-kit/extensions/ballast/commands/`, `templates/spec-kit/workflows/autonomous/` and `templates/spec-kit/workflows/continue/` directories
- [x] T004 [P] Write `docs/adr/0004-autonomous-provisional-decisions.md` with status `Proposed`: the separate gate-less workflow instead of conditional gates (R-01), the operator-state hash-chained decision log with committed projections (R-05), publication by the trusted runner (R-11), continuation as a gate-only workflow (R-10), and bubblewrap confinement for Autonomous agent steps (R-02, D-7); link plan decisions D-1, D-3, D-6 and D-7
- [x] T005 [P] Add the `[checks]` table from [contracts/config.md](contracts/config.md#checks) to this repository's `ballast.toml` (the fast-gate commands, `timeout_minutes = 30`) and note in the PR evidence that the operator must re-run `ballast trust` because `ballast.toml` is a protected input Evidence (2026-10-04): `[checks]` added with the fast-gate commands and `timeout_minutes = 30`; `ballast trust` re-run by the coordinating agent under the operator's standing authority.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Operator-state records, policy, Git and confinement primitives, eligibility, the record renderer and the confined agent wrapper that every story needs.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete. Each task writes its failing tests in the named test file first, then implements.

- [x] T006 Write `RunRecordTests` in `tests/test_autonomy.py`, then implement the run record in `tools/spec_workflow/autonomy.py`: `run.json` fields and validation per [data-model.md](data-model.md#run-record-runjson), directory mode `0700`, atomic write (temporary file, `O_NOFOLLOW`, `os.replace`), strict read where a missing, malformed, symlinked or unknown-version file is a refusal, `run_id` pattern equal to the directory name, only the legal status transitions, `mode_history` with `start` only first and `lower` only from `autonomous` to `human-gated`, and a raise refused before any write [FR-002, FR-003] (depends on T001, T002)
- [x] T007 Write `HashChainTests` in `tests/test_autonomy.py`, then implement append and read for `decisions.jsonl` and `human-decisions.jsonl` in `tools/spec_workflow/autonomy.py`: sequential `PD-NNNN`/`HD-NNNN`, `prev` as the SHA-256 of the previous line's bytes (64 zeros first), a missing trailing newline or broken chain makes the log unreadable, `supersedes` must name an existing, not-yet-superseded ID, and lines are never rewritten [FR-013] (depends on T006)
- [x] T008 Write `BlockRecordTests` in `tests/test_autonomy.py`, then implement the block model in `tools/spec_workflow/autonomy.py`: `block.json` per [data-model.md](data-model.md#block-blockjson) with one current block replaced atomically and every earlier block appended to `blocks.jsonl`, `command` restricted to `ballast run continue RUN_ID ...`, `ballast run publish RUN_ID`, `ballast discard-runs` or `ballast run start ...`, and validation of an agent block draft (`decision`/`contradiction` only, at least two options, a `decision` block states why no safe reversible default exists) [FR-022] (depends on T007)
- [x] T009 Write `PolicyTests` in `tests/test_autonomy.py`, then implement parsing of `[autonomous]` and `[checks]` from `ballast.toml` with `tomllib` in `tools/spec_workflow/autonomy.py` per [contracts/config.md](contracts/config.md): `risk` intersected with R0–R2, other levels and unknown keys returned as `ignored [autonomous] <key>: cannot widen eligibility` warnings, never-authorized actions ignored with a warning, out-of-range limits refused, limit precedence operator > project > default with `source` recorded, `[checks] commands` non-empty and `timeout_minutes` 1–240 (default 30), and a missing or empty `[checks]` reported as a start refusal naming `[checks]` [FR-007, FR-020] (depends on T008)
- [x] T010 Write `GitHelperTests` in `tests/test_autonomy.py`, then implement in `tools/spec_workflow/autonomy.py` a single trusted Git runner that prefixes every call with the hardened flags, a tree digest (`git write-tree` of a private index after `git add --all`, excluding `ballast.toml`, `.ballast/`, `.specify/`, `.venv/`, with optional extra exclusions such as `specs/<f>/reviews/` and `specs/<f>/autonomous/drafts/`, and a variant limited to paths outside `specs/<f>/`), the snapshot of repository-local Git configuration (`--local`, `--worktree`, include targets) and of the hooks directory listing, and the scan for effective configuration values that carry a credential (`https://user:token@`, `http.*.extraheader`, `Authorization`, an in-checkout `credential.helper` store) or name an in-checkout program (`gpg.program`, `gpg.ssh.program`, `gpg.x509.program`, `core.sshCommand`, `credential.helper`, `core.askPass`, `include.path`, `includeIf.*.path`) (depends on T009)
- [x] T011 Write `ConfinementTests` in `tests/test_autonomy.py` (argv-builder cases always run; real-`bwrap` cases skipped without `bwrap` or user namespaces), then implement `confined_argv()` and `confinement_self_test()` in `tools/spec_workflow/autonomy.py` per [research R-02](research.md#r-02-where-the-mode-limits-and-eligibility-live): read-only host, writable worktree, protected inputs `--ro-bind` on top with the `SPECIFY_WRITABLE` paths pre-created and bound writable, `.git` read-only in a primary checkout, private `/tmp`, empty `--tmpfs` over `/run`, `/var/run` and `$XDG_RUNTIME_DIR`, `--unshare-pid --unshare-ipc --new-session --die-with-parent`, throwaway overlays for the agent CLI homes and `~/.cache`, a per-step copy of `~/.claude.json`, empty tmpfs over the listed credential directories, `/dev/null` over the listed credential files, and removal of secret-named environment variables except the running integration's own key. Real cases: writes to the state directory, the Git common directory (primary checkout and linked worktree), `~/.config` and outside the worktree fail; a `~/.claude` write does not persist; a confined `feature.json` write succeeds and a `.specify/workflows/` write fails; `systemd-run --user true` fails; `$XDG_RUNTIME_DIR` is empty; the parent's `/proc/<pid>/environ` is unreadable; `gh auth status` is not logged in; an authenticated `git ls-remote` fails; listed secret paths and variables are unreadable. The self-test fails closed when `bwrap` is missing or any probe succeeds [AC-016, SC-005] (depends on T010)
- [x] T012 Write `EligibilityTests` in `tests/test_autonomy.py` with the fake `gh`, then implement `check_eligibility()` in `tools/spec_workflow/autonomy.py` per [research R-03](research.md#r-03-eligibility-source-and-timing) and [contracts/cli.md](contracts/cli.md#refusals): open Issue, not labelled `epic`, no sub-issues, no open blocker, `ready-for-agent`, exactly one intake scope comment whose author association is OWNER, MEMBER or COLLABORATOR, `Risk:` and `Privileged actions before merge:` lines present, risk allowed by the narrowed policy, every declared privileged action authorized, no excluded boundary, feature number equal to the Issue, current branch not the default branch and no open PR for it, no credential-bearing Git configuration, confinement self-test passing; `gh` failure fails closed with `cannot check autonomous eligibility: <cause>`; the result stores reasons, privileged actions, the policy snapshot and ignored keys. Cases: an eligible R0, R1 and R2 Issue each accepted with its risk recorded; an Epic, sub-issues, an open blocker and a missing scope each refused with the scope-gate reason; a missing privileged-actions line refused; an unauthorized and an authorized privileged action; a narrowed risk refused; a widening key ignored with a warning; a token-bearing remote URL refused [AC-018, AC-019, AC-020, AC-021, FR-005, FR-006, FR-008] (depends on T011)
- [x] T013 Write `RecordRenderTests` in `tests/test_autonomy.py`, then implement `render_record(run, decisions, checks)` in `tools/spec_workflow/autonomy.py`: deterministic bytes for `specs/<f>/autonomous/record.md` with the sections of [contracts/pr-summary.md](contracts/pr-summary.md) minus the PR-only header (mode history, risk and limits, material provisional changes or `None`, the decision table in log order with superseded rows kept and `agent-provisional` in every row, reviews with `cross-provider: yes|no` and the reduced-independence line, open findings, checks), agent-written `summary` and `basis` quoted with HTML comments, `<!-- workflow-* -->` markers and `@mentions` neutralized [FR-014, FR-025] (depends on T012)
- [x] T014 [P] Write wrapper tests in `tests/test_autonomous_run.py`, then extend `tools/spec_workflow/agent.py` for Autonomous runs: read the run record and exit 2 when it is missing for an Autonomous workflow or its status is not `active`; re-run `confinement_self_test()` and launch the agent CLI (Claude and Codex) under `confined_argv()` inside the existing systemd scope; before the step move any file in `specs/<f>/autonomous/drafts/` aside into the operator run directory, and after the step list the drafts the step created with their SHA-256 in the protected `meta.json`; human-gated runs keep today's argv exactly (depends on T011)

**Checkpoint**: Operator records, policy, eligibility, confinement and the renderer are tested; story work can begin.

---

## Phase 3: User Story 1 - Run an eligible feature to a Draft PR unattended (Priority: P1) 🎯 MVP

**Goal**: `ballast run start --mode autonomous` runs `ballast-autonomous` from scope to final acceptance with no gate, records one provisional decision per gate, enforces every postcondition, and publishes one Draft PR.

**Independent Test**: In a scratch repository, start an Autonomous run on an eligible R1 Issue. It reaches a Draft PR without any prompt, and every gate of `ballast-feature` appears in `record.md` as a provisional decision (quickstart §2 and pilot step 1).

### Acceptance tests for User Story 1

- [x] T015 [P] [US1] Add `AutonomousWorkflowDefinitionTests` to `tests/test_spec_workflow.py`: `templates/spec-kit/workflows/autonomous/workflow.yml` parses, contains no `gate` step, its step IDs and order match the table in [contracts/workflow.md](contracts/workflow.md) (including `renew-intent` and `run-checks`), every `shell` step runs `python3 -I -S .ballast/spec_workflow/artifacts.py <check> --run {{ context.run_id }}` with no input interpolation, the review steps set `integration: "{{ inputs.review_integration }}"`, and `templates/spec-kit/workflows/feature/workflow.yml` is byte-identical to `main` [AC-001, SC-007]

### Implementation for User Story 1

- [x] T016 [US1] Write `templates/spec-kit/workflows/autonomous/workflow.yml` (`ballast-autonomous`) per [contracts/workflow.md](contracts/workflow.md#ballast-autonomous), with inputs `idea`, `feature_directory`, `integration` and `review_integration` only (depends on T003, T015)
- [x] T017 [P] [US1] Write `templates/spec-kit/extensions/ballast/commands/speckit.ballast.decide.md`: `args` names the point (`scope`, `intent`, `plan`, `tasks`, `final-acceptance`); read the named policies, skills and artifacts; write exactly `drafts/<point>.json` per [contracts/decision-draft.md](contracts/decision-draft.md), including `privileged_actions`, optional `risk` and `boundaries`; to stop, write `drafts/block.json` and print `RECONCILE_STATUS: BLOCKED_DECISION`; never edit `autonomous/record.md`, `intent.md` approval or provisional blocks, `.specify/`, `.ballast/` or `ballast.toml`; label gate text `agent-provisional` and never write "approved by" a human (depends on T003)
- [x] T018 [P] [US1] Write `templates/spec-kit/extensions/ballast/commands/speckit.ballast.clarify.md`: resolve each open clarification by adopting only a safe, reversible default recorded in `drafts/clarification-<n>.json` with `assumption.reversible: true`, remove every unresolved marker from `spec.md`, and block (never ask the operator) when no such default exists or when the Issue splits into several independent outcomes, recommending decomposition without creating Issues (depends on T003)
- [x] T019 [P] [US1] Write `templates/spec-kit/extensions/ballast/commands/speckit.ballast.review.md`: `args` is `plan`, `implementation` (engineering and test), `specialists` or `spec-reconciliation`; load the matching `ballast-*-review` and `ballast-spec-reconciliation` skill files; write narrative-only reports under `specs/<f>/reviews/<kind>.md` with no findings heading or severity tag, put every finding in the review draft, declare any further required kinds, and write `- Verdict:` in `reviews/convergence.md`; never edit anything outside `specs/<f>/reviews/` and drafts (depends on T003)
- [x] T020 [P] [US1] Write `templates/spec-kit/extensions/ballast/commands/speckit.ballast.resolve.md`: give each open implementation discovery in `decisions.md` an agent-provisional `## DEC-NNNN — Resolution` record in the form of [contracts/decision-draft.md](contracts/decision-draft.md#provisional-decision-resolution-in-decisionsmd-autonomous-only), mark material changes (product behavior, scope, data authority, security boundary, accepted architecture), write `drafts/decision-resolution-<n>.json`, and block when a resolution needs a code change (depends on T003)
- [x] T021 [US1] Write `RecordDecisionTests` in `tests/test_autonomous_artifacts.py`, then implement in `tools/spec_workflow/artifacts.py` the Autonomous preamble for every check run with `--run` (run record exists, `workflow == ballast-autonomous`, `status == active`, committed `record.md` equals `render_record()` or fail with "autonomous record was edited outside the recorder") and the generic `record-decision --point P` check: accept only drafts listed with a matching SHA-256 in the immediately preceding agent step's `meta.json` and refuse any other file in `drafts/`, validate every field rule of the decision draft contract (point match, lengths, one-line summary, evidence paths inside the checkout with no symlink or `..`, artifact hashed by the recorder, wording guard, workflow markers refused), ignore runner-owned fields with a recorded warning, fill `provider`, `step_id`, `role` and `at` from the runner, append the PD, re-render `record.md`, delete the draft. Cases include a planted draft refused, a forged human-approval phrase refused, an edited `record.md` failing the next check, and a failed check exiting non-zero [AC-002, AC-003, AC-007, FR-010, FR-011, FR-013] (depends on T013, T014)
- [x] T022 [US1] Write clarification tests in `tests/test_autonomous_artifacts.py`, then implement `record-decision --point clarification` in `tools/spec_workflow/artifacts.py`: zero drafts allowed, one PD per `assume` draft, `reversible: false` refused, and the unchanged `clarified-spec` check still rejects any unresolved marker [AC-005, FR-017] (depends on T021)
- [x] T023 [US1] Write intent tests in `tests/test_autonomous_artifacts.py`, then implement `record-provisional-intent` in `tools/spec_workflow/artifacts.py`: append the `intent` PD and write the `<!-- workflow-provisional: begin/end -->` block of [data-model.md](data-model.md#committed-projections) with `Provisional spec digest`; with `--renew`, when the spec digest differs from the current intent PD, append a superseding intent PD attributed to `runner`, marked material, referencing the resolutions that changed the spec and stating the renewed spec was not re-reviewed, otherwise do nothing; make `check_intent` in an Autonomous run accept only a provisional block whose digest equals both the current spec and its log entry [FR-012] (depends on T022)
- [x] T024 [US1] Write review-recorder tests in `tests/test_autonomous_artifacts.py`, then implement `record-decision` for `plan-review`, `implementation-review`, `specialist-review` and `spec-reconciliation` in `tools/spec_workflow/artifacts.py`: review entry validation per [data-model.md](data-model.md#review-entry), `cross_provider` and `author_provider` filled by the runner, required-kind coverage (security always, plus path triggers on the diff since the implementation baseline, declared R2 boundaries and reviewer-declared kinds; `none` refused), every `critical`/`high` finding records a `review-finding` block whatever its disposition, the findings section of each report rendered from the draft, a narrative carrying a findings heading or a severity tag refused, the tree digest taken before each reviewer step compared afterwards (excluding `reviews/` and `drafts/`), and the non-spec tree digest recorded at `record-implementation-review`. Cases: a same-provider review recorded as `cross_provider: false`; a high finding blocks; a reviewer source edit blocks [AC-004, FR-016, FR-019] (depends on T023)
- [x] T025 [US1] Write tests in `tests/test_autonomous_artifacts.py`, then make `check_decisions` and `check_convergence` mode-aware in `tools/spec_workflow/artifacts.py`: in an Autonomous run accept a resolution only when its `PD-NNNN` exists with `point: decision-resolution`; in a human-gated run an `agent-provisional` resolution does not count as resolved; pending tasks block convergence; `record-resolutions`, the recorder after `converge` and `record-reconciliation` refuse any change to the frozen non-spec tree digest (a source edit in `resolve-decisions` or `converge` blocks) [FR-018] (depends on T024)
- [x] T026 [US1] Write tests in `tests/test_autonomous_artifacts.py`, then implement the `autonomous-preflight` check in `tools/spec_workflow/artifacts.py`: launcher environment present, run record Autonomous, active and eligible, clean worktree, `HEAD` recorded in the run record, refusal when `.gitattributes` names a `filter`, `diff` or `merge` driver that the effective configuration defines, and the local Git configuration and hooks snapshots stored in the operator run directory (depends on T025)
- [x] T027 [US1] Write tests in `tests/test_autonomous_artifacts.py`, then implement the `run-checks` check in `tools/spec_workflow/artifacts.py`: run each `[checks] commands` entry with `sh -c` under `confined_argv()`, timeout capped at the run's remaining wall time, record command, exit status and duration with `runner` provenance in the operator run directory, block (`postcondition`) on a non-zero exit, a timeout or a missing table, run the protected-input hash check afterwards and record a `tamper` block on any difference, then record the tree digest in the run record [FR-015] (depends on T026)
- [x] T028 [US1] Write tests in `tests/test_autonomous_artifacts.py`, then implement `record-decision --point final-acceptance` in `tools/spec_workflow/artifacts.py`: require exactly one current PD for every point (several allowed for multi-entry points), re-hash every current PD's artifact, re-run `check_intent` (a stale intent is rejected), and require the tree digest recorded at `run-checks` to be unchanged (an edit by `decide-final` blocks) [SC-002, FR-009] (depends on T027)
- [x] T029 [US1] Write publisher tests in `tests/test_autonomy.py`, then implement `render_pr_body()` (header, sections of [contracts/pr-summary.md](contracts/pr-summary.md), staged path list, `run-checks` results then agent-reported checks, `CI results appear on this PR.`, `Refs #<issue>`) and `publish()` in `tools/spec_workflow/autonomy.py` per [research R-11](research.md#r-11-draft-pr-publication-fr-024fr-027): refuse the default branch and an existing PR; recompute the tree digest and refuse unless it equals the `run-checks` digest; stage with `git add --all` and refuse any staged path outside the changes since the recorded `HEAD`, any protected input or any file over 1 MiB; refuse when the local Git configuration or hooks snapshot changed, when a used filter driver is configured, or when an effective program, helper or include path points inside the checkout; commit with `--no-verify` and an `Autonomous-Run: <id>` trailer; `git push -u origin HEAD`; `gh pr create --draft --body-file`. Cases: a planted hook does not run; run-created artifacts from before `implementation-baseline` are staged; each refusal returns a `forge` or `postcondition` result [FR-024, FR-025] (depends on T013)
- [x] T030 [US1] Write start tests in `tests/test_autonomous_run.py`, then implement `ballast run start --mode autonomous` in `tools/spec_workflow/run.py` per [contracts/cli.md](contracts/cli.md#ballast-run-start): parse `--mode`, `--wall-time`, `--max-agent-steps` (the last two refused without `--mode autonomous`), require `-i issue=N` matching the feature directory, run `check_eligibility()` and print each refusal with exit 2 and the human-gated alternative, create the run record with `status=active`, the risk record, limits and deadline, choose `review_integration` (the other provider when its CLI is on `PATH`, otherwise the same with `cross_provider: false`), and start `ballast-autonomous` with only `idea`, `feature_directory`, `integration` and `review_integration` as inputs (depends on T012, T014, T029)
- [x] T031 [US1] Write tests in `tests/test_autonomous_run.py`, then implement end-of-run publication in `tools/spec_workflow/run.py`: on workflow completion set `completed`, re-check eligibility on the union of declared privileged actions, call `publish()`, set `published` or record a retryable `forge` block and set `stopped`; add `ballast run publish RUN_ID` for a `completed` run or a `stopped` run with a `forge` block, never resuming the workflow or running an agent; archive the operator run directory under `speckit-runs/<run>/autonomous/` alongside today's archive; exit codes per [contracts/cli.md](contracts/cli.md#exit-codes) [FR-024] (depends on T030)
- [x] T032 [P] [US1] Write tests in `tests/test_setup.py`, then extend `tools/setup` to install `ballast-autonomous` with `specify workflow add --dev` and the `ballast` extension with `specify extension add --dev`, add an `IGNORE_PROBES` entry for the new workflow path, and accept the `[autonomous]` and `[checks]` tables in `ballast.toml` without changing permission merging (depends on T016, T017, T018, T019, T020)
- [x] T033 [US1] Add `AutonomousEngineTests` to `tests/test_spec_workflow.py` (skipped without Spec Kit, systemd or `bwrap`): with the fake integration, an Autonomous run reaches `record-final` and the publish step with no TTY prompt and no `gate` in workflow state, `decisions.jsonl` has one current PD per point and `record.md` lists them, and a failing validator stops the run as in the human-gated workflow [AC-001, AC-002, AC-003, SC-001, SC-002] (depends on T015, T016, T028, T031, T032)

**Checkpoint**: An eligible feature runs unattended to a Draft PR in tests; the MVP is demonstrable with the pilot.

---

## Phase 4: User Story 2 - Review every provisional decision once, at merge (Priority: P1)

**Goal**: The Draft PR shows every provisional decision, clearly labelled, with no claim of human approval; review feedback continues the work human-gated without rewriting history.

**Independent Test**: For a completed Autonomous run, the PR decision count equals the log, each row is `agent-provisional` with evidence links, no text claims a human approval, and `ballast run continue --reason changes-requested` starts a human-gated continuation that keeps every earlier PD.

### Acceptance tests and implementation for User Story 2

- [x] T034 [US2] Write golden tests in `tests/test_autonomy.py` with fixtures `tests/fixtures/autonomy/record-*.md` and `pr-body-*.md` (cross-provider R1, single-provider R1, superseded decisions, material changes, open medium findings), asserting each row contains `agent-provisional`, the body never matches the wording regex outside the fixed header phrase, comments, markers and `@mentions` are neutralized, `Refs #N` is used and `Closes` is not, and the decision count equals the log; then implement the 60,000-character fallback in `tools/spec_workflow/autonomy.py` that keeps ID, point and summary per row and links `record.md` [AC-006, AC-007, SC-003, SC-006] (depends on T029)
- [x] T035 [P] [US2] Write tests in `tests/test_autonomous_artifacts.py` for intent binding and forgery, then fix `tools/spec_workflow/artifacts.py` if they fail: editing `spec.md` after `record-provisional-intent` makes the next check fail as stale; a forged `workflow-approval` block in `intent.md` is refused in an Autonomous run; a provisional block is refused in a human-gated run; human-gated `check_intent` behavior is unchanged [AC-008, FR-011, FR-012] (depends on T028)
- [x] T036 [US2] Write a publisher argv test in `tests/test_autonomy.py` with the fake `git` and `gh` recording every argv: only `add`, `commit`, `push -u origin HEAD` and `pr create --draft` are issued, and `merge`, `ready`, `--force`, `release` and `deploy` never appear [AC-010, FR-027] (depends on T034)
- [x] T037 [US2] Add `ContinueWorkflowDefinitionTests` to `tests/test_spec_workflow.py`: `templates/spec-kit/workflows/continue/workflow.yml` has no `command` step, its steps match [contracts/workflow.md](contracts/workflow.md#ballast-continue), and each gate's message, `show_file` and `on_reject: retry` equal those of `ballast-feature` [AC-009, AC-017] (depends on T033)
- [x] T038 [US2] Write `templates/spec-kit/workflows/continue/workflow.yml` (`ballast-continue`) per [contracts/workflow.md](contracts/workflow.md#ballast-continue) (depends on T037)
- [x] T039 [US2] Write tests in `tests/test_autonomous_artifacts.py`, then implement the `continue-preflight` check in `tools/spec_workflow/artifacts.py`: run record `ballast-continue`, effective mode `human-gated`, `continues` naming an existing `continued` Autonomous run, and the copied implementation baseline present (depends on T035)
- [x] T040 [US2] Write tests in `tests/test_autonomous_run.py`, then implement `ballast run continue RUN_ID --reason block-resolved|changes-requested --ref TEXT` in `tools/spec_workflow/run.py` per [contracts/cli.md](contracts/cli.md#ballast-run-continue-run_id---reason-block-resolvedchanges-requested---ref-text): valid only for an Autonomous run that is `stopped`, `completed` or `published` and not yet `continued`; append an HD (`block-resolution` or `merge-feedback`) and a `lower` mode change; mark the source run `continued`; create a new run with `continues=RUN_ID`, copy `implementation-baseline.json`, and start `ballast-continue`; `--mode` is refused; the earlier PDs still render in `record.md` [AC-009, FR-028, FR-023] (depends on T031, T038, T039)
- [x] T041 [P] [US2] Extend `tools/setup` and `tests/test_setup.py` to install `ballast-continue` with `specify workflow add --dev` (depends on T032, T038)
- [x] T042 [US2] Add an engine case to `tests/test_spec_workflow.py` (skipped like `EngineRunTests`): after a completed Autonomous run, `ballast run continue --reason changes-requested --ref URL` starts `ballast-continue`, whose first prompt is `approve-intent`, `human-decisions.jsonl` holds the HD, and `record.md` still lists every earlier PD as provisional [AC-009, AC-017] (depends on T037, T040, T041)

**Checkpoint**: The merge reviewer sees the complete provisional history, and feedback continues human-gated.

---

## Phase 5: User Story 3 - Stop with a precise block instead of guessing (Priority: P1)

**Goal**: Every unsafe situation ends the run with a categorized block, its options and a recovery command, before the next agent step; Autonomous resume is refused.

**Independent Test**: Force each blocking condition in the fake engine run; each stops before the next agent step with a named category and recovery command, and `ballast run resume` names #18.

### Acceptance tests and implementation for User Story 3

- [x] T043 [US3] Write tests in `tests/test_autonomous_run.py`, then implement block handling in `tools/spec_workflow/run.py`: when a step ends with `RECONCILE_STATUS: BLOCKED_DECISION`, validate `drafts/block.json` with the block model, add the `command`, move it into `block.json` in operator state, and confirm no PD exists for the blocked point; a draft with fewer than two options, a `decision` block without a no-safe-default reason, or a missing draft (wrapper exit 3) still records a `decision` block [AC-011, FR-021, FR-022] (depends on T040)
- [x] T044 [US3] Write limit tests in `tests/test_autonomous_run.py`, then implement limits in `tools/spec_workflow/agent.py` with `EXIT_LIMIT = 5`: refuse before spawn once the deadline has passed or `agent_steps >= max_agent_steps`, increment `agent_steps` before each step, bound the wait by the remaining time, then stop the scope, run the protected-file check and exit 5; the resulting `limit` block names the exhausted limit and the agent logs are kept [AC-012, FR-020] (depends on T043)
- [x] T045 [US3] Write tests in `tests/test_autonomous_run.py`, then implement in `tools/spec_workflow/run.py` the end-of-run category mapping of [research R-10](research.md#r-10-blocks-and-recovery-fr-021fr-023-ac-014) (exit 3 → `decision`, 4 → `tamper`, 5 → `limit`, an unavailable credential or permission reported by the publisher → `permission` (agents never report one, DEC-0005), failed `validate-*`/`record-*` → `postcondition`, `ineligible` or `review-finding` as the recorder reports, 130 → `interrupted`, publish failure → `forge`), printing of the block and its recovery command, `status=stopped`, and the refusal of `ballast run resume` for an effective-Autonomous run with the exact text naming #18; a bare `specify workflow resume` is stopped by the wrapper because the run is not `active`; tamper, unfinished-step and trust-mismatch refusals behave as in a human-gated run and Autonomous adds no way past them; a changed trusted input stays a launcher refusal with no block category (DEC-0002) [AC-013, AC-014, FR-023] (depends on T044)
- [x] T046 [US3] Add block-category engine cases to `tests/test_spec_workflow.py` (skipped like `EngineRunTests`), one per category (`decision`, `contradiction`, `review-finding` from a fake reviewer's `high` finding at `record-plan-review`, `limit` with `--wall-time 1`, `tamper`, `unfinished-step`, `postcondition`, `ineligible`, `forge`, `interrupted`, `permission` (a missing forge credential at publication)), each asserting that no later agent step started, the block names its reason, and the recovery command is printed; plus `test_trust`: a changed trusted input makes `ballast run continue` refuse at the launcher, with no new run and the stopped run's block unchanged (DEC-0002) [SC-004, AC-013, FR-021] (depends on T042, T045)
- [x] T046a [US3] Add an engine case to `tests/test_spec_workflow.py` (skipped like `EngineRunTests`): a fake clarify agent that reports several independent outcomes makes the run stop with a `decision` block recommending decomposition, with no provisional split and no Issue created [spec edge case] (depends on T018, T046)

**Checkpoint**: Every listed blocking condition stops the run with a precise, tested block.

---

## Phase 6: User Story 4 - Choose the mode and keep it out of agent reach (Priority: P2)

**Goal**: The mode is operator-chosen, stored outside agent reach, lowered only by a trusted action, and never raised.

**Independent Test**: Agent writes cannot change the effective mode; lowering through `ballast run continue` is recorded with its time and keeps earlier decisions; any raise is refused.

### Acceptance tests for User Story 4

- [x] T047 [US4] Write tests in `tests/test_autonomous_run.py`: `ballast run start` without `--mode` starts `ballast-feature` with an argv identical to today's; the mode, limits and eligibility are not workflow inputs and exist only in the state directory; fix `tools/spec_workflow/run.py` if a case fails [AC-015, FR-001] (depends on T045)
- [x] T048 [US4] Add confined-step engine cases to `tests/test_spec_workflow.py` (skipped without `bwrap`, systemd or Codex, as `CodexSandboxTests` is): through both integrations, an agent edit to `ballast.toml` is refused by the read-only bind and leaves it unchanged (`test_agent_writes_change_nothing_operator_side`), and behind a confinement hole the wrapper still fails the step as tampering with exit 4 (`AutonomousBlockEngineTests.test_tamper`) (DEC-0003); a write to `run.json` or `decisions.jsonl` fails; edits to `record.md` and to the `intent.md` provisional block fail the next validator; an agent-invoked `ballast run` fails; the effective mode, eligibility and limits are unchanged afterwards [AC-016, SC-005, FR-003] (depends on T046)
- [x] T049 [US4] Write tests in `tests/test_autonomous_run.py`: lowering through `ballast run continue` appends a `lower` mode change with its time and actor, the earlier PDs stay visibly provisional in `record.md`, `--mode` on `continue` and `resume` is refused, and starting `ballast run start --mode autonomous` for a feature with a paused human-gated run never alters that run's record; fix `tools/spec_workflow/run.py` if a case fails [AC-017, FR-003, FR-004] (depends on T047)

**Checkpoint**: Mode authority is verified against agent-side tampering.

---

## Phase 7: User Story 5 - Refuse ineligible features up front (Priority: P2)

**Goal**: Ineligible starts are refused before any agent step; eligibility is re-checked when risk or privileged actions grow; intake records the new scope line.

**Independent Test**: Autonomous starts for an Epic, a pre-merge privileged action and an excluded R2 each exit 2 with a reason and no agent directory; an eligible R0 starts.

### Acceptance tests and implementation for User Story 5

- [x] T050 [US5] Write end-to-end refusal tests in `tests/test_autonomous_run.py` through `run.py` with the fake `gh`: each refusal of [contracts/cli.md](contracts/cli.md#refusals) exits 2, prints its reason prefix and `Run it human-gated instead: ...`, prints widening warnings, and creates no `.specify/workflow-state/<run>/agents/` directory; a missing `bwrap` or failed self-test, a token-bearing remote URL, a dirty worktree and a missing `[checks]` table each refuse; an eligible R0 Issue starts with its risk recorded [AC-018, AC-019, AC-020, AC-021, FR-008] (depends on T049)
- [x] T051 [US5] Write tests in `tests/test_autonomous_artifacts.py`, then implement in `tools/spec_workflow/artifacts.py` the recorder's risk and privileged-action re-check: a draft `risk` above the recorded level raises it (history entry with the PD ID) and re-evaluates eligibility against the start-time policy snapshot, blocking `ineligible` when excluded; a lower level is ignored and noted; declared `boundaries` merge into the risk record; a growing `privileged_actions` list with an unauthorized action records an `ineligible` block, from a decision draft or a review entry [AC-022, FR-005, FR-006] (depends on T039)
- [x] T052 [US5] Write a test in `tests/test_autonomy.py`, then make `publish()` in `tools/spec_workflow/autonomy.py` refuse with an `ineligible` result when the union of privileged actions recorded during the run contains an unauthorized action [AC-022] (depends on T036)
- [x] T053 [P] [US5] Write tests in `tests/test_feature_intake.py`, then change `_scope_text` in `tools/feature_intake.py` to require a `Privileged actions before merge:` line only when the scope says `Autonomous: yes`; existing human-gated intake output is unchanged [FR-006]
- [x] T054 [P] [US5] Update `templates/skills/ballast-feature-intake/SKILL.md` with the `Privileged actions before merge:` scope line, the `Autonomous: yes` marker and the Autonomous start command `ballast run start --mode autonomous -i issue=N ...` (depends on T053)

**Checkpoint**: Eligibility is enforced at start, during the run and at publication.

---

## Phase 8: User Story 6 - Keep R2 safeguards when the R2 approval moves to merge (Priority: P2)

**Goal**: R2 Autonomous runs require their specialist reviews, block on high or critical findings, and show a prominent R2 notice at merge.

**Independent Test**: An R2 run touching a security boundary records a security review, an injected unresolved high finding blocks, and the PR lists the R2 boundaries and the provisional pre-change approval.

### Acceptance tests and implementation for User Story 6

- [x] T055 [US6] Write tests in `tests/test_autonomous_artifacts.py` for R2 coverage, then fix `tools/spec_workflow/artifacts.py` if they fail: an R2 run with declared boundaries requires security and architecture reviews; a missing required kind fails `record-implementation-review`; a run with no path trigger still requires security [AC-023, FR-016] (depends on T051)
- [x] T056 [US6] Write severity tests in `tests/test_autonomous_artifacts.py`, then fix `tools/spec_workflow/artifacts.py` if they fail: a `high` or `critical` finding blocks at every review point and at every risk level even when its disposition is `resolved`; `medium` with `accepted-provisionally` and no reason fails; `open` is refused above `low` [AC-024, FR-019] (depends on T055)
- [x] T057 [US6] Write golden tests in `tests/test_autonomy.py` with an R2 fixture, then implement the R2 notice in `tools/spec_workflow/autonomy.py`: `This is an R2 change. It was made without any prior human approval; the pre-change approval was agent-provisional (PD-NNNN).` followed by the deduplicated R2 boundaries, in both `record.md` and the PR body, and absent for R0 and R1 [AC-025, FR-026] (depends on T052)

**Checkpoint**: All six stories are independently verified.

---

## Phase 9: Governance, Polish & Cross-Cutting Concerns

**Purpose**: Amend governance text in the same change (FR-029, FR-030), run every gate, review, reconcile and collect PR evidence.

- [x] T058 [P] Amend `templates/policies/workflow.md`: add a "Supervision modes" section and update the R2 gate row so that, for an eligible Autonomous run, intermediate approvals are agent-provisional and the merge decision is the single human approval, including for R2; human-gated wording stays unchanged and is scoped to the human-gated mode [FR-029]
- [x] T059 [P] Amend `templates/policies/spec-kit-workflow.md`: the Autonomous lifecycle, new rows in "Workflow runner contract" (`ballast-autonomous`, `ballast-continue`, recorders, `run-checks`, publication), blocks and recovery through `ballast run continue`, and the refusal of Autonomous resume until #18 [FR-029]
- [x] T060 [P] Amend `templates/policies/model-routing.md` around line 51 for review integration selection and reduced independence in single-provider runs [FR-029]
- [x] T061 [P] Amend the risk sentence in `templates/AGENTS.md` and the R2 line in `templates/github/pull_request_template.md` for Autonomous runs; note in the release notes draft that both are copy-once [FR-029, FR-030]
- [x] T062 [P] Amend this repository's `AGENTS.md` and `CLAUDE.md` risk sentence, and scope the "before the change" rule in `docs/policies/project/workflow.md` to human-gated runs (plan decision D-5) [FR-029]
- [x] T063 [P] Write the complete amended constitution to `specs/27-autonomous-core/constitution-amendment.md` (`.specify/memory/constitution.md` is a protected input, so an agent edit fails the step as tampering; the operator applies the file before the PR, see T071a): add principle BL-INV-006 "A provisional decision is never human approval; only merging the PR that contains it accepts it", bump the version to 1.1.0, and state the reason and the compatibility impact for projects pinning earlier versions [FR-030]
- [x] T064 [P] Amend `specs/TECHNICAL-SPEC.md` §37 and §91 and, only where it states R2 approval timing, `specs/PRODUCT-SPEC.md` around line 1370 [FR-030]
- [x] T065 [P] Document the operator commands (`run start --mode autonomous`, `--wall-time`, `--max-agent-steps`, `run continue`, `run publish`), the `[autonomous]` and `[checks]` tables and the `bwrap` host prerequisite in `README.md`
- [x] T066 Write `tests/test_governance.py` asserting that `.specify/memory/constitution.md`, or `specs/27-autonomous-core/constitution-amendment.md` while it is not yet applied, has version 1.1.0 and contains BL-INV-006, and that `templates/policies/workflow.md` and `templates/policies/spec-kit-workflow.md` contain the Autonomous section [FR-029, FR-030] (depends on T058, T059, T063)
- [x] T067 Verify on the qualified host the plan-review mediums left to the implementer and record outcomes in the PR evidence (or a proposal in `specs/27-autonomous-core/decisions.md` if behavior diverges): Codex's own sandbox starts nested inside `bwrap` (it does not on the qualified host: DEC-0004, Codex roles fall back to Claude after a confined probe, `CodexNestedSandboxTests`); Spec Kit branch scripts work with `.git` read-only in both a primary checkout and a linked worktree; the Checks section notes ignored files or checks run on a clean export (depends on T048)
- [x] T067a Write tests in `tests/test_autonomous_run.py` (a Codex whose sandbox nests keeps cross-provider review and is probed once, confined with `--unshare-net`; one that does not nest routes every requested integration to Claude for both roles with `integration_fallback` recorded, printed and rendered; a Codex-only host is refused; no probe without Codex) and `tests/test_spec_workflow.py` (`CodexNestedSandboxTests`, real `codex` and `bwrap`, skipped unless the host restricts unprivileged user namespaces), then implement `autonomy.codex_sandbox_nests()` and the fallback in `tools/spec_workflow/run.py`; Codex's own sandbox is never disabled (DEC-0004) (depends on T067)
- [x] T068 Run the fast gate `uvx ruff check && uvx ruff format --check` and `uv run --no-project --python 3.13 --with pyyaml python -m unittest tests/test_*.py`; confirm existing cases pass unmodified and `templates/spec-kit/workflows/feature/workflow.yml` is unchanged against `main`; record commands and outcomes [SC-007] (depends on T004, T005, T050, T054, T056, T057, T065, T066, T067)
- [x] T069 Run the full local gate on the qualified Linux host (systemd user session, Codex CLI, Spec Kit CLI, `bwrap` with user namespaces) so engine, confinement and Codex cases run; record which cases ran and any skipped gate with its reason (depends on T068)
- [x] T069a Fix implementation review codex-1 F1 (critical): `confined_env()` clears `GH_CONFIG_DIR` and `XDG_CONFIG_HOME` (`autonomy.CREDENTIAL_LOCATIONS`) and `confined_argv()` hides the directories they name like `CREDENTIAL_DIRS`; the wrapper and `run-checks` build the `bwrap` argv from the operator's environment. Tests: `ConfinementTests.test_custom_gh_and_xdg_config_locations_are_hidden`, `RealConfinementTests.test_custom_gh_and_xdg_config_locations_unreadable` (`tests/test_autonomy.py`, real `bwrap`, directories under `/var/tmp`), `AutonomousConfinementEngineTests.test_custom_gh_config_dir_is_hidden_from_the_agent` (`tests/test_spec_workflow.py`, through the wrapper) [AC-016, SC-005]
- [x] T069b Fix review F2 (high): every operator-side Git command (`autonomy.git`, `artifacts.worktree_tree`, `ledger.implementation_tree`) empties each configured filter driver (`autonomy.filter_overrides`/`filter_flags`: `clean`, `smudge`, `process` empty, `required=false`), so an agent-added `.gitattributes` runs no program (`git write-tree` also runs filters). Test: `GitHelperTests.test_no_filter_runs_in_operator_git` (`tests/test_autonomy.py`, a `clean` and a `process` filter writing a sentinel) [AC-016]
- [x] T069c Fix review F3 (high): `run-checks` blocks (`postcondition`) before any check when code outside `specs/<f>/` differs from `frozen_tree` or no tree was frozen, takes the checked digest before the checks and blocks when a check changed it. Tests: `RunChecksTests.test_check_that_changes_reviewed_code_blocks`, `test_code_changed_after_review_blocks_before_checks` (`tests/test_autonomous_artifacts.py`) [FR-015]
- [x] T069d Fix review F4 (high): `record-provisional-intent --renew` no longer appends a runner-attributed intent decision; a spec changed after the intent decision records a `postcondition` block naming the resolutions (stale intent), and the continuation's `approve-intent` decides it (DEC-0006). Test: `ProvisionalIntentTests.test_renew_blocks_stale_intent_after_a_spec_change` (`tests/test_autonomous_artifacts.py`) [FR-010, FR-012, AC-008]
- [x] T069e Fix review F5 (medium): only an `approved` review verdict proceeds; `changes-requested`, `partial` or `failed` records a `review-finding` block even with no finding. Test: `ReviewRecorderTests.test_only_an_approved_verdict_proceeds` (`tests/test_autonomous_artifacts.py`) [FR-019, AC-004]
- [x] T069f Apply DEC-0007 after merging `origin/main` (#17): `run.py` runs `draft_pr.checkpoint` once per invocation after the Autonomous publication (`_checkpoint`), so it reuses the publisher's PR; the publisher runs `gh` and `git` through draft_pr's hardening (`_resolve`, `_command`, `_pinned_repository`), names `--repo`, `--base` and `--head`, refuses an `origin` other than the pinned repository, and adopts the one open PR the checkpoint opened for this feature instead of opening a second one; eligibility reads the repository from the same pin. Tests: `PublisherCheckpointTests.test_publication_then_checkpoint_leaves_one_pr`, `test_publish_retry_adopts_the_checkpoints_pr` (`tests/test_autonomous_run.py`); `PublisherTests.test_gh_starts_outside_the_checkout_and_names_the_pinned_repo`, `test_checkout_local_gh_and_git_never_run`, `test_gh_only_in_a_temp_root_is_refused`, `test_missing_pin_is_a_retryable_forge_refusal`, `test_origin_other_than_the_pinned_repository_is_refused`, `test_open_pr_of_another_feature_is_still_refused`, `test_adopts_the_checkpoints_pr_and_keeps_its_section`, `test_eligibility_needs_the_pin` (`tests/test_autonomy.py`) [FR-024]
- [x] T069g Fix pilot finding (run 61e739f9, step decide-scope, `EAI_AGAIN`): on systemd-resolved hosts `/etc/resolv.conf` links into `/run`, which the confinement replaces with a tmpfs, so no agent step could resolve the API host. `confined_argv()` now read-only binds back each of `/etc/resolv.conf`, `/etc/hosts`, `/etc/nsswitch.conf` and `/etc/gai.conf` whose resolved regular file a tmpfs hides, and nothing else of `/run` (no user bus, no runtime socket). Agent steps keep the host network namespace (only the Codex nesting probe uses `--unshare-net`), so the 127.0.0.53 stub stays reachable; agent CLIs need nothing else under `/run`. Tests: `ConfinementTests.test_resolver_files_hidden_by_a_tmpfs_are_bound_back`, `RealConfinementTests.test_dns_resolves_inside_when_it_does_outside` (real `bwrap`; skipped without DNS), both failing before the fix
- [x] T069h Fix commit-review findings on DEC-0007: adopt only a PR whose head is the pinned repository's own branch; push HEAD's commit to a URL rebuilt from `[github] repository` from a throwaway bare repository with an empty config that borrows the checkout's objects (`objects/info/alternates`), so no checkout config applies (`remote.*.pushurl`, `url.*.insteadOf`/`pushInsteadOf`, `include.path`, `core.sshCommand`, `credential.helper`, hooks); Git location and `GIT_CONFIG_*` variables dropped, trusted `PATH`, hooks and fsmonitor off; the operator's global configuration still applies. A repository-scope `insteadOf` on the pinned URL still fails the `origin` check. Tests (`tests/test_autonomy.py`, each failing under a mutation of its guard): `PublisherTests.test_pr_from_another_head_repository_is_never_adopted`, `test_head_repository_matches_case_insensitively`, `test_pushurl_never_redirects_the_push`, `test_local_push_rewrite_never_redirects_the_push`, `test_local_fetch_rewrite_is_refused_and_never_pushed_to`, `test_rewrite_key_with_spaces_never_redirects_the_push`, `test_included_config_never_redirects_the_push`, `test_local_ssh_command_and_credential_helper_never_run`, `test_hooks_path_pre_push_never_runs`; `test_argv_never_merges_or_forces` now expects the push of HEAD's commit to the pinned URL from a `--git-dir` outside the checkout
- [x] T069i Apply DEC-0008 (pilot finding: agents never saw the Issue body): `autonomy.render_issue_snapshot`/`write_issue_snapshot` and `check_eligibility` returning the Issue and its scope comment; `run.py` writes `.specify/workflow-state/issues/<N>.md` after eligibility and names it in the `specify` idea; `speckit.ballast.decide` and `speckit.ballast.clarify` read it. Human-gated workflow unchanged. Tests (each failing under a mutation of its guard): `IssueSnapshotTests.test_renders_body_labels_and_scope_as_untrusted_data`, `test_long_body_is_capped_with_a_marker`, `test_snapshot_never_follows_a_symlink` (`tests/test_autonomy.py`); `RunStartTests.test_start_writes_the_issue_snapshot_for_agents` (`tests/test_autonomous_run.py`); `AutonomousConfinementEngineTests.test_agents_read_the_issue_snapshot_but_cannot_write_it` (`tests/test_spec_workflow.py`, real `bwrap`: the fake decide-scope and specify agents read the acceptance criteria and fail to append to the snapshot; the run's `idea` names it) [FR-024, AC-001]
- [x] T069j Fix implementation review codex-2 publisher findings (DEC-0007 follow-up): read every created or adopted PR back through the hardened `gh api` and require an open draft to the default branch from the pinned repository's branch (`_read_pr`, `_pr_problem`, `_create_verified`); adoption re-reads the body just before editing, leaves a changed body (retryable `forge` block), and sets only its own `ballast:autonomous` section. Tests (`tests/test_autonomy.py`, each failing under a mutation of its guard): `PublisherTests.test_created_pr_is_read_back_and_verified`, `test_ready_or_retargeted_pr_is_never_adopted`, `test_concurrent_body_edit_is_never_overwritten`, `test_republish_replaces_only_its_own_section`, `test_adopts_the_checkpoints_pr_and_keeps_its_section`; `test_argv_never_merges_or_forces` also allows read-only `gh api` GETs [FR-024]
- [x] T069k Fix pilot finding (every Autonomous run blocked at `record-decision --point spec-reconciliation`): the recorder required `reviews/spec-reconciliation.md`, while `speckit.ballast.review` and the `convergence` check use `reviews/convergence.md` ([contracts/workflow.md](contracts/workflow.md) step 33). `artifacts.review_report()` maps `spec-reconciliation` to `convergence`; every other kind in the review command's table already wrote `reviews/<kind>.md`. The engine fixture had encoded the recorder's path, so the full-run engine test hid the mismatch; the fake reviewers now write the table's paths. Tests (each failing with the mapping removed): `FinalAcceptanceTests.test_review_reports_follow_the_review_command_table`, `test_spec_reconciliation_report_is_convergence` (`tests/test_autonomous_artifacts.py`); `AutonomousEngineTests.test_runs_to_a_draft_pr_without_a_prompt` (`tests/test_spec_workflow.py`, every step to publication)
- [ ] T070 Operator scratch-repository pilot per [quickstart.md §3](quickstart.md#3-scratch-repository-pilot-operator-before-merge), steps 1–5: eligible R1 to Draft PR with no prompt; refusals before any agent step; `decision` and `limit` blocks and the resume refusal; `continue --reason changes-requested`; R2 run with security review and R2 notice. Record run IDs, PR URLs and any skipped step as manual evidence, because the real GitHub path has no automated seam [AC-001, AC-006, AC-010, AC-014, AC-017, AC-019, AC-020, AC-021, AC-025, SC-001, SC-006] (depends on T069)
- [ ] T071 Run the required reviews, cross-provider where available, and store reports under `specs/27-autonomous-core/reviews/`: engineering and test, security (agent authority, trust model, `gh` and Git writes), documentation (public CLI, config, policy) and architecture (ADR 0004) (depends on T069)
- [x] T071a Operator (not an agent step): after final acceptance and before the PR, copy `specs/27-autonomous-core/constitution-amendment.md` over `.specify/memory/constitution.md`, delete the amendment file, rerun `tests/test_governance.py`, and run `ballast trust` [FR-030] (depends on T063, T066, T071) Evidence (2026-10-04): amendment copied over `.specify/memory/constitution.md` (BL-INV-006, version 1.1.0), amendment file deleted, `tests/test_governance.py` OK, `ballast trust` re-run; done by the coordinating agent under the operator's standing authority and the operator's explicit 'keep going until both are merged'.
- [ ] T072 Run Spec Kit converge and the spec reconciliation skill; resolve every open item in `specs/27-autonomous-core/decisions.md` with human resolution where required (depends on T070, T071)
- [ ] T073 After human review, set ADR `docs/adr/0004-autonomous-provisional-decisions.md` to `Accepted` (or revise it), and draft follow-up Issues F-1 (`.ballast/feature_intake.py` outside the trust baseline) and F-2 (#17, #18, #19, #21 consumers) for the operator to file (depends on T071)
- [ ] T074 Prepare the PR description: link #27 and the spec, state R2, list verification commands and outcomes from T068–T070, required reviews, the re-trust needed after `ballast.toml` changed, and a Conventional Commit title (depends on T072, T073)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on T001 and T002; blocks every story. `autonomy.py` tasks T006–T013 are a chain because they share one file.
- **US1 (Phase 3)**: Depends on Foundational. It is the MVP and the base for every other story, because the recorders, the start path and the publisher it builds are reused.
- **US2 (Phase 4)**: Depends on US1 (renderer, publisher, recorders, engine test harness).
- **US3 (Phase 5)**: Depends on US2's `continue` subcommand (T040), which is the only recovery path.
- **US4 (Phase 6)**: Depends on US3 (the block and resume behavior it verifies against).
- **US5 (Phase 7)**: Its eligibility core is foundational (T012); its end-to-end and re-check tasks depend on US1–US4 through shared files.
- **US6 (Phase 8)**: Depends on US5's recorder re-check (T051) and publisher re-check (T052).
- **Governance and Polish (Phase 9)**: T058–T065 have no code dependency and can start at once; gates, pilot, reviews and reconciliation run last.

### User Story Dependencies

```text
Foundational ─▶ US1 ─▶ US2 ─▶ US3 ─▶ US4 ─▶ US5 (T050)
                  │      │                    
                  │      └─▶ US5 (T051, T052) ─▶ US6
                  └─▶ governance tests ─▶ gates ─▶ pilot, reviews ─▶ reconciliation ─▶ PR
```

Stories are independently **testable** (each has its own acceptance tests and checkpoint) but not independently **buildable**: the shared files force the order above.

### Within Each Story

- Tests first, failing, then implementation in the same task.
- Workflow definitions before setup installation, setup before engine tests.
- Recorders before `record-final`; publisher before `run.py` publication.

---

## Execution Wave DAG

Each wave starts when all its tasks' dependencies are complete; tasks within a wave may run in parallel.

| Wave | Tasks | Notes |
| --- | --- | --- |
| 1 | T001, T002, T003, T004, T005, T015, T053, T058, T059, T060, T061, T062, T063, T064, T065 | Setup, workflow-definition test, intake, governance text |
| 2 | T006, T016, T017, T018, T019, T020, T054, T066 | Run record; workflow and commands; skill; governance test |
| 3 | T007, T032 | Hash-chained logs; setup installs |
| 4 | T008 | Block model |
| 5 | T009 | Policy and limits |
| 6 | T010 | Git helper and digests |
| 7 | T011 | Confinement |
| 8 | T012, T014 | Eligibility; confined agent wrapper |
| 9 | T013 | Record renderer |
| 10 | T021, T029 | Generic recorder; publisher |
| 11 | T022, T030, T034 | Clarification; `run start`; golden tests |
| 12 | T023, T031, T036 | Provisional intent; publication; argv test |
| 13 | T024, T052 | Review recorders; publish re-check |
| 14 | T025, T057 | Decisions and convergence; R2 notice |
| 15 | T026 | Autonomous preflight |
| 16 | T027 | `run-checks` |
| 17 | T028 | `record-final` |
| 18 | T033, T035 | Autonomous engine test; intent forgery tests |
| 19 | T037, T039 | Continue definition test; continue preflight |
| 20 | T038, T051 | Continue workflow; risk re-check |
| 21 | T040, T041, T055 | `run continue`; setup installs continue; R2 coverage |
| 22 | T042, T043, T056 | Continue engine case; block handling; severity |
| 23 | T044 | Limits |
| 24 | T045 | Category mapping and resume refusal |
| 25 | T046, T047 | Block-category engine cases; default-mode test |
| 26 | T046a, T048, T049 | Confined tamper cases; lowering tests |
| 27 | T050, T067, T067a | End-to-end refusals; host verification; Codex nested-sandbox fallback |
| 28 | T068 | Fast gate |
| 29 | T069 | Full local gate |
| 30 | T070, T071 | Pilot; reviews |
| 31 | T071a, T072, T073 | Reconciliation; ADR and follow-ups |
| 32 | T074 | PR evidence |

---

## Acceptance Coverage

| Criterion | Tasks |
| --- | --- |
| AC-001 | T015, T033, T070 |
| AC-002 | T021, T033 |
| AC-003 | T021, T033 |
| AC-004 | T024 |
| AC-005 | T022 |
| AC-006 | T034, T070 |
| AC-007 | T021, T034 |
| AC-008 | T035 |
| AC-009 | T037, T040, T042 |
| AC-010 | T036, T070 |
| AC-011 | T043 |
| AC-012 | T044, T046 |
| AC-013 | T045, T046 |
| AC-014 | T045, T070 |
| AC-015 | T047 |
| AC-016 | T011, T048 |
| AC-017 | T037, T042, T049, T070 |
| AC-018 – AC-021 | T012, T050, T070 |
| AC-022 | T051, T052 |
| AC-023 | T055 |
| AC-024 | T024, T046, T056 |
| AC-025 | T057, T070 |
| SC-001, SC-002 | T028, T033, T070 |
| SC-003, SC-006 | T034, T070 |
| SC-004 | T046, T046a |
| SC-005 | T011, T048 |
| SC-007 | T015, T068 |
| FR-029, FR-030 | T058–T066 |

---

## Parallel Example: Wave 1 and Wave 2

```text
# Wave 1: independent files
T001 autonomy.py skeleton        T002 test scaffolding        T003 extension skeleton
T004 ADR                         T005 ballast.toml [checks]   T015 workflow definition test
T053 feature_intake.py           T058–T065 governance text

# Wave 2: once T003 and T015 are done, the workflow and the four commands in parallel
T016 autonomous workflow.yml     T017 decide.md   T018 clarify.md   T019 review.md   T020 resolve.md
```

---

## Implementation Strategy

### MVP First (User Story 1)

1. Phases 1 and 2.
2. Phase 3 (US1) through T033.
3. **Stop and validate**: run the fast gate, then pilot step 1 in a scratch repository. A Draft PR with a complete `record.md` is the MVP.

### Incremental Delivery

1. US1: unattended run to a Draft PR.
2. US2: merge-review summary verified and human-gated continuation.
3. US3: precise blocks and the resume refusal.
4. US4 and US5: mode authority and eligibility verified end to end.
5. US6: R2 safeguards.
6. Governance, gates, pilot, reviews, reconciliation, PR.

All stories ship in one PR, because the governance amendment (FR-029, FR-030) and R2 merge approval cover the whole feature; the order above is the build and validation order.

---

## Notes

- `[P]` tasks touch different files and have no unmet dependency.
- Never weaken or edit an existing test in `tests/test_spec_workflow.py`; add new cases only (SC-007).
- `templates/spec-kit/workflows/feature/workflow.yml`, `tools/ballast`, `claude-settings.json`, `ledger.py` and the ledger schema stay unchanged.
- An implementation discovery that conflicts with the approved spec or plan stops at the conflict and goes to `specs/27-autonomous-core/decisions.md` for human resolution.
- Changing `ballast.toml` (T005) requires the operator to run `ballast trust`; only the operator runs it.
