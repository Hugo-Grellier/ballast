# Implementation Plan: Autonomous run core

**Branch**: `feat-autonomous-core` | **Date**: 2026-10-03 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/27-autonomous-core/spec.md` (intent approved, digest in [intent.md](intent.md))

**Risk**: R2. This feature changes the launcher's trust model, the headless-agent authority model, and what `ballast` executes (it pushes a branch and opens a Draft PR). The plan needs human approval, and the PR needs human merge approval.

## Summary

An operator can start `ballast run start --mode autonomous` for an eligible, scoped leaf Issue at R0, R1 or R2. The run then reaches a Draft PR without any approval prompt.

How it works:

- **Workflow**: a second Spec Kit workflow, `ballast-autonomous`, has no `gate` steps. Each human gate becomes an agent decision step followed by a trusted recorder step. Every existing postcondition stays in place.
- **Decision records**: agents write untrusted JSON drafts. Trusted shell steps validate them and append them to a hash-chained log in the operator state directory, where no agent can write. The steps then render a committed projection, `specs/<f>/autonomous/record.md`, which every later validator compares byte for byte.
- **Mode, eligibility and limits**: recorded by `run.py` before Spec Kit starts, in the same operator state directory that already holds the trust baseline. The agent wrapper enforces wall-time and step limits and refuses work for an inactive run.
- **Blocks**: they end the run with a categorized record and a recovery command. Recovery is only possible human-gated, through `ballast run continue`, which starts a gate-only workflow, `ballast-continue`.
- **Publication**: after completion, `run.py` (not an agent) commits, pushes and opens one Draft PR. Its body is rendered from the records. It never merges, marks the PR ready, releases or deploys.
- **Governance**: policies, agent instructions, the constitution and the technical spec are amended in the same change.

Full rationale: [research.md](research.md).

## Technical Context

**Language/Version**: Python ≥3.11 standard library only (`tomllib`). Workflow tools run under the system `/usr/bin/python3 -I -S`. Tests run on 3.13.

**Primary Dependencies**: Spec Kit CLI 1.0.11 (pinned in `tools/setup`), using only `command`, `shell` and `gate` steps, per-step `integration`, and `input.args`. Also the `gh` CLI (operator side only: the eligibility read and PR creation), `git`, `systemd-run --user`, and the Claude Code and Codex CLIs. No new Python dependency is added. Tests keep `pyyaml` through `uv run --with`.

**Storage**: Local files. The operator state is `$XDG_STATE_HOME/ballast/<checkout-key>/runs/<run-id>/` (`run.json`, `decisions.jsonl`, `human-decisions.jsonl`, `block.json`, `blocks.jsonl`). Committed projections: `specs/<f>/autonomous/record.md` and the provisional block in `intent.md`. Agent drafts go to `specs/<f>/autonomous/drafts/`, which is transient. See [data-model.md](data-model.md).

**Testing**: `unittest`, with a fake `gh`/agent on `PATH`, a temporary `XDG_STATE_HOME` and temporary Git repositories. Engine-driven tests are skipped where Spec Kit, systemd or Codex are unavailable, as today. An operator scratch-repository pilot covers the GitHub path ([quickstart.md](quickstart.md)).

**Target Platform**: GitHub on Linux with a systemd user session, the qualified Ballast 1.0 environment.

**Project Type**: CLI and workflow standard installed into other repositories.

**Performance Goals**: None beyond today's. Recorder steps re-render one Markdown file and read logs of at most a few hundred lines.

**Constraints**:

- Stdlib-only and `-I -S`.
- Nothing executes from an agent-writable path before trust.
- No agent gains push, PR, merge or state-directory authority.
- The human-gated workflow file stays unchanged.
- Limits: wall time from 1 to 1440 minutes (default 240) and agent steps from 1 to 200 (default 30).

**Scale/Scope**: One Autonomous run per checkout at a time, the same rule as today. About 37 workflow steps; up to 30 agent steps by default.

## Constitution Check

*Gate before Phase 0; re-checked after Phase 1 design (result below).*

| Principle | How the design complies | Status |
| --- | --- | --- |
| BL-INV-001 Projects own only their own files | New installed files (workflows, the `ballast` extension, `autonomy.py`) live under paths already ignored (`.specify/*`, `.ballast/`). The project-owned additions are the optional `[autonomous]` table in `ballast.toml` and the per-feature `autonomous/record.md` (feature artifact). Setup's `IGNORE_PROBES` gains a probe for the new workflow path. | Pass |
| BL-INV-002 Nothing executes from a writable checkout before trust | `autonomy.py` lives in `.ballast/spec_workflow/`, inside the trust baseline. It does not import `.ballast/feature_intake.py`, which is outside the baseline (R-03). New workflow definitions and the extension live under `.specify/`, which is hashed. The launcher still verifies before executing `run.py`. | Pass |
| BL-INV-003 Delegated authority | The mode, limits, eligibility, decision log and run limits are all in the operator state directory. Agents only write drafts that a trusted recorder validates. Push and PR creation are done by `run.py` as the operator, never by an agent; the agent permissions (`claude-settings.json` denying `git push` and `gh`) are unchanged. The only mode change after start is lowering. | Pass |
| BL-INV-004 A project picks a version, never a source | No change to `tools/ballast` fetch rules. | Pass |
| BL-INV-005 Postconditions over exit codes | Every producer is still followed by a validator. Each decision step is followed by a recorder that checks the draft and the artifact digest. `record-final` requires one current decision per point. | Pass |
| 6. Portable, dependency-free tools | Stdlib only (`json`, `hashlib`, `tomllib`, `subprocess`). | Pass |
| 7. Generic by default | Boundaries, risk lists and privileged actions are project data in `ballast.toml`. Shipped text names no project. | Pass |
| 8. Executable evidence | Each refusal, block, forgery and limit path has a test that fails if the stop is removed (SC-004, SC-005). See Verification. | Pass |
| Governance: weakening an invariant needs R2 and a reason | Moving intermediate human approvals to a single merge approval for eligible Autonomous runs changes governance text. The constitution is amended with new principle BL-INV-006 and version 1.1.0, with its reason and compatibility impact (FR-030). | Pass, with an amendment |

**Post-design re-check**: Passed. No violation needs justification. The single duplication is noted under Complexity Tracking.

## Architecture Boundaries

- **Affected areas**:
  - Trusted launcher path (`launcher.py` → `run.py`).
  - Headless agent wrapper (`agent.py`).
  - Artifact validators (`artifacts.py`).
  - Shipped Spec Kit workflows and extensions (`templates/spec-kit/`).
  - The installer (`tools/setup`).
  - Shipped policies, skills and copy-once templates.
  - Governance documents: the constitution, `specs/TECHNICAL-SPEC.md` and `specs/PRODUCT-SPEC.md`.
- **Contracts and data flow**:
  1. The operator runs `ballast run start --mode autonomous`. The launcher verifies trust and executes `run.py`. `run.py` calls `autonomy.check_eligibility()`, which reads `gh` and `ballast.toml`, and then writes `run.json`.
  2. Spec Kit runs `ballast-autonomous`. Agent steps go through `agent.py`, which checks and updates `run.json` limits, and write drafts. Recorder steps (`artifacts.py record-decision`) append to `decisions.jsonl` and render `record.md`.
  3. When the run ends, `run.py` writes `block.json` or calls `autonomy.publish()` (git and `gh`). It then archives the run as today and archives the operator run directory under `speckit-runs/<run>/autonomous/`.
  4. Source of truth: the operator logs. `record.md`, the `intent.md` provisional block and the PR body are deterministic projections.
- **Architecture references**:
  - [Technical spec §91](../TECHNICAL-SPEC.md#91-v10-target): the v1.0 target, Autonomous.
  - §37: human intervention contract.
  - §96: failure philosophy.
  - §35 R2.
  - The roadmap, [Priority 4](../../docs/plans/2026-10-02-product-roadmap.md#priority-4--let-the-operator-choose-the-level-of-supervision).
  - `templates/policies/spec-kit-workflow.md`, "Workflow runner contract".
  - [Constitution](../../.specify/memory/constitution.md).
- **Proposed architecture decisions**: Record ADR `docs/adr/0004-autonomous-provisional-decisions.md`. It covers:
  - the separate gate-less workflow, instead of conditional gates;
  - the operator-state, hash-chained decision log with committed projections;
  - publication by the trusted runner;
  - continuation as a gate-only workflow.

  These need human review with this plan.

## Decisions needing human approval at plan review

| ID | Decision | Recommendation |
| --- | --- | --- |
| D-1 | Implement Autonomous as separate workflows (`ballast-autonomous`, `ballast-continue`) rather than modifying `ballast-feature`. | Accept (R-01). |
| D-2 | ~~Approval registry for human-gated runs.~~ | Withdrawn (operator, 2026-10-03): FR-011 is narrowed to Autonomous runs, which refuse every human approval block; gated hardening is #29. |
| D-3 | `run.py` commits the worktree changes since the start-of-run `HEAD` as the operator, with hooks and filters disabled and protected paths refused (R-11), pushes the current branch, and opens the Draft PR. Autonomous starts only on a non-default branch with no open PR. | Accept (R-11). |
| D-4 | Specialist reviews run in one reviewer step, with trusted coverage checking against deterministic path triggers and declared boundaries. | Accept (R-08). |
| D-5 | Whether Ballast's own `ballast.toml` narrows Autonomous to R0/R1 for this repository, given that `docs/policies/project/workflow.md` lists the launcher and permission model as R2 boundaries. | Decided (operator, 2026-10-03, option 3 on #11): no narrowing; R2 runs fully autonomous to the PR and is reviewed at merge. The plan amends `docs/policies/project/workflow.md` to scope its "before the change" rule to human-gated runs. |
| D-6 | Constitution 1.1.0 adds BL-INV-006: "A provisional decision is never human approval; only merging the PR that contains it accepts it." | Accept (FR-030). |
| D-7 | In Autonomous, every agent step (Claude and Codex) runs under `bwrap` with operator state and the ledger bound read-only; a missing `bwrap` or failed self-test refuses Autonomous (R-02). Human-gated runs unchanged. | Accepted (operator, 2026-10-03; plan review F-1). |
| D-8 | A changed trusted input stays a launcher refusal before `run.py` runs; there is no `trust` block category. Only the publisher reports a `permission` block. | Accepted (operator, 2026-10-04; DEC-0002, DEC-0005). |
| D-9 | When Codex's own sandbox cannot start inside Ballast's `bwrap`, a confined, offline probe at run start routes both roles to Claude and records the fallback; Codex never runs with its sandbox off. | Accepted (operator, 2026-10-04; DEC-0004). Running Codex unsandboxed under `bwrap` stays a possible R2 follow-up. |

## Repository Impact

New files:

- `tools/spec_workflow/autonomy.py`: the run record, eligibility and policy, the hash-chained logs, blocks, the record and PR renderer, and the publisher.
- `templates/spec-kit/workflows/autonomous/workflow.yml` and `templates/spec-kit/workflows/continue/workflow.yml` (contract: [workflow.md](contracts/workflow.md)).
- `templates/spec-kit/extensions/ballast/extension.yml` and `commands/speckit.ballast.{decide,clarify,review,resolve}.md`.
- `tests/test_autonomy.py`.
- `docs/adr/0004-autonomous-provisional-decisions.md`.

Changed files:

- `tools/spec_workflow/run.py`:
  - `--mode`, `--wall-time` and `--max-agent-steps` on `start`;
  - the Autonomous refusal on `resume`;
  - the new `continue` and `publish` subcommands;
  - the end-of-run block or publication;
  - archiving the operator run directory.
- `tools/spec_workflow/agent.py`: run-record checks, the step counter, the bounded wait and `EXIT_LIMIT = 5`.
- `tools/spec_workflow/artifacts.py`:
  - mode-aware `check_intent`, `check_decisions` and `check_convergence`;
  - the new checks `autonomous-preflight`, `continue-preflight`, `record-decision` and `record-provisional-intent`;
  - record re-render comparison in every check of an Autonomous run.
- `tools/spec_workflow/launcher.py`: no logic change. `COMMANDS` routing is unchanged, because `run.py` handles the new subcommands. `state_dir()` is reused.
- `tools/setup`: installs the two workflows and the `ballast` extension; adds an ignore probe; accepts `[autonomous]` in `ballast.toml` without changing permission merging.
- `templates/policies/workflow.md`, `templates/policies/spec-kit-workflow.md`, `templates/policies/model-routing.md`.
- `templates/skills/ballast-feature-intake/SKILL.md`: the `Privileged actions before merge:` scope line and the Autonomous start command.
- `tools/feature_intake.py`: `_scope_text` requires the new line only when the scope says `Autonomous: yes`. Existing human-gated intake is unchanged.
- `templates/AGENTS.md`, `templates/github/pull_request_template.md`.
- Repository-owned files: `AGENTS.md`, `CLAUDE.md`, `docs/policies/project/workflow.md`, `.specify/memory/constitution.md`, `specs/TECHNICAL-SPEC.md` (§37, §91) and `specs/PRODUCT-SPEC.md` (only R2 timing text).
- `README.md`: the operator commands.
- `tests/test_spec_workflow.py`: new cases only; existing cases stay unmodified.

Unchanged:

- `templates/spec-kit/workflows/feature/workflow.yml`.
- `tools/ballast`.
- `claude-settings.json`.
- `ledger.py` and the ledger schema. The ledger keeps importing Spec Kit runs, and for Autonomous runs it sees `ballast-autonomous` as the workflow ID.

## Verification Strategy

| Acceptance | Evidence |
| --- | --- |
| AC-001, AC-002, AC-003, SC-001, SC-002 | `AutonomousEngineTests` full run with a fake agent: no gate in state, one current PD per point, a failed validator stops the run. A unit test confirms that `ballast-autonomous` has no `gate` step. Pilot step 1. |
| AC-004, AC-023, AC-024 | Recorder unit tests: same-provider review flagged `cross_provider: false`; a missing required kind fails; a run with no path trigger still requires a security review; a report narrative with a severity-tagged finding missing from the draft is refused; `renew-intent` blocks as stale intent after a spec-changing resolution (DEC-0006); a review verdict other than `approved` blocks; a `high` or `critical` finding blocks even when marked `resolved`; `medium` with no reason fails. Pilot step 5. |
| AC-005, AC-011 | Recorder unit tests: an `assume` draft with `reversible: false` is refused; a block draft with fewer than two options is refused; no PD is written for a blocked point. `validate-clarified-spec` is unchanged. |
| AC-006, AC-007, AC-025, SC-003, SC-006 | Renderer golden tests for `record.md` and the PR body, including R2 and single-provider variants. A wording-guard test covers drafts and output. |
| AC-008, FR-012 | `check_intent` test: a spec edit after the provisional block fails as stale. Forged human block: refused in an Autonomous run. Human-gated validation unchanged (#29). |
| AC-009, AC-014, AC-017 | `run.py` tests: `resume` refused for Autonomous with #18 named; `continue` appends HD and the lowering, copies the baseline and starts `ballast-continue`; no raise path exists; earlier PDs are still rendered. |
| AC-010, FR-027 | Publisher test with a fake `git`/`gh` recording argv: only `add`, `commit`, `push -u origin HEAD` and `pr create --draft`; never `merge`, `ready`, `--force`, `release` or `deploy`. |
| AC-012 | Wrapper tests: an expired deadline refuses before spawn (exit 5); the step limit is reached; an agent outliving the remaining time has its scope stopped, is checked and exits 5. |
| AC-013, AC-016, SC-005 | Wrapper and validator tests: an agent edit to `ballast.toml` gives tamper exit 4; edits to `record.md` and `intent.md` provisional blocks fail the next validator; the run record is unreachable from the agent sandbox (Codex test, as in `CodexSandboxTests`). |
| AC-015, FR-001 | `run.py` tests: no `--mode` gives `ballast-feature` with an unchanged argv; the run record exists only in the state directory. |
| AC-018 – AC-022 | `autonomy` eligibility unit tests with fake `gh` JSON: an Epic, sub-issues, a missing scope, a missing privileged-actions line, a narrowed risk, an ignored widening key, an authorized action, and a risk raise to an excluded level that blocks. |
| Sandbox escape (round 5) | Confined-step tests: `systemd-run --user` fails; `$XDG_RUNTIME_DIR` empty; parent `/proc/<pid>/environ` unreadable; protected inputs not writable from agent steps or check commands; a token-bearing remote URL refuses the start; an edit by `decide-final` or a reviewer step blocks; the published tree digest equals the checked one. |
| Credential isolation | Confined-step tests: `gh auth status` not logged in; authenticated `git ls-remote` fails; listed secret paths and variables unreadable; a custom `GH_CONFIG_DIR` or `XDG_CONFIG_HOME` is cleared and hidden; no Git filter driver runs operator-side. |
| FR-015, final checks | `run-checks` tests: a failing or timed-out command blocks before publication; code changed after implementation review, or a check that changes the tree, blocks; a missing `[checks]` table refuses an Autonomous start; results carry `runner` provenance in the PR body. |
| SC-004 | One test per block category asserts that no later agent step started. |
| SC-007 | Existing `tests/test_*.py` pass unmodified, and `ballast-feature/workflow.yml` is byte-identical to `main`. |
| FR-029, FR-030 | Documentation review. A test asserts that the constitution version is 1.1.0 and that BL-INV-006 is present, and that the shipped policies contain the Autonomous section. |

Required reviews (review matrix):

- engineering and test;
- security (agent authority, the trust model, `gh` and git writes);
- documentation (public CLI, config and policy);
- architecture (the new ADR);
- spec reconciliation before the PR.

Use a cross-provider reviewer.

## Feature Artifacts

```text
specs/27-autonomous-core/
├── intent.md
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── cli.md
│   ├── workflow.md
│   ├── decision-draft.md
│   ├── pr-summary.md
│   └── config.md
├── checklists/
├── tasks.md           # next: speckit-tasks
├── decisions.md       # only when implementation discovers a decision
└── reviews/           # plan review, implementation reviews, convergence
```

## Follow-ups (out of scope, to file as Issues)

- **F-1**: `.ballast/feature_intake.py` is installed outside the trust baseline (`launcher.BASES` covers only `.ballast/spec_workflow`). Decide whether to move it or extend the baseline.
- **F-2**: Safe Autonomous resume (#18), the Draft PR lifecycle and reuse (#17), the review packet (#19), and bounded fix loops (#21) consume these records.

## Complexity Tracking

| Item | Why needed | Simpler alternative rejected because |
| --- | --- | --- |
| A small read-only Issue query in `autonomy.py` that duplicates part of `feature_intake.preflight` | The eligibility check runs as trusted code and must not import an unbaselined file (BL-INV-002). | Importing `.ballast/feature_intake.py` would execute code that the trust baseline does not cover. |
| Two extra workflow definitions | Spec Kit gates are interactive. No evidence shows conditional steps exist, and the human-gated file must stay unchanged (SC-007). | A single conditional workflow relies on unverified engine features and risks changing human-gated behavior. |
