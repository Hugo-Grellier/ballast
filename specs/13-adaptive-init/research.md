# Research: Adapt Ballast to blank and established repositories

Phase 0 of [plan.md](plan.md). Each entry resolves an open design point of [spec.md](spec.md). This is an Autonomous run: every decision here is agent-provisional, not human-approved (BL-INV-006); merging the PR is the single human approval.

Code evidence: `tools/ballast` (`main`, `command_standard`, `ensure_standard`, `read_pin`, `manifest`, `declarations`, `PIN_REMEDY`), `tools/setup` (`GITIGNORE`, `IGNORE_PROBES`, `GIT`, `PARENTS`, `Setup.main`, `check_ignored`, `check_links`, `_open_dir`, `RefusedError`, `StageFailedError`), `tools/spec_workflow/launcher.py` (`BASES`, `_refusal`, `_trust_refusal`, `status --json`), `tools/cli.toml`, `templates/AGENTS.md`, `tests/test_setup.py` (`fakes()`, `_audit`, `CheckoutGitConfigTests`).

## R1. Where `init` runs: CLI bootstrap plus a declared standard tool

- **Decision**: The global CLI gains an `init` subcommand that only bootstraps. It chooses the ref (R2), fetches that version into the per-machine cache with the existing `ensure_standard`, reads its `tools/cli.toml` as data, refuses unless the version declares `[init] supported = true` and the CLI meets its `[cli] minimum`, then `execv`s `/usr/bin/python3 -IS <standard>/tools/init --project ROOT --ref REF <remaining arguments>`. All inspection, generation, installation and reporting live in the new standard tool `tools/init`. With `BALLAST_STANDARD_DIR`, the CLI runs that checkout's `tools/init`, exactly as it already does for `setup`.
- **Rationale**: D-01 (settled) and ADR-0002: per-version behaviour (ignore block, installed paths, templates) belongs to the standard, and the CLI runs only declared tools from the fetched directory, never from the checkout (BL-INV-002). `init` is the first command that runs before a pin exists, so a new ADR records it (FR-021).
- **Alternatives considered**: all logic in the CLI (duplicates `GITIGNORE`/`IGNORE_PROBES` and templates per version, drifts from the pinned setup); a fixed tool path without a manifest declaration (an older pinned version would be sent a command it lacks, against ADR-0002's "never send a flag it does not know").

## R2. Which ref init pins, and reruns

- **Decision**: Without `ballast.toml`, the ref is `--ref REF` when given, validated by the existing `REF` pattern and `..` rule, else `v{VERSION}` of the running CLI. With `ballast.toml`, the CLI uses `read_pin` and refuses a `--ref` that differs from the pin, naming `ballast preview REF` and a reviewed edit as the way to move it. The download source stays `REPOSITORY`.
- **Rationale**: D-02 and D-10; no extra network lookup; a pin change keeps its existing reviewed path.
- **Alternatives considered**: querying the latest release (moving default, one more call); letting init move a pin (overwrites a project-owned value, against FR-018).

## R3. Compatibility refusals before any write (AC-033, FR-020)

- **Decision**: The CLI refuses with exit 2, before running anything from the standard and before touching the target directory, when: the version's `tools/cli.toml` is missing or has no `[init] supported = true` ("standard REF has no init; pass --ref vX.Y.Z of a release that has it, or upgrade the CLI"); `[cli] minimum` is above the CLI's `VERSION` (names the install line for that minimum); the fetch fails (the existing `ensure_standard` message). Fetching into `$XDG_DATA_HOME` may precede the refusal (PD-0014). `[cli] minimum` is not bumped: other commands keep working with older CLIs, and an older CLI has no `init` subcommand at all.
- **Rationale**: ADR-0002's manifest-as-data pattern; the version that lacks init is only knowable after fetching.
- **Alternatives considered**: probing for `tools/init` existence alone (a file is not a declaration of the contract); bumping `[cli] minimum` (would block unrelated commands on older CLIs).

## R4. One stage order shared by blank and established repositories

- **Decision**: `tools/init` runs these stages in order and stops at the first failure: `check` (arguments, root, git state, symlinked targets), `inspect` (read evidence, R6), `choose` (material choices, R5), `plan` (compute every create, the `.gitignore` change and every proposal in memory, render and validate them), then the first write: `git-init` (only when no repository), `ignore` (R8), `write` (exclusive creates, R9), `patch` (R10), `install` (setup, R11), `verify` and `report` (R12). Everything before `git-init` writes nothing in the target directory, so every refusal of AC-004, AC-033 and FR-020 happens with an untouched target. Blank and established differ only in the evidence found and the questions asked (spec assumption).
- **Rationale**: one design keeps PD-0001's scope condition; all refusals cluster before the first write; `ignore` precedes the other writes so an un-ignored installed path (AC-009) stops before any further tracked file appears, and a rerun completes the rest (AC-030).
- **Alternatives considered**: writing all tracked files first and probing last (leaves more tracked files behind on an AC-009 stop); a transactional rollback of tracked writes (deleting files init created is a destructive step the spec does not ask for, and creates-only writes are already reviewable in `git status`).

## R5. Material choices: flags, terminal prompts, refusal

- **Decision**: Flags `--description TEXT` and `--stack {python,node,rust,go,neutral}`. In a blank repository both are material; each missing one is prompted with `input()` when stdin and stdout are terminals, otherwise init refuses in stage `choose` with exit 2 and names the flag. In an established repository nothing is asked: the description comes from a manifest `description` (`[project] description` in `pyproject.toml`, `description` in `package.json`, `[package] description` in `Cargo.toml`) when present, else it is written as `TO CONFIRM` (PD-0013); the stack comes from evidence (R6), else stack-neutral marked inferred. Ambiguous evidence (several stacks, conflicting lockfiles, several candidate commands) is never asked: it only shapes inactive, inferred suggestions, so it is not material. A description must be one line of 1 to 200 printable characters without a backtick; a stack outside the list is refused.
- **Rationale**: D-05, SC-002 (at most two questions for blank, none for unambiguous established), AC-003/AC-004.
- **Alternatives considered**: prompting for ambiguous evidence (adds questions that change nothing active); `--yes` defaults (would invent a material answer, against AC-004).

## R6. Evidence: a fixed, bounded, link-safe list read as data

- **Decision**: Inspection reads only these paths relative to the root:
  - manifests parsed with `tomllib`/`json`: `pyproject.toml`, `package.json`, `Cargo.toml`; `go.mod` (module line only);
  - lockfiles and package-manager markers by existence only: `uv.lock`, `poetry.lock`, `requirements.txt`, `package-lock.json`, `pnpm-lock.yaml`, `yarn.lock`, `bun.lock`, `bun.lockb`, `Cargo.lock`, `go.sum`;
  - `Makefile`, `makefile`, `GNUmakefile`: target names by a line regex;
  - `.github/workflows/*.yml` and `*.yaml`, at most 20 files: `run:` steps by a line scanner (no YAML library; R7);
  - `AGENTS.md`, `CLAUDE.md`: existence, link target and whether a Ballast section is present (R10);
  - `ARCHITECTURE.md`, `docs/architecture.md`, `docs/ARCHITECTURE.md`, `docs/adr/`, `docs/decisions/`: existence only, cited in `AGENTS.md`;
  - `docs/policies/project/*.md`: names only;
  - the `origin` URL from `git remote get-url origin` with the config-safe prefix (R13).
  Each file is opened through directory descriptors with `O_NOFOLLOW` on every component (the same walk as setup's `_open_dir`), must be a regular file, and is read only up to 256 KiB (`fstat` first); a link, a non-regular file, an oversized file, undecodable UTF-8 or a parse error skips that file with a reported reason (AC-017, AC-025). Stacks: `python` (`pyproject.toml`, `requirements.txt`, `uv.lock` or `poetry.lock`), `node` (`package.json`), `rust` (`Cargo.toml`), `go` (`go.mod`); none recognised falls back to `neutral`, marked inferred (AC-024). Nothing read is executed, shell-interpolated or passed to a subprocess.
- **Rationale**: D-11, FR-005, the security policy's untrusted-content rules; a fixed list is testable and can grow per release.
- **Alternatives considered**: walking the tree (unbounded exposure); a YAML or TOML dependency for CI parsing (breaks the stdlib-only invariant, FR-023).

## R7. Which commands become active checks

- **Decision**: A command is **direct** evidence, and becomes an active `[checks] commands` entry with a `# evidence: PATH:LINE` comment, when it is (a) a CI `run:` command (a single-line `run:` value, or one line of a `run: |` block) whose program is a recognised verifier, or (b) a `package.json` script named `test`, `lint`, `check`, `typecheck` or `format:check`, written as `<pm> run <name>` (`<pm>` from the lockfile: `pnpm`, `yarn`, `bun`, else `npm`). Recognised verifiers: `pytest`, `ruff`, `mypy`, `pyright`, `tox`, `nox`, `uv run`, `uvx`, `python -m pytest|unittest|mypy`, `npm|pnpm|yarn|bun run|test`, `npx eslint|tsc|prettier|vitest|jest`, `eslint`, `tsc`, `prettier --check`, `cargo test|clippy|fmt`, `go test|vet`, `golangci-lint`, `make <target>`. A CI line qualifies only when it is a plain command: it splits with `shlex`, contains no `${{`, `$`, backtick, `;`, `|`, `&`, `<`, `>` or control character, and is at most 200 characters; any other line is ignored. Everything else that suggests a command is **inferred** and written as a commented line marked `inferred`: a `Makefile` target named `test`, `check` or `lint` (`make <target>`), `[tool.pytest.ini_options]` or `[tool.ruff]` in `pyproject.toml` (`pytest`, `ruff check`, prefixed `uv run` when `uv.lock` exists), `Cargo.toml` (`cargo test`), `go.mod` (`go test ./...`), and, for a blank repository, the chosen stack's usual gate. A command found both ways is direct; duplicates are dropped in first-seen order. The matching `[agents.permissions] extra_allow` rules (`Bash(<command>*)`) are always commented and marked inferred; init adds no active permission (FR-012, AC-019).
- **Rationale**: D-06; AC-021/AC-022; nothing widens headless-agent authority without an operator edit. `ballast doctor`'s existing `checks-allowed` check then names the remedy, which the report repeats.
- **Alternatives considered**: executing `--help` or dry runs to confirm commands (forbidden, AC-015); activating `extra_allow` (R2 boundary, rejected in D-06).

## R8. The ignore block: append once, probe, stop on a conflict

- **Decision**: init imports the same version's `tools/setup` as a module (R11) and uses its `GITIGNORE`, `IGNORE_PROBES` and `GIT` as the single source. Stage `ignore`: if every probe already holds (`git check-ignore -q --no-index`, as `check_ignored`), change nothing; else if `.gitignore` is absent, create it with the block; else if the block's exact text is not already in the file, append it (a separating newline first when the file does not end with one) through an `O_APPEND | O_NOFOLLOW` descriptor; `.gitignore` as a link refuses. Then probe again. If a probe still fails, init stops before `write` and `install`, finds the deciding rule with `git check-ignore -v --no-index --non-matching PATH`, writes a patch proposing to comment that line out when it is in a `.gitignore` inside the repository (otherwise the report names the rule's source, such as `.git/info/exclude` or `core.excludesFile`, with no patch), and reports it (AC-009). Project-owned paths init creates are probed too and must not be ignored (AC-013).
- **Rationale**: D-04; FR-007 permits exactly this one change to an existing tracked file; the probe-first rule makes a rerun, and Ballast's own repository, a no-op (AC-028, AC-031).
- **Alternatives considered**: testing the block in a scratch copy before appending (misses nested `.gitignore`, `info/exclude` and global excludes); rewriting the conflicting rule in place (modifies an existing tracked file beyond FR-007).

## R9. Writing only absent files, never through a link

- **Decision**: Every created file is opened with `O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW` relative to a parent descriptor opened component by component with `O_NOFOLLOW`, creating missing directories (reusing setup's `_open_dir(root, parts, create=True)`). `CLAUDE.md` is created as a relative symlink to `AGENTS.md` with `symlinkat`, only when neither file exists (AC-011). An existing target, including a dangling link, is never touched: it is kept and, where init has content for it, becomes a proposal (R10). A parent that is a link refuses in stage `check` for the paths init plans to write, and in setup's `check_links` for installed paths (AC-017). Created files: `ballast.toml`, `.gitignore` (when absent), `.specify/memory/constitution.md`, `AGENTS.md`, `CLAUDE.md`, and `docs/policies/project/testing.md` only when direct check evidence exists (AC-027). Setup then keeps the constitution because it exists (`finish` seeds only an absent one).
- **Rationale**: FR-007; matches setup's link discipline; exclusive creation makes concurrent or repeated runs safe without a lock.
- **Alternatives considered**: write-then-rename (can replace a file created meanwhile); a `CLAUDE.md` file importing `@AGENTS.md` (the repository's own convention and the template text both use a link).

## R10. The init patch

- **Decision**: All proposals for existing files go into one unified diff, `.ballast/init/proposed.patch`, built with `difflib.unified_diff` using `a/` and `b/` prefixes so `git apply` takes it; one hunk group per file in path order. Proposals: (1) a Ballast section for an existing `AGENTS.md` (or for `CLAUDE.md` when it is the only instruction file and not a link), shipped as `templates/init/agents-section.md`, proposed only when the file lacks a link to `docs/policies/spec-kit-workflow.md` (which every Ballast instruction file carries, including this repository's); (2) drift on a rerun (R14) appended to `ballast.toml`; (3) an AC-009 ignore conflict (R8). The patch file is rewritten each run, removed when there is nothing to propose, written only if `git check-ignore` confirms `.ballast/init/proposed.patch` is ignored, and otherwise printed in the report instead of written. `.ballast/init/` is outside the launcher's `BASES` and setup's `INSTALLED`, so it affects neither trust nor installation records.
- **Rationale**: D-04 (one reviewable patch in an ignored location), FR-008, PD-0012 (the preflight never depends on applying it).
- **Alternatives considered**: one patch per file (harder to review as one proposal); a tracked proposal file (a tracked change the operator did not ask for).

## R11. Installing through the existing setup

- **Decision**: `tools/init` sets `sys.dont_write_bytecode` itself, before it loads its sibling `tools/setup` with `importlib` (`SourceFileLoader`) and, through setup, the launcher (F-005), and runs `Setup(root).main()` in process after `write`, catching `RefusedError` and `StageFailedError` to report the stage as `install: <setup's message>`. Setup keeps its lock, recovery, stage, validation, switch and ignore and link checks unchanged (FR-014, AC-020); its existing "nothing changed" path makes a rerun a no-op. Tests reuse `tests/test_setup.py`'s `fakes()` by patching the module object init loaded.
- **Rationale**: one owner for installation (ADR-0007); in-process exceptions carry the stage without parsing output; the same module provides `GITIGNORE`, `IGNORE_PROBES`, `GIT`, `PARENTS` and `_open_dir`, so init adds no second source of truth.
- **Alternatives considered**: a `tools/setup` subprocess (works, but stage reporting would parse stderr, and tests could not reuse the in-process fakes); the CLI running setup after init (init could not verify and report afterwards).

## R12. Verification and the readiness report

- **Decision**: After `install`, init checks and reports, each as `ready`, `warning` or `not-ready` with a detail:
  - `instructions`: the instruction entry point exists; `CLAUDE.md` resolves to `AGENTS.md` when init created it; every relative Markdown link in the file init created (or the existing file's Ballast section) resolves inside the root after installation; an existing file without a Ballast section is a `warning` naming the patch;
  - `ignored-paths`: every `IGNORE_PROBES` entry holds and no project-owned file init created is ignored;
  - `pinned-version`: `ballast.toml`'s ref equals the running version's ref and setup's `status` is `current`;
  - `trust-boundary`: init wrote no baseline, and the launcher's `_refusal(root)` (imported, as setup does) returns the no-baseline or changed-inputs refusal; an existing baseline that still matches is `ready` with next action `ballast run`;
  - `checks`: each active command's program (first word) is found with `shutil.which` on the operator's `PATH`, or as an existing relative path in the root, without running it; a missing program is a `warning`, as is an uncovered `extra_allow` (doctor's `checks-allowed` remedy).
  The report then lists what was written and kept, the patch, the inferred values to confirm, the optional integrations not written (`templates/github/` files, stack CI) with how to add them (AC-012, FR-017), the protected inputs to review (`ballast.toml`, `.specify/`, `.ballast/spec_workflow/`), and `Next: review the files above, then run \`ballast trust\``. A failure or refusal reports `stopped at <stage>`, the written paths, the planned paths not written, and how to continue (AC-034). All report text passes through setup's `printable`. Exit codes: 0 when nothing is `not-ready`, 1 on a failed stage or a `not-ready` check, 2 on a refusal.
- **Rationale**: FR-019 and AC-032; every check reuses the owner's code (setup, launcher) instead of recomputing it.
- **Alternatives considered**: running `ballast doctor` in process (doctor lives in the CLI, not the standard, and checks machine prerequisites outside init's scope); a `--json` report (no consumer yet; can follow).

## R13. Git: config-safe calls, `git init` only when absent, root required

- **Decision**: Every git call uses setup's `GIT` prefix (`--no-pager`, `core.fsmonitor=false`, `core.hooksPath=/dev/null`) with stdin closed (AC-016). Stage `check` runs `git rev-parse --show-toplevel`: an error means no repository, and `git init --template=` (empty template, so no hook samples are copied) runs in stage `git-init`; a toplevel equal to the root means a repository; a different toplevel refuses ("inside the repository at X; run `ballast init` at its root"). The `origin` URL is parsed for `github.com` in HTTPS (`https://github.com/OWNER/REPO(.git)`) and SSH (`git@github.com:OWNER/REPO(.git)`, `ssh://git@github.com/OWNER/REPO(.git)`) forms, `OWNER/REPO` validated against `[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+`; otherwise `[github]` is omitted and the report says how to add it (AC-026). No commit, push, remote or `gh` call exists in the tool (AC-018).
- **Rationale**: FR-006, FR-013, FR-016, D-09, D-12.
- **Alternatives considered**: `git init` in a subdirectory of another repository (creates a nested repository the operator did not ask for).

## R14. Reruns and drift

- **Decision**: With `ballast.toml` present, init keeps the pin and every existing project-owned file, runs the same stages, creates only what is absent (AC-029, AC-030), reruns setup (a no-op when current) and reports. Drift is computed between the fresh profile and the committed `ballast.toml`: when `[checks]` or `[github]` is absent and evidence supplies it, the patch appends the active table with evidence comments; when the table exists, differing evidence is appended as commented lines `# ballast init found: "CMD" (evidence: PATH:LINE)`. A rerun on an adopted repository therefore changes no tracked file and reproduces the same report (AC-028); Ballast's own repository is a test fixture (AC-031).
- **Rationale**: D-10; appending to the end of a TOML file is the only edit that cannot break existing tables, and it stays a proposal.
- **Alternatives considered**: regenerating `ballast.toml` (overwrites project-owned config); rewriting arrays in place (fragile TOML text editing).

## R15. Generated content and templates

- **Decision**: New generic templates under `templates/init/`: `constitution.md` (stack-neutral project constitution with the product description, stack and check gates as placeholders and generic principles: project-owned files, specs govern, executable evidence, no secrets in tracked files, generic Ballast invariants), `agents-section.md` (the Ballast section proposed for an existing instruction file) and `testing.md` (project testing addendum listing the detected gates with evidence). `AGENTS.md` for a blank or instruction-less repository is rendered from the existing `templates/AGENTS.md`: init drops the "This file is a starting point" paragraph and replaces each `[UPPERCASE]` placeholder from a fixed table with evidence (cited) or `TO CONFIRM: <what>`; a test asserts the table covers every placeholder in the template, so the copy-once template stays the single source. Placeholders are `{{name}}` in the new templates and filled by plain replacement; values are single-line, control characters escaped, backticks refused. `ballast.toml` is rendered by code, TOML strings escaped, and parsed back with `tomllib` and checked with the launcher's `pinned_ref` before writing. No shipped template names a project (FR-022).
- **Rationale**: D-07; principle 7 (generic by default); one source per artifact.
- **Alternatives considered**: a second `AGENTS.md` template for init (two copies drift); keeping Spec Kit's placeholder constitution (misses the main outcome).

## R16. Documentation and the ADR

- **Decision**: New `docs/adr/0012-init-before-pin.md` (proposed until the PR merges): `init` is the only CLI command that runs before a pin; the CLI bootstraps a version that declares `[init] supported = true` in `tools/cli.toml` and runs that version's `tools/init` from the fetched directory; the standard owns inspection, generation and installation; init never records trust, commits or pushes. Update `README.md` (adoption with `ballast init` first, the manual steps kept as the fallback), `specs/TECHNICAL-SPEC.md` (the CLI command list and the manifest's `[init]`), the CLI's usage, docstring and `PIN_REMEDY`/missing-pin message (name `ballast init`), and the layout line of `AGENTS.md` (`templates/init/`).
- **Rationale**: FR-021; documentation policy for public CLI behaviour.
- **Alternatives considered**: amending ADR-0002 in place (an accepted ADR is superseded or extended by a new one, not edited).

## R17. Test strategy

- **Decision**: New `tests/test_init.py`, offline, running `tools/init` in process against scratch directories with `tests/test_setup.py`'s `fakes()` patched onto the setup module init loaded, plus a subprocess audit hook (as `_audit`) proving the only programs started are `git` (AC-015). Fixtures: blank directory; directory with only `.git`; Python repository (`pyproject.toml`, CI running `pytest`, `Makefile` with `check`, existing `AGENTS.md`, `docs/policies/project/security.md`); un-ignoring `.gitignore`; malformed and oversized manifests; symlinked `.github` and symlinked `docs/policies` parent; git config with hooks, pager and fsmonitor that write a marker; GitHub and non-GitHub origins; existing `ballast.toml` (adopted and partial); a copy of Ballast's own tracked files. `tests/test_ballast.py` gains CLI bootstrap tests (default ref, `--ref` validation, pin conflict, missing `[init]`, minimum too high, refusal leaves the target untouched, `execv` arguments). After each successful fixture, `launcher._trust` then `launcher._refusal` returning `None` proves the post-trust preflight (AC-002, AC-010). One networked end-to-end scratch run (blank and established) is recorded in the PR (testing policy for `tools/setup`/`tools/ballast` changes).
- **Rationale**: constitution principle 8; reuses the existing fakes instead of a parallel stub.
- **Alternatives considered**: a stub `tools/setup` in a fake standard (a second implementation of setup's contract to keep in sync).
