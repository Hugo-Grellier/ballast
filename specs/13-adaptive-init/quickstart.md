# Quickstart: validating `ballast init`

How to prove [spec.md](spec.md) holds. Behaviour is defined in [contracts/](contracts/); this guide only says what to run and what to expect.

## Prerequisites

- The fast gate: `uvx ruff check && uvx ruff format --check` and `uv run --no-project --python 3.13 --with pyyaml python -m unittest tests/test_*.py`.
- For the end-to-end run: `git`, `uvx`, network access, and a scratch `XDG_DATA_HOME`/`XDG_STATE_HOME` outside the scratch project and outside `/tmp` (the CLI refuses a standard directory in a temp root).

## Automated tests (offline)

`tests/test_init.py` runs `tools/init` in process with setup's fakes; `tests/test_ballast.py` covers the CLI bootstrap. Each fixture that completes also records a baseline with `launcher._trust` and asserts `launcher._refusal(root) is None` (the post-trust preflight).

| Criterion | Fixture and assertion |
| --- | --- |
| AC-001, AC-003, SC-002 | Empty directory, `--description`/`--stack` flags: `.git/`, `ballast.toml`, `.gitignore` with the block, constitution, `AGENTS.md`, `CLAUDE.md -> AGENTS.md`, `setup --check` current; a fake terminal shows exactly two prompts when flags are absent. |
| AC-002, AC-010, SC-001 | Blank, `.git`-only and established fixtures: after init, `_refusal` names the missing baseline; after `_trust`, `_refusal` is `None`, with the patch not applied. |
| AC-004 | No terminal, each flag missing in turn: exit 2, the message names the flag, the directory tree is byte-identical (no `.git` created). |
| AC-005 | No `--ref`: pin `v{VERSION}`; `--ref` with `..` or bad characters refused by the CLI; the fetch URL uses `REPOSITORY`. |
| AC-006, SC-003 | Python fixture (`pyproject.toml`, CI with `pytest`, `AGENTS.md`, `docs/policies/project/security.md`): digests of those files equal before and after. |
| AC-007, AC-011 | Same fixture: `.ballast/init/proposed.patch` holds the `AGENTS.md` section and `git apply --check` accepts it; the report names it; no `CLAUDE.md` created. Variant with only `CLAUDE.md`: neither created, patch targets `CLAUDE.md`. |
| AC-008 | Existing `.gitignore` without the block: the new content equals the old content plus the block (and one newline when missing). |
| AC-009 | A nested `docs/.gitignore` with `!policies/*.md`, which outranks the root block (a `!.ballast/spec_workflow/` rule cannot conflict: git never re-includes a path below the ignored `.ballast/`): exit 1 at `ignore`, the report names the rule, the patch comments it out, no installed entry and no setup journal exist, `ballast.toml` not written. |
| AC-012 | Established fixture: no file under `.github/` created; the report lists the optional templates. |
| AC-013, SC-005 | After every successful fixture: each `IGNORE_PROBES` entry holds, and `git check-ignore` rejects every created project-owned path. |
| AC-014 | No `trusted.json` in operator state after init; the report lists the protected inputs and `ballast trust`. |
| AC-015 | Audit hook on `subprocess.Popen`/`os.exec*`/`os.system`: only `git` starts; fixture `Makefile`, `package.json` scripts and CI commands write a marker file if run, and the marker never appears. |
| AC-016 | Repository config sets `core.hooksPath`, `core.pager` and `core.fsmonitor` to marker-writing scripts plus a `post-checkout` hook; no marker after init. |
| AC-017 | `.github` linked outside the root: skipped with reason `symbolic link`, nothing read through it (the target is unreadable to make a read fail loudly); `docs/policies` linked outside: refusal in `check`, target untouched. |
| AC-018 | No commit (`git rev-list --all` empty in a blank fixture), no remote added; `git init` ran only in the no-repository fixture (inode of an existing `.git/config` unchanged). |
| AC-019 | Generated `ballast.toml` parses with no `agents` table; each `extra_allow` line is commented and marked `inferred`. |
| AC-020 | Setup fakes fail `specify init`: exit 1 at `install`, the message is setup's stage message, the previous installation (or none) is kept. |
| AC-021, AC-022, SC-006 | CI `run: pytest` and `run: \|` block lines become active with `# evidence: PATH:LINE`; a `run:` with `${{ }}` or `&&` is ignored; `Makefile` `check` is commented `inferred`; every active entry has an evidence comment. |
| AC-023 | Constitution and `AGENTS.md` contain the description's source or `TO CONFIRM`, and no unreplaced `[UPPERCASE]` placeholder; the placeholder-table test covers `templates/AGENTS.md`. |
| AC-024 | Repository with only `src/main.zig`: stack `neutral`, marked inferred. |
| AC-025 | Malformed `pyproject.toml`, `package.json` larger than 256 KiB, non-UTF-8 workflow: each skipped with its reason; init completes. |
| AC-026 | `origin` as HTTPS, SSH and `ssh://` GitHub URLs: `repository = "OWNER/REPO"`; GitLab URL and no remote: `[github]` commented, report says how to add it. |
| AC-027 | No direct check: no `docs/policies/project/testing.md`; existing one kept byte-identical. |
| AC-028, AC-029, SC-004 | Run init twice on each completed fixture: `git status --porcelain` and every tracked digest equal after the second run; reports equal. Drift fixture (new CI step after adoption): patch appends a commented `# ballast init found:` line; `ballast.toml` unchanged. |
| AC-030 | `ballast.toml` present, constitution and ignore block missing: both created, pin unchanged. |
| AC-031 | Copy of Ballast's own tracked files in a scratch repository: no tracked file changes. |
| AC-032 | Report contains the five readiness lines and `Next:`. |
| AC-033 | CLI with a fake standard whose `tools/cli.toml` lacks `[init]`, and one whose `[cli] minimum` exceeds `VERSION`: exit 2, remedy named, scratch root unchanged, no `execv`. |
| AC-034 | Each forced stop (`choose`, `ignore`, `install`): `stopped at STAGE`, `Written:`, `Not written:`, `Next:`. |

## End-to-end scratch run (networked, recorded in the PR)

1. `export XDG_DATA_HOME=$HOME/.cache/ballast-e2e/data XDG_STATE_HOME=$HOME/.cache/ballast-e2e/state BALLAST_STANDARD_DIR=$PWD` from the feature checkout.
2. Blank: `mkdir -p ~/scratch/blank && cd ~/scratch/blank && ballast init --description "Scratch service" --stack python`. Expect exit 0, the readiness block, `Next: ... ballast trust`. Then `ballast trust`; the preflight passes: `python3 -IS $BALLAST_STANDARD_DIR/tools/spec_workflow/launcher.py status --json` prints `"refusal": null`.
3. Established: a scratch repository with `pyproject.toml`, `.github/workflows/ci.yml` (`run: pytest`), `Makefile` (`check:`) and an `AGENTS.md`; `ballast init`. Expect no question, `AGENTS.md` and CI byte-identical (`git diff --exit-code`), the patch named, `pytest` active, `make check` inferred. Then `ballast trust` and the same preflight.
4. Rerun `ballast init` in both: `git status --porcelain` unchanged, same report.
5. Record the commands, exit codes and the two reports in the PR, with the fast and full local gates.
