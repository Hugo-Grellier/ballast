# Review: implementation (documentation)

- Role: documentation reviewer
- Agent/model: claude/claude-opus-5-5, the driving agent; reduced independence (see the security review)
- Base: `1176309..bf5359c`
- Artifacts: `README.md`, `docs/adr/0006-recoverable-installation.md`, `docs/adr/0007-verified-cache-and-update-preview.md`, `docs/policies/project/testing.md`, module docstrings of `tools/setup`, `tools/ballast`, `tools/spec_workflow/launcher.py`, `tools/cli.toml`, the feature's contracts; `docs/policies/documentation.md`
- Verdict: approved

## What was checked

- README: install paragraph (cache record and verification, staging, no-op, worktree copy, never-touched paths), "Only `setup` and `preview` download", and the new "Updating the pinned version" section: update the CLI first (DEC-0001), preview, pin change, setup, trust, checks; failure messages; interrupted setup; retry; rollback with exact commands (at most three plus review, SC-007); what versions before this feature do not guarantee. `ReadmeUpdateTests` checks every `ballast` command shown exists.
- Each command's usage and docstring names its new behavior (`preview`, `--check` states, launcher lock and refusals, `[setup]`/`[runs]` comments).
- ADRs: ADR-0006 and ADR-0007 are new, status proposed until merge; ADR-0002 is extended, not rewritten.
- Contracts and data model updated for the implementation's choices (kept installation, `entries` in the record, `.fetch-<ref>+` naming, `install standard` and `stage` stages).

## Findings

| ID | Class | Severity | Location | Evidence | Required action |
|---|---|---|---|---|---|
| DOC-001 | spec violation | medium | `docs/policies/project/testing.md` | Its critical evidence still said "only `setup` downloads", false once `preview` fetches, and did not name the new recovery evidence. | Update it. |
| DOC-002 | spec ambiguity | low | `README.md` rollback | The example `git checkout HEAD~1 -- ballast.toml` assumes the pin change was the last commit. | Phrased "for example" next to "restore the previous `ref`"; accept. |
| DOC-003 | spec ambiguity | low | `README.md` | It names v0.5.0 as the last version without these guarantees, assuming this feature ships in the next release. | True for any next release; accept. |

## Resolution

- DOC-001: fixed in `bf5359c`.
- DOC-002, DOC-003: accepted.
