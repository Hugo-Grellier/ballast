# Documentation review 1: Source-backed discovery brief

- review: documentation
- Reviewer: claude/claude-opus-5-5, separate session from the implementing run (d0e73b31); agent-provisional, not human approval
- Read: `docs/policies/documentation.md`; diff of `templates/policies/spec-kit-workflow.md` (T040), `specs/TECHNICAL-SPEC.md` (T041), `templates/spec-kit/templates/spec-template.md`, the discover and clarify commands, `extension.yml`, `tools/spec_workflow/run.py` module docstring
- Verdict: approved

## Checked

- Lifecycle diagrams in both modes show `discover` before `specify`.
- The new "Discovery brief" section states the brief's content, the markers, its non-authority, the per-mode handling of open decisions, the operator's answer-and-resume procedure (`**Status**` answered, fill `**Answer**`, `ballast run resume <run>`), the decomposition stop and that bugfix and assess workflows are unchanged and completed work is not retrofitted.
- The runner-contract table has `discover` and the extended `specify` row; the Autonomous table has `speckit.ballast.discover` with `record-discovery` and `validate-discovery`.
- The failure state of a human-gated start that cannot read the Issue is documented, and so is the Autonomous start still refusing.
- `TECHNICAL-SPEC.md` changes only the workflow-steps section, as T041 required. The installed `docs/policies/` copy is not edited (it is rebuilt from the pinned version).
- The spec template comment tells the author the marker and `IAC-n` rules that `validate-spec` enforces.
- No ADR is needed: the plan reuses existing decision points and the failed-validation pattern; no accepted decision changes.
- Every relative link in installed documents resolves (governance tests in the full suite).

## Findings

- DOC-001 (low): the snapshot paragraph listed "no `gh`, no network" as the reasons a human-gated start cannot read the Issue, but a missing `[github] repository` in `ballast.toml` has the same result (`read_issue` raises). Required: name it.
- DOC-002 (medium, follows SEC-001 and SEC-002): the policy and the contract must say that comment bodies are quoted and that only an owner, member or collaborator comment can settle a decision.
- DOC-003 (info): the `ballast-autonomous` workflow comment and the policy describe `record-discovery` before `validate-discovery`; consistent with the workflow file.

## Resolution

- DOC-001: fixed in `templates/policies/spec-kit-workflow.md`.
- DOC-002: fixed in `templates/policies/spec-kit-workflow.md` (snapshot paragraph and Discovery brief section) and `contracts/workflow-and-validator.md`.

- Verdict: approved
