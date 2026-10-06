# Autonomous run record

Run `3ee0601b` for #13 (`specs/13-adaptive-init`). Generated from the operator records; every check re-renders it, so an edit fails the next check. Every decision below is agent-provisional; merging the PR that contains this record is the only human approval.

## Mode and risk

- Mode start: autonomous at 2026-10-06T10:42:33+00:00 by operator
- Risk: R2 (scope-record); history: R2 at 2026-10-06T10:42:33+00:00
- Limits (default): 240 minutes wall time, 40 agent steps
- Spend: bounded by the agent-step limit; every agent step, retry and fix cycle counts; monetary spend is not measured
- Authoring integration: claude; review integration: claude
- Integration fallback: codex cannot start its own sandbox inside Ballast's confinement; claude takes both roles (DEC-0004)

## R2 notice

This is an R2 change. It was made without any prior human approval; the pre-change approval was agent-provisional (PD-0018).

R2 boundaries touched:

- ignore block and setup-installed paths
- launcher trust model (initial trust consolidation)
- protected inputs (generated ballast.toml)

## Material provisional changes

None.

## Provisional decisions

| ID | Point | Decision | Summary | Decided by | Artifact | Evidence | Superseded by |
| --- | --- | --- | --- | --- | --- | --- | --- |
| PD-0001 | scope | accept (agent-provisional) | Issue #13 is one independently specifiable leaf outcome: a single `ballast init` invocation makes a blank or established repository usable, with a clear in/out boundary. | claude/claude-opus-5-5 (author) | [.specify/feature.json](../../../.specify/feature.json) `2ffcf8b8987d` | [.specify/feature.json](../../../.specify/feature.json), <https://github.com/Hugo-Grellier/ballast/issues/13>, <https://github.com/Hugo-Grellier/ballast/issues/11>, [docs/policies/spec-kit-workflow.md](../../../docs/policies/spec-kit-workflow.md), [docs/policies/project/workflow.md](../../../docs/policies/project/workflow.md), [docs/plans/2026-10-02-product-roadmap.md](../../../docs/plans/2026-10-02-product-roadmap.md), [specs/12-cli-install-doctor](../../../specs/12-cli-install-doctor), [specs/14-recoverable-install](../../../specs/14-recoverable-install), [specs/15-worktree-setup](../../../specs/15-worktree-setup), [AGENTS.md](../../../AGENTS.md) |  |
| PD-0002 | clarification | assume (agent-provisional) | D-02: init pins the CLI's own release tag v&lt;VERSION&gt;, overridable with an explicit ref. | claude/claude-opus-5-5 (author) | [specs/13-adaptive-init/discovery.md](../../../specs/13-adaptive-init/discovery.md) `15b3ce90cd2d` | [specs/13-adaptive-init/discovery.md](../../../specs/13-adaptive-init/discovery.md), [tools/ballast](../../../tools/ballast), [.specify/memory/constitution.md](../../../.specify/memory/constitution.md), [docs/adr/0001-cli-release-asset-install.md](../../../docs/adr/0001-cli-release-asset-install.md) |  |
| PD-0003 | clarification | assume (agent-provisional) | D-12: [github] repository comes from a GitHub origin remote; otherwise it is omitted and the report says how to add it. | claude/claude-opus-5-5 (author) | [specs/13-adaptive-init/discovery.md](../../../specs/13-adaptive-init/discovery.md) `15b3ce90cd2d` | [specs/13-adaptive-init/discovery.md](../../../specs/13-adaptive-init/discovery.md), [docs/adr/0003-launcher-github-authority.md](../../../docs/adr/0003-launcher-github-authority.md), [tools/ballast](../../../tools/ballast) |  |
| PD-0004 | clarification | assume (agent-provisional) | D-04: init creates only absent files, appends an absent ignore block to .gitignore, and writes every other change as one patch under ignored .ballast/init/. | claude/claude-opus-5-5 (author) | [specs/13-adaptive-init/discovery.md](../../../specs/13-adaptive-init/discovery.md) `15b3ce90cd2d` | [specs/13-adaptive-init/discovery.md](../../../specs/13-adaptive-init/discovery.md), [tools/setup](../../../tools/setup), [docs/plans/2026-10-02-product-roadmap.md](../../../docs/plans/2026-10-02-product-roadmap.md) |  |
| PD-0005 | clarification | assume (agent-provisional) | D-05: material choices are prompted on a terminal, each has a flag, and a missing one refuses without a terminal. | claude/claude-opus-5-5 (author) | [specs/13-adaptive-init/discovery.md](../../../specs/13-adaptive-init/discovery.md) `15b3ce90cd2d` | [specs/13-adaptive-init/discovery.md](../../../specs/13-adaptive-init/discovery.md), [docs/plans/2026-10-02-product-roadmap.md](../../../docs/plans/2026-10-02-product-roadmap.md) |  |
| PD-0006 | clarification | assume (agent-provisional) | D-06: evidence-backed commands become active [checks] entries; inferred commands and extra_allow rules are written commented and marked inferred. | claude/claude-opus-5-5 (author) | [specs/13-adaptive-init/discovery.md](../../../specs/13-adaptive-init/discovery.md) `15b3ce90cd2d` | [specs/13-adaptive-init/discovery.md](../../../specs/13-adaptive-init/discovery.md), [tools/ballast](../../../tools/ballast), [docs/policies/project/workflow.md](../../../docs/policies/project/workflow.md), [README.md](../../../README.md) |  |
| PD-0007 | clarification | assume (agent-provisional) | D-07: absent constitution, AGENTS.md and evidence-backed policy addenda are filled from generic templates with unknowns marked. | claude/claude-opus-5-5 (author) | [specs/13-adaptive-init/discovery.md](../../../specs/13-adaptive-init/discovery.md) `15b3ce90cd2d` | [specs/13-adaptive-init/discovery.md](../../../specs/13-adaptive-init/discovery.md), [templates/AGENTS.md](../../../templates/AGENTS.md), [tools/setup](../../../tools/setup), [.specify/memory/constitution.md](../../../.specify/memory/constitution.md) |  |
| PD-0008 | clarification | assume (agent-provisional) | D-08: init writes no GitHub copy-once files or stack CI; the readiness report lists the relevant ones. | claude/claude-opus-5-5 (author) | [specs/13-adaptive-init/discovery.md](../../../specs/13-adaptive-init/discovery.md) `15b3ce90cd2d` | [specs/13-adaptive-init/discovery.md](../../../specs/13-adaptive-init/discovery.md), [docs/plans/2026-10-02-product-roadmap.md](../../../docs/plans/2026-10-02-product-roadmap.md), [templates/github/pull_request_template.md](../../../templates/github/pull_request_template.md) |  |
| PD-0009 | clarification | assume (agent-provisional) | D-09: init never commits, pushes or creates a remote; it runs git init only when no repository exists. | claude/claude-opus-5-5 (author) | [specs/13-adaptive-init/discovery.md](../../../specs/13-adaptive-init/discovery.md) `15b3ce90cd2d` | [specs/13-adaptive-init/discovery.md](../../../specs/13-adaptive-init/discovery.md), [AGENTS.md](../../../AGENTS.md), [docs/plans/2026-10-02-product-roadmap.md](../../../docs/plans/2026-10-02-product-roadmap.md) |  |
| PD-0010 | clarification | assume (agent-provisional) | D-10: a rerun keeps the pin and existing project-owned files, creates only what is absent, reruns setup and reports drift as a patch. | claude/claude-opus-5-5 (author) | [specs/13-adaptive-init/discovery.md](../../../specs/13-adaptive-init/discovery.md) `15b3ce90cd2d` | [specs/13-adaptive-init/discovery.md](../../../specs/13-adaptive-init/discovery.md), [README.md](../../../README.md) |  |
| PD-0011 | clarification | assume (agent-provisional) | D-11: inspection reads a fixed, size-bounded list of evidence files as data; an unknown stack falls back to stack-neutral, marked inferred. | claude/claude-opus-5-5 (author) | [specs/13-adaptive-init/discovery.md](../../../specs/13-adaptive-init/discovery.md) `15b3ce90cd2d` | [specs/13-adaptive-init/discovery.md](../../../specs/13-adaptive-init/discovery.md), [docs/policies/security.md](../../../docs/policies/security.md), [docs/plans/2026-10-02-product-roadmap.md](../../../docs/plans/2026-10-02-product-roadmap.md) |  |
| PD-0012 | clarification | assume (agent-provisional) | The post-trust preflight passes without applying the reported init patch | claude/claude-opus-5-5 (author) | [specs/13-adaptive-init/spec.md](../../../specs/13-adaptive-init/spec.md) `16fb76c3f2f4` | [specs/13-adaptive-init/spec.md](../../../specs/13-adaptive-init/spec.md), [specs/13-adaptive-init/discovery.md](../../../specs/13-adaptive-init/discovery.md), [tools/spec_workflow/launcher.py](../../../tools/spec_workflow/launcher.py) |  |
| PD-0013 | clarification | assume (agent-provisional) | An established repository's missing product description is marked to confirm, not asked | claude/claude-opus-5-5 (author) | [specs/13-adaptive-init/spec.md](../../../specs/13-adaptive-init/spec.md) `16fb76c3f2f4` | [specs/13-adaptive-init/spec.md](../../../specs/13-adaptive-init/spec.md), [specs/13-adaptive-init/discovery.md](../../../specs/13-adaptive-init/discovery.md) |  |
| PD-0014 | clarification | assume (agent-provisional) | Refusing before writing anything means in the target directory; fetching into the machine cache may precede it | claude/claude-opus-5-5 (author) | [specs/13-adaptive-init/spec.md](../../../specs/13-adaptive-init/spec.md) `16fb76c3f2f4` | [specs/13-adaptive-init/spec.md](../../../specs/13-adaptive-init/spec.md), [tools/ballast](../../../tools/ballast) |  |
| PD-0015 | intent | accept (agent-provisional) | The spec for #13 is one coherent feature: a single `ballast init` adopts a blank or established repository, with consistent outcome, constraints, non-goals and acceptance criteria and no unresolved marker. | claude/claude-opus-5-5 (author) | [specs/13-adaptive-init/spec.md](../../../specs/13-adaptive-init/spec.md) `16fb76c3f2f4` | [specs/13-adaptive-init/discovery.md](../../../specs/13-adaptive-init/discovery.md), [specs/13-adaptive-init/spec.md](../../../specs/13-adaptive-init/spec.md), [specs/13-adaptive-init/checklists/requirements.md](../../../specs/13-adaptive-init/checklists/requirements.md), [specs/13-adaptive-init/autonomous/record.md](../../../specs/13-adaptive-init/autonomous/record.md), <https://github.com/Hugo-Grellier/ballast/issues/13>, [AGENTS.md](../../../AGENTS.md), [docs/policies/spec-kit-workflow.md](../../../docs/policies/spec-kit-workflow.md), [docs/policies/project/workflow.md](../../../docs/policies/project/workflow.md) |  |
| PD-0016 | plan-review | accept-finding (agent-provisional) | Plan for ballast init covers every FR/AC, keeps the R2 boundaries and reuses setup and launcher; three medium and four minor gaps to settle in tasks | claude/claude-opus-5-5 (reviewer) | [specs/13-adaptive-init/plan.md](../../../specs/13-adaptive-init/plan.md) `efe78e781569` | [specs/13-adaptive-init/reviews/plan.md](../../../specs/13-adaptive-init/reviews/plan.md), [specs/13-adaptive-init/plan.md](../../../specs/13-adaptive-init/plan.md), [specs/13-adaptive-init/research.md](../../../specs/13-adaptive-init/research.md), [specs/13-adaptive-init/contracts/cli-init.md](../../../specs/13-adaptive-init/contracts/cli-init.md), [specs/13-adaptive-init/contracts/init-tool.md](../../../specs/13-adaptive-init/contracts/init-tool.md), [specs/13-adaptive-init/contracts/generated-files.md](../../../specs/13-adaptive-init/contracts/generated-files.md), [specs/13-adaptive-init/quickstart.md](../../../specs/13-adaptive-init/quickstart.md), [specs/13-adaptive-init/spec.md](../../../specs/13-adaptive-init/spec.md), [tools/setup](../../../tools/setup), [tools/ballast](../../../tools/ballast), [tools/spec_workflow/launcher.py](../../../tools/spec_workflow/launcher.py), [docs/adr/0002-cli-standard-manifest.md](../../../docs/adr/0002-cli-standard-manifest.md) |  |
| PD-0017 | plan | accept (agent-provisional) | The plan for ballast init delivers the agent-provisional spec (PD-0015) as one shared stage sequence for blank and established repositories. It reuses setup and the launcher unchanged and keeps every R2 boundary. The seven review findings are for tasks to settle and change no design. | claude/claude-opus-5-5 (author) | [specs/13-adaptive-init/plan.md](../../../specs/13-adaptive-init/plan.md) `efe78e781569` | [specs/13-adaptive-init/plan.md](../../../specs/13-adaptive-init/plan.md), [specs/13-adaptive-init/reviews/plan.md](../../../specs/13-adaptive-init/reviews/plan.md), [specs/13-adaptive-init/spec.md](../../../specs/13-adaptive-init/spec.md), [specs/13-adaptive-init/intent.md](../../../specs/13-adaptive-init/intent.md), [specs/13-adaptive-init/research.md](../../../specs/13-adaptive-init/research.md), [specs/13-adaptive-init/contracts/cli-init.md](../../../specs/13-adaptive-init/contracts/cli-init.md), [specs/13-adaptive-init/contracts/init-tool.md](../../../specs/13-adaptive-init/contracts/init-tool.md), [specs/13-adaptive-init/contracts/generated-files.md](../../../specs/13-adaptive-init/contracts/generated-files.md), [specs/13-adaptive-init/quickstart.md](../../../specs/13-adaptive-init/quickstart.md), [specs/13-adaptive-init/autonomous/record.md](../../../specs/13-adaptive-init/autonomous/record.md), [AGENTS.md](../../../AGENTS.md), [docs/policies/workflow.md](../../../docs/policies/workflow.md), [docs/policies/spec-kit-workflow.md](../../../docs/policies/spec-kit-workflow.md), [docs/policies/project/workflow.md](../../../docs/policies/project/workflow.md), [docs/adr/0002-cli-standard-manifest.md](../../../docs/adr/0002-cli-standard-manifest.md) |  |
| PD-0018 | tasks | accept (agent-provisional) | tasks.md for ballast init cites a test task for every AC-001..AC-034, carries plan findings F-001..F-007 into tasks, and its 26 waves respect every declared dependency; analyze found no critical or high issue. | claude/claude-opus-5-5 (author) | [specs/13-adaptive-init/tasks.md](../../../specs/13-adaptive-init/tasks.md) `54149434bee6` | [specs/13-adaptive-init/tasks.md](../../../specs/13-adaptive-init/tasks.md), [.specify/workflow-state/3ee0601b/agents/20261006T110750881447Z-speckit-analyze-claude/stdout.log](../../../.specify/workflow-state/3ee0601b/agents/20261006T110750881447Z-speckit-analyze-claude/stdout.log), [specs/13-adaptive-init/spec.md](../../../specs/13-adaptive-init/spec.md), [specs/13-adaptive-init/plan.md](../../../specs/13-adaptive-init/plan.md), [specs/13-adaptive-init/reviews/plan.md](../../../specs/13-adaptive-init/reviews/plan.md), [specs/13-adaptive-init/autonomous/record.md](../../../specs/13-adaptive-init/autonomous/record.md), [docs/policies/spec-kit-workflow.md](../../../docs/policies/spec-kit-workflow.md), [docs/policies/workflow.md](../../../docs/policies/workflow.md), [docs/policies/project/workflow.md](../../../docs/policies/project/workflow.md), [AGENTS.md](../../../AGENTS.md) |  |

