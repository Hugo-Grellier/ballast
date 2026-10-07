# Ballast 1.0 release checklist

Prepared 2026-10-07 by the driving agent for #24, against `main` at `69f5602` (release 0.9.0). Merging, tagging `v1.0.0` and publishing the release are the operator's alone; nothing below was done by an agent unless it says "done".

## 1. Open blockers

| Item | State | Owner |
| --- | --- | --- |
| [#111](https://github.com/Hugo-Grellier/ballast/issues/111) Chat publish has no acceptance packet; `checkpoint` refuses Chat runs | open, milestone v1.0 | fix before 1.0, or the operator accepts it as a known gap |
| [#112](https://github.com/Hugo-Grellier/ballast/issues/112) Autonomous UI features block on operator-only tasks; packets carry no per-criterion evidence | open, milestone v1.0 | fix before 1.0, or the operator accepts it as a known gap |
| [#114](https://github.com/Hugo-Grellier/ballast/issues/114) A tamper block has no working recovery path; uv projects hit it on their first agent test run | open, milestone v1.0 | fix before 1.0, or the operator accepts it as a known gap |
| Roadmap gate item 6 (free fallback) has no live completion on the qualified host: with the operator's home the fallback is refused (`~/.agents/skills` not empty), and the selected `qwen3:4b-16k` did not write the step's artifact ([qualification.md D6](qualification.md#ac-002-recovery-drills)) | qualified by #23 as "completes or is refused with a recorded cause" | operator decides whether that is enough for 1.0 |
| #22 SC-004: the packet's reproduce command failed on this host because of the pilot project's script ([qualification.md](qualification.md#ui-demo-on-pr-3-22-sc-001-and-sc-004)) | Ballast behaved as specified | operator notes it, or reruns with a portable scenario |
| Required checks are not enforced on `main` (section 3) | not configured | operator (R2) |
| [#115](https://github.com/Hugo-Grellier/ballast/pull/115) (#24 evidence) | open | operator review and merge |

[#113](https://github.com/Hugo-Grellier/ballast/issues/113) (Chat step friction) is filed without a milestone. Its item 2, Chat has no `discover` step and cannot read the Issue, touches roadmap gate item 2. The operator may move it to v1.0.

## 2. Milestone v1.0: issues, specs and decisions

Read with `gh api "repos/Hugo-Grellier/ballast/issues?milestone=*&state=all&per_page=100"` on 2026-10-07.

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
| [#111](https://github.com/Hugo-Grellier/ballast/issues/111), [#112](https://github.com/Hugo-Grellier/ballast/issues/112), [#114](https://github.com/Hugo-Grellier/ballast/issues/114) | open | filed from this qualification | n/a |

**ADR status (operator review):** ADR-0001 to ADR-0005 read `accepted`. ADR-0006 to ADR-0016 still read `proposed` or `Proposed` with "accepted when its PR merges", although every one of those PRs has merged. Before tagging, the operator should either accept them, which is a one-line status edit per ADR in a docs PR, or record which of them stay open.

## 3. GitHub required checks

Read on 2026-10-07:

```text
$ gh api repos/Hugo-Grellier/ballast/rulesets
[]
$ gh api repos/Hugo-Grellier/ballast/rules/branches/main
[]
$ gh api repos/Hugo-Grellier/ballast/branches/main/protection
{"message":"Branch not protected", ... "status":"404"}
```

**Not met.** Roadmap gate item 5 requires that "GitHub branch protection or rulesets enforce required checks at merge". `main` has no ruleset and no branch protection, so nothing GitHub-side enforces the checks. The check runs on `main` at `69f5602` are `lint`, `test`, `dogfood` (workflow `CI`), `release-please` and `publish-cli`. `PR title` runs on pull requests.

**Operator action (R2, not done by the agent):** add a ruleset for the default branch that requires the status checks `lint`, `test`, `dogfood` and `PR title`, requires a pull request before merging, and blocks force pushes and deletion. Then re-read it with `gh api repos/Hugo-Grellier/ballast/rules/branches/main` and paste the output here. Decide whether the Release Please bot needs a bypass for its release PR (it runs CI through `RELEASE_PLEASE_TOKEN`, so the checks run on it).

## 4. Local gate on the qualified host

Done. See [qualification.md §AC-003](qualification.md#ac-003-full-local-gate-on-the-qualified-host): 1591 tests, 0 skipped, 0 failed; ruff check and format clean.

## 5. Release steps (operator only)

1. Resolve or explicitly accept #111, #112 and #114 (section 1), and decide on #113 item 2.
2. Configure the ruleset (section 3).
3. Settle the ADR statuses (section 2).
4. Review and merge this PR.
5. Re-run the full local gate (§4) on the commit to be released if anything merged after `69f5602`.
6. Release Please: release v1.0.0 per README "Releases" by adding a `Release-As: 1.0.0` footer or the repository's chosen mechanism, then merge the release PR. That tags `v1.0.0` and publishes the release and the CLI asset.
7. Close #24 and Epic #11.
8. Optional clean-up of the pilot resources, which the agent may not delete: the private repository `Hugo-Grellier/ballast-qual-blank-20261007` with its drill branch `main-next`, and the LoreForge pilot PR and Issue #126 if they are not wanted.
