# Research: Setup trusts a checkout it just installed

Phase 0 decisions for [plan.md](plan.md). Every decision here is agent-provisional (Autonomous run `38380ec3`); merging the PR is the only human approval (BL-INV-006). D-01, D-02 and D-03 are the operator's answers recorded in [discovery.md](discovery.md); this file only decides how to implement them inside the boundary [spec.md](spec.md) sets.

No NEEDS CLARIFICATION remained in the Technical Context. R1 to R19 below record the design choices and the alternatives rejected.

## R1. Where the eligibility check and the recording live

- **Decision**: A new module `tools/spec_workflow/setup_trust.py` in the standard holds the eligibility conditions, the observation of the pinned repository's default branch and the decision to record. `tools/setup` imports it lazily, only after an installation is in place, from its own `STANDARD` directory (the pinned, fetched copy). Writing the baseline, its provenance and the reviewed-repositories record belongs to `tools/spec_workflow/launcher.py`, which already owns operator state, the digest format and `trusted.json`: a new `record_baseline(root, state, inputs, source)` is called by both the launcher's `_trust` and `setup_trust`.
- **Rationale**: The launcher stays the single owner of the trust baseline and its comparison (ADR-0002, FR-015); setup only decides whether to call it. A separate module keeps `tools/setup --check`, which doctor runs as a read-only probe, from importing the Git and run-state helpers. The module imports `launcher`, `ledger` (program resolution outside working trees) and `autonomy` (`GIT_HARDENING`); all are standard-library-only files of the same pinned version.
- **Alternatives considered**: Logic inside `tools/setup`: grows an already 1,760-line file and mixes trust with installation. Inside `launcher.py`: the launcher would gain network and Git transport it does not have today and would have to be loaded with them by every `status --json` probe. Importing `branch_sync`: drags `draft_pr`, `demo` and `packet` into setup for one URL rule.

## R2. When setup and preparation evaluate eligibility

- **Decision**: Only while the command still holds the exclusive checkout lock, after the installation is complete and no journal is left: after `attempt()` commits and `finish()` removes the journal, after a "nothing changed" verdict in `ballast setup`, and after `recover()` finished a committed preparation. Never during staging or switching, never in `--check`, and never in the "nothing to prepare" path where another command holds or finished the preparation.
- **Rationale**: The lock keeps `ballast run`, `ledger`, `intake`, `trust` and `discard-runs` out until the decision is written (they take the lock shared), so the launcher never sees a half-written baseline. An interrupted attempt never records, because recording happens after the journal is gone (spec edge case). Only the command that installed records (spec edge case: two preparations).
- **Alternatives considered**: Observing the default branch before taking the lock, to hold the lock for less time: the observation and the recording would no longer be one invocation's view under one lock; the network step is bounded instead (R9).

## R3. One snapshot, checked once, written once

