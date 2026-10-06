# Security review: 55-setup-trust (setup records the trust baseline)

- Reviewer: security reviewer, independent context
- Change: `git diff 641fa7f..HEAD` (ee50e93, 5201073, 3d0a087, c659760), branch `feat/55-setup-trust`, risk R2 (launcher trust model)
- Scope examined: `tools/spec_workflow/setup_trust.py` (all), `tools/spec_workflow/launcher.py` (`record_baseline`, `_provenance`, `baseline_source`, `operator_baseline`, `reviewed_repositories`, `add_reviewed`, `_trust`, `_review_repository`, `_status`), `tools/setup` (`main`, `prepare`, `settle`, `closing`, preparation's stale-baseline removal, recovery), `tools/spec_workflow/branch_sync.py` and `draft_pr.py` (shared Git environment), `tools/ballast` (doctor), `tools/init`; tests `tests/test_setup_trust.py` and the new classes in `tests/test_spec_workflow.py` (read for coverage, not run in full).
- Policies and artifacts read: `AGENTS.md`, `.specify/memory/constitution.md` (BL-INV-002, BL-INV-003, the rest), `docs/policies/security.md` (no `docs/policies/project/security.md` exists), ADR-0005, ADR-0015, the feature's `spec.md`, `research.md`, `data-model.md`, `contracts/*.md`, `decisions.md`, `README.md` setup section.

## What was checked

- The decision order in `_evaluate`: standard outside the checkout, tamper and in-progress markers, saved and unfinished runs, configs read once with `O_NOFOLLOW`/`O_NONBLOCK`/size cap and compared to the snapshot digest, installation record, pointer, `HEAD` blobs, reference. Every non-configuration input is compared from the single snapshot to the installation record, and the recorded baseline is that snapshot. Any later difference is refused by the unchanged launcher, so a race can only make a baseline stricter (a swap after the snapshot makes the launcher refuse). Exception: the `.git` pointer (SEC-002).
- Agent-writable `.git` of the checkout: only `rev-parse` and `remote get-url` run there, with `core.hooksPath` and `core.fsmonitor` neutralized, location and configuration variables dropped, replace refs and grafts off. Nothing from it selects the repository, branch or file (the scheme of `origin` is the only value read). Remotes, refs and `insteadOf` in the checkout are ignored by construction. I confirmed that the throwaway's `GIT_DIR`, `GIT_CEILING_DIRECTORIES` and `--template=` keep the checkout's configuration out of every network command.
- Command and argument injection: owner and name are `[A-Za-z0-9._-]` (no `/`, `..`), the branch must match `ledger.REF` (no leading `-`, `..`, `@{`, `:` or `*`) and is only used inside a refspec, commit IDs are 40 hex, all argv are lists, `--` precedes paths. No injection path found.
- Credentials and disclosure: Git output is parsed, never printed; stderr is only pattern-matched; skipped reasons are fixed phrases plus checkout-derived names that `say()` escapes through `printable()`; the doctor reads only `status --json` and maps `baseline_source` through a whitelist. Prompts, askpass and display variables are off; every network command is bounded (30 s, 30 s, 120 s). I checked that `subprocess.run` really returns at the timeout when a grandchild keeps the pipes open (POSIX): it did, in 1.0 s with a 6 s grandchild.
- Operator state: `trusted-source.json` and `reviewed-repositories.json` live in `state_base`, which `state_base()` already refuses inside the checkout or an agent temp directory, and which the agent sandbox mounts read-only (`autonomy.STEP_DIRECTORIES` redirects a step's own `XDG_STATE_HOME` to a tmpfs, so an agent running `ballast setup` or `trust` inside a step writes nothing real and has no real marker to bypass). Unreadable, malformed, unbound or foreign-schema provenance fails closed in `operator_baseline` and `reviewed_repositories`; `baseline_source` reads it as `trust`, which is display only (FR-013). The comparison never reads either file. Crash orderings of `record_baseline` (source first, baseline second) and of `_record`'s rollback leave either the old pair or a source unbound to its baseline, which fails closed.
- `add_reviewed` is serialized by an `flock` on a `O_NOFOLLOW` lock file and written atomically; a read concurrent with a write sees the old or the new file. `ballast trust` records the repository only when the re-read `ballast.toml` digest equals the trusted one.
- `ballast init` sets `records_trust = False`; `--check` and doctor never import or call `setup_trust` (also asserted by tests).

Experiment (scratch only, `XDG_STATE_HOME` under `~/.local/state/ballast-tests`, nothing in the repository or the real state directory): a subclass of `tests.test_setup_trust.TrustCase` in the scratchpad replaced `.ballast` and then `.specify` with a symlink to an outside copy with identical content and called `settle`. Both records a baseline (SEC-001).

## Review

```yaml
review: security
verdict: changes_required
findings:
  - id: SEC-001
    severity: medium
    invariant: BL-INV-002
    location: tools/setup:533 (main, "nothing changed" branch) and tools/setup:582 (prepare, recovered preparation); tools/spec_workflow/setup_trust.py:659 (snapshot) and :288 (_check_installation)
    description: >
      Demonstrated. Setup only runs `check_links(PARENTS)` on the paths that
      install (tools/setup:537, :599). The "nothing changed" branch and the
      recovered-preparation branch call `settle` without it, and `settle` itself
      does not look for a link in a protected parent. `launcher.digests`
      follows a symlinked base directory and records no entry for the link, so a
      `.ballast` or `.specify` replaced by a symlink to an outside directory with
      identical content equals the installation record. In the experiment,
      `settle` returned `recorded ... default branch main at <commit>` for both a
      symlinked `.ballast` and a symlinked `.specify`, and the launcher's
      `_refusal` then returned None. The baseline therefore covers bytes that
      live outside the checkout, in a place an agent with /tmp or any other
      writable path can change; the launcher's comparison catches a later edit
      (confirmed: "workflow inputs changed since trust"), but the time between
      its check and the execution of `.ballast/spec_workflow/run.py` through the
      link is unprotected, and no human saw the link, which is the review the
      old `ballast trust` step provided. A full `ballast setup` refuses this
      checkout ("is a symbolic link; setup never moves files through a link"), so
      the two paths disagree, and the existing test only covers a link to a leaf
      file (`test_a_linked_installed_file`).
    required_action: >
      Make eligibility refuse a link anywhere between the checkout root and a
      protected input (`.ballast`, `.ballast/spec_workflow`, `.specify`,
      `.specify/memory`, `.venv`, and every recorded entry's parents) inside
      `setup_trust._evaluate` itself, so no caller path can skip it, with the
      reason "a protected path is a link". Add regression tests for a symlinked
      `.ballast` and `.specify` through the "nothing changed" path and the
      recovered-preparation path, asserting no baseline and no provenance.

  - id: SEC-002
    severity: low
    invariant: BL-INV-002
    location: tools/spec_workflow/setup_trust.py:305-330 (_check_pointer), :288-302 (_check_installation skips ".git")
    description: >
      Demonstrated by reading, not exploited. The linked-worktree `.git` pointer
      is validated from a fresh read, while the baseline records the digest of the
      earlier snapshot; unlike the two configuration files (compared to the
      snapshot digest at line 677, CHANGED), the pointer bytes are never compared
      with `snapshot[".git"]`. A process that can write the checkout while setup
      runs can hold a forged pointer P_bad at snapshot time, swap in a valid
      P_good for the read in `_check_pointer`, and restore P_bad before the final
      re-snapshot; the baseline then binds P_bad although only P_good was checked.
      The launcher protects the pointer because a forged gitdir makes later
      operator-run Git execute configuration from an agent-written repository.
      The window is narrow (milliseconds between the snapshot and the pointer read)
      and needs a concurrent writer in an unsandboxed session, hence low.
    required_action: >
      Compare the bytes `_check_pointer` read with `snapshot[".git"]`
      (`hashlib.sha256`, as for the configurations), and fail with CHANGED on a
      difference. Add a test that changes the pointer between the snapshot and the
      pointer check.

  - id: SEC-003
    severity: low
    invariant: BL-INV-002
    location: tools/spec_workflow/setup_trust.py:57 (GIT_FLOOR), :392-396 (_Checkout.env), :421-425
    description: >
      Unresolved assumption, not demonstrated. Local plumbing in the
      agent-writable checkout relies on `GIT_NO_LAZY_FETCH=1` to stop a promisor
      configuration in `.git/config` from making `rev-parse HEAD:<path>` fetch
      from a URL the checkout names (operator credentials, attacker-chosen host).
      The floor is Git 2.41. I believe `GIT_NO_LAZY_FETCH` (and `--no-lazy-fetch`)
      arrived in 2.44, so a 2.41 to 2.43 Git (Ubuntu 24.04 ships 2.43) passes the
      floor and ignores the variable; I did not verify the version. The
      precondition is a write to `.git/config` plus a missing HEAD object, which
      the sandbox keeps read-only for agent steps, so this is residual and the
      same pattern pre-exists in branch_sync, but this change adds new local
      commands in the checkout on every setup and preparation.
    required_action: >
      Verify the introducing version. If it is later than 2.41, raise
      `GIT_FLOOR` for setup_trust, or pass `-c extensions.partialClone=` and
      `-c remote.origin.promisor=false` for the checkout commands, and say which
      in the contract; otherwise record the verification here.

  - id: SEC-004
    severity: info
    invariant: BL-INV-002
    location: docs/adr/0015-setup-recorded-trust-baseline.md (Decision 9, Consequences); launcher.py add_reviewed
    description: >
      Unresolved assumption, accepted by the operator (D-01 to D-03) but not
      stated. "Reviewed" for the default-branch alternative means "equal to what
      is on the default branch of a repository ever passed to `ballast trust`";
      the reviewed record holds identities only and never expires. Any later
      change to the default branch of that repository (an unreviewed merge, a
      compromised maintainer account, a repository transferred to another owner
      under the same name) is trusted on every future clone without a human,
      including a widened `[agents.permissions]` that was merged. The design is
      sound given a protected default branch, but the ADR and README do not say
      the safety depends on it.
    required_action: >
      State in ADR-0015 and the README section that the guarantee holds only if
      the default branch is protected and its changes reviewed, and that
      `reviewed-repositories.json` entries should be removed when a repository
      changes hands. No code change required.

  - id: SEC-005
    severity: info
    invariant: BL-INV-002
    location: tools/spec_workflow/setup_trust.py:432-443 (_check_committed), :472-478 (origin scheme)
    description: >
      FR-020 says nothing read to decide eligibility may come from an agent-
      writable file unless changing it makes the checkout ineligible. The
      "committed and unchanged from HEAD" check reads `.git` of the checkout
      (HEAD, objects, config), which an agent can forge, and `origin`'s scheme
      selects HTTPS or SSH (the contract lists the latter; both reach github.com
      for the pinned repository only). Neither affects the invariant, because
      condition 9 compares the bytes read to the operator baseline or to a live
      default-branch observation that uses none of the checkout's Git state; the
      committed check is hygiene, not a boundary. Related, also by design: the
      standard-outside-checkout test ignores agent temp roots, so a standard
      under /tmp would pass it.
    required_action: >
      Reword FR-020/AC and the contract to call the committed check a consistency
      check, not a security condition, and optionally reject a standard under
      `ledger.agent_temp_roots()` as the pointer check already does.
```

## Resolution

Resolved by the implementer after the review; each fix has a regression test in `tests/test_setup_trust.py` that fails when the fix is removed (mutation-checked).

- SEC-001 (medium): fixed. `setup_trust._check_parents` refuses a link in any directory above a protected input, on every path that reaches `settle` (the "nothing changed" and recovered paths included). Tests: `LocalIneligibleTests.test_a_linked_protected_directory_is_not_recorded`, `test_setup_says_so_for_a_linked_directory`.
- SEC-002 (low): fixed. `_check_pointer` requires the bytes it reads to hash to the snapshot's `.git` digest. Test: `WorktreePointerTests.test_a_pointer_swapped_after_the_snapshot`.
- SEC-003 (low): fixed without relying on the Git version. Every local Git command now carries `-c protocol.allow=never`, so a promisor remote named by the checkout's agent-writable configuration can never be contacted, with or without `GIT_NO_LAZY_FETCH` (Git 2.44 and later). The two network commands do not carry it. Test: `ObservationTests.test_only_the_documented_commands_run`.
- SEC-004 (info): documented. ADR-0015 "Residual risks", README and `decisions.md` DEC-0008 say what "reviewed" means, how to drop a repository from the record, and that binding a repository to one project is a spec change for the human.
- SEC-005 (info): fixed and documented. A standard under an agent temp directory is refused like one inside the checkout (`LocalIneligibleTests.test_a_standard_in_a_temp_directory`); ADR-0015 says the `HEAD` check and the `origin` scheme are early refusals, not the boundary.

Verdict after resolution: approved, with DEC-0008 and the two agent inferences left to the merge reviewer.
