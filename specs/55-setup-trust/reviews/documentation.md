# Documentation review: #55 setup-recorded trust baseline

- Reviewer: documentation reviewer, independent context
- Scope: `git diff 641fa7f..HEAD` over `README.md`, `templates/policies/`, `docs/` (ADR-0007, ADR-0011, new ADR-0015, roadmap), `specs/TECHNICAL-SPEC.md` and `specs/55-setup-trust/constitution-amendment.md`, checked against `tools/spec_workflow/setup_trust.py`, `tools/spec_workflow/launcher.py`, `tools/setup`, `tools/init` and `tools/ballast`
- Policies read: `docs/policies/documentation.md`, `.agents/skills/ballast-documentation-review/SKILL.md` (there is no `docs/policies/project/documentation.md`)

## What was checked

- README "Worktrees", "Setup records the baseline", the `trust`/launcher paragraph, and the pin-update and rollback blocks, claim by claim against `setup_trust._evaluate`/`_reference`/`_check_*`, the printed lines (`Recorded the trust baseline ...`, `No trust baseline recorded: <reason>.`, the two unchanged remedy lines), `launcher.trust`/`_review_repository`/`_status` and doctor's `baseline recorded by ...`. Conditions, network and Git authority, the first-checkout-per-machine rule, run state, markers, extra protected inputs (`.venv`, committed `.specify` files), the F-005 re-record consequence, doctor output and "init never records" are true, with the gaps below.
- Policy paragraph "Setup-recorded baseline" in `templates/policies/spec-kit-workflow.md`, ADR-0015 (context, decision, consequences, the two agent inferences, rejected alternatives, supersession), TECHNICAL-SPEC status, roadmap items 3 and 7.
- Grep for `never records`, `records trust`, `nothing is trusted`, `silently trust`, `local-only`, `offline`, `no network`: remaining hits are accurate (README:72 and ADR-0012 say `init` never records trust, which holds: `tools/init` sets `records_trust = False`) or are annotated (ADR-0007, ADR-0011). The old README text "nothing is trusted for you" and the roadmap's "setup cannot silently trust itself" are gone.
- ADR history: `git diff --word-diff` on ADR-0007 and ADR-0011 shows only added superseded-in-part notes and the rewording of "no network" to "no download" beside the superseded clauses; nothing else changed.
- Links in README, ADR-0015, ADR-0007, ADR-0011, the amendment and TECHNICAL-SPEC resolve; the `#setup-records-the-baseline` anchor exists.
- Constitution: `git diff 641fa7f..HEAD --stat -- .specify` is empty, so it was not edited. The amendment replaces BL-INV-002, adds a 1.2.0 history entry with reason and compatibility, and sets the version line, which matches FR-018 and AC-026 and the constitution's governance wording. AC-026 holds only once the operator applies it (DOC-007).
- `uv run ... -m unittest tests.test_governance`: 14 tests OK.

review: documentation
verdict: changes_required

## Findings

### DOC-001 (medium): the earlier-`ballast trust`-baseline alternative is documented for preparation, but only setup uses it

`setup_trust._reference` reads the operator baseline only when `mode == "setup"`; a preparation never opens operator state (docstring: "a preparation ... never opens a baseline in its state"). README:98 correctly says a preparation compares with the default branch. But README:100 and :105 say "`ballast setup`, and the preparation of a new worktree" record when the files equal the default branch "or the baseline you earlier recorded with `ballast trust` (no network needed for that one)". The policy paragraph (`templates/policies/spec-kit-workflow.md:349-358`) and ADR-0015 decision item 9 (line 26) say the same without the limit. A worktree prepared offline, or from a configuration only the primary checkout's baseline covers, is therefore not recorded, and a reader is told otherwise.
Action: in README:105, the policy and ADR-0015 item 9, state that the earlier-baseline alternative applies to `ballast setup` only, and that a worktree preparation always needs the network and a reviewed repository.

### DOC-002 (medium): the upgrade and first-use consequence is in the ADR but not in the README or the policy

ADR-0015:39 and the amendment say a project whose baselines predate this decision needs one `ballast trust` per machine to populate `reviewed-repositories.json`. README:106 says only that "the first checkout of a project here still needs one `ballast trust`". A user with an existing baseline from an earlier Ballast version will expect a fresh worktree to be recorded and get `No trust baseline recorded: the pinned repository is not one you trusted on this machine` (`setup_trust.NOT_REVIEWED`). Also `launcher._review_repository` only warns on a failed write ("setup will not trust its fresh checkouts"), which no document mentions.
Action: add to README:106 that an existing baseline does not count, that one `ballast trust` per project and machine after upgrading records the repository, and that `ballast trust` prints a warning when it cannot record the repository.

