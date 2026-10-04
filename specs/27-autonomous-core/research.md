# Research: Autonomous run core

Phase 0 decisions for [plan.md](plan.md). Each entry gives the decision, why, and what was rejected. Evidence is the current code in `tools/spec_workflow/`, `tools/setup`, `tools/feature_intake.py`, the shipped workflow `templates/spec-kit/workflows/feature/workflow.yml`, and the policies under `templates/policies/`.

Limits of this research: the Spec Kit 1.0.11 engine source and its upstream workflow reference were not readable from the planning session (outside the worktree, and network access was denied). Every decision below therefore relies only on behavior this repository already exercises: `command`, `shell` and `gate` steps, per-step `integration`, `input.args`, `on_reject`, run IDs from `SPECKIT_WORKFLOW_RUN_ID`, and resume of a paused or failed step. No decision depends on conditional, loop or non-interactive gate support.

## R-01 How Autonomous avoids approval prompts

- **Decision**: Ship a second workflow, `ballast-autonomous`, with no `gate` steps. Each human gate in `ballast-feature` becomes an agent decision step (`command`), followed by a trusted `shell` step that records the provisional decision and enforces the same postcondition. `run.py` selects the workflow from the operator-chosen mode.
- **Rationale**: Gates prompt on a TTY (`EngineRunTests` answers `Choose [`), and there is no in-repo evidence of a non-interactive gate or a step condition. A separate definition leaves `ballast-feature` byte-for-byte unchanged, which is the simplest way to meet SC-007 and keep the existing workflow tests passing.
- **Alternatives rejected**: One workflow with mode-conditional steps (engine support unverified). Piping `approve` into gate prompts (that would be the runner approving on the human's behalf, and the record would say "approve" for a human gate). Patching Spec Kit (another maintained patch for a feature the engine may later offer).

## R-02 Where the mode, limits and eligibility live

- **Decision**: In a per-run operator record, `$XDG_STATE_HOME/ballast/<checkout-key>/runs/<run-id>/run.json`, inside the existing `launcher.state_dir()`. `run.py` writes it before Spec Kit starts. The agent wrapper and validators read it. Mode changes are appended to the same record's history.
- **Rationale**: `state_dir()` already holds `trusted.json` and the `in-progress` marker because no agent can write there. Codex's `workspace-write` sandbox confines writes to the checkout. Claude's `acceptEdits` runs with prompts disabled, which denies edits outside the checkout. Workflow inputs (`inputs.json`) and `ballast.toml` were rejected as the mode's home: inputs are engine state, and the toml is project configuration that the operator does not set per run.
- **Confinement (operator decision, 2026-10-03; plan review F-1)**: Claude's allowed test commands run repository code without an OS sandbox, so in a human-gated run that code could write the state directory. Autonomous removes the human gates that cover this, so in an Autonomous run the agent wrapper starts every agent CLI (Claude and Codex) inside the existing systemd scope under bubblewrap with a **read-only host** (plan review round 2):
  `bwrap --ro-bind / / --bind <worktree> <worktree> --tmpfs /tmp --dev /dev --proc /proc --overlay-src <dir> --tmp-overlay <dir> … --die-with-parent`.
  - Writable: the worktree only, minus its protected inputs, which the wrapper's existing hash check still guards. When the worktree is a primary checkout, its `.git` directory is bound read-only on top (`--ro-bind <worktree>/.git <worktree>/.git`), so the Git directory is read-only in both layouts (a linked worktree's `.git` file points into the read-only common directory). `/tmp` is a private tmpfs.
  - Throwaway overlays (writes discarded at step end): the agent CLI homes (`~/.claude`, `~/.codex`, or the directory `CLAUDE_CONFIG_DIR` names) and `~/.cache`. Claude's top-level `~/.claude.json` is a file, so it is bind-mounted from a per-step copy in the wrapper's private temporary directory and discarded at step end. An agent therefore cannot plant hooks, settings or skills that run in the operator's later unconfined sessions. Authentication still works because the CLIs read existing credentials through the overlay. A refreshed token is lost at step end, which only costs a refresh.
  - Process and socket isolation (plan review round 5, verified on this host): `--unshare-pid --unshare-ipc --new-session`, and an empty `--tmpfs` over `/run`, `/var/run` and `$XDG_RUNTIME_DIR`. Inside, the systemd user bus, session D-Bus, keyring, `ssh-agent`, `gpg-agent` and `docker.sock` are unreachable (`systemd-run --user` fails with "Failed to connect to user scope bus"), only the sandbox's own processes are visible, so `/proc/<pid>/environ` of the operator's shell and `run.py` cannot be read, and TIOCSTI injection into the operator's terminal is impossible. The self-test fails closed when, from inside, `systemd-run --user true` succeeds, any entry of `$XDG_RUNTIME_DIR` is visible, or the parent's `/proc/<pid>/environ` is readable.
  - Protected inputs read-only (round 5): `ballast.toml`, `.ballast/`, `.specify/` and `.venv/` are bound `--ro-bind` on top of the writable worktree, so neither an agent nor code it wrote can rewrite workflow machinery that a later trusted step executes. The paths Spec Kit itself writes during agent steps (`SPECIFY_WRITABLE`: `.specify/feature.json`, `.specify/extensions/.cache`, `.specify/workflows/.cache`) are pre-created and bound writable on top, exactly the set the wrapper's hash check already skips (round 6, H-1). The wrapper's after-step hash check remains as a second guard. Test: a confined fake `speckit.specify` writes `feature.json` and succeeds, while a write to `.specify/workflows/` fails.
  - The same confinement applies to every process that runs agent-written code: agent steps and the `run-checks` step (R-12). After `run-checks`, `run.py` runs the protected-input hash check and records a `tamper` block on any difference.
  - Credentials hidden (plan review round 4): forge, SSH, signing and other secrets are unreachable from agent processes, so agent-run code cannot write to GitHub or any other system outside the publisher. The wrapper mounts an empty tmpfs over `~/.config`, `~/.ssh`, `~/.gnupg`, `~/.docker`, `~/.aws`, `~/.kube` and `~/.local/share/keyrings`, binds `/dev/null` over `~/.git-credentials`, `~/.netrc` and `~/.pypirc`, and unsets every environment variable whose name contains `TOKEN`, `SECRET`, `PASSWORD`, `CREDENTIAL`, `API_KEY` or `AUTH`, plus `SSH_AUTH_SOCK`, `GPG_AGENT_INFO` and `GIT_ASKPASS`, except the running integration's own key variable (`ANTHROPIC_API_KEY` for Claude, `OPENAI_API_KEY`/`CODEX_API_KEY` for Codex) when set, so an API-key login keeps working. The agent CLI's own login stays readable through its throwaway overlay, which is the only credential an agent needs. Network stays available, because the CLIs need their provider API; with no forge credentials, network access cannot reach a forge write. Tests: inside a confined step, `gh auth status` reports not logged in, `git ls-remote` over an authenticated remote fails for lack of credentials, and none of the listed paths or variables is readable.
  - Read-only by default: everything else, including the state directory, the Git common directory (with `speckit-runs`, `hooks/` and `config`), `~/.config` and `~/.local`. Network stays as each integration configures it.
  - The mode, limits, eligibility, decision log, trust baseline, ledger, repository Git config and hooks are therefore read-only to the agent and everything it runs.
  - Why bwrap and not systemd sandboxing: on the qualified Ubuntu host, `kernel.apparmor_restrict_unprivileged_userns = 1` makes a user manager silently skip `ReadOnlyPaths`/`ProtectHome` (verified: writes still succeeded). `bwrap` is allowed user namespaces by Ubuntu's `bwrap-userns-restrict` profile, and the same read-only bind blocked the write (verified on systemd 259).
  - Fail closed: before the first agent step, `run.py` runs a self-test (a confined `touch` into the state directory and into the Git common directory must fail with a read-only error, and a write to an overlaid home must not persist). A missing `bwrap` or a failed self-test refuses an Autonomous start as `ineligible` ("confinement unavailable"), naming the human-gated mode as the alternative. The wrapper re-checks before each Autonomous agent step.
  - Human-gated runs are unchanged (no bwrap), keeping #27's scope.
  - Tests: from inside a confined agent step, through both integrations, writes to `run.json`, `decisions.jsonl`, `trusted.json`, the ledger, the Git common directory, `~/.config` and a path outside the worktree fail, a write to `~/.claude` does not persist after the step, and the Git-directory write test passes in both a primary checkout and a linked worktree, and the run's effective mode is unchanged (SC-005); a missing `bwrap` and a failing self-test each refuse an Autonomous start. The real-bwrap test is skipped in CI without user namespaces, like the existing real-systemd tests.
  - Dependency: `bwrap` (bubblewrap) becomes a host prerequisite for Autonomous only; #12's `ballast doctor` should report it.

