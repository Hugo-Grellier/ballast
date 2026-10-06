<!-- ballast-discovery: input evidence -->
# Discovery brief: Adapt Ballast to blank and established repositories

This brief is input evidence for [spec.md](spec.md). It is not the feature's
authority: once intent is recorded, [spec.md](spec.md) and [intent.md](intent.md)
govern, and later steps do not read requirements from this file.

**Mode**: autonomous
**Issue**: #13 (snapshot `.specify/workflow-state/issues/13.md`, untrusted requirements data)

## Sources

- S-1: Issue #13 body
- S-2: Issue #13 intake scope comment
- S-3: AGENTS.md
- S-4: .specify/memory/constitution.md
- S-5: docs/plans/2026-10-02-product-roadmap.md#priority-1--one-command-adoption-updates-and-worktrees
- S-6: specs/TECHNICAL-SPEC.md#91-v10-target
- S-7: specs/PRODUCT-SPEC.md#57-greenfield-bootstrap
- S-8: docs/adr/0001-cli-release-asset-install.md
- S-9: docs/adr/0002-cli-standard-manifest.md
- S-10: docs/adr/0007-recoverable-installation.md
- S-11: docs/adr/0011-worktree-preparation.md
- S-12: docs/policies/project/workflow.md
- S-13: docs/policies/project/testing.md
- S-14: docs/policies/security.md
- S-15: README.md#installing-the-spec-kit-workflow
- S-16: README.md#using-the-copy-once-templates
- S-17: tools/ballast
- S-18: tools/setup
- S-19: tools/cli.toml
- S-20: tools/spec_workflow/launcher.py
- S-21: templates/AGENTS.md
- S-22: templates/github/pull_request_template.md
- S-23: specs/13-adaptive-init/autonomous/record.md
- S-24: docs/adr/0003-launcher-github-authority.md
- unavailable: Issue #13 comments — the snapshot records none
- unavailable: Issue #55 — referenced by the intake scope comment; not read, GitHub is outside this step's sources

## Need

