# Contract: Chat step runner and interactive confinement

The trusted step runner is `chat.run_step`, called by `run.py` after the launcher has verified the checkout. The interactive launch lives in `agent.py` next to the headless one and reuses its containment helpers. Everything here runs operator-side, from the pinned `.ballast/spec_workflow/` that the trust baseline covers.

## Lifecycle of `ballast run step RUN PHASE`

| # | Action | On failure |
| --- | --- | --- |
| 1 | Take `runs/<run>/lock` (`fcntl.flock`, non-blocking). | Refuse (exit 2), naming the active step from `run.json`. |
| 2 | If `run.json.active_step` is set (the previous wrapper died and `discard-runs` cleared the marker), close it as `interrupted`, run its postcondition, and record both. This late close stores `tree_after` as the current tree manifest and sets `last_manifest`. It records `late_close: true` and `attribution: "uncertain"`: every change since `tree_before` is attributed to the step, so the step's write-scope check covers it. Attributing agent edits to the operator would hide them behind operator authority. It also records `protected_compared: false`, because the step-7 snapshot lived only in the dead wrapper's memory. Protection then rests on bwrap's read-only binds (interactive driver) and on the launcher baseline over `launcher.BASES` at the next invocation. Note that `autonomy.PROTECTED` covers all of `.ballast`, while `BASES` covers only `.ballast/spec_workflow`. | Recorded. The new step continues only if that close recorded `scope_stopped: true`. |
| 3 | Compare the tree with `last_manifest`. Record an `out-of-step-change` if they differ. | Never fails. |
| 4 | Branch synchronization (`starting=False`, Chat `rerun` text). | Print the existing block. Record a `sync` event and a `refusal`. Exit 1. No agent. |
| 5 | Evaluate the entry condition ([phase-graph.md](phase-graph.md)). | Record the `check` and the `refusal`, print the failing check, exit 1. No agent. |
| 6 | Choose the integration: `review` uses `review_integration`, otherwise the step's `-i integration` or the run's. Run `confinement_self_test`, and for Codex `codex_sandbox_nests`. | Refuse that integration with the reason (exit 2) and name the other integration when it is available. |
| 7 | Snapshot `tree_before` and the protected state. Write `active_step` to `run.json`, then the `start` step entry, then `in-progress` (unit name). | n/a |
| 8 | Run the agent: interactive (below) in `chat` mode, headless `agent.py` argv in `human-gated` mode. | n/a |
| 9 | When the session ends: `stop_scope(unit)` until systemd reports it gone, then `_stop_descendants()`. | Not confirmed: record `scope_stopped: false`, keep `in-progress`, exit 4. The launcher refuses until `discard-runs`. |
| 10 | Compare the protected state with step 7. | Changed: write `BALLAST_TAMPERED` with the paths, record `tampered`, exit 4. |
| 11 | Remove `in-progress`. Run the postcondition and the cumulative checks, then the write-scope check against `tree_before`. | Record the `check` events and outcome `failed`, exit 1. |
| 12 | Store `tree_after`. Write the `close` entry and clear `active_step`. For `review`, write the `review` event. Write the ledger `step` and `snapshot` events. Archive. Run the Draft PR checkpoint. | Archive and ledger failures are reported as today and never turn a failed step into a passing one. |

Steps 9–12 also run when the wrapper receives `SIGHUP`, `SIGTERM` or `SIGINT`, or when the operator presses the escape sequence `Ctrl-]` `Ctrl-]`. The outcome is then `interrupted` unless the postcondition passed after a normal agent exit. A second signal during steps 9–12 is ignored, as `agent.main` ignores a second `SIGINT`.

## Interactive argv (inside bwrap, inside the scope)

```text
systemd-run --user --scope --quiet --collect --unit=ballast-agent-<run>-<step> [--expand-environment=no] -- \
  bwrap <autonomy.confined_argv binds> [no --new-session, see below] -- \
  <agent argv>
```

**Claude:**

```text
claude --permission-mode dontAsk --setting-sources project --strict-mcp-config \
  --settings .specify/workflow-state/<run>/agents/<step>/claude-settings.json \
  [--model NAME] "<phase prompt>" \
  --allowedTools <agent.CONFINED_ALLOW> --disallowedTools <agent.CONFINED_DENY>
```

