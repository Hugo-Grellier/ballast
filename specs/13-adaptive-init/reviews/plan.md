# Plan review: Adapt Ballast to blank and established repositories

- Review: plan (engineering)
- Feature: `specs/13-adaptive-init`, Issue #13, risk R2
- Reviewer: claude/claude-opus-5-5, fresh context, agent-provisional verdict
- Artifacts reviewed: `plan.md`, `research.md` (R1 to R17), `data-model.md`, `contracts/cli-init.md`, `contracts/init-tool.md`, `contracts/generated-files.md`, `quickstart.md`, against `spec.md` (AC-001 to AC-034, FR-001 to FR-023, SC-001 to SC-007), `intent.md` (PD-0015) and the run record. `tasks.md` and `decisions.md` do not exist yet at this stage.
- Policies and decisions read: `AGENTS.md`, `docs/policies/workflow.md`, `docs/policies/engineering.md`, `docs/policies/project/workflow.md`, `.specify/memory/constitution.md`, ADR-0002.

## Method

I traced each requirement to the research decision and contract that delivers it, then checked the plan's claims about existing code against the source it reuses:

- `tools/ballast`: `main` dispatch order, `command_standard`, `read_pin`, `pinned_ref`, `ensure_standard`, `trusted_standard_dir`, `REF`, `VERSION`, `PIN_REMEDY`, `before_launcher`, and `tools/cli.toml` (no `[init]` today; `[cli] minimum = "0.1.0"`).
- `tools/setup`: `GITIGNORE`, `IGNORE_PROBES`, `GIT`, `PARENTS`, `SEEDS`, `Setup.__init__` (reads `ballast.toml` at construction, so init must write it before constructing `Setup`, which R4 does), `Setup.main` (`current` no-op, `check_links(PARENTS)`, `check_ignored`), `finish` (seeds the constitution only when absent), `cli` (the exception set it maps to exit codes), and the module-level `sys.dont_write_bytecode`.
- `tools/spec_workflow/launcher.py`: `BASES`, `input_bases`, `_refusal`, `_trust_refusal`, `_trust`, `pinned_ref`, `state_dir` and `main`. The launcher's run preflight is exactly `_refusal`, so the plan's post-trust check (`_trust` then `_refusal(root) is None`) is a faithful proxy for "the workflow preflight passes" in AC-002, AC-010 and SC-001.
- `templates/AGENTS.md`: every placeholder in the template is covered by the table in `generated-files.md`, and the "starting point" paragraph exists to be dropped.

## Coverage

Every FR and AC maps to a research decision and to a fixture in `quickstart.md`. The shared stage sequence keeps the blank and established paths one design, as PD-0001 required. Refusals cluster before the first write in the target (R4), and fetching into the per-machine cache first is the reading PD-0014 recorded. FR-021 is delivered by the proposed ADR-0012, which extends ADR-0002 instead of editing it.

## Boundaries checked (R2)

- Trust: init never writes `trusted.json`. It only reads `_refusal` to report the trust boundary and names `ballast trust` as the next action (FR-015, AC-014).
- Agent authority: `extra_allow` suggestions are always commented and marked inferred, and no active permission is added (FR-012, AC-019).
- Ignore block and installed paths: the block, the probes and `PARENTS` come from the same version's setup, which avoids a second source of truth. The only change to an existing tracked file is the appended block (FR-007). Installation goes only through `Setup.main` (FR-014, ADR-0007).
- Execution: evidence is parsed as data, and CI lines are filtered to plain commands. Git always runs with setup's config-safe prefix, and `git init --template=` copies no hooks. Init makes no commit, push, remote or `gh` call. The CLI executes only the fetched version's declared `tools/init`, under `-IS` (BL-INV-002, ADR-0002 pattern).
- Pin: the default is the CLI's own version. A rerun keeps the pin, and a differing `--ref` is refused and pointed to `ballast preview` (BL-INV-004, D-10).

## Observations

The findings this review records are:

- Wording that makes AC-028's "same report" untestable.
- A remedy message that is wrong for adopted repositories pinned to a version without init.
- The in-process setup call catches narrower exceptions than setup's own `cli`.
- The link checks on setup's install parents run only after init's own writes.
- A bytecode-ordering premise in R11 that is wrong.
- An unspecified action when existing rules ignore a file init would create.
- A contract sentence about started programs that is broader than intended.

None of these changes the design, a boundary or product scope. Each can be settled while writing tasks and tests. The draft lists them with severity and disposition.

## Verdict

`approved`, as an agent-provisional review verdict. The plan is coherent, stays inside the approved spec, and reuses the owners of installation (setup) and trust (launcher) without redefining them.

<!-- ballast-findings: begin -->
## Findings (recorded from the review draft)

- F-001 (medium, spec-ambiguity, accepted-provisionally): AC-028/SC-004 require the second run's report to be the same, and quickstart asserts 'reports equal', but the init-tool report contract prints 'Written:' and 'Appended the Ballast ignore block' on the first run and 'Kept:' on the second, so the full reports cannot be equal. Tasks must define 'same' as the readiness block, the protected inputs and the Next line (or make the lists rerun-stable) and test that; no product change is needed.
- F-002 (medium, implementation-bug, accepted-provisionally): On an adopted repository pinned to a version without [init], the CLI uses the pin and refuses with 'pass --ref with a release that has it', but cli-init.md also refuses any --ref that differs from the pin, so the named remedy is impossible (AC-033 requires a working remedy). The refusal must name moving the pin (ballast preview REF, then a reviewed edit) when ballast.toml exists; the behaviour itself is correct.
- F-003 (medium, implementation-bug, accepted-provisionally): R11 catches only RefusedError and StageFailedError around Setup(root).main(), while setup's own cli also maps RuntimeError, ValueError and OSError to exit 1. Any of those would escape as a traceback with no AC-034 'stopped at install' report. Tasks must catch the same set as setup's cli and report it as stage install.
- F-004 (low, implementation-bug, open): R9 leaves linked installed-path parents (setup PARENTS such as docs/policies) to setup's check_links at install, after init has written ballast.toml and other files; quickstart's AC-017 fixture expects a refusal in stage check with the target untouched. The check stage should test every PARENTS entry too, not only init's own planned parents.
- F-005 (low, implementation-bug, open): R11 says sys.dont_write_bytecode is 'already set by setup', but setup sets it only while its module body runs, after the loader has compiled it; init must set it before loading tools/setup and the launcher, or it writes __pycache__ into the standard directory (a checkout under BALLAST_STANDARD_DIR).
- F-006 (low, spec-ambiguity, open): R8 says project-owned paths init creates are probed and must not be ignored (AC-013), but no stage says what happens when an existing rule ignores one (for example ballast.toml or AGENTS.md). Pick the behaviour in tasks: report it not-ready with a patch proposal, without rewriting the rule.
- F-007 (info, spec-ambiguity, open): init-tool.md says no program other than git is started, yet the install stage runs setup, which starts uvx and patch. Scope the sentence and the AC-015 audit hook to init's own stages (or to the faked setup) so the contract matches reality.
<!-- ballast-findings: end -->
