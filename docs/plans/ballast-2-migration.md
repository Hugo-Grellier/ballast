# Migration, v1 retirement and 2.0 release — #180

Parent: #174. Blocked by #179 (optional Orca adapter, in progress separately). Build
with ordinary worktree/agent development, not Ballast 1.x or Spec Kit. This is a
plan, not completed proof. Merge and release remain human decisions.

## Operator decisions (2026-10-15, conversation)

- V1 tests and tools are not needed for 2.0. Done in #185: deleted from `main`, kept at
  the `v1.x` tags; the release job no longer attaches the `ballast` CLI.
- Release PR #183 (1.2.0) is closed. The next release is 2.0.0.
- This repository fully switches: remove `ballast.toml` and `.specify/`, rewrite
  `AGENTS.md` for 2.0, and state the 2.0 invariants in an ADR that supersedes the v1
  ADRs. `specs/` stays as the v1 historical record.
- Consumers keep the generic policies and review skills as copy-once content,
  cleaned of v1 references (option B). Spec Kit and v1-only content are removed.
- Orca stays in 2.0: the release waits for #179. This branch does not touch Orca
  files (`docs/orca-execution.md`, any Orca tool) to avoid conflicting with it.

## Waves

1. **Standard content (`templates/`).**
   - Delete `spec-kit/`, `init/`, `github/workflows/ballast-demo.yml`, the
     `spec-kit-workflow` and `model-routing` policies, and the `ballast-feature-intake`,
     `ballast-spec-reconciliation` and `ballast-model-routing` skills. The 2.0
     replacements are `docs/issue-workflow.md` and `docs/model-routing.md`.
   - Rewrite `policies/workflow.md` to risk classes and the review matrix only (no
     run modes), `policies/issue-tracker.md` to point to the issue workflow, and the
     constitution link in `policies/engineering.md` to the project's invariants.
   - Rewrite `templates/AGENTS.md` as the 2.0 entry point and align the PR template
     with this repository's 2.0 one.
   - Drop `tools/spec-kit/preset.patch` and the Spec Kit notices that no longer apply.
2. **This repository.**
   - Remove `ballast.toml`, `.specify/`, `docs/policies/project/` and the installed-path
     block in `.gitignore`.
   - Rewrite `AGENTS.md`. Its gate, R2 boundaries and invariants come from
     `docs/policies/project/` and the constitution, restated for 2.0. Generic rules
     link to `templates/policies/` (the source, not a copy).
3. **Authority.**
   - ADR-0024 accepts ADR-0023, supersedes the v1 runner ADRs (0001–0021) and replaces
     the constitution with the 2.0 invariants.
   - Each superseded ADR gets one status line naming ADR-0024. Their text is unchanged.
   - `specs/PRODUCT-SPEC.md` and `specs/TECHNICAL-SPEC.md` get a banner: v1.x record;
     the 2.0 authority is the ADRs and `docs/`.
4. **Consumers.** `docs/migration.md`:
   - what 2.0 is and what it no longer guarantees;
   - how to adopt: copy the templates and use the Ballast checkout's helpers;
   - how to stay on or roll back to v1: pin `ref = "v1.1.0"`, the v1.1.0 CLI asset,
     the v1.1.0 README;
   - what to delete when leaving v1.

   The README becomes the 2.0 overview. The v1 usage section moves behind a link to
   the v1.1.0 README.
5. **Issues.** Apply the triage table below after merge approval, with comments that
   link this PR.
6. **Release (after #179).**
   - `docs/evidence/release-2.0.md`: standalone (#177), queue/recovery (#178) and
     Orca (#179) evidence, limits, remaining gaps, and the throughput/quality
     tradeoffs observed.
   - The `feat!` title and `BREAKING CHANGE` footer make Release Please propose
     2.0.0. The operator merges that release PR only after #179 and the evidence.

## Removed guarantees (for ADR-0024 and the migration guide)

| v1 guarantee | 2.0 |
| --- | --- |
| Trusted launcher: pinned, verified code; nothing runs from a writable checkout (BL-INV-002, ADR-0015/0021) | None. Helpers run from an operator-selected Ballast checkout under the caller's native permissions |
| Protected inputs and tamper markers fail closed (BL-INV-003) | None. Workers are confined by the native CLI sandbox. Coordinator records are cooperative, not tamper-proof |
| Pinned install into ignored paths, project owns only its files (BL-INV-001, ADR-0001/0002/0007/0008) | Copy-once templates. No installer and no `ballast.toml` |
| Postcondition-checked phases and run ledger (BL-INV-005) | Phase records on the issue and PR evidence. Settlement needs backend terminal evidence. Unknown stays unknown |
| Human-gated, Chat and Autonomous runs with gates and relays (BL-INV-006, ADR-0004/0009/0010/0021) | Coordinator plus independent review. Human merge stays the approval. No agent merges |

## Issue triage (applied after merge approval)

| Issue | Action | Reason |
| --- | --- | --- |
| #149 one Issue in, one PR out | Superseded by #174 | 2.0 epic owns the outcome |
| #136, PR #172 specify-cli pin | Close | Spec Kit removed |
| #137 Dependabot Ballast pin | Close | No `ballast.toml` in 2.0 |
| #138 Haiku/Sonnet routing | Close | v1 routing profiles; 2.0 routing is `docs/model-routing.md` |
| #139 context budget/compaction | Close | v1 runner feature |
| #143 Autonomous merge | Close | Outside 2.0 scope (#174) |
| #151 clarify decides | Superseded | Issue workflow asks only consequential questions |
| #152 intake/decompose | Superseded | Issue workflow scope and decomposition |
| #153 token budget | Superseded by #178 | Attempt limits and token totals |
| #154 usage-limit resume | Superseded by #178 | Quota pause with explicit window |
| #158 lean Autonomous path | Superseded | 2.0 is the lean path |
| #159 per-step tokens/time | Superseded by #178 | `coordinate status` |
| #168 parallel dispatch | Superseded by #178 | Bounded queue |
| #160, #164–#167, #171 v1 tests/CI | Close | v1 suite removed (#185) |
| PR #173 pin v1.1.0 | Close | `ballast.toml` removed |
| #170 duplicate ADR numbers | Retain | Still true in `docs/adr/` |
| PR #144 setup-uv bump | Retain | CI still uses it |

## Acceptance mapping

| #180 criterion | Evidence |
| --- | --- |
| Active instructions use v2; standalone supported; Orca optional | Waves 1–2; a grep shows no active `ballast run`/Spec Kit instruction outside `specs/` and the superseded ADRs |
| Authority accounts for replaced v1 decisions | Wave 3 |
| Migration, removed guarantees, rollback/pinning | Wave 4, table above |
| Related issues retained/superseded/closed | Wave 5 |
| CI deterministic; evidence at submitted revision | `ci.yml` unchanged (lint, tests); checks recorded in the PR |
| Integration evidence | Wave 6 (after #179) |
| Limits, gaps, tradeoffs | Wave 6 |
| No merge, destructive cleanup or release without approval | Issue actions and release wait for the operator |
