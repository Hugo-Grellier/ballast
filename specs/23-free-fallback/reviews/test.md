# Test review: local zero-cost fallback (#23)

- Review: tests. Agent-provisional, run during the operator's human-gated continuation of Autonomous run `f200c320` (not human approval).
- Reviewer: claude/claude-sonnet-5-5, driving agent (reduced independence).
- Method: `.agents/skills/ballast-test-review/SKILL.md` and `docs/policies/testing.md`; `specs/23-free-fallback/acceptance-evidence.json` against `spec.md` AC-001 to AC-021 and SC-001 to SC-005; `tests/test_fallback.py` (76 tests before this review, 77 after, plus new cases inside existing tests), the additions to `test_autonomous_run.py` and `test_governance.py`; the live check.

## Coverage map

| Criteria | Evidence |
| --- | --- |
| AC-001, AC-002 | `WrapperFallbackTests.test_quota_failure_completes_on_fallback`, `test_provider_unavailable_completes_on_fallback`, `test_cli_missing_completes_on_fallback`; real run in [live-check.md](live-check.md) |
| AC-003 | `test_setting_off_matches_today`, `SettingTests.test_wrapper_treats_invalid_as_off`, `LocalFallbackRecordTests` |
| AC-004, AC-008 | `InvocationTests.test_fallback_argv_literal_tokens`, `PermissionTests` (each widening token, extra env, proxy and endpoint variables), `test_fallback_runs_under_same_confinement`, `ConfinementCompositionTests` |
| AC-005, AC-006, AC-007 | `ProbeTests` (missing model, cloud tag, remote host, server down, no `--oss`, missing skill, sandbox not nesting, deadline, old Ollama), `ProbeContextTests`, `LayerTests`; live refusals |
| AC-009 | `StateTests`, `RefusalTests` (tree, reviews, draft, ignored path, ref, unverifiable) |
| AC-010 | `ClassifyTests`, `test_non_recoverable_never_falls_back` |
| AC-011 to AC-017 | `LedgerFallbackTests`, `WrapperFallbackTests` (single effect, step limit, no retry), `ArtifactsFallbackTests`, `test_agent_run_ledger` additions |
| AC-018 to AC-021 | `evaluation.md`, `RunCliTests`, `HumanGatedMetaTests`, `test_chat_step_never_falls_back`, governance link checks |

All 21 criteria map to existing tests (checked mechanically: every test in `acceptance-evidence.json` exists).

## Quality of the evidence

- Denial and failure paths are tested as negatives: each refusal reason asserts nothing was sent to Codex and the stub server saw only probe requests (`assert_nothing_sent`); the wrapper tests use real `steps.jsonl` and ledger files and fake CLIs, not mocks of the code under test. The literal fallback token list is pinned, so a widening in `permission_args` fails.
- The seams that need real systemd, bubblewrap and Codex run only in the full local gate; the live check exercised the real probes, Codex and a real model.

## Findings

- F-001 (medium, missing-test): nothing tested the real `confined_argv` composition for the fallback after #89 (fake `bwrap` only). Required: assert that the fallback's Codex step gets the private home overlay, the Claude homes emptied and no Claude login copy.
- F-002 (high, missing-test): no test pinned that the operator's proxy variables never reach the fallback and that the environment is exactly the allowlist (security F-001, F-002).
- F-003 (low, missing-test): cloud detection by `remote_model`/`remote_host` is fixture-driven; no cloud tag could be pulled on the host (Ollama sign-in). The pilot says so. Accepted.
- F-004 (low, missing-test): the Claude subscription quota message signature comes from the CLI's own strings, not a capture. Accepted; an unmatched message is `unrecognized` and never falls back.

## Resolution

- F-001: fixed test-first (`ConfinementCompositionTests.test_fallback_step_shows_the_private_home_and_hides_claude`), mapped to AC-004 in `acceptance-evidence.json`.
- F-002: fixed test-first (`test_fallback_env`, `test_extra_env_refused` with proxy, FTP and mixed-case cases, `BLACKHOLE` removal subtests); mapped to AC-006.
- F-003, F-004: accepted.

- Verdict: approved