## R-03 Eligibility source and timing

- **Decision**: A new trusted module, `tools/spec_workflow/autonomy.py`, checks eligibility in `run.py` before Spec Kit starts:
  1. The Issue (from `-i issue=N`) is open, not labelled `epic`, has no sub-issues and no open blocker, carries `ready-for-agent`, and has exactly one intake scope comment (`<!-- ballast-intake: issue=#N; scope=... -->`).
  2. The scope comment declares `Risk: R0|R1|R2` and a new line `Privileged actions before merge: none` (or a list).
  3. The risk is allowed and each declared privileged action is authorized by `[autonomous]` in `ballast.toml` (R-04).
  4. The feature directory number matches the Issue number.
  5. No effective Git configuration value (system, global, local, worktree or included) carries a credential an agent could read: a URL with embedded user information (`https://user:token@…`), any `http.*.extraheader`, any value containing `Authorization`, or a `credential.helper` store file inside the checkout. Any match refuses the start, naming the key (plan review round 5). Test: a token-bearing remote URL in `.git/config` refuses the start.
  6. The scope comment's author has `author_association` OWNER, MEMBER or COLLABORATOR, so an outside commenter cannot widen a feature's scope or risk.
  The result, the reasons and a snapshot of the effective policy are stored in the run record. A refusal exits 2 before any agent step and names `ballast run start` without `--mode` as the alternative.
