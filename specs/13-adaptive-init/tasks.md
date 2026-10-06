---

description: "Task list for Adapt Ballast to blank and established repositories"
---

# Tasks: Adapt Ballast to blank and established repositories

**Input**: Design documents from `specs/13-adaptive-init/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md) (R1 to R17), [data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md), [reviews/plan.md](reviews/plan.md) (findings F-001 to F-007)

**Risk**: R2, Autonomous run. Every decision in this file is agent-provisional; merging the PR is the single human approval (BL-INV-006).

**Acceptance evidence**: Every behavior acceptance criterion AC-001 to AC-034 has a test task below that cites it. Tests run offline: `tests/test_init.py` runs `tools/init` in process with `tests/test_setup.py`'s `fakes()` patched onto the setup module init loads; `tests/test_ballast.py` covers the CLI bootstrap. SC-007 (fast gate, full local gate and the networked end-to-end scratch run recorded in the PR) is workflow-owned and listed in [quickstart.md](quickstart.md), not here.

**Workflow-owned steps**: No task here runs the full gate, the quickstart end-to-end run, reviews, converge or spec reconciliation.

**Plan review findings carried into tasks**: F-001 → T036; F-002 → T010, T040; F-003 → T018; F-004 → T006, T027; F-005 → T005, T048; F-006 → T021, T028; F-007 → T027, T048.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no unmet dependencies)
- **[Story]**: Which user story this task belongs to (US1 to US6)
- Test tasks cite the acceptance criterion IDs they prove.
- Most implementation lives in one new file, `tools/init`, and most tests in one new file, `tests/test_init.py`; tasks touching the same file are chained by dependencies so no two run at once.

## Path Conventions

Single project at the repository root: `tools/` (the CLI and standard tools), `templates/`, `tests/` (unittest), `docs/`, `specs/`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: The manifest declaration and the generic templates init renders from.

- [X] T001 [P] Add the `[init]` table with `supported = true` and the comment from [contracts/cli-init.md](contracts/cli-init.md) to `tools/cli.toml`; leave `[cli] minimum` unchanged (R3)
- [X] T002 [P] Create `templates/init/constitution.md`: a generic, stack-neutral project constitution with sections Core principles (project-owned vs installed files; specs and ADRs govern intent; executable evidence before acceptance; no secrets or local destinations in tracked files; Ballast's protected inputs and operator-only trust), Product (`{{description}}`, `{{description_source}}`), Stack and gates (`{{stack}}`, `{{stack_source}}`, `{{gates}}`), Governance and Amendment history (`{{date}}` on the ratification line only); no project names (FR-022, R15)
- [X] T003 [P] Create `templates/init/agents-section.md`: the Ballast section proposed for an existing `AGENTS.md`/`CLAUDE.md`, containing a relative link to `docs/policies/spec-kit-workflow.md` (the marker R10 uses to detect the section), the issue/spec workflow pointer, the policy table pointer and `ballast trust` as operator-only; no project names (FR-022)
- [X] T004 [P] Create `templates/init/testing.md`: the project testing addendum listing `{{gates}}` (each command with its evidence) and a line for inferred commands to confirm; no project names (FR-022)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The `tools/init` skeleton, its `check`/`inspect`/`plan` stages, the test harness and the CLI bootstrap that every story uses.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T005 Create `tools/init` (executable, same `#!/usr/bin/env python3` shebang and module docstring style as `tools/setup`, standard library only): `argparse` for `--project ROOT --ref REF [--description TEXT] [--stack python|node|rust|go|neutral]`; set `sys.dont_write_bytecode = True` **before** loading the sibling `tools/setup` and `tools/spec_workflow/launcher.py` with `importlib.machinery.SourceFileLoader` (F-005), exposing them as module attributes so tests can patch them; a `git(*args)` helper that always prefixes setup's `GIT` and runs with `stdin=subprocess.DEVNULL`; a `Stop(stage, cause, code)` exception (code 2 refusal, 1 failure); a stage runner that records `written` and planned-but-not-written paths; the stop report from [contracts/init-tool.md](contracts/init-tool.md) (`ballast init: stopped at STAGE: CAUSE`, `Written:`, `Not written:`, `Next: ACTION, then rerun \`ballast init\``) with every value passed through setup's `printable`; exit codes 0/1/2
- [X] T006 Implement stage `check` in `tools/init`: validate arguments and the ref (setup/launcher `REF` rule, no `..`); when `ballast.toml` exists, its pin (launcher `pinned_ref`) must equal `--ref`; `git rev-parse --show-toplevel` (error → no repository; toplevel ≠ root → refusal `inside the repository at X; run \`ballast init\` at its root`); refuse with `P is a symbolic link; init never writes through a link` when `.gitignore`, any parent of a path init plans to write, **or any entry of setup's `PARENTS`** is a link (F-004), so a linked `docs/policies` refuses here with the target untouched (depends on T005)
- [X] T007 Implement stage `inspect` in `tools/init`: the fixed evidence list of R6 read through directory descriptors with `O_NOFOLLOW` on every component (reuse setup's `_open_dir`), regular files only, `fstat` before reading, at most 256 KiB, UTF-8 only, at most 20 workflow files; `EvidenceItem(path, kind, status, reason)` and `DetectedValue(key, value, source, confidence)` records per [data-model.md](data-model.md); skip reasons `symbolic link`, `not a regular file`, `larger than 256 KiB`, `not UTF-8`, `parse error: ...`, `more than 20 workflows`; classify `blank` (no entry but `.git`) or `established`; nothing read is executed or passed to a subprocess (depends on T006)
- [X] T008 Implement stage `plan` in `tools/init`: the project profile and write plan of [data-model.md](data-model.md) (`create`, `ignore`, `proposal`, `git_init`); value sanitising (single line, control characters escaped, backtick refused, R15); the code renderer of `ballast.toml` per [contracts/generated-files.md](contracts/generated-files.md) — `[standard] ref`, `[checks]` with `# evidence: PATH:LINE` on active entries and commented `inferred` lines, the always-commented `[agents.permissions] extra_allow` block (`Bash(<command>*)`, marked inferred, AC-019), `[github]` or its explanatory comment, empty tables omitted, TOML strings escaped — parsed back with `tomllib` and checked with launcher `pinned_ref` before any write; a render error is a failure (1) (depends on T007)
- [X] T009 [P] Create `tests/test_init.py` harness: load `tools/init` as a module; scratch-directory fixtures; a context manager patching `tests/test_setup.py`'s `fakes()` onto the setup module init loaded; a subprocess/exec audit hook helper (as `tests/test_setup.py`'s `_audit`) that records program names; a tree snapshot helper (paths, digests, link targets, inodes); a fake-terminal helper for `input()`/`isatty`; a `post_trust(root)` helper that calls `launcher._trust` then asserts `launcher._refusal(root) is None`; an isolated operator state directory per test (depends on T005)
- [X] T010 [P] Add the `init` subcommand to `tools/ballast` per [contracts/cli-init.md](contracts/cli-init.md), dispatched in `main` before `command_standard`: `parse_known_args` for `--ref` only; root `Path.cwd()`; ref = `--ref` or `v{VERSION}` without `ballast.toml` (`lstat`), `read_pin` otherwise with a differing `--ref` refused (`ballast.toml pins PIN; init keeps the pin. To move it, run \`ballast preview REF\`, then edit the pin`); `REF` and `..` validation; `BALLAST_STANDARD_DIR` (existing notice) or `ensure_standard`; read the manifest's `[init] supported` as data (extend `manifest()` or add a sibling reader); refuse when it is not `true` — naming `--ref` with a release that has init or a CLI upgrade when there is no `ballast.toml`, and naming moving the pin (`ballast preview REF`, then a reviewed edit) when `ballast.toml` exists (F-002); refuse when `[cli] minimum` is above `VERSION`, naming `install_line` for that minimum; then `os.execv("/usr/bin/python3", ["/usr/bin/python3", "-IS", STANDARD/tools/init, "--project", ROOT, "--ref", REF, *rest])`; every refusal exits 2 before `execv` and writes nothing in the root (depends on T001)

