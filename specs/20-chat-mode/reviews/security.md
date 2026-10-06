# Security review: Chat mode (#20)

- Review: security
- Reviewer: claude (model), fresh context, same provider as the author. Codex was unavailable (usage limit), so there is no cross-provider reviewer.
- Scope: `52031c1..HEAD` (feature code in `1e1a478`, docs in `6591e1a`), reviewed as committed. Locations are `path:line` in `HEAD`.
- Risk: R2 (headless-agent permission model, launcher trust model)

## What was examined

- Policies and intent: `docs/policies/security.md`, `docs/policies/project/workflow.md`, constitution BL-INV-001..006, `specs/20-chat-mode/spec.md`, `plan.md`, `research.md` (R3), `contracts/step-runner.md`, `contracts/cli.md`, `contracts/phase-graph.md`, ADR-0006.
- Code: `tools/spec_workflow/chat.py` (whole file), `agent.py` (`chat_settings`, `interactive_argv`, `run_interactive`, plus the headless `permission_args`/`main` for comparison), `autonomy.py` (`confined_argv`, `_binds_for_worktree`, `PROTECTED`, `tree_digest`, mode history, human-decision kinds and validation, `change_mode`, `_publish_chat`), `artifacts.py` (`Feature.from_operator_run`, `check_intent`/`record_intent` registration, `check_decisions` and `human_resolutions`, `project_checks`), `launcher.py` (`_unfinished`, `BASES`/`SKIPPED`, `state_dir`), `run.py` dispatch, `draft_pr._run_feature`, `ledger` Chat report, `claude-chat-settings.json`, `claude-settings.json`, `tools/setup` skill installation and `.gitignore`.
- Traced: a Chat step from the launcher refusal through lock, late close, out-of-step record, branch sync, entry check, settings write, protected snapshot, pty session, scope stop, protected compare, postcondition, write-scope check and close. Also traced: approve/reject/resolve/mode/continue/checks/publish, the human-gated headless driver inside a Chat run, and a wrapper that died mid-step.
- Adversary: an interactive agent during a Chat step, and a headless agent in a Chat run switched to human-gated.
- Not run: no pilot on a real terminal, Claude Code or Codex build. Terminal-emulator behavior and agent-CLI configuration loading are marked unverified below.

## Findings

