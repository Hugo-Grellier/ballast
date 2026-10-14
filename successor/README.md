# Ballast 2.0 proposal

Ballast 2.0 can evolve in this repository, keeping its name and history. Its core
would be a reusable set of repository instructions. Copy the files in `starter/`
into a project, customize its `AGENTS.md`, and tell your agent `Start #123`.
GitHub issues hold scope and progress; PRs hold changes and review evidence.
The goal is high issue throughput with controlled autonomy, verified results,
and visible execution. Starting from an existing agent conversation is the
primary path; each implementing issue gets its own worktree.
Agents, independent review, and repair loops run on the authorized development
host, using installed agent tools with or without Orca. CI runs deterministic
verification only. Agents can consume CI
results and repair failures from their issue worktrees; CI never launches agents
or calls models.

The normal flow is:

```text
Issue → read and scope → split if needed → clarify and plan as needed
      → implement → check → independent pair review → fix
      → PR ready for human merge
```

## Files to keep

| File in `starter/` | Purpose |
| --- | --- |
| `AGENTS.md` | Entry point, project context, authority, workflow trigger |
| `docs/issue-workflow.md` | Start, split, implement, resume, and publish |
| `docs/pair-review.md` | Instructions for an independent reviewer |
| `docs/model-routing.md` | Explicit model/effort selection and execution verification |
| `docs/execution.md` | Portable dispatch, worktrees, ownership, queue limits, recovery |
| `docs/orca-execution.md` (optional) | Orca-specific execution adapter |
| `.github/ISSUE_TEMPLATE/task.md` | Outcome and acceptance criteria |
| `.github/pull_request_template.md` | Evidence needed for a merge decision |

These seven core files and one optional Orca adapter are the instruction starter.
Standalone use requires no Orca installation, account, skills, or runtime.
There is no installer, runner,
generated policy tree, release pin, or required skills package. They work as
ordinary repository files with an agent that can read them, edit code, use
GitHub, and launch an independent reviewer. Keep the project's existing CI.
Enforced model routing additionally requires an execution integration that can
apply and report worker settings; the contract is included, its implementation
is not. Native tools may suffice when they meet that contract.
Where they do not, a small dispatcher that applies settings, verifies receipts,
and records execution is justified. Phase logic remains in the instructions.
Both standalone and Orca execution must satisfy the same routing, recovery, and
readiness contracts; standalone is a required supported path, not a reduced mode.

## Adopt the starter

1. Copy the contents of `starter/` into the adopting project, preserving hidden
   files. This directory remains a proposal until the Ballast 2.0 migration is
   reviewed; the existing repository rules still govern Ballast itself.
2. Fill the project context in `AGENTS.md` for each adopting project. Record
   its actual setup and verification commands, preferably commands already in
   CI. Merge with existing instructions rather than overwriting them.
3. Make the entry point available to your agent. Agents that read `AGENTS.md`
   use it directly; for Claude Code, add a root `CLAUDE.md` containing
   `@AGENTS.md`, merging that import with existing instructions when necessary.
4. Give the development agent repository access for issues, branches, pushes,
   and PRs. Use its native permissions and sandbox. Configure access outside
   tracked files. Verify that it can start a separate reviewer, or provide a
   second agent session for review.
5. Keep required CI checks and human merge approval in the hosting platform's
   branch rules. Choose the checks for the project's stack; this starter ships
   no generic CI workflow.
6. Try one bounded issue before adding conventions. Change these files directly
   when friction appears. Copy updates into consumers deliberately when useful.

The instructions guide agent behavior. They do not enforce a sandbox, protect
credentials, or provide Ballast's trusted launcher and tamper checks. Use the
agent's permission controls and repository protection for those boundaries.

## First executable proof: standalone routing qualification

From this repository, with an installed Codex client exposing model capabilities
and resolved thread-start configuration, run outside CI:

```sh
python3 -I -S tools/v2/qualify.py --model YOUR_MODEL_ID --effort YOUR_EFFORT
```

Both values are required. The probe checks the model catalog, starts a fresh
ephemeral read-only thread, and compares its resolved model, effort, provider,
directory, sandbox and approval policy. It accepts no task prompt and never
starts a model turn. Output contains only sanitized configuration evidence.
Protocol work has a default 30-second deadline, followed by bounded client cleanup.

CI runs only the deterministic fake-backend tests in `tests/test_v2_routing.py`;
the real probe refuses common CI environments before client startup. This guard
supports the operating policy; it is not a sandbox or detection of every possible
custom CI environment. Local [qualification evidence](routing-qualification.md)
is specific to the tested client version and route pairs. It cannot verify a
later worker session: the eventual dispatcher must repeat verification on the
same session immediately before task input.

## Daily use

