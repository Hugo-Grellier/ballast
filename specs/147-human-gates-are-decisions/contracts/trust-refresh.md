# Contract: automatic trust refresh and the trust settings check

Covers FR-001 to FR-004, FR-019 and FR-020, and AC-001 to AC-006. Design rationale is in [research R1 to R6](../research.md#r1-where-the-automatic-refresh-runs-before-the-launcher-as-a-setup-subprocess). Record shapes are in the [data model](../data-model.md).

## Trigger (`tools/ballast`)

For `run`, `ledger` and `intake` only, after worktree preparation (if any) and before executing the launcher:

```text
status = launcher status --json            # writes nothing
if status.refusal is a protected-input change or a pin/installation mismatch
   and declarations(standard_for_pin).refresh is true:
       ensure_standard(pin)                 # fixed source, verified cache (ADR-0008)
       python3 -IS <standard>/tools/setup --project ROOT --refresh   # subprocess
execv launcher ...                          # unchanged; it decides
```

- The refusal kind comes from a new `status --json` field, `"refusal_kind": "inputs-changed" | "pin-mismatch" | "tamper" | "unfinished-step" | "no-baseline" | "setup-unfinished" | ...`. Older launchers lack it, and `tools/ballast` then never refreshes.
- Only `inputs-changed` and `pin-mismatch` trigger a refresh.
- The subprocess's stdout and stderr pass through. Its exit status is ignored: the launcher's own check decides.
- `tools/cli.toml` gains `refresh = true` under `[setup]`.

## `tools/setup --refresh`

Runs under the exclusive checkout lock. It refuses, and changes nothing, while another command holds the lock, after an unfinished attempt (it says "run `ballast setup`"), or with either marker present. Then:

1. `verdict = setup_trust.refresh_eligible(root, state, standard=STANDARD)`. This covers every eligibility term of the data model up to the observation, in the order of [research R2](../research.md#r2-refresh-eligibility-fr-001-fr-003-ac-002-ac-005-ac-006). If it is not eligible, setup prints `not refreshed: <first reason>; the operator reviews and runs ballast trust` and exits 0.
2. `attempt(state, build)`: the normal installation for the current `ballast.toml` and pin. A failure goes through the existing journal and recovery, and no baseline is recorded.
3. `setup_trust.record_refresh(root, state, verdict, record)`. This checks the recordable terms (installation equality, observed blobs, previous-baseline equality, generated settings), then calls `launcher.record_baseline(state, snapshot, source="default-branch", reference={...}, repository=...)`, re-snapshots, and restores the previous baseline and provenance on any difference. On success it calls `launcher.add_reviewed(root, repository, pair)` and prints:

```text
refreshed the trust baseline from OWNER/NAME BRANCH at COMMIT12 (N workflow inputs); regenerated the installation for ballast.toml
```

`setup_trust.refresh_eligible` never raises. Any exception becomes `not refreshed: internal error: <type>`.

## Plain `ballast setup`

Its result is unchanged when ADR-0015's `settle` records or keeps a baseline. When `settle` skips, and a baseline with a named repository exists, setup runs `record_refresh` with the same eligibility after its installation. An operator-run setup after pulling a merged change therefore needs no `ballast trust` either (FR-001, second alternative).

## Launcher

- **`record_baseline(state, inputs, *, source, reference=None, repository=None)`**: `source` may be `trust`, `setup` or `default-branch`. It writes `repository` when given. It remains the only writer of `trusted.json`.
- **`_trust`**: refuses before writing when `generated_settings(STANDARD_DIR, config)` differs from `.ballast/spec_workflow/claude-settings.json`, or `[agents.permissions]` is malformed (AC-003):

  ```text
  ballast: refusing to trust: generated agent settings (.ballast/spec_workflow/claude-settings.json) differ from what ballast.toml produces; run `ballast setup`, review, then `ballast trust`
  ```

  It keeps today's terminal-free behavior and today's refusals with a tamper marker or the `in-progress` marker; it also refuses when `BALLAST_AGENT_STEP` is set (D-09). It writes `repository` into the provenance.
- **`status --json`**: adds `refusal_kind`. It adds `baseline_commit` when `baseline_source == "default-branch"`.
- **`run`, after a refresh**: the first `ballast run` whose provenance is `default-branch` and was recorded after the run's last invocation prints `trust baseline refreshed from OWNER/NAME BRANCH at COMMIT12` once. The launcher passes the line to `run.py` through `BALLAST_REFRESHED`, and `run.py` appends it to the invocation output and the ledger.
- **Comparison, refusals and markers**: unchanged.

## Branch synchronization

`RECOVERY["protected-input"]` becomes:

```text
the synchronized branch changed protected inputs; rerun {rerun}: it refreshes trust and the installation from the pinned default branch when every change came from it, otherwise the operator reviews them and runs ballast trust
```

## Refusal and tamper tests required (FR-019, SC-005)

Each test asserts that `trusted.json`, `trusted-source.json`, the reviewed record and the installation are byte-identical afterwards, and that the launcher still refuses with `ballast trust`.

| Case | AC |
| --- | --- |
| Local uncommitted edit to `ballast.toml` | AC-002 |
| A committed branch change absent on the default branch | AC-002 |
| A changed `.venv` | AC-002 |
| `[github] repository` repointed (to an unreviewed repository, and to another reviewed one) | AC-005 |
| Legacy provenance without a repository | R5 |
| Network failure, a timeout, an `insteadOf` rewrite | AC-006 |
| A tamper marker; the `in-progress` marker | AC-006 |
| A default-branch path that is a symlink or a submodule | R2 |
| The default branch moved between observation and record | edge case |
| Stale `claude-settings.json` at `trust` | AC-003 |
| Stale settings after a regeneration (simulated) at refresh | AC-004 |
| A regeneration failure (fetch fails) | edge case |
