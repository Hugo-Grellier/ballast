# Quickstart: validate worktree preparation

How to prove the feature end to end. Behavior is defined in [contracts/prepare.md](contracts/prepare.md) and [contracts/cli-and-launcher.md](contracts/cli-and-launcher.md); entities in [data-model.md](data-model.md).

## Fast gate

```sh
uvx ruff check && uvx ruff format --check
uv run --no-project --python 3.13 --with pyyaml python -m unittest tests/test_*.py
```

All new tests are offline. They use `tests/test_setup.py`'s fakes (Spec Kit commands and source archives per ref), real linked worktrees (`git worktree add`) in a temporary repository, and `XDG_STATE_HOME`/`XDG_DATA_HOME` inside the test directory. "No network" means `_fetch_source` and `urllib.request.urlretrieve` fail the test if called, and CLI children run with a `PATH` that has no `uvx`.

## Scenario map

Final test names (all in `tests/`). Each new test failed before the code it covers: the feature tests against base `1ce1f9a`, the review tests against the commit before their fix.

| Scenario | Tests | Evidence |
| --- | --- | --- |
| AC-001, SC-001 | `test_setup.PrepareTests.test_new_worktree_is_prepared_offline`; `test_ballast.PrepareTriggerTests.test_run_prepares_then_reaches_preflight` (`run`, `ledger`, `intake`) | installation equals the source record; network guarded (fetch, `urlretrieve`, `socket.connect`); exit 2 at the trust preflight; no constitution created; live run in a network namespace without interfaces |
| AC-002, FR-008 | `test_spec_workflow.TrustedLauncherTests.test_no_baseline_names_the_inputs_to_review`; `PrepareTriggerTests.test_run_prepares_then_reaches_preflight` | full message with only present inputs; no `trusted.json` |
| AC-003 | `PrepareTests.test_sibling_and_kept_sources` | sibling at vB used while the primary is at vA; primary's kept copy used after the primary moved |
| AC-004 | `PrepareTriggerTests.test_doctor_trust_then_run` | doctor's `setup-current` probe passing, trust missing; after `trust`, `ledger report` passes with no second preparation |
| AC-005, FR-012 | `PrepareTriggerTests.test_non_preparing_commands`; `TrustedLauncherTests.test_uninstalled_checkout_is_refused_without_writing`, `test_unfinished_step_is_discarded_on_an_uninstalled_checkout` (DEC-0001); `test_doctor.ProjectTests.test_setup_then_trust` | trust/discard-runs refuse and write nothing; `status --json` and doctor leave everything unchanged; `preview` is not exercised offline (it builds a disposable project, which needs the network) and is unchanged by this feature |
| AC-006, FR-007 | `PrepareTests.test_existing_installation_is_never_replaced`, `test_tracked_policy_is_not_an_installation` (F-002) | stale, modified and partial installations refused naming setup, tree unchanged |
| AC-007, FR-013 | `PrepareTriggerTests.test_version_without_declaration`; `test_ballast.ShimTests.test_runs_the_launcher_of_the_pinned_version` | CLI refusal for run/ledger/intake/trust/discard-runs; journal-only checkout reaches the launcher's unfinished-setup refusal |
| AC-008 | `PrepareTests.test_other_pin_is_never_used` | `it is for vA, not vB`; nothing installed |
| AC-009 | `PrepareTests.test_other_configuration_is_never_used` | `it was built for another configuration`; no `claude-settings.json` |
| AC-010, SC-003 | `PrepareTests.test_mismatched_content_is_rejected` (added, missing, altered, +x, -x, record without `executable`), `test_source_reached_through_a_link_is_rejected`; `WorktreeCopyTests.test_record_lists_executable_files`, `test_changed_file_mode_is_not_copied`, `test_record_without_modes_is_still_copied` | each reason printed; nothing left installed |
| AC-011 | `PrepareTests.test_unfinished_or_busy_source_is_rejected` | journal, held lock, no lock file (F-004, nothing created) |
| AC-012, SC-003 | `PrepareTests.test_no_baseline_is_inherited` | audit hook: no `trusted.json` opened; reused-path baseline removed (DEC-0002) |
| AC-013 | `PrepareTriggerTests.test_damaged_standard_refuses` | damaged path named; nothing written, no state created |
| AC-014 | `WorktreeCase.prepare()` around every in-process preparation | every other checkout's tree, archives and operator state, and this worktree's project-owned files, byte-identical |
| AC-015, SC-002 | `PrepareConcurrencyTests.test_ten_worktrees_two_pins` | 20 repetitions of 10 concurrent preparations on 2 pins: right pin, fingerprint and content; own preflight refusal |
| AC-016 | `PrepareConcurrencyTests.test_state_stays_per_worktree` | no run state copied; trust and discard in one worktree leave every other tree and state unchanged |
| AC-017 | `PrepareTests.test_missing_source_then_setup` | refusal naming setup, nothing left; a later worktree prepared from the one set up |
| AC-018, AC-019, SC-004 | `PrepareTests.test_killed_preparation_is_recovered` (copy, validate, switching, rename, committed), `test_committed_preparation_at_a_changed_pin_is_rolled_back`, `test_setup_recovers_a_preparation`, `test_unfinished_setup_is_not_recovered_by_preparation` | recovery line; final tree equals an uninterrupted preparation |
| AC-020 | `PrepareConcurrencyTests.test_one_preparation_per_worktree` | held, sequenced (F-001), launcher-held and 10 unsequenced races |
| SC-005 | `PrepareTests.test_new_worktree_is_prepared_offline` (< 10 s on the fake installation); live run | live: 0.57 s for a real installation |
| Security review | `PrepareTests.test_stage_link_is_never_followed`, `test_stage_changed_after_verification_is_refused`, `test_git_configuration_never_runs_a_program`; `WorktreeCopyTests.test_primary_record_is_read_under_its_lock` | SEC-001 to SEC-003, T023 |