- **Rationale**: The scope gate is already recorded on GitHub by `feature_intake.py ensure_scope`. Reading it is deterministic and needs no agent. A missing privileged-actions line fails closed, because older scope comments never declared it.
- **Why not reuse `.ballast/feature_intake.py`**: it is installed outside `.ballast/spec_workflow/`, so it is not in the trust baseline (`launcher.BASES`). `autonomy.py` therefore carries its own small read-only `gh api` query. The duplication is about 40 lines and is recorded under Complexity Tracking. Whether `.ballast/feature_intake.py` should join the baseline is a separate hardening question, noted as follow-up F-1 in the plan.
- **Risk re-check (AC-022)**: Agents may only raise risk, by declaring a higher level in a decision draft. The recorder updates the run record and re-evaluates eligibility against the policy snapshot taken at start. If the run is no longer eligible, it blocks. A lower declared level is ignored and noted.

- **Late discovery (plan review F-5)**: every agent draft and every review entry carries `privileged_actions: [..]` (empty list when none). The recorder rechecks eligibility (step 3) whenever the list grows, and `run.py` rechecks it again immediately before publication. An action not authorized by `[autonomous]` records an `ineligible` block. Tests: a draft that adds an unauthorized action blocks the run; a review that reports one blocks publication.

## R-04 Project narrowing policy

- **Decision**: An optional `[autonomous]` table in `ballast.toml`, with keys `risk` (a subset of `["R0","R1","R2"]`), `excluded_boundaries`, `authorized_privileged_actions`, `wall_time_minutes` and `max_agent_steps`. Unknown keys, risk levels outside R0–R2 and anything else that would widen eligibility are ignored, and the run prints a warning naming them. `merge`, `release` and `deploy` can never be authorized (FR-027).
- **Rationale**: `ballast.toml` is a protected trusted input: it is hashed by `trust`, its edits are denied to Claude, and any change fails the agent step. A policy in `docs/policies/project/` would be agent-writable during the run.
- **Alternative rejected**: Reading narrowing rules from `docs/policies/project/workflow.md`. That prose is not machine-checkable, and an agent can edit it mid-run.

## R-05 Provisional decision storage, append-only and forgery checks

- **Decision**: The source of truth is the operator log `runs/<run-id>/decisions.jsonl` in the state directory. Only trusted shell steps and `run.py` append to it. Each entry carries the SHA-256 of the previous entry, so the log forms a hash chain. Agents write one draft per decision point to `specs/<f>/autonomous/drafts/<point>.json`. The recorder validates the draft, adds runner-observed identity from the protected agent `meta.json`, appends the entry, deletes the draft, and re-renders the committed projection `specs/<f>/autonomous/record.md`. Every later validator re-renders the record from the log and fails when the committed file differs. That catches edits, deletions and forged entries.
- **Rationale**: Agents cannot write `.specify/workflow-state/` (the wrapper hashes it) or the state directory, so drafts must live in the feature directory. Keeping the log outside agent reach gives a real append-only guarantee (FR-013). The committed file is a projection, not a second source of truth, and it is the reviewer-visible artifact (FR-014, SC-006).
- **Alternatives rejected**: Agent-written committed markdown as the record (forgeable). The ledger as the record: its schema forbids prose by design, and it lives in the Git common directory, which a primary checkout's Claude agent may be able to reach.

