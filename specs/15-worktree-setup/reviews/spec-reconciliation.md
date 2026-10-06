# Review: reconciliation

- Role: reconciliation reviewer
- Agent/model: claude/claude-opus-5-5, the driving agent; reduced independence (see the [security review](implementation-security.md))
- Base: `1ce1f9a..HEAD` (the whole feature branch)
- Artifacts: [intent.md](../intent.md), [discovery.md](../discovery.md), [spec.md](../spec.md), [plan.md](../plan.md), [research.md](../research.md), [data-model.md](../data-model.md), [contracts/](../contracts/), [tasks.md](../tasks.md), [decisions.md](../decisions.md), the implementation reviews, `tools/setup`, `tools/ballast`, `tools/spec_workflow/launcher.py`, `tools/cli.toml`, the tests, `README.md`, ADR-0011
- Converge: every task T001 to T035 is checked with evidence; comparing the plan, research, data model and contracts with the code appended no task.
- Verdict: CONVERGED

## Criterion to implementation and evidence

| Criterion | Implementation | Evidence |
|---|---|---|
| AC-001, FR-001, FR-002, SC-001 | `tools/ballast` `before_launcher` → `prepare`; `tools/setup` `Setup.prepare`, `fill_from_candidates` (no `install_spec_kit`, no `_fetch_source`) | `PrepareTests.test_new_worktree_is_prepared_offline`, `PrepareTriggerTests.test_run_prepares_then_reaches_preflight`; live run under `unshare -rn` |
| AC-002, FR-008 | launcher `_trust_refusal` | `TrustedLauncherTests.test_no_baseline_names_the_inputs_to_review`; trigger tests assert the full text |
| AC-003, FR-003 | `candidates()` (own kept, primary live/kept, each worktree live/kept) | `PrepareTests.test_sibling_and_kept_sources` |
| AC-004 | prepared record equals source; launcher passes after `trust` | `PrepareTriggerTests.test_doctor_trust_then_run`; live run |
| AC-005, FR-012 | launcher `main` refusals before `_hold`; CLI `before_launcher`; DEC-0001 exception | `PrepareTriggerTests.test_non_preparing_commands`, `TrustedLauncherTests` (two tests), `test_doctor.ProjectTests.test_setup_then_trust`; `preview` not exercised (TST-001) |
| AC-006, FR-007 | prepare steps 5 and 6 (`current`, `live_entries`) | `PrepareTests.test_existing_installation_is_never_replaced`, `test_tracked_policy_is_not_an_installation` |
| AC-007, FR-013 | `Declarations.prepare`, `refuse_uninstalled` | `PrepareTriggerTests.test_version_without_declaration`, `ShimTests.test_runs_the_launcher_of_the_pinned_version` |
| AC-008 to AC-011, FR-004, FR-014 | `mismatch`, `_share`, `_linked_parent`, `copy_verified` (content and execute bits) | the corresponding `PrepareTests`; `WorktreeCopyTests` mode tests |
| AC-012, FR-009 | no `trusted.json` read; own stale baseline removed (DEC-0002) | `PrepareTests.test_no_baseline_is_inherited` (audit hook) |
| AC-013, FR-005 | `prepare` → `damage()` before running setup | `PrepareTriggerTests.test_damaged_standard_refuses` |
| AC-014, FR-011 | stage-only writes; `finish` skips the constitution in prepare mode; other checkouts opened read-only | `WorktreeCase.prepare()` snapshots in every case |
| AC-015, AC-016, FR-010, SC-002 | per-worktree operator state; source shared lock | `PrepareConcurrencyTests.test_ten_worktrees_two_pins`, `test_state_stays_per_worktree` |
| AC-017 | refusal naming setup; `ballast setup` unchanged | `PrepareTests.test_missing_source_then_setup` |
| AC-018, AC-019, FR-006, SC-004 | journal `mode`, `recover` (committed at another fingerprint rolled back) | `PrepareTests.test_killed_preparation_is_recovered` and three recovery tests |
| AC-020 | `hold`, `settled`, `lock` holder `mode` | `PrepareConcurrencyTests.test_one_preparation_per_worktree` |
| SC-003 | rejection rules | mismatch, link and baseline tests |
| SC-005 | local copy only | test bound 10 s; live 0.57 s |
| FR-015 | the tests above and the recorded end-to-end run | [quickstart.md](../quickstart.md) |

## Gaps and how they were closed

- **Spec missing accepted behavior**: removal of a stale baseline at a reused path was in the plan (R8) but not in the spec (analyze U1). Recorded as DEC-0002; FR-009 updated.
- **Spec gap found in review**: an unfinished agent step in an uninstalled checkout had no way out (ENG-001). Recorded as DEC-0001; FR-012, AC-005's contract and ADR-0011 updated.
- **Contract refinements**: candidates are only checkouts with a record or kept copy; parent-link rejection; F-001 checked first under the shared lock with a bounded retry; the stage-changed failure; the safe copy; the reworded baseline line. Contracts, data model and ADR-0011 updated in the same documentation commit.
- **Not covered by an automated test**: `ballast preview` on an uninstalled worktree (unchanged code, needs network), the full doctor report (its probes are checked directly). Listed in the [test review](implementation-tests.md).

No proposed product change remains open; both decisions are resolved and listed for the merge review.
