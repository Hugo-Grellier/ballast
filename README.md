# Ballast

Ballast keeps a repository steady while AI coding agents move fast. It is a reusable, repository-level baseline: a Spec Kit feature workflow with deterministic artifact checks, a bounded headless-agent runner, review skills, engineering policies, and agent instruction templates.

This repository is the source of the standard. Projects pin a version and install it into git-ignored paths with `ballast setup`; only `AGENTS.md` and the PR template are copied once, because agents and GitHub read them from committed files.

## Repository map

- [`specs/PRODUCT-SPEC.md`](specs/PRODUCT-SPEC.md) describes the users, problem, goals, and product boundaries.
- [`specs/TECHNICAL-SPEC.md`](specs/TECHNICAL-SPEC.md) describes the repository structure and the conventions for template content.
- [`tools/ballast`](tools/ballast) is the global command; [`tools/setup`](tools/setup) installs Spec Kit and the standard into a project; [`tools/spec_workflow/`](tools/spec_workflow/) holds the validators, agent wrapper, trusted launcher and run ledger; [`tools/feature_intake.py`](tools/feature_intake.py) is the GitHub intake helper, run as `ballast intake`.
- [`templates/policies/`](templates/policies/) are the base policies installed into `docs/policies/`; [`templates/skills/`](templates/skills/) are the `ballast-*` skills; [`templates/spec-kit/`](templates/spec-kit/) holds the feature workflow and Spec Kit templates.
- [`templates/AGENTS.md`](templates/AGENTS.md) and [`templates/github/`](templates/github/) (PR template, Dependabot configuration, Conventional Commit PR-title workflow) are copy-once templates. Stack-specific CI stays in each project.
- `profiles/` is reserved for curated combinations of templates and will be added later.

## Using the copy-once templates

Review each template before copying it into a project. Replace project-specific placeholders, remove guidance that does not apply, and keep the resulting instructions close to the code they govern. Treat templates as a starting point, not as a substitute for the target project's own conventions.

## Installing the Ballast CLI

Once per machine, run this line. It downloads the `ballast` command of one release and its SHA-256 checksum into a fresh directory under `/tmp`, checks the checksum, and installs the command as `~/.local/bin/ballast`; on a mismatch or a failed download it installs nothing. It reads nothing from the current directory, so it is safe to run inside any checkout.

<!-- x-release-please-start-version -->
```sh
(c=$PATH; PATH=/usr/local/bin:/usr/bin:/bin; v=v0.6.0; u=https://github.com/Hugo-Grellier/ballast/releases/download/$v; d=$(TMPDIR=/tmp mktemp -d) && { curl -q -fsSL -o "$d/ballast" "$u/ballast" && curl -q -fsSL -o "$d/ballast.sha256" "$u/ballast.sha256" || { echo "ballast: cannot download $v from $u; nothing installed" >&2; false; }; } && { [ "$(cut -d" " -f1 "$d/ballast.sha256")" = "$(sha256sum <"$d/ballast" | cut -d" " -f1)" ] || { echo "ballast: checksum mismatch for $v; nothing installed" >&2; false; }; } && BALLAST_CALLER_PATH="$c" /usr/bin/python3 -I -S "$d/ballast" self-install)
```
<!-- x-release-please-end -->

If the download fails with 404, that release predates the installer; use the developer fallback below.

Then check the machine and, from a project root, the project:

```bash
ballast --version
ballast doctor            # add --json for a machine-readable report
```

`ballast doctor` is read-only: it downloads and writes nothing. It reports each prerequisite as passing, missing, unsupported or inconclusive, names the commands each gap blocks and gives the exact fix, and exits 1 while any command is blocked. Its checks are the authoritative prerequisite list; in summary:

- `python`: `/usr/bin/python3` 3.11 or newer, which runs every Ballast tool.
- `cli-on-path`: the `ballast` command on `PATH`.
- `git` (2.41 or later, which branch synchronization needs), `uvx` and `patch` for `ballast setup`, and `network`: HTTPS access to GitHub and PyPI the first time a version is fetched.
- `linux`, `systemd-user` and `systemd-run`: headless agent steps of `ballast run` need Linux with a systemd user session that can start transient scopes.
- `specify` (the Spec Kit CLI) and `agent-cli` (Claude Code or Codex) for `ballast run`; `agent-cli` also reports where agents can write, which Ballast never trusts for programs or state.
- `gh`, authenticated, for issue intake and PR steps.

