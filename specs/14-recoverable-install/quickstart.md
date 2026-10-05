# Quickstart: validating recoverable installs and pin updates

How to prove each acceptance criterion. Formats are in [contracts/](contracts/) and states in [data-model.md](data-model.md); this guide names scenarios, commands and expected outcomes only.

## Prerequisites

- Fast gate: `uvx ruff check && uvx ruff format --check` and `uv run --no-project --python 3.13 --with pyyaml python -m unittest tests/test_*.py`. Every scenario below except "End to end" runs offline in that suite: Spec Kit commands, source downloads and the standard archive are replaced by fakes or `file://` fixtures.
- Every test sets `XDG_DATA_HOME` and `XDG_STATE_HOME` to fresh directories outside `/tmp`, `/var/tmp`, `/dev/shm` and `$TMPDIR` (the launcher refuses agent temp roots), and builds a disposable Git project with the shipped ignore block.
- **Snapshot**: a helper that records path → digest for the checkout (including ignored files), the run archives under the Git common directory, `$XDG_STATE_HOME/ballast/` (minus `checkout.lock` and `setup-holder.json`) and, where stated, the cache. "Unchanged" means equal snapshots.

## Scenarios

| ID | Scenario | Expected |
| --- | --- | --- |
| AC-001 | Trusted installation and paused run; fail `_fetch_source` for each Spec Kit source; separately fail the CLI's archive download | Exit 1 naming `fetch <source>` or the standard ref; checkout snapshot unchanged; no `.ballast/setup/`, no `.fetch-*` in the cache |
| AC-002 | Fail each `specify` call in turn and each `patch` | Exit 1 naming the step; checkout snapshot unchanged |
| AC-003 | Remove a promised output from the stage; make one staged path un-ignored; plant the stage path in a staged file; fill the disk (raise `OSError(ENOSPC)` in a copy) | Exit 1 naming the check; switch never starts; checkout unchanged |
| AC-004, SC-001 | Kill setup with `SIGKILL` at ≥ 5 points: during staging, after `switching` is journaled, after the first entry rename, mid-switch, after `committed` | Next setup prints the recovery line; checkout equals the full previous or full new snapshot, never a mix |
| AC-005 | After a kill, run `launcher.py run …`, `ledger …`, `intake …`, `trust` | Each exits 2 naming `ballast setup` |
| AC-006 | All runs of AC-001 to AC-004 | Constitution, `docs/policies/project/`, run state, archives and `trusted.json` unchanged |
| AC-007, SC-002 | Unchanged pin, setup fails or is killed then recovered | `launcher.py status --json` reports `refusal: null`; no `trust` run |
| AC-008 | Change the pin to B; fail B's setup (B fetched) and fail B's fetch (B not fetched) | `ballast doctor`, `launcher.py run` and the CLI refusal name pinned B, installed A and both recovery actions |
| AC-009 | Hold the checkout lock exclusively from a helper process, run setup | Exit 2 naming the holder's PID; no file written |
| AC-010, SC-004 | Two CLI processes fetch the same uncached ref from sibling worktrees (fake download counts calls and sleeps); repeat 20 times; also two setups in one checkout | One download per race; both installations equal; no partial cache; second same-checkout setup refused every time |
| AC-011 | Kill a process holding the checkout lock, and one holding a cache lock | Next setup proceeds and recovers |
| AC-012, SC-003 | Run setup twice at a current pin with network access denied (download functions raise) | Second run prints `nothing changed`; checkout and cache snapshots unchanged; under 5 s |
| AC-013, SC-005 | Remove, add or alter one file in a cached version; remove its record | Detected before use; refetched, or refused naming the path when the fetch fails |
| AC-014, SC-005 | Primary checkout installed; alter, add or remove one installed file there; run setup in a linked worktree | `full installation: the primary installation differs from its record at <path>` |
| AC-015 | Create `in-progress`; separately hold the launcher's shared lock | Setup exits 2 before writing, naming `ballast discard-runs` or the running command |
| AC-016 | Preview a fixture target whose `cli.toml` minimum is above the CLI version | Report names pinned, target, installed and minimum, with `does not meet` and the install line |
| AC-017 | Two unfinished runs, one with `run-format.json` in the target's `resumes`, one without | First compatible, second incompatible with "finish or discard"; exit 1 |
| AC-018, SC-006 | Fixture targets A and B differing by an added skill, a changed tool, a removed policy and a new ignored path; preview A → B, then update a copy of the project and diff | Preview's added/changed/removed lists equal the actual difference; ignore impact reported; project-owned list empty |
| AC-019 | Any preview | Ordered steps: pin edit, `ballast setup`, protected inputs to review, `ballast trust`, `[checks] commands` |
| AC-020 | Successful, failing and refused previews | Checkout, run archives and operator state snapshots unchanged; only the cache may differ; no `preview/` directory left |
| AC-021 | Preview a target without `[setup] recoverable` | Report says the recovery guarantees do not apply |
| AC-022, SC-007 | Update A → B with A cached, restore pin A, setup with downloads denied | A reinstalled from cache; equals a fresh A installation |
| AC-023 | After AC-022 | Constitution, project policies, run state, archives unchanged; launcher refuses until `trust`; `trusted.json` unchanged |
| AC-024 | README test | The update section documents preview, update, retry and rollback; every `ballast <subcommand>` it shows is one the CLI or launcher accepts |

## End to end (full gate, network)

On a Linux machine with network, from a scratch project pinned to this branch's working copy through `BALLAST_STANDARD_DIR`:

1. `ballast setup`, `ballast trust`, start and pause a run.
2. Edit `tools/spec-kit/skills.patch` in the working copy so it no longer applies, run `ballast setup`: exit 1 naming `patch skills.patch`, then `ballast run resume …` passes the preflight without `trust`.
3. Restore the patch, run `ballast setup` twice: the second prints `nothing changed`.
4. Run `ballast setup` and kill it with `kill -9` during the Spec Kit steps, then run it again: the recovery line names the previous installation.

Record the commands and results in the PR, as the [project workflow](../../docs/policies/project/workflow.md) requires when `tools/setup` or `tools/ballast` changes.
