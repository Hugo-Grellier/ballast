# Review: implementation (engineering)

- Role: engineering and architecture reviewer
- Agent/model: claude/claude-opus-5-5 (the driving agent, plus the independent fresh-context pass recorded in the [security review](implementation-security.md)); reduced independence
- Base: `1ce1f9a..HEAD`
- Artifacts: [spec.md](../spec.md), [plan.md](../plan.md), [research.md](../research.md), [contracts/](../contracts/), ADR-0007, ADR-0011, `docs/policies/engineering.md`
- Verdict: approved (after the fixes below)

## What was examined

- **Requirement coverage.** FR-001 to FR-015 against the code paths: CLI trigger (`before_launcher`, `needs_installation`, `prepare`), declaration (`Declarations.prepare`), local-only attempt (`Setup.prepare`, `hold`, `settled`, `candidates`, `copy_candidate`, `mismatch`, `fill_from_candidates`, `check_unchanged`), recovery (`recover` with `mode`), launcher messages and refusals. Mapping in [quickstart.md](../quickstart.md).
- **Architecture.** Preparation is ADR-0007's attempt with another `fill` function: one stage, journal, switch, verification and recovery implementation; the CLI decides whether, the pinned setup decides how (ADR-0002). ADR-0011 records the extension and stays proposed until merge.
- **Source authority.** Installation records stay in operator state, written only by `tools/setup`; the CLI reads the manifest as data; no second store.
- **Partial failure and concurrency.** Kill points staging (mid-copy, after copy), switching, mid-rename and committed; a committed preparation at another fingerprint is rolled back; ten concurrent worktrees on two pins, 20 times; two commands in one worktree.
- **Compatibility.** Old CLI with this standard: launcher refusal naming setup. This CLI with an old standard: CLI refusal naming setup for run/ledger/intake/trust/discard-runs. Old records without `executable` stay valid for `ballast setup`'s copy and are never a preparation source.

## Findings

| ID | Class | Severity | Location | Evidence | Required action |
|---|---|---|---|---|---|
| ENG-001 | spec ambiguity | medium | launcher `main`; prepare step 4; `Setup.main` | An `in-progress` marker in an uninstalled checkout sent the operator in a circle: preparation and setup named `discard-runs`, which refused naming setup. | Let `discard-runs` clear the marker on an uninstalled checkout; record the FR-012 exception (DEC-0001); test. |
| ENG-002 | spec violation | low | `tools/ballast` `main` | The contract's CLI refusal for `trust`/`discard-runs` on an uninstalled checkout pinned to a version without `[setup] prepare` was not implemented (the old launcher printed usage text). | Implement; test. |
| ENG-003 | implementation bug | low | `copy_verified` | Local state was skipped by file name at any depth (`runs`, `.cache`, `.backup`), not by path. Fails closed. | Skip by path. |
| ENG-004 | implementation bug | medium | `Setup.lock` / `prepare` | Found by the full suite (1 of 903): another preparation's brief shared-lock check made a concurrent preparation's exclusive attempt fail with "a `ballast run` … is running", so both first commands could refuse. Also, once the first command's launcher held the lock, the second refused for the whole run (plan review F-001 only half met). | Check for a current installation under the shared lock first; retry the exclusive lock up to 2 s before refusing; tests. |
| ENG-005 | implementation bug | low | `candidates()` | Every uninstalled sibling worktree was printed as `skipped …: it has no installation record`, and counted, although a checkout without a record holds no candidate (FR-003). | Yield only checkouts with a record or kept copy; contract and data model updated. |
| ENG-006 | implementation bug | low | `discard_work` | A refused preparation left an empty `.ballast/` in the worktree ("leaves the worktree as it found it"). | Remove `.ballast/` when the attempt created it and it is empty. |
| ENG-007 | implementation bug | info | `tools/ballast` `prepare` | A prepare child killed by a signal returned a negative code to `sys.exit`. | Map to 1. |
| ENG-008 | architecture issue | info | `Setup.lock` from a source's side | While a worktree copies from the primary, `ballast setup` in the primary refuses naming a running `run`/`ledger`/`intake`; the action (wait, rerun) is right, the named cause is approximate. | Accept; the copy takes well under a second. |
| ENG-009 | spec ambiguity | info | `recover` in an older pinned version | Moving the pin back to a version before this feature while a committed `prepare` journal exists lets that older setup finish it and create the constitution. Running an older setup over a newer journal is outside the guarantees (as in feature 14 SEC-003). | Accept; documented here. |
| ENG-010 | implementation bug | low | `copy_candidate` lint | The Autonomous run's partial implementation failed `ruff check` (complexity, return count). | Split `mismatch` and `_share`, `_kept_record`. |

## Resolution

- ENG-001: fixed in `980511e`; DEC-0001; test `TrustedLauncherTests.test_unfinished_step_is_discarded_on_an_uninstalled_checkout` failed before.
- ENG-002, ENG-007: fixed in `980511e` (`before_launcher`, `refuse_uninstalled`); `PrepareTriggerTests.test_version_without_declaration` extended and failed before.
- ENG-003: fixed in `de68125` (path-based skip in `_copy_node`).
- ENG-004: fixed in `dedc146` (`settled`, launcher-held case) and `1c82a1a` (`hold` retry); `PrepareConcurrencyTests.test_one_preparation_per_worktree` covers both and failed before each.
- ENG-005, ENG-006: fixed in `dedc146`; the AC-008 to AC-011 tests assert exact output and no leftover `.ballast/`, and failed before.
- ENG-010: fixed in `dedc146`.
- ENG-008, ENG-009: accepted; listed for the merge review.
