# Quickstart: validating setup-recorded trust

How to prove the feature works. Contracts: [setup-trust.md](contracts/setup-trust.md), [launcher-and-doctor.md](contracts/launcher-and-doctor.md). Data: [data-model.md](data-model.md).

## Prerequisites

- Linux, Git 2.41 or later outside every working tree, `uv`.
- Fast gate: `uvx ruff check && uvx ruff format --check` and `uv run --no-project --python 3.13 --with pyyaml python -m unittest tests/test_*.py`.
- Full local gate: the same suite on a machine with a systemd user session, the Codex CLI and the Spec Kit CLI.
- No test reaches github.com: a local bare repository stands in for the pinned repository through the `setup_trust.repository_url` seam (research R18).

## Automated evidence (AC → test)

Test module names are the plan's; `tasks.md` fixes the exact test names.

| AC | Scenario | Where |
| --- | --- | --- |
| AC-001 | clean clone, config equals the stand-in default branch, repository reviewed → baseline recorded, provenance `setup`, output names the branch and commit | `tests/test_setup.py` |
| AC-002 | after AC-001, launcher `run`/`ledger`/`intake` preflight accepts with no `trust` | `tests/test_setup.py` (launcher subprocess) |
| AC-003 | doctor detail names `ballast setup`; after `ballast trust`, names `ballast trust` | `tests/test_doctor.py` |
| AC-004 | config differs from default branch but equals an operator baseline → recorded, reference `operator-baseline`, no network command run | `tests/test_setup_trust.py` |
| AC-005 | no-op setup with no baseline records; with a matching operator baseline → `kept`, bytes and provenance untouched | `tests/test_setup.py` |
| AC-006 | new linked worktree, first `run` prepares and records | `tests/test_setup.py` (`PrepareTests`) |
| AC-007 | worktree branch changed `ballast.toml` / constitution → installed, no baseline, launcher refusal names `ballast trust` | `tests/test_setup.py` |
| AC-008 | stale baseline and provenance at a reused path removed; re-recorded only when eligible | `tests/test_setup.py` |
| AC-009 | another checkout's baseline and provenance never opened (open-call spy) and never equal by copy | `tests/test_setup.py` |
| AC-010 | uncommitted `ballast.toml` pin bump; uncommitted constitution → skipped with reason | `tests/test_setup_trust.py` |
| AC-011 | committed widened `[agents.permissions]` differing from both references → skipped | `tests/test_setup_trust.py` |
| AC-012 | extra file under `.specify`, edited `.ballast/spec_workflow` file, a `.venv` → skipped naming the path | `tests/test_setup_trust.py` |
| AC-013 | `.git` pointer to a forged repository in the checkout or a temp root, missing back-link, a link → skipped | `tests/test_setup_trust.py` |
| AC-014 | unreachable URL, refused credentials (fake Git exit), missing/malformed `[github] repository`, timeout → skipped; with matching operator baseline → recorded | `tests/test_setup_trust.py` |
| AC-015 | local `refs/remotes/origin/main`, `origin` URL and `url.*.insteadOf` in the checkout point at the changed config → observation ignores them, skipped; argv log shows only the pinned URL | `tests/test_setup_trust.py` |
| AC-016 | `[github] repository` repointed to a repository whose default branch carries the same file, not in the reviewed record → skipped, no network command; never-trusted repository → skipped | `tests/test_setup_trust.py` |
| AC-017 | every skipped case: reason and `ballast trust` printed, exit status as without the feature, existing baseline bytes unchanged | `tests/test_setup_trust.py` (shared assertion) |
| AC-018 | in-progress marker → setup refuses as today, no baseline | `tests/test_setup.py` |
| AC-019 | `BALLAST_TAMPERED` → skipped | `tests/test_setup_trust.py` |
| AC-020 | saved run state in checkout; `active` / `stopped` / unreadable operator-state run → skipped; `completed` run alone → eligible | `tests/test_setup_trust.py` |
| AC-021 | setup started while a step holds the marker → no baseline | `tests/test_setup.py` |
| AC-022 | after a setup-recorded baseline, edit `.specify/scripts/...` → launcher refuses with today's message | `tests/test_spec_workflow.py` |
| AC-023 | existing launcher trust and refusal tests unedited and passing | `git diff main -- tests/test_spec_workflow.py` shows additions only in new classes; full suite green |
| AC-024 | provenance missing, unreadable, unbound, `setup` but unbound → `status --json` says `trust`; refusal unaffected either way | `tests/test_spec_workflow.py` |
| AC-025 | ADR-0014 exists; ADR-0007 and ADR-0011 mark the superseded clauses; roadmap wording updated | review of the PR diff; `tests/test_governance.py` link checks |
| AC-026 | constitution BL-INV-002 amended, version 1.2.0, amendment history entry | review; `tests/test_governance.py` |
| AC-027 | README and `templates/policies/spec-kit-workflow.md` describe conditions, network and Git authority, when `ballast trust` is still needed, doctor's source | `ballast-documentation-review` |

Additional tests: `record_baseline` write order and crash between writes (provenance bound to a never-written baseline reads as `trust`); reviewed-repositories record concurrency (ten `trust` processes) and malformed file read as empty; post-write recheck removes the baseline when an input changes during `settle`; `--check` and doctor never import `setup_trust`; the fetch-with-filter command works against a local bare repository with and without `uploadpack.allowFilter`.

## End-to-end check (recorded in the PR)

On a scratch GitHub repository the operator can read, with `[github] repository` set and the project pinned to the feature's build (`BALLAST_STANDARD_DIR` at a separate checkout of this branch):

```bash
git clone <scratch> a && cd a
ballast setup                 # expect: "No trust baseline recorded: the pinned repository is not one you trusted on this machine."
ballast trust                 # records the repository as reviewed
cd .. && git clone <scratch> b && cd b
ballast setup                 # expect: "Recorded the trust baseline ... default branch main at <commit>."
ballast doctor                # expect trust: "baseline recorded by ballast setup"
ballast run start --help      # the launcher accepts the checkout
git worktree add ../b-55 -b feat/55-x && cd ../b-55
ballast run start --help      # first command prepares and records; no ballast trust
printf '\n# edit\n' >> ballast.toml && git commit -qam edit
git worktree add ../b-56 -b feat/56-y feat/55-x && cd ../b-56
ballast run start --help      # expect: prepared, "No trust baseline recorded: ...", refusal naming ballast trust
```

Expected outcomes are the comments; record the outputs and the Git version in the PR.
