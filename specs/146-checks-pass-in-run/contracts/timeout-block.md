# Contract: the unaddressable timeout block

Covers AC-015 to AC-018, FR-009 to FR-011. See [data-model.md](../data-model.md#unaddressable-timeout-block) and [research R6-R8](../research.md#r6-recognizing-an-unaddressable-timeout).

## Constants (`autonomy.py`)

```text
LIMIT_KINDS += ("check-timeout",)                 # not in FIXED_LIMITS: resumable
LIMIT_LABELS["check-timeout"] = "check timeout"
LIMIT_RECOVERY["check-timeout"] =
  "Raise [checks] timeout_minutes in ballast.toml or speed up the named
   commands, run ballast trust, then resume, or continue human-gated."
```

## Trigger (`artifacts.record_decision`, implementation-review, fix loop on)

Evaluated after the drafts validate and before the existing `limit` and `fixing` handling, for the first record and for `--recheck`:

| Latest feedback failures | Blocking or open-to-fix findings | Result |
| --- | --- | --- |
| none | any | existing rules |
| all timed out | none | **block `check-timeout`**, fix state and cycle count unchanged |
| all timed out | some | existing rules (fix cycle, or the `fix-cycles` limit) |
| at least one non-timeout | any | existing rules |

The final `run-checks` (no `--feedback`) keeps its `postcondition` block for any failed check, including a timeout.

## Condition text

```text
check timeout reached: check 'CMD' timed out after M min[, ...]; no review finding is open, so a fix step cannot address it
```

`M` is `timeout_seconds / 60` from the result; when the applied timeout was the run's remaining wall time, the entry reads `timed out when the run's wall time ran out (S s)`. Commands are shown with `repr`, as `_check_text` does, and the whole text stays within the 4000-character block limit.

## Resume

`run._reentry` maps a `check-timeout` block's step to the feedback checks step before it: `record-implementation-review` → `checks-implementation`, `record-fix-review-N` → `checks-fix-N`. The earliest of that step and any changed-input step wins. `run-checks --feedback` re-reads `[checks]` from `ballast.toml`, which the launcher only accepts after `ballast trust`.

## Unchanged

Pass/fail rules, the review freeze, the protected-input and tree-change blocks, the `fix-cycles` limit for every other case, and `FIX_CYCLES`.
