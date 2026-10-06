# Plan review: Prepare a new worktree on first Ballast use

- Review: plan (independent, agent-provisional; not a human approval)
- Reviewer: claude-opus-5-5, fresh context
- Feature: `specs/15-worktree-setup` (Issue #15, R2, Autonomous run `ccdd9716`)

## Scope of the review

Read `AGENTS.md`, `docs/policies/workflow.md` (review matrix), `docs/policies/engineering.md`, `docs/policies/project/workflow.md`, `docs/policies/project/testing.md`, the engineering-review skill, and the feature's `intent.md`, `spec.md`, `plan.md`, `research.md`, `data-model.md`, `contracts/prepare.md`, `contracts/cli-and-launcher.md`, `quickstart.md` and `autonomous/record.md`. `tasks.md` and `decisions.md` do not exist yet, as expected at this stage; `docs/policies/project/engineering.md` does not exist.

Each design claim the plan makes about existing behavior was checked against the current code: `tools/setup` (`Setup.main`, `lock`, `attempt`, `build`, `copy_verified`, `copy_kept`, `primary`, `copy_from_primary`, `validate`, `roll_back`, `finish`, `recover`, `entries`, `tracked`, `installed_digests`, `INSTALLED`, `LOCAL_STATE`, `PARENTS`), `tools/spec_workflow/launcher.py` (`state_dir`, `input_bases`, `read_record`, `checkout_lock`, `_setup_refusal`, `_trust_refusal`, `_hold`, `main`) and `tools/ballast` (`command_standard`, `main`, `declarations`, `damage`, doctor's `_trust`). ADR-0002, ADR-0007 and ADR-0008 exist under `docs/adr/`.

## Requirement coverage

Every FR-001 to FR-015 and AC-001 to AC-020 maps to a design element and to a planned test in `quickstart.md`. The trigger list (`run`, `ledger`, `intake`) matches D-04; `trust` never prepares, so a baseline is never recorded over files placed in the same command (BL-INV-002). The no-network rule holds by construction: `--prepare` never reaches `install_spec_kit`/`_fetch_source`, and the CLI keeps the not-fetched refusal and adds a `damage()` check before running the cached setup (FR-002, FR-005, AC-013). Older-version and older-CLI compatibility is handled by the `[setup] prepare` declaration, read as data like `recoverable` (FR-013, ADR-0002).

## Source authority and trust

Candidates are only installations whose content hashes, on the stage copy, equal a record in operator state keyed by the candidate's resolved path; ref and fingerprint (which digests `ballast.toml` bytes and the standard's `tools/` and `templates/`) must match, so a different `[agents.permissions]` or pin is never reused. The plan correctly moves the record read after the shared lock (closing the read-then-lock window in today's `copy_from_primary`) and verifies the stage copy, not the source, so a concurrent change in the source can only cause a rejection. The new `executable` list closes the mode gap that `launcher.digests` leaves without changing the trust-baseline format. No `trusted.json` is read across checkouts; removing a stale baseline at a reused path only narrows authority and forces one extra `ballast trust`, and it is declared in the proposed ADR-0011 as a launcher-trust-model (R2) change.

## Partial failure and concurrency

Preparation reuses ADR-0007's lock, journal, stage, switch, live verification and recovery unchanged, adding `mode` to the journal and holder and one recovery rule (roll back a committed first preparation whose fingerprint no longer applies). I traced that rule through `roll_back`: with every plan item `new` and an empty `before`, a committed switch is moved back into the stage and discarded, and `read_record` returns `None` once the stamp is gone, so the verification against `{}` holds. Per-worktree state stays keyed by `sha256(resolved path)`; run state lives in the checkout and is never copied.

I examined the one-worktree concurrency window (AC-020) and the definition of "no installation" used by the refusal in step 5; both are recorded as findings with the required contract adjustment. I also examined the launcher's lock ordering for `trust`/`discard-runs` on an uninstalled checkout against the contract's "no file is created" claim, and the case where a candidate's lock file is absent.

## Complexity and scope

The change stays inside the three files ADR-0007 and ADR-0002 already give these responsibilities; no new store, dependency or abstraction is introduced, and the size estimate (about +210 lines plus tests) is proportionate. No silent scope expansion beyond the spec's non-goals was found.

## Reviews this feature needs

Per the review matrix and the project's R2 boundaries (installed paths, launcher trust model, what `ballast` executes): security and architecture (against ADR-0007) in addition to engineering and test; documentation because `README.md` and a new ADR change. The project testing policy's end-to-end scratch run is planned in `quickstart.md`.

<!-- ballast-findings: begin -->
## Findings (recorded from the review draft)

- F-001 (medium, implementation-bug, accepted-provisionally): contracts/prepare.md step 5 refuses 'this checkout already holds an installation; run `ballast setup`' whenever any installed entry exists. Two commands started together in one new worktree (AC-020) can both see run.py missing in the CLI; if the first finishes before the second takes the exclusive lock, the second refuses with the wrong next action for a correctly prepared worktree (FR-014). Fix in tasks: under the lock, when the live installation is current for this ref and fingerprint (Setup.current), exit 0 with 'nothing to prepare' so the CLI proceeds to the launcher, mirroring step 3's committed-recovery success; cover it in PrepareConcurrencyTests.test_one_preparation_per_worktree. Small, local contract change that does not alter intent; merge review can confirm.
- F-002 (low, implementation-bug, open): research.md R6 and data-model.md define 'installation present' as any path entries(root) lists, but setup's own definition (Setup.live_entries) excludes entries holding a tracked file. A project that tracks a file matching docs/policies/*.md or an .agents/skills/speckit-* directory would then never be prepared. Use the tracked-filtered rule (live_entries) for the step-5 check.
- F-003 (low, spec-ambiguity, open): contracts/cli-and-launcher.md says `trust` and `discard-runs` on an uninstalled checkout create no state file, but launcher.main calls _hold before the installed check, and _hold opens checkout.lock with O_CREAT whenever the state directory exists (a reused path, or after an interrupted preparation). Either check installation before _hold for these commands or narrow the contract to 'records nothing'.
- F-004 (info, spec-ambiguity, open): research.md R4 rule 2 opens a candidate's checkout.lock only when the file exists but does not say what happens when it is absent. Stage-copy verification still guarantees integrity, but the contract should state that a candidate without a lock file is rejected (or copied without the shared lock) so the implementation and tests agree.
- F-005 (info, spec-ambiguity, open): Doctor's trust check keeps the remedy `ballast setup` for an uninstalled checkout. That remains correct, but with a version that declares `[setup] prepare` the cheaper, offline next step is the first `ballast run`/`ledger`/`intake`; consider naming both, as the new launcher refusal does, for consistent operator guidance.
<!-- ballast-findings: end -->
