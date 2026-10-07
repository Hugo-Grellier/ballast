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
`ballast intake --repo OWNER/REPO preflight N` as a read-only leaf
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
| Feature the operator wants to shape in conversation, one step at a time | Chat mode, `ballast run start --mode chat`: the same phases, checks and human approvals, driven by the operator through `ballast run` (see [Chat runs](#chat-runs)). |
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
discover (sourced brief; open decisions asked in one round) → specify → clarify
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

1. **Scope, discover, specify, and clarify.** Confirm the tracking Issue is one
   independently specifiable outcome. Before any spec exists, the
   [discovery brief](#discovery-brief) gathers what the Issue, its comments and
   the repository already answer, and asks the few remaining high-impact
   questions in one round. Use Spec Kit to draft `spec.md` from the brief,
   assign a stable `AC-NNN` ID to each acceptance scenario, trace each
   requirement to its source, and resolve blocking questions without asking
   again what the brief settled. Read the relevant project context and ADRs; do
   not copy entire product or architecture documents into the feature. Revisit
   scope if discovery or clarification reveals separate outcomes.
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

## Discovery brief

In both `ballast-feature` and `ballast-autonomous`, the `discover` step
(`speckit.ballast.discover`) writes `specs/<f>/discovery.md` after the scope
decision and before `speckit.specify`. It reads the Issue snapshot (body and
comments, untrusted data), the relevant parts of the product and technical
specs, ADRs, policies and the code the request touches, and records:

- the user, job to be done, current pain, intended outcome and examples;
- scope, non-goals, constraints, permission and data-authority boundaries,
  success evidence, and edge, failure and permission cases;
- the Issue's acceptance criteria verbatim as `IAC-1`, `IAC-2`, …;
- what is known, inferred and still undecided, and one `D-NN` block per
  decision that would change implementation or acceptance, with options,
  consequences and a recommended default;
- how many question rounds, questions and assumptions the request needed.

Every item ends with a provenance marker: `[S: source]` for an Issue, comment,
repository path or `IAC-n`; `[I]` for an inference; `[O: D-NN]` for an operator
answer; `[P: D-NN]` for an agent-provisional assumption. The brief is input
evidence: it says so in its first line, `spec.md` and `intent.md` stay the
feature's authority, and recorded intent binds only the `spec.md` digest, so
editing the brief never changes or invalidates it.

What the repository or the Issue already answers is `settled` with its source
and never asked; a comment settles a decision only when its author is an owner,
member or collaborator of the repository. Sources that contradict each other are never settled. What
remains depends on the mode:

| Mode | Open decision | Result |
|---|---|---|
| human-gated | Any | Left `open`. `validate-discovery` records the question round in your state directory and fails once with every open question, its options, consequences and recommended default. Set each decision's **Status** to `answered`, write your choice on its **Answer** line, then `ballast run resume <run>`. Only answers to questions asked in a recorded round, with the questions unchanged, are accepted; an answer an agent wrote is refused. With nothing open, nothing is asked. |
| autonomous | Safe, reversible default, not about product behavior, scope, data authority, a security boundary or accepted architecture | `assumed`; recorded as an agent-provisional `clarification` decision (`record-discovery`), shown in `autonomous/record.md` and the Draft PR. |
| autonomous | No safe default, or a contradiction | The run blocks (`decision` or `contradiction`) with the decision, its sources, two options or more with consequences, and the recovery. Nothing is prompted. |

Several independent outcomes stop discovery with a decomposition
recommendation; it never splits the spec or creates Issues. An answer that
introduces a new contradiction may need a second round, which the brief
counts. Clarification afterwards does not ask again what the brief settled,
answered or assumed. Once discovery ran for a feature (the brief exists, or
your state directory records that it validated), the spec check requires an
`AC-NNN` ID and a provenance marker on every acceptance scenario and each
`IAC-n` cited in one or listed under a Non-goals heading; deleting the brief
does not skip that check. Features specified before discovery existed are not
checked or retrofitted. Bugfix and assess workflows have no discovery step.

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
| discover | `discovery.md` | Every section of the [brief](#discovery-brief); every item cites an existing source or is marked as an inference; the Issue's acceptance criteria listed verbatim; no wording that claims a human approval. In a human-gated run every open decision was asked and answered by the operator; in an Autonomous run none is open and each assumption is a recorded provisional decision. |
| specify | `spec.md` | Exists in the requested feature directory, non-empty, no spec-template placeholders. Once discovery ran: every acceptance scenario has an `AC-NNN` ID and a provenance marker, and each of the brief's `IAC-n` is cited by one or listed under a Non-goals heading. |
| clarify | `spec.md` | Also no `[NEEDS CLARIFICATION` marker. |
| intent approval | `intent.md` | Written only after the `approve-intent` gate; has the intent sections and one approval record whose spec digest matches the current `spec.md`. |
| plan | `plan.md` | Intent still valid; non-empty; no plan-template placeholders or unresolved clarification. |
| tasks | `tasks.md` | Plan still valid; at least one `- [ ] T###` task, unique IDs, every `(depends on T###)` names an existing task. |
| implement | repository change | Every task checked and a path outside the feature directory changed since the pre-implementation baseline, or `tasks.md` declares `<!-- workflow: no-code-change -->` (visible at the task gate). In an Autonomous run, a task tagged `[DEFERRED-TO-PR]` may stay open only when the tasks decision recorded it (see Autonomous runs). |
| decisions | `decisions.md` (optional) | Every `DEC-NNNN — Proposal` has a matching resolution. |
| convergence | `reviews/convergence.md` | All of the above, no pending task (converge appends none), and the latest `- Verdict:` line is `CONVERGED`. |

The `approve-intent`, `review-plan`, `review-tasks`, and `final-acceptance`
gates show the artifact they approve (Spec Kit truncates the display at 200
lines; open the file for the rest). Peer reviews and spec reconciliation are
**manual**: the gates say so and the workflow does not claim they ran.
Approving an intent change outside the gate means reviewing `spec.md` and
running `.ballast/spec_workflow/artifacts.py record-intent --feature <dir>`.
`record-intent` registers each approval it writes in your state directory,
which no agent can write, and every check of a human-gated run refuses an
approval block it did not register in this checkout. A run approved before
this check existed, or a checkout that moved, stops at `validate-intent`:
review the spec, re-approve with the command above, then resume the run.
Human-only steps a headless agent cannot finish—discovery questions,
clarification questions, decision resolutions, convergence verdicts—surface as
a failed validation; complete them interactively and resume.

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
write. Every command refuses an `XDG_STATE_HOME` that is relative or lies
inside the checkout, `/tmp`, `/var/tmp`, `/dev/shm` or `$TMPDIR`, which
agents can write. `ballast run ...` and `ballast ledger ...` then
refuse, before executing any checkout code, if those inputs changed since
`trust` (or since the baseline setup recorded), if `BALLAST_TAMPERED` exists, or if an agent step never finished its
check (for example because the agent killed the wrapper). Saved run state is
not in the baseline, so after an unfinished step `trust` also refuses: review
the checkout, run `ballast discard-runs`, then `trust`; continue the stopped
run in Chat (see below) or start a fresh run. `discard-runs` first kills the unfinished step's agent scope (see
below) and refuses unless systemd confirms it is gone, so no surviving agent
process can rewrite state afterwards; only then does it delete the local run
state (the archived copy in the Git common directory remains). It never follows
a link on the way to that state. A primary checkout's `.git` directory is not hashed; it
relies on the agent sandbox keeping it read-only. They run `run.py` and
`ledger.py` under the launcher's own `/usr/bin/python3 -I -S`.
Bytecode is excluded from the baseline because no workflow tool reads it.

**Setup-recorded baseline.** Only the operator's `ballast trust` records a
baseline after a review, with one exception that the operator's own
`ballast setup` (and a new worktree's first-command preparation, which installs
from a verified local copy) may also record it (ADR-0015). They record it only
when every protected input is exactly what setup installed (no `.venv`, no
committed `.specify` file other than the constitution, no edited installed
file, a linked worktree's `.git` pointer naming a worktree of its own
repository), `ballast.toml` and the constitution are committed and unchanged,
and equal the default branch of the repository pinned in `[github] repository`
(`ballast setup` also accepts the checkout's earlier baseline from `ballast
trust`; a preparation never reads a baseline). That branch is
read live, from the pinned repository only, with the operator's own Git
authority (it needs network access and never prompts), and only for a
repository `ballast trust` already reviewed on this machine, and only for the
exact `ballast.toml` and constitution it reviewed for that repository (a
baseline from before this version does not count; each project needs one
`ballast trust` per machine first, and again after its default branch changes); nothing the
checkout's Git configuration names is used. Setup records nothing when saved run
state, an unfinished run, `BALLAST_TAMPERED` or an agent step's marker exists, so
an agent step can never lead to a recorded baseline; it then says why and that
`ballast trust` is needed after review. A baseline recorded from the operator's
earlier one is marked as recorded by setup, so a later setup that records again
needs the network or `ballast trust`. The launcher compares the baseline exactly
as before, whoever recorded it, and `ballast doctor` shows which. Only the
operator runs `ballast trust`; an agent never does.

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
  except `.env`/`*.local.md`, `.git/`, CI and agent configuration,
  `ballast.toml`, the workflow machinery itself, and paths the project denies
  in `ballast.toml`; Bash is limited to the Spec Kit scripts, read-only Git
  (`status`, `diff`, `log`, `show`, `rev-parse`, `ls-files`, matched as whole
  subcommands), and the commands the project allows there.
- **Codex** runs `codex exec --sandbox workspace-write`: writes are confined to
  the checkout and temporary directories (extra `writable_roots` from your
  Codex configuration are pinned empty), network access is pinned off, and
  approvals are never requested. Codex still loads the user's Codex
  configuration, and user Codex hooks run for workflow workers; these flags
  override its sandbox. Codex cannot express Claude's per-path denials, so the
  wrapper hashes the run state, `.specify/workflow-state/<run>/`, the installed
  Spec Kit configuration, extensions, scripts and workflows under `.specify/`
  (except `feature.json`, other runs and caches), `.ballast/spec_workflow/`
  including its bytecode, and the whole `.venv` before and after every agent
  call and fails the step if any of them changed. Still review the diff for CI
  changes.

Both integrations run `git` through `.ballast/spec_workflow/guard/git`, first
on the agent's `PATH`. It sees the arguments after shell quoting, which a
permission rule matching command text cannot, and refuses `--output` (which
writes a file anywhere), `difftool` and `mergetool` (which run a program)
before running the trusted `git` the wrapper resolved.

**Agent write boundary.** Headless agents can write the checkout and the
temp roots (`/tmp`, `/var/tmp`, `/dev/shm` and `$TMPDIR`); Claude also any
`additionalDirectories` the project's committed Claude settings add, so review
those like code. Autonomous runs narrow this further with bubblewrap. Whenever
Ballast runs a program with your authority (`git`, `gh`, `systemd-run`,
`bwrap`) it skips copies inside that boundary or any Git working tree and
trusts every other absolute `PATH` entry, so keep no directory an agent can
write on your `PATH`. Ballast also refuses an `XDG_STATE_HOME` or
`XDG_DATA_HOME` inside the boundary. `ballast doctor` reports the boundary
under `agent-cli` and names any program it ignored.

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
project's locked dependency install, delete the marker, run `ballast
discard-runs` (it lists the run state it removed), and `ballast trust` again.
The discarded run state is gone, so a run stopped on `tamper` or
`unfinished-step` cannot resume in Autonomous or continue human-gated; continue
it in Chat with `ballast run continue RUN_ID --mode chat --reason
block-resolved --ref TEXT`, or start a new run. Run one headless workflow per
checkout at a time: the check covers every run's saved state, so a concurrent
run would fail as tampered.

`.venv` is a protected input, so an agent check that creates it is a tamper.
A fresh worktree has none, and `uv run` or `uv sync` creates it: when a
`[checks]` command or `extra_allow` rule runs either (without `--no-project`
or `--isolated`, for sync `--dry-run`) in a `pyproject.toml` project without `.venv`, setup and
worktree preparation print a warning, `ballast doctor` reports `checks-venv`,
and Autonomous eligibility refuses. Run `uv sync --locked` before `ballast
trust`.

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
| `speckit.ballast.discover` (`autonomous`), then `record-discovery` and `validate-discovery` | confined agent, then trusted `artifacts.py` | The agent writes only `discovery.md` and one `clarification-discovery-<n>.json` draft per adopted assumption, or a block draft. Each assumption is recorded at the `clarification` point; `validate-discovery` refuses an open or answered decision, an assumed decision without its recorded assumption, counts that differ from the recorded ones, and any change outside `specs/<f>/`. |
| `record-decision --point P` | trusted `artifacts.py` | The draft was written by the immediately preceding agent step, passes the decision-draft contract and never claims human approval; the decision is appended to the hash-chained log in operator state and `autonomous/record.md` is re-rendered. Every later check fails if `record.md` differs from the log. |
| `record-provisional-intent` | trusted `artifacts.py` | Writes the `workflow-provisional` block in `intent.md`, bound to the current spec digest; a later spec change makes it stale. With `--renew` (after decision resolutions) a changed spec blocks the run as stale intent; the runner never decides intent. In an Autonomous run every human approval block is refused. |
| Reviews (`review-plan`, `review-implementation`, `review-specialists`, `reconcile-spec`) | confined agent on the other provider when available; Claude for every role when Codex's own sandbox cannot start inside `bwrap` (checked once at start, recorded in the run) | One entry per required review kind (security always); any `high` or `critical` finding, or a verdict other than `approved`, blocks; a reviewer that edits source blocks. |
| `checks-implementation`, `checks-fix-N` (`run-checks --feedback`) | trusted `artifacts.py`, confined | The same `[checks]` commands as `run-checks`, as feedback for the fix loop: a failed command is recorded in operator state (`checks-feedback.jsonl`) and reaches the fix step only through the fix input, never as a block; a protected-input change, a tree change or the wall-time limit still blocks. A cycle step with nothing to do writes nothing. |
| `fix-N` (`speckit.ballast.fix`), `record-fix-N`, `review-fix-N`, `review-specialists-fix-N`, `record-fix-review-N` (`record-decision --point implementation-review --recheck`) | confined agent (skipped by the wrapper unless the run's fix state asks for it), then trusted `artifacts.py` | The fix step changes only code, tests, `tasks.md` and `decisions.md` for the findings and failed checks the fix input lists; `record-fix` counts the cycle only after that step ran and the implementation contract still holds; the recheck records the reviews again, superseding the earlier ones, and sets the next fix state or blocks as `fix-cycle limit (3)`. |
| Draft retries | the trusted agent wrapper | After an Autonomous agent step, the recorder's own draft checks; a correctable refusal reruns the step with the message, at most twice, each attempt counted. |
| `run-checks` | trusted `artifacts.py`, confined | Each `[checks] commands` entry in `ballast.toml` exits 0 within its timeout; code outside `specs/<f>/` still equals the tree frozen at implementation review before the checks, the checks change no tracked or unignored file, and protected inputs are unchanged afterwards; the tree digest is frozen for publication. When the commands pass, it then runs each test `acceptance-evidence.json` maps, once, confined with the whole checkout read-only, within the check timeout and the wall time, and records one `runner-recorded` result per criterion and test in the ledger (ADR-0018 in the Ballast repository). A missing, malformed, stale or oversized (over 100 tests) manifest, or no `.venv/bin/python`, runs none and is named in the run record; a failed test is recorded, not a block. |
| Publication | `run.py` as the operator, after the workflow completes | Commits the changes since the recorded `HEAD` with hooks and filters disabled, pushes the branch without force and opens one Draft PR whose body lists every provisional decision. It runs `gh` and `git` as the [Draft PR](#draft-pr) checkpoint does, for the `[github] repository` pinned in `ballast.toml`, and refuses an `origin` other than that repository. It pushes the commit to that repository's URL from a throwaway repository with an empty configuration, so nothing in the checkout's Git configuration (remotes, URL rewrites, includes, SSH command, credential helper, hooks) applies to the push. When the branch's only open PR is the one the checkpoint opened for this feature and it is still a draft to the default branch, the publisher adopts it instead of opening another. It re-reads the body just before editing and adds or replaces only its own summary section, so no other text is lost. A body that changed meanwhile is left alone, and `ballast run publish` retries. Every PR it creates or adopts is read back and must be an open draft from this branch to the default branch. It never merges, marks ready, releases or deploys. |

Agent steps in an Autonomous run run under `bwrap`: the host is read-only, the
worktree is writable except its protected inputs, and the operator state,
Git directory, credentials and session bus are out of reach. `GH_CONFIG_DIR`
and `XDG_CONFIG_HOME` are cleared for the agent and the directories they name
are hidden. Every Git command the operator side runs (tree digests, staging,
publication) empties each configured filter driver, so no `clean`, `smudge` or
`process` program runs, whatever `.gitattributes` an agent adds. A missing `bwrap`
or a failed confinement self-test refuses the start. Wall-time and agent-step
limits are enforced by the wrapper (exit 5).

**Chat runs.** `ballast run start --mode chat` drives the `ballast-feature`
phases one operator action at a time (see [Chat runs](#chat-runs)); the rows
below extend the runner contract for it. Every validator above runs unchanged,
in process, on the run's feature.

| Action | Run by | Valid when |
|---|---|---|
| Entry of a `step` | trusted `chat.py` | The phase's cumulative checks and current human approvals pass now; each evaluation is recorded in the run's hash-chained event log in operator state. A refused phase names its first failing check. |
| Interactive agent step | confined agent behind a wrapper-owned pty | Runs only after the launcher's checks and branch synchronization in the same invocation; anything its permission rules do not allow is denied without a prompt. |
| Close of a `step` | trusted `chat.py` | The agent's scope is confirmed stopped, protected inputs are unchanged, the phase's postcondition passes and the step changed only its write scope (`specs/<f>/` before `implement`, `specs/<f>/reviews/` for a review). |
| `approve`, `reject`, `resolve` | the operator, from a terminal | No step is active, the gate's precondition passes, and the operator types the confirmation; the human decision is bound to the artifact's digest and is current only while it matches. |
| `checks` | trusted `artifacts.py`, confined | Each `[checks] commands` entry runs and its result is recorded with the tree it ran on; no `[checks]` table is recorded as unavailable. |
| `publish` | `run.py` as the operator | The final approval and the project checks are current for this tree; then the Autonomous publication path commits, pushes and writes a Chat section, rendered from operator records, into the single Draft PR, then runs the Draft PR checkpoint, which refreshes that PR and attempts the acceptance packet; a packet failure, or a PR that GitHub does not list yet, leaves the publication successful and names `ballast run checkpoint RUN` as the retry. |

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
any agent step and names the human-gated command as the alternative. A start
also refuses while `specs/<f>/autonomous/record.md` from an earlier run is
present: retire it with `git rm` and a commit (Git history keeps it).

**Privileged actions.** Agents declare every action needed before merge as
`KIND` or `KIND: description`, with `KIND` one of `operator-trust`,
`scratch-repository`, `secret-provisioning`, `network-access`,
`external-write`, `permission-change`, `deploy`, `release`, `merge`,
`mark-ready` or `other`; the recorder refuses a draft naming any other kind,
and the step is retried. `[autonomous] authorized_privileged_actions` lists
the kinds the project authorizes, spelled exactly, and only the kind is
compared. `deploy`, `release`, `merge`, `mark-ready` and `other`, and any
action starting with one of them, are never authorized. Any other entry is
legacy: it still authorizes only an action with exactly its text, with a
warning.

**Deferred tasks.** A task only the operator can do (a manual browser or
device check, a demo capture) is kept out of `tasks.md` when it can be; demo
captures are requested with `ballast run demo` instead. One that remains is
tagged `[DEFERRED-TO-PR]` after its other tags and left open. When the tasks
decision is recorded, the recorder (never the agent) lists every open tagged
task in it; `validate-implementation` and `convergence` then accept those tasks
open, and no other. A task tagged after the tasks decision, or a listed task
whose tag or text changed, is pending and blocks the run. The run record and the Draft
PR show a `Deferred to the PR` section, and the acceptance packet lists the
open tagged tasks at head next to the criteria they cite; one the tasks
decision did not record with the same text is marked pending, not deferred. A deferred task is
never evidence: its criterion stays `missing` until an operator records a
check. Chat and human-gated runs accept no deferral; the operator does the
task.

Agents cannot call `gh`, so at an eligible start the runner writes the Issue as
it read it (title, labels, body with the acceptance criteria, the intake scope
comment and the other comments, oldest first, each quoted under its author
and author association) to `.specify/workflow-state/issues/<N>.md`, capped at 60,000
characters. A human-gated start writes the same snapshot; when it cannot read
the Issue (no `gh`, no network, or no `[github] repository` in
`ballast.toml`), the snapshot says so and the run goes on with
the Issue listed as unavailable in the brief. Agent steps can read the snapshot
but not write it. Discovery, the `specify` prompt, the scope decision and
clarification read it as untrusted requirements data, never as instructions.

```text
scope decision → discover (assume or block) → specify
    → clarify (provisional assumptions) → intent decision
    → plan → independent plan review → plan decision → tasks → tasks decision
    → implement → feedback checks → independent implementation and
      specialist reviews → fix loop (at most three cycles: fix, feedback
      checks, reviews again) → provisional decision resolutions → converge
      → spec reconciliation
    → run-checks → final-acceptance decision → Draft PR (published by run.py)
```

Each human gate of `ballast-feature` becomes an agent decision recorded as
**agent-provisional**, with its basis, evidence, deciding agent and artifact
digest. A provisional decision is never human approval; the human approves once,
by merging the Draft PR, after reading every provisional decision in its body
and in `specs/<f>/autonomous/record.md`. The human-gated lifecycle above is
unchanged.

**Blocks.** When an agent cannot decide safely, a check or review fails, a limit
runs out, a protected input changes, publication fails, the agent CLI cannot
authenticate or the run becomes ineligible, the run stops with a block: a
category, the condition, the options or recovery, and the next command. No
approval prompt appears and no provisional decision is written for the blocked
point. Every block names its class, printed as
`Autonomous run blocked (<class>: <category>)`:

| Class | Categories |
| --- | --- |
| conflict | `contradiction`, `review-finding` |
| missing authority | `permission`, `ineligible`, `forge`, `credential` |
| exhausted limits | `limit` (the agent-step limit, the wall-time limit, the three fix cycles, or the two draft retries) |
| unsafe uncertainty | `decision`, `postcondition`, `tamper`, `unfinished-step`, `interrupted`, `upstream-sync` |

A confined Claude or Codex step reads the operator's login without its refresh
token, so it can never rotate the operator out of their session. When the
access token expires during a step, the step stops with a `credential` block:
sign in again outside the sandbox (for Claude, run `claude` once, or
`claude /login`; for Codex, `codex login`), then `ballast run resume RUN_ID`
re-enters at the failed step. Every home of the CLI the step runs gets this
treatment: `$CLAUDE_CONFIG_DIR` and `~/.claude` for Claude, `$CODEX_HOME` and
`~/.codex` for Codex, when both exist. A step sees only its own CLI's
credentials: the other CLI's homes are empty, its API-key variables are
dropped, and only a Claude step sees `~/.claude.json`; `[checks]` commands
see neither CLI's. A Codex API-key login has no refresh token and keeps working.
No confined step reads the operator's global Git configuration (`~/.gitconfig`,
`$GIT_CONFIG_GLOBAL`, `~/.config/git/config`), which can carry a token; its Git
directory is read-only, so it never commits and needs no identity.
A human-gated or Chat step that hits the same error fails with
`Blocked (credential)` and the same remedy.

**Fix loop.** After implementation the trusted runner runs the `[checks]`
commands as feedback (`checks-implementation`): a failure is recorded for the
reviews, not a block. When the implementation reviews return a verdict other
than approved, a high or critical finding, a medium finding left `open`, or a
failed feedback check, the run does not stop: the recorder writes the fix input
`.specify/workflow-state/fix-input/<slug>.json` (findings and failed checks, as
data agents can read but not write) and `speckit.ballast.fix` fixes only what it
lists. The checks and every required review then run again. A run has at most
three fix cycles, counted in operator state; a resume never resets the count.
While a cycle remains, a reviewer may leave a finding of any severity `open`
("fix this"). When the cycles are spent, a high or critical finding, a
non-approved verdict or a failed check blocks the run as an exhausted limit
(`fix-cycle limit (3)`), naming what is still open; a remaining medium finding
reaches the PR as `accepted-provisionally` with its reason. Plan review and
spec reconciliation keep the stricter rule: a high or critical finding or a
non-approved verdict blocks at once. The fix, its reviews and their
dispositions are agent-provisional, like every decision of the run. A run
started before ballast-autonomous 1.2.0 has no fix step, so its findings block
as before.

**Draft retries.** Right after an agent step, the wrapper runs the recorder's
own draft checks. When a draft breaks a rule the agent can correct in its own
text (a length or format limit, a missing or misnamed draft, a missing path,
approval wording, an invalid finding field, an invalid block draft), the step
reruns with the recorder's message, at most twice; the refused drafts are kept
in operator state. Every attempt counts against the agent-step limit. When the
retries are spent, or a limit runs out first, the run blocks as an exhausted
limit with the last message. A refusal about state outside the draft (a
protected-input change, a high finding at plan review, a contradiction with
accepted intent, an ineligible risk) blocks at once, without a retry. No
validator is relaxed: the approval-wording guard refuses a quotation of a
human approval as well as a claim, so decide and review drafts paraphrase and
cite such a source instead. A decision recorded after a retry shows "after N
retries" in the record.

**Limits and spend.** The wall-time limit counts only active time, the time
spent inside `start` and `resume` invocations: a run paused overnight keeps its
budget, and each agent step still stops when the recorded limit is reached. An
invocation that died without closing its clock is closed at the last time the
run recorded anything, so its downtime never counts. The agent-step limit
(default 40) counts every agent step, every retry and every fix step and
review, and is the run's attempt and spend bound; Ballast does not measure
monetary spend, and the record says so. A resume never raises a limit and
never changes the mode, the risk or the integrations.

**Resume.** `ballast run resume RUN_ID [--ref TEXT]` continues a blocked or
interrupted Autonomous run in Autonomous, without prompts (ADR-0010). It takes
the run's invocation lock, then synchronizes the branch with its base before
any agent step ([Branch synchronization](#branch-synchronization)); a
synchronization block, a protected-input change included, stops the resume
before it records anything and is resumed the same way. It then records the
operator's resolution as a human decision of kind `block-resolution` (`--ref`,
1–500 characters that must not read as an approval, or a default naming the
block), and re-enters the workflow at the blocked step: the failed agent step
or validator, or for a failed recorder the agent step whose drafts it records.
When an input changed during the block (the discovery brief, spec, intent,
plan, tasks or decisions of the feature, or, once implementation started, any
file outside the feature directory), the run re-enters at that input's
validator instead, when it comes earlier, so no stale intent, baseline or
review is trusted. The implementation baseline is never retaken. Resume keeps
the mode, risk, limits, integrations and fix-cycle count recorded at start, and
refuses `-i`, `--mode`, `--wall-time` and `--max-agent-steps`.

A run also keeps the `[autonomous]` policy it started with, so authorizing an
action in `ballast.toml` does not reach a run blocked `ineligible`. After
editing it and running `ballast trust`, resume with `--refresh-policy`: after
the synchronization, the runner re-reads `[autonomous]` from `ballast.toml`
only when its bytes equal the baseline `ballast trust` recorded (a baseline
setup recorded, one without provenance, or none, refuses), replaces the run's
policy snapshot, and
records the previous and new policy with the block resolution, where the
record shows it. A refreshed policy that no longer allows the run's risk,
boundaries or declared actions refuses the resume and records nothing.
Limits never change. A block
resolution is not an approval of any provisional decision: every decision made
after a resume stays agent-provisional, and merging the PR stays the single
human approval.

Resume refuses, naming the command that applies, a run that is:

| Status or block | Command |
| --- | --- |
| completed | `ballast run publish RUN_ID` |
| published | `ballast run checkpoint RUN_ID` |
| continued (lowered by `continue`) | resume the continuation run |
| stopped on `tamper` or `unfinished-step` | `ballast discard-runs` and `ballast trust`, then `ballast run continue RUN_ID --mode chat --reason block-resolved --ref TEXT` |
| stopped on `forge` or `permission` | `ballast run publish RUN_ID` |
| stopped on `upstream-sync` at start | your `ballast run start --mode autonomous` command |
| stopped on the agent-step or wall-time limit | `ballast run continue RUN_ID --reason block-resolved --ref TEXT`, or a new run with a larger limit |
| active, with an invocation running | none: wait for it |

An `active` run whose invocation is gone (the runner was killed) is stopped as
`interrupted` and resumed. A rewind spends agent steps again; a run that runs
out of them blocks, and the operator continues it human-gated.

A paused run's work stays uncommitted until publication. When the base
advanced during the pause, the synchronization therefore blocks the first
resume with cause `dirty` (it never stashes or commits for you): commit the
paused run's work on the feature branch, then resume again. The resume
records no human decision until the synchronization passes.

**Continue.** `continue` lowers a run to human-gated after implementation:

- `ballast run continue RUN_ID --reason block-resolved --ref TEXT` after
  resolving a block; before implementation, a human-gated `continue` refuses
  and points to `ballast run resume RUN_ID` (or, for a step or wall-time
  limit, to a new run), because `ballast-continue` only gates an existing
  implementation, while `--mode chat` continues the run in Chat, which can do
  the missing work; an `upstream-sync` block at start means
  removing the cause and starting again with your
  `ballast run start --mode autonomous` command;
- `ballast run continue RUN_ID --reason changes-requested --ref PR-REVIEW-URL`
  when the merge reviewer requests changes;
- `ballast run publish RUN_ID` retries a failed publication without running an
  agent.

`continue` records a human decision and lowers the run to human-gated, then
starts `ballast-continue`, which has only validators and the human gates from
`approve-intent` to `final-acceptance`. Earlier provisional decisions stay in
the log and in `record.md`; the human approvals given in the continuation
supersede them. Missing producer work is done interactively, as in any
human-gated run. With `--mode chat`, `continue` lowers the run to chat and
continues it as a linked [Chat run](#chat-runs) instead. Raising a run to
Autonomous after start is never possible.

**Refresh.** `ballast run checkpoint RUN_ID` refreshes the Draft PR checkpoint
and the acceptance packet of an Autonomous or Chat run from the current
records, in any status, `published` included, for example after `ballast
ledger check`. It starts no agent and changes no decision, mode or status.
Without a Draft PR it refuses and writes nothing; while another invocation of
the run is active, or a Chat step holds the run's lock, it refuses. An
Autonomous run's refreshed packet still lists every decision as
agent-provisional; a Chat run's lists the operator's approvals from its
operator records.

**Runs started before branch pinning.** A run started before v0.5.0 has a pin
with only its `branch`, and every `resume` or `continue` blocks it as
`wrong-branch`, "started before branch pinning". Nothing in Ballast writes the
missing feature for it: the pin lives in the launcher state directory
(`$XDG_STATE_HOME/ballast/<checkout>/draft-pr/<RUN_ID>.json`, outside the
checkout), and only the operator may add it. Read the feature from the run's
own record (`runs/<RUN_ID>/run.json`, field `feature`, in the same state
directory, or the `feature_directory` of the start command you used), check
that it is the feature the branch carries, add `"feature": "specs/<N>-<slug>"`
to the pin (and `"branch"` when it is missing), then rerun the command. Never
take the value from a file in the checkout.

## Local fallback

A human-gated or Autonomous run can let a headless step fall back once to a
zero-cost local model when its agent's quota is exhausted, its provider is
unreachable or its CLI is missing. It is off unless the operator turns it on
for the run:

```sh
ballast run start [--mode autonomous] --local-fallback MODEL -i ...
ballast run resume RUN_ID --local-fallback MODEL|off
```

- **What it runs.** The same step, once, as `codex exec --oss --local-provider
  ollama -m MODEL --json`, against Ollama's default endpoint `127.0.0.1:11434`;
  there is no endpoint option. MODEL is a local Ollama model served with a
  context of at least 16384 tokens, for example a variant created with
  `PARAMETER num_ctx 16384` (Codex's own prompt is about 12k tokens). Ollama
  must be 0.13.4 or newer, and the project needs Spec Kit's Codex integration
  installed, so that Codex finds the step's skill under `.agents/skills/`.
- **When.** Only after the step's first attempt failed on quota, provider
  availability or a missing CLI, recognized from the CLI's own messages; any
  other failure, and any failure on a draft-retry attempt, ends the step as
  before. The fallback counts as an agent step and is never retried: a failed
  fallback, or one whose draft the recorder refuses, ends the step.
- **Refusals.** Before any prompt is sent the wrapper checks, and refuses with
  one reason and a stderr line `local fallback refused: <reason>: <detail>`;
  the step keeps the primary's exit code:
  - `changed-state`: the first attempt changed the tree, the reviews, the
    drafts, a git-ignored path or a ref, or that could not be checked (for
    example more than 200,000 ignored entries);
  - `privacy-exclusion`: the model is remote or a cloud tag (or an endpoint
    override survives in the fallback's environment, which the wrapper cannot
    produce: it removes `OLLAMA_HOST`, `CODEX_OSS_BASE_URL` and
    `CODEX_OSS_PORT`, and every proxy variable, from the fallback's
    environment, so Codex reaches only `127.0.0.1:11434` directly). Codex
    itself contacts `github.com` and `chatgpt.com` at start-up even with a
    local model, so the fallback's environment points every proxy-aware request
    at a closed local port (`127.0.0.1:9`) and exempts only loopback; this
    reduces egress, it is not a network boundary;
  - `unknown-free-status`: the model is not installed, or has no size or
    digest;
  - `incompatible-capability`: Ollama is not answering or too old, the served
    context is below 16384 or unknown, Codex lacks `--oss`, the step's Codex
    skill is missing, Codex's sandbox does not start under the step's
    confinement (an Autonomous step on a host where it cannot nest inside
    bubblewrap always refuses), or the checks took over 10 s;
  - `permission-mismatch`: a Codex configuration layer exists outside the
    fallback's private Codex home (`/etc/codex/`, a project
    `.codex/config.toml`), `~/.agents/skills` is not empty (empty it, or leave
    the fallback off), or the argv or environment differs from the canonical
    headless Codex step's.
- **What it never does.** It is never available in Chat runs, never routes to a
  paid or remote backend, never reads the user's Codex configuration (it runs
  with a private, empty `CODEX_HOME`), never runs while the user's skills
  directory holds anything, and never loosens a sandbox, adds a writable root or
  enables network access. A review it completes never counts as cross-provider.
- **Turning it off.** `ballast run resume RUN_ID --local-fallback off`, or
  start without the flag. No environment variable or `ballast.toml` key turns
  it on.
- **Where it shows.** `ballast run status RUN_ID` prints a `Local fallback:`
  line, an Autonomous `record.md` lists it under "Mode and risk", and each
  step's `meta.json` carries `local_fallback: true` while it is on. The
  setting lives in the run's operator directory (`fallback.json`), where no
  agent can write.
- **Evidence.** `ballast ledger report --run RUN_ID` reports every decision
  as ledger `route` events (`failure_cause`, `fallback`, `fallback_reason`,
  `route_source: fallback`) and the fallback's token usage.

## Chat runs

Chat mode is the third per-run mode, beside human-gated and Autonomous. The
operator works conversationally with the agent during a step, chooses the next
step, and inspects or edits files between steps. Ballast keeps every guarantee
of a headless run: the trusted preflight before each agent step, the same
confinement, the artifact postconditions, the run's evidence record and the
human approvals. Chat changes who orders the steps and how the operator talks to
the agent; it does not change who approves, what is checked or which artifacts
are canonical. **Working in a plain Claude Code or Codex session outside
`ballast run` gives none of these guarantees.**

Each action is one `ballast run` invocation through the trusted launcher, so
each agent step is the only agent step of its invocation:

| Command | What it does |
|---|---|
| `ballast run start --mode chat -i feature_directory=specs/N-slug [-i idea="Issue #N: ..."] [-i integration=auto\|claude\|codex] [-i model=NAME]` | Records the run in operator state, synchronizes and pins the branch, archives the `ballast-feature` definition, prints the handoff summary and runs the Draft PR checkpoint. No agent runs. |
| `ballast run step RUN PHASE [--kind KIND]` | Runs one phase: `specify`, `clarify`, `plan`, `tasks`, `analyze`, `implement`, `reconcile-intent`, `converge`, or `review --kind plan\|implementation\|security\|test\|documentation\|spec-reconciliation`. |
| `ballast run status RUN` | Prints the handoff summary from the run record: mode and history, feature identity, completed steps, failed checks, gates (current, stale, rejected, pending), open decisions, changes made outside agent steps, and the allowed next actions. It needs no conversation log. |
| `ballast run approve RUN GATE`, `ballast run reject RUN GATE --reason TEXT` | Records a human decision for `scope`, `intent`, `plan`, `tasks`, `implementation`, `spec-reconciliation` or `final`, bound to the artifact's digest. `approve intent` writes the registered approval block in `intent.md`; `approve tasks` records the implementation baseline. |
| `ballast run resolve RUN DEC-NNNN` | Records the human resolution of a decision proposal, bound to its resolution text. A resolution an agent writes resolves nothing. |
| `ballast run checks RUN` | Runs the `[checks] commands`, confined, and records the result for the current tree. |
| `ballast run mode RUN chat\|human-gated --reason TEXT` | Switches the run. In human-gated mode each `step` runs headless through the agent wrapper, with the same checks, gates and records. A paused `ballast-feature` engine run switched to chat continues as a linked Chat run. |
| `ballast run continue RUN --reason block-resolved\|changes-requested --ref TEXT --mode chat` | Continues a stopped Autonomous run as a linked Chat run (see [Autonomous runs](#autonomous-runs)). |
| `ballast run publish RUN` | After a current final approval, commits, pushes and writes the Chat section into the feature's single Draft PR, then attempts the [acceptance packet](#acceptance-packet) in it; when the packet is not published, `ballast run checkpoint RUN` retries it. |
| `ballast run checkpoint RUN` | Refreshes the Draft PR checkpoint and the acceptance packet from the run's records, for example after `ballast ledger check`; it starts no agent and refuses while a step holds the run's lock. |

**Preflight before every step.** The launcher refuses on a changed trust
baseline, a tamper marker or an unfinished step, as for any `ballast run`; then
`step` runs [branch synchronization](#branch-synchronization) before the agent,
with `ballast run step RUN PHASE` as its recovery command. Stop between steps
whenever you like and come back from any terminal: `status` shows where the run
stands, and the next `step` runs the whole preflight again. `ballast run resume`
refuses a Chat run and names `step` and `status`.

**Allowed steps.** A step starts only when its cumulative upstream checks and
current approvals pass at that moment, and a refusal names the first failing
check. A failed check keeps blocking every dependent step, whatever the mode,
until a later run of the same check passes; the failure stays in the record. An
earlier phase can always be run again; a step or an edit that changes an
artifact makes every approval bound to it stale.

**Interactive confinement.** An interactive step runs `claude --permission-mode
dontAsk` (or `codex --ask-for-approval never`) with the headless permission
rules, inside the same bubblewrap confinement and systemd scope as an Autonomous
step, plus read-only `.claude/` and `.codex/` in the checkout: anything the rules
do not allow is denied without a prompt, and nothing granted inside the session
gets past bubblewrap. If a Claude session leaves `dontAsk` (Shift+Tab), a hook
denies every tool call until it is back, so no step ever asks for a permission.
Codex has no such hook: an operator's own `/approvals` in a Codex step can widen
that session up to the bubblewrap bound, so leave it at `never`.
The installed workflow skills are read-only for every confined step. `bwrap` with user namespaces is therefore a Chat
prerequisite; an integration that cannot run confined (for example Codex when its
own sandbox cannot start inside `bwrap`) is refused for Chat and the other one is
named. The agent's terminal is a pty the wrapper owns; press `Ctrl-]` twice to
end a step while the agent is still working. When a step ends, normally or not,
Ballast confirms its processes are gone before it runs the postcondition; when
it cannot, the unfinished-step refusal applies until `ballast discard-runs`
confirms them stopped, and the next invocation closes the step as interrupted.

**Human approvals only through `ballast run approve`.** Nothing an agent writes,
prints or says opens a gate, records a passing check, resolves a decision or
changes the mode: approvals exist only as operator commands from a terminal,
refused while a step is active. `final` is bound to the whole tree, reviews
included, and needs every earlier approval current; `publish` checks it again.
A change a step made outside its write scope blocks every later step until the
operator restores or changes it. Chat asks for every human approval the
human-gated mode asks for and never records an agent-provisional decision. A
continued Autonomous run's provisional decisions stay labeled agent-provisional,
in its record and in the Draft PR, even after a Chat approval supersedes them.

**Evidence and logs.** A Chat run records its steps, checks, reviews and
approvals in its operator record and in the same local ledger as a headless run,
with `mode: chat`; `ballast ledger report --run RUN` reports it against the
`ballast-feature` steps and gates. Conversation logs stay in ignored
`.specify/workflow-state/<run>/agents/` like any agent log, and are never
attached to, quoted in or linked from an Issue or a PR.

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
`unittest` cases in `acceptance-evidence.json`, or to `[]` when no unit test
proves it (a browser or demo check): such a criterion stays `missing`, since
Ballast records no evidence for a manual check. The local tool checks one mapped
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

## Branch synchronization

Before the first agent step of every `ballast run start`, `resume` and
`continue`, the launcher checks the run's branch against its base. A [Chat
run](#chat-runs) checks it at `start --mode chat`, at `continue --mode chat`
and before the agent of every `step`, whose recovery line names `ballast run
step RUN PHASE`; `status`, `approve`, `reject`, `resolve`, `checks` and `mode`
start no agent and run no check. `publish` starts no agent and runs no check.
Bugfix and assess runs started with `specify` directly do not pass through
`ballast run` and are not synchronized.

- **The base** is the base the run recorded, or else the default branch of the
  `[github] repository` pinned in `ballast.toml`. It is fetched from that
  repository on every invocation, never through `origin` or another remote an
  agent can change, and never replaced by a cached or substituted base.
- **Up to date**: when the base commit is already in the branch, nothing
  changes and the run prints `Branch sync: up-to-date BRANCH with BASE
  (COMMIT)`.
- **Behind**: a clean feature branch is rebased onto the base before any agent
  starts, and the run prints `Branch sync: synchronized BRANCH onto BASE
  (OLD..NEW), HEAD OLD -> NEW`. A published feature branch is pushed with
  `--force-with-lease` on the commit observed in the same invocation, and the
  line ends with `, pushed`.
- **Which branches it may rewrite**: only the feature branch, whose name split
  at `/`, `-`, `_` and `.` has a segment equal to the feature's Issue number
  (`18` in `feat/18-branch-sync` or `18-branch-sync`, not in `feat/180-x`), and
  that is neither the run's base nor the repository's default branch. A run on
  its base branch is only fast-forwarded, never replayed or pushed. Any other
  branch is never rewritten or pushed; when it is behind, the run blocks. A
  branch that is strictly behind its own published branch and clean is
  fast-forwarded to it first; nothing is pushed then.
- **The pin**: `ballast run start` pins the branch and the feature directory
  (whose Issue number decides which branch may be rewritten) in your state
  directory before the first agent step; a continuation uses its source run's
  pin. A human-gated `start` without exactly one valid `-i
  feature_directory=specs/<issue>-<slug>` is refused before any check. A
  `resume` or `continue` of a run whose pin lacks the branch or the feature
  (started before branch pinning) blocks and asks for a new run. The run must
  be on its pinned branch.
- **Requirements**: `git` 2.41 or later on `PATH`, outside every checkout and
  temp directory (`ballast doctor` checks it). Shallow checkouts and partial
  clones are refused, as are checkouts that borrow objects through
  `objects/info/alternates`; unshallow the checkout, or clone it again without
  `--filter` or alternates.
- **Plan and review evidence**: when the base and the feature both changed a
  file and the feature has a `plan.md` or review evidence, the line names that
  evidence as possibly stale, the ledger event records it, and the Draft PR's
  Ballast section lists the dated entry and its files (the newest 20 entries,
  from your state directory). This also holds for a synchronization kept by a
  `protected-input` block or finished from a write-ahead record. No gate is
  added and no review re-runs; the human approving the merge sees the
  staleness.

When the branch cannot be updated safely, the launcher changes nothing, starts
no agent, prints `BLOCKED_UPSTREAM_SYNC (CAUSE): DETAIL` and one `Recovery:`
action on stderr, and exits 1 (130 after Ctrl-C). An Autonomous `start` records
the block in category `upstream-sync`; recover by removing the cause and
starting the run again, because `ballast run continue` has nothing to continue
in a run stopped before its first agent step. Every check records one
`branch_sync` event in the run ledger. "rerun" below is printed as the full
command: `ballast run resume RUN_ID`, your `ballast run start` command, or
your `ballast run continue` command.

| Cause | When | Recovery |
| --- | --- | --- |
| `busy` | another invocation is synchronizing the same branch | another ballast run is synchronizing {branch}; retry when it finishes |
| `git-unavailable` | no trusted `git`, or one older than 2.41 | put a system git 2.41 or later on PATH ahead of any checkout directory |
| `git-unavailable` | shallow checkout | git fetch --unshallow, then rerun |
| `git-unavailable` | partial clone | clone the repository again without --filter, then rerun |
| `git-unavailable` | alternate object store | clone the repository again without alternates, then rerun |
| `in-progress` | a rebase, merge, cherry-pick, revert or bisect is in progress | finish or abort the {operation} yourself, then rerun |
| `in-progress` | `index.lock` exists | if no git process is running, remove {path}, then rerun |
| `wrong-branch` | detached HEAD, or not the pinned branch (at `start`, `{pinned}` is the feature's branch name) | git switch {pinned}, then rerun |
| `wrong-branch` | the run has no branch or feature pin | after checking the feature in the run's record, add "feature": "specs/<N>-<slug>" (and "branch" when missing) to the run's pin in the launcher state directory (see Runs started before branch pinning), then rerun |
| `unknown-base` | no `[github] repository` in `ballast.toml` | declare [github] repository and run ballast trust |
| `unknown-base` | the base or a default branch does not exist on the repository | restore {base} on {repo}; Ballast never substitutes another base |
| `fetch-failed` | the repository cannot be reached or read | check network access and credentials for {repo} (Ballast cannot answer a prompt), then rerun |
| `not-feature-branch` | behind on a branch that is not the feature branch of the pinned feature | synchronize {branch} yourself, or run the feature on its own branch: git switch -c {feature_branch} |
| `diverged` | the branch and its published branch both have commits, or the published branch moved during the check | reconcile by hand: git pull --rebase {remote} {branch}, then rerun |
| `diverged` | the base was rewritten and the old base is unknown | rebase by hand onto {base}, then rerun |
| `diverged` | the base branch itself has local commits | git switch -c {new_branch} |
| `dirty` | uncommitted changes (tracked, or untracked and not ignored) | commit or finish these changes (Ballast never stashes or discards them), then rerun |
| `dirty` | ignored files the update would overwrite, or untracked files in the way | move or commit these files, then rerun |
| `dirty` | uncommitted changes while finishing a synchronization already pushed | move these changes aside without committing them (Ballast never stashes or discards them), then rerun to finish the synchronization |
| `dirty` | files in the way while finishing a synchronization already pushed | move or commit these files, then rerun to finish the synchronization |
| `dirty` | an update interrupted while it wrote the working tree | git restore --source={new_head} --staged --worktree ., then rerun to finish the synchronization |
| `conflict` | replaying a feature commit conflicts | rebase by hand: git pull --rebase {remote} {base}, resolve, then rerun |
| `conflict` | replaying a commit of a published feature branch conflicts | rebase by hand: git pull --rebase {remote} {base}, resolve, git push --force-with-lease={branch}:{published} {remote} {branch}, then rerun |
| `conflict` | a commit made after a pushed synchronization conflicts | git rebase --onto {new_head} {old_head} {branch}, resolve, then rerun |
| `push-failed` | the push failed and a retry can succeed alone | rerun |
| `push-failed` | the repository rejected the push | check {repo}'s branch rules for {branch} (protection, required signatures), then rerun |
| `protected-input` | the update changed `ballast.toml`, `.ballast/`, `.specify/` or `.venv/` | review these changes; after a pin change run ballast setup first, then ballast trust (operator only) |
| `internal-error` | an unexpected failure, Ctrl-C, or the check could not be recorded | report it with the run ID, then rerun |
| `internal-error` | no committer identity | set user.name and user.email in your global Git configuration, then rerun |
| `internal-error` | invalid write-ahead record | report it with the run ID; Ballast keeps {record} until you check {branch} and its published branch and delete it |
| `busy`, `internal-error` | after the published branch was already updated | rerun to finish the synchronization |

"Nothing changes" has two exceptions. `protected-input` keeps the completed
synchronization, so you can review it and run `ballast trust`; the next
`ballast run` is refused until you do. A block after a successful push leaves
the published branch at the rebased commit; the next invocation on the branch,
whatever its run ID, finishes the synchronization from a write-ahead record in
your state directory, and says so with `completed the interrupted
synchronization from run RUN_ID`.

The by-hand recoveries use `origin`, which must name the repository pinned in
`[github] repository`, and run Git in the checkout with your credentials, so
its hooks and configuration apply: review them first if an agent could have
changed them.

What the check never does: stash, reset or discard changes; overwrite or
delete ignored files; push without a lease; push or rewrite the base or any
branch other than the feature branch; run a hook, merge driver, filter,
`core.sshCommand`, credential helper or any other program named by the
checkout's Git configuration or attributes; prompt for a credential; or print
Git's own output. It fetches, replays and pushes in a throwaway repository
with an empty configuration, so only your global and system Git configuration
apply, and replayed commits carry your global committer identity.

Differences from `git rebase`: replayed commits are unsigned; merge attributes
such as `merge=union` come from the fetched base's `.gitattributes`, not from
each replayed commit or the feature branch; no `rebase.*` configuration
applies. As with `git rebase`, merge commits are dropped and their non-merge
commits replayed, and a change already upstream is dropped.

Authority: the check is trusted launcher code, imported by `run.py` after the
launcher verified the protected inputs. No agent step can run, skip or
configure it. See ADR-0005 in the Ballast repository.

## Draft PR

At the end of every `ballast run start`, `resume` or `continue` invocation,
whether the workflow completed, paused at a gate or failed, after an
Autonomous or Chat run's own publication, after every Chat step, and on
`ballast run checkpoint RUN_ID` for an Autonomous or Chat run (which never
creates a PR), the launcher runs a Draft PR checkpoint for an issue-linked feature (`specs/<issue>-<slug>/`). Once the
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
- An Autonomous run's publisher opens its own Draft PR, whose body references
  the Issue; the checkpoint reuses that PR and leaves its body unchanged.
- The checkpoint never pushes: publishing the branch stays your action, except
  for an Autonomous run's publisher. It never
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

`ballast run start` pins the branch before any agent runs (see
[Branch synchronization](#branch-synchronization)); every later checkpoint must
be on that branch, published under that name.

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

### Acceptance packet

When the checkpoint ends with an open Ballast Draft PR (`created` or
`reused`), it also publishes an acceptance packet into that PR: a second
section between `<!-- ballast:acceptance-packet:begin -->` and
`<!-- ballast:acceptance-packet:end -->`. The packet is a derived summary for
review, not an approval, and records none; the sources it links are
authoritative. It is rebuilt from those sources at every checkpoint.

- **Header**: the feature version (the Git tree of `specs/<feature>/` at the
  PR's head commit), the spec's digest, the base and head commits with a diff
  link, the run and its mode, the generation time, the recorded risk, and
  counts of criteria per state, open findings and decisions.
- **Criteria**: every `AC-NNN` of `spec.md` at the head commit, once, in spec
  order, linked to its line, with one evidence state:

  | State | Meaning |
  | --- | --- |
  | `verified` | every test `acceptance-evidence.json` maps to it passed in a `ballast ledger check` or an Autonomous run's `runner-recorded` check bound to the head commit, the spec at head and the manifest at head |
  | `failed` | a mapped test failed at the head commit |
  | `stale` | evidence exists only for another commit, spec or manifest; the packet names which |
  | `not run` | a mapped test has no recorded check |
  | `missing` | no `acceptance-evidence.json`, or no test mapped to the criterion (`[]` included); a row whose criterion an open `[DEFERRED-TO-PR]` task cites names that task |

  Each test links to its file at the head commit; ledger evidence, which has
  no URL, is named `ledger event <seq> of run <run>`, prefixed
  `runner-recorded` when the Autonomous runner recorded it. A verified row
  also links the head commit's GitHub check runs when there are any. CI and
  the `[checks]` commands run whole suites, so they never change a
  criterion's state.
- **Decisions, open findings and checks**: an Autonomous run's provisional
  decisions labeled `agent-provisional` and linked to the committed run
  record, human gate decisions and recorded human actions labeled `human`,
  `DEC-NNNN` records of `decisions.md`, open review findings with severity and
  report, `run-checks` results, GitHub check runs at the head commit and
  suite-wide ledger checks. Zero counts are written as `None (0).`
- **Deferred to the PR**: open `tasks.md` tasks tagged `[DEFERRED-TO-PR]` at
  the head commit, each linked to its line, when there are any. They are
  operator checks, never evidence.
- **Sources**: intent, spec, plan, tasks, decisions, acceptance evidence,
  review reports, run record and diff, each pinned to the head commit, or
  `not present`.

Per-criterion evidence comes from `ballast ledger check RUN_ID AC-NNN
tests.test_module.Class.test_method` on a clean checkout of the pushed
commit (`operator-attested`) and, in an Autonomous run, from `run-checks`,
which runs each mapped test after the final review and records it
`runner-recorded`: agent-written tests run by Ballast, bound to the tree the
run publishes, never an operator's check. The packet is rebuilt only at a checkpoint, at
the end of `ballast run start`, `resume` and `continue`, from that run's own
ledger and records: record checks for a human-gated run under its run ID, then
resume it. For an Autonomous or Chat run, record checks under its run ID, then
`ballast run checkpoint RUN_ID` rebuilds the packet and the Draft PR section
from that run's ledger and records, in any status and without an agent; its
packet's run line names the run ID and its current mode. An Autonomous run's `ballast run
publish` retry runs no checkpoint, and `ballast run continue` starts a
new run whose packet reads only the new run's ledger.

Optional review sections come from the `[review]` table of `ballast.toml`,
which agents cannot change (run `ballast trust` after editing it):

```toml
[review]
openapi = "docs/api/openapi.json"   # a committed JSON OpenAPI document

[[review.ui_states]]                 # at most 50
name = "Login error"                 # 1-80 characters
criteria = ["AC-003"]
path = "docs/screens/login-error.png"   # a committed file, or instead:
# check = "ui / login-error"            # a GitHub check run on the head commit
```

- `openapi` is compared between the base and head commits through the GitHub
  contents API. The packet lists operations added, removed and changed by
  method and path, and flags as potentially breaking a removed operation, a
  removed or newly required parameter, a newly required request body, and a
  top-level request field removed or newly required. The classification needs
  human review. Only JSON is read; commit a JSON rendering of a YAML document.
  Otherwise the section says `no API change`, `added in this PR`,
  `removed in this PR` or `could not compare (<reason>)`.
- Each UI state appears beside its criteria with a link to the file at the
  head commit, or the check run's result (`passed`, `failed`, `not run`,
  `not run (in progress)`), or `missing`. Ballast captures nothing itself.
- Without the table each section is one `not configured` line; an invalid
  value gives `configuration invalid (<reason>)` and the rest of the packet is
  published.

The packet section is replaced in place, appended again after a human deletes
it, and left unedited when nothing but its generation time changed. When the
PR description has no room, the packet keeps its header, every criterion not
`verified`, every open finding and every provisional decision, and shortens the
rest, and a list longer than 50 lines is cut in the PR. Every checkpoint that
builds a packet writes the complete text to
`speckit-runs/<run>/acceptance-packet.md` under the clone's Git common
directory (mode 0600). Agent-written text is shown as inert data: it cannot end
the section, form a link or mention, or change a state or label.

The run prints a second line, `Acceptance packet: <state>[ (<reason>)][
#<number> head <commit>][: <remedy>]`, and records an `acceptance_packet`
ledger event. A packet failure never changes the Draft PR outcome, the run's
exit status or its step state; the next checkpoint retries.

| State | Reason | Remedy |
| --- | --- | --- |
| `published` | | none: no packet section existed |
| `updated` | | none: the section was replaced |
| `unchanged` | | none: nothing changed, so the PR was not edited |
| `pending` | `no-pr` | see the Draft PR line; the next run retries |
| `pending` | `pr-blocked` | see the Draft PR line |
| `pending` | `head-not-local` | fetch the feature branch, then resume |
| `failed-retryable` | `gh-*`, `github-*` | as for the Draft PR line |
| `failed-retryable` | `body-changed` | none: the next run retries |
| `failed-retryable` | `section-unmanaged` | keep at most one acceptance-packet section in the PR body |
| `failed-retryable` | `source-unreadable` | commit a readable `spec.md`; the next run retries |
| `failed-retryable` | `manifest-malformed` | fix the manifest; `ballast ledger check` validates it |
| `failed-retryable` | `ledger-invalid` | run `ballast ledger report --run RUN_ID` |
| `failed-retryable` | `too-large` | shorten the PR description outside Ballast's sections |
| `failed-retryable` | `internal-error` | report it with the run ID; the next run retries |

The packet adds only read calls to the checkpoint's GitHub authority (the PR,
check runs at the head commit, the configured OpenAPI file) and local Git reads
of the head commit; it never fetches, pushes or commits. See ADR-0006 in the
Ballast repository.

### Demo capture

A reviewer can ask for a short video of implemented UI behavior. The operator
requests it; the capture runs on a GitHub-hosted runner, and the packet links
the video. A video helps a reviewer see behavior. It is never evidence for a
criterion, never changes a criterion's state, and is never an approval. The
capture's outcome is reported by the same job that runs the PR's code, so that
code could make a failed journey read `captured`; watch the video.

**Setup.** Declare the scenarios in the `[demo]` table of `ballast.toml`, which
agents cannot change (run `ballast trust` after editing it):

```toml
[demo]
retention_days = 14        # optional, 1-90; GitHub applies a lower repository limit
timeout_minutes = 15       # optional, 1-60

[[demo.scenarios]]         # 1-20, unique names
name = "login-journey"     # [A-Za-z0-9._-]{1,64}
command = "npm run demo:login"          # one line, at most 1000 characters
video = "demo-output/login.webm"        # the one file the command writes
environment = "Chromium 1280x720, seeded fixtures"   # 1-80 characters
```

Then copy `templates/github/workflows/ballast-demo.yml` of the pinned Ballast
version to `.github/workflows/ballast-demo.yml` on the default branch. Every
feature branch must carry the default branch's `ballast-demo.yml` unchanged:
the capture runs on the feature branch's ref, so the PR's code can write no
cache that the default branch's workflows restore, and Ballast refuses a
branch whose copy is missing or differs (`workflow-differs`). Cut feature
branches after installing the workflow, or sync them with the default branch.
The command installs its own browser or recorder; Ballast installs and
downloads none.

**Data.** The job has no secrets and a read-only token. The command must use
only seeded, nonsensitive data and fake accounts: the video and the job log
are readable by anyone with repository read access, which on a public
repository is everyone. The video is an Actions artifact; the log holds the
command and everything it prints.

**Requesting.** `ballast run demo RUN_ID SCENARIO [--no-wait]`, from the
operator's terminal, for a run with an open Ballast Draft PR in any mode. It
starts no agent, holds the run's lock and refuses while an agent step is in
progress. It dispatches the workflow for the PR's head commit, records a
`demo_capture` ledger event, waits at most 120 seconds (none with
`--no-wait`) and refreshes the packet. It prints `Demo capture: <state>[
(<reason>)][ <scenario> at <commit>][: <remedy or link>]`, then the Draft PR
and packet lines. A refusal or a GitHub failure dispatches nothing, records
nothing, creates no PR and exits 1; a dispatched capture exits 0 whatever its
outcome. A local error after the dispatch succeeded, such as a failed ledger
write, prints `failed-retryable (internal-error)` and exits 1 although a run
was dispatched; that run is never linked or shown, so request again. A refusal names its reason and remedy: `not-configured`,
`config-invalid`, `unknown-scenario`, `no-draft-pr`, `pr-not-open`,
`workflow-not-installed`, `workflow-disabled`, `workflow-differs`, `untrusted`
or `lock-held`. A GitHub failure is `failed-retryable` with the Draft PR
line's causes; `gh-forbidden` means the operator's account needs Actions write
access. An unfinished capture is refreshed by the next checkpoint, such as
`ballast run checkpoint RUN_ID`.

**Reading the result.** The packet's `### Demo captures` section has one line
per declared scenario, for that scenario's newest request:

| State | Meaning |
| --- | --- |
| `captured` | the run at the head commit succeeded; the line links the video |
| `in progress` | `queued` (no run yet) or `running`; the line links the run when known |
| `failed` | `command-failed`, `timed-out`, `cancelled`, `request-invalid`, `job-failed`, `run-not-found` (no run within 24 hours), `run-ambiguous`, `run-list-truncated` or `commit-mismatch` (the run is not at the requested commit) |
| `missing` | the run ended without a usable video: `no-video`, `expired` or `artifact-absent` |
| `stale` | the capture is for an earlier commit; the line shows that commit and the outcome there, and links the run, never the video |
| `not yet requested` | the scenario is declared but no capture was requested in this run |
| `not configured` | the one line when `ballast.toml` has no `[demo]` table |
| `configuration invalid` | the one line when `[demo]` breaks a rule; it names the reason, and the rest of the packet is published |

A command that itself exits 124 or 137, or is killed for lack of memory, is
reported `timed-out`, like one stopped by the timeout. Ballast reads only the
run's status, the failed step's name and the artifact's metadata; it never
downloads a log or the video. An event for a scenario that is no longer
declared shows `no longer declared`, with no link. A new run started by
`ballast run continue` lists its scenarios as `not yet requested`.

**Reproducing locally.** Each line names the scenario's command as declared,
in a code span you can copy. Check out the captured commit in a clean checkout
and run that command, without credentials, to see the same journey. When the
declared command changed after the capture, the line says so. A backtick in
the command is dropped from the line, and a token-like value is shown as
`[redacted]`; take such a command from `ballast.toml`.

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
