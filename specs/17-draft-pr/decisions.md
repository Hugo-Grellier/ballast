# Decisions

## DEC-0001 — Proposal

- Source: analyze I1. `skipped` (tamper or in-progress marker present) is printed but not recorded, while FR-010 asks every checkpoint to record an outcome.
- Proposal: exempt this path from FR-010: while either marker exists the ledger itself refuses every write, so the printed line is the outcome.

## DEC-0001 — Resolution

- Decision: accepted (agent, provisional, under the operator's standing authority of 2026-10-03).
- Rationale: recording is impossible by design in that state; forcing a write would weaken the tamper stop.

## DEC-0002 — Proposal

- Source: analyze I3. The design adds reasons not listed in the spec: `blocked-ambiguous/base-mismatch`, `blocked-ambiguous/create-unverified`, `pending/on-base-branch`, `pending/diff-unclassified`, `failed-retryable/lock-busy`, `failed-retryable/internal-error`, `failed-retryable/gh-untrusted`, `failed-retryable/git-untrusted`.
- Proposal: accept them as reasons under the spec's existing seven states; FR-010's state list is unchanged.

## DEC-0002 — Resolution

- Decision: accepted (agent, provisional, under the operator's standing authority of 2026-10-03).
- Rationale: they refine causes and remedies without adding states.

## DEC-0003 — Proposal

- Source: implementation (manual path after run 3eea832b), T024/T026. `data-model.md` § Marked section says a reused PR with no section and no Issue reference gets "only the line `Related to #N`". Spec AC-007 ("one Ballast-marked section that adds the Issue link"), `research.md` § Reuse, `quickstart.md` and tasks T024/T026 all say the whole marked section is appended.
- Classification: spec ambiguity (artifact wording conflict).
- Current implementation: follows AC-007, research, quickstart and tasks: it appends a blank line and the marked section, keeping every other byte (`ReuseTests.test_hand_opened_pr_without_reference_gets_the_section`).
- Proposal: correct the data-model row to "append the marked section after a blank line". If the human prefers the data-model wording instead, `reuse()` appends `Related to #N` alone and the test changes accordingly.


## DEC-0003 — Resolution

- Accepted by the operator (2026-10-04). `data-model.md` now appends the whole marked section, matching AC-007, research, quickstart and T024/T026. No code change.

## DEC-0004 — Proposal

- Source: implementation review against BL-INV-002 (security). The checkpoint resolves `gh` outside every working tree, but `_command` passes `gh` the operator's unmodified `PATH`, as the contract's Environment boundary specifies. `gh pr create` runs `git` itself (remote listing, uncommitted-change count), found through that `PATH`. A checkout-local `git` placed ahead of the system one, the exact case T008 guards for Ballast's own calls, would then run inside `gh` with the operator's credentials in its environment.
- Classification: architecture issue (security boundary; R2).
- Proposal: in `_command`, replace `PATH` for every `gh` and `git` call with only the absolute `PATH` entries that lie outside every Git working tree (the entries `resolve_program` keeps), and add a test where a checkout-local `git` first on `PATH` is not reachable through the environment given to `gh`. Update the contract's Environment boundary and ADR-0003 to match.
- Not implemented: it changes the approved environment contract and a security boundary, so it waits for human resolution. T039's security review should consider it.


## DEC-0004 — Resolution

- Accepted by the operator (2026-10-04). `_command` gives `gh` and `git` only `PATH` entries outside every working tree, drops `GIT_DIR`/`GIT_WORK_TREE`/`GIT_COMMON_DIR`/`GIT_INDEX_FILE`, overrides `core.fsmonitor` and `core.hooksPath`, and sets `GIT_CEILING_DIRECTORIES`. A follow-up security review showed PATH alone was not enough: `gh`'s own `git` read the checkout's agent-writable `.git/config` (a `core.fsmonitor` command ran with the operator's token in its environment). Every `gh` call now starts in an empty temporary directory. Contract, ADR-0003 and policy updated (T041).

## DEC-0005 — Proposal

- Source: background security review of commit 832da86 (confused deputy). The checkpoint derives the target repository from `<git> remote get-url <upstream remote>` and the branch upstream from `for-each-ref`, both read from `.git/config`. The launcher leaves the `.git` directory writable by the agent (`launcher.py`, protected-path docstring), so an agent can run `git remote set-url` / `git branch --set-upstream-to` and steer the operator's `gh` credentials to create a Draft PR, or rewrite the Ballast section of a PR body, in any other repository the operator can write.
- Classification: architecture issue (security boundary; R2).
- Proposal: pin the GitHub repository in operator-controlled state rather than reading it from agent-writable Git config. Options: (a) record `owner/repo` in the run's protected `inputs.json` at `ballast run start` and refuse (`blocked-…`) when the upstream remote later resolves elsewhere; (b) record it in the trust baseline at `ballast trust`; (c) declare it in `ballast.toml`. Option (a) still trusts `.git/config` at start time, which an earlier run's agent could have changed, so (b) or (c) is stronger. Add a test where the remote URL is changed between trust and checkpoint and no `gh` write call is made.
- Not implemented: it changes the approved data sources and a security boundary, so it waits for human resolution. T039's security review should consider it together with DEC-0004.

## DEC-0005 — Resolution

- Accepted by the operator (2026-10-04), option (c): `[github] repository = "OWNER/NAME"` in `ballast.toml`. The upstream remote must match it case-insensitively, else `blocked-unlinked/repository-mismatch`; missing or invalid → `blocked-unlinked/no-repository`; both before any `gh` call. Contract, data model, research, quickstart (step 7), ADR-0003, policy and README updated (T041).
