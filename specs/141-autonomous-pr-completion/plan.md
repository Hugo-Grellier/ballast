# Implementation Plan: Autonomous PR completion policy

**Branch**: `feat/141-autonomous-pr-completion` | **Date**: 2026-10-12 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/141-autonomous-pr-completion/spec.md` (intent agent-provisional, PD-0008, digest in [intent.md](intent.md))

**Risk**: R2. The trusted runner gains a forge write (`gh pr ready`), which changes what `ballast` executes and the launcher's trust model ([research R14](research.md#r14-risk-recheck-against-the-r2-boundaries)). **Mode**: Autonomous run `478cbe23`. Every decision here is agent-provisional. Merging the PR is the only human approval, including for R2.

## Summary

Operators can opt in with `[autonomous] completion = "ready"` in `ballast.toml`. They can narrow it per run with `ballast run start --mode autonomous --completion draft`. A flag that would widen it refuses the start. The value goes into the run's policy snapshot. `--refresh-policy` re-reads it from the `ballast trust` baseline and still applies the start flag.

After an Autonomous publication, `run.py` already runs the Draft PR checkpoint and the acceptance packet. A new step, `_complete`, then runs in the same invocation. It reads only operator records: the run record, the decision log, the human decisions, `checks.json`, the in-process packet outcome and one read-back of the PR. A pure function, `completion.evaluate`, checks the spec's twelve conditions in order and lists every failure. When none fails, the runner runs `gh pr ready` as the operator, against the pinned repository and through the same hardened `gh` path as publication. It then reads the PR back to verify the result.

The result is printed as one `PR completion:` line and recorded as a new runner-only `pr_completion` ledger event. A forge failure leaves a Draft with its cause code and never changes the exit status or run state. With no key, with `draft`, or with an unknown value, nothing new runs, prints or records (FR-013). Checkpoints, Chat and human-gated runs never mark ready. `mark-ready` stays never-authorizable for agents.

A new ADR-0019 records the amendment to ADR-0004's publication decision and to its narrowing-only `[autonomous]` rule.

## Technical Context

**Language/Version**: Python ≥ 3.11, standard library only. `run.py` runs under `python3 -I -S` and imports the new `completion` module at startup, before any agent step.

**Primary Dependencies**: none new. External programs are the already-resolved `git` and `gh` (≥ 2.48, the Draft PR minimum; `gh pr ready` is long available).

**Storage**: the run record in operator state (new optional policy-snapshot fields) and the run ledger `events.jsonl` (new `pr_completion` kind and `labels` value type). No new file or store. The publication's identity passes in-process ([R1](research.md#r1-where-the-completion-step-runs)).

**Testing**: `unittest`, offline. The pure `evaluate` is tested directly. `run.py` is tested through the existing `RunCase` harness with its stand-in `gh`, extended for `pr ready`. Ledger validation goes through `ledger.validate`.

**Target Platform**: the qualified 1.0 host (Linux, systemd user session, authenticated `gh`, GitHub).

**Project Type**: workflow tool inside the installed standard (`tools/spec_workflow/`).

**Performance Goals**: at most 2 extra PR reads and 1 `gh pr ready` per reported publication, each bounded by the Draft PR 30 s command timeout. No polling and no waiting for CI ([PD-0004](research.md#r5-eligibility-as-a-pure-function-over-operator-records)).

**Constraints**: FR-013 byte-identical behavior without the key. No `gh` output, token or agent text in any line or event. Fail closed: any doubt keeps the Draft.

**Scale/Scope**: `completion.py` about 250 lines. About 60 lines in `run.py`, 50 in `autonomy.py` and 60 in `ledger.py`. One new test file plus additions to three existing ones. Documentation and ADR-0019.

No NEEDS CLARIFICATION remains. Two spec wordings are read explicitly, without changing behavior: "the Draft PR line" ([R10](research.md#r10-output-line)) and AC-003's publish-retry clause ([R11](research.md#r11-ac-003-and-fr-012-against-current-status-transitions)).

## Constitution Check

*Gate before Phase 0, re-checked after Phase 1. Result: **PASS** both times, no violations.*

| Principle | How the design holds it |
| --- | --- |
| 1. Projects own only their files (BL-INV-001) | `completion.py` installs with `tools/spec_workflow/` into the ignored `.ballast/`. The policy lives in the project's own `ballast.toml`. No tracked file is written. |
| 2. Nothing executes from a writable checkout (BL-INV-002) | `completion` is imported at `run.py` startup from the pinned standard. It runs only the resolved `gh` outside working trees, from an empty directory, through `draft_pr._command`. The step follows the checkpoint, which already refuses on `BALLAST_TAMPERED` or an unfinished-step marker, and `_complete` skips when the checkpoint skipped. |
| 3. Delegated authority (BL-INV-003) | Agents gain nothing. `mark-ready` stays in `NEVER_AUTHORIZED` (AC-017), and agents still cannot run `gh`. The policy comes only from the start snapshot of protected `ballast.toml`, or from a `ballast trust` baseline on refresh. The start flag only narrows. Eligibility reads operator records only (AC-013, AC-014). |
| 4. A project picks a version, never a source (BL-INV-004) | Not touched. |
| 5. Postconditions over exit codes (BL-INV-005) | `ready` is recorded only after a read-back shows `draft: false` at the published commit. A successful `gh` exit alone gives `forge-unverified`. |
| 6. Portable, dependency-free tools | Standard library only. |
| 7. Generic by default | Generic keys, wording and codes. Any GitHub repository. |
| 8. Executable evidence | Every AC and each of the 12 conditions has a named scenario in [quickstart.md](quickstart.md), including refusal, tamper and forge-failure paths. |
| 9. A provisional decision is never human approval (BL-INV-006) | Marking ready approves nothing. Every line, event, doc and ADR says that merging stays the only human approval. Output text is checked against `autonomy.HUMAN_APPROVAL` (FR-017). No human-approval record is created. |

## Architecture Boundaries

- **Affected areas**: the runner `tools/spec_workflow/run.py` (start flag, `_publish` hand-off, `_complete` after `_checkpoint`, publish-retry checkpoint on reported runs), the Autonomous policy and publisher in `tools/spec_workflow/autonomy.py` (`parse_policy`, `POLICY_KEYS`, `completion_policy`, additive `publish` return keys), a new trusted module `tools/spec_workflow/completion.py`, the ledger `tools/spec_workflow/ledger.py` and its schema note, and the operator documentation.
- **Contracts and data flow**: `run._publish` → `autonomy.publish` (unchanged behavior, returns `repo`, `number`, `commit`) → in-process publication → `_checkpoint` (#17 checkpoint, #19 packet; unchanged) → `_complete`: return when not reported; otherwise collect (run record, decision log, human decisions, `checks.json`, packet outcome, one PR read-back) → `completion.evaluate` (pure) → when eligible, `gh pr ready` and verification read-back → one `PR completion:` line and one `pr_completion` event. GitHub stays the source of truth for the PR's state. The decision log and run record are the source for the run's facts, and the ledger is the evidence of the outcome. See [contracts/config-and-cli.md](contracts/config-and-cli.md), [contracts/output-and-ledger.md](contracts/output-and-ledger.md) and [data-model.md](data-model.md).
- **Architecture references**: [constitution](../../.specify/memory/constitution.md) BL-INV-002, -003, -005, -006; [ADR-0003](../../docs/adr/0003-launcher-github-authority.md) (launcher GitHub authority); [ADR-0004](../../docs/adr/0004-autonomous-provisional-decisions.md) (publication by the trusted runner, narrowing-only `[autonomous]`); [ADR-0016](../../docs/adr/0016-privileged-action-kinds-and-policy-refresh.md) (`mark-ready` never authorizable, `--refresh-policy`); [ADR-0018](../../docs/adr/0018-runner-recorded-acceptance-checks.md) (published tree = checked tree, ledger compatibility); [Workflow runner contract](../../templates/policies/spec-kit-workflow.md#workflow-runner-contract) Publication row; [technical spec §36](../TECHNICAL-SPEC.md#36-risk-escalation).
- **Proposed architecture decisions** (agent-provisional; the merge accepts them):
  1. **ADR-0019 The trusted runner marks an eligible Autonomous PR ready for review.** It amends ADR-0004's publication decision ("opens one Draft PR"; Publication row "never … marks ready") for runs whose operator set `[autonomous] completion = "ready"`. It also amends ADR-0004's "narrowing-only `[autonomous]`" consequence: `completion` is an explicit operator opt-in to one runner action, never a widening of eligibility. It extends ADR-0003's fixed command list with `gh pr ready <n> --repo <pinned>`. It records the twelve conditions, the pure evaluation over operator records, the verification read-back, the residual head race ([R8](research.md#r8-the-forge-action-and-its-verification)), the `pr_completion` ledger kind and its older-version incompatibility, and that merge and auto-merge remain out (#143). ADR-0004 gets an "Amended by ADR-0019" note on the two affected bullets.

## Repository Impact

| Path | Change |
| --- | --- |
| `tools/spec_workflow/completion.py` | New. `Reason`, `Inputs`, `COMPLETION_REASONS`, `reported(policy)`, `evaluate(inputs)` (pure, conditions 1–12 in order), severity threshold, fixed reason wording, `format_line`, `event_data`, and `complete(root, run_id, publication, packet)` (collect, one PR read-back, `gh pr ready`, verification read-back, ledger append). Any exception becomes `internal-error`. |
| `tools/spec_workflow/run.py` | `_split_mode` takes `--completion`. Start-mode and value refusals. `_start_autonomous` applies the widening refusal and records `completion_flag` and `completion`. `RESUME_FLAGS` gains `--completion`. `_publish` leaves the publication for `_complete`. `_checkpoint` returns its outcome. `_run_autonomous`, `_resume_engine` and `_publish_command` call `_complete` after it, and the publish retry runs `_checkpoint` first only on a reported run. `_resume_locked` recomputes `completion` on refresh, keeping the flag. Module docstring and usage line updated. |
| `tools/spec_workflow/autonomy.py` | `POLICY_KEYS` gains `completion` and `completion_max_severity`. `parse_policy` normalizes both, with the "cannot widen eligibility" warning for unknown values. `completion_policy(configured, flag)`. `publish` returns `repo`, `number` and `commit` in addition to today's keys, and its docstring states that publication itself never marks ready. |
| `tools/spec_workflow/ledger.py` | `labels` value type. `COMPLETION_REASONS`. `pr_completion` in `FIELDS`, `ENUM_FIELDS`, `RUNNER_ONLY`, the required-source map and the cross-field rules. `report` shows the latest `pr_completion`. |
| `tools/spec_workflow/ledger-schema.md` | Document the kind, the `labels` type and the compatibility note. |
| `tests/test_completion.py` | New. Each condition alone, several conditions in order, thresholds, reason wording, approval-wording guard, forge failure, unverified ready, head moved, internal error. |
| `tests/test_autonomous_run.py` | Stand-in `gh` handles `pr ready`. End-to-end ready path, no-config byte identity (stdout, run record, ledger), `draft` and unknown values, the start flag (refusal, narrowing, mode refusal, resume refusal), refresh keeps the flag, checkpoint after ready, publish retry, Chat, human-gated and lowered runs never call `pr ready`, checkout `ballast.toml` change, exit status unchanged on forge failure. |
| `tests/test_autonomy.py` | `parse_policy` with the new keys and unknown values. `completion_policy` table. `publish` returns the new keys and still never calls `pr ready`. |
| `tests/test_agent_run_ledger.py` | `pr_completion` validation, the `labels` type, the runner-only refusal through `record`, the report line. |
| `templates/policies/spec-kit-workflow.md` | Publication row: the publisher still opens a Draft PR, and for a run whose operator set `completion = "ready"` the runner marks it ready after the checkpoint and packet when every condition holds. Autonomous runs: new **PR completion** paragraph (configuration, flag, conditions, line, ledger, "not an approval"). Draft PR: the checkpoint still never marks ready, with a pointer to PR completion. Resume: `--refresh-policy` also re-reads `completion` and keeps the start flag. |
| `templates/policies/workflow.md` | Autonomous bullet: "It never merges, marks a PR ready…" becomes "It never merges, releases or deploys. It marks its PR ready for review only when the operator opted in and every completion condition holds, and that is not an approval." |
| `README.md` | Configuration example gains `completion`. One paragraph for the flag and the outcome line. The "never marks a PR ready" sentences are scoped to the checkpoint and to runs without the opt-in. |
| `specs/TECHNICAL-SPEC.md` | §36 Autonomous paragraph and the v1.0 status paragraph: an eligible, opted-in Autonomous run ends with a PR ready for review, and the merge stays the single human approval. Link ADR-0019 and this spec. |
| `docs/adr/0019-autonomous-pr-completion.md` | New (ADR-0019). |
| `docs/adr/0004-autonomous-provisional-decisions.md` | "Amended by ADR-0019" notes on the publication decision and the narrowing-only consequence. |

Unchanged: `draft_pr.py` and `packet.py` (read through their existing results), `artifacts.py`, `chat.py`, the workflow YAML, `tools/setup`, `tools/ballast`, `tools/cli.toml`, agent settings, the constitution and this repository's `ballast.toml`, a protected input that the operator owns.

## Feature Artifacts

```text
specs/141-autonomous-pr-completion/
├── discovery.md
├── intent.md
├── spec.md
├── plan.md            # this file
├── research.md        # Phase 0 decisions R1–R15
├── data-model.md
├── contracts/
│   ├── config-and-cli.md
│   └── output-and-ledger.md
├── quickstart.md      # validation scenarios mapped to ACs
├── checklists/
├── autonomous/        # run record (rendered by the runner)
├── tasks.md           # next: speckit-tasks
├── decisions.md       # only if implementation discovers one
└── reviews/
```

## Review notes

- **Required reviews** (R2, [review matrix](../../templates/policies/workflow.md#review-triggers)): engineering review; security review, because the runner gains a forge write, policy authority comes from a protected input, and agent-writable inputs must not influence the result; test review, covering each condition alone, the no-configuration identity and the failure paths; documentation review, covering the policy sections, README, technical spec and ADR-0019.
- **For the plan decision** (agent-provisional): confirm R2 against [R14](research.md#r14-risk-recheck-against-the-r2-boundaries). Accept ADR-0019 as an amendment of ADR-0004 and an extension of ADR-0003. Accept the two wording readings: the `PR completion:` line ([R10](research.md#r10-output-line)) and AC-003's vacuous publish-retry clause ([R11](research.md#r11-ac-003-and-fr-012-against-current-status-transitions)). Accept that a `--refresh-policy` resume keeps that run's PR a Draft through condition (11).
- **For the merge reviewer**: [R7](research.md#r7-agent-derived-values-inside-operator-records) explains which conditions read agent-provisional content that trusted recorders recorded. [R8](research.md#r8-the-forge-action-and-its-verification) names the residual head race.
- **Not in scope**: merge or auto-merge (#143); waiting for GitHub CI; a per-Issue completion line.

## Complexity Tracking

No constitution violations.
