# Qualification evidence: Ballast 1.0 request-to-PR path (#24)

Raw logs and pty transcripts were kept on the operator's host (scratch directory of this session), not in the repository. Every excerpt below is copied from them. Run on 2026-10-07 (times UTC) by the driving agent under the operator's standing authority for v1.0 issues (2026-10-05). The released `ballast` v0.9.0 ran from the operator's `~/.local/bin`, and the standard was pinned at `v0.9.0`. Host: Linux with a systemd user session (`systemctl --user is-system-running`: `degraded`, user manager up), bubblewrap with user namespaces (restricted unprivileged namespaces), Git 2.53, Spec Kit CLI 1.0.11, codex-cli 0.155.1, Claude Code 2.1.290, Ollama 0.35.1 serving `qwen3:4b-16k`. `ballast doctor` reported "Everything Ballast needs is in place" before the pilots.

## Summary

| AC | Verdict | Blockers |
| --- | --- | --- |
| AC-001 blank + LoreForge reach a PR ready for human merge, both modes, one UI demo | **Blocked.** All three pilot features reached a Draft PR. The UI demo was captured and linked (#22 SC-001). The promise was not met unattended. #22 SC-004 (reproduce from the packet's command) was not met as written, and LoreForge#127's browser test never ran. | [#111](https://github.com/Hugo-Grellier/ballast/issues/111), [#112](https://github.com/Hugo-Grellier/ballast/issues/112), [#114](https://github.com/Hugo-Grellier/ballast/issues/114) (all milestone v1.0) |
| AC-002 seven recovery drills recorded | **Pass.** Every drill is recorded. The partial-agent-failure drill found a recovery loop. | [#114](https://github.com/Hugo-Grellier/ballast/issues/114) (the defect it found) |
| AC-003 full local gate on the qualified host | **Pass.** 1591 tests, 0 skipped, 0 failures. Ruff is clean. | none |
| AC-004 release checklist | **Blocked.** The checklist is written. Reading the configuration shows that no required checks are enforced on `main`. | Operator action: a ruleset (R2), [release-checklist.md §3](release-checklist.md#3-github-required-checks) |

Whether a gate was answered by a human: every gate answered in this qualification was answered by the driving agent after it read the artifact. That covers the `approve` commands in Chat, the gate-driver answers and Autonomous block resolutions. The Chat PR bodies say "approved by the operator" because Ballast records the terminal user as the operator. Read them as agent answers under standing authority. Merging stays the human decision.

## Pilot resources

| Pilot | Repository and branch | Run(s) | PR |
| --- | --- | --- | --- |
| P1 Autonomous, UI | `Hugo-Grellier/ballast-qual-blank-20261007` (private), `1-undo-click`, Issue #1 | `ad58c5ee` | [#3](https://github.com/Hugo-Grellier/ballast-qual-blank-20261007/pull/3), Draft, head `c81eb735bda2` |
| P2 Chat | same repository, `2-counter-text`, Issue #2 | `8ddcf665` | [#4](https://github.com/Hugo-Grellier/ballast-qual-blank-20261007/pull/4), Draft, head `436477ec4bb2` |
| P3 fallback drill, human-gated | same repository, `5-fallback-pilot` | `7e4a0445` | none (drill) |
| Drill runs, Chat | same repository, `6-drill`, `7-drill` | `3c7fdfff`, `0840d2db` | none |
| P4 LoreForge | `Hugo-Grellier/LoreForge`, `126-health-probe` cut from `chore/adopt-ballast`, Issue [#126](https://github.com/Hugo-Grellier/LoreForge/issues/126) | Autonomous `aefcdab6`, continued as Chat `3a494e70` | [LoreForge#127](https://github.com/Hugo-Grellier/LoreForge/pull/127), Draft, head `5c6f99736172` |
| LoreForge re-pin | `chore/adopt-ballast` ([LoreForge#124](https://github.com/Hugo-Grellier/LoreForge/pull/124)) | n/a | commit `441933c` "chore(engineering): pin Ballast v0.9.0" pushed to the branch |

## AC-001: request to a PR ready for human merge

### Blank repository: adoption

| Step | Command | Outcome |
| --- | --- | --- |
| init | `ballast init --ref v0.9.0 --description "Tally: ..." --stack python` in an empty directory | 8 s. It ran `git init` and wrote `ballast.toml`, the constitution, `AGENTS.md` with its `CLAUDE.md` link and `.gitignore`. Readiness: instructions, ignored-paths, pinned-version and trust-boundary `ready`; checks `warning` ("no active [checks]", `pytest` inferred and left commented). |
| project files | (by hand) `tally/`, `tests/`, `web/index.html`, `demo/record.*`; `ballast.toml` gained `[github]`, `[checks]` (`python3 -m unittest discover -s tests`), `extra_allow` and a `[demo]` scenario `counter-page`; copy-once `ballast-demo.yml`, `pr-title.yml` and the PR template from the v0.9.0 standard | Initial commit `3fb9335`, pushed as the repository's only push to `main`, with `gh repo create --private --source . --push`. |
| trust | `ballast trust` | 132 inputs. It recorded the repository as reviewed. |
| doctor | `ballast doctor` | `setup-current: setup is stale`, because `ballast.toml` changed after init. `ballast setup` then printed "Recorded the trust baseline for 132 protected inputs: ... match the baseline you recorded with ballast trust". After that, doctor reported everything in place. |
| intake | `ballast intake --repo ... preflight 1` | It refused at first: `issue has no acceptance criteria section`. With an AC section added, `prepare --issue N --classification feature --scope-file ...` returned `{"completed": ["scope", "ready"]}` for #1 (`Autonomous: yes`) and #2. |

### P1, Autonomous (`ad58c5ee`): a UI feature to Draft PR #3

- **Start**: `ballast run start --mode autonomous --wall-time 180 -i issue=1 -i idea="Issue #1: ..." -i feature_directory=specs/1-undo-click -i integration=claude`, from a fresh worktree (see drill D1). The run printed `ballast: codex cannot start its own sandbox inside Ballast's confinement; claude takes both roles (DEC-0004)` and `review by claude (same provider: reduced independence)`.
- These steps ran with no prompt: scope decision, discovery, specify, clarify, intent, plan, plan review, tasks, analyze, implement. The implementation was correct (`Counter.decrement`, a `−1` button, 5 new tests).
- **Block**: `validate-implementation` → `Autonomous run blocked (unsafe uncertainty: postcondition): implementation: specs/1-undo-click/tasks.md has pending tasks: T004, T005, T010, T012`. `speckit.tasks` had generated tasks only an operator could do: a manual browser check and a local demo recording. → [#112](https://github.com/Hugo-Grellier/ballast/issues/112).
- **Operator intervention (1)**: the driving agent ran the page check in Chromium 154 (Playwright) and recorded it in `specs/1-undo-click/evidence/manual-page-check.md`: 5 of 5 steps passed. It resolved T005 as "requested later with `ballast run demo`", ticked the four tasks and ran `ballast run resume ad58c5ee --ref "..."`. Ballast recorded `HD-0001 (block-resolution) ... resumes in Autonomous at validate-tasks; Changed during the block: specs/1-undo-click/tasks.md`.
- **End**: `Run ad58c5ee: completed at step record-final` · `Draft PR: https://github.com/Hugo-Grellier/ballast-qual-blank-20261007/pull/3` · `Acceptance packet: published #3 head c81eb735bda2`. The packet shows: engineering, security and test reviews approved, provisional decisions PD-0001 to PD-0014 labeled agent-provisional, 0 of 3 fix cycles used, the block resolution, and checks `python3 -m unittest discover -s tests` exit 0. GitHub checks on #3: 2 of 2 passed.
- **Packet gap**: all nine criteria are `missing (no acceptance-evidence.json)`. No step writes the manifest, and the manifest cannot map the four page criteria, which have no unit test (`ledger.archive_manifest` requires every AC). → [#112](https://github.com/Hugo-Grellier/ballast/issues/112).
- **Ledger**: `ballast ledger report --run ad58c5ee` reports `compliance: incomplete_or_noncompliant` with `out_of_order: ["validate-tasks"]` (the legitimate resume point) and `human_effort.manual_recovery: 0`, although HD-0001 is a manual recovery. This is a reporting inaccuracy, listed here and not filed separately.
- **Title**: `feat: feat(web): let people undo ...`, with a doubled prefix ([#113 comment](https://github.com/Hugo-Grellier/ballast/issues/113#issuecomment-6040289625)).

### UI demo on PR #3 (#22 SC-001 and SC-004)

- `ballast run demo ad58c5ee counter-page` → `Demo capture: in progress (running) counter-page at c81eb735bda2: .../actions/runs/37630870641`, exit 0. The Actions run completed with `success` at `head_sha c81eb735...`. Steps: validate, check out, run (success), video-missing check (success), upload. Artifact `ballast-demo-7eb89bb01295dcc9`, 44 720 bytes.
- `ballast run checkpoint ad58c5ee` → packet line: `counter-page (Chromium 1280x720, no data): captured at c81eb735bda2 · [video](.../actions/runs/37630870641/artifacts/11486262521) · reproduce: bash demo/record.sh`. **SC-001: met.**
- SC-004, local reproduction without credentials, from a fresh clone at `c81eb735`: the packet's command `bash demo/record.sh` **failed on this host**: `The virtual environment was not created successfully because ensurepip is not available` (no `python3-venv`). The pinned `playwright==1.55.0` then reported `Playwright does not support chromium on ubuntu26.04-x64`. Both are portability defects of the pilot project's demo script, not of Ballast. The same journey (`demo/record.py`) with `uv run --with playwright` (1.63.0) wrote `demo-output/counter-page.webm` (90 481 bytes), exit 0, with no credentials. **SC-004: not met as written.** The packet's own command does not reproduce the journey on this host, because of the pilot project's script. Ballast reported the command faithfully. The journey itself reproduced with an adapted command and no credentials. Side effect: the failed 1.55 install removed `~/.cache/ms-playwright/chromium-1243` and `chromium_headless_shell-1243`, and the 1.63 install downloaded both again. They are present again.

### P2, Chat (`8ddcf665`): a library feature to Draft PR #4

Driven in a real pty (private `tmux` server):

| Action | Evidence |
| --- | --- |
| `ballast run start --mode chat -i feature_directory=specs/2-counter-text -i idea=...` | `Chat run 8ddcf665 (active)`; no agent started |
| `approve scope` | `Recorded HD-0001: scope approved at sha256:5c15134a...` |
| `step specify` | `Branch sync: up-to-date ...`; spec AC-001 to AC-006; the agent could not read the Issue (`gh` denied in the step) → [#113](https://github.com/Hugo-Grellier/ballast/issues/113) item 2 |
| `approve intent`, `step plan`, `approve plan`, `step tasks`, `approve tasks`, `step implement` | HD-0002 to HD-0004; implement added `Counter.__repr__` and 8 tests. The operator ran two `!` commands for evidence the agent's allowlist did not cover (`python3 -c ...`). |
| `step review --kind implementation` | `Verdict: approved` (claude, same provider) |
| `checks` | `Project checks recorded as E-0038`, 11 tests OK |
| `approve implementation`, `step review --kind spec-reconciliation` | The review step wrote `research.md`, outside its write scope, on the operator's instruction. `approve implementation` then refused: `open-write-scope (E-0053): a step changed paths outside its write scope: specs/2-counter-text/research.md; restore or change them`. An operator edit cleared it, and the PR lists it under "Changes made outside agent steps". |
| `approve final` | It refused twice, correctly: `project-checks (E-0048): ... ran on another tree`, then `implementation approval is stale (HD-0005)`. It was approved after a re-check (E-0061) and re-approvals HD-0008 to HD-0010. |
| `publish` | `Draft PR: https://github.com/Hugo-Grellier/ballast-qual-blank-20261007/pull/4`; Chat section with steps, 10 approvals (current and superseded), the review, checks and the out-of-step change. **No acceptance packet**; `ballast run checkpoint 8ddcf665` → `refusing: run 8ddcf665 is not an autonomous run` → [#111](https://github.com/Hugo-Grellier/ballast/issues/111). PR title `feat: 2-counter-text`. GitHub checks 2 of 2 passed. |

#20 pilot checks moved here (P-3 to P-5, Claude only; Codex cannot nest on this host):

| Check | Result |
| --- | --- |
| P-3 resize, Ctrl-C, `/exit`, Ctrl-] twice | **Pass.** `resize-window` to 120x40 redrew the TUI. Ctrl-C reached the agent at its prompt. `/exit` ended the step (`Step ...: completed`) and the shell prompt came back. `Ctrl-]` twice ended the plan step as `interrupted`, with its postcondition still checked. Mouse-mode state was not inspected. |
| P-4 Shift+Tab out of `dontAsk`, edit `ballast.toml`, `curl` | **Pass.** Both were denied by `chat_hook.py`: "Ballast Chat steps run in dontAsk mode, so nothing is granted by a prompt; this session is in 'default' mode. Press Shift+Tab until it is dontAsk." No permission prompt appeared. The installed Claude Code does pass `permission_mode` to the hook. **Finding:** `dontAsk` is not in Claude Code 2.1.290's Shift+Tab cycle (manual → accept edits → plan), so the remedy cannot be followed. → [#113](https://github.com/Hugo-Grellier/ballast/issues/113) item 1. |
| P-5 `/permissions` → save `Bash(curl:*)` to project settings | **Pass.** The rule showed in the session list, but no `.claude/settings.json` was written (read-only). A later `curl` was still denied by the hook outside `dontAsk`. |

Quickstart scenarios: scenario 1 (conversation, approvals, out-of-step change) and scenario 4 (evidence and publication) ran above. Scenario 3 (leave and resume: killed wrapper, base advance, `discard-runs`) ran as drills D3 and D7. Scenario 6 (Autonomous to Chat) ran on LoreForge (P4). Scenarios 2, 5 and 7 (forged approvals, mode switches, Spec Kit run to Chat) were not run live. They remain covered by the automated suite (AC-003).

### P4, LoreForge (established repository)

| Step | Command | Outcome |
| --- | --- | --- |
| state | PR #124 open, Draft, `chore/adopt-ballast` at `a847a70`, pin `v0.1.0`; LoreForge `main` had moved to `60a668c` (#125) | n/a |
| own gate on the adoption branch | `./scripts/check` | exit 0 (ruff, ty, sqlfluff, unittest, transcribe test, biome, tsc) |
| preview | `ballast preview v0.9.0` | `ballast: the cached standard v0.1.0 was damaged (.ballast-cache.json); fetched it again` (a cache from an older CLI, documented); lists added and changed paths; "Ignore rules: the current .gitignore covers every installed path" |
| re-pin | `ref = "v0.9.0"` plus `[github] repository` and confined `[checks]` (the Python gates of `./scripts/check`) | commit `441933c` pushed to `chore/adopt-ballast` (fast-forward, no force) |
| failed update | drill D2 | n/a |
| setup | `ballast setup` | installed, but `No trust baseline recorded: .specify/.workflow-install.lock was not written by setup` (an ignored leftover of the v0.1.0 install) |
| trust | `ballast trust` | 2322 inputs; LoreForge recorded as reviewed |
| intake | Issue [#126](https://github.com/Hugo-Grellier/LoreForge/issues/126) created; `preflight 126` → `eligible_leaf: true`; `prepare` → scope and ready | n/a |
| worktree | `git worktree add -b 126-health-probe ... chore/adopt-ballast`; first `ballast run` | `Prepared the v0.9.0 installation from .../LoreForge-ballast (verified, nothing downloaded)`; no baseline, because the default branch has no `ballast.toml` → `ballast trust` (133 inputs) |
| Autonomous start | `ballast run start --mode autonomous --wall-time 240 -i issue=126 ... -i integration=claude` | `Branch sync: synchronized 126-health-probe onto main (5ca7e8724c6f..60a668c88d6b)`; scope through tasks with no prompt; implement wrote the route, 9 tests and part of the regenerated API |
| block | implement | `Autonomous run blocked (unsafe uncertainty: tamper): an agent step changed protected workflow files`: the agent's allowed `uv run --locked ...` created `.venv` in the new worktree → drill D7(c), [#114](https://github.com/Hugo-Grellier/ballast/issues/114) |
| recovery | recreate `.venv` (`uv sync --locked`), remove the marker, `discard-runs`, `trust`; `resume` and `continue` refused in a loop; `ballast run continue aefcdab6 --reason block-resolved --ref ... --mode chat` | `Recorded HD-0001 (block-resolution); run aefcdab6 is lowered to chat and continues as Chat run 3a494e70`; PD-0001 to PD-0008 stay agent-provisional |
| Chat to the end | approve scope, intent, plan, tasks (HD-0001 to HD-0004); the operator ran `pnpm --dir web install --frozen-lockfile` and `./scripts/generate-api` outside the steps (network); `step implement` (T007 and T008 verified, 9 health tests run confined); `checks` (E-0016, then E-0029, all exit 0); reviews implementation, security and spec-reconciliation (`approved`, `approved`, `CONVERGED`); approve implementation, spec-reconciliation, final (HD-0005 to HD-0007) | n/a |
| full project gate (operator, outside steps) | `./scripts/check` and `./scripts/verify` | `scripts/check` exit 0 (92 Python tests OK, 46 PostgreSQL tests skipped without a test database); `scripts/verify` exit 0 (web build; 2 Playwright tests passed, `campaigns.spec.ts` and `jobs.spec.ts`). The agent's new `web/tests/health.spec.ts` is selected by no project in `web/playwright.config.ts`, so it never ran. The probe's evidence is the 9 ASGI tests in `tests/test_health.py`. This is a feature defect in LoreForge#127, noted on the PR ([comment](https://github.com/Hugo-Grellier/LoreForge/pull/127)) for the human reviewer.; `./scripts/generate-api` run twice gives identical output |
| publish | `ballast run publish 3a494e70` | [LoreForge#127](https://github.com/Hugo-Grellier/LoreForge/pull/127), Draft, no acceptance packet (#111) |

Notes:

- #127's base is `main` (Ballast always targets the repository default branch), so its diff carries the adoption commits as rebased by the start-time sync: 94 files. Once #124 merges, the diff shrinks to the feature. Stacked PRs onto a non-default base are not supported. This is a design limit, not filed.
- LoreForge's real PostgreSQL tests did not run (no test database configured on this host). The feature touches no database, but this is an unavailable check for LoreForge's full gate and is named here.
- `ballast ledger report --run 3a494e70` lists `specify`, `plan` and `tasks` as missing, because they ran in the Autonomous run `aefcdab6` that this Chat run continues. The report does not join the two runs.

## AC-002: recovery drills

| ID | Drill | Command | Output excerpt | Outcome |
| --- | --- | --- | --- | --- |
| D1 | Fresh worktree | `git worktree add -b 1-undo-click .../blank-1 main`; first `ballast run start ...` | `Prepared the v0.9.0 installation from .../blank (verified, nothing downloaded).` `Recorded the trust baseline for 133 protected inputs: ... match Hugo-Grellier/ballast-qual-blank-20261007's default branch main at 3fb933530e05.` | Pass, with no setup, download or trust. Repeated for `blank-fb`, `blank-d`, `blank-d7`. On LoreForge (`lf-126`) preparation worked, and trust was correctly required because the default branch differs. |
| D2 | Failed update | (1) LoreForge v0.1.0 → v0.9.0 with `uvx` absent from `PATH`: `ballast setup`. (2) Logged rerun with a preservation check, on a fresh clone of the blank repository: setup at v0.9.0, commit a pin change to v0.8.1, `ballast setup` without `uvx`, then with it | (1) `setup: spec-kit failed: Required setup tool is missing: uvx; run ballast doctor for details. The previous installation was kept. Next: check network access (ballast doctor), then rerun ballast setup` (exit 1). (2) Same message, `setup exit=1`; installed version and a SHA-256 digest of every file under `.ballast`, `.specify` and `.agents` identical before and after the failure (`1a63665b4f6fe65f`); `ballast doctor`: `missing uvx` and `setup-current: setup is stale: pinned v0.8.1, installed v0.9.0; restore ref = "v0.9.0" in ballast.toml, or fix the cause and rerun ballast setup`; the retry installed v0.8.1 and asked for `ballast trust` | Pass. The previous installation is byte-identical after the failure, and the retry completes the update (here a rollback to v0.8.1). Minor wording: the "Next" line says network for a missing tool. |
| D3 | Stale resume | Chat run `0840d2db` started while `main-next` was the default branch, so its pinned base is `main-next`. The default was set back to `main`, `main-next` advanced (`a61240e`), then `ballast run step 0840d2db specify` | `Branch sync: synchronized 7-drill onto main-next (40f38ac97287..a61240ee583d), HEAD 40f38ac97287 -> a61240ee583d` before the agent started | Pass. Logged rerun (`script`, after the base gained `2f952180154c`): `Branch sync: synchronized 7-drill onto main-next (b490c5d0dfae..2f952180154c), HEAD 2b5e5fa9674f -> 2a5463f79bb8`, before the agent started. Also seen live on LoreForge: `synchronized 126-health-probe onto main (5ca7e8724c6f..60a668c88d6b)` at start. The base-advance setup used a second branch ([DEC-0002](decisions.md#dec-0002-base-advance-drills-use-a-second-branch-of-the-disposable-repository)). |
| D4 | Merge conflict at sync | A feature commit and a base commit edit the same README line; `ballast run step 0840d2db specify` | `BLOCKED_UPSTREAM_SYNC (conflict): replaying 4d62f024ed48 conflicts in README.md` · `Recovery: rebase by hand: git pull --rebase origin main-next, resolve, then ballast run step 0840d2db specify` · `refusing: branch synchronization blocked (conflict)` | Pass. No agent started, and the tree was left at `4d62f02`. After the prescribed manual rebase: `Branch sync: up-to-date 7-drill with main-next (b490c5d0dfae)` and the step ran. Logged rerun: `BLOCKED_UPSTREAM_SYNC (conflict): replaying 4d38c3c8a380 conflicts in README.md`, the same recovery line, `COMMAND_EXIT_CODE="1"`. |
| D5 | Fetch failure | `GIT_SSH_COMMAND="ssh -o ConnectTimeout=2 -p 9" ballast run step 3c7fdfff specify` | `BLOCKED_UPSTREAM_SYNC (fetch-failed): could not fetch main from Hugo-Grellier/ballast-qual-blank-20261007` · `Recovery: check network access and credentials ... then ballast run step 3c7fdfff specify` | Pass. No agent started. Logged rerun against the run's pinned base: `BLOCKED_UPSTREAM_SYNC (fetch-failed): could not fetch main-next from Hugo-Grellier/ballast-qual-blank-20261007`, exit 1. |
| D6 | Provider fallback | A human-gated run with `--local-fallback qwen3:4b-16k`. A stand-in `claude` early on `PATH` prints `Claude AI usage limit reached\|...` and exits 1. | (a) `local fallback refused: permission-mismatch: user skills directory is not empty`, because the operator's `~/.agents/skills` holds personal skills. Ledger `route`: `failure_cause: quota-exhausted`, `fallback: refused`, `fallback_reason: permission-mismatch`. (b) Resumed with `HOME` set to a directory without user skills (XDG and `gh` paths kept): `local fallback: running this step once on ollama qwen3:4b-16k (quota-exhausted)`. Ledger: `fallback: selected` and attempt 2 `provider: ollama, model: qwen3:4b-16k, route_source: fallback, outcome: success`. After about 35 minutes on CPU the model printed the brief instead of writing it, so the step failed its postcondition: `workflow contract failed [discovery]: specs/5-fallback-pilot/discovery.md is missing`. | Pass as a drill. Recognition, refusal, selection, confinement and ledger evidence work live. **Not a demonstration of a usable fallback**: the selected local model did not produce a valid artifact, and with the operator's real home the fallback is always refused (`~/.agents/skills` is not empty). This meets #23 SC-004 ("completes or is refused with a recorded cause"). Roadmap gate item 6, "qualified as a recoverable fallback", has no live completion on this host. The release checklist lists it for the operator's decision. |
| D7 | Partial agent failure | (a) `kill -9` of the `ballast run step 0840d2db specify` wrapper during the step | `ballast run status` → `refusing: an agent step is active or did not finish: run 0840d2db, step ...; ... run ballast discard-runs`; after `discard-runs`, `Step ...: interrupted (closed after its wrapper ended)` and the run continued. `discard-runs` printed `start a fresh run`, which is misleading for Chat (#113 item 4). A logged rerun gave the same three outputs (step `20261007T145543022721Z-specify-claude`), and no confined agent process remained afterwards. | Pass |
| | | (b) Implement left operator-only tasks open (P1) | `validate-implementation` block with class, reason and `Next: ballast run resume ad58c5ee` | Pass. The recovery worked (#112 covers the cause). |
| | | (c) Implement created `.venv` (P4) | Tamper block with the full path list and recovery text. After that recovery, `resume` → `stopped on a tamper block; recover with ballast discard-runs` (again after discard), and `continue` → `stopped before implementation; resume it in Autonomous` | **Defect**: recovery loop. Only `continue --mode chat` worked → [#114](https://github.com/Hugo-Grellier/ballast/issues/114) |

## AC-003: full local gate on the qualified host

Commit `69f5602` (release 0.9.0, `origin/main`), this worktree:

```text
$ uv run --isolated --no-project --python 3.13 --with pyyaml python -m unittest tests/test_*.py
Ran 1591 tests in 2463.802s
OK
real 41m5.106s
$ uvx ruff check
All checks passed!
$ uvx ruff format --check
447 files already formatted        (ruff 0.16.10)
```

Rerun before the PR, on the branch with this feature directory: `uvx ruff check` → `All checks passed!` (exit 0); `uvx ruff format --check` → `452 files already formatted` (exit 0). The file count includes every file ruff discovers, not only Python sources.

**Skipped: 0.** `OK` with no `(skipped=N)` means that no test skipped, including every `skipUnless` guard that CI skips: `test_branch_sync.SyncCase`/`Sha256Tests` (Git ≥ 2.41); `test_chat_mode` real-bwrap tests (`test_real_bwrap_keeps_protected_and_operator_paths_out_of_reach`, `..._keeps_installed_skills_read_only`, `..._hides_earlier_step_logs`, `test_operator_records_are_out_of_reach_under_real_bwrap`, and the bwrap and systemd step-close test); `test_spec_workflow.ScopeContainmentTests` (systemd), the Codex and systemd class, `EngineRunTests` and `EngineRepositionTests` (Spec Kit CLI), the Spec Kit, systemd and bwrap class, and the Codex, bwrap and restricted-userns class; `test_autonomy.RealConfinementTests` (bwrap). The prerequisites were present: `specify` 1.0.11 and `codex` 0.155.1 on `PATH`, a running systemd user manager, and a working `bwrap`. No mandatory check was unavailable.

## AC-004: release checklist

[release-checklist.md](release-checklist.md) links every v1.0 issue (read with `gh api`), its spec and ADR, and the three v1.0 issues filed here. It reads GitHub's configuration: `rulesets: []`, `rules/branches/main: []` and `branches/main/protection: 404 Branch not protected`. So **no required check is enforced on `main`**, which fails roadmap gate item 5. The checklist names the ruleset to add (`lint`, `test`, `dogfood`, `PR title`) as an R2 operator action. It also notes that ADR-0006 to ADR-0016 still read `proposed` although their PRs merged. Merging, the `v1.0.0` tag and the release are left to the operator.

## Issues filed

| Issue | Milestone | Found in |
| --- | --- | --- |
| [#111](https://github.com/Hugo-Grellier/ballast/issues/111) Chat publish has no acceptance packet and checkpoint refuses Chat runs | v1.0 | P2, P4 |
| [#112](https://github.com/Hugo-Grellier/ballast/issues/112) Autonomous UI features block on operator-only tasks and packets carry no per-criterion evidence | v1.0 | P1 |
| [#113](https://github.com/Hugo-Grellier/ballast/issues/113) Chat step friction (hook remedy, no Issue text or discovery, start-up prompts, discard message, PR titles) | none (operator may promote item 2) | P2, drills |
| [#114](https://github.com/Hugo-Grellier/ballast/issues/114) A tamper block has no working recovery path, and uv projects hit it on their first agent test run | v1.0 | P4 |

Observed and not filed (minor): the ledger marks a resumed Autonomous run `out_of_order` and does not count its block resolution as manual recovery. The ledger does not join a Chat continuation to its Autonomous parent. An ignored `.specify/.workflow-install.lock` left by v0.1.0 stops setup from recording a baseline after the upgrade. `ballast init` infers `pytest` for a stdlib-unittest project. The failed-setup "Next" line mentions network for a missing tool.

## Operator interventions and time

| Pilot | Elapsed | Interventions |
| --- | --- | --- |
| P1 Autonomous | 13:21 to 13:43 (22 min), demo +3 min | 1 (block resolution after a manual browser check) |
| P2 Chat | 13:22 to 13:54 (32 min) | 10 approvals; 2 `!` evidence commands; 1 out-of-step edit; Issue text pasted twice |
| P4 LoreForge | 14:00 to 14:42 (42 min) | tamper recovery; Chat continuation with 7 approvals; operator `pnpm install` and `generate-api`; operator `scripts/check` and `scripts/verify` |

## Pilot side effects to clean up (operator)

The private repository `Hugo-Grellier/ballast-qual-blank-20261007` holds the drill branch `main-next` and PRs #3 and #4. Its default branch is `main` again. LoreForge holds Issue #126, PR #127 and the pin commit on `chore/adopt-ballast`. The local checkouts are in the operator's pilot directory and the LoreForge adoption worktree. The agent deleted nothing.