**Checkpoint**: init can be invoked, refuses unsafe targets, reads evidence and renders a validated `ballast.toml` in memory.

---

## Phase 3: User Story 1 - A blank directory becomes a Ballast project in one command (Priority: P1) 🎯 MVP

**Goal**: An empty directory (or one with only `.git`) becomes a usable Ballast project with one `ballast init` and one `ballast trust`.

**Independent Test**: In a scratch empty directory, run init with `--description` and `--stack`, then trust; `launcher._refusal` returns `None`.

### Acceptance tests for User Story 1

- [X] T011 [US1] Add `BlankRepositoryTests` to `tests/test_init.py`: empty directory with `--description`/`--stack` flags produces `.git/`, `ballast.toml`, `.gitignore` holding setup's `GITIGNORE`, `.specify/memory/constitution.md`, `AGENTS.md`, `CLAUDE.md -> AGENTS.md` and setup `--check` current [AC-001]; a fake terminal with no flags shows exactly two prompts (description, stack) [AC-003, SC-002]; blank and `.git`-only fixtures: after init `_refusal` names the missing baseline, after `post_trust` it is `None` [AC-002] (depends on T009)
- [X] T012 [US1] Add `MaterialChoiceRefusalTests` to `tests/test_init.py`: no terminal, each of `--description` and `--stack` missing in turn → exit 2, message names the flag, tree snapshot byte-identical and no `.git` created; an invalid stack and a description with a backtick or over 200 characters are refused naming the rule [AC-004] (depends on T011)
- [X] T013 [P] [US1] Add `InitBootstrapTests` (default-ref part) to `tests/test_ballast.py`: without `--ref` the tool receives `--ref v{VERSION}`; `--ref` with `..` or invalid characters refused with exit 2; the fetch URL uses `REPOSITORY`; `execv` arguments are exactly `/usr/bin/python3 -IS STANDARD/tools/init --project ROOT --ref REF` plus the passed-through flags; `BALLAST_STANDARD_DIR` selects that directory's `tools/init` [AC-005] (depends on T010)