- **Decision**: The check starts from one `launcher.trusted_inputs(root)` snapshot. The bytes of `ballast.toml` and `.specify/memory/constitution.md` are read once, through `O_NOFOLLOW` as regular files of at most 256 KiB (the launcher's `read_config` rule), and must hash to the snapshot's digest for that path; every later condition uses these bytes, never a second read. The baseline written is that snapshot. After writing, setup takes a second snapshot; if it differs, it removes the baseline and provenance it just wrote and reports the checkout ineligible ("protected inputs changed while setup checked them").
- **Rationale**: The lock excludes Ballast commands but not an unrelated process writing files. Snapshot-first means the recorded digests are exactly the bytes that were judged reviewed; the re-check closes the window between the check and the write.
- **Alternatives considered**: Reading files again for each condition: a change between reads could pair a reviewed `ballast.toml` check with an unreviewed recorded digest.

## R4. "Exactly what setup wrote" (FR-002)

- **Decision**: Each snapshot entry is classified:
  - `ballast.toml` and `.specify/memory/constitution.md`: the reviewed-configuration conditions (R5 to R8).
  - `.git` (a linked worktree's pointer): R10.
  - Every other entry must appear in the valid, current installation record (`installation.json` read by `launcher.read_record`, fingerprint equal to the stamp and to this setup's fingerprint) with the same digest.
  - Conversely, every record file under a protected base (`.ballast/spec_workflow`, `.specify`) that the launcher does not skip must be in the snapshot with the same digest.
  Any extra, missing or differing entry makes the checkout ineligible and names the first such path.
- **Consequences, stated in the docs**: a `.venv` in the checkout, committed project files under `.specify/` other than the constitution (for example `.specify/assessments/`), and a leftover `.specify/extensions/.backup` are protected inputs setup did not write, so such a checkout needs `ballast trust`. Fresh clones and new worktrees normally have none of them.
- **Rationale**: This is FR-002 read literally; widening it to other committed files would be a product change the spec does not make.
- **Alternatives considered**: Treating every committed protected file like the constitution (compare against the default branch): broader convenience, but not in the approved spec; left for a later issue.

## R5. Committed and unchanged from `HEAD` (FR-003, first half)

- **Decision**: For each of the two configuration files, setup computes the Git blob ID of the snapshot bytes in the checkout's object format (`rev-parse --show-object-format`, `sha1` or `sha256`; anything else is ineligible) in Python, and compares it with `git rev-parse --verify --quiet HEAD:<path>` run as local plumbing in the checkout: Git resolved outside every working tree and temp root, `autonomy.GIT_HARDENING`, `-c core.commitGraph=false`, `GIT_NO_REPLACE_OBJECTS=1`, `GIT_GRAFT_FILE=/dev/null`, `GIT_NO_LAZY_FETCH=1`, `GIT_TERMINAL_PROMPT=0`, the Git location variables and injected configuration removed (ADR-0005's environment), stdin closed. A file absent both in the working tree and at `HEAD` is unchanged; absent on one side only is a change. No `HEAD` (unborn branch) is ineligible.
- **Rationale**: Blob equality is content equality and needs no index or filter. `HEAD` lives in agent-writable `.git`, but a forged `HEAD` cannot create eligibility on its own: the same bytes must also equal a reviewed reference (R6). The check exists to reject uncommitted edits early and with a precise message (AC-010, D-06).
- **Alternatives considered**: `git diff --quiet HEAD -- <path>`: runs diff machinery and attribute lookups the checkout configures; `git status`: may refresh the index and read filters.

## R6. Which reviewed reference, in which order

- **Decision**: After R4 and R5, setup tries the previous operator-recorded baseline (R7) first; it is local and works offline. Only when it does not match does setup check the reviewed-repositories record (R8) and then observe the pinned repository's default branch (R9). The first match decides and is named in setup's output and in the provenance record.
- **Rationale**: Every local refusal happens before any network access, so an ineligible checkout costs no request and an offline re-setup at an unchanged configuration still records. The default branch is observed only for a repository the operator already reviewed, so nothing is fetched on the operator's credentials for a repository named by an unreviewed `ballast.toml`.
- **Alternatives considered**: Default branch first: needs the network in the common re-setup case and asks a possibly repointed repository.

## R7. The previous operator-recorded baseline

- **Decision**: The checkout's current `trusted.json` counts as operator-recorded when it parses as a map of path to digest and either no provenance record exists (every baseline written before this feature was written by `ballast trust`), or the provenance record is readable, names `trust` and is bound to that `trusted.json` (R12). A provenance record naming `setup`, or one that is unreadable or bound to another baseline, makes it not operator-recorded for eligibility. The two configuration files match when the snapshot's SHA-256 digest for each path equals the baseline's entry for that path, an absent entry matching only an absent file.
- **Rationale**: A setup-recorded baseline never serves as a reviewed reference, so the chain of setup recordings always ends at an operator review or the default branch. Reading an unbound or unreadable provenance as `trust` is right for display (FR-013) but would fail open here, so eligibility treats it as not operator-recorded (fail closed). A legacy baseline with no provenance can only have come from `ballast trust`.
- **Preparation**: preparation removes a baseline left at a reused path before it installs (ADR-0011, AC-008), so for a new worktree this alternative never applies; only the default branch can make it eligible. No other checkout's baseline is ever opened (FR-010).
- **Alternatives considered**: Requiring a provenance record naming `trust`: every existing project would lose this alternative until its next `ballast trust`.

## R8. The record of reviewed repositories (FR-005, PD-0004)

- **Decision**: One machine-wide operator-state file, `$XDG_STATE_HOME/ballast/reviewed-repositories.json`, beside the per-checkout directories, located through the same `state_dir` validation (refused when it resolves into the checkout or a temp root). It holds `{"schema": 1, "repositories": ["owner/name", ...]}`, case-folded, sorted, unique. Only the launcher's `_trust` adds to it: after writing the baseline it adds the `[github] repository` named in the trusted `ballast.toml` snapshot, when that value is a valid `OWNER/NAME` (the same rule as `draft_pr._pinned_repository`); otherwise it adds nothing. Writes are read-modify-write under an `flock` on `reviewed-repositories.lock` and an atomic replace. Setup and preparation only read it; an unreadable or malformed file is treated as empty.
- **Rationale**: Nothing in a checkout can tell the reviewed repository from a repointed one whose default branch carries the same changed file (AC-016). The operator's own `ballast trust` of a `ballast.toml` naming a repository is the only local evidence that a human accepted that repository. Identities only, no digests, so no baseline is inherited (FR-010).
- **Migration**: the record starts empty. Baselines written before this feature do not populate it, because `trusted.json` holds digests only. After upgrading, each project needs one `ballast trust` on the machine; the docs say so.
- **Alternatives considered**: Accepting whatever repository `ballast.toml` names: breaks FR-005. Per-checkout records: a fresh clone or new worktree would never have one, defeating SC-001. Storing the repository in `trusted.json`: changes the format the comparison reads (D-05, D-07).

## R9. Observing the pinned repository's default branch (FR-004)

- **Decision**:
  - **Repository and URL**: `OWNER/NAME` from the snapshot bytes of `ballast.toml` `[github] repository` (R3), validated as in R8. The URL follows ADR-0005's rule, shared by moving `branch_sync._url` into `setup_trust.repository_url` and having `branch_sync` call it: `https://github.com/OWNER/NAME.git` when the checkout's `origin` URL starts with `https://`, otherwise `ssh://git@github.com/OWNER/NAME.git`. Only the scheme is read from `origin`; the host, owner and name never are.
  - **Git**: resolved outside every working tree and temp root (`ledger.resolve_program`), version 2.41 or later, as ADR-0005.
  - **Throwaway repository**: `git init --bare --template= --object-format=sha1` in a fresh directory under the operator state directory (`<state>/setup-trust/<random>/`), with its **own** object store, deleted afterwards. Unlike branch synchronization, nothing is merged or pushed, so the checkout's agent-writable object store is never shared or consulted.
  - **Commands**, only these, run in the throwaway with `autonomy.GIT_HARDENING`, `-c maintenance.auto=false -c gc.auto=0 -c core.commitGraph=false`: `ls-remote --symref URL HEAD` (30 s) to learn the default branch and its commit; `fetch --depth=1 --no-tags --no-write-fetch-head --filter=blob:none reviewed +refs/heads/<default>:refs/reviewed/default` (120 s), where the remote `reviewed` exists only as command-line configuration (`-c remote.reviewed.url=URL -c remote.reviewed.promisor=true -c remote.reviewed.partialclonefilter=blob:none`), so Git accepts the filter, a server without filter support sends the full tip instead, and nothing is written to any configuration file; a unit test pins this behavior on the floor Git version; `rev-parse --verify refs/reviewed/default^{commit}`; `ls-tree -z <commit> -- ballast.toml .specify/memory/constitution.md`. Trees suffice: blob IDs are compared, no blob is read.
  - **Environment**: ADR-0005's throwaway environment: Git location variables and injected configuration removed, `PATH` limited to entries outside working trees and temp roots, `GIT_TERMINAL_PROMPT=0`, `GIT_ASKPASS` empty, `SSH_ASKPASS` and display variables removed, `SSH_ASKPASS_REQUIRE=never`, `GIT_NO_LAZY_FETCH=1`, `GIT_NO_REPLACE_OBJECTS=1`, stdin closed, network commands in a new session. The operator's global and system Git configuration and credentials stay in effect: that is the operator's Git authority.
  - **Comparison**: the default branch matches when, for both paths, the blob ID listed at the fetched commit equals the SHA-1 blob ID of the snapshot bytes, an absent path matching only an absent file. The commit observed is the fetched one; a branch that moved between `ls-remote` and `fetch` is simply observed later in the same invocation (spec edge case).
  - **Failure**: any non-zero exit, timeout, missing symref, invalid branch name or commit, or a fetch that does not yield the commit is "unobservable" (AC-014) with a short cause (`offline or unreachable`, `no access with your Git credentials`, `no default branch`, `timed out`). Git's own output is never printed.
- **Rationale**: This implements an agent inference that only narrows the operator's D-02 answer and is listed for merge review (discovery `## Inferred`): observe the default branch live, from the pinned repository only, through the trusted path of ADR-0005, never through a local remote-tracking ref, `origin`, `insteadOf` or any setting the checkout configures (AC-015). A depth-1, blob-less fetch keeps the download to one commit and its trees.
- **Alternatives considered**: The local `refs/remotes/origin/<default>` ref (D-02 option B as first worded): agent-writable, so it would let an agent choose what counts as reviewed. The GitHub contents API through `gh`: a second authority and transport for the same fact, and ADR-0005's trusted path is Git. Sharing the checkout's object store as branch synchronization does: unnecessary here, and it would let objects an agent planted answer the lookup. A full depth-1 fetch: downloads every blob at the tip of a large repository on each setup.

## R10. A linked worktree's `.git` pointer (FR-006)

- **Decision**: When `.git` is a file, it is read without following links (at most 4 KiB) and must be exactly `gitdir: <absolute path P>`; P must resolve to `C/worktrees/<name>` where `C` is the directory named by `P/commondir` (resolved relative to P); `P/gitdir` must name this checkout's `.git`; and `C` must lie outside this checkout and every agent temp root. A `.git` that is a link, or any other shape, is ineligible. A primary checkout's `.git` directory is not a protected input and is not checked (spec edge case).
- **Rationale**: The pointer is the one protected input setup cannot write. The back-link and the location checks reject a pointer redirected to a repository an agent built in the checkout or a temp directory, the attack the launcher's `input_bases` docstring names. The repository's `worktrees/` area is read-only to confined agents.
- **Alternatives considered**: Asking `git worktree list` in the checkout: it runs Git through the pointer being validated.

## R11. No agent trace (FR-007, D-04)

- **Decision**: The checkout is ineligible when any of these exist: `BALLAST_TAMPERED` in the checkout; the in-progress marker in operator state; any entry under `.specify/workflows/runs` or `.specify/workflow-state` (an empty directory is not run state); or a run directory under `<state>/runs/` whose `run.json` is unreadable or has status `active` or `stopped`. `completed`, `published` and `continued` runs are finished.
- **Rationale**: The markers and operator-state run records are written by trusted code only and are the authority (AC-018 to AC-021). Run state inside the checkout only adds refusals: removing it cannot make an unreviewed input eligible, because every other condition still holds the inputs to an installation record and a reviewed reference (FR-020).
- **Alternatives considered**: Refusing on the markers only, as `ballast trust` does (D-04 option B): not chosen in D-04.

## R12. Provenance: where, bound how, written when (FR-012, FR-013, D-05)

- **Decision**: `<state>/trusted-source.json`: `{"schema": 1, "source": "setup" | "trust", "baseline": "sha256:<hex of the exact trusted.json bytes>", "recorded": "<UTC ISO-8601>", "reference": {...}}`, where `reference` is `{"kind": "default-branch", "repository": "owner/name", "branch": "...", "commit": "..."}` or `{"kind": "operator-baseline"}` for setup, and absent for `trust`. `record_baseline` serializes `trusted.json` exactly as `_trust` does today (`json.dumps(inputs, indent=1)`), writes the provenance file first, then `trusted.json`, each atomically (temporary file, `fsync`, `rename`, directory `fsync`, mode 0600, `O_NOFOLLOW`). The launcher reports `baseline_source` as `null` without a readable `trusted.json`, `setup` only when the provenance record is readable, names `setup` and is bound, and `trust` in every other case.
- **Rationale**: The comparison keeps reading the unchanged flat map (D-07). Writing provenance first means a crash between the two writes leaves a record bound to a baseline that was never written, which reads as `trust` for the old baseline, the correct source. The provenance can never make a checkout trusted or untrusted (AC-024): the launcher's refusal does not read it.
- **Alternatives considered**: A source field inside `trusted.json` (D-05 option B): changes the comparison reader. Writing `trusted.json` first: a crash would show a setup baseline as bound to nothing and read as `trust`, misreporting it.

## R13. Doctor and cross-version behavior (FR-014)

- **Decision**: `status --json` gains one key, `"baseline_source"`. Doctor's `trust` check keeps its classification from `installed` and `refusal`, and appends the source to its detail when the key is present: "the launcher accepts this checkout; baseline recorded by `ballast setup`" or "... by `ballast trust`", and for a refusal "launcher will refuse: ...; the current baseline was recorded by ...". A launcher without the key (a project pinned to an older version) gives today's text. `tools/cli.toml` gains no declaration: the key is optional data, and an older CLI ignores it.
- **Rationale**: ADR-0002: doctor recomputes nothing and reads only the launcher's JSON. Optional data needs no version negotiation.

## R14. What setup says, and its exit status (FR-008, FR-016)

- **Decision**: The installation's own lines and exit status are unchanged in every case. Then exactly one of:
  - Recorded: `Recorded the trust baseline for N protected inputs: ballast.toml and the constitution match <reference>.` where `<reference>` is `OWNER/NAME's default branch BRANCH at <12-hex commit>` or `the baseline you recorded with ballast trust`; then `The next ballast run, ledger or intake needs no ballast trust.`
  - Kept: `The trust baseline you recorded with ballast trust still matches; left unchanged.` (FR-011), or `The trust baseline setup recorded still matches; left unchanged.`
  - Not recorded: `No trust baseline recorded: <reason>.` followed by today's `Review the changed protected inputs, then run ballast trust before the next workflow run.` (preparation: today's worktree line).
  Reasons are fixed phrases naming the condition, with checkout-derived values passed through `printable()`. Setup still refuses outright, as today, on an in-progress marker and on an operator state directory agents can write.
- **Rationale**: SC-002 needs the reason and `ballast trust` in every ineligible case; existing tests that look for today's success and trust lines keep passing (AC-023, SC-003).

## R15. Preparation specifics (FR-009, FR-010, AC-006 to AC-009)

- **Decision**: Preparation keeps removing a baseline left at a reused path before it installs (ADR-0011), and also removes a provenance record left there. It then evaluates eligibility like setup, from the worktree's own snapshot and the installation record it just wrote (copied from a verified candidate). It never opens another checkout's `trusted.json`, provenance or run records; it reads only the machine-wide reviewed-repositories record. A preparation that finds another command already prepared the worktree records nothing.
- **Rationale**: D-03 option A with ADR-0011's stale-baseline rule kept (AC-008, AC-009).

## R16. Only a standard outside the checkout records

- **Decision**: Setup records nothing when its own `STANDARD` directory resolves inside the checkout being set up ("setup runs from this checkout, which agents can write").
- **Rationale**: The trust decision must come from code an agent cannot write (BL-INV-002, FR-020). `ballast setup` always runs the pinned copy in `$XDG_DATA_HOME/ballast/standard/<ref>/`; running `tools/setup` from inside the project (for example while developing the standard with `BALLAST_STANDARD_DIR` pointing at the same checkout) keeps today's behavior.

## R17. Governing documents (FR-017 to FR-019)

- **Decision**:
  - New `docs/adr/0014-setup-recorded-trust-baseline.md`, proposed until merge: the conditions R2 to R16, the observation path (R9) and the reviewed-repositories record (R8). It supersedes ADR-0007's clause "never records trust" and ADR-0011's "Preparation never reads any `trusted.json`" (for the checkout's own baseline only; other checkouts' baselines stay unread) and rejected-alternative wording where they conflict; ADR-0007 and ADR-0011 get a one-line "Superseded in part by ADR-0014" note beside those clauses, nothing else.
  - Constitution 1.2.0: BL-INV-002 reads "The launcher refuses until the operator trusts the current inputs, or the operator's `ballast setup` or worktree preparation recorded them under the conditions of ADR-0014, and fails closed ..."; the amendment history records the reason (Issue #55, one human command per checkout for inputs the operator's own setup wrote from reviewed configuration) and the compatibility impact (none for earlier pins; projects keep their own constitution). MINOR, because the refusal and its fail-closed checks are unchanged and only who may record the baseline widens under stated conditions.
  - Roadmap phase 2 items 3 and 7: "setup cannot silently trust itself" becomes "setup records a baseline only under ADR-0014's conditions and says so".
  - `specs/TECHNICAL-SPEC.md` §9.1: one "Status (#55)" paragraph like the others.
  - `README.md` (Worktrees, Running the workflow, pin-update and rollback blocks) and `templates/policies/spec-kit-workflow.md` (the trust section): when setup and preparation record, the network and Git authority needed, when `ballast trust` is still needed (including once per project per machine, and the R4 consequences), and how doctor shows the source.
  - `templates/init/constitution.md` and `templates/init/agents-section.md` stay as they are: "only the operator runs `ballast trust`; an agent never does" remains true.
- **Rationale**: AGENTS.md requires a new ADR for an accepted architecture change and the constitution's governance requires a recorded reason for weakening an invariant.

## R18. Test strategy

- **Decision**: A local bare repository stands in for GitHub through one seam, `setup_trust.repository_url`, patched in-process as `tests/test_branch_sync.py` patches `branch_sync._url`; every other test keeps the network unreachable and asserts no observation is attempted when a local condition fails. New tests live in `tests/test_setup_trust.py` (eligibility matrix, observation, recording, provenance, reviewed record) and extend `tests/test_setup.py` (setup and preparation flows), `tests/test_spec_workflow.py` (launcher `trust`, `status --json`) and `tests/test_doctor.py`. Existing trust and refusal tests are not edited (AC-023). The existing `ProjectCase` fixtures hold run state and no `[github] repository`, so they stay ineligible and keep today's output.
- **Rationale**: Testing policy: every AC needs evidence, including refusal and failure paths; no test touches github.com.

## R19. Compatibility

- **Decision**: Projects pinned to earlier versions see no change: their setup and launcher are their own. A baseline written before this feature has no provenance and reads as `trust`. The reviewed-repositories record is ignored by older versions. An older global CLI ignores `baseline_source`. A project that upgrades needs one `ballast trust` per machine before fresh clones and worktrees are trusted by setup.
