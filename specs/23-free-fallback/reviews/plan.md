# Plan review: Qualify one zero-cost provider fallback

- Review: plan (independent, agent-provisional)
- Reviewer: claude/claude-opus-5-5, fresh context
- Artifacts: `plan.md`, `research.md` (R1 to R10), `data-model.md`, `contracts/operator-cli.md`, `contracts/wrapper-fallback.md`, `contracts/ledger.md`, `quickstart.md`, against `spec.md` (AC-001 to AC-021, FR-001 to FR-011, SC-001 to SC-005), `intent.md` and the run record. `tasks.md` and `decisions.md` do not exist yet, as expected at this point.
- Policies: `AGENTS.md` invariants, `docs/policies/workflow.md` (risk and review matrix), `docs/policies/engineering.md` via the engineering review skill, the R2 boundaries in `docs/policies/project/workflow.md`.

## What was checked

**Requirement coverage.** Every AC and SC maps to a planned test or artifact in `quickstart.md`. FR-001 (off by default, operator-only setting) maps to `--local-fallback` on `ballast run start|resume`, stored in `fallback.json` under the run's operator directory. FR-002 maps to the fixed cause set in R2, where anything unknown is non-recoverable. FR-003 and FR-004 map to the ordered checks in R5, which fail closed. FR-005 maps to the R6 argv and env construction plus the explicit `permission_mismatch` check. FR-006 maps to R9 and the existing `_autonomous_run` count. FR-007 maps to the additive ledger enums in R8 and `contracts/ledger.md`, with schema version 1 unchanged. FR-009 holds because the plan ships no model list. FR-010 maps to `evaluation.md` and the documentation rows. FR-011 holds because the plan uses only `urllib`, `json` and `ipaddress`.

**Code anchors.** The symbols the plan builds on exist with the shapes it assumes:

- in `tools/spec_workflow/autonomy.py`: `tree_digest`, `reviews_digest`, `codex_sandbox_nests`, `run_dir`, `trusted_program`, `confined_env`, `confined_argv` and `append_step`;
- in `tools/spec_workflow/agent.py`: `main`, `_attempt`, `permission_args`, `_real_executable`, `_autonomous_run`, `FORBIDDEN` and the `EXIT_*` codes;
- in `tools/spec_workflow/ledger.py`: the `ENUM_FIELDS`/`FIELDS` entries for `route`, the `runner` and `client-counter` sources, and the `ID`/`LABEL`/`MODEL` patterns;
- in `tools/spec_workflow/artifacts.py`: the `cross_provider` derivation that R8 corrects.

`main` returns early on `_real_executable` failure today. The plan explicitly restructures that path for `cli-unavailable` when the setting is on, and keeps the off path unchanged.

**Boundaries and failure behavior.**

- Source authority stays single: the launcher owns the setting, the wrapper owns attempts and the ledger stays the one record.
- The off path is byte-for-byte unchanged, and a test is planned to prove it.
- A refused fallback returns the primary's exit code.
- A failed fallback ends the step without a retry.
- Idempotency rests on `ledger.append`'s per-event-ID comparison.
- An HTTP probe sends only the model name, through an opener with no proxy.
- The endpoint must be a loopback IP literal. Host names, including `localhost`, are refused.
- Codex's sandbox is never loosened. An Autonomous step on this host is expected to refuse as `incompatible-capability` (DEC-0004), and SC-004 accepts that outcome.
- The plan records two residual risks: changes under git-ignored paths outside `tree_digest`, and a model-pull race.

**Unnecessary complexity.** The plan adds one new module and keeps the other changes small and additive. It adds no adapter layer and no new store, and it ships no model list. The proposed ADR-0012 is the right place for the boundary decision.

**Gaps.** Three are recorded in the draft's findings:

- The permission comparison and the privacy probes cover argv, env and the Ollama model entry, but not the user's Codex configuration file. In a Claude-primary run this can give the fallback MCP servers or a `notify` program that the primary step (`--strict-mcp-config`, project-only settings) never had.
- SC-005 ("no step ever makes more than two attempts") is reinterpreted in R9 so that the existing draft-retry loop does not count. The plan does not record that interpretation as a decision.
- The contracts disagree on one ledger cross-field rule. There is also no human-gated record of the setting when no fallback is ever considered.

None of these blocks task generation: each is a bounded change that a task can address. They are listed so that the tasks and the merge review pick them up.

## Uncertainty

Host facts are unknown until the R10 pilot. These include the exact Codex `--config` key for the Ollama base URL, the `--json` event shape, whether Codex's sandbox nests on this host, and the quota message text. Every check that depends on one of them fails closed, so an unknown result can only refuse a fallback, never send content. I did not run Codex or Ollama.

<!-- ballast-findings: begin -->
## Findings (recorded from the review draft)

- F-001 (medium, spec-violation, accepted-provisionally): R6 permission_mismatch and the R5 privacy probes inspect only argv, env and the Ollama model entry. Codex still reads the operator's config.toml (agent_homes only overlays CODEX_HOME), so its mcp_servers, notify program or profiles reach the fallback. A Claude primary runs with --strict-mcp-config and project-only settings, so the fallback can be wider than the actual primary (AC-008) and can send content off loopback through an MCP server or notify (AC-006). It does not block planning because the config is operator-owned, not agent-writable, and a task can close it: pin mcp_servers and notify empty through allowlisted --config overrides, or refuse as permission-mismatch when they are set, with tests and a pilot check.
- F-002 (low, spec-ambiguity, open): SC-005 says no step ever makes more than two attempts, but R9 reads it as two attempts beyond the existing draft-retry loop and lets a draft-retry primary fall back. That reading is reasonable, because draft retries predate this feature, but it should be recorded as a decision or a spec wording clarification rather than left implicit in research.md.
- F-003 (low, spec-ambiguity, open): The two contracts disagree. data-model.md says route_source fallback forbids failure_cause; contracts/ledger.md says it forbids failure_cause and fallback. Pick one rule before tasks are written so ledger tests have one source.
- F-004 (low, spec-ambiguity, open): AC-020 asks that the run record show whether the fallback was on. Autonomous runs get a record.md line, but a human-gated run has no record.md and writes nothing about the setting unless a fallback is considered. Its only trace is fallback.json and the printed start line. A task should state what counts as the human-gated run record.
<!-- ballast-findings: end -->