### Implementation for User Story 1

- [X] T014 [US1] Implement stage `choose` in `tools/init` (R5): flag value, else `input()` prompt when stdin and stdout are terminals and the repository is blank, else refusal `missing the product description; pass --description TEXT` / `missing the stack; pass --stack python|node|rust|go|neutral`; validate description (one line, 1 to 200 printable characters, no backtick) and stack; never prompt in an established repository (depends on T008)
- [X] T015 [US1] Implement stages `git-init` (`git init --template=` only when `check` found no repository) and `ignore`'s create path in `tools/init`: probe setup's `IGNORE_PROBES` with `git check-ignore -q --no-index`; when all hold change nothing; when `.gitignore` is absent create it with setup's `GITIGNORE` through `_open_dir` and `O_CREAT|O_EXCL|O_NOFOLLOW`; probe again (depends on T014)
- [X] T016 [US1] Implement the constitution and `AGENTS.md` renderers in `tools/init`: `{{name}}` replacement on `templates/init/constitution.md`; `templates/AGENTS.md` with the "starting point" paragraph removed and every `[UPPERCASE]` placeholder replaced from the table in [contracts/generated-files.md](contracts/generated-files.md) (evidence cited or `TO CONFIRM: ...`); fail as a defect when a placeholder is left unreplaced (depends on T015, T002)
- [X] T017 [US1] Implement stage `write` in `tools/init` (R9): exclusive creates in order `ballast.toml`, `.specify/memory/constitution.md`, `docs/policies/project/testing.md` (when planned), `AGENTS.md`, `CLAUDE.md`; parents opened with setup's `_open_dir(root, parts, create=True)`; files with `O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW`; `CLAUDE.md` as relative `symlinkat` to `AGENTS.md` only when neither exists; an existing path (including a dangling link) is kept and listed as kept; a link met during the write refuses (2), an OS error fails (1) (depends on T016)
- [X] T018 [US1] Implement stage `install` in `tools/init` (R11): `setup.Setup(root).main()` in process; catch exactly the exception set setup's own `cli` maps (`RefusedError` → 2, `StageFailedError`, `RuntimeError`, `ValueError`, `OSError` → 1) and stop with `stopped at install: install: <setup's message>` (F-003); setup keeps its prior installation (depends on T017)
- [X] T019 [US1] Implement the success form of stage `report` in `tools/init`: the header `ballast init: blank|established repository at ROOT (pin REF)`, `Written:`, `Kept:`, `Appended the Ballast ignore block to .gitignore` when it happened, `Review these protected inputs: ballast.toml, .specify/, .ballast/spec_workflow/`, `Next: review the files above, then run \`ballast trust\``; values through `printable` (depends on T018)

**Checkpoint**: The blank-directory path works end to end with setup faked; T011 to T013 pass.

---

## Phase 4: User Story 2 - An established repository keeps its own instructions, CI and policy (Priority: P1)

**Goal**: Existing tracked files stay byte-identical; only absent files are created; every other change is one ignored patch.

**Independent Test**: Scratch repository with `pyproject.toml`, CI running `pytest` and an `AGENTS.md`: init then trust; existing files byte-identical, patch holds the `AGENTS.md` section, preflight passes.