The prompt precedes the tool lists, which are variadic and would otherwise take it as a tool.

`claude-chat-settings.json` contains:

- every `allow` and `deny` rule of the shipped `claude-settings.json`;
- `Edit(./**)` and `Write(./**)` in `allow`;
- `permissions.disableBypassPermissionsMode: "disable"`;
- `permissions.disableAutoMode: "disable"`;
- deny rules for the installed `.agents/skills/ballast-*` and `speckit-*` skills;
- `disableAllHooks: false` and a `PreToolUse` hook (`chat_hook.py`, installed in `.ballast/spec_workflow/`) that blocks every tool call unless the session's `permission_mode` is `dontAsk`. Leaving `dontAsk` with Shift+Tab therefore never leads to a permission prompt ([DEC-0001](../decisions.md)).

`tools/setup` merges the project's `[agents.permissions]` rules into the installed `claude-settings.json` only. So before the protected-state snapshot, the step writes its own settings file in its log directory, which the agent sees read-only. That file holds the allow and deny rules of the installed `claude-settings.json`, project rules included, followed by those of `claude-chat-settings.json` (`agent.chat_settings`). A test keeps the deny list a superset of the installed headless settings, project rules included.

**Codex:**

```text
codex --sandbox workspace-write --ask-for-approval never \
  --config sandbox_workspace_write.network_access=false \
  --config sandbox_workspace_write.writable_roots=[] [--model NAME] "<phase prompt>"
```

**Both:**

- Any token containing a `FORBIDDEN` marker is refused before launch.
- The environment is `autonomy.confined_env`, plus `PYTHONPYCACHEPREFIX`, plus `guard/git` first on `PATH` with `BALLAST_GIT`.
- The bwrap binds are those of an Autonomous step, which bind the installed `.agents/skills/ballast-*` and `speckit-*` directories read-only (review finding SEC-001). In addition, `<root>/.claude` and `<root>/.codex` are bound read-only when they exist.

## Terminal

- **Pty**: the runner opens a pty (`os.openpty`). Its child calls `setsid()`, makes the slave its controlling terminal (`TIOCSCTTY`), duplicates the slave onto fds 0–2, closes every other descriptor, and executes the argv above. The parent never passes the operator's terminal descriptor to the child.
- **`--new-session`**: omitted only for this argv and only in this case. `confined_argv(..., interactive_pty=True)` is the only way to omit it, and `chat.run_step` is the only caller that passes `True`.
- **Relay**: the parent puts the operator's terminal in raw mode, saves its attributes, and restores them on every exit path (`finally`, signal handlers). It relays stdin to the pty master and the pty master to stdout, and writes the pty output to `stdout.log`. On `SIGWINCH` it copies the window size to the pty (`TIOCSWINSZ`). When the session ends it writes a fixed reset sequence (alternate screen off, mouse, focus and bracketed-paste reports off, cursor shown, normal keypad, default colors) and restores the attributes with `TCSAFLUSH`, discarding input the shell has not read yet (review finding SEC-006).
- **No terminal**: if stdin or stdout of `ballast run step` is not a TTY in `chat` mode, the step is refused with "Chat steps need a terminal; use `ballast run mode RUN human-gated` for headless steps".

## Log and `meta.json`

- **Directory**: `.specify/workflow-state/<run>/agents/<step>/`. It is opened as a directory handle before the agent starts, and files are created through it with `O_NOFOLLOW`.
- **`stdout.log`**: the raw pty stream.
- **`meta.json`**: run ID, feature, integration, model, role, phase, the argv (program name only for `argv[0]`), driver, `started_at`, `finished_at`, exit code, `protected_changes`, `stopped_descendants` and `scope_stopped`. These are the headless keys plus `phase`, `driver`, `model`, `role` and `scope_stopped`.
- Nothing from these files is copied into a PR, Issue or committed file.

## Launcher refusal text

`launcher._refusal` reads the `in-progress` marker. When its content matches `SCOPE` and splits into run and step, it returns:

```text
an agent step is active or did not finish: run <run>, step <step>; wait for it to end, or if no step is running, run `ballast discard-runs`
```

Otherwise it returns the current text. Both keep the refusal; only the wording changes.
