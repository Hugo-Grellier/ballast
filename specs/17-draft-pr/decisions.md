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

## DEC-0006 — Proposal

- Source: R2 implementation review (`reviews/implementation-review-codex-1.md`, security, high). The published branch comes from `symbolic-ref HEAD` and its upstream in agent-writable `.git/config`. The repository pin (DEC-0005) stops redirection to another repository, but an agent can point the run at any other branch of the pinned repository; the checkpoint then creates a Draft PR from that branch or rewrites the Ballast section of its open PR.
- Classification: architecture issue (security boundary; R2).
- Proposal: record the feature branch in operator state (`state_dir`, outside the checkout) when the operator runs `ballast run start`, and stop as `blocked-unlinked/branch-mismatch` when the checked-out branch or its published name differs on any later checkpoint. Alternative: derive the branch from the feature directory name; rejected in research R4 because projects name branches freely.
- Not implemented: it adds operator state and a new outcome, so it waits for human resolution.

## DEC-0006 — Resolution

- Accepted by the operator (2026-10-04). `run.py` calls `draft_pr.pin_branch` at `ballast run start`, before the engine, writing `branch` and `published` to operator state outside the checkout; a resume never re-pins. The checkpoint stops as `blocked-unlinked/branch-unpinned` or `branch-mismatch` before any `gh` call. Contract, data model, research, quickstart (step 8), ADR-0003 and policy updated (T042).

## DEC-0007 — Proposal

- Source: R2 implementation review (engineering, high). `reuse()` builds the new body from the earlier pulls listing and submits the whole body with `gh pr edit --body-file -`. A human edit made between the listing and the edit is overwritten outside the Ballast section, against FR-007. GitHub's REST API offers no conditional (If-Match) update for a PR body, so the window cannot be closed completely.
- Classification: spec violation (FR-007) with a platform limit.
- Proposal: immediately before an edit, re-read that one PR (`gh api repos/{repo}/pulls/{n}`) and edit only when its body still equals the body the replacement was built from; otherwise record `reused/section-unmanaged`-style `reused/body-changed` and leave the PR alone until the next run. Document the remaining sub-second window in the policy. Alternative: never edit an existing body (drop section refresh), a product change.
- Not implemented: it adds an outcome reason and accepts a residual race, so it waits for human resolution.

## DEC-0007 — Resolution

- Accepted by the operator (2026-10-04). Before an edit the checkpoint re-reads the PR (`gh api repos/{repo}/pulls/{n}`); a body that differs from the listed one gives `reused/body-changed` and no edit. The sub-second window GitHub's API cannot close is documented in the data model (T042).

## DEC-0008 — Proposal

- Source: R2 implementation review (engineering, medium). `compare()` reads one page of at most 300 files. When those are all under `specs/<feature>/`, the result is `pending/diff-unclassified` even if a later file is outside it, so a meaningful change can stay pending (FR-003). The approved plan chose this cap with the remedy "open the PR by hand; Ballast will adopt it".
- Classification: spec ambiguity (approved limit vs FR-003).
- Proposal: paginate the compare's files (`gh api --paginate`, GitHub serves up to 3000) and stop at the first file outside the spec directory; keep `pending/diff-unclassified` only beyond GitHub's own 3000-file limit. Alternative: keep the 300 cap and state it in FR-003 as accepted.
- Not implemented: it changes an approved data source and the call budget, so it waits for human resolution.

## DEC-0008 — Resolution

- Accepted by the operator (2026-10-04). The compare is read with `--paginate --slurp` and `per_page=100`; `pending/diff-unclassified` remains only at GitHub's own 3000-file limit (T042).
- Superseded (2026-10-04): The R2 round-2 review showed pagination was wrong: GitHub's compare lists changed files only on its first page, at most 300; later pages list commits. Paginating could report `pending/no-meaningful-change` while an implementation file sat past the cap. Reverted to one response and the original rule: 300 or more listed files is never concluded (`pending/diff-unclassified`, remedy "open the PR by hand; Ballast will adopt it"). FR-003 holds for every diff GitHub can fully list. Provisional decision under the operator's standing authority for Epic #11 children; confirm at merge.

## DEC-0009 — Proposal

