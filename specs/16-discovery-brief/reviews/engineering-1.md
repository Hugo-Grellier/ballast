# Engineering review 1: Source-backed discovery brief

- review: engineering
- Reviewer: claude/claude-opus-5-5, separate session from the implementing run (d0e73b31); agent-provisional, not human approval
- Scope: `git diff origin/main...HEAD` (code, templates, workflows, tests), against `spec.md`, `plan.md`, `data-model.md`, `contracts/`
- Read: `docs/policies/engineering.md`, `AGENTS.md` invariants, constitution BL-INV-001 to BL-INV-006
- Verdict: approved

## Behavior and boundaries checked

- **Requirement coverage.** Each FR has a mechanism: workflow steps (FR-001), `check_discovery` sections, markers, decisions and IAC list (FR-003, FR-004, FR-006), the failed-validation question round with operator-state attribution (FR-007, FR-008, FR-010), Autonomous assume-or-block through the existing `clarification` point and block contract (FR-009), `check_spec` traceability (FR-011, FR-012), `check_intent` untouched (FR-013), metrics (FR-015), the Autonomous write boundary (FR-016), the decomposition stop in the command (FR-017). FR-002 and FR-014 are prompt and review rules, as the spec's Assumptions state.
- **Source authority.** The brief never becomes a requirement source after specification: only `check_spec` reads it, and intent binds the `spec.md` digest alone (`test_brief_edit_after_intent_leaves_intent_valid`). No second source of truth.
- **Reuse.** Autonomous assumptions reuse `record-decision --point clarification`; `autonomy.current` keeps them alongside the later clarify step's entries, since neither supersedes the other. Operator state follows `_approval_path`/`state_dir`. The snapshot reuses `_gh`, `_gh_list` and `repository()` pinning.
- **Fail closed.** Malformed operator state fails in a run; a missing brief after `ran` fails; pre-filled or changed answers fail; a changed question fails; blocking status never passes. Structural checks run before a round is recorded, so a malformed brief never consumes a round.
- **Partial failure.** The round is saved before the validation fails, so a crash between them cannot let an agent answer first. A human-gated start whose Issue cannot be read continues with an "unavailable" snapshot (contract); the Autonomous start still refuses.
- **Compatibility.** Features without a brief or `ran` keep today's `spec` check (PD-0002); checked live: `artifacts.py spec --feature` passes for `specs/12-cli-install-doctor`, `specs/17-draft-pr` and `specs/27-autonomous-core`. Workflow versions are bumped (`ballast-feature` 1.2.0, `ballast-autonomous` 1.1.0) and the digest pin is updated on purpose. `tools/setup` changes a comment only.
- **Scope.** No unrelated refactor; `_gh_list` gains a `category` parameter so the human-gated read reports `forge`, not `ineligible`.
- **Complexity.** About 890 lines in `artifacts.py`, larger than the plan's estimate of 400 to 600 lines of Python and tests. The parser is long but each helper owns one rule of `data-model.md`, and the tests reach every refusal. No abstraction without a second use.

## Findings

- id: ENG-001
  severity: high
  location: `tests/test_spec_workflow.py` `AutonomousDiscoveryEngineTests.test_safe_gap_is_assumed_and_recorded`
  invariant_or_requirement: AC-010 evidence; testing policy (tests must run green)
  evidence: The test failed in the first full run: its assumed decision used the fixture's default `Sources`, citing `docs/policies/demo.md`, which does not exist in the engine fixture repository, so `validate-discovery` correctly refused it. The implementing run could not execute tests, so this was never observed.
  required_action: Fix the fixture to cite files the fixture repository has (`Issue #27 body`, `README.md`), without relaxing the citation check.
- id: ENG-002
  severity: low
  location: `tools/spec_workflow/artifacts.py` `_discovery_state_path`
  invariant_or_requirement: Edge case "Continuing an existing feature"
  evidence: Operator state is keyed by the feature path, not the run. A second human-gated run on the same feature reuses earlier rounds; if the discover agent rewords an already-asked question, validation fails with "restore them as asked". The message names the recovery, and keeping questions stable across reruns is what the command asks ("update it instead of starting over").
  required_action: None now. If pilots show reruns that legitimately rephrase questions, add an operator-side reset.
- id: ENG-003
  severity: low
  location: `tools/spec_workflow/artifacts.py` `_changed_paths`
  invariant_or_requirement: FR-016
  evidence: The Autonomous write-boundary check sees only paths `git status` reports, so writes to ignored paths are not caught by this check. The confinement already binds `.specify/` and `.ballast/` read-only and protected inputs are checked separately.
  required_action: None; recorded as a known ceiling.
- id: ENG-004
  severity: low
  location: repository (lint)
  invariant_or_requirement: fast gate
  evidence: `uvx ruff check` reported 19 findings (D401 docstring mood, ISC004, RUF007, E501, S105 on a test variable named `secret`) and `ruff format --check` one file.
  required_action: Fix mechanically, without `noqa`.

## Resolution

- ENG-001: fixed in the fixture (`sources="[S: Issue #27 body] [S: README.md]"`); the citation rule is unchanged. `AutonomousDiscoveryEngineTests` (2 tests) pass; the full suite passes (tasks.md T042).
- ENG-002, ENG-003: accepted as low, no change.
- ENG-004: fixed (imperative docstrings, parenthesized implicit concatenations, `itertools.pairwise`, renamed test variable, formatted). `uvx ruff check` and `uvx ruff format --check` pass.

- Verdict: approved
