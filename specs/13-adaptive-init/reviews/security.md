# Security review: adaptive `ballast init` (#13)

- Review: security, specialists recheck after fix cycle 3 (the last) of Autonomous run `3ee0601b`
- Reviewer: claude/claude-opus-5-5, agent-provisional; same provider as the author (reduced independence)
- Scope: the change from `11134f1` to the working tree: `tools/ballast` (`init`, `init_ref`, `refuse`, `declarations`), the new `tools/init`, `tools/cli.toml`, `templates/init/*`, and how they meet `tools/setup`, `tools/spec_workflow/launcher.py` and the confined check runner.
- Read: `AGENTS.md`, `docs/policies/workflow.md`, `docs/policies/security.md`, `.specify/memory/constitution.md`, the spec, intent, plan, tasks, the fix input for cycle 3 and the run record. There is no `docs/policies/project/security.md` and no `decisions.md`.

## What changed since the last review

The cycle-3 fix input held no findings and no verdicts, only the three `[checks]` commands that failed again. `git diff bd6ac47` touches only `specs/13-adaptive-init/autonomous/record.md`; `tools/ballast`, `tools/init`, `tools/cli.toml` and `templates/init` are byte-identical to what cycles 0 to 2 reviewed. The whole change was still re-read, not only the fix.

## Authority trace

- CLI bootstrap: `ballast init` validates the ref, fetches through the verified cache, refuses on a missing `[init]` declaration or a `[cli]` minimum before anything runs, then `execv`s the cached `tools/init` under `python3 -I -S`. Nothing it runs comes from the target checkout.
- Trust: `tools/init` never writes a trust baseline; `render_config` rejects an agents table, and every inferred `extra_allow` is written commented. `ballast trust` stays an operator step (BL-INV-001..004).
- Git: only fixed subcommands through `setup.GIT`, with hooks, pager and fsmonitor disabled. No commit, push or remote creation; `git init` only when no repository exists.
- Evidence: a fixed list of files is read as size-bounded, no-follow data and parsed; nothing found is executed. CI-derived checks exclude `$`, backtick, `;`, `|`, `&`, `<`, `>` and later run confined with a sanitized environment.
- Writes: creates use `O_EXCL|O_NOFOLLOW` after `check_links` covers `setup.PARENTS`; the ignore block is appended once; every other change is a patch under ignored `.ballast/init/`, written only when ignored.
- Installation: only in-process `Setup.main`, with setup's own exception set mapped to a stop at `install`.

## Residuals, re-checked in source

- `verifier()` (tools/init:254) still accepts `make <one target>`, `uv run <anything>` and `uvx <anything>` from a CI `run:` line, so a deploy or publish step can become an active `[checks]` entry. Bounded by operator review of `ballast.toml` before trust and by confinement.
- A manifest description still becomes text in the generated `AGENTS.md` and constitution: repository content at the same trust level, reviewed before commit.

## Checks

The runner's `[checks]` failed again after cycle 3 with the same signatures as cycles 0 to 2: `uvx` cannot write the read-only `~/.local/share/uv/tools`, and the unit suite's errors come from `outside_temp()` in `tests/test_autonomy.py` creating state under a read-only `~/.local/state`. The single failure is a governance subprocess exiting on the same condition. No failure traces to this change, but the AC-015 audit-hook test and the rest of the init tests have still not passed in any recorded run, so a passing gate from a writable environment must be shown in the PR before merge. This is the last review; the failed checks stop the run for a human regardless of this verdict.

<!-- ballast-findings: begin -->
## Findings (recorded from the review draft)

- F-001 (low, spec-ambiguity, open): Unchanged since cycle 0. verifier() accepts make &lt;one target&gt;, npm/pnpm/yarn/bun run &lt;any script&gt;, uv run &lt;anything&gt; and uvx &lt;anything&gt; from a CI run: line, so a deploy or publish step can become an active [checks] entry. Bounded by operator review of ballast.toml before trust and confined checks with a sanitized environment. Fix option: keep such lines inferred unless the target is a known verifier.
- F-002 (info, spec-ambiguity, open): Unchanged since cycle 0. A manifest description (bounded, printable, no backtick) becomes text in the generated AGENTS.md and constitution. It is the repository's own content at the same trust level, cited with its source and reviewed before commit; nothing needs doing.
<!-- ballast-findings: end -->