- `Start #123`: complete the issue, including necessary child issues, to reviewed PRs.
- `Work the queue, up to 3 issues concurrently`: supervise eligible independent
  issues with explicit execution and backlog limits, using separate worktrees.
- `Continue #123`: reconstruct progress and finish the remaining work.
- `Investigate #123`: report findings and options on the issue; implementation
  requires a subsequent start request.
- `Review PR #456`: run the independent review instructions against that PR.

A start request authorizes the workflow's issue updates, necessary child issues,
branch publication, and PR creation in the named repository. Product decisions
and privileged operations follow the boundaries in `AGENTS.md`.

For a larger issue, expect one PR per independently mergeable child, in dependency
order. Children depending on an unmerged PR wait for that merge. A genuinely
cohesive change stays in one issue with a short checklist. You get a ready PR for
each completed unit and a precise status for any remaining children.

Clarification and planning scale with uncertainty. A small, clear fix gets a short
checklist and proceeds. Missing product choices get focused questions. A change
across components or a consequential boundary gets a concrete plan and a pair's
plan review before implementation. Human approval is needed for material scope,
architecture, or authority decisions; routine plans proceed autonomously.

## Modular phases and observable execution

Treat understand, decompose, clarify/plan, implement, verify, review, and publish
as named phases. Each phase needs its inputs, completion evidence, skip condition,
and escalation rule. Keep one default route; direct requests can invoke just a
phase. Extract separate phase files when reuse or complexity warrants it.

Keep a concise execution trace on the issue and its summary on the PR, following
the workflow's recording rules. Capture the instruction revision, phase outcomes,
skips and their reasons, waits for decisions, verification failures, and review
rounds. Preserve milestone history even as the current progress note changes.
GitHub timestamps, commits, reviews, and CI provide the supporting evidence.

Evaluate workflow changes across comparable tasks: time to a ready PR, time
blocked, human decisions needed, review rework, and defects or reverts after
merge. Include blocked and abandoned attempts. Keep elapsed time distinct from
measured agent runtime; record cost only when actually available. A shorter run
with missed requirements is not an improvement. Use the first few issues as a
baseline, then change one workflow behavior at a time and record the hypothesis
and observed tradeoffs. Small samples are signals to investigate.

This starts with ordinary issue and PR records. A reporting script or dashboard
can follow if reading those records repeatedly becomes a burden. The trace is
agent-reported evidence, without the tamper guarantees of the v1 runner.

Worker model and effort are selected independently of the launching conversation.
Record requested versus observed settings for each attempt. A backend that cannot
apply or expose them blocks routed execution instead of silently inheriting the
parent configuration. The routing contract includes integration acceptance cases
for agent-started tasks, nested workers, retries, resumes, and switches.

## Bring forward from Ballast

Carry forward the principles: explicit outcomes, small changes, dependency order,
independent review, evidence for acceptance, honest blockers, and human merge.
Rewrite those principles in these few files, using the starter as the baseline.

For an existing application adopting this workflow, retain its tests, CI, domain
knowledge, current architecture decisions, and relevant accepted requirements.
For Ballast 2.0 itself, the starter files become the proposed product; the old
implementation remains historical reference once its replacement is accepted.

Keep Ballast's issues, PRs, specs, decisions, and releases in this repository.
Re-triage unfinished issues against the accepted 2.0 direction; preserve applicable
acceptance criteria and dependencies, and explicitly close obsolete work. Existing
decisions remain authoritative until superseded. Old run state belongs to the
old workflow and does not become 2.0 progress.

Remove Ballast entry points and dependencies from an adopting project's active
instructions and CI as a separate reviewed migration. Inspect ignore rules and
generated files before removal. This kit does not migrate or archive anything.

## Evolve this repository to 2.0

1. Agree on the 2.0 product boundary: these instructions, issue-driven execution,
   conditional clarification and planning, independent review, and a ready PR.
2. Record the architecture change and v1 compatibility/migration policy through
   the current repository's required decision process. In particular, explicitly
   replace the trusted-runner guarantees and Spec Kit requirements.
3. Try the starter in a small consuming project and revise it from that evidence.
4. Switch this repository's active instructions, docs, and CI in reviewed changes;
   remove obsolete tooling and its tests only as its responsibilities retire.
5. Release 2.0 after human approval. Retain v1 tags and release artifacts for
   projects that still pin them. Archiving the repository is unnecessary.

## Keep it small

The [Orca research notes](orca-research.md) separate observed practices and
incidents from recommendations for a solo maintainer. The proposed pilot uses
one implementation worker, at most one independent reviewer, and two ready PRs
in the backlog, with existing authorized model access. These limits are starting
points to evaluate, not a claim of optimal throughput or a new service requirement.

Use issues for plans and progress, PRs for review evidence, and code plus tests
for behavior. Add an ADR when an actual architecture decision needs a durable
explanation. Add another workflow file only when repeated work demonstrates
that one is needed.
