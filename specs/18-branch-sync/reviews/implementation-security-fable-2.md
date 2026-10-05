# Implementation security review 2: branch synchronization (#18)

- Reviewer: Claude Fable, round 2 (same provider as the author; Codex quota exhausted until 2026-10-10, so no cross-provider review this round either)
- Date: 2026-10-05
- Risk: R2 (unchanged)
- Scope: commit `17ae84f` (the round-1 fixes and the engineering-review fixes E-01..E-06, S-01..S-05) and `da590d0` (decisions), read as the current `tools/spec_workflow/branch_sync.py`, `draft_pr.py`, `run.py` end to end, against [round 1](implementation-security-fable-1.md), ADR-0005, the contract and `data-model.md`. Each round-1 attack was reproduced again with git 2.53 in scratch repositories under `/tmp` using the module's exact argv and environment; the new tests were read and run. Nothing in the worktree was modified except this file; no `ballast` or `specify` command ran. Trust model as in round 1.

## Round-1 findings

| Finding | Status | Evidence |
| --- | --- | --- |
| SEC-001 (high): `status --ignore-submodules=none` ran a nested repository's clean filter | Resolved | `branch_sync.py:1091-1105`, the one `status()` every caller uses, passes `--ignore-submodules=dirty`. Reproduced in `/tmp/bsync-r2-sub2` (gitlink, nested `.git/config` filter, same-size edit so content is read): with `none` both the `--untracked-files=normal` and the `--ignored=matching --untracked-files=all` listings created the marker; with `dirty` neither did, and a staged gitlink change is still reported (`M  sub`). `read-tree -m -u` and `diff-files` under `submodule.recurse=false` did not enter the nested repository either. Test `test_nested_repository_configuration_never_runs` plants the same shape and also asserts the gitlink change blocks as `dirty`. |
| SEC-002 (medium): Issue number from agent-writable `inputs.json` on `resume` | Resolved | `start` pins `feature` (`branch_sync.py:800-804`, validated by `FEATURE_PATTERN` in `__init__` and again by `run._option_feature` / `_start_autonomous` with `autonomy.FEATURE`); `resume` and `continue` take `feature` from the pin and set `self.issue` from it (`829-830`); a pin without `feature` blocks `wrong-branch` (`820-828`). `self.issue` is `None` unless `starting` (`527`), so the `inputs.json` value passed by `run.py` only attributes the ledger event. Tests `test_issue_number_comes_from_the_pin` (module) and `test_resume_takes_the_issue_number_from_the_pin` (`run.main(["resume", ...])` end to end: `not-feature-branch`, no engine, snapshot unchanged) are the round-1 test. Contract § Entry point now states that every rewrite-rule input is operator state. |
| SEC-003 (medium): stale records in the agent-writable common dir, unbounded, link-capable | Resolved | Writer: `draft_pr.stale_dir(root, feature)` = `<state_dir>/branch-sync/stale/<sha256(feature)[:16]>/<event_id>.json` via `_write_json` (`branch_sync.py:1818-1834`). Reader: `_stale_entries` lists only that directory, `.json` suffix, `_small_json` opens `O_NOFOLLOW`, requires `S_ISREG`, reads at most 16 KiB + 1 and refuses larger (`draft_pr.py:548-560`); `MemoryError`/`RecursionError` are caught; newest 20 entries with "and N earlier" (`589-592`); paths rendered by `_code` as code spans with backticks removed. Tests: `test_planted_or_oversized_records_stay_bounded` (500 records + 100 MiB sparse file, 21 lines, body under 10 000 bytes), `test_paths_are_code_spans_and_bounded` (`[review passed](https://example.test)` inside backticks), `test_records_in_the_git_directory_are_ignored`. The remaining rendering edge is SEC-007 below. |
| SEC-004 (low): replace refs, grafts, commit-graph; unvalidated hashes | Resolved | `_env()` sets `GIT_NO_REPLACE_OBJECTS=1` and `GIT_GRAFT_FILE=/dev/null` for both runners (`579-583`); `core.commitGraph=false` in `NO_RECURSION` and `NO_MAINTENANCE` (`52-66`). Reproduced in `/tmp/bsync-r2-cg`: `git replace --graft feat main` and `.git/info/grafts` each made `merge-base --is-ancestor main feat` answer yes under the round-1 environment and no under the fixed one; `rev-list main..feat` returned the real commit. `rev-list` lines and the `parent` header are `COMMIT`-checked before use (`1472-1474`, `1485-1487`). Tests: `test_replace_refs_and_grafts_do_not_hide_the_base` (both shapes, outcome `synchronized`), `test_runners_harden_every_command` (both variables on every environment, `core.commitGraph=false` in every argv). |
| SEC-005 (low): `objects/info/alternates` honored by the throwaway | Resolved | `shape()` resolves `rev-parse --path-format=absolute --git-path objects/info/alternates` and blocks `git-unavailable` / "alternate object store" on `lexists` (`851-860`), before `ls-remote` or `fetch`. Checked that the path resolves to the common directory from a linked worktree and from a `--separate-git-dir` checkout, and that a dangling symlink is caught. Contract, policy table and ADR-0005 carry the row; `test_alternates_are_refused` asserts the block, no network command and an unchanged snapshot. |
| SEC-006 (low): throwaway allow-list was an `assert` | Resolved | `throwaway()` raises `RuntimeError` for a command outside `THROWAWAY_COMMANDS` or a missing bare repository (`644-647`); `test_throwaway_allow_list_holds_without_assert`. The remaining `assert`s (`record_path`, `classify`, `recheck`, `old_base`) guard internal invariants, not agent input, and under `-O` would fail later as `internal-error`. |