## R-06 Intent binding and human-approval forgery (FR-011, FR-012, AC-008)

- **Decision**:
  - In Autonomous mode, `record-provisional-intent` writes a separate block `<!-- workflow-provisional: begin/end -->` with `- **Provisional spec digest**: sha256:...` and the decision ID. `check_intent` under an Autonomous run accepts only that block, and only when its digest equals both the current spec and the log entry. It refuses any `workflow-approval` (human) block.
  - A human-gated check refuses a provisional block, because the existing `DIGEST_LINE` only matches `Approved spec digest`.
- **Rationale**: An Autonomous run has no human gate before merge, so any human approval block inside it is forged by construction. Refusing all of them closes the forgery path for Autonomous runs without touching human-gated validation.
- **Out of scope (operator decision, 2026-10-03)**: an approval registry for human-gated runs. It would change human-gated behavior and force in-flight runs to re-approve, so it moved to #29.

## R-07 Agent commands for decisions, clarification, reviews and resolutions

- **Decision**: Ship a local Spec Kit extension `ballast` (`templates/spec-kit/extensions/ballast/`) installed by `tools/setup` with `specify extension add --dev`, as the other extensions are. It provides four commands:
  - `speckit.ballast.decide`: one gate decision; `args` names the decision point.
  - `speckit.ballast.clarify`: autonomous clarification, which adopts only safe, reversible defaults.
  - `speckit.ballast.review`: an independent review; `args` names the kind.
  - `speckit.ballast.resolve`: provisional resolution of implementation discoveries.
  Each command writes a draft that matches [contracts/decision-draft.md](contracts/decision-draft.md). To block, it writes `drafts/block.json` and prints `RECONCILE_STATUS: BLOCKED_DECISION`, which the wrapper already turns into a failed step.
- **Rationale**: The installed `speckit.clarify`, `speckit.intent.implement` and `speckit.intent.decisions` instruct the agent to ask a human or to emit `BLOCKED_*` without a human resolution. Overriding them with contradicting `args` is unreliable. Autonomous therefore uses `speckit.implement` directly and the Ballast commands for every point that would need a human.
- **Alternative rejected**: Calling Ballast skills (`ballast-engineering-review`, for example) directly from a `command` step. Spec Kit resolves `command` IDs to installed commands, not arbitrary skills. The review command instead tells the agent to load the relevant skill files.

## R-08 Independent reviews and specialist coverage (FR-016, AC-004, AC-023)

- **Decision**: Review steps set `integration: "{{ inputs.review_integration }}"`. `run.py` fills that input with the provider that did not author the run when its CLI is on `PATH`. Otherwise it uses the same provider and records `cross_provider: false`. Codex's own `workspace-write` sandbox is `bwrap`-based and cannot start nested inside Ballast's confinement on a host that restricts unprivileged user namespaces (DEC-0004). Whenever Codex would take either role, `run.py` therefore probes once at run start, confined and without network, whether `codex sandbox` can run `true`. When it cannot, Claude takes both roles (`cross_provider: false`), and the run record (`integration_fallback`), the start output and `record.md` carry a fixed reason; a host without `claude` is refused. Codex's sandbox is never disabled. Every `command` step is a fresh CLI process, so each review runs in a context separate from the author's. The run has three review steps: `review-plan`, `review-implementation` (engineering and test, always) and `review-specialists`, which runs every required specialist in one fresh reviewer context. The recorder requires one review entry for each required kind. **Security review is always required in Autonomous** (fail closed, plan review round 2): a change to authentication, access rules, secrets or agent authority can sit in any source path, so path triggers may add reviews but never remove security. The required set is security plus the union of:
  - deterministic path triggers on the diff since the implementation baseline (`.github/` → security; lockfiles and `pyproject.toml` → dependency; migration directories → database migration; `docs/`, `README*` and public config → documentation);
  - the R2 boundaries declared in the scope record or raised during the run (security, architecture);
  - the kinds the reviewers declare.
  `none` is never accepted for specialist reviews, because security is always required.
