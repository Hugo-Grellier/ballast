# Ballast run token cost against a sandboxed Ralph loop

Investigation for [#156](https://github.com/Hugo-Grellier/ballast/issues/156), run on 2026-10-13 with Ballast v1.0.0 pinned in LoreForge. Risk R0: measurement and documentation only. Nothing in the launcher, the sandbox or the headless-agent permissions changed.

## Question

For R0/R1 work with explicit acceptance criteria, does a Ralph loop run inside Ballast's confinement deliver a mergeable PR for materially fewer tokens than an Autonomous run?

## Method

**Issues.** LoreForge [#126](https://github.com/Hugo-Grellier/LoreForge/issues/126) (an unauthenticated health and version probe; R1, three acceptance criteria) and [#128](https://github.com/Hugo-Grellier/LoreForge/issues/128) (deduplicated vault validation errors; R1). Both had an approved scope record with `Autonomous: yes`. Every run started from LoreForge `main` at `bcd1ff0`, in its own worktree, after `uv sync --locked`, `ballast setup` and `ballast trust`.

**Ballast arm.** `ballast run start --mode autonomous -i issue=N … -i integration=claude`, unchanged.

**Ralph arm.** A throwaway harness, kept outside every tracked path, that imports the worktree's installed `.ballast/spec_workflow` modules and calls them as they are:

- each iteration runs `claude -p PROMPT` with the same `permission_args`, the same allow and deny lists, `confined_argv` (bwrap) and `confined_env` as an Autonomous step;
- the prompt is the Issue title and body plus loop rules: read `.ralph/progress.md` and the last gate output, make the smallest complete change with tests, then write `DONE` or `CONTINUE` to `.ralph/status`;
- the loop stops when the agent writes `DONE` and the `[checks]` commands from `ballast.toml` pass, run confined with a read-only checkout;
- the cap was 8 iterations;
- the harness commits, pushes and opens a Draft PR outside the sandbox, as Ballast's publisher does, because the agent cannot commit or push in either arm.

Neither arm pins a model, so both used the Claude CLI default.

**Measurement.** `ballast run` records no token usage for Claude steps. Only the Codex local fallback sums usage, in `fallback.py`. Transcripts are not usable either: each confined step gets a throwaway `~/.claude` overlay, so its session log disappears when the step ends. Instead, both arms ran with Claude Code's OpenTelemetry export (`CLAUDE_CODE_ENABLE_TELEMETRY=1`, OTLP HTTP/JSON) pointed at a small standard-library collector on localhost, one port per run. These variables are not secret-named, so `confined_env` passes them through, and the sandbox shares the host network. Every `api_request` event carries input, output, cache-read and cache-write tokens, an estimated cost and a duration. The events were matched to Ballast steps using each step's `started_at`/`finished_at` in `.specify/workflow-state/RUN/agents/*/meta.json`.

`cost_usd` is Claude Code's list-price estimate. On a subscription it stands in for quota consumed, not money spent.

## Results

### #126: health probe

| | Ralph loop | Ballast Autonomous | Ratio |
| --- | ---: | ---: | ---: |
| Estimated cost (USD) | 1.25 | 14.09 | 11.3× |
| API requests | 49 | 253 | 5.2× |
| Output tokens | 18,400 | 173,757 | 9.4× |
| Cache-read tokens | 1,499,831 | 8,385,298 | 5.6× |
| Cache-write tokens | 72,692 | 1,117,160 | 15.4× |
| Uncached input tokens | 98 | 506 | |
| Agent sessions | 2 iterations | 24 steps | |
| Agent time | 215 s | 2,085 s | 9.7× |
| Elapsed, start to Draft PR | 4 min 7 s | about 37 min | 9× |
| Operator interventions | 0 | 1 | |
| Draft PR | [LoreForge#146](https://github.com/Hugo-Grellier/LoreForge/pull/146) | [LoreForge#147](https://github.com/Hugo-Grellier/LoreForge/pull/147) | |

The Ballast figures include $1.53 of rework that my intervention caused (see below). Without it, Ballast cost $12.56, still 10× the Ralph loop.

Ballast cost by stage:

| Stage | Steps | USD | Share |
| --- | --- | ---: | ---: |
| Scope and discovery | decide scope, discover | 0.93 | 7% |
| Specification | specify, clarify, decide intent | 1.10 | 8% |
| Plan | plan, review plan, decide plan | 1.59 | 11% |
| Tasks | tasks, analyze, decide tasks | 1.86 | 13% |
| Implementation | implement | 0.75 | 5% |
| Rework after the operator fix | analyze, decide tasks, implement (again) | 1.53 | 11% |
| Review and fix cycle | review, specialists, fix, two rechecks | 4.25 | 30% |
| Close-out | resolve, converge, reconcile, decide final | 2.08 | 15% |

The implementation step itself cost $0.75 (+$0.48 on its rerun), about what the whole Ralph loop cost. The remaining 90% went to the workflow around it. Cache reads dominate in both arms: each Ballast step is a fresh session that reloads the Issue, policies, skills and artifacts. Cache writes per step were 16k to 98k tokens, and that is the part the Ralph loop avoids by running two sessions instead of 24.

**The intervention.** Neither worktree had `web/node_modules`, and the confined agent may not run `pnpm install`. `./scripts/generate-api` therefore failed in both arms.

- Ballast stopped at `validate-implementation` with task T012 left open and exact recovery instructions. I installed the web dependencies outside the sandbox, ran the generator, ticked T012 and resumed. Because `tasks.md` had changed during the block, the resume reran `analyze`, `decide-tasks` and `implement`.
- The Ralph agent wrote the generated TypeScript client by hand and noted it in its progress file. Its output matches the generator's output in the Ballast worktree except for the docstrings, which come from each arm's own Pydantic model; `index.ts` and `sdk.gen.ts` are identical byte for byte.

### #128: vault validation errors (stale Issue)

LoreForge #128 was already delivered on `main` by PR #138 (commit `5c184da`) but was still open.

- **Ballast**: blocked at `decide-scope` after 30 s and $0.25. It named the earlier PR and its feature directory, and offered three options: close the Issue, rerun deliberately, or file the remaining gap.
- **Ralph**: ran one iteration ($0.22), found nothing to change, wrote `DONE`, and passed the gate on an unchanged tree. The harness then failed on an empty commit, and no PR was opened. Nothing told the operator why.

Cost was the same. Only Ballast told a human that the Issue was stale.

## PR quality (#126)

Rubric: CI and local gate green; each acceptance criterion met with a test; edits a human would need before merging; scope discipline; review trail.

| Criterion | Ralph #146 | Ballast #147 |
| --- | --- | --- |
| Local gate | Green on iteration 2 | Green |
| CI (`check`, `acceptance`, lint, PR title) | 4/4 pass | 4/4 pass |
| AC1 unauthenticated success with version | Met, tested | Met, tested |
| AC2 no database, no campaign or user data | Met; one test asserts that no vault or session directory is created | Met; tests also cover a forged session cookie and the mounted web client |
| AC3 tests and published API description | Met; regenerated OpenAPI and client | Met; regenerated OpenAPI and client |
| Human edits needed before merge | None found | None found in code |
| Code and test size | 7 files, +162 (route +14, tests +64) | 7 code files, +282 (route +22, tests +177), plus 19 feature artifacts, +1,403 |
| Robustness | Reads the version at import time with no fallback; acceptable because the Dockerfile installs the package | Falls back to `unknown` without package metadata |
| Review trail | None: progress notes outside Git | Spec, plan, decisions, five reviews, convergence, acceptance packet |
| Open findings | Not reviewed | Two low findings left open (HEAD with the web client mounted returns 404; one missing `Set-Cookie` assertion), recorded as decision D-001 for the human |

Both PRs are mergeable as they stand. Ballast's reviews found nothing that Ralph's PR gets wrong. They tightened edge cases (HTTP methods, the mounted static client, forged cookies) and documented one spec ambiguity. Those are real but marginal for an R1 liveness route.

## Findings

1. On a small, well-specified R1 feature, a Ralph loop inside Ballast's confinement reached an equally mergeable PR for about 1/11 of the tokens and 1/9 of the elapsed time. The hypothesis holds for this case.
2. Ballast's cost is ceremony, not implementation. About 30% goes to the review and fix cycle and 15% to close-out, steps that duplicate parts of CI for R1 work. The plan and tasks stages cost more than implementation.
3. Ballast's guarantees showed twice where Ralph's did not:
   - the scope step caught a stale Issue for $0.25, where the Ralph loop declared success on an empty change;
   - when the environment was incomplete, Ballast failed closed with a recovery path, where the Ralph agent hand-wrote generated code, which happened to match the generator.

   The first guarantee is cheap and worth keeping on any route. The second is a trade-off: in other conditions, the hand-written code could have been wrong while still passing CI.
4. Confinement is not what makes Ballast expensive. The Ralph loop ran under the same bwrap, permissions and environment filtering.
5. Per-step token accounting is missing from the run record. This investigation had to rebuild it from OpenTelemetry.

**Limits.** One feature and one stale Issue (n = 1 for the cost comparison). The same provider wrote and reviewed. The four runs partly overlapped, which may have affected wall time but not tokens. The Ralph prompt was written once and never tuned.

## Recommendation

Add a risk-routed lean path for R0/R1 Issues with explicit acceptance criteria; keep the full workflow for R2, unclear intent, and anything the scope step does not classify as lean. The lean path would be:

- keep `decide-scope` (it caught the stale Issue cheaply);
- run one implementation loop with Ralph-style iteration under the existing confinement, stopping on the confined `[checks]` plus an explicit done claim;
- run one review step;
- publish through the existing Draft PR and acceptance packet.

No spec, plan, tasks, analyze, converge or reconcile artifacts. If the measured ratio holds, this cuts cost by roughly 70–85%. Changing what the launcher executes is R2, so it goes in its own Issue with a human decision. Before deciding, repeat the comparison on two or three more R0/R1 Issues.

Separately, record per-step token usage and wall time in the run record so that routing decisions rest on numbers. This also touches what the launcher passes to the agent, so it is R2 as well.

## Follow-up

- [#158](https://github.com/Hugo-Grellier/ballast/issues/158): risk-routed lean Autonomous path for R0/R1 (R2).
- [#159](https://github.com/Hugo-Grellier/ballast/issues/159): per-step token usage and wall time in the run record (R2).
- LoreForge #128 is already done (PR #138) and can be closed.
- LoreForge worktree setup should install `web/node_modules`. Without it, any Issue that touches the API description blocks or tempts the agent to hand-write generated code.