Engineering fixes, security impact:

- E-01 (`run._option_feature`): exactly one `-i feature_directory=` matching `autonomy.FEATURE`, else `start` is refused before any check or pin; `--input=k=v` single-token form is refused too (fail closed). Autonomous `start` validates the feature against the Issue number (`run.py:459-462`) and passes it to the same check (`527`).
- E-02: `in_progress()` before the detached-HEAD stop at `start` is the same `rev-parse --git-path` plumbing; no new input.
- E-03: recovery rows 4 and 5 call `overlap_from(record, old)` with `old_base`/`new_base` from the operator record, `COMMIT`-validated in `valid_record` and probed with `has()`; `find_overlap` runs `diff-tree`/`ls-tree` in the checkout and reads the run's ledger only for the `stale_review` flag (round-1 I-3, unchanged). A `protected-input` block now carries `overlap`/`stale_*` and writes the stale record; both are operator state. The write-ahead record gained two fields; `valid_record` requires both or neither. No authority input is touched.
- E-04: row 5 replays with `--attr-source=<fetched base>` (`1246-1248`), closing the one place where the pushed feature commit supplied `.gitattributes`; `test_row_5_reads_attributes_from_the_fetched_base`.
- E-06: a recorded `base_commit` missing from the store blocks `diverged` instead of guessing a merge base (`1434`); narrower, fail closed.
- S-01..S-05: `new_pin` removed in favor of `save_pin(final=True)`, `_text = draft_pr.printable`, `_Block.retryable`/`interrupted` fields. Behavior-neutral for the boundary; a continuation still writes its pin only on a non-blocked outcome.

## New findings

### Low

#### SEC-007: a path can carry the Draft PR section marker into the raw body now that paths skip `_escape`

- Label: implementation bug (defense in depth; round 1 recorded "no ... marker spoof is possible" because `_escape` turned `<` into `&lt;`)
- Location: `tools/spec_workflow/draft_pr.py:470-472` (`_code`), reached from `_stale_record` at `509`; consumer `reuse()` at `817-826`
- Evidence: `_code` applies `printable` and strips backticks only, so a repository path equal to `<!-- ballast:draft-pr:end -->` renders as `` `<!-- ballast:draft-pr:end -->` `` and the raw body then contains two end markers. Checked with `_stale_record` directly: the entry holds one `MARK_END`, and a body built from it counts two. `reuse()` then returns `reused` with `section-unmanaged` and never updates the section again, so later stale-evidence entries stop reaching reviewers. Rendering is otherwise safe: inside a code span GitHub treats `<`, `@` and `[..](..)` as literal text. Reach is narrow: the path must be changed on both sides of the synchronization, so the base branch must already carry a file with that name; an agent alone cannot cause it. No authority is gained and the failure is fail-safe (nothing is overwritten).
- Fix: in `_code`, also neutralize the comment opener, e.g. `printable(text).replace("`", "").replace("<!--", "<!- -")`, or refuse a path that contains `MARK_BEGIN`/`MARK_END` in `_stale_record`. One line either way; update the "code span with backticks removed" sentence in `data-model.md` § Stale evidence record.
- Test: in `StaleEvidenceSectionTests.test_paths_are_code_spans_and_bounded`, add the path `<!-- ballast:draft-pr:end -->` and assert `draft_pr._section(...)` contains `MARK_END` exactly once.