### Acceptance tests for User Story 2

- [X] T020 [US2] Add `EstablishedRepositoryTests` to `tests/test_init.py` with the Python fixture (`pyproject.toml`, `.github/workflows/ci.yml` running `pytest`, `Makefile` with `check:`, `AGENTS.md`, `docs/policies/project/security.md`): those files' digests equal before and after [AC-006, SC-003]; `.ballast/init/proposed.patch` holds the `AGENTS.md` section, `git apply --check` accepts it and the report names it [AC-007]; no `CLAUDE.md` created, and a variant with only a regular `CLAUDE.md` creates neither file and the patch targets `CLAUDE.md` [AC-011]; an existing `.gitignore` without the block becomes old content plus the block (one newline added only when missing) [AC-008]; `post_trust` passes with the patch not applied [AC-010, SC-001]; no file under `.github/` created and the report lists the optional templates and stack CI with how to add them [AC-012] (depends on T012)
- [X] T021 [US2] Add `IgnoreConflictTests` to `tests/test_init.py`: a nested `docs/.gitignore` containing `!policies/*.md` (corrected during implementation: `!.ballast/spec_workflow/` cannot conflict, because git never re-includes a path below the ignored `.ballast/`) → exit 1 at `ignore`, the report names the rule as `SOURCE:LINE:PATTERN`, the patch comments that line out under `# ballast init: un-ignores PATH:`, no installed entry and no setup journal exist, `ballast.toml` not written [AC-009, SC-003]; a rule in `.git/info/exclude` is named with no patch; an existing rule ignoring a project-owned path init would create (e.g. `ballast.toml`) gives `ignored-paths` `not-ready`, exit 1, a patch proposal and an unchanged rule (F-006) [AC-013] (depends on T020)

### Implementation for User Story 2

- [X] T022 [US2] Extend stage `ignore` in `tools/init` (R8): when probes fail and `.gitignore` exists without the exact block text, append it through an `O_WRONLY|O_APPEND|O_NOFOLLOW` descriptor (separating newline first when needed); probe again; on a still-failing probe find the deciding rule with `git check-ignore -v --no-index --non-matching PATH`, add a proposal commenting that line out when it lives in a `.gitignore` inside the root (otherwise name its source with no proposal), write the patch first, then stop with `installed paths are not ignored: PATH (rule SOURCE:LINE:PATTERN)` before `write` and `install` (depends on T019)
- [X] T023 [US2] Implement stage `patch` in `tools/init` (R10): one unified diff of every proposal with `difflib.unified_diff`, `a/`/`b/` prefixes, files in path order, `git apply`-able; write it to `.ballast/init/proposed.patch` through `_open_dir` only after `git check-ignore` confirms the path is ignored, otherwise print it in the report; rewrite it each run and remove it when there is nothing to propose; the report line `Proposed patch: PATH (FILE: reason, ...)`; make the `ignore` conflict stop reuse this writer (depends on T022)
- [X] T024 [US2] Implement the instruction-file proposal in `tools/init`: when `AGENTS.md` exists (or only a regular, non-link `CLAUDE.md`) and it has no link to `docs/policies/spec-kit-workflow.md`, propose appending `templates/init/agents-section.md`; when either file exists, create neither (AC-011) (depends on T023, T003)
- [X] T025 [US2] Add the optional-integrations line to stage `report` in `tools/init`: `Not written (optional): ...` listing `templates/github/` files (PR template, Dependabot, PR-title workflow) and stack CI with how to add them (README: Using the copy-once templates); never write them (FR-017) (depends on T024)

**Checkpoint**: Established repositories adopt without any change to existing tracked files beyond the appended ignore block.

---

## Phase 5: User Story 3 - Adoption keeps the trust boundary and the tracked/ignored split (Priority: P1)

**Goal**: Init never executes repository commands, never records trust, never commits or pushes, and keeps installed paths ignored and project-owned files tracked.

**Independent Test**: After init in both scratch repositories, installed paths are ignored, created project files are not, no baseline exists, no detected command ran, and no commit or remote exists.

### Acceptance tests for User Story 3