### DOC-003 (low): "committed and unchanged" is not tied to the everyday pin-bump flow

README:105 and the pin-update/rollback blocks (README:184, :197, `unless setup recorded the baseline` / `unless setup says it recorded the baseline`) read as if a pin bump may be recorded. In the normal flow the operator edits `ballast.toml` uncommitted, so setup records nothing (`<path> has uncommitted changes`), and a committed bump differs from the default branch unless it has merged. README:109 covers only the committed-branch case.
Action: add one sentence at README:109 that an uncommitted edit, or any configuration not yet on the default branch, is never recorded, so the pin-update block normally ends with `ballast trust`; point the two block comments at "Setup records the baseline".

### DOC-004 (low): requirements and limits of the live check are not stated

Undocumented: Git 2.41 or later outside working trees is required (`GIT_FLOOR`, reason `git 2.41 or later is required`); network commands time out at 30 s and 120 s; setup holds the checkout lock for that time (ADR-0015:42 says so, README does not); `ballast setup --check` and `ballast init` never record (`--check` appears only in the `tools/setup` docstring, `init` only at README:72).
Action: add a short sentence in "Setup records the baseline" with the Git floor, the time bound and the lock, and that `--check` and `ballast init` never record.

### DOC-005 (low): policy sentence still says inputs are compared "since `trust`"

`templates/policies/spec-kit-workflow.md:335`: "if those inputs changed since `trust`". The new paragraph right after it says setup may also record the baseline.
Action: reword to "since the baseline was recorded".

### DOC-006 (low): TECHNICAL-SPEC status is ambiguous and omits the setup/preparation difference

`specs/TECHNICAL-SPEC.md:2412`: "... equal to the default branch ..., for a repository `ballast trust` reviewed on this machine, or equal to the checkout's own baseline from `ballast trust`" can be read as the reviewed-repository condition applying to both alternatives, and does not say the own-baseline alternative is setup-only (DOC-001).
Action: split the two alternatives into separate clauses and add the setup-only limit.

### DOC-007 (info): constitution stays at 1.1.0 until the operator applies the amendment

The constitution is unedited (correct) and `constitution-amendment.md` is complete. Until it is applied, BL-INV-002 still reads "refuses until the operator trusts the current inputs", while README, ADR-0015 and the policy describe setup-recorded trust. The ADR (status "proposed", "accepted when its PR merges") and the amendment both say so. AC-026 is closed only after the operator applies it and the PR records that.
Action: none in this diff; the PR description should name the amendment as an operator step.

### DOC-008 (info): ADR-0015 is complete

Context, decision (ordered conditions matching `setup_trust` docstring), reviewed-repository record, provenance, consequences including F-005, the two agent inferences for merge review, rejected alternatives and the supersession of ADR-0007 and ADR-0011 are present and match the code. Only DOC-001 applies to it (item 9).

## Resolution

Resolved by the implementer after the review.

- DOC-001 (medium): fixed. README, the policy template and ADR-0015 now say only `ballast setup` accepts the checkout's earlier baseline and a preparation never reads one.
- DOC-002 (medium): fixed. README says a baseline from before this version does not count, each project needs one `ballast trust` per machine after upgrading, and `ballast trust` only warns when it cannot write the record. The policy template says the same.
- DOC-003 (low): fixed. README says an uncommitted `ballast.toml` edit is never recorded and a pin bump not yet on the default branch always needs `ballast trust`; the pin-update block says so.
- DOC-004 (low): fixed. README names Git 2.41 or later, the 30 s and 120 s limits, that setup holds the checkout lock while it asks, and that `--check`, doctor and `ballast init` never record.
- DOC-005 (low): fixed. The policy says "since `trust` (or since the baseline setup recorded)".
- DOC-006 (low): fixed. `specs/TECHNICAL-SPEC.md` names the reviewed-repository condition and that the own-baseline alternative is setup-only.
- DOC-007 (info): an operator step: apply `specs/55-setup-trust/constitution-amendment.md` to the protected constitution. Stated in the PR notes.
- DOC-008 (info): no action.

Verdict after resolution: approved.
