# Quickstart: validating the Autonomous PR completion policy

Every scenario runs offline. It uses the existing stand-in `gh` of `tests/test_autonomous_run.py` and `tests/test_autonomy.py` (data files and `FAIL_<argv>` markers in the fake's directory), extended so that `pr ready` flips the fake PR's `draft` to `false` and records the call. Contracts: [config-and-cli.md](contracts/config-and-cli.md), [output-and-ledger.md](contracts/output-and-ledger.md). Entities: [data-model.md](data-model.md).

## Prerequisites

```sh
uv sync --locked
```

## Fast gate

```sh
uv run --locked ruff check && uv run --locked ruff format --check
uv run --locked python -m unittest tests/test_*.py
```

Focused runs while implementing:

```sh
uv run --locked python -m unittest tests/test_completion.py
uv run --locked python -m unittest tests/test_autonomous_run.py tests/test_autonomy.py tests/test_agent_run_ledger.py
```

The full local gate (real `bwrap`, systemd, Codex and Spec Kit CLIs) is the same suite on the qualified host. Record it in the PR, or list it as unavailable.

## Scenarios and the acceptance criteria they prove

| Scenario | Setup | Expected | AC / SC |
| --- | --- | --- | --- |
| Eligible run is marked ready | `completion = "ready"`; R1; final acceptance and approved reconciliation recorded; checks pass; packet `published` with only `verified`; PR head = pushed commit | exactly one `pr ready 7 --repo acme/demo` call; last line `PR completion: ready-for-review #7 …`; one `pr_completion` event `ready` with the PR and commit; exit 0 | AC-001, AC-002, SC-001 |
| Later checkpoint after ready | the run above, then `ballast run checkpoint RUN` | `Draft PR: reused #7`; no `pr ready` call; PR stays non-draft | AC-003, FR-012 |
| Publish retry after ready | the run above, then `ballast run publish RUN` | refused as today (run is published); no forge call | AC-003 (R11) |
| Each condition alone | for each of conditions 1–12, operator records that meet every other condition and fail that one | no `pr ready` call; PR stays draft; line and `reasons` name exactly that code | AC-004, AC-005, AC-007, AC-009, SC-002 |
| Several conditions | R2 plus a `not run` criterion plus a material change | `reasons == ["risk", "packet", "material-change"]`, the printed reasons in that order | AC-006 |
| PR head moved | fake read-back `head.sha` ≠ pushed commit | `head-moved`; no `pr ready` call | AC-007 |
| Forge refuses | `FAIL_pr_ready` with `HTTP 403` | `PR completion: draft …: marking ready failed (gh-forbidden)`; `reasons == ["forge-failed"]`, `cause == "gh-forbidden"`; exit 0; run `published`; no block | AC-008, FR-011 |
| `gh` missing | no trusted `gh` at completion | `forge-failed` with `gh-missing` (or `pr-unreadable`); exit unchanged | AC-008 edge |
| Forge reports success but PR still draft | `pr ready` succeeds, read-back still `draft: true` | `forge-unverified` | FR-011, BL-INV-005 |
| Severity threshold | open `low` finding with no key → eligible; with `completion_max_severity = "none"` → `open-finding`; open `medium` (accepted-provisionally) with default → `open-finding` | as stated | AC-009 |
| No configuration | no `[autonomous]` table; same eligible records | stdout, `run.json` and ledger events byte-identical to a baseline captured with the feature disabled; no `pr ready`, no `pr_completion` | AC-010, SC-003 |
| `completion = "draft"` | same | identical to no configuration | AC-011 |
| Unknown value | `completion = "Ready"` | start warning; then as no configuration | FR-002 |
| Unknown threshold | `completion_max_severity = "medium"` | start warning; threshold `low` | FR-006 |
| Lowered or other modes | Chat run publish; human-gated run; Autonomous lowered by `continue` | no `pr ready` call in any argv; no completion line | AC-012, FR-014 |
| Checkout copy changed | trusted snapshot `draft`; an agent step's scenario rewrites `ballast.toml` in the checkout to `ready` before publication | effective policy stays `draft`; nothing reported; PR stays draft | AC-013, SC-004 |
| Agent claims eligibility | ineligible records (e.g. no final acceptance); agent writes drafts, `reviews/convergence.md` CONVERGED, a manifest and record edits claiming success | same reasons as without those writes | AC-014, SC-004 |
| Widening flag | no key or `draft`; `--completion ready` | refused before any agent step: no run record, no engine launch | AC-015 |
| Narrowing flag | `ready`; `--completion draft` | snapshot `completion: draft`, `completion_flag: draft`; line reason `the run's start flag chose draft`; `reasons == ["policy-draft"]` | AC-016 |
| Agent asks to mark ready | a decision draft declaring `mark-ready` | refused as never authorizable, as today (existing test kept) | AC-017 |
| Refresh keeps the flag | started with `--completion draft`; trusted config becomes `ready`; `resume --refresh-policy` | snapshot `completion` stays `draft`; without the flag it becomes `ready` | AC-018 |
| No approval wording | every reason text and both line forms | `autonomy.HUMAN_APPROVAL` finds no match | FR-017 |
| Ledger validation | `pr_completion` with `ready` + `reasons`, `draft` without `reasons`, unknown code, `cause` without `forge-failed`, non-runner source, `ledger record pr_completion` | each rejected | FR-010 |

## Manual check on a scratch repository (optional, operator only)

On a scratch GitHub repository with `[autonomous] completion = "ready"`, run an R1 Autonomous run to publication. The PR should become ready for review, and `ballast ledger report --run RUN_ID` should show `pr_completion ready`. This is not required for the gate. It needs a privileged action (a scratch repository), which this run does not take before merge.