- [X] T026 [US3] Add `BoundaryTests` to `tests/test_init.py`: after every successful fixture each `IGNORE_PROBES` entry holds and `git check-ignore` rejects every created project-owned path [AC-013, SC-005]; no `trusted.json` in operator state, `_refusal` refuses, the report lists the protected inputs and `ballast trust` [AC-014]; `git rev-list --all` empty in a blank fixture, no remote, and an existing `.git/config` inode unchanged in the `.git`-only fixture [AC-018]; the generated `ballast.toml` parses with no `agents` table and every `extra_allow` line is commented and marked `inferred` [AC-019]; setup fakes failing `specify init` give exit 1 at `install` with setup's stage message and the prior installation (or none) kept, and a fake raising `OSError` is reported the same way (F-003) [AC-020] (depends on T021)
- [X] T027 [US3] Add `NoExecutionTests` to `tests/test_init.py`: with setup faked, the audit hook over init's own stages sees only `git` start; fixture `Makefile`, `package.json` scripts and CI commands write a marker if run, and the marker never appears (F-007 scope) [AC-015, SC-005]; repository config with `core.hooksPath`, `core.pager`, `core.fsmonitor` pointing at marker scripts plus a `post-checkout` hook leaves no marker [AC-016]; `.github` linked outside the root (target made unreadable) is skipped with reason `symbolic link` and nothing is read through it, and a linked `docs/policies` refuses in `check` with the target untouched (F-004) [AC-017] (depends on T026)

### Implementation for User Story 3

- [X] T028 [US3] Implement the project-owned ignore check in `tools/init` (R8, F-006): in stage `ignore`, after the block is in place, probe every planned created project-owned path with `git check-ignore -v --no-index`; when an existing rule ignores one, add a proposal commenting the rule out (when it lives in a `.gitignore` inside the root), never rewrite it, and record it so `ignored-paths` reports `not-ready` and init exits 1 after reporting (depends on T025)

**Checkpoint**: Every R2 boundary of the spec has a passing test.

---

## Phase 6: User Story 4 - The generated profile reflects evidence and marks what is inferred (Priority: P2)

**Goal**: Values with direct evidence cite it and are active; inferred values are marked and inactive.

**Independent Test**: CI step running `pytest` and an unlabelled `Makefile` `check` target: `pytest` is active citing the CI file; `make check` is commented and marked inferred.

### Acceptance tests for User Story 4

- [X] T029 [US4] Add `EvidenceTests` to `tests/test_init.py`: CI `run: pytest` and lines of a `run: |` block become active with `# evidence: PATH:LINE`; a `run:` with `${{ }}`, `$`, `&&`, `|` or a backtick is ignored; `package.json` `test` script becomes `<pm> run test` with the lockfile's manager [AC-021]; `Makefile` `check` is a commented `inferred` line [AC-022]; every active entry has an evidence comment [SC-006]; a repository with only `src/main.zig` gets stack `neutral` marked inferred [AC-024]; malformed `pyproject.toml`, `package.json` over 256 KiB and a non-UTF-8 workflow are each skipped with their reason and init completes [AC-025] (depends on T027)
- [X] T030 [US4] Add `GeneratedContentTests` to `tests/test_init.py`: the constitution and `AGENTS.md` carry the description's source or `TO CONFIRM` and no unreplaced `[UPPERCASE]` or `{{name}}` placeholder, and the placeholder table covers every placeholder in `templates/AGENTS.md` [AC-023]; `origin` as `https://github.com/O/R(.git)`, `git@github.com:O/R.git` and `ssh://git@github.com/O/R.git` yields `repository = "O/R"`, while a GitLab URL and no remote give the commented `[github]` and a report line saying how to add it [AC-026]; no direct check → no `docs/policies/project/testing.md`, and an existing one stays byte-identical [AC-027] (depends on T029)

### Implementation for User Story 4