### PD-0001 basis

> Per the scope gate in docs/policies/spec-kit-workflow.md, the Issue has one main outcome (one `ballast init` brings a blank or an established repository to a valid workflow preflight without hand-writing the pin, ignore block, constitution, policy addenda or agent instructions). The four acceptance criteria form one group: reaching preflight, preserving existing files with a reviewable patch on conflict, idempotent evidence-based generation with uncertain inference marked, and correct ignored/tracked paths with no silent trust. They share one design (inspect, propose profile, apply safe changes, reuse setup, report next action) and are testable together. The boundary is explicit: out of scope are generating an application, overwriting project policy, executing detected commands during inspection, installing every optional integration, and recording trust on the operator's behalf (#55). The installer it reuses already exists (specs/14-recoverable-install, specs/15-worktree-setup) and its declared blocker #12 has a feature directory (specs/12-cli-install-doctor). It is a child outcome of Epic #11 and matches the `ballast init` section of docs/plans/2026-10-02-product-roadmap.md. Risk stays R2 per docs/policies/project/workflow.md: init generates protected inputs (ballast.toml), writes the ignore block and setup-installed paths, and touches the trust boundary. Recheck scope after clarify, plan and tasks; the blank-repository and established-repository paths must stay one design, or the run should stop for decomposition.

