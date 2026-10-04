# Decisions

## DEC-0001 — Proposal

- Source: plan review round 7 (Codex), high finding on the README install version before the first installer release.
- Proposal: keep `v0.1.0` in the README until Release Please writes the first installer release; close the window by merging the Release Please PR immediately after this feature merges; add a 404 hint pointing to the developer fallback; verify the unmodified README command after release (T042).

## DEC-0001 — Resolution

- Decision: accepted (agent, provisional, under the operator's standing authority of 2026-10-03; v0.x releases delegated).
- Rationale: the failure is a transient, actionable download error confined to the merge-to-release interval, which the delegated release step closes immediately.

## DEC-0002 — Proposal

- Source: manual implementation path (2026-10-04). `validate-implementation` requires every task checked, but T041 (converge and spec reconciliation) is performed by the workflow's own `converge` and `reconcile-spec` steps after that validation, and T042 needs a published release.
- Proposal: keep T041 and T042 in `tasks.md` for traceability but without checkboxes; T041 is satisfied by the workflow steps, T042 becomes the PR's post-release verification checklist (run the unmodified README command on a clean account after the release).

## DEC-0002 — Resolution

- Decision: accepted (agent, provisional, under the operator's standing authority of 2026-10-03).
- Rationale: checking these boxes now would claim work that has not happened; the workflow and the release still perform both.

## DEC-0003 — Proposal

- **Observed during**: T017, implementation reviews 1 and 2 (Codex)
- **Classification**: contract-discovery
- **Observation**: The `systemd-run` check starts a real transient scope (`systemd-run --user --scope --collect /usr/bin/true`). Both implementation reviews flag this as a change to the user manager's runtime state, which conflicts with a strictly read-only doctor; round 2 lists it as NOT RESOLVED. After the implementation, `research.md` R7 gained a paragraph reading FR-011 as forbidding only file and persistent-state writes, attributed to an "operator decision, implementation review 1". This ledger has no record of that decision.
- **Proposed decision**: Keep the active scope probe. FR-011 and AC-012 forbid writes to files and persistent state (project, fetched versions, trust baseline, run state, ledgers) and downloads. A collected transient scope that leaves no unit or file behind is allowed. Add one sentence to FR-011 saying so. Rejected alternative: a passive check (unit-file or D-Bus property inspection) that reports `inconclusive` when it cannot tell whether a scope would start.
- **Evidence**: `tools/ballast:420-440`; `reviews/implementation-review-codex-1.md` (Medium, architecture issue); `reviews/implementation-review-codex-2.md` (NOT RESOLVED); `research.md` R7, paragraph after the table.
- **Affected artifacts**: `spec.md` FR-011 (one clarifying sentence); `research.md` R7 (replace the attribution with `DEC-0003`)
- **Status**: proposed

## DEC-0004 — Proposal

- **Observed during**: T017, fix for implementation review 1
- **Classification**: contract-discovery
- **Observation**: T017 says a `systemd-run` that is present but cannot start a scope is `inconclusive`, which is non-blocking. In that case doctor exited 0 with "Everything Ballast needs is in place" although headless steps cannot run. The fix makes a definite failure to start `unsupported`, which blocks with exit 1. A timeout stays `inconclusive`.
- **Proposed decision**: A definite scope-start failure is `unsupported` and blocks `ballast run (headless steps)`. A timeout is `inconclusive`. Align the T017 wording in `tasks.md`; `research.md` R7 already says this.
- **Evidence**: `tools/ballast:430-438`; `tests/test_doctor.py` (scope-failure verdict test near line 313); `reviews/implementation-review-codex-2.md` (RESOLVED)
- **Affected artifacts**: `tasks.md` T017 (wording only)
- **Status**: proposed

## DEC-0005 — Proposal

- **Observed during**: T016, fix for implementation review 1
- **Classification**: design-decision
- **Observation**: The plan (R8, T016) excludes executables that are inside the project root or the enclosing Git working tree. The implementation now rejects a resolved `PATH` entry or program inside *any* Git working tree, meaning any directory with a `.git` ancestor. It then keeps searching later `PATH` entries. Side effect: an operator whose home directory is a Git repository (for example a dotfiles repo with `~/.git`) gets every tool under `~/.local/bin` (such as `claude`, `gh` and `uvx`) reported `missing` with the "another Git working tree" note. `self-install` already refuses `~/.local/bin` in that layout, as planned in R4.
- **Proposed decision**: Accept the broader rule for doctor's program resolution. It matches ADR-0002's "any Git working tree" rule for probe files. Record the dotfiles-home limitation in `research.md` R8 and in the note doctor prints.
- **Evidence**: `tools/ballast:166-170`, `tools/ballast:319-342`; `tests/test_doctor.py` (external checkout test near line 427); `reviews/implementation-review-codex-1.md` (High), `-2.md` (RESOLVED, plus the first-match follow-up now addressed by the loop at lines 329-336)
- **Affected artifacts**: `plan.md` and `research.md` R8 (executable resolution), `tasks.md` T016 (wording)
- **Status**: proposed

## DEC-0006 — Proposal

- **Observed during**: T008, fix for implementation review 1
- **Classification**: contract-discovery
- **Observation**: R4 and ADR-0001 refuse "a symlink to anything that is not Ballast", which means a symlink to a Ballast file would be accepted. The implementation now refuses every symlink at `DIR/ballast` with exit 2, even one pointing to an identical Ballast file. It never follows or keeps a symlink. With `--force`, it replaces the symlink with a regular file and reports "replaced ballast a symbolic link …". The reason: a symlink into a checkout would otherwise pass the same-version check and keep executing checkout code.
- **Proposed decision**: Treat any symlink at the target as a foreign target: refuse it without `--force`, and with `--force` replace it with a regular file. Update R4, ADR-0001's consequence line and `contracts/install.md`.
- **Evidence**: `tools/ballast:219-235`; `tests/test_ballast.py` (symlink test near line 332); `reviews/implementation-review-codex-1.md` (High), `-2.md` (RESOLVED)
- **Affected artifacts**: `research.md` R4, `contracts/install.md`, `docs/adr/0001-cli-release-asset-install.md`
- **Status**: proposed

## DEC-0007 — Proposal

- **Observed during**: T018, fix for implementation review 1
- **Classification**: design-decision
- **Observation**: The plan does not say how the network `HEAD` probe maps HTTP results. The implementation maps 2xx and 3xx to reachable, without following redirects (one request). It maps 404 or no connection to `missing`, which blocks setup, and every other HTTP error (403, 429, 5xx) to `inconclusive`, which does not block. Before the review fix, those other errors counted as reachable.
- **Proposed decision**: Accept this mapping and record it in `research.md` R7 and R10.
- **Evidence**: `tools/ballast:549-560`; `tests/test_doctor.py` (status tests near line 325, redirect test near line 706); `reviews/implementation-review-codex-2.md` (RESOLVED)
- **Affected artifacts**: `research.md` R7 and R10
- **Status**: proposed

## DEC-0003 — Resolution

- Decision: accepted as proposed (agent, provisional, under the operator's standing authority of 2026-10-03); affected artifacts updated.
- Rationale: keeps the only probe that proves headless steps can run; no file or persistent state is written.

## DEC-0004 — Resolution

- Decision: accepted as proposed (agent, provisional, under the operator's standing authority of 2026-10-03); affected artifacts updated.
- Rationale: a definite failure means headless steps cannot run; reporting ready would be wrong.

## DEC-0005 — Resolution

- Decision: accepted as proposed (agent, provisional, under the operator's standing authority of 2026-10-03); affected artifacts updated.
- Rationale: closes the review's high finding; the dotfiles-home limitation is documented and the doctor note explains it.

## DEC-0006 — Resolution

- Decision: accepted as proposed (agent, provisional, under the operator's standing authority of 2026-10-03); affected artifacts updated.
- Rationale: a symlink into a checkout would otherwise keep executing checkout code.

## DEC-0007 — Resolution

- Decision: accepted as proposed (agent, provisional, under the operator's standing authority of 2026-10-03); affected artifacts updated.
- Rationale: only a definite answer may block, and an ambiguous error must not pass.