- **Rationale**: There are no loops or conditionals. A fixed step that runs a variable set of reviews in one reviewer context, verified by a trusted recorder, keeps the number of agent invocations bounded.
- **Severity rule**: Every `critical` or `high` finding blocks the run, whatever disposition the review proposes, including `resolved` (FR-019, AC-024; plan review F-3). `medium` may be `accepted-provisionally` with a reason. This feature has no fix loop; a blocking finding stops the run.

## R-09 Limits (FR-020, AC-012)

- **Decision**: The run record holds `deadline` (start time plus wall time) and `max_agent_steps`. Values come from `--wall-time` and `--max-agent-steps`, or from `[autonomous]` defaults, or from the built-in defaults of 240 minutes and 30 steps. The agent wrapper:
  - refuses to start an agent step once the deadline has passed or the step count is reached;
  - increments the step count before each step;
  - waits on the agent for at most the remaining time, then stops its scope and runs the normal protected-file check.
  It exits with a new code, `EXIT_LIMIT = 5`. The block names the exhausted limit and keeps the agent logs.
- **Rationale**: The wrapper already owns process containment and runs from the protected `.ballast/spec_workflow/`. Enforcing limits there stops the run before the next agent step without killing Spec Kit mid-write. Killing Spec Kit would leave an unfinished step and force `discard-runs`, which loses state.
- **Excluded**: spend limits (spec assumption: no reliable usage data).

## R-10 Blocks and recovery (FR-021–FR-023, AC-014)

- **Decision**: When `run.py` stops an Autonomous run that has not completed, it writes `runs/<run-id>/block.json`. The category comes from the evidence:
  - an agent block draft → `decision` or `contradiction`;
  - wrapper exit 3 without a draft → `decision`;
  - exit 4 → `tamper`;
  - exit 5 → `limit`;
  - a failed `validate-*` or `record-*` step → `postcondition`, or `ineligible` and `review-finding` when the recorder says so;
  - exit 130 → `interrupted`;
  - a publish failure → `forge`, or `permission` when the publisher finds `gh` missing or unauthenticated. Agents never report `permission`: the block-draft contract allows only `decision` and `contradiction`, and a missing permission inside a confined step fails the step (`postcondition`) (DEC-0005).
  A changed trusted input is not a block category: the launcher refuses every `ballast run` subcommand before `run.py` executes, so the stopped run keeps its earlier block (DEC-0002).
  It prints the block and the recovery command and marks the run `stopped`. `ballast run resume` refuses any run whose record says Autonomous and names #18. The agent wrapper also refuses agent steps for a run that is not `active`, which covers a bare `specify workflow resume`.
- **Recovery**: `ballast run continue RUN_ID --reason block-resolved|changes-requested --ref TEXT`. This trusted operator action appends a human decision and a mode change to `human-gated`, then starts a new run of `ballast-continue`. That workflow has only validators and human gates, from `approve-intent` to `final-acceptance`. It carries the implementation baseline across and never re-runs a producer. Producer work still missing is done interactively, as the policy already allows, followed by a human-gated resume. Earlier provisional entries stay in the log and the record. Human approvals in the continuation supersede them, which the record shows.
- **Rationale**: Without conditional steps, a gate-only continuation cannot overwrite earlier artifacts and makes every remaining gate a human prompt (AC-017). Re-approving intent is required anyway, because human-gated validators accept only a human intent block.

## R-11 Draft PR publication (FR-024–FR-027)

