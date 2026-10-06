# Plan review: Chat mode (#20)

- Review: plan (engineering, plan scope)
- Reviewer: claude/claude-opus-5-5, fresh context, same provider as the author (the run record's DEC-0004 explains why Codex could not take the review role)
- Run: Autonomous `2cb9c5c5`; this verdict is agent-provisional
- Verdict: approved

## What was reviewed

- `spec.md` (FR-001 to FR-023, AC-001 to AC-022, SC-001 to SC-007, Assumptions) and `intent.md`, which defers to the spec at the PD-0003 digest.
- `plan.md`, `research.md` (R1 to R15), `data-model.md`, `quickstart.md` and the five contracts: `cli.md`, `phase-graph.md`, `step-runner.md`, `run-record.md` and `pr-evidence.md`.
- `autonomous/record.md` for the run's provisional decisions and integration fallback.
- Policies: `AGENTS.md`, `docs/policies/workflow.md`, `docs/policies/project/workflow.md` (R2 boundaries) and `docs/policies/engineering.md`. There is no `docs/policies/project/engineering.md`. ADR-0005 for the branch-synchronization rule.
- `tasks.md` and `decisions.md` do not exist yet, which is expected at this point in the workflow.

## How the claims were checked against the code

The plan reuses many existing helpers, so I checked that each one exists and behaves as the plan says:

- `autonomy.py`: `MODES`, `WORKFLOWS`, `HUMAN_DECISION_KINDS`, `TRANSITIONS`, `_validate_mode_history`, `change_mode`, `read_log` and `append_log`, `tree_digest`, `filter_flags`, `confined_env`, `confinement_self_test`, `codex_sandbox_nests`, `neutralize`, `MAX_BODY`, `HUMAN_APPROVAL` and `publish` all exist. `confined_argv` passes `--new-session` unconditionally today, so D-3 adds a new parameter. It does not repurpose an existing one.
- `agent.py`: `FORBIDDEN`, `CONFINED_ALLOW`/`CONFINED_DENY`, `_open_log`, `_containment`, `_stop_descendants`, `_protected_state`, `_mark_tampered` and the second-`SIGINT` handling match R3, R4 and R9. `stop_scope` is in `launcher.py`, and `agent.py` imports it from there.
- `launcher.py`: `_refusal` refuses on the tamper marker, the `in-progress` marker and a changed baseline over `BASES`. `_discard` stops the recorded scope before it removes `RUN_STATE`. This supports R8 and R10, and it supports the claim that `discard-runs` leaves the operator run record alone.
- `branch_sync.synchronize` takes `starting=` as R5 says.
- `artifacts.py`: `Feature`, `spec_digest`, `check_intent`, `record_intent` with registration under operator-state `approvals/`, `check_decisions`, `check_convergence` and `run_checks` exist. Today `check_intent` routes any `Feature` with `feature.run` set to `check_provisional_intent`, so the plan's "registered-approval check enabled" for a Chat `Feature` is a real behavior change.
- `claude-settings.json` and `permission_args`: these give the headless bound for the human-gated driver inside a Chat run. That driver has no bwrap.

## Assessment

- **Requirement coverage.** The Verification Strategy maps every acceptance scenario, every FR with a behavior, SC-002 to SC-005 and SC-007 to a named test or pilot check. Each edge case in the spec has a row. FR-023 has a governance test and a documentation review.
- **Source authority.** The operator run record is the single source of truth. The ledger, the handoff summary and the PR section are projections of it. Canonical intent stays in the feature artifacts and the registered `intent.md` block. Approvals bind to artifact digests, so staleness is computed and never set by hand. The phase graph recomputes entry conditions from checks instead of storing a "blocked" set. This rules out drift between the mode and the failure state, which is the core of FR-022.
- **Trust boundary.** One invocation per action makes FR-004 structural: each agent step follows the launcher's checks and branch synchronization. Approvals, resolutions, mode changes and publication exist only as operator commands. These commands are refused while the `in-progress` marker exists, so an agent inside a step cannot reach them. The D-3 omission of `--new-session` is narrowly scoped and has two named tests and pilot P-3. The interactive permission bound (bwrap plus `dontAsk`/`never`) is the right answer to an interactive session that can leave its permission mode.
- **Concurrency and partial failure.** The marker, the per-run `flock` and `active_step` cover the race between the launcher check and the marker write. A dead wrapper is recovered through the existing reviewed `discard-runs` path. Ledger and archive failures cannot turn a failed step into a passing one.
- **Compatibility.** Headless argv, every `workflow.yml` and `claude-settings.json` stay unchanged. New ledger fields are additive. SC-007 is guarded by the unchanged existing tests.
- **Scope.** The change surface is large: about nine subcommands, a new module, a mode-aware publisher and a Chat path in `ledger report`. Each part traces to an FR. Complexity Tracking justifies the two duplications.

The draft records four observations for `speckit-tasks` to turn into tasks and tests:

- the bound that protects the operator record during a headless step inside a Chat run;
- the provisional-intent route in `check_intent`;
- tree attribution when an interrupted step is closed late;
- the missing protected-state comparison after a dead wrapper.

None of these blocks the plan. Each needs a task or a test, or a sentence in the contracts.

<!-- ballast-findings: begin -->
## Findings (recorded from the review draft)

- F-001 (medium, missing-test, accepted-provisionally): data-model.md says that no agent step can write the operator record because bwrap hides it. Under D-5, a ballast-chat run switched to human-gated runs its steps headless through agent.py without bwrap. There, the bound is the headless permission model: Claude acceptEdits with prompts none and a narrow Bash allow list, and Codex workspace-write with no extra roots. human-decisions.jsonl is hash-chained but not authenticated, so a write would forge a gate approval. The existing human-gated registration under state_dir/approvals (#29) already relies on this bound, so the design is not weaker than today. Before merge, tasks must correct the data-model wording and add a forgery test with a headless-driver step: an approval, mode change or check written to run state does not count. AC-008 and FR-006 cover the run in either mode.
- F-002 (medium, missing-test, accepted-provisionally): artifacts.check_intent sends every Feature with feature.run set to check_provisional_intent, which accepts an agent-provisional intent block. A Chat Feature, and above all a Chat continuation of an Autonomous run whose intent.md still carries the provisional block, must require the registered human block instead (FR-003, AC-009, BL-INV-006). The plan states this, but the forgery list in the Verification Strategy does not test it. Tasks must add a test: in a Chat run, and in a continued Autonomous run before approve intent, the plan phase is refused on the provisional block, and record_intent removes that block only through approve intent.
- F-003 (low, spec-ambiguity, open): Step 2 of the step-runner lifecycle closes a dead wrapper's active step as interrupted, and step 3 then compares the tree with last_manifest. The contract does not say whether the late close stores tree_after and sets last_manifest. If it does not, the agent's edits are reported as an operator out-of-step change. If it does, operator edits made after the wrapper died are attributed to the agent step. Tasks should pick one rule and document that the attribution of a late close is uncertain.
- F-004 (low, spec-ambiguity, open): For a dead wrapper (R10), the protected-state snapshot from lifecycle step 7 lived only in the wrapper's memory, so the late close cannot run the comparison of step 10. Protection then rests on bwrap's read-only binds (Chat driver) and the launcher baseline over BASES at the next invocation. PROTECTED in autonomy.py covers all of .ballast, while BASES covers only .ballast/spec_workflow. The contracts should state this bound for the late close, and the interrupted close should record that no protected-state comparison was possible.
<!-- ballast-findings: end -->