### PD-0002 basis

> The ref passes the existing ref validation in tools/ballast and the download source stays fixed (BL-INV-004 in .specify/memory/constitution.md); the pin is a tracked file the operator reviews and can change before trust. No network lookup is added.

### PD-0003 basis

> The value is a reviewed line in ballast.toml that grants no authority by itself; the launcher keeps GitHub authority (docs/adr/0003-launcher-github-authority.md). The operator can edit it before trust.

### PD-0004 basis

> Existing instructions, CI and policy stay byte-identical (IAC-2); every write is a tracked change visible in git diff or an ignored patch; the ignore check in tools/setup still refuses an incorrect .gitignore, and init stops before setup when the probes fail. The roadmap asks init to apply safe changes and offer a patch for conflicts.

### PD-0005 basis

> A command-line interface choice that adds no authority, never invents a material answer, keeps tests deterministic, and can gain options later. The roadmap names the blank-repository choices (product description, stack or stack-neutral).

### PD-0006 basis

> Init adds no headless-agent permission, an R2 boundary per docs/policies/project/workflow.md. Nothing is executed during inspection; [checks] runs only after the operator reviews and trusts ballast.toml; uncommenting a line is a deliberate operator edit; ballast doctor in tools/ballast already reports checks-allowed with its remedy.

