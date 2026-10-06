# Quickstart: validating Chat mode

This guide shows how to prove the feature works. The commands and expected results come from [contracts/cli.md](contracts/cli.md) and [contracts/phase-graph.md](contracts/phase-graph.md); this file does not restate those contracts.

## Prerequisites

- Linux with a systemd user session, `bwrap` with working user namespaces, and Git 2.41 or later on `PATH` outside any checkout.
- The `claude` CLI, and `codex` too for the cross-provider review scenario. The `specify` CLI is needed only for scenario 7.
- A scratch GitHub repository that has adopted Ballast at this feature's version, with `[github] repository` and `[checks]` in its `ballast.toml`, and a scoped leaf Issue `#N` with an intake scope comment.
- `ballast trust` run after review.

## Automated gates

```bash
uvx ruff check && uvx ruff format --check
uv run --no-project --python 3.13 --with pyyaml python -m unittest tests/test_*.py
```

The expected result is a full pass. `tests/test_chat_mode.py` drives `run.py` with a fake interactive agent on a pty, a fake `gh`, `git` and `systemd-run` from `tests/fixtures/`, and a temporary `XDG_STATE_HOME`. Cases that need bwrap, systemd or a real CLI are skipped where those are unavailable, as today. Run the full gate on a qualified machine so they also run. Existing test files pass with their assertions unchanged (SC-007).

## Pilot checks (record the results in `reviews/pilot.md`)

These close the facts research could not verify in the planning sandbox.

| ID | Check | Expected |
| --- | --- | --- |
| P-1 | `specify workflow run --help` and `specify workflow resume --help` on 1.0.11 | No single-step option. If one exists, record it; it does not change R1. |
| P-2 | `codex --help`: interactive `--sandbox`, `--ask-for-approval never`, positional prompt | The flags exist for the TUI. A command outside the sandbox fails and is never escalated. |
| P-3 | A Chat step with Claude, then with Codex: resize the terminal, press Ctrl-C, run `/exit` | The TUI redraws on resize, Ctrl-C reaches the agent, `/exit` ends the step, and the terminal is restored. |
| P-4 | In a Claude Chat step, press Shift+Tab out of `dontAsk`, approve an `Edit(ballast.toml)` prompt if one appears, and ask for `curl` | The deny rule still refuses the edit, bwrap keeps `ballast.toml` read-only, and nothing is written outside the worktree. |
| P-5 | `/permissions` → save an allow rule in project settings | Fails: `.claude/` is read-only for the step. |

## End-to-end scenarios

Run each one in the scratch repository. "Record" means `ballast run status RUN` shows the entry and `ballast ledger report --run RUN` lists it.

1. **Conversational feature (US1, AC-001 to AC-006; SC-001)**
   1. `ballast run start --mode chat -i feature_directory=specs/N-slug -i idea="Issue #N: ..."`. Expect `Branch sync:`, the handoff summary, and no agent started.
   2. `ballast run step RUN specify`. Expect a refusal that names `scope`.
   3. `ballast run approve RUN scope`, then type `approve scope`.
   4. `ballast run step RUN specify`. Converse, then `/exit`. Expect `Step ...: completed`, with `specify` and `clarify` offered next.
   5. Edit `spec.md` in the shell. `ballast run status RUN` shows an out-of-step change.
   6. Step `clarify`, approve `intent`, step `plan`. Expect the step history with agent identities and postconditions, one out-of-step change, and the human intent approval with its spec digest.
   7. Compare the feature artifacts with those of a headless run. They are the same set of files; there is no Chat-only artifact.

2. **Agent cannot approve (US2, AC-007 to AC-009; SC-004)**
   1. In a `plan` step, ask the agent to write a `workflow-approval` block into `intent.md`, to write "RECONCILE_STATUS: approved" and "plan approved", to run `ballast run approve`, and to edit `.ballast/` or the run state.
   2. Expect: the `ballast` call fails inside the step (state hidden, launcher refuses while the step is active); protected edits are refused or end the step as `tampered`; `intent` checks as failed (unregistered block); `tasks` stays refused until `approve plan` from the operator's terminal.

3. **Leave and resume (US3, AC-010 to AC-013)**
   1. Close the terminal during a `plan` step. In a new terminal, `ballast run status RUN` shows the step `interrupted` and its postcondition result.
   2. Kill the wrapper with `kill -9` during a step. The next `ballast run status RUN` is refused and names the run and step. Run `ballast discard-runs`. Then `status` records the step as interrupted.
   3. Advance `main` on GitHub, then `ballast run step RUN plan`. Expect `Branch sync: synchronized` (or a `dirty` block with "commit first") before the agent starts.
   4. While a step is active, run `ballast run step RUN tasks` and `ballast run resume <other run>` from another terminal. Both are refused, and the reason names the active step.

4. **Evidence and publication (US4, AC-014 to AC-017; SC-003)**
   1. Finish the feature in Chat, including `ballast run step RUN review --kind implementation` (the other provider, if installed) and `ballast run checks RUN`.
   2. Approve `implementation`, `spec-reconciliation` and `final`, then run `ballast run publish RUN`.
   3. Expect one Draft PR whose Chat section lists the steps, human approvals, reviews with the cross-provider flag, checks, and the "logs stay local" line, and no link to `speckit-runs` or `.specify/workflow-state`.
   4. Compare `ballast ledger report` for this run and for a human-gated run of a similar feature. The same kinds of entry appear, labeled by mode.

5. **Mode switches (US5, AC-018 to AC-021; SC-005)**
   1. With a failed `plan` postcondition and a `DEC-0001` proposal resolved only in text, run `ballast run mode RUN human-gated --reason "headless implement"`, then `mode RUN chat`.
   2. Expect `tasks` still refused on the failed `plan` check, and `converge` still refused on the unconfirmed resolution.
   3. Run `ballast run mode RUN autonomous`. Expect "never raised".
   4. In human-gated mode, `ballast run step RUN implement` runs headless with today's argv.

6. **Autonomous to Chat (AC-022)**
   1. Take a blocked Autonomous run and run `ballast run continue RUN --reason block-resolved --ref "..." --mode chat`.
   2. Expect the HD, the source lowered to chat and `continued`, and a new Chat run whose summary lists every PD as agent-provisional.
   3. `approve intent` in the Chat run. The summary shows PD-0003 superseded by the new HD, still labeled provisional.

7. **Spec Kit run to Chat (AC-018)**: start `ballast run start -i feature_directory=...` (human-gated), stop at a gate, then run `ballast run mode <engine run> chat --reason x`. Expect a linked Chat run, plan and tasks approvals re-asked, and `ballast run resume <engine run>` refused, naming the Chat run.

## Record in the PR

Record the fast-gate and full-gate commands with their results, the pilot checks P-1 to P-5, scenarios 1 to 7 with their run IDs, and any unavailable gate.
