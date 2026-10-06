# Documentation review: 22-ui-demo

- Kind: documentation
- Reviewer: claude/claude-opus-5-5, agent-provisional, same provider as the author
- Scope: working tree against the branch start; required because the change touches `README.md`, an ADR and user-facing workflow policy

Policy read: `docs/policies/documentation.md`. `docs/policies/project/documentation.md` does not exist.

## What was reviewed

- `templates/policies/spec-kit-workflow.md`, new "Demo capture" section (the source of the installed `docs/policies/spec-kit-workflow.md`)
- `README.md` copy-once template list
- `specs/TECHNICAL-SPEC.md` §9.1 status paragraph
- `docs/adr/0013-demo-capture-dispatch.md` (new; ADR history preserved, no earlier ADR edited)
- `tools/spec_workflow/ledger-schema.md` (`demo_capture` kind)
- `tools/spec_workflow/run.py` usage docstring and `templates/github/workflows/ballast-demo.yml` header comment

## Coverage of FR-019 and AC-007/AC-009

- **Contract**: a complete `[demo]` example with each key's limit (retention 1-90, timeout 1-60, 1-20 scenarios, the name pattern, command and environment lengths). It also says to run `ballast trust` after editing. Matches `demo.py` (`RETENTION_DAYS`, `TIMEOUT_MINUTES`, `SCENARIO_LIMIT`, `NAME`, `COMMAND_LIMIT`, `ENVIRONMENT_LIMIT`).
- **Installing the workflow**: copy the template of the pinned version to the default branch. It also states that every feature branch must carry it unchanged, gives the `workflow-differs` refusal and its remedy, and explains why: the cache scope. This matches ADR-0013's consequences.
- **Requesting**: the command, `--no-wait`, the 120 s wait, the lock and in-progress refusal, the output line format, the exit codes (refusal/GitHub failure 1, dispatched 0), and every refusal reason. Each matches `REMEDIES` in `demo.py` plus `untrusted`/`lock-held` in `run.py`. `gh-forbidden` names the Actions write access the operator needs.
- **Outcomes**: the state table lists every reason in `demo.REASONS` under its outcome. It covers `stale`, `not yet requested`, `not configured` and `configuration invalid`, and explains that exit 124/137 and OOM read as `timed-out`. It also covers `no longer declared` and the `continue` case. I compared it with `resolve`, `format_line` and `lines`.
- **Data and access**: seeded, nonsensitive data and fake accounts. The video is readable by anyone with repository read access, and by everyone on a public repository (AC-009). The template header repeats this.
- **Local reproduction**: each line names the declared command, and the reader runs it at the captured commit without credentials. A changed command is flagged (AC-007).
- **Non-evidence**: the section's intro and the packet's intro line say a video is never evidence, never changes a criterion's state and is never an approval (FR-014).

## Consistency

The README, TECHNICAL-SPEC, ADR-0013, ledger schema and policy section describe the same model: an operator-only request, feature-branch dispatch, the blob-identity check, the `head_sha` postcondition, no secrets, a read-only token and no local execution. The ADR is marked `proposed` and agent-provisional until merge, and TECHNICAL-SPEC cites it as proposed. No screenshot applies: the change adds no visible UI of its own.

## Residual observations

- The policy says a refusal or a GitHub failure "dispatches nothing, records nothing". That holds for both. However, an unexpected local error after a successful dispatch, such as a failed ledger append, also prints `failed-retryable (internal-error)` and exits 1, although a run was dispatched. An operator reading only the policy could assume nothing ran. This is rare and harmless: the run is unlinked and never shown as `captured`. A sentence or a distinct reason would make the claim exact.
- The README's generic "Using the copy-once templates" section does not say that `ballast-demo.yml` must be committed on the default branch before feature branches are cut. The policy section says it, and the README entry links the template, whose header comment says it too.

Same-provider review: independence is reduced.

<!-- ballast-findings: begin -->
## Findings (recorded from the review draft)

- F-001 (info, implementation-bug, resolved): The policy says a refusal or GitHub failure dispatches and records nothing, which holds. An unexpected local error after a successful dispatch, such as a failed ledger append, also prints failed-retryable (internal-error) and exits 1 although a run was dispatched. That run is never linked or shown as captured. Name this case or give it a distinct reason. Fixed in 1b0cc91: the policy names a local error after a successful dispatch.
- F-002 (info, spec-ambiguity, resolved): The README's copy-once section does not say ballast-demo.yml must be on the default branch before feature branches are cut. The policy section and the template header say it, and the README links the template, so this is a discoverability nit only. Fixed in 1b0cc91: the README entry says to commit the workflow on the default branch before cutting feature branches.
<!-- ballast-findings: end -->
