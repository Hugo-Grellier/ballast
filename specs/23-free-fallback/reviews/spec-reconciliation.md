# Spec reconciliation: local zero-cost fallback (#23)

- Reviewer: claude/claude-sonnet-5-5, driving agent, during the operator's human-gated continuation of Autonomous run `f200c320` (not human approval); the same provider family as the implementation (reduced independence)
- Inputs: `spec.md`, `plan.md`, `research.md`, `data-model.md`, the contracts, `tasks.md` (37 of 37 done), `decisions.md` (DEC-0001 to DEC-0004), `evaluation.md`, `acceptance-evidence.json`, the diff from `origin/main`, ADR-0014, the policy, README and technical-spec changes, `tests/test_fallback.py` and its siblings, and the reviews in this directory including [live-check.md](live-check.md)

## Criterion to evidence

| Criteria | Implementation | Executable evidence |
| --- | --- | --- |
| AC-001, AC-002, SC-001 | `agent.main` (classify, `_fallback_step`, `_attempt_in(route=...)`), `fallback.classify`, `codex_prompt` | `WrapperFallbackTests` (quota, availability, CLI missing), `ClassifyTests`; real completion in [live-check.md](live-check.md) |
| AC-003, FR-001 | `fallback.read_setting` (absent or invalid is off), `_fallback_setting` | `test_setting_off_matches_today`, `SettingTests` |
| AC-004, FR-005 | `fallback_argv` from `permission_args("codex", ...)`, `confined_env`, the shared `_attempt_in` | `InvocationTests` (literal tokens), `test_fallback_runs_under_same_confinement`, `ConfinementCompositionTests` (#89) |
| AC-005, AC-006, AC-007, FR-004 | `fallback.probe` (checks 5 to 11 and 11a) | `ProbeTests`, `ProbeContextTests`, `LayerTests`; live refusals |
| AC-008 | `permission_mismatch` (exact allowlist) | `PermissionTests` |
| AC-009 | `state_evidence`, `changed_state`, `autonomy.ignored_digest`, `refs_digest` | `StateTests`, `RefusalTests`; live `changed-state` |
| AC-010, FR-002 | `classify` (tail-only signatures) | `ClassifyTests` |
| AC-011 to AC-014, AC-017, FR-007, SC-003 | `route` and `usage` events with fixed IDs, ledger enums and cross-field rules | `LedgerFallbackTests`, `test_agent_run_ledger` additions; live ledger |
| AC-013, FR-006, SC-005 | first-attempt-only gate, no retry | `test_failed_fallback_stops`, `test_refused_fallback_draft_not_retried`, `test_retry_attempt_never_falls_back` |
| AC-015 | `_autonomous_run` counts the fallback | `test_fallback_counts_a_step`, `test_step_limit_blocks_fallback` |
| AC-016 | `artifacts._validate_review`, `ledger._fallback_reviews` | `ArtifactsFallbackTests`, `test_human_gated_review_by_fallback_not_cross_provider` |
| AC-018, FR-010 | `evaluation.md` (candidate, alternatives, pilot items 1 to 10) | `test_governance` evaluation and ADR checks |
| AC-019, SC-004, FR-010 | policy "Local fallback" section, README, `run.py` usage | `LocalFallbackDocumentTests`, `RunCliTests.test_start_and_resume_flags` |
| AC-020, FR-001 | operator-directory setting, record and status lines | `RunCliTests`, `HumanGatedMetaTests`, `LocalFallbackRecordTests` |
| AC-021 | Chat steps use `run_interactive`, never `agent.main` | `test_chat_step_never_falls_back`, `test_chat_refuses_flag` |
| FR-003, FR-008 | refusals return the primary's code with a readable reason; no paid backend | `RefusalTests`, `ModuleTests` |
| FR-009, FR-011, SC-002 | no model list; stdlib only; probes send only the model name | `ModuleTests.test_stdlib_only_no_model_list`, `assert_nothing_sent` |

## Behavior beyond or against the spec

- **Beyond the spec, narrowing only.** The wrapper also refuses on a non-empty `~/.agents/skills`, a project `.codex/config.toml`, a served context below 16384 and an Ollama older than 0.13.4. Each only refuses more; DEC-0003 and DEC-0004 record the endpoint and context. The proxy handling added by this reconciliation's security review (operator proxies removed, every proxy-aware request pointed at a closed local port) narrows too: it removes ways for content to leave and adds none.
- **Stale assumption.** The spec's assumption that "confined steps keep the host network, so a loopback model server is reachable" holds, and the live check found its corollary: the Codex CLI itself uses that network for its own start-up requests (`github.com`, `chatgpt.com`). That is new knowledge, not a spec change: FR-004 and AC-006 concern where the prompt and repository content go, which is the fixed loopback endpoint; the mitigation and its limit are in ADR-0014, the policy and the technical spec. No product behavior, scope or boundary changed, so no `decisions.md` proposal is needed.
- **Documentation drift fixed.** The policy named a refusal the wrapper cannot produce (`OLLAMA_HOST`) and a command this repository does not ship (`./scripts/agent-metrics`); both corrected, with the governance test updated to pin the corrected text.
- **ADR number.** The plan, tasks and run record say ADR-0012; the file is ADR-0014, whose header says why. Those artifacts are digest-bound to recorded reviews and are left as they are.
- **Architecture.** ADR-0014 is proposed and extends ADR-0003 and ADR-0010 without changing an accepted decision. No existing decision is contradicted.

## Gaps

- Pilot quickstart steps 3 to 5 through `ballast run start --local-fallback` and `--mode autonomous` were not run (no ballast command runs in this worktree). The operator-side equivalent through the real wrapper is in [live-check.md](live-check.md); an Autonomous fallback is covered offline only, and the expected host result is an `incompatible-capability` refusal. This is an unavailable gate, not a defect, and is listed for the operator.
- `tests.test_chat_mode.EndToEndTests.test_conversational_feature` fails with exit 130 in this agent shell on `origin/main` as well as on this branch (an interrupted pty step); it does not touch the fallback and is expected to pass on the operator's terminal.

- Verdict: CONVERGED
