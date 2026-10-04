# ADR-0003: The trusted launcher holds GitHub authority, agents never do

- Status: proposed (needs human approval; set to accepted only after it)
- Feature: [17-draft-pr](../../specs/17-draft-pr/spec.md), FR-001, FR-013, SC-005; plan [§ Proposed architecture decisions](../../specs/17-draft-pr/plan.md#architecture-boundaries)

## Context

Feature work under `ballast run` must become visible in one Draft PR without a manual step. Agents are denied `git push` and `gh`, and must stay so (BL-INV-003). Something on the operator's side therefore has to talk to GitHub, and later features (the autonomous publisher #27, ready-for-review policy, review packets) will need the same boundary.

## Decision

- The trusted `run.py` may call the operator's GitHub CLI after a run, from the module `draft_pr.py` that it imports at startup, before any agent step.
- `gh` and `git` are resolved by the rule of `resolve_program` in `tools/ballast`: absolute `PATH` entries only, never an entry or a resolved executable inside any Git working tree. Each is called by its absolute path, with a list argv, no shell and a 30 s limit. Their `PATH` keeps only entries outside every working tree, Git location variables are dropped, and `core.fsmonitor`/`core.hooksPath` are overridden. `gh` starts in an empty temporary directory so it never reads the checkout's agent-writable `.git/config` (DEC-0004).
- The target repository is `[github] repository` in the protected `ballast.toml`; the branch's upstream remote must match it, or the checkpoint stops as `blocked-unlinked` (DEC-0005).
- The command allowlist is fixed:
  - `gh api` reads of the repository, an Issue, its comments, the pulls for one head, a compare and the base branch's pull-request template;
  - `gh pr create --draft --body-file -`;
  - `gh pr edit <N> --body-file -`, rewriting only the Ballast-marked section;
  - `git symbolic-ref`, `git for-each-ref`, `git remote get-url` and `git rev-parse`; no push, fetch or commit.
- The checkpoint refuses to act while `BALLAST_TAMPERED` or the launcher's `in-progress` marker exists.
- Agents keep every existing denial, and `run.py` removes `GH_TOKEN`, `GITHUB_TOKEN`, `GH_ENTERPRISE_TOKEN` and `GITHUB_ENTERPRISE_TOKEN` from the environment it passes to the workflow engine. The checkpoint, in `run.py`'s own process, keeps them.
- `gh` output is parsed, never printed or stored; failures map to fixed reasons and remedies.

## Consequences

- One place states what GitHub authority Ballast uses; later features extend this allowlist by a new ADR rather than adding a second path.
- Ballast never handles a token: `gh` keeps its own credential store.
- An operator who exported a GitHub token no longer leaks it to agent steps.
- A project without an authenticated `gh` 2.48 or later gets `failed-retryable` outcomes and no PR; the workflow is unaffected.

## Rejected alternatives

- Letting an agent run `gh`: it would gain the operator's authority (BL-INV-003).
- `shutil.which("gh")`: a checkout-local `gh` placed by an agent would run with operator credentials.
- A hand-written HTTPS client reading the token: Ballast would then handle the credential.
- A GitHub App or Action: an operator-side change in every project, out of scope for 1.0.