### Informational (no change required)

- I-6: `_write_json` creates `branch-sync/` and `branch-sync/stale/` with the process umask (0755 observed under `umask 022`); only the leaf directory is forced to 0700 and the file to 0600. They sit under `state_dir`, which the launcher creates 0700 (`launcher.py:262`), so nothing is exposed; same pattern as `draft-pr/`.
- I-7: the Draft PR checkpoint still takes `feature` from `inputs.json` (`draft_pr.identify`), validated by `FEATURE_PATTERN`, and `stale_dir` is keyed by it. An agent that rewrites it changes the whole PR identity (Issue number, PR lookup) and is caught by the wrapper's run-state digest before the checkpoint (round-1 lead 1); the dependency now reaches the PR section only, no longer the rewrite rule.
- I-8: at `start`, a pre-existing pin for the fresh run ID that has `branch` but no `feature` (a 32-bit ID collision with a #17 pin) is kept as is; the start proceeds with the Issue number from the command line and the next `resume` blocks `wrong-branch`. Fail closed, negligible likelihood.
- I-1, I-2, I-3, I-5 from round 1 are unchanged and still informational. I-4 is moot (the record moved).

## Round-1 sound areas, rechecked for regression

| Area | Result |
| --- | --- |
| Push URL | `_url()` unchanged: owner and name from the protected `ballast.toml`; `origin` contributes the scheme only. |
| Lease | `push()` unchanged: `--force-with-lease=refs/heads/<branch>:<observed>` with `observed` from the same invocation's advertisement or the operator record; `push-failed` now carries `retryable` through `_Block`. |
| Base and non-feature branches | `fast_forward_base` and `follow_published` call `mutate(..., push=False)`; recovery row 2 still requires `records_push`; `kind()` reads `self.issue`, which is now operator state on every entry point. |
| Hooks, fsmonitor, filters, prompts | `GIT_HARDENING` and `filter_flags()` unchanged on the checkout; the throwaway's empty-config `--template=` init, prompt variables and `GIT_CEILING_DIRECTORIES` unchanged; `DROPPED_ENV` unchanged (`GIT_DIR`, `GIT_WORK_TREE`, `GIT_COMMON_DIR`, `GIT_INDEX_FILE`, `GIT_OBJECT_DIRECTORY`, `GIT_ALTERNATE_OBJECT_DIRECTORIES`, `GIT_NAMESPACE`, injected configuration). The two added variables only remove inputs. |
| Credential helper | still only from the operator's global or system configuration; the throwaway never reads the checkout's `.git/config`. |
| State paths | pin `draft-pr/<run_id>.json` (`RUN_ID_PATTERN`), record and lock `branch-sync/<sha256(branch)[:16]>`, stale `branch-sync/stale/<sha256(feature)[:16]>/<uuid hex>.json`: every component is a validated ID or a hex digest, no traversal; `_pin_path` raises on an invalid run ID and `read_pin` returns `{}`. |
| New git invocation | `rev-parse --git-path objects/info/alternates` runs in the checkout environment; failure raises and becomes `internal-error` (fail closed). |
| Program resolution | `draft_pr._resolve`/`ledger.resolve_program` untouched by the fix. |

## Verification

- `uvx ruff check` and `uvx ruff format --check` on the touched tool and test files: clean.
- `uv run --no-project --python 3.13 --with pyyaml python -m unittest tests/test_branch_sync.py tests/test_draft_pr.py tests/test_spec_workflow.py tests/test_autonomous_run.py` from the worktree with the normal `HOME`: 345 tests, 344 pass; the one error is `InterpreterStartupTests.test_only_no_site_skips_pth_startup_hooks`, whose scratch venv under `/tmp` fails its own `sysconfig` probe in this sandbox (outside this feature's diff, not a regression). Every test named in the table above passed. A first run with `HOME` under `/tmp` failed wholesale because `state_dir` refuses a temp root, which is the intended behavior.
- Reproductions: `/tmp/bsync-r2-sub2` (SEC-001), `/tmp/bsync-r2-cg` (SEC-004), `/tmp/bsync-r2-alt` (SEC-005 path resolution), `draft_pr._stale_record` in-process (SEC-003 rendering, SEC-007), `branch_sync._write_json` in a temp directory (I-6).

## Required before merge

1. SEC-007: the one-line neutralization in `_code` (or the refusal in `_stale_record`) and the marker-count assertion. No further security round is needed for it.

- Verdict: APPROVE WITH CHANGES
