# Independent security review 2: 55-setup-trust (setup records the trust baseline)

- Reviewer: independent security reviewer, a different model from the author and from the first security review, no shared context with either.
- Change: `git diff origin/main...HEAD` on `feat/55-setup-trust` at `cbde7e2`, risk R2 (the launcher's trust model; who may record a baseline).
- Read: `CLAUDE.md`, `.agents/skills/ballast-security-review/SKILL.md`, `docs/policies/security.md` (no project override exists), the constitution (BL-INV-002 to BL-INV-004, BL-INV-006), `constitution-amendment.md`, ADR-0014 (and ADR-0005, ADR-0011 for the parts it supersedes), `discovery.md` D-01 to D-07 with the D-02 refinement, `spec.md`, `plan.md`, `contracts/setup-trust.md`, `contracts/launcher-and-doctor.md`, `decisions.md` DEC-0001 to DEC-0008, `reviews/security.md` (and its resolution), `README.md` "Setup records the baseline".
- Code: `tools/spec_workflow/setup_trust.py` (all), `launcher.py` (`state_base`, `digests`, `input_bases`, `trusted_inputs`, `write_atomic`, `record_baseline`, `_provenance`, `baseline_source`, `operator_baseline`, `split_repository`, `reviewed_repositories`, `add_reviewed`, `_trust`, `_review_repository`, `_status`, and `_trust_refusal`, which the diff does not touch), `tools/setup` (`main`, `prepare`, `settle`, `settling`, `hold`, `fill_from_candidates`, `candidates`, `copy_candidate`), `tools/init`, `tools/ballast` doctor `_trust`/`_recorder`, `branch_sync.py` and `draft_pr.py` (now delegating to the shared Git rules), `autonomy.py` (`GIT_HARDENING`, `confined_argv`, `_binds_for_worktree`, `_git_binds`, `STEP_DIRECTORIES`) to establish what a confined step can write.
- Run: `uv run --no-project --isolated --python 3.13 --with pyyaml python -m unittest tests.test_setup_trust tests.test_setup tests.test_spec_workflow`: `Ran 363 tests in 686.852s`, `OK`.
- Experiments: a scratch `unittest` subclass of `tests.test_setup_trust.TrustCase` in the session scratchpad (`review55/exp.py`), state under the tests' own `XDG_STATE_HOME`, nothing written to the repository, no `ballast trust` run in the worktree. Results E1 to E5 are cited below.

## Threat model used

An agent that writes the checkout (working tree, a branch's commits), the agent-writable parts of `.git`, a sibling worktree, `/tmp`, or any path a confined step can reach, and then waits for the operator's `ballast setup`, or for the orchestrator's first `ballast run` in a new worktree, to record a baseline for inputs no human reviewed. A chat-mode agent with the operator's authority is out of scope (it can run `ballast trust` itself). The confined-step sandbox (`confined_argv`) was read to fix what "agent-writable" means: `/` read-only, the worktree writable minus `ballast.toml`, `.ballast`, `.specify` (except `feature.json` and two caches), `.venv` and the `.git` pointer or directory and its admin and common dirs, a private tmpfs on `/tmp`, `/run` and `XDG_RUNTIME_DIR`, throwaway overlays on the agent homes and `~/.cache`, a step-private `XDG_STATE_HOME` under `/run`. So a confined step writes nothing that survives it outside the checkout, and cannot change a protected input or `.git` at all; agent-authored protected inputs reach a checkout only through commits on a branch and through whatever a later `git worktree add` or clone materializes.

## What was traced

- **Where the decisions live.** `trusted.json`, `trusted-source.json`, the installation record, the checkout lock and the in-progress marker are under `state_dir(root)`; `reviewed-repositories.json` and its lock under `state_base(root)`. `state_base` refuses an `XDG_STATE_HOME` inside the checkout or an agent temp root; a confined step sees the real state read-only and gets its own empty one. Nothing a step can write is read to decide eligibility except the checkout's bytes, and every checkout byte read is either part of the recorded snapshot (so a change is refused by the unchanged launcher) or compared against something outside the checkout (installation record, operator baseline, live default branch). The `HEAD` check and the `origin` scheme are the two exceptions; both were confirmed to be refusals only, not authority (a forged `HEAD` cannot make bytes equal a reviewed reference; `origin` chooses HTTPS or SSH to `github.com/<owner>/<name>` and nothing else).
- **Order and TOCTOU.** Snapshot once (`launcher.trusted_inputs`), then configs read with `O_NOFOLLOW` and a size cap and compared to the snapshot digest (`CHANGED`), installation record compared from the snapshot, pointer bytes compared to the snapshot (`CHANGED`, first review's SEC-002), `HEAD` compared to the bytes read, observation compares the bytes read, `record_baseline` writes the snapshot, re-snapshot must equal it or the previous pair is restored. Any write between the snapshot and the record produces a baseline the launcher refuses; any write after it is the launcher's pre-existing window. A link in any parent directory of a protected input is refused on every path that reaches `settle` (first review's SEC-001; `_check_parents`). `rglob` in 3.13 does not follow directory links, so a linked `.specify/memory` records as `link:` and differs from the record.
- **Comparison by blob ID and `.gitattributes`.** All three comparisons are of raw bytes: the working file's bytes hashed as a Git blob against `HEAD:<path>`, the same against the remote `ls-tree` blob, and sha256 of the same bytes into the baseline. Filters, `eol`, `autocrlf` and `export-*` attributes never apply to any of them, so an attribute can only make the checkout ineligible (working bytes differing from the committed blob), never eligible. A link or submodule entry on the remote is not a blob (`BLOB_MODES`); a link in the working tree fails `_read_regular`.
- **Live observation.** Pinned `owner/name` are `[A-Za-z0-9._-]{1,100}` minus `.`/`..` and sit in URL position; the branch must match `ledger.REF` and is used only inside a refspec; commits are 40 hex. The throwaway runs with `GIT_DIR` set, `--template=`, `GIT_CEILING_DIRECTORIES`, `cwd` in operator state, so the checkout's `.git/config` is never read: E3 (an `url.<evil>.insteadOf=<pinned>` in the checkout's `.git/config`, evil carrying the widened `ballast.toml` the checkout commits) returned `skipped ... differs from example/project's default branch`. Checkout-local commands carry `protocol.allow=never` so a promisor remote named by `.git/config` cannot be contacted (first review's SEC-003). Lazy fetch in the throwaway is blocked by `GIT_NO_LAZY_FETCH` and, for the non-network commands, by `protocol.allow=never`, so a missing tree reads as "unreadable", not as a second fetch. Prompts, askpass and displays are off; three bounded commands. Only a reviewed repository is contacted, so a hostile remote serving crafted objects needs a hostile reviewed repository (SEC2-001, SEC2-005).
- **Reviewed record.** Written only by `ballast trust` through `add_reviewed` under `flock`, atomic, identities only; read fails closed on any malformation (tests cover four shapes). `_review_repository` re-reads `ballast.toml` and records the repository only when its digest equals the trusted one.
- **Pointer.** `_check_pointer` is structural (admin dir is `<common>/worktrees/<name>`, back-link equals `root/.git`, common dir outside the checkout and every agent temp root). It cannot tell "this repository" from "any repository", but a confined step can write no common dir that survives outside the checkout, `/tmp` and `/run`, and cannot write the pointer at all (`--ro-bind`), so the check holds within the sandbox's guarantee (SEC2-006 asks for that sentence in the ADR).
- **Previous own baseline (DEC-0004).** `held` and `earlier` are read only when `mode == "setup"`; a preparation removes a baseline left at a reused path in `fill_from_candidates` before installing and reads none afterwards, on the first-run and the recovered path.
- **Run state and markers.** `BALLAST_TAMPERED` and the in-progress marker before anything else (DEC-0001); saved run state in the checkout and any unfinished or unreadable operator-state run refuse. A confined step always holds the in-progress marker in real operator state, and its own `ballast setup` or `trust` writes a step-private state that vanishes.
- **`ballast init`, `--check`, doctor.** `Init` sets `records_trust = False` so `settle` returns `None` and the old reminder prints; `--check` never imports `setup_trust`; doctor reads only `status --json` and maps `baseline_source` through a whitelist.
- **The comparison before every run.** `_trust_refusal`, `_refusal`, `_setup_refusal` and `_unfinished` are absent from the diff; `trusted.json`'s format and writer path (`json.dumps(inputs, indent=1)`) are unchanged; `_status` adds a key only when a baseline exists. Confirmed by E1: after a `recorded` verdict, `launcher._trust_refusal` returns `None` through the unchanged code.

## Review

```yaml
review: security
verdict: approved
findings:
  - id: SEC2-001
    severity: medium
    invariant: BL-INV-002
    location: tools/spec_workflow/setup_trust.py:_default_branch (reviewed check), launcher.py:add_reviewed; decisions.md DEC-0008; ADR-0014 "Residual risks"
    description: >
      Demonstrated (E1). The reviewed record is machine-wide and holds names
      only, so a committed `ballast.toml` that repoints `[github] repository`
      to any other repository the operator ever ran `ballast trust` for is
      eligible as soon as that repository's default branch carries the same
      `ballast.toml` and constitution. In E1 the checkout committed
      `other/pilot`'s configuration with `[agents.permissions]` widened to
      `Bash(*)`; `settle` returned `recorded other/pilot's default branch main`
      and the launcher accepted the checkout. No human reviewed that
      configuration for this project. Preconditions, stated honestly: the
      machine must hold at least two reviewed repositories and one of them must
      carry, on its default branch, a configuration more permissive than the
      target project's (a pilot or sandbox repository is the realistic case),
      or the attacker must be able to change a reviewed repository's default
      branch (an unprotected pilot, a fork the operator once trusted, a
      transferred or reclaimed name: the record never expires). The attacker
      chooses among existing reviewed configurations; it cannot craft one.
      Because the recorded reference names the matched repository and the setup
      line prints it, an operator running `ballast setup` can notice; a
      preparation started by an orchestrator prints to nobody. This is the
      residual the author recorded as DEC-0008 and the first review's SEC-004;
      it is real, bounded, and the design cannot close it without a spec change.
    required_action: >
      Human resolution at merge, as DEC-0008 already asks: accept as-is, or
      choose (b) per-repository digests of the reviewed `ballast.toml` and
      constitution (closes it; costs one `ballast trust` per default-branch
      change), or a middle ground not listed there: for a checkout that already
      has an operator baseline, require the pinned repository to equal the one
      in that baseline's `ballast.toml` (closes the repoint for re-setups, not
      for fresh clones). Whatever the choice, pair it with SEC2-003 so the
      record's growth is visible. No code change is required for approval; the
      merge decision is the approval of this residual.

  - id: SEC2-002
    severity: low
    invariant: BL-INV-002
    location: tools/spec_workflow/setup_trust.py:throwaway_environment, _observe_in (fetch); shared with branch_sync.py
    description: >
      Demonstrated (E4), pre-existing scope. The environment of the two network
      commands drops the Git location and `GIT_CONFIG_*` injection variables
      but keeps `GIT_CONFIG_GLOBAL`, `GIT_CONFIG_SYSTEM`, `GIT_SSH_COMMAND`,
      `GIT_EXEC_PATH`, `HOME` and `XDG_CONFIG_HOME`, because they are the
      operator's and carry their credential helper. With
      `GIT_CONFIG_GLOBAL` pointing at a file in the checkout holding
      `url.<evil>.insteadOf=<pinned url>`, E4 returned `recorded
      example/project's default branch main` while the bytes came from the
      evil mirror. A confined step cannot set the operator's environment, so
      this needs a checkout-sourced shell hook the operator opted into
      (direnv `.envrc`, a shell `rc` sourced from the repository, an IDE task):
      the same hook could also change `PATH` outside the excluded roots and
      replace `ballast` itself, which is why this is the operator-shell
      boundary every Ballast command already assumes, and why it is low. It is
      new only in that setup and preparation now reach the network on this
      path, where before only branch synchronization did.
    required_action: >
      Optional hardening, one local command: before `ls-remote`, run
      `git ls-remote --get-url <url>` in the throwaway environment (no
      network; it prints the URL after `insteadOf` rewriting) and treat a
      result different from `<url>` as unobservable. It closes the only
      rewrite Git performs silently and costs nothing; `branch_sync` can
      share it. State in ADR-0014's residual risks that the observation trusts
      the operator's shell environment and Git configuration.

  - id: SEC2-003
    severity: low
    invariant: BL-INV-002
    location: tools/spec_workflow/launcher.py:_review_repository; tools/ballast doctor `_trust`
    description: >
      Demonstrated (E5). `ballast trust` adds the pinned repository to the
      machine-wide record and prints nothing about it on success (stdout is
      only `trusted N workflow inputs for ROOT`), and no command lists the
      record; the README names the file. The mitigation ADR-0014 and DEC-0008
      rely on ("remove the entry when a repository changes hands") needs the
      operator to know an entry was created, in particular when they trust a
      worktree whose `ballast.toml` an agent repointed, which is exactly the
      case SEC2-001 needs.
    required_action: >
      Print one line from `_review_repository` on success, for example
      `recorded OWNER/NAME as reviewed on this machine; setup may trust fresh
      checkouts whose configuration equals its default branch`, and have
      doctor's trust check list the reviewed repositories it reads from
      `status --json` (or a new `ballast trust --list`). Display only; no
      change to the comparison.

  - id: SEC2-004
    severity: info
    invariant: BL-INV-002
    location: tools/spec_workflow/setup_trust.py:_observe_in (`_blob_id(data, "sha1")`), `--object-format=sha1`
    description: >
      Unresolved assumption, not demonstrated. The default-branch comparison
      is of 160-bit SHA-1 blob IDs, not of content, because the fetch is
      blob-less. A second preimage of the reviewed blob is infeasible; the
      only path is a chosen-prefix pair (B merged to the default branch, B'
      used locally), which needs collision bytes inside a TOML or Markdown
      file to survive human review and GitHub's sha1dc rejection on push.
      Accepted as is.
    required_action: >
      None. If ever revisited, `cat-file` of the two blobs after a fetch with
      `--filter=blob:limit=256k` would compare bytes at a bounded cost.

  - id: SEC2-005
    severity: info
    invariant: BL-INV-002
    location: docs/adr/0014-setup-recorded-trust-baseline.md "Residual risks"
    description: >
      Demonstrated (E2), documented. "Reviewed" is whatever the reviewed
      repository's default branch holds at observation time: after the default
      branch moved to a widened `[agents.permissions]`, a checkout committing
      the same bytes was `recorded`. The ADR and README say this depends on
      branch protection. Confirmed as the intended D-02 behavior; no change.
    required_action: None.

  - id: SEC2-006
    severity: info
    invariant: BL-INV-002
    location: tools/spec_workflow/setup_trust.py:_check_pointer; ADR-0014 decision 7
    description: >
      Unresolved assumption, stated for the record. The pointer check is
      structural and is sufficient only because a confined step can create no
      surviving directory outside the checkout, `/tmp` and `/run`
      (`confined_argv`: read-only `/`, tmpfs and overlays), and cannot write
      the pointer (`_git_binds`). ADR-0014 does not say the check leans on the
      sandbox.
    required_action: >
      One sentence in ADR-0014 decision 7 or its residual risks: the pointer
      check relies on the step sandbox leaving no agent-writable path outside
      the checkout and the temp roots; weakening the sandbox weakens it.
```

## Attacks tried and why they fail

- Forging the reviewed record or provenance: both live in operator state that `state_base` validates and the sandbox mounts read-only or replaces with a step-private tmpfs; malformed, unbound or foreign-schema reads fail closed; the comparison never reads provenance.
- Uncommitted or committed-but-unreviewed configuration: `HEAD` refusal, then the reference comparison; a widened `ballast.toml` on a feature branch is `differs from ... default branch`.
- Moving `refs/remotes/origin/<default>`, adding remotes, `insteadOf` in `.git/config`, promisor or alternates configuration: the throwaway never reads the checkout's Git state (E3); local commands have no transport.
- Planting objects in the checkout to satisfy `HEAD:<path>`: achievable by committing anyway, and not a boundary.
- Swapping protected bytes between check and record: the recorded baseline is the first snapshot; the launcher refuses the swapped state.
- Deleting saved run state, or hiding an in-progress marker: the marker is in operator state; run state is a refusal in depth, and the agent's other changes are not protected inputs.
- Reusing a path with a stale baseline, or inheriting another checkout's: preparation removes the stale pair before installing and never reads one; candidates are verified against their own operator-state record.
- Making `ballast init` or `--check` record: `records_trust = False`; `--check` never imports `setup_trust`.
- `.gitattributes` filters or `eol`: only make the checkout ineligible.

## Verdict

The feature keeps the stated boundary: within the confined-step model, no path was found by which an agent-written protected input is recorded without a human having reviewed those bytes somewhere. The one working escalation (SEC2-001) is the residual the author already surfaced as DEC-0008; it is bounded by the operator's own reviewed repositories and belongs to the human merge decision, which this review hands it to with its severity stated. SEC2-002 and SEC2-003 are cheap follow-ups that make the DEC-0008 mitigations operable; they do not block.

- Verdict: approved

## Resolution

Resolved by the driving agent under the operator's standing authority for v1.0 issues (2026-10-05), test-first; listed for merge review (not an operator approval).

- SEC2-001: resolved (DEC-0008, option (b)). `ballast trust` records per repository the digests of the trusted `ballast.toml` and constitution; setup and preparation accept the default-branch observation only when the checkout's files equal a pair reviewed for the repository it pins, before any network request. `tests.test_setup_trust.ReviewedConfigurationTests` (repointed reviewed repository, exact reviewed configuration, name without digests, accumulation, malformed digests, no network first). ADR-0014's residual risks are rewritten.
- SEC2-002: resolved. `git ls-remote --get-url <url>` runs in the throwaway's hardened environment first; a result other than `<url>` is "unobservable" (not eligible). `RewrittenUrlTests` uses an `insteadOf` in a `GIT_CONFIG_GLOBAL` fixture (it recorded from the mirror before the fix). ADR-0014 now states that the observation trusts the operator's Git environment. `branch_sync` is unchanged.
- SEC2-003: resolved. `ballast trust` prints one `recorded OWNER/NAME as reviewed on this machine: ...` line when it changes the record; `launcher.py reviewed --json` and `ballast doctor`'s trust check list the reviewed repositories (`TrustProvenanceTests`, `TrustSourceTests`).
- SEC2-004, SEC2-005: no action, as the review states (SEC2-005's moved-default-branch case is now also refused, because the new bytes were not reviewed).
- SEC2-006: resolved. ADR-0014 states that the pointer check relies on the step sandbox.
