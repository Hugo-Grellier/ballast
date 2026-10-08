# Ballast 1.0 release checklist

Prepared by the driving agent for #24. First pass: 2026-10-07 on `69f5602` (0.9.0). Updated 2026-10-08 against `main` at `e7a4e8f` (release 0.10.0, standard pinned at v0.10.0). Merging, tagging `v1.0.0` and publishing the release are the operator's alone. Nothing below was done by an agent unless it says "done".

## 1. Blockers

No open defect blocks 1.0. One **release exception** remains for the operator to confirm at merge: gate item 6 is not met as worded. The operator decided on 2026-10-07 to accept the fallback as a qualified mechanism with a known model limit ([DEC-0003](decisions.md#dec-0003-release-gate-item-6-met-as-a-qualified-mechanism-with-a-known-model-limit)). The independent reviewer holds that this is an exception, not a demonstration. Everything else the first pass found is closed or decided:

| Item | State |
| --- | --- |
| [#111](https://github.com/Hugo-Grellier/ballast/issues/111) Chat publish had no acceptance packet | closed by [PR #119](https://github.com/Hugo-Grellier/ballast/pull/119); verified on pilot PR #9 ([qualification.md](qualification.md#final-pass-on-v0100)) |
| [#112](https://github.com/Hugo-Grellier/ballast/issues/112) Autonomous UI features blocked on operator-only tasks | closed by [PR #121](https://github.com/Hugo-Grellier/ballast/pull/121) (ADR-0017); verified on pilot PR #8 |
| [#114](https://github.com/Hugo-Grellier/ballast/issues/114) tamper recovery loop; uv `.venv` | closed by [PR #120](https://github.com/Hugo-Grellier/ballast/pull/120); re-drilled on a uv project |
| [#117](https://github.com/Hugo-Grellier/ballast/issues/117) per-criterion checks in Autonomous runs | closed by [PR #122](https://github.com/Hugo-Grellier/ballast/pull/122) (ADR-0018); verified on pilot PR #8 |
| Required checks on `main` | met: ruleset 24660402 (section 3) |
| ADR status | ADR-0001 to ADR-0016 accepted ([PR #116](https://github.com/Hugo-Grellier/ballast/pull/116) for 0006 to 0016); ADR-0017 and ADR-0018 accepted by the merges of #121 and #122 (section 2) |
| Gate item 6, free fallback | **accepted known limit** (operator decision 2026-10-07, [DEC-0003](decisions.md#dec-0003-release-gate-item-6-met-as-a-qualified-mechanism-with-a-known-model-limit); this narrows how the gate is read, so confirm it at merge): the mechanism works live (quota recognized, refusal or selection recorded, confined attempt, ledger evidence); the 4B local model `qwen3:4b-16k` wrote no usable artifact; the fallback is refused while the operator's `~/.agents/skills` is not empty ([drill D6](qualification.md#ac-002-recovery-drills)) |
| [#113](https://github.com/Hugo-Grellier/ballast/issues/113) Chat step friction, PR titles | open, out of 1.0 (operator, 2026-10-07) |
| [#124](https://github.com/Hugo-Grellier/ballast/issues/124) tasks name test commands outside the allowlist (one safe block in the LoreForge pilot) | open, no milestone; not a 1.0 blocker unless the operator decides otherwise |
| #22 SC-004 local reproduction | the pilot project's demo script failed on this host; Ballast behaved as specified; noted, not a Ballast blocker |
| [#115](https://github.com/Hugo-Grellier/ballast/pull/115) (this evidence) | open: operator review and merge |

## 2. Milestone v1.0: issues, specs and decisions

Read with `gh api "repos/Hugo-Grellier/ballast/issues?milestone=*&state=all&per_page=100"` on 2026-10-07, and the issue states again on 2026-10-08.

| Issue | State | Spec | Decision records |
| --- | --- | --- | --- |
| [#11](https://github.com/Hugo-Grellier/ballast/issues/11) Epic: request-to-PR workflow | open (closes with this checklist) | [roadmap](../../docs/plans/2026-10-02-product-roadmap.md), [TECHNICAL-SPEC §91](../TECHNICAL-SPEC.md#91-v10-target) | n/a |
| [#12](https://github.com/Hugo-Grellier/ballast/issues/12) one-command install and doctor | closed | [12-cli-install-doctor](../12-cli-install-doctor/spec.md) | [ADR-0001](../../docs/adr/0001-cli-release-asset-install.md), [ADR-0002](../../docs/adr/0002-cli-standard-manifest.md) |
| [#13](https://github.com/Hugo-Grellier/ballast/issues/13) adaptive init | closed | [13-adaptive-init](../13-adaptive-init/spec.md) | [ADR-0012](../../docs/adr/0012-init-before-pin.md) |
| [#14](https://github.com/Hugo-Grellier/ballast/issues/14) recoverable install | closed | [14-recoverable-install](../14-recoverable-install/spec.md) | [ADR-0007](../../docs/adr/0007-recoverable-installation.md), [ADR-0008](../../docs/adr/0008-verified-cache-and-update-preview.md) |
| [#15](https://github.com/Hugo-Grellier/ballast/issues/15) worktree setup | closed | [15-worktree-setup](../15-worktree-setup/spec.md) | [ADR-0011](../../docs/adr/0011-worktree-preparation.md) |
| [#16](https://github.com/Hugo-Grellier/ballast/issues/16) discovery brief | closed | [16-discovery-brief](../16-discovery-brief/spec.md) | n/a |
| [#17](https://github.com/Hugo-Grellier/ballast/issues/17) Draft PR | closed | [17-draft-pr](../17-draft-pr/spec.md) | [ADR-0003](../../docs/adr/0003-launcher-github-authority.md) |
| [#18](https://github.com/Hugo-Grellier/ballast/issues/18) branch sync | closed | [18-branch-sync](../18-branch-sync/spec.md) | [ADR-0005](../../docs/adr/0005-launcher-branch-synchronization.md) |
| [#19](https://github.com/Hugo-Grellier/ballast/issues/19) acceptance packet | closed | [19-acceptance-packet](../19-acceptance-packet/spec.md) | [ADR-0006](../../docs/adr/0006-review-packet-reads.md) |
| [#20](https://github.com/Hugo-Grellier/ballast/issues/20) Chat mode | closed | [20-chat-mode](../20-chat-mode/spec.md) | [ADR-0009](../../docs/adr/0009-chat-mode-operator-driven-steps.md) |
| [#21](https://github.com/Hugo-Grellier/ballast/issues/21) Autonomous reviewed PR | closed | [21-autonomous-reviewed-pr](../21-autonomous-reviewed-pr/spec.md) | [ADR-0010](../../docs/adr/0010-autonomous-resume-and-bounded-recovery.md) |
| [#22](https://github.com/Hugo-Grellier/ballast/issues/22) UI demo | closed | [22-ui-demo](../22-ui-demo/spec.md) | [ADR-0013](../../docs/adr/0013-demo-capture-dispatch.md) |
| [#23](https://github.com/Hugo-Grellier/ballast/issues/23) free fallback | closed | [23-free-fallback](../23-free-fallback/spec.md) | [ADR-0014](../../docs/adr/0014-local-zero-cost-fallback.md) |
| [#27](https://github.com/Hugo-Grellier/ballast/issues/27) Autonomous core | closed | [27-autonomous-core](../27-autonomous-core/spec.md) | [ADR-0004](../../docs/adr/0004-autonomous-provisional-decisions.md) |
| [#55](https://github.com/Hugo-Grellier/ballast/issues/55) setup-recorded trust | closed | [55-setup-trust](../55-setup-trust/spec.md) | [ADR-0015](../../docs/adr/0015-setup-recorded-trust-baseline.md) |
| [#58](https://github.com/Hugo-Grellier/ballast/issues/58), [#65](https://github.com/Hugo-Grellier/ballast/issues/65), [#66](https://github.com/Hugo-Grellier/ballast/issues/66), [#74](https://github.com/Hugo-Grellier/ballast/issues/74), [#76](https://github.com/Hugo-Grellier/ballast/issues/76), [#79](https://github.com/Hugo-Grellier/ballast/issues/79), [#81](https://github.com/Hugo-Grellier/ballast/issues/81), [#83](https://github.com/Hugo-Grellier/ballast/issues/83), [#90](https://github.com/Hugo-Grellier/ballast/issues/90), [#94](https://github.com/Hugo-Grellier/ballast/issues/94), [#95](https://github.com/Hugo-Grellier/ballast/issues/95), [#97](https://github.com/Hugo-Grellier/ballast/issues/97) | closed | fixes (bug workflow) | [ADR-0016](../../docs/adr/0016-privileged-action-kinds-and-policy-refresh.md) (#95) |
| [#24](https://github.com/Hugo-Grellier/ballast/issues/24) this qualification | open | [24-v1-qualification](spec.md) | n/a |
| [#111](https://github.com/Hugo-Grellier/ballast/issues/111), [#112](https://github.com/Hugo-Grellier/ballast/issues/112), [#114](https://github.com/Hugo-Grellier/ballast/issues/114) (filed by this qualification), [#117](https://github.com/Hugo-Grellier/ballast/issues/117) | closed | fixes: PR #119, #121, #120, #122 | [ADR-0017](../../docs/adr/0017-deferred-operator-tasks-and-unmapped-criteria.md) (#112), [ADR-0018](../../docs/adr/0018-runner-recorded-acceptance-checks.md) (#117) |

**ADR status (read 2026-10-08):** ADR-0001 to ADR-0016 read `accepted`; ADR-0006 to ADR-0016 were accepted by the operator for the 1.0 release in PR #116. ADR-0017 and ADR-0018 still read `proposed ... accepted when the PR merges`, and their PRs (#121, #122) are merged, so they are accepted by merge as the operator decided; editing their status line is optional.

## 3. GitHub required checks

Read on 2026-10-08:

```text
$ gh api repos/Hugo-Grellier/ballast/rulesets/24660402
id 24660402, name "main: required checks", enforcement "active", bypass_actors [],
conditions.ref_name.include ["~DEFAULT_BRANCH"],
rules: deletion; non_fast_forward; required_status_checks
  [lint, test, dogfood, PR title] (strict policy false)
$ gh api repos/Hugo-Grellier/ballast/rules/branches/main
types: deletion, non_fast_forward, required_status_checks
```

**Met.** Roadmap gate item 5 ("GitHub branch protection or rulesets enforce required checks at merge") holds: the four checks CI and the PR-title workflow report must pass to merge into the default branch, with no bypass actor. The operator created the ruleset (R2); the agent only read it.

## 4. Local gate on the qualified host

Done. 1643 tests at `e764321` (release 0.10.0; the code is the same as `e7a4e8f`), OK, 0 skipped; ruff check and format clean. See [qualification.md](qualification.md#full-local-gate-final).

## 5. Release steps (operator only)

1. Review and merge [#115](https://github.com/Hugo-Grellier/ballast/pull/115) (it closes #24), then close Epic #11.
2. If anything other than #115 merges after `e7a4e8f`, re-run the full local gate (section 4) on the commit to be released.
3. Release v1.0.0 per README "Releases": add a `Release-As: 1.0.0` footer, or use the repository's chosen mechanism, then merge the Release Please PR. That tags `v1.0.0` and publishes the release and the CLI asset.
4. Optional cleanup, which the agent may not do:
   - the private repository `Hugo-Grellier/ballast-qual-blank-20261007` with its drill branch `main-next`, PRs #3, #4, #8 and #9 and Issues #1, #2 and #5 to #7;
   - LoreForge Issues #126 and #128, and Draft PRs #127 and #129. #127's `health.spec.ts` is not wired into Playwright; see the PR comment.
   - LoreForge's adoption PR #124 (`chore/adopt-ballast`) now pins v0.10.0 (commit `4b14fe9`).
