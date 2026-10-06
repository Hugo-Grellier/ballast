# Quickstart: validate worktree preparation

How to prove the feature end to end. Behavior is defined in [contracts/prepare.md](contracts/prepare.md) and [contracts/cli-and-launcher.md](contracts/cli-and-launcher.md); entities in [data-model.md](data-model.md).

## Fast gate

```sh
uvx ruff check && uvx ruff format --check
uv run --no-project --python 3.13 --with pyyaml python -m unittest tests/test_*.py
```

All new tests are offline. They use `tests/test_setup.py`'s fakes (Spec Kit commands and source archives per ref), real linked worktrees (`git worktree add`) in a temporary repository, and `XDG_STATE_HOME`/`XDG_DATA_HOME` inside the test directory. "No network" means `_fetch_source` and `urllib.request.urlretrieve` fail the test if called, and CLI children run with a `PATH` that has no `uvx`.

## Scenario map

| Scenario | Test (planned) | Evidence |
| --- | --- | --- |
| AC-001, SC-001 | `test_setup.PrepareTests.test_new_worktree_is_prepared_offline`; `test_ballast.PrepareTriggerTests.test_run_prepares_then_reaches_preflight` (each of `run`, `ledger`, `intake`) | installation equals the source record; no fetch; launcher exit 2 at the trust preflight; no `ballast setup` invoked |
| AC-002, FR-008 | `test_spec_workflow` no-baseline message test; `PrepareTriggerTests` asserts the full message | names inputs present and `ballast trust`; no `trusted.json` written |
| AC-003 | `PrepareTests.test_sibling_and_kept_sources` | primary at Y, sibling at X → copied from sibling; primary's kept X → copied from kept |
| AC-004 | `PrepareTriggerTests.test_doctor_trust_then_run` | `setup --check` `current`; after `trust`, run passes preflight; no second preparation (no journal, record unchanged) |
| AC-005, FR-012 | `PrepareTriggerTests.test_non_preparing_commands` | `trust`, `discard-runs` refuse with the install message and write nothing; `doctor`, `status --json`, `preview` leave the worktree snapshot unchanged |
| AC-006, FR-007 | `PrepareTests.test_existing_installation_is_never_replaced` | stale, modified (one file), other-pin and partial installations → refusal naming `ballast setup`; tree unchanged |
| AC-007, FR-013 | `PrepareTriggerTests.test_version_without_declaration` | standard without `[setup] prepare` → CLI refusal naming `ballast setup`; `tools/setup` never run; no fetch |
| AC-008 | `PrepareTests.test_other_pin_is_never_used` | only pin-X sources, worktree at Y → refusal naming `ballast setup`; no Y entries; reason `it is for X, not Y` |
| AC-009 | `PrepareTests.test_other_configuration_is_never_used` | `[agents.permissions]` differs → rejected; generated `claude-settings.json` absent |
| AC-010, SC-003 | `PrepareTests.test_mismatched_content_is_rejected` (subtests: added, missing, altered file; changed executable bit; record without `executable`) | each named in output; no partial installation |
| AC-011 | `PrepareTests.test_unfinished_or_busy_source_is_rejected` | source journal present; source exclusive lock held |
| AC-012, SC-003 | `PrepareTests.test_no_baseline_is_inherited` | trusted primary with identical inputs; worktree `trusted.json` absent after preparation; primary `trusted.json` never opened (`open` audit); a stale baseline at a reused path is removed |
| AC-013 | `PrepareTriggerTests.test_damaged_standard_refuses` | names the damaged path; no fetch; worktree unchanged |
| AC-014 | every `PrepareTests` case snapshots `ballast.toml`, constitution, `docs/policies/project/` and each source tree plus its operator state, before and after | byte-identical |
| AC-015, SC-002 | `PrepareConcurrencyTests.test_ten_worktrees_two_pins` (20 repetitions) | each worktree's record ref and fingerprint equal its own pin's; content equals the source record; each refuses at its own preflight |
| AC-016 | `PrepareConcurrencyTests.test_state_stays_per_worktree` | start, advance, discard a run in one; every other worktree's and source's run state, `trusted.json`, `in-progress`, journal and lock file unchanged |
| AC-017 | `PrepareTests.test_missing_source_then_setup` | refusal naming `ballast setup`; no stage; after a (faked) `ballast setup` in that worktree, a new worktree at the same pin is prepared from it |
| AC-018, AC-019, SC-004 | `PrepareTests.test_killed_preparation_is_recovered` | SIGKILL at ≥ 5 points (journal `staging`, mid-copy, journal `switching`, mid-switch rename, journal `committed`); next command prints the recovery; result equals an uninterrupted preparation; plus a committed attempt whose pin changed is rolled back |
| AC-020 | `PrepareConcurrencyTests.test_one_preparation_per_worktree` | two concurrent commands: one prepares, the other refuses naming the holder; no interleaved writes (final tree equals the source record) |
| SC-005 | `PrepareTests` timing assertion on the fake installation, plus the measured time in the end-to-end run | < 10 s |

## End-to-end scratch-project run (record in the PR)

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
