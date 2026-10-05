# Review: reconciliation

- Role: reconciliation reviewer
- Agent/model: claude/claude-opus-5-5, the driving agent; reduced independence (see [the security review](implementation-security.md))
- Base: `52031c1..HEAD` (the whole feature branch)
- Artifacts: [intent.md](../intent.md), [spec.md](../spec.md), [plan.md](../plan.md), [research.md](../research.md), [data-model.md](../data-model.md), [contracts/](../contracts/), [tasks.md](../tasks.md), [decisions.md](../decisions.md), the implementation reviews, `tools/setup`, `tools/ballast`, `tools/spec_workflow/launcher.py`, `tools/spec_workflow/run.py`, `tools/cli.toml`, the tests, `README.md`, ADR-0006, ADR-0007
- Converge: every task in `tasks.md` is checked with evidence; comparing the plan, contracts and data model with the code appended no task.
- Verdict: CONVERGED

## Criterion to implementation and evidence

| Criterion | Implementation | Evidence |
|---|---|---|
| AC-001 | `ensure_standard`/`fetch` (no partial copy), `install_spec_kit` (`fetch <source>`) | `CacheTests.test_failed_download_leaves_nothing`, `test_failed_stages_keep_the_previous_installation` |
| AC-002 | `specify`, `patch` name the step; staging never touches live paths | same test; T028 live |
| AC-003 | `validate` checks (1) to (6), `check_links` | `test_invalid_stage_is_never_switched`, `test_linked_work_area_is_refused` |
| AC-004 | journal, `roll_back` keyed on `new`, `finish`, `recover` | `test_killed_setup_is_recovered`, `test_kill_during_rollback_is_recovered`; T028 live |
| AC-005 | launcher `_hold`, `_setup_refusal` | `TrustedLauncherTests.test_unfinished_setup_is_refused` |
| AC-006 | `entries` never covers project-owned files; constitution only when absent | snapshot comparisons in every failure and kill test |
| AC-007 | rename switch restores identical bytes; work area outside `BASES` | `test_failure_at_an_unchanged_pin_keeps_trust`; T028 live |
| AC-008 | `--check` stale detail, launcher refusal, CLI and doctor details | `test_changed_pin_names_both_versions`, `test_pinned_and_installed_versions_differ`, `NotFetchedTests`, `test_pinned_and_installed_versions_are_named` |
| AC-009, AC-015 | `Setup.lock`, `in-progress` refusal | `SetupLockTests` |
| AC-010, AC-011 | `fetch_lock`, kernel-released `flock` | `CacheTests`, `SetupLockTests` |
| AC-012 | `Setup.current` before any write; verified cache without download | `NoOpTests`, `CacheTests`; T028 live (0.25 s) |
| AC-013 | `damage`, refetch or refusal | `CacheTests.test_damage_is_detected_and_refetched`; T028 live refetch |
| AC-014 | `copy_from_primary` → `copy_verified` | `WorktreeCopyTests` |
| AC-016 to AC-021 | `preview` and helpers; `[setup]`, `[runs]`; `RUN_FORMAT` | `tests/test_preview.py`, `RunFormatTests`; T028 live preview |
| AC-022, AC-023 | `copy_kept` (DEC-0002) and the cache | `test_rollback_reuses_the_previous_installation` |
| AC-024 | README "Updating the pinned version" | `ReadmeUpdateTests` |
| SC-001 to SC-007 | as above | as above; SC-003 measured < 5 s offline and 0.25 s live |

## Gaps and their diagnosis

| Gap | Diagnosis | Correction |
|---|---|---|
| FR-009, FR-012, AC-010, AC-013 hold only with a CLI that includes this feature. | New knowledge (the cache lives in the per-machine CLI; the minimum cannot name an unreleased CLI). | DEC-0001, resolved and listed for the merge review; README and ADR-0007 state it. The spec text is not edited to excuse it. |
| AC-022's "without a network request" was not reachable by the plan: a full build downloads Spec Kit sources. | New knowledge. | DEC-0002 (kept installation); data model, operator-state and setup contracts, ADR-0006 updated. |
| Plan-review findings F-001 to F-007. | Plan defects found before tasks. | Resolved in the design and implemented; see [plan.md](plan.md) review Resolution. |
| Implementation review findings ENG-001, TST-001, SEC-001, SEC-002, DOC-001. | Implementation wrong. | Fixed test-first in `bf5359c`. |

No behavior contradicts the spec. Behavior beyond the spec's wording, each inside its intent and recorded: `trust` and `discard-runs` hold the checkout lock (F-005), the launcher reports a running setup as running (F-006), and setup refuses symbolic links among installed parents (F-007).

## Not checked on a live machine

A kill in the middle of a real switch was checked live after the reviews (real Spec Kit, `SIGKILL` after 15 of the switch's renames, 111 entries journaled): the launcher refused naming `ballast setup`; the next setup printed the recovery line, restored the previous installation byte-identical and the trust baseline still held. Covered offline only (fakes or `file://` archives): a worktree copy of a real Spec Kit installation, two real worktrees racing a GitHub download, and a rollback A → B → A between two real releases that both carry this feature (none is published yet). The live checks that were run are recorded under T028 in [tasks.md](../tasks.md).