- **User**: an operator adopting Ballast in a repository that does not use it yet, either an empty directory or repository, or an established codebase with its own instructions and CI. [S: Issue #13 body] [S: docs/plans/2026-10-02-product-roadmap.md#priority-1--one-command-adoption-updates-and-worktrees]
- **Job to be done**: make the repository usable by the Ballast workflow with one `ballast init`, without hand-writing the pin, ignore block, constitution, policy addenda or agent instructions. [S: Issue #13 body]
- **Current pain**: there is no first-run `init`; the operator must create `ballast.toml`, copy the ignore block that setup prints after refusing, adapt the copy-once templates by hand, run setup, then review and trust, and learns the order from errors. [S: docs/plans/2026-10-02-product-roadmap.md] [S: README.md#installing-the-spec-kit-workflow] [S: tools/setup]
- **Intended outcome**: one invocation inspects the repository without executing its commands, writes a minimal evidence-based profile and safe tracked files, installs the ignored standard files through setup, and ends with a readiness report and the exact next action. [S: Issue #13 intake scope comment] [S: docs/plans/2026-10-02-product-roadmap.md]

## Examples

- In an empty directory, `ballast init` asks for a short product description and a stack or a stack-neutral start, runs `git init`, writes `ballast.toml`, `.gitignore`, a constitution, `AGENTS.md` and its `CLAUDE.md` link, installs the standard and reports `ballast trust` as the next command. [S: docs/plans/2026-10-02-product-roadmap.md] [P: D-05] [P: D-07]
- In a Python repository with `pyproject.toml`, a `.github/workflows/ci.yml` running `pytest` and an existing `AGENTS.md`, init leaves `AGENTS.md` and the CI file untouched, proposes `pytest` as a check command from the CI evidence and writes the Ballast addition to `AGENTS.md` as a reviewable patch. [S: IAC-2] [P: D-04] [P: D-06]
- A command inferred only from a file name, such as a `Makefile` with an unlabelled `check` target, appears in `ballast.toml` as an inactive, commented line marked as inferred. [S: IAC-3] [P: D-06]
- Running init a second time on the repository it just adopted changes no tracked file and reports the same readiness. [S: IAC-3] [P: D-10]

## Scope

- Detect whether the target is empty or established and inspect only relevant files: manifests, package managers, test, lint and build commands, CI, architecture docs, existing `AGENTS.md`/`CLAUDE.md` and project policies. [S: Issue #13 body] [S: docs/plans/2026-10-02-product-roadmap.md]
- Initialize Git in an empty directory. [S: docs/plans/2026-10-02-product-roadmap.md]
- Generate `ballast.toml`, the ignore block, the project constitution, project policy addenda and a concise agent-instruction entry point. [S: docs/plans/2026-10-02-product-roadmap.md] [P: D-07]
- Install the ignored standard files by reusing setup (#14, #15). [S: Issue #13 intake scope comment]
- Verify adoption and report readiness: instructions resolve, ignored paths are correct, the pinned version is available, the trust boundary is intact, chosen check commands exist, and the next action. [S: docs/plans/2026-10-02-product-roadmap.md]
- Present the generated protected inputs for review and name `ballast trust` as the operator's next action. [S: Issue #13 intake scope comment] [S: docs/plans/2026-10-02-product-roadmap.md]

## Non-goals

- Generating an application. [S: Issue #13 body]
- Overwriting existing project policy. [S: Issue #13 body]
- Executing detected build, test or lint commands during inspection. [S: Issue #13 body]
- Installing every optional integration, including stack CI by default. [S: Issue #13 body] [S: docs/plans/2026-10-02-product-roadmap.md]
- Recording trust on the operator's behalf (#55). [S: Issue #13 intake scope comment]
- Committing, pushing or creating a remote repository. [P: D-09]
- Changing the CLI distribution path, which #12 delivered. [S: docs/adr/0001-cli-release-asset-install.md]

## Constraints

- A project commits only `ballast.toml`, its constitution, `docs/policies/project/` and adopted copy-once files; everything setup installs is ignored and rebuildable (BL-INV-001). [S: .specify/memory/constitution.md]
- Nothing executes from a writable checkout before trust; `ballast` runs only the pinned, fetched standard's tools (BL-INV-002). [S: .specify/memory/constitution.md] [S: tools/ballast]
- A project picks a version, never a source; the repository `ballast` downloads from stays fixed (BL-INV-004). [S: .specify/memory/constitution.md]
- Workflow tools stay standard-library-only and run under `python3 -I -S`. [S: AGENTS.md]
- Shipped templates carry no project's names or domain rules. [S: .specify/memory/constitution.md]
- The CLI reads a standard version's `tools/cli.toml` as data and runs only what it declares, from the fetched standard directory. [S: docs/adr/0002-cli-standard-manifest.md] [S: tools/cli.toml]
- Setup stages, validates and switches an installation, refuses unignored installed paths, and creates the constitution only when absent. [S: docs/adr/0007-recoverable-installation.md] [S: tools/setup]
- Every git call setup makes disables hooks, pager and fsmonitor, because repository config can run programs before trust. [S: tools/setup]
- Risk is R2: init generates protected inputs, writes the ignore block and setup-installed paths, and touches the launcher's trust model. [S: docs/policies/project/workflow.md] [S: specs/13-adaptive-init/autonomous/record.md]
- A change to `tools/setup` or `tools/ballast` needs an end-to-end run on a scratch project. [S: docs/policies/project/testing.md]

## Permissions and data authority

- Existing tracked instructions, CI and project policy are the project's authority; init never overwrites them and proposes changes as a reviewable patch. [S: IAC-2] [P: D-04]
- `ballast.toml`, `.ballast/` and `.specify/` are protected inputs; the operator reviews them and records trust with `ballast trust`, which init never runs. [S: IAC-4] [S: tools/spec_workflow/launcher.py]
- Generated config takes effect for agents only after that operator trust. [S: tools/spec_workflow/launcher.py]
- Init adds no headless-agent permission rule on its own. [P: D-06]
- File contents read during inspection are untrusted data: paths stay within the repository root, symbolic links are not followed out of it, and no value is interpolated into a shell. [S: docs/policies/security.md]

## Success evidence

- Scratch-project tests: a blank directory and an established repository with existing `AGENTS.md` and CI each reach a state where, after the reported `ballast trust`, the launcher preflight passes. [S: IAC-1] [S: docs/policies/project/testing.md]
- Tests show existing tracked instructions, CI and policy files are byte-identical after init, and a conflict produces a patch and no partial write. [S: IAC-2]
- Tests run init twice and show the second run changes nothing tracked; generated values cite their evidence and uncertain ones are marked. [S: IAC-3]
- Tests show the installed paths are ignored, project-owned files are tracked, and no trust baseline exists after init. [S: IAC-4]
- Tests show inspection executes no detected project command. [S: Issue #13 body]
- The fast gate, the full local gate and the end-to-end scratch run are recorded in the PR. [S: AGENTS.md] [S: docs/policies/project/testing.md]

## Edge, failure and permission cases

- The directory is not a Git repository, or is empty except for a `.git`. [S: docs/plans/2026-10-02-product-roadmap.md]
- `ballast.toml` already exists: the repository is already adopted, or partially adopted. [P: D-10]
- `.gitignore` has a rule that un-ignores an installed path, so the ignore probes still fail after the block is added. [S: tools/setup] [P: D-04]
- Setup fails during the download or the switch; the prior state stays and the report names the failed stage. [S: docs/adr/0007-recoverable-installation.md]
- No terminal is attached and a material choice is missing. [P: D-05]
- An installed path's parent, or a target file, is a symbolic link. [S: tools/setup]
- A repository's git config sets hooks or an fsmonitor that would run during inspection. [S: tools/setup]
- A manifest or CI file is malformed or very large. [S: docs/policies/security.md] [I]
- The origin remote is not on GitHub, or there is none. [P: D-12]
- The CLI is older than the standard it would pin, or the pinned version has no `init`. [S: docs/adr/0002-cli-standard-manifest.md] [I]
- Ballast's own repository, which dogfoods the standard, is an established repository init must not damage. [S: AGENTS.md] [I]

## Issue acceptance criteria

- IAC-1: A blank directory/repository and an established repository each reach a valid workflow preflight through one init invocation with only material choices requested.
- IAC-2: Existing tracked instructions, CI and project policy are preserved; conflicts yield a reviewable patch and no partial overwrite.
- IAC-3: Rerunning init is idempotent; generated config and verification commands reflect detected evidence, with uncertain inference marked.
- IAC-4: The resulting installed paths are ignored and project-owned files remain tracked; trust is never silently granted by setup.

## Known

- `ballast` dispatches every command except `doctor`, `preview`, `self-install` and `--version` through the pin in `ballast.toml`, and fails without one. [S: tools/ballast]
- `ballast setup` runs the fetched standard's `tools/setup`, which refuses until the project ignores the installed paths and prints the block to add. [S: tools/ballast] [S: tools/setup]
- Setup seeds `.specify/memory/constitution.md` from Spec Kit's template only when the file is absent, and never on a worktree preparation. [S: tools/setup]
- The ignore block and the installed paths are owned by each standard version's `tools/setup`. [S: tools/setup]
- `ballast trust` records the current protected inputs as the baseline; the launcher refuses until it matches. [S: tools/spec_workflow/launcher.py]
- `templates/AGENTS.md` and `templates/github/` are copy-once templates the operator adapts by hand today. [S: README.md#using-the-copy-once-templates] [S: templates/AGENTS.md]
- The CLI is installed from a checksummed release asset and carries its own version (#12, the declared blocker, is merged). [S: docs/adr/0001-cli-release-asset-install.md] [S: tools/ballast]
- `ballast doctor` already checks tools, pin, setup freshness, trust readiness and whether `[checks]` commands are allowed for agents. [S: tools/ballast]
- The v1.0 target requires both blank and established repositories. [S: specs/TECHNICAL-SPEC.md#91-v10-target]
- A greenfield bootstrap must generate the essential safeguards immediately. [S: specs/PRODUCT-SPEC.md#57-greenfield-bootstrap]
- Init's inspection and generation run from the fetched standard version, with the CLI only bootstrapping it. [S: docs/adr/0002-cli-standard-manifest.md]
- Init never records trust; it lists the protected inputs to review and ends with `ballast trust`. [S: Issue #13 intake scope comment] [S: IAC-4]

## Inferred

- The blank and established paths share one design: inspect, propose a profile, write absent files, reuse setup, verify, report; they differ only in the evidence found and the questions asked. [I]
- "Reach a valid workflow preflight through one init invocation" means that after init and the single reported `ballast trust`, the preflight passes with no further edit. [I]
- The plan needs a CLI change (to run `init` before a pin exists) and a new standard tool declared in `tools/cli.toml`, so a new ADR extends ADR-0002. [I]
- The pin defaults to the CLI's own release version, with an explicit override. [P: D-02]
- Conflicting changes go to a patch under ignored `.ballast/`; absent files are created; `.gitignore` gets the block appended when absent. [P: D-04]
- Material choices are prompted on a terminal, available as flags, and missing ones refuse without a terminal. [P: D-05]
- Check commands with direct evidence become `[checks]` entries; inferred ones and `extra_allow` suggestions stay commented. [P: D-06]
- The constitution and `AGENTS.md` come from generic templates filled from evidence, with remaining unknowns marked. [P: D-07]
- GitHub templates and stack CI are proposed in the report, not written. [P: D-08]
- Init never commits or pushes. [P: D-09]
- A rerun keeps the pin and every project-owned file and reports drift as a patch. [P: D-10]
- Detection reads a fixed list of evidence files and never executes them. [P: D-11]
- `[github] repository` comes from a GitHub origin remote, otherwise it is omitted and reported. [P: D-12]

## Undecided

None.

## Decisions

### D-01: Where init's inspection and generation run
- **Status**: settled
- **Question**: Does the global CLI contain init's logic, or does the CLI bootstrap a pinned standard version whose own tool inspects and generates?
- **Why it matters**: decides whether init's templates and ignore block follow the pinned version and how the CLI and standard versions stay compatible.
- **Sources**: [S: docs/adr/0002-cli-standard-manifest.md] [S: .specify/memory/constitution.md] [S: tools/setup]
- **Options**:
  - A — The CLI fetches the chosen version and runs its declared init tool from the fetched directory. Consequence: generated files match the version setup will install; a new manifest declaration and ADR extend ADR-0002.
  - B — All logic lives in the CLI. Consequence: the CLI duplicates per-version knowledge (ignore block, templates) and drifts from the pinned setup.
- **Recommended default**: A, because ADR-0002 places per-version behavior in the standard.
- **Answer**:
- **Resolution**: A. ADR-0002 keeps per-version behavior in the standard and has the CLI run only declared tools from the fetched directory [S: docs/adr/0002-cli-standard-manifest.md]; the ignore block and installed paths belong to each version's setup [S: tools/setup]; nothing runs from the checkout (BL-INV-002) [S: .specify/memory/constitution.md].

### D-02: Which version init pins
- **Status**: assumed
- **Question**: In a repository without `ballast.toml`, which standard ref does init write?
- **Why it matters**: decides what init downloads first and whether init needs a network lookup for the latest release.
- **Sources**: [S: tools/ballast] [S: docs/adr/0001-cli-release-asset-install.md] [S: .specify/memory/constitution.md]
- **Options**:
  - A — The CLI's own release tag `v<VERSION>`, overridable with an explicit ref. Consequence: no extra network lookup; the pin matches the CLI the operator installed.
  - B — Query the latest release. Consequence: one more network call and a moving default.
- **Recommended default**: A, because the CLI already carries its reviewed version and the fixed source does not change.
- **Answer**:
- **Resolution**: A. Safe and reversible: the ref passes the existing ref validation, the download source stays fixed (BL-INV-004), and the pin is a tracked file the operator reviews and can change before trust.

### D-03: Initial trust in the init experience
- **Status**: settled
- **Question**: Does init record the trust baseline after showing the protected inputs, or stop before trust with the exact next command?
- **Why it matters**: decides whether init touches the launcher's trust baseline, an R2 boundary.
- **Sources**: [S: Issue #13 intake scope comment] [S: IAC-4] [S: docs/plans/2026-10-02-product-roadmap.md] [S: .specify/memory/constitution.md]
- **Options**:
  - A — Init lists the generated protected inputs to review and ends with `ballast trust` as the next action. Consequence: trust stays a separate operator act; the preflight passes after it.
  - B — Init asks for confirmation and records trust itself. Consequence: setup-side code writes the baseline, against the intake scope.
- **Recommended default**: A, because the intake scope excludes recording trust for the operator.
- **Answer**:
- **Resolution**: A. The intake scope puts "recording trust on the operator's behalf (#55)" out of scope [S: Issue #13 intake scope comment]; IAC-4 forbids silent trust [S: IAC-4]; the roadmap consolidates review and the trust action into the experience "while preserving the rule that setup cannot silently trust itself" [S: docs/plans/2026-10-02-product-roadmap.md].

### D-04: Conflict handling and the reviewable patch
- **Status**: assumed
- **Question**: What does init write when a target file already exists, and where does the patch go?
- **Why it matters**: decides IAC-2's evidence and whether init can leave a repository half-adopted.
- **Sources**: [S: IAC-2] [S: docs/plans/2026-10-02-product-roadmap.md] [S: tools/setup]
- **Options**:
  - A — Create only absent files (exclusive create, no link followed); never modify an existing tracked file except appending the Ballast ignore block to `.gitignore` when it is absent; write every other proposed change as one patch under ignored `.ballast/init/` and stop before setup when the ignore probes still fail. Consequence: no partial overwrite; the operator applies the patch and reruns.
  - B — All-or-nothing: on any conflict write nothing and emit the whole change as a patch. Consequence: a repository with one existing `AGENTS.md` gets no adoption at all.
- **Recommended default**: A, because the roadmap asks init to apply safe changes and offer a patch for conflicts.
- **Answer**:
- **Resolution**: A. Safe and reversible: existing instructions, CI and policy stay byte-identical, every write is a tracked change visible in `git diff` or an ignored patch, and setup's ignore check still refuses an incorrect `.gitignore`.

### D-05: How material choices are asked
- **Status**: assumed
- **Question**: How does init request the material choices (product description, stack or stack-neutral, ambiguous evidence)?
- **Why it matters**: decides IAC-1's "only material choices requested" and how scripts and tests run init.
- **Sources**: [S: IAC-1] [S: docs/plans/2026-10-02-product-roadmap.md]
- **Options**:
  - A — Prompt on a terminal; each choice also has a flag; without a terminal, a missing choice refuses with the flag to pass. Consequence: tests and scripts are deterministic; nothing material is silently defaulted.
  - B — Prompt only. Consequence: not scriptable or testable without a pty.
- **Recommended default**: A, because it is testable and never invents a material answer.
- **Answer**:
- **Resolution**: A. Safe and reversible: a command-line interface choice that adds no authority and can gain options later.

### D-06: Detected verification commands and agent permissions
- **Status**: assumed
- **Question**: Which detected commands does init write to `[checks]`, and does it add `[agents.permissions] extra_allow` rules?
- **Why it matters**: decides IAC-3's marking of uncertain inference and whether init widens what headless agents may run.
- **Sources**: [S: IAC-3] [S: README.md#installing-the-spec-kit-workflow] [S: tools/ballast] [S: docs/policies/project/workflow.md]
- **Options**:
  - A — Commands with direct evidence (a CI step, a named manifest script) become active `[checks]` entries with their source in a comment; inferred ones and the matching `extra_allow` rules are written as commented lines marked inferred; doctor's `checks-allowed` names the remedy. Consequence: no permission is widened without an operator edit.
  - B — Also write active `extra_allow` rules for every check. Consequence: init widens the headless-agent permission model, an R2 boundary.
- **Recommended default**: A, because it adds no agent authority.
- **Answer**:
- **Resolution**: A. Safe and reversible: nothing is executed during inspection, `[checks]` runs only after the operator reviews and trusts `ballast.toml`, and uncommenting a line is all it takes to widen permissions deliberately.

### D-07: Content of the generated constitution, addenda and agent instructions
- **Status**: assumed
- **Question**: What does init write for the constitution, `docs/policies/project/` and `AGENTS.md` when they are absent?
- **Why it matters**: decides whether a blank repository is usable without hand-editing and what new templates the standard ships.
- **Sources**: [S: docs/plans/2026-10-02-product-roadmap.md] [S: templates/AGENTS.md] [S: tools/setup] [S: .specify/memory/constitution.md]
- **Options**:
  - A — Fill generic templates (a new stack-neutral constitution template and `templates/AGENTS.md`) from the answers and detected evidence, mark every unknown as inferred or to-confirm, link `CLAUDE.md` to `AGENTS.md` only when neither exists, and write a policy addendum only where evidence supports it, such as the detected gates in `docs/policies/project/testing.md`. Consequence: small, reviewable files; unknowns stay visible.
  - B — Keep Spec Kit's placeholder constitution and copy templates unchanged. Consequence: the operator still writes the constitution and instructions by hand, missing the main outcome.
- **Recommended default**: A, because it meets the main outcome with generic shipped content.
- **Answer**:
- **Resolution**: A. Safe and reversible: the files are only created when absent, carry no project's domain rules in the shipped templates, and are tracked changes the operator reviews and edits.

### D-08: Optional integrations
- **Status**: assumed
- **Question**: Does init write the GitHub copy-once files (PR template, Dependabot, PR-title workflow) or stack CI?
- **Why it matters**: decides what tracked files appear in an established repository's CI.
- **Sources**: [S: Issue #13 body] [S: docs/plans/2026-10-02-product-roadmap.md] [S: templates/github/pull_request_template.md]
- **Options**:
  - A — Do not write them; list the relevant ones in the readiness report with how to add them. Consequence: no CI change by default.
  - B — Write each absent one. Consequence: new CI behavior in an established repository without a request.
- **Recommended default**: A, because the roadmap says propose and the Issue excludes installing every optional integration.
- **Answer**:
- **Resolution**: A. Safe and reversible: writes nothing; a flag to add them can follow.

### D-09: Commits and remotes
- **Status**: assumed
- **Question**: Does init commit its changes, push, or create a GitHub repository?
- **Why it matters**: decides whether init performs externally visible or history-changing actions.
- **Sources**: [S: AGENTS.md] [S: docs/plans/2026-10-02-product-roadmap.md]
- **Options**:
  - A — Never commit, push or create a remote; run `git init` only when there is no repository. Consequence: the operator reviews and commits.
  - B — Commit the generated files. Consequence: unreviewed protected inputs land in history.
- **Recommended default**: A, because external and history actions need human approval.
- **Answer**:
- **Resolution**: A. Safe and reversible: the most conservative option; a commit option can be added later.

### D-10: Rerun on an adopted repository
- **Status**: assumed
- **Question**: What does init do when `ballast.toml` already exists?
- **Why it matters**: decides IAC-3's idempotence and whether init can move a pin.
- **Sources**: [S: IAC-3] [S: README.md#installing-the-spec-kit-workflow]
- **Options**:
  - A — Keep the pin and every existing project-owned file, create only what is absent, rerun setup (a no-op at a current pin), verify, and report differences between new evidence and committed config as a patch. Consequence: idempotent; pin changes stay with `ballast preview` and a reviewed edit.
  - B — Regenerate the profile. Consequence: overwrites project-owned files.
- **Recommended default**: A, because pin updates already have their own reviewed path.
- **Answer**:
- **Resolution**: A. Safe and reversible: it writes nothing that exists and reuses the existing update path.

### D-11: Detection evidence
- **Status**: assumed
- **Question**: Which files does inspection read, and how are unknown stacks handled?
- **Why it matters**: decides what "detected evidence" means for IAC-3 and the inspection's exposure to untrusted content.
- **Sources**: [S: docs/plans/2026-10-02-product-roadmap.md] [S: docs/policies/security.md] [S: Issue #13 body]
- **Options**:
  - A — A fixed list read as data with a size bound and no link followed out of the root: common manifests and lockfiles, `Makefile`, `.github/workflows/*`, `AGENTS.md`, `CLAUDE.md`, ADR and architecture docs, `docs/policies/project/`; an unknown stack falls back to stack-neutral with the inference marked. Consequence: bounded, testable detection that can grow per release.
  - B — Walk the whole tree. Consequence: slower, larger exposure to untrusted content.
- **Recommended default**: A, because it is bounded and testable.
- **Answer**:
- **Resolution**: A. Safe and reversible: it executes nothing and only affects suggestions the operator reviews; the list can grow later.

### D-12: GitHub repository setting
- **Status**: assumed
- **Question**: How does init fill `[github] repository`?
- **Why it matters**: decides whether intake and Draft PR publication work right after adoption.
- **Sources**: [S: tools/ballast] [S: docs/adr/0003-launcher-github-authority.md]
- **Options**:
  - A — Derive `OWNER/REPO` from a GitHub `origin` remote read with config-safe git; otherwise omit it and report how to add it. Consequence: no guess for non-GitHub or missing remotes.
  - B — Always ask. Consequence: one more question when the evidence already answers it.
- **Recommended default**: A, because it asks only when evidence is missing.
- **Answer**:
- **Resolution**: A. Safe and reversible: the value is a reviewed line in `ballast.toml` and grants no authority by itself; the launcher still holds GitHub authority.

## Question metrics

- **Rounds**: 0
- **Questions asked**: 0
- **Assumptions adopted**: 10
