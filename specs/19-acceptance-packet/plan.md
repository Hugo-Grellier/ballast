# Implementation Plan: Source-linked acceptance packet on the Draft PR

**Branch**: `feat/19-acceptance-packet` | **Date**: 2026-10-05 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/19-acceptance-packet/spec.md` (intent agent-provisional, PD-0003, digest in [intent.md](intent.md))

**Risk**: R1, rechecked against the R2 boundaries in [research R18](research.md#r18-risk-recheck-against-the-r2-boundaries). The plan extends ADR-0003's fixed GitHub/Git command allowlist with read-only calls (proposed ADR-0006). The plan gate must confirm R1 explicitly. **Mode**: Autonomous run `97858712`. Every decision here is agent-provisional; merging the PR is the only human approval.

## Summary

Each PR checkpoint (#17) that ends with an open Ballast Draft PR (`created` or `reused`) now also publishes an **acceptance packet**. It is a Markdown section between `<!-- ballast:acceptance-packet:begin/end -->` markers in the PR description, built by a new trusted, stdlib-only module `tools/spec_workflow/packet.py`. Data flows in three stages:

1. **collect**: a fresh read of the PR supplies the head and base commits. Feature artifacts are read from the local Git object store at the head commit. Evidence comes from the run ledger, Autonomous decisions and checks from the operator records, CI from GitHub check runs at head, and an optional OpenAPI document from the contents API at base and head. Optional configuration is the `[review]` table of the protected `ballast.toml`.
2. **render**: a pure, deterministic function lists every spec criterion with one evidence state (`verified`, `failed`, `not run`, `stale`, `missing`), alongside risk, decisions labeled as recorded, open findings, checks, API and UI sections, and pinned source links.
3. **publish**: the packet's own section is replaced in place (or appended), only when its text changed apart from the generation time. The edit uses #17's re-read-before-edit rule and its `gh pr edit --body-file -`.

A criterion is `verified` only when every manifest-mapped test passed in operator-attested ledger checks bound to the head commit's implementation fingerprint, spec version and manifest version. Everything else falls to a weaker state that names what the evidence belongs to. Each named test links to its file at the head commit, and the head commit's check runs are linked when GitHub reports any; ledger evidence, which has no URL, is named by run ID and event sequence (DEC-0001). The outcome is printed as a second line after `Draft PR: …`, recorded as a new `acceptance_packet` ledger event, and the complete packet is archived in the run archive. A packet failure never changes the #17 outcome or the run's exit status. Implementation also fixes a ledger defect (R6): `ledger check` rejected every spec written in Spec Kit's numbered criterion format.

## Technical Context

**Language/Version**: Python ≥ 3.11 standard library only. `run.py` runs under `python3 -I -S` and imports `draft_pr`, which now imports `packet`, before any agent step.

**Primary Dependencies**: none. External tools are #17's resolved `git` and `gh` (≥ 2.48), with no new program.

**Storage**: ledger `events.jsonl` (new `acceptance_packet` kind and `verification.commit`), the archive file `<git common dir>/speckit-runs/<run>/acceptance-packet.md`, and the PR description on GitHub. No new authoritative store (FR-002).

**Testing**: `unittest`, offline. Fixtures are a real temporary Git repository with base and head commits, ledger events written through `ledger.append`, #17's scripted `_command` fake for `gh`, and an injected clock. `render` is tested directly.

**Target Platform**: the qualified 1.0 host (Linux, systemd user session, authenticated `gh`, GitHub).

**Project Type**: workflow tool inside the installed standard (`tools/spec_workflow/`).

**Performance Goals**: after #17, at most 2 PR reads, 1 + N check-run pages, 0 or 2 contents reads and 1 edit, all bounded by #17's 30 s per call. Local Git calls are proportional to the number of feature files read (≤ 10 plus review reports).

**Constraints**: inert rendering of all agent-written text; links built only by Ballast; GitHub body limit 65,536 characters; JSON-only OpenAPI; nothing waits for CI; no fetch, push or commit; no free text in the ledger.

**Scale/Scope**: `packet.py` about 700 lines (collect, render, OpenAPI diff, config, publish); about 40 lines in `draft_pr.py`, 10 in `run.py` and 120 in `ledger.py`; one new test file; documentation and ADR-0006.

No NEEDS CLARIFICATION remains. Three spec wordings are read explicitly, without changing behavior: AC-010 (R13), the CI edge case (R8) and AC-021's archive "link" (R15).

## Constitution Check

*Gate before Phase 0, re-checked after Phase 1. Result: **PASS** both times, no violations.*

| Principle | How the design holds it |
| --- | --- |
| 1. Projects own only their files (BL-INV-001) | `packet.py` installs with `tools/spec_workflow/` into the ignored `.ballast/`. The archive copy and ledger live in the Git common directory. The optional `[review]` table is in the project's own `ballast.toml`. No tracked file is written. |
| 2. Nothing executes from a writable checkout (BL-INV-002) | `packet.py` is imported with `draft_pr` at `run.py` startup, before any agent step, and acts only inside #17's checkpoint, which refuses on `BALLAST_TAMPERED` or the in-progress marker. It runs only #17's resolved `git` and `gh` through `_command`. Git reads use object IDs and plumbing on a private temporary index, so no worktree filter, hook or fsmonitor runs. Feature artifacts are data, never executed. |
| 3. Delegated authority (BL-INV-003) | No agent permission changes. GitHub writes stay with the launcher and use the command ADR-0003 already allows. Configuration comes from protected `ballast.toml`, so an agent cannot redirect the API comparison. |
| 4. A project picks a version, never a source (BL-INV-004) | Not touched: nothing is downloaded. |
| 5. Postconditions over exit codes (BL-INV-005) | `verified` requires recorded passing results bound to the head commit's fingerprint, spec and manifest. `published`/`updated` are recorded only after the edit call succeeds on an unchanged re-read body. Before writing, the body is checked to contain exactly one packet marker pair and unchanged bytes outside it. |
| 6. Portable, dependency-free tools | Standard library only. That is why OpenAPI is JSON-only (R10). |
| 7. Generic by default | Generic markers, wording and configuration; any GitHub repository. |
| 8. Executable evidence | Every FR-017 situation and every AC has a named test in [quickstart.md](quickstart.md), including hostile text, oversize, token leakage and failure paths. |
| 9. A provisional decision is never human approval (BL-INV-006) | Labels are copied from structured records only: `agent-provisional` from the decision log, `human` from human records and ledger gate events. The packet states it is not an approval. The finished text is checked with #27's `HUMAN_APPROVAL` guard outside inert data. |

## Architecture Boundaries

- **Affected areas**: the PR checkpoint `tools/spec_workflow/draft_pr.py` (calls the packet step, extends `Outcome`), a new trusted module `tools/spec_workflow/packet.py`, the ledger `tools/spec_workflow/ledger.py` (event kind, `oid` type, fingerprint functions, criteria parser) and its schema note, `run.py` (second output line), and operator documentation.
- **Contracts and data flow**: `run.py` → `draft_pr.checkpoint` → #17 outcome recorded → `packet.publish(work, outcome)` → `collect` (GitHub PR read, local Git at head, ledger, operator records, check runs, contents) → `render` (pure) → section edit → `acceptance_packet` event and archive file → second printed line. GitHub stays the source of truth for the PR, the feature artifacts at head for intent, the ledger for evidence, and the operator records for Autonomous decisions. The packet is a projection and can be regenerated from them (FR-002). See [contracts/checkpoint-integration.md](contracts/checkpoint-integration.md), [contracts/packet-format.md](contracts/packet-format.md), [contracts/ledger-acceptance-packet-event.md](contracts/ledger-acceptance-packet-event.md) and [data-model.md](data-model.md).
- **Architecture references**: [constitution](../../.specify/memory/constitution.md) BL-INV-002, -003, -006; [ADR-0003](../../docs/adr/0003-launcher-github-authority.md); [ADR-0004](../../docs/adr/0004-autonomous-provisional-decisions.md); [technical spec §91](../TECHNICAL-SPEC.md#91-v10-target); [ledger schema](../../tools/spec_workflow/ledger-schema.md); #17 [checkpoint contract](../17-draft-pr/contracts/pr-checkpoint.md); #27 [PR summary contract](../27-autonomous-core/contracts/pr-summary.md).
- **Proposed architecture decisions** (agent-provisional here; the merge approves them):
  1. **ADR-0006 Review packet reads under the launcher's GitHub authority.** This extends ADR-0003's fixed allowlist. It adds `gh api` reads of a single PR (already used for the re-read), of check runs for one commit, and of one configured file's contents at a commit. It adds `git` plumbing reads (`cat-file`, `ls-tree`, `rev-parse <commit>:<path>`, `read-tree`/`rm --cached`/`write-tree` on a private index). `gh pr edit --body-file -` now also rewrites a second Ballast-marked section, the acceptance packet, under the same re-read rule. No new program, no write other than the PR body, and no fetch.

## Repository Impact

| Path | Change |
| --- | --- |
| `tools/spec_workflow/packet.py` | New: `Sources`, `collect`, `render` (levels 1–4), `inert`, criteria evaluation, decisions, findings, checks, `ReviewConfig` parsing, OpenAPI comparison, UI states, section replace/append, `publish`, `PacketOutcome`, reasons and remedies, `format_line`, archive write. |
| `tools/spec_workflow/draft_pr.py` | Import `packet`; `Outcome.packet`; after `_record`, call `packet.publish` guarded, then record its event. Expose the hardened `git`/`gh` helpers to it. Extend the module docstring. |
| `tools/spec_workflow/run.py` | `_checkpoint` prints the packet line after the Draft PR line. Module docstring updated. |
| `tools/spec_workflow/ledger.py` | `oid` type; `acceptance_packet` in `FIELDS`, `ENUM_FIELDS`, `RUNNER_ONLY` and per-outcome required fields; `PACKET_REASONS`; `verification.commit?`; `spec_criteria` (used by `_approved_spec_ids`, R6 fix); `commit_tree`; `implementation_tree` seeded from `HEAD`; `_check` records `commit` on a clean checkout; `report` and `_text_report` show the latest packet. |
| `tools/spec_workflow/ledger-schema.md` | Document the kind, `oid`, `verification.commit` and the fingerprint change. |
| `tests/test_packet.py` | New: the [quickstart](quickstart.md) scenarios. |
| `tests/test_draft_pr.py` | The packet runs only after `created`/`reused`; a raising packet leaves the #17 outcome unchanged; argv sequence with the packet calls. |
| `tests/test_agent_run_ledger.py` | Event validation and report; `spec_criteria` on both forms; `commit_tree` and `implementation_tree` equality; `check` records `commit`. Existing `- **AC-` fixtures stay. |
| `tests/test_spec_workflow.py` | `run.py` prints both lines; a raising packet step keeps exit statuses 0, 1 and 130. |
| `templates/policies/spec-kit-workflow.md` | New subsection "Acceptance packet" under "Draft PR": what it shows, the five evidence states, `ballast ledger check` to record evidence, the `[review]` configuration (JSON OpenAPI, UI states), outcomes and remedies, "derived summary, not an approval" (FR-018). `ballast setup` refreshes the installed `docs/policies/` copy. |
| `README.md` | One sentence in the workflow section pointing to that subsection. |
| `docs/adr/0006-review-packet-reads.md` | New (ADR-0006). |

`tools/setup`, `tools/ballast`, `tools/cli.toml`, `claude-settings.json`, `agent.py`, `autonomy.py` (read through its existing public functions) and `artifacts.py` are unchanged.

## Feature Artifacts

```text
specs/19-acceptance-packet/
├── intent.md
├── spec.md
├── plan.md            # this file
├── research.md        # Phase 0 decisions R1–R18
├── data-model.md
├── contracts/
│   ├── checkpoint-integration.md
│   ├── packet-format.md
│   └── ledger-acceptance-packet-event.md
├── quickstart.md      # validation scenarios mapped to ACs
├── checklists/
├── autonomous/        # run record (rendered by the runner)
├── tasks.md           # next: speckit-tasks
├── decisions.md       # only if implementation discovers one
└── reviews/
```

## Review notes

- **Required reviews** (R1, [review matrix](../../docs/policies/workflow.md#review-triggers)): engineering review; security review, because the change touches GitHub authority, agent-written text rendered into the PR and credential leakage; test review; documentation review for the policy section and ADR-0006.
- **For the plan gate**: confirm R1 against R18, and accept ADR-0006 as an extension of ADR-0003 rather than a trust-model change. Also accept the `implementation_tree` change (R3): evidence recorded before the upgrade reads `stale` once.
- **Follow-up to propose in the PR, not in scope**: let `run-checks` record per-criterion evidence by running the manifest's mapped tests. Today Autonomous packets show `not run` until the operator runs `ballast ledger check` (R5). It would be a new command path, so R2 under FR-012.

## Complexity Tracking

No constitution violations.
