# Feature Specification: Adapt Ballast to blank and established repositories

**Feature Branch**: `feat/13-adaptive-init`

**Created**: 2026-10-06

**Status**: Draft

**Input**: Issue #13: `ballast init` makes a repository usable without manually writing its pin, ignore block, constitution, policy addenda or agent instructions. Written from the discovery brief [discovery.md](discovery.md); the brief stays input evidence and this spec is the authority.

**Risk**: R2 (generates protected inputs, writes the ignore block and setup-installed paths, and touches the launcher's trust model). In this Autonomous run every intermediate decision is agent-provisional; merging the PR is the single human decision.

## User Scenarios & Testing *(mandatory)*

An operator adopting Ballast today must create `ballast.toml` by hand, copy the ignore block that setup prints after refusing, adapt the copy-once templates, run setup, then review and trust, learning the order from errors. This feature gives them one `ballast init` that inspects the repository without executing anything from it, writes a minimal evidence-based profile and the safe tracked files, installs the ignored standard files through the existing setup, and ends with a readiness report naming `ballast trust` as the operator's next action. Blank and established repositories follow the same path; they differ only in the evidence found and the questions asked.

### User Story 1 - A blank directory becomes a Ballast project in one command (Priority: P1)

In an empty directory, the operator runs `ballast init`. It asks for a short product description and a stack (or a stack-neutral start), initializes Git, writes the pin, the ignore block, a constitution, the agent instructions and their `CLAUDE.md` link, installs the standard, and reports `ballast trust` as the next command. After that one trust, the workflow preflight passes.

**Why this priority**: It is the Issue's main outcome for the greenfield case, and the product spec requires a greenfield bootstrap to generate the essential safeguards immediately.

**Independent Test**: In a scratch empty directory, run `ballast init` with the product description and stack supplied as flags, then `ballast trust`; the launcher preflight passes with no further edit.

**Acceptance Scenarios**:

1. **AC-001**: **Given** an empty directory, **When** the operator runs `ballast init` and answers the material choices, **Then** the directory becomes a Git repository with `ballast.toml`, a `.gitignore` containing the Ballast ignore block, a constitution, `AGENTS.md` and a `CLAUDE.md` link to it, and the standard is installed. [S: IAC-1] [S: docs/plans/2026-10-02-product-roadmap.md] [P: D-05] [P: D-07]
2. **AC-002**: **Given** a blank directory or a repository containing only `.git`, **When** init finishes and the operator runs the reported `ballast trust`, **Then** the workflow preflight passes with no further edit. [S: IAC-1] [I]
3. **AC-003**: **Given** a blank directory, **When** init runs, **Then** the only questions are the material choices (product description; a stack or a stack-neutral start), and each can also be given as a flag. [S: IAC-1] [P: D-05]
4. **AC-004**: **Given** no terminal is attached and a material choice is missing, **When** init runs, **Then** it refuses before writing anything and names the flag that supplies the choice; it never invents a material answer. [S: IAC-1] [P: D-05]
5. **AC-005**: **Given** the operator does not pass a version, **When** init writes `ballast.toml`, **Then** the pin is the CLI's own release version; an explicit version passes the existing version validation and the download source stays fixed. [S: IAC-1] [P: D-02] [S: .specify/memory/constitution.md]

---

### User Story 2 - An established repository keeps its own instructions, CI and policy (Priority: P1)

The operator runs `ballast init` in an existing codebase with its own `AGENTS.md`, CI and project policies. Init leaves every existing tracked file byte-identical, creates only what is absent, and writes the Ballast additions it could not apply safely as one reviewable patch. After the operator's trust, the preflight passes.

**Why this priority**: The v1.0 target requires established repositories, and damaging a project's own instructions or CI would make adoption unsafe.

**Independent Test**: In a scratch repository with `pyproject.toml`, `.github/workflows/ci.yml` running `pytest` and an existing `AGENTS.md`, run init then `ballast trust`; the existing files are byte-identical, a patch holds the proposed `AGENTS.md` addition, and the preflight passes.

**Acceptance Scenarios**:

1. **AC-006**: **Given** an established repository with existing agent instructions, CI and project policy, **When** init runs, **Then** each of those files is byte-identical afterwards. [S: IAC-2] [P: D-04]
2. **AC-007**: **Given** a proposed change to a file that already exists, **When** init runs, **Then** it writes the change as one reviewable patch in an ignored location, names the patch in the report, and modifies no part of the existing file. [S: IAC-2] [P: D-04]
3. **AC-008**: **Given** an existing `.gitignore` without the Ballast ignore block, **When** init runs, **Then** it appends the block and changes nothing else in the file. [S: IAC-2] [S: IAC-4] [P: D-04]
4. **AC-009**: **Given** an existing rule that un-ignores an installed path, so the ignore probes still fail after the block is appended, **When** init runs, **Then** it stops before installing, writes the needed change as a patch and reports the conflicting rule; no partial installation remains. [S: IAC-2] [S: IAC-4] [P: D-04] [S: tools/setup]
5. **AC-010**: **Given** an established repository, **When** init finishes and the operator runs the reported `ballast trust`, **Then** the workflow preflight passes with no further edit; it does not depend on applying the reported patch, which the operator may apply afterwards. [S: IAC-1] [I]
6. **AC-011**: **Given** neither `AGENTS.md` nor `CLAUDE.md` exists, **When** init runs, **Then** it creates `AGENTS.md` and links `CLAUDE.md` to it; when either exists, it creates neither and proposes the Ballast addition as a patch. [S: IAC-2] [P: D-07]
7. **AC-012**: **Given** an established repository, **When** init runs, **Then** it writes no GitHub copy-once file or stack CI, and the readiness report lists the relevant ones with how to add them. [S: IAC-2] [P: D-08]

---

### User Story 3 - Adoption keeps the trust boundary and the tracked/ignored split (Priority: P1)

Whichever repository init adopts, it never executes the repository's commands, never records trust, never commits or pushes, and leaves installed paths ignored and project-owned files tracked. The operator sees exactly which protected inputs to review before trusting them.

**Why this priority**: Init writes protected inputs and the ignore block, both R2 boundaries; it must not grant more authority than the operator's own explicit trust.

**Independent Test**: After init in both scratch repositories, check that every installed path is ignored, every project-owned file is tracked-eligible, no trust baseline exists, no detected command ran, and no commit or remote was created.

**Acceptance Scenarios**:

1. **AC-013**: **Given** init has finished, **When** Git's ignore rules are checked, **Then** every path setup installs is ignored, and `ballast.toml`, the constitution, `docs/policies/project/` and the other project-owned files init created are not ignored. [S: IAC-4] [S: .specify/memory/constitution.md]
2. **AC-014**: **Given** init has finished, **When** the trust state is checked, **Then** no trust baseline exists, the launcher refuses until the operator runs `ballast trust`, and the report lists the generated protected inputs to review and names `ballast trust` as the next action. [S: IAC-4] [B: D-03] [S: tools/spec_workflow/launcher.py]
3. **AC-015**: **Given** a repository whose manifests, `Makefile` and CI name build, test and lint commands, **When** init inspects it, **Then** none of those commands is executed. [S: Issue #13 body] [P: D-11]
4. **AC-016**: **Given** a repository whose Git config sets hooks, a pager or an fsmonitor, **When** init runs any Git command, **Then** none of them runs. [S: IAC-4] [S: tools/setup]
5. **AC-017**: **Given** an evidence file or an installed path's parent is a symbolic link pointing outside the repository, **When** init inspects or writes, **Then** it neither reads nor writes through that link and reports it. [S: IAC-2] [S: docs/policies/security.md] [S: tools/setup]
6. **AC-018**: **Given** any repository, **When** init finishes, **Then** it has made no commit, no push and no remote; `git init` ran only when no repository existed. [S: IAC-4] [P: D-09]
7. **AC-019**: **Given** init generates `ballast.toml`, **When** it writes headless-agent settings, **Then** it adds no active agent permission rule; any suggested rule is a commented line marked inferred. [S: IAC-4] [P: D-06]
8. **AC-020**: **Given** the standard is installed by init, **When** the installation runs, **Then** it goes through the existing setup, so a failed download or switch keeps the prior state and the report names the failed stage. [S: IAC-4] [S: docs/adr/0007-recoverable-installation.md]

---

### User Story 4 - The generated profile reflects evidence and marks what is inferred (Priority: P2)

Init reads a fixed, bounded set of evidence files (manifests, lockfiles, `Makefile`, CI workflows, existing instructions, architecture docs, project policies) as data and fills the pin, checks, constitution, instructions and policy addenda from them. Values with direct evidence cite their source; values that are only inferred are marked and left inactive.

**Why this priority**: It makes the generated files trustworthy to review, but adoption is already safe and usable without perfect detection.

**Independent Test**: In a scratch repository with a CI step running `pytest` and a `Makefile` with an unlabelled `check` target, run init; `pytest` is an active check citing the CI file, and `make check` is a commented line marked inferred.

**Acceptance Scenarios**:

1. **AC-021**: **Given** a CI step or a named manifest script that runs a verification command, **When** init writes `ballast.toml`, **Then** the command is an active check entry with its evidence source in a comment. [S: IAC-3] [P: D-06]
2. **AC-022**: **Given** a command inferred only from a file name, such as an unlabelled `Makefile` target, **When** init writes `ballast.toml`, **Then** it appears as a commented, inactive line marked inferred. [S: IAC-3] [P: D-06]
3. **AC-023**: **Given** init creates the constitution, `AGENTS.md` or a project policy addendum, **When** the operator reads it, **Then** each value drawn from evidence cites its source and each unknown is marked as inferred or to confirm. [S: IAC-3] [P: D-07]
4. **AC-024**: **Given** a repository whose stack init does not recognize, **When** init runs, **Then** it falls back to a stack-neutral profile and marks that inference. [S: IAC-3] [P: D-11]
5. **AC-025**: **Given** a malformed or oversized manifest or CI file, **When** init inspects it, **Then** it skips the file with a reported reason and continues without executing or interpolating any of its content. [S: IAC-3] [P: D-11] [S: docs/policies/security.md]
6. **AC-026**: **Given** an `origin` remote on GitHub, **When** init writes `ballast.toml`, **Then** the GitHub repository setting is derived from it; with no remote or a non-GitHub remote, the setting is omitted and the report says how to add it. [S: IAC-3] [P: D-12]
7. **AC-027**: **Given** detected test or lint gates, **When** init writes project policy addenda, **Then** it writes an addendum only where such evidence supports it, and only when the addendum file is absent. [S: IAC-3] [P: D-07]

---

### User Story 5 - Rerunning init is safe and reports the same readiness (Priority: P2)

The operator, or a teammate, runs `ballast init` again on a repository it already adopted. Nothing tracked changes, setup is a no-op at the current pin, and the report shows the same readiness; drift between new evidence and committed config appears as a patch.

**Why this priority**: Idempotence makes init a safe readiness check and lets a partial adoption be completed, but the first run is the primary value.

**Independent Test**: Run init twice in each scratch repository; the second run changes no tracked file and reports the same readiness.

**Acceptance Scenarios**:

1. **AC-028**: **Given** a repository init has adopted, **When** init runs again, **Then** no tracked file changes and the readiness report is the same. [S: IAC-3] [P: D-10]
2. **AC-029**: **Given** an existing `ballast.toml`, **When** init runs, **Then** it keeps the pin and every existing project-owned file, creates only what is absent, and reports any difference between new evidence and committed config as a patch. [S: IAC-3] [P: D-10]
3. **AC-030**: **Given** a partially adopted repository (a pin but a missing constitution or ignore block), **When** init runs, **Then** it creates only the missing pieces and completes adoption. [S: IAC-3] [P: D-10] [P: D-04]
4. **AC-031**: **Given** Ballast's own repository, which dogfoods the standard, **When** init runs there, **Then** no tracked file changes. [S: IAC-3] [S: AGENTS.md] [I]

---

### User Story 6 - The readiness report says what is ready and what to do next (Priority: P3)

Init ends with a readiness report: instructions resolve, installed paths are ignored, the pinned version is available, the trust boundary is intact, chosen check commands exist, and the exact next action.

**Why this priority**: It turns the result into a clear next step, but every safety property above holds without it.

**Independent Test**: Inspect the report after init in each scratch repository and after a forced failure; each names its checks and the exact next command.

**Acceptance Scenarios**:

1. **AC-032**: **Given** init has finished, **When** it reports, **Then** the report states whether the instructions resolve, installed paths are ignored, the pinned version is available, the trust boundary is intact and the chosen check commands exist, and names the exact next action. [S: IAC-1] [S: docs/plans/2026-10-02-product-roadmap.md]
2. **AC-033**: **Given** the installed CLI is older than the standard it would pin, or the pinned version has no init, **When** init runs, **Then** it refuses before writing anything with a reason that names the remedy. [S: IAC-1] [S: docs/adr/0002-cli-standard-manifest.md] [I]
3. **AC-034**: **Given** any refusal or failed stage, **When** init stops, **Then** the report names the stage, what was and was not written, and how to continue. [S: IAC-2] [S: docs/adr/0007-recoverable-installation.md]

### Edge Cases

- The directory is not a Git repository, or is empty except for a `.git`: init runs `git init` only in the first case. [S: docs/plans/2026-10-02-product-roadmap.md] [P: D-09]
- `ballast.toml` already exists from a full or partial adoption: init keeps it and completes only what is absent. [P: D-10]
- `.gitignore` un-ignores an installed path: init stops before setup with a patch. [S: tools/setup] [P: D-04]
- Setup fails during the download or the switch: the prior state stays and the report names the stage. [S: docs/adr/0007-recoverable-installation.md]
- No terminal is attached and a material choice is missing: init refuses and names the flag. [P: D-05]
- An installed path's parent or a target file is a symbolic link: init refuses to write through it. [S: tools/setup]
- Repository Git config sets hooks or an fsmonitor: no Git call init makes runs them. [S: tools/setup]
- A manifest or CI file is malformed or very large: it is skipped with a reported reason. [S: docs/policies/security.md] [I]
- The `origin` remote is not on GitHub, or there is none: the GitHub setting is omitted and reported. [P: D-12]
- The CLI is older than the standard it would pin, or the pinned version has no init: init refuses with the remedy. [S: docs/adr/0002-cli-standard-manifest.md] [I]
- Ballast's own repository is an established repository init must not damage. [S: AGENTS.md] [I]

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `ballast init` MUST run in a directory without `ballast.toml`; the CLI MUST only bootstrap it, fetching the chosen standard version and running that version's declared init tool from the fetched directory, never from the checkout. [S: IAC-1] [B: D-01] [S: docs/adr/0002-cli-standard-manifest.md]
- **FR-002**: Init MUST classify the target as blank (empty, or only `.git`) or established and run `git init` only when no repository exists. [S: IAC-1] [S: docs/plans/2026-10-02-product-roadmap.md] [P: D-09]
- **FR-003**: Init MUST request only material choices (for a blank repository, a short product description and a stack or stack-neutral start; in an established repository, evidence it cannot resolve is marked to confirm in the generated files, not asked for), prompt for them on a terminal, accept each as a flag, and refuse without a terminal when one is missing. [S: IAC-1] [P: D-05]
- **FR-004**: Without an explicit version, init MUST pin the CLI's own release version; an explicit version MUST pass the existing version validation, and the download source MUST stay fixed. [S: IAC-1] [P: D-02] [S: .specify/memory/constitution.md]
- **FR-005**: Inspection MUST read only a fixed, size-bounded list of evidence files (manifests, lockfiles, `Makefile`, CI workflows, `AGENTS.md`, `CLAUDE.md`, architecture and ADR documents, `docs/policies/project/`) as data, MUST stay within the repository root without following links out of it, and MUST NOT execute or shell-interpolate any of their content. [S: IAC-3] [P: D-11] [S: docs/policies/security.md]
- **FR-006**: Every Git command init runs MUST disable repository hooks, pager and fsmonitor. [S: IAC-4] [S: tools/setup]
- **FR-007**: Init MUST create only absent files, with exclusive creation and no link followed; the only change it MAY make to an existing tracked file is appending the Ballast ignore block to `.gitignore` when the block is absent. [S: IAC-2] [P: D-04]
- **FR-008**: Every other proposed change to an existing file MUST be written as one reviewable patch under an ignored location and named in the report; existing tracked instructions, CI and project policy MUST stay byte-identical. [S: IAC-2] [P: D-04]
- **FR-009**: When the ignore probes still fail after the block is in place, init MUST stop before installing, leave no partial installation, and report the conflicting rule and the patch. [S: IAC-2] [S: IAC-4] [P: D-04] [S: tools/setup]
- **FR-010**: Init MUST generate, when absent, `ballast.toml`, the ignore block, the project constitution, evidence-backed project policy addenda, and `AGENTS.md` with a `CLAUDE.md` link (the link only when neither file exists), filled from generic shipped templates, the operator's answers and detected evidence. [S: IAC-1] [P: D-07] [S: docs/plans/2026-10-02-product-roadmap.md]
- **FR-011**: Generated values MUST cite their evidence; unknowns MUST be marked as inferred or to confirm; an unrecognized stack MUST fall back to stack-neutral, marked inferred. [S: IAC-3] [P: D-07] [P: D-11]
- **FR-012**: Commands with direct evidence (a CI step or a named manifest script) MUST become active check entries citing their source; inferred commands and any suggested agent permission rules MUST be commented lines marked inferred. Init MUST add no active headless-agent permission. [S: IAC-3] [S: IAC-4] [P: D-06]
- **FR-013**: The GitHub repository setting MUST be derived from a GitHub `origin` remote read with config-safe Git; otherwise it MUST be omitted and the report MUST say how to add it. [S: IAC-3] [P: D-12]
- **FR-014**: Init MUST install the ignored standard files only through the existing setup, keeping its staged, validated, recoverable installation and its ignore checks. [S: IAC-4] [S: docs/adr/0007-recoverable-installation.md] [S: Issue #13 intake scope comment]
- **FR-015**: Init MUST NOT record, modify or approve the trust baseline; it MUST list the generated protected inputs to review and name `ballast trust` as the operator's next action. [S: IAC-4] [B: D-03] [S: tools/spec_workflow/launcher.py]
- **FR-016**: Init MUST NOT commit, push or create a remote repository. [S: IAC-4] [P: D-09]
- **FR-017**: Init MUST NOT write GitHub copy-once files or stack CI; the report MUST list the relevant ones and how to add them. [S: IAC-2] [P: D-08]
- **FR-018**: On a repository with `ballast.toml`, init MUST keep the pin and every existing project-owned file, create only what is absent, rerun setup, verify, and report drift between new evidence and committed config as a patch; a second run on an adopted repository MUST change no tracked file. [S: IAC-3] [P: D-10]
- **FR-019**: Init MUST end with a readiness report covering instruction resolution, ignored paths, pinned-version availability, the trust boundary, the existence of chosen check commands, and the exact next action; a refusal or failure MUST name the stage, what was written and how to continue. [S: IAC-1] [S: docs/plans/2026-10-02-product-roadmap.md]
- **FR-020**: Init MUST refuse before writing anything when the CLI cannot run the chosen version's init, naming the remedy. [S: IAC-1] [S: docs/adr/0002-cli-standard-manifest.md] [I]
- **FR-021**: A new ADR MUST record that `init` runs before a pin exists and is a tool declared by the standard version, extending ADR-0002. [S: docs/adr/0002-cli-standard-manifest.md] [I]
- **FR-022**: Shipped templates MUST carry no project's names or domain rules. [S: .specify/memory/constitution.md]
- **FR-023**: Workflow tools MUST stay standard-library-only and run under `python3 -I -S`. [S: AGENTS.md]

### Key Entities

- **Target repository**: the directory init adopts; classified as blank or established from what it contains.
- **Evidence**: the bounded set of files init reads as data; each detected value records the file it came from.
- **Project profile**: the minimal set of choices init derives (pin, checks, GitHub repository, stack or stack-neutral, product description), each either evidenced or marked inferred.
- **Generated project-owned files**: `ballast.toml`, the ignore block in `.gitignore`, the constitution, project policy addenda, `AGENTS.md` and its `CLAUDE.md` link; tracked and reviewed by the operator.
- **Init patch**: one reviewable patch in an ignored location holding every change init would make to an existing file.
- **Readiness report**: init's final output: the verification results, the protected inputs to review, the patch if any, proposed optional integrations, and the next action.

## Non-goals

- Generating an application. [S: Issue #13 body]
- Overwriting existing project policy. [S: Issue #13 body]
- Executing detected build, test or lint commands during inspection. [S: Issue #13 body]
- Installing every optional integration, including stack CI and the GitHub copy-once files by default. [S: Issue #13 body] [P: D-08]
- Recording trust on the operator's behalf (#55). [S: Issue #13 intake scope comment]
- Committing, pushing or creating a remote repository. [P: D-09]
- Changing a pin on rerun; pin updates keep their reviewed path through `ballast preview` and an edit. [P: D-10]
- Changing the CLI distribution path, which #12 delivered. [S: docs/adr/0001-cli-release-asset-install.md]

Every Issue acceptance criterion (IAC-1 to IAC-4) is covered by an acceptance criterion above; none is a non-goal.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In scratch-project tests, both a blank directory and an established repository with existing `AGENTS.md` and CI reach a passing workflow preflight with one init invocation followed by one `ballast trust`, and no manual file edit.
- **SC-002**: A blank-directory adoption asks at most two questions; an established repository whose evidence is unambiguous asks none.
- **SC-003**: 100% of the existing tracked instructions, CI and policy files in the test fixtures are byte-identical after init, and every conflict case produces a patch with no partial write.
- **SC-004**: A second init on each adopted fixture changes zero tracked files and reports the same readiness.
- **SC-005**: In every test fixture, every installed path is ignored, every project-owned file is not ignored, no trust baseline exists after init, and zero detected project commands are executed.
- **SC-006**: Every generated check entry either cites an evidence file or is an inactive line marked inferred.
- **SC-007**: The fast gate, the full local gate and an end-to-end scratch run of init are recorded in the PR.

## Assumptions

- Blank and established repositories share one design: inspect, propose a profile, write absent files, reuse setup, verify, report. [I]
- "Reach a valid workflow preflight through one init invocation" means that after init and the single reported `ballast trust`, the preflight passes with no further edit. [I]
- The plan needs a CLI change so `init` can run before a pin exists, plus a new standard tool declared in the standard's manifest, recorded in a new ADR extending ADR-0002. [I]
- The pin defaults to the CLI's own release version, with an explicit override. [P: D-02]
- Conflicting changes go to one patch under ignored `.ballast/init/`; absent files are created; `.gitignore` gets the block appended when absent. [P: D-04]
- Material choices are prompted on a terminal, available as flags, and missing ones refuse without a terminal. [P: D-05]
- Check commands with direct evidence become active checks; inferred ones and permission suggestions stay commented. [P: D-06]
- The constitution and `AGENTS.md` come from generic templates filled from evidence, with unknowns marked. [P: D-07]
- GitHub templates and stack CI are proposed in the report, not written. [P: D-08]
- Init never commits or pushes. [P: D-09]
- A rerun keeps the pin and every project-owned file and reports drift as a patch. [P: D-10]
- Detection reads a fixed list of evidence files and never executes them; the list can grow in later releases. [P: D-11]
- The GitHub repository setting comes from a GitHub `origin` remote, otherwise it is omitted and reported. [P: D-12]
- The Issue's intake scope comment records that the operator's standing authority classifies this Issue as a leaf feature; this spec relies on that classification and on no other approval. [S: Issue #13 intake scope comment]
- Clarification: the preflight after init and `ballast trust` passes without the operator applying the reported init patch; the patch only proposes Ballast additions to existing files (AC-010, SC-001). [I]
- Clarification: in an established repository, a product description absent from the evidence is not asked for; the generated files mark it to confirm, so an unambiguous repository asks no question (FR-003, SC-002). [I]
- Clarification: "before writing anything" (AC-004, AC-033, FR-020) means before writing in the target directory; fetching the chosen standard version into the per-machine cache outside the repository may happen first. [I] [S: tools/ballast]
- The declared blocker #12 (CLI release-asset install) is merged, and setup's recoverable installation (#14) and worktree preparation (#15) are reused as they are. [S: docs/adr/0001-cli-release-asset-install.md] [S: docs/adr/0007-recoverable-installation.md] [S: docs/adr/0011-worktree-preparation.md]
