# Issue #17: feat(github): create or reuse one issue-linked Draft PR

Parent Epic: #11
Milestone: v1.0
Source: https://github.com/Hugo-Grellier/ballast/blob/main/docs/plans/2026-10-02-product-roadmap.md and https://github.com/Hugo-Grellier/ballast/blob/main/specs/TECHNICAL-SPEC.md#91-v10-target.
Originating LoreForge issue: https://github.com/Hugo-Grellier/LoreForge/issues/111

Scope gate: cohesive feature or bounded release qualification; this issue owns one independently reviewable outcome.
Main outcome: Issue-linked implementation becomes visible in exactly one Draft PR after the first meaningful pushed commit.
In scope: Resolve one issue/branch/base/PR identity, defer until a remote diff exists, create or reuse the Draft PR, preserve issue association, and retry observable GitHub failures. Adapt the generic behavior requested in LoreForge #111.
Out of scope: Intake/decomposition, automatic merge, premature issue closure, and per-agent PR implementations.
Risk: R2 — trusted operator-side Git and GitHub mutation.
Blocked by: none.

## Acceptance criteria

- [ ] First eligible pushed implementation diff creates one Draft PR with the correct base, issue reference, template and scope/status summary.
- [ ] Resume, retry, agent switch and a manually opened matching PR reuse the same PR; no PR is attempted before a remote diff exists.
- [ ] Auth/network/API failures are explicit and retryable without claiming success or discarding local work.
- [ ] Ready-for-review and merge obey the chosen workflow mode and human merge rule.

Prepare the feature-local spec and plan through the normal scope/intent workflow before implementation. R2 work requires the project's explicit human approval before crossing the risky boundary.