### PD-0007 basis

> Files are created only when absent; shipped templates stay generic (principle 7 of .specify/memory/constitution.md); setup already seeds a constitution only when absent (tools/setup); the results are tracked changes the operator reviews and edits before committing.

### PD-0008 basis

> Writes nothing. The roadmap says to propose PR/CI templates and not install every stack integration; the Issue excludes installing every optional integration. A flag to add them can follow.

### PD-0009 basis

> The most conservative option: no history change and no externally visible action, which AGENTS.md reserves for explicit human approval. A commit option can be added later.

### PD-0010 basis

> Writes nothing that exists, so reruns are idempotent (IAC-3); pin changes keep their existing reviewed path through ballast preview and a committed edit (README.md).

### PD-0011 basis

> Executes nothing (out of scope in the Issue), bounds exposure to untrusted content per docs/policies/security.md, and only shapes suggestions the operator reviews; the list can grow in later releases.

### PD-0012 basis

> AC-010 allowed an operator-applied patch while SC-001 required no manual edit; the brief does not settle which. The patch only proposes Ballast additions to existing files such as AGENTS.md, which the preflight does not depend on. Reversible: a later change can tighten the criterion without data loss or migration.

### PD-0013 basis

> SC-002 says an unambiguous established repository asks no question, while D-05 lists the product description as a material choice for blank repositories. Marking it to confirm follows D-07's rule for unknowns, adds no authority, and a prompt can be added later without data loss.

