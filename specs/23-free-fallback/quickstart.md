# Quickstart: validate the local fallback

How to show the feature works. Behavior is described in [contracts/](contracts/) and stored data in [data-model.md](data-model.md).

## Prerequisites

- Fast gate: `uv`, Python 3.13. CI runs the offline tests below.
- Full local gate and pilot: the qualified Linux host with a systemd user session, `bwrap`, the Codex CLI with `--oss`, Ollama on `127.0.0.1:11434` with `qwen3:4b` pulled, the Spec Kit CLI.

## Offline gate

```sh
uvx ruff check && uvx ruff format --check
uv run --no-project --python 3.13 --with pyyaml python -m unittest tests/test_*.py
```

Offline tests use a loopback stub Ollama server (`http.server` on an ephemeral `127.0.0.1` port) that records every request, and fake `claude`/`codex` executables that record their argv, prompt and environment and print fixture messages. "Nothing sent" means: the stub saw no request outside `/api/version`, `/api/tags` and `/api/show`; the fake Codex was never started with the prompt.

| Criterion | Test (planned names) |
| --- | --- |
| AC-001, SC-001 | `test_fallback.WrapperFallbackTests.test_quota_failure_completes_on_fallback` |
| AC-002, SC-001 | `…test_provider_unavailable_completes_on_fallback`, `…test_cli_missing_completes_on_fallback` |
| AC-003 | `…test_setting_off_matches_today` (argv, `steps.jsonl` and ledger equal with and without the feature) |
| AC-004 | `…test_fallback_argv_is_primary_codex_profile`, `…test_fallback_runs_under_same_confinement` (Autonomous: same `confined_argv`; env has no provider key and no OSS overrides), `…test_user_codex_config_not_read` |
| AC-005, SC-002 | `ProbeTests.test_model_missing_refuses_unknown_free_status` |
| AC-006, SC-002 | `…test_cloud_model_refuses_privacy`, `…test_remote_host_refuses_privacy`, `SettingTests.test_non_loopback_endpoint_refused`, `WrapperFallbackTests.test_user_codex_config_not_read` (no user MCP server or notify program) |
| AC-007, SC-002 | `…test_server_down_refuses_capability`, `…test_codex_without_oss_refuses_capability`, `…test_codex_skill_missing_refuses_capability`, `…test_sandbox_not_nesting_refuses_capability`, `…test_probe_deadline_refuses` |
| AC-008, SC-002 | `PermissionTests.test_wider_argv_refused` (each widening token), `…test_extra_env_refused`, `…test_other_codex_config_layer_refuses` |
| AC-009, SC-002 | `StateTests` (ignored and ref digests, caps, unreadable entries); `WrapperFallbackTests.test_changed_tree_refuses`, `…test_created_draft_refuses`, `…test_changed_reviews_refuses`, `…test_ignored_path_change_refuses`, `…test_primary_commit_refuses`, `…test_unverifiable_state_refuses` |
| AC-010 | `ClassifyTests` (each non-recoverable cause, tail-only matching, unknown text) and `…test_non_recoverable_never_falls_back` |
| AC-011 | `LedgerFallbackTests.test_selected_records_both_routes_and_usage` |
| AC-012 | `…test_refusal_recorded_with_reason` (each reason) |
| AC-013, SC-005 | `WrapperFallbackTests.test_failed_fallback_stops`, `…test_refused_fallback_draft_not_retried`, `…test_retry_attempt_never_falls_back` |
| AC-014, SC-003 | `…test_repeated_record_is_idempotent`, `…test_retried_step_single_effect` |
| AC-015 | `…test_step_limit_blocks_fallback`, `…test_fallback_counts_a_step` |
| AC-016 | `ArtifactsFallbackTests.test_review_by_fallback_not_cross_provider` (Autonomous), `LedgerFallbackTests.test_human_gated_review_by_fallback_not_cross_provider` |
| AC-017 | `test_agent_run_ledger` cases for the new enums and fields, cross-field rules, unchanged `schema_version`, rejection of free text |
| AC-018 | `evaluation.md` present with the pilot (below); `test_governance` link check |
| AC-019, SC-004 | documentation review; `RunCliTests.test_start_and_resume_flags` |
| AC-020 | `RunCliTests.test_setting_outside_checkout`, `…test_chat_refuses_flag`, `SettingTests.test_invalid_setting_is_off`, `RunCliTests.test_status_shows_setting`, `…test_human_gated_meta_records_setting`; `record.md` shows the setting |
| AC-021 | `…test_chat_step_never_falls_back` (`run_interactive` path untouched) |
| FR-009, FR-011 | `ModuleTests.test_stdlib_only_no_model_list` |

Each mapping is recorded in `acceptance-evidence.json` during implementation.

## Pilot (full local gate, operator host)

Run first and record each result in `evaluation.md`:

1. `codex --version`, `codex exec --help` (confirm `--oss`, `--local-provider`, `--json`), `ollama --version`, `curl -s 127.0.0.1:11434/api/tags`, the Codex configuration layers, and a `codex exec --oss` run with an empty `CODEX_HOME`. Run these from the operator's terminal.
2. The tests that need real systemd, `bwrap` and Codex (skipped in CI), including the real `codex_sandbox_nests` probe with and without bubblewrap.
3. In a scratch project: `ballast run start --local-fallback qwen3:4b -i feature_directory=specs/1-demo -i integration=claude …` with a fake `claude` early on `PATH` that prints a captured quota message and exits 1. Expected: the ledger report shows a `route` with `failure_cause: quota-exhausted` and either `fallback: selected` plus a `route_source: fallback` attempt with usage, or `fallback: refused` with `incompatible-capability`. The scratch step's artifacts validate, or the step fails with both attempts recorded.
4. The same with `--mode autonomous`. The expected result on this host is a refusal with `incompatible-capability`, because Codex's sandbox does not nest (DEC-0004).
5. `ballast run resume RUN --local-fallback off`, then repeat step 3: no fallback, no new ledger event.

Record the exact commands and the unavailable gates in the PR.