- [X] T031 [US4] Implement manifest parsing in `tools/init` (R5, R6): `pyproject.toml`, `Cargo.toml` with `tomllib`, `package.json` with `json`, `go.mod` module line; lockfile/marker existence; stack detection (`python`, `node`, `rust`, `go`, else `neutral` inferred); established-repository description from `[project] description` / `description` / `[package] description` with its source, else `TO CONFIRM` (never asked) (depends on T028)
- [X] T032 [US4] Implement check detection in `tools/init` (R7): the CI line scanner for single-line `run:` and `run: |` blocks (no YAML library), the plain-command filter (`shlex` split; no `${{`, `$`, backtick, `;`, `|`, `&`, `<`, `>`, control character; ≤ 200 characters), the recognised-verifier list, `package.json` scripts `test`/`lint`/`check`/`typecheck`/`format:check` as `<pm> run <name>`, inferred `Makefile` targets `test`/`check`/`lint`, `[tool.pytest.ini_options]`/`[tool.ruff]` (prefixed `uv run` with `uv.lock`), `cargo test`, `go test ./...`, and the chosen stack's usual gate for a blank repository; direct wins over inferred, duplicates dropped in first-seen order (depends on T031)
- [X] T033 [US4] Implement the `origin` reader in `tools/init` (R13): `git remote get-url origin` through the config-safe helper, parse HTTPS, SCP-style SSH and `ssh://` GitHub forms, validate `OWNER/REPO` against `[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+`, else omit `[github]` and add the report line on how to set it (depends on T032)
- [X] T034 [US4] Fill evidence into generated files in `tools/init`: `docs/policies/project/testing.md` from `templates/init/testing.md` only when absent and at least one direct check exists; constitution `{{gates}}`/`{{stack_source}}`/`{{description_source}}` and `AGENTS.md` architecture, ADR, glossary, install-command and gate placeholders from detected values with citations, else `TO CONFIRM`; the report's `To confirm (inferred):` and `Skipped evidence:` lines (depends on T033, T004)

**Checkpoint**: Every generated value is either cited or marked inferred/to confirm.

---

## Phase 7: User Story 5 - Rerunning init is safe and reports the same readiness (Priority: P2)

**Goal**: A rerun changes no tracked file, keeps the pin and reports drift as a patch.

**Independent Test**: Run init twice in each scratch repository; the second run changes no tracked file and reports the same readiness.

### Acceptance tests for User Story 5

- [X] T035 [US5] Add `RerunTests` to `tests/test_init.py`: init twice on each completed fixture (blank, `.git`-only, established) leaves `git status --porcelain` and every tracked digest equal after the second run [AC-028, SC-004]; a drift fixture (new CI step after adoption) gets a patch appending a commented `# ballast init found: "CMD" (evidence: PATH:LINE)` line while `ballast.toml` stays unchanged, and an adopted `ballast.toml` without `[github]` plus a GitHub `origin` gets the table proposed in the patch [AC-029]; `ballast.toml` present with constitution and ignore block missing → both created, pin unchanged [AC-030]; a scratch copy of this repository's tracked files (`git ls-files`) changes no tracked file [AC-031] (depends on T030)
- [X] T036 [US5] In `RerunTests` in `tests/test_init.py`, define the "same report" of AC-028 as the `Readiness:` block, the `Review these protected inputs:` line and the `Next:` line, and assert those are equal between the first and second run (F-001); the `Written:`/`Kept:` lists are expected to differ (depends on T035)

### Implementation for User Story 5

- [X] T037 [US5] Implement rerun drift in `tools/init` (R14): with `ballast.toml` present keep the pin and every existing project-owned file; compute the fresh profile against the committed `ballast.toml` (parsed with `tomllib`); propose appending an absent `[checks]` or `[github]` table with evidence comments, or commented `# ballast init found: ...` lines for differing evidence; no proposal when nothing differs, so the patch is removed (depends on T034)
- [X] T038 [US5] Make the readiness block, protected-inputs line and `Next:` line of the report in `tools/init` deterministic across runs (stable ordering, no timestamps or run-specific paths) so a rerun on an adopted repository prints them identically (depends on T037)

**Checkpoint**: init doubles as a safe readiness check on adopted repositories.

---

## Phase 8: User Story 6 - The readiness report says what is ready and what to do next (Priority: P3)

**Goal**: The report states the five readiness checks and the exact next action; every stop names the stage, what was written and how to continue.

**Independent Test**: Inspect the report after init in each scratch repository and after forced failures.

### Acceptance tests for User Story 6

- [X] T039 [US6] Add `ReportTests` to `tests/test_init.py`: a completed run's report contains the `instructions`, `ignored-paths`, `pinned-version`, `trust-boundary` and `checks` lines with `ready|warning|not-ready` and a `Next:` line; a missing check program is a `warning`; an existing matching baseline gives next action `ballast run` [AC-032]; forced stops at `choose`, `ignore` and `install` each print `stopped at STAGE`, `Written:`, `Not written:` and `Next:` [AC-034] (depends on T036)
- [X] T040 [P] [US6] Extend `InitBootstrapTests` in `tests/test_ballast.py`: a fake standard whose `tools/cli.toml` lacks `[init]`, and one whose `[cli] minimum` exceeds `VERSION`, each exit 2 naming the remedy, leave the scratch root unchanged and never call `execv`; with an existing `ballast.toml` pinned to a version without `[init]`, the remedy names `ballast preview REF` and a pin edit, not `--ref` (F-002); a `--ref` differing from the pin is refused [AC-033] (depends on T013)