### PD-0014 basis

> AC-033 and FR-020 require refusing before writing anything when the pinned version has no init, which init can only learn by fetching that version. The CLI caches versions under XDG_DATA_HOME outside the repository, so the target stays untouched. Reversible wording clarification; no repository state is affected.

### PD-0015 basis

> spec.md states one outcome (one init plus one `ballast trust` reaches a passing preflight) across blank and established repositories via one shared design: inspect, profile, write absent files, reuse setup, report. Each Issue criterion IAC-1 to IAC-4 maps to AC-001..AC-034 and FR-001..FR-023, and spec.md says none is a non-goal. Constraints keep the R2 boundaries recorded in the run record: no trust recorded (FR-015, D-03 settled from the intake scope), no active agent permission (FR-012), installed paths ignored and project files tracked (AC-013), installation only through the existing recoverable setup (FR-014), stdlib tools under python3 -I -S (FR-023, AGENTS.md). Non-goals match the Issue's out-of-scope list plus no commit/push and no pin change on rerun. Every [P:] tag traces to a discovery.md decision; the brief lists no undecided item, and the spec has no NEEDS CLARIFICATION marker. Its three Clarification assumptions match agent-provisional PD-0012 to PD-0014, which resolved the only AC-010/SC-001, D-05/SC-002 and AC-033 tensions reversibly. The requirements checklist has no open item. FR-021 requires a new ADR extending ADR-0002 for init running before a pin exists, consistent with D-01; the plan must deliver it. Risk stays R2 per docs/policies/project/workflow.md.

