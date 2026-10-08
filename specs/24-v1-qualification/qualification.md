# Qualification evidence: Ballast 1.0 request-to-PR path (#24)

This qualification ran in two passes on the qualified host: Linux with a systemd user session (`systemctl --user is-system-running`: `degraded`, user manager up), bubblewrap with user namespaces (restricted unprivileged namespaces), Git 2.53, Spec Kit CLI 1.0.11, codex-cli 0.155.1, Claude Code 2.1.290 and Ollama 0.35.1 serving `qwen3:4b-16k`. The driving agent ran both under the operator's standing authority for v1.0 issues (2026-10-05). Raw logs and pty transcripts stay on the operator's host, in this session's scratch directory, not in the repository. Every excerpt below is copied from them.

- **First pass, 2026-10-07, v0.9.0** (the CLI and pin): the full path on a blank repository and LoreForge, the UI demo, the fallback and seven recovery drills. It found four v1.0 defects (#111, #112, #114, #117), recorded from [Pilot resources](#pilot-resources) onward.
- **Final pass, 2026-10-07 22:00 to 2026-10-08 01:30 UTC, v0.10.0** (the CLI and pin): it re-ran what those fixes change. The results are in [Final pass on v0.10.0](#final-pass-on-v0100). Where the two passes differ, the final pass is the result.

## Summary (final)

| AC | Verdict | Evidence |
| --- | --- | --- |
| AC-001 blank + LoreForge reach a PR ready for human merge, both modes, one UI demo | **Pass.** | v0.10.0: blank Autonomous UI feature to Draft PR [#8](https://github.com/Hugo-Grellier/ballast-qual-blank-20261007/pull/8) with no human decision. The operator-only browser check was deferred and shows in the packet. 4 of 7 criteria were `verified` by runner-recorded checks; the 3 page criteria are `missing`, citing the deferred task. A demo was captured and linked. Blank Chat feature to Draft PR [#9](https://github.com/Hugo-Grellier/ballast-qual-blank-20261007/pull/9) with an acceptance packet, 6 of 6 criteria `verified` after `checkpoint`. LoreForge on v0.10.0: an Autonomous run of LoreForge#128 to Draft PR [LoreForge#129](https://github.com/Hugo-Grellier/LoreForge/pull/129), 5 of 5 criteria `verified` (runner-recorded). It had one safe block that resumed cleanly: verification tasks used a test command outside the allowlist ([#124](https://github.com/Hugo-Grellier/ballast/issues/124), not a 1.0 blocker). |
| AC-002 seven recovery drills recorded | **Pass.** | All seven are in the first pass. In the final pass, the tamper drill on a uv project shows the `checks-venv` warning in `doctor`, in setup and at Autonomous eligibility before any agent ran. After an induced tamper, the printed recovery command (`continue --mode chat`) works. |
| AC-003 full local gate on the qualified host | **Pass.** | `e764321` (release 0.10.0; the code is identical to `origin/main` `e7a4e8f`, which only re-pins `ballast.toml`): 1643 tests OK, **0 skipped**. Ruff check and format clean. |
| AC-004 release checklist | **Pass**, with one operator-accepted release exception. | [release-checklist.md](release-checklist.md): ruleset 24660402 is active on the default branch with no bypass. It requires `lint`, `test`, `dogfood` and `PR title`, and blocks deletion and non-fast-forward. Read with `gh api`. ADR-0001 to ADR-0016 are accepted; ADR-0017 and ADR-0018 were accepted by merge. Merge, tag and release are left to the operator. The checklist names one exception for the operator to confirm at merge: gate item 6, the free fallback ([DEC-0003](decisions.md#dec-0003-release-gate-item-6-met-as-a-qualified-mechanism-with-a-known-model-limit)). |

Each AC passes by its own wording. The independent reviewer (Codex, round 3) disagrees on two points that go beyond the wording, so #115 says `Refs #24` and leaves closing #24 to the operator: (a) gate item 6 is met only through the operator's exception DEC-0003; (b) the Chat PR bodies attribute agent-answered gates to "the operator". A comment on each pilot PR corrects (b), but Ballast's generated body is unchanged. In real use the human is at the terminal, so the attribution is right by design.

Known limits the operator accepted (2026-10-07), not blockers:

- **Free fallback (gate item 6), [DEC-0003](decisions.md#dec-0003-release-gate-item-6-met-as-a-qualified-mechanism-with-a-known-model-limit):** the gate is read as "the mechanism is qualified", not "a local model completes a step here". The mechanism works live: quota is recognized, the refusal or selection is recorded, and the attempt is confined. The selected 4B local model wrote no usable artifact. The fallback is refused while the operator's `~/.agents/skills` is not empty. See drill D6.
- **#113** (Chat step friction, PR titles) stays out of 1.0. Both v0.10.0 pilot PR titles still show it: #8 is `feat: feat(web): ...` and #9 is `feat: 5-start-value`.
- #22 SC-004 (reproduce from the packet's command) failed only because of the pilot project's own demo script (see the first pass).

Whether a gate was answered by a human: every gate answered in this qualification was answered by the driving agent after it read the artifact. That covers the `approve` commands in Chat, the gate-driver answers and the block resolutions. The Chat PR bodies say "approved by the operator" because Ballast records the terminal user as the operator. Read them as agent answers under standing authority. A comment saying so was added to each pilot PR (blank #3, #4, #9; LoreForge #127, #129). Merging stays the human decision.

## Final pass on v0.10.0

The blank repository's `main` is still pinned at v0.9.0, because the agent may not push to it. A local branch `pin-0.10` (commit `630bba3`, "chore: pin Ballast v0.10.0") carries the pin. Every final-pass feature branch was cut from it, so pilot PRs #8 and #9 include that commit. `ballast preview v0.10.0` listed the changed protected inputs, and `ballast setup` then `ballast trust` on `pin-0.10` recorded the repository as reviewed. Each feature worktree got a `.venv` (`uv venv .venv`) before `ballast trust`, because runner-recorded checks run tests with `.venv/bin/python`. `ballast doctor` reported `checks-venv: no .venv to create` there, since the blank project's checks do not use uv.

Blank-repository issues: [#5](https://github.com/Hugo-Grellier/ballast-qual-blank-20261007/issues/5) Chat, [#6](https://github.com/Hugo-Grellier/ballast-qual-blank-20261007/issues/6) Autonomous UI and [#7](https://github.com/Hugo-Grellier/ballast-qual-blank-20261007/issues/7) tamper drill. Intake `preflight` returned `eligible_leaf: true` for each, and `prepare` returned scope and ready.

### Autonomous UI feature: Issue #6, run `52a74c91`, Draft PR #8

- **First attempt, run `21b05eed`:** blocked correctly at `decide-scope`. The Issue as first written said "+1 and -1 keep working", but `main` has no -1 (it is in unmerged PR #3). The block was `Autonomous run blocked (conflict: contradiction): Issue #6 assumes the counter page already has +1 and -1 controls ...` and it offered three options. The cause was the Issue text, so the operator narrowed the criterion (option 1) and started a clean run from a fresh worktree (`6-reset-counter`).
- **Clean run:** `ballast run start --mode autonomous --wall-time 180 -i issue=6 -i idea=... -i feature_directory=specs/6-reset-counter -i integration=claude`. Every step from `preflight` through `record-final` ran with no prompt and no block, including `fix-1` to `fix-3` (idle), `converge`, `reconcile-spec` and `run-checks`. The run ended with `Draft PR: https://github.com/Hugo-Grellier/ballast-qual-blank-20261007/pull/8` and `Acceptance packet: published #8 head 931093ff2e3b`.
- **Deferral (#112, PR #121):** `speckit.tasks` tagged the browser check T002 `[DEFERRED-TO-PR]`. The run record and the PR show a `Deferred to the PR` section, and the packet's criteria rows AC-001 to AC-003 read `missing · no test named in acceptance-evidence.json · deferred to the PR: T002`.
- **Per-criterion evidence (#117, PR #122):** the record has an `Acceptance checks (runner-recorded)` section. The packet header reads `Criteria: 7 · verified 4 · failed 0 · not run 0 · stale 0 · missing 3` and `Provisional decisions: 13 · Human decisions: 0`. AC-004 to AC-007 are `verified`, "1/1 tests passed at head".
- **Reviews:** engineering, documentation, security and test were all approved, with 0 of 3 fix cycles used. GitHub checks on #8 are `PR title` and `test`, both passed. They were read with `gh pr checks 8` after the demo.
- **Demo:** `ballast run demo 52a74c91 counter-page` returned `Demo capture: captured counter-page at 931093ff2e3b: .../actions/runs/37711703693/artifacts/11522295084` and `Acceptance packet: updated #8`. The refreshed packet line reads `counter-page (Chromium 1280x720, no data): captured at 931093ff2e3b · [video](.../actions/runs/37711703693/artifacts/11522295084) · reproduce: bash demo/record.sh`.
- **Open for the human reviewer:** the deferred browser check T002, the operator's own task before merge.

### Chat feature: Issue #5, run `4b1dbb97`, Draft PR #9

Driven in a pty (private `tmux` server):

- **Gates and steps:** `approve scope` (HD-0001), `step specify`, `approve intent` (HD-0002), `step plan`, `approve plan` (HD-0003), `step tasks`, `approve tasks` (HD-0004), `step implement`, `checks` (E-0032, exit 0), `step review --kind implementation` (`Verdict: approved`), `approve implementation` (HD-0005), `step review --kind spec-reconciliation` (`Verdict: CONVERGED`), `approve spec-reconciliation` (HD-0006), `approve final` (HD-0007).
- **Operator interventions:** one message during `implement`. The agent first stopped without trying a shell command, and the operator told it to run `python3 -m unittest` as a single command. As in the first pass, the agent could not read the Issue (#113 item 2).
- **Manifest:** the agent wrote `acceptance-evidence.json`, mapping AC-001 to AC-006 to 7 unittest cases.
- **Publish (#111, PR #119):** `ballast run publish 4b1dbb97` returned `Draft PR: .../pull/9` and `Acceptance packet: published #9 head 110dc0f7e968`. The body has both the Chat section and the packet (`Run: 4b1dbb97 (chat)`).
- **Per-criterion checks:** the operator ran `ballast ledger check 4b1dbb97 AC-NNN tests...` once for each of the 7 mappings on the clean pushed checkout. Then `ballast run checkpoint 4b1dbb97` returned `Acceptance packet: updated #9 head 110dc0f7e968`, and the header reads `Criteria: 6 · verified 6 · failed 0 · not run 0 · stale 0 · missing 0`. On v0.9.0, `checkpoint` refused Chat runs.
- **CI:** GitHub checks on #9 are `PR title` and `test`, both passed.

### LoreForge (established repository): Issue #128, run `9135e30d`, Draft PR LoreForge#129

- **Re-pin**: `chore/adopt-ballast` (LoreForge#124) gained commit `4b14fe9` "chore(engineering): pin Ballast v0.10.0", pushed as a fast-forward. Then `ballast setup` and `ballast trust` ran on the adoption checkout, and `doctor` reported everything in place.
- **Intake**: Issue [LoreForge#128](https://github.com/Hugo-Grellier/LoreForge/issues/128) ("report each vault validation problem once, in a stable order"). `preflight` returned `eligible_leaf: true`, and `prepare` returned scope and ready (`Autonomous: yes`).
- **Fresh worktree** (`128-vault-issues` from `chore/adopt-ballast`): before any agent ran, `ballast doctor` reported a real-world `checks-venv` warning: `missing checks-venv uv run --locked ruff check ... creates .venv, a protected input, on an agent's first run, and this checkout has none ... fix: run uv sync --locked before ballast trust`. After `uv sync --locked`, the first `ballast run` prepared the installation (`Prepared the v0.10.0 installation ... nothing downloaded`), and `ballast trust` (2321 inputs) brought `doctor` to `Everything Ballast needs is in place`. The tamper that ended the first pass's LoreForge run did not recur.
- **Start**: `ballast run start --mode autonomous --wall-time 240 -i issue=128 ... -i integration=claude` → `Branch sync: synchronized 128-vault-issues onto main (5ca7e8724c6f..60a668c88d6b)`.
- **One block**: `validate-implementation` → `Autonomous run blocked (unsafe uncertainty: postcondition): implementation: specs/128-vault-issues/tasks.md has pending tasks: T004, T005`. The code and tests were written. The agent's verification commands (`uv run python -m unittest ...` without `--locked`, and `git diff main -- ...`) were outside the project's `extra_allow` and were denied. The operator ran `uv run --locked python -m unittest tests.test_vault` (22 tests, OK) and checked that the test diff only adds lines, ticked T004 and T005, then ran `ballast run resume 9135e30d --ref "..."`. Filed as [#124](https://github.com/Hugo-Grellier/ballast/issues/124), without a milestone: the block is safe, names its cause and resumed cleanly.
- **End**: `Run 9135e30d: completed at step record-final` · `Draft PR: https://github.com/Hugo-Grellier/LoreForge/pull/129` · `Acceptance packet: published #129 head 6f4790f27587`. The packet reads `Criteria: 5 · verified 5 · failed 0 · not run 0 · stale 0 · missing 0` and `Provisional decisions: 12 · Human decisions: 1`; the human decision is the block resolution HD-0001. Fix cycles used: 0 of 3. GitHub checks on #129 all passed: `PR title`, `Shell and Docker lint`, `check`, and `acceptance` (LoreForge's browser and PostgreSQL acceptance job, 4m59s). #129 targets LoreForge `main`, so its diff (91 files) carries the adoption commits until LoreForge#124 merges, as in the first pass.

### Tamper drill on a uv project: Issue #7, runs `25a0408c` and `57dbb5bf`

The branch `7-uv-tests` adds `pyproject.toml` and `uv.lock` and changes `[checks]` to `uv run --locked python -m unittest discover -s tests`, with a matching `extra_allow`. It is a fresh worktree with no `.venv`.

| Step | Command | Output excerpt |
| --- | --- | --- |
| Warning in doctor | `ballast doctor` | `missing checks-venv uv run --locked python -m unittest discover -s tests creates .venv, a protected input, on an agent's first run, and this checkout has none: the run would stop as tampered` · `fix: run uv sync --locked before ballast trust` |
| Warning in setup | `ballast setup` | `warning: 'uv run --locked python -m unittest discover -s tests' creates .venv, a protected input, on an agent's first run, and this checkout has none; run uv sync --locked before ballast trust` |
| Eligibility | `ballast run start --mode autonomous -i issue=7 ...` | `ballast: refusing: not eligible for autonomous: '...' creates .venv ...; run uv sync --locked before ballast trust`, exit 2, no agent started |
| Fix | `uv sync --locked`, `ballast doctor`, `ballast trust` | `ok checks-venv no .venv to create`; 152 inputs trusted |
| Tamper | Autonomous start. 20 s into the first agent step (`decide-scope`), the operator appended a line to `.venv/pyvenv.cfg`. The warning now prevents the natural case, so the tamper was induced. | `Autonomous run blocked (unsafe uncertainty: tamper): an agent step changed protected workflow files` · `Recovery: ... delete and recreate .venv (uv sync --locked), delete BALLAST_TAMPERED, run ballast discard-runs and ballast trust. The discarded run cannot resume in Autonomous; continue it in Chat with ballast run continue RUN_ID --mode chat --reason block-resolved --ref TEXT.` · `BALLAST_TAMPERED`: `.venv/pyvenv.cfg` |
| Recovery | `rm -rf .venv`, `uv sync --locked`, `rm BALLAST_TAMPERED`, `ballast discard-runs`, `ballast trust` | `discarded local run state: removed .specify/workflows/runs (runs: 25a0408c) ... stopped the unfinished agent step and removed its marker ... A stopped Autonomous run cannot resume after this; continue it in Chat with ballast run continue RUN_ID --mode chat ...` |
| Wrong paths now name the right one | `ballast run resume 25a0408c`; `ballast run continue 25a0408c --reason block-resolved --ref ...` | Both exit 2: `... cannot resume in Autonomous ... continue it in Chat: ballast run continue 25a0408c --mode chat ...` and `... after ballast discard-runs and ballast trust only Chat continues it: ballast run continue 25a0408c --mode chat ...`. The v0.9.0 loop is gone. |
| Named command | `ballast run continue 25a0408c --mode chat --reason block-resolved --ref "..."` | `Recorded HD-0001 (block-resolution); run 25a0408c is lowered to chat and continues as Chat run 57dbb5bf.` |

### Full local gate (final)

```text
$ uv run --isolated --no-project --python 3.13 --with pyyaml python -m unittest tests/test_*.py   # at e764321
Ran 1643 tests in 2553.555s
OK
$ uvx ruff check          # on this branch, rebased on e7a4e8f
All checks passed!        (exit 0)
$ uvx ruff format --check
458 files already formatted   (exit 0)
```

`OK` with no `(skipped=N)` means that no test skipped. The `skipUnless` guards listed under the first pass's AC-003 (systemd, bwrap, Codex, Spec Kit, Git ≥ 2.41) all ran.

## First pass on v0.9.0 (2026-10-07)

The first pass's verdicts were AC-001 blocked (#111, #112, #114), AC-002 pass, AC-003 pass (1591 tests, 0 skipped) and AC-004 blocked (no ruleset). The final pass supersedes them. What follows is the first pass's record.

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

| Issue | Milestone | Found in | State (2026-10-08) |
| --- | --- | --- | --- |
| [#111](https://github.com/Hugo-Grellier/ballast/issues/111) Chat publish has no acceptance packet and checkpoint refuses Chat runs | v1.0 | P2, P4 | closed by [PR #119](https://github.com/Hugo-Grellier/ballast/pull/119); re-verified on #9 |
| [#112](https://github.com/Hugo-Grellier/ballast/issues/112) Autonomous UI features block on operator-only tasks and packets carry no per-criterion evidence | v1.0 | P1 | closed by [PR #121](https://github.com/Hugo-Grellier/ballast/pull/121) (ADR-0017); re-verified on #8 |
| [#113](https://github.com/Hugo-Grellier/ballast/issues/113) Chat step friction (hook remedy, no Issue text or discovery, start-up prompts, discard message, PR titles) | none | P2, drills | open; out of 1.0 by the operator's decision (2026-10-07) |
| [#114](https://github.com/Hugo-Grellier/ballast/issues/114) A tamper block has no working recovery path, and uv projects hit it on their first agent test run | v1.0 | P4 | closed by [PR #120](https://github.com/Hugo-Grellier/ballast/pull/120); re-drilled on #7 |
| [#117](https://github.com/Hugo-Grellier/ballast/issues/117) Autonomous runs record per-criterion checks from the agent-proposed manifest (split from #112 by the coordinator, not filed here) | v1.0 | P1 | closed by [PR #122](https://github.com/Hugo-Grellier/ballast/pull/122) (ADR-0018); re-verified on #8 |
| [#124](https://github.com/Hugo-Grellier/ballast/issues/124) Tasks name test commands the agent allowlist does not cover | none | final pass, LoreForge | open; not a 1.0 blocker |

Observed and not filed (minor): the ledger marks a resumed Autonomous run `out_of_order` and does not count its block resolution as manual recovery. The ledger does not join a Chat continuation to its Autonomous parent. An ignored `.specify/.workflow-install.lock` left by v0.1.0 stops setup from recording a baseline after the upgrade. `ballast init` infers `pytest` for a stdlib-unittest project. The failed-setup "Next" line mentions network for a missing tool.

## Operator interventions and time

| Pilot | Elapsed | Interventions |
| --- | --- | --- |
| P1 Autonomous | 13:21 to 13:43 (22 min), demo +3 min | 1 (block resolution after a manual browser check) |
| P2 Chat | 13:22 to 13:54 (32 min) | 10 approvals; 2 `!` evidence commands; 1 out-of-step edit; Issue text pasted twice |
| P4 LoreForge | 14:00 to 14:42 (42 min) | tamper recovery; Chat continuation with 7 approvals; operator `pnpm install` and `generate-api`; operator `scripts/check` and `scripts/verify` |

## Pilot side effects to clean up (operator)

The private repository `Hugo-Grellier/ballast-qual-blank-20261007` holds the drill branch `main-next`, the first-pass PRs #3 and #4, the final-pass PRs #8 and #9, and Issues #5 to #7 (plus the unpushed local branches `pin-0.10`, `6-reset-page` and `7-uv-tests` with the Chat run `57dbb5bf`). Its default branch is `main` again. LoreForge holds Issues #126 and #128, PRs #127 and #129, and the pin commits `441933c` (v0.9.0) and `4b14fe9` (v0.10.0) on `chore/adopt-ballast`. The local checkouts are in the operator's pilot directory and the LoreForge adoption worktree. The agent deleted nothing.
