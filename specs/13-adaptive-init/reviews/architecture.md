# Architecture review: adaptive `ballast init` (#13)

- Review: architecture, specialists recheck after fix cycle 3 (the last) of Autonomous run `3ee0601b`
- Reviewer: claude/claude-opus-5-5, agent-provisional; same provider as the author (reduced independence)
- Scope: the change from `11134f1` to the working tree against the accepted ADRs it touches: ADR-0002 (CLI and standard manifest), ADR-0003 (launcher GitHub authority), ADR-0007 (recoverable installation), ADR-0008 (cache), ADR-0011 (worktree setup), and the new ADR-0012 (`docs/adr/0012-init-before-pin.md`); `specs/TECHNICAL-SPEC.md` for the #13 status line.
- Read: `AGENTS.md`, `docs/policies/workflow.md`, `docs/policies/engineering.md`, the spec, intent, plan, tasks, the cycle-3 fix input and the run record. There is no `docs/policies/project/engineering.md` and no `decisions.md`.

## What changed since the last review

The cycle-3 fix input held no findings or verdicts, only the failed `[checks]`. `git diff bd6ac47` touches only the run record, so the code and docs are those reviewed in cycles 0 to 2. Re-read the whole change.

## Assessment

- ADR-0002: `[init]` is a declared tool in `tools/cli.toml`, read as data through `declarations()`; the CLI's minimum version is enforced with the existing helpers. ADR-0012 extends ADR-0002 for the init-before-pin case without rewriting it.
- Single source: the ignore block, `PARENTS`, `GIT`, the probes, the pin rule and the trust refusal come from the same version's `tools/setup` and launcher; `AGENTS.md` is filled from the existing copy-once template. No second source of truth.
- ADR-0007: installation goes only through in-process `Setup.main`; a failed install keeps the previous installation and init reports a stop at `install`.
- ADR-0008 and ADR-0011: the cache path is unchanged and no worktree preparation is triggered.
- ADR-0003: `[github] repository` comes only from a GitHub `origin` remote into the reviewed `ballast.toml`; the launcher still confirms it.

## Residuals, re-checked in source

- `report_stop` (tools/init:1565) lists only `self.written`; an append to an existing `.gitignore` (`self.appended`) before a later stage stops is missing from the stop report, short of AC-034.
- `fill()` (tools/init:431) replaces each `{{name}}` in turn on the growing text, so a description containing a placeholder is substituted again or stops `plan` with a remedy that blames the standard.
- `tools/init` calls the private `setup._open_dir` and `launcher._refusal`; acceptable because they ship and version together under ADR-0012, but a refactor of either must update `tools/init`.

No further ADR is needed. The failed checks are environmental (read-only `~/.local/share/uv/tools` and `~/.local/state`) and do not trace to the architecture of this change; a passing gate is still required before merge.

<!-- ballast-findings: begin -->
## Findings (recorded from the review draft)

- F-001 (low, implementation-bug, open): Unchanged since cycle 0. When the ignore stage fails on a conflicting rule, or install fails, after add_block appended to an existing .gitignore, report_stop lists only self.written, so the tracked .gitignore change is missing from the stop report, short of AC-034. Fix: report self.appended in report_stop and add a test.
- F-002 (low, implementation-bug, open): Unchanged since cycle 0. fill() replaces each {{name}} in turn on the growing text; a description containing {{gates}} is substituted again, and any other {{word}} stops plan with a remedy that blames the standard. --description works around it. Fix: one MUSTACHE.sub pass, or reject {{ in description_error.
- F-003 (info, architecture-issue, open): Unchanged since cycle 0. tools/init calls setup._open_dir and launcher._refusal. Acceptable because the files ship and version together and ADR-0012 gives the standard ownership, but a refactor of either private helper must update tools/init too.
<!-- ballast-findings: end -->
