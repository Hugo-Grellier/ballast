# Dispatching agent-native subagents as workers

Guidance for a coordinator that uses its agent's own subagents (for example
Claude Code subagents) as implementation or review workers. Claude Code is an
example; the rules hold for any agent with a subagent mechanism.

- **Create the worktree yourself.** Claim and create it with
  [`tools/worktree.py`](standalone.md) and pass the worker its absolute path.
  Do not rely on the agent's built-in worktree isolation: it can refuse git
  commands that a user-level command-rewriting or output-filtering hook has
  altered, which stops every worker at once.
- **Embed the issue; do not ask the worker to fetch it.** Output-filtering hooks
  can swallow `gh issue view` and `gh pr view`, and a worker then implements
  from your notes alone. Write the issue body, comments and acceptance criteria
  to a file and tell the worker to read it. Where a fetch is unavoidable,
  `gh api repos/OWNER/REPO/issues/N --jq .body` returns the text.
- **Ask for a fixed short result block.** Results above the notification size
  limit arrive truncated. Require a short block that starts with the verdict
  (for example issue, head SHA, gate pass/fail, one line per acceptance
  criterion, frictions) and keep detail in the branch or PR.
- **The local gate is not CI.** A test can pass only because an agent CLI or
  credential exists on the host. Tests must not depend on either (see the
  [testing policy](../templates/policies/testing.md)); read CI on the PR head
  before calling a PR ready, as in [issue workflow](issue-workflow.md) step 6.

Current limits: executions dispatched this way are not yet recorded as
Ballast executions (#197), and `coordinate.py publish` still requires a
completed review from a `worker.py --role review` worker, so a subagent review
does not satisfy it.
