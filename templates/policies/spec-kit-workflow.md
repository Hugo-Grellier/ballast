# Spec Kit workflow

This workflow is for interactive work with Claude Code, Codex, or another
supported Spec Kit integration. The human chooses the model for each role,
using the [model routing policy](model-routing.md) when model
choice is under operator control.
Feature artifacts committed to Git are the durable record; Issues track work,
discussion, and status. Spec Kit's workflow runner is an optional way to walk
through the same stages and pause at human gates, not a supervisor or source of
feature intent.

## Authority and repository layout

| Artifact | Owns |
|---|---|
| The project's domain glossary, accepted architecture documents, ADRs, and `docs/policies/` (including `docs/policies/project/`) | Project language, accepted architecture, durable decisions, and engineering rules. Feature work cites these documents; it does not copy them. |
| `.specify/memory/constitution.md` | Cross-feature principles and invariants used during Spec Kit planning. |
| `specs/<issue-number>-<slug>/intent.md` | Human-approved outcome, constraints, non-goals, and success evidence for one feature. |
| `specs/<issue-number>-<slug>/spec.md` | User behavior, scope, scenarios, and stable `AC-NNN` acceptance criteria. |
| `specs/<issue-number>-<slug>/plan.md` | Technical approach, affected boundaries, data flow, trade-offs, migrations, and verification seams. |
| `specs/<issue-number>-<slug>/tasks.md` | Executable tasks, explicit dependencies, execution waves, and acceptance-evidence links. |
| `specs/<issue-number>-<slug>/decisions.md` | Append-only proposals and resolutions discovered during implementation. Create when a decision is needed. |
| `specs/<issue-number>-<slug>/reviews/` | Material peer-review findings, dispositions, and convergence report. |
| GitHub Issue and PR | Tracking, discussion, dependencies, implementation status, verification summary, and merge review. They link to accepted feature artifacts; they do not override them. |

Do not promote current code into a specification just because it exists. When
code and an approved artifact disagree, first determine whether the code is
defective or implementation has uncovered a real decision. Record and resolve
that decision before changing authoritative artifacts.

Feature plans should describe only boundaries the feature touches. Use the
current areas and terminology of the accepted architecture, listed in
[`project/spec-kit-workflow.md`](project/spec-kit-workflow.md) when the project
provides one, as a map, not as a frozen package layout. Name owners and
contracts across affected areas. A feature decision cannot supersede an
accepted ADR; a project-wide architecture change also needs a reviewed ADR.

## Scope and decomposition gate

Decide the work's granularity **before `speckit.specify`**, whether using the
workflow runner or working manually:

```text
GitHub Milestone (planned release target, e.g. v1.0)
  └─ Epic / parent Issue (roadmap capability)
       └─ feature Issue (one independently specifiable outcome)
            ├─ specs/<issue-number>-<slug>/ (intent, spec, plan, tasks)
            └─ optional substantial sub-issues (ownership/dependency slices)
                 tasks.md remains the fine-grained implementation breakdown
```

Roadmap capabilities, such as numbered milestones in an architecture document,
are tracked as Epics, not as GitHub Milestones.

A Milestone groups planned work; the project's release process still creates
the actual version, tag, and release. An Epic coordinates child Issues
and their dependencies. It may have a shallow `docs/roadmap/<epic-slug>.md`
when the child map needs a durable explanation, but the Epic itself has no
complete `spec.md`, `plan.md`, or `tasks.md`. Each child feature runs the full
Spec Kit lifecycle and normally maps 1:1 to `specs/<issue-number>-<slug>/`.

An Issue is one feature when it has one main outcome, a clear in/out boundary,
acceptance criteria that belong together, a cohesive design, and can be
reviewed and tested independently. If it contains independently useful
outcomes, largely independent subsystems or acceptance-criterion groups, or
needs separate implementation plans, classify it as an Epic. Keep the parent
as the coordination/history object, create child Issues, and record child
dependencies in GitHub. Record the scope classification, main outcome, and
in/out boundary in the Issue or a short comment before applying
`ready-for-agent`; for an Epic, link its child map there. Task count is not a
split rule: a cohesive feature can have many tasks executed in dependency-safe
waves. Create a GitHub sub-issue only for a substantial slice that benefits
from separate ownership, dependency tracking, or parallel visibility;
individual `tasks.md` entries remain tasks. A sub-issue links its parent
feature spec; if it grows into an independent outcome, treat it as a separate
feature Issue with its own spec.

Recheck scope after `speckit.clarify`, `speckit.plan`, and `speckit.tasks`. If
independent outcomes emerge, stop the parent feature run. Preserve its Issue
and discussion, create child Issues and feature directories, and explicitly
move each requirement and acceptance criterion to its new authority. Link the
children and record dependencies; do not leave conflicting parent and child
specifications. Resume the full lifecycle on each child. A human resolves any
material change to already approved intent before its artifacts are revised.
If a parent draft was already written, mark it superseded and preserve its Git
history; active requirements move to child specs, while the parent Issue stays
the coordination record.

The [feature-intake skill](../../.agents/skills/ballast-feature-intake/SKILL.md) applies
this gate before the existing workflow. It uses
`.ballast/feature_intake.py --repo OWNER/REPO preflight N` as a read-only leaf
check before feature handoff. The helper rejects explicit Epic signals, closed
or blocked issues, and missing acceptance criteria. Scope judgment still
requires the issue and its accepted context; a mechanical check cannot decide
whether an unmarked broad request is one cohesive feature.