Inside a project it also checks the pin in `ballast.toml`, whether that version is fetched, the CLI version it needs, whether setup is current, and whether the launcher would refuse until `ballast trust`.

To develop the standard itself, install from a reviewed checkout of this repository instead: `install -m 0755 tools/ballast ~/.local/bin/ballast`.

## Installing the Spec Kit workflow

`tools/setup` installs pinned Spec Kit sources and this standard's workflow tooling into a project. Everything it writes is rebuildable and git-ignored; the project commits only its own files. Projects reach it through one global command:

1. Once per machine, install the `ballast` command (see [Installing the Ballast CLI](#installing-the-ballast-cli)) and run `ballast doctor`.
2. Add `ballast.toml` at the project root. It pins the standard version (a tag or commit) and can extend the headless-agent permissions:

   ```toml
   [standard]
   ref = "v0.1.0"

   [agents.permissions]
   extra_allow = ["Bash(./scripts/check)"]
   extra_deny = ["Edit(./private/**)"]
   ```

   Headless Claude agents run only the Bash commands these rules and the standard's base list name, so list the project's checks here; Codex runs any command inside its sandbox. Rules match the command text: `*` matches anything, and a command with a leading `VAR=value` never matches, so write checks without one. Autonomous steps, which bubblewrap confines, may also run `ls`, `cat`, `head`, `tail`, `wc` and `find` without `-exec` or `-delete`.

3. From the project root, run `ballast setup`. It downloads the pinned version once into `$XDG_DATA_HOME/ballast/standard/<ref>/` with a record of its content, checks the cached copy against that record before every setup, then runs its `tools/setup`. On the first run, add the ignore block it prints to the project's `.gitignore`; the block keeps `.specify/memory/constitution.md` tracked. Setup needs `git`, `uvx`, `patch`, and network access to GitHub; `ballast doctor` checks them.

The result is Spec Kit with its bugfix and assess bundles, the multi-model-review, status-report and intent extensions, the explicit-task-dependencies preset, the `ballast-feature` workflow and its tools under `.ballast/`, the `ballast-*` skills under `.agents/skills/` (linked from `.claude/skills/`), and the standard's policies under `docs/policies/`. Project-specific additions go in `docs/policies/project/`, which setup never touches. Setup builds the new installation beside the current one under `.ballast/setup/`, validates it, then switches it in; a failed or interrupted setup keeps the previous installation (see [Updating the pinned version](#updating-the-pinned-version)). A rerun at a current pin changes nothing and downloads nothing. Setup never touches `.specify/workflows/runs/`, the project constitution or `docs/policies/project/`.

### Worktrees

The first `ballast run`, `ballast ledger` or `ballast intake` in a new Git worktree prepares its installation without a separate `ballast setup` and without downloading: it copies an installation already on this machine for the same repository (the primary checkout's, another worktree's, or a kept previous one) whose pin and `ballast.toml` match and whose files, execute bits included, still match the record setup kept of it. Then it stops at the trust check, naming the protected inputs to review: trust is per worktree, so run `ballast trust` there. Run state is never copied between worktrees. The first worktree at a new pin or `ballast.toml` still needs `ballast setup`, which may download; later ones are prepared from it. `ballast setup` in a worktree also copies the primary checkout's installation when it matches its record.

### Running the workflow

Headless agent steps need Linux with a systemd user session. The operator entry point must live outside the checkout, because an agent can rewrite anything inside it. `ballast` therefore runs the launcher of the project's pinned version from `$XDG_DATA_HOME/ballast/standard/<ref>/`, never from the checkout:

```bash
ballast trust                 # from the reviewed project root
ballast run start|resume ...
ballast ledger snapshot|check|report ...
```

Only `setup` and `preview` download; the other commands refuse a version that is not fetched yet. The repository is fixed in `ballast`, so `ballast.toml` chooses a version, never a source. Run `trust` again after reviewing any change to `ballast.toml`, `.ballast/`, `.specify/` or `.venv/`, including a rerun of setup. To work on the standard itself, set `BALLAST_STANDARD_DIR` to a local checkout. The launcher refuses to run while those inputs differ from the trusted baseline, while an `BALLAST_TAMPERED` marker exists, or after an agent step that did not finish its check. Its baseline and the agent run ledger live in `$XDG_STATE_HOME/ballast/`.

Before the first agent step of every `ballast run start`, `resume` or `continue`, and of every Chat `step`, the launcher rebases the run's feature branch onto its base when that is safe, or stops before any agent with `BLOCKED_UPSTREAM_SYNC` and one recovery action; the [Branch synchronization section of the Spec Kit workflow policy](templates/policies/spec-kit-workflow.md#branch-synchronization) lists the causes and their recovery.

At the end of every `ballast run start`, `resume` or `continue` invocation, after any Autonomous publication, the launcher makes sure one Draft PR shows an issue-linked feature once its published branch holds a change outside `specs/<feature>/`, and reuses that PR afterwards. It needs `[github] repository = "OWNER/NAME"` in `ballast.toml`, uses your authenticated `gh` 2.48 or later, never pushes (only an Autonomous run's publisher does), and never marks a PR ready, merges or closes it. The [Draft PR section of the Spec Kit workflow policy](templates/policies/spec-kit-workflow.md#draft-pr) lists the reported states and their remedies. The same Draft PR carries an [acceptance packet](templates/policies/spec-kit-workflow.md#acceptance-packet): each acceptance criterion's evidence state at the head commit, the run's decisions, open findings and checks, and links to every source; it is a derived summary, not an approval.

### Autonomous runs

An eligible feature can run unattended to a Draft PR. Every gate decision is then recorded as agent-provisional, and merging the PR is the single human approval. Eligible means a scoped leaf Issue (its intake scope comment has `Risk: R0|R1|R2` and `Privileged actions before merge: none` or an authorized action), started from a feature branch named for the Issue with no open PR. Autonomous needs `bwrap` (bubblewrap) with user namespaces on the host, because every agent step and check runs confined; a missing `bwrap` refuses the start. It also needs the `[github] repository` pin described above: eligibility and publication use only that repository, and `origin` must be it.

```bash
ballast run start --mode autonomous [--wall-time MINUTES] [--max-agent-steps N] \
    -i issue=N -i idea="Issue #N: OUTCOME" -i feature_directory=specs/N-slug [-i integration=auto]
ballast run continue RUN_ID --reason block-resolved|changes-requested --ref TEXT
ballast run publish RUN_ID
```

`--wall-time` (1–1440 minutes, default 240) and `--max-agent-steps` (1–200, default 30) are accepted only with `--mode autonomous`. An ineligible start is refused before any agent step and prints the human-gated command instead. A run ends with a Draft PR or with a block that names its reason and the recovery command. `ballast run resume` refuses an Autonomous run; `continue` records the operator's decision, lowers the run to human-gated and starts the remaining human gates. `publish` retries a failed publication without running an agent. Nothing in an Autonomous run merges, marks a PR ready, releases or deploys.

Two `ballast.toml` tables configure it:

```toml
[autonomous]                              # optional; can only narrow eligibility
risk = ["R0", "R1"]
excluded_boundaries = ["agent authority"]
authorized_privileged_actions = ["secret provisioning"]
wall_time_minutes = 120
max_agent_steps = 24

[checks]                                  # required for Autonomous
commands = ["uvx ruff check", "uv run python -m unittest"]
timeout_minutes = 30
```

Keys that would widen eligibility, and `merge`, `release`, `deploy` or `mark ready` as authorized actions, are ignored with a warning. The `[checks]` commands run confined before final acceptance; a failure blocks publication. Agents can run them while implementing only if `[agents.permissions] extra_allow` covers each one; `ballast doctor` reports any it does not as `checks-allowed`. Run `ballast trust` after changing either table.

### Chat runs

Chat mode lets you work through a feature in conversation, one step at a time, while Ballast keeps the guarantees of a headless run: the trusted preflight and branch synchronization before every agent step, the same confinement, the artifact postconditions, the run record and the human approvals. Each action is one `ballast run` command:

```bash
ballast run start --mode chat -i feature_directory=specs/N-slug [-i idea="Issue #N: OUTCOME"]
ballast run step RUN_ID PHASE [--kind KIND]   # specify, clarify, plan, tasks, analyze, implement, ...
ballast run status RUN_ID                     # where the run stands and what is allowed next
ballast run approve RUN_ID GATE               # from your terminal; reject ... --reason TEXT
ballast run resolve RUN_ID DEC-NNNN
ballast run checks RUN_ID
ballast run mode RUN_ID chat|human-gated --reason TEXT
ballast run publish RUN_ID
```

A step is an interactive Claude or Codex session for one phase. It runs with the headless permission rules (anything else is denied, never prompted) under the same `bwrap` confinement as an Autonomous step, so Chat needs `bwrap` too. When the session ends (`/exit`, or `Ctrl-]` twice), Ballast confirms the agent is gone and checks the phase's artifact. Every gate needs your `ballast run approve` from a terminal; nothing the agent writes or says approves anything. Leave whenever you like: `status` and the next `step` pick the run up later, from any terminal, after the full preflight. `ballast run continue RUN_ID ... --mode chat` continues a stopped Autonomous run in Chat. Conversation logs stay local. Working in a plain agent session outside `ballast run` gives none of these guarantees.

### Updating the pinned version

Pin changes stay manual and reviewed in Git. Update the `ballast` command first (see [Installing the Ballast CLI](#installing-the-ballast-cli)): verified downloads of the standard and `ballast preview` come with the CLI, not with the pinned version, so an older CLI does without them.

```bash
ballast preview vX.Y.Z      # what moving the pin would do; changes nothing
# set ref = "vX.Y.Z" under [standard] in ballast.toml, review and commit it
ballast setup               # the previous installation stays until the new one verifies
ballast trust               # after reviewing the changed protected inputs it lists
```

Then run the project's checks. `ballast preview` (add `--json` for scripts) names the pinned, installed and target versions and the CLI version the target needs, lists each unfinished run with whether the target can resume it, the installed paths it would add, change or remove, any ignore-rule change, and the exact steps above. It builds the target in a disposable directory, so it may need network, and exits 1 when something must happen first, such as finishing or discarding a run the target cannot resume.

When setup fails, it says which stage failed, that the previous installation was kept, and what to do next. At an unchanged pin nothing else is needed: the existing trust still holds and a paused run resumes. If setup was interrupted, every other command refuses until the next `ballast setup`, which first restores the previous installation or completes the new one and says which. A second `ballast setup` in the same checkout refuses while one runs.

**Retry after a failed update.** With the new pin, the launcher and `ballast doctor` name the pinned and the installed versions. Fix the cause (`ballast doctor` checks network access and tools), then run `ballast setup` again.

**Roll back to the previous pin.** Restore the previous `ref` in `ballast.toml` (for example `git checkout HEAD~1 -- ballast.toml`), review and commit it, then:

```bash
ballast setup               # reuses the previous installation and the cached version: no download
ballast trust               # nothing is trusted for you
```

The constitution, `docs/policies/project/`, paused runs and their archives are untouched. Versions released before this feature (v0.5.0 and earlier) run their own, older setup: a failure there can still leave the checkout without a usable installation, and `ballast preview` says so. A version cached by an older CLI is downloaded again once.

## Dogfooding

This repository installs Ballast like any project: `ballast.toml` pins a released version, `AGENTS.md` comes from the template, and Ballast-specific rules live in `docs/policies/project/` and `.specify/memory/constitution.md`. CI installs the working copy into the repository on every PR and fails if the install leaves any file that is not ignored.

## Releases

Release Please opens a release PR from Conventional Commit titles on `main`; merging it tags `vX.Y.Z`, updates `CHANGELOG.md`, `version.txt`, the CLI's `VERSION` and the install line above, and publishes the GitHub release. A follow-up job attaches the unchanged `tools/ballast` and its `ballast.sha256` to that release, for the install line. Projects pin those tags in `ballast.toml`. The workflow needs a `RELEASE_PLEASE_TOKEN` repository secret (a fine-grained token with contents and pull-request write access) so its release PR runs CI.

## Status

Draft, backported from LoreForge. The [backport plan](docs/plans/2026-09-28-loreforge-backport.md) tracks parity before the first release; profiles are not yet defined.