### Implementation for User Story 6

- [X] T041 [US6] Implement stage `verify` in `tools/init` (R12): `instructions` (entry point exists; `CLAUDE.md` resolves to `AGENTS.md` when created; relative Markdown links in the created file or Ballast section resolve inside the root after install; an existing file without the section is a `warning` naming the patch); `ignored-paths` (probes hold and no created project file is ignored, including T028's result); `pinned-version` (pin equals `--ref` and setup's status is `current`); `trust-boundary` (no baseline written; launcher `_refusal(root)` refuses, or a matching baseline is `ready` with next `ballast run`); `checks` (`shutil.which` or an existing relative path for each active command's program, without running it; an `extra_allow` that does not cover a check is a `warning`, as doctor's `checks-allowed`) (depends on T038)
- [X] T042 [US6] Print the `Readiness:` block and choose the `Next:` action in stage `report` of `tools/init`; exit 1 when any check is `not-ready`; ensure every `Stop` from `choose`, `ignore` and `install` reaches the stop report with the planned-but-not-written list (depends on T041)

**Checkpoint**: All user stories are independently functional.

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, the ADR, CLI messages and repository-wide invariants.

- [X] T043 [P] Write `docs/adr/0012-init-before-pin.md` (status proposed until the PR merges, agent-provisional): `init` is the only CLI command that runs before a pin; the CLI bootstraps a version declaring `[init] supported = true` and runs that version's `tools/init` from the fetched directory; the standard owns inspection, generation and installation; init creates only absent files, proposes other changes as an ignored patch, never executes detected commands, records trust, commits or pushes; extends ADR-0002 (FR-021, R16) (depends on T042)
- [X] T044 [P] Update `README.md`: adoption starts with `ballast init` (what it writes, asks, never does, the patch, and the `ballast trust` step); keep the manual steps as the fallback for pins without init (depends on T042)
- [X] T045 [P] Update `specs/TECHNICAL-SPEC.md`: the CLI command list gains `init`; the manifest section documents `[init] supported` (depends on T042)
- [X] T046 [P] Update the layout line of `AGENTS.md` to mention `templates/init/` (depends on T042)
- [X] T047 Update `tools/ballast` `USAGE`, the module docstring, the missing-or-unreadable `ballast.toml` messages for `setup`, `trust`, `run`, `ledger` and `intake`, and `PIN_REMEDY` to name `ballast init` first, then the manual pin; update the expected text in `tests/test_doctor.py` and any affected assertion in `tests/test_ballast.py` (depends on T040)
- [X] T048 [P] Correct the plan artifacts for review findings: scope the "no other program is started" sentence in `specs/13-adaptive-init/contracts/init-tool.md` to init's own stages, noting setup starts its own programs during `install` (F-007), and fix R11 in `specs/13-adaptive-init/research.md` to say init sets `sys.dont_write_bytecode` before loading setup and the launcher (F-005) (depends on T042)
- [X] T049 Add `InvariantTests` to `tests/test_init.py`: `tools/init` imports only modules in `sys.stdlib_module_names` (by `ast`) and the CLI runs it under `-IS` [FR-023]; `templates/init/*` contain no project, owner or repository name of this repository and no unknown placeholder [FR-022]; loading `tools/init` from a scratch copy of the standard leaves no `__pycache__` in it (F-005) (depends on T039, T048)
- [X] T050 Run the fast gate (`uvx ruff check && uvx ruff format --check` and `uv run --no-project --python 3.13 --with pyyaml python -m unittest tests/test_*.py`) and fix any finding in the files this feature touched (depends on T043, T044, T045, T046, T047, T049)
  - Evidence (host, Linux with a systemd user session, Codex and Spec Kit CLIs, after `git rebase origin/main` onto 11134f1): `uvx ruff check` → All checks passed; `uvx ruff format --check` → 356 files already formatted; `uv run --no-project --isolated --python 3.13 --with pyyaml python -m unittest tests/test_*.py` → `Ran 1233 tests in 1663.348s`, `OK`, none skipped.
  - Fixes: `tools/init` mode set to 100755; `InitBootstrapTests` moved from `~/.cache/ballast-tests` (`trusted_directory`) to the shared `outside_temp()` root like the other `tests/test_ballast.py` cases; a pinned `ballast.toml` over 256 KiB crashed `plan` with an uncaught `Skipped` traceback and now stops at `plan` with exit 1 and nothing written (`RerunTests.test_an_oversized_pin_file_stops_without_writing`, red before the fix); `EvidenceTests.test_checkout_text_is_escaped_in_the_report` pins the `printable` escaping of checkout text in the report.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies; all four tasks run in parallel.
