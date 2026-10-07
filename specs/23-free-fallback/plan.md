# Implementation Plan: Qualify one zero-cost provider fallback

**Branch**: `feat/23-free-fallback` | **Date**: 2026-10-06 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/23-free-fallback/spec.md` (intent agent-provisional, PD-0007, digest in [intent.md](intent.md))

**Risk**: R2. The plan adds an execution backend, changes what the wrapper executes after a failed step, and sends repository content to a second model under the headless permission model. This is an Autonomous run: every design decision below is agent-provisional, not human-approved, and merging the PR is the single human approval (BL-INV-006).

## Summary

When a headless step's primary agent fails because its quota is exhausted, its provider is unreachable, or its CLI is missing, the wrapper (`agent.py`) may run the same step once more on Codex CLI's local-provider mode against the operator's Ollama model on loopback. This happens only if the operator opted in for the run, the failure came on the step's first attempt (never after a draft retry, DEC-0001), and the failed attempt changed nothing. The opt-in is `ballast run start|resume --local-fallback MODEL|off`, stored in the run's operator directory, where no agent can write.

Before any prompt is sent, these checks run in order:

- the primary left the tree, reviews, drafts, git-ignored paths and refs unchanged, and all of them could be checked;
- the probes use only Ollama's fixed default endpoint `127.0.0.1:11434`, the one Codex uses, and no endpoint override survives in the environment;
- the server answers and is Ollama 0.13.4 or newer;
- the model is installed and is neither remote nor cloud;
- Codex supports `--oss`;
- the model's served context is at least 16384 tokens;
- Codex's sandbox starts under the step's own confinement;
- no Codex configuration layer outside the fallback's private, empty `CODEX_HOME` exists, and the user's `~/.agents/skills` is empty or absent;
- the built argv and environment equal, token for token, the one the wrapper builds from the canonical headless Codex step's profile.

Any failed or unknown check refuses with one of five reasons: `changed-state`, `privacy-exclusion`, `unknown-free-status`, `incompatible-capability` or `permission-mismatch`. The network and subprocess checks, including the served-context check, share a 10 s budget.

The fallback reuses the primary attempt's code path: scope, subreaper, bubblewrap for Autonomous steps, protected-state and tamper checks, draft snapshotting. It counts as an agent step and is never retried. The wrapper records the failed primary, the decision and the fallback attempt with its usage (`codex exec --json`) as additive `route` and `usage` ledger events and `steps.jsonl` fields. A review completed by the fallback is never counted as cross-provider: in Autonomous runs through the step entry, in human-gated runs through the ledger report. A pilot on the operator host runs first and goes into `evaluation.md`. On this host Codex's sandbox is already known not to nest inside Ballast's bubblewrap (DEC-0004), so Autonomous steps are expected to refuse the fallback as an incompatible capability, while human-gated steps can use it. Decisions are in [research.md](research.md) (R1 to R10).

## Technical Context

**Language/Version**: Python ≥ 3.11 standard library only, run under `python3 -I -S` (workflow tools) and the wrapper's existing interpreter flags.

**Primary Dependencies**: None new in Python. Runtime, optional and operator-installed: the Codex CLI with `--oss`/`--local-provider`/`--json`, and Ollama serving on loopback. The model must be served with a context of at least 16384 tokens (research R5 check 11a). Neither is installed or downloaded by Ballast. `urllib.request` for three loopback probe requests.

**Storage**: Files only. New `fallback.json` in the run's operator directory (`$XDG_STATE_HOME/ballast/<key>/runs/<run>/`); new `usage.json` in a fallback step's log directory; optional fields in `steps.jsonl` and the step's `meta.json`; additive `route` enum values and fields in the ledger (schema stays 1). See [data-model.md](data-model.md).

**Testing**: `unittest`, offline: a loopback stub Ollama recording every request, fake `claude`/`codex` executables recording argv/env/prompt, the existing wrapper test harness with real `steps.jsonl` and ledger files. The tests that need real systemd, `bwrap` and Codex run in the full local gate only (CI skips them). Pilot on the operator host. See [quickstart.md](quickstart.md).

**Target Platform**: The qualified 1.0 host: Linux with a systemd user session.

**Project Type**: The standard's workflow tools (`tools/spec_workflow/`) behind the `ballast` launcher.

**Performance Goals**: Probes finish in under 10 s before a fallback, or refuse. While the setting is on, each step adds one `lstat` walk of the worktree's ignored paths before and after the primary attempt, capped at 200,000 entries and 10 s. A step adds nothing when the setting is off. The fallback attempt is bounded by the remaining wall time (Autonomous) or 3600 s (human-gated).

**Constraints**: Off by default and byte-for-byte unchanged when off. No sandbox loosened, no bypass flag, no extra writable root, no tool network. No content leaves loopback. No shipped model list. No account, quota or credential data stored. Stdlib only.

**Scale/Scope**: New `fallback.py` about 380 lines; `agent.py` about +110 (cause capture, state evidence, decision, second attempt, private `CODEX_HOME`, `--json` handling); `run.py` about +70 (flags, setting write, status line, messages); `ledger.py` about +40 (enums, review provenance rule); `artifacts.py` about +10; `autonomy.py` about +60 (ignored and ref digests, record line). One ADR, one evaluation record, documentation updates, about 75 tests.

No NEEDS CLARIFICATION remains. Host facts not observable during planning (exact Codex config key, `--json` event shape, sandbox nesting, quota message text) are pilot task R10, and every dependent check fails closed.

## Constitution Check

*Gate before Phase 0, re-checked after Phase 1. Result: **PASS** both times, no violations.*

| Principle | How the design holds it |
| --- | --- |
| 1. Projects own only their files (BL-INV-001) | Nothing new is committed by a project; `fallback.json` is operator state outside the checkout; no new installed path or ignore rule. |
| 2. Nothing executes from a writable checkout (BL-INV-002) | `codex` is resolved with `autonomy.trusted_program` (never from a working tree or temp directory); the wrapper and `fallback.py` are the installed, trusted copies; the launcher's trust and tamper refusals are untouched. |
| 3. Delegated authority (BL-INV-003) | The fallback runs under the same confinement and Codex sandbox as a primary step, with a stricter environment (no provider key) and a private, empty Codex home (no user MCP servers, notify program or profile); an explicit `permission_mismatch` check refuses anything wider; a non-nesting sandbox refuses rather than loosens; only the operator's launcher writes the setting. |
| 4. A project picks a version, never a source (BL-INV-004) | No download source added; Ballast installs no model or CLI. Residual: Codex `--oss` pulls a model that disappears between probe and run (research R5), which never carries repository content. |
| 5. Postconditions over exit codes (BL-INV-005) | A fallback step succeeds only through the same artifact validation and draft contract as a primary; an unparsable `--json` stream fails the attempt. |
| 6. Portable, dependency-free tools | Standard library only (`urllib`, `json`, `ipaddress`); no new Python dependency. |
| 7. Generic by default | No project names; the model is operator input; Ollama is the only provider value, named as a backend, not a project. |
| 8. Executable evidence | Every AC and SC maps to tests in [quickstart.md](quickstart.md), including each refusal, the off path and idempotency; the pilot is recorded. |
| 9. Provisional decisions (BL-INV-006) | This plan, the ADR proposal and R1 to R10 are agent-provisional; no artifact calls them approved. |

Post-design re-check: the contracts add no writable path for agents, no new network destination beyond loopback, and no committed setting. **PASS**.

## Architecture Boundaries

- **Affected areas**:
  - the headless agent wrapper `tools/spec_workflow/agent.py` (attempt loop, cause capture, state evidence);
  - a new `tools/spec_workflow/fallback.py` (setting, classification, probes, argv/env, permission comparison, `--json` parsing, ledger writes);
  - the launcher's run command `tools/spec_workflow/run.py` (start/resume flags);
  - the Agent Run Ledger `tools/spec_workflow/ledger.py` and `ledger-schema.md`;
  - `autonomy.py` (ignored-path and ref digests, `record.md` line) and `artifacts.py` (Autonomous review and draft provenance);
  - the ledger report's review provenance for human-gated runs;
  - documentation.
- **Contracts and data flow**: operator `ballast run start|resume --local-fallback` → `run.py` validates → `fallback.json` (operator state) → Spec Kit dispatches a step → `agent.main` → primary `_attempt` → `fallback.classify` → (setting on, recoverable) state, probe and permission checks → refuse (stderr, `route` event, entry) or `_autonomous_run` counts → fallback `_attempt` (Codex `--oss`, same confinement) → artifact and draft checks → `route` + `usage` events, `steps.jsonl` entry → exit code to Spec Kit. Ownership is unchanged: the launcher owns the setting, the wrapper owns attempts and their records, the recorders own decisions, and the ledger stays the single record that the Draft PR reads. Contracts: [operator-cli.md](contracts/operator-cli.md), [wrapper-fallback.md](contracts/wrapper-fallback.md), [ledger.md](contracts/ledger.md).
- **Architecture references**:
  - [constitution](../../.specify/memory/constitution.md) BL-INV-002, BL-INV-003, BL-INV-005, BL-INV-006;
  - [TECHNICAL-SPEC 6.4 subscription-aware routing, 6.5 paid-API guard, 9.1 v1.0 target](../TECHNICAL-SPEC.md);
  - [PRODUCT-SPEC 5.3, 5.4](../PRODUCT-SPEC.md);
  - [ADR-0003](../../docs/adr/0003-launcher-github-authority.md) (trusted programs);
  - [ADR-0004](../../docs/adr/0004-autonomous-provisional-decisions.md);
  - [ADR-0010](../../docs/adr/0010-autonomous-resume-and-bounded-recovery.md) (limits and retries);
  - [ledger schema](../../tools/spec_workflow/ledger-schema.md);
  - [model routing policy](../../docs/policies/model-routing.md);
  - [project workflow R2 boundaries](../../docs/policies/project/workflow.md).
- **Proposed architecture decisions** (agent-provisional; written with the implementation as `docs/adr/0012-local-zero-cost-fallback.md`, accepted only when the PR merges):
  1. **ADR-0012 Local zero-cost fallback through Codex local-provider mode.** The wrapper may make one fallback attempt per step on `codex exec --oss --local-provider ollama` against an operator-named, locally installed, non-cloud model at Ollama's default loopback endpoint `127.0.0.1:11434` (DEC-0003; the operator cannot choose another endpoint). Conditions: the operator opted in per run; the step's first primary attempt failed on quota, availability or a missing CLI; the attempt changed nothing; and runtime checks prove free status, privacy, capability and an equal permission profile, refusing otherwise. The changed-state evidence covers tracked, untracked and git-ignored worktree paths and the refs, and refuses when it cannot be established (DEC-0001). The fallback reads no user Codex configuration and refuses while the user's skills directory is non-empty. The ADR records the remaining residual risk (a model pull race), the cost of the state walk and the host result that Autonomous steps refuse while Codex's sandbox does not nest (R1 to R9).

## Repository Impact

| Path | Change |
| --- | --- |
| `tools/spec_workflow/fallback.py` | New, per [wrapper-fallback.md](contracts/wrapper-fallback.md#module-boundary). |
| `tools/spec_workflow/agent.py` | Capture `cli-unavailable` instead of returning early when a setting is on; state evidence before and after the primary; classify the primary; decision, probes and one fallback attempt in `main` on the first attempt only; private `CODEX_HOME`; `local_fallback` in `meta.json`; `_attempt(fallback=...)` with Codex `--oss` argv/env, `--json` parsing, timeout and entry fields; module docstring. |
| `tools/spec_workflow/run.py` | `--local-fallback` in `_split_mode` and resume option parsing for human-gated and Autonomous; Chat refusal; setting write and printed line; `status` line; usage text. |
| `tools/spec_workflow/ledger.py` | `route` enum value, three optional fields, cross-field validation, report counts, no cross-provider review in a run whose review step fell back. |
| `tools/spec_workflow/ledger-schema.md` | One paragraph on the additions. |
| `tools/spec_workflow/artifacts.py` | Fallback-step provenance: `cross_provider` false, runner-known provider and model. |
| `tools/spec_workflow/autonomy.py` | `ignored_digest` and `refs_digest`; `record.md` "Local fallback" line; step-entry optional fields accepted by readers. |
| `templates/policies/spec-kit-workflow.md` | "Local fallback" subsection: enable, model, refusal reasons, turning it off, what it never does. |
| `templates/policies/model-routing.md` | One paragraph: the fallback is a zero-cost availability route, not a routing profile or cross-provider review. |
| `specs/TECHNICAL-SPEC.md` | 6.4/6.5/9.1: the qualified fallback, its checks and refusal. |
| `README.md` | One line under `ballast run` options. |
| `docs/adr/0012-local-zero-cost-fallback.md` | New; proposed until merge. |
| `specs/23-free-fallback/evaluation.md` | New; pilot evidence (AC-018). |
| `specs/23-free-fallback/acceptance-evidence.json` | AC → test mapping. |
| `tests/test_fallback.py` | New: `SettingTests`, `StateTests`, `ModuleTests`, `ClassifyTests`, `ProbeTests`, `PermissionTests`, `EventsTests`, `WrapperFallbackTests`, `LedgerFallbackTests`, `ArtifactsFallbackTests`, `RunCliTests`. |
| `tests/test_agent_run_ledger.py` | Enum, field and cross-field validation cases. |
| `tests/test_autonomous_run.py` | `record.md` line; off-path regression. |

## Feature Artifacts

```text
specs/23-free-fallback/
├── discovery.md        # input evidence
├── intent.md
├── spec.md
├── plan.md             # this file
├── research.md         # Phase 0 decisions R1–R10
├── data-model.md       # setting, attempt, cause, decision, ledger additions
├── contracts/
│   ├── operator-cli.md       # ballast run start/resume --local-fallback
│   ├── wrapper-fallback.md   # fallback.py API, agent.main flow, refusals
│   └── ledger.md             # route additions, events per case
├── quickstart.md       # AC/SC → test map, pilot
├── evaluation.md       # written by the pilot task
├── checklists/
├── autonomous/
├── tasks.md            # next: speckit-tasks
├── decisions.md        # DEC-0001 (tasks-gate contradictions, spec kept)
└── reviews/
```

## Complexity Tracking

No constitution violations.
