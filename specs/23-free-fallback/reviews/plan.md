# Plan review: Qualify one zero-cost provider fallback

- Review: plan (independent, agent-provisional), rerun after the contradiction block at `decide-tasks` was resolved (DEC-0001, HD-0001)
- Reviewer: claude/claude-opus-5-5, fresh context
- Artifacts: `plan.md`, `research.md` (R1 to R10), `data-model.md`, `contracts/operator-cli.md`, `contracts/wrapper-fallback.md`, `contracts/ledger.md`, `quickstart.md` and `decisions.md` (DEC-0001), checked against `spec.md` (AC-001 to AC-021, FR-001 to FR-011, SC-001 to SC-005), `intent.md` and the run record. `tasks.md` exists but is out of scope for this review; the tasks gate judges it.
- Policies: `AGENTS.md` invariants, `docs/policies/workflow.md` (risk and review matrix), `docs/policies/engineering.md` via the engineering review skill, and the R2 boundaries in `docs/policies/project/workflow.md`.

## What was checked

**The DEC-0001 resolution keeps the spec.** The plan now matches the spec as written:

- The fallback is considered only after the step's first primary attempt. It is never followed by a draft retry or by another fallback (R9, the `agent.main` flow, the data-model decision tree). A step that falls back makes exactly two attempts, which meets SC-005 and FR-006 without reinterpreting them.
- The changed-state evidence now covers git-ignored worktree paths (an `lstat` metadata digest that includes `ctime_ns`) and `HEAD` plus every ref. When the evidence cannot be established, the fallback is refused as `changed-state` (R3). This closes the residual risk of replaying a partial mutation, which the spec lists as a non-goal (AC-009, FR-003).
- The earlier F-003 (the `route_source: fallback` cross-field rule) is now identical in `data-model.md` and `contracts/ledger.md`.
- The earlier F-004 now has a defined human-gated run record: `fallback.json` is kept after `off`, `ballast run status` prints a line, each step's `meta.json` carries `local_fallback`, and the ledger holds `route` events.

**F-001 of the earlier review is closed by design.** The fallback runs with a fresh, wrapper-owned, empty `CODEX_HOME` inside the attempt's private directory. `agent.py` already creates a private `mkdtemp` directory per attempt, so this applies in both modes. R5 check 11 refuses with `permission-mismatch` when any other Codex configuration layer exists, or when the pilot could not establish the list of layers. `permission_mismatch` allows `CODEX_HOME` only with that private path. With no user configuration read, the fallback gets no MCP servers, `notify` program or profiles, so it cannot be wider than a Claude primary.

**Requirement coverage.** Every AC, FR and SC maps to a design element and to a planned test or artifact in `quickstart.md`. The new DEC-0001 tests are mapped: `test_retry_attempt_never_falls_back`, `test_ignored_path_change_refuses`, `test_primary_commit_refuses`, `test_unverifiable_state_refuses`, `test_user_codex_config_not_read`, `test_other_codex_config_layer_refuses`, `test_probe_deadline_refuses`, the human-gated provenance and status tests, and `test_stdlib_only_no_model_list` for FR-009 and FR-011.

**Code anchors spot-checked.**

- `agent.permission_args` pins Codex to `workspace-write`, network off and no extra writable roots, and gives Claude `--strict-mcp-config` with project-only settings. The canonical profile R6 compares against therefore exists.
- The wrapper takes the run ID from `SPECKIT_WORKFLOW_RUN_ID`, which it does in both modes, so `read_setting(root, run_id)` works for human-gated steps.
- `autonomy.run_dir` sits under `state_dir`, outside the checkout.
- The headless Claude settings allow no write outside the checkout, and Codex's writable roots are pinned. So in a human-gated run, as well as under bubblewrap, no agent can write `fallback.json` (AC-020).
- `autonomy.agent_homes` overlays the `CODEX_HOME` named in the environment, which R6 relies on under bubblewrap.
- `ledger.py` derives `cross_provider` from `reviewer_provider`, which the R8 report rule overrides conservatively for runs that hold a fallback review route.

**Boundaries and failure behavior.**

- Source authority stays single: the launcher owns the setting, the wrapper owns attempts and their records, and the ledger is the only record.
- The off path takes no digests, runs no probes and writes nothing, and a test compares argv, `steps.jsonl` and the ledger with and without the feature.
- The probes send only the model name, through a proxy-less opener, to a loopback IP literal. They share a 10 s deadline and fail closed.
- Codex's sandbox is never loosened. On this host an Autonomous step is expected to refuse as `incompatible-capability` (DEC-0004), and SC-004 accepts that outcome.
- Bytecode writes cannot trip the ignored-path digest, because the wrapper already sets `PYTHONPYCACHEPREFIX` away from the tree.

**Unnecessary complexity.** The plan adds one new stdlib module and makes small additive changes elsewhere. It adds no adapter layer, no new store and no model list. The ignored-path walk is the main new cost: it runs only while the setting is on, is capped, and a refusal only means a missed fallback. ADR-0012 is the right place to record the boundary.

**Remaining gap.** The plan has one minor capability gap, recorded in the draft. In a Claude-primary run, `codex_prompt` turns `/speckit-x` into `$speckit-x`, but no probe checks that the project has Codex's Spec Kit skill for that command installed. In a project with only the Claude integration installed, the fallback would start, use an agent step and fail its postconditions. Content stays on loopback, so this is a wasted attempt, not a boundary breach.

## Uncertainty

Host facts stay unknown until the R10 pilot: the Codex `--config` key for the Ollama base URL, the `--json` event shape, the Codex configuration layers, sandbox nesting, and the quota message text. Every check that depends on one of them fails closed. If no quota signature can be pinned, the plan records that as a discovery, because AC-001 could then never be met on a real run. I did not run Codex or Ollama, and I did not review `tasks.md`.

<!-- ballast-findings: begin -->
## Findings (recorded from the review draft)

- F-001 (low, architecture-issue, open): In a Claude-primary run, codex_prompt maps /speckit-x to $speckit-x, but no R5 check confirms the project has Codex's Spec Kit skill for that command installed. In a project with only the Claude integration installed, the fallback would start, use an agent step and fail its postconditions. Content stays on loopback, so no boundary is crossed. A task could add an incompatible-capability refusal when the Codex skill is missing, or the pilot and evaluation.md could state the Codex integration as a prerequisite.
<!-- ballast-findings: end -->