- **Foundational (Phase 2)**: T005 → T006 → T007 → T008 (one file); T009 after T005; T010 after T001. Blocks every story.
- **User stories (Phases 3 to 8)**: start after Foundational. Because nearly all implementation is in `tools/init` and most tests in `tests/test_init.py`, the stories execute in priority order on those two files; tasks on other files (`tests/test_ballast.py`, templates, docs) run alongside.
- **Polish (Phase 9)**: after the stories it documents.

### User Story Dependencies

- **US1 (P1)**: after Foundational. The MVP.
- **US2 (P1)**: builds on US1's `ignore`, `write` and `report` stages (T019); independently testable with the established fixture.
- **US3 (P1)**: its tests prove boundaries implemented in Foundational, US1 and US2; adds the project-owned ignore check (T028).
- **US4 (P2)**: after US3 on `tools/init`; refines the evidence the earlier stories already render as `TO CONFIRM`.
- **US5 (P2)**: after US4 (drift compares the full evidence profile).
- **US6 (P3)**: after US5 (the readiness block must be rerun-stable). T040 depends only on T013.

### Within Each User Story

- Tests are written first against the harness (T009) and fail until the story's implementation lands.
- `tools/init` tasks are chained to avoid concurrent edits of one file.

---

## Execution Wave DAG

Each wave starts when every dependency of its tasks is done; tasks within a wave run in parallel.

| Wave | Tasks | Notes |
| --- | --- | --- |
| 1 | T001, T002, T003, T004, T005 | manifest, templates, `tools/init` skeleton |
| 2 | T006, T009, T010 | `check` stage; test harness; CLI bootstrap |
| 3 | T007, T011, T013 | `inspect`; US1 tests (two files) |
| 4 | T008, T012, T040 | `plan`; US1 refusal tests; CLI compatibility tests |
| 5 | T014, T020, T047 | `choose`; US2 tests; CLI messages |
| 6 | T015, T021 | `git-init`/`ignore`; US2 conflict tests |
| 7 | T016, T026 | renderers; US3 tests |
| 8 | T017, T027 | `write`; US3 no-execution tests |
| 9 | T018, T029 | `install`; US4 tests |
| 10 | T019, T030 | `report`; US4 content tests |
| 11 | T022, T035 | `ignore` append/conflict; US5 tests |
| 12 | T023, T036 | `patch`; US5 same-report test |
| 13 | T024, T039 | instruction proposal; US6 report tests |
| 14 | T025 | integrations line |
| 15 | T028 | project-owned ignore check |
| 16 | T031 | manifests and stack |
| 17 | T032 | check detection |
| 18 | T033 | `origin` reader |
| 19 | T034 | evidence in generated files |
| 20 | T037 | rerun drift |
| 21 | T038 | deterministic report |
| 22 | T041 | `verify` |
| 23 | T042 | readiness block and `Next:` |
| 24 | T043, T044, T045, T046, T048 | ADR, README, technical spec, layout line, artifact corrections |
| 25 | T049 | invariant tests |
| 26 | T050 | fast gate |

---

## Parallel Example: Phase 1 and Wave 2

```text
Task: "Add [init] supported = true to tools/cli.toml"
Task: "Create templates/init/constitution.md"
Task: "Create templates/init/agents-section.md"
Task: "Create templates/init/testing.md"
Task: "Create tools/init skeleton"

# after T001 and T005:
Task: "Implement stage check in tools/init"
Task: "Create tests/test_init.py harness"
Task: "Add the init subcommand to tools/ballast"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1 and Phase 2.
2. Phase 3 (US1): a blank directory adopts with one init and one trust.
3. Stop and validate T011 to T013.

### Incremental Delivery

1. US1 (blank) → US2 (established, patch) → US3 (boundary proofs and the project-owned ignore check): the three P1 stories make adoption safe for both repository kinds.
2. US4 (evidence quality) → US5 (reruns) → US6 (full readiness report).
3. Polish: ADR-0012, README, technical spec, CLI messages, invariant tests, fast gate.

---

## Notes

- Every decision here is agent-provisional; the PR merge is the human approval.
- Never weaken a failing test; a conflict with the spec goes to `decisions.md`.
- Commit after each task or logical group.
