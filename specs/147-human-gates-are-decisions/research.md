# Research: Human gates are decisions, not command relays

Phase 0 decisions for [plan.md](plan.md). Every decision here is agent-provisional (Autonomous run `2e651132`); merging the PR is the only human approval (BL-INV-006). D-01 to D-05 are settled in the [discovery brief](discovery.md) from the Issue body and the operator's block resolution HD-0002. D-06 and D-07 are the agent-provisional assumptions PD-0002 and PD-0003. D-08 is the operator's resolution of plan-review F-001 (HD-0003, recorded on Issue #147). This file decides only how to implement them within the boundary that [spec.md](spec.md) sets.

No NEEDS CLARIFICATION remained in the Technical Context. R1 to R14 record the design choices and the alternatives rejected. Code references are to the current tree.

## R1. Where the automatic refresh runs: before the launcher, as a setup subprocess

- **Decision**: The global `ballast` command (`tools/ballast`) refreshes before it executes the launcher for `run`, `ledger` and `intake`. It asks the launcher's `status --json`, which writes nothing. When the refusal is a protected-input change, or a pin that differs from the installation, and the pinned standard declares `[setup] refresh = true` in `tools/cli.toml`, it does three things:
  - fetches the pinned standard through the existing `ensure_standard` path from the fixed source;
  - runs `python3 -IS <standard>/tools/setup --project ROOT --refresh` as a subprocess, the same way it runs worktree preparation (`prepare`, `tools/ballast:1884`);
  - then executes the launcher as today.

  `setup --refresh` takes the exclusive checkout lock, decides eligibility (R2) before it installs anything, regenerates the installation from the current `ballast.toml` through the existing `attempt()` path, and records the baseline only after a verified re-snapshot (R4). If it is not eligible it changes nothing and prints one line of reasons. The launcher then refuses exactly as today, naming `ballast trust`.
- **Rationale**:
  - The launcher runs from the standard that the checkout's `ballast.toml` pins. After a pin change, only `tools/ballast` can download that standard, and only setup can replace `.ballast/spec_workflow` while nothing runs from it.
  - Setup already owns the exclusive lock, the journal, the installation record and `setup_trust`. Reusing it keeps one writer for each artifact.
  - The launcher's comparison before every command stays byte-for-byte the same check (FR-003, FR-020).
- **Compatibility**: an older global CLI, or a pinned standard without the declaration, never refreshes and behaves as today. `ballast self-install` brings the new CLI. The docs say so.
- **Alternatives considered**:
  - Refresh inside the launcher: it cannot download a newly pinned standard, and it would gain network and Git transport that `status --json` probes would load.
  - Refresh inside `run.py` after branch synchronization: `run.py` executes from `.ballast/spec_workflow`, which the regeneration replaces, and it holds the shared lock that setup needs exclusively.
  - `tools/ballast` running the launcher as a child to loop once after a refresh: this adds signal and terminal handling to R2 code for one saved command (see R3).

## R2. Refresh eligibility (FR-001, FR-003, AC-002, AC-005, AC-006)

- **Decision**: A new `setup_trust.refresh(root, state, *, standard)` checks the conditions below in order, reporting the first that fails and reaching the network last. Every failure means "not eligible", changes nothing, and leaves the launcher's `ballast trust` refusal in place.
  1. The standard lies outside the checkout. No `BALLAST_TAMPERED` marker or `in-progress` marker exists (AC-006).
  2. A baseline exists, and its provenance names a repository (R5).
  3. The current `ballast.toml` pins the same `[github] repository`, case-folded. That repository is in the machine's reviewed-repositories record (AC-005). A legacy baseline without a named repository is not eligible, and one `ballast trust` populates it.
  4. The changed set is the baseline compared with the current inputs. Every changed path falls into one of three groups:
     - (a) a file that setup installs. This is the `.ballast/spec_workflow` tree and every installed path under `.specify`, the same split `_check_installation` uses. It is attributed by the regeneration in R4.
     - (b) a regular file tracked at `HEAD` and unchanged from `HEAD`, with the hardened local plumbing of `_check_committed`. It is attributed by the observation in step 6.
     - (c) anything else, for example `.venv`, an untracked or uncommitted file, or a link. Such a path is not attributable, so the checkout is not eligible (AC-002).
  5. The checkout holds no `in-progress` marker (checked again under the lock). Saved run state is allowed: it is outside the baseline (`SKIPPED`), and the wrapper checks it around every agent step. This differs from ADR-0015's fresh-checkout path, which never runs mid-feature.
  6. The default branch is observed through `_observe` on ADR-0015's trusted path: the throwaway repository, `ls-remote --get-url` refusal of an `insteadOf` rewrite, `ls-remote --symref`, a depth-1 blob-less fetch, and the 30 s and 120 s bounds. `ls-tree` lists every path in group (b), not only the two configuration files. Every one must be a regular-file entry whose blob ID equals the local bytes. Any failure is "unobservable", which makes the checkout not eligible (AC-006).
- **Rationale**: This is D-02 option A as the operator resolved it: the live default branch of a reviewed repository counts as reviewed for any bytes. The ADR-0015 refusals the resolution keeps still apply: a repointed repository, an unobservable branch, the markers, and the trusted path. Steps 2 and 3 make "same repository as the reviewed baseline" the anchor, so a repointing commit inherits nothing even when it points at another reviewed repository.
- **Narrowing, listed for merge review**:
  - The any-bytes rule applies only to refreshing an existing baseline whose provenance names the same repository. ADR-0015's fresh-checkout path keeps its reviewed-pair check (SEC2-001).
  - `.venv` changes are never attributable. A merged `uv.lock` change followed by `uv sync` still needs `ballast trust`, which is stated as a residual gap in the ADR.
- **Alternatives considered**:
  - Accept any reviewed repository the new `ballast.toml` names: a commit could repoint to another reviewed repository with unreviewed bytes there.
  - Compare only `ballast.toml` and the constitution: other committed `.specify` files would still force a trust.
  - Read the local `refs/remotes/origin/*`: it is agent-writable (ADR-0015, rejected).

## R3. Branch synchronization that brings a protected-input change (FR-002, D-05)

- **Decision**: The ADR-0005 recheck after a HEAD move is unchanged: a protected-input difference still stops the invocation before any agent step, and the synchronization is kept (E-03). Only the recovery text changes. It names the same `ballast run` command again (`resume RUN`, `step RUN PHASE`, or a new `start`), which the operator's agent session may run. The note says the next invocation refreshes trust and the installation from the default branch automatically when R2 holds, and otherwise names `ballast trust`. The current "run `ballast setup` first, then `ballast trust`" text goes. When the stop happens at start, the existing upstream-sync restart rule applies.
- **Rationale**: The refresh must run before the launcher (R1), and the invocation that synchronized is already past it. One rerun of the same command keeps every check in place, carries no decision, and is agent-runnable. SC-001 counts operator `trust` and `setup` commands, and both reach zero.
- **Alternatives considered**: An in-process refresh (rejected in R1); a launcher-level re-exec after closing inherited lock descriptors (fragile lock handling in R2 code).

## R4. Regeneration and the recorded baseline (FR-002, FR-004, AC-001, AC-004)

- **Decision**: When R2 holds, `setup --refresh` runs the normal installation path for the current `ballast.toml` and pin: `attempt` → `build` → `validate` → `switch` → `finish`. The fingerprint already covers the `ballast.toml` bytes, so a configuration change is always a full regeneration, including `claude-settings.json`. A failed attempt goes through the existing journal and recovery, records no baseline, and the launcher refuses with `UNFINISHED` ("run `ballast setup`"). That is the one combined fix of the spec's edge case.

  After `finish`, setup takes one snapshot. Recording requires all four:
  - every installed entry equals the new installation record;
  - every entry in group (b) still equals its observed blob;
  - every other entry equals the previous baseline;
  - the generated agent settings equal `launcher.generated_settings(...)` for the current `ballast.toml` (R6).

  The baseline is then written through `launcher.record_baseline(source="default-branch", reference={repository, branch, commit})`, re-snapshotted, and restored on any difference, exactly as `setup_trust._record` does. Setup prints `refreshed the trust baseline from <repository> <branch> at <commit>`. The launcher's `status --json` reports `baseline_source: "default-branch"` and the commit. `ballast run` repeats the line once after a refresh, read from the provenance, so the run output names it (AC-001).

  The refresh also adds the new (`ballast.toml`, constitution) pair to the reviewed record for that repository, so later fresh worktrees of the same default-branch configuration need no `ballast trust` either.
- **Rationale**:
  - One installation path means one writer.
  - Recording after the regeneration means the baseline describes the installed bytes.
  - Adding the pair is the consequence of option A for ADR-0015's fresh-checkout path. Without it the next new worktree would need a trust for configuration that is already accepted.
- **Alternatives considered**: Regenerate only `claude-settings.json`. Other installed files follow the pin and the fingerprint, and a partial regeneration would be a second installer.

## R5. Provenance gains the repository and the default-branch source

- **Decision**: `trusted-source.json` stays schema 1 and gains two additive things:
  - `repository`, written by `ballast trust` (from the trusted `ballast.toml`), by setup (from its reference) and by the refresh;
  - a third `source` value, `default-branch`, with `reference = {repository, branch, commit}`.

  `baseline_source` returns `trust`, `setup` or `default-branch`. A missing, unreadable or unbound record reads as `trust`, as before. `operator_baseline` still accepts only `trust`, so ADR-0015's operator-baseline alternative is unchanged. The comparison never reads provenance (ADR-0015).
- **Rationale**: R2 needs the reviewed repository of the current baseline, and the digest-only `trusted.json` cannot say it. Keeping it in the provenance, which the comparison never reads, leaves the comparison format alone.
- **Alternatives considered**: A field inside `trusted.json` (rejected by ADR-0015: it changes what the comparison reads); re-deriving the repository from the old `ballast.toml` bytes (they are not stored).

## R6. Trust refuses generated settings that differ from `ballast.toml` (FR-004, AC-003)

- **Decision**:
  - `merge_permissions` moves from `tools/setup` (`:1566`) to `launcher.py`, and setup imports it from its standard.
  - A new `launcher.generated_settings(standard_dir, config) -> bytes` returns the exact bytes setup writes: the standard's `claude-settings.json` merged with `[agents.permissions]`, `json.dumps(..., indent=2) + "\n"`.
  - `_trust` reads `ballast.toml` once with `read_config` and compares `.ballast/spec_workflow/claude-settings.json` with that result, using the base file of the pinned standard the launcher runs from (the same ref as the installation, guaranteed by `_setup_refusal`). A difference refuses with: `generated agent settings differ from ballast.toml; run ballast setup, review, then ballast trust`. No baseline is written and the reviewed record is untouched.
  - A malformed `[agents.permissions]` refuses too.
  - The refresh uses the same function (R4).
- **Rationale**: `claude-settings.json` is the only installed file whose content depends on `ballast.toml` beyond the pin. Codex receives its sandbox as `-c` flags, and Chat writes per-step copies at step time. A test enumerates the installed files and asserts this, so a later config-derived file fails it. Byte comparison against the producer's own function means the two cannot drift.
- **Alternatives considered**:
  - Compare the installation fingerprint: the launcher would need setup's fingerprint inputs, which are the whole standard tree.
  - Add a config digest to `installation.json`: a second source of truth for what the settings already show.

## R7. Who did it: operator at a terminal, or a relaying agent session (FR-010, FR-011)

- **Decision**: One rule, in a new trusted helper `actor.py` (standard library only, imported by `run.py` and `chat.py`), decides the actor of every operator-state record that today says `by: "operator"`. Those are human decisions (`HD-NNNN`) and mode-history entries.
  - If `--relayed-by SESSION` is given, the actor is `relayed` and the session is recorded. `SESSION` must match `[A-Za-z0-9][A-Za-z0-9._:-]{0,79}`, carries no wording, and is refused if it matches `autonomy.HUMAN_APPROVAL`.
  - Otherwise, if both stdin and stdout are terminals, the actor is `operator`, as today.
  - Otherwise the command is refused before anything is recorded: "without a terminal, name the relaying agent session with --relayed-by". The refusal applies to `start` in every mode, `resume`, `continue` and a batch or single `approve` in Chat.
  - Records gain `by: "operator" | "relayed"` and, for `relayed`, `relayed_by: SESSION`. Relayed records hold no free text: the `ref` of a relayed gate approval is `relayed approve GATE`, never the operator's chat words. `resume --ref` and `continue --ref` text stays allowed under the existing `HUMAN_APPROVAL` wording guard.
  - Every renderer shows the actor: `record.md` mode and block-resolution lines, Chat status "Gates:" lines, `allowed_actions`, the Chat PR "Human approvals" section, and the ledger gate `log_line`. Relayed records read `relayed by agent session SESSION` and are never rendered as `by operator` (AC-010, AC-013, SC-004).
  - Validators accept both values. Existing records with `by: "operator"` stay valid.
- **Rationale**:
  - The launcher cannot verify that the operator said yes in chat (spec Assumptions), so the record must say who claims it.
  - An agent session's shell has no terminal, so a terminal-less command that records a decision must name its session or be refused. It can never fall back silently to `operator`. This closes an existing gap: today `start --mode autonomous` needs no terminal and records `by operator`.
  - A terminal is not proof of a human, but it is the boundary Chat approvals already use (`chat._terminal`, ADR-0009 D-4).
- **Test impact**: In-process tests of terminal-less `start`, `resume` and `continue` today record `by: "operator"`. They will pass `--relayed-by` or the existing `TTY` stand-in. Assertions that a terminal-less command recorded `operator` change by design (FR-011), each named in the tasks. No refusal or validation test is weakened.
- **Alternatives considered**:
  - Infer the session from provider environment variables: they are undocumented, spoofable, and absent for Codex. The explicit flag is honest about being a claim.
  - Label terminal-less commands `relayed` with an `unnamed` session instead of refusing: it would hide which session acted.

## R8. Which relays each mode allows (FR-008, FR-010, FR-012, AC-011 to AC-016, AC-028)

- **Decision**: The matrix lives in `actor.py` as data, and the ADR and policy table is generated from the same names (contract [cli.md](contracts/cli.md#agent-command-matrix)).
  - **`approve` relayed** is allowed only when the run is a Chat run whose effective mode is `chat`.
    - In a human-gated run, or a Chat run switched to `human-gated`, it is refused: "the operator approves at a terminal in a human-gated run". Nothing is recorded.
    - In an Autonomous run it is refused: "an Autonomous run has no human gate before merge". No HD is written. The existing gate code already exists only in Chat, so this is a new early refusal in `run._chat_command` (AC-012).
  - **`start --mode autonomous` relayed** is allowed when eligibility passes, and recorded as relayed in `mode_history[0]` (AC-013). `start --mode chat` relayed is allowed and recorded as relayed in its `mode_history[0]`. Human-gated `start` and `resume` relayed are allowed, but a human-gated run has no operator run record (`autonomy.new_run` runs only for Chat, Autonomous and `continue`) and gains none: `--relayed-by` is validated, and the actor rule's refusal of a terminal-less call without it is all that applies. Its gate decisions are Spec Kit engine `gate` steps, which prompt only at a terminal, so nothing in a human-gated run is recorded as relayed (plan-review F-002, F-001).
  - **`resume` and `continue` relayed** depend on the category of the block the run stopped on (operator decision D-08 on Issue #147, resolving plan-review F-001). Both record a relayed `block-resolution` or `mode-change`.
    - A block that carries no decision (`upstream-sync`, `interrupted` including a usage limit, `postcondition`) may be resumed or continued relayed without asking the operator.
    - Every other category carries a decision: `decision`, `contradiction`, `review-finding`, `limit` and `ineligible` as the spec names, and, failing closed, `tamper`, `unfinished-step`, `permission`, `forge` and `credential`. A relay of such a block needs `--ref TEXT` naming the operator's in-chat answer. Without `--ref` it is refused before anything is written: "this block carries a decision; relay it only with --ref naming the operator's answer". The `ref` passes the existing `HUMAN_APPROVAL` wording guard, so it names the answer (for example `Issue #147 comment, option 2`) and never quotes approval words.
    - The set of decision-free categories is data in `actor.py`, so a block category added later carries a decision until someone classifies it.
    - This governs blocks, not gates. A relayed gate approval in an Autonomous run stays refused (FR-010).
  - **`mode RUN chat|human-gated`** now needs a terminal with the typed confirmation `mode RUN TARGET`, and is never relayed. Switching a human-gated run to Chat would otherwise let a session open relayed approvals on a run the operator chose to gate.
  - **`trust` and `reject`, and `resolve`**: `run reject` accepts no `--relayed-by` and keeps its terminal requirement. `trust` keeps today's behavior: no terminal requirement, refused inside a workflow step, so the agent session may run it on a checkout it set up (operator decision D-09 on Issue #147). `run resolve` stays terminal-only, as it records a human decision resolution, which the Issue does not open to relay.
  - **Confined steps (FR-012, AC-014)**:
    - The boundary is unchanged: the `in-progress` marker refuses every launcher command while any step runs, and the step's sandbox hides operator state.
    - As defence in depth, every agent step's environment (headless, confined and interactive) gains `BALLAST_AGENT_STEP=1`, and `launcher.main` refuses every command except `status` when it is set.
    - The ADR states that the marker, not the variable, is the boundary.
- **Consequence for merge review**: today `ballast trust` needs no terminal. This repository's `ballast.toml` comment (operator decision 2026-10-06) describes the driving agent running `ballast trust` on checkouts it set up. That practice stays (D-09): AC-016 no longer adds a terminal requirement to `trust`. The `operator-trust` privileged-action kind (ADR-0016) still authorizes a run to *need* a trust before merge, which the operator or the operator's agent session outside any step may run. The automatic refresh (R1 to R4) removes the cases that practice existed for. The plan follows the spec. The `ballast.toml` comment stays as it is.
- **Rationale**:
  - This is D-01 and D-04 as resolved.
  - Requiring a terminal for `mode` is the smallest change that keeps a human-gated run's typed approvals from being bypassed by an agent-driven mode switch.
  - It costs one command that already carries a decision.
- **Alternatives considered**:
  - Allow relays only in Chat runs whose mode was entered at a terminal: the operator drives from an agent session, so `start --mode chat` itself is relayed. This would block the user story.
  - Leave `mode` unrestricted: an agent session could turn a human-gated run into a Chat run and relay its gates.
  - Allow every relayed `resume` and `continue` (the first plan): an agent could resolve its own run's decision block unseen by the operator (F-001). Refusing relayed resolution of decision blocks outright (F-001 option 1): the operator would type a command for a decision already given in chat. The operator chose option 2, the `--ref` requirement (D-08).

## R9. Batch approval (FR-007, AC-017 to AC-020)

- **Decision**:
  - **Command forms**: `ballast run approve RUN GATE [GATE ...]` and `ballast run approve RUN --through GATE`, which are mutually exclusive. `--through` selects, in `GATES` order up to and including `GATE`, every gate whose `approval_state` is `pending` or `stale`. Explicit gates must be named in `GATES` order without duplicates.
  - **Validation, under one run lock before any prompt**:
    - every named gate must be `pending` or `stale`, otherwise "GATE is not pending" (AC-019);
    - `_require_no_step`;
    - each gate's `gate_precondition` is evaluated with the batch's earlier gates treated as approved at their current digests, so `tasks`, which needs `intent` and `plan`, can follow them in one batch.
  - **Display and confirmation**: one block lists each gate, its artifact path and digest. The confirmation is the exact line `approve GATE GATE ...`, and a mismatch records nothing (AC-019).
  - **Recording**: after confirmation, every digest is re-read. One new `autonomy.append_human_decisions(run_dir, decisions)` writes all `HD` lines in one atomic rewrite of `human-decisions.jsonl`, keeping the hash chain. Then the per-gate side effects run in gate order: `record_intent`, the tasks baseline, the ledger gate events. A failure before the write records nothing. The write is all-or-nothing.
  - **Single-gate compatibility**: `approve RUN GATE` is a batch of one with today's prompt text `approve GATE`, so existing tests and muscle memory hold.
  - **Relayed batch**: in Chat, `--relayed-by` replaces the terminal and the typed line and writes per-gate relayed records (AC-020). Terminal-less without the flag, it is refused.
- **Rationale**: One confirmation that lists every decision keeps each decision explicit (SC-003). Atomic append is what makes "all or none" true after a crash.
- **Alternatives considered**: Loop the existing single-gate path (a crash or a failing third precondition would leave gates half-approved); `--all` (approves gates the operator did not name or bound).

## R10. Headless Chat step (FR-009, AC-015)

- **Decision**:
  - `ballast run step RUN PHASE --headless` runs the phase's agent through `agent.py main` with the Autonomous confinement: bwrap, `CONFINED_ALLOW` and `CONFINED_DENY`, the systemd scope, the `in-progress` marker, and the confinement self-test. It reuses the phase prompts, postconditions and `_finish` of the interactive Chat step.
  - `agent.py` today confines only when an Autonomous record exists (`:1600-1629`). It gains an explicit `--confined` flag that `chat._headless` passes for `--headless` in Chat mode. Human-gated Chat steps keep today's argv, which `test_headless_step_keeps_todays_argv` asserts.
  - Without `--headless` and without a terminal, the Chat refusal stays and now names `--headless`.
  - The run then stops wherever the phase graph needs an approval. `status` lists the pending gates and the batch command.
- **Rationale**: The agent session needs a step it can run without a terminal, under no less confinement than Autonomous. An explicit flag keeps today's refusal for a terminal-less interactive request.
- **Alternatives considered**: Choose headless automatically without a terminal (it hides which confinement ran); run headless Chat steps unconfined like human-gated ones (that widens an agent session's reach beyond Autonomous).

## R11. `discard-runs` arguments and the trust it no longer forces (FR-005, FR-006, AC-021 to AC-023)

- **Decision**:
  - **Arguments**: `discard-runs --help` and `-h` print a usage text to stdout, exit 0, and take no lock and no action. Any other argument is refused with exit 2 and does nothing. The check is the first thing `main` does for `discard-runs`, before the uninstalled-checkout refusal.
  - **Trust**: run state and the marker are outside the baseline, so discarding them never changes protected inputs. After discarding, `_discard` runs `_trust_refusal` minus the marker it just removed.
    - If inputs equal the baseline, the "Next" line no longer names `ballast trust`.
    - If they differ, it still does.
    - With a tamper marker, the tamper recovery is printed.
  - The `unfinished-step` and `tamper` recovery texts in `autonomy.RECOVERY`, and the launcher's `RECOVER`, say "then `ballast trust` if `ballast run status` still reports changed inputs". Tamper recovery keeps its `ballast trust`, because restored files must be reviewed.
- **Rationale**: The launcher already accepts an unchanged checkout after the marker is gone. The forced re-trust was in the instructions, not in the check.
- **Alternatives considered**: Make `discard-runs` record a fresh baseline itself (it would vouch for the checkout without review).

## R12. Resume after an implementation postcondition reruns `implement` (FR-015, AC-024)

- **Decision**:
  - `run._block_step` maps a failed `validate-implementation` with category `postcondition` to `implement`, as it already maps a failed `record-*` step to its agent step.
  - `_reentry` can still move earlier for a changed input. The implementation baseline is kept, and the agent step counts against the limit.
  - An operator who fixed the implementation by hand reruns `implement`, which finds every task done and changes nothing material, then the validator runs.
  - The ADR records this as an amendment to ADR-0010's re-entry rule.
- **Rationale**: Rerunning only the validator after no change fails the same way. The #141 run needed a manual workaround.
- **Alternatives considered**: Rerun `implement` only when nothing changed outside the feature directory (two behaviors to explain for one block).

## R13. Usage-limit stops close as interrupted (FR-016, AC-025, AC-026, D-07)

- **Decision**:
  - `agent.py` classifies every failed agent exit with `fallback.classify` against `fallback.SIGNATURES`, not only when a fallback is configured.
  - A usage-limit signature whose wrapper confirmed the scope stopped (`stop_scope` and `_stop_descendants` succeeded, marker removed) exits with a new `EXIT_USAGE_LIMIT`. `run.WRAPPER_CATEGORIES` maps it to `interrupted`, with the detail "the agent CLI hit its provider usage limit".
  - That category is already resumable through `ballast run resume` (Autonomous) or `ballast run step` (Chat), needs no `discard-runs` and no `trust`, and the recovery text says to wait for the limit to reset.
  - A wrapper that died leaves the marker, so `unfinished-step` and its refusal are unchanged (AC-026).
  - The local-fallback behavior is unchanged when a fallback is configured.
- **Rationale**: D-07 option A. Only the confirmed-stopped path changes category, so no tamper path weakens.
- **Alternatives considered**: Treat every non-zero exit as interrupted (that hides real postcondition failures).

## R14. Issue-named branch at Autonomous start (FR-017, AC-027, D-06)

- **Decision**: When `check_eligibility` fails only on the branch rule (`BRANCH_REFUSAL`, no open-PR cause), `_start_autonomous` proposes a branch:
  - the existing local branch whose name has the Issue number as a segment (`is_feature_branch`), when exactly one exists; otherwise
  - `feat-<feature directory name>`, for example `feat-147-human-gates-are-decisions`. It is validated by `git check-ref-format --branch` and must not exist.

  At a terminal it asks `switch to BRANCH? type "switch BRANCH"`. On a match it runs `git switch [-c] BRANCH` through the hardened Git of `draft_pr._resolve`, re-runs eligibility once, and proceeds. Without a terminal, including a relayed start, it refuses and prints the exact `git switch -c BRANCH` (or `git switch BRANCH`) command and the start command to rerun. The checkout is never switched without a typed answer.
- **Rationale**: D-06 option A. The switch keeps uncommitted changes (`git switch` refuses conflicting ones), which matches what an operator would type.
- **Alternatives considered**: Switch automatically (rejected by D-06); a `y/N` prompt (the typed-text confirmation is the house pattern).

## Governing documents (FR-013, FR-014, FR-018)

- **New ADR**: [ADR-0021](../../docs/adr/0021-agent-sessions-relay-decisions.md), "Agent sessions run mechanical commands and relay decisions within the run's autonomy". It is proposed and agent-provisional until merge, and covers:
  - the agent command matrix (R8);
  - the actor rule (R7);
  - the default-branch refresh (R1 to R5);
  - the trust settings check (R6);
  - batch approval (R9), headless Chat steps (R10) and the recovery changes (R11 to R14);
  - the dependency on Spec Kit engine `gate` steps prompting only at a terminal, which keeps a relayed human-gated `start` or `resume` from recording an approval (ADR-0004 context; plan-review F-001);
  - residual risks:
    - branch protection on the pinned default branch is now the only review of configuration changes for a checkout with an existing baseline of that repository, including widened `[agents.permissions]` and `[autonomous]`;
    - a relayed approval, or a relayed `--ref` resolving a decision block, is a labeled claim the launcher cannot verify;
    - the terminal test (`isatty` on stdin and stdout) guarding `reject`, `resolve`, `mode` and human-gated approvals is not proof of a human, since an agent session can allocate a pseudo-terminal; the boundary is ADR-0009 D-4's, and this feature makes agent sessions routine `ballast` callers (first plan review);
    - `ballast trust` has no terminal test (D-09), so on a checkout the operator's agent session set up, that session can vouch for its own protected-input changes outside a step; the step boundary (the `in-progress` marker, the sandbox hiding operator state) is what keeps an agent inside a step from doing so;
    - `.venv` changes still need trust;
    - `BALLAST_AGENT_STEP` is not a boundary.

  It supersedes in part ADR-0004 ("Rejected: piping `approve` into gate prompts" now has a labeled relayed alternative in Chat only) and ADR-0009 D-4 (approvals only from a terminal) and D-1 (the list of operator actions). It amends ADR-0015 (refresh path, a third provenance source, the reviewed record also written by the refresh) and ADR-0010 (re-entry after an implementation postcondition). Each superseded ADR gets a one-line note beside the affected clause.
- **Constitution 1.3.0** amends BL-INV-002. The text is in [constitution-amendment.md](constitution-amendment.md) and is applied in this PR. BL-INV-006 is unchanged: a relayed approval is never presented as operator-typed and is refused in Autonomous runs.
- **Policies** are edited at the source `templates/policies/*.md` and mirrored into `docs/policies/` by the same change, as the governance tests read the templates. The edits cover `spec-kit-workflow.md` (runner contract table, Chat runs, Autonomous runs, branch synchronization, trust) and `workflow.md` (supervision modes). AGENTS.md, `templates/AGENTS.md`, `templates/init/agents-section.md`, the `ballast-feature-intake` skill, README and `specs/TECHNICAL-SPEC.md` §37 and §9.1 change with them (FR-018).
