---

description: "Task list for Chat mode"
---

# Tasks: Chat mode

**Input**: Design documents from `specs/20-chat-mode/`: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md) (R1–R15), [data-model.md](data-model.md), [contracts/cli.md](contracts/cli.md), [contracts/phase-graph.md](contracts/phase-graph.md), [contracts/step-runner.md](contracts/step-runner.md), [contracts/run-record.md](contracts/run-record.md), [contracts/pr-evidence.md](contracts/pr-evidence.md), [quickstart.md](quickstart.md), [reviews/plan.md](reviews/plan.md) (findings F-001–F-004)

**Prerequisites**: plan.md (R2; agent-provisional PD-0005 in Autonomous run `2cb9c5c5`, decisions D-1–D-7), spec.md (agent-provisional intent PD-0003). The merge decision is the single human approval.

**Acceptance evidence**: Every acceptance criterion `AC-001`–`AC-022` has at least one deterministic test task (see [AC traceability](#acceptance-criteria-traceability)). The four plan-review findings each have a task: F-001 (T002, T041), F-002 (T014, T042), F-003 (T002, T050), F-004 (T002, T050). Pilot checks P-1–P-5 and quickstart scenarios 1–7 (T075) add manual evidence that needs a real interactive `claude`/`codex` TUI and a real GitHub remote; they replace no test.

**Organization**: Tasks are grouped by user story. US1, US2 and US3 are P1; US4 and US5 are P2. Story labels follow the spec's numbering.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel: a file no other task in the same wave touches, and no unfinished dependency
- **[Story]**: US1–US5 from spec.md
- Test tasks cite the acceptance criteria (`AC-NNN`), requirements (`FR-NNN`), success criteria (`SC-NNN`), decisions (`D-N`) and review findings (`F-NNN`) they prove
- Tests are written first and must fail before the implementation task that depends on them

## Conventions used by every task

- **Modules**: the new trusted module is `tools/spec_workflow/chat.py`, standard library only, imported by `run.py` at startup, runnable under `python3 -I -S`, and refusing to run as `__main__`. It reuses, and does not copy, `autonomy.run_dir`, `read_log`, `append_log`, `tree_digest`, `filter_flags`, `confined_env`, `confined_argv`, `confinement_self_test`, `codex_sandbox_nests`, `neutralize`, `MAX_BODY`, `publish`; `agent.FORBIDDEN`, `CONFINED_ALLOW`, `CONFINED_DENY`, `permission_args`, `_open_log`, `_containment`, `_stop_descendants`, `_protected_state`, `_mark_tampered`; `launcher.stop_scope`, `launcher.BASES`; `artifacts.Feature`, `spec_digest`, `check_*`, `record_intent`, `run_checks`; `branch_sync.synchronize`; `draft_pr.checkpoint`.
- **Unchanged**: headless `agent.py` argv, `claude-settings.json`, `tools/ballast`, `tools/setup`, the constitution and every `templates/spec-kit/workflows/*/workflow.yml` (verified by T072).
- **Wording**: refusal texts, printed lines and PR section headings are copied verbatim from the contracts; do not paraphrase.
- **Test harness** (T006): `ChatCase` in `tests/test_chat_mode.py`, extending `AutonomyCase` from `tests/test_autonomy.py`. A temporary `XDG_STATE_HOME`, a bare "GitHub" remote and a checkout with a trusted baseline; fake `gh`, `git` (passthrough with an argv log), `systemd-run` (records the unit, execs the command, answers stop/confirm from a state file) and `bwrap` (records argv, execs after `--`) in the trusted program directory, reusing `tests/fixtures/autonomy/` fakes where they exist; fake `claude` and `codex` that are copies of `tests/fixtures/chat/fake_tui.py`. Tests that need a real `bwrap`, systemd user session or agent CLI skip when unavailable, as `RealConfinementTests` does.
- **"Before any agent"**: asserted by the fake TUI's run report being absent, no `start` entry in `steps.jsonl`, and no `in-progress` marker.
- Run tests with `uv run --no-project --python 3.13 --with pyyaml python -m unittest tests/test_chat_mode.py tests/test_autonomy.py tests/test_spec_workflow.py tests/test_agent_run_ledger.py tests/test_branch_sync.py tests/test_draft_pr.py tests/test_autonomous_run.py tests/test_governance.py`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Record the architecture decision, settle the plan-review clarifications, and create the module, settings file, fake agent and harness.

- [X] T001 [P] Draft ADR-0009 "Chat mode: operator-driven steps" in `docs/adr/0009-chat-mode-operator-driven-steps.md` with status `Proposed`, covering plan.md § Proposed architecture decisions: Ballast drives Chat runs one invocation per action outside the Spec Kit engine (R1, D-1); interactive steps under bwrap behind a wrapper-owned pty without `--new-session` (R3, R3a, D-2, D-3); every Chat `step` is an invocation that runs branch synchronization (extends ADR-0005's list, not its rule); digest-bound human approvals for every gate in operator state (R11, D-4); mode switches and linked runs (R12, D-5); the Autonomous publisher also publishes Chat runs (extends ADR-0004, D-6); dead-wrapper recovery through `discard-runs` (R10, D-7). State that it is agent-provisional and accepted only by the merge.
- [X] T002 [P] Amend the contracts for the plan-review findings in `specs/20-chat-mode/data-model.md` and `specs/20-chat-mode/contracts/step-runner.md`. [F-001] In data-model.md's opening paragraph, replace "No agent step can write it ... bwrap hides it" with the per-driver bound: interactive Chat steps run under bwrap, which hides operator state; headless steps of a run switched to human-gated (D-5) are bound only by the headless permission model (Claude `acceptEdits` with no prompts and the narrow Bash allow list, Codex `workspace-write` with no extra writable roots), the same bound the human-gated intent registration under `state_dir/approvals` relies on today; the hash chain detects a broken or edited log but does not authenticate the writer. [F-003] In step-runner.md lifecycle step 2, choose this rule: the late close stores `tree_after` = the current tree manifest, sets `last_manifest`, and records `late_close: true` and `attribution: "uncertain"`; every change since `tree_before` is attributed to the step (so it is subject to the step's write-scope check), because attributing agent edits to the operator would hide them behind operator authority. [F-004] In the same row, state that a late close records `protected_compared: false` because the step-7 snapshot lived only in the dead wrapper's memory, and that protection then rests on bwrap's read-only binds (interactive driver) and on the launcher baseline over `launcher.BASES` at the next invocation; note that `autonomy.PROTECTED` covers all of `.ballast` while `BASES` covers only `.ballast/spec_workflow`. Add `late_close`, `attribution` and `protected_compared` to the `steps.jsonl` close fields in data-model.md.
- [X] T003 [P] Create `tools/spec_workflow/claude-chat-settings.json` per contracts/step-runner.md § Interactive argv: every `allow` and `deny` rule of `claude-settings.json`, plus `Edit(./**)` and `Write(./**)` in `allow`, `permissions.disableBypassPermissionsMode: "disable"` and `permissions.disableAutoMode: "disable"`.
- [X] T004 [P] Create the `tools/spec_workflow/chat.py` skeleton: module docstring stating the trust boundary (operator-side only, called by `run.py` behind the launcher, never by an agent); a `__main__` guard that prints a refusal and exits 2 (FR-001); constants `PHASES` (the nine phases with their `ballast-feature` step IDs, command names, write scopes), `REVIEW_KINDS` (kind → entry check, report path, skill), `GATES` (gate → `ballast-feature` gate ID, artifact, digest rule), `VERDICTS`, `OUTCOMES` (`completed`, `failed`, `interrupted`, `tampered`), `EVENT_KINDS` (`check`, `project-checks`, `review`, `out-of-step-change`, `refusal`, `sync`), `ESCAPE = b"\x1d\x1d"`; function stubs raising `NotImplementedError`: `start`, `run_step`, `summary`, `approve`, `reject`, `resolve`, `checks`, `change_mode`, `continue_run`, `publish_section`.
- [X] T005 [P] Create the fake interactive agent `tests/fixtures/chat/fake_tui.py`: a stdlib script that reads `scenario.json` next to its own file and writes `report.json` there with its argv, the environment keys, `os.isatty` for fds 0–2, `os.ttyname(0)`, its controlling terminal (`/dev/tty` open result), its open file descriptors (`/proc/self/fd` targets) and its session ID. Scenario actions, run in order: `write PATH TEXT`, `append PATH TEXT`, `print TEXT`, `read_line` (block until a line arrives on stdin), `try_write PATH` (record success or `errno`), `run ARGV` (record exit and output), `sleep SECONDS`, `ignore SIGHUP`, `exit CODE`.
- [X] T006 Create the harness in `tests/test_chat_mode.py` (depends on T004, T005): `ChatCase` per Conventions, with helpers `ballast(*args, tty=False, keys=b"", timeout=...)` (runs the launcher → `run.py` in a subprocess; under `pty.fork` when `tty=True`, writing `keys` and returning exit status, output and the terminal attributes before and after), `scenario(actions)`, `fake_report()`, `record(run)` (parsed `run.json`, `steps.jsonl`, `events.jsonl`, `human-decisions.jsonl` through `autonomy.read_log`), `raw(run, name)` (bytes of a record file), `ledger(run)`, `edit(path, text)`, `advance_base(files)`, `trust()`, `valid_spec()`, `valid_plan()`, `valid_tasks()` (artifact text that passes the `artifacts.py` checks). Add one smoke test that builds a `ChatCase` checkout.

**Checkpoint**: `chat.py`, the settings file, the fake agent and the harness import; `uvx ruff check` passes.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The operator record for Chat, the ledger `mode` field, the interactive confinement parameter, Chat-aware artifact checks, the Chat event log and manifests, the phase graph, the launcher refusal text and `run.py` dispatch. Every user story needs all of them.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T007 [P] Write Chat record tests in `tests/test_autonomy.py` class `ChatRecordTests`: `MODES` contains `chat` and `WORKFLOWS` contains `ballast-chat`; `new_run`/`validate_run` accept a `ballast-chat` record with the data-model fields (`integration`, `review_integration`, `cross_provider`, `continues`, `start_head`, `baseline`, `active_step`, `last_manifest`) and without `risk`, `eligibility` or `limits`, which stay required for `ballast-autonomous`; malformed `active_step` or `baseline` is refused; `_validate_mode_history` and `change_mode` allow only `start`, `lower` (`autonomous → human-gated`, `autonomous → chat`) and `switch` (`chat ⇄ human-gated`), refuse any move to `autonomous` after `start` with the "never raised" text, and require `by: operator`, `at`, `reason`, `decision_id`; `HUMAN_DECISION_KINDS` gains `gate-approval`, `gate-rejection`, `decision-resolution` with the data-model extra fields validated; `TRANSITIONS` allows `completed → active` and `published → active` for `ballast-chat` only. Existing record tests are unchanged. [FR-002, FR-020, FR-022, AC-018, AC-021, SC-007]
- [X] T008 Implement the Chat record in `tools/spec_workflow/autonomy.py` (depends on T007): `MODES`, `WORKFLOWS`, the `ballast-chat` branch of `new_run`/`validate_run`, mode-history `switch` and `lower → chat` rules in `_validate_mode_history` and `change_mode`, the new human-decision kinds and their field validation, and the `ballast-chat` status transitions.
- [X] T009 Write confinement tests in `tests/test_autonomy.py` class `ConfinementTests` (same file as T007; run after it): `confined_argv(...)` with the default arguments still contains `--new-session` for every existing caller (headless, Autonomous, the self-test, `codex_sandbox_nests`); `interactive_pty=True` is the only way to omit it; `readonly_extra=(".claude", ".codex")` adds `--ro-bind` for each path that exists and nothing for one that does not; a `readonly_extra` path outside the root is refused. [D-3, R3a, AC-003]
- [X] T010 Add `interactive_pty=False` and `readonly_extra=()` to `autonomy.confined_argv` in `tools/spec_workflow/autonomy.py` (depends on T008, T009).
- [X] T011 [P] Write ledger tests in `tests/test_agent_run_ledger.py`: a `run` event accepts an optional `mode` in `human-gated`, `autonomous`, `chat`; `status: mode-changed` requires `mode`; an unknown mode is rejected; a stream without `mode` is still valid; `_semantic_problems` accepts the Chat event order of contracts/run-record.md (one `run started`, step completions after starts, `gate` matched to a completed gate step entry, `mode-changed` anywhere after start); `schema_version` stays 1. [AC-014, FR-013, SC-007]
- [X] T012 Implement the `mode` field and the `mode-changed` status in `tools/spec_workflow/ledger.py` (depends on T011).
- [X] T013 [P] Document the `mode` field and the `mode-changed` status in `tools/spec_workflow/ledger-schema.md`, with the compatibility note that the change is additive (depends on T012).
- [X] T014 [P] Write Chat artifact tests in `tests/test_spec_workflow.py` class `ChatArtifactTests`: a `Feature` built from a `ballast-chat` operator record (`artifacts.Feature.from_operator_run` or the equivalent constructor) has the record's feature and run; `check_intent` on it requires the registered human approval block at the current spec digest and refuses an agent-provisional block, an unregistered human block and a stale digest (unlike the `check_provisional_intent` route an Autonomous `Feature` takes) [F-002, FR-003, AC-009]; `record_intent` on a Chat `Feature` removes an agent-provisional block and registers the human block [F-002, BL-INV-006]; the Chat decisions rule fails a `DEC-NNNN — Resolution` without a current `decision-resolution` human decision, passes with one at the resolution's normalized-text digest, and fails again after the resolution text changes [AC-008, AC-009]; the mode-neutral `run_checks` core runs `[checks] commands` with no wall-time limit and no frozen-tree prerequisite, returns results with `provenance: "runner"` and the tree digest, and reports `unavailable` when there is no `[checks]` table. Existing artifact tests are unchanged.
- [X] T015 Implement the Chat routes in `tools/spec_workflow/artifacts.py` (depends on T008, T014): the operator-record `Feature` constructor; `check_intent` routing a Chat `Feature` to the registered-approval check; `record_intent` removing the provisional block for a Chat `Feature`; the Chat decisions rule reading `human-decisions.jsonl`; the mode-neutral `run_checks` core with the Autonomous entry point calling it unchanged.
- [X] T016 Write record-layer tests in `tests/test_chat_mode.py` (depends on T006): `chat` creates `run.json`, `steps.jsonl`, `events.jsonl`, `human-decisions.jsonl` and `manifests/` under `autonomy.run_dir`, mode `0600` files in a `0700` directory; `events.jsonl` is hash-chained with `E-NNNN` IDs and read through `autonomy.read_log`, and an edited line makes the next read fail; a `check` event's `detail` is cut at 2,000 characters; the tree manifest maps every tracked and unignored file outside `.git` to its `hash-object --no-filters` digest, with a filter driver, a hook and `core.fsmonitor` in `.git/config` each pointing at a marker program that never runs; manifests are content-addressed and deduplicated; the out-of-step diff lists sorted paths up to 500 then a count, and the HD IDs whose bound digests no longer match; the per-run lock is non-blocking and a second holder is told who holds it. [FR-002, FR-010, FR-011]
- [X] T017 Implement the record layer in `tools/spec_workflow/chat.py` (depends on T004, T008, T016): run creation and loading, `append_event`, `append_step`, `append_human`, the manifest builder with `autonomy.filter_flags`, `out_of_step(run)`, `_Lock(run)` on `runs/<run>/lock` with `fcntl.flock(LOCK_EX | LOCK_NB)`.
- [X] T018 Write phase-graph tests in `tests/test_chat_mode.py` (depends on T006): for each phase of contracts/phase-graph.md, it is allowed exactly when its entry condition passes, with the cumulative upstream checks (`plan` re-verifies `intent`, `tasks` re-verifies `plan`, ...); a refused phase names its first failing check and that evaluation's `E-NNNN`; every evaluation appends a `check` event with `purpose: entry`; an earlier phase can be re-run whenever its entry passes; each gate's precondition matches the Gates table; each gate's digest follows data-model § Gate digest binding (`spec_digest` for intent, normalized text for plan, tasks and convergence, `tree_digest` excluding `specs/<f>/reviews/` for implementation and final, `"<N>\n<feature>"` for scope); an approval is current only while its digest matches; a rejection keeps the gate closed until a later approval at a current digest; a failed postcondition blocks every dependent phase until a later passing run of the same check, and the failed event stays in `events.jsonl`; the result is identical whatever the run's effective mode; `allowed_actions` lists phases, gates, `checks`, `publish`, `mode` in the contract's order. [AC-002, AC-004, AC-019, FR-007, FR-010, FR-022]
- [X] T019 Implement the phase graph in `tools/spec_workflow/chat.py` (depends on T015, T017, T018): `entry(run, phase, kind=None)`, `gate_precondition(run, gate)`, `gate_digest(run, gate)`, `approval_state(run, gate)` (`current`, `stale`, `rejected`, `pending`), `allowed_actions(run)`, each recording its evaluations.
- [X] T020 Write the launcher refusal-text test in `tests/test_spec_workflow.py` class `TrustedLauncherTests` (same file as T014; run after it): when the `in-progress` marker holds `ballast-agent-<run>-<step>.scope`, `_refusal` returns the contracts/step-runner.md § Launcher refusal text naming the run and step; any other content keeps today's text; both still refuse. [AC-013, FR-012]
- [X] T021 Change only the unfinished-step refusal text in `tools/spec_workflow/launcher.py` `_refusal` (depends on T020).
- [X] T022 Write dispatch tests in `tests/test_chat_mode.py` (depends on T006): `run.py --help` lists `start --mode chat`, `step`, `status`, `approve`, `reject`, `resolve`, `checks`, `mode`, `continue --mode chat` and `publish` for Chat runs; each new subcommand with an unknown run ID exits 2; `start --mode chat` with `--wall-time` or `--max-agent-steps` is refused; `python3 -I -S tools/spec_workflow/chat.py` exits 2 without touching any state; a Chat subcommand invoked by importing `run.py` without the launcher's environment is refused as other `run.py` paths are. [FR-001]
- [X] T023 Wire the dispatch in `tools/spec_workflow/run.py` (depends on T004, T021, T022): import `chat` at startup inside the baseline, parse the new subcommands and options, extend the usage text, and dispatch to the `chat` stubs.

**Checkpoint**: the Chat record, ledger field, confinement parameter, Chat artifact routes, event log, phase graph and dispatch exist; existing tests pass unchanged.

---

## Phase 3: User Story 1 - Work through a feature one conversational step at a time (Priority: P1) 🎯 MVP

**Goal**: An operator starts a Chat run through the launcher, runs phases interactively under headless-equivalent confinement, inspects and edits between steps, and every step is checked and recorded.

**Independent Test**: Quickstart scenario 1 (T030 automates it with the fake TUI): start, approve scope, step `specify`, edit `spec.md`, step `clarify`, approve intent, step `plan`. The record lists both steps with agent identity and postconditions, the out-of-step edit and the human intent approval; the feature directory holds only the headless artifact set.

### Acceptance tests for User Story 1

- [X] T024 [US1] Write `start --mode chat` tests in `tests/test_chat_mode.py` (depends on T006): a valid start creates the record (`workflow: ballast-chat`, `mode_history[0] = {mode: chat, action: start}`), runs `branch_sync.synchronize` with `starting=True` and pins the branch, archives `run/workflow.yml` (the trusted `ballast-feature` definition) and `run/chat.json`, appends the ledger `run` event with `mode: chat`, prints the handoff summary, runs the Draft PR checkpoint, and starts no agent; the stored `idea` becomes the `specify` prompt, `Issue #N` without one. Each of the five preflight conditions (changed trust baseline, tamper marker, `in-progress` marker, changed protected input, blocked synchronization) refuses the start before any agent with the same reason and exit status as a headless `start`; a blocked synchronization leaves a record with no steps and prints the `BLOCKED_UPSTREAM_SYNC` line. Refused: no or two `feature_directory` inputs; a failed `confinement_self_test`; Codex when `codex_sandbox_nests` fails, naming `claude` as the other integration [edge "integration cannot run confined"]; another Chat run in the checkout with an active step. [AC-001, FR-001, FR-004, SC-002]
- [X] T025 [US1] Write step entry and confinement tests in `tests/test_chat_mode.py` (depends on T006): `step RUN plan` before intent is approved is refused naming `intent`, records a `check` and a `refusal`, and starts no agent [AC-002, edge "step not allowed yet"]; `--kind` is required for `review` and refused for other phases. Claude argv inside the fake bwrap and scope is exactly contracts/step-runner.md § Interactive argv (`--permission-mode dontAsk --setting-sources project --strict-mcp-config --settings .ballast/spec_workflow/claude-chat-settings.json`, the `CONFINED_ALLOW`/`CONFINED_DENY` lists, `--model` only when given); Codex argv is `--sandbox workspace-write --ask-for-approval never` with network off and no writable roots; a token containing a `FORBIDDEN` marker (in `-i model=` or the idea) is refused before launch; bwrap has no `--new-session`, binds `.claude` and `.codex` read-only, and the environment is `confined_env` plus `PYTHONPYCACHEPREFIX` with `guard/git` first on `PATH`; the chat settings `deny` ⊇ and `allow` ⊇ `claude-settings.json`'s, and both disable flags are set. Real-bwrap variant (skipped without bwrap): the fake TUI's `try_write` on `ballast.toml`, `.ballast/`, the operator state directory, `.git/config` and `.claude/settings.json` all fail, and its `run ["systemd-run", "--user", ...]` fails. [AC-003, FR-005, D-2, edge "permission the step does not allow"]
- [X] T026 [US1] Write terminal tests in `tests/test_chat_mode.py` (depends on T006): in a `tty=True` step the fake TUI reports fds 0–2 as TTYs, its controlling terminal is the step's pty (not the harness terminal), it holds no descriptor to the harness terminal, and its session differs from the wrapper's [R3a test 1, D-3]; a window-size change on the harness terminal reaches the fake as the same size; the harness terminal's attributes after the step equal those before, on normal exit, after `SIGTERM` to the wrapper and after the fake crashes; output the fake prints appears on the harness terminal and in `stdout.log`; `step` without a TTY in `chat` mode is refused with "Chat steps need a terminal; use `ballast run mode RUN human-gated` for headless steps". [AC-003, FR-005]
- [X] T027 [US1] Write step-close tests in `tests/test_chat_mode.py` (depends on T006): the fake writes a valid spec and exits 0 → outcome `completed`, `postcondition` lists the `E-NNNN` of the `spec` check, `steps.jsonl` has the `start` and `close` entries with phase, `driver: interactive`, integration, model (`unreported` without `--model`), `role: author`, `tree_before`, `tree_after`, and the ledger has `step` started/completed with the `ballast-feature` step ID and a `snapshot`; the fake writes an invalid spec → `failed`, exit 1, and `clarify` is refused until a later `specify` passes, with the failure still in `events.jsonl`; the scope is confirmed stopped before the first postcondition `check` event (fake `systemd-run` log order) [FR-009]; the fake `systemd-run` cannot confirm the stop → `scope_stopped: false`, `in-progress` kept, exit 4, no postcondition run; the fake writes `ballast.toml` (fake bwrap) → `tampered`, `BALLAST_TAMPERED` names it, exit 4; a `specify` step that writes `tools/x.py` → `failed` with `write_scope_violations: ["tools/x.py"]` [FR-008]; the operator sends `Ctrl-]` `Ctrl-]` while the fake is in `sleep` → the fake is stopped, the scope confirmed gone, then the postcondition runs, outcome `interrupted` [edge "ends a step while the agent is still writing"]; `stdout.log` and `meta.json` (with the contract's keys, `argv[0]` reduced to the program name) are under `.specify/workflow-state/<run>/agents/<step>/`, and replacing that directory with a symlink after the step starts does not redirect the writes. [AC-004, FR-008, FR-009, FR-010, FR-017]
- [X] T028 [US1] Write `status` tests in `tests/test_chat_mode.py` (depends on T006): from a fixture record with completed and failed steps, a failed check, current, stale, rejected and pending gates, an open `DEC-NNNN` proposal and an out-of-step change, `status` prints the seven data-model § Handoff summary sections in order, matching a golden text; it runs no agent and no `ls-remote` (fake `git` log); it writes nothing except an `out-of-step-change` event when the tree differs from `last_manifest`; on a `ballast-autonomous` run it shows the record and points to `continue --mode chat`. [AC-005, FR-019]
- [X] T029 [US1] Write out-of-step tests in `tests/test_chat_mode.py` (depends on T006): after a step, edit `spec.md` in the shell → the next invocation appends one `out-of-step-change` with `actor: operator`, the path, `from_manifest`/`to_manifest` and the intent approval's HD in `stale`; the next `step` runs branch synchronization again (a new `sync` event) before the agent; editing `ballast.toml` between steps makes the launcher refuse the next `step` until `ballast trust` [edge "protected input between steps"]; re-running `specify` after `approve plan` makes the intent and plan approvals stale, and `status` shows them stale with the change that did it [edge "re-runs an earlier step"]. [AC-006, FR-004, FR-011]
- [X] T030 [US1] Write the US1 end-to-end test in `tests/test_chat_mode.py` (depends on T006): quickstart scenario 1 with the fake TUI (`approve` typed through the pty): start, `step specify` refused naming `scope`, `approve scope`, `step specify`, edit `spec.md`, `step clarify`, `approve intent`, `step plan`. The record has the three steps with agent identity and postconditions, one out-of-step change, and a `gate-approval` for intent bound to `spec_digest`; `intent.md` carries the registered human block; `specs/<f>/` contains only files a headless run produces (no Chat-only artifact); every `step` entry is preceded by a passing `sync` event. [AC-001–AC-006, FR-008, SC-001]

### Implementation for User Story 1

- [X] T031 [P] [US1] Add a `rerun` text parameter to `branch_sync.synchronize` and its recovery lines in `tools/spec_workflow/branch_sync.py`, with tests in `tests/test_branch_sync.py`: the default output is byte-identical to today's; a Chat caller's block prints `ballast run step RUN PHASE` instead of `ballast run resume`. [R5]
- [X] T032 [P] [US1] Make `draft_pr` feature identification fall back to the operator run record, then the branch pin, when no engine `inputs.json` exists, in `tools/spec_workflow/draft_pr.py`, with tests in `tests/test_draft_pr.py` class `IdentityTests`: a Chat run's checkpoint resolves its feature; an engine run is resolved as today. [R14]
- [X] T033 [US1] Implement `agent.run_interactive()` in `tools/spec_workflow/agent.py` (depends on T003, T010, T026): the interactive Claude and Codex argv builders with the `FORBIDDEN` refusal; the shared containment helpers reused from `main()` (scope, subreaper, `guard/git`, `PYTHONPYCACHEPREFIX`); `os.openpty`, a child that calls `setsid()`, `TIOCSCTTY` on the slave, duplicates it onto fds 0–2, closes every other descriptor and executes `systemd-run ... bwrap (confined_argv(..., interactive_pty=True, readonly_extra=(".claude", ".codex"))) ... agent`; raw mode on the operator terminal restored in `finally` and in signal handlers; the stdin → master and master → stdout + `stdout.log` relay through `select`; `SIGWINCH` → `TIOCSWINSZ`; the `Ctrl-]` `Ctrl-]` escape; `SIGHUP`/`SIGTERM`/`SIGINT` ending the session with a second signal ignored; `meta.json` through `_open_log`. Headless `main()` argv is unchanged.
- [X] T034 [US1] Implement `chat.start` and its `run.py` wiring in `tools/spec_workflow/chat.py` and `tools/spec_workflow/run.py` (depends on T017, T019, T023, T024, T031, T032): the contracts/cli.md § `start --mode chat` refusals and its six steps in order; integration and `review_integration` selection with `cross_provider`; `start_head`; the archive of `run/workflow.yml` and `run/chat.json`; rename `_archive_operator`'s target by mode (`autonomous/` for Autonomous, `operator/` otherwise); the ledger `run` event with `mode: chat`.
- [X] T035 [US1] Implement `chat.run_step`, the lifecycle of contracts/step-runner.md steps 1 and 3–12 (step 2 is T050), and the `step` wiring in `tools/spec_workflow/chat.py` and `tools/spec_workflow/run.py` (depends on T025, T027, T033, T034): run lock; out-of-step detection; synchronization with the Chat `rerun` text and a `sync` event; entry condition; integration choice with the self-test and Codex nesting probe; `tree_before`, protected snapshot, `active_step`, `start` entry and `in-progress`; `agent.run_interactive` in `chat` mode, the unchanged headless `agent.py` path in `human-gated` mode (`driver: headless`); scope stop and confirmation, then descendants; protected comparison and tamper marker; postcondition, cumulative checks and write-scope check; `close` entry, `last_manifest`, ledger `step` and `snapshot` events, archive and Draft PR checkpoint; the outcome derived only from exit status, scope stop, protected comparison and recorded checks; the last printed lines per contracts/cli.md § `step`.
- [X] T036 [US1] Implement `chat.summary` and the `status` command in `tools/spec_workflow/chat.py` and `tools/spec_workflow/run.py` (depends on T019, T028, T034): built only from the operator record (and a continuation source's decision log), never from a log under `.specify/workflow-state/`.
- [X] T037 [US1] Implement `approve` and `reject` in `tools/spec_workflow/chat.py` and `tools/spec_workflow/run.py` (depends on T019, T034): refused without a TTY on stdin and stdout, with an active step, or when the precondition fails now (recorded as a `check` with `purpose: gate` and a `refusal`); print gate, artifact, digest and, for a continued Autonomous run, the PDs this approval supersedes; require the exact typed `approve GATE` / `reject GATE`, else exit 2 with nothing written; append `gate-approval` / `gate-rejection` with the digest and `supersedes_provisional`; `approve intent` calls `artifacts.record_intent`; `approve tasks` writes `baseline`; `approve final` sets `completed`; ledger `step` started/completed for the gate step ID then `gate`; store a manifest and `last_manifest` after the approval.
- [X] T038 [US1] Run out-of-step detection at the start of every Chat invocation that reads the run (`step`, `status`, `approve`, `reject`, `resolve`, `checks`, `mode`, `publish`) in `tools/spec_workflow/chat.py`, and make `completed` or `published` return to `active` when the final approval becomes stale (depends on T029, T035, T037). [FR-011]

**Checkpoint**: T024–T030 pass. Do not ship US1 alone: US2 (agent cannot approve) and US3 (resume, interruption, concurrency) are also P1.

---

## Phase 4: User Story 2 - Approve gates as a human, never through the conversation (Priority: P1)

**Goal**: Only the operator's TTY-confirmed actions approve gates or resolve decisions; nothing an agent writes, prints or says changes the run's mode, approvals, recorded checks or allowed steps.

**Independent Test**: Quickstart scenario 2: in a step, the agent writes an approval block, claims approval and passing checks, and tries `ballast run approve`. The next step that needs the approval is still refused, and the record shows no approval and no passing check.

### Acceptance tests for User Story 2

- [X] T039 [US2] Write approval tests in `tests/test_chat_mode.py` (depends on T006): `approve RUN intent` without a TTY is refused with exit 2 and writes nothing; under a TTY, typing anything but `approve intent` exits 2 and writes nothing; the exact text appends a `gate-approval` bound to the digest printed on screen, stored under `autonomy.run_dir` and nowhere in the checkout, plus the ledger `gate` event; `approve` while a step is active is refused by the launcher (marker) and by `active_step`; a failing precondition is refused and recorded; `reject plan --reason x` keeps `tasks` refused until a later `approve plan` at a current digest; editing `plan.md` after `approve plan` makes it stale. [AC-007, FR-003, D-4]
- [X] T040 [US2] Write interactive-forgery tests in `tests/test_chat_mode.py` (depends on T006): one test per attempt by the fake TUI in a `plan` step: write a `workflow-approval` block into `intent.md`; print and write `RECONCILE_STATUS: approved`, "plan approved" and `- Verdict: approved` into `plan.md`; write a `DEC-0001 — Resolution` into `decisions.md`; `run ["ballast", "run", "approve", RUN, "plan"]` (refused: `in-progress` marker); `try_write` on `run.json`, `human-decisions.jsonl` and `events.jsonl` (real-bwrap variant: not visible; fake-bwrap variant skipped for this attempt). After each: no `gate-approval` exists, no `check` for the forged claim is recorded as passed, `mode_history` is unchanged, `allowed_actions` equals its value before the step, `tasks` is still refused, and `converge` stays refused on the unconfirmed resolution. [AC-008, FR-006, FR-015, SC-004]
- [X] T041 [US2] Write headless-driver forgery tests in `tests/test_chat_mode.py` (depends on T006; its human-gated switch passes only after T062, analyze F1): after `mode RUN human-gated`, a `step` runs through `agent.py` with argv equal to `agent.permission_args` for that integration and no option widening it toward the operator state directory (no `--add-dir`, no writable root); a forged `human-decisions.jsonl` line with a wrong `prev` makes every later Chat command refuse with the chain error instead of counting it; a `human-decisions.jsonl`, `run.json` or approval file written anywhere under the checkout (including `.specify/workflow-state/`) is never read. The residual bound (a correctly chained line written with the operator's own file access) is the one documented by T002. [F-001, AC-008, FR-006]
- [X] T042 [US2] Write human-resolution and provisional-intent tests in `tests/test_chat_mode.py` (depends on T006): a Chat run whose `intent.md` holds an agent-provisional block refuses `step plan` naming `intent`; so does a Chat continuation of an Autonomous run before `approve intent`; `approve intent` replaces the provisional block with the registered human block, and only then is `plan` allowed [F-002, BL-INV-006]; `resolve RUN DEC-0001` needs a TTY, no active step and a `Resolution` section, shows the text and digest, requires `resolve DEC-0001`, and records a `decision-resolution`; after it `converge` is allowed, and after the resolution text is edited it is refused again; the set of Chat gates equals the gate IDs of `templates/spec-kit/workflows/feature/workflow.yml`, so Chat asks for every human approval the human-gated mode asks for; no Chat command calls `autonomy.append_decision` or writes an `agent-provisional` entry (patched sentinel over a full US1 flow). [AC-009, FR-003, D-4]

### Implementation for User Story 2

- [X] T043 [US2] Implement `resolve` in `tools/spec_workflow/chat.py` and `tools/spec_workflow/run.py` (depends on T037, T042): the contracts/cli.md § `resolve` refusals, the normalized resolution-text digest shared with T015's decisions rule, the typed confirmation and the `decision-resolution` record.
- [X] T044 [US2] Close any gap T039–T041 expose in `tools/spec_workflow/chat.py` and `tools/spec_workflow/run.py` (depends on T035, T038, T039, T040, T041, T043): gate state comes only from `human-decisions.jsonl`; check results only from events the runner appended; the review verdict is written only into a `review` event; no Chat path reads agent output, `intent.md` blocks other than the registered one, or any checkout-side state file to decide a gate, a check or the mode.

**Checkpoint**: T039–T042 pass. US1 + US2 give a conversational run whose approvals stay human.

---

## Phase 5: User Story 3 - Leave and resume a Chat run safely (Priority: P1)

**Goal**: A Chat run survives closed terminals, crashes and days away: every return re-runs the full preflight, the handoff comes from the record, interrupted steps are closed and checked, and one step at a time is enforced.

**Independent Test**: Quickstart scenario 3: run two steps with one failed postcondition, end the session, advance the base, return. Synchronization runs before the next agent, the summary shows the failed check and pending gates, and no dependent step is offered.

### Acceptance tests for User Story 3

- [X] T045 [US3] Write return-preflight tests in `tests/test_chat_mode.py` (depends on T006): each of the five preflight conditions refuses `step` before any agent with the headless reason and exit status (completing SC-002 with T024's `start` cases); `resume RUN` of a Chat run is refused with "Chat runs continue with `ballast run step RUN_ID PHASE`; see `ballast run status RUN_ID`"; after `advance_base` with a clean tree, `step` records a `synchronized` sync event before the step's `start` entry [edge "base branch advances"]; with a dirty tree it prints the `dirty` block with the `ballast run step RUN PHASE` recovery, records `sync` and `refusal` events, exits 1 and starts no agent. [AC-010, FR-004, FR-018, SC-002]
- [X] T046 [US3] Write handoff-on-return tests in `tests/test_chat_mode.py` (depends on T006): after two steps with a failed `plan` postcondition, a pending plan gate and an open decision, a new process runs `status`; the output names the failed check with its `E-NNNN`, the pending gates and the allowed next steps (no dependent phase); deleting every `stdout.log` and `meta.json` leaves the output byte-identical. [AC-011, FR-019, SC-006]
- [X] T047 [US3] Write interruption tests in `tests/test_chat_mode.py` (depends on T006): `SIGHUP` to the wrapper mid-step closes the step as `interrupted` in the same process, after scope confirmation, with its postcondition recorded; with the wrapper killed by `SIGKILL` and the fake TUI still running in its scope, the next `ballast run status` is refused with the launcher text naming the run and step; `ballast discard-runs` with a confirming fake `systemd-run` clears the marker, after which the next invocation closes the step as `interrupted` with `late_close: true`, `attribution: "uncertain"`, `protected_compared: false`, `tree_after` = the current manifest and the step's postcondition and write-scope check recorded before anything else; with a non-confirming fake the refusal stays and the step is not closed. [AC-012, FR-009, F-003, F-004, D-7]
- [X] T048 [US3] Write concurrency tests in `tests/test_chat_mode.py` (depends on T006; the `mode` and `continue` refusals pass only after T062 and T063, analyze F2): while a step is active, a second `step` on the same run, `resume` of another run, `continue` and `mode` are each refused with a reason that names the active run and step; two `step` invocations started together before either writes the marker (a barrier seam after the lock is taken) → exactly one runs the fake agent and the other exits 2 naming the active step. [AC-013, FR-012]

### Implementation for User Story 3

- [X] T049 [US3] Refuse `resume` of a `ballast-chat` run, and of a `ballast-feature` run that a Chat run continues (naming that Chat run), in `run._resume_refusal` in `tools/spec_workflow/run.py` (depends on T034, T045).
- [X] T050 [US3] Implement lifecycle step 2, the late close of an `active_step` without a `close` entry, in `tools/spec_workflow/chat.py` per the rule written by T002 (depends on T002, T035, T047): continue only when the late close records `scope_stopped: true`.
- [X] T051 [US3] Apply the run lock and the `active_step` refusal to every Chat command that changes a run (`approve`, `reject`, `resolve`, `checks`, `mode`, `continue`, `publish`) in `tools/spec_workflow/chat.py` and `tools/spec_workflow/run.py`, with the refusal naming the active step (depends on T035, T043, T048; the `mode`, `continue` and `publish` commands it covers land in T059, T062 and T063, analyze F2).

**Checkpoint**: T045–T048 pass. US1–US3 are the minimum mergeable increment.

---

## Phase 6: User Story 4 - Record the same evidence a headless run would give the PR (Priority: P2)

**Goal**: A Chat run's ledger, reviews, checks and Draft PR carry the same evidence as a headless run, labeled Chat, with conversation logs kept local.

**Independent Test**: Quickstart scenario 4: finish a fixture feature in Chat with a review and checks, approve the remaining gates and publish; compare its ledger report with a human-gated fixture run.

### Acceptance tests for User Story 4

- [X] T052 [US4] Write ledger evidence tests in `tests/test_chat_mode.py` (depends on T006): a full Chat fixture run's `events.jsonl` validates; `ballast ledger report --run RUN` takes the Chat path (reads `run/workflow.yml` and `run/chat.json`, never engine `state.json`), shows the mode history, and computes compliance against the `ballast-feature` step and gate IDs; the set of event kinds and feature-identity fields (Issue, feature directory, branch, run) equals that of a human-gated fixture run, differing only in `mode` and step order. [AC-014, FR-013, SC-003]
- [X] T053 [US4] Write review-step tests in `tests/test_chat_mode.py` (depends on T006): `step RUN review --kind implementation` runs in a fresh process with the run's `review_integration`, `role: reviewer`, and a prompt naming `ballast-engineering-review`; a write outside `specs/<f>/reviews/` fails the step; a report that is missing, unchanged in the step, or whose last `- Verdict:` is outside the enum fails it; a passing close appends a `review` event with reviewer provider and model, `cross_provider`, report path and digest and verdict, and a ledger `review` event; `cross_provider` is true when `codex` reviews a `claude`-authored run and false when only `claude` is available, and the summary states it [edge "no reviewer from another provider"]; a `- Verdict: approved` opens no gate. [AC-015, FR-014, FR-015]
- [X] T054 [US4] Write project-checks tests in `tests/test_chat_mode.py` (depends on T006): `checks RUN` runs each `[checks] commands` entry and appends a `project-checks` event with exit, seconds, `timed_out`, `provenance: "runner"` and the tree, and ledger `verification` events; without a `[checks]` table it records `unavailable: true`; it is refused while a step is active; `approve final` is refused without a passing or `unavailable` result for the current tree and after any later edit. [AC-014, FR-013, FR-015]
- [X] T055 [US4] Write publication tests in `tests/test_chat_mode.py` (depends on T006): `publish` is refused (recorded `refusal`, exit 2) with no `final` approval, with a stale one after an edit, and while a step is active; with fake `git` and `gh` it runs only `add`, `commit` (hooks and filters disabled, protected paths refused), `push` without force from a throwaway repository, and `pr create --draft` or `pr edit` on the single Draft PR; the Chat section between `<!-- ballast:chat:begin -->` and `<!-- ballast:chat:end -->` matches a golden text from contracts/pr-evidence.md, including the mode history, every human approval with its digest, carried PDs labeled `agent-provisional`, reviews with the cross-provider flag, checks, out-of-step changes and the "Conversation logs and agent logs stay on the operator's machine" line; a body edited between read and write is left alone and a retry succeeds; an oversized section falls back to counts; agent-derived values pass through `neutralize` and "approved by the operator" appears only in the header and `gate-approval` rows; the run becomes `published`. Secret variant: the fake TUI prints `sk-test-0000SECRET`; it is in `stdout.log` but not in the PR body, the commit, any tracked file or the ledger, and the body has no `speckit-runs` or `.specify/workflow-state` reference. Existing Autonomous publisher tests are unchanged. [AC-016, AC-017, FR-016, FR-017, D-6, edge "secret in the conversation"]

### Implementation for User Story 4

- [X] T056 [P] [US4] Implement the Chat path of `ledger report` in `tools/spec_workflow/ledger.py` (depends on T012, T035, T037, T052): recognize `mode: chat` on the `run` event, read the archived definition and phase graph, compute step and gate compliance and freshness against the same IDs, and print the mode history.
- [X] T057 [US4] Implement the `review` phase in `tools/spec_workflow/chat.py` (depends on T035, T053): kind validation, reviewer integration and role, the report checks, verdict parsing restricted to `VERDICTS`, and the `review` events.
- [X] T058 [US4] Implement `checks` in `tools/spec_workflow/chat.py` and `tools/spec_workflow/run.py` on the mode-neutral `artifacts.run_checks` core, and add the checks result to the `final` gate precondition (depends on T015, T035, T054).
- [X] T059 [US4] Make `autonomy.publish` mode-aware in `tools/spec_workflow/autonomy.py` and implement `chat.publish_section` and the Chat `publish` dispatch in `tools/spec_workflow/chat.py` and `tools/spec_workflow/run.py` (depends on T037, T055, T058): the contracts/pr-evidence.md preconditions, the existing commit/push/PR path, a commit message naming the mode, the Chat section renderer and wording rules; the Autonomous body and its `HUMAN_APPROVAL` guard unchanged.

**Checkpoint**: T052–T055 pass; a Chat run reaches a Draft PR with headless-equivalent evidence.

---

## Phase 7: User Story 5 - Switch modes without losing a failure or promoting a decision (Priority: P2)

**Goal**: Chat ⇄ human-gated switches, engine-run and Autonomous continuations into Chat, and no raise to Autonomous; no switch hides a failure or promotes a decision.

**Independent Test**: Quickstart scenarios 5–7: switch a run with a failed check and an open decision to human-gated and back; try Autonomous; continue a blocked Autonomous run and a paused engine run in Chat.

### Acceptance tests for User Story 5

- [X] T060 [US5] Write mode-switch tests in `tests/test_chat_mode.py` (depends on T006): with a failed `plan` postcondition and a `DEC-0001` resolved only in text, `mode RUN human-gated --reason x` then `mode RUN chat --reason y` each append a `switch` entry (time, `by: operator`, reason, HD ID) and a `mode-change` HD, and the bytes of every earlier line of `steps.jsonl`, `events.jsonl` and `human-decisions.jsonl` are unchanged [AC-018]; after each switch `tasks` is still refused on the failed `plan` check and only a later passing `plan` run clears it, with the failure still in the history [AC-019]; `converge` stays refused until `resolve` [AC-020]; `mode RUN autonomous` is refused with "autonomy is never raised after start" [AC-021]; in human-gated mode `step RUN implement` runs headless through `agent.py` with today's argv, records `driver: headless` and the same close entry, checks and ledger events; `mode` on a paused `ballast-feature` engine run with a branch pin creates a linked Chat run (`continues: RUN`), leaves engine state untouched, re-asks plan and tasks approvals, carries intent through its registered block, and `resume RUN` is then refused naming the Chat run. [AC-018–AC-021, FR-020, FR-022, SC-005, D-5]
- [X] T061 [US5] Write Autonomous-continuation tests in `tests/test_chat_mode.py` (depends on T006): `continue RUN --reason block-resolved --ref x --mode chat` on a blocked Autonomous run applies the same source refusals as today, records the human decision, lowers the source `autonomous → chat` and sets it `continued`, re-renders its `autonomous/record.md`, creates a linked Chat run with the source's pin, runs branch synchronization, starts no agent, and prints a summary that lists every source PD as `agent-provisional`; after `approve intent` in the Chat run, `status` and the PR section show PD-0003 "superseded by HD-NNNN" and still labeled `agent-provisional`; `--reason changes-requested` behaves the same; `continue ... --mode autonomous` is refused with the "never raised" text; `continue` without `--mode` behaves as today (existing tests unchanged). [AC-022, FR-021, FR-022, BL-INV-006]

### Implementation for User Story 5

- [X] T062 [US5] Implement `mode` in `tools/spec_workflow/chat.py` and `tools/spec_workflow/run.py` (depends on T008, T051, T060): the contracts/cli.md § `mode` table, the linked-run path from a `ballast-feature` run, and the refusals.
- [X] T063 [US5] Implement `continue --mode chat` in `run._continue_command` in `tools/spec_workflow/run.py` and `chat.continue_run` in `tools/spec_workflow/chat.py` (depends on T015, T037, T061, T062): the six steps of contracts/cli.md § `continue --mode chat`, and the carried PD list used by `summary`, `approve` (`supersedes_provisional`) and the PR section.

**Checkpoint**: every story's tests pass.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Operator documentation, governance, installed-copy refresh, gates, pilot evidence, reviews and reconciliation.

- [X] T064 [P] Add a "Chat runs" section and runner-contract rows to `templates/policies/spec-kit-workflow.md` (depends on T059, T062, T063): start, step, status, approve/reject/resolve, checks, mode, continue, publish and resume refusal; the preflight before every step; interactive confinement (deny without prompt, bwrap prerequisite); human approvals only through `ballast run approve`; conversation logs stay local; working in a plain agent session outside `ballast run` gives none of these guarantees. [FR-023]
- [X] T065 [P] Add Chat to the modes in `templates/policies/workflow.md` (depends on T062): same approvals as human-gated, switchable with human-gated, never raised to Autonomous; and, as T069 checks (analyze F3), how to start, inspect, continue, resume and switch a Chat run, that its approvals are human, and that work outside `ballast run` has none of its guarantees. [FR-023]
- [X] T066 [P] Add the Chat start, inspect and resume commands and the "outside `ballast run` gives no guarantees" rule to `templates/AGENTS.md` (depends on T062, T063). [FR-023]
- [X] T067 [P] Add the Chat start command to `templates/skills/ballast-feature-intake/SKILL.md` as an option of the hand-off (depends on T034). [FR-023]
- [X] T068 [P] Update the repository-owned `AGENTS.md`, `CLAUDE.md`, `README.md` and the §91 status line of `specs/TECHNICAL-SPEC.md` for Chat mode (depends on T059, T063). [FR-023]
- [X] T069 Add governance tests in `tests/test_governance.py` asserting that the shipped spec-kit workflow policy, workflow policy, `AGENTS.md` template and intake skill each describe starting, inspecting, continuing, resuming and switching a Chat run, that approvals are human, and that work outside `ballast run` has none of its guarantees (depends on T064, T065, T066, T067). [FR-023]
- [X] T070 [P] Reconcile `docs/adr/0009-chat-mode-operator-driven-steps.md` with the implemented behavior, still `Proposed` (depends on T001, T059, T063).
- [X] T071 In a fresh clone of this branch, run `BALLAST_STANDARD_DIR=<this checkout> ballast setup` and confirm that `.ballast/spec_workflow/chat.py` and `claude-chat-settings.json` are installed, that the installed policies equal the templates, and that `git status --short` shows no tracked change outside plan.md § Repository Impact; record the evidence here (depends on T064, T065, T066, T067). [BL-INV-001]
  - Evidence (2026-10-06): the implementing agent step runs inside the run's bubblewrap sandbox, where it cannot write a fresh clone outside the worktree or run the global `ballast`. Instead, `tests/test_setup.py` `ChatInstallTests` runs `tools/setup`'s `install_standard` into a temporary project. It checks that `.ballast/spec_workflow/chat.py` and `claude-chat-settings.json` are installed and every installed policy equals its template, and that a project `[agents.permissions] extra_deny` rule reaches the settings a Chat step generates. `ChatCase` in `tests/test_chat_mode.py` installs `tools/spec_workflow` the same way (`copytree` without `__pycache__`) and runs every Chat command through the launcher. The fresh-clone `ballast setup` run stays for the operator's full gate (T074).
  - Fresh clone (2026-10-06, branch at `802e3c0`, outside any agent sandbox): `git clone --branch feat/20-chat-mode` into a scratch directory, then `BALLAST_STANDARD_DIR=<that clone> ballast setup` inside it (the `ballast` CLI on PATH is v0.3.0; it runs the clone's own `tools/setup`) exited 0 ("Spec Kit 1.0.11 and the standard are set up"). `.ballast/spec_workflow/chat.py` and `claude-chat-settings.json` are installed, and `chat.py` equals `tools/spec_workflow/chat.py`; `diff -r templates/policies docs/policies -x project` prints nothing; `git status --short` prints nothing, so setup left no tracked change.
- [X] T072 Verify the unchanged surfaces and record the evidence here (depends on T044, T050, T051, T059, T063): `git diff --exit-code main -- templates/spec-kit/workflows tools/spec_workflow/claude-settings.json tools/ballast tools/setup .specify/memory/constitution.md` is empty; `git diff main -- tests/` changes no assertion of an existing test (list any fixture-only change for the PR). [SC-007]
  - Evidence (2026-10-06, against the branch base `HEAD` 52031c1; the local `main` ref is stale): `git diff --stat HEAD -- templates/spec-kit/workflows tools/spec_workflow/claude-settings.json tools/ballast tools/setup .specify/memory/constitution.md` prints nothing. `git diff HEAD -- tests/ | grep -E "^-[^-]"` prints nothing: existing test files only gain new tests and classes, and no existing line or assertion changed. The new fixture is `tests/fixtures/chat/fake_tui.py`; the existing fixtures are unchanged.
- [X] T073 Run the fast gate and record commands and results for the PR: `uvx ruff check && uvx ruff format --check` and `uv run --no-project --python 3.13 --with pyyaml python -m unittest tests/test_*.py` (depends on T013, T030, T049, T056, T057, T068, T069, T070, T071, T072).
  - Evidence (2026-10-06, code at `83d04c2`): `uvx ruff check` and `uvx ruff format --check` are clean; `uv run --no-project --isolated --python 3.13 --with pyyaml python -m unittest tests/test_*.py` ran 791 tests, OK.
- [X] T074 Run the full local gate on Linux with a systemd user session, `bwrap`, the Codex CLI and the Spec Kit CLI, so the real-confinement and CI-skipped tests also run; record the result, or the unavailable gate and why (depends on T073).
  - Evidence (2026-10-06): the run above was on Linux with a systemd user session, `bwrap` with user namespaces, codex-cli 0.155.1 and Spec Kit 1.0.11. It reported OK with no skipped test, so the real-confinement tests ran, including the Chat ones: real bwrap ×3, and real `systemd-run` plus bwrap in `StepCloseTests.test_real_scope_and_bwrap_step_is_confirmed_stopped`. Codex cannot nest its sandbox inside bwrap on this host (`codex_sandbox_nests` is False), so Chat with Codex is refused here, as designed. The fresh-clone `ballast setup` (T071) stays with the operator.
- [X] T075 Run pilot checks P-1–P-5 and quickstart scenarios 1–7 in a scratch repository with a real GitHub remote and the real `claude` (and `codex` when it can run confined), and record the transcript summary, run IDs and results in `specs/20-chat-mode/reviews/pilot.md`. Manual evidence because a real interactive TUI, terminal resizing, Shift+Tab and `/permissions` cannot be driven by the fake; every AC also has a deterministic test (depends on T073). [AC-001, AC-003, SC-001, D-3]
  - Evidence (2026-10-06): P-1, P-2 and the Codex nesting probe ran and are recorded in `reviews/pilot.md`. P-3 to P-5 and quickstart scenarios 1–7 need a person at a real terminal with a GitHub remote; they moved to #24 (cross-repository v1.0 qualification, run by the operator) per [DEC-0004](decisions.md#dec-0004--proposal).
- [X] T076 Run the reviews the matrix requires and store reports in `specs/20-chat-mode/reviews/`: engineering, test (against the traceability table below), security (agent authority, trust model, the D-3 confinement change, the second publication caller), documentation (CLI, policies, ADR-0009) and architecture (ADR-0009). Use a cross-provider reviewer when Codex can run confined; otherwise record why not (DEC-0004 of the run record) (depends on T073).
  - Evidence: `reviews/security.md`, `engineering.md` (architecture and ADR-0009), `test.md` and `documentation.md`. Each verdict is approved after its Resolution section. The reviews were same-provider: Codex hit its usage limit, and its sandbox does not nest in bwrap here. Medium and higher findings were fixed test-first in `110d8c8` and `83d04c2`; the open low findings are follow-up F-5.
- [X] T077 Resolve open items in `specs/20-chat-mode/decisions.md` if it exists, run Spec Kit converge and the spec-reconciliation skill (`reviews/convergence.md`), and leave ADR-0009 `Proposed` for the human merge decision (depends on T074, T075, T076).
  - Evidence: DEC-0001 to DEC-0004 are resolved in `decisions.md` and listed for the merge review. Converge found no unbuilt work. `reviews/spec-reconciliation.md` and `reviews/convergence.md` end with `- Verdict: CONVERGED`, and ADR-0009 stays `Proposed`. T075's interactive pilot checks moved to #24 per DEC-0004.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: T001–T005 need nothing; T006 needs T004 and T005.
- **Foundational (Phase 2)**: T007, T011, T014, T020 need nothing; the `tests/test_chat_mode.py` tasks need T006; each implementation task needs its tests; T019 needs T015 and T017; T023 needs T021 and T022. Blocks every story.
- **US1 (Phase 3)**: tests need only T006; T031 and T032 need nothing; T034 needs the whole foundation; T035 needs T033 and T034.
- **US2 (Phase 4)**: tests need only T006; implementation needs US1's `approve` (T037) and step lifecycle (T035).
- **US3 (Phase 5)**: tests need only T006; implementation needs US1's start and step (T034, T035) and US2's `resolve` (T043) for the lock coverage.
- **US4 (Phase 6)**: tests need only T006; implementation needs US1's step and approve and, for `final`, `checks`.
- **US5 (Phase 7)**: tests need only T006; implementation needs US3's command lock (T051) and US1's approve.
- **Polish (Phase 8)**: after all stories.

### User Story Dependencies

- **US1 (P1)**: after Foundational. Its `approve`/`reject` (T037) live here because the US1 scenario approves scope and intent.
- **US2 (P1)**: after US1's T035 and T037; it hardens and tests them and adds `resolve`.
- **US3 (P1)**: after US1's T034 and T035; T051 also follows US2's T043.
- **US4 (P2)**: after US1. Independent of US2 and US3 except through shared files.
- **US5 (P2)**: after US3's T051. `continue --mode chat` uses US1's approve.

### Within Each User Story

- Tests first, failing; then implementation.
- `tests/test_chat_mode.py`, `tools/spec_workflow/chat.py` and `tools/spec_workflow/run.py` are each edited by one task at a time.

## Execution Wave DAG

Tasks in a wave have every dependency met by earlier waves. Tasks in one wave that edit the same file run one after another; only `[P]` tasks touch a file no other task in their wave touches.

| Wave | Tasks | Notes |
| --- | --- | --- |
| 1 | T001, T002, T003, T004, T005, T031, T032; then T007 → T009 (`tests/test_autonomy.py`); T011; then T014 → T020 (`tests/test_spec_workflow.py`) | ADR, contract amendments, settings, skeleton, fake TUI, `branch_sync` rerun text, `draft_pr` identity, first test files |
| 2 | T006, T008, T012, T021 | harness; Chat record (`autonomy.py`); ledger field; launcher text |
| 3 | T010, T013, T015; then in `tests/test_chat_mode.py`: T016, T018, T022, T024, T025, T026, T027, T028, T029, T030, T039, T040, T041, T042, T045, T046, T047, T048, T052, T053, T054, T055, T060, T061 | confinement parameter (`autonomy.py`), schema doc, artifact routes; every Chat test written before the code it proves, one after another in one file |
| 4 | T017, T023, T033 | record layer (`chat.py`); dispatch (`run.py`); interactive launch (`agent.py`) |
| 5 | T019 | phase graph |
| 6 | T034 | `start --mode chat` |
| 7 | T035 → T036 → T037 (`chat.py`, `run.py`); T049 after T035 (`run.py`) | step lifecycle, status, approve/reject, resume refusal |
| 8 | T038 → T043 → T050 → T057 → T058 (`chat.py`); T056 [P] (`ledger.py`) | out-of-step wiring, resolve, late close, review phase, checks; ledger Chat report |
| 9 | T044 → T051 → T059 (`chat.py`, `run.py`; T059 also `autonomy.py`) | forgery hardening, command lock, publication |
| 10 | T062 | `mode` |
| 11 | T063 | `continue --mode chat` |
| 12 | T064, T065, T066, T067, T068, T070, T072 | documentation, ADR, unchanged-surface check |
| 13 | T069, T071 | governance test, installed-copy refresh |
| 14 | T073 | fast gate |
| 15 | T074, T075, T076 | full gate, pilot, reviews |
| 16 | T077 | converge and spec reconciliation |

## Parallel Example: Wave 1

```text
Task: "Draft ADR-0009 in docs/adr/0009-chat-mode-operator-driven-steps.md"                  (T001)
Task: "Amend data-model.md and contracts/step-runner.md for F-001, F-003, F-004"              (T002)
Task: "Create tools/spec_workflow/claude-chat-settings.json"                                  (T003)
Task: "Create the tools/spec_workflow/chat.py skeleton"                                       (T004)
Task: "Create tests/fixtures/chat/fake_tui.py"                                                (T005)
Task: "Add the rerun text to branch_sync with tests"                                          (T031)
Task: "Add the operator-record fallback to draft_pr identification with tests"                (T032)
Task: "Write Chat record then confinement tests in tests/test_autonomy.py"                    (T007, T009)
Task: "Write ledger mode tests in tests/test_agent_run_ledger.py"                              (T011)
Task: "Write Chat artifact then launcher-text tests in tests/test_spec_workflow.py"           (T014, T020)
```

## Implementation Strategy

### MVP first (User Stories 1–3)

1. Phases 1 and 2: the Chat record, event log, phase graph, confinement parameter and dispatch.
2. Phase 3 (US1): start, interactive steps, status, approvals, out-of-step changes.
3. **Stop and validate**: T024–T030 and the fast gate. Do not ship US1 alone: without US2 the approval boundary is untested against forgery, and without US3 an interrupted step or a concurrent invocation is not handled. US1–US3 are all P1.

### Incremental delivery

1. Foundation → US1 → US2 → US3 is the minimum mergeable increment: a conversational run that keeps the preflight, human approvals and resume guarantees.
2. US4 adds the ledger report, reviews, checks and publication. It is required for the 1.0 goal of a Chat run reaching a reviewable Draft PR (Issue #20 acceptance criterion 2).
3. US5 adds mode switches and continuations (Issue #20 acceptance criterion 3).
4. Polish: documentation, governance test, gates, pilot, R2 reviews, reconciliation. ADR-0009 stays `Proposed` until the human merge decision.

## Acceptance criteria traceability

| Criterion | Test or verification tasks |
| --- | --- |
| AC-001 | T024, T030, T075 |
| AC-002 | T018, T025, T030 |
| AC-003 | T009, T025, T026, T075 (P-3, P-4, P-5) |
| AC-004 | T018, T027, T030 |
| AC-005 | T028 |
| AC-006 | T029, T030 |
| AC-007 | T039 |
| AC-008 | T014, T040, T041 |
| AC-009 | T014, T042 |
| AC-010 | T045 |
| AC-011 | T046 |
| AC-012 | T047 |
| AC-013 | T020, T048 |
| AC-014 | T011, T052, T054 |
| AC-015 | T053 |
| AC-016 | T055 |
| AC-017 | T027, T055 |
| AC-018 | T007, T060 |
| AC-019 | T018, T060 |
| AC-020 | T060 |
| AC-021 | T007, T060 |
| AC-022 | T061 |
| SC-001 | T030, T075 |
| SC-002 | T024, T045 |
| SC-003 | T052 |
| SC-004 | T040, T041 |
| SC-005 | T060 |
| SC-006 | T046 |
| SC-007 | T007, T011, T014, T072, T073 |
| FR-001 | T022, T024 |
| FR-023 | T069, T076 (documentation review) |
| F-001 | T002, T041 |
| F-002 | T014, T042 |
| F-003 | T002, T047, T050 |
| F-004 | T002, T047, T050 |

| Edge case | Tasks |
| --- | --- |
| Protected input edited between steps | T029 |
| Base branch advances during a session | T045 |
| Step the workflow does not allow yet | T025 |
| Re-run of an earlier step | T029 |
| Permission the step does not allow | T025, T075 (P-4) |
| Integration cannot run confined | T024 |
| Secret in the conversation | T055 |
| Operator ends a step while the agent writes | T027 |
| No reviewer from another provider | T053 |

## Notes

- Every decision in this file is agent-provisional in Autonomous run `2cb9c5c5`; the merge decision is the single human approval.
- T002 changes contract wording to settle F-001, F-003 and F-004 as the plan review asked; it changes no requirement. If implementation shows the F-003 rule is wrong, record a proposal in `decisions.md` instead of changing it silently.
- Commit after each task or logical group, with Conventional Commit messages.
- Implementation clarifications. Each one fixes a contract defect that blocked a requirement, with no change of intent; each is written into the contract it touches and covered by a test:
  - **Tasks digest** (data-model § Gate digest binding): it reads every checkbox as unchecked. Otherwise implementing tasks, which marks them done, made the tasks approval stale, so the `implementation` gate, whose precondition needs a current tasks approval, could never be approved.
  - **`converge` entry** (phase-graph): it is cumulative, as in `ballast-feature`, so `implementation` and a current `implementation` approval come before `decisions`. A missing `decisions.md` passes the decisions check, so the contract's text alone opened `converge` before any implementation.
  - **`plan` entry** (phase-graph): it also requires the intent approval state, so a later `reject intent` keeps `plan` closed, as for every other gate. Before, the registered block alone kept it open.
  - **Claude settings of an interactive step** (step-runner § Interactive argv): `tools/setup` merges the project's `[agents.permissions]` rules only into the installed `claude-settings.json`. So each step writes, before its protected snapshot, a settings file in its own log directory: the installed headless rules (project rules included) plus `claude-chat-settings.json`. This keeps the Chat deny list a superset of the headless one (FR-005), with `tools/setup` unchanged.
  - **Review verdicts**: `artifacts.VERDICT_LINE` stops at a hyphen, so `chat.py` uses the same pattern with `-` allowed, for `changes-requested`.
  - **Tree manifest** (T016): file contents are hashed with SHA-256 in the runner (data model: `{path: sha256}`) rather than with `git hash-object`. The digest is the same unfiltered-content identity, and no Git content command runs.
  - **Mode-change ledger event**: `run` with `action: ended`, `status: mode-changed` and `mode`, so the only schema changes are the contract's two additive ones.