For approved setup, the same helper's `prepare` command can create or reuse
one child, link it to its parent, add a scope-gate comment, and add
`ready-for-agent`. It reads live state before each step and verifies the
result; a failure reports completed and pending steps as JSON. Retry with the
same parent and child slug after inspecting the issue. A conflicting child,
parent or scope comment stops for review. It preserves unrelated labels,
milestones and Project fields, and Project auto-add remains responsible for
Project membership. `gh` authentication is required for live GitHub writes.

## Choose a workflow path

| Work | Path |
|---|---|
| New feature or meaningful behavior change | Full `ballast-feature` lifecycle below. |
| Eligible feature the operator chooses to run unattended | `ballast-autonomous`: the same lifecycle with agent-provisional decisions instead of human gates, ending in a Draft PR (see [Autonomous runs](#autonomous-runs)). |
| Small bug with a narrow fix | Official `bugfix` bundle: assess the report, review its proposed fix at a human gate, then fix and verify. Keep the Issue as the tracker and avoid creating a full feature spec. Promote to a feature if intent, contract, scope, or architecture changes. |
| Investigation, spike, or architectural research | Official `assess` bundle for intake, research, shaping, and a human verdict. If findings should persist, write a focused note under `docs/research/`. A `go` verdict is a request to start a feature spec, not approval to implement. |

Completed work and existing issues are not retrofitted. For new significant
features, link the feature directory from the Issue. A small issue may carry its
own reproduction and acceptance criteria; it remains subordinate to any
accepted feature spec it supports.

## Full feature lifecycle

```text
Milestone → Epic (if needed) → candidate Issue → scope gate → feature Issue
    ↓
specify → clarify
    ↓
HUMAN GATE: approve intent.md
    ↓
plan
    ↓
peer model reviews spec + architecture → HUMAN GATE: approve plan
    ↓
tasks → analyze → check dependencies and execution waves
    ↓
implement ready waves
    ↓
peer model reviews diff against spec → reconcile discoveries
    ↓
corrections → tests / checks / CI → converge
    ↺ repeat implementation and review when needed
    ↓
HUMAN GATE: final acceptance
    ↓
PR → Issue update → human merge review
```

1. **Scope, specify, and clarify.** Confirm the tracking Issue is one
   independently specifiable outcome. Use Spec Kit to draft `spec.md`, assign a
   stable `AC-NNN` ID to each acceptance scenario, and resolve blocking
   questions. Read the relevant project context and ADRs; do not copy entire
   product or architecture documents into the feature. Revisit scope if
   clarification reveals separate outcomes.
2. **Approve intent.** A human approves the clarified `spec.md` as the
   feature's intent. In the workflow runner, the `approve-intent` gate shows
   `spec.md`; approval makes a deterministic step write `intent.md` with an
   approval record bound to that spec's digest. Interactively,
   `speckit.intent.confirm` drafts `intent.md` and asks for approval. A draft,
   silence, model confidence, or passing test is not approval, and a later
   `spec.md` change makes the approval stale. Material changes to product
   outcome, public contract, identity, visibility, data migration, or
   architecture require explicit human resolution before implementation.
3. **Plan and peer-review.** The author creates `plan.md`. If planning needs
   independent plans, return to decomposition. A different model
   reviews the spec, intent, plan, and cited architecture in a fresh context.
   Record material findings in `reviews/plan.md`; the author resolves or
   escalates them. The human approves the plan before task generation.
4. **Create and analyze tasks.** Generate `tasks.md`, then run
   `speckit.analyze`. Every behavior acceptance criterion must map to a test or
   explicit verification task that cites its `AC-NNN` ID. Use
   `(depends on T###)` for real prerequisites and check the Execution Wave DAG
   against those dependencies. `[P]` means tasks can proceed together after
   prerequisites; it is not permission to skip them. Do not invent setup,
   architecture, or test tasks that the feature does not need. Revisit scope
   if tasks expose independent outcomes; a long cohesive task list stays one
   feature and uses execution waves.
5. **Implement in dependency-safe waves.** Before editing, read the active
   feature's `intent.md`, `spec.md`, `plan.md`, `tasks.md`, and unresolved
   `decisions.md`, plus relevant policies and ADRs. Implement only ready tasks.
   Use `speckit.intent.implement` when invoking Spec Kit implementation. Direct
   interactive edits are also supported; run intent confirmation before a
   slice and decision reconciliation after it. Never use implementation as
   authority to change the spec.
6. **Cross-model review.** A different model reviews the changed behavior and
   diff against the approved artifacts. It may be Claude, Codex, or another
   available model; no model owns a permanent author or reviewer role. Findings
   distinguish: spec violation, implementation bug, architecture issue,
   missing test, spec ambiguity, and proposed product change. Save material
   reports and dispositions in `reviews/`.
7. **Reconcile discoveries.** Run `speckit.intent.decisions` on meaningful
   implementation discoveries. Agents may fix defects against approved intent,
   add missing evidence for an existing criterion, and clarify wording without
   changing behavior; these need no proposal. Every other discovery, including
   a new technical choice within approved intent, is appended as a proposal
   and needs a human resolution before `plan.md` or other affected artifacts
   change. Changes to intent or product behavior require human approval;
   update `intent.md` first, then align the spec, plan, tasks, tests, and code.
   Unsupported drift is reverted. Material architecture changes also require
   an ADR.
8. **Verify and converge.** Run the project's fast check command and its full
   local gate when the engineering workflow requires it. CI results are evidence, not product approval. Run
   `speckit.converge` and the spec reconciliation review. Record `CONVERGED`,
   `PARTIAL`, or `FAILED` in `reviews/convergence.md`. Convergence means every
   accepted criterion has evidence; implementation, tests, and docs match the
   approved intent and spec; tasks and review findings are resolved; decisions
   have resolutions; and unavailable checks are stated. For `PARTIAL` or
   `FAILED`, add or update tasks and repeat the implementation/review loop.
   Escalate after three unsuccessful correction cycles.
9. **Accept and merge.** The human gives final acceptance after convergence.
   The PR links the Issue, feature artifacts, review reports, risk, checks,
   migration/security impact, and limitations. Human review and merge remain
   required at every risk level.

The native `.specify/workflows/ballast-feature/workflow.yml` makes these
stages repeatable and pauses at intent, plan, task-readiness, implementation
review, spec-reconciliation, and final-acceptance gates. With
`on_reject: retry`, rejection pauses at the **same gate**; resuming does not
rerun earlier commands. Before resuming, revise the affected artifacts and
manually rerun the commands and reviews named in that gate's message. For task
revisions, rerun `speckit.analyze`; for implementation or final-acceptance
revisions, rerun affected checks, decision reconciliation, peer review, and
convergence as applicable. Approve only after the new evidence is recorded.
Workflow run state under `.specify/workflows/runs/` is local resume state. After
each start or resume, `run.py` copies the full run state and agent logs to
`$(git rev-parse --git-common-dir)/speckit-runs/<run>/`, which outlives the
worktree and stays outside Git tracking. Do not commit per-run files. Resume a
run only in the worktree that started it. Running stages manually in the IDE is
always supported.

## Workflow runner contract

A command step's exit code 0 only means the agent process ended. A phase
succeeds only when its artifact contract holds: every producer is followed by a
`validate-*` shell step running `.ballast/spec_workflow/artifacts.py`, and a
failed contract fails the run, so no later gate or command is reachable. Checks
are cumulative: each re-verifies the upstream artifacts it relies on. The
validator reads `feature_directory` from the run's inputs, requires
`specs/<issue-number>-<slug>`, and refuses symlinks or paths outside it.

| Phase | Required output | Valid when |
|---|---|---|
| specify | `spec.md` | Exists in the requested feature directory, non-empty, no spec-template placeholders. |
| clarify | `spec.md` | Also no `[NEEDS CLARIFICATION` marker. |
| intent approval | `intent.md` | Written only after the `approve-intent` gate; has the intent sections and one approval record whose spec digest matches the current `spec.md`. |
| plan | `plan.md` | Intent still valid; non-empty; no plan-template placeholders or unresolved clarification. |
| tasks | `tasks.md` | Plan still valid; at least one `- [ ] T###` task, unique IDs, every `(depends on T###)` names an existing task. |
| implement | repository change | Every task checked and a path outside the feature directory changed since the pre-implementation baseline, or `tasks.md` declares `<!-- workflow: no-code-change -->` (visible at the task gate). |
| decisions | `decisions.md` (optional) | Every `DEC-NNNN — Proposal` has a matching resolution. |
| convergence | `reviews/convergence.md` | All of the above, no pending task (converge appends none), and the latest `- Verdict:` line is `CONVERGED`. |

The `approve-intent`, `review-plan`, `review-tasks`, and `final-acceptance`
gates show the artifact they approve (Spec Kit truncates the display at 200
lines; open the file for the rest). Peer reviews and spec reconciliation are
**manual**: the gates say so and the workflow does not claim they ran.
Approving an intent change outside the gate means reviewing `spec.md` and
running `.ballast/spec_workflow/artifacts.py record-intent --feature <dir>`.
Human-only steps a headless agent cannot finish—clarification questions,
decision resolutions, convergence verdicts—surface as a failed validation;
complete them interactively and resume.

**Trusted launcher.** A headless agent can rewrite any file in the checkout,
including the launcher itself, so the operator entry point lives outside it.
The global `ballast` command runs the launcher of the standard version
pinned in `ballast.toml`, from the copy `ballast setup` fetched into
`$XDG_DATA_HOME/ballast/standard/<ref>/`, never from the checkout. Install that
command once per machine from a reviewed checkout of the standard.

From the checkout root, after reviewing it (for example right after a pull, a
dependency sync, or a `tools/setup` reinstall), record a baseline with
`ballast trust`. It stores the digests of `ballast.toml`,
`.ballast/spec_workflow/`, `.specify/` (except run state, logs,
`feature.json`, bug reports and caches), `.venv` and, in a linked worktree, the
`.git` pointer file (a redirected pointer could make the operator's Git run a
forged repository's configuration) under
`$XDG_STATE_HOME/ballast/` (default `~/.local/state`), where no agent can
write. `ballast run ...` and `ballast ledger ...` then
refuse, before executing any checkout code, if those inputs changed since
`trust`, if `BALLAST_TAMPERED` exists, or if an agent step never finished its
check (for example because the agent killed the wrapper). Saved run state is
not in the baseline, so after an unfinished step `trust` also refuses: review
the checkout, run `ballast discard-runs`, then `trust` and start a
fresh run. `discard-runs` first kills the unfinished step's agent scope (see
below) and refuses unless systemd confirms it is gone, so no surviving agent
process can rewrite state afterwards; only then does it delete the local run
state (the archived copy in the Git common directory remains). It never follows
a link on the way to that state. A primary checkout's `.git` directory is not hashed; it
relies on the agent sandbox keeping it read-only. They run `run.py` and
`ledger.py` under the launcher's own `/usr/bin/python3 -I -S`.
Bytecode is excluded from the baseline because no workflow tool reads it.

**Headless permissions.** Start and resume runs only with
`ballast run`; a `preflight` step fails otherwise. It routes
Spec Kit's dispatch through `.ballast/spec_workflow/agent.py`, which refuses
any `dangerously`/`bypassPermissions`/`danger-full-access` flag, including
from `SPECKIT_INTEGRATION_*_EXTRA_ARGS`:

- **Claude** runs `claude -p` with `--permission-mode acceptEdits`,
  `--permission-prompts none` (anything not allowed is denied, never
  prompted), `--setting-sources project`, `--strict-mcp-config`, and
  `.ballast/spec_workflow/claude-settings.json`. User settings, plugins, hooks,
  and MCP servers are not loaded. File edits are accepted inside the checkout
  except `.env`/`*.local.md`, CI and agent configuration, `ballast.toml`, the
  workflow machinery itself, and paths the project denies in `ballast.toml`;
  Bash is limited to the Spec Kit scripts, read-only Git, and the commands the
  project allows there.
- **Codex** runs `codex exec --sandbox workspace-write`: writes are confined to
  the checkout and temporary directories, network access is pinned off, and
  approvals are never requested. Codex still loads the user's Codex
  configuration, and user Codex hooks run for workflow workers; these flags
  override its sandbox. Codex cannot express Claude's per-path denials, so the
  wrapper hashes the run state, `.specify/workflow-state/<run>/`, the installed
  Spec Kit configuration, extensions, scripts and workflows under `.specify/`
  (except `feature.json`, other runs and caches), `.ballast/spec_workflow/`
  including its bytecode, and the whole `.venv` before and after every agent
  call and fails the step if any of them changed. Still review the diff for CI
  changes.

Both integrations get the same executable-input guard. The agent runs with
`PYTHONPYCACHEPREFIX` outside the checkout, so a legitimate test run leaves no
bytecode behind; a changed `__pycache__` or `.venv` file therefore fails the
step. An agent must not sync dependencies or otherwise change `.venv`; after a
dependency change, the operator reviews the lockfile and syncs. The wrapper
needs Linux and a systemd user manager, and refuses to start without them. It
starts the agent in its own `systemd-run --user --scope` unit, a cgroup the
agent cannot leave (Codex's sandbox denies writes to `/sys/fs/cgroup`), and
records the unit name in the launcher's state directory. After the agent exits
it kills the whole scope, waits until systemd reports it gone, and, as a child
subreaper, reaps any remaining descendant before the final hash; a scope it
cannot confirm stopped fails the step as tampered. If the agent kills the
wrapper itself, the recorded scope lets `discard-runs` stop what is left. Workflow validators run under the system
`python3 -I -S`, not `.venv/bin/python`: `-S` skips `site`, so
site-packages `.pth` code cannot run, whereas `-I -B` alone still runs it and
still reads existing bytecode. The launcher and ledger never read checkout
bytecode (`sys.pycache_prefix` is `os.devnull`).

A protected change leaves an untracked `BALLAST_TAMPERED` file at the
checkout root, listing the changed paths, and the trusted launcher refuses to
continue. `run.py` and `ledger.py` also check it before importing other checkout
modules, but only the installed launcher is outside agent reach. A planted
`.pth` runs in anything started from `.venv`, so after this failure run nothing
from the checkout: inspect the listed files and `git status`, restore them with
Git, remove `__pycache__` directories, delete and recreate `.venv` with the
project's locked dependency install, delete the marker, and `ballast
trust` again. Run one headless workflow per
checkout at a time: the check covers every run's saved state, so a concurrent
run would fail as tampered.

Both integrations produce the same artifacts; provider differences live only
in this runtime configuration. Validators treat everything an agent can write,
including run state and the implementation baseline, as untrusted input.
Claude's allowed check and test commands execute repository code the agent may
have written, **without an OS sandbox**: that code runs as your user, with
network access, and can read credentials in your home directory ; the Read denials bind only Claude's own file tools.
Run Claude workers only on an account or machine where that is acceptable, or
use Codex, whose sandbox confines writes and disables network.
Editing source, tests, docs, and spec artifacts inside that worktree is normal
R1-capable implementation, not R2 agent write authority.

**Resume and integration switching.** `ballast run resume <run> -i
integration=claude|codex` may change only the integration. Spec Kit re-executes
only the paused or failed step and does not replay earlier validations; the
cumulative checks at every later boundary re-verify existing artifacts before
anything proceeds. A failed validation resumes at that validation, so fix the
artifact first—rerun the producer interactively (for example `/speckit-plan`
in Claude Code or `$speckit-plan` in Codex)—or start a fresh run.

**Logs.** Each agent invocation tees stdout and stderr to the terminal and to
ignored `.specify/workflow-state/<run>/agents/<time>-<command>-<integration>/`
with a `meta.json` (run, feature, integration, argv, timestamps, exit code,
blocking status). An exact `RECONCILE_STATUS: BLOCKED_*` line fails the step;
artifact validation stays the primary check. Spec Kit 1.0.11 still stores no
command output in `state.json` and shows shell-step diagnostics only there, so
`run.py` prints the failing step's output after the run stops. Agent logs
contain whatever the agent printed, which can include secrets or private
project data; they and the `speckit-runs` archive stay local and are never
attached to Issues or PRs.

**Autonomous runs.** `ballast run start --mode autonomous` starts
`ballast-autonomous` instead of `ballast-feature`; the rows below extend the
runner contract for it. Every validator above still runs unchanged.

| Step | Run by | Valid when |
|---|---|---|
| `autonomous-preflight` | trusted `artifacts.py` | Run record in operator state says Autonomous, active and eligible; clean worktree; `HEAD`, local Git configuration and hooks recorded. |
| `speckit.ballast.decide`, `.clarify`, `.review`, `.resolve` | confined agent | Write only drafts under `specs/<f>/autonomous/drafts/`, review narratives under `reviews/` and resolutions in `decisions.md`; or a block draft with at least two options. |
| `record-decision --point P` | trusted `artifacts.py` | The draft was written by the immediately preceding agent step, passes the decision-draft contract and never claims human approval; the decision is appended to the hash-chained log in operator state and `autonomous/record.md` is re-rendered. Every later check fails if `record.md` differs from the log. |
| `record-provisional-intent` | trusted `artifacts.py` | Writes the `workflow-provisional` block in `intent.md`, bound to the current spec digest; a later spec change makes it stale. With `--renew` (after decision resolutions) a changed spec blocks the run as stale intent; the runner never decides intent. In an Autonomous run every human approval block is refused. |
| Reviews (`review-plan`, `review-implementation`, `review-specialists`, `reconcile-spec`) | confined agent on the other provider when available; Claude for every role when Codex's own sandbox cannot start inside `bwrap` (checked once at start, recorded in the run) | One entry per required review kind (security always); any `high` or `critical` finding, or a verdict other than `approved`, blocks; a reviewer that edits source blocks. |
| `run-checks` | trusted `artifacts.py`, confined | Each `[checks] commands` entry in `ballast.toml` exits 0 within its timeout; code outside `specs/<f>/` still equals the tree frozen at implementation review before the checks, the checks change no tracked or unignored file, and protected inputs are unchanged afterwards; the tree digest is frozen for publication. |
| Publication | `run.py` as the operator, after the workflow completes | Commits the changes since the recorded `HEAD` with hooks and filters disabled, pushes the branch without force and opens one Draft PR whose body lists every provisional decision. It never merges, marks ready, releases or deploys. |

Agent steps in an Autonomous run run under `bwrap`: the host is read-only, the
worktree is writable except its protected inputs, and the operator state,
Git directory, credentials and session bus are out of reach. `GH_CONFIG_DIR`
and `XDG_CONFIG_HOME` are cleared for the agent and the directories they name
are hidden. Every Git command the operator side runs (tree digests, staging,
publication) empties each configured filter driver, so no `clean`, `smudge` or
`process` program runs, whatever `.gitattributes` an agent adds. A missing `bwrap`
or a failed confinement self-test refuses the start. Wall-time and agent-step
limits are enforced by the wrapper (exit 5).

**Upstream candidates** (github/spec-kit; this workflow does not wait for them):
per-step artifact postconditions and gate preconditions in the workflow schema;
tee semantics that stream and persist command output in run state; semantic
command status (for example `BLOCKED`) distinct from exit code; a shell-quoting
filter or input `pattern` for expressions; per-step `integration_args` for the
Claude and Codex integrations; and an untruncated or paged `show_file`.

**Restarting a corrupted run.** Treat a run that completed steps without
their artifacts (such as one from before this contract) as invalid evidence.
Do not edit its `state.json`. Inspect the feature directory, remove or fix
untrusted artifacts, and start a fresh run with `ballast run start`.

## Autonomous runs

An operator may run an eligible feature unattended with `ballast run start
--mode autonomous -i issue=N ...`. Eligible means a scoped leaf Issue with a
recorded scope comment (including `Privileged actions before merge:`), risk R0,
R1 or R2, no unauthorized privileged action before merge, a feature branch
with no open PR, a `[checks]` table and working confinement, narrowed by any
`[autonomous]` table in `ballast.toml`. An ineligible start is refused before
any agent step and names the human-gated command as the alternative.

```text
scope decision → specify → clarify (provisional assumptions) → intent decision
    → plan → independent plan review → plan decision → tasks → tasks decision
    → implement → independent implementation and specialist reviews
    → provisional decision resolutions → converge → spec reconciliation
    → run-checks → final-acceptance decision → Draft PR (published by run.py)
```

Each human gate of `ballast-feature` becomes an agent decision recorded as
**agent-provisional**, with its basis, evidence, deciding agent and artifact
digest. A provisional decision is never human approval; the human approves once,
by merging the Draft PR, after reading every provisional decision in its body
and in `specs/<f>/autonomous/record.md`. The human-gated lifecycle above is
unchanged.

**Blocks.** When an agent cannot decide safely, a check or review fails, a limit
runs out, a protected input changes, publication fails or the run becomes
ineligible, the run stops with a block: a category, the condition, the options
or recovery, and the recovery command. No approval prompt appears and no
provisional decision is written for the blocked point.

**Recovery.** `ballast run resume` refuses an Autonomous run until safe
Autonomous resume (#18) exists. Continue human-gated instead:

- `ballast run continue RUN_ID --reason block-resolved --ref TEXT` after
  resolving a block;
- `ballast run continue RUN_ID --reason changes-requested --ref PR-REVIEW-URL`
  when the merge reviewer requests changes;
- `ballast run publish RUN_ID` retries a failed publication without running an
  agent.

`continue` records a human decision and lowers the run to human-gated, then
starts `ballast-continue`, which has only validators and the human gates from
`approve-intent` to `final-acceptance`. Earlier provisional decisions stay in
the log and in `record.md`; the human approvals given in the continuation
supersede them. Missing producer work is done interactively, as in any
human-gated run. Raising a run to Autonomous after start is never possible.

## Local agent-run evidence

The pilot ledger lives in the clone's Git common directory at
`speckit-runs/<run-id>/events.jsonl`. It is outside worktrees and Git tracking;
removing a worktree preserves the ledger, while deleting the clone removes it.
`.ballast/spec_workflow/run.py` archives and imports runner events after each
start or resume. Import failures are reported with the original workflow exit
code. A skipped import cannot reconstruct an earlier gate choice from a later
state snapshot. Each import records the runner's end-of-invocation artifact
snapshot, so a later change can invalidate earlier acceptance. Use a fresh run
after changing the trusted workflow definition.
An interrupted launcher exit (130) leaves a waiting gate's apparent `reject`
choice unobserved, because Spec Kit may write that choice on Ctrl-C.

For a significant feature with an approved spec, map each `AC-NNN` to named
`unittest` cases in `acceptance-evidence.json`. The local tool checks one mapped
case at a time, records its exit and implementation snapshot, and archives the
manifest by digest. Changing the approved mapping within a run archives a new
version; earlier mapped checks become stale. Suite-wide check commands do not
by themselves prove a particular AC. Examples:

```bash
ballast ledger snapshot RUN_ID
ballast ledger check RUN_ID AC-001 tests.test_agent_run_ledger.LedgerTests.test_append_is_ordered_idempotent_and_outside_worktree
ballast ledger report --run RUN_ID
ballast ledger report --all --json
```

Use `ballast ledger record RUN_ID KIND --source SOURCE --data JSON` for observations
the runner cannot see. The [schema](../../.ballast/spec_workflow/ledger-schema.md)
lists the allowed fields and provenance limits. Record actual author and
reviewer identities, review verdicts and findings, route choices, human
recovery, and reliable client-exposed usage when available. Operator-attested
checks, snapshots, reviews, and convergence must be recorded before approving
the corresponding gate. The runner imports gate decisions only after that
invocation returns; record this evidence from another terminal while the gate
prompt is waiting, then inspect the report after the runner import. A report
from an archived run after its worktree is removed labels current compliance
and AC pass status unavailable, while retaining the observed event history.
Records are claims for audit, not proof that an agent could not submit them.
The tool refuses such a record in the normal agent-step environment as a
mistake guard; that environment check is not an authority boundary. Review
trusted file changes before running the launcher again.

Reports keep outcome, workflow, routing, efficiency, and human-action measures
separate. Missing or stale checks, incomplete token scopes, unobserved manual
recovery, and unknown model identities remain unavailable or noncompliant.
Reports read archived evidence after a worktree is removed and do not choose a
model or change policy defaults. If an event stream is malformed, keep the
original file for diagnosis; do not silently rewrite it.

## Model-neutral review handoff

Choose roles per feature, not providers: **spec author**, **architecture
reviewer**, **implementer**, **code reviewer**, and **reconciliation reviewer**.
Claude and Codex can fill any role, in either order. The author gives the peer a
repository-visible handoff in Markdown; the peer should not rely on the
author's chat history.

Use the Multi-Model Review extension to prepare a compact Markdown package when
its local configuration is available. The extension writes working packages
under ignored `.cross-review/`; those packages are handoffs, not canonical
specifications. Save the peer's material report and the author's disposition
under `specs/<feature>/reviews/` so the decision survives. Do not enable its
optional subagent routing, model router, work-assist tools, or hidden external
calls for the normal workflow. If the package tool is not configured,
the same review can be done directly from the feature files and diff.

Recommended report format:

```markdown
# Review: plan | implementation | reconciliation

- Role: architecture reviewer | code reviewer | reconciliation reviewer
- Agent/model: <provider + model, optional version>
- Routing: <economy | standard | senior | critical>, effort <level>
- Base: <commit or diff range>
- Artifacts: <paths>
- Verdict: approved | changes_required | blocked

## Findings

| ID | Class | Severity | Location | Evidence | Required action |
|---|---|---|---|---|---|

## Disposition

<Accepted fixes, rejected findings with reasons, and unresolved human questions.>
```

## Decisions and disagreements

`decisions.md` is append-only: a proposal and resolution are separate records.
It captures implementation evidence without letting code rewrite approved
intent. Classify discoveries as:

| Class | Default action |
|---|---|
| Implementation defect or accidental divergence | Fix or revert code to match approved artifacts; no spec change. |
| Missing test or verification | Add evidence for the existing acceptance criterion. |
| Technical choice inside accepted intent | Record the proposal; a human resolves it before the plan changes. |
| Spec ambiguity or missing behavior | Pause the affected work and ask the human to clarify. |
| Product or intent change | Human approval required; update `intent.md` first and then downstream artifacts. |
| Project-wide architecture change | Human approval plus reviewed ADR before adopting it. |

If reviewers disagree, keep both findings visible and ask the human to decide.
Do not hide a product change inside a bug fix or rewrite a spec merely because
implementation already exists.

## GitHub Issues and PRs

Authority flows from durable product and technical documents to a feature spec,
then its plan and tasks, and only then to tracking Issues and PRs. Issues hold
discussion, dependencies, status, and links. PRs hold the change summary, review
evidence, verification, risk, migration/security impact, and merge discussion.
Neither is a second full copy of the spec.
Before a spec exists, the Issue carries provisional scope and acceptance
criteria for the scope gate; once approved, feature artifacts own the detail.

Update the feature Issue from accepted Spec Kit state; never sync a changed
Issue back into an approved spec without an explicit reconciliation decision.
The normal workflow does not run `speckit.taskstoissues`: it creates an Issue
per task, while this workflow keeps fine-grained tasks in `tasks.md`. If a
substantial implementation slice needs a GitHub sub-issue, create and link it
deliberately from the approved feature plan, then update GitHub with concise
status. GitHub remains useful without API/MCP access: humans can update Issues
and PRs manually.

## Draft PR

At the end of every `ballast run start` or `resume` invocation, whether the
workflow completed, paused at a gate or failed, the launcher runs a Draft PR
checkpoint for an issue-linked feature (`specs/<issue>-<slug>/`). Once the
feature branch as published on GitHub differs from the default branch outside
`specs/<feature>/`, exactly one Draft PR shows it. Every later invocation reuses
that PR, including one a human opened by hand from the same branch.

- A created PR is always a draft to the repository's default branch. Its title
  is the Issue title (at most 256 characters). Its body is the default branch's
  `.github/pull_request_template.md` as stored on GitHub (never the feature
  branch's copy), then a Ballast section between
  `<!-- ballast:draft-pr:begin -->` and `<!-- ballast:draft-pr:end -->`: `Related
  to #<issue>` (never a closing keyword), the feature directory, the run ID, the
  last checkpoint time, and the `Main outcome:`, `Risk:` and `Scope gate:` lines
  of the newest intake scope comment (`<!-- ballast-intake:`) written by an
  owner, member or collaborator.
- On a reused PR Ballast changes only its marked section. It adds that section
  when the body neither has one nor references the Issue, and leaves a body with
  several or unbalanced sections alone.
- Ballast never pushes: publishing the branch stays your action. It never
  changes the title, base, labels, reviewers or draft state, and never marks a
  PR ready, merges, closes or reopens one.
- The checkpoint never changes the run's exit status or step state. Every state
  is recomputed from Git and GitHub at the next invocation.

The run ends with one line, `Draft PR: <state>[ (<reason>)][ #<number>
<url>][: <remedy>]`, and the run ledger records a `pull_request` event (`ballast
ledger report --run RUN_ID` shows the latest one). No `gh` output or credential
is printed or stored.

| State | Reason | Remedy |
| --- | --- | --- |
| `created` | | none |
| `reused` | | none |
| `reused` | `section-unmanaged` | keep one Ballast section in the PR body |
| `reused` | `body-changed` | none: the PR body changed during the check; the next run refreshes the section |
| `pending` | `no-branch` | check out the feature branch, then resume |
| `pending` | `not-published` | publish the branch, e.g. `git push -u <remote or origin> <branch>` |
| `pending` | `on-base-branch` | run the feature on its own branch |
| `pending` | `no-meaningful-change` | none: a Draft PR opens once implementation changes are pushed |
| `pending` | `diff-unclassified` | open the PR by hand; Ballast will adopt it |
| `failed-retryable` | `gh-missing` | install the GitHub CLI; `ballast doctor` checks it |
| `failed-retryable` | `gh-unauthenticated` | run `gh auth login` |
| `failed-retryable` | `gh-forbidden` | grant your GitHub account write access to `<owner>/<repo>` |
| `failed-retryable` | `github-unreachable` | check the network; the next run retries |
| `failed-retryable` | `github-error` | the next run retries; check GitHub status, or upgrade `gh` to 2.48 or later, if it persists |
| `failed-retryable` | `lock-busy` | another checkpoint is running; the next run retries |
| `failed-retryable` | `internal-error` | report it with the run ID; the next run retries |
| `failed-retryable` | `gh-untrusted` | gh not found outside working trees: install it in a directory outside any Git working tree and put that directory on `PATH` |
| `failed-retryable` | `git-untrusted` | git not found outside working trees: put a system `git` on `PATH` ahead of any checkout directory |
| `blocked-ambiguous` | `several-open` | close all but one of the listed PRs |
| `blocked-ambiguous` | `base-mismatch` | PR #N targets X, expected Y: change its base on GitHub, or close it |
| `blocked-ambiguous` | `create-unverified` | check the listed PR on GitHub: its base, head or draft state is not what Ballast requested |
| `blocked-closed` | `closed`, `merged` | reopen the PR, or open a new one by hand from this branch; Ballast will adopt it |
| `blocked-unlinked` | `no-issue-number` | name the feature directory `specs/<issue>-<slug>/` |
| `blocked-unlinked` | `issue-not-found` | create the Issue, or fix the number in the feature directory |
| `blocked-unlinked` | `not-github` | none: Draft PRs need a GitHub upstream |
| `blocked-unlinked` | `branch-unpinned` | start a new run with `ballast run start` on the feature branch |
| `blocked-unlinked` | `branch-mismatch` | check out the branch the run started on, with its upstream, then resume |
| `blocked-unlinked` | `no-repository` | declare `[github] repository = "OWNER/NAME"` in `ballast.toml`, then run `ballast trust` |
| `blocked-unlinked` | `repository-mismatch` | the branch's upstream is not the repository pinned in `ballast.toml`: push the branch there, or fix the pin and run `ballast trust` |

`ballast run start` prints `Draft PR: branch pinned: <branch>` before any agent
runs; every later checkpoint must be on that branch, published under that name.

While `BALLAST_TAMPERED` or an unfinished agent step's marker exists, the
checkpoint prints `Draft PR: skipped: <marker> exists; restore the checkout`
and records nothing.

Authority: the checkpoint is trusted launcher code, outside the agent sandbox.
It uses your authenticated GitHub CLI, `gh` 2.48 or later, and `git`, each
resolved from absolute `PATH` entries outside every Git working tree and
outside `/tmp`, `/var/tmp`, `/dev/shm` and `$TMPDIR`, and run by
absolute path without a shell. `gh` starts outside the checkout, and the
repository it targets is the `[github] repository` you pin in `ballast.toml`,
never one read from Git configuration an agent can change. Agents stay denied `git push` and `gh`, and the
launcher withholds `GH_TOKEN`, `GITHUB_TOKEN`, `GH_ENTERPRISE_TOKEN` and
`GITHUB_ENTERPRISE_TOKEN` from the workflow engine and every agent step. See
ADR-0003 in the Ballast repository.

## Project status and component choices

`speckit.status-report.show` derives a convenient overview from feature
artifacts and task checkboxes. Its generated `specs/spec-status.md` is ignored
and disposable; never edit it or use it as authority. Task checkboxes, decision
records, reviews, and GitHub tracking remain the underlying state.

| Component | Decision | Scope |
|---|---|---|
| Explicit Task Dependencies v1.0.0 | Use | Installed per checkout by `tools/setup`; supplies task dependencies and execution waves, not a scheduler. |
| Intent Reconciliation v1.0.2 | Use | Feature-local intent and append-only decisions; the wrapper is the implementation entrypoint when using Spec Kit. |
| Multi-Model Review v0.1.2 | Use selectively | Portable review packages and report workflow. Follow the model routing policy; do not enable the extension's optional router or orchestration. |
| Status Report v1.4.2 | Use as convenience | Read derived status; its generated snapshot is ignored. |
| Official `bugfix` bundle v1.0.0 | Use for small bugs | Assessment → human gate → fix → test. |
| Official `assess` bundle v1.0.0 | Use for investigations | Intake and research with a human verdict; `go` hands off to a feature spec. |
| Axi v1.1.4 | Defer | Browser annotations duplicate direct Markdown edits and PR review for this solo project. Reconsider if review comments become hard to manage. |
| CI Guard | Defer | Existing CI is established; automate spec policy only after a pilot reveals stable checks worth enforcing. |
| Architecture Guard | Defer | Plans cite current boundaries and ADRs now. Add one small guard at a time only after repeated boundary violations show a clear rule. |

The bugfix and assess bundles are official, opt-in Spec Kit bundles. Community
extensions are independently maintained and are not endorsed by Spec Kit;
pin versions and inspect updates before upgrading.

Run `ballast setup` in each fresh checkout before using these
commands. Linked worktrees copy a matching primary checkout's installation.
Other checkouts install the pinned upstream sources and apply the standard's
task and skill patches. Every installed file is ignored; only the constitution,
`ballast.toml` and `docs/policies/project/` remain in Git. A worktree manager
such as Orca can run the same command as its worktree setup script. To upgrade,
change the pinned standard version in `ballast.toml` and rerun setup; it
reinstalls whenever the standard or `ballast.toml` changes. Do not run `specify
integration upgrade --force`: it discards the standard's patches, which
`specify integration status` reports as intentionally modified managed files.

## Day-to-day commands

Create a candidate Issue, classify it using the scope gate above, then start
the native workflow only for a feature Issue:

```bash
ballast trust   # after reviewing the checkout
ballast run start \
  -i idea="Issue #NNN: import a transcript as reviewable session evidence" \
  -i feature_directory=specs/NNN-session-text-import \
  -i integration=claude
ballast run resume <run-id> -i integration=claude
```

At each gate, review the artifacts and record the result before resuming. To
work entirely in Claude Code or Codex without the runner, use
`speckit-specify`, `speckit-clarify`, `speckit-intent-confirm`, `speckit-plan`,
`speckit-tasks`, `speckit-analyze`, `speckit-intent-implement`,
`speckit-intent-decisions`, and `speckit-converge` in the same order. Check
progress with `speckit.status-report.show` or `specify workflow status`.
For manual `speckit.specify`, explicitly provide
`SPECIFY_FEATURE_DIRECTORY=specs/<issue-number>-<slug>`; otherwise Spec Kit's
default sequential number can differ from the GitHub Issue number.

Small bug:

```bash
specify workflow run bugfix \
  -i report="Issue #123: importing an empty transcript reports success" \
  -i slug=empty-transcript-import
```

Investigation:

```bash
specify workflow run assess \
  -i idea="Compare transcript storage options for large sessions" \
  -i slug=transcript-storage-research
```

## Concrete example: session text import

For a bounded roadmap slice, a planned `v1.0` Milestone groups an Epic. Its child
feature Issue says “Import an existing text transcript and inspect its
evidence.” The feature author writes acceptance criteria such as:

- `AC-001`: Importing the same file twice does not duplicate transcript
  evidence.
- `AC-002`: A failed import preserves the original file and reports failure.
- `AC-003`: Unknown speakers and timestamps remain unknown rather than being
  inferred.

After the human approves `intent.md`, the plan defines how the application stores the
imported evidence and its source checksum, while citing the existing persistence
and session boundaries. A peer model challenges replay behavior, provenance,
and migration impact. The human approves the plan. Tasks link tests to those
criteria and express dependencies—for example, duplicate/failure tests precede
the import service, which precedes the API and UI. The team executes ready
waves, and another model reviews the diff against the spec.

Suppose implementation discovers that the source format has no reliable speaker
identifier. The implementer appends a `contract-discovery` proposal to
`decisions.md`; no code silently labels speakers. The human chooses to preserve
unknown speaker identity, the author updates the affected artifacts and tests,
and implementation continues. Cross-review and convergence confirm each AC has
evidence. The human accepts the result and the PR links the Issue, spec, reports,
checks, and migration impact. This example defines the workflow; it does not
implement session import.

## Migration note

Keep existing completed work and historical Issues as-is. Add links from active
significant feature Issues to the feature artifacts as they are touched. Small
bug Issues remain Issue-led; investigations get a research note only when the
result should persist. New meaningful behavior changes use the full workflow.
Do not backfill every historical ticket, create duplicate GitHub tasks by
default, or copy the full product specification into feature directories.

## Current Spec Kit references

Versions and syntax were checked against Spec Kit 1.0.11 on 2026-09-25. Review
the upstream references before upgrading pinned components:

- [Workflow authoring, gates, and resume](https://github.com/github/spec-kit/blob/main/docs/reference/workflows.md)
- [First-party bundles](https://github.com/github/spec-kit/blob/main/docs/reference/bundles.md)
- [Extensions](https://github.com/github/spec-kit/blob/main/docs/reference/extensions.md)
- [Presets](https://github.com/github/spec-kit/blob/main/docs/reference/presets.md)
- [Multi-Model Review extension](https://github.com/formin/multi-model-review)
- [Status Report extension](https://github.com/Open-Agent-Tools/spec-kit-status)
- [Intent Reconciliation extension](https://github.com/SuhaibAslam/spec-kit-reconcile)