### PD-0016 basis

> Traced FR-001..FR-023 and AC-001..AC-034 to research R1-R17, the three contracts and quickstart fixtures; verified the plan's claims against tools/ballast (main dispatch, read_pin, ensure_standard, trusted_standard_dir), tools/setup (GITIGNORE, IGNORE_PROBES, GIT, PARENTS, Setup.__init__/main/finish/cli) and launcher.py (BASES, _refusal, _trust, main: the run preflight is _refusal). No trust write, no active extra_allow, installation only through Setup.main, evidence as data, config-safe git, fixed download source, ADR-0012 extending ADR-0002. Findings are wording, error-handling and ordering gaps fixable in tasks without changing design, scope or a boundary. tasks.md and decisions.md do not exist yet at this stage.

### PD-0017 basis

> plan.md traces FR-001..FR-023 and AC-001..AC-034 to research R1-R17, three contracts and quickstart fixtures, and the engineering plan review (PD-0016, reviews/plan.md) confirmed that coverage against tools/ballast, tools/setup and launcher.py. Blank and established repositories share one stage sequence (check, inspect, choose, plan, git-init, ignore, write, patch, install, verify, report), so scope stays one outcome as PD-0001 required. R2 boundaries hold: init never writes trust and only reports _refusal with ballast trust as the next action (FR-015). extra_allow suggestions stay commented (FR-012). The ignore block, probes and PARENTS come from the same version's setup, and installation goes only through Setup.main (FR-014, ADR-0007). Evidence is parsed as data, git runs config-safe, and nothing is committed or pushed. The CLI runs only the fetched version's tools/init under -I -S, and the source stays fixed (BL-INV-002, BL-INV-004). FR-021 is delivered by a proposed ADR-0012 extending ADR-0002. The constitution check passes. Review findings F-001..F-007 (wording, remedy text, exception set, check and bytecode ordering) are fixable in tasks and tests without changing behaviour, scope or a boundary; tasks.md must address them. Risk stays R2 with the recorded boundaries.

### PD-0018 basis

