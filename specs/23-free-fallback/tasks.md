---

description: "Task list for Qualify one zero-cost provider fallback"
---

# Tasks: Qualify one zero-cost provider fallback

**Input**: Design documents from `specs/23-free-fallback/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md), [decisions.md](decisions.md)

**Risk**: R2, Autonomous run. Merging the PR is the single human approval (BL-INV-006). DEC-0001 in [decisions.md](decisions.md) keeps the spec as written. A step falls back only after its first primary attempt (SC-005, FR-006). Changed-state evidence covers git-ignored worktree paths and refs, and refuses when it cannot be checked (AC-009, FR-003). DEC-0003 option 1 fixes the endpoint at Ollama's default `127.0.0.1:11434`: there is no endpoint option, setting field or base-URL `--config` key, and the probes check exactly the endpoint Codex uses. DEC-0004 requires a served context of at least 16384 tokens. The permission comparison is an exact-argv allowlist, and a non-empty `~/.agents/skills` refuses (plan-review F-001 to F-004 of the third review). The earlier plan-review finding PD-0010 F-001 is closed by an `incompatible-capability` refusal when the project lacks Codex's Spec Kit skill for the step's command (research R5 check 9; T001, T013, T015, T029).

**Acceptance evidence**: Every behavior acceptance criterion (AC-001 to AC-021) has a test or an explicit verification task below that cites its ID. Test names follow the [quickstart map](quickstart.md#offline-gate). Offline tests use a loopback stub Ollama (`http.server` on an ephemeral `127.0.0.1` port) that records every request. They also use fake `claude` and `codex` executables that record argv, prompt and environment. "Nothing sent" means the stub saw no request outside `/api/version`, `/api/tags` and `/api/show`, and the fake Codex never received the prompt.

**Workflow-owned steps**: The workflow runs these after implementation, so they have no task here: the full local gate, the quickstart pilot runs through `ballast run` (quickstart steps 3 to 5), the reviews, converge and spec reconciliation.

**Organization**: Tasks are grouped by user story. Several test tasks write to the single `tests/test_fallback.py`, and several implementation tasks share `fallback.py`, `agent.py` or `autonomy.py`. Tasks that share a file are chained by explicit dependencies, so no two of them run at the same time.

## Format: `[ID] [P?] [Story?] Description [(depends on ...)]`

- **[P]**: Can run in parallel with other ready tasks once its listed dependencies are satisfied
- **[Story?]**: User story the task belongs to (US1 to US4)
- **(depends on ...)**: Explicit dependency on earlier task IDs; omitted only when a task has none
- Test and verification tasks cite the acceptance criteria they prove, e.g. `[AC-001]`

## Path Conventions

Workflow tools live in `tools/spec_workflow/`, tests in `tests/` (unittest, stdlib plus `pyyaml`), feature artifacts in `specs/23-free-fallback/`. Workflow tools stay standard-library-only and run under `python3 -I -S` (FR-011).

---

## Phase 1: Setup (Pilot and test harness)

**Purpose**: Pin the host facts the design leaves open (research R10) and build the offline test harness.

- [X] T001 Run the host pilot of research R10 (items 1, 2, 4 and 5) on the qualified operator host. Run every probe from the operator's terminal, not from inside a confined agent step. Record each command, its outcome and the context it ran in, in a "Pilot" section of `specs/23-free-fallback/evaluation.md`:
  - versions and help: `codex --version`; `codex exec --help` (does it list `--oss`, `--local-provider` and `--json`?); `ollama --version`;
  - the exact `--config` key that pins the Ollama provider's base URL;
  - the `/api/version`, `/api/tags` and `/api/show` response fields for one local tag and one cloud tag (`remote_host`, `remote_model`, `size`, `digest`);
  - the `codex exec --json` event shape (`agent_message` items, `turn.completed` usage fields), from one `codex exec --oss --local-provider ollama -m qwen3:4b --json` run of a trivial prompt in a scratch directory, with `CODEX_HOME` set to an empty directory, which also shows whether `--oss` needs any login;
  - every Codex configuration layer that run reads (user, system, project `.codex/config.toml`);
  - the project path where Codex finds a Spec Kit skill for a `$speckit-x` prompt (expected `.agents/skills/<command>/SKILL.md`), from a run in a scratch project with the Codex integration installed;
  - `autonomy.codex_sandbox_nests` with bubblewrap, and the same `codex sandbox` probe without it;
  - quota-exhausted and provider-unavailable messages from `claude` and `codex`, with account, quota and credential details redacted. Each one comes from a captured run, the CLI's source or documentation, or an earlier run's logs (research R2), and its source is recorded. When a cause has no signature for an integration, list it.

  Record a discovery in `specs/23-free-fallback/decisions.md` and stop when any of these holds: the host cannot run the probes; the candidate is rejected outright (`--oss` missing, or the model cannot answer); no quota signature can be found for any integration; or the configuration layers cannot be established. Never switch backend silently.
  The `--config` key of the second bullet does not exist (DEC-0003 option 1): the endpoint is fixed. Done 2026-10-06: items 1 to 9 and the 16k rerun in [evaluation.md](evaluation.md#pilot) (item 10: `qwen3:4b-16k` answered `ok` under `codex exec --oss --json`, exit 0, `turn.completed` input_tokens 11905). DEC-0002 to DEC-0004 are resolved.
- [ ] T002 Create `tests/test_fallback.py` with the shared harness (depends on T001):
  - `StubOllama`, a loopback `http.server` on an ephemeral `127.0.0.1` port that serves configurable `/api/version`, `/api/tags` and `/api/show` responses, with an optional delay, and records every request;
  - helpers that write fake `claude` and `codex` executables into a temporary `PATH` directory. They record argv, environment, `CODEX_HOME` contents and prompt to a file, and print configurable output (including `--json` event streams) and exit codes;
  - module-level fixtures holding the redacted quota and availability messages and the `--json` event sample from T001;
  - a temporary `XDG_STATE_HOME`, `HOME` and Git checkout per test, with the Codex Spec Kit skill of the test's command installed at the path T001 recorded unless a test removes it.

---

## Phase 2: Foundational (Ledger additions, the fallback setting, worktree state evidence)

**Purpose**: The ledger values the wrapper writes, the operator setting it reads, and the evidence that a primary attempt changed nothing. Every story depends on these.

**⚠️ CRITICAL**: No user story work begins until this phase is complete; story tasks name these tasks as explicit dependencies.

- [X] T003 [P] Add ledger tests to `tests/test_agent_run_ledger.py` [AC-017]:
  - `route_source: fallback` is accepted.
  - `failure_cause` (`quota-exhausted`, `provider-unavailable`, `cli-unavailable`, `unrecognized`), `fallback` (`selected`, `refused`) and `fallback_reason` (`unknown-free-status`, `privacy-exclusion`, `incompatible-capability`, `permission-mismatch`, `changed-state`) are accepted. Any other value, or free text, is rejected.
  - The single cross-field rule set of [contracts/ledger.md](contracts/ledger.md#validation-ledgerpy), which data-model.md now repeats: `fallback_reason` without `fallback: refused` is rejected; `fallback: refused` without `fallback_reason` is rejected; `route_source: fallback` with `failure_cause` or `fallback` is rejected; a primary `route` with `failure_cause` and no `fallback` is accepted.
  - `schema_version` stays 1.
  - A `usage` event with `counter_source: codex-exec-json` and `provider: ollama` validates.
  - `ledger.report` counts `fallback` in `route_sources` and shows refusal reasons in `actual_routes`.
- [X] T004 Implement the additive ledger changes in `tools/spec_workflow/ledger.py` (depends on T003):
  - `ENUM_FIELDS["route"]` gains the `route_source` value `fallback` and the `failure_cause`, `fallback` and `fallback_reason` enums;
  - `FIELDS["route"]` gains the three optional label fields;
  - `validate`/`_semantic_problems` enforce the cross-field rules;
  - `report` counts fallbacks and lists refusal reasons;
  - `schema_version` is unchanged.
- [X] T005 [P] Add one paragraph to `tools/spec_workflow/ledger-schema.md` (depends on T004). It describes the new `route` value and fields, the cross-field rules and the report's fallback review rule of [contracts/ledger.md](contracts/ledger.md#report). It also states that the schema version is unchanged and that an older pinned Ballast rejects a stream holding them.
- [ ] T006 Add `SettingTests` to `tests/test_fallback.py` [AC-006, AC-020] (depends on T002):
  - `validate_model` accepts `qwen3:4b`. It rejects an empty name, a leading `-`, a name outside the ledger `MODEL` pattern and cloud tags (`:cloud`, `-cloud`), with the fixed messages of [contracts/operator-cli.md](contracts/operator-cli.md#start).
  - `test_setting_has_no_endpoint`: `write_setting` has no endpoint argument and `fallback.json` has no `endpoint` field; `read_setting` raises `SettingError` for a file that carries `endpoint` or any other unknown field; `OLLAMA_ENDPOINT` is `http://127.0.0.1:11434`.
  - `write_setting` writes `fallback.json` with mode 0600 in `autonomy.run_dir`, with the fields of [data-model.md](data-model.md#fallback-setting). `write_setting(model=None)` writes `enabled: false`.
  - `read_setting` returns `None` when the file is absent or disabled. It raises `SettingError` for a symlink, an unreadable file, bad JSON or any invalid field (`test_invalid_setting_is_off`).
- [ ] T007 Create `tools/spec_workflow/fallback.py` (standard library only, no top-level side effects), passing T006 (depends on T006). It holds:
  - the module docstring, `RECOVERABLE`, the cause and refusal-reason constants, the `Setting` dataclass, `SettingError` and `EventError`;
  - `validate_model`;
  - the constants `OLLAMA_ENDPOINT = "http://127.0.0.1:11434"`, `MIN_OLLAMA_VERSION` (0.13.4) and `MIN_SERVED_CONTEXT` (16384);
  - `write_setting(root, run_id, model)`: no endpoint argument; 0600 through the `autonomy` state helpers, `set_at` in UTC, `set_by: operator`, provider `ollama`;
  - `read_setting`: opened with `O_NOFOLLOW`; any invalid or unknown content raises `SettingError`.
- [ ] T008 Add `StateTests` to `tests/test_fallback.py` [AC-009] (depends on T006).

  `autonomy.ignored_digest` changes when any of these happens under a git-ignored path: a file is created, written (same size, mtime reset with `os.utime`), chmodded, renamed or deleted, a directory is added, or a symlink target changes. It also changes when `.specify/feature.json` changes. It ignores changes under `.ballast/`, `.venv/` and `.specify/` other than the `SPECIFY_WRITABLE` paths, and the wrapper's own log files. It never follows a symlink out of the worktree. It returns `None` for over 200,000 entries (patched cap), a walk over the time budget (patched clock), an entry that `lstat` cannot read, or a failing Git.

  `autonomy.refs_digest` changes after a commit, a new branch, a new tag and a detached `HEAD`. It returns `None` on a Git failure.

  `fallback.state_evidence` returns `None` when any piece is `None`.
- [ ] T009 Implement `ignored_digest(root)` and `refs_digest(root)` in `tools/spec_workflow/autonomy.py`, per research R3 and [data-model.md](data-model.md#worktree-state-evidence) (depends on T007, T008):
  - `ignored_digest` uses `git ls-files -z --others --ignored --exclude-standard --directory`, then walks collapsed directories with `os.walk(followlinks=False)` and `lstat`. It excludes `PROTECTED` except `SPECIFY_WRITABLE`, and stops at 200,000 entries or 10 s.
  - `refs_digest` covers `HEAD` and `git for-each-ref`.
  - Git runs with hooks and fsmonitor disabled, as `tree_digest` does.

  Add `state_evidence(root, feature)` to `tools/spec_workflow/fallback.py`. It combines `tree_digest`, `reviews_digest`, the drafts listing, `ignored_digest` and `refs_digest`, and returns `None` when any piece cannot be established.

**Checkpoint**: The ledger accepts the new events, the setting can be written and read safely, and the wrapper can tell whether an attempt changed the worktree.

---

## Phase 3: User Story 1 - A quota or availability failure falls back to the local free backend (Priority: P1) 🎯 MVP

**Goal**: The setting is on and every check passes. A headless step's first primary attempt fails on quota, provider availability or a missing CLI. The step then runs once more on `codex exec --oss --local-provider ollama`, under the same confinement, with a private, empty Codex home, and completes.

**Independent Test**: A fake `claude` prints a captured quota message and exits 1; a second run prints an availability message instead. A fake `codex` succeeds against the stub Ollama. The step completes through the fallback with the canonical headless Codex permission profile. For an Autonomous step, the fallback uses the same `confined_argv` as the primary.

### Acceptance tests for User Story 1

- [ ] T010 [US1] Add US1 tests to `tests/test_fallback.py` [AC-001, AC-002, AC-003, AC-004, AC-006] (depends on T004, T009):
  - `ClassifyTests` recoverable cases: each captured quota and availability fixture, per integration, gives `quota-exhausted` or `provider-unavailable`; `cli_found=False` gives `cli-unavailable`.
  - `codex_prompt`: `/speckit-x rest` becomes `$speckit-x rest`; a `$` prompt is unchanged.
  - `fallback_argv(codex, prompt, model)` is exactly `permission_args("codex", ["exec", prompt])` plus `--oss`, `--local-provider ollama`, `-m MODEL` and `--json`. No `-c model_providers.ollama.*` or other base-URL key appears (Codex refuses it, DEC-0003), and no primary extra arguments are forwarded.
  - `fallback_env` keeps no provider key and no `OLLAMA_HOST`, `CODEX_OSS_BASE_URL` or `CODEX_OSS_PORT`. Its `CODEX_HOME` is the given private directory.
  - `parse_events` returns the agent message text, the summed usage and `complete`.
  - `permission_mismatch` returns false for exactly the argv `fallback_argv` builds and the env `fallback_env` builds, with the private `CODEX_HOME`.
  - `ProbeTests.test_eligible_model_passes`: the stub answers correctly, `probe` returns `None`, and only the model name is sent.
  - `WrapperFallbackTests`:
    - `test_quota_failure_completes_on_fallback`, `test_provider_unavailable_completes_on_fallback` and `test_cli_missing_completes_on_fallback`;
    - `test_setting_off_matches_today`: with the feature present and the setting off, argv, `steps.jsonl`, `meta.json` and the ledger are the same as without it, with no probe request, no state walk and no new file;
    - `test_fallback_argv_is_primary_codex_profile`;
    - `test_fallback_runs_under_same_confinement`: Autonomous; the same `confined_argv` call as the primary;
    - `test_user_codex_config_not_read`: the user's `~/.codex/config.toml` defines `mcp_servers`, a `notify` program and a default `profile`. The fake Codex sees a `CODEX_HOME` that is not the user's, is empty at start and is removed after the attempt. No MCP server or notify program from the user configuration is started.
- [ ] T011 [US1] Implement `classify(integration, exit_code, blocked, contained, tail, *, cli_found)` in `tools/spec_workflow/fallback.py` per [data-model.md](data-model.md#normalized-cause) (depends on T001, T010). It checks reserved wrapper exit codes and the blocking status first, then the per-integration signature tables pinned from T001, matched only against the last 64 KiB of stdout and stderr. Anything unmatched is `unrecognized`.
- [ ] T037 [US1] Add `ProbeContextTests` to `tests/test_fallback.py` (depends on T010; tests first, so T013 depends on this task): against a stub Ollama, `/api/show` with `num_ctx 16384` or more passes; `num_ctx 4096`, a missing `num_ctx` and an unparsable one each refuse as `incompatible-capability` with the detail `served context below 16384` or `served context unknown` [FR-006, DEC-0004]. `test_old_ollama_refuses_capability`: `/api/version` `0.6.8` refuses with `ollama older than 0.13.4`, `0.13.4` and `0.35.1` pass, and an unparsable version refuses with `ollama version unknown` [DEC-0003]. The stub shape comes from [evaluation.md](evaluation.md#10-qwen34b-16k-a-16k-context-local-variant-2026-10-06) item 10.
- [ ] T012 [US1] Implement the invocation helpers in `tools/spec_workflow/fallback.py` (depends on T011):
  - `codex_prompt`;
  - `fallback_argv(codex, prompt, model)`: research R6, the fixed token list with no base-URL key;
  - `fallback_env(env, codex_home)`: `autonomy.confined_env(env, None)` minus `OLLAMA_HOST`, `CODEX_OSS_BASE_URL` and `CODEX_OSS_PORT`, with `CODEX_HOME=codex_home`;
  - `permission_mismatch(argv, env, codex_home, *, codex, prompt, model)`, an exact-argv allowlist and not a denylist (research R6, plan-review F-002): true unless `argv == fallback_argv(codex, prompt, model)` token for token, and `env` holds only the names `confined_env` keeps plus `CODEX_HOME == codex_home` and none of the three endpoint variables. The comparison is on the inner Codex argv, before `confined_argv` or the systemd scope wraps it. No token list is maintained;
  - `parse_events`: raises `EventError` on an unparsable stream; `complete` only when every turn reported usage.
- [ ] T013 [US1] Implement `probe(setting, *, root, autonomous, codex, prompt)` in `tools/spec_workflow/fallback.py` (depends on T012, T037). It runs research R5 checks 5 to 11 and 11a in order, under one 10 s deadline, with `urllib.request.build_opener(ProxyHandler({}))`, a per-request timeout capped by the remaining budget, and a 1 MiB response cap:
  1. the probes use only `OLLAMA_ENDPOINT`, and the built environment holds none of `CODEX_OSS_BASE_URL`, `CODEX_OSS_PORT` and `OLLAMA_HOST` (else `privacy-exclusion`), so the probes check exactly the endpoint Codex will use;
  2. `GET /api/version` answers and is at least `MIN_OLLAMA_VERSION` 0.13.4 (`ollama older than 0.13.4`, or `ollama version unknown`);
  3. `GET /api/tags` lists the exact name with a nonzero size and digest;
  4. there is no `remote_host`/`remote_model` in the tag entry or in `POST /api/show`, and no cloud tag;
  5. a trusted `codex` via `autonomy.trusted_program`, whose `codex exec --help` lists `--oss` and `--local-provider`; and, when `codex_prompt(prompt)` starts with `$<command>`, the project's Codex skill for that command at the path T001 recorded (a regular file inside `root`, checked with `lstat`, never followed through a symlink); a missing skill refuses as `incompatible-capability` with the detail `codex skill <command> is not installed`;
  6. Codex's sandbox starts: `autonomy.codex_sandbox_nests` for Autonomous, and for human-gated the same `codex sandbox` probe without bubblewrap, added as a helper in `tools/spec_workflow/autonomy.py` if none exists;
  7. no Codex configuration layer outside the private home exists among those T001 found, and the layer list is known; and `~/.agents/skills` in the operator's home is absent or an empty directory (`lstat`, never followed through a symlink; a non-empty directory, a symlink or an unreadable one refuses as `permission-mismatch` with the detail `user skills directory is not empty`, plan-review F-003);
  8. the model's served context is at least `MIN_SERVED_CONTEXT` (16384; the pilot's trivial prompt needed 11905 input tokens), read from `POST /api/show` `parameters` (`num_ctx NNNN`); a missing `num_ctx`, which means the server default, counts as unknown and refuses (T037, DEC-0004).

  It returns the fixed refusal reason with a fixed detail phrase, or `None`.
- [ ] T014 [US1] Wire the selected path into `tools/spec_workflow/agent.py` (depends on T013):
  - Read the setting. A `SettingError` prints one line and counts as off.
  - When the setting is on:
    - capture a `_real_executable` failure as `cli-unavailable` instead of returning early;
    - take `fallback.state_evidence` before the primary `_attempt`;
    - after the attempt, call `fallback.classify`.
  - Consider the fallback only when all of these hold: the run is not Chat; the cause is recoverable; this is the step's first attempt (`attempt == 1` and no refused draft before it).
  - Then compare the state evidence, run `probe` (passing the step's prompt) and `permission_mismatch`, and call `_autonomous_run` to count the step; an exhausted limit takes the existing limit path. Then run exactly one `_attempt(..., fallback=setting)`.
  - Add the `fallback` keyword to `_attempt`:
    - fallback argv and environment, `integration="codex"`;
    - a fresh 0700 `CODEX_HOME` inside the attempt's private directory (one is created for a human-gated step), exposed as the Codex home under bubblewrap through the existing agent-home overlay, and removed afterwards;
    - `--json` parsing for `BLOCKING` and terminal output;
    - the timeout: Autonomous remaining wall time or 3600 s;
    - `route`, `provider` and `model` in `meta.json`;
    - the same scope, subreaper, confinement, protected-state, tamper and draft-snapshot code path as a primary attempt.
  - Write `local_fallback: true` into every step's `meta.json` while the setting is on.
  - A fallback that exits 0 with a refused draft ends with `EXIT_LIMIT`, `limit: "retries"` and `draft refused after the local fallback: <message>`, and is never retried.
  - Update the module docstring. With the setting off, nothing new runs.

**Checkpoint**: The US1 tests pass. The MVP falls back on quota and availability failures, reads no user Codex configuration, and is byte-for-byte unchanged when off.

---

## Phase 4: User Story 2 - An ineligible fallback is refused before any content leaves the wrapper (Priority: P1)

**Goal**: Each refusal cause, a changed or uncheckable state, a draft-retry attempt and every non-recoverable failure stop the fallback before any prompt or content is sent, with a readable reason.

**Independent Test**: Run the fallback path once for each refusal cause against the recording stub. The stub sees only probe requests, the fake Codex never receives the prompt, and the step reports the cause and returns the primary's exit code.

### Acceptance tests for User Story 2

- [ ] T015 [US2] Add US2 tests to `tests/test_fallback.py` [AC-005, AC-006, AC-007, AC-008, AC-009, AC-010, AC-013] (depends on T014):
  - `ProbeTests`:
    - `test_model_missing_refuses_unknown_free_status`, including a tag without size or digest;
    - `test_cloud_model_refuses_privacy`;
    - `test_remote_host_refuses_privacy`: `remote_host`/`remote_model` in tags or show;
    - `test_server_down_refuses_capability`;
    - `test_codex_without_oss_refuses_capability`;
    - `test_codex_skill_missing_refuses_capability`: a Claude-primary `/speckit-plan` step in a project with no `.agents/skills/speckit-plan/SKILL.md`, and the same with that path as a symlink out of the worktree. Both refuse with `incompatible-capability`, use no agent step and never start the fake Codex with the prompt;
    - `test_sandbox_not_nesting_refuses_capability`, in both modes;
    - `test_probe_deadline_refuses`: a slow stub exhausts the 10 s budget (patched clock) and the result is `incompatible-capability`;
    - a proxy environment (`http_proxy`) that does not redirect a probe.
  - `PermissionTests`:
    - `test_wider_argv_refused`: the comparison is an exact-argv allowlist, so each case alters the argv `fallback_argv` builds and must refuse. One case per widening flag: `--approve-for-me`, `--enable X`/`--disable X`, `--worktree`, `--ignore-user-config`, `-p`/`--profile`, `--ignore-rules`, `--strict-config`, `--add-dir`, `--sandbox danger-full-access`, `--dangerously-bypass-approvals-and-sandbox`, `--dangerously-bypass-hook-trust`, any `-c`/`--config` key (including `network_access=true`, a non-empty `writable_roots` and `model_providers.ollama.base_url`), a repeated `--oss`, `-m` or `--local-provider`, and a flag nobody listed (`--some-future-flag`). Also one case each for a removed token, a reordered token and a changed model. The unchanged argv passes;
    - `test_extra_env_refused`, including a `CODEX_HOME` other than the private one;
    - `test_endpoint_override_env_refused`: `CODEX_OSS_BASE_URL`, `CODEX_OSS_PORT` or `OLLAMA_HOST` in the built environment refuses as `privacy-exclusion`, and `fallback_env` strips all three from a parent environment that has them;
    - `test_user_skills_dir_refuses` [plan-review F-003]: a non-empty `~/.agents/skills`, a symlink there and an unreadable one each refuse as `permission-mismatch` before the prompt is sent, in both modes. An absent and an empty directory pass. The project's own `.agents/skills` does not count;
    - `test_other_codex_config_layer_refuses`: a system or project Codex config layer that sets `mcp_servers`, `notify` or `profile`, or an unknown layer list, refuses with `permission-mismatch`.
  - `ClassifyTests` non-recoverable cases: `EXIT_BLOCKED`/`BLOCKED_*`, `EXIT_TAMPERED`/not contained, `EXIT_LIMIT`/timeout, `EXIT_INTERRUPTED`, a refused draft, exit 0, unknown text, and a signature present only before the last 64 KiB.
  - `WrapperFallbackTests`:
    - `test_changed_tree_refuses`, `test_created_draft_refuses` and `test_changed_reviews_refuses`;
    - `test_ignored_path_change_refuses`: the primary writes only a git-ignored file before its quota failure;
    - `test_primary_commit_refuses`: the primary commits, leaving the working tree equal;
    - `test_unverifiable_state_refuses`: the ignored walk exceeds its cap;
    - `test_non_recoverable_never_falls_back`;
    - `test_retry_attempt_never_falls_back` (Autonomous): a draft refused on attempt 1, then a quota failure on attempt 2. No fallback, the step ends as today, at most the existing draft-retry attempts and no fallback attempt.

    Each of the first five runs in human-gated and Autonomous modes.
  - A refusal test asserts that the stderr line `local fallback refused: <reason>: <detail>` holds no output or prompt text, and that the step returns the primary's exit code.

  Every refusal asserts that the stub saw only probe requests and the fake Codex never received the prompt.

### Implementation for User Story 2

- [ ] T016 [US2] Implement the refusal path in `tools/spec_workflow/agent.py` (depends on T015):
  - Compare the before and after `fallback.state_evidence` of research R3. When either is `None`, or the two differ, refuse with `changed-state` before any probe (details `worktree state changed` or `worktree state could not be checked`).
  - On any refusal:
    - print `local fallback refused: <reason>: <detail>` to stderr;
    - record `fallback: {"decision": "refused", "reason": ...}` on the primary entry;
    - append the entry and return the primary's exit code.
  - Never consider the fallback for a non-recoverable cause, a Chat run or a draft-retry attempt. A recoverable cause on a retry attempt only sets `failure_cause` on the entry.
- [ ] T017 [P] [US2] Bring `probe` and `permission_mismatch` in `tools/spec_workflow/fallback.py` to the T015 cases (depends on T015). Each check returns its reason from the fixed table of [contracts/wrapper-fallback.md](contracts/wrapper-fallback.md#refusal-reasons-fixed), with a fixed detail phrase such as `model qwen3:4b is not installed` or `eligibility checks timed out`. Any exception or unknown answer from a check refuses rather than passes.

**Checkpoint**: The US1 and US2 tests pass, and no refusal sends content.

---

## Phase 5: User Story 3 - Every attempt is visible in the existing run ledger (Priority: P2)

**Goal**: The ledger and step records show the failed primary, the decision, and the fallback attempt with its usage. Nothing is duplicated and no account detail is stored. A fallback review is never cross-provider, in Autonomous or human-gated runs.

**Independent Test**: After a simulated selected, refused and failed fallback, read the ledger report and the step records. Then re-run the record step and a retried step, and see no duplicate.

### Acceptance tests for User Story 3

- [ ] T018 [US3] Add US3 tests to `tests/test_fallback.py` [AC-011, AC-012, AC-013, AC-014, AC-015, AC-016, AC-017] (depends on T004, T016, T017):
  - `LedgerFallbackTests`:
    - `test_selected_records_both_routes_and_usage`: a primary `route` with `failure_cause` and `fallback: selected`, attempt n; a fallback `route` with `provider: ollama`, the model, `route_source: fallback`, attempt n+1 and the same `cause_id`; a `usage` event with `counter_source: codex-exec-json` and the SHA-256 of `usage.json` as `counter_digest`; event IDs `fallback:<step>:<attempt>:route|usage`;
    - `test_refusal_recorded_with_reason`: one case per reason, including `changed-state` for an uncheckable state;
    - `test_retry_attempt_records_cause_only`: a primary `route` with `failure_cause` and no `fallback` field;
    - `test_repeated_record_is_idempotent`;
    - `test_human_gated_review_by_fallback_not_cross_provider`: a human-gated run whose `ballast-review` step completed on the fallback. Its review event names another `reviewer_provider`, yet the report shows `cross_provider_reviews: 0`, `cross_provider: false` per review and `fallback_reviews: 1`. A run with a fallback only on an author step keeps its cross-provider count;
    - a check that no event or entry holds account, quota or credential text.
  - `WrapperFallbackTests`:
    - `test_failed_fallback_stops`: no third attempt, both attempts in the ledger, outcome `mechanical-failure`, `rejected`, or `incomplete` on a timeout;
    - `test_refused_fallback_draft_not_retried`;
    - `test_retried_step_single_effect`: outputs, drafts and ledger events appear once;
    - `test_step_limit_blocks_fallback`: Autonomous; the existing limit refusal, no fallback `route`;
    - `test_fallback_counts_a_step`;
    - a `cli-unavailable` primary is recorded with `ran: false` and counts no step.
  - The optional `steps.jsonl` fields (`failure_cause`, `fallback`, `route`, `provider`, `model`, `local_fallback`) are present as in [data-model.md](data-model.md#attempt).
  - `ArtifactsFallbackTests.test_review_by_fallback_not_cross_provider` (Autonomous): `cross_provider` is false, and the draft's `agent.provider`/`agent.model` come from the entry, not from the agent-reported model.

### Implementation for User Story 3

- [ ] T019 [US3] Implement `record(root, run_id, feature, events)` in `tools/spec_workflow/fallback.py` (depends on T018):
  - append the primary and fallback `route` events and the fallback `usage` event through `ledger.append`, with source `runner`, `stage` the command label, `cause_id` the primary step ID and the fixed event IDs;
  - write `usage.json` in the fallback step's log directory;
  - record no usage when the stream was unparsable.
- [ ] T020 [US3] Call `fallback.record` from `tools/spec_workflow/agent.py` for every case of [contracts/ledger.md](contracts/ledger.md#events-per-case): refused, selected, succeeded, failed, and a recoverable cause on a retry attempt (depends on T019). Add the optional `steps.jsonl` fields: `failure_cause`, `fallback`, `route`, `provider`, `model`, and `local_fallback: true` on every entry while the setting is on; `ran: false` for a `cli-unavailable` primary. Write nothing new when the setting is off or the cause is not recoverable.
- [ ] T021 [P] [US3] In `tools/spec_workflow/artifacts.py`, for a step entry with `route: "fallback"`, set the review entry's `cross_provider` to false. Set the draft's `agent.provider` and `agent.model` to the entry's `provider` and `model` (depends on T018).
- [ ] T022 [P] [US3] Make the step-entry readers in `tools/spec_workflow/autonomy.py` accept the new optional `steps.jsonl` fields, without changing the validation of existing entries (depends on T018).
- [ ] T023 [P] [US3] Implement the review provenance rule in `ledger.report` (`tools/spec_workflow/ledger.py`), per [contracts/ledger.md](contracts/ledger.md#report) (depends on T018). The rule applies when the run holds a runner `route` with `route_source: fallback`, `outcome: success` and a `ballast-review` stage:
  - `cross_provider_reviews` is 0;
  - every `review_provider_availability` and `outcome.reviews` item has `cross_provider: false`;
  - `routing.fallback_reviews` counts those routes.

**Checkpoint**: The US1 to US3 tests pass, and the ledger alone tells the fallback story in both modes.

---

## Phase 6: User Story 4 - The operator opts in to a backend chosen from evidence (Priority: P2)

**Goal**: The operator enables, changes and disables the fallback from `ballast run`. The run record shows it in both modes, and agents cannot touch it. The evaluation and documentation justify and explain it.

**Independent Test**:
- `ballast run start --local-fallback qwen3:4b` writes the setting outside the checkout and prints the on line.
- `ballast run status RUN` shows it.
- `resume RUN --local-fallback off` turns it off.
- Chat refuses the flag.
- The evaluation record and documentation cover the candidate, the alternatives, the refusals and the exit path.

### Acceptance tests for User Story 4

- [ ] T024 [US4] Add `RunCliTests` to `tests/test_fallback.py` [AC-019, AC-020, AC-021] (depends on T007, T018):
  - `test_start_and_resume_flags`:
    - `--local-fallback MODEL`, the `--name=value` form, and resume with a model and with `off`;
    - `--local-fallback-endpoint` in either form is refused on start and resume with exit 2 and nothing written (DEC-0003);
    - the printed lines `Local fallback: on (ollama MODEL at 127.0.0.1:11434); turn it off with ballast run resume RUN --local-fallback off` and `Local fallback: off`;
    - an absent flag keeps the stored setting, a value after `-i` is an input value, and a repeated flag is refused.
  - Each refusal of [contracts/operator-cli.md](contracts/operator-cli.md#start) exits 2 before any engine or agent starts, and writes nothing.
  - `test_chat_refuses_flag`, for start and resume.
  - `test_setting_outside_checkout`: `fallback.json` is under `$XDG_STATE_HOME`, and is refused when the state directory resolves inside the checkout. No environment variable or `ballast.toml` key enables the fallback.
  - `test_status_shows_setting`: `ballast run status RUN` prints `Local fallback: on (ollama MODEL)` and, after `off`, `Local fallback: off`, for a human-gated and an Autonomous run. Its output is unchanged when no `fallback.json` exists.
  - `test_human_gated_meta_records_setting`: each human-gated step's `meta.json` has `local_fallback: true` while the setting is on, and no such field when it is absent.
  - `WrapperFallbackTests.test_chat_step_never_falls_back`: the `run_interactive` path is untouched by a quota failure.
- [ ] T025 [P] [US4] Add to `tests/test_autonomous_run.py` [AC-003, AC-020] (depends on T022):
  - the `record.md` "Mode and risk" section shows `- Local fallback: off` and `- Local fallback: on (ollama MODEL)`;
  - an Autonomous run without the setting renders `record.md` and `steps.jsonl` exactly as before.

### Implementation for User Story 4

- [ ] T026 [US4] Add `--local-fallback` (and no endpoint option, DEC-0003) to `tools/spec_workflow/run.py` (depends on T024):
  - parse them in `_split_mode` and in the human-gated and Autonomous resume option parsing, with the `--mode` rules;
  - refuse Chat and the invalid cases with the fixed messages, and exit 2 before anything starts;
  - call `fallback.write_setting` before the engine starts, and print the on/off line;
  - add the `Local fallback:` line to `ballast run status` when `fallback.json` exists (an invalid file counts as off);
  - update the usage text.
- [ ] T027 [US4] Add the `- Local fallback: off|on (ollama MODEL)` line to the "Mode and risk" section of the `record.md` renderer in `tools/spec_workflow/autonomy.py`, read from `fallback.read_setting` (an invalid setting counts as off) (depends on T022, T025).
- [ ] T028 [US4] Complete `specs/23-free-fallback/evaluation.md` [AC-018] (depends on T001, T014, T016). It covers:
  - the candidate: Codex CLI local-provider mode against loopback Ollama;
  - the alternatives and their rejection reasons, from research R1;
  - the host versions;
  - each pilot probe from T001, with command, outcome and context (operator terminal or confined step);
  - the sandbox-nesting result in both modes;
  - the Codex configuration layers found and the empty-`CODEX_HOME` run;
  - the Codex Spec Kit skill path, and that a project needs Spec Kit's Codex integration installed for a fallback to run (otherwise it refuses as `incompatible-capability`);
  - the raw `codex exec --json` run's duration, outcome and usage;
  - the R2 signatures adopted, with their redacted sources, and any cause left `unrecognized`;
  - the expected Autonomous refusal per DEC-0004 of the run record;
  - the decision.

  Note that the workflow runs quickstart pilot steps 3 to 5 and appends them there.
- [ ] T029 [P] [US4] Add a "Local fallback" subsection to `templates/policies/spec-kit-workflow.md` [AC-019] (depends on T016, T026). It covers:
  - how to enable it with `--local-fallback MODEL`, that it always uses Ollama's default endpoint `127.0.0.1:11434` and a local model served with a context of at least 16384 tokens (for example a `num_ctx 16384` variant), that Ollama must be 0.13.4 or newer, and that the project needs Spec Kit's Codex integration installed (a missing Codex skill refuses as `incompatible-capability`);
  - what each refusal reason means, including `changed-state` for an uncheckable worktree and `permission-mismatch` for a Codex configuration layer or a non-empty `~/.agents/skills` (empty it, or leave the fallback off);
  - that it applies only to a step's first attempt;
  - how to turn it off: `resume RUN --local-fallback off`, or start without the flag;
  - where the setting shows: `ballast run status`, `record.md`, and the step's `meta.json`;
  - that it is never available in Chat runs, never routes to a paid or remote backend, never reads the user's Codex configuration, never runs while the user's skills directory is non-empty and never loosens a sandbox;
  - where to read the evidence: `./scripts/agent-metrics --run RUN`.
- [X] T030 [P] [US4] Add one paragraph to `templates/policies/model-routing.md` [AC-016, AC-019]: the local fallback is a zero-cost availability route, not a routing profile, and a review it completes never counts as cross-provider review.
- [ ] T031 [P] [US4] Add one line about `--local-fallback` under the `ballast run` options in `README.md`, linking the spec-kit-workflow subsection (depends on T026).

**Checkpoint**: All four stories pass independently.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [ ] T032 [P] Write `docs/adr/0012-local-zero-cost-fallback.md` with status proposed; it is accepted only when the PR merges (depends on T028). It records:
  - the decision of plan.md ADR-0012 and its conditions;
  - the first-attempt-only rule and the changed-state evidence (DEC-0001);
  - the fixed default endpoint, the Ollama and served-context minimums (DEC-0003, DEC-0004) and the exact-argv comparison;
  - the runtime checks, the private `CODEX_HOME` and the permission comparison;
  - the cost of the state walk;
  - the remaining residual risk, the model-pull race;
  - the host result from T028.
- [ ] T033 [P] Update `specs/TECHNICAL-SPEC.md` sections 6.4, 6.5 and 9.1 with the qualified fallback, its checks and its refusal behavior (depends on T020, T026).
- [ ] T034 Add `ModuleTests.test_stdlib_only_no_model_list` to `tests/test_fallback.py` [FR-009, FR-011] (depends on T017, T024). `tools/spec_workflow/fallback.py` imports only standard-library modules and `autonomy`/`ledger`, and imports cleanly under `python3 -I -S`. No model name, apart from test fixtures, appears in `fallback.py`, `agent.py` or `run.py`.
- [ ] T035 Write `specs/23-free-fallback/acceptance-evidence.json` in the format of earlier features' evidence files (depends on T005, T020, T021, T023, T025, T027, T028, T029, T030, T031, T032, T033, T034). It maps:
  - AC-001 to AC-021 and SC-001 to SC-005 to the tests of T003, T006, T008, T010, T015, T018, T024, T025 and T034;
  - the same criteria to the evaluation record and documentation of T028 to T031;
  - FR-009 and FR-011 to T034.
- [ ] T036 Run `uvx ruff check && uvx ruff format --check` and `uv run --no-project --python 3.13 --with pyyaml python -m unittest tests/test_*.py`. Fix lint and format findings in the changed files, and confirm that the `tests/test_governance.py` link checks pass for the new documents (depends on T035).

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: T001 runs first. The pilot pins the config key, event shape, configuration layers and signatures that every later design detail depends on.
- **Foundational (Phase 2)**: The ledger work (T003 to T005) has no dependency. The setting and the state evidence (T006 to T009) need the harness (T002).
- **US1 (Phase 3)**: Needs T004 and T009, named explicitly in T010. This is the MVP.
- **US2 (Phase 4)**: Needs the US1 probe and wrapper path (T014); it adds the refusal path to the same code.
- **US3 (Phase 5)**: Needs US2 (T016, T017), because it records both selected and refused decisions, and T004 for the ledger values.
- **US4 (Phase 6)**: The CLI tests need the setting (T007) and come after the US3 tests in the shared test file (T018). The record line needs the step-entry readers (T022). The model-routing paragraph (T030) needs nothing.
- **Polish (Phase 7)**: Comes after the stories it documents. The acceptance evidence (T035) names every task whose output it maps, and the fast gate (T036) comes last.

### User Story Dependencies

- **US1 (P1)**: After Foundational. Independent.
- **US2 (P1)**: After US1. It hardens US1's decision with refusals, and the recording stub tests it independently.
- **US3 (P2)**: After US2. Recording covers every decision.
- **US4 (P2)**: Its tests and CLI need the setting (Phase 2) and the step-entry fields (US3). T030 needs nothing.

### Within Each User Story

- Tests are written first and fail before implementation.
- `fallback.py` comes before the `agent.py` integration.
- Tasks that write the same file are chained by explicit dependencies: `tests/test_fallback.py` (T002, T006, T008, T010, T037, T015, T018, T024, T034), `tools/spec_workflow/fallback.py` (T007, T009, T011, T012, T013, T017, T019), `tools/spec_workflow/agent.py` (T014, T016, T020), `tools/spec_workflow/autonomy.py` (T009, T013, T022, T027) and `tools/spec_workflow/ledger.py` (T004, T023).

### Parallel Opportunities

- Wave 1: the host pilot, the ledger tests and the model-routing paragraph touch different files.
- Waves 2 to 4: the ledger implementation and its schema document run beside the harness, the setting tests and the state tests.
- Wave 14: `fallback.record`, `artifacts.py`, the `autonomy.py` readers, the `ledger.py` report rule, the CLI tests and the ADR are six different files.
- Wave 16: the `autonomy.py` record line, the policy template, the README and the technical spec are independent.

---

## Execution Wave DAG

Tasks grouped by dependency resolution. Tasks within the same wave can run in parallel.

```text
Wave 1 (no dependencies):
  T001  Host pilot
  T003 [P] Ledger tests
  T030 [P] [US4] Model-routing paragraph

Wave 2:
  T002  Test harness (depends on T001)
  T004  Ledger implementation (depends on T003)

Wave 3:
  T005 [P] Ledger schema paragraph (depends on T004)
  T006  Setting tests (depends on T002)

Wave 4:
  T007  fallback.py setting (depends on T006)
  T008  State evidence tests (depends on T006)

Wave 5 (Phase 2 complete):
  T009  ignored/refs digests, state_evidence (depends on T007, T008)

Wave 6:
  T010  [US1] US1 tests (depends on T004, T009)

Wave 7:
  T011  [US1] classify (depends on T001, T010)
  T037  [US1] Served-context probe tests (depends on T010)

Wave 8:
  T012  [US1] argv, env, private CODEX_HOME, permission comparison, events (depends on T011)

Wave 9:
  T013  [US1] Probes, config layers, served context, deadline (depends on T012, T037)

Wave 10:
  T014  [US1] Wrapper selected path (depends on T013)

Wave 11:
  T015  [US2] US2 tests (depends on T014)

Wave 12:
  T016  [US2] Wrapper refusal path (depends on T015)
  T017 [P] [US2] Probe phrases and fail-closed checks (depends on T015)

Wave 13:
  T018  [US3] US3 tests (depends on T004, T016, T017)
  T028  [US4] Evaluation record (depends on T001, T014, T016)

Wave 14:
  T019  [US3] fallback.record (depends on T018)
  T021 [P] [US3] Autonomous review provenance (depends on T018)
  T022 [P] [US3] Step-entry readers (depends on T018)
  T023 [P] [US3] Ledger report review rule (depends on T018)
  T024  [US4] CLI, status and meta tests (depends on T007, T018)
  T032 [P] ADR-0012 (depends on T028)

Wave 15:
  T020  [US3] Wrapper recording (depends on T019)
  T025 [P] [US4] record.md tests (depends on T022)
  T026  [US4] run.py flags and status line (depends on T024)
  T034  Stdlib and no-model-list test (depends on T017, T024)

Wave 16:
  T027  [US4] record.md line (depends on T022, T025)
  T029 [P] [US4] Workflow policy subsection (depends on T016, T026)
  T031 [P] [US4] README line (depends on T026)
  T033 [P] Technical spec (depends on T020, T026)

Wave 17:
  T035  Acceptance evidence (depends on T005, T020, T021, T023, T025, T027, T028, T029, T030, T031, T032, T033, T034)

Wave 18:
  T036  Fast gate (depends on T035)
```

---

## Implementation Strategy

### MVP First (User Story 1)

1. T001 pilot: stop and record a discovery if the candidate fails it.
2. Phase 2: ledger additions, the setting and the state evidence.
3. Phase 3: US1. **Stop and validate**: the US1 tests and the off-path regression pass.

### Incremental Delivery

1. US1: the fallback runs and completes on quota and availability failures.
2. US2: every refusal, including a changed or uncheckable state and a draft-retry attempt, is proven to send nothing. US1 plus US2 is the minimum shippable R2 boundary; do not open the PR without both.
3. US3: ledger and step evidence, idempotency, the step limit, and review provenance in both modes.
4. US4: the operator CLI, the status and record lines, the evaluation record and the documentation.
5. Polish: the ADR, the technical spec, the stdlib check, the acceptance evidence and the fast gate. The workflow then runs the full local gate, the quickstart pilot, the reviews, converge and reconciliation.

---

## Notes

- Never loosen either sandbox, add a writable root, a bypass flag or tool network, read the user's Codex configuration, or add an endpoint option or a `-c model_providers.ollama.*` key, to make the fallback run (FR-005, DEC-0003). A check that cannot be established refuses.
- A pilot result that contradicts research R1 to R10 is a discovery for `decisions.md`, not a silent design change.
- No account, quota, credential, prompt or agent output text goes into a ledger event, step entry, `meta.json` field, stderr refusal line or fixture.
- Commit after each task or logical group with a Conventional Commit message.
