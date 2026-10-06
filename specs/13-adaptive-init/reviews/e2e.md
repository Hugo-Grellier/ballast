# End-to-end runs (SC-007, quickstart "End-to-end scratch run")

- Date: 2026-10-06
- Host: Linux, Spec Kit CLI 1.0.11 fetched by setup through `uvx` (networked), git 2.x
- Standard: this branch after the rebase onto `origin/main` (#82), through `BALLAST_STANDARD_DIR=<this worktree>`; the CLI is this branch's `tools/ballast` (v0.7.1), run as `/usr/bin/python3 -IS <worktree>/tools/ballast` because the installed CLI has no `init` yet
- Operator state: `XDG_DATA_HOME` and `XDG_STATE_HOME` under a fresh `~/.cache/ballast-e2e-13/`, outside the scratch projects and every temp root
- Scratch projects: a session scratch directory; nothing ran in the feature worktree

## Scenario 1: blank directory (AC-001 to AC-003, AC-005, AC-018)

`ballast init --description "Scratch service" --stack python` in an empty directory: exit 0.

```
ballast init: blank repository at <scratch>/e2e/blank (pin v0.7.1)
Written: .git/, .gitignore, ballast.toml, .specify/memory/constitution.md, AGENTS.md, CLAUDE.md
Kept: none
To confirm (inferred): check "pytest" (the chosen stack)
GitHub repository: not set (no origin remote); add [github] repository = "OWNER/REPO" to ballast.toml for intake and Draft PRs
Readiness:
  instructions    ready      AGENTS.md has the Ballast workflow; CLAUDE.md links to it; its links resolve
  ignored-paths   ready      18 probes hold; project-owned files are not ignored
  pinned-version  ready      v0.7.1 installed and current
  trust-boundary  ready      no trust baseline; the launcher refuses until `ballast trust`
  checks          warning    no active [checks] commands; confirm the inferred ones in ballast.toml
Not written (optional): .github/pull_request_template.md, .github/dependabot.yml, .github/workflows/pr-title.yml, stack CI; copy them from the standard's templates/github/ (README: Using the copy-once templates)
Review these protected inputs: ballast.toml, .specify/, .ballast/spec_workflow/
Next: review the files above, then run `ballast trust`
```

- `CLAUDE.md -> AGENTS.md`; `ballast.toml` pins `v0.7.1`, `pytest` and `Bash(pytest*)` are commented and marked inferred, no `agents` table is active.
- `git status --porcelain` lists only the project-owned files (`.gitignore`, `.specify/` memory, `AGENTS.md`, `CLAUDE.md`, `ballast.toml`); `git rev-list --all` is empty and there is no remote: no commit, no push.
- `ballast trust`: exit 0 ("trusted 129 workflow inputs"). Then `launcher.py status --json` prints `{"installed": true, "refusal": null}`: the preflight passes after one trust (SC-001).
- Rerun `ballast init` (no flags): exit 0, `Written: none`, `git status --porcelain` and the digests of every untracked project file unchanged, readiness block unchanged except `trust-boundary` (now "a trust baseline matches these inputs"), `Next: run \`ballast run\``.

## Scenario 2: established repository (AC-006 to AC-012, AC-026, AC-028)

A shallow clone of the public `pypa/sampleproject` (`pyproject.toml`, `.gitignore`, two CI workflows, no instructions file), plus one local commit adding a three-line `AGENTS.md`. `ballast init </dev/null` with no flags and no terminal: exit 0, no question.

```
ballast init: established repository at <scratch>/e2e/established (pin v0.7.1)
Written: ballast.toml, .specify/memory/constitution.md
Kept: .gitignore, AGENTS.md
Appended the Ballast ignore block to .gitignore
Proposed patch: .ballast/init/proposed.patch (AGENTS.md: Ballast section)
Readiness:
  instructions    warning    AGENTS.md has no Ballast section; see the proposed patch
  ignored-paths   ready      18 probes hold; project-owned files are not ignored
  pinned-version  ready      v0.7.1 installed and current
  trust-boundary  ready      no trust baseline; the launcher refuses until `ballast trust`
  checks          warning    no active [checks] commands; confirm the inferred ones in ballast.toml
Not written (optional): .github/pull_request_template.md, .github/dependabot.yml, .github/workflows/pr-title.yml; copy them from the standard's templates/github/ (README: Using the copy-once templates)
Review these protected inputs: ballast.toml, .specify/, .ballast/spec_workflow/
Next: review the files above, then run `ballast trust`
```

- Every tracked file except `.gitignore` has the same digest as before; the `.gitignore` diff is exactly setup's ignore block appended. No `CLAUDE.md` and nothing under `.github/` was created.
- `git apply --check .ballast/init/proposed.patch` accepts the patch, which appends the Ballast section to `AGENTS.md`; the patch is not applied.
- `ballast.toml` gets `[github] repository = "pypa/sampleproject"  # evidence: git remote origin`. The constitution cites `pyproject.toml` for the description and stack.
- The CI steps are `python -m pip ...`, `python -m build .` and `python -m nox -s ...` (one with `${{ }}`): none is a recognised verifier (R7), so no check is active or inferred.
- `ballast trust`: exit 0; `launcher.py status --json` prints `{"installed": true, "refusal": null}`.
- Rerun (after a trust, with an unchanged standard): exit 0, setup did nothing (no Spec Kit output), `Written: none`, `git status --porcelain` unchanged, `trust-boundary` "a trust baseline matches these inputs", `Next: run \`ballast run\``. No commit beyond the fixture's own; the remote is unchanged.

## Findings

1. **Misleading `checks` detail** (scenario 2): with no check found at all, the readiness line said "confirm the inferred ones in ballast.toml", but `ballast.toml` had nothing to confirm. Fixed test-first (`ReviewFindingTests.test_no_check_at_all_is_named_as_missing`): the line now says "no check command was found; add the project's gate in ballast.toml" when `ballast.toml` has no commented `[checks]`. The scenario 2 rerun above shows the new wording.
2. An intermediate rerun of scenario 2 reinstalled because the standard directory changed under it (the fix above edited `tools/init`), which invalidated the trust baseline as designed; after one `ballast trust`, the rerun with the unchanged standard was a no-op. Not a defect: a local standard is not a fixed release.
3. Not a defect, but worth a follow-up Issue if pilots ask for it: `python -m nox` and `python -m tox` are not recognised verifiers (R7's `python -m` list is `pytest`, `unittest`, `mypy`), although `nox` and `tox` are when invoked directly.

- Verdict: PASS