> Every AC-001..AC-034 is cited by a test task (T011-T013, T020-T021, T026-T027, T029-T030, T035-T036, T039-T040) and FR-022/FR-023 by T049; SC-007 is workflow-owned per quickstart.md. The analyze report confirms 100% FR coverage, no constitution violation and 0 critical/high. Each wave was checked: no task runs before its dependencies, and tools/init and tests/test_init.py edits are chained so no two run at once. Plan review F-001..F-007 (PD-0016) map to T036, T010/T040, T018, T006/T027, T005/T048, T021/T028 and T027/T048. Medium analyze items do not block: I1 (FR-003 vs never prompting in an established repo) matches agent-provisional PD-0013 and is a wording fix; C1 (assert zero prompts with a terminal in T020), C2 (force setup download and switch failures in T026 for AC-020) and U1 (Next/checks line tells the operator to uncomment the inferred extra_allow) are test or message additions that implement and converge must close without changing scope or a boundary. LOW items (A1 in-process AC-031, U2 linked CLAUDE.md readiness, U3 check uses the fixed write set, U4 re-pass flags after a blank stop, F1 T047 phase label) are clarifications. R2 boundaries stay covered: no trust write (T026), commented extra_allow (T008, T026), no execution (T027), ignore split (T021, T028). Risk stays R2 per docs/policies/project/workflow.md; only merge needs a human.

## Reviews

- PD-0016 plan: approved; reviewer claude/claude-opus-5-5; cross-provider: no; report [specs/13-adaptive-init/reviews/plan.md](../../../specs/13-adaptive-init/reviews/plan.md)

Reduced independence: reviews used the authoring provider.

## Open findings

- PD-0016 F-001 (medium, spec-ambiguity, accepted-provisionally): AC-028/SC-004 require the second run's report to be the same, and quickstart asserts 'reports equal', but the init-tool report contract prints 'Written:' and 'Appended the Ballast ignore block' on the first run and 'Kept:' on the second, so the full reports cannot be equal. Tasks must define 'same' as the readiness block, the protected inputs and the Next line (or make the lists rerun-stable) and test that; no product change is needed.
- PD-0016 F-002 (medium, implementation-bug, accepted-provisionally): On an adopted repository pinned to a version without [init], the CLI uses the pin and refuses with 'pass --ref with a release that has it', but cli-init.md also refuses any --ref that differs from the pin, so the named remedy is impossible (AC-033 requires a working remedy). The refusal must name moving the pin (ballast preview REF, then a reviewed edit) when ballast.toml exists; the behaviour itself is correct.
- PD-0016 F-003 (medium, implementation-bug, accepted-provisionally): R11 catches only RefusedError and StageFailedError around Setup(root).main(), while setup's own cli also maps RuntimeError, ValueError and OSError to exit 1. Any of those would escape as a traceback with no AC-034 'stopped at install' report. Tasks must catch the same set as setup's cli and report it as stage install.
- PD-0016 F-004 (low, implementation-bug, open): R9 leaves linked installed-path parents (setup PARENTS such as docs/policies) to setup's check_links at install, after init has written ballast.toml and other files; quickstart's AC-017 fixture expects a refusal in stage check with the target untouched. The check stage should test every PARENTS entry too, not only init's own planned parents.
- PD-0016 F-005 (low, implementation-bug, open): R11 says sys.dont_write_bytecode is 'already set by setup', but setup sets it only while its module body runs, after the loader has compiled it; init must set it before loading tools/setup and the launcher, or it writes __pycache__ into the standard directory (a checkout under BALLAST_STANDARD_DIR).
- PD-0016 F-006 (low, spec-ambiguity, open): R8 says project-owned paths init creates are probed and must not be ignored (AC-013), but no stage says what happens when an existing rule ignores one (for example ballast.toml or AGENTS.md). Pick the behaviour in tasks: report it not-ready with a patch proposal, without rewriting the rule.
- PD-0016 F-007 (info, spec-ambiguity, open): init-tool.md says no program other than git is started, yet the install stage runs setup, which starts uvx and patch. Scope the sentence and the AC-015 audit hook to init's own stages (or to the faked setup) so the contract matches reality.

## Checks

- run-checks: not run yet
- run-checks ran in the run's worktree, so git-ignored files there were visible to them and are not part of this PR
- agent-reported: none; agent claims never satisfy run-checks

CI results appear on this PR.
