# Decisions

## DEC-0001 — Proposal

- **Found during**: the tasks gate of Autonomous run `97858712` (2026-10-05). The gate blocked with `BLOCKED_DECISION` (category `contradiction`) on analyze findings C1 and C3, both HIGH.
- **Conflict**: AC-002 requires a `verified` criterion to show "a link to each named test and to the check run or CI result that ran it". AC-009 requires every summary line to carry "a link to the source record it was derived from". The plan and [packet-format.md](contracts/packet-format.md) render named tests as plain text and per-criterion evidence as `ledger event <seq> of run <id>`, with no URL, and T019 and T028 test that weaker behavior. Per-criterion evidence comes from `ballast ledger check`, which runs the test locally and records it only in the local ledger (research R4, R5), so no check run ran it and no URL exists for it.
- **Label**: spec ambiguity (the spec promises a link that does not exist for local evidence).
- **Options**:
  1. Narrow the spec: reword AC-002 and AC-009 to the ledger-reference design, and add test-file links.
  2. Re-plan for real check-run links: run the manifest's mapped tests from `run-checks` so a check run exists for each. Research R5 classifies this as R2 under FR-012, and it widens scope.
  3. Hybrid: link each named test's file at the head commit, link the head commit's check runs when GitHub reports any, and narrow AC-002 and AC-009 only for evidence held solely in the local ledger.
- **Needs**: a resolution before implementation.

## DEC-0001 — Resolution

- **Status**: resolved by the driving agent (claude/claude-opus-5-5) under the operator's standing authority for the Epic #11 children (2026-10-05: "I approve also all issues that lead to 1.0 ... drive in autonomy"). The operator has not reviewed this option individually; it is listed in the PR for merge review. Option 3.
- **Resolution**: a `verified` row links each named test's file at the head commit (`blob/<head>/<path>`, the longest dotted prefix of the test name whose `.py` file exists at head; a test whose file is absent is named unlinked with `file not found at head`). The row links the head commit's check runs (`commit/<head>/checks`) when the R8 read reported at least one, else says `no CI result at head`; CI stays suite-wide and never changes a criterion's state (R4). Evidence held only in the local ledger (`verification` events, gate approvals) is named `ledger event <seq> of run <run_id>`. Every other summary line keeps its link.
- **Rationale**: it delivers every link that exists without a new command path (option 2 is R2), and narrows the promise only where no URL can exist. The test-file check uses `git cat-file -e`, already in ADR-0006's read list, so R1 holds.
- **Changed now**: spec AC-002, AC-009 and FR-006; plan summary; [packet-format.md](contracts/packet-format.md) link forms, example row and rules; data-model `Criterion.ci` and `TestEvidence.file`/`source`; quickstart AC-002 row; tasks T019, T022, T025, T028 and the analyze-findings section. Also folded in from the analyze report: A1, I2 and F3 into T048; I1 and F2 in research R17 and R12; [P] dropped from T039. C2 is unchanged: T036 keeps the contents-API read (PD-0004, PD-0005), because reading the base from local Git would add a `base-not-local` failure (R10).
- **Tests**: T019 (AC-002 links, `file not found at head`, CI present and absent) and T028 (ledger references only for ledger-held records).

## DEC-0002 — Proposal

- **Found during**: the independent documentation and engineering reviews of T053 ([documentation-1.md](reviews/documentation-1.md) DOC-001, [engineering-1.md](reviews/engineering-1.md) ENG-005), 2026-10-05.
- **Conflict**: US3 says the packet "stays current" as work continues, and the policy told the operator to record `ballast ledger check` evidence and let "the next checkpoint (`ballast run resume`, `continue` or `publish`)" show it. For an Autonomous run none of these refreshes it: `resume` is refused for an Autonomous run, `ballast run publish` runs no checkpoint (and refuses a run already `published`), and `continue` starts a new run whose packet reads only the new run's ledger and records, so evidence recorded under the Autonomous run ID never appears. The packet's own hint (`ballast ledger check RUN_ID AC-NNN TEST`) therefore leads nowhere on an Autonomous PR, which is this feature's main use. The `pending/head-not-local` remedy ("fetch the feature branch, then resume") has the same gap.
- **Label**: proposed product change (a new operator entry point), with a spec ambiguity in US3 (which run's evidence a packet reads).
- **Options**:
  1. Add `ballast run checkpoint RUN_ID`: run only the Draft PR checkpoint and packet for an existing run, no agent step, allowed for any run status. Smallest change; R1 if it reuses the #17 checkpoint unchanged.
  2. Let `ballast run publish` also run the checkpoint for a `published` run.
  3. Keep the behavior; the packet of a finished Autonomous run is final, and the policy says so (done now as the truthful interim).
- **Interim**: the policy now states option 3's behavior truthfully (no behavior change). The implementation is unchanged.
- **Needs**: an operator decision before v1.0; options 1 and 2 change the launcher's command surface and need their own Issue.

## DEC-0002 — Resolution

- **Status**: resolved by the driving agent (claude/claude-opus-5-5) under the operator's standing authority for the Epic #11 children (2026-10-05); listed in the PR for merge review. The operator has not reviewed this option individually.
- **Resolution**: option 3. The packet of a finished Autonomous run is final for this feature, and the policy says so (already applied as the interim). A refresh entry point for a finished Autonomous run's PR (option 1 or 2) changes the launcher's command surface and belongs to #21, which owns taking an Autonomous run through PR review; the gap is recorded on #21. No spec, plan or task change: US3's "stays current" holds for human-gated runs, which resume.
