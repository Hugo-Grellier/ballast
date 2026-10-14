# Orca lessons for Ballast 2.0 on a solo budget

Research date: 2026-10-14. Repository: [stablyai/orca](https://github.com/stablyai/orca).
Source snapshot: `d194712952ab6e4990f91b1157211c1805eb5a36`. Findings come from
source files, installed CLI guides/help, and specific public PRs. No Orca builds,
tests, workers, paid services, or production operations were started.

## What the evidence establishes

Orca is deliberately built for agent-assisted development. Its contribution guide
asks for an AI review summary and leaves releases under maintainer control. That
does not establish that all implementation or decisions are autonomous. Public
author metadata and agent-oriented instructions cannot quantify human involvement.
[Contribution guide](https://github.com/stablyai/orca/blob/d194712952ab6e4990f91b1157211c1805eb5a36/.github/CONTRIBUTING.md).

## Practices worth adapting

| Observed practice | Application to Ballast 2.0 |
| --- | --- |
| One instruction entry point, reused by agents | Keep project rules in AGENTS.md and an import for clients that need it. |
| Edits restricted to the assigned worktree | Resolve worker file references within that checkout; reject references pointing into another checkout. |
| Runtime owns agent status | Use Orca's execution records; issue comments and cards are projections. |
| Readable PR explanations and actual verification | Explain the user-visible result, changed mechanism, acceptance evidence, and remaining gaps. |
| Bounded source/history scans and API calls | Batch discovery and consume events; avoid repeatedly rereading every transcript. |

The worktree, status, bounded-scan, and validation rules are explicit in
[AGENTS.md](https://github.com/stablyai/orca/blob/d194712952ab6e4990f91b1157211c1805eb5a36/AGENTS.md).
The client import is visible in
[CLAUDE.md](https://github.com/stablyai/orca/blob/d194712952ab6e4990f91b1157211c1805eb5a36/CLAUDE.md).
The PR explanation format is in its
[template](https://github.com/stablyai/orca/blob/d194712952ab6e4990f91b1157211c1805eb5a36/.github/pull_request_template.md).

Orca's PR workflow cancels superseded runs, routes jobs by changed paths, and
keeps an aggregate gate when expensive jobs are unnecessary. Its source comments
also document advisory E2E coverage outside that gate. The lesson is to distinguish
required acceptance evidence from advisory signals and justified skips. These
comments describe the authors' baseline assessment; this research did not rerun
the suite. Copy the idea of proportional checks, rather than this application's
large platform matrix or its specific exclusions.
[PR workflow](https://github.com/stablyai/orca/blob/d194712952ab6e4990f91b1157211c1805eb5a36/.github/workflows/pr.yml).

For a small Ballast suite, running the full inexpensive suite may be simpler and
safer than building test selection. Optimize only after measuring a bottleneck.

## Real limits and failures to learn from

**Unused automation still consumes resources.** A merged change removes the daily
and post-merge triggers for headless-server checks because maintainers say those
results were unused. It preserves manual and release entry points. There is no
published dollar saving in that PR. Recommendation: every recurring job needs a
specific consumer, purpose, and resource ceiling.
[PR #28664](https://github.com/stablyai/orca/pull/28664).

**One-time requests can accidentally become permanent work.** Another merged PR
removes a recurring homepage check because the requested task was a one-time
check. Recommendation: explicitly record one-time versus recurring execution;
creating a schedule requires a separate human decision.
[PR #28682](https://github.com/stablyai/orca/pull/28682).

**A green check may belong to the wrong workflow.** A corrective PR reports that
a change merged after Mobile's check passed while the full PR gate was pending
and later failed. It introduces a unique aggregate name and exact-commit/workflow
guidance. This is a documented incident report with changes, not an independent
reconstruction of all execution history. Recommendation: readiness identifies
the commit, intended workflow/check, required jobs, and review revision.
[PR #28632](https://github.com/stablyai/orca/pull/28632).

**Free reviewers have capacity limits.** A public bot comment reports that an
included OSS review allowance was exhausted and the next review required waiting.
That observation is specific to the service/account/time, not a universal quota.
Recommendation: expose review waiting, retain the draft, and use only an explicitly
allowed available alternative. Never silently skip review or purchase capacity.
[Observed review-limit comment](https://github.com/stablyai/orca/pull/28682#issuecomment-6164888360).

**Observability can become its own subsystem.** Orca has a scheduled runner-demand
report and a collector that samples workflow runs and reports runner time, wasted
cancelled-run time, and queue delay. Those are useful signals, but that reporting
machinery would itself need maintaining. Begin with issue/PR evidence and existing
Actions summaries; add an on-demand report only when it answers a recurring question.
[Workflow](https://github.com/stablyai/orca/blob/d194712952ab6e4990f91b1157211c1805eb5a36/.github/workflows/ci-runner-demand.yml),
[collector](https://github.com/stablyai/orca/blob/d194712952ab6e4990f91b1157211c1805eb5a36/config/scripts/ci-runner-demand.mjs).

## A proposed pilot for one person

Operator constraints: no agents in CI, and Orca must be optional. Implementation,
pair review, and repair run on the authorized development host using a standalone
backend or Orca; CI supplies deterministic verification results. Orca's own
agent-enabled CI is not an adoption target.

The following are recommendations, not measurements of an optimal configuration:

- Use the existing machine and authorized CLI access. Start with one implementation
  worker and at most one independent reviewer, with a backlog of two ready PRs.
  Increase concurrency only when completed outcomes improve without more waiting,
  regressions, resource contention, or human review backlog.
- Select the lowest sufficient configured model/effort. Keep expensive capacity
  for evidenced escalation. Do not spawn several competing implementations of
  the same issue. A separate session with the same available provider can provide
  independent review when another provider would add cost.
- Reuse Orca's worktree/lifecycle facilities when selected. Standalone execution
  uses Git and installed agent tools with a small durable execution record.
  Ballast owns the issue policy, acceptance contract, and missing integration glue.
  Avoid a remote fleet, scheduler, dashboard, or subscription requirement.
- Review after useful checks pass. Reuse evidence only when its source, scope,
  commit and relevant configuration remain valid. Batch small local edits before
  pushing rather than triggering CI after each file change.
- On quota exhaustion, pause affected dispatches and surface the wait. Keep
  completed work and review requirements. Automated retries need a known retry
  window and a bound; waiting is preferable to an unexpected bill.
- Keep merge as the human decision. Make PRs small enough to assess, with concise
  acceptance evidence. Your attention, not just agent execution, limits throughput.

Existing subscriptions are not free computation: they have an existing cost and
finite capacity. Local models also consume hardware, electricity, and setup time;
their quality and explicit model/effort reporting need validation. With no usable
model access or hardware, unrestricted agent throughput cannot be promised.

For CI, GitHub currently provides free standard hosted runner execution for public
repositories, while larger runners are charged even for public repositories.
Private repositories have included allowances; storage has its own billing rules.
Use standard runners where applicable, small artifacts with bounded retention,
and account spending controls. This research did not inspect or change the user's
billing settings and does not guarantee zero charges.
[GitHub billing documentation](https://docs.github.com/en/billing/concepts/product-billing/github-actions).

## Recommended proposal changes

Keep instruction phases portable and support standalone execution plus an optional
Orca adapter. Pilot verified routing and safe resume before adding a general queue
engine. Add explicit recurring-automation authorization, budget-aware waiting,
and workflow identity to readiness evidence. Treat subscriptions, CI, disk/RAM,
and human review capacity as real limits. Measure accepted outcomes, cycle time,
rework, regressions, and resource use across comparable issues.
