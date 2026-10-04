# Issue #12: feat(cli): install Ballast in one command and diagnose readiness

Parent Epic: #11
Milestone: v1.0
Source: https://github.com/Hugo-Grellier/ballast/blob/main/docs/plans/2026-10-02-product-roadmap.md and https://github.com/Hugo-Grellier/ballast/blob/main/specs/TECHNICAL-SPEC.md#91-v10-target.
Scope gate: cohesive feature or bounded release qualification; this issue owns one independently reviewable outcome.
Main outcome: A new operator can obtain the pinned Ballast CLI without copying a script from a checkout and can see exact prerequisites before running a workflow.
In scope: Provide one supported CLI distribution path and a read-only `ballast doctor` that checks the installed pin, required tools, GitHub access, Linux/systemd support and trust state.
Out of scope: Project-specific bootstrap, installing a feature's dependencies, and support for other host platforms.
Risk: R2 — changes distribution and the trusted operator entry point.
Blocked by: none.

## Acceptance criteria

- [ ] A fresh qualified host installs and invokes Ballast with one documented command; a project still selects a version, never an executable source.
- [ ] `ballast doctor` distinguishes missing prerequisites, an unfetched pin, invalid install, missing trust, and unavailable GitHub/systemd with actionable remedies.
- [ ] Inspection never executes code from an untrusted project checkout; tests cover clean, missing and tampered states.

Prepare the feature-local spec and plan through the normal scope/intent workflow before implementation. R2 work requires the project's explicit human approval before crossing the risky boundary.


## Comment by Hugo-Grellier (2026-10-03T14:35:12Z)

Classification: feature (cohesive leaf of Epic #11, child outcome 1).
Acceptance grouping: the three acceptance criteria in #12 form one group owned by this issue.
Accepted links: docs/plans/2026-10-02-product-roadmap.md; specs/TECHNICAL-SPEC.md#91-v10-target.
Scope gate: cohesive feature; one independently reviewable outcome, no further decomposition.
Main outcome: A new operator can obtain the pinned Ballast CLI without copying a script from a checkout and can see exact prerequisites before running a workflow.
In scope: One supported CLI distribution path and a read-only `ballast doctor` that checks the installed pin, required tools, GitHub access, Linux/systemd support and trust state.
Out of scope: Project-specific bootstrap, installing a feature's dependencies, support for other host platforms.
Risk: R2

<!-- ballast-intake: issue=#12; scope=feature -->