```yaml
review: security
verdict: changes_required
findings:
  - id: SEC-001
    severity: high
    invariant: BL-INV-003 (and BL-INV-001)
    location: tools/spec_workflow/autonomy.py:197; tools/spec_workflow/autonomy.py:1500-1504; tools/spec_workflow/agent.py:635; tools/spec_workflow/chat.py:489-507; tools/spec_workflow/chat.py:1549; tools/spec_workflow/claude-chat-settings.json:22-38; tools/setup:338-341; .gitignore:5-8
    description: >
      Demonstrated by code reading. Every Chat step can rewrite the installed
      skills, and no Ballast check notices. `tools/setup` copies the skills
      into `.agents/skills/<name>/` as real directories and links
      `.claude/skills/ballast-*` to `../../.agents/skills/<name>`
      (setup:338-341). Both paths are git-ignored (.gitignore:5-8).
      `.agents` is not in `PROTECTED` (autonomy.py:197), so the worktree
      bind leaves it writable (autonomy.py:1500-1504). The Chat read-only
      bind of `.claude` (agent.py:635) does not cover the `.claude/skills/ballast-*`
      symlinks: a write through them resolves to the writable `.agents/`.
      No deny rule names `.agents`, so Claude's `Edit(./**)` allow rule
      covers it, and Codex can write it directly.
      The change is invisible to every check:
      - The manifest lists only unignored files (`--exclude-standard`, chat.py:497),
        so the write-scope check and the out-of-step record miss it.
      - `tree_digest` drops ignored files, so the implementation and final
        approvals miss it.
      - It is outside `launcher.BASES` and `agent._protected_state`.
      - Ignored files are never committed, so the PR never shows it.
      Path: an authoring step rewrites
      `.agents/skills/ballast-security-review/SKILL.md` (or
      `ballast-engineering-review`, `ballast-spec-reconciliation`, or
      `speckit-*` for Codex). The next `review` step's prompt invokes that
      skill by name (chat.py:1549), so the authoring agent writes the
      reviewer's instructions, for example "end with `- Verdict: approved`".
      The review event, the PR's "Reviews" table and the cross-provider claim
      then show that verdict as independent evidence. The same works for
      every later phase command. Gates still need a human, but the evidence
      the human approves on can be forged. BL-INV-003 says an agent cannot
      edit the installed tools. This exposure already exists in Autonomous
      and headless steps. Chat's read-only `.claude` bind looks like
      protection but is bypassed by the installed symlinks.
    required_action: >
      Treat installed skill directories (`.agents/skills/ballast-*`,
      `.agents/skills/speckit-*`, `.claude/skills/*`) as protected inputs:
      bind them read-only in `confined_argv` for every confined step, include
      them in `agent._protected_state` (a change fails the step as tampered),
      add `Edit(./.agents/**)` to the deny list, and consider adding them to
      the launcher baseline. Add a confined test showing that a write to
      `.agents/skills/ballast-security-review/SKILL.md` and a write through
      `.claude/skills/ballast-*` both fail or mark tampered.

  - id: SEC-002
    severity: medium
    invariant: BL-INV-003, BL-INV-005
    location: tools/spec_workflow/chat.py:1392-1411; tools/spec_workflow/chat.py:852-878; tools/spec_workflow/chat.py:2007-2014; tools/spec_workflow/chat.py:497
    description: >
      Demonstrated by code reading. A write-scope violation is recorded as a
      failed `write-scope` check and makes the step `failed`. It is not
      reverted, and no entry condition or gate precondition reads it
      (`_requirements` only lists artifact checks and approvals,
      chat.py:852-878). So the out-of-scope change persists and the next
      phase runs. Example: a `specify` step edits `src/app.py` or `.github/workflows/*`.
      The next step's `write-scope` check compares only its own `tree_before`
      and `tree_after`, so it passes. The handoff summary keeps only the
      latest event per check name (chat.py:2007-2014), so the earlier failure
      disappears from "Failed checks" without the violating paths ever being
      re-checked. The change becomes part of the tree that the
      implementation baseline and approvals bind to. The scope check is also
      blind to ignored paths (chat.py:497). For example, a Codex step can
      write `AGENTS.local.md` or `CLAUDE.local.md`, which later agents read
      as instructions, without any record. Claude's `Edit(./*.local.md)`
      deny does not bind Codex.
    required_action: >
      Make a write-scope failure block until the violating paths are restored
      or the operator explicitly accepts them as an out-of-step change. For
      example, keep the violation open until a later manifest no longer
      differs on those paths, and show it in the summary and the PR section.
      Also detect writes to ignored paths that agents read, such as
      `*.local.md`, either by listing them in the manifest or by binding them
      read-only. Add tests: a feature-scope step that edits `src/`, followed
      by a later passing step, still blocks or still reports the violation.

  - id: SEC-003
    severity: medium
    invariant: BL-INV-003
    location: tools/spec_workflow/agent.py:466-482; tools/spec_workflow/claude-chat-settings.json; specs/20-chat-mode/research.md:35; docs/adr/0006-chat-mode-operator-driven-steps.md (D-2)
    description: >
      Documented by the authors (research.md:35), not reproduced here. In an
      interactive session the operator can leave `dontAsk` with Shift+Tab
      and then gets permission prompts, or can use Codex `/approvals` to
      switch to full access. FR-005 and AC-003 say the operator MUST NOT be
      prompted. ADR-0006 accepts this because a grant cannot get past bwrap.
      But bwrap is wider than the headless model. It keeps the host network
      (autonomy.py `_resolver_binds` docstring) and a read-only view of
      every host file that is not on the credential list. So an approved
      `Bash(curl ...)`, `WebFetch`, or Codex full access gives network
      egress and arbitrary command execution. A headless step denies these:
      Codex pins `network_access=false`, and Claude has a closed Bash allow
      list. An agent can ask the operator to grant them in conversation.
      This differs from the approved spec, and it is recorded only in
      research and the ADR, not as a human-resolved decision.
    required_action: >
      Either enforce the headless allow list whatever the session's mode,
      for example with a `PreToolUse` hook in the generated step settings
      that denies any tool call outside the headless allow list (`--settings`
      hooks run in every permission mode), or record this as a decision in
      `decisions.md` that the human resolves, stating that in-session grants
      can add network and command execution inside bwrap. For Codex, document
      that `/approvals` re-enables network inside bwrap, or refuse Codex for
      Chat until it can be locked.

  - id: SEC-004
    severity: medium
    invariant: BL-INV-005
    location: tools/spec_workflow/chat.py:400-406; tools/spec_workflow/chat.py:643-644; tools/spec_workflow/chat.py:2652-2665; tools/spec_workflow/autonomy.py (_publish_chat, `git add --all`)
    description: >
      Demonstrated by code reading. The `final` approval binds to
      `tree:` + `run.tree()`, which excludes `specs/<f>/reviews/`
      (chat.py:400-406, 643-644). `publish` requires only a current final
      approval and project checks on that same reviews-excluded tree
      (chat.py:2659-2664), then commits `git add --all`. After final
      approval, a `review` step is still allowed: only `published` refuses a
      step, and the review entry needs only the `implementation` check. Its
      agent may change or add any file under `reviews/`. That can include a
      changed `convergence.md`, which makes the spec-reconciliation approval
      stale; publish does not re-check that. It can also include a new file
      quoting earlier conversation logs (see SEC-008). Final stays current,
      the run stays `completed`, and publish commits and pushes that content
      with no new human approval.
    required_action: >
      Bind `final` (and the publish check) to the full tree including
      `reviews/`. Alternatively, refuse publish when `reviews/` changed since
      the final approval, and have publish require every gate approval to be
      current, not only `final`. Add a test: approve final, run a review
      step, and publish is refused.

  - id: SEC-005
    severity: medium
    invariant: BL-INV-006 (human decisions must be informed and unforged)
    location: tools/spec_workflow/chat.py:2278-2281; tools/spec_workflow/chat.py:2033; tools/spec_workflow/chat.py:2056; tools/spec_workflow/chat.py:1339
    description: >
      Demonstrated by code reading. `resolve` prints the agent-written
      Resolution body raw (`_out(body.strip())`, chat.py:2279) and then asks
      the operator to type `resolve DEC-NNNN`. A body with terminal control
      sequences can hide or overwrite text on screen while the digest binds
      the real text. Examples: `ESC[8m` (hidden), `ESC[2K\r` (erase the line),
      cursor moves. The operator then confirms a resolution different from
      the one displayed. The handoff summary also prints agent-derived text
      through `autonomy.neutralize`, which escapes Markdown and HTML but not
      control characters. That covers carried provisional decision summaries
      (chat.py:2056), rejection refs (chat.py:2033) and check details
      (chat.py:1339). `draft_pr.printable` exists for this purpose and is
      used only for paths and branch names.
    required_action: >
      Pass every agent-derived string printed to the operator terminal
      through `draft_pr.printable` (or an equivalent that escapes C0, C1 and
      DEL). This covers the `resolve` body, summary lines and failed-check
      details. Add a test with an `ESC[8m` resolution body that asserts the
      escape is shown escaped.

  - id: SEC-006
    severity: medium
    invariant: none (D-3 terminal boundary)
    location: tools/spec_workflow/agent.py:681-687; tools/spec_workflow/agent.py:706-711; tools/spec_workflow/agent.py:618
    description: >
      The code path is demonstrated; exploitation depends on the terminal
      emulator and is unverified. TIOCSTI is contained correctly (see
      Sound). But the wrapper writes the agent's pty output raw to the
      operator's terminal (agent.py:685), and in-sandbox processes can write
      any bytes to `/dev/tty`. On every exit path it restores the attributes
      with `TCSADRAIN` (agent.py:618, 710). That does not discard pending
      input, and nothing resets terminal modes: alternate screen, mouse
      reporting, bracketed paste, application keypad, cursor visibility.
      Effects:
      - A query whose answer arrives after the loop ends is left in the input
        queue and read by the operator's shell. Examples: DECRQSS, title or
        colour reports, and OSC 52 clipboard read where enabled.
      - OSC 52 clipboard write can plant a command on the operator's clipboard.
      - Modes left enabled, for example mouse tracking, inject bytes into the
        shell.
      The headless wrapper already tees raw output (pre-existing), but Chat
      makes a full-screen session the normal path and owns the terminal.
    required_action: >
      On session end:
      - drain briefly, then `termios.tcflush(stdin_fd, TCIFLUSH)` (or restore
        with `TCSAFLUSH`);
      - write a fixed reset sequence: leave the alternate screen, disable the
        mouse modes and bracketed paste, show the cursor, reset the keypad
        and SGR.
      Consider filtering OSC 52 and DCS/APC/PM strings from the relayed
      output. Add a fake-TUI test that leaves mouse mode on and a pending
      response, and assert both are cleared.

  - id: SEC-007
    severity: low
    invariant: BL-INV-003 (FR-009)
    location: tools/spec_workflow/chat.py:1789-1814; tools/spec_workflow/chat.py:1842; tools/spec_workflow/chat.py:1906-1919; tools/spec_workflow/chat.py:558-582
    description: >
      Demonstrated by code reading. This affects the human-gated
      (headless) driver of a Chat run. The setup: on SIGHUP or SIGTERM,
      `_headless` waits 20 s and then `process.kill()`s the agent wrapper
      (chat.py:1796-1799). The killed wrapper never stops its scope and
      leaves the `in-progress` marker. `_headless` reports
      `scope_stopped: not marker.exists()`, which is False, but `_finish`
      checks it only for the interactive driver (chat.py:1842). For
      headless it runs the postconditions while agent processes may still
      be alive, closes the step with `scope_stopped: True` hard-coded
      (chat.py:1914), and clears `active_step`. After `ballast discard-runs`
      the next invocation does not take the late-close path. Any edits the
      surviving agents made after the close manifest are recorded by
      `out_of_step` as `actor: operator` (chat.py:571-578), so agent edits
      are attributed to the operator, which the step-runner contract
      forbids.
    required_action: >
      In `_finish`, treat `scope_stopped: False` the same way for both
      drivers: keep `active_step` with `scope_stopped: false`, exit 4, and
      let the late close attribute the changes to the step. Record the real
      `scope_stopped` value. Add a test with a headless wrapper that is
      SIGKILLed.

  - id: SEC-008
    severity: low
    invariant: FR-017 (conversation logs stay local)
    location: tools/spec_workflow/chat.py:1649; tools/spec_workflow/chat.py:1029-1039; tools/spec_workflow/autonomy.py:1500-1504; tools/spec_workflow/claude-settings.json
    description: >
      Demonstrated by code reading. The leak can be detected only by human
      review. Each Chat step's `stdout.log` records everything the operator
      typed, including a pasted secret (spec edge case). It sits in
      `.specify/workflow-state/<run>/agents/<step>/`, and `archive()` copies
      it into `<git common dir>/speckit-runs/<run>/state`. Both are readable
      inside later confined steps: the host is bound read-only and only
      `.specify` writes are blocked. Neither Claude's `Read` deny list nor
      Codex blocks them. A later step can copy the secret into a committed
      artifact, and `publish` commits and pushes it with no secret scan.
    required_action: >
      In a Chat step, hide the run's earlier logs and the archive from the
      agent: mount a tmpfs over `.specify/workflow-state` and over
      `<common dir>/speckit-runs`, with a read-only bind back for only the
      step's own `claude-settings.json`. Add `Read(./.specify/workflow-state/**)`
      to the deny list. Optionally scan staged content for known
      secret-variable values before publish.

  - id: SEC-009
    severity: low
    invariant: BL-INV-002 (unfinished-step refusal)
    location: tools/spec_workflow/chat.py:1236-1238; tools/spec_workflow/chat.py:1595-1687; tools/spec_workflow/chat.py:1890
    description: >
      Demonstrated by code reading. The race needs two concurrent operator
      invocations. The flock is per run. Only `start` checks other Chat runs
      for an active step (chat.py:1236). `step` writes the checkout-wide
      `in-progress` marker with a plain `write_text` (chat.py:1687) after
      the launcher's existence check, and `_finish` unlinks it
      unconditionally (chat.py:1890). So `step` on run A and on run B (or a
      `resume` of an engine run) in two terminals can both pass the launcher
      and run two agents in one worktree. Each one's write-scope and
      attribution then covers the other's edits. The first to close removes
      the marker the second wrote, so the launcher stops refusing while an
      agent is still running.
    required_action: >
      Take a checkout-wide step lock (flock in the state directory) for the
      whole step lifecycle, or create the marker with `O_EXCL` and unlink it
      only when it still names this unit. In `run_step`, refuse when another
      Chat run has an `active_step`.

  - id: SEC-010
    severity: low
    invariant: BL-INV-003
    location: tools/spec_workflow/agent.py:472-478; tools/spec_workflow/autonomy.py:1612-1619; tools/spec_workflow/chat.py:1415-1421
    description: >
      Partly demonstrated; unverified for Codex. `--setting-sources project`
      matches headless (agent.py:131-133 and 476-477), so loading the
      checkout `.claude/settings.json` is at parity. In Chat `.claude` is
      read-only during the step, and an installed project always has
      `.claude/skills`. However:
      - A headless Codex step in a Chat run switched to human-gated (no
        bwrap) can create or edit `.claude/settings.json`.
      - Worktree-scope phases accept `.claude/` and `.codex/` changes as in
        scope (`_in_scope` checks only `PROTECTED`).
      - The read-only bind applies only when the path already exists
        (autonomy.py:1618), so a Chat step can create `.codex/` when it is
        absent.
      Hooks and allow rules in that file then run, or widen permissions, in
      the next Claude step. Whether the Codex CLI loads a project
      `.codex/config.toml` (MCP servers, sandbox settings) was not verified.
    required_action: >
      Treat `.claude/settings*.json` and `.codex/` as protected in every
      phase: refuse them in the write-scope check and include them in the
      protected snapshot. Bind `.codex` read-only even when it is absent,
      for example with an empty read-only directory, or fail the step if it
      appears.
```

## Sound

- **Launcher and preflight**: `run.py` dispatches every Chat command after the launcher's trust-baseline, tamper-marker and `in-progress` checks, then checks the tamper marker again. A `step` always runs `late_close`, `out_of_step`, branch synchronization (`rerun` text) and the entry check before the one agent (chat.py:1595-1624). A blocked sync records a refusal and starts no agent. `launcher._unfinished` names the run and step only when the marker matches `SCOPE` and `STEP_SCOPE`, and otherwise keeps the old text.
- **Gates and decisions in operator state**: approvals, rejections, resolutions and mode changes are hash-chained HD entries under `state_dir`. That directory is refused when it lies inside the checkout or a temp root, and it is read-only inside bwrap (the confinement self-test probes writes there). `approve`, `reject` and `resolve` need a TTY, no active step, a passing precondition and an exact typed confirmation. The digest is computed again after confirmation (chat.py:2192-2194, 2284-2286). Gate state is computed when it is used, from digests. Nothing stores a pass or a "blocked" flag that an agent could write.
- **Intent**: `check_intent` with `run_id` set requires the block registered in operator state (`_approval_path`), so a block an agent writes into `intent.md` does not count. `Feature.from_operator_run` takes the baseline and resolutions only from the operator record. `check_decisions` for Chat counts only resolutions whose digest matches an HD.
- **Modes**: `_validate_mode_history` allows `switch` only for `ballast-chat` and only between chat and human-gated, and `lower` only from autonomous. Every switch needs a reason and an HD. A request for `autonomous` is refused and recorded. Failed checks keep blocking across switches because they are evaluated again on every request.
- **Interactive argv versus headless**: Claude gets `--permission-mode dontAsk`, the same `--setting-sources project --strict-mcp-config`, the same `CONFINED_ALLOW`/`CONFINED_DENY` as Autonomous, and a generated `--settings` whose allow and deny lists are a superset of the installed `claude-settings.json` (project rules included), plus `disableBypassPermissionsMode`/`disableAutoMode`. The settings file is written before the protected snapshot, under a read-only `.specify`. Codex gets `--sandbox workspace-write -a never`, network off, `writable_roots=[]`. `FORBIDDEN` tokens are refused in both the prompt and the model name.
- **TIOCSTI and the terminal descriptor**: the child calls `setsid` and then `TIOCSCTTY` on the pty slave, and gets only the slave on fds 0-2 (`close_fds=True`; the master, log, meta and lock fds are non-inheritable). bwrap `--unshare-pid --proc /proc --dev /dev` hides the wrapper's `/proc/<pid>/fd` and the host `/dev/pts`. TIOCSTI therefore reaches only the agent's own pty. `--new-session` is omitted only through `interactive_pty=True`. Raw mode is restored in the signal handler and in `finally`, with later signals ignored during close. Only SIGKILL of the wrapper leaves raw mode.
- **Protected inputs**: interactive steps snapshot and compare `agent._protected_state`, which covers `ballast.toml`, `.ballast/spec_workflow`, `.specify` minus the agent-writable entries, `.venv`, and a linked worktree's `.git` pointer. A change writes `BALLAST_TAMPERED` and exits 4. `.git` and the protected inputs are bound read-only. Late close attributes every change since `tree_before` to the step (`attribution: uncertain`) and never to the operator.
- **Paths**: run IDs, phases, kinds, gates, DEC IDs and models are validated against fixed patterns. Log directories are opened `O_NOFOLLOW` and written through directory handles. Operator logs use `O_NOFOLLOW`/`O_APPEND`. Artifact reads refuse symlinks. The unit name is checked against `SCOPE`.
- **Publication**: the publish path is the Autonomous one (pinned branch, origin check, attribute and filter driver refusal, protected and oversized paths refused, `--no-verify`, token variables withheld from agents). The Chat section is rendered from operator records, with agent-derived values passed through `_agent_value`. Conversation logs are never referenced in it.

Initial verdict (before fixes): changes requested.

## Resolution

I re-checked the findings against `git diff f7e91fb 110d8c8` (fix commit `110d8c8`). Locations are `path:line` in `110d8c8`. I read the code and the named tests but did not run the suite or any pilot.

### SEC-001 (high): installed skills writable by agents

- **Status**: fixed for confined steps (Chat interactive and Autonomous). Accepted residual for human-gated headless steps (pre-existing).
- **Evidence**:
  - `tools/spec_workflow/autonomy.py:1509` (`_installed_skill_binds`) binds each `.agents/skills/ballast-*` and `speckit-*` directory read-only, and `autonomy.py:1697` applies it in every `confined_argv`. The `.claude/skills/ballast-*` links resolve into those read-only binds.
  - `claude-chat-settings.json` adds `Edit(./.agents/skills/ballast-*/**)` and `Edit(./.agents/skills/speckit-*/**)` to the deny list.
  - Tests: `tests/test_autonomy.py:1134` `test_installed_workflow_skills_are_read_only`, and `tests/test_chat_mode.py:1395` `test_real_bwrap_keeps_installed_skills_read_only` (through `.agents` and through the `.claude/skills` link).
- **Agreement**: closed for every confined step. Remaining gaps:
  - A headless step in a Chat run switched to human-gated runs without bwrap, and its `claude-settings.json` has no `.agents` deny. That step (Codex in particular) can still rewrite a skill that a later Chat review step follows. Human-gated `ballast-feature` runs already have this exposure, so Chat adds no new exposure.
  - Recommended: add the installed skill directories to `agent._protected_state`, so that such a write fails the headless step as tampered. Record this as a follow-up; it is not in the plan's F-list today.
  - Minor: the `.agents/skills/` directory itself stays writable, so a new sibling skill directory can be added. A skill already linked as a symlink is skipped by the bind.
  - I do not consider these blocking for this feature.

### SEC-002 (medium): write-scope violations persist and do not block

- **Status**: fixed. Ignored paths are follow-up F-4.
- **Evidence**:
  - `tools/spec_workflow/chat.py:780` `_violations_check` is added to every phase entry (`chat.py:924-925`) and to the `implementation` and `final` preconditions (`chat.py:956`). `publish` re-evaluates the final precondition (`chat.py:3073`).
  - DEC-0003.
  - Test: `StepCloseTests.test_open_write_scope_violation_blocks_until_restored`.
- **Agreement**: closes the finding. Remaining gaps:
  - The check reads only the paths stored on the failed event, and those are capped at `PATH_LIMIT` (500, `chat.py:571`). A step that leaves more than 500 out-of-scope paths has the rest untracked once the listed ones are restored or changed. Low; recommend failing closed when the event has `more`.
  - Writes to ignored paths (for example `AGENTS.local.md`) stay undetected until F-4.

### SEC-003 (medium): prompts reachable inside a session

- **Status**: fixed for Claude. Accepted residual for Codex (DEC-0001, resolved and listed for the merge review).
- **Evidence**:
  - `tools/spec_workflow/chat_hook.py` blocks every tool call (exit 2) unless `permission_mode == "dontAsk"`, including on malformed input.
  - `claude-chat-settings.json` registers it as a `PreToolUse` hook for `*` and sets `disableAllHooks: false`. The step's `--settings` outranks a project `.claude/settings.json`.
  - Test: `tests/test_chat_mode.py:1361` `test_chat_settings_deny_prompts_outside_dont_ask`.
- **Agreement**: closes the Claude prompt path, but only as far as the hook actually runs:
  - Claude Code treats a hook exit code other than 2 as non-blocking. A hook that cannot start does not fail closed: for example, `python3` missing or shadowed on `PATH` gives exit 127 or 0.
  - Recommended hardening (low): give the generated settings an absolute path to the trusted interpreter instead of `python3` from `PATH`.
  - Whether the hook input carries `permission_mode` is unverified until pilot P-4. If it is missing, the hook denies everything (safe).
  - The Codex `/approvals` residual (network and command execution inside bwrap) is a deliberate operator command, not a prompt the agent raises. It is now stated in DEC-0001 and the shipped policy, and goes to the merge decision. I accept it as recorded.

### SEC-004 (medium): final and publish ignore `reviews/`

- **Status**: fixed.
- **Evidence**:
  - `chat.py:671` binds `final` to `tree_digest(root, ())`, with `reviews/` included.
  - `chat.py:261` requires the `scope`, `intent`, `plan`, `tasks` and `implementation` approvals to be current, in addition to `spec-reconciliation`.
  - `chat.py:3073` re-evaluates the whole final precondition at `publish`.
  - DEC-0002.
  - Tests: `PublishTests.test_a_review_changed_after_final_approval_blocks_publish` and `PublishTests.test_final_needs_every_earlier_approval_current`.
- **Agreement**: closes it.

### SEC-005 (medium): terminal control bytes in operator-facing text

- **Status**: fixed.
- **Evidence**:
  - The `resolve` body is printed line by line through `draft_pr.printable` (`chat.py:2579`).
  - `_safe` (`chat.py:1470`) is used for mode reasons, rejection refs, carried decision summaries and the Autonomous block condition. `_first_line` now escapes control bytes for check details and refusals.
  - Test: `tests/test_chat_mode.py:2671` `test_resolution_text_is_shown_without_control_bytes`.
- **Agreement**: closes it.

### SEC-006 (medium): terminal state after the session

- **Status**: partly fixed. Remainder accepted as a low residual.
- **Evidence**:
  - `agent.py:115` defines `TERMINAL_RESET` (alternate screen, mouse, focus and bracketed-paste reporting, cursor, keypad, SGR).
  - `agent.py:725-727` writes it and restores the attributes with `TCSAFLUSH`.
  - Test: `test_terminal_modes_the_agent_left_on_are_reset`.
- **Agreement**: closes the left-on modes and input already queued at close. Remaining gaps:
  - A terminal answer that arrives after the flush still reaches the shell, because there is no short drain before flushing.
  - OSC 52 clipboard writes, and output relayed raw during the session, are unchanged. The headless wrapper already has these; they depend on the terminal emulator.
  - Low; recommend a short drain before the flush and OSC 52 filtering as a follow-up.

### SEC-007 to SEC-010 (low)

- **Status**: unchanged.
  - SEC-007: the headless driver closes a step whose wrapper was killed and records `scope_stopped: True`.
  - SEC-009: two runs in one checkout can run steps at once and share the in-progress marker.
  - SEC-010: agent-created `.claude/settings.json` and `.codex/` are loaded by later steps.
  - SEC-008: earlier logs are readable by later agents. Follow-up F-4 covers ignored-path detection, not the hiding SEC-008 asks for, so SEC-008 stays open as a low.
- **Agreement**: none of these is critical, high or medium. They should be tracked, with SEC-007 and SEC-009 first, because they affect attribution and the unfinished-step refusal.

### Summary

No critical, high or medium finding remains open in the Chat-specific paths. The residuals are recorded as low or as accepted decisions:
- headless skill writes (pre-existing in human-gated runs);
- the Codex `/approvals` residual (DEC-0001);
- the hook's dependence on `python3` from `PATH`;
- post-flush answerbacks and OSC 52;
- the 500-path cap;
- F-4.

- Verdict: approved
