# Engineering review: adaptive `ballast init` (implementation recheck after fix cycle 3)

- Feature: `specs/13-adaptive-init`
- Review: `implementation-recheck` (kind `engineering`), after fix cycle 3 of 3. This is the last review, and no fix cycle remains.
- Reviewer: claude-opus-5-5 (same provider as the author, so independence is reduced)
- Base: `11134f1` (merge base with `origin/main`); head `bd6ac47` plus the run record

## Scope of this recheck

The cycle-3 fix input (`.specify/workflow-state/fix-input/13-adaptive-init.json`) has no findings and no verdicts. It holds only the three `[checks]` commands, which failed again. `git diff bd6ac47` touches only `specs/13-adaptive-init/autonomous/record.md`. Like cycles 1 and 2, fix cycle 3 changed no code, tests, templates or documentation. The change under review is still the three commits since `11134f1`, which touch 27 files:

- `tools/init` (new)
- the `init` bootstrap in `tools/ballast`
- the `[init]` declaration in `tools/cli.toml`
- `templates/init/*`
- `tests/test_init.py` and `InitBootstrapTests` in `tests/test_ballast.py`
- README, ADR-0012, the TECHNICAL-SPEC status line and AGENTS.md
- the `pyproject.toml` ruff include

## What was checked

- **Whole change re-read.** I re-read the whole change against `spec.md`, `intent.md`, `plan.md` and `tasks.md`; no `decisions.md` exists. Both kinds of repository go through the same stage sequence: check, inspect, choose, plan, git-init, ignore, write, patch, install, verify and report.
  - Creates happen only for absent files, use `O_EXCL|O_NOFOLLOW` and follow the link checks.
  - Setup's ignore block is appended once.
  - Every other change goes into one ignored patch.
  - Git runs only through `setup.GIT`, and installation only through in-process `Setup.main`.
  - Nothing writes trust, commits or adds an active `extra_allow`.
  - The CLI bootstrap validates the ref, fetches into the verified cache, refuses on the `[init]` and `[cli]` minimums, then runs `os.execv` on the fetched `tools/init` under `-I -S`.
  - Nothing contradicts the approved spec, the intent or the ADR-0002/ADR-0012 boundaries.
- **Earlier findings, checked in the source:**
  - `verifier()` (`tools/init:254`) still accepts any single `make` target, any `uv run` and any `uvx` line.
  - `tools/ballast:1781` still uses `parse_known_args`, and the parser in `tools/init` `cli()` still allows abbreviations.
  - The linked-AGENTS.md warning (`tools/init:1384`) still points at a patch that is not produced.
  - `decisions.md` still does not exist.
- **Checks.** The run record's Fix loop shows that in cycle 3, `uvx ruff check` and `uvx ruff format --check` exited 2 and the unit suite exited 1. The fix input's output tail gives the causes:
  - uvx cannot write the read-only `~/.local/share/uv/tools`.
  - The unit suite fails with `OSError: [Errno 30] Read-only file system` when `outside_temp()` (`tests/test_autonomy.py:89`) creates `~/.local/state/ballast-tests`. This breaks `setUpModule` in most modules, including modules this change does not touch.
  - The one failure, `test_governance`, is a subprocess exiting 5 under the same condition.

  No failure points to this change, and no code fix can clear one. The four cycles failed the same way, so ruff and the new tests have never passed in any recorded run.

## Conclusion

The implementation still meets the approved spec and plan. All open code findings are low or info. The run has used all three fix cycles and the feedback checks still fail. The runner treats that as an exhausted limit, which stops the run for a human whatever this verdict says. Before merge, the operator needs a passing gate run from an environment with writable `~/.local/state` and uv tool directories, recorded in the PR.

<!-- ballast-findings: begin -->
## Findings (recorded from the review draft)

- F-001 (low, spec-ambiguity, open): Still present: verifier() treats any single make target, any uv run and any uvx line from a CI run: step as a verifier, so a build or deploy step can become an active [checks] entry. Operator review before trust and confinement bound the impact.
- F-002 (low, implementation-bug, open): Still present: tools/ballast passes unknown arguments through (parse_known_args), and the ArgumentParser in tools/init allows abbreviations and later overrides, so an operator's --re or a repeated --project can diverge from what the CLI checked.
- F-003 (low, implementation-bug, open): Still present: a linked AGENTS.md without the Ballast section gets a warning that points at a proposed patch, but no patch is produced.
- F-004 (info, spec-ambiguity, open): Still present: decisions.md does not exist, so the FR-003 wording fix noted under PD-0019 is not recorded. Spec reconciliation should record it.
- F-005 (medium, missing-test, accepted-provisionally): Ruff and the unit suite have failed in all four cycles because ~/.local/state and the uv tool directory are read-only in the sandbox, so tools/init and its tests have never passed in a recorded run. No fix cycle remains and code cannot fix it. Merge review must see a passing gate run with writable state, recorded in the PR.
<!-- ballast-findings: end -->

## Resolution

- F-001: accepted (spec ambiguity, low). FR-012/AC-021 make a CI step that runs a verification command an active check; `make TARGET`, `uv run` and `uvx` are how many projects run their gate. Every active entry carries its evidence line, the operator reviews `ballast.toml` before `ballast trust`, and checks run confined with a sanitized environment. Narrowing the list is a product change left to a follow-up Issue if pilots show deploy steps becoming checks.
- F-002: fixed test-first. `tools/init` parses with `allow_abbrev=False`, and `--project` and `--ref` refuse a second value, so neither an abbreviation nor a repeated option passed through the CLI's `parse_known_args` can override the root or ref the CLI checked (`test_an_abbreviated_or_repeated_option_is_refused`).
- F-003: fixed test-first. A linked `AGENTS.md` without the section names its target and the section template instead of a patch that does not exist (`test_a_linked_agents_md_names_no_missing_patch`).
- F-004: resolved in spec reconciliation. FR-003's wording now matches the accepted clarification (an established repository is never asked; unresolved evidence is marked to confirm). It is a wording clarification of approved behavior, not a product change, so no `decisions.md` proposal was needed; the operator re-approves the spec at the continuation's `approve-intent` gate.
- F-005: resolved. ruff and the full suite pass on the host after the rebase (#82 also lets confined steps run them).

Gates on the host after the rebase onto `origin/main` (with #82): `uvx ruff check && uvx ruff format --check` pass; the full suite `uv run --no-project --isolated --python 3.13 --with pyyaml python -m unittest tests/test_*.py` passes (counts in [convergence.md](convergence.md)). The networked end-to-end run is in [e2e.md](e2e.md).

- Verdict: approved