- Source: R2 implementation review (architecture, medium). The launcher starts `run.py` with `-I` (`launcher.py`, `COMMANDS`), not `-I -S` as the constitution requires of workflow tools, and `run.py` now holds the operator's GitHub credentials. `-I` already ignores `PYTHON*` variables, the user site directory and the script directory, so no checkout path is imported; only root-owned system site-packages load. `run.py` and everything it imports are standard-library-only.
- Classification: architecture issue (pre-existing; launcher trust model, R2).
- Proposal: change `COMMANDS["run"]` to `("-IS", "run.py")` and add a test that `run.py` starts with `sys.flags.no_site`. It changes what the launcher executes for every run, so it belongs in its own bugfix PR rather than #17.
- Not implemented: launcher change outside this feature's scope; waits for human resolution.

## DEC-0009 — Resolution

- Accepted by the operator (2026-10-04): fix in its own bugfix PR, not in #17. Merged as PR #31 (`run.py` and `tools/setup` start with `-I -S`).

## DEC-0010 — Proposal

- Source: R2 round-2 review (security, high, partial). The DEC-0006 pin read the upstream's name from `.git/config` at `ballast run start`; an earlier run's agent may already have written it, steering the checkpoint to another branch of the pinned repository.
- Classification: architecture issue (security boundary; R2).

## DEC-0010 — Resolution

- Provisional, under the operator's standing authority; confirm at merge): pin only the branch; the checkpoint requires the local branch and its published name to both equal it. An upstream under another name is refused as `blocked-unlinked/branch-mismatch` (narrows research R4, which followed a renamed upstream). Implemented in T043.
- Refined by the T038 live check (2026-10-04): a branch that matches the pin but tracks another name (a worktree branch created from `origin/main` tracks `main`) is `pending/not-published` with `git push -u <remote> <branch>`, not `branch-mismatch`; only a different local branch is `branch-mismatch`. Neither path calls `gh`.

## DEC-0011 — Proposal

- Source: R2 round-2 review (security, high if an agent-writable directory is on `PATH`). Program and `PATH` filtering rejected Git working trees only. Agents can also write `/tmp` and `$TMPDIR` (Codex `workspace-write`); a `gh` or `git` planted there and reachable through `PATH` would run with the operator's token variables.
- Classification: architecture issue (security boundary; R2).

## DEC-0011 — Resolution

- Provisional, under the operator's standing authority; confirm at merge): `ledger.agent_temp_roots()` (`/tmp`, `/var/tmp`, `/dev/shm`, `$TMPDIR`) are excluded like working trees when `draft_pr` resolves programs and builds the child `PATH`, and when the ledger resolves its own `git`. `ballast doctor` keeps its working-tree rule. Implemented in T043.

## DEC-0012 — Proposal

- Source: R2 round-3 review (`reviews/implementation-review-codex-3.md`). (a) The pin records the branch `HEAD` names at `ballast run start`; an earlier run's agent could have moved `HEAD`. (b) Program trust excludes working trees and temp roots only; another agent-writable directory on `PATH` would be trusted. (c) `XDG_STATE_HOME` under an agent-writable location would let an agent rewrite the pin. (d) A malformed compare response read as an empty file list, i.e. `no-meaningful-change`.
- Classification: (a)(b)(c) architecture issue (security boundary; R2); (d) implementation bug.

## DEC-0012 — Resolution

- Provisional, under the operator's standing authority for Epic #11 children; confirm at merge. (c) and (d) fixed in T044: a pin whose path resolves under the checkout or a temp root is neither written nor trusted (`blocked-unlinked/branch-unpinned`), and a compare without a `files` list is `failed-retryable/github-error`. (a) mitigated, residual accepted: `ballast run start` prints `Draft PR: branch pinned: <branch>` so the operator sees it before any agent runs; exploiting it needs an earlier compromised run, and its effect is limited to Draft PR metadata in the pinned repository (no code, no push, no merge). (b) accepted for supported environments, whose agent write authority is the checkout plus the temp roots (Codex `workspace-write`; Claude edits limited to the project). The launcher-wide boundary, including allowlisted `git` output options and the trust baseline's state directory, is tracked in #34.