- **Decision**: After the workflow completes, `run.py` publishes. It is the trusted runner, outside the Spec Kit engine. Agents have no `git push` or `gh` permission. The publisher:
  1. refuses the default branch;
  2. refuses if a PR already exists for the branch (reuse is #17);
  3. commits the worktree (`git add --all`, which respects `.gitignore`) as the operator, with an `Autonomous-Run: <id>` trailer;
  4. runs `git push -u origin HEAD` without force;
  5. runs `gh pr create --draft --body-file`.
  Staging boundary and code execution (plan review F-4): every git command runs as `git -c core.hooksPath=/dev/null -c core.fsmonitor=false`, and `commit` adds `--no-verify`. `autonomous-preflight` (at start) and the publisher refuse (`postcondition` block) when a `.gitattributes` in the tree names a `filter`, `diff` or `merge` driver that the effective config defines, so a globally installed driver such as git-lfs blocks only when the repository uses it; the in-checkout executable and include check also runs at start. Every trusted Git invocation, including `implementation-baseline` and the private-index digests, uses the same `-c core.hooksPath=/dev/null -c core.fsmonitor=false`. The staging boundary is the run start (plan review round 3): `autonomous-preflight` requires a clean worktree and records `HEAD` in the run record. The publisher stages with `git add --all`, then compares the staged paths with every change since that recorded `HEAD` (spec, plan, tasks, decision records and implementation alike) and refuses any staged path outside them, any protected input (`ballast.toml`, `.ballast/`, `.specify/`, `.venv/`), and any file over 1 MiB. The PR body lists the staged paths. At run start, `run.py` snapshots the repository-local Git configuration (`git config --local --list`, including `--worktree` and any `include` targets) and the hooks directory listing into the operator run directory. The publisher refuses (`postcondition` block) when either differs at publication. With the confined host (R-02), agents cannot write them, so this is a second guard. Signing programs, SSH commands and credential helpers then come only from the operator's global and system configuration, which agents cannot write. The publisher also refuses when any effective `gpg.program`, `gpg.ssh.program`, `gpg.x509.program`, `core.sshCommand`, `credential.helper`, `core.askPass` or `include.path`/`includeIf.*.path` value names a path inside the checkout, because the agent could have written that file (plan review F-4, rounds 2–3).
  Tests: a planted hook does not run; a configured filter blocks; an unexpected or protected staged path blocks; a changed local `credential.helper`, `gpg.program`, `core.sshCommand` or `include.path` blocks publication; a global helper that points into the worktree blocks publication; a dirty worktree refuses an Autonomous start; run-created artifacts from before `implementation-baseline` are staged.
  The PR body is rendered from the run record (contract: [pr-summary.md](contracts/pr-summary.md)). Any failure records a retryable `forge` block. `ballast run publish RUN_ID` retries without resuming the workflow. The branch check also runs at start, so an ineligible branch fails before any agent step.
- **Never**: `gh pr ready`, `gh pr merge`, release, deploy or force push. A test asserts that these strings are absent from the publisher's argument vectors.
- **Rationale**: Publishing as a shell step would turn a forge failure into a failed workflow step, which an Autonomous run cannot resume. A separate retryable publish keeps evidence and branch intact (spec edge case).

## R-12 Checks evidence

- **Decision (plan review round 2)**: A trusted `run-checks` shell step runs before final acceptance. It runs each command listed in `[checks] commands` in `ballast.toml` (a protected, trusted input), under the same bubblewrap confinement as agent steps (R-02), so agent-written code never runs unconfined as the operator. It records each command, its exit status and its duration in the operator run directory, and renders them into the PR body with `runner` provenance. A non-zero exit, a timeout, or an empty or missing `[checks]` table blocks the run (`postcondition`). Each command's timeout is capped at the run's remaining wall time (FR-020). Agent-reported checks may also appear in the PR, labelled `agent-reported`, but never satisfy this step.
- **Rationale**: Final acceptance must not rest on an agent's claim that checks passed. Running them confined keeps BL-INV-003; reading the commands from `ballast.toml` keeps an agent from choosing which checks count.
- **Tests**: a failing command blocks; a missing `[checks]` table blocks Autonomous start; a check command cannot write operator state (confinement test reused).

## R-13 Governance amendments (FR-029, FR-030)

- **Decision**: Amend these, all in the same PR:
  - `templates/policies/workflow.md`: R2 gate row; a new "Supervision modes" section.
  - `templates/policies/spec-kit-workflow.md`: Autonomous lifecycle, runner contract rows, recovery.
  - `templates/policies/model-routing.md`: line 51.
  - `templates/AGENTS.md` and this repository's `AGENTS.md`/`CLAUDE.md`: risk sentence.
  - `templates/github/pull_request_template.md`: R2 line.
  - `templates/skills/ballast-feature-intake/SKILL.md`: the privileged-actions scope line and the Autonomous start command.
  - The constitution: new principle BL-INV-006, "A provisional decision is never human approval; only merging the PR that contains it accepts it". Version 1.1.0, with a compatibility note.
  - `specs/TECHNICAL-SPEC.md`: §37 and §91.
  - `specs/PRODUCT-SPEC.md` around line 1370, only where it states R2 approval timing.
  Human-gated wording stays as it is, scoped explicitly to the human-gated mode.
- **Compatibility**: Projects pinning an earlier version see no change. `templates/AGENTS.md` and the PR template are copy-once, so existing adopters keep their old wording until they copy it again; the release notes say so.