## End-to-end scratch-project run (record in the PR)

Recorded result (2026-10-06, `BALLAST_STANDARD_DIR` at the feature branch, scratch project under `~/.cache`): primary `ballast setup` (network), `trust`, `ledger report --all` passed; in two new worktrees `unshare -rn ballast ledger report --all` and `unshare -rn ballast run start --help` each printed `Prepared the v0.7.0 installation from <primary> (verified, nothing downloaded).` and stopped at `no trusted baseline for this checkout; review its protected inputs (ballast.toml, .ballast/spec_workflow, .specify, .git), then run \`ballast trust\`` (exit 2), in 0.57 s; `tools/setup --check` reported `current`; `ballast trust && ballast ledger report --all` then passed in the first; each worktree had its own `installation.json` and no `trusted.json` before its own `trust`; `git status` was clean in both worktrees and showed only the project-owned constitution in the primary. `ballast doctor` with a local standard skips its probes by design, so the `--check` probe it runs was invoked directly.

Prerequisites: a CLI and a standard ref that both include this feature (or `BALLAST_STANDARD_DIR` pointing at this checkout), `git`, `uvx`, network for the first setup only.

```sh
cd "$(mktemp -d -p ~)" && git init -q demo && cd demo
# ballast.toml pins the feature ref; add the shipped ignore block; commit.
ballast setup && ballast trust && ballast ledger report      # primary: network allowed
git worktree add ../demo-wt1 && git worktree add ../demo-wt2
cd ../demo-wt1
unshare -rn ballast ledger report      # or block network otherwise; expect "Prepared …" then the trust refusal
ballast doctor                         # setup-current passing; trust missing
ballast trust && ballast ledger report # passes
cd ../demo-wt2 && unshare -rn ballast run start --help   # prepared, refuses at preflight
git -C ../demo status --short; git status --short        # only project-owned files
```

Expected: no download in either worktree; each worktree has its own `$XDG_STATE_HOME/ballast/<key>/installation.json` and no `trusted.json` until its own `ballast trust`; the primary's tree and state are unchanged.
